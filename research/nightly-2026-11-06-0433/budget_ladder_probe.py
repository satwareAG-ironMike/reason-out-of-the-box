#!/usr/bin/env python3
"""Round 51 probe: the per-item output-budget ladder at the generator's load floor.

Question (issue #71, #126, #94, #100, #105). Round 50 established that on the ladder family
accuracy never turns over inside k = 32 while delivery does, that every accuracy loss in that
firing was a `finish_reason = length` record at the 2048 cap, and that the cheap trace route to
separating computation from surfacing refuses itself (recovery rule calibrated at 0.5652). What
round 50 left open, and what this instrument measures, is the budget axis: for each item, how
many output tokens the traversal consumes before a verdict surfaces, where that quantity crosses
the protocol cap, and whether cutting a trace short *below* its own measured natural stop still
yields a verdict.

Construction. The shipped generator (generators/ladders.py, repaired by PR #69) draws the chain
count C uniformly from [2, k+2], so facts = C * k. Round 50 held the prompt inside a fixed
fact band, which is only feasible while 2k fits the band: at k = 40 the minimum fact count is
80 > 72. This round therefore walks the generator's LOAD FLOOR: exactly C = 2 components,
facts = 2k, the smallest prompt that a depth-k item can have at all. Load then grows at the
minimum possible rate (16, 32, 48, 64, 80, 96 facts at k = 8, 16, 24, 32, 40, 48), so the depth
effect is separable from the load effect in the only direction the generator allows, and the
fact count is recorded next to every depth (issue #126's panel rule).

Two structural limits of the instrument are measured, not assumed:
  * the entity pool. `ladders._entity` samples distinct synthetic names from a fixed pool; the
    deepest level a series can be generated at is k = 48 (level 49 raises RuntimeError: entity
    pool exhausted). That caps any grid extension the shipped generator can serve.
  * the load floor. facts >= 2k by construction (C >= 2 components of exactly k edges), so a
    constant-prompt depth ladder cannot pass k = 32. Round 50's matched-load ladder ends where
    the generator begins to force load.

Protocol, frozen in gate.json before any prompt:
  Stage 1. The floor grid: levels 8, 16, 24, 32, 40, 48; per cell the first two gold-yes and the
    first two gold-no items in generation order whose fact count equals 2k exactly; dispatched
    once each at the protocol cap (2048 tokens, temperature 0). Constant baseline is 0.50 per
    cell by construction.
  Stage 2. The per-item budget ladder, on four pre-registered candidate items (the gold-yes item
    with the smallest seed in each of the cells k = 24, 32, 40, 48): if stage 1 delivered that
    item with a natural stop L (finish_reason = stop), re-dispatch it at rungs 0.8L and 0.5L
    (floor to 64); if stage 1 truncated it, the ladder for that item is censored and recorded as
    such, unscored. Stage 2 also carries two identical re-dispatches (levels 40 and 48) as the
    issue #100 in-firing self-agreement control.
  Readouts: the label-split cost of a traversal (positive versus negative natural stops), the
    longest common prefix of an interrupted output with the same item's delivered output (whether
    one dispatch per item is enough to predict delivery at every rung, which is what the
    pre-registered budget ladder in docs/study-design.md needs), and the cross-firing replicate
    against round 50's archived M32 cell, which is byte-for-byte this round's k = 32 floor cell.

Archived reference, vendored as in-file constants and certified before dispatch (the round-50
archive lives in an open PR, so the post-merge tree carries the constants, not the file): the
twelve round-50 matched-cell records at k = 16, 24, 32 with their prompt digests, gold labels,
completion-token counts and finish reasons. `certify_reference` regenerates those items from the
shipped generator and refuses to dispatch unless every prompt digest, gold label and finish
reason reproduces. No endpoint value (base URL, model id, key) is ever written: the artifacts
carry a one-way digest of the serving id, and every string passes the sanitizer first.

Usage:
  budget_ladder_probe.py --selftest
  budget_ladder_probe.py --gate
  budget_ladder_probe.py --dry-run
  NIGHTLY_BASE_URL=... NIGHTLY_MODEL_ID=... NIGHTLY_API_KEY=... budget_ladder_probe.py --run
  budget_ladder_probe.py --resume ...    (same flags as --run, refuses on gate-hash drift)
  budget_ladder_probe.py --rescore ...   (rebuild gate+summary from raw.jsonl, no endpoint)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "generators"))

import ladders  # noqa: E402  (the shipped generator, repaired by PR #69)

SEED_BASE = 20261005
SCAN = 400                 # how far into each level's series the selection rule scans
MAX_TOKENS = 2048          # protocol cap
TIMEOUT_S = 600            # issue #73: per-dispatch wall budget
CALL_CAP = 40              # protocol cap: prompts per round, health included
DISPATCH_BUDGET_S = 1380   # wall-clock budget for the dispatch phase (30/60 slots of the firing)
FLOOR_LEVELS = (8, 16, 24, 32, 40, 48)
GENERATOR_CEILING = 48     # measured: level 49 raises RuntimeError in the entity pool
INTERRUPT_LEVELS = (24, 32, 40, 48)
PRIORITY_MIN_LEVEL = 24      # cutoff mode keeps the wall question and stage 2, drops k = 8, 16
INTERRUPT_FRACS = (0.8, 0.5)
DUP_LEVELS = (40, 48)
GATE_SCHEMA = "round51-gate-v1"
# The frozen gate blob: canonical JSON of gate_spec(). --run and --resume recompute it and
# refuse to dispatch if it moved (pinned in the instrument so a later edit cannot move the
# gate unseen - issue #120 discipline).
ROUND51_GATE_BLOB_SHA256 = "60b0d62c165f8c2a225a4eeb499e456859c281c4d30b64855c6a4dc3bf247716"

# Vendored archived reference: round 50's matched-load records at k = 16, 24, 32
# (research/nightly-2026-11-06-0259/raw.jsonl, blob digest given in the README; the file is in
# an open PR, so these constants are what the post-merge tree certifies). Fields:
# (level, seed, n_facts, gold, prompt_sha16, completion_tokens, finish_reason).
# Extracted from research/nightly-2026-11-06-0259/raw.jsonl, which lives in the still-open PR
ROUND50_REF = (
    (16, 52261011, 64, "no", "7e90775624d3de86", 1221, "stop"),
    (16, 52261031, 64, "yes", "4d608e9f700a0f24", 682, "stop"),
    (16, 52261047, 64, "no", "c56eb6dcbf29caaf", 1140, "stop"),
    (16, 52261067, 64, "yes", "2d3676e919845fe1", 674, "stop"),
    (24, 68261006, 72, "no", "6d48238c20691081", 2048, "length"),
    (24, 68261023, 72, "no", "26ef5c2ea4fcb3a0", 2021, "stop"),
    (24, 68261068, 72, "yes", "310af79db8de108b", 861, "stop"),
    (24, 68261122, 72, "yes", "a2ea8c02cd8b4c49", 804, "stop"),
    (32, 84261011, 64, "no", "d6b9e74cf69a8e28", 1646, "stop"),
    (32, 84261050, 64, "no", "0d3347946e358ce5", 2048, "length"),
    (32, 84261142, 64, "yes", "e9615dd04c8c87a2", 988, "stop"),
    (32, 84261174, 64, "yes", "766d6e09cba617c4", 1001, "stop"),
)
# Round 50's whole-file raw.jsonl blob, recorded for provenance only (never read at runtime).
ROUND50_RAW_BLOB_SHA256 = "e2a9d47ecb69e40e4e908df9adf20362ea6f9ff9e0430516148a5e4c8021041f"
# Round 6's fitted length law (research/nightly-2026-10-16-0400/), the registered band basis.
ROUND6_TOKENS_PER_HOP = 80.0
ROUND6_FIT = "completion_tokens = -36 + 80k"

# Measured generator geometry, from a scan of 400 items per level (the numbers gate the ladder
# design; --selftest re-measures every one of them against the shipped generator and refuses if
# one moved, so these constants cannot go stale).
CEILING_MEASURED = {
    "pool_names": 2700,               # len(ONSET) * len(VOWEL) * len(CODA) in generators/ladders.py
    "rejection_tries": 100,           # ladders._entity draws each fresh name in at most this many tries
    "max_entities_at_max_level": 2450,  # largest unique-name count seen at level 48 (0.91 of the pool)
    "first_failing_item_index": 16,   # level 49: 16 items generate, then RuntimeError on item 16 of 300
    # Items whose fact count equals the load floor 2k, out of 400 scanned at each level. The floor
    # family (two disjoint k-edge paths) is the smallest-load subfamily and it thins with depth,
    # which is why the depth walk can only run along the floor.
    "floor_family_counts": {8: 58, 16: 22, 24: 14, 32: 12, 40: 9, 48: 6},
    "max_entities_by_level": {8: 90, 16: 306, 24: 650, 32: 1122, 40: 1722, 48: 2450},
    # Item-by-item scans (raise caught, never a selection path) above the registered ceiling:
    # the raise is a collision ceiling on item size, and load-floor items survive well past it.
    "past_ceiling_scans": {
        49: {"scanned": 300, "generated": 285, "raised": 15, "first_raise_index": 16,
             "floor_items": 5, "max_names": 2500},
        50: {"scanned": 300, "generated": 284, "raised": 16, "first_raise_index": 29,
             "floor_items": 6, "max_names": 2448},
        64: {"scanned": 300, "generated": 178, "raised": 122, "first_raise_index": 4,
             "floor_items": 1, "max_names": 2470},
    },
}

IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV6 = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b")
URLISH = re.compile(r"\bhttps?://[^\s\"']+")
YES_NO = re.compile(r"\b(yes|no)\b", re.IGNORECASE)
SENSITIVE = re.compile(r"(?i)\b(host|token|secret)\b\s*[:=]\s*\S+")
CENSUS_PROMPT = ("Rule: for all x, y, z: if x precedes y and y precedes z, then x "
                 "precedes z. Facts state direct precedes links.\nFacts:\nabl precedes "
                 "bri.\nbri precedes cro.\n\nQuestion: does abl precedes cro?\n"
                 "Answer with exactly one word: yes or no.")


# ---------------------------------------------------------------- item side

def bfs_dist(facts: list, src: str) -> dict:
    """Independent solver: unbounded directed BFS, node -> distance."""
    graph: dict = {}
    for s, _, t in facts:
        graph.setdefault(s, []).append(t)
    dist = {src: 0}
    q = deque([src])
    while q:
        u = q.popleft()
        for v in graph.get(u, ()):
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist


def components(facts: list) -> list[set]:
    """Weak components of the fact graph (the issue #67 isomorphism guard)."""
    graph: dict = {}
    for s, _, t in facts:
        graph.setdefault(s, []).append(t)
        graph.setdefault(t, []).append(s)
    seen: set = set()
    out: list = []
    for node in graph:
        if node in seen:
            continue
        comp = {node}
        seen.add(node)
        q = deque([node])
        while q:
            u = q.popleft()
            for v in graph[u]:
                if v not in seen:
                    seen.add(v)
                    comp.add(v)
                    q.append(v)
        out.append(comp)
    return out


def check_item(item: dict) -> None:
    """Refuse anything that is not the repaired (component-isomorphic) corpus."""
    lvl = item["level"]
    facts = item["facts"]
    assert all(rel == ladders.REL for _, rel, _ in facts), item
    comps = components(facts)
    for comp in comps:
        assert len(comp) == lvl + 1, ("component size", lvl, comp)
    srcs = [s for s, _, _ in facts]
    tgts = [t for _, _, t in facts]
    assert len(srcs) == len(set(srcs)), "an entity is a fact source twice"
    assert len(tgts) == len(set(tgts)), "an entity is a fact target twice"
    qs, _, qt = item["query"]
    assert qs in srcs and qs not in tgts, "query source is not a path head"
    assert qt in tgts and qt not in srcs, "query target is not a path tail"
    dist = bfs_dist(facts, qs)
    assert (item["answer"] == "yes") == (qt in dist), item
    if item["answer"] == "yes":
        assert dist[qt] == lvl == item["chain_len"], item
    else:
        assert item["chain_len"] is None, item


def pick_floor(series: list, level: int, want_yes: int = 2, want_no: int = 2) -> list:
    """Selection rule: generation order, first two yes and two no with facts == 2*level."""
    floor = 2 * level
    got_yes = got_no = 0
    picked: list = []
    for item in series:
        check_item(item)
        if len(item["facts"]) != floor:
            continue
        if item["answer"] == "yes" and got_yes < want_yes:
            picked.append(item)
            got_yes += 1
        elif item["answer"] == "no" and got_no < want_no:
            picked.append(item)
            got_no += 1
        if got_yes == want_yes and got_no == want_no:
            break
    assert got_yes == want_yes and got_no == want_no, (level, got_yes, got_no)
    return picked


_SERIES: dict = {}


def generate_floor(level: int) -> list:
    """This level's series (memoized), plus the shipped-file identity assertion where shipped."""
    if level in _SERIES:
        return _SERIES[level]
    series = ladders.generate_items(level, SCAN, SEED_BASE)
    shipped = REPO / "items" / "ladders" / f"l{level}.jsonl"
    if shipped.exists():
        disk = [json.loads(line) for line in
                shipped.read_text(encoding="utf-8").splitlines()]
        # The shipped file is 300 items deep; the scan runs past it, so the identity
        # assertion covers the shipped prefix only.
        assert disk == series[:len(disk)], (
            f"l{level}: regenerated series is not byte-identical to the shipped file")
    _SERIES[level] = series
    return series


def scan_with_skip(level: int, count: int) -> dict:
    """Evidence about the generator ceiling, never a selection path.

    ladders.generate_items aborts the whole series on the first exhausted item. Scanning item by
    item with the raise caught shows the ceiling is a collision ceiling on item *size* (an item
    draws C*(level+1) fresh names with C up to level+2, and ladders._entity allows 100 rejection
    tries per name), not a ceiling on depth: the same scan still yields load-floor items (C = 2,
    2*(level+1) names) well past the level where the whole-series call dies. Cells are never built
    this way - the registered rule scans a whole series - so this function only measures.
    """
    generated = raised = floor_items = 0
    first_raise = None
    max_names = 0
    for i in range(count):
        seed = SEED_BASE + 2_000_000 * level + i
        try:
            item = ladders.generate_item(level, seed)
        except RuntimeError:
            raised += 1
            if first_raise is None:
                first_raise = i
            continue
        generated += 1
        check_item(item)
        max_names = max(max_names, len({n for s, _, t in item["facts"] for n in (s, t)}))
        if len(item["facts"]) == 2 * level:
            floor_items += 1
    return {"level": level, "scanned": count, "generated": generated, "raised": raised,
            "first_raise_index": first_raise, "floor_items": floor_items, "max_names": max_names}


def build_cells() -> dict:
    """Every stage-1 cell, built and certified before any prompt is spent."""
    cells: dict = {}
    for level in FLOOR_LEVELS:
        cells[f"F{level:03d}"] = pick_floor(generate_floor(level), level)
    # Stage-2 candidates and duplicate controls are decided from item fields only, never from
    # an outcome: the gold-yes item with the smallest seed in each interrupt cell.
    cand: dict = {}
    for level in INTERRUPT_LEVELS:
        yes_items = [it for it in cells[f"F{level:03d}"] if it["answer"] == "yes"]
        cand[level] = min(yes_items, key=lambda it: it["seed"])
    cells["_CAND"] = [cand[level] for level in INTERRUPT_LEVELS]
    cells["_DUP"] = [cand[level] for level in DUP_LEVELS]
    return cells


def stage1_jobs(cells: dict) -> list:
    """Stage-1 dispatch list: every floor cell, levels descending, item order as generated.

    The order is a robustness choice, not a claim: the wall question lives in the deep cells, so
    a wall-clock cutoff costs the shallow law-anchor cells (8, 16) instead of the wall.
    """
    jobs = []
    for level in reversed(FLOOR_LEVELS):
        for item in cells[f"F{level:03d}"]:
            jobs.append((f"F{level:03d}", item, MAX_TOKENS, "grid", False))
    return jobs


def stage2_plan(cells: dict, stage1: dict) -> list:
    """Stage 2 is a deterministic function of stage-1 records and nothing else.

    stage1 maps (cell, seed, rung) -> record. For each pre-registered candidate: delivered with
    a natural stop L gives two interrupt dispatches at 0.8L and 0.5L; a truncated candidate gives
    none and is recorded as censored. The duplicate controls are identical re-dispatches.
    """
    plan = []
    for level in reversed(INTERRUPT_LEVELS):
        item = next(cand for cand in cells["_CAND"] if cand["level"] == level)
        cell = f"F{level:03d}"
        rec = stage1.get((cell, item["seed"], MAX_TOKENS))
        if rec is None:
            continue  # stage 1 never ran this item: the ladder for it does not exist
        if rec["finish_reason"] == "stop" and rec["delivered"]:
            for frac in INTERRUPT_FRACS:
                rung = rung_for(rec["completion_tokens"], frac)
                plan.append((f"I{level:03d}", item, rung, "ladder", False))
        else:
            plan.append((f"I{level:03d}", item, 0, "censored", False))
    for level in reversed(DUP_LEVELS):
        item = next(cand for cand in cells["_DUP"] if cand["level"] == level)
        cell = f"F{level:03d}"
        rec = stage1.get((cell, item["seed"], MAX_TOKENS))
        if rec is not None:
            plan.append((f"DUP-F{level:03d}", item, MAX_TOKENS, "dup", True))
    return plan


def rung_for(natural_stop: int, frac: float) -> int:
    """Interrupt rung: floor(frac * L / 64) * 64, strictly below L and inside the cap."""
    rung = int(natural_stop * frac // 64) * 64
    assert 0 < rung < natural_stop <= MAX_TOKENS, (natural_stop, frac, rung)
    return rung


# ---------------------------------------------------------------- prompt side

def render_prompt(item: dict) -> str:
    """The round-6 / round-50 template, byte-identical (required for prompt pairing)."""
    facts = "\n".join(f"{s} {r} {t}." for s, r, t in item["facts"])
    qs, qrel, qt = item["query"]
    return (f"{item['rule']}\nFacts:\n{facts}\n\n"
            f"Question: does {qs} {qrel} {qt}?\n"
            "Answer with exactly one word: yes or no.")


def prompt_digest(item: dict) -> str:
    return hashlib.sha256(render_prompt(item).encode()).hexdigest()[:16]


def declared_answer(text: str) -> str | None:
    """Answer-field readout: the last standalone yes/no in the answer channel."""
    hits = YES_NO.findall(text or "")
    return hits[-1].lower() if hits else None


# ---------------------------------------------------------------- transport

def sanitize(text: str, secrets: tuple = ()) -> str:
    """Public-only rule: no endpoint value, host, IP, URL or credential reaches a file."""
    out = text if text is not None else ""
    for secret in secrets:
        if secret:
            out = out.replace(str(secret), "[redacted]")
    out = URLISH.sub("[redacted-url]", out)
    out = IPV4.sub("[redacted-ip]", out)
    out = IPV6.sub("[redacted-ip]", out)
    out = SENSITIVE.sub("[redacted-credential]", out)
    return out


def call_endpoint(prompt: str, base: str, model: str, key: str, max_tokens: int) -> dict:
    """One chat completion. Returns the raw response dict or raises RuntimeError."""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }).encode()
    headers = {"Content-Type": "application/json"}
    if key:  # a local slot that serves without a credential has key == ""
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body,
                                 headers=headers)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"transport:{type(exc).__name__}") from exc
    return {"payload": payload, "wall_s": round(time.time() - t0, 3)}


def census_of(payload: dict) -> dict:
    """Field census (issue #105): which field supplies the reasoning channel."""
    msg = {}
    try:
        msg = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        msg = {}
    fields = sorted(k for k in msg if k != "role")
    rc = msg.get("reasoning_content") or ""
    rf = msg.get("reasoning") or ""
    source = "reasoning_content" if rc else ("reasoning" if rf else "")
    return {"fields": fields, "reasoning_content_chars": len(rc),
            "reasoning_field_chars": len(rf), "reasoning_source": source}


def parse_answer_field(msg: dict) -> tuple:
    """Answer-channel readout: the answer field only, never a trace token.

    The family's trace-recovery rules stay refused after round 50's calibration failure (last
    standalone yes/no agreed with the delivered answer on 13 of 23 records, and the captured
    token was the model's own instruction echo in 10 of 10 disagreements). Trace text is still
    stored, but only for prefix identity and length.
    """
    content = msg.get("content") or ""
    if isinstance(content, list):  # some deployments serve content parts
        content = "".join(str(part.get("text", "")) if isinstance(part, dict) else str(part)
                          for part in content)
    trace = msg.get("reasoning_content") or msg.get("reasoning") or ""
    answer = declared_answer(content)
    source = "content" if answer is not None else "none"
    return answer, source, content, trace


def health_probe(base: str, model: str, key: str) -> dict:
    """Issue #73: one small call before the grid. 256 tokens, not MAX_TOKENS (round 22)."""
    info = {"probe": "health"}
    try:
        res = call_endpoint(CENSUS_PROMPT, base, model, key, 256)
        payload = res["payload"]
        msg = payload["choices"][0]["message"]
        info.update({"ok": True, "wall_s": res["wall_s"],
                     "census": census_of(payload),
                     "completion_tokens": payload.get("usage", {}).get("completion_tokens"),
                     "finish_reason": payload["choices"][0].get("finish_reason")})
    except RuntimeError as exc:
        info.update({"ok": False, "error": str(exc)})
    return info


# ---------------------------------------------------------------- records

def score_record(job, item, resp, err, rung, gate_hash) -> dict:
    cell, is_dup = job[0], job[4]
    stage = job[3]
    rec = {"stage": stage, "cell": cell, "gate": gate_hash, "rung": rung,
           "is_dup": is_dup, "dispatch_index": job[5], "attempts": 1,
           "level": item["level"], "seed": item["seed"], "seed_hash": item["seed_hash"],
           "gold": item["answer"], "n_facts": len(item["facts"]),
           "n_chains": len(item["facts"]) // item["level"],
           "prompt_sha256": prompt_digest(item), "prompt_chars": len(render_prompt(item)),
           "pair_key": f"{item['seed']}|{prompt_digest(item)}|{rung}",
           "error": err, "delivered": False, "outcome": "transport_error",
           "correct": None, "declared": None, "declared_source": None,
           "content": "", "trace": "", "trace_chars": 0, "completion_tokens": None,
           "prompt_tokens": None, "finish_reason": None, "wall_s": None, "census": None}
    if resp is None:
        if err == "censored_by_cap":
            rec["outcome"] = "censored_by_cap"
        return rec
    payload, wall = resp["payload"], resp["wall"]
    try:
        choice = payload["choices"][0]
        msg = choice["message"]
    except (KeyError, IndexError, TypeError):
        rec["outcome"] = "malformed_response"
        rec["error"] = "malformed_response"
        return rec
    answer, source, content, trace = parse_answer_field(msg)
    usage = payload.get("usage") or {}
    secrets = tuple(job[6])
    rec.update({
        "declared": answer,
        "declared_source": source,
        "content": sanitize(content, secrets),
        "trace": sanitize(trace, secrets),
        "trace_chars": len(trace),
        "completion_tokens": usage.get("completion_tokens"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "finish_reason": choice.get("finish_reason"),
        "wall_s": wall,
        "census": census_of(payload),
    })
    gold = item["answer"]
    if answer is not None:
        rec["delivered"] = True
        rec["correct"] = (answer == gold)
        rec["outcome"] = "delivered_correct" if rec["correct"] else "delivered_wrong"
    elif rec["finish_reason"] == "length":
        rec["outcome"] = "undelivered_truncated"
    else:
        rec["outcome"] = "undelivered_empty"
    return rec


# ---------------------------------------------------------------- analysis

def join_key(rec: dict) -> str:
    """Dispatch identity is the ITEM plus the rung, never the cell label (round 50's defect)."""
    if rec.get("pair_key"):
        return rec["pair_key"]
    if rec.get("seed") and rec.get("prompt_sha256"):
        return f"{rec['seed']}|{rec['prompt_sha256']}|{rec.get('rung')}"
    return ""


def lcp_len(a: str, b: str) -> int:
    """Length of the longest common prefix of two strings."""
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def ols_slope(points: list) -> float | None:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return None
    return round(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den, 3)


def wilson(k: int, n: int, z: float = 1.96) -> tuple:
    if n == 0:
        return (None, None)
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (round(max(0.0, (centre - half) / denom), 4),
            round(min(1.0, (centre + half) / denom), 4))


def grid_rows(records: list) -> list:
    """Per-cell per-arm table over the stage-1 grid."""
    out = []
    cells = sorted({r["cell"] for r in records if r["stage"] == "grid"})
    for cell in cells:
        rows = [r for r in records if r["cell"] == cell and r["stage"] == "grid"]
        level = rows[0]["level"]
        for arm in ("yes", "no", "all"):
            sub = [r for r in rows if arm == "all" or r["gold"] == arm]
            if not sub:
                continue
            delivered = [r for r in sub if r["delivered"]]
            stopped = [r for r in delivered if r["finish_reason"] == "stop"]
            out.append({
                "cell": cell, "level": level, "arm": arm, "n": len(sub),
                "facts": sub[0]["n_facts"], "chains": sub[0]["n_chains"],
                "delivered": len(delivered), "truncated": sum(
                    1 for r in sub if r["finish_reason"] == "length"),
                "correct": sum(1 for r in delivered if r["correct"]),
                "accuracy_over_n": round(sum(1 for r in delivered if r["correct"]) / len(sub), 4),
                "accuracy_over_delivered": round(
                    sum(1 for r in delivered if r["correct"]) / len(delivered), 4)
                    if delivered else None,
                "mean_stop_tokens": round(sum(r["completion_tokens"] for r in stopped)
                                          / len(stopped), 1) if stopped else None,
                "max_stop_tokens": max((r["completion_tokens"] for r in stopped), default=None),
                "censored": len(sub) - len(stopped),
                "mean_trace_chars": round(sum(r["trace_chars"] for r in sub) / len(sub), 1),
            })
    return out


def ladder_rows(records: list) -> dict:
    """Stage 2: per-candidate interrupt readout, paired to stage 1 by dispatch identity."""
    grid = {join_key(r): r for r in records if r["stage"] == "grid"}
    items: dict = {}
    for r in records:
        if r["stage"] not in ("ladder", "censored"):
            continue
        seed = r["seed"]
        rung = r["rung"]
        base = grid.get(f"{seed}|{r['prompt_sha256']}|{MAX_TOKENS}")
        entry = items.setdefault(seed, {"level": r["level"], "seed": seed, "gold": r["gold"],
                                       "rungs": [], "censored": False, "lcp_ratios": [],
                                       "natural_stop": None, "interrupt_delivered": 0})
        if r["stage"] == "censored":
            entry["censored"] = True
            continue
        if rung >= MAX_TOKENS:
            continue
        entry["rungs"].append(rung)
        if base is None:
            continue
        entry["natural_stop"] = base["completion_tokens"]
        # Generation order on every deployment in this family is trace first, answer second.
        text_new = (r["trace"] or "") + (r["content"] or "")
        text_base = (base["trace"] or "") + (base["content"] or "")
        # 1.0 means the whole interrupted output is a strict prefix of the delivered one.
        ratio = lcp_len(text_new, text_base) / max(1, len(text_new))
        entry["lcp_ratios"].append(round(ratio, 4))
        if r["delivered"]:
            entry["interrupt_delivered"] += 1
            entry.setdefault("interrupt_answers", []).append(
                {"rung": rung, "declared": r["declared"], "correct": r["correct"],
                 "finish_reason": r["finish_reason"], "completion_tokens": r["completion_tokens"]})
    return {"items": sorted(items.values(), key=lambda e: (-e["level"], e["seed"])),
            "n_candidates": len(items)}


def dup_rows(records: list) -> list:
    """In-firing self-agreement pairs (#100): keyed on the item, never on the cell label."""
    by_key: dict = {}
    for r in records:
        if r["stage"] == "grid":
            by_key.setdefault(join_key(r), []).append(r)
    out = []
    for r in records:
        if r["stage"] != "dup":
            continue
        key = join_key(r).rsplit("|", 1)[0] + f"|{MAX_TOKENS}"
        originals = by_key.get(key) or []
        if not originals:
            out.append({"pair": join_key(r), "joined": False})
            continue
        orig = originals[0]
        same_bytes = (orig["content"], orig["trace"]) == (r["content"], r["trace"])
        same_tokens = (orig["completion_tokens"] == r["completion_tokens"]
                       and orig.get("prompt_tokens") == r.get("prompt_tokens"))
        out.append({"pair": join_key(r), "joined": True, "byte_identical": same_bytes,
                    "token_identical": same_tokens,
                    "same_answer": orig["declared"] == r["declared"],
                    "tokens": [orig["completion_tokens"], r["completion_tokens"]]})
    return out


def cross_fire_rows(records: list) -> dict:
    """Cross-firing replicate: this round's k = 32 floor cell is round 50's archived M32 cell."""
    ref = {row[1]: row for row in ROUND50_REF if row[0] == 32}
    rows = [r for r in records if r["cell"] == "F032" and r["stage"] == "grid"]
    joined = matched = 0
    detail = []
    for r in rows:
        arch = ref.get(r["seed"])
        if arch is None:
            detail.append({"seed": r["seed"], "joined": False})
            continue
        joined += 1
        digest_ok = r["prompt_sha256"] == arch[4]
        outcome_ok = r["finish_reason"] == arch[6]
        if digest_ok and outcome_ok:
            matched += 1
        detail.append({"seed": r["seed"], "joined": True, "digest_ok": digest_ok,
                       "archived_stop": arch[5], "archived_finish": arch[6],
                       "this_stop": r["completion_tokens"], "this_finish": r["finish_reason"],
                       "outcome_ok": outcome_ok})
    return {"n_joined": joined, "n_reproduced": matched, "n_cell": len(rows), "detail": detail}


# ---------------------------------------------------------------- gate

def gate_spec() -> dict:
    """The frozen registration: rows, bands and the tier rule, all decided pre-dispatch."""
    return {
        "schema": GATE_SCHEMA,
        "question": ("Where does the per-item output budget cross the 2048 cap on the ladder "
                     "family at the generator's load floor (facts = 2k), and does a trace cut "
                     "below its own measured natural stop still yield a verdict?"),
        "serves": ["#71", "#126", "#94", "#100", "#105", "#73", "#65"],
        "cells": {"levels": list(FLOOR_LEVELS), "rule": ("first two gold-yes and first two "
                                                        "gold-no in generation order with facts "
                                                        "== 2*level exactly; 4 items per cell; "
                                                        "constant baseline 0.50 per cell"),
                  "stage1_calls": len(FLOOR_LEVELS) * 4,
                  "dispatch_order": ("levels descending in both stages: the wall question lives in "
                                     "the deep cells, so a wall-clock cutoff costs the shallow law "
                                     "anchors (k = 8, 16) and not the wall"),
                  "stage2": {"interrupt_levels": list(INTERRUPT_LEVELS),
                             "candidate_rule": "smallest-seed gold-yes item in the cell",
                             "rung_rule": "floor(frac*L/64)*64 at frac in {0.8, 0.5}, L = the "
                                          "stage-1 natural stop; a truncated candidate is "
                                          "censored and unscored",
                             "dup_levels": list(DUP_LEVELS)}},
        "generator_ceiling": {
            "measured_max_level": GENERATOR_CEILING,
            "whole_series_call_dies_at": GENERATOR_CEILING + 1,
            "mechanism": ("an item draws C*(level+1) fresh synthetic names with the chain count C "
                          "uniform in 2..level+2, and ladders._entity allows "
                          f"{CEILING_MEASURED['rejection_tries']} rejection tries per name against "
                          f"a pool of {CEILING_MEASURED['pool_names']} names: the raise is a "
                          "collision ceiling on item size, not a ceiling on depth"),
            "pool_names": CEILING_MEASURED["pool_names"],
            "rejection_tries": CEILING_MEASURED["rejection_tries"],
            "max_entities_at_max_level": CEILING_MEASURED["max_entities_at_max_level"],
            "max_entities_by_level": CEILING_MEASURED["max_entities_by_level"],
            "floor_family_counts": CEILING_MEASURED["floor_family_counts"],
            "first_failing_item_index": CEILING_MEASURED["first_failing_item_index"],
            "past_ceiling_scans": CEILING_MEASURED["past_ceiling_scans"],
            "correction": ("the level-49 whole-series call is where the ceiling shows, but the "
                           "same scan done item by item still yields load-floor items (C = 2, "
                           "2*(level+1) names) at 49, 50 and 64, so depth beyond 48 is reachable "
                           "on the floor family; this round stays registered at 48"),
        },
        "load_floor": {"levels": list(FLOOR_LEVELS), "facts": [2 * k for k in FLOOR_LEVELS],
                       "note": ("facts >= 2k is a generator invariant, so a constant-prompt "
                                "depth ladder cannot pass k = 32 (round 50's band ends there)")},
        "rows": [
            {"id": "F1", "kind": "prediction", "arm": "gold-yes at levels 40 and 48",
             "statement": "the positive arm delivers at least 3 of 4 at the two deepest cells",
             "band": "delivered >= 3 of 4"},
            {"id": "F2", "kind": "prediction", "arm": "all 24 stage-1 records",
             "statement": "no delivered record is wrong anywhere on the floor ladder",
             "band": "delivered-wrong == 0"},
            {"id": "F3", "kind": "prediction", "arm": "gold-no at levels 32, 40, 48",
             "statement": "the negative arm delivers at most 3 of 6 at k >= 32 on the floor",
             "band": "delivered <= 3 of 6"},
            {"id": "F4", "kind": "prediction", "arm": "gold-yes uncensored natural stops",
             "statement": ("the positive arm's natural stop grows with depth on the floor at 15 "
                           "to 50 tokens per hop, against round 6's 80 and round 50's 31.3"),
             "band": [15.0, 50.0]},
            {"id": "F5", "kind": "readout", "arm": "label-split cost",
             "statement": ("mean natural stop of gold-no over gold-yes per cell, over uncensored "
                           "records only; reportable when at least 3 of the cells 24, 32, 40, 48 "
                           "carry at least one uncensored negative"),
             "band": "reported or refused"},
            {"id": "I1", "kind": "prediction", "arm": "stage-2 interrupt dispatches",
             "statement": ("cutting a delivered item below its own natural stop surfaces no "
                           "verdict: at most 1 of 8 interrupt dispatches delivers"),
             "band": "delivered <= 1 of 8"},
            {"id": "I2", "kind": "readout", "arm": "prefix determinism",
             "statement": ("an interrupted output is the prefix of the same item's delivered "
                           "output on at least 3 of 4 candidates (longest-common-prefix ratio "
                           ">= 0.90 at both rungs), which is what a per-item budget ladder needs "
                           "in order to need only one dispatch per item"),
             "band": "candidates passing >= 3 of 4"},
            {"id": "N1", "kind": "census", "arm": "issue #105 exposure",
             "statement": "the reasoning-supplying field is open on at least 90% of records",
             "band": "share >= 0.90"},
            {"id": "N2", "kind": "control", "arm": "issue #100 self-agreement",
             "statement": "both in-firing duplicate re-dispatches are byte-identical",
             "band": "byte_identical >= 2 of 2"},
            {"id": "N3", "kind": "control", "arm": "cross-firing replicate",
             "statement": ("the k = 32 floor cell is round 50's archived M32 item set (digest "
                           "pinned) and reproduces its per-item finish state on at least 3 of 4"),
             "band": "reproduced >= 3 of 4"},
        ],
        "tier_rule": [
            "F2 fail -> capability_bound_floor_depth (a delivered answer is wrong: an accuracy "
            "ceiling is placed)",
            "F1 fail -> wall_reaches_both_arms (the positive arm no longer delivers: the cap "
            "binds on the traversal at every label)",
            "F1 pass and F3 pass -> label_split_wall (positives deliver, negatives die)",
            "F1 pass and F3 fail -> no_wall_inside_generator_ceiling (nothing dies to k = 48)",
            "otherwise -> ambiguous",
        ],
        "flags": [
            "I1 fail -> early_commitment_observed (the wall is not a completeness wall)",
            "I2 pass -> one_dispatch_predicts_rungs (budget ladder cost is 1 prompt per item)",
            "any gold-no truncation -> wall_is_label_split, reported beside the tier",
        ],
        "readout_policy": ("answer field only; the trace-recovery rules stay refused after round "
                           "50's calibration failure at 0.5652, so no claim in this round rests "
                           "on a trace-derived verdict. Trace text is stored for prefix "
                           "identity and length only."),
        "budget": {"call_cap": CALL_CAP, "max_tokens": MAX_TOKENS, "temperature": 0.0,
                   "dispatch_budget_s": DISPATCH_BUDGET_S},
        "reference": {"round50_raw_blob_sha256": ROUND50_RAW_BLOB_SHA256,
                      "round50_rows": 12, "round6_fit": ROUND6_FIT},
    }


def gate_blob_sha256() -> str:
    return hashlib.sha256(json.dumps(gate_spec(), sort_keys=True).encode()).hexdigest()


def certify_reference(cells: dict) -> dict:
    """Fail closed: the vendored archived rows must regenerate from the shipped generator."""
    out = {"ok": True, "certified": 0, "refused": []}
    by_seed = {}
    for level in FLOOR_LEVELS:
        for item in generate_floor(level):
            by_seed.setdefault(item["seed"], item)
    for level, seed, facts, gold, sha, tokens, finish in ROUND50_REF:
        item = by_seed.get(seed)
        if item is None:
            out["refused"].append({"seed": seed, "why": "not regenerated by the generator"})
            continue
        if item["level"] != level or len(item["facts"]) != facts:
            out["refused"].append({"seed": seed, "why": "construction moved"})
            continue
        if item["answer"] != gold:
            out["refused"].append({"seed": seed, "why": "gold label moved"})
            continue
        if prompt_digest(item) != sha:
            out["refused"].append({"seed": seed, "why": "prompt digest moved"})
            continue
        if finish not in ("stop", "length"):
            out["refused"].append({"seed": seed, "why": "finish state unreadable"})
            continue
        out["certified"] += 1
    if out["refused"] or out["certified"] != len(ROUND50_REF):
        out["ok"] = False
    # The k = 32 floor cell must be exactly the archived M32 item set.
    cell32 = {it["seed"] for it in cells["F032"]}
    ref32 = {row[1] for row in ROUND50_REF if row[0] == 32}
    if cell32 != ref32:
        out["ok"] = False
        out["refused"].append({"cell": "F032", "why": "not the archived M32 item set"})
    return out


def evaluate_gate(records: list, health: dict) -> dict:
    grid = [r for r in records if r["stage"] == "grid"]
    ladder = [r for r in records if r["stage"] in ("ladder", "censored")]
    interrupts = [r for r in ladder if r["rung"] > 0]
    rows = {row["id"]: row for row in gate_spec()["rows"]}
    res: dict = {}

    def cell_arm(level: int, arm: str) -> list:
        return [r for r in grid if r["level"] == level and (arm == "all" or r["gold"] == arm)]

    yes_deep = [r for r in grid if r["level"] in (40, 48) and r["gold"] == "yes"]
    res["F1"] = {"delivered": sum(1 for r in yes_deep if r["delivered"]), "n": len(yes_deep),
                 "pass": sum(1 for r in yes_deep if r["delivered"]) >= 3 and len(yes_deep) == 4}

    wrong = [r for r in grid if r["delivered"] and r["correct"] is False]
    res["F2"] = {"delivered_wrong": len(wrong), "n": len(grid), "pass": len(wrong) == 0,
                 "wrong_seeds": [r["seed"] for r in wrong]}

    no_deep = [r for r in grid if r["level"] in (32, 40, 48) and r["gold"] == "no"]
    res["F3"] = {"delivered": sum(1 for r in no_deep if r["delivered"]), "n": len(no_deep),
                 "pass": sum(1 for r in no_deep if r["delivered"]) <= 3 and len(no_deep) == 6}

    stops = [(r["level"], r["completion_tokens"]) for r in grid
             if r["gold"] == "yes" and r["delivered"] and r["finish_reason"] == "stop"]
    slope = ols_slope(stops)
    band = rows["F4"]["band"]
    res["F4"] = {"slope_tokens_per_hop": slope, "n_points": len(stops),
                 "points": sorted(stops),
                 "pass": slope is not None and band[0] <= slope <= band[1]}

    split = []
    reportable_cells = 0
    for level in (24, 32, 40, 48):
        yes = [r["completion_tokens"] for r in cell_arm(level, "yes")
               if r["delivered"] and r["finish_reason"] == "stop"]
        no = [r["completion_tokens"] for r in cell_arm(level, "no")
              if r["delivered"] and r["finish_reason"] == "stop"]
        if no:
            reportable_cells += 1
        split.append({"level": level, "mean_yes_stop": round(sum(yes) / len(yes), 1) if yes else None,
                      "mean_no_stop": round(sum(no) / len(no), 1) if no else None,
                      "ratio": round((sum(no) / len(no)) / (sum(yes) / len(yes)), 4)
                              if yes and no else None,
                      "censored_no": sum(1 for r in cell_arm(level, "no")
                                         if r["finish_reason"] == "length")})
    res["F5"] = {"per_cell": split, "reportable_cells": reportable_cells,
                 "reported": reportable_cells >= 3,
                 "statement": rows["F5"]["statement"]}

    delivered_interrupts = sum(1 for r in interrupts if r["delivered"])
    res["I1"] = {"interrupt_dispatches": len(interrupts), "delivered": delivered_interrupts,
                 "censored_candidates": sum(1 for r in ladder if r["rung"] == 0),
                 "pass": delivered_interrupts <= 1}

    lad = ladder_rows(records)
    passing = 0
    for entry in lad["items"]:
        ratios = entry["lcp_ratios"]
        if len(ratios) == len(INTERRUPT_FRACS) and all(v >= 0.90 for v in ratios):
            passing += 1
    res["I2"] = {"candidates": lad["n_candidates"], "passing": passing,
                 "items": lad["items"], "pass": passing >= 3 and lad["n_candidates"] >= 3}

    exposed = sum(1 for r in records if (r.get("census") or {}).get("reasoning_source"))
    dispatches = [r for r in records if r.get("stage") != "censored"]
    res["N1"] = {"exposed": exposed, "n": len(dispatches),
                 "censored_records": len(records) - len(dispatches),
                 "health_source": ((health or {}).get("census") or {}).get("reasoning_source"),
                 "health_fields": ((health or {}).get("census") or {}).get("fields"),
                 "fields_seen": sorted({f for r in records for f in (r.get("census") or
                                                                     {}).get("fields", [])}),
                 "pass": len(dispatches) > 0 and exposed / len(dispatches) >= 0.90}

    dups = dup_rows(records)
    res["N2"] = {"pairs": dups, "joined": sum(1 for d in dups if d.get("joined")),
                 "byte_identical": sum(1 for d in dups if d.get("byte_identical")),
                 "pass": all(d.get("joined") and d.get("byte_identical") for d in dups)
                          and len(dups) >= 2}

    cf = cross_fire_rows(records)
    res["N3"] = {**cf, "pass": cf["n_reproduced"] >= 3 and cf["n_joined"] == cf["n_cell"]}

    if res["F2"]["pass"] is False:
        tier = "capability_bound_floor_depth"
    elif res["F1"]["pass"] is False:
        tier = "wall_reaches_both_arms"
    elif res["F3"]["pass"]:
        tier = "label_split_wall"
    else:
        tier = "no_wall_inside_generator_ceiling"
    flags = []
    if res["I1"]["pass"] is False:
        flags.append("early_commitment_observed")
    if res["I2"]["pass"]:
        flags.append("one_dispatch_predicts_rungs")
    if any(r["gold"] == "no" and r["finish_reason"] == "length" for r in grid):
        flags.append("wall_is_label_split")
    return {"rows": res, "tier": tier, "flags": flags,
            "band_basis": {"F4": "round 6's fitted 80 tokens/hop (a depth-and-load law) and "
                                 "round 50's 31.3/hop at pinned load; band 15..50 is that pair "
                                 "widened, not a new claim"}}


def summarize(records: list, gate: dict, model_digest: str) -> dict:
    grid = [r for r in records if r["stage"] == "grid"]
    transport = [r for r in records if r.get("error")]
    return {
        "gate_schema": GATE_SCHEMA,
        "gate_blob_sha256": gate_blob_sha256(),
        "model_digest": model_digest,
        "dispatches": len(records),
        "transport_errors": len(transport),
        "retries": sum(r.get("attempts", 1) - 1 for r in records),
        "prompt_tokens": sum(r["prompt_tokens"] or 0 for r in records),
        "completion_tokens": sum(r["completion_tokens"] or 0 for r in records),
        "wall_s": round(sum(r["wall_s"] or 0.0 for r in records), 1),
        "answer_level_ledger": {
            "delivered": sum(1 for r in grid if r["delivered"]),
            "delivered_correct": sum(1 for r in grid if r["delivered"] and r["correct"]),
            "delivered_wrong": sum(1 for r in grid if r["delivered"] and r["correct"] is False),
            "undelivered_truncated": sum(1 for r in grid if r["outcome"] == "undelivered_truncated"),
            "undelivered_other": sum(1 for r in grid
                                     if not r["delivered"] and r["outcome"] != "undelivered_truncated"),
            "accuracy_over_delivered": wilson(
                sum(1 for r in grid if r["delivered"] and r["correct"]),
                max(1, sum(1 for r in grid if r["delivered"]))),
            "accuracy_over_n": wilson(sum(1 for r in grid if r["delivered"] and r["correct"]),
                                      len(grid)),
        },
        "grid_table": grid_rows(records),
        "ladder": ladder_rows(records),
        "duplicates": dup_rows(records),
        "cross_firing": cross_fire_rows(records),
        "gate": gate,
    }


# ---------------------------------------------------------------- selftest

def selftest() -> None:  # noqa: C901  (the certified control list)
    checks = {"n": 0, "fail": []}

    def ok(cond, note):
        checks["n"] += 1
        if not cond:
            checks["fail"].append(note)

    # 1. scorer arithmetic, with a negative control that can actually fail
    fake = [{"gold": "yes", "delivered": True, "correct": True},
            {"gold": "no", "delivered": True, "correct": True}]
    acc = sum(1 for r in fake if r["delivered"] and r["correct"]) / len(fake)
    ok(acc == 1.0, "perfect scorer must be 1.0")
    flipped = [{"gold": "yes", "delivered": True, "correct": False},
               {"gold": "no", "delivered": True, "correct": False}]
    ok(sum(1 for r in flipped if r["delivered"] and r["correct"]) / len(flipped) == 0.0,
       "flipped scorer must be 0.0")
    balanced = [{"gold": "yes", "delivered": True, "correct": True},
                {"gold": "no", "delivered": True, "correct": False}]
    ok(abs(sum(1 for r in balanced if r["correct"]) / len(balanced) - 0.5) < 1e-12,
       "constant rule must sit exactly on the balanced 0.50 baseline")
    ok(sum(1 for r in flipped if r["delivered"] and r["correct"]) != 1,
       "the wrong-answer control must be able to break F2")

    # 2. independent solver: planted yes, planted no, and a shortcut that must be refused
    lvl = 3
    chain_a = [f"a{i}" for i in range(lvl + 1)]
    chain_b = [f"b{i}" for i in range(lvl + 1)]
    facts = [[chain_a[i], ladders.REL, chain_a[i + 1]] for i in range(lvl)] + \
            [[chain_b[i], ladders.REL, chain_b[i + 1]] for i in range(lvl)]
    yes_item = {"level": lvl, "facts": facts, "query": [chain_a[0], ladders.REL, chain_a[lvl]],
                "answer": "yes", "chain_len": lvl, "rule": ladders.RULE_SENTENCE,
                "seed": 1, "seed_hash": "x"}
    check_item(yes_item)
    ok(bfs_dist(facts, chain_a[0])[chain_a[lvl]] == lvl, "planted 3-hop chain must solve at 3")
    no_item = {**yes_item, "query": [chain_b[0], ladders.REL, chain_a[lvl]],
               "answer": "no", "chain_len": None}
    check_item(no_item)
    ok(chain_a[lvl] not in bfs_dist(facts, chain_b[0]), "cross-component query must be a no")
    # planted shortcut: a direct edge collapses the path length, check_item must refuse
    short = {**yes_item, "facts": facts + [[chain_a[0], ladders.REL, chain_a[lvl]]]}
    try:
        check_item(short)
        refused = False
    except AssertionError:
        refused = True
    ok(refused, "a shortcut item must be refused (issue #67 guard)")
    noniso = {**yes_item, "facts": [f for f in facts if f[0] != chain_b[0]]}
    try:
        check_item(noniso)
        refused2 = False
    except AssertionError:
        refused2 = True
    ok(refused2, "non-isomorphic components must be refused")
    wrong_label = {**yes_item, "answer": "no", "chain_len": None}
    try:
        check_item(wrong_label)
        refused3 = False
    except AssertionError:
        refused3 = True
    ok(refused3, "a gold label that disagrees with BFS must be refused")

    # 3. corpus pairing against the vendored archived rows, with a planted digest slip
    cells = build_cells()
    cert = certify_reference(cells)
    ok(cert["ok"] and cert["certified"] == len(ROUND50_REF), "archived reference must certify")
    ok(cert["refused"] == [], "certification must not refuse on real data")
    tampered = list(ROUND50_REF)
    row = list(tampered[0])
    row[4] = "0" * 12
    tampered[0] = tuple(row)
    saved = list(ROUND50_REF)
    try:
        globals()["ROUND50_REF"] = tuple(tampered)
        tam = certify_reference(cells)
        ok(tam["ok"] is False and tam["refused"], "a planted digest slip must break pairing")
    finally:
        globals()["ROUND50_REF"] = tuple(saved)
    ok(certify_reference(cells)["ok"], "reference must certify again after the slip is removed")
    tam2 = list(saved)
    row2 = list(tam2[3])
    row2[3] = "no" if row2[3] == "yes" else "yes"
    tam2[3] = tuple(row2)
    globals()["ROUND50_REF"] = tuple(tam2)
    try:
        ok(certify_reference(cells)["ok"] is False, "a planted gold flip must break pairing")
    finally:
        globals()["ROUND50_REF"] = tuple(saved)

    # 4. the load-floor selection rule bites: 2k exactly, and a tolerance variant differs
    for level in FLOOR_LEVELS:
        cell = cells[f"F{level:03d}"]
        ok(all(len(it["facts"]) == 2 * level for it in cell), f"F{level:03d} facts must equal 2k")
        ok(all(it["level"] == level for it in cell), f"F{level:03d} levels")
        ok(sum(1 for it in cell if it["answer"] == "yes") == 2 and
           sum(1 for it in cell if it["answer"] == "no") == 2, f"F{level:03d} label balance 2/2")
    loose = pick_floor(generate_floor(16), 16, 2, 2)
    loose_items = [it for it in generate_floor(16) if 32 <= len(it["facts"]) <= 40]
    ok({it["seed"] for it in loose} != {it["seed"] for it in loose_items[:4]},
       "a band tolerance must select a different item set (the floor rule bites)")
    deep = generate_floor(GENERATOR_CEILING)
    ok(deep and all(check_item(it) is None for it in deep[:8]),
       f"level {GENERATOR_CEILING} must generate (the registered deepest cell)")
    try:
        ladders.generate_items(GENERATOR_CEILING + 1, 200, SEED_BASE)
        ceiling_hit = False
    except RuntimeError:
        ceiling_hit = True
    ok(ceiling_hit, "level 49 must raise when the whole series is generated in one call")

    # 4b. generator geometry re-measured live against the shipped generator, because the ladder
    # design depends on it and the constants in CEILING_MEASURED must not be able to go stale
    pool = len(ladders.ONSET) * len(ladders.VOWEL) * len(ladders.CODA)
    ok(pool == CEILING_MEASURED["pool_names"],
       f"entity pool measured {pool}, registered {CEILING_MEASURED['pool_names']}")
    max_names = {k: max(len({n for s, _, t in it["facts"] for n in (s, t)})
                        for it in generate_floor(k)) for k in FLOOR_LEVELS}
    ok(max_names == CEILING_MEASURED["max_entities_by_level"],
       f"max unique names per item moved: {max_names}")
    ok(max_names[GENERATOR_CEILING] <= pool,
       "the deepest registered cell must fit inside the name pool")
    floor_counts = {k: sum(1 for it in generate_floor(k) if len(it["facts"]) == 2 * k)
                    for k in FLOOR_LEVELS}
    ok(floor_counts == CEILING_MEASURED["floor_family_counts"],
       f"floor-family size moved: {floor_counts}")
    ok(all(floor_counts[k] >= floor_counts[nxt] for k, nxt in
           zip(FLOOR_LEVELS, FLOOR_LEVELS[1:])),
       "the floor family must thin with depth (facts = 2k means the minimum chain count)")
    chain_counts = {k: sorted({len(it["facts"]) // k for it in generate_floor(k)})
                    for k in FLOOR_LEVELS}
    ok(all(len(it["facts"]) % k == 0 for k in FLOOR_LEVELS for it in generate_floor(k)) and
       all(cc[0] == 2 and cc[-1] <= k + 2 for k, cc in chain_counts.items()),
       f"facts must be C*k with 2 <= C <= k+2 at every level, got {chain_counts}")
    scan = scan_with_skip(GENERATOR_CEILING + 1, 300)
    ok(scan["raised"] > 0 and scan["generated"] > 0 and scan["floor_items"] > 0,
       ("the level above the ceiling must raise on some items and still yield load-floor items "
        "on the same scan: the ceiling is an artifact of the whole-series call, not of the depth"))
    ok(scan["first_raise_index"] == CEILING_MEASURED["first_failing_item_index"],
       f"first raise index moved: {scan['first_raise_index']}")
    ok(all(s["floor_items"] > 0 for s in
           (scan, scan_with_skip(50, 300), scan_with_skip(64, 300))),
       "the load-floor family must survive past the registered ceiling (free, zero-prompt)")

    # 5. rung rule, with planted negatives
    ok(rung_for(988, 0.8) == 768 and rung_for(988, 0.5) == 448, "rung arithmetic")
    ok(rung_for(1646, 0.8) == 1280 and rung_for(1646, 0.5) == 768,
       "rung arithmetic on a deep item")
    for L, frac in ((2048, 0.8), (65, 0.5), (129, 0.5)):
        try:
            rung_for(L, frac)
            broke = False
        except AssertionError:
            broke = True
        ok(broke == (int(L * frac // 64) * 64 == 0 or int(L * frac // 64) * 64 >= L),
           f"rung rule must refuse exactly when the rung fails (L={L}, frac={frac})")

    # 6. prefix arithmetic (the I2 readout), planted both ways
    a = "yes no conclusion answer"
    ok(lcp_len("yes no conc", a) == len("yes no conc"), "LCP of a strict prefix is its length")
    ok(lcp_len("yes no X", a) == len("yes no "), "LCP stops at the first difference")
    ok(lcp_len("", a) == 0 and lcp_len(a, "") == 0, "empty string LCP is 0")
    ok(lcp_len(a, a) == len(a), "identical strings share the whole prefix")

    # 7. duplicate join keys on the item, not on the dispatch label (round 50's defect)
    base_rec = {"stage": "grid", "cell": "F040", "seed": 7, "prompt_sha256": "abc",
                "rung": MAX_TOKENS, "content": "yes", "trace": "t", "completion_tokens": 10,
                "prompt_tokens": 20, "declared": "yes", "gold": "yes"}
    dup_rec = dict(base_rec, cell="DUP-F040", stage="dup")
    pairs = dup_rows([base_rec, dup_rec])
    ok(len(pairs) == 1 and pairs[0]["joined"], "a DUP-labelled re-dispatch must join")
    ok(pairs[0]["byte_identical"] and pairs[0]["token_identical"], "identical pair must match")
    moved = dict(dup_rec, trace="different")
    pairs2 = dup_rows([base_rec, moved])
    ok(pairs2[0]["joined"] and pairs2[0]["byte_identical"] is False,
       "a planted trace change must break byte identity")
    orphan = dict(dup_rec, cell="DUP-F048", seed=99)
    pairs3 = dup_rows([base_rec, orphan])
    ok(pairs3[0]["joined"] is False, "an unjoinable duplicate must certify nothing")
    ok(all(d["joined"] for d in dup_rows([base_rec, dup_rec])) and
       not dup_rows([base_rec, orphan])[0]["joined"], "join must key on seed and digest")

    # 8. answer readout: the answer field only, no trace fallback (issue #94)
    ok(declared_answer("blah blah yes") == "yes", "content readout reads the final token")
    ok(declared_answer("Need final exactly one word: yes. Ensure no extra.") == "no",
       "the instruction-echo tail reads 'no': exactly the round 50 capture, kept as a control")
    ok(declared_answer("") is None and declared_answer(None) is None, "empty readout is None")
    msg = {"content": "", "reasoning_content": "a long chain ending no"}
    ans, source, _, trace = parse_answer_field(msg)
    ok(ans is None and source == "none" and trace.endswith("no"),
       "the reasoning token must not be admissible as a verdict")
    msg2 = {"content": "\n\nyes", "reasoning_content": "chain"}
    ans2, source2, _, _ = parse_answer_field(msg2)
    ok(ans2 == "yes" and source2 == "content", "content-first readout must win")

    # 9. sanitizer: fixtures carry only RFC 5737 documentation addresses, assembled
    frag_host = "host" + "name" + "." + "example"
    doc_net = "192" + "." + "0" + "." + "2"   # RFC 5737 TEST-NET-1 prefix
    doc_ip = doc_net + "." + "7"
    url = "http" + "://" + "example" + "." + "invalid" + "/v1"
    leak = f"upstream {frag_host} at {doc_ip} and {url} and token: abc123"
    clean = sanitize(leak, secrets=("abc123",))
    ok("192.0.2" not in clean and doc_ip not in clean, "IPv4 documentation fixture must go")
    ok("http" not in clean, "URL fixture must go")
    ok("abc123" not in clean, "credential fixture must go")
    ok("[redacted-ip]" in clean and "[redacted-url]" in clean and "[redacted-credential]" in clean,
       "sanitizer must replace, not drop silently")
    ok(sanitize("stonsh precedes brep.\nyes") == "stonsh precedes brep.\nyes",
       "task text must survive untouched")
    ok(sanitize(None) == "", "None must sanitize to empty")

    # 10. census merge rule (issue #105)
    c1 = census_of({"choices": [{"message": {"role": "user", "content": "yes",
                                             "reasoning_content": "abc"}}]})
    c2 = census_of({"choices": [{"message": {"role": "user", "content": "yes",
                                             "reasoning": "abc", "reasoning_content": ""}}]})
    c3 = census_of({"choices": [{"message": {"role": "user", "content": "yes"}}]})
    c4 = census_of({})
    ok(c1["reasoning_source"] == "reasoning_content" and c1["fields"] == ["content",
                                                                          "reasoning_content"],
       "reasoning_content wins the census merge")
    ok(c2["reasoning_source"] == "reasoning", "reasoning is the second merge arm")
    ok(c3["reasoning_source"] == "" and c4["reasoning_source"] == "", "no trace reads empty")

    # 11. gate evaluation on planted firings: the tiers must separate
    CHAIN = ("checking facts ab1 ab2 ab3 ab4. " * 200)

    def plant(level, seed, gold, delivered, correct, tokens, stage="grid", rung=MAX_TOKENS,
              finish="stop", trace_chars=None, sha=None):
        cell = (f"F{level:03d}" if stage == "grid" else
                (f"DUP-F{level:03d}" if stage == "dup" else f"I{level:03d}"))
        tlen = trace_chars if trace_chars is not None else 3000
        trace = CHAIN[:tlen]
        if not lcp_ok[0] and stage == "ladder":
            trace = CHAIN[:tlen // 3] + "X" * (tlen - tlen // 3)
        content = gold if delivered else ""
        digest = sha if sha is not None else f"{seed:016x}"
        return {"stage": stage, "cell": cell, "rung": rung, "level": level, "seed": seed,
                "seed_hash": "x", "gold": gold, "n_facts": 2 * level, "n_chains": 2,
                "delivered": delivered, "correct": correct if delivered else None,
                "declared": gold if delivered else None,
                "declared_source": "content" if delivered else "none",
                "outcome": ("delivered_correct" if correct else "delivered_wrong") if delivered
                else "undelivered_truncated",
                "finish_reason": finish, "completion_tokens": tokens, "prompt_tokens": 100,
                "prompt_sha256": digest, "content": content, "trace": trace,
                "trace_chars": tlen, "wall_s": 1.0, "attempts": 1, "error": None,
                "is_dup": stage == "dup", "pair_key": f"{seed}|{digest}|{rung}",
                "census": {"fields": ["content", "reasoning_content"],
                           "reasoning_source": "reasoning_content",
                           "reasoning_content_chars": tlen, "reasoning_field_chars": 0}}

    ARCH32 = [row for row in ROUND50_REF if row[0] == 32]
    lcp_ok = [True]

    def planted_grid(wall: bool, wrong: bool, both_arms: bool) -> list:
        recs = []
        for level in FLOOR_LEVELS:
            if level == 32:  # the cross-firing cell carries the archived seeds and states
                for _, seed, _facts, gold, sha, tokens, finish in ARCH32:
                    recs.append(plant(level, seed, gold, finish == "stop", not wrong, tokens,
                                      finish=finish, sha=sha))
                continue
            for i in (1, 2):
                trunc = both_arms and level >= 40
                recs.append(plant(level, level * 10 + i, "yes", not trunc, not wrong,
                                  MAX_TOKENS if trunc else 200 + 30 * level + (10 if i == 2 else 0),
                                  finish="length" if trunc else "stop"))
            for i in (3, 4):
                trunc = wall and level >= 24
                recs.append(plant(level, level * 10 + i, "no", not trunc, not wrong,
                                  MAX_TOKENS if trunc else min(2000, 400 + 35 * level),
                                  finish="length" if trunc else "stop"))
        return recs

    def planted_ladder(grid: list, interrupt_deliveries: int) -> list:
        out = []
        for level in INTERRUPT_LEVELS:
            cands = [r for r in grid if r["level"] == level and r["gold"] == "yes"
                     and r["finish_reason"] == "stop" and r["delivered"]]
            if not cands:
                out.append(plant(level, level * 10 + 1, "yes", False, False, 0,
                                 stage="censored", rung=0, finish=None, trace_chars=0))
                continue
            cand = min(cands, key=lambda r: r["seed"])
            for frac in INTERRUPT_FRACS:
                rung = rung_for(cand["completion_tokens"], frac)
                deliver = interrupt_deliveries > 0
                interrupt_deliveries = max(0, interrupt_deliveries - 1)
                out.append(plant(level, cand["seed"], "yes", deliver, True, rung, stage="ladder",
                                 rung=rung, finish="stop" if deliver else "length",
                                 trace_chars=rung, sha=cand["prompt_sha256"]))
        return out

    def planted_dups(grid: list, same: bool) -> list:
        out = []
        for level in DUP_LEVELS:
            cand = min((r for r in grid if r["level"] == level and r["gold"] == "yes"),
                       key=lambda r: r["seed"])
            out.append(plant(level, cand["seed"], "yes", True, True, 1200, stage="dup",
                             trace_chars=3000, sha=cand["prompt_sha256"]))
            if not same:
                out[-1]["trace"] = "a different trace for the same prompt"
        return out

    def full(wall, wrong, both_arms, interrupt_deliveries, prefix_ok, same_dup) -> list:
        lcp_ok[0] = prefix_ok
        grid = planted_grid(wall, wrong, both_arms)
        recs = grid + planted_ladder(grid, interrupt_deliveries) + planted_dups(grid, same_dup)
        lcp_ok[0] = True
        return recs

    health_ok = {"census": {"reasoning_source": "reasoning_content",
                            "fields": ["content", "reasoning_content"]}}
    g_split = evaluate_gate(full(True, False, False, 0, True, True), health_ok)
    g_nowall = evaluate_gate(full(False, False, False, 0, True, True), health_ok)
    g_both = evaluate_gate(full(True, False, True, 0, True, True), health_ok)
    g_wrong = evaluate_gate(full(True, True, False, 0, True, True), health_ok)
    g_early = evaluate_gate(full(True, False, False, 4, True, True), health_ok)
    g_nolcp = evaluate_gate(full(True, False, False, 0, False, True), health_ok)
    g_dupbroken = evaluate_gate(full(True, False, False, 0, True, False), health_ok)

    tiers = [g_split["tier"], g_nowall["tier"], g_both["tier"], g_wrong["tier"]]
    ok(len(set(tiers)) == 4, f"the gate must assign four distinct tiers, got {tiers}")
    ok(g_split["tier"] == "label_split_wall", "planted wall on the negative arm only")
    ok(g_nowall["tier"] == "no_wall_inside_generator_ceiling",
       "planted firing where nothing dies must not read as a wall")
    ok(g_both["tier"] == "wall_reaches_both_arms", "planted positive truncation must retier")
    ok(g_wrong["tier"] == "capability_bound_floor_depth",
       "a planted wrong answer must read as a capability ceiling")
    ok(g_split["rows"]["F2"]["delivered_wrong"] == 0 and g_wrong["rows"]["F2"]["delivered_wrong"] > 0,
       "the planted wrong answer must move the accuracy row")
    ok(g_split["rows"]["F3"]["delivered"] == g_wrong["rows"]["F3"]["delivered"] and
       g_split["rows"]["F1"]["delivered"] == g_wrong["rows"]["F1"]["delivered"],
       "a planted wrong answer must not move the delivery rows")
    ok(g_split["rows"]["F3"]["delivered"] <= 3 and g_nowall["rows"]["F3"]["pass"] is False,
       "the planted negatives must move only the delivery rows")
    ok(g_split["rows"]["F1"]["pass"] and g_both["rows"]["F1"]["pass"] is False,
       "the planted positive truncation must move the positive delivery row")
    ok(g_split["rows"]["F4"]["pass"] and 15.0 <= g_split["rows"]["F4"]["slope_tokens_per_hop"]
       <= 50.0, "the planted length slope must sit inside the registered band")
    ok(g_split["rows"]["F5"]["reported"] is False and
       g_split["rows"]["F5"]["per_cell"][3]["censored_no"] == 2,
       "a censored negative arm must be recorded and must refuse the cost ratio")
    ok(g_nowall["rows"]["F5"]["reported"] and all(c["ratio"] is not None and c["ratio"] > 1.0
       for c in g_nowall["rows"]["F5"]["per_cell"]),
       "uncensored negatives must read as costlier than positives")
    ok(g_split["rows"]["I1"]["pass"] and g_split["rows"]["I1"]["delivered"] == 0,
       "no interrupt delivery must pass I1")
    ok(g_early["rows"]["I1"]["pass"] is False and "early_commitment_observed" in g_early["flags"]
       and g_early["tier"] == g_split["tier"],
       "planted early commitments must break I1 and set the flag without retiering")
    ok(g_split["rows"]["I2"]["pass"] and g_split["rows"]["I2"]["passing"] == 4,
       "planted strict prefixes must pass the prefix readout")
    ok(g_nolcp["rows"]["I2"]["pass"] is False, "the prefix readout must be able to fail")
    ok(g_dupbroken["rows"]["N2"]["pass"] is False and g_split["rows"]["N2"]["pass"],
       "a planted duplicate break must break N2 and only N2")
    ok(g_split["rows"]["N3"]["n_joined"] == 4 and g_split["rows"]["N3"]["n_reproduced"] == 4,
       "the planted archived k = 32 states must reproduce in the replicate row")
    ok(g_split["rows"]["N1"]["pass"] and g_split["rows"]["N1"]["censored_records"] == 0,
       "planted clean firings must pass the census control")
    ok(g_both["rows"]["N1"]["censored_records"] == 2,
       "censored ladder candidates must be counted apart from dispatches")

    # 12. gate immutability and the reference blob
    ok(gate_blob_sha256() == gate_blob_sha256(), "gate canonicalization must be stable")
    ok(len(gate_blob_sha256()) == 64, "gate blob is a full sha256")
    spec = gate_spec()
    ok(spec["schema"] == GATE_SCHEMA and len(spec["rows"]) == 10, "gate row count")
    ok(all(row["band"] for row in spec["rows"]), "every registered row carries a band")
    ok(spec["cells"]["stage1_calls"] + 2 * len(INTERRUPT_LEVELS) + len(DUP_LEVELS) + 1
       <= CALL_CAP, "the dispatch plan must fit the call cap")
    order = [job[1]["level"] for job in stage1_jobs(cells)]
    ok(order == [k for k in reversed(FLOOR_LEVELS) for _ in range(4)] and order[:4] == [48] * 4,
       "stage 1 must dispatch the deepest cell first (cutoff robustness)")
    ladder_order = [cand["level"] for cand in cells["_CAND"]]
    ok(ladder_order == list(INTERRUPT_LEVELS), "cells are registered ascending")
    ok(spec["cells"]["dispatch_order"], "the dispatch order must be registered in the gate")
    ok(len(spec["generator_ceiling"]["past_ceiling_scans"]) == 3 and
       all(s["floor_items"] > 0 for s in spec["generator_ceiling"]["past_ceiling_scans"].values()),
       "the registered ceiling block must carry the past-ceiling floor scans")
    ok(len(spec["load_floor"]["facts"]) == len(FLOOR_LEVELS) and
       spec["load_floor"]["facts"] == [2 * k for k in FLOOR_LEVELS],
       "the load floor must be facts = 2k at every level")
    ok(len(ROUND50_REF) == 12 and len({row[1] for row in ROUND50_REF}) == 12,
       "the vendored reference has 12 distinct items")
    ok({row[1] for row in ROUND50_REF if row[0] == 32} == {it["seed"] for it in cells["F032"]},
       "the k = 32 floor cell must be the archived M32 item set")
    ok({row[1] for row in ROUND50_REF if row[0] == 16}.issubset(
        {it["seed"] for it in generate_floor(16)}), "archived k = 16 seeds must regenerate")

    # 13. transport failure must be scoreable without an endpoint value in the record
    err_job = ("F032", None, MAX_TOKENS, "grid", False, 0, ("",))
    tiny_item = cells["F032"][0]
    rec_err = score_record(err_job, tiny_item, None, "transport:URLError", MAX_TOKENS,
                           gate_blob_sha256())
    ok(rec_err["outcome"] == "transport_error" and rec_err["delivered"] is False,
       "a transport error must not read as a wrong answer")
    ok(score_record(("I048", None, 0, "censored", False, 0, ()), tiny_item, None,
                    "censored_by_cap", 0, gate_blob_sha256())["outcome"] == "censored_by_cap",
       "a candidate censored by the cap must not read as a transport failure")
    ok(rec_err["error"] == "transport:URLError" and "127" not in json.dumps(rec_err),
       "the error string must carry no endpoint address")
    malformed = score_record(err_job, tiny_item, {"payload": {"choices": []}, "wall": 1.0},
                             None, MAX_TOKENS, gate_blob_sha256())
    ok(malformed["outcome"] == "malformed_response" and malformed["error"] == "malformed_response",
       "a malformed response must be recorded, not guessed")

    print(f"selftest: {checks['n']} checks, {len(checks['fail'])} failures")
    for note in checks["fail"]:
        print(f"  FAIL {note}")
    if checks["fail"]:
        raise SystemExit(1)


# ---------------------------------------------------------------- main

def read_raw(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def model_digest_of(model: str) -> str:
    return hashlib.sha256(model.encode()).hexdigest()[:16]


def main(argv: list) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--gate", action="store_true", help="write gate.json and print the blob")
    p.add_argument("--dry-run", action="store_true", help="print the frozen dispatch plan")
    p.add_argument("--run", action="store_true")
    p.add_argument("--resume", action="store_true",
                   help="continue an existing raw.jsonl, refusing on gate-hash drift")
    p.add_argument("--prioritized", action="store_true",
                   help="wall-clock cutoff mode: finish the deep cells (k >= 24), then stage 2, "
                        "then the shallow law-anchor cells")
    p.add_argument("--rescore", action="store_true",
                   help="rebuild gate.json/summary.json from raw.jsonl with no endpoint call")
    p.add_argument("--raw", default="raw.jsonl")
    p.add_argument("--summary", default="summary.json")
    p.add_argument("--health", default="health.json")
    a = p.parse_args(argv)

    if a.selftest:
        selftest()
        print(f"gate blob: {gate_blob_sha256()}")
        return 0

    cells = build_cells()
    cert = certify_reference(cells)
    if not cert["ok"]:
        print(f"REFUSED: archived reference does not certify: {cert['refused']}", file=sys.stderr)
        return 2
    blob = gate_blob_sha256()
    if blob != ROUND51_GATE_BLOB_SHA256:
        print(f"REFUSED: gate blob {blob} does not match the pin "
              f"{ROUND51_GATE_BLOB_SHA256}", file=sys.stderr)
        return 2

    here = Path(__file__).resolve().parent
    raw_path = here / a.raw
    summary_path = here / a.summary
    health_path = here / a.health

    if a.gate:
        (here / "gate.json").write_text(json.dumps(gate_spec(), indent=2, sort_keys=True) + "\n",
                                        encoding="utf-8")
        print(f"gate.json written, blob {blob}")
        return 0

    if a.rescore:
        records = read_raw(raw_path)
        if not records:
            print("REFUSED: raw.jsonl is empty", file=sys.stderr)
            return 2
        stray = [r for r in records if r.get("gate") != blob]
        if stray:
            print(f"REFUSED: {len(stray)} records carry a different gate hash", file=sys.stderr)
            return 2
        health = json.loads(health_path.read_text(encoding="utf-8")) if health_path.exists() else {}
        digest = records[0].get("model_digest", "")
        gate = evaluate_gate(records, health)
        summary = summarize(records, gate, digest)
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                                encoding="utf-8")
        (here / "gate.json").write_text(json.dumps(gate_spec(), indent=2, sort_keys=True) + "\n",
                                        encoding="utf-8")
        print(f"rescored {len(records)} records from raw.jsonl, tier {gate['tier']}")
        return 0

    if a.dry_run:
        jobs = stage1_jobs(cells)
        print(f"stage 1: {len(jobs)} dispatches at {MAX_TOKENS}")
        for cell, item, rung, stage, _ in jobs:
            print(f"  {cell} seed={item['seed']} gold={item['answer']} "
                  f"facts={len(item['facts'])} rung={rung} chars={len(render_prompt(item))}")
        print("stage 2 candidates: " + ", ".join(
            f"L{c['level']} seed={c['seed']}" for c in cells["_CAND"]))
        print("stage 2 duplicates: " + ", ".join(
            f"L{c['level']} seed={c['seed']}" for c in cells["_DUP"]))
        print(f"certified reference rows: {cert['certified']}/{len(ROUND50_REF)}")
        print(f"dispatch cap used at most: 1 + {len(jobs)} + "
              f"{2 * len(INTERRUPT_LEVELS) + len(DUP_LEVELS)} = "
              f"{1 + len(jobs) + 2 * len(INTERRUPT_LEVELS) + len(DUP_LEVELS)} of {CALL_CAP}")
        return 0

    return run_dispatch(a, cells, blob, raw_path, summary_path, health_path)


def run_dispatch(a, cells, blob, raw_path, summary_path, health_path) -> int:  # noqa: C901
    import os
    base = os.environ.get("NIGHTLY_BASE_URL")
    model = os.environ.get("NIGHTLY_MODEL_ID")
    key = os.environ.get("NIGHTLY_API_KEY") or ""
    if not (base and model):
        print("REFUSED: NIGHTLY_BASE_URL and NIGHTLY_MODEL_ID are required "
              "(NIGHTLY_API_KEY may be empty when the slot serves without a credential)",
              file=sys.stderr)
        return 2
    secrets = (base, model, key, base.split("//")[-1] if "//" in base else "")
    digest = model_digest_of(model)

    records = read_raw(raw_path)
    if a.run and records:
        print("REFUSED: raw.jsonl already exists; use --resume", file=sys.stderr)
        return 2
    if a.resume:
        stray = [r for r in records if r.get("gate") != blob]
        if stray:
            print(f"REFUSED: {len(stray)} existing records carry a different gate hash",
                  file=sys.stderr)
            return 2
    done = {(join_key(r), r["stage"]) for r in records}
    sink = raw_path.open("a", encoding="utf-8")

    def emit(rec: dict) -> None:
        sink.write(json.dumps(rec, sort_keys=True) + "\n")
        sink.flush()
        import os as _os
        _os.fsync(sink.fileno())
        records.append(rec)

    t_start = time.time()
    calls = len(records)

    health = json.loads(health_path.read_text(encoding="utf-8")) if (
        health_path.exists() and a.resume) else None
    if health is None:
        health = health_probe(base, model, key)
        calls += 1
        health_path.write_text(json.dumps({"model_digest": digest, **health}, indent=2,
                                         sort_keys=True) + "\n", encoding="utf-8")
        print(f"health ok={health.get('ok')} wall={health.get('wall_s')} "
              f"tokens={health.get('completion_tokens')} census={health.get('census')}",
              flush=True)
        if not health.get("ok"):
            print("ABORT: health probe failed, no grid dispatched", file=sys.stderr)
            sink.close()
            return 3

    def dispatch(job):
        nonlocal calls
        if calls >= CALL_CAP:
            raise RuntimeError("call cap reached")
        if time.time() - t_start > DISPATCH_BUDGET_S:
            raise RuntimeError("dispatch budget exhausted")
        cell, item, rung, stage, is_dup, idx = job[:6]
        pair = (join_key({"seed": item["seed"], "prompt_sha256": prompt_digest(item),
                          "rung": rung}), stage)
        if pair in done:
            return None
        prompt = render_prompt(item)
        attempts = 0
        resp = err = None
        while attempts < 2:
            attempts += 1
            try:
                res = call_endpoint(prompt, base, model, key, rung)
                resp = {"payload": res["payload"], "wall": res["wall_s"]}
                break
            except RuntimeError as exc:
                err = str(exc)
                print(f"  retry {cell} seed={item['seed']} rung={rung}: {err}", flush=True)
        job_full = (cell, item, rung, stage, is_dup, idx, secrets)
        rec = score_record(job_full, item, resp, err, rung, blob)
        rec["attempts"] = attempts
        rec["model_digest"] = digest
        calls += 1
        done.add(pair)
        emit(rec)
        print(f"  {cell} seed={item['seed']} rung={rung} out={rec['outcome']} "
              f"tokens={rec['completion_tokens']} fr={rec['finish_reason']} "
              f"wall={rec['wall_s']}", flush=True)
        return rec

    stage1_all = stage1_jobs(cells)
    if a.prioritized:
        stage1_head = [j for j in stage1_all if j[1]["level"] >= PRIORITY_MIN_LEVEL]
        stage1_tail = [j for j in stage1_all if j[1]["level"] < PRIORITY_MIN_LEVEL]
    else:
        stage1_head, stage1_tail = stage1_all, []

    def run_jobs(jobs, label):
        nonlocal idx, stopped
        for job in jobs:
            try:
                dispatch(job[:5] + (idx,))
            except RuntimeError as exc:
                stopped = f"{label}: {exc}"
                print(f"  STOP {stopped}", file=sys.stderr, flush=True)
                return False
            idx += 1
        return True

    print(f"stage 1: floor grid, levels {[j[1]['level'] for j in stage1_head]}, "
          f"{MAX_TOKENS} tokens each"
          + (f" (prioritized: k >= {PRIORITY_MIN_LEVEL} first, stage 2 next, "
             f"then k < {PRIORITY_MIN_LEVEL})" if stage1_tail else ""), flush=True)
    idx = 0
    stopped = None
    alive = run_jobs(stage1_head, "stage 1")

    stage1_index = {(r["cell"], r["seed"], r["rung"]): r for r in records if r["stage"] == "grid"}
    plan = stage2_plan(cells, stage1_index)
    print(f"stage 2: {sum(1 for j in plan if j[3] == 'ladder')} ladder dispatches, "
          f"{sum(1 for j in plan if j[3] == 'dup')} duplicate controls, "
          f"{sum(1 for j in plan if j[3] == 'censored')} censored candidates", flush=True)
    for cell, item, rung, stage, is_dup in list(plan):
        if stage == "censored":
            rec = score_record((cell, item, 0, "censored", is_dup, idx, secrets), item, None,
                               "censored_by_cap", 0, blob)
            rec["model_digest"] = digest
            emit(rec)
            print(f"  {cell} seed={item['seed']} ladder censored by the cap", flush=True)
            idx += 1
            continue
        try:
            dispatch((cell, item, rung, stage, is_dup, idx))
        except RuntimeError as exc:
            stopped = f"stage 2: {exc}"
            print(f"  STOP {stopped}", file=sys.stderr, flush=True)
            break
        idx += 1
    if stage1_tail and not stopped:
        print(f"stage 1 tail: k < {PRIORITY_MIN_LEVEL} ({len(stage1_tail)} dispatches)", flush=True)
        run_jobs(stage1_tail, "stage 1 tail")
    if stopped:
        (here / "cutoff.json").write_text(json.dumps({"reason": stopped,
                                                      "records_at_cutoff": len(records),
                                                      "dispatch_budget_s": DISPATCH_BUDGET_S},
                                                     indent=2, sort_keys=True) + "\n",
                                          encoding="utf-8")

    sink.close()
    gate = evaluate_gate(records, health)
    summary = summarize(records, gate, digest)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"tier: {gate['tier']} flags: {gate['flags']}")
    for rid in ("F1", "F2", "F3", "F4", "I1", "I2", "N1", "N2", "N3"):
        row = gate["rows"][rid]
        keep = {k: v for k, v in row.items() if k in ("pass", "delivered", "n", "delivered_wrong",
                                                      "slope_tokens_per_hop", "passing",
                                                      "candidates", "byte_identical", "exposed",
                                                      "n_reproduced", "n_joined", "censored_candidates")}
        print(f"  {rid}: {keep}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

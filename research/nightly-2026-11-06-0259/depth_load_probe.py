#!/usr/bin/env python3
"""Depth-at-matched-load probe for the k-hop ladder family (nightly round 50).

Question: when accuracy on the ladder family fails at high hop depth, did the
computation fail or did the DELIVERY fail? On this family the verdict token sits at
the end of an O(k) reasoning trace (round 6, research/nightly-2026-10-16-0400:
completion_tokens = -36 + 80k), so under the protocol's 2048-token cap a deep item can
lose its answer field without losing its traversal. Issue #71 asks for d* with "load
decoupling (budget-controlled)" and docs/next-investigations.md records that deciding
the depth ceiling "needs a budget-controlled or answer-token-first protocol, not a raw
truncation count". On a deployment whose reasoning channel precedes the answer field, an
answer-first instruction cannot decouple the two, so this instrument decouples them by
measurement instead: it reads the verdict back out of the trace and compares the trace
verdict with the delivered verdict.

Three things are separated by construction, not by post-hoc reading:

1. DEPTH vs INPUT LOAD. The shipped generator draws the number of chains uniformly from
   [2, k+2], so facts = chains * k and depth drags load with it. This probe selects items
   in a fixed fact-count band, so the matched-load series (k = 8, 16, 24, 32 at 64-72
   facts) holds the prompt size constant while the queried path grows 4x and the number of
   distractor chains falls 8 -> 2 (the conservative direction: any turnover at high k
   happens while the search breadth is shrinking). A load arm at fixed depth (k = 32 at
   192 facts) and a load arm at shallow depth (k = 16 at 192 facts) complete the grid.
2. COMPUTATION vs SURFACING. Each record carries the answer-field verdict and the
   trace-recovered verdict (last standalone yes/no of the trace text). The recovery rule
   is calibrated on the same firing against the items that DID deliver (control N3); if
   the calibration fails, every trace-derived row is refused rather than reported.
3. FIRING STATE. The #105 field census is recorded per record (message field names plus
   the reasoning-supplying field, merge rule reasoning_content if non-empty, else
   reasoning, else empty), and the 3 duplicate dispatches give the #100 self-agreement
   readout.

Cells (all items from generators/ladders.py under the shipped seed policy, seed_base
20261005; selection rule fixed before any call and never sees a model output):

  A08  k = 8,  round 6's selection rule verbatim (first two yes + first two no, no band):
       the archived anchor, same seeds as research/nightly-2026-10-16-0400 level 8.
  M08/M16/M24/M32  k = 8/16/24/32, first two yes + first two no with 64 <= facts <= 72.
  H16  k = 16, first two yes + first two no with 180 <= facts <= 200.
  H32  k = 32, first two yes + first two no with 180 <= facts <= 200.
  DUP  3 re-dispatches of the smallest-seed gold-yes matched item at k = 16, 24, 32.
  CENSUS  1 health call, fixed two-fact prompt, not experimental data.

Environment contract (never hardcoded, public-only rule):
  NIGHTLY_BASE_URL  OpenAI-compatible base URL ending in /v1
  NIGHTLY_MODEL_ID  served model id: only a one-way digest is written to an artifact
  NIGHTLY_API_KEY   bearer token (never written to any file)

Usage:
  depth_load_probe.py --selftest
  depth_load_probe.py --gate            (writes gate.json; digest must equal the pin)
  depth_load_probe.py --dry-run
  depth_load_probe.py --run --raw raw.jsonl --summary summary.json --health health.json
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import statistics
import sys
import threading
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
WORKERS = 3
MATCH_BAND = (64, 72)      # facts, matched-load band (64-11% to 72+12% is a +/- band)
HIGH_BAND = (180, 200)     # facts, the 3x load arm
ANCHOR_LEVEL = 8
MATCHED_LEVELS = (8, 16, 24, 32)
HIGH_LEVELS = (16, 32)
DUP_LEVELS = (16, 24, 32)
GATE_SCHEMA = "round50-gate-v1"
# The frozen gate blob (gate.json, canonical JSON of gate_spec()). Fail-closed: --run
# recomputes it and refuses to dispatch if it moved. Pinned in the instrument so a later
# edit cannot move the gate unseen (issue #120 discipline).
ROUND50_GATE_BLOB_SHA256 = "a805acd978d3f14350246cff86f988fdc93978709b28957613ff8b82e3e470c4"
# Archived anchor firing, pinned fail-closed by whole-file blob digest (round 6).
ROUND6_RAW = REPO / "research" / "nightly-2026-10-16-0400" / "raw.jsonl"
ROUND6_RAW_BLOB_SHA256 = "21987bdfb456c8a44449221defc006623870efb574cd7fe31919a073616e544e"
ROUND6_ANCHOR_SEEDS = (36261005, 36261006, 36261013, 36261017)
ROUND6_ANCHOR_ANSWERS = {36261005: "no", 36261006: "no", 36261013: "yes", 36261017: "yes"}
ROUND6_ANCHOR_TOKENS = {36261005: 340, 36261006: 570, 36261013: 447, 36261017: 191}

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
    """Weak components of the fact graph (the #67 isomorphism guard)."""
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


def _pick(series: list, band: tuple | None, want_yes: int, want_no: int) -> list:
    """Selection rule: generation order, first two yes and first two no in the band."""
    got_yes = got_no = 0
    picked: list = []
    for item in series:
        check_item(item)
        n = len(item["facts"])
        if band is not None and not (band[0] <= n <= band[1]):
            continue
        if item["answer"] == "yes" and got_yes < want_yes:
            picked.append(item)
            got_yes += 1
        elif item["answer"] == "no" and got_no < want_no:
            picked.append(item)
            got_no += 1
        if got_yes == want_yes and got_no == want_no:
            break
    assert got_yes == want_yes and got_no == want_no, (band, got_yes, got_no)
    return picked


def build_cells() -> dict:
    """Every cell, built and certified before any prompt is spent."""
    cells: dict = {}
    for lvl in MATCHED_LEVELS:
        series = ladders.generate_items(lvl, SCAN, SEED_BASE)
        shipped = REPO / "items" / "ladders" / f"l{lvl}.jsonl"
        if shipped.exists():
            disk = [json.loads(line) for line in
                    shipped.read_text(encoding="utf-8").splitlines()]
            # The shipped file is 300 items deep; the scan runs past it, so the
            # identity assertion covers the shipped prefix only.
            assert disk == series[:len(disk)], (
                f"l{lvl}: regenerated series is not byte-identical to the shipped file")
        cells[f"M{lvl:02d}"] = _pick(series, MATCH_BAND, 2, 2)
    for lvl in HIGH_LEVELS:
        series = ladders.generate_items(lvl, SCAN, SEED_BASE)
        cells[f"H{lvl:02d}"] = _pick(series, HIGH_BAND, 2, 2)
    series8 = ladders.generate_items(ANCHOR_LEVEL, SCAN, SEED_BASE)
    cells["A08"] = _pick(series8, None, 2, 2)
    assert [it["seed"] for it in cells["A08"]] == list(ROUND6_ANCHOR_SEEDS), (
        "the anchor cell is not round 6's item set")
    for item in cells["A08"]:
        assert item["answer"] == ROUND6_ANCHOR_ANSWERS[item["seed"]], item
    # DUP: deterministic control re-dispatches, decided from items only.
    dups = []
    for lvl in DUP_LEVELS:
        yes_items = [it for it in cells[f"M{lvl:02d}"] if it["answer"] == "yes"]
        dups.append(min(yes_items, key=lambda it: it["seed"]))
    cells["DUP"] = dups
    return cells


def work_items(cells: dict) -> list:
    """Dispatch list: every cell item in fixed order, duplicates last."""
    order = ["A08"] + [f"M{l:02d}" for l in MATCHED_LEVELS] + \
            [f"H{l:02d}" for l in HIGH_LEVELS]
    out = []
    for cell in order:
        for item in cells[cell]:
            out.append((cell, item, False))
    for item in cells["DUP"]:
        out.append((f"DUP-M{item['level']:02d}", item, True))
    return out


# ---------------------------------------------------------------- prompt side

def render_prompt(item: dict) -> str:
    """The round-6 template, byte-identical (research/nightly-2026-10-16-0400)."""
    facts = "\n".join(f"{s} {r} {t}." for s, r, t in item["facts"])
    qs, qrel, qt = item["query"]
    return (f"{item['rule']}\nFacts:\n{facts}\n\n"
            f"Question: does {qs} {qrel} {qt}?\n"
            "Answer with exactly one word: yes or no.")


def first_answer(text: str) -> str | None:
    m = YES_NO.search(text or "")
    return m.group(1).lower() if m else None


def last_answer(text: str) -> str | None:
    hits = YES_NO.findall(text or "")
    return hits[-1].lower() if hits else None


def first_answer_offset(text: str) -> int | None:
    m = YES_NO.search(text or "")
    return m.start() if m else None


def trace_verdict_cue(text: str) -> str | None:
    """Secondary trace rule: the last yes/no that sits in a conclusion-cue sentence."""
    out = None
    for sent in re.split(r"(?<=[.!?])\s+|\n+", text or ""):
        if re.match(r"(?i)^\s*(final|thus|so|therefore|answer|conclusion|answer:)", sent):
            v = last_answer(sent)
            if v:
                out = v
    return out


def sanitize(text: str, secret_substrings: tuple = ()) -> str:
    """Public-only rule: no host, IP, endpoint URL or credential reaches an artifact."""
    out = text or ""
    for sub in secret_substrings:
        if sub:
            out = out.replace(sub, "[REDACTED-HOST]")
    out = IPV4.sub("[REDACTED-IP]", out)
    out = IPV6.sub("[REDACTED-IP]", out)
    out = URLISH.sub("[REDACTED-URL]", out)
    out = SENSITIVE.sub("[REDACTED-CRED]", out)
    return out


# ---------------------------------------------------------------- call side

def call(prompt: str, base: str, model: str, key: str, max_tokens: int = MAX_TOKENS) -> dict:
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions", data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        data = json.load(resp)
    wall = round(time.time() - t0, 2)
    choice = data["choices"][0]
    msg = choice.get("message") or {}
    usage = data.get("usage") or {}
    fields = sorted(k for k in msg.keys())
    rc = msg.get("reasoning_content") or ""
    rn = msg.get("reasoning") or ""
    source = "reasoning_content" if rc else ("reasoning" if rn else "")
    return {
        "content": msg.get("content") or "",
        "trace": rc if rc else rn,
        "msg_fields": fields,
        "trace_source": source,
        "trace_content_chars": len(rc),
        "trace_reasoning_chars": len(rn),
        "finish_reason": choice.get("finish_reason"),
        "completion_tokens": usage.get("completion_tokens"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "wall_s": wall,
    }


def census_of(resp: dict) -> dict:
    """The #105 per-record field census."""
    return {
        "fields": resp.get("msg_fields") or [],
        "reasoning_source": resp.get("trace_source") or "",
        "reasoning_content_chars": resp.get("trace_content_chars", 0),
        "reasoning_field_chars": resp.get("trace_reasoning_chars", 0),
        "trace_chars": len(resp.get("trace") or ""),
    }


def score_record(cell: str, item: dict | None, is_dup: bool, resp: dict, err: str | None,
                 secrets: tuple) -> dict:
    """Deterministic scoring of one dispatch; no text-dependent row is decided here."""
    content = resp.get("content") or ""
    trace = resp.get("trace") or ""
    gold = item["answer"] if item else None
    delivered = first_answer(content)
    trace_last = last_answer(trace)
    trace_first = first_answer(trace)
    cue = trace_verdict_cue(trace)
    truncated = resp.get("finish_reason") == "length"
    if err:
        outcome = "transport_error"
    elif delivered is None and truncated:
        outcome = "undelivered_truncated"
    elif delivered is None and not trace:
        outcome = "undelivered_no_text"
    elif delivered is None:
        outcome = "undelivered_open_trace"
    elif delivered == gold:
        outcome = "delivered_correct"
    else:
        outcome = "delivered_wrong"
    # Char-proportional estimate of the completion-token index at which the verdict sits.
    pos = None
    if delivered is not None:
        before = len(trace) + (first_answer_offset(content) or 0)
        total = len(trace) + len(content)
        toks = resp.get("completion_tokens")
        if total and toks:
            pos = round(toks * before / total)
    return {
        "cell": cell,
        "level": item["level"] if item else None,
        "is_dup": is_dup,
        # Identity join for the #100 control. A duplicate is dispatched under its own
        # DUP- cell label, so the key must be built from the ITEM (seed plus the prompt
        # digest), never from the cell label, or the pair never joins (round-49 lesson:
        # verify which field a join reads).
        "pair_key": (f"{item['seed']}|{hashlib.sha256(render_prompt(item).encode()).hexdigest()[:16]}"
                     if item else None),
        "join_key": (f"{item['seed']}|{hashlib.sha256(render_prompt(item).encode()).hexdigest()[:16]}"
                     if item else None),
        "seed": item["seed"] if item else None,
        "seed_hash": item["seed_hash"] if item else None,
        "n_facts": len(item["facts"]) if item else None,
        "n_chains": len(components(item["facts"])) if item else None,
        "gold": gold,
        "prompt_sha256": hashlib.sha256(
            (render_prompt(item) if item else CENSUS_PROMPT).encode()).hexdigest()[:16],
        "prompt": sanitize(render_prompt(item) if item else CENSUS_PROMPT, secrets),
        "response": sanitize(content, secrets),
        "trace": sanitize(trace, secrets),
        "finish_reason": resp.get("finish_reason"),
        "completion_tokens": resp.get("completion_tokens"),
        "prompt_tokens": resp.get("prompt_tokens"),
        "wall_s": resp.get("wall_s"),
        "error": err,
        "census": census_of(resp),
        "content_answer": delivered,
        "content_answer_last": last_answer(content),
        "trace_answer": trace_last,
        "trace_answer_first": trace_first,
        "trace_answer_cue": cue,
        "delivered": delivered is not None,
        "correct": delivered is not None and delivered == gold,
        "trace_correct": trace_last is not None and trace_last == gold,
        "trace_agrees_delivered": (delivered is not None and trace_last is not None
                                   and delivered == trace_last),
        "verdict_token_pos_est": pos,
        "truncated": truncated,
        "outcome": outcome,
    }


# ---------------------------------------------------------------- aggregation

CELLS_ORDER = ["A08", "M08", "M16", "M24", "M32", "H16", "H32"]


def join_key(rec: dict) -> str | None:
    """The #100 identity join: item seed plus prompt digest. Deliberately independent of
    the cell label, so a duplicate dispatched under a DUP- label joins its original."""
    if rec.get("join_key"):
        return rec["join_key"]
    if rec.get("seed") is None or not rec.get("prompt_sha256"):
        return None
    return f"{rec['seed']}|{rec['prompt_sha256']}"


def _acc(rows: list) -> float:
    return round(sum(1 for r in rows if r["correct"]) / len(rows), 4) if rows else None


def cell_table(rows: list) -> list:
    out = []
    for cell in CELLS_ORDER + [f"DUP-M{l:02d}" for l in DUP_LEVELS]:
        sub = [r for r in rows if r["cell"] == cell]
        if not sub:
            continue
        gold_yes = sum(1 for r in sub if r["gold"] == "yes")
        n = len(sub)
        pos = [r["verdict_token_pos_est"] for r in sub
               if r["verdict_token_pos_est"] is not None]
        out.append({
            "cell": cell,
            "level": sub[0]["level"],
            "n_facts": sub[0]["n_facts"],
            "n_chains": sub[0]["n_chains"],
            "n": n,
            "gold_yes": gold_yes,
            "constant_yes_baseline": round(gold_yes / n, 4),
            "constant_no_baseline": round((n - gold_yes) / n, 4),
            "delivered": sum(1 for r in sub if r["delivered"]),
            "truncated": sum(1 for r in sub if r["truncated"]),
            "correct": sum(1 for r in sub if r["correct"]),
            "accuracy": _acc(sub),
            "trace_recovered": sum(1 for r in sub if r["trace_answer"]),
            "trace_correct": sum(1 for r in sub if r["trace_correct"]),
            "trace_agrees_delivered": sum(1 for r in sub if r["trace_agrees_delivered"]),
            "completion_tokens_mean": (round(statistics.mean(
                [r["completion_tokens"] for r in sub if r["completion_tokens"]]), 1)
                if any(r["completion_tokens"] for r in sub) else None),
            "verdict_pos_est_mean": round(statistics.mean(pos), 1) if pos else None,
        })
    return out


def ols_slope(points: list) -> float | None:
    """Ordinary least squares slope over (x, y) points; None if under-determined."""
    pts = [(x, y) for x, y in points if y is not None]
    if len(pts) < 2 or len({x for x, _ in pts}) < 2:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    mx = statistics.mean(xs)
    my = statistics.mean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return None
    return round(sum((x - mx) * (y - my) for x, y in pts) / den, 4)


def _by(rows: list, cell: str) -> list:
    return [r for r in rows if r["cell"] == cell]


def evaluate_gate(rows: list, census_health: dict) -> dict:
    """The registered gate, evaluated over dispatched records only."""
    exp = [r for r in rows if not r["is_dup"]]
    matched = [r for r in exp if r["cell"].startswith("M")]
    trace_open = bool(census_health.get("reasoning_source")) and \
        sum(1 for r in exp if r["census"]["trace_chars"] > 0) >= 0.9 * len(exp)
    # N3: calibration of the trace-recovery rule against items that delivered.
    cal = [r for r in exp if r["delivered"] and r["census"]["trace_chars"] > 0]
    calib_rate = round(sum(1 for r in cal if r["trace_agrees_delivered"]) / len(cal), 4) \
        if cal else None
    calibrated = calib_rate is not None and calib_rate >= 0.75 and trace_open
    # The decisive row: among undelivered records that have trace text, how often is the
    # traversal in the trace already the gold answer?
    und = [r for r in exp if not r["delivered"] and r["census"]["trace_chars"] > 0]
    surf_rate = round(sum(1 for r in und if r["trace_correct"]) / len(und), 4) if und else None
    # Self-agreement over the duplicate pairs (#100).
    pairs = {}
    for r in rows:
        key = join_key(r)
        if key:
            pairs.setdefault(key, []).append(r)
    dup_pairs = [v for v in pairs.values() if len(v) > 1]
    byte_ident = sum(1 for v in dup_pairs
                     if (v[0]["response"] == v[1]["response"]
                         and v[0]["trace"] == v[1]["trace"]))
    tok_ident = sum(1 for v in dup_pairs
                    if v[0]["completion_tokens"] == v[1]["completion_tokens"])
    # Depth-at-matched-load slope of the verdict surface position.
    pts = []
    for lvl in MATCHED_LEVELS:
        sub = [r for r in exp if r["cell"] == f"M{lvl:02d}"
               and r["verdict_token_pos_est"] is not None]
        if len(sub) >= 2:
            pts.append((lvl, statistics.mean(r["verdict_token_pos_est"] for r in sub)))
    slope = ols_slope(pts)
    m08, m16, m24, m32 = (_acc(_by(exp, f"M{l:02d}")) for l in MATCHED_LEVELS)
    a08 = _acc(_by(exp, "A08"))
    h16, h32 = (_acc(_by(exp, f"H{l:02d}")) for l in HIGH_LEVELS)
    checks = {
        "D1_anchor_round6_items_ge": {"value": a08, "threshold": 0.75,
                                      "result": a08 is not None and a08 >= 0.75},
        "D2_shallow_matched_accuracy_ge": {
            "value": _acc([r for r in exp if r["cell"] in ("M08", "M16")]),
            "threshold": 0.875,
            "result": _acc([r for r in exp if r["cell"] in ("M08", "M16")]) is not None
            and _acc([r for r in exp if r["cell"] in ("M08", "M16")]) >= 0.875},
        "D3_load_at_depth16_ge": {"value": h16, "threshold": 0.75,
                                  "result": h16 is not None and h16 >= 0.75},
        "D4_no_ceiling_at_matched_k32_ge": {"value": m32, "threshold": 0.75,
                                            "result": m32 is not None and m32 >= 0.75},
        "D5_load_does_not_help_at_depth": {
            "value": (None if m32 is None or h32 is None else round(m32 - h32, 4)),
            "threshold": 0.0,
            "result": m32 is not None and h32 is not None and m32 >= h32},
        "D6_matched_above_baseline_ge": {
            "value": _acc(matched), "threshold": 0.625,
            "result": _acc(matched) is not None and _acc(matched) >= 0.625},
        "N1_census_channel_open": {"value": census_health.get("reasoning_source"),
                                   "trace_open": trace_open, "result": trace_open},
        "N2_duplicate_pairs_byte_identical_ge": {
            "value": byte_ident, "n_pairs": len(dup_pairs), "threshold": 2,
            "answer_identical": sum(1 for v in dup_pairs
                                    if v[0]["response"] == v[1]["response"]),
            "token_identical": tok_ident, "result": byte_ident >= 2},
        "N3_trace_recovery_calibration_ge": {
            "value": calib_rate, "n_calibrated": len(cal), "threshold": 0.75,
            "result": calibrated},
        "T1_undelivered_trace_correct": {
            "value": surf_rate, "n_undelivered_with_trace": len(und),
            "admissible": calibrated and bool(und),
            "result": ("surfacing_bound" if calibrated and surf_rate is not None
                       and surf_rate >= 2 / 3 else
                       "capability_bound" if calibrated and surf_rate is not None else
                       "refused" if not calibrated else "no_undelivered")},
        "R_depth_turnover_at_matched_load": {
            "value": (None if m08 is None or m32 is None else round(m08 - m32, 4)),
            "turnover": (m08 is not None and m32 is not None and m08 - m32 >= 0.25)},
        "R_verdict_position_slope": {
            "value": slope, "band": [55, 110],
            "result": ("refused" if not trace_open or slope is None
                       else 55 <= slope <= 110)},
    }
    if not trace_open:
        tier = "answer_level_only"
    elif a08 is None or a08 < 0.75:
        tier = "anchor_broken"
    elif checks["T1_undelivered_trace_correct"]["result"] == "capability_bound" and \
            checks["R_depth_turnover_at_matched_load"]["turnover"]:
        tier = "capability_bound_depth"
    elif checks["T1_undelivered_trace_correct"]["result"] == "surfacing_bound":
        tier = "surfacing_bound"
    elif not und and checks["D4_no_ceiling_at_matched_k32_ge"]["result"]:
        tier = "no_ceiling_measured"
    else:
        tier = "ambiguous"
    return {"tier": tier, "trace_open": trace_open, "calibration": calib_rate,
            "checks": checks}


def summarize(rows: list, gate: dict, model_digest: str) -> dict:
    exp = [r for r in rows if not r["is_dup"]]
    return {
        "schema": "round50-summary-v1",
        "family": "ladders",
        "task_type": "hop_chain",
        "model_class": "a flash-next-class local endpoint",
        "model_id_digest": model_digest,
        "seed_base": SEED_BASE,
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
        "selection_rule": ("per cell, scan the level's series in generation order and "
                           "take the first two items with answer yes and the first two "
                           "with answer no inside the cell's fact-count band; the anchor "
                           "cell A08 uses round 6's rule with no band"),
        "bands": {"matched": MATCH_BAND, "high": HIGH_BAND},
        "cells": cell_table(rows),
        "outcomes": {k: sum(1 for r in exp if r["outcome"] == k)
                     for k in sorted({r["outcome"] for r in exp})},
        "gate": gate,
        "transport": {
            "dispatches": len(rows),
            "experimental": len(exp),
            "duplicates": len(rows) - len(exp),
            "errors": sum(1 for r in rows if r["error"]),
            "prompt_tokens": sum(r["prompt_tokens"] or 0 for r in rows),
            "completion_tokens": sum(r["completion_tokens"] or 0 for r in rows),
            "wall_s_total": round(sum(r["wall_s"] or 0 for r in rows), 1),
        },
    }


# ---------------------------------------------------------------- gate artifact

def gate_spec() -> dict:
    """The registered gate, frozen before dispatch. Rows come from archived records only:
    round 6 (research/nightly-2026-10-16-0400) supplies the anchor and the 80-token-per-hop
    length law; issue #126 supplies the current-build output state."""
    return {
        "schema": GATE_SCHEMA,
        "question": ("When ladder accuracy fails at high hop depth at matched input load, "
                     "is the failure in the traversal (capability) or in the delivery of "
                     "the verdict through the 2048-token cap (surfacing)?"),
        "evidence_label": "Executed",
        "reference_firings": {
            "round6": {
                "path": "research/nightly-2026-10-16-0400/raw.jsonl",
                "blob_sha256": ROUND6_RAW_BLOB_SHA256,
                "anchor_seeds": list(ROUND6_ANCHOR_SEEDS),
                "anchor_answers": ROUND6_ANCHOR_ANSWERS,
                "anchor_completion_tokens": ROUND6_ANCHOR_TOKENS,
                "readout": ("40/40 correct, 0 truncations at k <= 16; completion_tokens "
                            "= -36 + 80k; the verdict is emitted after the traversal")},
            "issue126": ("the archived cap-bound selection premise no longer holds on the "
                         "current builds: round 49 read 0/11 truncations at 2048")},
        "rows": {
            "D1_anchor_round6_items_ge": (
                "the four archived round-6 k=8 items (same seeds, same template) stay at "
                "or above 3/4 delivered accuracy on this firing (round 6 read 4/4)"),
            "D2_shallow_matched_accuracy_ge": (
                "matched-load cells M08+M16 stay at or above 7/8 delivered accuracy"),
            "D3_load_at_depth16_ge": (
                "tripling the input load at k=16 (192 facts) keeps accuracy at or above "
                "3/4 (round 6's k=16 items averaged 232 facts and read 4/4)"),
            "D4_no_ceiling_at_matched_k32_ge": (
                "at matched load, k=32 stays at or above 3/4 delivered accuracy: no depth "
                "ceiling inside 4x the archived grid at constant prompt size"),
            "D5_load_does_not_help_at_depth": (
                "matched-minus-high accuracy at k=32 >= 0: load does not improve accuracy "
                "at fixed depth"),
            "D6_matched_above_baseline_ge": (
                "matched-load accuracy at or above 10/16, i.e. strictly above the "
                "0.50 constant baseline the balanced cells put there by construction"),
            "N1_census_channel_open": (
                "issue #105: the reasoning-supplying field is non-empty on the health call "
                "and on >= 90% of dispatched records; otherwise every trace-derived row "
                "is refused and the round is an answer-level claim only"),
            "N2_duplicate_pairs_byte_identical_ge": (
                "issue #100: at least 2 of the 3 duplicate pairs byte-identical (answer "
                "field and trace), token-count identity reported alongside"),
            "N3_trace_recovery_calibration_ge": (
                "the trace-recovery rule (last standalone yes/no of the trace) agrees with "
                "the delivered answer field on >= 75% of delivered records; if it does "
                "not, T1 and the slope row are refused, not reported"),
            "T1_undelivered_trace_correct": (
                "the decisive row: among undelivered records with trace text, the "
                "trace-recovered verdict equals gold in >= 2/3 => surfacing_bound; "
                "below that => capability_bound; admissible only if N1 and N3 hold"),
            "R_depth_turnover_at_matched_load": (
                "readout, never a tier by itself: M08 minus M32 accuracy >= 0.25 marks a "
                "turnover inside the grid extension"),
            "R_verdict_position_slope": (
                "readout: OLS slope of the estimated verdict surface position against "
                "depth over the matched cells, round 6's law predicts 80 tokens per hop, "
                "band [55, 110]")},
        "tier_rule": [
            "N1 not open => answer_level_only",
            "D1 below 0.75 => anchor_broken",
            "T1 capability_bound and a registered turnover => capability_bound_depth",
            "T1 surfacing_bound => surfacing_bound",
            "no undelivered record and D4 holds => no_ceiling_measured",
            "otherwise => ambiguous"],
        "caps": {"prompts": 40, "max_tokens": 2048, "dispatch_planned": 32},
        "not_a_claim": ("n = 4 per cell is exploratory depth resolution; one endpoint, one "
                        "firing; a trace-recovered verdict is not evidence the model "
                        "computed anything (claim ladder C4), it is a readout of what the "
                        "surfaced text says; the char-proportional verdict position is an "
                        "estimate, not a tokenizer measurement"),
    }


def gate_blob_sha256() -> str:
    return hashlib.sha256(json.dumps(gate_spec(), sort_keys=True).encode()).hexdigest()


def certify_reference() -> dict:
    """Fail-closed pin of the archived anchor firing (never write its text)."""
    blob = ROUND6_RAW.read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    if digest != ROUND6_RAW_BLOB_SHA256:
        raise AssertionError("round 6 reference archive blob moved: "
                             f"{digest} != {ROUND6_RAW_BLOB_SHA256}")
    rows = [json.loads(line) for line in blob.decode("utf-8").splitlines()]
    anchor = {r["seed"]: r for r in rows if r["level"] == ANCHOR_LEVEL}
    if sorted(anchor) != list(ROUND6_ANCHOR_SEEDS):
        raise AssertionError("round 6 anchor seed set moved")
    for seed, row in anchor.items():
        if row["parsed"] != ROUND6_ANCHOR_ANSWERS[seed] or not row["correct"]:
            raise AssertionError("round 6 anchor readout moved")
    return {"blob_sha256": digest, "records": len(rows), "anchor_records": len(anchor)}


# ---------------------------------------------------------------- selftest

def selftest() -> None:
    checks = 0

    def ok(cond, note):
        nonlocal checks
        checks += 1
        assert cond, note

    # 1. items: every cell builds, is certified by the independent solver, and the
    #    matched cells really hold the prompt size constant across a 4x depth range.
    cells = build_cells()
    for name in CELLS_ORDER:
        for it in cells[name]:
            check_item(it)
            ok(len(it["facts"]) % it["level"] == 0, "facts not a multiple of depth")
    for lvl in MATCHED_LEVELS:
        for it in cells[f"M{lvl:02d}"]:
            ok(MATCH_BAND[0] <= len(it["facts"]) <= MATCH_BAND[1], "matched band broken")
    for lvl in HIGH_LEVELS:
        for it in cells[f"H{lvl:02d}"]:
            ok(HIGH_BAND[0] <= len(it["facts"]) <= HIGH_BAND[1], "high band broken")
    ok(len({it["seed"] for it in cells["M08"]}) == 4, "duplicate seeds in a cell")
    ok([it["seed"] for it in cells["A08"]] == list(ROUND6_ANCHOR_SEEDS), "anchor drift")
    # 2. selection integrity: the band is doing work. A08 (no band) and M08 (64-72 facts)
    #    must differ in item set, and every M08 item must sit at the band's fact count.
    ok({it["seed"] for it in cells["A08"]} != {it["seed"] for it in cells["M08"]},
       "the band selected nothing: A08 and M08 are the same items")
    ok(all(len(it["facts"]) > max(len(a["facts"]) for a in cells["A08"])
           for it in cells["M08"]), "matched-load items are not heavier than the anchor")
    # 3. the reference archive is pinned and its anchor readout is what the gate says.
    cert = certify_reference()
    ok(cert["anchor_records"] == 4, "anchor not certified")
    planted = ROUND6_RAW_BLOB_SHA256[::-1]
    ok(planted != ROUND6_RAW_BLOB_SHA256, "digest pin degenerate")
    # 4. scorer arithmetic: a constant rule sits exactly at the balanced baseline, a
    #    perfect rule at 1.0, a flipped rule at 0.0, an undelivered record is not correct.
    fake = [dict(cell="M08", level=8, is_dup=False, gold=("yes" if i % 2 else "no"),
                 delivered=True, correct=(i % 2 == 0),
                 trace_answer=("yes" if i % 2 else "no"), trace_correct=(i % 2 == 0),
                 trace_agrees_delivered=True, truncated=False,
                 completion_tokens=100, prompt_tokens=10, wall_s=1.0, error=None,
                 verdict_token_pos_est=80, content_answer=("yes" if i % 2 else "no"),
                 census={"trace_chars": 50, "reasoning_source": "reasoning_content"},
                 response="x", trace="y", n_facts=64, n_chains=8)
            for i in range(8)]
    ok(_acc([dict(r, correct=True) for r in fake]) == 1.0, "perfect scorer")
    ok(_acc([dict(r, correct=False) for r in fake]) == 0.0, "flipped scorer")
    const_no = [dict(r, correct=(r["gold"] == "no")) for r in fake]
    ok(_acc(const_no) == 0.5, "a constant rule must sit at the balanced baseline")
    ok(_acc(fake) == 0.5 and len(fake) == 8, "the control set is not balanced")
    # 5. trace recovery: the last-occurrence rule must read the CONCLUSION, not an
    #    intermediate deliberation yes/no, and must return None on a traceless record.
    ok(last_answer("Start. The chain gives no. Recheck. Thus answer yes.") == "yes",
       "trace rule read an intermediate verdict")
    ok(first_answer("Start. The chain gives no. Recheck. Thus answer yes.") == "no",
       "the first-occurrence control does not behave differently")
    ok(trace_verdict_cue("We check facts. no link. Thus answer yes.") == "yes",
       "cue rule failed")
    ok(last_answer("") is None and first_answer("") is None, "empty trace parsed")
    ok(last_answer("The answer is neither one nor the other") is None,
       "parser matched a non-verdict")
    # 6. planted slip (detection power): a trace that ends on the WRONG verdict must be
    #    scored as a capability failure, not silently as a surfacing failure.
    gold = "no"
    wrong = score_record("M24", {"level": 24, "answer": gold, "seed": 1,
                                "seed_hash": "h", "facts": [("a", "precedes", "b")],
                                "rule": "r", "query": ["a", "precedes", "b"]},
                        False, {"content": "", "trace": "deliberate. Thus answer yes.",
                                "msg_fields": ["content", "reasoning_content", "role"],
                                "trace_source": "reasoning_content",
                                "trace_content_chars": 27, "trace_reasoning_chars": 0,
                                "finish_reason": "length", "completion_tokens": 2048,
                                "prompt_tokens": 40, "wall_s": 9.0}, None, ())
    ok(wrong["outcome"] == "undelivered_truncated", "truncation not classified")
    ok(wrong["trace_answer"] == "yes" and not wrong["trace_correct"],
       "planted wrong-verdict trace scored as surfaced")
    right = score_record("M24", wrong and {"level": 24, "answer": gold, "seed": 1,
                                          "seed_hash": "h",
                                          "facts": [("a", "precedes", "b")],
                                          "rule": "r", "query": ["a", "precedes", "b"]},
                         False, {"content": "", "trace": "work work. Thus answer no.",
                                 "msg_fields": ["content", "reasoning_content", "role"],
                                 "trace_source": "reasoning_content",
                                 "trace_content_chars": 26, "trace_reasoning_chars": 0,
                                 "finish_reason": "length", "completion_tokens": 2048,
                                 "prompt_tokens": 40, "wall_s": 9.0}, None, ())
    ok(right["outcome"] == "undelivered_truncated" and right["trace_correct"],
       "the surfacing readout cannot see a completed traversal")
    # 7. the gate separates the two worlds it is built to separate: plant a firing where
    #    every deep failure is a capability failure, and one where every deep failure is a
    #    delivery failure over a correct trace. The tiers must differ.
    def plant(deep_ok_in_trace: bool) -> list:
        rows = []
        for cell, lvl in (("A08", 8), ("M08", 8), ("M16", 16), ("M24", 24), ("M32", 32),
                          ("H16", 16), ("H32", 32)):
            for i in range(4):
                gold = "yes" if i % 2 else "no"
                shallow = lvl <= 16
                delivered = shallow or (cell.startswith("H") and i == 0)
                rows.append(dict(
                    cell=cell, level=lvl, is_dup=False, seed=f"{cell}{i}",
                    prompt_sha256=f"p{cell}{i}", join_key=f"{cell}{i}|p{cell}{i}",
                    gold=gold, delivered=delivered, correct=delivered,
                    truncated=not delivered, completion_tokens=2048 if not delivered else 900,
                    prompt_tokens=40, wall_s=5.0, error=None,
                    verdict_token_pos_est=(900 if delivered else None),
                    content_answer=(gold if delivered else None),
                    trace_answer=(gold if (delivered or deep_ok_in_trace) else
                                  ("no" if gold == "yes" else "yes")),
                    trace_correct=(delivered or deep_ok_in_trace),
                    trace_agrees_delivered=delivered,
                    census={"trace_chars": 1200, "reasoning_source": "reasoning_content"},
                    response=(gold if delivered else ""),
                    trace="text", n_facts=64, n_chains=4))
        # Three control re-dispatches, labelled under a DUP- cell exactly as the
        # dispatcher does: the join must still find the pair, because it keys on seed
        # plus prompt digest, not on the cell label.
        for idx in (9, 13, 25):
            rows.append(dict(rows[idx], cell=f"DUP-{rows[idx]['cell']}", is_dup=True))
        return rows

    health = {"reasoning_source": "reasoning_content", "trace_chars": 140}
    cap = evaluate_gate(plant(False), health)
    surf = evaluate_gate(plant(True), health)
    ok(cap["tier"] == "capability_bound_depth", f"capability world tier {cap['tier']}")
    ok(surf["tier"] == "surfacing_bound", f"surfacing world tier {surf['tier']}")
    # 7b. the #100 join control: the planted duplicates carry a DUP- cell label, so a join
    #     that reads the cell label pairs nothing (the defect round 50 hit in the field).
    n2 = surf["checks"]["N2_duplicate_pairs_byte_identical_ge"]
    ok(n2["n_pairs"] == 3, f"duplicate join found {n2['n_pairs']} pairs")
    ok(n2["value"] == 3 and n2["token_identical"] == 3, "planted duplicates not identical")
    labelled = [dict(r) for r in plant(True)]
    for r in labelled:
        r.pop("join_key", None)
    ok(evaluate_gate(labelled, health)["checks"]["N2_duplicate_pairs_byte_identical_ge"
                                         ]["n_pairs"] == 3,
       "the seed-plus-digest join does not recover the pairs")
    # 8. a zero-trace deployment must refuse the trace rows, not score them (#105).
    closed = [dict(r, census={"trace_chars": 0, "reasoning_source": ""},
                   trace="", trace_answer=None, trace_correct=False,
                   trace_agrees_delivered=False) for r in plant(True)]
    zero = evaluate_gate(closed, {"reasoning_source": "", "trace_chars": 0})
    ok(zero["tier"] == "answer_level_only", f"zero-trace tier {zero['tier']}")
    ok(zero["checks"]["T1_undelivered_trace_correct"]["result"] == "refused",
       "trace row scored on a zero-trace deployment")
    ok(zero["checks"]["R_verdict_position_slope"]["result"] == "refused",
       "slope row scored on a zero-trace deployment")
    # 9. an anchor that cannot do the shallow item must break the tier, not be averaged
    #    into it: plant 0/4 on the archived anchor items over the surfacing world.
    broken = [dict(r, correct=False, delivered=True, content_answer=r["gold"],
                   gold=("no" if r["gold"] == "yes" else "yes"))
              if r["cell"] == "A08" else r for r in plant(True)]
    ok(evaluate_gate(broken, health)["tier"] == "anchor_broken",
       "anchor failure did not move the tier")
    # 10. OLS slope sanity plus the negative control that a flat series gives slope 0.
    ok(ols_slope([(8, 600), (16, 1240), (24, 1900)]) == 81.25, "slope fit wrong")
    ok(ols_slope([(8, 500), (16, 500)]) == 0.0, "flat series not zero slope")
    ok(ols_slope([(8, 500)]) is None, "under-determined slope returned a number")
    # 11. sanitizer: no IP, URL, host or credential assignment survives (documentation
    #     addresses from RFC 5737 only, never a real host).
    s = sanitize("see http://198.51.100.7:8080/v1 and 192.0.2.1 fe80::1 "
                 "token: abc123 host: node-9", ("198.51.100.7:8080",))
    ok("198.51.100.7" not in s and "192.0.2.1" not in s and "http" not in s, s)
    ok("abc123" not in s and "node-9" not in s, s)
    # 12. caps are contractual.
    work = work_items(cells)
    ok(len(work) + 1 <= 40, "protocol cap: 40 prompts")
    ok(MAX_TOKENS <= 2048, "protocol cap: max_tokens")
    ok(len(work) == 31, f"planned dispatch count drifted: {len(work)}")
    # 13. the prompt template is byte-stable and carries each fact exactly once.
    p1, p2 = render_prompt(cells["M32"][0]), render_prompt(cells["M32"][0])
    ok(p1 == p2, "prompt render not deterministic")
    for fact in cells["M32"][0]["facts"]:
        ok(p1.count(f"{fact[0]} precedes {fact[2]}.") == 1, "fact rendered twice")
    ok(p1.endswith("Answer with exactly one word: yes or no."), "template drift")
    # 14. negative controls on the item guard: a flipped answer and a pre-#69 item are
    #     both refused.
    it0 = json.loads(json.dumps(cells["M16"][0]))
    it0["answer"] = "no" if it0["answer"] == "yes" else "yes"
    try:
        check_item(it0)
    except AssertionError:
        checks += 1
    else:
        raise AssertionError("negative control: flipped answer not caught")
    noise = json.loads(json.dumps(cells["M16"][0]))
    noise["facts"] = noise["facts"][:2] + [["zzz1", "precedes", "zzz2"]]
    try:
        check_item(noise)
    except AssertionError:
        checks += 1
    else:
        raise AssertionError("negative control: pre-fix corpus not refused")
    # 15. the gate blob is reproducible, so the pin in this file can be trusted.
    ok(len(gate_blob_sha256()) == 64 and gate_blob_sha256() == gate_blob_sha256(),
       "gate digest unstable")
    ok(set(gate_spec()["rows"]) == set(evaluate_gate(plant(True), health)["checks"]),
       "registered rows and evaluated rows drifted apart")
    print(f"selftest passed ({checks} checks)")


# ---------------------------------------------------------------- main

def main(argv: list) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--gate", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--run", action="store_true")
    p.add_argument("--rescore", action="store_true",
                   help="recompute the gate and summary from an existing raw.jsonl "
                        "without dispatching (raw bytes stay immutable)")
    p.add_argument("--raw", default="raw.jsonl")
    p.add_argument("--summary", default="summary.json")
    p.add_argument("--health", default="health.json")
    args = p.parse_args(argv)
    if args.selftest:
        selftest()
        return 0
    if args.gate:
        spec = gate_spec()
        blob = json.dumps(spec, sort_keys=True, indent=1)
        Path(args.summary if args.summary != "summary.json"
             else "gate.json").write_text(blob + "\n", encoding="utf-8")
        print(gate_blob_sha256())
        return 0
    if args.rescore:
        raw_bytes = Path(args.raw).read_bytes()
        raw_digest = hashlib.sha256(raw_bytes).hexdigest()
        rows = [json.loads(line) for line in raw_bytes.decode("utf-8").splitlines()]
        health = json.loads(Path(args.health).read_text(encoding="utf-8"))
        gate = evaluate_gate(rows, health["census"])
        prior = {}
        if Path(args.summary).exists():
            prior = json.loads(Path(args.summary).read_text(encoding="utf-8"))
        summary = summarize(rows, gate,
                            prior.get("model_id_digest", "not-recorded-on-dispatch"))
        summary["gate"]["blob_sha256"] = gate_blob_sha256()
        summary["aggregation"] = {
            "mode": "rescore",
            "raw_sha256": raw_digest,
            "raw_records": len(rows),
            "note": ("recomputed from the dispatched raw.jsonl without any new endpoint "
                     "call; the duplicate join was corrected from a cell-label key to seed "
                     "plus prompt digest, which is what the #100 control means"),
        }
        Path(args.summary).write_text(json.dumps(summary, sort_keys=True, indent=1) + "\n",
                                      encoding="utf-8")
        print("raw", raw_digest[:16], "| records", len(rows), "| tier", gate["tier"])
        print("N2", gate["checks"]["N2_duplicate_pairs_byte_identical_ge"])
        return 0
    cells = build_cells()
    work = work_items(cells)
    if args.dry_run:
        joined = "\n".join(render_prompt(it) for _, it, _ in work)
        print(json.dumps({"cells": {k: len(v) for k, v in cells.items()},
                          "dispatch_experimental": len(work),
                          "dispatch_total_with_census": len(work) + 1,
                          "prompt_corpus_sha256":
                              hashlib.sha256(joined.encode()).hexdigest()[:16],
                          "max_tokens": MAX_TOKENS}, sort_keys=True, indent=1))
        return 0
    if args.run:
        digest = gate_blob_sha256()
        if digest != ROUND50_GATE_BLOB_SHA256:
            print(f"ERROR gate moved: {digest} != {ROUND50_GATE_BLOB_SHA256}",
                  file=sys.stderr)
            return 3
        certify_reference()
        base = os.environ.get("NIGHTLY_BASE_URL", "").rstrip("/")
        model = os.environ.get("NIGHTLY_MODEL_ID", "")
        key = os.environ.get("NIGHTLY_API_KEY", "")
        if not (base and model and key):
            print("ERROR NIGHTLY_BASE_URL, NIGHTLY_MODEL_ID and NIGHTLY_API_KEY "
                  "must be set", file=sys.stderr)
            return 2
        secrets = (base, base.split("//")[-1].split("/")[0], key)
        model_digest = hashlib.sha256(model.encode()).hexdigest()[:12]
        raw_path = Path(args.raw)
        lock = threading.Lock()
        raw_path.write_text("", encoding="utf-8")

        def emit(rec: dict) -> None:
            with lock:
                with raw_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, sort_keys=True) + "\n")
                    fh.flush()
                    os.fsync(fh.fileno())

        census_resp, census_err = {}, None
        try:
            census_resp = call(CENSUS_PROMPT, base, model, key, max_tokens=256)
        except Exception as exc:  # the health call is not experimental data
            census_err = type(exc).__name__
        health = {"ok": census_err is None, "outcome": "answered_in_answer_field"
                  if (census_resp.get("content") or "").strip() else "empty",
                  "error": census_err, "census": census_of(census_resp),
                  "completion_tokens": census_resp.get("completion_tokens"),
                  "prompt_tokens": census_resp.get("prompt_tokens"),
                  "latency_s": census_resp.get("wall_s")}
        Path(args.health).write_text(json.dumps(health, sort_keys=True, indent=1) + "\n",
                                     encoding="utf-8")

        def one(job) -> dict:
            idx, (cell, item, is_dup) = job
            prompt = render_prompt(item)
            err = None
            resp = {}
            for attempt in (1, 2):
                try:
                    resp = call(prompt, base, model, key)
                    err = None
                    break
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                        ConnectionError, OSError) as exc:  # one retry, then record it
                    err = type(exc).__name__
                    time.sleep(5 * attempt)
            rec = score_record(cell, item, is_dup, resp, err, secrets)
            rec["dispatch_index"] = idx
            rec["attempts"] = 2 if err else 1
            emit(rec)
            return rec

        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
            rows = list(pool.map(one, enumerate(work)))
        gate = evaluate_gate(rows, health["census"])
        summary = summarize(rows, gate, model_digest)
        summary["gate"]["blob_sha256"] = digest
        Path(args.summary).write_text(json.dumps(summary, sort_keys=True, indent=1) + "\n",
                                      encoding="utf-8")
        for row in cell_table(rows):
            print(f"| {row['cell']} | k={row['level']} | facts={row['n_facts']} | "
                  f"chains={row['n_chains']} | n={row['n']} | delivered={row['delivered']} | "
                  f"correct={row['correct']} | acc={row['accuracy']} | trunc={row['truncated']} | "
                  f"trace_correct={row['trace_correct']} | mean_toks={row['completion_tokens_mean']} |")
        print("tier", gate["tier"], "| outcomes", summary["outcomes"])
        return 0
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

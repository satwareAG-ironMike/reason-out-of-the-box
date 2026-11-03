#!/usr/bin/env python3
"""Nightly round 9 (tracker #65, firing 2026-10-18 02:00): the model-facing half of
issue #71, with the #73 transport hardening.

Question: at constant prompt load (E = 24 facts, C = 24/k chains), does hop-chain
accuracy turn over as hop depth k grows, and is any turnover a depth cliff or a
token-budget cliff? Round 8 declared this grid and passed its gate on all 8 cells,
but its probe arm died on transport (12 of 15 completions empty, then wall-clock),
so no depth measurement exists for the grid yet. This round runs the same grid on a
different, faster local endpoint class, sequentially, with the hardening issue #73
requires: a health check immediately before the grid, sequential dispatch, a
per-item deadline with one retry, an incremental fsynced raw archive, empty
completions counted as transport failures with a recorded error class (never as
no_answer evidence), and a per-arm wall-clock budget after which the arm stops and
the partial record is reported.

Independence: this file imports nothing from generators/ and re-implements the
component-isomorphic construction, the BFS solver, the structural verifier, the
permutation-calibrated leak gate, the probe and the scorer from scratch. The
item stream is deliberately byte-identical to round 8's (same seed base, same
name pools, same selection rule), so this round is a direct continuation of round
8's declared grid rather than a new one: selftest control 4 asserts stream
identity against the per-cell gate statistics round 8 published (rules,
calibrated threshold, observed max, p-value, pool gold-yes count, selected
prompt-character mean, as recorded in round 8's gate.json on branch
research/nightly-2026-10-17-0400). Nothing is chosen after seeing a response.

Budget replay is offline and free: each completion is replayed against fixed
budgets {256, 512, 1024, 2048} against the answer position. When the endpoint
separates reasoning into its own field and content carries the answer (the
response shape round 8 found on this endpoint class), the answer position is the
completion length, so completion_tokens is used directly; otherwise a
character-proportional estimate is used and reported as an estimate.

d* procedure: the round-8 trichotomy. Per depth: budget_limited (no-answer rate
above 0.5), maintained (Wilson 95% lower bound >= MAJORITY_FLOOR + MARGIN with
at least MIN_CERTIFY items), collapsed (Wilson 95% upper bound below the floor),
inconclusive (neither bound crosses), descriptive (fewer than MIN_CERTIFY items,
reported but never used to set d*). d* is the largest maintained arm-L depth
below the first collapsed arm-L depth.

Usage:
  const_load_depth.py --selftest
  const_load_depth.py --gate            [--out FILE]
  const_load_depth.py --probe           [--out-dir DIR] [--budget-seconds N]
  const_load_depth.py --replay          [--raw FILE]

Endpoint is read from the environment (NIGHTLY_BASE_URL, NIGHTLY_MODEL_ID,
NIGHTLY_API_KEY optional) and stripped from every artifact (public-only rule).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request

REL = "precedes"
RULE_SENTENCE = (f"Rule: for all x, y, z: if x {REL} y and y {REL} z, "
                 f"then x {REL} z. Facts state direct {REL} links.")
SEED_BASE = 20261017
ALPHA = 0.05
MARGIN = 0.10
MAJORITY_FLOOR = 0.5
PERMS = 400
MAX_TOKENS = 2048
TEMPERATURE = 0.0
PROMPT_CAP = 40
BUDGETS = (256, 512, 1024, 2048)
CONST_E = 24
ARM_L = ((2, 12), (3, 8), (4, 6), (6, 4), (8, 3), (12, 2))
ARM_X = ((16, 2), (24, 2))
ITEMS_PER_DEPTH_L = 6
YES_PER_DEPTH_L = 3
ITEMS_PER_DEPTH_X = 2
YES_PER_DEPTH_X = 1
CANDIDATES = 40
MIN_CERTIFY = 6
ITEM_DEADLINE_S = 600
PROBE_BUDGET_S = 3600
ATTEMPTS_PER_ITEM = 2
HEALTH_PROMPT = "Reply with exactly one word: yes or no. Does 2 precede 3? ANSWER:"

# Name pools: identical to round 8 by design, so the seed-frozen item stream is
# byte-identical and this round cross-checks against round 8's published record.
POOL_A = ("ka", "ke", "ki", "ko", "ku", "la", "le", "li", "lo", "ma", "me", "mi",
          "mo", "na", "ne", "ni", "pa", "pe", "pi", "ra", "re", "ri", "sa", "se",
          "si", "ta", "te", "ti", "va", "ve", "vi", "za", "ze", "zi")
POOL_B = ("ben", "dan", "fen", "gan", "hen", "jin", "kol", "lan", "min", "nor",
          "pan", "qir", "ran", "sol", "tan", "vur", "wen", "yot", "zur")
POOL_C = ("dex", "mark", "pik", "rove", "skel", "thum", "vosh", "wick", "yarn")

# Round 8's published per-cell gate record (gate.json on branch
# research/nightly-2026-10-17-0400, also in its README): (arm, k, chains,
# battery_rules, calibrated_threshold, observed_max, p_value, pool_gold_yes,
# selected prompt_chars_mean). Selftest control 4 asserts stream identity.
ROUND8_GATE = (
    ("L", 2, 12, 100, 0.700, 0.575, 0.9825, 21, 1110.0),
    ("L", 3, 8, 130, 0.725, 0.625, 0.7781, 22, 1111.5),
    ("L", 4, 6, 130, 0.725, 0.675, 0.2893, 24, 1111.0),
    ("L", 6, 4, 100, 0.725, 0.600, 0.9776, 19, 1111.0),
    ("L", 8, 3, 100, 0.800, 0.750, 0.5835, 12, 1111.3),
    ("L", 12, 2, 130, 0.725, 0.625, 0.8603, 24, 1109.5),
    ("X", 16, 2, 74, 0.700, 0.575, 1.0000, 23, 1414.0),
    ("X", 24, 2, 100, 0.725, 0.725, 0.0723, 19, 2035.0),
)


def _name(rng: random.Random, taken: set) -> str:
    for _ in range(500):
        name = rng.choice(POOL_A) + rng.choice(POOL_B) + rng.choice(POOL_C)
        if name not in taken:
            taken.add(name)
            return name
    raise RuntimeError("name pool exhausted")


def gen_item(k: int, c_chains: int, seed: int) -> dict:
    """Component-isomorphic hop chain: C disjoint directed paths of exactly k edges
    over fresh entities; the query is (head of one path, tail of one path); yes iff
    both endpoints lie on the same path. RNG call sequence is part of the seed-frozen
    stream contract and must stay in this order."""
    rng = random.Random(seed)
    taken: set = set()
    chains = [[_name(rng, taken) for _ in range(k + 1)] for _ in range(c_chains)]
    facts = [(u, REL, v) for ch in chains for u, v in zip(ch, ch[1:])]
    main = rng.randrange(c_chains)
    yes = rng.random() < 0.5
    if yes:
        src, tgt, chain_len = chains[main][0], chains[main][-1], k
    else:
        other = rng.randrange(c_chains - 1)
        if other >= main:
            other += 1
        src, tgt, chain_len = chains[main][0], chains[other][-1], None
    rng.shuffle(facts)
    return {
        "task_type": "hop_chain",
        "arm": "L" if k * c_chains == CONST_E else "X",
        "level": k,
        "chains": c_chains,
        "edges": len(facts),
        "seed": seed,
        "seed_hash": hashlib.sha256(f"ladders|hop_chain|{k}|{seed}".encode())
        .hexdigest()[:16],
        "rule": RULE_SENTENCE,
        "facts": [[s, r, t] for s, r, t in facts],
        "query": [src, REL, tgt],
        "answer": "yes" if yes else "no",
        "chain_len": chain_len,
    }


def bfs_dist(facts: list, src: str) -> dict:
    graph: dict = {}
    for s, _, t in facts:
        graph.setdefault(s, []).append(t)
    dist = {src: 0}
    queue = [src]
    while queue:
        nxt: list = []
        for u in queue:
            for v in graph.get(u, ()):
                if v not in dist:
                    dist[v] = dist[u] + 1
                    nxt.append(v)
        queue = nxt
    return dist


def verify_item(item: dict) -> list:
    """Independent structural and solvability audit of one item. Returns violations."""
    bad: list = []
    facts = item["facts"]
    k = item["level"]
    out: dict = {}
    inc: dict = {}
    nodes: set = set()
    for s, rel, t in facts:
        if rel != REL:
            bad.append(f"relation {rel!r}")
        out[s] = out.get(s, 0) + 1
        inc[t] = inc.get(t, 0) + 1
        nodes |= {s, t}
    if len({tuple(f) for f in facts}) != len(facts):
        bad.append("duplicate facts")
    adj: dict = {}
    for s, _, t in facts:
        adj.setdefault(s, set()).add(t)
        adj.setdefault(t, set()).add(s)
    seen: set = set()
    n_comp = 0
    for node in nodes:
        if node in seen:
            continue
        n_comp += 1
        comp = {node}
        stack = [node]
        while stack:
            u = stack.pop()
            for v in adj.get(u, ()):
                if v not in comp:
                    comp.add(v)
                    stack.append(v)
        seen |= comp
        edges = sum(out.get(u, 0) for u in comp)
        if edges != k or len(comp) != k + 1:
            bad.append(f"component of {edges} edges over {len(comp)} nodes")
        heads = [u for u in comp if inc.get(u, 0) == 0 and out.get(u, 0) == 1]
        tails = [u for u in comp if inc.get(u, 0) == 1 and out.get(u, 0) == 0]
        if len(heads) != 1 or len(tails) != 1:
            bad.append("component is not a directed path")
        if any(out.get(u, 0) > 1 or inc.get(u, 0) > 1 for u in comp):
            bad.append("branching node")
    if n_comp != item["chains"]:
        bad.append(f"{n_comp} components, manifest says {item['chains']}")
    qs, _, qt = item["query"]
    if inc.get(qs, 0) != 0 or out.get(qs, 0) != 1:
        bad.append("query source is not a path head")
    if inc.get(qt, 0) != 1 or out.get(qt, 0) != 0:
        bad.append("query target is not a path tail")
    dist = bfs_dist(facts, qs)
    if (item["answer"] == "yes") != (qt in dist):
        bad.append("stored answer disagrees with independent BFS")
    if item["answer"] == "yes" and dist.get(qt) != k:
        bad.append(f"shortest path {dist.get(qt)} != level {k}")
    if item["answer"] == "no" and item["chain_len"] is not None:
        bad.append("no item carries a chain_len")
    return bad


def features(item: dict) -> dict:
    """Traversal-free feature battery over the query endpoints and the fact list."""
    facts = item["facts"]
    srcs = {s for s, _, _ in facts}
    tgts = {t for _, _, t in facts}
    out: dict = {}
    inc: dict = {}
    for s, _, t in facts:
        out[s] = out.get(s, 0) + 1
        inc[t] = inc.get(t, 0) + 1
    qs, _, qt = item["query"]
    first_idx: dict = {}
    for i, (s, _, t) in enumerate(facts):
        first_idx.setdefault(s, i)
        first_idx.setdefault(t, i)
    e_count = len(facts)
    return {
        "tgt_is_fact_target": qt in tgts,
        "tgt_is_fact_source": qt in srcs,
        "tgt_outdeg_zero": out.get(qt, 0) == 0,
        "tgt_indeg_zero": inc.get(qt, 0) == 0,
        "src_is_fact_target": qs in tgts,
        "src_is_fact_source": qs in srcs,
        "src_outdeg_zero": out.get(qs, 0) == 0,
        "src_indeg_zero": inc.get(qs, 0) == 0,
        "tgt_name_lt_src_name": qt < qs,
        "tgt_name_longer_than_src": len(qt) > len(qs),
        "tgt_first_mention_before_src": first_idx.get(qt, 10 ** 9) < first_idx.get(qs, 10 ** 9),
        "tgt_first_third": first_idx.get(qt, 10 ** 9) < e_count / 3.0,
        "src_first_third": first_idx.get(qs, 10 ** 9) < e_count / 3.0,
        "tgt_last_third": first_idx.get(qt, 10 ** 9) >= 2.0 * e_count / 3.0,
        "n_facts_even": e_count % 2 == 0,
        "src_is_source_of_first_fact": facts[0][0] == qs,
        "tgt_is_target_of_last_fact": facts[-1][2] == qt,
    }


def _bits(vals: list) -> int:
    mask = 0
    for i, v in enumerate(vals):
        if v:
            mask |= 1 << i
    return mask


def _acc(pred: int, gold: int, n: int) -> float:
    return 1.0 - ((pred ^ gold) & ((1 << n) - 1)).bit_count() / n


def battery(items: list) -> tuple:
    n = len(items)
    gold = _bits([it["answer"] == "yes" for it in items])
    cols: dict = {}
    for it in items:
        for name, val in features(it).items():
            cols.setdefault(name, []).append(val)
    constant = sorted(name for name, vals in cols.items() if len(set(vals)) == 1)
    varying = {name: _bits(vals) for name, vals in cols.items() if len(set(vals)) > 1}
    names = sorted(varying)
    mask = (1 << n) - 1
    rules: dict = {}
    for name in names:
        b = varying[name]
        rules[f"single:{name}->yes"] = b
        rules[f"single:{name}->no"] = (~b) & mask
    for i, a in enumerate(names):
        for bname in names[i + 1:]:
            x, y = varying[a], varying[bname]
            rules[f"conj:{a}&{bname}"] = x & y
            rules[f"conj:{a}&~{bname}"] = x & (~y) & mask
            rules[f"conj:~{a}&{bname}"] = (~x) & mask & y
            rules[f"conj:~{a}&~{bname}"] = (~x) & mask & (~y) & mask
    rules["stump:always_yes"] = mask
    rules["stump:always_no"] = 0
    return constant, rules, gold


def gate(items: list, perms: int = PERMS, seed: int = SEED_BASE) -> dict:
    """Permutation-calibrated leak gate, family-wise alpha over the whole battery."""
    n = len(items)
    constant, rules, gold = battery(items)
    obs = {name: _acc(pred, gold, n) for name, pred in rules.items()}
    top = sorted(obs.items(), key=lambda kv: -kv[1])[:5]
    yes_n = sum(1 for it in items if it["answer"] == "yes")
    majority = max(yes_n, n - yes_n) / n
    rng = random.Random(seed)
    labels = [it["answer"] == "yes" for it in items]
    preds = list(rules.values())
    null_max: list = []
    for _ in range(perms):
        rng.shuffle(labels)
        g = _bits(labels)
        null_max.append(max(_acc(p, g, n) for p in preds))
    null_max.sort()
    threshold = null_max[min(perms - 1, int(round((1.0 - ALPHA) * perms)))]
    obs_max = top[0][1] if top else 0.0
    exceed = sum(1 for x in null_max if x >= obs_max)
    p_value = (exceed + 1) / (perms + 1)
    flagged = sorted((name for name, a in obs.items() if a > threshold),
                     key=lambda nm: -obs[nm])
    return {
        "n": n,
        "gold_yes": yes_n,
        "majority_baseline": round(majority, 4),
        "battery_rules": len(rules),
        "constant_features": constant,
        "top_rules": [{"rule": nm, "accuracy": round(a, 4)} for nm, a in top],
        "observed_max": round(obs_max, 4),
        "null_max_p95": round(threshold, 4),
        "calibrated_threshold": round(threshold, 4),
        "p_value": round(p_value, 4),
        "flagged_rules": flagged,
        "verdict": "leak" if flagged else "no leak at family-wise alpha",
    }


def cell_seed(k: int, c_chains: int, index: int) -> int:
    return SEED_BASE + 1_000_000 * k + 10_000 * c_chains + index


def build_cell(k: int, c_chains: int, want_yes: int, want_total: int) -> tuple:
    """Selection rule fixed in advance: seed order, the first `want_yes` yes items
    and the first `want_total - want_yes` no items, each candidate passing the
    independent structural audit. Returns (selected, full candidate pool). The gate
    runs on the whole pool, never on the selected items: round 8 showed the gate has
    zero power at 6 items per cell."""
    pool: list = []
    picked: list = []
    yes_n = 0
    for i in range(CANDIDATES):
        item = gen_item(k, c_chains, cell_seed(k, c_chains, i))
        violations = verify_item(item)
        if violations:
            raise RuntimeError(f"cell k={k} C={c_chains} seed {item['seed']}: {violations}")
        pool.append(item)
        if item["answer"] == "yes":
            if yes_n < want_yes:
                picked.append(item)
                yes_n += 1
        elif len(picked) - yes_n < want_total - want_yes:
            picked.append(item)
    if len(picked) != want_total:
        raise RuntimeError(f"cell k={k} C={c_chains}: selection rule starved")
    return picked, pool


def all_cells() -> list:
    cells = []
    for (k, c_chains) in ARM_L:
        picked, pool = build_cell(k, c_chains, YES_PER_DEPTH_L, ITEMS_PER_DEPTH_L)
        cells.append({"k": k, "chains": c_chains, "arm": "L", "items": picked, "pool": pool})
    for (k, c_chains) in ARM_X:
        picked, pool = build_cell(k, c_chains, YES_PER_DEPTH_X, ITEMS_PER_DEPTH_X)
        cells.append({"k": k, "chains": c_chains, "arm": "X", "items": picked, "pool": pool})
    return cells


def render_prompt(item: dict) -> str:
    lines = [RULE_SENTENCE]
    lines += [f"Fact {i + 1}: {s} {r} {t}." for i, (s, r, t) in enumerate(item["facts"])]
    s, r, t = item["query"]
    lines.append(f"Question: does {s} {r} {t}? Answer with exactly one word: yes or no.")
    return "\n".join(lines)


ANSWER_RE = re.compile(r"\b(yes|no)\b", re.IGNORECASE)
URL_RE = re.compile(r"https?://\S+|\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|"
                    r"(?:/[A-Za-z0-9_.-]+){2,}|[A-Za-z]:\\[^\s]*")


def sanitize(text: str) -> str:
    return URL_RE.sub("[REDACTED]", text or "")


def parse_answer(content: str) -> tuple:
    """Declared parser: the LAST standalone yes/no token in the content field
    (reasoning is in a separate field on this endpoint class and is not parsed).
    Returns (answer or None, char offset of the match)."""
    matches = list(ANSWER_RE.finditer(content or ""))
    if not matches:
        return None, -1
    m = matches[-1]
    return m.group(1).lower(), m.start()


def endpoint_url() -> str:
    base = os.environ.get("NIGHTLY_BASE_URL", "").strip().rstrip("/")
    if not base:
        raise SystemExit("NIGHTLY_BASE_URL is not set; the probe cannot run")
    return base + "/chat/completions"


def call_endpoint(prompt: str, deadline_s: int) -> dict:
    """One chat-completion request. Returns a normalized response dict; a transport
    failure is returned as {'error': <class>} with empty fields, never raised, so
    the dispatch loop can classify and record it."""
    key = os.environ.get("NIGHTLY_API_KEY", "").strip()
    model = os.environ.get("NIGHTLY_MODEL_ID", "").strip()
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": MAX_TOKENS, "temperature": TEMPERATURE,
                       "stream": False}).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(endpoint_url(), data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=deadline_s) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace"))
        choice = (payload.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        usage = payload.get("usage") or {}
        return {
            "content": sanitize(msg.get("content") or ""),
            "reasoning": sanitize(msg.get("reasoning_content") or ""),
            "finish_reason": choice.get("finish_reason"),
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
        }
    except urllib.error.HTTPError as exc:
        return {"error": f"http_{exc.code}", "content": "", "reasoning": "",
                "finish_reason": None, "prompt_tokens": 0, "completion_tokens": 0}
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {"error": type(exc).__name__, "content": "", "reasoning": "",
                "finish_reason": None, "prompt_tokens": 0, "completion_tokens": 0}


def classify(resp: dict) -> str:
    """Error class for a response that did not carry a usable completion.
    Round-8 lesson: empty completions under pool load are transport failures, never
    no_answer evidence about the model."""
    if resp.get("error"):
        return resp["error"]
    if resp["completion_tokens"] == 0:
        return "empty_completion"
    return ""


def health_check() -> dict:
    """#73 requirement 1: one trivial completion immediately before the grid.
    The arm is refused if the check fails."""
    t0 = time.monotonic()
    resp = call_endpoint(HEALTH_PROMPT, deadline_s=120)
    latency = round(time.monotonic() - t0, 3)
    cls = classify(resp)
    ok = not cls and parse_answer(resp["content"])[0] is not None
    return {"ok": ok, "error_class": cls or None, "latency_s": latency,
            "completion_tokens": resp["completion_tokens"],
            "prompt_tokens": resp["prompt_tokens"]}


def score_record(item: dict, resp: dict, latency: float, attempt: int) -> dict:
    answer, offset = parse_answer(resp["content"])
    gold = item["answer"]
    reasoning = resp.get("reasoning") or ""
    content = resp.get("content") or ""
    total_tokens = resp.get("completion_tokens") or 0
    # Answer position: this endpoint class separates reasoning into its own field
    # and content carries the answer (round 8's finding for the same response
    # shape), so the answer sits at the end of the completion and the position is
    # the completion length itself. For the other shape (trace in content) the
    # character-proportional estimate is used and reported as an estimate.
    if reasoning:
        est_answer_tokens = total_tokens if total_tokens > 0 else -1
        est_kind = "completion_tokens"
    elif reasoning == "" and content and offset >= 0:
        est_answer_tokens = round(total_tokens * (offset + 1) / max(len(content), 1))
        est_kind = "char_estimate"
    else:
        est_answer_tokens = -1
        est_kind = "none"
    err = classify(resp)
    if answer is None and not err:
        state = "no_answer"
    elif answer is None:
        state = "transport_failure"
    else:
        state = "correct" if answer == gold else "wrong"
    return {
        "attempt": attempt,
        "arm": item["arm"], "level": item["level"], "chains": item["chains"],
        "edges": item["edges"], "seed": item["seed"], "seed_hash": item["seed_hash"],
        "gold": gold, "pred": answer, "state": state,
        "error_class": err or None,
        "finish_reason": resp.get("finish_reason"),
        "prompt_tokens": resp.get("prompt_tokens", 0),
        "completion_tokens": total_tokens,
        "latency_s": round(latency, 3),
        "answer_char": offset,
        "est_answer_tokens": est_answer_tokens,
        "est_kind": est_kind,
        "response_reasoning_chars": len(reasoning),
        "prompt_sha256": hashlib.sha256(render_prompt(item).encode()).hexdigest()[:16],
        "prompt": sanitize(render_prompt(item)),
        "response_content": sanitize(content),
    }


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple:
    if n == 0:
        return 0.0, 0.0
    p = successes / n
    denom = 1.0 + z * z / n
    centre = p + z * z / (2 * n)
    span = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (centre - span) / denom, (centre + span) / denom


def place_dstar(rows: list) -> dict:
    """The round-8 trichotomy, unchanged. At 6 items per depth the Wilson 95%
    interval is wide: only 6/6 certifies maintained (lower bound 0.610 >= 0.60)
    and only 1/6 or worse certifies collapse (upper bound 0.564 < 0.60); anything
    between is inconclusive. Transport failures are carried separately and never
    count as answers either way."""
    floor = MAJORITY_FLOOR + MARGIN
    out = []
    for row in sorted(rows, key=lambda r: (r["arm"], r["k"])):
        n = row["n"]
        na = (row.get("no_answer", 0) / n) if n else 0.0
        lb, ub = wilson_interval(row["correct"], n)
        if n < MIN_CERTIFY:
            status = "descriptive"
        elif na > 0.5:
            status = "budget_limited"
        elif lb >= floor:
            status = "maintained"
        elif ub < floor:
            status = "collapsed"
        else:
            status = "inconclusive"
        out.append({"arm": row["arm"], "k": row["k"], "n": n,
                    "correct": row["correct"], "wrong": row.get("wrong", 0),
                    "no_answer": row.get("no_answer", 0),
                    "transport_failures": row.get("transport_failures", 0),
                    "accuracy": round(row["correct"] / n, 4) if n else 0.0,
                    "wilson_lb95": round(lb, 4), "wilson_ub95": round(ub, 4),
                    "no_answer_rate": round(na, 4), "status": status})
    arm_l = [r for r in out if r["arm"] == "L"]
    collapsed = [r["k"] for r in arm_l if r["status"] == "collapsed"]
    maintained = [r["k"] for r in arm_l if r["status"] == "maintained"]
    inconclusive = [r["k"] for r in arm_l if r["status"] == "inconclusive"]
    budget_limited = [r["k"] for r in arm_l if r["status"] == "budget_limited"]
    turnover = min(collapsed) if collapsed else None
    certified = [k for k in maintained if turnover is None or k < turnover]
    d_star = max(certified) if certified else None
    grid_max = max((r["k"] for r in arm_l), default=0)
    if turnover is None:
        report = (f"no collapsed depth within the declared grid (arm L k <= {grid_max}); "
                  f"d* >= {d_star}")
    else:
        report = f"d* = {d_star}, first collapsed depth at {turnover}"
    if inconclusive:
        report += f"; inconclusive depths {inconclusive}"
    if budget_limited:
        report += f"; budget-limited depths {budget_limited}"
    return {"d_star": d_star, "report": report, "turnover_at": turnover,
            "maintained_depths": maintained, "inconclusive_depths": inconclusive,
            "budget_limited_depths": budget_limited, "floor": floor,
            "min_certify_items": MIN_CERTIFY, "rows": out}


def replay_budget(records: list, budget: int) -> dict:
    """Offline replay against a fixed completion budget, using the answer position
    (completion_tokens for the separated-reasoning response shape, otherwise the
    character-proportional estimate). Transport-failure records are unanswerable at
    every budget by construction."""
    out = {"n": len(records), "answerable": 0, "correct": 0, "wrong": 0, "unanswerable": 0}
    for rec in records:
        pos = rec["est_answer_tokens"]
        if rec["state"] == "transport_failure" or pos < 0 or pos > budget:
            out["unanswerable"] += 1
            continue
        out["answerable"] += 1
        if rec["state"] == "correct":
            out["correct"] += 1
        elif rec["state"] == "wrong":
            out["wrong"] += 1
    out["accuracy_over_all"] = round(out["correct"] / out["n"], 4) if out["n"] else 0.0
    out["accuracy_over_answerable"] = (round(out["correct"] / out["answerable"], 4)
                                       if out["answerable"] else None)
    return out


def aggregate(records: list) -> dict:
    per: dict = {}
    for rec in records:
        key = (rec["arm"], rec["level"])
        row = per.setdefault(key, {"arm": rec["arm"], "k": rec["level"], "n": 0,
                                   "correct": 0, "wrong": 0, "no_answer": 0,
                                   "transport_failures": 0,
                                   "completion_tokens": [], "prompt_tokens": [],
                                   "est_answer_tokens": [], "latency_s": []})
        row["n"] += 1
        key = "transport_failures" if rec["state"] == "transport_failure" else rec["state"]
        row[key] += 1
        row["completion_tokens"].append(rec["completion_tokens"])
        row["prompt_tokens"].append(rec["prompt_tokens"])
        if rec["est_answer_tokens"] >= 0:
            row["est_answer_tokens"].append(rec["est_answer_tokens"])
        row["latency_s"].append(rec["latency_s"])
    rows = []
    for row in per.values():
        rows.append({"arm": row["arm"], "k": row["k"], "n": row["n"],
                     "correct": row["correct"], "wrong": row["wrong"],
                     "no_answer": row["no_answer"],
                     "transport_failures": row["transport_failures"],
                     "mean_completion_tokens": round(sum(row["completion_tokens"]) / row["n"], 1),
                     "mean_prompt_tokens": round(sum(row["prompt_tokens"]) / row["n"], 1),
                     "mean_est_answer_tokens": (round(sum(row["est_answer_tokens"])
                                                       / len(row["est_answer_tokens"]), 1)
                                                if row["est_answer_tokens"] else None),
                     "mean_latency_s": round(sum(row["latency_s"]) / row["n"], 1),
                     "p90_latency_s": round(sorted(row["latency_s"])[min(len(row["latency_s"]) - 1,
                                                                         int(round(0.9 * len(row["latency_s"]))))], 1)})
    d = place_dstar(rows)
    replay = {str(b): replay_budget(records, b) for b in BUDGETS}
    return {"records": len(records),
            "per_depth": sorted(rows, key=lambda r: (r["arm"], r["k"])),
            "d_star": d, "budget_replay": replay,
            "totals": {"correct": sum(1 for r in records if r["state"] == "correct"),
                       "wrong": sum(1 for r in records if r["state"] == "wrong"),
                       "no_answer": sum(1 for r in records if r["state"] == "no_answer"),
                       "transport_failures": sum(1 for r in records if r["state"] == "transport_failure")}}


def gate_report() -> dict:
    out = {"seed_base": SEED_BASE, "alpha": ALPHA, "perms": PERMS, "cells": []}
    total = 0
    for cell in all_cells():
        items = cell["items"]
        total += len(items)
        g = gate(cell["pool"])
        prompts = [render_prompt(it) for it in items]
        out["cells"].append({"arm": cell["arm"], "k": cell["k"], "chains": cell["chains"],
                             "edges": cell["k"] * cell["chains"],
                             "load": {"n": len(items),
                                      "facts_mean": round(sum(len(i["facts"]) for i in items) / len(items), 2),
                                      "prompt_chars_mean": round(sum(len(p) for p in prompts) / len(prompts), 1)},
                             "selected_seed_hashes": [it["seed_hash"] for it in items],
                             "gate": g})
    out["planned_prompts"] = total
    out["prompt_cap"] = PROMPT_CAP
    out["all_cells_pass"] = all(c["gate"]["verdict"] != "leak" for c in out["cells"])
    return out


def dispatch_item(item: dict, out_dir: str, raw_path: str) -> dict:
    """Sequential dispatch with per-item deadline and one retry (#73). The final
    attempt's record is appended to the incremental raw archive and fsynced, so a
    killed run still yields the record."""
    prompt = render_prompt(item)
    last = None
    for attempt in range(1, ATTEMPTS_PER_ITEM + 1):
        if last is not None and classify(last) == "":
            break
        t0 = time.monotonic()
        resp = call_endpoint(prompt, deadline_s=ITEM_DEADLINE_S)
        latency = time.monotonic() - t0
        last = resp
        if classify(resp) == "":
            break
    rec = score_record(item, last, latency, min(attempt, ATTEMPTS_PER_ITEM))
    with open(raw_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return rec


def existing_raw(raw_path: str) -> dict:
    if not os.path.exists(raw_path):
        return {}
    out = {}
    for line in open(raw_path, encoding="utf-8"):
        if line.strip():
            rec = json.loads(line)
            out[rec["seed_hash"]] = rec
    return out


def probe(out_dir: str, budget_s: int) -> int:
    cells = all_cells()
    gate_results = [gate(c["pool"]) for c in cells]
    for cell, g in zip(cells, gate_results):
        if g["verdict"] == "leak":
            print(f"REFUSED cell k={cell['k']} C={cell['chains']}: {g['flagged_rules'][:3]}",
                  file=sys.stderr)
            return 3
    plan = [(cell, item) for cell in cells for item in cell["items"]]
    if len(plan) > PROMPT_CAP:
        print(f"plan {len(plan)} exceeds cap {PROMPT_CAP}", file=sys.stderr)
        return 2
    os.makedirs(out_dir, exist_ok=True)
    raw_path = os.path.join(out_dir, "raw.jsonl")
    done = existing_raw(raw_path)

    # #73 requirement 1: health check immediately before the grid, in the same
    # firing. A failing health check refuses the whole arm.
    health = health_check()
    if not health["ok"]:
        record = {"arm_status": "failed_at_health_check", "health": health,
                  "note": "arm refused before the first grid prompt (issue #73 requirement 1)"}
        with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(json.dumps(record), file=sys.stderr)
        return 4
    print(f"health check ok: {health['latency_s']} s, {health['completion_tokens']} completion tokens")
    print(f"planned prompts: {len(plan)} (cap {PROMPT_CAP}), gate: all cells pass")

    started = time.monotonic()
    records: list = []
    arm_status = "completed"
    skipped = 0
    for cell, item in plan:
        if item["seed_hash"] in done:
            rec = done[item["seed_hash"]]
            records.append(rec)
            skipped += 1
            print(f"skip (already archived) k={rec['level']:>2} gold={rec['gold']:>3} "
                  f"{rec['state']}")
            continue
        if time.monotonic() - started > budget_s:
            arm_status = f"budget_exhausted_after_{len(records) - skipped}_new_records"
            print(f"arm wall-clock budget {budget_s} s reached; stopping after "
                  f"{len(records)} records (issue #73 requirement 3)", file=sys.stderr)
            break
        rec = dispatch_item(item, out_dir, raw_path)
        records.append(rec)
        print(f"k={rec['level']:>2} C={rec['chains']:>2} gold={rec['gold']:>3} "
              f"pred={str(rec['pred']):>4} {rec['state']:>15} "
              f"ctok={rec['completion_tokens']:>5} est={rec['est_answer_tokens']:>5} "
              f"lat={rec['latency_s']:>7.1f} a{rec['attempt']}")
    records.sort(key=lambda r: (r["arm"], r["level"], r["seed"]))
    summary = aggregate(records)
    summary["gate"] = [{"arm": c["arm"], "k": c["k"], "chains": c["chains"],
                        "verdict": g["verdict"],
                        "calibrated_threshold": g["calibrated_threshold"],
                        "observed_max": g["observed_max"], "p_value": g["p_value"],
                        "battery_rules": g["battery_rules"],
                        "constant_features": g["constant_features"]}
                       for c, g in zip(cells, gate_results)]
    summary["health"] = health
    summary["skipped_resumed"] = skipped
    summary["arm_status"] = arm_status
    summary["wall_seconds"] = round(time.monotonic() - started, 1)
    summary["budget_seconds"] = budget_s
    summary["item_deadline_s"] = ITEM_DEADLINE_S
    summary["dispatch"] = "sequential, one retry per item, incremental fsynced raw archive"
    summary["max_tokens"] = MAX_TOKENS
    summary["temperature"] = TEMPERATURE
    summary["seed_base"] = SEED_BASE
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(json.dumps({"totals": summary["totals"], "d_star": summary["d_star"]["report"],
                      "budget_replay": summary["budget_replay"],
                      "arm_status": arm_status}, indent=2))
    return 0 if arm_status == "completed" else 5


def replay(raw_path: str) -> int:
    records = [json.loads(line) for line in open(raw_path, encoding="utf-8") if line.strip()]
    print(json.dumps(aggregate(records), indent=2, sort_keys=True))
    return 0


def selftest() -> int:
    problems: list = []

    def check(label: str, cond: bool) -> None:
        print(f"  {label}: {'caught' if cond else 'MISSED'}")
        if not cond:
            problems.append(label)

    print("control 1: structural and solvability audit on all 8 cells")
    for (k, c_chains) in ARM_L + ARM_X:
        items, pool = build_cell(k, c_chains, 3, 6)
        assert len(pool) == CANDIDATES
        for it in items:
            assert not verify_item(it), verify_item(it)
            assert it["edges"] == k * c_chains
        yes = sum(1 for it in items if it["answer"] == "yes")
        check(f"cell k={k} C={c_chains} selection 3 yes", yes == 3)

    print("control 2: seed determinism (byte-identical stream; shifted seed differs)")
    a = "".join(json.dumps(i, sort_keys=True) for i in build_cell(4, 6, 3, 6)[0])
    b = "".join(json.dumps(i, sort_keys=True) for i in build_cell(4, 6, 3, 6)[0])
    c = "".join(json.dumps(gen_item(4, 6, cell_seed(4, 6, i) + 1000), sort_keys=True)
                for i in range(6))
    check("same seed byte-identical", a == b)
    check("shifted seed differs", a != c)

    print("control 3: constant load across arm L (exactly 24 facts, tight prompt spread)")
    edges = {it["edges"] for (k, cc) in ARM_L for it in build_cell(k, cc, 3, 6)[0]}
    check("all arm-L items have 24 facts", edges == {CONST_E})
    prompts = [render_prompt(it) for (k, cc) in ARM_L for it in build_cell(k, cc, 3, 6)[0]]
    lens = sorted(len(p) for p in prompts)
    check("prompt chars within 12% of the minimum", lens[-1] - lens[0] < 0.12 * lens[0])

    print("control 4: stream identity against round 8's published gate record")
    cells = all_cells()
    for cell, ref in zip(cells, ROUND8_GATE):
        g = gate(cell["pool"])
        prompts = [render_prompt(it) for it in cell["items"]]
        pmean = round(sum(len(p) for p in prompts) / len(prompts), 1)
        got = (cell["arm"], cell["k"], cell["chains"], g["battery_rules"],
               g["calibrated_threshold"], g["observed_max"], g["p_value"],
               g["gold_yes"], pmean)
        check(f"cell {ref[0]} k={ref[1]} matches round 8 (rules, threshold, obs, p, yes, load)",
              got == ref)

    print("control 5: gate arithmetic controls (constant rule at majority, perfect at 1.0)")
    items, pool6 = build_cell(6, 4, 3, 6)
    n = len(items)
    gold_bits = _bits([it["answer"] == "yes" for it in items])
    yes_n = sum(1 for it in items if it["answer"] == "yes")
    majority = max(yes_n, n - yes_n) / n
    check("constant rule scores the majority baseline",
          max(_acc((1 << n) - 1, gold_bits, n), _acc(0, gold_bits, n)) == majority)
    check("identity rule scores 1.0", _acc(gold_bits, gold_bits, n) == 1.0)

    print("control 6: planted leak (pure name-order, no traversal) must be flagged")
    planted = [dict(it) for it in pool6]
    for it in planted:
        qs, _, qt = it["query"]
        it["answer"] = "yes" if qt < qs else "no"
        it["chain_len"] = None
    gp = gate(planted)
    check("planted leak flagged", gp["verdict"] == "leak")
    check("planted rule named", any("tgt_name_lt_src_name" in r["rule"] for r in gp["top_rules"]))
    check("planted p below alpha", gp["p_value"] <= ALPHA)

    print("control 7: planted negative (shuffled labels) must not be flagged")
    shuffled = [dict(it) for it in pool6]
    rng = random.Random(99)
    labels = [it["answer"] for it in shuffled]
    rng.shuffle(labels)
    for it, lab in zip(shuffled, labels):
        it["answer"] = lab
        it["chain_len"] = None
    gs = gate(shuffled)
    check("shuffled labels not flagged", gs["verdict"] == "no leak at family-wise alpha")

    print("control 8: integrity controls (flipped stored answer, branching node)")
    broken = [dict(it) for it in items]
    broken[1]["answer"] = "no" if broken[1]["answer"] == "yes" else "yes"
    broken[1]["chain_len"] = None
    check("flipped answer caught by BFS", sum(1 for it in broken if any("BFS" in v for v in verify_item(it))) == 1)
    branch = [dict(it) for it in items]
    extra = branch[0]
    extra["facts"] = extra["facts"] + [[extra["query"][0], REL, "zzextra"]]
    check("branching node caught", any("branching" in v or "component" in v for v in verify_item(extra)))

    print("control 9: parser and sanitizer controls")
    check("last-token parse", parse_answer("The chain gives\nno") == ("no", 16))
    check("no answer token", parse_answer("maybe so") == (None, -1))
    check("empty content", parse_answer("") == (None, -1))
    check("last of several", parse_answer("yes. no, wait: yes") == ("yes", 15))
    check("case-insensitive", parse_answer("Final answer: NO") == ("no", 14))
    check("sanitizer redacts",
          sanitize("see http://example.invalid/x and 127.0.0.1 and /home/user/f.bin")
          == "see [REDACTED] and [REDACTED] and [REDACTED]")

    print("control 10: empty-completion path is a transport failure, not no_answer (#73)")
    item = items[0]
    empty = {"error": None, "content": "", "reasoning": "", "finish_reason": "stop",
             "prompt_tokens": 0, "completion_tokens": 0}
    rec_e = score_record(item, empty, 1.0, 1)
    check("empty completion classified transport_failure",
          rec_e["state"] == "transport_failure" and rec_e["error_class"] == "empty_completion")
    rec_t = score_record(item, {"error": "timeout", "content": "", "reasoning": "",
                                "finish_reason": None, "prompt_tokens": 0,
                                "completion_tokens": 0}, 600.0, 1)
    check("deadline timeout classified transport_failure",
          rec_t["state"] == "transport_failure" and rec_t["error_class"] == "timeout")
    agg = aggregate([rec_e, rec_t])
    check("transport failures excluded from no_answer totals",
          agg["totals"]["no_answer"] == 0 and agg["totals"]["transport_failures"] == 2)
    rep = replay_budget([rec_e], 2048)
    check("transport failure unanswerable at every budget", rep["unanswerable"] == 1)

    print("control 11: separated-reasoning response shape (round-8 finding)")
    ok_resp = {"error": None,
               "content": "no",
               "reasoning": "step one\nstep two",
               "finish_reason": "stop", "prompt_tokens": 400, "completion_tokens": 557}
    rec_ok = score_record(item, ok_resp, 61.2, 1)
    check("separated shape: est position is completion_tokens",
          rec_ok["est_answer_tokens"] == 557 and rec_ok["est_kind"] == "completion_tokens")
    check("separated shape scored on content only", rec_ok["pred"] == "no")
    # the round-8 invalid-estimate regression: a 557-token completion with a
    # one-token content must not estimate the answer at 1 token
    check("round-8 est_answer_tokens=1 regression gone", rec_ok["est_answer_tokens"] != 1)

    print("control 12: d* trichotomy controls (flat, turnover, budget cliff, descriptive X)")
    flat = [{"arm": "L", "k": k, "correct": 6, "n": 6, "no_answer": 0, "wrong": 0}
            for k in (2, 4, 8, 12)]
    r_flat = place_dstar(flat)
    check("flat grid: no turnover, d* = 12", r_flat["turnover_at"] is None and r_flat["d_star"] == 12)
    check("flat grid: all maintained", all(r["status"] == "maintained" for r in r_flat["rows"]))
    turn = [{"arm": "L", "k": k, "correct": c, "n": 6, "no_answer": 0, "wrong": 6 - c}
            for k, c in ((2, 6), (4, 5), (6, 4), (8, 1), (12, 0))]
    r_turn = place_dstar(turn)
    check("turnover at 8, d* = 2", r_turn["turnover_at"] == 8 and r_turn["d_star"] == 2)
    check("inconclusive at 4 and 6", r_turn["inconclusive_depths"] == [4, 6])
    cliff = [{"arm": "L", "k": k, "correct": 6 if k <= 6 else 0, "n": 6, "wrong": 0,
              "no_answer": 0 if k <= 6 else 6} for k in (2, 4, 6, 8, 12)]
    r_cliff = place_dstar(cliff)
    check("budget-limited at 8 and 12", r_cliff["budget_limited_depths"] == [8, 12])
    desc = [{"arm": "X", "k": k, "correct": 2, "n": 2, "no_answer": 0, "wrong": 0}
            for k in (16, 24)]
    r_desc = place_dstar(desc)
    check("arm X descriptive only, never sets d*",
          r_desc["d_star"] is None and all(r["status"] == "descriptive" for r in r_desc["rows"]))

    print("control 13: Wilson interval exact values at n = 6 (round-8 table)")
    check("6/6 lower bound 0.610", abs(wilson_interval(6, 6)[0] - 0.6101) < 0.001)
    check("1/6 upper bound 0.564", abs(wilson_interval(1, 6)[1] - 0.5644) < 0.001)

    print("control 14: budget replay controls")
    fake = [{"arm": "L", "level": 8, "state": "correct", "est_answer_tokens": 900,
             "completion_tokens": 900, "prompt_tokens": 400, "latency_s": 30.0},
            {"arm": "L", "level": 8, "state": "wrong", "est_answer_tokens": 1500,
             "completion_tokens": 1500, "prompt_tokens": 400, "latency_s": 45.0},
            {"arm": "L", "level": 8, "state": "no_answer", "est_answer_tokens": -1,
             "completion_tokens": 2048, "prompt_tokens": 400, "latency_s": 60.0}]
    rep = replay_budget(fake, 1024)
    check("replay at 1024: one answerable, one correct",
          rep["answerable"] == 1 and rep["correct"] == 1 and rep["unanswerable"] == 2)

    print("control 15: per-depth aggregation carries the transport-failure ledger")
    ans = items[0]["answer"]
    mixed = []
    for i in range(6):
        it = dict(items[0])
        it["seed_hash"] = f"deadbeef{i:04x}"
        it["seed"] = 9000 + i
        mixed.append(score_record(it, {"error": None, "content": ans, "reasoning": "r",
                                       "finish_reason": "stop", "prompt_tokens": 400,
                                       "completion_tokens": 100}, 30.0, 1))
    mixed[0] = score_record(items[0], {"error": "timeout", "content": "", "reasoning": "",
                                       "finish_reason": None, "prompt_tokens": 0,
                                       "completion_tokens": 0}, 600.0, 1)
    agg2 = aggregate(mixed)
    row = agg2["per_depth"][0]
    check("per-depth n=6 with one transport failure",
          row["n"] == 6 and row["transport_failures"] == 1 and row["correct"] == 5)
    check("per-depth latency stats present",
          row["mean_latency_s"] is not None and row["p90_latency_s"] is not None)

    if problems:
        print(f"\nSELFTEST FAIL: {len(problems)} control(s) not caught")
        for p in problems:
            print(f"  {p}")
        return 4
    print("\nSELFTEST PASS: all controls pass")
    return 0


def main(argv: list) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--gate", action="store_true")
    p.add_argument("--probe", action="store_true")
    p.add_argument("--replay", action="store_true")
    p.add_argument("--raw", default=None)
    p.add_argument("--out", default=None)
    p.add_argument("--out-dir", default=os.path.dirname(os.path.abspath(__file__)))
    p.add_argument("--budget-seconds", type=int, default=PROBE_BUDGET_S)
    args = p.parse_args(argv)
    here = os.path.dirname(os.path.abspath(__file__))
    if args.selftest:
        return selftest()
    if args.gate:
        blob = json.dumps(gate_report(), indent=2, sort_keys=True)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(blob + "\n")
        else:
            sys.stdout.write(blob + "\n")
        return 0
    if args.probe:
        return probe(args.out_dir, args.budget_seconds)
    if args.replay:
        return replay(args.raw or os.path.join(here, "raw.jsonl"))
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

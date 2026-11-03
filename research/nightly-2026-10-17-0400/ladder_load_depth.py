#!/usr/bin/env python3
"""Nightly round 8 (tracker #65, firing 2026-10-17 04:00): place the ladder depth
ceiling d* at constant prompt load, and separate the budget cliff from the depth cliff.

Question (issue #71 acceptance criteria 1, 2, 4, model-facing half): at a FIXED number
of facts, does hop-chain accuracy turn over as hop depth k grows, and is any turnover
a depth cliff or a token-budget cliff? Round 6 measured k in {1..16} with the shipped
generator, whose fact count E = C * k grows quadratically in k, so depth and prompt
load moved together and no turnover appeared. This round holds E constant and varies k
alone, which is the only variant that yields a depth axis the study can claim.

Independence: this file imports nothing from generators/ and re-implements the
component-isomorphic construction (issue #67 fix, PR #69, still unmerged), the BFS
solver, the structural verifier, the permutation-calibrated leak gate, the probe and
the scorer from scratch, with its own entity-name pools, so a shared bug cannot hide a
leak (docs/agent-execution.md section 5). The shipped corpus on main is not used.

Declared grid (fixed before any measurement, seed-frozen):
  arm L  constant load: E = 24 facts, k in {2,3,4,6,8,12}, C = 24/k chains
         6 items per depth (3 yes, 3 no) -> 36 prompts
  arm X  grid extension: C = 2 chains, k in {16,24}, E = 2k facts
         2 items per depth (1 yes, 1 no) -> 4 prompts
  total 40 prompts, max_tokens 2048, temperature 0.0, one sample per item.
Selection rule: candidates are generated in seed order; the first 3 yes and the first
3 no candidates that pass the structural audit are taken. Nothing is chosen after
seeing a model response. Every cell must pass the permutation-calibrated leak gate
before a single prompt is spent; a failing cell is refused (fail closed).

Budget replay is offline and free: each completion is replayed against fixed budgets
{256,512,1024,2048} using the answer position estimated as
completion_tokens * (answer_char / total_chars). The estimate is character-proportional
and approximate; it is reported as such and never as a measured token count.

d* procedure: Wilson 95% lower bound on per-depth accuracy; turnover at the first depth
whose lower bound falls below MAJORITY_FLOOR + MARGIN. A depth whose no-answer rate
exceeds 0.5 is reported as budget-limited, not depth-limited, and cannot set d*.

Usage:
  ladder_load_depth.py --selftest
  ladder_load_depth.py --gate            [--out FILE]
  ladder_load_depth.py --probe           [--out-dir DIR] [--max-workers 3]
  ladder_load_depth.py --replay          [--raw FILE]
"""
from __future__ import annotations

import argparse
import concurrent.futures
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

# Own name pools (deliberately different from generators/ladders.py).
POOL_A = ("ka", "ke", "ki", "ko", "ku", "la", "le", "li", "lo", "ma", "me", "mi",
          "mo", "na", "ne", "ni", "pa", "pe", "pi", "ra", "re", "ri", "sa", "se",
          "si", "ta", "te", "ti", "va", "ve", "vi", "za", "ze", "zi")
POOL_B = ("ben", "dan", "fen", "gan", "hen", "jin", "kol", "lan", "min", "nor",
          "pan", "qir", "ran", "sol", "tan", "vur", "wen", "yot", "zur")
POOL_C = ("dex", "mark", "pik", "rove", "skel", "thum", "vosh", "wick", "yarn")


def _name(rng: random.Random, taken: set) -> str:
    for _ in range(500):
        name = rng.choice(POOL_A) + rng.choice(POOL_B) + rng.choice(POOL_C)
        if name not in taken:
            taken.add(name)
            return name
    raise RuntimeError("name pool exhausted")


def gen_item(k: int, c_chains: int, seed: int) -> dict:
    """Component-isomorphic hop chain: C disjoint directed paths of exactly k edges
    over fresh entities; the query is always (head of one path, tail of one path);
    yes iff both endpoints lie on the same path."""
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
    """Selection rule fixed in advance: seed order, the first `want_yes` yes items and
    the first `want_total - want_yes` no items, each candidate passing the independent
    structural audit. Returns (selected, full candidate pool). The gate runs on the
    whole pool, never on the selected six: a gate over 6 items has no power, because a
    battery of ~100 rules reaches 100% accuracy on a random 6-item labeling (this is
    the small-n side of the issue #67 threshold critique)."""
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


def load_profile(items: list) -> dict:
    prompts = [render_prompt(it) for it in items]
    chars = [len(p) for p in prompts]
    return {"n": len(items), "facts_mean": round(sum(len(i["facts"]) for i in items) / len(items), 2),
            "prompt_chars_mean": round(sum(chars) / len(chars), 1)}


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
    return URL_RE.sub("[REDACTED]", text)


def parse_answer(content: str) -> tuple:
    """Declared parser: the LAST standalone yes/no token in the content field.
    Returns (answer or None, char offset of the match)."""
    matches = list(ANSWER_RE.finditer(content or ""))
    if not matches:
        return None, -1
    m = matches[-1]
    return m.group(1).lower(), m.start()


def gate_report() -> dict:
    out = {"seed_base": SEED_BASE, "alpha": ALPHA, "perms": PERMS, "cells": []}
    total = 0
    for cell in all_cells():
        items = cell["items"]
        total += len(items)
        g = gate(cell["pool"])
        out["cells"].append({"arm": cell["arm"], "k": cell["k"], "chains": cell["chains"],
                             "edges": cell["k"] * cell["chains"], "load": load_profile(items),
                             "gate": g})
    out["planned_prompts"] = total
    out["prompt_cap"] = PROMPT_CAP
    out["all_cells_pass"] = all(c["gate"]["verdict"] != "leak" for c in out["cells"])
    return out


def endpoint_url() -> str:
    base = os.environ.get("NIGHTLY_BASE_URL", "").strip().rstrip("/")
    if not base:
        raise SystemExit("NIGHTLY_BASE_URL is not set; the probe cannot run")
    return base + "/chat/completions"


def call_endpoint(prompt: str) -> dict:
    key = os.environ.get("NIGHTLY_API_KEY", "").strip()
    model = os.environ.get("NIGHTLY_MODEL_ID", "").strip()
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": MAX_TOKENS, "temperature": TEMPERATURE,
                       "stream": False}).encode()
    req = urllib.request.Request(endpoint_url(), data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {key}"})
    last_err = ""
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
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
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError,
                json.JSONDecodeError) as exc:
            last_err = f"{type(exc).__name__}"
            time.sleep(2.0 * (attempt + 1))
    return {"error": last_err, "content": "", "reasoning": "", "finish_reason": None,
            "prompt_tokens": 0, "completion_tokens": 0}


def score_record(item: dict, resp: dict) -> dict:
    answer, offset = parse_answer(resp["content"])
    gold = item["answer"]
    full = (resp.get("reasoning") or "") + (resp.get("content") or "")
    total_tokens = resp.get("completion_tokens") or 0
    est_answer_tokens = -1
    if offset >= 0 and full:
        est_answer_tokens = round(total_tokens * (offset + len(resp["content"])) / max(len(full), 1))
    state = "no_answer"
    if answer is not None:
        state = "correct" if answer == gold else "wrong"
    return {
        "arm": item["arm"], "level": item["level"], "chains": item["chains"],
        "edges": item["edges"], "seed": item["seed"], "seed_hash": item["seed_hash"],
        "gold": gold, "pred": answer, "state": state,
        "finish_reason": resp.get("finish_reason"), "error": resp.get("error"),
        "prompt_tokens": resp.get("prompt_tokens", 0),
        "completion_tokens": total_tokens,
        "answer_char": offset, "full_chars": len(full),
        "est_answer_tokens": est_answer_tokens,
        "prompt": sanitize(render_prompt(item)),
        "response_content": resp.get("content", ""),
        "response_reasoning_chars": len(resp.get("reasoning") or ""),
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
    """Declared d* procedure (issue #71 criterion 1), a trichotomy rather than a binary
    pass, because at ITEMS_PER_DEPTH = 6 the Wilson 95% interval is wide: only a perfect
    depth certifies maintained accuracy (6/6 gives a lower bound of 0.61) and only a
    depth at or below 1/6 certifies collapse (upper bound 0.56). Anything between is
    reported as inconclusive instead of being silently counted as a pass or a turnover.

    status per depth, in this order:
      budget_limited  no-answer rate > 0.5: the answer was never reached, so the depth
                      cannot say anything about depth and cannot set d*
      maintained      Wilson 95% lower bound >= MAJORITY_FLOOR + MARGIN
      collapsed       Wilson 95% upper bound < MAJORITY_FLOOR + MARGIN
      inconclusive    neither bound crosses the floor
      descriptive     n < MIN_CERTIFY items: reported, never used to set d*
    d* = the largest maintained arm-L depth below the first collapsed arm-L depth.
    """
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


def aggregate(records: list) -> dict:
    per: dict = {}
    for rec in records:
        key = (rec["arm"], rec["level"])
        row = per.setdefault(key, {"arm": rec["arm"], "k": rec["level"], "n": 0,
                                   "correct": 0, "wrong": 0, "no_answer": 0,
                                   "completion_tokens": [], "prompt_tokens": [],
                                   "est_answer_tokens": []})
        row["n"] += 1
        row[rec["state"] if rec["state"] in ("correct", "wrong", "no_answer") else "no_answer"] += 1
        row["completion_tokens"].append(rec["completion_tokens"])
        row["prompt_tokens"].append(rec["prompt_tokens"])
        if rec["est_answer_tokens"] >= 0:
            row["est_answer_tokens"].append(rec["est_answer_tokens"])
    rows = []
    for row in per.values():
        rows.append({"arm": row["arm"], "k": row["k"], "n": row["n"], "correct": row["correct"],
                     "wrong": row["wrong"], "no_answer": row["no_answer"],
                     "mean_completion_tokens": round(sum(row["completion_tokens"]) / row["n"], 1),
                     "mean_prompt_tokens": round(sum(row["prompt_tokens"]) / row["n"], 1),
                     "mean_est_answer_tokens": (round(sum(row["est_answer_tokens"])
                                                      / len(row["est_answer_tokens"]), 1)
                                                if row["est_answer_tokens"] else None)})
    d = place_dstar(rows)
    replay = {str(b): replay_budget(records, b) for b in BUDGETS}
    return {"records": len(records), "per_depth": sorted(rows, key=lambda r: (r["arm"], r["k"])),
            "d_star": d, "budget_replay": replay,
            "totals": {"correct": sum(1 for r in records if r["state"] == "correct"),
                       "wrong": sum(1 for r in records if r["state"] == "wrong"),
                       "no_answer": sum(1 for r in records if r["state"] == "no_answer"),
                       "errors": sum(1 for r in records if r.get("error"))}}


def replay_budget(records: list, budget: int) -> dict:
    """Offline replay: an item is answerable at this budget when the estimated answer
    position fits inside it. Character-proportional estimate, approximate."""
    out = {"n": len(records), "answerable": 0, "correct": 0, "wrong": 0, "unanswerable": 0}
    for rec in records:
        pos = rec["est_answer_tokens"]
        if pos < 0 or pos > budget:
            out["unanswerable"] += 1
            continue
        out["answerable"] += 1
        if rec["state"] == "correct":
            out["correct"] += 1
        else:
            out["wrong"] += 1
    out["accuracy_over_all"] = round(out["correct"] / out["n"], 4) if out["n"] else 0.0
    out["accuracy_over_answerable"] = (round(out["correct"] / out["answerable"], 4)
                                       if out["answerable"] else None)
    return out


def probe(out_dir: str, max_workers: int) -> int:
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
    print(f"planned prompts: {len(plan)} (cap {PROMPT_CAP}), gate: all cells pass")
    records: list = []
    started = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(call_endpoint, render_prompt(item)): (cell, item)
                   for (cell, item) in plan}
        for fut in concurrent.futures.as_completed(futures):
            cell, item = futures[fut]
            rec = score_record(item, fut.result())
            records.append(rec)
            print(f"k={rec['level']:>2} C={rec['chains']:>2} gold={rec['gold']:>3} "
                  f"pred={str(rec['pred']):>4} {rec['state']:>9} "
                  f"ctok={rec['completion_tokens']:>5} pos={rec['est_answer_tokens']:>5}")
    records.sort(key=lambda r: (r["arm"], r["level"], r["seed"]))
    summary = aggregate(records)
    summary["gate"] = [{"arm": c["arm"], "k": c["k"], "chains": c["chains"],
                        "verdict": g["verdict"], "calibrated_threshold": g["calibrated_threshold"],
                        "observed_max": g["observed_max"], "p_value": g["p_value"],
                        "constant_features": g["constant_features"]}
                       for c, g in zip(cells, gate_results)]
    summary["wall_seconds"] = round(time.time() - started, 1)
    summary["max_tokens"] = MAX_TOKENS
    summary["temperature"] = TEMPERATURE
    summary["seed_base"] = SEED_BASE
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "raw.jsonl"), "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(json.dumps({"totals": summary["totals"], "d_star": summary["d_star"]["report"],
                      "budget_replay": summary["budget_replay"]}, indent=2))
    return 0


def replay(raw_path: str) -> int:
    records = [json.loads(line) for line in open(raw_path, encoding="utf-8") if line.strip()]
    print(json.dumps(aggregate(records), indent=2, sort_keys=True))
    return 0


def selftest() -> None:
    # 1. structural and solvability audit on the fixed-chain construction
    for (k, c_chains) in ((2, 12), (4, 6), (8, 3), (12, 2), (16, 2), (24, 2)):
        items, pool = build_cell(k, c_chains, 3, 6)
        assert len(pool) == CANDIDATES
        for it in items:
            assert not verify_item(it), verify_item(it)
            assert it["edges"] == k * c_chains
        yes = sum(1 for it in items if it["answer"] == "yes")
        assert yes == 3, (k, c_chains, yes)

    # 2. determinism: same seed byte-identical, shifted seed different
    a = "".join(json.dumps(i, sort_keys=True) for i in build_cell(4, 6, 3, 6)[0])
    b = "".join(json.dumps(i, sort_keys=True) for i in build_cell(4, 6, 3, 6)[0])
    c = "".join(json.dumps(gen_item(4, 6, cell_seed(4, 6, i) + 1000), sort_keys=True)
                for i in range(6))
    assert a == b and a != c

    # 3. constant load across arm L: fact count is identical at every depth
    edges = {it["edges"] for (k, cc) in ARM_L for it in build_cell(k, cc, 3, 6)[0]}
    assert edges == {CONST_E}, edges
    prompts = [render_prompt(it) for (k, cc) in ARM_L for it in build_cell(k, cc, 3, 6)[0]]
    lens = sorted(len(p) for p in prompts)
    assert lens[-1] - lens[0] < 0.12 * lens[0], (lens[0], lens[-1])

    # 4. arithmetic controls on the gate battery
    items, pool6 = build_cell(6, 4, 3, 6)
    n = len(items)
    gold_bits = _bits([it["answer"] == "yes" for it in items])
    majority = max(sum(1 for it in items if it["answer"] == "yes"), n - 3) / n
    assert max(_acc((1 << n) - 1, gold_bits, n), _acc(0, gold_bits, n)) == majority
    assert _acc(gold_bits, gold_bits, n) == 1.0
    assert _acc(((1 << n) - 1) ^ gold_bits, gold_bits, n) == 0.0

    # 5. seeded defect (planted leak): relabel so gold == (target name < source name);
    #    the calibrated gate must flag it
    planted = [dict(it) for it in pool6]
    for it in planted:
        qs, _, qt = it["query"]
        it["answer"] = "yes" if qt < qs else "no"
        it["chain_len"] = None
    gp = gate(planted)
    assert gp["verdict"] == "leak", gp
    assert any("tgt_name_lt_src_name" in r["rule"] for r in gp["top_rules"]), gp["top_rules"]
    assert gp["p_value"] <= ALPHA, gp["p_value"]

    # 6. specificity control: shuffled labels must not be flagged as a leak
    shuffled = [dict(it) for it in pool6]
    rng = random.Random(99)
    labels = [it["answer"] for it in shuffled]
    rng.shuffle(labels)
    for it, lab in zip(shuffled, labels):
        it["answer"] = lab
        it["chain_len"] = None
    gs = gate(shuffled)
    assert gs["verdict"] == "no leak at family-wise alpha", gs

    # 7. every planned cell passes the gate (the fail-closed probe precondition)
    for cell in all_cells():
        g = gate(cell["pool"])
        assert g["verdict"] != "leak", (cell["k"], cell["chains"], g["flagged_rules"][:3])
        want_yes = YES_PER_DEPTH_L if cell["arm"] == "L" else YES_PER_DEPTH_X
        want_n = ITEMS_PER_DEPTH_L if cell["arm"] == "L" else ITEMS_PER_DEPTH_X
        yes_n = sum(1 for it in cell["items"] if it["answer"] == "yes")
        assert len(cell["items"]) == want_n and yes_n == want_yes, (cell["k"], yes_n)

    # 8. integrity controls: a flipped stored answer and a branching node are caught
    broken = [dict(it) for it in items]
    broken[1]["answer"] = "no" if broken[1]["answer"] == "yes" else "yes"
    broken[1]["chain_len"] = None
    assert sum(1 for it in broken if any("BFS" in v for v in verify_item(it))) == 1
    branch = [dict(it) for it in items]
    extra = branch[0]
    extra["facts"] = extra["facts"] + [[extra["query"][0], REL, "zzextra"]]
    assert any("branching" in v or "component" in v for v in verify_item(extra))

    # 9. parser controls: answer in content, answer absent, truncated content
    assert parse_answer("The chain gives\nno") == ("no", 16)
    assert parse_answer("maybe so") == (None, -1)
    assert parse_answer("") == (None, -1)
    assert parse_answer("yes. no, wait: yes") == ("yes", 15)
    assert parse_answer("Final answer: NO") == ("no", 14)
    assert sanitize("see http://example.invalid/x and 127.0.0.1 and /home/user/f.bin") == \
        "see [REDACTED] and [REDACTED] and [REDACTED]"

    # 10. d* controls: flat grid, turnover, budget cliff
    flat = [{"arm": "L", "k": k, "correct": 6, "n": 6, "no_answer": 0, "wrong": 0}
            for k in (2, 4, 8, 12)]
    r_flat = place_dstar(flat)
    assert r_flat["turnover_at"] is None and r_flat["d_star"] == 12, r_flat["report"]
    assert all(r["status"] == "maintained" for r in r_flat["rows"]), r_flat["rows"]
    # 6/6 certifies (lb 0.61 >= 0.60); 1/6 certifies collapse (ub 0.56 < 0.60);
    # 5/6, 4/6, 2/6 are inconclusive at n = 6 and must not be counted either way
    turn = [{"arm": "L", "k": k, "correct": c, "n": 6, "no_answer": 0, "wrong": 6 - c}
            for k, c in ((2, 6), (4, 5), (6, 4), (8, 1), (12, 0))]
    r_turn = place_dstar(turn)
    assert r_turn["turnover_at"] == 8 and r_turn["d_star"] == 2, r_turn["report"]
    assert r_turn["inconclusive_depths"] == [4, 6], r_turn["inconclusive_depths"]
    assert r_turn["maintained_depths"] == [2], r_turn["maintained_depths"]
    assert r_turn["budget_limited_depths"] == [], r_turn["budget_limited_depths"]
    cliff = [{"arm": "L", "k": k, "correct": 6 if k <= 6 else 0, "n": 6, "wrong": 0,
              "no_answer": 0 if k <= 6 else 6} for k in (2, 4, 6, 8, 12)]
    r_cliff = place_dstar(cliff)
    assert r_cliff["budget_limited_depths"] == [8, 12], r_cliff
    assert r_cliff["turnover_at"] is None and r_cliff["d_star"] == 6, r_cliff["report"]
    # arm X (2 items per depth) is descriptive only and can never set d*
    desc = [{"arm": "X", "k": k, "correct": 2, "n": 2, "no_answer": 0, "wrong": 0}
            for k in (16, 24)]
    r_desc = place_dstar(desc)
    assert r_desc["d_star"] is None and all(r["status"] == "descriptive" for r in r_desc["rows"])

    # 11. budget replay controls
    fake = [{"arm": "L", "level": 8, "state": "correct", "est_answer_tokens": 900},
            {"arm": "L", "level": 8, "state": "wrong", "est_answer_tokens": 1500},
            {"arm": "L", "level": 8, "state": "no_answer", "est_answer_tokens": -1}]
    rep = replay_budget(fake, 1024)
    assert rep["answerable"] == 1 and rep["correct"] == 1 and rep["unanswerable"] == 2, rep
    print("selftest passed")


def main(argv: list) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--gate", action="store_true")
    p.add_argument("--probe", action="store_true")
    p.add_argument("--replay", action="store_true")
    p.add_argument("--raw", default=None)
    p.add_argument("--out", default=None)
    p.add_argument("--out-dir", default=os.path.dirname(os.path.abspath(__file__)))
    p.add_argument("--max-workers", type=int, default=3)
    args = p.parse_args(argv)
    if args.selftest:
        selftest()
        return 0
    if args.gate:
        blob = json.dumps(gate_report(), indent=2, sort_keys=True)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(blob + "\n")
        else:
            sys.stdout.write(blob + "\n")
        return 0
    if args.probe:
        return probe(args.out_dir, args.max_workers)
    if args.replay:
        return replay(args.raw or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                               "raw.jsonl"))
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

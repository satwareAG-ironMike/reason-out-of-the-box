#!/usr/bin/env python3
"""Nightly research round 11 (2026-10-19, 02:00 slot).

Question: round 10 showed on a matched-pair probe (k = 4, 6, 8) that the probed
endpoint follows directed traversal, not undirected connectivity, and round 9
placed the constant-load depth ceiling at d* >= 12 on the same ladder family.
Does the traversal verdict replicate at depths k = 12, 16, 24, on items of the
same generator at levels beyond the shipped grid, on this round's endpoint?

Method: the matched-pair design of round 10, rebuilt on seed-generated items.
`generators/ladders.py` (this branch) generates 300 items per level at levels
12, 16, 24 from the public seed policy; gold labels are independently
re-derived by own BFS. Each selected item gets four arms:

  F1  (p_1, p_k)      forward interior      gold yes   k-1 hops
  R1  (p_k, p_1)      reverse interior      gold no    same component
  F2  (p_2, p_{k+1})  forward shifted       gold yes   k-1 hops
  X   (p_2, m)        cross-component       gold no    m matched by degree/name length

F1/R1 isolate direction; F2/X isolate component membership. The construction,
the invariant checks and the leak battery follow round 10
(research/nightly-2026-10-18-0400/matched_pair_probe.py, corrected revision).
Three round-10 verification findings are fixed here rather than copied:

1. the pool-corpus null bounds use the true support [|a+y-n|, n-|a-y|]
   (round-10 verification section 5);
2. both permutation nulls report one-sided and two-sided exact p values and
   the gate fires on the two-sided value against the Bonferroni bar
   (round-10 verification section 5);
3. the global prompt budget caps attempts, not just dispatches: health check
   plus dispatch plus retries can never exceed MAX_PROMPTS (round-10
   disclosure: 37 dispatched but up to 73 attempts).

Subcommands:
  --selftest  deterministic controls, no endpoint contact
  --gate      corpus verification, leak battery, exact nulls, gate.json
  --probe     the 36-prompt matched-pair probe against the live endpoint
  --analyze   read-only statistics over the archived raw responses

Stdlib only. Imports the canonical generator module for item construction and
independently re-derives every gold label. The endpoint is read from
NIGHTLY_BASE_URL / NIGHTLY_MODEL_ID / NIGHTLY_API_KEY and no endpoint value is
written to any artifact.
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures
import datetime
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))
LADDERS_PATH = os.path.join(REPO, "generators", "ladders.py")

SEED_BASE = 20261019
REL = "precedes"
RULE_SENTENCE = (
    f"Rule: for all x, y, z: if x {REL} y and y {REL} z, then x {REL} z. "
    "Facts state direct precedes links."
)
LEVELS = (12, 16, 24)
POOL_PER_LEVEL = 300
ITEMS_PER_LEVEL = 3
ARMS = ("F1", "R1", "F2", "X")
GOLD = {"F1": 1, "R1": 0, "F2": 1, "X": 0}

MAX_PROMPTS = 40
HEALTH_PROMPTS = 1
MAX_TOKENS = 2048
TEMPERATURE = 0.0
ITEM_DEADLINE_S = 900
CONCURRENCY = 4

GATE_ALPHA = 0.05
GATE_MIN_ACCURACY = 0.90

GATE_PATH = os.path.join(HERE, "gate.json")
RAW_PATH = os.path.join(HERE, "raw.jsonl")
SUMMARY_PATH = os.path.join(HERE, "summary.json")

ANSWER_RE = re.compile(r"\b(yes|no)\b", re.IGNORECASE)
URL_RE = re.compile(
    r"https?://\S+|\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|"
    r"(?:/[A-Za-z0-9_.-]+){2,}|[A-Za-z]:\\[^\s]*"
)
HEALTH_PROMPT = "Reply with exactly one word: yes"


# ---------------------------------------------------------------- utilities


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sanitize(text: str) -> str:
    return URL_RE.sub("[REDACTED]", text or "")


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple:
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    den = 1 + z * z / total
    centre = p + z * z / (2 * total)
    half = z * math.sqrt((p * (1 - p) / total) + z * z / (4 * total * total))
    return (max(0.0, (centre - half) / den), min(1.0, (centre + half) / den))


def log_choose(n: int, k: int) -> float:
    if k < 0 or k > n:
        return -math.inf
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar on the discordant pair counts."""
    n = b + c
    if n == 0:
        return 1.0
    lo = min(b, c)
    acc = 0.0
    for i in range(0, lo + 1):
        acc += math.exp(log_choose(n, i) - n * math.log(2.0))
    return min(1.0, 2.0 * acc)


# ------------------------------------------------- canonical item generator


def load_ladders():
    spec = importlib.util.spec_from_file_location("ladders_canonical",
                                                  LADDERS_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_pool() -> list:
    """The canonical generator's items at the declared levels, file order."""
    lad = load_ladders()
    pool = []
    for level in LEVELS:
        for rec in lad.generate_items(level, POOL_PER_LEVEL, SEED_BASE):
            rec["_level"] = level
            pool.append(rec)
    return pool


def pool_blob_sha256() -> dict:
    lad = load_ladders()
    out = {}
    for level in LEVELS:
        blob = "".join(lad.item_jsonl(i) + "\n"
                       for i in lad.generate_items(level, POOL_PER_LEVEL,
                                                   SEED_BASE))
        out[f"generated/l{level}.jsonl"] = hashlib.sha256(
            blob.encode("utf-8")).hexdigest()
    return out


# ---------------------------------------------------------------- graph tools


def graph_of(facts: list) -> tuple:
    out_deg = collections.defaultdict(int)
    in_deg = collections.defaultdict(int)
    adj = collections.defaultdict(list)
    und = collections.defaultdict(set)
    nodes = set()
    for src, _rel, dst in facts:
        out_deg[src] += 1
        in_deg[dst] += 1
        adj[src].append(dst)
        und[src].add(dst)
        und[dst].add(src)
        nodes.add(src)
        nodes.add(dst)
    for n in nodes:
        out_deg.setdefault(n, 0)
        in_deg.setdefault(n, 0)
    return adj, und, in_deg, out_deg, nodes


def components(nodes: set, und: dict) -> dict:
    comp = {}
    cid = 0
    for start in sorted(nodes):
        if start in comp:
            continue
        cid += 1
        stack = [start]
        while stack:
            node = stack.pop()
            if node in comp:
                continue
            comp[node] = cid
            stack.extend(und[node] - set(comp))
    return comp


def directed_reachable(src: str, dst: str, adj: dict) -> bool:
    if src == dst:
        return True
    stack = [src]
    seen = {src}
    while stack:
        node = stack.pop()
        if node == dst:
            return True
        for nxt in adj[node]:
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return False


def undirected_distance(a: str, b: str, und: dict) -> int:
    if a == b:
        return 0
    frontier = {a}
    seen = {a}
    dist = 0
    while frontier:
        dist += 1
        nxt = set()
        for node in frontier:
            for nb in und[node]:
                if nb == b:
                    return dist
                if nb not in seen:
                    seen.add(nb)
                    nxt.add(nb)
        frontier = nxt
    return -1


# ------------------------------------------------------------ pool validation


def verify_pool(recs: list) -> dict:
    """Independent recomputation of every generated gold label."""
    per_level = collections.OrderedDict()
    mismatches = []
    disagree = 0
    for rec in recs:
        adj, und, in_deg, out_deg, nodes = graph_of(rec["facts"])
        src, _rel, dst = rec["query"]
        reach = directed_reachable(src, dst, adj)
        comp = components(nodes, und)
        same = comp.get(src) == comp.get(dst)
        gold = 1 if rec["answer"] == "yes" else 0
        if int(reach) != gold:
            mismatches.append({"level": rec["_level"], "seed": rec["seed"]})
        if int(same) != int(reach):
            disagree += 1
        bucket = per_level.setdefault(
            rec["_level"],
            {"items": 0, "gold_yes": 0, "gold_no": 0, "reach_mismatch": 0,
             "component_reach_disagree": 0, "facts_min": 10**9,
             "facts_max": 0},
        )
        bucket["items"] += 1
        bucket["gold_yes"] += gold
        bucket["gold_no"] += 1 - gold
        bucket["reach_mismatch"] += int(int(reach) != gold)
        bucket["component_reach_disagree"] += int(int(same) != int(reach))
        bucket["facts_min"] = min(bucket["facts_min"], len(rec["facts"]))
        bucket["facts_max"] = max(bucket["facts_max"], len(rec["facts"]))
    return {
        "levels": {str(k): v for k, v in per_level.items()},
        "items_total": len(recs),
        "gold_reach_mismatches": mismatches,
        "cells_where_connectivity_and_reachability_disagree": disagree,
    }


# ------------------------------------------------- matched-pair construction


def chain_path(rec: list):
    """The directed chain the generated gold-yes query witnesses.

    Returns the node list p_1 .. p_{k+1} or None when the item is not usable:
    the query must be reachable, the path simple, every node on it of
    in-degree <= 1 and out-degree <= 1, and the item must contain a second
    component with a terminal node (in-degree 1, out-degree 0) whose name
    length equals the chain terminal's. Same rule as round 10.
    """
    facts = rec["facts"]
    adj, und, in_deg, out_deg, nodes = graph_of(facts)
    if rec["answer"] != "yes":
        return None
    src, _rel, dst = rec["query"]
    if not directed_reachable(src, dst, adj):
        return None
    path = [src]
    while path[-1] != dst:
        nxts = adj[path[-1]]
        if len(nxts) != 1:
            return None
        if nxts[0] in path:
            return None
        path.append(nxts[0])
        if len(path) > len(nodes) + 1:
            return None
    k = len(path) - 1
    if k < 4:
        return None
    for node in path:
        if in_deg[node] > 1 or out_deg[node] > 1:
            return None
    comp = components(nodes, und)
    main = comp[path[0]]
    target_len = len(path[k])
    cands = [n for n in sorted(nodes)
             if comp[n] != main and in_deg[n] == 1 and out_deg[n] == 0
             and len(n) == target_len]
    if not cands:
        return None
    return {"path": path, "k": k, "cross_target": cands[0],
            "components": len(set(comp.values()))}


def render_prompt(facts: list, src: str, dst: str) -> str:
    lines = [RULE_SENTENCE]
    lines += [f"Fact {i + 1}: {s} {r} {t}."
              for i, (s, r, t) in enumerate(facts)]
    lines.append(f"Question: does {src} {REL} {dst}? "
                 "Answer with exactly one word: yes or no.")
    return "\n".join(lines)


def build_matched_items() -> list:
    """Deterministic selection: first N usable items per level, in generated
    file order. The selection rule is fixed before any prompt is written."""
    recs = load_pool()
    items = []
    scanned = {}
    for level in LEVELS:
        picked = 0
        seen = 0
        for rec in recs:
            if rec["_level"] != level:
                continue
            seen += 1
            info = chain_path(rec)
            if info is None:
                continue
            path, k = info["path"], info["k"]
            arms = {
                "F1": (path[0], path[k - 1]),
                "R1": (path[k - 1], path[0]),
                "F2": (path[1], path[k]),
                "X": (path[1], info["cross_target"]),
            }
            prompts = {arm: render_prompt(rec["facts"], src, dst)
                       for arm, (src, dst) in arms.items()}
            if len({len(prompts["F1"]), len(prompts["R1"])}) != 1 \
                    or len({len(prompts["F2"]), len(prompts["X"])}) != 1:
                raise SystemExit(
                    "matched-pair prompt lengths differ within a family: "
                    f"{ {a: len(p) for a, p in prompts.items()} }")
            items.append({
                "item_id": f"L{level}-{picked + 1}",
                "level": level,
                "seed": rec["seed"],
                "seed_hash": rec["seed_hash"],
                "chain_len": k,
                "fact_count": len(rec["facts"]),
                "component_count": info["components"],
                "path": path,
                "arms": {arm: {"src": src, "dst": dst, "gold": GOLD[arm],
                               "prompt": prompts[arm],
                               "prompt_sha256": sha256_text(prompts[arm]),
                               "prompt_chars": len(prompts[arm])}
                         for arm, (src, dst) in arms.items()},
                "facts": rec["facts"],
            })
            picked += 1
            if picked >= ITEMS_PER_LEVEL:
                break
        scanned[level] = {"scanned": seen, "selected": picked}
    if len(items) != len(LEVELS) * ITEMS_PER_LEVEL:
        raise SystemExit(f"selection rule starved: {len(items)} items")
    return items


def fingerprint_of(items: list) -> list:
    """Seed-deterministic identity of the matched corpus, prompts excluded."""
    return [{"item_id": i["item_id"], "level": i["level"], "seed": i["seed"],
             "seed_hash": i["seed_hash"], "chain_len": i["chain_len"],
             "fact_count": i["fact_count"], "component_count": i["component_count"],
             "arms": {a: {k: v for k, v in i["arms"][a].items() if k != "prompt"}
                      for a in ARMS}} for i in items]


def matched_invariant(items: list) -> dict:
    """Every family matched on fact count, name multiset, prompt length and
    endpoint degree profile. Violations are fatal, not reported results."""
    violations = []
    for item in items:
        adj, und, in_deg, out_deg, _nodes = graph_of(item["facts"])
        comp = components(_nodes, und)
        for family, arms in (("direction", ("F1", "R1")),
                             ("component", ("F2", "X"))):
            a, b = arms
            pa, pb = item["arms"][a], item["arms"][b]
            names_a = sorted([pa["src"], pa["dst"]])
            names_b = sorted([pb["src"], pb["dst"]])
            deg_a = sorted([(in_deg[n], out_deg[n]) for n in names_a])
            deg_b = sorted([(in_deg[n], out_deg[n]) for n in names_b])
            undist_a = undirected_distance(pa["src"], pa["dst"], und)
            undist_b = undirected_distance(pb["src"], pb["dst"], und)
            common = [
                ("prompt_length", pa["prompt_chars"] == pb["prompt_chars"]),
                ("endpoint_name_lengths",
                 sorted(len(n) for n in names_a)
                 == sorted(len(n) for n in names_b)),
                ("degree_profile", deg_a == deg_b),
                ("gold_balance", pa["gold"] != pb["gold"]),
            ]
            if family == "direction":
                checks = common + [
                    ("name_multiset", names_a == names_b),
                    ("undirected_distance", undist_a == undist_b),
                    ("same_component_pair",
                     int(comp[pa["src"]] == comp[pa["dst"]])
                     == int(comp[pb["src"]] == comp[pb["dst"]])),
                ]
            else:
                checks = common + [
                    ("shared_endpoint", bool(set(names_a) & set(names_b))),
                    ("distinct_other_endpoint",
                     bool(set(names_a) ^ set(names_b))),
                    ("connectivity_differs",
                     int(comp[pa["src"]] == comp[pa["dst"]])
                     != int(comp[pb["src"]] == comp[pb["dst"]])),
                    ("terminal_degree_match",
                     out_deg[pb["dst"]] == 0 and out_deg[pa["dst"]] == 0),
                ]
            for name, ok in checks:
                if not ok:
                    violations.append({"item": item["item_id"],
                                       "family": family, "check": name})
        for arm in ARMS:
            pa = item["arms"][arm]
            reach = directed_reachable(pa["src"], pa["dst"], adj)
            if int(reach) != pa["gold"]:
                violations.append({"item": item["item_id"], "arm": arm,
                                   "check": "gold_vs_recomputed_reachability"})
            same = comp.get(pa["src"]) == comp.get(pa["dst"])
            pa["same_component"] = int(same)
            pa["directed_reach"] = int(reach)
            pa["undirected_hops"] = undirected_distance(pa["src"], pa["dst"],
                                                        und)
    return {"violations": violations, "items": len(items),
            "cells": len(items) * len(ARMS)}


# --------------------------------------------------------------- leak battery


def mention_order(facts: list) -> dict:
    first = {}
    last = {}
    for idx, (src, _rel, dst) in enumerate(facts):
        first.setdefault(src, idx)
        first.setdefault(dst, idx)
        last[src] = idx
        last[dst] = idx
    return {"first": first, "last": last}


def battery_predictions(rule: str, item: dict, arm: str) -> int:
    facts = item["facts"]
    a = item["arms"][arm]
    src, dst = a["src"], a["dst"]
    adj, und, in_deg, out_deg, nodes = graph_of(facts)
    comp = components(nodes, und)
    mo = mention_order(facts)
    if rule == "all_yes":
        return 1
    if rule == "all_no":
        return 0
    if rule == "same_component":
        return int(comp.get(src) == comp.get(dst))
    if rule == "name_first_mention_order":
        return int(mo["first"].get(src, 10**9) < mo["first"].get(dst, 10**9))
    if rule == "name_last_mention_order":
        return int(mo["last"].get(src, 10**9) < mo["last"].get(dst, 10**9))
    if rule == "name_alphabetical_order":
        return int(src < dst)
    if rule == "source_is_first_fact_source":
        return int(src == facts[0][0])
    if rule == "target_is_fact_target":
        return int(dst in {t for _s, _r, t in facts})
    if rule == "source_is_fact_source":
        return int(src in {s for s, _r, _t in facts})
    if rule == "endpoint_in_degree_zero":
        return int(in_deg[src] == 0 or in_deg[dst] == 0)
    if rule == "endpoint_out_degree_zero":
        return int(out_deg[src] == 0 or out_deg[dst] == 0)
    if rule == "undirected_connectivity_only":
        return int(undirected_distance(src, dst, und) >= 0)
    if rule == "fact_count_threshold":
        return int(len(facts) >= 9)
    if rule == "chain_len_matches_level":
        return int(item.get("chain_len") == item.get("level"))
    if rule == "relation_word_copy":
        return int(REL in f"{src} {dst}")
    if rule == "directed_reachability":
        return int(directed_reachable(src, dst, adj))
    if rule == "chain_position_order":
        path = item.get("path") or []
        if src in path and dst in path:
            return int(path.index(src) < path.index(dst))
        return 0
    raise KeyError(rule)


# Direction-blind heuristics: none orders two nodes along a directed chain.
LEAK_RULES = (
    "all_yes", "all_no", "same_component", "name_first_mention_order",
    "name_last_mention_order", "name_alphabetical_order",
    "source_is_first_fact_source", "target_is_fact_target",
    "source_is_fact_source", "endpoint_in_degree_zero",
    "endpoint_out_degree_zero", "undirected_connectivity_only",
    "fact_count_threshold", "chain_len_matches_level", "relation_word_copy",
)
# Competent references, excluded from the blind battery.
REFERENCE_RULES = ("directed_reachability", "chain_position_order")


def battery_on_matched(items: list) -> dict:
    rows = {}
    for rule in LEAK_RULES + REFERENCE_RULES:
        correct = 0
        per_item = []
        for item in items:
            hits = 0
            for arm in ARMS:
                pred = battery_predictions(rule, item, arm)
                hits += int(pred == item["arms"][arm]["gold"])
            per_item.append(hits)
            correct += hits
        total = len(items) * len(ARMS)
        rows[rule] = {"correct": correct, "cells": total,
                      "accuracy": correct / total, "per_item": per_item}
    return rows


def battery_on_pool(recs: list) -> dict:
    cached = []
    for rec in recs:
        info = chain_path(rec)
        cached.append({
            "facts": rec["facts"], "level": rec["_level"],
            "chain_len": rec.get("chain_len"),
            "path": (info or {}).get("path") or [],
            "arms": {"F1": {"src": rec["query"][0], "dst": rec["query"][2],
                            "gold": 1 if rec["answer"] == "yes" else 0}},
        })
    rows = {}
    for rule in LEAK_RULES + REFERENCE_RULES:
        correct = 0
        predictions = []
        for item in cached:
            pred = battery_predictions(rule, item, "F1")
            predictions.append(pred)
            correct += int(pred == item["arms"]["F1"]["gold"])
        rows[rule] = {"correct": correct, "cells": len(cached),
                      "accuracy": correct / len(cached),
                      "predictions": predictions}
    return rows


# ------------------------------------------------------------------ exact nulls


def exact_null_matched(rule: str, items: list, observed: int) -> dict:
    """Exact null for per-item gold-label shuffling on the matched corpus.

    Within one item the four arm labels are permuted uniformly at random. For
    a rule predicting 1 on `a` of the n cells and an item holding y gold-yes
    cells, matches = 2H + n - y - a with H ~ Hypergeometric(n, y, a). The
    total distribution is the exact convolution. Both tails reported; the
    two-sided value is double the smaller tail, capped at 1.
    """
    dist = {0: 1.0}
    mean = 0.0
    var = 0.0
    for item in items:
        n = len(ARMS)
        y = sum(item["arms"][a]["gold"] for a in ARMS)
        a = sum(battery_predictions(rule, item, arm) for arm in ARMS)
        lo = max(0, a - (n - y))
        hi = min(y, a)
        denom = log_choose(n, a)
        pdist = {}
        for h in range(lo, hi + 1):
            p = math.exp(log_choose(y, h) + log_choose(n - y, a - h) - denom)
            matches = 2 * h + n - y - a
            pdist[matches] = pdist.get(matches, 0.0) + p
        e1 = sum(k * v for k, v in pdist.items())
        e2 = sum(k * k * v for k, v in pdist.items())
        mean += e1
        var += e2 - e1 * e1
        ndist = {}
        for base, pb in dist.items():
            for add, pa in pdist.items():
                ndist[base + add] = ndist.get(base + add, 0.0) + pb * pa
        dist = ndist
    p_upper = sum(v for k, v in dist.items() if k >= observed)
    p_lower = sum(v for k, v in dist.items() if k <= observed)
    p_two = min(1.0, 2.0 * min(p_upper, p_lower))
    return {"null_mean": round(mean, 6), "null_sd": round(math.sqrt(var), 6),
            "null_min_hits": min(dist), "null_max_hits": max(dist),
            "observed_hits": observed,
            "p_one_sided_upper": float(f"{p_upper:.3e}"),
            "p_two_sided": float(f"{p_two:.3e}"),
            "z_observed": round((observed - mean) / math.sqrt(var), 4)
            if var > 0 else None}


def exact_null_pool(rule: str, recs: list, predictions) -> dict:
    """Exact null for a global gold-label shuffle over the generated pool.

    Per-item shuffling is degenerate (one queried pair per item), so gold
    labels are shuffled across the pool preserving the pool gold-yes count.
    Hits = 2K + n - y - a with K ~ Hypergeometric(n, y, a). Support of hits
    over K in [max(0, a + y - n), min(a, y)] is [|a+y-n|, n-|a-y|]: the
    round-10 defect used the naive intersection bounds and is fixed here.
    Both tails reported.
    """
    n = len(recs)
    y = sum(1 for r in recs if r["answer"] == "yes")
    a = sum(predictions)
    observed = sum(1 for rec, pred in zip(recs, predictions)
                   if pred == (1 if rec["answer"] == "yes" else 0))
    lo_k = max(0, a + y - n)
    hi_k = min(a, y)
    total = log_choose(n, a)
    k_of = lambda hits: (hits - n + y + a) / 2.0
    k_obs = int(math.ceil(k_of(observed)))
    mean = (a * y + (n - a) * (n - y)) / n
    if a == 0 or a == n or y == 0 or y == n:
        sd = 0.0
        p_upper = 1.0 if observed >= mean else 0.0
        p_lower = 1.0 if observed <= mean else 0.0
    else:
        p_upper = 0.0
        p_lower = 0.0
        for kk in range(lo_k, hi_k + 1):
            pk = math.exp(log_choose(y, kk) + log_choose(n - y, a - kk) - total)
            if kk >= k_obs:
                p_upper += pk
            if kk <= k_obs:
                p_lower += pk
        var_h = a * (y / n) * (1 - y / n) * ((n - a) / (n - 1))
        sd = 2 * math.sqrt(var_h)
    p_two = min(1.0, 2.0 * min(p_upper, p_lower))
    return {"null_mean": round(mean, 6), "null_sd": round(sd, 6),
            "null_min_hits": abs(a + y - n), "null_max_hits": n - abs(a - y),
            "observed_hits": observed, "rule_yes_cells": a,
            "gold_yes_cells": y,
            "p_one_sided_upper": float(f"{min(1.0, p_upper):.3e}"),
            "p_two_sided": float(f"{p_two:.3e}"),
            "z_observed": round((observed - mean) / sd, 4) if sd > 0 else None}


# --------------------------------------------------------------------- gate


def build_gate() -> dict:
    recs = load_pool()
    pool = verify_pool(recs)
    items = build_matched_items()
    invariant = matched_invariant(items)
    if invariant["violations"]:
        raise SystemExit(f"matched-pair invariant violated: {invariant['violations']}")
    pool_batt = battery_on_pool(recs)
    match_batt = battery_on_matched(items)
    bonf = GATE_ALPHA / len(LEAK_RULES)
    rows = []
    for rule in LEAK_RULES:
        s = pool_batt[rule]
        m = match_batt[rule]
        sn = exact_null_pool(rule, recs, s["predictions"])
        mn = exact_null_matched(rule, items, m["correct"])
        rows.append({
            "rule": rule,
            "pool_accuracy": round(s["accuracy"], 10),
            "pool_p_two_sided": sn["p_two_sided"],
            "pool_p_one_sided_upper": sn["p_one_sided_upper"],
            "pool_null": sn,
            "matched_accuracy": round(m["accuracy"], 10),
            "matched_p_two_sided": mn["p_two_sided"],
            "matched_p_one_sided_upper": mn["p_one_sided_upper"],
            "matched_null": mn,
            "fires_pool": bool(sn["p_two_sided"] <= bonf
                               and s["accuracy"] >= GATE_MIN_ACCURACY),
            "fires_matched": bool(mn["p_two_sided"] <= bonf
                                  and m["accuracy"] >= GATE_MIN_ACCURACY),
        })
    disagree_pool = pool["cells_where_connectivity_and_reachability_disagree"]
    disagree_matched = sum(
        1 for item in items for arm in ARMS
        if item["arms"][arm]["same_component"] != item["arms"][arm]["directed_reach"])
    return {
        "schema": "round11-gate-v3",
        "seed_base": SEED_BASE,
        "gate_hash": None,
        "alpha": GATE_ALPHA,
        "bonferroni_alpha": round(bonf, 12),
        "min_accuracy": GATE_MIN_ACCURACY,
        "null_model": {
            "tail_note": "firing uses the two-sided exact p value against the "
                         "Bonferroni bar; round 10 fired on the one-sided tail "
                         "(verification section 5); both tails are recorded",
            "pool": "global gold-label shuffle preserving the pool gold-yes "
                    "count; per-item shuffling is degenerate because each "
                    "pool item carries exactly one queried pair",
            "matched": "per-item gold-label shuffle preserving the per-item "
                       "gold-yes count; exact convolution, no Monte Carlo",
        },
        "item_source": {
            "generator": "generators/ladders.py",
            "generator_sha256": sha256_file(LADDERS_PATH),
            "generate_items": {f"level {lvl}": f"count {POOL_PER_LEVEL}, "
                              f"seed_base {SEED_BASE}" for lvl in LEVELS},
            "blob_sha256": pool_blob_sha256(),
        },
        "pool_corpus": {
            "items": pool["items_total"],
            "levels": pool["levels"],
            "gold_reach_mismatches": pool["gold_reach_mismatches"],
            "cells_where_connectivity_and_reachability_disagree": disagree_pool,
        },
        "matched_corpus": {
            "items": invariant["items"],
            "cells": invariant["cells"],
            "levels": list(LEVELS),
            "arms": list(ARMS),
            "invariant_violations": invariant["violations"],
            "cells_where_connectivity_and_reachability_disagree": disagree_matched,
        },
        "reference_rules": [
            {"rule": rule,
             "pool_accuracy": round(pool_batt[rule]["accuracy"], 10),
             "matched_accuracy": round(match_batt[rule]["accuracy"], 10)}
            for rule in REFERENCE_RULES
        ],
        "blind_rule_count": len(LEAK_RULES),
        "reference_rule_count": len(REFERENCE_RULES),
        "discrimination": {
            "definition": "a corpus is discriminating when no direction-blind "
                          "rule in the battery both beats its exact "
                          "label-shuffle null (two-sided, Bonferroni) and "
                          "reaches the accuracy bar",
            "max_blind_accuracy_pool": max(r["pool_accuracy"] for r in rows),
            "max_blind_accuracy_matched": max(r["matched_accuracy"] for r in rows),
            "rules_firing_pool": [r["rule"] for r in rows if r["fires_pool"]],
            "rules_firing_matched": [r["rule"] for r in rows if r["fires_matched"]],
            "pool_discriminating": max(r["pool_accuracy"] for r in rows)
                                   < GATE_MIN_ACCURACY,
            "matched_discriminating": max(r["matched_accuracy"] for r in rows)
                                      < GATE_MIN_ACCURACY,
            "note": "the accuracy bar is the load-bearing criterion; a "
                    "direction-blind rule can beat the label-shuffle null on "
                    "the matched corpus while still missing the bar",
        },
        "rules": rows,
        "selection_rule": {
            "levels": list(LEVELS),
            "pool_per_level": POOL_PER_LEVEL,
            "items_per_level": ITEMS_PER_LEVEL,
            "order": "generated file order, first usable items per level",
            "usable": "gold-yes query witnessed by a simple in-degree<=1 "
                      "out-degree<=1 chain of length >= 4, plus a second "
                      "component holding a terminal node (in-degree 1, "
                      "out-degree 0) whose name length equals the chain "
                      "terminal",
        },
        "probe_budget": {
            "max_prompts": MAX_PROMPTS,
            "health_prompts": HEALTH_PROMPTS,
            "dispatch_prompts": len(items) * len(ARMS),
            "attempt_cap_total": MAX_PROMPTS,
            "max_tokens": MAX_TOKENS,
            "temperature": TEMPERATURE,
            "item_deadline_s": ITEM_DEADLINE_S,
            "concurrency": CONCURRENCY,
            "retries": "one retry per arm, global attempt cap enforced",
        },
        "primary_statistic": {
            "test": "two-sided exact McNemar on the matched (F1, R1) pairs",
            "secondary": "two-sided exact McNemar on the matched (F2, X) pairs",
            "unit": "item",
            "n_pairs": len(items),
        },
    }


def gate_seed_hash(gate: dict) -> str:
    body = dict(gate)
    body.pop("gate_hash", None)
    return sha256_text(canonical(body))


# ---------------------------------------------------------------- transport


def endpoint_url() -> str:
    base = os.environ.get("NIGHTLY_BASE_URL", "").strip().rstrip("/")
    if not base:
        raise SystemExit("NIGHTLY_BASE_URL is not set; the probe cannot run")
    return base + "/chat/completions"


def call_endpoint(prompt: str, deadline_s: int) -> dict:
    key = os.environ.get("NIGHTLY_API_KEY", "").strip()
    model = os.environ.get("NIGHTLY_MODEL_ID", "").strip()
    body = json.dumps({"model": model,
                       "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": MAX_TOKENS, "temperature": TEMPERATURE,
                       "stream": False}).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(endpoint_url(), data=body, method="POST",
                                 headers=headers)
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
    except (urllib.error.URLError, TimeoutError, OSError,
            json.JSONDecodeError) as exc:
        return {"error": type(exc).__name__, "content": "", "reasoning": "",
                "finish_reason": None, "prompt_tokens": 0, "completion_tokens": 0}


def classify(resp: dict) -> str:
    if resp.get("error"):
        return resp["error"]
    if resp["completion_tokens"] == 0:
        return "empty_completion"
    return ""


def parse_answer(content: str, reasoning: str) -> tuple:
    """Declared parser: the LAST standalone yes/no token in the content field;
    if content carries none, fall back to the last yes/no token in the
    reasoning field and mark the source. Returns (answer, source, offset)."""
    matches = list(ANSWER_RE.finditer(content or ""))
    if matches:
        m = matches[-1]
        return m.group(1).lower(), "content", m.start()
    matches = list(ANSWER_RE.finditer(reasoning or ""))
    if matches:
        m = matches[-1]
        return m.group(1).lower(), "reasoning", m.start()
    return None, "none", -1


def health_check() -> dict:
    t0 = time.monotonic()
    resp = call_endpoint(HEALTH_PROMPT, deadline_s=180)
    latency = round(time.monotonic() - t0, 3)
    cls = classify(resp)
    ans, _src, _off = parse_answer(resp["content"], resp["reasoning"])
    return {"ok": (not cls) and ans is not None, "error_class": cls or None,
            "latency_s": latency, "completion_tokens": resp["completion_tokens"],
            "prompt_tokens": resp["prompt_tokens"],
            "started_at": now_iso(), "finished_at": now_iso()}


# -------------------------------------------------------------------- probe


class AttemptBudget:
    """Hard cap on total endpoint calls for the whole run (#73 lesson):
    health check + dispatch + retries can never exceed MAX_PROMPTS."""

    def __init__(self, cap: int):
        self.cap = cap
        self.lock = threading.Lock()
        self.used = 0

    def acquire(self) -> bool:
        with self.lock:
            if self.used >= self.cap:
                return False
            self.used += 1
            return True


def dispatch(items: list, gate: dict, budget: AttemptBudget) -> list:
    total_cells = len(items) * len(ARMS)
    if total_cells + HEALTH_PROMPTS > MAX_PROMPTS:
        raise SystemExit(f"dispatch budget exceeded: {total_cells}")
    done = {}
    if os.path.exists(RAW_PATH):
        with open(RAW_PATH, "r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("gate_hash") != gate["gate_hash"]:
                    raise SystemExit("raw.jsonl was written under a different gate")
                done[(rec["item_id"], rec["arm"])] = rec
                budget.used += len(rec["attempts"])
    jobs = [(item, arm) for item in items for arm in ARMS
            if (item["item_id"], arm) not in done]
    if done:
        print(f"resuming: {len(done)} cells already recorded, {len(jobs)} to go")
    results = dict(done)
    raw_lock = threading.Lock()

    def run(job):
        item, arm = job
        rec = {
            "item_id": item["item_id"], "arm": arm, "level": item["level"],
            "chain_len": item["chain_len"], "fact_count": item["fact_count"],
            "seed": item["seed"], "seed_hash": item["seed_hash"],
            "src": item["arms"][arm]["src"], "dst": item["arms"][arm]["dst"],
            "gold": item["arms"][arm]["gold"],
            "same_component": item["arms"][arm]["same_component"],
            "directed_reach": item["arms"][arm]["directed_reach"],
            "undirected_hops": item["arms"][arm]["undirected_hops"],
            "prompt_sha256": item["arms"][arm]["prompt_sha256"],
            "prompt_chars": item["arms"][arm]["prompt_chars"],
            "gate_hash": gate["gate_hash"],
            "attempts": [],
        }
        for attempt in (1, 2):
            if attempt == 2 and not budget.acquire():
                rec["retry_skipped_budget"] = True
                break
            if attempt == 1 and not budget.acquire():
                rec["attempts"].append({"attempt": 1, "error_class":
                                        "budget_exhausted", "wall_s": 0.0,
                                        "started_at": now_iso(),
                                        "finished_at": now_iso()})
                break
            t0 = time.monotonic()
            started = now_iso()
            resp = call_endpoint(item["arms"][arm]["prompt"],
                                 deadline_s=ITEM_DEADLINE_S)
            wall = round(time.monotonic() - t0, 3)
            finished = now_iso()
            cls = classify(resp)
            ans, src_field, offset = parse_answer(resp["content"],
                                                  resp["reasoning"])
            att = {"attempt": attempt, "wall_s": wall, "error_class": cls or None,
                   "started_at": started, "finished_at": finished,
                   "finish_reason": resp["finish_reason"],
                   "prompt_tokens": resp["prompt_tokens"],
                   "completion_tokens": resp["completion_tokens"],
                   "answer": ans, "answer_source": src_field,
                   "answer_offset": offset,
                   "content": resp["content"], "reasoning": resp["reasoning"]}
            rec["attempts"].append(att)
            if ans is not None:
                break
        rec["answer"] = rec["attempts"][-1]["answer"]
        rec["answer_source"] = rec["attempts"][-1]["answer_source"]
        if rec["answer"] is None:
            rec["correct"] = None
        else:
            model_yes = 1 if rec["answer"] == "yes" else 0
            rec["correct"] = int(model_yes == rec["gold"])
        rec["transport_failure"] = rec["answer"] is None
        return rec

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {pool.submit(run, job): job for job in jobs}
        for fut in concurrent.futures.as_completed(futures):
            rec = fut.result()
            results[(rec["item_id"], rec["arm"])] = rec
            with raw_lock:
                with open(RAW_PATH, "a", encoding="utf-8") as fh:
                    fh.write(canonical(rec) + "\n")
                    fh.flush()
                    os.fsync(fh.fileno())
    return [results[(item["item_id"], arm)] for item in items for arm in ARMS]


# ------------------------------------------------------------------ analysis


def analyse(records: list, items: list, gate: dict) -> dict:
    by = {(r["item_id"], r["arm"]): r for r in records}
    arms = {}
    for arm in ARMS:
        got = [by[(i["item_id"], arm)] for i in items]
        answered = [r for r in got if r["answer"] is not None]
        correct = sum(1 for r in answered if r["correct"] == 1)
        lo, hi = wilson(correct, len(answered)) if answered else (0.0, 0.0)
        arms[arm] = {
            "prompts": len(got), "answered": len(answered),
            "transport_failures": len(got) - len(answered),
            "correct": correct,
            "accuracy": round(correct / len(answered), 6) if answered else None,
            "wilson95": [round(lo, 6), round(hi, 6)],
            "answer_source_content": sum(1 for r in got
                                         if r["answer_source"] == "content"),
            "answer_source_reasoning": sum(1 for r in got
                                           if r["answer_source"] == "reasoning"),
            "mean_completion_tokens": round(
                sum(r["attempts"][-1]["completion_tokens"] for r in got)
                / len(got), 3),
            "finish_reason_length": sum(1 for r in got
                                        if r["attempts"][-1]["finish_reason"]
                                        == "length"),
        }
    per_level = {}
    for level in LEVELS:
        got = [r for r in records if r["level"] == level]
        answered = [r for r in got if r["answer"] is not None]
        per_level[str(level)] = {
            "cells": len(got), "answered": len(answered),
            "correct": sum(1 for r in answered if r["correct"] == 1),
            "mean_completion_tokens": round(
                sum(r["attempts"][-1]["completion_tokens"] for r in got)
                / len(got), 3) if got else None,
            "mean_wall_s": round(
                sum(r["attempts"][-1].get("wall_s", 0.0) for r in got)
                / len(got), 3) if got else None,
        }
    families = {}
    for name, (a, b) in (("direction_F1_R1", ("F1", "R1")),
                         ("component_F2_X", ("F2", "X"))):
        b_ct = c_ct = both_right = both_wrong = 0
        for item in items:
            ra = by[(item["item_id"], a)]
            rb = by[(item["item_id"], b)]
            if ra["correct"] is None or rb["correct"] is None:
                continue
            if ra["correct"] == 1 and rb["correct"] == 1:
                both_right += 1
            elif ra["correct"] == 0 and rb["correct"] == 0:
                both_wrong += 1
            elif ra["correct"] == 0:
                b_ct += 1
            else:
                c_ct += 1
        families[name] = {"pairs": both_right + both_wrong + b_ct + c_ct,
                          "both_right": both_right, "both_wrong": both_wrong,
                          "b_first_wrong": b_ct, "c_second_wrong": c_ct,
                          "p_exact_mcnemar": mcnemar_exact(b_ct, c_ct)}
    signature = {}
    for label, pred in (("connectivity", {"F1": 1, "R1": 1, "F2": 1, "X": 0}),
                        ("traversal", {"F1": 1, "R1": 0, "F2": 1, "X": 0}),
                        ("constant_yes", {a: 1 for a in ARMS}),
                        ("constant_no", {a: 0 for a in ARMS})):
        hits = 0
        per_item = 0
        for item in items:
            item_hits = 0
            for arm in ARMS:
                rec = by[(item["item_id"], arm)]
                got = 1 if rec["answer"] == "yes" else 0
                if got == pred[arm]:
                    item_hits += 1
            hits += item_hits
            per_item += int(item_hits == len(ARMS))
        signature[label] = {"cells_matching": hits,
                            "cells": len(items) * len(ARMS),
                            "items_matching_all_four": per_item,
                            "items": len(items)}
    chain_recite = 0
    for rec in records:
        text = (rec["attempts"][-1]["content"] + " "
                + rec["attempts"][-1]["reasoning"])
        names = [rec["src"], rec["dst"]]
        item = next(i for i in items if i["item_id"] == rec["item_id"])
        interior = [n for n in item["path"] if n not in names]
        if interior and all(n in text for n in interior):
            chain_recite += 1
    return {
        "arms": arms,
        "per_level": per_level,
        "families": families,
        "signature_table": signature,
        "records_naming_all_interior_nodes": chain_recite,
        "records": len(records),
    }


# ------------------------------------------------------------------ selftest


def selftest() -> int:
    fails = []

    def check(name, ok):
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            fails.append(name)

    recs = load_pool()
    pool = verify_pool(recs)
    items = build_matched_items()
    inv = matched_invariant(items)

    check("generated pool gold equals recomputed directed reachability",
          not pool["gold_reach_mismatches"])
    check("generated pool has zero cells where connectivity and reachability "
          "disagree",
          pool["cells_where_connectivity_and_reachability_disagree"] == 0)
    check("generated pool is 900 items over levels 12, 16, 24",
          pool["items_total"] == 900 and set(pool["levels"]) ==
          {"12", "16", "24"})
    check("generation is byte-identical across calls (blob hashes match twice)",
          pool_blob_sha256() == pool_blob_sha256())
    check("matched-pair invariant holds with zero violations",
          not inv["violations"])
    check("matched corpus has nine cells where connectivity and reachability "
          "disagree",
          sum(1 for i in items for a in ARMS
              if i["arms"][a]["same_component"] != i["arms"][a]["directed_reach"])
          == len(items))
    check("matched corpus gold is balanced 18 yes / 18 no",
          sum(i["arms"][a]["gold"] for i in items for a in ARMS) == 18)
    check("every matched family arm pair has identical prompt length",
          all(i["arms"][a]["prompt_chars"] == i["arms"][b]["prompt_chars"]
              for i in items for a, b in (("F1", "R1"), ("F2", "X"))))
    check("direction arms span at least 11 hops (levels 12, 16, 24 minus one)",
          all(i["arms"]["F1"]["undirected_hops"] >= 11 for i in items))
    check("interior endpoints defeat the out-degree-zero rule on F1 and R1",
          all(graph_of(i["facts"])[3][i["arms"][arm]["dst"]] >= 1
              for i in items for arm in ("F1", "R1")))
    check("the cross-component arm X is unreachable in the undirected graph",
          all(i["arms"]["X"]["undirected_hops"] == -1 for i in items))
    check("matched chain lengths equal the item levels (12, 16, 24 witnessed)",
          sorted(i["chain_len"] for i in items) == [12, 12, 12, 16, 16, 16,
                                                    24, 24, 24])
    check("the battery holds 15 direction-blind rules and 2 chain references",
          len(LEAK_RULES) == 15 and len(REFERENCE_RULES) == 2)

    batt = battery_on_matched(items)
    check("reference rule directed_reachability scores 1.0000 on the matched corpus",
          batt["directed_reachability"]["accuracy"] == 1.0)
    check("reference rule chain_position_order scores 1.0000 on the matched corpus",
          batt["chain_position_order"]["accuracy"] == 1.0)
    check("same_component scores exactly 0.7500 on the matched corpus",
          batt["same_component"]["accuracy"] == 0.75)
    check("all_yes and all_no each score exactly 0.5000 on the matched corpus",
          batt["all_yes"]["accuracy"] == 0.5 and batt["all_no"]["accuracy"] == 0.5)
    check("no direction-blind rule reaches the 0.90 bar on the matched corpus",
          max(batt[r]["accuracy"] for r in LEAK_RULES) < GATE_MIN_ACCURACY)

    planted = sum(1 for item in items for arm in ARMS
                  if battery_predictions("same_component", item, arm) == 1)
    null = exact_null_matched("same_component", items, planted)
    check("exact null for same_component on the matched corpus is centred "
          "near 18 of 36", 15.0 <= null["null_mean"] <= 21.0)
    check("two-sided matched p is at least the one-sided p for same_component",
          null["p_two_sided"] >= null["p_one_sided_upper"])
    check("matched null support bounds contain the observed hits",
          null["null_min_hits"] <= planted <= null["null_max_hits"])

    cross = build_matched_items()
    for item in cross:
        item["arms"]["X"]["dst"] = item["path"][0]
    cross_inv = matched_invariant(cross)
    check("cross-item query injection violates the matched-pair invariant",
          bool(cross_inv["violations"]))

    flipped = build_matched_items()
    for item in flipped:
        item["facts"] = [[t, REL, s] for s, r, t in item["facts"]]
    flip_inv = matched_invariant(flipped)
    check("edge-reversal of a matched item is caught by the gold-vs-reachability check",
          any(v.get("check") == "gold_vs_recomputed_reachability"
              for v in flip_inv["violations"]))

    pool_batt = battery_on_pool(recs)
    sn = exact_null_pool("same_component", recs,
                         pool_batt["same_component"]["predictions"])
    check("same_component reproduces every pool gold label",
          pool_batt["same_component"]["accuracy"] == 1.0)
    check("pool null has nonzero width and the observation sits at the "
          "attainable maximum",
          sn["null_sd"] > 0.0 and sn["null_max_hits"] == sn["observed_hits"])
    check("pool null support equals the true support for same_component",
          sn["null_min_hits"] == abs(sn["rule_yes_cells"] + sn["gold_yes_cells"]
                                     - 900))
    check("constant rules have a degenerate pool null with p_two_sided 1.0",
          exact_null_pool("all_no", recs,
                          pool_batt["all_no"]["predictions"])["p_two_sided"]
          == 1.0
          and exact_null_pool("all_yes", recs,
                              pool_batt["all_yes"]["predictions"])["p_two_sided"]
          == 1.0)
    inv_null = exact_null_pool("all_no", recs,
                               [1 - p for p in pool_batt["same_component"]
                                ["predictions"]])
    inv_pred = [1 - p for p in pool_batt["same_component"]["predictions"]]
    inv_gold = [1 if r["answer"] == "yes" else 0 for r in recs]
    inv_acc = sum(1 for p, g in zip(inv_pred, inv_gold) if p == g) / len(recs)
    check("a rule that is wrong on every pool cell has one-sided upper p 1.0 "
          "and cannot fire (two-sided significance without the accuracy bar "
          "is not a leak)", inv_null["p_one_sided_upper"] == 1.0
          and inv_acc < GATE_MIN_ACCURACY)
    check("a direction-blind rule does reach the bar on the pool corpus",
          max(pool_batt[r]["accuracy"] for r in LEAK_RULES) >= GATE_MIN_ACCURACY)
    check("chain_len_matches_level is the metadata leak on the pool",
          pool_batt["chain_len_matches_level"]["accuracy"] == 1.0)

    check("empty completion classifies as transport failure, not no_answer",
          classify({"content": "", "reasoning": "", "finish_reason": "stop",
                    "prompt_tokens": 5, "completion_tokens": 0})
          == "empty_completion")
    check("http failure classifies as its status code",
          classify({"error": "http_503", "content": "", "reasoning": "",
                    "finish_reason": None, "prompt_tokens": 0,
                    "completion_tokens": 0}) == "http_503")
    check("parser falls back to the reasoning field only when content has none",
          parse_answer("", "the answer is no")[1] == "reasoning"
          and parse_answer("no", "the answer is yes")[0] == "no")

    budget = AttemptBudget(3)
    got = [budget.acquire() for _ in range(4)]
    check("attempt budget stops calls at the cap", got == [True, True, True, False])

    gate = build_gate()
    gate["gate_hash"] = gate_seed_hash(gate)
    check("gate hash is stable across regeneration",
          gate_seed_hash(build_gate()) == gate["gate_hash"])
    check("gate declares a discriminating matched corpus",
          gate["matched_corpus"][
              "cells_where_connectivity_and_reachability_disagree"] == len(items))
    check("gate declares a non-discriminating pool corpus",
          gate["pool_corpus"][
              "cells_where_connectivity_and_reachability_disagree"] == 0)
    check("gate verdicts: matched discriminating, pool not",
          gate["discrimination"]["matched_discriminating"] is True
          and gate["discrimination"]["pool_discriminating"] is False)
    check("gate max blind accuracy is 1.0 pool and 0.75 matched",
          gate["discrimination"]["max_blind_accuracy_pool"] == 1.0
          and gate["discrimination"]["max_blind_accuracy_matched"] == 0.75)
    check("gate fires no blind rule on the matched corpus",
          gate["discrimination"]["rules_firing_matched"] == [])

    def fake_records(pred_by_arm, content_fn):
        out = []
        for item in items:
            for arm in ARMS:
                pred = pred_by_arm(arm, item)
                gold = item["arms"][arm]["gold"]
                out.append({"item_id": item["item_id"], "arm": arm,
                            "level": item["level"],
                            "answer": "yes" if pred == 1 else "no",
                            "answer_source": "content",
                            "correct": int(pred == gold), "gold": gold,
                            "src": item["arms"][arm]["src"],
                            "dst": item["arms"][arm]["dst"],
                            "attempts": [{"content": content_fn(item, arm),
                                          "reasoning": "",
                                          "finish_reason": "stop",
                                          "completion_tokens": 40,
                                          "prompt_tokens": 400, "wall_s": 1.0,
                                          "error_class": None,
                                          "answer": "x",
                                          "answer_source": "content",
                                          "answer_offset": 0,
                                          "started_at": "t", "finished_at": "t"}]})
        return out

    trav = fake_records(lambda arm, item: item["arms"][arm]["gold"],
                        lambda item, arm: " ".join(item["path"]))
    sig = analyse(trav, items, gate)
    check("traversal-consistent fabrication matches 36 of 36 cells",
          sig["signature_table"]["traversal"]["cells_matching"] == 36)
    check("connectivity oracle fails the traversal-consistent fabrication on "
          "exactly the nine R1 cells",
          sig["signature_table"]["connectivity"]["cells_matching"] == 27)
    yesfake = fake_records(lambda arm, item: 1, lambda item, arm: "yes")
    sig3 = analyse(yesfake, items, gate)
    check("an always-yes fabricated model scores 18 of 36, not 36 of 36",
          sum(sig3["arms"][a]["correct"] for a in ARMS) == 18)
    check("an always-yes fabricated model yields 9 discordant direction pairs",
          sig3["families"]["direction_F1_R1"]["c_second_wrong"] == 9
          and sig3["families"]["direction_F1_R1"]["b_first_wrong"] == 0)
    connfake = fake_records(lambda arm, item: {"F1": 1, "R1": 1, "F2": 1,
                                               "X": 0}[arm],
                            lambda item, arm: "")
    sig2 = analyse(connfake, items, gate)
    check("a connectivity-consistent fabrication yields 9 discordant direction pairs",
          sig2["families"]["direction_F1_R1"]["c_second_wrong"] == 9
          and sig2["families"]["direction_F1_R1"]["b_first_wrong"] == 0)
    check("exact McNemar on 9 one-sided discordant pairs is below 0.01",
          sig2["families"]["direction_F1_R1"]["p_exact_mcnemar"] < 0.01)
    check("a traversal-consistent fabrication yields zero discordant pairs",
          sig["families"]["direction_F1_R1"]["b_first_wrong"] == 0
          and sig["families"]["direction_F1_R1"]["c_second_wrong"] == 0)
    check("exact McNemar with no discordance is 1.0",
          sig["families"]["direction_F1_R1"]["p_exact_mcnemar"] == 1.0)
    check("chain recitation counter reads 36 on the traversal fabrication and "
          "0 on the always-yes fabrication",
          sig["records_naming_all_interior_nodes"] == 36
          and sig3["records_naming_all_interior_nodes"] == 0)
    wrongfake = fake_records(lambda arm, item: 1 - item["arms"][arm]["gold"],
                             lambda item, arm: "no")
    sig4 = analyse(wrongfake, items, gate)
    check("an adversarially wrong fabrication scores 0 of 36 and is caught",
          sum(sig4["arms"][a]["correct"] for a in ARMS) == 0)

    print(f"\nselftest: {len(fails)} failure(s)")
    return 1 if fails else 0


# --------------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.gate:
        gate = build_gate()
        gate["gate_hash"] = gate_seed_hash(gate)
        with open(GATE_PATH, "w", encoding="utf-8") as fh:
            json.dump(gate, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(f"gate written: {GATE_PATH}")
        print(f"gate_hash: {gate['gate_hash']}")
        print(f"pool items: {gate['pool_corpus']['items']}, disagreeing cells: "
              f"{gate['pool_corpus']['cells_where_connectivity_and_reachability_disagree']}")
        print(f"matched cells: {gate['matched_corpus']['cells']}, disagreeing "
              f"cells: {gate['matched_corpus']['cells_where_connectivity_and_reachability_disagree']}")
        for row in gate["rules"]:
            print(f"  {row['rule']:34s} pool {row['pool_accuracy']:.10f} "
                  f"p2={row['pool_p_two_sided']:.3e}  matched "
                  f"{row['matched_accuracy']:.10f} p2={row['matched_p_two_sided']:.3e}")
        return 0
    gate = json.load(open(GATE_PATH, encoding="utf-8"))
    if gate.get("gate_hash") != gate_seed_hash(gate):
        raise SystemExit("gate.json hash mismatch; refusing to spend prompts")
    items = build_matched_items()
    invariant = matched_invariant(items)
    if invariant["violations"]:
        raise SystemExit(f"matched-pair invariant violated: {invariant['violations']}")
    second = build_matched_items()
    if matched_invariant(second)["violations"]:
        raise SystemExit("matched-pair invariant violated on rebuild")
    if sha256_text(canonical(fingerprint_of(items))) \
            != sha256_text(canonical(fingerprint_of(second))):
        raise SystemExit("matched-pair construction is not seed deterministic")
    if args.probe:
        budget = AttemptBudget(MAX_PROMPTS)
        hc = health_check()
        budget.used += 1
        if not hc["ok"]:
            print(f"health check failed: {hc}")
            return 2
        print(f"health ok: {hc['latency_s']}s")
        t0 = time.monotonic()
        records = dispatch(items, gate, budget)
        wall = round(time.monotonic() - t0, 1)
        print(f"probe wall: {wall}s for {len(records)} prompts at concurrency "
              f"{CONCURRENCY}; total endpoint calls incl. health: {budget.used}")
        return 0
    if args.analyze:
        records = [json.loads(l) for l in open(RAW_PATH, encoding="utf-8")
                   if l.strip()]
        out = analyse(records, items, gate)
        out["gate_hash"] = gate["gate_hash"]
        out["seed_base"] = SEED_BASE
        out["raw_sha256"] = sha256_file(RAW_PATH)
        out["gate_sha256"] = sha256_file(GATE_PATH)
        out["item_source"] = {
            "generator_sha256": sha256_file(LADDERS_PATH),
            "blob_sha256": pool_blob_sha256(),
        }
        out["total_endpoint_calls_including_health"] = sum(
            len(r["attempts"]) for r in records) + 1
        out["item_deadline_s"] = ITEM_DEADLINE_S
        out["concurrency"] = CONCURRENCY
        out["dispatch"] = (f"parallel dispatch, concurrency {CONCURRENCY}, "
                           "one retry per arm under a global attempt cap, "
                           "incremental fsynced raw archive")
        with open(SUMMARY_PATH, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(json.dumps(out["arms"], indent=2))
        print(json.dumps(out["per_level"], indent=2))
        print(json.dumps(out["families"], indent=2))
        print(json.dumps(out["signature_table"], indent=2))
        print(f"records naming all interior nodes: "
              f"{out['records_naming_all_interior_nodes']}")
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

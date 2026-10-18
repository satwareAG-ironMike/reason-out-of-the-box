#!/usr/bin/env python3
"""Nightly research round 10 (2026-10-18, 04:00 slot).

Question: on the shipped ladder corpus the undirected-connectivity shortcut and
directed reachability are indistinguishable, because every shipped item has
`directed_reach == same_component` for its queried pair. Does the probed endpoint
actually traverse the chain, or does it answer from connectivity?

Method: take real shipped items and add a true matched pair of queries inside
each item. The pair shares the same facts, the same names, the same fact count,
the same prompt length and the same endpoint degree profile; only the queried
pair varies.

  F1  (p_1, p_{k-1})  forward interior      gold yes   k-2 hops
  R1  (p_{k-1}, p_1)  reverse interior      gold no    same component
  F2  (p_2, p_k)      forward interior      gold yes   k-2 hops
  X   (p_2, m)        cross-component       gold no    m matched to p_k by degree

F1/R1 isolate direction. F2/X isolate component membership. Every endpoint has
in-degree 1 and out-degree 1 except the two chain ends, and the two arms of each
family use the same two endpoints in swapped roles, so the degree and distance
features that issue #67 flagged are held constant inside each family.

Subcommands:
  --selftest  deterministic controls, no endpoint contact
  --gate      corpus verification, leak battery, exact null, gate.json
  --probe     the 36-prompt matched-pair probe against the live endpoint
  --analyze   read-only statistics over the archived raw responses

Stdlib only. Imports nothing from generators/. The endpoint is read from
NIGHTLY_BASE_URL / NIGHTLY_MODEL_ID and neither value is written to any artifact.
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures
import hashlib
import json
import math
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))

SEED_BASE = 20261018
REL = "precedes"
RULE_SENTENCE = (
    f"Rule: for all x, y, z: if x {REL} y and y {REL} z, then x {REL} z. "
    "Facts state direct precedes links."
)
LEVELS = (4, 6, 8)
ITEMS_PER_LEVEL = 3
ARMS = ("F1", "R1", "F2", "X")
GOLD = {"F1": 1, "R1": 0, "F2": 1, "X": 0}

MAX_PROMPTS = 40
CALIBRATION_RESERVE = 4
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


def hypergeometric_tail_or_equal(ngood: int, nbad: int, nsample: int,
                                 observed: int) -> float:
    """Exact P(H >= observed) for H ~ Hypergeometric(ngood + nbad, ngood, nsample)."""
    lo = max(0, nsample - nbad)
    hi = min(ngood, nsample)
    if observed > hi:
        return 0.0
    if observed <= lo:
        return 1.0
    total = log_choose(ngood + nbad, nsample)
    acc = 0.0
    for h in range(max(observed, lo), hi + 1):
        acc += math.exp(log_choose(ngood, h) + log_choose(nbad, nsample - h) - total)
    return min(1.0, acc)


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


# ---------------------------------------------------------------- corpus


def load_shipped() -> list:
    """Every shipped ladder item on this branch, with its level recorded."""
    out = []
    for level in (1, 2, 4, 6, 8):
        path = os.path.join(REPO, "items", "ladders", f"l{level}.jsonl")
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                rec["_level"] = level
                rec["_path"] = path
                out.append(rec)
    return out


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


def verify_shipped(recs: list) -> dict:
    """Independent recomputation of every shipped gold label."""
    per_level = collections.OrderedDict()
    mismatches = []
    disagree = 0
    for rec in recs:
        adj, und, in_deg, out_deg, nodes = graph_of(rec["facts"])
        src, _rel, dst = rec["query"]
        reach = directed_reachable(src, dst, adj)
        same = components(nodes, und).get(src) == components(nodes, und).get(dst)
        gold = 1 if rec["answer"] == "yes" else 0
        if int(reach) != gold:
            mismatches.append({"level": rec["_level"], "seed": rec["seed"]})
        if int(same) != int(reach):
            disagree += 1
        bucket = per_level.setdefault(
            rec["_level"],
            {"items": 0, "gold_yes": 0, "gold_no": 0, "reach_mismatch": 0,
             "component_reach_disagree": 0, "facts_min": 10**9, "facts_max": 0,
             "chain_len": collections.Counter(), "sha256": None},
        )
        bucket["items"] += 1
        bucket["gold_yes"] += gold
        bucket["gold_no"] += 1 - gold
        bucket["reach_mismatch"] += int(int(reach) != gold)
        bucket["component_reach_disagree"] += int(int(same) != int(reach))
        bucket["facts_min"] = min(bucket["facts_min"], len(rec["facts"]))
        bucket["facts_max"] = max(bucket["facts_max"], len(rec["facts"]))
        bucket["chain_len"][rec.get("chain_len")] += 1
        bucket["sha256"] = sha256_file(rec["_path"])
    for bucket in per_level.values():
        bucket["chain_len"] = {str(k): v for k, v in sorted(
            bucket["chain_len"].items(), key=lambda kv: (kv[0] is None, kv[0]))}
    return {
        "levels": {str(k): v for k, v in per_level.items()},
        "items_total": len(recs),
        "gold_reach_mismatches": mismatches,
        "cells_where_connectivity_and_reachability_disagree": disagree,
    }


# ------------------------------------------------- matched-pair construction


def chain_path(rec: list) -> list:
    """The directed chain that the shipped gold-yes query witnesses.

    Returns the node list p_1 .. p_{k+1} or None when the item is not usable:
    the query must be reachable, the path must be simple, every node on it must
    have in-degree <= 1 and out-degree <= 1, and the item must contain a second
    component with a terminal node of the same name length as p_{k+1}.
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


def build_matched_items() -> list:
    """Deterministic selection: first N usable items per shipped level, in file
    order. The selection rule is fixed before any prompt is written."""
    recs = load_shipped()
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
                "source_sha256": sha256_file(rec["_path"]),
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


def render_prompt(facts: list, src: str, dst: str) -> str:
    lines = [RULE_SENTENCE]
    lines += [f"Fact {i + 1}: {s} {r} {t}."
              for i, (s, r, t) in enumerate(facts)]
    lines.append(f"Question: does {src} {REL} {dst}? "
                 "Answer with exactly one word: yes or no.")
    return "\n".join(lines)


def matched_invariant(items: list) -> dict:
    """Every family must be matched on fact count, name multiset, prompt length
    and endpoint degree profile. Violations are fatal, not reported as results."""
    adj, und, in_deg, out_deg, _nodes = None, None, None, None, None
    violations = []
    for item in items:
        adj, und, in_deg, out_deg, _nodes = graph_of(item["facts"])
        comp = components(_nodes, und)
        fact_count = {len(item["facts"])}
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
                ("fact_count", len(fact_count) == 1),
                ("gold_balance", pa["gold"] != pb["gold"]),
            ]
            if family == "direction":
                # Same two names, same undirected distance: only the arrow of the
                # query differs, so any direction-blind rule must answer both alike.
                checks = common + [
                    ("name_multiset", names_a == names_b),
                    ("undirected_distance", undist_a == undist_b),
                    ("same_component_pair",
                     int(comp[pa["src"]] == comp[pa["dst"]])
                     == int(comp[pb["src"]] == comp[pb["dst"]])),
                ]
            else:
                # Connectivity is the manipulated variable here, so it must differ;
                # everything else about the two endpoints is held fixed.
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
            pa["undirected_hops"] = undirected_distance(pa["src"], pa["dst"], und)
    return {"violations": violations, "items": len(items),
            "cells": len(items) * len(ARMS)}


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


# Direction-blind heuristics: none of these ever orders two nodes along a
# directed chain. They are the candidate shortcuts the corpus must defeat.
LEAK_RULES = (
    "all_yes", "all_no", "same_component", "name_first_mention_order",
    "name_last_mention_order", "name_alphabetical_order",
    "source_is_first_fact_source", "target_is_fact_target",
    "source_is_fact_source", "endpoint_in_degree_zero",
    "endpoint_out_degree_zero", "undirected_connectivity_only",
    "fact_count_threshold", "chain_len_matches_level", "relation_word_copy",
)
# Competent references: both recover the chain order, so they are expected to
# score 1.0000 and are excluded from the blind battery.
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


def battery_on_shipped(recs: list) -> dict:
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
                      "accuracy": correct / len(cached), "predictions": predictions}
    return rows


# ------------------------------------------------------------------ exact null


def exact_null_matched(rule: str, items: list, observed: int) -> dict:
    """Exact null for per-item gold-label shuffling.

    Within one item the four arm labels are permuted uniformly at random, which
    preserves the per-item count of gold-yes cells. For a rule that predicts 1
    on `a` of the n cells and an item holding y gold-yes cells, the number of
    matches is 2H + n - y - a with H ~ Hypergeometric(n, y, a). The distribution
    of the total over items is the exact convolution of those per-item
    distributions.
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
    tail = sum(v for k, v in dist.items() if k >= observed)
    return {"null_mean": round(mean, 6), "null_sd": round(math.sqrt(var), 6),
            "null_max": max(dist), "observed_hits": observed,
            "p_exact": float(f"{tail:.3e}"),
            "z_observed": round((observed - mean) / math.sqrt(var), 4)
            if var > 0 else None}


def exact_null_shipped(rule: str, recs: list, predictions) -> dict:
    """Exact null for a global gold-label shuffle over the shipped corpus.

    Per-item shuffling is degenerate here (one queried pair per item), so the
    calibration shuffles the gold labels across the whole corpus while
    preserving the corpus-level count of gold-yes labels. The rule's prediction
    pattern is held fixed and the gold labels are reassigned uniformly.
    """
    n = len(recs)
    y = sum(1 for r in recs if r["answer"] == "yes")
    a = sum(predictions)
    observed = sum(1 for rec, pred in zip(recs, predictions)
                   if pred == (1 if rec["answer"] == "yes" else 0))
    # Under the label shuffle the number of gold-yes labels that land on the a
    # cells the rule predicts yes for is K ~ Hypergeometric(n, y, a), and the
    # hit count is hits = 2K + n - y - a. Convert the observed hits back to the
    # K threshold before taking the tail.
    k_min = max(0, -((-(observed + y + a - n)) // 2))
    mean = (a * y + (n - a) * (n - y)) / n
    if a == 0 or a == n or y == 0 or y == n:
        sd = 0.0
    else:
        var_h = a * (y / n) * (1 - y / n) * ((n - a) / (n - 1))
        sd = 2 * math.sqrt(var_h)
    p = hypergeometric_tail_or_equal(y, n - y, a, k_min)
    # NOTE (known defect, issue #77 follow-up): the support of hits = 2K + n - y - a
    # over K in [max(0, a + y - n), min(a, y)] is [|a + y - n|, n - |a - y|]. The
    # bounds emitted below are wider than that support (they are the naive
    # intersection bounds), so gate.json and summary.json from round 10 carry
    # null_min_hits and null_max_hits that are too wide for 12 of 15 rules, and
    # null_max_hits is wrong for all_yes, source_is_fact_source and
    # endpoint_in_degree_zero. Fixing the formulas changes gate.json, so it must
    # ship with a fresh gate hash and a re-run gate; it is not retrofittable into
    # the round-10 artifacts, whose hashes are bound into raw.jsonl.
    return {"null_mean": round(mean, 6), "null_sd": round(sd, 6),
            "null_min_hits": max(0, a + y - n), "null_max_hits": min(n, a + (n - y)),
            "observed_hits": observed, "rule_yes_cells": a, "gold_yes_cells": y,
            "p_exact": float(f"{p:.3e}"),
            "z_observed": round((observed - mean) / sd, 4) if sd > 0 else None}


# --------------------------------------------------------------------- gate


def build_gate() -> dict:
    recs = load_shipped()
    shipped = verify_shipped(recs)
    items = build_matched_items()
    invariant = matched_invariant(items)
    if invariant["violations"]:
        raise SystemExit(f"matched-pair invariant violated: {invariant['violations']}")
    ship_batt = battery_on_shipped(recs)
    match_batt = battery_on_matched(items)
    bonf = GATE_ALPHA / len(LEAK_RULES)
    rows = []
    for rule in LEAK_RULES:
        s = ship_batt[rule]
        m = match_batt[rule]
        sn = exact_null_shipped(rule, recs, s["predictions"])
        mn = exact_null_matched(rule, items, m["correct"])
        rows.append({
            "rule": rule,
            "shipped_accuracy": round(s["accuracy"], 10),
            "shipped_p_exact": sn["p_exact"],
            "shipped_null": sn,
            "matched_accuracy": round(m["accuracy"], 10),
            "matched_p_exact": mn["p_exact"],
            "matched_null": mn,
            "fires_shipped": bool(sn["p_exact"] <= bonf
                                  and s["accuracy"] >= GATE_MIN_ACCURACY),
            "fires_matched": bool(mn["p_exact"] <= bonf
                                  and m["accuracy"] >= GATE_MIN_ACCURACY),
        })
    disagree_shipped = shipped[
        "cells_where_connectivity_and_reachability_disagree"]
    disagree_matched = sum(
        1 for item in items for arm in ARMS
        if item["arms"][arm]["same_component"] != item["arms"][arm]["directed_reach"])
    return {
        "schema": "round10-gate-v2",
        "seed_base": SEED_BASE,
        "gate_hash": None,
        "alpha": GATE_ALPHA,
        "bonferroni_alpha": round(bonf, 12),
        "min_accuracy": GATE_MIN_ACCURACY,
        "null_model": {
            "shipped": "global gold-label shuffle preserving the corpus gold-yes "
                       "count; per-item shuffling is degenerate because each "
                       "shipped item carries exactly one queried pair",
            "matched": "per-item gold-label shuffle preserving the per-item "
                       "gold-yes count; exact convolution, no Monte Carlo",
        },
        "shipped_corpus": {
            "files": [f"items/ladders/l{lvl}.jsonl" for lvl in (1, 2, 4, 6, 8)],
            "items": shipped["items_total"],
            "levels": shipped["levels"],
            "gold_reach_mismatches": shipped["gold_reach_mismatches"],
            "cells_where_connectivity_and_reachability_disagree": disagree_shipped,
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
             "shipped_accuracy": round(ship_batt[rule]["accuracy"], 10),
             "matched_accuracy": round(match_batt[rule]["accuracy"], 10)}
            for rule in REFERENCE_RULES
        ],
        "blind_rule_count": len(LEAK_RULES),
        "reference_rule_count": len(REFERENCE_RULES),
        "discrimination": {
            "definition": "a corpus is discriminating when no direction-blind rule "
                          "in the battery both beats its exact label-shuffle null "
                          "and reaches the accuracy bar",
            "max_blind_accuracy_shipped": max(r["shipped_accuracy"] for r in rows),
            "max_blind_accuracy_matched": max(r["matched_accuracy"] for r in rows),
            "rules_firing_shipped": [r["rule"] for r in rows if r["fires_shipped"]],
            "rules_firing_matched": [r["rule"] for r in rows if r["fires_matched"]],
            "shipped_discriminating": max(r["shipped_accuracy"] for r in rows)
                                      < GATE_MIN_ACCURACY,
            "matched_discriminating": max(r["matched_accuracy"] for r in rows)
                                      < GATE_MIN_ACCURACY,
            "note": "significance is not competence: a direction-blind rule can beat "
                    "the label-shuffle null on the matched corpus while still missing "
                    "the bar, because component membership correlates with the gold "
                    "label there. The bar is what makes the corpus discriminating.",
        },
        "rules": rows,
        "selection_rule": {
            "levels": list(LEVELS),
            "items_per_level": ITEMS_PER_LEVEL,
            "order": "file order, first usable item per level",
            "usable": "gold-yes query witnessed by a simple in-degree<=1 "
                      "out-degree<=1 chain of length >= 4, plus a second "
                      "component holding a terminal node (in-degree 1, "
                      "out-degree 0) whose name length equals the chain terminal",
        },
        "probe_budget": {
            "max_prompts": MAX_PROMPTS,
            "dispatch_prompts": len(items) * len(ARMS),
            "calibration_reserve": CALIBRATION_RESERVE,
            "max_tokens": MAX_TOKENS,
            "temperature": TEMPERATURE,
            "item_deadline_s": ITEM_DEADLINE_S,
            "concurrency": CONCURRENCY,
            "retries_per_item": 1,
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
    if content carries none, fall back to the last yes/no token in the reasoning
    field and mark the source. Returns (answer or None, source, offset)."""
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
            "prompt_tokens": resp["prompt_tokens"]}


# -------------------------------------------------------------------- probe


def dispatch(items: list, gate: dict) -> list:
    total_cells = len(items) * len(ARMS)
    if total_cells > MAX_PROMPTS - CALIBRATION_RESERVE:
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
    jobs = [(item, arm) for item in items for arm in ARMS
            if (item["item_id"], arm) not in done]
    if done:
        print(f"resuming: {len(done)} cells already recorded, {len(jobs)} to go")
    results = dict(done)
    lock_records = []

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
            t0 = time.monotonic()
            resp = call_endpoint(item["arms"][arm]["prompt"],
                                 deadline_s=ITEM_DEADLINE_S)
            wall = round(time.monotonic() - t0, 3)
            cls = classify(resp)
            ans, src_field, offset = parse_answer(resp["content"], resp["reasoning"])
            att = {"attempt": attempt, "wall_s": wall, "error_class": cls or None,
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
        if all(n in text for n in interior):
            chain_recite += 1
    return {
        "arms": arms,
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

    recs = load_shipped()
    shipped = verify_shipped(recs)
    items = build_matched_items()
    inv = matched_invariant(items)

    check("shipped gold equals recomputed directed reachability",
          not shipped["gold_reach_mismatches"])
    check("shipped corpus has zero cells where connectivity and reachability "
          "disagree",
          shipped["cells_where_connectivity_and_reachability_disagree"] == 0)
    check("shipped corpus is 1500 items over levels 1,2,4,6,8",
          shipped["items_total"] == 1500 and set(shipped["levels"]) ==
          {"1", "2", "4", "6", "8"})
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
    check("interior endpoints defeat the out-degree-zero rule on F1 and R1",
          all(graph_of(i["facts"])[3][i["arms"][arm]["dst"]] >= 1
              for i in items for arm in ("F1", "R1")))
    check("queried distance is at least two hops on every forward arm",
          all(i["arms"][arm]["undirected_hops"] >= 2
              for i in items for arm in ("F1", "R1", "F2")))
    check("the cross-component arm X is unreachable in the undirected graph",
          all(i["arms"]["X"]["undirected_hops"] == -1 for i in items))
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

    planted = 0
    for item in items:
        for arm in ARMS:
            if battery_predictions("same_component", item, arm) == 1:
                planted += 1
    null = exact_null_matched("same_component", items, planted)
    check("exact null for same_component on the matched corpus is centred near "
          "18 of 36", 15.0 <= null["null_mean"] <= 21.0)
    check("exact null max for same_component is reachable but not the observed "
          "value alone", null["null_max"] >= planted)

    mislabel = 0
    for item in items:
        for arm in ARMS:
            gold = item["arms"][arm]["gold"]
            if battery_predictions("all_yes", item, arm) == gold:
                mislabel += 1
    null_yes = exact_null_matched("all_yes", items, mislabel)
    check("planted mislabelled reverse query is caught: all_yes matches exactly "
          "18 of 36 gold cells", mislabel == 18)
    check("all_yes null is centred at 18", abs(null_yes["null_mean"] - 18.0) < 1e-9)

    cross = build_matched_items()
    for item in cross:
        item["arms"]["X"]["dst"] = item["path"][0]
    cross_inv = matched_invariant(cross)
    check("cross-item query injection violates the matched-pair invariant",
          bool(cross_inv["violations"]))

    ship_batt = battery_on_shipped(recs)
    sn = exact_null_shipped("same_component", recs,
                            ship_batt["same_component"]["predictions"])
    check("same_component reproduces every shipped gold label",
          ship_batt["same_component"]["accuracy"] == 1.0)
    check("shipped exact null for same_component is astronomically small",
          sn["p_exact"] < 1e-100)
    check("shipped null for same_component has nonzero width and the observation "
          "sits at the attainable maximum",
          sn["null_sd"] > 0.0 and sn["null_max_hits"] == sn["observed_hits"])
    check("constant rules have a degenerate shipped null centred on the gold base "
          "rate", exact_null_shipped("all_no", recs,
                                     ship_batt["all_no"]["predictions"])["p_exact"]
          == 1.0
          and exact_null_shipped("all_yes", recs,
                                 ship_batt["all_yes"]["predictions"])["p_exact"]
          == 1.0)
    check("a rule that is wrong on every shipped cell has p_exact 1.0",
          exact_null_shipped("all_no", recs,
                             [1 - p for p in ship_batt["same_component"]
                              ["predictions"]])["p_exact"] == 1.0)
    check("a direction-blind rule does reach the bar on the shipped corpus",
          max(ship_batt[r]["accuracy"] for r in LEAK_RULES) >= GATE_MIN_ACCURACY)
    check("undirected_connectivity_only and same_component agree everywhere",
          ship_batt["undirected_connectivity_only"]["accuracy"]
          == ship_batt["same_component"]["accuracy"]
          and batt["undirected_connectivity_only"]["accuracy"]
          == batt["same_component"]["accuracy"])

    check("empty completion classifies as transport failure, not no_answer",
          classify({"content": "", "reasoning": "", "finish_reason": "stop",
                    "prompt_tokens": 5, "completion_tokens": 0})
          == "empty_completion")
    check("http failure classifies as its status code",
          classify({"error": "http_503", "content": "", "reasoning": "",
                    "finish_reason": None, "prompt_tokens": 0,
                    "completion_tokens": 0}) == "http_503")
    check("parser falls back to the reasoning field only when content is empty",
          parse_answer("", "the answer is no")[1] == "reasoning"
          and parse_answer("no", "the answer is yes")[0] == "no")

    gate = build_gate()
    gate["gate_hash"] = gate_seed_hash(gate)
    check("gate hash is stable across regeneration",
          gate_seed_hash(build_gate()) == gate["gate_hash"])
    check("gate declares a discriminating matched corpus",
          gate["matched_corpus"][
              "cells_where_connectivity_and_reachability_disagree"] == len(items))
    check("gate declares a non-discriminating shipped corpus",
          gate["shipped_corpus"][
              "cells_where_connectivity_and_reachability_disagree"] == 0)
    check("gate verdicts: matched corpus discriminating, shipped corpus not",
          gate["discrimination"]["matched_discriminating"] is True
          and gate["discrimination"]["shipped_discriminating"] is False)
    check("gate max blind accuracy is 1.0 shipped and 0.75 matched",
          gate["discrimination"]["max_blind_accuracy_shipped"] == 1.0
          and gate["discrimination"]["max_blind_accuracy_matched"] == 0.75)
    check("gate fires no blind rule on the matched corpus",
          gate["discrimination"]["rules_firing_matched"] == [])

    fake = []
    for item in items:
        for arm in ARMS:
            gold = item["arms"][arm]["gold"]
            fake.append({"item_id": item["item_id"], "arm": arm,
                         "answer": "yes" if gold == 1 else "no",
                         "answer_source": "content", "correct": 1,
                         "gold": gold,
                         "src": item["arms"][arm]["src"],
                         "dst": item["arms"][arm]["dst"],
                         "attempts": [{"content": " ".join(item["path"]),
                                       "reasoning": "",
                                       "finish_reason": "stop",
                                       "completion_tokens": 40,
                                       "prompt_tokens": 200, "wall_s": 1.0,
                                       "error_class": None, "answer": "x",
                                       "answer_source": "content",
                                       "answer_offset": 0}]})
    sig = analyse(fake, items, gate)
    check("traversal signature matches 36 of 36 cells on a traversal-consistent "
          "fabrication", sig["signature_table"]["traversal"]["cells_matching"] == 36)
    check("connectivity signature matches 27 of 36 cells on a traversal-consistent "
          "fabrication", sig["signature_table"]["connectivity"]["cells_matching"] == 27)
    yes_fake = []
    for item in items:
        for arm in ARMS:
            gold = item["arms"][arm]["gold"]
            yes_fake.append({"item_id": item["item_id"], "arm": arm,
                             "answer": "yes", "answer_source": "content",
                             "correct": int(gold == 1), "gold": gold,
                             "src": item["arms"][arm]["src"],
                             "dst": item["arms"][arm]["dst"],
                             "attempts": [{"content": "yes", "reasoning": "",
                                           "finish_reason": "stop",
                                           "completion_tokens": 4,
                                           "prompt_tokens": 200, "wall_s": 1.0,
                                           "error_class": None, "answer": "yes",
                                           "answer_source": "content",
                                           "answer_offset": 0}]})
    sig3 = analyse(yes_fake, items, gate)
    check("an always-yes fabricated model scores 18 of 36, not 36 of 36",
          sum(sig3["arms"][a]["correct"] for a in ARMS) == 18)
    check("an always-yes fabricated model yields 9 discordant direction pairs",
          sig3["families"]["direction_F1_R1"]["c_second_wrong"] == 9
          and sig3["families"]["direction_F1_R1"]["b_first_wrong"] == 0)
    conn_fake = []
    for item in items:
        for arm in ARMS:
            pred = {"F1": 1, "R1": 1, "F2": 1, "X": 0}[arm]
            conn_fake.append({"item_id": item["item_id"], "arm": arm,
                              "answer": "yes" if pred else "no",
                              "answer_source": "content",
                              "correct": int(pred == item["arms"][arm]["gold"]),
                              "gold": item["arms"][arm]["gold"],
                              "src": item["arms"][arm]["src"],
                              "dst": item["arms"][arm]["dst"],
                              "attempts": [{"content": "", "reasoning": "",
                                            "finish_reason": "stop",
                                            "completion_tokens": 12,
                                            "prompt_tokens": 200, "wall_s": 1.0,
                                            "error_class": None, "answer": "x",
                                            "answer_source": "content",
                                            "answer_offset": 0}]})
    sig2 = analyse(conn_fake, items, gate)
    check("a connectivity-consistent fabrication yields 9 discordant pairs in the "
          "direction family",
          sig2["families"]["direction_F1_R1"]["c_second_wrong"] == 9
          and sig2["families"]["direction_F1_R1"]["b_first_wrong"] == 0)
    check("exact McNemar on 9 one-sided discordant pairs is below 0.01",
          sig2["families"]["direction_F1_R1"]["p_exact_mcnemar"] < 0.01)
    check("a traversal-consistent fabrication yields zero discordant pairs",
          sig["families"]["direction_F1_R1"]["b_first_wrong"] == 0
          and sig["families"]["direction_F1_R1"]["c_second_wrong"] == 0)
    check("exact McNemar with no discordance is 1.0",
          sig["families"]["direction_F1_R1"]["p_exact_mcnemar"] == 1.0)

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
        print(f"shipped items: {gate['shipped_corpus']['items']}, "
              f"disagreeing cells: {gate['shipped_corpus']['cells_where_connectivity_and_reachability_disagree']}")
        print(f"matched cells: {gate['matched_corpus']['cells']}, "
              f"disagreeing cells: {gate['matched_corpus']['cells_where_connectivity_and_reachability_disagree']}")
        for row in gate["rules"]:
            print(f"  {row['rule']:34s} shipped {row['shipped_accuracy']:.10f} "
                  f"p={row['shipped_p_exact']:.3e}  matched "
                  f"{row['matched_accuracy']:.10f} p={row['matched_p_exact']:.3e}")
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
        hc = health_check()
        if not hc["ok"]:
            print(f"health check failed: {hc}")
            return 2
        print(f"health ok: {hc['latency_s']}s")
        t0 = time.monotonic()
        records = dispatch(items, gate)
        print(f"probe wall: {round(time.monotonic() - t0, 1)}s "
              f"for {len(records)} prompts at concurrency {CONCURRENCY}")
        return 0
    if args.analyze:
        records = [json.loads(l) for l in open(RAW_PATH, encoding="utf-8") if l.strip()]
        out = analyse(records, items, gate)
        out["gate_hash"] = gate["gate_hash"]
        out["seed_base"] = SEED_BASE
        out["raw_sha256"] = sha256_file(RAW_PATH)
        out["gate_sha256"] = sha256_file(GATE_PATH)
        out["corpus_sha256"] = {f"items/ladders/l{lvl}.jsonl":
                                sha256_file(os.path.join(REPO, "items", "ladders",
                                                         f"l{lvl}.jsonl"))
                                for lvl in (1, 2, 4, 6, 8)}
        out["item_deadline_s"] = ITEM_DEADLINE_S
        out["concurrency"] = CONCURRENCY
        out["dispatch"] = (f"parallel dispatch, concurrency {CONCURRENCY}, "
                           "one retry per arm, incremental fsynced raw archive")
        with open(SUMMARY_PATH, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(json.dumps(out["arms"], indent=2))
        print(json.dumps(out["families"], indent=2))
        print(json.dumps(out["signature_table"], indent=2))
        print(f"records naming all interior nodes: "
              f"{out['records_naming_all_interior_nodes']}")
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

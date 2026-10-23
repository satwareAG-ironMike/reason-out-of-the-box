#!/usr/bin/env python3
"""Nightly research round 14 (2026-10-20, 04:00 slot).

Question: rounds 9-11 established, on flash-class pool slots of one model
family, that the matched-pair probe separates directed traversal from
undirected connectivity (round 10: 36/36 cells on the k = 4, 6, 8 grid;
round 11: 36/36 cells replicated at k = 12, 16, 24). All of those runs are
one model family. This round asks one question: does the traversal verdict
replicate across model scale, on a 27B-class local endpoint, on the SAME
thirty-six cells as round 11 (same seed_base 20261019, same selection rule,
same generator, byte-identical prompts), with cell-paired answers?

This serves issue #71 (place the depth ceiling per (family, endpoint)):
flash-class shows no turnover up to k = 24; the per-endpoint data point for
a second, larger endpoint class is the open next step.

Method: round 11's matched-pair construction, reused unchanged (gate schema
round11-gate-v3 logic; corpus, battery, exact nulls, McNemar). Three
differences, each declared before any prompt is spent:

1. Cross-class reference. Round 11's raw archive (36 records, branch
   research/nightly-2026-10-19-0200 at commit a47ffa4, file
   research/nightly-2026-10-19-0200/raw.jsonl) is committed to this round's
   directory as round11_reference_raw.jsonl with its sha256 pinned in the
   gate. The matched corpus is verified byte-identical to round 11's by
   cell-paired prompt_sha256 equality, so the comparison is cell-paired,
   not just same-construction.
2. Transport policy (issue #73 direction). One health completion before the
   grid. The first two grid cells dispatch sequentially and their measured
   wall times set the per-item estimate (max of the two, doubled for the
   deeper levels). Concurrency for the remaining 34 cells is the largest of
   {4, 2, 1} such that estimate * 34 / concurrency * 1.25 fits a 2700 s
   phase-2 budget; ties go to the smaller concurrency. Per-item deadline
   900 s, one retry per arm, global attempt cap 40 including health.
   Incremental fsynced raw archive: one line per completed cell; abandoned
   cells (phase-2 or level budget exhausted) are written with outcome
   "abandoned_budget" and are never scored.
3. Outcome classification refinement. Round 11 counted every unanswered
   attempt as transport_failure. This round separates: "answered",
   "truncated_no_answer" (finish_reason length with no parseable yes/no: a
   budget outcome, not a transport failure, issue #71's "state which
   resource is scarce"), "no_answer_stop" (model stopped without a yes/no:
   a model outcome), "empty_completion" and "transport_<class>" (transport
   failures per issue #73). Correctness is scored only on "answered".

Stdlib only. Imports the canonical generator module for item construction
and independently re-derives every gold label. The endpoint is read from
NIGHTLY_BASE_URL / NIGHTLY_MODEL_ID / NIGHTLY_API_KEY and no endpoint value
is written to any artifact.

Subcommands:
  --selftest  deterministic controls, no endpoint contact
  --gate      corpus verification, leak battery, exact nulls, gate.json
  --probe     the 36-prompt matched-pair probe against the live endpoint
  --analyze   read-only statistics over the archived raw responses
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
LEVEL_BUDGET_S = 1500
PHASE2_BUDGET_S = 2700
CONCURRENCY_CHOICES = (4, 2, 1)

GATE_ALPHA = 0.05
GATE_MIN_ACCURACY = 0.90

GATE_PATH = os.path.join(HERE, "gate.json")
RAW_PATH = os.path.join(HERE, "raw.jsonl")
SUMMARY_PATH = os.path.join(HERE, "summary.json")
REF_PATH = os.path.join(HERE, "round11_reference_raw.jsonl")
REF_SHA256 = "f5a77a4685ad6ef44d2f1871c1c264be9fd82584db5f767df5f75f97fbf77f68"
REF_SOURCE = ("research/nightly-2026-10-19-0200/raw.jsonl, branch "
              "research/nightly-2026-10-19-0200 at commit a47ffa4 "
              "(round 11, flash-class local endpoint)")

ANSWER_RE = re.compile(r"\b(yes|no)\b", re.IGNORECASE)
URL_RE = re.compile(
    r"https?://\S+|\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|"
    r"(?:/[A-Za-z0-9_.-]+){2,}|[A-Za-z]:\\[^\s]*"
)
HEALTH_PROMPT = "Reply with exactly one word: yes"


# ---------------------------------------------------------------- utilities

def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sanitize(text: str) -> str:
    return URL_RE.sub("[redacted]", text or "")


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple:
    if total == 0:
        return 0.0, 0.0
    p = successes / total
    denom = 1 + z * z / total
    centre = p + z * z / (2 * total)
    spread = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return (centre - spread) / denom, (centre + spread) / denom


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


def load_ladders():
    spec = importlib.util.spec_from_file_location("ladders", LADDERS_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_pool() -> list:
    lad = load_ladders()
    recs = []
    for level in LEVELS:
        for item in lad.generate_items(level, POOL_PER_LEVEL, SEED_BASE):
            rec = dict(item)
            rec["_level"] = level
            recs.append(rec)
    return recs


def pool_blob_sha256() -> dict:
    lad = load_ladders()
    out = {}
    for level in LEVELS:
        blob = "".join(lad.item_jsonl(i) + "\n"
                       for i in lad.generate_items(level, POOL_PER_LEVEL,
                                                   SEED_BASE))
        out[f"generated/l{level}.jsonl"] = sha256_text(blob)
    return out


def graph_of(facts: list) -> tuple:
    adj: dict = {}
    und: dict = {}
    in_deg: dict = collections.defaultdict(int)
    out_deg: dict = collections.defaultdict(int)
    nodes: set = set()
    for s, _rel, t in facts:
        adj.setdefault(s, []).append(t)
        und.setdefault(s, set()).add(t)
        und.setdefault(t, set()).add(s)
        out_deg[s] += 1
        in_deg[t] += 1
        nodes.add(s)
        nodes.add(t)
    for n in nodes:
        in_deg.setdefault(n, 0)
        out_deg.setdefault(n, 0)
    return adj, und, dict(in_deg), dict(out_deg), nodes


def components(nodes: set, und: dict) -> dict:
    seen: set = set()
    labels: dict = {}
    for node in sorted(nodes):
        if node in seen:
            continue
        stack = [node]
        seen.add(node)
        while stack:
            u = stack.pop()
            labels[u] = node
            for v in und.get(u, ()):
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
    return labels


def directed_reachable(src: str, dst: str, adj: dict) -> bool:
    if src == dst:
        return True
    dist = {src: 0}
    q = [src]
    while q:
        u = q.pop(0)
        for v in adj.get(u, ()):
            if v not in dist:
                if v == dst:
                    return True
                dist[v] = dist[u] + 1
                q.append(v)
    return False


def undirected_distance(a: str, b: str, und: dict) -> int:
    if a == b:
        return 0
    dist = {a: 0}
    q = [a]
    while q:
        u = q.pop(0)
        for v in und.get(u, ()):
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist.get(b, -1)


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
    length equals the chain terminal's. Same rule as round 10/11.
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
    file order. The selection rule is fixed before any prompt is written.
    With seed_base 20261019 this is byte-identical to round 11's corpus."""
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
             "fact_count": i["fact_count"],
             "component_count": i["component_count"],
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
    over K in [max(0, a + y - n), min(a, y)] is [|a+y-n|, n-|a-y|].
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


def load_reference() -> list:
    if not os.path.exists(REF_PATH):
        raise SystemExit(f"reference archive missing: {REF_PATH}")
    if sha256_file(REF_PATH) != REF_SHA256:
        raise SystemExit("reference archive sha256 mismatch; refusing to continue")
    return [json.loads(line) for line in open(REF_PATH, encoding="utf-8")
            if line.strip()]


def cross_class_identity(items: list, ref_records: list) -> dict:
    """Cell-paired identity of this round's corpus with round 11's archive."""
    ref_by = {}
    for rec in ref_records:
        key = (rec["item_id"], rec["arm"])
        if key in ref_by:
            raise SystemExit(f"duplicate reference cell {key}")
        ref_by[key] = rec
    mine = {(i["item_id"], a): i["arms"][a]["prompt_sha256"]
            for i in items for a in ARMS}
    mismatches = []
    for key, prompt_sha in sorted(mine.items()):
        rec = ref_by.get(key)
        if rec is None:
            mismatches.append({"cell": list(key), "reason": "missing_in_ref"})
        elif rec.get("prompt_sha256") != prompt_sha:
            mismatches.append({"cell": list(key),
                               "reason": "prompt_sha256_mismatch"})
    ref_only = sorted(set(ref_by) - set(mine))
    return {
        "reference_cells": len(ref_by),
        "this_round_cells": len(mine),
        "prompt_sha256_mismatches": mismatches,
        "reference_cells_not_in_this_round": ref_only,
        "identical": not mismatches and not ref_only
                     and len(ref_by) == len(mine) == len(items) * len(ARMS),
    }


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
    identity = cross_class_identity(items, load_reference())
    return {
        "schema": "round14-gate-v1",
        "seed_base": SEED_BASE,
        "gate_hash": None,
        "alpha": GATE_ALPHA,
        "bonferroni_alpha": round(bonf, 12),
        "min_accuracy": GATE_MIN_ACCURACY,
        "null_model": {
            "tail_note": "firing uses the two-sided exact p value against the "
                         "Bonferroni bar; both tails are recorded",
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
            "round11_pin_check": {
                "note": "the three blob hashes must equal the round-11 gate "
                        "pins (byte-identical regeneration across runs and "
                        "branches); verified in the selftest",
                "expected": {
                    "generated/l12.jsonl":
                        "305e8d4ca0483ee67d493c91a0d88ea5aacdc77bdee2e0ad06e01d42a85266fe",
                    "generated/l16.jsonl":
                        "8a41995c9fe887b3eadfb3be8d5bcaf2d3574e58d2a4193d714c540fda5d3afd",
                    "generated/l24.jsonl":
                        "e9f5d19c161526f508db309045e295eeea00f7c144458b9ea513ec39f9d6a90f",
                },
            },
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
        "cross_class_reference": {
            "purpose": "round 14 is a scale replication: round 11 ran this "
                       "exact corpus on a flash-class local endpoint; this "
                       "round runs it on a 27B-class local endpoint. The "
                       "cell-paired prompt hashes make the comparison "
                       "cell-paired, not just same-construction.",
            "source": REF_SOURCE,
            "committed_copy": "round11_reference_raw.jsonl",
            "sha256": REF_SHA256,
            "records": len(load_reference()),
            "identity": identity,
            "endpoint_classes": "reference: flash-class local endpoint; "
                                "this round: 27B-class local endpoint "
                                "(both self-hosted, public class names only)",
        },
        "probe_budget": {
            "max_prompts": MAX_PROMPTS,
            "health_prompts": HEALTH_PROMPTS,
            "dispatch_prompts": len(items) * len(ARMS),
            "attempt_cap_total": MAX_PROMPTS,
            "max_tokens": MAX_TOKENS,
            "temperature": TEMPERATURE,
            "item_deadline_s": ITEM_DEADLINE_S,
            "level_budget_s": LEVEL_BUDGET_S,
            "phase2_budget_s": PHASE2_BUDGET_S,
            "retries": "one retry per arm, global attempt cap enforced",
        },
        "transport_policy": {
            "health_check": "one trivial completion, verified non-empty and "
                            "answer-parseable, before any grid prompt "
                            "(issue #73)",
            "measurement": "the first two grid cells dispatch sequentially; "
                           "their wall times measure the endpoint; per-item "
                           "estimate is max(wall_0, wall_1) * 2.0 "
                           "(depth factor for the k=24 items); both calls "
                           "count in the 40-attempt cap",
            "concurrency_rule": "largest of {4, 2, 1} such that "
                                "estimate * 34 / concurrency * 1.25 <= "
                                "phase2_budget_s; ties to the smaller "
                                "concurrency; the measured values and the "
                                "choice are recorded in summary.json",
            "level_budget": "each level group (4 cells) is dispatched as a "
                            "group with a LEVEL_BUDGET_S wall budget from "
                            "group start; cells that would start after the "
                            "group deadline or the phase-2 deadline are "
                            "written with outcome abandoned_budget and are "
                            "never scored (issue #73: a killed arm is not a "
                            "result)",
            "raw_archive": "incremental: one flushed raw.jsonl line per "
                           "completed cell, fsynced (issue #73)",
        },
        "outcome_classification": {
            "answered": "a yes/no token was parsed (content first, reasoning "
                        "fallback)",
            "truncated_no_answer": "finish_reason length with no parseable "
                                   "yes/no: a budget outcome, not a "
                                   "transport failure (issue #71: state "
                                   "which resource is scarce)",
            "no_answer_stop": "finish_reason stop with no parseable yes/no: "
                              "a model outcome",
            "empty_completion": "completion_tokens 0: a transport failure "
                                "(issue #73)",
            "transport_<class>": "endpoint error class: a transport failure",
            "abandoned_budget": "the cell was not dispatched because a "
                                "declared budget was exhausted; never "
                                "scored",
            "note": "correctness is scored only on answered cells; round 11 "
                    "counted every unanswered attempt as transport_failure, "
                    "this round separates the five outcomes above",
        },
        "primary_statistic": {
            "test": "two-sided exact McNemar on the matched (F1, R1) pairs",
            "secondary": "two-sided exact McNemar on the matched (F2, X) pairs",
            "unit": "item",
            "n_pairs": len(items),
        },
        "cross_class_primary": {
            "statistic": "cell-paired answer agreement between this round's "
                         "records and the round-11 reference records, on "
                         "cells answered on both sides",
            "n_cells": len(items) * len(ARMS),
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


def classify_attempt(att: dict) -> str:
    """Outcome classification for one attempt (see the gate declaration)."""
    if att.get("error_class"):
        return f"transport_{att['error_class']}"
    if att["completion_tokens"] == 0:
        return "empty_completion"
    if att["answer"] is not None:
        return "answered"
    if att["finish_reason"] == "length":
        return "truncated_no_answer"
    return "no_answer_stop"


def outcome_of(rec: dict) -> str:
    """Outcome for a record, from its last attempt; records with no attempts
    are abandoned_budget."""
    if not rec["attempts"]:
        return "abandoned_budget"
    return classify_attempt(rec["attempts"][-1])


def health_check() -> dict:
    t0 = time.monotonic()
    resp = call_endpoint(HEALTH_PROMPT, deadline_s=180)
    latency = round(time.monotonic() - t0, 3)
    att = {"error_class": resp.get("error"),
           "finish_reason": resp["finish_reason"],
           "completion_tokens": resp["completion_tokens"],
           "prompt_tokens": resp["prompt_tokens"],
           "answer": None, "answer_source": "none", "answer_offset": -1}
    ans, src_field, offset = parse_answer(resp["content"], resp["reasoning"])
    att["answer"] = ans
    att["answer_source"] = src_field
    att["answer_offset"] = offset
    cls = classify_attempt(att)
    ok = cls == "answered"
    return {"ok": ok, "outcome": cls if ok else cls,
            "latency_s": latency, "completion_tokens": resp["completion_tokens"],
            "prompt_tokens": resp["prompt_tokens"],
            "started_at": now_iso(), "finished_at": now_iso()}


class AttemptBudget:
    """Hard cap on total endpoint calls for the whole run: health check +
    dispatch + retries can never exceed MAX_PROMPTS."""

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


def attempt_record(item: dict, arm: str, gate: dict, budget: AttemptBudget,
                   phase: int) -> dict:
    """One cell: up to two attempts (one retry) under the global cap."""
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
        "phase": phase,
        "attempts": [],
    }
    for attempt_no in (1, 2):
        if attempt_no == 2 and rec["attempts"] and rec["attempts"][0]["answer"] is not None:
            break
        if not budget.acquire():
            rec["attempts"].append({"attempt": attempt_no, "wall_s": 0.0,
                                    "error_class": "budget_exhausted",
                                    "started_at": now_iso(),
                                    "finished_at": now_iso(),
                                    "finish_reason": None,
                                    "prompt_tokens": 0, "completion_tokens": 0,
                                    "answer": None, "answer_source": "none",
                                    "answer_offset": -1,
                                    "content": "", "reasoning": ""})
            break
        t0 = time.monotonic()
        started = now_iso()
        resp = call_endpoint(item["arms"][arm]["prompt"],
                             deadline_s=ITEM_DEADLINE_S)
        wall = round(time.monotonic() - t0, 3)
        finished = now_iso()
        att = {"attempt": attempt_no, "wall_s": wall,
               "error_class": resp.get("error"),
               "started_at": started, "finished_at": finished,
               "finish_reason": resp["finish_reason"],
               "prompt_tokens": resp["prompt_tokens"],
               "completion_tokens": resp["completion_tokens"],
               "content": resp["content"], "reasoning": resp["reasoning"]}
        ans, src_field, offset = parse_answer(resp["content"], resp["reasoning"])
        att["answer"] = ans
        att["answer_source"] = src_field
        att["answer_offset"] = offset
        rec["attempts"].append(att)
        if ans is not None:
            break
    last = rec["attempts"][-1] if rec["attempts"] else None
    rec["answer"] = last["answer"] if last else None
    rec["answer_source"] = last["answer_source"] if last else "none"
    rec["outcome"] = outcome_of(rec)
    rec["correct"] = None
    if rec["answer"] is not None:
        rec["correct"] = int((1 if rec["answer"] == "yes" else 0)
                             == rec["gold"])
    return rec


def write_raw(rec: dict) -> None:
    with open(RAW_PATH, "a", encoding="utf-8") as fh:
        fh.write(canonical(rec) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def dispatch(items: list, gate: dict, budget: AttemptBudget) -> tuple:
    """Two-phase dispatch: the first two cells sequentially (measurement),
    then the remaining 34 at the policy-declared concurrency. Per-level
    groups carry the level budget; abandoned cells are written with outcome
    abandoned_budget. Returns (records, transport_note)."""
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
    ordered = [(item, arm) for item in items for arm in ARMS]
    results = dict(done)
    note = {"resumed_cells": len(done)}

    def run(job: tuple, phase: int) -> dict:
        item, arm = job
        if (item["item_id"], arm) in results:
            return results[(item["item_id"], arm)]
        rec = attempt_record(item, arm, gate, budget, phase)
        results[(item["item_id"], arm)] = rec
        write_raw(rec)
        return rec

    # Phase 1: first two cells, sequential (measurement, issue #73).
    phase1 = [job for job in ordered[:2]
              if (job[0]["item_id"], job[1]) not in results]
    for job in phase1:
        run(job, phase=1)
    walls = [results[(j[0]["item_id"], j[1])]["attempts"][-1]["wall_s"]
             for j in ordered[:2]
             if results[(j[0]["item_id"], j[1])]["attempts"]]
    est = (max(walls) * 2.0) if walls else 60.0
    remaining = total_cells - 2 - note["resumed_cells"]
    chosen = None
    for cand in CONCURRENCY_CHOICES:
        if est * max(remaining, 0) / cand * 1.25 <= PHASE2_BUDGET_S:
            chosen = cand
            break
    if chosen is None:
        chosen = max(CONCURRENCY_CHOICES)
    note.update({"phase1_walls": walls,
                 "estimate_per_item_s": round(est, 3),
                 "chosen_concurrency": chosen})
    print(f"phase-1 walls {walls} s, estimate {round(est, 1)} s/item, "
          f"concurrency {chosen} for {remaining} cells", flush=True)

    # Phase 2: per-level groups, level budget from group start.
    by_level: dict = collections.OrderedDict()
    for job in ordered[2:]:
        by_level.setdefault(job[0]["level"], []).append(job)
    phase2_start = time.monotonic()
    for level, jobs in by_level.items():
        level_deadline = time.monotonic() + LEVEL_BUDGET_S
        pending = [j for j in jobs if (j[0]["item_id"], j[1]) not in results]
        to_run = []
        abandoned = []
        for job in pending:
            if time.monotonic() > min(level_deadline,
                                      phase2_start + PHASE2_BUDGET_S):
                abandoned.append(job)
            else:
                to_run.append(job)
        for job in abandoned:
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
                "gate_hash": gate["gate_hash"], "phase": 2, "attempts": [],
                "answer": None, "answer_source": "none", "outcome":
                "abandoned_budget", "correct": None,
            }
            results[(item["item_id"], arm)] = rec
            write_raw(rec)
        if not to_run:
            continue
        with concurrent.futures.ThreadPoolExecutor(max_workers=chosen) as pool:
            futures = {pool.submit(run, job, 2): job for job in to_run}
            for fut in concurrent.futures.as_completed(futures):
                fut.result()
        print(f"level {level} group done", flush=True)
    records = [results[(item["item_id"], arm)] for item in items for arm in ARMS]
    return records, note


# ------------------------------------------------------------------ analysis


def signature_of(by: dict, items: list) -> dict:
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
    return signature


def cross_class_analysis(records: list, items: list) -> dict:
    ref_records = load_reference()
    ref_by = {(r["item_id"], r["arm"]): r for r in ref_records}
    compared = 0
    agree = 0
    per_level = {}
    disagreements = []
    token_pairs = collections.defaultdict(list)
    wall_pairs = collections.defaultdict(list)
    my_unanswered = 0
    ref_unanswered = 0
    for rec in records:
        key = (rec["item_id"], rec["arm"])
        ref = ref_by.get(key)
        if ref is None:
            continue
        if rec["answer"] is None:
            my_unanswered += 1
        if ref.get("answer") is None:
            ref_unanswered += 1
        if rec["answer"] is None or ref.get("answer") is None:
            continue
        compared += 1
        same = int(rec["answer"] == ref["answer"])
        agree += same
        bucket = per_level.setdefault(str(rec["level"]),
                                      {"compared": 0, "agree": 0})
        bucket["compared"] += 1
        bucket["agree"] += same
        if not same:
            disagreements.append({"cell": list(key), "level": rec["level"],
                                  "this_round": rec["answer"],
                                  "round11": ref["answer"],
                                  "gold": rec["gold"],
                                  "correct_this_round": rec["correct"],
                                  "correct_round11": ref.get("correct")})
        my_att = rec["attempts"][-1] if rec["attempts"] else None
        ref_att = ref["attempts"][-1] if ref.get("attempts") else None
        if my_att and ref_att:
            if ref_att.get("completion_tokens"):
                token_pairs[str(rec["level"])].append(
                    (my_att["completion_tokens"],
                     ref_att["completion_tokens"]))
            if ref_att.get("wall_s"):
                wall_pairs[str(rec["level"])].append(
                    (my_att["wall_s"], ref_att["wall_s"]))
    token_ratio = {
        lvl: round(sum(a for a, _b in pairs) / len(pairs)
                   / (sum(b for _a, b in pairs) / len(pairs)), 4)
        for lvl, pairs in sorted(token_pairs.items()) if pairs}
    wall_ratio = {
        lvl: round(sum(a for a, _b in pairs) / len(pairs)
                   / (sum(b for _a, b in pairs) / len(pairs)), 4)
        for lvl, pairs in sorted(wall_pairs.items()) if pairs}
    # Reference-side signature, computed from the reference answers.
    ref_answers = {(k): (1 if r.get("answer") == "yes" else 0)
                   for k, r in ref_by.items()}
    ref_sig = {}
    for label, pred in (("traversal", {"F1": 1, "R1": 0, "F2": 1, "X": 0}),
                        ("connectivity", {"F1": 1, "R1": 1, "F2": 1, "X": 0})):
        hits = 0
        per_item = 0
        for item in items:
            item_hits = 0
            for arm in ARMS:
                if ref_answers.get((item["item_id"], arm)) == pred[arm]:
                    item_hits += 1
            hits += item_hits
            per_item += int(item_hits == len(ARMS))
        ref_sig[label] = {"cells_matching": hits,
                          "items_matching_all_four": per_item}
    return {
        "reference": REF_SOURCE,
        "reference_sha256": REF_SHA256,
        "cells_compared": compared,
        "cells_agree": agree,
        "cells_disagree": compared - agree,
        "agreement": round(agree / compared, 6) if compared else None,
        "per_level": per_level,
        "this_round_unanswered": my_unanswered,
        "reference_unanswered": ref_unanswered,
        "disagreements": disagreements,
        "completion_token_ratio_this_round_over_round11": token_ratio,
        "wall_s_ratio_this_round_over_round11": wall_ratio,
        "reference_signature": ref_sig,
    }


def reasoning_analysis(records: list) -> dict:
    arms = {}
    for arm in ARMS:
        got = [r for r in records if r["arm"] == arm and r["attempts"]]
        if not got:
            continue
        rc = [r["attempts"][-1] for r in got]
        mean_reasoning_chars = round(
            sum(len(a["reasoning"]) for a in rc) / len(rc), 3)
        mean_content_chars = round(
            sum(len(a["content"]) for a in rc) / len(rc), 3)
        denom = mean_reasoning_chars + mean_content_chars
        arms[arm] = {
            "records": len(got),
            "mean_reasoning_chars": mean_reasoning_chars,
            "mean_content_chars": mean_content_chars,
            "reasoning_char_share": round(mean_reasoning_chars / denom, 4)
            if denom else None,
            "mean_completion_tokens": round(
                sum(a["completion_tokens"] for a in rc) / len(rc), 3),
            "answer_source_content": sum(
                1 for r in got if r["answer_source"] == "content"),
            "answer_source_reasoning": sum(
                1 for r in got if r["answer_source"] == "reasoning"),
            "finish_reason_length": sum(
                1 for a in rc if a["finish_reason"] == "length"),
        }
    answered = [r for r in records if r["attempts"] and r["answer"] is not None]
    rc = [r["attempts"][-1] for r in answered]
    total_chars = [len(a["reasoning"]) + len(a["content"]) for a in rc]
    return {
        "arms": arms,
        "overall": {
            "records": len(rc),
            "mean_completion_tokens": round(
                sum(a["completion_tokens"] for a in rc) / len(rc), 3)
                if rc else None,
            "mean_reasoning_chars": round(
                sum(len(a["reasoning"]) for a in rc) / len(rc), 3) if rc else None,
            "mean_content_chars": round(
                sum(len(a["content"]) for a in rc) / len(rc), 3) if rc else None,
            "mean_reasoning_char_share": round(
                sum(len(a["reasoning"]) for a in rc) / sum(total_chars), 4)
                if rc and sum(total_chars) else None,
            "note": "completion_tokens cover reasoning plus content; char "
                    "shares are a proxy split (no per-field token count in "
                    "the API usage)",
        },
    }


def analyse(records: list, items: list, gate: dict, transport: dict) -> dict:
    by = {(r["item_id"], r["arm"]): r for r in records}
    arms = {}
    for arm in ARMS:
        got = [by[(i["item_id"], arm)] for i in items]
        answered = [r for r in got if r["answer"] is not None]
        correct = sum(1 for r in answered if r["correct"] == 1)
        lo, hi = wilson(correct, len(answered)) if answered else (0.0, 0.0)
        outcomes = collections.Counter(outcome_of(r) for r in got)
        arms[arm] = {
            "prompts": len(got), "answered": len(answered),
            "correct": correct,
            "accuracy": round(correct / len(answered), 6) if answered else None,
            "wilson95": [round(lo, 6), round(hi, 6)],
            "outcomes": dict(outcomes),
            "answer_source_content": sum(1 for r in got
                                         if r["answer_source"] == "content"),
            "answer_source_reasoning": sum(1 for r in got
                                           if r["answer_source"] == "reasoning"),
            "mean_completion_tokens": round(
                sum(r["attempts"][-1]["completion_tokens"] for r in got
                    if r["attempts"]) /
                max(1, sum(1 for r in got if r["attempts"])), 3),
            "finish_reason_length": sum(
                1 for r in got if r["attempts"]
                and r["attempts"][-1]["finish_reason"] == "length"),
        }
    per_level = {}
    for level in LEVELS:
        got = [r for r in records if r["level"] == level]
        answered = [r for r in got if r["answer"] is not None]
        per_level[str(level)] = {
            "cells": len(got), "answered": len(answered),
            "correct": sum(1 for r in answered if r["correct"] == 1),
            "outcomes": dict(collections.Counter(outcome_of(r) for r in got)),
            "mean_completion_tokens": round(
                sum(r["attempts"][-1]["completion_tokens"] for r in got
                    if r["attempts"]) /
                max(1, sum(1 for r in got if r["attempts"])), 3) if got else None,
            "mean_wall_s": round(
                sum(r["attempts"][-1].get("wall_s", 0.0) for r in got
                    if r["attempts"]) /
                max(1, sum(1 for r in got if r["attempts"])), 3) if got else None,
        }
    families = {}
    for name, (a, b) in (("direction_F1_R1", ("F1", "R1")),
                         ("component_F2_X", ("F2", "X"))):
        b_ct = c_ct = both_right = both_wrong = skipped = 0
        for item in items:
            ra = by[(item["item_id"], a)]
            rb = by[(item["item_id"], b)]
            if ra["correct"] is None or rb["correct"] is None:
                skipped += 1
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
                          "skipped_unanswered": skipped,
                          "both_right": both_right, "both_wrong": both_wrong,
                          "b_first_wrong": b_ct, "c_second_wrong": c_ct,
                          "p_exact_mcnemar": mcnemar_exact(b_ct, c_ct)}
    signature = signature_of(by, items)
    chain_recite = 0
    for rec in records:
        if not rec["attempts"]:
            continue
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
        "cross_class": cross_class_analysis(records, items),
        "reasoning": reasoning_analysis(records),
        "transport": transport,
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
    r11_pins = {"generated/l12.jsonl":
                "305e8d4ca0483ee67d493c91a0d88ea5aacdc77bdee2e0ad06e01d42a85266fe",
                "generated/l16.jsonl":
                "8a41995c9fe887b3eadfb3be8d5bcaf2d3574e58d2a4193d714c540fda5d3afd",
                "generated/l24.jsonl":
                "e9f5d19c161526f508db309045e295eeea00f7c144458b9ea513ec39f9d6a90f"}
    check("pool blob hashes equal the round-11 gate pins (byte-identical "
          "regeneration across runs and branches)",
          pool_blob_sha256() == r11_pins)
    check("generator module hash equals the round-11 pin",
          sha256_file(LADDERS_PATH) ==
          "15fcab2866cda65fb57db85f819f740f2ca9ab734d50d696b6bcc0a3c118111e")
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

    ref = load_reference()
    check("reference archive is 36 records over 9 items x 4 arms",
          len(ref) == 36
          and len({(r["item_id"], r["arm"]) for r in ref}) == 36)
    check("reference archive gate hash matches the round-11 published hash",
          all(r["gate_hash"] == "4e3d799b0266e93f8b7068357fba5cff3f994158534175a02209647f1936854c"
              for r in ref))
    check("the matched corpus is cell-paired byte-identical to round 11 "
          "(36/36 prompt_sha256 equal, no extra or missing cells)",
          cross_class_identity(items, ref)["identical"])
    check("reference archive answers are 36/36 answered",
          all(r["answer"] in ("yes", "no") for r in ref))

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

    check("truncated attempt without a yes/no is truncated_no_answer, not a "
          "transport failure",
          classify_attempt({"error_class": None, "completion_tokens": 2048,
                            "finish_reason": "length", "answer": None})
          == "truncated_no_answer")
    check("truncated attempt that still parsed a yes is answered",
          classify_attempt({"error_class": None, "completion_tokens": 2048,
                            "finish_reason": "length", "answer": "yes"})
          == "answered")
    check("stopped attempt without a yes/no is a model outcome, not "
          "transport",
          classify_attempt({"error_class": None, "completion_tokens": 400,
                            "finish_reason": "stop", "answer": None})
          == "no_answer_stop")
    check("empty completion classifies as a transport failure",
          classify_attempt({"error_class": None, "completion_tokens": 0,
                            "finish_reason": "stop", "answer": None})
          == "empty_completion")
    check("http failure classifies under its status code",
          classify_attempt({"error_class": "http_503",
                            "completion_tokens": 0, "finish_reason": None,
                            "answer": None}) == "transport_http_503")
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
    check("gate pins the round-11 blob hashes and the reference sha256",
          gate["item_source"]["round11_pin_check"]["expected"]
          == pool_blob_sha256()
          and gate["cross_class_reference"]["sha256"] == REF_SHA256)
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
    check("gate transport policy declares the phase-1 measurement, the "
          "concurrency rule, the level budget and the abandoned-budget "
          "outcome",
          "measurement" in gate["transport_policy"]
          and "concurrency_rule" in gate["transport_policy"]
          and gate["probe_budget"]["level_budget_s"] == LEVEL_BUDGET_S
          and "abandoned_budget" in gate["outcome_classification"])

    def fake_records(answer_fn, content_fn):
        out = []
        for item in items:
            for arm in ARMS:
                ans = answer_fn(arm, item)
                out.append({
                    "item_id": item["item_id"], "arm": arm,
                    "level": item["level"],
                    "answer": ans,
                    "answer_source": "content",
                    "correct": (int((1 if ans == "yes" else 0)
                                    == item["arms"][arm]["gold"])
                                if ans is not None else None),
                    "gold": item["arms"][arm]["gold"],
                    "src": item["arms"][arm]["src"],
                    "dst": item["arms"][arm]["dst"],
                    "attempts": [{"content": content_fn(item, arm),
                                  "reasoning": "r" * 200,
                                  "finish_reason": "stop",
                                  "completion_tokens": 400,
                                  "prompt_tokens": 400, "wall_s": 10.0,
                                  "error_class": None,
                                  "answer": ans,
                                  "answer_source": "content",
                                  "answer_offset": 0,
                                  "started_at": "t", "finished_at": "t"}]})
        return out

    trav = fake_records(lambda arm, item: "yes" if item["arms"][arm]["gold"]
                        else "no",
                        lambda item, arm: " ".join(item["path"]))
    trav_full = analyse(trav, items, gate, {})
    sig = trav_full["signature_table"]
    check("traversal-consistent fabrication matches 36 of 36 cells",
          sig["traversal"]["cells_matching"] == 36)
    check("connectivity oracle fails the traversal-consistent fabrication on "
          "exactly the nine R1 cells",
          sig["connectivity"]["cells_matching"] == 27)
    yesfake = fake_records(lambda arm, item: "yes", lambda item, arm: "yes")
    sig3 = analyse(yesfake, items, gate, {})
    check("an always-yes fabricated model scores 18 of 36, not 36 of 36",
          sum(sig3["arms"][a]["correct"] for a in ARMS) == 18)
    check("an always-yes fabricated model yields 9 discordant direction pairs",
          sig3["families"]["direction_F1_R1"]["c_second_wrong"] == 9
          and sig3["families"]["direction_F1_R1"]["b_first_wrong"] == 0)
    connfake = fake_records(lambda arm, item: "yes" if arm in ("F1", "R1",
                                                               "F2") else "no",
                            lambda item, arm: "")
    sig2 = analyse(connfake, items, gate, {})
    check("a connectivity-consistent fabrication yields 9 discordant direction pairs",
          sig2["families"]["direction_F1_R1"]["c_second_wrong"] == 9
          and sig2["families"]["direction_F1_R1"]["b_first_wrong"] == 0)
    check("exact McNemar on 9 one-sided discordant pairs is below 0.01",
          sig2["families"]["direction_F1_R1"]["p_exact_mcnemar"] < 0.01)
    check("a traversal-consistent fabrication yields zero discordant pairs",
          trav_full["families"]["direction_F1_R1"]["b_first_wrong"] == 0
          and trav_full["families"]["direction_F1_R1"]["c_second_wrong"] == 0)
    check("exact McNemar with no discordance is 1.0",
          trav_full["families"]["direction_F1_R1"]["p_exact_mcnemar"] == 1.0)
    check("chain recitation counter reads 36 on the traversal fabrication and "
          "0 on the always-yes fabrication",
          trav_full["records_naming_all_interior_nodes"] == 36
          and analyse(yesfake, items, gate, {})
          ["records_naming_all_interior_nodes"] == 0)

    cc_same = analyse(trav, items, gate, {})["cross_class"]
    check("cross-class analysis against the round-11 reference: the "
          "traversal fabrication agrees on all 36 cells",
          cc_same["cells_compared"] == 36 and cc_same["cells_agree"] == 36
          and cc_same["agreement"] == 1.0)
    check("cross-class analysis agrees with the reference on the reference "
          "signature (traversal 36/36)",
          cc_same["reference_signature"]["traversal"]["cells_matching"] == 36)
    trav_flipped = fake_records(
        lambda arm, item: "no" if item["arms"][arm]["gold"] else "yes",
        lambda item, arm: "x")
    cc_flip = analyse(trav_flipped, items, gate, {})["cross_class"]
    check("a fully flipped fabrication agrees with the reference on 0 of 36",
          cc_flip["cells_compared"] == 36 and cc_flip["cells_agree"] == 0)
    trav_half = fake_records(
        lambda arm, item: "yes" if arm == "R1"
        else ("yes" if item["arms"][arm]["gold"] else "no"),
        lambda item, arm: "x")
    cc_half = analyse(trav_half, items, gate, {})["cross_class"]
    check("a fabrication that flips only the nine R1 cells agrees with the "
          "reference on 27 of 36 and lists nine disagreements",
          cc_half["cells_compared"] == 36 and cc_half["cells_agree"] == 27
          and len(cc_half["disagreements"]) == 9)
    trav_trunc = fake_records(lambda arm, item: None, lambda item, arm: "")
    cc_trunc = analyse(trav_trunc, items, gate, {})["cross_class"]
    check("fully unanswered records compare on 0 cells and are counted as "
          "this_round_unanswered, not as agreement",
          cc_trunc["cells_compared"] == 0 and cc_trunc["agreement"] is None
          and cc_trunc["this_round_unanswered"] == 36)
    ra = analyse(trav, items, gate, {})["reasoning"]["overall"]
    check("reasoning analysis splits completion tokens by char shares",
          ra["records"] == 36 and ra["mean_reasoning_char_share"] is not None
          and 0.0 <= ra["mean_reasoning_char_share"] <= 1.0)

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
        ident = gate["cross_class_reference"]["identity"]
        print(f"cross-class identity: identical={ident['identical']}, "
              f"mismatches={len(ident['prompt_sha256_mismatches'])}")
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
        if os.path.exists(RAW_PATH):
            raise SystemExit("raw.jsonl already exists; remove it to re-dispatch")
        budget = AttemptBudget(MAX_PROMPTS)
        hc = health_check()
        budget.used += 1
        if not hc["ok"]:
            print(f"health check failed: {hc}", file=sys.stderr)
            return 2
        print(f"health ok: {hc['latency_s']} s, "
              f"{hc['completion_tokens']} completion tokens")
        t0 = time.monotonic()
        records, note = dispatch(items, gate, budget)
        wall = round(time.monotonic() - t0, 1)
        note["health"] = hc
        note["phase2_wall_s"] = wall
        note["total_endpoint_calls_including_health"] = budget.used
        note["attempt_cap"] = MAX_PROMPTS
        with open(os.path.join(HERE, "transport.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(note, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(f"probe wall: {wall} s for {len(records)} cells; total endpoint "
              f"calls incl. health: {budget.used}")
        return 0
    if args.analyze:
        records = [json.loads(l) for l in open(RAW_PATH, encoding="utf-8")
                   if l.strip()]
        transport = {}
        if os.path.exists(os.path.join(HERE, "transport.json")):
            transport = json.load(open(os.path.join(HERE, "transport.json"),
                                       encoding="utf-8"))
        out = analyse(records, items, gate, transport)
        out["gate_hash"] = gate["gate_hash"]
        out["seed_base"] = SEED_BASE
        out["raw_sha256"] = sha256_file(RAW_PATH)
        out["gate_sha256"] = sha256_file(GATE_PATH)
        out["item_source"] = {
            "generator_sha256": sha256_file(LADDERS_PATH),
            "blob_sha256": pool_blob_sha256(),
        }
        with open(SUMMARY_PATH, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(json.dumps(out["arms"], indent=2))
        print(json.dumps(out["per_level"], indent=2))
        print(json.dumps(out["families"], indent=2))
        print(json.dumps(out["signature_table"], indent=2))
        print(json.dumps(out["cross_class"], indent=2))
        print(f"records naming all interior nodes: "
              f"{out['records_naming_all_interior_nodes']}")
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

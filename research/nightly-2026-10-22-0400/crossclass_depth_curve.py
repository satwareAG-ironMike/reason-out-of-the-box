#!/usr/bin/env python3
"""Nightly round 18 (2026-10-22 04:00): the fixed-budget depth curve to
k = 48 on the repaired ladders family, 27B-class local endpoint (refs #71,
#78, #73, #65).

Question. Round 17 ran the matched-pair grid at k = 24, 32, 48 on a
flash-next-class local endpoint at the fixed 2048-token budget: no turnover
within the grid (36/36 answered, all correct), 17 of 36 cells at the budget
ceiling with the answer rescued from the reasoning trace. Round 16 ran the
same corpus at k = 12, 16, 24 on a 27B-class local endpoint: 33/33 answered
cells correct, but the three X cells at k = 24 unanswerable within 2 x 2048
tokens (trace rescue did not transfer across classes in that direction).
This round extends the 27B-class curve to k = 32 and 48 at the same fixed
budget and asks: does the flash-next class's clean deep-level behaviour (all
cells answered, ceiling hit but answer rescued mid-trace) hold on the 27B
class at k = 32 and 48, or does the negative arm X turn over there?

Design. Four-arm matched grid (F1 forward yes, R1 reverse no, F2 interior
forward yes, X cross-component no) over the repaired component-isomorphic
generator (issue #69 repair, merged on main; generators/ladders.py, module
sha pinned below), levels k in {24, 32, 48}, 3 items per level, first usable
items per level at seed_base 20261019 (the round-15 corpus seed). The
selection rule is round 15's rule plus the declared context-safety filter
(prompt_chars <= MAX_PROMPT_CHARS), applied identically at every level.
The grid is byte-identical to round 17's grid (same generator sha, same seed
base, same selection rule); the pairing is verified cell by cell (36 prompt
sha256 values) against the in-tree round-17 raw archive, and --probe refuses
to run when that verification fails. The level-24 cells additionally pair
with the in-tree round-16 raw archive (same class, same budget, same items):
12 prompt sha256 values, fail-closed. The level-24 pairing with round 16
doubles as a temperature-0 rerun test on this class, including the three X
cells that were unanswerable there.

Predictions are declared in the gate before any prompt is spent:
P1 every answered cell correct (budget-limited turnover, per rounds 6, 15,
16, 17); P2 answerability non-increasing in k with at least one strict drop
at 32/48, and at the deepest level the direction arm F1 answers at least as
often as the cross-component arm X; P3 truncated cells die late (median
ordered prefix coverage of the expected traversal >= 0.8), i.e. the budget
runs out near the end of the replay, not in preamble; P4 cross-class answer
agreement: on every cell both classes answered (joined to the round-17
archive on item_id + arm) the answers agree (round 16 vs round 15 at
k <= 24 gave 33/33 agreement, zero discordant pairs).

Outcome classification follows round 15 and issue #73 (answered /
truncated_no_answer / no_answer_stop / empty_completion / transport_* /
abandoned_budget; correctness scored only on answered). Policy inherited from
round 17: truncation is a measured outcome, not a transport failure; retries
are spent only on transport_* and empty_completion, one per cell, under the
global 40-attempt cap that includes the health check. (Round 16 spent two
attempts on its truncated X cells; this round does not, so the level-24 X
anchor rows carry an attempts-count field for exactly that comparison.)

Artifacts: gate.json (pre-registration record, including the anchor- and
cross-class-pairing verification), raw.jsonl (one record per cell,
sanitized raw responses), summary.json (aggregates including the cross-class
join to the round-17 archive), transport.json (dispatch note). run.log stays
local. Stdlib only; the endpoint is read from NIGHTLY_BASE_URL /
NIGHTLY_MODEL_ID / NIGHTLY_API_KEY and no endpoint value is written to any
artifact.

Subcommands:
  --selftest  deterministic controls, no endpoint contact
  --gate      corpus verification, leak battery, exact nulls, anchor and
              cross-class pairing, gate.json
  --probe     the 36-prompt fixed-budget probe against the live endpoint
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
LEVELS = (24, 32, 48)
POOL_PER_LEVEL = 300
ITEMS_PER_LEVEL = 3
ARMS = ("F1", "R1", "F2", "X")
GOLD = {"F1": 1, "R1": 0, "F2": 1, "X": 0}
MAX_PROMPT_CHARS = 45000

MAX_PROMPTS = 40
HEALTH_PROMPTS = 1
MAX_TOKENS = 2048
TEMPERATURE = 0.0
ITEM_DEADLINE_S = 900
LEVEL_BUDGET_S = 1500
PHASE2_BUDGET_S = 2400
CONCURRENCY_CHOICES = (4, 2, 1)

GATE_ALPHA = 0.05
GATE_MIN_ACCURACY = 0.90

GATE_PATH = os.path.join(HERE, "gate.json")
RAW_PATH = os.path.join(HERE, "raw.jsonl")
SUMMARY_PATH = os.path.join(HERE, "summary.json")

# Corpus identity: the repaired generator module (issue #69, merged on main)
# and the three pool blobs that regenerate byte-identically from
# seed_base 20261019. The level-24 pin is round 15's; the level-32/48 pins
# were recorded by the round-17 gate. All three are re-verified here and the
# selftest verifies the double-generation identity.
GENERATOR_SHA256 = "b0d77efd308d249fea77e5fd97e9bef7f5e0fd737b214c2d754cddf970a7f77b"
L24_BLOB_PIN = "cab16fae867b4791290259ffa451231efd73ef193da96664720fd4686fb7008f"
L32_BLOB_PIN = "3781a95da04b90ce0895b0314b7f159fa18f299537e082fa34166abb4075b5ff"
L48_BLOB_PIN = "f4dee382fb3c7be31a6836434e3b1ffe5856bfaaf19f4aa9270e287b36755288"

# Anchor archive: round 16's committed raw responses (same class, same
# budget, same selection rule at seed_base 20261019, levels 12/16/24). The
# 12 L24 cells give a cell-paired rerun anchor and a temperature-0
# reproducibility measurement on this class.
ROUND16_RAW = os.path.join(REPO, "research", "nightly-2026-10-21-0400",
                           "raw.jsonl")
# Cross-class archive: round 17's committed raw responses (flash-next class,
# same grid, same budget, levels 24/32/48). All 36 cells pair on (item_id,
# arm); the join is the round's cross-class comparison.
ROUND17_RAW = os.path.join(REPO, "research", "nightly-2026-10-22-0200",
                           "raw.jsonl")

ANSWER_RE = re.compile(r"\b(yes|no)\b", re.IGNORECASE)
URL_RE = re.compile(
    r"https?://\S+|\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|"
    r"(?:/[A-Za-z0-9_.-]+){2,}|[A-Za-z]:\\[^\s]*"
)
HEALTH_PROMPT = "Reply with exactly one word: yes"

LINEAGE = [
    {"round": 6, "corpus": "repaired family, single-query depth grid "
                           "k = 1..16, open budget",
     "endpoint": "flash-next-class local endpoint",
     "result": "40 of 40 correct, no turnover within k <= 16; completion "
               "tokens = -36 + 80k; fixed-budget replay lost 26/40 items at "
               "256 tokens, 12/40 at 512, 4/40 at 1024",
     "archive": "research/nightly-2026-10-16-0400/ (on main via PR #70)"},
    {"round": 15, "corpus": "repaired matched-pair grid k = 12, 16, 24 at "
                             "max_tokens 2048",
     "result": "36 of 36 answered cells correct; 7 truncations, all negative "
               "arms, all rescued from the reasoning trace; k = 24 answered "
               "12 of 12 with 6 finish_reason = length",
     "archive": "research/nightly-2026-10-21-0200/ (PR #88, open)"},
    {"round": 16, "corpus": "repaired matched-pair grid k = 12, 16, 24, "
                             "cell-paired to round 15; "
                             "level-24 cells anchor this round "
                             "(same class) by prompt sha256",
     "endpoint": "27B-class local endpoint",
     "result": "33 of 33 answered correct; the three X cells at k = 24 "
               "unanswerable within 2 x 2048 tokens (trace rescue did not "
               "transfer across classes)",
     "archive": "research/nightly-2026-10-21-0400/ (PR #89, open)"},
    {"round": 17, "corpus": "repaired matched-pair grid k = 24, 32, 48 at "
                            "max_tokens 2048; all 36 cells pair to this "
                            "round cross-class by prompt sha256",
     "endpoint": "flash-next-class local endpoint",
     "result": "36 of 36 answered cells correct, no turnover inside the "
               "grid; 17 of 36 cells at the 2048 ceiling (all nine X "
               "cells at every level), every one rescued from the "
               "reasoning trace with the answer committed at median "
               "0.457 of the stream",
     "archive": "research/nightly-2026-10-22-0200/ (PR #90, open)"},
]


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
# chain_path and render_prompt are round 15's verbatim (rounds 10/11 too);
# cell pairing at the anchor level depends on this being byte-identical.


def chain_path(rec: list):
    """The directed chain the generated gold-yes query witnesses.

    Returns the node list p_1 .. p_{k+1} or None when the item is not usable:
    the query must be reachable, the path simple, every node on it of
    in-degree <= 1 and out-degree <= 1, and the item must contain a second
    component with a terminal node (in-degree 1, out-degree 0) whose name
    length equals the chain terminal's. Same rule as round 10/11/15.
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
    file order, with the declared context-safety filter prompt_chars <=
    MAX_PROMPT_CHARS applied identically at every level. The grid is
    byte-identical to round 17's grid; at level 24 it reproduces the items
    rounds 15/16 shared (verified by prompt sha256 against the round-16
    archive in verify_anchor and against the round-17 archive in
    verify_crossclass)."""
    recs = load_pool()
    items = []
    scanned = {}
    for level in LEVELS:
        picked = 0
        seen = 0
        skipped_long = 0
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
            if max(len(p) for p in prompts.values()) > MAX_PROMPT_CHARS:
                skipped_long += 1
                continue
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
        scanned[level] = {"scanned": seen, "selected": picked,
                          "skipped_over_char_cap": skipped_long}
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
    Hits = 2K + n - y - a with K ~ Hypergeometric(n, y, a).
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


# ------------------------------------------- anchor and cross-class pairing
# Two in-tree references:
#   round 16 (same class, levels 12/16/24): the 12 L24 cells pair by prompt
#   sha256 and double as a temperature-0 rerun on this class (fail-closed);
#   round 17 (flash-next class, levels 24/32/48): all 36 cells pair by prompt
#   sha256 and carry the round's cross-class comparison (fail-closed).


def load_archive_cells(path: str, levels=None) -> dict:
    """Archive cells keyed by (item_id, arm), optionally level-filtered."""
    if not os.path.exists(path):
        return None
    cells = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            if levels is not None and rec.get("level") not in levels:
                continue
            cells[(rec["item_id"], rec["arm"])] = rec
    return cells


def load_round16_cells():
    """The 12 L24 cells of the round-16 archive (same class, same budget,
    same items: the temperature-0 rerun anchor for this round)."""
    return load_archive_cells(ROUND16_RAW, levels=(24,))


def load_round17_cells():
    """All 36 cells of the round-17 archive (flash-next class, same grid,
    same budget: the cross-class reference)."""
    return load_archive_cells(ROUND17_RAW, levels=(24, 32, 48))


def verify_pairing(items: list, cells: dict, level: int, archive_label: str,
                   archive_path: str) -> dict:
    """Cell-pairing verification against one in-tree archive (fail-closed).

    For the declared anchor level every cell's prompt sha256 must equal the
    archive record's; for the cross-class grid the whole 36-cell set must
    pair (the selection rule is class-independent, so all three levels pair).
    """
    mine = [(it["item_id"], arm) for it in items
            if (level is None or it["level"] == level) for arm in ARMS]
    out = {
        "archive": archive_label,
        "archive_present": cells is not None,
        "archive_sha256": (sha256_file(archive_path) if cells else None),
        "expected_cells": len(mine),
        "prompt_sha_matches": 0,
        "mismatches": [],
        "verified": False,
    }
    if not cells:
        return out
    by_item = {it["item_id"]: it for it in items}
    for key in mine:
        item_id, arm = key
        ref = cells.get(key)
        if ref is None or ref["prompt_sha256"] \
                != by_item[item_id]["arms"][arm]["prompt_sha256"]:
            out["mismatches"].append(list(key))
        else:
            out["prompt_sha_matches"] += 1
    out["verified"] = (out["prompt_sha_matches"] == out["expected_cells"]
                       and not out["mismatches"])
    return out


def verify_anchor(items: list) -> dict:
    """Cell-pairing verification against the round-16 archive (fail-closed).

    The anchor claim is: at level 24 this round dispatches exactly round 16's
    12 cells (identical prompt sha256), on the same endpoint class at the
    same fixed budget, so agreement/disagreement is a temperature-0 rerun
    statement, not a fresh-depth statement.
    """
    return verify_pairing(items, load_round16_cells(), 24,
                          "research/nightly-2026-10-21-0400/raw.jsonl",
                          ROUND16_RAW)


def verify_crossclass(items: list) -> dict:
    """Cell-pairing verification against the round-17 archive (fail-closed).

    The grid is declared byte-identical to round 17's grid (same generator
    sha, same seed base, same selection rule); the 36 prompt sha256 values
    must all pair, and --probe refuses to run when they do not.
    """
    return verify_pairing(items, load_round17_cells(), None,
                          "research/nightly-2026-10-22-0200/raw.jsonl",
                          ROUND17_RAW)


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
    blobs = pool_blob_sha256()
    anchor = verify_anchor(items)
    cross = verify_crossclass(items)
    return {
        "schema": "round18-gate-v1",
        "seed_base": SEED_BASE,
        "gate_hash": None,
        "alpha": GATE_ALPHA,
        "bonferroni_alpha": round(bonf, 12),
        "min_accuracy": GATE_MIN_ACCURACY,
        "question": "Does the flash-next class's clean deep-level "
                    "behaviour at the fixed 2048-token budget (round 17: "
                    "every cell answered, ceiling cells rescued from the "
                    "reasoning trace) hold on the 27B-class endpoint at "
                    "k = 32 and 48, or does the cross-component arm X turn "
                    "over there, and if so is the turnover an answerability "
                    "(budget) collapse with answered cells still correct or "
                    "a correctness collapse?",
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
            "generator_sha256_pin": GENERATOR_SHA256,
            "generate_items": {f"level {lvl}": f"count {POOL_PER_LEVEL}, "
                              f"seed_base {SEED_BASE}" for lvl in LEVELS},
            "blob_sha256": blobs,
            "blob_pin_checks": {
                "l24": {"note": "round-15 pin (repaired generator, "
                                "byte-identical regeneration from "
                                "seed_base 20261019)",
                        "expected": L24_BLOB_PIN,
                        "actual": blobs.get("generated/l24.jsonl")},
                "l32": {"note": "round-17 pin (new at this seed base in "
                                "round 17, re-verified here)",
                        "expected": L32_BLOB_PIN,
                        "actual": blobs.get("generated/l32.jsonl")},
                "l48": {"note": "round-17 pin (new at this seed base in "
                                "round 17, re-verified here)",
                        "expected": L48_BLOB_PIN,
                        "actual": blobs.get("generated/l48.jsonl")},
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
                      "terminal, and every rendered arm prompt within "
                      f"MAX_PROMPT_CHARS = {MAX_PROMPT_CHARS} (context-safety "
                      "filter, applied identically at every level)",
        },
        "anchor_pairing": anchor,
        "cross_class_pairing": cross,
        "cross_round_reference": {
            "purpose": "the grid is byte-identical to round 17's grid "
                       "(same generator sha, same seed base, same "
                       "selection rule): all 36 cells pair cross-class to "
                       "the round-17 archive (flash-next class), and the "
                       "level-24 cells additionally pair to the round-16 "
                       "archive (this class) as a temperature-0 rerun, "
                       "including the three X cells that were unanswerable "
                       "there. Rounds 10/11/14 ran the pre-repair corpus; "
                       "round 6 shares the family with a single-query "
                       "design on the flash-next class.",
            "anchor_paired_to_round16_level24": anchor["verified"],
            "cross_class_paired_to_round17": cross["verified"],
            "lineage": LINEAGE,
            "endpoint_classes": "this round: 27B-class local endpoint "
                                "(self-hosted, public class name only)",
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
            "retries": "one retry per cell, transport_* and empty_completion "
                       "outcomes only (round-17 policy, inherited: truncation "
                       "is a measured outcome, never retried; round 16 spent "
                       "two attempts on its truncated X cells, this round "
                       "does not), global attempt cap enforced",
        },
        "transport_policy": {
            "health_check": "one trivial completion, verified non-empty and "
                            "answer-parseable, before any grid prompt "
                            "(issue #73)",
            "measurement": "the first two grid cells dispatch sequentially; "
                           "their wall times measure the endpoint; per-item "
                           "estimate is max(wall_0, wall_1) * 2.0 (depth "
                           "factor for the k = 48 items); both calls count "
                           "in the 40-attempt cap",
            "concurrency_rule": "largest of {4, 2, 1} such that "
                                "estimate * remaining / concurrency * 1.25 "
                                "<= phase2_budget_s; ties to the smaller "
                                "concurrency; the measured values and the "
                                "choice are recorded in summary.json",
            "level_budget": "each level group is dispatched as a group with "
                            "a LEVEL_BUDGET_S wall budget from group start; "
                            "cells that would start after the group deadline "
                            "or the phase-2 deadline are written with "
                            "outcome abandoned_budget and are never scored "
                            "(issue #73: a killed arm is not a result)",
            "raw_archive": "incremental: one flushed raw.jsonl line per "
                           "completed cell, fsynced (issue #73)",
            "fail_closed": "--probe refuses to run unless the anchor "
                           "pairing verification passes 12 of 12 against the "
                           "in-tree round-16 archive and the cross-class "
                           "pairing passes 36 of 36 against the in-tree "
                           "round-17 archive",
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
            "note": "correctness is scored only on answered cells",
        },
        "new_measurements": {
            "expected_traversal": "F1: the full witnessed path p_0..p_k; "
                                  "F2 and X: p_1..p_k (the queried source "
                                  "component from the query source); R1: "
                                  "undefined (its query source is a path "
                                  "tail with no out-edge), recorded as null",
            "ordered_prefix_hops": "length of the longest prefix of the "
                                   "expected traversal whose entity names "
                                   "appear in order in reasoning+content "
                                   "(substring matching, the round-15 "
                                   "recitation convention)",
            "coverage_ratio": "ordered_prefix_hops / expected length, "
                              "computed on truncated F1/F2/X cells (P3)",
            "headroom_tokens": "MAX_TOKENS - completion_tokens on answered "
                               "cells",
            "commit_fraction": "answer_offset / reasoning length when the "
                               "answer came from the reasoning field on a "
                               "finish_reason = length completion (where in "
                               "the stream the decision was made)",
        },
        "predictions": {
            "declared_before_first_prompt": True,
            "P1_correctness_holds": "every answered cell is correct "
                                    "(budget-limited turnover; rounds 6, "
                                    "15, 16 and 17 mechanism)",
            "P2_answerability_decay": "answered fraction is non-increasing "
                                      "in k across (24, 32, 48) with at "
                                      "least one strict drop at 32 or 48, "
                                      "and at the deepest level with any "
                                      "truncation F1 answered >= X answered",
            "P3_truncation_is_late": "the median coverage_ratio of the "
                                     "expected traversal over truncated "
                                     "F1/F2/X cells is >= 0.8 (the budget "
                                     "dies near the end of the replay, not "
                                     "in preamble)",
            "P4_cross_class_agreement": "on every cell both classes answered "
                                        "(joined to the round-17 archive "
                                        "on item_id + arm) the answers "
                                        "agree (round 16 vs round 15 at "
                                        "k <= 24 gave 33 of 33 agreement, "
                                        "zero discordant pairs)",
            "falsification_reading": "P1 failing at a level with >= 8 "
                                     "answered cells is a correctness "
                                     "ceiling inside (24, 48] for this "
                                     "(family, endpoint, budget)",
            "turnover_rule": "no_turnover_within_grid if every level "
                             "answers 12 of 12 with all correct; "
                             "budget_turnover if every answered cell is "
                             "correct and some level answers fewer than 12; "
                             "correctness_turnover if some level has wrong "
                             "answered cells and every level answers >= 6; "
                             "mixed otherwise",
        },
        "primary_statistic": {
            "test": "two-sided exact McNemar on the matched (F1, R1) pairs",
            "secondary": "two-sided exact McNemar on the matched (F2, X) pairs",
            "unit": "item",
            "n_pairs": len(items),
        },
        "corpus_identity_primary": {
            "statistic": "the generator module sha256 and the three pool "
                         "blob hashes pin this round's corpus; the anchor "
                         "adds 12 prompt sha256 equalities against the "
                         "round-16 archive and the cross-class pairing "
                         "adds 36 against the round-17 archive",
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


def is_retryable(outcome: str) -> bool:
    """Declared retry policy: only transport failures and empty completions
    are retried; truncation and model stops are measured outcomes."""
    return outcome == "empty_completion" or outcome.startswith("transport_")


def outcome_of(rec: dict) -> str:
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
    return {"ok": ok, "outcome": cls, "latency_s": latency,
            "completion_tokens": resp["completion_tokens"],
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
    """One cell: a second attempt only when the first classifies as
    retryable (transport or empty), under the global cap."""
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
        if not is_retryable(classify_attempt(att)):
            break
    last = rec["attempts"][-1] if rec["attempts"] else None
    rec["answer"] = last["answer"] if last else None
    rec["answer_source"] = last["answer_source"] if last else "none"
    rec["answer_offset"] = last["answer_offset"] if last else -1
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
    then the remaining cells at the policy-declared concurrency. Per-level
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


def expected_traversal(item: dict, arm: str):
    if arm == "F1":
        return list(item["path"])
    if arm in ("F2", "X"):
        return list(item["path"][1:])
    return None  # R1: query source is a path tail


def ordered_prefix_hops(seq, text: str) -> int:
    pos = -1
    hops = 0
    for node in seq:
        idx = text.find(node, pos + 1)
        if idx < 0:
            return hops
        pos = idx
        hops += 1
    return hops


def cell_mechanics(rec: dict, item: dict) -> dict:
    """Per-cell budget mechanics on the last attempt."""
    if not rec["attempts"]:
        return {}
    att = rec["attempts"][-1]
    text = (att.get("reasoning") or "") + " " + (att.get("content") or "")
    seq = expected_traversal(item, rec["arm"])
    hops = ordered_prefix_hops(seq, text) if seq else None
    out = {
        "ordered_prefix_hops": hops,
        "expected_hops": len(seq) if seq else None,
        "coverage_ratio": (round(hops / len(seq), 4)
                           if seq and hops is not None else None),
        "completion_tokens": att["completion_tokens"],
        "headroom_tokens": MAX_TOKENS - att["completion_tokens"],
    }
    if rec["answer"] is not None and att["finish_reason"] == "length" \
            and rec["answer_source"] == "reasoning":
        rlen = max(1, len(att.get("reasoning") or ""))
        offset = att.get("answer_offset", rec.get("answer_offset", -1))
        if offset >= 0:
            out["commit_fraction"] = round(offset / rlen, 4)
    return out


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


def turnover_classification(per_level: dict) -> str:
    answered = [per_level[str(k)]["answered"] for k in LEVELS]
    correct = [per_level[str(k)]["correct"] for k in LEVELS]
    wrong = sum(a - c for a, c in zip(answered, correct))
    if wrong > 0:
        if all(a >= 6 for a in answered):
            return "correctness_turnover"
        return "mixed"
    if all(a == per_level[str(LEVELS[0])]["cells"] for a in answered):
        return "no_turnover_within_grid"
    return "budget_turnover"


def token_law(records: list, items: list) -> dict:
    """Least-squares completion_tokens ~ a + b*k over answered F1/F2 cells
    with a stop completion (truncated cells censored and reported
    separately)."""
    by_item = {i["item_id"]: i for i in items}
    pts = []
    censored = []
    for r in records:
        if r["arm"] not in ("F1", "F2") or not r["attempts"]:
            continue
        att = r["attempts"][-1]
        k = r["level"]
        if r["answer"] is not None and att["finish_reason"] != "length":
            pts.append((k, att["completion_tokens"]))
        elif att["finish_reason"] == "length":
            censored.append((k, att["completion_tokens"]))
    out = {"answered_stop_cells": len(pts),
           "censored_truncated_cells": len(censored)}
    if len(pts) >= 3:
        n = len(pts)
        sx = sum(k for k, _ in pts)
        sy = sum(t for _, t in pts)
        sxx = sum(k * k for k, _ in pts)
        sxy = sum(k * t for k, t in pts)
        denom = n * sxx - sx * sx
        b = (n * sxy - sx * sy) / denom
        a = (sy - b * sx) / n
        mx, my = sx / n, sy / n
        sxx_dev = sum((k - mx) ** 2 for k, _ in pts)
        syy_dev = sum((t - my) ** 2 for _, t in pts)
        corr = ((sum((k - mx) * (t - my) for k, t in pts) /
                 math.sqrt(sxx_dev * syy_dev)) if sxx_dev and syy_dev else None)
        out.update({"intercept": round(a, 3), "slope_tokens_per_hop": round(b, 3),
                    "pearson_r": round(corr, 4) if corr is not None else None})
    return out


def anchor_analysis(items: list) -> dict:
    """Cell-paired rerun comparison against the round-16 archive.

    Same class, same budget, same L24 items: agreement/disagreement is a
    temperature-0 rerun statement. The round-16 truncated X cells spent two
    attempts (that round's retry policy); this round declares no retry on
    truncation, so the rows record both sides' attempt counts.
    """
    cells = load_round16_cells()
    if cells is None:
        return {"available": False}
    try:
        mine = [json.loads(l) for l in open(RAW_PATH, encoding="utf-8")
                if l.strip()]
    except FileNotFoundError:
        return {"available": False, "note": "raw.jsonl not written yet"}
    by = {(r["item_id"], r["arm"]): r for r in mine if r["level"] == 24}
    rows = []
    agree = 0
    for key, ref in sorted(cells.items()):
        rec = by.get(key)
        if rec is None:
            continue
        same_ans = (rec["answer"] == ref["answer"])
        agree += int(same_ans)
        rows.append({
            "cell": list(key),
            "answer_this": rec["answer"], "answer_round16": ref["answer"],
            "outcome_this": rec["outcome"], "outcome_round16": ref.get("outcome"),
            "attempts_this": len(rec["attempts"]),
            "attempts_round16": len(ref.get("attempts") or []),
            "completion_tokens_this":
                (rec["attempts"][-1]["completion_tokens"] if rec["attempts"] else None),
            "completion_tokens_round16":
                (ref["attempts"][-1]["completion_tokens"] if ref.get("attempts") else None),
            "answer_agrees": same_ans,
        })
    return {"available": True, "cells": len(rows), "answer_agreements": agree,
            "note": "round 16 spent two attempts on its truncated X cells; "
                    "this round declares no retry on truncation (the row "
                    "attempts fields make the asymmetry explicit)",
            "rows": rows}


def join_crossclass(records: list, ref_records: list) -> dict:
    """Pure join of this round's cells with the round-17 archive on
    (item_id, arm).

    Both archives are declared the same 36-cell grid (same prompts, verified
    fail-closed before dispatch), so the join is a cross-class comparison at
    the fixed 2048-token budget. P4 is the all-agreement statement over the
    cells both classes answered; an exact McNemar over the both-answered
    correct/incorrect outcomes is reported as the paired test.
    """
    ref = {(r["item_id"], r["arm"]): r for r in ref_records}
    rows = []
    for r in records:
        rec_ref = ref.get((r["item_id"], r["arm"]))
        if rec_ref is None:
            continue
        both = r["answer"] is not None and rec_ref["answer"] is not None
        agree = (r["answer"] == rec_ref["answer"]) if both else None
        rows.append({
            "cell": [r["item_id"], r["arm"]],
            "level": r["level"],
            "answer_this": r["answer"], "answer_round17": rec_ref["answer"],
            "outcome_this": r["outcome"], "outcome_round17": rec_ref.get("outcome"),
            "both_answered": both,
            "answer_agrees": agree,
            "correct_this": r.get("correct"),
            "correct_round17": rec_ref.get("correct"),
            "answer_source_this": r.get("answer_source"),
            "answer_source_round17": rec_ref.get("answer_source"),
            "completion_tokens_this":
                (r["attempts"][-1]["completion_tokens"]
                 if r.get("attempts") else None),
            "completion_tokens_round17":
                (rec_ref["attempts"][-1]["completion_tokens"]
                 if rec_ref.get("attempts") else None),
        })
    joined = len(rows)
    both_rows = [row for row in rows if row["both_answered"]]
    agree_n = sum(1 for row in both_rows if row["answer_agrees"])
    b_ct = c_ct = 0
    for row in both_rows:
        if row["correct_this"] is None or row["correct_round17"] is None:
            continue
        if row["correct_this"] == 0 and row["correct_round17"] == 1:
            b_ct += 1
        elif row["correct_this"] == 1 and row["correct_round17"] == 0:
            c_ct += 1
    by_arm = {arm: {"this": [], "round17": []} for arm in ARMS}
    for row in rows:
        arm = row["cell"][1]
        if row["completion_tokens_this"] is not None:
            by_arm[arm]["this"].append(row["completion_tokens_this"])
        if row["completion_tokens_round17"] is not None:
            by_arm[arm]["round17"].append(row["completion_tokens_round17"])
    mean_tokens = {arm: {
        "this": (round(sum(v["this"]) / len(v["this"]), 3)
                 if v["this"] else None),
        "round17": (round(sum(v["round17"]) / len(v["round17"]), 3)
                    if v["round17"] else None),
    } for arm, v in by_arm.items()}
    trunc = {arm: {
        "this": sum(1 for r in records if r["arm"] == arm
                    and outcome_of(r) == "truncated_no_answer"),
        "round17": sum(1 for r in ref_records if r["arm"] == arm
                       and outcome_of(r) == "truncated_no_answer"),
    } for arm in ARMS}
    return {
        "reference": "research/nightly-2026-10-22-0200/raw.jsonl",
        "reference_class": "flash-next-class local endpoint (round 17)",
        "this_class": "27B-class local endpoint (this round)",
        "joined_cells": joined,
        "both_answered": len(both_rows),
        "answer_agreements": agree_n,
        "answer_disagreements": len(both_rows) - agree_n,
        "only_this_answered": sum(1 for row in rows
                                  if row["answer_this"] is not None
                                  and row["answer_round17"] is None),
        "only_round17_answered": sum(1 for row in rows
                                     if row["answer_this"] is None
                                     and row["answer_round17"] is not None),
        "mean_completion_tokens_by_arm": mean_tokens,
        "truncation_counts_by_arm": trunc,
        "reasoning_rescues_this": sum(1 for r in records
                                      if r.get("answer_source") == "reasoning"),
        "reasoning_rescues_round17": sum(
            1 for r in ref_records if r.get("answer_source") == "reasoning"),
        "both_answered_mcnemar": {
            "b_this_wrong_round17_right": b_ct,
            "c_this_right_round17_wrong": c_ct,
            "p_exact_mcnemar": mcnemar_exact(b_ct, c_ct),
        },
        "rows": rows,
    }


def crossclass_analysis(records: list) -> dict:
    """Join this round's archived cells with the in-tree round-17 archive."""
    cells = load_round17_cells()
    if cells is None:
        return {"available": False}
    out = join_crossclass(records, list(cells.values()))
    out["available"] = True
    out["archive_sha256"] = sha256_file(ROUND17_RAW)
    return out


def analyse(records: list, items: list, gate: dict, transport: dict) -> dict:
    by = {(r["item_id"], r["arm"]): r for r in records}
    mech = {(r["item_id"], r["arm"]): cell_mechanics(r, next(
        i for i in items if i["item_id"] == r["item_id"])) for r in records}
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
        }
    per_level = {}
    for level in LEVELS:
        got = [r for r in records if r["level"] == level]
        answered = [r for r in got if r["answer"] is not None]
        correct = sum(1 for r in answered if r["correct"] == 1)
        lo, hi = wilson(correct, len(answered)) if answered else (0.0, 0.0)
        trunc_cov = [mech[(r["item_id"], r["arm"])]["coverage_ratio"]
                     for r in got
                     if outcome_of(r) == "truncated_no_answer"
                     and mech[(r["item_id"], r["arm"])].get("coverage_ratio") is not None]
        head = [mech[(r["item_id"], r["arm"])]["headroom_tokens"]
                for r in answered]
        cts = [r["attempts"][-1]["completion_tokens"] for r in got if r["attempts"]]
        per_level[str(level)] = {
            "cells": len(got), "answered": len(answered), "correct": correct,
            "accuracy_answered": round(correct / len(answered), 6) if answered else None,
            "wilson95": [round(lo, 6), round(hi, 6)],
            "outcomes": dict(collections.Counter(outcome_of(r) for r in got)),
            "answered_per_arm": {arm: sum(1 for r in got if r["arm"] == arm
                                          and r["answer"] is not None)
                                 for arm in ARMS},
            "mean_completion_tokens": round(sum(cts) / len(cts), 3) if cts else None,
            "max_completion_tokens": max(cts) if cts else None,
            "median_truncation_coverage_ratio":
                round(sorted(trunc_cov)[len(trunc_cov) // 2], 4) if trunc_cov else None,
            "mean_headroom_answered": round(sum(head) / len(head), 3) if head else None,
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
    answered_cells = [r for r in records if r["answer"] is not None]
    commit_fr = [mech[(r["item_id"], r["arm"])].get("commit_fraction")
                 for r in answered_cells
                 if mech[(r["item_id"], r["arm"])].get("commit_fraction") is not None]
    cross = crossclass_analysis(records)
    pred = evaluate_predictions(per_level, mech, records,
                                 crossclass=cross)
    return {
        "arms": arms,
        "per_level": per_level,
        "families": families,
        "signature_table": signature_of(by, items),
        "turnover_classification": turnover_classification(per_level),
        "predictions": pred,
        "token_law": token_law(records, items),
        "anchor_vs_round16": anchor_analysis(items),
        "cross_class_vs_round17": cross,
        "mid_stream_commitment": {
            "answered_cells": len(answered_cells),
            "reasoning_rescues": sum(1 for r in answered_cells
                                     if r["answer_source"] == "reasoning"),
            "median_commit_fraction": round(sorted(commit_fr)[len(commit_fr) // 2], 4)
                                      if commit_fr else None,
            "max_commit_fraction": round(max(commit_fr), 4) if commit_fr else None,
        },
        "records_naming_all_interior_nodes": chain_recite,
        "records": len(records),
        "transport": transport,
    }


def evaluate_predictions(per_level: dict, mech: dict, records: list,
                         crossclass: dict = None) -> dict:
    fr = [per_level[str(k)]["answered"] / max(1, per_level[str(k)]["cells"])
          for k in LEVELS]
    p1 = all(per_level[str(k)]["correct"] == per_level[str(k)]["answered"]
             for k in LEVELS)
    monotone = all(fr[i + 1] <= fr[i] for i in range(len(fr) - 1))
    strict = any(fr[i + 1] < fr[i] for i in range(len(fr) - 1))
    deep = str(LEVELS[-1])
    arm_ans = per_level[deep]["answered_per_arm"]
    p2 = bool(monotone and strict and arm_ans.get("F1", 0) >= arm_ans.get("X", 0))
    cov = [mech[(r["item_id"], r["arm"])].get("coverage_ratio")
           for r in records
           if outcome_of(r) == "truncated_no_answer"
           and mech[(r["item_id"], r["arm"])].get("coverage_ratio") is not None]
    p3 = (round(sorted(cov)[len(cov) // 2], 4) if cov else None)
    p4 = None
    if crossclass is not None and crossclass.get("available") \
            and crossclass.get("both_answered"):
        p4 = crossclass["answer_agreements"] == crossclass["both_answered"]
    return {
        "P1_correctness_holds": bool(p1),
        "P2_answerability_decay": p2,
        "P2_answered_fraction_by_level": {str(k): round(v, 4)
                                          for k, v in zip(LEVELS, fr)},
        "P3_median_truncation_coverage": p3,
        "P3_threshold": 0.8,
        "P3_supported": (p3 >= 0.8) if p3 is not None else None,
        "P4_cross_class_agreement": p4,
        "P4_note": "None is vacuous (reference archive absent, or no cell "
                   "answered on both classes)",
    }


# ------------------------------------------------------------------ selftest


def selftest() -> int:
    fails = []

    def check(name, ok):
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            fails.append(name)

    # arithmetic controls
    lo, hi = wilson(0, 0)
    check("wilson on 0 of 0 is (0, 0)", lo == 0.0 and hi == 0.0)
    lo, hi = wilson(9, 9)
    check("wilson 9/9 lower bound is round 15's 0.701", abs(lo - 0.701) < 0.001)
    check("mcnemar exact on 9 versus 0 is 2*2^-9",
          abs(mcnemar_exact(9, 0) - 0.00390625) < 1e-12)
    check("mcnemar exact with no discordance is 1.0", mcnemar_exact(0, 0) == 1.0)
    check("mcnemar exact on 4 versus 6 is 2*P(Bin(10,0.5)<=4)=0.75390625",
          abs(mcnemar_exact(4, 6) - 0.75390625) < 1e-9)
    check("log_choose(5, 2) is 10", abs(math.exp(log_choose(5, 2)) - 10) < 1e-9)

    # declared parser
    a, s, o = parse_answer("No.", "reasoning blah")
    check("parser takes the last content token over the reasoning field",
          a == "no" and s == "content" and o == 0)
    a, s, o = parse_answer("", "walk on... NO, unreachable")
    check("parser falls back to reasoning (case-insensitive) and marks it",
          a == "no" and s == "reasoning" and o == 11)
    a, s, o = parse_answer("maybe yes then no", "no")
    check("parser keeps the LAST content match", a == "no")
    a, s, o = parse_answer("yep", "perhaps")
    check("parser returns None when neither field carries yes/no",
          a is None and s == "none")
    a, s, o = parse_answer("the answer is Yes", "")
    check("parser lower-cases yes", a == "yes")
    a, s, o = parse_answer("noe", "the no network stands")
    check("parser ignores 'noe' and takes the standalone 'no'",
          a == "no" and s == "reasoning")

    # sanitizer (public-only rule)
    check("sanitizer strips URLs, IPv4-like strings, paths and drive paths",
          "[redacted]" in sanitize("see https://example.invalid/x")
          and "[redacted]" in sanitize("host 10.64.1.2 down")
          and "[redacted]" in sanitize("loaded /srv/models/name.bin here")
          and "[redacted]" in sanitize("path C:\\Models\\x.bin end"))
    check("sanitizer leaves ordinary prose untouched",
          sanitize("the chain has 32 hops") == "the chain has 32 hops")

    # outcome classification and the declared retry policy
    def att(**kw):
        base = {"error_class": None, "completion_tokens": 10, "answer": "yes",
                "finish_reason": "stop"}
        base.update(kw)
        return base
    check("classify: answered", classify_attempt(att()) == "answered")
    check("classify: truncated_no_answer",
          classify_attempt(att(answer=None, finish_reason="length"))
          == "truncated_no_answer")
    check("classify: no_answer_stop",
          classify_attempt(att(answer=None, finish_reason="stop"))
          == "no_answer_stop")
    check("classify: empty_completion",
          classify_attempt(att(completion_tokens=0)) == "empty_completion")
    check("classify: transport class",
          classify_attempt(att(error_class="http_500")) == "transport_http_500")
    check("retry: truncation is NOT retryable (declared refinement)",
          not is_retryable("truncated_no_answer")
          and not is_retryable("no_answer_stop")
          and is_retryable("transport_timeout") and is_retryable("empty_completion"))

    # corpus construction and invariants
    recs = load_pool()
    pool = verify_pool(recs)
    items = build_matched_items()
    inv = matched_invariant(items)
    check("generated pool gold equals recomputed directed reachability",
          not pool["gold_reach_mismatches"])
    check("generated pool has zero cells where connectivity and reachability "
          "disagree",
          pool["cells_where_connectivity_and_reachability_disagree"] == 0)
    check("generated pool is 900 items over levels 24, 32, 48",
          pool["items_total"] == 900 and set(pool["levels"]) ==
          {"24", "32", "48"})
    check("generation is byte-identical across calls (blob hashes match twice)",
          pool_blob_sha256() == pool_blob_sha256())
    blobs = pool_blob_sha256()
    check("level-24 blob equals the round-15 pin (byte-identical "
          "regeneration from seed_base 20261019)",
          blobs["generated/l24.jsonl"] == L24_BLOB_PIN)
    check("level-32 and 48 blobs equal the round-17 pins",
          blobs["generated/l32.jsonl"] == L32_BLOB_PIN
          and blobs["generated/l48.jsonl"] == L48_BLOB_PIN)
    check("generator module hash equals the round-15 pin (issue #69 repair)",
          sha256_file(LADDERS_PATH) == GENERATOR_SHA256)
    check("matched-pair invariant holds with zero violations",
          not inv["violations"])
    check("matched corpus has nine cells where connectivity and reachability "
          "disagree (the R1 cells)",
          sum(1 for i in items for a in ARMS
              if i["arms"][a]["same_component"] != i["arms"][a]["directed_reach"])
          == len(items))
    check("matched corpus gold is balanced 18 yes / 18 no",
          sum(i["arms"][a]["gold"] for i in items for a in ARMS) == 18)
    check("every matched family arm pair has identical prompt length",
          all(i["arms"][a]["prompt_chars"] == i["arms"][b]["prompt_chars"]
              for i in items for a, b in (("F1", "R1"), ("F2", "X"))))
    check("the cross-component arm X is unreachable in the undirected graph",
          all(i["arms"]["X"]["undirected_hops"] == -1 for i in items))
    check("matched chain lengths equal the item levels",
          sorted(i["chain_len"] for i in items) == [24, 24, 24, 32, 32, 32,
                                                    48, 48, 48])
    check("every selected arm prompt is within the declared char cap",
          all(i["arms"][a]["prompt_chars"] <= MAX_PROMPT_CHARS
              for i in items for a in ARMS))
    check("the selection scanned deep levels",
          all(any(r["_level"] == lvl for r in recs) for lvl in LEVELS))
    check("the battery holds 15 direction-blind rules and 2 chain references",
          len(LEAK_RULES) == 15 and len(REFERENCE_RULES) == 2)

    # leak battery on the matched corpus: repair still holds at deep levels
    mb = battery_on_matched(items)
    check("the directed_reachability reference scores 36 of 36",
          mb["directed_reachability"]["accuracy"] == 1.0)
    check("no direction-blind rule reaches the accuracy bar on the matched "
          "corpus",
          max(mb[r]["accuracy"] for r in LEAK_RULES) < GATE_MIN_ACCURACY)
    check("the pre-repair leak rule target_is_fact_target stays below the "
          "accuracy bar at the deep levels (structurally 27/36 on the "
          "matched corpus: it misses exactly the X cells)",
          mb["target_is_fact_target"]["accuracy"] < GATE_MIN_ACCURACY)
    mn = exact_null_matched("target_is_fact_target", items,
                            mb["target_is_fact_target"]["correct"])
    check("the matched-corpus exact null is centered near the observed count",
          abs(mn["null_mean"] - mn["observed_hits"]) <= 9.0)

    # anchor pairing against the in-tree round-16 archive (same class)
    anchor = verify_anchor(items)
    check("the round-16 anchor archive is present", anchor["archive_present"])
    check("anchor pairing verifies 12 of 12 prompt sha256 against round 16",
          anchor["verified"] and anchor["prompt_sha_matches"] == 12)
    check("anchor mismatches list is empty", not anchor["mismatches"])

    # cross-class pairing against the in-tree round-17 archive
    cross = verify_crossclass(items)
    check("the round-17 cross-class archive is present",
          cross["archive_present"])
    check("cross-class pairing verifies 36 of 36 prompt sha256 against "
          "round 17",
          cross["verified"] and cross["prompt_sha_matches"] == 36)
    check("cross-class mismatches list is empty", not cross["mismatches"])

    # budget-mechanics metric controls
    item = items[0]
    path = item["path"]
    text_full = "walking: " + " -> ".join(path) + " done"
    check("ordered prefix on the full chain is k",
          ordered_prefix_hops(path, text_full) == len(path))
    cut = len(path) // 2
    text_cut = "walking: " + " -> ".join(path[:cut])
    check("ordered prefix on a cut chain is the cut length",
          ordered_prefix_hops(path, text_cut) == cut)
    rev = " -> ".join(reversed(path))
    check("ordered prefix on the reversed chain is 1 (only the head matches "
          "in place)", ordered_prefix_hops(path, rev) == 1)
    check("ordered prefix on unrelated text is 0",
          ordered_prefix_hops(path, "nothing here") == 0)
    check("expected traversal: F1 full path, F2/X drop the head, R1 null",
          expected_traversal(item, "F1") == path
          and expected_traversal(item, "F2") == path[1:]
          and expected_traversal(item, "X") == path[1:]
          and expected_traversal(item, "R1") is None)

    # token law control: synthetic linear data recovers the slope
    fake = [{"item_id": it["item_id"], "arm": "F1", "level": it["level"],
             "answer": "yes", "outcome": "answered", "attempts": [
                 {"completion_tokens": 500 + 60 * it["level"],
                  "finish_reason": "stop", "content": "yes",
                  "reasoning": ""}]}
            for it in items]
    tl = token_law(fake, items)
    check("token law on synthetic linear data recovers slope 60",
          abs(tl["slope_tokens_per_hop"] - 60) < 1e-6
          and abs(tl["intercept"] - 500) < 1e-6)

    # turnover classifier controls
    def fake_per(answered, wrong_levels=()):
        pl = {}
        for k in LEVELS:
            a = answered[k]
            c = a - (1 if k in wrong_levels else 0)
            pl[str(k)] = {"cells": 12, "answered": a, "correct": c}
        return pl
    check("turnover rule: all answered, all correct -> no_turnover",
          turnover_classification(fake_per({24: 12, 32: 12, 48: 12}))
          == "no_turnover_within_grid")
    check("turnover rule: fewer answered, none wrong -> budget_turnover",
          turnover_classification(fake_per({24: 12, 32: 9, 48: 3}))
          == "budget_turnover")
    check("turnover rule: wrong answered cells at every level -> "
          "correctness_turnover",
          turnover_classification(fake_per({24: 12, 32: 10, 48: 8},
                                           wrong_levels=(48,)))
          == "correctness_turnover")
    check("turnover rule: wrong cells with a starved level -> mixed",
          turnover_classification(fake_per({24: 12, 32: 12, 48: 3},
                                           wrong_levels=(48,)))
          == "mixed")

    # fabrication controls through the analyse path
    gate = {"gate_hash": "selftest"}

    def fake_records(answer_fn, reasoning_fn):
        out = []
        for it in items:
            for arm in ARMS:
                ans = answer_fn(arm, it)
                txt = reasoning_fn(it, arm)
                out.append({"item_id": it["item_id"], "arm": arm,
                            "level": it["level"], "answer": ans,
                            "answer_source": "content" if ans else "none",
                            "answer_offset": 0,
                            "outcome": "answered" if ans else
                                       "truncated_no_answer",
                            "correct": (None if ans is None else int(
                                (1 if ans == "yes" else 0)
                                == it["arms"][arm]["gold"])),
                            "src": it["arms"][arm]["src"],
                            "dst": it["arms"][arm]["dst"],
                            "attempts": [{"completion_tokens": 10,
                                          "finish_reason": "stop",
                                          "content": ans or "",
                                          "answer": ans,
                                          "reasoning": txt, "wall_s": 1.0}]})
        return out

    trav = fake_records(lambda arm, it: "yes" if it["arms"][arm]["gold"]
                        else "no", lambda it, arm: " ".join(it["path"]))
    trav_full = analyse(trav, items, gate, {})
    sig = trav_full["signature_table"]
    check("traversal-consistent fabrication matches 36 of 36 cells",
          sig["traversal"]["cells_matching"] == 36)
    check("connectivity oracle fails the traversal-consistent fabrication on "
          "exactly the nine R1 cells",
          sig["connectivity"]["cells_matching"] == 27)
    yesfake = fake_records(lambda arm, it: "yes", lambda it, arm: "yes")
    sig3 = analyse(yesfake, items, gate, {})
    check("an always-yes fabricated model scores 18 of 36, not 36 of 36",
          sum(sig3["arms"][a]["correct"] for a in ARMS) == 18)
    connfake = fake_records(lambda arm, it: "yes" if arm in ("F1", "R1",
                                                              "F2") else "no",
                            lambda it, arm: "")
    sig2 = analyse(connfake, items, gate, {})
    check("a connectivity-consistent fabrication yields 9 discordant "
          "direction pairs with exact McNemar below 0.01",
          sig2["families"]["direction_F1_R1"]["c_second_wrong"] == 9
          and sig2["families"]["direction_F1_R1"]["p_exact_mcnemar"] < 0.01)
    check("a traversal-consistent fabrication yields zero discordant pairs",
          trav_full["families"]["direction_F1_R1"]["b_first_wrong"] == 0
          and trav_full["families"]["direction_F1_R1"]["c_second_wrong"] == 0)
    check("chain recitation counter reads 36 on the traversal fabrication "
          "and 0 on the always-no fabrication",
          trav_full["records_naming_all_interior_nodes"] == 36
          and analyse(fake_records(lambda arm, it: None, lambda it, arm: ""),
                      items, gate, {})["records_naming_all_interior_nodes"] == 0)
    flipfake = fake_records(lambda arm, it: "no" if it["arms"][arm]["gold"]
                            else "yes", lambda it, arm: "x")
    flip = analyse(flipfake, items, gate, {})
    check("a fully inverted fabrication scores 0 correct yet zero discordant "
          "pairs (accuracy carries that failure, not McNemar)",
          sum(flip["arms"][a]["correct"] for a in ARMS) == 0
          and flip["families"]["direction_F1_R1"]["both_wrong"] == 9
          and flip["families"]["direction_F1_R1"]["p_exact_mcnemar"] == 1.0)
    check("the traversal-consistent fabrication classifies as no_turnover "
          "with P1 holding on all 36 cells",
          trav_full["turnover_classification"] == "no_turnover_within_grid"
          and trav_full["predictions"]["P1_correctness_holds"] is True
          and sum(trav_full["arms"][a]["correct"] for a in ARMS) == 36)
    tp = trav_full["predictions"]
    check("on an all-answered fabrication P2 is False (no strict decay) and "
          "P3 is vacuous (no truncated cells, supported is None)",
          tp["P2_answerability_decay"] is False and tp["P3_supported"] is None)
    mixedfake = fake_records(
        lambda arm, it: ("yes" if arm == "X" and it["level"] == 48
                         else ("yes" if it["arms"][arm]["gold"] else "no")),
        lambda it, arm: " ".join(it["path"]))
    mxf = analyse(mixedfake, items, gate, {})
    check("a wrong answered X cell at k = 48 flips P1 and yields "
          "correctness_turnover",
          mxf["predictions"]["P1_correctness_holds"] is False
          and mxf["turnover_classification"] == "correctness_turnover")
    halftrunc = [dict(r, outcome="truncated_no_answer", answer=None,
                      correct=None, answer_source="none",
                      attempts=[dict(r["attempts"][0], finish_reason="length",
                                     completion_tokens=2048, answer=None,
                                     reasoning=" ".join(
                                         next(i for i in items
                                              if i["item_id"] == r["item_id"]
                                              )["path"][:12]),
                                     content="")])
                 for r in trav]
    hf = analyse(halftrunc, items, gate, {})
    check("an all-truncated fabrication classifies as budget_turnover with "
          "P1 vacuously holding (no answered cell is wrong)",
          hf["turnover_classification"] == "budget_turnover"
          and hf["predictions"]["P1_correctness_holds"] is True)

    # cross-class join controls on synthetic archives (archive-independent)
    def fake_ref_records(flip_cell=None, drop_cell=None):
        out = []
        for it in items:
            for arm in ARMS:
                if drop_cell is not None \
                        and (it["item_id"], arm) == drop_cell:
                    continue
                ans = "yes" if it["arms"][arm]["gold"] else "no"
                if (it["item_id"], arm) == flip_cell:
                    ans = "no" if ans == "yes" else "yes"
                out.append({"item_id": it["item_id"], "arm": arm,
                            "level": it["level"], "answer": ans,
                            "outcome": "answered",
                            "correct": int((1 if ans == "yes" else 0)
                                           == it["arms"][arm]["gold"]),
                            "answer_source": "content",
                            "attempts": [{"completion_tokens": 100,
                                          "finish_reason": "stop",
                                          "content": ans, "reasoning": "",
                                          "error_class": None,
                                          "answer": ans,
                                          "answer_source": "content",
                                          "answer_offset": 0}]})
        return out

    fake_mine = fake_records(
        lambda arm, it: "yes" if it["arms"][arm]["gold"] else "no",
        lambda it, arm: "")
    j_all = join_crossclass(fake_mine, fake_ref_records())
    check("cross-class join on fully agreeing synthetic archives: 36 "
          "joined, 36 both-answered, zero disagreements, p = 1.0",
          j_all["joined_cells"] == 36 and j_all["both_answered"] == 36
          and j_all["answer_disagreements"] == 0
          and j_all["both_answered_mcnemar"]["p_exact_mcnemar"] == 1.0)
    j_flip = join_crossclass(fake_mine,
                             fake_ref_records(flip_cell=("L24-1", "X")))
    check("one flipped reference cell yields exactly one disagreement and "
          "exactly one discordant pair (n = 1, p = 1.0)",
          j_flip["both_answered"] == 36
          and j_flip["answer_disagreements"] == 1
          and (j_flip["both_answered_mcnemar"]
               ["b_this_wrong_round17_right"]
               + j_flip["both_answered_mcnemar"]
               ["c_this_right_round17_wrong"]) == 1
          and j_flip["both_answered_mcnemar"]["p_exact_mcnemar"] == 1.0)
    j_drop = join_crossclass(fake_mine,
                             fake_ref_records(drop_cell=("L48-3", "X")))
    check("a dropped reference cell reduces the join to 35 cells",
          j_drop["joined_cells"] == 35)

    # P4 evaluation controls (synthetic joins, archive-independent)
    pl = {str(k): {"cells": 12, "answered": 12, "correct": 12,
                    "answered_per_arm": {"F1": 3, "R1": 3, "F2": 3, "X": 3}}
          for k in LEVELS}
    # crossclass_analysis wraps the pure join with the `available` flag;
    # mirror that here so the controls exercise the production object
    p4t = evaluate_predictions(pl, {}, [],
                               crossclass={**j_all, "available": True})
    check("P4 is True on a fully agreeing cross-class join",
          p4t["P4_cross_class_agreement"] is True)
    p4f = evaluate_predictions(pl, {}, [],
                               crossclass={**j_flip, "available": True})
    check("P4 is False when the cross-class join carries one disagreement",
          p4f["P4_cross_class_agreement"] is False)
    p4v = evaluate_predictions(pl, {}, [], crossclass=None)
    check("P4 is vacuous (None) without a reference join",
          p4v["P4_cross_class_agreement"] is None)
    p4a = evaluate_predictions(pl, {}, [],
                               crossclass={"available": False})
    check("P4 is vacuous (None) when the reference archive is absent",
          p4a["P4_cross_class_agreement"] is None)

    print(f"\nselftest: {len(fails)} failure(s)")
    return 1 if fails else 0


# --------------------------------------------------------------------- main


def load_gate():
    gate = json.load(open(GATE_PATH, encoding="utf-8"))
    if gate.get("gate_hash") != gate_seed_hash(gate):
        raise SystemExit("gate.json hash mismatch; refusing to spend prompts")
    return gate


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
        print(f"pool items: {gate['pool_corpus']['items']}, disagreeing "
              f"cells: {gate['pool_corpus']['cells_where_connectivity_and_reachability_disagree']}")
        print(f"matched cells: {gate['matched_corpus']['cells']}, disagreeing "
              f"cells: {gate['matched_corpus']['cells_where_connectivity_and_reachability_disagree']}")
        print(f"generator sha256 pinned: "
              f"{gate['item_source']['generator_sha256'] == gate['item_source']['generator_sha256_pin']}")
        pins = gate["item_source"]["blob_pin_checks"]
        print(f"blob pins equal (l24/l32/l48): "
              f"{pins['l24']['actual'] == pins['l24']['expected']} / "
              f"{pins['l32']['actual'] == pins['l32']['expected']} / "
              f"{pins['l48']['actual'] == pins['l48']['expected']}")
        print(f"anchor pairing (round 16, L24): "
              f"{gate['anchor_pairing']['prompt_sha_matches']} "
              f"of {gate['anchor_pairing']['expected_cells']} verified: "
              f"{gate['anchor_pairing']['verified']}")
        print(f"cross-class pairing (round 17): "
              f"{gate['cross_class_pairing']['prompt_sha_matches']} "
              f"of {gate['cross_class_pairing']['expected_cells']} verified: "
              f"{gate['cross_class_pairing']['verified']}")
        for row in gate["rules"]:
            print(f"  {row['rule']:34s} pool {row['pool_accuracy']:.10f} "
                  f"p2={row['pool_p_two_sided']:.3e}  matched "
                  f"{row['matched_accuracy']:.10f} p2={row['matched_p_two_sided']:.3e}")
        return 0
    gate = load_gate()
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
        anchor = verify_anchor(items)
        if not anchor["verified"]:
            raise SystemExit(f"anchor pairing unverified; refusing to spend "
                             f"prompts: {anchor}")
        cross = verify_crossclass(items)
        if not cross["verified"]:
            raise SystemExit(f"cross-class pairing unverified; refusing to "
                             f"spend prompts: {cross}")
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
        print(json.dumps(out["per_level"], indent=2))
        print(json.dumps(out["turnover_classification"], indent=2))
        print(json.dumps(out["predictions"], indent=2))
        print(json.dumps(out["families"], indent=2))
        print(json.dumps(out["token_law"], indent=2))
        print(json.dumps(out["mid_stream_commitment"], indent=2))
        print(json.dumps(out["signature_table"], indent=2))
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

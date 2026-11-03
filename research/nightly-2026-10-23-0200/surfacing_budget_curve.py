#!/usr/bin/env python3
"""Nightly round 19 (2026-10-23 02:00): the budget elasticity of answer
surfacing at fixed depth.

Question. On the repaired ladders family (issue #69), the level-24 matched
grid measured twice on this endpoint class (rounds 15 and 17) answered 36 of
36 cells correctly, but every one of the nine cross-component (X) cells hit
the 2048-token ceiling with no answer in the answer field: the declared
parser rescued all nine from the reasoning trace. Rounds 15/16 also showed
the trace-rescue property does not transfer across endpoint classes. So on
this class the recorded "answerability" of a negative arm is decided by a
parse convention, not by an observable behaviour. One question: **at fixed
depth k = 24, how does answer surfacing depend on the output-token budget,
and how much budget does surfacing need beyond the budget the reasoning
itself needs?** The treatment is the output budget, not the depth: the same
nine level-24 cells (the positive arm F1, the reverse arm R1, the
cross-component arm X, three items each) at max_tokens in {256, 640, 1280,
2048}, temperature 0.

Declared predictions (written into gate.json before any prompt is spent):
  P1 surfacing monotonicity: within an arm, the count of cells whose answer
     field carries a parseable yes/no is non-decreasing in the budget.
  P2 arm asymmetry at the operating point: at 2048 the F1 arm surfaces 3 of 3
     in the answer field and the X arm surfaces 0 of 3 (the round-17
     signature), and F1 surfaces at least as often as X at every budget.
  P3 correctness invariance: every answer-field answer is correct, at every
     budget (the budget moves surfacing, not correctness).
  P4 trace-before-surface: for every cell, the smallest budget at which the
     reasoning field carries the answer is no larger than the smallest budget
     at which the answer field does.
  P5 operating-point pairing: the 2048 row reproduces round 17's level-24
     answers on the nine cell-paired cells.

Corpus identity is inherited: generator sha256 pin, level-24 blob pin, and
per-cell prompt sha256 pairing against the round-15 and round-17 archives.
The probe refuses to spend a prompt when pairing is unverified (fail-closed).

Reproduce:
    python3 surfacing_budget_curve.py --selftest
    python3 surfacing_budget_curve.py --gate
    NIGHTLY_BASE_URL=... NIGHTLY_MODEL_ID=... NIGHTLY_API_KEY=... \
        python3 surfacing_budget_curve.py --probe
    python3 surfacing_budget_curve.py --analyze

Endpoint values come from the environment and are never written to disk. All
stored text passes a sanitizer (URLs, IPs, absolute paths, host:port).
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

LEVEL = 24
POOL_PER_LEVEL = 300
ITEMS_PER_LEVEL = 3
ARMS = ("F1", "R1", "X")
GOLD = {"F1": 1, "R1": 0, "F2": 1, "X": 0}
MAX_PROMPT_CHARS = 45000

# The treatment: output-token budget ladder. The top rung is the operating
# point of rounds 10/11/14/15/16/17/18 and is the protocol ceiling.
BUDGETS = (256, 640, 1280, 2048)
OPERATING_BUDGET = 2048

MAX_PROMPTS = 40
HEALTH_PROMPTS = 1
TEMPERATURE = 0.0
ITEM_DEADLINE_S = 900
PHASE2_BUDGET_S = 1500
CONCURRENCY_CHOICES = (4, 2, 1)
TPS_FLOOR = 5.0

GATE_ALPHA = 0.05
GATE_MIN_ACCURACY = 0.90

GATE_PATH = os.path.join(HERE, "gate.json")
RAW_PATH = os.path.join(HERE, "raw.jsonl")
SUMMARY_PATH = os.path.join(HERE, "summary.json")

# Corpus identity: the repaired generator module (issue #69) and the level-24
# pool blob regenerating byte-identically from seed_base 20261019, pinned by
# rounds 15, 16, 17 and 18.
GENERATOR_SHA256 = "b0d77efd308d249fea77e5fd97e9bef7f5e0fd737b214c2d754cddf970a7f77b"
L24_BLOB_PIN = "cab16fae867b4791290259ffa451231efd73ef193da96664720fd4686fb7008f"

# Cell-pairing archives: the same nine level-24 prompts at the same budget.
ROUND15_RAW = os.path.join(REPO, "research", "nightly-2026-10-21-0200",
                           "raw.jsonl")
ROUND17_RAW = os.path.join(REPO, "research", "nightly-2026-10-22-0200",
                           "raw.jsonl")

ANSWER_RE = re.compile(r"\b(yes|no)\b", re.IGNORECASE)
# Post-hoc validity control (added after the first dispatch cells showed that
# a 256-token trace already classifies as "trace_only"): a reasoning-field
# yes/no can be an instruction echo ("answer yes/no", "yes or no") rather than
# a commitment. PHRASE_RE marks matches that sit inside such a phrase;
# MARKER_RE marks an answer intention before the token.
PHRASE_RE = re.compile(
    r"yes\s*[/|]\s*no|no\s*[/|]\s*yes|yes\s+or\s+no|no\s+or\s+yes",
    re.IGNORECASE)
MARKER_RE = re.compile(
    r"\b(answer|final|conclude|conclusion|therefore|thus|so the|output|"
    r"correct answer|response must)\b[^.]{0,120}$",
    re.IGNORECASE)
MARKER_WINDOW = 160
URL_RE = re.compile(
    r"https?://\S+|\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|"
    r"(?:/[A-Za-z0-9_.-]+){2,}|[A-Za-z]:\\[^\s]*"
)
HEALTH_PROMPT = "Reply with exactly one word: yes"

LINEAGE = [
    {"round": 6, "corpus": "repaired family, single-query depth grid "
                           "k = 1..16, open budget",
     "endpoint": "flash-next-class local endpoint",
     "result": "40 of 40 correct; completion tokens = -36 + 80k; the "
               "fixed-budget replay lost 26 of 40 items at 256 tokens, "
               "12 of 40 at 512, 4 of 40 at 1024 (arm-blind, pre-repair)",
     "archive": "research/nightly-2026-10-16-0400/ (on main via PR #70)"},
    {"round": 15, "corpus": "repaired matched-pair grid k = 12, 16, 24 at "
                            "max_tokens 2048",
     "endpoint": "flash-next-class local endpoint",
     "result": "36 of 36 answered cells correct; 7 truncations, all on "
               "negative arms, all rescued from the reasoning trace",
     "archive": "research/nightly-2026-10-21-0200/ (PR #88, open)"},
    {"round": 16, "corpus": "same grid, cell-paired to round 15",
     "endpoint": "27B-class local endpoint",
     "result": "33 of 33 answered correct; the three X cells at k = 24 "
               "unanswerable within 2 x 2048 tokens: trace rescue does not "
               "transfer across classes",
     "archive": "research/nightly-2026-10-21-0400/ (PR #89, open)"},
    {"round": 17, "corpus": "repaired grid at k = 24, 32, 48, max_tokens "
                            "2048 (the nine k = 24 cells used here)",
     "endpoint": "flash-next-class local endpoint",
     "result": "36 of 36 correct; 17 of 36 at the ceiling, all rescuable "
               "from the trace; 9 of 9 X cells at 2048.0 tokens with zero "
               "answers in the answer field; median commitment at 0.457 of "
               "the reasoning stream",
     "archive": "research/nightly-2026-10-22-0200/ (PR #90, open)"},
    {"round": 18, "corpus": "the identical 36-cell grid on the 27B class",
     "endpoint": "27B-class local endpoint",
     "result": "29 of 36 answered, all correct; turnover confined to the X "
               "arm at k = 24 (0 of 3 answered, 1 of 3 at 32 and 48)",
     "archive": "research/nightly-2026-10-22-0400/ (PR #91, open)"},
]

CELL_FIELDS = ("item_id", "arm", "level", "budget", "chain_len", "fact_count",
               "seed", "seed_hash", "src", "dst", "gold", "same_component",
               "directed_reach", "undirected_hops", "prompt_sha256",
               "prompt_chars", "gate_hash", "phase", "attempts",
               "content_answer", "reasoning_answer", "declared_answer",
               "declared_source", "outcome", "correct")


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
    for item in lad.generate_items(LEVEL, POOL_PER_LEVEL, SEED_BASE):
        rec = dict(item)
        rec["_level"] = LEVEL
        recs.append(rec)
    return recs


def pool_blob_sha256() -> dict:
    lad = load_ladders()
    blob = "".join(lad.item_jsonl(i) + "\n"
                   for i in lad.generate_items(LEVEL, POOL_PER_LEVEL,
                                               SEED_BASE))
    return {f"generated/l{LEVEL}.jsonl": sha256_text(blob)}


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
    mismatches = []
    disagree = 0
    for rec in recs:
        adj, und, _in_deg, _out_deg, nodes = graph_of(rec["facts"])
        src, _rel, dst = rec["query"]
        reach = directed_reachable(src, dst, adj)
        comp = components(nodes, und)
        same = comp.get(src) == comp.get(dst)
        gold = 1 if rec["answer"] == "yes" else 0
        if int(reach) != gold:
            mismatches.append({"level": rec["_level"], "seed": rec["seed"]})
        if int(same) != int(reach):
            disagree += 1
    return {"items_total": len(recs),
            "gold_reach_mismatches": mismatches,
            "pool_items_where_connectivity_and_reachability_disagree":
                disagree}


# ------------------------------------------------- matched-pair construction
# chain_path and render_prompt are rounds 10/11/15/17 verbatim: cell pairing
# at the anchor level depends on this being byte-identical.


def chain_path(rec: list):
    """The directed chain the generated gold-yes query witnesses.

    Returns the node list p_1 .. p_{k+1} or None when the item is not usable:
    the query must be reachable, the path simple, every node on it of
    in-degree <= 1 and out-degree <= 1, and the item must contain a second
    component with a terminal node (in-degree 1, out-degree 0) whose name
    length equals the chain terminal's.
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
    """Deterministic selection: first N usable items at level 24 in generated
    file order with the declared context-safety filter applied identically.
    This is round 15/17's rule and reproduces their level-24 items (verified
    against both archives by prompt sha256 in verify_pairing)."""
    recs = load_pool()
    items = []
    scanned = 0
    skipped_long = 0
    for rec in recs:
        scanned += 1
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
            "item_id": f"L{LEVEL}-{picked_name(len(items))}",
            "level": LEVEL,
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
        if len(items) >= ITEMS_PER_LEVEL:
            break
    if len(items) != ITEMS_PER_LEVEL:
        raise SystemExit(f"selection rule starved: {len(items)} items")
    return {"items": items, "scanned": scanned,
            "skipped_over_char_cap": skipped_long}


def picked_name(index: int) -> str:
    return str(index + 1)


def fingerprint_of(items: list) -> list:
    """Seed-deterministic identity of the matched corpus, prompts excluded."""
    return [{"item_id": i["item_id"], "level": i["level"], "seed": i["seed"],
             "seed_hash": i["seed_hash"], "chain_len": i["chain_len"],
             "fact_count": i["fact_count"],
             "component_count": i["component_count"],
             "arms": {a: {k: v for k, v in i["arms"][a].items() if k != "prompt"}
                      for a in ARMS}} for i in items]


def matched_invariant(items: list) -> dict:
    """Matchedness of the two families on the arms used here, plus gold
    recomputation. Violations are fatal, not reported results."""
    violations = []
    for item in items:
        adj, und, in_deg, out_deg, nodes = graph_of(item["facts"])
        comp = components(nodes, und)
        pa, pb = item["arms"]["F1"], item["arms"]["R1"]
        names_a = sorted([pa["src"], pa["dst"]])
        names_b = sorted([pb["src"], pb["dst"]])
        deg_a = sorted([(in_deg[n], out_deg[n]) for n in names_a])
        deg_b = sorted([(in_deg[n], out_deg[n]) for n in names_b])
        checks = [
            ("direction_prompt_length",
             pa["prompt_chars"] == pb["prompt_chars"]),
            ("direction_name_multiset", names_a == names_b),
            ("direction_degree_profile", deg_a == deg_b),
            ("direction_gold_differs", pa["gold"] != pb["gold"]),
            ("direction_undirected_distance",
             undirected_distance(pa["src"], pa["dst"], und)
             == undirected_distance(pb["src"], pb["dst"], und)),
            ("component_prompt_length",
             item["arms"]["F2"]["prompt_chars"]
             == item["arms"]["X"]["prompt_chars"]),
            ("component_connectivity_differs",
             int(comp[item["arms"]["F2"]["src"]]
                 == comp[item["arms"]["F2"]["dst"]])
             != int(comp[item["arms"]["X"]["src"]]
                    == comp[item["arms"]["X"]["dst"]])),
        ]
        for name, ok in checks:
            if not ok:
                violations.append({"item": item["item_id"], "check": name})
        for arm in ARMS:
            a = item["arms"][arm]
            reach = directed_reachable(a["src"], a["dst"], adj)
            if int(reach) != a["gold"]:
                violations.append({"item": item["item_id"], "arm": arm,
                                   "check": "gold_vs_recomputed_reachability"})
            a["same_component"] = int(comp.get(a["src"]) == comp.get(a["dst"]))
            a["directed_reach"] = int(reach)
            a["undirected_hops"] = undirected_distance(a["src"], a["dst"], und)
    disagree = sum(1 for item in items for arm in ARMS
                   if item["arms"][arm]["same_component"]
                   != item["arms"][arm]["directed_reach"])
    return {"violations": violations, "items": len(items),
            "cells_per_budget": len(items) * len(ARMS),
            "cells_where_connectivity_and_reachability_disagree": disagree}


# ---------------------------------------------------------------- leak battery

LEAK_RULES = ("all_yes", "all_no", "src_is_first_fact_subject",
              "dst_is_last_fact_object", "dst_is_fact_target",
              "src_mentioned_after_dst", "name_length_src_gt_dst")
REFERENCE_RULES = ("directed_reachability", "undirected_connectivity")


def mention_order(facts: list) -> dict:
    first: dict = {}
    last: dict = {}
    for idx, (src, _rel, dst) in enumerate(facts):
        first.setdefault(src, idx)
        first.setdefault(dst, idx)
        last[src] = idx
        last[dst] = idx
    return {"first": first, "last": last}


def battery_prediction(rule: str, item: dict, arm: str) -> int:
    facts = item["facts"]
    a = item["arms"][arm]
    src, dst = a["src"], a["dst"]
    adj, und, _in_deg, _out_deg, nodes = graph_of(facts)
    mo = mention_order(facts)
    if rule == "all_yes":
        return 1
    if rule == "all_no":
        return 0
    if rule == "directed_reachability":
        return int(directed_reachable(src, dst, adj))
    if rule == "undirected_connectivity":
        return int(undirected_distance(src, dst, und) >= 0)
    if rule == "src_is_first_fact_subject":
        return int(facts[0][0] == src)
    if rule == "dst_is_last_fact_object":
        return int(facts[-1][2] == dst)
    if rule == "dst_is_fact_target":
        # the pre-repair leak class (issue #69): answer yes when the query
        # destination is the generated gold-yes query's destination, i.e. the
        # chain terminal. On the repaired corpus this must stay near chance.
        return int(dst == item["path"][-1])
    if rule == "src_mentioned_after_dst":
        return int(mo["last"].get(src, -1) > mo["first"].get(dst, 10 ** 9))
    if rule == "name_length_src_gt_dst":
        return int(len(src) > len(dst))
    raise SystemExit(f"unknown rule {rule}")


def cells_of(items: list) -> list:
    return [(item, arm) for item in items for arm in ARMS]


def rule_accuracy(rule: str, items: list) -> dict:
    cells = cells_of(items)
    golds = [item["arms"][arm]["gold"] for item, arm in cells]
    hits = sum(1 for item, arm in cells
               if battery_prediction(rule, item, arm)
               == item["arms"][arm]["gold"])
    n = len(cells)
    p = min(1.0, 2.0 * sum(
        math.exp(log_choose(n, i) - n * math.log(2.0))
        for i in range(0, min(hits, n - hits) + 1)))
    lo, hi = wilson(hits, n)
    return {"rule": rule, "hits": hits, "cells": n, "accuracy":
            (hits / n if n else 0.0), "p_two_sided": p,
            "wilson_low": lo, "wilson_high": hi,
            "gold_yes": sum(golds)}


def battery_on_matched(items: list) -> dict:
    """Blind lexical rules must not reach the gold without the relation; the
    two reference rules are the oracles this round is testing against."""
    out = {}
    for rule in LEAK_RULES + REFERENCE_RULES:
        row = rule_accuracy(rule, items)
        row["reference"] = rule in REFERENCE_RULES
        row["fires"] = bool(row["accuracy"] >= GATE_MIN_ACCURACY
                            and row["p_two_sided"] < GATE_ALPHA
                            and not row["reference"])
        out[rule] = row
    firing = [r for r, v in out.items() if v["fires"]]
    return {"rules": out, "firing_leak_rules": firing,
            "bonferroni_alpha": GATE_ALPHA / len(LEAK_RULES),
            "passed": not firing}


# -------------------------------------------------------------- pairing gate

def load_archive_cells(path: str, level: int = LEVEL) -> dict:
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            if int(rec.get("level", -1)) != level:
                continue
            if rec.get("arm") not in ARMS:
                continue
            out[(rec["item_id"], rec["arm"])] = rec
    return out


def verify_pairing(items: list) -> dict:
    """Every one of the nine prompts must be byte-identical to the archived
    level-24 cells of rounds 15 and 17. Fail-closed at probe time."""
    r15 = load_archive_cells(ROUND15_RAW)
    r17 = load_archive_cells(ROUND17_RAW)
    rows = []
    matches15 = matches17 = 0
    for item, arm in cells_of(items):
        sha = item["arms"][arm]["prompt_sha256"]
        a15 = r15.get((item["item_id"], arm))
        a17 = r17.get((item["item_id"], arm))
        ok15 = bool(a15 and a15.get("prompt_sha256") == sha)
        ok17 = bool(a17 and a17.get("prompt_sha256") == sha)
        matches15 += int(ok15)
        matches17 += int(ok17)
        rows.append({"item_id": item["item_id"], "arm": arm,
                     "prompt_sha256_12": sha[:12], "round15_match": ok15,
                     "round17_match": ok17,
                     "round17_declared_answer": (a17 or {}).get("answer"),
                     "round17_answer_source": (a17 or {}).get("answer_source"),
                     "round17_completion_tokens":
                         (a17 or {}).get("mechanics", {}).get(
                             "completion_tokens")
                         if isinstance((a17 or {}).get("mechanics"), dict)
                         else (a17 or {}).get("completion_tokens")})
    expected = len(items) * len(ARMS)
    return {"expected_cells": expected,
            "round15_prompt_sha_matches": matches15,
            "round17_prompt_sha_matches": matches17,
            "verified": matches15 == expected and matches17 == expected,
            "round15_raw_sha256": (sha256_file(ROUND15_RAW)
                                   if os.path.exists(ROUND15_RAW) else None),
            "round17_raw_sha256": (sha256_file(ROUND17_RAW)
                                   if os.path.exists(ROUND17_RAW) else None),
            "cells": rows}


# -------------------------------------------------------------------- the gate

PREDICTIONS = {
    "P1_surfacing_monotonicity":
        "within each arm, the count of cells with a parseable yes/no in the "
        "answer field is non-decreasing across the budget ladder 256, 640, "
        "1280, 2048",
    "P2_arm_asymmetry_at_operating_point":
        "at max_tokens 2048 the F1 arm surfaces 3 of 3 answers in the answer "
        "field and the X arm surfaces 0 of 3 (the round-17 signature), and "
        "F1 surfaces at least as often as X at every budget",
    "P3_correctness_invariance":
        "every answer-field answer is correct at every budget: the budget "
        "moves surfacing, not correctness",
    "P4_trace_before_surface":
        "for every cell, the smallest budget carrying a reasoning-field "
        "answer is no larger than the smallest budget carrying an "
        "answer-field answer",
    "P5_operating_point_pairing":
        "the 2048 rung reproduces round 17's declared answer on all nine "
        "cell-paired level-24 cells",
}


def build_gate() -> dict:
    built = build_matched_items()
    items = built["items"]
    invariant = matched_invariant(items)
    if invariant["violations"]:
        raise SystemExit(f"matched-pair invariant violated: "
                         f"{invariant['violations']}")
    second_items = build_matched_items()["items"]
    if matched_invariant(second_items)["violations"]:
        raise SystemExit("matched-pair invariant violated on rebuild")
    if sha256_text(canonical(fingerprint_of(items))) \
            != sha256_text(canonical(fingerprint_of(second_items))):
        raise SystemExit("matched-pair construction is not seed deterministic")
    pool = verify_pool(load_pool())
    if pool["gold_reach_mismatches"]:
        raise SystemExit(f"pool gold labels do not recompute: "
                         f"{pool['gold_reach_mismatches'][:3]}")
    blob = pool_blob_sha256()
    gen_sha = sha256_file(LADDERS_PATH)
    cells = len(items) * len(ARMS) * len(BUDGETS)
    if cells + HEALTH_PROMPTS > MAX_PROMPTS:
        raise SystemExit(f"prompt cap exceeded: {cells} + {HEALTH_PROMPTS}")
    return {
        "schema": "round19-gate-v1",
        "created_at": now_iso(),
        "question": "At fixed depth k = 24 on the repaired ladders family, "
                    "how does answer surfacing depend on the output-token "
                    "budget, and how much budget does surfacing need beyond "
                    "what the reasoning needs?",
        "why": "rounds 15 and 17 recorded 36 of 36 correct on this endpoint "
               "class with all nine cross-component answers available only "
               "through the reasoning-fallback parse; the answerability "
               "measure is therefore convention-loaded, which round 17's "
               "next step 1 names as the instrument gap",
        "design": {
            "level": LEVEL, "arms": list(ARMS), "items": len(items),
            "budgets": list(BUDGETS), "operating_budget": OPERATING_BUDGET,
            "temperature": TEMPERATURE,
            "cells": cells, "endpoint_calls_cap": MAX_PROMPTS,
            "unit_of_analysis": "one (cell, budget) pair",
            "retry_policy": "transport failures and empty completions only; "
                            "truncation and model stops are measured "
                            "outcomes and are never retried",
            "parser": "each field parsed separately for the last standalone "
                      "yes/no; the round-15/17 declared parser (answer field "
                      "first, reasoning fallback) is also recorded so the "
                      "contribution of the fallback is measurable",
        },
        "predictions": PREDICTIONS,
        "item_source": {
            "generator_path": "generators/ladders.py",
            "generator_sha256": gen_sha,
            "generator_sha256_pin": GENERATOR_SHA256,
            "seed_base": SEED_BASE,
            "pool_per_level": POOL_PER_LEVEL,
            "blob_sha256": blob,
            "l24_pin_check": {"expected": L24_BLOB_PIN,
                              "actual": blob[f"generated/l{LEVEL}.jsonl"]},
            "selection": "chain_path rule verbatim from rounds 10/11/15/17 "
                         "plus the 45000-char context-safety filter",
            "scanned": built["scanned"],
            "skipped_over_char_cap": built["skipped_over_char_cap"],
        },
        "pool_corpus": pool,
        "matched_corpus": invariant,
        "leak_battery": battery_on_matched(items),
        "battery_note": "the full 15-rule battery with exact label-shuffle "
                        "nulls is recorded in round 15's and round 17's "
                        "gates on this same corpus; this round re-runs the "
                        "blind lexical rules and the two oracle references "
                        "on the nine cells it actually dispatches",
        "pairing": verify_pairing(items),
        "lineage": LINEAGE,
        "endpoint_class": "a flash-next-class local endpoint (the class "
                          "rounds 15 and 17 measured)",
        "evidence_label": "Executed",
        "known_limits": [
            "n = 3 items per arm: exploratory, not confirmatory",
            "one endpoint class, one run, quantized local deployment, "
            "undisclosed training data: not H1 evidence",
            "the budget ladder has four rungs: thresholds are bracketed, "
            "not measured exactly",
            "the level-24 corpus keeps prompt load coupled with chain depth "
            "(issue #71 option 2 stays open)",
            "a reasoning-field yes/no is the last such token in a "
            "still-running trace: it is evidence that the token is "
            "available, not that the model treats it as final",
        ],
    }


def gate_seed_hash(gate: dict) -> str:
    body = {k: v for k, v in gate.items() if k != "gate_hash"}
    body.pop("created_at", None)
    return sha256_text(canonical(body))[:12]


# ------------------------------------------------------------------ transport

def endpoint_url() -> str:
    base = os.environ.get("NIGHTLY_BASE_URL", "").strip().rstrip("/")
    if not base:
        raise SystemExit("NIGHTLY_BASE_URL is not set; the probe cannot run")
    return base + "/chat/completions"


def call_endpoint(prompt: str, max_tokens: int, deadline_s: int) -> dict:
    key = os.environ.get("NIGHTLY_API_KEY", "").strip()
    model = os.environ.get("NIGHTLY_MODEL_ID", "").strip()
    body = json.dumps({"model": model,
                       "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens,
                       "temperature": TEMPERATURE,
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
                "finish_reason": None, "prompt_tokens": 0,
                "completion_tokens": 0}
    except (urllib.error.URLError, TimeoutError, OSError,
            json.JSONDecodeError) as exc:
        return {"error": type(exc).__name__, "content": "", "reasoning": "",
                "finish_reason": None, "prompt_tokens": 0,
                "completion_tokens": 0}


def last_answer(text: str):
    """Last standalone yes/no in one field. Returns (answer, offset)."""
    matches = list(ANSWER_RE.finditer(text or ""))
    if not matches:
        return None, -1
    m = matches[-1]
    return m.group(1).lower(), m.start()


def parse_fields(content: str, reasoning: str) -> dict:
    """The measurement-relevant split: each field parsed on its own."""
    c_ans, c_off = last_answer(content)
    r_ans, r_off = last_answer(reasoning)
    declared, source, offset = ((c_ans, "content", c_off) if c_ans
                                else ((r_ans, "reasoning", r_off) if r_ans
                                      else (None, "none", -1)))
    return {"content_answer": c_ans, "content_offset": c_off,
            "reasoning_answer": r_ans, "reasoning_offset": r_off,
            "declared_answer": declared, "declared_source": source,
            "declared_offset": offset}


def classify_attempt(att: dict) -> str:
    if att.get("error_class"):
        return f"transport_{att['error_class']}"
    if att["completion_tokens"] == 0:
        return "empty_completion"
    if att["content_answer"] is not None:
        return "answered_in_answer_field"
    if att["reasoning_answer"] is not None:
        return "trace_only"
    if att["finish_reason"] == "length":
        return "truncated_no_answer"
    return "no_answer_stop"


def is_retryable(outcome: str) -> bool:
    return outcome == "empty_completion" or outcome.startswith("transport_")


class AttemptBudget:
    """Hard cap on total endpoint calls for the whole run."""

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


def health_check() -> dict:
    t0 = time.monotonic()
    resp = call_endpoint(HEALTH_PROMPT, OPERATING_BUDGET, deadline_s=180)
    latency = round(time.monotonic() - t0, 3)
    parsed = parse_fields(resp["content"], resp["reasoning"])
    att = {"error_class": None, "completion_tokens": resp["completion_tokens"],
           "content_answer": parsed["content_answer"],
           "reasoning_answer": parsed["reasoning_answer"]}
    if resp.get("error"):
        att["error_class"] = resp["error"]
    return {"ok": classify_attempt(att) == "answered_in_answer_field",
            "outcome": classify_attempt(att), "latency_s": latency,
            "completion_tokens": resp["completion_tokens"],
            "prompt_tokens": resp["prompt_tokens"],
            "started_at": now_iso(), "finished_at": now_iso()}


def expected_traversal(item: dict, arm: str):
    if arm == "F1":
        return list(item["path"])
    if arm in ("F2", "X"):
        return list(item["path"][1:])
    return None  # R1: the query source is a path tail


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


def mechanics(item: dict, arm: str, att: dict, budget: int) -> dict:
    text = (att.get("reasoning") or "") + " " + (att.get("content") or "")
    seq = expected_traversal(item, arm)
    hops = ordered_prefix_hops(seq, text) if seq else None
    out = {
        "ordered_prefix_hops": hops,
        "expected_hops": len(seq) if seq else None,
        "coverage_ratio": (round(hops / len(seq), 4)
                           if seq and hops is not None else None),
        "completion_tokens": att["completion_tokens"],
        "budget_utilisation": round(att["completion_tokens"] / budget, 4),
        "reasoning_chars": len(att.get("reasoning") or ""),
        "content_chars": len(att.get("content") or ""),
    }
    rlen = len(att.get("reasoning") or "")
    if att.get("reasoning_answer") is not None and rlen:
        out["reasoning_commit_fraction"] = round(
            att["reasoning_offset"] / rlen, 4)
    return out


def make_record(item: dict, arm: str, budget: int, gate: dict,
                budget_cap: AttemptBudget, phase: int) -> dict:
    a = item["arms"][arm]
    rec = {
        "item_id": item["item_id"], "arm": arm, "level": item["level"],
        "budget": budget, "chain_len": item["chain_len"],
        "fact_count": item["fact_count"], "seed": item["seed"],
        "seed_hash": item["seed_hash"], "src": a["src"], "dst": a["dst"],
        "gold": a["gold"], "same_component": a["same_component"],
        "directed_reach": a["directed_reach"],
        "undirected_hops": a["undirected_hops"],
        "prompt_sha256": a["prompt_sha256"], "prompt_chars": a["prompt_chars"],
        "gate_hash": gate["gate_hash"], "phase": phase, "attempts": [],
        "content_answer": None, "reasoning_answer": None,
        "declared_answer": None, "declared_source": "none",
        "outcome": "abandoned_budget", "correct": None,
    }
    for attempt_no in (1, 2):
        if not budget_cap.acquire():
            rec["attempts"].append({
                "attempt": attempt_no, "wall_s": 0.0,
                "error_class": "budget_exhausted", "started_at": now_iso(),
                "finished_at": now_iso(), "finish_reason": None,
                "prompt_tokens": 0, "completion_tokens": 0,
                "content": "", "reasoning": "", "content_answer": None,
                "reasoning_answer": None})
            break
        t0 = time.monotonic()
        started = now_iso()
        resp = call_endpoint(a["prompt"], budget, deadline_s=ITEM_DEADLINE_S)
        wall = round(time.monotonic() - t0, 3)
        att = {"attempt": attempt_no, "wall_s": wall,
               "error_class": resp.get("error"), "started_at": started,
               "finished_at": now_iso(),
               "finish_reason": resp["finish_reason"],
               "prompt_tokens": resp["prompt_tokens"],
               "completion_tokens": resp["completion_tokens"],
               "content": resp["content"], "reasoning": resp["reasoning"]}
        att.update(parse_fields(resp["content"], resp["reasoning"]))
        att["mechanics"] = mechanics(item, arm, att, budget)
        rec["attempts"].append(att)
        if not is_retryable(classify_attempt(att)):
            break
    last = rec["attempts"][-1]
    rec["content_answer"] = last["content_answer"]
    rec["reasoning_answer"] = last["reasoning_answer"]
    rec["declared_answer"] = last["declared_answer"]
    rec["declared_source"] = last["declared_source"]
    rec["outcome"] = classify_attempt(last)
    if rec["declared_answer"] is not None:
        rec["correct"] = int((1 if rec["declared_answer"] == "yes" else 0)
                             == rec["gold"])
    return rec


def write_raw(rec: dict) -> None:
    with open(RAW_PATH, "a", encoding="utf-8") as fh:
        fh.write(canonical(rec) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def job_key(rec: dict):
    return (rec["item_id"], rec["arm"], rec["budget"])


def dispatch(items: list, gate: dict, cap: AttemptBudget) -> tuple:
    """Two-phase dispatch (issue #73): the two cheapest cells sequentially to
    measure throughput, then the rest at the declared concurrency, ordered so
    that the cheap rungs go first. Small budgets first keeps the expensive
    2048 rung inside the phase-2 wall budget."""
    jobs = [(item, arm, budget) for budget in BUDGETS for item in items
            for arm in ARMS]
    if len(jobs) + HEALTH_PROMPTS > MAX_PROMPTS:
        raise SystemExit(f"dispatch budget exceeded: {len(jobs)}")
    done: dict = {}
    if os.path.exists(RAW_PATH):
        with open(RAW_PATH, "r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("gate_hash") != gate["gate_hash"]:
                    raise SystemExit(
                        "raw.jsonl was written under a different gate")
                done[job_key(rec)] = rec
                cap.used += len(rec["attempts"])
    results = dict(done)
    note = {"resumed_cells": len(done)}

    def run(job: tuple, phase: int) -> dict:
        item, arm, budget = job
        if (item["item_id"], arm, budget) in results:
            return results[(item["item_id"], arm, budget)]
        rec = make_record(item, arm, budget, gate, cap, phase)
        results[(item["item_id"], arm, budget)] = rec
        write_raw(rec)
        return rec

    phase1 = [j for j in jobs[:2] if (j[0]["item_id"], j[1], j[2])
              not in results]
    for job in phase1:
        run(job, phase=1)
    walls = [results[(j[0]["item_id"], j[1], j[2])]["attempts"][-1]["wall_s"]
             for j in jobs[:2]
             if results[(j[0]["item_id"], j[1], j[2])]["attempts"]]
    tps = max([TPS_FLOOR] + [jobs[i][2] / w for i, w in enumerate(walls)
                             if w and w > 0])
    remaining = [j for j in jobs[2:] if (j[0]["item_id"], j[1], j[2])
                 not in results]
    est_total = sum(j[2] for j in remaining) / tps
    chosen = None
    for cand in CONCURRENCY_CHOICES:
        if est_total / cand * 1.25 <= PHASE2_BUDGET_S:
            chosen = cand
            break
    if chosen is None:
        chosen = max(CONCURRENCY_CHOICES)
    note.update({"phase1_walls": walls, "estimated_tokens_per_second":
                 round(tps, 3), "estimate_phase2_s": round(est_total, 1),
                 "chosen_concurrency": chosen})
    print(f"phase-1 walls {walls} s, ~{round(tps, 1)} tok/s, concurrency "
          f"{chosen} for {len(remaining)} cells", flush=True)

    phase2_start = time.monotonic()
    pending = list(remaining)
    to_run, abandoned = [], []
    for job in pending:
        if time.monotonic() > phase2_start + PHASE2_BUDGET_S:
            abandoned.append(job)
        else:
            to_run.append(job)
    for item, arm, budget in abandoned:
        rec = {"item_id": item["item_id"], "arm": arm, "level": item["level"],
               "budget": budget, "chain_len": item["chain_len"],
               "fact_count": item["fact_count"], "seed": item["seed"],
               "seed_hash": item["seed_hash"],
               "src": item["arms"][arm]["src"],
               "dst": item["arms"][arm]["dst"],
               "gold": item["arms"][arm]["gold"],
               "same_component": item["arms"][arm]["same_component"],
               "directed_reach": item["arms"][arm]["directed_reach"],
               "undirected_hops": item["arms"][arm]["undirected_hops"],
               "prompt_sha256": item["arms"][arm]["prompt_sha256"],
               "prompt_chars": item["arms"][arm]["prompt_chars"],
               "gate_hash": gate["gate_hash"], "phase": 2, "attempts": [],
               "content_answer": None, "reasoning_answer": None,
               "declared_answer": None, "declared_source": "none",
               "outcome": "abandoned_budget", "correct": None}
        results[(item["item_id"], arm, budget)] = rec
        write_raw(rec)
    if to_run:
        with concurrent.futures.ThreadPoolExecutor(max_workers=chosen) as pool:
            futures = [pool.submit(run, job, 2) for job in to_run]
            for fut in concurrent.futures.as_completed(futures):
                fut.result()
    records = [results[(item["item_id"], arm, budget)]
               for budget in BUDGETS for item in items for arm in ARMS]
    return records, note


# ------------------------------------------------------------------- analysis

def monotone_non_decreasing(values: list) -> bool:
    return all(b >= a for a, b in zip(values, values[1:]))


def threshold(series: dict, budgets: tuple):
    """Smallest budget in `series` (budget -> truthy) with a truthy value."""
    for b in budgets:
        if series.get(b):
            return b
    return None


def trace_provenance(records: list) -> dict:
    """POST-HOC control, not one of the gate's declared predictions.

    A reasoning-field yes/no is only evidence of an available answer if it is
    the token the model is about to deliver. This class writes the instruction
    back into its trace ("answer exactly one word yes/no"), and in that phrase
    the LAST standalone yes/no is always "no". This function classifies the
    last trace token of every record by where it sits:

      instruction_echo   inside a "yes/no" / "yes or no" phrase
      terminal           within the last 2% of the trace (the answer position)
      mid_trace          anywhere else (a mention, not a conclusion)

    and reports gold agreement per class, so the value of the declared
    fallback readout can be judged instead of assumed.
    """
    classes = collections.OrderedDict(
        (k, {"records": 0, "tokens_with_a_yes_no": 0, "agrees_with_gold": 0,
             "commit_fractions": [], "by_arm": collections.Counter()})
        for k in ("instruction_echo", "terminal", "mid_trace",
                  "no_trace_token"))
    confusion = collections.Counter()
    for rec in records:
        if not rec["attempts"]:
            continue
        att = rec["attempts"][-1]
        reasoning = att.get("reasoning") or ""
        gold_word = "yes" if rec["gold"] == 1 else "no"
        matches = list(ANSWER_RE.finditer(reasoning))
        if not matches:
            cls = "no_trace_token"
        else:
            m = matches[-1]
            spans = [p.span() for p in PHRASE_RE.finditer(reasoning)]
            in_phrase = any(a <= m.start() and m.end() <= b
                            for a, b in spans)
            frac = m.start() / max(1, len(reasoning))
            if in_phrase:
                cls = "instruction_echo"
            elif frac >= 0.98:
                cls = "terminal"
            else:
                cls = "mid_trace"
        bucket = classes[cls]
        bucket["records"] += 1
        bucket["by_arm"][rec["arm"]] += 1
        if matches:
            bucket["tokens_with_a_yes_no"] += 1
            bucket["agrees_with_gold"] += int(
                matches[-1].group(1).lower() == gold_word)
            bucket["commit_fractions"].append(
                round(matches[-1].start() / max(1, len(reasoning)), 4))
        confusion[(cls, gold_word)] += 1
    for bucket in classes.values():
        fr = bucket.pop("commit_fractions")
        bucket["commit_fraction_median"] = (round(sorted(fr)[len(fr) // 2], 4)
                                            if fr else None)
        bucket["by_arm"] = dict(bucket["by_arm"])
        n_tok = bucket.pop("tokens_with_a_yes_no")
        bucket["agreement_with_gold"] = (
            round(bucket["agrees_with_gold"] / n_tok, 4) if n_tok else None)
    # the fallback token as a predictor: what would it have said?
    fallback_words = collections.Counter()
    fallback_correct = 0
    fallback_total = 0
    for rec in records:
        if not rec["attempts"]:
            continue
        r_ans = rec["reasoning_answer"]
        if r_ans is None:
            continue
        fallback_total += 1
        fallback_words[r_ans] += 1
        fallback_correct += int((1 if r_ans == "yes" else 0) == rec["gold"])
    return {
        "declared_post_hoc": True,
        "classes": classes,
        "last_trace_token_by_gold": {f"{k[0]}|gold_{k[1]}": v
                                     for k, v in sorted(confusion.items())},
        "fallback_readout": {
            "records_with_a_trace_token": fallback_total,
            "token_distribution": dict(fallback_words),
            "would_be_correct": fallback_correct,
            "accuracy": round(fallback_correct / fallback_total, 4)
            if fallback_total else None,
            "constant_no_baseline_accuracy": round(
                sum(1 for r in records if r["gold"] == 0) / len(records), 4),
        },
    }


STRICT_TAIL_RE = re.compile(r"[.!?:;\)\]\"'\s]*$")
VERDICT_CUE_RE = re.compile(
    r"\b(thus|therefore|so|answer|final|conclusion|answer is|verdict)\b"
    r"[^.\n]{0,30}$", re.IGNORECASE)


def strict_last_trace_token(reasoning: str):
    """Last trace yes/no that could be a verdict.

    A token qualifies when it is outside a "yes/no" or "yes or no" phrase and
    either closes the trace (only punctuation after it) or is both preceded by
    an answer cue within 30 characters and closed by punctuation. "No other
    incoming." does not qualify (no cue, trace continues); "Thus yes." and a
    trace ending in "no" do.
    """
    text = reasoning or ""
    spans = [p.span() for p in PHRASE_RE.finditer(text)]
    chosen = None
    for m in ANSWER_RE.finditer(text):
        if any(a <= m.start() and m.end() <= b for a, b in spans):
            continue
        closes_trace = bool(STRICT_TAIL_RE.match(text, m.end()))
        closed_by_punct = (m.end() < len(text)
                           and text[m.end()] in ".!?:;")
        cued = bool(VERDICT_CUE_RE.search(text, 0, m.start()))
        if closes_trace or (closed_by_punct and cued):
            chosen = m.group(1).lower()
    return chosen


def strict_commitment(records: list) -> dict:
    """POST-HOC control: what a trace yes/no is worth.

    Reading the raw traces shows that the last standalone yes/no in a negative
    arm's trace is usually bookkeeping prose ("No other incoming.") or the
    instruction echo ("answer yes/no", "Ensure no extra."), not a verdict. A
    trace token is counted as a strict commitment only when it is not inside a
    "yes/no" phrase and is immediately followed by sentence-final punctuation
    or the end of the trace. Reported next to the loose readout and next to the
    constant-"no" and constant-"yes" baselines, so the fallback's information
    content can be measured rather than assumed.
    """
    per = collections.OrderedDict()
    divergent = []
    for arm in ARMS:
        rows = {}
        for budget in BUDGETS:
            recs = [r for r in records if r["arm"] == arm
                    and r["budget"] == budget]
            loose = strict = strict_agree = 0
            for r in recs:
                reasoning = (r["attempts"][-1].get("reasoning")
                             if r["attempts"] else "") or ""
                if r["reasoning_answer"] is not None:
                    loose += 1
                m = strict_last_trace_token(reasoning)
                if m:
                    strict += 1
                    strict_agree += int((1 if m == "yes" else 0) == r["gold"])
            rows[budget] = {
                "cells": len(recs),
                "loose_trace_token": loose,
                "strict_commitment": strict,
                "strict_agrees_with_gold": strict_agree,
            }
        per[arm] = rows
    # whole-grid readout comparison
    tokens = [r["reasoning_answer"] for r in records
              if r["reasoning_answer"] is not None]
    loose_correct = sum(1 for r in records if r["reasoning_answer"] is not None
                        and (1 if r["reasoning_answer"] == "yes" else 0)
                        == r["gold"])
    strict_cells = 0
    strict_correct = 0
    for r in records:
        reasoning = (r["attempts"][-1].get("reasoning")
                     if r["attempts"] else "") or ""
        m = strict_last_trace_token(reasoning)
        if m:
            strict_cells += 1
            ok = (1 if m == "yes" else 0) == r["gold"]
            strict_correct += int(ok)
            if r["content_answer"] is None and not ok:
                divergent.append({"item_id": r["item_id"], "arm": r["arm"],
                                  "budget": r["budget"],
                                  "strict_token": m, "gold": r["gold"]})
    n = len(records)
    gold_no = sum(1 for r in records if r["gold"] == 0)
    return {
        "declared_post_hoc": True,
        "rule": "a trace yes/no counts only if it is outside a yes/no or "
                "yes-or-no phrase and is followed by end-of-text or "
                "sentence-final punctuation",
        "per_arm_budget": {arm: {str(b): v for b, v in rows.items()}
                           for arm, rows in per.items()},
        "grid": {
            "records": n,
            "gold_no_share": round(gold_no / n, 4),
            "loose_trace_token_records": len(tokens),
            "loose_token_distribution": dict(
                collections.Counter(tokens)),
            "loose_agrees_with_gold": loose_correct,
            "loose_accuracy": round(loose_correct / n, 4),
            "strict_commitment_records": strict_cells,
            "strict_agrees_with_gold": strict_correct,
            "strict_accuracy_over_all_records": round(strict_correct / n, 4),
            "strict_accuracy_within_commitments": (
                round(strict_correct / strict_cells, 4) if strict_cells
                else None),
            "constant_no_accuracy": round(gold_no / n, 4),
            "constant_yes_accuracy": round((n - gold_no) / n, 4),
            "answer_field_only_accuracy": round(sum(
                1 for r in records if r["content_answer"] is not None
                and (1 if r["content_answer"] == "yes" else 0) == r["gold"])
                / n, 4),
        },
        "un_surfaced_commitments_disagreeing_with_gold": divergent,
    }


def per_cell_table(records: list) -> dict:
    """Per (item, arm): the budget ladder outcomes and the two thresholds."""
    cells: dict = {}
    for rec in records:
        key = (rec["item_id"], rec["arm"])
        cell = cells.setdefault(key, {"item_id": rec["item_id"],
                                      "arm": rec["arm"], "gold": rec["gold"],
                                      "ladder": {}, "thresholds": {}})
        att = rec["attempts"][-1] if rec["attempts"] else {}
        cell["ladder"][rec["budget"]] = {
            "outcome": rec["outcome"],
            "content_answer": rec["content_answer"],
            "reasoning_answer": rec["reasoning_answer"],
            "declared_answer": rec["declared_answer"],
            "declared_source": rec["declared_source"],
            "completion_tokens": att.get("completion_tokens", 0),
            "finish_reason": att.get("finish_reason"),
            "coverage_ratio": att.get("mechanics", {}).get("coverage_ratio"),
            "reasoning_commit_fraction": att.get("mechanics", {}).get(
                "reasoning_commit_fraction"),
        }
    for cell in cells.values():
        gold = cell["gold"]
        surf = {b: (v["content_answer"] == "yes" if gold == 1 else
                    v["content_answer"] == "no")
                for b, v in cell["ladder"].items()}
        trace = {b: (v["reasoning_answer"] == "yes" if gold == 1 else
                     v["reasoning_answer"] == "no")
                 for b, v in cell["ladder"].items()}
        cell["threshold_content"] = threshold(surf, BUDGETS)
        cell["threshold_trace"] = threshold(trace, BUDGETS)
        cell["surfaced_anywhere"] = any(surf.values())
        cell["in_trace_anywhere"] = any(trace.values())
        cell["unsurfaced_at"] = [b for b in BUDGETS
                                 if trace.get(b) and not surf.get(b)]
        if (cell["threshold_content"] is not None
                and cell["threshold_trace"] is not None):
            cell["surfacing_extra_tokens"] = (cell["threshold_content"]
                                              - cell["threshold_trace"])
        else:
            cell["surfacing_extra_tokens"] = None
    return cells


def per_arm_budget(records: list) -> dict:
    out: dict = {}
    for arm in ARMS:
        rows = {}
        for budget in BUDGETS:
            recs = [r for r in records if r["arm"] == arm
                    and r["budget"] == budget]
            surfaced = sum(1 for r in recs if r["content_answer"] is not None)
            trace_only = sum(1 for r in recs if r["content_answer"] is None
                             and r["reasoning_answer"] is not None)
            unanswered = sum(1 for r in recs if r["declared_answer"] is None)
            correct_content = sum(1 for r in recs
                                  if r["content_answer"] is not None
                                  and (1 if r["content_answer"] == "yes"
                                       else 0) == r["gold"])
            correct_declared = sum(1 for r in recs if r["correct"] == 1)
            cov = [r["attempts"][-1]["mechanics"]["coverage_ratio"]
                   for r in recs if r["attempts"]
                   and r["attempts"][-1].get("mechanics", {}).get(
                       "coverage_ratio") is not None]
            rows[budget] = {
                "cells": len(recs),
                "surfaced_in_answer_field": surfaced,
                "trace_only": trace_only,
                "unanswered_by_declared_parser": unanswered,
                "correct_in_answer_field": correct_content,
                "correct_by_declared_parser": correct_declared,
                "mean_completion_tokens": round(
                    sum(r["attempts"][-1]["completion_tokens"] for r in recs
                        if r["attempts"]) / max(1, sum(
                            1 for r in recs if r["attempts"])), 1),
                "mean_coverage_ratio": (round(sum(cov) / len(cov), 4)
                                        if cov else None),
                "wilson_low_correct_declared": round(
                    wilson(correct_declared, len(recs))[0], 4),
            }
        out[arm] = rows
    return out


def evaluate_predictions(cells: dict, arm_budget: dict,
                         round17: dict) -> dict:
    out = {}
    mono = {}
    for arm in ARMS:
        seq = [arm_budget[arm][b]["surfaced_in_answer_field"]
               for b in BUDGETS]
        mono[arm] = {"series": seq, "non_decreasing":
                     monotone_non_decreasing(seq)}
    out["P1_surfacing_monotonicity"] = {
        "holds": all(v["non_decreasing"] for v in mono.values()),
        "per_arm": mono}

    op = {arm: arm_budget[arm][OPERATING_BUDGET]["surfaced_in_answer_field"]
          for arm in ARMS}
    p2_items = []
    p2_items.append(("F1 surfaces 3 of 3 at 2048", op["F1"] == 3))
    p2_items.append(("X surfaces 0 of 3 at 2048", op["X"] == 0))
    p2_items.append(("F1 >= X at every budget",
                     all(arm_budget["F1"][b]["surfaced_in_answer_field"]
                         >= arm_budget["X"][b]["surfaced_in_answer_field"]
                         for b in BUDGETS)))
    out["P2_arm_asymmetry_at_operating_point"] = {
        "holds": all(ok for _, ok in p2_items),
        "surface_counts_at_operating_budget": op,
        "clauses": {name: ok for name, ok in p2_items}}

    bad = [{"item_id": r["item_id"], "arm": r["arm"], "budget": r["budget"],
            "content_answer": r["content_answer"], "gold": r["gold"]}
           for r in _records_cache if r["content_answer"] is not None
           and (1 if r["content_answer"] == "yes" else 0) != r["gold"]]
    out["P3_correctness_invariance"] = {
        "holds": not bad, "wrong_answer_field_answers": bad}

    rows = []
    for cell in cells.values():
        tc, tt = cell["threshold_content"], cell["threshold_trace"]
        rows.append({"item_id": cell["item_id"], "arm": cell["arm"],
                     "threshold_trace": tt, "threshold_content": tc,
                     "satisfied": (tt is None or tc is None or tt <= tc)})
    out["P4_trace_before_surface"] = {
        "holds": all(r["satisfied"] for r in rows),
        "violations": [r for r in rows if not r["satisfied"]],
        "cells_with_both_thresholds": sum(
            1 for r in rows if r["threshold_trace"] is not None
            and r["threshold_content"] is not None)}

    agree = 0
    compared = 0
    disc_self_only = 0
    disc_arch_only = 0
    for r in _records_cache:
        if r["budget"] != OPERATING_BUDGET:
            continue
        arch = round17.get((r["item_id"], r["arm"]))
        if not arch:
            continue
        compared += 1
        mine = r["declared_answer"]
        theirs = arch.get("answer")
        if mine is not None and mine == theirs:
            agree += 1
        elif mine is not None and theirs is None:
            disc_self_only += 1
        elif theirs is not None and mine is None:
            disc_arch_only += 1
    out["P5_operating_point_pairing"] = {
        "holds": compared > 0 and agree == compared,
        "cells_compared": compared, "answers_agreeing": agree,
        "exact_mcnemar_p": round(mcnemar_exact(disc_self_only,
                                               disc_arch_only), 4),
        "discordant_this_round_only": disc_self_only,
        "discordant_archive_only": disc_arch_only}
    return out


_records_cache: list = []


def trace_surface_gap(cells: dict) -> dict:
    """The round's headline quantity: correct answers that exist in the trace
    but never reach the answer field, and the extra budget surfacing needs."""
    pairs = sum(len(c["unsurfaced_at"]) for c in cells.values())
    extras = [c["surfacing_extra_tokens"] for c in cells.values()
              if c["surfacing_extra_tokens"] is not None]
    never_surfaced = [f"{c['item_id']}/{c['arm']}" for c in cells.values()
                      if c["in_trace_anywhere"] and not c["surfaced_anywhere"]]
    never_any = [f"{c['item_id']}/{c['arm']}" for c in cells.values()
                 if not c["in_trace_anywhere"] and not c["surfaced_anywhere"]]
    return {
        "cell_budget_pairs_with_correct_answer_in_trace_only": pairs,
        "cell_budget_pairs_total": len(cells) * len(BUDGETS),
        "cells_never_surfaced_but_present_in_trace": never_surfaced,
        "cells_absent_from_both_fields_at_every_budget": never_any,
        "extra_budget_to_surface_tokens": {
            "values": sorted(extras),
            "median": (round(sorted(extras)[len(extras) // 2], 1)
                       if extras else None),
            "n": len(extras)},
    }


def token_law(arm_budget: dict) -> dict:
    return {arm: {str(b): arm_budget[arm][b]["mean_completion_tokens"]
                  for b in BUDGETS} for arm in ARMS}


def analyse(records: list, gate: dict, transport: dict) -> dict:
    global _records_cache
    _records_cache = records
    for rec in records:
        missing = [f for f in CELL_FIELDS if f not in rec]
        if missing:
            raise SystemExit(f"raw record missing fields {missing}: "
                             f"{rec.get('item_id')}/{rec.get('arm')}")
    cells = per_cell_table(records)
    arm_budget = per_arm_budget(records)
    round17 = load_archive_cells(ROUND17_RAW)
    predictions = evaluate_predictions(cells, arm_budget, round17)

    per_budget = {}
    for budget in BUDGETS:
        recs = [r for r in records if r["budget"] == budget]
        surfaced = sum(1 for r in recs if r["content_answer"] is not None)
        declared = sum(1 for r in recs if r["declared_answer"] is not None)
        correct_declared = sum(1 for r in recs if r["correct"] == 1)
        per_budget[budget] = {
            "cells": len(recs),
            "surfaced_in_answer_field": surfaced,
            "answerable_by_declared_parser": declared,
            "rescued_from_trace": declared - surfaced,
            "correct_by_declared_parser": correct_declared,
            "correct_among_surfaced": sum(
                1 for r in recs if r["content_answer"] is not None
                and (1 if r["content_answer"] == "yes" else 0) == r["gold"]),
            "wilson_low_correct_declared": round(
                wilson(correct_declared, len(recs))[0], 4),
        }

    # Oracle agreement on answered cells: traversal vs undirected connectivity.
    oracles = {}
    for name, pred in (("traversal", {"F1": 1, "R1": 0, "X": 0}),
                       ("undirected_connectivity",
                        {"F1": 1, "R1": 1, "X": 0})):
        for budget in BUDGETS:
            recs = [r for r in records if r["budget"] == budget
                    and r["declared_answer"] is not None]
            hits = sum(1 for r in recs
                       if pred[r["arm"]] == (1 if r["declared_answer"] == "yes"
                                             else 0))
            oracles.setdefault(name, {})[budget] = {
                "answered": len(recs), "matches": hits}
    return {
        "schema": "round19-summary-v1",
        "created_at": now_iso(),
        "gate_hash": gate["gate_hash"],
        "seed_base": SEED_BASE,
        "endpoint_class": gate["endpoint_class"],
        "per_budget": {str(k): v for k, v in per_budget.items()},
        "per_arm_budget": {arm: {str(b): v for b, v in rows.items()}
                           for arm, rows in arm_budget.items()},
        "per_cell": {f"{k[0]}/{k[1]}": v for k, v in sorted(cells.items())},
        "trace_surface_gap": trace_surface_gap(cells),
        "trace_token_provenance_post_hoc": trace_provenance(records),
        "strict_commitment_post_hoc": strict_commitment(records),
        "token_law_mean_completion_tokens": token_law(arm_budget),
        "oracles": {k: {str(b): v for b, v in rows.items()}
                    for k, rows in oracles.items()},
        "predictions": predictions,
        "transport": transport,
        "attempt_tally": {
            "records": len(records),
            "attempts": sum(len(r["attempts"]) for r in records),
            "retries": sum(max(0, len(r["attempts"]) - 1) for r in records),
            "abandoned": sum(1 for r in records
                             if r["outcome"] == "abandoned_budget"),
            "transport_failures": sum(
                1 for r in records for a in r["attempts"]
                if a.get("error_class")),
        },
        "evidence_label": "Executed",
    }


# -------------------------------------------------------------------- selftest

def selftest() -> int:
    checks = []

    def check(name: str, ok: bool) -> None:
        checks.append((name, bool(ok)))

    def approx(a: float, b: float, tol: float = 1e-6) -> bool:
        return abs(a - b) <= tol

    # --- arithmetic utilities
    check("wilson_zero_total", wilson(0, 0) == (0.0, 0.0))
    lo, hi = wilson(9, 9)
    check("wilson_9_of_9_low_matches_round15", approx(lo, 0.7005, 1e-3))
    check("wilson_brackets_point", lo < 1.0 <= hi)
    lo2, hi2 = wilson(0, 9)
    check("wilson_zero_success_low_is_zero", approx(lo2, 0.0, 1e-9))
    check("wilson_wider_than_wald_low", lo2 < 0.0 + 1e-9)
    check("mcnemar_no_discordant", mcnemar_exact(0, 0) == 1.0)
    check("mcnemar_symmetric",
          approx(mcnemar_exact(1, 4), mcnemar_exact(4, 1), 1e-12))
    check("mcnemar_2_of_2", approx(mcnemar_exact(2, 0), 0.5, 1e-12))
    check("mcnemar_capped", mcnemar_exact(1, 0) <= 1.0)
    check("log_choose_values", approx(log_choose(5, 2), math.log(10), 1e-12))
    check("log_choose_out_of_range", log_choose(5, 6) == -math.inf)
    check("monotone_true", monotone_non_decreasing([1, 1, 2, 3]))
    check("monotone_false", not monotone_non_decreasing([3, 1, 2]))
    check("monotone_single", monotone_non_decreasing([5]))
    check("threshold_first_hit",
          threshold({256: False, 640: True, 1280: True, 2048: False},
                    BUDGETS) == 640)
    check("threshold_none_when_all_false",
          threshold({b: False for b in BUDGETS}, BUDGETS) is None)
    check("threshold_missing_keys_safe", threshold({}, BUDGETS) is None)

    # --- parser: field separation and its negative controls
    p = parse_fields("no", "the answer is yes")
    check("content_wins_over_reasoning",
          p["declared_answer"] == "no" and p["declared_source"] == "content")
    check("fields_parsed_separately",
          p["content_answer"] == "no" and p["reasoning_answer"] == "yes")
    p = parse_fields("", "maybe yes then no then yes")
    check("reasoning_fallback_when_content_empty",
          p["declared_answer"] == "yes" and p["declared_source"] == "reasoning")
    p = parse_fields("Final: NO.", "reasoning yes")
    check("last_standalone_token_in_content", p["content_answer"] == "no")
    p = parse_fields("yesterday no idea", "x")
    check("word_boundary_rejects_substrings", p["content_answer"] == "no")
    p = parse_fields("nope never", "nothing")
    check("no_false_positive_on_nope",
          p["content_answer"] is None and p["reasoning_answer"] is None)
    p = parse_fields("", "")
    check("empty_fields_parse_to_none",
          p["declared_answer"] is None and p["declared_source"] == "none")
    check("offset_recorded", parse_fields("yes", "")["content_offset"] == 0)

    # --- outcome classification
    base = {"error_class": None, "completion_tokens": 100,
            "content_answer": "yes", "reasoning_answer": "no"}
    check("classify_answered_in_answer_field",
          classify_attempt(dict(base)) == "answered_in_answer_field")
    check("classify_trace_only", classify_attempt(
        {**base, "content_answer": None}) == "trace_only")
    check("classify_truncated_no_answer", classify_attempt(
        {**base, "content_answer": None, "reasoning_answer": None,
         "finish_reason": "length"}) == "truncated_no_answer")
    check("classify_no_answer_stop", classify_attempt(
        {**base, "content_answer": None, "reasoning_answer": None,
         "finish_reason": "stop"}) == "no_answer_stop")
    check("classify_empty_completion", classify_attempt(
        {**base, "completion_tokens": 0}) == "empty_completion")
    check("classify_transport", classify_attempt(
        {**base, "error_class": "timeout"}) == "transport_timeout")
    check("retryable_excludes_truncation",
          not is_retryable("truncated_no_answer")
          and not is_retryable("trace_only")
          and is_retryable("transport_http_500")
          and is_retryable("empty_completion"))

    # --- sanitizer
    check("sanitize_strips_url",
          "[redacted]" in sanitize("see https://example.invalid/a/b for info"))
    check("sanitize_strips_ip",
          "[redacted]" in sanitize("host 10.0.0.7 answered"))
    check("sanitize_strips_path",
          "[redacted]" in sanitize("weights /var/lib/models/weights.bin used"))
    check("sanitize_keeps_clean_text",
          sanitize("the chain has 24 hops, answer no") ==
          "the chain has 24 hops, answer no")

    # --- graph mechanics
    facts = [("a", "precedes", "b"), ("b", "precedes", "c"),
             ("c", "precedes", "d"), ("x", "precedes", "y")]
    adj, und, in_deg, out_deg, nodes = graph_of(facts)
    check("reachability_forward", directed_reachable("a", "d", adj))
    check("reachability_reverse_fails",
          not directed_reachable("d", "a", adj))
    check("undirected_distance", undirected_distance("d", "a", und) == 3)
    comp = components(nodes, und)
    check("components_separate", comp["a"] != comp["x"])
    check("degree_profile", in_deg["b"] == 1 and out_deg["d"] == 0)
    check("prefix_hops_ordered",
          ordered_prefix_hops(["a", "b", "c"], "a then b then c done") == 3)
    check("prefix_hops_out_of_order_loses_the_tail",
          ordered_prefix_hops(["a", "b", "c"], "a then c then b") == 2)
    check("prefix_hops_strict_order",
          ordered_prefix_hops(["a", "b", "c"], "a b c") == 3)
    check("prefix_hops_zero_when_absent",
          ordered_prefix_hops(["a", "b"], "nothing here") == 0)
    item = {"path": ["a", "b", "c", "d"]}
    att = {"reasoning": "a then b then c", "content": "",
           "completion_tokens": 128, "reasoning_answer": "no",
           "reasoning_offset": 20}
    mech = mechanics(item, "F1", att, 256)
    check("mechanics_coverage_four_expected", mech["expected_hops"] == 4)
    check("mechanics_coverage_ratio", mech["coverage_ratio"] == 0.75)
    check("mechanics_budget_utilisation", mech["budget_utilisation"] == 0.5)
    check("mechanics_commit_fraction",
          mech["reasoning_commit_fraction"] == round(20 / 15, 4))
    check("mechanics_r1_has_no_coverage",
          mechanics(item, "R1", att, 256)["coverage_ratio"] is None)

    # --- corpus identity and matchedness (real generator run)
    gen = sha256_file(LADDERS_PATH)
    check("generator_sha_matches_round_pin", gen == GENERATOR_SHA256)
    blob = pool_blob_sha256()
    check("l24_blob_matches_round_pin",
          blob[f"generated/l{LEVEL}.jsonl"] == L24_BLOB_PIN)
    built = build_matched_items()
    items = built["items"]
    check("items_selected", len(items) == ITEMS_PER_LEVEL)
    check("chain_length_is_level",
          all(i["chain_len"] == LEVEL for i in items))
    inv = matched_invariant(items)
    check("matched_invariant_clean", not inv["violations"])
    check("nine_cells_per_budget", inv["cells_per_budget"] == 9)
    check("disagreeing_cells_are_the_reverse_arms",
          inv["cells_where_connectivity_and_reachability_disagree"]
          == ITEMS_PER_LEVEL)
    rebuilt_items = build_matched_items()["items"]
    rebuilt = matched_invariant(rebuilt_items)
    check("rebuild_clean", not rebuilt["violations"])
    check("rebuild_deterministic",
          sha256_text(canonical(fingerprint_of(items)))
          == sha256_text(canonical(fingerprint_of(rebuilt_items))))
    check("gold_is_reachable_for_positive_arms",
          all(i["arms"]["F1"]["directed_reach"] == 1 for i in items))
    check("reverse_arm_is_connected_but_unreachable",
          all(i["arms"]["R1"]["directed_reach"] == 0
              and i["arms"]["R1"]["same_component"] == 1 for i in items))
    check("cross_arm_is_unconnected",
          all(i["arms"]["X"]["directed_reach"] == 0
              and i["arms"]["X"]["same_component"] == 0 for i in items))
    check("expected_traversal_lengths",
          len(expected_traversal(items[0], "F1")) == LEVEL + 1
          and len(expected_traversal(items[0], "X")) == LEVEL
          and expected_traversal(items[0], "R1") is None)

    # --- leak battery: must not fire on this corpus, must fire on a leak
    batt = battery_on_matched(items)
    check("battery_has_no_firing_leak_rule", batt["passed"])
    check("battery_reachability_oracle_is_perfect",
          batt["rules"]["directed_reachability"]["accuracy"] == 1.0)
    check("battery_connectivity_oracle_fails_exactly_the_reverse_arm",
          abs(batt["rules"]["undirected_connectivity"]["accuracy"]
              - 6 / 9) < 1e-9)
    check("battery_constants_are_not_significant",
          not batt["rules"]["all_yes"]["fires"]
          and not batt["rules"]["all_no"]["fires"])
    fake_facts = [("a", "precedes", "b"), ("c", "precedes", "d")]
    leaked = []
    for idx in range(ITEMS_PER_LEVEL):
        leaked.append({"item_id": f"FAKE-{idx}", "path": ["a", "b", "d"],
                       "facts": list(fake_facts),
                       "arms": {
                           "F1": {"src": "a", "dst": "d", "gold": 1},
                           "R1": {"src": "c", "dst": "a", "gold": 0},
                           "X": {"src": "a", "dst": "b", "gold": 0}}})
    leak_batt = battery_on_matched(leaked)
    check("battery_can_fire_on_a_planted_leak",
          leak_batt["rules"]["dst_is_last_fact_object"]["accuracy"] == 1.0
          and "dst_is_last_fact_object" in leak_batt["firing_leak_rules"]
          and not leak_batt["passed"])
    check("battery_rule_count", len(leak_batt["rules"])
          == len(LEAK_RULES) + len(REFERENCE_RULES))

    # --- thresholds and gap analysis on a synthetic ladder
    fake = {
        "cellA": {"item_id": "L24-1", "threshold_trace": 256,
                  "threshold_content": 1280,
                  "surfaced_anywhere": True, "in_trace_anywhere": True,
                  "unsurfaced_at": [256, 640],
                  "surfacing_extra_tokens": 1024, "arm": "X", "gold": 0},
        "cellB": {"item_id": "L24-2", "threshold_trace": 2048,
                  "threshold_content": None,
                  "surfaced_anywhere": False, "in_trace_anywhere": True,
                  "unsurfaced_at": [2048],
                  "surfacing_extra_tokens": None, "arm": "X", "gold": 0},
    }
    gap = trace_surface_gap(fake)
    check("gap_counts_trace_only_pairs",
          gap["cell_budget_pairs_with_correct_answer_in_trace_only"] == 3)
    check("gap_lists_never_surfaced_cell",
          gap["cells_never_surfaced_but_present_in_trace"] == ["L24-2/X"])
    check("gap_median_extra_budget",
          gap["extra_budget_to_surface_tokens"]["median"] == 1024)

    # --- prediction evaluation on a synthetic outcome set
    synth = []
    for arm, series in (("F1", ["yes", "yes", "yes", "yes"]),
                        ("X", [None, None, None, None])):
        for budget, val in zip(BUDGETS, series):
            synth.append({"item_id": "L24-1", "arm": arm, "budget": budget,
                          "content_answer": val,
                          "reasoning_answer": ("yes" if arm == "X" else val),
                          "declared_answer": val or ("yes" if arm == "X"
                                                     else None),
                          "declared_source": "content" if val else "reasoning",
                          "outcome": "answered_in_answer_field" if val
                          else ("trace_only" if arm == "X" else
                                "no_answer_stop"),
                          "gold": GOLD[arm] if arm != "X" else 1,
                          "attempts": [{"completion_tokens": budget,
                                        "mechanics": {}}],
                          "correct": 1 if (val or arm == "X") else 0})
    _set_cache(synth)
    cells_s = per_cell_table(synth)
    partial_cell = per_cell_table(
        [dict(r, item_id="L24-9") for r in synth[:2]])
    check("incomplete_ladder_does_not_crash",
          partial_cell[("L24-9", "F1")]["threshold_content"] == 256
          and 2048 not in partial_cell[("L24-9", "F1")]["ladder"])
    ab_s = per_arm_budget(synth)
    preds = evaluate_predictions(cells_s, ab_s, {})
    check("synthetic_P1_holds",
          preds["P1_surfacing_monotonicity"]["holds"])
    check("synthetic_P2_false_without_operating_point",
          not preds["P2_arm_asymmetry_at_operating_point"]["holds"])
    check("synthetic_P3_holds", preds["P3_correctness_invariance"]["holds"])
    check("synthetic_P5_no_archive_is_not_claimed",
          not preds["P5_operating_point_pairing"]["holds"])
    wrong_set = ([dict(synth[0], content_answer="no", gold=1, correct=0)]
                 + [dict(s) for s in synth[1:]])
    _set_cache(wrong_set)
    preds_w = evaluate_predictions(per_cell_table(wrong_set),
                                   per_arm_budget(wrong_set), {})
    check("synthetic_P3_catches_a_wrong_surfaced_answer",
          not preds_w["P3_correctness_invariance"]["holds"])
    _set_cache(synth)
    preds_2 = evaluate_predictions(cells_s, ab_s,
                                   {("L24-1", "F1"): {"answer": "yes"}})
    check("synthetic_P5_agreement_with_archive",
          preds_2["P5_operating_point_pairing"]["holds"])
    preds_3 = evaluate_predictions(cells_s, ab_s,
                                   {("L24-1", "F1"): {"answer": "no"}})
    check("synthetic_P5_catches_disagreement",
          not preds_3["P5_operating_point_pairing"]["holds"])

    # --- post-hoc provenance classes for the trace token
    def _prov_rec(rid, reasoning, gold, arm):
        toks = list(ANSWER_RE.finditer(reasoning))
        return {"item_id": rid, "arm": arm, "gold": gold, "budget": 256,
                "attempts": [{"reasoning": reasoning, "content": "",
                              "completion_tokens": 10}],
                "reasoning_answer": toks[-1].group(1).lower() if toks else None}

    tail = "h" * 200
    prov_set = [
        _prov_rec("A", "We must answer exactly one word yes/no. Tracing now",
                  1, "F1"),
        _prov_rec("B", tail + " so the answer is yes", 1, "F1"),
        _prov_rec("C", "we need yes or no here. then more work " + tail,
                  0, "X"),
        _prov_rec("D", "a long traversal with zero candidate tokens at all",
                  0, "R1"),
        _prov_rec("E", "so no, but the traversal goes on " + tail, 0, "R1"),
    ]
    prov = trace_provenance(prov_set)
    cls = prov["classes"]
    check("provenance_detects_instruction_echo",
          cls["instruction_echo"]["records"] == 2)
    check("provenance_echo_is_always_no_and_wrong_on_a_yes_arm",
          prov["last_trace_token_by_gold"].get("instruction_echo|gold_yes") == 1)
    check("provenance_detects_terminal_token",
          cls["terminal"]["records"] == 1
          and cls["terminal"]["agrees_with_gold"] == 1)
    check("provenance_detects_mid_trace_mention",
          cls["mid_trace"]["records"] == 1
          and cls["mid_trace"]["agrees_with_gold"] == 1)
    check("provenance_handles_absent_token",
          cls["no_trace_token"]["records"] == 1
          and cls["no_trace_token"]["agreement_with_gold"] is None)
    check("provenance_constant_no_baseline",
          prov["fallback_readout"]["constant_no_baseline_accuracy"]
          == round(3 / 5, 4))
    check("provenance_token_distribution_counted",
          sum(prov["fallback_readout"]["token_distribution"].values()) == 4)

    # --- strict commitment rule (post-hoc control) positive/negative controls
    check("strict_rejects_instruction_echo",
          strict_last_trace_token("We need answer yes/no to proceed") is None)
    check("strict_rejects_bookkeeping_prose",
          strict_last_trace_token("No other incoming. More work follows here"
                                  " in the trace") is None)
    check("strict_rejects_distractor_phrase",
          strict_last_trace_token("Need final one word. Ensure no extra. Then"
                                  " more enumeration continues on") is None)
    check("strict_accepts_cued_verdict",
          strict_last_trace_token("walk the chain, sum the hops. Thus yes.")
          == "yes")
    check("strict_accepts_trace_final_token",
          strict_last_trace_token("a long enumeration of facts and then no")
          == "no")
    check("strict_takes_the_last_qualifying_token",
          strict_last_trace_token("Thus no. More work. Thus yes.") == "yes")

    # --- record schema guard
    ok_rec = {f: None for f in CELL_FIELDS}
    check("schema_complete_on_full_record",
          not [f for f in CELL_FIELDS if f not in ok_rec])
    partial = {k: v for k, v in ok_rec.items() if k != "budget"}
    check("schema_detects_missing_field",
          bool([f for f in CELL_FIELDS if f not in partial]))

    # --- caps
    check("prompt_cap_respected",
          len(items) * len(ARMS) * len(BUDGETS) + HEALTH_PROMPTS
          <= MAX_PROMPTS)
    check("operating_budget_is_the_protocol_ceiling",
          OPERATING_BUDGET == 2048 and max(BUDGETS) <= 2048)
    check("budget_ladder_is_ordered",
          all(a < b for a, b in zip(BUDGETS, BUDGETS[1:])))

    failed = [name for name, ok in checks if not ok]
    print(f"selftest: {len(checks)} checks, {len(failed)} failures")
    for name in failed:
        print(f"  FAIL {name}")
    return 1 if failed else 0


def _set_cache(records: list) -> None:
    global _records_cache
    _records_cache = records


# ------------------------------------------------------------------------- CLI

def load_gate() -> dict:
    if not os.path.exists(GATE_PATH):
        raise SystemExit("gate.json missing; run --gate first")
    with open(GATE_PATH, "r", encoding="utf-8") as fh:
        gate = json.load(fh)
    if gate.get("gate_hash") != gate_seed_hash(gate):
        raise SystemExit("gate.json hash mismatch: the gate was edited")
    return gate


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--resume", action="store_true",
                    help="with --probe: continue a raw.jsonl left by an "
                         "interrupted dispatch (same gate hash required)")
    ap.add_argument("--analyze", action="store_true")
    args = ap.parse_args(argv)

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
        print(f"nine-cell battery firing: "
              f"{gate['leak_battery']['firing_leak_rules']}")
        print(f"pairing verified: {gate['pairing']['verified']} "
              f"(r15 {gate['pairing']['round15_prompt_sha_matches']}, "
              f"r17 {gate['pairing']['round17_prompt_sha_matches']} of "
              f"{gate['pairing']['expected_cells']})")
        print(f"l24 pin equal: "
              f"{gate['item_source']['l24_pin_check']['expected'] == gate['item_source']['l24_pin_check']['actual']}")
        return 0

    gate = load_gate()
    items = build_matched_items()["items"]
    invariant = matched_invariant(items)
    if invariant["violations"]:
        raise SystemExit(f"matched-pair invariant violated: "
                         f"{invariant['violations']}")
    if args.probe:
        if os.path.exists(RAW_PATH) and not args.resume:
            raise SystemExit("raw.jsonl already exists; remove it to "
                             "re-dispatch, or pass --resume to continue an "
                             "interrupted dispatch under the same gate")
        pairing = verify_pairing(items)
        if not pairing["verified"]:
            raise SystemExit("prompt pairing unverified; refusing to spend "
                             f"prompts: {pairing['cells'][:3]}")
        cap = AttemptBudget(MAX_PROMPTS)
        hc = health_check()
        cap.used += 1
        if not hc["ok"]:
            print(f"health check failed: {hc}", file=sys.stderr)
            return 2
        print(f"health ok: {hc['latency_s']} s, {hc['completion_tokens']} "
              f"completion tokens")
        t0 = time.monotonic()
        records, note = dispatch(items, gate, cap)
        wall = round(time.monotonic() - t0, 1)
        note["health"] = hc
        note["phase2_wall_s"] = wall
        note["total_endpoint_calls_including_health"] = cap.used
        note["attempt_cap"] = MAX_PROMPTS
        with open(os.path.join(HERE, "transport.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(note, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(f"probe wall: {wall} s for {len(records)} cells; endpoint "
              f"calls incl. health: {cap.used}")
        return 0
    if args.analyze:
        records = [json.loads(l) for l in open(RAW_PATH, encoding="utf-8")
                   if l.strip()]
        transport = {}
        if os.path.exists(os.path.join(HERE, "transport.json")):
            with open(os.path.join(HERE, "transport.json"),
                      encoding="utf-8") as fh:
                transport = json.load(fh)
        out = analyse(records, gate, transport)
        out["raw_sha256"] = sha256_file(RAW_PATH)
        out["gate_sha256"] = sha256_file(GATE_PATH)
        with open(SUMMARY_PATH, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(json.dumps(out["per_budget"], indent=2))
        print(json.dumps(out["per_arm_budget"], indent=2))
        print(json.dumps(out["trace_surface_gap"], indent=2))
        print(json.dumps(out["strict_commitment_post_hoc"]["grid"], indent=2))
        print(json.dumps(
            out["strict_commitment_post_hoc"]["per_arm_budget"], indent=2))
        print(json.dumps(out["predictions"], indent=2))
        print(json.dumps(out["attempt_tally"], indent=2))
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

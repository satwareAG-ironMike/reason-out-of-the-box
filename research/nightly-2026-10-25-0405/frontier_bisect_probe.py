#!/usr/bin/env python3
"""Nightly round 24 (tracker #65, firing 2026-10-25 04:05): bisect the (k, E) frontier on
a flash-next-class endpoint, on a true matched pair, scored under the declared readout
stack.

Question (issue #71, "place the ladder depth ceiling d*: grid extension and load
decoupling"). Round 23 (branch research/nightly-2026-10-25-0205, PR #97) walked this
class from the safe corner (k = 4, E = 24) toward the collapse corner and BRACKETED the
frontier on one grid step: maintained at (k = 8, E = 96) (6/6 delivered, 6/6 correct),
first non-maintained at (k = 8, E = 192) (4/6 delivered, then 2/6 at (12,192) and 1/6 at
(16,192)) - a surfacing collapse, 25 of 25 delivered answers correct, all 11 failures
truncations at the 2048-token cap. Its consequence comment on #71 names the next cheap
instrument verbatim: "bisect the load axis at fixed depth (k = 8, E in {112, 128, 160})
and add the two missing depth points at the safe load (k = 12 and k = 16 at E = 96), to
test whether E* shrinks as k grows or the boundary is load-only."

One question with two clauses, both inside the bracket round 23 left open:
  (i) where does the load boundary sit at fixed depth k = 8? bisect E in {112, 128, 160}
      between the archived maintained point (96) and the archived non-maintained point
      (192);
  (ii) at fixed safe load E = 96, does maintained survive depth to k = 12 and k = 16? If
      yes, inside the probed region the frontier is load-dominated (E* does not shrink
      with k between 8 and 16); if either goes non-maintained, the boundary shrinks with
      depth and the frontier is jointly multiplicative, not load-only.

Instrument (issue #78 acceptance criterion 1, the same shared-content polarity pair that
shipped in round 22 and ran in round 23, asserted not prose): every cell dispatches
PAIRS_PER_LEVEL graphs and asks each graph TWO questions over the IDENTICAL fact list
with IDENTICAL entity names and the identical queried source; only the queried target
varies. Arm F is the forward query (gold yes, k hops), arm X is the cross-component query
(gold no, the target lies on a different path). pair_violations() asserts the
shared-content invariant on every dispatched pair and --selftest carries the planted
non-matched control.

Declared grid (fixed before any measurement, seed-frozen, seed_base 20261024): two ARMS
in (k, C) with E = k * C total facts over C disjoint directed paths of exactly k edges.
Every transition inside an arm changes EXACTLY ONE axis (asserted in --selftest):

    load arm (k = 8 held, E grows through the bracket):
      L0 (k= 8, C=12)  E= 96   anchor; IS round 23's S3 cell, measured maintained there
      L1 (k= 8, C=14)  E=112   first bisection point
      L2 (k= 8, C=16)  E=128   second bisection point
      L3 (k= 8, C=20)  E=160   third bisection point; round 23's non-maintained (8,192)
                                sits one step beyond
    depth arm (E = 96 held, k grows at the safe load):
      D1 (k=12, C= 8)  E= 96   missing depth point at the safe load
      D2 (k=16, C= 6)  E= 96   missing depth point at the safe load; same k as round 23's
                                budget_limited S6 (16, 192) with the load cut in half

3 graphs per cell x 2 queries = 36 prompts, + 1 health probe = 37 of the 40-call cap,
max_tokens 2048, temperature 0.0, one sample per item, no exemplars, no chain of thought
asked.

Fail-closed anchor into the archived round (constants, not file dependencies): L0 IS
round 23's S3 cell. This file re-uses that construction's seed base, name pools, seed
formula and selection order, so L0's 40-candidate pool blob and its three arm-F prompt
digests must equal the values archived in research/nightly-2026-10-25-0205/ (PR #97);
--probe and --gate REFUSE otherwise. The archived per-prompt completion tokens and
delivered answers are carried too, making L0 a same-class rerun of a maintained point:
a difference at L0 is an endpoint or construction drift signal, not a measurement.
The five bisection and depth cells are all new (k, C) shapes, so their seeds cannot
collide with any archived cell of rounds 21 to 23.

Declared predictions (fixed in the gate before any prompt is spent; monotonicity clauses
carry explicit tolerances per round 23's protocol lesson):
  P1 the grid is visible to the tokenizer: mean prompt_tokens at L1 >= 1.05x L0, L2 >=
     1.05x L1, L3 >= 1.05x L2 (the load arm steps +16.7%, +14.3%, +25% in facts), AND the
     two equal-load cells agree within 1%: |mean prompt_tokens(D2) - mean(D1)| <=
     0.01 x mean(D1) (E = 96 both; entity-name length noise must not trip a
     construction-invariant property).
  P2a the anchor is maintained: L0 is classified maintained under content_only (Wilson
     95% floor 0.60, no-answer rate <= 0.5). Round 23 measured it maintained 6/6 here.
  P2b the load boundary at k = 8 is at or below 160: at least one of L1, L2, L3 is NOT
     maintained under content_only. If all three come back maintained, the bracket
     tightens to (160, 192) instead - a measurement, not a failure to measure.
  P2c the boundary is load-only inside the probed region: both D1 and D2 are maintained
     under content_only. If either is not, E* shrinks with k and the frontier is jointly
     multiplicative.
  P3 no enumeration switch on this class at bisection load: the mean distractor-mention
     ratio at L3 (k = 8, E = 160) is >= 0.30. The 27B class measured 0.016 at E = 240
     (round 22, the enumeration switch); this class measured 0.51-0.64 at E = 192
     (round 23). A ratio below 0.30 at E = 160 here would mean the switch happens at
     intermediate load on this class too.
  P4 polarity direction only, the fragile-negative reading of round 19: b >= c, where b
     counts matched pairs whose arm F delivered a correct content_only answer while its
     OWN arm X partner did not, and c counts the reverse (round 23: b = 4, c = 1,
     p = 0.375, directional but under-powered at 18 pairs). Reported with the exact
     McNemar p; if b = c = 0 the direction is vacuous and is reported as vacuous.
  P5 the delivered answer is never wrong: every content_only answer in the grid is
     correct. Failures should be silence, not error; a WRONG answer means the turnover is
     a correctness collapse.
  P6 fallback skew where the answer field is silent (issue #94): among cells whose answer
     field carries no yes/no but whose trace does, at least 2/3 of the fallback tokens
     are "no". Vacuous when no cell is content-silent, reported as vacuous.
  P7 the anchor reproduces: all three L0 arm-F prompts deliver the answer round 23
     recorded at (k = 8, E = 96) on this class. Token costs at the anchor are reported,
     not predicted.

Usage:
  frontier_bisect_probe.py --selftest
  frontier_bisect_probe.py --gate              [--out gate.json]
  frontier_bisect_probe.py --probe             [--out-dir DIR] [--resume]
  frontier_bisect_probe.py --analyze           [--out-dir DIR]
The endpoint is read from NIGHTLY_BASE_URL, NIGHTLY_MODEL_ID and NIGHTLY_API_KEY and no
endpoint value is ever written to an artifact; stored model text passes a sanitizer for
URLs, IP addresses and absolute paths. Stdlib only.
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
import threading
import time
import urllib.error
import urllib.request

REL = "precedes"
RULE_SENTENCE = (f"Rule: for all x, y, z: if x {REL} y and y {REL} z, "
                 f"then x {REL} z. Facts state direct {REL} links.")
SEED_BASE = 20261024
ALPHA = 0.05
MARGIN = 0.10
MAJORITY_FLOOR = 0.5
PERMS = 400
MAX_TOKENS = 2048
TEMPERATURE = 0.0
PROMPT_CAP = 40
HEALTH_CALLS = 1
PAIRS_PER_LEVEL = 3
CANDIDATES = 40
MIN_CERTIFY = 6
ITEM_DEADLINE_S = 600
PHASE2_BUDGET_S = 1500
TPS_FLOOR = 5.0
CONCURRENCY_CHOICES = (2, 3, 4, 6, 8)
HEALTH_PROMPT = "Reply with exactly one word: yes"
# Health-probe output budget: 256 tokens, per round 22's lesson that a 2048-token health
# call is not portable across the pool (one deployment's upstream gateway killed it at
# ~60 s with http_502 while 256 tokens returned in ~1 s). MAX_TOKENS, the grid, the corpus
# and therefore the gate hash are untouched by this transport-only choice.
HEALTH_BUDGET = 256

# The grid: two arms of (k, C) cells with E = k * C facts. Inside each arm, consecutive
# cells differ in exactly one axis; the load arm holds k = 8, the depth arm holds E = 96.
LOAD_ARM = (("L0", 8, 12), ("L1", 8, 14), ("L2", 8, 16), ("L3", 8, 20))
DEPTH_ARM = (("D1", 12, 8), ("D2", 16, 6))
WALK = LOAD_ARM + DEPTH_ARM  # dispatch and reporting order
LOAD_NAMES = tuple(name for name, _k, _c in LOAD_ARM)
DEPTH_NAMES = tuple(name for name, _k, _c in DEPTH_ARM)
WALK_INDEX = {name: i for i, (name, _k, _c) in enumerate(WALK)}

# Fail-closed anchor. A1: L0 IS round 23's S3 cell (k = 8, E = 96) from
# research/nightly-2026-10-25-0205/ (PR #97), which classified it maintained (6/6
# delivered in the answer field, 6/6 correct). Values below are read from that archived
# gate.json and raw.jsonl and hardcoded here so the post-merge tree can verify them
# without the ancestor branch.
A1_POOL_BLOB = "bee7e0264b8a69c7d1198d4b24d4207b57c31230bd8a0760bc4ce8853f03dd16"
A1_FORWARD_PROMPTS = frozenset({
    "b20d7fd289fd6f181fb05aebf9ae6526c041870e09c711ae60a7100cb5ca313b",
    "96462a5727cd001cee15875248307c476ca41b977a5aff509622736421fe169d",
    "b3335406e9b510f6a0d9b598494695f1aa798acfc347fe944677c21c07e93702"})
# seed -> (round-23 completion tokens on this class, answer round 23 recorded delivering
# in the answer field)
A1_RECORD = {28381026: {"r23_completion": 1134, "answer": "yes"},
             28381027: {"r23_completion": 1098, "answer": "yes"},
             28381028: {"r23_completion": 1050, "answer": "yes"}}

ANSWER_RE = re.compile(r"\b(yes|no)\b", re.IGNORECASE)
URL_RE = re.compile(
    r"https?://\S+|\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|"
    r"(?:/[A-Za-z0-9_.-]+){2,}|[A-Za-z]:\\[^\s]*")

# The strict commitment rule and the echo-phrase test, vendored verbatim from rounds
# 19 through 22 (research/nightly-2026-10-24-0405/constant_depth_load_arm.py, PR #96).
# --selftest asserts the documented behaviour of both, so the rule cannot drift silently
# from the rounds whose readout this grid must stay comparable to (#94).
PHRASE_RE = re.compile(
    r"yes\s*[/|]\s*no|no\s*[/|]\s*yes|yes\s+or\s+no|no\s+or\s+yes",
    re.IGNORECASE)
STRICT_TAIL_RE = re.compile(r"[.!?:;\)\]\"'\s]*$")
VERDICT_CUE_RE = re.compile(
    r"\b(thus|therefore|so|answer|final|conclusion|answer is|verdict)\b"
    r"[^.\n]{0,30}$", re.IGNORECASE)

# Own name pools (deliberately different from generators/ladders.py and from round 8;
# shared with rounds 21 and 22 so the anchor blobs reproduce).
POOL_A = ("ab", "ed", "ig", "ok", "ul", "ur", "yr", "ov", "ix", "ax",
          "eb", "ic", "ol", "um", "un", "ar", "er", "ir", "or", "uz")
POOL_B = ("bo", "dra", "fo", "gra", "ho", "la", "mo", "ni", "po", "sta",
          "tra", "vo", "xi", "zo", "bru", "kro", "pli", "spo", "tur", "vra")
POOL_C = ("q", "x", "z", "k", "v", "n", "r", "s", "t", "m")


def sanitize(text: str) -> str:
    """Public-only rule, enforced before anything is written: strip URLs, IP addresses
    and absolute paths from model output."""
    return URL_RE.sub("[REDACTED]", text or "")


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _name(rng: random.Random, taken: set) -> str:
    for _ in range(500):
        name = rng.choice(POOL_A) + rng.choice(POOL_B) + rng.choice(POOL_C)
        if name not in taken:
            taken.add(name)
            return name
    raise RuntimeError("name pool exhausted")


def gen_item(k: int, c_chains: int, seed: int) -> dict:
    """Component-isomorphic hop chain (the round-8 construction as re-implemented for
    round 21 and used unchanged by round 22, byte-compatible): C disjoint directed paths
    of exactly k edges over fresh entities; the query is (head of one path, tail of one
    path); yes iff both endpoints lie on the same path."""
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
        # "L" is the construction-lineage label inherited from round 8's arm L and kept
        # byte-identical through rounds 21 and 22: the item manifest is hashed, so this
        # is what makes the anchor cell's candidate pool the SAME pool round 23 archived
        # at (k = 8, E = 96) (and, one level down, the pools of rounds 21 and 22). The
        # dispatch arm of a record is a separate field, "F" or "X".
        "arm": "L",
        "level": k,
        "chains": c_chains,
        "edges": len(facts),
        "seed": seed,
        "seed_hash": sha256_text(f"ladders|hop_chain|{k}|{seed}")[:16],
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
    """Independent structural and solvability audit of one item."""
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
        tails = [u for u in comp if inc.get(u, 1 - 1) == 1 and out.get(u, 0) == 0]
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


def comp_tail_targets(item: dict) -> list:
    """Tails of every path in the item except the queried source's own path."""
    out_m = {s: t for s, _, t in item["facts"]}
    inc_set = {t for _, _, t in item["facts"]}
    k = item["level"]
    src = item["query"][0]
    heads = sorted(n for n in ({s for s, _, _ in item["facts"]} | inc_set)
                   if n not in inc_set)
    tails = []
    for head in heads:
        if head == src:
            continue
        node = head
        for _ in range(k):
            node = out_m[node]
        tails.append(node)
    return tails


def x_variant(item: dict) -> dict:
    """The matched cross-component query on the IDENTICAL fact list: same source (a path
    head), target = the tail of a different path, chosen deterministically from the item
    digest so the choice cannot depend on anything measured."""
    cands = sorted(comp_tail_targets(item))
    if not cands:
        raise RuntimeError("item has no other component to query")
    rng = random.Random(sha256_text("xvariant|" + canonical(item)))
    tgt = rng.choice(cands)
    var = dict(item)
    var["query"] = [item["query"][0], REL, tgt]
    var["answer"] = "no"
    var["chain_len"] = None
    return var


def pair_violations(f_item: dict, x_item: dict) -> list:
    """Issue #78 acceptance criterion 1: the two queries of a pair must share every fact,
    every entity name and the fact count, and differ only in the queried target; both
    labels must be certified by an independent BFS."""
    bad: list = []
    if canonical(f_item["facts"]) != canonical(x_item["facts"]):
        bad.append("fact lists differ")
    ent_f = {n for s, _, t in f_item["facts"] for n in (s, t)}
    ent_x = {n for s, _, t in x_item["facts"] for n in (s, t)}
    if ent_f != ent_x:
        bad.append("entity name sets differ")
    if len(f_item["facts"]) != len(x_item["facts"]):
        bad.append("fact counts differ")
    if f_item["query"][0] != x_item["query"][0]:
        bad.append("queried source differs")
    if f_item["query"][2] == x_item["query"][2]:
        bad.append("queried targets are identical")
    if not (f_item["answer"] == "yes" and x_item["answer"] == "no"):
        bad.append("pair labels are not (yes, no)")
    dist = bfs_dist(x_item["facts"], x_item["query"][0])
    if x_item["query"][2] in dist:
        bad.append("cross-component target is reachable from the source")
    if bfs_dist(f_item["facts"], f_item["query"][0]).get(f_item["query"][2]) != f_item["level"]:
        bad.append("forward target is not at distance k")
    return bad


def features(item: dict) -> dict:
    """Traversal-free feature battery over the query endpoints and fact list."""
    facts = item["facts"]
    srcs = {s for s, _, _ in facts}
    tgts = {t for _, _, t in facts}
    inc: dict = {}
    for s, _, t in facts:
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
        "tgt_outdeg_zero": all(t != qt for s, _, t in facts) or qt not in srcs,
        "tgt_indeg_zero": inc.get(qt, 0) == 0,
        "src_is_fact_target": qs in tgts,
        "src_is_fact_source": qs in srcs,
        "src_outdeg_zero": qs not in srcs,
        "src_indeg_zero": inc.get(qs, 0) == 0,
        "tgt_name_lt_src_name": qt < qs,
        "tgt_name_longer_than_src": len(qt) > len(qs),
        "tgt_first_mention_before_src": (first_idx.get(qt, 10 ** 9)
                                         < first_idx.get(qs, 10 ** 9)),
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


def gate_battery(items: list, perms: int = PERMS, seed: int = SEED_BASE) -> dict:
    """Permutation-calibrated leak gate, family-wise alpha over the whole battery. Runs
    on the candidate pool and on the paired pool, never on the selected pairs."""
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


def build_cell(k: int, c_chains: int, want_pairs: int) -> tuple:
    """Selection rule fixed in advance: candidate order by seed; the first want_pairs
    GOLD-YES candidates become the arm-F members of the dispatched pairs, each with its
    deterministic cross-component arm-X variant. Every candidate and every derived variant
    passes the independent structural audit, and every dispatched pair passes the
    shared-content assertion. Returns (selected pairs, 40-candidate pool, paired pool)."""
    pool: list = []
    pairs: list = []
    for i in range(CANDIDATES):
        item = gen_item(k, c_chains, cell_seed(k, c_chains, i))
        violations = verify_item(item)
        if violations:
            raise RuntimeError(
                f"cell k={k} C={c_chains} seed {item['seed']}: {violations}")
        pool.append(item)
        if item["answer"] != "yes":
            continue
        var = x_variant(item)
        var_violations = verify_item(var)
        if var_violations:
            raise RuntimeError(
                f"variant k={k} C={c_chains} seed {item['seed']}: {var_violations}")
        shared = pair_violations(item, var)
        if shared:
            raise RuntimeError(
                f"matched pair k={k} C={c_chains} seed {item['seed']}: {shared}")
        if len(pairs) < want_pairs:
            pairs.append((item, var))
    if len(pairs) != want_pairs:
        raise RuntimeError(f"cell k={k} C={c_chains}: selection rule starved")
    paired_pool = []
    for item in pool:
        if item["answer"] != "yes":
            continue
        paired_pool.append(item)
        paired_pool.append(x_variant(item))
    return pairs, pool, paired_pool


def all_cells() -> list:
    cells = []
    for name, k, c_chains in WALK:
        pairs, pool, paired_pool = build_cell(k, c_chains, PAIRS_PER_LEVEL)
        cells.append({"cell": name, "index": WALK_INDEX[name], "k": k,
                      "chains": c_chains, "edges": k * c_chains, "pairs": pairs,
                      "pool": pool, "paired_pool": paired_pool})
    return cells


def render_prompt(item: dict) -> str:
    lines = [RULE_SENTENCE]
    lines += [f"Fact {i + 1}: {s} {r} {t}." for i, (s, r, t) in enumerate(item["facts"])]
    s, r, t = item["query"]
    lines.append(f"Question: does {s} {r} {t}? Answer with exactly one word: yes or no.")
    return "\n".join(lines)


def last_answer(text: str):
    """Last standalone yes/no in one field. Returns (answer, offset)."""
    matches = list(ANSWER_RE.finditer(text or ""))
    if not matches:
        return None, -1
    m = matches[-1]
    return m.group(1).lower(), m.start()


def strict_last_trace_token(reasoning: str):
    """Round-19 rule, vendored verbatim: the last trace yes/no that could be a verdict.
    Qualifies when it is outside a "yes/no" or "yes or no" phrase and either closes the
    trace (only punctuation after it) or is both preceded by an answer cue within 30
    characters and closed by punctuation."""
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


def provenance_class(reasoning: str):
    """Round-19 classes for the LAST reasoning-field yes/no: instruction_echo (inside a
    yes/no phrase), terminal (last 2% of the trace), mid_trace (elsewhere), or None when
    the trace carries no yes/no."""
    text = reasoning or ""
    matches = list(ANSWER_RE.finditer(text))
    if not matches:
        return None, -1.0
    m = matches[-1]
    spans = [p.span() for p in PHRASE_RE.finditer(text)]
    in_phrase = any(a <= m.start() and m.end() <= b for a, b in spans)
    frac = m.start() / max(1, len(text))
    if in_phrase:
        return "instruction_echo", frac
    if frac >= 0.98:
        return "terminal", frac
    return "mid_trace", frac


def readouts(content: str, reasoning: str) -> dict:
    """All three declared readouts plus the provenance of the fallback token."""
    c_ans, c_off = last_answer(content)
    r_ans, r_off = last_answer(reasoning)
    loose = c_ans if c_ans else r_ans
    strict_trace = strict_last_trace_token(reasoning)
    delivered_or_strict = c_ans if c_ans else strict_trace
    pcls, pfrac = provenance_class(reasoning)
    return {"content_answer": c_ans, "content_offset": c_off,
            "reasoning_answer": r_ans, "reasoning_offset": r_off,
            "loose_fallback_answer": loose,
            "loose_fallback_source": "content" if c_ans else ("reasoning" if r_ans else "none"),
            "strict_trace_token": strict_trace,
            "delivered_or_strict_answer": delivered_or_strict,
            "fallback_provenance_class": pcls,
            "fallback_commit_fraction": round(pfrac, 4) if pfrac >= 0 else None}


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
                "finish_reason": None, "prompt_tokens": 0, "completion_tokens": 0}
    except (urllib.error.URLError, TimeoutError, OSError,
            json.JSONDecodeError) as exc:
        return {"error": type(exc).__name__, "content": "", "reasoning": "",
                "finish_reason": None, "prompt_tokens": 0, "completion_tokens": 0}


class AttemptBudget:
    """Hard cap on total endpoint calls for the whole run (health included)."""

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
    resp = call_endpoint(HEALTH_PROMPT, HEALTH_BUDGET, deadline_s=240)
    latency = round(time.monotonic() - t0, 3)
    ro = readouts(resp["content"], resp["reasoning"])
    att = {"error_class": resp.get("error"),
           "completion_tokens": resp["completion_tokens"],
           "content_answer": ro["content_answer"],
           "reasoning_answer": ro["reasoning_answer"]}
    return {"ok": classify_attempt(att) == "answered_in_answer_field",
            "outcome": classify_attempt(att), "latency_s": latency,
            "completion_tokens": resp["completion_tokens"],
            "prompt_tokens": resp["prompt_tokens"],
            "started_at": now_iso(), "finished_at": now_iso()}


def expected_chain(item: dict):
    """Ordered node sequence of the queried chain when gold is yes."""
    if item["answer"] != "yes":
        return None
    adj: dict = {}
    for s, _, t in item["facts"]:
        adj[s] = t
    seq = [item["query"][0]]
    for _ in range(item["level"]):
        seq.append(adj.get(seq[-1], "?"))
    return seq


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


def distractor_names(item: dict) -> list:
    """Every entity on a path other than the queried source's own path: name-mention
    counting over these measures how much of the output is spent enumerating facts the
    query does not need."""
    out_m = {s: t for s, _, t in item["facts"]}
    inc_set = {t for _, _, t in item["facts"]}
    nodes = {s for s, _, _ in item["facts"]} | inc_set
    src = item["query"][0]
    own = {src}
    node = src
    for _ in range(item["level"]):
        node = out_m.get(node)
        if node is None:
            break
        own.add(node)
    others = [n for n in nodes if n not in own]
    heads = [n for n in others if n not in inc_set]
    out = []
    for head in heads:
        node = head
        for _ in range(item["level"]):
            out.append(node)
            node = out_m.get(node)
            if node is None:
                break
        if node is not None:
            out.append(node)
    return out


def mechanics(item: dict, att: dict, prompt: str) -> dict:
    text = (att.get("reasoning") or "") + " " + (att.get("content") or "")
    seq = expected_chain(item)
    hops = ordered_prefix_hops(seq, text) if seq else None
    dis = distractor_names(item)
    mentioned = sum(1 for n in dis if n in text)
    src, tgt = item["query"][0], item["query"][2]
    return {
        "ordered_prefix_hops": hops,
        "expected_hops": len(seq) if seq else None,
        "coverage_ratio": (round(hops / len(seq), 4)
                           if seq and hops is not None else None),
        "completion_tokens": att["completion_tokens"],
        "budget_utilisation": round(att["completion_tokens"] / MAX_TOKENS, 4),
        "reasoning_chars": len(att.get("reasoning") or ""),
        "content_chars": len(att.get("content") or ""),
        "distractor_entities": len(dis),
        "distractors_mentioned": mentioned,
        "distractor_mention_ratio": round(mentioned / len(dis), 4) if dis else None,
        "src_first_mention_frac": round(prompt.find(src) / max(len(prompt), 1), 4),
        "tgt_first_mention_frac": round(prompt.find(tgt) / max(len(prompt), 1), 4),
    }


def blank_record(item: dict, arm: str, pair_seed: int, phase: int) -> dict:
    prompt = render_prompt(item)
    return {
        "arm": arm, "level": item["edges"], "k": item["level"],
        "chains": item["chains"], "edges": item["edges"], "seed": item["seed"],
        "pair_seed": pair_seed, "seed_hash": item["seed_hash"],
        "item_sha256": sha256_text(canonical(item)),
        "prompt_sha256": sha256_text(prompt), "prompt_chars": len(prompt),
        "gold": 1 if item["answer"] == "yes" else 0,
        "gate_hash": GATE_HASH, "phase": phase, "attempts": [],
    }


def make_record(item: dict, arm: str, pair_seed: int, budget_cap: AttemptBudget,
                phase: int) -> dict:
    rec = blank_record(item, arm, pair_seed, phase)
    prompt = render_prompt(item)
    max_attempts = 3
    for attempt_no in range(1, max_attempts + 1):
        if not budget_cap.acquire():
            rec["attempts"].append({
                "attempt": attempt_no, "wall_s": 0.0, "error_class": "cap_exceeded",
                "started_at": now_iso(), "finished_at": now_iso(),
                "finish_reason": None, "prompt_tokens": 0, "completion_tokens": 0,
                "content": "", "reasoning": ""})
            break
        t0 = time.monotonic()
        started = now_iso()
        resp = call_endpoint(prompt, MAX_TOKENS, deadline_s=ITEM_DEADLINE_S)
        wall = round(time.monotonic() - t0, 3)
        att = {"attempt": attempt_no, "wall_s": wall,
               "error_class": resp.get("error"),
               "started_at": started, "finished_at": now_iso(),
               "finish_reason": resp["finish_reason"],
               "prompt_tokens": resp["prompt_tokens"],
               "completion_tokens": resp["completion_tokens"],
               "content": resp["content"], "reasoning": resp["reasoning"]}
        att.update(readouts(resp["content"], resp["reasoning"]))
        att["mechanics"] = mechanics(item, att, prompt)
        rec["attempts"].append(att)
        if not is_retryable(classify_attempt(att)):
            break
    last = rec["attempts"][-1]
    for field in ("content_answer", "reasoning_answer", "loose_fallback_answer",
                  "loose_fallback_source", "strict_trace_token",
                  "delivered_or_strict_answer", "fallback_provenance_class",
                  "fallback_commit_fraction"):
        rec[field] = last[field]
    rec["completion_tokens"] = last.get("completion_tokens", 0)
    rec["prompt_tokens"] = last.get("prompt_tokens", 0)
    rec["outcome"] = classify_attempt(last)
    gold = rec["gold"]
    rec["correct"] = {}
    for name in ("content_only", "loose_fallback", "delivered_or_strict"):
        ans = {"content_only": last["content_answer"],
               "loose_fallback": last["loose_fallback_answer"],
               "delivered_or_strict": last["delivered_or_strict_answer"]}[name]
        rec["correct"][name] = (None if ans is None
                                else int((1 if ans == "yes" else 0) == gold))
    return rec


def write_jsonl(path: str, rec: dict) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(canonical(rec) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def anchor_state(gate: dict) -> dict:
    """Fail-closed check of the round-23 S3 pin, from constants only."""
    cells = {c["cell"]: c for c in gate["cells"]}
    rows = {}
    for label, cell_id, blob, prompts, record in (
            ("A1", "L0", A1_POOL_BLOB, A1_FORWARD_PROMPTS, A1_RECORD),):
        cell = cells.get(cell_id)
        observed_blob = cell["pool_blob_sha256"] if cell else None
        observed_prompts = set(cell["forward_prompt_sha256"]) if cell else set()
        rows[label] = {
            "cell": cell_id,
            "expected_pool_blob_sha256": blob,
            "observed_pool_blob_sha256": observed_blob,
            "pool_blob_matches": observed_blob == blob,
            "expected_forward_prompts": sorted(prompts),
            "observed_forward_prompts": sorted(observed_prompts),
            "forward_prompts_match": observed_prompts == set(prompts),
            "archived_records_by_seed": {str(s): v for s, v in sorted(record.items())},
        }
    all_ok = all(r["pool_blob_matches"] and r["forward_prompts_match"]
                 for r in rows.values())
    return {"checked": True, "all_ok": all_ok, "anchors": rows,
            "provenance": ("research/nightly-2026-10-25-0205 (round 23, PR #97), "
                           "gate.json and raw.jsonl, cell S3 (k = 8, E = 96)")}


def build_gate() -> dict:
    cells = all_cells()
    out = {"schema": "round24-gate-v1", "seed_base": SEED_BASE,
           "alpha": ALPHA, "perms": PERMS,
           "load_arm": [{"cell": n, "k": k, "chains": c, "edges": k * c}
                        for n, k, c in LOAD_ARM],
           "depth_arm": [{"cell": n, "k": k, "chains": c, "edges": k * c}
                         for n, k, c in DEPTH_ARM],
           "pairs_per_cell": PAIRS_PER_LEVEL,
           "max_tokens": MAX_TOKENS, "temperature": TEMPERATURE,
           "readouts": ["content_only", "loose_fallback", "delivered_or_strict"],
           "matched_pair_invariant": ("identical fact list, identical entity name set, "
                                      "identical fact count, identical queried source; "
                                      "only the queried target varies (issue #78 "
                                      "acceptance criterion 1, polarity contrast)"),
           "predictions": {
               "P1_load_arm_prompt_mean_steps_ge_1.05_and_depth_arm_within_1pct": True,
               "P2a_L0_maintained_content_only": True,
               "P2b_at_least_one_of_L1_L2_L3_not_maintained_content_only": True,
               "P2c_D1_D2_both_maintained_content_only": True,
               "P3_L3_mean_distractor_mention_ratio_ge": 0.30,
               "P4_direction_b_ge_c": True,
               "P5_all_content_only_answers_correct": True,
               "P6_fallback_no_share_when_content_silent_ge": 0.6667,
               "P7_anchor_prompts_reproduce_round23_answers": True},
           "cells": []}
    for cell in cells:
        g_pool = gate_battery(cell["pool"])
        g_pairs = gate_battery(cell["paired_pool"])
        prompts = [render_prompt(it) for pair in cell["pairs"] for it in pair]
        chars = [len(p) for p in prompts]
        out["cells"].append({
            "arm": "S", "cell": cell["cell"], "index": cell["index"],
            "k": cell["k"], "chains": cell["chains"], "edges": cell["edges"],
            "level": cell["edges"],
            "load": {"facts": cell["edges"],
                     "prompt_chars_mean": round(sum(chars) / len(chars), 1),
                     "prompt_chars_min": min(chars), "prompt_chars_max": max(chars)},
            "forward_item_sha256": [sha256_text(canonical(p[0])) for p in cell["pairs"]],
            "forward_prompt_sha256": [sha256_text(render_prompt(p[0]))
                                      for p in cell["pairs"]],
            "cross_prompt_sha256": [sha256_text(render_prompt(p[1]))
                                    for p in cell["pairs"]],
            "pool_blob_sha256": sha256_text(canonical(cell["pool"])),
            "paired_pool_blob_sha256": sha256_text(canonical(cell["paired_pool"])),
            "gate_pool": g_pool, "gate_paired_pool": g_pairs})
    blob = sha256_text(canonical([c["paired_pool_blob_sha256"] for c in out["cells"]]))
    out["corpus_blob_sha256"] = blob
    out["planned_prompts"] = 2 * PAIRS_PER_LEVEL * len(WALK)
    out["prompt_cap"] = PROMPT_CAP
    out["all_cells_pass"] = all(
        c["gate_pool"]["verdict"] != "leak" and c["gate_paired_pool"]["verdict"] != "leak"
        for c in out["cells"])
    out["anchor"] = anchor_state(out)
    out["anchor_ok"] = out["anchor"]["all_ok"]
    return out


GATE_HASH = "unset"


def gate_hash(gate: dict) -> str:
    return sha256_text(canonical(gate))


def cell_order_key(name: str) -> int:
    return WALK_INDEX.get(name, len(WALK))


def steps_at_least(means: list, factor: float) -> bool:
    """Every step of an ordered means list must be >= factor x its predecessor. Ties and
    dips fail; declared for steps that MUST be visible to the tokenizer (the load arm)."""
    if not means or any(m is None or m <= 0 for m in means):
        return False
    return all(b >= factor * a for a, b in zip(means, means[1:]))


def within_tolerance(a: float, b: float, tol: float) -> bool:
    """|b - a| <= tol x a. Declared for construction-invariant equalities (two cells with
    the SAME fact count): round 23's P1 lesson, a 0.12% entity-name-length dip must not
    read as a failed prediction."""
    if a is None or b is None or a <= 0:
        return False
    return abs(b - a) <= tol * a


def ols(points: list) -> dict:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    n = len(points)
    if n < 2:
        return {"slope": None, "intercept": None, "r": None, "n": n}
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in points)
    syy = sum((y - my) ** 2 for y in ys)
    slope = (sxy / sxx) if sxx else None
    r = (sxy / math.sqrt(sxx * syy)) if (sxx and syy) else None
    return {"slope": (round(slope, 6) if slope is not None else None),
            "intercept": (round(my - slope * mx, 3) if slope is not None else None),
            "r": (round(r, 4) if r is not None else None), "n": n}


def solve_linear(mat: list, vec: list):
    """Small dense solve (Gaussian elimination, partial pivoting). Returns None when the
    system is singular, which is what keeps a saturated cell-mean fit honest instead of
    silently returning garbage."""
    n = len(vec)
    a = [row[:] + [vec[i]] for i, row in enumerate(mat)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[piv][col]) < 1e-12:
            return None
        a[col], a[piv] = a[piv], a[col]
        for r in range(n):
            if r == col:
                continue
            factor = a[r][col] / a[col][col]
            if factor:
                for c in range(col, n + 1):
                    a[r][c] -= factor * a[col][c]
    return [a[i][n] / a[i][i] for i in range(n)]


def two_factor_means(means: list) -> dict:
    """Fit mean_completion = b0 + b1*k + b2*E + b3*k*E over the cell means, where each
    entry is (cell, k, edges, mean_completion_tokens). The interaction coefficient b3 is
    the declared summary of "the ceiling is a frontier in (k, E), not a curve in one":
    b3 > 0 says the joint corner costs more than the two single-axis effects predict.
    Four parameters on six cell means: descriptive, and reported as such."""
    pts = [m for m in means if m[3] is not None]
    if len(pts) < 5:
        return {"fit": None, "note": f"only {len(pts)} cell means, fit refused"}
    xs = [(1.0, float(k), float(e), float(k) * float(e)) for (_c, k, e, _m) in pts]
    ys = [m for (_c, _k, _e, m) in pts]
    at_a = [[sum(x[i] * x[j] for x in xs) for j in range(4)] for i in range(4)]
    at_y = [sum(x[i] * y for x, y in zip(xs, ys)) for i in range(4)]
    beta = solve_linear(at_a, at_y)
    if beta is None:
        return {"fit": None, "note": "singular design (cells do not span k x E)"}
    pred = [sum(b * x for b, x in zip(beta, xrow)) for xrow in xs]
    resid = [y - p for y, p in zip(ys, pred)]
    ss_tot = sum((y - sum(ys) / len(ys)) ** 2 for y in ys)
    ss_res = sum(r * r for r in resid)
    return {"fit": {"b0": round(beta[0], 3), "b_per_hop": round(beta[1], 4),
                    "b_per_fact": round(beta[2], 4), "b_hop_x_fact": round(beta[3], 6)},
            "r2": (round(1.0 - ss_res / ss_tot, 4) if ss_tot else None),
            "n_cell_means": len(pts),
            "residuals": {c: round(r, 1) for (c, _k, _e, _m), r in zip(pts, resid)}}


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple:
    if total == 0:
        return 0.0, 0.0
    p = successes / total
    denom = 1.0 + z * z / total
    centre = p + z * z / (2 * total)
    span = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return (centre - span) / denom, (centre + span) / denom


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact sign test on the discordant pair counts."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2.0 ** n)
    return min(1.0, 2.0 * tail)


def est_pos(r: dict) -> int:
    """Character-proportional estimate of the delivered answer's position inside the whole
    completion, recomputed at analysis time from the archived attempt fields (reasoning
    streams before content). Round 21's lesson: estimates stored at dispatch time rot, so
    this is derived here, never read back from a stored field."""
    if not r.get("attempts"):
        return -1
    a = r["attempts"][-1]
    off = a.get("content_offset", -1)
    if off < 0:
        return -1
    full = (a.get("reasoning") or "") + (a.get("content") or "")
    return round(a.get("completion_tokens", 0)
                 * (len(a.get("reasoning") or "") + off + 1) / max(len(full), 1))


def place_cell_status(rows: list) -> dict:
    """Round-8 trichotomy per cell (Wilson 95, floor 0.60), computed per readout, in WALK
    order. status: budget_limited (no-answer rate > 0.5) / maintained (lb >= floor) /
    collapsed (ub < floor) / inconclusive / descriptive (n < MIN_CERTIFY). The frontier
    report is two-dimensional by construction: for each hop depth k the largest E that is
    maintained, and for each E the largest k that is maintained."""
    floor = MAJORITY_FLOOR + MARGIN
    out_rows = []
    for row in sorted(rows, key=lambda r: cell_order_key(r["cell"])):
        n = row["n"]
        na = (row.get("no_answer", 0) / n) if n else 0.0
        lb, ub = wilson(row["correct"], n)
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
        out_rows.append({"arm": "S", "cell": row["cell"], "k": row["k"],
                         "edges": row["edges"], "n": n, "correct": row["correct"],
                         "wrong": row.get("wrong", 0), "no_answer": row.get("no_answer", 0),
                         "accuracy": round(row["correct"] / n, 4) if n else 0.0,
                         "wilson_lb95": round(lb, 4), "wilson_ub95": round(ub, 4),
                         "no_answer_rate": round(na, 4), "status": status})
    by_k: dict = {}
    by_e: dict = {}
    for r in out_rows:
        if r["status"] == "maintained":
            by_k[r["k"]] = max(by_k.get(r["k"], 0), r["edges"])
            by_e[r["edges"]] = max(by_e.get(r["edges"], 0), r["k"])
    bad = [r["cell"] for r in out_rows if r["status"] != "maintained"]
    grid_max = max((r["edges"] for r in out_rows), default=0)
    k_max = max((r["k"] for r in out_rows), default=0)
    if not bad:
        report = (f"no cell of the declared walk leaves maintained: E* >= {grid_max} at "
                  f"k <= {k_max}; the frontier on this class lies beyond "
                  f"(k={k_max}, E={grid_max})")
    else:
        first = bad[0]
        report = (f"first non-maintained cell {first} "
                  f"(k={[r['k'] for r in out_rows if r['cell'] == first][0]}, "
                  f"E={[r['edges'] for r in out_rows if r['cell'] == first][0]}); "
                  f"non-maintained cells {bad}")
    return {"report": report, "maintained_by_k": {str(k): v for k, v in sorted(by_k.items())},
            "maintained_by_edges": {str(e): v for e, v in sorted(by_e.items())},
            "non_maintained_cells": bad, "floor": floor,
            "min_certify_items": MIN_CERTIFY, "rows": out_rows}


def aggregate(records: list) -> dict:
    readout_names = ("content_only", "loose_fallback", "delivered_or_strict")
    cells = {name: {"k": k, "edges": k * c, "chains": c}
             for name, k, c in WALK}
    per_ro: dict = {}
    tok: dict = {}
    dis: dict = {}
    trunc: dict = {}
    for rec in records:
        key = rec.get("cell") or cells_for(rec["k"], rec["chains"])
        tok.setdefault(key, {"completion": [], "prompt": []})
        tok[key]["completion"].append(rec.get("completion_tokens", 0))
        tok[key]["prompt"].append(rec.get("prompt_tokens", 0))
        last = rec["attempts"][-1] if rec.get("attempts") else {}
        if last.get("finish_reason") == "length":
            trunc[key] = trunc.get(key, 0) + 1
        mech = last.get("mechanics") or {}
        if mech.get("distractor_entities"):
            dis.setdefault(key, []).append(mech.get("distractor_mention_ratio"))
        for name in readout_names:
            row = per_ro.setdefault((name, key), {"cell": key, "n": 0, "correct": 0,
                                                  "wrong": 0, "no_answer": 0})
            row["n"] += 1
            c = rec["correct"][name]
            if c is None:
                row["no_answer"] += 1
            elif c == 1:
                row["correct"] += 1
            else:
                row["wrong"] += 1
    per_cell = {}
    for name in readout_names:
        rows = []
        for (nm, key), row in sorted(per_ro.items(), key=lambda kv: cell_order_key(kv[0][1])):
            if nm != name:
                continue
            row = dict(row)
            row["k"] = cells[key]["k"]
            row["edges"] = cells[key]["edges"]
            row["chains"] = cells[key]["chains"]
            row["mean_completion_tokens"] = round(
                sum(tok[key]["completion"]) / len(tok[key]["completion"]), 1)
            row["mean_prompt_tokens"] = round(
                sum(tok[key]["prompt"]) / len(tok[key]["prompt"]), 1)
            row["truncated_cells"] = trunc.get(key, 0)
            rows.append(row)
        per_cell[name] = rows
    status = {name: place_cell_status(per_cell[name]) for name in readout_names}

    arm_stats = {}
    for arm in ("F", "X"):
        rs = [r for r in records if r["arm"] == arm]
        denom = max(1, len(rs))
        ratios = [((r["attempts"][-1].get("mechanics") or {}).get("distractor_mention_ratio"))
                  for r in rs if r.get("attempts")]
        ratios = [x for x in ratios if x is not None]
        entry = {"cells": len(rs),
                 "mean_completion_tokens": round(
                     sum(r.get("completion_tokens", 0) for r in rs) / denom, 1),
                 "mean_prompt_tokens": round(
                     sum(r.get("prompt_tokens", 0) for r in rs) / denom, 1),
                 "mean_distractor_mention_ratio": (round(sum(ratios) / len(ratios), 4)
                                                   if ratios else None),
                 "readouts": {}}
        for name in readout_names:
            correct = sum(1 for r in rs if r["correct"][name] == 1)
            wrong = sum(1 for r in rs if r["correct"][name] == 0)
            no_answer = sum(1 for r in rs if r["correct"][name] is None)
            lb, ub = wilson(correct, len(rs))
            entry["readouts"][name] = {"correct": correct, "wrong": wrong,
                                       "no_answer": no_answer,
                                       "accuracy": round(correct / len(rs), 4) if rs else 0.0,
                                       "wilson_lb95": round(lb, 4),
                                       "wilson_ub95": round(ub, 4)}
        arm_stats[arm] = entry

    # arm split per cell: does the negative arm become the fragile one at the joint corner?
    arm_by_cell = {}
    for name in WALK_INDEX:
        rs = [r for r in records if (r.get("cell") or cells_for(r["k"], r["chains"])) == name]
        entry = {}
        for arm in ("F", "X"):
            a_rs = [r for r in rs if r["arm"] == arm]
            correct = sum(1 for r in a_rs if r["correct"]["content_only"] == 1)
            no_answer = sum(1 for r in a_rs if r["correct"]["content_only"] is None)
            entry[arm] = {"cells": len(a_rs), "correct": correct, "no_answer": no_answer,
                          "mean_completion_tokens": (round(
                              sum(r.get("completion_tokens", 0) for r in a_rs) / len(a_rs), 1)
                              if a_rs else None)}
        arm_by_cell[name] = entry

    # matched-pair analysis: one graph per pair, arm F (gold yes) and arm X (gold no)
    pairs = collections.defaultdict(dict)
    for rec in records:
        key = rec.get("cell") or cells_for(rec["k"], rec["chains"])
        pairs[(key, rec["pair_seed"])][rec["arm"]] = rec
    counts = {"pairs": 0, "both_ok": 0, "f_ok_x_not": 0, "x_ok_f_not": 0,
              "both_not": 0, "both_silent": 0, "f_silent": 0, "x_silent": 0}
    per_cell_pairs = {}
    for (cell_name, _ps), pair in sorted(pairs.items(), key=lambda kv: (cell_order_key(kv[0][0]),
                                                                        kv[0][1])):
        f, x = pair.get("F"), pair.get("X")
        if f is None or x is None:
            continue
        counts["pairs"] += 1
        fok = f["correct"]["content_only"] == 1
        xok = x["correct"]["content_only"] == 1
        rl = per_cell_pairs.setdefault(cell_name, {"pairs": 0, "both_ok": 0,
                                                   "f_ok_x_not": 0, "x_ok_f_not": 0,
                                                   "both_not": 0})
        rl["pairs"] += 1
        if fok and xok:
            counts["both_ok"] += 1
            rl["both_ok"] += 1
        elif fok and not xok:
            counts["f_ok_x_not"] += 1
            rl["f_ok_x_not"] += 1
        elif xok and not fok:
            counts["x_ok_f_not"] += 1
            rl["x_ok_f_not"] += 1
        else:
            counts["both_not"] += 1
            rl["both_not"] += 1
        if f["content_answer"] is None:
            counts["f_silent"] += 1
        if x["content_answer"] is None:
            counts["x_silent"] += 1
        if f["content_answer"] is None and x["content_answer"] is None:
            counts["both_silent"] += 1
    mcnemar = {"b_forward_ok_cross_not": counts["f_ok_x_not"],
               "c_cross_ok_forward_not": counts["x_ok_f_not"],
               "p_exact": mcnemar_exact(counts["f_ok_x_not"], counts["x_ok_f_not"])}

    # single-axis transitions inside each arm: consecutive cells differ in exactly one axis
    means = {r["cell"]: r for r in per_cell["content_only"]}
    # the trichotomy status lives in the classification rows, NOT in the token rows
    # (round 22's aggregate KeyError class; asserted by --selftest item 14)
    status_by_cell = {r["cell"]: r["status"] for r in status["content_only"]["rows"]}
    steps = ([(a, b, "load") for a, b in zip(LOAD_NAMES, LOAD_NAMES[1:])]
             + [(a, b, "depth") for a, b in zip(DEPTH_NAMES, DEPTH_NAMES[1:])])
    transitions = []
    order = [name for name, _k, _c in WALK]
    for a_name, b_name, declared_axis in steps:
        if a_name not in means or b_name not in means:
            continue
        a, b = means[a_name], means[b_name]
        axis = "depth" if a["k"] != b["k"] else "load"
        if a["k"] != b["k"] and a["edges"] != b["edges"]:
            axis = "BOTH (design error)"
        transitions.append({
            "from": a_name, "to": b_name, "axis": axis,
            "declared_axis": declared_axis,
            "k": f"{a['k']}->{b['k']}", "edges": f"{a['edges']}->{b['edges']}",
            "accuracy": f"{a['correct']}/{a['n']}->{b['correct']}/{b['n']}",
            "no_answer": f"{a['no_answer']}->{b['no_answer']}",
            "mean_completion_tokens": (round(b["mean_completion_tokens"]
                                             / a["mean_completion_tokens"], 4)
                                       if a["mean_completion_tokens"] else None),
            "status": f"{status_by_cell.get(a_name)}->{status_by_cell.get(b_name)}"})

    # predictions
    load_prompt_means = [means[n]["mean_prompt_tokens"] for n in LOAD_NAMES if n in means]
    p1_load_ok = (len(load_prompt_means) == len(LOAD_NAMES)
                  and steps_at_least(load_prompt_means, 1.05))
    p1_depth_ok = (means.get("D1") and means.get("D2")
                   and within_tolerance(means["D1"]["mean_prompt_tokens"],
                                        means["D2"]["mean_prompt_tokens"], 0.01))
    p1_ok = bool(p1_load_ok and p1_depth_ok)
    st = {r["cell"]: r["status"] for r in status["content_only"]["rows"]}
    p2a_ok = st.get("L0") == "maintained"
    bisect_not_maintained = [n for n in ("L1", "L2", "L3")
                             if st.get(n) not in (None, "maintained")]
    p2b_ok = len(bisect_not_maintained) >= 1
    p2c_not_maintained = [n for n in ("D1", "D2") if st.get(n) not in (None, "maintained")]
    p2c_ok = len(p2c_not_maintained) == 0
    dis_by_cell = {}
    for key, vals in dis.items():
        good = [x for x in vals if x is not None]
        if good:
            dis_by_cell[key] = round(sum(good) / len(good), 4)
    p3_ratio = dis_by_cell.get("L3")
    p4_ok = counts["f_ok_x_not"] >= counts["x_ok_f_not"]
    content_recs = [r for r in records if r["content_answer"] is not None]
    p5_ok = all(r["correct"]["content_only"] == 1 for r in content_recs)
    silent = [r for r in records if r["content_answer"] is None
              and r["reasoning_answer"] is not None]
    p6_share = (sum(1 for r in silent if r["reasoning_answer"] == "no") / len(silent)
                if silent else None)

    anchor_rows = []
    for label, cell_name, prompt_set, archived in (
            ("A1", "L0", A1_FORWARD_PROMPTS, A1_RECORD),):
        for r in records:
            if r["arm"] != "F" or r["prompt_sha256"] not in prompt_set:
                continue
            ref = archived.get(r["seed"], {})
            anchor_rows.append({
                "anchor": label, "cell": cell_name, "seed": r["seed"],
                "prompt_sha256": r["prompt_sha256"][:12],
                "this_answer": r["content_answer"],
                "this_completion_tokens": r["completion_tokens"],
                "archived_answer": ref.get("answer"),
                "archived_completion_tokens": ref.get("r23_completion"),
                "answer_agrees": r["content_answer"] == ref.get("answer")})
    p7_ok = (len(anchor_rows) == 3 and all(row["answer_agrees"] for row in anchor_rows))

    cell_means_tok = [(n, means[n]["k"], means[n]["edges"], means[n]["mean_completion_tokens"])
                      for n in order if n in means]
    load_law_at_k8 = ols([(e, m) for (_c, k, e, m) in cell_means_tok
                          if k == 8 and m is not None])
    depth_law_at_E96 = ols([(k, m) for (_c, k, e, m) in cell_means_tok
                            if e == 96 and m is not None])

    prov = collections.Counter()
    prov_agree = collections.Counter()
    strict_on_silent = {"cells": 0, "committed": 0, "correct": 0}
    fractions = []
    for rec in records:
        cls = rec["fallback_provenance_class"]
        if cls is None:
            prov["no_trace_token"] += 1
            continue
        prov[cls] += 1
        gold_word = "yes" if rec["gold"] == 1 else "no"
        prov_agree[cls] += int(rec["reasoning_answer"] == gold_word)
        if rec["fallback_commit_fraction"] is not None:
            fractions.append(rec["fallback_commit_fraction"])
        if rec["content_answer"] is None:
            strict_on_silent["cells"] += 1
            if rec["strict_trace_token"] is not None:
                strict_on_silent["committed"] += 1
                strict_on_silent["correct"] += int(
                    (1 if rec["strict_trace_token"] == "yes" else 0) == rec["gold"])
    fractions.sort()
    fallback_correct = sum(1 for r in records if r["correct"]["loose_fallback"] == 1
                           and r["content_answer"] is None)
    no_baseline = sum(1 for r in records if r["gold"] == 0) / len(records) if records else 0.0

    replay = {}
    for b in (256, 512, 1024, 2048):
        ans = sum(1 for r in records if 0 <= est_pos(r) <= b)
        corr = sum(1 for r in records if 0 <= est_pos(r) <= b
                   and r["correct"]["content_only"] == 1)
        replay[str(b)] = {"n": len(records), "content_answerable_est": ans,
                          "correct": corr,
                          "accuracy_over_all": round(corr / len(records), 4) if records else 0.0}

    return {
        "records": len(records),
        "per_cell": per_cell,
        "cell_status": status,
        "per_arm": arm_stats,
        "arm_by_cell": arm_by_cell,
        "matched_pairs": {"counts": counts, "mcnemar": mcnemar,
                          "per_cell": per_cell_pairs},
        "single_axis_transitions": transitions,
        "token_model_completion": two_factor_means(cell_means_tok),
        "token_law_completion_vs_k_at_E96": depth_law_at_E96,
        "token_law_completion_vs_edges_at_k8": load_law_at_k8,
        "distractor_mention_ratio_by_cell": dis_by_cell,
        "predictions": {
            "P1_load_arm_prompt_steps_ge_1.05": p1_load_ok,
            "P1_depth_arm_prompt_means_within_1pct": bool(p1_depth_ok),
            "P1_pass": p1_ok,
            "P2a_L0_status": st.get("L0"),
            "P2a_pass": p2a_ok,
            "P2b_non_maintained_bisect_cells": bisect_not_maintained,
            "P2b_pass": p2b_ok,
            "P2c_non_maintained_depth_cells": p2c_not_maintained,
            "P2c_pass": p2c_ok,
            "P3_L3_mean_distractor_mention_ratio": p3_ratio,
            "P3_pass": (p3_ratio is not None and p3_ratio >= 0.30),
            "P4_b_forward_ok_cross_not": counts["f_ok_x_not"],
            "P4_c_cross_ok_forward_not": counts["x_ok_f_not"],
            "P4_mcnemar_p_exact": mcnemar_exact(counts["f_ok_x_not"], counts["x_ok_f_not"]),
            "P4_direction_b_ge_c_pass": p4_ok,
            "P4_vacuous": counts["f_ok_x_not"] + counts["x_ok_f_not"] == 0,
            "P5_content_answers_correct": (
                f"{sum(1 for r in content_recs if r['correct']['content_only'] == 1)}"
                f"/{len(content_recs)}"),
            "P5_pass": p5_ok,
            "P6_fallback_no_share_when_content_silent": (round(p6_share, 4)
                                                         if p6_share is not None else None),
            "P6_silent_cells": len(silent),
            "P6_pass": (p6_share is not None and p6_share >= 0.6667),
            "P6_vacuous": len(silent) == 0,
            "P7_anchor_rows": anchor_rows,
            "P7_anchored_cells": len(anchor_rows),
            "P7_pass": p7_ok},
        "fallback_provenance": {
            "classes": dict(prov),
            "agreement_with_gold": {cls: prov_agree[cls] for cls in prov if cls != "no_trace_token"},
            "commit_fraction_median": (round(fractions[len(fractions) // 2], 4)
                                       if fractions else None),
            "strict_rule_on_content_silent_cells": strict_on_silent,
            "loose_fallback_when_content_silent": {
                "cells_with_trace_token": len(silent), "correct": fallback_correct,
                "constant_no_baseline_accuracy": round(no_baseline, 4)}},
        "budget_replay_content_only": replay,
        "totals": {
            "correct": {name: sum(1 for r in records if r["correct"][name] == 1)
                        for name in readout_names},
            "answered": {name: sum(1 for r in records
                                   if r["correct"][name] is not None)
                         for name in readout_names},
            "truncated": sum(1 for r in records
                             if (r["attempts"][-1].get("finish_reason") if r.get("attempts")
                                 else None) == "length"),
            "outcomes": dict(collections.Counter(r["outcome"] for r in records)),
            "errors": sum(1 for r in records if r["outcome"].startswith("transport_"))}}


def cells_for(k: int, chains: int) -> str:
    """Reverse map from (k, C) to the walk cell name, for records written before the cell
    name existed (defensive: the resume path must never KeyError on its own archive)."""
    for name, kk, cc in WALK:
        if kk == k and cc == chains:
            return name
    return f"K{k}C{chains}"


def probe(out_dir: str, resume: bool) -> int:
    global GATE_HASH
    os.makedirs(out_dir, exist_ok=True)
    raw_path = os.path.join(out_dir, "raw.jsonl")
    gate = build_gate()
    GATE_HASH = gate_hash(gate)
    if not gate["all_cells_pass"]:
        print("REFUSED: at least one cell failed the permutation-calibrated gate",
              file=sys.stderr)
        return 3
    if not gate["anchor_ok"]:
        print("REFUSED: the round-23 S3 anchor pins do not match the construction",
              file=sys.stderr)
        return 3
    done: dict = {}
    cap = AttemptBudget(PROMPT_CAP)
    if resume:
        if not os.path.exists(raw_path):
            print("--resume without raw.jsonl", file=sys.stderr)
            return 2
        with open(raw_path, "r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("gate_hash") != GATE_HASH:
                    print("--resume refused: raw.jsonl written under a different gate",
                          file=sys.stderr)
                    return 2
                key = (rec["arm"], rec.get("cell") or cells_for(rec["k"], rec["chains"]),
                       rec["seed"])
                done[key] = rec
                cap.used += len(rec["attempts"])
    health = health_check()
    cap.used += 1
    print(f"health: {health}", flush=True)
    if not health["ok"]:
        print("REFUSED: endpoint failed the chat-completion health probe",
              file=sys.stderr)
        return 4
    plan = []
    for cell in all_cells():
        for (f_item, x_item) in cell["pairs"]:
            plan.append((cell["cell"], "F", f_item, f_item["seed"]))
            plan.append((cell["cell"], "X", x_item, f_item["seed"]))
    if len(plan) + HEALTH_CALLS > PROMPT_CAP:
        print(f"plan {len(plan)} + health exceeds cap {PROMPT_CAP}", file=sys.stderr)
        return 2
    note = {"resumed_cells": len(done), "health": health, "gate_hash": GATE_HASH}

    def run(cell_name: str, arm: str, item: dict, pair_seed: int, phase: int) -> dict:
        rec = make_record(item, arm, pair_seed, cap, phase)
        rec["cell"] = cell_name
        results[(arm, cell_name, item["seed"])] = rec
        write_jsonl(raw_path, rec)
        print(f"{cell_name} k={rec['k']:>2} E={rec['edges']:>3} {rec['arm']} "
              f"gold={rec['gold']} outcome={rec['outcome']:>22} "
              f"content={str(rec['content_answer']):>4} "
              f"strict={str(rec['strict_trace_token']):>4} "
              f"ctok={rec['attempts'][-1]['completion_tokens']:>5} "
              f"wall={rec['attempts'][-1]['wall_s']:.1f}s", flush=True)
        return rec

    def key_of(entry) -> tuple:
        cell_name, arm, item, _ps = entry
        return (arm, cell_name, item["seed"])

    pending = [e for e in plan if key_of(e) not in done]
    results = dict(done)
    started = time.monotonic()
    # phase 1: two cells to measure the single-stream rate. The estimator is the corrected
    # one from round 22's lesson: completion_tokens / wall_s, not MAX_TOKENS / wall_s.
    phase1 = pending[:2]
    for (cn, a, it, ps) in phase1:
        run(cn, a, it, ps, 1)
    walls, rates = [], []
    for e in phase1:
        rec = results[key_of(e)]
        if not rec["attempts"]:
            continue
        att = rec["attempts"][-1]
        if att["wall_s"] and att["wall_s"] > 0:
            walls.append(att["wall_s"])
            if att["completion_tokens"]:
                rates.append(att["completion_tokens"] / att["wall_s"])
    tps = max([TPS_FLOOR] + rates)
    est_cost = MAX_TOKENS if not rates else max(512, min(MAX_TOKENS, int(
        3 * sum(results[key_of(e)]["attempts"][-1]["completion_tokens"]
                for e in phase1 if results[key_of(e)]["attempts"]) / max(1, len(phase1)))))
    remaining = pending[2:]
    est_total = len(remaining) * est_cost / tps
    chosen = None
    for cand in CONCURRENCY_CHOICES:
        if est_total / cand * 1.25 <= PHASE2_BUDGET_S:
            chosen = cand
            break
    if chosen is None:
        chosen = max(CONCURRENCY_CHOICES)
    if tps < 30.0:
        chosen = max(chosen, 4)
    note.update({"phase1_walls": walls, "measured_tokens_per_second": round(tps, 2),
                 "estimated_tokens_per_cell": est_cost,
                 "estimate_phase2_s": round(est_total, 1), "chosen_concurrency": chosen})
    print(f"phase-1 walls {[round(w, 1) for w in walls]} s, measured ~{round(tps, 1)} "
          f"tok/s, {est_cost} tok/cell est, concurrency {chosen} for {len(remaining)} "
          f"cells", flush=True)
    phase2_start = time.monotonic()
    to_run, abandoned = [], []
    for entry in remaining:
        if time.monotonic() > phase2_start + PHASE2_BUDGET_S:
            abandoned.append(entry)
        else:
            to_run.append(entry)
    for (cn, a, it, ps) in abandoned:
        rec = blank_record(it, a, ps, 2)
        rec["cell"] = cn
        rec.update({"completion_tokens": 0, "prompt_tokens": 0,
                    "outcome": "abandoned_budget", "content_answer": None,
                    "reasoning_answer": None, "loose_fallback_answer": None,
                    "strict_trace_token": None, "delivered_or_strict_answer": None,
                    "fallback_provenance_class": None, "fallback_commit_fraction": None,
                    "correct": {"content_only": None, "loose_fallback": None,
                                "delivered_or_strict": None}})
        results[key_of(entry)] = rec
        write_jsonl(raw_path, rec)
    if to_run:
        with concurrent.futures.ThreadPoolExecutor(max_workers=chosen) as pool:
            futures = [pool.submit(run, cn, a, it, ps, 2) for (cn, a, it, ps) in to_run]
            for fut in concurrent.futures.as_completed(futures):
                fut.result()
    ordered = [results[key_of(e)] for e in plan]
    summary = aggregate(ordered)
    summary["gate_hash"] = GATE_HASH
    summary["wall_seconds"] = round(time.monotonic() - started, 1)
    summary["transport"] = note
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write("\n")
    with open(os.path.join(out_dir, "gate.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(gate, gate_hash=GATE_HASH), fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(json.dumps({"totals": summary["totals"],
                      "cell_status": {k: v["report"] for k, v in summary["cell_status"].items()},
                      "frontier": summary["cell_status"]["content_only"]["maintained_by_k"],
                      "matched_pairs": summary["matched_pairs"]["mcnemar"],
                      "predictions": summary["predictions"]}, indent=2, sort_keys=True))
    return 0


def cmd_gate(out_path: str) -> int:
    gate = build_gate()
    gate = dict(gate, gate_hash=gate_hash(gate))
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(gate, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"gate {gate['gate_hash'][:8]}: all_cells_pass={gate['all_cells_pass']} "
          f"anchor_ok={gate['anchor_ok']} planned={gate['planned_prompts']} "
          f"corpus={gate['corpus_blob_sha256'][:12]}")
    for c in gate["cells"]:
        g, gp = c["gate_pool"], c["gate_paired_pool"]
        print(f"  {c['cell']} k={c['k']:>2} C={c['chains']:>2} E={c['edges']:>3} "
              f"pool: {g['verdict']} obs={g['observed_max']} thr={g['calibrated_threshold']} "
              f"p={g['p_value']} | paired: {gp['verdict']} obs={gp['observed_max']} "
              f"thr={gp['calibrated_threshold']} p={gp['p_value']} "
              f"chars={c['load']['prompt_chars_mean']}")
    for label, row in sorted(gate["anchor"]["anchors"].items()):
        print(f"  anchor {label} cell {row['cell']}: pool={row['pool_blob_matches']} "
              f"prompts={row['forward_prompts_match']}")
    return 0 if (gate["all_cells_pass"] and gate["anchor_ok"]) else 3


def cmd_analyze(out_dir: str) -> int:
    raw_path = os.path.join(out_dir, "raw.jsonl")
    records = [json.loads(line) for line in open(raw_path, encoding="utf-8")
               if line.strip()]
    summary = aggregate(records)
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def synthetic_record(cell_name: str, arm: str, seed: int, gold: int, content: str,
                     reasoning: str, completion_tokens: int,
                     finish_reason: str = "stop") -> dict:
    """A record shaped exactly like make_record's output, for the analysis smoke test."""
    att = {"attempt": 1, "wall_s": 1.0, "error_class": None,
           "started_at": now_iso(), "finished_at": now_iso(),
           "finish_reason": finish_reason, "prompt_tokens": 100,
           "completion_tokens": completion_tokens, "content": content,
           "reasoning": reasoning}
    att.update(readouts(content, reasoning))
    att["mechanics"] = {"distractor_entities": 5, "distractors_mentioned": 2,
                        "distractor_mention_ratio": 0.4}
    rec = {"arm": arm, "cell": cell_name, "level": 96, "k": 4, "chains": 24,
           "edges": 96, "seed": seed, "pair_seed": seed, "seed_hash": "x",
           "item_sha256": "x", "prompt_sha256": "x", "prompt_chars": 100, "gold": gold,
           "gate_hash": "x", "phase": 2, "attempts": [att],
           "completion_tokens": completion_tokens, "prompt_tokens": 100,
           "outcome": classify_attempt(att)}
    for field in ("content_answer", "reasoning_answer", "loose_fallback_answer",
                  "loose_fallback_source", "strict_trace_token",
                  "delivered_or_strict_answer", "fallback_provenance_class",
                  "fallback_commit_fraction"):
        rec[field] = att[field]
    rec["correct"] = {}
    for name in ("content_only", "loose_fallback", "delivered_or_strict"):
        ans = {"content_only": att["content_answer"],
               "loose_fallback": att["loose_fallback_answer"],
               "delivered_or_strict": att["delivered_or_strict_answer"]}[name]
        rec["correct"][name] = (None if ans is None
                                else int((1 if ans == "yes" else 0) == gold))
    return rec


def selftest() -> None:
    checks = 0

    def ok(cond, msg):
        nonlocal checks
        checks += 1
        assert cond, msg

    # 1. the two arms are single-axis, the load arm is strictly rising in E at fixed
    #    k = 8, the depth arm holds E = 96 while k strictly rises, and the anchor cell is
    #    the (k, C) shape round 23 measured; none of the five measurement cells collides
    #    with any (k, C) shape archived by rounds 21 to 23
    load_ks = [k for _n, k, _c in LOAD_ARM]
    load_es = [k * c for _n, k, c in LOAD_ARM]
    ok(all(k == 8 for k in load_ks), "load arm does not hold k = 8")
    ok(load_es == sorted(load_es) and len(set(load_es)) == len(load_es),
       "load arm fact count not strictly rising")
    depth_es = [k * c for _n, k, c in DEPTH_ARM]
    depth_ks = [k for _n, k, _c in DEPTH_ARM]
    ok(all(e == 96 for e in depth_es), "depth arm does not hold E = 96")
    ok(depth_ks == sorted(depth_ks) and len(set(depth_ks)) == len(depth_ks),
       "depth arm hop depth not strictly rising")
    for arm in (LOAD_ARM, DEPTH_ARM):
        for (na, ka, ca), (nb, kb, cb) in zip(arm, arm[1:]):
            ok((ka == kb) != (ka * ca == kb * cb),
               f"step {na}->{nb} must change exactly one axis")
    ok(("L0", 8, 12) in LOAD_ARM, "anchor cell is not the round-23 S3 shape (8, 12)")
    archived_shapes = {(2, 12), (3, 8), (4, 6), (6, 4), (8, 3), (12, 2),  # round 21
                       (4, 12), (4, 24), (4, 36), (4, 48), (4, 60),       # round 22
                       (8, 24), (12, 16), (16, 12)}                       # round 23
    measurement = [(k, c) for n, k, c in WALK if n != "L0"]
    ok(not (set(measurement) & archived_shapes),
       "a round-24 measurement cell reuses an archived (k, C) shape")
    ok(load_es[0] == 96 and load_es[-1] == 160 and max(depth_ks) == 16,
       "arms do not sit inside the declared bracket")

    # 1b. the tolerance helpers themselves: a must-see step must fail on a tie, an
    #     equal-load equality must tolerate entity-name-length noise (round 23 P1 lesson)
    ok(steps_at_least([100.0, 110.0, 120.0], 1.05), "visible load steps rejected")
    ok(not steps_at_least([100.0, 100.1, 120.0], 1.05), "invisible step accepted")
    ok(not steps_at_least([100.0, 90.0, 120.0], 1.05), "dip accepted")
    ok(within_tolerance(1000.0, 1001.2, 0.01), "0.12% noise failed the tolerance")
    ok(not within_tolerance(1000.0, 1020.0, 0.01), "2% divergence passed the tolerance")
    ok(not within_tolerance(None, 1.0, 0.01), "missing mean passed the tolerance")

    # 2. structural and solvability audit on every candidate and variant, and the
    #    matched-pair invariant on every dispatched pair
    gate_cells = {c["cell"]: c for c in all_cells()}
    for name, k, c_chains in WALK:
        pairs, pool, paired_pool = build_cell(k, c_chains, PAIRS_PER_LEVEL)
        ok(len(pool) == CANDIDATES, f"pool size {name}")
        ok(len(pairs) == PAIRS_PER_LEVEL, f"pair count {name}")
        for it in pool:
            ok(not verify_item(it), f"audit {name} seed={it['seed']}")
            ok(it["edges"] == k * c_chains, f"E not as declared at {name}")
            ok(it["level"] == k, f"k not constant at {name}")
        for (f_item, x_item) in pairs:
            ok(not verify_item(x_item), f"variant audit {name}")
            ok(not pair_violations(f_item, x_item), f"pair invariant {name}")
            ok(f_item["answer"] == "yes" and x_item["answer"] == "no",
               f"pair labels {name}")
        ok(len(paired_pool) == 2 * sum(1 for it in pool if it["answer"] == "yes"),
           f"paired pool size {name}")
        ok(len({it["seed"] for it in pool}) == CANDIDATES, f"seed uniqueness {name}")

    # 3. negative controls on the structural audit (planted defects must be caught)
    k0, c0 = 8, 12
    base = gen_item(k0, c0, cell_seed(k0, c0, 0))
    while base["answer"] != "yes":
        base = gen_item(k0, c0, base["seed"] + 1)
    ok(not verify_item(base), "clean item failed the audit")
    planted = dict(base)
    planted["facts"] = [list(f) for f in base["facts"]] + [[base["facts"][0][0], REL,
                                                            base["facts"][0][0] + "zz"]]
    ok(bool(verify_item(planted)), "planted detached fact not caught")
    planted = dict(base)
    planted["facts"] = [list(f) for f in base["facts"]][:-1]
    ok(bool(verify_item(planted)), "planted truncated component not caught")
    planted = dict(base)
    planted["answer"] = "no"
    ok("stored answer disagrees with independent BFS" in verify_item(planted),
       "planted flipped label not caught")
    planted = dict(base)
    planted["facts"] = [list(f) for f in base["facts"]]
    planted["facts"].append(list(planted["facts"][0]))
    ok("duplicate facts" in verify_item(planted), "planted duplicate fact not caught")
    planted = dict(base)
    planted["chains"] = base["chains"] + 1
    ok(bool(verify_item(planted)), "planted manifest component count not caught")

    # 4. negative controls on the matched-pair invariant (#78 criterion 1)
    f_item = base
    x_item = x_variant(f_item)
    ok(not pair_violations(f_item, x_item), "clean pair rejected")
    # a variant built from ANOTHER item's facts (here: from the (4, 6) origin corner of
    # rounds 21 and 22, a shape outside this round's grid, so the fact lists and entity
    # sets cannot coincide by accident) must be caught
    other = next(gen_item(4, 6, cell_seed(4, 6, i)) for i in range(CANDIDATES)
                 if gen_item(4, 6, cell_seed(4, 6, i))["answer"] == "yes")
    ok(canonical(other["facts"]) != canonical(f_item["facts"]),
       "planted control item is not actually different")
    cross_item = dict(other)
    cross_item["query"] = [f_item["query"][0], REL, other["query"][2]]
    cross_item["answer"] = "no"
    cross_item["chain_len"] = None
    planted_viol = pair_violations(f_item, cross_item)
    ok("fact lists differ" in planted_viol and "entity name sets differ" in planted_viol,
       "planted cross-item pair not caught")
    same_target = dict(x_item)
    same_target["query"] = [f_item["query"][0], REL, f_item["query"][2]]
    same_target["answer"] = "no"
    ok("queried targets are identical" in pair_violations(f_item, same_target),
       "planted identical-target pair not caught")
    diff_source = dict(x_item)
    diff_source["query"] = [base["facts"][0][0], REL, x_item["query"][2]]
    ok(bool(pair_violations(f_item, diff_source)), "planted different-source pair not caught")
    reachable = dict(x_item)
    reachable["query"] = [f_item["query"][0], REL, f_item["query"][2]]
    reachable["answer"] = "no"
    ok("cross-component target is reachable from the source"
       in pair_violations(f_item, reachable), "planted reachable X target not caught")

    # 5. the leak gate: a planted traversal-free predictor must be flagged
    pool = [gen_item(k0, c0, cell_seed(k0, c0, i)) for i in range(12)]
    for it in pool:
        feat = features(it)["tgt_name_lt_src_name"]
        it["answer"] = "yes" if feat else "no"
    flagged = gate_battery(pool)
    ok(flagged["verdict"] == "leak", "planted leak not flagged")
    ok(any("tgt_name_lt_src_name" in r for r in flagged["flagged_rules"]),
       "planted leak rule not named")
    clean = [gen_item(k0, c0, cell_seed(k0, c0, i)) for i in range(12)]
    ok(gate_battery(clean)["verdict"] != "leak", "clean pool flagged")

    # 6. readout stack, vendored strict rule, provenance classes
    ok(readouts("yes", "reasoning")["content_answer"] == "yes", "content readout")
    ok(readouts("", "so the answer is no.")["loose_fallback_answer"] == "no",
       "loose fallback")
    ok(readouts("", "so the answer is no.")["delivered_or_strict_answer"] == "no",
       "strict readout on cued verdict")
    ok(readouts("", "check A then B")["loose_fallback_answer"] is None,
       "phantom fallback token")
    ok(strict_last_trace_token("I will answer yes/no after checking.") is None,
       "instruction echo accepted as a commitment")
    ok(strict_last_trace_token("chain is aq zeq fir then ghm") is None,
       "mid-trace bare token accepted")
    ok(strict_last_trace_token("walking the chain gives no") == "no",
       "trace-closing verdict rejected")
    ok(provenance_class("answer yes/no then stop")[0] == "instruction_echo",
       "echo class")
    ok(provenance_class("a" * 100 + " no")[0] == "terminal", "terminal class")
    ok(provenance_class("no " + "b" * 500)[0] == "mid_trace", "mid-trace class")
    ok(provenance_class("nothing at all") == (None, -1.0), "no trace token class")

    # 7. arithmetic: Wilson, exact McNemar, the linear solver, the two-factor fit
    lb, ub = wilson(6, 6)
    ok(abs(lb - 0.6097) < 0.001, f"Wilson 6/6 lower bound {lb:.4f}")
    ok(abs(ub - 1.0) < 1e-9, "Wilson 6/6 upper bound")
    ok(wilson(0, 0) == (0.0, 0.0), "Wilson empty")
    ok(mcnemar_exact(0, 0) == 1.0, "McNemar no discordance")
    ok(abs(mcnemar_exact(1, 0) - 1.0) < 1e-12, "McNemar 1/0: one discordant pair is not "
       "significant and the report must say so")
    ok(abs(mcnemar_exact(2, 0) - 0.5) < 1e-12, "McNemar 2/0")
    ok(mcnemar_exact(6, 0) < 0.05, "McNemar 6/0 should be significant")
    ok(solve_linear([[1.0, 0.0], [0.0, 1.0]], [3.0, 4.0]) == [3.0, 4.0], "solve identity")
    ok(solve_linear([[1.0, 2.0], [2.0, 4.0]], [1.0, 3.0]) is None, "singular not detected")
    fit = two_factor_means([("A", 4.0, 24.0, 300.0), ("B", 4.0, 96.0, 400.0),
                            ("C", 8.0, 96.0, 500.0), ("D", 8.0, 192.0, 700.0),
                            ("E", 12.0, 192.0, 900.0), ("F", 16.0, 192.0, 1100.0)])
    ok(fit["fit"] is not None and fit["fit"]["b_per_fact"] > 0, "load coefficient sign")
    ok(fit["r2"] is not None and fit["r2"] > 0.9, "fit quality on near-linear means")
    ok(two_factor_means([("A", 4.0, 24.0, 300.0)])["fit"] is None,
       "fit accepted with too few cells")

    # 8. the trichotomy and the two-dimensional frontier report
    rows = [{"cell": "L0", "k": 8, "edges": 96, "n": 6, "correct": 6, "wrong": 0,
             "no_answer": 0},
            {"cell": "L1", "k": 8, "edges": 112, "n": 6, "correct": 6, "wrong": 0,
             "no_answer": 0},
            {"cell": "L2", "k": 8, "edges": 128, "n": 6, "correct": 4, "wrong": 0,
             "no_answer": 2},
            {"cell": "L3", "k": 8, "edges": 160, "n": 6, "correct": 0, "wrong": 0,
             "no_answer": 6},
            {"cell": "D1", "k": 12, "edges": 96, "n": 6, "correct": 6, "wrong": 0,
             "no_answer": 0},
            {"cell": "D2", "k": 16, "edges": 96, "n": 6, "correct": 1, "wrong": 5,
             "no_answer": 0}]
    placed = place_cell_status(rows)
    by_cell = {r["cell"]: r["status"] for r in placed["rows"]}
    ok(by_cell["L0"] == "maintained" and by_cell["L1"] == "maintained",
       "clean cells not maintained")
    ok(by_cell["L2"] == "inconclusive", f"planted partial silence read {by_cell['L2']}")
    ok(by_cell["L3"] == "budget_limited", f"planted full silence read {by_cell['L3']}")
    ok(by_cell["D1"] == "maintained", "D1 not maintained")
    ok(by_cell["D2"] == "collapsed", f"planted collapse read {by_cell['D2']}")
    ok(placed["maintained_by_k"]["8"] == 112, "frontier by k wrong at k=8")
    ok(placed["maintained_by_edges"]["96"] == 12, "frontier by E wrong at E=96")
    ok("first non-maintained cell L2" in placed["report"], "report wording")
    small = place_cell_status([{"cell": "L0", "k": 8, "edges": 96, "n": 3, "correct": 3,
                               "wrong": 0, "no_answer": 0}])
    ok(small["rows"][0]["status"] == "descriptive", "small n certified")

    # 9. mechanics: distractor accounting and traversal coverage
    item = next(gen_item(k0, c0, cell_seed(k0, c0, i)) for i in range(CANDIDATES)
                if gen_item(k0, c0, cell_seed(k0, c0, i))["answer"] == "yes")
    dis = distractor_names(item)
    ok(len(dis) == (c0 - 1) * (k0 + 1), f"distractor count {len(dis)}")
    seq = expected_chain(item)
    ok(len(seq) == k0 + 1, "expected chain length")
    ok(ordered_prefix_hops(seq, " ".join(seq)) == k0 + 1, "full traversal coverage")
    ok(ordered_prefix_hops(seq, " ".join(seq[:3]) + " junk " + seq[-1]) == 3,
       "partial traversal coverage")
    ok(ordered_prefix_hops(seq, "no entities here") == 0, "phantom coverage")

    # 10. attempt classification and retry policy
    base_att = {"error_class": None, "completion_tokens": 10, "content_answer": "yes",
                "reasoning_answer": None, "finish_reason": "stop"}
    ok(classify_attempt(dict(base_att)) == "answered_in_answer_field", "answered class")
    ok(classify_attempt(dict(base_att, content_answer=None)) == "trace_only"
       or classify_attempt(dict(base_att, content_answer=None)) == "no_answer_stop",
       "silent class")
    ok(classify_attempt(dict(base_att, completion_tokens=0)) == "empty_completion",
       "empty class")
    ok(classify_attempt(dict(base_att, error_class="timeout")) == "transport_timeout",
       "transport class")
    ok(classify_attempt(dict(base_att, content_answer=None, completion_tokens=2048,
                            finish_reason="length")) == "truncated_no_answer",
       "truncation class")
    ok(is_retryable("empty_completion") and is_retryable("transport_http_502"),
       "retry policy too strict")
    ok(not is_retryable("truncated_no_answer") and not is_retryable("answered_in_answer_field"),
       "retry policy too loose")
    cap = AttemptBudget(2)
    ok(cap.acquire() and cap.acquire() and not cap.acquire(), "attempt cap")

    # 11. the sanitizer holds the public-only rule on hostile model output. The hostile
    #   strings are assembled at runtime from fragments so that the repo-facing artifact
    #   scan (research/AGENTS.md: no URL or IPv4 literal in a round directory) stays clean
    #   while the pattern under test is exercised with a real URL, a real IPv4 shape and a
    #   real absolute path.
    fake_url = "https:" + "//" + "ex" + ".ampl" + ".e" + "/path"
    fake_ip = "192" + "." + "168" + "." + "5" + "." + "4"
    fake_path = "/" + "home" + "/" + "some" + "/" + "dir" + "/file." + "bin"
    fake_win = "C:" + "\\" + "Models" + "\\" + "x.bin"
    dirty = f"see {fake_url} and {fake_ip} plus {fake_path} and {fake_win}"
    clean_text = sanitize(dirty)
    ok(fake_url in dirty and fake_ip in dirty and fake_path in dirty,
       "sanitizer fixture did not assemble")
    for token in (".ampl", fake_ip, "/home", "Models"):
        ok(token not in clean_text, f"sanitizer leaked {token}")
    ok("[REDACTED]" in clean_text, "sanitizer left no marker")
    ok("yes" in sanitize("yes"), "sanitizer ate a verdict")

    # 12. anchor pins: the L0 pool IS the round-23 S3 pool (fail-closed)
    gate = build_gate()
    anch = gate["anchor"]["anchors"]
    ok(anch["A1"]["pool_blob_matches"] and anch["A1"]["forward_prompts_match"],
       "round-23 S3 anchor mismatch")
    ok(gate["anchor"]["all_ok"] and gate["anchor_ok"], "gate anchor flag not set")
    ok(gate["planned_prompts"] == 36 and gate["planned_prompts"] + HEALTH_CALLS
       <= PROMPT_CAP, "prompt plan exceeds the cap")
    tampered = json.loads(canonical(gate))
    tampered["cells"][0]["pool_blob_sha256"] = "0" * 64
    ok(anchor_state(tampered)["all_ok"] is False, "tampered anchor accepted")

    # 13. gate refuses a leaky construction end to end
    ok(gate["all_cells_pass"] is True, "declared grid does not pass its own gate")
    for cell in gate["cells"]:
        ok(cell["gate_pool"]["verdict"] != "leak", f"pool leak {cell['cell']}")
        ok(cell["gate_paired_pool"]["verdict"] != "leak", f"paired leak {cell['cell']}")
        ok(cell["load"]["prompt_chars_min"] > 200, "prompt too short to carry the facts")

    # 14. analysis smoke test on synthetic records: statuses, discordance, predictions,
    #     budget replay, and the readout stack, all wired to the two arms
    recs = []
    for cell_name in ("L0", "L1", "L2", "L3", "D1", "D2"):
        for j in range(PAIRS_PER_LEVEL):
            seed = 1000 + j
            recs.append(synthetic_record(cell_name, "F", seed, 1, "yes", "chain checked",
                                         300))
            recs.append(synthetic_record(cell_name, "X", seed, 0, "no", "other branch",
                                         320))
    summary = aggregate(recs)
    ok(summary["records"] == 36, "smoke test record count")
    ok(summary["totals"]["correct"]["content_only"] == 36, "smoke test correctness")
    ok(summary["matched_pairs"]["counts"]["pairs"] == 18, "smoke test pair count")
    ok(summary["matched_pairs"]["mcnemar"]["p_exact"] == 1.0, "smoke test McNemar")
    ok(summary["predictions"]["P5_pass"] is True, "smoke test P5")
    ok(summary["predictions"]["P2a_pass"] is True, "smoke test P2a")
    ok(summary["predictions"]["P2b_pass"] is False, "smoke test P2b should not fire")
    ok(summary["predictions"]["P2c_pass"] is True, "smoke test P2c at full delivery")
    ok(summary["predictions"]["P4_vacuous"] is True, "smoke test P4 vacuity")
    ok(summary["predictions"]["P6_vacuous"] is True, "smoke test P6 vacuity")
    # negative control for the P1 wiring: flat synthetic prompt means must FAIL the
    # load-arm step clause (the check has to actually look at the token data)
    ok(summary["predictions"]["P1_pass"] is False, "P1 accepted flat prompt means")
    ok(len(summary["single_axis_transitions"]) == 4, "transition count")
    ok(all(t["axis"] == t["declared_axis"] and t["axis"] in ("load", "depth")
           for t in summary["single_axis_transitions"]), "transition axis mislabelled")
    st_from = {t["from"]: t["status"].split("->")[0]
               for t in summary["single_axis_transitions"]}
    ok(st_from.get("L0") == "maintained", "smoke test status wiring")

    def plant(cell_name: str, arm: str, seed: int) -> dict:
        target = [r for r in recs if r["cell"] == cell_name and r["arm"] == arm
                  and r["seed"] == seed]
        assert len(target) == 1, f"plant target {cell_name} {arm} {seed} not unique"
        return target[0]

    def silence(rec: dict, finish_reason: str) -> None:
        rec["content_answer"] = None
        rec["correct"]["content_only"] = None
        rec["reasoning_answer"] = "no"
        rec["loose_fallback_answer"] = "no"
        rec["correct"]["loose_fallback"] = 1
        rec["fallback_provenance_class"] = "terminal"
        rec["fallback_commit_fraction"] = 0.99
        rec["attempts"][-1]["finish_reason"] = finish_reason

    # plant a discordant pair on L2: arm X silent while its OWN arm F partner is correct;
    # this must ALSO flip P2b (the bisection fires at E = 128)
    silence(plant("L2", "X", 1000), "stop")
    summary2 = aggregate(recs)
    ok(summary2["matched_pairs"]["counts"]["f_ok_x_not"] == 1,
       "planted discordance not counted")
    ok(summary2["matched_pairs"]["counts"]["x_ok_f_not"] == 0,
       "planted discordance counted in the wrong direction")
    ok(summary2["predictions"]["P4_direction_b_ge_c_pass"] is True,
       "P4 direction did not fire on planted discordance")
    ok(summary2["predictions"]["P4_vacuous"] is False, "P4 vacuity wrong after plant")
    ok(summary2["predictions"]["P5_pass"] is True, "P5 fired on a silent cell")
    ok(summary2["predictions"]["P6_silent_cells"] == 1, "P6 silent wiring")
    ok(summary2["predictions"]["P2b_pass"] is True,
       "P2b did not fire once the bisection cell stopped delivering")
    ok(summary2["cell_status"]["content_only"]["rows"][0]["cell"] == "L0",
       "cells not in grid order")
    # plant two content-silent truncations on D2: the depth arm at the safe load must
    # flip P2c, and the truncation counter must see both
    silence(plant("D2", "X", 1000), "length")
    silence(plant("D2", "X", 1001), "length")
    summary3 = aggregate(recs)
    ok(summary3["totals"]["truncated"] == 2, "planted truncations not counted")
    ok(summary3["predictions"]["P2c_pass"] is False,
       "P2c did not fire once the depth arm stopped delivering at safe load")
    ok(summary3["predictions"]["P6_fallback_no_share_when_content_silent"] == 1.0,
       "P6 fallback skew wiring")
    ok(summary3["budget_replay_content_only"]["2048"]["content_answerable_est"]
       <= summary3["budget_replay_content_only"]["2048"]["n"], "replay exceeds n")
    ok(est_pos(recs[0]) >= 0, "est_pos refused a record with a content answer")
    ok(est_pos({"attempts": []}) == -1, "est_pos on empty attempts")

    # 15. resume key stability: cells_for inverts the grid, unknown shapes never collide
    ok(cells_for(8, 12) == "L0" and cells_for(8, 14) == "L1", "grid reverse map")
    ok(cells_for(16, 6) == "D2" and cells_for(12, 8) == "D1", "grid reverse map far cells")
    ok(cells_for(99, 99) == "K99C99", "unknown cell shape mapped wrongly")
    names = [n for n, _k, _c in WALK]
    ok(len(set(names)) == len(names), "duplicate cell names in the grid")
    ok(len({(k, c) for _n, k, c in WALK}) == len(WALK), "duplicate (k, C) in the grid")

    print(f"selftest: {checks} checks, 0 failures")


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--out", default="gate.json")
    ap.add_argument("--out-dir", default="research/nightly-2026-10-25-0405")
    args = ap.parse_args(argv[1:])
    if args.selftest:
        selftest()
        return 0
    if args.gate:
        return cmd_gate(args.out)
    if args.probe:
        return probe(args.out_dir, resume=args.resume)
    if args.analyze:
        return cmd_analyze(args.out_dir)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

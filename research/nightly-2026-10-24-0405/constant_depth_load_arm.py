#!/usr/bin/env python3
"""Nightly round 22 (tracker #65, firing 2026-10-24 04:05): the constant-DEPTH load
arm on the flash-next-class endpoint, on a true matched pair, scored under the
declared readout stack.

Question (issue #71, the load axis its option 2 leaves open, and issue #78's
"there is no true matched pair"). Round 21 measured the depth axis at constant
prompt load (E = 24 facts, k in {2..12}) on this endpoint class and found no
turnover anywhere in the grid: 36 of 36 cells answered IN THE ANSWER FIELD and 36
of 36 correct. Its conclusion was that the recorded negative-arm answerability
failure at k = 24 (round 19: 0 of 6 negative cells delivered an answer at any
budget up to 2048) is a joint prompt-load x budget effect, so the ceiling lives on
the LOAD axis, and the load axis has never been measured at constant depth. One
question: at FIXED hop depth k = 4, does the delivered answer turn over as the fact
count E grows through {24, 48, 96, 144, 192, 240}, and is any turnover a surfacing
(budget) collapse or a correctness collapse?

Instrument (issue #78 acceptance criterion 1, "build a true matched pair inside one
item", adapted to the polarity contrast rather than the shortcut contrast): each
level dispatches PAIRS_PER_LEVEL graphs, and every graph is asked TWO questions over
the IDENTICAL fact list with the IDENTICAL entity names and the identical queried
source - the forward query whose gold is yes (arm F) and the cross-component query
whose gold is no (arm X). Only the queried target varies. pair_violations() asserts
the shared-content invariants on every dispatched pair, and --selftest carries the
planted non-matched control required by #78 (a variant built from a different item's
facts must be caught). What this pair does NOT vary is shortcut-versus-traversal
depth: #78's shortcut arm (a query answerable by a single stated fact) is a different
contrast and stays open on #78.

Readout stack (issue #94, declared before dispatch, vendored verbatim from round 19
through round 21):

  content_only        last standalone yes/no in the answer field; the delivered answer
  loose_fallback      the archived convention of rounds 10..18: content, else the last
                      yes/no in the reasoning field
  delivered_or_strict content answer if present, else the strict trace commitment
                      (round 19's rule: outside an echo phrase, and either closing the
                      trace or answer-cued within 30 characters and closed by punctuation)

Independence: this file imports nothing from generators/ and re-uses the
component-isomorphic construction, BFS solver, structural verifier and
permutation-calibrated leak gate as re-implemented for round 21, with the same
seed-base and name pools, so the E = 24 level of this grid is the SAME construction as
round 21's k = 4 level. That is used as a fail-closed anchor (see R21 pins): the
40-candidate pool blob and the three arm-F prompt digests at E = 24 must equal the
values archived in research/nightly-2026-10-24-0205/ (PR #95); --probe refuses
otherwise. The pins are hardcoded constants, not a file dependency, so the post-merge
tree verifies them without needing the ancestor branch. The three anchored prompts
also give a same-endpoint double dispatch: round 19's next step 4 and round 18's next
step 3 asked for exactly this (temperature-0 reruns to separate endpoint noise from
quantization noise).

Declared grid (fixed before any measurement, seed-frozen, seed_base 20261024):
  arm M  constant depth k = 4; E in {24, 48, 96, 144, 192, 240}; C = E/4 disjoint
         directed paths (6, 12, 24, 36, 48, 60); 3 graphs per level x 2 queries
         (F forward gold-yes, X cross-component gold-no) -> 36 prompts
total 36 prompts + 1 health probe = 37 of the 40-call cap, max_tokens 2048,
temperature 0.0, one sample per item, no exemplars, no chain of thought asked.
Depth is constant by construction (the verifier asserts every component is a directed
path of exactly k edges), so the ONLY thing this arm varies is how many facts the
model has to search through, and, with it, the prompt length.

Declared predictions (fixed in the gate before any prompt is spent):
  P1 load visible to the tokenizer: mean prompt_tokens at E = 240 >= 5x the mean at
     E = 24 and non-decreasing in E (the construction ramps load; this checks the
     endpoint's tokenizer sees it, the mirror of round 21's constancy check).
  P2a no turnover below the ramp: under content_only the levels E in {24, 48, 96} are
     all classified maintained (round-8 trichotomy, Wilson 95% floor 0.60, no-answer
     rate <= 0.5). E = 24 is round 21's measured operating point.
  P2b the ramp bites at the top: the top level E = 240 is NOT maintained (at least one
     cell fails to deliver, or the Wilson lower bound falls under the floor). If E =
     240 also comes back maintained, load alone at k = 4 does not reach the ceiling
     inside this grid and the joint load x depth model on #71 needs a wider ramp.
  P3 enumeration token law: mean completion_tokens at E = 240 >= 3x the mean at E = 24
     (traversal work is constant at k = 4, so growth this large means the output is
     spending on the irrelevant facts, which is what round 19 saw at k = 24).
  P4 polarity asymmetry on the matched pair: at least one pair where arm F delivered a
     correct answer while its own matched arm X partner did not (F ok, X not ok), and
     no pair in the opposite direction. This is the unconfounded version of the
     round-19 finding that the negative arm is the fragile one.
  P5 the delivered answer is never wrong: every content_only answer in the whole grid
     is correct. Failures should be silence, not error; if an answer is WRONG, the
     turnover is a correctness collapse, not a surfacing collapse.
  P6 fallback skew where content is silent (issue #94): among cells whose answer field
     carries no yes/no but whose trace does, at least 2/3 of the fallback tokens are
     "no" (round 19's rescue-loading signature, measured on the load ramp).
  P7 anchor reproducibility: all three anchored E = 24 arm-F prompts deliver the same
     answer round 21 recorded for them (temperature 0, same endpoint class).

Usage:
  constant_depth_load_arm.py --selftest
  constant_depth_load_arm.py --gate              [--out gate.json]
  constant_depth_load_arm.py --probe             [--out-dir DIR] [--resume]
  constant_depth_load_arm.py --analyze           [--out-dir DIR]
The endpoint is read from NIGHTLY_BASE_URL, NIGHTLY_MODEL_ID and NIGHTLY_API_KEY and
no endpoint value is ever written to an artifact; stored model text passes a
sanitizer for URLs, IP addresses and absolute paths.
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
K_FIXED = 4
LEVELS_E = (24, 48, 96, 144, 192, 240)
PAIRS_PER_LEVEL = 3
CANDIDATES = 40
MIN_CERTIFY = 6
ITEM_DEADLINE_S = 900
PHASE2_BUDGET_S = 1500
TPS_FLOOR = 10.0
CONCURRENCY_CHOICES = (1, 2, 3, 4, 6, 8)
HEALTH_PROMPT = "Reply with exactly one word: yes"
# Health-probe output budget, lowered from the operating budget before the first
# prompt of this round was spent (disclosed in transport.json): the health call exists
# to prove generation-healthy, not to spend 2048 tokens, and on the serving
# deployment used here a 2048-token health call was killed by an upstream gateway at
# ~60 s (http_502) while a 256-token call returned in ~1 s. MAX_TOKENS, the grid, the
# corpus and therefore the gate hash are untouched by this transport-only change.
HEALTH_BUDGET = 256

# Fail-closed anchors into round 21's archive (research/nightly-2026-10-24-0205/,
# PR #95): the 40-candidate pool blob of its k = 4 cell and the three arm-F prompt
# digests selected there. This arm re-uses that construction's seed base, name pools,
# seed formula and selection order, so E = 24 IS round 21's k = 4 level; these values
# are what makes that identity checkable rather than asserted in prose.
R21_POOL_BLOB_E24 = ("11ab33acc9ea42fdc638298f548d3e1dd51a2b124b5a6823f362de99c11fe8f6")
R21_FORWARD_PROMPTS = frozenset({
    "0541a776b88e38c034633f622e62bf1bc5ec8eded0d35cc087932026ca04e704",
    "7aaa76e694771605c809323fe21e9351f7ea66f8633e2ffbc6513445a2d9caa6",
    "8e09374c031c1758c9aefdc3f5f29518b40c51e352aea1404319df8b7e8c4a81"})
R21_FORWARD_COMPLETION = {24321024: 351, 24321028: 360, 24321030: 385}

ANSWER_RE = re.compile(r"\b(yes|no)\b", re.IGNORECASE)
URL_RE = re.compile(
    r"https?://\S+|\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|"
    r"(?:/[A-Za-z0-9_.-]+){2,}|[A-Za-z]:\\[^\s]*")

# Vendored verbatim from round 19 through round 21 (research/nightly-2026-10-23-0200/
# surfacing_budget_curve.py, PR #93): the strict commitment rule and the echo phrase
# test. --selftest asserts the documented behaviour of both, so the rule cannot drift
# silently from the rounds whose readout this grid must stay comparable to (#94).
PHRASE_RE = re.compile(
    r"yes\s*[/|]\s*no|no\s*[/|]\s*yes|yes\s+or\s+no|no\s+or\s+yes",
    re.IGNORECASE)
STRICT_TAIL_RE = re.compile(r"[.!?:;\)\]\"'\s]*$")
VERDICT_CUE_RE = re.compile(
    r"\b(thus|therefore|so|answer|final|conclusion|answer is|verdict)\b"
    r"[^.\n]{0,30}$", re.IGNORECASE)

# Own name pools (deliberately different from generators/ladders.py and round 8;
# identical to round 21 so the E = 24 anchor holds).
POOL_A = ("ab", "ed", "ig", "ok", "ul", "ur", "yr", "ov", "ix", "ax",
          "eb", "ic", "ol", "um", "un", "ar", "er", "ir", "or", "uz")
POOL_B = ("bo", "dra", "fo", "gra", "ho", "la", "mo", "ni", "po", "sta",
          "tra", "vo", "xi", "zo", "bru", "kro", "pli", "spo", "tur", "vra")
POOL_C = ("q", "x", "z", "k", "v", "n", "r", "s", "t", "m")


def sanitize(text: str) -> str:
    return URL_RE.sub("[REDACTED]", text)


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"


def _name(rng: random.Random, taken: set) -> str:
    for _ in range(500):
        name = rng.choice(POOL_A) + rng.choice(POOL_B) + rng.choice(POOL_C)
        if name not in taken:
            taken.add(name)
            return name
    raise RuntimeError("name pool exhausted")


def gen_item(k: int, c_chains: int, seed: int) -> dict:
    """Component-isomorphic hop chain (round-8 construction as re-implemented for
    round 21, byte-compatible): C disjoint directed paths of exactly k edges over
    fresh entities; the query is (head of one path, tail of one path); yes iff both
    endpoints lie on the same path."""
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
        # "L" is the construction-lineage label inherited from round 8's arm L (the
        # load-isolated hop-chain family) and round 21's grid: it is part of the item
        # manifest, so keeping it byte-identical is what makes this round's E = 24
        # candidate pool the SAME pool round 21 archived. The dispatch arm of a record
        # is a separate field and is "F" or "X".
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
    """The matched cross-component query on the IDENTICAL fact list: same source
    (a path head), target = the tail of a different path, chosen deterministically
    from the item digest so the choice cannot depend on anything measured."""
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
    """Issue #78 acceptance criterion 1: the two queries of a pair must share every
    fact, every entity name and the fact count, and differ only in the queried
    target; both labels must be certified by an independent BFS."""
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
    if bfs_dist(f_item["facts"], f_item["query"][0]).get(f_item["query"][2]) != K_FIXED:
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
    """Permutation-calibrated leak gate, family-wise alpha over the whole battery.
    Runs on the candidate pool (and on the paired pool), never on the selected
    six."""
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
    """Selection rule fixed in advance: candidate order by seed; the first
    want_pairs GOLD-YES candidates become the arm-F members of the dispatched pairs,
    each with its deterministic cross-component arm-X variant. Every candidate and
    every derived variant passes the independent structural audit, and every
    dispatched pair passes the shared-content assertion. Returns
    (selected pairs, round-21-compatible 40-candidate pool, paired pool)."""
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
    for edges in LEVELS_E:
        c_chains = edges // K_FIXED
        pairs, pool, paired_pool = build_cell(K_FIXED, c_chains, PAIRS_PER_LEVEL)
        cells.append({"level": edges, "k": K_FIXED, "chains": c_chains,
                      "arm": "M", "pairs": pairs, "pool": pool,
                      "paired_pool": paired_pool})
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
    """Round-19 rule, vendored verbatim: last trace yes/no that could be a
    verdict. Qualifies when it is outside a "yes/no" or "yes or no" phrase and
    either closes the trace (only punctuation after it) or is both preceded by an
    answer cue within 30 characters and closed by punctuation."""
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
    """Round-19 classes for the LAST reasoning-field yes/no: instruction_echo
    (inside a yes/no phrase), terminal (last 2% of the trace), mid_trace
    (elsewhere), or None when the trace carries no yes/no."""
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
    counting over these measures how much of the output is spent enumerating facts
    the query does not need."""
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


def make_record(item: dict, arm: str, pair_seed: int, budget_cap: AttemptBudget,
                phase: int) -> dict:
    prompt = render_prompt(item)
    rec = {
        "arm": arm, "level": item["edges"], "k": item["level"],
        "chains": item["chains"], "edges": item["edges"], "seed": item["seed"],
        "pair_seed": pair_seed, "seed_hash": item["seed_hash"],
        "item_sha256": sha256_text(canonical(item)),
        "prompt_sha256": sha256_text(prompt), "prompt_chars": len(prompt),
        "gold": 1 if item["answer"] == "yes" else 0,
        "gate_hash": GATE_HASH, "phase": phase, "attempts": [],
    }
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
    # character-proportional estimate of the answer position within the WHOLE
    # completion (reasoning streams before content), for budget replay
    full = (last.get("reasoning") or "") + (last.get("content") or "")
    off = last.get("content_offset", -1)
    total = last.get("completion_tokens") or 0
    rec["est_content_answer_tokens"] = (
        round(total * (len(last.get("reasoning") or "") + off + 1) / max(len(full), 1))
        if off >= 0 and full else -1)
    return rec


def write_jsonl(path: str, rec: dict) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(canonical(rec) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def anchor_state(gate: dict) -> dict:
    """Fail-closed check of the round-21 pins, from constants only."""
    cells = {c["level"]: c for c in gate["cells"]}
    e24 = cells.get(24)
    blob_ok = e24 is not None and e24["pool_blob_sha256"] == R21_POOL_BLOB_E24
    f_prompts = set(e24["forward_prompt_sha256"]) if e24 else set()
    prompts_ok = f_prompts == set(R21_FORWARD_PROMPTS)
    return {"checked": True, "pool_blob_matches_r21": blob_ok,
            "forward_prompts_match_r21": prompts_ok,
            "expected_pool_blob_sha256": R21_POOL_BLOB_E24,
            "observed_pool_blob_sha256": e24["pool_blob_sha256"] if e24 else None,
            "expected_forward_prompts": sorted(R21_FORWARD_PROMPTS),
            "observed_forward_prompts": sorted(f_prompts),
            "r21_completion_tokens": R21_FORWARD_COMPLETION,
            "provenance": ("research/nightly-2026-10-24-0205 gate.json and raw.jsonl, "
                           "round 21, PR #95")}


def build_gate() -> dict:
    cells = all_cells()
    out = {"schema": "round22-gate-v1", "seed_base": SEED_BASE,
           "alpha": ALPHA, "perms": PERMS, "fixed_depth_k": K_FIXED,
           "levels_edges": list(LEVELS_E), "pairs_per_level": PAIRS_PER_LEVEL,
           "max_tokens": MAX_TOKENS, "temperature": TEMPERATURE,
           "readouts": ["content_only", "loose_fallback", "delivered_or_strict"],
           "matched_pair_invariant": ("identical fact list, identical entity name set, "
                                      "identical fact count, identical queried source; "
                                      "only the queried target varies (issue #78 "
                                      "acceptance criterion 1, polarity contrast)"),
           "predictions": {
               "P1_prompt_tokens_E240_over_E24_ge": 5.0,
               "P2a_levels_24_48_96_maintained_content_only": True,
               "P2b_level_240_not_maintained_content_only": True,
               "P3_completion_mean_E240_over_E24_ge": 3.0,
               "P4_forward_ok_cross_not_ok_ge_1_and_reverse_0": True,
               "P5_all_content_only_answers_correct": True,
               "P6_fallback_no_share_when_content_silent_ge": 0.6667,
               "P7_anchored_prompts_reproduce_round21_answers": True},
           "cells": []}
    for cell in cells:
        g_pool = gate_battery(cell["pool"])
        g_pairs = gate_battery(cell["paired_pool"])
        prompts = [render_prompt(it) for pair in cell["pairs"] for it in pair]
        chars = [len(p) for p in prompts]
        out["cells"].append({
            "arm": "M", "level": cell["level"], "k": cell["k"],
            "chains": cell["chains"], "edges": cell["level"],
            "load": {"facts": cell["level"],
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
    out["planned_prompts"] = 2 * PAIRS_PER_LEVEL * len(LEVELS_E)
    out["prompt_cap"] = PROMPT_CAP
    out["all_cells_pass"] = all(
        c["gate_pool"]["verdict"] != "leak" and c["gate_paired_pool"]["verdict"] != "leak"
        for c in out["cells"])
    out["anchor"] = anchor_state(out)
    out["anchor_ok"] = out["anchor"]["pool_blob_matches_r21"] and out["anchor"]["forward_prompts_match_r21"]
    return out


GATE_HASH = "unset"


def gate_hash(gate: dict) -> str:
    return sha256_text(canonical(gate))


def place_level_status(rows: list) -> dict:
    """Round-8 trichotomy per level (Wilson 95, floor 0.60), computed per readout.
    status: budget_limited (no-answer rate > 0.5) / maintained (lb >= floor) /
    collapsed (ub < floor) / inconclusive / descriptive (n < MIN_CERTIFY).
    E* = largest maintained level below the first collapsed level."""
    floor = MAJORITY_FLOOR + MARGIN
    out_rows = []
    for row in sorted(rows, key=lambda r: r["level"]):
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
        out_rows.append({"arm": "M", "level": row["level"], "n": n,
                         "correct": row["correct"], "wrong": row.get("wrong", 0),
                         "no_answer": row.get("no_answer", 0),
                         "accuracy": round(row["correct"] / n, 4) if n else 0.0,
                         "wilson_lb95": round(lb, 4), "wilson_ub95": round(ub, 4),
                         "no_answer_rate": round(na, 4), "status": status})
    collapsed = [r["level"] for r in out_rows if r["status"] == "collapsed"]
    maintained = [r["level"] for r in out_rows if r["status"] == "maintained"]
    inconclusive = [r["level"] for r in out_rows if r["status"] == "inconclusive"]
    budget_limited = [r["level"] for r in out_rows if r["status"] == "budget_limited"]
    turnover = min(collapsed) if collapsed else None
    certified = [lv for lv in maintained if turnover is None or lv < turnover]
    e_star = max(certified) if certified else None
    grid_max = max((r["level"] for r in out_rows), default=0)
    report = (f"no collapsed level within the declared grid (E <= {grid_max}); "
              f"E* >= {e_star}" if turnover is None
              else f"E* = {e_star}, first collapsed level at {turnover}")
    if inconclusive:
        report += f"; inconclusive levels {inconclusive}"
    if budget_limited:
        report += f"; budget-limited levels {budget_limited}"
    return {"e_star": e_star, "report": report, "turnover_at": turnover,
            "maintained_levels": maintained, "inconclusive_levels": inconclusive,
            "budget_limited_levels": budget_limited, "floor": floor,
            "min_certify_items": MIN_CERTIFY, "rows": out_rows}


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
    """Character-proportional estimate of the delivered answer's position inside the
    whole completion, recomputed at analysis time from the archived attempt fields
    (reasoning streams before content). Round 21's lesson: estimates stored at
    dispatch time rot, so this is derived, never read from the stored field."""
    if not r.get("attempts"):
        return -1
    a = r["attempts"][-1]
    off = a.get("content_offset", -1)
    if off < 0:
        return -1
    full = (a.get("reasoning") or "") + (a.get("content") or "")
    return round(a.get("completion_tokens", 0)
                 * (len(a.get("reasoning") or "") + off + 1) / max(len(full), 1))


def ols(points: list) -> dict:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    n = len(points)
    if n < 2:
        return {"slope": None, "intercept": None, "r": None}
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in points)
    syy = sum((y - my) ** 2 for y in ys)
    slope = (sxy / sxx) if sxx else None
    r = (sxy / math.sqrt(sxx * syy)) if (sxx and syy) else None
    return {"slope": (round(slope, 6) if slope is not None else None),
            "intercept": (round(my - slope * mx, 3) if slope is not None else None),
            "r": (round(r, 4) if r is not None else None)}


def aggregate(records: list) -> dict:
    readout_names = ("content_only", "loose_fallback", "delivered_or_strict")
    per_ro: dict = {}
    tok: dict = {}
    dis: dict = {}
    for rec in records:
        key = rec["level"]
        tok.setdefault(key, {"completion": [], "prompt": []})
        tok[key]["completion"].append(rec.get("completion_tokens", 0))
        tok[key]["prompt"].append(rec.get("prompt_tokens", 0))
        last = rec["attempts"][-1] if rec.get("attempts") else {}
        mech = last.get("mechanics") or {}
        if mech.get("distractor_entities"):
            dis.setdefault(key, []).append(mech.get("distractor_mention_ratio"))
        for name in readout_names:
            row = per_ro.setdefault((name, key), {"level": key, "n": 0, "correct": 0,
                                                  "wrong": 0, "no_answer": 0})
            row["n"] += 1
            c = rec["correct"][name]
            if c is None:
                row["no_answer"] += 1
            elif c == 1:
                row["correct"] += 1
            else:
                row["wrong"] += 1
    per_level = {}
    for name in readout_names:
        rows = [dict(row, mean_completion_tokens=round(
                    sum(tok[row["level"]]["completion"]) / len(tok[row["level"]]["completion"]), 1),
                    mean_prompt_tokens=round(
                    sum(tok[row["level"]]["prompt"]) / len(tok[row["level"]]["prompt"]), 1))
                for (nm, _), row in sorted(per_ro.items()) if nm == name]
        per_level[name] = rows
    e_star = {name: place_level_status(per_level[name]) for name in readout_names}

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

    # matched-pair analysis: every pair is one graph, arm F (gold yes) and arm X
    # (gold no); the shared content makes the polarity contrast unconfounded
    pairs = collections.defaultdict(dict)
    for rec in records:
        pairs[(rec["level"], rec["pair_seed"])][rec["arm"]] = rec
    counts = {"pairs": 0, "both_ok": 0, "f_ok_x_not": 0, "x_ok_f_not": 0,
              "both_not": 0, "both_silent": 0, "f_silent": 0, "x_silent": 0}
    per_level_pairs = {}
    for (level, _ps), pair in sorted(pairs.items()):
        f, x = pair.get("F"), pair.get("X")
        if f is None or x is None:
            continue
        counts["pairs"] += 1
        fok = f["correct"]["content_only"] == 1
        xok = x["correct"]["content_only"] == 1
        rl = per_level_pairs.setdefault(level, {"pairs": 0, "both_ok": 0,
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

    # predictions
    means = {r["level"]: r for r in per_level["content_only"]}
    p1 = None
    if means.get(24) and means.get(240) and means[24]["mean_prompt_tokens"]:
        p1 = round(means[240]["mean_prompt_tokens"] / means[24]["mean_prompt_tokens"], 4)
    low_levels = [24, 48, 96]
    # the trichotomy status lives in the classification rows, not in the token rows
    status = {r["level"]: r["status"] for r in e_star["content_only"]["rows"]}
    p2a_ok = all(status.get(lv) == "maintained" for lv in low_levels)
    top_status = status.get(240)
    p2b_ok = top_status is not None and top_status != "maintained"
    p3 = None
    if means.get(24) and means.get(240) and means[24]["mean_completion_tokens"]:
        p3 = round(means[240]["mean_completion_tokens"] / means[24]["mean_completion_tokens"], 4)
    p4_ok = counts["f_ok_x_not"] >= 1 and counts["x_ok_f_not"] == 0
    content_recs = [r for r in records if r["content_answer"] is not None]
    p5_ok = all(r["correct"]["content_only"] == 1 for r in content_recs)
    silent = [r for r in records if r["content_answer"] is None
              and r["reasoning_answer"] is not None]
    p6_share = (sum(1 for r in silent if r["reasoning_answer"] == "no") / len(silent)
                if silent else None)
    anchored = [r for r in records if r["prompt_sha256"] in R21_FORWARD_PROMPTS]
    p7_rows = []
    for r in anchored:
        p7_rows.append({"seed": r["seed"], "prompt_sha256": r["prompt_sha256"][:12],
                        "this_answer": r["content_answer"],
                        "this_completion_tokens": r["completion_tokens"],
                        "r21_completion_tokens": R21_FORWARD_COMPLETION.get(r["seed"]),
                        "r21_answer": "yes",
                        "answer_agrees": r["content_answer"] == "yes"})
    p7_ok = len(anchored) == 3 and all(row["answer_agrees"] for row in p7_rows)

    token_law = ols([(lv, means[lv]["mean_completion_tokens"])
                     for lv in sorted(means) if means[lv]["mean_completion_tokens"]])
    prompt_law = ols([(lv, means[lv]["mean_prompt_tokens"]) for lv in sorted(means)])

    # provenance of the fallback token where the answer field is silent (#94)
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
    fallback_total = sum(1 for r in records if r["reasoning_answer"] is not None)
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
        "per_level": per_level,
        "e_star": e_star,
        "per_arm": arm_stats,
        "matched_pairs": {"counts": counts, "mcnemar": mcnemar,
                          "per_level": {str(k): v for k, v in sorted(per_level_pairs.items())}},
        "token_law_completion_vs_edges": token_law,
        "token_law_prompt_vs_edges": prompt_law,
        "distractor_mention_ratio_by_level": {
            str(k): (round(sum(v) / len([x for x in v if x is not None]), 4)
                     if any(x is not None for x in v) else None)
            for k, v in sorted(dis.items())},
        "predictions": {
            "P1_prompt_tokens_E240_over_E24": p1,
            "P1_pass": (p1 is not None and p1 >= 5.0),
            "P2a_levels_24_48_96_maintained": [status.get(lv) for lv in low_levels],
            "P2a_pass": p2a_ok,
            "P2b_level_240_status": top_status,
            "P2b_pass": p2b_ok,
            "P3_completion_E240_over_E24": p3,
            "P3_pass": (p3 is not None and p3 >= 3.0),
            "P4_f_ok_x_not": counts["f_ok_x_not"],
            "P4_x_ok_f_not": counts["x_ok_f_not"],
            "P4_pass": p4_ok,
            "P5_content_answers_correct": f"{sum(1 for r in content_recs if r['correct']['content_only'] == 1)}/{len(content_recs)}",
            "P5_pass": p5_ok,
            "P6_fallback_no_share_when_content_silent": (round(p6_share, 4)
                                                         if p6_share is not None else None),
            "P6_silent_cells": len(silent),
            "P6_pass": (p6_share is not None and p6_share >= 0.6667),
            "P7_anchored_cells": len(anchored),
            "P7_rows": p7_rows,
            "P7_pass": p7_ok},
        "fallback_provenance": {
            "classes": dict(prov),
            "agreement_with_gold": {cls: prov_agree[cls] for cls in prov if cls != "no_trace_token"},
            "commit_fraction_median": (round(fractions[len(fractions) // 2], 4)
                                       if fractions else None),
            "strict_rule_on_content_silent_cells": strict_on_silent,
            "loose_fallback_when_content_silent": {
                "cells": fallback_total, "correct": fallback_correct,
                "constant_no_baseline_accuracy": round(no_baseline, 4)}},
        "budget_replay_content_only": replay,
        "totals": {
            "correct": {name: sum(1 for r in records if r["correct"][name] == 1)
                        for name in readout_names},
            "answered": {name: sum(1 for r in records
                                   if r["correct"][name] is not None)
                         for name in readout_names},
            "outcomes": dict(collections.Counter(r["outcome"] for r in records)),
            "errors": sum(1 for r in records if r["outcome"].startswith("transport_"))}}


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
        print("REFUSED: the round-21 anchor pins do not match the construction",
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
                done[(rec["arm"], rec["level"], rec["seed"])] = rec
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
            plan.append(("F", f_item, f_item["seed"]))
            plan.append(("X", x_item, f_item["seed"]))
    if len(plan) + HEALTH_CALLS > PROMPT_CAP:
        print(f"plan {len(plan)} + health exceeds cap {PROMPT_CAP}", file=sys.stderr)
        return 2
    note = {"resumed_cells": len(done), "health": health, "gate_hash": GATE_HASH}

    def run(arm: str, item: dict, pair_seed: int, phase: int) -> dict:
        rec = make_record(item, arm, pair_seed, cap, phase)
        results[(arm, item["edges"], item["seed"])] = rec
        write_jsonl(raw_path, rec)
        print(f"E={rec['level']:>3} {rec['arm']} gold={rec['gold']} "
              f"outcome={rec['outcome']:>22} content={str(rec['content_answer']):>4} "
              f"strict={str(rec['strict_trace_token']):>4} "
              f"ctok={rec['attempts'][-1]['completion_tokens']:>5}", flush=True)
        return rec

    pending = [(a, it, ps) for (a, it, ps) in plan
               if (a, it["edges"], it["seed"]) not in done]
    results = dict(done)
    started = time.monotonic()
    phase1 = pending[:2]
    for (a, it, ps) in phase1:
        run(a, it, ps, 1)
    walls = [results[(a, it["edges"], it["seed"])]["attempts"][-1]["wall_s"]
             for (a, it, ps) in phase1
             if results[(a, it["edges"], it["seed"])]["attempts"]]
    tps = max([TPS_FLOOR] + [MAX_TOKENS / w for w in walls if w and w > 0])
    remaining = pending[2:]
    est_total = len(remaining) * MAX_TOKENS / tps
    chosen = None
    for cand in CONCURRENCY_CHOICES:
        if est_total / cand * 1.25 <= PHASE2_BUDGET_S:
            chosen = cand
            break
    if chosen is None:
        chosen = max(CONCURRENCY_CHOICES)
    note.update({"phase1_walls": walls, "estimated_tokens_per_second": round(tps, 2),
                 "estimate_phase2_s": round(est_total, 1), "chosen_concurrency": chosen})
    print(f"phase-1 walls {walls} s, ~{round(tps, 1)} tok/s, concurrency {chosen} "
          f"for {len(remaining)} cells", flush=True)
    phase2_start = time.monotonic()
    to_run, abandoned = [], []
    for entry in remaining:
        if time.monotonic() > phase2_start + PHASE2_BUDGET_S:
            abandoned.append(entry)
        else:
            to_run.append(entry)
    for (a, it, ps) in abandoned:
        prompt = render_prompt(it)
        rec = {"arm": a, "level": it["edges"], "k": it["level"], "chains": it["chains"],
               "edges": it["edges"], "seed": it["seed"], "pair_seed": ps,
               "seed_hash": it["seed_hash"],
               "item_sha256": sha256_text(canonical(it)),
               "prompt_sha256": sha256_text(prompt), "prompt_chars": len(prompt),
               "gold": 1 if it["answer"] == "yes" else 0,
               "gate_hash": GATE_HASH, "phase": 2, "attempts": [],
               "completion_tokens": 0, "prompt_tokens": 0,
               "outcome": "abandoned_budget",
               "content_answer": None, "reasoning_answer": None,
               "loose_fallback_answer": None, "strict_trace_token": None,
               "delivered_or_strict_answer": None,
               "fallback_provenance_class": None,
               "fallback_commit_fraction": None,
               "est_content_answer_tokens": -1,
               "correct": {"content_only": None, "loose_fallback": None,
                           "delivered_or_strict": None}}
        results[(a, it["edges"], it["seed"])] = rec
        write_jsonl(raw_path, rec)
    if to_run:
        with concurrent.futures.ThreadPoolExecutor(max_workers=chosen) as pool:
            futures = [pool.submit(run, a, it, ps, 2) for (a, it, ps) in to_run]
            for fut in concurrent.futures.as_completed(futures):
                fut.result()
    ordered = [results[(a, it["edges"], it["seed"])] for (a, it, ps) in plan]
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
                      "e_star": {k: v["report"] for k, v in summary["e_star"].items()},
                      "matched_pairs": summary["matched_pairs"]["mcnemar"],
                      "predictions": summary["predictions"]}, indent=2))
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
        print(f"  E={c['level']:>3} k={c['k']} C={c['chains']:>2} "
              f"pool: {g['verdict']} obs={g['observed_max']} thr={g['calibrated_threshold']} "
              f"p={g['p_value']} | paired: {gp['verdict']} obs={gp['observed_max']} "
              f"thr={gp['calibrated_threshold']} p={gp['p_value']} "
              f"chars={c['load']['prompt_chars_mean']}")
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


def selftest() -> None:
    checks = 0

    def ok(cond, msg):
        nonlocal checks
        checks += 1
        assert cond, msg

    # 1. structural and solvability audit on every candidate and variant, and the
    #    matched-pair invariant on every dispatched pair
    for edges in LEVELS_E:
        c_chains = edges // K_FIXED
        pairs, pool, paired_pool = build_cell(K_FIXED, c_chains, PAIRS_PER_LEVEL)
        ok(len(pool) == CANDIDATES, f"pool size E={edges}")
        for it in pool:
            ok(not verify_item(it), f"audit E={edges} seed={it['seed']}")
        ok(len(pairs) == PAIRS_PER_LEVEL, f"pair count E={edges}")
        for (f_item, x_item) in pairs:
            ok(not verify_item(x_item), f"variant audit E={edges}")
            ok(not pair_violations(f_item, x_item), f"pair invariant E={edges}")
        ok(all(it["edges"] == edges for it in pool), f"E not as declared at {edges}")
        ok(all(it["level"] == K_FIXED for it in pool), f"k not constant at E={edges}")
        ok(len(paired_pool) == 2 * sum(1 for it in pool if it["answer"] == "yes"),
           f"paired pool size E={edges}")

    # 2. determinism: double generation byte-identical; shifted seed differs; and a
    #    variant choice recomputed twice is the same target
    def cells_blob() -> str:
        return canonical([build_cell(K_FIXED, e // K_FIXED, PAIRS_PER_LEVEL)[0]
                          for e in LEVELS_E])
    ok(cells_blob() == cells_blob(), "double generation differs")
    shifted = canonical([x_variant(gen_item(K_FIXED, 6, cell_seed(K_FIXED, 6, i) + 1000))
                         for i in range(4)])
    plain = canonical([x_variant(gen_item(K_FIXED, 6, cell_seed(K_FIXED, 6, i)))
                       for i in range(4)])
    ok(shifted != plain, "seed shift produced identical variants")
    item0 = build_cell(K_FIXED, 6, PAIRS_PER_LEVEL)[0][0][0]
    ok(canonical(x_variant(item0)) == canonical(x_variant(item0)),
       "variant selection is not deterministic")

    # 3. the load ramp is real and monotone, and depth is constant
    prompts = {e: [render_prompt(it) for pair in build_cell(K_FIXED, e // K_FIXED,
                                                            PAIRS_PER_LEVEL)[0]
                   for it in pair] for e in LEVELS_E}
    means = {e: sum(len(p) for p in ps) / len(ps) for e, ps in prompts.items()}
    ok(all(means[e] < means[e2] for e, e2 in zip(LEVELS_E, LEVELS_E[1:])),
       f"prompt length not monotone in E: {means}")
    ratio = means[LEVELS_E[-1]] / means[LEVELS_E[0]]
    ok(5.0 <= ratio <= 12.0, f"load ramp ratio out of design range: {ratio:.2f}")

    # 4. round-21 anchors (fail-closed; these constants are the whole point of the
    #    E = 24 level being the SAME construction as round 21's k = 4 level)
    gate = build_gate()
    ok(gate["anchor"]["pool_blob_matches_r21"],
       "E = 24 pool blob differs from the round-21 k = 4 archive")
    ok(gate["anchor"]["forward_prompts_match_r21"],
       "E = 24 arm-F prompts differ from the round-21 k = 4 archive")
    ok(len(gate["anchor"]["observed_forward_prompts"]) == 3, "anchor prompt count")

    # 5. gate arithmetic controls
    pairs6, pool6, _pp = build_cell(K_FIXED, 6, PAIRS_PER_LEVEL)
    n = len(pairs6)
    gold_bits = _bits([True] * n + [False] * n)
    ok(max(_acc((1 << (2 * n)) - 1, gold_bits, 2 * n),
           _acc(0, gold_bits, 2 * n)) == 0.5, "majority baseline on balanced pair set")
    ok(_acc(gold_bits, gold_bits, 2 * n) == 1.0, "perfect accuracy")
    ok(_acc(((1 << (2 * n)) - 1) ^ gold_bits, gold_bits, 2 * n) == 0.0, "inverted accuracy")

    # 6. planted-leak positive control: relabel by target < source name
    planted = [dict(it) for it in pool6]
    for it in planted:
        qs, _, qt = it["query"]
        it["answer"] = "yes" if qt < qs else "no"
        it["chain_len"] = None
    ok(gate_battery(planted)["verdict"] == "leak", "planted leak not flagged")

    # 7. a planted NON-matched pair must be caught (issue #78 control: a generator
    #    that silently stopped matching is caught rather than praised)
    pool_items = [it for it in pool6 if it["answer"] == "yes"]
    ok(len(pool_items) >= 2, "need two yes candidates for the negative control")
    mismatched = x_variant(pool_items[1])
    mismatched["facts"] = [list(f) for f in pool_items[0]["facts"]]
    ok(bool(pair_violations(pool_items[0], mismatched)),
       "cross-item pair not caught by the shared-content assertion")
    same_target = dict(pool_items[0])
    same_target["answer"] = "no"
    same_target["chain_len"] = None
    ok(bool(pair_violations(pool_items[0], same_target)),
       "identical queried target not caught")

    # 8. the real pools must not be flagged (also re-checked before probe)
    for edges in (24, 96):
        c_chains = edges // K_FIXED
        _p, pool, paired_pool = build_cell(K_FIXED, c_chains, PAIRS_PER_LEVEL)
        ok(gate_battery(pool)["verdict"] != "leak", f"real pool flagged E={edges}")
        ok(gate_battery(paired_pool)["verdict"] != "leak",
           f"paired pool flagged E={edges}")

    # 9. strict rule controls (the round-19 documented behaviours)
    ok(strict_last_trace_token("I will answer the question. Thus yes.") == "yes",
       "cued commitment 'Thus yes.' must qualify")
    ok(strict_last_trace_token("Answer exactly one word: yes or no") is None,
       "instruction echo must not qualify")
    ok(strict_last_trace_token("Check a. Check b. No other incoming. Then more text "
                               "follows about checking and it does not stop") is None,
       "mid-trace 'No other incoming.' must not qualify")
    ok(strict_last_trace_token("Enumerating links, enumerating links, and the final "
                               "answer is no") == "no", "cued trace-final 'no' must qualify")
    ok(strict_last_trace_token("") is None, "empty trace")

    # 10. provenance class controls
    cls, frac = provenance_class("answer with yes or no")
    ok(cls == "instruction_echo", "echo class")
    cls, frac = provenance_class("a" * 400 + " yes")
    ok(cls == "terminal" and frac > 0.98, "terminal class")
    cls, frac = provenance_class("x yes " + "y" * 100)
    ok(cls == "mid_trace" and frac < 0.98, "mid-trace class")
    cls, frac = provenance_class("nothing here")
    ok(cls is None, "no token class")

    # 11. readout precedence: content answer wins; strict fills only when content silent
    ro = readouts("Reasoning says no. Final: yes", "long trace thus no")
    ok(ro["content_answer"] == "yes" and ro["loose_fallback_answer"] == "yes"
       and ro["delivered_or_strict_answer"] == "yes", "content precedence")
    ro = readouts("still working on it", "checked all facts, thus no.")
    ok(ro["content_answer"] is None and ro["loose_fallback_answer"] == "no"
       and ro["delivered_or_strict_answer"] == "no", "strict fills when silent")
    ro = readouts("still working", "No other incoming. and then more words here to "
                                   "keep going and going")
    ok(ro["loose_fallback_answer"] == "no" and ro["strict_trace_token"] is None
       and ro["delivered_or_strict_answer"] is None,
       "loose reads mid-trace no, strict does not")

    # 12. retry and outcome classification controls
    ok(is_retryable("transport_TimeoutError") and is_retryable("empty_completion"),
       "retry classification")
    ok(not is_retryable("trace_only") and not is_retryable("truncated_no_answer"),
       "non-retry classification")
    att = {"error_class": None, "completion_tokens": 0, "content_answer": None,
           "reasoning_answer": None}
    ok(classify_attempt(att) == "empty_completion", "empty completion class")

    # 13. wilson, trichotomy and McNemar controls
    lb0, ub0 = wilson(0, 0)
    ok((lb0, ub0) == (0.0, 0.0), "wilson n=0")
    lb6, _ = wilson(6, 6)
    lb5, _ = wilson(5, 6)
    ok(lb6 > 0.6 > lb5, f"wilson floors 6/6={lb6:.3f} 5/6={lb5:.3f} (floor 0.60 sits between)")
    rows = [{"level": 24, "n": 6, "correct": 6, "wrong": 0, "no_answer": 0},
            {"level": 48, "n": 6, "correct": 0, "wrong": 0, "no_answer": 6},
            {"level": 96, "n": 6, "correct": 3, "wrong": 3, "no_answer": 0}]
    res = place_level_status(rows)
    statuses = {r["level"]: r["status"] for r in res["rows"]}
    ok(statuses[24] == "maintained" and statuses[48] == "budget_limited"
       and statuses[96] == "inconclusive", f"trichotomy {statuses}")
    ok(res["turnover_at"] is None, "collapsed detection needs ub < floor")
    rows2 = [{"level": 24, "n": 6, "correct": 6, "wrong": 0, "no_answer": 0},
             {"level": 48, "n": 6, "correct": 0, "wrong": 6, "no_answer": 0}]
    ok(place_level_status(rows2)["e_star"] == 24
       and place_level_status(rows2)["turnover_at"] == 48, "E* below turnover")
    ok(mcnemar_exact(0, 0) == 1.0, "mcnemar with no discordance")
    p6_0 = mcnemar_exact(6, 0)
    ok(abs(p6_0 - 0.03125) < 1e-12, f"mcnemar 6-0 must be 2/64, got {p6_0}")
    ok(abs(mcnemar_exact(9, 0) - 2.0 / 512.0) < 1e-12, "mcnemar 9-0 must be 2/512")
    ok(abs(mcnemar_exact(3, 3) - 1.0) < 1e-12, "mcnemar symmetric discordance is 1.0")

    # 14. token-law control: an exact linear ramp recovers its slope
    fit = ols([(24, 100 + 2 * 24), (48, 100 + 2 * 48), (96, 100 + 2 * 96)])
    ok(abs(fit["slope"] - 2.0) < 1e-6 and abs(fit["intercept"] - 100.0) < 1e-6
       and fit["r"] > 0.9999, f"ols control {fit}")

    # 15. distractor enumeration control: on a yes item the queried path's entities
    #     are excluded, and the count covers every other component exactly once
    f_item = pairs6[0][0]
    dis = distractor_names(f_item)
    own = {f_item["query"][0]}
    out_m = {s: t for s, _, t in f_item["facts"]}
    node = f_item["query"][0]
    for _ in range(K_FIXED):
        node = out_m[node]
        own.add(node)
    ok(len(dis) == (f_item["chains"] - 1) * (K_FIXED + 1), f"distractor count {len(dis)}")
    ok(not (set(dis) & own), "queried path counted as distractor")
    ok(len(set(dis)) == len(dis), "distractor list has duplicates")

    # 16. gold-label balance and cap arithmetic
    plan_arms = [a for e in LEVELS_E for _ in range(PAIRS_PER_LEVEL) for a in ("F", "X")]
    ok(plan_arms.count("F") == plan_arms.count("X") == 18, "arm balance")
    ok(len(plan_arms) + HEALTH_CALLS <= PROMPT_CAP, "cap arithmetic")

    print(f"selftest: {checks} checks, 0 failures")


def main(argv: list) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--out", default="gate.json")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        selftest()
        return 0
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = args.out_dir or here
    if args.gate:
        return cmd_gate(args.out if os.path.dirname(args.out) else os.path.join(out_dir, args.out))
    if args.probe:
        return probe(out_dir, args.resume)
    if args.analyze:
        return cmd_analyze(out_dir)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

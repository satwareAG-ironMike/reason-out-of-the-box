#!/usr/bin/env python3
"""Shortcut-leak audit for the compositional-ladder family (issue #67).

A generator leaks when a feature that is readable from the prompt without
performing the intended traversal predicts the gold label above chance. Issue
#67 established that the pre-fix k-hop ladder items (single chain plus
disjoint noise) leaked through two such features, both at 100% on the 1,500
shipped items (query target is a fact target; query target out-degree zero).
This module makes that measurement repeatable and enforces the acceptance
gate: a battery of surface features, a conjunction search over them, numeric
stumps, and bounded-search baselines, run against any item set.

The repaired family (implemented in ladders.py, "component isomorphism"):
every fact component is a directed path of exactly `level` edges over fresh
entities; the query is always (head of one path, tail of one path); yes iff
both endpoints lie on the same path. Under this contract every endpoint role,
degree, neighbourhood and component-length feature is constant across the two
answer classes, so no surface feature can separate them. Non-isomorphic
components (paths of differing length) re-open a leak through component
length, which the battery detects; that is why isomorphism is stated as an
invariant and not as a stylistic choice.

Gate semantics (calibrated 2026-10-16, nightly round 5, supersedes the
2026-10-15 round-4 semantics):
  - The gate is a hypothesis class: every boolean-feature literal (both
    polarities), every conjunction of up to three literals, and every numeric
    stump threshold (both directions). Hypotheses are evaluated as bitmasks
    over the item set, so the same class is scored on the real labels and on
    label permutations at no extra search cost.
  - A rule counts as a leak only if its accuracy beats the null distribution
    of the SAME statistic on the SAME corpus with the labels permuted
    (features fixed, labels shuffled, PERMUTATIONS draws). The absolute bound
    CHANCE_MAX is kept as a reported legacy floor only: on the repaired corpus
    the majority baseline alone reaches 0.5533 at level 6, so an absolute
    threshold below the majority is meaningless there, and the uncalibrated
    0.55 bound sits inside its own null band (issue #67 verification record).
  - Level 1 is a lookup control, not a depth level: `direct_fact` is the task
    itself at k=1 (a 1-hop query is derivable iff it is a stated fact), and any
    feature correlated with "the query pair co-occurs in one stated fact"
    inherits that signal. Level 1 is reported with its depth match and is never
    gated and never counted as depth evidence (issue #67 verification record,
    finding 3). Levels 2, 4, 6, 8 are the depth levels the gate applies to.
  - Instrument self-checks run on every audit: a constant rule must score
    exactly at the majority baseline, and an oracle rule that reads the gold
    label must score 1.0. If either fails the instrument is broken and the
    audit exits 4 rather than reporting a verdict.
  - Gate power is reported, not assumed: for every audited level the output
    states `min_detectable_accuracy`, the smallest rule accuracy that could
    flip the gate to FAIL on that corpus (it must beat the constant rule AND
    clear the permutation null at NULL_ALPHA), plus the null band itself. A PASS
    on a small corpus, where the bound is high, is weaker evidence than a PASS
    on a large one; the audit states its own power instead of presenting a
    vacuous verdict. The class size is reported too: a corpus where every
    gateable hypothesis is constant cannot produce a FAIL, and the audit says so.

Usage:
  audit_ladder_leaks.py --selftest
  audit_ladder_leaks.py --audit-shipped [--json]
  audit_ladder_leaks.py --audit-fixtures [--json]
  audit_ladder_leaks.py --generated [--count 300] [--seed-base N] [--json]
  (--json prints the full machine-readable report to stdout instead of one line
  per level; redirect it to the artifact file you want.)

Exit codes:
  0  audit ran clean, or selftest passed (all negative controls caught).
     For --audit-fixtures, 0 means the gate FIRED on every fixture level,
     which is the expected result for a known-leaky corpus (detection asserted).
  2  usage error
  4  a leak was detected on a gated level, or a negative control was not
     caught, or a solvability invariant failed, or an instrument self-check
     failed, or (--audit-fixtures only) the gate failed to detect the
     documented pre-fix leak
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
from collections import deque
from pathlib import Path

from ladders import CODA, ONSET, VOWEL
from ladders import generate_item as _ladders_generate_item
from ladders import generate_items as _ladders_generate_items

REPO = Path(__file__).resolve().parents[1]
FAMILY = "ladders"
TASK_TYPE = "hop_chain"
REL = "precedes"
LEVELS = (1, 2, 4, 6, 8)
# Level 1 is a lookup control (see gate semantics); only these levels are gated.
DEPTH_LEVELS = (2, 4, 6, 8)
ITEMS_PER_LEVEL = 300
SEED_BASE = 20261005
# Legacy absolute floor, reported only. The decision bound is the permutation
# null (issue #67 verification record: 0.55 sits inside the null band).
CHANCE_MAX = 0.55
PERMUTATIONS = 300
NULL_ALPHA = 0.05
# Public, date-based permutation seed base (same policy as item seeds): the
# null is reproducible from this constant alone.
PERM_SEED_BASE = 20261016
FIXTURE_DIR = REPO / "generators" / "fixtures"
FIXTURE_MANIFEST = FIXTURE_DIR / "issue67_prefix.manifest.json"

BOOL_FEATURES = (
    "tgt_is_fact_target", "tgt_is_fact_source", "tgt_outdeg_zero",
    "tgt_indeg_zero", "tgt_outdeg_one", "tgt_indeg_one",
    "src_is_fact_target", "src_is_fact_source", "src_outdeg_zero",
    "src_indeg_zero", "src_outdeg_one", "src_indeg_one",
    "tgt_in_nbr_is_fact_target", "tgt_out_nbr_is_fact_target",
    "src_out_nbr_is_fact_source", "direct_fact",
    "tgt_back_len_eq_level", "src_fwd_len_eq_level",
)
NUM_FEATURES = ("n_facts", "n_nodes", "n_heads", "n_tails",
                "tgt_back_len", "src_fwd_len")


def _entity(rng: random.Random, taken: set) -> str:
    for _ in range(200):
        name = rng.choice(ONSET) + rng.choice(VOWEL) + rng.choice(CODA)
        if name not in taken:
            taken.add(name)
            return name
    raise RuntimeError("entity pool exhausted")


def _adj(facts: list) -> tuple[dict, dict]:
    out: dict = {}
    inc: dict = {}
    for s, _, t in facts:
        out.setdefault(s, []).append(t)
        inc.setdefault(t, []).append(s)
    return out, inc


def bfs_dist(out: dict, src: str, limit: int | None = None) -> dict:
    dist = {src: 0}
    q = deque([src])
    while q:
        u = q.popleft()
        if limit is not None and dist[u] >= limit:
            continue
        for v in out.get(u, ()):
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist


def _walk_len(adj: dict, node: str, seen_guard: bool = True) -> int:
    """Length of the single directed path through `node` in a path forest."""
    length, cur, seen = 0, node, {node}
    while cur in adj:
        nxts = adj[cur]
        if len(nxts) != 1:
            return -1
        cur = nxts[0]
        if seen_guard and cur in seen:
            return -1
        seen.add(cur)
        length += 1
    return length


def features(facts: list, qs: str, qt: str, level: int) -> dict:
    out, inc = _adj(facts)
    srcs = {s for s, _, _ in facts}
    tgts = {t for _, _, t in facts}
    od_qt, id_qt = len(out.get(qt, ())), len(inc.get(qt, ()))
    od_qs, id_qs = len(out.get(qs, ())), len(inc.get(qs, ()))
    nodes = srcs | tgts
    f = {
        "tgt_is_fact_target": qt in tgts,
        "tgt_is_fact_source": qt in srcs,
        "tgt_outdeg_zero": od_qt == 0,
        "tgt_indeg_zero": id_qt == 0,
        "tgt_outdeg_one": od_qt == 1,
        "tgt_indeg_one": id_qt == 1,
        "src_is_fact_target": qs in tgts,
        "src_is_fact_source": qs in srcs,
        "src_outdeg_zero": od_qs == 0,
        "src_indeg_zero": id_qs == 0,
        "src_outdeg_one": od_qs == 1,
        "src_indeg_one": id_qs == 1,
        "direct_fact": (qs, REL, qt) in {(s, r, t) for s, r, t in facts},
        "n_facts": len(facts),
        "n_nodes": len(nodes),
        "n_heads": sum(1 for n in nodes if n not in inc),
        "n_tails": sum(1 for n in nodes if n not in out),
        "tgt_back_len": _walk_len(inc, qt),
        "src_fwd_len": _walk_len(out, qs),
    }
    f["tgt_in_nbr_is_fact_target"] = (
        id_qt == 1 and inc[qt][0] in tgts)
    f["tgt_out_nbr_is_fact_target"] = (
        od_qt == 1 and out[qt][0] in tgts)
    f["src_out_nbr_is_fact_source"] = (
        od_qs == 1 and out[qs][0] in srcs)
    f["tgt_back_len_eq_level"] = f["tgt_back_len"] == level
    f["src_fwd_len_eq_level"] = f["src_fwd_len"] == level
    return f


def _mask_of(pred, feats: list, n: int) -> int:
    """Bitmask of the items the hypothesis predicts "yes" for. Bit i is item i.

    Complements are always taken as `full ^ mask` against an n-bit field.
    `~mask` is never used: Python ints are signed and infinite-width, so
    bit_count() of a complement counts the wrong ones and silently corrupts
    accuracy (issue #67 verification record, process findings).
    """
    m = 0
    for i, f in enumerate(feats):
        if pred(f):
            m |= 1 << i
    return m


def _correct(mask: int, gold_mask: int, n: int) -> int:
    full = (1 << n) - 1
    return (full ^ (mask ^ gold_mask)).bit_count()


def hypothesis_class(feats: list, n: int) -> list[tuple[str, int]]:
    """The gateable hypothesis class as (name, bitmask) pairs.

    Literals of every boolean feature in both polarities, conjunctions of up
    to three literals, and threshold stumps on every numeric feature in both
    directions. Masks depend on the features only, never on the labels, so the
    class is built once and scored against any labelling.
    """
    full = (1 << n) - 1
    lit: dict[tuple[str, bool], int] = {}
    for name in BOOL_FEATURES:
        for val in (True, False):
            lit[(name, val)] = _mask_of(
                lambda f, name=name, val=val: f[name] == val, feats, n)
    hyps: list[tuple[str, int]] = []
    for (name, val), m in lit.items():
        hyps.append((f"{name}=={'true' if val else 'false'}", m))
    for size in (2, 3):
        for combo in itertools.combinations(BOOL_FEATURES, size):
            for signs in itertools.product((True, False), repeat=size):
                m = full
                for x, s in zip(combo, signs):
                    m &= lit[(x, s)]
                    if m == 0:
                        break
                hyps.append(
                    (" & ".join(f"{x}=={'true' if s else 'false'}"
                                for x, s in zip(combo, signs)), m))
    for name in NUM_FEATURES:
        for cut in sorted({f[name] for f in feats}):
            hyps.append((f"{name}>={cut}",
                         _mask_of(lambda f, name=name, cut=cut: f[name] >= cut,
                                  feats, n)))
            hyps.append((f"{name}<{cut}",
                         _mask_of(lambda f, name=name, cut=cut: f[name] < cut,
                                  feats, n)))
    return hyps


def _permute_labels(gold_bits: list[int], rng: random.Random) -> int:
    labels = list(gold_bits)
    rng.shuffle(labels)
    m = 0
    for i, b in enumerate(labels):
        if b:
            m |= 1 << i
    return m


def _min_detectable(maxima: list[int], const_best: int, n: int) -> int:
    """Detection power of the gate on this corpus and hypothesis class.

    Returns the smallest hit-count a surface rule would need to flip the gate to
    FAIL: it must beat the constant rule AND clear the permutation null at
    NULL_ALPHA. A rule below this bound is indistinguishable from label noise,
    so a PASS where the bound is high (small n) is weaker evidence than a PASS
    where it is low. Returns n + 1 when no hit-count, not even a perfect rule,
    would fire, which means the gate has no power on this corpus at all.
    """
    perm_n = len(maxima)
    freq = [0] * (n + 1)
    for m in maxima:
        freq[m] += 1
    ge = 0
    found = n + 1
    for h in range(n, const_best, -1):
        ge += freq[h]
        if (1 + ge) / (1 + perm_n) < NULL_ALPHA:
            found = h
        else:
            break
    return found


def audit_level(items: list[dict], level: int) -> dict:
    """Measure the battery and the calibrated gate against one level's items.

    No traversal beyond the bounded-search baselines, which are reported
    separately on purpose.
    """
    feats = []
    gold_bits = []
    for it in items:
        qs, _, qt = it["query"]
        feats.append(features(it["facts"], qs, qt, level))
        gold_bits.append(1 if it["answer"] == "yes" else 0)
    n = len(items)
    if n == 0:
        raise ValueError("empty item set")
    full = (1 << n) - 1
    gold_mask = 0
    for i, b in enumerate(gold_bits):
        if b:
            gold_mask |= 1 << i
    yes = sum(gold_bits)
    majority = max(yes, n - yes) / n

    # ---- instrument self-checks (always run, fail closed) ----
    const_best = max(_correct(0, gold_mask, n), _correct(full, gold_mask, n))
    if const_best / n != majority:
        raise RuntimeError(f"control failed: constant rule {const_best / n} "
                           f"!= majority {majority}")
    if _correct(gold_mask, gold_mask, n) != n:
        raise RuntimeError("control failed: oracle rule is not 1.0")

    # ---- single-feature view (kept for continuity with issue #67) ----
    def acc(pred) -> float:
        return sum(1 for f, g in zip(feats, gold_bits) if pred(f) == bool(g)) / n

    single = {name: acc(lambda f, name=name: f[name]) for name in BOOL_FEATURES}
    const = [name for name in BOOL_FEATURES
             if len({f[name] for f in feats}) == 1]
    exempt = {"direct_fact"} if level == 1 else set()
    depth_match = {name: single[name] for name in exempt}
    legacy_leaks = {name: single[name] for name in BOOL_FEATURES
                    if name not in const and name not in exempt
                    and single[name] > CHANCE_MAX}

    # ---- hypothesis class, built once, scored against real and permuted labels
    hyps = hypothesis_class(feats, n)
    masks = [m for _, m in hyps]
    distinct = sorted(set(masks))
    nonconst = [m for m in distinct if m not in (0, full)]
    obs_best_name, obs_best = "", -1
    for name, m in hyps:
        c = _correct(m, gold_mask, n)
        if c > obs_best or (c == obs_best and name < obs_best_name):
            obs_best, obs_best_name = c, name
    best_nonconst_name, best_nonconst = "", -1
    for name, m in hyps:
        if m in (0, full):
            continue
        c = _correct(m, gold_mask, n)
        if c > best_nonconst or (c == best_nonconst and name < best_nonconst_name):
            best_nonconst, best_nonconst_name = c, name

    rng = random.Random(PERM_SEED_BASE + level)
    maxima = []
    for _ in range(PERMUTATIONS):
        gm = _permute_labels(gold_bits, rng)
        maxima.append(max(_correct(m, gm, n) for m in distinct))
    ge = sum(1 for x in maxima if x >= best_nonconst)
    p_value = (1 + ge) / (1 + PERMUTATIONS)
    maxima_sorted = sorted(maxima)

    def pct(p: float) -> int:
        return maxima_sorted[min(len(maxima_sorted) - 1, int(p * len(maxima_sorted)))]

    gated = level in DEPTH_LEVELS
    if gated:
        beats_null = p_value < NULL_ALPHA
        beats_majority = best_nonconst > const_best
        status = "leak" if (beats_null and beats_majority) else "no_leak"
    else:
        status = "lookup_control_not_gated"

    # ---- bounded-search baselines (the intended traversal, truncated) ----
    bounded: dict[int, float] = {}
    for d in (1, 2, 3):
        hits = 0
        for it, g in zip(items, gold_bits):
            qs, _, qt = it["query"]
            out, _ = _adj(it["facts"])
            hits += (qt in bfs_dist(out, qs, limit=d)) == bool(g)
        bounded[d] = hits / n

    numeric_stumps = {}
    for name in NUM_FEATURES:
        vals = sorted({f[name] for f in feats})
        best = 0.0
        for cut in vals:
            best = max(best, acc(lambda f, name=name, cut=cut: f[name] >= cut),
                       acc(lambda f, name=name, cut=cut: f[name] < cut))
        numeric_stumps[name] = best

    return {
        "level": level,
        "level_role": "lookup_control" if level not in DEPTH_LEVELS else "depth",
        "gated": gated,
        "n": n,
        "gold_yes": yes,
        "majority_baseline": round(majority, 4),
        "constant_rule_accuracy": round(const_best / n, 4),
        "oracle_rule_accuracy": round(_correct(gold_mask, gold_mask, n) / n, 4),
        "constant_features": sorted(const),
        "depth_match_features": {k: round(v, 4) for k, v in depth_match.items()},
        "single_feature_accuracy": {k: round(v, 4) for k, v in single.items()},
        "legacy_threshold_leaks": {k: round(v, 4) for k, v in legacy_leaks.items()},
        "hypotheses_total": len(hyps),
        "hypotheses_distinct_masks": len(distinct),
        "hypotheses_non_constant": len(nonconst),
        "gate_power_status": "measured" if nonconst else "none_all_hypotheses_constant",
        "min_detectable_accuracy": round(_min_detectable(maxima, const_best, n) / n, 4),
        "best_constant_accuracy": round(const_best / n, 4),
        "best_hypothesis": best_nonconst_name,
        "best_hypothesis_accuracy": round(best_nonconst / n, 4),
        "permutations": PERMUTATIONS,
        "permutation_seed_base": PERM_SEED_BASE,
        "null_median_accuracy": round(pct(0.50) / n, 4),
        "null_p95_accuracy": round(pct(0.95) / n, 4),
        "null_max_accuracy": round(max(maxima) / n, 4),
        "permutation_p_value": round(p_value, 4),
        "gate_status": status,
        "numeric_stump_accuracy": {k: round(v, 4) for k, v in numeric_stumps.items()},
        "bounded_search_accuracy": {str(k): round(v, 4) for k, v in bounded.items()},
    }


def shipped_items(level: int) -> list[dict]:
    path = REPO / "items" / FAMILY / f"l{level}.jsonl"
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def fixture_items(level: int) -> list[dict]:
    """Pinned pre-fix items (issue #67 negative-control fixture).

    Extracted from the shipped corpus at commit 49ee823 (the last commit whose
    items carry the leak) by fixed-stride sampling, so the before/after
    comparison in issue #67 is testable from the tree without checking out
    history. See generators/fixtures/issue67_prefix.manifest.json.
    """
    path = FIXTURE_DIR / f"issue67_prefix_l{level}.jsonl"
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


# The audit measures the generator that actually ships (single source of
# truth): ladders.py implements the component-isomorphic construction. The
# thin aliases below keep the historical call sites stable while ensuring the
# battery, solvability check, and negative controls all run against the real
# item contract (no drift between a copied constructor and the shipped one).
def candidate_item(level: int, seed: int) -> dict:
    """The component-isomorphic item as produced by the shipped generator."""
    return _ladders_generate_item(level, seed)


def candidate_items(level: int, count: int, seed_base: int) -> list[dict]:
    return _ladders_generate_items(level, count, seed_base)


def check_solvability(items: list[dict], level: int) -> dict:
    """Independent BFS: yes items must have shortest path exactly `level`,
    no items must be unreachable. Returns counts of violations."""
    bad_answer = bad_depth = bad_unreach = 0
    for it in items:
        qs, _, qt = it["query"]
        out, _ = _adj(it["facts"])
        dist = bfs_dist(out, qs)
        reachable = qt in dist
        if (it["answer"] == "yes") != reachable:
            bad_answer += 1
        elif reachable and dist[qt] != level:
            bad_depth += 1
        elif not reachable and it["chain_len"] is not None:
            bad_unreach += 1
    return {"answer_vs_bfs": bad_answer, "depth_off_by_level": bad_depth,
            "chain_len_mismatch": bad_unreach, "n": len(items)}


def run_audit(gen, label: str, count: int, as_json: bool,
              levels: tuple[int, ...] = LEVELS,
              expect_leak: bool = False) -> int:
    report = {"mode": label, "expect_leak": expect_leak,
              "chance_max_legacy": CHANCE_MAX,
              "null_alpha": NULL_ALPHA, "permutations": PERMUTATIONS,
              "levels": []}
    fail = 0
    for level in levels:
        items = gen(level, count)
        solv = check_solvability(items, level)
        rep = audit_level(items, level)
        rep["solvability"] = solv
        report["levels"].append(rep)
        solv_bad = sum(v for k, v in solv.items() if k != "n")
        if solv_bad:
            fail = 4
        leak = rep["gated"] and rep["gate_status"] == "leak"
        if expect_leak:
            # The fixture audit asserts detection power: a fixture level that
            # does NOT fire the gate means the gate is too weak to be trusted.
            if not leak:
                fail = 4
        elif leak:
            fail = 4
        if not as_json:
            print(f"[{label}] level {level} ({rep['level_role']}): "
                  f"n={rep['n']} gold_yes={rep['gold_yes']} "
                  f"majority={rep['majority_baseline']:.4f} "
                  f"best={rep['best_hypothesis_accuracy']:.4f} "
                  f"({rep['best_hypothesis']}) "
                  f"null_p95={rep['null_p95_accuracy']:.4f} "
                  f"null_max={rep['null_max_accuracy']:.4f} "
                  f"p={rep['permutation_p_value']:.4f} "
                  f"gate={rep['gate_status']} "
                  f"min_detectable={rep['min_detectable_accuracy']:.4f} "
                  f"const={len(rep['constant_features'])}/{len(BOOL_FEATURES)} "
                  f"depth_match={rep['depth_match_features']} "
                  f"solv_bad={solv_bad}")
    if as_json:
        print(json.dumps(report, sort_keys=True))
    return fail


# ---------------- negative controls (seeded defects) ----------------

def _defect_dead_node(level: int, seed: int) -> dict:
    """Seeded defect: the no-item query target becomes a bare fact source
    (the shipped mechanism from issue #67). Solvability stays valid, so only
    the battery can catch it."""
    item = candidate_item(level, seed)
    if item["answer"] == "no":
        rng = random.Random(seed + 1)
        taken = {f[0] for f in item["facts"]} | {f[2] for f in item["facts"]}
        dead = _entity(rng, taken)
        other = _entity(rng, taken)
        item["facts"].append([dead, REL, other])
        item["query"] = [item["query"][0], REL, dead]
        item["chain_len"] = None
    return item


def selftest() -> int:
    ok = 0
    # control 1: the repaired family must be solvable and leak-free under the
    # calibrated gate
    items = candidate_items(4, 120, 991)
    solv = check_solvability(items, 4)
    if any(v for k, v in solv.items() if k != "n"):
        print("FAIL control 1: solvability", solv)
        return 4
    rep = audit_level(items, 4)
    if rep["gate_status"] != "no_leak":
        print("FAIL control 1: gate verdict", rep["gate_status"],
              rep["best_hypothesis"], rep["best_hypothesis_accuracy"],
              rep["permutation_p_value"])
        return 4
    ok += 1

    # control 2: planted leak (no-item target is a bare fact source, the
    # shipped issue #67 mechanism) must be caught by the calibrated gate
    planted = [_defect_dead_node(4, 991 + i) for i in range(120)]
    rep2 = audit_level(planted, 4)
    if rep2["gate_status"] != "leak":
        print("FAIL control 2: planted leak not caught",
              rep2["best_hypothesis"], rep2["best_hypothesis_accuracy"],
              rep2["permutation_p_value"])
        return 4
    ok += 1

    # control 3: shuffled gold labels must be caught by the solvability check
    shuffled = [dict(it, answer="no" if it["answer"] == "yes" else "yes")
                for it in candidate_items(2, 60, 7)]
    solv3 = check_solvability(shuffled, 2)
    if solv3["answer_vs_bfs"] == 0:
        print("FAIL control 3: shuffled labels not caught")
        return 4
    ok += 1

    # control 4: off-by-one n (dropped item) must be visible in the count
    short = candidate_items(1, 59, 11)
    if len(short) >= 60 or audit_level(short, 1)["n"] != 59:
        print("FAIL control 4: off-by-one n not caught")
        return 4
    ok += 1

    # control 5: a cross edge that makes a no item reachable must be caught
    items5 = candidate_items(2, 40, 13)
    for it in items5:
        if it["answer"] == "no":
            it["facts"].append([it["query"][0], REL, it["query"][2]])
            break
    solv5 = check_solvability(items5, 2)
    if solv5["answer_vs_bfs"] == 0:
        print("FAIL control 5: planted cross edge not caught")
        return 4
    ok += 1

    # control 6: determinism of the candidate generator
    a = [json.dumps(i, sort_keys=True) for i in candidate_items(6, 30, 21)]
    b = [json.dumps(i, sort_keys=True) for i in candidate_items(6, 30, 21)]
    c = [json.dumps(i, sort_keys=True) for i in candidate_items(6, 30, 22)]
    if a != b or a == c:
        print("FAIL control 6: candidate generator not deterministic or seed-insensitive")
        return 4
    ok += 1

    # control 7: non-isomorphic components must leak through component length
    def ragged(level: int, seed: int) -> dict:
        it = candidate_item(level, seed)
        if it["answer"] == "no":
            rng = random.Random(seed + 5)
            taken = {f[0] for f in it["facts"]} | {f[2] for f in it["facts"]}
            it["facts"].append([_entity(rng, taken), REL, it["query"][2]])
        return it
    rep7 = audit_level([ragged(4, 991 + i) for i in range(120)], 4)
    if rep7["gate_status"] != "leak":
        print("FAIL control 7: ragged components not caught",
              rep7["best_hypothesis"], rep7["best_hypothesis_accuracy"],
              rep7["permutation_p_value"])
        return 4
    ok += 1

    # control 8: the pinned pre-fix corpus (issue #67 fixture) must be detected
    # as a leak by the calibrated gate at every fixture level, at the accuracy
    # the issue #67 claim states. This is the gate's detection power, measured
    # from the tree rather than from a scratch re-implementation.
    for level in (2, 8):
        rep8 = audit_level(fixture_items(level), level)
        if rep8["gate_status"] != "leak" or rep8["best_hypothesis_accuracy"] < 0.99:
            print(f"FAIL control 8: pre-fix fixture l{level} not detected",
                  rep8["gate_status"], rep8["best_hypothesis"],
                  rep8["best_hypothesis_accuracy"], rep8["permutation_p_value"])
            return 4
    ok += 1

    # control 9: the shipped repaired corpus must pass the calibrated gate at
    # every depth level (false-positive control on the real corpus)
    for level in DEPTH_LEVELS:
        rep9 = audit_level(shipped_items(level), level)
        if rep9["gate_status"] != "no_leak":
            print(f"FAIL control 9: shipped l{level} flagged",
                  rep9["gate_status"], rep9["best_hypothesis"],
                  rep9["best_hypothesis_accuracy"], rep9["permutation_p_value"])
            return 4
    ok += 1

    # control 10: the instrument self-checks must fail closed. A corpus whose
    # labels are constant must still report the constant rule at the majority
    # baseline, and the gate must report no leak (there is no signal to find).
    flat = [dict(it, answer="yes") for it in candidate_items(2, 40, 17)]
    rep10 = audit_level(flat, 2)
    if rep10["gate_status"] != "no_leak" or rep10["oracle_rule_accuracy"] != 1.0:
        print("FAIL control 10: constant-label corpus mishandled",
              rep10["gate_status"], rep10["constant_rule_accuracy"],
              rep10["oracle_rule_accuracy"])
        return 4
    ok += 1

    print(f"selftest passed ({ok} controls)")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--audit-shipped", action="store_true")
    p.add_argument("--audit-fixtures", action="store_true",
                   help="audit the pinned pre-fix issue #67 fixture (expect leaks)")
    p.add_argument("--generated", action="store_true")
    p.add_argument("--count", type=int, default=ITEMS_PER_LEVEL)
    p.add_argument("--seed-base", type=int, default=SEED_BASE)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.audit_shipped:
        return run_audit(lambda level, count: shipped_items(level), "shipped",
                         0, args.json)
    if args.audit_fixtures:
        # Exit 0 asserts the gate FIRES on the known-leaky pre-fix corpus;
        # exit 4 means the gate failed to detect a documented leak.
        return run_audit(lambda level, count: fixture_items(level), "prefix_fixture",
                         0, args.json, levels=(2, 8), expect_leak=True)
    if args.generated:
        return run_audit(lambda level, count: candidate_items(level, count, args.seed_base),
                         "generated", args.count, args.json)
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

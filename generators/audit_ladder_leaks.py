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

Gate semantics (refined 2026-10-15, round 4):
  - a feature that is constant across an item set carries no label
    information; its accuracy is the sample's label imbalance, not a leak.
    Constant features are reported, never gated.
  - at level 1 the feature `direct_fact` is the task itself (a 1-hop query is
    derivable iff it is a stated fact; identical to the d=1 bounded search).
    It is reported as a depth match, never gated.
  - everything else is gated: a non-constant feature (or a conjunction
    containing a non-constant feature) that predicts gold above CHANCE_MAX is
    a leak.

Usage:
  audit_ladder_leaks.py --selftest
  audit_ladder_leaks.py --audit-shipped [--json OUT]
  audit_ladder_leaks.py --generated [--count 300] [--seed-base N] [--json OUT]

Exit codes:
  0  audit ran clean, or selftest passed (all negative controls caught)
  2  usage error
  4  a leak was detected above the acceptance bound, or a negative control was
     not caught, or a solvability invariant failed
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
ITEMS_PER_LEVEL = 300
SEED_BASE = 20261005
# Acceptance bound from issue #67: no surface rule may predict gold above this.
CHANCE_MAX = 0.55

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


def audit_level(items: list[dict], level: int) -> dict:
    """Measure the battery against one level's items. No traversal beyond the
    bounded-search baselines, which are reported separately on purpose."""
    rows = []
    for it in items:
        qs, _, qt = it["query"]
        gold = it["answer"] == "yes"
        rows.append((features(it["facts"], qs, qt, level), gold))
    n = len(rows)
    yes = sum(1 for _, g in rows if g)
    majority = max(yes, n - yes) / n

    def acc(pred) -> float:
        return sum(1 for f, g in rows if pred(f) == g) / n

    # single-feature accuracy: predict gold == feature value (a constant-true
    # feature therefore scores at the majority baseline, not above it)
    single = {name: acc(lambda f, name=name: f[name]) for name in BOOL_FEATURES}
    const = [name for name in BOOL_FEATURES
             if len({f[name] for f, _ in rows}) == 1]
    # level-1 depth match: a 1-hop query is derivable iff it is a stated
    # fact, so `direct_fact` is the d=1 bounded search (the task itself), not
    # a shortcut; reported, never gated
    exempt = {"direct_fact"} if level == 1 else set()
    # gate: only non-constant, non-exempt hypotheses can be leaks; a constant
    # feature's accuracy is the sample's label imbalance, not information
    gated_features = [name for name in BOOL_FEATURES
                      if name not in const and name not in exempt]
    leaked = {name: single[name]
              for name in gated_features if single[name] > CHANCE_MAX}
    depth_match = {name: single[name] for name in exempt}

    best_conj, best_conj_acc = None, 0.0
    gated_conj, gated_conj_acc = None, 0.0
    for size in (1, 2, 3):
        for combo in itertools.combinations(BOOL_FEATURES, size):
            # a conjunction of only constant/exempt features carries no
            # information beyond those (constant) features: not gateable
            gateable = any(x in gated_features for x in combo)
            # conjunction of (feature == value) literals, value chosen per combo
            for signs in itertools.product((True, False), repeat=size):
                pred = acc(lambda f, c=combo, s=signs: all(f[x] == s_i for x, s_i in zip(c, s)))
                if pred > best_conj_acc:
                    best_conj_acc = pred
                    best_conj = tuple(
                        (x, "true" if s_i else "false")
                        for x, s_i in zip(combo, signs))
                if gateable and pred > gated_conj_acc:
                    gated_conj_acc = pred
                    gated_conj = tuple(
                        (x, "true" if s_i else "false")
                        for x, s_i in zip(combo, signs))
    stumps = {}
    for name in NUM_FEATURES:
        vals = sorted({f[name] for f, _ in rows})
        best = 0.0
        for cut in vals:
            best = max(best, acc(lambda f, name=name, cut=cut: f[name] >= cut),
                       acc(lambda f, name=name, cut=cut: f[name] < cut))
        stumps[name] = best

    bounded: dict[int, float] = {}
    for d in (1, 2, 3):
        hits = 0
        for it, (_, gold) in zip(items, rows):
            qs, _, qt = it["query"]
            out, _ = _adj(it["facts"])
            hits += (qt in bfs_dist(out, qs, limit=d)) == gold
        bounded[d] = hits / n

    return {
        "level": level,
        "n": n,
        "gold_yes": yes,
        "majority_baseline": round(majority, 4),
        "constant_features": sorted(const),
        "depth_match_features": {k: round(v, 4) for k, v in depth_match.items()},
        "single_feature_accuracy": {k: round(v, 4) for k, v in single.items()},
        "leaked_single_features": {k: round(v, 4) for k, v in leaked.items()},
        "best_conjunction": best_conj,
        "best_conjunction_accuracy": round(best_conj_acc, 4),
        "gated_conjunction": gated_conj,
        "gated_conjunction_accuracy": round(gated_conj_acc, 4),
        "numeric_stump_accuracy": {k: round(v, 4) for k, v in stumps.items()},
        "bounded_search_accuracy": {str(k): round(v, 4) for k, v in bounded.items()},
    }


def shipped_items(level: int) -> list[dict]:
    path = REPO / "items" / FAMILY / f"l{level}.jsonl"
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


def run_audit(gen, label: str, count: int, as_json: bool) -> int:
    report = {"mode": label, "chance_max": CHANCE_MAX, "levels": []}
    fail = 0
    for level in LEVELS:
        items = gen(level, count)
        solv = check_solvability(items, level)
        rep = audit_level(items, level)
        rep["solvability"] = solv
        report["levels"].append(rep)
        solv_bad = sum(v for k, v in solv.items() if k != "n")
        if solv_bad:
            fail = 4
        if rep["leaked_single_features"]:
            fail = fail or 4
        if rep["gated_conjunction_accuracy"] > CHANCE_MAX:
            fail = fail or 4
        if not as_json:
            print(f"[{label}] level {level}: n={rep['n']} "
                  f"gold_yes={rep['gold_yes']} "
                  f"majority={rep['majority_baseline']:.4f} "
                  f"gated_conj={rep['gated_conjunction_accuracy']:.4f} "
                  f"{rep['gated_conjunction']} "
                  f"depth_match={rep['depth_match_features']} "
                  f"leaks={len(rep['leaked_single_features'])} "
                  f"solv_bad={solv_bad}")
            for name, val in sorted(rep["leaked_single_features"].items()):
                print(f"    LEAK {name} accuracy={val:.4f}")
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
    # control 1: the repaired family must be solvable and leak-free
    items = candidate_items(4, 120, 991)
    solv = check_solvability(items, 4)
    if any(v for k, v in solv.items() if k != "n"):
        print("FAIL control 1: solvability", solv)
        return 4
    rep = audit_level(items, 4)
    if rep["leaked_single_features"] or rep["gated_conjunction_accuracy"] > CHANCE_MAX:
        print("FAIL control 1: leaks", rep["leaked_single_features"],
              rep["gated_conjunction"])
        return 4
    ok += 1

    # control 2: planted leak (no-item target is a bare fact source, the
    # shipped issue #67 mechanism) must be caught by the battery
    planted = [_defect_dead_node(4, 991 + i) for i in range(120)]
    rep2 = audit_level(planted, 4)
    if (not rep2["leaked_single_features"]
            and rep2["gated_conjunction_accuracy"] <= CHANCE_MAX):
        print("FAIL control 2: planted leak not caught")
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
    if (not rep7["leaked_single_features"]
            and rep7["gated_conjunction_accuracy"] <= CHANCE_MAX):
        print("FAIL control 7: ragged components not caught")
        return 4
    ok += 1

    print(f"selftest passed ({ok} controls)")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--audit-shipped", action="store_true")
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
    if args.generated:
        return run_audit(lambda level, count: candidate_items(level, count, args.seed_base),
                         "generated", args.count, args.json)
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Surface-feature battery for the ladder corpora: is the answer readable without
following the directed chain?

The leak gate in generators/audit_ladder_leaks.py audits 18 single-endpoint
features (in/out degree, whether the endpoint is a fact source or target, and so
on). That class says nothing about entity names, about the order the facts are
listed in, or about the relation between the two query endpoints. This battery
covers those three channels, because they are the channels a language model can
read off a prompt without running a search.

Feature classes:
  traversal_free  computed from entity names and their positions in the fact list
                  alone: name length, alphabetical rank, first and last letter,
                  shared prefixes, which line first mentions each endpoint. No
                  graph structure is used. A model can apply these by reading.
  structural      computed from the fact graph: which connected component each
                  query endpoint belongs to, and the index of that component.
                  Clustering the facts is a computation, but it is not directed
                  chain traversal, and its cost does not scale with the hop count
                  k, so a corpus solvable this way is not a depth ladder.

For every feature the script reports accuracy and balanced accuracy against the
gold label over the whole corpus, the two-sided binomial probability of reaching
that hit count by chance under a balanced label assignment, and the
Bonferroni-corrected threshold for the battery.

Usage:
  python3 runs/nightly-2026-10-16-0200/name_channel_audit.py                 # JSON
  python3 runs/nightly-2026-10-16-0200/name_channel_audit.py --selftest      # controls
Exit codes:
  0  no feature clears the corrected threshold
  4  a traversal-free feature clears it (a name or position shortcut exists)
  5  a structural feature reproduces the label (a structural shortcut exists)
"""
from __future__ import annotations

import json
import random
import sys
from collections import deque
from math import comb
from pathlib import Path

RUN_DIR = Path(__file__).resolve().parent
REPO = RUN_DIR.parents[1]
LEVELS = (2, 4, 6, 8)
# The pinned issue #67 fixtures exist at the two probed depths only.
CORPUS_LEVELS = {"shipped": LEVELS, "fixtures": (2, 8)}
ALPHA = 0.05
STRUCTURAL_REPRO = 0.9  # accuracy at or above this reproduces the label in practice

VOWELS = frozenset("aeiou")


# ---------------- corpora ----------------

def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def corpus_items(kind: str, level: int) -> list[dict]:
    if kind == "fixtures":
        return load_jsonl(REPO / "generators" / "fixtures" / f"issue67_prefix_l{level}.jsonl")
    return load_jsonl(REPO / "items" / "ladders" / f"l{level}.jsonl")


# ---------------- structural ground work ----------------

def components(facts: list[list[str]]) -> tuple[dict[str, int], int]:
    """Connected components of the undirected fact graph, components ordered by
    their lexicographically smallest member. Iterative BFS, no recursion."""
    adj: dict[str, set[str]] = {}
    for src, _, tgt in facts:
        adj.setdefault(src, set()).add(tgt)
        adj.setdefault(tgt, set()).add(src)
    roots = sorted(min(comp) for comp in _component_sets(adj))
    seen: set[str] = set()
    comp_of: dict[str, int] = {}
    for cid, root in enumerate(roots):
        queue = deque([root])
        while queue:
            node = queue.popleft()
            if node in seen:
                continue
            seen.add(node)
            comp_of[node] = cid
            queue.extend(adj[node] - seen)
    return comp_of, len(roots)


def _component_sets(adj: dict[str, set[str]]) -> list[set[str]]:
    seen: set[str] = set()
    out: list[set[str]] = []
    for start in adj:
        if start in seen:
            continue
        comp: set[str] = set()
        queue = deque([start])
        while queue:
            node = queue.popleft()
            if node in seen:
                continue
            seen.add(node)
            comp.add(node)
            queue.extend(adj[node] - seen)
        out.append(comp)
    return out


# ---------------- features ----------------

def first_mention(names_in_order: list[str], name: str) -> int:
    return names_in_order.index(name) if name in names_in_order else -1


def traversal_free_features(item: dict) -> dict[str, bool]:
    """Features readable from the prompt text alone: entity names and the order
    the fact lines are listed in. No adjacency, no search."""
    qs, _, qt = item["query"]
    facts = item["facts"]
    names = [name for fact in facts for name in (fact[0], fact[2])]
    lengths = [len(n) for n in names]
    order: list[str] = []
    for fact in facts:
        for name in (fact[0], fact[2]):
            if name not in order:
                order.append(name)
    lo, hi = min(names), max(names)
    out = {
        "src_name_len_eq_tgt_len": len(qs) == len(qt),
        "src_name_len_gt_tgt_len": len(qs) > len(qt),
        "src_name_len_is_max": len(qs) == max(lengths),
        "tgt_name_len_is_max": len(qt) == max(lengths),
        "src_name_len_is_min": len(qs) == min(lengths),
        "tgt_name_len_is_min": len(qt) == min(lengths),
        "src_is_alphabetically_first": qs == lo,
        "tgt_is_alphabetically_first": qt == lo,
        "src_is_alphabetically_last": qs == hi,
        "tgt_is_alphabetically_last": qt == hi,
        "src_sorts_before_tgt": qs < qt,
        "src_first_letter_vowel": qs[0] in VOWELS,
        "tgt_first_letter_vowel": qt[0] in VOWELS,
        "src_last_letter_eq_tgt_last_letter": qs[-1] == qt[-1],
        "src_shares_prefix3_with_a_fact_source": any(f[0][:3] == qs[:3] for f in facts if f[0] != qs),
        "src_first_mention_index_lt_tgt_first_mention_index":
            first_mention(order, qs) < first_mention(order, qt),
    }
    return out


def structural_features(item: dict) -> dict[str, bool]:
    """Features that need the fact graph clustered. Not directed chain traversal."""
    qs, _, qt = item["query"]
    comp_of, n_comp = components(item["facts"])
    cs, ct = comp_of.get(qs, -1), comp_of.get(qt, -1)
    return {
        "same_component": cs == ct,
        "src_component_index_lt_tgt_component_index": cs < ct,
        "src_component_index_gt_tgt_component_index": cs > ct,
        "src_component_index_is_zero": cs == 0,
        "tgt_component_index_is_last": ct == n_comp - 1,
    }


# ---------------- statistics ----------------

def binom_two_sided(n: int, hits: int) -> float:
    """P(|K - n/2| >= |hits - n/2|) for K ~ Binomial(n, 1/2), exact."""
    def tail_ge(k: int) -> float:
        return sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n

    def tail_le(k: int) -> float:
        return sum(comb(n, i) for i in range(0, k + 1)) / 2 ** n

    if hits * 2 == n:
        return 1.0
    if hits * 2 > n:
        p = tail_ge(hits)
    else:
        p = tail_le(hits)
    return min(1.0, 2.0 * p)


def balanced_accuracy(preds: list[str], golds: list[str]) -> float:
    classes = sorted(set(golds))
    per = []
    for c in classes:
        tot = sum(1 for g in golds if g == c)
        hit = sum(1 for p, g in zip(preds, golds) if g == c and p == c)
        per.append(hit / tot)
    return sum(per) / len(per)


def score(items: list[dict], feats: dict[str, list[bool]]) -> dict[str, dict]:
    golds = [it["answer"] for it in items]
    n = len(items)
    out: dict[str, dict] = {}
    for name, values in feats.items():
        preds = ["yes" if v else "no" for v in values]
        hits = sum(1 for p, g in zip(preds, golds) if p == g)
        out[name] = {
            "accuracy": round(hits / n, 4),
            "balanced_accuracy": round(balanced_accuracy(preds, golds), 4),
            "hits": hits,
            "n": n,
            "p_value": round(binom_two_sided(n, hits), 6),
            "true_count": sum(1 for v in values if v),
        }
    return out


def audit_level(kind: str, level: int) -> dict:
    items = corpus_items(kind, level)
    tf: dict[str, list[bool]] = {}
    st: dict[str, list[bool]] = {}
    for it in items:
        for name, val in traversal_free_features(it).items():
            tf.setdefault(name, []).append(val)
        for name, val in structural_features(it).items():
            st.setdefault(name, []).append(val)
    n_features = len(tf) + len(st)
    threshold = round(ALPHA / n_features, 6)
    scores_tf = score(items, tf)
    scores_st = score(items, st)
    flagged_tf = sorted(k for k, v in scores_tf.items() if v["p_value"] <= threshold)
    repro_st = sorted(k for k, v in scores_st.items() if v["accuracy"] >= STRUCTURAL_REPRO)
    return {
        "level": level,
        "n": len(items),
        "gold_yes": sum(1 for it in items if it["answer"] == "yes"),
        "features_total": n_features,
        "bonferroni_threshold": threshold,
        "traversal_free": scores_tf,
        "structural": scores_st,
        "flagged_traversal_free": flagged_tf,
        "structural_reproduces_label": repro_st,
        "max_traversal_free_accuracy": max(v["accuracy"] for v in scores_tf.values()),
        "max_structural_accuracy": max(v["accuracy"] for v in scores_st.values()),
    }


def audit(kind: str) -> dict:
    levels = [audit_level(kind, lv) for lv in CORPUS_LEVELS[kind]]
    any_flag = sorted({f for lv in levels for f in lv["flagged_traversal_free"]})
    any_repro = sorted({f for lv in levels for f in lv["structural_reproduces_label"]})
    return {
        "corpus": kind,
        "levels": levels,
        "any_traversal_free_leak": any_flag,
        "any_structural_shortcut": any_repro,
        "reading": ("no traversal-free feature clears the corrected threshold at any level"
                    if not any_flag else
                    "traversal-free shortcut present: " + ", ".join(any_flag)),
    }


def verdict(result: dict) -> int:
    if result["any_traversal_free_leak"]:
        return 4
    if result["any_structural_shortcut"]:
        return 5
    return 0


# ---------------- selftest: planted-defect control ----------------

def selftest() -> int:
    """Plant a name-channel leak and a structural leak and assert the battery
    reports both, then assert it reports neither on shuffled labels."""
    failures: list[str] = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    # control 1: a planted name leak must be flagged as traversal-free
    # The planted corpus must be label-balanced, otherwise a constant feature scores
    # 1.0 against a constant label vector and the shuffle control tests nothing.
    planted = []
    for i in range(200):
        qs = "a" * (6 - 2 * (i % 2))
        qt = "b" * (3 + 2 * (i % 2))
        answer = "yes" if len(qs) > len(qt) else "no"
        facts = [[f"n{j}", "precedes", f"m{j}"] for j in range(4)]
        facts[0] = [qs, "precedes", "zz1"]
        facts[1] = ["zz2", "precedes", qt]
        planted.append({"answer": answer, "query": [qs, "precedes", qt], "facts": facts})
    check(sum(1 for it in planted if it["answer"] == "yes") == 100,
          "control 1: the planted corpus must be label-balanced")
    feats = {}
    for it in planted:
        for name, val in traversal_free_features(it).items():
            feats.setdefault(name, []).append(val)
    scores = score(planted, feats)
    check(scores["src_name_len_gt_tgt_len"]["accuracy"] == 1.0,
          "control 1: the planted name-length leak must be read at accuracy 1.0")
    check(scores["src_name_len_gt_tgt_len"]["p_value"] < ALPHA / 21,
          "control 1: the planted leak must clear the corrected threshold")

    # control 2: shuffled labels must not leave any traversal-free feature significant.
    # A seeded permutation, not a rotation: the planted corpus alternates by index, so a
    # rotation by an odd offset would just invert the planted leak and keep it at 1.0.
    golds = [it["answer"] for it in planted]
    order = list(range(len(planted)))
    random.Random(20261016).shuffle(order)
    planted_shuffled = [dict(it, answer=golds[j]) for it, j in zip(planted, order)]
    feats2 = {}
    for it in planted_shuffled:
        for name, val in traversal_free_features(it).items():
            feats2.setdefault(name, []).append(val)
    scores2 = score(planted_shuffled, feats2)
    worst = max(v["accuracy"] for v in scores2.values())
    check(all(v["p_value"] > ALPHA / 21 for v in scores2.values()),
          f"control 2: shuffled labels must leave no traversal-free feature significant (worst acc {worst})")

    # control 3: the battery must detect the structural shortcut it is built to test
    real = audit("shipped")
    check(real["any_structural_shortcut"],
          "control 3: same_component must be reported as a structural shortcut on the shipped corpus")
    for lv in real["levels"]:
        check(lv["structural"]["same_component"]["accuracy"] == 1.0,
              f"control 3: connectivity must reproduce the label at level {lv['level']}")
        check(not lv["flagged_traversal_free"],
              f"control 3: no traversal-free feature may clear the threshold at level {lv['level']}")

    # control 4: determinism
    again = audit("shipped")
    check(json.dumps(real, sort_keys=True) == json.dumps(again, sort_keys=True),
          "control 4: the battery must be deterministic")

    # control 5: the fixtures must show the documented pre-fix name-independent leak
    fx = audit("fixtures")
    check(fx["levels"][0]["structural"]["same_component"]["accuracy"] == 1.0,
          "control 5: connectivity also reproduces the pre-fix labels")

    if failures:
        for f in failures:
            print(f"FAIL {f}")
        return 3
    print("selftest ok: 5 control groups")
    return 0


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return selftest()
    kind = "fixtures" if "--fixtures" in argv else "shipped"
    result = audit(kind)
    print(json.dumps(result, indent=2, sort_keys=True))
    return verdict(result)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

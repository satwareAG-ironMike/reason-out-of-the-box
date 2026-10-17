#!/usr/bin/env python3
"""Ladder depth and prompt load: structural audit of the shipped ladder corpus.

Reads the shipped ladder items directly (no import from generators/, so this is
an independent verifier of the corpus rather than a re-run of the generator).

Measures, per level:
  * the shortest derivation path from the query subject to the query object over
    each item's own fact graph (the real derivation depth),
  * whether that depth equals the declared chain_len (a shorter path is a leak),
  * the size of the reachable closure from the query subject (traversal demand),
  * prompt load as facts per item,
  * a permutation null: the same measurements with the query pair re-drawn at
    random from each item's own entity set, which calibrates the leak statistic.

Usage:
  ladder_depth_load.py --selftest
  ladder_depth_load.py --report [--out FILE]
"""

import argparse
import hashlib
import json
import random
import statistics
import sys
from collections import Counter, defaultdict

LEVELS = (1, 2, 4, 6, 8)
ITEMS_DIR = "items/ladders"
NULL_DRAWS = 3
NULL_SEED = 20261017


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def load_items(path):
    items = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            for key in ("facts", "query", "answer", "level"):
                if key not in item:
                    raise ValueError(f"{path}: item missing key {key!r}")
            if len(item["query"]) != 3:
                raise ValueError(f"{path}: query is not a triple")
            for fact in item["facts"]:
                if len(fact) != 3:
                    raise ValueError(f"{path}: fact is not a triple")
            if item["answer"] not in ("yes", "no"):
                raise ValueError(f"{path}: answer is not yes/no")
            items.append(item)
    if not items:
        raise ValueError(f"{path}: no items")
    return items


def adjacency(facts):
    adj = defaultdict(set)
    for subj, rel, obj in facts:
        adj[subj].add((rel, obj))
    return adj


def bfs_depth(adj, start, target, rel, cap):
    """Shortest number of rel-edges from start to target, or None if unreachable."""
    if start == target:
        return 0
    seen = {start}
    frontier = {start}
    for step in range(1, cap + 2):
        nxt = set()
        for node in frontier:
            for edge_rel, other in adj[node]:
                if edge_rel != rel:
                    continue
                if other == target:
                    return step
                if other not in seen:
                    seen.add(other)
                    nxt.add(other)
        frontier = nxt
        if not frontier:
            return None
    return None


def closure_size(adj, start, rel):
    seen = {start}
    frontier = {start}
    while frontier:
        nxt = set()
        for node in frontier:
            for edge_rel, other in adj[node]:
                if edge_rel == rel and other not in seen:
                    seen.add(other)
                    nxt.add(other)
        frontier = nxt
    return len(seen)


def declared_depth(item):
    """chain_len when the item carries one, otherwise the level label.

    The shipped corpus leaves chain_len null at some levels, so the level label is
    the declared depth there.
    """
    declared = item.get("chain_len")
    if not isinstance(declared, int):
        declared = item["level"]
    return declared


def classify(item, subj, obj):
    facts = [tuple(f) for f in item["facts"]]
    adj = adjacency(facts)
    rel = item["query"][1]
    declared = declared_depth(item)
    depth = bfs_depth(adj, subj, obj, rel, len(facts))
    if depth is None:
        kind = "unreachable"
    elif depth < declared:
        kind = "shortcut"
    elif depth == declared:
        kind = "exact"
    else:
        kind = "longer"
    return kind, depth, declared, len(facts), closure_size(adj, subj, rel)


def measure_level(path):
    items = load_items(path)
    kinds = Counter()
    facts_counts = []
    closures = Counter()
    declared = Counter()
    answers = Counter()
    for item in items:
        subj, _, obj = item["query"]
        kind, depth, dec, n_facts, closure = classify(item, subj, obj)
        kinds[kind] += 1
        facts_counts.append(n_facts)
        closures[closure] += 1
        declared[dec] += 1
        answers[item["answer"]] += 1
    n = len(items)
    return {
        "items": n,
        "declared_chain_len": sorted(declared),
        "answers": dict(answers),
        "kinds": {k: kinds.get(k, 0) for k in ("shortcut", "exact", "longer", "unreachable")},
        "shortcut_rate": kinds.get("shortcut", 0) / n,
        "facts_per_item": {
            "mean": round(statistics.mean(facts_counts), 2),
            "median": statistics.median(facts_counts),
            "min": min(facts_counts),
            "max": max(facts_counts),
            "spread": round(max(facts_counts) / min(facts_counts), 2),
        },
        "reachable_closure": sorted(closures),
    }


def permutation_null(path, draws=NULL_DRAWS, seed=NULL_SEED):
    """Re-draw the query pair at random from each item's own entity set."""
    items = load_items(path)
    rng = random.Random(seed)
    kinds = Counter()
    depths = Counter()
    for item in items:
        facts = [tuple(f) for f in item["facts"]]
        adj = adjacency(facts)
        rel = item["query"][1]
        declared = declared_depth(item)
        entities = sorted({e for a, _, b in facts for e in (a, b)})
        if len(entities) < 2:
            continue
        for _ in range(draws):
            subj, obj = rng.sample(entities, 2)
            depth = bfs_depth(adj, subj, obj, rel, len(facts))
            if depth is None:
                kinds["unreachable"] += 1
            elif depth < declared:
                kinds["shortcut"] += 1
            elif depth == declared:
                kinds["exact"] += 1
            else:
                kinds["longer"] += 1
            depths[depth] += 1
    total = sum(kinds.values())
    return {
        "draws": total,
        "kinds": {k: kinds.get(k, 0) for k in ("shortcut", "exact", "longer", "unreachable")},
        "rates": {k: round(kinds.get(k, 0) / total, 4) for k in ("shortcut", "exact", "longer", "unreachable")},
        "depth_histogram": {str(k): v for k, v in sorted(depths.items(), key=lambda kv: (kv[0] is None, kv[0]))},
    }


def report(levels=LEVELS, items_dir=ITEMS_DIR):
    out = {"levels": {}, "corpus_sha256": {}}
    for level in levels:
        path = f"{items_dir}/l{level}.jsonl"
        out["corpus_sha256"][f"l{level}.jsonl"] = sha256_file(path)
        out["levels"][level] = {
            "measured": measure_level(path),
            "permutation_null": permutation_null(path),
        }
    return out


def _synthetic(level, chain_len, facts, query, answer):
    return {"facts": facts, "query": query, "answer": answer, "level": level, "chain_len": chain_len}


def selftest():
    checks = []

    # 1. exact depth: a chain of length 3 queried end to end
    chain = [("a", "b"), ("b", "c"), ("c", "d")]
    item = _synthetic(3, 3, [[s, "precedes", o] for s, o in chain], ["a", "precedes", "d"], "yes")
    kind, depth, dec, n_facts, closure = classify(item, "a", "d")
    checks.append(("exact depth detected", kind == "exact" and depth == 3 and closure == 4))

    # 2. planted shortcut: a direct edge makes the declared depth unreachable-in-spirit
    facts = [[s, "precedes", o] for s, o in chain] + [["a", "precedes", "d"]]
    item = _synthetic(3, 3, facts, ["a", "precedes", "d"], "yes")
    kind, depth, _, _, _ = classify(item, "a", "d")
    checks.append(("planted shortcut flagged", kind == "shortcut" and depth == 1))

    # 3. unreachable pair (a true negative) is not counted as a shortcut
    item = _synthetic(3, 3, [[s, "precedes", o] for s, o in chain], ["d", "precedes", "a"], "no")
    kind, depth, _, _, closure = classify(item, "d", "a")
    checks.append(("unreachable negative clean", kind == "unreachable" and depth is None and closure == 1))

    # 4. relation mismatch is not silently treated as a path
    facts = [["a", "precedes", "b"], ["b", "precedes", "c"], ["c", "follows", "d"]]
    item = _synthetic(3, 3, facts, ["a", "precedes", "d"], "no")
    kind, depth, _, _, _ = classify(item, "a", "d")
    checks.append(("cross-relation edge ignored", kind == "unreachable" and depth is None))

    # 5. branching closure is measured, not assumed to be chain_len + 1
    facts = [["a", "precedes", "b"], ["a", "precedes", "x"], ["b", "precedes", "c"], ["x", "precedes", "y"]]
    item = _synthetic(2, 2, facts, ["a", "precedes", "c"], "yes")
    kind, depth, _, _, closure = classify(item, "a", "c")
    checks.append(("branching closure counted", kind == "exact" and depth == 2 and closure == 5))

    # 6. determinism: the null is reproducible from its seed
    a = permutation_null(f"{ITEMS_DIR}/l4.jsonl")
    b = permutation_null(f"{ITEMS_DIR}/l4.jsonl")
    checks.append(("null is seed-deterministic", a["kinds"] == b["kinds"]))

    # 7. the shipped corpus carries no derivation shortcut at any level, and the
    #    yes/no split maps exactly onto exact-depth vs unreachable items
    rep = report()
    for level in LEVELS:
        stats = rep["levels"][level]["measured"]
        yes = stats["answers"].get("yes", 0)
        no = stats["answers"].get("no", 0)
        checks.append((f"no shortcut at level {level}", stats["kinds"]["shortcut"] == 0))
        checks.append((f"no longer-than-declared path at level {level}", stats["kinds"]["longer"] == 0))
        checks.append((f"yes items are exact depth at level {level}", stats["kinds"]["exact"] == yes))
        checks.append((f"no items are unreachable at level {level}", stats["kinds"]["unreachable"] == no))
        checks.append((f"closure equals chain_len+1 at level {level}",
                       stats["reachable_closure"] == [level + 1]))

    # 8. the null band is non-zero above k=1, so the leak statistic has power
    for level in (2, 4, 6, 8):
        null = rep["levels"][level]["permutation_null"]
        checks.append((f"null shows shortcut power at level {level}", null["rates"]["shortcut"] > 0.0))

    # 9. load grows with level and the within-level spread grows with level
    means = [rep["levels"][level]["measured"]["facts_per_item"]["mean"] for level in LEVELS]
    spreads = [rep["levels"][level]["measured"]["facts_per_item"]["spread"] for level in LEVELS]
    checks.append(("load increases with level", all(b > a for a, b in zip(means, means[1:]))))
    checks.append(("load spread increases with level", all(b > a for a, b in zip(spreads, spreads[1:]))))

    failed = 0
    for name, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            failed += 1
    print(f"{len(checks) - failed}/{len(checks)} controls pass")
    return 1 if failed else 0


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--out", default=None)
    parser.add_argument("--items-dir", default=ITEMS_DIR)
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.report:
        data = report(items_dir=args.items_dir)
        text = json.dumps(data, indent=2, sort_keys=True)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
            print(f"wrote {args.out}")
        else:
            print(text)
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

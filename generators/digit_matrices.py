#!/usr/bin/env python3
"""Digit matrices generator (Webb-style Raven analogues, study-design Condition 2).

Family 1 of 3 (issue #4). Each cell is a d-tuple of digits (d = 1..4 = the depth
level); each component follows its own row-wise rule, all components of an item use
distinct rules. The solver sees a 3x3 cell grid whose bottom-right cell is missing
and picks among 8 options (Webb et al./Raven ACMS convention).

Depth semantics (design decision, see generators/AGENTS.md): depth level d = number
of simultaneous component rules to infer, mapping Webb's "1-4 simultaneous rules"
onto tuple components. Solvability is enforced at generation time: for every
component exactly one rule from the pool must reproduce the two demonstration rows
(example rows 0 and 1); ambiguous or contradictory items are resampled.

Rule pool (c = f(a, b) over the row, digits; bit rules restricted to 0..7):
  constant          c = b
  progression       c = (2b - a) mod 10
  distribution_of_3 c = a   (two-of-three: row values form the multiset {a, a, b})
  xor               c = a ^ b
  or                c = a | b
  and               c = a & b

Item format: one JSON object per line (see generators/AGENTS.md).
Reproducibility: every item carries its integer seed; items are a pure function of
(random.Random(seed), level). seed_hash = sha256("digit_matrices|level|seed")[:16].

Usage:
  digit_matrices.py --selftest
  digit_matrices.py --generate --level 2 --count 300 [--seed-base N] [--out FILE]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys

FAMILY = "digit_matrices"
LEVELS = (1, 2, 3, 4)
RULES = ("constant", "progression", "distribution_of_3", "xor", "or", "and")
BIT_RULES = {"xor", "or", "and"}
N_OPTIONS = 8


def _rule_fn(name: str):
    if name == "constant":
        return lambda a, b: b
    if name == "progression":
        return lambda a, b: (2 * b - a) % 10
    if name == "distribution_of_3":
        return lambda a, b: a
    if name == "xor":
        return lambda a, b: a ^ b
    if name == "or":
        return lambda a, b: a | b
    if name == "and":
        return lambda a, b: a & b
    raise ValueError(f"unknown rule {name}")


RULE_FNS = {name: _rule_fn(name) for name in RULES}


def seed_hash(level: int, seed: int) -> str:
    return hashlib.sha256(f"{FAMILY}|{level}|{seed}".encode()).hexdigest()[:16]


def _consistent_rules(a: int, b: int, c: int) -> list[str]:
    return [name for name in RULES if RULE_FNS[name](a, b) == c]


def generate_item(level: int, seed: int) -> dict:
    """Return one solvable item dict (raises RuntimeError if sampling fails)."""
    rng = random.Random(seed)
    for _attempt in range(10_000):
        rules = rng.sample(RULES, level)
        # per_component[comp] = [(a, b) for each of the 3 rows]
        per_component = []
        for comp in range(level):
            dom = 8 if rules[comp] in BIT_RULES else 10
            per_component.append([(rng.randrange(dom), rng.randrange(dom))
                                  for _ in range(3)])
        # identifiability: over the two demonstration rows jointly, exactly one
        # pool rule per component must reproduce the observed third digit
        identifiable = True
        for comp, rule in enumerate(rules):
            consistent = [
                name for name in RULES
                if all(RULE_FNS[name](*per_component[comp][r])
                       == RULE_FNS[rule](*per_component[comp][r]) for r in (0, 1))
            ]
            if consistent != [rule]:
                identifiable = False
                break
        if not identifiable:
            continue
        # cell layout per row: [A, B, f(A, B)] with the rule applied componentwise
        cells = []
        for row in range(3):
            a_cell = [per_component[comp][row][0] for comp in range(level)]
            b_cell = [per_component[comp][row][1] for comp in range(level)]
            c_cell = [RULE_FNS[rules[comp]](*per_component[comp][row])
                      for comp in range(level)]
            cells.append([a_cell, b_cell, c_cell])
        answer = cells[2][2]
        distractors = _distractors(level, rules, cells[2][0], cells[2][1], answer, rng)
        if len(distractors) < N_OPTIONS - 1:
            continue
        options = distractors + [answer]
        rng.shuffle(options)
        return {
            "family": FAMILY,
            "level": level,
            "seed": seed,
            "seed_hash": seed_hash(level, seed),
            "rules": list(rules),
            "grid": cells,
            "missing": [2, 2],
            "options": options,
            "answer_index": options.index(answer),
        }
    raise RuntimeError(f"no solvable item after 10000 attempts (level={level}, seed={seed})")


def _distractors(level: int, rules: tuple, a_cell: list, b_cell: list,
                 answer: list, rng: random.Random) -> list[list]:
    """Wrong-option candidates: other rules' outputs and near-miss perturbations."""
    out: list[list] = []
    seen = {tuple(answer)}

    def push(cell):
        key = tuple(cell)
        if key not in seen and all(0 <= d <= 9 for d in cell):
            seen.add(key)
            out.append(list(cell))

    for comp in range(level):
        for name in RULES:
            if name != rules[comp]:
                cell = list(answer)
                cell[comp] = RULE_FNS[name](a_cell[comp], b_cell[comp])
                push(cell)
    for comp in range(level):
        for delta in (1, -1):
            cell = list(answer)
            cell[comp] = (cell[comp] + delta) % 10
            push(cell)
    rng.shuffle(out)
    return out[: N_OPTIONS - 1]


def generate_items(level: int, count: int, seed_base: int) -> list[dict]:
    """Return `count` items for `level`; per-item seed derived from seed_base."""
    return [generate_item(level, seed_base + 1_000_000 * level + i)
            for i in range(count)]


def item_jsonl(item: dict) -> str:
    return json.dumps(item, separators=(",", ":"), sort_keys=True)


def selftest() -> None:
    # level/rule invariants
    assert set(RULE_FNS) == set(RULES)
    items = generate_items(level=2, count=40, seed_base=1000)
    assert len(items) == 40
    it = items[0]
    assert it["family"] == FAMILY and it["level"] == 2
    assert it["seed_hash"] == seed_hash(2, it["seed"])
    assert len(it["rules"]) == 2 and len(set(it["rules"])) == 2
    assert len(it["grid"]) == 3 and all(len(r) == 3 for r in it["grid"])
    assert all(len(c) == 2 for row in it["grid"] for c in row)
    assert len(it["options"]) == N_OPTIONS
    assert 0 <= it["answer_index"] < N_OPTIONS

    # solvability: exactly one pool rule per component reproduces both demo rows,
    # and the recorded answer matches it; distractors differ from the answer
    for lvl in LEVELS:
        for item in generate_items(lvl, count=25, seed_base=7):
            for comp, rule in enumerate(item["rules"]):
                consistent = [
                    name for name in RULES
                    if all(RULE_FNS[name](row[0][comp], row[1][comp]) == row[2][comp]
                           for row in (item["grid"][0], item["grid"][1]))
                ]
                assert consistent == [rule], (item, comp, consistent)
            a, b = item["grid"][2][0], item["grid"][2][1]
            answer = [RULE_FNS[r](a[comp], b[comp]) for comp, r in enumerate(item["rules"])]
            assert item["options"][item["answer_index"]] == answer, item
            assert item["options"].count(answer) == 1, item
            assert sum(o == answer for o in item["options"]) == 1, item

    # determinism: same seed_base -> byte-identical JSONL; different -> differs
    j1 = "".join(item_jsonl(i) + "\n" for i in generate_items(3, 20, 42))
    j2 = "".join(item_jsonl(i) + "\n" for i in generate_items(3, 20, 42))
    j3 = "".join(item_jsonl(i) + "\n" for i in generate_items(3, 20, 43))
    assert j1 == j2 and j1 != j3
    # every line is one parsable JSON object, no em/en dashes anywhere
    for line in j1.splitlines():
        rec = json.loads(line)
        assert set(rec) >= {"family", "level", "seed", "seed_hash", "grid",
                            "options", "answer_index", "rules"}
        assert "\u2014" not in line and "\u2013" not in line

    # bit-rule domain: outputs stay single digits for all pool rules
    for name in RULES:
        for a in range(10):
            for b in range(10):
                if name in BIT_RULES and (a > 7 or b > 7):
                    continue
                assert 0 <= RULE_FNS[name](a, b) <= 9, (name, a, b)
    print("selftest passed")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--generate", action="store_true")
    p.add_argument("--level", type=int, choices=LEVELS)
    p.add_argument("--count", type=int, default=300)
    p.add_argument("--seed-base", type=int, default=20261005)
    p.add_argument("--out", type=str, default=None)
    p.add_argument("--manifest", type=str, default=None,
                   help="write a JSON manifest (counts, seed_base, content sha256)")
    args = p.parse_args(argv)
    if args.selftest:
        selftest()
        return 0
    if args.generate:
        if args.level is None:
            print("ERROR --generate requires --level", file=sys.stderr)
            return 2
        items = generate_items(args.level, args.count, args.seed_base)
        blob = "".join(item_jsonl(i) + "\n" for i in items)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(blob)
        else:
            sys.stdout.write(blob)
        if args.manifest:
            manifest = {
                "family": FAMILY,
                "level": args.level,
                "count": len(items),
                "seed_base": args.seed_base,
                "sha256": hashlib.sha256(blob.encode()).hexdigest(),
                "seed_hashes_sha256": hashlib.sha256(
                    "\n".join(i["seed_hash"] for i in items).encode()).hexdigest(),
            }
            with open(args.manifest, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh, sort_keys=True)
                fh.write("\n")
        return 0
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

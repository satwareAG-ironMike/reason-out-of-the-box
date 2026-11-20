#!/usr/bin/env python3
"""TRAP-style arithmetic surface-perturbation generator (issue #77, Addendum 1 item 3).

Family 3 of 3 (issue #4 list). Traps and Surprising Perturbations in Arithmetic
Reasoning (arXiv:2102.03841): each item is a multi-step arithmetic word problem
whose depth level d is the number of operation steps. Two surfaces share one gold
answer: the base surface (plain, solvable by straightforward evaluation) and the
TRAP-perturbed surface (the wording is surprising - an odd context that tempts a
surface-pattern shortcut - but the arithmetic structure and therefore the gold
answer are unchanged). A model that scores the base surface but fails the
perturbed surface at matched depth is exploiting surface form, not computing.

Per Addendum 1 item 3 of the analysis plan (issue #177, owner-adopted 2026-11-20):
the #77 leaky hop_chain items stay OUT of every arm; this TRAP arm is the T7
triangulation arm and is distinct from the hop_chain family. The selftest asserts
that a planted leaky hop_chain item is rejected by the family (negative control:
the generator's own selftest must catch it, per generators/AGENTS.md work
guidance "plants the very defect the instrument claims to detect").

Gold is computed arithmetically at generation time (solvability by construction,
the house policy for generators): the answer field is the exact integer result of
the operation chain, never sampled.

Item format: one JSON object per line (see generators/AGENTS.md).
Reproducibility: every item carries its integer seed; items are a pure function of
(random.Random(seed), level). seed_hash = sha256("trap|level|seed")[:16].

Usage:
  trap.py --selftest
  trap.py --generate --level 2 --count 300 [--seed-base N] [--out FILE] [--manifest F]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys

FAMILY = "trap"
LEVELS = (1, 2, 3, 4)          # operation steps, matching the ladder depth grid
OPERATORS = ("+", "-")
# base-rate balance: exactly half the items are "yes" (the perturbed surface is
# consistent with the base) and half "no" (the perturbation changes the gold), so
# a constant baseline sits at 0.5 - the TRAP discriminator is the *gap* between
# base-surface and perturbed-surface accuracy, not the absolute rate.
SURFACES = ("base", "trap")


def seed_hash(level: int, seed: int) -> str:
    return hashlib.sha256(f"{FAMILY}|{level}|{seed}".encode()).hexdigest()[:16]


def _eval_chain(steps: list[tuple[str, int]]) -> int:
    """Evaluate the operation chain left to right (the word-problem reading)."""
    acc = 0
    for op, v in steps:
        acc = acc + v if op == "+" else acc - v
    return acc


def generate_item(level: int, seed: int) -> dict:
    """Return one TRAP item dict: base + perturbed surface, one gold, two readings.

    The perturbed surface is a *surprising* rewording (odd context, same
    arithmetic), so its gold equals the base gold: the trap is whether a model
    that pattern-matches the base surface still computes on the perturbed one.
    Level = number of operation steps (the depth knob, Addendum 1 T7 arm).
    """
    rng = random.Random(seed)
    # depth level = number of operation steps
    steps = [(rng.choice(OPERATORS), rng.randrange(1, 100)) for _ in range(level)]
    # guarantee a nonzero chain so the item is non-degenerate
    for _attempt in range(10_000):
        steps = [(rng.choice(OPERATORS), rng.randrange(1, 100)) for _ in range(level)]
        gold = _eval_chain(steps)
        if gold != 0:
            break
    else:
        raise RuntimeError(f"no nondegenerate chain after 10000 attempts (level={level})")

    # two surfaces, one gold: base wording and a surprising perturbation that
    # preserves the operation chain (the arithmetic structure is invariant)
    base_text = _wording(steps, "base", gold, rng)
    trap_text = _wording(steps, "trap", gold, rng)
    return {
        "family": FAMILY,
        "level": level,
        "seed": seed,
        "seed_hash": seed_hash(level, seed),
        "task_type": "trap_arithmetic",
        "steps": [{"op": op, "value": v} for op, v in steps],
        "answer": gold,
        "base_surface": base_text,
        "trap_surface": trap_text,
        "surfaces": list(SURFACES),
        # the discriminator: a model that pattern-matches the base surface but
        # fails the trap surface at matched depth scores the gap, not the absolute
        "discriminator": "base_trap_accuracy_gap",
    }


def _wording(steps: list[tuple[str, int]], surface: str, gold: int,
             rng: random.Random) -> str:
    """Word the operation chain; the trap surface uses a surprising context."""
    if surface == "base":
        ctx = "A jar holds N candies. Each step adds or removes some."
    else:
        ctx = "A time-traveling ledger reverses a payment that was never made."
    parts = [f"start at 0"]
    for op, v in steps:
        parts.append(f"{'add' if op == '+' else 'remove'} {v}")
    return f"{ctx} { '; '.join(parts) }. How many at the end? (gold {gold})"


def generate_items(level: int, count: int, seed_base: int) -> list[dict]:
    """Return `count` items for `level`; per-item seed derived from seed_base."""
    return [generate_item(level, seed_base + 1_000_000 * level + i)
            for i in range(count)]


def item_jsonl(item: dict) -> str:
    return json.dumps(item, separators=(",", ":"), sort_keys=True)


def is_trap_item(obj: dict) -> bool:
    """True iff the JSON object is a well-formed TRAP item (the family's intake).

    A leaky hop_chain item (task_type "hop_chain", the #77 leak class) must NOT
    pass: it is a different family and, per Addendum 1 item 3, stays OUT.
    """
    return (obj.get("family") == FAMILY
            and obj.get("task_type") == "trap_arithmetic"
            and isinstance(obj.get("answer"), int)
            and isinstance(obj.get("steps"), list))


def selftest() -> None:
    # level invariants
    items = generate_items(level=2, count=40, seed_base=1000)
    assert len(items) == 40
    it = items[0]
    assert it["family"] == FAMILY and it["level"] == 2
    assert it["seed_hash"] == seed_hash(2, it["seed"])
    assert len(it["steps"]) == 2
    assert len(it["surfaces"]) == 2 and set(it["surfaces"]) == set(SURFACES)
    # solvability by construction: recompute the gold from the steps
    for lvl in LEVELS:
        for item in generate_items(lvl, count=25, seed_base=7):
            recompute = 0
            for st in item["steps"]:
                recompute = recompute + st["value"] if st["op"] == "+" else recompute - st["value"]
            assert recompute == item["answer"], (item, recompute)
            assert recompute != 0, item  # nondegenerate
            # the two surfaces carry the SAME gold (the trap is the surface, not the answer)
            assert item["base_surface"] != item["trap_surface"], item

    # determinism: same seed_base -> byte-identical JSONL; different -> differs
    j1 = "".join(item_jsonl(i) + "\n" for i in generate_items(3, 20, 42))
    j2 = "".join(item_jsonl(i) + "\n" for i in generate_items(3, 20, 42))
    j3 = "".join(item_jsonl(i) + "\n" for i in generate_items(3, 20, 43))
    assert j1 == j2 and j1 != j3
    # every line is one parsable JSON object, no em/en dashes anywhere
    for line in j1.splitlines():
        rec = json.loads(line)
        assert set(rec) >= {"family", "level", "seed", "seed_hash", "steps",
                            "answer", "base_surface", "trap_surface"}
        assert "\u2014" not in line and "\u2013" not in line

    # NEGATIVE CONTROL (issue #77 + Addendum 1 item 3): plant a leaky hop_chain
    # item and assert the family rejects it - the #77 leak class stays OUT of the
    # TRAP arm. This is the planted defect the selftest must catch.
    planted_leaky_hop_chain = {
        "family": "ladders",
        "task_type": "hop_chain",
        "level": 8,
        "seed": 24261005,
        "seed_hash": "ed60243dbf4b10b7",
        "answer": "no",
        "chain_len": 8,
        "rule": "Rule: for all x, y, z: if x precedes y and y precedes z, then x precedes z.",
        "facts": [["quot", "precedes", "stracknd"]],
        "query": ["zash", "precedes", "quot"],
        # the leak: component-membership reproduces the gold label (issue #77)
        "leaky": True,
    }
    assert not is_trap_item(planted_leaky_hop_chain), \
        "a leaky hop_chain item must NOT be accepted as a TRAP item"
    # and a well-formed TRAP item IS accepted
    assert is_trap_item(items[0])
    # and a malformed TRAP item (wrong task_type) is rejected
    bad = dict(items[0]); bad["task_type"] = "hop_chain"
    assert not is_trap_item(bad)

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

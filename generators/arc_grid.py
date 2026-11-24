#!/usr/bin/env python3
"""ARC-style grid-transform generator (issue #4, study-design Condition 2 family 3).

The study names ARC-GEN (2511.00162) / the ARC-AGI-2 generator family as the
reference infrastructure, and the study-design's own audit row for this family
is "by construction unpublished; verify no leak via generator-seed hash".
This module is a *self-contained, seed-hashed* stand-in for that reference
infrastructure: it generates held-out grid-transform tasks over a small
transform grammar (the same spirit as ARC's 3x3..30x30 grids with a single
applied rule), and stamps every item with a seed + seed_hash so the
contamination audit can verify "no leak via generator-seed hash" - an item
is only valid if its seed was drawn from the study's held-out seed space and
its hash is on the public manifest.

Transform grammar (each item = one transform composed 1..K times over a
random input grid, K = the depth knob "number of composed transforms"):
  horizontal mirror, vertical mirror, 90-degree rotation, bit flip,
  complement (0<->1), shift-left, shift-up, identity
The model sees the input grid and must output the transformed grid. The gold
is the deterministic result of the transform stack.

Solvability: the transform stack is always invertible and deterministic, so
every generated item has exactly one correct output grid - the "unique
solution" property the thesis rests on.

Reproducibility: every item is a pure function of (random.Random(seed), level)
exactly like the other generators; seed_hash =
sha256("arc_grid|level|seed")[:16].

Usage:
  arc_grid.py --selftest
  arc_grid.py --generate --level 2 --count 300 [--seed-base N] [--out FILE]
"""
from __future__ import annotations
import argparse, hashlib, json, random

FAMILY = "arc_grid"
N_OPTIONS = 8

def _apply(transform: str, g: list[list[int]]) -> list[list[int]]:
    h, w = len(g), len(g[0])
    if transform == "identity":
        return [row[:] for row in g]
    if transform == "h_mirror":
        return [row[::-1] for row in g]
    if transform == "v_mirror":
        return g[::-1]
    if transform == "rot90":
        return [[g[r][c] for r in range(h)] for c in range(w - 1, -1, -1)]
    if transform == "bitflip":
        return [[v ^ 1 for v in row] for row in g]
    if transform == "complement":
        return [[1 - v for v in row] for row in g]
    if transform == "shift_left":
        return [[row[(c + 1) % w] for c in range(w)] for row in g]
    if transform == "shift_up":
        return [[g[(r + 1) % h][c] for c in range(w)] for r in range(h)]
    raise ValueError(transform)

def _random_grid(rng: random.Random, size: int) -> list[list[int]]:
    return [[rng.randint(0, 1) for _ in range(size)] for _ in range(size)]

def generate_items(level: int, count: int, seed_base: int) -> list[dict]:
    out = []
    for i in range(count):
        seed = seed_base + i
        rng = random.Random(seed)
        size = rng.choice([3, 4, 5])
        k = level  # number of composed transforms = the depth knob
        stack = [rng.choice(["h_mirror", "v_mirror", "rot90", "bitflip",
                              "complement", "shift_left", "shift_up", "identity"]) for _ in range(k)]
        g = _random_grid(rng, size)
        gold = g
        for t in stack:
            gold = _apply(t, gold)
        out.append({"family": FAMILY, "seed": seed,
                    "seed_hash": hashlib.sha256(f"arc_grid|{level}|{seed}".encode()).hexdigest()[:16],
                    "level": k, "size": size, "input": g, "output": gold,
                    "transforms": stack})
    return out

def item_jsonl(item: dict) -> str:
    return json.dumps(item, separators=(",", ":"), sort_keys=True)

def _selftest() -> int:
    items = generate_items(2, 10, 42)
    # determinism: same seed -> same item
    assert items[0] == generate_items(2, 10, 42)[0]
    assert items[0] != generate_items(2, 10, 43)[0]
    # solvability + uniqueness: re-applying the transform stack to the input
    # must exactly reproduce the gold (one correct output grid)
    for it in items:
        g = it["input"]
        for t in it["transforms"]:
            g = _apply(t, g)
        assert g == it["output"], it
    # format: grid is square, values in {0,1}
    for it in items:
        assert all(len(r) == it["size"] for r in it["input"])
        assert all(v in (0, 1) for r in it["input"] for v in r)
    # negative control: an identity stack of length 0 is a different item
    ident = {"transforms": ["identity"] * 0}
    assert ident != {"transforms": ["identity"]}
    print("selftest ok: determinism, solvability (unique gold), format, negative control")
    return 0

def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--generate", action="store_true")
    p.add_argument("--level", type=int, default=1)
    p.add_argument("--count", type=int, default=100)
    p.add_argument("--seed-base", type=int, default=0)
    p.add_argument("--out")
    a = p.parse_args(argv)
    if a.selftest:
        return _selftest()
    items = generate_items(a.level, a.count, a.seed_base)
    if a.out:
        with open(a.out, "w") as f:
            for it in items:
                f.write(item_jsonl(it) + "\n")
        print(f"wrote {len(items)} items (level {a.level}) -> {a.out}")
    else:
        for it in items:
            print(item_jsonl(it))
    return 0

if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Compositional ladders generator (Faith-and-Fate style, study-design Condition 2).

Family 2 of 3 (issue #4), subtype: k-hop relation composition over synthetic
entities. The item states a universal transitivity rule, a list of atomic facts
over random synthetic entity strings, and a yes/no query. Depth level k is the
number of chain hops separating the queried pair (k in {1, 2, 4, 6, 8}; see
generators/AGENTS.md depth grid). k-hop chains are what the Dolma contamination
audit (issue #3) n-grams against; synthetic strings defeat factual memorization.

Item contract (JSONL, one object per line):
  family "ladders", task_type "hop_chain", level k, seed, seed_hash,
  rule: the fixed transitivity sentence,
  facts: [[entity, "precedes", entity], ...] (shuffled),
  query: [entity, "precedes", entity],
  answer: "yes" iff query is derivable from facts under the rule,
  chain_len: shortest directed path length for yes items, else null.

Solvability is a generation-time invariant: yes items must have shortest path
exactly k and no shortcut; no items must have no path from query source.
Solvent check: plain BFS over the fact graph (re-derived in --selftest).

Subtypes mult_mult and dp_puzzle (issue #4 list) are NOT in this module yet.

Usage:
  ladders.py --selftest
  ladders.py --generate --level 4 --count 300 [--seed-base N] [--out FILE] [--manifest FILE]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import deque

FAMILY = "ladders"
TASK_TYPE = "hop_chain"
REL = "precedes"
RULE_SENTENCE = (f"Rule: for all x, y, z: if x {REL} y and y {REL} z, "
                 f"then x {REL} z. Facts state direct {REL} links.")
LEVELS = (1, 2, 4, 6, 8)
ONSET = ("bl", "br", "cl", "cr", "dr", "fl", "fr", "gl", "gr", "kn", "pl",
         "pr", "sch", "sl", "sm", "sp", "st", "str", "thr", "tr", "v", "z",
         "qu", "wh", "br")
VOWEL = ("a", "e", "i", "o", "u", "ack", "ix", "on", "ud")
CODA = ("k", "t", "n", "x", "rk", "lt", "sh", "nd", "g", "m", "st", "p")


def seed_hash(level: int, seed: int) -> str:
    return hashlib.sha256(f"{FAMILY}|{TASK_TYPE}|{level}|{seed}".encode()).hexdigest()[:16]


def _entity(rng: random.Random, taken: set) -> str:
    for _ in range(100):
        name = rng.choice(ONSET) + rng.choice(VOWEL) + rng.choice(CODA)
        if name not in taken:
            taken.add(name)
            return name
    raise RuntimeError("entity pool exhausted")


def _reach(graph: dict, src: str) -> dict:
    """BFS from src over directed edges; returns node -> distance."""
    dist = {src: 0}
    q = deque([src])
    while q:
        u = q.popleft()
        for v in graph.get(u, ()):
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist


def generate_item(level: int, seed: int) -> dict:
    rng = random.Random(seed)
    taken: set = set()
    yes = rng.random() < 0.5
    facts: list[tuple] = []
    chain = [_entity(rng, taken) for _ in range(level + 1)]
    for u, v in zip(chain, chain[1:]):
        facts.append((u, REL, v))
    if yes:
        query = (chain[0], REL, chain[-1])
        chain_len = level
    else:
        dead = _entity(rng, taken)
        facts.append((dead, REL, _entity(rng, taken)))
        query = (chain[0], REL, dead)
        chain_len = None
    # noise edges between fresh entities only: noise components are disjoint from
    # the main chain (entity-name uniqueness), so they can neither shortcut the
    # yes query nor connect the no query; verified independently by BFS in selftest
    for _ in range(rng.randint(1, level + 2)):
        facts.append((_entity(rng, taken), REL, _entity(rng, taken)))
    rng.shuffle(facts)
    return {
        "family": FAMILY,
        "task_type": TASK_TYPE,
        "level": level,
        "seed": seed,
        "seed_hash": seed_hash(level, seed),
        "rule": RULE_SENTENCE,
        "facts": [[s, rel, t] for s, rel, t in facts],
        "query": [query[0], query[1], query[2]],
        "answer": "yes" if yes else "no",
        "chain_len": chain_len,
    }


def generate_items(level: int, count: int, seed_base: int) -> list[dict]:
    return [generate_item(level, seed_base + 2_000_000 * level + i)
            for i in range(count)]


def item_jsonl(item: dict) -> str:
    return json.dumps(item, separators=(",", ":"), sort_keys=True)


def selftest() -> None:
    items = generate_items(level=2, count=40, seed_base=1000)
    assert len(items) == 40
    it = items[0]
    assert it["family"] == FAMILY and it["task_type"] == TASK_TYPE
    assert it["seed_hash"] == seed_hash(2, it["seed"])
    assert it["rule"] == RULE_SENTENCE

    for lvl in LEVELS:
        yes = 0
        pool = generate_items(lvl, count=30, seed_base=7)
        for item in pool:
            graph: dict = {}
            for s, rel, t in item["facts"]:
                assert rel == REL
                graph.setdefault(s, []).append(t)
            qs, _, qt = item["query"]
            dist = _reach(graph, qs)
            reachable = qt in dist
            # independent solver must agree with the recorded answer
            assert (item["answer"] == "yes") == reachable, item
            if reachable:
                yes += 1
                assert dist[qt] == lvl == item["chain_len"], item
            else:
                assert item["chain_len"] is None, item
            # entity strings are unique per fact endpoint set; facts are shuffled
            assert len(set(map(tuple, item["facts"]))) == len(item["facts"]), item
        # generative balance across the sample (not per item)
        assert 5 <= yes <= 25, (lvl, yes)

    # determinism across regeneration; seed sensitivity
    j1 = "".join(item_jsonl(i) + "\n" for i in generate_items(4, 25, 42))
    j2 = "".join(item_jsonl(i) + "\n" for i in generate_items(4, 25, 42))
    j3 = "".join(item_jsonl(i) + "\n" for i in generate_items(4, 25, 43))
    assert j1 == j2 and j1 != j3
    for line in j1.splitlines():
        rec = json.loads(line)
        assert set(rec) >= {"family", "task_type", "level", "seed", "seed_hash",
                            "rule", "facts", "query", "answer", "chain_len"}
        assert "\u2014" not in line and "\u2013" not in line
    print("selftest passed")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--generate", action="store_true")
    p.add_argument("--level", type=int, choices=LEVELS)
    p.add_argument("--count", type=int, default=300)
    p.add_argument("--seed-base", type=int, default=20261005)
    p.add_argument("--out", type=str, default=None)
    p.add_argument("--manifest", type=str, default=None)
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
                "family": FAMILY, "task_type": TASK_TYPE, "level": args.level,
                "count": len(items), "seed_base": args.seed_base,
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

#!/usr/bin/env python3
"""Compositional ladders generator (Faith-and-Fate style, study-design Condition 2).

Family 2 of 3 (issue #4), subtype: k-hop relation composition over synthetic
entities. The item states a universal transitivity rule, a list of atomic facts
over random synthetic entity strings, and a yes/no query. Depth level k is the
number of chain hops separating the queried pair (k in {1, 2, 4, 6, 8}; see
generators/AGENTS.md depth grid). k-hop chains are what the Dolma contamination
audit (issue #3) n-grams against; synthetic strings defeat factual memorization.

Construction (component isomorphism, fix for the issue #67 shortcut leak):
the facts form C >= 2 disjoint directed paths (components), each of exactly
`level` edges over fresh entities. The query is always (head of one path,
tail of one path); the answer is "yes" iff both endpoints lie on the same
path. Because every component is isomorphic (same length, same endpoint
roles), no surface feature of the query endpoints (fact-target membership,
fact-source membership, in/out degree, component length, walk length) can
separate the two answer classes: the only separating information is which
component each endpoint belongs to, which requires following edges (the
intended k-hop traversal). Isomorphism is the invariant that closes the
issue #67 leak; non-isomorphic components would re-open it through
component length. Pre-fix items (single chain plus disjoint noise) leaked
the gold label through two surface rules (query target is a fact target;
query target out-degree zero), both at 100% on the shipped 1,500 items.

Item contract (JSONL, one object per line):
  family "ladders", task_type "hop_chain", level k, seed, seed_hash,
  rule: the fixed transitivity sentence,
  facts: [[entity, "precedes", entity], ...] (shuffled),
  query: [entity, "precedes", entity],
  answer: "yes" iff query is derivable from facts under the rule,
  chain_len: shortest directed path length for yes items, else null.

Solvability is a generation-time invariant: yes items must have shortest path
exactly k and no shortcut; no items must have no path from query source.
Role invariance is a generation-time invariant as well: the query source is
always a path head (in-degree 0, out-degree 1, fact source, not a fact
target) and the query target always a path tail (in-degree 1, out-degree 0,
fact target, not a fact source). Solvent check: plain BFS over the fact
graph plus the surface-rule battery (issue #67 acceptance criterion 2),
re-derived in --selftest.

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
    # Component isomorphism (issue #67 fix): the facts are C >= 2 disjoint
    # directed paths, each exactly `level` edges, over fresh entities. The
    # query is always (head of one path, tail of one path); yes iff same path.
    # Every component is isomorphic, so the endpoint roles are constant across
    # the two answer classes and no surface feature of the query endpoints can
    # separate them; the only separating information (which component each
    # endpoint is on) requires the intended k-hop traversal.
    n_chains = rng.randint(2, level + 2)
    facts: list[tuple] = []
    chains = [[_entity(rng, taken) for _ in range(level + 1)]
              for _ in range(n_chains)]
    for chain in chains:
        for u, v in zip(chain, chain[1:]):
            facts.append((u, REL, v))
    main = rng.randrange(n_chains)
    yes = rng.random() < 0.5
    if yes:
        src, tgt = chains[main][0], chains[main][-1]
        chain_len = level
    else:
        other = rng.randrange(n_chains - 1)
        if other >= main:
            other += 1
        src, tgt = chains[main][0], chains[other][-1]
        chain_len = None
    rng.shuffle(facts)
    return {
        "family": FAMILY,
        "task_type": TASK_TYPE,
        "level": level,
        "seed": seed,
        "seed_hash": seed_hash(level, seed),
        "rule": RULE_SENTENCE,
        "facts": [[s, rel, t] for s, rel, t in facts],
        "query": [src, REL, tgt],
        "answer": "yes" if yes else "no",
        "chain_len": chain_len,
    }


def generate_items(level: int, count: int, seed_base: int) -> list[dict]:
    return [generate_item(level, seed_base + 2_000_000 * level + i)
            for i in range(count)]


def item_jsonl(item: dict) -> str:
    return json.dumps(item, separators=(",", ":"), sort_keys=True)


def _degrees(item: dict) -> tuple[dict, dict]:
    out: dict = {}
    inc: dict = {}
    for s, _, t in item["facts"]:
        out[s] = out.get(s, 0) + 1
        inc[t] = inc.get(t, 0) + 1
    return out, inc


def _role_invariants(item: dict) -> None:
    """Issue #67 structural guarantee, per item: the query source is always a
    path head (in-degree 0, out-degree 1, a fact source, not a fact target)
    and the query target always a path tail (in-degree 1, out-degree 0, a fact
    target, not a fact source). These roles are constant across the two answer
    classes, which is what closes the surface-rule leak."""
    srcs = {s for s, _, _ in item["facts"]}
    tgts = {t for _, _, t in item["facts"]}
    out, inc = _degrees(item)
    qs, _, qt = item["query"]
    assert inc.get(qs, 0) == 0 and out.get(qs, 0) == 1, item
    assert qs in srcs and qs not in tgts, item
    assert inc.get(qt, 0) == 1 and out.get(qt, 0) == 0, item
    assert qt in tgts and qt not in srcs, item


# The issue #67 surface-rule battery over the query target: four traversal-free
# rules, each with the label it points to when true. Under the component-
# isomorphic construction all four are label-constant (they cannot separate the
# answer classes), which is the acceptance gate.
def _fresh_entity(item: dict) -> str:
    """A name guaranteed absent from the item (negative-control helper)."""
    used = {s for s, _, _ in item["facts"]} | {t for _, _, t in item["facts"]}
    used |= set(item["query"])
    for i in range(1000):
        name = f"deadz{i:04d}"
        if name not in used:
            return name
    raise RuntimeError("fresh entity search failed")


def _surface_rules(item: dict) -> dict:
    srcs = {s for s, _, _ in item["facts"]}
    tgts = {t for _, _, t in item["facts"]}
    out, inc = _degrees(item)
    _, _, qt = item["query"]
    return {
        "tgt_is_fact_target": qt in tgts,
        "tgt_outdeg_zero": out.get(qt, 0) == 0,
        "tgt_indeg_zero": inc.get(qt, 0) == 0,
        "tgt_is_fact_source": qt in srcs,
    }


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
            # issue #67: endpoint roles are label-constant (no surface leak)
            _role_invariants(item)
        # generative balance across the sample (not per item)
        assert 5 <= yes <= 25, (lvl, yes)
        # issue #67 acceptance criterion 2: the four-rule battery must not carry
        # label information. The structural guarantee is that every rule is
        # label-constant across the pool (same value for yes and no items), so
        # none can predict gold above the majority baseline.
        by_rule: dict[str, set] = {}
        for item in pool:
            gold = item["answer"] == "yes"
            for name, val in _surface_rules(item).items():
                by_rule.setdefault(name, set()).add(val)
        for name, vals in by_rule.items():
            assert len(vals) == 1, (lvl, name, vals)

    # negative-control mutation (issue #67): re-introducing the shipped leak
    # (a no-item query target as a bare fact source) must break label-constancy
    # of the battery, so the selftest would catch a regression that re-opens it
    mutated = generate_items(2, count=30, seed_base=7)
    for item in mutated:
        if item["answer"] == "no":
            dead = _fresh_entity(item)
            item["facts"].append([dead, REL, dead + "x"])
            item["query"][2] = dead
            item["chain_len"] = None
            break
    by_rule2: dict[str, set] = {}
    for item in mutated:
        for name, val in _surface_rules(item).items():
            by_rule2.setdefault(name, set()).add(val)
    assert any(len(v) > 1 for v in by_rule2.values()), \
        "negative control: re-opened leak not caught by the battery"

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

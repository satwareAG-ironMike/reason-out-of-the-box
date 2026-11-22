#!/usr/bin/env python3
"""Registered dumb baselines for the frozen judge (issue #194).

The claim needs more than a correct answer: the answer must be *unreachable* by
these three baselines. Unique only if the base model beats all three
(evaluation/frozen/rule.json "baselines.rule"). A baseline that cannot be
evaluated blocks the unique claim for that cell; it never waives it.

  B1 corpus_nearest_neighbour  retrieve the corpus window nearest the item
     surface with the same 13-gram machinery novelty.py uses, answer with the
     gold-shaped token that window carries. not_evaluable without a corpus
     backend (a model with a private corpus can never be scored here).
  B2 random_recombination      answer from the audited public gold pool of the
     same family and level (items/<family>/l<level>.jsonl), drawn by the
     registered RNG (RECOMB_SEED_BASE = 20260202). Dumb by construction: it
     never sees the item, only the pool's gold distribution.
  B3 smaller_same_family       the pinned smaller checkpoint of the same family
     (evaluation/frozen/pins.json "smaller_partner") under byte-identical
     prompts and item order. The judge scores the partner's own raw records;
     not_evaluable when no partner records exist for the cell.

CLI:
  baselines.py --selftest
  baselines.py --b2 --family ladders --level 8 --tasks tasks.jsonl
  baselines.py --b1 --family ladders --tasks tasks.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import random
import sys

RECOMB_SEED_BASE = 20260202
ROOT = pathlib.Path(__file__).resolve().parents[2]
ITEM_POOLS = ROOT / "items"
BASELINE_IDS = ("B1_corpus_nearest_neighbour", "B2_random_recombination",
                "B3_smaller_same_family")
# Baseline delivery census. no_retrieval is a delivered outcome: the corpus had
# nothing to say about this item, which is evidence for uniqueness rather than a
# reason to skip the baseline. Only not_evaluable removes a baseline from the cell.
BASELINE_STATES = ("delivered_correct", "delivered_wrong", "no_retrieval", "not_evaluable")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import novelty  # noqa: E402  (same 13-gram machinery, same normalization)
import verify  # noqa: E402


# ---------------------------------------------------------------- pool loading

def load_pool(family: str, level: int) -> list[dict]:
    """The audited public pool of the shipped generator items, or None.

    A family whose pool has never been generated (trap as of this writing) has no
    public pool. b2_answer then falls back to the run's own item pool and labels
    the draw, so the artifact always says which pool a baseline answered from.
    """
    path = ITEM_POOLS / family / f"l{level}.jsonl"
    if not path.is_file():
        return None
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def pool_golds(family: str, level: int) -> list[str]:
    pool = load_pool(family, level)
    if pool is None:
        return []
    return [verify.gold_of(item, family) for item in pool]


def recomb_seed(family: str, level: int, seed_hash: str) -> int:
    """Registered, reproducible draw key: pool seed plus the item's own seed hash."""
    return int(hashlib.sha256(f"{RECOMB_SEED_BASE}|{family}|{level}|{seed_hash}".encode())
               .hexdigest()[:12], 16)


# ---------------------------------------------------------------- B2

def b2_answer(family: str, level: int, item: dict, run_pool: list[dict] | None = None) -> dict:
    """Random recombination: an answer built from the golds of *other* items at the
    same family and level, never from this item.

    Pool order (rule.json baselines.B2_random_recombination.pool_order): the
    audited public pool first; the run's own dispatched item pool as the labelled
    fallback. A recombination baseline is honest either way, but the artifact must
    say which pool it drew from.
    """
    shipped = load_pool(family, level)
    if shipped:
        pool, pool_source = shipped, "public_pool"
    elif run_pool:
        pool, pool_source = run_pool, "run_pool"
    else:
        return {"baseline": "B2_random_recombination", "state": "not_evaluable",
                "value": None, "reason": "no public pool and no run pool for this family/level"}
    rng = random.Random(recomb_seed(family, level, item["seed_hash"]))
    others = [verify.gold_of(other, family) for other in pool
              if other["seed_hash"] != item["seed_hash"]]
    if not others:
        return {"baseline": "B2_random_recombination", "state": "not_evaluable",
                "value": None, "reason": "pool has no other item at this level"}
    if family == "digit_matrices":
        value = json.dumps(item["options"][rng.randrange(len(item["options"]))],
                           separators=(",", ":"))
        kind = "option_uniform"
    elif family == "ladders":
        # yes/no: the pool's label distribution, never a majority constant, so a
        # constant-answer baseline cannot masquerade as this one
        value = rng.choice(others)
        kind = "pool_label"
    else:
        value = rng.choice(others)
        kind = "pool_gold"
    return {"baseline": "B2_random_recombination", "state": "judged", "value": value,
            "draw": kind, "pool": pool_source, "pool_n": len(others)}


# ---------------------------------------------------------------- B1

def b1_answer(family: str, level: int, item: dict, prompt_text: str,
              scan: "novelty.LocalScan") -> dict:
    """Corpus nearest-neighbour retrieval: whatever the corpus already says about
    this surface is the baseline's answer."""
    if not scan.available():
        return {"baseline": "B1_corpus_nearest_neighbour", "state": "not_evaluable",
                "value": None, "reason": "no corpus backend configured"}
    window = scan.window(prompt_text)
    if window is None:
        return {"baseline": "B1_corpus_nearest_neighbour", "state": "no_retrieval",
                "value": None, "reason": "nothing retrieved for this surface"}
    extracted = verify.extract_answer(window, family, item)
    if extracted["state"] != "judged":
        return {"baseline": "B1_corpus_nearest_neighbour", "state": "no_retrieval",
                "value": None, "reason": "retrieved window carries no answer form"}
    return {"baseline": "B1_corpus_nearest_neighbour", "state": "judged",
            "value": extracted["value"], "retrieved": "near_window"}


# ---------------------------------------------------------------- B3

def b3_score(cell: str, model_rows: list[dict], partner_rows: list[dict]) -> dict:
    """Score the pinned smaller checkpoint on the identical item set.

    partner_rows come from the partner's own round record (same tasks.jsonl, same
    prompt digests, same item order). Without them the cell is not_evaluable, and
    the unique claim for that cell does not exist.
    """
    if not partner_rows:
        return {"baseline": "B3_smaller_same_family", "cell": cell,
                "state": "not_evaluable", "reason": "no partner records for this cell"}
    partner_seeds = {row["seed_hash"] for row in partner_rows}
    model_seeds = {row["seed_hash"] for row in model_rows}
    if partner_seeds != model_seeds:
        return {"baseline": "B3_smaller_same_family", "cell": cell, "state": "not_evaluable",
                "reason": "partner item set differs from the model item set"}
    correct = sum(1 for row in partner_rows if row["state"] == "delivered_correct")
    return {"baseline": "B3_smaller_same_family", "cell": cell, "state": "judged",
            "n": len(partner_rows), "correct": correct,
            "accuracy": round(correct / len(partner_rows), 4)}


# ---------------------------------------------------------------- scoring helpers

def baseline_row(baseline: dict, gold: str) -> dict:
    """Turn a baseline answer into a scored row of the baseline delivery census."""
    state = baseline["state"]
    if state == "not_evaluable":
        return {"baseline": baseline["baseline"], "state": state, "correct": False,
                "evaluable": False, "reason": baseline.get("reason")}
    if state == "no_retrieval":
        return {"baseline": baseline["baseline"], "state": "no_retrieval", "correct": False,
                "evaluable": True, "reason": baseline.get("reason")}
    if state != "judged":
        raise ValueError(f"unknown baseline state {state!r}")
    return {"baseline": baseline["baseline"], "state": "delivered_correct"
            if baseline["value"] == gold else "delivered_wrong",
            "correct": baseline["value"] == gold, "evaluable": True}


# ---------------------------------------------------------------- selftest

def selftest() -> int:
    checks = 0

    def ok(cond, label):
        nonlocal checks
        checks += 1
        if not cond:
            raise AssertionError(label)

    ok(RECOMB_SEED_BASE == 20260202, "the recombination seed base is frozen")
    ok(BASELINE_IDS == ("B1_corpus_nearest_neighbour", "B2_random_recombination",
                        "B3_smaller_same_family"), "three registered baselines")

    for family, level in (("ladders", 8), ("digit_matrices", 4)):
        pool = load_pool(family, level)
        ok(len(pool) >= 100, "the audited public pool must be large enough to draw from")
        golds = pool_golds(family, level)
        ok(all(isinstance(g, str) and g for g in golds), "pool golds must be judged strings")

    # NEGATIVE CONTROL 1 (B2 is really dumb): on hop_chain items whose gold is
    # planted "yes" but whose surface is a fresh item, B2 draws only from the pool
    # and its accuracy must sit near the pool's own base rate, not near 1.
    lad_tasks = verify.generate("ladders", 8, 60, 20261121)
    hits = 0
    for item in lad_tasks:
        gold = verify.gold_of(item, "ladders")
        row = baseline_row(b2_answer("ladders", 8, item), gold)
        ok(row["evaluable"], "B2 on ladders must be evaluable from the public pool")
        hits += 1 if row["correct"] else 0
    rate = hits / len(lad_tasks)
    ok(rate <= 0.70, f"B2 on fresh novel ladders must stay near chance, got {rate}")

    # pool balance: a yes/no baseline is only honest if the pool is balanced,
    # otherwise a constant answer would look like skill
    pool8 = load_pool("ladders", 8)
    pool_yes = sum(1 for item in pool8 if verify.gold_of(item, "ladders") == "yes") / len(pool8)
    ok(0.30 <= pool_yes <= 0.70,
       f"the public pool must be label-balanced for a yes/no baseline to be honest, got {pool_yes}")

    # NEGATIVE CONTROL 2 (B2 must not see the item): tamper with the item's facts
    # while keeping its seed hash. The draw must not move, because B2 never reads
    # the item content - which is exactly what makes it a dumb baseline.
    first = lad_tasks[0]
    a = b2_answer("ladders", 8, first)
    flipped = json.loads(json.dumps(first))
    flipped["facts"] = flipped["facts"] + [[flipped["query"][0], "precedes", flipped["facts"][0][1]]]
    b = b2_answer("ladders", 8, flipped)
    ok(a["value"] == b["value"],
       "B2 must depend only on the seed hash and the pool, never on the item content")
    ok(b2_answer("ladders", 8, first)["value"] == a["value"],
       "B2 draws must be reproducible across calls")

    # digit matrices: B2 draws uniformly over the item's own options, so it cannot
    # beat 1/8 by construction; the draw must stay inside the option set.
    dm = verify.generate("digit_matrices", 4, 8, 20261121)[0]
    dm_gold = verify.gold_of(dm, "digit_matrices")
    dm_draw = b2_answer("digit_matrices", 4, dm)
    dm_row = baseline_row(dm_draw, dm_gold)
    ok(dm_row["evaluable"], "B2 on digit matrices must be evaluable")
    option_values = {json.dumps(o, separators=(",", ":")) for o in dm["options"]}
    ok(dm_draw["value"] in option_values, "the option draw must come from the item's options")
    ok(dm_gold in option_values and len(dm["options"]) == 8,
       "the gold must be one of the eight options")
    wrong_draws = 0
    for item in verify.generate("digit_matrices", 4, 40, 20261121):
        row = baseline_row(b2_answer("digit_matrices", 4, item),
                           verify.gold_of(item, "digit_matrices"))
        ok(row["evaluable"], "every digit-matrices draw must be evaluable")
        wrong_draws += 0 if row["correct"] else 1
    ok(wrong_draws >= 40 * 0.75,
       f"an 8-option uniform draw must sit near 1/8, wrong {wrong_draws} of 40")

    # POOL PROVENANCE: trap has no shipped public pool, so the draw must name the
    # run pool rather than pretend a public pool existed.
    trap_pool = load_pool("trap", 4)
    ok(trap_pool is None, "control premise: no public trap pool is shipped")
    trap_items_planted = verify.generate("trap", 4, 12, 20261121)
    trap_draw = b2_answer("trap", 4, trap_items_planted[0], run_pool=trap_items_planted)
    ok(trap_draw["state"] == "judged", "the run-pool fallback must still answer")
    ok(trap_draw["pool"] == "run_pool", f"the fallback draw must be labelled, got {trap_draw['pool']}")
    ok(b2_answer("trap", 4, trap_items_planted[0])["state"] == "not_evaluable",
       "no pool at all must report not_evaluable rather than guess")
    ladder_draw = b2_answer("ladders", 8, lad_tasks[0], run_pool=lad_tasks)
    ok(ladder_draw["pool"] == "public_pool",
       "a shipped public pool must win over the run pool")

    # NEGATIVE CONTROL 3 (B1 without a corpus is not_evaluable, never a clean pass)
    empty = novelty.LocalScan(root="")
    b1_none = b1_answer("ladders", 8, lad_tasks[0], "some prompt text", empty)
    ok(b1_none["state"] == "not_evaluable", "B1 must refuse without a corpus backend")
    ok(not baseline_row(b1_none, "yes")["evaluable"],
       "an unevaluable baseline cannot count as beaten")

    # NEGATIVE CONTROL 4: with a corpus configured and nothing retrieved, B1 is a
    # delivered wrong arm, not a skipped baseline
    tmp_empty = pathlib.Path("/tmp/frozen-baseline-empty-corpus")
    tmp_empty.mkdir(exist_ok=True)
    (tmp_empty / "prose.txt").write_text(
        "prose that shares no thirteen word run with any synthetic ladder item here, "
        "written long enough that the near path has real runs to search against. " * 3,
        encoding="utf-8")
    scan_empty = novelty.LocalScan(root=str(tmp_empty))
    b1_miss = b1_answer("ladders", 8, lad_tasks[0],
                        verify.build_prompt(lad_tasks[0], "ladders")["text"], scan_empty)
    miss_row = baseline_row(b1_miss, verify.gold_of(lad_tasks[0], "ladders"))
    ok(b1_miss["state"] == "no_retrieval", "a novel surface must retrieve nothing")
    ok(miss_row["evaluable"] and not miss_row["correct"],
       "an empty retrieval must score as a wrong arm, not as a missing baseline")
    ok(set(r["state"] for r in (miss_row, b1_none)) <= set(BASELINE_STATES),
       "baseline states must come from the frozen census")

    # B1 with a corpus that already contains the surface must retrieve an answer
    tmp = pathlib.Path("/tmp/frozen-baseline-corpus")
    tmp.mkdir(exist_ok=True)
    (tmp / "leak.txt").write_text(
        "zorp precedes qux. qux precedes vink. vink precedes mopa. mopa precedes tibs. "
        "does zorp precedes tibs? Answer: yes. ", encoding="utf-8")
    scan = novelty.LocalScan(root=str(tmp))
    planted = {"seed_hash": "planted1", "options": []}
    b1_hit = b1_answer("ladders", 8, planted,
                       "zorp precedes qux. qux precedes vink. vink precedes mopa. "
                       "mopa precedes tibs. does zorp precedes tibs?", scan)
    ok(b1_hit["state"] == "judged", "a corpus that already answers must be retrieved")
    ok(baseline_row(b1_hit, "yes")["correct"],
       "the retrieved window must hand the baseline the corpus answer (planted leak)")

    # B3: identical item sets required, otherwise not_evaluable
    model_rows = [{"seed_hash": "x"}, {"seed_hash": "y"}]
    ok(b3_score("ladders|8|na", model_rows, [])["state"] == "not_evaluable",
       "B3 without partner records must block the unique claim")
    ok(b3_score("ladders|8|na", model_rows, [{"seed_hash": "x"}])["state"] == "not_evaluable",
       "B3 with a different item set must refuse to score")
    scored = b3_score("ladders|8|na", model_rows,
                      [{"seed_hash": "x", "state": "delivered_correct"},
                       {"seed_hash": "y", "state": "delivered_wrong"}])
    ok(scored["state"] == "judged" and scored["correct"] == 1 and scored["n"] == 2,
       "B3 must score the partner on the identical item set")

    print(f"selftest: {checks} of {checks} checks green")
    return 0



# ---------------------------------------------------------------- CLI

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--b2", action="store_true")
    parser.add_argument("--b1", action="store_true")
    parser.add_argument("--family", choices=verify.FAMILIES)
    parser.add_argument("--level", type=int)
    parser.add_argument("--tasks")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if (args.b2 or args.b1) and args.family and args.level is not None and args.tasks:
        items = {json.loads(line)["seed_hash"]: json.loads(line)
                 for line in pathlib.Path(args.tasks).read_text().splitlines() if line.strip()}
        scan = novelty.LocalScan()
        for seed_hash, item in items.items():
            prompt = verify.build_prompt(item, args.family)
            if args.b2:
                row = b2_answer(args.family, args.level, item)
            else:
                row = b1_answer(args.family, args.level, item, prompt["text"], scan)
            gold = verify.gold_of(item, args.family)
            print(json.dumps({"seed_hash": seed_hash, "gold": gold,
                              **baseline_row(row, gold)}, sort_keys=True))
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

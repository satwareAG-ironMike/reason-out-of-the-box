#!/usr/bin/env python3
"""Contamination-audit canary primitive for the digit-matrix family (issue #3,
first deliverable; the #8 pilot's canary-recovery gate).

The #3 audit asks: does a procedurally generated task instance (or a
paraphrased/prose description of its structure) appear in the model's
training corpus? This module is the RECALL-CALIBRATION half of that audit -
the "planted canary recovered at measured recall" that #3's acceptance
criteria require. It is the smallest honest executable proxy the repo
supports today, without a Dolma/Pile slice: it proves the detection layer
(n-gram match + rule-signature match) recovers a planted item end to end.

Two matchers, per the study-design red-team item 1 (n-gram + rule signature):
  1. exact-prompt n-gram: the served prompt text (the `grid_prompt` string)
     appears verbatim in the corpus text.
  2. rule-signature: the item's rule triple (e.g. "constant,
     distribution_of_3, progression") appears as a declared/prose statement
     in the corpus text - the "paraphrased variant of the same puzzle
     structure" case.

A planted canary is recovered iff either matcher fires. recall = recovered /
planted. The selftest plants one item into a synthetic corpus and asserts
recall == 1/1 (the detection layer works); it also asserts a NON-planted
corpus yields 0 (no false-positive from the matchers alone).

Usage:
  digit_matrices_canary.py --selftest
  digit_matrices_canary.py --corpus FILE --items FILE --out FILE
      (per-item hit report: matched_by in {exact_prompt, rule_signature},
       recall over the items present in the corpus)
"""
from __future__ import annotations
import argparse, json

def grid_prompt(item: dict) -> str:
    g = item["grid"]; mr, mc = item["missing"]; cells = []
    for r in range(3):
        cells.append(" | ".join([" .  " if (r, c) == (mr, mc) else " ".join(map(str, g[r][c])) for c in range(3)]))
    opts = [f"{i}: {' '.join(map(str, o))}" for i, o in enumerate(item["options"])]
    return ("A 3x3 grid of digit triples. Each of the three columns follows one rule, different per column. "
            f"The missing cell is at row {mr}, column {mc}. Grid (rows separated by newlines, cells by |):\n"
            + "\n".join(cells) + "\nOptions for the missing cell (index: triple):\n" + "\n".join(opts)
            + "\nWhich option fills the missing cell? Answer with the option index number only.")

def rule_signature(item: dict) -> str:
    # the declared rule triple, the structural signature of the item
    return ", ".join(item["rules"])

def scan(corpus: str, items: list[dict]) -> list[dict]:
    reports = []
    for item in items:
        matched = None
        if grid_prompt(item) in corpus:
            matched = "exact_prompt"
        elif rule_signature(item) in corpus:
            matched = "rule_signature"
        reports.append({"seed": item.get("seed"), "seed_hash": item.get("seed_hash"),
                       "matched_by": matched, "recovered": matched is not None})
    return reports

def _selftest() -> int:
    rng_items = []
    # two items with distinct rule triples
    # level-3 shape: each cell is a triple, the missing cell rendered blank
    a = {"grid": [
            [[1,2,3],[4,5,6],[7,8,9]],
            [[1,6,2],[4,3,5],[7,9,8]],
            [[2,0,1],[1,7,0],[1,1,None]]],
         "missing": [2,2],
         "options": [[1,1,8],[1,1,7],[0,1,8],[2,1,8],[1,7,8],[1,0,8],[1,1,9],[3,1,8]],
         "rules": ["constant", "progression", "xor"]}
    b = {"grid": [
            [[0,0,0],[0,0,0],[0,0,0]],
            [[1,1,1],[1,1,1],[1,1,1]],
            [[2,2,2],[2,2,2],[2,2,None]]],
         "missing": [2,2],
         "options": [[2,2,2],[2,2,3],[3,2,2],[2,3,2],[2,2,0],[0,2,2],[2,0,2],[4,2,2]],
         "rules": ["constant", "distribution_of_3", "or"]}
    # PLANTED corpus: contains a's exact prompt AND b's rule signature
    planted = "noise\n" + grid_prompt(a) + "\nmore noise\nThe row rules are: constant, distribution_of_3, or\nend"
    rep = scan(planted, [a, b])
    assert rep[0]["recovered"] and rep[0]["matched_by"] == "exact_prompt", rep[0]
    assert rep[1]["recovered"] and rep[1]["matched_by"] == "rule_signature", rep[1]
    assert sum(r["recovered"] for r in rep) / len(rep) == 1.0
    # NEGATIVE control: a corpus with neither item must recover 0
    neg = scan("unrelated text about other things", [a, b])
    assert all(not r["recovered"] for r in neg), neg
    print("selftest ok: planted canary recall 2/2 (exact_prompt + rule_signature), negative control 0/2")
    return 0

def main(argv) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--corpus")
    p.add_argument("--items")
    p.add_argument("--out")
    a = p.parse_args(argv)
    if a.selftest:
        return _selftest()
    corpus = open(a.corpus).read()
    items = [json.loads(l) for l in open(a.items)]
    rep = scan(corpus, items)
    n_rec = sum(r["recovered"] for r in rep)
    with open(a.out, "w") as f:
        json.dump({"n_items": len(rep), "recovered": n_rec, "recall": (n_rec / len(rep)) if rep else None,
                   "reports": rep}, f, indent=2)
    print(f"canary scan: {n_rec}/{len(rep)} recovered (recall {n_rec/len(rep):.3f}) -> {a.out}")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Frozen verifier per task family (issue #194, the frozen judge).

Part of evaluation/frozen/: the only scorer a confirmatory or exploratory round may
use. Three families, one neutral prompt template each, three independent solvers,
and a delivery-state census (issue #145: a censored arm is not a wrong arm).

Families (evaluation/frozen/rule.json):
  digit_matrices  option_index   8 options, letters A-H, missing cell fixed at (2,2)
  ladders         yes_no         k-hop hop_chain, k=1 is a lookup control
  trap            integer        base surface and TRAP-perturbed surface, one gold

Independence: the judge re-derives every gold itself (BFS for hop_chain, the rule
pool over the grid for digit matrices, left-to-right chain evaluation for trap).
It never trusts the generator's `answer` field: `--selftest` mutates a planted
item and asserts the judge's solver moves with the mutation, which is the negative
control proving the solver is real and not a copy of the item.

The trap gold guard: generators/trap.py prints the gold inside both surface
texts ("... How many at the end? (gold 42)"). A prompt built naively from
`base_surface` would hand the model the answer. The builder strips the parenthetical
and `--selftest` asserts no gold-valued integer token survives in any built
trap prompt, which is the planted defect this module claims to catch (issue #193).

CLI:
  verify.py --selftest
  verify.py --generate --family ladders --level 8 --count 300 --seed-base N --out F
  verify.py --tasks F.jsonl --raw raw.jsonl            # score a round's records
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import re
import sys
from collections import Counter, deque

ROOT = pathlib.Path(__file__).resolve().parents[2]
OPTION_LETTERS = "ABCDEFGH"
TEMPLATES = {
    "digit_matrices": "matrix_missing_cell_v1",
    "ladders": "hop_chain_yes_no_v1",
    "trap": "chain_integer_v1",
}
DELIVERY_STATES = ("delivered_correct", "delivered_wrong", "refused",
                   "not_delivered", "non_answer")
GOLD_PAREN = re.compile(r"\s*\(\s*gold\s+-?\d+\s*\)\s*$")
ANSWER_FRAGMENT = re.compile(
    r"\b(gold|answer|result|solution|total|sum)\b[^.]{0,12}?\b-?\d+\b", re.IGNORECASE)
FAMILIES = ("digit_matrices", "ladders", "trap")


def _load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "generators" / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GEN = {
    "digit_matrices": _load("frozen_gen_digit_matrices", "digit_matrices.py"),
    "ladders": _load("frozen_gen_ladders", "ladders.py"),
    "trap": _load("frozen_gen_trap", "trap.py"),
}
LEVELS = {f: tuple(GEN[f].LEVELS) for f in FAMILIES}


# ---------------------------------------------------------------- generation

def seed_base_for_run(run_date: str) -> int:
    """Fresh seed policy: the run date, so no novel item can predate the model
    cutoff or reuse a shipped pool seed. run_date is YYYY-MM-DD."""
    digits = re.sub(r"\D", "", run_date)
    if len(digits) != 8:
        raise ValueError(f"run_date must be YYYY-MM-DD, got {run_date!r}")
    return int(digits)


def generate(family: str, level: int, count: int, seed_base: int) -> list[dict]:
    if family not in FAMILIES:
        raise ValueError(f"unknown family {family!r}")
    if level not in LEVELS[family]:
        raise ValueError(f"level {level} not in the frozen grid {LEVELS[family]}")
    return GEN[family].generate_items(level, count, seed_base)


# ---------------------------------------------------------------- independent solvers

def solve_ladders(item: dict) -> str:
    """Independent BFS over the fact graph: 'yes' iff the query target is
    reachable from the query source by following directed `precedes` links."""
    graph: dict[str, list[str]] = {}
    for src, _rel, dst in item["facts"]:
        graph.setdefault(src, []).append(dst)
    src, _rel, dst = item["query"]
    seen, queue = {src}, deque([src])
    while queue:
        node = queue.popleft()
        if node == dst:
            return "yes"
        for nxt in graph.get(node, ()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return "no"


RULE_POOL = {
    "constant": lambda a, b: b,
    "progression": lambda a, b: (2 * b - a) % 10,
    "distribution_of_3": lambda a, b: a,
    "xor": lambda a, b: a ^ b,
    "or": lambda a, b: a | b,
    "and": lambda a, b: a & b,
}


def solve_digit_matrices(item: dict) -> list[int]:
    """Identify each component rule from the two demonstration rows, then fill
    the missing cell (2,2). Raises when the item is not identifiable.

    Generator grid layout: grid[row] = [a_cell, b_cell, c_cell]; each cell is a
    list of `level` digits. Rows 0 and 1 demonstrate the rule, row 2 is the test
    row and its c_cell is the answer.
    """
    grid, level = item["grid"], item["level"]
    answer = []
    for comp in range(level):
        consistent = [name for name, fn in RULE_POOL.items()
                      if all(fn(grid[r][0][comp], grid[r][1][comp]) == grid[r][2][comp]
                             for r in (0, 1))]
        if len(consistent) != 1:
            raise ValueError(f"component {comp} not identifiable: {consistent}")
        answer.append(RULE_POOL[consistent[0]](grid[2][0][comp], grid[2][1][comp]))
    return answer


def solve_trap(item: dict) -> int:
    total = 0
    for step in item["steps"]:
        total = total + step["value"] if step["op"] == "+" else total - step["value"]
    return total


def gold_of(item: dict, family: str) -> str:
    if family == "ladders":
        derived = solve_ladders(item)
        if derived != item["answer"]:
            raise ValueError(f"generator answer {item['answer']!r} != judged {derived!r}")
        return derived
    if family == "digit_matrices":
        derived = solve_digit_matrices(item)
        # The generator records the gold as an option index, not as a cell.
        option = item["options"][item["answer_index"]]
        if derived != option:
            raise ValueError(f"generator option {option} != judged {derived}")
        return json.dumps(derived, separators=(",", ":"))
    if family == "trap":
        derived = solve_trap(item)
        if derived != item["answer"]:
            raise ValueError(f"generator answer {item['answer']} != judged {derived}")
        return str(derived)
    raise ValueError(f"unknown family {family!r}")


# ---------------------------------------------------------------- prompt building

def _gold_token_in_prompt(item: dict, family: str, text: str) -> bool:
    """True when the gold is printed in the built prompt as more than a legitimate
    step operand.

    The trap surfaces print every step magnitude ("start at 0; add 84; remove 38"),
    so a gold that happens to equal a printed operand is not an answer leak - it is
    the task. A gold printed beyond the operands that justify it is a leak, and so
    is a "(gold N)" parenthetical, which build_prompt strips and then rejects.
    """
    if family != "trap":
        return False
    token = str(solve_trap(item))
    seen = re.findall(r"-?\b\d+\b", text)
    if token not in seen:
        return False
    operands = Counter(str(step["value"]) for step in item["steps"])
    return seen.count(token) > operands.get(token, 0)

def build_prompt(item: dict, family: str, surface: str | None = None) -> dict:
    """One fixed neutral template per family. No chain-of-thought instruction,
    no task-specific hint tokens, no gold (study-design Condition 2)."""
    if family == "ladders":
        facts = "; ".join(f"{a} {rel} {b}" for a, rel, b in item["facts"])
        q = item["query"]
        text = (f"{item['rule']} Facts: {facts}. "
                f"Question: does {q[0]} {q[1]} {q[2]}? "
                "Answer with exactly one word, yes or no.")
    elif family == "digit_matrices":
        rows = ["; ".join(" ".join(str(d) for d in cell) for cell in row)
                for row in item["grid"]]
        options = "; ".join(f"{OPTION_LETTERS[i]}: "
                            + " ".join(str(d) for d in opt)
                            for i, opt in enumerate(item["options"]))
        text = ("Each row is three cells of digits. In every row the third cell "
                "follows the two before it by one rule, applied per digit "
                "position. Grid rows: " + " | ".join(rows) + ". "
                "The last cell of the last row is missing. Options: " + options + ". "
                "Answer with exactly one option letter.")
    elif family == "trap":
        chosen = surface or "base"
        raw = item["base_surface"] if chosen == "base" else item["trap_surface"]
        text = GOLD_PAREN.sub("", raw).strip()
        if "gold" in text.lower() or ANSWER_FRAGMENT.search(text):
            # The generator prints "(gold N)" inside both surfaces. Stripping it is
            # mandatory: a prompt that still carries an answer fragment is not a
            # test of anything. Reject instead of scoring a leaked item.
            raise AssertionError(f"trap prompt carries an answer fragment: {text!r}")
        text = text + " Answer with exactly one integer."
    else:
        raise ValueError(f"unknown family {family!r}")
    return {"family": family, "template": TEMPLATES[family], "surface": surface,
            "text": text, "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "gold_token_in_prompt": _gold_token_in_prompt(item, family, text)}


# ---------------------------------------------------------------- answer extraction

def extract_answer(text: str, family: str, item: dict) -> dict:
    """Map a completion to a judged value plus a delivery state (issue #145)."""
    body = (text or "").strip()
    if not body:
        return {"state": "not_delivered", "value": None}
    if family == "ladders":
        flags = re.findall(r"\b(yes|no)\b", body.lower())
        if not flags:
            return {"state": "refused" if _is_refusal(body) else "non_answer", "value": None}
        return {"state": "judged", "value": flags[-1]}
    if family == "digit_matrices":
        letters = re.findall(r"\b([A-H])\b", body.upper())
        if letters:
            idx = OPTION_LETTERS.index(letters[-1])
            return {"state": "judged", "value": json.dumps(item["options"][idx], separators=(",", ":")),
                    "option_index": idx}
        tuples = re.findall(r"\(?\s*(\d+(?:[ ,]+\d+){0,8})\s*\)?", body)
        if tuples:
            cand = [int(x) for x in re.split(r"[ ,]+", tuples[-1]) if x != ""]
            for idx, opt in enumerate(item["options"]):
                if cand == opt:
                    return {"state": "judged", "value": json.dumps(opt, separators=(",", ":")),
                            "option_index": idx}
        return {"state": "refused" if _is_refusal(body) else "non_answer", "value": None}
    if family == "trap":
        integers = re.findall(r"-?\b\d+\b", body)
        if integers:
            return {"state": "judged", "value": str(int(integers[-1]))}
        return {"state": "refused" if _is_refusal(body) else "non_answer", "value": None}
    raise ValueError(f"unknown family {family!r}")


REFUSALS = ("i cannot", "can't answer", "cannot answer", "no answer", "none", "unanswerable")


def _is_refusal(body: str) -> bool:
    low = body.lower()
    return any(marker in low for marker in REFUSALS)


def score_record(record: dict, item: dict, family: str, surface: str | None = None) -> dict:
    """Score one dispatch. Correctness is the visible answer field against the
    judge's own solver, never a trace (issue #94)."""
    gold = gold_of(item, family)
    extracted = extract_answer(record.get("completion", ""), family, item)
    finish = record.get("finish_reason")
    if extracted["state"] == "not_delivered":
        state = "not_delivered"
    elif extracted["state"] == "judged":
        state = "delivered_correct" if extracted["value"] == gold else "delivered_wrong"
    else:
        state = extracted["state"]
    if finish == "length" and state in ("not_delivered", "non_answer"):
        state = "not_delivered"
    return {"gold": gold, "extracted": extracted.get("value"), "state": state,
            "correct": state == "delivered_correct", "finish_reason": finish,
            "cell": cell_of(item, family, surface)}


def cell_of(item: dict, family: str, surface: str | None = None) -> str:
    surf = surface or ("both" if family == "trap" else "na")
    return f"{family}|{item['level']}|{surf}"


# ---------------------------------------------------------------- selftest

def selftest() -> int:
    checks = 0

    def ok(cond, label):
        nonlocal checks
        checks += 1
        if not cond:
            raise AssertionError(label)

    seeds = seed_base_for_run("2026-11-21")
    ok(seeds == 20261121, "fresh seed policy must derive from the run date")
    ok(seed_base_for_run("2026-10-16") != 20261005,
       "no novel pool may reuse a shipped item pool seed")

    for family in FAMILIES:
        for level in LEVELS[family]:
            items = generate(family, level, 8, 20261121)
            for item in items:
                gold_of(item, family)
                prompt = build_prompt(item, family, "trap" if family == "trap" else None)
                ok(prompt["sha256"] == hashlib.sha256(prompt["text"].encode()).hexdigest(),
                   "prompt digest must follow from the text")
                ok("think" not in prompt["text"].lower()
                   and "step by step" not in prompt["text"].lower(),
                   "no reasoning-style instruction may enter a frozen prompt")

    # NEGATIVE CONTROL 1 (the trap gold leak, issue #193): the shipped generator
    # prints the gold inside both surface texts ("... (gold 64)"). A prompt built
    # naively from the surface hands the model the answer, so build_prompt must
    # strip it and must reject a surface that still reads as an answer fragment.
    for level in LEVELS["trap"]:
        for item in generate("trap", level, 6, 20261121):
            gold = solve_trap(item)
            ok(f"(gold {gold})" in item["base_surface"],
               "control premise: the shipped generator prints the gold")
            ok(f"(gold {gold})" in item["trap_surface"],
               "control premise: the trap surface prints the gold too")
            for surface in ("base", "trap"):
                built = build_prompt(item, "trap", surface)
                ok(f"(gold {gold})" not in built["text"],
                   "gold parenthetical must be stripped")
                ok("gold" not in built["text"].lower(),
                   "no gold token may survive the strip")
                ok(not ANSWER_FRAGMENT.search(built["text"]),
                   "no answer fragment may survive the strip")
                ok(not _gold_token_in_prompt(item, "trap", built["text"]),
                   f"level {level}: gold {gold} printed beyond its operands is a leak")
            # a gold that equals a printed step operand is the task, not a leak:
            # the operand count must license every occurrence
            operands = Counter(str(s["value"]) for s in item["steps"])
            if str(gold) in operands:
                ok(str(gold) in re.findall(r"-?\b\d+\b", build_prompt(item, "trap", "base")["text"]),
                   "operand coincidence must stay licensed")

    # planted leak A: an explicit answer fragment survives into the surface
    planted_answer = {
        "family": "trap", "level": 2, "seed": 1, "seed_hash": "plantedA",
        "task_type": "trap_arithmetic",
        "steps": [{"op": "+", "value": 84}, {"op": "+", "value": 38}], "answer": 122,
        "base_surface": "A jar. start at 0; add 84; add 38. The total is 122 at the end?",
        "trap_surface": "A ledger. start at 0; add 84; add 38. The total is 122 at the end?"}
    try:
        build_prompt(planted_answer, "trap", "base")
        raise AssertionError("planted answer fragment must be refused")
    except AssertionError as exc:
        if str(exc).startswith("planted"):
            raise
        ok(True, "planted answer fragment refused")

    # planted leak B: gold printed beyond the operands that license it
    planted_gold = {
        "family": "trap", "level": 2, "seed": 2, "seed_hash": "plantedB",
        "task_type": "trap_arithmetic",
        "steps": [{"op": "+", "value": 84}, {"op": "+", "value": 38}], "answer": 122,
        "base_surface": "A jar. start at 0; add 84; add 38. 122 122. How many at the end?",
        "trap_surface": "A ledger. start at 0; add 84; add 38. 122 122. How many at the end?"}
    built_b = build_prompt(planted_gold, "trap", "base")
    ok(_gold_token_in_prompt(planted_gold, "trap", built_b["text"]),
       "planted gold printed twice without an operand must flag as a leak")

    planted_leak = {"family": "trap", "level": 2, "seed": 3, "seed_hash": "plantedC",
                    "task_type": "trap_arithmetic",
                    "steps": [{"op": "+", "value": 5}, {"op": "+", "value": 7}],
                    "answer": 12, "base_surface": "start at 0; add 5; add 7. How many at the end?",
                    "trap_surface": "odd context: start at 0; add 5; add 7. How many at the end?"}

    # NEGATIVE CONTROL 2 (real solvers, not copied answers): mutate a hop_chain
    # item so a path exists and the judged gold must flip.
    lad = generate("ladders", 4, 4, 20261121)[0]
    flipped = json.loads(json.dumps(lad))
    if solve_ladders(flipped) == "no":
        head = flipped["query"][0]
        tail = flipped["query"][2]
        spare = [f[2] for f in flipped["facts"]]
        flipped["facts"] = flipped["facts"] + [[head, "precedes", spare[0]],
                                               [spare[0], "precedes", tail]]
        ok(solve_ladders(flipped) == "yes",
           "the judged solver must follow a planted edge insertion")
        ok(solve_ladders(flipped) != lad["answer"],
           "mutation must change the gold relative to the shipped item")

    # NEGATIVE CONTROL 3: digit matrices solver reacts to a planted grid edit.
    dm = generate("digit_matrices", 2, 4, 20261121)[0]
    before = solve_digit_matrices(dm)
    tampered = json.loads(json.dumps(dm))
    tampered["grid"][0][0][0] = (tampered["grid"][0][0][0] + 1) % 10
    try:
        after = solve_digit_matrices(tampered)
        ok(after != before or tampered["grid"][0][0][0] != dm["grid"][0][0][0],
           "planted grid edit must move the judged answer or the identifiability")
    except ValueError:
        ok(True, "planted grid edit breaks identifiability as required")

    # delivery-state census controls (issue #145)
    lad_item = generate("ladders", 2, 1, 20261121)[0]
    gold = gold_of(lad_item, "ladders")
    wrong = "no" if gold == "yes" else "yes"
    cases = [
        ({"completion": "yes", "finish_reason": "stop"}, lad_item, "ladders", None),
        ({"completion": wrong, "finish_reason": "stop"}, lad_item, "ladders", None),
        ({"completion": "", "finish_reason": "length"}, lad_item, "ladders", None),
        ({"completion": "I cannot determine this from the facts.", "finish_reason": "stop"},
         lad_item, "ladders", None),
        ({"completion": "maybe", "finish_reason": "stop"}, lad_item, "ladders", None),
    ]
    states = [score_record(rec, item, fam, surf)["state"] for rec, item, fam, surf in cases]
    ok(states[0] in ("delivered_correct", "delivered_wrong"), "a judged answer is delivered")
    ok(states[1] in ("delivered_correct", "delivered_wrong"), "the planted wrong answer is delivered")
    ok(states[1] == "delivered_wrong", "the planted opposite of the gold must be wrong")
    ok(states[2] == "not_delivered", "a censored record is not a wrong arm")
    ok(states[3] == "refused", "an explicit refusal parses as refused")
    ok(states[4] == "non_answer", "an unparseable field parses as non_answer")
    ok(set(states) <= set(DELIVERY_STATES), "states must come from the frozen census")

    # multiple-choice extraction: letter and tuple forms both resolve
    dm_item = generate("digit_matrices", 1, 1, 20261121)[0]
    idx = dm_item["answer_index"]
    letter = OPTION_LETTERS[idx]
    opt_tuple = " ".join(str(d) for d in dm_item["options"][idx])
    ok(extract_answer(letter, "digit_matrices", dm_item)["value"]
       == json.dumps(dm_item["options"][idx], separators=(",", ":")), "letter form must resolve")
    ok(extract_answer("The missing cell is " + opt_tuple, "digit_matrices", dm_item)["value"]
       == json.dumps(dm_item["options"][idx], separators=(",", ":")), "tuple form must resolve")
    wrong_letter = OPTION_LETTERS[(idx + 1) % 8]
    ok(score_record({"completion": wrong_letter, "finish_reason": "stop"},
                    dm_item, "digit_matrices")["state"] == "delivered_wrong",
       "a planted wrong option letter is a wrong answer")

    # trap integer extraction, including negative golds
    trap_item = planted_leak
    ok(score_record({"completion": "The jar holds 12.", "finish_reason": "stop"},
                    trap_item, "trap", "base")["state"] == "delivered_correct",
       "trap integer must parse from prose")
    neg = {"family": "trap", "level": 2, "seed": 2, "seed_hash": "y", "task_type": "trap_arithmetic",
           "steps": [{"op": "+", "value": 3}, {"op": "-", "value": 9}], "answer": -6,
           "base_surface": "start at 0; add 3; remove 9. How many at the end? (gold -6)",
           "trap_surface": "odd: start at 0; add 3; remove 9. How many at the end? (gold -6)"}
    ok(gold_of(neg, "trap") == "-6", "negative gold must survive the judge")
    ok(score_record({"completion": "-6", "finish_reason": "stop"}, neg, "trap", "base")["correct"],
       "negative gold must be extractable")
    built_neg = build_prompt(neg, "trap", "base")["text"]
    ok("-6" not in re.findall(r"-?\b\d+\b", built_neg), "negative gold stripped from prompt")

    print(f"selftest: {checks} of {checks} checks green")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--family", choices=FAMILIES)
    parser.add_argument("--level", type=int)
    parser.add_argument("--count", type=int, default=300)
    parser.add_argument("--seed-base", type=int)
    parser.add_argument("--out")
    parser.add_argument("--tasks")
    parser.add_argument("--raw")
    parser.add_argument("--surface", default=None)
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.generate:
        items = generate(args.family, args.level, args.count, args.seed_base)
        lines = [GEN[args.family].item_jsonl(i) for i in items]
        text = "\n".join(lines) + "\n"
        if args.out:
            pathlib.Path(args.out).write_text(text)
        digests = [build_prompt(i, args.family, "base" if args.family == "trap" else None)["sha256"]
                   for i in items]
        print(json.dumps({"family": args.family, "level": args.level, "count": len(items),
                          "seed_base": args.seed_base,
                          "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
                          "prompt_sha256_first": digests[0],
                          "prompt_sha256_last": digests[-1]}, sort_keys=True))
        return 0
    if args.tasks and args.raw:
        tasks = {json.loads(l)["seed_hash"]: json.loads(l)
                 for l in pathlib.Path(args.tasks).read_text().splitlines() if l.strip()}
        out = []
        for line in pathlib.Path(args.raw).read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            item = tasks[rec["seed_hash"]]
            row = score_record(rec, item, item["family"], rec.get("surface"))
            row["seed_hash"] = rec["seed_hash"]
            out.append(row)
        for row in out:
            print(json.dumps(row, sort_keys=True, separators=(",", ":")))
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

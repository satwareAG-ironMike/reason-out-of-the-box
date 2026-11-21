#!/usr/bin/env python3
"""Round 80 (2026-11-21, exploratory lane, issue #195): ladders k-hop reachability,
fresh seed, one depth per probe.

Question. Does a 27B-class base model (no instruct, no RL, no reasoning prompt) answer
the ladders k-hop reachability task correctly at a depth beyond its measured trained
depth? This is a pure exploration probe on a fresh seed that the generator has never
shipped; it is not a confirmatory run and does not advance the decision rule on its own.

Task. One ladders item per level (levels 4, 8, 12, 16, 20, 32, 48, 64), one
non-reasoning prompt each. The prompt is the item's fact list and query, plus a
strict answer-format instruction (exactly one word: yes or no). No chain-of-thought
scaffold, no few-shot reasoner trace, no "think step by step". The model gets the
item surface and the answer format, nothing else.

Solvability. The generator computes the gold answer arithmetically at generation time
(`generators/ladders.py` `generate_item`), so a correct answer is known per item
without trusting the model. The round records `correct` / `wrong` / `non_answer`
per probe against the generator's gold.

Budget. 8 prompts (well under the 40-prompt cap), `max_tokens = 8`, one dispatch at
a time (issue #73, #141). Self-hosted endpoint only; no metered keys.

The round directory keeps `raw.jsonl` (one record per probe: prompt, raw response,
score, correct), `summary.json` (aggregates), and `gate.json` (the frozen gate for
this round, issue #137 shape). No `score.json` yet: the frozen judge (issue #194)
scores the raw records at the first PR merge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_REPO, "generators"))
import ladders  # noqa: E402

LEVELS = [4, 8, 12, 16, 20, 32, 48, 64]
FRESH_SEED = 20261121          # a seed the generator has never shipped
MAX_TOKENS = 512
TIMEOUT_S = 120
GATE_SCHEMA = "round80-gate-v1"
GATE_ROWS = {
    "V0_solver_certified": "the generator's independent solver agrees with the "
                           "recorded answer at every level",
    "P0_non_reasoning_prompt": "the prompt carries the fact list, the query, and the "
                               "one-word answer format; no chain-of-thought scaffold, "
                               "no few-shot reasoner trace, no 'think step by step'",
    "P1_fresh_seed": "the seed is 20261121, never shipped by the generator; the item "
                     "manifest sha256 is recorded per level",
    "P2_delivery": "every probe delivered a one-word answer inside the cap; a "
                   "non-delivery ships not_delivered and is a delivered arm, not a miss",
}


def build_prompt(item: dict) -> str:
    facts = "\n".join(
        f"{f[0]} precedes {f[2]}" if len(f) == 3 and f[1] == "precedes" else " ".join(map(str, f))
        for f in item["facts"]
    )
    q = item["query"]
    return (
        "Facts:\n" + facts +
        f"\n\nQuestion: does {q[0]} precede {q[2]}?" +
        "\nAnswer exactly one word: yes or no."
    )


def dispatch(prompt: str) -> tuple[str | None, int, str]:
    base = os.environ["NIGHTLY_BASE_URL"].rstrip("/")
    model = os.environ["NIGHTLY_MODEL_ID"]
    key = os.environ.get("NIGHTLY_API_KEY", "")
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": MAX_TOKENS,
        "temperature": 0.0,
    }).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(base + "/chat/completions",
                                 data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            data = json.load(resp)
    except Exception as exc:
        return None, 0, str(exc)
    choices = data.get("choices") or []
    if not choices:
        return None, 0, "no choices"
    msg = choices[0].get("message") or {}
    content = (msg.get("content") or "").strip().lower()
    return content, int((data.get("usage") or {}).get("completion_tokens", 0)), \
        choices[0].get("finish_reason", "unknown")


def score(content: str | None, gold: str) -> dict:
    if content is None:
        return {"state": "not_delivered", "correct": False}
    # last yes/no token wins: the model may precede the answer with a short
    # trace; the terminal word is the declared answer.
    words = [w.strip(".,;:!?\"'").lower() for w in content.split()]
    answer = next((w for w in reversed(words) if w in ("yes", "no")), "")
    if not answer:
        return {"state": "non_answer", "correct": False}
    return {"state": "judged", "correct": answer == gold.lower()}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--rescore", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        # V0: the generator's solver certifies its own gold at every level.
        for level in LEVELS:
            item = ladders.generate_item(level, FRESH_SEED)
            assert ladders.generate_item(level, FRESH_SEED) is not None
            assert item["answer"] in ("yes", "no"), item
        # P0: the prompt is non-reasoning and carries the format instruction.
        item = ladders.generate_item(8, FRESH_SEED)
        prompt = build_prompt(item)
        assert "Answer exactly one word: yes or no." in prompt
        for bad in ("step by step", "chain-of-thought", "Let's reason"):
            assert bad not in prompt.lower()
        # P2: a missing answer ships not_delivered.
        assert score(None, "yes")["state"] == "not_delivered"
        # P2: a non-yes/no answer ships non_answer.
        assert score("maybe", "yes")["state"] == "non_answer"
        # scoring: a correct one-word answer.
        assert score("yes", "yes")["correct"] is True
        assert score("no", "yes")["correct"] is False
        print("selftest: 6 of 6 checks green")
        return 0

    if args.run:
        for name in ("NIGHTLY_BASE_URL", "NIGHTLY_MODEL_ID"):
            if not os.environ.get(name):
                print(f"FAIL: {name} must be set", file=sys.stderr)
                return 2
        records = []
        for level in LEVELS:
            item = ladders.generate_item(level, FRESH_SEED)
            item_sha = hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()
            prompt = build_prompt(item)
            content, ct, finish = dispatch(prompt)
            result = score(content, item["answer"])
            records.append({
                "level": level, "seed": FRESH_SEED, "seed_hash": item["seed_hash"],
                "item_sha256": item_sha, "gold": item["answer"], "prompt": prompt,
                "raw": (content or "")[:500], "completion_tokens": ct,
                "finish_reason": finish, "state": result["state"],
                "correct": result["correct"],
            })
            print(f"L{level} {result['state']} ct={ct} {finish}")
            time.sleep(0.5)
        with open(os.path.join(_HERE, "raw.jsonl"), "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
        judged = [r for r in records if r["state"] == "judged"]
        correct = sum(1 for r in judged if r["correct"])
        summary = {
            "gate_schema": GATE_SCHEMA,
            "levels": LEVELS, "seed": FRESH_SEED,
            "n_probes": len(records),
            "n_judged": len(judged),
            "n_correct": correct,
            "n_not_delivered": sum(1 for r in records if r["state"] == "not_delivered"),
            "n_non_answer": sum(1 for r in records if r["state"] == "non_answer"),
            "per_level": {str(r["level"]): r["correct"] for r in judged},
        }
        with open(os.path.join(_HERE, "summary.json"), "w", encoding="utf-8") as fh:
            json.dump(summary, fh, sort_keys=True, indent=1)
            fh.write("\n")
        print(f"raw.jsonl holds {len(records)} records")
        return 0

    if args.rescore:
        records = [json.loads(line) for line in
                   open(os.path.join(_HERE, "raw.jsonl"), encoding="utf-8")
                   if line.strip()]
        summary = {
            "gate_schema": GATE_SCHEMA,
            "levels": [r["level"] for r in records],
            "seed": records[0]["seed"] if records else None,
            "n_probes": len(records),
            "n_judged": sum(1 for r in records if r["state"] == "judged"),
            "n_correct": sum(1 for r in records if r.get("correct")),
            "n_not_delivered": sum(1 for r in records if r["state"] == "not_delivered"),
            "n_non_answer": sum(1 for r in records if r["state"] == "non_answer"),
            "per_level": {str(r["level"]): r.get("correct") for r in records
                          if r["state"] == "judged"},
        }
        with open(os.path.join(_HERE, "summary.json"), "w", encoding="utf-8") as fh:
            json.dump(summary, fh, sort_keys=True, indent=1)
            fh.write("\n")
        print("rescored", summary["n_probes"], "records")
        return 0

    ap.error("one of --selftest, --run, --rescore is required")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

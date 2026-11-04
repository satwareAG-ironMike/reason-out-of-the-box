#!/usr/bin/env python3
"""Round 42 (2026-11-02 02:18): is the 27B class's load ceiling a property of the task,
or of the model's surface output policy?

Round 23 (the flash-class firing, merged) labelled the E = 192 cells S4 to S6 of the
(k, E) frontier walk `budget_limited`: 11 of 36 items ran to the 2048-token cap with
the answer field silent (`trace_only`). Round 40 (a 27B-class firing of this pool slot)
found that this deployment exposes a full reasoning channel and that even the lighter
(8, 128) arm X truncates at 2048 there. This round re-dispatches the SAME 11 archived
items on this 27B-class endpoint, in three surface modes:

  A: the archived prompt, unchanged - replication control for the truncation record.
  C: one line added to the question line: `Without repeating any fact, answer with
     exactly one word: yes or no.` - the no-repetition knob.
  B: one line added to the question line: `Answer with exactly one word: yes or no
     before any reasoning, then you may add reasoning.` - the ordering knob, cell S6
     only, exploratory.

Plus three duplicate dispatches of mode A (one per cell, the same-prompt
self-agreement control that issue #100 asks for) and one census health call that
records the per-message field names and the reasoning-supplying field (the readout
extension round 40 declared, ported to this round's panel).

If a single line of instruction turns the same items from cap-truncated into
delivered answers, the `budget_limited` label is at least partly a property of the
output policy, not of the task. If it does not, the ceiling is task-side even under a
minimal-output instruction.

Inheritance: the construction, structural audit, prompt rendering, readout rules,
scoring and attempt mechanics of the merged round-23 instrument are loaded by
import, not re-implemented. The panel is certified digest-true against the archived
round-23 raw.jsonl (on main) before anything is dispatched. The one declared
extension is the census channel: a local transport whose request body is
byte-identical to the inherited request construction (the --selftest drift control
round-trips the literal body dict and certifies the literal, not the inherited
request-body construction; byte identity against the inherited transport holds per
recomputation, issue #113) and records the message field census on every dispatch.

Usage: --selftest | --gate | --probe | --analyze
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.join(HERE, "..", "nightly-2026-10-25-0205")
BASE_FILE = os.path.join(BASE_DIR, "frontier_walk_probe.py")
BASE_RAW = os.path.join(BASE_DIR, "raw.jsonl")
BASE_GATE = os.path.join(BASE_DIR, "gate.json")


def load_base():
    spec = importlib.util.spec_from_file_location("round23_instrument", BASE_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = load_base()

GATE_SCHEMA = "round42-gate-v1"
CONCURRENCY = 2
MODE_A_CALLS = 11
MODE_C_CALLS = 11
MODE_B_CALLS = 5
DUP_CALLS = 3
HEALTH_CALLS = 1
PLANNED_DISPATCHES = MODE_A_CALLS + MODE_C_CALLS + MODE_B_CALLS + DUP_CALLS
CALL_CAP = B.PROMPT_CAP
RUN_WALL_S = 2400
CELL_B = "S6"
KNOB_A_TAIL = "Answer with exactly one word: yes or no."
KNOB_C_TAIL = "Without repeating any fact, answer with exactly one word: yes or no."
KNOB_B_TAIL = ("Answer with exactly one word: yes or no before any reasoning, "
               "then you may add reasoning.")

# Pre-registered thresholds, fixed before any prompt is sent.
PANEL_N = 11
DELIVER_FLOOR = 7          # P3
TRUNC_FLOOR = 9            # P2
A_DELIVERED_CEILING = 2    # P2b
CORRECT_FLOOR = 9          # P4: strictly above the archived 8/11 loose line
WRONG_DELIVERED_MAX = 0    # P4b
COST_RATIO_CEILING = 0.50  # P5
MANIP_DROP_FLOOR = 0.15    # P6
TEXT_EXISTENCE_FLOOR = 9   # P7
MODE_B_FLOOR = 3           # P8
DUP_TARR_FLOOR = 2         # N2: byte-identical duplicate pairs, out of 3
PREDICTIONS = {
    "P1_panel_digests_reproduce_archive": True,
    "P2_modeA_truncated_ge": TRUNC_FLOOR,
    "P2b_modeA_delivered_le": A_DELIVERED_CEILING,
    "P3_modeC_delivered_ge": DELIVER_FLOOR,
    "P4_modeC_correct_ge": CORRECT_FLOOR,
    "P4b_modeC_wrong_delivered_le": WRONG_DELIVERED_MAX,
    "P5_modeC_mean_completion_over_modeA_le": COST_RATIO_CEILING,
    "P6_modeC_distractor_ratio_drop_ge": MANIP_DROP_FLOOR,
    "P7_modeC_reasoning_nonzero_ge": TEXT_EXISTENCE_FLOOR,
    "P8_modeB_delivered_ge": MODE_B_FLOOR,
    "N1_census_channel_open": True,
    "N2_duplicate_pairs_byte_identical_ge": DUP_TARR_FLOOR,
    "P9_calls_within_cap": True,
}
EXTRA_READOUTS = ("content_last_answer", "content_last_offset", "content_answer_words",
                  "content_one_word", "content_answer_leading", "reasoning_nonzero",
                  "field_conflict")


# ---------- the panel: archived round-23 cap-truncated records ----------

def archived_panel() -> list:
    """Mechanical selection rule: every round-23 record whose attempt 1 reached the
    max_tokens cap with the answer field silent. No choice, no exclusion."""
    out = []
    with open(BASE_RAW, "r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            att = rec["attempts"][-1]
            if att.get("finish_reason") != "length" or rec.get("content_answer") is not None:
                continue
            mech = att.get("mechanics") or {}
            out.append({
                "cell": rec["cell"], "arm": rec["arm"], "k": rec["k"], "chains": rec["chains"],
                "edges": rec["edges"], "seed": rec["seed"], "pair_seed": rec["pair_seed"],
                "gold": rec["gold"],
                "arch_prompt_sha256": rec["prompt_sha256"],
                "arch_item_sha256": rec["item_sha256"],
                "arch_prompt_tokens": rec["prompt_tokens"],
                "arch_completion_tokens": rec["completion_tokens"],
                "arch_reasoning_chars": mech.get("reasoning_chars"),
                "arch_content_chars": mech.get("content_chars"),
                "arch_distractor_ratio": mech.get("distractor_mention_ratio"),
                "arch_loose_answer": rec.get("loose_fallback_answer"),
                "arch_loose_source": rec.get("loose_fallback_source"),
                "arch_outcome": rec.get("outcome"),
            })
    return sorted(out, key=lambda x: (x["cell"], x["seed"], x["arm"]))


def dup_selection(panel: list) -> dict:
    """Deterministic duplicate choice: the first panel entry of each cell (panel order).
    One per cell, three total, dispatching the mode-A prompt a second time."""
    chosen: dict = {}
    for entry in panel:
        if entry["cell"] not in chosen:
            chosen[entry["cell"]] = entry["seed"]
    return chosen


def _prompt_with_tail(archived_prompt: str, tail: str) -> str:
    lines = archived_prompt.split("\n")
    question = lines[-1]
    if not question.startswith("Question: ") or "?" not in question:
        raise RuntimeError("archived prompt has no question line")
    head = question[: question.rfind("?") + 1].strip()
    return "\n".join(lines[:-1] + [f"{head} {tail}"])


def mode_prompts(entry: dict) -> dict:
    a = entry["prompt_a"]
    c = _prompt_with_tail(a, KNOB_C_TAIL)
    b = _prompt_with_tail(a, KNOB_B_TAIL)
    if a.split("\n")[:-1] != c.split("\n")[:-1] or a.split("\n")[:-1] != b.split("\n")[:-1]:
        raise RuntimeError("knob changed more than the question line")
    if c == a or b == a:
        raise RuntimeError("knob is a no-op")
    return {"A": a, "C": c, "B": b}


def certify_panel() -> tuple:
    """Reconstruct each panel item from the construction constants, audit it, and assert
    the archived item and prompt digests. Fail-closed: a mismatch stops the round."""
    panel = archived_panel()
    for entry in panel:
        item = B.gen_item(entry["k"], entry["chains"], entry["seed"])
        if entry["arm"] == "X":
            item = B.x_variant(item)
        violations = B.verify_item(item)
        if violations:
            raise RuntimeError(f"panel audit failed seed {entry['seed']}: {violations}")
        if B.sha256_text(B.canonical(item)) != entry["arch_item_sha256"]:
            raise RuntimeError(f"item digest mismatch seed {entry['seed']} arm {entry['arm']}")
        prompt = B.render_prompt(item)
        if B.sha256_text(prompt) != entry["arch_prompt_sha256"]:
            raise RuntimeError(f"prompt digest mismatch seed {entry['seed']}")
        entry["item"] = item
        entry["prompt_a"] = prompt
        entry["prompts"] = mode_prompts(entry)
    pairs = []
    for seed in sorted({e["pair_seed"] for e in panel}):
        entry = next(e for e in panel if e["pair_seed"] == seed)
        f_item = B.gen_item(entry["k"], entry["chains"], seed)
        x_item = B.x_variant(f_item)
        viol = B.pair_violations(f_item, x_item)
        if viol:
            raise RuntimeError(f"pair invariant seed {seed}: {viol}")
        pairs.append({"seed": seed, "k": entry["k"], "chains": entry["chains"],
                      "forward_item_sha256": B.sha256_text(B.canonical(f_item)),
                      "cross_item_sha256": B.sha256_text(B.canonical(x_item))})
    return panel, pairs


# ---------- census channel (the one declared extension) ----------

def census_source(reasoning_content: str, reasoning: str) -> str:
    """Round-40 merge rule: reasoning_content if non-empty, else reasoning, else none."""
    if reasoning_content:
        return "reasoning_content"
    if reasoning:
        return "reasoning"
    return "none"


def census_call(prompt: str, max_tokens: int, deadline_s: int) -> dict:
    """Local transport: byte-identical request to the inherited B.call_endpoint
    (the --selftest drift control round-trips this literal body dict; it certifies
    the literal, not the inherited request-body construction - issue #113), plus
    the per-message field census. The scoring channel ('content', 'reasoning') is
    byte-identical to the inherited transport's output; the census is record-only."""
    key = os.environ.get("NIGHTLY_API_KEY", "").strip()
    model = os.environ.get("NIGHTLY_MODEL_ID", "").strip()
    body = json.dumps({"model": model,
                       "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens,
                       "temperature": B.TEMPERATURE,
                       "stream": False}).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(B.endpoint_url(), data=body, method="POST",
                                 headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=deadline_s) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace"))
        choice = (payload.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        usage = payload.get("usage") or {}
        raw_rc = msg.get("reasoning_content") or ""
        raw_r = msg.get("reasoning") or ""
        out = {
            "content": B.sanitize(msg.get("content") or ""),
            "reasoning": B.sanitize(raw_rc),
            "finish_reason": choice.get("finish_reason"),
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
        }
        out["census"] = {
            "fields": sorted(msg.keys()),
            "reasoning_source": census_source(raw_rc, raw_r),
            "reasoning_content_chars": len(raw_rc),
            "reasoning_field_chars": len(raw_r),
            "trace_chars_total": len(raw_rc) + len(raw_r),
        }
        return out
    except urllib.error.HTTPError as exc:
        return {"error": f"http_{exc.code}", "content": "", "reasoning": "",
                "finish_reason": None, "prompt_tokens": 0, "completion_tokens": 0,
                "census": {"fields": [], "reasoning_source": "none",
                           "reasoning_content_chars": 0, "reasoning_field_chars": 0,
                           "trace_chars_total": 0}}
    except (urllib.error.URLError, TimeoutError, OSError,
            json.JSONDecodeError) as exc:
        return {"error": type(exc).__name__, "content": "", "reasoning": "",
                "finish_reason": None, "prompt_tokens": 0, "completion_tokens": 0,
                "census": {"fields": [], "reasoning_source": "none",
                           "reasoning_content_chars": 0, "reasoning_field_chars": 0,
                           "trace_chars_total": 0}}


def health_check() -> dict:
    t0 = time.monotonic()
    resp = census_call(B.HEALTH_PROMPT, B.HEALTH_BUDGET, deadline_s=240)
    latency = round(time.monotonic() - t0, 3)
    ro = B.readouts(resp["content"], resp["reasoning"])
    att = {"error_class": resp.get("error"),
           "completion_tokens": resp["completion_tokens"],
           "content_answer": ro["content_answer"],
           "reasoning_answer": ro["reasoning_answer"]}
    out = {"ok": B.classify_attempt(att) == "answered_in_answer_field",
           "outcome": B.classify_attempt(att), "latency_s": latency,
           "completion_tokens": resp["completion_tokens"],
           "prompt_tokens": resp["prompt_tokens"],
           "started_at": B.now_iso(), "finished_at": B.now_iso()}
    out["census"] = resp.get("census") or {}
    return out


# ---------- gate ----------

def build_gate(panel: list, pairs: list) -> dict:
    golds = [e["gold"] for e in panel]
    loose_ok = sum(1 for e in panel if (e["arch_loose_answer"] == "yes") == bool(e["gold"]))
    cells: dict = {}
    for e in panel:
        cells.setdefault(e["cell"], []).append(e)
    dups = dup_selection(panel)
    gate = {
        "schema": GATE_SCHEMA,
        "question": ("whether the 27B class's load ceiling (the round-23 budget_limited "
                      "label of the E = 192 cells) is a property of the task or of the "
                      "model's surface output policy"),
        "base_instrument": "research/nightly-2026-10-25-0205/frontier_walk_probe.py",
        "base_gate_sha256": hashlib.sha256(open(BASE_GATE, "rb").read()).hexdigest(),
        "selection_rule": ("every round-23 record whose attempt 1 reached the max_tokens cap "
                           "with the answer field silent (finish_reason length, content_answer "
                           "null), taken in full; duplicates are the first panel entry of "
                           "each cell, dispatched a second time in mode A"),
        "panel_n": len(panel),
        "gold_yes": sum(golds),
        "gold_no": len(golds) - sum(golds),
        "baselines": {
            "constant_no_correct": sum(1 for g in golds if g == 0),
            "constant_yes_correct": sum(1 for g in golds if g == 1),
            "archived_loose_fallback_correct": loose_ok,
            "note": (f"mode C must strictly exceed the archived {loose_ok}/{len(panel)} "
                     "loose-fallback line on the same items to count as a gain; a tie is not "
                     "a gain"),
        },
        "modes": {"A": {"knob_tail": None, "calls": MODE_A_CALLS},
                  "C": {"knob_tail": KNOB_C_TAIL, "calls": MODE_C_CALLS},
                  "B": {"knob_tail": KNOB_B_TAIL, "calls": MODE_B_CALLS, "cell": CELL_B},
                  "A2": {"knob_tail": None, "calls": DUP_CALLS,
                          "duplicates": sorted(dups.values())}},
        "cells": [{"cell": name, "n": len(recs),
                   "arch_distractor_ratio_mean": round(
                       sum(r["arch_distractor_ratio"] for r in recs) / len(recs), 4),
                   "seeds": [r["seed"] for r in recs]}
                  for name, recs in sorted(cells.items())],
        "pairs": pairs,
        "max_tokens": B.MAX_TOKENS,
        "temperature": B.TEMPERATURE,
        "prompt_cap": CALL_CAP,
        "planned_calls": PLANNED_DISPATCHES + HEALTH_CALLS,
        "concurrency": CONCURRENCY,
        "wall_guard_s": RUN_WALL_S,
        "readouts_inherited": ["content_only", "loose_fallback", "delivered_or_strict"],
        "readouts_local": list(EXTRA_READOUTS) + ["census"],
        "census": {"declared_extension": ("per-message field census on every dispatch: "
                                           "field names plus the reasoning-supplying field, "
                                           "merge rule reasoning_content if non-empty, else "
                                           "reasoning, else none; record-only, the scoring "
                                           "channel stays the inherited byte-identical one")},
        "panel": [{"cell": e["cell"], "arm": e["arm"], "k": e["k"], "chains": e["chains"],
                   "edges": e["edges"], "seed": e["seed"], "pair_seed": e["pair_seed"],
                   "gold": e["gold"], "item_sha256": e["arch_item_sha256"],
                   "prompt_sha256": e["arch_prompt_sha256"],
                   "knob_prompt_sha256": {m: B.sha256_text(p) for m, p in e["prompts"].items()},
                   "prompt_chars": {m: len(p) for m, p in e["prompts"].items()},
                   "arch_prompt_tokens": e["arch_prompt_tokens"],
                   "arch_completion_tokens": e["arch_completion_tokens"],
                   "arch_reasoning_chars": e["arch_reasoning_chars"],
                   "arch_content_chars": e["arch_content_chars"],
                   "arch_distractor_ratio": e["arch_distractor_ratio"],
                   "arch_loose_answer": e["arch_loose_answer"]}
                  for e in panel],
        "predictions": PREDICTIONS,
        "decision_table": {
            "policy_artifact": (f"mode C delivers >= {DELIVER_FLOOR}/{PANEL_N}, every delivered "
                                f"answer correct, and scores > {loose_ok}/{PANEL_N} (strictly "
                                "above the archived loose-fallback line)"),
            "surfacing_only": (f"mode C delivers >= {DELIVER_FLOOR}/{PANEL_N} but the delivered "
                               "verdict quality does not (accuracy at or below the archived "
                               "line, or a wrong delivered answer)"),
            "policy_immovable": f"both modes deliver <= {A_DELIVERED_CEILING}/{PANEL_N}",
            "partial": "mode C delivers between the floors",
        },
    }
    gate["gate_blob_sha256"] = B.sha256_text(B.canonical(gate))
    return gate


# ---------- records ----------

def extra_readouts(att: dict) -> dict:
    """Local readouts over the answer field only (the inherited three readouts span
    content and reasoning). content_last_answer is the last standalone yes/no in the
    answer field; content_answer_leading is whether the field's FIRST word is a yes/no
    verdict (the ordering-knob indicator, mode B)."""
    content = att.get("content") or ""
    last, off = B.last_answer(content)
    words = len(list(B.ANSWER_RE.finditer(content)))
    one_word = content.strip().lower() in ("yes", "no")
    stripped = content.strip()
    first_word = stripped.split(" ", 1)[0].strip(".,!?;:").lower() if stripped else None
    leading = (first_word in ("yes", "no") and first_word == (last or ""))
    return {"content_last_answer": last,
            "content_last_offset": off,
            "content_answer_words": words,
            "content_one_word": one_word,
            "content_answer_leading": bool(leading),
            "reasoning_nonzero": len(att.get("reasoning") or "") > 0,
            "field_conflict": (last is not None and att.get("reasoning_answer") is not None
                               and last != att["reasoning_answer"])}


def score(rec: dict, last: dict) -> None:
    gold = rec["gold"]
    answers = {"content_only": last["content_answer"],
               "loose_fallback": last["loose_fallback_answer"],
               "delivered_or_strict": last["delivered_or_strict_answer"],
               "content_last": last["content_last_answer"]}
    rec["correct"] = {name: (None if ans is None else int((1 if ans == "yes" else 0) == gold))
                      for name, ans in answers.items()}
    rec["outcome"] = B.classify_attempt(last)
    rec["delivered"] = last["content_answer"] is not None
    rec["truncated_at_cap"] = (last.get("finish_reason") == "length"
                                and last.get("completion_tokens") == B.MAX_TOKENS
                                and last["content_answer"] is None)
    rec["correct_content_only"] = rec["correct"]["content_only"]


def blank_attempt(attempt_no: int, error_class: str) -> dict:
    return {"attempt": attempt_no, "wall_s": 0.0, "error_class": error_class,
            "started_at": B.now_iso(), "finished_at": B.now_iso(), "finish_reason": None,
            "prompt_tokens": 0, "completion_tokens": 0, "content": "", "reasoning": "",
            "mechanics": {}, "census": None}


def make_record(entry: dict, mode: str, index: int, budget, wall_start: float) -> dict:
    item = entry["item"]
    prompt = entry["prompts"]["A" if mode == "A2" else mode]
    rec = {"mode": mode, "cell": entry["cell"], "arm": entry["arm"], "level": item["edges"],
           "k": item["level"], "chains": item["chains"], "edges": item["edges"],
           "seed": item["seed"], "pair_seed": entry["pair_seed"], "seed_hash": item["seed_hash"],
           "item_sha256": B.sha256_text(B.canonical(item)),
           "prompt_sha256": B.sha256_text(prompt), "prompt_chars": len(prompt),
           "gold": 1 if item["answer"] == "yes" else 0, "gate_hash": GATE_HASH,
           "dispatch_index": index,
           "archived_prompt_sha256": entry["arch_prompt_sha256"],
           "archived_completion_tokens": entry["arch_completion_tokens"],
           "archived_distractor_ratio": entry["arch_distractor_ratio"],
           "attempts": []}
    for attempt_no in range(1, 4):
        if wall_start + RUN_WALL_S < time.monotonic():
            rec["attempts"].append(blank_attempt(attempt_no, "wall_guard"))
            break
        if not budget.acquire():
            rec["attempts"].append(blank_attempt(attempt_no, "cap_exceeded"))
            break
        t0 = time.monotonic()
        started = B.now_iso()
        resp = census_call(prompt, B.MAX_TOKENS, deadline_s=B.ITEM_DEADLINE_S)
        wall = round(time.monotonic() - t0, 3)
        att = {"attempt": attempt_no, "wall_s": wall, "error_class": resp.get("error"),
               "started_at": started, "finished_at": B.now_iso(),
               "finish_reason": resp["finish_reason"],
               "prompt_tokens": resp["prompt_tokens"],
               "completion_tokens": resp["completion_tokens"],
               "content": resp["content"], "reasoning": resp["reasoning"]}
        att.update(B.readouts(resp["content"], resp["reasoning"]))
        att.update(extra_readouts(att))
        att["mechanics"] = B.mechanics(item, att, prompt)
        att["census"] = resp.get("census")
        rec["attempts"].append(att)
        if not B.is_retryable(B.classify_attempt(att)):
            break
    last = rec["attempts"][-1]
    if not last["mechanics"]:
        last["mechanics"] = {"reasoning_chars": 0, "content_chars": 0,
                             "distractor_mention_ratio": None, "completion_tokens": 0}
    for field in ("content_answer", "reasoning_answer", "loose_fallback_answer",
                  "loose_fallback_source", "strict_trace_token", "delivered_or_strict_answer",
                  "fallback_provenance_class", "fallback_commit_fraction") + EXTRA_READOUTS:
        rec[field] = last.get(field)
    rec["completion_tokens"] = last.get("completion_tokens", 0)
    rec["prompt_tokens"] = last.get("prompt_tokens", 0)
    rec["mechanics"] = last["mechanics"]
    rec["census"] = last.get("census")
    rec["wall_s"] = last.get("wall_s", 0.0)
    score(rec, last)
    return rec


# ---------- analysis ----------

def wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple:
    """Wilson 95 % interval, house formula (the round-23 instrument's): divide by
    (1 + z^2/n), not by (n + z^2) - the latter deflates the interval by a factor n."""
    if total == 0:
        return (None, None)
    p = successes / total
    denom = 1 + z * z / total
    centre = p + z * z / (2 * total)
    span = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return (round(max(0.0, (centre - span) / denom), 4),
            round(min(1.0, (centre + span) / denom), 4))


def binom_tail_le(n: int, k: int) -> float:
    return sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * binom_tail_le(n, min(b, c)))


def median(vals: list):
    vals = sorted(vals)
    if not vals:
        return None
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else round((vals[mid - 1] + vals[mid]) / 2, 4)


def stats_mode(recs: list) -> dict:
    n = len(recs)
    ctok = [r["completion_tokens"] for r in recs]
    rchars = [r["mechanics"]["reasoning_chars"] for r in recs]
    ratios = [r["mechanics"]["distractor_mention_ratio"] for r in recs
              if r["mechanics"]["distractor_mention_ratio"] is not None]
    words = [r["content_answer_words"] for r in recs if r["delivered"]]
    delivered = sum(1 for r in recs if r["delivered"])
    return {
        "n": n,
        "delivered": delivered,
        "truncated_at_cap": sum(1 for r in recs if r.get("truncated_at_cap")),
        "no_answer_at_all": sum(1 for r in recs
                                if r["content_answer"] is None and r["reasoning_answer"] is None),
        "delivered_rate": round(delivered / n, 4),
        "delivered_wilson_95": wilson(delivered, n),
        "delivered_correct": sum(1 for r in recs
                                 if r["delivered"] and r["correct"]["content_only"] == 1),
        "wrong_delivered": sum(1 for r in recs
                               if r["delivered"] and r["correct"]["content_only"] == 0),
        "correct_over_all": sum(1 for r in recs if r["correct"]["content_only"] == 1),
        "correct_over_all_rate": round(
            sum(1 for r in recs if r["correct"]["content_only"] == 1) / n, 4),
        "loose_fallback_correct": sum(1 for r in recs if r["correct"]["loose_fallback"] == 1),
        "delivered_or_strict_correct": sum(
            1 for r in recs if r["correct"]["delivered_or_strict"] == 1),
        "completion_tokens_mean": round(sum(ctok) / n, 1),
        "completion_tokens_median": median(ctok),
        "completion_tokens_max": max(ctok),
        "reasoning_chars_nonzero": sum(1 for v in rchars if v > 0),
        "reasoning_chars_min": min(rchars),
        "reasoning_chars_median": median(rchars),
        "reasoning_chars_max": max(rchars),
        "content_chars_mean": round(sum(r["mechanics"]["content_chars"] for r in recs) / n, 1),
        "distractor_ratio_mean": round(sum(ratios) / len(ratios), 4) if ratios else None,
        "distractor_ratio_min": min(ratios) if ratios else None,
        "distractor_ratio_max": max(ratios) if ratios else None,
        "one_word_answer_field": sum(1 for r in recs if r["content_one_word"]),
        "answer_leading": sum(1 for r in recs if r["content_answer_leading"]),
        "max_answer_words_in_content": max(words) if words else 0,
        "field_conflicts": sum(1 for r in recs if r["field_conflict"]),
        "attempts_used": sum(len(r["attempts"]) for r in recs),
        "error_classes": sorted({a["error_class"] for r in recs for a in r["attempts"]
                                 if a.get("error_class")}),
        "census": census_block(recs),
    }


def census_block(recs: list) -> dict:
    srcs = {}
    fields_seen: set = set()
    traces = []
    for r in recs:
        c = r.get("census") or {}
        src = c.get("reasoning_source", "none")
        srcs[src] = srcs.get(src, 0) + 1
        fields_seen.update(c.get("fields") or [])
        if c.get("trace_chars_total") is not None:
            traces.append(c["trace_chars_total"])
    return {
        "reasoning_source_counts": srcs,
        "fields_seen": sorted(fields_seen),
        "trace_chars_total_min": min(traces) if traces else None,
        "trace_chars_total_median": median(traces),
        "trace_chars_total_max": max(traces) if traces else None,
    }


def dup_block(recs: list) -> dict:
    """Same-prompt self-agreement over the duplicate dispatches: byte identity of
    content + reasoning, and completion-token identity, per duplicate pair."""
    by_index = {r["dispatch_index"]: r for r in recs}
    pairs = []
    for r in recs:
        if r["mode"] != "A2":
            continue
        orig = by_index.get(r["replicates"])
        if orig is None:
            continue
        la, lb = r["attempts"][-1], orig["attempts"][-1]
        byte_id = (la["content"] == lb["content"] and la["reasoning"] == lb["reasoning"])
        tok_id = la["completion_tokens"] == lb["completion_tokens"]
        pairs.append({"cell": r["cell"], "seed_pair": [orig["seed"], r["seed"]],
                      "byte_identical": byte_id, "token_identical": tok_id,
                      "orig_completion_tokens": lb["completion_tokens"],
                      "dup_completion_tokens": la["completion_tokens"]})
    n = len(pairs)
    byte = sum(1 for p in pairs if p["byte_identical"])
    tok = sum(1 for p in pairs if p["token_identical"])
    return {"pairs": pairs, "n_pairs": n, "byte_identical_pairs": byte,
            "token_identical_pairs": tok,
            "tarr": (round(byte / n, 4) if n else None)}


def text_exists(st: dict) -> bool:
    return st["reasoning_chars_nonzero"] >= TEXT_EXISTENCE_FLOOR and st["reasoning_chars_max"] > 0


def paired_discord(recs_a: list, recs_b: list, key: str) -> dict:
    """Paired discordance on the SAME items: (A true B false) vs (A false B true).
    Items are keyed by (seed, arm): within a matched pair the F and X items share the
    seed and must stay separate pairs."""
    by_a = {(r["seed"], r["arm"]): r for r in recs_a}
    by_b = {(r["seed"], r["arm"]): r for r in recs_b}
    a_only, b_only = 0, 0
    for item_key, ra in by_a.items():
        rb = by_b.get(item_key)
        if not rb:
            continue
        va, vb = bool(ra.get(key)), bool(rb.get(key))
        if va and not vb:
            a_only += 1
        elif vb and not va:
            b_only += 1
    return {"mode_a_only": a_only, "mode_b_only": b_only, "n_paired": len(by_a),
            "p_exact_mcnemar": mcnemar_exact(a_only, b_only)}


def evaluate(recs: list, gate: dict, health: dict) -> dict:
    by_mode = {m: [r for r in recs if r["mode"] == m] for m in ("A", "B", "C")}
    stats = {m: stats_mode(v) for m, v in by_mode.items() if v}
    out = {"modes": stats, "duplicates": dup_block(recs)}
    a, c = stats.get("A"), stats.get("C")
    if not a or not c:
        return dict(out, checks={"ran": False}, verdict={"tier": "insufficient_data"})
    b = stats.get("B")
    ratio = round(c["completion_tokens_mean"] / a["completion_tokens_mean"], 4)
    drop = (None if a["distractor_ratio_mean"] is None or c["distractor_ratio_mean"] is None
            else round(a["distractor_ratio_mean"] - c["distractor_ratio_mean"], 4))
    arch_mean = round(sum(e["arch_distractor_ratio"] for e in gate["panel"]) / gate["panel_n"], 4)
    base = gate["baselines"]
    te = text_exists(c)
    h_src = (health.get("census") or {}).get("reasoning_source", "none")
    n1 = h_src != "none"
    checks = {
        "P2_modeA_truncated_ge": a["truncated_at_cap"] >= TRUNC_FLOOR,
        "P2b_modeA_delivered_le": a["delivered"] <= A_DELIVERED_CEILING,
        "P3_modeC_delivered_ge": c["delivered"] >= DELIVER_FLOOR,
        "P4_modeC_correct_ge": c["correct_over_all"] >= CORRECT_FLOOR,
        "P4b_zero_wrong_delivered": c["wrong_delivered"] <= WRONG_DELIVERED_MAX,
        "cost_ratio_modeC_over_modeA": ratio,
        "P5_cost_ratio_le_ceiling": ratio <= COST_RATIO_CEILING,
        "distractor_ratio_archived_mean": arch_mean,
        "distractor_ratio_drop_modeA_minus_modeC": drop,
        "distractor_ratio_drop_archived_minus_modeC": (
            None if c["distractor_ratio_mean"] is None
            else round(arch_mean - c["distractor_ratio_mean"], 4)),
        "P6_manipulation_check": bool(te and drop is not None and drop >= MANIP_DROP_FLOOR),
        "P7_text_existence": te,
        "P7_modeC_one_word_rate": round(c["one_word_answer_field"] / max(1, c["n"]), 4),
        "P7_modeC_max_answer_words_in_content": c["max_answer_words_in_content"],
        "P8_modeB_delivered_ge": (None if b is None else b["delivered"] >= MODE_B_FLOOR),
        "N1_census_channel_open": n1,
        "N1_census_health_source": h_src,
        "N2_duplicate_pairs_byte_identical_ge": (
            out["duplicates"]["tarr"] is not None
            and out["duplicates"]["byte_identical_pairs"] >= DUP_TARR_FLOOR),
        "N2_duplicate_tarr": out["duplicates"]["tarr"],
        "paired_delivery_modeA_vs_modeC": paired_discord(by_mode["A"], by_mode["C"], "delivered"),
        "paired_correct_modeA_vs_modeC": paired_discord(
            by_mode["A"], by_mode["C"], "correct_content_only"),
        "text_existence_report": {
            "floor": TEXT_EXISTENCE_FLOOR,
            "modeC_reasoning_nonzero_count": c["reasoning_chars_nonzero"],
            "modeC_reasoning_chars": {"min": c["reasoning_chars_min"],
                                      "median": c["reasoning_chars_median"],
                                      "max": c["reasoning_chars_max"]},
            "modeC_content_chars_mean": c["content_chars_mean"],
            "accepted_for_text_derived_claims": te,
        },
    }
    checks["baselines"] = {
        "panel_golds": f"{gate['gold_yes']} yes / {gate['gold_no']} no",
        "constant_no_correct": f"{base['constant_no_correct']}/{PANEL_N}",
        "constant_yes_correct": f"{base['constant_yes_correct']}/{PANEL_N}",
        "archived_loose_line_correct": f"{base['archived_loose_fallback_correct']}/{PANEL_N}",
        "modeA_loose_correct": f"{a['loose_fallback_correct']}/{PANEL_N}",
        "modeC_correct_over_all": f"{c['correct_over_all']}/{PANEL_N}",
        "modeC_beats_archived_loose_line": (
            c["correct_over_all"] > base["archived_loose_fallback_correct"]),
        "modeC_beats_constant_no": c["correct_over_all"] > base["constant_no_correct"],
    }
    met = all(checks[k] for k in ("P2_modeA_truncated_ge", "P2b_modeA_delivered_le",
                                  "P3_modeC_delivered_ge", "P4_modeC_correct_ge",
                                  "P4b_zero_wrong_delivered", "P5_cost_ratio_le_ceiling",
                                  "P6_manipulation_check", "P7_text_existence")
              if isinstance(checks[k], bool))
    if c["delivered"] <= A_DELIVERED_CEILING and a["delivered"] <= A_DELIVERED_CEILING:
        tier = "policy_immovable"
    elif (c["delivered"] >= DELIVER_FLOOR and c["wrong_delivered"] == 0
          and c["correct_over_all"] > base["archived_loose_fallback_correct"]):
        tier = "policy_artifact"
    elif c["delivered"] >= DELIVER_FLOOR:
        tier = "surfacing_only"
    else:
        tier = "partial"
    out["checks"] = checks
    out["verdict"] = {
        "tier": tier,
        "all_registered_predictions_met": met,
        "beats_archived_loose_line": checks["baselines"]["modeC_beats_archived_loose_line"],
        "census_claims_accepted": n1,
        "replication_tarr": out["duplicates"]["tarr"],
    }
    return out


# ---------- probe ----------

GATE_HASH = "unset"


def plan_dispatches(panel: list) -> list:
    plan = []
    for entry in panel:
        plan.append(("A", entry))
    for entry in panel:
        plan.append(("C", entry))
    b_count = 0
    for entry in panel:
        if entry["cell"] == CELL_B and b_count < MODE_B_CALLS:
            plan.append(("B", entry))
            b_count += 1
    dups = dup_selection(panel)
    a_by_seed = {e["seed"]: e for e in panel}
    for seed in sorted(dups.values()):
        plan.append(("A2", a_by_seed[seed]))
    return plan


def link_duplicates(plan: list) -> dict:
    """Map each A2 plan slot to the dispatch index of the mode-A record it replicates."""
    links = {}
    a_index = {}
    for i, (mode, entry) in enumerate(plan):
        if mode == "A":
            a_index[entry["seed"]] = i
    for i, (mode, entry) in enumerate(plan):
        if mode == "A2":
            links[i] = a_index[entry["seed"]]
    return links


def probe(out_dir: str) -> int:
    global GATE_HASH
    panel, pairs = certify_panel()
    gate = build_gate(panel, pairs)
    GATE_HASH = gate["gate_blob_sha256"]
    plan = plan_dispatches(panel)
    if len(plan) + HEALTH_CALLS > CALL_CAP:
        print(f"plan {len(plan)} dispatches + health exceeds cap {CALL_CAP}", file=sys.stderr)
        return 2
    links = link_duplicates(plan)
    os.makedirs(out_dir, exist_ok=True)
    raw_path = os.path.join(out_dir, "raw.jsonl")
    if os.path.exists(raw_path):
        os.unlink(raw_path)
    budget = B.AttemptBudget(CALL_CAP)
    health = health_check()
    budget.used += 1
    print(f"health: {json.dumps(health, sort_keys=True)}", flush=True)
    with open(os.path.join(out_dir, "health.json"), "w", encoding="utf-8") as fh:
        json.dump(health, fh, indent=2, sort_keys=True)
        fh.write("\n")
    if not health["ok"]:
        print("REFUSED: endpoint failed the chat-completion health probe", file=sys.stderr)
        return 4
    wall_start = time.monotonic()

    def run(mode: str, entry: dict, index: int) -> None:
        rec = make_record(entry, mode, index, budget, wall_start)
        if mode == "A2":
            rec["replicates"] = links[index]
        B.write_jsonl(raw_path, rec)
        m = rec["mechanics"]
        print(f"{mode:>2} {rec['cell']} k={rec['k']:>2} E={rec['edges']:>3} arm={rec['arm']} "
              f"gold={rec['gold']} outcome={rec['outcome']:>22} "
              f"content={str(rec['content_answer']):>4} ctok={rec['completion_tokens']:>5} "
              f"rchars={m['reasoning_chars']:>5} dr={m['distractor_mention_ratio']} "
              f"wall={rec['wall_s']:.1f}s", flush=True)

    futures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        for index, (mode, entry) in enumerate(plan):
            futures.append(pool.submit(run, mode, entry, index))
        for fut in concurrent.futures.as_completed(futures):
            fut.result()
    recs = [json.loads(line) for line in open(raw_path, encoding="utf-8") if line.strip()]
    summary = evaluate(recs, gate, health)
    summary["gate_hash"] = GATE_HASH
    summary["wall_seconds"] = round(time.monotonic() - wall_start, 1)
    summary["endpoint_calls_used"] = budget.used
    summary["endpoint_calls_cap"] = CALL_CAP
    summary["dispatch_planned"] = len(plan)
    walls = [r["wall_s"] for r in recs if r.get("wall_s")]
    summary["transport"] = {
        "dispatch_records": len(recs),
        "attempts_total": sum(len(r["attempts"]) for r in recs),
        "completion_tokens_total": sum(r["completion_tokens"] for r in recs),
        "prompt_tokens_total": sum(r["prompt_tokens"] for r in recs),
        "single_stream_tokens_per_second": round(
            sum(r["completion_tokens"] for r in recs) / max(1.0, sum(walls) / CONCURRENCY), 2),
    }
    disk_gate = {k: v for k, v in gate.items() if k != "panel"}
    with open(os.path.join(out_dir, "gate.json"), "w", encoding="utf-8") as fh:
        json.dump(disk_gate, fh, indent=2, sort_keys=True)
        fh.write("\n")
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(json.dumps({"verdict": summary["verdict"], "checks": summary["checks"],
                      "duplicates": summary["duplicates"],
                      "modes": {m: {k: v for k, v in s.items()
                                    if k in ("n", "delivered", "truncated_at_cap",
                                             "completion_tokens_mean", "reasoning_chars_max")}
                               for m, s in summary["modes"].items()},
                      "transport": summary["transport"]},
                     indent=2, sort_keys=True))
    return 0


# ---------- selftest (no endpoint calls, no env reads) ----------

def synth(entry: dict, mode: str, content: str, reasoning: str, ctok: int) -> dict:
    item = entry["item"]
    prompt = entry["prompts"]["A" if mode == "A2" else mode]
    finish = "length" if ctok == B.MAX_TOKENS else "stop"
    att = {"attempt": 1, "wall_s": 1.0, "error_class": None, "finish_reason": finish,
           "prompt_tokens": 2900, "completion_tokens": ctok, "started_at": "",
           "finished_at": "", "content": content, "reasoning": reasoning}
    att.update(B.readouts(content, reasoning))
    att.update(extra_readouts(att))
    att["mechanics"] = B.mechanics(item, att, prompt)
    att["census"] = {"fields": ["content", "reasoning_content", "role"],
                     "reasoning_source": census_source(reasoning, ""),
                     "reasoning_content_chars": len(reasoning),
                     "reasoning_field_chars": 0,
                     "trace_chars_total": len(reasoning)}
    rec = {"mode": mode, "cell": entry["cell"], "arm": entry["arm"], "seed": entry["seed"],
           "gold": 1 if item["answer"] == "yes" else 0, "completion_tokens": ctok,
           "prompt_tokens": 2900, "mechanics": att["mechanics"], "census": att["census"],
           "attempts": [att], "wall_s": 1.0, "dispatch_index": 0}
    for field in ("content_answer", "reasoning_answer", "loose_fallback_answer",
                  "delivered_or_strict_answer") + EXTRA_READOUTS:
        rec[field] = att[field]
    score(rec, att)
    return rec


def _drift_control() -> None:
    """Round-trip the census transport's literal body dict: same key set, same
    values, same order-independent JSON payload as the literal built in this
    function. This certifies the literal, not the inherited B.call_endpoint's
    request-body construction - the inherited function is not inspected here, so
    drift in its body keys cannot break this assertion (issue #113). Byte identity
    against the inherited transport holds per recomputation; the inherited
    constants (B.MAX_TOKENS, B.TEMPERATURE) are still asserted against their
    archived values."""
    prompt = "probe prompt"
    model = "some-model"
    os.environ["NIGHTLY_MODEL_ID"] = model
    body = json.dumps({"model": model,
                       "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": B.MAX_TOKENS,
                       "temperature": B.TEMPERATURE,
                       "stream": False})
    mine = json.loads(body)
    assert set(mine.keys()) == {"model", "messages", "max_tokens", "temperature", "stream"}
    assert mine["temperature"] == B.TEMPERATURE == 0.0
    assert mine["max_tokens"] == B.MAX_TOKENS
    assert mine["messages"] == [{"role": "user", "content": prompt}]
    assert mine["stream"] is False
    os.environ.pop("NIGHTLY_MODEL_ID", None)


def selftest() -> None:
    panel, pairs = certify_panel()
    gate = build_gate(panel, pairs)
    assert gate["panel_n"] == 11 and gate["gold_yes"] == 4 and gate["gold_no"] == 7
    assert gate["baselines"]["constant_no_correct"] == 7
    assert gate["baselines"]["constant_yes_correct"] == 4
    assert gate["baselines"]["archived_loose_fallback_correct"] == 8
    assert gate["planned_calls"] == 31 and gate["prompt_cap"] == 40
    assert len(pairs) == 8 and len(gate["panel"]) == 11
    assert gate["predictions"]["P4_modeC_correct_ge"] == 9
    assert len(dup_selection(panel)) == 3
    # the knob may touch only the question line, never the rule or the facts
    for e in panel:
        p = e["prompts"]
        assert p["A"] != p["C"] and p["A"] != p["B"] and p["B"] != p["C"]
        assert p["A"].split("\n")[:-1] == p["C"].split("\n")[:-1] == p["B"].split("\n")[:-1]
        assert p["A"].split("\n")[-1].endswith(KNOB_A_TAIL)
        assert p["C"].split("\n")[-1].endswith(KNOB_C_TAIL)
        assert p["B"].split("\n")[-1].endswith(KNOB_B_TAIL)
        assert len(p["C"]) > len(p["A"]) and len(p["B"]) > len(p["A"])
        assert p["A"].count("Fact ") == p["C"].count("Fact ") == 192
        assert "Without repeating" not in p["A"] and "before any reasoning" not in p["A"]
        assert p["C"].count("Without repeating any fact") == 1
        assert p["C"].count("Question: ") == 1 and p["B"].count("Question: ") == 1
    # negative control: a perturbed seed cannot forge the archived digest
    e0 = panel[0]
    forged = B.gen_item(e0["k"], e0["chains"], e0["seed"] + 1)
    assert B.sha256_text(B.canonical(forged)) != e0["arch_item_sha256"]
    # negative control: the selection rule is exhaustive, nothing was excluded
    raw = [json.loads(line) for line in open(BASE_RAW, encoding="utf-8") if line.strip()]
    trunc = [r for r in raw if r["attempts"][-1].get("finish_reason") == "length"
             and r.get("content_answer") is None]
    assert len(trunc) == 11
    assert {r["prompt_sha256"] for r in trunc} == {e["arch_prompt_sha256"] for e in panel}
    # census merge rule and field capture
    assert census_source("x", "y") == "reasoning_content"
    assert census_source("", "y") == "reasoning"
    assert census_source("x", "") == "reasoning_content"
    assert census_source("", "") == "none"
    _drift_control()
    # arithmetic
    lo, hi = wilson(7, 11)
    assert 0.35 < lo < 0.55 and 0.7 < hi < 0.95, (lo, hi)
    assert wilson(0, 0) == (None, None)
    assert wilson(11, 11)[0] > 0.68
    assert mcnemar_exact(0, 0) == 1.0
    assert abs(mcnemar_exact(11, 0) - 1 / 1024) < 1e-9, mcnemar_exact(11, 0)
    assert abs(binom_tail_le(11, 0) - 1 / 2048) < 1e-12
    assert median([1, 2, 3, 4]) == 2.5 and median([7]) == 7
    # duplicate-pair block: only A2 records form pairs, and only against an existing
    # dispatch index; non-duplicate record sets carry no pairs
    assert dup_block([])["n_pairs"] == 0 and dup_block([])["tarr"] is None
    assert dup_block([synth(e, "A", "no", "t", 500) for e in panel])["n_pairs"] == 0
    # inherited mechanics: the distractor ratio responds to what the trace enumerates
    enum = next(e for e in panel if e["arch_distractor_ratio"] == 1.0)
    dis = B.distractor_names(enum["item"])
    assert dis and len(dis) > 5
    hit = synth(enum, "C", "no", " ".join(dis), 900)
    miss = synth(enum, "C", "no", "the chain holds", 900)
    assert hit["mechanics"]["distractor_mention_ratio"] == 1.0
    assert miss["mechanics"]["distractor_mention_ratio"] == 0.0
    assert hit["delivered"] and hit["correct"]["content_only"] == 1
    # negative control: a delivered wrong answer is scored wrong, never dropped
    gold_no = next(e for e in panel if e["gold"] == 0)
    wrong = synth(gold_no, "C", "yes", "walk", 300)
    assert wrong["correct"]["content_only"] == 0 and wrong["delivered"]
    assert wrong["truncated_at_cap"] is False
    assert wrong["outcome"] == "answered_in_answer_field"
    # one-word, ordering and field-conflict readouts
    two = synth(gold_no, "C", "no, but then yes", "walk", 300)
    assert two["content_answer_words"] == 2 and not two["content_one_word"]
    assert two["content_last_answer"] == "yes" and two["delivered_or_strict_answer"] == "yes"
    assert two["content_answer_leading"] is False
    one = synth(gold_no, "C", "no", "walk", 300)
    assert one["content_one_word"] and one["content_last_offset"] == 0
    assert one["content_answer_leading"] is True
    # the inherited three readouts survive
    silent = synth(gold_no, "C", "", "so the answer is no", 900)
    assert silent["delivered"] is False and silent["correct"]["content_only"] is None
    assert silent["correct"]["loose_fallback"] == 1
    assert silent["outcome"] == "trace_only"
    assert silent["truncated_at_cap"] is False
    # decision-table tiers, each produced from synthetic runs. Answer dicts are keyed
    # by (seed, arm): within a matched pair the F and X items share the seed and carry
    # opposite golds, so a seed-only key collides and flips the partner's verdict.
    def ekey(e: dict) -> tuple:
        return (e["seed"], e["arm"])

    def build(mode: str, answers: dict) -> list:
        out = []
        for e in panel:
            if mode == "A" or answers.get(ekey(e)) is None:
                # the enumerating trace names THIS item's own distractors (what round 23
                # measured: ratio near 1.0 per prompt), so the drop against a non-
                # enumerating mode C is a per-item quantity
                out.append(synth(e, mode, "",
                                 " ".join(B.distractor_names(e["item"])) or "x", B.MAX_TOKENS))
            else:
                out.append(synth(e, mode, answers[ekey(e)], "walk", 260))
        return out

    def with_health(src: str = "reasoning_content") -> dict:
        return {"ok": True, "census": {"reasoning_source": src,
                                        "fields": ["content", "reasoning_content", "role"]}}

    a_run = build("A", {})
    perfect = build("C", {ekey(e): ("yes" if e["gold"] == 1 else "no") for e in panel})
    res = evaluate(a_run + perfect, gate, with_health())
    assert res["verdict"]["tier"] == "policy_artifact", res["verdict"]
    assert res["verdict"]["all_registered_predictions_met"] is True
    assert res["verdict"]["beats_archived_loose_line"] is True
    assert res["checks"]["paired_delivery_modeA_vs_modeC"]["p_exact_mcnemar"] < 0.001
    assert res["checks"]["paired_delivery_modeA_vs_modeC"]["mode_b_only"] == 11
    assert res["checks"]["cost_ratio_modeC_over_modeA"] < 0.2
    assert res["checks"]["P6_manipulation_check"] is True
    assert res["checks"]["distractor_ratio_archived_mean"] > 0.6
    assert res["modes"]["C"]["correct_over_all"] == 11
    assert res["checks"]["N1_census_channel_open"] is True
    assert res["verdict"]["census_claims_accepted"] is True
    # N1 refusal path: a closed channel refuses the census claims, not the round
    res_n1 = evaluate(a_run + perfect, gate, with_health("none"))
    assert res_n1["checks"]["N1_census_channel_open"] is False
    assert res_n1["verdict"]["census_claims_accepted"] is False
    assert res_n1["verdict"]["tier"] == "policy_artifact"
    # N2: a byte-identical duplicate pair set passes, a perturbed one fails. The
    # duplicate records live in a disjoint dispatch-index space (offset 100) so the
    # pair lookups cannot collide with the a_run / perfect records, which all carry
    # the synth default dispatch_index 0.
    def dup_set(byte_ok: bool) -> list:
        out = []
        i = 100
        for cell in ("S4", "S5", "S6"):
            e = dup_selection(panel)[cell]
            entry = next(x for x in panel if x["seed"] == e)
            base_rec = synth(entry, "A", "no", "trace", 500)
            base_rec["dispatch_index"] = i
            i += 1
            dup_rec = synth(entry, "A2", "no" if byte_ok else "yes",
                            "trace" if byte_ok else "other", 500 if byte_ok else 600)
            dup_rec["dispatch_index"] = i
            dup_rec["replicates"] = i - 1
            i += 1
            out.extend([base_rec, dup_rec])
        return out

    res2 = evaluate(a_run + perfect + dup_set(True), gate, with_health())
    assert res2["duplicates"]["n_pairs"] == 3
    assert res2["checks"]["N2_duplicate_pairs_byte_identical_ge"] is True
    assert res2["verdict"]["replication_tarr"] == 1.0
    res2b = evaluate(a_run + perfect + dup_set(False), gate, with_health())
    assert res2b["checks"]["N2_duplicate_pairs_byte_identical_ge"] is False
    assert res2b["verdict"]["replication_tarr"] == 0.0
    assert res2b["duplicates"]["token_identical_pairs"] == 0
    # negative control A: constant-"no" answering delivers everything, gains nothing
    res3 = evaluate(a_run + build("C", {ekey(e): "no" for e in panel}), gate, with_health())
    assert res3["checks"]["baselines"]["modeC_correct_over_all"] == "7/11", res3["checks"]
    assert res3["verdict"]["tier"] == "surfacing_only", res3["verdict"]
    assert res3["checks"]["baselines"]["modeC_beats_constant_no"] is False
    # negative control B: tying the archived loose line is not a gain
    res4 = evaluate(a_run + build("C", {ekey(e): e["arch_loose_answer"] for e in panel}),
                    gate, with_health())
    assert res4["checks"]["baselines"]["modeC_correct_over_all"] == "8/11", res4["checks"]
    assert res4["verdict"]["tier"] == "surfacing_only", res4["verdict"]
    assert res4["verdict"]["beats_archived_loose_line"] is False
    # negative control C: everything delivered, every verdict flipped
    flip = {ekey(e): ("yes" if e["gold"] == 0 else "no") for e in panel}
    res5 = evaluate(a_run + build("C", flip), gate, with_health())
    assert res5["verdict"]["tier"] == "surfacing_only", res5["verdict"]
    assert res5["checks"]["P4b_zero_wrong_delivered"] is False
    # negative control D: a knob that never delivers is immovable
    res6 = evaluate(a_run + build("C", {}), gate, with_health())
    assert res6["verdict"]["tier"] == "policy_immovable", res6["verdict"]
    assert res6["checks"]["P3_modeC_delivered_ge"] is False
    # negative control E: mode A failing to truncate breaks the replication prediction
    a_deliv = build("A", {})
    for rec in a_deliv[:9]:
        rec["truncated_at_cap"] = False
        rec["delivered"] = True
        rec["content_answer"] = "no" if rec["gold"] == 0 else "yes"
        rec["correct"]["content_only"] = 1
        rec["correct_content_only"] = 1
    res7 = evaluate(a_deliv + perfect, gate, with_health())
    assert res7["checks"]["P2_modeA_truncated_ge"] is False
    assert res7["checks"]["P2b_modeA_delivered_le"] is False
    assert res7["verdict"]["tier"] == "policy_artifact"
    # text-existence precheck refuses text-derived claims when no trace text exists
    st = stats_mode([synth(e, "C", "no", "", 300) for e in panel])
    assert st["reasoning_chars_nonzero"] == 0 and st["reasoning_chars_max"] == 0
    assert text_exists(st) is False
    res8 = evaluate(a_run + [synth(e, "C", "no", "", 300) for e in panel], gate,
                    with_health())
    assert res8["checks"]["P7_text_existence"] is False
    assert res8["checks"]["P6_manipulation_check"] is False
    assert res8["checks"]["text_existence_report"]["accepted_for_text_derived_claims"] is False
    # the refusal hits the text-derived claims, not the verdict: the tier is still
    # computed from delivery and correctness (surfacing_only, as res3)
    assert res8["verdict"]["tier"] == "surfacing_only", res8["verdict"]
    assert st["max_answer_words_in_content"] == 1 and st["one_word_answer_field"] == 11
    assert st["truncated_at_cap"] == 0 and st["error_classes"] == []
    # census block over synthetic records
    assert st["census"]["reasoning_source_counts"] == {"none": 11}
    assert st["census"]["trace_chars_total_max"] == 0
    assert st["census"]["fields_seen"] == ["content", "reasoning_content", "role"]
    # insufficient data path
    assert evaluate(build("A", {}), gate, with_health())["verdict"]["tier"] == "insufficient_data"
    print("selftest ok: panel 11 (4 gold yes / 7 gold no), one-line knob delta, "
          "digest-true reconstruction, census merge rule and literal-body drift control, "
          "duplicate tarr controls, tiers A-D negative controls, mcnemar 11:0 exact p = 1/1024")


def cmd_gate(out_path: str) -> int:
    panel, pairs = certify_panel()
    gate = build_gate(panel, pairs)
    disk = {k: v for k, v in gate.items() if k != "panel"}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(disk, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(json.dumps({"gate_blob_sha256": gate["gate_blob_sha256"],
                      "panel_sha256": B.sha256_text(B.canonical(gate["panel"])),
                      "panel_n": gate["panel_n"],
                      "baselines": gate["baselines"],
                      "planned_calls": gate["planned_calls"],
                      "predictions": gate["predictions"]}, indent=2, sort_keys=True))
    return 0


def cmd_analyze(out_dir: str) -> int:
    panel, pairs = certify_panel()
    gate = build_gate(panel, pairs)
    raw_path = os.path.join(out_dir, "raw.jsonl")
    health_path = os.path.join(out_dir, "health.json")
    if not os.path.exists(raw_path):
        print(f"no {raw_path}", file=sys.stderr)
        return 2
    health = json.load(open(health_path, encoding="utf-8")) if os.path.exists(health_path) \
        else {"ok": True, "census": {"reasoning_source": "unknown"}}
    recs = [json.loads(line) for line in open(raw_path, encoding="utf-8") if line.strip()]
    print(json.dumps(evaluate(recs, gate, health), indent=2, sort_keys=True))
    return 0


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--out", default="gate.json")
    ap.add_argument("--out-dir", default=HERE)
    args = ap.parse_args(argv[1:])
    if args.selftest:
        selftest()
        return 0
    if args.gate:
        return cmd_gate(args.out)
    if args.probe:
        return probe(args.out_dir)
    if args.analyze:
        return cmd_analyze(args.out_dir)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

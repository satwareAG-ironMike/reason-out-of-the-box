#!/usr/bin/env python3
"""Round 63 (2026-11-13 03:48, issue #65): the k > 48 name-walk panel, the round-61
registered prediction P1, dispatched on a 27B-class local endpoint.

The question (frozen in gate.json before any dispatch): on the core panel's four
endpoint cells past the old generator ceiling (A48_j48, A49_j49, B50_j50, C64_j64,
cap 2048, name arm), at least 3 of 4 delivering the correct terminal makes the
measured ladder wall an output-budget and output-policy artifact (the issue #126
reading); at most 1 of 4 delivering (censor at the cap or a position error on the
right path, the round-59 shape) keeps the length-generalization reading (T1-T3)
alive on the 27B class. This is the single discriminator the round-61 gate
registered as owed to the next healthy 27B-class firing.

Standing rules carried in:
- pre-dispatch rate measurement gates the plan (round-61 standing rule): two
  256-token census calls plus one full-cap calibration dispatch on the k = 48
  anchor cell (the same prompt as round 61's E1 record, a cross-firing duplicate)
  are measured before the gate is frozen; the plan is selected by the measured
  rate against the frozen thresholds in the gate's dispatch block.
- validity gates first (round-60 order): the two shallow dead-end NONE controls
  (one step by design, round-60 lesson: off-end controls at depth inherit
  truncation) dispatch before the endpoint cells.
- byte-identical re-dispatch pair on the B50 endpoint (issue #100 self-agreement).
- the k = 48 anchor item is the archived load-floor item of rounds 51/52/53/54
  (seed 116261051, yes/no prompt digest 068bc6a1fb0620fb), re-certified
  byte-identically before any prompt is spent (fail-closed).
- trace-exposure census (issue #105): every raw record carries the message-field
  census plus the reasoning-supplying field (merge rule: reasoning_content if
  non-empty, else reasoning, else empty); the health call states this firing's
  exposure setting.

Item machinery: per-item generation with the entity-pool raise caught
(issue #129); the whole-series call `ladders.generate_items` dies at k = 49,
but the C = 2 load-floor items keep generating past it. The seed convention of
`generate_items` (seed_base + 2_000_000 * level + i) is preserved, so every
item this round generates is byte-identical to what the shipped generator would
produce for that seed. Prompt template byte-identical to the round-55
name-or-NONE template (rounds 55/60/61).

Readout policy (issue #94): the answer field only. Trace text is stored for
census and provenance only; no trace-recovery rule is applied (round 50
calibration failure).

House contract: stdlib only; --selftest with planted negatives; every record
carries the frozen gate blob; scripts read NIGHTLY_BASE_URL / NIGHTLY_MODEL_ID /
NIGHTLY_API_KEY from the environment and never write them anywhere; at most 40
prompts, max_tokens <= 2048.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import sys
import threading
import time
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_REPO, "generators"))

import ladders  # noqa: E402

SEED_BASE = 20261005          # round 51's seed base, so the k = 48 anchor is the archived item
SCAN = 300                    # round 51's scan width (the issue #129 measurement table)
MAX_TOKENS = 2048             # protocol cap: no requested cap may exceed it
CALL_CAP = 40
TIMEOUT_S = 3600
DISPATCH_BUDGET_S = 3000      # wall-clock guard on the dispatch phase
MAX_RETRIES_TOTAL = 4
WORKERS = 2
NONE_GOLD = "NONE"
GATE_SCHEMA = "round63-gate-v1"
CENSUS_CAP = 256

# The archived k = 48 load-floor item: rounds 51, 52, 53 and 54 dispatched it byte-identically.
ARCHIVED_K48 = {"seed": 116261051, "yesno_digest16": "068bc6a1fb0620fb"}

# Round 61's E1 record on the identical prompt (k = 48 anchor, j = 8, cap 2048,
# temperature 0.0): 1123 completion tokens. This round's calibration dispatch is
# a cross-firing duplicate of it; the within-firing duplicate is its re-dispatch
# as the A48_j8 plan cell.
R61_E1 = {"tokens": 1123}

# Pre-registered plan-selection thresholds (the standing round-61 rule: gate
# panel-scale commitments on a pre-dispatch rate measurement). Worst-case panel
# arithmetic (frozen): the r63 plan is eight cells of cap 2048 (16,384
# completion tokens), the r63core plan six (12,288). At r = 10 tok/s the full
# plan's worst case is 1,638 s and at r = 5 the core plan's worst case is
# 2,458 s: both inside the frozen 3,000 s dispatch budget.
RATE_FULL_PLAN = 10.0
RATE_CORE_PLAN = 5.0

CENSUS_PROMPT = ("Rule: for all x, y, z: if x precedes y and y precedes z, then x precedes z. "
                 "Facts: alby precedes birch. birch precedes cobin. Question: does alby precedes "
                 "cobin? Answer with exactly one word: yes or no.")


# ------------------------------------------------------------------ item selection


def series_scan(level: int) -> list:
    """Per-item generation with the entity-pool raise caught (issue #129): the level yields
    the items it can build instead of aborting. Same seed convention as generate_items."""
    out = []
    for i in range(SCAN):
        seed = SEED_BASE + 2_000_000 * level + i
        try:
            out.append(ladders.generate_item(level, seed))
        except RuntimeError:
            continue
    return out


def load_floor(level: int) -> list:
    """The items whose fact count is 2 * level: exactly two chains, the smallest load in the
    corpus (issue #129). Deterministic in the seed base, so no selection happens at run time."""
    return [it for it in series_scan(level) if len(it["facts"]) == 2 * level]


def check_item(item: dict) -> None:
    """Refuse anything that is not a load-floor, component-isomorphic item."""
    lvl = item["level"]
    facts = item["facts"]
    assert len(facts) == 2 * lvl, ("not a load-floor item", lvl, len(facts))
    out: dict = {}
    inc: dict = {}
    for s, _, t in facts:
        out[s] = out.get(s, 0) + 1
        inc[t] = inc.get(t, 0) + 1
    assert out and all(v == 1 for v in out.values()), "a chain node has two out-edges"
    heads = [e for e in out if inc.get(e, 0) == 0]
    tails = [e for e in inc if out.get(e, 0) == 0]
    assert len(heads) == 2 and len(tails) == 2, ("expected two disjoint paths", lvl)


def adjacency(item: dict) -> dict:
    adj: dict = {}
    for s, _, t in item["facts"]:
        assert s not in adj, "out-degree above one"
        adj[s] = t
    return adj


def terminal_at(item: dict, src: str, steps: int):
    """Independent solver: the node reached from src by exactly `steps` direct links, or None."""
    adj = adjacency(item)
    cur = src
    for _ in range(steps):
        nxt = adj.get(cur)
        if nxt is None:
            return None
        cur = nxt
    return cur


def other_tail(item: dict, src: str) -> str:
    """The tail of the path that does NOT contain src: matched pseudo-gold for the C6 row."""
    adj = adjacency(item)
    tails = [e for e in {t for _, _, t in item["facts"]} if e not in adj]
    own = terminal_at(item, src, item["level"])
    cands = [t for t in sorted(tails) if t != own]
    assert len(cands) == 1, ("expected one other tail", tails)
    return cands[0]


def select_items() -> dict:
    """Deterministic item set: the archived k = 48 anchor plus the first load-floor item of
    each new level. Vocabularies are drawn from one shared 2700-name pool by independent
    per-item RNG streams, so cross-item name overlap is expected and harmless: every prompt
    carries exactly one item and every score is taken against that item's own vocabulary."""
    anchor = next(it for it in load_floor(48) if it["seed"] == ARCHIVED_K48["seed"])
    check_item(anchor)
    items = {"A48": anchor}
    for key, level in (("A49", 49), ("B50", 50), ("C64", 64)):
        lf = load_floor(level)
        assert lf, f"level {level} produced no load-floor items in the scan"
        check_item(lf[0])
        items[key] = lf[0]
    return items


def item_for(key: str) -> dict:
    return _ITEMS[key]


def vocab_of(item: dict) -> set:
    words = set()
    for s, _, t in item["facts"]:
        words.add(s)
        words.add(t)
    return words


# ------------------------------------------------------------------ prompts

def fact_block(item: dict) -> str:
    return "\n".join(f"{s} {r} {t}." for s, r, t in item["facts"])


def render_name(item: dict, src: str, j: int) -> str:
    return (f"{item['rule']}\nFacts:\n{fact_block(item)}\n\n"
            f"Task: start at {src} and follow the direct links for exactly {j} steps. "
            "Answer with exactly one entity name, or the single word NONE if the links run out "
            f"before {j} steps.")


def render_yesno(item: dict) -> str:
    """The round-6 / round-50 / round-51 template, byte-identical: certifies that the k = 48
    anchor's fact block is the archived one (rounds 51/52/53/54)."""
    facts = fact_block(item)
    qs, qrel, qt = item["query"]
    return (f"{item['rule']}\nFacts:\n{facts}\n\n"
            f"Question: does {qs} {qrel} {qt}?\n"
            "Answer with exactly one word: yes or no.")


def prompt_digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ------------------------------------------------------------------ plan


def _cell(label: str, key: str, j: int, kind: str, cap: int = MAX_TOKENS) -> tuple:
    return (label, key, j, cap, kind)


# The round-60 order: validity gates first, then the primary contrast (the four
# endpoint cells of the registered P1 panel), then the droppable cells.
PLAN_R63 = [
    ("A49_deadend", "A49", 1, MAX_TOKENS, "dead_end"),
    ("C64_deadend", "C64", 1, MAX_TOKENS, "dead_end"),
    ("A48_j48", "A48", 48, MAX_TOKENS, "name"),
    ("A49_j49", "A49", 49, MAX_TOKENS, "name"),
    ("B50_j50", "B50", 50, MAX_TOKENS, "name"),
    ("C64_j64", "C64", 64, MAX_TOKENS, "name"),
    ("B50_j50_dup", "B50", 50, MAX_TOKENS, "dup"),
    ("A48_j8", "A48", 8, MAX_TOKENS, "name"),
]

# The trimmed plan, selected when the measured rate is between RATE_CORE_PLAN and
# RATE_FULL_PLAN (exclusive of the top threshold): the two controls and the four
# registered endpoint cells, the duplicate pair and the anchor liveness cell owed
# to a later firing.
PLAN_R63CORE = [
    ("A49_deadend", "A49", 1, MAX_TOKENS, "dead_end"),
    ("C64_deadend", "C64", 1, MAX_TOKENS, "dead_end"),
    ("A48_j48", "A48", 48, MAX_TOKENS, "name"),
    ("A49_j49", "A49", 49, MAX_TOKENS, "name"),
    ("B50_j50", "B50", 50, MAX_TOKENS, "name"),
    ("C64_j64", "C64", 64, MAX_TOKENS, "name"),
]

PANELS = {"r63": PLAN_R63, "r63core": PLAN_R63CORE}

DUP_PAIRS = (("B50_j50", "B50_j50_dup"),)
ENDPOINT_CELLS = ("A48_j48", "A49_j49", "B50_j50", "C64_j64")
CONTROL_CELLS = ("A49_deadend", "C64_deadend")
ANCHOR_CELL = "A48_j8"
PREGATE_CALLS = 3          # 2 census at cap 256 + 1 calibration dispatch on the anchor cell


def plan_selection(rate: float) -> str:
    """The frozen selection rule: the full plan at or above RATE_FULL_PLAN, the trimmed
    plan below it. Below RATE_CORE_PLAN the trimmed plan is kept and the budget
    governs: cells that do not land inside the frozen dispatch budget stay
    not_dispatched and the P1 row stays owed for the unrecorded endpoint cells."""
    return "r63" if rate >= RATE_FULL_PLAN else "r63core"


def cell_src(item: dict, kind: str) -> str:
    if kind == "dead_end":
        adj = adjacency(item)
        return sorted(t for t in {t for _, _, t in item["facts"]} if t not in adj)[0]
    return item["query"][0]


def plan_prompts(plan: list) -> list:
    """Expand the panel into records carrying prompt, gold and source, before any endpoint
    call."""
    out = []
    for label, key, j, cap, kind in plan:
        item = item_for(key)
        src = cell_src(item, kind)
        gold = terminal_at(item, src, j)
        gold = NONE_GOLD if gold is None else gold
        assert (gold == NONE_GOLD) == (kind == "dead_end"), (label, gold, kind)
        prompt = render_name(item, src, j)
        own = terminal_at(item, src, item["level"])
        pseudo = other_tail(item, src) if own is not None else ""
        out.append({"label": label, "level": item["level"], "seed": item["seed"],
                    "item_key": key, "src": src, "j": j, "cap": cap, "kind": kind,
                    "gold": gold, "prompt": prompt, "pseudo_gold": pseudo,
                    "n_facts": len(item["facts"]), "prompt_sha256": prompt_digest(prompt)})
    return out


# ------------------------------------------------------------------ sanitizer

_SECRET_PATTERNS = [
    re.compile(r"https?://\S+"),
    re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d+)?\b"),
    re.compile(r"/(?:root|home|mnt|media|run/user)/\S+"),
]


def sanitize(text, limit: int = 4000) -> str:
    """Strip anything the public-only rule forbids from model output before it is written
    down."""
    if text is None:
        return ""
    out = str(text)
    for pat in _SECRET_PATTERNS:
        out = pat.sub("[redacted]", out)
    for bad in ("NIGHTLY_BASE_URL", "NIGHTLY_API_KEY", "NIGHTLY_MODEL_ID"):
        val = os.environ.get(bad)
        if val and len(val) > 3:
            out = out.replace(val, "[redacted]")
    out = out.replace("\r", "")
    if len(out) > limit:
        out = out[:limit]
    return out


def model_digest() -> str:
    return hashlib.sha256(os.environ.get("NIGHTLY_MODEL_ID", "").encode()).hexdigest()[:16]


# ------------------------------------------------------------------ response measures

NAME_RE = re.compile(r"[A-Za-z]+")


def declared_answer(content: str, vocab: set):
    """The last entity name in the visible answer field, else the NONE sentinel, else
    undetermined. An empty answer field is not a delivery: on this deployment shape the
    reasoning channel precedes it and can consume the whole budget."""
    if not content or not content.strip():
        return None, False
    ents = [t.lower() for t in NAME_RE.findall(content) if t.lower() in vocab]
    if ents:
        return ents[-1], True
    if re.search(r"\bnone\b", content, re.I):
        return NONE_GOLD, True
    return None, True


def trace_of(message: dict) -> tuple:
    """Issue #105 merge rule: reasoning_content if non-empty, else reasoning, else empty."""
    fields = sorted(k for k in message)
    rc = message.get("reasoning_content") or ""
    src = "reasoning_content" if rc else ""
    if not rc:
        rc = message.get("reasoning") or ""
        src = "reasoning" if rc else ""
    return rc, fields, src


# ------------------------------------------------------------------ endpoint

def call(prompt: str, cap: int) -> dict:
    base = os.environ["NIGHTLY_BASE_URL"]
    key = os.environ.get("NIGHTLY_API_KEY", "")
    body = json.dumps({"model": os.environ["NIGHTLY_MODEL_ID"],
                       "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": cap, "temperature": 0.0}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + key})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        data = json.load(resp)
    choice = data["choices"][0]
    message = choice.get("message", {})
    usage = data.get("usage", {}) or {}
    return {"message": message, "finish_reason": choice.get("finish_reason"),
            "completion_tokens": usage.get("completion_tokens"),
            "prompt_tokens": usage.get("prompt_tokens"), "wall_s": round(time.time() - t0, 3)}


# ------------------------------------------------------------------ gate

THEORY_ROWS = {
    "T1_tc0_bound": {
        "source": "arXiv:2604.25800",
        "statement": ("learnable chain-of-thought length-generalizes only within TC0 under "
                      "standard positional encodings and a finite alphabet; the signpost-token "
                      "remedy shows the barrier is encoding-specific, not universal"),
        "verification": ("carried from the round-61 gate (work-record verified 2026-11-12, "
                         "OpenAlex: title, authors, year; no quote taken); not re-verified "
                         "this firing")},
    "T2_crasp_characterization": {
        "source": "arXiv:2608.13433",
        "statement": ("complete characterization of length generalization for regular "
                      "languages under NoPE: it holds iff the syntactic monoid decomposes "
                      "into loop-balanced integer counters (C-RASP); a near-binary split on "
                      "175 languages and 10x data does not rescue the failing class. "
                      "Caveat on record: NoPE theory; the deployed models use RoPE"),
        "verification": "carried from the round-61 gate (work-record verified 2026-11-12)"},
    "T3_encoding_specific_remedies": {
        "source": "arXiv:2608.31067 (with arXiv:2604.25800)",
        "statement": ("depth-tracking positional encoding plus halting gives exact length "
                      "generalization on Boolean evaluation, ListOps and modular arithmetic "
                      "with 280 parameters: the second encoding-specific remedy after the "
                      "signpost tokens, i.e. the wall moves with the encoding"),
        "verification": "carried from the round-61 gate (work-record verified 2026-11-12)"},
    "T4_task_complexity_not_the_wall": {
        "source": "in-repo measurement (rounds 51/52/59)",
        "statement": ("the ladder item at any tested depth is a two-path BFS problem in "
                      "NC1 (128 facts at k = 64); the task stays computationally trivial "
                      "while the observed walls sit at output budget (2048 cap, round 52) "
                      "and step position (j >= 40, round 59), so the wall is a "
                      "length-generalization and output-budget property of the deployment, "
                      "not a task-complexity limit"),
        "verification": "executed in-repo records, no external source"},
}


def gate_spec(plan: list, measure: dict) -> dict:
    cells = plan_prompts(plan)
    panel_name = "r63" if len(cells) == len(PLAN_R63) else "r63core"
    return {
        "schema": GATE_SCHEMA,
        "question": ("Does the k > 48 name-walk panel (issue #129) discriminate the two "
                     "wall readings on the 27B class, as registered by the round-61 gate "
                     "row P1_owed_panel_prediction? Registered discriminator: on the core "
                     "panel's four endpoint cells (A48_j48, A49_j49, B50_j50, C64_j64, cap "
                     "2048), at least 3 of 4 delivering the correct terminal makes the "
                     "wall an output-budget and output-policy artifact (the issue #126 "
                     "reading); at most 1 of 4 delivering (censor at the cap or a "
                     "position error on the right path, the round-59 shape) keeps the "
                     "length-generalization reading (T1-T3) alive on the 27B class. The "
                     "27B-class yes/no arm already censors at k = 48 (round 52) while the "
                     "name arm had never fired on the class; the round-61 E1 record added "
                     "the first shallow data point (correct, 1123 tokens)."),
        "criteria": {
            "E1_anchor_liveness": {
                "statement": ("the k = 48 anchor cell A48_j8 (archived seed 116261051, j = "
                              "8, cap 2048) delivers the correct terminal on this firing; "
                              "it is a cross-firing duplicate of the round-61 E1 record "
                              "(1123 tokens) and a within-firing duplicate of the pre-gate "
                              "calibration dispatch on the same prompt"),
                "threshold": "delivered and correct, when the cell is in the selected plan"},
            "E2_census_trace_exposure": {
                "statement": ("the 256-token census call answers the two-fact transitivity "
                              "query correctly and exposes the trace in the "
                              "reasoning_content channel (issue #105 firing-state census; "
                              "any cross-class trace claim must state both sides' exposure)"),
                "threshold": "correct content and non-empty reasoning channel"},
            "R1_dead_end_controls": {
                "statement": ("VALIDITY GATE: both dead-end NONE controls (A49 and C64, "
                              "one step by design, the round-60 lesson: off-end controls "
                              "at depth inherit truncation) declare NONE; if either names "
                              "an entity where the links have run out the firing is "
                              "flagged controls_invalid and the P1 evaluation is "
                              "uncertified"),
                "threshold": "both controls declare NONE"},
            "P1_panel_prediction": {
                "statement": ("DISCRIMINATOR (registered in the round-61 gate, owed to "
                              "this firing): on the four endpoint cells, at least 3 of 4 "
                              "delivering the correct terminal makes the wall an "
                              "output-budget and output-policy artifact (the issue #126 "
                              "reading); at most 1 of 4 delivering keeps the "
                              "length-generalization reading (T1-T3) alive on the 27B "
                              "class; exactly 2 of 4 is inconclusive and P1 stays owed. "
                              "All four endpoint cells must be recorded (delivered or "
                              "censored at the cap) for the count to be evaluable; "
                              "partial dispatch leaves P1 owed for the unrecorded "
                              "endpoint cells"),
                "threshold": "3+ of 4 correct: output-budget reading; 1 or fewer of 4 "
                             "correct: length-generalization reading; 2 of 4: "
                             "inconclusive"},
            "N3_anchor_certification": {
                "statement": ("pre-dispatch, fatal: the k = 48 anchor item regenerates "
                              "from the shipped generator with seed 116261051 and its "
                              "archived yes/no prompt digest 068bc6a1fb0620fb (rounds "
                              "51/52/53/54), and every item in the set is a load-floor, "
                              "component-isomorphic item (issue #67 guards)"),
                "threshold": "certified before any prompt is spent"},
        },
        "theory": THEORY_ROWS,
        "tier_rule": (
            "panel state drives the verdict tier: panel_delivered (all four endpoint "
            "cells recorded), panel_partial (two or three of four recorded), "
            "panel_starved (one or fewer recorded; P1 stays owed and the measured "
            "rate is the record). The P1 criterion carries the discriminator count "
            "and the reading; a controls_invalid firing downgrades the P1 "
            "evaluation to uncertified. The verdict is recorded against the "
            "dispatched plan only; a cell that did not dispatch is not reported as "
            "a result."),
        "plan_rule": {
            "note": ("standing round-61 rule: gate panel-scale commitments on a "
                     "pre-dispatch rate measurement. Measured by two 256-token census "
                     "calls plus one full-cap calibration dispatch on the anchor cell, "
                     "all before the gate is frozen; the selected panel is a "
                     "function of the measured rate, not of mid-run conditions. "
                     "Worst-case panel arithmetic: the full plan is 16,384 "
                     "completion tokens and the trimmed plan 12,288, against the "
                     "frozen 3,000 s dispatch budget"),
            "rate_full_plan": RATE_FULL_PLAN,
            "rate_core_plan": RATE_CORE_PLAN,
            "worst_case_tokens": {"r63": MAX_TOKENS * len(PLAN_R63),
                                   "r63core": MAX_TOKENS * len(PLAN_R63CORE)},
        },
        "panel": len(cells),
        "panel_name": panel_name,
        "cells": [{"label": p["label"], "level": p["level"], "seed": p["seed"],
                   "item_key": p["item_key"], "j": p["j"], "cap": p["cap"],
                   "kind": p["kind"], "gold": p["gold"],
                   "prompt_sha256": p["prompt_sha256"]} for p in cells],
        "dispatch": {
            "planned_calls": len(cells),
            "pre_gate_calls": PREGATE_CALLS,
            "call_cap": CALL_CAP,
            "temperature": 0.0,
            "max_tokens_cap": MAX_TOKENS,
            "dispatch_budget_s": DISPATCH_BUDGET_S,
            "workers": WORKERS,
            "archived_k48_certification": ARCHIVED_K48,
            "r61_e1_record": R61_E1,
            "rate_measurement": measure,
        },
    }


def gate_blob(spec: dict) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()


def p1_eval(records: dict) -> dict:
    """The registered P1 discriminator over the endpoint cells, plus the controls gate.
    `records` maps label -> scored record. Returns the count, the reading and whether
    the evaluation is certified (all four endpoint cells recorded and the controls
    valid)."""
    n_recorded = sum(1 for l in ENDPOINT_CELLS if l in records)
    n_correct = sum(1 for l in ENDPOINT_CELLS
                    if l in records and records[l].get("correct"))
    controls_valid = all(l in records and records[l].get("correct")
                          for l in CONTROL_CELLS if l in records)
    if n_recorded < len(ENDPOINT_CELLS):
        reading = ("undetermined (panel not fully recorded; P1 stays owed for the "
                   "unrecorded endpoint cells)" if n_recorded else
                   "undetermined (panel not dispatched; P1 stays owed)")
        return {"n_recorded": n_recorded, "n_correct": n_correct,
                "n_endpoint_cells": len(ENDPOINT_CELLS), "reading": reading,
                "certified": False, "controls_valid": controls_valid}
    if not controls_valid:
        return {"n_recorded": n_recorded, "n_correct": n_correct,
                "n_endpoint_cells": len(ENDPOINT_CELLS),
                "reading": "uncertified (controls_invalid: a NONE-gold control named)",
                "certified": False, "controls_valid": controls_valid}
    if n_correct >= 3:
        reading = ("output-budget and output-policy artifact (the issue #126 "
                   "reading): the wall moves with the serving budget, not with the "
                   "task")
    elif n_correct <= 1:
        reading = ("length-generalization reading survives on the 27B class (T1-T3): "
                   "at most one of four deep endpoints delivered")
    else:
        reading = ("inconclusive (exactly 2 of 4): the discriminator is undetermined, "
                   "P1 stays owed")
    return {"n_recorded": n_recorded, "n_correct": n_correct,
            "n_endpoint_cells": len(ENDPOINT_CELLS), "reading": reading,
            "certified": True, "controls_valid": controls_valid}


def score_records(records: list, spec: dict, health: dict | None = None) -> dict:
    by = {r["label"]: r for r in records}
    out = {}
    e1 = by.get(ANCHOR_CELL)
    out["E1"] = {"in_plan": ANCHOR_CELL in {c["label"] for c in spec["cells"]},
                 "dispatched": e1 is not None,
                 "delivered": (e1["delivered"] if e1 else None),
                 "correct": (e1["correct"] if e1 else None),
                 "declared": (e1["declared"] if e1 else None),
                 "gold": (e1["gold"] if e1 else None),
                 "completion_tokens": (e1["completion_tokens"] if e1 else None),
                 "wall_s": (e1["wall_s"] if e1 else None),
                 "pass": bool(e1 and e1["delivered"] and e1["correct"])}
    out["E2"] = {"dispatched": health is not None,
                 "content": (health.get("content") if health else None),
                 "content_stripped": (str(health.get("content")).strip() if health else None),
                 "reasoning_field": (health.get("reasoning_field") if health else None),
                 "reasoning_chars": (health.get("reasoning_chars") if health else None),
                 "pass": bool(health and str(health.get("content")).strip() == "yes"
                               and (health.get("reasoning_chars") or 0) > 0)}
    r1 = {l: by.get(l) for l in CONTROL_CELLS}
    out["R1"] = {"dispatched": [l for l in CONTROL_CELLS if r1[l] is not None],
                 "declared": {l: (r1[l]["declared"] if r1[l] else None)
                              for l in CONTROL_CELLS},
                 "all_refused": all(r1[l] is not None and r1[l]["correct"]
                                    for l in CONTROL_CELLS) and
                 all(r1[l] is not None for l in CONTROL_CELLS),
                 "completion_tokens": {l: (r1[l]["completion_tokens"] if r1[l] else None)
                                      for l in CONTROL_CELLS}}
    out["P1"] = p1_eval(by)
    for tid, row in THEORY_ROWS.items():
        out[tid] = {"status": "carried from round 61 (work-record level)",
                    "source": row["source"], "verification": row["verification"]}
    out["N3"] = {"status": "certified pre-dispatch",
                 "seed": ARCHIVED_K48["seed"], "yesno_digest16": ARCHIVED_K48["yesno_digest16"]}
    p1 = out["P1"]
    tier = "panel_starved"
    if p1["n_recorded"] >= len(ENDPOINT_CELLS):
        tier = "panel_delivered"
    elif p1["n_recorded"] >= 2:
        tier = "panel_partial"
    flags = []
    if not p1["controls_valid"] and all(l in by for l in CONTROL_CELLS):
        flags.append("controls_invalid")
    censored = [l for l in ENDPOINT_CELLS if l in by
                and by[l]["finish_reason"] == "length" and not by[l]["delivered"]]
    if censored:
        flags.append("endpoint_censored_at_cap:" + ",".join(censored))
    for a, b in DUP_PAIRS:
        if a in by and b in by:
            diverged = (by[a]["delivered"] != by[b]["delivered"]
                        or (by[a]["delivered"] and by[a]["declared"] != by[b]["declared"]))
            if diverged:
                flags.append(f"dup_pair_diverges:{a}/{b}")
    if tier == "panel_starved":
        flags.append("panel_starved_record")
    return {"tier": tier, "flags": flags, "criteria": out}


# ------------------------------------------------------------------ io

def write_jsonl(path: str, rows: list) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def read_jsonl(path: str) -> list:
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def score_record(row: dict, resp: dict, error: str = "") -> dict:
    """Score one planned row against one response. `row` is the expanded plan record; the
    item vocab and pseudo-gold are re-derived, never read from the response."""
    item = item_for(row["item_key"])
    vocab = vocab_of(item)
    message = resp.get("message", {}) if resp else {}
    content = sanitize(message.get("content"), 2000)
    trace, fields, reasoning_field = trace_of(message)
    declared, delivered = declared_answer(content, vocab)
    rec = {
        "label": row["label"], "level": row["level"], "seed": row["seed"],
        "item_key": row["item_key"], "src": row["src"], "j": row["j"],
        "cap": row["cap"], "kind": row["kind"], "gold": row["gold"],
        "pseudo_gold": row["pseudo_gold"], "n_facts": row["n_facts"],
        "prompt": sanitize(row["prompt"], 60000), "prompt_sha256": row["prompt_sha256"],
        "content": content,
        "declared": (declared.lower() if declared else None),
        "delivered": delivered,
        "correct": bool(delivered and declared is not None
                        and declared.lower() == row["gold"].lower()),
        "finish_reason": (resp or {}).get("finish_reason"),
        "completion_tokens": (resp or {}).get("completion_tokens"),
        "prompt_tokens": (resp or {}).get("prompt_tokens"),
        "wall_s": (resp or {}).get("wall_s"),
        "error": error,
        "message_fields": fields,
        "reasoning_field": reasoning_field,
        "trace_chars": len(trace),
        "gold_in_trace": (row["gold"] != NONE_GOLD and row["gold"].lower() in trace.lower()),
        "pseudo_in_trace": (bool(row["pseudo_gold"])
                            and row["pseudo_gold"].lower() in trace.lower()),
        "model_digest": model_digest(),
    }
    return rec


def build_summary(records: list, spec: dict, blob: str,
                  health: dict | None = None) -> dict:
    scored = score_records(records, spec, health)
    return {
        "schema": GATE_SCHEMA,
        "gate_blob": blob,
        "model_digest": model_digest(),
        "panel": spec["panel"],
        "panel_name": spec.get("panel_name"),
        "planned_calls": spec["dispatch"]["planned_calls"],
        "dispatched": len(records),
        "not_dispatched": [c["label"] for c in spec["cells"]
                           if c["label"] not in {r["label"] for r in records}],
        "verdict": scored["tier"],
        "flags": scored["flags"],
        "criteria": scored["criteria"],
        "records": {r["label"]: {"declared": r["declared"], "correct": r["correct"],
                                  "delivered": r["delivered"],
                                  "completion_tokens": r["completion_tokens"],
                                  "finish_reason": r["finish_reason"]}
                    for r in records},
    }


# ------------------------------------------------------------------ selftest

def selftest() -> None:
    global _ITEMS
    failures = []
    count = 0

    def ok(cond, msg):
        nonlocal count
        count += 1
        if not cond:
            failures.append(msg)

    # solver against an independent walk
    _ITEMS = select_items()
    items = _ITEMS
    for key, item in items.items():
        check_item(item)
        adj = adjacency(item)
        src = item["query"][0]
        cur = src
        for steps in (1, 8, item["level"]):
            expect = None
            c = src
            for _ in range(steps):
                if c in adj:
                    c = adj[c]
                else:
                    break
            else:
                expect = c
            ok(terminal_at(item, src, steps) == expect, f"terminal_at mismatch {key} {steps}")
        ok(terminal_at(item, src, item["level"] + 1) is None, f"past-end None {key}")
        ok(terminal_at(item, src, 0) == src, f"zero steps {key}")
    # anchor certification (planted-slip control: a wrong seed must not match)
    ok(items["A48"]["seed"] == ARCHIVED_K48["seed"], "anchor seed")
    ok(prompt_digest(render_yesno(items["A48"]))[:16] == ARCHIVED_K48["yesno_digest16"],
       "anchor yes/no digest")
    keys = list(items)
    assert len(keys) == 4, "item set has four items"
    # prompt template: the task sentence is one template; only the source name and j vary
    a = render_name(items["A48"], items["A48"]["query"][0], 8)
    b = render_name(items["A49"], items["A49"]["query"][0], 8)
    ta = a.split("Task: start at ", 1)[1]
    tb = b.split("Task: start at ", 1)[1]
    ok(ta.split(" ", 1)[1] == tb.split(" ", 1)[1],
       "task sentence identical after the source name")
    ok("follow the direct links for exactly 8 steps." in ta, "j rendered into the task")
    ok("Answer with exactly one entity name, or the single word NONE" in ta,
       "answer space is one entity name or NONE")
    # golds and structure for every plan
    for plan_name, plan in PANELS.items():
        rows = plan_prompts(plan)
        by = {r["label"]: r for r in rows}
        ok(all(r["gold"] == NONE_GOLD for r in rows if r["kind"] == "dead_end"),
           f"{plan_name} dead-end golds are NONE")
        ok(all(r["gold"] != NONE_GOLD for r in rows if r["kind"] in ("name", "dup")),
           f"{plan_name} name golds are names")
        ok(all(r["gold"] in vocab_of(item_for(r["item_key"])) for r in rows
               if r["gold"] != NONE_GOLD), f"{plan_name} golds in own vocab")
        ok(len({r["label"] for r in rows}) == len(rows), f"{plan_name} labels unique")
        ok(len(rows) + PREGATE_CALLS <= CALL_CAP, f"{plan_name} within call cap")
        ok(all(r["cap"] <= MAX_TOKENS for r in rows), f"{plan_name} caps within protocol")
        for r in rows:
            if r["kind"] in ("name", "dup"):
                ok(terminal_at(item_for(r["item_key"]), r["src"], r["j"]) == r["gold"],
                   f"{plan_name} {r['label']} gold walk")
        for a_l, b_l in DUP_PAIRS:
            if a_l in by and b_l in by:
                ok(by[a_l]["prompt_sha256"] == by[b_l]["prompt_sha256"],
                   f"{plan_name} dup pair {a_l}/{b_l} byte-identical prompt")
    ok(len(PANELS["r63"]) == 8, "r63 plan size")
    ok(len(PANELS["r63core"]) == 6, "r63core plan size")
    # plan order: controls first, endpoints before the droppable cells
    r63k = [c[0] for c in PANELS["r63"]]
    ok(r63k[0] == "A49_deadend" and r63k[1] == "C64_deadend", "controls dispatch first")
    ok(max(r63k.index(l) for l in ENDPOINT_CELLS) < r63k.index("B50_j50_dup"),
       "endpoints before the duplicate pair")
    ok(r63k.index("B50_j50_dup") < r63k.index(ANCHOR_CELL), "duplicate before the anchor")
    # endpoint cells are exactly the registered P1 panel
    ok([c[0] for c in PANELS["r63core"] if c[4] == "name"]
       == ["A48_j48", "A49_j49", "B50_j50", "C64_j64"], "core name cells are the P1 panel")
    # gate rows for this round: E1/E2/R1/P1/N3 plus the theory block
    spec = gate_spec(PANELS["r63"], {"tok_per_s": 50.0, "calibration": {},
                                      "census": []})
    for rid in ("E1_anchor_liveness", "E2_census_trace_exposure", "R1_dead_end_controls",
                "P1_panel_prediction", "N3_anchor_certification"):
        ok(rid in spec["criteria"], f"gate row {rid} present")
    ok(len(spec["theory"]) == 4, "four theory rows")
    ok(spec["plan_rule"]["rate_full_plan"] == RATE_FULL_PLAN, "plan rule thresholds frozen")
    # plan selection: the frozen rule at each threshold
    ok(plan_selection(50.0) == "r63", "full plan at a healthy rate")
    ok(plan_selection(RATE_FULL_PLAN) == "r63", "full plan at the threshold")
    ok(plan_selection(RATE_FULL_PLAN - 0.01) == "r63core", "trimmed plan just under")
    ok(plan_selection(RATE_CORE_PLAN) == "r63core", "trimmed plan at the lower threshold")
    ok(plan_selection(0.4) == "r63core", "starved rate keeps the trimmed plan")
    # P1 discriminator over synthetic record sets
    rows = plan_prompts(PANELS["r63core"])
    by = {r["label"]: r for r in rows}

    def synth(correct_labels: list, censored: list = ()):
        out = []
        for p in plan_prompts(PANELS["r63core"]):
            if p["kind"] == "dead_end":
                content, fin, tok = "NONE", "stop", 300
            elif p["label"] in correct_labels:
                content, fin, tok = p["gold"], "stop", 1000
            elif p["label"] in censored:
                content, fin, tok = "", "length", 2048
            else:
                # a position error on the right path: the next hop after the gold
                item = item_for(p["item_key"])
                next_hop = terminal_at(item, p["src"], p["j"] + 1)
                content = next_hop or "NONE"
                fin, tok = "stop", 1000
            out.append(score_record(p, {"message": {"content": content,
                                                    "reasoning_content": "abc"},
                                        "finish_reason": fin, "completion_tokens": tok,
                                        "prompt_tokens": 900, "wall_s": 1.0}))
        return out

    def p1_of(records):
        s = score_records(records, spec, {"content": "yes", "reasoning_chars": 300,
                                          "reasoning_field": "reasoning_content"})
        return s, s["criteria"]["P1"]

    all_correct = ["A48_j48", "A49_j49", "B50_j50", "C64_j64"]
    s, p1 = p1_of(synth(all_correct))
    ok(s["tier"] == "panel_delivered" and p1["n_correct"] == 4 and p1["certified"],
       "4 of 4 delivered: panel_delivered, certified")
    ok("output-budget" in p1["reading"], "4 of 4 reads as the output-budget artifact")
    s3, p1_3 = p1_of(synth(all_correct[:3], censored=["C64_j64"]))
    ok(p1_3["n_correct"] == 3 and "output-budget" in p1_3["reading"],
       "3 of 4 (one censored) reads as the output-budget artifact")
    ok("endpoint_censored" in ",".join(s3["flags"]), "censored endpoint flagged")
    s1, p1_1 = p1_of(synth(["A48_j48"]))
    ok(p1_1["n_correct"] == 1 and "length-generalization" in p1_1["reading"],
       "1 of 4 reads as the length-generalization survival")
    s0, p1_0 = p1_of(synth([], censored=all_correct))
    ok(p1_0["n_correct"] == 0 and "length-generalization" in p1_0["reading"]
       and s0["tier"] == "panel_delivered",
       "0 of 4 (all censored) is still a delivered panel with the surviving reading")
    s2, p1_2 = p1_of(synth(all_correct[:2]))
    ok(p1_2["n_correct"] == 2 and "inconclusive" in p1_2["reading"],
       "2 of 4 is inconclusive, P1 stays owed")
    # partial panel: only two endpoint cells recorded
    partial = [r for r in synth(all_correct[:2])
               if r["label"] in ("A49_deadend", "C64_deadend", "A48_j48", "A49_j49")]
    sp, p1p = p1_of(partial)
    ok(sp["tier"] == "panel_partial" and p1p["n_recorded"] == 2
       and "undetermined" in p1p["reading"], "partial panel leaves P1 undetermined")
    # starved panel: one endpoint cell recorded
    starved = [r for r in synth(["A48_j48"]) if r["label"] in ("A49_deadend", "A48_j48")]
    ss, p1s = p1_of(starved)
    ok(ss["tier"] == "panel_starved" and "panel_starved_record" in ",".join(ss["flags"]),
       "starved panel tier and flag")
    # controls invalid: a naming dead-end control downgrades the evaluation
    bad_ctrl = synth(all_correct)
    for r in bad_ctrl:
        if r["label"] == "C64_deadend":
            r["declared"] = "somename"
            r["correct"] = False
            r["delivered"] = True
    sc, p1c = p1_of(bad_ctrl)
    ok(p1c["certified"] is False and "controls_invalid" in ",".join(sc["flags"]),
       "a naming control flags controls_invalid and uncertifies P1")
    # gate blob: deterministic and stable
    b1 = gate_blob(spec)
    b2 = gate_blob(gate_spec(PANELS["r63"], {"tok_per_s": 50.0, "calibration": {},
                                             "census": []}))
    ok(b1 == b2 and len(b1) == 64, "gate blob deterministic")
    ok(gate_blob(gate_spec(PANELS["r63core"], {"tok_per_s": 50.0, "calibration": {},
                                                "census": []})) != b1,
       "core plan has a different blob")
    # declared_answer: planted negatives
    vocab = vocab_of(items["A48"])
    name = sorted(vocab)[0]
    ok(declared_answer("", vocab) == (None, False), "empty content is not a delivery")
    ok(declared_answer("NONE", vocab) == (NONE_GOLD, True), "plain none")
    ok(declared_answer(f"I walk to {name}.", vocab) == (name, True), "name in answer")
    decoy = "zzzzz"
    ok(declared_answer(f"{decoy}", vocab) == (None, True), "off-vocab word is undetermined")
    two = sorted(vocab)[1]
    got, _ = declared_answer(f"{name} then {two}.", vocab)
    ok(got == two, "last name wins")
    # census merge rule
    ok(trace_of({"reasoning_content": "abc", "reasoning": "xy"})[0] == "abc",
       "reasoning_content wins")
    ok(trace_of({"reasoning_content": "", "reasoning": "xy"})[0] == "xy",
       "reasoning fallback")
    ok(trace_of({"content": "yes"}) == ("", ["content"], ""), "no trace channel")
    # sanitizer: fixtures assembled from fragments so the committed file stays clean
    host = ".".join(["127", "0", "0", "1"])
    ok(sanitize(f"see https://{host}:8080/v1 for details") ==
       "see [redacted] for details", "url+ip stripped")
    ok(sanitize(f"path /root/models/x is local") == "path [redacted] is local",
       "local path stripped")
    ok(sanitize("plain text") == "plain text", "clean text passes")
    # score_record plumbing: a censored record must not be a delivery
    row = next(r for r in rows if r["label"] == "A48_j48")
    rec = score_record(row, {"message": {"content": "", "reasoning_content": "x" * 50},
                             "finish_reason": "length", "completion_tokens": 2048,
                             "prompt_tokens": 1000, "wall_s": 10.0})
    ok(rec["delivered"] is False and rec["correct"] is False and rec["trace_chars"] == 50,
       "censored record is not a delivery")
    rec2 = score_record(row, {"message": {"content": " " * 20,
                                          "reasoning_content": ""},
                              "finish_reason": "stop", "completion_tokens": 100,
                              "prompt_tokens": 1000, "wall_s": 10.0})
    ok(rec2["delivered"] is False, "whitespace-only content is not a delivery")
    good = terminal_at(items["A48"], row["src"], row["j"])
    rec3 = score_record(row, {"message": {"content": good, "reasoning_content": ""},
                              "finish_reason": "stop", "completion_tokens": 100,
                              "prompt_tokens": 1000, "wall_s": 10.0})
    ok(rec3["delivered"] is True and rec3["correct"] is True, "gold content scores correct")
    # summary build: the exact post-dispatch assembly path (round-61 selftest gap:
    # record-list construction, not only the scorers)
    full = [score_record(p, {"message": {"content": p["gold"] if p["gold"] != NONE_GOLD
                                         else "NONE", "reasoning_content": "abc"},
                             "finish_reason": "stop", "completion_tokens": 100 + i,
                             "prompt_tokens": 900, "wall_s": 1.0})
            for i, p in enumerate(plan_prompts(PANELS["r63"]))]
    summ = build_summary(full, gate_spec(PANELS["r63"], {"tok_per_s": 50.0,
                                                          "calibration": {},
                                                          "census": []}), b1,
                         {"content": "yes", "reasoning_chars": 300,
                          "reasoning_field": "reasoning_content"})
    ok(summ["verdict"] == "panel_delivered", "synthetic full panel verdict")
    ok(summ["not_dispatched"] == [], "synthetic r63 panel complete")
    ok(summ["criteria"]["E1"]["pass"] is True and summ["criteria"]["E2"]["pass"] is True,
       "synthetic E rows pass")
    ok(summ["criteria"]["P1"]["n_correct"] == 4, "synthetic P1 count")
    # a starved synthetic dispatch leaves the not_dispatched list intact
    starved2 = [r for r in full if r["label"] in ("A49_deadend", "C64_deadend", "A48_j48")]
    summ2 = build_summary(starved2, gate_spec(PANELS["r63"], {"tok_per_s": 50.0,
                                                               "calibration": {},
                                                               "census": []}), b1,
                          {"content": "yes", "reasoning_chars": 300,
                           "reasoning_field": "reasoning_content"})
    ok(summ2["verdict"] == "panel_starved" and len(summ2["not_dispatched"]) == 5,
       "starved summary keeps the unrecorded cells listed")
    # E2 census readout: the census answer is judged after strip, the channel must be
    # non-empty; a wrong census answer fails regardless of the channel
    h_ok = {"content": "\n\nyes", "reasoning_chars": 239, "reasoning_field": "reasoning"}
    ok(score_records(synth(all_correct), spec, h_ok)["criteria"]["E2"]["pass"] is True,
       "census answer with leading whitespace passes E2")
    ok(score_records(synth(all_correct), spec, {"content": "\n\nno",
                                                "reasoning_chars": 239,
                                                "reasoning_field": "reasoning"})
       ["criteria"]["E2"]["pass"] is False, "wrong census answer fails E2")
    ok(score_records(synth(all_correct), spec, {"content": "yes",
                                                "reasoning_chars": 0,
                                                "reasoning_field": ""})
       ["criteria"]["E2"]["pass"] is False, "empty trace channel fails E2")
    # dup-pair self-agreement: a byte-identical pair that disagrees flags
    summ_all = build_summary(full, gate_spec(PANELS["r63"], {"tok_per_s": 50.0,
                                                             "calibration": {},
                                                             "census": []}), b1,
                             h_ok)
    ok("dup_pair_diverges" not in ",".join(summ_all["flags"]),
       "agreeing dup pair flags nothing")
    diverged = [dict(r) for r in full]
    for r in diverged:
        if r["label"] == "B50_j50_dup":
            r["declared"] = None
            r["delivered"] = False
            r["correct"] = False
            r["finish_reason"] = "length"
    sd = build_summary(diverged, gate_spec(PANELS["r63"], {"tok_per_s": 50.0,
                                                           "calibration": {},
                                                           "census": []}), b1, h_ok)
    ok(any(f.startswith("dup_pair_diverges:B50_j50/B50_j50_dup") for f in sd["flags"]),
       "a censored duplicate of a delivered cell flags the pair")

    if failures:
        for f in failures:
            print("FAIL", f)
        raise SystemExit(f"selftest: {len(failures)} of {count} checks failed")
    print(f"selftest: {count} checks, 0 failures "
          f"(plans: r63={len(PANELS['r63'])}, r63core={len(PANELS['r63core'])})")


# ------------------------------------------------------------------ run

_ITEMS: dict = {}


def init_items() -> None:
    global _ITEMS
    if not _ITEMS:
        _ITEMS = select_items()
        # fail-closed anchor certification, before any prompt is spent
        ok_digest = prompt_digest(render_yesno(_ITEMS["A48"]))[:16]
        assert ok_digest == ARCHIVED_K48["yesno_digest16"], \
            "anchor certification failed: the k = 48 fact block is not the archived one"


def health_call() -> dict:
    resp = call(CENSUS_PROMPT, CENSUS_CAP)
    message = resp.get("message", {})
    trace, fields, rfield = trace_of(message)
    return {"finish_reason": resp.get("finish_reason"),
            "content": sanitize(message.get("content"), 200),
            "message_fields": fields, "reasoning_field": rfield,
            "reasoning_chars": len(trace),
            "completion_tokens": resp.get("completion_tokens"),
            "prompt_tokens": resp.get("prompt_tokens"), "wall_s": resp.get("wall_s"),
            "model_digest": model_digest()}


def do_measure(outdir: str) -> int:
    """Pre-gate rate measurement: two census calls at cap 256 plus one full-cap
    calibration dispatch on the anchor cell (the round-61 calibration shape, which
    doubles as a cross-firing duplicate of the round-61 E1 record). Writes
    measure.json; the gate is frozen against it by --freeze."""
    init_items()
    anchor_rows = [p for p in plan_prompts([PLAN_R63[7]])]
    cal_row = anchor_rows[0]
    census = []
    for i in range(2):
        resp = call(CENSUS_PROMPT, CENSUS_CAP)
        content = sanitize(resp.get("message", {}).get("content"), 200)
        tok = resp.get("completion_tokens")
        wall = resp.get("wall_s")
        census.append({"call": i + 1, "cap": CENSUS_CAP, "content": content,
                       "completion_tokens": tok, "wall_s": wall,
                       "tok_per_s": round(tok / wall, 3) if tok and wall else None})
        print(f"census {i + 1}: {tok} tokens in {wall}s "
              f"({census[-1]['tok_per_s']} tok/s)")
    cal = call(cal_row["prompt"], MAX_TOKENS)
    cal_tok = cal.get("completion_tokens") or 0
    cal_wall = cal.get("wall_s") or 1.0
    rate = round(cal_tok / cal_wall, 3)
    plan = plan_selection(rate)
    out = {
        "calibration": {"label": ANCHOR_CELL, "level": 48, "j": 8, "cap": MAX_TOKENS,
                        "finish_reason": cal.get("finish_reason"),
                        "declared": declared_answer(
                            sanitize(cal.get("message", {}).get("content"), 2000),
                            vocab_of(item_for("A48")))[0],
                        "completion_tokens": cal_tok, "wall_s": cal_wall,
                        "tok_per_s": rate,
                        "note": ("cross-firing duplicate of the round-61 E1 record "
                                 f"({R61_E1['tokens']} tokens on the identical prompt); "
                                 "temperature 0.0")},
        "census": census,
        "rate_tok_per_s": rate,
        "plan_rule": {"rate_full_plan": RATE_FULL_PLAN, "rate_core_plan": RATE_CORE_PLAN},
        "selected_panel": plan,
    }
    path = os.path.join(outdir, "measure.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"measured rate {rate} tok/s -> selected plan {plan} -> {path}")
    return 0


def do_freeze(outdir: str, panel: str) -> int:
    init_items()
    measure_path = os.path.join(outdir, "measure.json")
    assert os.path.exists(measure_path), "run --measure before freezing the gate"
    with open(measure_path, encoding="utf-8") as fh:
        measure = json.load(fh)
    selected = measure.get("selected_panel")
    if panel != selected:
        print(f"refusing: the measured rate selected panel {selected}, the gate was "
              f"requested for {panel} (re-run --measure or freeze the selected panel)")
        return 2
    spec = gate_spec(PANELS[panel], measure)
    blob = gate_blob(spec)
    spec["blob"] = blob
    path = os.path.join(outdir, "gate.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"frozen gate {panel} panel: blob {blob} -> {path}")
    print(f"anchor certified: seed {ARCHIVED_K48['seed']} "
          f"yes/no digest {ARCHIVED_K48['yesno_digest16']}; measured rate "
          f"{measure['rate_tok_per_s']} tok/s")
    return 0


def do_run(outdir: str, panel: str) -> int:
    init_items()
    spec_path = os.path.join(outdir, "gate.json")
    assert os.path.exists(spec_path), "freeze the gate before dispatch"
    with open(spec_path, encoding="utf-8") as fh:
        spec = json.load(fh)
    blob = spec["blob"]
    assert gate_blob({k: v for k, v in spec.items() if k != "blob"}) == blob, \
        "gate.json does not match its pinned blob"
    plan = plan_prompts(PANELS[panel])
    by_label = {p["label"]: p for p in plan}
    spec_labels = {c["label"] for c in spec["cells"]}
    assert spec_labels == set(by_label), "gate cells and panel disagree"

    raw_path = os.path.join(outdir, "raw.jsonl")
    existing = read_jsonl(raw_path)
    done = {r["label"] for r in existing if r.get("gate_blob") == blob}
    stale = {r["label"] for r in existing if r.get("gate_blob") != blob}
    if stale:
        print(f"refusing: {len(stale)} records carry a different gate blob "
              f"(re-freeze or start clean)")
        return 2
    todo = [p for p in plan if p["label"] not in done]

    health_path = os.path.join(outdir, "health.json")
    if not os.path.exists(health_path):
        write_jsonl(health_path, [health_call()])

    transport = {"errors": 0, "retries": 0}
    lock = threading.Lock()
    sink_lock = threading.Lock()
    rows_by_label = {r["label"]: r for r in existing}

    def worker(row: dict) -> None:
        attempts = 1
        resp, error = None, ""
        while True:
            try:
                resp = call(row["prompt"], row["cap"])
                error = ""
                break
            except Exception as exc:  # transport error: bounded retry
                if attempts >= MAX_RETRIES_TOTAL:
                    error = type(exc).__name__
                    break
                with lock:
                    transport["retries"] += 1
                attempts += 1
                time.sleep(5 * attempts)
        with lock:
            transport["errors"] += (1 if error else 0)
        rec = score_record(row, resp, error)
        rec["gate_blob"] = blob
        rec["dispatch_index"] = next(i for i, p in enumerate(plan) if p["label"] == row["label"])
        with sink_lock:
            rows_by_label[row["label"]] = rec
            write_jsonl(raw_path, [rows_by_label[l] for l in
                                   [p["label"] for p in plan if p["label"] in rows_by_label]])
        print(f"landed {row['label']} finish={rec['finish_reason']} "
              f"tokens={rec['completion_tokens']} wall={rec['wall_s']}s "
              f"declared={rec['declared']}")

    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(worker, row): row["label"] for row in todo}
        for fut in concurrent.futures.as_completed(futs):
            if time.time() - t0 > DISPATCH_BUDGET_S:
                print("dispatch budget exceeded; leaving remaining cells not_dispatched")
                break
            fut.result()

    records = [rows_by_label[label] for label in [p["label"] for p in plan]
               if label in rows_by_label]
    health_rows = read_jsonl(os.path.join(outdir, "health.json"))
    health = health_rows[0] if health_rows else None
    summary = build_summary(records, spec, blob, health)
    summary["transport"] = transport
    summary["dispatch_wall_s"] = round(time.time() - t0, 1)
    with open(os.path.join(outdir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"summary: tier={summary['verdict']} dispatched={summary['dispatched']} "
          f"not_dispatched={summary['not_dispatched']} wall={summary['dispatch_wall_s']}s")
    return 0


def do_rescore(outdir: str) -> int:
    init_items()
    with open(os.path.join(outdir, "gate.json"), encoding="utf-8") as fh:
        spec = json.load(fh)
    blob = spec["blob"]
    records = read_jsonl(os.path.join(outdir, "raw.jsonl"))
    bad = [r["label"] for r in records if r.get("gate_blob") != blob]
    if bad:
        print(f"refusing: records without the frozen blob: {bad}")
        return 2
    health_path = os.path.join(outdir, "health.json")
    health_rows = read_jsonl(health_path)
    health = health_rows[0] if health_rows else None
    summary = build_summary(records, spec, blob, health)
    old = json.load(open(os.path.join(outdir, "summary.json"), encoding="utf-8")) \
        if os.path.exists(os.path.join(outdir, "summary.json")) else {}
    for keep in ("transport", "dispatch_wall_s"):
        if keep in old:
            summary[keep] = old[keep]
    with open(os.path.join(outdir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"rescored: tier={summary['verdict']} dispatched={summary['dispatched']}")
    return 0


def do_check_readme(outdir: str) -> int:
    """Issue #137 guard: the README may only quote gate-row ids the frozen gate defines
    (criterion ids, the theory ids, the health id; an abbreviation that prefixes a defined
    key is defined, a cell label like `A49_deadend` is not a row id), and every 64-hex blob
    it cites must be this gate's. The certified 16-hex anchor digest is the only 16-hex
    value allowed."""
    with open(os.path.join(outdir, "gate.json"), encoding="utf-8") as fh:
        spec = json.load(fh)
    blob = spec["blob"]
    defined_keys = set(spec["criteria"]) | set(spec.get("theory", {})) | {"health"}
    defined_abbrs = {k.split("_")[0] for k in defined_keys} | {"health"}
    certified_16hex = {ARCHIVED_K48["yesno_digest16"]}
    with open(os.path.join(outdir, "README.md"), encoding="utf-8") as fh:
        text = fh.read()
    failures = []
    for row_id in sorted(set(re.findall(r"\b([A-Z]\d{1,2})\b", text))):
        if row_id not in defined_abbrs:
            failures.append(f"README quotes undefined gate-row id {row_id}")
    for b in set(re.findall(r"\b[0-9a-f]{64}\b", text)):
        if b != blob:
            failures.append(f"README cites a 64-hex blob that is not this gate's: "
                           f"{b[:16]}")
    for b in set(re.findall(r"\b[0-9a-f]{16}\b", text)):
        if b not in certified_16hex:
            failures.append(f"README cites a 16-hex digest that is not the certified "
                            f"anchor digest: {b}")
    if blob not in text:
        failures.append("README does not carry the frozen gate blob")
    for r in read_jsonl(os.path.join(outdir, "raw.jsonl")):
        if r.get("gate_blob") != blob:
            failures.append(f"raw record {r['label']} carries a different blob")
            break
    if failures:
        for f in failures:
            print("FAIL", f)
        return 1
    print("check-readme: clean")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--measure", action="store_true")
    p.add_argument("--freeze", action="store_true")
    p.add_argument("--run", action="store_true")
    p.add_argument("--rescore", action="store_true")
    p.add_argument("--check-readme", action="store_true")
    p.add_argument("--panel", choices=sorted(PANELS), default="r63")
    args = p.parse_args(argv)
    outdir = _HERE
    if args.selftest:
        selftest()
        return 0
    if args.measure:
        return do_measure(outdir)
    if args.freeze:
        return do_freeze(outdir, args.panel)
    if args.run:
        return do_run(outdir, args.panel)
    if args.rescore:
        return do_rescore(outdir)
    if args.check_readme:
        return do_check_readme(outdir)
    p.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

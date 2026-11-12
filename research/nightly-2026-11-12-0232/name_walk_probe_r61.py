#!/usr/bin/env python3
"""Round 61: where does the theory place the measured ladder wall, and which single
prediction does the now-generatable k > 48 name-walk panel (issue #129) discriminate?

This is a literature round with a rate-limited endpoint record. The slot for this firing
served at about 1 completion token per second under a co-fired load (measured pre-dispatch,
carried in the gate's dispatch block), so the deep name-walk cells could not run; the
dispatched record is the shallow anchor cell E1 (byte-identical to the pre-gate calibration
dispatch) and the shallow dead-end NONE control R1, and the gate registers the panel's
prediction P1 for the next healthy 27B-class firing.

The item machinery is a port of the round-55 name-space stack (prompt template
byte-identical, declared-answer readout, issue #105 census merge rule, sanitizer, gate/blob
discipline) with two load-bearing changes:

1. Item generation is per-item with the entity-pool raise caught (issue #129): the
   whole-series call `ladders.generate_items` dies at k = 49, but the C = 2 load-floor
   items keep generating far past it. The seed convention of `generate_items`
   (seed_base + 2_000_000 * level + i) is preserved, so every item this round generates
   is byte-identical to what the shipped generator would produce for that seed.
2. The k = 48 anchor item is the archived load-floor item of rounds 51/52/53/54
   (seed 116261051, yes/no prompt digest 068bc6a1fb0620fb): the fact block is
   re-certified byte-identical before any dispatch, so this firing pairs cell-for-cell
   with the archived 27B-class yes/no firing on one item, arm versus arm.

Readout policy (issue #94): the answer field only. Trace text is stored for census and
provenance only; no trace-recovery rule is applied (round 50 calibration failure).

House contract: stdlib only; --selftest with planted negatives; every record carries the
frozen gate blob; scripts read NIGHTLY_BASE_URL / NIGHTLY_MODEL_ID / NIGHTLY_API_KEY from
the environment and never write them anywhere; at most 40 prompts, max_tokens <= 2048.
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
GATE_SCHEMA = "round61-gate-v1"

# The archived k = 48 load-floor item: rounds 51, 52, 53 and 54 dispatched it byte-identically
# (round 52 on a 27B class, its P1 row censored 3 of 4 gold-no k = 48 cells at the cap).
ARCHIVED_K48 = {"seed": 116261051, "yesno_digest16": "068bc6a1fb0620fb"}

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


PLAN_FULL = [
    # round-60 order: validity gates first, then the primary contrast, then the droppable
    ("A49_deadend", "A49", 1, MAX_TOKENS, "dead_end"),
    ("C64_deadend", "C64", 1, MAX_TOKENS, "dead_end"),
    ("A48_j48", "A48", 48, MAX_TOKENS, "name"),
    ("A49_j49", "A49", 49, MAX_TOKENS, "name"),
    ("B50_j50", "B50", 50, MAX_TOKENS, "name"),
    ("C64_j64", "C64", 64, MAX_TOKENS, "name"),
    ("A49_j49_dup", "A49", 49, MAX_TOKENS, "dup"),
    ("C64_j64_dup", "C64", 64, MAX_TOKENS, "dup"),
    ("A48_j8", "A48", 8, MAX_TOKENS, "name"),
    ("A48_j32", "A48", 32, MAX_TOKENS, "name"),
    ("A49_j8", "A49", 8, MAX_TOKENS, "name"),
    ("A49_j32", "A49", 32, MAX_TOKENS, "name"),
    ("A49_j40", "A49", 40, MAX_TOKENS, "name"),
    ("B50_j8", "B50", 8, MAX_TOKENS, "name"),
    ("B50_j32", "B50", 32, MAX_TOKENS, "name"),
    ("C64_j8", "C64", 8, MAX_TOKENS, "name"),
    ("C64_j32", "C64", 32, MAX_TOKENS, "name"),
    ("C64_j48", "C64", 48, MAX_TOKENS, "name"),
]

# The reduced panel, used only if the endpoint's warm per-call wall (measured before the
# gate is frozen) makes the full panel unfinishable inside the round's wall clock. Both
# panels share the first two controls, all four endpoints and the A49 duplicate pair.
# The reduced panel, kept for the next healthy 27B-class firing (the prediction P1 in the
# gate is registered against it). Both panels share the first two controls, all four
# endpoints and the A49 duplicate pair.
PLAN_CORE = [
    ("A49_deadend", "A49", 1, MAX_TOKENS, "dead_end"),
    ("C64_deadend", "C64", 1, MAX_TOKENS, "dead_end"),
    ("A48_j48", "A48", 48, MAX_TOKENS, "name"),
    ("A49_j49", "A49", 49, MAX_TOKENS, "name"),
    ("B50_j50", "B50", 50, MAX_TOKENS, "name"),
    ("C64_j64", "C64", 64, MAX_TOKENS, "name"),
    ("A49_j49_dup", "A49", 49, MAX_TOKENS, "dup"),
    ("A48_j8", "A48", 8, MAX_TOKENS, "name"),
    ("A49_j8", "A49", 8, MAX_TOKENS, "name"),
    ("A49_j32", "A49", 32, MAX_TOKENS, "name"),
    ("C64_j8", "C64", 8, MAX_TOKENS, "name"),
    ("C64_j32", "C64", 32, MAX_TOKENS, "name"),
]

PANELS = {"full": PLAN_FULL, "core": PLAN_CORE}

# This firing's dispatch plan. The full name-walk panel could not run: the slot served at
# about 1 completion token per second under a co-fired load (measured pre-dispatch, see the
# README), so the registered deep cells of the panel are owed to the next healthy firing.
# What is dispatched here is the rate-limited record: the shallow anchor cell E1 (byte-
# identical to the pre-gate calibration dispatch, giving a within-firing duplicate) and the
# shallow dead-end NONE control R1.
PLAN_R61 = [
    ("A48_j8", "A48", 8, MAX_TOKENS, "name"),
    ("A49_deadend", "A49", 1, MAX_TOKENS, "dead_end"),
]

PANELS["r61"] = PLAN_R61

DUP_PAIRS = (("A49_j49", "A49_j49_dup"), ("C64_j64", "C64_j64_dup"))
ENDPOINT_CELLS = ("A48_j48", "A49_j49", "B50_j50", "C64_j64")


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
        "verification": "archive round 3 entry, re-verified against the OpenAlex work record "
                        "2026-11-12 (work-record level: title, authors, year; no quote taken)"},
    "T2_crasp_characterization": {
        "source": "arXiv:2608.13433",
        "statement": ("complete characterization of length generalization for regular "
                      "languages under NoPE: it holds iff the syntactic monoid decomposes "
                      "into loop-balanced integer counters (C-RASP); near-binary split on "
                      "175 languages and 10x data does not rescue the failing class. "
                      "Caveat on record: NoPE theory; the deployed models use RoPE"),
        "verification": "next-investigations round-11 candidate (2026-09-10 scan), "
                        "re-verified against the OpenAlex work record 2026-11-12"},
    "T3_encoding_specific_remedies": {
        "source": "arXiv:2608.31067 (with arXiv:2604.25800)",
        "statement": ("depth-tracking positional encoding plus halting gives exact length "
                      "generalization on Boolean evaluation, ListOps and modular arithmetic "
                      "with 280 parameters: the second encoding-specific remedy after the "
                      "signpost tokens, i.e. the wall moves with the encoding"),
        "verification": "next-investigations round-11 candidate (2026-09-10 scan), "
                        "re-verified against the OpenAlex work record 2026-11-12"},
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


def gate_spec(plan: list) -> dict:
    return {
        "schema": GATE_SCHEMA,
        "question": ("Where does the theory place the measured ladder wall, and which "
                     "single prediction does the now-generatable k > 48 name-walk panel "
                     "(issue #129) discriminate? Measured so far on this program: the "
                     "flash-class accuracy turnover at j >= 40 with position errors on the "
                     "right path (round 59), the 27B-class yes/no censors at k = 48 on the "
                     "gold-no cells (round 52), the zero-truncation wall on the current "
                     "flash builds (issue #126), and the generator scan ceiling at k = 48 "
                     "(issue #129, now unlocked at 49/50/64 for the load-floor family). "
                     "This firing's dispatch is rate-limited (about 1 completion token per "
                     "second under a co-fired load, measured pre-dispatch): it records the "
                     "shallow anchor cell E1 and the dead-end control R1, and registers P1 "
                     "for the owed panel."),
        "criteria": {
            "E1_shallow_anchor_delivers": {
                "statement": ("the k = 48 anchor item (archived seed 116261051) at j = 8, "
                              "cap 2048, delivers the correct declared terminal on this "
                              "27B-class firing under the measured ~1 tok/s load"),
                "threshold": "delivered and correct"},
            "E2_census_trace_exposure": {
                "statement": ("the 256-token census call answers the two-fact transitivity "
                              "query correctly and exposes the trace in the "
                              "reasoning_content channel (issue #105 firing-state census)"),
                "threshold": "correct content and non-empty reasoning_content"},
            "R1_dead_end_control": {
                "statement": ("REPORT ROW (no tier input): the k = 49 dead-end NONE control "
                              "(path tail asked one step, j = 1) declares NONE, as it does "
                              "on the flash-class record"),
                "threshold": "reported if dispatched; the control is shallow on purpose "
                             "(round 60 lesson: off-end controls at depth inherit "
                             "truncation)"},
            "P1_owed_panel_prediction": {
                "statement": ("REGISTERED PREDICTION, owed to the next healthy 27B-class "
                              "firing: on the core panel's four endpoint cells (A48_j48, "
                              "A49_j49, B50_j50, C64_j64, cap 2048), if at least 3 of 4 "
                              "deliver the correct terminal the wall is an output-budget "
                              "and output-policy artifact (the issue #126 reading); if at "
                              "most 1 of 4 delivers (censor at the cap or a position error "
                              "on the right path, the round-59 shape) the length-"
                              "generalization reading (T1-T3) survives on the 27B class. "
                              "The two readings are already both partially supported in "
                              "the record; this panel is the cleanest remaining "
                              "discriminator because the 27B-class yes/no arm censors at "
                              "k = 48 while the name arm has never fired on the class."),
                "threshold": "not dispatched this firing: owed"},
            "N3_anchor_certification": {
                "statement": ("pre-dispatch, fatal: the k = 48 anchor item regenerates from "
                              "the shipped generator with seed 116261051 and its archived "
                              "yes/no prompt digest 068bc6a1fb0620fb (rounds 51/52/53/54), "
                              "and every item in the set is a load-floor, component-"
                              "isomorphic item (issue #67 guards)"),
                "threshold": "certified before any prompt is spent"},
        },
        "theory": THEORY_ROWS,
        "tier_rule": ("no experimental tier: this is a literature round with a rate-limited "
                      "endpoint record. E1 and E2 are scored report-only against the "
                      "dispatched records; R1 is reported if dispatched; P1 stays owed. "
                      "The verdict is the literature synthesis stated in the README."),
        "panel": len(plan),
        "cells": [{"label": p["label"], "level": p["level"], "seed": p["seed"],
                   "item_key": p["item_key"], "j": p["j"], "cap": p["cap"],
                   "kind": p["kind"], "gold": p["gold"],
                   "prompt_sha256": p["prompt_sha256"]} for p in plan_prompts(plan)],
        "dispatch": {"planned_calls": len(plan), "call_cap": CALL_CAP,
                     "temperature": 0.0, "max_tokens_cap": MAX_TOKENS,
                     "dispatch_budget_s": DISPATCH_BUDGET_S, "workers": WORKERS,
                     "archived_k48_certification": ARCHIVED_K48,
                     "rate_measurement": {"tokens": 1123, "wall_s": 1116.0,
                                          "tok_per_s": 1.01,
                                          "note": "pre-dispatch calibration dispatch on the "
                                                  "k = 48 anchor at j = 8, cap 2048, under "
                                                  "a co-fired load on the shared host; "
                                                  "two 256-token census calls measured "
                                                  "1.7 and 0.9 tok/s"}},
    }


def gate_blob(spec: dict) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()


def score_records(records: list, spec: dict, health: dict | None = None) -> dict:
    by = {r["label"]: r for r in records}
    out = {}
    e1 = by.get("A48_j8")
    out["E1"] = {"dispatched": e1 is not None,
                 "delivered": (e1["delivered"] if e1 else None),
                 "correct": (e1["correct"] if e1 else None),
                 "declared": (e1["declared"] if e1 else None),
                 "gold": (e1["gold"] if e1 else None),
                 "completion_tokens": (e1["completion_tokens"] if e1 else None),
                 "wall_s": (e1["wall_s"] if e1 else None),
                 "pass": bool(e1 and e1["delivered"] and e1["correct"])}
    out["E2"] = {"dispatched": health is not None,
                 "content": (health.get("content") if health else None),
                 "reasoning_field": (health.get("reasoning_field") if health else None),
                 "reasoning_chars": (health.get("reasoning_chars") if health else None),
                 "pass": bool(health and health.get("content") == "yes"
                               and (health.get("reasoning_chars") or 0) > 0)}
    r1 = by.get("A49_deadend")
    out["R1"] = {"dispatched": r1 is not None,
                 "declared": (r1["declared"] if r1 else None),
                 "refused": (r1["correct"] if r1 else None),
                 "completion_tokens": (r1["completion_tokens"] if r1 else None),
                 "status": ("dispatched" if r1 else "not_dispatched (rate-limited firing)")}
    out["P1"] = {"status": "owed (registered; core panel on the next healthy 27B-class "
                           "firing)", "dispatched": False}
    for tid, row in THEORY_ROWS.items():
        out[tid] = {"status": "verified", "source": row["source"],
                    "verification": row["verification"]}
    out["N3"] = {"status": "certified pre-dispatch",
                 "seed": ARCHIVED_K48["seed"], "yesno_digest16": ARCHIVED_K48["yesno_digest16"]}
    flags = ["endpoint_rate_limited"]
    if r1 is not None:
        flags.append("dead_end_control_refused" if r1["correct"]
                     else "dead_end_control_named_a_token")
    return {"tier": "literature_synthesis_rate_limited_record",
            "flags": flags, "criteria": out}


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
    # pairwise overlap is EXPECTED (shared 2700-name pool, independent per-item streams);
    # what must hold is that every gold is in its own item's vocabulary (checked below)
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
    # golds: name cells have a name gold, dead-end cells have NONE
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
        ok(len(rows) <= CALL_CAP, f"{plan_name} within call cap")
        ok(all(r["cap"] <= MAX_TOKENS for r in rows), f"{plan_name} caps within protocol")
        # every non-NONE gold is a walk-position name, verified by the solver
        for r in rows:
            if r["kind"] in ("name", "dup"):
                ok(terminal_at(item_for(r["item_key"]), r["src"], r["j"]) == r["gold"],
                   f"{plan_name} {r['label']} gold walk")
        # duplicate pairs re-ask the same item, src and j
        for a_l, b_l in DUP_PAIRS:
            if a_l in by and b_l in by:
                ok(by[a_l]["prompt_sha256"] == by[b_l]["prompt_sha256"],
                   f"{plan_name} dup pair {a_l}/{b_l} byte-identical prompt")
    ok(set(PANELS["full"]) and len(PANELS["full"]) == 18, "full panel size")
    ok(len(PANELS["core"]) == 12, "core panel size")
    ok(len(PANELS["r61"]) == 2, "r61 dispatch size")
    # r61 dispatch: the anchor cell and the shallow dead-end control, controls-first order
    rk = [c[0] for c in PANELS["r61"]]
    ok(any(l.endswith("deadend") for l in rk), "r61 carries the dead-end control")
    # panel order: controls first, endpoints before mid-depth
    fk = [c[0] for c in PANELS["full"]]
    ok(fk[0].endswith("deadend") and fk[1].endswith("deadend"), "controls dispatch first")
    ok(fk.index("A48_j48") < fk.index("A48_j8"), "endpoints before mid-depth")
    # gate spec rows for this round: E1/E2/R1/P1/N3 plus the theory block
    spec = gate_spec(PANELS["r61"])
    for rid in ("E1_shallow_anchor_delivers", "E2_census_trace_exposure",
                "R1_dead_end_control", "P1_owed_panel_prediction",
                "N3_anchor_certification"):
        ok(rid in spec["criteria"], f"gate row {rid} present")
    ok(len(spec["theory"]) == 4, "four theory rows")
    # scoring on synthetic records: E1 pass, R1 report, P1 owed
    rows = plan_prompts(PANELS["r61"])
    by = {r["label"]: r for r in rows}
    synth = [score_record(p, {"message": {"content": p["gold"], "reasoning_content": "abc"},
                              "finish_reason": "stop", "completion_tokens": 100,
                              "prompt_tokens": 900, "wall_s": 1.0}) for p in rows]
    scored = score_records(synth, spec, {"content": "yes", "reasoning_chars": 300,
                                         "reasoning_field": "reasoning_content"})
    ok(scored["criteria"]["E1"]["pass"] is True, "synthetic E1 passes")
    ok(scored["criteria"]["E2"]["pass"] is True, "synthetic E2 passes")
    ok(scored["criteria"]["R1"]["refused"] is True, "synthetic R1 refuses")
    ok(scored["criteria"]["P1"]["status"].startswith("owed"), "P1 stays owed")
    ok(scored["tier"] == "literature_synthesis_rate_limited_record", "round tier")
    # planted negatives: E1 must fail on a wrong name, E2 on an empty trace
    bad = [dict(synth[0]), dict(synth[1])]
    wrong = sorted(vocab_of(items["A48"]))[0]
    if wrong != by["A48_j8"]["gold"]:
        bad[0]["declared"] = wrong
        bad[0]["correct"] = False
    scored_bad = score_records(bad, spec, {"content": "yes", "reasoning_chars": 0,
                                           "reasoning_field": ""})
    ok(scored_bad["criteria"]["E1"]["pass"] is False, "wrong name must fail E1")
    ok(scored_bad["criteria"]["E2"]["pass"] is False, "empty trace must fail E2")
    # R1 not dispatched: the status must say so, and the tier must not change
    scored_missing = score_records([synth[0]], spec, None)
    ok(scored_missing["criteria"]["R1"]["status"].startswith("not_dispatched"),
       "missing R1 reported as not dispatched")
    ok(scored_missing["tier"] == scored["tier"], "missing R1 does not move the tier")
    # gate blob: deterministic and stable
    b1, b2 = gate_blob(spec), gate_blob(gate_spec(PANELS["r61"]))
    ok(b1 == b2 and len(b1) == 64, "gate blob deterministic")
    ok(gate_blob(gate_spec(PANELS["core"])) != b1, "core panel has a different blob")
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
    row = plan_prompts(PANELS["full"])[2]  # A48_j48
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
    # summary build: a complete record set for the r61 dispatch reproduces the round tier
    r61 = [score_record(p, {"message": {"content": p["gold"] if p["gold"] != NONE_GOLD
                                        else "NONE", "reasoning_content": "abc"},
                            "finish_reason": "stop", "completion_tokens": 100 + i,
                            "prompt_tokens": 900, "wall_s": 1.0})
           for i, p in enumerate(plan_prompts(PANELS["r61"]))]
    summ = build_summary(r61, spec, b1, {"content": "yes", "reasoning_chars": 300,
                                         "reasoning_field": "reasoning_content"})
    ok(summ["verdict"] == "literature_synthesis_rate_limited_record", "round tier on synthetics")
    ok(summ["not_dispatched"] == [], "synthetic r61 panel complete")
    ok(summ["criteria"]["E1"]["pass"] is True and summ["criteria"]["E2"]["pass"] is True,
       "synthetic E rows pass")

    if failures:
        for f in failures:
            print("FAIL", f)
        raise SystemExit(f"selftest: {len(failures)} of {count} checks failed")
    print(f"selftest: {count} checks, 0 failures "
          f"(panels: full={len(PANELS['full'])}, core={len(PANELS['core'])})")


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
    resp = call(CENSUS_PROMPT, 256)
    message = resp.get("message", {})
    trace, fields, rfield = trace_of(message)
    return {"finish_reason": resp.get("finish_reason"),
            "content": sanitize(message.get("content"), 200),
            "message_fields": fields, "reasoning_field": rfield,
            "reasoning_chars": len(trace),
            "completion_tokens": resp.get("completion_tokens"),
            "prompt_tokens": resp.get("prompt_tokens"), "wall_s": resp.get("wall_s"),
            "model_digest": model_digest()}


def do_freeze(outdir: str, panel: str) -> int:
    init_items()
    spec = gate_spec(PANELS[panel])
    blob = gate_blob(spec)
    spec["blob"] = blob
    path = os.path.join(outdir, "gate.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"frozen gate {panel} panel: blob {blob} -> {path}")
    print(f"anchor certified: seed {ARCHIVED_K48['seed']} "
          f"yes/no digest {ARCHIVED_K48['yesno_digest16']}")
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
    p.add_argument("--freeze", action="store_true")
    p.add_argument("--run", action="store_true")
    p.add_argument("--rescore", action="store_true")
    p.add_argument("--check-readme", action="store_true")
    p.add_argument("--panel", choices=sorted(PANELS), default="r61")
    args = p.parse_args(argv)
    outdir = _HERE
    if args.selftest:
        selftest()
        return 0
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

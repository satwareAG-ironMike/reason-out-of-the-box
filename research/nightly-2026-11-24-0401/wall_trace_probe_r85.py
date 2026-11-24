#!/usr/bin/env python3
"""Round 85 (2026-11-24 04:01, nightly lane, issue #65): instruction arms at the wall.

Question. Round 84 found that a reasoning ban throttles the trace but never switches it
off, and its verdicts never moved - but every item it used was one this build solves, so
the verdict invariance was unfalsifiable there. The discriminating test is the same four
instruction arms at or past this build's measured wall, where verdicts do move: does the
instruction arm change accuracy when the task is hard enough for the trace to fail?

Two candidate readings, opposite predictions. If the trace is the computation (C4 false
for this build at depth), a ban that shortens the trace should lose accuracy at the wall
(shorter enumeration, more drift) while a permission that lengthens it should gain some.
If the trace is an epiphenomenal narration (C4), the verdict moves with the wall, not with
the instruction: all four arms land at the same accuracy and only the delivery surface
(delivery state, censoring, trace length) differs between arms.

Method. One task surface, one gold, four instruction arms that differ only in what they
say about reasoning (the item text is byte-identical across arms):

  baseline   the frozen judge template verbatim (evaluation/frozen/verify.py build_prompt)
  suppression  + an imperative: produce no reasoning at all
  ironic     + the same ban in negated form ("do not think about the chain"), the
               white-bear / ironic-process framing from process-suppression research
  posthoc    + an explicit request to reason, after the one-word answer

The wall comes from the build's own behaviour, not from the frozen grid: this serving
build self-stops at roughly 1,556 completion tokens (the "thought long enough" marker in
archived firings on the same id string) and the frozen grid tops out at k = 8, below the
wall. The panel therefore runs at k = 64, beyond the frozen grid (the sanctioned
nightly-lane wall pattern of the archived load-floor rounds), with a 2048-token budget so
the endpoint cap is not the wall and censoring, when it appears, is build-driven. A
pre-gate census (baseline arm at k = 32 / 48 / 64) locates the wall: the smallest census
level that is not fully delivered_correct. If every census level is fully correct, the
panel sits at the top of the available depth and the round states a top-of-depth
invariance reading instead of a wall claim.

22 planned prompts: 3 census rows plus 19 panel rows (4 arms x 5 items at k = 64, the
census k = 64 row doubling as the panel's baseline item 0). Under the 40-prompt round
cap and inside the 2026-W48 weekly cap (research/AGENTS.md, issue #195): round 84 billed
34 generations to this ISO week; 34 + 22 = 56, under 80.

Predictions frozen before dispatch (gate.json): the wall is identified by the census (G0),
the ban reduces the trace (G2, round 84's tiers), the negated ban backfires (G3), the
verdict is invariant to the ban among stop-terminated pairs (G4), the ban rescues at the
wall (G5, with the issue #145 denominator discipline: n_eligible and per-arm censoring
reported, and below the minimum-eligible threshold the outcome is inconclusive_budget,
never a competence claim), and the permission lengthens the generation (G6). Verdict
faithfulness is read answer-level only, never from the trace text (issue #94); the trace
is reported as a measured length, not scored as evidence. The build's self-stop signature
(the "long enough" marker) is censused per record as a readout, not a gate row.

Family: ladders k-hop reachability, beyond-grid k = 64 (the generator called directly, as
the archived load-floor rounds did), fresh seed base 20261124 (the judge's run-date
policy). max_tokens 2048, temperature 0.0, one dispatch at a time.

Kill rule (pre-registered): the pre-dispatch measurement (measure.json) decides the
dispatch plan; if its worst-case estimate exceeds 45 minutes the panel is not dispatched,
the census stands as the round's record, and a zero-panel kill report is posted (the
round-61 rule).

Evidence label: Executed, exploratory. n = 5 items per arm at one depth on one build of
an exploratory-only model class; no confirmatory cell (issue #196 blocks that track).

Endpoint config comes only from NIGHTLY_BASE_URL / NIGHTLY_MODEL_ID / NIGHTLY_API_KEY and
is never written to disk; every model-facing string is sanitized before it is recorded
(public-only rule). The build is pinned by the sha256 digest of NIGHTLY_MODEL_ID (first
16 hex), the house convention; a digest match across rounds is a serving-identity match,
not a proof of identical binaries.

Usage:
    python3 wall_trace_probe_r85.py --selftest     # arithmetic + negative controls, no I/O
    python3 wall_trace_probe_r85.py --freeze-gate  # write gate.json, before any dispatch
    python3 wall_trace_probe_r85.py --measure      # pre-dispatch census, writes measure.json
    python3 wall_trace_probe_r85.py --dispatch     # run the plan, append raw.jsonl
    python3 wall_trace_probe_r85.py --summarize    # score raw.jsonl, write summary.json
    python3 wall_trace_probe_r85.py --check-readme # issue #137 row-and-blob guard
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
FROZEN = os.path.join(REPO, "evaluation", "frozen", "verify.py")

GATE_FILE = os.path.join(HERE, "gate.json")
MEASURE_FILE = os.path.join(HERE, "measure.json")
RAW_FILE = os.path.join(HERE, "raw.jsonl")
SUMMARY_FILE = os.path.join(HERE, "summary.json")

TIMEOUT_S = 150
MAX_TOKENS = 2048
SEED_BASE = 20261124
PANEL_LEVEL = 64
CENSUS_LEVELS = (32, 48, 64)
ITEMS_PER_LEVEL = 5
PROMPT_CAP = 40  # research/AGENTS.md per-round cap
# Item selection (registered): the generator draws n_chains = randint(2, level + 2), so a
# level-64 item can carry up to 4,224 facts and turn the depth question into a load
# question. The load-ceiling rule keeps the panel a depth reading: take the first
# ITEMS_PER_LEVEL qualifying items per level, where qualifying means at most 4 chains
# (at most 4 x level facts); the scanned-and-skipped seeds are recorded in the gate.
MAX_CHAINS = 4
SCAN_BATCH = 400

ARMS = ("baseline", "suppression", "ironic", "posthoc")
# What each arm appends to the frozen base prompt. "" keeps the baseline byte-identical to
# the judge template, which is the control the whole contrast needs.
ARM_SUFFIX = {
    "baseline": "",
    "suppression": " Give no reasoning, no explanation and no steps: output only the single "
                   "answer word, nothing else.",
    "ironic": " Do not think about the chain of precedes links step by step. "
              "Answer with the single word only.",
    "posthoc": " First give the single-word answer, then briefly explain your reasoning.",
}
# The gate thresholds, frozen here rather than at scoring time. Tiers are ordered: the full
# pass always implies the partial pass, never the reverse.
TRACE_PRESENT_STRONG = 0.25        # G2 full: the ban suppresses the trace on >= 75% of items
IRONIC_BACKFIRE_MARGIN = 2         # G3: ironic traces >= baseline + 2 records
VERDICT_INVARIANCE_PASS = 0.80     # G4: share of comparable items with an invariant verdict

ROW_ID_RE = re.compile(r"\b(G\d|H\d)\b")
PINNED_BLOB_RE = re.compile(r"gate blob `([0-9a-f]{64})`")
BLOB_RE = re.compile(r"\b[0-9a-f]{64}\b")

_THINK_OPEN = "<" + "think>"
_THINK_CLOSE = "<" + "/think>"


# ------------------------------------------------------------------ sanitizer

_SECRET_PATTERNS = [
    re.compile(r"https?://\S+"),
    re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d+)?\b"),
    re.compile(r"/(?:root|home|mnt|media|run/user)/\S+"),
    # Serving-id labels (issue #85). Built by concatenation so this file carries no
    # pattern instance of its own.
    re.compile(r"\b[a-z0-9][a-z0-9._-]*-(?:" + "iq" + r"\d+|q\d+|ud-q\d+)(?:[_-]?[a-z0-9]+)?\b"),
]


def sanitize(text, limit: int = 2000) -> str:
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
    return out[:limit]


# ------------------------------------------------------------------ frozen judge

def load_frozen():
    spec = importlib.util.spec_from_file_location("r84_frozen_verify", FROZEN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FROZEN_MOD = None


def frozen():
    global FROZEN_MOD
    if FROZEN_MOD is None:
        FROZEN_MOD = load_frozen()
    return FROZEN_MOD


def base_prompt(item: dict) -> str:
    """The frozen judge's ladders template, verbatim (no CoT scaffold, no gold)."""
    return frozen().build_prompt(item, "ladders")["text"]


def gold(item: dict) -> str:
    return frozen().gold_of(item, "ladders")


def select_items(level: int, count: int) -> tuple[list[dict], list[int]]:
    """The registered load-ceiling selection (see MAX_CHAINS). Scans seeds in ascending
    scan-index order and picks the first `count` items whose fact block fits the ceiling.
    Beyond the frozen grid the generator's entity pool (2,400 names) can exhaust on
    high-chain items, so an ungeneratable seed is a recorded skip, not an error.
    Returns the picked items and the list of examined scan-indices (picked + skipped +
    ungeneratable), so the gate records exactly which seeds were used and which were not."""
    gen = frozen().GEN["ladders"]
    picked, examined = [], []
    for idx in range(SCAN_BATCH):
        seed = SEED_BASE + 2_000_000 * level + idx
        examined.append(idx)
        if len(picked) >= count:
            break
        try:
            item = gen.generate_item(level, seed)
        except RuntimeError:
            continue  # entity pool exhausted on this seed: recorded skip
        if len(item["facts"]) <= MAX_CHAINS * level:
            picked.append(item)
    if len(picked) < count:
        raise SystemExit(f"selection: {len(picked)}/{count} qualifying items at level {level} "
                         f"after {len(examined)} seeds")
    return picked, examined


def select_manifest() -> dict:
    manifest = {}
    for level in CENSUS_LEVELS:
        picked, scanned = select_items(level, 1)
        manifest[str(level)] = {
            "picked_seeds": [i["seed"] for i in picked],
            "scanned": len(scanned),
        }
    picked, scanned = select_items(PANEL_LEVEL, ITEMS_PER_LEVEL)
    manifest[str(PANEL_LEVEL)] = {
        "picked_seeds": [i["seed"] for i in picked],
        "scanned": len(scanned),
    }
    return manifest


def build_plan() -> list[dict]:
    """Census rows (baseline only, one item per census level) plus the four-arm panel at
    PANEL_LEVEL; the census row at the panel level doubles as the panel's baseline item.
    Items are taken straight from the generator module (beyond the frozen grid, the
    sanctioned nightly-lane wall pattern); the frozen judge still builds the prompt and
    judges the gold."""
    gen = frozen().GEN["ladders"]
    plan = []
    for level in CENSUS_LEVELS:
        items, _ = select_items(level, 1)
        item = items[0]
        base = base_prompt(item)
        plan.append({
            "label": f"L{level}_i{item['seed'] % 1000}_baseline",
            "level": level,
            "item_index": item["seed"],
            "arm": "baseline",
            "item_key": f"L{level}_i{item['seed'] % 1000}",
            "prompt": base,
            "base_chars": len(base),
            "gold": gold(item),
        })
    items, _ = select_items(PANEL_LEVEL, ITEMS_PER_LEVEL)
    for item in items:
        tag = item["seed"] % 1000
        for arm in ARMS:
            base = base_prompt(item)
            plan.append({
                "label": f"L{PANEL_LEVEL}_i{tag}_{arm}",
                "level": PANEL_LEVEL,
                "item_index": item["seed"],
                "arm": arm,
                "item_key": f"L{PANEL_LEVEL}_i{tag}",
                "prompt": base + ARM_SUFFIX[arm],
                "base_chars": len(base),
                "gold": gold(item),
            })
    seen = set()
    out = []
    for p in plan:
        if p["label"] in seen:
            continue
        seen.add(p["label"])
        out.append(p)
    return out


# ------------------------------------------------------------------ response measures

def split_trace(message: dict) -> dict:
    """Return the interior trace and the visible answer field.

    Channel priority follows the issue #105 census: reasoning_content if non-empty, else
    reasoning. On a deployment that serves no reasoning field the trace is inline in the
    content between the think tags, and the visible field is what survives after the last
    close tag: text before the commitment is the traversal, not the declared answer.
    `think_closed` is None when the reply carries no think tag at all: a zero-trace reply is
    not the same observation as a closed one.
    """
    fields = sorted(message.keys())
    rc = message.get("reasoning_content") or ""
    src = "reasoning_content" if rc else ""
    if not rc:
        rc = message.get("reasoning") or ""
        src = "reasoning" if rc else ""
    content = message.get("content") or ""
    inline_open = content.count(_THINK_OPEN)
    inline_close = content.count(_THINK_CLOSE)
    if not rc and inline_open:
        if inline_close < inline_open:
            # Never closed. The structural fact is recorded as such; the conservative rule
            # lives in delivery_state, which demands a stop termination either way, so a
            # traversal cut by the cap can never score on a stray token inside itself.
            visible, closed, inline_trace = content.rsplit(_THINK_OPEN, 1)[-1].strip(), False, content
        else:
            head, _, tail = content.rpartition(_THINK_CLOSE)
            visible, closed, inline_trace = tail.strip(), True, head
    else:
        visible, closed, inline_trace = content.strip(), None, ""
    return {
        "message_fields": fields,
        "trace_source": src or ("inline_think" if inline_open else "none"),
        "trace": rc or inline_trace,
        "visible": visible,
        "think_open": inline_open,
        "think_close": inline_close,
        "think_closed": closed,
    }


YES_NO_RE = re.compile(r"\b(yes|no)\b", re.IGNORECASE)


def declared_verdict(visible: str):
    """Last standalone yes/no in the visible field. Last, because a traversal that enumerates
    both answer classes must not be read as a verdict from its first mention."""
    hits = YES_NO_RE.findall(visible or "")
    if not hits:
        return None, False
    return hits[-1].lower(), True


def delivery_state(rec: dict) -> str:
    """House census (issue #145): a censored arm is not a wrong arm.

    Only a stop-terminated record can deliver: a truncation ends inside the traversal, so a
    yes/no that appears there is a mid-enumeration token, not a declared verdict (the
    round-50 finding)."""
    if rec["finish_reason"] != "stop":
        return "censored_at_cap" if rec["finish_reason"] == "length" else "not_delivered"
    if not rec["declared_present"]:
        return "non_answer"
    return "delivered_correct" if rec["declared"] == rec["gold"] else "delivered_wrong"


SELF_STOP_RE = re.compile(r"long enough|time to give my answer")


def model_digest():
    """House build pin: sha256 of the serving id, first 16 hex (the rounds 55-73
    convention). A digest match across rounds is a serving-identity match, not a proof
    of identical binaries. None when the id is unset; --freeze-gate refuses to run in
    that case (round-78 rule: an empty id hashes to a fixed value and the guard's
    message would be wrong)."""
    m = os.environ.get("NIGHTLY_MODEL_ID")
    if not m:
        return None
    return hashlib.sha256(m.encode()).hexdigest()[:16]


def measure_record(spec: dict, res: dict) -> dict:
    parts = split_trace(res["message"])
    visible = sanitize(parts["visible"], limit=400)
    trace = sanitize(parts["trace"], limit=1600)
    declared, present = declared_verdict(visible)
    rec = {
        "label": spec["label"],
        "level": spec["level"],
        "item_index": spec["item_index"],
        "arm": spec["arm"],
        "item_key": spec["item_key"],
        "gold": spec["gold"],
        "model_digest": model_digest(),
        "served_surface": "chat_completions",
        "prompt_chars": len(spec["prompt"]),
        "instruction_added_chars": len(spec["prompt"]) - spec["base_chars"],
        "prompt": sanitize(spec["prompt"], limit=2000),
        "message_fields": parts["message_fields"],
        "trace_source": parts["trace_source"],
        "trace_present": bool(trace.strip()),
        "trace_chars": len(trace),
        "trace": trace,
        # Readout, not a gate row: the build's self-stop signature on this id string.
        # Computed on the sanitized (capped) trace, so it means "marker inside the
        # recorded window", which for this build sits well inside the 1600-char cap.
        "self_stop_marker": bool(SELF_STOP_RE.search(trace)),
        "think_open": parts["think_open"],
        "think_close": parts["think_close"],
        "think_closed": parts["think_closed"],
        "visible": visible,
        "visible_chars": len(visible),
        "declared": declared,
        "declared_present": present,
        "finish_reason": res["finish_reason"],
        "completion_tokens": res["completion_tokens"],
        "prompt_tokens": res["prompt_tokens"],
        "wall_s": res["wall_s"],
        "tok_per_s": res["tok_per_s"],
    }
    rec["delivery_state"] = delivery_state(rec)
    return rec


# ------------------------------------------------------------------ endpoint

def tok_rate(completion_tokens, wall_s):
    if not completion_tokens or not wall_s:
        return None
    return round(completion_tokens / wall_s, 3)


def chat(prompt: str, cap: int) -> dict:
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
    usage = data.get("usage", {}) or {}
    wall = round(time.time() - t0, 3)
    completion = usage.get("completion_tokens")
    return {"message": choice.get("message", {}) or {},
            "finish_reason": choice.get("finish_reason"),
            "completion_tokens": completion,
            "prompt_tokens": usage.get("prompt_tokens"),
            "wall_s": wall, "tok_per_s": tok_rate(completion, wall)}


# ------------------------------------------------------------------ gate

ELIGIBLE_MIN = 3  # G5 minimum eligible pairs; below it the outcome is inconclusive_budget


def gate_spec(planned: list) -> dict:
    arms = {}
    for arm in ARMS:
        rows = [p for p in planned if p["arm"] == arm]
        arms[arm] = {"n": len(rows), "labels": [r["label"] for r in rows]}
    panel_items = sorted({p["item_index"] for p in planned
                          if p["level"] == PANEL_LEVEL and p["arm"] == "baseline"})
    census_items = sorted({p["item_index"] for p in planned
                           if p["level"] in CENSUS_LEVELS})
    spec = {
        "round": 85,
        "firing": "2026-11-24T04:01+01:00",
        "issue": 65,
        "question": "At or past this build's measured wall, do the four instruction arms "
                    "change the verdict, or only the delivery surface?",
        "family": "ladders",
        "beyond_frozen_grid": True,
        "levels": list(CENSUS_LEVELS),
        "panel_level": PANEL_LEVEL,
        "seed_base": SEED_BASE,
        "item_selection": {
            "rule": "first qualifying items in scan order, at most "
                    f"{MAX_CHAINS} chains per item (<= {MAX_CHAINS} x level facts); "
                    "skipped seeds are recorded",
            "max_chains": MAX_CHAINS,
            "scan_batch": SCAN_BATCH,
            "census_seeds": census_items,
            "panel_seeds": panel_items,
        },
        "model_digest": model_digest(),
        "arms": arms,
        "planned_dispatches": len(planned),
        "prompt_cap": PROMPT_CAP,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.0,
        "kill_rule": "if measure.json's worst-case estimate exceeds 45 minutes the panel is "
                     "not dispatched; the census stands as the round record and a zero-panel "
                     "kill report is posted (round-61 rule)",
        "criteria": [
            {"id": "G0", "name": "wall_identified",
             "rule": "the census rows identify the smallest census level that is not fully "
                     "delivered_correct; if every census level is fully correct, the panel "
                     "sits at the top of the available depth and the round states a "
                     "top-of-depth invariance reading instead of a wall claim."},
            {"id": "G1", "name": "trace_channel_exposed",
             "rule": "At least one dispatched record carries a non-empty trace on a named "
                     "channel; without exposure every trace claim below is answer-level only "
                     "(issue #105)."},
            {"id": "G2", "name": "ban_reduces_trace",
             "rule": f"partial: the suppression arm traces strictly fewer records than baseline "
                     f"AND its trace-present fraction is below baseline's. full: partial AND the "
                     f"suppression trace-present fraction is at or under {TRACE_PRESENT_STRONG}."},
            {"id": "G3", "name": "negated_ban_backfires",
             "rule": f"ironic traces at least baseline + {IRONIC_BACKFIRE_MARGIN} records, "
                     "the ironic-process prediction."},
            {"id": "G4", "name": "verdict_invariant_to_the_ban",
             "rule": f"among items with a stop-terminated verdict in BOTH baseline and "
                     f"suppression, at least {VERDICT_INVARIANCE_PASS:.0%} carry the same "
                     "verdict AND both arms agree with the judge gold on every one of them."},
            {"id": "G5", "name": "ban_rescues_at_the_wall",
             "rule": f"eligible items are those whose BASELINE record is not delivered_correct; "
                     f"pass: the suppression arm is delivered_correct on at least one eligible "
                     f"item AND n_eligible >= {ELIGIBLE_MIN}. Below the minimum, the outcome is "
                     "inconclusive_budget, never a competence claim (issue #145)."},
            {"id": "G6", "name": "permission_lengthens",
             "rule": "the posthoc arm's median completion_tokens strictly exceeds the "
                     "baseline arm's median (round 84's lengthening finding, re-registered "
                     "at the 2048 budget)."},
        ],
        "health": {"id": "H1", "name": "dispatch_integrity",
                   "rule": "Every dispatched record has a non-null finish_reason and a "
                           "completion_tokens count; a transport failure is recorded, not scored."},
    }
    spec["blob"] = gate_blob(spec)
    return spec


def gate_blob(spec: dict) -> str:
    src = {k: v for k, v in spec.items() if k != "blob"}
    return hashlib.sha256(json.dumps(src, sort_keys=True).encode()).hexdigest()


# ------------------------------------------------------------------ scoring

def score(records: list, spec: dict) -> dict:
    blob = spec["blob"]
    out: dict = {"gate": blob, "records": len(records), "arms": {}}
    for arm in ARMS:
        rows = [r for r in records if r["arm"] == arm]
        stop = [r for r in rows if r["finish_reason"] == "stop"]
        out["arms"][arm] = {
            "n": len(rows),
            "trace_present": sum(1 for r in rows if r["trace_present"]),
            "trace_present_fraction": round(sum(1 for r in rows if r["trace_present"]) / len(rows), 4)
            if rows else None,
            "median_trace_chars": _median([r["trace_chars"] for r in rows if r["trace_present"]]),
            "max_trace_chars": max([r["trace_chars"] for r in rows], default=0),
            "median_completion_tokens": _median([r["completion_tokens"] or 0 for r in rows]),
            "censored_at_cap": sum(1 for r in rows if r["delivery_state"] == "censored_at_cap"),
            "delivered_correct": sum(1 for r in rows if r["delivery_state"] == "delivered_correct"),
            "delivered_wrong": sum(1 for r in rows if r["delivery_state"] == "delivered_wrong"),
            "non_answer": sum(1 for r in rows if r["delivery_state"] == "non_answer"),
            "think_closed": sum(1 for r in rows if r["think_closed"]),
        }

    def traces(arm):
        return [r for r in records if r["arm"] == arm and r["trace_present"]]

    base_traced, base_n = len(traces("baseline")), len([r for r in records if r["arm"] == "baseline"])
    sup_traced = len(traces("suppression"))
    base_frac = round(base_traced / base_n, 4) if base_n else None
    sup_frac = out["arms"]["suppression"]["trace_present_fraction"]
    fewer = sup_traced < base_traced
    below = bool(base_frac is not None and sup_frac is not None and sup_frac < base_frac)
    # G0: the census rows (baseline, one item per census level) locate the wall.
    census_rows = [r for r in records if r["arm"] == "baseline" and r["level"] in CENSUS_LEVELS]
    by_level = {}
    for lvl in CENSUS_LEVELS:
        rows = [r for r in census_rows if r["level"] == lvl]
        by_level[lvl] = {
            "states": sorted({r["delivery_state"] for r in rows}) if rows else [],
            "n": len(rows),
        }
    wall_level = next((lvl for lvl in CENSUS_LEVELS
                       if by_level[lvl]["states"] and "delivered_correct" not in by_level[lvl]["states"]),
                      None)
    top_of_depth = not any(r["delivery_state"] != "delivered_correct" for r in census_rows)
    out["g0_census"] = {
        "levels": by_level,
        "wall_level": wall_level,
        "top_of_depth": top_of_depth,
        "pass": bool(wall_level is not None or top_of_depth),
        "reading": "wall_at_" + str(wall_level) if wall_level is not None
                   else "top_of_depth_invariance",
    }

    # G5 material: eligible items are those whose baseline record is not delivered_correct.
    baseline_state = {}
    for r in records:
        if r["arm"] == "baseline":
            baseline_state[r["item_key"]] = r["delivery_state"]
    eligible = [k for k, s in baseline_state.items()
                if s != "delivered_correct" and k.startswith(f"L{PANEL_LEVEL}")]
    rescued = [r["item_key"] for r in records
               if r["arm"] == "suppression" and r["delivery_state"] == "delivered_correct"
               and r["item_key"] in set(eligible)]

    med = lambda arm, field: _median([r[field] for r in records
                                      if r["arm"] == arm and r.get(field) is not None])
    posthoc_med, baseline_med = med("posthoc", "completion_tokens"), med("baseline", "completion_tokens")

    out["criteria"] = {
        "G0_wall_identified": out["g0_census"],
        "G1_trace_channel_exposed": {
            "channels": sorted({r["trace_source"] for r in records if r["trace_present"]}),
            "any_trace": any(r["trace_present"] for r in records),
            "pass": any(r["trace_present"] for r in records),
        },
        "G2_ban_reduces_trace": {
            "baseline_traced": base_traced, "baseline_n": base_n,
            "baseline_fraction": base_frac,
            "suppression_traced": sup_traced, "suppression_fraction": sup_frac,
            "strictly_fewer": fewer,
            "partial_pass": bool(fewer and below),
            "full_pass": bool(fewer and below and sup_frac is not None
                              and sup_frac <= TRACE_PRESENT_STRONG),
        },
        "G3_negated_ban_backfires": {
            "baseline_traced": len(traces("baseline")),
            "ironic_traced": len(traces("ironic")),
            "margin": len(traces("ironic")) - len(traces("baseline")),
            "threshold": IRONIC_BACKFIRE_MARGIN,
            "pass": len(traces("ironic")) - len(traces("baseline")) >= IRONIC_BACKFIRE_MARGIN,
        },
        "G4_verdict_invariant_to_the_ban": _g4(records),
        "G5_ban_rescues_at_the_wall": {
            "n_eligible": len(eligible),
            "eligible_items": sorted(eligible),
            "rescued_items": sorted(rescued),
            "n_rescued": len(rescued),
            "minimum_eligible": ELIGIBLE_MIN,
            "per_arm_censoring": {arm: out["arms"][arm]["censored_at_cap"] for arm in ARMS},
            "outcome": ("rescued" if (len(rescued) >= 1 and len(eligible) >= ELIGIBLE_MIN)
                        else ("inconclusive_budget" if len(eligible) < ELIGIBLE_MIN
                              else "not_rescued")),
            "pass": bool(len(rescued) >= 1 and len(eligible) >= ELIGIBLE_MIN),
        },
        "G6_permission_lengthens": {
            "posthoc_median_completion_tokens": posthoc_med,
            "baseline_median_completion_tokens": baseline_med,
            "ratio": round(posthoc_med / baseline_med, 3)
            if (posthoc_med and baseline_med) else None,
            "pass": bool(posthoc_med is not None and baseline_med is not None
                         and posthoc_med > baseline_med),
        },
    }
    out["self_stop_census"] = {
        arm: {"records": sum(1 for r in records if r["arm"] == arm),
              "marker": sum(1 for r in records
                            if r["arm"] == arm and r.get("self_stop_marker")),
              # The build's self-stop signature in the archived firings on this id
              # string: completions stopping at exactly the 1556 to 1558 token band
              # with the stop-terminated answer after. completion_tokens is the
              # uncapped readout, so the band count is auditable; the text marker is
              # only observable inside the recorded 1600-char window.
              "stop_band_1556_1558": sum(1 for r in records
                                         if r["arm"] == arm
                                         and 1556 <= (r.get("completion_tokens") or 0) <= 1558)}
        for arm in ARMS
    }
    out["health"] = {
        "id": "H1",
        "records_with_finish_reason": sum(1 for r in records if r.get("finish_reason")),
        "records_with_token_count": sum(1 for r in records if r.get("completion_tokens") is not None),
        "transport_errors": sum(1 for r in records if r.get("transport_error")),
        "pass": all(r.get("finish_reason") for r in records) and not any(
            r.get("transport_error") for r in records),
    }
    out["census"] = {
        "field_names": sorted({f for r in records for f in r.get("message_fields", [])}),
        "trace_source_counts": {src: sum(1 for r in records if r["trace_source"] == src)
                                for src in sorted({r["trace_source"] for r in records})},
    }
    return out


def _g4(records: list) -> dict:
    by = {}
    for r in records:
        if r["delivery_state"] in ("delivered_correct", "delivered_wrong"):
            by.setdefault(r["item_key"], {})[r["arm"]] = r["declared"]
    pairs = [k for k, v in by.items() if "baseline" in v and "suppression" in v]
    same = [k for k in pairs if by[k]["baseline"] == by[k]["suppression"]]
    golds = {r["item_key"]: r["gold"] for r in records}
    both_match_gold = [k for k in same
                       if by[k]["baseline"] == golds[k] and by[k]["suppression"] == golds[k]]
    share = round(len(same) / len(pairs), 4) if pairs else None
    return {
        "comparable_items": len(pairs),
        "invariant": len(same),
        "invariant_share": share,
        "invariant_and_correct": len(both_match_gold),
        "threshold": VERDICT_INVARIANCE_PASS,
        "pass": bool(pairs) and share is not None and share >= VERDICT_INVARIANCE_PASS
        and len(both_match_gold) == len(pairs),
    }


def _median(vals):
    vals = sorted(vals)
    if not vals:
        return None
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else round((vals[mid - 1] + vals[mid]) / 2, 1)


# ------------------------------------------------------------------ issue #137 guard

def check_readme(readme_text: str, gate: dict, records: list) -> dict:
    defined = ({str(c["id"]) for c in gate["criteria"]} | {gate["health"]["id"]}
               | {str(a).split("_")[0].upper() for a in ARMS})
    problems = []
    named = set(ROW_ID_RE.findall(readme_text))
    undefined = sorted(named - defined)
    if undefined:
        problems.append({"kind": "row_id_not_in_gate", "ids": undefined})
    pinned = PINNED_BLOB_RE.search(readme_text)
    blob = gate_blob(gate)
    if not pinned or pinned.group(1) != blob:
        problems.append({"kind": "readme_blob_stale_or_missing",
                         "quoted": pinned.group(1) if pinned else None, "expected": blob})
    stale = [r.get("label") for r in records if r.get("gate") != blob]
    if stale:
        problems.append({"kind": "raw_record_stale_blob", "labels": stale})
    gate_labels = {l for arm in gate["arms"].values() for l in arm["labels"]}
    raw_labels = {r.get("label") for r in records}
    if not raw_labels <= gate_labels:
        problems.append({"kind": "raw_label_not_in_gate",
                         "labels": sorted(raw_labels - gate_labels)})
    return {"ok": not problems, "problems": problems}


# ------------------------------------------------------------------ commands

def read_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def cmd_freeze():
    if model_digest() is None:
        raise SystemExit("NIGHTLY_MODEL_ID is unset: refusing to freeze the gate "
                         "(round-78 rule - an empty id pins to a fixed digest and the "
                         "guard's refusal message would be wrong)")
    plan = build_plan()
    if len(plan) > PROMPT_CAP:
        raise SystemExit(f"plan of {len(plan)} exceeds the {PROMPT_CAP}-prompt round cap")
    spec = gate_spec(plan)
    with open(GATE_FILE, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"gate frozen: {spec['blob']} planned={len(plan)}")


def cmd_measure():
    """Pre-dispatch census (standing round-61 rule). The census rows are the plan's own
    baseline rows at the census levels (wall location AND the rate call-pair), so they
    are written to raw.jsonl with the frozen gate blob and the dispatch step skips them:
    one prompt, one record."""
    plan = build_plan()
    spec_g = json.load(open(GATE_FILE, encoding="utf-8"))
    blob = gate_blob(spec_g)
    done = {r["label"] for r in read_jsonl(RAW_FILE)}
    census_rows = [p for p in plan if p["arm"] == "baseline" and p["level"] in CENSUS_LEVELS]
    census = []
    for spec in census_rows:
        if spec["label"] in done:
            rec = next(r for r in read_jsonl(RAW_FILE) if r["label"] == spec["label"])
            census.append({k: rec[k] for k in
                          ("label", "level", "arm", "completion_tokens", "prompt_tokens",
                           "wall_s", "tok_per_s", "finish_reason", "trace_present",
                           "trace_chars", "delivery_state", "self_stop_marker")})
            print(json.dumps(census[-1], sort_keys=True))
            continue
        res = chat(spec["prompt"], MAX_TOKENS)
        rec = measure_record(spec, res)
        rec["gate"] = blob
        with open(RAW_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        census.append({k: rec[k] for k in
                      ("label", "level", "arm", "completion_tokens", "prompt_tokens", "wall_s",
                       "tok_per_s", "finish_reason", "trace_present", "trace_chars",
                       "delivery_state", "self_stop_marker")})
        print(json.dumps(census[-1], sort_keys=True))
    rates = [c["tok_per_s"] for c in census if c["tok_per_s"]]
    mean_rate = round(sum(rates) / len(rates), 3) if rates else None
    est_min = round(len(plan) * MAX_TOKENS / mean_rate / 60, 1) if mean_rate else None
    out = {"census": census, "mean_tok_per_s": mean_rate,
           "planned_dispatches": len(plan), "max_tokens": MAX_TOKENS,
           "worst_case_minutes_if_every_item_hits_the_cap": est_min,
           "decision": "dispatch" if mean_rate and est_min and est_min <= 45 else "abort"}
    with open(MEASURE_FILE, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(json.dumps({k: out[k] for k in
                      ("mean_tok_per_s", "planned_dispatches",
                       "worst_case_minutes_if_every_item_hits_the_cap", "decision")},
                     sort_keys=True))


def cmd_dispatch():
    plan = build_plan()
    spec = json.load(open(GATE_FILE, encoding="utf-8"))
    blob = gate_blob(spec)
    done = {r["label"] for r in read_jsonl(RAW_FILE)}
    if len(done) >= len(plan):
        print(f"nothing to do: {len(done)}/{len(plan)} records already on disk")
        return
    for i, item in enumerate(p for p in plan if p["label"] not in done):
        try:
            res = chat(item["prompt"], MAX_TOKENS)
            rec = measure_record(item, res)
        except Exception as exc:  # a transport failure is a record, not a silent gap
            rec = dict(label=item["label"], level=item["level"], item_index=item["item_index"],
                       arm=item["arm"], item_key=item["item_key"], gold=item["gold"],
                       transport_error=sanitize(f"{type(exc).__name__}: {exc}", 200),
                       finish_reason=None, completion_tokens=None, prompt_tokens=None,
                       wall_s=None, tok_per_s=None, trace_present=False, trace_chars=0,
                       trace="", think_open=0, think_close=0, think_closed=False,
                       visible="", visible_chars=0, declared=None, declared_present=False,
                       delivery_state="not_delivered", message_fields=[], trace_source="none",
                       prompt_chars=len(item["prompt"]), prompt=sanitize(item["prompt"]))
        rec["gate"] = blob
        with open(RAW_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        print(f"[{len(done) + i + 1}/{len(plan)}] {rec['label']} "
              f"finish={rec['finish_reason']} ct={rec['completion_tokens']} "
              f"trace={rec['trace_present']} state={rec['delivery_state']}", flush=True)


def cmd_summarize():
    spec = json.load(open(GATE_FILE, encoding="utf-8"))
    records = read_jsonl(RAW_FILE)
    summary = score(records, spec)
    with open(SUMMARY_FILE, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


def cmd_check_readme():
    gate = json.load(open(GATE_FILE, encoding="utf-8"))
    text = open(os.path.join(HERE, "README.md"), encoding="utf-8").read()
    report = check_readme(text, gate, read_jsonl(RAW_FILE))
    print(json.dumps(report, sort_keys=True))
    if not report["ok"]:
        raise SystemExit(1)


# ------------------------------------------------------------------ selftest

def selftest() -> int:
    fails = []

    def check(name, cond):
        if not cond:
            fails.append(name)

    # Trace splitting: the inline case, the channel case, and the unclosed case.
    T_OPEN, T_CLOSE = _THINK_OPEN, _THINK_CLOSE
    closed = split_trace({"role": "assistant",
                          "content": T_OPEN + "a->b->c so yes" + T_CLOSE + "\n\nThe answer is yes."})
    check("inline_tag_seen", closed["think_open"] == 1)
    check("inline_visible_is_tail", closed["visible"] == "The answer is yes.")
    check("inline_closed", closed["think_closed"] and closed["trace_source"] == "inline_think")
    check("inline_trace_holds_the_traversal", "a->b->c" in closed["trace"])

    unclosed = split_trace({"role": "assistant",
                            "content": T_OPEN + "traversing: a->b, b->c, c->d " * 4})
    check("unclosed_flagged", unclosed["think_closed"] is False)
    check("unclosed_tail_is_the_traversal", unclosed["visible"].startswith("traversing"))
    # A never-closed traversal cannot deliver even with a stray yes inside it: delivery gates
    # on termination, not on the presence of a token.
    check("unclosed_truncation_cannot_deliver",
          delivery_state({"finish_reason": "length", "declared_present": True,
                          "declared": "yes", "gold": "yes"}) == "censored_at_cap")

    channel = split_trace({"role": "assistant", "content": "no", "reasoning_content": "long walk"})
    check("channel_wins", channel["trace_source"] == "reasoning_content"
          and channel["trace"] == "long walk" and channel["visible"] == "no")

    # Negative control: a reply with no trace anywhere reads as no trace, not as empty trace.
    plain = split_trace({"role": "assistant", "content": "yes"})
    check("plain_no_trace", plain["trace_source"] == "none" and plain["visible"] == "yes")
    check("plain_tag_state_is_unknown_not_closed",
          plain["think_open"] == 0 and plain["think_closed"] is None)

    # Verdict extraction: last mention wins, and an enumeration is not a verdict.
    check("last_wins", declared_verdict("maybe no, actually yes")[0] == "yes")
    check("first_not_used", declared_verdict("yes then no")[0] == "no")
    check("no_verdict", declared_verdict("I cannot say")[1] is False)
    check("empty_not_delivered", declared_verdict("")[1] is False)
    check("word_boundary", declared_verdict("nothing here")[1] is False)

    # Delivery census: a truncation is never scored as wrong (issue #145).
    base_rec = {"finish_reason": "stop", "declared_present": True, "declared": "yes", "gold": "yes"}
    check("delivered_correct", delivery_state(base_rec) == "delivered_correct")
    check("delivered_wrong", delivery_state({**base_rec, "declared": "no"}) == "delivered_wrong")
    check("censored_not_wrong",
          delivery_state({**base_rec, "finish_reason": "length"}) == "censored_at_cap")
    check("non_answer",
          delivery_state({**base_rec, "declared_present": False}) == "non_answer")

    # Sanitizer: URL, address, home path and quantization-tagged label all go.
    # Serving-id guard fixture: built by concatenation so this source carries no instance, and
    # deliberately generic rather than echoing any model this program serves.
    dirty = ("see https://example.invalid/x at 198.51.100.7:8080 under "
             + "/home" + "/someone/x and the acme-" + "widget" + "-iq3_xxs build")
    clean = sanitize(dirty)
    check("url_scrubbed", "http" not in clean)
    check("addr_scrubbed", "198.51.100.7" not in clean)
    check("path_scrubbed", "someone" not in clean)
    check("serving_label_scrubbed", "widget" not in clean)
    check("sanitizer_keeps_task_text", sanitize("zelt precedes schont") == "zelt precedes schont")
    # Negative control for the sanitizer: ordinary prose must survive untouched.
    check("sanitizer_no_op_on_plain",
          sanitize("The answer is yes.") == "The answer is yes.")

    # Gate blob: stable under key order, moves when a threshold moves.
    plan = build_plan()
    spec = gate_spec(plan)
    shuffled = json.loads(json.dumps({k: spec[k] for k in reversed(list(spec))}))
    check("blob_stable", gate_blob(spec) == gate_blob(shuffled))
    moved = dict(spec)
    moved["max_tokens"] = MAX_TOKENS + 1
    check("blob_moves_with_threshold", gate_blob(moved) != spec["blob"])
    check("blob_matches_file_field", gate_blob({k: v for k, v in spec.items()}) == spec["blob"])

    # Plan shape and the round cap.
    check("plan_is_22", len(plan) == 22)
    check("plan_within_cap", len(plan) <= PROMPT_CAP)
    check("arms_balanced_at_panel", all(
        len([p for p in plan if p["arm"] == a and p["level"] == PANEL_LEVEL]) == ITEMS_PER_LEVEL
        for a in ARMS))
    check("non_panel_census_rows_are_baseline", all(
        p["arm"] == "baseline" for p in plan
        if p["level"] in CENSUS_LEVELS and p["level"] != PANEL_LEVEL))
    check("levels_present", {p["level"] for p in plan} == set(CENSUS_LEVELS))
    check("golds_are_yes_no", all(p["gold"] in ("yes", "no") for p in plan))

    # The registered load-ceiling selection: deterministic, bounded, and the census
    # panel-level item is the panel's first item (so the census row doubles as a panel row).
    sel1, _ = select_items(PANEL_LEVEL, ITEMS_PER_LEVEL)
    sel2, _ = select_items(PANEL_LEVEL, ITEMS_PER_LEVEL)
    check("selection_deterministic", [i["seed"] for i in sel1] == [i["seed"] for i in sel2])
    check("load_ceiling_holds", all(
        len(i["facts"]) <= MAX_CHAINS * PANEL_LEVEL for i in sel1))
    c64, _ = select_items(PANEL_LEVEL, 1)
    check("census_item_is_panel_item", c64[0]["seed"] == sel1[0]["seed"])
    sel32, _ = select_items(32, 1)
    check("census_levels_bounded", all(
        len(i["facts"]) <= MAX_CHAINS * 32 for i in sel32))

    # The baseline arm is byte-identical to the frozen judge template, and only the baseline.
    for p in plan:
        added = len(p["prompt"]) - p["base_chars"]
        check(f"baseline_parity_{p['label']}",
              (added == 0) == (p["arm"] == "baseline"))
        check(f"surface_carried_{p['label']}", "precedes" in p["prompt"])

    # Scoring on synthetic records, including the planted-slip controls.
    def synth(arm, item_key, gold, traced, declared, finish="stop", level=4, index=0):
        r = {"label": f"{item_key}_{arm}", "level": level, "item_index": index, "arm": arm,
             "item_key": item_key, "gold": gold, "trace_present": traced, "trace_chars": 300
             if traced else 0, "completion_tokens": 400, "finish_reason": finish,
             "declared": declared, "declared_present": declared is not None,
             "delivery_state": delivery_state({"finish_reason": finish, "declared_present":
                                               declared is not None, "declared": declared,
                                               "gold": gold}),
             "trace_source": "inline_think" if traced else "none", "message_fields": ["content"],
             "think_closed": True}
        return r

    good = []
    for i in range(8):
        key = f"L4_i{i}"
        g = "yes" if i % 2 else "no"
        for arm in ARMS:
            traced = not (arm == "suppression" and i >= 5)
            good.append(synth(arm, key, g, traced, g, index=i))
    sc = score(good, spec)
    check("G1_passes_when_exposed", sc["criteria"]["G1_trace_channel_exposed"]["pass"])
    check("G2_partial_passes_on_suppression",
          sc["criteria"]["G2_ban_reduces_trace"]["partial_pass"])
    check("G2_full_tier_is_the_stronger_one",
          not sc["criteria"]["G2_ban_reduces_trace"]["full_pass"])
    check("G3_does_not_fire_when_equal", not sc["criteria"]["G3_negated_ban_backfires"]["pass"])
    check("G4_invariance_holds", sc["criteria"]["G4_verdict_invariant_to_the_ban"]["pass"])

    # Negative control: the same records, but the ban flips the verdict on half the items.
    flipped = []
    for r in good:
        if r["arm"] == "suppression" and r["item_index"] % 2 == 0:
            alt = dict(r, declared="no" if r["gold"] == "yes" else "yes")
            alt["delivery_state"] = delivery_state(alt)
            flipped.append(alt)
        else:
            flipped.append(r)
    sc2 = score(flipped, spec)
    check("G4_catches_verdict_drift", not sc2["criteria"]["G4_verdict_invariant_to_the_ban"]["pass"])

    # Negative control: a build that traces everywhere must not read as a successful ban.
    noisy = [dict(r, trace_present=True) for r in good]
    sc3 = score(noisy, spec)
    check("G2_fails_when_ban_does_nothing",
          not sc3["criteria"]["G2_ban_reduces_trace"]["partial_pass"])

    # Negative control: zero traces means no channel, so G1 must refuse the trace claims.
    dark = [dict(r, trace_present=False, trace_source="none") for r in good]
    sc4 = score(dark, spec)
    check("G1_refuses_without_channel", not sc4["criteria"]["G1_trace_channel_exposed"]["pass"])

    # Tier control: near-total suppression must clear the full tier, and clearing full implies
    # clearing partial. A gate whose full tier were the looser one would pass this by accident.
    strong = [dict(r, trace_present=(r["arm"] != "suppression" or r["item_index"] == 0))
              for r in good]
    sc5 = score(strong, spec)
    check("G2_full_fires_on_near_total_ban", sc5["criteria"]["G2_ban_reduces_trace"]["full_pass"])
    check("G2_full_implies_partial", sc5["criteria"]["G2_ban_reduces_trace"]["partial_pass"])

    # G0 census read: a non-correct census level locates the wall; all-correct is
    # top-of-depth.
    census_all_good = [synth("baseline", f"L{lvl}_i100", "yes", True, "yes", level=lvl)
                       for lvl in CENSUS_LEVELS]
    sc_g0a = score(census_all_good, spec)
    check("G0_top_of_depth_when_all_correct",
          sc_g0a["g0_census"]["top_of_depth"] and sc_g0a["g0_census"]["wall_level"] is None)
    census_with_wall = [dict(r, finish_reason="length", delivery_state="censored_at_cap")
                       if lvl == 32 else r
                       for lvl, r in zip(CENSUS_LEVELS, census_all_good)]
    sc_g0b = score(census_with_wall, spec)
    check("G0_wall_at_first_bad_level",
          sc_g0b["g0_census"]["wall_level"] == 32
          and sc_g0b["g0_census"]["reading"] == "wall_at_32")

    # G5 rescue at the wall, with the #145 denominator discipline.
    def wallrec(arm, ikey, state):
        declared = "yes" if state in ("delivered_correct", "delivered_wrong") else None
        return {"label": f"{ikey}_{arm}", "level": PANEL_LEVEL, "item_index": 0, "arm": arm,
                "item_key": ikey, "gold": "yes", "trace_present": True, "trace_chars": 300,
                "completion_tokens": 400, "finish_reason": "stop", "declared": declared,
                "declared_present": declared is not None, "delivery_state": state,
                "trace_source": "inline_think", "message_fields": ["content"],
                "think_closed": True}

    rescued_set = [wallrec("baseline", "L64_i0", "censored_at_cap"),
                   wallrec("baseline", "L64_i1", "delivered_wrong"),
                   wallrec("baseline", "L64_i2", "non_answer"),
                   wallrec("suppression", "L64_i0", "delivered_correct"),
                   wallrec("suppression", "L64_i1", "censored_at_cap"),
                   wallrec("suppression", "L64_i2", "delivered_correct")]
    sc_g5a = score(rescued_set, spec)
    g5a = sc_g5a["criteria"]["G5_ban_rescues_at_the_wall"]
    check("G5_rescued_when_eligible_and_saved",
          g5a["outcome"] == "rescued" and g5a["pass"] and g5a["n_eligible"] == 3
          and g5a["n_rescued"] == 2)
    thin_set = [wallrec("baseline", "L64_i0", "censored_at_cap"),
                wallrec("suppression", "L64_i0", "censored_at_cap")]
    g5b = score(thin_set, spec)["criteria"]["G5_ban_rescues_at_the_wall"]
    check("G5_inconclusive_below_minimum",
          g5b["outcome"] == "inconclusive_budget" and not g5b["pass"])
    no_save = [wallrec("baseline", "L64_i0", "censored_at_cap"),
               wallrec("baseline", "L64_i1", "delivered_wrong"),
               wallrec("baseline", "L64_i2", "non_answer"),
               wallrec("suppression", "L64_i0", "censored_at_cap"),
               wallrec("suppression", "L64_i1", "delivered_wrong"),
               wallrec("suppression", "L64_i2", "censored_at_cap")]
    g5c = score(no_save, spec)["criteria"]["G5_ban_rescues_at_the_wall"]
    check("G5_not_rescued_when_nothing_saved",
          g5c["outcome"] == "not_rescued" and not g5c["pass"])

    # G6: the permission lengthens; equal medians must refuse.
    len_good = [dict(r, completion_tokens=(800 if r["arm"] == "posthoc" else 400))
                for r in good]
    check("G6_passes_when_posthoc_longer",
          score(len_good, spec)["criteria"]["G6_permission_lengthens"]["pass"])
    len_eq = [dict(r, completion_tokens=400) for r in good]
    check("G6_refuses_equal_medians",
          not score(len_eq, spec)["criteria"]["G6_permission_lengthens"]["pass"])

    # The self-stop marker census: present in the marker text, absent otherwise.
    spec_min = {"label": "L64_i0_baseline", "level": PANEL_LEVEL, "item_index": 0,
                "arm": "baseline", "item_key": "L64_i0", "prompt": "p", "base_chars": 1,
                "gold": "yes"}
    res_marker = {"message": {"role": "assistant", "content": "yes",
                              "reasoning_content": "walk the chain. "
                                                    "I have thought about this long enough; "
                                                    "time to give my answer."},
                  "finish_reason": "stop", "completion_tokens": 1556, "prompt_tokens": 100,
                  "wall_s": 1.0, "tok_per_s": 1556.0}
    check("self_stop_marker_seen",
          measure_record(spec_min, res_marker)["self_stop_marker"] is True)
    res_plain = {"message": {"role": "assistant", "content": "yes",
                             "reasoning_content": "a->b, b->c, so yes"},
                 "finish_reason": "stop", "completion_tokens": 90, "prompt_tokens": 100,
                 "wall_s": 1.0, "tok_per_s": 90.0}
    check("self_stop_marker_absent",
          measure_record(spec_min, res_plain)["self_stop_marker"] is False)

    # The stop-band readout counts the uncapped completion_tokens in the archived
    # 1556 to 1558 band; nothing else may count.
    band_set = [dict(r, completion_tokens=1556) for r in good if r["arm"] == "baseline"]
    sc_band = score(band_set, spec)
    n_band = sc_band["self_stop_census"]["baseline"]["stop_band_1556_1558"]
    check("stop_band_counts_in_band", n_band == len(band_set))
    out_band = [dict(r, completion_tokens=1555) for r in band_set]
    check("stop_band_excludes_adjacent",
          score(out_band, spec)["self_stop_census"]["baseline"]["stop_band_1556_1558"] == 0)

    # Readme guard: an invented row id is caught, a real one is not.
    ok_readme = "Rows G0 G1 G2 G3 G4 G5 G6 and H1. gate blob `" + gate_blob(spec) + "`"
    check("readme_ok_when_valid", check_readme(ok_readme, spec, [])["ok"])
    check("readme_catches_invented_row",
          not check_readme("Rows G0 G7. gate blob `" + gate_blob(spec) + "`", spec, [])["ok"])
    check("readme_catches_stale_blob",
          not check_readme("Rows G0. gate blob `" + "0" * 64 + "`", spec, [])["ok"])

    if fails:
        print(f"SELFTEST FAILED: {len(fails)}")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("selftest ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--freeze-gate", action="store_true")
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--dispatch", action="store_true")
    ap.add_argument("--summarize", action="store_true")
    ap.add_argument("--check-readme", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.freeze_gate:
        cmd_freeze()
        return 0
    if args.measure:
        cmd_measure()
        return 0
    if args.dispatch:
        cmd_dispatch()
        return 0
    if args.summarize:
        cmd_summarize()
        return 0
    if args.check_readme:
        cmd_check_readme()
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())

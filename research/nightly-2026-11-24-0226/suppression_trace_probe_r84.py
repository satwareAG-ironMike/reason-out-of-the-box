#!/usr/bin/env python3
"""Round 84 (2026-11-24 02:26, nightly lane, issue #65): the process-suppression probe.

Question. On a build that emits an inline reasoning trace under the frozen judge's neutral
one-word contract, what is that trace? Two candidate readings: the trace is the computation
(the verdict depends on it), or the trace is an output-format attractor the build cannot switch
off (the verdict is computed without it and the trace rides along). The two readings make
opposite predictions about what happens when the instruction forbids reasoning.

Method. One task surface, one gold, four instruction arms that differ only in what they say
about reasoning (the item text is byte-identical across arms):

  baseline   the frozen judge template verbatim (evaluation/frozen/verify.py build_prompt)
  suppression  + an imperative: produce no reasoning at all
  ironic     + the same ban in negated form ("do not think about the chain"), the
              white-bear / ironic-process framing from process-suppression research
  posthoc    + an explicit request to reason, after the one-word answer

Predictions frozen before dispatch (gate.json): does the ban reduce the trace (G2), does the
negated ban backfire (G3), and is the verdict invariant to an instruction that changes the
trace (G4). Verdict faithfulness is read answer-level only, never from the trace text (issue
#94); the trace is reported as a measured length, not scored as evidence.

Family: ladders k-hop reachability, frozen grid levels 4 and 8, fresh seed base 20261124
(the judge's run-date policy). 8 items, 4 arms = 32 dispatched prompts, max_tokens 1024,
temperature 0.0, one dispatch at a time. Under the 40-prompt round cap and inside the
2026-W48 weekly cap (research/AGENTS.md, issue #195).

Evidence label: Executed, exploratory. n = 8 items per arm on one build of an
exploratory-only model class; no confirmatory cell (issue #196 blocks that track).

Endpoint config comes only from NIGHTLY_BASE_URL / NIGHTLY_MODEL_ID / NIGHTLY_API_KEY and is
never written to disk; every model-facing string is sanitized before it is recorded
(public-only rule).

Usage:
    python3 suppression_trace_probe_r84.py --selftest     # arithmetic + negative controls, no I/O
    python3 suppression_trace_probe_r84.py --freeze-gate  # write gate.json, before any dispatch
    python3 suppression_trace_probe_r84.py --measure      # pre-dispatch rate census, writes measure.json
    python3 suppression_trace_probe_r84.py --dispatch     # run the plan, append raw.jsonl
    python3 suppression_trace_probe_r84.py --summarize    # score raw.jsonl, write summary.json
    python3 suppression_trace_probe_r84.py --check-readme # issue #137 row-and-blob guard
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
MAX_TOKENS = 1024
SEED_BASE = 20261124
LEVELS = (4, 8)
ITEMS_PER_LEVEL = 4
PROMPT_CAP = 40  # research/AGENTS.md per-round cap

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


def build_plan() -> list[dict]:
    plan = []
    for level in LEVELS:
        items = frozen().generate("ladders", level, ITEMS_PER_LEVEL, SEED_BASE)
        for idx, item in enumerate(items):
            for arm in ARMS:
                base = base_prompt(item)
                prompt = base + ARM_SUFFIX[arm]
                plan.append({
                    "label": f"L{level}_i{idx}_{arm}",
                    "level": level,
                    "item_index": idx,
                    "arm": arm,
                    "item_key": f"L{level}_i{idx}",
                    "prompt": prompt,
                    "base_chars": len(base),
                    "gold": gold(item),
                })
    return plan


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
        "prompt_chars": len(spec["prompt"]),
        "instruction_added_chars": len(spec["prompt"]) - spec["base_chars"],
        "prompt": sanitize(spec["prompt"], limit=2000),
        "message_fields": parts["message_fields"],
        "trace_source": parts["trace_source"],
        "trace_present": bool(trace.strip()),
        "trace_chars": len(trace),
        "trace": trace,
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

def gate_spec(planned: list) -> dict:
    arms = {}
    for arm in ARMS:
        rows = [p for p in planned if p["arm"] == arm]
        arms[arm] = {"n": len(rows), "labels": [r["label"] for r in rows]}
    spec = {
        "round": 84,
        "firing": "2026-11-24T02:26+01:00",
        "issue": 65,
        "question": "On a build that emits an inline reasoning trace under the frozen one-word "
                    "contract, does an instruction that forbids reasoning change the trace, and "
                    "does the verdict move when the trace does?",
        "family": "ladders",
        "levels": list(LEVELS),
        "seed_base": SEED_BASE,
        "arms": arms,
        "planned_dispatches": len(planned),
        "prompt_cap": PROMPT_CAP,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.0,
        "criteria": [
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
    out["criteria"] = {
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
    plan = build_plan()
    if len(plan) > PROMPT_CAP:
        raise SystemExit(f"plan of {len(plan)} exceeds the {PROMPT_CAP}-prompt round cap")
    spec = gate_spec(plan)
    with open(GATE_FILE, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"gate frozen: {spec['blob']} planned={len(plan)}")


def cmd_measure():
    """Pre-dispatch rate census (standing round-61 rule). The two census calls are real plan
    rows, so they are written to raw.jsonl with the frozen gate blob and the dispatch step
    skips them: one prompt, one record."""
    plan = build_plan()
    blob = gate_blob(json.load(open(GATE_FILE, encoding="utf-8")))
    done = {r["label"] for r in read_jsonl(RAW_FILE)}
    census = []
    for label in (plan[0]["label"], plan[-1]["label"]):
        spec = next(p for p in plan if p["label"] == label)
        res = chat(spec["prompt"], MAX_TOKENS)
        rec = measure_record(spec, res)
        rec["gate"] = blob
        if spec["label"] not in done:
            with open(RAW_FILE, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
        census.append({k: rec[k] for k in
                       ("label", "level", "arm", "completion_tokens", "prompt_tokens", "wall_s",
                        "tok_per_s", "finish_reason", "trace_present", "trace_chars",
                        "delivery_state")})
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
    check("plan_is_32", len(plan) == 32)
    check("plan_within_cap", len(plan) <= PROMPT_CAP)
    check("arms_balanced", all(
        len([p for p in plan if p["arm"] == a]) == 8 for a in ARMS))
    check("levels_present", {p["level"] for p in plan} == set(LEVELS))
    check("golds_are_yes_no", all(p["gold"] in ("yes", "no") for p in plan))

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

    # Readme guard: an invented row id is caught, a real one is not.
    ok_readme = "Rows G1 G2 G3 G4 and H1. gate blob `" + gate_blob(spec) + "`"
    check("readme_ok_when_valid", check_readme(ok_readme, spec, [])["ok"])
    check("readme_catches_invented_row",
          not check_readme("Rows G1 G7. gate blob `" + gate_blob(spec) + "`", spec, [])["ok"])
    check("readme_catches_stale_blob",
          not check_readme("Rows G1. gate blob `" + "0" * 64 + "`", spec, [])["ok"])

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

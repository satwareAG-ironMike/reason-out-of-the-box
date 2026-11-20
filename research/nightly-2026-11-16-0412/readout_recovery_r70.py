#!/usr/bin/env python3
"""Round 70 (2026-11-16 04:12): is a lost terminal name accessible for report?

Question. Round 69 (`research/nightly-2026-11-16-0219/`, PR never opened; the firing timed out
under issue #150) found that on deep rungs of the name-walk ladder the record's non-report channel
names every node of the asked path, the asked terminal included, while the answer field carries a
wrong name, a refusal, or a token that is not an entity of the item. Its own words: "the walk is
not where the loss happens: the loss is between a name the record already contains and the one
word the answer field carries." That firing measured the gap; it did not ask whether the lost name
is ACCESSIBLE, i.e. whether a change in the report conditions makes it reportable.

This round asks exactly that, with a paired context manipulation and an answer-channel verdict.
For every deep cell the turn-1 record is replayed as a two-turn conversation and followed by the
same neutral question ("which single entity name is at step j, or NONE"). The two arms differ in
one bit:

  arm A  the assistant turn carries the turn-1 answer field PLUS the turn-1 non-report channel,
  arm B  the assistant turn carries the turn-1 answer field ONLY.

Both arms are scored against the generator's independent solver, never against trace text, so the
verdict is an answer-level claim (issue #94). Trace text is used as a treatment and as a count
census (issue #105); it is never archived and never scores anything. Round 50 refused a
surfacing row because scoring a trace-derived answer calibrated at 0.5652; the refusal was about
the SCORER reading the trace, not about the model being shown its own prior text, and this
instrument keeps that line.

Registered rows, frozen in gate.json before any prompt:

  V0_trace_exposure   the deployment must hand back a non-report channel at all; without it arm A
                      cannot be built and row R1 is refused rather than trusted (issue #105).
  V1_solver_certified the independent solver agrees with the path walk at j = 0, 1, mid, level and
                      returns None one step past the tail; every item is a load-floor
                      (facts = 2 * level), component-isomorphic two-chain item.
  V2_control_liveness both past-the-tail controls declare NONE at turn 1 (issue #139 shape).
  V3_anchor           the shallow j = 8 anchor cell delivers the correct terminal (liveness).
  R1_readout_recovery PRIMARY. Over the deep cells whose turn-1 answer is not the gold: n_A
                      recoveries in arm A against n_B in arm B. n_lost >= 3 to be evaluable.
                      readout_gated when n_A - n_B >= 2 and n_A >= 2; channel_toxic when
                      n_B - n_A >= 2; no_channel_effect when |n_A - n_B| <= 1; otherwise reported
                      as ambiguous. Discordant pairs are reported with an exact one-sided binomial
                      and no significance claim: n is single digits.
  X2_tail_shortcut    companion to R1 and a downgrade rule: if every arm-A recovery is simply the
                      LAST generator-vocabulary name in the restored notes, the reading is
                      tail_copy, not selection, and R1 is downgraded.
  H1_answer_stability over the deep cells whose turn-1 answer WAS the gold: how often each arm
                      keeps it.
  C1_name_pressure    the two NONE-gold controls under both arms: a name where the links ran out is
                      a manufactured name, and any arm-A false name caps the R1 reading.
  S1_delivery_census  every turn-1 and arm record classified into the issue #145 delivery states.
  W2_wall_shape       every record fitted against the three archived wall laws (the 1,556 to 1,558
                      self-stop band, a reserve of exactly 492, a reserve at or below 19).
  M4_matched_pair     three turn-1 cells are byte-identical to the round-69 endpoint cells; the
                      prompt digests are asserted in --selftest, so "same items, same prompts,
                      different serving build" is machine-checked here.

Contracts: stdlib only; reads NIGHTLY_BASE_URL, NIGHTLY_MODEL_ID, NIGHTLY_API_KEY from the
environment and writes none of them; at most 40 prompts; max_tokens <= 2048; sequential dispatch
one cell at a time (issue #73) so a cell's rate belongs to that cell (issue #141); the sanitizer
redacts host, IP, path and serving-id classes (issue #85) from anything the model answers, and
that behavior is tested in --selftest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_REPO, "generators"))

import ladders  # noqa: E402

SEED_BASE = 20261005          # the round-51 seed base, so the k = 48 item is the archived one
SCAN = 300                    # the round-51 scan width
MAX_TOKENS = 2048             # protocol cap: no requested cap may exceed it
ARM_CAP = 2048                # arms get the same cap: censoring must not be my artifact
CALL_CAP = 40
TIMEOUT_S = 900
DISPATCH_BUDGET_S = 2100
CELL_FLOOR_S = 90
MAX_RETRIES_TOTAL = 3
NONE_GOLD = "NONE"
GATE_SCHEMA = "round70-gate-v1"
CENSUS_CAP = 256
NOTES_LABEL = "[working notes from the previous answer]"

ARCHIVED_K48 = {"seed": 116261051, "yesno_digest16": "068bc6a1fb0620fb"}

# The matched pair: prompt digests frozen by the round-63 gate (PR #143, unmerged) and dispatched
# again by round 69. Three of this round's turn-1 cells use the identical item, depth and template,
# so --selftest can assert that the only variable against those firings is the serving build.
MATCHED_PAIR = {
    "record": "round-63 gate cells (PR #143, unmerged here), re-dispatched by round 69",
    "prompt_sha256": {
        "A48_j48": "baabc3462652878fdbdca1994faa18240e917b5f0fea69fd786d34e56526c4c9",
        "B50_j50": "c15a68eb63cc474457ebe6f8ee806f6e0182d38967bfdbe67726417c272e5362",
        "C64_j64": "c1ef6c20bfd84e2fd30a6eaefa22caf1dfb4663280b0824cac72e89f298eea7e",
    },
}

WALL_LAWS = {
    "L1_self_stop_band": {
        "source": "round 59 (PR #140, unmerged here) and round 69, both on one digest",
        "test": "1556 <= completion_tokens <= 1558 and finish_reason == 'stop'",
    },
    "L2_reserve_492": {
        "source": "round 53 (PR #131, unmerged here)",
        "test": "cap - completion_tokens == 492",
    },
    "L3_cap_bound": {
        "source": "round 54 (PR #133, unmerged here), the 27B-class shape",
        "test": "cap - completion_tokens <= 19",
    },
}

DELIVERY_STATES = ("delivered_correct", "delivered_wrong_on_right_path",
                   "delivered_wrong_off_path", "declared_none_on_name_gold",
                   "delivered_no_item_name", "declared_none", "false_name_on_none_gold",
                   "censored_at_cap", "empty_answer_field")

# ------------------------------------------------------------------ item selection


def series_scan(level: int) -> list:
    out = []
    for i in range(SCAN):
        seed = SEED_BASE + 2_000_000 * level + i
        try:
            out.append(ladders.generate_item(level, seed))
        except RuntimeError:
            continue
    return out


def load_floor(level: int) -> list:
    """Items whose fact count is 2 * level: exactly two chains, the smallest load in the corpus."""
    return [it for it in series_scan(level) if len(it["facts"]) == 2 * level]


def adjacency(item: dict) -> dict:
    adj: dict = {}
    for s, _, t in item["facts"]:
        assert s not in adj, "out-degree above one"
        adj[s] = t
    return adj


def check_item(item: dict) -> None:
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


def path_nodes(item: dict, src: str) -> list:
    adj = adjacency(item)
    nodes = [src]
    while True:
        nxt = adj.get(nodes[-1])
        if nxt is None:
            return nodes
        nodes.append(nxt)


def vocab_of(item: dict) -> set:
    words = set()
    for s, _, t in item["facts"]:
        words.add(s)
        words.add(t)
    return words


def select_items() -> dict:
    anchor = next(it for it in load_floor(48) if it["seed"] == ARCHIVED_K48["seed"])
    items = {"A48": anchor}
    for key, level in (("B50", 50), ("C64", 64)):
        lf = load_floor(level)
        assert lf, f"level {level} produced no load-floor items in the scan"
        items[key] = lf[0]
    for it in items.values():
        check_item(it)
    return items


_ITEMS: dict = {}


def item_for(key: str) -> dict:
    return _ITEMS[key]


# ------------------------------------------------------------------ prompts


def fact_block(item: dict) -> str:
    return "\n".join(f"{s} {r} {t}." for s, r, t in item["facts"])


def render_name(item: dict, src: str, j: int) -> str:
    """Byte-identical to the round-63 and round-69 name template (row M4 depends on it)."""
    return (f"{item['rule']}\nFacts:\n{fact_block(item)}\n\n"
            f"Task: start at {src} and follow the direct links for exactly {j} steps. "
            "Answer with exactly one entity name, or the single word NONE if the links run out "
            f"before {j} steps.")


def render_yesno(item: dict) -> str:
    qs, qrel, qt = item["query"]
    return (f"{item['rule']}\nFacts:\n{fact_block(item)}\n\n"
            f"Question: does {qs} {qrel} {qt}?\n"
            "Answer with exactly one word: yes or no.")


def render_followup(src: str, j: int) -> str:
    """The neutral cue. It preserves the NONE option, so a recovered name is not the price of the
    question, and row C1 measures what is left of that pressure."""
    return (f"Question: starting at {src} and following the direct links for exactly {j} steps, "
            "which single entity name is at step "
            f"{j}? Answer with exactly one entity name, or the single word NONE if the links run "
            f"out before {j} steps.")


def prompt_digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ------------------------------------------------------------------ panel

# (label, item key, j, kind). kind "name" asks for a node on the chain, "over_end" asks past the
# tail so the gold is NONE. Three of the name cells are the round-69 endpoint cells.
PLAN_R70 = [
    ("A48_over", "A48", 56, "over_end"),
    ("C64_over", "C64", 72, "over_end"),
    ("A48_j48", "A48", 48, "name"),
    ("B50_j50", "B50", 50, "name"),
    ("C64_j64", "C64", 64, "name"),
    ("A48_j40", "A48", 40, "name"),
    ("B50_j42", "B50", 42, "name"),
    ("C64_j56", "C64", 56, "name"),
    ("A48_j8", "A48", 8, "name"),
]
ARMS = ("A", "B")
ANCHOR_CELL = "A48_j8"
CONTROL_CELLS = ("A48_over", "C64_over")
DEEP_CELLS = tuple(l for l, _, _, k in PLAN_R70 if k == "name" and l != ANCHOR_CELL)
PREGATE_CALLS = 2             # the exposure census call plus the calibration dispatch


def plan_records() -> list:
    out = []
    for label, key, j, kind in PLAN_R70:
        item = item_for(key)
        src = item["query"][0]
        gold = terminal_at(item, src, j)
        gold = NONE_GOLD if gold is None else gold
        assert (gold == NONE_GOLD) == (kind == "over_end"), (label, gold, kind)
        nodes = path_nodes(item, src)
        cap = MAX_TOKENS
        out.append({"label": label, "arm": "t1", "cell": label, "kind": kind,
                    "item_key": key, "level": item["level"], "seed": item["seed"],
                    "src": src, "j": j, "cap": cap, "gold": gold,
                    "prompt": render_name(item, src, j), "n_facts": len(item["facts"]),
                    "path_len": len(nodes) - 1, "on_path": nodes,
                    "prompt_sha256": prompt_digest(render_name(item, src, j))})
    return out


def arm_records(t1: dict) -> list:
    """The two follow-ups derived from one turn-1 record. Arm A restores the non-report channel
    into the assistant turn, arm B does not. Everything else, down to the cue text, is shared."""
    item = item_for(t1["item_key"])
    vocab = vocab_of(item)
    cue = render_followup(t1["src"], t1["j"])
    out = []
    for arm in ARMS:
        msgs = [{"role": "user", "content": t1["prompt"]}]
        assistant = t1["content_visible"]
        if arm == "A":
            assistant = f"{assistant}\n\n{NOTES_LABEL}\n{t1['trace']}"
        msgs.append({"role": "assistant", "content": assistant})
        msgs.append({"role": "user", "content": cue})
        out.append({"label": f"{t1['label']}_{arm}", "arm": arm, "cell": t1["cell"],
                    "kind": t1["kind"], "item_key": t1["item_key"], "level": t1["level"],
                    "seed": t1["seed"], "src": t1["src"], "j": t1["j"], "cap": ARM_CAP,
                    "gold": t1["gold"], "prompt": cue, "messages": msgs,
                    "on_path": t1.get("on_path", []),
                    "vocab": sorted(vocab),
                    # the pin covers the whole treatment: the cue plus the reconstructed turn
                    "prompt_sha256": prompt_digest(json.dumps(msgs, sort_keys=True))})
    return out


# ------------------------------------------------------------------ sanitizer

_SECRET_PATTERNS = [
    re.compile(r"https?://\S+"),
    re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d+)?\b"),
    re.compile(r"/(?:root|home|mnt|media|run/user)/\S+"),
    # Serving-id labels (issue #85): a model identifier ending in a quantization tag. Assembled by
    # concatenation so this file carries no pattern instance of its own.
    re.compile(r"\b[a-z0-9][a-z0-9._-]*-(?:" + "iq" + r"\d+|q\d+|ud-q\d+)(?:[_-]?[a-z0-9]+)?\b"),
]


def sanitize(text, limit: int = 2600) -> str:
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


def trace_of(message: dict) -> tuple:
    """Issue #105 merge rule: reasoning_content if non-empty, else reasoning, else empty."""
    fields = sorted(k for k in message)
    rc = message.get("reasoning_content") or ""
    src = "reasoning_content" if rc else ""
    if not rc:
        rc = message.get("reasoning") or ""
        src = "reasoning" if rc else ""
    return rc, fields, src


def declared_answer(content: str, vocab: set):
    """The last entity name in the visible answer field, else the NONE sentinel, else delivered
    without an item name. An empty answer field is not a delivery."""
    if not content or not content.strip():
        return None, False
    ents = [t.lower() for t in NAME_RE.findall(content) if t.lower() in vocab]
    if ents:
        return ents[-1], True
    if re.search(r"\bnone\b", content, re.I):
        return NONE_GOLD, True
    return None, True


def last_vocab_name(text: str, vocab: set):
    ents = [t.lower() for t in NAME_RE.findall(text or "") if t.lower() in vocab]
    return ents[-1] if ents else None


def delivery_state(rec: dict) -> str:
    gold = rec["gold"]
    ans, delivered = rec["declared"], rec["delivered"]
    if not delivered:
        return ("censored_at_cap" if rec["finish_reason"] == "length" else "empty_answer_field")
    if gold == NONE_GOLD:
        if ans == NONE_GOLD:
            return "declared_none"
        return "false_name_on_none_gold"
    if ans == gold:
        return "delivered_correct"
    if ans == NONE_GOLD:
        return "declared_none_on_name_gold"
    if ans is None:
        return "delivered_no_item_name"
    return ("delivered_wrong_on_right_path" if ans in (rec.get("on_path") or [])
            else "delivered_wrong_off_path")


def wall_laws_fit(rec: dict) -> list:
    fits = []
    ct, cap, fin = rec["completion_tokens"], rec["cap"], rec["finish_reason"]
    if ct is None:
        return fits
    if 1556 <= ct <= 1558 and fin == "stop":
        fits.append("L1_self_stop_band")
    if cap - ct == 492:
        fits.append("L2_reserve_492")
    if cap - ct <= 19:
        fits.append("L3_cap_bound")
    return fits


def tok_rate(completion_tokens, wall_s):
    if not completion_tokens or not wall_s:
        return None
    return round(completion_tokens / wall_s, 3)


# ------------------------------------------------------------------ endpoint


def chat(messages: list, cap: int) -> dict:
    base = os.environ["NIGHTLY_BASE_URL"]
    key = os.environ.get("NIGHTLY_API_KEY", "")
    body = json.dumps({"model": os.environ["NIGHTLY_MODEL_ID"], "messages": messages,
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
    completion = usage.get("completion_tokens")
    wall = round(time.time() - t0, 3)
    return {"message": message, "finish_reason": choice.get("finish_reason"),
            "completion_tokens": completion, "prompt_tokens": usage.get("prompt_tokens"),
            "wall_s": wall, "tok_per_s": tok_rate(completion, wall)}


def measure_record(spec: dict, res: dict) -> dict:
    """Turn one endpoint response into the scored record. The scorer never reads the trace: the
    verdict is the visible answer field against the solver gold (issue #94)."""
    message = res["message"]
    trace, fields, tsrc = trace_of(message)
    vocab = set(spec.get("vocab") or vocab_of(item_for(spec["item_key"])))
    visible = sanitize(message.get("content") or "")
    ans, delivered = declared_answer(visible, vocab)
    rec = dict(spec)
    rec.pop("messages", None)
    rec.update({
        "content": visible, "content_chars": len(visible),
        "finish_reason": res["finish_reason"], "completion_tokens": res["completion_tokens"],
        "prompt_tokens": res["prompt_tokens"], "wall_s": res["wall_s"],
        "tok_per_s": res["tok_per_s"], "message_fields": fields, "trace_field": tsrc,
        "trace_chars": len(trace), "declared": ans, "delivered": delivered,
        "correct": (ans is not None and ans == spec["gold"]),
        "gold_in_visible": spec["gold"] in (visible or "").lower() if spec["gold"] != NONE_GOLD
        else None,
        "gold_in_trace": (spec["gold"] in trace.lower()) if spec["gold"] != NONE_GOLD else None,
        "trace_vocab_tail": last_vocab_name(trace, vocab),
    })
    if rec["completion_tokens"] is not None:
        rec["reserve"] = spec["cap"] - rec["completion_tokens"]
    rec["wall_laws"] = wall_laws_fit(rec)
    rec["delivery_state"] = delivery_state(rec)
    if rec["arm"] == "A":
        rec["answer_is_notes_tail"] = (ans is not None and ans == rec["trace_vocab_tail"])
    rec["prompt"] = sanitize(spec["prompt"], limit=900)
    rec["prompt_sha256"] = spec.get("prompt_sha256") or prompt_digest(spec["prompt"])
    return rec


# ------------------------------------------------------------------ gate


def gate_spec(records: list) -> dict:
    return {
        "schema": GATE_SCHEMA,
        "round": 70,
        "firing": "2026-11-16 04:12",
        "slot": "2/6",
        "model_digest": model_digest(),
        "question": ("is a terminal name that the record's non-report channel contains but the "
                     "answer field omits accessible for report, when the report conditions change"),
        "arms": {"A": "turn-1 answer field plus the turn-1 non-report channel in the assistant turn",
                 "B": "turn-1 answer field only in the assistant turn"},
        "scoring": ("visible answer field against the generator's independent solver; the trace is "
                    "a treatment and a count census, never a scorer (issue #94)"),
        "decision_R1": {
            "min_lost_cells": 3,
            "readout_gated": "n_A - n_B >= 2 and n_A >= 2",
            "channel_toxic": "n_B - n_A >= 2",
            "no_channel_effect": "abs(n_A - n_B) <= 1",
            "downgrade_X2": "if every arm-A recovery equals the notes' last vocabulary name, "
                            "the reading is tail_copy and not selection",
            "statistics": "exact one-sided binomial over discordant pairs, exploratory, n single "
                          "digits, no significance claim",
        },
        "controls_C1": "a name emitted where the links ran out is a manufactured name; any arm-A "
                       "false name caps the R1 reading at recovery-with-compliance-cost",
        "caps": {"max_prompts": CALL_CAP, "max_tokens": MAX_TOKENS,
                 "dispatch_budget_s": DISPATCH_BUDGET_S,
                 "planned_calls": len(records), "pre_gate_calls": PREGATE_CALLS},
        "matched_pair": MATCHED_PAIR,
        "wall_laws": WALL_LAWS,
        "delivery_states": list(DELIVERY_STATES),
        "cells": [{"label": r["label"], "arm": r["arm"], "j": r["j"], "gold": r["gold"],
                   "kind": r["kind"], "level": r["level"], "seed": r["seed"],
                   "prompt_sha256": r["prompt_sha256"]} for r in records],
        "theory_rows": {
            "T1_verbal_report_bibliographic": {
                "source": "Ericsson & Simon 1980, Psychological Review 87(3):215-251, "
                          "DOI 10.1037/0033-295X.87.3.215",
                "statement": ("used only as the bibliographic anchor for the frame that a verbal "
                              "report is a retrieval from a prior store rather than a special "
                              "introspective faculty. The thesis wording itself was NOT read "
                              "this session and is carried as owed"),
                "verification": ("Crossref work record fetched this session 2026-11-16, record "
                                 "level only (title, authors, venue, year, DOI); no abstract, so "
                                 "no content claim from this row")},
            "T2_reports_as_causal_theory": {
                "source": "Nisbett & Wilson 1977, Psychological Review 84(3):231-259, "
                          "DOI 10.1037/0033-295X.84.3.231",
                "statement": ("a fluent report can be produced by implicit causal theory instead "
                              "of by access to the process, so arm A recovering a name is not by "
                              "itself access. Content carried as owed at the same level"),
                "verification": ("Crossref work record fetched this session 2026-11-16, record "
                                 "level only. Corrected during this round: the working draft of "
                                 "this gate had the title as 'Telling more than we can do' and "
                                 "the venue as the Journal of Experimental Social Psychology")},
            "T3_accessibility": {
                "source": "Block 2007, Behavioral and Brain Sciences 30:481-499, "
                          "DOI 10.1017/S0140525X07002786",
                "statement": ("the row R1 operationalizes availability-for-report versus report; "
                              "the article takes accessibility as its object of analysis. No "
                              "argument content is claimed from this row"),
                "verification": ("Crossref work record fetched this session 2026-11-16, record "
                                 "level only. Caveat on record: citation databases circulate a "
                                 "second DOI suffix for this article and the alternative was not "
                                 "cross-checked this session")},
            "T4_verbalizable_workspace": {
                "source": "arXiv:2607.15495 v1, 2026-07-16 (Gurnee, Sofroniew, Pearce, and "
                          "co-authors, 16; Lindsey corresponding group), unrefereed preprint",
                "statement": ("title 'Verbalizable Representations Form a Global Workspace in "
                              "Language Models'; the abstract reports a set of representations "
                              "the model is poised to verbalize whose contents can be reported "
                              "and are used to carry the intermediate steps of silent reasoning "
                              "(quote, 9 words), and it introduces training that changes only "
                              "what a model would say if interrupted and asked to reflect"),
                "verification": "arXiv export API fetched this session 2026-11-16, abstract level"},
            "T5_introspection_gap": {
                "source": "arXiv:2601.01828 v1, 2026-01-05 (Lindsey), unrefereed preprint",
                "statement": ("injecting known concepts into activations and reading the self-"
                              "report separates grounded report from confabulation; the abstract "
                              "reports the capacity is highly unreliable and context-dependent "
                              "(quote, 5 words)"),
                "verification": ("arXiv export API fetched this session 2026-11-16, abstract "
                                 "level. The base-model versus post-trained asymmetry is NOT in "
                                 "the abstract and is not claimed here")},
            "T6_trace_answer_dissociation": {
                "source": "arXiv:2605.29087 v1, 2026-05-27, unrefereed preprint",
                "statement": ("'The Chain Holds, the Answer Folds: Trace-Answer Dissociation in "
                              "Reasoning Models Under Adversarial Pressure': the abstract reports "
                              "the chain staying correct while the emitted answer flips, a latent-"
                              "correct rate near 50 percent at the behavioral flip in think mode "
                              "against 11 to 15 percent without a thinking channel, and that a "
                              "naive trace-anchored defense backfired. That last clause is the "
                              "registered prior against arm A: restoring the channel is not "
                              "assumed to help"),
                "verification": "arXiv export API fetched this session 2026-11-16, abstract level"},
        },
    }


# ------------------------------------------------------------------ scoring


def score(records: list, gate: dict) -> dict:
    by_label = {r["label"]: r for r in records}
    t1 = [r for r in records if r["arm"] == "t1"]
    deep = [r for r in t1 if r["cell"] in DEEP_CELLS]
    lost = [r for r in deep if not r["correct"]]
    held = [r for r in deep if r["correct"]]

    def arm_n(cell_labels: list, arm: str):
        n_ok = n_seen = 0
        for lab in cell_labels:
            rec = by_label.get(f"{lab}_{arm}")
            if rec is None:
                continue
            n_seen += 1
            if rec["correct"]:
                n_ok += 1
        return n_ok, n_seen

    lost_labels = [r["label"] for r in lost]
    held_labels = [r["label"] for r in held]
    nA, seenA = arm_n(lost_labels, "A")
    nB, seenB = arm_n(lost_labels, "B")
    hA, hseenA = arm_n(held_labels, "A")
    hB, hseenB = arm_n(held_labels, "B")

    paired = [lab for lab in lost_labels
              if f"{lab}_A" in by_label and f"{lab}_B" in by_label]
    disc_a = [lab for lab in paired
              if by_label[f"{lab}_A"]["correct"] and not by_label[f"{lab}_B"]["correct"]]
    disc_b = [lab for lab in paired
              if by_label[f"{lab}_B"]["correct"] and not by_label[f"{lab}_A"]["correct"]]
    n_disc = len(disc_a) + len(disc_b)
    p_one = None
    if n_disc:
        k = max(len(disc_a), len(disc_b))
        p_one = round(min(1.0, 2.0 * sum(math.comb(n_disc, i) for i in range(k, n_disc + 1))
                          / (2.0 ** n_disc)), 4)

    if seenA < gate["decision_R1"]["min_lost_cells"] or seenB < gate["decision_R1"]["min_lost_cells"]:
        verdict_r1 = "not_evaluable"
    elif nA - nB >= 2 and nA >= 2:
        verdict_r1 = "readout_gated"
    elif nB - nA >= 2:
        verdict_r1 = "channel_toxic"
    elif abs(nA - nB) <= 1:
        verdict_r1 = "no_channel_effect"
    else:
        verdict_r1 = "ambiguous"

    recov = [by_label[f"{lab}_A"] for lab in paired
             if by_label[f"{lab}_A"]["correct"]]
    if not recov:
        verdict_x2 = "no_recovery_to_explain"
    elif all(r.get("answer_is_notes_tail") for r in recov):
        verdict_x2 = "tail_copy"
        if verdict_r1 == "readout_gated":
            verdict_r1 = "readout_gated_downgraded_to_tail_copy"
    else:
        verdict_x2 = "selection_beyond_tail"

    ctrl = [r for r in t1 if r["cell"] in CONTROL_CELLS]
    false_names = {"A": 0, "B": 0}
    ctrl_none_t1 = sum(1 for r in ctrl if r["declared"] == NONE_GOLD)
    for lab in [r["label"] for r in ctrl]:
        for arm in ARMS:
            rec = by_label.get(f"{lab}_{arm}")
            if rec is not None and rec["delivery_state"] == "false_name_on_none_gold":
                false_names[arm] += 1

    states: dict = {}
    for r in records:
        states[r["delivery_state"]] = states.get(r["delivery_state"], 0) + 1
    law_counts: dict = {}
    for r in records:
        for law in r["wall_laws"]:
            law_counts[law] = law_counts.get(law, 0) + 1

    return {
        "model_digest": gate["model_digest"],
        "prompts_dispatched": len(records),
        "R1_readout_recovery": {
            "verdict": verdict_r1, "n_lost": len(lost), "n_held": len(held),
            "lost_cells": lost_labels, "held_cells": held_labels,
            "arm_A_recovered": nA, "arm_A_seen": seenA,
            "arm_B_recovered": nB, "arm_B_seen": seenB,
            "paired_cells": paired, "discordant_A_only": disc_a, "discordant_B_only": disc_b,
            "exact_two_sided_binomial_on_discordants": p_one,
        },
        "X2_tail_shortcut": {
            "verdict": verdict_x2,
            "arm_A_correct_is_notes_tail": [bool(r.get("answer_is_notes_tail")) for r in recov],
        },
        "H1_answer_stability": {"n_held": len(held), "arm_A_kept": hA, "arm_A_seen": hseenA,
                                "arm_B_kept": hB, "arm_B_seen": hseenB},
        "C1_name_pressure": {"controls": [r["label"] for r in ctrl],
                             "turn1_declared_none": ctrl_none_t1,
                             "false_names_arm_A": false_names["A"],
                             "false_names_arm_B": false_names["B"]},
        "S1_delivery_census": states,
        "W2_wall_law_counts": law_counts,
        "M4_matched_pair": {lab: {"prompt_sha256": by_label[lab].get("prompt_sha256", "")[:16],
                                 "delivery_state": by_label[lab]["delivery_state"],
                                 "completion_tokens": by_label[lab]["completion_tokens"]}
                            for lab in MATCHED_PAIR["prompt_sha256"] if lab in by_label},
        "trace_exposure": {"fields": sorted({f for r in records for f in r.get("message_fields", [])}),
                           "supplying_field": sorted({r["trace_field"] for r in records
                                                      if r.get("trace_field")}),
                           "records_with_trace": sum(1 for r in records if r.get("trace_chars"))},
        "gold_in_trace_census": {"true": sum(1 for r in records if r["gold_in_trace"] is True),
                                 "false": sum(1 for r in records if r["gold_in_trace"] is False),
                                 "n_a_none_gold": sum(1 for r in records
                                                      if r["gold_in_trace"] is None)},
        "per_record": [{"label": r["label"], "arm": r["arm"], "j": r["j"], "gold": r["gold"],
                        "declared": r["declared"], "correct": r["correct"],
                        "delivery_state": r["delivery_state"], "finish": r["finish_reason"],
                        "tokens": r["completion_tokens"], "reserve": r.get("reserve"),
                        "tok_per_s": r["tok_per_s"], "trace_chars": r["trace_chars"],
                        "gold_in_trace": r["gold_in_trace"], "wall_laws": r["wall_laws"],
                        "answer_is_notes_tail": r.get("answer_is_notes_tail")}
                       for r in records],
    }


# ------------------------------------------------------------------ commands


def write_jsonl(path: str, records: list) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, sort_keys=True) + "\n")


def read_jsonl(path: str) -> list:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def cmd_measure() -> int:
    """Pre-dispatch: the trace-exposure census and one shallow calibration dispatch. Both are
    counted against the prompt cap."""
    recs = []
    item = _ITEMS["A48"]
    probe = ("Rule: for all x, y, z: if x precedes y and y precedes z, then x precedes z. "
             "Facts: alby precedes birch. birch precedes cobin. Question: does alby precedes "
             "cobin? Answer with exactly one word: yes or no.")
    res = chat([{"role": "user", "content": probe}], CENSUS_CAP)
    trace, fields, tsrc = trace_of(res["message"])
    cen = {"prompt_tokens": res["prompt_tokens"], "completion_tokens": res["completion_tokens"],
           "finish_reason": res["finish_reason"], "wall_s": res["wall_s"],
           "message_fields": fields, "trace_field": tsrc, "trace_chars": len(trace),
           "content": sanitize(res["message"].get("content") or "", 80)}
    recs.append({"label": "census_exposure", "arm": "census", "cell": "census", "kind": "census",
                 "item_key": "A48", "level": 48, "seed": item["seed"], "src": "", "j": 0,
                 "cap": CENSUS_CAP, "gold": "yes", "prompt": probe, "on_path": [],
                 **{k: v for k, v in cen.items()}})
    spec = plan_records()[-1]
    res2 = chat([{"role": "user", "content": spec["prompt"]}], MAX_TOKENS)
    m = measure_record(spec, res2)
    m["label"] = "pregate_calibration"
    m["cell"] = "pregate_calibration"
    recs.append(m)
    write_jsonl(os.path.join(_HERE, "measure.jsonl"), recs)
    with open(os.path.join(_HERE, "measure.json"), "w", encoding="utf-8") as fh:
        json.dump({"census": cen, "calibration": {"completion_tokens": m["completion_tokens"],
                                                  "tok_per_s": m["tok_per_s"],
                                                  "wall_s": m["wall_s"],
                                                  "delivery_state": m["delivery_state"],
                                                  "declared": m["declared"]},
                   "model_digest": model_digest()}, fh, sort_keys=True, indent=1)
    print(json.dumps(recs[-1]["delivery_state"]))
    return 0


def cmd_freeze() -> int:
    recs = plan_records()
    gate = gate_spec(recs)
    with open(os.path.join(_HERE, "gate.json"), "w", encoding="utf-8") as fh:
        json.dump(gate, fh, sort_keys=True, indent=1)
    blob = hashlib.sha256(json.dumps(gate, sort_keys=True).encode()).hexdigest()
    print(blob)
    return 0


def cmd_run() -> int:
    """Dispatch pass. A turn-1 non-report channel stays in memory only long enough to build its
    two arms: it is a treatment, never an archive field, so no trace text is written to disk."""
    gate_path = os.path.join(_HERE, "gate.json")
    if not os.path.exists(gate_path):
        print("refusing to dispatch: the gate is not frozen", file=sys.stderr)
        return 3
    with open(gate_path, encoding="utf-8") as fh:
        gate = json.load(fh)
    pins = {c["label"]: c["prompt_sha256"] for c in gate["cells"]}
    planned = plan_records()
    for r in planned:
        if pins.get(r["label"]) != r["prompt_sha256"]:
            print(f"refusing to dispatch: the prompt drifted at {r['label']}", file=sys.stderr)
            return 3
    if gate["model_digest"] != model_digest():
        print("refusing to dispatch: the serving build moved after the freeze", file=sys.stderr)
        return 3
    raw_path = os.path.join(_HERE, "raw.jsonl")
    records = read_jsonl(raw_path)
    done = {r["label"] for r in records}
    t_start = time.time()
    retries = 0
    stopped_early: list = []

    def dispatch(messages: list, cap: int) -> dict:
        nonlocal retries
        while True:
            try:
                return chat(messages, cap)
            except Exception as exc:
                retries += 1
                print(f"transport error ({type(exc).__name__}), retry {retries}/"
                      f"{MAX_RETRIES_TOTAL}", file=sys.stderr)
                if retries > MAX_RETRIES_TOTAL:
                    raise
                time.sleep(5.0)

    for spec in planned:
        if spec["label"] in done:
            continue
        if time.time() - t_start > DISPATCH_BUDGET_S - CELL_FLOOR_S:
            print(f"dispatch budget reached, stopping before {spec['label']}", file=sys.stderr)
            stopped_early.append(spec["label"])
            break
        res = dispatch([{"role": "user", "content": spec["prompt"]}], spec["cap"])
        rec = measure_record(spec, res)
        trace, _fields, _tsrc = trace_of(res["message"])
        with open(raw_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        records.append(rec)
        print(f"{rec['label']} {rec['delivery_state']} ct={rec['completion_tokens']} "
              f"trace={rec['trace_chars']} {rec['tok_per_s']} tok/s", flush=True)
        if spec["label"] == ANCHOR_CELL:
            continue          # the anchor is liveness only, it gets no follow-up
        for arm_spec in arm_records({**rec, "content_visible": rec["content"], "trace": trace}):
            if arm_spec["label"] in done:
                continue      # a resumed pass never re-dispatches an arm it already recorded
            if time.time() - t_start > DISPATCH_BUDGET_S - CELL_FLOOR_S:
                print(f"dispatch budget reached, stopping before {arm_spec['label']}",
                      file=sys.stderr)
                stopped_early.append(arm_spec["label"])
                break
            arec = measure_record(arm_spec, dispatch(arm_spec["messages"], arm_spec["cap"]))
            with open(raw_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(arec, sort_keys=True) + "\n")
            records.append(arec)
            print(f"{arec['label']} {arec['delivery_state']} ct={arec['completion_tokens']} "
                  f"{arec['tok_per_s']} tok/s", flush=True)
    with open(os.path.join(_HERE, "raw_meta.json"), "w", encoding="utf-8") as fh:
        json.dump({"prompts_in_raw": len(records),
                   "gate_blob": hashlib.sha256(
                       json.dumps(gate, sort_keys=True).encode()).hexdigest(),
                   "dispatch_wall_s": round(time.time() - t_start, 1),
                   "stopped_early": stopped_early, "transport_retries": retries,
                   "model_digest": model_digest()}, fh, sort_keys=True, indent=1)
    print(f"raw.jsonl holds {len(records)} records")
    return 0


def cmd_rescore() -> int:
    with open(os.path.join(_HERE, "gate.json"), encoding="utf-8") as fh:
        gate = json.load(fh)
    records = read_jsonl(os.path.join(_HERE, "raw.jsonl"))
    summary = score(records, gate)
    with open(os.path.join(_HERE, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, sort_keys=True, indent=1)
    print(json.dumps({k: summary[k] for k in ("R1_readout_recovery", "X2_tail_shortcut",
                                              "H1_answer_stability", "C1_name_pressure")},
                     sort_keys=True, indent=1))
    return 0


# ------------------------------------------------------------------ selftest


def selftest() -> int:
    global _ITEMS
    checks: list = []

    def ok(name: str, cond: bool) -> None:
        checks.append((name, bool(cond)))

    ok("binomial 3 of 3", abs(sum(math.comb(3, i) for i in range(3, 4)) / 8 - 0.125) < 1e-12)
    ok("binomial row sum", sum(math.comb(5, i) for i in range(6)) == 32)
    ok("math is stdlib exact", math.comb(40, 2) == 780)

    _ITEMS = select_items()
    ok("three items", len(_ITEMS) == 3)
    ok("archived k=48 seed", _ITEMS["A48"]["seed"] == ARCHIVED_K48["seed"])
    ok("archived k=48 yes/no digest",
       prompt_digest(render_yesno(_ITEMS["A48"]))[:16] == ARCHIVED_K48["yesno_digest16"])
    for key in ("A48", "B50", "C64"):
        it = _ITEMS[key]
        lvl = it["level"]
        head = it["query"][0]
        nodes = path_nodes(it, head)
        ok(f"{key} load floor facts", len(it["facts"]) == 2 * lvl)
        ok(f"{key} path length", len(nodes) - 1 == lvl)
        ok(f"{key} solver at 0", terminal_at(it, head, 0) == head)
        ok(f"{key} solver at 1", terminal_at(it, head, 1) == nodes[1])
        mid = lvl // 2
        ok(f"{key} solver at mid", terminal_at(it, head, mid) == nodes[mid])
        ok(f"{key} solver at tail", terminal_at(it, head, lvl) == nodes[-1])
        ok(f"{key} solver past tail", terminal_at(it, head, lvl + 1) is None)
        check_item(it)
        bad = dict(it)
        bad["facts"] = list(it["facts"]) + [it["facts"][0]]
        try:
            check_item(bad)
            ok(f"{key} doctored item refused", False)
        except AssertionError:
            ok(f"{key} doctored item refused", True)
        wide = dict(it)
        s0, r0, t0 = it["facts"][0]
        s1, r1, t1 = it["facts"][1]
        wide["facts"] = [(s0, r0, t0), (s0, r0, t1)] + list(it["facts"][2:])
        try:
            check_item(wide)
            ok(f"{key} out-degree-two item refused", False)
        except AssertionError:
            ok(f"{key} out-degree-two item refused", True)

    # the matched pair: three turn-1 prompts are byte-identical to the round-63 and round-69 cells
    for lab, want in MATCHED_PAIR["prompt_sha256"].items():
        rec = next(r for r in plan_records() if r["label"] == lab)
        ok(f"matched pair {lab}", prompt_digest(rec["prompt"]) == want)

    # panel arithmetic and gold assignment
    recs = plan_records()
    ok("nine turn-1 cells", len(recs) == 9)
    ok("prompt cap", sum(1 for _ in recs) + 2 + sum(
        2 for r in recs if r["label"] != ANCHOR_CELL) <= CALL_CAP)
    ok("controls ask past the tail", all(r["gold"] == NONE_GOLD for r in recs
                                         if r["kind"] == "over_end"))
    ok("name cells have a name gold", all(r["gold"] != NONE_GOLD for r in recs
                                          if r["kind"] == "name"))
    over = next(r for r in recs if r["label"] == "A48_over")
    ok("over_end j above path length", over["j"] > over["path_len"])

    # scoring controls
    vocab = {"blorp", "crath", "dunnu"}
    ok("scorer takes the last name", declared_answer("walk gives Blorp then CRATH.", vocab)
       == ("crath", True))
    ok("scorer reads NONE", declared_answer("The links run out: NONE.", vocab)
       == (NONE_GOLD, True))
    ok("scorer refuses an empty field", declared_answer("   ", vocab) == (None, False))
    ok("scorer marks a non-entity", declared_answer("zorp", vocab) == (None, True))
    sample = {"gold": "crath", "finish_reason": "stop", "completion_tokens": 40, "cap": 2048,
              "on_path": ["blorp", "crath"], "declared": "blorp", "delivered": True}
    ok("state wrong on right path", delivery_state(sample) == "delivered_wrong_on_right_path")
    sample2 = dict(sample, declared="flimp")
    ok("state wrong off path", delivery_state(sample2) == "delivered_wrong_off_path")
    sample3 = dict(sample, declared=NONE_GOLD)
    ok("state refusal on a name gold",
       delivery_state(sample3) == "declared_none_on_name_gold")
    sample4 = dict(sample, gold=NONE_GOLD, declared="blorp")
    ok("state false name on a NONE gold",
       delivery_state(sample4) == "false_name_on_none_gold")
    sample5 = dict(sample, delivered=False, finish_reason="length")
    ok("state cap censor", delivery_state(sample5) == "censored_at_cap")
    sample6 = dict(sample, delivered=False, finish_reason="stop")
    ok("state empty field", delivery_state(sample6) == "empty_answer_field")

    # wall laws
    ok("L1 band", "L1_self_stop_band" in wall_laws_fit(
        {"completion_tokens": 1557, "cap": 2048, "finish_reason": "stop"}))
    ok("L1 needs stop", "L1_self_stop_band" not in wall_laws_fit(
        {"completion_tokens": 1557, "cap": 2048, "finish_reason": "length"}))
    ok("L2 reserve 492", "L2_reserve_492" in wall_laws_fit(
        {"completion_tokens": 1556, "cap": 2048, "finish_reason": "stop"}))
    ok("L3 cap bound", "L3_cap_bound" in wall_laws_fit(
        {"completion_tokens": 2040, "cap": 2048, "finish_reason": "length"}))
    ok("law-free record", wall_laws_fit(
        {"completion_tokens": 300, "cap": 2048, "finish_reason": "stop"}) == [])

    # arm construction: one bit, and nothing else
    spec = next(r for r in plan_records() if r["label"] == "B50_j50")
    fake_t1 = {**spec, "content_visible": "prish", "trace": "dunnu precedes crath. crath blorp."}
    arms = {a["arm"]: a for a in arm_records(fake_t1)}
    ok("two arms per cell", set(arms) == {"A", "B"})
    a_txt = json.dumps(arms["A"]["messages"])
    b_txt = json.dumps(arms["B"]["messages"])
    ok("arm A carries the notes label", NOTES_LABEL in a_txt)
    ok("arm A carries the trace text", "dunnu precedes crath" in a_txt)
    ok("arm B carries no trace text", "dunnu precedes crath" not in b_txt)
    ok("arm B keeps the visible answer", "prish" in b_txt)
    ok("both arms share the cue", arms["A"]["prompt"] == arms["B"]["prompt"] ==
       render_followup(spec["src"], spec["j"]))
    ok("cue preserves NONE", "NONE" in render_followup(spec["src"], spec["j"]))
    ok("cue names the step", f"step {spec['j']}" in render_followup(spec["src"], spec["j"]))
    ok("arms differ in exactly one message", sum(
        1 for x, y in zip(arms["A"]["messages"], arms["B"]["messages"])
        if json.dumps(x) != json.dumps(y)) == 1)
    ok("arm cap within protocol", ARM_CAP <= MAX_TOKENS)

    # notes-tail measure (the X2 shortcut detector)
    ok("tail name is the last vocabulary name",
       last_vocab_name("blorp then crath then dunnu then zorp", vocab) == "dunnu")
    ok("tail name None when no vocabulary name", last_vocab_name("nothing here", vocab) is None)

    # decision rule, exercised on synthetic outcomes
    dc = list(DEEP_CELLS)   # the scorer only looks at registered deep cells
    def synth(outcomes: dict, tail_all: bool = True) -> tuple:
        fake = []
        for lab, (t1_ok, a_ok, b_ok) in outcomes.items():
            gold = "crath"
            fake.append({"label": lab, "arm": "t1", "cell": lab, "kind": "name", "j": 48,
                         "gold": gold, "correct": t1_ok, "declared": gold if t1_ok else "blorp",
                         "delivered": True, "finish_reason": "stop", "completion_tokens": 1557,
                         "cap": 2048, "on_path": ["blorp", "crath"], "trace_chars": 900,
                         "gold_in_trace": True, "trace_vocab_tail": "blorp", "wall_laws": [],
                         "delivery_state": "delivered_correct" if t1_ok else
                         "delivered_wrong_on_right_path", "tok_per_s": 40.0,
                         "message_fields": [], "trace_field": "reasoning_content"})
            for arm, okk in (("A", a_ok), ("B", b_ok)):
                fake.append({"label": f"{lab}_{arm}", "arm": arm, "cell": lab, "kind": "name",
                             "j": 48, "gold": gold, "correct": okk,
                             "declared": gold if okk else "blorp", "delivered": True,
                             "finish_reason": "stop", "completion_tokens": 60, "cap": 2048,
                             "on_path": ["blorp", "crath"], "trace_chars": 0,
                             "gold_in_trace": None, "trace_vocab_tail": "blorp", "wall_laws": [],
                             "delivery_state": "delivered_correct" if okk else
                             "delivered_wrong_on_right_path", "tok_per_s": 30.0,
                             "answer_is_notes_tail": (okk and arm == "A" and tail_all),
                             "message_fields": [], "trace_field": ""})
        out = score(fake, gate_spec(plan_records()))
        return out["R1_readout_recovery"]["verdict"], out["X2_tail_shortcut"]["verdict"]

    lost3 = {dc[0]: (False, True, False), dc[1]: (False, True, False),
             dc[2]: (False, True, False)}
    v, x = synth(dict(lost3))
    ok("R1 readout_gated on 3-0", v == "readout_gated_downgraded_to_tail_copy")
    ok("X2 tail_copy downgrade fires", x == "tail_copy")
    v2, x2 = synth({dc[0]: (False, True, False), dc[1]: (False, True, False),
                    dc[2]: (False, True, False), dc[3]: (False, True, False)}, tail_all=False)
    ok("R1 gated with four recoveries", v2 == "readout_gated")
    ok("X2 selection beyond tail", x2 == "selection_beyond_tail")
    v3, _ = synth({dc[0]: (False, False, True), dc[1]: (False, False, True),
                   dc[2]: (False, False, True)})
    ok("R1 channel_toxic on 0-3", v3 == "channel_toxic")
    v4, _x4 = synth({dc[0]: (False, True, True), dc[1]: (False, False, False),
                     dc[2]: (False, True, True)})
    ok("R1 no_channel_effect on a tie", v4 == "no_channel_effect")
    v5, _ = synth({dc[0]: (True, True, True), dc[1]: (True, True, True)})
    ok("R1 not_evaluable with no lost cells", v5 == "not_evaluable")
    v6, _ = synth({dc[0]: (False, True, False), dc[1]: (False, True, False)})
    ok("R1 not_evaluable below min lost", v6 == "not_evaluable")

    # sanitizer: assembled fixtures on RFC 5737 documentation addresses, so this file carries no
    # instance of what it redacts and no live-endpoint address class either
    doc_ip = "192.0.2.34" + ":" + "9999"
    ok("sanitizer strips an IP", doc_ip not in sanitize("endpoint at " + doc_ip))
    url = "ht" + "tps://example.invalid/deep/path"
    ok("sanitizer strips a URL", "tp://" not in sanitize("see " + url))
    path = "/" + "home" + "/user/models/m.bin"
    ok("sanitizer strips a home path", "user/models" not in sanitize("load " + path))
    quant = "pool-" + "model" + "-q" + "4_kx"
    ok("sanitizer strips a serving-id label", quant not in sanitize("serving " + quant))
    ok("sanitizer keeps an entity name", "trackst" in sanitize("trackst"))
    ok("sanitizer caps length", len(sanitize("y" * 9000, limit=900)) == 900)
    ok("sanitizer passes None", sanitize(None) == "")

    # the trace merge rule (issue #105)
    ok("merge prefers reasoning_content", trace_of({"reasoning_content": "x", "reasoning": "y"})
       == ("x", ["reasoning", "reasoning_content"], "reasoning_content"))
    ok("merge falls back to reasoning", trace_of({"reasoning": "y"}) == ("y", ["reasoning"],
                                                                         "reasoning"))
    ok("merge yields empty with no channel", trace_of({"content": "c"}) == ("c"[:0], ["content"],
                                                                           ""))

    # gate integrity
    gate = gate_spec(plan_records())
    ok("gate carries the decision rule", "readout_gated" in gate["decision_R1"])
    ok("gate cell count", len(gate["cells"]) == 9)
    ok("gate records every cell prompt", all(c["prompt_sha256"] for c in gate["cells"]))
    ok("gate model digest is 16 hex",
       re.fullmatch(r"[0-9a-f]{16}", gate["model_digest"]) is not None)
    planned_total = (gate["caps"]["planned_calls"] + gate["caps"]["pre_gate_calls"]
                     + 2 * (len(DEEP_CELLS) + len(CONTROL_CELLS)))
    ok("gate cap arithmetic within 40", planned_total <= CALL_CAP)
    ok("gate has theory rows with sources", all(
        row["source"] and row["verification"] for row in gate["theory_rows"].values()))

    failed = [name for name, cond in checks if not cond]
    print(f"selftest: {len(checks) - len(failed)} of {len(checks)} checks green")
    for name in failed:
        print(f"FAIL {name}", file=sys.stderr)
    return 1 if failed else 0


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description="round 70 readout-recovery probe")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--rescore", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    global _ITEMS
    _ITEMS = select_items()
    if args.measure:
        return cmd_measure()
    if args.freeze:
        return cmd_freeze()
    if args.run:
        return cmd_run()
    if args.rescore:
        return cmd_rescore()
    print("nothing to do", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

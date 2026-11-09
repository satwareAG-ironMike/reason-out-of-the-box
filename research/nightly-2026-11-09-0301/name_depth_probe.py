#!/usr/bin/env python3
"""Round 55 probe: can the ladder be answered in a name space, and where does that space turn over?

Question (issue #71, #94, #100, #105, #126, #129). Every ladder accuracy number this repository has
shipped is a yes/no number. Two consequences follow from that and neither has been measured on one
firing. First, on a two-way answer space a constant rule scores 0.50 and the shipped corpus is
leaky under undirected component membership, which reproduces the gold label at 1.0000 on every
shipped level (generators/AGENTS.md, issue #77), so a high yes/no accuracy is weak evidence that a
traversal happened (issue #94 states the same problem for the probe readout). Second, the answer
space is what makes the depth claim soft at the top: to answer "does a precedes b" the model only
has to decide membership, while to answer "name the entity exactly j steps from a" it has to
produce one name out of about 2,700, which no constant rule and no connectivity shortcut can do.

Round 50 separated depth from input load by selecting items inside a fixed fact band, and found
that accuracy never turns over while delivery does (23/23 delivered answers correct, 5
non-deliveries, all at the 2,048 cap). It could not separate computation from surfacing: its
trace-recovery rule failed its own calibration at 0.5652 because the model echoes the question, and
an echo contains the verdict words. A name answer has no such echo, so the same separation can be
attempted here with a matched control (row C6): for every record, the rate at which the gold
terminal name appears in the reasoning text against the rate at which a pseudo-gold name of the
same role from the same item appears.

This instrument holds the prompt bytes fixed and moves only the step count. Every cell is the same
item, the same rule sentence, the same shuffled fact block; the only thing that changes between two
cells of one item is the integer j. Depth is therefore isolated from input load inside one item,
without the band matching round 50 had to do across items.

  gold   the entity reached from the query source by following direct links for exactly j steps,
         computed by an independent BFS in this file, never read from the generator's label
  NONE   the two negative classes: j = k + 1 (the links run out one step past the end of the path)
         and a dead-end source (a path tail asked for one step)
  tier   controls_invalid if the NONE controls fail; else name_space_ceiling_at_or_below_48 if the
         deep in-band cells fall to at most 1 of 4; else name_space_no_ceiling_in_range; else
         unresolved. The tier rule and every band below are frozen in gate.json before the first
         prompt.

Caps are contractual: 40 prompts for the round, max_tokens at most 2,048, temperature 0.0, no
metered or hosted provider. No endpoint value (base URL, model id, key) is ever written: artifacts
carry a one-way digest of the serving id and every string passes the sanitizer first.

Usage:
  name_depth_probe.py --selftest
  name_depth_probe.py --gate        (freeze gate.json, no endpoint call)
  name_depth_probe.py --dry-run     (the dispatch plan and prompt digests, no endpoint call)
  NIGHTLY_BASE_URL=... NIGHTLY_MODEL_ID=... NIGHTLY_API_KEY=... name_depth_probe.py --run
  name_depth_probe.py --rescore     (rebuild gate.json + summary.json from raw.jsonl, no endpoint)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_REPO, "generators"))

import ladders  # noqa: E402

FAMILY = "ladders"
SEED_BASE = 20261005          # round 51's seed base, so the items are the same items
SCAN = 400
MAX_TOKENS = 2048             # protocol cap: no requested cap may exceed it
CALL_CAP = 40
TIMEOUT_S = 600
DISPATCH_BUDGET_S = 1800      # wall-clock guard on the dispatch phase
MAX_RETRIES_TOTAL = 4
NONE_GOLD = "NONE"
GATE_SCHEMA = "round55-gate-v1"

# The certified deep item: round 51's load-floor k = 48 item that rounds 51, 53 and 54 dispatched
# byte-identically. Its archived yes/no prompt digest is re-derived before dispatch from the same
# rule and fact block, so the name-form prompt used here provably carries the same fact bytes.
ARCHIVED_K48 = {"seed": 116261051, "yesno_digest16": "068bc6a1fb0620fb"}

# Dispatch plan: (label, level, seed index within the load-floor list, j, cap, kind).
# kind: name = the depth query; off_end = j one past the path (gold NONE);
#       dead_end = a path tail asked for one step (gold NONE); dup = re-dispatch (#100).
PLAN = [
    # shallow anchor, round 6's archived seed family: the answer space must work somewhere first
    ("L8_j1", 8, 0, 1, MAX_TOKENS, "name"),
    ("L8_j2", 8, 0, 2, MAX_TOKENS, "name"),
    ("L8_j4", 8, 0, 4, MAX_TOKENS, "name"),
    ("L8_j8", 8, 0, 8, MAX_TOKENS, "name"),
    ("L8_offend", 8, 0, 9, MAX_TOKENS, "off_end"),
    # NONE controls next: they gate whether any name hit means anything
    ("L32A_deadend", 32, 0, 1, MAX_TOKENS, "dead_end"),
    ("L48_deadend", 48, 0, 1, MAX_TOKENS, "dead_end"),
    # mid depth at byte-identical load, one item
    ("L16_j2", 16, 0, 2, MAX_TOKENS, "name"),
    ("L16_j8", 16, 0, 8, MAX_TOKENS, "name"),
    ("L16_j16", 16, 0, 16, MAX_TOKENS, "name"),
    ("L16_offend", 16, 0, 17, MAX_TOKENS, "off_end"),
    ("L32A_j2", 32, 0, 2, MAX_TOKENS, "name"),
    ("L32A_j8", 32, 0, 8, MAX_TOKENS, "name"),
    ("L32A_j16", 32, 0, 16, MAX_TOKENS, "name"),
    ("L32A_j24", 32, 0, 24, MAX_TOKENS, "name"),
    ("L32B_j8", 32, 1, 8, MAX_TOKENS, "name"),
    ("L48_j2", 48, 0, 2, MAX_TOKENS, "name"),
    ("L48_j8", 48, 0, 8, MAX_TOKENS, "name"),
    ("L48_j16", 48, 0, 16, MAX_TOKENS, "name"),
    ("L48_j32", 48, 0, 32, MAX_TOKENS, "name"),
    # the deep cells, last: a cutoff costs the top of the curve, not its gates
    ("L32A_j32", 32, 0, 32, MAX_TOKENS, "name"),
    ("L32A_offend", 32, 0, 33, MAX_TOKENS, "off_end"),
    ("L32B_j32", 32, 1, 32, MAX_TOKENS, "name"),
    ("L32B_offend", 32, 1, 33, MAX_TOKENS, "off_end"),
    ("L48_j48", 48, 0, 48, MAX_TOKENS, "name"),
    ("L48_offend", 48, 0, 49, MAX_TOKENS, "off_end"),
    # budget rung on the deepest query: does a one-token answer space still get censored?
    ("L48_j48_c256", 48, 0, 48, 256, "name"),
    # issue #100 self-agreement: byte-identical re-dispatch of two deep cells
    ("L32A_j32_dup", 32, 0, 32, MAX_TOKENS, "dup"),
    ("L48_j48_dup", 48, 0, 48, MAX_TOKENS, "dup"),
]
DEEP_CELLS = ("L16_j16", "L32A_j32", "L32B_j32", "L48_j48")
SHALLOW_CELLS = ("L8_j1", "L8_j2", "L8_j4", "L8_j8")
DUP_PAIRS = (("L32A_j32", "L32A_j32_dup"), ("L48_j48", "L48_j48_dup"))

CENSUS_PROMPT = ("Rule: for all x, y, z: if x precedes y and y precedes z, then x precedes z. "
                 "Facts: alby precedes birch. birch precedes cobin. Question: does alby precedes "
                 "cobin? Answer with exactly one word: yes or no.")


# ------------------------------------------------------------------ item and gold machinery

_SERIES: dict = {}


def series(level: int) -> list:
    if level not in _SERIES:
        _SERIES[level] = ladders.generate_items(level, SCAN, SEED_BASE)
    return _SERIES[level]


def load_floor(level: int) -> list:
    """The items whose fact count is 2 * level: exactly two chains, the smallest load in the
    corpus (issue #129). Deterministic in the seed base, so no selection happens at run time."""
    return [it for it in series(level) if len(it["facts"]) == 2 * level]


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
    """The tail of the path that does NOT contain src: matched pseudo-gold for row C6."""
    adj = adjacency(item)
    tails = [e for e in {t for _, _, t in item["facts"]} if e not in adj]
    own = terminal_at(item, src, item["level"])
    cands = [t for t in sorted(tails) if t != own]
    assert len(cands) == 1, ("expected one other tail", tails)
    return cands[0]


def item_for(level: int, index: int) -> dict:
    lf = load_floor(level)
    assert index < len(lf), f"level {level} has only {len(lf)} load-floor items"
    item = lf[index]
    check_item(item)
    return item


# ------------------------------------------------------------------ prompts

def fact_block(item: dict) -> str:
    return "\n".join(f"{s} {r} {t}." for s, r, t in item["facts"])


def render_name(item: dict, src: str, j: int) -> str:
    return (f"{item['rule']}\nFacts:\n{fact_block(item)}\n\n"
            f"Task: start at {src} and follow the direct links for exactly {j} steps. "
            "Answer with exactly one entity name, or the single word NONE if the links run out "
            f"before {j} steps.")


def render_yesno(item: dict) -> str:
    """The round-6 / round-50 / round-51 template, byte-identical, used only to certify that the
    fact block this round dispatches is the archived one."""
    facts = fact_block(item)
    qs, qrel, qt = item["query"]
    return (f"{item['rule']}\nFacts:\n{facts}\n\n"
            f"Question: does {qs} {qrel} {qt}?\n"
            "Answer with exactly one word: yes or no.")


def prompt_digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def plan_prompts() -> list:
    """Expand PLAN into records carrying prompt, gold and source, before any endpoint call."""
    out = []
    for label, level, index, j, cap, kind in PLAN:
        item = item_for(level, index)
        qs = item["query"][0]
        if kind == "dead_end":
            adj = adjacency(item)
            src = sorted(t for t in {t for _, _, t in item["facts"]} if t not in adj)[0]
        else:
            src = qs
        gold = terminal_at(item, src, j)
        gold = NONE_GOLD if gold is None else gold
        assert (gold == NONE_GOLD) == (kind in ("off_end", "dead_end")), (label, gold, kind)
        prompt = render_name(item, src, j)
        own = terminal_at(item, src, item["level"])
        pseudo = other_tail(item, src) if own is not None else ""
        out.append({"label": label, "level": level, "index": index, "seed": item["seed"],
                    "src": src, "j": j,
                    "cap": cap, "kind": kind, "gold": gold, "prompt": prompt,
                    "pseudo_gold": pseudo, "n_facts": len(item["facts"]),
                    "prompt_sha256": prompt_digest(prompt)})
    return out


# ------------------------------------------------------------------ sanitizer

_SECRET_PATTERNS = [
    re.compile(r"https?://\S+"),
    re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d+)?\b"),
    re.compile(r"/(?:root|home|mnt|media|run/user)/\S+"),
]


def sanitize(text, limit: int = 4000) -> str:
    """Strip anything the public-only rule forbids from model output before it is written down."""
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


def vocab_of(item: dict) -> set:
    words = set()
    for s, _, t in item["facts"]:
        words.add(s)
        words.add(t)
    return words


def declared_answer(content: str, vocab: set):
    """The last entity name in the visible answer field, else the NONE sentinel, else undetermined.
    An empty answer field is not a delivery: on this deployment shape the reasoning channel
    precedes it and can consume the whole budget."""
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

def gate_spec() -> dict:
    return {
        "schema": GATE_SCHEMA,
        "question": ("On a flash-next-class deployment, with the prompt bytes fixed and only the "
                     "step count j moved inside one load-floor ladder item, does a one-of-many "
                     "entity-name answer space (a) deliver correct terminals at shallow j where no "
                     "constant rule and no connectivity shortcut could, (b) hold to j = k on the "
                     "certified k = 48 item, (c) refuse correctly when the links run out, and (d) "
                     "leave a trace signal that passes a matched-name provenance control?"),
        "criteria": {
            "C1_shallow_name_competence": {
                "statement": "correct declared terminal on L8_j1, L8_j2, L8_j4, L8_j8 is at least 3 of 4",
                "threshold": "3/4"},
            "C2_none_controls_honest": {
                "statement": "correct NONE on the seven NONE-gold calls (five off-end, two dead-end) is at least 6 of 7",
                "threshold": "6/7"},
            "C3_deep_cells": {
                "statement": ("correct on the four deep in-band cells L16_j16, L32A_j32, L32B_j32, "
                              "L48_j48: ceiling if at most 1 of 4, no ceiling if at least 3 of 4"),
                "threshold": "1/4 ceiling, 3/4 no ceiling"},
            "C4_delivery_split": {
                "statement": ("delivery rate at j at most 8 minus delivery rate at j at least 24, "
                              "name cells only: a drop of 0.25 or more is a delivery-bound loss"),
                "threshold": "0.25"},
            "C5_self_agreement": {
                "statement": "both re-dispatch pairs agree on the declared name and completion tokens",
                "threshold": "2/2"},
            "C6_trace_provenance": {
                "statement": ("among undelivered name-gold records, gold-terminal-in-trace minus "
                              "pseudo-gold-in-trace is at least 0.50, else the trace readout is refused"),
                "threshold": "0.50"},
        },
        "tier_rule": ("controls_invalid if C2 below 6/7; else name_space_ceiling_at_or_below_48 if "
                      "C1 passes and C3 is a ceiling; else name_space_no_ceiling_in_range if C1 "
                      "passes and C3 is no ceiling; else unresolved"),
        "cells": [{"label": p["label"], "level": p["level"], "seed": p["seed"], "j": p["j"],
                   "cap": p["cap"], "kind": p["kind"], "gold": p["gold"],
                   "prompt_sha256": p["prompt_sha256"]} for p in plan_prompts()],
        "dispatch": {"planned_calls": len(PLAN), "call_cap": CALL_CAP,
                     "temperature": 0.0, "max_tokens_cap": MAX_TOKENS,
                     "dispatch_budget_s": DISPATCH_BUDGET_S,
                     "archived_k48_certification": ARCHIVED_K48},
    }


def gate_blob(spec: dict) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()


def score_records(records: list, spec: dict) -> dict:
    by = {r["label"]: r for r in records}
    out = {}
    c1 = [by[l]["correct"] for l in SHALLOW_CELLS if l in by]
    out["C1"] = {"correct": sum(1 for c in c1 if c), "n": len(c1),
                 "pass": len(c1) == 4 and sum(1 for c in c1 if c) >= 3}
    none_rows = [r for r in records if r["gold"] == NONE_GOLD]
    out["C2"] = {"correct": sum(1 for r in none_rows if r["correct"]), "n": len(none_rows),
                 "pass": len(none_rows) >= 7 and sum(1 for r in none_rows if r["correct"]) >= 6}
    deep = [by[l]["correct"] for l in DEEP_CELLS if l in by]
    n_ok = sum(1 for c in deep if c)
    if len(deep) < 4:
        verdict = "insufficient"
    elif n_ok <= 1:
        verdict = "ceiling"
    elif n_ok >= 3:
        verdict = "no_ceiling"
    else:
        verdict = "ambiguous"
    out["C3"] = {"correct": n_ok, "n": len(deep), "verdict": verdict}
    sh = [r for r in records if r["kind"] in ("name", "dup") and r["j"] <= 8]
    dp = [r for r in records if r["kind"] in ("name", "dup") and r["j"] >= 24]

    def rate(rows):
        return round(sum(1 for r in rows if r["delivered"]) / len(rows), 4) if rows else None
    r_sh, r_dp = rate(sh), rate(dp)
    out["C4"] = {"delivery_shallow": r_sh, "delivery_deep": r_dp,
                 "drop": (round(r_sh - r_dp, 4) if r_sh is not None and r_dp is not None else None),
                 "delivery_bound": (r_sh is not None and r_dp is not None and r_sh - r_dp >= 0.25)}
    agree = []
    for a, b in DUP_PAIRS:
        if a in by and b in by:
            agree.append({"pair": [a, b],
                          "name_agrees": by[a]["declared"] == by[b]["declared"],
                          "tokens_agree": by[a]["completion_tokens"] == by[b]["completion_tokens"]})
    out["C5"] = {"pairs": agree, "name_agreement": sum(1 for x in agree if x["name_agrees"]),
                 "pass": len(agree) == 2 and all(x["name_agrees"] for x in agree)}
    und = [r for r in records if r["kind"] in ("name",) and not r["delivered"] and r["trace_chars"]]
    if und:
        g = sum(1 for r in und if r["gold_in_trace"])
        p = sum(1 for r in und if r["pseudo_in_trace"])
        gap = round(g / len(und) - p / len(und), 4)
        out["C6"] = {"n": len(und), "gold_rate": round(g / len(und), 4),
                     "pseudo_rate": round(p / len(und), 4), "gap": gap,
                     "admissible": gap >= 0.50,
                     "pass": gap >= 0.50}
    else:
        out["C6"] = {"n": 0, "gold_rate": None, "pseudo_rate": None, "gap": None,
                     "admissible": False, "pass": False}
    if not out["C2"]["pass"]:
        tier = "controls_invalid"
    elif out["C1"]["pass"] and out["C3"]["verdict"] == "ceiling":
        tier = "name_space_ceiling_at_or_below_48"
    elif out["C1"]["pass"] and out["C3"]["verdict"] == "no_ceiling":
        tier = "name_space_no_ceiling_in_range"
    else:
        tier = "unresolved"
    flags = []
    if out["C4"]["delivery_bound"]:
        flags.append("delivery_bound_loss")
    if out["C6"]["n"] and not out["C6"]["admissible"]:
        flags.append("trace_provenance_refused")
    if out["C5"]["name_agreement"] < len(agree):
        flags.append("self_agreement_split")
    return {"tier": tier, "flags": flags, "criteria": out}


# ------------------------------------------------------------------ io

def write_jsonl(path: str, rows: list) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def read_jsonl(path: str) -> list:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


_GATE_BLOB: str = ""


def current_blob() -> str:
    """The frozen gate blob, computed once per process from the deterministic plan."""
    global _GATE_BLOB
    if not _GATE_BLOB:
        _GATE_BLOB = gate_blob(gate_spec())
    return _GATE_BLOB


def score_record(spec_row: dict, resp: dict, item: dict, error: str = "") -> dict:
    message = resp.get("message", {}) if resp else {}
    content = sanitize(message.get("content"), 2000)
    trace, fields, reasoning_field = trace_of(message)
    trace = sanitize(trace)
    vocab = vocab_of(item)
    declared, delivered = declared_answer(content, vocab)
    gold = spec_row["gold"]
    correct = (declared == gold) if delivered else None
    rec = {"label": spec_row["label"], "kind": spec_row["kind"], "level": spec_row["level"],
           "seed": spec_row["seed"], "src": spec_row["src"], "j": spec_row["j"],
           "cap": spec_row["cap"], "gold": gold, "pseudo_gold": spec_row["pseudo_gold"],
           "prompt_sha256": spec_row["prompt_sha256"], "prompt_chars": len(spec_row["prompt"]),
           "n_facts": spec_row["n_facts"], "content": content, "content_chars": len(content),
           "delivered": delivered, "declared": declared, "correct": correct,
           "trace": trace, "trace_chars": len(trace),
           "gold_in_trace": gold != NONE_GOLD and gold in trace,
           "pseudo_in_trace": bool(spec_row["pseudo_gold"]) and spec_row["pseudo_gold"] in trace,
           "census": {"fields": fields, "reasoning_field": reasoning_field},
           "finish_reason": resp.get("finish_reason") if resp else None,
           "completion_tokens": resp.get("completion_tokens") if resp else None,
           "prompt_tokens": resp.get("prompt_tokens") if resp else None,
           "wall_s": resp.get("wall_s") if resp else None,
           "model_digest": model_digest(), "gate": current_blob()}
    if error:
        rec["transport_error"] = error
    return rec


# ------------------------------------------------------------------ selftest

def selftest() -> None:
    checks = 0

    def ok(cond, msg):
        nonlocal checks
        checks += 1
        assert cond, f"selftest failed: {msg}"

    # 1. determinism: the shipped series re-derives byte-identically from the seed
    a = [ladders.item_jsonl(x) for x in ladders.generate_items(8, 5, SEED_BASE)]
    b = [ladders.item_jsonl(x) for x in ladders.generate_items(8, 5, SEED_BASE)]
    ok(a == b, "series not deterministic")

    # 2. the archived k = 48 certification really holds on this checkout
    item = item_for(48, 0)
    ok(item["seed"] == ARCHIVED_K48["seed"], "certified seed moved")
    ok(prompt_digest(render_yesno(item))[:16] == ARCHIVED_K48["yesno_digest16"],
       "reconstructed yes/no prompt digest does not match the archived round 51/53/54 record")

    # 3. solver arithmetic on a hand-built item, independent of the generator
    hand = {"level": 3, "rule": "R", "facts": [["a", "precedes", "b"], ["b", "precedes", "c"],
                                               ["c", "precedes", "d"], ["p", "precedes", "q"],
                                               ["q", "precedes", "r"], ["r", "precedes", "s"]],
            "query": ["a", "precedes", "d"]}
    ok(terminal_at(hand, "a", 1) == "b", "one step")
    ok(terminal_at(hand, "a", 3) == "d", "three steps")
    ok(terminal_at(hand, "a", 4) is None, "one past the end is None")
    ok(terminal_at(hand, "zz", 1) is None, "absent source is None")
    ok(other_tail(hand, "a") == "s", "matched pseudo-gold is the other tail")

    # 4. scorer arithmetic: perfect, flipped, and the constant-name baseline
    vocab = {"glag", "quonk", "thrend"}
    ok(declared_answer("thrend", vocab) == ("thrend", True), "plain name")
    ok(declared_answer("NONE", vocab) == (NONE_GOLD, True), "plain none")
    ok(declared_answer("", vocab) == (None, False), "empty is not a delivery")
    ok(declared_answer("The chain ends at thrend.", vocab) == ("thrend", True), "name in prose")
    ok(declared_answer("glag then thrend", vocab) == ("thrend", True), "last name wins")
    ok(declared_answer("I cannot say", vocab) == (None, True), "delivered but undetermined")
    constant = declared_answer("thrend", vocab)
    ok(constant != ("glag", True), "a constant name cannot score on both classes")

    # 5. planted negative: an off-by-one gold is scored wrong, so accuracy means the stated depth
    spec = {"label": "x", "kind": "name", "level": 8, "seed": 1, "src": "glag", "j": 4,
            "cap": 2048, "gold": "thrend", "pseudo_gold": "quonk", "pseudo_gold": "quonk",
            "prompt_sha256": "0" * 64, "prompt": "p", "n_facts": 16}
    resp = {"message": {"content": "quonk", "reasoning_content": "walked 4 hops to thrend"},
            "finish_reason": "stop", "completion_tokens": 12, "prompt_tokens": 5, "wall_s": 0.1}
    rec = score_record(spec, resp, {"facts": [["glag", "precedes", "thrend"],
                                              ["quonk", "precedes", "x"]]}, "")
    ok(rec["correct"] is False, "planted off-by-one must be scored wrong")
    ok(rec["gold_in_trace"] is True, "gold containment in trace")
    ok(rec["census"]["reasoning_field"] == "reasoning_content", "census merge rule")

    # 6. planted negative: a zero-trace record must report an empty reasoning field, not reason
    resp2 = {"message": {"content": "thrend", "reasoning": ""}, "finish_reason": "stop",
             "completion_tokens": 3, "prompt_tokens": 5, "wall_s": 0.1}
    rec2 = score_record(spec, resp2, {"facts": [["glag", "precedes", "thrend"]]}, "")
    ok(rec2["census"]["reasoning_field"] == "" and rec2["trace_chars"] == 0, "zero-trace shape")

    # 7. planted negative: an empty answer field at the cap is a non-delivery, not a wrong answer
    resp3 = {"message": {"content": "", "reasoning_content": "x" * 500}, "finish_reason": "length",
             "completion_tokens": 2048, "prompt_tokens": 5, "wall_s": 0.1}
    rec3 = score_record(spec, resp3, {"facts": [["glag", "precedes", "thrend"]]}, "")
    ok(rec3["delivered"] is False and rec3["correct"] is None, "censored is not wrong")

    # 7b. planted negative: an empty pseudo-gold must never read as present in the trace
    rec3b = score_record(dict(spec, pseudo_gold=""),
                         {"message": {"content": "", "reasoning_content": "glag thrend quonk"},
                          "finish_reason": "length", "completion_tokens": 2048,
                          "prompt_tokens": 5, "wall_s": 0.1},
                         {"facts": [["glag", "precedes", "thrend"]]}, "")
    ok(rec3b["pseudo_in_trace"] is False and rec3b["gold_in_trace"] is True,
       "empty pseudo-gold guard")

    # 8. sanitizer: no endpoint value, URL, address or path survives
    probe = ("see http://example.invalid/x and 198.51.100.7:8080 and /root/models/f.bin "
             + os.environ.get("NIGHTLY_MODEL_ID", "SENTINEL") * 2)
    s = sanitize(probe)
    ok("http" not in s and "198.51.100.7" not in s and "/root/" not in s, "sanitizer patterns")
    ok(os.environ.get("NIGHTLY_MODEL_ID", "") not in s or not os.environ.get("NIGHTLY_MODEL_ID"),
       "serving id must not survive the sanitizer")

    # 9. the plan is internally consistent: gold classes, caps, budget, digest uniqueness
    spec_full = gate_spec()
    rows = plan_prompts()
    ok(len(rows) == len(PLAN), "plan expanded")
    ok(len(rows) + 1 <= CALL_CAP, "plan plus the census call must sit inside the 40-call cap")
    ok(all(r["cap"] <= MAX_TOKENS for r in rows), "protocol token cap")
    groups: dict = {}
    for r in rows:
        groups.setdefault(r["prompt_sha256"], []).append(r["label"])
    redispatch = {"L32A_j32", "L32A_j32_dup", "L48_j48", "L48_j48_dup", "L48_j48_c256"}
    shared = {tuple(sorted(v)) for v in groups.values() if len(v) > 1}
    ok(all(set(g) <= redispatch for g in shared),
       f"an unintended pair of cells shares a prompt: {shared}")
    ok(len(groups) == len(rows) - 3, f"expected exactly three re-dispatches, got {len(groups)}")
    ok(sum(1 for r in rows if r["gold"] == NONE_GOLD) == 7, "seven NONE controls planned")
    ok(all(r["j"] <= r["level"] + 1 for r in rows), "no cell asks past the off-end probe")

    # 10. the tier rule itself: planted record sets must land on each tier
    fake = []
    for r in rows:
        fake.append({"label": r["label"], "kind": r["kind"], "j": r["j"], "gold": r["gold"],
                     "pseudo_gold": r["pseudo_gold"],
                     "delivered": True, "declared": r["gold"], "correct": True,
                     "completion_tokens": 100, "trace_chars": 0, "gold_in_trace": False,
                     "pseudo_in_trace": False})
    t = score_records(fake, spec_full)
    ok(t["tier"] == "name_space_no_ceiling_in_range", f"all-correct run must be no-ceiling: {t}")
    for row in fake:
        if row["label"] in DEEP_CELLS:
            row["declared"] = row["pseudo_gold"]
            row["correct"] = row["label"] not in ("L16_j16", "L32A_j32")
    t = score_records(fake, spec_full)
    ok(t["criteria"]["C3"]["verdict"] == "ambiguous" and t["tier"] == "unresolved",
       f"two of four deep cells wrong must read ambiguous: {t['criteria']['C3']}")
    for row in fake:
        if row["label"] in DEEP_CELLS:
            row["correct"] = row["label"] == "L48_j48"
    t = score_records(fake, spec_full)
    ok(t["tier"] == "name_space_ceiling_at_or_below_48", f"one deep hit must read as a ceiling: {t}")
    for row in fake:
        if row["gold"] == NONE_GOLD:
            row["correct"] = False
    t = score_records(fake, spec_full)
    ok(t["tier"] == "controls_invalid", "failed NONE controls must invalidate the tier")

    print(f"selftest ok: {checks} checks")


# ------------------------------------------------------------------ commands

def freeze_gate(path: str) -> dict:
    spec = gate_spec()
    blob = gate_blob(spec)
    spec["blob"] = blob
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return spec


def do_run(outdir: str) -> int:
    global _GATE_BLOB
    spec = freeze_gate(os.path.join(outdir, "gate.json"))
    _GATE_BLOB = spec["blob"]
    print("gate blob", spec["blob"])
    rows = plan_prompts()
    raw_path = os.path.join(outdir, "raw.jsonl")
    done = {}
    if os.path.exists(raw_path):
        done = {r["label"]: r for r in read_jsonl(raw_path)}
    records = list(done.values())
    fh = open(raw_path, "a", encoding="utf-8")
    retries = 0
    t_start = time.time()
    not_dispatched = []
    health = call(CENSUS_PROMPT, 256)
    trace, fields, reasoning_field = trace_of(health["message"])
    with open(os.path.join(outdir, "health.json"), "w", encoding="utf-8") as hj:
        json.dump({"fields": fields, "reasoning_field": reasoning_field,
                   "trace_chars": len(trace), "finish_reason": health["finish_reason"],
                   "completion_tokens": health["completion_tokens"],
                   "model_digest": model_digest()}, hj, indent=2, sort_keys=True)
    print(f"health: fields {fields} reasoning field {reasoning_field or 'none'}")
    for spec_row in rows:
        if spec_row["label"] in done:
            continue
        if time.time() - t_start > DISPATCH_BUDGET_S:
            not_dispatched.append(spec_row["label"])
            continue
        item = item_for(spec_row["level"], spec_row["index"])
        err = ""
        resp = None
        for attempt in (1, 2):
            try:
                resp = call(spec_row["prompt"], spec_row["cap"])
                break
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                err = type(exc).__name__
                retries += 1
                if attempt == 2 or retries > MAX_RETRIES_TOTAL:
                    resp = None
                else:
                    time.sleep(20)
        rec = score_record(spec_row, resp or {}, item, err)
        records.append(rec)
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
        print(f"{rec['label']:16s} j={rec['j']:<3d} tok={rec['completion_tokens']} "
              f"finish={rec['finish_reason']} declared={rec['declared']} correct={rec['correct']}")
    fh.close()
    records = read_jsonl(raw_path)
    scored = score_records(records, spec)
    scored["dispatch"] = {"wall_s": round(time.time() - t_start, 3), "planned": len(rows),
                          "dispatched": len(rows) - len(not_dispatched),
                          "not_dispatched": not_dispatched, "retries_used": retries,
                          "call_cap": CALL_CAP, "calibration_calls": 1}
    with open(os.path.join(outdir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(scored, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print("tier", scored["tier"], "flags", scored["flags"])
    return 0


def do_rescore(outdir: str) -> int:
    spec = json.load(open(os.path.join(outdir, "gate.json"), encoding="utf-8"))
    records = read_jsonl(os.path.join(outdir, "raw.jsonl"))
    scored = score_records(records, spec)
    with open(os.path.join(outdir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(scored, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print("tier", scored["tier"])
    print(json.dumps(scored["criteria"], indent=2, sort_keys=True))
    return 0


def main(argv: list) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--rescore", action="store_true")
    ap.add_argument("--outdir", default=_HERE)
    args = ap.parse_args(argv)
    if args.selftest:
        selftest()
        return 0
    if args.gate:
        spec = freeze_gate(os.path.join(args.outdir, "gate.json"))
        print("gate blob", spec["blob"], "cells", len(spec["cells"]))
        return 0
    if args.dry_run:
        spec = gate_spec()
        for row in plan_prompts():
            print(f"{row['label']:16s} level={row['level']:<3d} seed={row['seed']} "
                  f"j={row['j']:<3d} cap={row['cap']:<5d} gold={row['gold']:10s} "
                  f"facts={row['n_facts']} digest={row['prompt_sha256'][:16]}")
        print("planned calls", len(plan_prompts()), "of cap", CALL_CAP)
        print("gate blob (dry, not frozen)", gate_blob(spec))
        return 0
    if args.run:
        return do_run(args.outdir)
    if args.rescore:
        return do_rescore(args.outdir)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

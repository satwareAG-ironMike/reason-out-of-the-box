#!/usr/bin/env python3
"""Round 60 (2026-11-11 04:40): can the ladder traversal run without being written out?

Tracker issue #65. Question, frozen in `gate.json` before the first endpoint call:

    On one load-floor ladder item, with the fact block fixed and only the step count `j`
    and the output permission moved, does banning the written traversal (a) collapse
    terminal-name accuracy, (b) preserve it at a token cost that still grows with depth,
    or (c) preserve it at flat cost?

Why this question. Every depth number this program has placed on the ladder family is a
number from a free-writing instruction: the model may write the chain before it answers.
Round 6 (issue #71, artifacts `research/nightly-2026-10-16-0400/`) measured the cost of
that writing at about 80 completion tokens per hop; round 50
(`research/nightly-2026-11-06-0259/`, merged as #128) found that accuracy never turns
over while delivery does, and could not say whether the missing answers were missing
computation or missing surfacing; round 55 (issue #94's name-space answer space, PR #136)
delivered correct terminal names to `j = 32` and lost the `j = 48` cells to non-delivery.
Issue #71's standing ask is a named procedure that says which resource is scarce. The
direct test is to remove the writing and see what is left: if a correct name still comes
back with a one-word visible answer, the traversal did not need the output channel, and
no `d*` placed on output cost means what the study assumed it meant.

Design. Two arms on the same items, the same seeds and the same fact block; the ban arm's
prompt is the free arm's prompt plus one appended clause, so the pair is minimal by
construction and the selftest asserts it byte-wise:

  free  "Task: start at X and follow the direct links for exactly j steps. Answer with
         exactly one entity name, or the single word NONE if the links run out before j
         steps."   (round 55's template, byte-identical)
  ban   the same bytes + " Do not write out any intermediate entity name; answer with the
         single name only."

The answer space is one name out of the generator's 2,700-name pool, so neither a constant
rule nor the undirected-connectivity shortcut (issue #77) can produce it. NONE-gold cells
(`j` one past the path end, and one step past a path tail) gate the round: a model that
names an entity where the links have run out has not traversed anything.

Measures per record: declared name, correctness, `finish_reason`, server-reported
completion tokens, visible answer characters, and the reasoning-channel characters the
serving stack exposes separately (issue #105 census: `reasoning_content` if non-empty,
else `reasoning`, else empty). The cost contrast is the within-item slope of completion
tokens against `j` per arm.

Transport contract (issue #73): env-only endpoint (`NIGHTLY_BASE_URL`, `NIGHTLY_MODEL_ID`,
`NIGHTLY_API_KEY`, never written to an artifact), temperature 0, one retry per item inside
a global retry budget, records appended and fsynced one by one, `--resume` reuses a record
only after re-deriving the prompt it would have sent. Caps are contractual: 40 prompts,
`max_tokens <= 2048`, free scholarly APIs only upstream of this file.

Usage:
  internalized_traversal_probe.py --selftest
  internalized_traversal_probe.py --dry-run
  internalized_traversal_probe.py --freeze-gate OUTDIR
  internalized_traversal_probe.py --run OUTDIR [--resume]
  internalized_traversal_probe.py --rescore OUTDIR
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from collections import deque

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_REPO, "generators"))

import ladders  # noqa: E402

FAMILY = "ladders"
SEED_BASE = 20261005          # round 51/55's seed base, so the items are the same items
SCAN = 400                    # items scanned per level before the load-floor filter
MAX_TOKENS = 2048             # protocol cap: no requested cap may exceed it
CALL_CAP = 40                 # protocol cap on prompts per round
TIMEOUT_S = 600
DISPATCH_BUDGET_S = 1500      # wall-clock guard on the dispatch phase
MAX_RETRIES_TOTAL = 4
RETRY_BACKOFF_S = 20
NONE_GOLD = "NONE"
GATE_SCHEMA = "round60-gate-v1"
BAN_CLAUSE = (" Do not write out any intermediate entity name; answer with the single "
              "name only.")

# A-priori cost threshold, fixed before dispatch: round 6 measured the free-writing cost
# law at 80 completion tokens per hop on this family (issue #71). One fifth of that law,
# 10 tokens per hop, is the line between "the ban moved the cost into the hidden channel"
# and "the traversal stopped costing tokens per hop".
GROWTH_TOKENS_PER_HOP = 10.0

# The certified deep item: the load-floor k = 48 item rounds 51, 53 and 54 dispatched
# byte-identically. Its archived yes/no prompt digest is re-derived before dispatch from
# the same rule and fact block, so the name-form prompts used here provably carry the same
# fact bytes as the archived ladder record.
ARCHIVED_K48 = {"seed": 116261051, "yesno_digest16": "068bc6a1fb0620fb"}

# Round 55's load-floor item selection (same seed base, same rule): pinned so that a
# generator change moves the items and this round refuses instead of silently re-selecting.
PINNED_SEEDS = {8: 36261005, 16: 52261033, 32: 84261011, 48: 116261051}

# Dispatch plan: (label, level, index within the load-floor list, j, mode, kind).
# mode: free = round 55's template, ban = that template plus BAN_CLAUSE.
# kind: name = depth query; off_end = j one past the path (gold NONE);
#       dead_end = a path tail asked for one step (gold NONE); dup = re-dispatch (#100).
PLAN = [
    # 1. shallow anchors first: the ban arm must be able to answer at all before any deep
    # non-delivery can be read as a ceiling
    ("F_L8_j1", 8, 0, 1, "free", "name"),
    ("B_L8_j1", 8, 0, 1, "ban", "name"),
    ("F_L8_j2", 8, 0, 2, "free", "name"),
    ("B_L8_j2", 8, 0, 2, "ban", "name"),
    ("F_L8_j8", 8, 0, 8, "free", "name"),
    ("B_L8_j8", 8, 0, 8, "ban", "name"),
    # 2. the ten NONE controls next: a model that names an entity where the links have run
    # out has not traversed anything, and nothing downstream means anything either
    ("F_L8_offend", 8, 0, 9, "free", "off_end"),
    ("B_L8_offend", 8, 0, 9, "ban", "off_end"),
    ("F_L16_offend", 16, 0, 17, "free", "off_end"),
    ("B_L16_offend", 16, 0, 17, "ban", "off_end"),
    ("F_L32A_offend", 32, 0, 33, "free", "off_end"),
    ("B_L32A_offend", 32, 0, 33, "ban", "off_end"),
    ("F_L48_offend", 48, 0, 49, "free", "off_end"),
    ("B_L48_offend", 48, 0, 49, "ban", "off_end"),
    ("F_L48_deadend", 48, 0, 1, "free", "dead_end"),
    ("B_L48_deadend", 48, 0, 1, "ban", "dead_end"),
    # 3. the primary contrast: the three matched deep pairs, before any budget cutoff can
    # take them (this is the row the round's question is about)
    ("F_L32A_j32", 32, 0, 32, "free", "name"),
    ("B_L32A_j32", 32, 0, 32, "ban", "name"),
    ("F_L48_j32", 48, 0, 32, "free", "name"),
    ("B_L48_j32", 48, 0, 32, "ban", "name"),
    ("F_L48_j48", 48, 0, 48, "free", "name"),
    ("B_L48_j48", 48, 0, 48, "ban", "name"),
    # 4. the shallow rungs of the cost-law fit on the same item as the deep cells
    ("F_L48_j8", 48, 0, 8, "free", "name"),
    ("B_L48_j8", 48, 0, 8, "ban", "name"),
    ("F_L48_j16", 48, 0, 16, "free", "name"),
    ("B_L48_j16", 48, 0, 16, "ban", "name"),
    # 5. mid-depth rungs on the two mid items: depth profile, droppable under a cutoff
    ("F_L16_j2", 16, 0, 2, "free", "name"),
    ("B_L16_j2", 16, 0, 2, "ban", "name"),
    ("F_L16_j16", 16, 0, 16, "free", "name"),
    ("B_L16_j16", 16, 0, 16, "ban", "name"),
    ("F_L32A_j2", 32, 0, 2, "free", "name"),
    ("B_L32A_j2", 32, 0, 2, "ban", "name"),
    ("F_L32A_j16", 32, 0, 16, "free", "name"),
    ("B_L32A_j16", 32, 0, 16, "ban", "name"),
    # 6. issue #100 self-agreement: byte-identical re-dispatch of two deep cells
    ("F_L32A_j32_dup", 32, 0, 32, "free", "dup"),
    ("B_L48_j32_dup", 48, 0, 32, "ban", "dup"),
]

DEEP_CELLS = ("F_L32A_j32", "B_L32A_j32", "F_L48_j32", "B_L48_j32", "F_L48_j48", "B_L48_j48")
FREE_DEEP = ("F_L32A_j32", "F_L48_j32", "F_L48_j48")
BAN_DEEP = ("B_L32A_j32", "B_L48_j32", "B_L48_j48")
BAN_SHALLOW = ("B_L8_j1", "B_L8_j2", "B_L8_j8")
DUP_PAIRS = (("F_L32A_j32", "F_L32A_j32_dup"), ("B_L48_j32", "B_L48_j32_dup"))


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


def bfs_terminal(item: dict, src: str, steps: int):
    """Second, independent solver (BFS with depth bookkeeping) used only by the selftest to
    cross-check `terminal_at` rather than mirroring it."""
    graph: dict = {}
    for s, _, t in item["facts"]:
        graph.setdefault(s, []).append(t)
    dist = {src: 0}
    q = deque([src])
    while q:
        u = q.popleft()
        for v in graph.get(u, ()):
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    for node, d in dist.items():
        if d == steps:
            return node
    return None


def other_tail(item: dict, src: str) -> str:
    """The tail of the path that does NOT contain src: matched pseudo-gold for the trace row."""
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
    assert item["seed"] == PINNED_SEEDS[level], (
        f"level {level} load-floor item {index} moved: seed {item['seed']} != "
        f"{PINNED_SEEDS[level]}")
    return item


# ------------------------------------------------------------------ prompts

def fact_block(item: dict) -> str:
    return "\n".join(f"{s} {r} {t}." for s, r, t in item["facts"])


def render_free(item: dict, src: str, j: int) -> str:
    """Round 55's template, byte-identical, so the free arm is a re-fire and not a new task."""
    return (f"{item['rule']}\nFacts:\n{fact_block(item)}\n\n"
            f"Task: start at {src} and follow the direct links for exactly {j} steps. "
            "Answer with exactly one entity name, or the single word NONE if the links run out "
            f"before {j} steps.")


def render_ban(item: dict, src: str, j: int) -> str:
    """The ban arm is the free arm plus one clause: the pair is minimal by construction."""
    return render_free(item, src, j) + BAN_CLAUSE


def render(item: dict, src: str, j: int, mode: str) -> str:
    if mode == "free":
        return render_free(item, src, j)
    if mode == "ban":
        return render_ban(item, src, j)
    raise AssertionError(f"unknown mode {mode}")


def render_yesno(item: dict) -> str:
    """The round-6 / round-51 template, byte-identical, used only to certify that the fact
    block this round dispatches is the archived one."""
    qs, qrel, qt = item["query"]
    return (f"{item['rule']}\nFacts:\n{fact_block(item)}\n\n"
            f"Question: does {qs} {qrel} {qt}?\n"
            "Answer with exactly one word: yes or no.")


def prompt_digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def dead_end_source(item: dict) -> str:
    adj = adjacency(item)
    return sorted(t for t in {t for _, _, t in item["facts"]} if t not in adj)[0]


def plan_prompts() -> list:
    """Expand PLAN into records carrying prompt, gold and arm, before any endpoint call."""
    out = []
    for label, level, index, j, mode, kind in PLAN:
        item = item_for(level, index)
        src = dead_end_source(item) if kind == "dead_end" else item["query"][0]
        gold = terminal_at(item, src, j)
        gold = NONE_GOLD if gold is None else gold
        assert (gold == NONE_GOLD) == (kind in ("off_end", "dead_end")), (label, gold, kind)
        own = terminal_at(item, src, item["level"])
        out.append({"label": label, "level": level, "index": index, "mode": mode,
                    "seed": item["seed"], "src": src, "j": j, "kind": kind,
                    "cap": MAX_TOKENS, "gold": gold, "prompt": render(item, src, j, mode),
                    "free_prompt": render_free(item, src, j),
                    "pseudo_gold": other_tail(item, src) if own is not None else "",
                    "n_facts": len(item["facts"]),
                    "prompt_sha256": prompt_digest(render(item, src, j, mode))})
    labels = [r["label"] for r in out]
    assert len(labels) == len(set(labels)), "duplicate plan label"
    for r in out:
        if r["mode"] == "ban":
            assert r["prompt"] == r["free_prompt"] + BAN_CLAUSE, r["label"]
    return out


# ------------------------------------------------------------------ sanitizer

_SECRET_PATTERNS = [
    re.compile(r"https?://\S+"),
    re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d+)?\b"),
    re.compile(r"/(?:root|home|mnt|media|run/user)/\S+"),
]


def sanitize(text, limit: int = 4000) -> str:
    """Strip anything the public-only rule forbids from model output before it is written."""
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
    """The last entity name in the visible answer field, else the NONE sentinel, else
    undetermined. An empty visible field is not a delivery: on this deployment shape the
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

def gate_spec() -> dict:
    return {
        "schema": GATE_SCHEMA,
        "question": ("On one load-floor ladder item, with the fact block fixed and only the step "
                     "count j and the output permission moved, does banning the written traversal "
                     "(a) collapse terminal-name accuracy, (b) preserve it at a token cost that "
                     "still grows with depth, or (c) preserve it at flat cost?"),
        "arms": {"free": "round 55's template, byte-identical, chain may be written",
                 "ban": "the same bytes plus one clause banning written intermediate names"},
        "criteria": {
            "C1_ban_shallow_competence": {
                "statement": ("the ban arm declares the correct terminal on at least 2 of 3 of "
                              "B_L8_j1, B_L8_j2, B_L8_j8"),
                "threshold": "2/3"},
            "C2_none_controls_honest": {
                "statement": ("at least 9 of the 10 NONE-gold calls declare NONE, and no "
                              "NONE-gold call declares an entity name from its own item"),
                "threshold": "9/10 and 0 name-on-NONE"},
            "C3_matched_deep": {
                "statement": ("correct deliveries over the three matched deep pairs (j = 32 on "
                              "L32A, j = 32 and j = 48 on L48), free against ban"),
                "threshold": "reported as a 3/3 pair, no band"},
            "C4_cost_law": {
                "statement": ("least-squares slope of completion tokens against j on the four "
                              "L48 depth rungs, per arm; growth if slope >= 10 tokens per hop "
                              "(one fifth of round 6's 80 tokens per hop free-writing law)"),
                "threshold": "10 tokens/hop"},
            "C5_self_agreement": {
                "statement": "both re-dispatch pairs agree on the declared name and on tokens",
                "threshold": "2/2"},
            "C6_trace_provenance": {
                "statement": ("among undelivered name-gold records, gold-terminal-in-trace minus "
                              "pseudo-gold-in-trace is at least 0.50, else the trace readout is "
                              "refused"),
                "threshold": "0.50"},
        },
        "tier_rule": ("controls_invalid if C2 fails; else ban_not_followed if the ban arm's mean "
                      "visible answer length is at least half the free arm's on matched in-band "
                      "cells; else no_ceiling_both_modes if both arms deliver at least 2 of 3 "
                      "deep; else internalized_flat_cost if the ban arm delivers at least 2 of 3 "
                      "deep, the free arm at most 1 of 3, and the ban arm's C4 slope is below "
                      "10 tokens per hop; else cost_migrated_to_hidden_channel on the same "
                      "delivery split with a C4 slope at or above 10; else "
                      "externalized_chain_required if the free arm delivers at least 2 of 3 and "
                      "the ban arm at most 1 of 3; else unresolved"),
        "cells": [{"label": p["label"], "level": p["level"], "seed": p["seed"], "mode": p["mode"],
                   "j": p["j"], "kind": p["kind"], "gold": p["gold"],
                   "prompt_sha256": p["prompt_sha256"]} for p in plan_prompts()],
        "dispatch": {"planned_calls": len(PLAN), "call_cap": CALL_CAP, "temperature": 0.0,
                     "max_tokens_cap": MAX_TOKENS, "dispatch_budget_s": DISPATCH_BUDGET_S,
                     "growth_tokens_per_hop": GROWTH_TOKENS_PER_HOP,
                     "archived_k48_certification": ARCHIVED_K48},
    }


def gate_blob(spec: dict) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()


# ------------------------------------------------------------------ scoring

def least_squares_slope(xs: list, ys: list):
    """Slope of y on x, None when fewer than two distinct x values are present."""
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return None
    return round(sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / den, 4)


def score_records(records: list, spec: dict) -> dict:
    by = {r["label"]: r for r in records}
    out: dict = {}

    sh = [by[l]["correct"] for l in BAN_SHALLOW if l in by]
    out["C1"] = {"correct": sum(1 for c in sh if c), "n": len(sh),
                 "pass": len(sh) == 3 and sum(1 for c in sh if c) >= 2}

    none_rows = [r for r in records if r["gold"] == NONE_GOLD]
    correct_none = sum(1 for r in none_rows if r["declared"] == NONE_GOLD)
    name_on_none = sum(1 for r in none_rows if r["declared"] not in (None, NONE_GOLD))
    unresolved_none = sum(1 for r in none_rows
                          if r["declared"] is None or r["declared"] == "")
    out["C2"] = {"n": len(none_rows), "correct_none": correct_none,
                 "name_on_none": name_on_none, "unresolved": unresolved_none,
                 "pass": (len(none_rows) == 10 and correct_none >= 9 and name_on_none == 0)}

    free_deep = sum(1 for l in FREE_DEEP if l in by and by[l]["correct"])
    ban_deep = sum(1 for l in BAN_DEEP if l in by and by[l]["correct"])
    out["C3"] = {"free_deep_correct": free_deep, "ban_deep_correct": ban_deep,
                 "n_pairs": len(FREE_DEEP),
                 "pairs": [{"cell": f, "ban": b,
                            "free_correct": bool(by.get(f, {}).get("correct")),
                            "ban_correct": bool(by.get(b, {}).get("correct")),
                            "free_delivered": bool(by.get(f, {}).get("delivered")),
                            "ban_delivered": bool(by.get(b, {}).get("delivered"))}
                           for f, b in zip(FREE_DEEP, BAN_DEEP)]}

    def slope(mode: str):
        rows = [r for r in records
                if r["mode"] == mode and r["level"] == 48 and r["kind"] == "name"
                and r["completion_tokens"] is not None]
        return least_squares_slope([r["j"] for r in rows], [r["completion_tokens"] for r in rows])

    s_free, s_ban = slope("free"), slope("ban")
    out["C4"] = {"slope_free_tokens_per_hop": s_free, "slope_ban_tokens_per_hop": s_ban,
                 "growth_threshold": GROWTH_TOKENS_PER_HOP,
                 "ban_growth": (s_ban is not None and s_ban >= GROWTH_TOKENS_PER_HOP),
                 "free_growth": (s_free is not None and s_free >= GROWTH_TOKENS_PER_HOP)}

    agree = []
    for a, b in DUP_PAIRS:
        if a in by and b in by:
            agree.append({"pair": [a, b], "name_agrees": by[a]["declared"] == by[b]["declared"],
                          "tokens_agree": by[a]["completion_tokens"] == by[b]["completion_tokens"]})
    out["C5"] = {"pairs": agree, "name_agreement": sum(1 for x in agree if x["name_agrees"]),
                 "pass": len(agree) == 2 and all(x["name_agrees"] for x in agree)}

    und = [r for r in records if r["kind"] == "name" and not r["delivered"] and r["trace_chars"]]
    if und:
        g = sum(1 for r in und if r["gold_in_trace"])
        p = sum(1 for r in und if r["pseudo_in_trace"])
        gap = round(g / len(und) - p / len(und), 4)
        out["C6"] = {"n": len(und), "gold_rate": round(g / len(und), 4),
                     "pseudo_rate": round(p / len(und), 4), "gap": gap, "admissible": gap >= 0.50,
                     "pass": gap >= 0.50}
    else:
        out["C6"] = {"n": 0, "gold_rate": None, "pseudo_rate": None, "gap": None,
                     "admissible": False, "pass": False}

    inband = [r for r in records if r["kind"] in ("name", "dup")]
    vis_free = [r["content_chars"] for r in inband if r["mode"] == "free"]
    vis_ban = [r["content_chars"] for r in inband if r["mode"] == "ban"]
    mean_free = round(sum(vis_free) / len(vis_free), 2) if vis_free else None
    mean_ban = round(sum(vis_ban) / len(vis_ban), 2) if vis_ban else None
    ban_followed = (mean_free is not None and mean_ban is not None and mean_free > 0
                    and mean_ban < 0.5 * mean_free)

    tier = decide(out, ban_followed)
    flags = []
    if out["C1"]["correct"] < 2:
        flags.append("ban_shallow_competence_failed")
    if out["C2"]["name_on_none"]:
        flags.append("name_on_none")
    if out["C2"]["unresolved"]:
        flags.append("none_control_unresolved")
    if out["C5"]["name_agreement"] < len(agree):
        flags.append("self_agreement_split")
    if out["C6"]["n"] and not out["C6"]["admissible"]:
        flags.append("trace_provenance_refused")
    return {"tier": tier, "ban_followed": ban_followed,
            "visible_mean_free_chars": mean_free, "visible_mean_ban_chars": mean_ban,
            "flags": flags, "criteria": out}


def decide(c: dict, ban_followed: bool) -> str:
    """The registered tier rule, kept as a pure function so the selftest can plant inputs."""
    if not c["C2"]["pass"]:
        return "controls_invalid"
    if not ban_followed:
        return "ban_not_followed"
    f = c["C3"]["free_deep_correct"]
    b = c["C3"]["ban_deep_correct"]
    if f >= 2 and b >= 2:
        return "no_ceiling_both_modes"
    if b >= 2 and f <= 1:
        return ("cost_migrated_to_hidden_channel" if c["C4"]["ban_growth"]
                else "internalized_flat_cost")
    if f >= 2 and b <= 1:
        return "externalized_chain_required"
    return "unresolved"


# ------------------------------------------------------------------ io

def write_jsonl(path: str, rows: list) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())


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
    global _GATE_BLOB
    if not _GATE_BLOB:
        _GATE_BLOB = gate_blob(gate_spec())
    return _GATE_BLOB


def score_record(spec_row: dict, resp: dict, item: dict, error: str = "") -> dict:
    message = resp.get("message", {}) if resp else {}
    content = sanitize(message.get("content"), 2000)
    trace, fields, reasoning_field = trace_of(message)
    trace = sanitize(trace)
    declared, delivered = declared_answer(content, vocab_of(item))
    gold = spec_row["gold"]
    rec = {"label": spec_row["label"], "kind": spec_row["kind"], "mode": spec_row["mode"],
           "level": spec_row["level"], "seed": spec_row["seed"], "src": spec_row["src"],
           "j": spec_row["j"], "cap": spec_row["cap"], "gold": gold,
           "pseudo_gold": spec_row["pseudo_gold"], "prompt_sha256": spec_row["prompt_sha256"],
           "prompt_chars": len(spec_row["prompt"]), "n_facts": spec_row["n_facts"],
           "content": content, "content_chars": len(content), "delivered": delivered,
           "declared": declared, "correct": (declared == gold) if delivered else None,
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


# ------------------------------------------------------------------ certification

def certify_archived_k48() -> dict:
    """Rebuild the archived k = 48 yes/no prompt from the same fact block and compare its
    digest to the value rounds 51, 53 and 54 dispatched. Fail closed on a move."""
    item = item_for(48, 0)
    digest = prompt_digest(render_yesno(item))
    assert digest[:16] == ARCHIVED_K48["yesno_digest16"], (
        "archived certification refused: k = 48 fact block moved", digest[:16])
    return {"seed": item["seed"], "yesno_digest16": digest[:16], "n_facts": len(item["facts"])}


# ------------------------------------------------------------------ selftest

def selftest() -> None:
    checks = 0

    def ok(cond, msg):
        nonlocal checks
        checks += 1
        assert cond, f"selftest failed: {msg}"

    ok(CALL_CAP <= 40 and len(PLAN) <= CALL_CAP, "plan exceeds the 40-prompt protocol cap")
    ok(MAX_TOKENS <= 2048, "requested cap exceeds the 2048 protocol cap")
    ok(not any(r[4] not in ("free", "ban") for r in PLAN), "unknown arm in plan")

    # 1. determinism and the pinned item selection
    p1 = plan_prompts()
    p2 = plan_prompts()
    ok([r["prompt_sha256"] for r in p1] == [r["prompt_sha256"] for r in p2],
       "plan prompts are not deterministic")
    ok([r["seed"] for r in p1] == [r["seed"] for r in p2], "plan seeds are not deterministic")
    for lvl in PINNED_SEEDS:
        ok(item_for(lvl, 0)["seed"] == PINNED_SEEDS[lvl], f"pin moved at level {lvl}")
    ok(certify_archived_k48()["yesno_digest16"] == ARCHIVED_K48["yesno_digest16"],
       "archived k = 48 certification failed")

    # 2. the arms are a minimal pair: one appended clause and nothing else
    for r in p1:
        if r["mode"] == "ban":
            ok(r["prompt"] == r["free_prompt"] + BAN_CLAUSE, f"arm pair moved: {r['label']}")
            ok(r["prompt"].startswith(r["free_prompt"]), f"arm is not an append: {r['label']}")
        else:
            ok(r["prompt"] == r["free_prompt"], f"free arm drifted: {r['label']}")
    ok(BAN_CLAUSE not in p1[0]["free_prompt"], "ban clause leaked into the free template")

    # 3. gold solver against an independent BFS, on every plan row
    for r in p1:
        item = item_for(r["level"], r["index"])
        bfs = bfs_terminal(item, r["src"], r["j"])
        bfs = NONE_GOLD if bfs is None else bfs
        ok(bfs == r["gold"], f"solver disagreement at {r['label']}: {bfs} vs {r['gold']}")
    # one step past the end must be NONE, at every level used
    for lvl in PINNED_SEEDS:
        item = item_for(lvl, 0)
        src = item["query"][0]
        ok(terminal_at(item, src, lvl) is not None, f"path shorter than k at {lvl}")
        ok(terminal_at(item, src, lvl + 1) is None, f"path longer than k at {lvl}")

    # 4. gold-NONE structure: exactly ten NONE-gold controls, no more and no less
    none_rows = [r for r in p1 if r["gold"] == NONE_GOLD]
    ok(len(none_rows) == 10, f"expected 10 NONE controls, found {len(none_rows)}")
    ok(all(r["kind"] in ("off_end", "dead_end") for r in none_rows),
       "an in-band cell carries NONE gold")

    # 5. declared-answer extraction, planted negatives included
    item = item_for(8, 0)
    vocab = vocab_of(item)
    tail = terminal_at(item, item["query"][0], 8)
    ok(declared_answer(f"{tail}", vocab) == (tail, True), "bare name not read as a delivery")
    ok(declared_answer("NONE", vocab) == (NONE_GOLD, True), "NONE not read as a delivery")
    ok(declared_answer("", vocab) == (None, False), "empty field read as a delivery")
    ok(declared_answer("I cannot answer this.", vocab)[1] is True
       and declared_answer("I cannot answer this.", vocab)[0] is None,
       "refusal read as a name")
    ok(declared_answer(f"{tail} xyzzy", vocab) == (tail, True), "name among words not read")
    ok(declared_answer("zzznotanezzz", vocab) == (None, True), "out-of-vocab word read as name")

    # 6. the sanitizer: URL, IP, path and env value must not survive, in either channel
    dirty = ("see http://example.invalid/x 100.64.0.1 /root/models/f.bin "
             + os.environ.get("NIGHTLY_MODEL_ID", "sentinel"))
    clean = sanitize(dirty)
    ok("http" not in clean and "100.64" not in clean and "/root/" not in clean,
       "sanitizer let a forbidden token through")
    if os.environ.get("NIGHTLY_MODEL_ID"):
        ok(os.environ["NIGHTLY_MODEL_ID"] not in clean, "sanitizer let the serving id through")

    # 7. census merge rule (issue #105)
    tr, fields, src = trace_of({"role": "assistant", "content": "x", "reasoning_content": "rc"})
    ok(tr == "rc" and src == "reasoning_content" and fields == ["content", "reasoning_content",
                                                                "role"], "census rule moved")
    tr, _, src = trace_of({"role": "assistant", "reasoning_content": "", "reasoning": "r"})
    ok(tr == "r" and src == "reasoning", "census fallback rule moved")
    tr, _, src = trace_of({"role": "assistant"})
    ok(tr == "" and src == "", "empty census rule moved")

    # 8. cost-law arithmetic: an exact linear set must return its slope
    ok(least_squares_slope([8, 16, 32, 48], [80, 160, 320, 480]) == 10.0,
       "slope arithmetic wrong")
    ok(least_squares_slope([8, 16, 32, 48], [100, 100, 100, 100]) == 0.0,
       "flat cost read as growth")
    ok(least_squares_slope([8], [100]) is None, "single-point slope must be None")

    # 9. tier rule, planted inputs: every tier must be reachable and the wrong ones refused
    def fake(free_deep, ban_deep, ban_growth, c2_pass=True, ban_followed=True):
        c = {"C2": {"pass": c2_pass}, "C3": {"free_deep_correct": free_deep,
                                             "ban_deep_correct": ban_deep},
             "C4": {"ban_growth": ban_growth}}
        return decide(c, ban_followed)

    ok(fake(3, 3, True) == "no_ceiling_both_modes", "no-ceiling tier unreachable")
    ok(fake(0, 3, False) == "internalized_flat_cost", "internalized tier unreachable")
    ok(fake(1, 2, True) == "cost_migrated_to_hidden_channel", "migration tier unreachable")
    ok(fake(3, 0, False) == "externalized_chain_required", "externalized tier unreachable")
    ok(fake(1, 1, False) == "unresolved", "unresolved tier unreachable")
    ok(fake(3, 3, True, c2_pass=False) == "controls_invalid", "controls gate does not fire")
    ok(fake(3, 3, True, ban_followed=False) == "ban_not_followed", "ban-adherence gate fires late")

    # 10. planted defect in a scored record: a wrong name must not score correct, and a
    #     name on a NONE control must trip C2 (the defect round 55 was blocked on)
    spec = gate_spec()
    ok(len(spec["cells"]) == len(PLAN), "gate cell count moved")
    row = [c for c in p1 if c["label"] == "F_L8_j8"][0]
    resp = {"message": {"role": "assistant", "content": row["gold"],
                        "reasoning_content": "trail"}, "finish_reason": "stop",
            "completion_tokens": 120, "prompt_tokens": 400, "wall_s": 1.0}
    rec = score_record(row, resp, item_for(8, 0))
    ok(rec["correct"] is True and rec["delivered"] is True, "correct delivery not scored")
    ok(rec["census"]["reasoning_field"] == "reasoning_content", "record census missing")
    ok(rec["gate"] == current_blob(), "record not stamped with the frozen gate")
    wrong = dict(rec, declared="zork", correct=False)
    none_row = [c for c in p1 if c["gold"] == NONE_GOLD][0]
    bad_none = {"label": none_row["label"], "kind": none_row["kind"], "mode": none_row["mode"],
                "level": none_row["level"], "seed": none_row["seed"], "src": none_row["src"],
                "j": none_row["j"], "cap": none_row["cap"], "gold": NONE_GOLD,
                "pseudo_gold": "", "prompt_sha256": none_row["prompt_sha256"],
                "prompt_chars": 0, "n_facts": 0, "content": "zork", "content_chars": 4,
                "delivered": True, "declared": "zork", "correct": False, "trace": "",
                "trace_chars": 0, "gold_in_trace": False, "pseudo_in_trace": False,
                "census": {"fields": [], "reasoning_field": ""}, "finish_reason": "stop",
                "completion_tokens": 4, "prompt_tokens": 1, "wall_s": 0.1,
                "model_digest": "x", "gate": current_blob()}
    scored = score_records([rec, wrong, bad_none], spec)
    ok(scored["criteria"]["C2"]["name_on_none"] == 1, "name-on-NONE defect not caught")
    ok(scored["tier"] == "controls_invalid", "planted leak did not invalidate the controls")

    # 11. a plan change must move the gate blob (fail closed on post-freeze edits)
    moved = json.loads(json.dumps(spec))
    moved["cells"][0]["j"] = moved["cells"][0]["j"] + 1
    ok(gate_blob(moved) != gate_blob(spec), "gate blob insensitive to a cell change")

    print(f"selftest passed ({checks} checks)")


# ------------------------------------------------------------------ run

def health_probe() -> dict:
    resp = call("Rule: for all x, y, z: if x precedes y and y precedes z, then x precedes z. "
                "Facts: alby precedes birch. birch precedes cobin. Question: does alby precedes "
                "cobin? Answer with exactly one word: yes or no.", 64)
    tr, fields, reasoning_field = trace_of(resp["message"])
    return {"completion_tokens": resp.get("completion_tokens"), "finish_reason": resp.get("finish_reason"),
            "fields": fields, "reasoning_field": reasoning_field, "trace_chars": len(tr),
            "model_digest": model_digest()}


def do_freeze(outdir: str) -> int:
    cert = certify_archived_k48()
    spec = gate_spec()
    assert len(PLAN) <= CALL_CAP, "plan exceeds the call cap"
    os.makedirs(outdir, exist_ok=True)
    blob = gate_blob(spec)
    with open(os.path.join(outdir, "gate.json"), "w", encoding="utf-8") as fh:
        json.dump({"gate_sha256": blob, "certification": cert, "spec": spec}, fh,
                  sort_keys=True, indent=2)
        fh.write("\n")
    print(json.dumps({"gate_sha256": blob, "planned_calls": len(PLAN)}))
    return 0


def do_run(outdir: str, resume: bool) -> int:
    assert len(PLAN) <= CALL_CAP, "plan exceeds the call cap"
    os.makedirs(outdir, exist_ok=True)
    gate_path = os.path.join(outdir, "gate.json")
    assert os.path.exists(gate_path), "gate.json must be frozen before the first call"
    with open(gate_path, encoding="utf-8") as fh:
        frozen = json.load(fh)
    assert frozen["gate_sha256"] == current_blob(), (
        "the plan moved after the gate was frozen; refuse to dispatch")
    raw_path = os.path.join(outdir, "raw.jsonl")
    done: dict = {}
    if resume and os.path.exists(raw_path):
        for rec in read_jsonl(raw_path):
            spec_row = next((c for c in plan_prompts() if c["label"] == rec["label"]), None)
            if spec_row and spec_row["prompt_sha256"] == rec["prompt_sha256"] and \
                    rec.get("finish_reason") not in (None, "client_error"):
                done[rec["label"]] = rec
    cert = certify_archived_k48()
    health = health_probe()
    with open(os.path.join(outdir, "health.json"), "w", encoding="utf-8") as fh:
        json.dump(health, fh, sort_keys=True, indent=2)
        fh.write("\n")

    rows = list(done.values())
    retries = 0
    not_dispatched = []
    t0 = time.time()
    for spec_row in plan_prompts():
        if spec_row["label"] in done:
            continue
        if time.time() - t0 > DISPATCH_BUDGET_S:
            not_dispatched.append(spec_row["label"])
            continue
        item = item_for(spec_row["level"], spec_row["index"])
        try:
            resp = call(spec_row["prompt"], spec_row["cap"])
        except Exception as exc:  # transport failure: retry once inside the global budget
            if retries >= MAX_RETRIES_TOTAL:
                rows.append(score_record(spec_row, None, item, error=type(exc).__name__))
                continue
            retries += 1
            time.sleep(RETRY_BACKOFF_S)
            try:
                resp = call(spec_row["prompt"], spec_row["cap"])
            except Exception as exc2:
                rows.append(score_record(spec_row, None, item, error=type(exc2).__name__))
                continue
        rows.append(score_record(spec_row, resp, item))
        write_jsonl(raw_path, rows)
    write_jsonl(raw_path, rows)

    scored = score_records(rows, gate_spec())
    summary = {"gate_sha256": current_blob(), "certification": cert, "health": health,
               "planned_calls": len(PLAN), "dispatched": len(rows),
               "reused_from_resume": len(done), "retries_used": retries,
               "not_dispatched": not_dispatched,
               "dispatch_wall_s": round(time.time() - t0, 3),
               "labels": [r["label"] for r in rows], "scores": scored,
               "cells": [{"label": r["label"], "mode": r["mode"], "j": r["j"],
                          "delivered": r["delivered"], "declared": r["declared"],
                          "correct": r["correct"], "finish_reason": r["finish_reason"],
                          "completion_tokens": r["completion_tokens"],
                          "content_chars": r["content_chars"], "trace_chars": r["trace_chars"]}
                         for r in rows]}
    with open(os.path.join(outdir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, sort_keys=True, indent=2)
        fh.write("\n")
    print(json.dumps({"tier": scored["tier"], "flags": scored["flags"],
                      "dispatched": len(rows), "not_dispatched": not_dispatched}, sort_keys=True))
    return 0


def do_rescore(outdir: str) -> int:
    """Rebuild summary.json from a frozen raw.jsonl at zero prompt cost."""
    rows = read_jsonl(os.path.join(outdir, "raw.jsonl"))
    scored = score_records(rows, gate_spec())
    path = os.path.join(outdir, "summary.json")
    old = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            old = json.load(fh)
    old.update({"gate_sha256": current_blob(), "labels": [r["label"] for r in rows],
                "scores": scored,
                "cells": [{"label": r["label"], "mode": r["mode"], "j": r["j"],
                           "delivered": r["delivered"], "declared": r["declared"],
                           "correct": r["correct"], "finish_reason": r["finish_reason"],
                           "completion_tokens": r["completion_tokens"],
                           "content_chars": r["content_chars"], "trace_chars": r["trace_chars"]}
                          for r in rows]})
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(old, fh, sort_keys=True, indent=2)
        fh.write("\n")
    print(json.dumps({"tier": scored["tier"], "flags": scored["flags"],
                      "records": len(rows)}, sort_keys=True))
    return 0


def do_dry() -> int:
    cert = certify_archived_k48()
    prompts = plan_prompts()
    by_mode = {"free": 0, "ban": 0}
    for p in prompts:
        by_mode[p["mode"]] += 1
    print(json.dumps({"planned_calls": len(prompts), "by_mode": by_mode,
                      "call_cap": CALL_CAP, "max_tokens": MAX_TOKENS,
                      "none_controls": sum(1 for p in prompts if p["gold"] == NONE_GOLD),
                      "gate_sha256": gate_blob(gate_spec()), "certification": cert,
                      "prompt_sha256_by_label": {p["label"]: p["prompt_sha256"][:16]
                                                 for p in prompts}}, sort_keys=True, indent=2))
    return 0


def main(argv: list) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--freeze-gate", metavar="OUTDIR")
    p.add_argument("--run", metavar="OUTDIR")
    p.add_argument("--rescore", metavar="OUTDIR")
    p.add_argument("--resume", action="store_true")
    args = p.parse_args(argv)
    if args.selftest:
        selftest()
        return 0
    if args.dry_run:
        return do_dry()
    if args.freeze_gate:
        return do_freeze(args.freeze_gate)
    if args.run:
        return do_run(args.run, args.resume)
    if args.rescore:
        return do_rescore(args.rescore)
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Round 69 (2026-11-16 02:19, issue #65): the k > 48 name-walk panel dispatched as a
byte-identical matched pair on the build that already broke it.

The question (frozen in gate.json before any dispatch): the round-61 gate registered one
discriminator, row P1, on the four endpoint cells past the old generator ceiling (A48_j48,
A49_j49, B50_j50, C64_j64, name arm, cap 2048). The 27B-class firing (round 63) put it on
one build and got 1 of 4. This firing puts the identical eight cells on the other side of
the identity split: the serving build whose model digest is the pinned `c62b81e96826354e`,
the build that already returned 2 of 4 on the same four labels (round 49) and the only
build in this program that has produced wrong terminal names (rounds 37, 38, 47, 49, 59),
whose wall shape is a self-stop near 1,557 tokens with position errors on the right path
instead of a censor at the 2,048 cap. Items, seeds, golds, caps, prompt template and cell
order are frozen from the shipped generator; the matched-pair prompt digests are asserted
in --selftest against the round-63 pins, so the only free variable is the build.

Readings at stake (both already partially supported): the output-budget reading (issue
#126: the wall collapsed to zero on both classes and moves with the serving budget) and
the length-generalization reading (T1-T3: the wall moves with the step count).

What this firing adds on top of the registered row:
- row S1 (issue #145): the registered P1 count treats a cell that delivered nothing the
  same as a cell that delivered a wrong name. A reading carried by no-delivery cells is a
  budget outcome, not a competence outcome, so this firing reports the registered count
  verbatim AND a per-cell delivery census; when the non-correct endpoint cells are all
  no-delivery the outcome carries the name `inconclusive_budget` and P1 stays owed for the
  reading while the count stays recorded.
- row W2: a per-cell wall-signature census (reserve tokens below the requested cap,
  finish reason) fitted against the three archived laws (the 1,556 to 1,558 self-stop band
  with finish `stop`, the 492-token reserve, the cap-bound reserve at or below 19). It is
  the test-retest of the round-59 signature on the same serving build.
- sequential dispatch (issue #73, open since round 42: health check and incremental
  archive were adopted, sequential dispatch was not): one worker, so each cell's wall
  time, token count and rate are attributable to that cell and not to a shared queue
  (issue #141: a co-fired grid starves the host to about one completion token per second).

Standing rules carried in:
- pre-dispatch rate measurement gates the plan (the round-61 standing rule, the round-63
  measure.json shape): two 256-token census calls plus one full-cap calibration dispatch on
  the k = 48 anchor cell, all before the gate is frozen; the plan is a function of the
  measured rate and the frozen thresholds, not of mid-run conditions.
- validity gates first (the round-60 order): the two shallow dead-end NONE controls (one
  step by design) dispatch before the endpoint cells.
- a byte-identical re-dispatch pair on the B50 endpoint (issue #100 self-agreement).
- the k = 48 anchor item is the archived load-floor item of rounds 51/52/53/54 (seed
  116261051, yes/no prompt digest 068bc6a1fb0620fb), re-certified before any prompt is
  spent (fail closed).
- trace-exposure census (issue #105): every raw record carries the message-field census
  plus the reasoning-supplying field (merge rule: reasoning_content if non-empty, else
  reasoning, else empty). No trace-recovery rule is applied (issue #94, the round-50
  calibration failure); the readout is the answer field only.

Item machinery: per-item generation with the entity-pool raise caught (issue #129) and the
`generate_items` seed convention (seed_base + 2_000_000 * level + i) preserved, so every
item here is byte-identical to what the shipped generator produces for that seed. Prompt
template byte-identical to the round-55 name-or-NONE template (rounds 55/60/61/63/64).

House contract: stdlib only; --selftest with planted negatives; every record carries the
frozen gate blob; scripts read NIGHTLY_BASE_URL / NIGHTLY_MODEL_ID / NIGHTLY_API_KEY from
the environment and never write them anywhere; at most 40 prompts; max_tokens <= 2048; the
sanitizer also redacts serving-id labels (the issue #85 leak class) from model output.
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

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_REPO, "generators"))

import ladders  # noqa: E402

SEED_BASE = 20261005          # the round-51 seed base, so the k = 48 anchor is the archived item
SCAN = 300                    # the round-51 scan width (the issue #129 measurement table)
MAX_TOKENS = 2048             # protocol cap: no requested cap may exceed it
CALL_CAP = 40
TIMEOUT_S = 900               # per-call guard; a stuck endpoint must not eat the round cap
DISPATCH_BUDGET_S = 3000      # wall-clock guard on the dispatch phase
CELL_FLOOR_S = 120            # do not start a cell with less than this much budget left
MAX_RETRIES_TOTAL = 4
WORKERS = 1                   # sequential (issue #73): one cell at a time on a shared host
NONE_GOLD = "NONE"
GATE_SCHEMA = "round69-gate-v1"
CENSUS_CAP = 256

# The archived k = 48 load-floor item: rounds 51, 52, 53 and 54 dispatched it byte-identically.
ARCHIVED_K48 = {"seed": 116261051, "yesno_digest16": "068bc6a1fb0620fb"}

# Cross-firing anchors on the identical A48_j8 prompt (cap 2048, temperature 0.0), with the
# merged state of the record each number is quoted from.
ANCHOR_RECORDS = {
    "round61": {"tokens": 1123, "record": "round-61 gate E1 row, PR #142, unmerged here"},
    "round63": {"tokens": 1113, "record": "round-63 pre-gate calibration, PR #143, unmerged here"},
}

# The matched pair: the eight cell prompt digests frozen by the round-63 gate (PR #143,
# unmerged at this firing). --selftest asserts that the recomputed digests equal these, so
# the claim "this firing dispatches the same items and prompts on a different build" is
# machine-checked here instead of being typed in the README.
MATCHED_PAIR = {
    "record": "round-63 gate cells, PR #143, unmerged at this firing",
    "prompt_sha256": {
        "A49_deadend": "8a6aadff52bf045290536c44d8877c330582f51a7e18c4150def8cbfd3499f27",
        "C64_deadend": "c36ea5dff6d90a069d0573968c9823c92e403bfdb0891862aab56a19669af465",
        "A48_j48": "baabc3462652878fdbdca1994faa18240e917b5f0fea69fd786d34e56526c4c9",
        "A49_j49": "0d61f97016e61b4da797c84f4139ca72ac0e94001739c429a7d91140a304ec59",
        "B50_j50": "c15a68eb63cc474457ebe6f8ee806f6e0182d38967bfdbe67726417c272e5362",
        "C64_j64": "c1ef6c20bfd84e2fd30a6eaefa22caf1dfb4663280b0824cac72e89f298eea7e",
        "B50_j50_dup": "c15a68eb63cc474457ebe6f8ee806f6e0182d38967bfdbe67726417c272e5362",
        "A48_j8": "cec71db935bf42f9b0707da23f6973c622dd8b780fc9abc68f1f33edd5716260",
    },
}

# The three archived wall-shape laws, each quoted from the record that measured it.
WALL_LAWS = {
    "L1_self_stop_band": {
        "source": "round 59 (PR #140, unmerged here), the same serving build as this firing",
        "test": "1556 <= completion_tokens <= 1558 and finish_reason == 'stop'",
        "basis": "16 of 26 records sit in the 1,556 to 1,558 token band, zero cells cap-bound",
    },
    "L2_reserve_492": {
        "source": "round 53 (PR #131, unmerged here), a flash-class build with a different digest",
        "test": "cap - completion_tokens == 492",
        "basis": "every pinned ladder record stops 492 tokens below its requested cap",
    },
    "L3_cap_bound": {
        "source": "round 54 (PR #133, unmerged here), a 27B-class build",
        "test": "cap - completion_tokens <= 19",
        "basis": "the 27B-class cap ladder is cap-bound at every rung below the pin; "
                 "issue #141 records the same shape on the deep cells (reserve 0 or 2)",
    },
}

# Pre-registered plan-selection thresholds, kept identical to the round-63 gate so the two
# firings are comparable. Worst-case panel arithmetic (frozen): the full plan is eight cells
# of cap 2048 (16,384 completion tokens), the trimmed plan six (12,288). At r = 10 the full
# plan's worst case is 1,638 s and at r = 5 the trimmed plan's worst case is 2,458 s: both
# inside the frozen 3,000 s dispatch budget.
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


def path_nodes(item: dict, src: str) -> list:
    """Every node on the path that starts at src, in step order: node i is reached from src by
    exactly i links. The position readout (the round-59 signature: a wrong position on the
    right path) is a lookup in this list."""
    adj = adjacency(item)
    nodes = [src]
    while True:
        nxt = adj.get(nodes[-1])
        if nxt is None:
            return nodes
        nodes.append(nxt)


def off_path_nodes(item: dict, src: str) -> set:
    """Nodes that are not on the src path: naming one of them is an off-path answer."""
    on = set(path_nodes(item, src))
    return {n for n in {t for _, _, t in item["facts"]} if n not in on}


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
    each new level (the round-63 selection). Vocabularies come from one shared name pool by
    independent per-item RNG streams, so cross-item name overlap is expected and harmless:
    every prompt carries exactly one item and every score is taken against that item's own
    vocabulary."""
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
    qs, qrel, qt = item["query"]
    return (f"{item['rule']}\nFacts:\n{fact_block(item)}\n\n"
            f"Question: does {qs} {qrel} {qt}?\n"
            "Answer with exactly one word: yes or no.")


def prompt_digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ------------------------------------------------------------------ plan


# The round-63 order and the round-63 eight cells: validity gates first, then the four
# endpoint cells of the registered P1 panel, then the duplicate pair and the anchor cell.
PLAN_R69 = [
    ("A49_deadend", "A49", 1, MAX_TOKENS, "dead_end"),
    ("C64_deadend", "C64", 1, MAX_TOKENS, "dead_end"),
    ("A48_j48", "A48", 48, MAX_TOKENS, "name"),
    ("A49_j49", "A49", 49, MAX_TOKENS, "name"),
    ("B50_j50", "B50", 50, MAX_TOKENS, "name"),
    ("C64_j64", "C64", 64, MAX_TOKENS, "name"),
    ("B50_j50_dup", "B50", 50, MAX_TOKENS, "dup"),
    ("A48_j8", "A48", 8, MAX_TOKENS, "name"),
]

# The trimmed plan, selected when the measured rate is below RATE_FULL_PLAN: the two controls
# and the four registered endpoint cells. The duplicate pair (issue #100) and the anchor
# liveness cell are owed to a later firing; the registered panel stays fully evaluable.
PLAN_R69CORE = [c for c in PLAN_R69 if c[0] not in ("B50_j50_dup", "A48_j8")]

PANELS = {"r69": PLAN_R69, "r69core": PLAN_R69CORE}

DUP_PAIRS = (("B50_j50", "B50_j50_dup"),)
ENDPOINT_CELLS = ("A48_j48", "A49_j49", "B50_j50", "C64_j64")
CONTROL_CELLS = ("A49_deadend", "C64_deadend")
ANCHOR_CELL = "A48_j8"
PREGATE_CALLS = 3          # 2 census calls at cap 256 plus one full-cap calibration dispatch
# The issue #145 delivery census. A state counts as a delivery when the cell put something
# on the wire that can be read as its answer (an entity name of its own item, the NONE
# sentinel, or a non-empty answer field whose token is not one of the item's). A cap censor
# and an answer field that was never written are not deliveries.
DELIVERY_CENSUS_STATES = ("delivered_correct", "delivered_wrong_on_right_path",
                          "delivered_wrong_off_path", "declared_none_on_name_gold",
                          "delivered_no_item_name", "no_answer_field", "censored_at_cap")
DELIVERED_STATES = ("delivered_correct", "delivered_wrong_on_right_path",
                    "delivered_wrong_off_path", "declared_none_on_name_gold",
                    "delivered_no_item_name")


def plan_selection(rate: float) -> str:
    """The frozen selection rule: the full plan at or above RATE_FULL_PLAN, the trimmed plan
    below it. Below RATE_CORE_PLAN the trimmed plan is kept and the budget governs: cells
    that do not land inside the frozen dispatch budget stay not_dispatched and row P1 stays
    owed for the unrecorded endpoint cells."""
    return "r69" if rate >= RATE_FULL_PLAN else "r69core"


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
        nodes = path_nodes(item, src)
        own = terminal_at(item, src, item["level"])
        pseudo = other_tail(item, src) if own is not None else ""
        out.append({"label": label, "level": item["level"], "seed": item["seed"],
                    "item_key": key, "src": src, "j": j, "cap": cap, "kind": kind,
                    "gold": gold, "prompt": prompt, "pseudo_gold": pseudo,
                    "n_facts": len(item["facts"]), "path_len": len(nodes) - 1,
                    "prompt_sha256": prompt_digest(prompt)})
    return out


# ------------------------------------------------------------------ sanitizer

_SECRET_PATTERNS = [
    re.compile(r"https?://\S+"),
    re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d+)?\b"),
    re.compile(r"/(?:root|home|mnt|media|run/user)/\S+"),
    # Serving-id labels (issue #85): a model identifier ending in a quantization tag.
    # Assembled by concatenation so this file carries no pattern instance of its own.
    re.compile(r"\b[a-z0-9][a-z0-9._-]*-(?:" + "iq" + r"\d+|q\d+|ud-q\d+)(?:[_-]?[a-z0-9]+)?\b"),
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
    reasoning channel can consume the whole budget before the answer field is written."""
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


def tok_rate(completion_tokens, wall_s):
    if not completion_tokens or not wall_s:
        return None
    return round(completion_tokens / wall_s, 3)


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
    completion = usage.get("completion_tokens")
    wall = round(time.time() - t0, 3)
    return {"message": message, "finish_reason": choice.get("finish_reason"),
            "completion_tokens": completion, "prompt_tokens": usage.get("prompt_tokens"),
            "wall_s": wall, "tok_per_s": tok_rate(completion, wall)}


# ------------------------------------------------------------------ gate

THEORY_ROWS = {
    "T1_tc0_bound": {
        "source": "arXiv:2604.25800",
        "statement": ("learnable chain-of-thought length-generalizes only within TC0 under "
                      "standard positional encodings and a finite alphabet; the signpost-token "
                      "remedy shows the barrier is encoding-specific, not universal"),
        "verification": ("OpenAlex work record re-read in this session 2026-11-16 "
                         "(work-record level: title, authors, year; no quote taken)")},
    "T2_crasp_characterization": {
        "source": "arXiv:2608.13433",
        "statement": ("complete characterization of length generalization for regular "
                      "languages under NoPE: it holds iff the syntactic monoid decomposes "
                      "into loop-balanced integer counters (C-RASP); a near-binary split on "
                      "175 languages and 10x data does not rescue the failing class. "
                      "Caveat on record: NoPE theory; the deployed models use RoPE"),
        "verification": ("OpenAlex work record re-read in this session 2026-11-16 "
                         "(work-record level: title, authors, year; no quote taken)")},
    "T3_encoding_specific_remedies": {
        "source": "arXiv:2608.31067 (with arXiv:2604.25800)",
        "statement": ("depth-tracking positional encoding plus halting gives exact length "
                      "generalization on Boolean evaluation, ListOps and modular arithmetic "
                      "with 280 parameters: the second encoding-specific remedy after the "
                      "signpost tokens, i.e. the wall moves with the encoding"),
        "verification": ("OpenAlex work record re-read in this session 2026-11-16 (also "
                         "verified at work-record level in the round-61 gate; title, authors, "
                         "year; no quote taken)")},
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


def question_text() -> str:
    return ("Does the k > 48 name-walk panel discriminate the two wall readings on the "
            "flash-next-class build whose serving identity is the pinned model digest "
            "c62b81e96826354e? Row P1 was registered by the round-61 gate on the four "
            "endpoint cells (A48_j48, A49_j49, B50_j50, C64_j64, cap 2048, name arm): 3 or "
            "4 of 4 delivering the correct terminal makes the measured wall an output-budget "
            "and output-policy artifact (the issue #126 reading), 1 or fewer keeps the "
            "length-generalization reading (T1-T3) alive, 2 of 4 is inconclusive. The 27B "
            "side of the split was dispatched by round 63 on a build with a different digest "
            "and returned 1 of 4. This firing dispatches the identical eight cells "
            "(byte-identical items, seeds, golds, caps and prompts, asserted in --selftest "
            "against the round-63 pins) on the build that already returned 2 of 4 on the "
            "same four labels (round 49) and that is the only build in this record to have "
            "named a wrong terminal (rounds 37, 38, 47, 49, 59). The panel's wall mode was "
            "called build-tied by round 64; this firing is the test-retest of that claim on "
            "the tie's own side.")


def gate_spec(plan: list, measure: dict) -> dict:
    cells = plan_prompts(plan)
    panel_name = "r69" if len(cells) == len(PLAN_R69) else "r69core"
    return {
        "schema": GATE_SCHEMA,
        "question": question_text(),
        "criteria": {
            "N3_anchor_certification": {
                "statement": ("pre-dispatch, fatal: the k = 48 anchor item regenerates from "
                              "the shipped generator with seed 116261051 and its archived "
                              "yes/no prompt digest 068bc6a1fb0620fb (rounds 51/52/53/54), "
                              "every item in the set is a load-floor, component-isomorphic "
                              "item (issue #67 guards), and every cell prompt digest equals "
                              "the round-63 matched-pair pin, so the build is the only "
                              "difference between the two firings"),
                "threshold": "certified before any prompt is spent"},
            "E1_anchor_liveness": {
                "statement": ("the k = 48 anchor cell A48_j8 (archived seed 116261051, j = 8, "
                              "cap 2048) delivers the correct terminal on this build; the "
                              "same prompt delivered correctly at 1,123 tokens on the "
                              "round-61 build and at 1,113 tokens on the round-63 build, so "
                              "this record is the third point of a cross-build test-retest "
                              "of the shallow rung"),
                "threshold": "delivered and correct, when the cell is in the selected plan"},
            "E2_census_trace_exposure": {
                "statement": ("the 256-token census call answers the two-fact transitivity "
                              "query correctly and names the reasoning-supplying field of "
                              "this firing (issue #105; any cross-build trace claim must "
                              "state both sides' exposure)"),
                "threshold": "correct content and non-empty reasoning channel"},
            "R1_dead_end_controls": {
                "statement": ("VALIDITY GATE: both dead-end NONE controls (A49 and C64, one "
                              "step by design, the round-60 lesson: off-end controls at depth "
                              "inherit truncation; certified on this build family by the "
                              "issue #139 fix) declare NONE; if either names an entity where "
                              "the links have run out the firing is flagged "
                              "controls_invalid and the P1 evaluation is uncertified"),
                "threshold": "both controls declare NONE"},
            "P1_panel_prediction": {
                "statement": ("DISCRIMINATOR as registered by the round-61 gate, rule "
                              "unchanged: on the four endpoint cells, 3 or 4 delivering the "
                              "correct terminal makes the wall an output-budget and "
                              "output-policy artifact (issue #126); 1 or fewer keeps the "
                              "length-generalization reading (T1-T3) alive; exactly 2 of 4 is "
                              "inconclusive and P1 stays owed. All four endpoint cells must "
                              "be recorded for the count to be evaluable; a cell that did "
                              "not dispatch is not reported as a result. Row S1 states "
                              "whether the count is carried by deliveries or by "
                              "non-deliveries."),
                "threshold": "3+ of 4 correct: output-budget reading; 1 or fewer of 4 "
                             "correct: length-generalization reading; 2 of 4: inconclusive"},
            "X1_stopping_build_prediction": {
                "statement": ("REGISTERED PREDICTION (round 64, PR #144, unmerged at this "
                              "firing): on the build that stops by itself, a wrong position "
                              "should coincide with a self-truncated trace and the emitted "
                              "name should be the last position its own trace reached. This "
                              "firing runs on that build, so the prediction is tested here "
                              "rather than restated. Evaluated per named-but-wrong endpoint "
                              "cell: is the declared name the last generator-vocab name in "
                              "that record's own trace, does its position on the asked path "
                              "equal the furthest position along that path the trace names, "
                              "and did the record stop on its own (finish stop with a "
                              "reserve above 19 tokens below the requested cap). Reachable "
                              "when at least one endpoint cell names a terminal the solver "
                              "did not accept; with no named cell the row reports "
                              "not_evaluable_no_named_cell and the prediction stays owed"),
                "threshold": "supported when every named-but-wrong cell satisfies all three "
                             "measures; refuted when any named-but-wrong cell fails one; "
                             "not_evaluable_no_named_cell with no named cell"},
            "S1_delivery_census": {
                "statement": ("REPORT ROW (issue #145): every recorded endpoint cell is "
                              "classified delivered_correct, delivered_wrong_on_right_path "
                              "(the round-59 signature: a name on the asked path at the "
                              "wrong step), delivered_wrong_off_path (a name of the same "
                              "item that is not on the asked path), "
                              "declared_none_on_name_gold (a refusal where a terminal was "
                              "asked), delivered_no_item_name (a non-empty answer field "
                              "carrying no entity name of that item and no NONE), "
                              "censored_at_cap (the finish reason is length: the requested "
                              "cap cut the output before an answer landed, whether the "
                              "field is empty or holds a fragment) or no_answer_field (the "
                              "record stopped on its own without writing an answer), and "
                              "n_eligible (the cells that put a readable answer on the wire) "
                              "is reported beside n and the correct count. When the panel "
                              "lands on the 1-or-fewer "
                              "branch and every non-correct endpoint cell of that branch is "
                              "a non-delivery (a cap censor or an empty answer field), the "
                              "branch was produced by the output budget and not by the "
                              "model's behavior on the task, and the outcome carries the "
                              "name inconclusive_budget with P1 owed for the reading. A "
                              "branch carried by a named-but-wrong terminal or a delivered "
                              "refusal is delivery_backed and stays evaluable, because a "
                              "name read out of a cell that never put an answer on the wire "
                              "is not evidence about the task while a named wrong terminal "
                              "is"),
                "threshold": "reachable whenever at least one endpoint cell is recorded"},
            "W2_wall_signature_census": {
                "statement": ("REPORT ROW: for every recorded cell the reserve below the "
                              "requested cap (cap minus completion_tokens) and the finish "
                              "reason are fitted against the three archived wall laws "
                              "(L1 the 1,556 to 1,558 self-stop band at finish stop, L2 the "
                              "492-token reserve, L3 the cap-bound reserve at or below 19) "
                              "and the modal shape is reported per cell. On this build L1 is "
                              "the archived signature, so a re-presenting L1 fit is a "
                              "test-retest of the round-59 wall mode and a re-presenting L3 "
                              "fit moves that wall mode from build-tied to firing-tied"),
                "threshold": "reported for every recorded cell"},
        },
        "theory": THEORY_ROWS,
        "wall_laws": WALL_LAWS,
        "pins": {
            "archived_k48": ARCHIVED_K48,
            "matched_pair": MATCHED_PAIR,
            "anchor_records": ANCHOR_RECORDS,
        },
        "tier_rule": (
            "panel state drives the verdict tier exactly as registered: panel_delivered "
            "(all four endpoint cells recorded), panel_partial (two or three of four "
            "recorded), panel_starved (one or fewer recorded; P1 stays owed and the measured "
            "rate is the record). Row P1 carries the discriminator count and the reading; a "
            "controls_invalid firing downgrades the P1 evaluation to uncertified. Row S1 "
            "attaches the eligibility state to the reading: when every non-correct endpoint "
            "cell is a non-delivery the reading is named inconclusive_budget and P1 stays "
            "owed for the reading while the count stays on the record. A cell that did not "
            "dispatch is never reported as a result. Row X1 is evaluated on its own "
            "reachability rule and never moves the tier."),
        "plan_rule": {
            "note": ("standing round-61 rule: gate panel-scale commitments on a pre-dispatch "
                     "rate measurement. Measured by two 256-token census calls plus one "
                     "full-cap calibration dispatch on the anchor cell, all before the gate "
                     "is frozen; the selected panel is a function of the measured rate, not "
                     "of mid-run conditions. Worst-case panel arithmetic: the full plan is "
                     "16,384 completion tokens and the trimmed plan 12,288, against the "
                     "frozen 3,000 s dispatch budget. Dispatch runs on one worker (issue "
                     "#73), so a cell's wall time and rate belong to that cell"),
            "rate_full_plan": RATE_FULL_PLAN,
            "rate_core_plan": RATE_CORE_PLAN,
            "worst_case_tokens": {"r69": MAX_TOKENS * len(PLAN_R69),
                                  "r69core": MAX_TOKENS * len(PLAN_R69CORE)},
        },
        "panel": len(cells),
        "panel_name": panel_name,
        "cells": [{"label": p["label"], "level": p["level"], "seed": p["seed"],
                   "item_key": p["item_key"], "j": p["j"], "cap": p["cap"],
                   "kind": p["kind"], "gold": p["gold"], "path_len": p["path_len"],
                   "prompt_sha256": p["prompt_sha256"]} for p in cells],
        "dispatch": {
            "planned_calls": len(cells),
            "pre_gate_calls": PREGATE_CALLS,
            "call_cap": CALL_CAP,
            "temperature": 0.0,
            "max_tokens_cap": MAX_TOKENS,
            "dispatch_budget_s": DISPATCH_BUDGET_S,
            "cell_floor_s": CELL_FLOOR_S,
            "workers": WORKERS,
            "model_digest": model_digest(),
            "rate_measurement": measure,
        },
    }


def gate_blob(spec: dict) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()


# ------------------------------------------------------------------ readouts


def wall_class(cap: int, completion_tokens, finish_reason: str) -> str:
    """Reserve below the requested cap, classified against the three archived laws."""
    if completion_tokens is None:
        return "no_usage_report"
    reserve = cap - completion_tokens
    if finish_reason == "length":
        return "cap_bound" if reserve <= 19 else "censored_with_reserve"
    if 1556 <= completion_tokens <= 1558:
        return "self_stop_band"
    return "stop_with_reserve"


def law_fits(cap: int, completion_tokens, finish_reason: str) -> list:
    """Which archived wall laws this record fits. Deterministic, order fixed."""
    if completion_tokens is None:
        return []
    reserve = cap - completion_tokens
    fits = []
    if 1556 <= completion_tokens <= 1558 and finish_reason == "stop":
        fits.append("L1_self_stop_band")
    if reserve == 492:
        fits.append("L2_reserve_492")
    if reserve <= 19:
        fits.append("L3_cap_bound")
    return fits


def delivery_state(row: dict, rec: dict) -> str:
    """The issue #145 delivery state of one recorded cell. Derived from the record and the
    frozen item only. The order is fixed: a name or a NONE that reached the answer field is
    scored against the cell's own path first; only a record that carried no item name is
    classified by how its output ended."""
    gold = row["gold"]
    declared = rec["declared"]
    if declared == NONE_GOLD:
        return "declared_none" if gold == NONE_GOLD else "declared_none_on_name_gold"
    if declared is not None:
        if declared == gold.lower():
            return "delivered_correct"
        nodes = [n.lower() for n in path_nodes(item_for(row["item_key"]), row["src"])]
        return ("delivered_wrong_on_right_path" if declared in nodes
                else "delivered_wrong_off_path")
    if rec["finish_reason"] == "length":
        return "censored_at_cap"
    return "delivered_no_item_name" if rec["delivered"] else "no_answer_field"


def position_index(row: dict, declared):
    """Step position of a declared name on the asked path, or None when it is not on it."""
    if not declared or declared == NONE_GOLD:
        return None
    nodes = [n.lower() for n in path_nodes(item_for(row["item_key"]), row["src"])]
    return nodes.index(declared) if declared in nodes else None


def p1_eval(rows: dict, records: dict) -> dict:
    """The registered P1 discriminator (rule unchanged) plus the issue #145 eligibility
    state. `rows` maps label -> planned row, `records` label -> scored record."""
    n_recorded = sum(1 for l in ENDPOINT_CELLS if l in records)
    n_correct = sum(1 for l in ENDPOINT_CELLS
                    if l in records and records[l].get("correct"))
    controls_valid = all(records[l].get("correct") for l in CONTROL_CELLS
                         if l in records) and any(l in records for l in CONTROL_CELLS)
    states = {l: delivery_state(rows[l], records[l]) for l in ENDPOINT_CELLS if l in records}
    n_eligible = sum(1 for s in states.values() if s in DELIVERED_STATES)
    non_correct = [l for l in ENDPOINT_CELLS if l in records and not records[l].get("correct")]
    # The 1-or-fewer branch is decided by the failures, so only there can a non-delivery
    # decide the reading. The 3-or-4 branch is decided by deliveries that already happened.
    carried_by_nondelivery = (n_correct <= 1 and bool(non_correct)
                              and all(states[l] not in DELIVERED_STATES for l in non_correct))
    out = {"n_recorded": n_recorded, "n_correct": n_correct,
           "n_endpoint_cells": len(ENDPOINT_CELLS), "n_eligible": n_eligible,
           "controls_valid": controls_valid, "delivery_states": states}
    if n_recorded < len(ENDPOINT_CELLS):
        out["count"] = "undetermined (panel not fully recorded; P1 stays owed for the " \
                       "unrecorded endpoint cells)" if n_recorded else \
                       "undetermined (panel not dispatched; P1 stays owed)"
        out["eligibility"] = "panel_incomplete"
        out["certified"] = False
        return out
    if not controls_valid:
        out["count"] = "uncertified (controls_invalid: a NONE-gold control named)"
        out["eligibility"] = "controls_invalid"
        out["certified"] = False
        return out
    if n_correct >= 3:
        out["count"] = ("output-budget and output-policy artifact (the issue #126 reading): "
                        "3 or 4 of 4 deep endpoints delivered the correct terminal")
    elif n_correct <= 1:
        out["count"] = ("length-generalization reading (T1-T3): 1 or fewer of 4 deep "
                        "endpoints delivered the correct terminal")
    else:
        out["count"] = "inconclusive (exactly 2 of 4): the discriminator is undetermined"
    if carried_by_nondelivery:
        out["eligibility"] = "inconclusive_budget"
        out["count"] += " [named inconclusive_budget by row S1: every non-correct endpoint " \
                        "cell delivered no answer, so the count was carried by the output " \
                        "budget and the reading stays owed]"
        out["certified"] = False
    else:
        out["eligibility"] = "delivery_backed"
        out["certified"] = n_correct != 2
    return out


def wall_census(rows: dict, records: dict) -> dict:
    """Row W2: the per-cell law fits, the modal shape, and the build-identity statement."""
    per = {}
    tally: dict = {}
    for l, row in rows.items():
        rec = records.get(l)
        if not rec:
            continue
        wc = wall_class(row["cap"], rec.get("completion_tokens"), rec.get("finish_reason"))
        fits = law_fits(row["cap"], rec.get("completion_tokens"), rec.get("finish_reason"))
        reserve = (row["cap"] - rec["completion_tokens"]
                   if rec.get("completion_tokens") is not None else None)
        per[l] = {"wall_class": wc, "reserve_tokens": reserve, "law_fits": fits,
                  "finish_reason": rec.get("finish_reason"),
                  "completion_tokens": rec.get("completion_tokens"),
                  "tok_per_s": rec.get("tok_per_s")}
        tally[wc] = tally.get(wc, 0) + 1
    modal = max(tally, key=lambda k: (tally[k], k)) if tally else None
    return {"per_cell": per, "tally": tally, "modal": modal,
            "model_digest": model_digest(),
            "archived_signature_of_this_build": "L1_self_stop_band (round 59, same digest)",
            "test_retest": ("L1 re-presents on this build" if tally.get("self_stop_band")
                            else "L1 does not re-present on this build in the recorded cells")}


def trace_position_readout(row: dict, trace: str, vocab: set) -> dict:
    """Where a trace actually got to, measured on the trace text: the last generator-vocab
    name it names, the furthest position along the asked path its names reach, and how many
    positions of the asked path it names at all. The trace is read for these measures only;
    no answer is recovered from it (issue #94)."""
    seen = {t.lower() for t in NAME_RE.findall(trace)}
    names = [t.lower() for t in NAME_RE.findall(trace)]
    last = next((n for n in reversed(names) if n in vocab), None)
    nodes = [n.lower() for n in path_nodes(item_for(row["item_key"]), row["src"])]
    hit = [i for i, n in enumerate(nodes) if n in seen]
    return {"trace_last_name": last, "trace_max_step_index": max(hit) if hit else None,
            "trace_path_positions_named": len(hit)}


def prediction_eval(rows: dict, records: dict) -> dict:
    """Row X1: the prediction round 64 registered about the self-stopping build, evaluated
    on the named-but-wrong endpoint cells of this firing."""
    named = [l for l in ENDPOINT_CELLS if l in records and records[l].get("delivered")
             and records[l].get("declared") not in (None, NONE_GOLD)
             and not records[l].get("correct")]
    out = {"n_named_wrong": len(named), "per_cell": {}}
    if not named:
        out["state"] = "not_evaluable_no_named_cell (no endpoint cell named a terminal the " \
                       "solver did not accept; the prediction stays owed)"
        return out
    agrees = 0
    for l in named:
        rec = records[l]
        name_is_trace_tail = rec["declared"] == rec["trace_last_name"]
        position_agrees = (rec["declared_step_index"] is not None
                           and rec["trace_max_step_index"] is not None
                           and rec["declared_step_index"] == rec["trace_max_step_index"])
        self_truncated = rec["finish_reason"] == "stop" and (rec["reserve_tokens"] or 0) > 19
        all_three = name_is_trace_tail and position_agrees and self_truncated
        agrees += 1 if all_three else 0
        out["per_cell"][l] = {"declared": rec["declared"],
                              "declared_step_index": rec["declared_step_index"],
                              "asked_j": rec["j"], "gold": rec["gold"],
                              "trace_last_name": rec["trace_last_name"],
                              "trace_max_step_index": rec["trace_max_step_index"],
                              "name_is_trace_tail": name_is_trace_tail,
                              "position_agrees": position_agrees,
                              "self_truncated": self_truncated,
                              "reserve_tokens": rec["reserve_tokens"]}
    out["n_agree"] = agrees
    out["state"] = ("prediction supported: all " if agrees == len(named) else
                    "prediction refuted: ") + f"{len(named)} named-but-wrong cell(s), " \
                        f"{agrees} of them place the emitted name at the last position its " \
                        "own trace reached and stopped on their own"
    return out


def score_records(records: list, rows: dict, spec: dict, health: dict | None = None) -> dict:
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
                 "archived_anchors": ANCHOR_RECORDS,
                 "pass": bool(e1 and e1["delivered"] and e1["correct"])}
    out["E2"] = {"dispatched": health is not None,
                 "content": (health.get("content") if health else None),
                 "reasoning_field": (health.get("reasoning_field") if health else None),
                 "reasoning_chars": (health.get("reasoning_chars") if health else None),
                 "pass": bool(health and str(health.get("content")).strip() == "yes"
                              and (health.get("reasoning_chars") or 0) > 0)}
    r1 = {l: by.get(l) for l in CONTROL_CELLS}
    out["R1"] = {"dispatched": [l for l in CONTROL_CELLS if r1[l] is not None],
                 "declared": {l: (r1[l]["declared"] if r1[l] else None)
                              for l in CONTROL_CELLS},
                 "all_refused": all(r1[l] is not None and r1[l]["correct"]
                                    for l in CONTROL_CELLS),
                 "completion_tokens": {l: (r1[l]["completion_tokens"] if r1[l] else None)
                                       for l in CONTROL_CELLS}}
    out["P1"] = p1_eval(rows, by)
    out["S1"] = {"n_eligible": out["P1"]["n_eligible"], "states": out["P1"]["delivery_states"],
                 "eligibility": out["P1"]["eligibility"],
                 "rule": "issue #145: report n_eligible and the per-cell delivery state "
                         "beside n and the correct count; name a budget-carried outcome "
                         "inconclusive_budget"}
    out["X1"] = prediction_eval(rows, by)
    out["W2"] = wall_census(rows, by)
    for tid, row in THEORY_ROWS.items():
        out[tid] = {"status": row["verification"], "source": row["source"]}
    out["N3"] = {"status": "certified pre-dispatch", "seed": ARCHIVED_K48["seed"],
                 "yesno_digest16": ARCHIVED_K48["yesno_digest16"],
                 "matched_pair": MATCHED_PAIR["record"],
                 "digest_mismatches": [l for l, row in rows.items()
                                       if l in by and by[l]["prompt_sha256"] != row["prompt_sha256"]]}
    p1 = out["P1"]
    tier = "panel_starved"
    if p1["n_recorded"] >= len(ENDPOINT_CELLS):
        tier = "panel_delivered"
    elif p1["n_recorded"] >= 2:
        tier = "panel_partial"
    flags = []
    if not p1["controls_valid"] and any(l in by for l in CONTROL_CELLS):
        flags.append("controls_invalid")
    censored = [l for l in ENDPOINT_CELLS if l in by
                and by[l]["finish_reason"] == "length" and not by[l]["delivered"]]
    if censored:
        flags.append("endpoint_censored_at_cap:" + ",".join(censored))
    wrong = [l for l in ENDPOINT_CELLS if l in by and by[l]["delivered"]
             and not by[l]["correct"] and by[l]["declared"] not in (None, NONE_GOLD)]
    if wrong:
        flags.append("endpoint_named_wrong:" + ",".join(wrong))
    if p1["eligibility"] == "inconclusive_budget":
        flags.append("inconclusive_budget")
    if out["X1"]["state"].startswith("prediction supported"):
        flags.append("x1_prediction_supported")
    elif out["X1"]["state"].startswith("prediction refuted"):
        flags.append("x1_prediction_refuted")
    else:
        flags.append("x1_not_evaluable")
    for a, b in DUP_PAIRS:
        if a in by and b in by:
            diverged = (by[a]["delivered"] != by[b]["delivered"]
                        or (by[a]["delivered"] and by[a]["declared"] != by[b]["declared"]))
            if diverged:
                flags.append(f"dup_pair_diverges:{a}/{b}")
    if tier == "panel_starved":
        flags.append("panel_starved_record")
    return {"tier": tier, "flags": flags, "criteria": out}


def score_record(row: dict, resp: dict, error: str = "") -> dict:
    """Score one planned row against one response. The item vocabulary, the path and the
    pseudo-gold are re-derived from the generator, never read from the response."""
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
        "path_len": row["path_len"],
        "prompt": sanitize(row["prompt"], 60000), "prompt_sha256": row["prompt_sha256"],
        "content": content,
        "declared": (NONE_GOLD if declared == NONE_GOLD
                     else (declared.lower() if declared else None)),
        "delivered": delivered,
        "correct": bool(delivered and declared is not None
                        and declared.lower() == row["gold"].lower()),
        "finish_reason": (resp or {}).get("finish_reason"),
        "completion_tokens": (resp or {}).get("completion_tokens"),
        "prompt_tokens": (resp or {}).get("prompt_tokens"),
        "wall_s": (resp or {}).get("wall_s"),
        "tok_per_s": (resp or {}).get("tok_per_s"),
        "reserve_tokens": (row["cap"] - resp["completion_tokens"]
                           if resp and resp.get("completion_tokens") is not None else None),
        "error": error,
        "message_fields": fields,
        "reasoning_field": reasoning_field,
        "trace_chars": len(trace),
        "answer_chars": len(content),
        "gold_in_trace": (row["gold"] != NONE_GOLD and row["gold"].lower() in trace.lower()),
        "pseudo_in_trace": (bool(row["pseudo_gold"])
                            and row["pseudo_gold"].lower() in trace.lower()),
        "model_digest": model_digest(),
    }
    rec["delivery_state"] = delivery_state(row, rec)
    rec["declared_step_index"] = position_index(row, rec["declared"])
    tp = trace_position_readout(row, trace, vocab)
    rec["trace_last_name"] = tp["trace_last_name"]
    rec["trace_max_step_index"] = tp["trace_max_step_index"]
    rec["trace_path_positions_named"] = tp["trace_path_positions_named"]
    return rec


def build_summary(records: list, rows: dict, spec: dict, blob: str,
                  health: dict | None = None) -> dict:
    scored = score_records(records, rows, spec, health)
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
                                 "delivery_state": r["delivery_state"],
                                 "declared_step_index": r["declared_step_index"],
                                 "gold": r["gold"], "j": r["j"],
                                 "completion_tokens": r["completion_tokens"],
                                 "reserve_tokens": r["reserve_tokens"],
                                 "finish_reason": r["finish_reason"],
                                 "wall_s": r["wall_s"], "tok_per_s": r["tok_per_s"],
                                 "trace_chars": r["trace_chars"],
                                 "trace_last_name": r["trace_last_name"],
                                 "trace_max_step_index": r["trace_max_step_index"],
                                 "trace_path_positions_named": r["trace_path_positions_named"],
                                 "answer_chars": r["answer_chars"],
                                 "reasoning_field": r["reasoning_field"]}
                   for r in records},
    }


# ------------------------------------------------------------------ selftest

def _bad_item(item: dict, facts) -> dict:
    """A doctored item for the negative controls: same level, wrong load floor."""
    out = dict(item)
    out["facts"] = [list(f) for f in facts]
    return out


def readme_failures(text: str, spec: dict, blob: str) -> list:
    """Issue #137 guard, pure function so the planted negatives can be tested: the README
    may only name gate-row ids the frozen gate defines (criterion ids, the theory ids, the
    wall-law ids, the health id; an abbreviation that prefixes a defined key is defined),
    every 64-hex blob it cites must be this gate's or a digest registered in the gate's
    pins block, and every 16-hex digest must be a certified pinned one."""
    failures = []
    defined_keys = (set(spec["criteria"]) | set(spec.get("theory", {}))
                    | set(spec.get("wall_laws", {})) | {"health"})
    defined_abbrs = {k.split("_")[0] for k in defined_keys} | {"health"}
    cell_tokens = ({c[0] for c in PLAN_R69} | {c[1] for c in PLAN_R69}
                   | {c["label"] for c in spec.get("cells", [])}
                   | {c["item_key"] for c in spec.get("cells", [])})
    cell_abbrs = {t.split("_")[0] for t in cell_tokens}
    allowed_64 = {blob} | set(spec.get("pins", {}).get("matched_pair", {}).get(
        "prompt_sha256", {}).values())
    allowed_16 = {ARCHIVED_K48["yesno_digest16"], model_digest(),
                  spec.get("dispatch", {}).get("model_digest", "")}
    # A row id is a token that starts with one letter and one or two digits and is not a
    # cell label: "P1", "S1_delivery_census", "Z9_row". Cell labels share the shape, so they
    # are excluded by name instead of by regex, which is what keeps the A48_j48 results
    # table readable in a README.
    for tok in sorted(set(re.findall(r"\b[A-Z]\d{1,2}(?:_[A-Za-z0-9]+)*\b", text))):
        if tok in defined_keys or tok in cell_tokens:
            continue
        abbr = tok.split("_")[0]
        if abbr in defined_abbrs or abbr in cell_abbrs:
            continue
        failures.append(f"README quotes undefined gate-row id {tok}")
    for b in sorted(set(re.findall(r"\b[0-9a-f]{64}\b", text))):
        if b not in allowed_64:
            failures.append(f"README cites a 64-hex blob that is neither this gate's nor a "
                            f"registered pin: {b[:16]}")
    for b in sorted(set(re.findall(r"\b[0-9a-f]{16}\b", text))):
        if b not in allowed_16:
            failures.append(f"README cites a 16-hex digest that is not a certified pin: {b}")
    if blob not in text:
        failures.append("README does not carry the frozen gate blob")
    return failures


def selftest() -> None:
    global _ITEMS
    failures: list = []
    checks = {"n": 0}

    def ok(cond, msg):
        checks["n"] += 1
        if not cond:
            failures.append(msg)

    def raises(fn, msg):
        checks["n"] += 1
        try:
            fn()
        except (AssertionError, KeyError, ValueError):
            return
        failures.append(msg)

    _ITEMS = select_items()
    items = _ITEMS

    # N3: item certification, plus the planted non-load-floor negative.
    ok(items["A48"]["seed"] == ARCHIVED_K48["seed"], "anchor seed is not the archived seed")
    ok(prompt_digest(render_yesno(items["A48"]))[:16] == ARCHIVED_K48["yesno_digest16"],
       "anchor yes/no prompt digest does not match the archived pin")
    for key, level, nfacts in (("A48", 48, 96), ("A49", 49, 98), ("B50", 50, 100),
                              ("C64", 64, 128)):
        check_item(items[key])
        ok(items[key]["level"] == level and len(items[key]["facts"]) == nfacts,
           f"{key} is not the load-floor item of level {level}")
    doctor = _bad_item(items["A48"], [list(f) for f in items["A48"]["facts"][:94]]
                       + [list(items["A48"]["facts"][0])])
    raises(lambda: check_item(doctor), "check_item accepted a 94-fact item as load floor")
    fork = [list(f) for f in items["A49"]["facts"]]
    fork.append([fork[0][0], "leads_to", "trudx"])
    raises(lambda: check_item(_bad_item(items["A49"], fork)),
           "check_item accepted an item with an out-degree of two")

    # Independent solver: the walk recomputed by chain, then the negatives past the tail.
    for key in ("A48", "A49", "B50", "C64"):
        item = items[key]
        src = item["query"][0]
        chain = [n for n in path_nodes(item, src)]
        ok(len(chain) - 1 == item["level"], f"{key}: path length is not the level")
        for j in (0, 1, 8, item["level"]):
            ok(terminal_at(item, src, j) == chain[j], f"{key}: solver disagrees at j = {j}")
        ok(terminal_at(item, src, item["level"] + 1) is None,
           f"{key}: the solver walked past the tail")
    for key in ("A49", "C64"):
        tail = cell_src(items[key], "dead_end")
        ok(terminal_at(items[key], tail, 1) is None, f"{key}: the dead-end source has a link")

    # The frozen panel golds and the matched-pair prompt digests.
    rows = {r["label"]: r for r in plan_prompts(PLAN_R69)}
    expect_gold = {"A48_j8": "trackst", "A48_j48": "spog", "A49_j49": "studnd",
                   "B50_j50": "prish", "C64_j64": "brelt",
                   "A49_deadend": NONE_GOLD, "C64_deadend": NONE_GOLD,
                   "B50_j50_dup": "prish"}
    for label, gold in expect_gold.items():
        ok(rows[label]["gold"] == gold, f"{label}: gold drifted from the frozen panel")
    for label, dig in MATCHED_PAIR["prompt_sha256"].items():
        ok(rows[label]["prompt_sha256"] == dig, f"{label}: prompt digest is not the "
                                                 f"round-63 matched-pair pin")
    ok(len({rows[l]["prompt_sha256"] for l in ("B50_j50", "B50_j50_dup")}) == 1,
       "the duplicate pair is not byte-identical")
    for l in ENDPOINT_CELLS:
        ok(rows[l]["n_facts"] == 2 * rows[l]["level"], f"{l}: not dispatched at load floor")

    # Plan shape and the frozen rate thresholds.
    ok([c[0] for c in PLAN_R69][:2] == list(CONTROL_CELLS), "controls do not dispatch first")
    ok(len(PLAN_R69) == 8 and len(PLAN_R69CORE) == 6, "plan sizes are not the registered ones")
    ok(all(c[3] == MAX_TOKENS for c in PLAN_R69), "a requested cap exceeds the protocol cap")
    ok(plan_selection(10.0) == "r69" and plan_selection(9.999) == "r69core",
       "the full-plan threshold is not at RATE_FULL_PLAN")
    ok(MAX_TOKENS * len(PLAN_R69) // 10 <= DISPATCH_BUDGET_S,
       "the full plan worst case does not fit the dispatch budget at RATE_FULL_PLAN")
    ok(MAX_TOKENS * len(PLAN_R69CORE) // 5 <= DISPATCH_BUDGET_S,
       "the trimmed plan worst case does not fit the dispatch budget at RATE_CORE_PLAN")
    ok(CALL_CAP >= len(PLAN_R69) + PREGATE_CALLS + 1, "the prompt cap does not cover the round")

    # Scoring arithmetic on synthetic responses, including every negative boundary.
    row48 = rows["A48_j48"]

    def synth(content, finish="stop", tokens=1500, fields=("content", "role")):
        return {"message": {"content": content, "role": "assistant",
                            **({"reasoning_content": "step 1, step 2"} if fields == (
                                "content", "reasoning_content", "role") else {})},
                "finish_reason": finish, "completion_tokens": tokens, "prompt_tokens": 1000,
                "wall_s": 100.0, "tok_per_s": tok_rate(tokens, 100.0)}

    r_ok = score_record(row48, synth("spog"))
    ok(r_ok["correct"] and r_ok["declared"] == "spog" and r_ok["delivered"],
       "a correct name was not scored correct")
    ok(r_ok["delivery_state"] == "delivered_correct", "delivery state of a correct name")
    other_tail_name = rows["A48_j48"]["pseudo_gold"]
    off_name = sorted(off_path_nodes(items["A48"], row48["src"]))[0]
    r_wrongpath = score_record(row48, synth(off_name))
    ok(not r_wrongpath["correct"] and r_wrongpath["declared_step_index"] is None,
       "an off-path name got a position index")
    ok(r_wrongpath["delivery_state"] == "delivered_wrong_off_path",
       "off-path name got the wrong delivery state")
    r_notitem = score_record(row48, synth("trudx"))
    ok(not r_notitem["correct"] and r_notitem["delivered"]
       and r_notitem["declared"] is None
       and r_notitem["delivery_state"] == "delivered_no_item_name",
       "an answer field carrying no name of the cell's item was not censused")
    mid = path_nodes(items["A48"], row48["src"])[20]
    r_shift = score_record(row48, synth(mid))
    ok(r_shift["delivery_state"] == "delivered_wrong_on_right_path"
       and r_shift["declared_step_index"] == 20 and not r_shift["correct"],
       "the round-59 signature (a wrong position on the right path) is not measurable")
    ok(r_shift["declared_step_index"] != row48["j"], "a shifted name got the asked position")
    ok(other_tail_name != mid, "the pseudo-gold and the mid-path node are the same name")
    r_empty = score_record(row48, synth("", finish="length", tokens=2048))
    ok(not r_empty["delivered"] and r_empty["delivery_state"] == "censored_at_cap",
       "an answer field the cap cut off before any token landed was not a cap censor")
    r_stopped_blank = score_record(row48, synth("", finish="stop", tokens=300))
    ok(not r_stopped_blank["delivered"]
       and r_stopped_blank["delivery_state"] == "no_answer_field",
       "a record that stopped on its own without an answer was not censused")
    r_cut = score_record(row48, synth("sp", finish="length", tokens=2048))
    ok(r_cut["delivery_state"] == "censored_at_cap" and r_cut["declared"] is None,
       "a mid-word censor was not classified as a cap censor")
    r_none = score_record(row48, synth("NONE"))
    ok(r_none["delivered"] and not r_none["correct"]
       and r_none["delivery_state"] == "declared_none_on_name_gold",
       "a NONE on a name-gold cell was not classified")
    rowc = rows["C64_deadend"]
    r_ctl = score_record(rowc, synth("NONE"))
    ok(r_ctl["correct"] and r_ctl["delivery_state"] == "declared_none",
       "the NONE control is not scored against its own gold")
    r_named = score_record(rowc, synth("brelt"))
    ok(not r_named["correct"], "a control that named the tail counted as valid")

    # Wall-shape census: the three laws and each boundary.
    ok(wall_class(2048, 2048, "length") == "cap_bound", "reserve 0 is not cap_bound")
    ok(wall_class(2048, 2029, "length") == "cap_bound", "reserve 19 is not cap_bound")
    ok(wall_class(2048, 2028, "length") == "censored_with_reserve",
       "reserve 20 counted as cap_bound")
    ok(wall_class(2048, 1556, "stop") == "self_stop_band"
       and wall_class(2048, 1558, "stop") == "self_stop_band",
       "the 1,556 to 1,558 band is not measured at both ends")
    ok(wall_class(2048, 1555, "stop") == "stop_with_reserve"
       and wall_class(2048, 1559, "stop") == "stop_with_reserve",
       "the band boundary is open at 1,555 or 1,559")
    ok(wall_class(2048, 1556, "length") == "censored_with_reserve",
       "a length finish inside the token band got the self-stop class")
    ok(law_fits(2048, 1556, "stop") == ["L1_self_stop_band", "L2_reserve_492"],
       "1,556 tokens at finish stop must fit both the stop band and the 492 reserve")
    ok(law_fits(2000, 1508, "stop") == ["L2_reserve_492"],
       "the 492 reserve fit is wrong (measured away from the self-stop band so the two "
       "laws are separable)")
    ok(law_fits(2048, 1555, "stop") == [],
       "1,555 tokens (a 493 reserve, outside the band) fitted a wall law")
    ok(law_fits(2048, 2048, "length") == ["L3_cap_bound"], "the cap-bound fit is wrong")
    ok(law_fits(2048, 1000, "stop") == [], "a mid-length stop fit a wall law")
    ok(law_fits(2048, None, "stop") == [], "a missing usage report fitted a law")

    # P1 and S1 on synthetic record sets, one per registered branch.
    def rec(label, correct, delivered=True, finish="stop", declared=None,
            trace_last=None, trace_max=None, tokens=1600):
        r = dict(rows[label])
        r.update({"correct": correct, "delivered": delivered, "finish_reason": finish,
                  "declared": declared, "completion_tokens": tokens,
                  "reserve_tokens": 2048 - tokens, "cap": 2048,
                  "item_key": rows[label]["item_key"], "src": rows[label]["src"],
                  "gold": rows[label]["gold"],
                  "declared_step_index": position_index(rows[label], declared),
                  "trace_last_name": trace_last, "trace_max_step_index": trace_max,
                  "trace_path_positions_named": 0})
        return r

    def ctl_ok():
        return {l: rec(l, True, declared="NONE") for l in CONTROL_CELLS}

    def panel(states):
        out = ctl_ok()
        for l, s in states.items():
            out[l] = s
        return out

    good = {l: rec(l, True, declared=rows[l]["gold"]) for l in ENDPOINT_CELLS}
    res = p1_eval(rows, panel(good))
    ok(res["certified"] and "output-budget" in res["count"] and res["eligibility"]
       == "delivery_backed", "4 of 4 did not produce the output-budget reading")
    res = p1_eval(rows, panel({**good, "C64_j64": rec("C64_j64", False, declared="breltx")}))
    ok(res["n_correct"] == 3 and "output-budget" in res["count"], "3 of 4 branch is wrong")
    mix = {**good, "C64_j64": rec("C64_j64", False, declared="breltx"),
           "B50_j50": rec("B50_j50", False, declared="prishx")}
    res = p1_eval(rows, panel(mix))
    ok(res["n_correct"] == 2 and "inconclusive (exactly 2 of 4)" in res["count"]
       and not res["certified"], "the 2 of 4 middle tier is wrong")
    cuts = {l: rec(l, False, delivered=False, finish="length", declared=None)
            for l in ENDPOINT_CELLS}
    res = p1_eval(rows, panel(cuts))
    ok(res["n_correct"] == 0 and "inconclusive_budget" in res["count"]
       and res["eligibility"] == "inconclusive_budget" and res["n_eligible"] == 0,
       "a panel carried entirely by cap censors did not get the inconclusive_budget name")
    one = {**cuts, "A48_j48": rec("A48_j48", True, declared=rows["A48_j48"]["gold"])}
    res = p1_eval(rows, panel(one))
    ok(res["n_correct"] == 1 and "length-generalization" in res["count"]
       and res["eligibility"] == "inconclusive_budget" and not res["certified"]
       and res["n_eligible"] == 1,
       "1 of 4 carried by three cap censors was not named inconclusive_budget")
    three = {**cuts, "A48_j48": rec("A48_j48", True, declared=rows["A48_j48"]["gold"]),
             "A49_j49": rec("A49_j49", True, declared=rows["A49_j49"]["gold"]),
             "B50_j50": rec("B50_j50", True, declared=rows["B50_j50"]["gold"])}
    res = p1_eval(rows, panel(three))
    ok(res["n_correct"] == 3 and "output-budget" in res["count"]
       and res["eligibility"] == "delivery_backed" and res["certified"],
       "a single censored cell moved a 3-of-4 panel into the budget branch")
    wrong_named = {**cuts, "A48_j48": rec("A48_j48", False, declared="spogx")}
    res = p1_eval(rows, panel(wrong_named))
    ok(res["eligibility"] == "delivery_backed" and "inconclusive_budget" not in res["count"],
       "a named-but-wrong cell in a 0-of-4 panel was read as a budget outcome")
    blank_stops = {l: rec(l, False, delivered=True, finish="stop", declared=None, tokens=900)
                   for l in ENDPOINT_CELLS}
    res = p1_eval(rows, panel(blank_stops))
    ok(res["eligibility"] == "delivery_backed" and res["n_eligible"] == 4
       and "inconclusive_budget" not in res["count"],
       "four stopped cells that answered nothing were counted as a budget outcome")
    res = p1_eval(rows, {l: good[l] for l in ENDPOINT_CELLS[:3]} | ctl_ok())
    ok(not res["certified"] and res["eligibility"] == "panel_incomplete",
       "three recorded endpoint cells did not leave P1 owed")
    badctl = ctl_ok()
    badctl["A49_deadend"] = rec("A49_deadend", False, declared="studnd")
    res = p1_eval(rows, {**badctl, **good})
    ok(res["eligibility"] == "controls_invalid" and "controls_invalid" in res["count"],
       "a named dead-end control did not uncertify the panel")
    res = p1_eval(rows, ctl_ok())
    ok(res["n_recorded"] == 0 and "not dispatched" in res["count"],
       "an undispatched panel was not reported as owed")

    # X1: the prediction registered by round 64 about the self-stopping build, one test per
    # measure plus its not-evaluable branch.
    mid_name = path_nodes(items["A48"], rows["A48_j48"]["src"])[20]
    nxt_name = path_nodes(items["A48"], rows["A48_j48"]["src"])[21]
    hit = {**ctl_ok(), **{l: good[l] for l in ENDPOINT_CELLS if l != "A48_j48"},
           "A48_j48": rec("A48_j48", False, declared=mid_name, trace_last=mid_name,
                          trace_max=20)}
    ev = prediction_eval(rows, hit)
    ok(ev["n_named_wrong"] == 1 and ev["n_agree"] == 1 and "prediction supported" in ev["state"],
       "a self-stopped cell naming the last position its trace reached did not support X1")
    ok(hit["A48_j48"]["declared_step_index"] == 20 and hit["A48_j48"]["j"] == 48,
       "the position readout confused the trace position with the asked step count")
    ev = prediction_eval(rows, {**hit, "A48_j48": rec("A48_j48", False, declared=mid_name,
                                                       trace_last=mid_name, trace_max=30)})
    ok("prediction refuted" in ev["state"] and ev["per_cell"]["A48_j48"]["position_agrees"]
       is False, "a trace that walked past the emitted name did not refute X1")
    ev = prediction_eval(rows, {**hit, "A48_j48": rec("A48_j48", False, declared=mid_name,
                                                       trace_last=nxt_name, trace_max=20)})
    ok("prediction refuted" in ev["state"]
       and ev["per_cell"]["A48_j48"]["name_is_trace_tail"] is False,
       "a name that is not its own trace tail did not refute X1")
    ev = prediction_eval(rows, {**hit, "A48_j48": rec("A48_j48", False, declared=mid_name,
                                                       trace_last=mid_name, trace_max=20,
                                                       finish="length", tokens=2048)})
    ok("prediction refuted" in ev["state"]
       and ev["per_cell"]["A48_j48"]["self_truncated"] is False,
       "a cap-censored cell passed the self-truncation measure")
    ev = prediction_eval(rows, panel(cuts))
    ok(ev["n_named_wrong"] == 0 and "not_evaluable_no_named_cell" in ev["state"],
       "a panel with no named cell was not reported as not evaluable")
    ev = prediction_eval(rows, panel(good))
    ok(ev["n_named_wrong"] == 0, "a fully correct panel produced named-but-wrong cells")

    # Census, delivery-state table and the row-and-blob guard.
    ok(set(DELIVERY_CENSUS_STATES) | {"declared_none"} >= {
        "delivered_correct", "censored_at_cap", "no_answer_field",
        "declared_none_on_name_gold"}, "the delivery census lost a state")
    spec = gate_spec(PLAN_R69, {"rate_tok_per_s": 12.0})
    blob = gate_blob({k: v for k, v in spec.items()})
    spec["blob"] = blob
    ok(gate_blob({k: v for k, v in spec.items() if k != "blob"}) == blob,
       "the gate blob is not the compact sorted-key hash of the gate without its blob field")
    ok(len(spec["criteria"]) == 8 and set(spec["criteria"]) == {
        "N3_anchor_certification", "E1_anchor_liveness", "E2_census_trace_exposure",
        "R1_dead_end_controls", "P1_panel_prediction", "S1_delivery_census",
        "W2_wall_signature_census", "X1_stopping_build_prediction"},
       "the gate does not carry the eight registered rows")
    ok(all("threshold" in c and "statement" in c for c in spec["criteria"].values()),
       "a gate criterion is missing its threshold or statement")
    ok({r["source"].split(" ")[0] for r in THEORY_ROWS.values() if
        r["source"].startswith("arXiv")} >= {"arXiv:2604.25800", "arXiv:2608.13433"},
       "a theory row lost its arXiv source id")
    clean = ("Gate blob " + blob + " round69 criteria P1_panel_prediction S1_delivery_census "
             "W2_wall_signature_census X1_stopping_build_prediction "
             "E1 E2 N3 R1 S1 W2 X1 T1 T2 T3 T4 L1 L2 L3 health A48_j48 B50_j50_dup C64_deadend "
             "model digest " + model_digest() + " and the certified anchor digest "
             + ARCHIVED_K48["yesno_digest16"])
    ok(readme_failures(clean, spec, blob) == [], "the guard rejected a clean README")
    ok(len(readme_failures(clean.replace("S1_delivery_census", "Z9_row"), spec, blob)) == 1,
       "the guard did not catch an undefined gate-row id")
    foreign = "f" * 64
    ok(len(readme_failures(clean + " " + foreign, spec, blob)) == 1,
       "the guard did not catch a foreign 64-hex blob")
    ok(len(readme_failures(clean + " deadbeefdeadbeef", spec, blob)) == 1,
       "the guard did not catch an uncertified 16-hex digest")
    ok(len(readme_failures(clean.replace(blob, ""), spec, blob)) == 1,
       "the guard did not catch a README without the gate blob")
    ok(readme_failures(clean + " " + MATCHED_PAIR["prompt_sha256"]["A48_j48"], spec, blob)
       == [], "the guard rejected a registered matched-pair pin")

    # Transport and sanitizer negatives.
    ok(sanitize("see http://example.invalid/x and 192.0.2.34:8080 under /home/user/keep")
       == "see [redacted] and [redacted] under [redacted]", "the sanitizer leaked a fixture")
    planted = "qwen3.8-flash-" + "next-" + "iq3" + "_xxs"   # assembled so this file
    # carries no serving-id pattern instance of its own (issue #85, the guard scans tracked text)
    ok(sanitize("serving as " + planted + " today") == "serving as [redacted] today",
       "the sanitizer leaked a serving-id label")
    ok(sanitize(None) == "", "sanitize(None) is not empty")
    ok(sanitize("keep the name spog and the word NONE intact").startswith("keep"),
       "the sanitizer mangled a clean answer")
    ok(trace_of({"content": "", "reasoning": "r", "role": "assistant"})[2] == "reasoning",
       "the trace merge rule did not fall back to reasoning")
    ok(trace_of({"content": "x", "role": "assistant"})[2] == "",
       "a zero-trace deployment reported a trace channel")
    ok(trace_of({"content": "x", "reasoning_content": "rc", "reasoning": "",
                 "role": "assistant"})[2] == "reasoning_content",
       "the trace merge rule did not prefer reasoning_content")
    ok(tok_rate(120, 15.0) == 8.0 and tok_rate(0, 5.0) is None and tok_rate(5, 0) is None,
       "the rate helper is wrong at the zero boundaries")

    if failures:
        for f in failures:
            print("FAIL", f)
        print(f"selftest: {checks['n']} checks, {len(failures)} failed")
        raise SystemExit(1)
    print(f"selftest: {checks['n']} checks, 0 failed")


# ------------------------------------------------------------------ runner

_ITEMS: dict = {}


def init_items() -> None:
    global _ITEMS
    _ITEMS = select_items()
    rows = plan_prompts(PLAN_R69)
    pins = MATCHED_PAIR["prompt_sha256"]
    bad = [r["label"] for r in rows if r["prompt_sha256"] != pins[r["label"]]]
    if bad:
        raise SystemExit(f"fail closed: the recomputed prompts drifted from the matched-pair "
                         f"pins at {bad}; the shipped generator or the template changed")
    dig = prompt_digest(render_yesno(_ITEMS["A48"]))[:16]
    if dig != ARCHIVED_K48["yesno_digest16"]:
        raise SystemExit("fail closed: the k = 48 anchor no longer certifies the archived "
                         "yes/no prompt digest")


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
            "tok_per_s": resp.get("tok_per_s"), "model_digest": model_digest()}


def do_measure(outdir: str) -> int:
    """Pre-gate rate measurement: two census calls at cap 256 plus one full-cap calibration
    dispatch on the anchor cell (the round-61 and round-63 calibration shape, which doubles
    as a cross-build duplicate of the round-61 and round-63 E1 records). Writes
    measure.json; the gate is frozen against it by --freeze."""
    init_items()
    cal_row = plan_prompts([PLAN_R69[7]])[0]
    census = []
    for i in range(2):
        resp = call(CENSUS_PROMPT, CENSUS_CAP)
        content = sanitize(resp.get("message", {}).get("content"), 200)
        census.append({"call": i + 1, "cap": CENSUS_CAP, "content": content,
                       "completion_tokens": resp.get("completion_tokens"),
                       "wall_s": resp.get("wall_s"), "tok_per_s": resp.get("tok_per_s")})
        print(f"census {i + 1}: {census[-1]['completion_tokens']} tokens in "
              f"{census[-1]['wall_s']}s ({census[-1]['tok_per_s']} tok/s)")
    cal = call(cal_row["prompt"], MAX_TOKENS)
    cal_tok = cal.get("completion_tokens") or 0
    cal_wall = cal.get("wall_s") or 1.0
    rate = round(cal_tok / cal_wall, 3)
    declared = declared_answer(sanitize(cal.get("message", {}).get("content"), 2000),
                               vocab_of(item_for("A48")))[0]
    plan = plan_selection(rate)
    out = {
        "calibration": {"label": ANCHOR_CELL, "level": 48, "j": 8, "cap": MAX_TOKENS,
                        "finish_reason": cal.get("finish_reason"),
                        "declared": declared,
                        "correct": bool(declared and declared.lower() == cal_row["gold"]),
                        "gold": cal_row["gold"],
                        "completion_tokens": cal_tok, "wall_s": cal_wall,
                        "tok_per_s": rate,
                        "reserve_tokens": MAX_TOKENS - cal_tok,
                        "note": ("cross-build duplicate of the round-61 (1,123 tokens) and "
                                 "round-63 (1,113 tokens) records on the identical prompt; "
                                 "temperature 0.0; the calibration dispatch runs alone, so "
                                 "it is also this firing's host-rate record")},
        "census": census,
        "rate_tok_per_s": rate,
        "plan_rule": {"rate_full_plan": RATE_FULL_PLAN, "rate_core_plan": RATE_CORE_PLAN},
        "selected_panel": plan,
        "dispatch_shape": {"workers": WORKERS,
                           "note": "one worker, cells in panel order (issue #73)"},
        "model_digest": model_digest(),
    }
    path = os.path.join(outdir, "measure.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"measured rate {rate} tok/s -> selected panel {plan} -> {path}")
    return 0


def read_measure(outdir: str) -> dict:
    with open(os.path.join(outdir, "measure.json"), encoding="utf-8") as fh:
        return json.load(fh)


def do_freeze(outdir: str, panel: str) -> int:
    init_items()
    measure_path = os.path.join(outdir, "measure.json")
    assert os.path.exists(measure_path), "run --measure before freezing the gate"
    measure = read_measure(outdir)
    selected = measure.get("selected_panel")
    if panel == "auto":
        panel = selected
    if panel != selected:
        print(f"refusing: the measured rate selected panel {selected}, the gate was "
              f"requested for {panel} (freeze the selected panel or re-measure)")
        return 2
    spec = gate_spec(PANELS[panel], measure)
    spec["blob"] = gate_blob({k: v for k, v in spec.items()})
    path = os.path.join(outdir, "gate.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"frozen panel {panel}: gate blob {spec['blob']} -> {path}")
    print(f"anchor certified: seed {ARCHIVED_K48['seed']} yes/no digest "
          f"{ARCHIVED_K48['yesno_digest16']}; measured rate {measure['rate_tok_per_s']} "
          f"tok/s; build digest {model_digest()}")
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
    panel = spec["panel_name"] if panel == "auto" else panel
    plan = plan_prompts(PANELS[panel])
    by_label = {p["label"]: p for p in plan}
    spec_labels = {c["label"] for c in spec["cells"]}
    assert spec_labels == set(by_label), "gate cells and panel disagree"
    assert spec["dispatch"]["workers"] == WORKERS == 1, "the frozen worker count is not one"

    raw_path = os.path.join(outdir, "raw.jsonl")
    existing = read_jsonl(raw_path)
    stale = [r["label"] for r in existing if r.get("gate_blob") != blob]
    if stale:
        print(f"refusing: {len(stale)} records carry a different gate blob "
              f"(re-freeze or start clean)")
        return 2
    done = {r["label"] for r in existing if r.get("gate_blob") == blob}
    todo = [p for p in plan if p["label"] not in done]

    health_path = os.path.join(outdir, "health.json")
    if not os.path.exists(health_path):
        write_jsonl(health_path, [health_call()])

    transport = {"errors": 0, "retries": 0}
    rows_by_label = {r["label"]: r for r in existing}
    order = [p["label"] for p in plan]

    def flush() -> None:
        write_jsonl(raw_path, [rows_by_label[l] for l in order if l in rows_by_label])

    t0 = time.time()
    for idx, row in enumerate(todo):
        if time.time() - t0 > DISPATCH_BUDGET_S - CELL_FLOOR_S:
            print(f"dispatch budget left no room for {row['label']}: it stays not_dispatched")
            break
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
                transport["retries"] += 1
                attempts += 1
                time.sleep(5 * attempts)
        transport["errors"] += (1 if error else 0)
        rec = score_record(row, resp, error)
        rec["gate_blob"] = blob
        rec["dispatch_index"] = order.index(row["label"])
        rows_by_label[row["label"]] = rec
        flush()   # incremental archive (issue #73): the record lands before the next call
        print(f"landed {row['label']} finish={rec['finish_reason']} "
              f"tokens={rec['completion_tokens']} reserve={rec['reserve_tokens']} "
              f"wall={rec['wall_s']}s rate={rec['tok_per_s']} declared={rec['declared']} "
              f"state={rec['delivery_state']} trace_chars={rec['trace_chars']}")
        if time.time() - t0 > DISPATCH_BUDGET_S:
            print("dispatch budget spent; remaining cells stay not_dispatched")
            break

    records = [rows_by_label[l] for l in order if l in rows_by_label]
    health_rows = read_jsonl(health_path)
    health = health_rows[0] if health_rows else None
    summary = build_summary(records, by_label, spec, blob, health)
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
    if gate_blob({k: v for k, v in spec.items() if k != "blob"}) != blob:
        print("refusing: gate.json does not match its pinned blob")
        return 2
    records = read_jsonl(os.path.join(outdir, "raw.jsonl"))
    bad = [r["label"] for r in records if r.get("gate_blob") != blob]
    if bad:
        print(f"refusing: records without the frozen blob: {bad}")
        return 2
    rows = {p["label"]: p for p in plan_prompts(PANELS[spec["panel_name"]])}
    health_rows = read_jsonl(os.path.join(outdir, "health.json"))
    health = health_rows[0] if health_rows else None
    summary = build_summary(records, rows, spec, blob, health)
    old_path = os.path.join(outdir, "summary.json")
    old = json.load(open(old_path, encoding="utf-8")) if os.path.exists(old_path) else {}
    for keep in ("transport", "dispatch_wall_s"):
        if keep in old:
            summary[keep] = old[keep]
    with open(old_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"rescored: tier={summary['verdict']} dispatched={summary['dispatched']}")
    return 0


def do_check_readme(outdir: str) -> int:
    with open(os.path.join(outdir, "gate.json"), encoding="utf-8") as fh:
        spec = json.load(fh)
    blob = spec["blob"]
    with open(os.path.join(outdir, "README.md"), encoding="utf-8") as fh:
        text = fh.read()
    failures = readme_failures(text, spec, blob)
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
    p.add_argument("--panel", choices=sorted(PANELS) + ["auto"], default="auto")
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
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

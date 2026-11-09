#!/usr/bin/env python3
"""Round 53 probe: is the 1,556-token stop a property of the traversal or a budget in the serving stack?

Question (issue #71, #94, #100, #105, #126). Two firings on one deployment (round 49, 36 records,
and round 51, 20 records) stopped at exactly 1,556 completion tokens whenever the model kept
reasoning, and never at the 2,048-token protocol cap, while two firings on other deployments
(rounds 48 and 50) reached the cap with `finish_reason = length` in five records each and never
showed the pin. In every pinned record the archived reasoning text ends with one literal English
sentence, `I have thought about this long enough; time to give my answer.`, preceded by a
mid-token or mid-line cut. Round 49 computed the ratio itself - its `mechanics.budget_utilisation`
is 0.7598 = 1556 / 2048 on all 33 pinned records and nowhere else - and nothing in the round read
it as a budget. The pin also ignores prompt size: round 49's prompts are ~2,900 prompt tokens,
round 51's load-floor prompts ~700, both pinned at 1556 with the same requested cap.

This instrument holds the prompt bytes fixed and moves only the requested cap, so the two
candidate mechanisms make opposite predictions on the same items:

  H1 proportional budget  the stop lands at 1556 * cap / 2048 with `finish_reason = stop` and the
      marker sentence present at every cap, because the stack reserves a fixed share of the
      requested budget for the answer and forces the transition when reasoning reaches it.
  H2 absolute budget      for every cap below 1556 the output reaches the cap itself with
      `finish_reason = length`, no marker and no answer, because the budget is a fixed token
      count the server never lets the run reach; at cap 2048 the pin and the marker reappear.
  H3 no serving budget    lengths track the task, the marker appears wherever the model writes it,
      and the pin is a property of this family on this class (which is how rounds 49 and 51 read it).

The readout that decides the point is therefore the *cap ladder below the pin*, on prompts certified
byte-identical to round 51's archived records (regenerated from the shipped generator and digested
against the archived digests before any dispatch). Two secondary arms are dispatched: the same
listing task at two caps (a non-ladder control that any budget must cut, so the hook cannot be a
property of the ladder family), and the two items round 51 delivered *wrong* under an arm that asks
for the reachable set before the answer, whose list is then checked against an independent BFS.

Dispatch budget: 15 calls of the 40-call cap, temperature 0, every requested cap at or below the
2048 protocol cap, a wall-clock guard on the dispatch phase. The gate rows, their bands and the
tier rule are frozen in gate.json before the first prompt and the blob is pinned below.

Archived reference: quoted from the four pending round directories (branches
research/nightly-2026-11-05-0229 #125, origin/research/nightly-2026-11-05-0400 #127,
research/nightly-2026-11-06-0259 #128, research/nightly-2026-11-06-0433 #130), none of which is on
`main` yet, so the rows are vendored as constants with the sha256 of each archived raw.jsonl beside
them, and no verdict of this round depends on them.

No endpoint value (base URL, model id, key) is ever written: artifacts carry a one-way digest of
the serving id and every string passes the sanitizer first.

Usage:
  budget_hook_probe.py --selftest
  budget_hook_probe.py --gate
  budget_hook_probe.py --dry-run
  NIGHTLY_BASE_URL=... NIGHTLY_MODEL_ID=... NIGHTLY_API_KEY=... budget_hook_probe.py --run
  budget_hook_probe.py --rescore    (rebuild gate+summary from raw.jsonl, no endpoint call)
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
from collections import deque
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "generators"))

import ladders  # noqa: E402  (the shipped generator, repaired by PR #69)

SEED_BASE = 20261005          # round 51's seed base, kept so the items are the same items
SCAN = 400
LEVEL = 48                    # round 51's deepest certified load-floor cell
MAX_TOKENS = 2048             # protocol cap: no requested cap may exceed it
CALL_CAP = 40
TIMEOUT_S = 600
DISPATCH_BUDGET_S = 900       # wall-clock guard on the dispatch phase
GATE_SCHEMA = "round53-gate-v1"

PIN_TOKENS = 1556             # the archived pin (rounds 49 and 51, cap 2048)
PIN_CAP = 2048
HOOK_BAND = 8                 # tokens: |measured - predicted| for a hook hit
CAPS = (512, 1024, 1536, 2048)
MARKER = "I have thought about this long enough; time to give my answer."
LISTING_MAX = 4000            # integers the non-ladder control is asked to write
LISTING_SMALL = 600           # the same control at a smaller extent (completable, so uncapped)

ROUND51_RAW_SHA256 = "fbfa4fde59f43ea3f484b4205b5beff11d2add27e6c3f60e210ca092e3452f7a"
ROUND49_RAW_SHA256 = "b140458952955711974bb2013e714cdea08dab012f2f0cf94140969c841f7f48"
ROUND50_RAW_SHA256 = "e2a9d47ecb69e40e4e908df9adf20362ea6f9ff9e0430516148a5e4c8021041f"
ROUND48_RAW_SHA256 = "736d93119b9748b189d98aed59172bc54d79f5371bb19b25ee57811192de31fb"

# Trace exposure quoted from each archive's own per-record census field (issue #105): the message
# field names the endpoint supplied and the field that supplied the reasoning text. `text_stored` is
# whether that directory keeps the reasoning text itself, which is what makes a marker count
# evaluable there at all. Round 48 characterizes its `reasoning` field by length (census
# `reasoning_field_chars`) but archives none of its text, so no marker count is quotable from it.
TRACE_EXPOSURE = {
    "round 49": {"fields": ("content", "reasoning_content", "role"),
                 "reasoning_source": "reasoning_content", "text_stored": True},
    "round 51": {"fields": ("content", "reasoning_content"),
                 "reasoning_source": "reasoning_content", "text_stored": True},
    "round 50": {"fields": ("content", "reasoning_content", "role"),
                 "reasoning_source": "reasoning_content", "text_stored": True},
    "round 48": {"fields": ("audio", "content", "function_call", "reasoning", "refusal", "role"),
                 "reasoning_source": "reasoning", "text_stored": False},
}

# Vendored archived rows, extracted programmatically from the four pending round directories.
# ROUND51_GRID: (seed, gold, facts, prompt_sha16, completion_tokens, requested cap, finish,
#                marker_in_trace, answer_channel_readout, correct). Stage-1 grid rows only.
ROUND51_GRID = (
    (68261051, 'no', 48, 'ab8097b385a6e84e', 1556, 2048, 'stop', 1, 'no', 1),
    (68261092, 'no', 48, '0e080296a1ba1f5b', 1556, 2048, 'stop', 1, 'no', 1),
    (68261108, 'yes', 48, '40e3dfb191140791', 771, 2048, 'stop', 0, 'yes', 1),
    (68261194, 'yes', 48, '61dd9aaebb1d42c8', 666, 2048, 'stop', 0, 'yes', 1),
    (84261011, 'no', 64, 'd6b9e74cf69a8e28', 1556, 2048, 'stop', 1, 'no', 1),
    (84261050, 'no', 64, '0d3347946e358ce5', 1556, 2048, 'stop', 1, 'yes', 0),
    (84261142, 'yes', 64, 'e9615dd04c8c87a2', 985, 2048, 'stop', 0, 'yes', 1),
    (84261174, 'yes', 64, '766d6e09cba617c4', 845, 2048, 'stop', 0, 'yes', 1),
    (100261062, 'yes', 80, 'e80ea59e1f32f2b5', 1153, 2048, 'stop', 0, 'yes', 1),
    (100261101, 'yes', 80, '7937eadc8a8cad36', 1059, 2048, 'stop', 0, 'yes', 1),
    (100261153, 'no', 80, '76009aa8c4b886e5', 1556, 2048, 'stop', 1, 'no', 1),
    (100261309, 'no', 80, '69ad228f8fed1e75', 1556, 2048, 'stop', 1, 'no', 1),
    (116261051, 'no', 96, '068bc6a1fb0620fb', 1556, 2048, 'stop', 1, 'yes', 0),
    (116261076, 'no', 96, 'ffc75c928f37f0d9', 1556, 2048, 'stop', 1, 'yes', 0),
    (116261338, 'yes', 96, '87e36020f5c31c93', 1310, 2048, 'stop', 0, 'yes', 1),
    (116261360, 'yes', 96, '651e3f1737483f12', 1509, 2048, 'stop', 0, 'yes', 1),
)
# ROUND51_LADDER: (seed, requested rung, completion_tokens, finish_reason, marker_in_trace,
#                  answer_channel_readout). Round 51's stage 2, the same items at rungs below the
# pin: two reached their rung with no marker, one stopped early *with* a marker at 532 tokens where
# the proportional prediction was 778 (the archive-side anomaly the C9 row counts).
ROUND51_LADDER = (
    (116261338, 1024, 532, 'stop', 1, 'yes'),
    (116261338, 640, 640, 'length', 0, None),
    (100261062, 896, 876, 'stop', 0, 'yes'),
    (100261062, 576, 576, 'length', 0, None),
)
# ROUND49_RECORDS: (mode, arm, k, seed, gold, answer_channel_readout, completion_tokens, finish,
#                   marker_in_text, budget_utilisation). The cap was 2048 throughout.
ROUND49_RECORDS = (
    ('A', 'F', 12, 32421025, 1, 'no', 1556, 'stop', 1, 0.7598),
    ('A', 'F', 12, 32421026, 1, 'yes', 1556, 'stop', 1, 0.7598),
    ('A', 'F', 16, 36381025, 1, 'yes', 1556, 'stop', 1, 0.7598),
    ('A', 'F', 16, 36381027, 1, 'yes', 551, 'stop', 0, 0.269),
    ('A', 'X', 8, 28501026, 0, 'yes', 1556, 'stop', 1, 0.7598),
    ('A', 'X', 8, 28501028, 0, 'yes', 1556, 'stop', 1, 0.7598),
    ('A', 'X', 12, 32421024, 0, 'yes', 1556, 'stop', 1, 0.7598),
    ('A', 'X', 12, 32421025, 0, 'yes', 1556, 'stop', 1, 0.7598),
    ('A', 'X', 16, 36381024, 0, 'yes', 1556, 'stop', 1, 0.7598),
    ('A', 'X', 16, 36381025, 0, 'yes', 1556, 'stop', 1, 0.7598),
    ('A', 'X', 16, 36381027, 0, 'yes', 1556, 'stop', 1, 0.7598),
    ('A2', 'X', 8, 28501026, 0, 'yes', 1556, 'stop', 1, 0.7598),
    ('A2', 'X', 12, 32421024, 0, 'yes', 1556, 'stop', 1, 0.7598),
    ('A2', 'X', 16, 36381024, 0, 'yes', 1556, 'stop', 1, 0.7598),
    ('C', 'F', 12, 32421025, 1, 'yes', 1556, 'stop', 1, 0.7598),
    ('C', 'F', 12, 32421026, 1, 'yes', 495, 'stop', 0, 0.2417),
    ('C', 'F', 16, 36381025, 1, 'yes', 932, 'stop', 0, 0.4551),
    ('C', 'F', 16, 36381027, 1, 'yes', 1556, 'stop', 1, 0.7598),
    ('C', 'X', 8, 28501028, 0, 'yes', 1556, 'stop', 1, 0.7598),
    ('C', 'X', 8, 28501026, 0, 'yes', 1556, 'stop', 1, 0.7598),
    ('C', 'X', 12, 32421024, 0, 'yes', 1556, 'stop', 1, 0.7598),
    ('C', 'X', 12, 32421025, 0, 'yes', 1556, 'stop', 1, 0.7598),
    ('C', 'X', 16, 36381024, 0, 'yes', 1556, 'stop', 1, 0.7598),
    ('C', 'X', 16, 36381025, 0, 'yes', 1556, 'stop', 1, 0.7598),
    ('C', 'X', 16, 36381027, 0, 'yes', 1556, 'stop', 1, 0.7598),
    ('D', 'F', 12, 32421025, 1, 'no', 1556, 'stop', 1, 0.7598),
    ('D', 'F', 12, 32421026, 1, 'yes', 1556, 'stop', 1, 0.7598),
    ('D', 'F', 16, 36381025, 1, 'yes', 1556, 'stop', 1, 0.7598),
    ('D', 'F', 16, 36381027, 1, 'yes', 1556, 'stop', 1, 0.7598),
    ('D', 'X', 8, 28501026, 0, 'yes', 1556, 'stop', 1, 0.7598),
    ('D', 'X', 8, 28501028, 0, 'no', 1556, 'stop', 1, 0.7598),
    ('D', 'X', 12, 32421024, 0, 'yes', 1556, 'stop', 1, 0.7598),
    ('D', 'X', 12, 32421025, 0, 'no', 1556, 'stop', 1, 0.7598),
    ('D', 'X', 16, 36381024, 0, 'yes', 1556, 'stop', 1, 0.7598),
    ('D', 'X', 16, 36381025, 0, 'no', 1556, 'stop', 1, 0.7598),
    ('D', 'X', 16, 36381027, 0, 'yes', 1556, 'stop', 1, 0.7598),
)
# ROUND50_RECORDS: (completion_tokens, finish_reason, marker_in_text). Other firing, other
# deployment, cap 2048.  ROUND48_RECORDS: same shape; that archive stores no reasoning text, so
# its marker column is not evaluable there and is recorded as 0 with `text_archived` false.
ROUND50_RECORDS = (
    (191, 'stop', 0), (246, 'stop', 0), (371, 'stop', 0), (447, 'stop', 0), (515, 'stop', 0),
    (670, 'stop', 0), (674, 'stop', 0), (682, 'stop', 0), (682, 'stop', 0), (706, 'stop', 0),
    (710, 'stop', 0), (735, 'stop', 0), (804, 'stop', 0), (861, 'stop', 0), (861, 'stop', 0),
    (862, 'stop', 0), (928, 'stop', 0), (988, 'stop', 0), (988, 'stop', 0), (1001, 'stop', 0),
    (1140, 'stop', 0), (1221, 'stop', 0), (1646, 'stop', 0), (1846, 'stop', 0), (1975, 'stop', 0),
    (2021, 'stop', 0), (2048, 'length', 0), (2048, 'length', 0), (2048, 'length', 0),
    (2048, 'length', 0), (2048, 'length', 0),
)
ROUND48_RECORDS = (
    (255, 'stop', 0), (259, 'stop', 0), (269, 'stop', 0), (272, 'stop', 0), (311, 'stop', 0),
    (319, 'stop', 0), (359, 'stop', 0), (377, 'stop', 0), (379, 'stop', 0), (387, 'stop', 0),
    (388, 'stop', 0), (567, 'stop', 0), (596, 'stop', 0), (596, 'stop', 0), (642, 'stop', 0),
    (679, 'stop', 0), (702, 'stop', 0), (717, 'stop', 0), (797, 'stop', 0), (807, 'stop', 0),
    (833, 'stop', 0), (945, 'stop', 0), (974, 'stop', 0), (993, 'stop', 0), (1124, 'stop', 0),
    (1192, 'stop', 0), (1250, 'stop', 0), (1473, 'stop', 0), (1588, 'stop', 0), (1628, 'stop', 0),
    (1646, 'stop', 0), (2048, 'length', 0), (2048, 'length', 0), (2048, 'length', 0),
    (2048, 'length', 0), (2048, 'length', 0),
)

IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV6 = re.compile(r"\b(?:[0-9a-fA-F]{0,4}:){2,}[0-9a-fA-F]{0,4}\b")
URLISH = re.compile(r"\bhttps?://[^\s\"']+")
SENSITIVE = re.compile(r"(?i)\b(host|token|secret|key)\b\s*[:=]\s*\S+")
YES_NO = re.compile(r"\b(yes|no)\b", re.IGNORECASE)
ENTITY_RE = re.compile(r"^[a-z][a-z0-9]{2,15}$")
CENSUS_PROMPT = ("Rule: for all x, y, z: if x precedes y and y precedes z, then x precedes z. "
                 "Facts: alby precedes birch. birch precedes cobin. Question: does alby precedes "
                 "cobin? Answer with exactly one word: yes or no.")

# Items this round dispatches: round 51's certified k = 48 load-floor pair that it delivered
# *wrong* (gold "no", answer channel "yes"), plus the gold-yes item whose archived natural stop
# (1310) sits below the pin, which is the no-hook control at cap 2048.
PINNED_SEEDS = (116261051, 116261076, 116261338)
PAIR_SEEDS = (116261051, 116261076)   # the pair round 51 delivered wrong

ROUND53_GATE_BLOB_SHA256 = "1f78366a0d610f12e03b3f46c4ab8e6ee21c9301d5a51e452758dd3998b9ae8c"


# ---------------------------------------------------------------- solver and items

def bfs_reachable(facts: list, src: str) -> dict:
    """Independent solver: unbounded directed BFS, node -> distance (src at 0)."""
    graph: dict = {}
    for s, _, t in facts:
        graph.setdefault(s, []).append(t)
    dist = {src: 0}
    q = deque([src])
    while q:
        u = q.popleft()
        for v in graph.get(u, ()):
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist


def weak_components(facts: list) -> list:
    graph: dict = {}
    for s, _, t in facts:
        graph.setdefault(s, []).append(t)
        graph.setdefault(t, []).append(s)
    seen: set = set()
    out: list = []
    for node in graph:
        if node in seen:
            continue
        comp = {node}
        seen.add(node)
        q = deque([node])
        while q:
            u = q.popleft()
            for v in graph[u]:
                if v not in seen:
                    seen.add(v)
                    comp.add(v)
                    q.append(v)
        out.append(comp)
    return out


def check_item(item: dict) -> None:
    """Refuse anything that is not the repaired (component-isomorphic) load-floor corpus."""
    lvl = item["level"]
    facts = item["facts"]
    assert len(facts) == 2 * lvl, ("not a load-floor item", lvl, len(facts))
    assert all(rel == ladders.REL for _, rel, _ in facts), item
    comps = weak_components(facts)
    assert len(comps) == 2, ("the load floor has exactly two components", len(comps))
    for comp in comps:
        assert len(comp) == lvl + 1, ("component size", lvl, len(comp))
    srcs = [s for s, _, _ in facts]
    tgts = [t for _, _, t in facts]
    assert len(srcs) == len(set(srcs)), "an entity is a fact source twice"
    assert len(tgts) == len(set(tgts)), "an entity is a fact target twice"
    qs, _, qt = item["query"]
    assert qs in srcs and qs not in tgts, "query source is not a path head"
    assert qt in tgts and qt not in srcs, "query target is not a path tail"
    dist = bfs_reachable(facts, qs)
    assert (item["answer"] == "yes") == (qt in dist), item
    if item["answer"] == "yes":
        assert dist[qt] == lvl == item["chain_len"], item
    else:
        assert item["chain_len"] is None, item


_SERIES: dict = {}


def series(level: int) -> list:
    if level not in _SERIES:
        _SERIES[level] = ladders.generate_items(level, SCAN, SEED_BASE)
    return _SERIES[level]


def item_by_seed(seed: int) -> dict:
    for item in series(LEVEL):
        if item["seed"] == seed:
            check_item(item)
            return item
    raise RuntimeError(f"seed {seed} is not in the certified k = {LEVEL} series")


def render_prompt(item: dict) -> str:
    """The round-6 / round-50 / round-51 template, byte-identical (required for pairing)."""
    facts = "\n".join(f"{s} {r} {t}." for s, r, t in item["facts"])
    qs, qrel, qt = item["query"]
    return (f"{item['rule']}\nFacts:\n{facts}\n\n"
            f"Question: does {qs} {qrel} {qt}?\n"
            "Answer with exactly one word: yes or no.")


def render_enumerate(item: dict) -> str:
    """The search-organized arm: same facts, same query, reachable set asked for first.

    This changes what the model is asked to produce, so it can never show that the as-is task is
    solvable at k = 48. It only tests whether an as-is failure co-occurs with a search the model
    had to organize for itself, and the list it produces is checked against an independent BFS.
    """
    facts = "\n".join(f"{s} {r} {t}." for s, r, t in item["facts"])
    qs, qrel, qt = item["query"]
    return (f"{item['rule']}\nFacts:\n{facts}\n\n"
            f"Task: list every entity reachable from {qs} by applying the rule to the Facts, one "
            f"entity per line, starting with {qs} itself, then the entities in the order you reach "
            "them. Finish the whole list before you answer. After the list write one final line "
            "containing exactly one word: yes or no. "
            f"Question: does {qs} {qrel} {qt}?")


def render_listing(count: int) -> str:
    """Non-ladder control: a task with no relation, no entities and no ladder, that any length
    budget must cut off and that no traversal explains."""
    return (f"Write every integer from 1 to {count}, one per line, in increasing order, and write "
            "nothing else. After the last integer write a final line containing exactly one word: "
            "DONE.")


def prompt_digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def predicted_hook(cap: int) -> int:
    """The proportional prediction: the archived pin scaled to the requested cap."""
    return PIN_TOKENS * cap // PIN_CAP


# ---------------------------------------------------------------- text measures

def marker_positions(text: str) -> list:
    out, i = [], 0
    while True:
        j = text.find(MARKER, i)
        if j < 0:
            return out
        out.append(j)
        i = j + 1


def marker_tail(text: str, pos: int) -> str:
    """The 60 characters that end immediately before the marker (the cut signature)."""
    return text[max(0, pos - 60):pos]


def answer_channel_readout(content: str) -> tuple:
    """The answer field only (issue #94): last standalone yes/no plus an echo guard.

    The instruction itself contains the words yes and no, so a readout lifted from a content
    string that is still quoting the instruction is refused as an instruction echo.
    """
    hits = YES_NO.findall(content or "")
    if not hits:
        return None, "none"
    answer = hits[-1].lower()
    stripped = (content or "").strip().lower()
    if stripped in ("yes or no", "answer with exactly one word: yes or no", "yes or no."):
        return answer, "instruction_echo"
    return answer, "content"


def entity_vocabulary(item: dict) -> set:
    vocab = set()
    for s, _, t in item["facts"]:
        vocab.add(s)
        vocab.add(t)
    qs, _, qt = item["query"]
    vocab.add(qs)
    vocab.add(qt)
    return vocab


def parse_listed_entities(text: str, vocab: set) -> list:
    """Whole-line entity listings, in order, deduplicated: the enumerate arm's readout."""
    seen, out = set(), []
    for raw in text.splitlines():
        token = raw.strip().strip(".,:*-()").lower()
        if not token or token in ("yes", "no") or not ENTITY_RE.match(token):
            continue
        if token in vocab and token not in seen:
            seen.add(token)
            out.append(token)
    return out


def measure_listing(text: str) -> dict:
    """Objective measures of the non-ladder control: which integers actually reached the text."""
    nums = [int(m) for m in re.findall(r"\b\d{1,5}\b", text or "")]
    uniq = sorted(set(nums))
    done = bool(re.search(r"\bDONE\b", text or ""))
    missing = 0
    if uniq:
        missing = sum(1 for v in range(1, uniq[-1] + 1) if v not in set(uniq))
    return {"numbers_found": len(nums), "distinct_numbers": len(uniq),
            "max_number": uniq[-1] if uniq else 0, "missing_in_range": missing,
            "done_present": done}


def coverage_measures(item: dict, text: str) -> dict:
    """How much of the item the run touched before it stopped (reported, never gated)."""
    vocab = entity_vocabulary(item)
    qs, _, qt = item["query"]
    dist = bfs_reachable(item["facts"], qs)
    reachable = set(dist)
    mentioned = {e for e in vocab if re.search(rf"\b{re.escape(e)}\b", text or "")}
    return {"entities_in_item": len(vocab), "entities_mentioned": len(mentioned),
            "coverage_ratio": round(len(mentioned) / len(vocab), 4),
            "reachable_from_source": len(reachable),
            "query_source_mentioned": qs in mentioned,
            "query_target_mentioned": qt in mentioned,
            "target_is_reachable": qt in reachable}


# ---------------------------------------------------------------- transport

def sanitize(text: str, secrets: tuple = ()) -> str:
    """Public-only rule: no endpoint value, host, IP, URL or credential reaches a file."""
    out = text if text is not None else ""
    for secret in secrets:
        if secret:
            out = out.replace(str(secret), "[redacted]")
    out = URLISH.sub("[redacted-url]", out)
    out = IPV4.sub("[redacted-ip]", out)
    out = IPV6.sub("[redacted-ip]", out)
    out = SENSITIVE.sub("[redacted-credential]", out)
    return out


def call_endpoint(prompt: str, base: str, model: str, key: str, max_tokens: int) -> dict:
    """One chat completion. Returns the payload and wall time or raises RuntimeError."""
    body = json.dumps({"model": model,
                       "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0.0,
                       "max_tokens": max_tokens}).encode()
    headers = {"Content-Type": "application/json"}
    if key:  # a local slot that serves without a credential has key == ""
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body, headers=headers)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"transport:{type(exc).__name__}") from exc
    return {"payload": payload, "wall_s": round(time.time() - t0, 3)}


def census_of(payload: dict) -> dict:
    """Field census (issue #105): which field supplies the reasoning channel."""
    try:
        msg = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        msg = {}
    fields = sorted(k for k in msg if k != "role")
    rc = msg.get("reasoning_content") or ""
    rf = msg.get("reasoning") or ""
    source = "reasoning_content" if rc else ("reasoning" if rf else "")
    return {"fields": fields, "reasoning_content_chars": len(rc),
            "reasoning_field_chars": len(rf), "reasoning_source": source}


def channels_of(payload: dict) -> tuple:
    try:
        choices = payload.get("choices") or []
        choice = choices[0] if choices else {}
        msg = choice.get("message") if isinstance(choice, dict) else {}
        if not isinstance(msg, dict):
            msg = {}
    except (AttributeError, IndexError, TypeError):
        choice, msg = {}, {}
    content = msg.get("content") or ""
    if isinstance(content, list):
        content = "".join(str(p.get("text", "")) if isinstance(p, dict) else str(p) for p in content)
    trace = msg.get("reasoning_content") or msg.get("reasoning") or ""
    finish = choice.get("finish_reason") if isinstance(choice, dict) else None
    usage = payload.get("usage") or {}
    return content, trace, finish, usage


# ---------------------------------------------------------------- classification

def classify(tokens, cap, finish, marker_count) -> str:
    """The one classification every dispatched record passes through.

    Mutually exclusive, and the alternative-hypothesis row (absolute budget) is read off the same
    classification, never off a separate count: a record is either at the predicted hook, or at the
    cap without a marker, or a natural stop, or an anomaly.
    """
    if tokens is None:
        return "transport_error"
    pred = predicted_hook(cap)
    if marker_count == 0 and tokens >= cap:
        return "alt_absolute_cap_no_marker" if cap < PIN_TOKENS else "censored_at_protocol_cap"
    if marker_count == 1 and abs(tokens - pred) <= HOOK_BAND:
        return "hook_hit_predicted"
    if marker_count == 1 and tokens < pred - HOOK_BAND:
        return "marker_below_predicted_hook"
    if marker_count == 1 and tokens > pred + HOOK_BAND:
        return "marker_above_predicted_hook"
    if marker_count == 0 and tokens < pred - HOOK_BAND:
        return "natural_stop_no_marker"
    if marker_count == 0:
        return "no_marker_near_hook"
    return "marker_anomaly_count_gt1"


def join_key(rec: dict) -> str:
    """Duplicate pairing on the request, not on a dispatch label."""
    return f"{rec['arm']}|{rec['seed']}|{rec['requested_cap']}|{rec['prompt_sha256'][:16]}"


# ---------------------------------------------------------------- gate

def gate_spec() -> dict:
    items = {"as_is": "the round-6/50/51 template, certified byte-identical to the archived rows",
             "enumerate": "same facts, same query, reachable set asked for first (a task variant: "
                          "it cannot show the as-is task is solvable, only whether an as-is failure "
                          "co-occurs with a self-organized search)",
             "listing": "non-ladder control, no relation and no entities, asked to write 1..4000 "
                        "and then DONE"}
    return {
        "schema": GATE_SCHEMA,
        "question_blob": (
            "Does the 1,556-token stop that two firings on this deployment produced at the 2048 cap "
            "come from the traversal or from a budget in the serving stack? Hold the prompt bytes "
            "fixed, move the requested cap to 512, 1024 and 1536, and ask whether the stop length "
            "and the self-termination marker move with the cap."
        ),
        "hypotheses": {
            "H1_proportional_budget": f"the stop lands at {PIN_TOKENS}*cap//{PIN_CAP} "
                                      f"(band {HOOK_BAND} tokens) with finish_reason stop and the "
                                      "marker sentence present at every cap",
            "H2_absolute_budget": "for every cap below the pin the output reaches the cap itself "
                                  "with finish_reason length, no marker and no answer",
            "H3_no_serving_budget": "lengths track the task; the marker appears wherever the model "
                                    "writes it; the pin is a property of the family on the class",
        },
        "budget": {"call_cap": CALL_CAP, "dispatch_budget_s": DISPATCH_BUDGET_S,
                   "max_tokens_cap": MAX_TOKENS, "temperature": 0.0,
                   "caps": list(CAPS), "planned_calls": 15},
        "dispatch_order": ("health, cap-2048 as-is pair, duplicate control, gold-yes natural-stop "
                           "control, enumerate pair, listing at 2048, cap-1536 pair, listing at "
                           "1024, cap-1024 pair, cap-512 pair: the decisive same-prompt anchors go "
                           "first so a wall-clock cutoff costs the low-cap rungs and not the "
                           "replication"),
        "items": {"rule": "three seeds certified against the archived digests before any dispatch: "
                          "the two k = 48 gold-no items round 51 delivered wrong, and the gold-yes "
                          "item whose archived natural stop 1310 sits below the pin",
                  "level": LEVEL, "seed_base": SEED_BASE, "facts": 2 * LEVEL},
        "arms": items,
        "rows": [
            {"id": "C1", "kind": "predicted", "text": "the cap ladder below the pin lands at the "
             "predicted hook: 6 records (2 items x caps 512, 1024, 1536), measured tokens within "
             f"{HOOK_BAND} of {PIN_TOKENS}*cap//{PIN_CAP}, finish_reason stop, marker present",
             "band": "6 of 6", "admits_tier": ["serving_budget_hook"]},
            {"id": "C2", "kind": "alternative", "text": "the absolute-budget signature at the same "
             "6 records: tokens equal the requested cap, finish_reason length, no marker",
             "band": "reported; 5 of 6 or more refuses C1 and the H1 reading",
             "admits_tier": ["absolute_pin"]},
            {"id": "C3", "kind": "predicted", "text": "the marker appears in every predicted-hook "
             "record and in no natural-stop record (0 disagreements)",
             "band": "0 disagreements", "admits_tier": ["serving_budget_hook"]},
            {"id": "C4", "kind": "control", "text": "the gold-yes item whose archived natural stop "
             "was 1310 stays below the hook at cap 2048: delivered, finish_reason stop, no marker, "
             "tokens below 1556", "band": "1 of 1", "admits_tier": ["serving_budget_hook"]},
            {"id": "C5", "kind": "control", "text": "the non-ladder listing control is cut by the "
             "same hook at caps 2048 and 1024 (predicted lengths, marker present, DONE absent)",
             "band": "2 of 2", "admits_tier": ["serving_budget_hook"]},
            {"id": "C6", "kind": "mechanism", "text": "the enumerate arm delivers the gold label on "
             "both items round 51 delivered wrong, and its own list equals the independent BFS "
             "reachable set", "band": "2 of 2 for the recovery flag; 0 of 2 keeps the ceiling",
             "admits_tier": []},
            {"id": "C7", "kind": "control", "text": "issue #100 self-agreement: the duplicate "
             "re-dispatch of the same request is byte-identical to its twin (trace and answer)",
             "band": "1 of 1", "admits_tier": []},
            {"id": "C8", "kind": "control", "text": "same-prompt cross-firing against the archived "
             "rows of round 51 on the certified pair: same finish_reason and same answer-channel "
             "readout for both items, with the serving-id digest comparison stated",
             "band": "2 of 2", "admits_tier": []},
            {"id": "C9", "kind": "anomaly", "text": "markers that appear below the predicted hook "
             "are counted as anomalies, never as hook hits (round 51's archived rung record is one: "
             "marker at 532 tokens where the prediction was 778)", "band": "reported",
             "admits_tier": []},
            {"id": "N1", "kind": "census", "text": "issue #105 field census on every record: the "
             "message field names and the reasoning-supplying field (reasoning_content if "
             "non-empty, else reasoning, else empty)", "band": "every record censused",
             "admits_tier": []},
            {"id": "R1", "kind": "reported", "text": "traversal completeness at the hook, as-is "
             "cap-2048 records only: the fraction of the item's entities the run mentioned before "
             "the cut, and whether the query target was mentioned", "band": "reported",
             "admits_tier": []},
        ],
        "tier_rule": [
            "serving_budget_hook if C1 >= 5 of 6 and C2 <= 1 of 6 and C5 == 2 of 2",
            "absolute_pin if C2 >= 5 of 6",
            "no_serving_budget if C1 <= 2 of 6 and C5 == 0 of 2",
            "unresolved otherwise",
        ],
        "flags": [
            "C6 == 2 of 2 AND tier serving_budget_hook -> enumerate_arm_recovers_label_and_tier_is_hook",
            "C9 > 0 -> marker_not_locked_to_predicted_hook",
            "R1 coverage_ratio < 1.0 in both as-is cap-2048 records -> traversal_unfinished_at_hook",
        ],
        "readout_policy": ("the answer channel only for every verdict (issue #94); trace text is "
                           "stored for marker position, listing extent and entity coverage only, "
                           "never as a verdict"),
        "archived_reference": {
            "note": "quoted from four round directories that are open PRs, not main; vendored "
                    "because the post-merge tree, not this firing, is what certifies them; no "
                    "verdict of this round depends on them",
            "branches": {"round 48": "research/nightly-2026-11-05-0229 (#125)",
                         "round 49": "origin/research/nightly-2026-11-05-0400 (#127)",
                         "round 50": "research/nightly-2026-11-06-0259 (#128)",
                         "round 51": "research/nightly-2026-11-06-0433 (#130)"},
            "raw_sha256": {"round 48": ROUND48_RAW_SHA256, "round 49": ROUND49_RAW_SHA256,
                           "round 50": ROUND50_RAW_SHA256, "round 51": ROUND51_RAW_SHA256},
            "pin_signature": {"round 49": {"records": 36, "at_pin": 33, "at_cap": 0,
                                           "marker": 33, "utilisations_at_pin": [0.7598]},
                              "round 51": {"records": 20, "at_pin": 8, "at_cap": 0, "marker": 9,
                                           "utilisations_at_pin": [0.7598]},
                              "round 50": {"records": 31, "at_pin": 0, "at_cap": 5, "marker": 0,
                                           "utilisations_at_pin": []},
                              "round 48": {"records": 36, "at_pin": 0, "at_cap": 5, "marker": None,
                                           "utilisations_at_pin": []}},
            # Quoted from each archive's own per-record census field (issue #105): the message field
            # names and the reasoning-supplying field. `text_stored` is whether that directory keeps
            # the reasoning text itself, which is what makes a marker count evaluable at all; round
            # 48 characterizes its reasoning field (census `reasoning_field_chars`) but stores no
            # reasoning text, so no marker count is quotable there and its marker is recorded as not
            # evaluable.
            "trace_exposure": TRACE_EXPOSURE,
        },
    }


def gate_blob_sha256() -> str:
    return hashlib.sha256(json.dumps(gate_spec(), sort_keys=True).encode()).hexdigest()


def certify_items() -> dict:
    """Regenerate the three dispatched items and refuse unless every archived digest reproduces."""
    out = {"ok": True, "certified": 0, "refused": []}
    for seed, gold, facts, sha16, *_rest in ROUND51_GRID:
        if seed not in PINNED_SEEDS:
            continue
        item = item_by_seed(seed)
        digest = prompt_digest(render_prompt(item))
        ok = (digest == sha16 and item["answer"] == gold and len(item["facts"]) == facts)
        if ok:
            out["certified"] += 1
        else:
            out["refused"].append({"seed": seed, "expected": sha16, "got": digest,
                                   "gold_expected": gold, "gold_got": item["answer"],
                                   "facts_expected": facts, "facts_got": len(item["facts"])})
    out["certified"] = min(out["certified"], len(PINNED_SEEDS))
    if out["refused"] or out["certified"] != len(PINNED_SEEDS):
        out["ok"] = False
    return out


def certify_archive() -> dict:
    """The quoted archive rows must reproduce their own quoted aggregates (issue #120 discipline).

    Every count the README quotes from the four pending directories is emitted here from the
    vendored rows and asserted against the value stated in gate.json.
    """
    def tally(rows, cap_column, marker_column, cap):
        return sum(1 for r in rows if r[cap_column] == cap), sum(1 for r in rows
                                                                 if r[marker_column] == 1)
    r49_pin, r49_mark = tally(ROUND49_RECORDS, 6, 8, PIN_TOKENS)
    r51_pin = sum(1 for r in ROUND51_GRID if r[4] == PIN_TOKENS)
    r51_pin += sum(1 for r in ROUND51_LADDER if r[2] == PIN_TOKENS)
    r51_mark = sum(1 for r in ROUND51_GRID if r[7] == 1)
    r51_mark += sum(1 for r in ROUND51_LADDER if r[4] == 1)
    util51 = sorted({round(r[4] / r[5], 4) for r in ROUND51_GRID if r[4] == PIN_TOKENS})
    r50_cap, r50_mark = tally(ROUND50_RECORDS, 0, 2, MAX_TOKENS)
    r48_cap, r48_mark = tally(ROUND48_RECORDS, 0, 2, MAX_TOKENS)
    util49 = sorted({r[9] for r in ROUND49_RECORDS if r[6] == PIN_TOKENS})
    measured = {
        "round 49": {"records": len(ROUND49_RECORDS), "at_pin": r49_pin,
                     "at_cap": sum(1 for r in ROUND49_RECORDS if r[6] == MAX_TOKENS),
                     "marker": r49_mark, "utilisations_at_pin": util49},
        "round 51": {"records": len(ROUND51_GRID) + len(ROUND51_LADDER), "at_pin": r51_pin,
                     "at_cap": sum(1 for r in ROUND51_GRID if r[4] == MAX_TOKENS),
                     "marker": r51_mark, "utilisations_at_pin": util51},
        "round 50": {"records": len(ROUND50_RECORDS), "at_pin": sum(1 for r in ROUND50_RECORDS
                                                                    if r[0] == PIN_TOKENS),
                     "at_cap": r50_cap, "marker": r50_mark, "utilisations_at_pin": []},
        "round 48": {"records": len(ROUND48_RECORDS), "at_pin": sum(1 for r in ROUND48_RECORDS
                                                                    if r[0] == PIN_TOKENS),
                     "at_cap": r48_cap, "marker": None, "utilisations_at_pin": []},
    }
    stated = gate_spec()["archived_reference"]["pin_signature"]
    problems = []
    for name, want in stated.items():
        got = measured[name]
        for key, value in want.items():
            if key == "marker" and value is None:
                continue
            if key == "marker" and got["marker"] is None:
                continue
            if got.get(key) != value:
                problems.append({"round": name, "field": key, "stated": value, "measured": got.get(key)})
    # The ratio claim: 1556 / 2048 rounded to four places must equal every archived utilisation.
    ratio = round(PIN_TOKENS / PIN_CAP, 4)
    if util49 and util49 != [ratio]:
        problems.append({"round": "round 49", "field": "ratio_recomputation",
                         "stated": ratio, "measured": util49})
    # Trace-exposure rule (issue #105): a marker count is quotable only where that archive stores the
    # reasoning text; where it does not, the marker must be recorded as not evaluable.
    for name, want in stated.items():
        exposure = TRACE_EXPOSURE[name]
        if exposure["text_stored"]:
            if want["marker"] is None or measured[name]["marker"] is None:
                problems.append({"round": name, "field": "trace_exposure",
                                 "stated": "text stored, marker count quotable",
                                 "measured": "no marker count"})
        elif want["marker"] is not None or measured[name]["marker"] is not None:
            problems.append({"round": name, "field": "trace_exposure",
                             "stated": "no reasoning text stored, marker not evaluable",
                             "measured": "marker count present"})
    return {"ok": not problems, "problems": problems, "measured": measured,
            "pin_ratio_recomputed": ratio}


def evaluate_gate(records: list, health: dict) -> dict:
    """Gate rows evaluated from the records. A refused row carries no number (issue #120 class)."""
    ran = [r for r in records if r.get("kind") != "not_dispatched"]
    spec = gate_spec()

    def row(row_id: str, measured, passes: bool, ran_expected: int) -> dict:
        spec_row = next(r for r in spec["rows"] if r["id"] == row_id)
        if ran_expected == 0:
            return {"id": row_id, "status": "did not run", "measured": None,
                    "band": spec_row["band"], "text": spec_row["text"]}
        return {"id": row_id, "status": "pass" if passes else "fail", "measured": measured,
                "band": spec_row["band"], "text": spec_row["text"]}

    ladder = [r for r in ran if r["arm"] == "as_is" and r["requested_cap"] < MAX_TOKENS]
    c1_hits = sum(1 for r in ladder if classify(r["completion_tokens"], r["requested_cap"],
                                                 r["finish_reason"], r["marker_count"])
                   == "hook_hit_predicted")
    c2_hits = sum(1 for r in ladder if classify(r["completion_tokens"], r["requested_cap"],
                                                 r["finish_reason"], r["marker_count"])
                   == "alt_absolute_cap_no_marker")
    c1 = row("C1", f"{c1_hits} of {len(ladder)}", c1_hits >= 5 and len(ladder) >= 5, len(ladder))
    c2 = row("C2", f"{c2_hits} of {len(ladder)}", c2_hits >= 5, len(ladder))

    marker_disagree = 0
    for r in ran:
        if r["arm"] == "listing":
            pred = predicted_hook(r["requested_cap"])
            hit = r["marker_count"] == 1 and abs((r["completion_tokens"] or 0) - pred) <= HOOK_BAND
            if hit != (r["marker_count"] == 1 and r["finish_reason"] == "stop"):
                marker_disagree += 1
            continue
        if r["completion_tokens"] is None:
            continue
        pred = predicted_hook(r["requested_cap"])
        at_hook = abs(r["completion_tokens"] - pred) <= HOOK_BAND
        natural = r["completion_tokens"] < pred - HOOK_BAND and r["finish_reason"] == "stop"
        if at_hook and r["marker_count"] != 1:
            marker_disagree += 1
        if natural and r["marker_count"] != 0:
            marker_disagree += 1
    c3 = row("C3", marker_disagree, marker_disagree == 0,
             len([r for r in ran if r["completion_tokens"] is not None]))

    ctrl = [r for r in ran if r["arm"] == "as_is" and r["seed"] == 116261338
            and r["requested_cap"] == MAX_TOKENS]
    c4_ok = sum(1 for r in ctrl if r["delivered"] and r["finish_reason"] == "stop"
                and r["marker_count"] == 0
                and (r["completion_tokens"] or 0) < predicted_hook(MAX_TOKENS))
    c4 = row("C4", f"{c4_ok} of {len(ctrl)}", c4_ok == 1 and len(ctrl) == 1, len(ctrl))

    listing = [r for r in ran if r["arm"] == "listing"]
    c5_ok = 0
    for r in listing:
        pred = predicted_hook(r["requested_cap"])
        if (r["marker_count"] == 1 and r["completion_tokens"] is not None
                and abs(r["completion_tokens"] - pred) <= HOOK_BAND
                and not r["listing_measures"]["done_present"]):
            c5_ok += 1
    c5 = row("C5", f"{c5_ok} of {len(listing)}", c5_ok == 2 and len(listing) == 2, len(listing))

    enum = [r for r in ran if r["arm"] == "enumerate"]
    enum_detail = []
    c6_ok = 0
    for r in enum:
        gold_consistent = r["declared"] == r["gold"]
        list_exact = r["enumeration_measures"]["list_equals_bfs_reachable_set"] is True
        if gold_consistent and list_exact:
            c6_ok += 1
        enum_detail.append({"seed": r["seed"], "gold": r["gold"], "declared": r["declared"],
                            "gold_consistent": gold_consistent, "list_equals_bfs": list_exact,
                            "listed": r["enumeration_measures"]["listed_count"],
                            "bfs_reachable": r["enumeration_measures"]["bfs_reachable_count"],
                            "extra": r["enumeration_measures"]["extra_count"],
                            "missing": r["enumeration_measures"]["missing_count"]})
    c6 = row("C6", f"{c6_ok} of {len(enum)}", c6_ok == 2 and len(enum) == 2, len(enum))

    pairs: dict = {}
    for r in ran:
        pairs.setdefault(join_key(r), []).append(r)
    dup_pairs = 0
    dup_identical = 0
    for key, group in pairs.items():
        if len(group) < 2:
            continue
        dup_pairs += 1
        texts = {(g["trace"], g["content"]) for g in group}
        if len(texts) == 1:
            dup_identical += 1
    c7 = row("C7", f"{dup_identical} of {dup_pairs}", dup_identical == 1 and dup_pairs == 1,
             dup_pairs)

    archived = {r[0]: r for r in ROUND51_GRID}
    grouped: dict = {}
    for r in ran:
        if (r["arm"] != "as_is" or r["requested_cap"] != MAX_TOKENS
                or r["seed"] not in PAIR_SEEDS or r["seed"] not in archived):
            continue
        grouped.setdefault(r["seed"], []).append(r)
    c8_detail, c8_ok = [], 0
    for seed, group in sorted(grouped.items()):
        a = archived[seed]
        matches = [a[6] == g["finish_reason"] and a[8] == g["declared"] for g in group]
        consistent = len({(g["finish_reason"], g["declared"], g["completion_tokens"])
                          for g in group}) == 1
        if all(matches) and consistent:
            c8_ok += 1
        c8_detail.append({"seed": seed, "records": len(group), "archived_tokens": a[4],
                          "tokens": [g["completion_tokens"] for g in group],
                          "archived_finish": a[6], "finish": [g["finish_reason"] for g in group],
                          "archived_answer": a[8], "answer": [g["declared"] for g in group],
                          "all_match_archived": all(matches), "internally_consistent": consistent})
    c8 = row("C8", f"{c8_ok} of {len(grouped)}", c8_ok == 2 and len(grouped) == 2, len(grouped))

    anomalies = [r for r in ran if classify(r["completion_tokens"], r["requested_cap"],
                                            r["finish_reason"], r["marker_count"])
                 in ("marker_below_predicted_hook", "marker_above_predicted_hook",
                     "marker_anomaly_count_gt1")]
    c9 = row("C9", {"count": len(anomalies),
                    "records": [{"seed": r["seed"], "arm": r["arm"], "cap": r["requested_cap"],
                                 "tokens": r["completion_tokens"],
                                 "predicted": predicted_hook(r["requested_cap"]),
                                 "class": classify(r["completion_tokens"], r["requested_cap"],
                                                   r["finish_reason"], r["marker_count"])}
                                for r in anomalies]}, True, len(ran))

    as_is_2048 = [r for r in ran if r["arm"] == "as_is" and r["requested_cap"] == MAX_TOKENS]
    r1 = row("R1", [{"seed": r["seed"], "gold": r["gold"], "tokens": r["completion_tokens"],
                     "coverage_ratio": r["coverage_measures"]["coverage_ratio"],
                     "entities_mentioned": r["coverage_measures"]["entities_mentioned"],
                     "entities_in_item": r["coverage_measures"]["entities_in_item"],
                     "query_target_mentioned": r["coverage_measures"]["query_target_mentioned"],
                     "marker_count": r["marker_count"]} for r in as_is_2048], True, len(as_is_2048))

    census_ok = all(r.get("census") for r in ran)
    n1 = row("N1", {"records": len(ran), "censused": sum(1 for r in ran if r.get("census")),
                    "sources": sorted({(r.get("census") or {}).get("reasoning_source", "")
                                       for r in ran if r.get("census")})}, census_ok, len(ran))

    rows = {"C1": c1, "C2": c2, "C3": c3, "C4": c4, "C5": c5, "C6": c6, "C7": c7, "C8": c8,
            "C9": c9, "N1": n1, "R1": r1}

    if c1["status"] == "did not run" or c5["status"] == "did not run":
        tier = "unresolved"
    elif c2["measured"] and int(c2["measured"].split(" of ")[0]) >= 5:
        tier = "absolute_pin"
    elif (c1["status"] == "pass" and int(c1["measured"].split(" of ")[0]) >= 5
          and c2["status"] == "fail" and c5["status"] == "pass"):
        tier = "serving_budget_hook"
    elif (c1["status"] == "fail" and int(c1["measured"].split(" of ")[0]) <= 2
          and c5["status"] == "fail"):
        tier = "no_serving_budget"
    else:
        tier = "unresolved"

    flags = []
    # Every flag is gated by the code path that produces it: a flag whose condition is not met
    # here cannot reach summary.json, the README or a commit subject (issue #120 lesson).
    if c6["status"] == "pass" and tier == "serving_budget_hook":
        flags.append("enumerate_arm_recovers_label_and_tier_is_hook")
    if c9["measured"] and c9["measured"]["count"] > 0:
        flags.append("marker_not_locked_to_predicted_hook")
    pair_2048 = [r for r in as_is_2048 if r["seed"] in PAIR_SEEDS]
    coverage_lt_one = [r for r in pair_2048 if r["coverage_measures"]["coverage_ratio"] < 1.0]
    if pair_2048 and len(coverage_lt_one) == len(pair_2048):
        flags.append("traversal_unfinished_at_hook")

    health_census = health.get("census") if isinstance(health.get("census"), dict) else {}
    health_row = {"id": "H0", "status": "pass" if health.get("ok") else "fail",
                  "measured": {"ok": health.get("ok"), "tokens": health.get("completion_tokens"),
                               "finish": health.get("finish_reason"),
                               "reasoning_source": health.get("reasoning_source")
                               or health_census.get("reasoning_source"),
                               "wall_s": health.get("wall_s"), "error": health.get("error")}}
    return {"rows": rows, "tier": tier, "tier_rule": spec["tier_rule"], "flags": flags,
            "health": health_row, "enumerate_detail": enum_detail, "cross_fire_detail": c8_detail,
            "dispatch_budget_s": spec["budget"]["dispatch_budget_s"],
            "planned_calls": spec["budget"]["planned_calls"],
            "spec_rows": {r["id"]: r["band"] for r in spec["rows"]}}


def stop_offsets(records: list) -> dict:
    """Post-hoc only (not part of the registered gate blob): completion_tokens measured against the
    requested cap, per arm and cap.

    Added after the dispatch because the fired pattern was not one of the three registered shapes.
    It reads only the frozen raw.jsonl; gate.json and the gate blob are untouched by it.
    """
    per_arm: dict = {}
    for r in records:
        tokens, cap = r.get("completion_tokens"), r.get("requested_cap")
        if tokens is None or cap is None:
            continue
        arm = r["arm"]
        per_arm.setdefault(arm, {}).setdefault(cap, []).append({
            "seed": r.get("seed"), "tokens": tokens, "cap": cap, "reserve": cap - tokens,
            "markers": r.get("marker_count"), "finish": r.get("finish_reason"),
        })
    distinct: dict = {}
    for arm, by_cap in per_arm.items():
        for cap, rows in by_cap.items():
            for row in rows:
                key = row["reserve"]
                distinct.setdefault(key, {"reserve": key, "rows": 0, "marker_rows": 0,
                                          "arms": set()})
                distinct[key]["rows"] += 1
                distinct[key]["marker_rows"] += 1 if row["markers"] else 0
                distinct[key]["arms"].add(arm)
    return {"registered": False,
            "note": "post-dispatch observation, added after the tier rule had been frozen; "
                    "no verdict of this round rests on it",
            "by_arm_and_cap": {arm: {str(c): sorted(v, key=lambda x: x["seed"] or 0)
                                     for c, v in sorted(by_cap.items())}
                               for arm, by_cap in sorted(per_arm.items())},
            "reserve_histogram": sorted(({"arms": sorted(d["arms"]), "marker_rows": d["marker_rows"],
                                          "reserve": d["reserve"], "rows": d["rows"]}
                                         for d in distinct.values()),
                                        key=lambda x: x["reserve"])}


def summarize(records: list, gate: dict, model_digest: str, blob: str) -> dict:
    ran = [r for r in records if r.get("kind") != "not_dispatched"]
    missing = [r for r in records if r.get("kind") == "not_dispatched"]
    delivered = [r for r in ran if r["delivered"]]
    correct = [r for r in delivered if r["correct"]]
    out = {
        "gate": blob,
        "schema": GATE_SCHEMA,
        "model_digest": model_digest,
        "dispatch": {"calls_used": len(ran), "call_cap": CALL_CAP,
                     "planned_calls": gate["planned_calls"],
                     "not_dispatched": [m.get("label") for m in missing],
                     "prompt_tokens": sum(r["prompt_tokens"] or 0 for r in ran),
                     "completion_tokens": sum(r["completion_tokens"] or 0 for r in ran),
                     "dispatch_wall_s": round(sum(r["wall_s"] or 0 for r in ran), 3)},
        "answers": {"delivered": len(delivered), "records": len(ran),
                    "correct": len(correct),
                    "delivered_wrong": [
                        {"seed": r["seed"], "arm": r["arm"], "cap": r["requested_cap"],
                         "gold": r["gold"], "declared": r["declared"]} for r in delivered
                        if not r["correct"]]},
        "classes": {k: sum(1 for r in ran if r["kind"] == k) for k in
                    sorted({r["kind"] for r in ran})},
        "gate_rows": gate["rows"],
        "tier": gate["tier"],
        "tier_rule": gate["tier_rule"],
        "flags": gate["flags"],
        "health": gate["health"],
        "enumerate_detail": gate["enumerate_detail"],
        "cross_fire_detail": gate["cross_fire_detail"],
        "census": gate["rows"]["N1"]["measured"],
        "anomalies": gate["rows"]["C9"]["measured"],
        "archive_certification": certify_archive(),
        # post-dispatch only, outside the registered gate blob: see stop_offsets()
        "stop_offsets": stop_offsets(records),
    }
    return out


# ---------------------------------------------------------------- dispatch plan

def build_jobs() -> list:
    """The frozen dispatch plan. Each job: (label, arm, seed, listing_extent, cap)."""
    jobs = [("health", "health", None, None, 256)]
    for seed in (116261051, 116261076):
        jobs.append((f"as_is_{seed}_c2048", "as_is", seed, None, 2048))
    jobs.append(("dup_116261051_c2048", "as_is", 116261051, None, 2048))
    jobs.append(("as_is_116261338_c2048", "as_is", 116261338, None, 2048))
    for seed in (116261051, 116261076):
        jobs.append((f"enum_{seed}_c2048", "enumerate", seed, None, 2048))
    jobs.append(("listing_4000_c2048", "listing", None, LISTING_MAX, 2048))
    for seed in (116261051, 116261076):
        jobs.append((f"as_is_{seed}_c1536", "as_is", seed, None, 1536))
    jobs.append(("listing_4000_c1024", "listing", None, LISTING_MAX, 1024))
    for seed in (116261051, 116261076):
        jobs.append((f"as_is_{seed}_c1024", "as_is", seed, None, 1024))
    for seed in (116261051, 116261076):
        jobs.append((f"as_is_{seed}_c512", "as_is", seed, None, 512))
    return jobs


def job_prompt(job) -> str:
    _label, arm, seed, extent, _cap = job
    if arm == "as_is":
        return render_prompt(item_by_seed(seed))
    if arm == "enumerate":
        return render_enumerate(item_by_seed(seed))
    if arm == "listing":
        return render_listing(extent)
    return CENSUS_PROMPT


def score_record(job, resp, err, blob: str) -> dict:
    label, arm, seed, extent, cap = job
    rec = {"arm": arm, "requested_cap": cap, "label": label, "gate": blob, "seed": seed,
           "listing_extent": extent, "level": None, "gold": None, "n_facts": None}
    if arm in ("as_is", "enumerate"):
        item = item_by_seed(seed)
        rec["seed"] = item["seed"]
        rec["seed_hash"] = hashlib.sha256(str(item["seed"]).encode()).hexdigest()[:16]
        rec["level"] = item["level"]
        rec["gold"] = item["answer"]
        rec["n_facts"] = len(item["facts"])
        rec["n_chains"] = len(weak_components(item["facts"]))
    if resp is None:
        rec.update({"kind": "transport_error", "error": err, "completion_tokens": None,
                    "prompt_tokens": None, "finish_reason": None, "delivered": False,
                    "declared": None, "declared_source": "none", "correct": None,
                    "marker_count": 0, "wall_s": None, "prompt_sha256": None,
                    "prompt_tokens_chars": None, "census": None, "trace": "", "content": "",
                    "trace_chars": 0, "coverage_measures": None, "enumeration_measures": None,
                    "listing_measures": None, "marker_tails": []})
        return rec
    payload = resp["payload"]
    content, trace, finish, usage = channels_of(payload)
    both = trace + "\n" + content
    positions = marker_positions(both)
    declared, source = answer_channel_readout(content)
    prompt_text = job_prompt(job)
    rec.update({
        "kind": classify(usage.get("completion_tokens"), cap, finish, len(positions)),
        "prompt_sha256": hashlib.sha256(prompt_text.encode()).hexdigest(),
        "prompt_chars": len(prompt_text),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "finish_reason": finish,
        "wall_s": resp["wall_s"],
        "census": census_of(payload),
        "trace_chars": len(trace),
        "content_chars": len(content),
        "marker_count": len(positions),
        "marker_tails": [sanitize(marker_tail(both, p)) for p in positions],
        "declared": declared,
        "declared_source": source,
        "delivered": declared is not None and source == "content",
    })
    rec["correct"] = None if declared is None else (declared == rec["gold"])
    if rec["gold"] is None:
        rec["correct"] = None
    if arm in ("as_is", "enumerate"):
        item = item_by_seed(seed)
        rec["coverage_measures"] = coverage_measures(item, both)
        vocab = entity_vocabulary(item)
        listed = parse_listed_entities(both, vocab)
        dist = bfs_reachable(item["facts"], item["query"][0])
        reachable = set(dist) | {item["query"][0]}
        extra = [e for e in listed if e not in reachable]
        missing = sorted(reachable - set(listed))
        rec["enumeration_measures"] = {
            "listed_count": len(listed), "bfs_reachable_count": len(reachable),
            "extra_count": len(extra), "missing_count": len(missing),
            "list_equals_bfs_reachable_set": (arm == "enumerate" and not extra
                                              and not missing and len(listed) > 0),
            "query_target_listed": item["query"][2] in listed,
            "gold_says_target_reachable": rec["gold"] == "yes",
        }
    else:
        rec["coverage_measures"] = None
        rec["enumeration_measures"] = None
    rec["listing_measures"] = measure_listing(both) if arm == "listing" else None
    rec["trace"] = sanitize(trace)
    rec["content"] = sanitize(content)
    return rec


def read_raw(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def model_digest_of(model: str) -> str:
    return hashlib.sha256(model.encode()).hexdigest()[:16]


def main(argv: list) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--gate", action="store_true", help="write gate.json and print the blob")
    p.add_argument("--dry-run", action="store_true", help="print the frozen dispatch plan")
    p.add_argument("--archive", action="store_true",
                   help="re-derive the quoted archived aggregates and print them")
    p.add_argument("--run", action="store_true")
    p.add_argument("--rescore", action="store_true",
                   help="rebuild gate.json and summary.json from raw.jsonl, no endpoint call")
    p.add_argument("--raw", default="raw.jsonl")
    p.add_argument("--summary", default="summary.json")
    p.add_argument("--health", default="health.json")
    a = p.parse_args(argv)

    if a.selftest:
        checks = selftest()
        print(f"selftest checks passed: {checks}")
        print(f"gate blob: {gate_blob_sha256()}")
        return 0

    cert_items = certify_items()
    if not cert_items["ok"]:
        print(f"REFUSED: item certification failed: {cert_items['refused']}", file=sys.stderr)
        return 2
    cert_archive = certify_archive()
    if not cert_archive["ok"]:
        print(f"REFUSED: archive quote does not reproduce: {cert_archive['problems']}",
              file=sys.stderr)
        return 2
    blob = gate_blob_sha256()
    if blob != ROUND53_GATE_BLOB_SHA256:
        print(f"REFUSED: gate blob {blob} does not match the pin {ROUND53_GATE_BLOB_SHA256}",
              file=sys.stderr)
        return 2

    here = Path(__file__).resolve().parent
    raw_path, summary_path, health_path = here / a.raw, here / a.summary, here / a.health

    if a.archive:
        print(json.dumps(cert_archive["measured"], indent=2, sort_keys=True))
        return 0

    if a.gate:
        (here / "gate.json").write_text(json.dumps(gate_spec(), indent=2, sort_keys=True) + "\n",
                                        encoding="utf-8")
        print(f"gate.json written, blob {blob}")
        return 0

    if a.dry_run:
        jobs = build_jobs()
        for label, arm, seed, extent, cap in jobs:
            prompt = job_prompt((label, arm, seed, extent, cap))
            print(f"  {label:26s} cap={cap:4d} predicted_hook={predicted_hook(cap):4d} "
                  f"prompt_chars={len(prompt):5d} digest={prompt_digest(prompt)}")
        print(f"planned calls {len(jobs)} of {CALL_CAP}; caps used "
              f"{sorted({c for *_ , c in jobs})}")
        return 0

    if a.rescore:
        records = read_raw(raw_path)
        if not records:
            print("REFUSED: raw.jsonl is empty", file=sys.stderr)
            return 2
        stray = [r for r in records if r.get("gate") != blob]
        if stray:
            print(f"REFUSED: {len(stray)} records carry a different gate hash", file=sys.stderr)
            return 2
        health = json.loads(health_path.read_text(encoding="utf-8")) if health_path.exists() else {}
        gate = evaluate_gate(records, health)
        digest = next((r.get("model_digest") for r in records if r.get("model_digest")), "")
        summary = summarize(records, gate, digest, blob)
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                                encoding="utf-8")
        (here / "gate.json").write_text(json.dumps(gate_spec(), indent=2, sort_keys=True) + "\n",
                                        encoding="utf-8")
        print(f"rescored {len(records)} records, tier {gate['tier']}, flags {gate['flags']}")
        return 0

    if a.run:
        return run_dispatch(a, blob, raw_path, summary_path, health_path)
    p.print_help()
    return 2


def run_dispatch(a, blob: str, raw_path: Path, summary_path: Path, health_path: Path) -> int:
    base = os.environ.get("NIGHTLY_BASE_URL")
    model = os.environ.get("NIGHTLY_MODEL_ID")
    key = os.environ.get("NIGHTLY_API_KEY") or ""
    if not (base and model):
        print("REFUSED: NIGHTLY_BASE_URL and NIGHTLY_MODEL_ID are required", file=sys.stderr)
        return 2
    secrets = (base, model, key, base.split("//")[-1] if "//" in base else "")
    digest = model_digest_of(model)
    records = []
    t0 = time.time()

    def flush():
        raw_path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records),
                            encoding="utf-8")

    jobs = build_jobs()
    health: dict = {}
    for job in jobs:
        label, arm, seed, extent, cap = job
        if arm == "health":
            try:
                res = call_endpoint(CENSUS_PROMPT, base, model, key, 256)
                content, trace, finish, usage = channels_of(res["payload"])
                health = {"probe": "health", "ok": True, "wall_s": res["wall_s"],
                          "census": sanitize(json.dumps(census_of(res["payload"]),
                                                        sort_keys=True), secrets),
                          "completion_tokens": usage.get("completion_tokens"),
                          "finish_reason": finish,
                          "census_fields": census_of(res["payload"])["fields"],
                          "reasoning_source": census_of(res["payload"])["reasoning_source"],
                          "marker_in_health": len(marker_positions((trace or "") + content))}
            except RuntimeError as exc:
                health = {"probe": "health", "ok": False, "error": sanitize(str(exc), secrets)}
            health_path.write_text(json.dumps(health, sort_keys=True) + "\n", encoding="utf-8")
            print(f"[1/{len(jobs)}] health ok={health.get('ok')} tokens="
                  f"{health.get('completion_tokens')}", flush=True)
            continue
        elapsed = time.time() - t0
        if elapsed > DISPATCH_BUDGET_S:
            for rest in jobs[jobs.index(job):]:
                records.append({"label": rest[0], "arm": rest[1], "seed": rest[2],
                                "listing_extent": rest[3], "requested_cap": rest[4],
                                "kind": "not_dispatched", "gate": blob,
                                "reason": f"wall-clock guard tripped at {round(elapsed, 1)} s of "
                                          f"{DISPATCH_BUDGET_S} s"})
            flush()
            print(f"GUARD: {len(jobs) - jobs.index(job)} dispatches dropped after "
                  f"{round(elapsed, 1)} s", flush=True)
            break
        prompt = job_prompt(job)
        try:
            if any(secret and secret in prompt for secret in secrets):
                raise RuntimeError("sanitizer: an endpoint value reached a prompt")
            resp = call_endpoint(prompt, base, model, key, cap)
            rec = score_record(job, resp, None, blob)
        except RuntimeError as exc:
            rec = score_record(job, None, sanitize(str(exc), secrets), blob)
        rec["model_digest"] = digest
        records.append(rec)
        flush()
        print(f"[{len(records)}/{len(jobs)}] {label} kind={rec['kind']} "
              f"tokens={rec.get('completion_tokens')} finish={rec.get('finish_reason')} "
              f"markers={rec.get('marker_count')} answer={rec.get('declared')}", flush=True)
    if not health.get("ok"):
        print(f"health probe failed: {health.get('error')}", flush=True)
    gate = evaluate_gate(records, health)
    summary = summarize(records, gate, digest, blob)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (here_gate := Path(__file__).resolve().parent / "gate.json").write_text(
        json.dumps(gate_spec(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"tier {gate['tier']}; flags {gate['flags']}; calls used {summary['dispatch']['calls_used']}")
    return 0


# ---------------------------------------------------------------- selftest

def selftest() -> int:  # noqa: C901  (the certified control list)
    n = 0

    def check(label: str, cond: bool) -> None:
        nonlocal n
        n += 1
        if not cond:
            raise AssertionError(f"selftest failed: {label}")

    # 1. hook arithmetic, with planted negatives
    check("predicted hook at the archived cap is the archived pin", predicted_hook(2048) == 1556)
    check("predicted hook at 1024", predicted_hook(1024) == 778)
    check("predicted hook at 512", predicted_hook(512) == 389)
    check("predicted hook at 1536", predicted_hook(1536) == 1167)
    check("predicted hook is monotone in the cap",
          all(predicted_hook(c) < predicted_hook(c + 128) for c in range(128, 2048 - 128, 128)))
    check("predicted hook never exceeds the cap", all(predicted_hook(c) < c for c in (512, 1024,
          1536, 2048)))
    bad = PIN_TOKENS + 1
    check("a planted off-by-one in the archived pin moves the cap-level prediction",
          (bad * 1024 // PIN_CAP == predicted_hook(1024)
           and bad * PIN_CAP // PIN_CAP != predicted_hook(PIN_CAP)))
    check("a planted six-point ratio slip moves the 1024 prediction",
          1024 * 70 // 100 != predicted_hook(1024) and 1024 * 76 // 100 == predicted_hook(1024))
    check("the pin ratio recomputes the archived utilisation", round(PIN_TOKENS / PIN_CAP, 4) == 0.7598)

    # 2. marker detection, cut signature and its planted negatives
    text = ("drind -> clixsh\n157 sch\n\n" + MARKER + "\n")
    pos = marker_positions(text)
    check("marker detected once", len(pos) == 1)
    check("no marker in an unrelated text", marker_positions("nothing to see") == [])
    check("marker counted twice", len(marker_positions(MARKER + " x " + MARKER)) == 2)
    check("the marker tail records the mid-line cut", "clixsh" in marker_tail(text, pos[0]))
    check("a marker at index zero has an empty tail", marker_tail(MARKER, 0) == "")

    # 3. classification: mutually exclusive, and the alternative row comes from the same function
    check("proportional record classifies as a hook hit", classify(778, 1024, "stop", 1)
          == "hook_hit_predicted")
    check("absolute record classifies as the alternative", classify(1024, 1024, "length", 0)
          == "alt_absolute_cap_no_marker")
    check("at the protocol cap without a marker it is censoring, not the alternative",
          classify(2048, 2048, "length", 0) == "censored_at_protocol_cap")
    check("a natural stop classifies as natural", classify(1310, 2048, "stop", 0)
          == "natural_stop_no_marker")
    check("a marker below the hook is an anomaly, not a hit", classify(532, 1024, "stop", 1)
          == "marker_below_predicted_hook")
    check("a marker above the hook is an anomaly, not a hit", classify(1700, 2048, "stop", 1)
          == "marker_above_predicted_hook")
    check("a second marker is an anomaly row", classify(1556, 2048, "stop", 2)
          == "marker_anomaly_count_gt1")
    check("a transport failure is its own class", classify(None, 2048, None, 0) == "transport_error")
    check("band edge inside", classify(1556 - HOOK_BAND, 2048, "stop", 1) == "hook_hit_predicted")
    check("band edge outside", classify(1556 - HOOK_BAND - 1, 2048, "stop", 1)
          == "marker_below_predicted_hook")

    # 4. independent solver and the load-floor geometry of the dispatched items
    facts = [("a", "precedes", "b"), ("b", "precedes", "c"), ("x", "precedes", "y"),
             ("y", "precedes", "z")]
    dist = bfs_reachable(facts, "a")
    check("BFS reaches the tail of its own path", dist.get("c") == 2)
    check("BFS does not cross into the other component", "z" not in dist)
    bridge_facts = [("a", "precedes", "b"), ("b", "precedes", "c"), ("c", "precedes", "z"),
                    ("x", "precedes", "y")]
    check("a planted bridge is detected by the solver", bfs_reachable(bridge_facts, "a").get("z") == 3)
    check("weak components separate the two paths", len(weak_components(facts)) == 2)
    check("a planted bridge still leaves two components", len(weak_components(bridge_facts)) == 2)
    merge_facts = [("a", "precedes", "b"), ("b", "precedes", "c"), ("y", "precedes", "c"),
                   ("x", "precedes", "y")]
    check("a planted cross-link collapses the components", len(weak_components(merge_facts)) == 1)
    check("the collapsed graph breaks the load-floor guard", not all(
        len(c) == 2 + 1 for c in weak_components(merge_facts)))

    for seed, gold, facts_n, sha16, tokens, cap, finish, marker, answer, correct in ROUND51_GRID:
        if seed not in PINNED_SEEDS:
            continue
        item = item_by_seed(seed)
        check(f"item {seed} is load floor", len(item["facts"]) == 2 * LEVEL == facts_n)
        check(f"item {seed} gold label reproduces", item["answer"] == gold)
        check(f"item {seed} prompt digest reproduces the archived digest",
              prompt_digest(render_prompt(item)) == sha16)
        check(f"item {seed} has two components of size k+1",
              all(len(c) == LEVEL + 1 for c in weak_components(item["facts"])))
        dist = bfs_reachable(item["facts"], item["query"][0])
        check(f"item {seed} solver agrees with the generator",
              (item["query"][2] in dist) == (gold == "yes"))
        if gold == "yes":
            check(f"item {seed} shortest path is exactly k", dist[item["query"][2]] == LEVEL)
    check("certify_items certifies the three dispatched items",
          certify_items() == {"ok": True, "certified": 3, "refused": []})
    # the certifier must refuse a planted digest slip
    saved = list(ROUND51_GRID)
    mutated = [row for row in saved]
    mutated[12] = mutated[12][:3] + ("0" * 16,) + mutated[12][4:]
    globals()["ROUND51_GRID"] = tuple(mutated)
    check("a planted prompt digest slip is refused by the certifier", not certify_items()["ok"])
    mutated2 = list(saved)
    mutated2[12] = mutated2[12][:1] + ("yes",) + mutated2[12][2:]
    globals()["ROUND51_GRID"] = tuple(mutated2)
    check("a planted gold flip is refused by the certifier", not certify_items()["ok"])
    mutated3 = list(saved)
    mutated3[12] = mutated3[12][:2] + (95,) + mutated3[12][3:]
    globals()["ROUND51_GRID"] = tuple(mutated3)
    check("a planted fact-count slip is refused by the certifier", not certify_items()["ok"])
    globals()["ROUND51_GRID"] = tuple(saved)
    check("certification is restored after the planted slips", certify_items()["ok"])

    # 5. the archive quotes reproduce their own aggregates, and a planted count fails
    cert = certify_archive()
    check("archive quotes reproduce", cert["ok"], )
    check("the recomputed pin ratio is 0.7598", cert["pin_ratio_recomputed"] == 0.7598)
    check("round 49 pin count", cert["measured"]["round 49"]["at_pin"] == 33)
    check("round 49 marker count equals the pin count",
          cert["measured"]["round 49"]["marker"] == cert["measured"]["round 49"]["at_pin"])
    check("round 49 reached the protocol cap nowhere", cert["measured"]["round 49"]["at_cap"] == 0)
    check("round 51 pin count", cert["measured"]["round 51"]["at_pin"] == 8)
    check("round 51 marker count is the grid pins plus the one rung anomaly",
          cert["measured"]["round 51"]["marker"] == 9)
    check("round 51 carries the same 0.7598 ratio at the pin",
          cert["measured"]["round 51"]["utilisations_at_pin"] == [0.7598])
    check("round 51 records cover both stages", cert["measured"]["round 51"]["records"] == 20)
    check("the archived rung record is an off-hook marker",
          [r for r in ROUND51_LADDER if r[4] == 1 and abs(r[2] - predicted_hook(r[1])) > HOOK_BAND]
          == [(116261338, 1024, 532, 'stop', 1, 'yes')])
    check("two archived rung records reached the rung with no marker",
          sum(1 for r in ROUND51_LADDER if r[2] == r[1] and r[3] == 'length' and r[4] == 0) == 2)
    check("round 50 shows no pin and five cap records",
          cert["measured"]["round 50"]["at_pin"] == 0 and cert["measured"]["round 50"]["at_cap"] == 5)
    check("round 50 shows no marker", cert["measured"]["round 50"]["marker"] == 0)
    check("round 48 shows no pin and five cap records",
          cert["measured"]["round 48"]["at_pin"] == 0 and cert["measured"]["round 48"]["at_cap"] == 5)
    check("round 49's non-pinned records are the only unpinned ones",
          sum(1 for r in ROUND49_RECORDS if r[6] != PIN_TOKENS) == 3)
    saved49 = list(ROUND49_RECORDS)
    mutated49 = list(saved49)
    mutated49[4] = mutated49[4][:6] + (1555,) + mutated49[4][7:]
    globals()["ROUND49_RECORDS"] = tuple(mutated49)
    check("a planted pin count slip is refused by the archive certifier",
          not certify_archive()["ok"])
    globals()["ROUND49_RECORDS"] = tuple(saved49)
    check("the archive certifier is restored", certify_archive()["ok"])
    stated = gate_spec()["archived_reference"]["pin_signature"]
    check("the stated round 49 utilisation set is the recomputed one",
          stated["round 49"]["utilisations_at_pin"] == [0.7598])
    check("round 48's marker column is declared not evaluable",
          TRACE_EXPOSURE["round 48"]["text_stored"] is False
          and stated["round 48"]["marker"] is None)
    check("the three trace-bearing archives declare a quotable marker count",
          all(TRACE_EXPOSURE[r]["text_stored"] and stated[r]["marker"] is not None
              for r in ("round 49", "round 51", "round 50")))
    saved_exposure = {k: dict(v) for k, v in TRACE_EXPOSURE.items()}
    TRACE_EXPOSURE["round 48"] = {**TRACE_EXPOSURE["round 48"], "text_stored": True}
    check("a planted zero-trace flip is refused: a marker count cannot be quoted "
          "against an archive that stores no reasoning text", not certify_archive()["ok"])
    TRACE_EXPOSURE["round 48"] = {**TRACE_EXPOSURE["round 48"], "text_stored": False}
    TRACE_EXPOSURE["round 50"] = {**TRACE_EXPOSURE["round 50"], "text_stored": False}
    check("a planted trace-bearing flip the other way is also refused",
          not certify_archive()["ok"])
    for key, value in saved_exposure.items():
        TRACE_EXPOSURE[key] = value
    check("the archive certifier is restored after the planted exposure slips",
          certify_archive()["ok"])

    # 6. answer-field readout with the instruction-echo guard (issue #94)
    check("a one-word answer is read", answer_channel_readout("no") == ("no", "content"))
    check("the last standalone answer wins",
          answer_channel_readout("first yes, in the end no") == ("no", "content"))
    check("an instruction echo is refused as a verdict",
          answer_channel_readout("Answer with exactly one word: yes or no")[1] == "instruction_echo")
    check("no answer field is 'none'", answer_channel_readout("") == (None, "none"))
    check("a list-shaped content is handled by channels_of",
          channels_of({"choices": [{"message": {"content": [{"text": "yes"}], "role": "user"},
                                    "finish_reason": "stop"}], "usage": {}})[0] == "yes")

    # 7. listing and enumeration measures, with planted negatives
    listing_text = "\n".join(str(i) for i in range(1, 11)) + "\nDONE\n"
    m = measure_listing(listing_text)
    check("complete listing measures", m["distinct_numbers"] == 10 and m["max_number"] == 10
          and m["missing_in_range"] == 0 and m["done_present"])
    cut = "\n".join(str(i) for i in range(1, 11) if i != 7)
    m2 = measure_listing(cut)
    check("a planted gap is counted", m2["missing_in_range"] == 1)
    check("a cut listing has no DONE", not m2["done_present"])
    check("no numbers parses cleanly", measure_listing("nothing")["distinct_numbers"] == 0)
    item = item_by_seed(116261051)
    vocab = entity_vocabulary(item)
    reachable = set(bfs_reachable(item["facts"], item["query"][0])) | {item["query"][0]}
    good = "\n".join(sorted(reachable)) + "\nno\n"
    listed = parse_listed_entities(good, vocab)
    check("a complete list parses to the reachable set", set(listed) == reachable)
    bad_list = "\n".join(sorted(reachable - {item["query"][0]})) + "\nno\n"
    check("a planted dropped head is counted as missing",
          len(sorted(reachable - set(parse_listed_entities(bad_list, vocab)))) == 1)
    other = sorted(vocab - reachable)[0]
    extra_list = "\n".join(sorted(reachable | {other})) + "\nyes\n"
    check("a planted foreign entity is counted as extra",
          other in parse_listed_entities(extra_list, vocab))
    check("listing lines outside the vocabulary are not counted as entities",
          parse_listed_entities("yes\nno\nFacts\nrule\n", vocab) == [])
    cov = coverage_measures(item, "\n".join(sorted(list(vocab)[:10])))
    check("coverage ratio is a fraction of the item's entities",
          0 < cov["coverage_ratio"] <= 1 and cov["entities_in_item"] == len(vocab))
    check("the gold-no item's target is unreachable",
          coverage_measures(item, "")["target_is_reachable"] is False)
    yes_item = item_by_seed(116261338)
    check("the gold-yes item's target is reachable",
          coverage_measures(yes_item, "")["target_is_reachable"] is True)

    # 8. sanitizer over the public-only rule: the fixtures carry only RFC 5737 TEST-NET-1
    # documentation addresses, assembled so no complete address or URL literal sits in this file
    doc_net = "192" + "." + "0" + "." + "2"          # RFC 5737 TEST-NET-1 prefix
    doc_ip = doc_net + "." + "7"
    other_net = "100" + "." + "64" + "." + "0" + "." + "13"
    v6 = "fe80" + "::" + "1:2:3"
    url = "http" + "s" + "://" + "example" + "." + "invalid" + "/v1"
    fixture = f"host: {doc_ip} token=abc123 {url} {other_net} {v6} localslot plainword"
    clean = sanitize(fixture, (doc_ip, "abc123", "localslot"))
    check("the endpoint address never survives the sanitizer", doc_net not in clean)
    check("a second documentation address is redacted", "100" + "." + "64" not in clean)
    check("the credential never survives", "abc123" not in clean)
    check("an IPv6-shaped value is redacted", "fe80" not in clean)
    check("a URL is redacted, not dropped silently", "http" not in clean
          and "[redacted-url]" in clean)
    check("a bare word that carries no address stays untouched",
          "plainword" in clean and "documentation" in sanitize("documentation label"))

    # 9. census merge rule (issue #105)
    def census(source: str, rc: str, rf: str) -> str:
        return census_of({"choices": [{"message": {"role": "user", "content": "yes",
                                                   "reasoning_content": rc, "reasoning": rf},
                                       "finish_reason": "stop"}]})["reasoning_source"]
    check("reasoning_content wins when non-empty", census("a", "text", "other") == "reasoning_content")
    check("reasoning is used when reasoning_content is empty", census("a", "", "other") == "reasoning")
    check("an empty deployment censuses as empty", census("a", "", "") == "")

    # 10. gate tiers, driven by planted firings: every tier reachable, and the refusal path real
    def enumerate_text(seed: int) -> str:
        item = item_by_seed(seed)
        ent = set(bfs_reachable(item["facts"], item["query"][0])) | {item["query"][0]}
        return "\n".join(sorted(ent))

    def planted(rows: list) -> dict:
        recs = []
        for arm, seed, cap, tokens, finish, markers, declared, gold in rows:
            label = f"{arm}_{seed}_c{cap}"
            job = (label, arm, seed, LISTING_MAX if arm == "listing" else None, cap)
            trace = MARKER * markers
            if arm == "enumerate":
                # The reachable-set listing is short, so in every tier it is written before
                # whatever stop follows; the marker sentence, when present, comes last and always
                # on its own line, never glued to the final entity of the list.
                trace = enumerate_text(seed) + (("\n" + trace) if trace else "")
            payload = {"choices": [{"message": {"role": "user", "content": declared or "",
                                                "reasoning_content": trace},
                                    "finish_reason": finish}],
                       "usage": {"completion_tokens": tokens, "prompt_tokens": 100}}
            resp = {"payload": payload, "wall_s": 1.0}
            recs.append(score_record(job, resp, None, gate_blob_sha256()))
        return evaluate_gate(recs, {"ok": True})

    proportional = ([("as_is", 116261051, 512, 389, "stop", 1, "yes", "no"),
                     ("as_is", 116261076, 512, 390, "stop", 1, "no", "no"),
                     ("as_is", 116261051, 1024, 778, "stop", 1, "yes", "no"),
                     ("as_is", 116261076, 1024, 777, "stop", 1, "no", "no"),
                     ("as_is", 116261051, 1536, 1167, "stop", 1, "yes", "no"),
                     ("as_is", 116261076, 1536, 1168, "stop", 1, "no", "no"),
                     ("as_is", 116261051, 2048, 1556, "stop", 1, "yes", "no"),
                     ("as_is", 116261076, 2048, 1556, "stop", 1, "yes", "no"),
                     ("as_is", 116261338, 2048, 1310, "stop", 0, "yes", "yes"),
                     ("listing", None, 2048, 1556, "stop", 1, None, None),
                     ("listing", None, 1024, 778, "stop", 1, None, None),
                     ] + [("enumerate", s, 2048, 1556, "stop", 1, "no", "no") for s in
                          (116261051, 116261076)]
                     + [("as_is", 116261051, 2048, 1556, "stop", 1, "yes", "no")])
    gate_prop = planted(proportional)
    check("a proportional firing yields the serving-budget tier", gate_prop["tier"]
          == "serving_budget_hook")
    check("the proportional C1 row runs 6 of 6", gate_prop["rows"]["C1"]["measured"] == "6 of 6")
    check("the proportional C2 row counts zero", gate_prop["rows"]["C2"]["measured"] == "0 of 6")
    check("the proportional C3 row finds no disagreement", gate_prop["rows"]["C3"]["measured"] == 0)
    check("the proportional C4 control passes", gate_prop["rows"]["C4"]["status"] == "pass")
    check("the proportional listing control is cut at both caps",
          gate_prop["rows"]["C5"]["measured"] == "2 of 2")
    check("the duplicate control is recognized", gate_prop["rows"]["C7"]["measured"] == "1 of 1")
    check("the planted enumerate arm recovers the label",
          gate_prop["rows"]["C6"]["measured"] == "2 of 2")
    check("the recovery flag requires the tier",
          "enumerate_arm_recovers_label_and_tier_is_hook" in gate_prop["flags"])

    absolute = [("as_is", 116261051, 512, 512, "length", 0, None, "no"),
                ("as_is", 116261076, 512, 512, "length", 0, None, "no"),
                ("as_is", 116261051, 1024, 1024, "length", 0, None, "no"),
                ("as_is", 116261076, 1024, 1024, "length", 0, None, "no"),
                ("as_is", 116261051, 1536, 1536, "length", 0, None, "no"),
                ("as_is", 116261076, 1536, 1536, "length", 0, None, "no"),
                ("as_is", 116261051, 2048, 1556, "stop", 1, "yes", "no"),
                ("as_is", 116261076, 2048, 1556, "stop", 1, "yes", "no"),
                ("as_is", 116261338, 2048, 1310, "stop", 0, "yes", "yes"),
                ("listing", None, 2048, 1556, "stop", 1, None, None),
                ("listing", None, 1024, 1024, "length", 0, None, None)]
    gate_abs = planted(absolute)
    check("an absolute-budget firing yields the absolute tier", gate_abs["tier"] == "absolute_pin")
    check("the absolute C1 row refuses the proportional reading",
          gate_abs["rows"]["C1"]["status"] == "fail")
    check("the absolute C2 row counts every low-cap rung",
          gate_abs["rows"]["C1"]["measured"] == "0 of 6"
          and gate_abs["rows"]["C2"]["measured"] == "6 of 6")
    check("the flag cannot be raised under the absolute tier",
          "enumerate_arm_recovers_label_and_tier_is_hook" not in gate_abs["flags"])

    none_budget = [("as_is", 116261051, 512, 480, "stop", 0, "no", "no"),
                   ("as_is", 116261076, 512, 460, "stop", 0, "no", "no"),
                   ("as_is", 116261051, 1024, 1024, "length", 0, None, "no"),
                   ("as_is", 116261076, 1024, 1024, "length", 0, None, "no"),
                   ("as_is", 116261051, 1536, 1400, "stop", 1, "no", "no"),
                   ("as_is", 116261076, 1536, 1536, "length", 0, None, "no"),
                   ("as_is", 116261051, 2048, 1500, "stop", 0, "yes", "no"),
                   ("as_is", 116261076, 2048, 1400, "stop", 0, "no", "no"),
                   ("as_is", 116261338, 2048, 1310, "stop", 0, "yes", "yes"),
                   ("listing", None, 2048, 2048, "length", 0, None, None),
                   ("listing", None, 1024, 1024, "length", 0, None, None),
                   ("enumerate", 116261051, 2048, 1500, "stop", 0, "no", "no"),
                   ("enumerate", 116261076, 2048, 1500, "stop", 0, "yes", "no")]
    gate_none = planted(none_budget)
    check("a family-dependent firing yields the no-serving-budget tier",
          gate_none["tier"] == "no_serving_budget")
    check("the anomaly row counts the off-hook markers",
          gate_none["rows"]["C9"]["measured"]["count"] >= 1)
    check("the anomaly flag is raised when a marker sits off the hook",
          "marker_not_locked_to_predicted_hook" in gate_none["flags"])

    partial = proportional[:8] + [("as_is", 116261338, 2048, 1310, "stop", 0, "yes", "yes"),
                                  ("listing", None, 2048, 1556, "stop", 1, None, None),
                                  ("listing", None, 1024, 1300, "length", 1, None, None),
                                  ("enumerate", 116261051, 2048, 1500, "stop", 1, "no", "no"),
                                  ("enumerate", 116261076, 2048, 1500, "stop", 1, "no", "no")]
    check("a firing that misses the listing control at one cap is unresolved",
          planted(partial)["tier"] == "unresolved")

    # 11. refused rows carry no number: a row whose dispatches did not run is not quotable
    gate_norun = planted([row for row in proportional if row[2] == 2048])
    check("the low-cap ladder row did not run when its dispatches did not run",
          gate_norun["rows"]["C1"]["status"] == "did not run")
    check("a did-not-run row carries no measured number",
          gate_norun["rows"]["C1"]["measured"] is None
          and gate_norun["rows"]["C2"]["measured"] is None)
    check("the tier is refused when a decisive row did not run",
          gate_norun["tier"] == "unresolved")
    check("no flag that depends on a ran row is raised for a did-not-run row",
          "enumerate_arm_recovers_label_and_tier_is_hook" not in gate_norun["flags"])
    short = planted([row for row in proportional if row[2] in (512, 1024)])
    check("four of six low-cap dispatches fails rather than passes C1",
          short["rows"]["C1"]["measured"] == "4 of 4" and short["rows"]["C1"]["status"] == "fail")
    nd = [{"label": f"drop{i}", "arm": "as_is", "seed": 116261051, "listing_extent": None,
           "requested_cap": 512, "kind": "not_dispatched", "gate": gate_blob_sha256()}
          for i in range(3)]
    summary_drop = summarize(nd, gate_norun, "d", gate_blob_sha256())
    check("the summary records dropped dispatches by label",
          len(summary_drop["dispatch"]["not_dispatched"]) == 3)
    check("the summary keeps the refused tier", summary_drop["tier"] == "unresolved")
    check("a summary over only dropped dispatches counts no calls",
          summary_drop["dispatch"]["calls_used"] == 0)

    # 12. join key pairs the request, not the dispatch label
    a_rec = {"arm": "as_is", "seed": 116261051, "requested_cap": 2048,
             "prompt_sha256": "a" * 64}
    b_rec = dict(a_rec, prompt_sha256="a" * 64)
    c_rec = dict(a_rec, prompt_sha256="b" * 64)
    check("identical requests share a join key", join_key(a_rec) == join_key(b_rec))
    check("a different prompt bytes breaks the pair", join_key(a_rec) != join_key(c_rec))
    check("a different cap breaks the pair", join_key(dict(a_rec, requested_cap=1024))
          != join_key(a_rec))

    # 13. transport-failure and malformed-response record paths
    err_rec = score_record(("as_is_116261051_c2048", "as_is", 116261051, None, 2048), None,
                           "transport:URLError", gate_blob_sha256())
    check("a transport failure is recorded as such", err_rec["kind"] == "transport_error")
    check("a transport failure is never counted as delivered", err_rec["delivered"] is False)
    malformed = score_record(("as_is_116261051_c2048", "as_is", 116261051, None, 2048),
                             {"payload": {"choices": []}, "wall_s": 0.1}, None, gate_blob_sha256())
    check("an empty choices list is recorded, not invented",
          malformed["completion_tokens"] is None and malformed["kind"] == "transport_error")
    check("the malformed record still censuses", malformed["census"] == {"fields": [],
          "reasoning_content_chars": 0, "reasoning_field_chars": 0, "reasoning_source": ""})

    # 14. cap contract: nothing in the plan may exceed the protocol cap
    caps = {c for *_, c in build_jobs()}
    check("every requested cap is at or below the protocol cap", max(caps) <= MAX_TOKENS)
    check("the plan stays inside the call cap", len(build_jobs()) <= CALL_CAP)
    check("the plan requests the four registered caps", caps <= set(CAPS) | {256})
    check("the plan carries two listing controls",
          sum(1 for j in build_jobs() if j[1] == "listing") == 2)
    check("the plan carries the duplicate control",
          sum(1 for j in build_jobs() if j[1] == "as_is" and j[4] == 2048) == 4)
    check("the health probe is a small call, not the cap",
          next(j[4] for j in build_jobs() if j[1] == "health") == 256)
    prompts = {j[0]: job_prompt(j) for j in build_jobs()}
    check("the as-is prompt is byte-identical to the certified template",
          prompts["as_is_116261051_c2048"] == render_prompt(item_by_seed(116261051)))
    check("the enumerate arm keeps the same question line",
          f"Question: does {item_by_seed(116261051)['query'][0]} precedes "
          f"{item_by_seed(116261051)['query'][2]}?" in prompts["enum_116261051_c2048"])
    check("no prompt carries an endpoint value", all(
        "://" not in p and not IPV4.search(p) for p in prompts.values()))

    # 15. gate integrity
    check("the gate blob is stable across calls", gate_blob_sha256() == gate_blob_sha256())
    check("the pinned gate blob matches the spec", gate_blob_sha256() == ROUND53_GATE_BLOB_SHA256)
    spec = gate_spec()
    check("every row has a band", all(r["band"] for r in spec["rows"]))
    check("every row has text", all(len(r["text"]) > 20 for r in spec["rows"]))
    check("the gate names all three hypotheses", len(spec["hypotheses"]) == 3)
    ids = [r["id"] for r in spec["rows"]]
    check("row ids are unique", len(ids) == len(set(ids)))
    summary = summarize([score_record(("as_is_116261051_c2048", "as_is", 116261051, None, 2048),
                                      {"payload": {"choices": [{"message": {"role": "user",
                                                                           "content": "yes",
                                                                           "reasoning_content": MARKER},
                                                               "finish_reason": "stop"}],
                                                  "usage": {"completion_tokens": 1556,
                                                            "prompt_tokens": 700}},
                                          "wall_s": 1.0}, None, gate_blob_sha256())],
                        evaluate_gate([], {"ok": True}), "d", gate_blob_sha256())
    check("the summary carries the tier and the flags", {"tier", "flags"} <= set(summary))
    check("the summary re-derives the archive certification",
          summary["archive_certification"]["ok"] is True)

    # 16. the post-dispatch reserve column: outside the gate blob, and a planted slip moves it
    fixture = [
        score_record(("as_is_116261051_c2048", "as_is", 116261051, None, 2048),
                     {"payload": {"choices": [{"message": {"role": "user", "content": "yes",
                                                           "reasoning_content": MARKER},
                                               "finish_reason": "stop"}],
                                  "usage": {"completion_tokens": 1556, "prompt_tokens": 700}},
                                "wall_s": 1.0}, None, gate_blob_sha256()),
        score_record(("as_is_116261051_c512", "as_is", 116261051, None, 512),
                     {"payload": {"choices": [{"message": {"role": "user", "content": "yes"},
                                               "finish_reason": "length"}],
                                  "usage": {"completion_tokens": 512, "prompt_tokens": 700}},
                                "wall_s": 1.0}, None, gate_blob_sha256()),
    ]
    offsets = stop_offsets(fixture)
    check("the reserve column is marked outside the registered gate",
          offsets["registered"] is False)
    check("the reserve column states that no verdict rests on it",
          "no verdict" in offsets["note"])
    check("the reserve is the requested cap minus the completion tokens",
          offsets["by_arm_and_cap"]["as_is"]["2048"][0]["reserve"] == 2048 - PIN_TOKENS
          and offsets["by_arm_and_cap"]["as_is"]["512"][0]["reserve"] == 0)
    hist = {row["reserve"]: row for row in offsets["reserve_histogram"]}
    check("the reserve histogram separates the archived offset from a truncation",
          hist[2048 - PIN_TOKENS]["rows"] == 1 and hist[0]["rows"] == 1)
    check("only the marker row counts as marker-bearing",
          hist[2048 - PIN_TOKENS]["marker_rows"] == 1 and hist[0]["marker_rows"] == 0)
    planted = [{**fixture[0], "completion_tokens": PIN_TOKENS + 1}]
    planted_reserve = stop_offsets(planted)["reserve_histogram"][0]["reserve"]
    check("a planted one-token slip moves the recorded reserve",
          planted_reserve == 2048 - (PIN_TOKENS + 1) and planted_reserve != 2048 - PIN_TOKENS)
    check("the summary carries the reserve column and the gate blob is unchanged by it",
          summarize(fixture, evaluate_gate([], {"ok": True}), "d",
                    gate_blob_sha256())["stop_offsets"]["registered"] is False
          and gate_blob_sha256() == ROUND53_GATE_BLOB_SHA256)
    return n


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

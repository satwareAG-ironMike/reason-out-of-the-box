#!/usr/bin/env python3
"""Round 59 probe: does the 27B-class step-40 wall travel to a flash-next-class build?

Question (issue #71, #94, #100, #105, #126, #129). Round 58 (`research/nightly-2026-11-10-0401/`, a
killed firing that left an untracked archive and no PR) fired the matched load-times-depth name grid
on a re-fired 27B build and landed on the law `step40_wall`: delivery stopped at step 40, the
96-fact input-load law was refuted on that build, and the 3,072 product law was not separable from
the step count. Round 57 (`research/nightly-2026-11-10-0223/`, killed before it fired any gate) had
registered the same wall-shape question on the flash class and never answered it. This firing
answers it: the identical 17-coordinate name grid, the identical four registered laws, on a
flash-next-class build whose model digest differs from every archived build in this repository, so
the tier reading is a class-level comparison at matched coordinates rather than a re-fire.

  grid   four load-floor items (exactly two disjoint k-edge paths, facts = 2k, issue #129):
         k = 16 (32 facts, j = 8, 16), k = 32 (64 facts, j = 8, 16, 24, 32),
         k = 48 (96 facts, j = 8, 16, 24, 32, 40), k = 64 (128 facts, j = 8, 16, 24, 32, 40, 48).
         Inside one item only the integer j moves: the rule sentence and the shuffled fact block are
         byte-identical between two cells of one item, so depth is isolated from input load by
         construction.
  gold   the entity reached from the query source by following direct links for exactly j steps,
         computed by an independent walker in this file, never read from the generator's label.
  NONE   the two negative classes: j = k + 1 (the links run out one step past the path end) and a
         path tail asked for one step (out-degree zero).
  laws   four candidates, thresholds declared in gate.json before the first prompt and scored over
         the 17 name cells as predictions of "censored" (no terminal produced):
           input_load_wall    censored iff n_facts >= 96
           step_count_wall    censored iff j >= 32
           load_depth_product censored iff n_facts * j >= 3072
           step40_wall        censored iff j >= 40
         The first three carry the flash class's own archived thresholds (round 55's largest
         delivered product 64 * 32 = 2,048 against its smallest censored product 96 * 32 = 3,072, and
         its censored step-32 cell at 96 facts); the fourth carries the 27B build's archived tier.
         No threshold moves between the gate and the dispatch.

Gate rows are C1-C9, H1 and X1; the tier rule and every threshold are frozen in gate.json before the
first prompt. Row ids quoted in README.md are checked against the frozen gate by `--check-readme`
(the issue #137 guard, implemented round-side here: undefined row ids, a stale blob pin, and a raw
record carrying a stale blob all fail it).

Caps are contractual: 40 prompts for the round, max_tokens at most 2,048, temperature 0.0, no metered
or hosted provider. No endpoint value (base URL, model id, key) is ever written: artifacts carry a
one-way digest of the serving id and every string passes the sanitizer first.

Usage:
  wall_transfer_probe_r59.py --selftest
  wall_transfer_probe_r59.py --gate        (freeze gate.json, no endpoint call)
  wall_transfer_probe_r59.py --dry-run     (the dispatch plan and prompt digests, no endpoint call)
  NIGHTLY_BASE_URL=... NIGHTLY_MODEL_ID=... NIGHTLY_API_KEY=... wall_transfer_probe_r59.py --run
  wall_transfer_probe_r59.py --calibrate   (one format call, written to calibration.json, not data)
  wall_transfer_probe_r59.py --rescore     (rebuild summary.json from raw.jsonl + gate.json)
  wall_transfer_probe_r59.py --check-readme (issue #137 guard over README.md, gate.json, raw.jsonl)
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
SEED_BASE = 20261005          # the round 51 seed base: the same items, the same seeds
SCAN = 400
MAX_TOKENS = 2048             # protocol cap: no requested cap may exceed it
CALL_CAP = 40
TIMEOUT_S = 600
DISPATCH_BUDGET_S = 1800      # wall-clock guard on the dispatch phase
MAX_RETRIES_TOTAL = 4
NONE_GOLD = "NONE"
GATE_SCHEMA = "round59-gate-v1"
TIER_LINE = 14                # a law must agree on at least 14 of the 17 name cells, uniquely

# ---------------------------------------------------------------- archived anchors (public record)

# Round 51's certified load-floor k = 48 item, dispatched byte-identically by rounds 51, 53, 54 and
# 55. Its archived yes/no prompt digest is re-derived before any dispatch from the same rule and
# fact block, so the name-form prompts used here provably carry the same fact bytes.
ARCHIVED_K48 = {"seed": 116261051, "yesno_digest16": "068bc6a1fb0620fb"}

# The level-64 load-floor item, pinned by the deterministic per-item scan (issue #129 option (a)):
# scanning 400 candidate seeds of the level-64 series with the entity-pool raise caught per item
# yields 235 items, 165 raises, the first raise at index 4, and exactly one load-floor item, at
# scan index 115. Re-derived in --selftest and asserted before the first prompt, so a generator
# revision that moves the scan breaks the round before any prompt is spent.
L64_PIN = {"level": 64, "scan_index": 115, "seed": 148261120, "scan_generated": 235,
           "scan_raised": 165, "scan_first_raise_index": 4, "n_facts": 128,
           "query": ["smixg", "precedes", "brelt"]}

# Round 55 (`research/nightly-2026-11-09-0301/`, head 806f5d37, open PR #136 at this firing): the
# flash class's own name grid. The prompt bytes are certified here by re-rendering each shared cell
# and asserting the archived sha256, so the response format is pinned byte-identically, and the
# archived delivery states are carried for the same-class reproduction column (row C5).
R55_MODEL_DIGEST = "4075b5949b2b0487"
R55_BLOB = "eadf84d55d10b649c952a29a350437a8658c837fb62c6f39356c508378a151a4"
R55_CELLS = {
    # label: (kind, j, gold, prompt_sha256, archived_state, archived_completion_tokens)
    "L16_j8": ("name", 8, "stacklt",
               "87169f9ec6f776c3933f511b0e6b4c52c73627f9fe28c5e6b67aa7a3f796636c", "D", 441),
    "L16_j16": ("name", 16, "brond",
                "a22f1d12cc743d194ee386939eeb8d4998a8e2fc28c59b70b16ee2e9a5db1f30", "D", 529),
    "L16_offend": ("off_end", 17, "NONE",
                   "515a50f2c6478f796b0b46744566c670eb696da3581350968480ee363461dcd3", "D", 974),
    "L32A_deadend": ("dead_end", 1, "NONE",
                     "1f56a9a6f5969364284e1af8ce1a5dcdf8ee22b90bc5c5ce99aecba5079fce86", "D", 204),
    "L32A_j8": ("name", 8, "thrend",
                "70ed757a4d369ae5ff57164bb1937f1d8b24b0ddf63925ad35d8b28936a48366", "D", 528),
    "L32A_j16": ("name", 16, "crux",
                 "40909990f780674a7d93d9df15d819e43fedb57c4e0df326c56290084242d4c7", "D", 437),
    "L32A_j24": ("name", 24, "vixx",
                 "def7b75e37c9eaa4e7b72ebdba8435a4fdcbb440a264522cc2dc72fbe427380e", "D", 1285),
    "L32A_j32": ("name", 32, "sterk",
                 "a8697dfb826079fc9be40fae6e6a8a78c915e1b16d5c066311eb438c9f694c53", "D", 951),
    "L32A_offend": ("off_end", 33, "NONE",
                    "cbd27af78988945009fce3608b9b7ebe9cc4e3bac6a4a2ed01c8192843c095b9", "C", 2048),
    "L48_j8": ("name", 8, "trackst",
               "cec71db935bf42f9b0707da23f6973c622dd8b780fc9abc68f1f33edd5716260", "D", 1096),
    "L48_j16": ("name", 16, "flixm",
                "7f6bbe18f35294e11fdfba70a4fbd2f0243f00ebf123b75348ff9074161340b1", "D", 883),
    "L48_j32": ("name", 32, "whesh",
                "6f19b9f8c406d70313e6f598c99a982855aa4f51e43af4ff9b60d3819f82e054", "C", 2048),
    "L48_offend": ("off_end", 49, "NONE",
                   "e07afb24060fd6523c44f8c7147ae5e08e2b55a0131dcc2e14742f7452c45747", "C", 2048),
}

# Round 58 (`research/nightly-2026-11-10-0401/`): a killed firing on a re-fired 27B build. Its
# directory carries no commit, no branch and no PR, so these constants are the only surviving copy
# of its reading of the same grid; they are used in the post-hoc cross-class column (row X1),
# `registered: false`, and no tier input reads them. States and completion tokens only.
R58_MODEL_DIGEST = "26df9af5972ff312"
R58_STATES = {
    "L16_j8": ("D", 438), "L16_j16": ("D", 526),
    "L32A_j8": ("D", 793), "L32A_j16": ("D", 1024), "L32A_j24": ("C", 2048), "L32A_j32": ("D", 1121),
    "L48_j8": ("D", 365), "L48_j16": ("D", 1003), "L48_j24": ("D", 1816), "L48_j32": ("C", 2048),
    "L48_j40": ("C", 2048),
    "L64_j8": ("D", 1423), "L64_j16": ("D", 1156), "L64_j24": ("D", 895), "L64_j32": ("D", 1767),
    "L64_j40": ("C", 2048),
}

# The load-floor items themselves, certified by seed against the archived record.
ARCHIVED_ITEM_SEEDS = {16: 52261033, 32: 84261011, 48: 116261051}

# ------------------------------------------------------------------ dispatch plan

# (label, level, index within the load-floor list, j, cap, kind).
# kind: name = the depth query; off_end = j one past the path (gold NONE);
#       dead_end = a path tail asked for one step (gold NONE); dup = byte-identical re-dispatch
#       (issue #100); rung = the 256-token budget rung.
# Order is contractual: the NONE controls go first, the deepest cells last, so a cutoff spends the
# top of the curve rather than the gates that make any name hit mean something.
PLAN = [
    ("L32A_deadend", 32, 0, 1, MAX_TOKENS, "dead_end"),
    ("L64_deadend", 64, 0, 1, MAX_TOKENS, "dead_end"),
    ("L16_offend", 16, 0, 17, MAX_TOKENS, "off_end"),
    ("L32A_offend", 32, 0, 33, MAX_TOKENS, "off_end"),
    ("L48_offend", 48, 0, 49, MAX_TOKENS, "off_end"),
    ("L64_offend", 64, 0, 65, MAX_TOKENS, "off_end"),
    ("L16_j8", 16, 0, 8, MAX_TOKENS, "name"),
    ("L16_j16", 16, 0, 16, MAX_TOKENS, "name"),
    ("L32A_j8", 32, 0, 8, MAX_TOKENS, "name"),
    ("L32A_j16", 32, 0, 16, MAX_TOKENS, "name"),
    ("L32A_j24", 32, 0, 24, MAX_TOKENS, "name"),
    ("L32A_j32", 32, 0, 32, MAX_TOKENS, "name"),
    ("L48_j8", 48, 0, 8, MAX_TOKENS, "name"),
    ("L48_j16", 48, 0, 16, MAX_TOKENS, "name"),
    ("L48_j24", 48, 0, 24, MAX_TOKENS, "name"),
    ("L48_j32", 48, 0, 32, MAX_TOKENS, "name"),
    ("L48_j40", 48, 0, 40, MAX_TOKENS, "name"),
    ("L64_j8", 64, 0, 8, MAX_TOKENS, "name"),
    ("L64_j16", 64, 0, 16, MAX_TOKENS, "name"),
    ("L64_j24", 64, 0, 24, MAX_TOKENS, "name"),
    ("L64_j32", 64, 0, 32, MAX_TOKENS, "name"),
    ("L64_j40", 64, 0, 40, MAX_TOKENS, "name"),
    ("L64_j48", 64, 0, 48, MAX_TOKENS, "name"),
    ("L64_j32_c256", 64, 0, 32, 256, "rung"),
    ("L48_j40_dup", 48, 0, 40, MAX_TOKENS, "dup"),
    ("L64_j40_dup", 64, 0, 40, MAX_TOKENS, "dup"),
]

SHALLOW_CELLS = ("L16_j8", "L16_j16", "L32A_j8", "L32A_j16")
DUP_PAIRS = (("L48_j40", "L48_j40_dup"), ("L64_j40", "L64_j40_dup"))
RUNG_LABEL = "L64_j32_c256"
DELIVERY_SHALLOW_J = 16
DELIVERY_DEEP_J = 32

LAW_SPECS = [
    {"id": "input_load_wall", "quantity": "n_facts", "op": ">=", "threshold": 96,
     "statement": "censored if and only if n_facts >= 96",
     "declared_from": "the 96-fact cap-bound reading carried from the archived verdict arm"},
    {"id": "step_count_wall", "quantity": "j", "op": ">=", "threshold": 32,
     "statement": "censored if and only if j >= 32",
     "declared_from": "the archived flash-class censored step-32 cell at 96 facts"},
    {"id": "load_depth_product", "quantity": "n_facts_times_j", "op": ">=", "threshold": 3072,
     "statement": "censored if and only if n_facts * j >= 3072",
     "declared_from": "archived largest delivered product 64 * 32 = 2048 against smallest censored "
                      "product 96 * 32 = 3072"},
    {"id": "step40_wall", "quantity": "j", "op": ">=", "threshold": 40,
     "statement": "censored if and only if j >= 40",
     "declared_from": "the archived 27B-class tier on the same grid"},
]

CENSUS_PROMPT = ("Rule: for all x, y, z: if x precedes y and y precedes z, then x precedes z. "
                 "Facts: alby precedes birch. birch precedes cobin. Question: does alby precedes "
                 "cobin? Answer with exactly one word: yes or no.")

CALIBRATION = {"level": 8, "index": 0, "j": 2, "cap": 512}


# ------------------------------------------------------------------ item and gold machinery

_SERIES: dict = {}


def scan_series(level: int) -> dict:
    """Per-item scan with the entity-pool raise caught per item (issue #129 option (a)).

    `ladders.generate_items(level, count, seed_base)` aborts the whole series as soon as one
    large-C item exhausts the 2,700-name pool, which is what stops every archived ladder grid at
    k = 48. Here each candidate seed is built on its own, the raise is recorded by index, and the
    scan returns the items the level can actually build. Seeds are the generator's own formula
    (`seed_base + 2_000_000 * level + index`), so the item set is deterministic in the seed base
    and no selection happens at run time.
    """
    if level not in _SERIES:
        built: dict = {}
        raised = []
        for i in range(SCAN):
            try:
                built[i] = ladders.generate_items(level, 1, SEED_BASE + i)[0]
            except RuntimeError:
                raised.append(i)
        items = [built[i] for i in sorted(built)]
        lf_indices = [i for i in sorted(built) if len(built[i]["facts"]) == 2 * level]
        _SERIES[level] = {"generated": len(items), "raised": raised,
                          "first_raise_index": raised[0] if raised else None,
                          "load_floor": [built[i] for i in lf_indices],
                          "load_floor_indices": lf_indices}
    return _SERIES[level]


def load_floor(level: int) -> list:
    """The items whose fact count is 2 * level: exactly two disjoint k-edge paths, the smallest
    load in the corpus (issue #129's reachable family)."""
    return scan_series(level)["load_floor"]


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
    """Independent solver: the node reached from src by exactly `steps` direct links, or None.

    This is not the generator's label and not a BFS: it walks the edge function, so an off-by-one
    in the depth claim shows up as a different name rather than as a silent agreement.
    """
    adj = adjacency(item)
    cur = src
    for _ in range(steps):
        nxt = adj.get(cur)
        if nxt is None:
            return None
        cur = nxt
    return cur


def tails_of(item: dict) -> list:
    adj = adjacency(item)
    return sorted(t for t in {t for _, _, t in item["facts"]} if t not in adj)


def other_tail(item: dict, src: str) -> str:
    """The tail of the path that does NOT contain src: matched pseudo-gold for row C7."""
    own = terminal_at(item, src, item["level"])
    cands = [t for t in tails_of(item) if t != own]
    assert len(cands) == 1, ("expected one other tail", tails_of(item))
    return cands[0]


def item_for(level: int, index: int) -> dict:
    lf = load_floor(level)
    assert index < len(lf), f"level {level} has only {len(lf)} load-floor items"
    item = lf[index]
    check_item(item)
    return item


def dead_end_source(item: dict) -> str:
    """The control source for a dead-end cell: the first sorted out-degree-zero tail (round 55's
    rule, kept byte-identical so the archived control digests certify). Whether this is the query
    path's own tail or the other path's tail is recorded per record."""
    return tails_of(item)[0]


def pin_level64() -> dict:
    """Re-derive the pinned level-64 scan and refuse if the pin moved (issue #129)."""
    s = scan_series(64)
    lf = s["load_floor"]
    assert s["generated"] == L64_PIN["scan_generated"], ("level 64 scan moved", s["generated"])
    assert len(s["raised"]) == L64_PIN["scan_raised"], ("level 64 raises moved", len(s["raised"]))
    assert s["first_raise_index"] == L64_PIN["scan_first_raise_index"], "first raise index moved"
    assert len(lf) == 1, ("expected exactly one level-64 load-floor item", len(lf))
    it = lf[0]
    assert it["seed"] == L64_PIN["seed"], ("level-64 pin seed moved", it["seed"])
    assert list(it["query"]) == L64_PIN["query"], ("level-64 pin query moved", it["query"])
    assert len(it["facts"]) == L64_PIN["n_facts"], "level-64 pin fact count moved"
    scan_index = s["load_floor_indices"][0] if lf else None
    assert scan_index == L64_PIN["scan_index"], ("level-64 scan index moved", scan_index)
    return {"scan_generated": s["generated"], "scan_raised": len(s["raised"]),
            "scan_first_raise_index": s["first_raise_index"], "seed": it["seed"],
            "scan_index": scan_index, "query": list(it["query"]),
            "n_facts": len(it["facts"]), "load_floor_count": len(lf)}


# ------------------------------------------------------------------ prompts

def fact_block(item: dict) -> str:
    return "\n".join(f"{s} {r} {t}." for s, r, t in item["facts"])


def render_name(item: dict, src: str, j: int) -> str:
    """The round 55 name-or-NONE template, byte-identical (issue #129's registered format)."""
    return (f"{item['rule']}\nFacts:\n{fact_block(item)}\n\n"
            f"Task: start at {src} and follow the direct links for exactly {j} steps. "
            "Answer with exactly one entity name, or the single word NONE if the links run out "
            f"before {j} steps.")


def render_yesno(item: dict) -> str:
    """The round 51 template, byte-identical, used only to certify that the fact block dispatched
    here is the archived one."""
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
        assert item["seed"] == (L64_PIN["seed"] if level == 64
                                 else ARCHIVED_ITEM_SEEDS[level]), (level, item["seed"])
        if kind == "dead_end":
            src = dead_end_source(item)
        else:
            src = item["query"][0]
        walked = terminal_at(item, src, j)
        gold = NONE_GOLD if walked is None else walked
        assert (gold == NONE_GOLD) == (kind in ("off_end", "dead_end")), (label, gold, kind)
        own = terminal_at(item, item["query"][0], level)
        prompt = render_name(item, src, j)
        out.append({"label": label, "level": level, "index": index, "seed": item["seed"],
                    "src": src, "j": j, "cap": cap, "kind": kind, "gold": gold,
                    "own_terminal": own,
                    "dead_end_is_query_tail": bool(kind == "dead_end" and src == own),
                    "pseudo_gold": other_tail(item, item["query"][0]) if own is not None else "",
                    "prompt": prompt, "n_facts": len(item["facts"]),
                    "prompt_sha256": prompt_digest(prompt)})
    return out


# ------------------------------------------------------------------ archived certification

def certify_archived(rows: list) -> dict:
    """Fail closed unless every shared cell re-renders byte-identically to the archived record,
    and unless the level-48 fact block rebuilds the archived round 51 yes/no prompt."""
    by = {r["label"]: r for r in rows}
    problems = []
    certified = []
    for label, (kind, j, gold, digest, state, tokens) in sorted(R55_CELLS.items()):
        if label not in by:
            continue
        r = by[label]
        if r["prompt_sha256"] != digest:
            problems.append(f"prompt digest moved: {label}")
        if r["gold"] != gold:
            problems.append(f"gold moved: {label} {r['gold']} vs {gold}")
        if r["kind"] != kind or r["j"] != j:
            problems.append(f"cell shape moved: {label}")
        certified.append({"label": label, "kind": kind, "j": j, "prompt_sha256": digest,
                          "gold": gold, "archived_state": state,
                          "archived_completion_tokens": tokens})
    k48 = item_for(48, 0)
    if k48["seed"] != ARCHIVED_K48["seed"]:
        problems.append("k48 seed moved")
    if prompt_digest(render_yesno(k48))[:16] != ARCHIVED_K48["yesno_digest16"]:
        problems.append("k48 archived yes/no digest does not rebuild")
    return {"ok": not problems, "problems": problems, "cells": certified,
            "k48_yesno_digest16": prompt_digest(render_yesno(k48))[:16],
            "archived_model_digest": R55_MODEL_DIGEST, "archived_gate_blob": R55_BLOB,
            "build_model_digest": model_digest(),
            "build_matches_archived": model_digest() == R55_MODEL_DIGEST,
            "l64_pin": pin_level64(),
            "archived_item_seeds": ARCHIVED_ITEM_SEEDS}


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
    """The last generator-vocab name in the visible answer field, else the NONE sentinel, else
    undetermined. An empty answer field is not a delivery: on this deployment shape the reasoning
    channel precedes it and can consume the whole budget."""
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


def trace_names(trace: str, vocab: set) -> list:
    """Every generator-vocab name mentioned in the reasoning text, in mention order."""
    return [t.lower() for t in NAME_RE.findall(trace) if t.lower() in vocab]


def last_name_measure(name: str, trace: str, vocab: set):
    """Issue #94, order readout: is `name` the LAST entity the reasoning text mentions?

    The containment readout used by rounds 50, 55, 56 and 58 cannot separate "the walk reached the
    terminal" from "the traversal enumerated both path tails": on a long traversal every tail
    appears, so gold and pseudo-gold contain both sit at 1.0 and the gap is 0.0 (three refusals in
    a row). Position is a different question. A model that ran out of budget one name before
    emitting its answer should have the reached terminal as its most recent mention; a model that
    merely listed candidates has no reason for the reached one to be last.
    """
    names = trace_names(trace, vocab)
    if not name or not names:
        return None
    return names[-1] == name


def first_offset(name: str, trace: str):
    return trace.find(name) if name and name in trace else None


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


# ------------------------------------------------------------------ laws and tier

def law_predicts_censored(spec: dict, n_facts: int, j: int) -> bool:
    if spec["quantity"] == "n_facts":
        value = n_facts
    elif spec["quantity"] == "j":
        value = j
    elif spec["quantity"] == "n_facts_times_j":
        value = n_facts * j
    else:
        raise AssertionError(spec["quantity"])
    assert spec["op"] == ">="
    return value >= spec["threshold"]


def law_agreements(name_rows: list) -> dict:
    """Score each registered law as a prediction of the observed delivery state over the name cells.

    Observed state is D when the record produced a terminal (a delivered field carrying a generator
    name or the NONE sentinel is still not a terminal: only a declared name counts here) and C
    otherwise, which is what a "censored" prediction must match.
    """
    out = {}
    for spec in LAW_SPECS:
        agr = 0
        disagreements = []
        for r in name_rows:
            predicted = law_predicts_censored(spec, r["n_facts"], r["j"])
            observed_censored = r["declared"] is None
            if predicted == observed_censored:
                agr += 1
            else:
                disagreements.append({"label": r["label"], "n_facts": r["n_facts"], "j": r["j"],
                                      "predicted": "C" if predicted else "D",
                                      "observed": "C" if observed_censored else "D",
                                      "completion_tokens": r["completion_tokens"]})
        out[spec["id"]] = {"agreed": agr, "n": len(name_rows), "disagreements": disagreements}
    return out


def wall_tier(agr: dict, n_cells: int, line: int = TIER_LINE) -> str:
    """The registered tier rule: the unique law at or above `line` of `n_cells` wins; a tie reads
    laws_not_separable; nothing at the line reads no_wall_law."""
    if n_cells == 0:
        return "no_name_cells"
    top = max(v["agreed"] for v in agr.values())
    at_line = sorted(k for k, v in agr.items() if v["agreed"] >= line)
    if not at_line:
        return "no_wall_law"
    if len(at_line) > 1:
        return "laws_not_separable"
    if top < line:
        return "no_wall_law"
    return at_line[0]


def pockets(name_rows: list) -> list:
    """Name cells that were censored although no registered law predicted a censoring: coordinates
    the grid was not built to catch (round 58's finding-2 class)."""
    out = []
    for r in name_rows:
        if r["declared"] is not None:
            continue
        if any(law_predicts_censored(s, r["n_facts"], r["j"]) for s in LAW_SPECS):
            continue
        out.append({"label": r["label"], "n_facts": r["n_facts"], "j": r["j"],
                    "product": r["n_facts"] * r["j"],
                    "completion_tokens": r["completion_tokens"],
                    "finish_reason": r["finish_reason"]})
    return out


def spearman(xs: list, ys: list):
    """Rank correlation with ties averaged (stdlib only)."""
    if len(xs) != len(ys) or len(xs) < 3:
        return None

    def ranks(vals):
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        out = [0.0] * len(vals)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            rank = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                out[order[k]] = rank
            i = j + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    mx = sum(rx) / len(rx)
    my = sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    denx = sum((a - mx) ** 2 for a in rx) ** 0.5
    deny = sum((b - my) ** 2 for b in ry) ** 0.5
    if denx == 0 or deny == 0:
        return None
    return round(num / (denx * deny), 4)


# ------------------------------------------------------------------ gate

def gate_spec() -> dict:
    rows = plan_prompts()
    cert = certify_archived(rows)
    if not cert["ok"]:
        raise SystemExit("archived certification refused: " + "; ".join(cert["problems"]))
    name_cells = sum(1 for r in rows if r["kind"] == "name")
    return {
        "schema": GATE_SCHEMA,
        "question": ("On a flash-next-class build whose serving-id digest matches no archived build "
                     "in this repository, with the round 55 name-or-NONE response format re-pinned "
                     "byte-identically (every cell's prompt digest frozen in this gate before the "
                     "first prompt) and the identical four registered wall laws, does delivery on "
                     "the one-of-many entity-name answer space over the matched load-times-depth "
                     "grid (32, 64, 96 and 128 facts against j = 8, 16, 24, 32, 40, and 48 on the "
                     "128-fact item) (a) sit at the input load, at the step count, at their "
                     "product, or at the 27B class's step-40 boundary; (b) keep every delivered "
                     "terminal correct while only delivery turns over; (c) reproduce the archived "
                     "flash-class states at the nine shared coordinates; (d) refuse with no false "
                     "name when the links run out; (e) hold self-agreement on the re-dispatched "
                     "boundary cells; and (f) pass or refuse itself on the order-based "
                     "trace-provenance control?"),
        "criteria": {
            "C1_shallow_reproduction": {
                "statement": "correct declared terminal on L16_j8, L16_j16, L32A_j8, L32A_j16 is at "
                             "least 3 of 4",
                "threshold": "3/4"},
            "C2_none_controls_honest": {
                "statement": ("two parts, the archived amendment from round 56 carried by round 58: "
                              "the gated part is zero false names among the delivered NONE-gold "
                              "controls with at least 3 of them delivered; the censored controls are "
                              "reported as non-deliveries, never scored as misses, and the control "
                              "delivery rate is reported and not gated"),
                "threshold": "0 false names, at least 3/6 controls delivered"},
            "C3_wall_laws": {
                "statement": ("four registered laws over the 17 name cells as predictions of "
                              "censoring: the tier is the unique law agreeing on at least 14 of 17, "
                              "a tie at or above the line reads laws_not_separable, and no law at "
                              "the line reads no_wall_law"),
                "threshold": "unique law at 14 of 17"},
            "C4_accuracy_vs_delivery": {
                "statement": ("every produced terminal on a name cell is the gold name, no name cell "
                              "is delivered-but-undetermined, and every name-cell non-delivery "
                              "carries finish_reason length at completion_tokens equal to its "
                              "requested cap"),
                "threshold": "0 false names, 0 undetermined, all non-deliveries cap-bound"},
            "C5_archived_flash_column": {
                "statement": ("delivery-state agreement with the archived flash-class record over "
                              "the nine shared name cells L16_j8, L16_j16, L32A_j8, L32A_j16, "
                              "L32A_j24, L32A_j32, L48_j8, L48_j16, L48_j48 is at least 6 of 9, and "
                              "no shared coordinate where both sides delivered carries two different "
                              "names"),
                "threshold": "6/9 state agreement, 0 name contradictions"},
            "C6_self_agreement": {
                "statement": "both byte-identical re-dispatch pairs agree on the declared answer and "
                            "on completion tokens",
                "threshold": "2/2"},
            "C7_trace_provenance_lastmention": {
                "statement": ("among the name-gold records that produced no terminal and carry a "
                              "non-empty reasoning channel, the rate at which the gold terminal is "
                              "the last entity named in the reasoning text minus the same rate for "
                              "the matched pseudo-gold (the other path's tail, same item, same role) "
                              "is at least 0.50 over at least 3 records; containment rates are "
                              "reported for comparability with rounds 50, 55, 56 and 58 and are "
                              "never gated"),
                "threshold": "0.50 gap over at least 3 records"},
            "C8_census": {
                "statement": ("every dispatched record carries the message-field census and the "
                              "merge rule names the reasoning-supplying field (issue #105); the "
                              "number of records with an open channel is reported"),
                "threshold": "all dispatched records"},
            "C9_monotone_quantity": {
                "statement": ("Spearman rank correlation between completion tokens and each of j, "
                              "n_facts and n_facts * j over the name cells that produced a terminal "
                              "is at least 0.60 in absolute value for at least one quantity"),
                "threshold": "abs(rho) >= 0.60 for one of three"},
            "H1_budget_rung": {
                "statement": "the 256-token rung on L64_j32 produces no terminal (registered as a "
                            "predicted non-delivery, carried from the archived budget rungs)",
                "threshold": "non-delivered"},
            "X1_cross_class_states": {
                "registered": False,
                "statement": ("post-hoc only: delivery-state agreement with the killed round-58 27B "
                              "firing at the 16 coordinates both grids dispatched. That archive "
                              "carries no commit and no PR, so it is disclosed provenance and no "
                              "tier input reads it"),
                "threshold": "reported, not gated"},
        },
        "tier_rule": ("dispatch_incomplete if any planned cell was not dispatched; else "
                      "controls_invalid if the gated part of C2 fails; else accuracy_turnover if C4 "
                      "fails; else the unique wall law at or above 14 of 17 name cells; else "
                      "laws_not_separable if two or more laws reach the line; else no_wall_law"),
        "laws": LAW_SPECS,
        "tier_line": TIER_LINE,
        "name_cells": name_cells,
        "cells": [{"label": r["label"], "level": r["level"], "seed": r["seed"], "src": r["src"],
                   "j": r["j"], "cap": r["cap"], "kind": r["kind"], "gold": r["gold"],
                   "own_terminal": r["own_terminal"], "n_facts": r["n_facts"],
                   "dead_end_is_query_tail": r["dead_end_is_query_tail"],
                   "prompt_sha256": r["prompt_sha256"]} for r in rows],
        "dispatch": {"planned_calls": len(PLAN), "call_cap": CALL_CAP, "temperature": 0.0,
                     "max_tokens_cap": MAX_TOKENS, "dispatch_budget_s": DISPATCH_BUDGET_S,
                     "calibration_call": CALIBRATION,
                     "health_call_cap": 256,
                     "order_note": "NONE controls first, deepest name cells last"},
        "certification": cert,
        "health": {"id": "H0", "prompt_sha256": prompt_digest(CENSUS_PROMPT), "cap": 256},
        "delivery_split": {"shallow_j_max": DELIVERY_SHALLOW_J, "deep_j_min": DELIVERY_DEEP_J,
                           "flag_at": 0.25},
    }


def gate_blob(spec: dict) -> str:
    blob_source = {k: v for k, v in spec.items() if k != "blob"}
    return hashlib.sha256(json.dumps(blob_source, sort_keys=True).encode()).hexdigest()


# ------------------------------------------------------------------ scoring

def score_records(records: list, spec: dict) -> dict:
    by = {r["label"]: r for r in records}
    planned = {c["label"]: c for c in spec["cells"]}
    dispatched = [l for l in planned if l in by]
    missing = sorted(set(planned) - set(dispatched))
    name_rows = [by[l] for l in planned if planned[l]["kind"] == "name" and l in by]
    out: dict = {}

    c1 = [by[l]["correct"] for l in SHALLOW_CELLS if l in by]
    out["C1_shallow_reproduction"] = {"cells": list(SHALLOW_CELLS),
                                      "correct": sum(1 for c in c1 if c), "n": len(c1),
                                      "pass": len(c1) == 4 and sum(1 for c in c1 if c) >= 3}

    controls = [r for r in records if r["gold"] == NONE_GOLD]
    delivered_controls = [r for r in controls if r["delivered"]]
    false_control_names = [r["label"] for r in delivered_controls if r["declared"] != NONE_GOLD]
    c2_pass = (len(delivered_controls) >= 3 and not false_control_names)
    out["C2_none_controls_honest"] = {
        "planned": len(controls), "delivered": len(delivered_controls),
        "censored_not_scored": len(controls) - len(delivered_controls),
        "delivery_rate": round(len(delivered_controls) / len(controls), 4) if controls else None,
        "correct_none": sum(1 for r in delivered_controls if r["declared"] == NONE_GOLD),
        "false_names": false_control_names, "pass": c2_pass, "gated_part": "false_names"}

    agr = law_agreements(name_rows)
    tier_law = wall_tier(agr, len(name_rows))
    out["C3_wall_laws"] = {"laws": agr, "tier_law": tier_law, "tier_line": TIER_LINE,
                           "name_cells": len(name_rows),
                           "pockets": pockets(name_rows),
                           "pass": tier_law in {s["id"] for s in LAW_SPECS}}

    produced = [r for r in name_rows if r["declared"] is not None]
    false_names = [r["label"] for r in produced if r["correct"] is not True]
    undetermined = [r["label"] for r in name_rows if r["delivered"] and r["declared"] is None]
    non_delivered = [r for r in name_rows if not r["delivered"]]
    cap_bound = [r["label"] for r in non_delivered
                 if r["finish_reason"] == "length" and r["completion_tokens"] == r["cap"]]
    not_cap_bound = sorted({r["label"] for r in non_delivered} - set(cap_bound))
    out["C4_accuracy_vs_delivery"] = {
        "name_cells": len(name_rows), "produced_terminals": len(produced),
        "correct_terminals": sum(1 for r in produced if r["correct"] is True),
        "false_names": false_names, "undetermined": undetermined,
        "non_deliveries": [r["label"] for r in non_delivered], "cap_bound": cap_bound,
        "not_cap_bound": not_cap_bound,
        "pass": (len(name_rows) == len(produced) + len(non_delivered) and not false_names
                 and not undetermined and not not_cap_bound)}

    def rate(rows):
        return round(sum(1 for r in rows if r["declared"] is not None) / len(rows), 4) if rows \
            else None
    sh = [r for r in name_rows if r["j"] <= DELIVERY_SHALLOW_J]
    dp = [r for r in name_rows if r["j"] >= DELIVERY_DEEP_J]
    r_sh, r_dp = rate(sh), rate(dp)
    out["C4_accuracy_vs_delivery"]["delivery_split"] = {
        "shallow_j_max": DELIVERY_SHALLOW_J, "deep_j_min": DELIVERY_DEEP_J,
        "delivery_shallow": r_sh, "delivery_deep": r_dp,
        "drop": (round(r_sh - r_dp, 4) if r_sh is not None and r_dp is not None else None),
        "flag_at": spec["delivery_split"]["flag_at"],
        "delivery_bound": (r_sh is not None and r_dp is not None
                           and r_sh - r_dp >= spec["delivery_split"]["flag_at"])}

    cert_cells = {c["label"]: c for c in spec["certification"]["cells"]}
    shared = [l for l in cert_cells if cert_cells[l]["kind"] == "name"]
    states, extensions, regressions, contradictions = [], [], [], []
    for label in sorted(shared):
        arch = cert_cells[label]
        if label not in by:
            continue
        mine = "D" if by[label]["declared"] is not None else "C"
        if mine == arch["archived_state"]:
            states.append(label)
        elif arch["archived_state"] == "C" and mine == "D":
            extensions.append(label)
        else:
            regressions.append(label)
        if mine == "D" and arch["archived_state"] == "D" and by[label]["declared"] != arch["gold"]:
            contradictions.append(label)
    out["C5_archived_flash_column"] = {
        "shared_name_cells": len(shared), "state_agreement": len(states),
        "extensions_past_archived": extensions, "regressions_below_archived": regressions,
        "name_contradictions": contradictions,
        "build_matches_archived_build": spec["certification"]["build_matches_archived"],
        "pass": (len(states) >= 6 and not contradictions)}

    agree = []
    for a, b in DUP_PAIRS:
        if a in by and b in by:
            agree.append({"pair": [a, b], "answer_agrees": by[a]["declared"] == by[b]["declared"],
                          "tokens_agree": by[a]["completion_tokens"] == by[b]["completion_tokens"],
                          "declared": by[a]["declared"],
                          "completion_tokens": [by[a]["completion_tokens"],
                                               by[b]["completion_tokens"]]})
    out["C6_self_agreement"] = {"pairs": agree,
                                "agreements": sum(1 for x in agree
                                                  if x["answer_agrees"] and x["tokens_agree"]),
                                "pass": len(agree) == len(DUP_PAIRS)
                                        and all(x["answer_agrees"] and x["tokens_agree"]
                                                for x in agree)}

    undelivered = [r for r in name_rows
                   if r["declared"] is None and r["trace_chars"] and r["gold"] != NONE_GOLD]
    if undelivered:
        g_last = sum(1 for r in undelivered if r["gold_is_last_trace_name"])
        p_last = sum(1 for r in undelivered if r["pseudo_is_last_trace_name"])
        g_cont = sum(1 for r in undelivered if r["gold_in_trace"])
        p_cont = sum(1 for r in undelivered if r["pseudo_in_trace"])
        n = len(undelivered)
        out["C7_trace_provenance_lastmention"] = {
            "n": n,
            "gold_last_rate": round(g_last / n, 4), "pseudo_last_rate": round(p_last / n, 4),
            "gap": round((g_last - p_last) / n, 4),
            "gold_never_mentioned": sum(1 for r in undelivered if not r["gold_in_trace"]),
            "other_tail_last": sum(1 for r in undelivered
                                   if r["trace_last_name"] and r["trace_last_name"] not in
                                   (r["gold"], r.get("pseudo_gold") or "")),
            "containment_legacy": {"gold_rate": round(g_cont / n, 4),
                                   "pseudo_rate": round(p_cont / n, 4),
                                   "gap": round((g_cont - p_cont) / n, 4)},
            "first_mention_order": [{"label": r["label"], "gold_offset": r["gold_offset"],
                                     "pseudo_offset": r["pseudo_offset"]} for r in undelivered],
            "admissible": (n >= 3 and (g_last - p_last) / n >= 0.50),
            "pass": (n >= 3 and (g_last - p_last) / n >= 0.50)}
    else:
        out["C7_trace_provenance_lastmention"] = {
            "n": 0, "gold_last_rate": None, "pseudo_last_rate": None, "gap": None,
            "containment_legacy": {"gold_rate": None, "pseudo_rate": None, "gap": None},
            "admissible": False, "pass": False}

    census_present = [r for r in records if "census" in r and "fields" in r["census"]]
    open_channel = [r for r in records if r.get("census", {}).get("reasoning_field")]
    out["C8_census"] = {"records": len(records), "with_census": len(census_present),
                        "with_open_channel": len(open_channel),
                        "reasoning_fields": sorted({r.get("census", {}).get("reasoning_field", "")
                                                    for r in records}),
                        "pass": len(census_present) == len(records) and len(records) == len(dispatched)}

    tok = [r["completion_tokens"] for r in produced if r["completion_tokens"] is not None]
    rho = {}
    if len(tok) >= 3:
        rho["j"] = spearman([r["j"] for r in produced], tok)
        rho["n_facts"] = spearman([r["n_facts"] for r in produced], tok)
        rho["n_facts_times_j"] = spearman([r["n_facts"] * r["j"] for r in produced], tok)
    best = max((abs(v) for v in rho.values() if v is not None), default=None)
    out["C9_monotone_quantity"] = {"n": len(tok), "rho": rho, "best_abs_rho": best,
                                   "pass": best is not None and best >= 0.60}

    if RUNG_LABEL in by:
        r = by[RUNG_LABEL]
        out["H1_budget_rung"] = {"label": RUNG_LABEL, "produced_terminal": r["declared"] is not None,
                                 "completion_tokens": r["completion_tokens"],
                                 "finish_reason": r["finish_reason"],
                                 "pass": r["declared"] is None}
    else:
        out["H1_budget_rung"] = {"label": RUNG_LABEL, "pass": False, "dispatched": False}

    x1 = []
    for label, (state, tokens) in sorted(R58_STATES.items()):
        if label not in by:
            continue
        mine = "D" if by[label]["declared"] is not None else "C"
        x1.append({"label": label, "archived_state": state, "this_state": mine,
                   "archived_completion_tokens": tokens,
                   "this_completion_tokens": by[label]["completion_tokens"],
                   "agree": mine == state, "gold": by[label]["gold"]})
    out["X1_cross_class_states"] = {
        "registered": False, "coordinates": len(x1),
        "agreements": sum(1 for x in x1 if x["agree"]),
        "disagreements": [x for x in x1 if not x["agree"]],
        "this_build_extension": [x["label"] for x in x1
                                 if x["archived_state"] == "C" and x["this_state"] == "D"],
        "this_build_regression": [x["label"] for x in x1
                                  if x["archived_state"] == "D" and x["this_state"] == "C"]}

    if missing:
        tier = "dispatch_incomplete"
    elif not out["C2_none_controls_honest"]["pass"]:
        tier = "controls_invalid"
    elif not out["C4_accuracy_vs_delivery"]["pass"]:
        tier = "accuracy_turnover"
    elif tier_law in {s["id"] for s in LAW_SPECS}:
        tier = tier_law
    else:
        tier = tier_law

    flags = []
    if out["C4_accuracy_vs_delivery"]["delivery_split"]["delivery_bound"]:
        flags.append("delivery_bound_loss")
    if out["C7_trace_provenance_lastmention"]["n"] and \
            not out["C7_trace_provenance_lastmention"]["admissible"]:
        flags.append("trace_provenance_refused")
    if out["C6_self_agreement"]["agreements"] < len(DUP_PAIRS):
        flags.append("self_agreement_split")
    if out["C3_wall_laws"]["pockets"]:
        flags.append("unpredicted_pocket_present")
    if not out["C9_monotone_quantity"]["pass"]:
        flags.append("no_monotone_quantity")
    if out["C5_archived_flash_column"]["regressions_below_archived"]:
        flags.append("archived_state_regression")
    return {"tier": tier, "flags": flags, "criteria": out,
            "not_dispatched": missing, "model_digest": model_digest()}


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
    correct = (declared == gold) if declared is not None else None
    rec = {"label": spec_row["label"], "kind": spec_row["kind"], "level": spec_row["level"],
           "seed": spec_row["seed"], "src": spec_row["src"], "j": spec_row["j"],
           "cap": spec_row["cap"], "gold": gold, "own_terminal": spec_row["own_terminal"],
           "pseudo_gold": spec_row["pseudo_gold"],
           "dead_end_is_query_tail": spec_row["dead_end_is_query_tail"],
           "prompt_sha256": spec_row["prompt_sha256"], "prompt_chars": len(spec_row["prompt"]),
           "n_facts": spec_row["n_facts"], "content": content, "content_chars": len(content),
           "delivered": delivered, "declared": declared, "correct": correct,
           "trace": trace, "trace_chars": len(trace),
           "trace_last_name": last_trace_name(trace, vocab),
           "gold_is_last_trace_name": last_name_measure(gold, trace, vocab),
           "pseudo_is_last_trace_name": last_name_measure(spec_row["pseudo_gold"], trace, vocab),
           "gold_offset": first_offset(gold, trace) if gold != NONE_GOLD else None,
           "pseudo_offset": first_offset(spec_row["pseudo_gold"], trace),
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


def last_trace_name(trace: str, vocab: set):
    names = trace_names(trace, vocab)
    return names[-1] if names else None


# ------------------------------------------------------------------ issue #137 row-label guard

ROW_ID_RE = re.compile(r"\b([A-Z][0-9]{1,2})\b")
BLOB_RE = re.compile(r"[0-9a-f]{64}")
PINNED_BLOB_RE = re.compile(r"blob:\s*`?([0-9a-f]{64})", re.I)


def check_readme_rows(readme_text: str, gate: dict, records: list, allow_blobs: set = None) -> dict:
    """Every gate-row id quoted in README.md must exist in this round's frozen gate; the blob quoted
    in README.md must equal the compact sorted-key sha256 of gate.json (its own `blob` field
    excluded); and every raw.jsonl record must carry that blob (issue #137). A quoted token counts
    as defined if it is a gate row id, the health row id, or an item shorthand that prefixes a cell
    label of this gate (`L48` for `L48_j40`); a label of the shape `L48_j40` never reads as a row
    id at all, because the underscore keeps it one word."""
    allow_blobs = allow_blobs or set()
    defined = ({str(cid).split("_")[0] for cid in gate["criteria"]} | {gate["health"]["id"]}
               | {str(c["label"]).split("_")[0] for c in gate["cells"]})
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
    cited = set(BLOB_RE.findall(readme_text)) - {blob} - allow_blobs
    if cited:
        problems.append({"kind": "uncertified_blob_cited_in_readme", "blobs": sorted(cited)})
    stale = [r.get("label") for r in records if r.get("gate") != blob]
    if stale:
        problems.append({"kind": "raw_record_stale_blob", "labels": stale})
    gate_file_rows = {c["label"]: c for c in gate["cells"]}
    raw_rows = {r.get("label") for r in records}
    if not raw_rows <= set(gate_file_rows):
        problems.append({"kind": "raw_label_not_in_gate",
                         "labels": sorted(raw_rows - set(gate_file_rows))})
    return {"ok": not problems, "problems": problems, "rows_named": sorted(named),
            "rows_defined": sorted(defined), "blob": blob}


# ------------------------------------------------------------------ selftest

def selftest() -> None:
    checks = 0

    def ok(cond, msg):
        nonlocal checks
        checks += 1
        assert cond, f"selftest failed: {msg}"

    # 1. determinism: the same series re-derives byte-identically from the same seed base
    a = [ladders.item_jsonl(x) for x in ladders.generate_items(8, 5, SEED_BASE)]
    b = [ladders.item_jsonl(x) for x in ladders.generate_items(8, 5, SEED_BASE)]
    ok(a == b, "series not deterministic")

    # 2. the archived load-floor items really are the archived ones on this checkout
    for level, seed in ARCHIVED_ITEM_SEEDS.items():
        it = item_for(level, 0)
        ok(it["seed"] == seed, f"level {level} load-floor seed moved")
        ok(len(it["facts"]) == 2 * level, f"level {level} item is not load-floor")
        check_item(it)

    # 3. the level-64 pin (issue #129 option (a) per-item scan) holds, and moving it is refused
    pin = pin_level64()
    ok(pin["seed"] == L64_PIN["seed"], "level-64 pin seed moved")
    ok(pin["scan_generated"] == L64_PIN["scan_generated"], "level-64 scan count moved")
    ok(pin["scan_raised"] == L64_PIN["scan_raised"], "level-64 raise count moved")
    ok(pin["scan_first_raise_index"] == L64_PIN["scan_first_raise_index"], "first raise moved")
    ok(pin["query"] == L64_PIN["query"], "level-64 query moved")
    ok(pin["n_facts"] == 128, "level-64 fact count moved")
    ok(pin["load_floor_count"] == 1, "level-64 load-floor count moved")
    _SERIES[64] = dict(_SERIES[64], generated=234)
    raised = False
    try:
        pin_level64()
    except AssertionError:
        raised = True
    ok(raised, "planted scan mutation must refuse the pin before any prompt")
    del _SERIES[64]
    ok(pin_level64()["scan_generated"] == 235, "pin recovers after the planted mutation")

    # 4. the archived round 51 k = 48 yes/no prompt rebuilds from this round's own fact block
    k48 = item_for(48, 0)
    ok(k48["seed"] == ARCHIVED_K48["seed"], "certified k48 seed moved")
    ok(prompt_digest(render_yesno(k48))[:16] == ARCHIVED_K48["yesno_digest16"],
       "reconstructed yes/no digest does not match the archived record")
    mutated = {"level": 48, "rule": k48["rule"],
               "facts": [list(f) for f in k48["facts"]], "query": list(k48["query"])}
    mutated["facts"][0] = [mutated["facts"][0][0], "precedes", "zznotanentity"]
    ok(prompt_digest(render_yesno(mutated))[:16] != ARCHIVED_K48["yesno_digest16"],
       "planted fact-block mutation must move the digest")

    # 5. archived response-format certification: every shared cell re-renders byte-identically
    rows = plan_prompts()
    cert = certify_archived(rows)
    ok(cert["ok"], "archived certification refused: " + "; ".join(cert["problems"]))
    ok(len(cert["cells"]) == len(R55_CELLS), "not every archived shared cell was certified")
    ok(cert["k48_yesno_digest16"] == ARCHIVED_K48["yesno_digest16"], "k48 digest in certification")
    tampered = [dict(r) for r in rows]
    tampered[6]["prompt"] = tampered[6]["prompt"] + " "
    tampered[6]["prompt_sha256"] = prompt_digest(tampered[6]["prompt"])
    ok(not certify_archived(tampered)["ok"],
       "planted trailing-space prompt mutation must be refused")
    wrong_gold = [dict(r) for r in rows]
    wrong_gold[6]["gold"] = "notthegold"
    ok(not certify_archived(wrong_gold)["ok"], "planted gold mutation must be refused")

    # 6. solver arithmetic on a hand-built item, independent of the generator
    hand = {"level": 3, "rule": "R", "facts": [["a", "precedes", "b"], ["b", "precedes", "c"],
                                               ["c", "precedes", "d"], ["p", "precedes", "q"],
                                               ["q", "precedes", "r"], ["r", "precedes", "s"]],
            "query": ["a", "precedes", "d"]}
    ok(terminal_at(hand, "a", 1) == "b", "one step")
    ok(terminal_at(hand, "a", 3) == "d", "three steps")
    ok(terminal_at(hand, "a", 4) is None, "one past the end is None")
    ok(terminal_at(hand, "zz", 1) is None, "absent source is None")
    ok(terminal_at(hand, "d", 1) is None, "a tail has no outgoing edge")
    ok(other_tail(hand, "a") == "s", "matched pseudo-gold is the other path tail")
    ok(tails_of(hand) == ["d", "s"], "tails sorted")

    # 7. scorer arithmetic on the answer field
    vocab = {"glag", "quonk", "thrend", "knudnd"}
    ok(declared_answer("thrend", vocab) == ("thrend", True), "plain name")
    ok(declared_answer("NONE", vocab) == (NONE_GOLD, True), "plain none")
    ok(declared_answer("", vocab) == (None, False), "empty field is not a delivery")
    ok(declared_answer("   ", vocab) == (None, False), "whitespace is not a delivery")
    ok(declared_answer("The chain ends at thrend.", vocab) == ("thrend", True), "name in prose")
    ok(declared_answer("glag then thrend", vocab) == ("thrend", True), "last name wins")
    ok(declared_answer("I cannot say", vocab) == (None, True), "delivered but undetermined")
    ok(declared_answer("knudnd", {"glag", "thrend"}) == (None, True),
       "a name outside the item vocabulary is not a terminal claim")

    # 8. planted negatives on the per-record scorer
    spec_row = {"label": "x", "kind": "name", "level": 8, "seed": 1, "src": "glag", "j": 4,
                "cap": 2048, "gold": "thrend", "own_terminal": "knudnd", "pseudo_gold": "quonk",
                "dead_end_is_query_tail": False, "prompt_sha256": "0" * 64, "prompt": "p",
                "n_facts": 16}
    item8 = {"facts": [["glag", "precedes", "quonk"], ["quonk", "precedes", "thrend"]]}
    resp = {"message": {"content": "quonk",
                        "reasoning_content": "walking: glag x thrend, then the other tail quonk"},
            "finish_reason": "stop", "completion_tokens": 12, "prompt_tokens": 5, "wall_s": 0.1}
    rec = score_record(spec_row, resp, item8, "")
    ok(rec["correct"] is False, "planted off-by-one answer must be scored wrong")
    ok(rec["gold_in_trace"] is True and rec["pseudo_in_trace"] is True, "containment arithmetic")
    ok(rec["gold_is_last_trace_name"] is False and rec["pseudo_is_last_trace_name"] is True,
       "planted containment trap: both tails listed, the pseudo-gold mentioned last")
    ok(rec["census"]["reasoning_field"] == "reasoning_content", "census merge rule")
    ok(rec["trace_last_name"] == "quonk", "last trace name")

    # 9. planted zero-trace and reasoning-field fallback shapes
    resp2 = {"message": {"content": "thrend", "reasoning": ""}, "finish_reason": "stop",
             "completion_tokens": 3, "prompt_tokens": 5, "wall_s": 0.1}
    rec2 = score_record(spec_row, resp2, item8, "")
    ok(rec2["census"]["reasoning_field"] == "" and rec2["trace_chars"] == 0, "zero-trace shape")
    resp2b = {"message": {"content": "thrend", "reasoning_content": "", "reasoning": "glag thrend"},
              "finish_reason": "stop", "completion_tokens": 4, "prompt_tokens": 5, "wall_s": 0.1}
    rec2b = score_record(spec_row, resp2b, item8, "")
    ok(rec2b["census"]["reasoning_field"] == "reasoning" and rec2b["trace_chars"] > 0,
       "issue #105 fallback to the reasoning field")

    # 10. planted negative: an empty answer field at the cap is a non-delivery, not a wrong answer
    resp3 = {"message": {"content": "", "reasoning_content": "x" * 500}, "finish_reason": "length",
             "completion_tokens": 2048, "prompt_tokens": 5, "wall_s": 0.1}
    rec3 = score_record(spec_row, resp3, item8, "")
    ok(rec3["delivered"] is False and rec3["correct"] is None and rec3["declared"] is None,
       "censored is not wrong")
    # 10b. planted negative: an empty pseudo-gold never reads as present in the trace
    rec3b = score_record(dict(spec_row, pseudo_gold=""),
                         {"message": {"content": "", "reasoning_content": "glag thrend"},
                          "finish_reason": "length", "completion_tokens": 2048,
                          "prompt_tokens": 5, "wall_s": 0.1}, item8, "")
    ok(rec3b["pseudo_in_trace"] is False and rec3b["gold_in_trace"] is True,
       "empty pseudo-gold guard")
    ok(rec3b["pseudo_is_last_trace_name"] is None, "empty pseudo-gold has no last-mention verdict")

    # 11. sanitizer: no endpoint value, URL, address or path survives. The fixture below uses the
    # RFC 5737 documentation addresses and an unusable .invalid domain; nothing in this file names a
    # real endpoint (public-only rule).
    probe = ("see http://example.invalid/x and 198.51.100.7:8080 and /root/models/f.bin "
             + os.environ.get("NIGHTLY_MODEL_ID", "SENTINEL") * 2)
    s = sanitize(probe)
    ok("http" not in s and "198.51.100.7" not in s and "/root/" not in s, "sanitizer patterns")
    ok(os.environ.get("NIGHTLY_MODEL_ID", "") not in s or not os.environ.get("NIGHTLY_MODEL_ID"),
       "serving id must not survive the sanitizer")

    # 12. the law predictor: each threshold on its own terms, both sides of each boundary
    by_id = {s["id"]: s for s in LAW_SPECS}
    ok(law_predicts_censored(by_id["input_load_wall"], 96, 8) is True, "96 facts is at the line")
    ok(law_predicts_censored(by_id["input_load_wall"], 64, 32) is False, "64 facts is below")
    ok(law_predicts_censored(by_id["step_count_wall"], 128, 32) is True, "step 32 is at the line")
    ok(law_predicts_censored(by_id["step_count_wall"], 128, 24) is False, "step 24 is below")
    ok(law_predicts_censored(by_id["step40_wall"], 32, 40) is True, "step 40 is at the line")
    ok(law_predicts_censored(by_id["step40_wall"], 32, 32) is False, "step 32 is below step 40")
    ok(law_predicts_censored(by_id["load_depth_product"], 96, 32) is True, "3072 is at the line")
    ok(law_predicts_censored(by_id["load_depth_product"], 64, 32) is False, "2048 is below 3072")
    ok(law_predicts_censored(by_id["load_depth_product"], 128, 24) is True, "3072 from 128 x 24")
    refused = False
    try:
        law_predicts_censored({"quantity": "bogus", "op": ">=", "threshold": 1}, 1, 1)
    except AssertionError:
        refused = True
    ok(refused, "planted unknown quantity must refuse")

    # 13. the tier rule over planted agreement counts
    def fake(agr):
        return {k: {"agreed": v, "n": 17, "disagreements": []} for k, v in agr.items()}
    ok(wall_tier(fake({"input_load_wall": 15, "step_count_wall": 12, "load_depth_product": 11,
                       "step40_wall": 10}), 17) == "input_load_wall", "unique law at the line")
    ok(wall_tier(fake({"input_load_wall": 14, "step_count_wall": 9, "load_depth_product": 9,
                       "step40_wall": 9}), 17) == "input_load_wall", "exactly at the line counts")
    ok(wall_tier(fake({"input_load_wall": 13, "step_count_wall": 13, "load_depth_product": 12,
                       "step40_wall": 12}), 17) == "no_wall_law", "below the line reads no law")
    ok(wall_tier(fake({"step40_wall": 15, "step_count_wall": 15, "load_depth_product": 12,
                       "input_load_wall": 12}), 17) == "laws_not_separable",
       "two laws at the line must not be resolved by preference")
    ok(wall_tier(fake({"step40_wall": 17, "step_count_wall": 17, "load_depth_product": 17,
                       "input_load_wall": 17}), 17) == "laws_not_separable",
       "a law set that fits everything is not evidence of a wall")
    ok(wall_tier(fake({"step40_wall": 5, "step_count_wall": 4, "load_depth_product": 4,
                       "input_load_wall": 4}), 0) == "no_name_cells", "empty grid has no tier")

    # 14. planted law agreement over a real coordinate set, plus the pocket detector
    coords = [{"label": "c1", "n_facts": 32, "j": 8, "declared": "aa", "completion_tokens": 400,
               "finish_reason": "stop"},
              {"label": "c2", "n_facts": 96, "j": 8, "declared": "bb", "completion_tokens": 500,
               "finish_reason": "stop"},
              {"label": "c3", "n_facts": 96, "j": 32, "declared": None, "completion_tokens": 2048,
               "finish_reason": "length"},
              {"label": "c4", "n_facts": 128, "j": 24, "declared": None, "completion_tokens": 2048,
               "finish_reason": "length"}]
    agr = law_agreements(coords)
    ok(agr["input_load_wall"]["agreed"] == 3, "input load law agrees on 3 of 4 planted")
    ok(agr["step_count_wall"]["agreed"] == 3, "step count law agrees on 3 of 4 planted")
    ok(agr["step40_wall"]["agreed"] == 2, "step40 law covers 2 of 4 planted")
    ok(agr["load_depth_product"]["agreed"] == 4, "the product law fits every planted cell, which is "
                                                 "exactly why a law that fits is not a wall")
    pk = pockets(coords)
    ok([p["label"] for p in pk] == [], "planted censored cells are predicted by the laws")
    pocket_coords = [dict(coords[0]), dict(coords[1]), dict(coords[2]),
                     {"label": "c5", "n_facts": 64, "j": 24, "declared": None,
                      "completion_tokens": 2048, "finish_reason": "length"}]
    pocket_coords[1]["declared"] = "bb"
    pk2 = pockets(pocket_coords)
    ok([p["label"] for p in pk2] == ["c5"], "planted below-threshold pocket is caught")
    ok(pk2[0]["product"] == 1536, "pocket product reported")
    ok(wall_tier(law_agreements(pocket_coords), 4, line=3) == "laws_not_separable",
       "planted tie at the planted line")

    # 15. Spearman arithmetic, including ties
    ok(spearman([1, 2, 3], [1, 2, 3]) == 1.0, "perfect order")
    ok(spearman([1, 2, 3], [3, 2, 1]) == -1.0, "reversed order")
    ok(spearman([1, 2, 3], [1, 2, 2]) == 0.8660, "ties averaged")
    ok(abs(spearman([1, 2, 3], [3, 1, 2])) < 0.6, "scrambled ranks")
    ok(spearman([1, 2], [1, 2]) is None, "below three points is not a correlation")
    ok(spearman([1, 1, 1], [1, 2, 3]) is None, "a constant side has no correlation")

    # 16. the plan is internally consistent: caps, budget, gold classes, digest sharing
    full = gate_spec()
    ok(len(rows) == len(PLAN), "plan expanded")
    ok(len(rows) + 2 <= CALL_CAP, "plan plus the health and calibration calls inside the 40 cap")
    ok(all(r["cap"] <= MAX_TOKENS for r in rows), "protocol token cap")
    ok(all(r["cap"] > 0 for r in rows), "no zero cap")
    ok(sum(1 for r in rows if r["kind"] == "name") == full["name_cells"] == 17, "17 name cells")
    ok(sum(1 for r in rows if r["gold"] == NONE_GOLD) == 6, "six NONE controls planned")
    ok(all(r["j"] <= r["level"] + 1 for r in rows), "no cell asks past the off-end probe")
    groups: dict = {}
    for r in rows:
        groups.setdefault(r["prompt_sha256"], []).append(r["label"])
    redispatch = {"L48_j40", "L48_j40_dup", "L64_j40", "L64_j40_dup", "L64_j32", "L64_j32_c256"}
    shared_groups = {tuple(sorted(v)) for v in groups.values() if len(v) > 1}
    ok(all(set(g) <= redispatch for g in shared_groups),
       f"an unintended pair of cells shares a prompt: {shared_groups}")
    ok(len(groups) == len(rows) - 3, f"expected exactly three shared prompts: {len(groups)}")
    ok(sorted(full["tier_line"] for _ in [0]) == [14], "tier line frozen at 14")
    ok(all(c["kind"] in ("name", "off_end", "dead_end", "dup", "rung") for c in full["cells"]),
       "every planned cell has a registered kind")
    ok(all(c["own_terminal"] for c in full["cells"] if c["kind"] == "name"),
       "every name cell asks within a path that reaches a terminal")
    ok(sum(1 for c in full["cells"] if c["dead_end_is_query_tail"]) == 1,
       "the level-32 dead-end control uses the other path tail and the level-64 one uses the "
       "query path's own tail: both are out-degree zero, so both are gold NONE")

    # 17. planted record sets against the tier and the flags, on the real plan
    planted = []
    for r in rows:
        is_none_control = r["gold"] == NONE_GOLD
        declared = NONE_GOLD if is_none_control else r["gold"]
        # name cells get a cost that grows with j so the planted grid has a known monotone shape;
        # every planted value stays under that cell's own cap
        if r["kind"] in ("name", "dup"):
            planted_tokens = 200 + 20 * r["j"]
        else:
            planted_tokens = min(500, r["cap"])
        planted.append({"label": r["label"], "kind": r["kind"], "level": r["level"], "j": r["j"],
                        "n_facts": r["n_facts"], "gold": r["gold"], "cap": r["cap"],
                        "delivered": True, "declared": declared, "correct": True,
                        "completion_tokens": planted_tokens, "finish_reason": "stop",
                        "trace_chars": 400, "trace_last_name": declared,
                        "gold_in_trace": True, "pseudo_in_trace": True,
                        "gold_is_last_trace_name": True, "pseudo_is_last_trace_name": False,
                        "gold_offset": 10, "pseudo_offset": 20,
                        "census": {"fields": ["content", "reasoning_content", "role"],
                                   "reasoning_field": "reasoning_content"}})
    res = score_records(planted, full)
    ok(res["tier"] in {s["id"] for s in LAW_SPECS} or res["tier"] in
       ("laws_not_separable", "no_wall_law"), f"all-delivered grid reads a law tier: {res['tier']}")
    ok(res["criteria"]["C2_none_controls_honest"]["pass"], "planted controls delivered honestly")
    ok(res["criteria"]["C4_accuracy_vs_delivery"]["pass"], "all-delivered grid is not a turnover")
    ok(res["criteria"]["C9_monotone_quantity"]["rho"]["j"] == 1.0, "planted monotone token cost in j")
    planted_const = [dict(r) for r in planted]
    for r in planted_const:
        if r["kind"] in ("name", "dup"):
            r["completion_tokens"] = 500
    res_const = score_records(planted_const, full)
    ok(res_const["criteria"]["C9_monotone_quantity"]["rho"]["j"] is None
       and not res_const["criteria"]["C9_monotone_quantity"]["pass"],
       "a constant token cost has no rank correlation and must not pass C9")

    # 17b. planted NONE-control classes: a censored control must not invalidate, a false name must
    planted_b = [dict(r) for r in planted]
    for r in planted_b:
        if r["gold"] == NONE_GOLD:
            r["delivered"] = False
            r["declared"] = None
            r["correct"] = None
            r["finish_reason"] = "length"
            r["completion_tokens"] = r["cap"]
    res_b = score_records(planted_b, full)
    ok(res_b["criteria"]["C2_none_controls_honest"]["censored_not_scored"] == 6,
       "censored controls reported, not scored")
    ok(res_b["tier"] == "controls_invalid",
       f"zero delivered controls must invalidate the tier: {res_b['tier']}")
    planted_c = [dict(r) for r in planted]
    planted_c[0]["declared"] = "quixg"
    planted_c[0]["correct"] = False
    res_c = score_records(planted_c, full)
    ok(res_c["criteria"]["C2_none_controls_honest"]["false_names"] == ["L32A_deadend"],
       "planted false name on a delivered control is named")
    ok(res_c["tier"] == "controls_invalid", "a false name on a control invalidates the tier")

    # 17c. planted accuracy turnover: a wrong name on a delivered name cell, and a non-capping
    #      non-delivery, both read accuracy_turnover rather than a wall law
    planted_d = [dict(r) for r in planted]
    planted_d[6]["declared"] = "notthegold"
    planted_d[6]["correct"] = False
    planted_d[6]["gold"] = "somethingelse"
    res_d = score_records(planted_d, full)
    ok(res_d["tier"] == "accuracy_turnover", "a wrong terminal on a name cell is a turnover")
    planted_e = [dict(r) for r in planted]
    for r in planted_e:
        if r["kind"] == "name":
            r["delivered"] = False
            r["declared"] = None
            r["correct"] = None
            r["finish_reason"] = "content_filter"
            r["completion_tokens"] = 7
    res_e = score_records(planted_e, full)
    ok(res_e["tier"] == "accuracy_turnover", "a non-capping non-delivery is a turnover")
    ok(res_e["criteria"]["C4_accuracy_vs_delivery"]["not_cap_bound"],
       "the non-capping non-deliveries are named")

    # 17d. planted delivery split: deep cells censored, shallow delivered
    planted_f = [dict(r) for r in planted]
    for r in planted_f:
        if r["kind"] == "name" and r["j"] >= DELIVERY_DEEP_J:
            r["delivered"] = False
            r["declared"] = None
            r["correct"] = None
            r["finish_reason"] = "length"
            r["completion_tokens"] = r["cap"]
    res_f = score_records(planted_f, full)
    ok(res_f["criteria"]["C4_accuracy_vs_delivery"]["delivery_split"]["delivery_bound"],
       "planted deep censoring reads a delivery-bound loss")
    ok(res_f["tier"] in {s["id"] for s in LAW_SPECS} or res_f["tier"] in
       ("laws_not_separable", "no_wall_law"), "planted shape still reads a law tier")

    # 17e. planted self-agreement split
    planted_g = [dict(r) for r in planted]
    for r in planted_g:
        if r["label"] == "L48_j40_dup":
            r["completion_tokens"] = 501
    res_g = score_records(planted_g, full)
    ok("self_agreement_split" in res_g["flags"], "planted token split flags")

    # 17f. planted trace provenance: the containment trap must refuse and the order readout must pass
    planted_h = [dict(r) for r in planted]
    for r in planted_h:
        if r["kind"] == "name":
            r["delivered"] = False
            r["declared"] = None
            r["correct"] = None
            r["finish_reason"] = "length"
            r["completion_tokens"] = r["cap"]
            r["gold_is_last_trace_name"] = True
            r["pseudo_is_last_trace_name"] = False
    res_h = score_records(planted_h, full)
    ok(res_h["criteria"]["C7_trace_provenance_lastmention"]["admissible"],
       "gold-last on every undelivered record must admit the readout")
    ok(res_h["criteria"]["C7_trace_provenance_lastmention"]["containment_legacy"]["gap"] == 0.0,
       "the archived containment gap on the same records is 0.0, which is why it is not the row")
    planted_i = [dict(r) for r in planted_h]
    for r in planted_i:
        r["gold_is_last_trace_name"] = False
        r["pseudo_is_last_trace_name"] = True
    res_i = score_records(planted_i, full)
    ok(not res_i["criteria"]["C7_trace_provenance_lastmention"]["admissible"],
       "the enumerated-tails shape must refuse the order readout")
    ok("trace_provenance_refused" in res_i["flags"], "refusal flags")
    planted_j = [dict(r) for r in planted_h]
    for r in planted_j:
        r["gold_is_last_trace_name"] = None
        r["pseudo_is_last_trace_name"] = None
    res_j = score_records(planted_j, full)
    ok(not res_j["criteria"]["C7_trace_provenance_lastmention"]["admissible"],
       "no entity mentioned in the trace cannot support the claim")

    # 17g. planted incomplete dispatch must outrank everything
    res_k = score_records([r for r in planted if r["label"] != "L48_j40"], full)
    ok(res_k["tier"] == "dispatch_incomplete", "a cut grid is never a verdict")
    ok(res_k["not_dispatched"] == ["L48_j40"], "the cut cell is named")

    # 18. the issue #137 guard, planted negatives included
    gate_file = json.loads(json.dumps(full))
    recs = [{"label": r["label"], "gate": gate_blob(gate_file)} for r in rows]
    good_readme = ("Question\n\nblob:\n\n" + gate_blob(gate_file) + "\n\n"
                   "Rows C1, C2, C3, C4, C5, C6, C7, C8, C9, H0, H1 and X1 fired.\n")
    chk = check_readme_rows(good_readme, gate_file, recs)
    ok(chk["ok"], "clean README must pass the row guard: " + json.dumps(chk["problems"]))
    ok(chk["rows_named"] == sorted(["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "H0",
                                    "H1", "X1"]),
       f"the guard must read exactly the quoted row ids: {chk['rows_named']}")
    noise = (good_readme + "\nLabels like L48_j40, coordinates like k = 32 and j = 40, PR #136, "
             "sha256 and IQ3 must not read as row ids.\n")
    chk_noise = check_readme_rows(noise, gate_file, recs)
    ok(chk_noise["ok"] and chk_noise["rows_named"] == chk["rows_named"],
       f"cell labels and coordinates must not read as row ids: {chk_noise['problems']}")
    shorthand = good_readme + "\nItem shorthand L16, L32A, L48 and L64 names cells of this gate.\n"
    ok(check_readme_rows(shorthand, gate_file, recs)["ok"],
       "an item shorthand that prefixes a cell label of this gate is defined")
    fake_item = good_readme + "\nItem shorthand L99 names nothing in this gate.\n"
    chk_fake_item = check_readme_rows(fake_item, gate_file, recs)
    ok(not chk_fake_item["ok"] and any(p["kind"] == "row_id_not_in_gate" and "L99" in p["ids"]
                                       for p in chk_fake_item["problems"]),
       "an item shorthand that matches no cell of this gate must fail the guard")
    bad1 = good_readme.replace("Rows C1", "Rows R2 seed pairing and C1")
    chk1 = check_readme_rows(bad1, gate_file, recs)
    ok(not chk1["ok"] and chk1["problems"][0]["ids"] == ["R2"],
       "the archived R2 template residue must fail the guard")
    near = gate_blob(gate_file)[:63] + ("0" if gate_blob(gate_file)[63] != "1" else "1")
    bad2 = good_readme.replace(gate_blob(gate_file), near)
    chk2 = check_readme_rows(bad2, gate_file, recs)
    ok(not chk2["ok"] and any(p["kind"] == "readme_blob_stale_or_missing" for p in chk2["problems"]),
       "a blob pin differing by one hex char must fail")
    stale_recs = [dict(r) for r in recs]
    stale_recs[4]["gate"] = "f" * 64
    chk3 = check_readme_rows(good_readme, gate_file, stale_recs)
    ok(not chk3["ok"] and any(p["kind"] == "raw_record_stale_blob" for p in chk3["problems"]),
       "a raw record carrying a stale blob must fail")
    chk4 = check_readme_rows(good_readme + "\n" + "c" * 64 + "\n", gate_file, recs)
    ok(not chk4["ok"] and any(p["kind"] == "uncertified_blob_cited_in_readme"
                             for p in chk4["problems"]),
       "a cited blob that is not this gate's or a certified archive's must fail")
    chk5 = check_readme_rows(good_readme, gate_file, recs + [{"label": "ghost", "gate": ""}])
    ok(not chk5["ok"] and any(p["kind"] == "raw_label_not_in_gate" for p in chk5["problems"]),
       "a raw label the gate does not define must fail")
    ok(check_readme_rows(good_readme, gate_file, recs, {R55_BLOB})["ok"],
       "the certified archived blob is allowed in the README")
    ok(gate_blob(gate_file) == gate_blob(json.loads(json.dumps(gate_file))),
       "gate blob recomputes byte-identically through json")
    ok(gate_blob(dict(gate_file, blob="f" * 64)) == gate_blob(gate_file),
       "the blob is the gate with its own blob field removed")

    print(f"selftest ok: {checks} checks")


# ------------------------------------------------------------------ commands

def freeze_gate(path: str) -> dict:
    spec = gate_spec()
    spec["blob"] = gate_blob(spec)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return spec


def do_calibrate(outdir: str) -> int:
    item = item_for(CALIBRATION["level"], CALIBRATION["index"])
    check_item(item)
    src = item["query"][0]
    prompt = render_name(item, src, CALIBRATION["j"])
    gold = terminal_at(item, src, CALIBRATION["j"])
    resp = call(prompt, CALIBRATION["cap"])
    content = sanitize(resp["message"].get("content"), 2000)
    declared, delivered = declared_answer(content, vocab_of(item))
    trace, fields, reasoning_field = trace_of(resp["message"])
    out = {"note": "one format call on a level-8 load-floor item outside the grid, to confirm the "
                   "registered response format parses on this build before any dispatch; it is not "
                   "experimental data and is not in raw.jsonl",
           "label": "calibrate", "level": CALIBRATION["level"], "j": CALIBRATION["j"],
           "cap": CALIBRATION["cap"], "gold": gold, "content": content, "declared": declared,
           "delivered": delivered, "correct": declared == gold,
           "census": {"fields": fields, "reasoning_field": reasoning_field},
           "trace_chars": len(sanitize(trace)), "finish_reason": resp["finish_reason"],
           "completion_tokens": resp["completion_tokens"], "prompt_tokens": resp["prompt_tokens"],
           "prompt_sha256": prompt_digest(prompt), "model_digest": model_digest(),
           "wall_s": resp["wall_s"]}
    with open(os.path.join(outdir, "calibration.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"calibrate: declared {declared} gold {gold} correct {out['correct']} "
          f"tokens {resp['completion_tokens']} finish {resp['finish_reason']}")
    return 0


def do_run(outdir: str) -> int:
    global _GATE_BLOB
    spec = freeze_gate(os.path.join(outdir, "gate.json"))
    _GATE_BLOB = spec["blob"]
    print("gate blob", spec["blob"], "cells", len(spec["cells"]))
    rows = plan_prompts()
    raw_path = os.path.join(outdir, "raw.jsonl")
    done = {}
    if os.path.exists(raw_path):
        done = {r["label"]: r for r in read_jsonl(raw_path) if r.get("gate") == _GATE_BLOB}
    records = list(done.values())
    fh = open(raw_path, "a", encoding="utf-8")
    retries = 0
    t_start = time.time()
    not_dispatched = []
    health = call(CENSUS_PROMPT, spec["health"]["cap"])
    trace, fields, reasoning_field = trace_of(health["message"])
    with open(os.path.join(outdir, "health.json"), "w", encoding="utf-8") as hj:
        json.dump({"id": spec["health"]["id"], "fields": fields,
                   "reasoning_field": reasoning_field, "trace_chars": len(sanitize(trace)),
                   "finish_reason": health["finish_reason"],
                   "completion_tokens": health["completion_tokens"],
                   "prompt_sha256": spec["health"]["prompt_sha256"],
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
              f"finish={rec['finish_reason']} declared={rec['declared']} correct={rec['correct']} "
              f"trace={rec['trace_chars']} last={rec['trace_last_name']}")
    fh.close()
    records = [r for r in read_jsonl(raw_path) if r.get("gate") == _GATE_BLOB]
    scored = score_records(records, spec)
    scored["dispatch"] = {"wall_s": round(time.time() - t_start, 3), "planned": len(rows),
                          "dispatched": len(rows) - len(not_dispatched),
                          "not_dispatched": not_dispatched, "retries_used": retries,
                          "call_cap": CALL_CAP, "calibration_calls": 1,
                          "prompt_tokens": sum(r.get("prompt_tokens") or 0 for r in records),
                          "completion_tokens": sum(r.get("completion_tokens") or 0 for r in records)}
    scored["gate_blob"] = _GATE_BLOB
    with open(os.path.join(outdir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(scored, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print("tier", scored["tier"], "flags", scored["flags"])
    return 0


def do_rescore(outdir: str) -> int:
    global _GATE_BLOB
    spec = json.load(open(os.path.join(outdir, "gate.json"), encoding="utf-8"))
    _GATE_BLOB = gate_blob(spec)
    records = read_jsonl(os.path.join(outdir, "raw.jsonl"))
    scored = score_records(records, spec)
    scored["gate_blob"] = _GATE_BLOB
    # The dispatch record is rebuilt from the immutable gate and raw artifacts, and the two numbers
    # that only the firing process knows (the phase wall clock and the retry count) are carried
    # forward from whatever summary.json is already there. Idempotent from the second call on.
    prev_path = os.path.join(outdir, "summary.json")
    prev = json.load(open(prev_path, encoding="utf-8")) if os.path.exists(prev_path) else {}
    labels_gate = {c["label"] for c in spec["cells"]}
    labels_raw = {r.get("label") for r in records}
    dispatch = dict(prev.get("dispatch") or {})
    dispatch.update({
        "planned": len(spec["cells"]), "dispatched": len(labels_gate & labels_raw),
        "not_dispatched": sorted(labels_gate - labels_raw),
        "call_cap": spec["dispatch"]["call_cap"], "calibration_calls": 1,
        "prompt_tokens": sum(r.get("prompt_tokens") or 0 for r in records),
        "completion_tokens": sum(r.get("completion_tokens") or 0 for r in records),
        "call_wall_s_sum": round(sum(r.get("wall_s") or 0.0 for r in records), 3),
        "dispatch_source": "carried_from_run" if prev.get("dispatch") else "reconstructed_from_raw",
    })
    scored["dispatch"] = dispatch
    with open(os.path.join(outdir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(scored, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print("tier", scored["tier"], "flags", scored["flags"])
    print(json.dumps(scored["criteria"], indent=2, sort_keys=True))
    return 0


def do_check_readme(outdir: str) -> int:
    gate = json.load(open(os.path.join(outdir, "gate.json"), encoding="utf-8"))
    readme_path = os.path.join(outdir, "README.md")
    if not os.path.exists(readme_path):
        print("no README.md yet in", outdir)
        return 1
    readme = open(readme_path, encoding="utf-8").read()
    records = read_jsonl(os.path.join(outdir, "raw.jsonl"))
    chk = check_readme_rows(readme, gate, records, {R55_BLOB})
    print(json.dumps(chk, indent=2, sort_keys=True))
    return 0 if chk["ok"] else 1


def main(argv: list) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--rescore", action="store_true")
    ap.add_argument("--check-readme", action="store_true")
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
                  f"j={row['j']:<3d} cap={row['cap']:<5d} kind={row['kind']:<8s} "
                  f"gold={row['gold']:10s} facts={row['n_facts']:<4d} "
                  f"digest={row['prompt_sha256'][:16]}")
        print("planned calls", len(plan_prompts()), "of cap", CALL_CAP)
        print("certification", json.dumps(spec["certification"], sort_keys=True)[:400])
        print("gate blob (dry, not frozen)", gate_blob(spec))
        return 0
    if args.calibrate:
        return do_calibrate(args.outdir)
    if args.run:
        return do_run(args.outdir)
    if args.rescore:
        return do_rescore(args.outdir)
    if args.check_readme:
        return do_check_readme(args.outdir)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

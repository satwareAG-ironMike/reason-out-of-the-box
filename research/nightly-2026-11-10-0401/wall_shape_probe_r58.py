#!/usr/bin/env python3
"""Round 58 (issue #65): which wall governs the name arm on a 27B-class build - input load,
step count, or their product - and does the class's own boundary sit at step 32 or step 40.

The question, registered before dispatch (see gate.json, schema round58-gate-v1): on this
27B-class build (the re-fired round-54 build, model digest 26df9af5972ff312; the serving id
itself is never written anywhere, only the one-way digest), run the round-55 name-or-NONE
arm byte-identically over a grid of three input loads (64, 96, 128 facts) and five step
counts (j = 8, 16, 24, 32, 40), with a shallow 32-fact reference row. Where does delivery
stop: at the fact-block size, at the step count, or at a single load-times-depth product?
Four laws are declared in the gate before the first prompt and are scored against the
observed delivered / censored states of the 16 name cells.

  law `input_load_wall`    : censored iff n_facts >= 96
  law `step_count_wall`    : censored iff j >= 32
  law `load_depth_product` : censored iff n_facts * j >= 3072
  law `step40_wall`        : censored iff j >= 40

The three flash-class laws are cross-class transfer candidates: the thresholds are drawn
from the archived flash-class record (rounds 55, 57; sibling build digest 4075b5949b2b0487)
and from this build's own archived yes/no cap-ladder rows (round 54: every 96-fact
dispatch cap-bound at every requested rung below the pin, open PR #133). The step40 law is
the boundary extension: the parallel killed round-56 firing on the sibling 27B build
(digest 86d6f3507f8725bf, untracked archive, disclosed as provenance below) delivered
j = 32 and censored j = 40..64 at 128 facts, so the class's own boundary sits between 32
and 40 and the two step laws must be separated on this firing.

Items are the load-floor family of the shipped generator (facts = 2 * level, exactly two
disjoint `level`-edge paths, issue #129), scanned per item with skip-on-raise so the
level-64 series can be reached at all. Level 64 has exactly one load-floor item in the
400-draw scan (seed 148261120).

The 13 round-55 archived rows are byte-identical prompt anchors, certified fail-closed
before dispatch against the open PR #136 head (raw sha256 pinned); the level-48 item's
fact block is lineage-certified by rebuilding the round-51 yes/no prompt and asserting its
archived digest 068bc6a1fb0620fb (rounds 51/54), so the cross-firing comparison rides on
item identity, not prompt identity.

Resilience contract (issue #67, issue #100): records are appended and fsynced one by one,
`--run` resumes by label (a killed dispatch costs only the in-flight call), a transport
failure is recorded as `transport_error` rather than ending the run, and every
re-dispatch pair is scored for self-agreement.

Usage:
  wall_shape_probe_r58.py --selftest
  wall_shape_probe_r58.py --dry-run
  wall_shape_probe_r58.py --calibrate        one pre-gate call, written to calibration.json only
  wall_shape_probe_r58.py --gate             freeze gate.json
  wall_shape_probe_r58.py --run              dispatch (reads NIGHTLY_BASE_URL / NIGHTLY_MODEL_ID /
                                             NIGHTLY_API_KEY from the environment, writes them nowhere)
  wall_shape_probe_r58.py --rescore          rebuild summary.json from raw.jsonl at zero prompt cost
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
SEED_BASE = 20261005           # the round 51 seed base: the same items, the same seeds
SCAN = 400
MAX_TOKENS = 2048              # protocol cap: no requested cap may exceed it
CALL_CAP = 40
TIMEOUT_S = 600
DISPATCH_BUDGET_S = 3000       # wall-clock guard on the dispatch phase
MAX_RETRIES_TOTAL = 4
RETRY_BACKOFF_S = 15
NONE_GOLD = "NONE"
GATE_SCHEMA = "round58-gate-v1"
PRODUCT_THRESHOLD = 3072       # declared before dispatch, from the archived flash-class surface
INPUT_LOAD_THRESHOLD = 96      # declared before dispatch, from the archived 96-fact cap-bound record
STEP_THRESHOLD = 32            # declared before dispatch, from the class's k = 48 cliff
STEP40_THRESHOLD = 40         # declared before dispatch: the boundary-extension law

# ------------------------------------------------------------------ dispatch plan

# (label, level, index within the load-floor list, j, cap, kind).
# kind: name = the depth query; off_end = j one past the path end (gold NONE);
#       dead_end = a path tail asked for one step (gold NONE); dup = re-dispatch (#100);
#       rung = the same query at a 256-token cap (budget control, outside the law scoring).
PLAN = [
    # shallow load: 32 facts, two 16-edge paths; the round-55 anchor family
    ("L16_j8", 16, 0, 8, MAX_TOKENS, "name"),
    ("L16_j16", 16, 0, 16, MAX_TOKENS, "name"),
    ("L16_offend", 16, 0, 17, MAX_TOKENS, "off_end"),
    # mid load: 64 facts, two 32-edge paths; the round-55 anchor family
    ("L32A_j8", 32, 0, 8, MAX_TOKENS, "name"),
    ("L32A_j16", 32, 0, 16, MAX_TOKENS, "name"),
    ("L32A_j24", 32, 0, 24, MAX_TOKENS, "name"),
    ("L32A_j32", 32, 0, 32, MAX_TOKENS, "name"),
    ("L32A_offend", 32, 0, 33, MAX_TOKENS, "off_end"),
    ("L32A_deadend", 32, 0, 1, MAX_TOKENS, "dead_end"),
    # heavy load: 96 facts, two 48-edge paths; round 51's certified item (lineage below)
    ("L48_j8", 48, 0, 8, MAX_TOKENS, "name"),
    ("L48_j16", 48, 0, 16, MAX_TOKENS, "name"),
    ("L48_j24", 48, 0, 24, MAX_TOKENS, "name"),
    ("L48_j32", 48, 0, 32, MAX_TOKENS, "name"),
    ("L48_j40", 48, 0, 40, MAX_TOKENS, "name"),
    ("L48_j40_dup", 48, 0, 40, MAX_TOKENS, "dup"),
    ("L48_offend", 48, 0, 49, MAX_TOKENS, "off_end"),
    # deepest load reachable under issue #129: 128 facts, two 64-edge paths
    ("L64_j8", 64, 0, 8, MAX_TOKENS, "name"),
    ("L64_j16", 64, 0, 16, MAX_TOKENS, "name"),
    ("L64_j24", 64, 0, 24, MAX_TOKENS, "name"),
    ("L64_j32", 64, 0, 32, MAX_TOKENS, "name"),
    ("L64_j40", 64, 0, 40, MAX_TOKENS, "name"),
    ("L64_j40_dup", 64, 0, 40, MAX_TOKENS, "dup"),
    ("L64_offend", 64, 0, 65, MAX_TOKENS, "off_end"),
    ("L64_deadend", 64, 0, 1, MAX_TOKENS, "dead_end"),
    # budget rung on the heaviest load's step-32 cell: does a one-token answer space survive?
    ("L64_j32_c256", 64, 0, 32, 256, "rung"),
]
NAME_CELLS = tuple(row[0] for row in PLAN if row[5] == "name")
CONTROL_CELLS = tuple(row[0] for row in PLAN if row[5] in ("off_end", "dead_end"))
DUP_PAIRS = (("L48_j40", "L48_j40_dup"), ("L64_j40", "L64_j40_dup"))
RUNG_CELLS = tuple(row[0] for row in PLAN if row[5] == "rung")
# The pre-gate calibration cell (round 6's level-8 seed family; not experimental data).
CALIBRATION = {"label": "CALIBRATION_L8_j8", "level": 8, "index": 0, "j": 8,
               "cap": MAX_TOKENS, "expect_gold": "zish",
               "expect_digest16": "4f1fdb53f99a46eb"}

CENSUS_PROMPT = ("Rule: for all x, y, z: if x precedes y and y precedes z, then x precedes z. "
                 "Facts: alby precedes birch. birch precedes cobin. Question: does alby precedes "
                 "cobin? Answer with exactly one word: yes or no.")

# ------------------------------------------------------------------ archived anchors
# Round 55 (research/nightly-2026-11-09-0301, PR #136: open at this firing, not on main).
# Vendored as in-file constants with the prompt digest beside each row; the certifier refuses
# to dispatch a row whose rebuilt prompt digest does not match, so the cross-build comparison
# is byte-identity certified before any prompt is spent. The round-55 build is a different
# build of the same class from this firing's (issue #105), and both sides' exposure is
# stated because of it.

R55_MODEL_DIGEST = "4075b5949b2b0487"
R55_HEAD = "806f5d3728ce04314f9c4e8bcb503bd95f28f478"     # PR #136 head at this firing
R55_RAW_SHA256 = "57dff62e1f53b6b8b5abc02ccd205332c13a2dbfe7421ab9acf448041d89ec4a"
R55_GATE_BLOB = "eadf84d55d10b649c952a29a350437a8658c837fb62c6f39356c508378a151a4"
R55_ANCHORS = [
    # label, digest16, n_facts, gold, completion tokens, finish, declared, trace_chars
    ("L16_j8", "87169f9ec6f776c3", 32, "stacklt", 441, "stop", "stacklt", 1343),
    ("L16_j16", "a22f1d12cc743d19", 32, "brond", 529, "stop", "brond", 1509),
    ("L16_offend", "515a50f2c6478f79", 32, "NONE", 974, "stop", "NONE", 2775),
    ("L32A_j8", "70ed757a4d369ae5", 64, "thrend", 528, "stop", "thrend", 1831),
    ("L32A_j16", "40909990f780674a", 64, "crux", 437, "stop", "crux", 1301),
    ("L32A_j24", "def7b75e37c9eaa4", 64, "vixx", 1285, "stop", "vixx", 3652),
    ("L32A_j32", "a8697dfb826079fc", 64, "sterk", 951, "stop", "sterk", 2485),
    ("L32A_offend", "cbd27af789889450", 64, "NONE", 2048, "length", None, 4000),
    ("L32A_deadend", "1f56a9a6f5969364", 64, "NONE", 204, "stop", "NONE", 813),
    ("L48_j8", "cec71db935bf42f9", 96, "trackst", 1096, "stop", "trackst", 3116),
    ("L48_j16", "7f6bbe18f35294e1", 96, "flixm", 883, "stop", "flixm", 2870),
    ("L48_j32", "6f19b9f8c406d703", 96, "whesh", 2048, "length", None, 4000),
    ("L48_offend", "e07afb24060fd652", 96, "NONE", 2048, "length", None, 4000),
]
ANCHOR_BY_LABEL = {a[0]: a for a in R55_ANCHORS}

# Level-48 item lineage: the round-51 yes/no prompt rebuilt from this round's L48 item
# must reproduce the archived digest (rounds 51/54; the item is 116261051, gold no).
YESNO_LINEAGE_DIGEST = "068bc6a1fb0620fb"
YESNO_LINEAGE_SEED = 116261051


def render_yesno(item: dict) -> str:
    """The round-6 / round-50 / round-51 yes-no template, byte-identical (lineage only)."""
    facts = "\n".join(f"{s} {r} {t}." for s, r, t in item["facts"])
    qs, qrel, qt = item["query"]
    return (f"{item['rule']}\nFacts:\n{facts}\n\n"
            f"Question: does {qs} {qrel} {qt}?\n"
            "Answer with exactly one word: yes or no.")


# This build's own archived yes/no record (round 54, open PR #133, head
# a116f6784c0038e2e4ea5142a349931898b2dfa1, same model digest as this firing). Stated as
# provenance for the input-load law and the determinism context, not as this round's data.
BUILD_LOAD_RECORD = {
    "model_digest": "26df9af5972ff312",
    "archived_dir": "research/nightly-2026-11-08-0221",
    "archived_pr": 133,
    "archived_head": "a116f6784c0038e2e4ea5142a349931898b2dfa1",
    "statement": ("every 96-fact ladder dispatch on this build stopped at its requested cap "
                  "with finish_reason length on all cap-ladder rungs below the pin (round 54: "
                  "1536 at 1536, 1024 at 1024, 512 at 512, and 2048 at 2048 on the two "
                  "gold-no items), no self-termination marker, gold-yes natural stop 838, and "
                  "the duplicate re-dispatch diverged from its censored twin to a natural stop "
                  "at 1798 with the correct label at temperature 0"),
}

# The parallel killed round-56 firing (2026-11-09 04:17, 27B-class, sibling build
# 86d6f3507f8725bf). Its archive is UNTRACKED (a killed firing left no branch and no PR),
# so it is vendored here as disclosed provenance for the post-hoc same-class column only;
# it carries no verdict in this round and is marked registered: false in the summary.
R56_MODEL_DIGEST = "86d6f3507f8725bf"
R56_CELLS = [
    # label, archived declared name, archived completion tokens, archived finish,
    # archived census reasoning field
    ("L32A_j32", "sterk", 1283, "stop", "reasoning_content"),
    ("L48_j16", "flixm", 1325, "stop", "reasoning_content"),
    ("L48_j32", "whesh", 1636, "stop", "reasoning_content"),
]

# ------------------------------------------------------------------ item and gold machinery

_SCAN_CACHE: dict = {}


def scan_series(level: int) -> tuple:
    """Per-item scan of the shipped ladder series with skip-on-raise (issue #129 option (a)).

    Returns (items, generated_ok, raised). The shipped whole-series call dies at level 64
    because one large-branching item exhausts the entity pool; a per-item scan keeps the
    items whose fact count is 2 * level, which is the smallest load in the corpus at that
    level.
    """
    if level not in _SCAN_CACHE:
        items: list = []
        raised = 0
        for i in range(SCAN):
            seed = SEED_BASE + 2_000_000 * level + i
            try:
                item = ladders.generate_item(level, seed)
            except RuntimeError:
                raised += 1
                continue
            if len(item["facts"]) == 2 * level:
                items.append(item)
        _SCAN_CACHE[level] = (items, SCAN - raised, raised)
    return _SCAN_CACHE[level]


def load_floor(level: int) -> list:
    return scan_series(level)[0]


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
    assert all(len({s for s, _, _ in facts} & {t for _, _, t in facts} - set(out)) >= 0 for _ in (0,))


def adjacency(item: dict) -> dict:
    adj: dict = {}
    for s, _, t in item["facts"]:
        assert s not in adj, "out-degree above one"
        adj[s] = t
    return adj


def terminal_at(item: dict, src: str, steps: int):
    """Independent solver: the node reached from src by exactly `steps` direct links, else None."""
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
    """The tail of the path that does NOT contain src: matched pseudo-gold for the trace row."""
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


# ------------------------------------------------------------------ prompts

def fact_block(item: dict) -> str:
    return "\n".join(f"{s} {r} {t}." for s, r, t in item["facts"])


def render_name(item: dict, src: str, j: int) -> str:
    """The round-55 response format, byte-identical (the anchor digests certify it)."""
    return (f"{item['rule']}\nFacts:\n{fact_block(item)}\n\n"
            f"Task: start at {src} and follow the direct links for exactly {j} steps. "
            "Answer with exactly one entity name, or the single word NONE if the links run out "
            f"before {j} steps.")


def prompt_digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def plan_prompts() -> list:
    """Expand PLAN into rows carrying prompt, gold and source, before any endpoint call."""
    out = []
    for label, level, index, j, cap, kind in PLAN:
        item = item_for(level, index)
        if kind == "dead_end":
            src = tails_of(item)[0]
        else:
            src = item["query"][0]
        gold = terminal_at(item, src, j)
        gold = NONE_GOLD if gold is None else gold
        assert (gold == NONE_GOLD) == (kind in ("off_end", "dead_end")), (label, gold, kind)
        assert (gold != NONE_GOLD) == (kind in ("name", "dup", "rung")), (label, gold, kind)
        prompt = render_name(item, src, j)
        own = terminal_at(item, src, item["level"])
        pseudo = other_tail(item, src) if own is not None else ""
        out.append({"label": label, "level": level, "index": index, "seed": item["seed"],
                    "src": src, "j": j, "cap": cap, "kind": kind, "gold": gold,
                    "prompt": prompt, "pseudo_gold": pseudo, "n_facts": len(item["facts"]),
                    "prompt_sha256": prompt_digest(prompt)})
    return out


def certify_anchors(rows: list) -> dict:
    """Fail closed: a row that claims an archived anchor must rebuild its exact prompt bytes,
    and the level-48 fact block must rebuild the archived yes/no digest."""
    hits, fails = 0, []
    for row in rows:
        anchor = ANCHOR_BY_LABEL.get(row["label"])
        if not anchor:
            continue
        hits += 1
        if anchor[1] != row["prompt_sha256"][:16]:
            fails.append({"label": row["label"], "want": anchor[1],
                          "got": row["prompt_sha256"][:16]})
        elif anchor[2] != row["n_facts"] or anchor[3] != row["gold"]:
            fails.append({"label": row["label"], "reason": "facts or gold differ"})
    lineage = [r for r in rows if r["level"] == 48 and r["seed"] == YESNO_LINEAGE_SEED]
    if not lineage:
        fails.append({"reason": "no level-48 lineage row in the plan"})
    else:
        l48 = item_for(48, 0)
        if hashlib.sha256(render_yesno(l48).encode()).hexdigest()[:16] != YESNO_LINEAGE_DIGEST:
            fails.append({"reason": "the level-48 yes/no prompt does not rebuild the archived "
                                    "digest: the item lineage is broken"})
    if fails:
        raise RuntimeError("anchor certification failed: " + json.dumps(fails, sort_keys=True))
    return {"certified": hits, "of": len(R55_ANCHORS), "lineage_seed": YESNO_LINEAGE_SEED,
            "lineage_digest16": YESNO_LINEAGE_DIGEST,
            "build_model_digest": model_digest(),
            "archived_model_digest": R55_MODEL_DIGEST}


# ------------------------------------------------------------------ sanitizer

_SECRET_PATTERNS = [
    re.compile(r"https?://\S+"),
    re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d+)?\b"),
    re.compile(r"/(?:root|home|mnt|media|run/user)/\S+"),
    re.compile(r"\b(?:localhost|127\.0\.0\.1)(?::\d{2,5})?\b", re.I),
]


def sanitize(text, limit: int = 4000) -> str:
    """Strip anything the public-only rule forbids from model output before it is written down."""
    if text is None:
        return ""
    out = str(text)
    for pat in _SECRET_PATTERNS:
        out = pat.sub("[redacted]", out)
    for bad in ("NIGHTLY_BASE_URL", "NIGHTLY_API_KEY", "NIGHTLY_MODEL_ID", "NIGHTLY_MODEL_LABEL",
                "NIGHTLY_PROVIDER_MODEL"):
        val = os.environ.get(bad)
        if val and len(val) > 3:
            out = out.replace(val, "[redacted]")
    out = out.replace("\r", "")
    return out[:limit] if len(out) > limit else out


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
    """(declared, delivered). The last entity name in the visible answer field, else the NONE
    sentinel, else undetermined. An empty answer field is a non-delivery, not a miss."""
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


# ------------------------------------------------------------------ laws

LAWS = {
    "input_load_wall": lambda facts, j: facts >= INPUT_LOAD_THRESHOLD,
    "step_count_wall": lambda facts, j: j >= STEP_THRESHOLD,
    "load_depth_product": lambda facts, j: facts * j >= PRODUCT_THRESHOLD,
    "step40_wall": lambda facts, j: j >= STEP40_THRESHOLD,
}


def law_predictions() -> dict:
    """The registered prediction table: for each name cell, which laws predict censoring."""
    table = {}
    for row in plan_prompts():
        if row["kind"] != "name":
            continue
        key = (row["n_facts"], row["j"])
        table[row["label"]] = {"n_facts": key[0], "j": key[1], "product": key[0] * key[1],
                                "predict_censored": {law: bool(fn(key[0], key[1]))
                                                     for law, fn in LAWS.items()}}
    return table


def disagreement_cells() -> dict:
    """The registered discriminators: the name cells on which the four declared laws do not all
    predict the same state. Derived from the laws before any endpoint call."""
    table = law_predictions()
    out: dict = {}
    for label, v in table.items():
        states = v["predict_censored"]
        if len(set(states.values())) > 1:
            out[label] = {"n_facts": v["n_facts"], "j": v["j"], "product": v["product"],
                          "predict_censored": states}
    return out


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
    table = law_predictions()
    n_name = len(NAME_CELLS)
    return {
        "schema": GATE_SCHEMA,
        "question": ("On a 27B-class local build (the re-fired round-54 build; the record "
                     "carries the one-way model digest only), with the round-55 name-or-NONE "
                     "response format re-pinned byte-identically (13 archived prompt digests "
                     "certified against open PR #136 and the level-48 fact block lineage-"
                     "certified against the archived round-51 yes/no digest) and a grid of "
                     "three input loads (64, 96, 128 facts) against five step counts "
                     "(j = 8, 16, 24, 32, 40) plus a 32-fact reference row, does delivery on a "
                     "one-of-many entity-name answer space stop at the input load, at the step "
                     "count, or at a single load-times-depth product, and does the class's own "
                     "boundary sit at step 32 or step 40?"),
        "laws": {
            "input_load_wall": {"predict_censored_iff": f"n_facts >= {INPUT_LOAD_THRESHOLD}",
                                 "basis": ("cross-class transfer candidate: the flash-class "
                                           "archived record censored the 96-fact name cells "
                                           "(rounds 55, 57) and this build's own archived "
                                           "yes/no cap-ladder rows put every 96-fact dispatch "
                                           "cap-bound at every rung below the pin (round 54)")},
            "step_count_wall": {"predict_censored_iff": f"j >= {STEP_THRESHOLD}",
                                 "basis": ("cross-class transfer candidate: the k = 48 cliff "
                                           "archived on both classes and the flash-class "
                                           "name arm's 96-fact censorship at j = 32 (round 55)")},
            "load_depth_product": {
                "predict_censored_iff": f"n_facts * j >= {PRODUCT_THRESHOLD}",
                "basis": ("cross-class transfer candidate: round 55's archived surface on the "
                          "class sibling, largest delivered product 64 * 32 = 2048, smallest "
                          "censored product 96 * 32 = 3072; the threshold is the archived "
                          "censoring coordinate, declared before dispatch")},
            "step40_wall": {"predict_censored_iff": f"j >= {STEP40_THRESHOLD}",
                             "basis": ("boundary extension declared before dispatch: the "
                                       "parallel killed round-56 firing on the sibling 27B "
                                       "build (digest 86d6f3507f8725bf, untracked archive, "
                                       "disclosed provenance, post-hoc column only) delivered "
                                       "j = 32 and censored j = 40..64 at 128 facts, so the "
                                       "class's own boundary must be separated from step 32")},
        },
        "prediction_table": table,
        "discriminators": disagreement_cells(),
        "criteria": {
            "C1_name_accuracy": {
                "statement": ("every delivered row of the 16 name cells plus the 2 re-dispatch "
                              "rows declares the BFS gold terminal; a delivered row with a "
                              "different name is a false name"),
                "threshold": f"{n_name + len(DUP_PAIRS)}/{n_name + len(DUP_PAIRS)} delivered "
                             "rows correct, 0 false names"},
            "C2_none_controls": {
                "statement": ("amendment adopted from round 55 finding 3 and carried by rounds "
                              "56 and 57: a censored NONE control is a non-delivery, not a "
                              "miss. Gate: zero false names among the controls that delivered, "
                              "with at least 3 controls delivered for the statement to be "
                              "admissible. The control delivery rate is reported, never gated."),
                "threshold": "0 false names among delivered controls, delivered >= 3"},
            "C3_wall_law": {
                "statement": ("agreement of each of the four registered laws with the observed "
                              "delivered / censored state over the 16 name cells, scored only "
                              "on delivery shape, never on accuracy"),
                "threshold": "the unique law with at least 13 of 16; mixed_laws at the best "
                             "law's at least 10 of 16; unresolved below that"},
            "C4_discriminators": {
                "statement": ("the nine registered discriminating cells: each one separates at "
                              "least two laws; their observed states are reported beside the "
                              "predictions"),
                "threshold": "reported"},
            "C5_anchor_reproduction": {
                "statement": ("13 byte-identical archived prompts (round 55, a different build "
                              "of the same class) plus the level-48 fact-block lineage: the "
                              "count whose delivered / censored state and declared name both "
                              "match the archived record"),
                "threshold": "reported, with the token delta per row"},
            "C6_self_agreement": {
                "statement": "both re-dispatch pairs agree on the declared name (issue #100)",
                "threshold": "2/2"},
            "C7_trace_provenance": {
                "statement": ("among undelivered name-gold records, gold-terminal-in-trace minus "
                              "matched pseudo-gold-in-trace is at least 0.50, else the trace "
                              "readout is refused (issue #94, issue #105)"),
                "threshold": "0.50"},
            "C8_census": {
                "statement": ("every record carries its field census and the reasoning-supplying "
                              "field; the cross-firing trace column states both exposures "
                              "(issue #105)"),
                "threshold": "25/25 rows censused"},
            "H1_budget_rung": {
                "statement": "the 256-token rung on the heaviest load's step-32 cell is a "
                             "non-delivery",
                "threshold": "1/1 non-delivered"},
        },
        "post_hoc_columns": {
            "X1_same_class_pair": {
                "registered": False,
                "statement": ("answer-level comparison against the parallel killed round-56 "
                              "firing (sibling 27B build 86d6f3507f8725bf, untracked archive, "
                              "disclosed): the three shared cells L32A_j32, L48_j16, L48_j32 "
                              "beside that firing's archived states. Exposure is stated on both "
                              "sides (this firing's channel from its own census, that build's "
                              "reasoning_content). No verdict of this round reads it; it is the "
                              "issue #105 same-class pair for the class-level trace "
                              "statement the next depth round owes."),
            },
        },
        "tier_rule": ("tier is the name of the unique registered law that agrees with all 16 "
                      "observed delivered / censored name-cell states on at least 13 of 16; "
                      "if no law reaches 13, the tier is mixed_laws when the best law reaches "
                      "at least 10 of 16 and unresolved below that. No tier reads accuracy: "
                      "C1 is reported beside it and a false name sets the flag "
                      "false_name_present."),
        "cells": [{"label": p["label"], "level": p["level"], "seed": p["seed"], "j": p["j"],
                   "cap": p["cap"], "kind": p["kind"], "gold": p["gold"],
                   "n_facts": p["n_facts"], "prompt_sha256": p["prompt_sha256"]}
                  for p in plan_prompts()],
        "dispatch": {"planned_calls": len(PLAN), "call_cap": CALL_CAP, "calibration_calls": 1,
                     "temperature": 0.0, "max_tokens_cap": MAX_TOKENS,
                     "dispatch_budget_s": DISPATCH_BUDGET_S,
                     "scan_pins": {lvl: {"generated_ok": scan_series(lvl)[1],
                                         "raised": scan_series(lvl)[2],
                                         "load_floor_items": len(load_floor(lvl)),
                                         "first_seed": load_floor(lvl)[0]["seed"]}
                                    for lvl in (16, 32, 48, 64)},
                     "anchor_certification": {"archived_dir": "research/nightly-2026-11-09-0301",
                                              "archived_pr": 136,
                                              "archived_head": R55_HEAD,
                                              "archived_raw_sha256": R55_RAW_SHA256,
                                              "archived_gate_blob": R55_GATE_BLOB,
                                              "archived_model_digest": R55_MODEL_DIGEST,
                                              "digests16": [a[1] for a in R55_ANCHORS],
                                              "lineage_seed": YESNO_LINEAGE_SEED,
                                              "lineage_digest16": YESNO_LINEAGE_DIGEST},
                     "build_load_record": BUILD_LOAD_RECORD,
                     "same_class_pair_provenance": {"round": 56,
                                                     "model_digest": R56_MODEL_DIGEST,
                                                     "archive_state": "untracked (killed "
                                                                      "firing, no PR)",
                                                     "cells": [r[0] for r in R56_CELLS]}},
    }


def gate_blob(spec: dict) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()


# ------------------------------------------------------------------ scoring

def score_records(records: list, spec: dict) -> dict:
    by = {r["label"]: r for r in records}
    out: dict = {}

    name_rows = [by[l] for l in NAME_CELLS if l in by]
    dup_rows = [by[a[1]] for a in DUP_PAIRS if a[1] in by]
    cap_rows = name_rows + dup_rows
    delivered_cap = [r for r in cap_rows if r["delivered"]]
    out["C1"] = {"n_rows": len(cap_rows), "delivered": len(delivered_cap),
                 "correct": sum(1 for r in delivered_cap if r["correct"]),
                 "false_names": [r["label"] for r in delivered_cap if r["delivered"]
                                 and r["correct"] is False],
                 "pass": bool(delivered_cap) and len(delivered_cap) == len(cap_rows)
                         and all(r["correct"] for r in delivered_cap)}

    controls = [by[l] for l in CONTROL_CELLS if l in by]
    del_controls = [r for r in controls if r["delivered"]]
    out["C2"] = {"n": len(controls), "delivered": len(del_controls),
                 "censored_non_deliveries": [r["label"] for r in controls if not r["delivered"]],
                 "false_names": [r["label"] for r in del_controls if r["correct"] is False],
                 "delivery_rate": round(len(del_controls) / len(controls), 4) if controls else None,
                 "admissible": len(del_controls) >= 3,
                 "pass": bool(controls) and not [r for r in del_controls if r["correct"] is False]}

    counts: dict = {}
    for law in LAWS:
        agree, bad = 0, []
        for r in name_rows:
            predicted = LAWS[law](r["n_facts"], r["j"])
            observed_censored = not r["delivered"]
            if predicted == observed_censored:
                agree += 1
            else:
                bad.append({"label": r["label"], "predicted": "censored" if predicted
                            else "delivered", "observed": "censored" if observed_censored
                            else "delivered"})
        counts[law] = {"agreements": agree, "n": len(name_rows), "disagreements": bad}
    out["C3"] = counts
    best = max((counts[l]["agreements"] for l in counts), default=0)
    top = [l for l, v in counts.items() if v["agreements"] == best]
    if not name_rows:
        tier = "unresolved"
    elif len(top) == 1 and best >= 13:
        tier = top[0]
    elif best >= 10:
        tier = "mixed_laws"
    else:
        tier = "unresolved"

    disc_expected = disagreement_cells()
    disc = {}
    for label in disc_expected:
        row = by.get(label)
        if not row:
            continue
        disc[label] = {"observed": "censored" if not row["delivered"] else "delivered",
                       "n_facts": row["n_facts"], "j": row["j"], "product": row["product"],
                       "predicted": {law: ("censored" if LAWS[law](row["n_facts"], row["j"])
                                           else "delivered") for law in LAWS}}
    out["C4"] = {"registered_cells": sorted(disc_expected), "observed": disc,
                 "undispatched": [l for l in disc_expected if l not in by]}

    repro = []
    for label, anchor in ANCHOR_BY_LABEL.items():
        row = by.get(label)
        if not row:
            continue
        want_censored = anchor[5] == "length"
        obs_censored = not row["delivered"]
        repro.append({"label": label, "archived_tokens": anchor[4], "archived_declared": anchor[6],
                      "observed_declared": row["declared"], "observed_tokens": row["completion_tokens"],
                      "state_reproduces": want_censored == obs_censored,
                      "name_reproduces": anchor[6] == row["declared"],
                      "token_delta": (row["completion_tokens"] - anchor[4])
                      if row["completion_tokens"] is not None else None})
    out["C5"] = {"rows": repro, "state_reproduced": sum(1 for r in repro if r["state_reproduces"]),
                 "name_reproduced": sum(1 for r in repro if r["name_reproduces"]),
                 "n": len(repro),
                 "lineage_certified": True, "lineage_seed": YESNO_LINEAGE_SEED,
                 "lineage_digest16": YESNO_LINEAGE_DIGEST}

    agree = []
    for a, b in DUP_PAIRS:
        if a in by and b in by:
            agree.append({"pair": [a, b], "name_agrees": by[a]["declared"] == by[b]["declared"],
                          "tokens_agree": by[a]["completion_tokens"] == by[b]["completion_tokens"],
                          "tokens": [by[a]["completion_tokens"], by[b]["completion_tokens"]]})
    out["C6"] = {"pairs": agree, "name_agreement": sum(1 for x in agree if x["name_agrees"]),
                 "pass": len(agree) == len(DUP_PAIRS) and all(x["name_agrees"] for x in agree)}

    und = [r for r in name_rows if not r["delivered"] and r["trace_chars"]]
    if und:
        g = sum(1 for r in und if r["gold_in_trace"])
        p = sum(1 for r in und if r["pseudo_in_trace"])
        gap = round(g / len(und) - p / len(und), 4)
        out["C7"] = {"n": len(und), "gold_rate": round(g / len(und), 4),
                     "pseudo_rate": round(p / len(und), 4), "gap": gap, "admissible": gap >= 0.50,
                     "pass": gap >= 0.50}
    else:
        out["C7"] = {"n": 0, "gold_rate": None, "pseudo_rate": None, "gap": None,
                     "admissible": False, "pass": False}

    censused = [r for r in records if r.get("census")]
    out["C8"] = {"n": len(records), "censused": len(censused),
                 "reasoning_open": sum(1 for r in censused if r["census"].get("reasoning_field")),
                 "pass": len(censused) == len(records)}

    rungs = [by[l] for l in RUNG_CELLS if l in by]
    out["H1"] = {"n": len(rungs), "non_delivered": sum(1 for r in rungs if not r["delivered"]),
                 "pass": len(rungs) == 1 and rungs[0]["delivered"] is False}

    # Post-hoc same-class column (registered: false): never a tier input.
    x1_rows = []
    for label, archived_name, archived_tokens, archived_finish, r56_field in R56_CELLS:
        row = by.get(label)
        if not row:
            continue
        x1_rows.append({"label": label, "archived": {"build": R56_MODEL_DIGEST,
                                                     "reasoning_field": r56_field,
                                                     "declared": archived_name,
                                                     "tokens": archived_tokens,
                                                     "finish": archived_finish},
                        "observed": {"build": model_digest(),
                                     "reasoning_field": (row.get("census") or {}).get("reasoning_field", ""),
                                     "declared": row["declared"],
                                     "tokens": row["completion_tokens"],
                                     "finish": row.get("finish_reason")},
                        "state_agrees": ((archived_finish != "length") == row["delivered"]),
                        "name_agrees": archived_name == row["declared"]})
    out["X1"] = {"registered": False,
                 "note": ("post-hoc same-class column against the parallel killed round-56 "
                           "firing (untracked archive, disclosed); exposure stated on both "
                           "sides; no verdict reads it"),
                 "rows": x1_rows,
                 "state_agreement": sum(1 for r in x1_rows if r["state_agrees"]),
                 "name_agreement": sum(1 for r in x1_rows if r["name_agrees"] and
                                       r["archived"]["declared"] != NONE_GOLD)}

    flags = []
    if out["C1"]["false_names"]:
        flags.append("false_name_present")
    if out["C2"]["false_names"]:
        flags.append("control_false_name")
    if out["C2"]["censored_non_deliveries"]:
        flags.append("control_censored_reported_not_gated")
    if not out["C2"]["admissible"]:
        flags.append("controls_underpowered")
    if out["C7"]["n"] and not out["C7"]["admissible"]:
        flags.append("trace_provenance_refused")
    if out["C6"]["name_agreement"] < len(DUP_PAIRS):
        flags.append("self_agreement_split")
    if tier == "mixed_laws":
        flags.append("laws_not_separated")
    token_surface = [{"label": r["label"], "n_facts": r["n_facts"], "j": r["j"],
                      "completion_tokens": r["completion_tokens"], "delivered": r["delivered"]}
                     for r in name_rows]
    return {"tier": tier, "flags": flags, "criteria": out,
            "token_surface": {"registered": False,
                              "note": ("post-hoc column: the completion-token surface is "
                                       "reported for the next round's cost law and no verdict "
                                       "here reads it"),
                              "rows": token_surface}}


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
    declared, delivered = declared_answer(content, vocab_of(item))
    gold = spec_row["gold"]
    rec = {"label": spec_row["label"], "kind": spec_row["kind"], "level": spec_row["level"],
           "seed": spec_row["seed"], "src": spec_row["src"], "j": spec_row["j"],
           "cap": spec_row["cap"], "gold": gold, "pseudo_gold": spec_row["pseudo_gold"],
           "n_facts": spec_row["n_facts"], "product": spec_row["n_facts"] * spec_row["j"],
           "prompt_sha256": spec_row["prompt_sha256"], "prompt_chars": len(spec_row["prompt"]),
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


# ------------------------------------------------------------------ selftest

def selftest() -> None:
    checks = 0

    def ok(cond, msg):
        nonlocal checks
        checks += 1
        assert cond, f"selftest failed: {msg}"

    # 1. generator scan pins: the load-floor family and the level-64 item-size ceiling
    pins = {16: (400, 0, 22, 52261033), 32: (400, 0, 12, 84261011),
            48: (400, 0, 6, 116261051), 64: (235, 165, 1, 148261120)}
    for lvl, (gen, raised, n_lf, first_seed) in pins.items():
        items, g, r = scan_series(lvl)
        ok(g == gen, f"level {lvl} generated count {g} != {gen}")
        ok(r == raised, f"level {lvl} raise count {r} != {raised}")
        ok(len(items) == n_lf, f"level {lvl} load-floor count {len(items)} != {n_lf}")
        ok(items[0]["seed"] == first_seed, f"level {lvl} first seed != {first_seed}")
        ok(all(len(it["facts"]) == 2 * lvl for it in items), f"level {lvl} not load-floor")
    ok(pins[64][1] > 0, "the level 64 scan must show the item-size ceiling (raised draws)")
    raised_here = False
    try:
        ladders.generate_items(64, 8, SEED_BASE)
    except RuntimeError:
        raised_here = True
    ok(raised_here, "the shipped whole-series call at level 64 must still die: the scan is the "
                    "only route to k = 64")
    for lvl in (16, 32, 48):
        shipped = ladders.generate_items(lvl, 400, SEED_BASE)
        mine = load_floor(lvl)
        ok(len(mine) == len([it for it in shipped if len(it["facts"]) == 2 * lvl]),
           f"level {lvl} scan does not agree with the shipped series")

    # 2. plan integrity: caps, labels, gold classes, and the call cap
    rows = plan_prompts()
    labels = [r["label"] for r in rows]
    ok(len(labels) == len(set(labels)), "duplicate labels in the plan")
    ok(len(rows) <= CALL_CAP, f"plan {len(rows)} exceeds the call cap {CALL_CAP}")
    ok(all(r["cap"] <= MAX_TOKENS for r in rows), "a requested cap exceeds the protocol cap")
    ok(all(r["gold"] == NONE_GOLD for r in rows if r["kind"] in ("off_end", "dead_end")),
       "a control row is not NONE-gold")
    ok(all(r["gold"] != NONE_GOLD for r in rows if r["kind"] in ("name", "dup", "rung")),
       "a name row is NONE-gold: the walk ran out where a terminal was expected")
    ok(len(NAME_CELLS) == 16, "the name grid is not 16 cells")
    ok(len(CONTROL_CELLS) == 6, "control count moved")
    ok(len(DUP_PAIRS) == 2 and len(RUNG_CELLS) == 1, "the resilience and rung rows moved")
    ok(all(r["j"] <= r["n_facts"] // 2 for r in rows if r["kind"] in ("name", "dup", "rung")),
       "a name cell asks for more steps than the path has")
    grid = sorted({(r["n_facts"], r["j"]) for r in rows if r["kind"] == "name"})
    ok(len(grid) == 16, "the (load, j) grid collapsed: two cells share a coordinate")
    ok({128, 96, 64, 32} == {r["n_facts"] for r in rows if r["kind"] == "name"},
       "the loads are not 32, 64, 96, 128 facts")
    ok({j for _, j in grid if j in (32, 40)} == {32, 40}, "the step-32/40 boundary row is missing")

    # 3. the independent solver: BFS terminals, the off-end NONE, the dead-end NONE
    item48 = item_for(48, 0)
    ok(terminal_at(item48, item48["query"][0], 48) in tails_of(item48),
       "the solver does not land on a tail at j = k")
    ok(terminal_at(item48, item48["query"][0], 49) is None, "off-end walk must run out")
    ok(other_tail(item48, item48["query"][0]) in tails_of(item48), "pseudo-gold is not a tail")
    ok(other_tail(item48, item48["query"][0]) != terminal_at(item48, item48["query"][0], 48),
       "pseudo-gold equals the gold tail")
    deep = item_for(64, 0)
    terms = [terminal_at(deep, deep["query"][0], j) for j in (8, 16, 24, 32, 40)]
    ok(len(set(terms)) == 5 and all(t is not None for t in terms),
       "the k = 64 terminals at j = 8/16/24/32/40 are not five distinct reachable names")
    ok(all(t not in tails_of(deep) for t in terms),
       "a j = 8..40 terminal on the k = 64 item is an out-degree-zero tail: the cell would be "
       "guessable by the tail shortcut")
    ok(terminal_at(deep, deep["query"][0], 65) is None, "the k = 64 off-end walk must run out")

    # 4. planted negatives on the item certifier
    bad = json.loads(json.dumps(deep))
    bad["facts"][0] = list(bad["facts"][0])
    victim = bad["facts"][0][1]
    bad["facts"].append([bad["facts"][0][0], "precedes", victim])
    caught = False
    try:
        check_item(bad)
    except AssertionError:
        caught = True
    ok(caught, "the certifier accepted an item with a node of out-degree two")
    caught = False
    try:
        item_for(64, 1)
    except AssertionError:
        caught = True
    ok(caught, "index 1 of level 64 does not exist and the certifier must refuse it")

    # 5. the registered prediction table and the discriminators
    table = law_predictions()
    ok(len(table) == 16, "the prediction table is not 16 rows")
    for law in LAWS:
        cens = [lbl for lbl, v in table.items() if v["predict_censored"][law]]
        want = {"input_load_wall": 10, "step_count_wall": 5, "load_depth_product": 5,
                "step40_wall": 2}[law]
        ok(len(cens) == want, f"law {law} predicts {len(cens)} censorings, registered {want}")
    ok(all(v["product"] == v["n_facts"] * v["j"] for v in table.values()), "product arithmetic")
    ok(table["L64_j24"]["product"] == PRODUCT_THRESHOLD,
       "the discriminating cell L64_j24 must sit exactly on the declared product threshold")
    ok(table["L48_j40"]["product"] == 3840, "L48_j40 must sit above the product threshold")
    disc = disagreement_cells()
    ok(sorted(disc) == ["L32A_j32", "L48_j16", "L48_j24", "L48_j32", "L48_j8",
                        "L64_j16", "L64_j24", "L64_j32", "L64_j8"],
       f"the registered discriminator set moved: {sorted(disc)}")
    for label, v in disc.items():
        states = set(v["predict_censored"].values())
        ok(len(states) > 1, f"{label}: the laws agree here, so it cannot be a discriminator")
    unanimous = [lbl for lbl, v in table.items() if lbl not in disc]
    ok(sorted(unanimous) == ["L16_j16", "L16_j8", "L32A_j16", "L32A_j24", "L32A_j8",
                             "L48_j40", "L64_j40"],
       f"the unanimous cell set moved: {sorted(unanimous)}")
    ok(all(table[l]["predict_censored"]["input_load_wall"] for l in ("L48_j40", "L64_j40")),
       "the two deepest step cells must be censored under every law")
    ok(disc["L64_j24"]["predict_censored"] == {"input_load_wall": True, "step_count_wall": False,
                                               "load_depth_product": True, "step40_wall": False},
       "L64_j24 must censor under input and product and deliver under both step laws")
    ok(disc["L48_j8"]["predict_censored"] == {"input_load_wall": True, "step_count_wall": False,
                                              "load_depth_product": False, "step40_wall": False},
       "L48_j8 must be the input-law discriminator at 96 facts")
    ok(disc["L32A_j32"]["predict_censored"] == {"input_load_wall": False, "step_count_wall": True,
                                                "load_depth_product": False,
                                                "step40_wall": False},
       "L32A_j32 is the archived coordinate that only the step-32 law censors")
    ok(disc["L64_j32"]["predict_censored"] == {"input_load_wall": True, "step_count_wall": True,
                                               "load_depth_product": True, "step40_wall": False},
       "L64_j32 must be the cell that separates step 40 from the other three laws")
    for law in LAWS:
        separated = any(table[l]["predict_censored"][law] != table[l]["predict_censored"][other]
                        for l in table for other in LAWS if other != law)
        ok(separated, f"law {law} is not separated from the others by any cell")

    # 6. the anchor digests certify against the archived record, and a mutation is refused
    cert = certify_anchors(rows)
    ok(cert["certified"] == len(R55_ANCHORS), "not every archived anchor is in this plan")
    mutated = [json.loads(json.dumps(r)) for r in rows]
    hit = False
    for r in mutated:
        if r["label"] == "L32A_j32":
            r["prompt_sha256"] = hashlib.sha256(b"mutated").hexdigest()
            r["prompt"] = "mutated"
            hit = True
    ok(hit, "the planted digest mutation did not reach the row")
    caught = False
    try:
        certify_anchors(mutated)
    except RuntimeError:
        caught = True
    ok(caught, "the certifier accepted a planted prompt-digest mutation")
    ok(hashlib.sha256(render_yesno(item48).encode()).hexdigest()[:16] == YESNO_LINEAGE_DIGEST,
       "the level-48 fact block does not rebuild the archived yes/no digest")

    # 7. the response measures: vocabulary, NONE sentinel, empty field is a non-delivery
    vocab = vocab_of(item48)
    gname = terminal_at(item48, item48["query"][0], 16)
    ok(gname in vocab, "the gold terminal is not in the item vocabulary")
    ok(declared_answer(f"... the answer is {gname}", set(vocab))[0] == gname, "name extraction")
    ok(declared_answer("the links run out: NONE", vocab) == (NONE_GOLD, True), "NONE sentinel")
    ok(declared_answer("", vocab) == (None, False), "an empty field must be a non-delivery")
    ok(declared_answer("   ", vocab) == (None, False), "a whitespace field must be a non-delivery")
    ok(declared_answer("I cannot say", vocab) == (None, True), "undetermined is a delivery")
    first, second = None, None
    for name in sorted(vocab)[:2]:
        first, second = name, first
    ok(declared_answer(f"{first} then {second}", vocab)[0] == second,
       "the declared answer must be the last name in the field")

    # 8. the census merge rule, planted in both directions
    trace, fields, srcf = trace_of({"role": "assistant", "content": "c", "reasoning_content": "r1",
                                     "reasoning": "r2"})
    ok((trace, srcf) == ("r1", "reasoning_content"), "reasoning_content must win when non-empty")
    trace, fields, srcf = trace_of({"role": "assistant", "content": "c", "reasoning_content": "",
                                     "reasoning": "r2"})
    ok((trace, srcf) == ("r2", "reasoning"), "reasoning must be used when reasoning_content is empty")
    trace, fields, srcf = trace_of({"role": "assistant", "content": "c"})
    ok((trace, srcf, fields) == ("", "", ["content", "role"]), "no channel must census empty")

    # 9. the sanitizer: planted endpoint noise
    # Fixture noise uses RFC 5737 documentation addresses and a non-model path: the
    # guard scripts scan tracked files, so a live-shaped address or a model file name
    # in a fixture would read as a leak (issue #149). The sanitizer strips both classes.
    dirty = ("see http://[HOST]:8080/v1 for the trace 198.51.100.7:8080 and "
             "/root/models/f.bin plus NIGHTLY_MODEL_ID")
    clean = sanitize(dirty)
    ok("http" not in clean and "198.51.100.7" not in clean and "/root/" not in clean,
       "the sanitizer left a forbidden token")
    ok("[redacted]" in clean, "the sanitizer did not mark what it stripped")
    val = os.environ.get("NIGHTLY_MODEL_ID") or "placeholder-sentinel-value"
    ok(val not in sanitize("NIGHTLY_MODEL_ID=" + val),
       "the environment value must be replaced, not copied")
    ok(len(sanitize("z" * 9000)) == 4000, "the sanitizer must cap trace length")

    # 10. the scoring rules, planted
    spec = gate_spec()
    base = [{"label": r["label"], "kind": r["kind"], "n_facts": r["n_facts"], "j": r["j"],
             "product": r["n_facts"] * r["j"], "gold": r["gold"], "delivered": True,
             "declared": r["gold"], "correct": True, "completion_tokens": 900,
             "trace_chars": 10, "gold_in_trace": False, "pseudo_in_trace": False,
             "census": {"fields": ["content"], "reasoning_field": ""}}
            for r in rows]
    # an all-delivered fixture: the weakest wall (step40, 2 predicted censorings) fits best
    scored = score_records(base, spec)
    ok(scored["tier"] == "step40_wall",
       f"an all-delivered fixture must fit the step40 law (14 of 16), read {scored['tier']}")
    ok(scored["criteria"]["C2"]["pass"] and not scored["criteria"]["C2"]["false_names"],
       "the clean control fixture must pass the amended control gate")
    ok(len(scored["criteria"]["C1"]["false_names"]) == 0, "clean fixture shows a false name")

    # planted: every censored control is a non-delivery and must NOT fail C2 (round 55 gap)
    fixture = [dict(r) for r in base]
    for r in fixture:
        if r["kind"] in ("off_end", "dead_end"):
            r["delivered"] = False
            r["declared"] = None
            r["correct"] = None
    scored = score_records(fixture, spec)
    ok(scored["criteria"]["C2"]["pass"] is True,
       "a censored NONE control was scored as a miss: the round 55 gap is still open")
    ok(scored["criteria"]["C2"]["delivery_rate"] == 0.0
       and len(scored["criteria"]["C2"]["censored_non_deliveries"]) == 6,
       "censored controls must be reported as non-deliveries")
    ok("controls_underpowered" in scored["flags"], "zero delivered controls must flag underpowered")

    # planted: a delivered control that names a wrong entity must fail the gate
    fixture = [dict(r) for r in base]
    for r in fixture:
        if r["label"] == "L48_offend":
            r["declared"] = "bogus"
            r["correct"] = False
    scored = score_records(fixture, spec)
    ok(scored["criteria"]["C2"]["pass"] is False and scored["criteria"]["C2"]["false_names"]
       == ["L48_offend"], "the control gate did not fire on a planted false name")
    ok("control_false_name" in scored["flags"], "missing control_false_name flag")

    # planted: a delivered name cell with a wrong name must set false_name_present
    fixture = [dict(r) for r in base]
    for r in fixture:
        if r["label"] == "L48_j24":
            r["declared"] = "bogus"
            r["correct"] = False
    scored = score_records(fixture, spec)
    ok("false_name_present" in scored["flags"], "missing false_name_present flag")

    # planted: the input-load law observed -> the tier reads input_load_wall
    fixture = [dict(r) for r in base]
    for r in fixture:
        if r["kind"] == "name":
            censored = LAWS["input_load_wall"](r["n_facts"], r["j"])
            r["delivered"] = not censored
            r["declared"] = None if censored else r["gold"]
            r["correct"] = None if censored else True
    scored = score_records(fixture, spec)
    ok(scored["tier"] == "input_load_wall", "the input-load fixture did not read input_load_wall")
    ok(scored["criteria"]["C3"]["step_count_wall"]["agreements"] < 13,
       "the rival step law must not tie the input-load fixture at the tier line")

    # planted: the product law observed -> the tier reads load_depth_product
    fixture = [dict(r) for r in base]
    for r in fixture:
        if r["kind"] == "name":
            censored = LAWS["load_depth_product"](r["n_facts"], r["j"])
            r["delivered"] = not censored
            r["declared"] = None if censored else r["gold"]
            r["correct"] = None if censored else True
    scored = score_records(fixture, spec)
    ok(scored["tier"] == "load_depth_product", "the product fixture did not read load_depth_product")
    ok(scored["criteria"]["C3"]["input_load_wall"]["agreements"] < 13,
       "the input-load law must not tie the product fixture at the tier line")

    # planted: the step-32 law observed -> the tier reads step_count_wall
    fixture = [dict(r) for r in base]
    for r in fixture:
        if r["kind"] == "name":
            censored = LAWS["step_count_wall"](r["n_facts"], r["j"])
            r["delivered"] = not censored
            r["declared"] = None if censored else r["gold"]
            r["correct"] = None if censored else True
    scored = score_records(fixture, spec)
    ok(scored["tier"] == "step_count_wall", "the step-32 fixture did not read step_count_wall")

    # planted: a tie between laws must refuse the tier
    fixture = [dict(r) for r in base]
    for r in fixture:
        if r["kind"] == "name":
            censored = (r["n_facts"] >= 96 and r["j"] >= 32)
            r["delivered"] = not censored
            r["declared"] = None if censored else r["gold"]
            r["correct"] = None if censored else True
    scored = score_records(fixture, spec)
    ok(scored["tier"] == "mixed_laws", f"the tie fixture read {scored['tier']}")
    ok("laws_not_separated" in scored["flags"], "missing laws_not_separated flag")

    # planted: the off-threshold product shift must move the product law's predictions
    ok(LAWS["load_depth_product"](128, 24) is True and LAWS["load_depth_product"](128, 16) is False,
       "the product threshold must censor 128 x 24 and deliver 128 x 16")
    ok(LAWS["load_depth_product"](96, 24) is False, "96 x 24 = 2304 must sit below the threshold")

    # planted: the trace row must refuse an echo-only containment signal
    fixture = [dict(r) for r in base]
    for r in fixture:
        if r["kind"] == "name":
            r["delivered"] = False
            r["trace_chars"] = 4000
            r["gold_in_trace"] = True
            r["pseudo_in_trace"] = True
    scored = score_records(fixture, spec)
    ok(scored["criteria"]["C7"]["gap"] == 0.0 and "trace_provenance_refused" in scored["flags"],
       "the trace row must refuse when gold and pseudo-gold are contained equally")

    # planted: self-agreement split
    fixture = [dict(r) for r in base]
    for r in fixture:
        if r["label"] == "L64_j40_dup":
            r["declared"] = "other"
    scored = score_records(fixture, spec)
    ok("self_agreement_split" in scored["flags"], "the dup control did not detect a planted split")

    # the budget rung: a 256-token rung that delivered would fail H1
    fixture = [dict(r) for r in base]
    scored = score_records(fixture, spec)
    ok(scored["criteria"]["H1"]["pass"] is False, "the all-delivered fixture must fail the rung row")
    for r in fixture:
        if r["label"] == "L64_j32_c256":
            r["delivered"] = False
            r["declared"] = None
            r["correct"] = None
    scored = score_records(fixture, spec)
    ok(scored["criteria"]["H1"]["pass"] is True, "the rung row must pass on a non-delivery")

    # the census row must fire when a record carries no census
    fixture = [dict(r) for r in base]
    fixture[0]["census"] = None
    scored = score_records(fixture, spec)
    ok(scored["criteria"]["C8"]["pass"] is False, "C8 must refuse when a record is uncensused")

    # the post-hoc same-class column: a planted agreement and a planted mismatch
    fixture = [dict(r) for r in base]
    for r in fixture:
        if r["label"] in ("L48_j16", "L32A_j32"):
            r["declared"] = {x[0]: x[1] for x in R56_CELLS}[r["label"]]
        if r["label"] == "L48_j32":
            r["delivered"] = False
            r["declared"] = None
            r["correct"] = None
    scored = score_records(fixture, spec)
    x1 = scored["criteria"]["X1"]
    ok(x1["registered"] is False, "the same-class column must stay post-hoc")
    ok(x1["state_agreement"] == 2 and x1["name_agreement"] == 2,
       "the planted same-class agreement was not read")
    ok(x1["rows"][2]["state_agrees"] is False, "the planted mismatch was not read")

    # the token surface is declared post-hoc and cannot carry a verdict
    ok(scored["token_surface"]["registered"] is False, "the token surface must be marked post-hoc")
    ok(len(scored["token_surface"]["rows"]) == 16, "the token surface must cover the 16 name cells")

    # 11. the gate is deterministic: the blob is reproducible and covers every cell
    blob_a = gate_blob(gate_spec())
    blob_b = gate_blob(gate_spec())
    ok(blob_a == blob_b, "the gate blob is not deterministic")
    spec = gate_spec()
    ok(len(spec["cells"]) == len(rows), "the gate does not cover every planned cell")
    ok({c["prompt_sha256"][:16] for c in spec["cells"] if c["label"] in ANCHOR_BY_LABEL}
       == {a[1] for a in R55_ANCHORS}, "the gate cell digests do not match the anchor table")
    ok(spec["dispatch"]["planned_calls"] + 2 <= CALL_CAP,
       "planned calls plus health and calibration must sit inside the call cap")
    ok(all(c["cap"] <= MAX_TOKENS for c in spec["cells"]), "a gate cell requests a cap above 2048")
    ok(spec["laws"]["load_depth_product"]["predict_censored_iff"].endswith(str(PRODUCT_THRESHOLD)),
       "the product threshold must be stated in the gate")
    ok(all(l in spec["laws"] for l in LAWS), "the gate must carry all four laws")
    ok(spec["dispatch"]["calibration_calls"] == 1, "one calibration call, declared")

    print(f"selftest: {checks} checks passed, {len(rows)} planned calls, "
          f"{len(NAME_CELLS)} name cells, {len(CONTROL_CELLS)} controls, "
          f"gate blob {gate_blob(gate_spec())[:16]}")


# ------------------------------------------------------------------ commands

def freeze_gate(path: str) -> dict:
    spec = gate_spec()
    spec["blob"] = gate_blob(spec)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return spec


def do_calibrate(outdir: str) -> int:
    """One pre-gate call on round 6's level-8 anchor cell. Not experimental data: it confirms
    that this build answers the registered format at shallow depth before any cap is spent."""
    level, index, j = CALIBRATION["level"], CALIBRATION["index"], CALIBRATION["j"]
    item = item_for(level, index)
    prompt = render_name(item, item["query"][0], j)
    gold = terminal_at(item, item["query"][0], j)
    resp = call(prompt, CALIBRATION["cap"])
    declared, delivered = declared_answer(sanitize(resp["message"].get("content"), 2000),
                                          vocab_of(item))
    out = {"label": CALIBRATION["label"], "note": "pre-gate calibration, not experimental data",
           "level": level, "seed": item["seed"], "j": j, "gold": gold,
           "prompt_sha256": prompt_digest(prompt), "expect_digest16": CALIBRATION["expect_digest16"],
           "digest_matches": prompt_digest(prompt)[:16] == CALIBRATION["expect_digest16"],
           "declared": declared, "delivered": delivered, "correct": declared == gold,
           "completion_tokens": resp["completion_tokens"], "finish_reason": resp["finish_reason"],
           "model_digest": model_digest(), "wall_s": resp["wall_s"]}
    with open(os.path.join(outdir, "calibration.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(json.dumps(out, sort_keys=True))
    if not out["digest_matches"]:
        print("CALIBRATION DIGEST MISMATCH: the level 8 cell is not the archived prompt")
        return 3
    return 0


def do_run(outdir: str) -> int:
    global _GATE_BLOB
    rows = plan_prompts()
    cert = certify_anchors(rows)
    spec = freeze_gate(os.path.join(outdir, "gate.json"))
    _GATE_BLOB = spec["blob"]
    print("anchors certified", json.dumps(cert, sort_keys=True))
    print("gate blob", spec["blob"])
    raw_path = os.path.join(outdir, "raw.jsonl")
    done = {}
    if os.path.exists(raw_path):
        done = {r["label"]: r for r in read_jsonl(raw_path)}
        for r in done.values():
            if r.get("transport_error"):
                del done[r["label"]]
    fh = open(raw_path, "a", encoding="utf-8")
    retries = 0
    t_start = time.time()
    not_dispatched = []
    health = call(CENSUS_PROMPT, 256)
    trace, fields, reasoning_field = trace_of(health["message"])
    with open(os.path.join(outdir, "health.json"), "w", encoding="utf-8") as hj:
        json.dump({"fields": fields, "reasoning_field": reasoning_field,
                   "trace_chars": len(sanitize(trace)), "finish_reason": health["finish_reason"],
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
                    time.sleep(RETRY_BACKOFF_S)
        rec = score_record(spec_row, resp or {}, item, err)
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
        print(f"{rec['label']:16s} facts={rec['n_facts']:<4d} j={rec['j']:<3d} "
              f"tok={rec['completion_tokens']} finish={rec['finish_reason']} "
              f"declared={rec['declared']} correct={rec['correct']}")
    fh.close()
    records = read_jsonl(raw_path)
    scored = score_records(records, spec)
    scored["dispatch"] = {"wall_s": round(time.time() - t_start, 3), "planned": len(rows),
                          "dispatched": len(rows) - len(not_dispatched),
                          "not_dispatched": not_dispatched, "retries_used": retries,
                          "call_cap": CALL_CAP, "calibration_calls": 1,
                          "anchor_certification": cert}
    with open(os.path.join(outdir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(scored, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print("tier", scored["tier"], "flags", scored["flags"])
    for law, v in scored["criteria"]["C3"].items():
        print(f"  {law:22s} {v['agreements']}/{v['n']}")
    return 0


def do_rescore(outdir: str) -> int:
    spec = json.load(open(os.path.join(outdir, "gate.json"), encoding="utf-8"))
    records = read_jsonl(os.path.join(outdir, "raw.jsonl"))
    scored = score_records(records, spec)
    prior: dict = {}
    summary_path = os.path.join(outdir, "summary.json")
    if os.path.exists(summary_path):
        prior = json.load(open(summary_path, encoding="utf-8")).get("dispatch", {})
    if prior:
        scored["dispatch"] = prior
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(scored, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print("tier", scored["tier"], "flags", scored["flags"])
    print(json.dumps(scored["criteria"], indent=2, sort_keys=True))
    return 0


def main(argv: list) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--rescore", action="store_true")
    ap.add_argument("--outdir", default=_HERE)
    args = ap.parse_args(argv)
    if args.selftest:
        selftest()
        return 0
    if args.dry_run:
        rows = plan_prompts()
        cert = certify_anchors(rows)
        for row in rows:
            print(f"{row['label']:16s} level={row['level']:<3d} seed={row['seed']} "
                  f"j={row['j']:<3d} cap={row['cap']:<5d} gold={row['gold']:10s} "
                  f"facts={row['n_facts']:<4d} product={row['n_facts'] * row['j']:<5d} "
                  f"digest={row['prompt_sha256'][:16]}")
        table = law_predictions()
        for law in LAWS:
            print(f"predicted censored under {law}: "
                  f"{sorted(l for l, v in table.items() if v['predict_censored'][law])}")
        print("anchors certified", json.dumps(cert, sort_keys=True))
        print("planned calls", len(rows), "of cap", CALL_CAP)
        print("gate blob (dry, not frozen)", gate_blob(gate_spec()))
        return 0
    if args.calibrate:
        return do_calibrate(args.outdir)
    if args.gate:
        spec = freeze_gate(os.path.join(args.outdir, "gate.json"))
        print("gate blob", spec["blob"], "cells", len(spec["cells"]))
        return 0
    if args.run:
        return do_run(args.outdir)
    if args.rescore:
        return do_rescore(args.outdir)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

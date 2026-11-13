#!/usr/bin/env python3
"""Nightly round 64: is a deep ladder failure a missing walk or a lost readout?

Question (registered before dispatch, issue #65). On one name-walk item and one
asked step `j`, the same model answers twice: once free-response (the archived
name-arm template, byte-identical to the archived records), once forced-choice
over five options (the names at positions `j-2`, `j-1`, `j`, `j+1` of that item
plus the word NONE). If the deep failures the program keeps recording (a name on
the right path at the wrong step, the round-59 shape; a censor at the output cap
with the gold inside the trace, the round-63 shape) are readout losses, the
recognition arm should pick the gold on the cells the recall arm misses. If the
step position is simply not represented, recognition should sit at the one-in-five
chance line on exactly those cells.

Design notes that are part of the contract, not of the prose:

- The two arms are a minimal pair. The rule line, the fact block and the task
  sentence are byte-identical between arms; only the answer clause differs, and its
  exact text is frozen here. `--selftest` asserts the shared prefix byte-wise.
- The recall arm is byte-identical to the archived name-arm template: the frozen
  prompt digests of the archived records it reproduces are asserted in `--selftest`.
- Distractors are always drawn from the item's own vocabulary (plus NONE), so no
  option can be recognised from outside the item, and the near-miss options are the
  adjacent step positions the archived errors landed on.
- Every recognition prompt carries exactly one gold option; the option order is a
  seeded shuffle and the gold slot is recorded, because option-position preference
  is a documented confound (arXiv:2309.03882, arXiv:2308.11483).
- Cross-attempt practice effects (arXiv:2503.14996 lineage, Wenger et al. 1980)
  cannot operate here: each dispatch is a stateless single-turn request, so the
  arms are independent samples of one latent state rather than a test-retest pair.
- The controls follow the issue #139 fix: every NONE control is a one-step ask on a
  path tail, so a control cannot inherit a deep cell's output budget.
- Plan scale is chosen by a measured pre-dispatch rate against frozen thresholds
  (the standing round-61 rule, issue #141), and the choice is recorded in
  `measure.json` before `gate.json` freezes.

Endpoint credentials and the serving id come from the environment only and are
never written to any artifact; the round records a sha256 prefix of the serving id
as a build fingerprint. Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_REPO, "generators"))

import ladders  # noqa: E402

SEED_BASE = 20261005          # round 51's seed base: the k = 48 anchor is the archived item
SCAN = 300                    # round 51's scan width (the issue #129 measurement table)
MAX_TOKENS = 2048             # protocol cap: no requested cap may exceed it
CENSUS_CAP = 256
CALL_CAP = 40
TIMEOUT_S = 900
DISPATCH_BUDGET_S = 1800      # wall-clock guard on the dispatch phase
MAX_RETRIES_TOTAL = 2
NONE_GOLD = "NONE"
GATE_SCHEMA = "round64-gate-v1"
CHANCE = 0.2                  # five options, one of them gold
ALPHA = 0.05                  # exact one-sided binomial threshold on the recognition win
MIN_MATERIAL = 4              # recall-failed cells needed before any dissociation claim

# Pre-registered plan-selection thresholds (frozen worst-case arithmetic, all cells
# at the cap): full 23 cells = 47,104 completion tokens, at 27 tok/s 1,745 s;
# trimmed 19 cells = 38,912 tokens, at 22 tok/s 1,769 s; core 14 cells = 28,672
# tokens, at 16 tok/s 1,792 s. All three inside the frozen 1,800 s dispatch budget.
RATE_FULL_PLAN = 27.0
RATE_TRIM_PLAN = 22.0
RATE_CORE_PLAN = 16.0

# The archived k = 48 load-floor item: rounds 51, 52, 53, 54 dispatched its yes/no
# form byte-identically; round 63 dispatched its name form (j = 48, j = 8).
ARCHIVED_K48 = {"seed": 116261051, "yesno_digest16": "068bc6a1fb0620fb"}
ARCHIVED_RECALL_PROMPTS = {
    # label -> sha256 of the archived name-arm prompt this round reproduces byte-wise
    "A48_j8_R": "cec71db935bf42f9b0707da23f6973c622dd8b780fc9abc68f1f33edd5716260",
    "A48_j48_R": "baabc3462652878fdbdca1994faa18240e917b5f0fea69fd786d34e56526c4c9",
    "C64_j64_R": "c1ef6c20bfd84e2fd30a6eaefa22caf1dfb4663280b0824cac72e89f298eea7e",
    "C64_deadend_R": "c36ea5dff6d90a069d0573968c9823c92e403bfdb0891862aab56a19669af465",
}

CENSUS_PROMPT = ("Rule: for all x, y, z: if x precedes y and y precedes z, then x precedes z. "
                 "Facts: alby precedes birch. birch precedes cobin. Question: does alby precedes "
                 "cobin? Answer with exactly one word: yes or no.")

# The frozen answer clauses. The shared prefix is everything before them.
RECALL_CLAUSE = ("Answer with exactly one entity name, or the single word NONE if the links "
                 "run out before {j} steps.")
RECOG_CLAUSE = ("Which name is reached at step {j}? Answer with exactly one of these five "
                "options, copied exactly as written: {opts}. If the links run out before {j} "
                "steps, answer NONE.")


# ------------------------------------------------------------------ items


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
    """The items whose fact count is 2 * level: exactly two chains, the smallest load in
    the corpus (issue #129). Deterministic in the seed base."""
    return [it for it in series_scan(level) if len(it["facts"]) == 2 * level]


def adjacency(item: dict) -> dict:
    adj: dict = {}
    for s, _, t in item["facts"]:
        assert s not in adj, "out-degree above one"
        adj[s] = t
    return adj


def check_item(item: dict) -> None:
    """Refuse anything that is not a load-floor, component-isomorphic two-path item."""
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


def path_index(item: dict) -> dict:
    """Independent solver: every node mapped to (head, position from that head)."""
    adj = adjacency(item)
    inc = {t for _, _, t in item["facts"]}
    heads = sorted(s for s in adj if s not in inc)
    idx: dict = {}
    for h in heads:
        cur, pos = h, 0
        while True:
            idx[cur] = (h, pos)
            nxt = adj.get(cur)
            if nxt is None:
                break
            cur, pos = nxt, pos + 1
    assert len(idx) == 2 * item["level"] + 2, ("node count off", len(idx), item["level"])
    return idx


def heads_of(item: dict) -> list:
    adj = adjacency(item)
    inc = {t for _, _, t in item["facts"]}
    return sorted(s for s in adj if s not in inc)


def tails_of(item: dict) -> list:
    adj = adjacency(item)
    return sorted(t for t in {t for _, _, t in item["facts"]} if t not in adj)


def terminal_at(item: dict, src: str, steps: int):
    """The node reached from src by exactly `steps` direct links, or None."""
    adj = adjacency(item)
    cur = src
    for _ in range(max(steps, 0)):
        nxt = adj.get(cur)
        if nxt is None:
            return None
        cur = nxt
    return cur


def select_items() -> dict:
    """Deterministic item set: the archived k = 48 anchor plus the first load-floor item at
    levels 40 and 64. The k = 64 item is round 63's, so its name-form and dead-end prompts
    are cross-class duplicates of archived records."""
    anchor = next(it for it in load_floor(48) if it["seed"] == ARCHIVED_K48["seed"])
    check_item(anchor)
    items = {"A48": anchor}
    for key, level in (("B40", 40), ("C64", 64)):
        lf = load_floor(level)
        assert lf, f"level {level} produced no load-floor items in the scan"
        check_item(lf[0])
        items[key] = lf[0]
    return items


_ITEMS: dict = {}


def item_for(key: str) -> dict:
    return _ITEMS[key]


def vocab_of(item: dict) -> set:
    words = set()
    for s, _, t in item["facts"]:
        words.add(s)
        words.add(t)
    return words


def fact_block(item: dict) -> str:
    return "\n".join(f"{s} {r} {t}." for s, r, t in item["facts"])


# ------------------------------------------------------------------ prompts


def shared_prefix(item: dict, src: str, j: int) -> str:
    return (f"{item['rule']}\nFacts:\n{fact_block(item)}\n\n"
            f"Task: start at {src} and follow the direct links for exactly {j} steps. ")


def render_recall(item: dict, src: str, j: int) -> str:
    return shared_prefix(item, src, j) + RECALL_CLAUSE.format(j=j)


def render_recog(item: dict, src: str, j: int, options: list) -> str:
    return (shared_prefix(item, src, j)
            + RECOG_CLAUSE.format(j=j, opts=", ".join(options)))


def render_yesno(item: dict) -> str:
    """The round-6 / round-50 / round-51 template, byte-identical: certifies that the
    k = 48 anchor's fact block is the archived one."""
    qs, qrel, qt = item["query"]
    return (f"{item['rule']}\nFacts:\n{fact_block(item)}\n\n"
            f"Question: does {qs} {qrel} {qt}?\n"
            "Answer with exactly one word: yes or no.")


def prompt_digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def certify_anchor() -> str:
    """16-hex digest of the archived yes/no form of the k = 48 anchor item."""
    return prompt_digest(render_yesno(item_for("A48")))[:16]


# ------------------------------------------------------------------ option sets


def option_names(item: dict, src: str, j: int, gold: str, want: int) -> list:
    """Distractors, every one of them a name that occurs in this item and none of them the
    gold. Adjacent step positions first (the archived error targets), then the other path's
    endpoints, then a sorted vocabulary tail so the rule is total."""
    lvl = item["level"]
    out: list = []

    def add(name) -> None:
        if name and name != gold and name != NONE_GOLD and name not in out and len(out) < want:
            out.append(name)

    for p in (j - 1, j + 1, j - 2, j + 2, 0):
        add(terminal_at(item, src, p))
    own = path_index(item).get(src, (None, None))[0]
    for h in heads_of(item):
        if h == own:
            continue
        for p in (lvl, 1, lvl // 2, lvl - 1, 2):
            add(terminal_at(item, h, p))
    for w in sorted(vocab_of(item)):
        add(w)
    assert len(out) == want, ("option fill rule did not reach its distractors", src, j, gold, out)
    return out


def build_options(item: dict, src: str, j: int, gold: str, label: str) -> tuple:
    """Five options: the gold, three distractors (four, when the gold is NONE), and NONE, in a
    seeded shuffle. Returns (options, gold_slot)."""
    want = 4 if gold == NONE_GOLD else 3
    opts = option_names(item, src, j, gold, want)
    if gold != NONE_GOLD:
        opts.append(gold)
    opts.append(NONE_GOLD)
    assert len(set(opts)) == 5, ("duplicate option", opts)
    assert opts.count(gold) == 1, ("gold offered more than once", gold, opts)
    seed = int(hashlib.sha256(f"{label}|{item['seed']}".encode()).hexdigest()[:12], 16)
    random.Random(seed).shuffle(opts)
    return opts, opts.index(gold)


# ------------------------------------------------------------------ plan


def _cell(label: str, key: str, j: int, arm: str, kind: str, cap: int = MAX_TOKENS) -> tuple:
    return (label, key, j, arm, kind, cap)


# Order is part of the registration: the four recognition form cells first (a broken
# instrument must be caught before the budget is spent), the two recall baseline cells,
# then the five deep pairs, then the two mid pairs, then the byte-identical duplicate.
PLAN_FULL = [
    _cell("A48_j8_P", "A48", 8, "P", "name"),
    _cell("B40_j16_P", "B40", 16, "P", "name"),
    _cell("A48_deadend_P", "A48", 1, "P", "dead_end"),
    _cell("C64_deadend_P", "C64", 1, "P", "dead_end"),
    _cell("A48_deadend_R", "A48", 1, "R", "dead_end"),
    _cell("C64_deadend_R", "C64", 1, "R", "dead_end"),
    _cell("A48_j8_R", "A48", 8, "R", "name"),
    _cell("B40_j16_R", "B40", 16, "R", "name"),
    _cell("A48_j40_R", "A48", 40, "R", "name"),
    _cell("A48_j40_P", "A48", 40, "P", "name"),
    _cell("A48_j48_R", "A48", 48, "R", "name"),
    _cell("A48_j48_P", "A48", 48, "P", "name"),
    _cell("B40_j40_R", "B40", 40, "R", "name"),
    _cell("B40_j40_P", "B40", 40, "P", "name"),
    _cell("C64_j48_R", "C64", 48, "R", "name"),
    _cell("C64_j48_P", "C64", 48, "P", "name"),
    _cell("C64_j64_R", "C64", 64, "R", "name"),
    _cell("C64_j64_P", "C64", 64, "P", "name"),
    _cell("A48_j24_R", "A48", 24, "R", "name"),
    _cell("A48_j24_P", "A48", 24, "P", "name"),
    _cell("C64_j32_R", "C64", 32, "R", "name"),
    _cell("C64_j32_P", "C64", 32, "P", "name"),
    _cell("A48_j40_R_dup", "A48", 40, "R", "dup"),
]

# Trimmed: the two mid pairs drop out. Core: the k = 64 deep pairs and the duplicate drop
# out as well, leaving the form cells, the baselines and three deep pairs.
PLAN_TRIM = [c for c in PLAN_FULL if c[0] not in
             ("A48_j24_R", "A48_j24_P", "C64_j32_R", "C64_j32_P")]
PLAN_CORE = [c for c in PLAN_TRIM if c[0] not in
             ("C64_j48_R", "C64_j48_P", "C64_j64_R", "C64_j64_P", "A48_j40_R_dup")]

PANELS = {"r64": PLAN_FULL, "r64trim": PLAN_TRIM, "r64core": PLAN_CORE}

FORM_CELLS = ("A48_j8_P", "B40_j16_P", "A48_deadend_P", "C64_deadend_P")
BASELINE_CELLS = ("A48_j8_R", "B40_j16_R")
NONE_CONTROL_CELLS = ("A48_deadend_R", "C64_deadend_R")
DUP_PAIRS = (("A48_j40_R", "A48_j40_R_dup"),)
CALIBRATION_LABEL = "A48_j8_P"        # the pre-gate rate call doubles as this cell's twin
DEEP_J = (40, 48, 64)
SHALLOW_J = (8, 16)


def plan_selection(rate: float) -> str:
    """The frozen selection rule: full at or above RATE_FULL_PLAN, trimmed at or above
    RATE_TRIM_PLAN, core at or above RATE_CORE_PLAN. Below RATE_CORE_PLAN the core plan is
    kept and the dispatch budget governs: cells that do not land stay not_dispatched."""
    if rate >= RATE_FULL_PLAN:
        return "r64"
    if rate >= RATE_TRIM_PLAN:
        return "r64trim"
    return "r64core"


def cell_src(item: dict, kind: str) -> str:
    if kind == "dead_end":
        return tails_of(item)[0]
    return item["query"][0]


def plan_prompts(plan: list) -> list:
    """Expand the panel into records carrying prompt, gold, options and source, before any
    endpoint call."""
    out = []
    for label, key, j, arm, kind, cap in plan:
        item = item_for(key)
        src = cell_src(item, kind)
        reached = terminal_at(item, src, j)
        gold = NONE_GOLD if reached is None else reached
        assert (gold == NONE_GOLD) == (kind == "dead_end"), (label, gold, kind)
        if arm == "R":
            prompt = render_recall(item, src, j)
            options, gold_slot = None, None
        else:
            options, gold_slot = build_options(item, src, j, gold, label)
            prompt = render_recog(item, src, j, options)
        idx = path_index(item)
        out.append({"label": label, "arm": arm, "kind": kind, "level": item["level"],
                    "seed": item["seed"], "item_key": key, "src": src, "j": j, "cap": cap,
                    "gold": gold, "gold_position": idx[gold][1] if gold != NONE_GOLD else None,
                    "src_position": idx[src][1], "path_head": idx[src][0],
                    "options": options, "gold_slot": gold_slot, "prompt": prompt,
                    "n_facts": len(item["facts"]), "prompt_sha256": prompt_digest(prompt)})
    return out


# ------------------------------------------------------------------ sanitizer


_SECRET_PATTERNS = [
    re.compile(r"https?://\S+"),
    re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d+)?\b"),
    re.compile(r"/(?:root|home|mnt|media|run/user)/\S+"),
]


def sanitize(text, limit: int = 1200) -> str:
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
    return out[:limit] if len(out) > limit else out


def model_digest() -> str:
    """Build fingerprint: a hash prefix, never the serving id itself."""
    return hashlib.sha256(os.environ.get("NIGHTLY_MODEL_ID", "").encode()).hexdigest()[:16]


# ------------------------------------------------------------------ response measures

NAME_RE = re.compile(r"[A-Za-z]+")


def declared_recall(content: str, vocab: set):
    """The last entity name in the visible answer field, else the NONE sentinel, else
    undetermined. An empty answer field is not a delivery."""
    if not content or not content.strip():
        return None, False
    ents = [t.lower() for t in NAME_RE.findall(content) if t.lower() in vocab]
    if ents:
        return ents[-1], True
    if re.search(r"\bnone\b", content, re.I):
        return NONE_GOLD, True
    return None, True


def declared_pick(content: str, options: list):
    """The recognition readout rule: the last offered option that occurs in the visible
    field, compared as a whole word. A name that is in the item but not among the options
    is returned as an off-options declaration and scored wrong."""
    if not content or not content.strip():
        return None, False, False
    low = content.lower()
    hits = []
    for opt in options:
        if re.search(r"(?<![a-z0-9_])" + re.escape(opt.lower()) + r"(?![a-z0-9_])", low):
            hits.append((low.rindex(opt.lower()), opt))
    if hits:
        return max(hits)[1], True, True
    return None, True, False


# ------------------------------------------------------------------ error signatures


def recall_signature(cell: dict, declared) -> str:
    """The frozen taxonomy every recall cell is filed under."""
    gold, j = cell["gold"], cell["j"]
    if declared is None:
        return "no_delivery"
    if declared == gold:
        return "correct"
    if gold == NONE_GOLD:
        idx = path_index(item_for(cell["item_key"]))
        if declared == cell["src"]:
            return "clamp_start"
        hit = idx.get(declared)
        if hit is None:
            return "off_item"
        if hit[0] == cell["path_head"] and hit[1] > cell["src_position"]:
            return "past_end_same_path"
        return "other_path_name"
    if declared == NONE_GOLD:
        return "refusal"
    hit = path_index(item_for(cell["item_key"])).get(declared)
    if hit is None:
        return "off_item"
    if hit[0] != cell["path_head"]:
        return "other_path_name"
    offset = hit[1] - (cell["src_position"] + j)
    if abs(offset) <= 2:
        return "near_step_offset"
    return "far_on_path"


def pick_kind(cell: dict, declared, in_options: bool, recall_declared) -> str:
    """The frozen taxonomy every recognition cell is filed under."""
    if declared is None:
        return "no_delivery" if not in_options else "off_options"
    if not in_options:
        return "off_options"
    if declared == cell["gold"]:
        return "gold"
    if recall_declared is not None and declared == recall_declared:
        return "recall_match"
    if declared == NONE_GOLD:
        return "none"
    return "other_option"


# ------------------------------------------------------------------ statistics


def binom_upper(n: int, k: int, p: float) -> float:
    """Exact one-sided binomial tail P(X >= k) for small n."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    total = 0.0
    for i in range(k, n + 1):
        total += math.comb(n, i) * (p ** i) * ((1.0 - p) ** (n - i))
    return min(1.0, total)


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


def trace_of(message: dict) -> tuple:
    """Issue #105 merge rule: reasoning_content if non-empty, else reasoning, else empty."""
    fields = sorted(message)
    rc = message.get("reasoning_content") or ""
    src = "reasoning_content" if rc else ""
    if not rc:
        rc = message.get("reasoning") or ""
        src = "reasoning" if rc else ""
    return rc, fields, src


# ------------------------------------------------------------------ gate


THEORY = {
    "T1_position_bias_confound": {
        "source": "arXiv:2309.03882 (ICLR 2024); arXiv:2308.11483",
        "statement": ("option-position preference moves reported multiple-choice accuracy, "
                      "and the preference traces to token-level bias rather than to content, "
                      "so a forced-choice arm needs its key positions balanced and recorded"),
        "verification": "abstract-level in this firing (arXiv export API id_list fetch)"},
    "T2_format_is_not_neutral": {
        "source": "arXiv:2507.02856; arXiv:2503.14996; arXiv:2503.13508",
        "statement": ("the same model scores differently on multiple-choice and on "
                      "generative answer matching, and part of the multiple-choice score is "
                      "extraction- and format-driven, so a recognition-arm gain is not by "
                      "itself evidence of competence"),
        "verification": "abstract-level in this firing (arXiv export API)"},
    "T3_recognition_without_recall": {
        "source": "DOI:10.1080/09658211.2024.2397037; DOI:10.1037/0278-7393.6.2.135",
        "statement": ("in human memory the two readouts of one store dissociate: forced-choice "
                      "recognition can stay above chance where cued recall fails, and a prior "
                      "recall attempt changes later recognition, which is why the arms here run "
                      "as independent stateless dispatches"),
        "verification": "metadata-level in this firing (Crossref records, no quote taken)"},
    "T4_knowledge_prediction_gap": {
        "source": "arXiv:2509.23782 (ICML 2026); arXiv:2207.05221; arXiv:2305.04388",
        "statement": ("a model can hold an answer in its hidden representations and still fail "
                      "to emit it, and its written trace need not report what drove the answer, "
                      "so representation and expression are separate measurement targets"),
        "verification": "abstract-level in this firing (arXiv export API)"},
    "T5_step_counting_is_not_connectivity": {
        "source": "arXiv:2305.18654; arXiv:2407.15160; arXiv:2405.18719",
        "statement": ("multi-step composition degrades with graph depth while counting and "
                      "ordinal selection are separately capacity-limited and are not what token "
                      "positions encode, which is the mechanism the archived wrong-step "
                      "signatures point at"),
        "verification": "abstract-level in this firing (arXiv export API)"},
}


def criteria_spec(blob_holder: dict) -> dict:
    """Gate rows. `blob_holder` carries nothing at build time: the blob is a property of the
    whole spec and is attached to gate.json and to every raw record, per research/AGENTS.md."""
    return {
        "F1_form_validity": {
            "criterion": ("recognition delivers the gold on both shallow cells and picks NONE on "
                          "both one-step dead-end controls, four of four delivered"),
            "threshold": "4/4"},
        "F2_recall_controls": {
            "criterion": ("the free-response arm delivers the gold on both shallow cells and "
                          "NONE on both one-step dead-end controls, so the control set certifies "
                          "this firing on the shallow control shape the issue #139 fix prescribes"),
            "threshold": "4/4"},
        "D1_dissociation": {
            "criterion": ("over the paired name cells at j >= 24 whose recall arm missed the gold "
                          "(n cells), the recognition arm picks the gold in m cells; tier "
                          "readout_failure needs m >= 4 and an exact one-sided binomial "
                          f"P(X >= m | n, {CHANCE}) < {ALPHA}; representation_failure needs "
                          "m <= 1; a firing with fewer than 4 recall-missed cells has no "
                          "dissociation material"),
            "threshold": "n >= 4"},
        "D2_head_to_head": {
            "criterion": ("among the recall-missed paired cells, the recognition pick is counted "
                          "as gold, the same wrong name the recall arm declared, another option, "
                          "or NONE; a pick that repeats the recall error is a representation "
                          "error, not a lost readout"),
            "threshold": "descriptive"},
        "D3_error_census": {
            "criterion": ("every recall cell is filed under exactly one frozen signature "
                          "(correct, near_step_offset, far_on_path, other_path_name, off_item, "
                          "refusal, clamp_start, past_end_same_path, no_delivery) and every "
                          "recognition cell under gold, recall_match, other_option, none, "
                          "off_options or no_delivery"),
            "threshold": "all cells filed"},
        "D4_j_band": {
            "criterion": ("recall accuracy is reported separately for j <= 16, 24 <= j <= 32 and "
                          "j >= 40; the round-59 turnover claim is refuted on this build where a "
                          "j >= 40 cell delivers the gold, and supported where every j >= 40 cell "
                          "misses while every j <= 32 cell hits"),
            "threshold": "descriptive"},
        "S1_self_agreement": {
            "criterion": ("the byte-identical recall duplicate pair agrees on the declared answer "
                          "conditioned on both delivering (issue #100; the delivery outcome is not "
                          "the claimed quantity, per the round-63 MTP lesson), and the recognition "
                          "twin of the pre-gate calibration call is reported separately"),
            "threshold": "descriptive"},
        "C3_census": {
            "criterion": ("every record carries its message field names and the reasoning-supplying "
                          "field under the issue #105 merge rule, and the class-level statement "
                          "names the archived same-class side"),
            "threshold": "all records"},
        "C4_option_balance": {
            "criterion": ("the gold slot index is recorded for every recognition cell and the "
                          "slot distribution is reported; the instrument claims no per-slot test "
                          "at this n"),
            "threshold": "recorded"},
        "C5_option_integrity": {
            "criterion": ("every offered option other than NONE occurs in that item's own "
                          "vocabulary, the five options are distinct, exactly one equals the gold, "
                          "and the two arms share a byte-identical prefix through the task "
                          "sentence"),
            "threshold": "all cells"},
        "R1_rate_gate": {
            "criterion": ("the dispatch plan was selected by the measured pre-dispatch completion "
                          "rate against the frozen thresholds, and the measurement is recorded in "
                          "measure.json before gate.json freezes (issue #141)"),
            "threshold": "selected"},
        "L1_archived_prompt_identity": {
            "criterion": ("the free-response prompts that reproduce archived name-arm records are "
                          "byte-identical to them by prompt sha256, so the recall arm is a "
                          "cross-firing duplicate rather than a new task"),
            "threshold": "all named cells"},
    }


def gate_blob(spec: dict) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()


def tier_rule() -> dict:
    return {
        "order": ["form_invalid", "dispatch_incomplete", "controls_invalid",
                  "no_dissociation_material", "readout_failure", "representation_failure",
                  "mixed", "unresolved"],
        "notes": ("form_invalid fires from the F1 row whether or not the run was stopped early "
                  "for it; controls_invalid fires when the free-response arm names an entity "
                  "where the links ran out or misses a shallow cell, which is the round-59 and "
                  "round-60 refusal and leaves the paired contrast uncertified rather than "
                  "reinterpreted; the dissociation tiers apply only when D1 has at least 4 paired "
                  "recall-missed cells; nothing in this table converts a single cell into a "
                  "class-level claim; the core panel carries 3 deep pairs, so a rate-starved "
                  "firing cannot reach a dissociation tier and owes the panel to the next one"),
    }


def build_gate(panel: str, measure: dict) -> dict:
    spec = {
        "schema": GATE_SCHEMA,
        "question": ("On a name-walk item and one asked step j, does a forced-choice "
                     "recognition arm recover the gold on the cells the free-response recall "
                     "arm misses? If it does, the deep failure is a readout loss on a walk the "
                     "deployment still represents; if recognition sits at the one-in-five "
                     "chance line on exactly those cells, the step position is not represented "
                     "and the length-generalization reading stands. Registered on the "
                     "flash-next-class build this firing was assigned, on the round-59 wrong-step "
                     "band (j >= 40) plus a mid and a shallow band, with the archived k = 48 and "
                     "k = 64 anchor items."),
        "criteria": criteria_spec({}),
        "theory": THEORY,
        "tier_rule": tier_rule(),
        "plan_rule": {"rate_full_plan": RATE_FULL_PLAN, "rate_trim_plan": RATE_TRIM_PLAN,
                      "rate_core_plan": RATE_CORE_PLAN, "dispatch_budget_s": DISPATCH_BUDGET_S,
                      "chance": CHANCE, "alpha": ALPHA, "min_material": MIN_MATERIAL,
                      "worst_case_tokens": {"r64": len(PLAN_FULL) * MAX_TOKENS,
                                            "r64trim": len(PLAN_TRIM) * MAX_TOKENS,
                                            "r64core": len(PLAN_CORE) * MAX_TOKENS}},
        "contract": {"max_tokens": MAX_TOKENS, "temperature": 0.0, "call_cap": CALL_CAP,
                     "arm_pair": "shared prefix through the task sentence, answer clause only "
                                 "differs", "control_shape": "one-step ask on a path tail "
                                 "(issue #139 fix)", "stateless_arms": True},
        "rate_measurement": measure,
        "panel_name": panel,
        "cells": [{"label": c["label"], "arm": c["arm"], "j": c["j"], "kind": c["kind"],
                   "level": c["level"], "seed": c["seed"], "src": c["src"], "gold": c["gold"],
                   "gold_slot": c["gold_slot"], "options": c["options"],
                   "prompt_sha256": c["prompt_sha256"]} for c in plan_prompts(PANELS[panel])],
    }
    spec["blob"] = gate_blob(spec)
    return spec


# ------------------------------------------------------------------ scoring


def score_record(row: dict, resp: dict, error: str = "") -> dict:
    cell = row
    message = (resp or {}).get("message", {}) or {}
    content = sanitize(message.get("content"))
    trace, fields, reasoning_field = trace_of(message)
    item = item_for(cell["item_key"])
    vocab = vocab_of(item) | {NONE_GOLD}
    if cell["arm"] == "R":
        declared, delivered = declared_recall(content, vocab)
        signature = recall_signature(cell, declared)
        in_options = None
    else:
        declared, delivered, in_options = declared_pick(content, cell["options"] or [])
        signature = None
    completion = (resp or {}).get("completion_tokens")
    wall = (resp or {}).get("wall_s")
    rec = {"label": cell["label"], "arm": cell["arm"], "kind": cell["kind"],
           "item_key": cell["item_key"], "level": cell["level"], "seed": cell["seed"],
           "src": cell["src"], "j": cell["j"], "cap": cell["cap"], "gold": cell["gold"],
           "gold_position": cell["gold_position"], "options": cell["options"],
           "gold_slot": cell["gold_slot"], "prompt": sanitize(cell["prompt"], 4000),
           "prompt_sha256": cell["prompt_sha256"], "prompt_chars": len(cell["prompt"]),
           "n_facts": cell["n_facts"], "content": content,
           "content_chars": len(content), "declared": declared,
           "delivered": bool(delivered), "finish_reason": (resp or {}).get("finish_reason"),
           "completion_tokens": completion, "prompt_tokens": (resp or {}).get("prompt_tokens"),
           "wall_s": wall,
           "tok_per_s": (round(completion / wall, 3) if completion and wall else None),
           "message_fields": fields, "reasoning_field": reasoning_field,
           "trace_chars": len(trace), "model_digest": model_digest(),
           "error": error or ""}
    rec["correct"] = bool(declared is not None and declared == cell["gold"])
    if cell["arm"] == "R":
        rec["signature"] = signature
    else:
        rec["pick_in_options"] = bool(in_options)
    return rec


def paired_records(records: list) -> dict:
    """label-without-arm -> {arm: record}, restricted to name cells that have both arms."""
    by: dict = {}
    for r in records:
        if r["kind"] == "dup":
            continue
        base = r["label"].rsplit("_", 1)[0]
        by.setdefault(base, {})[r["arm"]] = r
    return {k: v for k, v in by.items() if "R" in v and "P" in v}


def evaluate(records: list, spec: dict) -> dict:
    """The frozen scorecard. Deterministic in raw.jsonl plus the frozen gate."""
    by_label = {r["label"]: r for r in records}
    plan_labels = [c["label"] for c in spec["cells"]]
    missing = [lab for lab in plan_labels if lab not in by_label]
    flags = []

    form = [by_label.get(l) for l in FORM_CELLS]
    form_present = [r for r in form if r]
    form_failed = bool(form_present) and not all(
        r["delivered"] and r["correct"] for r in form_present)
    if form_failed:
        flags.append("form_invalid")
    base = [by_label.get(l) for l in BASELINE_CELLS]
    ctrl = [by_label.get(l) for l in NONE_CONTROL_CELLS]
    controls_ok = bool(all(r and r["delivered"] and r["correct"] for r in base + ctrl))
    if not controls_ok and not missing:
        flags.append("controls_invalid")

    paired = paired_records(records)
    deep_mid = {k: v for k, v in paired.items()
                if v["R"]["kind"] == "name" and v["R"]["j"] >= 24}
    missed = {k: v for k, v in deep_mid.items() if not v["R"]["correct"]}
    n = len(missed)
    m = sum(1 for v in missed.values() if v["P"]["correct"])
    pval = binom_upper(n, m, CHANCE) if n else None
    head = {"gold": 0, "recall_match": 0, "other_option": 0, "none": 0,
            "off_options": 0, "no_delivery": 0}
    for v in missed.values():
        pr = v["P"]
        if not pr["delivered"]:
            head["no_delivery"] += 1
        elif not pr.get("pick_in_options"):
            head["off_options"] += 1
        elif pr["declared"] == v["R"]["gold"]:
            head["gold"] += 1
        elif pr["declared"] is not None and pr["declared"] == v["R"]["declared"]:
            head["recall_match"] += 1
        elif pr["declared"] == NONE_GOLD:
            head["none"] += 1
        else:
            head["other_option"] += 1

    if form_failed:
        tier = "form_invalid"
    elif missing:
        tier = "dispatch_incomplete"
    elif not controls_ok:
        tier = "controls_invalid"
    elif n < MIN_MATERIAL:
        tier = "no_dissociation_material"
    elif m >= MIN_MATERIAL and pval is not None and pval < ALPHA:
        tier = "readout_failure"
    elif m <= 1:
        tier = "representation_failure"
    else:
        tier = "mixed"

    sig_counts: dict = {}
    for r in records:
        if r["arm"] == "R":
            sig_counts[r.get("signature") or "unfiled"] = \
                sig_counts.get(r.get("signature") or "unfiled", 0) + 1
    bands = {}
    for name, lo, hi in (("j <= 16", 0, 16), ("24 <= j <= 32", 24, 32), ("j >= 40", 40, 999)):
        cells = [r for r in records if r["arm"] == "R" and r["kind"] in ("name", "dup")
                 and lo <= r["j"] <= hi]
        bands[name] = f"{sum(1 for r in cells if r['correct'])}/{len(cells)}" if cells else "n/a"

    dup_rows = []
    for a, b in DUP_PAIRS:
        ra, rb = by_label.get(a), by_label.get(b)
        if ra and rb:
            dup_rows.append({"pair": f"{a} / {b}",
                             "prompt_identical": ra["prompt_sha256"] == rb["prompt_sha256"],
                             "both_delivered": bool(ra["delivered"] and rb["delivered"]),
                             "declared_a": ra["declared"], "declared_b": rb["declared"],
                             "agree_declared": ra["declared"] == rb["declared"],
                             "completion_tokens": [ra["completion_tokens"],
                                                   rb["completion_tokens"]]})

    slots: dict = {}
    for r in records:
        if r["arm"] == "P" and r.get("gold_slot") is not None:
            key = r["gold_slot"]
            slots[str(key)] = slots.get(str(key), 0) + 1
    pick_slots = {}
    for r in records:
        if r["arm"] == "P" and r["declared"] in (r.get("options") or []):
            s = r["options"].index(r["declared"])
            pick_slots[str(s)] = pick_slots.get(str(s), 0) + 1

    census = {}
    for r in records:
        key = json.dumps({"fields": r["message_fields"], "reasoning": r["reasoning_field"]},
                         sort_keys=True)
        census[key] = census.get(key, 0) + 1

    scorecard = {
        "F1_form_validity": f"{sum(1 for r in form if r and r['correct'])}/4",
        "F2_recall_controls": (f"{sum(1 for r in base + ctrl if r and r['correct'])}/4 "
                               f"(shallow {sum(1 for r in base if r and r['correct'])}/2, "
                               f"NONE controls "
                               f"{sum(1 for r in ctrl if r and r['correct'])}/2)"),
        "D1_dissociation": (f"n {n}, m {m}, exact P(X >= m | n, {CHANCE}) "
                            f"{('%.4f' % pval) if pval is not None else 'n/a'}"),
        "D2_head_to_head": json.dumps(head, sort_keys=True),
        "D3_error_census": json.dumps(sig_counts, sort_keys=True),
        "D4_j_band": json.dumps(bands, sort_keys=True),
        "S1_self_agreement": json.dumps(dup_rows, sort_keys=True),
        "C3_census": json.dumps(sorted(census.items()), sort_keys=True),
        "C4_option_balance": json.dumps({"gold_slots": slots, "pick_slots": pick_slots},
                                        sort_keys=True),
        "C5_option_integrity": "see selftest and the per-cell assertions in plan_prompts",
        "R1_rate_gate": json.dumps({"rate": spec["rate_measurement"].get("rate_tok_per_s"),
                                    "panel": spec["panel_name"]}, sort_keys=True),
        "L1_archived_prompt_identity": archived_identity_report(records),
    }
    if any(r["finish_reason"] == "length" for r in records):
        flags.append("cap_truncation_present")
    if not missing and any(r.get("error") for r in records):
        flags.append("transport_error_recorded")
    return {"tier": tier, "flags": sorted(set(flags)), "scorecard": scorecard,
            "not_dispatched": missing, "paired_cells": sorted(paired),
            "recall_missed_paired": sorted(missed), "n_missed": n, "m_recognised": m,
            "binomial_p": pval, "chance": CHANCE}


def archived_identity_report(records: list) -> str:
    got = {r["label"]: r["prompt_sha256"] for r in records if r["arm"] == "R"}
    out = {}
    for label, want in ARCHIVED_RECALL_PROMPTS.items():
        have = got.get(label)
        out[label] = ("match" if have == want else
                      ("mismatch" if have else "not dispatched"))
    return json.dumps(out, sort_keys=True)


# ------------------------------------------------------------------ io helpers


def write_json(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)
        fh.write("\n")


def read_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_jsonl(path: str, rows: list) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def append_jsonl(path: str, row: dict) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def read_jsonl(path: str) -> list:
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def init_items() -> None:
    global _ITEMS
    if not _ITEMS:
        _ITEMS = select_items()


# ------------------------------------------------------------------ commands


def health_call() -> dict:
    resp = call(CENSUS_PROMPT, CENSUS_CAP)
    trace, fields, field = trace_of(resp["message"])
    return {"id": "health", "prompt_sha256": prompt_digest(CENSUS_PROMPT),
            "finish_reason": resp["finish_reason"],
            "completion_tokens": resp["completion_tokens"], "wall_s": resp["wall_s"],
            "content": sanitize(resp["message"].get("content"), 80),
            "message_fields": fields, "reasoning_field": field, "trace_chars": len(trace),
            "model_digest": model_digest()}


def do_measure(outdir: str) -> int:
    """Pre-gate rate measurement: two census calls at cap 256 and one full-cap dispatch on
    the calibration prompt (the recognition form of the shallow anchor cell, so the measured
    rate prices the arm that carries the primary contrast)."""
    init_items()
    cells = {c["label"]: c for c in plan_prompts(PLAN_FULL)}
    cal = cells[CALIBRATION_LABEL]
    census = []
    for i in (1, 2):
        resp = call(CENSUS_PROMPT, CENSUS_CAP)
        ct = resp["completion_tokens"] or 0
        census.append({"call": i, "cap": CENSUS_CAP, "completion_tokens": ct,
                       "wall_s": resp["wall_s"],
                       "tok_per_s": round(ct / resp["wall_s"], 3) if resp["wall_s"] else None,
                       "finish_reason": resp["finish_reason"],
                       "content": sanitize(resp["message"].get("content"), 40)})
    resp = call(cal["prompt"], MAX_TOKENS)
    ct = resp["completion_tokens"] or 0
    declared, delivered, _ = declared_pick(resp["message"].get("content") or "",
                                          cal["options"] or [])
    calibration = {"label": CALIBRATION_LABEL, "cap": MAX_TOKENS, "j": cal["j"],
                   "level": cal["level"], "completion_tokens": ct, "wall_s": resp["wall_s"],
                   "tok_per_s": round(ct / resp["wall_s"], 3) if resp["wall_s"] else None,
                   "declared": declared, "gold": cal["gold"],
                   "finish_reason": resp["finish_reason"],
                   "note": ("recognition form of the shallow anchor cell; the plan cell of the "
                            "same label is a within-firing twin of this dispatch")}
    rate = calibration["tok_per_s"] or 0.0
    measure = {"census": census, "calibration": calibration, "rate_tok_per_s": rate,
               "plan_rule": {"rate_full_plan": RATE_FULL_PLAN, "rate_trim_plan": RATE_TRIM_PLAN,
                             "rate_core_plan": RATE_CORE_PLAN,
                             "dispatch_budget_s": DISPATCH_BUDGET_S},
               "selected_panel": plan_selection(rate), "health": health_call()}
    write_json(os.path.join(outdir, "measure.json"), measure)
    print(json.dumps({"rate_tok_per_s": rate, "selected_panel": plan_selection(rate),
                      "calibration_tokens": ct, "calibration_wall_s": resp["wall_s"]}))
    return 0


def do_freeze(outdir: str, panel: str) -> int:
    init_items()
    measure = read_json(os.path.join(outdir, "measure.json"))
    spec = build_gate(panel, measure)
    write_json(os.path.join(outdir, "gate.json"), spec)
    print(json.dumps({"panel": panel, "cells": len(spec["cells"]), "blob": spec["blob"]}))
    return 0


def do_dry_run(plan: str) -> int:
    init_items()
    cells = plan_prompts(PANELS[plan])
    out = []
    for c in cells:
        rec = score_record(c, {"message": {"content": c["gold"]}, "finish_reason": "stop",
                              "completion_tokens": 1, "prompt_tokens": 1, "wall_s": 0.001})
        out.append({"label": c["label"], "arm": c["arm"], "j": c["j"], "gold": c["gold"],
                    "gold_slot": c["gold_slot"], "options": c["options"],
                    "scored_correct_on_gold": rec["correct"],
                    "prompt_sha256": c["prompt_sha256"][:8]})
    print(json.dumps({"panel": plan, "cells": len(cells),
                      "anchor_yesno_digest16": certify_anchor(),
                      "archived_prompt_identity": archived_identity_report(
                          [{"label": c["label"], "arm": c["arm"],
                            "prompt_sha256": c["prompt_sha256"]} for c in cells]),
                      "plan": out}, indent=1, sort_keys=True))
    return 0


def do_run(outdir: str, plan: str) -> int:
    init_items()
    spec = read_json(os.path.join(outdir, "gate.json"))
    if spec["panel_name"] != plan:
        print(f"gate panel {spec['panel_name']} does not match --run {plan}", file=sys.stderr)
        return 2
    cells = plan_prompts(PANELS[plan])
    raw = os.path.join(outdir, "raw.jsonl")
    if os.path.exists(raw):
        print("raw.jsonl already exists; refusing to append to a frozen round", file=sys.stderr)
        return 2
    write_jsonl(raw, [])
    write_json(os.path.join(outdir, "health.json"), health_call())
    blob = spec["blob"]
    started = time.time()
    retries = 0
    aborted_for_form = False
    done: dict = {}
    for idx, cell in enumerate(cells):
        if idx >= CALL_CAP - 4:
            break                                   # protocol call cap, headroom kept
        if idx >= 4 and time.time() - started > DISPATCH_BUDGET_S:
            print(f"dispatch budget reached at cell {idx}", file=sys.stderr)
            break
        form_gate_due = idx >= len(FORM_CELLS) and not done.get("_form_checked")
        if form_gate_due:
            done["_form_checked"] = True
            form_rows = [done.get(l) for l in FORM_CELLS]
            if not all(r and r["delivered"] and r["correct"] for r in form_rows):
                aborted_for_form = True
                print("form gate failed after the four form cells: stopping dispatch",
                      file=sys.stderr)
                break
        resp = None
        error = ""
        for attempt in range(2):
            try:
                resp = call(cell["prompt"], cell["cap"])
                break
            except (urllib.error.URLError, OSError, TimeoutError, KeyError) as exc:
                error = type(exc).__name__
                retries += 1
                if retries > MAX_RETRIES_TOTAL or attempt == 1:
                    break
                time.sleep(20)
        rec = score_record(cell, resp or {}, error)
        rec["dispatch_index"] = idx
        rec["gate_blob"] = blob
        append_jsonl(raw, rec)
        done[cell["label"]] = rec
        print(json.dumps({"i": idx, "label": cell["label"], "declared": rec["declared"],
                          "correct": rec["correct"], "finish": rec["finish_reason"],
                          "tok": rec["completion_tokens"], "wall_s": rec["wall_s"]}),
              flush=True)
    summary = build_summary(read_jsonl(raw), spec, blob, started, retries, aborted_for_form)
    write_json(os.path.join(outdir, "summary.json"), summary)
    print(json.dumps({"tier": summary["tier"], "dispatched": summary["dispatched"],
                      "not_dispatched": summary["not_dispatched"]}))
    return 0


def build_summary(records: list, spec: dict, blob: str, started=None, retries: int = 0,
                  aborted_for_form: bool = False) -> dict:
    ev = evaluate(records, spec)
    if aborted_for_form:
        ev["tier"] = "form_invalid"
        if "aborted_after_form_gate" not in ev["flags"]:
            ev["flags"] = sorted(set(ev["flags"]) | {"aborted_after_form_gate"})
    if started is None:
        # Rescore path: the live wall is gone, and dispatch is sequential, so the sum of the
        # per-record walls is the honest replacement and is labelled as one.
        wall = round(sum(r["wall_s"] or 0.0 for r in records), 1)
        wall_note = "sum of per-record walls (rescore path, sequential dispatch)"
    else:
        wall = round(time.time() - started, 1)
        wall_note = "measured dispatch phase"
    return {"schema": "round64-summary-v1", "gate_blob": blob, "panel": spec["panel_name"],
            "dispatched": len(records), "retries_used": retries,
            "retry_budget": MAX_RETRIES_TOTAL,
            "dispatch_wall_s": wall, "dispatch_wall_basis": wall_note,
            "completion_tokens_total": sum(r["completion_tokens"] or 0 for r in records),
            "prompt_tokens_total": sum(r["prompt_tokens"] or 0 for r in records),
            "rate_gate": spec["rate_measurement"].get("rate_tok_per_s"),
            "aborted_for_form": aborted_for_form, "tier": ev["tier"], "flags": ev["flags"],
            "scorecard": ev["scorecard"], "not_dispatched": ev["not_dispatched"],
            "paired_cells": ev["paired_cells"], "recall_missed_paired": ev["recall_missed_paired"],
            "n_missed": ev["n_missed"], "m_recognised": ev["m_recognised"],
            "binomial_p": ev["binomial_p"], "chance": ev["chance"],
            "cells": [{"label": r["label"], "arm": r["arm"], "j": r["j"], "gold": r["gold"],
                       "declared": r["declared"], "correct": r["correct"],
                       "signature": r.get("signature"),
                       "pick_in_options": r.get("pick_in_options"),
                       "gold_slot": r["gold_slot"], "options": r["options"],
                       "delivered": r["delivered"], "finish_reason": r["finish_reason"],
                       "completion_tokens": r["completion_tokens"], "wall_s": r["wall_s"],
                       "tok_per_s": r["tok_per_s"], "reasoning_field": r["reasoning_field"],
                       "trace_chars": r["trace_chars"]} for r in records]}


def do_rescore(outdir: str) -> int:
    init_items()
    spec = read_json(os.path.join(outdir, "gate.json"))
    records = read_jsonl(os.path.join(outdir, "raw.jsonl"))
    summary = build_summary(records, spec, spec["blob"])
    write_json(os.path.join(outdir, "summary.json"), summary)
    print(json.dumps({"tier": summary["tier"], "dispatched": summary["dispatched"]}))
    return 0


def do_check_scores(outdir: str) -> int:
    init_items()
    spec = read_json(os.path.join(outdir, "gate.json"))
    records = read_jsonl(os.path.join(outdir, "raw.jsonl"))
    summary = build_summary(records, spec, spec["blob"])
    stored = read_json(os.path.join(outdir, "summary.json"))
    bad = []
    for key in ("tier", "flags", "scorecard", "not_dispatched", "n_missed", "m_recognised",
                "binomial_p"):
        if json.dumps(summary.get(key), sort_keys=True) != json.dumps(stored.get(key),
                                                                     sort_keys=True):
            bad.append(key)
    if stored.get("gate_blob") != spec["blob"]:
        bad.append("gate_blob")
    if bad:
        print("check-scores: differs on " + ", ".join(bad))
        return 1
    print("check-scores: identical")
    return 0


def do_check_readme(outdir: str) -> int:
    """Issue #137 guard: the README may only quote gate-row ids this gate defines (criterion
    ids, the theory ids, the health id), every 64-hex blob in it must be this gate's, every
    16-hex digest the certified anchor digest, and every raw record must carry the blob. Item
    keys are only allowed inside a cell label, which is why the id pattern needs word
    boundaries."""
    spec = read_json(os.path.join(outdir, "gate.json"))
    blob = spec["blob"]
    defined = set(spec["criteria"]) | set(spec.get("theory", {})) | {"health"}
    abbrs = {k.split("_")[0] for k in defined} | {"health"}
    certified = {ARCHIVED_K48["yesno_digest16"]}
    with open(os.path.join(outdir, "README.md"), encoding="utf-8") as fh:
        text = fh.read()
    failures = []
    for row_id in sorted(set(re.findall(r"\b([A-Z]\d{1,2})\b", text))):
        if row_id not in abbrs:
            failures.append(f"README quotes undefined gate-row id {row_id}")
    for b in sorted(set(re.findall(r"\b[0-9a-f]{64}\b", text))):
        if b != blob:
            failures.append(f"README cites a 64-hex blob that is not this gate's: {b[:16]}")
    for b in sorted(set(re.findall(r"\b[0-9a-f]{16}\b", text))):
        if b not in certified:
            failures.append(f"README cites a 16-hex digest that is not the certified anchor "
                            f"digest: {b}")
    if blob not in text:
        failures.append("README does not carry the frozen gate blob")
    if "Executed" not in text:
        failures.append("README does not state the evidence label")
    for r in read_jsonl(os.path.join(outdir, "raw.jsonl")):
        if r.get("gate_blob") != blob:
            failures.append(f"raw record {r['label']} carries a different blob")
            break
    for name in sorted(os.listdir(outdir)):
        if name.endswith(".py") or not name.endswith((".json", ".jsonl")):
            continue                              # the script carries the sanitizer fixtures
        path = os.path.join(outdir, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as fh:
            body = fh.read()
        for m in re.finditer(r"https?://\S+|(?<![\d.])\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}",
                             body):
            failures.append(f"{name} carries an endpoint-shaped literal: {m.group(0)[:40]}")
            break
    if failures:
        for f in failures:
            print("FAIL", f)
        return 1
    print("check-readme: clean")
    return 0


# ------------------------------------------------------------------ selftest


def selftest() -> int:
    """Deterministic checks, no endpoint. Every check that could pass vacuously is paired
    with a planted version of the defect it is meant to catch."""
    init_items()
    checks = 0

    def ok(cond, what) -> None:
        nonlocal checks
        checks += 1
        if not cond:
            raise AssertionError(f"selftest: {what}")

    ok(certify_anchor() == ARCHIVED_K48["yesno_digest16"], "anchor yes/no digest")
    ok(certify_anchor() != "0" * 16, "anchor digest is not a placeholder")

    cells = {c["label"]: c for c in plan_prompts(PLAN_FULL)}
    for label, want in ARCHIVED_RECALL_PROMPTS.items():
        ok(cells[label]["prompt_sha256"] == want, f"{label} reproduces the archived prompt")
    ok(cells["A48_j8_R"]["prompt_sha256"] != ARCHIVED_RECALL_PROMPTS["A48_j48_R"],
       "archived digests are distinct (a copy-paste would pass both)")

    # minimal pair: the arms share everything through the task sentence
    for key, j in (("A48", 40), ("C64", 64), ("B40", 16)):
        item = item_for(key)
        src = cell_src(item, "name")
        r = render_recall(item, src, j)
        opts, _ = build_options(item, src, j, terminal_at(item, src, j), f"{key}_x")
        p = render_recog(item, src, j, opts)
        pre = shared_prefix(item, src, j)
        ok(r.startswith(pre) and p.startswith(pre), "shared prefix present in both arms")
        ok(r[len(pre):] == RECALL_CLAUSE.format(j=j), "recall clause is the frozen text")
        ok(p[len(pre):] == RECOG_CLAUSE.format(j=j, opts=", ".join(opts)),
           "recognition clause is the frozen text")
        ok(not r[len(pre):] == p[len(pre):], "the arms differ in the answer clause only")
    planted = render_recall(item_for("A48"), cell_src(item_for("A48"), "name"), 40) + "?"
    ok(planted != cells["A48_j40_R"]["prompt"], "a one-character prompt edit is caught")

    # option integrity, and a planted off-item option is caught
    for lab, c in cells.items():
        if c["arm"] != "P":
            continue
        opts = c["options"]
        vocab = vocab_of(item_for(c["item_key"]))
        ok(len(opts) == 5 and len(set(opts)) == 5, f"{lab}: five distinct options")
        ok(sum(1 for o in opts if o == c["gold"]) == 1, f"{lab}: exactly one gold option")
        ok(all(o == NONE_GOLD or o in vocab for o in opts), f"{lab}: options are in-item")
        ok(c["gold_slot"] == opts.index(c["gold"]), f"{lab}: gold slot recorded")
        bad = list(opts)
        bad[0] = "zzznotaname"
        caught = False
        try:
            for o in bad:
                if o != NONE_GOLD and o not in vocab:
                    raise AssertionError
        except AssertionError:
            caught = True
        ok(caught, f"{lab}: an off-item option would be caught")
    slots = [c["gold_slot"] for c in cells.values() if c["arm"] == "P"]
    ok(len(set(slots)) >= 3, "gold key positions are spread, not constant")
    ok(sum(slots) != len(slots) * 0, "gold is never in slot 0 by construction alone")

    # golds and the independent solver
    for lab, c in cells.items():
        if c["kind"] in ("name", "dup"):
            ok(c["gold"] == terminal_at(item_for(c["item_key"]), c["src"], c["j"]),
               f"{lab}: gold matches the walker")
        else:
            ok(terminal_at(item_for(c["item_key"]), c["src"], c["j"]) is None,
               f"{lab}: dead-end gold is NONE")
    a48 = cells["A48_j40_R"]
    ok(cells["A48_j48_R"]["gold"] != a48["gold"], "different j gives a different gold")
    wrong_solver = terminal_at(item_for("A48"), a48["src"], 40 + 1)
    ok(wrong_solver != a48["gold"], "an off-by-one solver is distinguishable from the gold")

    # signatures
    cell40 = dict(a48)
    ok(recall_signature(cell40, a48["gold"]) == "correct", "gold is filed correct")
    near = terminal_at(item_for("A48"), a48["src"], 39)
    ok(recall_signature(cell40, near) == "near_step_offset", "a one-step error is filed near")
    far = terminal_at(item_for("A48"), a48["src"], 10)
    ok(recall_signature(cell40, far) == "far_on_path", "a distant same-path name is filed far")
    ok(recall_signature(cell40, "qqzz") == "off_item", "an invented name is filed off_item")
    ok(recall_signature(cell40, None) == "no_delivery", "a missing answer is filed no_delivery")
    ok(recall_signature(cell40, NONE_GOLD) == "refusal", "a NONE on a name cell is a refusal")
    other_head = [h for h in heads_of(item_for("A48")) if h != a48["path_head"]][0]
    ok(recall_signature(cell40, other_head) == "other_path_name",
       "a name on the other component is filed separately")
    de = cells["A48_deadend_R"]
    ok(recall_signature(de, NONE_GOLD) == "correct", "NONE on a dead-end cell is correct")
    ok(recall_signature(de, de["src"]) == "clamp_start", "naming the stuck node is a clamp")
    ok(recall_signature(de, terminal_at(item_for("A48"), other_head, 3)) == "other_path_name",
       "a dead-end answer from the other path is filed separately")

    # recognition readout
    pc = cells["A48_j40_P"]
    ok(declared_pick(f"{pc['gold']}", pc["options"]) == (pc["gold"], True, True),
       "a bare gold option is picked")
    ok(declared_pick("I think the answer is trackst",
                     [x for x in pc["options"] if x != "trackst"] + ["trackst"]
                     ) is not None, "sentence-wrapped picks resolve")
    ok(declared_pick("", pc["options"])[1] is False, "an empty field is not a delivery")
    d, deliv, inopt = declared_pick("zorp", pc["options"])
    ok(d is None and deliv and not inopt, "an off-options name is not a pick")
    two = [pc["options"][0], pc["options"][1]]
    ok(declared_pick(f"{two[0]} ... {two[1]}", pc["options"])[0] == two[1],
       "the last mentioned option wins")
    planted_prefix = declared_pick(f"not{two[0]}", [two[0]])
    ok(planted_prefix[0] is None, "a substring inside a longer word is not a pick")

    # statistics: planted negatives around the threshold
    ok(abs(binom_upper(4, 4, 0.2) - 0.0016) < 1e-12, "binomial tail arithmetic")
    ok(binom_upper(6, 1, 0.2) > 0.5, "a single success is not significant")
    ok(binom_upper(5, 4, 0.2) < 0.01, "four of five against 0.2 is significant")
    ok(binom_upper(0, 0, 0.2) == 1.0 and binom_upper(3, 4, 0.2) == 0.0, "tail edge cases")
    ok(binom_upper(4, 3, 0.2) < ALPHA, "three of four is significant at this n")
    ok(binom_upper(5, 3, 0.2) > ALPHA, "three of five is NOT significant at this n")

    # plan selection against the frozen thresholds
    ok(plan_selection(RATE_FULL_PLAN) == "r64", "full at the threshold")
    ok(plan_selection(RATE_FULL_PLAN - 0.1) == "r64trim", "trim just below full")
    ok(plan_selection(RATE_TRIM_PLAN - 0.1) == "r64core", "core just below trim")
    ok(plan_selection(1.0) == "r64core", "starved endpoint keeps the core plan")
    for panel, plan in PANELS.items():
        worst = len(plan) * MAX_TOKENS
        rate = {"r64": RATE_FULL_PLAN, "r64trim": RATE_TRIM_PLAN,
                "r64core": RATE_CORE_PLAN}[panel]
        ok(worst / rate <= DISPATCH_BUDGET_S, f"{panel} worst case fits the dispatch budget")
    ok(len(PLAN_FULL) + 5 <= CALL_CAP, "the full plan plus pre-gate calls fits the call cap")

    # scoring path (the round-61 selftest gap: this is the post-dispatch assembly path)
    spec = build_gate("r64core", {"rate_tok_per_s": 12.0, "selected_panel": "r64core"})
    ok(spec["blob"] == gate_blob({k: v for k, v in spec.items() if k != "blob"}),
       "gate blob is the sha256 of the spec without the blob key")
    planted = dict(spec)
    planted["panel_name"] = "other"
    ok(gate_blob({k: v for k, v in planted.items() if k != "blob"}) != spec["blob"],
       "a one-field gate edit changes the blob")
    core_cells = {c["label"]: c for c in spec["cells"]}
    ok(set(core_cells) == {c[0] for c in PLAN_CORE}, "core panel expands to its cells")
    for c in spec["cells"]:
        ok(c["gold"] == core_cells[c["label"]]["gold"], "gate cells carry the cell gold")

    def fake(cell, declared, finish="stop", tokens=900):
        content = "" if declared is None else declared
        resp = {"message": {"content": content, "reasoning_content": "t" * 50},
                "finish_reason": finish, "completion_tokens": tokens, "prompt_tokens": 100,
                "wall_s": 30.0}
        return score_record(cell, resp)

    recs = []
    for c in plan_prompts(PANELS["r64core"]):
        if c["label"] in FORM_CELLS or c["label"] in BASELINE_CELLS:
            recs.append(fake(c, c["gold"]))
        elif c["arm"] == "R":
            recs.append(fake(c, terminal_at(item_for(c["item_key"]), c["src"], max(c["j"] - 2, 0))
                             if c["kind"] == "name" else NONE_GOLD))
        else:
            recs.append(fake(c, c["gold"]))
    ev = evaluate(recs, spec)
    ok(ev["tier"] in ("readout_failure", "mixed", "representation_failure",
                      "no_dissociation_material"), f"synthetic tier is a dissociation tier: {ev['tier']}")
    recs2 = [dict(r) for r in recs]
    for r in recs2:
        if r["label"] in FORM_CELLS:
            r["correct"] = False
    ok(evaluate(recs2, spec)["tier"] == "form_invalid", "a failed form cell refuses the round")
    recs3 = [r for r in recs if r["label"] not in ("B40_j40_P",)]
    ok(evaluate(recs3, spec)["tier"] == "dispatch_incomplete", "a missing cell is incomplete")
    recs5 = [dict(r) for r in recs]
    for r in recs5:
        if r["label"] == "A48_deadend_R":
            r["correct"] = False
            r["declared"] = "spog"
            r["signature"] = "past_end_same_path"
    ev5 = evaluate(recs5, spec)
    ok(ev5["tier"] == "controls_invalid", "a control that names an entity refuses the firing")
    ok("controls_invalid" in ev5["flags"], "the control failure is flagged, not hidden")
    recs4 = [dict(r) for r in recs]
    for r in recs4:
        if r["arm"] == "R" and r["kind"] == "name" and r["j"] >= 24:
            r["correct"] = True
    ok(evaluate(recs4, spec)["tier"] == "no_dissociation_material",
       "a firing where recall never misses has no dissociation material")
    summary = build_summary(recs, spec, spec["blob"], time.time(), 0, False)
    ok(set(summary["scorecard"]) == set(spec["criteria"]),
       "the scorecard reports exactly the frozen rows")
    ok(summary["cells"], "summary assembly produced the per-cell rows")
    ok(all(k in summary for k in ("tier", "not_dispatched", "n_missed", "m_recognised")),
       "summary carries the assembly fields (round-61 selftest gap)")
    rescored = build_summary(recs, spec, spec["blob"])
    ok(rescored["tier"] == summary["tier"], "the rescore path preserves the tier")
    ok("rescore" in rescored["dispatch_wall_basis"], "the rescore wall basis is labelled")
    ok(abs(rescored["dispatch_wall_s"] - sum(r["wall_s"] for r in recs)) < 0.001,
       "the rescore wall is the sum of record walls, not a zero (round-64 defect)")

    # census merge rule, planted both channels
    a, f, src_f = trace_of({"role": "assistant", "content": "x", "reasoning_content": "abc",
                            "reasoning": "zz"})
    ok(a == "abc" and src_f == "reasoning_content", "reasoning_content wins when non-empty")
    a, f, src_f = trace_of({"role": "assistant", "content": "x", "reasoning_content": "",
                            "reasoning": "zz"})
    ok(a == "zz" and src_f == "reasoning", "reasoning is the fallback")
    a, f, src_f = trace_of({"role": "assistant", "content": "x"})
    ok(a == "" and src_f == "", "no trace is an empty field, not a missing one")

    # sanitizer: RFC 5737 documentation addresses, an .invalid domain and a dummy path only
    dirty = ("see https://example.invalid/x at 198.51.100.7 and 192.0.2.1:8080 and "
             "/root/scratch/weights.bin, also 127.0.0.1")
    clean = sanitize(dirty)
    ok("http" not in clean and "198.51.100.7" not in clean and "/root/" not in clean,
       "sanitizer strips urls, addresses and paths")
    ok("127.0.0.1" not in clean and "192.0.2.1" not in clean,
       "sanitizer strips loopback and documentation addresses alike")
    ok("[redacted]" in clean, "sanitizer leaves a marker")
    ok(sanitize(None) == "", "sanitizer tolerates None")
    ok(len(sanitize("x" * 5000)) == 1200, "sanitizer caps length")

    # row-and-blob guard fixtures
    tmp = os.path.join(_HERE, "_selftest_guard")
    os.makedirs(tmp, exist_ok=True)
    write_json(os.path.join(tmp, "gate.json"), spec)
    write_jsonl(os.path.join(tmp, "raw.jsonl"),
                [dict(r, gate_blob=spec["blob"]) for r in recs])
    good = (f"blob {spec['blob']} and rows F1, D1, T1 and the k = 48 anchor item "
            f"{ARCHIVED_K48['yesno_digest16']} plus the label A48_j40_R\nExecuted\n")
    with open(os.path.join(tmp, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(good)
    ok(do_check_readme(tmp) == 0, "guard passes a clean README")
    for bad_text, what in (
            (good.replace("A48_j40_R", " A48 "), "a bare item key outside a cell label"),
            (good.replace("F1", "F7"), "an undefined gate-row id"),
            (good.replace(spec["blob"], "0" * 64), "a foreign 64-hex blob"),
            (good.replace("Executed", "Validated"), "a missing evidence label")):
        with open(os.path.join(tmp, "README.md"), "w", encoding="utf-8") as fh:
            fh.write(bad_text)
        ok(do_check_readme(tmp) == 1, f"guard catches {what}")
    with open(os.path.join(tmp, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(good)
    write_jsonl(os.path.join(tmp, "raw.jsonl"),
                [dict(recs[0], gate_blob="f" * 64)] + recs[1:])
    ok(do_check_readme(tmp) == 1, "guard catches a raw record with a different blob")
    write_jsonl(os.path.join(tmp, "raw.jsonl"),
                [dict(r, gate_blob=spec["blob"]) for r in recs])
    with open(os.path.join(tmp, "notes.jsonl"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"x": "on http://198.51.100.9:8080/v1"}) + "\n")
    ok(do_check_readme(tmp) == 1, "guard catches an endpoint literal in a round artifact")
    os.remove(os.path.join(tmp, "notes.jsonl"))
    ok(do_check_readme(tmp) == 0, "guard is clean again after removing the artifact")
    for name in os.listdir(tmp):
        os.remove(os.path.join(tmp, name))
    os.rmdir(tmp)

    print(f"selftest: {checks} checks green")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--measure", action="store_true")
    p.add_argument("--freeze", action="store_true")
    p.add_argument("--run", action="store_true")
    p.add_argument("--rescore", action="store_true")
    p.add_argument("--check-scores", action="store_true")
    p.add_argument("--check-readme", action="store_true")
    p.add_argument("--panel", default=None, choices=sorted(PANELS))
    p.add_argument("--outdir", default=_HERE)
    args = p.parse_args(argv[1:])

    if args.selftest:
        return selftest()
    if args.dry_run:
        return do_dry_run(args.panel or "r64")
    if args.measure:
        return do_measure(args.outdir)
    if args.freeze:
        if not args.panel:
            print("--freeze needs --panel", file=sys.stderr)
            return 2
        return do_freeze(args.outdir, args.panel)
    if args.run:
        if not args.panel:
            print("--run needs --panel", file=sys.stderr)
            return 2
        return do_run(args.outdir, args.panel)
    if args.rescore:
        return do_rescore(args.outdir)
    if args.check_scores:
        return do_check_scores(args.outdir)
    if args.check_readme:
        return do_check_readme(args.outdir)
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

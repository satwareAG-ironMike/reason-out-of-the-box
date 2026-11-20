#!/usr/bin/env python3
"""Round 77 (2026-11-20 04:00): does the own-content readout survive when the arms are
token-matched on the endpoint's measured prompt_tokens?

Question. Round 75 (this 27B-class build, fifth public firing on its serving id string)
ran the issue #152 foreign-scaffold arm C and shipped the primary verdict own_content_selects
(arm X 3 of 3, arm C 0 of 3, arm F 0 of 3) with the context-length claim downgraded to
context_length_unmatched: the notes arms were matched on whitespace tokens, not on the
endpoint's tokenization, so arm X added a constant 2,057 measured prompt tokens over arm B
while arm F added only 776 to 950 and the P1 band of 400 failed on every armed cell. The
round-75 "Next" item and issue #152 register the debt: match the arms on measured
prompt_tokens with a tokenization-aware filler/donor budget. This round runs the same
four-arm panel with that fix, on the three M4 items whose turn-1 prompts are byte-identical
to the round-63/69/70/72/73/75 dispatches:

  arm X  the assistant turn carries the turn-1 answer field PLUS the item's own turn-1
         non-report channel under the fixed notes label (the own draft);
  arm C  the assistant turn carries the turn-1 answer field PLUS a draft of a DIFFERENT
         item, used WHOLE and uncut under the same label (a donor chosen for prompt-token
         parity by taking the donor's cap-censored draft whole, instead of cutting it to a
         whitespace-token budget; donor map frozen in the gate);
  arm F  the assistant turn carries the turn-1 answer field PLUS a tokenization-aware
         filler: the block starts at the draft's whitespace-token budget and is tuned, by
         at most two registered probes at cap 1 that read the endpoint's own measured
         prompt_tokens, to sit within the P1 band of arm X's measured prompt_tokens;
  arm B  the assistant turn carries the turn-1 answer field only.

The per-cell dispatch order is X, C, B, then the F probes and the F scoring dispatch, so
the tuner sees arm X's and arm B's measured prompt_tokens before it places the filler.
Row P1 keeps the round-75 band (400 tokens of spread across the measured prompt_tokens of
X, C and F, all above arm B's) and ships the context-length claim only while it holds:
if the tuned arms still fail the band, the claim ships downgraded again, which is the
registered outcome, not a failure of the round. Scoring is against the generator's
independent solver on the visible answer field, never on trace text (issue #94).

Registered rows, frozen in gate.json before any prompt; every row is a key of the frozen
gate (issue #137 shape):

  V0_trace_exposure   the deployment must hand back a non-report channel at the pre-gate
                      census; without it arms X and C cannot be built and row C2 is refused.
  V1_solver_certified the independent solver agrees with the path walk at j = 0, 1, mid,
                      level and returns None one step past the tail; every item is a
                      load-floor (facts = 2 * level), component-isomorphic two-chain item;
                      the interior gold is asserted distinct from the terminal and the
                      start; the filler token is asserted outside every item vocabulary;
                      and for each interior cell the asked interior gold is asserted absent
                      from the donor item's vocabulary (the item vocabularies are NOT
                      pairwise disjoint; the asserted property is the narrower gold-leak
                      one, recorded per donor pair), so a whole donor draft can never
                      contain the asked gold.
  V2_control_liveness the past-the-tail control declares NONE at turn 1 (issue #139 shape).
  V3_anchor           the shallow j = 8 anchor cell delivers the correct terminal (liveness).
  C2_foreign_draft    PRIMARY, carried from round 75. Over the terminal cells whose turn-1
                      draft contains the interior gold (the registered evaluable scope,
                      minimum 2): n_X correct with the own draft, n_C with the whole
                      foreign draft. scaffold_carries when n_C >= 1 and n_C >= n_X - 1;
                      own_content_selects when n_X >= 2 and n_X - n_C >= 2; no_recovery
                      when n_X = 0 and n_C = 0; ambiguous otherwise. Exact two-sided
                      binomial over the X-vs-C discordant pairs, exploratory, n is single
                      digits, no significance claim.
  R2_cross_ask        carried from round 72: the X-vs-F comparison with its decision
                      ladder, so this round's F arm stays comparable across firings. On
                      this firing the F arm is the tokenized filler, so R2 is the
                      token-matched reading of round 72's row.
  X2_tail_shortcut    companion downgrade rule for arm X: if every delivered arm-X record
                      emitted the own draft's last vocabulary name, the reading is
                      tail_copy; on the interior ask a tail copy is a wrong answer, so the
                      downgrade and a correct recovery are mutually exclusive. The foreign
                      analogue is the census answer_is_foreign_tail on delivered arm-C
                      records (the last vocabulary name of the restored whole donor
                      block; a foreign-tail copy is a wrong answer by construction and is
                      never scored as a recovery).
  F1_filler_token_match  the arm-F notes block is tuned to measured prompt_tokens parity
                      with arm X within the P1 band: probe 1 at the draft's whitespace
                      budget n0 (cap 1), and if out of band one registered rescale
                      n1 = round(n0 * (pt_X - pt_B) / (pt_F@n0 - pt_B)) (2 * n0 when the
                      measured increment is not positive), probed once, cap 1. At most
                      two probes per armed cell; the realized counts and probe lengths
                      are recorded per record (fields filler_tokens, filler_probe_lengths).
  P1_prompt_tokens_parity  every arm user turn is the FULL turn-1 prompt, so the four
                      arms differ only in the notes block; per armed cell the measured
                      endpoint prompt_tokens of X, C and F spread by at most 400 tokens
                      and all three exceed arm B's while the context-length claim in the
                      README ships; violation ships it downgraded to
                      context_length_unmatched (the round-75 reading, registered as the
                      fallback outcome).
  H1_answer_stability over the terminal cells whose turn-1 answer WAS the terminal gold:
                      how often each arm still reports the interior step correctly (the
                      arm-damages-a-right-answer side, issue #152 item 3).
  C1_name_pressure    the NONE-gold control under all four arms: a name where the links
                      ran out is a manufactured name, and any false name caps the C2
                      reading.
  S1_delivery_census  every turn-1 and arm record (F probes excluded: they are
                      instrument measurements, not dispatches of the panel) classified
                      into the issue #145 delivery states.
  W2_wall_shape       every scored record fitted against the three archived wall laws
                      (the 1,556 to 1,558 self-stop band, a reserve of exactly 492, a
                      reserve at or below 19).
  M4_matched_pair     three turn-1 cells are byte-identical to the round-63, round-69,
                      round-70, round-72, round-73 and round-75 dispatches; the prompt
                      digests are asserted in --selftest, so "same items, same prompts,
                      different firing" is machine-checked.

Contracts: stdlib only; reads NIGHTLY_BASE_URL, NIGHTLY_MODEL_ID, NIGHTLY_API_KEY from the
environment and writes none of them; at most 40 prompts; max_tokens <= 2048 (the F probes
run at cap 1); sequential dispatch one cell at a time (issue #73); the sanitizer redacts
host, IP, path and serving-id classes (issue #85) from anything the model answers, and
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
F_PROBE_CAP = 1               # the F tuner probes read prompt_tokens, they generate one token
F_PROBE_MAX_PER_CELL = 2      # registered probe budget: probe 1 at n0, probe 2 at the rescale
CALL_CAP = 40
TIMEOUT_S = 900
DISPATCH_BUDGET_S = 2100
CELL_FLOOR_S = 90
MAX_RETRIES_TOTAL = 3
NONE_GOLD = "NONE"
GATE_SCHEMA = "round77-gate-v1"
CENSUS_CAP = 256
NOTES_LABEL = "[working notes from the previous answer]"
J_INT = 40                    # the interior ask step; interior on all three paths (48, 50, 64)
FILLER_TOKEN = "fill"         # the tokenization-aware filler token; asserted outside every vocabulary
P1_TOKEN_BAND = 400           # P1: max spread across the measured prompt_tokens of arms X, C, F

ARCHIVED_K48 = {"seed": 116261051, "yesno_digest16": "068bc6a1fb0620fb"}

# The matched pair: prompt digests frozen by the round-63 gate (PR #143, unmerged) and
# dispatched by rounds 69, 70, 72, 73 and 75. Three of this round's turn-1 cells use the
# identical item, depth and template, so --selftest can assert that the only variable
# against those firings is the firing itself (same serving id string, fifth public firing).
MATCHED_PAIR = {
    "record": ("round-63 gate cells (PR #143, unmerged here), re-dispatched by rounds "
               "69, 70, 72, 73 and 75"),
    "prompt_sha256": {
        "A48_j48": "baabc3462652878fdbdca1994faa18240e917b5f0fea69fd786d34e56526c4c9",
        "B50_j50": "c15a68eb63cc474457ebe6f8ee806f6e0182d38967bfdbe67726417c272e5362",
        "C64_j64": "c1ef6c20bfd84e2fd30a6eaefa22caf1dfb4663280b0824cac72e89f298eea7e",
    },
}

# Foreign-draft donor map (row C2), frozen in the round-75 gate and carried unchanged: the
# item whose turn-1 draft is restored under the notes label when asking an interior step
# of the other item. Round robin over the three M4 items so every draft is donated exactly
# once on a name cell; the control (item C64) takes the same donor as C64_j64.
FOREIGN_MAP = {"A48": "B50", "B50": "C64", "C64": "A48"}

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

# (label, item key, j, kind). kind "name" asks for the terminal node, "over_end" asks past the
# tail so the gold is NONE. The three name cells are the round-63/69/70/72/73/75 byte-identical
# M4 pins; every arm derived from them asks the interior step J_INT instead of the cell's own j.
PLAN_R77 = [
    ("A48_j48", "A48", 48, "name"),
    ("B50_j50", "B50", 50, "name"),
    ("C64_j64", "C64", 64, "name"),
    ("C64_over", "C64", 72, "over_end"),
    ("A48_j8", "A48", 8, "name"),
]
ARMS = ("X", "C", "F", "B")
ARM_DISPATCH_ORDER = ("X", "C", "B", "F")   # F is last: its tuner needs X's and B's measured pt
ANCHOR_CELL = "A48_j8"
CONTROL_CELLS = ("C64_over",)
INTERIOR_CELLS = ("A48_j48", "B50_j50", "C64_j64")
ARMED_CELLS = INTERIOR_CELLS + CONTROL_CELLS
PREGATE_CALLS = 2             # the exposure census call plus the calibration dispatch
ARM_CALLS = 4 * len(ARMED_CELLS)
F_PROBE_CALLS = F_PROBE_MAX_PER_CELL * len(ARMED_CELLS)


def plan_records() -> list:
    out = []
    for label, key, j, kind in PLAN_R77:
        item = item_for(key)
        src = item["query"][0]
        gold = terminal_at(item, src, j)
        gold = NONE_GOLD if gold is None else gold
        assert (gold == NONE_GOLD) == (kind == "over_end"), (label, gold, kind)
        nodes = path_nodes(item, src)
        cap = MAX_TOKENS
        interior_gold = terminal_at(item, src, J_INT) if kind == "name" else None
        out.append({"label": label, "arm": "t1", "cell": label, "kind": kind,
                    "item_key": key, "level": item["level"], "seed": item["seed"],
                    "src": src, "j": j, "cap": cap, "gold": gold,
                    "interior_gold": interior_gold,
                    "prompt": render_name(item, src, j), "n_facts": len(item["facts"]),
                    "path_len": len(nodes) - 1, "on_path": nodes,
                    "prompt_sha256": prompt_digest(render_name(item, src, j))})
    return out


def filler_block(n: int) -> str:
    """The arm-F notes block: n repetitions of the neutral filler token. The length is the
    tuned quantity; the shared structural label is present in all notes arms and cancels
    in the comparison."""
    return " ".join([FILLER_TOKEN] * max(n, 0))


def foreign_block(donor_trace: str) -> tuple:
    """The arm-C notes block: a DIFFERENT item's draft used WHOLE, uncut (the round-77
    tokenization-aware change: round 75 cut it to the item's own draft whitespace-token
    budget, and the cut is exactly what broke the measured parity). A missing donor draft
    is an empty block; the realized count is the recorded field foreign_tokens. The donor
    item's vocabulary is asserted in --selftest to exclude the asked interior gold
    (the narrower gold-leak property), so the block can never contain the asked gold."""
    block = (donor_trace or "").strip()
    return (block, len(block.split()) if block else 0)


def tune_filler(n0: int, pt_x, pt_b, pt_f0) -> tuple:
    """The registered single rescale step (row F1). pt_x, pt_b, pt_f0 are the endpoint's
    measured prompt_tokens for arm X, arm B and the F probe at n0. In band (within P1 of
    arm X, above arm B): keep n0, one probe used. Out of band: rescale by the measured
    increment ratio and probe once (two probes used). A non-positive measured probe
    increment falls back to 2 * n0; a missing measurement keeps n0 (one probe used),
    since there is no target to place the filler against. The band check then decides,
    and a failure ships the context-length claim downgraded, which is the registered
    outcome."""
    if pt_x is not None and pt_b is not None and pt_f0 is not None:
        if pt_f0 > pt_b and abs(pt_f0 - pt_x) <= P1_TOKEN_BAND:
            return max(n0, 0), 1
        if pt_f0 > pt_b and n0 > 0:
            n1 = round(n0 * (pt_x - pt_b) / (pt_f0 - pt_b))
            return max(1, n1), 2
        return max(2 * max(n0, 0), 1), 2
    return max(n0, 0), 1


def arm_records(t1: dict, drafts: dict, filler_n: int = 0) -> list:
    """The four follow-ups derived from one turn-1 record. The user turn is the FULL turn-1
    prompt (the 2026-11-18 pr-review fix: rounds 72/73 built the arms from the archived
    900-character copy), so the four arms differ only in the notes block of the assistant
    turn. Arm X restores the item's own non-report channel, arm C restores the WHOLE draft
    of the donor item (FOREIGN_MAP), arm F restores a filler of the tuned length, arm B
    keeps the answer field only. The cue, the cap and every shared byte are identical.
    filler_n is the arm-F length in effect (the n0 start before the probes, the final
    tuned length at the scoring dispatch)."""
    item = item_for(t1["item_key"])
    vocab = vocab_of(item)
    j_ask = J_INT if t1["kind"] == "name" else t1["j"]
    gold = terminal_at(item, t1["src"], J_INT) if t1["kind"] == "name" else NONE_GOLD
    cue = render_followup(t1["src"], j_ask)
    own_draft = t1["trace"]
    donor_key = FOREIGN_MAP[t1["item_key"]]
    donor_draft = (drafts or {}).get(donor_key, "")
    donor_vocab = vocab_of(item_for(donor_key))
    out = []
    for arm in ARMS:
        msgs = [{"role": "user", "content": t1["prompt"]}]
        assistant = t1["content_visible"]
        notes = {"filler_tokens": 0, "foreign_tokens": 0,
                 "draft_vocab_tail": None, "foreign_vocab_tail": None,
                 "donor_item": donor_key if arm == "C" else None}
        if arm == "X":
            assistant = f"{assistant}\n\n{NOTES_LABEL}\n{own_draft}"
            notes["draft_vocab_tail"] = last_vocab_name(own_draft, vocab)
        elif arm == "C":
            block, n = foreign_block(donor_draft)
            assistant = f"{assistant}\n\n{NOTES_LABEL}\n{block}"
            notes["foreign_tokens"] = n
            # the tail detector on the foreign block: the last name in the restored block
            # that belongs to the DONOR item's vocabulary (the block's own tail object)
            notes["foreign_vocab_tail"] = last_vocab_name(block, donor_vocab)
            # belt-and-suspenders gold-leak census: does the delivered whole foreign block
            # contain the asked gold? The selftest asserts the interior gold is absent from
            # the donor vocabulary, so this must stay False; a True here flags a
            # contaminated recovery.
            notes["foreign_block_contains_gold"] = (gold != NONE_GOLD
                                                    and gold.lower() in block.lower())
        elif arm == "F":
            block = filler_block(filler_n)
            assistant = f"{assistant}\n\n{NOTES_LABEL}\n{block}"
            notes["filler_tokens"] = filler_n
        msgs.append({"role": "assistant", "content": assistant})
        msgs.append({"role": "user", "content": cue})
        out.append({"label": f"{t1['label']}_{arm}", "arm": arm, "cell": t1["cell"],
                    "kind": t1["kind"], "item_key": t1["item_key"], "level": t1["level"],
                    "seed": t1["seed"], "src": t1["src"], "j": j_ask, "cap": ARM_CAP,
                    "gold": gold, "prompt": cue, "messages": msgs,
                    "on_path": t1.get("on_path", []),
                    "vocab": sorted(vocab),
                    "donor_item": notes["donor_item"],
                    "filler_tokens": notes["filler_tokens"],
                    "foreign_tokens": notes["foreign_tokens"],
                    "draft_vocab_tail": notes["draft_vocab_tail"],
                    "foreign_vocab_tail": notes["foreign_vocab_tail"],
                    "foreign_block_contains_gold": notes.get(
                        "foreign_block_contains_gold", False),
                    # the pin covers the whole treatment: the full-prompt user turn, the
                    # notes block and the cue
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
    interior_gold = spec.get("interior_gold")
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
        "interior_gold_in_trace": (interior_gold in (trace or "").lower()
                                    if interior_gold is not None else None),
        "trace_vocab_tail": last_vocab_name(trace, vocab),
    })
    if rec["completion_tokens"] is not None:
        rec["reserve"] = spec["cap"] - rec["completion_tokens"]
    rec["wall_laws"] = wall_laws_fit(rec)
    rec["delivery_state"] = delivery_state(rec)
    if rec["arm"] in ("A", "X"):
        rec["answer_is_notes_tail"] = (ans is not None and ans == rec["trace_vocab_tail"])
    if rec["arm"] == "X":
        # the registered tail-copy detector on the interior ask: the treatment-side quantity,
        # the last vocabulary name of the restored own draft, not of the response's own channel
        rec["answer_is_draft_tail"] = (ans is not None
                                       and spec.get("draft_vocab_tail") is not None
                                       and ans == spec["draft_vocab_tail"])
    if rec["arm"] == "C":
        # the foreign analogue: the last vocabulary name of the restored whole donor block.
        # A foreign-tail copy is a wrong answer by construction (gold-leak precondition)
        # and is a census, never a recovery.
        rec["answer_is_foreign_tail"] = (ans is not None
                                         and spec.get("foreign_vocab_tail") is not None
                                         and ans == spec["foreign_vocab_tail"])
    rec["prompt"] = sanitize(spec["prompt"], limit=900)
    rec["prompt_sha256"] = spec.get("prompt_sha256") or prompt_digest(spec["prompt"])
    return rec


# ------------------------------------------------------------------ gate


def gate_spec(records: list, theory: dict) -> dict:
    return {
        "schema": GATE_SCHEMA,
        "round": 77,
        "firing": "2026-11-20 04:00",
        "slot": "6/6",
        "model_digest": model_digest(),
        "question": ("does the round-75 own-content readout (own draft 3 of 3 against a "
                      "foreign draft 0 of 3 and a whitespace-budget filler 0 of 3) "
                      "survive when the arms are matched on the endpoint's measured "
                      "prompt_tokens: the registered P1 debt, a tokenization-aware "
                      "filler/donor budget"),
        "arms": {"X": "turn-1 answer field plus the item's own turn-1 non-report channel under "
                       "the notes label in the assistant turn (the own draft)",
                 "C": "turn-1 answer field plus a draft of a DIFFERENT item, used WHOLE and "
                       "uncut under the same label (a donor chosen for prompt-token parity "
                       "by taking the donor's cap-censored draft whole, instead of the "
                       "round-75 whitespace-token cut; donor map frozen below)",
                 "F": "turn-1 answer field plus a tokenization-aware filler under the same "
                      "label: the block starts at the draft's whitespace-token budget and is "
                      "tuned by at most two registered probes at cap 1 to sit within the "
                      "P1 band of arm X's measured prompt_tokens",
                 "B": "turn-1 answer field only in the assistant turn"},
        "arm_dispatch_order": list(ARM_DISPATCH_ORDER),
        "f_probe_cap": F_PROBE_CAP,
        "f_probe_max_per_cell": F_PROBE_MAX_PER_CELL,
        "scoring": ("visible answer field against the generator's independent solver; the trace "
                    "is a treatment and a count census, never a scorer (issue #94)"),
        "foreign_map": dict(FOREIGN_MAP),
        "decision_C2": {
            "evaluable_scope": ("the terminal cells whose turn-1 draft contains the interior "
                                "gold, census field interior_gold_in_trace, registered here "
                                "before any prompt"),
            "min_drafts_with_gold": 2,
            "scaffold_carries": "n_C >= 1 and n_C >= n_X - 1 (the foreign scaffold does the "
                                "work at parity: a name-scaffold lookup posture)",
            "own_content_selects": "n_X >= 2 and n_X - n_C >= 2 (the item's own draft "
                                   "outperforms the foreign scaffold by two or more: "
                                   "content-specific recovery)",
            "no_recovery": "n_X == 0 and n_C == 0",
            "ambiguous": "otherwise",
            "statistics": ("exact two-sided binomial over the X-vs-C discordant pairs across "
                           "the items, exploratory, n single digits, no significance claim"),
        },
        "decision_R2": {
            "evaluable_scope": ("the terminal cells whose turn-1 draft contains the interior "
                                "gold, census field interior_gold_in_trace, registered here "
                                "before any prompt"),
            "min_drafts_with_gold": 2,
            "cross_ask_gated": "n_X >= 2 and n_X - n_F >= 2",
            "filler_matches_budget": "n_F >= n_X - 1 and n_F >= 1",
            "tail_copy_downgrade": ("n_X == 0 and every delivered arm-X record on the scope "
                                    "emitted the draft's last vocabulary name"),
            "no_recovery": "n_X == 0 and no arm-X record on the scope was delivered",
            "ambiguous": "|n_X - n_F| <= 1 and n_X < 2",
            "statistics": ("exact two-sided binomial over the X-vs-F discordant pairs across "
                           "the three items, exploratory, n single digits, no significance "
                           "claim"),
        },
        "F1_filler_token_match": ("the arm-F notes block is tuned to the endpoint's measured "
                                  "prompt_tokens: probe 1 at the draft's whitespace-token "
                                  "budget n0 (cap 1), and out of band one registered rescale "
                                  "n1 = round(n0 * (pt_X - pt_B) / (pt_F@n0 - pt_B)) (2 * n0 "
                                  "when the measured increment is not positive), probed "
                                  "once; at most two probes per armed cell; the realized "
                                  "counts and probe lengths are recorded per record (fields "
                                  "filler_tokens, filler_probe_lengths)"),
        "P1_prompt_tokens_parity": ("every arm user turn is the FULL turn-1 prompt, so the "
                                    "four arms differ only in the notes block; per armed "
                                    "cell the measured endpoint prompt_tokens of X, C and F "
                                    "spread by at most " + str(P1_TOKEN_BAND)
                                    + " tokens and all three exceed arm B's while the "
                                      "context-length claim in the README ships; violation "
                                      "ships it downgraded to context_length_unmatched "
                                      "(the round-75 reading, registered as the fallback "
                                      "outcome)"),
        "V0_precondition": ("the deployment must hand back a non-report channel at the "
                            "pre-gate census; without it arms X and C cannot be built and "
                            "row C2 is refused, not trusted (issue #105)"),
        "V1_solver_certified": ("the independent solver agrees with the path walk at j = "
                                "0, 1, mid, level and returns None one step past the tail; "
                                "every item is a load-floor (facts = 2 * level), "
                                "component-isomorphic two-chain item; the interior gold is "
                                "asserted distinct from the terminal and the start; the "
                                "filler token is asserted outside every vocabulary; for "
                                "each interior cell the asked interior gold is asserted "
                                "absent from the donor item's vocabulary, so a whole donor "
                                "draft can never contain the asked gold (the item "
                                "vocabularies are not pairwise disjoint; the asserted "
                                "property is the narrower gold-leak one, recorded per "
                                "donor pair)"),
        "V2_control_liveness": ("the past-the-tail control declares NONE at turn 1 "
                                "(issue #139 shape)"),
        "V3_anchor": "the shallow j = 8 anchor cell delivers the correct terminal (liveness)",
        "X2_tail_shortcut": ("if every delivered arm-X record on the scope emitted the own "
                             "draft's last vocabulary name, the reading is tail_copy, not "
                             "selection; on the interior ask a tail copy is a wrong answer, "
                             "so the downgrade and a correct recovery are mutually "
                             "exclusive. The foreign analogue on arm C is a census (field "
                             "answer_is_foreign_tail): a foreign-tail copy is a wrong "
                             "answer by construction"),
        "H1_answer_stability": ("over the terminal cells whose turn-1 answer WAS the "
                                "terminal gold: how often each arm still reports the "
                                "interior step correctly (the arm-damages-a-right-answer "
                                "side, issue #152 item 3)"),
        "controls_C1": ("a name emitted where the links ran out is a manufactured name; "
                        "the NONE-gold control runs under all four arms, drafts included, "
                        "and any false name caps the C2 reading"),
        "caps": {"max_prompts": CALL_CAP, "max_tokens": MAX_TOKENS,
                 "dispatch_budget_s": DISPATCH_BUDGET_S,
                 "planned_calls": len(records), "pre_gate_calls": PREGATE_CALLS,
                 "arm_calls": ARM_CALLS, "f_probe_calls": F_PROBE_CALLS,
                 "f_probe_cap": F_PROBE_CAP},
        "matched_pair": MATCHED_PAIR,
        "wall_laws": WALL_LAWS,
        "delivery_states": list(DELIVERY_STATES),
        "cells": [{"label": r["label"], "arm": r["arm"], "j": r["j"], "gold": r["gold"],
                   "kind": r["kind"], "level": r["level"], "seed": r["seed"],
                   "prompt_sha256": r["prompt_sha256"]} for r in records],
        "theory_rows": theory,
    }


DEFAULT_THEORY = {
    "T1_verbal_report_bibliographic": {
        "source": "Ericsson & Simon 1980, Psychological Review 87(3):215-255, "
                  "DOI 10.1037/0033-295X.87.3.215",
        "statement": ("used only as the bibliographic anchor for the frame that a verbal "
                      "report is a retrieval from a prior store rather than a special "
                      "introspective faculty. The thesis wording itself was NOT read "
                      "this session and is carried as owed"),
        "verification": ("record level, Crossref work record fetched 2026-11-17 in the "
                         "round-72 gate (PR #153); no abstract, so no content claim from "
                         "this row"),
    },
    "T2_reports_as_causal_theory": {
        "source": "Nisbett & Wilson 1977, Psychological Review 84(3):231-259, "
                  "DOI 10.1037/0033-295X.84.3.231",
        "statement": ("a fluent report can be produced by implicit causal theory instead "
                      "of by access to the process, so an arm recovering a name is not by "
                      "itself access. Content carried as owed at the same level"),
        "verification": ("record level, Crossref work record fetched 2026-11-17 in the "
                         "round-72 gate (PR #153), with the round-72 title/venue "
                         "correction on record"),
    },
    "T3_accessibility": {
        "source": "Block 2007, Behavioral and Brain Sciences 30:481-499, "
                  "DOI 10.1017/S0140525X07002786",
        "statement": ("the row R1 operationalizes availability-for-report versus report; "
                      "the article takes accessibility as its object of analysis. No "
                      "argument content is claimed from this row"),
        "verification": ("record level, Crossref work record fetched 2026-11-17 in the "
                         "round-72 gate (PR #153). Caveat on record: citation databases "
                         "circulate a second DOI suffix for this article and the "
                         "alternative was not cross-checked"),
    },
    "T4_verbalizable_workspace": {
        "source": "arXiv:2607.15495 v1, 2026-07-16 (Gurnee, Sofroniew, Pearce, and "
                  "co-authors, 16; Lindsey corresponding group), unrefereed preprint",
        "statement": ("title 'Verbalizable Representations Form a Global Workspace in "
                      "Language Models'; the abstract reports a set of representations "
                      "the model is poised to verbalize whose contents can be reported "
                      "and are used to carry the intermediate steps of silent reasoning "
                      "(quote, 9 words), and it introduces training that changes only "
                      "what a model would say if interrupted and asked to reflect"),
        "verification": "arXiv export API, abstract level; fetched 2026-11-17 in round 72, refetched 2026-11-19 in round 75",
    },
    "T5_introspection_gap": {
        "source": "arXiv:2601.01828 v1, 2026-01-05 (Lindsey), unrefereed preprint",
        "statement": ("injecting known concepts into activations and reading the self-"
                      "report separates grounded report from confabulation; the abstract "
                      "reports the capacity is highly unreliable and context-dependent "
                      "(quote, 5 words)"),
        "verification": ("record level via the archived [FT] entry "
                         "archive/round8-do-llms-think/2601.01828-lindsey-introspective-"
                         "awareness.md (provenance arXiv); the base-model versus "
                         "post-trained asymmetry is NOT in the abstract and is not "
                         "claimed here"),
    },
    "T6_trace_answer_dissociation": {
        "source": "arXiv:2605.29087 v1, 2026-05-27, unrefereed preprint",
        "statement": ("paper title 'The Chain Holds, the Answer Folds: Trace-Answer "
                      "Dissociation in Reasoning Models Under Adversarial Pressure'; "
                      "the abstract reports the chain staying correct while the emitted "
                      "answer flips, a latent-correct rate near 50 percent at the "
                      "behavioral flip in think mode against 11 to 15 percent without a "
                      "thinking channel, and that a naive trace-anchored defense "
                      "backfired (the abstract says backfires). That last clause is the "
                      "registered prior against arms X and C: restoring the channel is "
                      "not assumed to help"),
        "verification": "arXiv export API, abstract level; fetched 2026-11-17 in round 72, refetched 2026-11-19 in round 75",
    },
}


# ------------------------------------------------------------------ scoring


def binom_two_sided(n: int, k: float):
    """Exact two-sided binomial: P(binom(n, 1/2) >= max(k, n - k))."""
    if n <= 0 or k <= 0:
        return None
    hi = int(max(k, n - k))
    return round(min(1.0, 2.0 * sum(math.comb(n, i) for i in range(hi, n + 1))
                     / (2.0 ** n)), 4)


def score(records: list, gate: dict) -> dict:
    # F probes are instrument measurements (cap 1), not panel dispatches: they carry
    # prompt_tokens for the tuner but are excluded from every scored row and census
    core = [r for r in records if r["arm"] != "Fprobe"]
    by_label = {r["label"]: r for r in records}
    t1 = [r for r in core if r["arm"] == "t1"]
    term = [r for r in t1 if r["cell"] in INTERIOR_CELLS]
    scope = [r["label"] for r in term if r.get("interior_gold_in_trace") is True]
    lost = [r for r in term if not r["correct"]]
    held = [r for r in term if r["correct"]]

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
    nX, seenX = arm_n(scope, "X")
    nC, seenC = arm_n(scope, "C")
    nF, seenF = arm_n(scope, "F")
    nB, seenB = arm_n(scope, "B")
    hA, hseenA = arm_n(held_labels, "X")
    hC, hseenC = arm_n(held_labels, "C")
    hF, hseenF = arm_n(held_labels, "F")
    hB, hseenB = arm_n(held_labels, "B")

    min_scope = gate["decision_C2"]["min_drafts_with_gold"]

    # row C2 (primary): own draft against the whole foreign draft
    if len(scope) < min_scope:
        verdict_c2 = "not_evaluable"
    elif nC >= 1 and nC >= nX - 1:
        verdict_c2 = "scaffold_carries"
    elif nX >= 2 and nX - nC >= 2:
        verdict_c2 = "own_content_selects"
    elif nX == 0 and nC == 0:
        verdict_c2 = "no_recovery"
    else:
        verdict_c2 = "ambiguous"

    # row R2 (carried): own draft against the tokenized filler
    if len(scope) < min_scope:
        verdict_r2 = "not_evaluable"
    elif nF >= 1 and nF >= nX - 1:
        verdict_r2 = "filler_matches_budget"
    elif nX >= 2 and nX - nF >= 2:
        verdict_r2 = "cross_ask_gated"
    elif nX == 0:
        verdict_r2 = "no_recovery"
    else:
        verdict_r2 = "ambiguous"

    # the tail detectors and the downgrades
    delivered_x = [by_label[f"{lab}_X"] for lab in scope
                   if f"{lab}_X" in by_label and by_label[f"{lab}_X"]["delivered"]]
    all_tail = bool(delivered_x) and all(r.get("answer_is_draft_tail") for r in delivered_x)
    if not delivered_x:
        verdict_x2 = "no_delivered_X_records"
    elif all_tail:
        verdict_x2 = "tail_copy"
        if verdict_r2 == "cross_ask_gated":
            verdict_r2 = "cross_ask_gated_downgraded_to_tail_copy"
    else:
        verdict_x2 = "selection_beyond_tail"

    delivered_c = [by_label[f"{lab}_C"] for lab in scope
                   if f"{lab}_C" in by_label and by_label[f"{lab}_C"]["delivered"]]

    # binomials over the discordant pairs
    def discordant(arm_a: str, arm_b: str):
        paired = [lab for lab in scope
                   if f"{lab}_{arm_a}" in by_label and f"{lab}_{arm_b}" in by_label]
        a_only = [lab for lab in paired
                  if by_label[f"{lab}_{arm_a}"]["correct"]
                  and not by_label[f"{lab}_{arm_b}"]["correct"]]
        b_only = [lab for lab in paired
                  if by_label[f"{lab}_{arm_b}"]["correct"]
                  and not by_label[f"{lab}_{arm_a}"]["correct"]]
        n_disc = len(a_only) + len(b_only)
        p_two = binom_two_sided(n_disc, max(len(a_only), len(b_only))) if n_disc else None
        return paired, a_only, b_only, p_two

    paired_xc, xc_x, xc_c, p_xc = discordant("X", "C")
    paired_xf, xf_x, xf_f, p_xf = discordant("X", "F")

    # row P1: measured prompt-token parity across the notes arms, per armed cell
    p1 = {}
    for lab in ARMED_CELLS:
        pt = {a: by_label.get(f"{lab}_{a}", {}).get("prompt_tokens") for a in ARMS}
        notes = [pt[a] for a in ("X", "C", "F") if pt.get(a) is not None]
        pB = pt.get("B")
        cell_matched = (bool(notes) and pB is not None
                        and (max(notes) - min(notes)) <= P1_TOKEN_BAND
                        and min(notes) > pB)
        p1[lab] = {"prompt_tokens": pt, "cell_matched": cell_matched,
                   "notes_spread": (max(notes) - min(notes)) if notes else None}
    n_matched = sum(1 for v in p1.values() if v["cell_matched"])

    # row F1: the tuned filler's realized counts and probe lengths, per armed cell
    f1 = {}
    for lab in ARMED_CELLS:
        frec = by_label.get(f"{lab}_F")
        if frec is None:
            continue
        f1[lab] = {"filler_tokens": frec.get("filler_tokens"),
                   "filler_probe_lengths": frec.get("filler_probe_lengths", []),
                   "prompt_tokens": frec.get("prompt_tokens"),
                   "cell_matched": p1[lab]["cell_matched"]}

    ctrl = [r for r in t1 if r["cell"] in CONTROL_CELLS]
    false_names = {a: 0 for a in ARMS}
    ctrl_none_t1 = sum(1 for r in ctrl if r["declared"] == NONE_GOLD)
    for lab in [r["label"] for r in ctrl]:
        for arm in ARMS:
            rec = by_label.get(f"{lab}_{arm}")
            if rec is not None and rec["delivery_state"] == "false_name_on_none_gold":
                false_names[arm] += 1

    states: dict = {}
    for r in core:
        states[r["delivery_state"]] = states.get(r["delivery_state"], 0) + 1
    law_counts: dict = {}
    for r in core:
        for law in r["wall_laws"]:
            law_counts[law] = law_counts.get(law, 0) + 1

    return {
        "model_digest": gate["model_digest"],
        "prompts_dispatched": len(records),
        "prompts_scored": len(core),
        "f_probes": sum(1 for r in records if r["arm"] == "Fprobe"),
        "C2_foreign_draft": {
            "verdict": verdict_c2, "evaluable_scope": len(scope), "scope_cells": scope,
            "n_lost_turn1": len(lost_labels), "lost_cells": lost_labels,
            "arm_X_correct": nX, "arm_X_seen": seenX,
            "arm_C_correct": nC, "arm_C_seen": seenC,
            "arm_F_correct": nF, "arm_F_seen": seenF,
            "arm_B_correct": nB, "arm_B_seen": seenB,
            "paired_cells_X_vs_C": paired_xc, "discordant_X_only": xc_x,
            "discordant_C_only": xc_c,
            "exact_two_sided_binomial_on_X_C_discordants": p_xc,
            "arm_C_delivered_foreign_tail": [bool(r.get("answer_is_foreign_tail"))
                                              for r in delivered_c],
        },
        "R2_cross_ask": {
            "verdict": verdict_r2, "evaluable_scope": len(scope), "scope_cells": scope,
            "arm_X_correct": nX, "arm_X_seen": seenX,
            "arm_F_correct": nF, "arm_F_seen": seenF,
            "arm_B_correct": nB, "arm_B_seen": seenB,
            "paired_cells_X_vs_F": paired_xf, "discordant_X_only": xf_x,
            "discordant_F_only": xf_f,
            "exact_two_sided_binomial_on_X_F_discordants": p_xf,
        },
        "X2_tail_shortcut": {
            "verdict": verdict_x2,
            "arm_X_delivered_is_draft_tail": [bool(r.get("answer_is_draft_tail"))
                                              for r in delivered_x],
        },
        "F1_filler_token_match": f1,
        "P1_prompt_tokens_parity": {
            "band": P1_TOKEN_BAND, "cells": p1, "cells_matched": n_matched,
            "cells_armed": len(ARMED_CELLS),
            "context_matched": n_matched == len(ARMED_CELLS)},
        "H1_answer_stability": {"n_held": len(held_labels), "held_cells": held_labels,
                                "arm_X_kept": hA, "arm_X_seen": hseenA,
                                "arm_C_kept": hC, "arm_C_seen": hseenC,
                                "arm_F_kept": hF, "arm_F_seen": hseenF,
                                "arm_B_kept": hB, "arm_B_seen": hseenB},
        "C1_name_pressure": {"controls": [r["label"] for r in ctrl],
                             "turn1_declared_none": ctrl_none_t1,
                             "false_names_arm_X": false_names["X"],
                             "false_names_arm_C": false_names["C"],
                             "false_names_arm_F": false_names["F"],
                             "false_names_arm_B": false_names["B"]},
        "S1_delivery_census": states,
        "W2_wall_law_counts": law_counts,
        "M4_matched_pair": {lab: {"prompt_sha256": by_label[lab].get("prompt_sha256", "")[:16],
                                  "delivery_state": by_label[lab]["delivery_state"],
                                  "completion_tokens": by_label[lab]["completion_tokens"]}
                            for lab in MATCHED_PAIR["prompt_sha256"] if lab in by_label},
        "trace_exposure": {"fields": sorted({f for r in core for f in r.get("message_fields", [])}),
                           "supplying_field": sorted({r["trace_field"] for r in core
                                                       if r.get("trace_field")}),
                           "records_with_trace": sum(1 for r in core if r.get("trace_chars"))},
        "gold_in_trace_census": {"true": sum(1 for r in core if r["gold_in_trace"] is True),
                                 "false": sum(1 for r in core if r["gold_in_trace"] is False),
                                 "n_a_none_gold": sum(1 for r in core
                                                      if r["gold_in_trace"] is None)},
        "interior_gold_in_trace_census": {
            "true": sum(1 for r in core if r.get("interior_gold_in_trace") is True),
            "false": sum(1 for r in core if r.get("interior_gold_in_trace") is False)},
        "per_record": [{"label": r["label"], "arm": r["arm"], "j": r["j"], "gold": r["gold"],
                        "declared": r["declared"], "correct": r["correct"],
                        "delivery_state": r["delivery_state"], "finish": r["finish_reason"],
                        "tokens": r["completion_tokens"], "reserve": r.get("reserve"),
                        "prompt_tokens": r.get("prompt_tokens"),
                        "tok_per_s": r["tok_per_s"], "trace_chars": r["trace_chars"],
                        "gold_in_trace": r["gold_in_trace"],
                        "interior_gold_in_trace": r.get("interior_gold_in_trace"),
                        "wall_laws": r["wall_laws"],
                        "answer_is_notes_tail": r.get("answer_is_notes_tail"),
                        "answer_is_draft_tail": r.get("answer_is_draft_tail"),
                        "answer_is_foreign_tail": r.get("answer_is_foreign_tail"),
                        "foreign_block_contains_gold": r.get("foreign_block_contains_gold"),
                        "donor_item": r.get("donor_item"),
                        "filler_tokens": r.get("filler_tokens"),
                        "filler_probe_lengths": r.get("filler_probe_lengths"),
                        "foreign_tokens": r.get("foreign_tokens")}
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


def cmd_freeze(theory: dict) -> int:
    recs = plan_records()
    gate = gate_spec(recs, theory)
    with open(os.path.join(_HERE, "gate.json"), "w", encoding="utf-8") as fh:
        json.dump(gate, fh, sort_keys=True, indent=1)
    blob = hashlib.sha256(json.dumps(gate, sort_keys=True).encode()).hexdigest()
    print(blob)
    return 0


def probe_spec(arm_spec: dict, label: str, arm: str, cap: int, filler_n: int) -> dict:
    """A cap-1 measurement spec for the F tuner: the same treatment, the recorded length,
    the probe label and the probe cap. The pin digest recomputes with the length in
    effect, so a probe's pin equals the scoring dispatch's pin at the same length."""
    spec = dict(arm_spec)
    spec["label"] = label
    spec["arm"] = arm
    spec["cap"] = cap
    spec["filler_tokens"] = filler_n
    spec["prompt_sha256"] = prompt_digest(json.dumps(arm_spec["messages"], sort_keys=True))
    return spec


def cmd_run() -> int:
    """Dispatch pass. The turn-1 non-report channels stay in memory only long enough to build
    the arms: they are treatments, never archive fields, so no trace text is written to disk.
    All three terminal turn-1 cells dispatch before any arm (arm C needs another item's
    draft), then the control and the anchor, then per armed cell in the registered order
    X, C, B, the F probes (cap 1, at most two) and the F scoring dispatch."""
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
    drafts: dict = {}

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

    def within_budget() -> bool:
        return time.time() - t_start < DISPATCH_BUDGET_S - CELL_FLOOR_S

    def record(spec: dict, res: dict) -> dict:
        rec = measure_record(spec, res)
        with open(raw_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        records.append(rec)
        return rec

    def dispatch_scoring(spec: dict) -> dict:
        """A scoring dispatch (cap 2048), resume-safe. Returns the record (fresh or resumed)."""
        if spec["label"] in done:
            return next(r for r in records if r["label"] == spec["label"])
        res = dispatch(spec["messages"], spec["cap"])
        rec = record(spec, res)
        print(f"{rec['label']} {rec['delivery_state']} ct={rec['completion_tokens']} "
              f"pt={rec.get('prompt_tokens')} {rec['tok_per_s']} tok/s", flush=True)
        return rec

    # pass 1: the three terminal turn-1 cells (arm C needs the other items' drafts)
    for spec in planned:
        if spec["cell"] not in INTERIOR_CELLS:
            continue
        if not within_budget():
            print(f"dispatch budget reached, stopping before {spec['label']}", file=sys.stderr)
            stopped_early.append(spec["label"])
            break
        if spec["label"] in done:
            # a resumed pass: the turn-1 draft was a treatment, never an archive field, so it
            # is not reusable; arm X/C on this cell dispatch with an empty notes block and the
            # cell ships downgraded
            print(f"resume: {spec['label']} already recorded; its draft is not reusable, "
                  f"arms X/C dispatch with an empty notes block", file=sys.stderr)
            drafts.setdefault(spec["item_key"], "")
            continue
        res = dispatch([{"role": "user", "content": spec["prompt"]}], spec["cap"])
        rec = record(spec, res)
        content_visible = rec["content"]
        trace, _f, _s = trace_of(res["message"])
        drafts[spec["item_key"]] = trace
        print(f"{rec['label']} {rec['delivery_state']} ct={rec['completion_tokens']} "
              f"trace={rec['trace_chars']} {rec['tok_per_s']} tok/s", flush=True)

    # pass 2: the control and the anchor. The control's own trace is kept for its arm X; it
    # never replaces a terminal draft in the donor map (the control's item is C64, whose
    # donor-side draft is the C64_j64 terminal's)
    ctrl_trace = ""
    for spec in planned:
        if spec["cell"] in INTERIOR_CELLS or spec["label"] in done:
            continue
        if not within_budget():
            print(f"dispatch budget reached, stopping before {spec['label']}", file=sys.stderr)
            stopped_early.append(spec["label"])
            break
        res = dispatch([{"role": "user", "content": spec["prompt"]}], spec["cap"])
        rec = record(spec, res)
        if spec["label"] == "C64_over":
            ctrl_trace = trace_of(res["message"])[0]
        print(f"{rec['label']} {rec['delivery_state']} ct={rec['completion_tokens']} "
              f"{rec['tok_per_s']} tok/s", flush=True)

    # pass 3: the arms, per cell in the registered order X, C, B, then the F probes and the
    # F scoring dispatch. Each cell's own draft is its terminal trace (the control's own
    # trace for the control); the donor draft comes from the donor map, whole and uncut.
    for spec in planned:
        if spec["cell"] not in ARMED_CELLS:
            continue
        if spec["label"] in done and all(
                f"{spec['label']}_{a}" in done for a in ARMS):
            continue
        rec = next(r for r in records if r["label"] == spec["label"])
        own_trace = ctrl_trace if spec["label"] in CONTROL_CELLS else drafts.get(
            spec["item_key"], "")
        t1p = {**spec, "content_visible": rec["content"], "trace": own_trace}
        n0 = len((own_trace or "").split())
        specs = {a: s for a, s in zip(ARMS, arm_records(t1p, drafts, filler_n=n0))}
        for arm in ("X", "C", "B"):
            if not within_budget():
                print(f"dispatch budget reached, stopping before {specs[arm]['label']}",
                      file=sys.stderr)
                stopped_early.append(specs[arm]["label"])
                break
            dispatch_scoring(specs[arm])
        else:
            # the F tuner: probe 1 at n0 (cap 1), the registered rescale, probe 2, then the
            # scoring dispatch at the tuned length. Probes are resume-safe like arms: a
            # recorded probe is read back, never re-dispatched.
            xrec = next(r for r in records if r["label"] == f"{spec['label']}_X")
            brec = next(r for r in records if r["label"] == f"{spec['label']}_B")
            pt_x = xrec.get("prompt_tokens")
            pt_b = brec.get("prompt_tokens")
            p1_label = f"{spec['label']}_Fp1"
            if p1_label in done:
                probe1 = next(r for r in records if r["label"] == p1_label)
            else:
                probe1 = record(probe_spec(specs["F"], p1_label, "Fprobe",
                                           F_PROBE_CAP, n0),
                                dispatch(specs["F"]["messages"], F_PROBE_CAP))
                print(f"{probe1['label']} probe ct={probe1['completion_tokens']} "
                      f"pt={probe1.get('prompt_tokens')} n={n0}", flush=True)
            n_final, probes_used = tune_filler(n0, pt_x, pt_b,
                                                probe1.get("prompt_tokens"))
            filler_lengths = [n0]
            if probes_used == 2:
                specs2 = {a: s for a, s in zip(
                    ARMS, arm_records(t1p, drafts, filler_n=n_final))}
                p2_label = f"{spec['label']}_Fp2"
                if p2_label in done:
                    probe2 = next(r for r in records if r["label"] == p2_label)
                else:
                    probe2 = record(probe_spec(specs2["F"], p2_label, "Fprobe",
                                               F_PROBE_CAP, n_final),
                                    dispatch(specs2["F"]["messages"], F_PROBE_CAP))
                    print(f"{probe2['label']} probe ct={probe2['completion_tokens']} "
                          f"pt={probe2.get('prompt_tokens')} n={n_final}", flush=True)
                specs["F"] = specs2["F"]
                filler_lengths.append(n_final)
            if not within_budget():
                print(f"dispatch budget reached, stopping before {specs['F']['label']}",
                      file=sys.stderr)
                stopped_early.append(specs["F"]["label"])
            elif specs["F"]["label"] in done:
                pass      # a resumed scoring dispatch: nothing to do
            else:
                fspec = dict(specs["F"])
                fspec["filler_tokens"] = n_final
                fspec["filler_probe_lengths"] = filler_lengths
                fspec["prompt_sha256"] = prompt_digest(
                    json.dumps(fspec["messages"], sort_keys=True))
                frec = dispatch_scoring(fspec)

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
    print(json.dumps({k: summary[k] for k in ("C2_foreign_draft", "R2_cross_ask",
                                               "X2_tail_shortcut",
                                               "F1_filler_token_match",
                                               "P1_prompt_tokens_parity",
                                               "H1_answer_stability",
                                               "C1_name_pressure")},
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
    ok("two-sided binomial 3-0", binom_two_sided(3, 3) == 0.25)
    ok("two-sided binomial 5-0", binom_two_sided(5, 5) == 0.0625)
    ok("two-sided binomial 1-1 is a tie", binom_two_sided(2, 1) == 1.0)
    ok("two-sided binomial empty", binom_two_sided(0, 0) is None)

    _ITEMS = select_items()
    ok("three items", len(_ITEMS) == 3)
    ok("archived k=48 seed", _ITEMS["A48"]["seed"] == ARCHIVED_K48["seed"])
    ok("archived k=48 yes/no digest",
       prompt_digest(render_yesno(_ITEMS["A48"]))[:16] == ARCHIVED_K48["yesno_digest16"])

    # the foreign-scaffold precondition: the item vocabularies are NOT pairwise disjoint, so the
    # right check is the narrower gold-leak one - for each interior cell the asked interior gold
    # must not sit in the DONOR item's vocabulary, so a whole donor draft can never contain the
    # asked gold (a copy of the block only yields donor-vocabulary names)
    donor_gold_leak = {}
    for key in ("A48", "B50", "C64"):
        it = _ITEMS[key]
        head = it["query"][0]
        gint = terminal_at(it, head, J_INT)
        donor_vocab = {w.lower() for w in vocab_of(_ITEMS[FOREIGN_MAP[key]])}
        leak = gint.lower() in donor_vocab
        donor_gold_leak[key] = leak
        ok(f"{key} interior gold not in donor vocab", not leak)

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
        s1, r1, t1w = it["facts"][1]
        wide["facts"] = [(s0, r0, t0), (s0, r0, t1w)] + list(it["facts"][2:])
        try:
            check_item(wide)
            ok(f"{key} out-degree-two item refused", False)
        except AssertionError:
            ok(f"{key} out-degree-two item refused", True)
        # the interior geometry: the ask is strictly inside the walk, and the tail detectors
        # are not vacuous (the interior gold is neither the tail nor the start)
        gint = terminal_at(it, head, J_INT)
        ok(f"{key} interior ask strictly inside", 0 < J_INT < lvl)
        ok(f"{key} interior gold exists", gint is not None)
        ok(f"{key} interior gold distinct from tail", gint != nodes[-1])
        ok(f"{key} interior gold distinct from start", gint != head)
        ok(f"{key} filler token outside vocabulary",
           FILLER_TOKEN.lower() not in {w.lower() for w in vocab_of(it)})

    # the donor map is a permutation of the other two items on each name cell
    ok("donor map is round robin",
       sorted(FOREIGN_MAP.values()) == sorted(set(_ITEMS) - set()) and
       all(FOREIGN_MAP[k] != k for k in FOREIGN_MAP) and len(set(FOREIGN_MAP.values())) == 3)

    # the matched pair: three turn-1 prompts are byte-identical to the round-63/69/70/72/73/75 cells
    for lab, want in MATCHED_PAIR["prompt_sha256"].items():
        rec = next(r for r in plan_records() if r["label"] == lab)
        ok(f"matched pair {lab}", prompt_digest(rec["prompt"]) == want)

    # panel arithmetic and gold assignment
    recs = plan_records()
    ok("five turn-1 cells", len(recs) == 5)
    ok("interior cells carry the interior gold", all(r["interior_gold"] for r in recs
                                                       if r["cell"] in INTERIOR_CELLS))
    ok("over-tail control has no interior gold",
       next(r for r in recs if r["label"] == "C64_over")["interior_gold"] is None)
    ok("prompt cap with probes",
       len(recs) + PREGATE_CALLS + ARM_CALLS + F_PROBE_CALLS <= CALL_CAP)
    ok("controls ask past the tail", all(r["gold"] == NONE_GOLD for r in recs
                                          if r["kind"] == "over_end"))
    ok("interior cells have a name gold", all(r["gold"] != NONE_GOLD for r in recs
                                               if r["cell"] in INTERIOR_CELLS))
    over = next(r for r in recs if r["label"] == "C64_over")
    ok("over_end j above path length", over["j"] > over["path_len"])
    ok("probe budget registered", F_PROBE_MAX_PER_CELL == 2 and F_PROBE_CAP == 1)

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

    # foreign-block construction: WHOLE donor, no cut (the round-77 change); a short donor is
    # used whole, an empty donor is an empty block
    block, n = foreign_block("w1 w2 w3 w4 w5 w6 w7 w8")
    ok("foreign block uses the donor whole",
       block == "w1 w2 w3 w4 w5 w6 w7 w8" and n == 8)
    block2, n2 = foreign_block("w1 w2")
    ok("short donor used whole", block2 == "w1 w2" and n2 == 2)
    block3, n3 = foreign_block("")
    ok("empty donor is an empty block", block3 == "" and n3 == 0)

    # filler tuning (row F1): the registered in-band keep, the rescale step, the degenerate
    # increments and the missing-measurement fallback
    ok("filler tune keeps an in-band probe",
       tune_filler(900, 2457, 400, 2400) == (900, 1))
    ok("filler tune rescales an out-of-band probe",
       tune_filler(900, 2457, 400, 1192) == (round(900 * (2457 - 400) / (1192 - 400)), 2))
    ok("filler tune rescale target", tune_filler(900, 2457, 400, 1192)[0] == 2338)
    ok("filler tune keeps an exact match", tune_filler(500, 1200, 400, 1200) == (500, 1))
    ok("filler tune falls back to 2x on a non-positive increment",
       tune_filler(500, 2000, 400, 300) == (1000, 2))
    ok("filler tune floors the rescale at 1", tune_filler(900, 300, 400, 1000) == (1, 2))
    ok("filler tune keeps n0 on a missing measurement",
       tune_filler(900, None, None, None) == (900, 1))

    # arm construction: four arms, one notes-block difference, FULL prompt user turn
    spec = next(r for r in plan_records() if r["label"] == "B50_j50")
    long_prompt = spec["prompt"]  # the full turn-1 prompt, far over the 900-char archive cap
    fake_t1 = {**spec, "content_visible": "prish", "trace": "dunnu precedes crath. crath blorp."}
    fake_drafts = {"A48": "aaa bbb", "B50": fake_t1["trace"],
                   "C64": "y1 y2 y3 y4 y5 y6 y7 y8"}   # longer than the own-draft budget
    arms = {a["arm"]: a for a in arm_records(fake_t1, fake_drafts, filler_n=6)}
    ok("four arms per cell", set(arms) == set(ARMS))
    x_txt = json.dumps(arms["X"]["messages"])
    c_txt = json.dumps(arms["C"]["messages"])
    f_txt = json.dumps(arms["F"]["messages"])
    b_txt = json.dumps(arms["B"]["messages"])
    ok("every arm user turn is the full turn-1 prompt",
       all(arms[a]["messages"][0]["content"] == long_prompt for a in ARMS))
    ok("full prompt exceeds the archive copy cap", len(long_prompt) > 900)
    ok("arm X carries the notes label", NOTES_LABEL in x_txt)
    ok("arm X carries the own draft text", "dunnu precedes crath" in x_txt)
    ok("arm C carries the donor draft whole, not the own",
       "y1 y2 y3 y4 y5 y6 y7 y8" in c_txt and "dunnu precedes crath" not in c_txt)
    ok("arm C pins the donor item", arms["C"]["donor_item"] == FOREIGN_MAP["B50"])
    ok("arm C counts the whole donor block", arms["C"]["foreign_tokens"] == 8)
    ok("arm F carries the tuned filler, no drafts",
       FILLER_TOKEN in f_txt and "dunnu precedes crath" not in f_txt
       and "y1 y2" not in f_txt)
    ok("arm B carries no notes", NOTES_LABEL not in b_txt)
    ok("arm B keeps the visible answer", "prish" in b_txt)
    ok("all arms share the interior cue",
       arms["X"]["prompt"] == arms["F"]["prompt"] == arms["C"]["prompt"] == arms["B"]["prompt"] ==
       render_followup(spec["src"], J_INT))
    ok("interior cue names the step", f"step {J_INT}" in arms["X"]["prompt"])
    ok("interior cue preserves NONE", "NONE" in arms["X"]["prompt"])
    ok("arms differ only in the assistant turn",
       all(sum(1 for m, n in zip(arms[a]["messages"], arms["B"]["messages"])
               if json.dumps(m) != json.dumps(n)) == 1 for a in ("X", "C", "F")))
    ok("filler length is the tuned quantity",
       arms["F"]["filler_tokens"] == 6
       and arms["F"]["messages"][1]["content"].count(FILLER_TOKEN) == 6)
    tail_name = spec["gold"]
    # the foreign-tail detector's positive case uses a real donor-vocabulary word: the donor
    # item's step-1 node (always in the donor's vocabulary)
    donor_gold = terminal_at(_ITEMS["C64"], _ITEMS["C64"]["query"][0], 1)
    arms2 = {a["arm"]: a for a in arm_records(
        {**spec, "content_visible": "prish", "trace": f"nodes end at {tail_name}."},
        {"A48": "zz1 zz2", "B50": "", "C64": "yy1 " + donor_gold}, filler_n=2)}
    ok("arm X pins the draft tail", arms2["X"]["draft_vocab_tail"] == tail_name)
    ok("arm C tail is the last donor-vocabulary name of the whole block",
       arms2["C"]["foreign_vocab_tail"] == donor_gold)
    ok("arm cap within protocol", ARM_CAP <= MAX_TOKENS)
    # the gold-leak census: a foreign block that carries the asked gold is flagged; a clean
    # donor block is not
    gint_arm = terminal_at(item_for(spec["item_key"]), spec["src"], J_INT)
    arms3 = {a["arm"]: a for a in arm_records(
        {**spec, "content_visible": "prish", "trace": "nodes end at zorp."},
        {"A48": "", "B50": "", "C64": "the gold is " + gint_arm + " here"}, filler_n=1)}
    ok("arm C flags a gold-bearing foreign block",
       arms3["C"]["foreign_block_contains_gold"] is True)
    ok("arm C clean donor block is unflagged",
       arms["C"]["foreign_block_contains_gold"] is False)

    # the tail-copy measure and the delivery states
    ok("tail name is the last vocabulary name",
       last_vocab_name("blorp then crath then dunnu then zorp", vocab) == "dunnu")
    ok("tail name None when no vocabulary name", last_vocab_name("nothing here", vocab) is None)
    tail_spec = {"gold": "crath", "finish_reason": "stop", "completion_tokens": 40, "cap": 2048,
                 "on_path": ["blorp", "crath"], "declared": "blorp", "delivered": True,
                 "draft_vocab_tail": "blorp"}
    ok("tail copy is wrong on the right path",
       delivery_state(tail_spec) == "delivered_wrong_on_right_path")

    # decision rules, exercised on synthetic outcomes
    # outcomes: label -> (t1 correct, X correct, X delivered, X is draft tail,
    #                        C correct, C delivered, F correct, B correct)
    dc = list(INTERIOR_CELLS)

    def synth(outcomes: dict) -> dict:
        fake = []
        for lab, (t1_ok, x_ok, x_del, x_tail, c_ok, c_del, f_ok, b_ok) in outcomes.items():
            gold, gint = "crath", "dunnu"
            fake.append({"label": lab, "arm": "t1", "cell": lab, "kind": "name", "j": 48,
                        "gold": gold, "interior_gold": gint, "correct": t1_ok,
                        "declared": gold if t1_ok else "blorp", "delivered": True,
                        "finish_reason": "stop", "completion_tokens": 1557, "cap": 2048,
                        "on_path": ["blorp", "crath", "dunnu"], "trace_chars": 900,
                        "gold_in_trace": True, "interior_gold_in_trace": True,
                        "trace_vocab_tail": "blorp", "wall_laws": [],
                        "delivery_state": "delivered_correct" if t1_ok
                        else "delivered_wrong_on_right_path", "tok_per_s": 40.0,
                        "message_fields": [], "trace_field": "reasoning_content"})
            for arm, okk, deliv, tail in (("X", x_ok, x_del, x_tail),
                                           ("C", c_ok, c_del, False),
                                           ("F", f_ok, True, False),
                                           ("B", b_ok, True, False)):
                fake.append({"label": f"{lab}_{arm}", "arm": arm, "cell": lab, "kind": "name",
                            "j": J_INT, "gold": gint, "correct": okk,
                            "declared": gint if okk else "blorp", "delivered": deliv,
                            "finish_reason": "stop" if deliv else "length",
                            "completion_tokens": 60, "cap": 2048,
                            "on_path": ["blorp", "crath", "dunnu"], "trace_chars": 0,
                            "gold_in_trace": None, "interior_gold_in_trace": None,
                            "trace_vocab_tail": "blorp", "wall_laws": [],
                            "delivery_state": ("delivered_correct" if okk
                                               else "delivered_wrong_on_right_path"
                                               if deliv else "censored_at_cap"),
                            "tok_per_s": 30.0,
                            "answer_is_draft_tail": (deliv and not okk and tail)
                            if arm == "X" else None,
                            "answer_is_foreign_tail": False,
                            "filler_tokens": 4, "foreign_tokens": 4, "donor_item": "C64",
                            "message_fields": [], "trace_field": ""})
        out = score(fake, gate_spec(plan_records(), DEFAULT_THEORY))
        return out

    g = {dc[0]: (False, True, True, False, False, True, False, False),
         dc[1]: (False, True, True, False, False, True, False, False),
         dc[2]: (False, True, True, False, False, True, False, False)}
    out = synth(g)
    ok("C2 own_content_selects on 3-0", out["C2_foreign_draft"]["verdict"] == "own_content_selects")
    ok("R2 cross_ask_gated on 3-0 (X vs F)", out["R2_cross_ask"]["verdict"] == "cross_ask_gated")
    ok("X2 selection beyond tail on a recovery", out["X2_tail_shortcut"]["verdict"]
       == "selection_beyond_tail")

    s = {dc[0]: (False, True, True, False, True, True, False, False),
         dc[1]: (False, True, True, False, True, True, False, False),
         dc[2]: (False, True, True, False, True, True, False, False)}
    out = synth(s)
    ok("C2 scaffold_carries on 3-3", out["C2_foreign_draft"]["verdict"] == "scaffold_carries")

    o = {dc[0]: (False, True, True, False, True, True, False, False),
         dc[1]: (False, True, True, False, True, True, False, False),
         dc[2]: (False, True, True, False, False, True, False, False)}
    out = synth(o)
    ok("C2 scaffold_carries on a 3-2 one-step lead", out["C2_foreign_draft"]["verdict"]
       == "scaffold_carries")

    w = {dc[0]: (False, False, True, True, False, True, False, False),
         dc[1]: (False, False, True, True, False, True, False, False),
         dc[2]: (False, False, True, True, False, True, False, False)}
    out = synth(w)
    ok("C2 no_recovery when both arms fail", out["C2_foreign_draft"]["verdict"] == "no_recovery")

    u = {dc[0]: (False, True, True, False, True, True, False, False),
         dc[1]: (False, True, True, False, True, True, False, False),
         dc[2]: (False, False, True, True, False, True, False, False)}
    out = synth(u)
    ok("C2 scaffold_carries on a 2-2 tie", out["C2_foreign_draft"]["verdict"]
       == "scaffold_carries")

    amb = {dc[0]: (False, True, True, False, False, True, False, False),
           dc[1]: (False, False, True, True, False, True, False, False),
           dc[2]: (False, False, True, True, False, True, False, False)}
    out = synth(amb)
    ok("C2 ambiguous on a 1-0", out["C2_foreign_draft"]["verdict"] == "ambiguous")

    n1 = {dc[0]: (False, True, True, False, True, True, True, False)}
    out = synth(n1)
    ok("C2 not_evaluable below the scope minimum",
       out["C2_foreign_draft"]["verdict"] == "not_evaluable")

    # R2 ladder still carries its round-72 shape
    f1o = {dc[0]: (False, True, True, False, False, True, True, False),
           dc[1]: (False, False, True, True, False, True, False, False),
           dc[2]: (False, True, True, False, False, True, True, False)}
    out = synth(f1o)
    ok("R2 filler_matches_budget on 2-2", out["R2_cross_ask"]["verdict"] == "filler_matches_budget")
    n4 = {dc[0]: (False, False, False, False, False, True, True, False),
          dc[1]: (False, False, False, False, False, True, True, False)}
    out = synth(n4)
    ok("R2 filler-only recovery is a budget account",
       out["R2_cross_ask"]["verdict"] == "filler_matches_budget")

    # P1 parity logic, exercised on the score() row with synthetic arm records
    p1cells = {"A48_j48": {"X": 1400, "C": 1420, "F": 1380, "B": 450},
               "B50_j50": {"X": 1400, "C": 1900, "F": 1400, "B": 450},
               "C64_j64": {"X": 1400, "C": 1410, "F": 1420, "B": 1430},
               "C64_over": {"X": 1400, "C": 1390, "F": 1410, "B": 450}}
    p1fake = []
    for lab, arms in p1cells.items():
        for arm, pt in arms.items():
            p1fake.append({"label": f"{lab}_{arm}", "arm": arm, "cell": lab,
                           "prompt_tokens": pt, "correct": False, "delivered": True,
                           "declared": None, "gold": "x", "finish_reason": "stop",
                           "completion_tokens": 60, "cap": 2048,
                           "on_path": [], "delivery_state": "delivered_no_item_name",
                           "wall_laws": [], "trace_chars": 0, "gold_in_trace": None,
                           "interior_gold_in_trace": None,
                           "filler_tokens": 0, "foreign_tokens": 0, "donor_item": None,
                           "message_fields": [], "trace_field": "",
                           "j": 40, "tok_per_s": 30.0})
    # a probe record must not touch any scored row or census
    p1fake.append({"label": "A48_j48_Fp1", "arm": "Fprobe", "cell": "A48_j48",
                   "prompt_tokens": 9999, "correct": True, "delivered": True,
                   "declared": "blorp", "gold": "x", "finish_reason": "stop",
                   "completion_tokens": 1, "cap": 1, "on_path": [],
                   "delivery_state": "delivered_no_item_name", "wall_laws": [],
                   "trace_chars": 0, "gold_in_trace": None,
                   "interior_gold_in_trace": None,
                   "filler_tokens": 900, "foreign_tokens": 0, "donor_item": None,
                   "message_fields": [], "trace_field": "", "j": 40, "tok_per_s": 30.0})
    p1out = score(p1fake, gate_spec(plan_records(), DEFAULT_THEORY))
    p1row = p1out["P1_prompt_tokens_parity"]
    ok("P1 band holds on a 40-token spread",
       p1row["cells"]["A48_j48"]["cell_matched"] is True)
    ok("P1 band breaks on a 500-token spread",
       p1row["cells"]["B50_j50"]["cell_matched"] is False)
    ok("P1 band breaks when B carries the most context",
       p1row["cells"]["C64_j64"]["cell_matched"] is False)
    ok("P1 context_matched is the matched fraction",
       p1row["context_matched"] is False and p1row["cells_matched"] == 2)
    ok("F probe does not pollute the census",
       p1out["S1_delivery_census"] == {"delivered_no_item_name": 16}
       and p1out["prompts_dispatched"] == 17 and p1out["prompts_scored"] == 16
       and p1out["f_probes"] == 1)
    ok("F1 row reports the tuned counts",
       "A48_j48" in p1out["F1_filler_token_match"]
       and p1out["F1_filler_token_match"]["A48_j48"]["cell_matched"] is True)

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
    gate = gate_spec(plan_records(), DEFAULT_THEORY)
    ok("gate carries the C2 decision rule", "own_content_selects" in gate["decision_C2"])
    ok("gate carries every row as a key",
       all(k in gate for k in ("F1_filler_token_match", "P1_prompt_tokens_parity",
                                "V0_precondition", "V1_solver_certified",
                                "V2_control_liveness", "V3_anchor", "X2_tail_shortcut",
                                "H1_answer_stability", "controls_C1", "matched_pair",
                                "wall_laws", "delivery_states", "foreign_map",
                                "arm_dispatch_order", "f_probe_cap",
                                "f_probe_max_per_cell")))
    ok("gate dispatch order ends with the tuned arm",
       gate["arm_dispatch_order"] == list(ARM_DISPATCH_ORDER))
    ok("gate cell count", len(gate["cells"]) == 5)
    ok("gate records every cell prompt", all(c["prompt_sha256"] for c in gate["cells"]))
    ok("gate model digest is 16 hex",
       re.fullmatch(r"[0-9a-f]{16}", gate["model_digest"]) is not None)
    planned_total = (gate["caps"]["planned_calls"] + gate["caps"]["pre_gate_calls"]
                     + gate["caps"]["arm_calls"] + gate["caps"]["f_probe_calls"])
    ok("gate cap arithmetic within 40", planned_total <= CALL_CAP)
    ok("gate has theory rows with sources", all(
        row["source"] and row["verification"] for row in gate["theory_rows"].values()))

    failed = [name for name, cond in checks if not cond]
    print(f"selftest: {len(checks) - len(failed)} of {len(checks)} checks green")
    for name in failed:
        print(f"FAIL {name}", file=sys.stderr)
    return 1 if failed else 0


# ------------------------------------------------------------------ theory fetch


def fetch_theory() -> dict:
    """Re-fetch the theory rows through free scholarly APIs and stamp this round's
    verification strings. T4 and T6 are refetched at arXiv abstract level; T1 is
    refetched at Crossref record level. T2, T3 carry the round-72 record-level
    verification (archived in PR #153) and T5 the archived [FT] entry. A failed fetch
    leaves the round-75 verification in place and says so, so the gate never ships a
    row with a verification it did not actually run."""
    theory = json.loads(json.dumps(DEFAULT_THEORY))
    stamp = "this round 2026-11-20"

    def arxiv_abstract(arxiv_id: str) -> str:
        url = ("https://export.arxiv.org/api/query?id_list=" + arxiv_id
               + "&max_results=1")
        with urllib.request.urlopen(url, timeout=60) as resp:
            xml = resp.read().decode("utf-8", "replace")
        m = re.search(r"<summary>(.*?)</summary>", xml, re.S)
        return (m.group(1).strip() if m else "")

    for key, arxiv_id, phrase in (
            ("T4_verbalizable_workspace", "2607.15495", "poised to verbalize"),
            ("T6_trace_answer_dissociation", "2605.29087", "trace-anchored defense")):
        try:
            abstract = arxiv_abstract(arxiv_id)
        except Exception:
            abstract = ""
        if abstract:
            phrase_ok = phrase.lower() in abstract.lower()
            theory[key]["verification"] = (
                "arXiv export API, abstract level; refetched " + stamp + ", "
                + (str(len(abstract)) + " chars, quoted phrase present"
                   if phrase_ok else
                   str(len(abstract)) + " chars, QUOTED PHRASE NOT IN REFETCHED "
                   "ABSTRACT - statement wording is owed, not silently kept"))
            if not phrase_ok:
                theory[key]["statement"] += (" [refetched abstract no longer carries the "
                                              "quoted phrase; the quoted wording is owed]")
        else:
            theory[key]["verification"] = (
                "arXiv export API fetch failed " + stamp + "; the row carries the "
                "round-75 verification (abstract level, fetched 2026-11-19) only")

    try:
        url = ("https://api.crossref.org/works/10.1037/0033-295X.87.3.215")
        req = urllib.request.Request(url, headers={"User-Agent": "reason-out-of-the-box "
                                                                 "(stdlib research round)"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            work = json.load(resp)
        title = ((work.get("message") or {}).get("title") or [""])[0]
        if "think" in title.lower() or "report" in title.lower():
            theory["T1_verbal_report_bibliographic"]["verification"] = (
                "Crossref work record refetched " + stamp + " (record level: title "
                f"'{title[:80]}'...), title match against the Ericsson-Simon frame")
        else:
            raise ValueError("title mismatch: " + title[:80])
    except Exception as exc:
        theory["T1_verbal_report_bibliographic"]["verification"] = (
            "Crossref refetch failed " + stamp + " (" + type(exc).__name__ + "); the row "
            "carries the round-75 verification (record level, fetched 2026-11-17) only")
    return theory


# ------------------------------------------------------------------ main


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description="round 77 token-matched cross-ask probe")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--fetch-theory", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--rescore", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    global _ITEMS
    _ITEMS = select_items()
    if args.fetch_theory:
        with open(os.path.join(_HERE, "theory.json"), "w", encoding="utf-8") as fh:
            json.dump(fetch_theory(), fh, sort_keys=True, indent=1)
        return 0
    if args.measure:
        return cmd_measure()
    if args.freeze:
        theory_path = os.path.join(_HERE, "theory.json")
        if os.path.exists(theory_path):
            with open(theory_path, encoding="utf-8") as fh:
                theory = json.load(fh)
        else:
            theory = DEFAULT_THEORY
        return cmd_freeze(theory)
    if args.run:
        return cmd_run()
    if args.rescore:
        return cmd_rescore()
    print("nothing to do", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

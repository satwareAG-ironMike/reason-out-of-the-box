#!/usr/bin/env python3
"""Round 54 probe: does the 27B class carry a serving-stack budget, or a constant reserve region?

Question (issue #71, #94, #100, #105, #126). Round 53 ran the cap-ladder design (prompt bytes
fixed, requested cap moved) on a flash-next-class deployment and found none of its three
registered shapes: the stops moved with neither the cap (1,044 at cap 1,536 where the proportional
prediction was 1,167) nor a fixed fraction, and every one of its seven pinned ladder records
stopped with 492 tokens of reserve below its requested cap (disclosed there as post-hoc, outside
its registered gate blob). Round 52, the last 27B-class firing, showed the opposite shape on the
ladder family at the load floor: every censored record ran to the full 2,048 cap (reserve 0) with
`finish_reason` `length`, and the 1,556 pin never appeared. This round re-dispatches round 53's
design, prompts byte-identical, on a 27B-class deployment and asks:

  H1 proportional budget  the stop lands at 1556 * cap / 2048 with `finish_reason = stop` and the
      marker sentence present at every cap.
  H2 absolute budget      for every cap below 1556 the output reaches the cap itself with
      `finish_reason = length`, no marker and no answer.
  H3 no serving budget    lengths track the task, the marker appears wherever the model writes it,
      and the pin is a property of the family on this class as well.
  H4 reserve region (cross-class contrast, post-hoc readout only) the pinned ladder records stop
      at a constant nonzero reserve below the requested cap, the shape round 53 found on the
      flash class.

The dispatch plan is round 53's, unchanged: the three certified k = 48 load-floor items (round 51's
pair that the flash class delivered *wrong*, plus the gold-yes control), the same arms and caps,
one duplicate re-dispatch as the issue #100 self-agreement control, and the non-ladder listing
control at two caps. The duplicate control and the 27B-class cross-firing row (X1, against round
52's archived k = 48 records) are the round-52 debts this firing discharges: a byte-identical
re-dispatch on a second 27B-class deployment, and the 27B class's second same-class pair with the
reasoning channel open on both sides (issue #105).

Dispatch budget: 15 calls of the 40-call cap, temperature 0, every requested cap at or below the
2048 protocol cap, a 3,000 s wall-clock guard on the dispatch phase (the 27B class is the slower
of the two classes measured so far). The gate rows, their bands and the tier rule are frozen in
gate.json before the first prompt and the blob is pinned below.

Archived reference: quoted from the three pending round directories (branches
research/nightly-2026-11-06-0433 #130, research/nightly-2026-11-07-0319 #132,
origin/research/nightly-2026-11-07-0400 #131), none of which is on `main` yet, so the rows are
vendored as constants with the sha256 of each archived raw.jsonl beside them, and no verdict of
this round depends on them.

No endpoint value (base URL, model id, key) is ever written: artifacts carry a one-way digest of
the serving id and every string passes the sanitizer first.

Usage:
  class_reserve_probe.py --selftest
  class_reserve_probe.py --gate
  class_reserve_probe.py --archive   (the three archive quotes, recomputed, no endpoint call)
  class_reserve_probe.py --dry-run
  NIGHTLY_BASE_URL=... NIGHTLY_MODEL_ID=... NIGHTLY_API_KEY=... class_reserve_probe.py --run
  class_reserve_probe.py --rescore    (rebuild gate+summary from raw.jsonl, no endpoint call)
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
DISPATCH_BUDGET_S = 3000     # wall-clock guard on the dispatch phase (the 27B class runs slower)
GATE_SCHEMA = "round54-gate-v1"

PIN_TOKENS = 1556             # the archived pin (rounds 49 and 51, cap 2048)
PIN_CAP = 2048
HOOK_BAND = 8                 # tokens: |measured - predicted| for a hook hit
CAPS = (512, 1024, 1536, 2048)
MARKER = "I have thought about this long enough; time to give my answer."
LISTING_MAX = 4000            # integers the non-ladder control is asked to write
LISTING_SMALL = 600           # the same control at a smaller extent (completable, so uncapped)
RESERVE = 492                 # the constant reserve round 53 measured below every pinned cap

ROUND51_RAW_SHA256 = "fbfa4fde59f43ea3f484b4205b5beff11d2add27e6c3f60e210ca092e3452f7a"
ROUND52_RAW_SHA256 = "6c1ca286bffd4421ea4aef0bb71aac50648f6591b2c950b1185ba4d989544a1b"
ROUND53_RAW_SHA256 = "d75ced46f51ece2ddf7413bf4331fe8618568d4e300965471486700657efc246"

# Trace exposure quoted from each archive's own per-record census field (issue #105): the message
# field names the endpoint supplied and the field that supplied the reasoning text. `text_stored` is
# whether that directory keeps the reasoning text itself, which is what makes a marker count
# evaluable there at all. All three of this round's archives store the reasoning text.
TRACE_EXPOSURE = {
    "round 51": {"fields": ("content", "reasoning_content"),
                 "reasoning_source": "reasoning_content", "text_stored": True,
                 "marker_quotable": True, "model_digest": "c62b81e96826354e"},
    "round 52": {"fields": ("content", "reasoning_content"),
                 "reasoning_source": "reasoning_content", "text_stored": True,
                 "marker_quotable": False, "model_digest": "86d6f3507f8725bf"},
    "round 53": {"fields": ("content", "reasoning_content"),
                 "reasoning_source": "reasoning_content", "text_stored": True,
                 "marker_quotable": True, "model_digest": "c62b81e96826354e"},
}
# Round 52's 27B-class digest is the class-level pair for issue #105: two 27B-class firings
# (round 52's deployment and this firing's) with the reasoning channel open on both sides.

# Vendored archived rows, extracted programmatically from the three pending round directories.
# ROUND51_PINNED: (seed, gold, facts, prompt_sha16, completion_tokens, requested cap, finish,
#                  marker_in_trace, answer_channel_readout, correct). The three dispatched items,
# quoted from round 51's stage-1 grid.
ROUND51_PINNED = (
    (116261051, 'no', 96, '068bc6a1fb0620fb', 1556, 2048, 'stop', 1, 'yes', 0),
    (116261076, 'no', 96, 'ffc75c928f37f0d9', 1556, 2048, 'stop', 1, 'yes', 0),
    (116261338, 'yes', 96, '87e36020f5c31c93', 1310, 2048, 'stop', 0, 'yes', 1),
)
# ROUND52_K48: (stage, seed, gold, completion_tokens, finish_reason, answer_channel_readout,
#               prompt_sha16, trace_chars, reasoning_source). Round 52's 27B-class k = 48
# as-is rows plus its two duplicate re-dispatches, the X1 cross-firing reference.
ROUND52_K48 = (
    ('grid', 116261051, 'no', 2048, 'length', None, '068bc6a1fb0620fb', 6352, 'reasoning_content'),
    ('grid', 116261076, 'no', 2048, 'length', None, 'ffc75c928f37f0d9', 6378, 'reasoning_content'),
    ('grid', 116261338, 'yes', 840, 'stop', 'yes', '87e36020f5c31c93', 2193, 'reasoning_content'),
    ('dup', 116261051, 'no', 2048, 'length', None, '068bc6a1fb0620fb', 6352, 'reasoning_content'),
    ('dup', 116261338, 'yes', 840, 'stop', 'yes', '87e36020f5c31c93', 2193, 'reasoning_content'),
)
# ROUND53_LADDER: (label, arm, seed, requested cap, completion_tokens, finish_reason,
#                  marker_in_trace, answer_channel_readout, gold). Round 53's flash-class
# cap-ladder records, the reserve-region reference (reserve = cap - completion_tokens).
ROUND53_LADDER = (
    ('as_is_116261051_c2048', 'as_is', 116261051, 2048, 1556, 'stop', 1, 'no', 'no'),
    ('as_is_116261076_c2048', 'as_is', 116261076, 2048, 1556, 'stop', 1, 'yes', 'no'),
    ('dup_116261051_c2048', 'as_is', 116261051, 2048, 1556, 'stop', 1, 'yes', 'no'),
    ('as_is_116261338_c2048', 'as_is', 116261338, 2048, 1205, 'stop', 0, 'yes', 'yes'),
    ('enum_116261051_c2048', 'enumerate', 116261051, 2048, 1715, 'stop', 1, 'yes', 'no'),
    ('enum_116261076_c2048', 'enumerate', 116261076, 2048, 1713, 'stop', 1, 'yes', 'no'),
    ('listing_4000_c2048', 'listing', None, 2048, 2048, 'length', 1, None, None),
    ('as_is_116261051_c1536', 'as_is', 116261051, 1536, 1044, 'stop', 1, 'yes', 'no'),
    ('as_is_116261076_c1536', 'as_is', 116261076, 1536, 1044, 'stop', 1, 'yes', 'no'),
    ('listing_4000_c1024', 'listing', None, 1024, 1024, 'length', 1, None, None),
    ('as_is_116261051_c1024', 'as_is', 116261051, 1024, 532, 'stop', 1, 'yes', 'no'),
    ('as_is_116261076_c1024', 'as_is', 116261076, 1024, 532, 'stop', 1, 'yes', 'no'),
    ('as_is_116261051_c512', 'as_is', 116261051, 512, 512, 'length', 0, None, 'no'),
    ('as_is_116261076_c512', 'as_is', 116261076, 512, 512, 'length', 0, None, 'no'),
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

ROUND54_GATE_BLOB_SHA256 = "435e193993b2f7ffe871c6839bb6e84fec0546d6e2995b99cda1c00f99de71a3"


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
            "On the 27B class, does the cap-ladder design (prompt bytes fixed, requested cap moved "
            "to 512, 1024 and 1536) show a serving-stack budget, a constant reserve region below "
            "the requested cap (the shape round 53 measured on the flash class), or neither; and "
            "does the byte-identical self-agreement control (issue #100) hold on this deployment; "
            "and does this firing give the 27B class a second same-class pair with the reasoning "
            "channel open on both sides (issue #105)?"
        ),
        "hypotheses": {
            "H1_proportional_budget": f"the stop lands at {PIN_TOKENS}*cap//{PIN_CAP} "
                                      f"(band {HOOK_BAND} tokens) with finish_reason stop and the "
                                      "marker sentence present at every cap",
            "H2_absolute_budget": "for every cap below the pin the output reaches the cap itself "
                                  "with finish_reason length, no marker and no answer",
            "H3_no_serving_budget": "lengths track the task; the marker appears wherever the model "
                                    "writes it; the pin is a property of the family on this class "
                                    "as well",
            "H4_reserve_region": "the pinned ladder records stop at a constant nonzero reserve "
                                 "below the requested cap, the flash-class shape round 53 "
                                 "measured; a cross-class contrast readout only, decided post-hoc "
                                 "from the stop-offset column, never by the tier rule",
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
             "rows of round 51 on the certified pair (the flash class): same finish_reason and "
             "same answer-channel readout for both items, with the serving-id digest comparison "
             "stated", "band": "2 of 2", "admits_tier": []},
            {"id": "X1", "kind": "control", "text": "same-prompt cross-firing against the archived "
             "k = 48 rows of round 52 on the 27B class: each item matches round 52's "
             "declared-answer state (the two censored gold-no items: no declared answer; the "
             "gold-yes item: delivered and correct); answer-level only, round 52's archive stores "
             "no marker count (issue #105)", "band": "3 of 3", "admits_tier": []},
            {"id": "C9", "kind": "anomaly", "text": "markers that appear below the predicted hook "
             "are counted as anomalies, never as hook hits (round 51's archived rung record is one: "
             "marker at 532 tokens where the prediction was 778)", "band": "reported",
             "admits_tier": []},
            {"id": "N1", "kind": "census", "text": "issue #105 field census on every record: the "
             "message field names and the reasoning-supplying field (reasoning_content if "
             "non-empty, else reasoning, else empty); the trace-exposure settings of both sides of "
             "the 27B-class pair are stated (round 52: reasoning_content open on all archived "
             "records, model digest 86d6f3507f8725bf; this firing: its own digest), so a "
             "class-level trace statement about this class rests on a same-class pair with the "
             "channel open on both sides", "band": "every record censused",
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
            "N1 every record censused with a non-empty reasoning source AND round 52's archived "
            "source non-empty -> same_class_pair_exposed",
        ],
        "readout_policy": ("the answer channel only for every verdict (issue #94); trace text is "
                           "stored for marker position, listing extent and entity coverage only, "
                           "never as a verdict"),
        "archived_reference": {
            "note": "quoted from three round directories that are open PRs, not main; vendored "
                    "because the post-merge tree, not this firing, is what certifies them; no "
                    "verdict of this round depends on them",
            "branches": {"round 51": "research/nightly-2026-11-06-0433 (#130)",
                         "round 52": "research/nightly-2026-11-07-0319 (#132)",
                         "round 53": "origin/research/nightly-2026-11-07-0400 (#131)"},
            "raw_sha256": {"round 51": ROUND51_RAW_SHA256, "round 52": ROUND52_RAW_SHA256,
                           "round 53": ROUND53_RAW_SHA256},
            "pin_signature": {
                "round 51": {"records": 3, "at_pin": 2, "marker": 2, "gold_yes_stop": 1310,
                             "facts": 2 * LEVEL, "utilisations_at_pin": [round(PIN_TOKENS / PIN_CAP, 4)]},
                "round 52": {"records": 5, "censored_pair": 2, "gold_yes_stop": 840,
                             "dup_trace_chars_equal": True},
                "round 53": {"records": 14,
                              "as_is_stops": {"512": [512, 512], "1024": [532, 532],
                                              "1536": [1044, 1044],
                                              "2048": [1205, 1556, 1556, 1556]},
                              "pinned_reserve_rows": 7, "reserve": RESERVE,
                              "tier_recomputed": "no_serving_budget"},
            },
            # Quoted from each archive's own per-record census field (issue #105): the message
            # field names and the reasoning-supplying field. `marker_quotable` is whether that
            # archive records a marker count at all: rounds 51 and 53 do, round 52 stores the
            # reasoning text but no marker count, so its cross-firing stays answer-level.
            "trace_exposure": TRACE_EXPOSURE,
        },
    }

def gate_blob_sha256() -> str:
    return hashlib.sha256(json.dumps(gate_spec(), sort_keys=True).encode()).hexdigest()


def certify_items() -> dict:
    """Regenerate the three dispatched items and refuse unless every archived digest reproduces."""
    out = {"ok": True, "certified": 0, "refused": []}
    for seed, gold, facts, sha16, *_rest in ROUND51_PINNED:
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

    Every count the README quotes from the three pending directories is emitted here from the
    vendored rows and asserted against the value stated in gate.json.
    """
    problems = []
    stated = gate_spec()["archived_reference"]["pin_signature"]

    # round 51: the three pinned items - the gold-no pair pinned at the cap, the gold-yes
    # control below the pin, and the archived utilisation the pin ratio must reproduce.
    util51 = sorted({round(r[4] / r[5], 4) for r in ROUND51_PINNED if r[1] == "no"})
    measured = {
        "round 51": {"records": len(ROUND51_PINNED),
                     "at_pin": sum(1 for r in ROUND51_PINNED if r[1] == "no"
                                   and r[4] == PIN_TOKENS),
                     "marker": sum(1 for r in ROUND51_PINNED if r[7] == 1),
                     "gold_yes_stop": next(r[4] for r in ROUND51_PINNED if r[1] == "yes"),
                     "facts": next(r[2] for r in ROUND51_PINNED),
                     "utilisations_at_pin": util51},
    }
    if measured["round 51"]["gold_yes_stop"] >= PIN_TOKENS:
        problems.append({"round": "round 51", "field": "gold_yes_stop",
                         "stated": "below the pin", "measured": measured["round 51"]["gold_yes_stop"]})

    # round 52: the 27B-class censored pair and the gold-yes delivery; the duplicate
    # re-dispatches must carry the same trace length as their grid originals.
    grid = {r[1]: r for r in ROUND52_K48 if r[0] == "grid"}
    dup = {r[1]: r for r in ROUND52_K48 if r[0] == "dup"}
    censored = [r for s, r in grid.items() if s in PAIR_SEEDS]
    measured["round 52"] = {
        "records": len(ROUND52_K48),
        "censored_pair": sum(1 for r in censored
                             if r[3] == MAX_TOKENS and r[4] == "length" and r[5] is None),
        "gold_yes_stop": grid[116261338][3],
        "dup_trace_chars_equal": all(grid[s][7] == dup[s][7] for s in dup),
    }

    # round 53: the flash-class cap-ladder stops and the constant reserve below the cap.
    # The reserve claim is scoped to the pinned pair (the round-51 wrong pair), so the
    # gold-yes natural stop (1205 at 2048, reserve 843) is not part of the uniformity check.
    reserved = [r for r in ROUND53_LADDER if r[1] == "as_is" and r[5] == "stop"
                 and r[2] in PAIR_SEEDS]
    ladder = [r for r in ROUND53_LADDER if r[1] == "as_is" and r[3] < MAX_TOKENS]
    c1 = sum(1 for r in ladder if classify(r[4], r[3], r[5], r[6]) == "hook_hit_predicted")
    c2 = sum(1 for r in ladder if classify(r[4], r[3], r[5], r[6]) == "alt_absolute_cap_no_marker")
    c5 = 0
    for r in (row for row in ROUND53_LADDER if row[1] == "listing"):
        pred = predicted_hook(r[3])
        if r[6] == 1 and r[4] is not None and abs(r[4] - pred) <= HOOK_BAND:
            c5 += 1
    if c2 >= 5:
        tier53 = "absolute_pin"
    elif c1 >= 5 and c5 == len([row for row in ROUND53_LADDER if row[1] == "listing"]):
        tier53 = "serving_budget_hook"
    elif c1 <= 2 and c5 == 0:
        tier53 = "no_serving_budget"
    else:
        tier53 = "unresolved"
    measured["round 53"] = {
        "records": len(ROUND53_LADDER),
        "as_is_stops": {str(cap): sorted(r[4] for r in ROUND53_LADDER
                                          if r[1] == "as_is" and r[3] == cap)
                         for cap in CAPS},
        "pinned_reserve_rows": sum(1 for r in reserved if r[3] - r[4] == RESERVE),
        "reserve": RESERVE,
        "tier_recomputed": tier53,
    }

    for name, want in stated.items():
        got = measured[name]
        for key, value in want.items():
            if got.get(key) != value:
                problems.append({"round": name, "field": key, "stated": value,
                                 "measured": got.get(key)})
    # The ratio claim: 1556 / 2048 rounded to four places must equal the archived utilisation.
    ratio = round(PIN_TOKENS / PIN_CAP, 4)
    if util51 != [ratio]:
        problems.append({"round": "round 51", "field": "ratio_recomputation",
                         "stated": ratio, "measured": util51})
    # The reserve claim must be the same number on every reserved row: a slip in one
    # stop shows up as a count slip, not an explained-away discrepancy.
    if sum(1 for r in reserved if r[3] - r[4] == RESERVE) != len(reserved):
        problems.append({"round": "round 53", "field": "reserve_uniformity",
                         "stated": RESERVE,
                         "measured": sorted({r[3] - r[4] for r in reserved})})
    # Trace-exposure rule (issue #105): a marker count is quotable only where the archive
    # records one; round 52 stores the reasoning text but no marker count, so its X1
    # cross-firing must stay an answer-level claim.
    for name, exposure in TRACE_EXPOSURE.items():
        want = stated[name]
        if exposure["marker_quotable"] and "marker" not in want and name != "round 53":
            problems.append({"round": name, "field": "trace_exposure",
                             "stated": "marker count quotable",
                             "measured": "no marker count stated"})
        if not exposure["marker_quotable"] and "marker" in want:
            problems.append({"round": name, "field": "trace_exposure",
                             "stated": "no marker count in the archive, answer-level only",
                             "measured": "marker count quoted"})
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

    archived = {r[0]: r for r in ROUND51_PINNED}
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

    # X1: same-prompt cross-firing against round 52's 27B-class k = 48 records. Match is on the
    # declared-answer state only (answer-level claim: round 52's archive stores no marker count).
    r52_grid = {r[1]: r for r in ROUND52_K48 if r[0] == "grid"}
    x1_detail, x1_ok = [], 0
    for seed in sorted(PINNED_SEEDS):
        archived_row = r52_grid.get(seed)
        group = [r for r in ran if r["label"] == f"as_is_{seed}_c2048"]
        if archived_row is None or not group:
            continue
        g = group[0]
        if archived_row[5] is None:
            match = g["declared"] is None
        else:
            match = g["declared"] == archived_row[5] and g["correct"] is True
        if match:
            x1_ok += 1
        x1_detail.append({"seed": seed, "archived_tokens": archived_row[3],
                         "archived_finish": archived_row[4], "archived_answer": archived_row[5],
                         "tokens": g["completion_tokens"], "finish": g["finish_reason"],
                         "answer": g["declared"], "match": match})
    x1 = row("X1", f"{x1_ok} of {len(x1_detail)}", x1_ok == 3 and len(x1_detail) == 3,
             len(x1_detail))

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
            "X1": x1, "C9": c9, "N1": n1, "R1": r1}

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
    # The 27B-class same-class pair (issue #105): this firing's census must be complete with a
    # non-empty reasoning source, and round 52's archived source must be non-empty too, for the
    # pair to count. Zero records or a zero-trace firing does not complete the pair.
    sources = {(r.get("census") or {}).get("reasoning_source", "") for r in ran if r.get("census")}
    if (n1["status"] == "pass" and len(ran) > 0 and sources and all(sources)
            and TRACE_EXPOSURE["round 52"]["reasoning_source"]):
        flags.append("same_class_pair_exposed")

    health_census = health.get("census") if isinstance(health.get("census"), dict) else {}
    health_row = {"id": "H0", "status": "pass" if health.get("ok") else "fail",
                  "measured": {"ok": health.get("ok"), "tokens": health.get("completion_tokens"),
                               "finish": health.get("finish_reason"),
                               "reasoning_source": health.get("reasoning_source")
                               or health_census.get("reasoning_source"),
                               "wall_s": health.get("wall_s"), "error": health.get("error")}}
    return {"rows": rows, "tier": tier, "tier_rule": spec["tier_rule"], "flags": flags,
            "health": health_row, "enumerate_detail": enum_detail, "cross_fire_detail": c8_detail,
            "cross_fire_27b_detail": x1_detail,
            "dispatch_budget_s": spec["budget"]["dispatch_budget_s"],
            "planned_calls": spec["budget"]["planned_calls"],
            "spec_rows": {r["id"]: r["band"] for r in spec["rows"]}}


def stop_offsets(records: list) -> dict:
    """Post-hoc reserve column (outside the registered gate blob): completion_tokens measured
    against the requested cap, per arm and cap.

    It reads only the frozen raw.jsonl; gate.json and the gate blob are untouched by it. The two
    shape flags name the two class shapes measured so far, scoped to the pinned as-is pair (the
    same scoping as round 53's reserve claim): `constant_reserve_below_cap` - every delivered
    pinned-pair record stops at one shared positive reserve, censored records, if any, at their
    cap (the round-53 flash-class shape); `no_reserve_cap_bound` - censored pinned-pair records
    with no positive reserve region (the round-52 27B-class shape). The conditions are mutually
    exclusive; a firing matching neither raises no flag.
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
    shape_flags = []
    as_is_rows = []
    for rows in per_arm.get("as_is", {}).values():
        as_is_rows.extend(rows)
    pinned_rows = [row for row in as_is_rows if row.get("seed") in PAIR_SEEDS]
    reserved_counts: dict = {}
    censored = 0
    for row in pinned_rows:
        if row["finish"] == "length" and row["tokens"] == row["cap"]:
            censored += 1
        elif row["reserve"] > 0:
            reserved_counts[row["reserve"]] = reserved_counts.get(row["reserve"], 0) + 1
    if (len(reserved_counts) == 1 and next(iter(reserved_counts)) > 0
            and next(iter(reserved_counts.values())) >= 2):
        shape_flags.append("constant_reserve_below_cap")
    if censored > 0 and not any(n >= 2 for n in reserved_counts.values()):
        shape_flags.append("no_reserve_cap_bound")
    return {"registered": False,
            "note": "post-dispatch observation column, outside the registered gate blob; "
                    "no verdict of this round rests on it",
            "shape_flags": shape_flags,
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
        "cross_fire_27b_detail": gate["cross_fire_27b_detail"],
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
    if blob != ROUND54_GATE_BLOB_SHA256:
        print(f"REFUSED: gate blob {blob} does not match the pin {ROUND54_GATE_BLOB_SHA256}",
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

    for seed, gold, facts_n, sha16, tokens, cap, finish, marker, answer, correct in ROUND51_PINNED:
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
    saved = list(ROUND51_PINNED)
    mutated = [row for row in saved]
    mutated[0] = mutated[0][:3] + ("0" * 16,) + mutated[0][4:]
    globals()["ROUND51_PINNED"] = tuple(mutated)
    check("a planted prompt digest slip is refused by the certifier", not certify_items()["ok"])
    mutated2 = list(saved)
    mutated2[0] = mutated2[0][:1] + ("yes",) + mutated2[0][2:]
    globals()["ROUND51_PINNED"] = tuple(mutated2)
    check("a planted gold flip is refused by the certifier", not certify_items()["ok"])
    mutated3 = list(saved)
    mutated3[0] = mutated3[0][:2] + (95,) + mutated3[0][3:]
    globals()["ROUND51_PINNED"] = tuple(mutated3)
    check("a planted fact-count slip is refused by the certifier", not certify_items()["ok"])
    globals()["ROUND51_PINNED"] = tuple(saved)
    check("certification is restored after the planted slips", certify_items()["ok"])

    # 5. the archive quotes reproduce their own aggregates, and a planted slip fails
    cert = certify_archive()
    check("archive quotes reproduce", cert["ok"], )
    check("the recomputed pin ratio is 0.7598", cert["pin_ratio_recomputed"] == 0.7598)
    check("round 51 pin count is the certified gold-no pair",
          cert["measured"]["round 51"]["at_pin"] == 2)
    check("round 51 marker count equals the pin count",
          cert["measured"]["round 51"]["marker"] == cert["measured"]["round 51"]["at_pin"])
    check("round 51 carries the same 0.7598 ratio at the pin",
          cert["measured"]["round 51"]["utilisations_at_pin"] == [0.7598])
    check("round 51 records are the three dispatched items",
          cert["measured"]["round 51"]["records"] == 3)
    check("the round 52 censored pair runs to the full cap with no declared answer",
          cert["measured"]["round 52"]["censored_pair"] == 2
          and cert["measured"]["round 52"]["records"] == 5)
    check("the round 52 duplicate re-dispatches carry the grid trace length",
          cert["measured"]["round 52"]["dup_trace_chars_equal"] is True)
    check("the round 52 gold-yes stop sits below the pin",
          cert["measured"]["round 52"]["gold_yes_stop"] < PIN_TOKENS)
    check("the round 53 ladder recomputes to no_serving_budget",
          cert["measured"]["round 53"]["tier_recomputed"] == "no_serving_budget")
    check("the round 53 pinned-pair rows share the 492 reserve",
          cert["measured"]["round 53"]["pinned_reserve_rows"] == 7
          and cert["measured"]["round 53"]["reserve"] == RESERVE
          and cert["measured"]["round 53"]["records"] == 14)
    stated = gate_spec()["archived_reference"]["pin_signature"]
    check("the stated round 51 utilisation set is the recomputed one",
          stated["round 51"]["utilisations_at_pin"] == [0.7598])
    check("round 52 stores the reasoning text but no marker count, so its "
          "cross-firing must stay answer-level",
          TRACE_EXPOSURE["round 52"]["marker_quotable"] is False
          and "marker" not in stated["round 52"])
    check("the round 51 marker count is quotable against its stated value",
          TRACE_EXPOSURE["round 51"]["marker_quotable"] is True
          and stated["round 51"]["marker"] is not None)
    saved52 = list(ROUND52_K48)
    mutated52 = [row for row in saved52]
    # row 3 is the duplicate re-dispatch of seed 116261051: slip its trace length away
    # from the grid original and the duplicate-control quote must fail
    mutated52[3] = mutated52[3][:7] + (saved52[3][7] + 1,) + mutated52[3][8:]
    globals()["ROUND52_K48"] = tuple(mutated52)
    check("a planted round 52 trace-length slip is refused by the archive certifier",
          not certify_archive()["ok"])
    globals()["ROUND52_K48"] = tuple(saved52)
    check("the archive certifier is restored after the planted slip",
          certify_archive()["ok"])
    saved_exposure = {k: dict(v) for k, v in TRACE_EXPOSURE.items()}
    TRACE_EXPOSURE["round 52"] = {**TRACE_EXPOSURE["round 52"], "marker_quotable": True}
    check("a planted exposure slip is refused: a marker count cannot be quoted "
          "against an archive that records no marker count",
          not certify_archive()["ok"])
    TRACE_EXPOSURE["round 52"] = saved_exposure["round 52"]
    TRACE_EXPOSURE["round 51"] = {**TRACE_EXPOSURE["round 51"], "marker_quotable": False}
    check("a planted zero-marker slip is also refused: a quotable marker count "
          "cannot stand against an archive that records none",
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
    check("the pinned gate blob matches the spec", gate_blob_sha256() == ROUND54_GATE_BLOB_SHA256)
    spec = gate_spec()
    check("every row has a band", all(r["band"] for r in spec["rows"]))
    check("every row has text", all(len(r["text"]) > 20 for r in spec["rows"]))
    check("the gate names all four hypotheses", len(spec["hypotheses"]) == 4)
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
          and gate_blob_sha256() == ROUND54_GATE_BLOB_SHA256)
    return n


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

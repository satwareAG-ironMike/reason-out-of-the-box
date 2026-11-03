#!/usr/bin/env python3
"""Round 40 (2026-11-01 02:04): the 27B class is not zero-trace as a class property: a new
firing of a 27B-class endpoint exposes the reasoning channel that the two archived firings
of the same class (rounds 31 and 37, probed with this same inherited stack) exposed not, and
the cross-class trace comparison the round-38 addendum declared unmeasurable is measured here
on the round-38 panel.

Question, method and verdict summary posted on tracker issue #65
(https://github.com/satwareAG-ironMike/reason-out-of-the-box/issues/65); this file, gate.json,
raw.jsonl and summary.json in this directory are the reproducible record.

Why this question. Round 38's addendum (branch research/nightly-2026-10-31-0228, PR #103)
found that the other class's transcribed transcripts collapse to two hashes, because that
deployment (a 27B-class local model under 4-bit floating-point quantization, vLLM serving,
multi-token-prediction speculative decoding, the class of rounds 31 and 37) answers with a
bare word in the content field and exposes no reasoning text at all, while completion_tokens
bills 182 to 1355 tokens per panel prompt. It concluded that a deployment that does not
expose its reasoning channel makes every trace-level quantity unmeasurable on it, whatever
its accuracy, and that any cross-class trace claim needs the reasoning text surfaced and
archived on both sides. Two PRs of that class had reported the structurally zero
distractor-mention ratio as "the class does not enumerate". This round's endpoint (a 27B
class local model; the served model id is read from the pool environment and never written
to an artifact) exposed non-empty reasoning text on the 256 token health prompt before any
panel prompt was spent. The zero-trace status is therefore testable as a class property or a
deployment property, and the two classes' traces are now joinable on the round-38 panel,
with the reasoning text archived on both sides.

Instrument. Inherits the construction, audit and readout stack verbatim from round 38's
samepanel_replicate_probe.py (branch research/nightly-2026-10-31-0228, PR #103), which
inherits it from round 37's sameclass_frontier_retest_probe.py (PR #102), which inherits it
from rounds 19 to 24: C disjoint directed paths of exactly k edges over fresh entity names,
one rule sentence (transitivity of "precedes"), E = k x C facts in shuffled order, one query
per prompt, answer required as exactly one word; gold from an unbounded BFS independent of
the generator plus a structural audit of every item; each graph asked twice over identical
content (arm F forward, gold yes; arm X cross-component, gold no) with the shared-content
invariant asserted per pair (#78). Readout stack: content_only (primary, scored),
delivered_or_strict (content, else the round-19 strict trace-commitment rule),
loose_fallback (reported, never scored), with the fallback provenance class of every record
(#94). The panel is the first matched pair (arm F and arm X) of each of round 24's six
digest-pinned cells, selected by the archived selection order (pair index 0) before any
outcome was known; 12 prompts dispatched three times in ABABA order (serialized, two in
flight, serialized) = 36 dispatches plus 1 health call = 37 of the 40-call cap, max_tokens
2048, temperature 0.0.

The one declared extension to the inherited stack: call_endpoint also records which message
fields the deployment exposes (field names only) and which field supplied the reasoning
text. The merge rule is fixed before any prompt is spent: reasoning text is the
"reasoning_content" value when non-empty, else the "reasoning" value, else empty, and the
supply is recorded per attempt. The extension exists because the field census is itself a
measurement this round is meant to make; every inherited quantity (including output_sha256
over content + U+0000 + reasoning text, the quantity TARr is measured on) is unchanged.

Joins (transcribed constants; none of the joined firings is on main at authoring time, so
the post-merge tree verifies every comparison without the ancestor branches):
- R38P1_PANEL: round 38's P1 (serialized) records for the 12 panel digests, transcribed from
  research/nightly-2026-10-31-0228/raw.jsonl (PR #103) with full content and reasoning text.
  --selftest recomputes every record's output_sha256 from the embedded text and refuses on
  drift, so the transcription is hash-pinned, not trust-based.
- R31_PANEL and R37_PANEL: the two archived firings of this class, transcribed verbatim from
  round 38's script (billed tokens, answers, finish reasons; R37 carries its collapsed
  content-only hashes, R31 carries no text).
- The R37 collapse is verified deterministic here: --selftest recomputes the output hash of
  the exact archived content strings ("\n\nyes" in 18 records, "\n\nno" in 18, empty
  reasoning) and requires the two archived hashes, so the round-38 addendum's "collapse to
  two hashes" is proven to be bare-answer-with-empty-reasoning, not two long texts.

Caps from the round protocol are contractual, not advisory: at most 40 endpoint calls,
max_tokens 2048, free scholarly APIs only, no metered or hosted providers. Endpoint from
NIGHTLY_BASE_URL, NIGHTLY_MODEL_ID and NIGHTLY_API_KEY; no endpoint value is ever written to
an artifact, and stored model text passes the inherited sanitizer (URLs, IP addresses,
absolute paths). Stdlib only.

  panel_trace_channel_probe.py --selftest
  panel_trace_channel_probe.py --gate              [--out gate.json]
  panel_trace_channel_probe.py --probe             [--out-dir DIR] [--resume]
  panel_trace_channel_probe.py --analyze           [--out-dir DIR]
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import hashlib
import json
import math
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request

REL = "precedes"
RULE_SENTENCE = (f"Rule: for all x, y, z: if x {REL} y and y {REL} z, "
                 f"then x {REL} z. Facts state direct {REL} links.")
SEED_BASE = 20261024
ALPHA = 0.05
PERMS = 400
MAX_TOKENS = 2048
TEMPERATURE = 0.0
PROMPT_CAP = 40
HEALTH_CALLS = 1
PAIRS_PER_LEVEL = 3
CANDIDATES = 40
ITEM_DEADLINE_S = 600
HEALTH_PROMPT = "Reply with exactly one word: yes"
# Health-probe output budget: 256 tokens, per round 22's lesson that a 2048-token health call
# is not portable across the pool (one deployment's upstream gateway killed it at ~60 s with
# http_502 while 256 tokens returned in ~1 s).
HEALTH_BUDGET = 256
GATE_SCHEMA = "round40-gate-v1"
ROUND_LABEL = "round 40 (2026-11-01 02:04)"
CLASS_LABEL = ("a 27B-class local endpoint (served model id read from the pool "
               "environment, never written to an artifact); class identity is an inference "
               "from the pool slot and the served model id, not a fingerprint; the two "
               "archived firings of this class (rounds 31 and 37) were served under 4-bit "
               "floating-point quantization with vLLM-class serving")

# The grid: two arms of (k, C) cells with E = k * C facts. Inside each arm, consecutive cells
# differ in exactly one axis; the load arm holds k = 8, the depth arm holds E = 96. The grid
# is unchanged from round 24, so the panel is a subset of a digest-pinned corpus.
LOAD_ARM = (("L0", 8, 12), ("L1", 8, 14), ("L2", 8, 16), ("L3", 8, 20))
DEPTH_ARM = (("D1", 12, 8), ("D2", 16, 6))
WALK = LOAD_ARM + DEPTH_ARM  # dispatch and reporting order
LOAD_NAMES = tuple(name for name, _k, _c in LOAD_ARM)
DEPTH_NAMES = tuple(name for name, _k, _c in DEPTH_ARM)
WALK_INDEX = {name: i for i, (name, _k, _c) in enumerate(WALK)}
PANEL_PAIR_INDEX = 0  # the archived selection order decides the panel, before any outcome

# The panel: 12 digests, arm F then arm X of pair 0 in each cell. These are round 24's digests
# (research/nightly-2026-10-25-0405/, PR #98); --gate refuses if the builder returns anything
# else, so the panel cannot silently drift away from the pinned corpus.
PANEL_DIGESTS = [
    ("L0", "b20d7fd289fd6f181fb05aebf9ae6526c041870e09c711ae60a7100cb5ca313b"),
    ("L0", "ddb9421bc3e7c63dcae14af51cdb6b5e6347ff569b21683558c0f9fa409b6402"),
    ("L1", "d2ab3a4e71b559b5605e3689658d8f3dfc93efaf7b6f85e74c246e7674f5ced2"),
    ("L1", "31636587257e460c48810a5498e9fee105559cf3425a7262ff909b3a9f8427bc"),
    ("L2", "29635c816e9cf67dbcf54cc78b935840e8b8435d079eba3a5ee79ddaf2b2e32d"),
    ("L2", "54d8b96f74e74bb2fa315f1de73e5812682def9773dc88843a81e93d62a7be5c"),
    ("L3", "4ed1d525026f2f7c43149d7ef8d3d5df040b274f830c8f6fb1f1f0788463cb18"),
    ("L3", "d548b1f9681cf082174cf141f33e0f34a65b98cf2504111e36284bdf287386cc"),
    ("D1", "3a378f98a2b0a41f6fef81c7f0529dcb8264e5cea3dacbf45ddef7b25125a873"),
    ("D1", "b3e37ce3f7f1df518ccfde8ec1c6831680e23e6fb404ed30bd325d41d7f7e491"),
    ("D2", "74388a9a6f4d5549a343593617388774e7adf5dae49681704ac3f3eed7a9c834"),
    ("D2", "de5ed21b32895e67bd295d1b63df3245e57634d0b07da4ba92e9442cd1e0fead"),
]
PANEL_CELLS: dict = collections.defaultdict(list)
for _cell, _digest in PANEL_DIGESTS:
    PANEL_CELLS[_cell].append(_digest)
PANEL_CELLS = {k: list(v) for k, v in PANEL_CELLS.items()}
PANEL_EDGES = {name: k * c for name, k, c in WALK}
PANEL_K = {name: k for name, k, _c in WALK}

# The ABABA pass plan. Passes 1 and 3 are identical in mode and bracket pass 2, which uses the
# concurrency the archived rounds used (round 24: chosen concurrency 2).
ARCHIVED_CONCURRENCY = 2
PASS_PLAN = (
    {"pass_id": "P1", "mode": "serial", "concurrency": 1},
    {"pass_id": "P2", "mode": "paired", "concurrency": ARCHIVED_CONCURRENCY},
    {"pass_id": "P3", "mode": "serial", "concurrency": 1},
)
PASS_IDS = tuple(p["pass_id"] for p in PASS_PLAN)

# Fail-closed structural pin: every cell's pool blob and all 36 prompt digests must equal round
# 24's gate, transcribed from research/nightly-2026-10-25-0405/gate.json (PR #98, not on main
# at authoring time), so the post-merge tree can verify the pin without the ancestor branch.
R24_DIGESTS = {
    "D1": {"cross_prompt_sha256": ["b3e37ce3f7f1df518ccfde8ec1c6831680e23e6fb404ed30bd325d41d7f7e491", "2543a77e9fe6e6a99cf3b72da17a374bd5116692145228cff0646407c2b79eb8", "85bdf738ee94ba77873e213719d719369818420ac69ff228acfa58af828d5f69"], "forward_prompt_sha256": ["3a378f98a2b0a41f6fef81c7f0529dcb8264e5cea3dacbf45ddef7b25125a873", "ec6a74cf4d8475d2937acda2fdd8a7b994dcba7486e47a7ce36b7da12a1cb909", "29e02b372ac84f5e6f631df8ef563e50c8e7381f69921d87c6e2133a7a46e64a"], "pool_blob_sha256": "d5fc4ca963b448d8d6f9501b06a8814185c0b8ec73c9130d853a4f6a2681c214"},
    "D2": {"cross_prompt_sha256": ["de5ed21b32895e67bd295d1b63df3245e57634d0b07da4ba92e9442cd1e0fead", "817d852383a6ef12a7f6215955a1f1d87240a2ca549c6c81b89f598c90ed0e9c", "e21833ff126f4b1f810c05e3dc97342227834e6cb700eb128fedc88e8899b4ba"], "forward_prompt_sha256": ["74388a9a6f4d5549a343593617388774e7adf5dae49681704ac3f3eed7a9c834", "51ddd1f327f0570a048aaf51afe85c3b57968b0287e14f547fd6820a4cfcf7af", "09701216d3fdfe235fa84c9098ae700737a07af184e30f2d264786ffcbd109c9"], "pool_blob_sha256": "161829ff61c37bd0b73f7ce9026bb0ca7b5012f72280b1c88accf91c8a49c6e1"},
    "L0": {"cross_prompt_sha256": ["ddb9421bc3e7c63dcae14af51cdb6b5e6347ff569b21683558c0f9fa409b6402", "af0462f2fdb3097c0f11d4894478ee465646b841cfa003f14938d217eb12204a", "d4e04bfc376c3fa7510d18b3e349a34dbc140e2dfb5bbee85199efaf39c53f6a"], "forward_prompt_sha256": ["b20d7fd289fd6f181fb05aebf9ae6526c041870e09c711ae60a7100cb5ca313b", "96462a5727cd001cee15875248307c476ca41b977a5aff509622736421fe169d", "b3335406e9b510f6a0d9b598494695f1aa798acfc347fe944677c21c07e93702"], "pool_blob_sha256": "bee7e0264b8a69c7d1198d4b24d4207b57c31230bd8a0760bc4ce8853f03dd16"},
    "L1": {"cross_prompt_sha256": ["31636587257e460c48810a5498e9fee105559cf3425a7262ff909b3a9f8427bc", "3748f096518670511c09dc45518580857e80c5541f48200bf7d064cec54e2327", "582c3d08ff0a6b7fbeefaa94ab6ba9d63e6b8d8ffde92d1814d6359d80bb046f"], "forward_prompt_sha256": ["d2ab3a4e71b559b5605e3689658d8f3dfc93efaf7b6f85e74c246e7674f5ced2", "8611a03e5c9afcd443b3317c4f4847e2098e22cfc00022cb92dbdccfdf76ca4a", "50f7c8cc855497a25f636a88b9a06525efc07f1da85e1592db30ac9223e9ce40"], "pool_blob_sha256": "44ae63f24f439ab665463059a415a217c4fb8d24bc67e5672b10e1114e637c67"},
    "L2": {"cross_prompt_sha256": ["54d8b96f74e74bb2fa315f1de73e5812682def9773dc88843a81e93d62a7be5c", "1de707958baabe18e055807eb756159c40a243e7e608b6fa49dbd90351b1a568", "ed9e510b2f843cbc352a9bfaae79b960a5f19900801fb00ff321c5303b4543aa"], "forward_prompt_sha256": ["29635c816e9cf67dbcf54cc78b935840e8b8435d079eba3a5ee79ddaf2b2e32d", "a9c7c461501d38fe6ab35e0dcc6494e7053d4b4bf335aee105b57ceb4eff705b", "135807684c9c2641a478d482733434cd39b96514fabfd9203b6568b4ad442390"], "pool_blob_sha256": "bb383e5ea9c1c20b447acbac755190031ff3a3dc5d47bacff1fd78ac05a62536"},
    "L3": {"cross_prompt_sha256": ["d548b1f9681cf082174cf141f33e0f34a65b98cf2504111e36284bdf287386cc", "3ba9842ed8d61e0bd07e6525fa344b493eafffc962d83fc256b1901119c276a3", "c2fa54ea50ec9930790b9af79669470e3de6511ae859a7512d80339b7e3a1fba"], "forward_prompt_sha256": ["4ed1d525026f2f7c43149d7ef8d3d5df040b274f830c8f6fb1f1f0788463cb18", "3a697ba510346b68e343db17b909fa84a0e5cfb83d12b3dd7b9d4b0746d0fe8c", "2387559a6df93b8e176dc5fcbeb356716e7d873f12917b91669e8782abdad4c0"], "pool_blob_sha256": "8c3005a7516fdacf09a19e05510966eaadb591d2b31a4ff408f45581c766b90f"},
}
ANSWER_RE = re.compile(r"\b(yes|no)\b", re.IGNORECASE)
URL_RE = re.compile(
    r"https?://\S+|\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|"
    r"(?:/[A-Za-z0-9_.-]+){2,}|[A-Za-z]:\\[^\s]*")

# The strict commitment rule and the echo-phrase test, vendored verbatim from rounds
# 19 through 22 (research/nightly-2026-10-24-0405/constant_depth_load_arm.py, PR #96).
PHRASE_RE = re.compile(
    r"yes\s*[/|]\s*no|no\s*[/|]\s*yes|yes\s+or\s+no|no\s+or\s+yes",
    re.IGNORECASE)
STRICT_TAIL_RE = re.compile(r"[.!?:;\)\]\"'\s]*$")
VERDICT_CUE_RE = re.compile(
    r"\b(thus|therefore|so|answer|final|conclusion|answer is|verdict)\b"
    r"[^.\n]{0,30}$", re.IGNORECASE)

# Own name pools (deliberately different from generators/ladders.py and from round 8;
# shared with rounds 21 and 22 so the anchor blobs reproduce).
POOL_A = ("ab", "ed", "ig", "ok", "ul", "ur", "yr", "ov", "ix", "ax",
          "eb", "ic", "ol", "um", "un", "ar", "er", "ir", "or", "uz")
POOL_B = ("bo", "dra", "fo", "gra", "ho", "la", "mo", "ni", "po", "sta",
          "tra", "vo", "xi", "zo", "bru", "kro", "pli", "spo", "tur", "vra")
POOL_C = ("q", "x", "z", "k", "v", "n", "r", "s", "t", "m")

# Per-firing archives of the firings this round joins against, restricted to the 12 panel
# digests and to the fields the analysis needs. Transcribed from the round archives; none of
# the ancestor branches is on main at authoring time, hence transcribed constants: the
# post-merge tree verifies every comparison without them. out_sha is sha256(sanitized content
# + U+0000 + sanitized reasoning) of the final attempt, the quantity TARr is measured on. It is
# present for R37 (where it collapses to two values, see below) and for R38P1; round 31's
# transcription carries no text, so every raw pair involving R31 is non-joinable and is counted
# as such rather than as disagreement. Fields: tok = completion tokens, ans = content_only
# answer (None when the dispatch delivered no answer in the answer field), out = that round's
# own attempt outcome class, fin = finish_reason, dr = distractor-mention ratio, ptok = prompt
# tokens.
R31_PANEL = {
    "b20d7fd289fd6f181fb05aebf9ae6526c041870e09c711ae60a7100cb5ca313b": {"ans": "yes", "arm": "F", "dr": 0.0, "edges": 96, "fin": "stop", "gold": 1, "k": 8, "out": "answered_in_answer_field", "ptok": 1447, "tok": 196},
    "ddb9421bc3e7c63dcae14af51cdb6b5e6347ff569b21683558c0f9fa409b6402": {"ans": "no", "arm": "X", "dr": 0.0, "edges": 96, "fin": "stop", "gold": 0, "k": 8, "out": "answered_in_answer_field", "ptok": 1448, "tok": 300},
    "d2ab3a4e71b559b5605e3689658d8f3dfc93efaf7b6f85e74c246e7674f5ced2": {"ans": "yes", "arm": "F", "dr": 0.0, "edges": 112, "fin": "stop", "gold": 1, "k": 8, "out": "answered_in_answer_field", "ptok": 1693, "tok": 181},
    "31636587257e460c48810a5498e9fee105559cf3425a7262ff909b3a9f8427bc": {"ans": "no", "arm": "X", "dr": 0.0, "edges": 112, "fin": "stop", "gold": 0, "k": 8, "out": "answered_in_answer_field", "ptok": 1693, "tok": 1607},
    "29635c816e9cf67dbcf54cc78b935840e8b8435d079eba3a5ee79ddaf2b2e32d": {"ans": "yes", "arm": "F", "dr": 0.0, "edges": 128, "fin": "stop", "gold": 1, "k": 8, "out": "answered_in_answer_field", "ptok": 1925, "tok": 190},
    "54d8b96f74e74bb2fa315f1de73e5812682def9773dc88843a81e93d62a7be5c": {"ans": "no", "arm": "X", "dr": 0.0, "edges": 128, "fin": "stop", "gold": 0, "k": 8, "out": "answered_in_answer_field", "ptok": 1925, "tok": 383},
    "4ed1d525026f2f7c43149d7ef8d3d5df040b274f830c8f6fb1f1f0788463cb18": {"ans": "yes", "arm": "F", "dr": 0.0, "edges": 160, "fin": "stop", "gold": 1, "k": 8, "out": "answered_in_answer_field", "ptok": 2442, "tok": 202},
    "d548b1f9681cf082174cf141f33e0f34a65b98cf2504111e36284bdf287386cc": {"ans": "no", "arm": "X", "dr": 0.0, "edges": 160, "fin": "stop", "gold": 0, "k": 8, "out": "answered_in_answer_field", "ptok": 2443, "tok": 379},
    "3a378f98a2b0a41f6fef81c7f0529dcb8264e5cea3dacbf45ddef7b25125a873": {"ans": "yes", "arm": "F", "dr": 0.0, "edges": 96, "fin": "stop", "gold": 1, "k": 12, "out": "answered_in_answer_field", "ptok": 1477, "tok": 294},
    "b3e37ce3f7f1df518ccfde8ec1c6831680e23e6fb404ed30bd325d41d7f7e491": {"ans": "no", "arm": "X", "dr": 0.0, "edges": 96, "fin": "stop", "gold": 0, "k": 12, "out": "answered_in_answer_field", "ptok": 1476, "tok": 1181},
    "74388a9a6f4d5549a343593617388774e7adf5dae49681704ac3f3eed7a9c834": {"ans": "yes", "arm": "F", "dr": 0.0, "edges": 96, "fin": "stop", "gold": 1, "k": 16, "out": "answered_in_answer_field", "ptok": 1439, "tok": 310},
    "de5ed21b32895e67bd295d1b63df3245e57634d0b07da4ba92e9442cd1e0fead": {"ans": "no", "arm": "X", "dr": 0.0, "edges": 96, "fin": "stop", "gold": 0, "k": 16, "out": "answered_in_answer_field", "ptok": 1438, "tok": 1284},
}
R37_PANEL = {
    "b20d7fd289fd6f181fb05aebf9ae6526c041870e09c711ae60a7100cb5ca313b": {"ans": "yes", "arm": "F", "dr": 0.0, "edges": 96, "fin": "stop", "gold": 1, "k": 8, "out": "answered_in_answer_field", "out_sha": "e799bb67aa4b0afd1ff76ac661042dd85fa5f19d45d5140dd2204a6c44ae7153", "ptok": 1447, "tok": 1024},
    "ddb9421bc3e7c63dcae14af51cdb6b5e6347ff569b21683558c0f9fa409b6402": {"ans": "no", "arm": "X", "dr": 0.0, "edges": 96, "fin": "stop", "gold": 0, "k": 8, "out": "answered_in_answer_field", "out_sha": "588bf483d9c6a67a40899737e7cc2690b754530a21f36d0a44553c96a562b92c", "ptok": 1448, "tok": 591},
    "d2ab3a4e71b559b5605e3689658d8f3dfc93efaf7b6f85e74c246e7674f5ced2": {"ans": "yes", "arm": "F", "dr": 0.0, "edges": 112, "fin": "stop", "gold": 1, "k": 8, "out": "answered_in_answer_field", "out_sha": "e799bb67aa4b0afd1ff76ac661042dd85fa5f19d45d5140dd2204a6c44ae7153", "ptok": 1693, "tok": 182},
    "31636587257e460c48810a5498e9fee105559cf3425a7262ff909b3a9f8427bc": {"ans": "no", "arm": "X", "dr": 0.0, "edges": 112, "fin": "stop", "gold": 0, "k": 8, "out": "answered_in_answer_field", "out_sha": "588bf483d9c6a67a40899737e7cc2690b754530a21f36d0a44553c96a562b92c", "ptok": 1693, "tok": 770},
    "29635c816e9cf67dbcf54cc78b935840e8b8435d079eba3a5ee79ddaf2b2e32d": {"ans": "yes", "arm": "F", "dr": 0.0, "edges": 128, "fin": "stop", "gold": 1, "k": 8, "out": "answered_in_answer_field", "out_sha": "e799bb67aa4b0afd1ff76ac661042dd85fa5f19d45d5140dd2204a6c44ae7153", "ptok": 1925, "tok": 1355},
    "54d8b96f74e74bb2fa315f1de73e5812682def9773dc88843a81e93d62a7be5c": {"ans": "no", "arm": "X", "dr": 0.0, "edges": 128, "fin": "stop", "gold": 0, "k": 8, "out": "answered_in_answer_field", "out_sha": "588bf483d9c6a67a40899737e7cc2690b754530a21f36d0a44553c96a562b92c", "ptok": 1925, "tok": 746},
    "4ed1d525026f2f7c43149d7ef8d3d5df040b274f830c8f6fb1f1f0788463cb18": {"ans": "yes", "arm": "F", "dr": 0.0, "edges": 160, "fin": "stop", "gold": 1, "k": 8, "out": "answered_in_answer_field", "out_sha": "e799bb67aa4b0afd1ff76ac661042dd85fa5f19d45d5140dd2204a6c44ae7153", "ptok": 2442, "tok": 201},
    "d548b1f9681cf082174cf141f33e0f34a65b98cf2504111e36284bdf287386cc": {"ans": "no", "arm": "X", "dr": 0.0, "edges": 160, "fin": "stop", "gold": 0, "k": 8, "out": "answered_in_answer_field", "out_sha": "588bf483d9c6a67a40899737e7cc2690b754530a21f36d0a44553c96a562b92c", "ptok": 2443, "tok": 419},
    "3a378f98a2b0a41f6fef81c7f0529dcb8264e5cea3dacbf45ddef7b25125a873": {"ans": "yes", "arm": "F", "dr": 0.0, "edges": 96, "fin": "stop", "gold": 1, "k": 12, "out": "answered_in_answer_field", "out_sha": "e799bb67aa4b0afd1ff76ac661042dd85fa5f19d45d5140dd2204a6c44ae7153", "ptok": 1477, "tok": 221},
    "b3e37ce3f7f1df518ccfde8ec1c6831680e23e6fb404ed30bd325d41d7f7e491": {"ans": "no", "arm": "X", "dr": 0.0, "edges": 96, "fin": "stop", "gold": 0, "k": 12, "out": "answered_in_answer_field", "out_sha": "588bf483d9c6a67a40899737e7cc2690b754530a21f36d0a44553c96a562b92c", "ptok": 1476, "tok": 497},
    "74388a9a6f4d5549a343593617388774e7adf5dae49681704ac3f3eed7a9c834": {"ans": "yes", "arm": "F", "dr": 0.0, "edges": 96, "fin": "stop", "gold": 1, "k": 16, "out": "answered_in_answer_field", "out_sha": "e799bb67aa4b0afd1ff76ac661042dd85fa5f19d45d5140dd2204a6c44ae7153", "ptok": 1439, "tok": 325},
    "de5ed21b32895e67bd295d1b63df3245e57634d0b07da4ba92e9442cd1e0fead": {"ans": "no", "arm": "X", "dr": 0.0, "edges": 96, "fin": "stop", "gold": 0, "k": 16, "out": "answered_in_answer_field", "out_sha": "588bf483d9c6a67a40899737e7cc2690b754530a21f36d0a44553c96a562b92c", "ptok": 1438, "tok": 870},
}
# Round 33's P1-equivalent panel records for the 12 panel digests (flash class, the firing of
# 2026-10-28), transcribed from round 38's script (which transcribed them from
# research/nightly-2026-10-28-0400/raw.jsonl, PR #101). Billed tokens and answers only: this
# round uses them for the flash class's own cross-firing floor and the class-identity table.
R33_PANEL = {
    "b20d7fd289fd6f181fb05aebf9ae6526c041870e09c711ae60a7100cb5ca313b": {"ans": "yes", "arm": "F", "dr": 1.0, "edges": 96, "fin": "stop", "gold": 1, "k": 8, "out": "answered_in_answer_field", "out_sha": "8ff08f0d167e8846b8b4f4d5b7fb057a6a16fc76ed832a00b0f1d6c53bbd4b37", "ptok": 1447, "tok": 1087},
    "ddb9421bc3e7c63dcae14af51cdb6b5e6347ff569b21683558c0f9fa409b6402": {"ans": "no", "arm": "X", "dr": 1.0, "edges": 96, "fin": "stop", "gold": 0, "k": 8, "out": "answered_in_answer_field", "out_sha": "f1d28b59eacc80c9436d12d09a4c4845e0c0a7056c5057b59d7aab4f08348649", "ptok": 1448, "tok": 1258},
    "d2ab3a4e71b559b5605e3689658d8f3dfc93efaf7b6f85e74c246e7674f5ced2": {"ans": "yes", "arm": "F", "dr": 1.0, "edges": 112, "fin": "stop", "gold": 1, "k": 8, "out": "answered_in_answer_field", "out_sha": "0ca4bd41185af4a9a5bc7d8ea555db3fe4c81ee38670c15fa73fe898e37d0c67", "ptok": 1693, "tok": 1239},
    "31636587257e460c48810a5498e9fee105559cf3425a7262ff909b3a9f8427bc": {"ans": "no", "arm": "X", "dr": 1.0, "edges": 112, "fin": "stop", "gold": 0, "k": 8, "out": "answered_in_answer_field", "out_sha": "46d291a1c3111d501256c73c1cc108f32c2c3699ee4677ad38a005166170bfac", "ptok": 1693, "tok": 1631},
    "29635c816e9cf67dbcf54cc78b935840e8b8435d079eba3a5ee79ddaf2b2e32d": {"ans": "yes", "arm": "F", "dr": 1.0, "edges": 128, "fin": "stop", "gold": 1, "k": 8, "out": "answered_in_answer_field", "out_sha": "8c0a1920a3426a618a3f25264e72c645d5b5ba8d5f3e9b3a66dba047cc072ffb", "ptok": 1925, "tok": 1389},
    "54d8b96f74e74bb2fa315f1de73e5812682def9773dc88843a81e93d62a7be5c": {"ans": "no", "arm": "X", "dr": 1.0, "edges": 128, "fin": "stop", "gold": 0, "k": 8, "out": "answered_in_answer_field", "out_sha": "cb304e88594a15486e6d38956df96b8e4a813499430bbd67aae3e1a7555c1017", "ptok": 1925, "tok": 1700},
    "4ed1d525026f2f7c43149d7ef8d3d5df040b274f830c8f6fb1f1f0788463cb18": {"ans": "yes", "arm": "F", "dr": 1.0, "edges": 160, "fin": "stop", "gold": 1, "k": 8, "out": "answered_in_answer_field", "out_sha": "378ed863c5981a201a9ccf6ce3e4570139e97f36846f1883ec3b57d6c6e28fd4", "ptok": 2442, "tok": 1756},
    "d548b1f9681cf082174cf141f33e0f34a65b98cf2504111e36284bdf287386cc": {"ans": "no", "arm": "X", "dr": 1.0, "edges": 160, "fin": "stop", "gold": 0, "k": 8, "out": "answered_in_answer_field", "out_sha": "221e3537968a636ec9af373b32cb350b78ce433547820f35259dc1089b324598", "ptok": 2443, "tok": 2043},
    "3a378f98a2b0a41f6fef81c7f0529dcb8264e5cea3dacbf45ddef7b25125a873": {"ans": "yes", "arm": "F", "dr": 1.0, "edges": 96, "fin": "stop", "gold": 1, "k": 12, "out": "answered_in_answer_field", "out_sha": "2c328d98d8352d94f9995bef7ffcdc51664a239933e57d755824a269ac8a12aa", "ptok": 1477, "tok": 1185},
    "b3e37ce3f7f1df518ccfde8ec1c6831680e23e6fb404ed30bd325d41d7f7e491": {"ans": "no", "arm": "X", "dr": 0.989, "edges": 96, "fin": "stop", "gold": 0, "k": 12, "out": "answered_in_answer_field", "out_sha": "0c95a130db9025bdc9ec5135bdca17a1a03c8085233a861d17c0385a8af4cf3c", "ptok": 1476, "tok": 1335},
    "74388a9a6f4d5549a343593617388774e7adf5dae49681704ac3f3eed7a9c834": {"ans": "yes", "arm": "F", "dr": 1.0, "edges": 96, "fin": "stop", "gold": 1, "k": 16, "out": "answered_in_answer_field", "out_sha": "b6cb1564180e15cc1963e0262a86aa397c40c7f8b3515f5558683c08d5121b2d", "ptok": 1439, "tok": 1138},
    "de5ed21b32895e67bd295d1b63df3245e57634d0b07da4ba92e9442cd1e0fead": {"ans": "no", "arm": "X", "dr": 1.0, "edges": 96, "fin": "stop", "gold": 0, "k": 16, "out": "answered_in_answer_field", "out_sha": "19fc9b24ffd8b5410c8f58ca24854558dbf5a95dc44e76d0f7fba119446fcd0f", "ptok": 1438, "tok": 1619},
}
# The exact content strings of round 37's 36 archived records (18 of each), transcribed from
# research/nightly-2026-10-30-0400/raw.jsonl (PR #102): the deployment answered with a bare
# word prefixed by the chat template's trailing newlines and exposed no reasoning text. With
# empty reasoning, output_sha of these strings IS the collapsed pair of hashes above; --selftest
# recomputes both and refuses on drift.
R37_CONTENT_SURFACE = {"yes": 18, "no": 18}
R37_COLLAPSE = {
    "yes": "e799bb67aa4b0afd1ff76ac661042dd85fa5f19d45d5140dd2204a6c44ae7153",
    "no": "588bf483d9c6a67a40899737e7cc2690b754530a21f36d0a44553c96a562b92c",
}

# Round 38's P1 (serialized) records for the 12 panel digests, transcribed from
# research/nightly-2026-10-31-0228/raw.jsonl (PR #103) with full content and reasoning text.
# The flash-next-class firing: the comparator side of every cross-class trace comparison in
# this round. Fields as above plus content/reasoning (full text) and out_sha, which --selftest
# recomputes from the embedded text for all 12 records.
R38P1_PANEL = {
    "29635c816e9cf67dbcf54cc78b935840e8b8435d079eba3a5ee79ddaf2b2e32d": {
        "ans": 'yes',
        "arm": 'F',
        "cell": 'L2',
        "content": 'yes',
        "dr": 1.0,
        "edges": 128,
        "fin": 'stop',
        "gold": 1,
        "k": 8,
        "out_sha": '8c0a1920a3426a618a3f25264e72c645d5b5ba8d5f3e9b3a66dba047cc072ffb',
        "ptok": 1925,
        "reasoning": "We need answer yes/no if ebstas precedes edplir given transitive closure of directed facts. Need analyze carefully. Need produce final exactly one word.\n\nWe need determine if path from ebstas to edplir in directed graph defined by facts, transitive rule. Let's list edges. Need see if ebstas -> ... -> edplir.\n\nFacts:\n1 icdrav -> ovpliz\n2 erkrom -> irstaz\n3 ichoq -> irdraz\n4 ulmox -> yrkrom\n5 igtrak -> edhok\n6 ungrav -> ulbrut\n7 unturv -> okkror\n8 yrtrat -> urhon\n9 irxiv -> urbrux\n10 ungras -> uldran\n11 abkror -> ichoq\n12 ixfoz -> irlaq\n13 ebpon -> axbon\n14 ollam -> orbot\n15 arfor -> ungras\n16 igvor -> arstat\n17 edpov -> arzos\n18 okvom -> uzhon\n19 urhon -> erfov\n20 ergrar -> yrniq\n21 erbos -> iclas\n22 orspoz -> urxiq\n23 erspov -> unbox\n24 erturs -> undraq\n25 okfon -> axxir\n26 ulpot -> ulniz\n27 erzok -> iglat\n28 ulstak -> ovpon\n29 igvov -> oltrax\n30 icnix -> iclaq\n31 undrak -> igvov\n32 icvrat -> ebspok\n33 untrak -> icvom\n34 unfov -> edpov\n35 icstax -> orbruq\n36 orbruq -> arspov\n37 ovstar -> icboz\n38 iglat -> edtran\n39 orstam -> ardran\n40 edzot -> uzkros\n41 yrspok -> edzot\n42 iclas -> abbrux\n43 icvom -> ulstak\n44 undraq -> yrbruk\n45 irturt -> umdrak\n46 orbot -> ulpot\n47 ebpor -> ebzok\n48 arvom -> icnix\n49 abvon -> arvom\n50 yrkrom -> ergrar\n51 olhoz -> axmok\n52 uzfom -> yrspok\n53 okvraq -> ovxis\n54 unbor -> irturt\n55 axhov -> igxix\n56 ovbruz -> uzfom\n57 axbon -> arkros\n58 ovxis -> axlak\n59 okfok -> abkror\n60 ictrak -> okpot\n61 uzhot -> axpor\n62 axmok -> irfon\n63 ermoq -> ebxiv\n64 edtran -> ovstar\n65 irlaq -> okbrut\n66 orkron -> unbor\n67 axlak -> uzhot\n68 uzfok -> abvon\n69 ovpliz -> orfok\n70 erfov -> axhov\n71 icboz -> yrxim\n72 abturv -> axbov\n73 edvrar -> edspok\n74 arkros -> icxin\n75 irdraz -> igtrak\n76 yrbruk -> urboz\n77 okbrut -> icstak\n78 ovpon -> okdrax\n79 abturx -> ulmox\n80 umlas -> orkron\n81 ixhot -> ermoq\n82 abbrux -> okfon\n83 okpot -> edplir\n84 axxir -> erturs\n85 ebpox -> orstam\n86 axmon -> icvrat\n87 ebzok -> urstaz\n88 irfon -> uzfok\n89 okkror -> ixfoz\n90 abturm -> okfok\n91 unspov -> ednin\n92 ulniz -> untrak\n93 umdrak -> arkrov\n94 urbrux -> ixlas\n95 ixlas -> erfox\n96 igxix -> ebpox\n97 arzos -> orspoz\n98 ebgram -> erspov\n99 unbox -> abturx\n100 ardran -> okboz\n101 abvox -> unspov\n102 ednin -> ungrav\n103 urxiq -> erlam\n104 uldran -> ovbruz\n105 axpor -> ictrak\n106 ullax -> irxiv\n107 ixspom -> erkrom\n108 axbov -> ixspom\n109 erlam -> abmor\n110 ebstas -> okvraq\n111 erfot -> abturv\n112 oltrax -> ixhot\n113 arspov -> undrak\n114 orturs -> unfov\n115 erfox -> ulkros\n116 ulbrut -> ebpon\n117 edspok -> abturm\n118 urstaz -> unturv\n119 ebspok -> erfot\n120 orfok -> erzok\n121 arstat -> olzom\n122 yrniq -> uzpon\n123 arkrov -> igvor\n124 umgraq -> okvom\n125 uzkros -> yrgrak\n126 abmor -> igbon\n127 uzhon -> ullax\n128 yrnin -> olhoz\n\nNeed path from ebstas. Edge 110: ebstas -> okvraq. Then 53: okvraq -> ovxis. 58: ovxis -> axlak. 67: axlak -> uzhot. 61: uzhot -> axpor. 105: axpor -> ictrak. 60: ictrak -> okpot. 83: okpot -> edplir. So yes. Need ensure no missing? All direct facts. Transitive closure yes. Answer yes.\n\nNeed final exactly one word: yes. Ensure no extra.",
        "tok": 1389
    },
    "31636587257e460c48810a5498e9fee105559cf3425a7262ff909b3a9f8427bc": {
        "ans": 'no',
        "arm": 'X',
        "cell": 'L1',
        "content": 'no',
        "dr": 1.0,
        "edges": 112,
        "fin": 'stop',
        "gold": 0,
        "k": 8,
        "out_sha": '46d291a1c3111d501256c73c1cc108f32c2c3699ee4677ad38a005166170bfac',
        "ptok": 1693,
        "reasoning": "We need answer yes/no if olplik precedes umpoq given transitive rule and direct facts. Need compute reachability from olplik to umpoq. Let's parse facts as directed edges. Need determine if path exists from olplik to umpoq.\n\nWe can manually trace. Need be careful. Let's list edges:\n1 axpliq -> ovvor\n2 icturr -> unvon\n3 abpok -> urxit\n4 orxix -> ebstaz\n5 yrstak -> ergrav\n6 arturt -> erxim\n7 abbruq -> ebbrus\n8 axstax -> axhot\n9 urvrak -> uzturk\n10 igkrom -> untrav\n11 ulstav -> axdram\n12 urxit -> olmor\n13 axpok -> erdrav\n14 okhov -> ebspoz\n15 urvrax -> ornik\n16 igtrar -> ovbrut\n17 abbruk -> axstax\n18 uzlan -> ungrat\n19 ulzox -> edstaz\n20 unspox -> ovxir\n21 ovtrar -> orgras\n22 umturv -> yrxiv\n23 ebniv -> irplit\n24 unvraq -> urvrax\n25 irvran -> orlat\n26 irbrux -> ermoq\n27 urkroz -> edfon\n28 icnin -> icpor\n29 unfoz -> axpoz\n30 umstan -> igdrax\n31 yrxiv -> arfon\n32 ovturz -> abbruk\n33 uzhot -> edgran\n34 arkrov -> unspox\n35 erxim -> okhov\n36 ovxiz -> irplix\n37 urhot -> icturr\n38 okpom -> arpoq\n39 ebstaz -> orvraq\n40 ovvor -> umturv\n41 yrmor -> ulbrus\n42 unvon -> olstat\n43 erdrav -> uzzor\n44 icdrar -> edzov\n45 arturv -> ixturs\n46 icfoz -> yrbos\n47 axhot -> arturt\n48 igbor -> icfoz\n49 ichoz -> abpok\n50 edstaz -> edfos\n51 ebkron -> igkrom\n52 okniz -> ignir\n53 igspor -> irvran\n54 ornik -> icdrar\n55 orvraq -> ixxim\n56 abmor -> ixxin\n57 edzov -> irtrax\n58 uzturk -> edvraz\n59 ardraq -> ixfov\n60 unfok -> umpoq\n61 orzoq -> okniz\n62 olspoq -> olbov\n63 irgraq -> igpos\n64 icvoz -> arkrov\n65 ignir -> ichoz\n66 ungrat -> ardraq\n67 iczom -> uzhot\n68 ulbov -> axpok\n69 olmor -> ablat\n70 ovbruk -> yrvoz\n71 igspov -> ixbrun\n72 ovmon -> iczom\n73 ummor -> unfok\n74 edvraz -> irvras\n75 igzor -> urkroz\n76 ixzot -> abbruq\n77 igpos -> ixzot\n78 yrplim -> urvrak\n79 ergrav -> okpom\n80 axdram -> orbox\n81 ixbrun -> igtrar\n82 orgran -> olspok\n83 arfon -> ulbov\n84 irnim -> ovtrar\n85 orgras -> unvraq\n86 yrpon -> yrmor\n87 ovbrut -> yrfom\n88 orlat -> irgraq\n89 olplik -> ovturz\n90 olbov -> orgran\n91 ablat -> igpoz\n92 icpor -> ovmon\n93 ebbrus -> ixspom\n94 edfon -> unfoz\n95 ixfov -> igbor\n96 yrvoz -> ebniv\n97 irpliz -> yrturn\n98 edgran -> ummor\n99 yrbos -> umstan\n100 olspok -> orturm\n101 arpoq -> yrplim\n102 orbox -> ebkron\n103 ovxir -> igspov\n104 ermoq -> abmor\n105 ixturs -> olspoq\n106 untrav -> ulzox\n107 ixxin -> urhot\n108 orturm -> ovxiz\n109 ulbrus -> irpliz\n110 yrturn -> orxix\n111 axpoz -> ovbruk\n112 olstat -> ummoq\n\nQuestion: olplik precedes umpoq? Need path from olplik to umpoq. Start olplik -> ovturz (89). ovturz -> abbruk (32). abbruk -> axstax (17). axstax -> axhot (8). axhot -> arturt (47). arturt -> erxim (6). erxim -> okhov (35). okhov -> ebspoz (14). ebspoz no outgoing? Not in list. Dead.\n\nNeed see if any alternative from olplik? Only one outgoing. So path is deterministic chain until ebspoz. Does ebspoz lead to umpoq? No outgoing. So no? But maybe transitive closure could have other branches? Let's check if any edge from ebspoz? Search facts: ebspoz appears only Fact14 okhov precedes ebspoz. No outgoing. So no path to umpoq. But need ensure no other path from olplik via other nodes? olplik only edge to ovturz. ovturz only edge to abbruk? Check ovturz appears Fact32 ovturz precedes abbruk; also maybe incoming from olplik. No other outgoing. abbruk outgoing Fact17 axstax. axstax outgoing Fact8 axhot. axhot outgoing Fact47 arturt. arturt outgoing Fact6 erxim. erxim outgoing Fact35 okhov. okhov outgoing Fact14 ebspoz. ebspoz no outgoing. So no.\n\nBut wait maybe there is a path from olplik to umpoq via some other chain if some node has multiple outgoing? We need check all nodes in chain for multiple outgoing. Let's scan facts for each:\nolplik: only 89.\novturz: only 32.\nabbruk: only 17.\naxstax: only 8.\naxhot: only 47.\narturt: only 6.\nerxim: only 35.\nokhov: only 14.\nebspoz: none.\nThus no.\n\nNeed answer exactly one word: no. Ensure no hidden transitive from ebspoz? no.\n\nDouble-check if umpoq has incoming only unfok -> umpoq (60). To reach umpoq need reach unfok. Could chain reach unfok? Our chain doesn't. Could there be path from ebspoz to something? no. So no.\n\nNeed final only no.",
        "tok": 1631
    },
    "3a378f98a2b0a41f6fef81c7f0529dcb8264e5cea3dacbf45ddef7b25125a873": {
        "ans": 'yes',
        "arm": 'F',
        "cell": 'D1',
        "content": 'yes',
        "dr": 1.0,
        "edges": 96,
        "fin": 'stop',
        "gold": 1,
        "k": 12,
        "out_sha": '2c328d98d8352d94f9995bef7ffcdc51664a239933e57d755824a269ac8a12aa',
        "ptok": 1477,
        "reasoning": "We need answer yes/no if ebplit precedes ixplix given transitive rule and direct facts. Need analyze graph. Need be careful. We can manually trace. Need determine if path from ebplit to ixplix via directed edges. Facts list direct precedes. Rule transitive closure. Need answer exactly one word.\n\nLet's parse facts as edges:\n1 ixkrov -> irxik\n2 irxiq -> abkror\n3 umniq -> yrxit\n4 edplim -> yrbov\n5 ebspor -> yrvrar\n6 erxiq -> umnir\n7 abgras -> orlar\n8 irvos -> erspok\n9 artrav -> yrlas\n10 ernis -> ebdrak\n11 arstat -> okplis\n12 icgrax -> ulstar\n13 ulstar -> umspos\n14 urlaq -> ebspor\n15 erbruz -> ixplix\n16 irbrun -> urlas\n17 erkron -> ergras\n18 ixmov -> orhox\n19 yrbov -> edvrat\n20 umspok -> ixmov\n21 urlas -> irvrax\n22 orhox -> icfon\n23 ebkror -> icturq\n24 orvram -> artrav\n25 igzox -> ebkrot\n26 ixpos -> orkroq\n27 yrxit -> ovpov\n28 ulxiv -> ulgram\n29 abspor -> ardras\n30 ebhoz -> okkroq\n31 axgras -> irbox\n32 okkroq -> icpos\n33 arbos -> umniq\n34 uzkroz -> abzoq\n35 orkroq -> edvoz\n36 axspoz -> edvran\n37 irspom -> axvrav\n38 uzvram -> unxit\n39 icgras -> irbov\n40 ebplit -> ebkror\n41 axplin -> ixkrov\n42 umspos -> orzor\n43 urxis -> urfoz\n44 ummok -> ulxiv\n45 icxim -> ixkrox\n46 ulgram -> ummos\n47 ardras -> edplim\n48 abkror -> arplir\n49 edvrat -> icxim\n50 ebdras -> axplin\n51 yrturm -> arxix\n52 ixkrox -> erxiq\n53 axvrav -> ernis\n54 irxik -> yrturm\n55 yrlas -> ungraz\n56 olvrar -> ebvok\n57 edvoz -> irvos\n58 edzov -> erstan\n59 erstan -> ulstas\n60 argrar -> icgrax\n61 abzoq -> urlaq\n62 okgraz -> urxis\n63 erbot -> edbruz\n64 ergras -> unpliz\n65 igbruk -> orvram\n66 ulstas -> irbrun\n67 ixkroq -> igbruk\n68 icturq -> uzkroz\n69 unpliz -> edzot\n70 ebvok -> umspok\n71 urfoz -> abgras\n72 umspox -> uzbor\n73 orlar -> erbot\n74 yrspoz -> icgras\n75 okplis -> ummok\n76 edvran -> ixkroq\n77 irvrax -> ebdras\n78 arplir -> erbruz\n79 arvox -> uzvram\n80 orzor -> umdram\n81 arxix -> ulnik\n82 edzot -> umkron\n83 ungraz -> ebhoz\n84 arturt -> arvox\n85 edbruz -> argrar\n86 ebdrak -> arturt\n87 ummos -> umspox\n88 yrvrar -> irxiq\n89 ebkrot -> ixpos\n90 irbov -> irspom\n91 icfon -> igzox\n92 icpos -> axgras\n93 umkron -> arstat\n94 ovpov -> abspor\n95 irvok -> arfor\n96 arfor -> yrspoz\n\nNeed path ebplit -> ... -> ixplix. Start ebplit edge 40 -> ebkror. ebkror -> icturq (23). icturq -> uzkroz (68). uzkroz -> abzoq (34). abzoq -> urlaq (61). urlaq -> ebspor (14). ebspor -> yrvrar (5). yrvrar -> irxiq (88). irxiq -> abkror (2). abkror -> arplir (48). arplir -> erbruz (78). erbruz -> ixplix (15). So yes. Need ensure no typo: Fact 2 irxiq precedes abkror, yes. Fact 48 abkror precedes arplir. Fact 78 arplir precedes erbruz. Fact 15 erbruz precedes ixplix. Path exists. Answer yes. Need exactly one word. final yes.",
        "tok": 1185
    },
    "4ed1d525026f2f7c43149d7ef8d3d5df040b274f830c8f6fb1f1f0788463cb18": {
        "ans": 'yes',
        "arm": 'F',
        "cell": 'L3',
        "content": 'yes',
        "dr": 1.0,
        "edges": 160,
        "fin": 'stop',
        "gold": 1,
        "k": 8,
        "out_sha": '378ed863c5981a201a9ccf6ce3e4570139e97f36846f1883ec3b57d6c6e28fd4',
        "ptok": 2442,
        "reasoning": "We need answer yes/no if ebspot precedes igturv given transitive closure of directed facts. Need analyze carefully. We can manually trace graph. Need final exactly one word.\n\nWe need determine if path from ebspot to igturv. Facts direct edges. Rule transitive. Need see if ebspot -> ... -> igturv.\n\nLet's list relevant edges. We can build graph mentally.\n\nFacts:\n1 iclav -> abdrav\n2 yrlam -> uzgrak\n3 igkrok -> icbrun\n4 uzbom -> yrbon\n5 edgrav -> yrfor\n6 icbrun -> icdram\n7 abkrov -> igstaz\n8 irlas -> eddram\n9 ulgrav -> umkroq\n10 unvok -> igkrok\n11 abspoz -> igzoq\n12 urmok -> ixstam\n13 unzox -> iclaq\n14 igvox -> ullar\n15 arpliv -> okdrat\n16 igmox -> abspoz\n17 erturm -> oklav\n18 ixxiz -> ixkrox\n19 edplim -> ovmon\n20 unkror -> unvok\n21 irbrum -> uzpoq\n22 ernik -> olnit\n23 ergraq -> yrkroq\n24 ixvrak -> edvrax\n25 yrzov -> ebzoq\n26 orxis -> unspox\n27 ebnis -> ovlax\n28 yrfor -> uzmov\n29 ormox -> ormot\n30 umfoq -> irbrum\n31 urplis -> unkror\n32 abdrav -> olnim\n33 urtras -> abgram\n34 abvor -> arpliv\n35 erxiq -> oknis\n36 olbrut -> olxiz\n37 unspox -> uzhor\n38 edvov -> orbon\n39 erlat -> axkrok\n40 yrbon -> ovmom\n41 urboq -> edgrav\n42 ulniz -> ordras\n43 ovmon -> ernik\n44 edvor -> urboq\n45 icdram -> umspoz\n46 ovlax -> umfoq\n47 eddram -> yrvom\n48 yrvom -> olxit\n49 olkror -> ebgrar\n50 artraz -> axpoz\n51 olniz -> yrfon\n52 ebstas -> axmom\n53 ebvox -> abhox\n54 igbor -> urspon\n55 uzdrax -> unzox\n56 uldraq -> iglav\n57 irboz -> ulhom\n58 irfom -> arhot\n59 irgrat -> yrlam\n60 urkrom -> okgraz\n61 irbruz -> uztraq\n62 ulbruv -> erkroq\n63 ebbrux -> olkror\n64 abgram -> irfom\n65 axkrok -> orxis\n66 uzpoq -> ixgram\n67 arkroq -> unplin\n68 axmom -> irspox\n69 okgraz -> erxiq\n70 orxiv -> umstak\n71 unplin -> icnir\n72 ixstam -> ebnis\n73 erpos -> yrzov\n74 ernit -> irbruz\n75 olxiz -> igvox\n76 iglas -> ernit\n77 olbom -> irdraq\n78 undras -> ebturk\n79 abspox -> arvom\n80 umxit -> okturv\n81 axturq -> urtras\n82 ulhom -> erstak\n83 abspot -> urboz\n84 uztraq -> axkrot\n85 erpot -> orhot\n86 ordras -> olmon\n87 ebspot -> igmox\n88 icplik -> oktrar\n89 igbot -> axzoq\n90 ebgrar -> axpon\n91 umgrav -> uzdrax\n92 ulxix -> urkrom\n93 igtram -> uzmox\n94 umniq -> ergrak\n95 abmov -> ebvox\n96 oklav -> umgrav\n97 ertraz -> erpos\n98 olnim -> axturq\n99 edxiz -> olbrut\n100 ormot -> ixxik\n101 oktrar -> igtram\n102 umspoz -> abspox\n103 ictrax -> icplik\n104 igfom -> erlat\n105 abhox -> ovstak\n106 erbox -> umxit\n107 urboz -> ebstas\n108 ovhoq -> olplik\n109 ebzoq -> iglas\n110 olpoz -> ebtrax\n111 ixxiq -> arspor\n112 ixxik -> ebbrux\n113 arhot -> ermon\n114 ixpok -> ovhoq\n115 axzoq -> abpot\n116 axstas -> umpox\n117 yrbrun -> igturv\n118 urspon -> abkrov\n119 ovstak -> uzbom\n120 arvrak -> uldraq\n121 orhot -> ixpok\n122 olxit -> edplim\n123 ovmom -> yrkrov\n124 yrfon -> uzkroz\n125 olplis -> ictrax\n126 axpoz -> ovvoz\n127 yrkrov -> urnik\n128 ullar -> ebplis\n129 oknis -> ulzok\n130 axpon -> ergraq\n131 ebturk -> irgrat\n132 ebplis -> igbot\n133 olplik -> irboz\n134 orbon -> ulbruv\n135 ebtrax -> ulxir\n136 iglav -> igpoz\n137 ixkrox -> erbox\n138 uzmov -> olbom\n139 arspor -> olplis\n140 irbom -> igfom\n141 olnit -> unvraz\n142 erstak -> umdrav\n143 igkror -> ollan\n144 igpoz -> ixxiz\n145 erkroq -> ixvrak\n146 iclaq -> abvor\n147 olmon -> yrbrun\n148 ergrak -> ulgrav\n149 igstaz -> olpoz\n150 umkroq -> undras\n151 irspox -> arkroq\n152 ulzok -> artraz\n153 uzkroz -> edvov\n154 arstav -> abspot\n155 umstak -> irbom\n156 ollan -> igbor\n157 erturq -> urmok\n158 igzoq -> ulniz\n159 umpox -> edvor\n160 uzmox -> ollar\n\nNeed path ebspot -> igturv. Start ebspot -> igmox (87). igmox -> abspoz (16). abspoz -> igzoq (11). igzoq -> ulniz (158). ulniz -> ordras (42). ordras -> olmon (86). olmon -> yrbrun (147). yrbrun -> igturv (117). Yes. Need ensure no missing? All direct edges. So yes.\n\nNeed final exactly one word: yes. Ensure no extra.",
        "tok": 1756
    },
    "54d8b96f74e74bb2fa315f1de73e5812682def9773dc88843a81e93d62a7be5c": {
        "ans": 'no',
        "arm": 'X',
        "cell": 'L2',
        "content": 'no',
        "dr": 1.0,
        "edges": 128,
        "fin": 'stop',
        "gold": 0,
        "k": 8,
        "out_sha": 'cb304e88594a15486e6d38956df96b8e4a813499430bbd67aae3e1a7555c1017',
        "ptok": 1925,
        "reasoning": "We need answer yes/no if ebstas precedes yrxim given transitive rule and direct facts. Need compute reachability. Need be careful. Let's parse facts as directed edges. Need determine if path from ebstas to yrxim.\n\nWe can manually trace. Need maybe build graph. Let's list edges:\n1 icdrav -> ovpliz\n2 erkrom -> irstaz\n3 ichoq -> irdraz\n4 ulmox -> yrkrom\n5 igtrak -> edhok\n6 ungrav -> ulbrut\n7 unturv -> okkror\n8 yrtrat -> urhon\n9 irxiv -> urbrux\n10 ungras -> uldran\n11 abkror -> ichoq\n12 ixfoz -> irlaq\n13 ebpon -> axbon\n14 ollam -> orbot\n15 arfor -> ungras\n16 igvor -> arstat\n17 edpov -> arzos\n18 okvom -> uzhon\n19 urhon -> erfov\n20 ergrar -> yrniq\n21 erbos -> iclas\n22 orspoz -> urxiq\n23 erspov -> unbox\n24 erturs -> undraq\n25 okfon -> axxir\n26 ulpot -> ulniz\n27 erzok -> iglat\n28 ulstak -> ovpon\n29 igvov -> oltrax\n30 icnix -> iclaq\n31 undrak -> igvov\n32 icvrat -> ebspok\n33 untrak -> icvom\n34 unfov -> edpov\n35 icstax -> orbruq\n36 orbruq -> arspov\n37 ovstar -> icboz\n38 iglat -> edtran\n39 orstam -> ardran\n40 edzot -> uzkros\n41 yrspok -> edzot\n42 iclas -> abbrux\n43 icvom -> ulstak\n44 undraq -> yrbruk\n45 irturt -> umdrak\n46 orbot -> ulpot\n47 ebpor -> ebzok\n48 arvom -> icnix\n49 abvon -> arvom\n50 yrkrom -> ergrar\n51 olhoz -> axmok\n52 uzfom -> yrspok\n53 okvraq -> ovxis\n54 unbor -> irturt\n55 axhov -> igxix\n56 ovbruz -> uzfom\n57 axbon -> arkros\n58 ovxis -> axlak\n59 okfok -> abkror\n60 ictrak -> okpot\n61 uzhot -> axpor\n62 axmok -> irfon\n63 ermoq -> ebxiv\n64 edtran -> ovstar\n65 irlaq -> okbrut\n66 orkron -> unbor\n67 axlak -> uzhot\n68 uzfok -> abvon\n69 ovpliz -> orfok\n70 erfov -> axhov\n71 icboz -> yrxim\n72 abturv -> axbov\n73 edvrar -> edspok\n74 arkros -> icxin\n75 irdraz -> igtrak\n76 yrbruk -> urboz\n77 okbrut -> icstak\n78 ovpon -> okdrax\n79 abturx -> ulmox\n80 umlas -> orkron\n81 ixhot -> ermoq\n82 abbrux -> okfon\n83 okpot -> edplir\n84 axxir -> erturs\n85 ebpox -> orstam\n86 axmon -> icvrat\n87 ebzok -> urstaz\n88 irfon -> uzfok\n89 okkror -> ixfoz\n90 abturm -> okfok\n91 unspov -> ednin\n92 ulniz -> untrak\n93 umdrak -> arkrov\n94 urbrux -> ixlas\n95 ixlas -> erfox\n96 igxix -> ebpox\n97 arzos -> orspoz\n98 ebgram -> erspov\n99 unbox -> abturx\n100 ardran -> okboz\n101 abvox -> unspov\n102 ednin -> ungrav\n103 urxiq -> erlam\n104 uldran -> ovbruz\n105 axpor -> ictrak\n106 ullax -> irxiv\n107 ixspom -> erkrom\n108 axbov -> ixspom\n109 erlam -> abmor\n110 ebstas -> okvraq\n111 erfot -> abturv\n112 oltrax -> ixhot\n113 arspov -> undrak\n114 orturs -> unfov\n115 erfox -> ulkros\n116 ulbrut -> ebpon\n117 edspok -> abturm\n118 urstaz -> unturv\n119 ebspok -> erfot\n120 orfok -> erzok\n121 arstat -> olzom\n122 yrniq -> uzpon\n123 arkrov -> igvor\n124 umgraq -> okvom\n125 uzkros -> yrgrak\n126 abmor -> igbon\n127 uzhon -> ullax\n128 yrnin -> olhoz\n\nNeed path ebstas -> ... -> yrxim. Start ebstas edge 110: ebstas -> okvraq.\nokvraq -> ovxis (53)\novxis -> axlak (58)\naxlak -> uzhot (67)\nuzhot -> axpor (61)\naxpor -> ictrak (105)\nictrak -> okpot (60)\nokpot -> edplir (83). Dead? edplir no outgoing. So this branch dead.\n\nAny other outgoing from ebstas? only 110. So if no other path, answer no. But need ensure maybe transitive via other chains? Starting only okvraq. okvraq only ovxis. ovxis only axlak. axlak only uzhot. uzhot only axpor. axpor only ictrak. ictrak only okpot. okpot only edplir. edplir no outgoing. So no yrxim. But let's double-check facts: ebstas precedes okvraq. okvraq precedes ovxis. ovxis precedes axlak. axlak precedes uzhot. uzhot precedes axpor. axpor precedes ictrak. ictrak precedes okpot. okpot precedes edplir. No edge to yrxim. yrxim reached from icboz (71). icboz from ovstar (37). ovstar from edtran (64). edtran from iglat (38). iglat from erzok (27). erzok from orfok (120). orfok from ovpliz (69). ovpliz from icdrav (1). No connection from ebstas branch. Also yrxim maybe from? only icboz -> yrxim. So no.\n\nNeed answer exactly one word yes/no. final: no. Ensure no hidden path via edplir? none. Could there be reverse? Rule only if x precedes y and y precedes z then x precedes z, directed. No.\n\nNeed final only no.",
        "tok": 1700
    },
    "74388a9a6f4d5549a343593617388774e7adf5dae49681704ac3f3eed7a9c834": {
        "ans": 'yes',
        "arm": 'F',
        "cell": 'D2',
        "content": 'yes',
        "dr": 1.0,
        "edges": 96,
        "fin": 'stop',
        "gold": 1,
        "k": 16,
        "out_sha": 'b6cb1564180e15cc1963e0262a86aa397c40c7f8b3515f5558683c08d5121b2d',
        "ptok": 1439,
        "reasoning": "We need answer yes/no if orvor precedes orbruq given transitive rule and direct facts. Need analyze graph. Need determine if path from orvor to orbruq via directed edges. Let's parse facts. Need be careful. We can manually trace.\n\nFacts:\n1 irzos -> ovhos\n2 umturt -> ulxit\n3 arkrox -> erstaq\n4 irvon -> unhoz\n5 edmov -> olfom\n6 orspor -> abmov\n7 uzbruz -> edxim\n8 erlaq -> ixvom\n9 olpliv -> ebhor\n10 uzfok -> yrlat\n11 ovvran -> arstaz\n12 edxim -> edmov\n13 ulpom -> iglas\n14 uzdraz -> irpox\n15 olplik -> erfot\n16 ovbox -> umstak\n17 urnir -> igvram\n18 arspon -> olbruv\n19 erstaq -> uzturk\n20 arvoz -> ebzom\n21 arstaz -> ixhos\n22 irpox -> unpov\n23 orlat -> olpliv\n24 ebspoz -> ixkrov\n25 umturv -> uzbruz\n26 orvor -> orgras\n27 abbon -> abnix\n28 ovhos -> uzvran\n29 iglas -> ovgrav\n30 ixstav -> arspos\n31 olmon -> ovgras\n32 yrgran -> edstar\n33 edvran -> olplik\n34 ovzox -> orlat\n35 ixkroz -> uzkror\n36 uzturk -> yrvon\n37 abbor -> ormoq\n38 edstar -> igdrax\n39 abstaq -> urmox\n40 arvran -> yrpon\n41 igbor -> edhom\n42 irbrux -> urdrar\n43 ulplim -> ovzox\n44 igxin -> ulpom\n45 okbruq -> erspor\n46 armor -> ovbox\n47 umstak -> edvran\n48 igdrax -> abmox\n49 ormox -> irbrux\n50 ulxit -> orbruq\n51 urmox -> olmon\n52 olfom -> irzos\n53 arzor -> igxin\n54 erspor -> icplin\n55 ormoq -> yrturs\n56 ulhoq -> abbor\n57 uzkror -> irvon\n58 ebstas -> ixxiv\n59 ixkrov -> ormox\n60 yrvon -> orspor\n61 ebzom -> ixstav\n62 ixhos -> umturt\n63 olbruv -> arvoz\n64 yrpon -> okplim\n65 ebhor -> ovvran\n66 edhom -> ebstas\n67 urdrar -> yrgran\n68 iglan -> ixspok\n69 yrturs -> iclat\n70 ertrat -> okbruq\n71 uzkrom -> uzdraz\n72 unhoz -> abstaq\n73 igmot -> oltraq\n74 abnix -> olstas\n75 olstas -> ixkroz\n76 ovgrav -> ertrat\n77 igturx -> arkrox\n78 oltraq -> ebspoz\n79 iclat -> edhon\n80 icplin -> igturx\n81 yrlat -> urnir\n82 okgraz -> ulhoq\n83 orgras -> unlar\n84 unlar -> iglan\n85 erfot -> okgraz\n86 uzvran -> igbor\n87 ixxiv -> uzkrom\n88 ixspok -> urxiz\n89 ovgras -> iggram\n90 okplim -> abbon\n91 arspos -> igmot\n92 igvram -> armor\n93 unpov -> uzkrov\n94 urxiz -> ulplim\n95 ordraq -> arzor\n96 ixvom -> arvran\n\nQuestion: orvor precedes orbruq? Need path from orvor to orbruq.\n\nStart orvor -> orgras (26). orgras -> unlar (83). unlar -> iglan (84). iglan -> ixspok (68). ixspok -> urxiz (88). urxiz -> ulplim (94). ulplim -> ovzox (43). ovzox -> orlat (34). orlat -> olpliv (23). olpliv -> ebhor (9). ebhor -> ovvran (65). ovvran -> arstaz (11). arstaz -> ixhos (21). ixhos -> umturt (62). umturt -> ulxit (2). ulxit -> orbruq (50). Yes path exists. Need answer exactly one word yes. Ensure no hidden issue: rule transitive, facts direct. Yes.\n\nNeed final only yes. But ensure no need mention. final: yes.",
        "tok": 1138
    },
    "b20d7fd289fd6f181fb05aebf9ae6526c041870e09c711ae60a7100cb5ca313b": {
        "ans": 'yes',
        "arm": 'F',
        "cell": 'L0',
        "content": 'yes',
        "dr": 1.0,
        "edges": 96,
        "fin": 'stop',
        "gold": 1,
        "k": 8,
        "out_sha": '7942c07845ce8151aa0aa76e37b077922b62ec6e57b7452aa9c8e5e1a8087ef0',
        "ptok": 1447,
        "reasoning": "We need answer yes/no based on transitive closure of directed graph facts. Need determine if yrvok precedes ulnix via chain. Need analyze carefully.\n\nWe have rule transitive: if x precedes y and y precedes z then x precedes z. Facts direct. Need see if path from yrvok to ulnix.\n\nLet's list edges:\n1 igniv -> unbon\n2 ovkrox -> axtras\n3 ulzom -> ablav\n4 ulfok -> yrlav\n5 uzzon -> ixpoz\n6 unspon -> urhom\n7 ixpoz -> urxir\n8 iglar -> orxiz\n9 umturn -> ortraq\n10 yrvok -> abniq\n11 icvom -> umturn\n12 ebstam -> unvraq\n13 icxik -> axspom\n14 ovhot -> ixtraz\n15 axbrux -> ulfok\n16 okmom -> edlar\n17 axturx -> axvrav\n18 ortraq -> ebbot\n19 umhoz -> yrkroz\n20 igplit -> olpov\n21 eblaq -> erspon\n22 erplis -> orturv\n23 erfot -> ixhok\n24 okmon -> uzzon\n25 ovbot -> orgrat\n26 unvraq -> irpon\n27 umvrat -> icfov\n28 abbruq -> uzlan\n29 irdras -> ulzom\n30 orxiv -> ermon\n31 ormos -> edgraq\n32 axspom -> orxiv\n33 urvos -> icxik\n34 erturm -> ignik\n35 abnin -> uzplir\n36 ignik -> urbot\n37 orvos -> umvrat\n38 eblat -> arvram\n39 uzturm -> ulturq\n40 unmom -> umhoz\n41 ixnis -> ovlak\n42 orturv -> yrturk\n43 orpor -> ovbot\n44 ixlak -> igniv\n45 yrturk -> icvrak\n46 okspox -> unmom\n47 irhon -> okvoz\n48 ixpliq -> ulnix\n49 irmoz -> ovhot\n50 ovhoz -> unspon\n51 erbruz -> irhon\n52 icvrak -> irdras\n53 orxiz -> ulplim\n54 edlar -> igtras\n55 ulvon -> eblat\n56 yrlav -> iglaq\n57 edgraq -> axbrux\n58 igturm -> ebstam\n59 irturm -> eblaq\n60 uzplir -> erplis\n61 irpon -> irmoz\n62 ebtraq -> irturm\n63 axtras -> ixnis\n64 icxiz -> erturm\n65 ixhok -> icxiz\n66 igzon -> ednit\n67 erplir -> urvos\n68 uzlan -> erplir\n69 uzgras -> orpor\n70 iclat -> igzox\n71 olfoz -> icvom\n72 unbon -> axturx\n73 okvoz -> ixlak\n74 yrkroz -> igzon\n75 icplir -> axplit\n76 arvram -> ebtraq\n77 ulturq -> orvos\n78 abniq -> ovhoz\n79 igpov -> uzturm\n80 uzxiq -> abbruq\n81 erfok -> ixpliq\n82 erspon -> iclat\n83 ednit -> okmom\n84 ovlak -> olfoz\n85 icfov -> erfon\n86 ixstak -> icplir\n87 urhom -> okvrat\n88 icnis -> uzgras\n89 axplit -> ormos\n90 yrspok -> erbruz\n91 erfon -> uztran\n92 orgrat -> okmon\n93 okvrat -> erfok\n94 ixtraz -> igplit\n95 ulplim -> erfot\n96 umbruv -> igpov\n\nNeed path yrvok -> ... -> ulnix. Start yrvok -> abniq -> ovhoz -> unspon -> urhom -> okvrat -> erfok -> ixpliq -> ulnix. Check edges:\n10 yrvok -> abniq yes.\n78 abniq -> ovhoz yes.\n50 ovhoz -> unspon yes.\n6 unspon -> urhom yes.\n87 urhom -> okvrat yes.\n93 okvrat -> erfok yes.\n81 erfok -> ixpliq yes.\n48 ixpliq -> ulnix yes.\nThus yes. Need answer exactly one word yes. Ensure no hidden issue: direct links and transitive. Yes.\n\nFinal: yes.",
        "tok": 1101
    },
    "b3e37ce3f7f1df518ccfde8ec1c6831680e23e6fb404ed30bd325d41d7f7e491": {
        "ans": 'no',
        "arm": 'X',
        "cell": 'D1',
        "content": 'no',
        "dr": 0.989,
        "edges": 96,
        "fin": 'stop',
        "gold": 0,
        "k": 12,
        "out_sha": '0c95a130db9025bdc9ec5135bdca17a1a03c8085233a861d17c0385a8af4cf3c',
        "ptok": 1476,
        "reasoning": "We need answer yes/no if ebplit precedes ulnik given transitive rule and facts direct links. Need compute reachability. Need be careful. Let's parse facts as directed edges. Need determine if path from ebplit to ulnik.\n\nFacts:\n1 ixkrov -> irxik\n2 irxiq -> abkror\n3 umniq -> yrxit\n4 edplim -> yrbov\n5 ebspor -> yrvrar\n6 erxiq -> umnir\n7 abgras -> orlar\n8 irvos -> erspok\n9 artrav -> yrlas\n10 ernis -> ebdrak\n11 arstat -> okplis\n12 icgrax -> ulstar\n13 ulstar -> umspos\n14 urlaq -> ebspor\n15 erbruz -> ixplix\n16 irbrun -> urlas\n17 erkron -> ergras\n18 ixmov -> orhox\n19 yrbov -> edvrat\n20 umspok -> ixmov\n21 urlas -> irvrax\n22 orhox -> icfon\n23 ebkror -> icturq\n24 orvram -> artrav\n25 igzox -> ebkrot\n26 ixpos -> orkroq\n27 yrxit -> ovpov\n28 ulxiv -> ulgram\n29 abspor -> ardras\n30 ebhoz -> okkroq\n31 axgras -> irbox\n32 okkroq -> icpos\n33 arbos -> umniq\n34 uzkroz -> abzoq\n35 orkroq -> edvoz\n36 axspoz -> edvran\n37 irspom -> axvrav\n38 uzvram -> unxit\n39 icgras -> irbov\n40 ebplit -> ebkror\n41 axplin -> ixkrov\n42 umspos -> orzor\n43 urxis -> urfoz\n44 ummok -> ulxiv\n45 icxim -> ixkrox\n46 ulgram -> ummos\n47 ardras -> edplim\n48 abkror -> arplir\n49 edvrat -> icxim\n50 ebdras -> axplin\n51 yrturm -> arxix\n52 ixkrox -> erxiq\n53 axvrav -> ernis\n54 irxik -> yrturm\n55 yrlas -> ungraz\n56 olvrar -> ebvok\n57 edvoz -> irvos\n58 erstan -> ulstas\n59 argrar -> icgrax\n60 abzoq -> urlaq\n61 okgraz -> urxis\n62 erbot -> edbruz\n63 ergras -> unpliz\n64 igbruk -> orvram\n65 ulstas -> irbrun\n66 ixkroq -> igbruk\n67 icturq -> uzkroz\n68 unpliz -> edzot\n69 ebvok -> umspok\n70 urfoz -> abgras\n71 umspox -> uzbor\n72 orlar -> erbot\n73 yrspoz -> icgras\n74 okplis -> ummok\n75 edvran -> ixkroq\n76 irvrax -> ebdras\n77 arplir -> erbruz\n78 arvox -> uzvram\n79 orzor -> umdram\n80 arxix -> ulnik\n81 edzot -> umkron\n82 ungraz -> ebhoz\n83 arturt -> arvox\n84 edbruz -> argrar\n85 ebdrak -> arturt\n86 ummos -> umspox\n87 yrvrar -> irxiq\n88 ebkrot -> ixpos\n89 irbov -> irspom\n90 icfon -> igzox\n91 icpos -> axgras\n92 umkron -> arstat\n93 ovpov -> abspor\n94 irvok -> arfor\n95 arfor -> yrspoz\n\nNeed path ebplit -> ... -> ulnik.\n\nStart ebplit -> ebkror (40). ebkror -> icturq (23). icturq -> uzkroz (67). uzkroz -> abzoq (34). abzoq -> urlaq (60). urlaq -> ebspor (14). ebspor -> yrvrar (5). yrvrar -> irxiq (87). irxiq -> abkror (2). abkror -> arplir (48). arplir -> erbruz (77). erbruz -> ixplix (15). ixplix no outgoing? Not listed. Dead.\n\nNeed maybe other branches? ebplit only edge to ebkror. ebkror only to icturq. icturq only to uzkroz. uzkroz only to abzoq. abzoq only to urlaq. urlaq only to ebspor. ebspor only to yrvrar. yrvrar only to irxiq. irxiq only to abkror. abkror only to arplir. arplir only to erbruz. erbruz only to ixplix. ixplix no outgoing. So no ulnik. But check if any fact with ixplix? none. So answer no.\n\nNeed ensure no typo: Fact 2 irxiq precedes abkror, Fact 88 yrvrar precedes irxiq. Yes.\n\nCould there be path via ebkrot? ebkror vs ebkrot distinct. ebplit -> ebkror not ebkrot. ebkrot -> ixpos -> orkroq -> edvoz -> irvos -> erspok dead. Not connected.\n\nThus no. Need final exactly one word: no. Ensure no extra.",
        "tok": 1335
    },
    "d2ab3a4e71b559b5605e3689658d8f3dfc93efaf7b6f85e74c246e7674f5ced2": {
        "ans": 'yes',
        "arm": 'F',
        "cell": 'L1',
        "content": 'yes',
        "dr": 1.0,
        "edges": 112,
        "fin": 'stop',
        "gold": 1,
        "k": 8,
        "out_sha": '0ca4bd41185af4a9a5bc7d8ea555db3fe4c81ee38670c15fa73fe898e37d0c67',
        "ptok": 1693,
        "reasoning": "We need answer yes/no if olplik precedes ebspoz given transitive rule and direct facts. Need compute reachability from olplik to ebspoz. Need be careful. Let's parse facts as directed edges. Need determine if path from olplik to ebspoz.\n\nFacts:\n1 axpliq -> ovvor\n2 icturr -> unvon\n3 abpok -> urxit\n4 orxix -> ebstaz\n5 yrstak -> ergrav\n6 arturt -> erxim\n7 abbruq -> ebbrus\n8 axstax -> axhot\n9 urvrak -> uzturk\n10 igkrom -> untrav\n11 ulstav -> axdram\n12 urxit -> olmor\n13 axpok -> erdrav\n14 okhov -> ebspoz\n15 urvrax -> ornik\n16 igtrar -> ovbrut\n17 abbruk -> axstax\n18 uzlan -> ungrat\n19 ulzox -> edstaz\n20 unspox -> ovxir\n21 ovtrar -> orgras\n22 umturv -> yrxiv\n23 ebniv -> irplit\n24 unvraq -> urvrax\n25 irvran -> orlat\n26 irbrux -> ermoq\n27 urkroz -> edfon\n28 icnin -> icpor\n29 unfoz -> axpoz\n30 umstan -> igdrax\n31 yrxiv -> arfon\n32 ovturz -> abbruk\n33 uzhot -> edgran\n34 arkrov -> unspox\n35 erxim -> okhov\n36 ovxiz -> irplix\n37 urhot -> icturr\n38 okpom -> arpoq\n39 ebstaz -> orvraq\n40 ovvor -> umturv\n41 yrmor -> ulbrus\n42 unvon -> olstat\n43 erdrav -> uzzor\n44 icdrar -> edzov\n45 arturv -> ixturs\n46 icfoz -> yrbos\n47 axhot -> arturt\n48 igbor -> icfoz\n49 ichoz -> abpok\n50 edstaz -> edfos\n51 ebkron -> igkrom\n52 okniz -> ignir\n53 igspor -> irvran\n54 ornik -> icdrar\n55 orvraq -> ixxim\n56 abmor -> ixxin\n57 edzov -> irtrax\n58 uzturk -> edvraz\n59 ardraq -> ixfov\n60 unfok -> umpoq\n61 orzoq -> okniz\n62 olspoq -> olbov\n63 irgraq -> igpos\n64 icvoz -> arkrov\n65 ignir -> ichoz\n66 ungrat -> ardraq\n67 iczom -> uzhot\n68 ulbov -> axpok\n69 olmor -> ablat\n70 ovbruk -> yrvoz\n71 igspov -> ixbrun\n72 ovmon -> iczom\n73 ummor -> unfok\n74 edvraz -> irvras\n75 igzor -> urkroz\n76 ixzot -> abbruq\n77 igpos -> ixzot\n78 yrplim -> urvrak\n79 ergrav -> okpom\n80 axdram -> orbox\n81 ixbrun -> igtrar\n82 orgran -> olspok\n83 arfon -> ulbov\n84 irnim -> ovtrar\n85 orgras -> unvraq\n86 yrpon -> yrmor\n87 ovbrut -> yrfom\n88 orlat -> irgraq\n89 olplik -> ovturz\n90 olbov -> orgran\n91 ablat -> igpoz\n92 icpor -> ovmon\n93 ebbrus -> ixspom\n94 edfon -> unfoz\n95 ixfov -> igbor\n96 yrvoz -> ebniv\n97 irpliz -> yrturn\n98 edgran -> ummor\n99 yrbos -> umstan\n100 olspok -> orturm\n101 arpoq -> yrplim\n102 orbox -> ebkron\n103 ovxir -> igspov\n104 ermoq -> abmor\n105 ixturs -> olspoq\n106 untrav -> ulzox\n107 ixxin -> urhot\n108 orturm -> ovxiz\n109 ulbrus -> irpliz\n110 yrturn -> orxix\n111 axpoz -> ovbruk\n112 olstat -> ummoq\n\nNeed path olplik -> ... -> ebspoz. ebspoz only incoming from okhov (Fact14). Need reach okhov. okhov incoming from erxim (35). erxim incoming from arturt (6). arturt incoming from axhot (47). axhot incoming from axstax (8). axstax incoming from abbruk (17). abbruk incoming from ovturz (32). ovturz incoming from olplik (89). So path: olplik -> ovturz -> abbruk -> axstax -> axhot -> arturt -> erxim -> okhov -> ebspoz. Yes.\n\nNeed final exactly one word yes. Ensure no extra.",
        "tok": 1239
    },
    "d548b1f9681cf082174cf141f33e0f34a65b98cf2504111e36284bdf287386cc": {
        "ans": None,
        "arm": 'X',
        "cell": 'L3',
        "content": '',
        "dr": 1.0,
        "edges": 160,
        "fin": 'length',
        "gold": 0,
        "k": 8,
        "out_sha": 'd8f96da2f21d486daccdfd70225508904188591bb0172ff841338487860f559b',
        "ptok": 2443,
        "reasoning": "We need answer yes/no if ebspot precedes yrkroq given transitive rule and direct facts. Need compute reachability from ebspot to yrkroq. Need be careful. Let's parse facts as directed edges. Need determine if path ebspot -> ... -> yrkroq.\n\nWe can manually trace. Let's list edges relevant.\n\nFacts:\n1 iclav -> abdrav\n2 yrlam -> uzgrak\n3 igkrok -> icbrun\n4 uzbom -> yrbon\n5 edgrav -> yrfor\n6 icbrun -> icdram\n7 abkrov -> igstaz\n8 irlas -> eddram\n9 ulgrav -> umkroq\n10 unvok -> igkrok\n11 abspoz -> igzoq\n12 urmok -> ixstam\n13 unzox -> iclaq\n14 igvox -> ullar\n15 arpliv -> okdrat\n16 igmox -> abspoz\n17 erturm -> oklav\n18 ixxiz -> ixkrox\n19 edplim -> ovmon\n20 unkror -> unvok\n21 irbrum -> uzpoq\n22 ernik -> olnit\n23 ergraq -> yrkroq\n24 ixvrak -> edvrax\n25 yrzov -> ebzoq\n26 orxis -> unspox\n27 ebnis -> ovlax\n28 yrfor -> uzmov\n29 ormox -> ormot\n30 umfoq -> irbrum\n31 urplis -> unkror\n32 abdrav -> olnim\n33 urtras -> abgram\n34 abvor -> arpliv\n35 erxiq -> oknis\n36 olbrut -> olxiz\n37 unspox -> uzhor\n38 edvov -> orbon\n39 erlat -> axkrok\n40 yrbon -> ovmom\n41 urboq -> edgrav\n42 ulniz -> ordras\n43 ovmon -> ernik\n44 edvor -> urboq\n45 icdram -> umspoz\n46 ovlax -> umfoq\n47 eddram -> yrvom\n48 yrvom -> olxit\n49 olkror -> ebgrar\n50 artraz -> axpoz\n51 olniz -> yrfon\n52 ebstas -> axmom\n53 ebvox -> abhox\n54 igbor -> urspon\n55 uzdrax -> unzox\n56 uldraq -> iglav\n57 irboz -> ulhom\n58 irfom -> arhot\n59 irgrat -> yrlam\n60 urkrom -> okgraz\n61 irbruz -> uztraq\n62 ulbruv -> erkroq\n63 ebbrux -> olkror\n64 abgram -> irfom\n65 axkrok -> orxis\n66 uzpoq -> ixgram\n67 arkroq -> unplin\n68 axmom -> irspox\n69 okgraz -> erxiq\n70 orxiv -> umstak\n71 unplin -> icnir\n72 ixstam -> ebnis\n73 erpos -> yrzov\n74 ernit -> irbruz\n75 olxiz -> igvox\n76 iglas -> ernit\n77 olbom -> irdraq\n78 undras -> ebturk\n79 abspox -> arvom\n80 umxit -> okturv\n81 axturq -> urtras\n82 ulhom -> erstak\n83 abspot -> urboz\n84 uztraq -> axkrot\n85 erpot -> orhot\n86 ordras -> olmon\n87 ebspot -> igmox\n88 icplik -> oktrar\n89 igbot -> axzoq\n90 ebgrar -> axpon\n91 umgrav -> uzdrax\n92 ulxix -> urkrom\n93 igtram -> uzmox\n94 umniq -> ergrak\n95 abmov -> ebvox\n96 oklav -> umgrav\n97 ertraz -> erpos\n98 olnim -> axturq\n99 edxiz -> olbrut\n100 ormot -> ixxik\n101 oktrar -> igtram\n102 umspoz -> abspox\n103 ictrax -> icplik\n104 igfom -> erlat\n105 abhox -> ovstak\n106 erbox -> umxit\n107 urboz -> ebstas\n108 ovhoq -> olplik\n109 ebzoq -> iglas\n110 olpoz -> ebtrax\n111 ixxiq -> arspor\n112 ixxik -> ebbrux\n113 arhot -> ermon\n114 ixpok -> ovhoq\n115 axzoq -> abpot\n116 axstas -> umpox\n117 yrbrun -> igturv\n118 urspon -> abkrov\n119 ovstak -> uzbom\n120 arvrak -> uldraq\n121 orhot -> ixpok\n122 olxit -> edplim\n123 ovmom -> yrkrov\n124 yrfon -> uzkroz\n125 olplis -> ictrax\n126 axpoz -> ovvoz\n127 yrkrov -> urnik\n128 ullar -> ebplis\n129 oknis -> ulzok\n130 axpon -> ergraq\n131 ebturk -> irgrat\n132 ebplis -> igbot\n133 olplik -> irboz\n134 orbon -> ulbruv\n135 ebtrax -> ulxir\n136 iglav -> igpoz\n137 ixkrox -> erbox\n138 uzmov -> olbom\n139 arspor -> olplis\n140 irbom -> igfom\n141 olnit -> unvraz\n142 erstak -> umdrav\n143 igkror -> ollan\n144 igpoz -> ixxiz\n145 erkroq -> ixvrak\n146 iclaq -> abvor\n147 olmon -> yrbrun\n148 ergrak -> ulgrav\n149 igstaz -> olpoz\n150 umkroq -> undras\n151 irspox -> arkroq\n152 ulzok -> artraz\n153 uzkroz -> edvov\n154 arstav -> abspot\n155 umstak -> irbom\n156 ollan -> igbor\n157 erturq -> urmok\n158 igzoq -> ulniz\n159 umpox -> edvor\n160 uzmox -> ollar\n\nNeed path from ebspot. ebspot -> igmox (87). igmox -> abspoz (16). abspoz -> igzoq (11). igzoq -> ulniz (158). ulniz -> ordras (42). ordras -> olmon (86). olmon -> yrbrun (147). yrbrun -> igturv (117). igturv no outgoing? Not in facts. So dead.\n\nBut maybe other branches? ebspot only one outgoing? Fact 87 only. Need see if any path to yrkroq. yrkroq incoming from ergraq (23). ergraq incoming from axpon (130). axpon incoming from ebgrar (90). ebgrar incoming from olkror (49). olkror incoming from ebbrux (63). ebbrux incoming from ixxik (112). ixxik incoming from ormot (100). ormot incoming from ormox (29). ormox no incoming? Need path from ebspot to ormox? Not in above chain. Other incoming to yrkroq? only ergraq. Need reach ergraq. Incoming to ergraq: axpon. Incoming axpon: ebgrar. Incoming ebgrar: olkror. Incoming olkror: ebbrux. Incoming ebbrux: ixxik. Incoming ixxik: ormot. Incoming ormot: ormox. Incoming ormox? none? Check facts: ormox precedes ormot only. No incoming to ormox. So to reach yrkroq must reach ormox. Does ebspot reach ormox? ebspot chain to igturv dead. No.\n\nBut maybe there are other paths from ebspot? ebspot -> igmox -> abspoz -> igzoq -> ulniz -> ordras -> olmon -> yrbrun -> igturv.",
        "tok": 2048
    },
    "ddb9421bc3e7c63dcae14af51cdb6b5e6347ff569b21683558c0f9fa409b6402": {
        "ans": 'no',
        "arm": 'X',
        "cell": 'L0',
        "content": 'no',
        "dr": 1.0,
        "edges": 96,
        "fin": 'stop',
        "gold": 0,
        "k": 8,
        "out_sha": 'f1d28b59eacc80c9436d12d09a4c4845e0c0a7056c5057b59d7aab4f08348649',
        "ptok": 1448,
        "reasoning": "We need answer yes/no if yrvok precedes iglaq given transitive rule and facts direct links. Need compute reachability. Need be careful. Let's parse facts as directed edges x -> y. Need determine if path from yrvok to iglaq.\n\nFacts:\n1 igniv -> unbon\n2 ovkrox -> axtras\n3 ulzom -> ablav\n4 ulfok -> yrlav\n5 uzzon -> ixpoz\n6 unspon -> urhom\n7 ixpoz -> urxir\n8 iglar -> orxiz\n9 umturn -> ortraq\n10 yrvok -> abniq\n11 icvom -> umturn\n12 ebstam -> unvraq\n13 icxik -> axspom\n14 ovhot -> ixtraz\n15 axbrux -> ulfok\n16 okmom -> edlar\n17 axturx -> axvrav\n18 ortraq -> ebbot\n19 umhoz -> yrkroz\n20 igplit -> olpov\n21 eblaq -> erspon\n22 erplis -> orturv\n23 erfot -> ixhok\n24 okmon -> uzzon\n25 ovbot -> orgrat\n26 unvraq -> irpon\n27 umvrat -> icfov\n28 abbruq -> uzlan\n29 irdras -> ulzom\n30 orxiv -> ermon\n31 ormos -> edgraq\n32 axspom -> orxiv\n33 urvos -> icxik\n34 erturm -> ignik\n35 abnin -> uzplir\n36 ignik -> urbot\n37 orvos -> umvrat\n38 eblat -> arvram\n39 uzturm -> ulturq\n40 unmom -> umhoz\n41 ixnis -> ovlak\n42 orturv -> yrturk\n43 orpor -> ovbot\n44 ixlak -> igniv\n45 yrturk -> icvrak\n46 okspox -> unmom\n47 irhon -> okvoz\n48 ixpliq -> ulnix\n49 irmoz -> ovhot\n50 ovhoz -> unspon\n51 erbruz -> irhon\n52 icvrak -> irdras\n53 orxiz -> ulplim\n54 edlar -> igtras\n55 ulvon -> eblat\n56 yrlav -> iglaq\n57 edgraq -> axbrux\n58 igturm -> ebstam\n59 irturm -> eblaq\n60 uzplir -> erplis\n61 irpon -> irmoz\n62 ebtraq -> irturm\n63 axtras -> ixnis\n64 icxiz -> erturm\n65 ixhok -> icxiz\n66 igzon -> ednit\n67 erplir -> urvos\n68 uzlan -> erplir\n69 uzgras -> orpor\n70 iclat -> igzox\n71 olfoz -> icvom\n72 unbon -> axturx\n73 okvoz -> ixlak\n74 yrkroz -> igzon\n75 icplir -> axplit\n76 arvram -> ebtraq\n77 ulturq -> orvos\n78 abniq -> ovhoz\n79 igpov -> uzturm\n80 uzxiq -> abbruq\n81 erfok -> ixpliq\n82 erspon -> iclat\n83 ednit -> okmom\n84 ovlak -> olfoz\n85 icfov -> erfon\n86 ixstak -> icplir\n87 urhom -> okvrat\n88 icnis -> uzgras\n89 axplit -> ormos\n90 yrspok -> erbruz\n91 erfon -> uztran\n92 orgrat -> okmon\n93 okvrat -> erfok\n94 ixtraz -> igplit\n95 ulplim -> erfot\n96 umbruv -> igpov\n\nNeed path yrvok -> ... -> iglaq.\nStart yrvok -> abniq (10). abniq -> ovhoz (78). ovhoz -> unspon (50). unspon -> urhom (6). urhom -> okvrat (87). okvrat -> erfok (93). erfok -> ixpliq (81). ixpliq -> ulnix (48). ulnix no outgoing? Not listed. Dead. So this path doesn't reach iglaq.\n\nMaybe other branches? yrvok only fact 10. abniq only 78. ovhoz only 50. unspon only 6. urhom only 87. okvrat only 93. erfok only 81. ixpliq only 48. ulnix none. So no path to iglaq? Need check if any other outgoing from these nodes? Let's scan all facts for sources: yrvok only 10. abniq only 78. ovhoz only 50. unspon only 6. urhom only 87. okvrat only 93. erfok only 81. ixpliq only 48. ulnix no outgoing. So no.\n\nBut maybe transitive rule only if x precedes y and y precedes z, then x precedes z. Direct facts. Need answer no.\n\nDouble-check if there is any hidden path via yrvok? No.\n\nNeed final exactly one word: no. Ensure no extra.",
        "tok": 1258
    },
    "de5ed21b32895e67bd295d1b63df3245e57634d0b07da4ba92e9442cd1e0fead": {
        "ans": 'no',
        "arm": 'X',
        "cell": 'D2',
        "content": 'no',
        "dr": 1.0,
        "edges": 96,
        "fin": 'stop',
        "gold": 0,
        "k": 16,
        "out_sha": '19fc9b24ffd8b5410c8f58ca24854558dbf5a95dc44e76d0f7fba119446fcd0f',
        "ptok": 1438,
        "reasoning": "We need answer yes/no based on transitive closure of directed precedes facts. Need determine if orvor precedes abmov. Need analyze carefully. We can manually trace graph. Rule transitive. Facts direct. Need see if path from orvor to abmov.\n\nLet's list facts as edges:\n1 irzos -> ovhos\n2 umturt -> ulxit\n3 arkrox -> erstaq\n4 irvon -> unhoz\n5 edmov -> olfom\n6 orspor -> abmov\n7 uzbruz -> edxim\n8 erlaq -> ixvom\n9 olpliv -> ebhor\n10 uzfok -> yrlat\n11 ovvran -> arstaz\n12 edxim -> edmov\n13 ulpom -> iglas\n14 uzdraz -> irpox\n15 olplik -> erfot\n16 ovbox -> umstak\n17 urnir -> igvram\n18 arspon -> olbruv\n19 erstaq -> uzturk\n20 arvoz -> ebzom\n21 arstaz -> ixhos\n22 irpox -> unpov\n23 orlat -> olpliv\n24 ebspoz -> ixkrov\n25 umturv -> uzbruz\n26 orvor -> orgras\n27 abbon -> abnix\n28 ovhos -> uzvran\n29 iglas -> ovgrav\n30 ixstav -> arspos\n31 olmon -> ovgras\n32 yrgran -> edstar\n33 edvran -> olplik\n34 ovzox -> orlat\n35 ixkroz -> uzkror\n36 uzturk -> yrvon\n37 abbor -> ormoq\n38 edstar -> igdrax\n39 abstaq -> urmox\n40 arvran -> yrpon\n41 igbor -> edhom\n42 irbrux -> urdrar\n43 ulplim -> ovzox\n44 igxin -> ulpom\n45 okbruq -> erspor\n46 armor -> ovbox\n47 umstak -> edvran\n48 igdrax -> abmox\n49 ormox -> irbrux\n50 ulxit -> orbruq\n51 urmox -> olmon\n52 olfom -> irzos\n53 arzor -> igxin\n54 erspor -> icplin\n55 ormoq -> yrturs\n56 ulhoq -> abbor\n57 uzkror -> irvon\n58 ebstas -> ixxiv\n59 ixkrov -> ormox\n60 yrvon -> orspor\n61 ebzom -> ixstav\n62 ixhos -> umturt\n63 olbruv -> arvoz\n64 yrpon -> okplim\n65 ebhor -> ovvran\n66 edhom -> ebstas\n67 urdrar -> yrgran\n68 iglan -> ixspok\n69 yrturs -> iclat\n70 ertrat -> okbruq\n71 uzkrom -> uzdraz\n72 unhoz -> abstaq\n73 igmot -> oltraq\n74 abnix -> olstas\n75 olstas -> ixkroz\n76 ovgrav -> ertrat\n77 igturx -> arkrox\n78 oltraq -> ebspoz\n79 iclat -> edhon\n80 icplin -> igturx\n81 yrlat -> urnir\n82 okgraz -> ulhoq\n83 orgras -> unlar\n84 unlar -> iglan\n85 erfot -> okgraz\n86 uzvran -> igbor\n87 ixxiv -> uzkrom\n88 ixspok -> urxiz\n89 ovgras -> iggram\n90 okplim -> abbon\n91 arspos -> igmot\n92 igvram -> armor\n93 unpov -> uzkrov\n94 urxiz -> ulplim\n95 ordraq -> arzor\n96 ixvom -> arvran\n\nQuestion: orvor precedes abmov? Direct or transitive.\n\nStart orvor -> orgras (26). orgras -> unlar (83). unlar -> iglan (84). iglan -> ixspok (68). ixspok -> urxiz (88). urxiz -> ulplim (94). ulplim -> ovzox (43). ovzox -> orlat (34). orlat -> olpliv (23). olpliv -> ebhor (9). ebhor -> ovvran (65). ovvran -> arstaz (11). arstaz -> ixhos (21). ixhos -> umturt (62). umturt -> ulxit (2). ulxit -> orbruq (50). orbruq? no outgoing listed? Check facts: orbruq appears only as target fact 50. No outgoing. So path dead. Need see if any branch from nodes along path to abmov. Need explore all reachable from orvor.\n\nFrom orvor only orgras. orgras only unlar? fact 83. unlar only iglan. iglan only ixspok. ixspok only urxiz. urxiz only ulplim. ulplim only ovzox. ovzox only orlat. orlat only olpliv. olpliv only ebhor. ebhor only ovvran. ovvran only arstaz. arstaz only ixhos. ixhos only umturt. umturt only ulxit. ulxit only orbruq. orbruq no outgoing. So no abmov. But need ensure no other edges from these nodes? Let's scan all facts for each source:\norvor: 26 only.\norgras: 83 only.\nunlar: 84 only.\niglan: 68 only.\nixspok: 88 only.\nurxiz: 94 only.\nulplim: 43 only.\novzox: 34 only.\norlat: 23 only.\nolpliv: 9 only.\nebhor: 65 only.\novvran: 11 only.\narstaz: 21 only.\nixhos: 62 only.\numturt: 2 only.\nulxit: 50 only.\norbruq: none.\nThus no path to abmov. But maybe abmov reachable via other chain? Need path to orspor -> abmov. Need reach orspor. From orvor chain reaches? It reaches umturt, ulxit, orbruq. Not yrvon? There is yrvon -> orspor. Need reach yrvon. Chain from orvor doesn't. Could there be branch from orgras? no. So answer no.\n\nNeed final exactly one word: no. Ensure no hidden transitive via reverse? Rule only if x precedes y and y precedes z then x precedes z. Facts direct. No.\n\nDouble-check if any fact has orvor as target? no. If orvor precedes abmov? no.\n\nNeed final only yes/no.",
        "tok": 1619
    }
}

SAME_CLASS_ARCHIVES = {"R31": R31_PANEL, "R37": R37_PANEL}
FLASH_CLASS_ARCHIVES = {"R33": R33_PANEL, "R38P1": R38P1_PANEL}
PANEL_ARCHIVE = {"R31": R31_PANEL, "R33": R33_PANEL, "R37": R37_PANEL,
                 "R38P1": R38P1_PANEL}

# Published full-design (6 prompts per cell) cost slopes, transcribed from the round records:
# the basis is part of the number (issue #100's estimator-basis rule); "uncensored" excludes a
# cell with any 2048-token truncation from the fit, "all-cell" keeps its censored mean.
PUBLISHED_SLOPES = {
    "R24": {"basis": "all-cell (no truncation in this firing)",
            "load_tok_per_fact": 7.8854, "depth_tok_per_hop": 29.3542},
    "R33": {"basis": "all-cell (no truncation in this firing)",
            "load_tok_per_fact": 7.6869, "depth_tok_per_hop": 29.5625},
    "R31": {"basis": "uncensored (D2 censored through one 2048-token truncation)",
            "load_tok_per_fact": -6.0107, "depth_tok_per_hop": -27.1250,
            "depth_tok_per_hop_all_cell": 60.4583},
    "R37": {"basis": "all-cell (no truncation in this firing)",
            "load_tok_per_fact": -5.1899, "depth_tok_per_hop": -9.4792},
}

# Declared thresholds, frozen before any prompt was spent.
T1_CHANNEL_MIN = 11          # of 12 P1 dispatches expose non-empty reasoning text
T2_DR_POSITIVE_MIN = 8       # of 12 P1 dispatches with distractor_mention_ratio > 0
T2_DR_MEAN_MIN = 0.25        # mean distractor_mention_ratio over the 12 P1 dispatches
T3_BILLING_ANOMALIES_MAX = 0  # attempts (of 36) with billed_tokens * 6 < exposed chars
T4_CROSS_CLASS_TARR_MAX = 3   # of 12 full-text byte-identical pairs vs round 38 P1
# Round 38's P1 did not deliver one panel answer (L3 arm X truncated at 2048 on the flash
# class), so the 12 pairs carry 11 both-delivered answers; T4 scores agreement over those.
T4_CROSS_CLASS_TARA_RATIO_MIN = 1.0
T5_R37_FACTOR2_MIN = 8       # of 12 prompts with billed tokens within a factor of 2 of R37
N1_TARR_GRID_MIN = 0.90      # serialized vs serialized, over the 12 same-mode replicate pairs
N1_TARR_CELL_MIN = 0.50      # per cell carries 2 same-mode pairs: at most one may disagree
N2_TARR_GRID_MIN = 1.00      # the mode change moves nothing at all
N2_TOKEN_DELTA_MAX = 0       # per prompt: |completion token change| between modes
N3_TARA_GRID_MIN = 1.00      # parsed answer agrees in every within-run stratum
N4_DELIVERED_MIN = 36        # all 36 dispatches answer in the answer field
N4_CORRECT_MIN = 36          # and all 36 are correct under content_only
N5_COST_BAND = (0.5, 2.0)    # house band, scored on the panel basis against the panel reference
N5_REFERENCE_FIRING = "R38P1"  # the same panel's flash-class firing measured yesterday
CELL_ITEMS = 2               # panel items per cell: exploratory, and labelled wherever used
CELL_DISPATCHES = 6          # 2 items x 3 passes: not 6 independent items, and labelled as such

# Noise-floor arithmetic: the observed per-prompt pairwise difference of a stratum is propagated
# through the same slope estimator, so the floor comes out in tokens/fact and tokens/hop, on
# the same scale as the quantity it judges. Fixed seed and draw count: the floor is
# reproducible from gate.json and raw.jsonl alone.
BOOT_DRAWS = 4000
BOOT_SEED = 20261101
FLOOR_QUANTILES = (0.50, 0.95, 0.99)
RESOLVE_QUANTILE = 0.99      # a difference counts as a change only beyond this quantile
MATERIAL_REL_DEV = 0.10      # a per-prompt length move of 10 percent or more is "material"
BILLING_CHARS_PER_TOKEN = 6  # the anomaly test: billed below 1 token per 6 exposed chars

# The pair strata. Within-run pairs are same-session and same host by construction;
# cross-firing pairs also carry whatever the deployment did between firings (restart, build,
# host), which is why the floor is reported per stratum and never pooled across them. R38P1 is
# the other class; R31 and R37 are this class.
STRATA = {
    "within_run_same_mode": [("P1", "P3")],
    "within_run_mode_change": [("P1", "P2"), ("P2", "P3")],
    "cross_firing_this_class": [("R37", "P1"), ("R31", "P1")],
    "cross_firing_flash_class": [("R38P1", "P1")],
    "cross_class": [("R38P1", "P1")],
}


def sanitize(text: str) -> str:
    """Public-only rule, enforced before anything is written: strip URLs, IP addresses
    and absolute paths from model output."""
    return URL_RE.sub("[REDACTED]", text or "")


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _name(rng: random.Random, taken: set) -> str:
    for _ in range(500):
        name = rng.choice(POOL_A) + rng.choice(POOL_B) + rng.choice(POOL_C)
        if name not in taken:
            taken.add(name)
            return name
    raise RuntimeError("name pool exhausted")


def gen_item(k: int, c_chains: int, seed: int) -> dict:
    """Component-isomorphic hop chain (the round-8 construction as re-implemented for
    round 21 and used unchanged by round 22, byte-compatible): C disjoint directed paths
    of exactly k edges over fresh entities; the query is (head of one path, tail of one
    path); yes iff both endpoints lie on the same path."""
    rng = random.Random(seed)
    taken: set = set()
    chains = [[_name(rng, taken) for _ in range(k + 1)] for _ in range(c_chains)]
    facts = [(u, REL, v) for ch in chains for u, v in zip(ch, ch[1:])]
    main = rng.randrange(c_chains)
    yes = rng.random() < 0.5
    if yes:
        src, tgt, chain_len = chains[main][0], chains[main][-1], k
    else:
        other = rng.randrange(c_chains - 1)
        if other >= main:
            other += 1
        src, tgt, chain_len = chains[main][0], chains[other][-1], None
    rng.shuffle(facts)
    return {
        "task_type": "hop_chain",
        # "L" is the construction-lineage label inherited from round 8's arm L and kept
        # byte-identical through rounds 21 and 22: the item manifest is hashed, so this
        # is what makes the anchor cell's candidate pool the SAME pool round 23 archived
        # at (k = 8, E = 96) (and, one level down, the pools of rounds 21 and 22). The
        # dispatch arm of a record is a separate field, "F" or "X".
        "arm": "L",
        "level": k,
        "chains": c_chains,
        "edges": len(facts),
        "seed": seed,
        "seed_hash": sha256_text(f"ladders|hop_chain|{k}|{seed}")[:16],
        "rule": RULE_SENTENCE,
        "facts": [[s, r, t] for s, r, t in facts],
        "query": [src, REL, tgt],
        "answer": "yes" if yes else "no",
        "chain_len": chain_len,
    }


def bfs_dist(facts: list, src: str) -> dict:
    graph: dict = {}
    for s, _, t in facts:
        graph.setdefault(s, []).append(t)
    dist = {src: 0}
    queue = [src]
    while queue:
        nxt: list = []
        for u in queue:
            for v in graph.get(u, ()):
                if v not in dist:
                    dist[v] = dist[u] + 1
                    nxt.append(v)
        queue = nxt
    return dist


def verify_item(item: dict) -> list:
    """Independent structural and solvability audit of one item."""
    bad: list = []
    facts = item["facts"]
    k = item["level"]
    out: dict = {}
    inc: dict = {}
    nodes: set = set()
    for s, rel, t in facts:
        if rel != REL:
            bad.append(f"relation {rel!r}")
        out[s] = out.get(s, 0) + 1
        inc[t] = inc.get(t, 0) + 1
        nodes |= {s, t}
    if len({tuple(f) for f in facts}) != len(facts):
        bad.append("duplicate facts")
    adj: dict = {}
    for s, _, t in facts:
        adj.setdefault(s, set()).add(t)
        adj.setdefault(t, set()).add(s)
    seen: set = set()
    n_comp = 0
    for node in nodes:
        if node in seen:
            continue
        n_comp += 1
        comp = {node}
        stack = [node]
        while stack:
            u = stack.pop()
            for v in adj.get(u, ()):
                if v not in comp:
                    comp.add(v)
                    stack.append(v)
        seen |= comp
        edges = sum(out.get(u, 0) for u in comp)
        if edges != k or len(comp) != k + 1:
            bad.append(f"component of {edges} edges over {len(comp)} nodes")
        heads = [u for u in comp if inc.get(u, 0) == 0 and out.get(u, 0) == 1]
        tails = [u for u in comp if inc.get(u, 1 - 1) == 1 and out.get(u, 0) == 0]
        if len(heads) != 1 or len(tails) != 1:
            bad.append("component is not a directed path")
        if any(out.get(u, 0) > 1 or inc.get(u, 0) > 1 for u in comp):
            bad.append("branching node")
    if n_comp != item["chains"]:
        bad.append(f"{n_comp} components, manifest says {item['chains']}")
    qs, _, qt = item["query"]
    if inc.get(qs, 0) != 0 or out.get(qs, 0) != 1:
        bad.append("query source is not a path head")
    if inc.get(qt, 0) != 1 or out.get(qt, 0) != 0:
        bad.append("query target is not a path tail")
    dist = bfs_dist(facts, qs)
    if (item["answer"] == "yes") != (qt in dist):
        bad.append("stored answer disagrees with independent BFS")
    if item["answer"] == "yes" and dist.get(qt) != k:
        bad.append(f"shortest path {dist.get(qt)} != level {k}")
    if item["answer"] == "no" and item["chain_len"] is not None:
        bad.append("no item carries a chain_len")
    return bad


def comp_tail_targets(item: dict) -> list:
    """Tails of every path in the item except the queried source's own path."""
    out_m = {s: t for s, _, t in item["facts"]}
    inc_set = {t for _, _, t in item["facts"]}
    k = item["level"]
    src = item["query"][0]
    heads = sorted(n for n in ({s for s, _, _ in item["facts"]} | inc_set)
                   if n not in inc_set)
    tails = []
    for head in heads:
        if head == src:
            continue
        node = head
        for _ in range(k):
            node = out_m[node]
        tails.append(node)
    return tails


def x_variant(item: dict) -> dict:
    """The matched cross-component query on the IDENTICAL fact list: same source (a path
    head), target = the tail of a different path, chosen deterministically from the item
    digest so the choice cannot depend on anything measured."""
    cands = sorted(comp_tail_targets(item))
    if not cands:
        raise RuntimeError("item has no other component to query")
    rng = random.Random(sha256_text("xvariant|" + canonical(item)))
    tgt = rng.choice(cands)
    var = dict(item)
    var["query"] = [item["query"][0], REL, tgt]
    var["answer"] = "no"
    var["chain_len"] = None
    return var


def pair_violations(f_item: dict, x_item: dict) -> list:
    """Issue #78 acceptance criterion 1: the two queries of a pair must share every fact,
    every entity name and the fact count, and differ only in the queried target; both
    labels must be certified by an independent BFS."""
    bad: list = []
    if canonical(f_item["facts"]) != canonical(x_item["facts"]):
        bad.append("fact lists differ")
    ent_f = {n for s, _, t in f_item["facts"] for n in (s, t)}
    ent_x = {n for s, _, t in x_item["facts"] for n in (s, t)}
    if ent_f != ent_x:
        bad.append("entity name sets differ")
    if len(f_item["facts"]) != len(x_item["facts"]):
        bad.append("fact counts differ")
    if f_item["query"][0] != x_item["query"][0]:
        bad.append("queried source differs")
    if f_item["query"][2] == x_item["query"][2]:
        bad.append("queried targets are identical")
    if not (f_item["answer"] == "yes" and x_item["answer"] == "no"):
        bad.append("pair labels are not (yes, no)")
    dist = bfs_dist(x_item["facts"], x_item["query"][0])
    if x_item["query"][2] in dist:
        bad.append("cross-component target is reachable from the source")
    if bfs_dist(f_item["facts"], f_item["query"][0]).get(f_item["query"][2]) != f_item["level"]:
        bad.append("forward target is not at distance k")
    return bad


def features(item: dict) -> dict:
    """Traversal-free feature battery over the query endpoints and fact list."""
    facts = item["facts"]
    srcs = {s for s, _, _ in facts}
    tgts = {t for _, _, t in facts}
    inc: dict = {}
    for s, _, t in facts:
        inc[t] = inc.get(t, 0) + 1
    qs, _, qt = item["query"]
    first_idx: dict = {}
    for i, (s, _, t) in enumerate(facts):
        first_idx.setdefault(s, i)
        first_idx.setdefault(t, i)
    e_count = len(facts)
    return {
        "tgt_is_fact_target": qt in tgts,
        "tgt_is_fact_source": qt in srcs,
        "tgt_outdeg_zero": all(t != qt for s, _, t in facts) or qt not in srcs,
        "tgt_indeg_zero": inc.get(qt, 0) == 0,
        "src_is_fact_target": qs in tgts,
        "src_is_fact_source": qs in srcs,
        "src_outdeg_zero": qs not in srcs,
        "src_indeg_zero": inc.get(qs, 0) == 0,
        "tgt_name_lt_src_name": qt < qs,
        "tgt_name_longer_than_src": len(qt) > len(qs),
        "tgt_first_mention_before_src": (first_idx.get(qt, 10 ** 9)
                                          < first_idx.get(qs, 10 ** 9)),
        "tgt_first_third": first_idx.get(qt, 10 ** 9) < e_count / 3.0,
        "src_first_third": first_idx.get(qs, 10 ** 9) < e_count / 3.0,
        "tgt_last_third": first_idx.get(qt, 10 ** 9) >= 2.0 * e_count / 3.0,
        "n_facts_even": e_count % 2 == 0,
        "src_is_source_of_first_fact": facts[0][0] == qs,
        "tgt_is_target_of_last_fact": facts[-1][2] == qt,
    }


def _bits(vals: list) -> int:
    mask = 0
    for i, v in enumerate(vals):
        if v:
            mask |= 1 << i
    return mask


def _acc(pred: int, gold: int, n: int) -> float:
    return 1.0 - ((pred ^ gold) & ((1 << n) - 1)).bit_count() / n


def battery(items: list) -> tuple:
    n = len(items)
    gold = _bits([it["answer"] == "yes" for it in items])
    cols: dict = {}
    for it in items:
        for name, val in features(it).items():
            cols.setdefault(name, []).append(val)
    constant = sorted(name for name, vals in cols.items() if len(set(vals)) == 1)
    varying = {name: _bits(vals) for name, vals in cols.items() if len(set(vals)) > 1}
    names = sorted(varying)
    mask = (1 << n) - 1
    rules: dict = {}
    for name in names:
        b = varying[name]
        rules[f"single:{name}->yes"] = b
        rules[f"single:{name}->no"] = (~b) & mask
    for i, a in enumerate(names):
        for bname in names[i + 1:]:
            x, y = varying[a], varying[bname]
            rules[f"conj:{a}&{bname}"] = x & y
            rules[f"conj:{a}&~{bname}"] = x & (~y) & mask
            rules[f"conj:~{a}&{bname}"] = (~x) & mask & y
            rules[f"conj:~{a}&~{bname}"] = (~x) & mask & (~y) & mask
    rules["stump:always_yes"] = mask
    rules["stump:always_no"] = 0
    return constant, rules, gold


def gate_battery(items: list, perms: int = PERMS, seed: int = SEED_BASE) -> dict:
    """Permutation-calibrated leak gate, family-wise alpha over the whole battery. Runs
    on the candidate pool and on the paired pool, never on the selected pairs."""
    n = len(items)
    constant, rules, gold = battery(items)
    obs = {name: _acc(pred, gold, n) for name, pred in rules.items()}
    top = sorted(obs.items(), key=lambda kv: -kv[1])[:5]
    yes_n = sum(1 for it in items if it["answer"] == "yes")
    majority = max(yes_n, n - yes_n) / n
    rng = random.Random(seed)
    labels = [it["answer"] == "yes" for it in items]
    preds = list(rules.values())
    null_max: list = []
    for _ in range(perms):
        rng.shuffle(labels)
        g = _bits(labels)
        null_max.append(max(_acc(p, g, n) for p in preds))
    null_max.sort()
    threshold = null_max[min(perms - 1, int(round((1.0 - ALPHA) * perms)))]
    obs_max = top[0][1] if top else 0.0
    exceed = sum(1 for x in null_max if x >= obs_max)
    p_value = (exceed + 1) / (perms + 1)
    flagged = sorted((name for name, a in obs.items() if a > threshold),
                     key=lambda nm: -obs[nm])
    return {
        "n": n,
        "gold_yes": yes_n,
        "majority_baseline": round(majority, 4),
        "battery_rules": len(rules),
        "constant_features": constant,
        "top_rules": [{"rule": nm, "accuracy": round(a, 4)} for nm, a in top],
        "observed_max": round(obs_max, 4),
        "null_max_p95": round(threshold, 4),
        "calibrated_threshold": round(threshold, 4),
        "p_value": round(p_value, 4),
        "flagged_rules": flagged,
        "verdict": "leak" if flagged else "no leak at family-wise alpha",
    }


def cell_seed(k: int, c_chains: int, index: int) -> int:
    return SEED_BASE + 1_000_000 * k + 10_000 * c_chains + index


def build_cell(k: int, c_chains: int, want_pairs: int) -> tuple:
    """Selection rule fixed in advance: candidate order by seed; the first want_pairs
    GOLD-YES candidates become the arm-F members of the dispatched pairs, each with its
    deterministic cross-component arm-X variant. Every candidate and every derived variant
    passes the independent structural audit, and every dispatched pair passes the
    shared-content assertion. Returns (selected pairs, 40-candidate pool, paired pool)."""
    pool: list = []
    pairs: list = []
    for i in range(CANDIDATES):
        item = gen_item(k, c_chains, cell_seed(k, c_chains, i))
        violations = verify_item(item)
        if violations:
            raise RuntimeError(
                f"cell k={k} C={c_chains} seed {item['seed']}: {violations}")
        pool.append(item)
        if item["answer"] != "yes":
            continue
        var = x_variant(item)
        var_violations = verify_item(var)
        if var_violations:
            raise RuntimeError(
                f"variant k={k} C={c_chains} seed {item['seed']}: {var_violations}")
        shared = pair_violations(item, var)
        if shared:
            raise RuntimeError(
                f"matched pair k={k} C={c_chains} seed {item['seed']}: {shared}")
        if len(pairs) < want_pairs:
            pairs.append((item, var))
    if len(pairs) != want_pairs:
        raise RuntimeError(f"cell k={k} C={c_chains}: selection rule starved")
    paired_pool = []
    for item in pool:
        if item["answer"] != "yes":
            continue
        paired_pool.append(item)
        paired_pool.append(x_variant(item))
    return pairs, pool, paired_pool


def all_cells() -> list:
    cells = []
    for name, k, c_chains in WALK:
        pairs, pool, paired_pool = build_cell(k, c_chains, PAIRS_PER_LEVEL)
        cells.append({"cell": name, "index": WALK_INDEX[name], "k": k,
                      "chains": c_chains, "edges": k * c_chains, "pairs": pairs,
                      "pool": pool, "paired_pool": paired_pool})
    return cells


def render_prompt(item: dict) -> str:
    lines = [RULE_SENTENCE]
    lines += [f"Fact {i + 1}: {s} {r} {t}." for i, (s, r, t) in enumerate(item["facts"])]
    s, r, t = item["query"]
    lines.append(f"Question: does {s} {r} {t}? Answer with exactly one word: yes or no.")
    return "\n".join(lines)


def last_answer(text: str):
    """Last standalone yes/no in one field. Returns (answer, offset)."""
    matches = list(ANSWER_RE.finditer(text or ""))
    if not matches:
        return None, -1
    m = matches[-1]
    return m.group(1).lower(), m.start()


def strict_last_trace_token(reasoning: str):
    """Round-19 rule, vendored verbatim: the last trace yes/no that could be a verdict.
    Qualifies when it is outside a "yes/no" or "yes or no" phrase and either closes the
    trace (only punctuation after it) or is both preceded by an answer cue within 30
    characters and closed by punctuation."""
    text = reasoning or ""
    spans = [p.span() for p in PHRASE_RE.finditer(text)]
    chosen = None
    for m in ANSWER_RE.finditer(text):
        if any(a <= m.start() and m.end() <= b for a, b in spans):
            continue
        closes_trace = bool(STRICT_TAIL_RE.match(text, m.end()))
        closed_by_punct = (m.end() < len(text)
                           and text[m.end()] in ".!?:;")
        cued = bool(VERDICT_CUE_RE.search(text, 0, m.start()))
        if closes_trace or (closed_by_punct and cued):
            chosen = m.group(1).lower()
    return chosen


def provenance_class(reasoning: str):
    """Round-19 classes for the LAST reasoning-field yes/no: instruction_echo (inside a
    yes/no phrase), terminal (last 2% of the trace), mid_trace (elsewhere), or None when
    the trace carries no yes/no."""
    text = reasoning or ""
    matches = list(ANSWER_RE.finditer(text))
    if not matches:
        return None, -1.0
    m = matches[-1]
    spans = [p.span() for p in PHRASE_RE.finditer(text)]
    in_phrase = any(a <= m.start() and m.end() <= b for a, b in spans)
    frac = m.start() / max(1, len(text))
    if in_phrase:
        return "instruction_echo", frac
    if frac >= 0.98:
        return "terminal", frac
    return "mid_trace", frac


def readouts(content: str, reasoning: str) -> dict:
    """All three declared readouts plus the provenance of the fallback token."""
    c_ans, c_off = last_answer(content)
    r_ans, r_off = last_answer(reasoning)
    loose = c_ans if c_ans else r_ans
    strict_trace = strict_last_trace_token(reasoning)
    delivered_or_strict = c_ans if c_ans else strict_trace
    pcls, pfrac = provenance_class(reasoning)
    return {"content_answer": c_ans, "content_offset": c_off,
            "reasoning_answer": r_ans, "reasoning_offset": r_off,
            "loose_fallback_answer": loose,
            "loose_fallback_source": "content" if c_ans else ("reasoning" if r_ans else "none"),
            "strict_trace_token": strict_trace,
            "delivered_or_strict_answer": delivered_or_strict,
            "fallback_provenance_class": pcls,
            "fallback_commit_fraction": round(pfrac, 4) if pfrac >= 0 else None}


def classify_attempt(att: dict) -> str:
    if att.get("error_class"):
        return f"transport_{att['error_class']}"
    if att["completion_tokens"] == 0:
        return "empty_completion"
    if att["content_answer"] is not None:
        return "answered_in_answer_field"
    if att["reasoning_answer"] is not None:
        return "trace_only"
    if att["finish_reason"] == "length":
        return "truncated_no_answer"
    return "no_answer_stop"


def is_retryable(outcome: str) -> bool:
    return outcome == "empty_completion" or outcome.startswith("transport_")


# ---------------------------------------------------------------------------
# Statistics helpers (inherited from round 38's script, verbatim)
# ---------------------------------------------------------------------------

def ols(points: list) -> dict:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    n = len(points)
    if n < 2:
        return {"slope": None, "intercept": None, "r": None, "n": n}
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in points)
    syy = sum((y - my) ** 2 for y in ys)
    slope = (sxy / sxx) if sxx else None
    r = (sxy / math.sqrt(sxx * syy)) if (sxx and syy) else None
    return {"slope": (round(slope, 6) if slope is not None else None),
            "intercept": (round(my - slope * mx, 3) if slope is not None else None),
            "r": (round(r, 4) if r is not None else None), "n": n}


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple:
    if total == 0:
        return 0.0, 0.0
    p = successes / total
    denom = 1.0 + z * z / total
    centre = p + z * z / (2 * total)
    span = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return (centre - span) / denom, (centre + span) / denom


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact sign test on the discordant pair counts."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2.0 ** n)
    return min(1.0, 2.0 * tail)


def quantile(values: list, q: float):
    """Linear-interpolated empirical quantile (the definition matters at n = 12 and n = 36)."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = q * (len(ordered) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] * (1.0 - (pos - lo)) + ordered[hi] * (pos - lo)


def output_sha(content: str, reasoning: str) -> str:
    """The quantity TARr is measured on: the whole sanitized generation, reasoning field and
    answer field together, in a fixed order, U+0000 separated. Two dispatches agree on raw
    output only when every token of both fields is identical."""
    return sha256_text((content or "") + "\x00" + (reasoning or ""))


def reasoning_merge(reasoning_content: str, reasoning_alt: str) -> tuple:
    """The declared merge rule (frozen in the gate): the "reasoning_content" value when
    non-empty, else the "reasoning" value, else empty; returns (text, supply field)."""
    if reasoning_content:
        return reasoning_content, "reasoning_content"
    if reasoning_alt:
        return reasoning_alt, "reasoning"
    return "", "none"


# ---------------------------------------------------------------------------
# Endpoint (the inherited stack plus the one declared extension: field census)
# ---------------------------------------------------------------------------

def endpoint_url() -> str:
    base = os.environ.get("NIGHTLY_BASE_URL", "").strip().rstrip("/")
    if not base:
        raise SystemExit("NIGHTLY_BASE_URL is not set; the probe cannot run")
    return base + "/chat/completions"


def call_endpoint(prompt: str, max_tokens: int, deadline_s: int) -> dict:
    key = os.environ.get("NIGHTLY_API_KEY", "").strip()
    model = os.environ.get("NIGHTLY_MODEL_ID", "").strip()
    body = json.dumps({"model": model,
                       "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens,
                       "temperature": TEMPERATURE,
                       "stream": False}).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(endpoint_url(), data=body, method="POST",
                                 headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=deadline_s) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace"))
        choice = (payload.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        usage = payload.get("usage") or {}
        text, field = reasoning_merge(sanitize(msg.get("reasoning_content") or ""),
                                      sanitize(msg.get("reasoning") or ""))
        return {
            "content": sanitize(msg.get("content") or ""),
            "reasoning": text,
            "reasoning_field": field,
            "message_fields": sorted(sanitize(str(k)) for k in msg.keys()),
            "finish_reason": choice.get("finish_reason"),
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
        }
    except urllib.error.HTTPError as exc:
        return {"error": f"http_{exc.code}", "content": "", "reasoning": "",
                "reasoning_field": "none", "message_fields": [],
                "finish_reason": None, "prompt_tokens": 0, "completion_tokens": 0}
    except (urllib.error.URLError, TimeoutError, OSError,
            json.JSONDecodeError) as exc:
        return {"error": type(exc).__name__, "content": "", "reasoning": "",
                "reasoning_field": "none", "message_fields": [],
                "finish_reason": None, "prompt_tokens": 0, "completion_tokens": 0}


class AttemptBudget:
    """Hard cap on total endpoint calls for the whole run (health included)."""

    def __init__(self, cap: int):
        self.cap = cap
        self.lock = threading.Lock()
        self.used = 0

    def acquire(self) -> bool:
        with self.lock:
            if self.used >= self.cap:
                return False
            self.used += 1
            return True


def health_check() -> dict:
    t0 = time.monotonic()
    resp = call_endpoint(HEALTH_PROMPT, HEALTH_BUDGET, deadline_s=240)
    latency = round(time.monotonic() - t0, 3)
    ro = readouts(resp["content"], resp["reasoning"])
    att = {"error_class": resp.get("error"),
           "completion_tokens": resp["completion_tokens"],
           "content_answer": ro["content_answer"],
           "reasoning_answer": ro["reasoning_answer"]}
    return {"ok": classify_attempt(att) == "answered_in_answer_field",
            "outcome": classify_attempt(att), "latency_s": latency,
            "completion_tokens": resp["completion_tokens"],
            "prompt_tokens": resp["prompt_tokens"],
            "reasoning_chars": len(resp["reasoning"]),
            "reasoning_field": resp["reasoning_field"],
            "message_fields": resp["message_fields"],
            "started_at": now_iso(), "finished_at": now_iso()}


def expected_chain(item: dict):
    """Ordered node sequence of the queried chain when gold is yes."""
    if item["answer"] != "yes":
        return None
    adj: dict = {}
    for s, _, t in item["facts"]:
        adj[s] = t
    seq = [item["query"][0]]
    for _ in range(item["level"]):
        seq.append(adj.get(seq[-1], "?"))
    return seq


def ordered_prefix_hops(seq, text: str) -> int:
    pos = -1
    hops = 0
    for node in seq:
        idx = text.find(node, pos + 1)
        if idx < 0:
            return hops
        pos = idx
        hops += 1
    return hops


def distractor_names(item: dict) -> list:
    """Every entity on a path other than the queried source's own path: name-mention
    counting over these measures how much of the output is spent enumerating facts the
    query does not need."""
    out_m = {s: t for s, _, t in item["facts"]}
    inc_set = {t for _, _, t in item["facts"]}
    nodes = {s for s, _, _ in item["facts"]} | inc_set
    src = item["query"][0]
    own = {src}
    node = src
    for _ in range(item["level"]):
        node = out_m.get(node)
        if node is None:
            break
        own.add(node)
    others = [n for n in nodes if n not in own]
    heads = [n for n in others if n not in inc_set]
    out = []
    for head in heads:
        node = head
        for _ in range(item["level"]):
            out.append(node)
            node = out_m.get(node)
            if node is None:
                break
        if node is not None:
            out.append(node)
    return out


def mechanics(item: dict, att: dict, prompt: str) -> dict:
    text = (att.get("reasoning") or "") + " " + (att.get("content") or "")
    seq = expected_chain(item)
    hops = ordered_prefix_hops(seq, text) if seq else None
    dis = distractor_names(item)
    mentioned = sum(1 for n in dis if n in text)
    src, tgt = item["query"][0], item["query"][2]
    return {
        "ordered_prefix_hops": hops,
        "expected_hops": len(seq) if seq else None,
        "coverage_ratio": (round(hops / len(seq), 4)
                           if seq and hops is not None else None),
        "completion_tokens": att["completion_tokens"],
        "budget_utilisation": round(att["completion_tokens"] / MAX_TOKENS, 4),
        "reasoning_chars": len(att.get("reasoning") or ""),
        "content_chars": len(att.get("content") or ""),
        "distractor_entities": len(dis),
        "distractors_mentioned": mentioned,
        "distractor_mention_ratio": round(mentioned / len(dis), 4) if dis else None,
        "src_first_mention_frac": round(prompt.find(src) / max(len(prompt), 1), 4),
        "tgt_first_mention_frac": round(prompt.find(tgt) / max(len(prompt), 1), 4),
    }


GATE_HASH = "unset"


def blank_record(item: dict, arm: str, pair_seed: int, phase: int) -> dict:
    prompt = render_prompt(item)
    return {
        "arm": arm, "level": item["edges"], "k": item["level"],
        "chains": item["chains"], "edges": item["edges"], "seed": item["seed"],
        "pair_seed": pair_seed, "seed_hash": item["seed_hash"],
        "item_sha256": sha256_text(canonical(item)),
        "prompt_sha256": sha256_text(prompt), "prompt_chars": len(prompt),
        "gold": 1 if item["answer"] == "yes" else 0,
        "gate_hash": GATE_HASH, "phase": phase, "attempts": [],
    }


def write_jsonl(path: str, rec: dict) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(canonical(rec) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


# ---------------------------------------------------------------------------
# Panel, anchor, slopes, gate
# ---------------------------------------------------------------------------

def panel_units() -> list:
    """The 12 panel prompts: arm F and arm X of pair PANEL_PAIR_INDEX of every cell, in WALK
    order. Selection is by the archived selection order (build_cell is deterministic in the
    seed and takes candidates in seed order), so pair 0 here is pair 0 of round 24's corpus
    and no outcome influences the choice. Refuses unless every digest is one of
    PANEL_DIGESTS, every PANEL_DIGESTS entry is returned, and every panel digest carries an
    arm-consistent entry in the round-38 P1 transcription."""
    units = []
    for name, k, c_chains in WALK:
        pairs, _pool, _paired = build_cell(k, c_chains, PANEL_PAIR_INDEX + 1)
        f_item, x_item = pairs[PANEL_PAIR_INDEX]
        for arm, item in (("F", f_item), ("X", x_item)):
            violations = verify_item(item)
            if violations:
                raise RuntimeError(f"panel {name} {arm}: {violations}")
            prompt = render_prompt(item)
            units.append({"cell": name, "arm": arm, "item": item, "prompt": prompt,
                          "digest": sha256_text(prompt), "k": k, "chains": c_chains,
                          "edges": k * c_chains,
                          "gold": 1 if item["answer"] == "yes" else 0})
    observed = sorted((u["cell"], u["digest"]) for u in units)
    if observed != sorted(PANEL_DIGESTS):
        raise RuntimeError("panel drifted from the pinned digests")
    for u in units:
        if u["digest"] not in PANEL_CELLS[u["cell"]]:
            raise RuntimeError(f"panel digest {u['digest'][:12]} outside cell {u['cell']}")
        archived = PANEL_ARCHIVE["R38P1"].get(u["digest"])
        if archived is None or archived["arm"] != u["arm"] or archived["k"] != u["k"]:
            raise RuntimeError(f"panel digest {u['digest'][:12]} missing from the R38P1 archive")
    return units


def anchor_state(gate: dict) -> dict:
    """Fail-closed structural pin. Every cell's pool blob and all 36 prompt digests must
    equal round 24's gate, and the 12-entry panel must be a subset of those digests.
    Constants only, no file dependency, so the post-merge tree verifies the pin without the
    ancestor branch."""
    cells = {c["cell"]: c for c in gate["cells"]}
    rows = {}
    for cell_id in WALK_INDEX:
        expected = R24_DIGESTS[cell_id]
        cell = cells.get(cell_id)
        observed_blob = cell["pool_blob_sha256"] if cell else None
        observed_f = sorted(cell["forward_prompt_sha256"]) if cell else []
        observed_x = sorted(cell["cross_prompt_sha256"]) if cell else []
        corpus = set(expected["forward_prompt_sha256"]) | set(expected["cross_prompt_sha256"])
        rows[cell_id] = {
            "cell": cell_id,
            "expected_pool_blob_sha256": expected["pool_blob_sha256"],
            "observed_pool_blob_sha256": observed_blob,
            "pool_blob_matches": observed_blob == expected["pool_blob_sha256"],
            "expected_forward_prompts": sorted(expected["forward_prompt_sha256"]),
            "observed_forward_prompts": observed_f,
            "forward_prompts_match": observed_f == sorted(expected["forward_prompt_sha256"]),
            "expected_cross_prompts": sorted(expected["cross_prompt_sha256"]),
            "observed_cross_prompts": observed_x,
            "cross_prompts_match": observed_x == sorted(expected["cross_prompt_sha256"]),
            "panel_digests": sorted(PANEL_CELLS.get(cell_id, [])),
            "panel_in_corpus": set(PANEL_CELLS.get(cell_id, [])) <= corpus,
        }
    all_ok = all(r["pool_blob_matches"] and r["forward_prompts_match"]
                 and r["cross_prompts_match"] and r["panel_in_corpus"]
                 for r in rows.values())
    return {"checked": True, "all_ok": all_ok, "anchors": rows,
            "provenance": ("research/nightly-2026-10-25-0405 (round 24, PR #98), gate.json, "
                           "all six cells of the declared grid; the panel is pair 0 of "
                           "each cell")}


def panel_axis_slope(token_table: dict, axis: str):
    """One panel-basis cost slope: "load" = mean cell tokens against E over the four k = 8
    cells; "depth" = mean cell tokens against k over the E = 96 cells (L0, D1, D2). Same
    estimator as the published full-design laws, on 2 items per cell instead of 6. Refuses
    a partial cell, so a missing dispatch cannot silently move a slope."""
    if axis == "load":
        names = LOAD_NAMES
    elif axis == "depth":
        names = ("L0",) + DEPTH_NAMES
    else:
        raise ValueError(axis)
    means = {}
    for cell in names:
        vals = [token_table[d] for d in PANEL_CELLS[cell] if d in token_table]
        if len(vals) != len(PANEL_CELLS[cell]):
            return None
        means[cell] = sum(vals) / len(vals)
    if axis == "load":
        pts = [(PANEL_EDGES[c], means[c]) for c in names]
    else:
        pts = [(PANEL_K[c], means[c]) for c in names]
    fit = ols(pts)
    return fit["slope"]


def firing_slopes(token_table: dict) -> dict:
    """Panel-basis cost slopes from a {digest: completion tokens} table. Refuses a partial
    cell, so a missing dispatch cannot silently move a slope."""
    load = panel_axis_slope(token_table, "load")
    depth = panel_axis_slope(token_table, "depth")
    means = {}
    for cell, digests in PANEL_CELLS.items():
        vals = [token_table[d] for d in digests if d in token_table]
        if len(vals) != len(digests):
            return {"load": None, "depth": None, "cell_means": None,
                    "note": f"cell {cell} has {len(vals)} of {len(digests)} items"}
        means[cell] = sum(vals) / len(vals)
    return {"load": (round(load, 4) if load is not None else None),
            "depth": (round(depth, 4) if depth is not None else None),
            "cell_means": {k: round(v, 2) for k, v in means.items()},
            "note": "panel basis: 2 items per cell"}


def panel_reference_slopes() -> dict:
    """Panel-basis slopes of the archived firings, computed from the transcribed archives at
    gate time, so the reference a band is scored against is inside gate.json before any
    prompt is spent."""
    return {label: firing_slopes({d: v["tok"] for d, v in archive.items()})
            for label, archive in PANEL_ARCHIVE.items()}


def band_for(reference, band: tuple) -> list:
    """The house band around a reference slope, ordered so a negative reference still gives
    a usable interval (rounds 31 and 37 both score against negative references)."""
    if reference is None:
        return [None, None]
    lo, hi = sorted((reference * band[0], reference * band[1]))
    return [round(lo, 4), round(hi, 4)]


def in_band(value, reference, band: tuple) -> bool:
    if value is None or reference is None:
        return False
    lo, hi = band_for(reference, band)
    return lo <= value <= hi


def build_gate() -> dict:
    cells = all_cells()
    panel = panel_units()
    refs = panel_reference_slopes()
    reference = refs[N5_REFERENCE_FIRING]
    out = {
        "schema": GATE_SCHEMA, "round": ROUND_LABEL, "seed_base": SEED_BASE,
        "alpha": ALPHA, "perms": PERMS,
        "class_label": CLASS_LABEL,
        "load_arm": [{"cell": n, "k": k, "chains": c, "edges": k * c} for n, k, c in LOAD_ARM],
        "depth_arm": [{"cell": n, "k": k, "chains": c, "edges": k * c} for n, k, c in DEPTH_ARM],
        "pairs_per_cell": PAIRS_PER_LEVEL,
        "panel": {"pair_index": PANEL_PAIR_INDEX, "items": len(panel),
                  "passes": [dict(p) for p in PASS_PLAN],
                  "digests": [{"cell": u["cell"], "arm": u["arm"], "digest": u["digest"],
                               "k": u["k"], "edges": u["edges"], "gold": u["gold"]}
                              for u in panel]},
        "max_tokens": MAX_TOKENS, "temperature": TEMPERATURE,
        "readouts": ["content_only", "loose_fallback", "delivered_or_strict"],
        "reasoning_merge_rule": ("reasoning text is the reasoning_content value when "
                                 "non-empty, else the reasoning value, else empty; the "
                                 "supply field is recorded per attempt"),
        "matched_pair_invariant": ("identical fact list, identical entity name set, "
                                   "identical fact count, identical queried source; only "
                                   "the queried target varies (issue #78 acceptance "
                                   "criterion 1, polarity contrast)"),
        "panel_reference_slopes": refs,
        "published_full_design_slopes": PUBLISHED_SLOPES,
        "r37_content_surface": dict(R37_CONTENT_SURFACE),
        "r37_collapse_hashes": dict(R37_COLLAPSE),
        "boot": {"draws": BOOT_DRAWS, "seed": BOOT_SEED, "quantiles": list(FLOOR_QUANTILES),
                 "resolve_quantile": RESOLVE_QUANTILE},
        "strata": {k: [list(p) for p in v] for k, v in STRATA.items()},
        "predictions": {
            "T1_P1_dispatches_with_nonempty_reasoning_ge": T1_CHANNEL_MIN,
            "T2_P1_dispatches_with_dr_positive_ge": T2_DR_POSITIVE_MIN,
            "T2_P1_mean_dr_ge": T2_DR_MEAN_MIN,
            "T3_billing_anomalies_max": T3_BILLING_ANOMALIES_MAX,
            "T4_cross_class_full_text_identical_max": T4_CROSS_CLASS_TARR_MAX,
            "T4_cross_class_answer_agreement_over_both_delivered_ge": T4_CROSS_CLASS_TARA_RATIO_MIN,
            "T5_P1_prompts_within_factor2_of_R37_ge": T5_R37_FACTOR2_MIN,
            "N1_within_run_same_mode_tarr_ge": N1_TARR_GRID_MIN,
            "N1_within_run_same_mode_tarr_cell_ge": N1_TARR_CELL_MIN,
            "N2_within_run_mode_change_tarr_ge": N2_TARR_GRID_MIN,
            "N2_within_run_mode_change_abs_token_change_le": N2_TOKEN_DELTA_MAX,
            "N3_tara_every_stratum_ge": N3_TARA_GRID_MIN,
            "N4_all_dispatches_deliver_content_answer": N4_DELIVERED_MIN,
            "N4_all_dispatches_correct_content_only": N4_CORRECT_MIN,
            "N5_pass_panel_load_slope_in_band": band_for(reference["load"], N5_COST_BAND),
            "N5_pass_panel_depth_slope_in_band": band_for(reference["depth"], N5_COST_BAND),
            "N5_band_reference": N5_REFERENCE_FIRING,
            "N6_guard": (f"a slope difference counts as a change only beyond the "
                         f"{RESOLVE_QUANTILE} quantile of the same-class floor of its own "
                         f"stratum; a stratum whose floor rests on a single observed pair "
                         f"is reported as not separable, never as a change")},
        "cells": [],
    }
    for cell in cells:
        prompts = [render_prompt(it) for pair in cell["pairs"] for it in pair]
        chars = [len(p) for p in prompts]
        out["cells"].append({
            "arm": "S", "cell": cell["cell"], "index": cell["index"], "k": cell["k"],
            "chains": cell["chains"], "edges": cell["edges"], "level": cell["edges"],
            "load": {"facts": cell["edges"],
                     "prompt_chars_mean": round(sum(chars) / len(chars), 1),
                     "prompt_chars_min": min(chars), "prompt_chars_max": max(chars)},
            "forward_item_sha256": [sha256_text(canonical(p[0])) for p in cell["pairs"]],
            "forward_prompt_sha256": [sha256_text(render_prompt(p[0])) for p in cell["pairs"]],
            "cross_prompt_sha256": [sha256_text(render_prompt(p[1])) for p in cell["pairs"]],
            "pool_blob_sha256": sha256_text(canonical(cell["pool"])),
            "paired_pool_blob_sha256": sha256_text(canonical(cell["paired_pool"])),
            "gate_pool": gate_battery(cell["pool"]),
            "gate_paired_pool": gate_battery(cell["paired_pool"])})
    out["corpus_blob_sha256"] = sha256_text(
        canonical([c["paired_pool_blob_sha256"] for c in out["cells"]]))
    out["planned_prompts"] = len(panel) * len(PASS_PLAN)
    out["prompt_cap"] = PROMPT_CAP
    out["health_calls"] = HEALTH_CALLS
    out["all_cells_pass"] = all(
        c["gate_pool"]["verdict"] != "leak" and c["gate_paired_pool"]["verdict"] != "leak"
        for c in out["cells"])
    out["anchor"] = anchor_state(out)
    out["anchor_ok"] = out["anchor"]["all_ok"]
    return out


def gate_hash(gate: dict) -> str:
    return sha256_text(canonical(gate))


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def dispatch_record(unit: dict, plan: dict, budget: "AttemptBudget", order_index: int) -> dict:
    """One (prompt, pass) measurement: the archived record shape plus the three labels this
    round needs (pass_id, dispatch_mode, order_in_pass) and the two field-census fields.
    Retries follow the inherited rule (transport failure or empty completion only), and
    every attempt is kept."""
    item = unit["item"]
    rec = blank_record(item, unit["arm"], unit["item"]["seed"],
                       PASS_IDS.index(plan["pass_id"]) + 1)
    rec["cell"] = unit["cell"]
    rec["pass_id"] = plan["pass_id"]
    rec["dispatch_mode"] = plan["mode"]
    rec["dispatch_concurrency"] = plan["concurrency"]
    rec["order_in_pass"] = order_index
    prompt = unit["prompt"]
    for attempt_no in range(1, 4):
        if not budget.acquire():
            rec["attempts"].append({"attempt": attempt_no, "wall_s": 0.0,
                                    "error_class": "cap_exceeded", "started_at": now_iso(),
                                    "finished_at": now_iso(), "finish_reason": None,
                                    "prompt_tokens": 0, "completion_tokens": 0,
                                    "content": "", "reasoning": "",
                                    "reasoning_field": "none", "message_fields": [],
                                    "output_sha256": output_sha("", "")})
            break
        t0 = time.monotonic()
        started = now_iso()
        resp = call_endpoint(prompt, MAX_TOKENS, deadline_s=ITEM_DEADLINE_S)
        wall = round(time.monotonic() - t0, 3)
        att = {"attempt": attempt_no, "wall_s": wall, "error_class": resp.get("error"),
               "started_at": started, "finished_at": now_iso(),
               "finish_reason": resp["finish_reason"],
               "prompt_tokens": resp["prompt_tokens"],
               "completion_tokens": resp["completion_tokens"],
               "content": resp["content"], "reasoning": resp["reasoning"],
               "reasoning_field": resp["reasoning_field"],
               "message_fields": resp["message_fields"]}
        att.update(readouts(resp["content"], resp["reasoning"]))
        att["mechanics"] = mechanics(item, att, prompt)
        att["output_sha256"] = output_sha(resp["content"], resp["reasoning"])
        rec["attempts"].append(att)
        if not is_retryable(classify_attempt(att)):
            break
    last = rec["attempts"][-1]
    for field in ("content_answer", "reasoning_answer", "loose_fallback_answer",
                  "loose_fallback_source", "strict_trace_token", "delivered_or_strict_answer",
                  "fallback_provenance_class", "fallback_commit_fraction"):
        rec[field] = last[field]
    rec["reasoning_field"] = last.get("reasoning_field", "none")
    rec["message_fields"] = last.get("message_fields", [])
    rec["completion_tokens"] = last.get("completion_tokens", 0)
    rec["prompt_tokens"] = last.get("prompt_tokens", 0)
    rec["outcome"] = classify_attempt(last)
    rec["finish_reason"] = last.get("finish_reason")
    rec["output_sha256"] = last.get("output_sha256", output_sha("", ""))
    rec["distractor_mention_ratio"] = last["mechanics"]["distractor_mention_ratio"]
    gold = rec["gold"]
    rec["correct"] = {}
    for name in ("content_only", "loose_fallback", "delivered_or_strict"):
        ans = {"content_only": last["content_answer"],
               "loose_fallback": last["loose_fallback_answer"],
               "delivered_or_strict": last["delivered_or_strict_answer"]}[name]
        rec["correct"][name] = (None if ans is None
                                else int((1 if ans == "yes" else 0) == gold))
    rec["delivered"] = last["content_answer"] is not None
    rec["truncated"] = last.get("finish_reason") == "length"
    rec["retried"] = len(rec["attempts"]) > 1
    return rec


class RecordSink:
    """Incremental archive (#73): every measurement is appended and fsynced the moment it
    lands, so a firing that is killed mid-pass leaves the measurements it already paid
    for. Round 35 and round 36 both lost a whole round to a run that only held its records
    in memory."""

    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()
        self.count = 0

    def emit(self, rec: dict) -> None:
        with self.lock:
            write_jsonl(self.path, rec)
            self.count += 1
        print(f"  [{self.count}] {rec['pass_id']} {rec['cell']} {rec['arm']} "
              f"{rec['prompt_sha256'][:12]} tokens {rec['completion_tokens']} "
              f"answer {rec['content_answer']} outcome {rec['outcome']}", flush=True)


def run_pass(plan: dict, units: list, budget: "AttemptBudget", sink=None) -> tuple:
    """One pass over the panel at the pass's own concurrency, records returned in panel
    order and emitted to the sink as they land."""
    t0 = time.monotonic()
    results: dict = {}
    if plan["concurrency"] <= 1:
        for idx, unit in enumerate(units):
            rec = dispatch_record(unit, plan, budget, idx)
            results[idx] = rec
            if sink:
                sink.emit(rec)
    else:
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=plan["concurrency"],
                thread_name_prefix=str(plan["pass_id"])) as pool:
            futures = {pool.submit(dispatch_record, unit, plan, budget, idx): idx
                       for idx, unit in enumerate(units)}
            for future in concurrent.futures.as_completed(futures):
                key = futures[future]
                rec = future.result()
                results[key] = rec
                if sink:
                    sink.emit(rec)
    records = [results[i] for i in range(len(units))]
    starts = [a["started_at"] for r in records for a in r["attempts"] if a.get("started_at")]
    ends = [a["finished_at"] for r in records for a in r["attempts"] if a.get("finished_at")]
    stats = {"pass_id": plan["pass_id"], "mode": plan["mode"],
             "concurrency": plan["concurrency"], "items": len(records),
             "wall_s": round(time.monotonic() - t0, 1),
             "completion_tokens": sum(r["completion_tokens"] for r in records),
             "prompt_tokens": sum(r["prompt_tokens"] for r in records),
             "retries": sum(1 for r in records if r["retried"]),
             "transport_errors": sum(1 for r in records
                                     if r["outcome"].startswith("transport_")
                                     or r["outcome"] == "cap_exceeded"),
             "truncations": sum(1 for r in records if r["truncated"]),
             "delivered": sum(1 for r in records if r["delivered"]),
             "started_at": min(starts) if starts else None,
             "finished_at": max(ends) if ends else None}
    return records, stats


def probe(out_dir: str, resume: bool) -> int:
    gate_path = os.path.join(out_dir, "gate.json")
    if not os.path.exists(gate_path):
        raise SystemExit(f"{gate_path} not found: run --gate first, the gate must precede "
                         "the dispatch")
    with open(gate_path, encoding="utf-8") as fh:
        gate = json.load(fh)
    global GATE_HASH
    GATE_HASH = gate_hash(gate)
    if not gate.get("anchor_ok"):
        raise SystemExit("structural pin failed: the grid is not round 24's grid")
    if not gate.get("all_cells_pass"):
        raise SystemExit("leak audit failed on at least one cell")
    units = panel_units()
    raw_path = os.path.join(out_dir, "raw.jsonl")
    done: set = set()
    if resume and os.path.exists(raw_path):
        with open(raw_path, encoding="utf-8") as fh:
            for line in fh:
                rec = json.loads(line)
                if rec.get("gate_hash") != GATE_HASH:
                    raise SystemExit("raw.jsonl carries a different gate hash")
                if not (rec["outcome"].startswith("transport_")
                        or rec["outcome"] in ("empty_completion", "cap_exceeded")):
                    done.add((rec["prompt_sha256"], rec["pass_id"]))
        print(f"resume: {len(done)} of {len(units) * len(PASS_PLAN)} measurements kept")
    budget = AttemptBudget(PROMPT_CAP)
    sink = RecordSink(raw_path)
    health = health_check()
    print(f"health: ok={health['ok']} outcome={health['outcome']} "
          f"latency={health['latency_s']}s reasoning_field={health['reasoning_field']} "
          f"reasoning_chars={health['reasoning_chars']}")
    if not health["ok"]:
        raise SystemExit("endpoint health check failed before the panel")
    health_path = os.path.join(out_dir, "health.json")
    with open(health_path, "w", encoding="utf-8") as fh:
        json.dump(health, fh, indent=1, sort_keys=True)
        fh.write("\n")
    for plan in PASS_PLAN:
        pending = [u for u in units if (u["digest"], plan["pass_id"]) not in done]
        if not pending:
            print(f"pass {plan['pass_id']}: complete, skipped")
            continue
        print(f"pass {plan['pass_id']} ({plan['mode']}, concurrency {plan['concurrency']}): "
              f"{len(pending)} prompts", flush=True)
        records, stats = run_pass(plan, pending, budget, sink)
        print(f"  pass {plan['pass_id']} wall {stats['wall_s']}s, completion tokens "
              f"{stats['completion_tokens']}, retries {stats['retries']}, transport errors "
              f"{stats['transport_errors']}", flush=True)
    print(f"endpoint calls used: {HEALTH_CALLS + budget.used} of the {PROMPT_CAP} cap "
          f"({HEALTH_CALLS} health + {budget.used} panel dispatches)")
    return 0


# ---------------------------------------------------------------------------
# Measurements
# ---------------------------------------------------------------------------

def measurements(records: list) -> dict:
    """Per (pass, digest) final-attempt table: the quantities every comparison in this round
    consumes."""
    meas: dict = {}
    for rec in records:
        att = rec["attempts"][-1]
        key = (rec["pass_id"], rec["prompt_sha256"])
        meas[key] = {
            "cell": rec["cell"], "arm": rec["arm"], "gold": rec["gold"],
            "k": rec["k"], "edges": rec["edges"],
            "tok": rec["completion_tokens"], "ptok": rec["prompt_tokens"],
            "ans": rec["content_answer"], "sha": rec["output_sha256"],
            "delivered": rec["delivered"], "outcome": rec["outcome"],
            "correct": rec["correct"],
            "content_chars": att["mechanics"]["content_chars"],
            "reasoning_chars": att["mechanics"]["reasoning_chars"],
            "reasoning_field": att.get("reasoning_field", "none"),
            "message_fields": att.get("message_fields", []),
            "dr": rec["distractor_mention_ratio"],
            "truncated": rec["truncated"],
            "content": att.get("content", ""),
        }
    return meas


def archived_table(label: str) -> dict:
    """The transcribed {digest: tok} table of an archived firing (panel basis)."""
    return {d: v["tok"] for d, v in PANEL_ARCHIVE[label].items()}


def rel_dev(a, b):
    """Absolute relative deviation of two billed lengths, on the smaller side as base, so a
    large prompt is not hidden by a large denominator."""
    if a is None or b is None or min(a, b) == 0:
        return None
    return abs(a - b) / min(a, b)


def stratum_pairs(meas: dict, label_a: str, label_b: str) -> list:
    """Per-prompt (digest, a, b) rows for two labels, where a label is a pass id (P1, P2,
    P3, looked up in the live measurements) or an archived firing id (R31, R37, R38P1,
    looked up in the transcribed tables)."""
    def get(label, digest):
        cell = next(c for c, ds in PANEL_CELLS.items() if digest in ds)
        if label in PASS_IDS:
            m = meas.get((label, digest))
            if m is None:
                return None
            return {"tok": m["tok"], "ans": m["ans"], "sha": m["sha"],
                    "delivered": m["delivered"], "reasoning_chars": m["reasoning_chars"],
                    "dr": m["dr"], "content_chars": m["content_chars"],
                    "cell": m["cell"], "arm": m["arm"], "gold": m["gold"]}
        v = PANEL_ARCHIVE[label].get(digest)
        if v is None:
            return None
        return {"tok": v["tok"], "ans": v["ans"],
                "sha": v.get("out_sha"), "delivered": v["ans"] is not None,
                "reasoning_chars": len(v.get("reasoning", "")) if "reasoning" in v else None,
                "dr": v.get("dr"), "content_chars": None,
                "cell": cell, "arm": v["arm"], "gold": v.get("gold")}
    rows = []
    for d in sorted({d for ds in PANEL_CELLS.values() for d in ds}):
        a = get(label_a, d)
        b = get(label_b, d)
        if a is not None and b is not None:
            rows.append((d, a, b))
    return rows


def stratum_agreement(rows: list) -> dict:
    """TARr (raw output byte identity on joinable pairs), TARa (parsed answer agreement),
    billed-token deltas and material moves over one stratum's rows. Pairs whose both sides
    carry no joinable text (out_sha missing) are counted as non-joinable, never as
    disagreement."""
    n = len(rows)
    if n == 0:
        return {"pairs": 0}
    joinable = [(d, a, b) for d, a, b in rows if a.get("sha") and b.get("sha")]
    tar_r_hits = sum(1 for _d, a, b in joinable if a["sha"] == b["sha"])
    both_delivered = [(d, a, b) for d, a, b in rows if a["delivered"] and b["delivered"]]
    tara_hits = sum(1 for _d, a, b in both_delivered if a["ans"] == b["ans"])
    tok_deltas = [(d, a["tok"], b["tok"]) for d, a, b in rows]
    rel_devs = [rel_dev(a, b) for _d, a, b in tok_deltas]
    rel_devs = [r for r in rel_devs if r is not None]
    material = sum(1 for r in rel_devs if r >= MATERIAL_REL_DEV)
    return {
        "pairs": n,
        "joinable_pairs": len(joinable),
        "tarr": (round(tar_r_hits / len(joinable), 4) if joinable else None),
        "tarr_hits": tar_r_hits,
        "tarr_wilson": list(wilson(tar_r_hits, len(joinable))) if joinable else [None, None],
        "tara": (round(tara_hits / len(both_delivered), 4) if both_delivered else None),
        "tara_hits": tara_hits,
        "tara_pairs_both_delivered": len(both_delivered),
        "tok_delta_mean": round(sum(b - a for _d, a, b in tok_deltas) / n, 2),
        "tok_delta_median": quantile([b - a for _d, a, b in tok_deltas], 0.50),
        "rel_dev_median": round(quantile(rel_devs, 0.50), 4) if rel_devs else None,
        "rel_dev_max": round(max(rel_devs), 4) if rel_devs else None,
        "material_moves": material,
    }


def within_run(meas: dict) -> dict:
    out = {}
    for stratum, pairs in (("within_run_same_mode", [("P1", "P3")]),
                           ("within_run_mode_change", [("P1", "P2"), ("P2", "P3")])):
        per = []
        for la, lb in pairs:
            rows = stratum_pairs(meas, la, lb)
            agg = stratum_agreement(rows)
            agg["labels"] = [la, lb]
            per.append(agg)
        pooled = stratum_agreement([r for la, lb in pairs for r in stratum_pairs(meas, la, lb)])
        pooled["labels"] = ["P1", "P2", "P3"] if stratum == "within_run_mode_change" \
            else ["P1", "P3"]
        out[stratum] = {"per_pair": per, "pooled": pooled}
    return out


def per_cell_same_mode(meas: dict) -> dict:
    """The 2 same-mode pairs per cell (one prompt, P1 vs P3): the per-cell TARr N1 scores."""
    out = {}
    for cell in WALK_INDEX:
        hits = 0
        n = 0
        for d in PANEL_CELLS[cell]:
            a = meas.get(("P1", d))
            b = meas.get(("P3", d))
            if a and b:
                n += 1
                if a["sha"] == b["sha"]:
                    hits += 1
        out[cell] = {"pairs": n, "tarr_hits": hits,
                     "tarr": (hits / n if n else None),
                     "wilson": list(wilson(hits, n)) if n else [None, None]}
    return out


def billing_census(records: list) -> dict:
    """The lesson pre-check, run per pass before any text-derived metric is trusted:
    measure the text that exists."""
    out = {}
    for pass_id in PASS_IDS:
        recs = [r for r in records if r["pass_id"] == pass_id]
        rows = []
        for r in recs:
            att = r["attempts"][-1]
            mech = att["mechanics"]
            exposed = mech["reasoning_chars"] + mech["content_chars"]
            anomaly = att["completion_tokens"] * BILLING_CHARS_PER_TOKEN < exposed
            rows.append({"digest": r["prompt_sha256"], "cell": r["cell"], "arm": r["arm"],
                         "tok": att["completion_tokens"],
                         "reasoning_chars": mech["reasoning_chars"],
                         "content_chars": mech["content_chars"],
                         "reasoning_field": att.get("reasoning_field", "none"),
                         "message_fields": att.get("message_fields", []),
                         "billing_anomaly": anomaly})
        rc = [x["reasoning_chars"] for x in rows]
        cc = [x["content_chars"] for x in rows]
        fields = collections.Counter(x["reasoning_field"] for x in rows)
        field_names = sorted({f for x in rows for f in x["message_fields"]})
        margins = [x["tok"] - x["reasoning_chars"] / 4.0 for x in rows]
        out[pass_id] = {
            "records": len(rows),
            "reasoning_chars_nonzero": sum(1 for v in rc if v > 0),
            "reasoning_chars_min": min(rc) if rc else None,
            "reasoning_chars_median": round(quantile(rc, 0.50), 1) if rc else None,
            "reasoning_chars_max": max(rc) if rc else None,
            "content_chars_min": min(cc) if cc else None,
            "content_chars_median": round(quantile(cc, 0.50), 1) if cc else None,
            "content_chars_max": max(cc) if cc else None,
            "reasoning_field_census": dict(fields),
            "message_field_names_union": field_names,
            "billing_anomalies": sum(1 for x in rows if x["billing_anomaly"]),
            "billing_margin_median": round(quantile(margins, 0.50), 1) if margins else None,
            "billing_margin_note": ("median of billed tokens minus the exposed text at a "
                                    "4 chars per token heuristic; context only, not a "
                                    "tokenization"),
        }
    return out


def cross_firing_same_class(meas: dict) -> dict:
    """This firing's P1 against the two archived firings of this class (billed length and
    answer; R31 is non-joinable on text by construction)."""
    out = {}
    for label in ("R37", "R31"):
        rows = stratum_pairs(meas, label, "P1")
        agg = stratum_agreement(rows)
        per_prompt = []
        for d, a, b in rows:
            per_prompt.append({
                "digest": d, "cell": b["cell"], "arm": b["arm"],
                "tok_archived": a["tok"], "tok_this": b["tok"],
                "delta": b["tok"] - a["tok"],
                "rel_dev": round(rel_dev(a["tok"], b["tok"]), 4)
                           if rel_dev(a["tok"], b["tok"]) is not None else None,
                "ans_archived": a["ans"], "ans_this": b["ans"],
                "answer_agrees": (a["ans"] == b["ans"]) if (a["ans"] and b["ans"]) else None,
            })
        factor2 = sum(1 for p in per_prompt
                      if 0.5 <= (p["tok_this"] / p["tok_archived"]) <= 2.0)
        agg["within_factor2_of_archived"] = factor2
        out[label] = {"agreement": agg, "per_prompt": per_prompt}
    # Content-surface join against R37's collapsed hashes: does this firing answer with the
    # same bare-word surface (content-only hash) the R37 deployment left behind?
    surface = {"matched": 0, "rows": []}
    for d in sorted({d for ds in PANEL_CELLS.values() for d in ds}):
        r = meas.get(("P1", d))
        if r is None:
            continue
        content_only_sha = output_sha(r["content"], "")
        match = None
        for word, h in R37_COLLAPSE.items():
            if content_only_sha == h:
                match = word
        surface["rows"].append({"digest": d, "content": r["content"],
                                "content_only_sha": content_only_sha,
                                "matches_r37_collapse": match})
        if match:
            surface["matched"] += 1
    out["content_surface_vs_R37"] = surface
    return out


def cross_class(meas: dict) -> dict:
    """The headline comparison: this firing's P1 against round 38's P1 (flash class), now
    with reasoning text archived on both sides."""
    rows = stratum_pairs(meas, "R38P1", "P1")
    agg = stratum_agreement(rows)
    per_prompt = []
    for d, a, b in rows:
        per_prompt.append({
            "digest": d, "cell": b["cell"], "arm": b["arm"], "gold": b["gold"],
            "tok_flash": a["tok"], "tok_this": b["tok"],
            "rel_dev": round(rel_dev(a["tok"], b["tok"]), 4)
                       if rel_dev(a["tok"], b["tok"]) is not None else None,
            "ans_flash": a["ans"], "ans_this": b["ans"],
            "reasoning_chars_flash": a["reasoning_chars"],
            "reasoning_chars_this": b["reasoning_chars"],
            "dr_flash": a["dr"], "dr_this": b["dr"],
            "full_text_identical": bool(a.get("sha") and b.get("sha")
                                        and a["sha"] == b["sha"]),
        })
    both_have_text = sum(1 for p in per_prompt
                         if p["reasoning_chars_flash"] and p["reasoning_chars_this"])
    return {"agreement": agg, "per_prompt": per_prompt,
            "both_sides_text_archived": both_have_text,
            "measurability": ("the round-38 addendum's condition for a cross-class trace "
                              "claim (reasoning text surfaced and archived on both sides) "
                              "is met by this round on this class; the TARr above is a "
                              "measured byte comparison, not a structural zero")}


def enumeration_table(meas: dict) -> dict:
    """The distractor-mention comparison the two PRs of this class had reported as a class
    signature: R37 structural 0.0 (zero trace), flash class near 1.0, this firing with the
    channel exposed."""
    rows = []
    for d in sorted({d for ds in PANEL_CELLS.values() for d in ds}):
        m = meas.get(("P1", d))
        if m is None:
            continue
        r37 = PANEL_ARCHIVE["R37"][d]
        r38p1 = PANEL_ARCHIVE["R38P1"][d]
        rows.append({"digest": d, "cell": m["cell"], "arm": m["arm"], "gold": m["gold"],
                     "dr_this_p1": m["dr"], "dr_flash_r38p1": r38p1["dr"],
                     "dr_r37_structural": r37["dr"],
                     "reasoning_chars_this": m["reasoning_chars"],
                     "reasoning_chars_flash": len(r38p1["reasoning"])})
    drs = [r["dr_this_p1"] for r in rows if r["dr_this_p1"] is not None]
    return {"per_prompt": rows,
            "n_positive": sum(1 for v in drs if v > 0),
            "mean": round(sum(drs) / len(drs), 4) if drs else None,
            "median": round(quantile(drs, 0.50), 4) if drs else None}


def slope_noise_floor(base_table: dict, dev_pool: list, axis: str,
                      draws: int = BOOT_DRAWS, seed: int = BOOT_SEED) -> dict:
    """The round-38 noise guard, inherited: the observed per-prompt difference of a stratum
    is propagated through the same slope estimator, so the floor comes out in tokens per
    fact / tokens per hop, on the same scale as the quantity it judges."""
    if not dev_pool:
        return {"note": "no observed pairs; floor not separable"}
    base_slope = panel_axis_slope(base_table, axis)
    if base_slope is None:
        return {"note": "partial base cell; floor not separable"}
    rng = random.Random(seed + {"load": 0, "depth": 1}[axis])
    diffs = []
    for _ in range(draws):
        pert = {d: base_table[d] + rng.choice(dev_pool) for d in base_table}
        s = panel_axis_slope(pert, axis)
        if s is not None:
            diffs.append(abs(s - base_slope))
    return {
        "base_firing": sorted(base_table)[:1],
        "observed_pairs": len(dev_pool),
        "draws": draws,
        "quantiles": {f"q{int(q * 100)}": round(quantile(diffs, q), 4)
                      for q in FLOOR_QUANTILES},
        "note": "absolute slope difference, tokens per fact (load) or per hop (depth)"}


def floor_bundle(meas: dict) -> dict:
    """Every floor this round judges a claim with, per axis and per stratum kind."""
    out = {}
    # Within-run floors, base P1.
    for stratum, pairs in (("within_run_same_mode", [("P1", "P3")]),
                           ("within_run_mode_change", [("P1", "P2"), ("P2", "P3")])):
        pool = []
        for la, lb in pairs:
            for d, a, b in stratum_pairs(meas, la, lb):
                pool.append(b["tok"] - a["tok"])
        base = {d: meas[("P1", d)]["tok"]
                for d in {d for ds in PANEL_CELLS.values() for d in ds}
                if ("P1", d) in meas}
        out[stratum] = {"load": slope_noise_floor(base, pool, "load"),
                        "depth": slope_noise_floor(base, pool, "depth")}
    # Cross-firing floors of this class: three firings (R31, R37, P1), every pair.
    base_r37 = archived_table("R37")
    base_r31 = archived_table("R31")
    p1_table = {d: meas[("P1", d)]["tok"]
                for d in {d for ds in PANEL_CELLS.values() for d in ds}
                if ("P1", d) in meas}
    pairs_cf = [
        ("R37_vs_P1", base_r37, [p1_table[d] - base_r37[d] for d in base_r37]),
        ("R31_vs_P1", base_r31, [p1_table[d] - base_r31[d] for d in base_r31]),
        ("R31_vs_R37", base_r31, [base_r37[d] - base_r31[d] for d in base_r31]),
    ]
    out["cross_firing_this_class"] = {}
    for name, base, pool in pairs_cf:
        out["cross_firing_this_class"][name] = {
            "load": slope_noise_floor(base, pool, "load"),
            "depth": slope_noise_floor(base, pool, "depth")}
    # Cross-firing floor of the flash class from its two archived firings (round 33 and
    # round 38, both transcribed with billed tokens).
    base_r33 = archived_table("R33")
    r38p1_table = archived_table("R38P1")
    out["cross_firing_flash_class"] = {
        "R33_vs_R38P1": {
            "load": slope_noise_floor(base_r33, [r38p1_table[d] - base_r33[d]
                                                 for d in base_r33], "load"),
            "depth": slope_noise_floor(base_r33, [r38p1_table[d] - base_r33[d]
                                                  for d in base_r33], "depth")}}
    # The union floor a cross-class claim is judged against: the largest q99 either class has
    # demonstrated on this panel, per axis.
    def worst_q99(axis):
        vals = []
        for group in ("cross_firing_this_class", "cross_firing_flash_class"):
            for _name, axes in out[group].items():
                q = axes[axis].get("quantiles", {}).get("q99")
                if q is not None:
                    vals.append(q)
        return max(vals) if vals else None
    out["union_cross_class"] = {
        "load_q99": worst_q99("load"),
        "depth_q99": worst_q99("depth"),
        "note": ("largest cross-firing slope-difference floor (q99) demonstrated by either "
                 "class on the panel; a cross-class slope delta beyond it is resolvable, "
                 "within it is not (round 38's convention)")}
    return out


def slope_resolvability(slopes: dict, floors: dict, gate: dict) -> dict:
    """The N6-guarded slope statements: (a) this firing's law against the archived law of
    this class (R37, the zero-trace deployment); (b) this firing's law against the flash
    class's law (R38P1), judged against the union floor."""
    def delta(a, b):
        return round(a - b, 4) if (a is not None and b is not None) else None
    p1 = slopes.get("P1", {})
    r37 = gate["panel_reference_slopes"]["R37"]
    r38p1 = gate["panel_reference_slopes"]["R38P1"]
    cf_this = floors["cross_firing_this_class"]
    q99_this = {axis: max(v[axis]["quantiles"]["q99"]
                          for v in cf_this.values()
                          if v[axis].get("quantiles", {}).get("q99") is not None)
                for axis in ("load", "depth")}
    union = floors["union_cross_class"]
    def verdict(d, floor):
        if d is None or floor is None:
            return "not separable"
        return "resolvable" if abs(d) > floor else "not resolvable"
    return {
        "this_firing_vs_R37_archived_law": {
            "delta_load": delta(p1.get("load"), r37["load"]),
            "delta_depth": delta(p1.get("depth"), r37["depth"]),
            "floor_q99": q99_this,
            "verdict_load": verdict(delta(p1.get("load"), r37["load"]),
                                    q99_this["load"]),
            "verdict_depth": verdict(delta(p1.get("depth"), r37["depth"]),
                                     q99_this["depth"]),
            "note": ("R37's archived law is the zero-trace deployment's billed length, "
                     "negative on both axes; a resolvable delta here is a statement about "
                     "the deployment's trace exposure, not about the model's capability")},
        "this_firing_vs_flash_class": {
            "delta_load": delta(p1.get("load"), r38p1["load"]),
            "delta_depth": delta(p1.get("depth"), r38p1["depth"]),
            "union_floor_q99": union,
            "verdict_load": verdict(delta(p1.get("load"), r38p1["load"]),
                                    union["load_q99"]),
            "verdict_depth": verdict(delta(p1.get("depth"), r38p1["depth"]),
                                     union["depth_q99"]),
            "note": ("round 38 found the load-axis class gap resolvable and the depth-axis "
                     "gap not, on its own floors; this re-judges both with a fresh firing "
                     "of this class and the flash class's own two-firing floor")},
    }


def class_identity(meas: dict) -> dict:
    """Billed-length closeness of all five archived panel firings, grouped by class."""
    tables = {label: archived_table(label)
              for label in ("R31", "R37", "R38P1")}
    p1_table = {d: meas[("P1", d)]["tok"]
                for d in {d for ds in PANEL_CELLS.values() for d in ds}
                if ("P1", d) in meas}
    tables["P1"] = p1_table
    labels = sorted(tables)
    pairs = []
    for i, la in enumerate(labels):
        for lb in labels[i + 1:]:
            shared = sorted(set(tables[la]) & set(tables[lb]))
            devs = [rel_dev(tables[la][d], tables[lb][d]) for d in shared]
            devs = [x for x in devs if x is not None]
            pairs.append({"a": la, "b": lb, "shared_prompts": len(shared),
                          "rel_dev_median": round(quantile(devs, 0.50), 4) if devs else None,
                          "rel_dev_max": round(max(devs), 4) if devs else None})
    return {"pairs": pairs,
            "note": ("billed completion tokens only; text-level identity is reported in "
                     "cross_class and cross_firing_same_class")}


def cell_table(records: list) -> dict:
    """Per-cell delivery and correctness with both Wilson denominators (inherited from
    round 38): an item counts as correct when every dispatch of it is correct; the item
    interval is the cell statement, the dispatch interval the measurement-precision
    statement about the two prompts."""
    out = {}
    for cell in WALK_INDEX:
        cell_recs = [r for r in records if r["cell"] == cell]
        items = collections.defaultdict(list)
        for r in cell_recs:
            items[(r["arm"], r["prompt_sha256"])].append(r)
        item_ok = 0
        disp_ok = 0
        disp_n = 0
        for (arm, digest), recs in sorted(items.items()):
            all_ok = all(r["correct"]["content_only"] == 1 for r in recs)
            item_ok += int(all_ok)
            for r in recs:
                disp_n += 1
                disp_ok += int(r["correct"]["content_only"] == 1)
        delivered_n = sum(1 for r in cell_recs if r["delivered"])
        out[cell] = {
            "items": len(items),
            "item_correct": item_ok,
            "item_accuracy": (item_ok / len(items) if items else None),
            "item_wilson": list(wilson(item_ok, len(items))) if items else [None, None],
            "dispatch_correct": disp_ok,
            "dispatch_n": disp_n,
            "dispatch_wilson": list(wilson(disp_ok, disp_n)) if disp_n else [None, None],
            "delivered": delivered_n,
            "delivery_wilson": list(wilson(delivered_n, disp_n)) if disp_n else [None, None],
        }
    return out


def score_predictions(gate: dict, meas: dict, within: dict, cells: dict,
                      cf: dict, cc: dict, enum: dict, census: dict, slopes: dict) -> dict:
    preds = gate["predictions"]
    p1 = {d: meas[("P1", d)] for d in
          {d for ds in PANEL_CELLS.values() for d in ds} if ("P1", d) in meas}
    r1 = sum(1 for m in p1.values() if m["reasoning_chars"] > 0)
    drs = [m["dr"] for m in p1.values() if m["dr"] is not None]
    anomalies = sum(v["billing_anomalies"] for v in census.values())
    tarr_cc = cc["agreement"]["tarr"]
    tara_cc = cc["agreement"]["tara"]
    t5 = sum(1 for p in cf["R37"]["per_prompt"]
             if 0.5 <= (p["tok_this"] / p["tok_archived"]) <= 2.0)
    same_mode = within["within_run_same_mode"]["pooled"]
    mode_change = within["within_run_mode_change"]["pooled"]
    n1_cell_min = min(v["tarr"] for v in cells["same_mode"].values() if v["tarr"] is not None)
    delivered = sum(1 for (p, _d), m in meas.items() if p in PASS_IDS and m["delivered"])
    correct = sum(1 for (p, _d), m in meas.items()
                  if p in PASS_IDS and m["correct"]["content_only"] == 1)
    ref = gate["panel_reference_slopes"][preds["N5_band_reference"]]
    return {
        "T1_channel": {"threshold": preds["T1_P1_dispatches_with_nonempty_reasoning_ge"],
                       "measured": r1, "pass": r1 >= preds["T1_P1_dispatches_with_nonempty_reasoning_ge"]},
        "T2_enumeration": {"threshold_positive": preds["T2_P1_dispatches_with_dr_positive_ge"],
                           "threshold_mean": preds["T2_P1_mean_dr_ge"],
                           "measured_positive": enum["n_positive"],
                           "measured_mean": enum["mean"],
                           "pass": (enum["n_positive"] >= preds["T2_P1_dispatches_with_dr_positive_ge"]
                                    and (enum["mean"] or 0) >= preds["T2_P1_mean_dr_ge"])},
        "T3_billing": {"threshold_max": preds["T3_billing_anomalies_max"],
                       "measured": anomalies,
                       "pass": anomalies <= preds["T3_billing_anomalies_max"]},
        "T4_cross_class": {"tarr_threshold_max": preds["T4_cross_class_full_text_identical_max"],
                           "tara_threshold": preds["T4_cross_class_answer_agreement_over_both_delivered_ge"],
                           "measured_tarr_hits": cc["agreement"]["tarr_hits"],
                           "measured_tarr_joinable": cc["agreement"]["joinable_pairs"],
                           "measured_tara": cc["agreement"]["tara"],
                           "measured_tara_hits": cc["agreement"]["tara_hits"],
                           "measured_tara_pairs": cc["agreement"]["tara_pairs_both_delivered"],
                           "pass": (cc["agreement"]["joinable_pairs"] == 0
                                    or cc["agreement"]["tarr_hits"]
                                    <= preds["T4_cross_class_full_text_identical_max"])
                                   and cc["agreement"]["tara"] is not None
                                   and cc["agreement"]["tara"]
                                   >= preds["T4_cross_class_answer_agreement_over_both_delivered_ge"]},
        "T5_r37_proximity": {"threshold": preds["T5_P1_prompts_within_factor2_of_R37_ge"],
                             "measured": t5,
                             "pass": t5 >= preds["T5_P1_prompts_within_factor2_of_R37_ge"]},
        "N1_determinism": {"threshold": preds["N1_within_run_same_mode_tarr_ge"],
                           "measured": same_mode["tarr"],
                           "per_cell_min": n1_cell_min,
                           "cell_threshold": preds["N1_within_run_same_mode_tarr_cell_ge"],
                           "pass": (same_mode["tarr"] is not None
                                    and same_mode["tarr"] >= preds["N1_within_run_same_mode_tarr_ge"]
                                    and n1_cell_min >= preds["N1_within_run_same_mode_tarr_cell_ge"])},
        "N2_mode_change": {"threshold": preds["N2_within_run_mode_change_tarr_ge"],
                           "measured_tarr": mode_change["tarr"],
                           "token_delta_max_threshold": preds["N2_within_run_mode_change_abs_token_change_le"],
                           "measured_max_abs_token_change": max(
                               (abs(meas[("P1", d)]["tok"] - meas[("P2", d)]["tok"])
                                for d in {d for ds in PANEL_CELLS.values() for d in ds}
                                if ("P2", d) in meas),
                               default=0),
                           "pass": (mode_change["tarr"] is not None
                                    and mode_change["tarr"]
                                    >= preds["N2_within_run_mode_change_tarr_ge"]
                                    and max((abs(meas[("P1", d)]["tok"]
                                                 - meas[("P2", d)]["tok"])
                                             for d in {d for ds in PANEL_CELLS.values()
                                                        for d in ds}
                                             if ("P2", d) in meas),
                                            default=0)
                                    <= preds["N2_within_run_mode_change_abs_token_change_le"])},
        "N3_answers": {"threshold": preds["N3_tara_every_stratum_ge"],
                       "measured": [within[s]["pooled"]["tara"]
                                    for s in ("within_run_same_mode",
                                              "within_run_mode_change")],
                       "pass": all(within[s]["pooled"]["tara"] is not None
                                   and within[s]["pooled"]["tara"]
                                   >= preds["N3_tara_every_stratum_ge"]
                                   for s in ("within_run_same_mode",
                                             "within_run_mode_change"))},
        "N4_delivery": {"threshold_delivered": preds["N4_all_dispatches_deliver_content_answer"],
                        "threshold_correct": preds["N4_all_dispatches_correct_content_only"],
                        "measured_delivered": delivered, "measured_correct": correct,
                        "pass": (delivered >= preds["N4_all_dispatches_deliver_content_answer"]
                                 and correct >= preds["N4_all_dispatches_correct_content_only"])},
        "N5_cost_band": {"reference": preds["N5_band_reference"],
                         "band_load": preds["N5_pass_panel_load_slope_in_band"],
                         "band_depth": preds["N5_pass_panel_depth_slope_in_band"],
                         "measured": slopes.get("P1"),
                         "pass": (in_band(slopes.get("P1", {}).get("load"),
                                          ref["load"], N5_COST_BAND)
                                  and in_band(slopes.get("P1", {}).get("depth"),
                                              ref["depth"], N5_COST_BAND))},
    }


def aggregate(records: list, gate: dict, health: dict = None) -> dict:
    meas = measurements(records)
    within = within_run(meas)
    cells = {"same_mode": per_cell_same_mode(meas), "accuracy": cell_table(records)}
    census = billing_census(records)
    cf = cross_firing_same_class(meas)
    cc = cross_class(meas)
    enum = enumeration_table(meas)
    slopes = {pid: firing_slopes({d: meas[(pid, d)]["tok"] for d in
                                  {d for ds in PANEL_CELLS.values() for d in ds}
                                  if (pid, d) in meas})
              for pid in PASS_IDS}
    floors = floor_bundle(meas)
    identity = class_identity(meas)
    resolv = slope_resolvability(slopes, floors, gate)
    preds = score_predictions(gate, meas, within, cells, cf, cc, enum, census, slopes)
    pass_stats = []
    for pid in PASS_IDS:
        recs = [r for r in records if r["pass_id"] == pid]
        starts = [a["started_at"] for r in recs for a in r["attempts"] if a.get("started_at")]
        ends = [a["finished_at"] for r in recs for a in r["attempts"] if a.get("finished_at")]
        pass_stats.append({
            "pass_id": pid, "items": len(recs),
            "completion_tokens": sum(r["completion_tokens"] for r in recs),
            "prompt_tokens": sum(r["prompt_tokens"] for r in recs),
            "retries": sum(1 for r in recs if r["retried"]),
            "truncations": sum(1 for r in recs if r["truncated"]),
            "delivered": sum(1 for r in recs if r["delivered"]),
            "started_at": min(starts) if starts else None,
            "finished_at": max(ends) if ends else None})
    return {
        "schema": "round40-summary-v1",
        "round": gate["round"],
        "gate_hash": GATE_HASH,
        "class_label": gate["class_label"],
        "generated_at": now_iso(),
        "transport": {"endpoint": "pool endpoint, value never written (public-only rule)",
                      "max_tokens": MAX_TOKENS, "temperature": TEMPERATURE,
                      "calls": HEALTH_CALLS + len(records), "cap": PROMPT_CAP,
                      "passes": pass_stats, "health": health},
        "predictions": preds,
        "trace_census": census,
        "within_run": within,
        "per_cell_same_mode": cells["same_mode"],
        "cell_accuracy": cells["accuracy"],
        "cross_firing_same_class": cf,
        "cross_class": cc,
        "enumeration": enum,
        "slopes": slopes,
        "panel_reference_slopes": gate["panel_reference_slopes"],
        "published_full_design_slopes": gate["published_full_design_slopes"],
        "floors": floors,
        "slope_resolvability": resolv,
        "class_identity": identity,
        "state": ("Executed (one endpoint, no independent second implementation, and the "
                  "pre-registered decision table does not cover this design; the selftest "
                  "certifies the instrument's controls, the digest-true replay of the pinned "
                  "panel, the hash-pinned transcriptions and the deterministic verification "
                  "of round 37's collapsed hashes)"),
    }


def cmd_gate(out_path: str) -> int:
    gate = build_gate()
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(gate, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"gate {gate_hash(gate)[:8]}: anchor_ok={gate['anchor_ok']} "
          f"all_cells_pass={gate['all_cells_pass']} "
          f"planned_prompts={gate['planned_prompts']}")
    return 0


def cmd_analyze(out_dir: str) -> int:
    gate_path = os.path.join(out_dir, "gate.json")
    raw_path = os.path.join(out_dir, "raw.jsonl")
    with open(gate_path, encoding="utf-8") as fh:
        gate = json.load(fh)
    global GATE_HASH
    GATE_HASH = gate_hash(gate)
    records = []
    if os.path.exists(raw_path):
        with open(raw_path, encoding="utf-8") as fh:
            for line in fh:
                rec = json.loads(line)
                if rec.get("gate_hash") != GATE_HASH:
                    raise SystemExit("raw.jsonl carries a different gate hash")
                records.append(rec)
    if len(records) != len(PANEL_DIGESTS) * len(PASS_PLAN):
        raise SystemExit(f"expected {len(PANEL_DIGESTS) * len(PASS_PLAN)} records, "
                         f"found {len(records)}")
    health = None
    health_path = os.path.join(out_dir, "health.json")
    if os.path.exists(health_path):
        with open(health_path, encoding="utf-8") as fh:
            health = json.load(fh)
    summary = aggregate(records, gate, health)
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"summary.json written: {len(records)} records, gate {GATE_HASH[:8]}")
    return 0


# ---------------------------------------------------------------------------
# Selftest: arithmetic, planted negative controls, digest-true replay of the pinned
# panel, hash-pinned transcriptions, and the deterministic verification of round 37's
# collapsed hashes. No endpoint, no network.
# ---------------------------------------------------------------------------

def selftest() -> int:
    failures: list = []
    count = 0

    def ck(name: str, cond: bool) -> None:
        nonlocal count
        count += 1
        if not cond:
            failures.append(name)

    # --- arithmetic ------------------------------------------------------
    ck("wilson(0,0)", wilson(0, 0) == (0.0, 0.0))
    lo, hi = wilson(1, 2)
    ck("wilson(1,2) lower", abs(lo - 0.0945) < 1e-4)
    ck("wilson(1,2) upper", abs(hi - 0.9055) < 1e-4)
    ck("wilson monotone", wilson(11, 12)[0] > wilson(1, 2)[0])
    ck("ols exact line", ols([(0, 0), (1, 2), (2, 4)])["slope"] == 2.0)
    ck("ols r exact line", ols([(0, 0), (1, 2), (2, 4)])["r"] == 1.0)
    ck("ols single point", ols([(1, 1)])["slope"] is None)
    ck("quantile even", quantile([1, 2, 3, 4], 0.5) == 2.5)
    ck("quantile high", quantile([1, 2, 3, 4, 5], 0.9) == 4.6)
    ck("quantile single", quantile([7], 0.99) == 7)
    ck("quantile empty", quantile([], 0.5) is None)
    ck("mcnemar none", mcnemar_exact(0, 0) == 1.0)
    ck("mcnemar lopsided", mcnemar_exact(3, 0) == 0.25)
    ck("ols panel shape", abs(ols([(96, 100), (112, 110), (128, 120), (160, 130)])["slope"]
                                - (130 - 100) / (160 - 96)) < 0.5)

    # --- hash conventions and the R37 collapse ---------------------------
    ck("output_sha convention",
       output_sha("yes", "abc") == sha256_text("yes\x00abc"))
    ck("output_sha empty", output_sha("", "") == sha256_text("\x00"))
    ck("r37 collapse yes", output_sha("\n\nyes", "") == R37_COLLAPSE["yes"])
    ck("r37 collapse no", output_sha("\n\nno", "") == R37_COLLAPSE["no"])
    ck("r37 surface counts", sum(R37_CONTENT_SURFACE.values()) == 36)
    ck("r37 surface words", sorted(R37_CONTENT_SURFACE) == ["no", "yes"])
    # The collapse is content-only: any non-empty reasoning would change the hash.
    ck("r37 collapse not stable under reasoning",
       output_sha("\n\nyes", "x") != R37_COLLAPSE["yes"])

    # --- transcription integrity -----------------------------------------
    ck("r38p1 has 12 records", len(R38P1_PANEL) == 12)
    ok = True
    for d, v in R38P1_PANEL.items():
        if output_sha(v["content"], v["reasoning"]) != v["out_sha"]:
            ok = False
    ck("r38p1 hashes recompute", ok)
    ck("r38p1 arms consistent",
       all(v["arm"] in ("F", "X") for v in R38P1_PANEL.values()))
    ck("r38p1 flash side has text",
       all(len(v["reasoning"]) > 0 for v in R38P1_PANEL.values()))
    l3x = R38P1_PANEL["d548b1f9681cf082174cf141f33e0f34a65b98cf2504111e36284bdf287386cc"]
    ck("r38p1 single undelivered is the L3-X truncation",
       sum(1 for v in R38P1_PANEL.values() if v["ans"] is None) == 1
       and l3x["ans"] is None and l3x["fin"] == "length")
    ck("r31 has 12 records", len(R31_PANEL) == 12)
    ck("r31 non-joinable on text",
       all("out_sha" not in v for v in R31_PANEL.values()))
    ck("r37 has 12 records", len(R37_PANEL) == 12)
    ck("r37 hashes are the collapsed pair",
       {v["out_sha"] for v in R37_PANEL.values()} == set(R37_COLLAPSE.values()))
    ck("r33 has 12 records", len(R33_PANEL) == 12)
    ck("panel archives cover the panel",
       all(set(a) == {d for ds in PANEL_CELLS.values() for d in ds}
           for a in PANEL_ARCHIVE.values()))

    # --- construction: digest-true replay of the pinned panel ------------
    cells = all_cells()
    ck("six cells built", [c["cell"] for c in cells] == list(WALK_INDEX))
    pin_ok = True
    for cell in cells:
        exp = R24_DIGESTS[cell["cell"]]
        if sha256_text(canonical(cell["pool"])) != exp["pool_blob_sha256"]:
            pin_ok = False
        if sorted([sha256_text(render_prompt(p[0])) for p in cell["pairs"]]
                  + [sha256_text(render_prompt(p[1])) for p in cell["pairs"]]) \
                != sorted(exp["forward_prompt_sha256"] + exp["cross_prompt_sha256"]):
            pin_ok = False
    ck("r24 structural pin holds", pin_ok)
    units = panel_units()
    ck("panel is 12", len(units) == 12)
    ck("panel digests match the pin",
       sorted((u["cell"], u["digest"]) for u in units) == sorted(PANEL_DIGESTS))
    pair_ok = True
    leak_ok = True
    for cell in cells:
        if gate_battery(cell["pool"])["verdict"] == "leak" \
                or gate_battery(cell["paired_pool"])["verdict"] == "leak":
            leak_ok = False
    for cell in cells:
        f_item, x_item = cell["pairs"][PANEL_PAIR_INDEX]
        if pair_violations(f_item, x_item):
            pair_ok = False
        if verify_item(f_item) or verify_item(x_item):
            pair_ok = False
    ck("leak audit passes all cells", leak_ok)
    ck("78 shared-content invariant on panel pairs", pair_ok)

    # --- transcribed tok tables reproduce round 38's gate slopes ----------
    r37 = firing_slopes(archived_table("R37"))
    ck("r37 load slope matches r38 gate", r37["load"] == -5.7857)
    ck("r37 depth slope matches r38 gate", r37["depth"] == -26.25)
    r31 = firing_slopes(archived_table("R31"))
    ck("r31 load slope matches r38 gate", r31["load"] == -2.7089)
    ck("r31 depth slope matches r38 gate", r31["depth"] == 68.625)
    r33 = firing_slopes(archived_table("R33"))
    ck("r33 load slope matches r38 gate", r33["load"] == 10.942)
    ck("r33 depth slope matches r38 gate", r33["depth"] == 25.75)

    # --- readout stack controls ------------------------------------------
    ck("last_answer basic", last_answer("chain. yes") == ("yes", 7))
    ck("last_answer last wins", last_answer("no yes or no")[0] == "no")
    ck("last_answer none", last_answer("nothing here")[0] is None)
    ck("strict trace cued",
       strict_last_trace_token("We check the chain. therefore no.") == "no")
    ck("strict trace closes",
       strict_last_trace_token("The answer is yes or no: pick one. no") == "no")
    ck("strict trace last qualified",
       strict_last_trace_token("no yes") == "yes")
    ck("strict trace none",
       strict_last_trace_token("the graph has two paths") is None)
    ck("provenance terminal",
       provenance_class("x" * 196 + " no")[0] == "terminal")
    ck("provenance instruction_echo",
       provenance_class("answer yes or no")[0] == "instruction_echo")
    ck("provenance mid_trace",
       provenance_class("mid no here and lots of padding padding padding")[0]
       == "mid_trace")
    ck("provenance none", provenance_class("verdict words at all here")[0] is None)
    ro = readouts("yes", "")
    ck("readouts content path",
       ro["content_answer"] == "yes" and ro["loose_fallback_source"] == "content"
       and ro["strict_trace_token"] is None
       and ro["fallback_provenance_class"] is None)
    ro2 = readouts("", "we walk the chain. therefore no")
    ck("readouts trace fallback",
       ro2["content_answer"] is None and ro2["loose_fallback_answer"] == "no"
       and ro2["loose_fallback_source"] == "reasoning"
       and ro2["delivered_or_strict_answer"] == "no")
    ck("classify answered",
       classify_attempt({"content_answer": "yes", "reasoning_answer": None,
                         "completion_tokens": 5, "error_class": None,
                         "finish_reason": "stop"}) == "answered_in_answer_field")
    ck("classify trace_only",
       classify_attempt({"content_answer": None, "reasoning_answer": "no",
                         "completion_tokens": 5, "error_class": None,
                         "finish_reason": "stop"}) == "trace_only")
    ck("classify truncated",
       classify_attempt({"content_answer": None, "reasoning_answer": None,
                         "completion_tokens": 2048, "error_class": None,
                         "finish_reason": "length"}) == "truncated_no_answer")
    ck("classify transport",
       classify_attempt({"content_answer": None, "reasoning_answer": None,
                         "completion_tokens": 0, "error_class": "http_502",
                         "finish_reason": None}) == "transport_http_502")
    ck("classify empty",
       classify_attempt({"content_answer": None, "reasoning_answer": None,
                         "completion_tokens": 0, "error_class": None,
                         "finish_reason": "stop"}) == "empty_completion")
    ck("retryable transport", is_retryable("transport_http_502"))
    ck("not retryable trace_only", not is_retryable("trace_only"))

    # --- mechanics: the enumeration quantity on a real panel item ---------
    f_item, x_item = build_cell(8, 12, 1)[0][PANEL_PAIR_INDEX]
    dis = distractor_names(f_item)
    ck("distractors count", len(dis) == (12 - 1) * (8 + 1))
    mech_all = mechanics(f_item, {"completion_tokens": 10, "reasoning": " ".join(dis),
                                  "content": "yes"}, "p")
    ck("distractor ratio all mentioned", mech_all["distractor_mention_ratio"] == 1.0)
    mech_none = mechanics(f_item, {"completion_tokens": 1, "reasoning": "",
                                   "content": "yes"}, "p")
    ck("distractor ratio structural zero",
       mech_none["distractor_mention_ratio"] == 0.0)
    seq = expected_chain(f_item)
    ck("expected chain length", len(seq) == 9)
    mech_chain = mechanics(f_item, {"completion_tokens": 10,
                                    "reasoning": " | ".join(seq), "content": "yes"}, "p")
    ck("ordered prefix full coverage",
       mech_chain["ordered_prefix_hops"] == 9 and mech_chain["coverage_ratio"] == 1.0)
    ck("no item has no expected chain", expected_chain(x_item) is None)

    # --- sanitizer --------------------------------------------------------
    ck("sanitize url", "https" not in sanitize("see https://example.com/x now"))
    ck("sanitize ip", "10.0.0.1" not in sanitize("host 10.0.0.1 here"))
    ck("sanitize path", "/a/b/c" not in sanitize("path /a/b/c here"))
    ck("sanitize passthrough", sanitize("yes or no") == "yes or no")
    ck("sanitize redaction marker", "[REDACTED]" in sanitize("see https://example.com/x"))

    # --- merge rule and budget --------------------------------------------
    ck("merge prefers reasoning_content",
       reasoning_merge("abc", "xyz") == ("abc", "reasoning_content"))
    ck("merge falls back to reasoning",
       reasoning_merge("", "xyz") == ("xyz", "reasoning"))
    ck("merge none", reasoning_merge("", "") == ("", "none"))
    budget = AttemptBudget(2)
    ck("budget first", budget.acquire())
    ck("budget second", budget.acquire())
    ck("budget cap", not budget.acquire())

    # --- determinism of the construction ----------------------------------
    ck("gen_item deterministic",
       gen_item(8, 12, cell_seed(8, 12, 0)) == gen_item(8, 12, cell_seed(8, 12, 0)))
    ck("x_variant deterministic", x_variant(f_item) == x_variant(f_item))
    ck("pair invariant clean", pair_violations(f_item, x_variant(f_item)) == [])

    # --- stratum agreement on planted rows --------------------------------
    def row(i, sha_a="s0", sha_b="s0", ans_a="yes", ans_b="yes", tok=1000):
        return (f"d{i}",
                {"tok": tok, "ans": ans_a, "sha": sha_a, "delivered": True,
                 "reasoning_chars": 100, "dr": 1.0, "content_chars": 3, "cell": "L0"},
                {"tok": tok, "ans": ans_b, "sha": sha_b, "delivered": True,
                 "reasoning_chars": 100, "dr": 1.0, "content_chars": 3, "cell": "L0"})
    rows = [row(i) for i in range(12)]
    rows[5] = row(5, sha_b="sX")
    agg = stratum_agreement(rows)
    ck("planted tarr 11 of 12", agg["tarr"] == round(11 / 12, 4)
       and agg["tarr_hits"] == 11 and agg["joinable_pairs"] == 12)
    rows2 = [row(i) for i in range(12)]
    rows2[5] = row(5, sha_b="sX")
    rows2[0] = row(0, ans_b="no")
    agg2 = stratum_agreement(rows2)
    ck("planted tara 11 of 12", agg2["tara"] == round(11 / 12, 4)
       and agg2["tara_hits"] == 11
       and agg2["tara_pairs_both_delivered"] == 12)
    rows3 = [row(i) for i in range(11)]
    rows3.append(("d11",
                  {"tok": 1000, "ans": "yes", "sha": "s0", "delivered": True,
                   "reasoning_chars": 100, "dr": 1.0, "content_chars": 3, "cell": "L0"},
                  {"tok": 1913, "ans": "yes", "sha": "s0", "delivered": True,
                   "reasoning_chars": 100, "dr": 1.0, "content_chars": 3, "cell": "L0"}))
    agg3 = stratum_agreement(rows3)
    ck("material move flagged", agg3["material_moves"] == 1
       and agg3["rel_dev_max"] > MATERIAL_REL_DEV)
    rows4 = [row(i, sha_a=None, ans_a=None) for i in range(12)]
    agg4 = stratum_agreement(rows4)
    ck("non-joinable counted as such", agg4["joinable_pairs"] == 0
       and agg4["tarr"] is None)

    # --- billing census flag on planted records ----------------------------
    def mk_rec(pass_id, tok, rc, cc):
        mech = {"reasoning_chars": rc, "content_chars": cc,
                "distractor_mention_ratio": None, "completion_tokens": tok,
                "budget_utilisation": 0.0, "ordered_prefix_hops": None,
                "expected_hops": None, "coverage_ratio": None,
                "distractor_entities": 0, "distractors_mentioned": 0,
                "src_first_mention_frac": 0.0, "tgt_first_mention_frac": 0.0}
        return {"pass_id": pass_id, "cell": "L0", "arm": "F",
                "prompt_sha256": f"digest-{pass_id}",
                "attempts": [{"completion_tokens": tok, "mechanics": mech,
                              "reasoning_field": "reasoning_content",
                              "message_fields": ["content", "role"]}],
                "content_answer": "yes"}
    census = billing_census([mk_rec("P1", 10, 90, 0), mk_rec("P1", 100, 100, 0)])
    ck("billing anomaly planted", census["P1"]["billing_anomalies"] == 1)
    ck("billing census fields",
       census["P1"]["reasoning_field_census"].get("reasoning_content") == 2
       and census["P1"]["message_field_names_union"] == ["content", "role"])

    # --- bands and floors ----------------------------------------------------
    ck("band positive", band_for(10.8545, (0.5, 2.0)) == [5.4272, 21.709])
    ck("band negative", band_for(-5.0, (0.5, 2.0)) == [-10.0, -2.5])
    ck("in_band true", in_band(10.0, 10.8545, (0.5, 2.0)))
    ck("in_band false", not in_band(40.0, 10.8545, (0.5, 2.0)))
    ck("in_band negative reference", in_band(-5.5, -5.0, (0.5, 2.0))
       and not in_band(-1.5, -5.0, (0.5, 2.0)))
    base = {d: 1000 for d in {d for ds in PANEL_CELLS.values() for d in ds}}
    pool = [5, -7, 12, -3, 8, -9, 6, 4, -6, 10, -2, 7]
    fl1 = slope_noise_floor(base, pool, "load")
    fl2 = slope_noise_floor(base, pool, "load")
    ck("floor deterministic", fl1 == fl2)
    ck("floor has quantiles",
       all(k in fl1["quantiles"] for k in ("q50", "q95", "q99")))
    ck("floor observed pairs", fl1["observed_pairs"] == 12)

    if failures:
        print(f"SELFTEST FAILED: {len(failures)} of {count}:")
        for name in failures:
            print(f"  - {name}")
        return 1
    print(f"selftest: {count} checks passed")
    return 0


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(
        description="round 40 panel trace-channel probe (see module docstring)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--selftest", action="store_true",
                      help="run the offline control battery, no endpoint")
    mode.add_argument("--gate", action="store_true",
                      help="build gate.json before any prompt is spent")
    mode.add_argument("--probe", action="store_true",
                      help="health check plus the 36 panel dispatches")
    mode.add_argument("--analyze", action="store_true",
                      help="rebuild summary.json from gate.json and raw.jsonl")
    ap.add_argument("--out", default="gate.json", help="gate output path")
    ap.add_argument("--out-dir", default=".", help="round directory")
    ap.add_argument("--resume", action="store_true",
                    help="skip (prompt, pass) pairs already archived in raw.jsonl")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.gate:
        return cmd_gate(args.out)
    if args.probe:
        return probe(args.out_dir, args.resume)
    return cmd_analyze(args.out_dir)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

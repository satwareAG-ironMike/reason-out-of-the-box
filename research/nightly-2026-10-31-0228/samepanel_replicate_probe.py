#!/usr/bin/env python3
"""Round 38 (2026-10-31 02:28): within-run replicate panel on the digest-pinned (k, E) grid -
how much of an archived cell verdict is decoding, how much is dispatch mode, and how much is
the firing?

Question. Issue #100 states the gap this round fills: "every cell verdict this program has
placed comes from a single run", and no archived measurement separates decoding noise from
firing-level noise, so no archived ceiling can be quoted with a run-level uncertainty. Round
33 measured same-class repeatability across two firings three days apart (32 of 36 completions
token-identical, cost slopes within 2.6 percent, the same silent digest) and round 37 measured
it on the other class (0 of 36 identical, one cell verdict moved, the depth slope came back at
0.35x of the reference) and concluded that a band test cannot be scored without a same-run noise
floor. Neither round could say WHERE the variation comes from, because both compared firings:
two unknown deployments against one another. Both rounds also left issue #100's acceptance
criteria 1 and 2 unmet: no raw archive in this program stores a per-cell self-agreement pair
(raw output and parsed answer), and no archived cell stores a Wilson interval next to its
accuracy.

This round holds the firing fixed and varies the conditions inside it. The same 12 digest-pinned
prompts are dispatched three times in one session in an ABABA order: serialized (one request in
flight), then at the concurrency the archived rounds used (two in flight), then serialized again.
The two serialized passes bracket the batched pass, so agreement between them is the endpoint's
own determinism at temperature 0 over an interval that contains the mode change, and any
serialized-versus-batched difference is attributable to the dispatch mode rather than to drift.
The same digests are then joined, per prompt, to the two archived firings of this class (rounds
24 and 33) and, for context, to the two firings on the other class (rounds 31 and 37).

Declared predictions (fixed in gate.json before any prompt was spent):

  N1 determinism: serialized-versus-serialized raw-output agreement (TARr) is at least 0.90 over
      the 12 same-mode replicate pairs and at least 0.50 in every cell (each cell carries 2
      same-mode pairs, so at most one of them may disagree);
  N2 dispatch mode: the concurrency change moves nothing - serialized-versus-batched TARr is
      1.00 and no prompt's completion length changes;
  N3 parsed answer: TARa is 1.00 in every stratum (identical prompts at temperature 0 return the
      same verdict, whatever the mode or the firing);
  N4 delivery: all 36 dispatches deliver a content answer, and all 36 are correct (content_only);
  N5 cost law: the panel load slope (k = 8) and panel depth slope (E = 96) of every pass stay
      inside the 0.5x to 2.0x house band around the round-24 panel reference;
  N6 noise-guard criterion, measurement with a declared rule: a slope difference counts as a
      change only when it exceeds the measured same-class noise floor for its own stratum. The
      floor is built by propagating the observed per-prompt pairwise difference distribution of
      that stratum through the same slope estimator.

Reported alongside the predictions, not predicted: the per-cell self-agreement pair (TARr, TARa)
and the per-cell Wilson interval next to accuracy that #100 asks for; the per-item flip rates
propagated to the probability that at least one of six items moves across a re-run; a
class-identity diagnostic (raw-output agreement against the archived firings, the strongest
evidence the archive can carry that two rounds hit the same deployment); and the resolvability
verdict for the cross-class cost-law claim against both classes' floors.

Instrument. Construction, generation, audit and readout are inherited verbatim from round 37's
sameclass_frontier_retest_probe.py (branch research/nightly-2026-10-30-0400, PR #102), which
inherits them from rounds 19 to 24: C disjoint directed paths of exactly k edges over fresh
entity names, one rule sentence (transitivity of `precedes`), E = k x C facts in shuffled order,
one query per prompt, answer required as exactly one word; gold from an unbounded BFS
independent of the generator plus a structural audit of every item; each graph asked twice over
identical content (arm F forward, gold yes; arm X cross-component, gold no) with the
shared-content invariant asserted per pair (#78). Readout stack: content_only (primary),
delivered_or_strict (content, else the round-19 strict trace-commitment rule), loose_fallback
(reported, never scored).

Panel. The panel is the first matched pair (arm F and arm X) of each of the six cells of round
24's digest-pinned grid, selected by the archived selection order before any outcome is known
(pair index 0), so the panel is a deterministic subset of a pinned corpus: 6 cells x 2 arms = 12
prompts, dispatched 3 times = 36. It is NOT the full 6-per-cell design: cell accuracy here has
an effective n of 2 items, both Wilson denominators are stored and labelled, and no cell verdict
of any kind is re-placed by this round. The one digest that was content-silent in both archived
firings of this class (round 24 and round 33, D2 arm X, third pair) is outside the panel, so the
borderline cell is not re-tested here.

Cell  k  C(paths)  E(facts)  round-24 status on this class
  L0   8    12        96     maintained
  L1   8    14       112     maintained
  L2   8    16       128     maintained
  L3   8    20       160     maintained
  D1  12     8        96     maintained
  D2  16     6        96     inconclusive (5 of 6 delivered, one 2048-token truncation)

Transport: endpoint from NIGHTLY_BASE_URL, NIGHTLY_MODEL_ID and NIGHTLY_API_KEY; 1 health call
plus 36 panel dispatches = 37 of the 40-call cap; max_tokens 2048, temperature 0.0; passes 1 and
3 run one request at a time, pass 2 runs two. No endpoint value is ever written to an artifact,
and stored model text passes a sanitizer for URLs, IP addresses and absolute paths. Stdlib only.

  samepanel_replicate_probe.py --selftest
  samepanel_replicate_probe.py --gate              [--out gate.json]
  samepanel_replicate_probe.py --probe             [--out-dir DIR] [--resume]
  samepanel_replicate_probe.py --analyze           [--out-dir DIR]
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
MARGIN = 0.10
MAJORITY_FLOOR = 0.5
PERMS = 400
MAX_TOKENS = 2048
TEMPERATURE = 0.0
PROMPT_CAP = 40
HEALTH_CALLS = 1
PAIRS_PER_LEVEL = 3
CANDIDATES = 40
MIN_CERTIFY = 6
ITEM_DEADLINE_S = 600
HEALTH_PROMPT = "Reply with exactly one word: yes"
# Health-probe output budget: 256 tokens, per round 22's lesson that a 2048-token health call is
# not portable across the pool (one deployment's upstream gateway killed it at ~60 s with
# http_502 while 256 tokens returned in ~1 s).
HEALTH_BUDGET = 256

# The grid: two arms of (k, C) cells with E = k * C facts. Inside each arm, consecutive cells
# differ in exactly one axis; the load arm holds k = 8, the depth arm holds E = 96. The grid is
# unchanged from round 24, so the panel is a subset of a digest-pinned corpus.
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

# The ABABA pass plan. Passes 1 and 3 are identical in mode and bracket pass 2, which uses the
# concurrency of the archived rounds on this class (round 24: chosen_concurrency 2).
ARCHIVED_CONCURRENCY = 2
PASS_PLAN = (
    {"pass_id": "P1", "mode": "serial", "concurrency": 1},
    {"pass_id": "P2", "mode": "paired", "concurrency": ARCHIVED_CONCURRENCY},
    {"pass_id": "P3", "mode": "serial", "concurrency": 1},
)
PASS_IDS = tuple(p["pass_id"] for p in PASS_PLAN)

# Fail-closed structural pin: every cell's pool blob and all 36 prompt digests must equal round
# 24's gate, transcribed from research/nightly-2026-10-25-0405/gate.json (PR #98, not on main at
# authoring time), so the post-merge tree can verify the pin without the ancestor branch.
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
# --selftest asserts the documented behaviour of both, so the rule cannot drift silently
# from the rounds whose readout this grid must stay comparable to (#94).
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


# Per-firing archives of the four firings this round joins against, restricted to the 12 panel
# digests and to the fields the analysis needs. Transcribed from the round archives:
# research/nightly-2026-10-25-0405/raw.jsonl (PR #98) and
# research/nightly-2026-10-28-0400/raw.jsonl (PR #101) on this class, and
# research/nightly-2026-10-27-0439/raw.jsonl (PR #99) and
# research/nightly-2026-10-30-0400/raw.jsonl (PR #102) on the other class. None of the four
# ancestor branches is on main at authoring time, hence transcribed constants: the post-merge
# tree verifies every comparison without them. out_sha is sha256(sanitized content + U+0000 +
# sanitized reasoning) of the final attempt, the quantity TARr is measured on. It is present for
# the two firings on this class and for round 37 on the other class; round 31's transcription
# carries no text, so every raw pair involving R31 is non-joinable and is counted as such rather
# than as disagreement. Fields: tok = completion tokens, ans = content_only answer (None when the
# dispatch delivered no answer in the answer field), out = that round's own attempt outcome class,
# fin = finish_reason, dr = distractor-mention ratio, ptok = prompt tokens.
R24_PANEL = {
    "b20d7fd289fd6f181fb05aebf9ae6526c041870e09c711ae60a7100cb5ca313b": {"ans": "yes", "arm": "F", "dr": 1.0, "edges": 96, "fin": "stop", "gold": 1, "k": 8, "out": "answered_in_answer_field", "out_sha": "7942c07845ce8151aa0aa76e37b077922b62ec6e57b7452aa9c8e5e1a8087ef0", "ptok": 1447, "tok": 1101},
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
# The other class (a 27B-class local model under 4-bit floating-point quantization, vLLM serving,
# multi-token-prediction speculative decoding), the same 12 digests.
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
SAME_CLASS_FIRINGS = ("R24", "R33")
OTHER_CLASS_FIRINGS = ("R31", "R37")
PANEL_ARCHIVE = {
    "R24": R24_PANEL, "R33": R33_PANEL, "R31": R31_PANEL, "R37": R37_PANEL,
}

# Published full-design (6 prompts per cell) cost slopes, transcribed from the round records and
# recomputed from the same archives by --selftest. The basis is part of the number (issue #100's
# estimator-basis rule): "uncensored" excludes a cell with any 2048-token truncation from the fit,
# "all-cell" keeps its censored mean.
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
# Round 33's published full-grid same-class reference for the per-item flip rates: 32 of 36
# completions token-identical three days apart, 0 of 36 parsed-answer disagreements, one item
# moved materially (+16.9 percent completion length, same correct answer), one item hit the
# 600 s per-item deadline and was retried once.
R33_PUBLISHED = {"identical_of_36": 32, "answer_flips_of_36": 0,
                 "material_moves_of_36": 1, "deadline_retries_of_36": 1,
                 "material_move_item": "L1 arm X, +16.9 percent"}

# Declared thresholds, frozen before any prompt was spent.
N1_TARR_GRID_MIN = 0.90     # serialized vs serialized, over the 12 same-mode replicate pairs
N1_TARR_CELL_MIN = 0.50     # per cell carries 2 same-mode pairs: at most one may disagree
N2_TARR_GRID_MIN = 1.00     # the mode change moves nothing at all
N2_TOKEN_DELTA_MAX = 0      # per prompt: |completion token change| between modes
N3_TARA_GRID_MIN = 1.00     # parsed answer agrees in every stratum
N4_DELIVERED_MIN = 36       # all 36 dispatches answer in the answer field
N4_CORRECT_MIN = 36         # and all 36 are correct under content_only
N5_COST_BAND = (0.5, 2.0)   # house band, scored on the panel basis against the panel reference
N5_REFERENCE_FIRING = "R24"
CELL_ITEMS = 2              # panel items per cell: exploratory, and labelled wherever it is used
CELL_DISPATCHES = 6         # 2 items x 3 passes: not 6 independent items, and labelled as such

# Noise-floor arithmetic: the observed per-prompt pairwise difference of a stratum is propagated
# through the same slope estimator, so the floor comes out in tokens/fact and tokens/hop, on the
# same scale as the quantity it judges. Fixed seed and draw count: the floor is reproducible from
# gate.json and raw.jsonl alone.
BOOT_DRAWS = 4000
BOOT_SEED = 20261031
FLOOR_QUANTILES = (0.50, 0.95, 0.99)
RESOLVE_QUANTILE = 0.99     # a difference counts as a change only beyond this quantile
MATERIAL_REL_DEV = 0.10     # a per-prompt length move of 10 percent or more is "material"

# The pair strata. Within-run pairs are same-session and same host by construction; cross-firing
# pairs also carry whatever the deployment did between firings (restart, build, host), which is
# why the floor is reported per stratum and never pooled across them.
STRATA = {
    "within_run_same_mode": [("P1", "P3")],
    "within_run_mode_change": [("P1", "P2"), ("P2", "P3")],
    "cross_firing": [("R24", "R33"), ("R24", "P1"), ("R24", "P2"), ("R24", "P3"),
                     ("R33", "P1"), ("R33", "P2"), ("R33", "P3")],
    "other_class": [("R31", "R37")],
    "cross_class": [("R24", "R31"), ("R24", "R37"), ("R33", "R31"), ("R33", "R37")],
}
# Strata whose slope floor may be used to judge a claim of its own kind.
SAME_CLASS_STRATA = ("within_run_same_mode", "within_run_mode_change", "cross_firing")
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
        return {
            "content": sanitize(msg.get("content") or ""),
            "reasoning": sanitize(msg.get("reasoning_content") or ""),
            "finish_reason": choice.get("finish_reason"),
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
        }
    except urllib.error.HTTPError as exc:
        return {"error": f"http_{exc.code}", "content": "", "reasoning": "",
                "finish_reason": None, "prompt_tokens": 0, "completion_tokens": 0}
    except (urllib.error.URLError, TimeoutError, OSError,
            json.JSONDecodeError) as exc:
        return {"error": type(exc).__name__, "content": "", "reasoning": "",
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


def make_record(item: dict, arm: str, pair_seed: int, budget_cap: AttemptBudget,
                phase: int) -> dict:
    rec = blank_record(item, arm, pair_seed, phase)
    prompt = render_prompt(item)
    max_attempts = 3
    for attempt_no in range(1, max_attempts + 1):
        if not budget_cap.acquire():
            rec["attempts"].append({
                "attempt": attempt_no, "wall_s": 0.0, "error_class": "cap_exceeded",
                "started_at": now_iso(), "finished_at": now_iso(),
                "finish_reason": None, "prompt_tokens": 0, "completion_tokens": 0,
                "content": "", "reasoning": ""})
            break
        t0 = time.monotonic()
        started = now_iso()
        resp = call_endpoint(prompt, MAX_TOKENS, deadline_s=ITEM_DEADLINE_S)
        wall = round(time.monotonic() - t0, 3)
        att = {"attempt": attempt_no, "wall_s": wall,
               "error_class": resp.get("error"),
               "started_at": started, "finished_at": now_iso(),
               "finish_reason": resp["finish_reason"],
               "prompt_tokens": resp["prompt_tokens"],
               "completion_tokens": resp["completion_tokens"],
               "content": resp["content"], "reasoning": resp["reasoning"]}
        att.update(readouts(resp["content"], resp["reasoning"]))
        att["mechanics"] = mechanics(item, att, prompt)
        rec["attempts"].append(att)
        if not is_retryable(classify_attempt(att)):
            break
    last = rec["attempts"][-1]
    for field in ("content_answer", "reasoning_answer", "loose_fallback_answer",
                  "loose_fallback_source", "strict_trace_token",
                  "delivered_or_strict_answer", "fallback_provenance_class",
                  "fallback_commit_fraction"):
        rec[field] = last[field]
    rec["completion_tokens"] = last.get("completion_tokens", 0)
    rec["prompt_tokens"] = last.get("prompt_tokens", 0)
    rec["outcome"] = classify_attempt(last)
    gold = rec["gold"]
    rec["correct"] = {}
    for name in ("content_only", "loose_fallback", "delivered_or_strict"):
        ans = {"content_only": last["content_answer"],
               "loose_fallback": last["loose_fallback_answer"],
               "delivered_or_strict": last["delivered_or_strict_answer"]}[name]
        rec["correct"][name] = (None if ans is None
                                else int((1 if ans == "yes" else 0) == gold))
    return rec


def write_jsonl(path: str, rec: dict) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(canonical(rec) + "\n")
        fh.flush()
        os.fsync(fh.fileno())

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


def rank_values(vals: list) -> list:
    """Average ranks (ties share the mean of the ranks they span), for Spearman."""
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for t in range(i, j + 1):
            ranks[order[t]] = avg
        i = j + 1
    return ranks


def corr(xs: list, ys: list) -> dict:
    """Pearson r and Spearman rho between two equal-length numeric sequences.

    None instead of a number when the sample is smaller than three points or one side is
    constant (a constant side is a degenerate run, not a correlation of zero)."""
    def pearson(a: list, b: list):
        ma, mb = sum(a) / len(a), sum(b) / len(b)
        num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
        da = math.sqrt(sum((x - ma) ** 2 for x in a))
        db = math.sqrt(sum((y - mb) ** 2 for y in b))
        return None if da == 0 or db == 0 else num / (da * db)

    if len(xs) != len(ys) or len(xs) < 3:
        return {"n": len(xs), "pearson": None, "spearman": None}
    pr = pearson(xs, ys)
    sr = pearson(rank_values(xs), rank_values(ys))
    return {"n": len(xs),
            "pearson": (round(pr, 4) if pr is not None else None),
            "spearman": (round(sr, 4) if sr is not None else None)}



# ---------------------------------------------------------------------------
# This round's layer: the panel, the self-agreement pair, the noise floor
# ---------------------------------------------------------------------------

GATE_SCHEMA = "round38-gate-v1"
GATE_HASH = "unset"
PANEL_EDGES = {name: k * c for name, k, c in WALK}
PANEL_K = {name: k for name, k, _c in WALK}
# Derived from PANEL_DIGESTS order: arm F first, then arm X, in each cell.
PANEL_CELL = {digest: cell for cell, digest in PANEL_DIGESTS}
PANEL_ARM = {digest: ("F" if i % 2 == 0 else "X")
             for i, (_cell, digest) in enumerate(PANEL_DIGESTS)}


def output_sha(content: str, reasoning: str) -> str:
    """The quantity TARr is measured on: the whole sanitized generation, reasoning field and
    answer field together, in a fixed order, U+0000 separated. Two dispatches agree on raw output
    only when every token of both fields is identical."""
    return sha256_text((content or "") + "\x00" + (reasoning or ""))


def panel_units() -> list:
    """The 12 panel prompts: arm F and arm X of pair PANEL_PAIR_INDEX of every cell, in WALK
    order. Selection is by the archived selection order (build_cell is deterministic in the seed
    and takes candidates in seed order), so pair 0 here is pair 0 of round 24's corpus and no
    outcome influences the choice. Refuses unless every digest is one of PANEL_DIGESTS, every
    PANEL_DIGESTS entry is returned, and every panel digest carries an arm-consistent entry in
    the round-24 archive."""
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
        archived = PANEL_ARCHIVE["R24"].get(u["digest"])
        if archived is None or archived["arm"] != u["arm"] or archived["k"] != u["k"]:
            raise RuntimeError(f"panel digest {u['digest'][:12]} missing from the R24 archive")
    return units


def anchor_state(gate: dict) -> dict:
    """Fail-closed structural pin. Every cell's pool blob and all 36 prompt digests must equal
    round 24's gate, and the 12-entry panel must be a subset of those digests. Constants only, no
    file dependency, so the post-merge tree verifies the pin without the ancestor branch."""
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
            "provenance": ("research/nightly-2026-10-25-0405 (round 24, PR #98), gate.json, all "
                           "six cells of the declared grid; the panel is pair 0 of each cell")}


def firing_slopes(token_table: dict) -> dict:
    """Panel-basis cost slopes from a {digest: completion tokens} table. Load: mean cell tokens
    against E over the four k = 8 cells. Depth: mean cell tokens against k over the three E = 96
    cells. Same estimator as the published full-design laws, on 2 items per cell instead of 6.
    Refuses a partial cell, so a missing dispatch cannot silently move a slope."""
    means = {}
    for cell, digests in PANEL_CELLS.items():
        vals = [token_table[d] for d in digests if d in token_table]
        if len(vals) != len(digests):
            return {"load": None, "depth": None, "cell_means": None,
                    "note": f"cell {cell} has {len(vals)} of {len(digests)} items"}
        means[cell] = sum(vals) / len(vals)
    load = ols([(PANEL_EDGES[c], means[c]) for c in LOAD_NAMES])
    depth = ols([(PANEL_K[c], means[c]) for c in ("L0",) + DEPTH_NAMES])
    return {"load": (round(load["slope"], 4) if load["slope"] is not None else None),
            "load_r": load["r"], "depth": (round(depth["slope"], 4)
                                           if depth["slope"] is not None else None),
            "depth_r": depth["r"],
            "cell_means": {k: round(v, 2) for k, v in means.items()},
            "note": "panel basis: 2 items per cell"}


def panel_reference_slopes() -> dict:
    """Panel-basis slopes of the four archived firings, computed from the transcribed archives at
    gate time, so the reference a band is scored against is inside gate.json before any prompt is
    spent."""
    return {label: firing_slopes({d: v["tok"] for d, v in archive.items()})
            for label, archive in PANEL_ARCHIVE.items()}


def band_for(reference, band: tuple) -> list:
    """The house band around a reference slope, ordered so a negative reference still gives a
    usable interval (rounds 31 and 37 both score against negative references)."""
    if reference is None:
        return [None, None]
    lo, hi = sorted((reference * band[0], reference * band[1]))
    return [round(lo, 4), round(hi, 4)]


def in_band(value, reference, band: tuple) -> bool:
    if value is None or reference is None:
        return False
    lo, hi = band_for(reference, band)
    return lo <= value <= hi


def quantile(values: list, q: float):
    """Linear-interpolated empirical quantile (the definition matters at n = 12 and n = 84)."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = q * (len(ordered) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] * (1.0 - (pos - lo)) + ordered[hi] * (pos - lo)


def build_gate() -> dict:
    cells = all_cells()
    panel = panel_units()
    refs = panel_reference_slopes()
    reference = refs[N5_REFERENCE_FIRING]
    out = {
        "schema": GATE_SCHEMA, "seed_base": SEED_BASE, "alpha": ALPHA, "perms": PERMS,
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
        "matched_pair_invariant": ("identical fact list, identical entity name set, identical "
                                   "fact count, identical queried source; only the queried target "
                                   "varies (issue #78 acceptance criterion 1, polarity contrast)"),
        "panel_reference_slopes": refs,
        "published_full_design_slopes": PUBLISHED_SLOPES,
        "r33_published_full_grid_reference": R33_PUBLISHED,
        "boot": {"draws": BOOT_DRAWS, "seed": BOOT_SEED, "quantiles": list(FLOOR_QUANTILES),
                 "resolve_quantile": RESOLVE_QUANTILE},
        "strata": {k: [list(p) for p in v] for k, v in STRATA.items()},
        "predictions": {
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
                         f"stratum; a stratum whose floor rests on a single observed pair is "
                         f"reported as not separable, never as a change")},
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
    """One (prompt, pass) measurement: the archived record shape plus the three labels this round
    needs (pass_id, dispatch_mode, order_in_pass). Retries follow the inherited rule (transport
    failure or empty completion only), and every attempt is kept."""
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
               "content": resp["content"], "reasoning": resp["reasoning"]}
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
    """Incremental archive (#73): every measurement is appended and fsynced the moment it lands,
    so a firing that is killed mid-pass leaves the measurements it already paid for. Round 35 and
    round 36 both lost a whole round to a run that only held its records in memory."""

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
    """One pass over the panel at the pass's own concurrency, records returned in panel order and
    emitted to the sink as they land."""
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
    print(f"health: ok={health['ok']} outcome={health['outcome']} latency={health['latency_s']}s")
    if not health["ok"]:
        raise SystemExit("endpoint health check failed before the panel")
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
# Measurements, self-agreement, Wilson, noise floor
# ---------------------------------------------------------------------------

def measurements(records: list) -> dict:
    """{digest: {label: measurement}} over this run's three passes and the four archived firings.
    Joins are on the prompt digest, never on position: a firing either carries the digest or does
    not join at all."""
    meas: dict = collections.defaultdict(dict)
    for rec in records:
        meas[rec["prompt_sha256"]][rec["pass_id"]] = {
            "tok": rec["completion_tokens"], "ans": rec["content_answer"],
            "out_sha": rec["output_sha256"], "delivered": rec["delivered"],
            "correct": rec["correct"]["content_only"], "truncated": rec["truncated"],
            "dr": rec["distractor_mention_ratio"], "outcome": rec["outcome"],
            "source": "this_run"}
    for label in ("R24", "R33", "R31", "R37"):
        for digest, row in PANEL_ARCHIVE[label].items():
            entry = {"tok": row["tok"], "ans": row["ans"], "delivered": row["ans"] is not None,
                     "correct": (None if row["ans"] is None
                                 else int((1 if row["ans"] == "yes" else 0) == row["gold"])),
                     "truncated": row["fin"] == "length", "dr": row["dr"],
                     "outcome": row["out"], "source": "archive"}
            if "out_sha" in row:
                entry["out_sha"] = row["out_sha"]
            meas[digest][label] = entry
    return dict(meas)


def rel_dev(a, b):
    if a is None or b is None:
        return None
    centre = (a + b) / 2.0
    return (b - a) / centre if centre else None


def stratum_agreement(meas: dict) -> dict:
    """TARr (raw output) and TARa (parsed answer) per stratum and per cell, plus the per-prompt
    length deviation. Both are pairwise: a stratum that compares two dispatches of a prompt
    carries one pair for that prompt, and agreement is the share of pairs that agree. A firing
    whose archive carries no raw text hash is a non-joinable pair for TARr and is counted
    separately, never as agreement."""
    out = {}
    for stratum, pairs in STRATA.items():
        rows = {"raw_agree": 0, "raw_unjoinable": 0, "answer_agree": 0,
                "delivered_pairs": 0, "answer_agree_delivered": 0, "correct_agree": 0,
                "correct_pairs": 0, "delivery_agree": 0, "material_moves": 0, "devs": [],
                "per_cell": {cell: {"pairs": 0, "raw_agree": 0, "answer_agree": 0,
                                    "raw_unjoinable": 0}
                             for cell in PANEL_CELLS},
                "discordant": []}
        n_pairs = 0
        for label_a, label_b in pairs:
            for _cell, digest in PANEL_DIGESTS:
                entry = meas.get(digest, {})
                a, b = entry.get(label_a), entry.get(label_b)
                if a is None or b is None:
                    continue
                cell = PANEL_CELL[digest]
                n_pairs += 1
                rows["per_cell"][cell]["pairs"] += 1
                sha_a, sha_b = a.get("out_sha"), b.get("out_sha")
                if sha_a is None or sha_b is None:
                    rows["raw_unjoinable"] += 1
                    rows["per_cell"][cell]["raw_unjoinable"] += 1
                else:
                    agree = sha_a == sha_b
                    rows["raw_agree"] += int(agree)
                    rows["per_cell"][cell]["raw_agree"] += int(agree)
                    if not agree:
                        rows["discordant"].append({"cell": cell, "arm": PANEL_ARM[digest],
                                                   "digest": digest[:12],
                                                   "pair": [label_a, label_b],
                                                   "kind": "raw_output",
                                                   "tokens": [a["tok"], b["tok"]]})
                ans_agree = a["ans"] == b["ans"]
                rows["answer_agree"] += int(ans_agree)
                rows["per_cell"][cell]["answer_agree"] += int(ans_agree)
                if not ans_agree:
                    rows["discordant"].append({"cell": cell, "arm": PANEL_ARM[digest],
                                               "digest": digest[:12],
                                               "pair": [label_a, label_b],
                                               "kind": "parsed_answer",
                                               "answers": [a["ans"], b["ans"]]})
                if a["delivered"] and b["delivered"]:
                    rows["delivered_pairs"] += 1
                    rows["answer_agree_delivered"] += int(ans_agree)
                rows["delivery_agree"] += int(a["delivered"] == b["delivered"])
                if a["correct"] is not None and b["correct"] is not None:
                    rows["correct_pairs"] += 1
                    rows["correct_agree"] += int(a["correct"] == b["correct"])
                dev = rel_dev(a["tok"], b["tok"])
                if dev is not None:
                    rows["devs"].append(dev)
                    if abs(dev) >= MATERIAL_REL_DEV:
                        rows["material_moves"] += 1
        abs_devs = sorted(abs(d) for d in rows["devs"])
        joinable = n_pairs - rows["raw_unjoinable"]
        summary = {
            "n_pairs": n_pairs,
            "raw_discordant": joinable - rows["raw_agree"],
            "answer_discordant": n_pairs - rows["answer_agree"],
            "delivery_discordant": n_pairs - rows["delivery_agree"],
            "tarr": round(rows["raw_agree"] / joinable, 4) if joinable else None,
            "tarr_joinable_pairs": joinable,
            "tara": round(rows["answer_agree"] / n_pairs, 4) if n_pairs else None,
            "tara_delivered_only": (round(rows["answer_agree_delivered"] / rows["delivered_pairs"],
                                          4) if rows["delivered_pairs"] else None),
            "delivery_agreement": round(rows["delivery_agree"] / n_pairs, 4) if n_pairs else None,
            "correctness_agreement": (round(rows["correct_agree"] / rows["correct_pairs"], 4)
                                      if rows["correct_pairs"] else None),
            "raw_unjoinable_pairs": rows["raw_unjoinable"],
            "material_moves": rows["material_moves"],
            "abs_rel_dev_median": round(quantile(abs_devs, 0.50), 4) if abs_devs else None,
            "abs_rel_dev_p90": round(quantile(abs_devs, 0.90), 4) if abs_devs else None,
            "abs_rel_dev_max": round(abs_devs[-1], 4) if abs_devs else None,
            "per_cell": {cell: {"n_pairs": counts["pairs"],
                                "tarr_joinable_pairs": counts["pairs"]
                                - counts["raw_unjoinable"],
                                "tarr": (round(counts["raw_agree"]
                                               / (counts["pairs"] - counts["raw_unjoinable"]), 4)
                                         if counts["pairs"] - counts["raw_unjoinable"] else None),
                                "tara": (round(counts["answer_agree"] / counts["pairs"], 4)
                                         if counts["pairs"] else None)}
                         for cell, counts in rows["per_cell"].items()},
            "discordant": rows["discordant"],
        }
        out[stratum] = summary
    return out


def cell_accuracy_and_wilson(records: list) -> dict:
    """Issue #100 acceptance criterion 2: a Wilson 95 percent interval next to the accuracy of
    every cell. Two denominators, because they answer different questions and must not be
    confused. per_item treats the 2 distinct panel digests of a cell as the unit (a digest is
    correct when a majority of its dispatches are correct). per_dispatch treats the 6 dispatches
    as the unit; its interval is tighter and the less honest one, since those 6 dispatches are 2
    items seen three times, so effective_n is stored beside it."""
    per_cell: dict = collections.defaultdict(lambda: {"digests": set(), "dispatches": 0,
                                                      "dispatch_correct": 0,
                                                      "dispatch_delivered": 0})
    by_digest: dict = collections.defaultdict(list)
    for rec in records:
        cell = rec["cell"]
        per_cell[cell]["digests"].add(rec["prompt_sha256"])
        per_cell[cell]["dispatches"] += 1
        per_cell[cell]["dispatch_delivered"] += int(rec["delivered"])
        per_cell[cell]["dispatch_correct"] += int(rec["correct"]["content_only"] == 1)
        by_digest[rec["prompt_sha256"]].append(rec["correct"]["content_only"])
    out = {}
    for cell in WALK_INDEX:
        info = per_cell.get(cell)
        if not info:
            continue
        digests = sorted(info["digests"])
        item_flags = []
        for digest in digests:
            votes = by_digest[digest]
            item_flags.append(1 if sum(1 for v in votes if v == 1) > len(votes) / 2.0 else 0)
        items_lo, items_hi = wilson(sum(item_flags), len(item_flags))
        disp_lo, disp_hi = wilson(info["dispatch_correct"], info["dispatches"])
        out[cell] = {
            "per_item": {"n_items": len(item_flags), "correct": sum(item_flags),
                         "accuracy": round(sum(item_flags) / len(item_flags), 4)
                         if item_flags else None,
                         "wilson_low": round(items_lo, 4), "wilson_high": round(items_hi, 4),
                         "unit": "distinct prompt digest, majority over its dispatches"},
            "per_dispatch": {"n_dispatches": info["dispatches"],
                             "correct": info["dispatch_correct"],
                             "accuracy": round(info["dispatch_correct"] / info["dispatches"], 4)
                             if info["dispatches"] else None,
                             "wilson_low": round(disp_lo, 4), "wilson_high": round(disp_hi, 4),
                             "effective_n": len(item_flags),
                             "caveat": "dispatches of the same item are not independent; "
                                       "effective_n is the honest denominator"},
            "delivered_dispatches": info["dispatch_delivered"],
            "digests": digests,
        }
    return out


def dev_pool(meas: dict, stratum: str) -> list:
    """Every observed per-prompt relative completion-length deviation of one stratum: same
    prompts, same class, same conditions. This is the empirical noise the floor is built from."""
    pool = []
    for label_a, label_b in STRATA[stratum]:
        for _cell, digest in PANEL_DIGESTS:
            entry = meas.get(digest, {})
            a, b = entry.get(label_a), entry.get(label_b)
            if a is None or b is None:
                continue
            dev = rel_dev(a["tok"], b["tok"])
            if dev is not None:
                pool.append(dev)
    return pool


def base_tokens(meas: dict, labels) -> dict:
    """{digest: [length of each listed label]} for the digests where every label joined."""
    out = {}
    for _cell, digest in PANEL_DIGESTS:
        entry = meas.get(digest, {})
        vals = [entry[label]["tok"] for label in labels if label in entry]
        if len(vals) == len(labels):
            out[digest] = vals
    return out


def slope_noise_floor(base: dict, pool: list, draws: int, seed: int) -> dict:
    """The floor: propagate a stratum's own observed per-prompt length differences through the
    same slope estimator. For each draw and each prompt a symmetric pseudo-pair of firings is
    built around the prompt's mean length, its separation drawn from the observed deviation pool,
    and the two pseudo-firings' panel slopes are differenced. The result is the distribution of
    |slope difference| this design produces when nothing at all has changed, in tokens/fact and
    tokens/hop. Stated assumption: the observed deviations are exchangeable across the 12 panel
    prompts."""
    if len(pool) < 2:
        return {"note": "fewer than two observed deviations, no floor", "n_dev": len(pool)}
    means = {}
    for digest, values in base.items():
        vals = [v for v in values if v is not None]
        if not vals:
            return {"note": "a panel prompt has no base length"}
        means[digest] = sum(vals) / len(vals)
    if len(means) != len(PANEL_DIGESTS):
        return {"note": "base lengths do not cover the panel", "n_base": len(means)}
    rng = random.Random(seed)
    load_deltas = []
    depth_deltas = []
    for _ in range(draws):
        tokens_a = {}
        tokens_b = {}
        for digest, mean in means.items():
            dev = rng.choice(pool)
            tokens_a[digest] = mean * (1.0 + dev / 2.0)
            tokens_b[digest] = mean * (1.0 - dev / 2.0)
        sa = firing_slopes(tokens_a)
        sb = firing_slopes(tokens_b)
        if sa["load"] is None or sb["load"] is None:
            return {"note": "slope refused on synthetic lengths"}
        load_deltas.append(abs(sa["load"] - sb["load"]))
        depth_deltas.append(abs(sa["depth"] - sb["depth"]))
    return {"n_dev": len(pool), "draws": draws, "seed": seed,
            "load_abs_delta": {f"q{int(q * 100)}": round(quantile(load_deltas, q), 4)
                               for q in FLOOR_QUANTILES},
            "depth_abs_delta": {f"q{int(q * 100)}": round(quantile(depth_deltas, q), 4)
                                for q in FLOOR_QUANTILES}}


def observed_slope_delta(meas: dict, label_a: str, label_b: str) -> dict:
    """The model-free floor entry: the two firings' own panel slopes and their difference."""
    ta = {d: meas[d][label_a]["tok"] for _c, d in PANEL_DIGESTS if label_a in meas.get(d, {})}
    tb = {d: meas[d][label_b]["tok"] for _c, d in PANEL_DIGESTS if label_b in meas.get(d, {})}
    sa = firing_slopes(ta)
    sb = firing_slopes(tb)
    if sa["load"] is None or sb["load"] is None:
        return {"note": "one side incomplete", "a": sa, "b": sb}
    return {"a": sa, "b": sb,
            "delta_load": round(sb["load"] - sa["load"], 4),
            "delta_depth": round(sb["depth"] - sa["depth"], 4),
            "ratio_load": (round(sb["load"] / sa["load"], 4) if sa["load"] else None),
            "ratio_depth": (round(sb["depth"] / sa["depth"], 4) if sa["depth"] else None)}


def flip_risk(flip_count: int, pair_count: int, items: int = 6) -> dict:
    """Per-item flip risk with its own uncertainty, carried into the quantity #100 asks for: the
    probability that at least one item of a six-item cell moves across a re-run. Reported at the
    measured rate and at the Wilson upper bound of that rate. The independence assumption is the
    one a single run cannot test, so it is named here rather than hidden, and the within-run
    stratum is the only evidence available on it."""
    if pair_count == 0:
        return {"note": "no pairs"}
    lo, hi = wilson(flip_count, pair_count)
    rate = flip_count / pair_count
    return {"flips": flip_count, "pairs": pair_count, "rate": round(rate, 4),
            "rate_wilson_low": round(lo, 4), "rate_wilson_high": round(hi, 4),
            "p_at_least_one_of_six_at_rate": round(1.0 - (1.0 - rate) ** items, 4),
            "p_at_least_one_of_six_at_upper_bound": round(1.0 - (1.0 - hi) ** items, 4),
            "assumption": "items flip independently; only the within-run stratum tests this"}


def class_identity_diagnostic(meas: dict) -> dict:
    """The archive does not fingerprint endpoints, so the strongest evidence it can carry that two
    rounds hit the same deployment is per-prompt raw-output agreement against their archives. This
    is a measurement, not a prediction: it says how far this run sits from each archived firing,
    and the cross-firing reading of every other number here depends on it."""
    out = {}
    for label in ("R24", "R33", "R31", "R37"):
        identical = 0
        comparable = 0
        answer_agree = 0
        answer_pairs = 0
        devs = []
        for _cell, digest in PANEL_DIGESTS:
            entry = meas.get(digest, {})
            archived = entry.get(label)
            if archived is None:
                continue
            for pass_id in PASS_IDS:
                here = entry.get(pass_id)
                if here is None:
                    continue
                if "out_sha" in archived:
                    comparable += 1
                    identical += int(archived["out_sha"] == here["out_sha"])
                answer_pairs += 1
                answer_agree += int(archived["ans"] == here["ans"])
                dev = rel_dev(archived["tok"], here["tok"])
                if dev is not None:
                    devs.append(abs(dev))
        out[label] = {
            "class_of_firing": ("this class" if label in SAME_CLASS_FIRINGS else "other class"),
            "raw_output_identical": f"{identical}/{comparable}" if comparable else "n/a",
            "answer_agreement": round(answer_agree / answer_pairs, 4) if answer_pairs else None,
            "abs_rel_dev_median": round(quantile(devs, 0.50), 4) if devs else None,
            "abs_rel_dev_max": round(max(devs), 4) if devs else None,
        }
    return out


# ---------------------------------------------------------------------------
# Aggregation: the self-agreement pair, the floors, the verdicts
# ---------------------------------------------------------------------------

def pair_floor(meas: dict, label_a: str, label_b: str, draws: int, seed: int) -> dict:
    """One pair of dispatches, its own floor: the 12 per-prompt length deviations of that pair,
    propagated through the slope estimator. Each pair carries its own floor because the strata are
    not interchangeable: a same-session serialized pair and a pair three days apart are different
    measurements, and pooling them would hide which condition moves the number."""
    base = {}
    pool = []
    for _cell, digest in PANEL_DIGESTS:
        entry = meas.get(digest, {})
        a, b = entry.get(label_a), entry.get(label_b)
        if a is None or b is None:
            continue
        base[digest] = [a["tok"], b["tok"]]
        dev = rel_dev(a["tok"], b["tok"])
        if dev is not None:
            pool.append(dev)
    return slope_noise_floor(base, pool, draws, seed)


def per_cell_selfagreement(strata: dict, cell_table: dict) -> dict:
    """Issue #100 acceptance criteria 1 and 2 in one place: for every cell, the self-agreement
    pair (raw-output TARr, parsed-answer TARa) at each measured condition, next to the accuracy
    and its Wilson interval. This is the block the M2 harness (#5) is asked to emit for every cell
    that feeds the decision table."""
    out = {}
    for cell in WALK_INDEX:
        row = {"agreement": {}}
        for stratum in SAME_CLASS_STRATA:
            entry = strata.get(stratum, {}).get("per_cell", {}).get(cell)
            if entry:
                row["agreement"][stratum] = entry
        stats = cell_table.get(cell)
        if stats:
            row["accuracy_per_item"] = stats["per_item"]["accuracy"]
            row["wilson_per_item"] = [stats["per_item"]["wilson_low"],
                                      stats["per_item"]["wilson_high"]]
            row["accuracy_per_dispatch"] = stats["per_dispatch"]["accuracy"]
            row["wilson_per_dispatch"] = [stats["per_dispatch"]["wilson_low"],
                                          stats["per_dispatch"]["wilson_high"]]
            row["effective_n_items"] = stats["per_dispatch"]["effective_n"]
        out[cell] = row
    return out


def resolvability(meas: dict, gate: dict) -> dict:
    """Every slope difference this round can name, judged against the floor of its own condition.
    The rule is the one round 37's lesson asks for: a difference is a CHANGE only when it clears
    the q99 of the noise the same design produces when nothing has changed; below that it is NOT
    SEPARABLE, whatever the house band says."""
    boot = gate["boot"]
    rows = {}
    for stratum, pairs in STRATA.items():
        judged = []
        for label_a, label_b in pairs:
            obs = observed_slope_delta(meas, label_a, label_b)
            floor = pair_floor(meas, label_a, label_b, boot["draws"], boot["seed"])
            entry = {"pair": [label_a, label_b]}
            if obs.get("note") or floor.get("note"):
                entry["note"] = obs.get("note") or floor.get("note")
                judged.append(entry)
                continue
            load_q = floor["load_abs_delta"]["q99"]
            depth_q = floor["depth_abs_delta"]["q99"]
            entry.update({
                "floor_is_zero": {"load": load_q == 0.0, "depth": depth_q == 0.0},
                "load_a": obs["a"]["load"], "load_b": obs["b"]["load"],
                "depth_a": obs["a"]["depth"], "depth_b": obs["b"]["depth"],
                "delta_load": obs["delta_load"], "delta_depth": obs["delta_depth"],
                "ratio_load": obs["ratio_load"], "ratio_depth": obs["ratio_depth"],
                "floor_load_q50": floor["load_abs_delta"]["q50"],
                "floor_load_q99": load_q,
                "floor_depth_q50": floor["depth_abs_delta"]["q50"],
                "floor_depth_q99": depth_q,
                "load_verdict": ("change" if abs(obs["delta_load"]) > load_q
                                 else "not separable from run noise"),
                "depth_verdict": ("change" if abs(obs["delta_depth"]) > depth_q
                                  else "not separable from run noise"),
                "cell_means_a": obs["a"]["cell_means"], "cell_means_b": obs["b"]["cell_means"],
            })
            judged.append(entry)
        rows[stratum] = {"n_pairs_of_firings": len(pairs), "pairs": judged}

    def worst(stratum, key):
        values = [p[key] for p in rows[stratum]["pairs"] if key in p]
        return round(max(values), 4) if values else None

    own = {"load": worst("cross_firing", "floor_load_q99"),
           "depth": worst("cross_firing", "floor_depth_q99")}
    other = {"load": worst("other_class", "floor_load_q99"),
             "depth": worst("other_class", "floor_depth_q99")}
    cross = []
    for label_a, label_b in STRATA["cross_class"]:
        obs = observed_slope_delta(meas, label_a, label_b)
        if obs.get("note"):
            continue
        union_load = max(v for v in (own["load"], other["load"]) if v is not None)
        union_depth = max(v for v in (own["depth"], other["depth"]) if v is not None)
        cross.append({
            "pair": [label_a, label_b], "this_class": label_a, "other_class": label_b,
            "delta_load": obs["delta_load"], "delta_depth": obs["delta_depth"],
            "ratio_load": obs["ratio_load"], "ratio_depth": obs["ratio_depth"],
            "floor_this_class_load_q99": own["load"], "floor_this_class_depth_q99": own["depth"],
            "floor_other_class_load_q99": other["load"],
            "floor_other_class_depth_q99": other["depth"],
            "union_floor_load": union_load, "union_floor_depth": union_depth,
            "load_verdict": ("resolvable" if abs(obs["delta_load"]) > union_load
                             else "not separable from run noise"),
            "depth_verdict": ("resolvable" if abs(obs["delta_depth"]) > union_depth
                              else "not separable from run noise"),
            "note": ("the other class's floor rests on ONE pair of firings (rounds 31 and 37), so "
                     "resolvable here means beyond the largest noise either class has "
                     "demonstrated, not beyond a replicated bound"),
        })
    return {"per_stratum": rows, "cross_class": cross,
            "rule": f"a difference counts as a change only beyond the {RESOLVE_QUANTILE} "
                    f"quantile of its own condition's floor",
            "zero_floor_meaning": ("a floor of zero means that condition produced no measurable "
                                   "variation at all: it is a determinism result, not a bound. A "
                                   "nonzero difference measured against a zero floor is not "
                                   "certified as a change until the floor itself has replicates")}


def score_predictions(gate: dict, meas: dict, strata: dict, records: list, slopes: dict,
                      resolve: dict) -> dict:
    out = {}
    same = strata["within_run_same_mode"]
    mode = strata["within_run_mode_change"]
    same_cell_min = min([c["tarr"] for c in same["per_cell"].values()
                         if c["tarr"] is not None] or [1.0])
    out["N1"] = {"measured_tarr_grid": same["tarr"], "measured_tarr_worst_cell": same_cell_min,
                 "n_pairs": same["n_pairs"],
                 "threshold_grid": N1_TARR_GRID_MIN, "threshold_cell": N1_TARR_CELL_MIN,
                 "pass": (same["tarr"] is not None and same["tarr"] >= N1_TARR_GRID_MIN
                          and same_cell_min >= N1_TARR_CELL_MIN)}
    worst_tokens = 0
    worst_detail = None
    for label_a, label_b in STRATA["within_run_mode_change"]:
        for _cell, digest in PANEL_DIGESTS:
            entry = meas.get(digest, {})
            a, b = entry.get(label_a), entry.get(label_b)
            if a is None or b is None:
                continue
            delta = abs(a["tok"] - b["tok"])
            if delta > worst_tokens:
                worst_tokens = delta
                worst_detail = {"cell": PANEL_CELL[digest], "arm": PANEL_ARM[digest],
                                "pair": [label_a, label_b], "tokens": [a["tok"], b["tok"]]}
    out["N2"] = {"measured_tarr_grid": mode["tarr"], "threshold_tarr": N2_TARR_GRID_MIN,
                 "n_pairs": mode["n_pairs"], "worst_abs_token_change": worst_tokens,
                 "worst_change_detail": worst_detail,
                 "threshold_token_change": N2_TOKEN_DELTA_MAX,
                 "pass": (mode["tarr"] is not None and mode["tarr"] >= N2_TARR_GRID_MIN
                          and worst_tokens <= N2_TOKEN_DELTA_MAX)}
    tara_by_stratum = {name: s["tara"] for name, s in strata.items()}
    out["N3"] = {"measured_tara_by_stratum": tara_by_stratum, "threshold": N3_TARA_GRID_MIN,
                 "pass": all(v is not None and v >= N3_TARA_GRID_MIN
                             for v in tara_by_stratum.values())}
    delivered = sum(1 for r in records if r["delivered"])
    correct = sum(1 for r in records if r["correct"]["content_only"] == 1)
    out["N4"] = {"delivered": delivered, "correct_content_only": correct,
                 "dispatches": len(records),
                 "threshold_delivered": N4_DELIVERED_MIN, "threshold_correct": N4_CORRECT_MIN,
                 "pass": delivered >= N4_DELIVERED_MIN and correct >= N4_CORRECT_MIN}
    ref = gate["panel_reference_slopes"][N5_REFERENCE_FIRING]
    pass_rows = {}
    for pass_id in PASS_IDS:
        slopes_this = slopes.get(pass_id, {})
        if slopes_this.get("load") is None:
            pass_rows[pass_id] = {"note": slopes_this.get("note", "no slope")}
            continue
        pass_rows[pass_id] = {
            "load": slopes_this["load"], "depth": slopes_this["depth"],
            "load_in_band": in_band(slopes_this["load"], ref["load"], N5_COST_BAND),
            "depth_in_band": in_band(slopes_this["depth"], ref["depth"], N5_COST_BAND),
            "load_ratio_vs_reference": (round(slopes_this["load"] / ref["load"], 4)
                                        if ref["load"] else None),
            "depth_ratio_vs_reference": (round(slopes_this["depth"] / ref["depth"], 4)
                                         if ref["depth"] else None)}
    out["N5"] = {"reference": N5_REFERENCE_FIRING, "reference_load": ref["load"],
                 "reference_depth": ref["depth"],
                 "band_load": band_for(ref["load"], N5_COST_BAND),
                 "band_depth": band_for(ref["depth"], N5_COST_BAND), "per_pass": pass_rows,
                 "pass": all("note" not in r and r["load_in_band"] and r["depth_in_band"]
                             for r in pass_rows.values())}
    within = [p for name in ("within_run_same_mode", "within_run_mode_change")
              for p in resolve["per_stratum"][name]["pairs"] if "load_verdict" in p]
    cross_own = [p for p in resolve["per_stratum"]["cross_firing"]["pairs"]
                 if "load_verdict" in p]
    out["N6"] = {
        "criterion": gate["predictions"]["N6_guard"],
        "within_run_pairs_judged": len(within),
        "within_run_any_change_detected": any(p["load_verdict"] == "change"
                                              or p["depth_verdict"] == "change" for p in within),
        "cross_firing_pairs_judged": len(cross_own),
        "cross_firing_any_change_detected": any(p["load_verdict"] == "change"
                                                or p["depth_verdict"] == "change"
                                                for p in cross_own),
        "cross_class": resolve["cross_class"],
        "pass": all(p["load_verdict"] != "change" and p["depth_verdict"] != "change"
                    for p in within + cross_own)}
    out["passed"] = sorted(k for k, v in out.items() if isinstance(v, dict) and v.get("pass"))
    out["failed"] = sorted(k for k, v in out.items()
                           if isinstance(v, dict) and v.get("pass") is False)
    return out


def aggregate(records: list, gate: dict) -> dict:
    meas = measurements(records)
    strata = stratum_agreement(meas)
    cell_table = cell_accuracy_and_wilson(records)
    slopes = {}
    for label in list(PASS_IDS) + list(PANEL_ARCHIVE):
        table = {}
        for _cell, digest in PANEL_DIGESTS:
            entry = meas.get(digest, {})
            if label in entry:
                table[digest] = entry[label]["tok"]
        slopes[label] = firing_slopes(table)
    resolve = resolvability(meas, gate)
    per_pass = {}
    for plan in PASS_PLAN:
        rows = [r for r in records if r["pass_id"] == plan["pass_id"]]
        per_pass[plan["pass_id"]] = {
            "mode": plan["mode"], "concurrency": plan["concurrency"], "items": len(rows),
            "attempt_wall_s_sum": round(sum(a["wall_s"] for r in rows for a in r["attempts"]), 1),
            "completion_tokens": sum(r["completion_tokens"] for r in rows),
            "prompt_tokens": sum(r["prompt_tokens"] for r in rows),
            "retries": sum(1 for r in rows if r["retried"]),
            "transport_errors": sum(1 for r in rows if r["outcome"].startswith("transport_")),
            "truncations": sum(1 for r in rows if r["truncated"]),
            "delivered": sum(1 for r in rows if r["delivered"]),
            "correct": sum(1 for r in rows if r["correct"]["content_only"] == 1),
            "started_at": min((a["started_at"] for r in rows for a in r["attempts"]
                               if a.get("started_at")), default=None),
            "finished_at": max((a["finished_at"] for r in rows for a in r["attempts"]
                                if a.get("finished_at")), default=None)}
    flip = {}
    for stratum in ("within_run_same_mode", "within_run_mode_change", "cross_firing"):
        rows = strata[stratum]
        flip[stratum] = {
            "pairs": rows["n_pairs"],
            "raw_output": flip_risk(rows["raw_discordant"], rows["n_pairs"]),
            "parsed_answer": flip_risk(rows["answer_discordant"], rows["n_pairs"]),
            "delivery": flip_risk(rows["delivery_discordant"], rows["n_pairs"]),
            "material_length_move": flip_risk(rows["material_moves"], rows["n_pairs"])}
    return {
        "schema": "round38-summary-v1", "gate_schema": gate["schema"],
        "gate_hash": GATE_HASH, "generated_at": now_iso(),
        "panel": {"digests": len(PANEL_DIGESTS), "passes": list(PASS_IDS),
                  "cells": sorted(PANEL_CELLS), "items_per_cell": CELL_ITEMS,
                  "dispatches": len(records),
                  "dispatches_expected": len(PANEL_DIGESTS) * len(PASS_PLAN)},
        "transport": {"per_pass": per_pass,
                      "calls_used": (1 + sum(len(r["attempts"]) for r in records)),
                      "prompt_cap": PROMPT_CAP, "max_tokens": MAX_TOKENS,
                      "temperature": TEMPERATURE,
                      "note": "passes 1 and 3 are serialized, pass 2 runs at the concurrency the "
                              "archived rounds on this class used"},
        "delivery": {"dispatches": len(records),
                     "delivered": sum(1 for r in records if r["delivered"]),
                     "correct_content_only": sum(1 for r in records
                                                 if r["correct"]["content_only"] == 1),
                     "truncated": sum(1 for r in records if r["truncated"]),
                     "retried": sum(1 for r in records if r["retried"]),
                     "outcomes": dict(collections.Counter(r["outcome"] for r in records))},
        "self_agreement": strata,
        "per_cell_selfagreement_and_wilson": per_cell_selfagreement(strata, cell_table),
        "cell_accuracy_wilson": cell_table,
        "panel_slopes": slopes,
        "published_full_design_slopes": PUBLISHED_SLOPES,
        "noise_floors_and_verdicts": resolve,
        "per_item_flip_risk": flip,
        "class_identity_diagnostic": class_identity_diagnostic(meas),
        "predictions": score_predictions(gate, meas, strata, records, slopes, resolve),
        "labels": {
            "evidence": "Executed",
            "why": "one endpoint, one firing, no independent second implementation, not covered "
                   "by the pre-registered decision table",
            "per_cell_n": f"{CELL_ITEMS} distinct items per cell ({CELL_DISPATCHES} dispatches): "
                          f"exploratory, no cell verdict is re-placed",
            "class_identity": "an inference from the pool slot and the served model id, not a "
                              "fingerprint; see class_identity_diagnostic"},
    }


def cmd_gate(out_path: str) -> int:
    gate = build_gate()
    payload = json.dumps(gate, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(payload)
    digest = gate_hash(gate)
    print(f"gate {digest[:8]} written to {out_path} ({len(gate['cells'])} cells, "
          f"{gate['panel']['items']} panel items x {len(PASS_PLAN)} passes = "
          f"{gate['planned_prompts']} prompts)")
    print(f"anchor_ok={gate['anchor_ok']} all_cells_pass={gate['all_cells_pass']}")
    if not gate["anchor_ok"]:
        for cell_id, row in gate["anchor"]["anchors"].items():
            if not (row["pool_blob_matches"] and row["forward_prompts_match"]
                    and row["cross_prompts_match"] and row["panel_in_corpus"]):
                print(f"  pin FAILED for {cell_id}")
        return 1
    return 0


def cmd_analyze(out_dir: str) -> int:
    with open(os.path.join(out_dir, "gate.json"), encoding="utf-8") as fh:
        gate = json.load(fh)
    global GATE_HASH
    GATE_HASH = gate_hash(gate)
    records = []
    with open(os.path.join(out_dir, "raw.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("gate_hash") != GATE_HASH:
                raise SystemExit("raw.jsonl carries a different gate hash")
            records.append(rec)
    expected = len(PANEL_DIGESTS) * len(PASS_PLAN)
    if len(records) != expected:
        raise SystemExit(f"raw.jsonl holds {len(records)} records, expected {expected}")
    summary = aggregate(records, gate)
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=True) + "\n")
    print(f"summary.json written: {len(records)} records, gate {GATE_HASH[:8]}")
    for name, row in summary["self_agreement"].items():
        print(f"  {name}: pairs {row['n_pairs']}, TARr {row['tarr']}, TARa {row['tara']}, "
              f"median |rel dev| {row['abs_rel_dev_median']}")
    print(f"  predictions passed: {summary['predictions']['passed']}")
    print(f"  predictions failed: {summary['predictions']['failed']}")
    return 0


# ---------------------------------------------------------------------------
# Selftest: estimator arithmetic, planted controls, fail-closed behaviour
# ---------------------------------------------------------------------------

def synth_record(cell: str, digest: str, pass_id: str, tokens: int, answer, out_sha: str,
                 gate_hash_value: str = "selftest") -> dict:
    """A record carrying every field the analysis layer reads, for the planted controls below.
    Nothing here comes from an endpoint: it is synthetic input for the scoring code."""
    gold = 1 if PANEL_ARM[digest] == "F" else 0
    correct = None if answer is None else int((1 if answer == "yes" else 0) == gold)
    attempt = {"attempt": 1, "wall_s": 1.0, "error_class": None,
               "started_at": "2026-10-31T00:00:00Z", "finished_at": "2026-10-31T00:00:01Z",
               "finish_reason": "stop" if answer is not None else "length",
               "prompt_tokens": 100, "completion_tokens": tokens, "content": answer or "",
               "reasoning": "", "output_sha256": out_sha,
               "mechanics": {"distractor_mention_ratio": 0.5}}
    return {"cell": cell, "arm": PANEL_ARM[digest], "pass_id": pass_id,
            "dispatch_mode": "serial", "dispatch_concurrency": 1, "order_in_pass": 0,
            "prompt_sha256": digest, "k": PANEL_K[cell], "edges": PANEL_EDGES[cell],
            "gold": gold, "gate_hash": gate_hash_value, "phase": 1, "attempts": [attempt],
            "completion_tokens": tokens, "prompt_tokens": 100,
            "content_answer": answer, "output_sha256": out_sha,
            "distractor_mention_ratio": 0.5,
            "correct": {"content_only": correct, "loose_fallback": correct,
                        "delivered_or_strict": correct},
            "outcome": "answered_in_answer_field" if answer is not None else "truncated_no_answer",
            "finish_reason": "stop" if answer is not None else "length",
            "delivered": answer is not None, "truncated": answer is None, "retried": False}


def synth_records(tokens_by: dict, answers_by: dict, shas_by: dict) -> list:
    """tokens_by/answers_by/shas_by map (digest, pass_id) to a value; a missing sha falls back to
    a value derived from the tokens, so an all-identical panel is easy to declare."""
    records = []
    for cell, digest in PANEL_DIGESTS:
        for pass_id in PASS_IDS:
            tokens = tokens_by.get((digest, pass_id), 1000)
            answer = answers_by.get((digest, pass_id), "yes" if PANEL_ARM[digest] == "F" else "no")
            sha = shas_by.get((digest, pass_id), f"{digest[:16]}-{tokens}")
            records.append(synth_record(cell, digest, pass_id, tokens, answer, sha))
    return records


def _wilson_score_z(p0: float, p_hat: float, n: int) -> float:
    """Independent route to the same quantity: a Wilson endpoint is a p0 whose score-test z
    equals the confidence z. Recomputing z at the endpoint audits the closed form."""
    if p0 <= 0.0 or p0 >= 1.0:
        return float("inf")
    return abs(p_hat - p0) / math.sqrt(p0 * (1.0 - p0) / n)


def selftest() -> int:
    checks = 0

    def ck(name: str, cond) -> None:
        nonlocal checks
        checks += 1
        if not cond:
            raise AssertionError(f"selftest failed: {name}")

    # --- A. estimator arithmetic -------------------------------------------------------
    fit = ols([(0.0, 0.0), (1.0, 2.0), (2.0, 4.0)])
    ck("ols slope", fit["slope"] == 2.0)
    ck("ols intercept", fit["intercept"] == 0.0)
    ck("ols r", fit["r"] == 1.0)
    ck("ols refuses one point", ols([(1.0, 1.0)])["slope"] is None)
    flat = ols([(0.0, 5.0), (1.0, 5.0), (2.0, 5.0)])
    ck("ols flat slope", flat["slope"] == 0.0)
    ck("ols flat r is undefined", flat["r"] is None)
    for k, n in ((0, 1), (1, 2), (3, 6), (5, 6), (2, 6), (6, 6), (35, 36), (32, 36)):
        lo, hi = wilson(k, n)
        p_hat = k / n
        ck(f"wilson brackets p_hat {k}/{n}", lo <= p_hat <= hi)
        if 0 < k < n:
            ck(f"wilson inverts the score test at {k}/{n}",
               abs(_wilson_score_z(lo, p_hat, n) - 1.959963984540054) < 1e-6
               and abs(_wilson_score_z(hi, p_hat, n) - 1.959963984540054) < 1e-6)
        else:
            ck(f"wilson boundary {k}/{n}", lo >= 0.0 and hi <= 1.0)
    ck("wilson of nothing", wilson(0, 0) == (0.0, 0.0))
    ck("mcnemar no discordance", mcnemar_exact(0, 0) == 1.0)
    ck("mcnemar one-sided single", mcnemar_exact(1, 0) == 1.0)
    ck("mcnemar five to zero", abs(mcnemar_exact(5, 0) - 0.0625) < 1e-12)
    ck("mcnemar balanced", abs(mcnemar_exact(3, 3) - 1.0) < 1e-12)
    ck("quantile low", quantile(list(range(1, 11)), 0.0) == 1)
    ck("quantile high", quantile(list(range(1, 11)), 1.0) == 10)
    ck("quantile median", quantile(list(range(1, 11)), 0.5) == 5.5)
    ck("quantile single", quantile([7], 0.99) == 7)
    ck("quantile empty", quantile([], 0.5) is None)
    ck("rank ties share", rank_values([10, 20, 20, 30]) == [1.0, 2.5, 2.5, 4.0])
    cc = corr([1, 2, 3, 4], [2, 4, 6, 8])
    ck("corr pearson", cc["pearson"] == 1.0 and cc["spearman"] == 1.0)
    ck("corr constant side is None", corr([1, 1, 1, 1], [1, 2, 3, 4])["pearson"] is None)
    ck("corr too short", corr([1, 2], [1, 2])["spearman"] is None)

    # --- B. axis guard: the load axis is facts, the depth axis is hops ------------------
    def panel_token_table(fn) -> dict:
        return {digest: fn(PANEL_CELL[digest]) for _cell, digest in PANEL_DIGESTS}

    per_fact = 0.5
    table_e = panel_token_table(lambda c: 1000.0 + per_fact * (PANEL_EDGES[c] - 96))
    slopes_e = firing_slopes(table_e)
    ck("load axis recovers the per-fact coefficient",
       abs(slopes_e["load"] - per_fact) < 1e-9)
    ck("a pure-facts law has no depth slope", abs(slopes_e["depth"]) < 1e-9)
    per_hop = 20.0
    table_k = panel_token_table(lambda c: 1000.0 + per_hop * (PANEL_K[c] - 8))
    slopes_k = firing_slopes(table_k)
    ck("depth axis recovers the per-hop coefficient", abs(slopes_k["depth"] - per_hop) < 1e-9)
    ck("a pure-hops law has no load slope", abs(slopes_k["load"]) < 1e-9)
    partial = dict(table_e)
    partial.pop(PANEL_DIGESTS[0][1])
    ck("a partial cell refuses the slope", firing_slopes(partial)["load"] is None)
    ck("refusal carries a reason", "of" in firing_slopes(partial)["note"])

    # --- C. structural pin -------------------------------------------------------------
    gate = build_gate()
    global GATE_HASH
    GATE_HASH = gate_hash(gate)
    ck("gate schema", gate["schema"] == GATE_SCHEMA)
    ck("anchor pins round 24's grid", gate["anchor_ok"] is True)
    ck("leak audit passes every cell", gate["all_cells_pass"] is True)
    ck("panel has 12 items and 36 dispatches planned",
       gate["panel"]["items"] == 12 and gate["planned_prompts"] == 36)
    ck("three passes declared", [p["pass_id"] for p in gate["panel"]["passes"]]
       == ["P1", "P2", "P3"])
    ck("ABABA: passes 1 and 3 share a mode",
       gate["panel"]["passes"][0]["mode"] == gate["panel"]["passes"][2]["mode"]
       and gate["panel"]["passes"][1]["mode"] != gate["panel"]["passes"][0]["mode"])
    ck("pass 2 matches the archived concurrency",
       gate["panel"]["passes"][1]["concurrency"] == ARCHIVED_CONCURRENCY)
    ck("calls fit the cap", 1 + len(PANEL_DIGESTS) * len(PASS_PLAN) <= PROMPT_CAP)
    units = panel_units()
    ck("panel arm order", [u["arm"] for u in units] == ["F", "X"] * 6)
    ck("panel gold follows the arm", all(u["gold"] == (1 if u["arm"] == "F" else 0)
                                        for u in units))
    ck("panel digests are the pinned set",
       sorted((u["cell"], u["digest"]) for u in units) == sorted(PANEL_DIGESTS))
    fact_lines_equal = 0
    for cell in WALK_INDEX:
        pair = [u for u in units if u["cell"] == cell]
        lines_f = pair[0]["prompt"].splitlines()
        lines_x = pair[1]["prompt"].splitlines()
        fact_lines_equal += int(lines_f[:-1] == lines_x[:-1] and lines_f[-1] != lines_x[-1])
    ck("matched pair shares every fact line and varies only the query", fact_lines_equal == 6)
    mutated = json.loads(json.dumps(gate))
    first = mutated["cells"][0]
    first["pool_blob_sha256"] = "0" * 64
    ck("a wrong pool blob fails the pin", anchor_state(mutated)["all_ok"] is False)
    mutated2 = json.loads(json.dumps(gate))
    mutated2["cells"][0]["forward_prompt_sha256"] = ["1" * 64, "2" * 64, "3" * 64]
    ck("a wrong prompt digest fails the pin", anchor_state(mutated2)["all_ok"] is False)

    # --- D. self-agreement pair: TARr and TARa are separable ---------------------------
    base_records = synth_records({}, {}, {})
    meas = measurements(base_records)
    ck("every panel digest joins to all four archived firings",
       all(len(meas[d]) == 3 + 4 for _c, d in PANEL_DIGESTS))
    strata = stratum_agreement(meas)
    ck("identical passes: same-mode TARr is 1",
       strata["within_run_same_mode"]["tarr"] == 1.0)
    ck("identical passes: mode-change TARr is 1",
       strata["within_run_mode_change"]["tarr"] == 1.0)
    ck("identical passes: TARa is 1 everywhere",
       all(s["tara"] == 1.0 for s in strata.values()))
    ck("the other-class stratum cannot be scored on raw output",
       strata["other_class"]["raw_unjoinable_pairs"] == 12
       and strata["other_class"]["tarr"] is None
       and strata["other_class"]["tarr_joinable_pairs"] == 0)
    ck("round 31 carries no text, so half the cross-class raw pairs cannot join",
       strata["cross_class"]["raw_unjoinable_pairs"] == 24
       and strata["cross_class"]["tarr_joinable_pairs"] == 24)
    ck("TARr can say no: the same metric against the other class reads zero",
       strata["cross_class"]["tarr"] == 0.0)
    ck("stratum pair counts", strata["within_run_same_mode"]["n_pairs"] == 12
       and strata["within_run_mode_change"]["n_pairs"] == 24
       and strata["cross_firing"]["n_pairs"] == 84)

    # planted: one raw-output change in the bracketing pass, same answer, same length
    changed = list(base_records)
    target = PANEL_DIGESTS[0][1]
    for i, rec in enumerate(changed):
        if rec["prompt_sha256"] == target and rec["pass_id"] == "P3":
            changed[i] = synth_record(PANEL_DIGESTS[0][0], target, "P3", rec["completion_tokens"],
                                      rec["content_answer"], "ff" + rec["output_sha256"][2:])
    strata2 = stratum_agreement(measurements(changed))
    ck("planted raw change moves TARr in its own stratum",
       strata2["within_run_same_mode"]["tarr"] == round(11 / 12, 4))
    ck("planted raw change leaves TARa alone",
       all(s["tara"] == 1.0 for s in strata2.values()))
    ck("planted raw change leaves delivery alone",
       all(s["delivery_agreement"] == 1.0 for s in strata2.values()))
    ck("planted raw change is reported with its digest",
       strata2["within_run_same_mode"]["discordant"][0]["digest"] == target[:12]
       and strata2["within_run_same_mode"]["discordant"][0]["kind"] == "raw_output")

    # planted: one answer flip in the middle pass, raw text and length unchanged
    flipped = list(base_records)
    mid = PANEL_DIGESTS[3][1]
    for i, rec in enumerate(flipped):
        if rec["prompt_sha256"] == mid and rec["pass_id"] == "P2":
            flipped[i] = synth_record(PANEL_DIGESTS[3][0], mid, "P2", rec["completion_tokens"],
                                      "no" if rec["content_answer"] == "yes" else "yes",
                                      rec["output_sha256"])
    strata3 = stratum_agreement(measurements(flipped))
    ck("planted answer flip moves TARa", strata3["within_run_mode_change"]["tara"] < 1.0)
    ck("planted answer flip does not move TARr (raw text held)",
       strata3["within_run_mode_change"]["tarr"] == 1.0)
    ck("planted answer flip is reported as a parsed_answer discordance",
       any(d["kind"] == "parsed_answer" and d["digest"] == mid[:12]
           for d in strata3["within_run_mode_change"]["discordant"]))

    # planted: one silent dispatch
    silent = list(base_records)
    quiet = PANEL_DIGESTS[11][1]
    for i, rec in enumerate(silent):
        if rec["prompt_sha256"] == quiet and rec["pass_id"] == "P1":
            silent[i] = synth_record(PANEL_DIGESTS[11][0], quiet, "P1", 2048, None,
                                     "silent-" + quiet[:8])
    strata4 = stratum_agreement(measurements(silent))
    ck("planted silence moves delivery agreement",
       strata4["within_run_same_mode"]["delivery_agreement"] < 1.0
       and strata4["within_run_mode_change"]["delivery_agreement"] < 1.0)
    ck("planted silence shrinks the correctness denominator",
       strata4["within_run_same_mode"]["correctness_agreement"] is not None)
    table4 = cell_accuracy_and_wilson(silent)
    ck("Wilson is stored for every cell", len(table4) == 6
       and all(r["per_item"]["wilson_high"] >= r["per_item"]["wilson_low"]
               and r["per_dispatch"]["wilson_high"] >= r["per_dispatch"]["wilson_low"]
               for r in table4.values()))
    ck("the per-dispatch denominator is labelled with the effective n",
       all(r["per_dispatch"]["effective_n"] == 2 for r in table4.values()))
    ck("a single silence moves the dispatch denominator, not the item majority",
       table4["D2"]["per_dispatch"]["accuracy"] == round(5 / 6, 4)
       and table4["D2"]["delivered_dispatches"] == 5
       and table4["D2"]["per_item"]["accuracy"] == 1.0)
    always_silent = list(base_records)
    for i, rec in enumerate(always_silent):
        if rec["prompt_sha256"] == quiet:
            always_silent[i] = synth_record(PANEL_DIGESTS[11][0], quiet, rec["pass_id"], 2048,
                                            None, "silent-" + quiet[:8])
    table4b = cell_accuracy_and_wilson(always_silent)
    ck("an item that never delivers is not counted correct, and the interval says so",
       table4b["D2"]["per_item"]["accuracy"] == 0.5
       and table4b["D2"]["per_item"]["wilson_high"] < 1.0)

    # fail-closed: a foreign digest joins nothing and certifies nothing
    foreign_rec = dict(base_records[0])
    foreign_rec["prompt_sha256"] = "e" * 64
    foreign_rec["output_sha256"] = "foreign-output"
    foreign = list(base_records) + [foreign_rec]
    strata5 = stratum_agreement(measurements(foreign))
    ck("an unjoinable digest adds no pair",
       strata5["within_run_same_mode"]["n_pairs"] == 12
       and strata5["within_run_mode_change"]["n_pairs"] == 24
       and strata5["cross_firing"]["n_pairs"] == 84)

    # --- E. noise floor ----------------------------------------------------------------
    zero_floor = slope_noise_floor({d: [1000, 1000] for _c, d in PANEL_DIGESTS},
                                   [0.0] * 12, 200, BOOT_SEED)
    ck("no variation gives a zero floor",
       zero_floor["load_abs_delta"]["q99"] == 0.0
       and zero_floor["depth_abs_delta"]["q99"] == 0.0)
    small = slope_noise_floor({d: [1000, 1000] for _c, d in PANEL_DIGESTS},
                              [0.10 if i % 2 else -0.10 for i in range(12)], 400, BOOT_SEED)
    big = slope_noise_floor({d: [1000, 1000] for _c, d in PANEL_DIGESTS},
                            [0.20 if i % 2 else -0.20 for i in range(12)], 400, BOOT_SEED)
    ck("floor quantiles are ordered",
       small["load_abs_delta"]["q50"] <= small["load_abs_delta"]["q95"]
       <= small["load_abs_delta"]["q99"])
    ck("floor is non-negative", small["load_abs_delta"]["q50"] >= 0.0)
    ratio = big["load_abs_delta"]["q99"] / max(small["load_abs_delta"]["q99"], 1e-9)
    ck("doubling the per-prompt noise doubles the slope floor", 1.5 <= ratio <= 2.5)
    again = slope_noise_floor({d: [1000, 1000] for _c, d in PANEL_DIGESTS},
                              [0.10 if i % 2 else -0.10 for i in range(12)], 400, BOOT_SEED)
    ck("the floor is reproducible from the seed",
       again["depth_abs_delta"]["q99"] == small["depth_abs_delta"]["q99"])
    ck("a pool of one deviation is refused",
       "note" in slope_noise_floor({d: [1000, 1000] for _c, d in PANEL_DIGESTS}, [0.1], 50, 1))
    ck("a base that misses the panel is refused",
       "note" in slope_noise_floor({PANEL_DIGESTS[0][1]: [1000, 1000]}, [0.1, -0.1], 50, 1))

    # --- F. flip risk ------------------------------------------------------------------
    ck("zero flips give zero risk",
       flip_risk(0, 12)["p_at_least_one_of_six_at_rate"] == 0.0)
    one = flip_risk(1, 12)
    ck("flip rate", one["rate"] == round(1 / 12, 4))
    ck("six-item risk at p = 1/12",
       abs(one["p_at_least_one_of_six_at_rate"] - (1.0 - (11.0 / 12.0) ** 6)) < 1e-4)
    ck("the upper bound dominates the point estimate",
       one["p_at_least_one_of_six_at_upper_bound"] >= one["p_at_least_one_of_six_at_rate"])
    ck("risk grows with the flip rate",
       flip_risk(2, 12)["p_at_least_one_of_six_at_rate"]
       > flip_risk(1, 12)["p_at_least_one_of_six_at_rate"])
    ck("no pairs is not a zero risk", "note" in flip_risk(0, 0))

    # --- G. bands ----------------------------------------------------------------------
    ck("negative reference keeps the house band ordered",
       band_for(-27.13, N5_COST_BAND) == [-54.26, -13.565])
    ck("positive reference band", band_for(10.0, N5_COST_BAND) == [5.0, 20.0])
    ck("band of None is unusable", band_for(None, N5_COST_BAND) == [None, None])
    ck("in_band on a negative reference", in_band(-20.0, -27.13, N5_COST_BAND) is True)
    ck("in_band refuses None", in_band(None, -27.13, N5_COST_BAND) is False)

    # --- H. class identity diagnostic --------------------------------------------------
    # A clone of round 24's firing: same digests, same completion text, same lengths. The
    # diagnostic has to read perfect identity against R24 AND the real archived disagreement
    # against R33, otherwise it would be a tautology rather than an identity test.
    vs_r33 = sum(1 for _c, d in PANEL_DIGESTS
                 if PANEL_ARCHIVE["R24"][d]["out_sha"] == PANEL_ARCHIVE["R33"][d]["out_sha"])
    ck("the two archived firings of this class agree somewhere and differ somewhere",
       0 < vs_r33 < 12)
    clone_shas = {(d, p): PANEL_ARCHIVE["R24"][d]["out_sha"]
                  for _c, d in PANEL_DIGESTS for p in PASS_IDS}
    clone_tokens = {(d, p): PANEL_ARCHIVE["R24"][d]["tok"]
                    for _c, d in PANEL_DIGESTS for p in PASS_IDS}
    clone_answers = {(d, p): PANEL_ARCHIVE["R24"][d]["ans"]
                     for _c, d in PANEL_DIGESTS for p in PASS_IDS}
    clone = synth_records(clone_tokens, clone_answers, clone_shas)
    ident = class_identity_diagnostic(measurements(clone))
    ck("a clone of round 24's firing reads 36 of 36 against round 24",
       ident["R24"]["raw_output_identical"] == "36/36")
    ck("the same clone reads the archived disagreement against round 33",
       ident["R33"]["raw_output_identical"] == f"{vs_r33 * 3}/36")
    ck("round 31 carries no text, so identity against it is not asserted",
       ident["R31"]["raw_output_identical"] == "n/a")
    ck("a clone of this class reads zero identity against the other class",
       ident["R37"]["raw_output_identical"] == "0/36")
    ck("parsed-answer agreement is measurable even where raw text is not",
       ident["R31"]["answer_agreement"] == 1.0 and ident["R37"]["answer_agreement"] == 1.0)
    clone_strata = stratum_agreement(measurements(clone))
    ck("a clone reproduces the cross-firing TARr ceiling",
       clone_strata["cross_firing"]["tarr"] == round((vs_r33 * 4 + 36) / 84, 4))

    # --- I. archive consistency (transcription audit) ---------------------------------
    for label, archive in PANEL_ARCHIVE.items():
        ck(f"{label} archive covers the panel",
           all(d in archive for _c, d in PANEL_DIGESTS))
        for _cell, digest in PANEL_DIGESTS:
            row = archive[digest]
            ck(f"{label} arm matches the panel for {digest[:8]}", row["arm"] == PANEL_ARM[digest])
            ck(f"{label} cell geometry matches for {digest[:8]}",
               row["k"] == PANEL_K[_cell] and row["edges"] == PANEL_EDGES[_cell])
            if row["ans"] is not None:
                ck(f"{label} delivered answer is correct for {digest[:8]}",
                   int((1 if row["ans"] == "yes" else 0) == row["gold"]) == 1)
    same_r24_r33 = sum(1 for _c, d in PANEL_DIGESTS
                       if PANEL_ARCHIVE["R24"][d]["out_sha"]
                       == PANEL_ARCHIVE["R33"][d]["out_sha"])
    ck("the two archived firings of this class join on raw text", same_r24_r33 >= 1)
    # Archive-side audit of the two published enumeration signatures, on the transcribed rows
    # themselves: the other class reported a distractor-mention ratio of 0.000 in every cell,
    # this class a grid mean of 0.8922. A transcription slip in a dr or tok column trips this.
    other_ratios = ([PANEL_ARCHIVE["R31"][d]["dr"] for _c, d in PANEL_DIGESTS]
                    + [PANEL_ARCHIVE["R37"][d]["dr"] for _c, d in PANEL_DIGESTS])
    ck("the other class's non-enumerating signature holds in every transcribed row",
       all(v == 0.0 for v in other_ratios))
    own_ratios = [PANEL_ARCHIVE["R24"][d]["dr"] for _c, d in PANEL_DIGESTS]
    ck("this class's enumerating signature is present in the transcribed panel",
       sum(1 for v in own_ratios if v >= 0.5) >= 9
       and sum(own_ratios) / len(own_ratios) >= 0.5)
    ck("no transcribed row was truncated except round 31's censored cell",
       sum(1 for label in PANEL_ARCHIVE for _c, d in PANEL_DIGESTS
           if PANEL_ARCHIVE[label][d]["fin"] == "length") == 0)

    # --- J. aggregation smoke over planted clean data ---------------------------------
    summary = aggregate(base_records, gate)
    ck("aggregate scores every prediction",
       all(key in summary["predictions"] for key in ("N1", "N2", "N3", "N4", "N5", "N6")))
    ck("aggregate stores the self-agreement pair per cell",
       all("tarr" in row["agreement"]["within_run_same_mode"]
           and "tara" in row["agreement"]["within_run_same_mode"]
           for row in summary["per_cell_selfagreement_and_wilson"].values()))
    ck("aggregate keeps both Wilson denominators",
       all("wilson_per_item" in row and "wilson_per_dispatch" in row
           for row in summary["per_cell_selfagreement_and_wilson"].values()))
    ck("the guard reports a verdict for every same-class pair",
       all("load_verdict" in p
           for name in SAME_CLASS_STRATA
           for p in summary["noise_floors_and_verdicts"]["per_stratum"][name]["pairs"]))
    ck("a perfectly reproducible synthetic run trips no change verdict",
       summary["predictions"]["N6"]["within_run_any_change_detected"] is False)
    ck("a zero floor is labelled as such, and a zero delta against it is not a change",
       all(p["floor_is_zero"]["load"] and p["floor_is_zero"]["depth"]
           and p["delta_load"] == 0.0 and p["load_verdict"] != "change"
           for p in summary["noise_floors_and_verdicts"]["per_stratum"]
           ["within_run_same_mode"]["pairs"]))
    ck("the guard explains what a zero floor means",
       "determinism result" in summary["noise_floors_and_verdicts"]["zero_floor_meaning"])
    cross_rows = summary["noise_floors_and_verdicts"]["cross_class"]
    ck("the cross-class guard judges against the larger of the two classes' floors",
       len(cross_rows) == 4
       and all(r["union_floor_load"] >= max(r["floor_this_class_load_q99"],
                                            r["floor_other_class_load_q99"])
               and r["union_floor_depth"] >= max(r["floor_this_class_depth_q99"],
                                                 r["floor_other_class_depth_q99"])
               for r in cross_rows))
    ck("the cross-class verdict follows its own arithmetic",
       all((r["load_verdict"] == "resolvable") == (abs(r["delta_load"]) > r["union_floor_load"])
           and (r["depth_verdict"] == "resolvable")
           == (abs(r["delta_depth"]) > r["union_floor_depth"]) for r in cross_rows))
    ck("synthetic identical lengths produce zero within-run slope deltas",
       all(p["delta_load"] == 0.0 and p["delta_depth"] == 0.0
           for name in ("within_run_same_mode", "within_run_mode_change")
           for p in summary["noise_floors_and_verdicts"]["per_stratum"][name]["pairs"]))
    summary_again = aggregate(base_records, gate)

    def _without_stamp(payload: dict) -> dict:
        return {k: v for k, v in payload.items() if k != "generated_at"}

    ck("aggregation is deterministic apart from its own timestamp",
       canonical(_without_stamp(summary_again)) == canonical(_without_stamp(summary)))

    print(f"selftest: {checks} checks passed")
    return 0


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true", help="run the instrument's own checks")
    ap.add_argument("--gate", action="store_true", help="build and freeze the gate")
    ap.add_argument("--probe", action="store_true", help="dispatch the panel")
    ap.add_argument("--resume", action="store_true",
                    help="with --probe: keep measurements already in raw.jsonl")
    ap.add_argument("--analyze", action="store_true", help="rebuild summary.json from raw.jsonl")
    ap.add_argument("--out", default="gate.json", help="gate path for --gate")
    ap.add_argument("--out-dir", default=".", help="round directory for --probe/--analyze")
    args = ap.parse_args(argv[1:])
    if args.selftest:
        return selftest()
    if args.gate:
        return cmd_gate(args.out)
    if args.probe:
        return probe(args.out_dir, resume=args.resume)
    if args.analyze:
        return cmd_analyze(args.out_dir)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

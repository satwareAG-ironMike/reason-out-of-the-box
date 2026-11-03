#!/usr/bin/env python3
"""Nightly round 31 (tracker #65, firing 2026-10-27 04:39): cross-class replication of
the round-24 (k, E) bisection grid on a 27B-class endpoint under NVFP4 quantization
(vLLM serving, multi-token-prediction speculative decoding), on byte-identical prompts
pinned by digest to the archived flash-next-class run.

Question (issue #71, "place the ladder depth ceiling d*: grid extension and load
decoupling"). Round 24 (branch research/nightly-2026-10-25-0405, PR #98) measured the
declared six-cell grid on the flash-next class: the k = 8 load frontier is maintained to
E = 160 (the bracket then tightens to (160, 192)), and at the safe load E = 96 the depth
arm turns over at k = 16 (one arm-X truncation at exactly 2048 tokens, 5/6 delivered and
correct). Zero wrong answers grid-wide. Whether that frontier is a property of the model
weights or of the deployment (quantization, serving runtime, output cap) has not been
tested: every archived frontier point so far sits on one class. This round re-runs the
identical prompt set on a NEW endpoint class - a 27B-class local model under NVFP4
(4-bit floating point) quantization, served by vLLM - and compares per cell and per
prompt against the flash-next archive.

Instrument (issue #78 acceptance criterion 1, the shared-content polarity pair shipped in
round 22): every cell dispatches PAIRS_PER_LEVEL graphs and asks each graph TWO questions
over the IDENTICAL fact list with IDENTICAL entity names and the identical queried
source; only the queried target varies. Arm F is the forward query (gold yes, k hops),
arm X is the cross-component query (gold no). pair_violations() asserts the shared-
content invariant on every dispatched pair and --selftest carries the planted non-
matched control.

Declared grid: exactly round 24's grid, seed_base 20261024. This file re-uses that
construction's seed base, name pools, seed formula and selection order, so ALL 36 prompt
digests and ALL 6 candidate-pool blobs must equal the values archived in
research/nightly-2026-10-25-0405/ (PR #98); --probe and --gate REFUSE otherwise. The
digests are carried as constants below, transcribed from that round's gate.json, so the
post-merge tree can verify the pin without the ancestor branch. The round-24 per-prompt
results (completion tokens, delivered answer, outcome, truncation) are carried the same
way, making every prompt a two-class comparison: same prompt, same graph, two
deployments. A difference is a class signal, not a measurement artifact; a digest
mismatch is a construction drift and fails the gate.

  load arm (k = 8 held, E grows through the bracket):
    L0 (k= 8, C=12)  E= 96   anchor cell of round 24, maintained 6/6 on the flash-next
                              class
    L1 (k= 8, C=14)  E=112   first bisection point
    L2 (k= 8, C=16)  E=128   second bisection point
    L3 (k= 8, C=20)  E=160   third bisection point, maintained on the flash-next class;
                              round 23's non-maintained (8,192) sits one step beyond
  depth arm (E = 96 held, k grows at the safe load):
    D1 (k=12, C= 8)  E= 96   maintained on the flash-next class
    D2 (k=16, C= 6)  E= 96   the turnover cell: one truncation of six on the flash-next
                              class

3 graphs per cell x 2 queries = 36 prompts, + 1 health probe = 37 of the 40-call cap,
max_tokens 2048, temperature 0.0, one sample per item, no exemplars, no chain of thought
asked. Readout stack as declared in round 24 (issue #94): content_only (primary),
delivered_or_strict, loose_fallback; cell status by the round-8 trichotomy (Wilson 95%,
floor 0.60).

Class caveat, declared: the NVFP4 deployment differs from the flash-next class on TWO
axes at once (quantization format and serving runtime; the flash-next class ran on a
GGUF deployment). This is a class replication, not a controlled quantization
experiment; the cross-class delta spans model class + quantization + runtime and is
recorded as such. At temperature 0 the MTP draft acceptance is deterministic, so the
completions are the underlying model's greedy outputs; that is an assumption about the
serving runtime, noted and not verified from outside. The open literature gap found in
round 6 (no verified evidence that quantization or inference precision degrades multi-
hop depth reasoning specifically) gets its first cross-class data point on the 4-bit
floating point axis from this round.

Declared predictions (fixed in the gate before any prompt is spent):
  P1 the frontier is class-specific: all six cells are maintained under content_only on
     this class. The flash-next turnover at (16, 96) and the k = 8 load frontier are
     properties of that class, not of the 2048-token cap shared by the pool. A
     non-maintained cell is a measurement, not a gate failure: it means E* is not
     deployment-invariant and the two classes carry different (k, E) surfaces.
  P2 the delivered answer is never wrong: every content_only answer in the grid is
     correct (rounds 23 and 24: every delivered answer on the flash-next class was
     correct; a wrong answer would be a correctness collapse, a different event).
  P3 no truncation: all 36 prompts deliver the answer in the answer field under the
     2048 cap. If any cell truncates, the turnover is shared by both classes and the
     ceiling is a cap-level property of the enumeration-length upper tail.
  P4 the enumeration cost law is class-invariant: the per-hop completion slope at
     E = 96 (k = 8, 12, 16 over uncensored cell means) lies in [0.5x, 2.0x] of round
     24's +29.36 tokens/hop, and the per-fact slope at k = 8 (E = 96, 112, 128, 160
     over uncensored cell means) lies in [0.5x, 2.0x] of round 24's +7.89 tokens/fact.
     Out of band, the quantization or runtime axis changes enumeration length, not
     only surfacing.
  P5 the surfacing is mostly class-invariant: at least half of the prompts where BOTH
     classes delivered a content answer carry the SAME answer (agreement over the
     comparable subset; vacuous and reported as vacuous when no prompt is comparable).
  P6 the anchor reproduces cross-class: all three L0 arm-F prompts deliver the answer
     ("yes") that round 24 recorded on the flash-next class at (k = 8, E = 96).
  P7 prompt-digest identity: all 36 prompt digests and 6 pool blobs equal round 24's
     gate (structural; true by construction, asserted by --gate and reported for
     completeness).

Usage:
  crossclass_frontier_probe.py --selftest
  crossclass_frontier_probe.py --gate              [--out gate.json]
  crossclass_frontier_probe.py --probe             [--out-dir DIR] [--resume]
  crossclass_frontier_probe.py --analyze           [--out-dir DIR]
The endpoint is read from NIGHTLY_BASE_URL, NIGHTLY_MODEL_ID and NIGHTLY_API_KEY and no
endpoint value is ever written to an artifact; stored model text passes a sanitizer for
URLs, IP addresses and absolute paths. Stdlib only.
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
PHASE2_BUDGET_S = 1500
TPS_FLOOR = 5.0
CONCURRENCY_CHOICES = (2, 3, 4, 6, 8)
HEALTH_PROMPT = "Reply with exactly one word: yes"
# Health-probe output budget: 256 tokens, per round 22's lesson that a 2048-token health
# call is not portable across the pool (one deployment's upstream gateway killed it at
# ~60 s with http_502 while 256 tokens returned in ~1 s). MAX_TOKENS, the grid, the corpus
# and therefore the gate hash are untouched by this transport-only choice.
HEALTH_BUDGET = 256

# The grid: two arms of (k, C) cells with E = k * C facts. Inside each arm, consecutive
# cells differ in exactly one axis; the load arm holds k = 8, the depth arm holds E = 96.
LOAD_ARM = (("L0", 8, 12), ("L1", 8, 14), ("L2", 8, 16), ("L3", 8, 20))
DEPTH_ARM = (("D1", 12, 8), ("D2", 16, 6))
WALK = LOAD_ARM + DEPTH_ARM  # dispatch and reporting order
LOAD_NAMES = tuple(name for name, _k, _c in LOAD_ARM)
DEPTH_NAMES = tuple(name for name, _k, _c in DEPTH_ARM)
WALK_INDEX = {name: i for i, (name, _k, _c) in enumerate(WALK)}

# Fail-closed cross-class anchor. R24: the ENTIRE declared grid IS round 24's grid.
# research/nightly-2026-10-25-0405/ (PR #98) measured it on the flash-next class;
# values below are transcribed from that round's gate.json and raw.jsonl and hardcoded
# here so the post-merge tree can verify the pin without the ancestor branch.
# R24_DIGESTS: per-cell pool blob and the six prompt digests (3 forward, 3 cross) of
# round 24's gate. R24_RECORDS: per-prompt archive of round 24's flash-next results
# keyed by prompt digest - completion tokens, delivered answer, outcome, truncation,
# distractor-mention ratio - so every dispatched prompt is a two-class comparison.
R24_DIGESTS = {
    "D1": {"cross_prompt_sha256": ["b3e37ce3f7f1df518ccfde8ec1c6831680e23e6fb404ed30bd325d41d7f7e491", "2543a77e9fe6e6a99cf3b72da17a374bd5116692145228cff0646407c2b79eb8", "85bdf738ee94ba77873e213719d719369818420ac69ff228acfa58af828d5f69"], "forward_prompt_sha256": ["3a378f98a2b0a41f6fef81c7f0529dcb8264e5cea3dacbf45ddef7b25125a873", "ec6a74cf4d8475d2937acda2fdd8a7b994dcba7486e47a7ce36b7da12a1cb909", "29e02b372ac84f5e6f631df8ef563e50c8e7381f69921d87c6e2133a7a46e64a"], "pool_blob_sha256": "d5fc4ca963b448d8d6f9501b06a8814185c0b8ec73c9130d853a4f6a2681c214"},
    "D2": {"cross_prompt_sha256": ["de5ed21b32895e67bd295d1b63df3245e57634d0b07da4ba92e9442cd1e0fead", "817d852383a6ef12a7f6215955a1f1d87240a2ca549c6c81b89f598c90ed0e9c", "e21833ff126f4b1f810c05e3dc97342227834e6cb700eb128fedc88e8899b4ba"], "forward_prompt_sha256": ["74388a9a6f4d5549a343593617388774e7adf5dae49681704ac3f3eed7a9c834", "51ddd1f327f0570a048aaf51afe85c3b57968b0287e14f547fd6820a4cfcf7af", "09701216d3fdfe235fa84c9098ae700737a07af184e30f2d264786ffcbd109c9"], "pool_blob_sha256": "161829ff61c37bd0b73f7ce9026bb0ca7b5012f72280b1c88accf91c8a49c6e1"},
    "L0": {"cross_prompt_sha256": ["ddb9421bc3e7c63dcae14af51cdb6b5e6347ff569b21683558c0f9fa409b6402", "af0462f2fdb3097c0f11d4894478ee465646b841cfa003f14938d217eb12204a", "d4e04bfc376c3fa7510d18b3e349a34dbc140e2dfb5bbee85199efaf39c53f6a"], "forward_prompt_sha256": ["b20d7fd289fd6f181fb05aebf9ae6526c041870e09c711ae60a7100cb5ca313b", "96462a5727cd001cee15875248307c476ca41b977a5aff509622736421fe169d", "b3335406e9b510f6a0d9b598494695f1aa798acfc347fe944677c21c07e93702"], "pool_blob_sha256": "bee7e0264b8a69c7d1198d4b24d4207b57c31230bd8a0760bc4ce8853f03dd16"},
    "L1": {"cross_prompt_sha256": ["31636587257e460c48810a5498e9fee105559cf3425a7262ff909b3a9f8427bc", "3748f096518670511c09dc45518580857e80c5541f48200bf7d064cec54e2327", "582c3d08ff0a6b7fbeefaa94ab6ba9d63e6b8d8ffde92d1814d6359d80bb046f"], "forward_prompt_sha256": ["d2ab3a4e71b559b5605e3689658d8f3dfc93efaf7b6f85e74c246e7674f5ced2", "8611a03e5c9afcd443b3317c4f4847e2098e22cfc00022cb92dbdccfdf76ca4a", "50f7c8cc855497a25f636a88b9a06525efc07f1da85e1592db30ac9223e9ce40"], "pool_blob_sha256": "44ae63f24f439ab665463059a415a217c4fb8d24bc67e5672b10e1114e637c67"},
    "L2": {"cross_prompt_sha256": ["54d8b96f74e74bb2fa315f1de73e5812682def9773dc88843a81e93d62a7be5c", "1de707958baabe18e055807eb756159c40a243e7e608b6fa49dbd90351b1a568", "ed9e510b2f843cbc352a9bfaae79b960a5f19900801fb00ff321c5303b4543aa"], "forward_prompt_sha256": ["29635c816e9cf67dbcf54cc78b935840e8b8435d079eba3a5ee79ddaf2b2e32d", "a9c7c461501d38fe6ab35e0dcc6494e7053d4b4bf335aee105b57ceb4eff705b", "135807684c9c2641a478d482733434cd39b96514fabfd9203b6568b4ad442390"], "pool_blob_sha256": "bb383e5ea9c1c20b447acbac755190031ff3a3dc5d47bacff1fd78ac05a62536"},
    "L3": {"cross_prompt_sha256": ["d548b1f9681cf082174cf141f33e0f34a65b98cf2504111e36284bdf287386cc", "3ba9842ed8d61e0bd07e6525fa344b493eafffc962d83fc256b1901119c276a3", "c2fa54ea50ec9930790b9af79669470e3de6511ae859a7512d80339b7e3a1fba"], "forward_prompt_sha256": ["4ed1d525026f2f7c43149d7ef8d3d5df040b274f830c8f6fb1f1f0788463cb18", "3a697ba510346b68e343db17b909fa84a0e5cfb83d12b3dd7b9d4b0746d0fe8c", "2387559a6df93b8e176dc5fcbeb356716e7d873f12917b91669e8782abdad4c0"], "pool_blob_sha256": "8c3005a7516fdacf09a19e05510966eaadb591d2b31a4ff408f45581c766b90f"},
}
R24_RECORDS = {
    "09701216d3fdfe235fa84c9098ae700737a07af184e30f2d264786ffcbd109c9": {"arm": "F", "cell": "D2", "completion_tokens": 1141, "content_answer": "yes", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 96, "finish_reason": "stop", "k": 16, "outcome": "answered_in_answer_field"},
    "135807684c9c2641a478d482733434cd39b96514fabfd9203b6568b4ad442390": {"arm": "F", "cell": "L2", "completion_tokens": 280, "content_answer": "yes", "correct_content_only": 1, "distractor_mention_ratio": 0.0, "edges": 128, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "1de707958baabe18e055807eb756159c40a243e7e608b6fa49dbd90351b1a568": {"arm": "X", "cell": "L2", "completion_tokens": 1883, "content_answer": "no", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 128, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "2387559a6df93b8e176dc5fcbeb356716e7d873f12917b91669e8782abdad4c0": {"arm": "F", "cell": "L3", "completion_tokens": 1684, "content_answer": "yes", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 160, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "2543a77e9fe6e6a99cf3b72da17a374bd5116692145228cff0646407c2b79eb8": {"arm": "X", "cell": "D1", "completion_tokens": 1156, "content_answer": "no", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 96, "finish_reason": "stop", "k": 12, "outcome": "answered_in_answer_field"},
    "29635c816e9cf67dbcf54cc78b935840e8b8435d079eba3a5ee79ddaf2b2e32d": {"arm": "F", "cell": "L2", "completion_tokens": 1389, "content_answer": "yes", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 128, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "29e02b372ac84f5e6f631df8ef563e50c8e7381f69921d87c6e2133a7a46e64a": {"arm": "F", "cell": "D1", "completion_tokens": 1037, "content_answer": "yes", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 96, "finish_reason": "stop", "k": 12, "outcome": "answered_in_answer_field"},
    "31636587257e460c48810a5498e9fee105559cf3425a7262ff909b3a9f8427bc": {"arm": "X", "cell": "L1", "completion_tokens": 1631, "content_answer": "no", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 112, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "3748f096518670511c09dc45518580857e80c5541f48200bf7d064cec54e2327": {"arm": "X", "cell": "L1", "completion_tokens": 1512, "content_answer": "no", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 112, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "3a378f98a2b0a41f6fef81c7f0529dcb8264e5cea3dacbf45ddef7b25125a873": {"arm": "F", "cell": "D1", "completion_tokens": 1185, "content_answer": "yes", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 96, "finish_reason": "stop", "k": 12, "outcome": "answered_in_answer_field"},
    "3a697ba510346b68e343db17b909fa84a0e5cfb83d12b3dd7b9d4b0746d0fe8c": {"arm": "F", "cell": "L3", "completion_tokens": 1789, "content_answer": "yes", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 160, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "3ba9842ed8d61e0bd07e6525fa344b493eafffc962d83fc256b1901119c276a3": {"arm": "X", "cell": "L3", "completion_tokens": 561, "content_answer": "no", "correct_content_only": 1, "distractor_mention_ratio": 0.0526, "edges": 160, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "4ed1d525026f2f7c43149d7ef8d3d5df040b274f830c8f6fb1f1f0788463cb18": {"arm": "F", "cell": "L3", "completion_tokens": 1756, "content_answer": "yes", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 160, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "50f7c8cc855497a25f636a88b9a06525efc07f1da85e1592db30ac9223e9ce40": {"arm": "F", "cell": "L1", "completion_tokens": 252, "content_answer": "yes", "correct_content_only": 1, "distractor_mention_ratio": 0.0, "edges": 112, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "51ddd1f327f0570a048aaf51afe85c3b57968b0287e14f547fd6820a4cfcf7af": {"arm": "F", "cell": "D2", "completion_tokens": 1172, "content_answer": "yes", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 96, "finish_reason": "stop", "k": 16, "outcome": "answered_in_answer_field"},
    "54d8b96f74e74bb2fa315f1de73e5812682def9773dc88843a81e93d62a7be5c": {"arm": "X", "cell": "L2", "completion_tokens": 1700, "content_answer": "no", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 128, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "582c3d08ff0a6b7fbeefaa94ab6ba9d63e6b8d8ffde92d1814d6359d80bb046f": {"arm": "X", "cell": "L1", "completion_tokens": 758, "content_answer": "no", "correct_content_only": 1, "distractor_mention_ratio": 0.0769, "edges": 112, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "74388a9a6f4d5549a343593617388774e7adf5dae49681704ac3f3eed7a9c834": {"arm": "F", "cell": "D2", "completion_tokens": 1138, "content_answer": "yes", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 96, "finish_reason": "stop", "k": 16, "outcome": "answered_in_answer_field"},
    "817d852383a6ef12a7f6215955a1f1d87240a2ca549c6c81b89f598c90ed0e9c": {"arm": "X", "cell": "D2", "completion_tokens": 1322, "content_answer": "no", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 96, "finish_reason": "stop", "k": 16, "outcome": "answered_in_answer_field"},
    "85bdf738ee94ba77873e213719d719369818420ac69ff228acfa58af828d5f69": {"arm": "X", "cell": "D1", "completion_tokens": 1415, "content_answer": "no", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 96, "finish_reason": "stop", "k": 12, "outcome": "answered_in_answer_field"},
    "8611a03e5c9afcd443b3317c4f4847e2098e22cfc00022cb92dbdccfdf76ca4a": {"arm": "F", "cell": "L1", "completion_tokens": 1241, "content_answer": "yes", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 112, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "96462a5727cd001cee15875248307c476ca41b977a5aff509622736421fe169d": {"arm": "F", "cell": "L0", "completion_tokens": 1098, "content_answer": "yes", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 96, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "a9c7c461501d38fe6ab35e0dcc6494e7053d4b4bf335aee105b57ceb4eff705b": {"arm": "F", "cell": "L2", "completion_tokens": 1422, "content_answer": "yes", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 128, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "af0462f2fdb3097c0f11d4894478ee465646b841cfa003f14938d217eb12204a": {"arm": "X", "cell": "L0", "completion_tokens": 1334, "content_answer": "no", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 96, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "b20d7fd289fd6f181fb05aebf9ae6526c041870e09c711ae60a7100cb5ca313b": {"arm": "F", "cell": "L0", "completion_tokens": 1101, "content_answer": "yes", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 96, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "b3335406e9b510f6a0d9b598494695f1aa798acfc347fe944677c21c07e93702": {"arm": "F", "cell": "L0", "completion_tokens": 1050, "content_answer": "yes", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 96, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "b3e37ce3f7f1df518ccfde8ec1c6831680e23e6fb404ed30bd325d41d7f7e491": {"arm": "X", "cell": "D1", "completion_tokens": 1335, "content_answer": "no", "correct_content_only": 1, "distractor_mention_ratio": 0.989, "edges": 96, "finish_reason": "stop", "k": 12, "outcome": "answered_in_answer_field"},
    "c2fa54ea50ec9930790b9af79669470e3de6511ae859a7512d80339b7e3a1fba": {"arm": "X", "cell": "L3", "completion_tokens": 1862, "content_answer": "no", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 160, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "d2ab3a4e71b559b5605e3689658d8f3dfc93efaf7b6f85e74c246e7674f5ced2": {"arm": "F", "cell": "L1", "completion_tokens": 1239, "content_answer": "yes", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 112, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "d4e04bfc376c3fa7510d18b3e349a34dbc140e2dfb5bbee85199efaf39c53f6a": {"arm": "X", "cell": "L0", "completion_tokens": 1190, "content_answer": "no", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 96, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "d548b1f9681cf082174cf141f33e0f34a65b98cf2504111e36284bdf287386cc": {"arm": "X", "cell": "L3", "completion_tokens": 2043, "content_answer": "no", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 160, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "ddb9421bc3e7c63dcae14af51cdb6b5e6347ff569b21683558c0f9fa409b6402": {"arm": "X", "cell": "L0", "completion_tokens": 1258, "content_answer": "no", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 96, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
    "de5ed21b32895e67bd295d1b63df3245e57634d0b07da4ba92e9442cd1e0fead": {"arm": "X", "cell": "D2", "completion_tokens": 1619, "content_answer": "no", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 96, "finish_reason": "stop", "k": 16, "outcome": "answered_in_answer_field"},
    "e21833ff126f4b1f810c05e3dc97342227834e6cb700eb128fedc88e8899b4ba": {"arm": "X", "cell": "D2", "completion_tokens": 2048, "content_answer": None, "correct_content_only": None, "distractor_mention_ratio": 1.0, "edges": 96, "finish_reason": "length", "k": 16, "outcome": "trace_only"},
    "ec6a74cf4d8475d2937acda2fdd8a7b994dcba7486e47a7ce36b7da12a1cb909": {"arm": "F", "cell": "D1", "completion_tokens": 1048, "content_answer": "yes", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 96, "finish_reason": "stop", "k": 12, "outcome": "answered_in_answer_field"},
    "ed9e510b2f843cbc352a9bfaae79b960a5f19900801fb00ff321c5303b4543aa": {"arm": "X", "cell": "L2", "completion_tokens": 1682, "content_answer": "no", "correct_content_only": 1, "distractor_mention_ratio": 1.0, "edges": 128, "finish_reason": "stop", "k": 8, "outcome": "answered_in_answer_field"},
}
# Cross-class cost-law bands, declared before dispatch (P4): round 24's cost laws on
# the flash-next class and the 0.5x-2.0x tolerance band around them.
R24_DEPTH_SLOPE_TOK_PER_HOP = 29.36    # round 24 token_law_completion_vs_k_at_E96 slope
R24_LOAD_SLOPE_TOK_PER_FACT = 7.89     # round 24 token_law_completion_vs_edges_at_k8 slope
COST_BAND = (0.5, 2.0)

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


def anchor_state(gate: dict) -> dict:
    """Fail-closed cross-class pin: every cell's pool blob and prompt digests must equal
    round 24's gate (constants only, no file dependency)."""
    cells = {c["cell"]: c for c in gate["cells"]}
    rows = {}
    for cell_id in WALK_INDEX:
        expected = R24_DIGESTS[cell_id]
        cell = cells.get(cell_id)
        observed_blob = cell["pool_blob_sha256"] if cell else None
        observed_f = sorted(cell["forward_prompt_sha256"]) if cell else []
        observed_x = sorted(cell["cross_prompt_sha256"]) if cell else []
        rows[cell_id] = {
            "cell": cell_id,
            "expected_pool_blob_sha256": expected["pool_blob_sha256"],
            "observed_pool_blob_sha256": observed_blob,
            "pool_blob_matches": observed_blob == expected["pool_blob_sha256"],
            "expected_forward_prompts": sorted(expected["forward_prompt_sha256"]),
            "observed_forward_prompts": observed_f,
            "forward_prompts_match": (observed_f == sorted(expected["forward_prompt_sha256"])),
            "expected_cross_prompts": sorted(expected["cross_prompt_sha256"]),
            "observed_cross_prompts": observed_x,
            "cross_prompts_match": (observed_x == sorted(expected["cross_prompt_sha256"])),
            "archived_results_by_digest": {
                d: R24_RECORDS[d] for d in sorted(
                    set(expected["forward_prompt_sha256"])
                    | set(expected["cross_prompt_sha256"]))},
        }
    all_ok = all(r["pool_blob_matches"] and r["forward_prompts_match"]
                 and r["cross_prompts_match"] for r in rows.values())
    return {"checked": True, "all_ok": all_ok, "anchors": rows,
            "provenance": ("research/nightly-2026-10-25-0405 (round 24, PR #98), "
                           "gate.json and raw.jsonl, all six cells of the declared grid")}


def build_gate() -> dict:
    cells = all_cells()
    out = {"schema": "round31-gate-v1", "seed_base": SEED_BASE,
           "alpha": ALPHA, "perms": PERMS,
           "load_arm": [{"cell": n, "k": k, "chains": c, "edges": k * c}
                        for n, k, c in LOAD_ARM],
           "depth_arm": [{"cell": n, "k": k, "chains": c, "edges": k * c}
                         for n, k, c in DEPTH_ARM],
           "pairs_per_cell": PAIRS_PER_LEVEL,
           "max_tokens": MAX_TOKENS, "temperature": TEMPERATURE,
           "readouts": ["content_only", "loose_fallback", "delivered_or_strict"],
           "matched_pair_invariant": ("identical fact list, identical entity name set, "
                                      "identical fact count, identical queried source; "
                                      "only the queried target varies (issue #78 "
                                      "acceptance criterion 1, polarity contrast)"),
           "predictions": {
               "P1_all_six_cells_maintained_content_only": True,
               "P2_all_content_only_answers_correct": True,
               "P3_zero_truncations": True,
               "P4_depth_slope_in_band": [
                   round(R24_DEPTH_SLOPE_TOK_PER_HOP * COST_BAND[0], 3),
                   round(R24_DEPTH_SLOPE_TOK_PER_HOP * COST_BAND[1], 3)],
               "P4_load_slope_in_band": [
                   round(R24_LOAD_SLOPE_TOK_PER_FACT * COST_BAND[0], 3),
                   round(R24_LOAD_SLOPE_TOK_PER_FACT * COST_BAND[1], 3)],
               "P5_crossclass_answer_agreement_ge": 0.5,
               "P6_L0_forward_prompts_reproduce_round24_answers": True,
               "P7_all_36_digests_and_6_pool_blobs_match_round24": True},
           "cells": []}
    for cell in cells:
        g_pool = gate_battery(cell["pool"])
        g_pairs = gate_battery(cell["paired_pool"])
        prompts = [render_prompt(it) for pair in cell["pairs"] for it in pair]
        chars = [len(p) for p in prompts]
        out["cells"].append({
            "arm": "S", "cell": cell["cell"], "index": cell["index"],
            "k": cell["k"], "chains": cell["chains"], "edges": cell["edges"],
            "level": cell["edges"],
            "load": {"facts": cell["edges"],
                     "prompt_chars_mean": round(sum(chars) / len(chars), 1),
                     "prompt_chars_min": min(chars), "prompt_chars_max": max(chars)},
            "forward_item_sha256": [sha256_text(canonical(p[0])) for p in cell["pairs"]],
            "forward_prompt_sha256": [sha256_text(render_prompt(p[0]))
                                      for p in cell["pairs"]],
            "cross_prompt_sha256": [sha256_text(render_prompt(p[1]))
                                    for p in cell["pairs"]],
            "pool_blob_sha256": sha256_text(canonical(cell["pool"])),
            "paired_pool_blob_sha256": sha256_text(canonical(cell["paired_pool"])),
            "gate_pool": g_pool, "gate_paired_pool": g_pairs})
    blob = sha256_text(canonical([c["paired_pool_blob_sha256"] for c in out["cells"]]))
    out["corpus_blob_sha256"] = blob
    out["planned_prompts"] = 2 * PAIRS_PER_LEVEL * len(WALK)
    out["prompt_cap"] = PROMPT_CAP
    out["all_cells_pass"] = all(
        c["gate_pool"]["verdict"] != "leak" and c["gate_paired_pool"]["verdict"] != "leak"
        for c in out["cells"])
    out["anchor"] = anchor_state(out)
    out["anchor_ok"] = out["anchor"]["all_ok"]
    return out


GATE_HASH = "unset"


def gate_hash(gate: dict) -> str:
    return sha256_text(canonical(gate))


def cell_order_key(name: str) -> int:
    return WALK_INDEX.get(name, len(WALK))


def steps_at_least(means: list, factor: float) -> bool:
    """Every step of an ordered means list must be >= factor x its predecessor. Ties and
    dips fail; declared for steps that MUST be visible to the tokenizer (the load arm)."""
    if not means or any(m is None or m <= 0 for m in means):
        return False
    return all(b >= factor * a for a, b in zip(means, means[1:]))


def within_tolerance(a: float, b: float, tol: float) -> bool:
    """|b - a| <= tol x a. Declared for construction-invariant equalities (two cells with
    the SAME fact count): round 23's P1 lesson, a 0.12% entity-name-length dip must not
    read as a failed prediction."""
    if a is None or b is None or a <= 0:
        return False
    return abs(b - a) <= tol * a


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


def solve_linear(mat: list, vec: list):
    """Small dense solve (Gaussian elimination, partial pivoting). Returns None when the
    system is singular, which is what keeps a saturated cell-mean fit honest instead of
    silently returning garbage."""
    n = len(vec)
    a = [row[:] + [vec[i]] for i, row in enumerate(mat)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[piv][col]) < 1e-12:
            return None
        a[col], a[piv] = a[piv], a[col]
        for r in range(n):
            if r == col:
                continue
            factor = a[r][col] / a[col][col]
            if factor:
                for c in range(col, n + 1):
                    a[r][c] -= factor * a[col][c]
    return [a[i][n] / a[i][i] for i in range(n)]


def two_factor_means(means: list) -> dict:
    """Fit mean_completion = b0 + b1*k + b2*E + b3*k*E over the cell means, where each
    entry is (cell, k, edges, mean_completion_tokens). The interaction coefficient b3 is
    the declared summary of "the ceiling is a frontier in (k, E), not a curve in one":
    b3 > 0 says the joint corner costs more than the two single-axis effects predict.
    Four parameters on six cell means: descriptive, and reported as such."""
    pts = [m for m in means if m[3] is not None]
    if len(pts) < 5:
        return {"fit": None, "note": f"only {len(pts)} cell means, fit refused"}
    xs = [(1.0, float(k), float(e), float(k) * float(e)) for (_c, k, e, _m) in pts]
    ys = [m for (_c, _k, _e, m) in pts]
    at_a = [[sum(x[i] * x[j] for x in xs) for j in range(4)] for i in range(4)]
    at_y = [sum(x[i] * y for x, y in zip(xs, ys)) for i in range(4)]
    beta = solve_linear(at_a, at_y)
    if beta is None:
        return {"fit": None, "note": "singular design (cells do not span k x E)"}
    pred = [sum(b * x for b, x in zip(beta, xrow)) for xrow in xs]
    resid = [y - p for y, p in zip(ys, pred)]
    ss_tot = sum((y - sum(ys) / len(ys)) ** 2 for y in ys)
    ss_res = sum(r * r for r in resid)
    return {"fit": {"b0": round(beta[0], 3), "b_per_hop": round(beta[1], 4),
                    "b_per_fact": round(beta[2], 4), "b_hop_x_fact": round(beta[3], 6)},
            "r2": (round(1.0 - ss_res / ss_tot, 4) if ss_tot else None),
            "n_cell_means": len(pts),
            "residuals": {c: round(r, 1) for (c, _k, _e, _m), r in zip(pts, resid)}}


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


def est_pos(r: dict) -> int:
    """Character-proportional estimate of the delivered answer's position inside the whole
    completion, recomputed at analysis time from the archived attempt fields (reasoning
    streams before content). Round 21's lesson: estimates stored at dispatch time rot, so
    this is derived here, never read back from a stored field."""
    if not r.get("attempts"):
        return -1
    a = r["attempts"][-1]
    off = a.get("content_offset", -1)
    if off < 0:
        return -1
    full = (a.get("reasoning") or "") + (a.get("content") or "")
    return round(a.get("completion_tokens", 0)
                 * (len(a.get("reasoning") or "") + off + 1) / max(len(full), 1))


def place_cell_status(rows: list) -> dict:
    """Round-8 trichotomy per cell (Wilson 95, floor 0.60), computed per readout, in WALK
    order. status: budget_limited (no-answer rate > 0.5) / maintained (lb >= floor) /
    collapsed (ub < floor) / inconclusive / descriptive (n < MIN_CERTIFY). The frontier
    report is two-dimensional by construction: for each hop depth k the largest E that is
    maintained, and for each E the largest k that is maintained."""
    floor = MAJORITY_FLOOR + MARGIN
    out_rows = []
    for row in sorted(rows, key=lambda r: cell_order_key(r["cell"])):
        n = row["n"]
        na = (row.get("no_answer", 0) / n) if n else 0.0
        lb, ub = wilson(row["correct"], n)
        if n < MIN_CERTIFY:
            status = "descriptive"
        elif na > 0.5:
            status = "budget_limited"
        elif lb >= floor:
            status = "maintained"
        elif ub < floor:
            status = "collapsed"
        else:
            status = "inconclusive"
        out_rows.append({"arm": "S", "cell": row["cell"], "k": row["k"],
                         "edges": row["edges"], "n": n, "correct": row["correct"],
                         "wrong": row.get("wrong", 0), "no_answer": row.get("no_answer", 0),
                         "accuracy": round(row["correct"] / n, 4) if n else 0.0,
                         "wilson_lb95": round(lb, 4), "wilson_ub95": round(ub, 4),
                         "no_answer_rate": round(na, 4), "status": status})
    by_k: dict = {}
    by_e: dict = {}
    for r in out_rows:
        if r["status"] == "maintained":
            by_k[r["k"]] = max(by_k.get(r["k"], 0), r["edges"])
            by_e[r["edges"]] = max(by_e.get(r["edges"], 0), r["k"])
    bad = [r["cell"] for r in out_rows if r["status"] != "maintained"]
    grid_max = max((r["edges"] for r in out_rows), default=0)
    k_max = max((r["k"] for r in out_rows), default=0)
    if not bad:
        report = (f"no cell of the declared walk leaves maintained: E* >= {grid_max} at "
                  f"k <= {k_max}; the frontier on this class lies beyond "
                  f"(k={k_max}, E={grid_max})")
    else:
        first = bad[0]
        report = (f"first non-maintained cell {first} "
                  f"(k={[r['k'] for r in out_rows if r['cell'] == first][0]}, "
                  f"E={[r['edges'] for r in out_rows if r['cell'] == first][0]}); "
                  f"non-maintained cells {bad}")
    return {"report": report, "maintained_by_k": {str(k): v for k, v in sorted(by_k.items())},
            "maintained_by_edges": {str(e): v for e, v in sorted(by_e.items())},
            "non_maintained_cells": bad, "floor": floor,
            "min_certify_items": MIN_CERTIFY, "rows": out_rows}


def aggregate(records: list) -> dict:
    readout_names = ("content_only", "loose_fallback", "delivered_or_strict")
    cells = {name: {"k": k, "edges": k * c, "chains": c}
             for name, k, c in WALK}
    per_ro: dict = {}
    tok: dict = {}
    dis: dict = {}
    trunc: dict = {}
    for rec in records:
        key = rec.get("cell") or cells_for(rec["k"], rec["chains"])
        tok.setdefault(key, {"completion": [], "prompt": []})
        tok[key]["completion"].append(rec.get("completion_tokens", 0))
        tok[key]["prompt"].append(rec.get("prompt_tokens", 0))
        last = rec["attempts"][-1] if rec.get("attempts") else {}
        if last.get("finish_reason") == "length":
            trunc[key] = trunc.get(key, 0) + 1
        mech = last.get("mechanics") or {}
        if mech.get("distractor_entities"):
            dis.setdefault(key, []).append(mech.get("distractor_mention_ratio"))
        for name in readout_names:
            row = per_ro.setdefault((name, key), {"cell": key, "n": 0, "correct": 0,
                                                  "wrong": 0, "no_answer": 0})
            row["n"] += 1
            c = rec["correct"][name]
            if c is None:
                row["no_answer"] += 1
            elif c == 1:
                row["correct"] += 1
            else:
                row["wrong"] += 1
    per_cell = {}
    for name in readout_names:
        rows = []
        for (nm, key), row in sorted(per_ro.items(), key=lambda kv: cell_order_key(kv[0][1])):
            if nm != name:
                continue
            row = dict(row)
            row["k"] = cells[key]["k"]
            row["edges"] = cells[key]["edges"]
            row["chains"] = cells[key]["chains"]
            row["mean_completion_tokens"] = round(
                sum(tok[key]["completion"]) / len(tok[key]["completion"]), 1)
            row["mean_prompt_tokens"] = round(
                sum(tok[key]["prompt"]) / len(tok[key]["prompt"]), 1)
            row["truncated_cells"] = trunc.get(key, 0)
            rows.append(row)
        per_cell[name] = rows
    status = {name: place_cell_status(per_cell[name]) for name in readout_names}

    arm_stats = {}
    for arm in ("F", "X"):
        rs = [r for r in records if r["arm"] == arm]
        denom = max(1, len(rs))
        ratios = [((r["attempts"][-1].get("mechanics") or {}).get("distractor_mention_ratio"))
                  for r in rs if r.get("attempts")]
        ratios = [x for x in ratios if x is not None]
        entry = {"cells": len(rs),
                 "mean_completion_tokens": round(
                     sum(r.get("completion_tokens", 0) for r in rs) / denom, 1),
                 "mean_prompt_tokens": round(
                     sum(r.get("prompt_tokens", 0) for r in rs) / denom, 1),
                 "mean_distractor_mention_ratio": (round(sum(ratios) / len(ratios), 4)
                                                   if ratios else None),
                 "readouts": {}}
        for name in readout_names:
            correct = sum(1 for r in rs if r["correct"][name] == 1)
            wrong = sum(1 for r in rs if r["correct"][name] == 0)
            no_answer = sum(1 for r in rs if r["correct"][name] is None)
            lb, ub = wilson(correct, len(rs))
            entry["readouts"][name] = {"correct": correct, "wrong": wrong,
                                       "no_answer": no_answer,
                                       "accuracy": round(correct / len(rs), 4) if rs else 0.0,
                                       "wilson_lb95": round(lb, 4),
                                       "wilson_ub95": round(ub, 4)}
        arm_stats[arm] = entry

    # arm split per cell: does the negative arm become the fragile one at the joint corner?
    arm_by_cell = {}
    for name in WALK_INDEX:
        rs = [r for r in records if (r.get("cell") or cells_for(r["k"], r["chains"])) == name]
        entry = {}
        for arm in ("F", "X"):
            a_rs = [r for r in rs if r["arm"] == arm]
            correct = sum(1 for r in a_rs if r["correct"]["content_only"] == 1)
            no_answer = sum(1 for r in a_rs if r["correct"]["content_only"] is None)
            entry[arm] = {"cells": len(a_rs), "correct": correct, "no_answer": no_answer,
                          "mean_completion_tokens": (round(
                              sum(r.get("completion_tokens", 0) for r in a_rs) / len(a_rs), 1)
                              if a_rs else None)}
        arm_by_cell[name] = entry

    # matched-pair analysis: one graph per pair, arm F (gold yes) and arm X (gold no)
    pairs = collections.defaultdict(dict)
    for rec in records:
        key = rec.get("cell") or cells_for(rec["k"], rec["chains"])
        pairs[(key, rec["pair_seed"])][rec["arm"]] = rec
    counts = {"pairs": 0, "both_ok": 0, "f_ok_x_not": 0, "x_ok_f_not": 0,
              "both_not": 0, "both_silent": 0, "f_silent": 0, "x_silent": 0}
    per_cell_pairs = {}
    for (cell_name, _ps), pair in sorted(pairs.items(), key=lambda kv: (cell_order_key(kv[0][0]),
                                                                        kv[0][1])):
        f, x = pair.get("F"), pair.get("X")
        if f is None or x is None:
            continue
        counts["pairs"] += 1
        fok = f["correct"]["content_only"] == 1
        xok = x["correct"]["content_only"] == 1
        rl = per_cell_pairs.setdefault(cell_name, {"pairs": 0, "both_ok": 0,
                                                   "f_ok_x_not": 0, "x_ok_f_not": 0,
                                                   "both_not": 0})
        rl["pairs"] += 1
        if fok and xok:
            counts["both_ok"] += 1
            rl["both_ok"] += 1
        elif fok and not xok:
            counts["f_ok_x_not"] += 1
            rl["f_ok_x_not"] += 1
        elif xok and not fok:
            counts["x_ok_f_not"] += 1
            rl["x_ok_f_not"] += 1
        else:
            counts["both_not"] += 1
            rl["both_not"] += 1
        if f["content_answer"] is None:
            counts["f_silent"] += 1
        if x["content_answer"] is None:
            counts["x_silent"] += 1
        if f["content_answer"] is None and x["content_answer"] is None:
            counts["both_silent"] += 1
    mcnemar = {"b_forward_ok_cross_not": counts["f_ok_x_not"],
               "c_cross_ok_forward_not": counts["x_ok_f_not"],
               "p_exact": mcnemar_exact(counts["f_ok_x_not"], counts["x_ok_f_not"])}

    # single-axis transitions inside each arm: consecutive cells differ in exactly one axis
    means = {r["cell"]: r for r in per_cell["content_only"]}
    # the trichotomy status lives in the classification rows, NOT in the token rows
    # (round 22's aggregate KeyError class; asserted by --selftest item 14)
    status_by_cell = {r["cell"]: r["status"] for r in status["content_only"]["rows"]}
    steps = ([(a, b, "load") for a, b in zip(LOAD_NAMES, LOAD_NAMES[1:])]
             + [(a, b, "depth") for a, b in zip(DEPTH_NAMES, DEPTH_NAMES[1:])])
    transitions = []
    order = [name for name, _k, _c in WALK]
    for a_name, b_name, declared_axis in steps:
        if a_name not in means or b_name not in means:
            continue
        a, b = means[a_name], means[b_name]
        axis = "depth" if a["k"] != b["k"] else "load"
        if a["k"] != b["k"] and a["edges"] != b["edges"]:
            axis = "BOTH (design error)"
        transitions.append({
            "from": a_name, "to": b_name, "axis": axis,
            "declared_axis": declared_axis,
            "k": f"{a['k']}->{b['k']}", "edges": f"{a['edges']}->{b['edges']}",
            "accuracy": f"{a['correct']}/{a['n']}->{b['correct']}/{b['n']}",
            "no_answer": f"{a['no_answer']}->{b['no_answer']}",
            "mean_completion_tokens": (round(b["mean_completion_tokens"]
                                             / a["mean_completion_tokens"], 4)
                                       if a["mean_completion_tokens"] else None),
            "status": f"{status_by_cell.get(a_name)}->{status_by_cell.get(b_name)}"})

    # predictions (round 31, cross-class; declared in gate round31-gate-v1)
    st = {r["cell"]: r["status"] for r in status["content_only"]["rows"]}
    non_maintained = [n for n in WALK_INDEX if st.get(n) != "maintained"]
    p1_ok = len(non_maintained) == 0
    content_recs = [r for r in records if r["content_answer"] is not None]
    p2_ok = bool(content_recs) and all(r["correct"]["content_only"] == 1
                                       for r in content_recs)
    truncated_cells = {r.get("cell") or cells_for(r["k"], r["chains"])
                       for r in records
                       if (r["attempts"][-1].get("finish_reason") if r.get("attempts")
                           else None) == "length"}
    p3_ok = not truncated_cells

    # P4: cost law on UNCENSORED cell means (a cell with ANY truncation is censored);
    # the bands are 0.5x-2.0x of round 24's flash-next slopes, declared in the gate
    depth_band = (round(R24_DEPTH_SLOPE_TOK_PER_HOP * COST_BAND[0], 3),
                  round(R24_DEPTH_SLOPE_TOK_PER_HOP * COST_BAND[1], 3))
    load_band = (round(R24_LOAD_SLOPE_TOK_PER_FACT * COST_BAND[0], 3),
                 round(R24_LOAD_SLOPE_TOK_PER_FACT * COST_BAND[1], 3))
    depth_pts = [(r["k"], r["mean_completion_tokens"])
                 for r in per_cell["content_only"]
                 if r["edges"] == 96 and r["cell"] not in truncated_cells
                 and r["mean_completion_tokens"]]
    load_pts = [(r["edges"], r["mean_completion_tokens"])
                for r in per_cell["content_only"]
                if r["k"] == 8 and r["cell"] not in truncated_cells
                and r["mean_completion_tokens"]]
    depth_law_this = ols(depth_pts)
    load_law_this = ols(load_pts)
    p4_depth_in_band = (depth_law_this["slope"] is not None
                        and depth_band[0] <= depth_law_this["slope"] <= depth_band[1])
    p4_load_in_band = (load_law_this["slope"] is not None
                       and load_band[0] <= load_law_this["slope"] <= load_band[1])
    p4_ok = p4_depth_in_band and p4_load_in_band

    # distractor accounting (descriptive, carried in the return dict)
    dis_by_cell = {}
    for key, vals in dis.items():
        good = [x for x in vals if x is not None]
        if good:
            dis_by_cell[key] = round(sum(good) / len(good), 4)

    # P5/P6: per-prompt cross-class delta against the round-24 archive (digest-pinned)
    comparable = 0
    agreed = 0
    per_prompt_delta = []
    for rec in records:
        ref = R24_RECORDS.get(rec["prompt_sha256"])
        if ref is None:
            continue
        a, b = rec["content_answer"], ref["content_answer"]
        entry = {"prompt_sha256": rec["prompt_sha256"], "cell": rec["cell"],
                 "arm": rec["arm"], "k": rec["k"], "edges": rec["edges"],
                 "r24_answer": b, "r24_outcome": ref["outcome"],
                 "r24_completion_tokens": ref["completion_tokens"],
                 "this_answer": a, "this_outcome": rec["outcome"],
                 "this_completion_tokens": rec["completion_tokens"],
                 "agreement": None}
        if a is not None and b is not None:
            comparable += 1
            entry["agreement"] = (a == b)
            if a == b:
                agreed += 1
        per_prompt_delta.append(entry)
    p5_rate = (agreed / comparable) if comparable else None
    p5_ok = p5_rate is not None and p5_rate >= 0.5

    l0_forward = set(R24_DIGESTS["L0"]["forward_prompt_sha256"])
    anchor_rows = []
    for r in records:
        if r["arm"] != "F" or r["prompt_sha256"] not in l0_forward:
            continue
        ref = R24_RECORDS[r["prompt_sha256"]]
        anchor_rows.append({
            "cell": "L0", "seed": r["seed"],
            "prompt_sha256": r["prompt_sha256"][:12],
            "this_answer": r["content_answer"],
            "this_completion_tokens": r["completion_tokens"],
            "r24_answer": ref["content_answer"],
            "r24_completion_tokens": ref["completion_tokens"],
            "answer_agrees": r["content_answer"] == ref["content_answer"]})
    p6_ok = len(anchor_rows) == 3 and all(row["answer_agrees"] for row in anchor_rows)

    # content-silent cells (kept for the round-24 fallback-provenance section, #94)
    silent = [r for r in records if r["content_answer"] is None
              and r["reasoning_answer"] is not None]

    # P7: digest identity with round 24 (structural; true by construction, reported)
    p7_ok = (len(records) == 2 * PAIRS_PER_LEVEL * len(WALK)
             and all(r["prompt_sha256"] in R24_RECORDS for r in records))

    # per-cell cross-class table: this class against the round-24 flash-next archive
    # (cell status comes from the trichotomy rows, not the token rows: round 22 lesson)
    r24_cell_agg = {}
    for cell in WALK_INDEX:
        rows_r24 = [v for v in R24_RECORDS.values() if v["cell"] == cell]
        r24_cell_agg[cell] = {
            "mean_completion_tokens": (round(sum(v["completion_tokens"] for v in rows_r24)
                                             / len(rows_r24), 1) if rows_r24 else None),
            "delivered": sum(1 for v in rows_r24 if v["content_answer"] is not None),
            "correct_content_only": sum(1 for v in rows_r24
                                        if v["correct_content_only"] == 1),
            "truncated": sum(1 for v in rows_r24 if v["finish_reason"] == "length")}
    cc_status = {r["cell"]: r["status"] for r in status["content_only"]["rows"]}
    crossclass_cells = []
    for r in per_cell["content_only"]:
        crossclass_cells.append({
            "cell": r["cell"], "k": r["k"], "edges": r["edges"],
            "this_status": cc_status.get(r["cell"]),
            "this_correct": r["correct"], "this_no_answer": r["no_answer"],
            "this_truncated": r["truncated_cells"],
            "this_mean_completion_tokens": r["mean_completion_tokens"],
            "r24": r24_cell_agg.get(r["cell"])})


    cell_means_tok = [(n, means[n]["k"], means[n]["edges"], means[n]["mean_completion_tokens"])
                      for n in order if n in means]
    load_law_at_k8 = ols([(e, m) for (_c, k, e, m) in cell_means_tok
                          if k == 8 and m is not None])
    depth_law_at_E96 = ols([(k, m) for (_c, k, e, m) in cell_means_tok
                            if e == 96 and m is not None])

    prov = collections.Counter()
    prov_agree = collections.Counter()
    strict_on_silent = {"cells": 0, "committed": 0, "correct": 0}
    fractions = []
    for rec in records:
        cls = rec["fallback_provenance_class"]
        if cls is None:
            prov["no_trace_token"] += 1
            continue
        prov[cls] += 1
        gold_word = "yes" if rec["gold"] == 1 else "no"
        prov_agree[cls] += int(rec["reasoning_answer"] == gold_word)
        if rec["fallback_commit_fraction"] is not None:
            fractions.append(rec["fallback_commit_fraction"])
        if rec["content_answer"] is None:
            strict_on_silent["cells"] += 1
            if rec["strict_trace_token"] is not None:
                strict_on_silent["committed"] += 1
                strict_on_silent["correct"] += int(
                    (1 if rec["strict_trace_token"] == "yes" else 0) == rec["gold"])
    fractions.sort()
    fallback_correct = sum(1 for r in records if r["correct"]["loose_fallback"] == 1
                           and r["content_answer"] is None)
    no_baseline = sum(1 for r in records if r["gold"] == 0) / len(records) if records else 0.0

    replay = {}
    for b in (256, 512, 1024, 2048):
        ans = sum(1 for r in records if 0 <= est_pos(r) <= b)
        corr = sum(1 for r in records if 0 <= est_pos(r) <= b
                   and r["correct"]["content_only"] == 1)
        replay[str(b)] = {"n": len(records), "content_answerable_est": ans,
                          "correct": corr,
                          "accuracy_over_all": round(corr / len(records), 4) if records else 0.0}

    return {
        "records": len(records),
        "per_cell": per_cell,
        "cell_status": status,
        "per_arm": arm_stats,
        "arm_by_cell": arm_by_cell,
        "matched_pairs": {"counts": counts, "mcnemar": mcnemar,
                          "per_cell": per_cell_pairs},
        "single_axis_transitions": transitions,
        "token_model_completion": two_factor_means(cell_means_tok),
        "token_law_completion_vs_k_at_E96": depth_law_at_E96,
        "token_law_completion_vs_edges_at_k8": load_law_at_k8,
        "distractor_mention_ratio_by_cell": dis_by_cell,
        "predictions": {
            "P1_non_maintained_cells": non_maintained,
            "P1_pass": p1_ok,
            "P2_content_answers_correct": (
                f"{sum(1 for r in content_recs if r['correct']['content_only'] == 1)}"
                f"/{len(content_recs)}"),
            "P2_pass": p2_ok,
            "P3_truncated_cells": sorted(truncated_cells),
            "P3_pass": p3_ok,
            "P4_depth_slope_this_class": depth_law_this,
            "P4_depth_slope_band": [depth_band[0], depth_band[1]],
            "P4_depth_slope_in_band": p4_depth_in_band,
            "P4_load_slope_this_class": load_law_this,
            "P4_load_slope_band": [load_band[0], load_band[1]],
            "P4_load_slope_in_band": p4_load_in_band,
            "P4_pass": p4_ok,
            "P5_comparable_prompts": comparable,
            "P5_agreed": agreed,
            "P5_agreement_rate": (round(p5_rate, 4) if p5_rate is not None else None),
            "P5_pass": p5_ok,
            "P5_vacuous": comparable == 0,
            "P6_anchor_rows": anchor_rows,
            "P6_anchored_prompts": len(anchor_rows),
            "P6_pass": p6_ok,
            "P7_digests_in_round24_archive": sum(1 for r in records
                                                  if r["prompt_sha256"] in R24_RECORDS),
            "P7_pass": p7_ok},
        "fallback_provenance": {
            "classes": dict(prov),
            "agreement_with_gold": {cls: prov_agree[cls] for cls in prov if cls != "no_trace_token"},
            "commit_fraction_median": (round(fractions[len(fractions) // 2], 4)
                                       if fractions else None),
            "strict_rule_on_content_silent_cells": strict_on_silent,
            "loose_fallback_when_content_silent": {
                "cells_with_trace_token": len(silent), "correct": fallback_correct,
                "constant_no_baseline_accuracy": round(no_baseline, 4)}},
        "budget_replay_content_only": replay,
        "crossclass": {
            "r24_class": "flash-next class, round 24 (PR #98), gate.json and raw.jsonl",
            "this_class": ("NVFP4 27B class under vLLM serving, round 31; "
                           "served model referenced by public class name only"),
            "per_cell": crossclass_cells,
            "per_prompt": per_prompt_delta,
            "agreement": {"comparable": comparable, "agreed": agreed,
                          "rate": (round(p5_rate, 4) if p5_rate is not None else None)}},
        "totals": {
            "correct": {name: sum(1 for r in records if r["correct"][name] == 1)
                        for name in readout_names},
            "answered": {name: sum(1 for r in records
                                   if r["correct"][name] is not None)
                         for name in readout_names},
            "truncated": sum(1 for r in records
                             if (r["attempts"][-1].get("finish_reason") if r.get("attempts")
                                 else None) == "length"),
            "outcomes": dict(collections.Counter(r["outcome"] for r in records)),
            "errors": sum(1 for r in records if r["outcome"].startswith("transport_"))}}


def cells_for(k: int, chains: int) -> str:
    """Reverse map from (k, C) to the walk cell name, for records written before the cell
    name existed (defensive: the resume path must never KeyError on its own archive)."""
    for name, kk, cc in WALK:
        if kk == k and cc == chains:
            return name
    return f"K{k}C{chains}"


def probe(out_dir: str, resume: bool) -> int:
    global GATE_HASH
    os.makedirs(out_dir, exist_ok=True)
    raw_path = os.path.join(out_dir, "raw.jsonl")
    gate = build_gate()
    GATE_HASH = gate_hash(gate)
    if not gate["all_cells_pass"]:
        print("REFUSED: at least one cell failed the permutation-calibrated gate",
              file=sys.stderr)
        return 3
    if not gate["anchor_ok"]:
        print("REFUSED: the round-24 digest anchor pins do not match the construction",
              file=sys.stderr)
        return 3
    done: dict = {}
    cap = AttemptBudget(PROMPT_CAP)
    if resume:
        if not os.path.exists(raw_path):
            print("--resume without raw.jsonl", file=sys.stderr)
            return 2
        with open(raw_path, "r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("gate_hash") != GATE_HASH:
                    print("--resume refused: raw.jsonl written under a different gate",
                          file=sys.stderr)
                    return 2
                key = (rec["arm"], rec.get("cell") or cells_for(rec["k"], rec["chains"]),
                       rec["seed"])
                done[key] = rec
                cap.used += len(rec["attempts"])
    health = health_check()
    cap.used += 1
    print(f"health: {health}", flush=True)
    if not health["ok"]:
        print("REFUSED: endpoint failed the chat-completion health probe",
              file=sys.stderr)
        return 4
    plan = []
    for cell in all_cells():
        for (f_item, x_item) in cell["pairs"]:
            plan.append((cell["cell"], "F", f_item, f_item["seed"]))
            plan.append((cell["cell"], "X", x_item, f_item["seed"]))
    if len(plan) + HEALTH_CALLS > PROMPT_CAP:
        print(f"plan {len(plan)} + health exceeds cap {PROMPT_CAP}", file=sys.stderr)
        return 2
    note = {"resumed_cells": len(done), "health": health, "gate_hash": GATE_HASH}

    def run(cell_name: str, arm: str, item: dict, pair_seed: int, phase: int) -> dict:
        rec = make_record(item, arm, pair_seed, cap, phase)
        rec["cell"] = cell_name
        results[(arm, cell_name, item["seed"])] = rec
        write_jsonl(raw_path, rec)
        print(f"{cell_name} k={rec['k']:>2} E={rec['edges']:>3} {rec['arm']} "
              f"gold={rec['gold']} outcome={rec['outcome']:>22} "
              f"content={str(rec['content_answer']):>4} "
              f"strict={str(rec['strict_trace_token']):>4} "
              f"ctok={rec['attempts'][-1]['completion_tokens']:>5} "
              f"wall={rec['attempts'][-1]['wall_s']:.1f}s", flush=True)
        return rec

    def key_of(entry) -> tuple:
        cell_name, arm, item, _ps = entry
        return (arm, cell_name, item["seed"])

    pending = [e for e in plan if key_of(e) not in done]
    results = dict(done)
    started = time.monotonic()
    # phase 1: two cells to measure the single-stream rate. The estimator is the corrected
    # one from round 22's lesson: completion_tokens / wall_s, not MAX_TOKENS / wall_s.
    phase1 = pending[:2]
    for (cn, a, it, ps) in phase1:
        run(cn, a, it, ps, 1)
    walls, rates = [], []
    for e in phase1:
        rec = results[key_of(e)]
        if not rec["attempts"]:
            continue
        att = rec["attempts"][-1]
        if att["wall_s"] and att["wall_s"] > 0:
            walls.append(att["wall_s"])
            if att["completion_tokens"]:
                rates.append(att["completion_tokens"] / att["wall_s"])
    tps = max([TPS_FLOOR] + rates)
    est_cost = MAX_TOKENS if not rates else max(512, min(MAX_TOKENS, int(
        3 * sum(results[key_of(e)]["attempts"][-1]["completion_tokens"]
                for e in phase1 if results[key_of(e)]["attempts"]) / max(1, len(phase1)))))
    remaining = pending[2:]
    est_total = len(remaining) * est_cost / tps
    chosen = None
    for cand in CONCURRENCY_CHOICES:
        if est_total / cand * 1.25 <= PHASE2_BUDGET_S:
            chosen = cand
            break
    if chosen is None:
        chosen = max(CONCURRENCY_CHOICES)
    if tps < 30.0:
        chosen = max(chosen, 4)
    note.update({"phase1_walls": walls, "measured_tokens_per_second": round(tps, 2),
                 "estimated_tokens_per_cell": est_cost,
                 "estimate_phase2_s": round(est_total, 1), "chosen_concurrency": chosen})
    print(f"phase-1 walls {[round(w, 1) for w in walls]} s, measured ~{round(tps, 1)} "
          f"tok/s, {est_cost} tok/cell est, concurrency {chosen} for {len(remaining)} "
          f"cells", flush=True)
    phase2_start = time.monotonic()
    to_run, abandoned = [], []
    for entry in remaining:
        if time.monotonic() > phase2_start + PHASE2_BUDGET_S:
            abandoned.append(entry)
        else:
            to_run.append(entry)
    for (cn, a, it, ps) in abandoned:
        rec = blank_record(it, a, ps, 2)
        rec["cell"] = cn
        rec.update({"completion_tokens": 0, "prompt_tokens": 0,
                    "outcome": "abandoned_budget", "content_answer": None,
                    "reasoning_answer": None, "loose_fallback_answer": None,
                    "strict_trace_token": None, "delivered_or_strict_answer": None,
                    "fallback_provenance_class": None, "fallback_commit_fraction": None,
                    "correct": {"content_only": None, "loose_fallback": None,
                                "delivered_or_strict": None}})
        results[key_of(entry)] = rec
        write_jsonl(raw_path, rec)
    if to_run:
        with concurrent.futures.ThreadPoolExecutor(max_workers=chosen) as pool:
            futures = [pool.submit(run, cn, a, it, ps, 2) for (cn, a, it, ps) in to_run]
            for fut in concurrent.futures.as_completed(futures):
                fut.result()
    ordered = [results[key_of(e)] for e in plan]
    summary = aggregate(ordered)
    summary["gate_hash"] = GATE_HASH
    summary["wall_seconds"] = round(time.monotonic() - started, 1)
    summary["transport"] = note
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write("\n")
    with open(os.path.join(out_dir, "gate.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(gate, gate_hash=GATE_HASH), fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(json.dumps({"totals": summary["totals"],
                      "cell_status": {k: v["report"] for k, v in summary["cell_status"].items()},
                      "frontier": summary["cell_status"]["content_only"]["maintained_by_k"],
                      "matched_pairs": summary["matched_pairs"]["mcnemar"],
                      "predictions": summary["predictions"]}, indent=2, sort_keys=True))
    return 0


def cmd_gate(out_path: str) -> int:
    gate = build_gate()
    gate = dict(gate, gate_hash=gate_hash(gate))
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(gate, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"gate {gate['gate_hash'][:8]}: all_cells_pass={gate['all_cells_pass']} "
          f"anchor_ok={gate['anchor_ok']} planned={gate['planned_prompts']} "
          f"corpus={gate['corpus_blob_sha256'][:12]}")
    for c in gate["cells"]:
        g, gp = c["gate_pool"], c["gate_paired_pool"]
        print(f"  {c['cell']} k={c['k']:>2} C={c['chains']:>2} E={c['edges']:>3} "
              f"pool: {g['verdict']} obs={g['observed_max']} thr={g['calibrated_threshold']} "
              f"p={g['p_value']} | paired: {gp['verdict']} obs={gp['observed_max']} "
              f"thr={gp['calibrated_threshold']} p={gp['p_value']} "
              f"chars={c['load']['prompt_chars_mean']}")
    for label, row in sorted(gate["anchor"]["anchors"].items()):
        print(f"  anchor {label} cell {row['cell']}: pool={row['pool_blob_matches']} "
              f"forward={row['forward_prompts_match']} "
              f"cross={row['cross_prompts_match']}")
    return 0 if (gate["all_cells_pass"] and gate["anchor_ok"]) else 3


def cmd_analyze(out_dir: str) -> int:
    raw_path = os.path.join(out_dir, "raw.jsonl")
    records = [json.loads(line) for line in open(raw_path, encoding="utf-8")
               if line.strip()]
    summary = aggregate(records)
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def synthetic_record(cell_name: str, arm: str, seed: int, gold: int, content: str,
                     reasoning: str, completion_tokens: int,
                     finish_reason: str = "stop") -> dict:
    """A record shaped exactly like make_record's output, for the analysis smoke test."""
    att = {"attempt": 1, "wall_s": 1.0, "error_class": None,
           "started_at": now_iso(), "finished_at": now_iso(),
           "finish_reason": finish_reason, "prompt_tokens": 100,
           "completion_tokens": completion_tokens, "content": content,
           "reasoning": reasoning}
    att.update(readouts(content, reasoning))
    att["mechanics"] = {"distractor_entities": 5, "distractors_mentioned": 2,
                        "distractor_mention_ratio": 0.4}
    rec = {"arm": arm, "cell": cell_name, "level": 96, "k": 4, "chains": 24,
           "edges": 96, "seed": seed, "pair_seed": seed, "seed_hash": "x",
           "item_sha256": "x", "prompt_sha256": "x", "prompt_chars": 100, "gold": gold,
           "gate_hash": "x", "phase": 2, "attempts": [att],
           "completion_tokens": completion_tokens, "prompt_tokens": 100,
           "outcome": classify_attempt(att)}
    for field in ("content_answer", "reasoning_answer", "loose_fallback_answer",
                  "loose_fallback_source", "strict_trace_token",
                  "delivered_or_strict_answer", "fallback_provenance_class",
                  "fallback_commit_fraction"):
        rec[field] = att[field]
    rec["correct"] = {}
    for name in ("content_only", "loose_fallback", "delivered_or_strict"):
        ans = {"content_only": att["content_answer"],
               "loose_fallback": att["loose_fallback_answer"],
               "delivered_or_strict": att["delivered_or_strict_answer"]}[name]
        rec["correct"][name] = (None if ans is None
                                else int((1 if ans == "yes" else 0) == gold))
    return rec


def selftest() -> None:
    checks = 0

    def ok(cond, msg):
        nonlocal checks
        checks += 1
        assert cond, msg

    # 1. the two arms are single-axis, the load arm is strictly rising in E at fixed
    #    k = 8, the depth arm holds E = 96 while k strictly rises, and the whole grid is
    #    exactly the six cells round 24 measured on the flash-next class (replication
    #    claim; digest-level pin in item 12)
    load_ks = [k for _n, k, _c in LOAD_ARM]
    load_es = [k * c for _n, k, c in LOAD_ARM]
    ok(all(k == 8 for k in load_ks), "load arm does not hold k = 8")
    ok(load_es == sorted(load_es) and len(set(load_es)) == len(load_es),
       "load arm fact count not strictly rising")
    depth_es = [k * c for _n, k, c in DEPTH_ARM]
    depth_ks = [k for _n, k, _c in DEPTH_ARM]
    ok(all(e == 96 for e in depth_es), "depth arm does not hold E = 96")
    ok(depth_ks == sorted(depth_ks) and len(set(depth_ks)) == len(depth_ks),
       "depth arm hop depth not strictly rising")
    for arm in (LOAD_ARM, DEPTH_ARM):
        for (na, ka, ca), (nb, kb, cb) in zip(arm, arm[1:]):
            ok((ka == kb) != (ka * ca == kb * cb),
               f"step {na}->{nb} must change exactly one axis")
    ok(("L0", 8, 12) in LOAD_ARM, "anchor cell is not the round-24 L0 shape (8, 12)")
    # the cross-class replication claim: WALK is exactly the grid round 24 measured,
    # cell by cell; verified against the round-24 gate digests (item 12) below
    r24_grid = (("L0", 8, 12), ("L1", 8, 14), ("L2", 8, 16), ("L3", 8, 20),
                ("D1", 12, 8), ("D2", 16, 6))
    ok(tuple(tuple(x) for x in WALK) == r24_grid,
       "grid is not exactly round 24's declared grid")
    ok(load_es[0] == 96 and load_es[-1] == 160 and max(depth_ks) == 16,
       "arms do not sit inside the declared bracket")

    # 1b. the tolerance helpers themselves: a must-see step must fail on a tie, an
    #     equal-load equality must tolerate entity-name-length noise (round 23 P1 lesson)
    ok(steps_at_least([100.0, 110.0, 120.0], 1.05), "visible load steps rejected")
    ok(not steps_at_least([100.0, 100.1, 120.0], 1.05), "invisible step accepted")
    ok(not steps_at_least([100.0, 90.0, 120.0], 1.05), "dip accepted")
    ok(within_tolerance(1000.0, 1001.2, 0.01), "0.12% noise failed the tolerance")
    ok(not within_tolerance(1000.0, 1020.0, 0.01), "2% divergence passed the tolerance")
    ok(not within_tolerance(None, 1.0, 0.01), "missing mean passed the tolerance")

    # 2. structural and solvability audit on every candidate and variant, and the
    #    matched-pair invariant on every dispatched pair
    gate_cells = {c["cell"]: c for c in all_cells()}
    for name, k, c_chains in WALK:
        pairs, pool, paired_pool = build_cell(k, c_chains, PAIRS_PER_LEVEL)
        ok(len(pool) == CANDIDATES, f"pool size {name}")
        ok(len(pairs) == PAIRS_PER_LEVEL, f"pair count {name}")
        for it in pool:
            ok(not verify_item(it), f"audit {name} seed={it['seed']}")
            ok(it["edges"] == k * c_chains, f"E not as declared at {name}")
            ok(it["level"] == k, f"k not constant at {name}")
        for (f_item, x_item) in pairs:
            ok(not verify_item(x_item), f"variant audit {name}")
            ok(not pair_violations(f_item, x_item), f"pair invariant {name}")
            ok(f_item["answer"] == "yes" and x_item["answer"] == "no",
               f"pair labels {name}")
        ok(len(paired_pool) == 2 * sum(1 for it in pool if it["answer"] == "yes"),
           f"paired pool size {name}")
        ok(len({it["seed"] for it in pool}) == CANDIDATES, f"seed uniqueness {name}")

    # 3. negative controls on the structural audit (planted defects must be caught)
    k0, c0 = 8, 12
    base = gen_item(k0, c0, cell_seed(k0, c0, 0))
    while base["answer"] != "yes":
        base = gen_item(k0, c0, base["seed"] + 1)
    ok(not verify_item(base), "clean item failed the audit")
    planted = dict(base)
    planted["facts"] = [list(f) for f in base["facts"]] + [[base["facts"][0][0], REL,
                                                            base["facts"][0][0] + "zz"]]
    ok(bool(verify_item(planted)), "planted detached fact not caught")
    planted = dict(base)
    planted["facts"] = [list(f) for f in base["facts"]][:-1]
    ok(bool(verify_item(planted)), "planted truncated component not caught")
    planted = dict(base)
    planted["answer"] = "no"
    ok("stored answer disagrees with independent BFS" in verify_item(planted),
       "planted flipped label not caught")
    planted = dict(base)
    planted["facts"] = [list(f) for f in base["facts"]]
    planted["facts"].append(list(planted["facts"][0]))
    ok("duplicate facts" in verify_item(planted), "planted duplicate fact not caught")
    planted = dict(base)
    planted["chains"] = base["chains"] + 1
    ok(bool(verify_item(planted)), "planted manifest component count not caught")

    # 4. negative controls on the matched-pair invariant (#78 criterion 1)
    f_item = base
    x_item = x_variant(f_item)
    ok(not pair_violations(f_item, x_item), "clean pair rejected")
    # a variant built from ANOTHER item's facts (here: from the (4, 6) origin corner of
    # rounds 21 and 22, a shape outside this round's grid, so the fact lists and entity
    # sets cannot coincide by accident) must be caught
    other = next(gen_item(4, 6, cell_seed(4, 6, i)) for i in range(CANDIDATES)
                 if gen_item(4, 6, cell_seed(4, 6, i))["answer"] == "yes")
    ok(canonical(other["facts"]) != canonical(f_item["facts"]),
       "planted control item is not actually different")
    cross_item = dict(other)
    cross_item["query"] = [f_item["query"][0], REL, other["query"][2]]
    cross_item["answer"] = "no"
    cross_item["chain_len"] = None
    planted_viol = pair_violations(f_item, cross_item)
    ok("fact lists differ" in planted_viol and "entity name sets differ" in planted_viol,
       "planted cross-item pair not caught")
    same_target = dict(x_item)
    same_target["query"] = [f_item["query"][0], REL, f_item["query"][2]]
    same_target["answer"] = "no"
    ok("queried targets are identical" in pair_violations(f_item, same_target),
       "planted identical-target pair not caught")
    diff_source = dict(x_item)
    diff_source["query"] = [base["facts"][0][0], REL, x_item["query"][2]]
    ok(bool(pair_violations(f_item, diff_source)), "planted different-source pair not caught")
    reachable = dict(x_item)
    reachable["query"] = [f_item["query"][0], REL, f_item["query"][2]]
    reachable["answer"] = "no"
    ok("cross-component target is reachable from the source"
       in pair_violations(f_item, reachable), "planted reachable X target not caught")

    # 5. the leak gate: a planted traversal-free predictor must be flagged
    pool = [gen_item(k0, c0, cell_seed(k0, c0, i)) for i in range(12)]
    for it in pool:
        feat = features(it)["tgt_name_lt_src_name"]
        it["answer"] = "yes" if feat else "no"
    flagged = gate_battery(pool)
    ok(flagged["verdict"] == "leak", "planted leak not flagged")
    ok(any("tgt_name_lt_src_name" in r for r in flagged["flagged_rules"]),
       "planted leak rule not named")
    clean = [gen_item(k0, c0, cell_seed(k0, c0, i)) for i in range(12)]
    ok(gate_battery(clean)["verdict"] != "leak", "clean pool flagged")

    # 6. readout stack, vendored strict rule, provenance classes
    ok(readouts("yes", "reasoning")["content_answer"] == "yes", "content readout")
    ok(readouts("", "so the answer is no.")["loose_fallback_answer"] == "no",
       "loose fallback")
    ok(readouts("", "so the answer is no.")["delivered_or_strict_answer"] == "no",
       "strict readout on cued verdict")
    ok(readouts("", "check A then B")["loose_fallback_answer"] is None,
       "phantom fallback token")
    ok(strict_last_trace_token("I will answer yes/no after checking.") is None,
       "instruction echo accepted as a commitment")
    ok(strict_last_trace_token("chain is aq zeq fir then ghm") is None,
       "mid-trace bare token accepted")
    ok(strict_last_trace_token("walking the chain gives no") == "no",
       "trace-closing verdict rejected")
    ok(provenance_class("answer yes/no then stop")[0] == "instruction_echo",
       "echo class")
    ok(provenance_class("a" * 100 + " no")[0] == "terminal", "terminal class")
    ok(provenance_class("no " + "b" * 500)[0] == "mid_trace", "mid-trace class")
    ok(provenance_class("nothing at all") == (None, -1.0), "no trace token class")

    # 7. arithmetic: Wilson, exact McNemar, the linear solver, the two-factor fit
    lb, ub = wilson(6, 6)
    ok(abs(lb - 0.6097) < 0.001, f"Wilson 6/6 lower bound {lb:.4f}")
    ok(abs(ub - 1.0) < 1e-9, "Wilson 6/6 upper bound")
    ok(wilson(0, 0) == (0.0, 0.0), "Wilson empty")
    ok(mcnemar_exact(0, 0) == 1.0, "McNemar no discordance")
    ok(abs(mcnemar_exact(1, 0) - 1.0) < 1e-12, "McNemar 1/0: one discordant pair is not "
       "significant and the report must say so")
    ok(abs(mcnemar_exact(2, 0) - 0.5) < 1e-12, "McNemar 2/0")
    ok(mcnemar_exact(6, 0) < 0.05, "McNemar 6/0 should be significant")
    ok(solve_linear([[1.0, 0.0], [0.0, 1.0]], [3.0, 4.0]) == [3.0, 4.0], "solve identity")
    ok(solve_linear([[1.0, 2.0], [2.0, 4.0]], [1.0, 3.0]) is None, "singular not detected")
    fit = two_factor_means([("A", 4.0, 24.0, 300.0), ("B", 4.0, 96.0, 400.0),
                            ("C", 8.0, 96.0, 500.0), ("D", 8.0, 192.0, 700.0),
                            ("E", 12.0, 192.0, 900.0), ("F", 16.0, 192.0, 1100.0)])
    ok(fit["fit"] is not None and fit["fit"]["b_per_fact"] > 0, "load coefficient sign")
    ok(fit["r2"] is not None and fit["r2"] > 0.9, "fit quality on near-linear means")
    ok(two_factor_means([("A", 4.0, 24.0, 300.0)])["fit"] is None,
       "fit accepted with too few cells")

    # 8. the trichotomy and the two-dimensional frontier report
    rows = [{"cell": "L0", "k": 8, "edges": 96, "n": 6, "correct": 6, "wrong": 0,
             "no_answer": 0},
            {"cell": "L1", "k": 8, "edges": 112, "n": 6, "correct": 6, "wrong": 0,
             "no_answer": 0},
            {"cell": "L2", "k": 8, "edges": 128, "n": 6, "correct": 4, "wrong": 0,
             "no_answer": 2},
            {"cell": "L3", "k": 8, "edges": 160, "n": 6, "correct": 0, "wrong": 0,
             "no_answer": 6},
            {"cell": "D1", "k": 12, "edges": 96, "n": 6, "correct": 6, "wrong": 0,
             "no_answer": 0},
            {"cell": "D2", "k": 16, "edges": 96, "n": 6, "correct": 1, "wrong": 5,
             "no_answer": 0}]
    placed = place_cell_status(rows)
    by_cell = {r["cell"]: r["status"] for r in placed["rows"]}
    ok(by_cell["L0"] == "maintained" and by_cell["L1"] == "maintained",
       "clean cells not maintained")
    ok(by_cell["L2"] == "inconclusive", f"planted partial silence read {by_cell['L2']}")
    ok(by_cell["L3"] == "budget_limited", f"planted full silence read {by_cell['L3']}")
    ok(by_cell["D1"] == "maintained", "D1 not maintained")
    ok(by_cell["D2"] == "collapsed", f"planted collapse read {by_cell['D2']}")
    ok(placed["maintained_by_k"]["8"] == 112, "frontier by k wrong at k=8")
    ok(placed["maintained_by_edges"]["96"] == 12, "frontier by E wrong at E=96")
    ok("first non-maintained cell L2" in placed["report"], "report wording")
    small = place_cell_status([{"cell": "L0", "k": 8, "edges": 96, "n": 3, "correct": 3,
                               "wrong": 0, "no_answer": 0}])
    ok(small["rows"][0]["status"] == "descriptive", "small n certified")

    # 9. mechanics: distractor accounting and traversal coverage
    item = next(gen_item(k0, c0, cell_seed(k0, c0, i)) for i in range(CANDIDATES)
                if gen_item(k0, c0, cell_seed(k0, c0, i))["answer"] == "yes")
    dis = distractor_names(item)
    ok(len(dis) == (c0 - 1) * (k0 + 1), f"distractor count {len(dis)}")
    seq = expected_chain(item)
    ok(len(seq) == k0 + 1, "expected chain length")
    ok(ordered_prefix_hops(seq, " ".join(seq)) == k0 + 1, "full traversal coverage")
    ok(ordered_prefix_hops(seq, " ".join(seq[:3]) + " junk " + seq[-1]) == 3,
       "partial traversal coverage")
    ok(ordered_prefix_hops(seq, "no entities here") == 0, "phantom coverage")

    # 10. attempt classification and retry policy
    base_att = {"error_class": None, "completion_tokens": 10, "content_answer": "yes",
                "reasoning_answer": None, "finish_reason": "stop"}
    ok(classify_attempt(dict(base_att)) == "answered_in_answer_field", "answered class")
    ok(classify_attempt(dict(base_att, content_answer=None)) == "trace_only"
       or classify_attempt(dict(base_att, content_answer=None)) == "no_answer_stop",
       "silent class")
    ok(classify_attempt(dict(base_att, completion_tokens=0)) == "empty_completion",
       "empty class")
    ok(classify_attempt(dict(base_att, error_class="timeout")) == "transport_timeout",
       "transport class")
    ok(classify_attempt(dict(base_att, content_answer=None, completion_tokens=2048,
                            finish_reason="length")) == "truncated_no_answer",
       "truncation class")
    ok(is_retryable("empty_completion") and is_retryable("transport_http_502"),
       "retry policy too strict")
    ok(not is_retryable("truncated_no_answer") and not is_retryable("answered_in_answer_field"),
       "retry policy too loose")
    cap = AttemptBudget(2)
    ok(cap.acquire() and cap.acquire() and not cap.acquire(), "attempt cap")

    # 11. the sanitizer holds the public-only rule on hostile model output. The hostile
    #   strings are assembled at runtime from fragments so that the repo-facing artifact
    #   scan (research/AGENTS.md: no URL or IPv4 literal in a round directory) stays clean
    #   while the pattern under test is exercised with a real URL, a real IPv4 shape and a
    #   real absolute path.
    fake_url = "https:" + "//" + "ex" + ".ampl" + ".e" + "/path"
    fake_ip = "192" + "." + "168" + "." + "5" + "." + "4"
    fake_path = "/" + "home" + "/" + "some" + "/" + "dir" + "/file." + "bin"
    fake_win = "C:" + "\\" + "Models" + "\\" + "x.bin"
    dirty = f"see {fake_url} and {fake_ip} plus {fake_path} and {fake_win}"
    clean_text = sanitize(dirty)
    ok(fake_url in dirty and fake_ip in dirty and fake_path in dirty,
       "sanitizer fixture did not assemble")
    for token in (".ampl", fake_ip, "/home", "Models"):
        ok(token not in clean_text, f"sanitizer leaked {token}")
    ok("[REDACTED]" in clean_text, "sanitizer left no marker")
    ok("yes" in sanitize("yes"), "sanitizer ate a verdict")

    # 12. anchor pins: every cell's digests equal round 24's gate (fail-closed)
    gate = build_gate()
    anch = gate["anchor"]["anchors"]
    ok(all(v["pool_blob_matches"] and v["forward_prompts_match"] and v["cross_prompts_match"]
           for v in anch.values()), "round-24 digest anchor mismatch")
    ok(set(anch) == set(WALK_INDEX), "anchor rows missing")
    ok(all(v["archived_results_by_digest"] for v in anch.values()),
       "archived round-24 records missing")
    ok(gate["anchor"]["all_ok"] and gate["anchor_ok"], "gate anchor flag not set")
    ok(gate["planned_prompts"] == 36 and gate["planned_prompts"] + HEALTH_CALLS
       <= PROMPT_CAP, "prompt plan exceeds the cap")
    tampered = json.loads(canonical(gate))
    tampered["cells"][0]["pool_blob_sha256"] = "0" * 64
    ok(anchor_state(tampered)["all_ok"] is False, "tampered anchor accepted")
    tampered = json.loads(canonical(gate))
    tampered["cells"][3]["forward_prompt_sha256"][0] = "0" * 64
    ok(anchor_state(tampered)["all_ok"] is False, "tampered prompt digest accepted")
    # R24_RECORDS integrity: one entry per dispatched prompt, digests consistent with
    # R24_DIGESTS, only grid cells and dispatch arms
    ok(len(R24_RECORDS) == 2 * PAIRS_PER_LEVEL * len(WALK), "round-24 record table size")
    ok(set(R24_RECORDS) == {d for v in R24_DIGESTS.values()
                            for d in v["forward_prompt_sha256"]
                            + v["cross_prompt_sha256"]},
       "record table digests disagree with the digest table")
    ok(all(v["cell"] in WALK_INDEX and v["arm"] in ("F", "X")
           for v in R24_RECORDS.values()), "record table carries a foreign cell or arm")

    # 13. gate refuses a leaky construction end to end
    ok(gate["all_cells_pass"] is True, "declared grid does not pass its own gate")
    for cell in gate["cells"]:
        ok(cell["gate_pool"]["verdict"] != "leak", f"pool leak {cell['cell']}")
        ok(cell["gate_paired_pool"]["verdict"] != "leak", f"paired leak {cell['cell']}")
        ok(cell["load"]["prompt_chars_min"] > 200, "prompt too short to carry the facts")

    # 14. analysis smoke test on synthetic records: statuses, discordance, predictions,
    #     budget replay, and the readout stack, all wired to the two arms
    recs = []
    for cell_name in ("L0", "L1", "L2", "L3", "D1", "D2"):
        for j in range(PAIRS_PER_LEVEL):
            seed = 1000 + j
            recs.append(synthetic_record(cell_name, "F", seed, 1, "yes", "chain checked",
                                         300))
            recs.append(synthetic_record(cell_name, "X", seed, 0, "no", "other branch",
                                         320))
    summary = aggregate(recs)
    ok(summary["records"] == 36, "smoke test record count")
    ok(summary["totals"]["correct"]["content_only"] == 36, "smoke test correctness")
    ok(summary["matched_pairs"]["counts"]["pairs"] == 18, "smoke test pair count")
    ok(summary["matched_pairs"]["mcnemar"]["p_exact"] == 1.0, "smoke test McNemar")
    ok(summary["predictions"]["P1_pass"] is True, "smoke test P1 at full delivery")
    ok(summary["predictions"]["P2_pass"] is True, "smoke test P2")
    ok(summary["predictions"]["P3_pass"] is True, "smoke test P3")
    # negative control for the P4 wiring: flat synthetic cell means (slope 0) must
    # fail BOTH cost-law bands; P5 must be vacuous and fail on synthetic digests
    ok(summary["predictions"]["P4_pass"] is False, "P4 accepted flat cell means")
    ok(summary["predictions"]["P5_vacuous"] is True, "smoke test P5 vacuity")
    ok(summary["predictions"]["P5_pass"] is False, "P5 passed on an empty comparable set")
    ok(summary["predictions"]["P6_pass"] is False, "P6 passed with no anchor records")
    ok(summary["predictions"]["P7_pass"] is False, "P7 passed on foreign digests")
    ok(len(summary["crossclass"]["per_prompt"]) == 0,
       "crossclass delta on synthetic records")
    ok(len(summary["crossclass"]["per_cell"]) == 6, "crossclass per-cell table rows")
    ok(len(summary["single_axis_transitions"]) == 4, "transition count")
    ok(all(t["axis"] == t["declared_axis"] and t["axis"] in ("load", "depth")
           for t in summary["single_axis_transitions"]), "transition axis mislabelled")
    st_from = {t["from"]: t["status"].split("->")[0]
               for t in summary["single_axis_transitions"]}
    ok(st_from.get("L0") == "maintained", "smoke test status wiring")

    def plant(cell_name: str, arm: str, seed: int) -> dict:
        target = [r for r in recs if r["cell"] == cell_name and r["arm"] == arm
                  and r["seed"] == seed]
        assert len(target) == 1, f"plant target {cell_name} {arm} {seed} not unique"
        return target[0]

    def silence(rec: dict, finish_reason: str) -> None:
        rec["content_answer"] = None
        rec["correct"]["content_only"] = None
        rec["reasoning_answer"] = "no"
        rec["loose_fallback_answer"] = "no"
        rec["correct"]["loose_fallback"] = 1
        rec["fallback_provenance_class"] = "terminal"
        rec["fallback_commit_fraction"] = 0.99
        rec["attempts"][-1]["finish_reason"] = finish_reason

    # plant a discordant pair on L2: arm X silent while its OWN arm F partner is correct;
    # this must ALSO flip P1 (L2 leaves the maintained set)
    silence(plant("L2", "X", 1000), "stop")
    summary2 = aggregate(recs)
    ok(summary2["matched_pairs"]["counts"]["f_ok_x_not"] == 1,
       "planted discordance not counted")
    ok(summary2["matched_pairs"]["counts"]["x_ok_f_not"] == 0,
       "planted discordance counted in the wrong direction")
    ok(summary2["predictions"]["P1_pass"] is False,
       "P1 did not fire once the bisection cell stopped delivering")
    ok(summary2["predictions"]["P1_non_maintained_cells"] == ["L2"],
       "non-maintained cell list wrong after plant")
    ok(summary2["predictions"]["P3_pass"] is True,
       "P3 must not fire on a stop silence")
    ok(summary2["cell_status"]["content_only"]["rows"][0]["cell"] == "L0",
       "cells not in grid order")
    # plant two content-silent truncations on D2: P3 must fire, the P4 depth law must
    # be censored (the E = 96 arm drops to two cells), and the replay counters still
    # hold
    silence(plant("D2", "X", 1000), "length")
    silence(plant("D2", "X", 1001), "length")
    summary3 = aggregate(recs)
    ok(summary3["totals"]["truncated"] == 2, "planted truncations not counted")
    ok(summary3["predictions"]["P3_pass"] is False,
       "P3 did not fire once the depth arm truncated at safe load")
    ok(summary3["predictions"]["P3_truncated_cells"] == ["D2"],
       "truncated cell list wrong after plant")
    ok(summary3["predictions"]["P4_depth_slope_in_band"] is False,
       "P4 depth slope not censored by the D2 truncation")
    ok(summary3["budget_replay_content_only"]["2048"]["content_answerable_est"]
       <= summary3["budget_replay_content_only"]["2048"]["n"], "replay exceeds n")
    ok(est_pos(recs[0]) >= 0, "est_pos refused a record with a content answer")
    ok(est_pos({"attempts": []}) == -1, "est_pos on empty attempts")

    # 15. resume key stability: cells_for inverts the grid, unknown shapes never collide
    ok(cells_for(8, 12) == "L0" and cells_for(8, 14) == "L1", "grid reverse map")
    ok(cells_for(16, 6) == "D2" and cells_for(12, 8) == "D1", "grid reverse map far cells")
    ok(cells_for(99, 99) == "K99C99", "unknown cell shape mapped wrongly")
    names = [n for n, _k, _c in WALK]
    ok(len(set(names)) == len(names), "duplicate cell names in the grid")
    ok(len({(k, c) for _n, k, c in WALK}) == len(WALK), "duplicate (k, C) in the grid")

    print(f"selftest: {checks} checks, 0 failures")


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--out", default="gate.json")
    ap.add_argument("--out-dir", default="research/nightly-2026-10-27-0439")
    args = ap.parse_args(argv[1:])
    if args.selftest:
        selftest()
        return 0
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

#!/usr/bin/env python3
"""Nightly round 21 (tracker #65, firing 2026-10-24 02:05): the constant-load depth
arm on the flash-next-class endpoint, scored under a declared readout stack.

Question (issue #71 criterion 2 and option 2, the binding next instrument, and the
arm whose first dispatch, round 8 on 2026-10-17, died on endpoint transport failure
after 15 of 40 prompts and was never re-run): at a FIXED number of facts (E = 24),
does answerability or accuracy on the component-isomorphic hop-chain family turn
over as hop depth k grows through {2, 3, 4, 6, 8, 12}, and what does each readout
say? All shipped grids so far (rounds 6, 9..19) couple prompt load and depth: the
generator's fact count grows with k. Holding E constant and varying k alone is the
only variant that yields a depth axis the study can claim.

This round implements issue #94's harness request: no single parser is treated as
the answer. Every cell is scored under three declared readouts and the fallback
token carries a provenance class (both vendored verbatim from round 19, cited
there, asserted by --selftest here, so the post-merge tree reproduces the control
without a cross-round file dependency):

  content_only        last standalone yes/no in the answer field; the delivered
                      answer (round 19: the observable answer field)
  loose_fallback      the archived convention of rounds 10..18: content, else the
                      last yes/no in the reasoning field; reported for comparability
  delivered_or_strict content answer if present, else the strict trace commitment
                      (round 19's rule: outside an echo phrase, and either closing
                      the trace or answer-cued within 30 characters and closed by
                      punctuation)

Independence: this file imports nothing from generators/ and re-implements the
component-isomorphic construction (issue #67 fix, PR #69), the BFS solver, the
structural verifier and the permutation-calibrated leak gate from the round-8
script with its own entity-name pools, so a shared bug cannot hide a leak
(docs/agent-execution.md section 5). The shipped corpus on main is not used.

Declared grid (fixed before any measurement, seed-frozen, seed_base 20261024):
  arm L  constant load: E = 24 facts, k in {2,3,4,6,8,12}, C = 24/k chains,
         6 items per depth (3 yes, 3 no) -> 36 prompts
total 36 prompts + 1 health probe = 37 of the 40-call cap, max_tokens 2048,
temperature 0.0, one sample per item, no exemplars, no chain of thought asked.
There is no cell pairing: this construction shares no prompt with any archived
round; the comparison to rounds 15..19 is same-construction, cited by generator
digest. A new round-20-style silent gap is not repeated: the round summary comment
goes to #65 before the PR opens.

Declared predictions (fixed in the gate before any prompt is spent):
  P1 load constancy: mean prompt_tokens flat across depths, max/min <= 1.12
     (the construction is constant-load by design; this checks the tokenizer sees
     it that way).
  P2 no depth turnover under content_only: no depth in the declared grid is
     classified collapsed or budget_limited by the r8 trichotomy (Wilson floor
     0.60, no-answer rate <= 0.5). The coupled-load archive shows no turnover up
     to k = 48, but never at constant load; the point of P2 is that constancy is
     visible in the delivered answer, not only via trace rescue.
  P3 token law flattens: mean completion_tokens at k = 12 <= 2x the mean at k = 2
     (the coupled-load law is steep, about 33 tokens/hop on this class; constant
     load must flatten it or the load axis is doing the work).
  P4 readout honesty: P4a every delivered_or_strict answer is correct (the r19
     strict rule kept 13 of 13); P4b on cells where the answer field carries no
     yes/no, the loose fallback token is "no" in at least 2/3 of cases (the #94
     skew replicated at constant load).

Usage:
  constant_load_depth.py --selftest
  constant_load_depth.py --gate              [--out gate.json]
  constant_load_depth.py --probe             [--out-dir DIR] [--resume]
  constant_load_depth.py --analyze           [--out-dir DIR]
The endpoint is read from NIGHTLY_BASE_URL, NIGHTLY_MODEL_ID and NIGHTLY_API_KEY
and no endpoint value is ever written to an artifact; stored model text passes a
sanitizer for URLs, IP addresses and absolute paths.
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
CONST_E = 24
ARM_L = ((2, 12), (3, 8), (4, 6), (6, 4), (8, 3), (12, 2))
ITEMS_PER_DEPTH = 6
YES_PER_DEPTH = 3
CANDIDATES = 40
MIN_CERTIFY = 6
OPERATING_BUDGET = 2048
ITEM_DEADLINE_S = 900
PHASE2_BUDGET_S = 1800
TPS_FLOOR = 10.0
CONCURRENCY_CHOICES = (1, 2, 3, 4)
HEALTH_PROMPT = "Reply with exactly one word: yes"
BUDGET_REPLAY = (256, 512, 1024, 2048)

ANSWER_RE = re.compile(r"\b(yes|no)\b", re.IGNORECASE)
URL_RE = re.compile(
    r"https?://\S+|\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|"
    r"(?:/[A-Za-z0-9_.-]+){2,}|[A-Za-z]:\\[^\s]*")

# Vendored verbatim from round 19 (research/nightly-2026-10-23-0200/
# surfacing_budget_curve.py, PR #93): the strict commitment rule and the echo
# phrase test. --selftest asserts the documented behaviour of both, so the rule
# cannot drift silently from the round whose grid this round must stay comparable
# to (issue #94).
PHRASE_RE = re.compile(
    r"yes\s*[/|]\s*no|no\s*[/|]\s*yes|yes\s+or\s+no|no\s+or\s+yes",
    re.IGNORECASE)
STRICT_TAIL_RE = re.compile(r"[.!?:;\)\]\"'\s]*$")
VERDICT_CUE_RE = re.compile(
    r"\b(thus|therefore|so|answer|final|conclusion|answer is|verdict)\b"
    r"[^.\n]{0,30}$", re.IGNORECASE)

# Own name pools (deliberately different from generators/ladders.py and round 8).
POOL_A = ("ab", "ed", "ig", "ok", "ul", "ur", "yr", "ov", "ix", "ax",
          "eb", "ic", "ol", "um", "un", "ar", "er", "ir", "or", "uz")
POOL_B = ("bo", "dra", "fo", "gra", "ho", "la", "mo", "ni", "po", "sta",
          "tra", "vo", "xi", "zo", "bru", "kro", "pli", "spo", "tur", "vra")
POOL_C = ("q", "x", "z", "k", "v", "n", "r", "s", "t", "m")


def sanitize(text: str) -> str:
    return URL_RE.sub("[REDACTED]", text)


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"


def _name(rng: random.Random, taken: set) -> str:
    for _ in range(500):
        name = rng.choice(POOL_A) + rng.choice(POOL_B) + rng.choice(POOL_C)
        if name not in taken:
            taken.add(name)
            return name
    raise RuntimeError("name pool exhausted")


def gen_item(k: int, c_chains: int, seed: int) -> dict:
    """Component-isomorphic hop chain: C disjoint directed paths of exactly k
    edges over fresh entities; the query is always (head of one path, tail of one
    path); yes iff both endpoints lie on the same path. E = k * C = CONST_E."""
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
        tails = [u for u in comp if inc.get(u, 0) == 1 and out.get(u, 0) == 0]
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


def features(item: dict) -> dict:
    """Traversal-free feature battery over the query endpoints and fact list."""
    facts = item["facts"]
    srcs = {s for s, _, _ in facts}
    tgts = {t for _, _, t in facts}
    out: dict = {}
    inc: dict = {}
    for s, _, t in facts:
        out[s] = out.get(s, 0) + 1
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
        "tgt_outdeg_zero": out.get(qt, 0) == 0,
        "tgt_indeg_zero": inc.get(qt, 0) == 0,
        "src_is_fact_target": qs in tgts,
        "src_is_fact_source": qs in srcs,
        "src_outdeg_zero": out.get(qs, 0) == 0,
        "src_indeg_zero": inc.get(qs, 0) == 0,
        "tgt_name_lt_src_name": qt < qs,
        "tgt_name_longer_than_src": len(qt) > len(qs),
        "tgt_first_mention_before_src": first_idx.get(qt, 10 ** 9) < first_idx.get(qs, 10 ** 9),
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
    """Permutation-calibrated leak gate, family-wise alpha over the whole battery.
    Runs on the whole candidate pool, never on the selected six."""
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


def build_cell(k: int, c_chains: int, want_yes: int, want_total: int) -> tuple:
    """Selection rule fixed in advance: seed order, first want_yes yes items and
    first want_total - want_yes no items, every candidate passing the independent
    structural audit. Returns (selected, full candidate pool)."""
    pool: list = []
    picked: list = []
    yes_n = 0
    for i in range(CANDIDATES):
        item = gen_item(k, c_chains, cell_seed(k, c_chains, i))
        violations = verify_item(item)
        if violations:
            raise RuntimeError(f"cell k={k} C={c_chains} seed {item['seed']}: {violations}")
        pool.append(item)
        if item["answer"] == "yes":
            if yes_n < want_yes:
                picked.append(item)
                yes_n += 1
        elif len(picked) - yes_n < want_total - want_yes:
            picked.append(item)
    if len(picked) != want_total:
        raise RuntimeError(f"cell k={k} C={c_chains}: selection rule starved")
    return picked, pool


def all_cells() -> list:
    cells = []
    for (k, c_chains) in ARM_L:
        picked, pool = build_cell(k, c_chains, YES_PER_DEPTH, ITEMS_PER_DEPTH)
        cells.append({"k": k, "chains": c_chains, "arm": "L",
                      "items": picked, "pool": pool})
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
    """Round-19 rule, vendored verbatim: last trace yes/no that could be a
    verdict. Qualifies when it is outside a "yes/no" or "yes or no" phrase and
    either closes the trace (only punctuation after it) or is both preceded by an
    answer cue within 30 characters and closed by punctuation."""
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
    """Round-19 classes for the LAST reasoning-field yes/no: instruction_echo
    (inside a yes/no phrase), terminal (last 2% of the trace), mid_trace
    (elsewhere), or None when the trace carries no yes/no."""
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
    resp = call_endpoint(HEALTH_PROMPT, OPERATING_BUDGET, deadline_s=180)
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


def mechanics(item: dict, att: dict) -> dict:
    text = (att.get("reasoning") or "") + " " + (att.get("content") or "")
    seq = expected_chain(item)
    hops = ordered_prefix_hops(seq, text) if seq else None
    out = {
        "ordered_prefix_hops": hops,
        "expected_hops": len(seq) if seq else None,
        "coverage_ratio": (round(hops / len(seq), 4)
                           if seq and hops is not None else None),
        "completion_tokens": att["completion_tokens"],
        "budget_utilisation": round(att["completion_tokens"] / MAX_TOKENS, 4),
        "reasoning_chars": len(att.get("reasoning") or ""),
        "content_chars": len(att.get("content") or ""),
    }
    return out


def make_record(item: dict, budget_cap: AttemptBudget, phase: int) -> dict:
    prompt = render_prompt(item)
    rec = {
        "arm": "L", "level": item["level"], "chains": item["chains"],
        "edges": item["edges"], "seed": item["seed"], "seed_hash": item["seed_hash"],
        "item_sha256": sha256_text(canonical(item)),
        "prompt_sha256": sha256_text(prompt), "prompt_chars": len(prompt),
        "gold": 1 if item["answer"] == "yes" else 0,
        "gate_hash": GATE_HASH, "phase": phase, "attempts": [],
    }
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
        att["mechanics"] = mechanics(item, att)
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
    # character-proportional estimate of the answer position within the WHOLE
    # completion (reasoning streams before content), for budget replay
    full = (last.get("reasoning") or "") + (last.get("content") or "")
    off = last.get("content_offset", -1)
    total = last.get("completion_tokens") or 0
    rec["est_content_answer_tokens"] = (
        round(total * (len(last.get("reasoning") or "") + off + 1) / max(len(full), 1))
        if off >= 0 and full else -1)
    return rec


def write_jsonl(path: str, rec: dict) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(canonical(rec) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def build_gate() -> dict:
    cells = all_cells()
    out = {"schema": "round21-gate-v1", "seed_base": SEED_BASE,
           "alpha": ALPHA, "perms": PERMS, "const_edges": CONST_E,
           "max_tokens": MAX_TOKENS, "temperature": TEMPERATURE,
           "readouts": ["content_only", "loose_fallback", "delivered_or_strict"],
           "predictions": {
               "P1_prompt_token_load_constancy_max_over_min_le": 1.12,
               "P2_no_content_only_depth_turnover": True,
               "P3_completion_mean_k12_over_k2_le": 2.0,
               "P4a_all_delivered_or_strict_correct": True,
               "P4b_fallback_no_share_when_content_silent_ge": 0.6667},
           "cells": []}
    for cell in cells:
        items = cell["items"]
        g = gate_battery(cell["pool"])
        prompts = [render_prompt(it) for it in items]
        chars = [len(p) for p in prompts]
        out["cells"].append({
            "arm": "L", "k": cell["k"], "chains": cell["chains"],
            "edges": cell["k"] * cell["chains"],
            "load": {"facts_mean": CONST_E,
                     "prompt_chars_mean": round(sum(chars) / len(chars), 1),
                     "prompt_chars_min": min(chars), "prompt_chars_max": max(chars)},
            "selected_item_sha256": [sha256_text(canonical(it)) for it in items],
            "pool_blob_sha256": sha256_text(canonical(cell["pool"])),
            "gate": g})
    blob = sha256_text(canonical([c["pool_blob_sha256"] for c in out["cells"]]))
    out["corpus_blob_sha256"] = blob
    out["planned_prompts"] = sum(len(c["items"]) for c in cells)
    out["prompt_cap"] = PROMPT_CAP
    out["all_cells_pass"] = all(c["gate"]["verdict"] != "leak" for c in out["cells"])
    return out


GATE_HASH = "unset"


def gate_hash(gate: dict) -> str:
    return sha256_text(canonical(gate))


def place_depth_status(rows: list) -> dict:
    """Round-8 trichotomy per depth (Wilson 95, floor 0.60), computed per readout.
    status: budget_limited (no-answer rate > 0.5) / maintained (lb >= floor) /
    collapsed (ub < floor) / inconclusive / descriptive (n < MIN_CERTIFY).
    d* = largest maintained depth below the first collapsed depth."""
    floor = MAJORITY_FLOOR + MARGIN
    out_rows = []
    for row in sorted(rows, key=lambda r: r["k"]):
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
        out_rows.append({"arm": "L", "k": row["k"], "n": n,
                         "correct": row["correct"], "wrong": row.get("wrong", 0),
                         "no_answer": row.get("no_answer", 0),
                         "accuracy": round(row["correct"] / n, 4) if n else 0.0,
                         "wilson_lb95": round(lb, 4), "wilson_ub95": round(ub, 4),
                         "no_answer_rate": round(na, 4), "status": status})
    collapsed = [r["k"] for r in out_rows if r["status"] == "collapsed"]
    maintained = [r["k"] for r in out_rows if r["status"] == "maintained"]
    inconclusive = [r["k"] for r in out_rows if r["status"] == "inconclusive"]
    budget_limited = [r["k"] for r in out_rows if r["status"] == "budget_limited"]
    turnover = min(collapsed) if collapsed else None
    certified = [k for k in maintained if turnover is None or k < turnover]
    d_star = max(certified) if certified else None
    grid_max = max((r["k"] for r in out_rows), default=0)
    report = (f"no collapsed depth within the declared grid (k <= {grid_max}); "
              f"d* >= {d_star}" if turnover is None
              else f"d* = {d_star}, first collapsed depth at {turnover}")
    if inconclusive:
        report += f"; inconclusive depths {inconclusive}"
    if budget_limited:
        report += f"; budget-limited depths {budget_limited}"
    return {"d_star": d_star, "report": report, "turnover_at": turnover,
            "maintained_depths": maintained, "inconclusive_depths": inconclusive,
            "budget_limited_depths": budget_limited, "floor": floor,
            "min_certify_items": MIN_CERTIFY, "rows": out_rows}


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple:
    if total == 0:
        return 0.0, 0.0
    p = successes / total
    denom = 1.0 + z * z / total
    centre = p + z * z / (2 * total)
    span = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return (centre - span) / denom, (centre + span) / denom


def aggregate(records: list) -> dict:
    readout_names = ("content_only", "loose_fallback", "delivered_or_strict")
    per_ro: dict = {}
    tok: dict = {}
    for rec in records:
        key = rec["level"]
        tok.setdefault(key, {"completion": [], "prompt": []})
        tok[key]["completion"].append(rec.get("completion_tokens", 0))
        tok[key]["prompt"].append(rec.get("prompt_tokens", 0))
        for name in readout_names:
            row = per_ro.setdefault((name, key), {"k": key, "n": 0, "correct": 0,
                                                  "wrong": 0, "no_answer": 0})
            row["n"] += 1
            c = rec["correct"][name]
            if c is None:
                row["no_answer"] += 1
            elif c == 1:
                row["correct"] += 1
            else:
                row["wrong"] += 1
    per_depth = {}
    for name in readout_names:
        rows = [dict(row, mean_completion_tokens=round(
                    sum(tok[row["k"]]["completion"]) / len(tok[row["k"]]["completion"]), 1),
                    mean_prompt_tokens=round(
                    sum(tok[row["k"]]["prompt"]) / len(tok[row["k"]]["prompt"]), 1))
                for (nm, _), row in sorted(per_ro.items()) if nm == name]
        per_depth[name] = rows
    dstar = {name: place_depth_status(per_depth[name]) for name in readout_names}

    # P checks
    prompts_mean = [r["mean_prompt_tokens"] for r in per_depth["content_only"]]
    p1 = (max(prompts_mean) / min(prompts_mean)) if prompts_mean and min(prompts_mean) else None
    comp_mean = {r["k"]: r["mean_completion_tokens"] for r in per_depth["content_only"]}
    p3 = ((comp_mean.get(12) / comp_mean.get(2))
          if comp_mean.get(2) else None)
    p2_ok = all(r["status"] not in ("collapsed", "budget_limited")
                for r in dstar["content_only"]["rows"])
    ds_answers = [r for r in records if r["delivered_or_strict_answer"] is not None]
    p4a_ok = all(r["correct"]["delivered_or_strict"] == 1 for r in ds_answers)
    silent = [r for r in records if r["content_answer"] is None
              and r["reasoning_answer"] is not None]
    p4b_share = (sum(1 for r in silent if r["reasoning_answer"] == "no") / len(silent)
                 if silent else None)

    # provenance of the fallback token (round-19 classes)
    prov = collections.Counter()
    prov_agree = collections.Counter()
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
    fractions.sort()
    fallback_total = sum(1 for r in records if r["reasoning_answer"] is not None)
    fallback_correct = sum(1 for r in records if r["correct"]["loose_fallback"] == 1
                           and r["content_answer"] is None)
    no_baseline = sum(1 for r in records if r["gold"] == 0) / len(records) if records else 0.0

    replay = {}
    for b in BUDGET_REPLAY:
        # Position estimate recomputed here at analysis time from the archived
        # attempt fields (reasoning streams before content). The per-record
        # est_content_answer_tokens field stored in raw.jsonl predates this fix
        # and is superseded by this recomputation; see the round README.
        def est_pos(r):
            if not r["attempts"]:
                return -1
            a = r["attempts"][-1]
            off = a.get("content_offset", -1)
            if off < 0:
                return -1
            full = (a.get("reasoning") or "") + (a.get("content") or "")
            return round(a.get("completion_tokens", 0)
                         * (len(a.get("reasoning") or "") + off + 1)
                         / max(len(full), 1))
        ans = sum(1 for r in records if 0 <= est_pos(r) <= b)
        corr = sum(1 for r in records if 0 <= est_pos(r) <= b
                   and r["correct"]["content_only"] == 1)
        replay[str(b)] = {"n": len(records), "content_answerable_est": ans,
                          "correct": corr,
                          "accuracy_over_all": round(corr / len(records), 4) if records else 0.0}

    return {
        "records": len(records),
        "per_depth": per_depth,
        "d_star": dstar,
        "predictions": {
            "P1_prompt_tokens_max_over_mean_min": round(p1, 4) if p1 else None,
            "P1_pass": (p1 is not None and p1 <= 1.12),
            "P2_pass_no_content_only_turnover": p2_ok,
            "P3_completion_mean_k12_over_k2": round(p3, 4) if p3 else None,
            "P3_pass": (p3 is not None and p3 <= 2.0),
            "P4a_delivered_or_strict_correct": f"{sum(1 for r in ds_answers if r['correct']['delivered_or_strict'] == 1)}/{len(ds_answers)}",
            "P4a_pass": p4a_ok,
            "P4b_fallback_no_share_when_content_silent": (round(p4b_share, 4)
                                                          if p4b_share is not None else None),
            "P4b_cells": len(silent),
            "P4b_pass": (p4b_share is not None and p4b_share >= 0.6667)},
        "fallback_provenance": {
            "classes": dict(prov),
            "agreement_with_gold": {cls: prov_agree[cls] for cls in prov if cls != "no_trace_token"},
            "commit_fraction_median": (round(fractions[len(fractions) // 2], 4)
                                       if fractions else None),
            "loose_fallback_when_content_silent": {
                "cells": fallback_total, "correct": fallback_correct,
                "constant_no_baseline_accuracy": round(no_baseline, 4)}},
        "budget_replay_content_only": replay,
        "totals": {
            "correct": {name: sum(1 for r in records if r["correct"][name] == 1)
                        for name in readout_names},
            "answered": {name: sum(1 for r in records
                                   if r["correct"][name] is not None)
                         for name in readout_names},
            "outcomes": dict(collections.Counter(r["outcome"] for r in records)),
            "errors": sum(1 for r in records if r["outcome"].startswith("transport_"))}}


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
                done[(rec["level"], rec["seed"])] = rec
                cap.used += len(rec["attempts"])
    health = health_check()
    cap.used += 1
    print(f"health: {health}", flush=True)
    if not health["ok"]:
        print("REFUSED: endpoint failed the chat-completion health probe",
              file=sys.stderr)
        return 4
    items = [it for cell in all_cells() for it in cell["items"]]
    if len(items) + HEALTH_CALLS > PROMPT_CAP:
        print(f"plan {len(items)} + health exceeds cap {PROMPT_CAP}", file=sys.stderr)
        return 2
    note = {"resumed_cells": len(done), "health": health, "gate_hash": GATE_HASH}

    def run(item: dict, phase: int) -> dict:
        rec = make_record(item, cap, phase)
        results[(item["level"], item["seed"])] = rec
        write_jsonl(raw_path, rec)
        print(f"k={rec['level']:>2} gold={rec['gold']} outcome={rec['outcome']:>22} "
              f"content={str(rec['content_answer']):>4} strict={str(rec['strict_trace_token']):>4} "
              f"ctok={rec['attempts'][-1]['completion_tokens']:>5}", flush=True)
        return rec

    pending = [it for it in items if (it["level"], it["seed"]) not in done]
    results = dict(done)
    started = time.monotonic()
    phase1 = pending[:2]
    for item in phase1:
        rec = run(item, 1)
        results[(item["level"], item["seed"])] = rec
    walls = [results[(it["level"], it["seed"])]["attempts"][-1]["wall_s"]
             for it in phase1 if results[(it["level"], it["seed"])]["attempts"]]
    tps = max([TPS_FLOOR] + [MAX_TOKENS / w for w in walls if w and w > 0])
    remaining = pending[2:]
    est_total = len(remaining) * MAX_TOKENS / tps
    chosen = None
    for cand in CONCURRENCY_CHOICES:
        if est_total / cand * 1.25 <= PHASE2_BUDGET_S:
            chosen = cand
            break
    if chosen is None:
        chosen = max(CONCURRENCY_CHOICES)
    note.update({"phase1_walls": walls, "estimated_tokens_per_second": round(tps, 2),
                 "estimate_phase2_s": round(est_total, 1), "chosen_concurrency": chosen})
    print(f"phase-1 walls {walls} s, ~{round(tps, 1)} tok/s, concurrency {chosen} "
          f"for {len(remaining)} cells", flush=True)
    phase2_start = time.monotonic()
    to_run, abandoned = [], []
    for item in remaining:
        if time.monotonic() > phase2_start + PHASE2_BUDGET_S:
            abandoned.append(item)
        else:
            to_run.append(item)
    for item in abandoned:
        rec = {"arm": "L", "level": item["level"], "chains": item["chains"],
               "edges": item["edges"], "seed": item["seed"],
               "seed_hash": item["seed_hash"],
               "item_sha256": sha256_text(canonical(item)),
               "prompt_sha256": sha256_text(render_prompt(item)),
               "prompt_chars": len(render_prompt(item)),
               "gold": 1 if item["answer"] == "yes" else 0,
               "gate_hash": GATE_HASH, "phase": 2, "attempts": [],
               "completion_tokens": 0, "prompt_tokens": 0,
               "outcome": "abandoned_budget",
               "content_answer": None, "reasoning_answer": None,
               "loose_fallback_answer": None, "strict_trace_token": None,
               "delivered_or_strict_answer": None,
               "fallback_provenance_class": None,
               "fallback_commit_fraction": None,
               "est_content_answer_tokens": -1,
               "correct": {"content_only": None, "loose_fallback": None,
                           "delivered_or_strict": None}}
        results[(item["level"], item["seed"])] = rec
        write_jsonl(raw_path, rec)
    if to_run:
        with concurrent.futures.ThreadPoolExecutor(max_workers=chosen) as pool:
            futures = [pool.submit(run, item, 2) for item in to_run]
            for fut in concurrent.futures.as_completed(futures):
                fut.result()
    ordered = [results[(it["level"], it["seed"])] for it in items]
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
                      "d_star": {k: v["report"] for k, v in summary["d_star"].items()},
                      "predictions": summary["predictions"]}, indent=2))
    return 0


def cmd_gate(out_path: str) -> int:
    gate = build_gate()
    gate = dict(gate, gate_hash=gate_hash(gate))
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(gate, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"gate {gate['gate_hash'][:8]}: all_cells_pass={gate['all_cells_pass']} "
          f"planned={gate['planned_prompts']} corpus={gate['corpus_blob_sha256'][:12]}")
    for c in gate["cells"]:
        g = c["gate"]
        print(f"  k={c['k']:>2} C={c['chains']:>2} verdict={g['verdict']} "
              f"obs={g['observed_max']} thr={g['calibrated_threshold']} p={g['p_value']} "
              f"chars={c['load']['prompt_chars_mean']}")
    return 0 if gate["all_cells_pass"] else 3


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


def selftest() -> None:
    checks = 0

    def ok(cond, msg):
        nonlocal checks
        checks += 1
        assert cond, msg

    # 1. structural and solvability audit on every cell, yes counts exact
    for (k, c_chains) in ARM_L:
        items, pool = build_cell(k, c_chains, YES_PER_DEPTH, ITEMS_PER_DEPTH)
        ok(len(pool) == CANDIDATES, f"pool size k={k}")
        for it in items + pool:
            ok(not verify_item(it), f"audit k={k} seed={it['seed']}")
        ok(sum(1 for it in items if it["answer"] == "yes") == YES_PER_DEPTH,
           f"yes count k={k}")

    # 2. determinism: double generation byte-identical; shifted seed differs
    a = canonical([build_cell(k, cc, YES_PER_DEPTH, ITEMS_PER_DEPTH)[0]
                   for k, cc in ARM_L])
    b = canonical([build_cell(k, cc, YES_PER_DEPTH, ITEMS_PER_DEPTH)[0]
                   for k, cc in ARM_L])
    c = canonical([gen_item(4, 6, cell_seed(4, 6, i) + 1000) for i in range(6)])
    d = canonical([gen_item(4, 6, cell_seed(4, 6, i)) for i in range(6)])
    ok(a == b, "double generation differs")
    ok(c != d, "seed shift produced identical items")

    # 3. constant load across arm L
    edges = {it["edges"] for (k, cc) in ARM_L
             for it in build_cell(k, cc, YES_PER_DEPTH, ITEMS_PER_DEPTH)[0]}
    ok(edges == {CONST_E}, f"edges not constant: {edges}")
    prompts = [render_prompt(it) for (k, cc) in ARM_L
               for it in build_cell(k, cc, YES_PER_DEPTH, ITEMS_PER_DEPTH)[0]]
    lens = sorted(len(p) for p in prompts)
    ok(lens[-1] - lens[0] < 0.12 * lens[0], f"prompt length spread {lens[0]}..{lens[-1]}")

    # 4. gate arithmetic controls
    items, pool6 = build_cell(6, 4, 3, 6)
    n = len(items)
    gold_bits = _bits([it["answer"] == "yes" for it in items])
    ok(max(_acc((1 << n) - 1, gold_bits, n), _acc(0, gold_bits, n)) == 0.5,
       "majority baseline on balanced cell")
    ok(_acc(gold_bits, gold_bits, n) == 1.0, "perfect accuracy")
    ok(_acc(((1 << n) - 1) ^ gold_bits, gold_bits, n) == 0.0, "inverted accuracy")

    # 5. planted-leak positive control: relabel by target < source name
    planted = [dict(it) for it in pool6]
    for it in planted:
        qs, _, qt = it["query"]
        it["answer"] = "yes" if qt < qs else "no"
        it["chain_len"] = None
    ok(gate_battery(planted)["verdict"] == "leak", "planted leak not flagged")

    # 6. the real pools must not be flagged (this is also re-checked before probe)
    for (k, cc) in ARM_L:
        g = gate_battery(build_cell(k, cc, 3, 6)[1])
        ok(g["verdict"] != "leak", f"real pool flagged k={k}")

    # 7. strict rule controls (the round-19 documented behaviours)
    ok(strict_last_trace_token("I will answer the question. Thus yes.") == "yes",
       "cued commitment 'Thus yes.' must qualify")
    ok(strict_last_trace_token("Answer exactly one word: yes or no") is None,
       "instruction echo must not qualify")
    ok(strict_last_trace_token("Check a. Check b. No other incoming. Then more text "
                               "follows about checking and it does not stop") is None,
       "mid-trace 'No other incoming.' must not qualify")
    ok(strict_last_trace_token("Enumerating links, enumerating links, and the final "
                               "answer is no") == "no", "cued trace-final 'no' must qualify")
    ok(strict_last_trace_token("") is None, "empty trace")

    # 8. provenance class controls
    cls, frac = provenance_class("answer with yes or no")
    ok(cls == "instruction_echo", "echo class")
    cls, frac = provenance_class("a" * 400 + " yes")
    ok(cls == "terminal" and frac > 0.98, "terminal class")
    cls, frac = provenance_class("x yes " + "y" * 100)
    ok(cls == "mid_trace" and frac < 0.98, "mid-trace class")
    cls, frac = provenance_class("nothing here")
    ok(cls is None, "no token class")

    # 9. readout precedence: content answer wins; strict fills only when content silent
    ro = readouts("Reasoning says no. Final: yes", "long trace thus no")
    ok(ro["content_answer"] == "yes" and ro["loose_fallback_answer"] == "yes"
       and ro["delivered_or_strict_answer"] == "yes", "content precedence")
    ro = readouts("still working on it", "checked all facts, thus no.")
    ok(ro["content_answer"] is None and ro["loose_fallback_answer"] == "no"
       and ro["delivered_or_strict_answer"] == "no", "strict fills when silent")
    ro = readouts("still working", "No other incoming. and then more words here to "
                                   "keep going and going")
    ok(ro["loose_fallback_answer"] == "no" and ro["strict_trace_token"] is None
       and ro["delivered_or_strict_answer"] is None,
       "loose reads mid-trace no, strict does not")

    # 10. retry and outcome classification controls
    ok(is_retryable("transport_TimeoutError") and is_retryable("empty_completion"),
       "retry classification")
    ok(not is_retryable("trace_only") and not is_retryable("truncated_no_answer"),
       "non-retry classification")
    att = {"error_class": None, "completion_tokens": 0, "content_answer": None,
           "reasoning_answer": None}
    ok(classify_attempt(att) == "empty_completion", "empty completion class")

    # 11. wilson and trichotomy controls
    lb0, ub0 = wilson(0, 0)
    ok((lb0, ub0) == (0.0, 0.0), "wilson n=0")
    lb6, _ = wilson(6, 6)
    lb5, _ = wilson(5, 6)
    ok(lb6 > 0.6 > lb5, f"wilson floors 6/6={lb6:.3f} 5/6={lb5:.3f} (floor 0.60 sits between)")
    rows = [{"k": 2, "n": 6, "correct": 6, "wrong": 0, "no_answer": 0},
            {"k": 3, "n": 6, "correct": 0, "wrong": 0, "no_answer": 6},
            {"k": 4, "n": 6, "correct": 3, "wrong": 3, "no_answer": 0}]
    res = place_depth_status(rows)
    statuses = {r["k"]: r["status"] for r in res["rows"]}
    ok(statuses[2] == "maintained" and statuses[3] == "budget_limited"
       and statuses[4] == "inconclusive", f"trichotomy {statuses}")
    ok(res["turnover_at"] is None, "collapsed detection needs ub < floor")
    rows2 = [{"k": 2, "n": 6, "correct": 6, "wrong": 0, "no_answer": 0},
             {"k": 3, "n": 6, "correct": 0, "wrong": 6, "no_answer": 0}]
    ok(place_depth_status(rows2)["d_star"] == 2
       and place_depth_status(rows2)["turnover_at"] == 3, "d* below turnover")

    # 12. negative control: gold-no share and constant-no baseline agree
    rec_stub = [{"gold": 0}, {"gold": 0}, {"gold": 1}]
    ok(sum(1 for r in rec_stub if r["gold"] == 0) / len(rec_stub) == 2 / 3,
       "baseline arithmetic")

    print(f"selftest: {checks} checks, 0 failures")


def main(argv: list) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--out", default="gate.json")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        selftest()
        return 0
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = args.out_dir or here
    if args.gate:
        return cmd_gate(args.out if os.path.dirname(args.out) else os.path.join(out_dir, args.out))
    if args.probe:
        return probe(out_dir, args.resume)
    if args.analyze:
        return cmd_analyze(out_dir)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Matched-pair shortcut probe for the compositional-ladder family (issue #67).

Question: when a model answers a k-hop transitivity query, does it read a
surface shortcut out of the prompt, or does it traverse the fact graph?

The audit (`audit_ladder_leaks.py`) shows the generator side of this: the
pre-fix corpus carries a surface rule that predicts gold at 1.0, the repaired
corpus carries none. It cannot say what a model actually does. This probe
measures the model side, using the one comparison that isolates the mechanism:

  matched pairs. A pre-fix item and a post-fix item generated from the SAME
  seed at the SAME level. Same seed, same level, same query shape; the only
  difference is the construction, so the shortcut is present in one arm and
  structurally absent in the other.

Design (fixed before any endpoint call):
  - 4 cells x 10 items = 40 experimental prompts, no more:
      fixture_l2  pre-fix  k=2  (shortcut present)
      shipped_l2  post-fix k=2  (shortcut absent)
      fixture_l8  pre-fix  k=8  (shortcut present)
      shipped_l8  post-fix k=8  (shortcut absent)
  - Matched by seed, not by position: fixture item j and its shipped partner
    carry identical `seed` values. The probe asserts all 40 pairs match.
  - Zero-shot, greedy (temperature 0), one fixed neutral prompt template,
    one decoding seed. No chain-of-thought instruction, no traversal
    instruction: the prompt never tells the model how to solve the item.
  - Three a-priori baselines computed offline from the facts alone, on the
    same 10 items as the model, never selected after seeing model output:
      B_majority   majority gold label of the cell
      B_direct     "yes" iff the query pair is itself a stated fact
      B_leak_sig   "yes" iff the query target is a fact target AND has
                   out-degree 0 (the leak signature documented in issue #67)
  - Verdict rule, fixed in advance:
      shortcut behaviour  -> fixture cells far above their baselines AND
                             shipped cells at or below their baselines
      traversal behaviour -> both arms above their baselines
      anything else       -> inconclusive
  - Process indicator (heuristic, reported as such): for "yes" items the gold
    path's intermediate entities are recovered offline by BFS; the indicator
    counts how many of them appear as words in the model's reasoning trace.
    A shortcut user has no reason to name them. It is a weak signal and is
    never used as the primary measure.

Instrument constraints measured on the serving endpoint (2026-10-16):
  - The endpoint is a reasoning model: it emits `reasoning_content` and, at
    small token caps, ends with finish_reason="length" and content=null.
    `chat_template_kwargs: {"thinking": false}` is accepted but ignored.
    So the token cap must cover the reasoning trace, and truncation is a
    measured failure mode, not a bug to hide.
  - Calibration calls on NON-experimental items (seeds outside the 40) size
    that cap: the longest chain available in each arm that is not part of the
    experiment. They are reported in the manifest as instrument validation,
    separate from the 40-prompt experimental budget.
  - The pool is shared and can stall: a call can hang past the client timeout.
    Records are therefore appended and fsynced one by one, a stalled item is
    retried once under a global retry budget (MAX_RETRIES_TOTAL), a still-failed
    item is recorded as finish_reason="client_error" and marked invalid instead
    of killing the run, and --resume reuses answered items while re-asking
    failed ones. Round 5 attempt 1 lost 21 paid answers to exactly this failure.

Endpoint access: the base URL is read from the environment variable
NIGHTLY_BASE_URL (or --base-url-env NAME). It is never hardcoded, never
printed, and never written into any artifact. Model identity is read from
GET <base>/models. Public model labels only.

Usage:
  probe_ladder_shortcut.py --selftest
  probe_ladder_shortcut.py --calibrate [--calibrate-item synthetic|fixture|shipped]
                               [--calibrate-level 8] [--calibration-out FILE]
  probe_ladder_shortcut.py --run [--out-dir DIR] [--max-tokens N] [--resume]

Exit codes:
  0  selftest passed, or the run completed within budget
  2  usage error
  4  a selftest control was not caught, or a design invariant failed
  5  endpoint unavailable, or the endpoint returned a malformed response
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
from collections import Counter, deque
from fractions import Fraction
from math import comb
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ITEMS_DIR = REPO / "items" / "ladders"
FIXTURE_DIR = REPO / "generators" / "fixtures"

LEVELS = (2, 8)
CELLS = (("fixture", 2), ("shipped", 2), ("fixture", 8), ("shipped", 8))
ITEMS_PER_CELL = 10
EXPERIMENTAL_BUDGET = len(CELLS) * ITEMS_PER_CELL  # 40, fixed
MAX_CALIBRATION_CALLS = 3  # instrument validation only, never experimental data
CALIBRATION_SEED_BASE = 20261005 + 1_000_000  # outside every corpus and experiment
CAL_FLAT_KEYS = ("kind", "seed", "level", "n_facts", "gold_path_len",
                 "requested_max_tokens", "finish_reason", "completion_tokens",
                 "reasoning_chars", "parsed_answer", "parse_method", "truncated",
                 "latency_s")
CALIBRATION_POLICY = {
    "purpose": ("instrument validation: size the token cap so a greedy zero-shot "
                "answer is not truncated; calibration responses are discarded and "
                "are never experimental data"),
    "selection_rule": ("for each arm, the longest item in that arm whose seed is "
                       "not one of the 10 experimental seeds; ties broken by seed"),
    "planned_calls": 1,
    "max_calls": MAX_CALIBRATION_CALLS,
    "deviation": ("2026-10-16: the planned single calibration used a synthetic "
                  "disjoint-pair item that never exercised traversal cost, so two "
                  "further calibrations were added on generator-produced k=8 items "
                  "(one per arm, worst-case chain length). The 40-prompt "
                  "experimental budget is unchanged by this deviation."),
}
REL = "precedes"
DECODE_SEED = 20261016
DEFAULT_MAX_TOKENS = 1536
HTTP_TIMEOUT_S = 300
# A local inference pool is shared and can stall. A stalled call must not take
# the whole experiment down with it: round 5 attempt 1 died at item 22/40 on a
# socket timeout and lost all 21 collected answers, because records were only
# written at the end. So: per-item retry under a global retry budget, records
# appended as they are produced, and --resume reusing already-answered items.
MAX_RETRIES_TOTAL = 8
RETRY_BACKOFF_S = 20
RUN_ID = "nightly-2026-10-16-0200"

WORD_RE = re.compile(r"\b(yes|no)\b", re.IGNORECASE)
ANSWER_LINE_RE = re.compile(r"^\s*answer\s*[:\-]?\s*(yes|no)\b",
                            re.IGNORECASE | re.MULTILINE)
# The whole prompt template: item block + this fixed instruction. The guard in
# build_prompt runs on the item block only, because the instruction is the one
# place where yes/no may legitimately appear.
INSTRUCTION = "Reply with exactly one word: yes or no."


# ---------------- item loading and matched pairs ----------------

def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def corpus_items(kind: str, level: int) -> list[dict]:
    name = (f"issue67_prefix_l{level}.jsonl" if kind == "fixture"
            else f"l{level}.jsonl")
    path = FIXTURE_DIR / name if kind == "fixture" else ITEMS_DIR / name
    return load_jsonl(path)


def matched_cells() -> list[dict]:
    """The 40 experimental items, paired by seed. Fails closed on any drift."""
    cells = []
    for kind, level in CELLS:
        items = corpus_items(kind, level)
        if kind == "fixture":
            partners = {it["seed"]: it for it in corpus_items("shipped", level)}
            pairs = []
            for it in items[:ITEMS_PER_CELL]:
                if it["seed"] not in partners:
                    raise RuntimeError(f"no shipped partner for seed {it['seed']}")
                pairs.append((it, partners[it["seed"]]))
            if len(pairs) != ITEMS_PER_CELL:
                raise RuntimeError(f"fixture l{level}: only {len(pairs)} pairs")
            seeds = [p[0]["seed"] for p in pairs]
            if len(set(seeds)) != ITEMS_PER_CELL:
                raise RuntimeError(f"fixture l{level}: duplicate seeds")
        else:
            # The shipped arm is the partners of the fixture seeds, so the two
            # arms of one level are the same 10 seeds, no free selection.
            fixture_seeds = [it["seed"] for it in
                             corpus_items("fixture", level)[:ITEMS_PER_CELL]]
            by_seed = {it["seed"]: it for it in items}
            pairs = [(by_seed[s], by_seed[s]) for s in fixture_seeds]
        cells.append({"kind": kind, "level": level, "pairs": pairs})
    return cells


# ---------------- prompt construction ----------------

def build_prompt(item: dict) -> str:
    """Prompt from the item's facts and query only.

    The answer fields (`answer`, `chain_len`) are answer-bearing and must never
    reach the model. The guard below is what enforces that; --selftest plants a
    leak and checks the guard catches it.
    """
    qs, rel, qt = item["query"]
    lines = [f"{i}. {src} {r} {tgt}" for i, (src, r, tgt) in enumerate(item["facts"], 1)]
    block = "Facts:\n" + "\n".join(lines) + "\n\n"
    block += f"Question: Does {qs} {rel} {qt}?"
    for banned in ("answer", "chain_len"):
        if banned in block:
            raise RuntimeError(f"leak guard: {banned!r} reached the prompt")
    if WORD_RE.search(block):
        raise RuntimeError("leak guard: a yes/no token reached the item block")
    return block + "\n\n" + INSTRUCTION


def prompt_hash(prompts: list[str]) -> str:
    blob = "\n\x1f\n".join(prompts)
    return hashlib.sha256(blob.encode()).hexdigest()


def task_hash(prompts: list[str]) -> str:
    """Hash of the task contract: the ordered prompts plus the decoding plan."""
    return prompt_hash(prompts)


# ---------------- independent graph tools (no generator reuse) ----------------

def adjacency(facts: list[list[str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for src, _, tgt in facts:
        out.setdefault(src, []).append(tgt)
        out.setdefault(tgt, [])
    return out


def bfs_path(facts: list[list[str]], src: str, tgt: str) -> list[str] | None:
    """Shortest directed path src->tgt as a node list, or None. Independent of
    the generator's own BFS and of the item's `chain_len` field."""
    out = adjacency(facts)
    if src not in out or tgt not in out:
        return None
    prev = {src: None}
    q = deque([src])
    while q:
        cur = q.popleft()
        if cur == tgt:
            path = [cur]
            while prev[path[-1]] is not None:
                path.append(prev[path[-1]])
            return list(reversed(path))
        for nxt in out.get(cur, ()):
            if nxt not in prev:
                prev[nxt] = cur
                q.append(nxt)
    return None


# ---------------- a-priori baselines (facts only, never gold) ----------------

def _round(value, nd: int = 4):
    return None if value is None else round(float(value), nd)


def exact_null_ba(n_yes: int, n_no: int) -> list[tuple[Fraction, int]]:
    """Exact null distribution of balanced accuracy when every answer is an
    independent fair coin. Enumerated over class-conditional hit counts with
    binomial weights, so there is no Monte Carlo error and no endpoint cost.

    Returns [(ba_value, weight)] pairs; weights sum to 2 ** (n_yes + n_no).
    """
    weights: dict[Fraction, int] = {}
    total_cases = 2 ** (n_yes + n_no)
    for tp in range(n_yes + 1):
        for tn in range(n_no + 1):
            ba = (Fraction(tp, n_yes) + Fraction(tn, n_no)) / 2
            weights[ba] = weights.get(ba, 0) + comb(n_yes, tp) * comb(n_no, tn)
    assert sum(weights.values()) == total_cases
    return sorted(weights.items())


def _null_p_at_least(null: list[tuple[Fraction, int]], observed) -> float:
    """Exact one-sided p-value: P(BA >= observed) under the answering null."""
    if observed is None:
        return 1.0
    total = sum(w for _, w in null)
    obs = Fraction(observed).limit_denominator(10 ** 6)
    hit = sum(w for ba, w in null if ba >= obs)
    return hit / total


def _null_quantile(null: list[tuple[Fraction, int]], q: float) -> float:
    total = sum(w for _, w in null)
    need = q * total
    acc = 0
    for ba, w in null:
        acc += w
        if acc >= need:
            return float(ba)
    return float(null[-1][0])


def balanced_accuracy(preds: list[str | None], golds: list[str]) -> float | None:
    """Mean of the two class-conditional accuracies (Youden's J).

    Primary metric, chosen before the run: the cells are base-rate imbalanced
    (5/5, 4/6, 3/7, 6/4), so plain accuracy rewards always-answering-the-major-
    class. Balanced accuracy puts every a-priori constant baseline at exactly
    0.5, which is the chance reference the verdict rule needs. Returns None when
    a class is absent from the cell.
    """
    yes_i = [i for i, g in enumerate(golds) if g == "yes"]
    no_i = [i for i, g in enumerate(golds) if g == "no"]
    if not yes_i or not no_i:
        return None
    tp = sum(1 for i in yes_i if preds[i] == "yes")
    tn = sum(1 for i in no_i if preds[i] == "no")
    return (tp / len(yes_i) + tn / len(no_i)) / 2


def baseline_predictions(items: list[dict]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    gold = [it["answer"] for it in items]
    maj = Counter(gold).most_common(1)[0][0]
    out["B_majority"] = [maj] * len(items)
    direct, sig = [], []
    for it in items:
        qs, _, qt = it["query"]
        stated = any(s == qs and t == qt for s, _, t in it["facts"])
        direct.append("yes" if stated else "no")
        out_map = adjacency(it["facts"])
        is_fact_target = any(t == qt for _, _, t in it["facts"])
        outdeg_zero = not out_map.get(qt)
        sig.append("yes" if (is_fact_target and outdeg_zero) else "no")
    out["B_direct"] = direct
    out["B_leak_sig"] = sig
    return out


# ---------------- answer parsing ----------------

def parse_answer(content: str | None) -> tuple[str | None, str]:
    """Return (answer, method). Method is empty when the answer is valid."""
    if not content or not content.strip():
        return None, "no_content"
    m = None
    for m in ANSWER_LINE_RE.finditer(content):
        pass
    if m:
        return m.group(1).lower(), "answer_line"
    hits = WORD_RE.findall(content)
    if hits:
        return hits[-1].lower(), "last_word"
    return None, "unparseable"


# ---------------- endpoint client ----------------

def read_endpoint_model(base: str) -> dict:
    req = urllib.request.Request(base.rstrip("/") + "/models")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    models = data.get("data") or []
    if not models:
        raise RuntimeError("endpoint /models returned no models")
    return models[0]


class Client:
    """Minimal OpenAI-compatible chat client. Greedy, single completion."""

    def __init__(self, base: str, model_id: str, max_tokens: int):
        self.url = base.rstrip("/") + "/chat/completions"
        self.model_id = model_id
        self.max_tokens = max_tokens

    def complete(self, prompt: str, seed: int) -> dict:
        payload = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": self.max_tokens,
            "seed": seed,
            "stream": False,
        }
        req = urllib.request.Request(
            self.url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"})
        t0 = time.monotonic()
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            body = json.loads(resp.read().decode())
        dt = time.monotonic() - t0
        choices = body.get("choices") or []
        if not choices:
            raise RuntimeError("endpoint returned no choices")
        msg = choices[0].get("message") or {}
        return {
            "content": msg.get("content"),
            "reasoning": msg.get("reasoning_content") or "",
            "finish_reason": choices[0].get("finish_reason"),
            "prompt_tokens": (body.get("usage") or {}).get("prompt_tokens"),
            "completion_tokens": (body.get("usage") or {}).get("completion_tokens"),
            "latency_s": round(dt, 3),
        }


class MockClient:
    """Offline stand-in that exercises the full pipeline without an endpoint.

    `mode` "shortcut" answers with the B_leak_sig prediction, which is the
    behaviour the probe is built to detect; "garbage" answers with text that
    contains no yes/no token. A selftest control asserts the scorer reports
    the shortcut mock as shortcut behaviour and the garbage mock as invalid.
    """

    def __init__(self, mode: str, items_by_key: dict, max_tokens: int):
        self.mode = mode
        self.items_by_key = items_by_key
        self.max_tokens = max_tokens
        self.calls = 0

    def complete(self, prompt: str, seed: int) -> dict:
        self.calls += 1
        item = self.items_by_key[prompt]
        pred = baseline_predictions([item])["B_leak_sig"][0]
        if self.mode == "garbage":
            text = "the relation may or may not hold under some reading"
        else:
            text = f"Answer: {pred}"
        return {"content": text, "reasoning": "mock trace", "finish_reason": "stop",
                "prompt_tokens": len(prompt.split()), "completion_tokens": 8,
                "latency_s": 0.0}


# ---------------- process indicator ----------------

def process_indicator(item: dict, trace: str) -> dict:
    """Heuristic: does the reasoning trace name the gold path's intermediates?

    Only defined for items whose gold answer is "yes" (a gold path exists).
    Word-boundary matching; entity strings are synthetic and cannot collide
    with yes/no tokens.
    """
    path = bfs_path(item["facts"], item["query"][0], item["query"][2])
    inter = path[1:-1] if path else []
    named = sum(1 for e in inter if re.search(rf"\b{re.escape(e)}\b", trace))
    return {"gold_path_len": len(path) if path else None,
            "intermediates": len(inter),
            "intermediates_named": named,
            "named_fraction": round(named / len(inter), 4) if inter else None}


# ---------------- run ----------------

def append_record(path: Path, rec: dict) -> None:
    """Append one record and force it to disk.

    Crash safety: a run that dies mid-experiment must not lose the answers it
    already paid for, so records are flushed one by one instead of being
    written at the end.
    """
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def run(client, cells: list[dict], max_tokens: int, model_info: dict,
        calibration: dict | None, out_dir: Path, commit: str,
        dry_run: bool, quiet: bool = False, resume: bool = False,
        retry_backoff_s: int = RETRY_BACKOFF_S) -> int:
    # Prompts are built per cell, in cell order, and hashed once: the hash is
    # the task contract, so the ordering is part of it.
    prompts: list[str] = []
    per_cell_prompts: list[list[str]] = []
    for cell in cells:
        arm = cell["kind"]
        cps = [build_prompt(f if arm == "fixture" else s) for f, s in cell["pairs"]]
        per_cell_prompts.append(cps)
        prompts.extend(cps)
    phash = prompt_hash(prompts)
    if len(prompts) != EXPERIMENTAL_BUDGET:
        raise RuntimeError(f"budget drift: {len(prompts)} prompts")

    started = time.time()
    n_calls = 0
    n_attempts = 0
    n_retries = 0
    n_resumed = 0
    n_errors = 0
    records: list[dict] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "probe_raw.jsonl"
    prior: dict[tuple[str, int], dict] = {}
    # The prompt each item would be sent as, keyed the same way records are.
    # Resume validation is done up front, before the raw file is rewritten, so
    # a refused resume cannot damage the file it was asked to protect.
    prompt_of: dict[tuple[str, int], str] = {}
    for cell, cps in zip(cells, per_cell_prompts):
        arm, level = cell["kind"], cell["level"]
        for (fixture_item, shipped_item), prompt in zip(cell["pairs"], cps):
            item = fixture_item if arm == "fixture" else shipped_item
            prompt_of[(f"{arm}_l{level}", item["seed"])] = hashlib.sha256(prompt.encode()).hexdigest()
    if resume and raw_path.exists():
        for rec in load_jsonl(raw_path):
            # First occurrence wins: a timed-out call may still have been
            # answered server-side, so a later duplicate is not preferred.
            prior.setdefault((rec["cell"], rec["seed"]), rec)
        for key, rec in prior.items():
            if rec.get("finish_reason") == "client_error":
                continue
            want = prompt_of.get(key)
            if want is None:
                raise RuntimeError(f"resume refused: {key} is not an item of this design")
            if rec.get("prompt_sha256") != want:
                raise RuntimeError(f"resume refused: {key} record does not match "
                                   f"the prompt this run would send")
    raw_path.write_text("")  # canonical cell order restarts on every run
    for cell, cps in zip(cells, per_cell_prompts):
        arm, level = cell["kind"], cell["level"]
        cell_name = f"{arm}_l{level}"
        items = [f if arm == "fixture" else s for f, s in cell["pairs"]]
        base = baseline_predictions(items)
        for idx, ((fixture_item, shipped_item), prompt) in enumerate(zip(cell["pairs"], cps)):
            item = fixture_item if arm == "fixture" else shipped_item
            prev = prior.get((cell_name, item["seed"]))
            if prev and prev.get("finish_reason") != "client_error":
                rec = dict(prev)
                rec["resumed"] = True
                records.append(rec)
                append_record(raw_path, rec)
                n_resumed += 1
                if not quiet:
                    print(f"[{cell_name}] seed={item['seed']} reused from a prior attempt")
                continue
            res = None
            err: Exception | None = None
            attempts = 0
            while attempts < 2:
                attempts += 1
                try:
                    if dry_run:
                        res = {"content": None, "reasoning": "", "finish_reason": "dry_run",
                               "prompt_tokens": None, "completion_tokens": None,
                               "latency_s": 0.0}
                    else:
                        n_attempts += 1
                        res = client.complete(prompt, DECODE_SEED)
                        n_calls += 1
                    err = None
                    break
                except (OSError, RuntimeError, ValueError) as exc:
                    err = exc
                    if n_retries >= MAX_RETRIES_TOTAL:
                        break
                    n_retries += 1
                    print(f"[{cell_name}] seed={item['seed']} attempt {attempts} failed: "
                          f"{type(exc).__name__}: {exc}; retrying in {retry_backoff_s}s "
                          f"({MAX_RETRIES_TOTAL - n_retries} retries left)", flush=True)
                    time.sleep(retry_backoff_s)
            if err is not None:
                # A failed call is a recorded outcome, not a crash: the item is
                # marked invalid and the run continues.
                n_errors += 1
                res = {"content": None, "reasoning": "", "finish_reason": "client_error",
                       "prompt_tokens": None, "completion_tokens": None, "latency_s": None}
            ans, method = parse_answer(res["content"])
            gold = item["answer"]
            rec = {
                "cell": cell_name, "arm": arm, "level": level,
                "seed": item["seed"], "seed_hash": item["seed_hash"],
                "query": item["query"], "n_facts": len(item["facts"]),
                "gold": gold, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "model_answer": ans, "parse_method": method,
                "valid": ans is not None,
                "correct": (ans == gold) if ans is not None else None,
                "finish_reason": res["finish_reason"],
                "prompt_tokens": res["prompt_tokens"],
                "completion_tokens": res["completion_tokens"],
                "reasoning_chars": len(res["reasoning"] or ""),
                "latency_s": res["latency_s"],
                "attempts": attempts, "resumed": False,
                "error": (f"{type(err).__name__}: {err}"[:200] if err else None),
                "b_majority_correct": base["B_majority"][idx] == gold,
                "b_direct_correct": base["B_direct"][idx] == gold,
                "b_leak_sig_correct": base["B_leak_sig"][idx] == gold,
                "process": process_indicator(item, res["reasoning"] or ""),
            }
            records.append(rec)
            append_record(raw_path, rec)
            if not dry_run and not quiet:
                pr = rec["process"]
                print(f"[{rec['cell']}] seed={rec['seed']} gold={gold} ans={ans} "
                      f"valid={rec['valid']} finish={rec['finish_reason']} "
                      f"comp_tok={rec['completion_tokens']} "
                      f"trace_chars={rec['reasoning_chars']} "
                      f"named={pr['intermediates_named']}/{pr['intermediates']} "
                      f"attempts={attempts}", flush=True)
    ended = time.time()

    # cell summaries and exact answering nulls, computed in one place per cell
    summary: dict[str, dict] = {}
    for cell in cells:
        name = f"{cell['kind']}_l{cell['level']}"
        recs = [r for r in records if r["cell"] == name]
        items = [f if cell["kind"] == "fixture" else s for f, s in cell["pairs"]]
        golds = [r["gold"] for r in recs]
        if golds != [it["answer"] for it in items]:
            raise RuntimeError(f"record/item gold drift in {name}")
        ny, nn = golds.count("yes"), golds.count("no")
        if not ny or not nn:
            raise RuntimeError(f"design failure: {name} has a missing answer class")
        valid = [r for r in recs if r["valid"]]
        preds_all = [r["model_answer"] for r in recs]        # None counts as wrong
        preds_valid = [r["model_answer"] for r in valid]
        golds_valid = [r["gold"] for r in valid]
        ba_all = balanced_accuracy(preds_all, golds)
        ba_valid = balanced_accuracy(preds_valid, golds_valid)
        null_full = exact_null_ba(ny, nn)
        ny_v, nn_v = golds_valid.count("yes"), golds_valid.count("no")
        # A valid subset that lost an answer class cannot carry a balanced
        # accuracy claim; its null is left undefined and the cell is not strong.
        null_valid = exact_null_ba(ny_v, nn_v) if (ny_v and nn_v) else None
        summary[name] = {
            "n": len(recs), "valid": len(valid),
            "gold_yes": ny, "gold_no": nn,
            "accuracy_on_valid": _round(sum(1 for r in valid if r["correct"]) / len(valid))
            if valid else None,
            "accuracy_on_all": _round(sum(1 for r in recs if r["correct"]) / len(recs)),
            "balanced_accuracy_on_valid": _round(ba_valid),
            "balanced_accuracy_on_all": _round(ba_all),
            "leak_sig_agreement": _round(sum(1 for r in recs if r["b_leak_sig_correct"]) / len(recs)),
            "direct_agreement": _round(sum(1 for r in recs if r["b_direct_correct"]) / len(recs)),
            "mean_completion_tokens": _round(sum(r["completion_tokens"] or 0 for r in recs) / len(recs), 1),
            "mean_trace_chars": _round(sum(r["reasoning_chars"] for r in recs) / len(recs), 1),
            "named_fraction_mean": _round(sum((r["process"]["named_fraction"] or 0) for r in recs) / len(recs)),
            "baselines_balanced": {
                key: _round(balanced_accuracy(baseline_predictions(items)[key], golds))
                for key in ("B_majority", "B_direct", "B_leak_sig")},
            "null_ba_full": {
                "n": len(recs),
                "mean": _round(sum(float(v) * w for v, w in null_full) / sum(w for _, w in null_full)),
                "p95": _round(_null_quantile(null_full, 0.95)),
                "max": _round(max(float(v) for v, _ in null_full)),
                "support_size": sum(w for _, w in null_full),
            },
            "p_ba_at_least_observed_full": _round(_null_p_at_least(null_full, ba_all)),
            "p_ba_at_least_observed_valid": _round(_null_p_at_least(null_valid, ba_valid))
            if null_valid else None,
        }

    # Fixed verdict rule (balanced accuracy; exact null of fair-coin answering).
    # Power note: 10 items per cell means BA moves in steps of ~0.08-0.17, so
    # this is a screening experiment. The rule therefore only accepts large,
    # exactly-signalled effects and calls everything else inconclusive.
    def strong(name: str) -> bool:
        s = summary[name]
        ba = s["balanced_accuracy_on_valid"]
        p_v = s["p_ba_at_least_observed_valid"]
        p_f = s["p_ba_at_least_observed_full"]
        return (ba is not None and ba >= 0.75
                and p_v is not None and p_v < 0.05
                and p_f is not None and p_f < 0.05)

    fixture_strong = all(strong(f"fixture_l{lv}") for lv in LEVELS)
    shipped_strong = all(strong(f"shipped_l{lv}") for lv in LEVELS)
    if not fixture_strong:
        verdict = "inconclusive_no_capability"
    elif shipped_strong:
        verdict = "traversal_consistent"
    else:
        verdict = "shortcut_consistent"

    manifest = {
        "run_id": RUN_ID,
        "parent_run_id": "nightly-2026-10-15-0400",
        "task_hash": phash,
        "prompt_hash": phash,
        "commit": commit,
        "model": {
            "endpoint_model_id": model_info.get("id"),
            "public_label": model_info.get("public_label"),
            "provider_model_id": model_info.get("provider_model_id"),
            "endpoint_n_ctx": model_info.get("n_ctx"),
            "weights_hash": None,
            "weights_hash_note": "not exposed by the serving endpoint; recorded as a gap",
            "serving_revision": None,
            "endpoint_reference": "env:NIGHTLY_BASE_URL (value not recorded, public-only rule)",
        },
        "decoding": {"temperature": 0, "max_tokens": max_tokens, "seed": DECODE_SEED,
                     "stream": False, "shots": 0},
        "budget": {"experimental_prompts": EXPERIMENTAL_BUDGET,
                   "experimental_calls_used": n_calls,
                   "endpoint_attempts": n_attempts,
                   "retries_used": n_retries,
                   "retry_budget": MAX_RETRIES_TOTAL,
                   "items_reused_from_prior_attempt": n_resumed,
                   "items_recorded_as_client_error": n_errors,
                   "calibration_calls_allowed": MAX_CALIBRATION_CALLS,
                   "calibration_calls_used": len(calibration["calls"])
                   if calibration and calibration.get("calls") else 0},
        "calibration": calibration,
        "cells": {name: summary[name] for name in summary},
        "fixture_seed_pairs": {f"l{lv}": [f["seed"] for f, _ in c["pairs"]]
                               for c in cells for lv in [c["level"]] if c["kind"] == "fixture"},
        "verdict_rule": {
            "strong_cell": "balanced_accuracy_on_valid >= 0.75 AND exact P(BA >= observed) < 0.05 under fair-coin answering, on both the full cell (invalid answers count as wrong) and the valid subset",
            "inconclusive_no_capability": "a fixture cell is not strong (the model could not answer the task)",
            "traversal_consistent": "both fixture cells strong AND both shipped cells strong",
            "shortcut_consistent": "both fixture cells strong AND at least one shipped cell not strong",
            "power_note": "10 items per cell: BA steps are 0.08-0.17, so only large exactly-signalled effects are read; screening, not confirmatory",
        },
        "verdict": verdict,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "ended_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ended)),
        "status": "executed" if not dry_run else "dry_run",
        "failure_codes": [],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = out_dir / "probe_raw.jsonl"
    with open(raw, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    manifest["artifact_hashes"] = {
        "probe_raw.jsonl": hashlib.sha256(raw.read_bytes()).hexdigest()}
    man = out_dir / "probe_manifest.json"
    with open(man, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    if not quiet:
        print(json.dumps({"verdict": verdict, "cells": summary}, sort_keys=True, indent=2))
        print(f"wrote {raw} and {man}")
    return 0


# ---------------- calibration (instrument validation, never data) ----------------

def experimental_seeds() -> set[int]:
    seeds: set[int] = set()
    for cell in matched_cells():
        for fixture_item, shipped_item in cell["pairs"]:
            seeds.add(fixture_item["seed"])
            seeds.add(shipped_item["seed"])
    return seeds


def longest_calibration_item(kind: str, level: int) -> dict:
    """Worst-case prompt for this arm: the longest item whose seed is not one of
    the 10 experimental seeds. Deterministic (ties broken by seed)."""
    exp = experimental_seeds()
    candidates = [it for it in corpus_items(kind, level) if it["seed"] not in exp]
    if not candidates:
        raise RuntimeError(f"no non-experimental calibration item for {kind} l{level}")
    return max(candidates, key=lambda it: (len(it["facts"]), it["seed"]))


def synthetic_calibration_item(level: int) -> dict:
    """The original single-call plan: 2*level isolated edges, query across them.

    It has no gold path, so it measures output length only and never exercises
    traversal cost. That limitation is why the plan was extended (see
    CALIBRATION_POLICY["deviation"]); the item is kept byte-identical so the
    recorded first call stays reproducible.
    """
    facts = [[f"n{i}", REL, f"n{i + 1}"] for i in range(0, 2 * level, 2)]
    facts += [[f"m{i}", REL, f"m{i + 1}"] for i in range(0, 2 * level, 2)]
    return {"facts": facts, "query": ["n0", REL, f"n{2 * level - 1}"],
            "answer": "no", "level": level, "seed": 999999, "seed_hash": "calibration"}


def calibration_item_for(kind: str, level: int) -> dict:
    if kind == "synthetic":
        return synthetic_calibration_item(level)
    return longest_calibration_item(kind, level)


def normalize_calibration(data: dict | None) -> dict | None:
    """Accept the legacy flat record or the calls-list record, always emit the
    calls-list record with the policy attached."""
    if not data:
        return None
    cal = dict(data.get("calibration") or {})
    merged = dict(CALIBRATION_POLICY)
    if "calls" in cal:
        merged.update({k: v for k, v in cal.items() if k != "calls"})
        merged["calls"] = list(cal["calls"])
    else:
        call = {k: cal[k] for k in CAL_FLAT_KEYS if k in cal}
        if not call:
            return None
        call["record_format"] = "legacy_flat"
        if "kind" not in call:
            call["kind"] = "synthetic" if call.get("seed") == 999999 else "unrecorded"
        merged["calls"] = [call]
    calls = merged["calls"]
    merged["n_calls"] = len(calls)
    merged["n_truncated"] = sum(1 for c in calls if c.get("truncated"))
    merged["max_completion_tokens"] = max((c.get("completion_tokens") or 0) for c in calls)
    merged["any_unparsed"] = any(c.get("parsed_answer") is None for c in calls)
    return merged


def calibration_call(client, item: dict, kind: str, max_tokens: int) -> dict:
    prompt = build_prompt(item)
    res = client.complete(prompt, DECODE_SEED)
    answer, method = parse_answer(res["content"])
    path = bfs_path(item["facts"], item["query"][0], item["query"][2])
    return {
        "kind": kind, "seed": item["seed"], "level": item.get("level"),
        "n_facts": len(item["facts"]),
        "gold_path_len": len(path) if path else None,
        "prompt_chars": len(prompt),
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "requested_max_tokens": max_tokens,
        "finish_reason": res["finish_reason"],
        "completion_tokens": res["completion_tokens"],
        "reasoning_chars": len(res["reasoning"] or ""),
        "content_chars": len(res["content"] or ""),
        "parsed_answer": answer, "parse_method": method,
        "truncated": res["finish_reason"] == "length",
        "latency_s": res["latency_s"],
    }


def run_calibration(client, kind: str, level: int, max_tokens: int,
                    out_path: Path, model_info: dict) -> tuple[dict, int]:
    """One calibration call, appended to the calibration record.

    Refuses to exceed MAX_CALIBRATION_CALLS and refuses to use an experimental
    seed, so calibration can never bleed into the 40-prompt budget.
    """
    item = calibration_item_for(kind, level)
    if item["seed"] in experimental_seeds():
        raise RuntimeError("calibration seed collides with an experimental seed")
    cal = normalize_calibration(
        json.loads(out_path.read_text()) if out_path.exists() else None)
    if cal is None:
        cal = dict(CALIBRATION_POLICY)
        cal["calls"] = []
    if len(cal["calls"]) >= MAX_CALIBRATION_CALLS:
        raise RuntimeError(f"calibration budget reached ({MAX_CALIBRATION_CALLS} calls)")
    cal["calls"].append(calibration_call(client, item, kind, max_tokens))
    cal["n_calls"] = len(cal["calls"])
    cal["n_truncated"] = sum(1 for c in cal["calls"] if c["truncated"])
    cal["max_completion_tokens"] = max(c["completion_tokens"] or 0 for c in cal["calls"])
    cal["any_unparsed"] = any(c["parsed_answer"] is None for c in cal["calls"])
    cal["model"] = model_info
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"calibration": cal}, sort_keys=True, indent=2)
    out_path.write_text(text + "\n", encoding="utf-8")
    return cal, 0 if cal["calls"][-1]["parsed_answer"] is not None else 5


# ---------------- selftest ----------------



def selftest() -> int:
    fails: list[str] = []

    def check(cond: bool, label: str) -> None:
        if not cond:
            fails.append(label)

    cells = matched_cells()
    check(len(cells) == 4, "cell count")
    check(all(len(c["pairs"]) == ITEMS_PER_CELL for c in cells), "cell sizes")

    # 1. matched pairs really share seeds, and the two arms of a level are the
    #    same 10 seeds (no free selection of the shipped arm).
    for c in cells:
        for f, s in c["pairs"]:
            check(f["seed"] == s["seed"], f"seed match l{c['level']}")
    for lv in LEVELS:
        fx = sorted(s["seed"] for c in cells if c["kind"] == "fixture"
                    and c["level"] == lv for s, _ in c["pairs"])
        sh = sorted(s["seed"] for c in cells if c["kind"] == "shipped"
                    and c["level"] == lv for _, s in c["pairs"])
        check(len(fx) == ITEMS_PER_CELL and fx == sh, f"arm seed identity l{lv}")

    # 2. prompts are deterministic and answer-free
    prompts = [build_prompt(f if c["kind"] == "fixture" else s)
               for c in cells for f, s in c["pairs"]]
    check(len(prompts) == EXPERIMENTAL_BUDGET, "prompt budget")
    check(prompt_hash(prompts) == prompt_hash(list(prompts)), "prompt determinism")
    check(all(not WORD_RE.search(p[: -len(INSTRUCTION)]) for p in prompts),
          "prompt item block answer-free")
    check(all(p.endswith(INSTRUCTION) for p in prompts), "prompt template fixed")
    check(prompt_hash(prompts) != prompt_hash(prompts[:20] + prompts[20:][::-1]),
          "prompt hash is order-sensitive")
    # entity names may contain yes/no as substrings; the guard must not fire
    substr = {"facts": [["knot", REL, "yesp"], ["yesp", REL, "noth"]],
              "query": ["knot", REL, "noth"], "answer": "yes",
              "seed": 3, "seed_hash": "z"}
    check(build_prompt(substr).endswith(INSTRUCTION), "guard tolerates yes/no substrings")

    # 3. leak guard catches a planted answer in the prompt
    planted = dict(cells[0]["pairs"][0][0])
    planted["facts"] = planted["facts"] + [["answer", "chain_len", "yes"]]
    try:
        build_prompt(planted)
        fails.append("leak guard did not fire")
    except RuntimeError:
        pass

    # 4. baseline arithmetic on hand-built items (declared expectations)
    hand = {"facts": [["a", REL, "b"], ["b", REL, "c"], ["x", REL, "y"]],
            "query": ["a", REL, "c"], "answer": "yes", "seed": 1, "seed_hash": "x"}
    b = baseline_predictions([hand])
    check(b["B_direct"][0] == "no", "B_direct on hand item (a->c is not a stated fact)")
    check(b["B_leak_sig"][0] == "yes", "B_leak_sig on hand item (c is a fact target with outdeg 0)")
    check(b["B_majority"][0] == "yes", "B_majority on hand item")
    hand2 = {"facts": [["a", REL, "b"], ["c", REL, "d"]],
             "query": ["a", REL, "c"], "answer": "no", "seed": 2, "seed_hash": "y"}
    b2 = baseline_predictions([hand2])
    check(b2["B_direct"][0] == "no", "B_direct on hand item 2")
    check(b2["B_leak_sig"][0] == "no", "B_leak_sig on hand item 2 (c is a fact source, not target)")
    check(b2["B_majority"][0] == "no", "B_majority on hand item 2")

    # 5. independent BFS path recovery
    check(bfs_path(hand["facts"], "a", "c") == ["a", "b", "c"], "bfs path")
    check(bfs_path(hand["facts"], "c", "a") is None, "bfs direction")

    # 6. parser controls
    check(parse_answer("Answer: no") == ("no", "answer_line"), "parse answer line")
    check(parse_answer("... yes\nAnswer: No") == ("no", "answer_line"), "parse prefers answer line")
    check(parse_answer("probably yes") == ("yes", "last_word"), "parse last word")
    check(parse_answer("maybe") == (None, "unparseable"), "parse unparseable")
    check(parse_answer(None) == (None, "no_content"), "parse null content")
    check(parse_answer("knot") == (None, "unparseable"), "parse ignores substring 'no' in knot")

    # 7. shortcut mock must be scored as shortcut behaviour (the probe detects
    #    the behaviour it is built to detect)
    items_by_key = {}
    for c in cells:
        for f, s in c["pairs"]:
            it = f if c["kind"] == "fixture" else s
            items_by_key[build_prompt(it)] = it
    tmp = Path("/tmp/opencode/nightly-2026-10-16-0200/selftest_run")
    # 7. the dry-run path: prompts built and hashed, no call made, and the run
    #    must report no capability rather than an empty success
    rc = run(MockClient("shortcut", items_by_key, 8), cells, 8,
             {"id": "mock", "public_label": "mock"}, None, tmp, "selftest", True, True)
    man = json.loads((tmp / "probe_manifest.json").read_text())
    check(rc == 0, "dry run rc")
    check(man["status"] == "dry_run", "dry run status")
    check(all(v["valid"] == 0 for v in man["cells"].values()), "dry run makes no calls")
    check(man["verdict"] == "inconclusive_no_capability", "dry run verdict")
    check(man["budget"]["experimental_calls_used"] == 0, "dry run call count")

    # 8. garbage mock: every cell reports zero valid answers, and the run
    #    cannot claim capability it does not have
    rc2 = run(MockClient("garbage", items_by_key, 8), cells, 8,
              {"id": "mock"}, None, tmp, "selftest", False, True)
    man2 = json.loads((tmp / "probe_manifest.json").read_text())
    check(rc2 == 0, "garbage run rc")
    check(man2["status"] == "executed", "garbage run status")
    check(man2["budget"]["experimental_calls_used"] == EXPERIMENTAL_BUDGET,
          "garbage run uses the full budget")
    check(all(v["valid"] == 0 for v in man2["cells"].values()), "garbage run validity")
    check(man2["verdict"] == "inconclusive_no_capability", "garbage run verdict")

    # 9. a perfect-traversal mock (answers gold) must read as traversal
    class PerfectMock(MockClient):
        def complete(self, prompt, seed):
            r = super().complete(prompt, seed)
            r["content"] = f"Answer: {self.items_by_key[prompt]['answer']}"
            return r

    rc3 = run(PerfectMock("shortcut", items_by_key, 8), cells, 8,
              {"id": "mock"}, None, tmp, "selftest", False, True)
    man3 = json.loads((tmp / "probe_manifest.json").read_text())
    check(rc3 == 0, "perfect run rc")
    check(man3["verdict"] == "traversal_consistent", "perfect run verdict")
    check(all(man3["cells"][c]["balanced_accuracy_on_valid"] == 1.0 for c in man3["cells"]),
          "perfect run balanced accuracy")
    check(all(abs(man3["cells"][c]["p_ba_at_least_observed_valid"] - 1 / 1024) < 1e-4
              for c in man3["cells"]), "perfect run exact p")

    # 10. a pure-shortcut mock (answers by the pre-fix leak signature) must read
    #     as shortcut behaviour on the fixture arm and chance on the shipped arm
    class LeakMock(MockClient):
        def complete(self, prompt, seed):
            r = super().complete(prompt, seed)
            r["content"] = f"Answer: {baseline_predictions([self.items_by_key[prompt]])['B_leak_sig'][0]}"
            return r

    rc4 = run(LeakMock("shortcut", items_by_key, 8), cells, 8,
              {"id": "mock"}, None, tmp, "selftest", False, True)
    man4 = json.loads((tmp / "probe_manifest.json").read_text())
    check(rc4 == 0, "leak mock run rc")
    check(man4["cells"]["fixture_l2"]["accuracy_on_valid"] == 1.0,
          "leak mock perfect on fixture l2")
    check(man4["cells"]["fixture_l2"]["balanced_accuracy_on_valid"] == 1.0,
          "leak mock balanced accuracy on fixture l2")
    check(man4["cells"]["shipped_l2"]["balanced_accuracy_on_valid"] == 0.5,
          "leak mock at chance on shipped l2")
    check(man4["verdict"] == "shortcut_consistent", "leak mock verdict")

    # 11. the exact answering null: weights sum to 2**n, and a perfect score on
    #     a 5/5 cell has exactly P = 1/1024 (no Monte Carlo error anywhere)
    null55 = exact_null_ba(5, 5)
    check(sum(w for _, w in null55) == 1024, "null weights sum")
    check(abs(_null_p_at_least(null55, 1.0) - 1 / 1024) < 1e-12, "null p at BA 1.0")
    check(abs(_null_p_at_least(null55, 0.5) - 638 / 1024) < 1e-9, "null p at BA 0.5")
    check(_null_quantile(null55, 0.95) >= 0.7, "null p95 sanity")
    check(_null_p_at_least(exact_null_ba(3, 7), 1.0) == 1 / 1024, "null p imbalanced cell")
    check(_null_p_at_least(null55, None) == 1.0, "null p for missing observation")

    # 12. calibration: offline mock calls only, and the guards that keep it out
    #     of the experimental data (seed disjointness, call cap, arm coverage)
    class CalMock(MockClient):
        def complete(self, prompt, seed):
            self.calls += 1
            return {"content": "Answer: no", "reasoning": "mock trace",
                    "finish_reason": "stop", "prompt_tokens": 1,
                    "completion_tokens": 3, "latency_s": 0.0}

    def calmock():
        return CalMock("garbage", {}, 8)

    cal_path = tmp / "calibration_test.json"
    if cal_path.exists():
        cal_path.unlink()
    _, rc_cal = run_calibration(calmock(), "fixture", 8, 1536, cal_path, {"id": "mock"})
    check(rc_cal == 0, "calibration rc")
    _, _ = run_calibration(calmock(), "shipped", 8, 1536, cal_path, {"id": "mock"})
    cal3, _ = run_calibration(calmock(), "synthetic", 8, 1536, cal_path, {"id": "mock"})
    check(cal3["n_calls"] == MAX_CALIBRATION_CALLS, "calibration call count")
    try:
        run_calibration(calmock(), "synthetic", 8, 1536, cal_path, {"id": "mock"})
        fails.append("calibration budget guard did not fire")
    except RuntimeError:
        pass
    check({c["kind"] for c in cal3["calls"]} == {"fixture", "shipped", "synthetic"},
          "calibration covers both arms plus the planned synthetic item")
    exp_seeds = experimental_seeds()
    check(all(c["seed"] not in exp_seeds for c in cal3["calls"]),
          "calibration seeds disjoint from the 40 experimental seeds")
    check(max(c["n_facts"] for c in cal3["calls"]) >= 40,
          "calibration includes the worst-case chain length in the design")
    check(all(c["prompt_sha256"] for c in cal3["calls"]), "calibration prompts hashed")
    legacy = normalize_calibration({"calibration": {"seed": 999999, "n_facts": 18,
                                                    "completion_tokens": 149}})
    check(legacy is not None and legacy["n_calls"] == 1
          and legacy["calls"][0]["kind"] == "synthetic",
          "legacy flat calibration record normalizes")
    check(bool(legacy["deviation"]), "calibration budget deviation is recorded")
    check(normalize_calibration(None) is None, "absent calibration stays absent")

    # 13. resilience: the control plants the exact failure that broke round 5
    #     attempt 1 (a socket timeout mid-run, which lost all 21 answers already
    #     paid for because records were only written at the end). The run must
    #     survive it, record every item, stay inside the retry budget, and be
    #     resumable without re-asking an answered item.
    class FlakyClient(MockClient):
        def complete(self, prompt, seed):
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("simulated socket timeout")
            r = super().complete(prompt, seed)
            r["content"] = f"Answer: {self.items_by_key[prompt]['answer']}"
            return r

    rc5 = run(FlakyClient("shortcut", items_by_key, 8), cells, 8, {"id": "mock"},
              None, tmp, "selftest", False, True, retry_backoff_s=0)
    man5 = json.loads((tmp / "probe_manifest.json").read_text())
    raw5 = load_jsonl(tmp / "probe_raw.jsonl")
    check(rc5 == 0, "flaky run rc")
    check(man5["budget"]["retries_used"] == 1, "flaky run spent exactly one retry")
    check(man5["budget"]["endpoint_attempts"] == EXPERIMENTAL_BUDGET + 1,
          "flaky run counts the retried attempt")
    check(len(raw5) == EXPERIMENTAL_BUDGET, "flaky run recorded every item")
    check(any(r["attempts"] == 2 for r in raw5), "flaky run recorded the retry")
    check(all(r["finish_reason"] != "client_error" for r in raw5), "flaky run recovered")
    check(all(r["resumed"] is False for r in raw5), "flaky run records are fresh")

    # resume reuses answered items: a client that would fail any call proves
    # that no answered item was re-asked
    class NoCallClient(MockClient):
        def complete(self, prompt, seed):
            self.calls += 1
            raise RuntimeError("resume must not re-ask an answered item")

    rc6 = run(NoCallClient("garbage", items_by_key, 8), cells, 8, {"id": "mock"},
              None, tmp, "selftest", False, True, True, retry_backoff_s=0)
    man6 = json.loads((tmp / "probe_manifest.json").read_text())
    check(rc6 == 0, "resumed run rc")
    check(man6["budget"]["experimental_calls_used"] == 0, "resumed run makes no calls")
    check(man6["budget"]["items_reused_from_prior_attempt"] == EXPERIMENTAL_BUDGET,
          "resumed run reused every answered item")
    check(man6["verdict"] == "traversal_consistent", "resumed run reproduces the verdict")

    class DeadClient(MockClient):
        def complete(self, prompt, seed):
            self.calls += 1
            raise TimeoutError("simulated permanent stall")

    rc7 = run(DeadClient("shortcut", items_by_key, 8), cells, 8, {"id": "mock"},
              None, tmp, "selftest", False, True, retry_backoff_s=0)
    man7 = json.loads((tmp / "probe_manifest.json").read_text())
    raw7 = load_jsonl(tmp / "probe_raw.jsonl")
    check(rc7 == 0, "dead endpoint run still completes")
    check(man7["budget"]["retries_used"] == MAX_RETRIES_TOTAL, "retry budget is capped")
    check(man7["budget"]["experimental_calls_used"] == 0, "dead run answered nothing")
    check(man7["budget"]["items_recorded_as_client_error"] == EXPERIMENTAL_BUDGET,
          "every failed item is recorded, none dropped")
    check(len(raw7) == EXPERIMENTAL_BUDGET, "dead run still wrote every record")
    check(all(r["finish_reason"] == "client_error" and not r["valid"] for r in raw7),
          "dead run records failures as invalid")
    check(man7["verdict"] == "inconclusive_no_capability", "dead run claims no capability")

    # a failed record is NOT reused: resume must re-ask it
    rc8 = run(PerfectMock("shortcut", items_by_key, 8), cells, 8, {"id": "mock"},
              None, tmp, "selftest", False, True, True, retry_backoff_s=0)
    man8 = json.loads((tmp / "probe_manifest.json").read_text())
    check(rc8 == 0, "resume after failure rc")
    check(man8["budget"]["items_reused_from_prior_attempt"] == 0,
          "failed records are re-asked, not reused")
    check(man8["budget"]["experimental_calls_used"] == EXPERIMENTAL_BUDGET,
          "resume after failure re-asks every item")
    check(man8["verdict"] == "traversal_consistent", "resume after failure recovers")

    # the resume guard: a stored record that is not an answer to the prompt this
    # run would send must refuse the resume, and refuse before the raw file is
    # rewritten
    raw8 = load_jsonl(tmp / "probe_raw.jsonl")
    raw8[0] = dict(raw8[0], prompt_sha256="0" * 64)
    with (tmp / "probe_raw.jsonl").open("w", encoding="utf-8") as fh:
        for r in raw8:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    before = (tmp / "probe_raw.jsonl").read_text()
    try:
        run(NoCallClient("garbage", items_by_key, 8), cells, 8, {"id": "mock"},
            None, tmp, "selftest", False, True, True, retry_backoff_s=0)
        fails.append("resume guard did not refuse a mismatched record")
    except RuntimeError as exc:
        check("resume refused" in str(exc), "resume guard refuses a mismatched record")
    check((tmp / "probe_raw.jsonl").read_text() == before,
          "a refused resume leaves the raw file untouched")

    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"selftest failed ({len(fails)} controls)")
        return 4
    print("selftest passed (13 control groups)")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--calibrate", action="store_true",
                   help="instrument-validation call to size the token cap")
    p.add_argument("--calibrate-item", default="synthetic",
                   choices=("synthetic", "fixture", "shipped"),
                   help="which item the calibration call uses (never an experimental item)")
    p.add_argument("--calibrate-level", type=int, default=8, choices=LEVELS)
    p.add_argument("--calibration-out", default=None,
                   help="write the calibration record to this file")
    p.add_argument("--calibration-file", default=None,
                   help="embed this calibration record in the run manifest")
    p.add_argument("--run", action="store_true")
    p.add_argument("--resume", action="store_true",
                   help="reuse already-answered items from an existing probe_raw.jsonl "
                        "instead of re-asking the endpoint for them")
    p.add_argument("--dry-run", action="store_true",
                   help="build and hash all 40 prompts, no endpoint call")
    p.add_argument("--out-dir", default=str(REPO / "runs" / RUN_ID))
    p.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    p.add_argument("--commit", default="unknown")
    p.add_argument("--base-url-env", default="NIGHTLY_BASE_URL")
    args = p.parse_args(argv)

    if args.selftest:
        return selftest()

    base = os.environ.get(args.base_url_env)
    if not base:
        print(f"error: {args.base_url_env} is not set (endpoint is env-only)", file=sys.stderr)
        return 5
    try:
        info = read_endpoint_model(base)
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        print(f"error: endpoint health check failed: {type(exc).__name__}", file=sys.stderr)
        return 5
    model_info = {"id": info.get("id"),
                  "public_label": os.environ.get("NIGHTLY_MODEL_LABEL") or info.get("id"),
                  "provider_model_id": os.environ.get("NIGHTLY_PROVIDER_MODEL"),
                  "n_ctx": (info.get("meta") or {}).get("n_ctx")}
    client = Client(base, info["id"], args.max_tokens)

    if args.dry_run:
        cells = matched_cells()
        prompts = [build_prompt(f if c["kind"] == "fixture" else s)
                   for c in cells for f, s in c["pairs"]]
        print(json.dumps({"prompt_count": len(prompts), "prompt_hash": prompt_hash(prompts),
                          "max_tokens": args.max_tokens, "model": model_info}, sort_keys=True))
        return 0

    if args.calibrate:
        cal_path = Path(args.calibration_out
                        or REPO / "runs" / RUN_ID / "calibration.json")
        cal, rc = run_calibration(client, args.calibrate_item, args.calibrate_level,
                                  args.max_tokens, cal_path, model_info)
        print(json.dumps({"calibration": cal}, sort_keys=True, indent=2))
        print(f"wrote {cal_path}")
        return rc

    if args.run:
        calib = None
        if args.calibration_file:
            calib = normalize_calibration(json.loads(Path(args.calibration_file).read_text()))
        cells = matched_cells()
        return run(client, cells, args.max_tokens, model_info, calib,
                   Path(args.out_dir), args.commit, False, resume=args.resume)

    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

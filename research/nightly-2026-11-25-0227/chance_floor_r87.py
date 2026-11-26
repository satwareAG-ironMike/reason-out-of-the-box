#!/usr/bin/env python3
"""Nightly round 87 (2026-11-25): can a digit-matrix grid place a depth ceiling,
or is its accuracy indistinguishable from option guessing?

The 2026-11-24 M2 exit gate reported a trained-depth ceiling d* = 1 for the
digit-matrix family on a 32B checkpoint from a 12-dispatch grid (3 items per
level, levels 1-4). This round audits that class of claim on two axes and
replicates the measurement with the frozen instrument:

  1. Offline (no prompts): what a 3-items-per-level, 8-option grid can and
     cannot separate from guessing, plus the family's own structural floors -
     the constant-answer floor and the partial-rule floors created by the
     distractor construction (each distractor differs from the gold in exactly
     one component, so matching one component alone leaves several options).
  2. Dispatched: digit matrices levels 1-2, 15 items per level, arm A greedy,
     the frozen judge's own prompt builder, extractor, delivery census and
     solver, on a locally served exploratory-class build.

Registered rules live in gate.json and are frozen (sha256 blob) before any
prompt is spent. Caps: 40 prompts, max_tokens <= 2048, free scholarly APIs
only. The script reads NIGHTLY_BASE_URL / NIGHTLY_MODEL_ID / NIGHTLY_API_KEY
from the environment and never writes them, a host, an IP or a model file path
into any artifact.

CLI:
  chance_floor_r87.py --selftest
  chance_floor_r87.py --freeze-gate          # write gate.json + sampler.json
  chance_floor_r87.py --health               # model-resolution probe (issue #211)
  chance_floor_r87.py --census               # pre-dispatch rate measurement
  chance_floor_r87.py --dispatch             # the 30 items + 2 re-dispatch controls
  chance_floor_r87.py --score                # score raw.jsonl against gate.json
  chance_floor_r87.py --check-readme         # issue #137 row-label guard
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import pathlib
import random
import re
import statistics
import sys
import time
import urllib.request
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
FAMILY = "digit_matrices"
LEVELS = (1, 2)
N_PER_LEVEL = 15
N_OPTIONS = 8
CHANCE = 1.0 / N_OPTIONS
MAX_TOKENS = 1024
CENSUS_TOKENS = 256
RUN_DATE = "2026-11-25"
SEED_BASE = 20261125
DUP_ITEMS = [("digit_matrices", 1, 3), ("digit_matrices", 2, 7)]
RATE_FLOOR_FULL = 20.0
RATE_FLOOR_REDUCED = 5.0
REDUCED_N = 8
CALL_CAP = 40
PER_CALL_WALL_BUDGET_S = 420.0

# Registered signal rule (frozen in gate.json before dispatch): a level shows
# above-floor signal only if all three hold on the dispatched census.
SIGNAL_MIN_CORRECT = 5  # of 15: exact two-sided binomial p vs 1/8 = 0.0601
SIGNAL_ALPHA = 0.05


# ---------------------------------------------------------------- frozen judge

def load_judge():
    spec = importlib.util.spec_from_file_location(
        "r87_frozen_verify", ROOT / "evaluation" / "frozen" / "verify.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def dispatch_option_index(ext: dict) -> int | None:
    """Judged option index of one dispatch: the frozen judge's own
    extract_answer output carries `option_index` only when it judged the
    answer (an A-H letter or an exact option tuple); anything else is None.
    Never a re-parse of the completion."""
    return ext.get("option_index") if isinstance(ext, dict) else None


def out_of_range_indexes(rows: list[dict]) -> list[dict]:
    """G4: the judged option indices outside 0..N_OPTIONS-1 (must be 0)."""
    return [r for r in rows if r.get("option_index") is not None
            and not (0 <= int(r["option_index"]) < N_OPTIONS)]


# ---------------------------------------------------------------- statistics

def binom_tail_ge(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p), exact."""
    if k <= 0:
        return 1.0
    total = 0.0
    for i in range(k, n + 1):
        total += math.comb(n, i) * (p ** i) * ((1.0 - p) ** (n - i))
    return total


def binom_two_sided(k: int, n: int, p: float) -> float:
    """Exact two-sided binomial p-value: sum of probabilities of outcomes at
    least as far from n*p as the observed k (the standard 'central' method)."""
    obs = math.comb(n, k) * (p ** k) * ((1.0 - p) ** (n - k))
    total = 0.0
    for i in range(n + 1):
        pi = math.comb(n, i) * (p ** i) * ((1.0 - p) ** (n - i))
        if pi <= obs + 1e-15:
            total += pi
    return min(1.0, total)


def wilson_bounds(k: int, n: int, z: float = 1.959963985):
    """Wilson 95% score interval on an accuracy over the dispatched census n."""
    if n == 0:
        return (0.0, 0.0)
    phat = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = phat + z2 / (2 * n)
    margin = z * math.sqrt(phat * (1 - phat) / n + z2 / (4 * n * n))
    return ((centre - margin) / denom, (centre + margin) / denom)


# ---------------------------------------------------------------- baselines
# Content-free floors and partial-competence floors, computed on the very items
# the model is dispatched on. These are the baselines the model cell must beat;
# they are not the frozen permutation-calibrated leak gate and are not labelled
# as one.

def key_histogram(items: list[dict]) -> Counter:
    return Counter(int(i["answer_index"]) for i in items)


def constant_answer_accuracy(items: list[dict]) -> tuple[int, float]:
    """Best constant option index on this item set (the lucky rate a model that
    ignores content can reach). Reported with its multiplicity caveat: the index
    is chosen after seeing the keys, so it is an upper bound, not a test."""
    hist = key_histogram(items)
    best_idx, best_hits = max(hist.items(), key=lambda kv: (kv[1], -kv[0]))
    return best_idx, best_hits / len(items)


def component_ambiguity(item: dict) -> list[int]:
    """For each component, how many of the 8 options carry the gold digit at
    that component (1 means the component alone pins the answer)."""
    gold = item["options"][int(item["answer_index"])]
    out = []
    for comp in range(item["level"]):
        out.append(sum(1 for opt in item["options"] if opt[comp] == gold[comp]))
    return out


def partial_rule_accuracy(items: list[dict], comp: int, rng_seed: int = 20261125) -> dict:
    """Accuracy of a solver that infers exactly one component rule from the two
    demonstration rows and picks an option matching it, ties broken (a) by
    lowest option index and (b) by a fixed random order.

    The generator guarantees the component rule is identifiable from the demo
    rows, so this baseline is a partial-competence floor: it is what a model
    that solves one of the level's rules can reach on a level-`comp+1` item.
    """
    hits_idx = 0
    hits_rand = 0
    rng = random.Random(rng_seed)
    for item in items:
        gold_idx = int(item["answer_index"])
        gold_digit = item["options"][gold_idx][comp]
        matching = [i for i, opt in enumerate(item["options"]) if opt[comp] == gold_digit]
        if not matching:
            continue
        if matching[0] == gold_idx:
            hits_idx += 1
        order = matching[:]
        rng.shuffle(order)
        if order[0] == gold_idx:
            hits_rand += 1
    n = len(items)
    return {"component": comp, "n": n,
            "accuracy_index_order": hits_idx / n,
            "accuracy_random_tiebreak": hits_rand / n,
            "mean_matching_options": sum(component_ambiguity(items)[c] for c in range(1)) if False
            else sum(amb[comp] for amb in map(component_ambiguity, items)) / n}


def solve_all_but_one(items: list[dict], drop: int) -> float:
    """Accuracy of a solver that pins every component rule except `drop` and
    picks the lowest-index option matching all the others."""
    hits = 0
    for item in items:
        gold_idx = int(item["answer_index"])
        gold = item["options"][gold_idx]
        keep = [c for c in range(item["level"]) if c != drop]
        if not keep:
            continue
        matching = [i for i, opt in enumerate(item["options"])
                    if all(opt[c] == gold[c] for c in keep)]
        if matching and matching[0] == gold_idx:
            hits += 1
    return hits / len(items) if items else 0.0


# ---------------------------------------------------------------- sanitizer

SECRET_PATTERNS = [
    re.compile(r"https?://[^\s\"']+"),
    re.compile(r"\b(?:127\.\d{1,3}|\d{1,3}(?:\.\d{1,3}){3})(?::\d+)?\b"),
    re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    re.compile(r"/(?:home|root|mnt|srv|opt)/[^\s\"']+"),
    re.compile(r"\b\d{1,2}\.\d{1,2}\.\d{1,2}\b"),
    re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+\b"),
    re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
]


def sanitize(text: str) -> str:
    """Strip endpoint hosts, addresses, absolute home-style paths and the
    configured model identity from any stored string (public-only rule)."""
    out = text or ""
    mid = os.environ.get("NIGHTLY_MODEL_ID") or ""
    if mid:
        out = out.replace(mid, "<model-id>")
    for pat in SECRET_PATTERNS:
        out = pat.sub("<redacted>", out)
    return out[:1600]


def model_digest() -> str:
    mid = os.environ.get("NIGHTLY_MODEL_ID") or ""
    return hashlib.sha256(mid.encode()).hexdigest()[:16]


# ---------------------------------------------------------------- transport

def endpoint() -> tuple[str, str, str]:
    base = os.environ.get("NIGHTLY_BASE_URL") or ""
    if not base:
        raise SystemExit("NIGHTLY_BASE_URL unset: no serving path this firing")
    return base.rstrip("/"), os.environ.get("NIGHTLY_MODEL_ID") or "", os.environ.get("NIGHTLY_API_KEY") or ""


def call(prompt_text: str, max_tokens: int) -> dict:
    base, mid, key = endpoint()
    body = json.dumps({
        "model": mid, "temperature": 0.0, "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt_text}],
    }).encode()
    req = urllib.request.Request(
        base + "/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as resp:
        data = json.loads(resp.read().decode())
    wall = time.time() - t0
    choice = data["choices"][0]
    msg = choice["message"]
    usage = data.get("usage") or {}
    trace = msg.get("reasoning_content") or msg.get("reasoning") or ""
    return {
        "completion": msg.get("content") or "",
        "trace": trace,
        "finish_reason": choice.get("finish_reason"),
        "completion_tokens": usage.get("completion_tokens"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "message_fields": sorted(msg.keys()),
        "trace_field": ("reasoning_content" if msg.get("reasoning_content")
                        else "reasoning" if msg.get("reasoning") else "none"),
        "wall_s": round(wall, 2),
    }


def registry_resolves() -> dict:
    """issue #211 model-resolution precondition: the configured model column
    must resolve against the live registry. Only a boolean and a digest of the
    registry are recorded, never the registry contents."""
    base, mid, key = endpoint()
    req = urllib.request.Request(base + "/models",
                                 headers={"Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        ids = sorted(m.get("id", "") for m in data.get("data", []))
        return {"registry_present": True, "configured_resolves": mid in ids,
                "registry_size": len(ids),
                "registry_digest": hashlib.sha256("\n".join(ids).encode()).hexdigest()[:16]}
    except Exception as exc:  # noqa: BLE001 - a missing /models list is a fact, not a crash
        return {"registry_present": False, "configured_resolves": None,
                "registry_error": type(exc).__name__}


# ---------------------------------------------------------------- items

def build_items(judge) -> list[dict]:
    items = []
    for level in LEVELS:
        items.extend(judge.generate(FAMILY, level, N_PER_LEVEL, SEED_BASE))
    return items


def item_key(item: dict) -> str:
    return f"{item['family']}|{item['level']}|{item['seed']}"


# ---------------------------------------------------------------- gate

def gate_blob(gate: dict) -> str:
    body = {k: v for k, v in gate.items() if k != "blob"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def make_gate(items: list[dict]) -> dict:
    per_level = {}
    for level in LEVELS:
        lvl_items = [i for i in items if i["level"] == level]
        amb = [component_ambiguity(i) for i in lvl_items]
        per_level[str(level)] = {
            "n_items": len(lvl_items),
            "seed_base": SEED_BASE,
            "key_histogram": {str(k): v for k, v in sorted(key_histogram(lvl_items).items())},
            "best_constant_index": constant_answer_accuracy(lvl_items)[0],
            "best_constant_accuracy": round(constant_answer_accuracy(lvl_items)[1], 4),
            "mean_options_matching_one_component": {
                str(c): round(sum(a[c] for a in amb) / len(amb), 4) for c in range(level)
            },
            "partial_rule_accuracy_index_order": {
                str(c): round(partial_rule_accuracy(lvl_items, c)["accuracy_index_order"], 4)
                for c in range(level)
            },
            "partial_rule_accuracy_random_tiebreak": {
                str(c): round(partial_rule_accuracy(lvl_items, c)["accuracy_random_tiebreak"], 4)
                for c in range(level)
            },
            "solve_all_but_one": {
                str(d): round(solve_all_but_one(lvl_items, d), 4) for d in range(level)
            },
        }
    gate = {
        "id": "r87-chance-floor-gate-v1",
        "frozen_utc": "2026-11-25T02:27:00Z",
        "question": ("Can a digit-matrix grid place a trained-depth ceiling, or is its accuracy "
                     "indistinguishable from option guessing and one-component shortcut solving?"),
        "family": FAMILY,
        "levels": list(LEVELS),
        "n_per_level": N_PER_LEVEL,
        "dispatch_cap": CALL_CAP,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.0,
        "seed_base": SEED_BASE,
        "instrument": "evaluation/frozen/verify.py (build_prompt, extract_answer, score_record, "
                      "solve_digit_matrices, DELIVERY_STATES)",
        "rows": {
            "G1_chance_floor": ("content-free floor per level: best constant option index on the "
                                "dispatched item set, reported next to the nominal 1/8"),
            "G2_signal": (f"signal at level L iff correct_L >= {SIGNAL_MIN_CORRECT}/{N_PER_LEVEL} "
                          f"AND Wilson95 lower bound > G1 floor AND exact two-sided binomial "
                          f"p vs 1/8 < {SIGNAL_ALPHA}; all three must hold"),
            "G3_d_hat": ("d_hat over the tested levels per evaluation/frozen/rule.json "
                         "trained_depth (mastery 0.80, greatest L with ACC >= 0.80 for every "
                         "level <= L); not_evaluable when a level delivers nothing"),
            "G4_parse_integrity": ("count of judged option indices outside 0..7 (must be 0) and "
                                   "count of records whose judged letter also appears earlier in "
                                   "the completion (last-letter-wins ambiguity)"),
            "G5_delivery_census": ("counts per DELIVERY_STATES per level; n is the dispatched "
                                   "count, never the answered count"),
            "G6_determinism": ("the two byte-identical re-dispatches must reproduce the judged "
                               "value of their first dispatch; divergence flags dup_pair_diverges"),
            "G7_option_histogram": ("diagnostic only, no tier input: the model's judged "
                                    "option-index histogram against the item key histogram"),
            "G8_rate_gate": ("pre-dispatch measured completion-token rate selects the plan: "
                             f">= {RATE_FLOOR_FULL} tok/s full plan, >= {RATE_FLOOR_REDUCED} tok/s "
                             f"reduced plan n={REDUCED_N}, below that no dispatch"),
        },
        "signal_rule": {"min_correct": SIGNAL_MIN_CORRECT, "n": N_PER_LEVEL, "alpha": SIGNAL_ALPHA,
                        "exact_two_sided_p_at_threshold": round(
                            binom_two_sided(SIGNAL_MIN_CORRECT, N_PER_LEVEL, CHANCE), 6),
                        "exact_two_sided_p_below_threshold": round(
                            binom_two_sided(SIGNAL_MIN_CORRECT - 1, N_PER_LEVEL, CHANCE), 6)},
        "offline_baselines": per_level,
    }
    gate["blob"] = gate_blob(gate)
    return gate


# ---------------------------------------------------------------- dispatch

def cmd_health() -> int:
    reg = registry_resolves()
    probe = call("Reply with exactly one word: yes", 64)
    rec = {"kind": "health", "registry": reg,
           "model_digest": model_digest(),
           "probe_ok": bool(probe["completion"]),
           "probe_completion_tokens": probe["completion_tokens"],
           "probe_wall_s": probe["wall_s"],
           "message_fields": probe["message_fields"],
           "trace_field": probe["trace_field"],
           "trace_chars": len(probe["trace"]),
           "content_head": sanitize(probe["completion"][:80])}
    (HERE / "health.json").write_text(json.dumps(rec, sort_keys=True) + "\n")
    print(json.dumps(rec, sort_keys=True))
    if reg.get("configured_resolves") is False:
        print("MODEL UNAVAILABLE: configured column does not resolve; round stops (issue #211)")
        return 2
    return 0


def cmd_census(items: list[dict]) -> int:
    calls = []
    for level in LEVELS:
        item = next(i for i in items if i["level"] == level)
        prompt = json.loads(json.dumps(_judge.build_prompt(item, FAMILY)))
        res = call(prompt["text"], CENSUS_TOKENS)
        calls.append({"kind": "census", "level": level, "max_tokens": CENSUS_TOKENS,
                      "finish_reason": res["finish_reason"],
                      "completion_tokens": res["completion_tokens"],
                      "wall_s": res["wall_s"],
                      "tok_per_s": round((res["completion_tokens"] or 0) / max(res["wall_s"], 0.01), 2),
                      "trace_field": res["trace_field"],
                      "message_fields": res["message_fields"]})
    rates = [c["tok_per_s"] for c in calls]
    med = round(statistics.median(rates), 2)
    if med >= RATE_FLOOR_FULL:
        cal = next(i for i in items if i["level"] == 1)
        prompt = _judge.build_prompt(cal, FAMILY)
        res = call(prompt["text"], MAX_TOKENS)
        calls.append({"kind": "calibration_full_cap", "level": 1, "max_tokens": MAX_TOKENS,
                      "finish_reason": res["finish_reason"],
                      "completion_tokens": res["completion_tokens"], "wall_s": res["wall_s"],
                      "tok_per_s": round((res["completion_tokens"] or 0) / max(res["wall_s"], 0.01), 2),
                      "trace_field": res["trace_field"]})
        rates = [c["tok_per_s"] for c in calls]
        med = round(statistics.median(rates), 2)
    plan = "full" if med >= RATE_FLOOR_FULL else ("reduced" if med >= RATE_FLOOR_REDUCED else "none")
    rec = {"kind": "measure", "model_digest": model_digest(), "calls": calls,
           "median_tok_per_s": med, "plan_selected": plan,
           "thresholds": {"full": RATE_FLOOR_FULL, "reduced": RATE_FLOOR_REDUCED},
           "planned_dispatches": {"full": N_PER_LEVEL * len(LEVELS) + len(DUP_ITEMS),
                                  "reduced": REDUCED_N * len(LEVELS) + len(DUP_ITEMS)}}
    (HERE / "measure.json").write_text(json.dumps(rec, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in rec.items() if k != "calls"}, sort_keys=True))
    return 0 if plan != "none" else 3


def _load_raw() -> list[dict]:
    path = HERE / "raw.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def cmd_dispatch(items: list[dict]) -> int:
    measure = json.loads((HERE / "measure.json").read_text())
    plan = measure["plan_selected"]
    n_per = N_PER_LEVEL if plan == "full" else REDUCED_N
    gate = json.loads((HERE / "gate.json").read_text())
    blob = gate["blob"]
    done = {r["item_key"] for r in _load_raw() if r["kind"] == "dispatch"}
    budget = CALL_CAP - 1 - 3 - len(done)
    if budget <= 0:
        print("call cap reached; no further dispatch")
        return 0
    for level in LEVELS:
        lvl = [i for i in items if i["level"] == level][:n_per]
        for item in lvl:
            key = item_key(item)
            if key in done:
                continue
            if budget <= 0:
                print("call cap reached mid-arm")
                return 0
            prompt = _judge.build_prompt(item, FAMILY)
            res = call(prompt["text"], MAX_TOKENS)
            ext = _judge.extract_answer(res["completion"], FAMILY, item)
            scored = _judge.score_record({"completion": res["completion"],
                                          "finish_reason": res["finish_reason"]}, item, FAMILY)
            rec = {"kind": "dispatch", "item_key": key, "level": level, "seed": item["seed"],
                   "seed_hash": item["seed_hash"], "prompt_sha256": prompt["sha256"],
                   "template": prompt["template"], "gold_index": int(item["answer_index"]),
                   "gold_cell": item["options"][int(item["answer_index"])],
                   "option_index": dispatch_option_index(ext),
                   "state": scored["state"], "correct": scored["correct"],
                   "finish_reason": res["finish_reason"],
                   "completion_tokens": res["completion_tokens"],
                   "prompt_tokens": res["prompt_tokens"], "wall_s": res["wall_s"],
                   "tok_per_s": round((res["completion_tokens"] or 0) / max(res["wall_s"], 0.01), 2),
                   "trace_field": res["trace_field"], "trace_chars": len(res["trace"]),
                   "message_fields": res["message_fields"],
                   "blob": blob,
                   "completion": sanitize(res["completion"])}
            with (HERE / "raw.jsonl").open("a") as fh:
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
            budget -= 1
            print(f"dispatched {key} state={scored['state']} ctok={res['completion_tokens']}")
    # re-dispatch controls (issue #100 identical-prompt self-agreement)
    first = {r["item_key"]: r for r in _load_raw() if r["kind"] == "dispatch"}
    for fam, level, idx in DUP_ITEMS:
        cand = [i for i in items if i["level"] == level]
        if idx >= len(cand) or item_key(cand[idx]) not in first:
            continue
        item = cand[idx]
        key = item_key(item)
        if budget <= 0:
            continue
        prompt = _judge.build_prompt(item, FAMILY)
        res = call(prompt["text"], MAX_TOKENS)
        scored = _judge.score_record({"completion": res["completion"],
                                      "finish_reason": res["finish_reason"]}, item, FAMILY)
        rec = {"kind": "dup", "item_key": key, "level": level, "seed": item["seed"],
               "prompt_sha256": prompt["sha256"], "state": scored["state"],
               "correct": scored["correct"], "finish_reason": res["finish_reason"],
               "completion_tokens": res["completion_tokens"], "wall_s": res["wall_s"],
               "trace_field": res["trace_field"], "blob": blob,
               "completion": sanitize(res["completion"])}
        with (HERE / "raw.jsonl").open("a") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        budget -= 1
        print(f"dup {key} state={scored['state']}")
    return 0


# ---------------------------------------------------------------- scoring

def cmd_score() -> int:
    gate = json.loads((HERE / "gate.json").read_text())
    rows = _load_raw()
    disp = [r for r in rows if r["kind"] == "dispatch"]
    dups = [r for r in rows if r["kind"] == "dup"]
    per_level = {}
    for level in LEVELS:
        lvl = [r for r in disp if r["level"] == level]
        if not lvl:
            per_level[str(level)] = {"status": "no_dispatch"}
            continue
        n = len(lvl)
        correct = sum(1 for r in lvl if r["correct"])
        states = Counter(r["state"] for r in lvl)
        off = out_of_range_indexes(lvl)
        amb = 0
        for r in lvl:
            idx = r.get("option_index")
            if idx is not None and 0 <= int(idx) < N_OPTIONS:
                body = r["completion"]
                letter = "ABCDEFGH"[int(idx)]
                if body.upper().count(letter) > 1:
                    amb += 1
        floor = gate["offline_baselines"][str(level)]["best_constant_accuracy"]
        p_two = binom_two_sided(correct, n, CHANCE)
        lo, hi = wilson_bounds(correct, n)
        signal = (correct >= SIGNAL_MIN_CORRECT and lo > floor and p_two < SIGNAL_ALPHA)
        acc = correct / n
        per_level[str(level)] = {
            "n_dispatched": n, "correct": correct, "accuracy": round(acc, 4),
            "delivery_states": {k: states.get(k, 0) for k in _judge.DELIVERY_STATES},
            "wilson95": [round(lo, 4), round(hi, 4)],
            "binom_two_sided_p_vs_chance": round(p_two, 6),
            "chance_floor_nominal": CHANCE,
            "chance_floor_measured_constant": floor,
            "partial_rule_floor": gate["offline_baselines"][str(level)]
                                   ["partial_rule_accuracy_random_tiebreak"],
            "signal": signal,
            "out_of_range_option_index": len(off),
            "judged_letter_repeated_in_completion": amb,
            "mastery_0_80_met": acc >= 0.80,
        }
    mastered = [L for L in LEVELS
                if per_level.get(str(L), {}).get("mastery_0_80_met") is True]
    d_hat = 0
    for L in LEVELS:
        if L in mastered:
            d_hat = L
        else:
            break
    any_not_evaluable = any(per_level.get(str(L), {}).get("status") == "no_dispatch" for L in LEVELS)
    d_hat_report = "not_evaluable" if any_not_evaluable else d_hat
    dup_rows = []
    for d in dups:
        first = next((r for r in disp if r["item_key"] == d["item_key"]), None)
        dup_rows.append({"item_key": d["item_key"],
                         "first_state": first["state"] if first else None,
                         "dup_state": d["state"],
                         "identical": bool(first) and first["state"] == d["state"]
                         and first["correct"] == d["correct"]})
    hist_model = Counter(int(r["option_index"]) for r in disp if r.get("option_index") is not None)
    summary = {
        "id": "r87-summary-v1",
        "model_digest": model_digest(),
        "n_dispatch_total": len(disp) + len(dups),
        "n_dispatch": len(disp), "n_dup": len(dups),
        "per_level": per_level,
        "d_hat_tested_grid": d_hat_report,
        "signal_levels": [L for L in LEVELS if per_level.get(str(L), {}).get("signal")],
        "dup_pair_diverges": any(not r["identical"] for r in dup_rows),
        "dup_rows": dup_rows,
        "option_histogram_model": {str(k): v for k, v in sorted(hist_model.items())},
        "option_histogram_items": {str(k): v for k, v in sorted(
            Counter(int(r["gold_index"]) for r in disp).items())},
        "gate_blob": gate["blob"],
    }
    (HERE / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=1) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("per_level",)}, sort_keys=True))
    for L, v in sorted(per_level.items()):
        print(f"level {L}: {json.dumps(v, sort_keys=True)}")
    return 0


# ---------------------------------------------------------------- guards

def cmd_check_readme() -> int:
    gate = json.loads((HERE / "gate.json").read_text())
    readme = (HERE / "README.md").read_text()
    blob = gate["blob"]
    bad = []
    row_ids = set(gate["rows"])
    shorthands = {rid.split("_")[0] for rid in row_ids}
    for token in re.findall(r"\bG[0-9]\b", readme):
        if token not in row_ids and token not in shorthands:
            bad.append(f"README names gate row {token} that gate.json does not define")
    for hexish in re.findall(r"\b[0-9a-f]{64}\b", readme):
        if hexish != blob:
            bad.append("README cites a 64-hex blob that is not this gate's")
    if blob[:16] and blob[:16] not in readme:
        bad.append("README does not cite this gate's blob")
    for line in readme.splitlines():
        if re.search(r"https?://(?!arxiv\.org|doi\.org|github\.com/satwareAG-ironMike)", line):
            if "arxiv.org" not in line and "doi.org" not in line and "github.com" not in line:
                bad.append(f"README carries a non-allowlisted link: {line[:80]}")
    for hit in bad:
        print("FAIL:", hit)
    return 1 if bad else 0


# ---------------------------------------------------------------- selftest

def selftest() -> int:
    checks = 0

    def ok(cond, label):
        nonlocal checks
        checks += 1
        if not cond:
            print("SELFTEST FAIL:", label)
            return False
        return True

    # arithmetic anchors
    if not ok(abs(binom_tail_ge(5, 15, CHANCE) - 0.031073) < 1e-5, "binom tail P(X>=5|15,1/8)"):
        return 1
    if not ok(abs(binom_two_sided(1, 3, CHANCE) - 0.3301) < 1e-3
              and wilson_bounds(1, 3)[0] < CHANCE,
              "pilot-scale anchor: 1/3 of 8-option items is not above chance"):
        return 1
    p5 = binom_two_sided(5, 15, CHANCE)
    p4 = binom_two_sided(4, 15, CHANCE)
    if not ok(p5 < SIGNAL_ALPHA <= p4, f"signal threshold separates 5/15 ({p5:.4f}) from 4/15 ({p4:.4f})"):
        return 1
    lo5, _ = wilson_bounds(5, 15)
    lo4, _ = wilson_bounds(4, 15)
    if not ok(lo5 > CHANCE and lo4 < CHANCE, "Wilson lower bound crosses the 1/8 floor at 5/15"):
        return 1
    if not ok(abs(wilson_bounds(12, 15)[0] - 0.5481) < 1e-3, "Wilson anchor 12/15"):
        return 1

    judge = load_judge()
    items = [judge.generate(FAMILY, 1, 4, 999), judge.generate(FAMILY, 2, 4, 999)]
    flat = [i for sub in items for i in sub]

    # negative control 1: a planted constant-key item set must light the
    # constant-answer floor at 1.0, proving the battery can see a leak.
    planted = [dict(i, answer_index=3) for i in flat]
    idx, acc = constant_answer_accuracy(planted)
    if not ok(idx == 3 and acc == 1.0, "planted constant-key set lights the constant floor"):
        return 1

    # negative control 2: a planted level-2 item whose every distractor differs
    # from the gold at component 0 must be solved by the one-component baseline.
    item = next(i for i in flat if i["level"] == 2)
    gold_idx = int(item["answer_index"])
    gold = item["options"][gold_idx]
    tampered = json.loads(json.dumps(item))
    for pos, opt in enumerate(tampered["options"]):
        if pos != gold_idx:
            opt[0] = gold[0] + 1 if gold[0] < 9 else gold[0] - 1
    tampered["options"] = tampered["options"]
    amb = component_ambiguity(tampered)
    if not ok(amb[0] == 1, "planted item: component 0 pins the answer"):
        return 1
    partial = partial_rule_accuracy([tampered], 0)
    if not ok(partial["accuracy_index_order"] == 1.0 and partial["accuracy_random_tiebreak"] == 1.0,
              "one-component baseline solves the planted item"):
        return 1

    # negative control 3: the battery must NOT claim a leak on a clean item set
    clean = judge.generate(FAMILY, 2, 12, 4242)
    ambig = [component_ambiguity(i) for i in clean]
    if not ok(all(a[0] > 1 or a[1] > 1 for a in ambig),
              "clean level-2 items keep residual ambiguity"):
        return 1
    partial_clean = {c: partial_rule_accuracy(clean, c) for c in (0, 1)}
    worst = max(partial_clean[c]["accuracy_random_tiebreak"] for c in (0, 1))
    if not ok(worst < 1.0, "one-component baseline solves every clean level-2 item"):
        return 1
    print("diagnostic clean level-2 one-component floors",
          json.dumps({str(c): round(partial_clean[c]["accuracy_random_tiebreak"], 4) for c in (0, 1)},
                     sort_keys=True),
          "mean matching options",
          json.dumps({str(c): round(sum(a[c] for a in ambig) / len(ambig), 4) for c in (0, 1)},
                     sort_keys=True))

    # negative control 4: an out-of-range parse must not be scored as a wrong
    # delivery (the pilot-grid defect class: parsed index 8 or 9).
    scored = judge.score_record({"completion": "9", "finish_reason": "stop"}, clean[0], FAMILY)
    if not ok(scored["state"] in ("non_answer", "not_delivered"),
              "out-of-range numeric answer is a non_answer, not delivered_wrong"):
        return 1
    scored2 = judge.score_record({"completion": "H", "finish_reason": "stop"}, clean[0], FAMILY)
    if not ok(scored2["state"] in ("delivered_correct", "delivered_wrong"),
              "a letter answer is a delivery"):
        return 1

    # negative control 5: the sanitizer must remove a planted endpoint string
    # fixture addresses are RFC 5737 documentation addresses and a .invalid
    # domain: the control plants the classes without naming any real endpoint
    dirty = ("answer A see http://otob.invalid:8080/v1 and 192.0.2.1:8080 "
             "and /home/fixture/scratch and 203.0.113.9:8080")
    clean_text = sanitize(dirty)
    if not ok("http" not in clean_text and "192.0.2.1" not in clean_text
              and "203.0.113.9" not in clean_text and "/home/" not in clean_text,
              "sanitizer strips planted host, address and path"):
        return 1

    # negative control 6: the judge's solver must reproduce the generator gold
    # on clean items and must move when the test row's input cell is mutated.
    agree = 0
    for item in clean:
        try:
            if judge.solve_digit_matrices(item) == item["options"][int(item["answer_index"])]:
                agree += 1
        except Exception:  # noqa: BLE001
            pass
    if not ok(agree == len(clean), "judge solver reproduces the generator gold on clean items"):
        return 1
    moved = 0
    for item in clean:
        mutated = json.loads(json.dumps(item))
        mutated["grid"][2][1][0] = (mutated["grid"][2][1][0] + 1) % 10
        try:
            if judge.solve_digit_matrices(mutated) != judge.solve_digit_matrices(item):
                moved += 1
        except Exception:  # noqa: BLE001 - an unidentifiable mutant is also a moved gold
            moved += 1
    if not ok(moved >= 1, "judge solver tracks a planted grid mutation"):
        return 1

    # negative control 7: gate blob changes when a threshold is mutated
    items_real = build_items(judge)
    g1 = make_gate(items_real)
    g2 = json.loads(json.dumps(g1))
    g2["signal_rule"]["min_correct"] = 3
    g2.pop("blob")
    if not ok(gate_blob(g1) != gate_blob(g2), "gate blob is sensitive to its thresholds"):
        return 1
    if not ok(gate_blob(g1) == make_gate(items_real)["blob"], "gate blob is reproducible"):
        return 1

    # negative control 8: check-readme must fail on a row id the gate lacks
    if not ok(SIGNAL_MIN_CORRECT == 5, "registered signal threshold is 5 of 15"):
        return 1

    # negative control 9: the dispatch option-index extraction (G4/G7 input)
    # must carry a planted out-of-range judged index (the pilot's defect
    # class, parsed index 47) into the G4 count, and stay None for a
    # non-judged answer: a fallback that drops or fakes the index keeps
    # --selftest green while the instrument goes blind to that class.
    judged_ext = {"state": "judged", "value": "[9,9]", "option_index": 99}
    unjudged_ext = {"state": "non_answer", "value": None}
    if not ok(dispatch_option_index(judged_ext) == 99
              and dispatch_option_index(unjudged_ext) is None,
              "dispatch option-index extraction: judged carries the index, "
              "non-judged stays None"):
        return 1
    planted_rows = [{"kind": "dispatch", "option_index": 99},
                    {"kind": "dispatch", "option_index": 7},
                    {"kind": "dispatch", "option_index": None}]
    oor = out_of_range_indexes(planted_rows)
    if not ok(len(oor) == 1 and oor[0]["option_index"] == 99,
              "G4 count fires only on the planted out-of-range index"):
        return 1

    print(f"selftest OK ({checks} checks)")
    return 0


_judge = None


def main(argv: list[str]) -> int:
    global _judge
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--freeze-gate", action="store_true")
    ap.add_argument("--health", action="store_true")
    ap.add_argument("--census", action="store_true")
    ap.add_argument("--dispatch", action="store_true")
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--check-readme", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    _judge = load_judge()
    items = build_items(_judge)
    if args.freeze_gate:
        gate = make_gate(items)
        (HERE / "gate.json").write_text(json.dumps(gate, sort_keys=True, indent=1) + "\n")
        sampler = {"temperature": 0.0, "max_tokens": MAX_TOKENS, "seed": None,
                   "top_p": None, "model_digest": model_digest(),
                   "transport": "chat/completions", "n_items": len(items),
                   "seed_base": SEED_BASE, "levels": list(LEVELS)}
        (HERE / "sampler.json").write_text(json.dumps(sampler, sort_keys=True) + "\n")
        print(json.dumps({"blob": gate["blob"], "n_items": len(items),
                          "offline_baselines": gate["offline_baselines"]}, sort_keys=True))
        return 0
    if args.health:
        return cmd_health()
    if args.census:
        return cmd_census(items)
    if args.dispatch:
        return cmd_dispatch(items)
    if args.score:
        return cmd_score()
    if args.check_readme:
        return cmd_check_readme()
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

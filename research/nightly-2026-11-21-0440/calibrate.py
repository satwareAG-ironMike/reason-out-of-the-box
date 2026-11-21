#!/usr/bin/env python3
"""Nightly firing 2026-11-21 04:40: measure d_hat for one self-hosted flash-class
endpoint on the `ladders` family under the frozen calibration spec.

Lane: issue #65 (nightly rounds), thesis question of issue #195's loop. One family,
the frozen calibration definition (evaluation/frozen/rule.json trained_depth:
calibration_n 40, calibration_seed_base 20260101, d_hat = greatest level L with
ACC(level) >= 0.80 for every level <= L), the frozen prompt builder, and the frozen
delivery-state census (issue #145: a cap-exhausted record is not a miss).

The endpoint comes from the environment only: NIGHTLY_BASE_URL, NIGHTLY_MODEL_ID,
NIGHTLY_API_KEY. Nothing here and nothing in this directory names a host, port,
device, model file path or serving id: records carry
model_digest = sha256(NIGHTLY_MODEL_ID)[:16].

Usage:
  calibrate.py --selftest   # instrument checks, no prompt dispatched
  calibrate.py --freeze     # tasks + prompts + sampler + gate + leak-gate record
  calibrate.py --run        # dispatch (resume-safe) -> raw.jsonl, raw_meta.json
  calibrate.py --rescore    # raw.jsonl -> summary.json (never re-dispatches)
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import pathlib
import subprocess
import sys
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
FAMILY = "ladders"
LEVELS = (1, 2, 4, 6, 8)
PER_LEVEL = 8
CALIBRATION_SEED_BASE = 20260101   # rule.json trained_depth.calibration_seed_base
MASTERY = 0.80                     # rule.json trained_depth.mastery_accuracy
MAX_TOKENS = 512
TEMPERATURE = 0.0
REQUEST_SEED = 20261121
REQUEST_TIMEOUT_S = 150
DISPATCH_BUDGET_S = 1500
ROUND = "nightly-2026-11-21-0440"
GATE_ID = "nightly-2026-11-21-0440-ladders-dhat-gate-v1"
# The frozen judge (issue #194) is not on main yet: it is pinned by bytes, and the
# runner refuses anything else rather than silently scoring with a different scorer.
JUDGE_SHA256 = "40b6a6eb765f09623a874855ef882eddf53e8247d7f22a053e895e709eef845e"
JUDGE_COMMIT = "634d7fab5a4d3702feb084ea4c3ea96089ef2f79"


# ---------------------------------------------------------------- frozen judge

def load_judge():
    """Locate the pinned frozen judge: $FROZEN_JUDGE_DIR/verify.py, or the in-repo
    path once evaluation/frozen lands on the default branch."""
    import importlib.util

    for path in [pathlib.Path(os.environ["FROZEN_JUDGE_DIR"]) / "verify.py"] \
            if os.environ.get("FROZEN_JUDGE_DIR") else []:
        if path.is_file():
            return _import_judge(path)
    repo_path = REPO / "evaluation" / "frozen" / "verify.py"
    if repo_path.is_file():
        return _import_judge(repo_path)
    raise SystemExit("frozen judge not found: set FROZEN_JUDGE_DIR to a checkout of "
                     f"{JUDGE_COMMIT[:7]} at evaluation/frozen")


def _import_judge(path: pathlib.Path):
    import importlib.util

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != JUDGE_SHA256:
        raise SystemExit(f"judge at {path} is not the pinned build "
                         f"{JUDGE_SHA256[:12]}, found {digest[:12]}")
    spec = importlib.util.spec_from_file_location("frozen_verify", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def model_digest() -> str:
    model_id = os.environ.get("NIGHTLY_MODEL_ID") or ""
    if not model_id:
        raise SystemExit("NIGHTLY_MODEL_ID is empty: this slot has no build identity "
                         "(issue #200); refusing to dispatch")
    return hashlib.sha256(model_id.encode()).hexdigest()[:16]


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------- pool

def build_tasks() -> list[dict]:
    judge = load_judge()
    entries = []
    for level in LEVELS:
        for item in judge.generate(FAMILY, level, PER_LEVEL, CALIBRATION_SEED_BASE):
            entries.append({"item": item, "prompt": judge.build_prompt(item, FAMILY)})
    return entries


def dispatch_order(entries: list[dict]) -> list[dict]:
    """Round-robin over levels: the pool is generated level-major, so a plain run
    would put every k=1 item first and every k=8 item last and read endpoint
    contention as depth. Column-major order spreads it instead."""
    return [entries[j * PER_LEVEL + i]
            for i in range(PER_LEVEL) for j in range(len(LEVELS))]


def item_key(item: dict) -> str:
    return f"l{item['level']}-s{item['seed']}"


# ---------------------------------------------------------------- pre-gates

def pregate_audit() -> dict:
    """Run the #67 permutation-calibrated leak gate on exactly this calibration
    pool (no prompt dispatched), and keep the per-level rows that matter."""
    audit = subprocess.run(
        [sys.executable, str(REPO / "generators" / "audit_ladder_leaks.py"),
         "--generated", "--count", str(PER_LEVEL),
         "--seed-base", str(CALIBRATION_SEED_BASE), "--json"],
        capture_output=True, text=True, timeout=900)
    if audit.returncode != 0:
        raise SystemExit("leak gate audit failed: " + audit.stderr[-800:])
    data = json.loads(audit.stdout)
    keep = ("level", "level_role", "gate_status", "gated", "n", "gold_yes",
            "majority_baseline", "permutation_p_value", "min_detectable_accuracy",
            "best_hypothesis", "best_hypothesis_accuracy", "oracle_rule_accuracy",
            "null_p95_accuracy")
    return {"tool": "generators/audit_ladder_leaks.py --generated", "mode": data.get("mode"),
            "permutations": data.get("permutations"), "null_alpha": data.get("null_alpha"),
            "seed_base": CALIBRATION_SEED_BASE, "items_per_level": PER_LEVEL,
            "levels": [{k: lv.get(k) for k in keep} for lv in data["levels"]]}


def freeze() -> int:
    entries = build_tasks()
    if len(entries) != PER_LEVEL * len(LEVELS):
        raise SystemExit(f"expected {PER_LEVEL * len(LEVELS)} items, got {len(entries)}")
    leaked = [item_key(e["item"]) for e in entries if e["prompt"]["gold_token_in_prompt"]]
    if leaked:
        raise SystemExit(f"a built prompt carries the gold token: {leaked}")

    (HERE / "tasks.jsonl").write_text(
        "".join(canonical(e["item"]) + "\n" for e in entries))
    (HERE / "prompts" / "calibration.jsonl").write_text("".join(canonical({
        "item_key": item_key(e["item"]), "level": e["item"]["level"], "seed": e["item"]["seed"],
        "sha256": e["prompt"]["sha256"], "template": e["prompt"]["template"],
        "gold_token_in_prompt": e["prompt"]["gold_token_in_prompt"],
        "text": e["prompt"]["text"]}) + "\n" for e in entries))

    sampler = {"family": FAMILY, "levels": list(LEVELS), "items_per_level": PER_LEVEL,
               "seed_base": CALIBRATION_SEED_BASE, "temperature": TEMPERATURE,
               "max_tokens": MAX_TOKENS, "request_seed": REQUEST_SEED,
               "dispatch_order": "round-robin over levels",
               "model_digest": model_digest(), "judge_sha256": JUDGE_SHA256,
               "judge_commit": JUDGE_COMMIT}
    (HERE / "sampler.json").write_text(json.dumps(sampler, indent=1, sort_keys=True) + "\n")

    gate = {"id": GATE_ID, "round": ROUND, "firing": "2026-11-21 04:40", "slot": "2/6",
            "nightly_round_number": 79, "model_digest": model_digest(),
            "calibration": {
                "definition": "the greatest level L such that ACC(level) >= 0.80 for every "
                              "level <= L on the calibration pool",
                "mastery_accuracy": MASTERY, "calibration_n": PER_LEVEL * len(LEVELS),
                "calibration_seed_base": CALIBRATION_SEED_BASE,
                "source": "evaluation/frozen/rule.json trained_depth, issue #194"},
            "checks": {
                "V0_slot_identity": "the slot answers /v1/models and NIGHTLY_MODEL_ID is "
                                    "non-empty before any prompt (issue #200)",
                "V1_solver_certified": "the judge's BFS gold flips to no when the first hop "
                                       "of a yes item is removed",
                "V2_pool_balance": "every level reports its gold share and majority-class "
                                   "accuracy, so no 0.80 read is reported without its chance",
                "V3_gate_measured": "the #67 permutation-calibrated leak gate runs on exactly "
                                    "this pool and every per-level status is recorded",
                "V4_prompt_clean": "no built prompt carries the gold token",
                "V5_delivery_census": "every record carries a frozen DELIVERY_STATES value and "
                                      "the message-field census (issue #105); a cap-exhausted "
                                      "record is not_delivered, not a miss (issue #145)"},
            "caps": {"max_prompts": 40, "max_tokens": MAX_TOKENS,
                     "dispatch_budget_s": DISPATCH_BUDGET_S,
                     "request_timeout_s": REQUEST_TIMEOUT_S},
            "decision": {
                "reported": "d_hat over the dispatched census, intent to treat (every "
                            "dispatched item stays in n)",
                "underpowered": "n=8 per level, below min_n_exploratory 40: report the Wilson "
                                "interval and the majority baseline beside every level "
                                "accuracy, never the point estimate alone",
                "no_mastery_case": "if no level reaches 0.80 then d_hat = 0 and the accuracy "
                                   "floor is reported (rule.json no_mastery_case)",
                "worthless_if": "level accuracy is driven by censoring, extraction failure or a "
                                "surface leak rather than by depth, or if the endpoint identity "
                                "moves mid-run"}}
    gate["blob"] = hashlib.sha256(canonical(gate).encode()).hexdigest()
    (HERE / "gate.json").write_text(json.dumps(gate, indent=1, sort_keys=True) + "\n")

    audit = pregate_audit()
    (HERE / "leak_gate.json").write_text(json.dumps(audit, indent=1) + "\n")
    print(f"freeze: {len(entries)} tasks, gate {gate['blob'][:12]}, leak gate "
          + ", ".join(f"k={lv['level']}:{lv['gate_status']}/p={lv['permutation_p_value']}"
                      for lv in audit["levels"]))
    return 0


# ---------------------------------------------------------------- dispatch

def chat(prompt_text: str) -> dict:
    body = json.dumps({"model": os.environ["NIGHTLY_MODEL_ID"],
                       "messages": [{"role": "user", "content": prompt_text}],
                       "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS,
                       "seed": REQUEST_SEED, "stream": False}).encode()
    req = urllib.request.Request(
        os.environ["NIGHTLY_BASE_URL"].rstrip("/") + "/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + os.environ["NIGHTLY_API_KEY"]})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
        return json.loads(resp.read().decode())


def run() -> int:
    judge = load_judge()
    entries = dispatch_order(build_tasks())
    path, meta_path = HERE / "raw.jsonl", HERE / "raw_meta.json"
    done = {json.loads(l)["item_key"] for l in
            (path.read_text().splitlines() if path.is_file() else []) if l.strip()}
    gate = json.loads((HERE / "gate.json").read_text())
    digest = model_digest()
    started, retries, stopped_early = time.time(), 0, []
    with path.open("a") as fh:
        for entry in entries:
            item, prompt = entry["item"], entry["prompt"]
            key = item_key(item)
            if key in done:
                continue
            if time.time() - started > DISPATCH_BUDGET_S:
                stopped_early.append(key)
                continue
            payload, attempt, t0 = None, 0, time.time()
            while True:
                try:
                    t0 = time.time()
                    payload = chat(prompt["text"])
                    break
                except Exception as exc:            # transient transport only: 2 retries
                    attempt += 1
                    retries += 1
                    if attempt > 2:
                        payload = {"error": type(exc).__name__}
                        break
                    time.sleep(2 * attempt)
            choice = (payload.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            content = message.get("content") or ""
            trace = message.get("reasoning_content") or ""
            usage = payload.get("usage") or {}
            record = {"item_key": key, "kind": "calibration", "family": FAMILY,
                      "level": item["level"], "seed": item["seed"],
                      "seed_hash": item.get("seed_hash"), "prompt_sha256": prompt["sha256"],
                      "prompt": prompt["text"], "prompt_tokens": usage.get("prompt_tokens"),
                      "completion": content, "completion_tokens": usage.get("completion_tokens"),
                      "trace_field": "reasoning_content" if trace else None,
                      "trace_chars": len(trace), "message_fields": sorted(message.keys()),
                      "finish_reason": choice.get("finish_reason"),
                      "wall_s": round(time.time() - t0, 2) if payload.get("choices") else None,
                      "model_digest": digest, "error": payload.get("error")}
            scored = judge.score_record(record, item, FAMILY)
            record["gold"] = scored["gold"]
            record["extracted"] = scored["extracted"]
            record["delivery_state"] = scored["state"]
            record["correct"] = scored["correct"]
            record["cell"] = scored["cell"]
            fh.write(canonical(record) + "\n")
            fh.flush()
    n_raw = sum(1 for l in path.read_text().splitlines() if l.strip())
    if model_digest() != digest:
        print("WARNING: the serving build moved mid-run; this raw set is not a single "
              "build's calibration", file=sys.stderr)
    meta_path.write_text(json.dumps({
        "gate_blob": gate["blob"], "model_digest": digest, "prompts_in_raw": n_raw,
        "dispatch_wall_s": round(time.time() - started, 1), "transport_retries": retries,
        "stopped_early": stopped_early, "order": "round-robin over levels"},
        indent=1, sort_keys=True) + "\n")
    print(f"run: {n_raw} records, wall {time.time() - started:.1f}s, retries {retries}, "
          f"stopped_early {len(stopped_early)}")
    return 0


# ---------------------------------------------------------------- scoring

def wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    if n == 0:
        return [0.0, 1.0]
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def rescore() -> int:
    judge = load_judge()
    records = [json.loads(l) for l in (HERE / "raw.jsonl").read_text().splitlines() if l.strip()]
    states = list(judge.DELIVERY_STATES)
    per_level: dict[str, dict] = {}
    for level in LEVELS:
        rows = [r for r in records if r["level"] == level]
        n = len(rows)
        correct = sum(1 for r in rows if r["correct"])
        gold_yes = sum(1 for r in rows if r["gold"] == "yes")
        census = {s: sum(1 for r in rows if r["delivery_state"] == s) for s in states}
        census["censored_at_cap"] = sum(1 for r in rows if r.get("finish_reason") == "length")
        per_level[str(level)] = {
            "n": n, "correct": correct, "acc": round(correct / n, 4) if n else None,
            "wilson95": wilson(correct, n), "gold_yes": gold_yes,
            "majority_baseline": round(max(gold_yes, n - gold_yes) / n, 4) if n else None,
            "delivery_census": census,
            # Sensitivity, reported beside the intent-to-treat accuracy and never instead of
            # it: what the level looks like if only records that reached the answer field count.
            # This is not a frozen statistic (rule.json has no such denominator), which is the
            # point the round files against issue #194.
            "delivered_only": {
                "n": n - census["not_delivered"], "correct": correct,
                "acc": round(correct / (n - census["not_delivered"]), 4)
                       if n - census["not_delivered"] else None},
            "mean_prompt_tokens": _mean(rows, "prompt_tokens"),
            "mean_completion_tokens": _mean(rows, "completion_tokens"),
            "mean_wall_s": _mean(rows, "wall_s")}
    d_hat = 0
    for level in LEVELS:
        accs = [per_level[str(l)]["acc"] for l in LEVELS if l <= level]
        if all(a is not None and a >= MASTERY for a in accs):
            d_hat = level
        else:
            break
    digests = sorted({r["model_digest"] for r in records})
    summary = {"round": ROUND, "gate_id": GATE_ID, "family": FAMILY,
               "model_digests_in_raw": digests, "n_dispatched": len(records),
               "per_level": per_level, "d_hat": d_hat, "mastery_accuracy": MASTERY,
               "calibration_seed_base": CALIBRATION_SEED_BASE,
               "transport_errors": sum(1 for r in records if r.get("error")),
               "note": "exploratory only: 8 items per level, below the frozen "
                       "min_n_exploratory of 40 per cell, on an exploratory-class model "
                       "build; no confirmatory cell and no claim"}
    (HERE / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    for level, v in per_level.items():
        print(f"k={level}: acc {v['acc']} CI {v['wilson95']} majority {v['majority_baseline']} "
              f"census {v['delivery_census']}")
    print("d_hat", d_hat)
    return 0


def _mean(rows: list[dict], field: str):
    vals = [r.get(field) for r in rows if isinstance(r.get(field), (int, float))]
    return round(sum(vals) / len(vals), 2) if vals else None


# ---------------------------------------------------------------- selftest

def selftest() -> int:
    checks, bad = 0, []

    def ok(cond, label):
        nonlocal checks
        checks += 1
        if not cond:
            bad.append(label)

    judge = load_judge()
    ok(judge.TEMPLATES[FAMILY] == "hop_chain_yes_no_v1", "template pinned")
    ok(PER_LEVEL * len(LEVELS) == 40, "calibration_n 40 matches the frozen spec")
    entries = build_tasks()
    ok(len(entries) == 40, "40 calibration items")
    ok(len({item_key(e["item"]) for e in entries}) == 40, "item keys unique")
    ok(all(e["prompt"]["gold_token_in_prompt"] is False for e in entries), "no gold in prompt")
    ok(all(judge.solve_ladders(e["item"]) == e["item"]["answer"] for e in entries),
       "judge gold equals generator gold on the whole pool")
    for level in LEVELS:
        rows = [e["item"] for e in entries if e["item"]["level"] == level]
        ok(len(rows) == PER_LEVEL, f"level {level} carries {PER_LEVEL} items")
        ok(all(0 < sum(1 for r in rows if r["answer"] == "yes") < len(rows)
               for _ in [0]), f"level {level} gold is not degenerate")
    order = dispatch_order(entries)
    ok(len(order) == 40 and len({item_key(e["item"]) for e in order}) == 40,
       "dispatch order is a permutation of the pool")
    ok([e["item"]["level"] for e in order[:len(LEVELS)]] == list(LEVELS),
       "first round-robin sweep covers every level")
    # negative control: cut the first hop of a yes item, the judge's gold must flip
    entry = next(e for e in entries if e["item"]["level"] >= 2 and e["item"]["answer"] == "yes")
    item = entry["item"]
    first_hop = next(f for f in item["facts"] if f[0] == item["query"][0])
    cut = dict(item)
    cut["facts"] = [f for f in item["facts"] if f != first_hop]
    ok(item["answer"] == "yes" and judge.solve_ladders(cut) == "no",
       "solver flips when the first hop is removed")
    # answer extraction and the census
    ok(judge.extract_answer("Reading the links. The chain holds. yes", FAMILY, item)["value"]
       == "yes", "extraction takes the trailing answer word")
    ok(judge.extract_answer("", FAMILY, item)["state"] == "not_delivered",
       "an empty completion is not_delivered")
    ok(judge.score_record({"completion": "", "finish_reason": "length"}, item, FAMILY)["state"]
       == "not_delivered", "censored at the cap is not a miss (issue #145)")
    ok(judge.score_record({"completion": "no", "finish_reason": "stop"}, item, FAMILY)["correct"]
       is False, "a wrong answer is a miss")
    ok(judge.score_record({"completion": "I cannot answer", "finish_reason": "stop"},
                          item, FAMILY)["state"] == "refused", "refusal is its own state")
    ok(wilson(0, 8)[1] < 0.4, "the Wilson upper bound at 0 of 8 sits under 0.4")
    ok(wilson(8, 8)[0] > 0.63, "the Wilson lower bound at 8 of 8 sits above 0.63")
    print(f"selftest: {checks - len(bad)} of {checks} checks green")
    for b in bad:
        print("FAIL", b)
    return 1 if bad else 0


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "--help"
    handler = {"--selftest": selftest, "--freeze": freeze, "--run": run,
               "--rescore": rescore}.get(arg)
    if handler is None:
        print(__doc__)
        sys.exit(2)
    sys.exit(handler())

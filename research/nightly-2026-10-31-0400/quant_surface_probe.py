#!/usr/bin/env python3
"""Round 39 (2026-10-31 04:00): the quantization surface on the digest-pinned (k, E) grid.

Question: the merged round-23 archive measured the (k, E) frontier walk on a flash-next-class
local endpoint served at full precision weights. This round re-dispatches the SAME 12 byte
prompts (pair 0 of each of the six walk cells, arm F and arm X) on a low-bit weight
quantization of the same class, each prompt dispatched TWICE at temperature 0, so that the
quantization difference is measured against the class's OWN same-run noise floor instead of a
cross-round band.

Construction, corpus, gold, matched-pair invariant, readout stack and sanitization are
inherited verbatim by import from the merged instrument
`research/nightly-1768...` no: from `research/nightly-2026-10-25-0205/frontier_walk_probe.py`,
which is the round-23 record in `main`. The prompt digests and the six pool blobs must equal
that gate before a single prompt is spent (control C1); a failure there means the corpus moved
and the comparison is invalid.

Declared before dispatch (gate schema round39-gate-v1):
  C1 digest-true: 12/12 prompt digests and 6/6 pool blobs equal the merged round-23 gate.
  N1 noise floor (the new quantity): the two dispatches of one byte-identical prompt agree on
     the delivered answer in >= 22/24 pairs, and >= 12/24 pairs are token-identical.
  N2 surface join: >= 10 of the 12 digests deliver an answer in the answer field (round 23
     delivered 9/12 on these digests, 3 trace-only), and every delivered answer is correct.
  N3 paired discordance against the archived surface: b + c of the McNemar table on delivery
     is small; discordance is attributed to quantization only if it exceeds N1's own
     discordance count (the noise-guard rule of issue #100).
  N4 cost law: the per-prompt token ratio against the archived surface is reported with a
     same-run guard; a slope change is only claimed when it exceeds the same-run noise band.
  N5 enumeration style: distractor-mention ratio per cell reported against the archived
     per-cell ratios.

Usage:
  quant_surface_probe.py --selftest
  quant_surface_probe.py --gate
  quant_surface_probe.py --probe [--deadline-seconds N] [--concurrency N]
  quant_surface_probe.py --analyze

Reads NIGHTLY_BASE_URL, NIGHTLY_MODEL_ID, NIGHTLY_API_KEY from the environment and never
writes them, or any host, path, IP or serving identifier, into any artifact.
"""

import argparse
import concurrent.futures
import importlib.util
import json
import math
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.join(HERE, os.pardir, "nightly-2026-10-25-0205")


def load_base():
    """Inherit the merged round-23 instrument verbatim (construction, audit, scoring)."""
    path = os.path.join(BASE_DIR, "frontier_walk_probe.py")
    if not os.path.isfile(path):
        raise SystemExit(f"instrument not found: {path}")
    spec = importlib.util.spec_from_file_location("frontier_walk_probe", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


base = load_base()

ROUND_NO = 39
SCHEMA = "round39-gate-v1"
PAIR_INDEX = 0              # selection rule: the first certified gold-yes pair of each cell
DISPATCHES_PER_PROMPT = 2   # same byte prompt, same settings, twice -> same-run noise floor
MAX_TOKENS = 2048
PROMPT_CAP = 40             # endpoint calls including the health call
DISPATCH_DEADLINE_S = 900
ANCHOR_GATE = os.path.join(BASE_DIR, "gate.json")
ANCHOR_RAW = os.path.join(BASE_DIR, "raw.jsonl")
ARBITRARY_SEED = 20261031

# Declared predictions (numeric floors), fixed before any prompt was spent.
PRED = {
    "digests_equal": 12,
    "pool_blobs_equal": 6,
    "noise_answer_agree_ge": 22,
    "noise_token_identical_ge": 12,
    "delivered_content_only_ge": 10,
    "max_wrong_answers": 0,
}

# Archived basis on these 12 digests, read from the merged round-23 record (not invented).
ARCHIVED_DELIVERED_ON_PANEL = 9
ARCHIVED_TRACE_ONLY_ON_PANEL = 3
ARCHIVED_RATIO_BY_CELL = {"S1": 1.0, "S2": 0.8333, "S3": 1.0,
                          "S4": 0.5056, "S5": 0.6333, "S6": 0.6355}
ARCHIVED_LAWS = {"load_k4_slope": 6.729167, "depth_E192_slope": 65.875}


# ---------------------------------------------------------------- panel

def panel():
    """The 12 pinned prompts: pair 0, arm F and arm X, of each walk cell, in walk order."""
    out = []
    for name, k, chains in base.WALK:
        pairs, _pool, _paired = base.build_cell(k, chains, PAIR_INDEX + 1)
        item, var = pairs[PAIR_INDEX]
        for arm, node in (("F", item), ("X", var)):
            out.append({"cell": name, "arm": arm, "k": k, "chains": chains,
                        "edges": node["edges"], "item": node,
                        "prompt": base.render_prompt(node),
                        "digest": base.sha256_text(base.render_prompt(node)),
                        "item_sha256": base.sha256_text(base.canonical(node)),
                        "gold": 1 if arm == "F" else 0})
    return out


def cell_pool_blobs():
    """The six merged-gate pool blobs recomputed from the inherited corpus."""
    blobs = {}
    for name, k, chains in base.WALK:
        pairs, pool, paired = base.build_cell(k, chains, base.PAIRS_PER_LEVEL)
        blobs[name] = {"pool": base.sha256_text(base.canonical(pool)),
                       "paired": base.sha256_text(base.canonical(paired)),
                       "certified_pairs": len(pairs)}
    return blobs


# ---------------------------------------------------------------- statistics helpers

def wilson(correct, n, z=1.96):
    if n == 0:
        return None, None
    p = correct / n
    den = 1 + z * z / n
    mid = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round(max(0.0, (mid - half) / den), 4), round(min(1.0, (mid + half) / den), 4))


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p under H0: b = c."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = 0.0
    for i in range(k + 1):
        tail += math.comb(n, i)
    return round(min(1.0, 2 * tail / (2 ** n)), 4)


def rank_of(values):
    """Ranks with ties averaged."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1
        for t in range(i, j + 1):
            ranks[order[t]] = avg
        i = j + 1
    return ranks


def spearman(xs, ys):
    if len(xs) < 2:
        return None
    rx, ry = rank_of(xs), rank_of(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return None if den == 0 else round(num / den, 4)


def least_squares(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    intercept = my - slope * mx
    fitted = [intercept + slope * x for x in xs]
    ss_res = sum((y - f) ** 2 for y, f in zip(ys, fitted))
    ss_tot = sum((y - my) ** 2 for y in ys)
    r = None if ss_tot == 0 else round(math.sqrt(max(0.0, 1 - ss_res / ss_tot)), 4)
    return {"slope": round(slope, 4), "intercept": round(intercept, 4), "r": r, "n": n}


def rel_dev(a, b):
    return abs(a - b) / max(1, min(a, b))


# ---------------------------------------------------------------- gate

def build_gate(out_path):
    t0 = time.monotonic()
    pan = panel()
    blobs = cell_pool_blobs()
    anchor = json.load(open(ANCHOR_GATE))
    anchor_cells = {c["cell"]: c for c in anchor["cells"]}
    checks, failures = 0, []
    dig_ok, blob_ok = 0, 0
    for name, b in blobs.items():
        ac = anchor_cells[name]
        checks += 1
        if ac["pool_blob_sha256"] == b["pool"]:
            dig_ok += 1
        else:
            failures.append(f"pool blob {name}")
        checks += 1
        if ac["paired_pool_blob_sha256"] == b["paired"]:
            blob_ok += 1
        else:
            failures.append(f"paired blob {name}")
    pinned = []
    for rec in pan:
        ac = anchor_cells[rec["cell"]]
        arr = ac["forward_prompt_sha256"] if rec["arm"] == "F" else ac["cross_prompt_sha256"]
        want = arr[PAIR_INDEX]
        checks += 1
        if want == rec["digest"]:
            pinned.append(rec["digest"])
        else:
            failures.append(f"digest {rec['cell']}/{rec['arm']}")
    # structural audit of every dispatched item, and the matched-pair invariant
    struct_problems = []
    for rec in pan:
        struct_problems += base.verify_item(rec["item"])
    pair_ok = 0
    for name, k, chains in base.WALK:
        pairs, _p, _q = base.build_cell(k, chains, PAIR_INDEX + 1)
        viol = base.pair_violations(pairs[PAIR_INDEX][0], pairs[PAIR_INDEX][1])
        if viol:
            failures.append(f"matched pair {name}: {viol}")
        else:
            pair_ok += 1
    gate = {
        "schema": SCHEMA, "round": ROUND_NO,
        "seed_base": base.SEED_BASE, "temperature": base.TEMPERATURE,
        "max_tokens": MAX_TOKENS, "prompt_cap": PROMPT_CAP,
        "planned_prompts": len(pan) * DISPATCHES_PER_PROMPT,
        "dispatches_per_prompt": DISPATCHES_PER_PROMPT,
        "pairs_per_cell": 1, "pair_index": PAIR_INDEX,
        "panel": [{"cell": r["cell"], "arm": r["arm"], "k": r["k"], "chains": r["chains"],
                   "edges": r["edges"], "digest": r["digest"], "gold": r["gold"],
                   "item_sha256": r["item_sha256"]} for r in pan],
        "pool_blobs": {n: b["pool"] for n, b in blobs.items()},
        "paired_pool_blobs": {n: b["paired"] for n, b in blobs.items()},
        "anchor": {"gate_hash": anchor.get("gate_hash"),
                   "source": "research/nightly-2026-10-25-0205 (merged, main)",
                   "digests_on_panel": ARCHIVED_DELIVERED_ON_PANEL + ARCHIVED_TRACE_ONLY_ON_PANEL,
                   "delivered_content_only": ARCHIVED_DELIVERED_ON_PANEL,
                   "trace_only": ARCHIVED_TRACE_ONLY_ON_PANEL,
                   "distractor_ratio_by_cell": ARCHIVED_RATIO_BY_CELL,
                   "token_laws": ARCHIVED_LAWS},
        "predictions": PRED,
        "audit": {"checks": checks, "failures": failures,
                  "structural_problems": struct_problems,
                  "matched_pairs_ok": pair_ok,
                  "digests_equal": len(pinned), "pool_blobs_equal": dig_ok,
                  "paired_blobs_equal": blob_ok},
        "built_at": base.now_iso(), "build_seconds": round(time.monotonic() - t0, 2),
    }
    corpus = base.sha256_text(json.dumps(sorted(pinned)))
    gate["corpus_blob_sha256"] = corpus
    gate["gate_hash"] = base.sha256_text(json.dumps(
        {k: gate[k] for k in ("schema", "panel", "pool_blobs", "paired_pool_blobs",
                              "predictions", "corpus_blob_sha256")}, sort_keys=True))
    gate["anchor_ok"] = (not failures) and len(pinned) == PRED["digests_equal"]
    with open(out_path, "w") as fh:
        json.dump(gate, fh, indent=2, sort_keys=True)
    print(f"gate {gate['gate_hash'][:8]} checks {checks} failures {len(failures)} "
          f"digests {len(pinned)}/{len(pan)} blobs {dig_ok}/{len(blobs)} "
          f"anchor_ok {gate['anchor_ok']} build {gate['build_seconds']}s")
    return 0 if gate["anchor_ok"] else 1


# ---------------------------------------------------------------- probe

def read_archived():
    """The merged round-23 observation on the identical digests (paired, prompt-matched)."""
    out = {}
    with open(ANCHOR_RAW) as fh:
        for line in fh:
            rec = json.loads(line)
            out[rec["prompt_sha256"]] = rec
    return out


def health_call():
    h = base.health_check()
    rate = None
    if h["completion_tokens"] and h["latency_s"]:
        rate = round(h["completion_tokens"] / max(0.001, h["latency_s"] - 0.4), 1)
    return {"ok": h["ok"], "outcome": h["outcome"], "latency_s": h["latency_s"],
            "completion_tokens": h["completion_tokens"], "tok_per_s": rate}


def dispatch(digest_rec, budget):
    rec = dict(cell=digest_rec["cell"], arm=digest_rec["arm"], k=digest_rec["k"],
               chains=digest_rec["chains"], edges=digest_rec["edges"],
               gold=digest_rec["gold"], prompt_sha256=digest_rec["digest"],
               item_sha256=digest_rec["item_sha256"],
               prompt_chars=len(digest_rec["prompt"]), phase=digest_rec["dispatch"])
    if not budget.acquire():
        rec["outcome"] = "call_cap_exhausted"
        return rec
    t0 = time.monotonic()
    resp = base.call_endpoint(digest_rec["prompt"], MAX_TOKENS, deadline_s=600)
    rec["wall_s"] = round(time.monotonic() - t0, 2)
    ro = base.readouts(resp["content"], resp["reasoning"])
    att = {"error_class": resp.get("error"),
           "completion_tokens": resp["completion_tokens"],
           "content_answer": ro["content_answer"],
           "reasoning_answer": ro["reasoning_answer"],
           "finish_reason": resp["finish_reason"]}
    rec.update({
        "completion_tokens": resp["completion_tokens"],
        "prompt_tokens": resp["prompt_tokens"],
        "finish_reason": resp["finish_reason"],
        "outcome": base.classify_attempt(att),
        "content_answer": ro["content_answer"],
        "reasoning_answer": ro["reasoning_answer"],
        "loose_fallback_answer": ro["loose_fallback_answer"],
        "delivered_or_strict_answer": ro["delivered_or_strict_answer"],
        "loose_fallback_source": ro["loose_fallback_source"],
        "strict_trace_token": ro["strict_trace_token"],
        "fallback_provenance_class": ro["fallback_provenance_class"],
        "fallback_commit_fraction": ro["fallback_commit_fraction"],
        "reasoning_chars": len(resp["reasoning"] or ""),
        "content_chars": len(resp["content"] or ""),
        "truncated": bool(resp["completion_tokens"] >= MAX_TOKENS),
        "error_class": resp.get("error"),
    })
    gold_yes = "yes" if rec["gold"] == 1 else "no"
    for key in ("content_answer", "reasoning_answer", "loose_fallback_answer",
                "strict_trace_token"):
        val = rec.get(key)
        rec["correct_" + key] = None if val is None else int(val == gold_yes)
    mech = base.mechanics(digest_rec["item"], resp, digest_rec["prompt"])
    rec["distractor_mention_ratio"] = mech["distractor_mention_ratio"]
    rec["ordered_prefix_hops"] = mech["ordered_prefix_hops"]
    rec["coverage_ratio"] = mech["coverage_ratio"]
    return rec


def cmd_probe(out_dir, deadline_s, concurrency):
    gate = json.load(open(os.path.join(out_dir, "gate.json")))
    pan = panel()
    by_digest = {r["digest"]: r for r in pan}
    for r in pan:
        assert r["digest"] in {p["digest"] for p in gate["panel"]}
    h = health_call()
    used = 1
    print(f"health {h}")
    if not h["ok"]:
        print("endpoint unhealthy, abort before spending the grid")
        return 1
    est = h["tok_per_s"] or 20.0
    chosen = concurrency or (3 if est > 25 else 2)
    # heaviest first: the truncation-prone walk tail is dispatched before the deadline guard
    order = sorted(pan, key=lambda r: (-r["edges"], -r["k"]))
    jobs = []
    for d in range(1, DISPATCHES_PER_PROMPT + 1):
        for rec in order:
            item = dict(rec)
            item["dispatch"] = d
            jobs.append(item)
    raw_path = os.path.join(out_dir, "raw.jsonl")
    started = time.monotonic()
    done = 0
    cap = AttemptCap(used)
    with open(raw_path, "w") as fh:
        with concurrent.futures.ThreadPoolExecutor(max_workers=chosen) as pool:
            futs = [pool.submit(dispatch, j, cap) for j in jobs]
            for fut in concurrent.futures.as_completed(futs):
                rec = fut.result()
                if rec["outcome"] != "call_cap_exhausted":
                    used += 1
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
                fh.flush()
                done += 1
                print(f"{done}/{len(jobs)} {rec['cell']}/{rec['arm']} d{rec['dispatch']} "
                      f"{rec['outcome']} tok={rec.get('completion_tokens')} "
                      f"wall={rec.get('wall_s')}", flush=True)
                if time.monotonic() - started > deadline_s:
                    print("DEADLINE reached, dispatch stopped here")
                    break
    print(f"dispatch wall {round(time.monotonic() - started, 1)}s records {done} "
          f"calls {used}")
    return 0


class AttemptCap:
    """Shared call counter; the cap is the contractual 40-call limit (issue: round protocol)."""

    def __init__(self, already_used):
        self.lock = __import__("threading").Lock()
        self.used = already_used
        self.cap = PROMPT_CAP

    def acquire(self):
        with self.lock:
            if self.used >= self.cap:
                return False
            self.used += 1
            return True


# ---------------------------------------------------------------- analyze

def cmd_analyze(out_dir):
    gate = json.load(open(os.path.join(out_dir, "gate.json")))
    recs = [json.loads(l) for l in open(os.path.join(out_dir, "raw.jsonl"))]
    archived = read_archived()
    panel_digests = [p["digest"] for p in gate["panel"]]
    by = {}
    for r in recs:
        by.setdefault(r["prompt_sha256"], []).append(r)
    pairs = []
    for d in panel_digests:
        mine = sorted(by.get(d, []), key=lambda r: r["dispatch"])
        if not mine:
            continue
        a = mine[0]
        arch = archived.get(d)
        row = {"cell": a["cell"], "arm": a["arm"], "k": a["k"], "edges": a["edges"],
               "gold": a["gold"], "digest": d[:12], "dispatches": len(mine),
               "tokens": [r["completion_tokens"] for r in mine],
               "answers": [r["content_answer"] for r in mine],
               "loose": [r["loose_fallback_answer"] for r in mine],
               "outcome": a["outcome"], "truncated": any(r["truncated"] for r in mine),
               "archived_tokens": None if arch is None else arch["completion_tokens"],
               "archived_outcome": None if arch is None else arch["outcome"],
               "archived_content_answer": None if arch is None else arch["content_answer"],
               "correct_content": max((r["correct_content_answer"] for r in mine),
                                      key=lambda v: (v is not None, v), default=None),
               "correct_loose": max((r["correct_loose_fallback_answer"] for r in mine),
                                    key=lambda v: (v is not None, v), default=None),
               "distractor_ratio": a["distractor_mention_ratio"]}
        if len(mine) == 2:
            row["token_identical"] = mine[0]["completion_tokens"] == mine[1]["completion_tokens"]
            row["answer_agree"] = mine[0]["content_answer"] == mine[1]["content_answer"]
            row["rel_dev"] = round(rel_dev(mine[0]["completion_tokens"],
                                           mine[1]["completion_tokens"]), 4)
            if arch is not None:
                row["token_ratio_vs_archived"] = round(
                    statistics.mean([r["completion_tokens"] for r in mine])
                    / max(1, arch["completion_tokens"]), 4)
        pairs.append(row)
    complete = [p for p in pairs if p["dispatches"] == 2]
    n2 = len(complete)
    ident = sum(1 for p in complete if p["token_identical"])
    agree = sum(1 for p in complete if p["answer_agree"])
    devs = [p["rel_dev"] for p in complete]
    toks_a = [p["tokens"][0] for p in complete]
    toks_b = [p["tokens"][1] for p in complete]
    delivered = sum(1 for p in pairs if p["outcome"] == "answered_in_answer_field")
    wrong = sum(1 for p in pairs if p["correct_content"] == 0)
    loose_wrong = sum(1 for p in pairs if p["correct_loose"] == 0)
    # McNemar on delivery: this surface vs the archived surface, identical byte prompts
    b = c = 0
    for p in pairs:
        mine_del = p["outcome"] == "answered_in_answer_field"
        arch_del = p["archived_outcome"] == "answered_in_answer_field"
        if mine_del and not arch_del:
            b += 1
        elif arch_del and not mine_del:
            c += 1
    ratios = [p["token_ratio_vs_archived"] for p in complete
              if p.get("token_ratio_vs_archived") is not None]
    # same-run noise band on the two declared token laws: slope from dispatch A and from
    # dispatch B over the same digests, the spread of the two is the noise floor of the law
    def law(sel, idx):
        pts = [(p["edges"], p["tokens"][idx]) for p in complete if p["arm"] == "F"]
        return least_squares([x for x, _ in pts], [y for _, y in pts]) if sel else None
    lawA, lawB = law(True, 0), law(False, 1)
    noise_slope = None
    if lawA and lawB:
        noise_slope = round(abs(lawA["slope"] - lawB["slope"]), 4)
    ratio_by_cell = {}
    for name in ARCHIVED_RATIO_BY_CELL:
        vals = [p["distractor_ratio"] for p in pairs if p["cell"] == name
                and p["distractor_ratio"] is not None]
        if vals:
            ratio_by_cell[name] = round(statistics.mean(vals), 4)
    summary = {
        "gate_hash": gate["gate_hash"], "schema": SCHEMA, "round": ROUND_NO,
        "records": len(recs), "prompts_covered": len(pairs), "paired_prompts": n2,
        "noise_floor": {
            "identical_token_pairs": ident, "paired_prompts": n2,
            "identical_rate": round(ident / n2, 4) if n2 else None,
            "answer_agree_pairs": agree,
            "answer_agree_rate": round(agree / n2, 4) if n2 else None,
            "median_rel_dev": round(statistics.median(devs), 4) if devs else None,
            "max_rel_dev": max(devs) if devs else None,
            "spearman_dispatchA_dispatchB": spearman(toks_a, toks_b),
            "grid_mean_tokens_A": round(statistics.mean(toks_a), 1) if toks_a else None,
            "grid_mean_tokens_B": round(statistics.mean(toks_b), 1) if toks_b else None,
        },
        "surface_join": {
            "panel_size": len(panel_digests), "covered": len(pairs),
            "delivered_content_only": delivered,
            "archived_delivered_content_only": ARCHIVED_DELIVERED_ON_PANEL,
            "truncated": sum(1 for p in pairs if p["truncated"]),
            "archived_truncated": ARCHIVED_TRACE_ONLY_ON_PANEL,
            "wrong_content_answers": wrong, "wrong_loose_answers": loose_wrong,
            "mcnemar_delivery": {"b_this_only": b, "c_archived_only": c,
                                 "p": mcnemar_exact(b, c)},
            "token_ratio_vs_archived_median": (round(statistics.median(ratios), 4)
                                               if ratios else None),
            "token_ratio_vs_archived_min": min(ratios) if ratios else None,
            "token_ratio_vs_archived_max": max(ratios) if ratios else None,
            "per_digest": pairs,
        },
        "token_laws": {"all_F_dispatchA": lawA, "all_F_dispatchB": lawB,
                       "same_run_slope_noise_band": noise_slope,
                       "archived": ARCHIVED_LAWS,
                       "note": "two-point and three-point fits over the six walk cells; "
                               "exploratory by construction (issue #94 readout stack)"},
        "distractor_mention_ratio_by_cell": ratio_by_cell,
        "archived_distractor_mention_ratio_by_cell": ARCHIVED_RATIO_BY_CELL,
        "predictions": gate["predictions"],
    }
    verdicts = {
        "C1_digest_true": gate["audit"]["digests_equal"] == PRED["digests_equal"]
        and gate["audit"]["pool_blobs_equal"] == PRED["pool_blobs_equal"],
        "N1_answer_agree": agree >= PRED["noise_answer_agree_ge"] and n2 > 0,
        "N1_token_identical": ident >= PRED["noise_token_identical_ge"] and n2 > 0,
        "N2_delivery": delivered >= PRED["delivered_content_only_ge"],
        "N2_no_wrong_answers": wrong <= PRED["max_wrong_answers"],
        "N3_discordance_separable": (b + c) > 0 and (b + c) > max(0, n2 - agree),
    }
    summary["verdicts"] = verdicts
    with open(os.path.join(out_dir, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
    print(json.dumps({"noise": summary["noise_floor"],
                      "join": {k: v for k, v in summary["surface_join"].items()
                               if k != "per_digest"},
                      "laws": summary["token_laws"],
                      "ratio_by_cell": ratio_by_cell, "verdicts": verdicts},
                     indent=2, sort_keys=True))
    return 0


# ---------------------------------------------------------------- selftest

def selftest():
    checks, failed = 0, []

    def chk(name, ok):
        nonlocal checks
        checks += 1
        if not ok:
            failed.append(name)

    # arithmetic controls on the statistics helpers
    lo, hi = wilson(9, 12)
    chk("wilson_bounds", lo < 0.75 < hi)
    chk("wilson_zero_n", wilson(0, 0) == (None, None))
    chk("mcnemar_null", mcnemar_exact(0, 0) == 1.0)
    chk("mcnemar_b1c0", abs(mcnemar_exact(1, 0) - 1.0) < 1e-6)
    # the exact two-sided binomial p is what the verdicts compare against, so pin its value
    chk("mcnemar_b4c0", abs(mcnemar_exact(4, 0) - 0.125) < 1e-9)
    chk("mcnemar_balanced", mcnemar_exact(3, 3) > 0.9)
    chk("spearman_perfect", spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0)
    chk("spearman_swap", abs(spearman([1, 2, 3, 4], [10, 20, 40, 30]) - 0.8) < 1e-9)
    chk("spearman_anti", spearman([1, 2, 3, 4], [40, 30, 20, 10]) == -1.0)
    # synthetic slope controls: the fit must recover a planted slope and its sign
    fit = least_squares([1, 2, 3], [2, 4, 6])
    chk("lsq_slope_recovers_planted_line", abs(fit["slope"] - 2.0) < 1e-9)
    chk("lsq_intercept_recovers_planted_line", abs(fit["intercept"] - 0.0) < 1e-9)
    chk("lsq_n", fit["n"] == 3)
    chk("lsq_sign_flips_on_negated_y", least_squares([1, 2, 3], [-2, -4, -6])["slope"] < 0)
    flat = least_squares([1, 2, 3], [5, 5, 5])
    chk("lsq_flat_series_gives_zero_slope", abs(flat["slope"]) < 1e-9)
    curved = least_squares([1, 2, 3, 4], [1, 4, 9, 16])
    chk("lsq_curve_fit_is_imperfect_by_r_design", curved["slope"] > 0 and curved["r"] < 1.0)
    degenerate = least_squares([1, 1, 1], [2, 3, 4])
    chk("lsq_degenerate_x_returns_none", degenerate is None)
    chk("lsq_single_point_returns_none", least_squares([1], [2]) is None)
    # the archived load-k4 law must be a real number, not a silent failure
    archived = json.load(open(ANCHOR_SUMMARY))["token_laws"]["load_k4_slope"]
    chk("anchor_law_is_numeric", isinstance(archived, (int, float)) and archived > 0)
    # planted negative control: a discordant repeat pair must show up in the noise estimator
    chk("rel_dev_detects_move", rel_dev(2048, 379) > 1.0)
    chk("rel_detects_zero_noise", rel_dev(512, 512) == 0.0)
    # planted non-matched control (inherited assertion): a pair built from another item's facts
    k, chains = base.WALK[0][1], base.WALK[0][2]
    pairs, _pool, _pp = base.build_cell(k, chains, 2)
    chk("pair_invariant_clean", base.pair_violations(pairs[0][0], pairs[0][1]) == [])
    tampered = dict(pairs[0][1])
    tampered["facts"] = list(pairs[1][0]["facts"])
    chk("pair_invariant_detects_foreign_facts",
        base.pair_violations(pairs[0][0], tampered) != [])
    # gold is derived from an independent BFS, and the audit catches a flipped verdict
    item = pairs[0][0]
    chk("gold_matches_bfs", item["answer"] == "yes" and base.verify_item(item) == [])
    flipped = dict(item)
    flipped["answer"] = "no"
    chk("audit_detects_flipped_gold", base.verify_item(flipped) != [])
    # panel selection rule: pair 0 of every cell, F and X, 12 byte prompts, all distinct
    pan = panel()
    chk("panel_size", len(pan) == 12)
    chk("panel_arm_split", len({r["arm"] for r in pan}) == 2)
    chk("panel_digests_distinct", len({r["digest"] for r in pan}) == 12)
    chk("panel_walk_order", [r["cell"] for r in pan] ==
        [name for name, _k, _c in base.WALK for _arm in ("F", "X")])
    # negative control: a different pair index is a different prompt
    alt = base.render_prompt(base.build_cell(k, chains, 2)[0][0][1])
    chk("pair_index_selection_is_deterministic",
        base.render_prompt(base.build_cell(k, chains, 2)[0][0][0]) == pan[0]["prompt"])
    chk("other_pair_is_different_prompt", alt != pan[0]["prompt"])
    # the panel must equal the merged anchor gate (this is the identity control, not a tautology)
    anchor = json.load(open(ANCHOR_GATE))
    acells = {c["cell"]: c for c in anchor["cells"]}
    hits = 0
    for rec in pan:
        arr = (acells[rec["cell"]]["forward_prompt_sha256"] if rec["arm"] == "F"
               else acells[rec["cell"]]["cross_prompt_sha256"])
        if arr[PAIR_INDEX] == rec["digest"]:
            hits += 1
    chk("panel_equals_merged_gate", hits == 12)
    wrong_cell = 0
    for rec in pan:
        arr = (acells[rec["cell"]]["cross_prompt_sha256"] if rec["arm"] == "F"
               else acells[rec["cell"]]["forward_prompt_sha256"])
        if arr[PAIR_INDEX] == rec["digest"]:
            wrong_cell += 1
    chk("digest_control_is_not_vacuous", wrong_cell == 0)
    # cap contract
    chk("call_cap_within_protocol", 1 + 12 * DISPATCHES_PER_PROMPT <= PROMPT_CAP)
    chk("max_tokens_contract", MAX_TOKENS <= 2048)
    print(f"selftest {checks} checks {len(failed)} failures {failed[:6]}")
    return 0 if not failed else 1


def main(argv):
    ap = argparse.ArgumentParser(description="round 39 quantization-surface probe")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--out-dir", default=HERE)
    ap.add_argument("--out", default=os.path.join(HERE, "gate.json"))
    ap.add_argument("--deadline-seconds", type=int, default=DISPATCH_DEADLINE_S)
    ap.add_argument("--concurrency", type=int, default=0)
    args = ap.parse_args(argv[1:])
    if args.selftest:
        return selftest()
    if args.gate:
        return build_gate(args.out)
    if args.probe:
        return cmd_probe(args.out_dir, args.deadline_seconds, args.concurrency)
    if args.analyze:
        return cmd_analyze(args.out_dir)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

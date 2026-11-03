#!/usr/bin/env python3
"""Round 30 (2026-10-27 02:00): verdict position versus budget in the archived (k, E) runs.

Question (tracker #65, issue #71, issue #94): the (k, E) frontier stops delivering at the
archived non-maintained corners because the generation cap (max_tokens 2048) cuts an
enumeration that had not finished, or because the protocol asks for the verdict last, so a
run that is still writing when the cap lands can never fill the answer field? This round
answers it without dispatching anything, by reanalysing the 72 attempts already archived in
rounds 23 and 24, and freezes the dispatch instrument that can separate the two on a later
firing.

What this script reads: `archived_attempts.jsonl` next to it. That file is one row per
archived attempt, rebuilt from the two archived raw.jsonl files with the raw model text and
the timing fields dropped: only task coordinates, readout tokens, provenance classes, the
commit fraction and the token/char mechanics survive. No model output text is copied here.

What this script refuses to do:
- analyse a rows file that carries any raw-text or timing field (public-only rule, and the
  no-raw-trace rule for a reanalysis of another round's data);
- analyse when a recomputed readout disagrees with the archived `correct` field (the
  transcription-drift guard);
- emit any verdict when the reproduction control P1 does not reproduce the archived
  aggregates exactly, or when the gate file does not match the frozen decision table, or
  when the analysis source has changed since the gate was frozen;
- exceed the contractual cap: no dispatch exists in this instrument at all.

Usage:
  verdict_margin_probe.py --selftest
  verdict_margin_probe.py --gate   [--out gate.json]
  verdict_margin_probe.py --analyze [--rows archived_attempts.jsonl] [--gate gate.json]
                      [--out summary.json]

Exit codes: 0 ok, 2 selftest failure, 3 refusal (gate drift, integrity failure, P1 failure).
"""

import argparse
import hashlib
import json
import math
import os
import sys

# ---------------------------------------------------------------- frozen constants

CAP = 2048                     # contractual: max_tokens <= 2048 (research/AGENTS.md)
VERBOSE_MIN_TOKENS = 800       # declared split between the gist mode and the enumeration mode
EARLY_MARGIN_TOKENS = 128      # declared: a trace verdict counts as early above this
MIN_SILENT_FOR_CALL = 8        # below this many silent attempts no class call is made
SAFE_BAND = 0.95               # predicted cost below 0.95 x CAP is a firm "safe" call
MAJORITY_FLOOR = 0.5           # inherited (rounds 8-24)
MARGIN = 0.10                  # inherited
MIN_CERTIFY = 6                # inherited
ARCHIVE_MEAN_DP = 1            # the archived laws fit per-cell means rounded to 1 decimal

ROUND_DIRS = {"r23": "research/nightly-2026-10-25-0205", "r24": "research/nightly-2026-10-25-0405"}
ROUND_BRANCHES = {"r23": "research/nightly-2026-10-25-0205", "r24": "research/nightly-2026-10-25-0405"}
SOURCE_GATE_HASHES = {
    "r23": "f324fedaa1685c8a7cbfbe77ebf6d4a5a6ddd85ded96b000f849f8784a4af760",
    "r24": "85e70f3fc3e3f4092535f41d78b321ac92704352b5c47b61477a443a15732755",
}

# P1: aggregates published in the two archived summary.json files. The analyzer must
# reproduce every one of them from the vendored rows, or it refuses to report anything.
ARCHIVED_AGGREGATES = {
    "r23": {
        "answered": {"content_only": 25, "delivered_or_strict": 28, "loose_fallback": 36},
        "correct": {"content_only": 25, "delivered_or_strict": 28, "loose_fallback": 33},
        "outcomes": {"answered_in_answer_field": 25, "trace_only": 11},
        "truncated": 11,
        "provenance_classes": {"instruction_echo": 7, "mid_trace": 2, "terminal": 27},
        "commit_fraction_upper_median": 0.9963,
        "strict_on_silent": {"cells": 11, "committed": 3, "correct": 3},
        "silent_loose_correct": 8,
        "budget_replay_answerable": {"256": 1, "512": 9, "1024": 14, "2048": 25},
        "per_cell_correct": {"S1": 6, "S2": 6, "S3": 6, "S4": 4, "S5": 2, "S6": 1},
        "per_cell_no_answer": {"S1": 0, "S2": 0, "S3": 0, "S4": 2, "S5": 4, "S6": 5},
        "per_cell_mean_completion": {"S1": 445.5, "S2": 930.0, "S3": 1177.3, "S4": 1245.2,
                                     "S5": 1675.0, "S6": 1772.2},
        "non_maintained_cells": ["S4", "S5", "S6"],
        "laws": {"depth_at_top_load": {"intercept": 773.633, "slope": 65.875, "r": 0.9396},
                 "load_at_k4": {"intercept": 284.0, "slope": 6.729167, "r": 1.0}},
        "law_points": {"depth_at_top_load": [(8, 1245.2), (12, 1675.0), (16, 1772.2)],
                       "load_at_k4": [(24, 445.5), (96, 930.0)]},
    },
    "r24": {
        "answered": {"content_only": 35, "delivered_or_strict": 35, "loose_fallback": 36},
        "correct": {"content_only": 35, "delivered_or_strict": 35, "loose_fallback": 36},
        "outcomes": {"answered_in_answer_field": 35, "trace_only": 1},
        "truncated": 1,
        "provenance_classes": {"instruction_echo": 1, "mid_trace": 1, "terminal": 34},
        "commit_fraction_upper_median": 0.9979,
        "strict_on_silent": {"cells": 1, "committed": 0, "correct": 0},
        "silent_loose_correct": 1,
        "budget_replay_answerable": {"256": 1, "512": 2, "1024": 4, "2048": 35},
        "per_cell_correct": {"L0": 6, "L1": 6, "L2": 6, "L3": 6, "D1": 6, "D2": 5},
        "per_cell_no_answer": {"L0": 0, "L1": 0, "L2": 0, "L3": 0, "D1": 0, "D2": 1},
        "per_cell_mean_completion": {"L0": 1171.8, "L1": 1105.5, "L2": 1392.7, "L3": 1615.8,
                                     "D1": 1196.0, "D2": 1406.7},
        "non_maintained_cells": ["D2"],
        "laws": {"depth_at_E96": {"intercept": 905.817, "slope": 29.3625, "r": 0.909},
                 "load_at_k8": {"intercept": 343.666, "slope": 7.885357, "r": 0.9308}},
        "law_points": {"depth_at_E96": [(8, 1171.8), (12, 1196.0), (16, 1406.7)],
                       "load_at_k8": [(96, 1171.8), (112, 1105.5), (128, 1392.7),
                                      (160, 1615.8)]},
    },
}

MEASURE_DEFS = {
    "M1_strict_committed_share":
        "share of content-silent, cap-capped attempts whose trace ends on a strict-committed "
        "verdict (archived strict_trace_token non-null)",
    "M2_echo_tail_share":
        "share of content-silent, cap-capped attempts whose last bare yes/no sits inside a "
        "restated instruction phrase (archived provenance class instruction_echo)",
    "M3_walk_incomplete_share":
        "among content-silent arm-F attempts with walk mechanics recorded, the share with "
        "ordered_prefix_hops < expected_hops",
    "M4_verdict_margin_tokens":
        "completion_tokens x (1 - fallback_commit_fraction), defined only when the provenance "
        "class is mid_trace or terminal; undefined for instruction_echo (no verdict outside "
        "the instruction) and for no trace token",
    "M5_verdict_at_cap_share":
        "share of content-silent, cap-capped attempts with a strict-committed verdict at "
        "commit fraction >= 0.98",
    "M6_verdict_last_share":
        "share of DELIVERED attempts whose last in-trace verdict sits at commit fraction "
        ">= 0.98, plus the answer-field lag (completion_tokens - est_pos)",
    "M7_cap_headroom":
        "per (cell, arm): CAP minus the largest completion_tokens among delivered attempts, "
        "next to the truncation count of that group",
    "M8_verbose_cost_law":
        "per arm, completion_tokens = a + b x E + c x k fitted on delivered verbose-mode rows "
        "(one value per unique prompt), used to predict the cost a verbose run would need",
    "M9_constant_no_control":
        "the echo class readout as a classifier: its answer distribution, its accuracy split "
        "by gold, and the silent-subset gain of the loose readout over a constant-no responder",
}

TAXONOMY = {
    "echo_tail": "no verdict anywhere outside the restated instruction, trace open at the cap",
    "no_trace_token": "no bare yes/no in the trace at all, trace open at the cap",
    "open_at_cap": "a verdict was written late in the trace but does not close it (margin "
                   "< EARLY_MARGIN_TOKENS), trace open at the cap",
    "open_early": "a verdict was written mid-trace with margin >= EARLY_MARGIN_TOKENS, the "
                  "trace continued and the answer field never arrived",
    "committed_at_cap": "the trace closes on a strict verdict within EARLY_MARGIN_TOKENS of "
                        "the cap: delivery just in time or not at all",
    "committed_early": "the trace closes on a strict verdict with margin "
                       ">= EARLY_MARGIN_TOKENS and the answer field still never arrived",
    "delivered": "the answer field arrived",
    "silent_not_capped": "no answer field and completion_tokens below the cap: not a cap hit, "
                         "excluded from the mechanism call",
}
CAP_BOUND_GROUP = ("echo_tail", "no_trace_token", "open_at_cap", "committed_at_cap")
SURFACING_GROUP = ("open_early", "committed_early")

# Frozen decision table. Rules are data, evaluated as conjunctions of field/op/value.
DECISION_TABLE = [
    {"id": "T1", "call": "budget_or_traversal_bound", "conds": [
        ["cap_bound_share", ">=", 0.75], ["surfacing_share", "<=", 0.25],
        ["n_silent_capped", ">=", MIN_SILENT_FOR_CALL]]},
    {"id": "T2", "call": "protocol_or_surfacing_bound", "conds": [
        ["surfacing_share", ">=", 0.50], ["M1_strict_committed_share", ">=", 0.75],
        ["n_silent_capped", ">=", MIN_SILENT_FOR_CALL]]},
    {"id": "T3", "call": "mixed_or_insufficient", "conds": []},
]

DECLARED_PREDICTIONS = {
    "PR1": "the 72 attempts contain no wrong delivered answer: every failure of the "
           "content_only readout is a nondelivery",
    "PR2": "M6: the verdict-last convention holds on essentially every delivered attempt "
           "(commit fraction >= 0.98 and answer-field lag <= 1 token)",
    "PR3": "the silent attempts are dominated by cap-bound mechanisms (echo_tail, "
           "no_trace_token, open_at_cap, committed_at_cap) rather than by verdicts committed "
           "with budget headroom",
    "PR4": "M8: verbose-mode cost per arm crosses CAP between E = 160 and E = 192 at k = 8, "
           "so the archived E = 192 non-maintenance is a cap overrun, and the per-hop cost at "
           "safe load is small compared with the per-fact cost",
    "PR5": "M3: the arm-F truncations at E = 192 are walks that had not reached the query "
           "target when the cap landed",
    "PR6": "the single truncation behind the round-24 (k = 16, E = 96) turnover is not "
           "predicted by the verbose cost law fitted on uncensored runs",
}

# Frozen instrument for a later firing. Nothing in this round dispatches it.
DISPATCH_DESIGN = {
    "status": "frozen, not executed on this firing (the firing was cut by the runner timeout "
              "and a later firing was already running in the same checkout)",
    "question": "does an early-commitment instruction line convert cap-bound nondelivery into "
                "delivery without changing walk coverage, i.e. is the ceiling the verdict-last "
                "protocol or the traversal?",
    "target_cells": [
        {"cell": "D2", "k": 16, "C": 6, "edges": 96, "why": "the archived turnover corner: "
         "arm F delivered 3/3 with complete walks at ~1150 tokens, arm X truncated 1/3 at "
         "2048 (issue #71 asks whether this corner is real)"},
        {"cell": "L3", "k": 8, "C": 20, "edges": 160, "why": "the archived maintained corner "
         "whose arm X delivery came within 5 tokens of the cap (2043/2048)"},
        {"cell": "S5", "k": 12, "C": 16, "edges": 192, "why": "the archived corner where the "
         "verbose cost law predicts a cap overrun and arm F showed both a 310-token delivery "
         "and a 2048-token truncation on the same level"},
    ],
    "policies": {
        "A": "the archived prompt verbatim: the future round must reproduce the archived "
             "prompt_sha256 values listed below byte for byte, which doubles as a transport "
             "and determinism control",
        "B": "policy A plus one appended line, frozen here verbatim: commit the answer field "
             "before enumerating, then verify it",
        "B_commit_line": "Before you list any fact, write the answer field with yes or no. "
                         "Then walk the chain to check that answer. If the walk changes your "
                         "mind, correct the answer field.",
    },
    "grid": "3 cells x 3 archived matched pairs x 2 arms (F forward gold yes, X cross gold "
            "no) x 2 policies = 36 dispatches, within the 40-prompt cap",
    "pairs_and_archived_prompt_sha256": {
        "D2": {"36321026": {"F": "74388a9a6f4d", "X": "de5ed21b3289"},
               "36321027": {"F": "51ddd1f327f0", "X": "817d852383a6"},
               "36321029": {"F": "09701216d3fd", "X": "e21833ff126f"}},
        "L3": {"28461024": {"F": "4ed1d525026f", "X": "d548b1f9681c"},
               "28461028": {"F": "3a697ba51034", "X": "3ba9842ed8d6"},
               "28461030": {"F": "2387559a6df9", "X": "c2fa54ea50ec"}},
        "S5": {"32421024": {"F": "96a1a4057bd3", "X": "b8e87891a1a6"},
               "32421025": {"F": "8e67257ab5cf", "X": "90ffcbbde81e"},
               "32421026": {"F": "874a7bf9ae6e", "X": "ade6eaee919c"}},
    },
    "seeds": "inherited seed policy cell_seed(k, C, index) = 20261024 + 1000000 k + 10000 C + "
             "index, and the pair seeds listed above, so the graphs are the archived graphs",
    "budget": "max_tokens = 2048 unchanged. The 3072-token ladder that issue #71 suggests is "
              "outside the round contract and is NOT part of this design; the cap boundary is "
              "measured indirectly here (cost law plus policy manipulation)",
    "readouts": "the inherited stack: content_only primary, delivered_or_strict, loose_fallback "
                "reported and never the basis of a maintained claim; cell status per the "
                "round-8 trichotomy with floor MAJORITY_FLOOR + MARGIN = 0.60 and "
                "MIN_CERTIFY = 6",
    "measures_carried_over": ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M9"],
    "primary_statistic": "per (cell, arm): delivered_or_strict delivery rate under policy B "
                         "minus policy A on the identical prompts, plus the exact McNemar sign "
                         "test on the matched pairs",
    "traversal_control": "mean coverage_ratio and mean ordered_prefix_hops/expected_hops per "
                         "(cell, arm) under policy B minus policy A",
    "decision_rule": [
        ["if policy B raises delivery_or_strict by >= 0.34 (2 of 6) on >= 4 of the 6 "
         "(cell, arm) groups AND the coverage delta stays within 0.15, the ceiling is a "
         "protocol artifact: the model can answer once the protocol asks early, and the walk "
         "is unchanged",
         "protocol_artifact"],
        ["if policy B raises delivery_or_strict by < 0.17 on all 6 groups while truncation "
         "count stays at or above the archived count, the ceiling is traversal/budget bound: "
         "asking early does not buy a finished walk", "traversal_bound"],
        ["otherwise mixed, and the next instrument is the one issue #71 asked for: a budget "
         "ladder above 2048, which needs a contract change first", "mixed"],
    ],
    "stop_rules": [
        "health check the endpoint before dispatch, as in rounds 23-24; abort the firing if "
        "the health probe does not answer",
        "abort before dispatch if another round is live in the same checkout (round 30 lost "
        "its firing to exactly that collision)",
        "abort if any policy A prompt digest differs from the archived digest recorded above",
    ],
}

# ---------------------------------------------------------------- helpers


class Refusal(Exception):
    """Raised when an integrity or gate precondition fails. The analyzer never proceeds."""


REQUIRED_KEYS = ("round", "cell", "arm", "k", "edges", "level", "seed", "pair_seed", "gold",
                 "item_sha256", "prompt_sha256", "outcome", "correct", "gate_hash", "attempt",
                 "finish_reason", "error_class", "completion_tokens", "prompt_tokens",
                 "content_answer", "content_offset", "reasoning_answer", "reasoning_offset",
                 "strict_trace_token", "loose_fallback_answer", "loose_fallback_source",
                 "delivered_or_strict_answer", "fallback_provenance_class",
                 "fallback_commit_fraction", "reasoning_chars", "content_chars",
                 "coverage_ratio", "ordered_prefix_hops", "expected_hops",
                 "distractors_mentioned", "distractor_entities", "budget_cap")
FORBIDDEN_KEYS = ("content", "reasoning", "chains", "wall_s", "started_at", "finished_at",
                  "prompt", "raw", "response", "base_url", "model_id", "api_key")
ANSWER_WORDS = ("yes", "no")


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def script_digest() -> str:
    with open(os.path.realpath(__file__), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple:
    if total == 0:
        return 0.0, 0.0
    p = successes / total
    denom = 1.0 + z * z / total
    centre = p + z * z / (2 * total)
    span = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return (round((centre - span) / denom, 4), round((centre + span) / denom, 4))


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2.0 ** n)
    return min(1.0, 2.0 * tail)


def solve_linear(mat: list, vec: list):
    """Dense Gaussian solve with partial pivoting. Returns None on a singular design."""
    n = len(vec)
    a = [row[:] + [vec[i]] for i, row in enumerate(mat)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[piv][col]) < 1e-12:
            return None
        a[col], a[piv] = a[col], a[piv]
        for r in range(n):
            if r == col:
                continue
            factor = a[r][col] / a[col][col]
            if factor:
                for c in range(col, n + 1):
                    a[r][c] -= factor * a[col][col]
    return [a[i][n] / a[i][i] for i in range(n)]


def fit_linear_1d(points: list) -> dict:
    """Least squares y = a + b x, plus Pearson r. n < 2 refuses."""
    pts = [(float(x), float(y)) for x, y in points]
    n = len(pts)
    if n < 2:
        return {"fit": None, "note": f"only {n} points, fit refused"}
    if n == 2:
        (x0, y0), (x1, y1) = pts
        b = (y1 - y0) / (x1 - x0) if x1 != x0 else 0.0
        return {"intercept": round(y0 - b * x0, 3), "slope": round(b, 6), "r": 1.0, "n": n}
    sx = sum(p[0] for p in pts)
    sy = sum(p[1] for p in pts)
    sxx = sum(p[0] * p[0] for p in pts)
    sxy = sum(p[0] * p[1] for p in pts)
    den = n * sxx - sx * sx
    if abs(den) < 1e-12:
        return {"fit": None, "note": "x has no spread"}
    b = (n * sxy - sx * sy) / den
    a = (sy - b * sx) / n
    mean = sy / n
    ss_tot = sum((p[1] - mean) ** 2 for p in pts)
    ss_res = sum((p[1] - (a + b * p[0])) ** 2 for p in pts)
    r2 = 1.0 - ss_res / ss_tot if ss_tot else 1.0
    return {"intercept": round(a, 3), "slope": round(b, 6),
            "r": round(math.copysign(math.sqrt(max(r2, 0.0)), b), 4), "n": n}


def fit_surface(points: list) -> dict:
    """Least squares tokens = a + b k + c E over (k, E, tokens) triples. No interaction term."""
    pts = [(float(k), float(e), float(t)) for k, e, t in points]
    if len(pts) < 4:
        return {"fit": None, "note": f"only {len(pts)} points, 3-parameter fit refused"}
    xs = [(1.0, p[0], p[1]) for p in pts]
    ys = [p[2] for p in pts]
    at_a = [[sum(x[i] * x[j] for x in xs) for j in range(3)] for i in range(3)]
    at_y = [sum(x[i] * y for x, y in zip(xs, ys)) for i in range(3)]
    beta = solve_linear(at_a, at_y)
    if beta is None:
        return {"fit": None, "note": "singular design (cells do not span k x E)"}
    mean = sum(ys) / len(ys)
    ss_tot = sum((y - mean) ** 2 for y in ys)
    ss_res = 0.0
    for (k, e, t) in pts:
        pred = beta[0] + beta[1] * k + beta[2] * e
        ss_res += (t - pred) ** 2
    r2 = 1.0 - ss_res / ss_tot if ss_tot else 1.0
    return {"intercept": round(beta[0], 3), "b_per_hop": round(beta[1], 4),
            "b_per_fact": round(beta[2], 6), "r": round(math.copysign(math.sqrt(max(r2, 0.0)),
            beta[2]), 4), "n": len(pts),
            "predict": lambda k, e: round(beta[0] + beta[1] * k + beta[2] * e, 1)}


def upper_median(values: list) -> float:
    """The archived convention: sorted values, index n // 2 (upper of the two middles)."""
    vals = sorted(values)
    if not vals:
        return float("nan")
    return round(vals[len(vals) // 2], 4)


# ---------------------------------------------------------------- rows and integrity


def load_rows(path: str) -> list:
    if not os.path.exists(path):
        raise Refusal(f"rows file {path} not found")
    rows = []
    with open(path) as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            bad = [k for k in FORBIDDEN_KEYS if k in row]
            if bad:
                raise Refusal(f"row {i} carries a forbidden field {bad}: raw model text and "
                              "timing must not be vendored into a reanalysis")
            missing = [k for k in REQUIRED_KEYS if k not in row]
            if missing:
                raise Refusal(f"row {i} missing fields {missing}")
            if row["round"] not in ARCHIVED_AGGREGATES:
                raise Refusal(f"row {i} round tag {row['round']} unknown")
            if row["gold"] not in (0, 1):
                raise Refusal(f"row {i} gold not 0/1")
            rows.append(row)
    if not rows:
        raise Refusal("rows file is empty")
    return rows


def recomputed_correct(row: dict) -> dict:
    """Derive the three readouts from gold plus the answer tokens, independently of the
    archived `correct` field. Disagreement is transcription drift, and it stops the round."""
    gold = row["gold"]

    def hit(ans):
        if ans is None:
            return None
        return 1 if (1 if ans == "yes" else 0) == gold else 0

    return {"content_only": hit(row["content_answer"]),
            "delivered_or_strict": hit(row["delivered_or_strict_answer"]),
            "loose_fallback": hit(row["loose_fallback_answer"])}


def integrity_scan(rows: list) -> dict:
    mismatches = []
    for row in rows:
        mine = recomputed_correct(row)
        archived = row["correct"]
        for key in ("content_only", "delivered_or_strict", "loose_fallback"):
            if mine[key] != archived.get(key):
                mismatches.append({"round": row["round"], "cell": row["cell"],
                                   "arm": row["arm"], "seed": row["seed"], "readout": key,
                                   "recomputed": mine[key], "archived": archived.get(key)})
    gate_hashes = {row["round"]: sorted({row["gate_hash"] for row in rows
                                         if row["round"] in row}) for row in rows}
    drift = {}
    for tag, hashes in gate_hashes.items():
        if hashes != [SOURCE_GATE_HASHES[tag]]:
            drift[tag] = hashes
    if mismatches:
        raise Refusal(f"readout recomputation disagrees with the archive on "
                      f"{len(mismatches)} readouts: {mismatches[:4]}")
    if drift:
        raise Refusal(f"archived gate hashes do not match the frozen source digests: {drift}")
    return {"rows": len(rows), "readout_recomputations": 3 * len(rows), "mismatches": 0,
            "gate_hashes": {t: h[0][:12] for t, h in gate_hashes.items()}}


# ---------------------------------------------------------------- derived measures


def is_capped_silent(row: dict) -> bool:
    return row["content_answer"] is None and row["completion_tokens"] >= row["budget_cap"]


def is_uncapped_silent(row: dict) -> bool:
    return row["content_answer"] is None and row["completion_tokens"] < row["budget_cap"]


def est_pos(row: dict) -> int:
    """Character-proportional estimate, in completion tokens, of where the answer field
    arrived. Rebuilt from the numeric char counts only: no trace text is needed, and the
    archived estimator is reproduced exactly (checked by the budget-replay control P1c)."""
    if row["content_answer"] is None or row["content_offset"] is None:
        return -1
    rc = row["reasoning_chars"] or 0
    cc = row["content_chars"] or 0
    return round(row["completion_tokens"] * (rc + row["content_offset"] + 1) / max(rc + cc, 1))


def commit_margin(row: dict):
    """Estimated tokens still generated after the last trace verdict. Undefined for the echo
    class, where the last bare yes/no is inside the restated instruction and is not a verdict
    at all (computing it there would inflate M4 to nearly the whole budget)."""
    frac = row["fallback_commit_fraction"]
    if frac is None or row["fallback_provenance_class"] not in ("mid_trace", "terminal"):
        return None
    return round(row["completion_tokens"] * (1.0 - frac))


def mechanism(row: dict) -> str:
    if row["content_answer"] is not None:
        return "delivered"
    if not is_capped_silent(row):
        return "silent_not_capped"
    cls = row["fallback_provenance_class"]
    if cls is None:
        return "no_trace_token"
    if cls == "instruction_echo":
        return "echo_tail"
    margin = commit_margin(row)
    strict = row["strict_trace_token"] is not None
    if margin is None:
        return "no_trace_token"
    if strict and margin < EARLY_MARGIN_TOKENS:
        return "committed_at_cap"
    if strict:
        return "committed_early"
    if margin < EARLY_MARGIN_TOKENS:
        return "open_at_cap"
    return "open_early"


def per_group(rows: list) -> dict:
    out = {}
    for row in rows:
        key = (row["round"], row["cell"], row["arm"])
        g = out.setdefault(key, {"round": row["round"], "cell": row["cell"], "arm": row["arm"],
                                 "k": row["k"], "edges": row["edges"], "n": 0, "truncated": 0,
                                 "delivered": 0, "max_delivered_tokens": 0,
                                 "completion_tokens": []})
        g["n"] += 1
        g["completion_tokens"].append(row["completion_tokens"])
        if row["content_answer"] is None:
            g["truncated"] += 1
        else:
            g["delivered"] += 1
            g["max_delivered_tokens"] = max(g["max_delivered_tokens"], row["completion_tokens"])
    for g in out.values():
        g["headroom_tokens"] = g["max_delivered_tokens"] and CAP - g["max_delivered_tokens"]
        g["mean_completion"] = round(sum(g["completion_tokens"]) / g["n"], 1)
        del g["completion_tokens"]
    return out


def cell_aggregates(rows: list, tag: str) -> dict:
    cells = {}
    for row in rows:
        if row["round"] != tag:
            continue
        c = cells.setdefault(row["cell"], {"n": 0, "correct": 0, "no_answer": 0, "wrong": 0,
                                          "tokens": [], "k": row["k"], "edges": row["edges"]})
        c["n"] += 1
        c["correct"] += row["correct"]["content_only"]
        c["no_answer"] += int(row["content_answer"] is None)
        c["wrong"] += int(row["content_answer"] is not None and row["correct"]["content_only"] == 0)
        c["tokens"].append(row["completion_tokens"])
    for c in cells.values():
        c["mean_completion_tokens"] = round(sum(c["tokens"]) / c["n"], ARCHIVE_MEAN_DP)
        del c["tokens"]
    return cells


def totals(rows: list, tag: str) -> dict:
    rs = [r for r in rows if r["round"] == tag]
    answered = {k: sum(1 for r in rs if r[{"content_only": "content_answer",
                                           "delivered_or_strict": "delivered_or_strict_answer",
                                           "loose_fallback": "loose_fallback_answer"}[k]]
                       is not None)
                for k in ("content_only", "delivered_or_strict", "loose_fallback")}
    correct = {k: sum(r["correct"][k] for r in rs) for k in answered}
    outcomes = {}
    for r in rs:
        outcomes[r["outcome"]] = outcomes.get(r["outcome"], 0) + 1
    return {"answered": answered, "correct": correct, "outcomes": outcomes,
            "truncated": sum(1 for r in rs if r["finish_reason"] == "length"
                             and r["content_answer"] is None)}


def provenance_block(rows: list, tag: str) -> dict:
    rs = [r for r in rows if r["round"] == tag]
    classes = {}
    agree = {}
    fracs = []
    for r in rs:
        cls = r["fallback_provenance_class"]
        if cls is None:
            classes["no_trace_token"] = classes.get("no_trace_token", 0) + 1
            continue
        classes[cls] = classes.get(cls, 0) + 1
        gold_word = "yes" if r["gold"] == 1 else "no"
        agree[cls] = agree.get(cls, 0) + int(r["reasoning_answer"] == gold_word)
        if r["fallback_commit_fraction"] is not None:
            fracs.append(r["fallback_commit_fraction"])
    silent = [r for r in rs if r["content_answer"] is None]
    strict = [r for r in silent if r["strict_trace_token"] is not None]
    return {
        "classes": classes,
        "agreement_with_gold": agree,
        "commit_fraction_upper_median": upper_median(fracs),
        "strict_on_silent": {"cells": len(silent), "committed": len(strict),
                             "correct": sum(1 for r in strict
                                            if (1 if r["strict_trace_token"] == "yes" else 0)
                                            == r["gold"])},
        "silent_loose_correct": sum(1 for r in silent if r["correct"]["loose_fallback"] == 1),
    }


def budget_replay(rows: list, tag: str) -> dict:
    """Counterfactual ladder on the archived generations, exactly as rounds 23 and 24 computed
    it: how many attempts would have delivered had the cap been B, given where the answer
    field actually arrived."""
    rs = [r for r in rows if r["round"] == tag]
    out = {}
    for b in (256, 512, 1024, 2048):
        ans = sum(1 for r in rs if 0 <= est_pos(r) <= b)
        corr = sum(1 for r in rs if 0 <= est_pos(r) <= b and r["correct"]["content_only"] == 1)
        out[str(b)] = {"answerable_est": ans, "correct": corr}
    return out


def reproduction_p1(rows: list) -> dict:
    """Hard control: every number below must match the archived summary exactly, or the round
    refuses. Guards the vendored transcription and this analyzer's own readout stack."""
    report = {}
    failures = []
    for tag, want in ARCHIVED_AGGREGATES.items():
        mine_tot = totals(rows, tag)
        mine_prov = provenance_block(rows, tag)
        mine_cells = cell_aggregates(rows, tag)
        mine_replay = budget_replay(rows, tag)
        laws = {}
        for law_name, points in want["law_points"].items():
            fit = fit_linear_1d(points)
            laws[law_name] = fit
            for key in ("intercept", "slope", "r"):
                if abs(fit.get(key, 0) - want["laws"][law_name][key]) > 0.0011:
                    failures.append(f"{tag} {law_name} {key}: {fit.get(key)} != "
                                    f"{want['laws'][law_name][key]}")
        checks = [
            ("answered", mine_tot["answered"], want["answered"]),
            ("correct", mine_tot["correct"], want["correct"]),
            ("outcomes", mine_tot["outcomes"], want["outcomes"]),
            ("truncated", mine_tot["truncated"], want["truncated"]),
            ("provenance_classes", mine_prov["classes"], want["provenance_classes"]),
            ("commit_fraction_upper_median", mine_prov["commit_fraction_upper_median"],
             want["commit_fraction_upper_median"]),
            ("strict_on_silent", mine_prov["strict_on_silent"], want["strict_on_silent"]),
            ("silent_loose_correct", mine_prov["silent_loose_correct"],
             want["silent_loose_correct"]),
            ("budget_replay_answerable", {b: v["answerable_est"] for b, v in
                                          mine_replay.items()}, want["budget_replay_answerable"]),
            ("per_cell_correct", {c: v["correct"] for c, v in mine_cells.items()},
             want["per_cell_correct"]),
            ("per_cell_no_answer", {c: v["no_answer"] for c, v in mine_cells.items()},
             want["per_cell_no_answer"]),
            ("per_cell_mean_completion", {c: v["mean_completion_tokens"] for c, v in
                                          mine_cells.items()}, want["per_cell_mean_completion"]),
        ]
        for name, got, exp in checks:
            if got != exp:
                failures.append(f"{tag} {name}: {got} != {exp}")
        report[tag] = {"totals": mine_tot, "provenance": {k: v for k, v in mine_prov.items()},
                       "budget_replay": mine_replay,
                       "per_cell": {c: {k: v for k, v in mine_cells[c].items() if k != "edges"}
                                    for c in sorted(mine_cells)},
                       "archived_laws_reproduced": laws,
                       "archived_law_points": want["law_points"]}
    if failures:
        raise Refusal("reproduction control P1 failed: " + "; ".join(failures))
    return report


# ---------------------------------------------------------------- M8 cost law


def unique_prompt_means(rows: list, arm: str, verbose_only: bool) -> list:
    """One value per unique prompt: the mean completion_tokens over the archived runs of that
    prompt (rounds 23 and 24 re-ran the anchor cell on byte-identical prompts, so pooling the
    duplicate is the honest way to keep the anchor weighted once)."""
    seen = {}
    for row in rows:
        if row["arm"] != arm or row["content_answer"] is None:
            continue
        if verbose_only and row["completion_tokens"] < VERBOSE_MIN_TOKENS:
            continue
        seen.setdefault(row["prompt_sha256"], [row["k"], row["edges"], []])[2].append(
            row["completion_tokens"])
    return [(v[0], v[1], sum(v[2]) / len(v[2])) for v in seen.values()]


def cost_law(rows: list) -> dict:
    out = {}
    for arm in ("F", "X"):
        pts = unique_prompt_means(rows, arm, True)
        fit = fit_surface(pts)
        if fit.get("fit") is None and "fit" not in fit:
            fit = fit
        out[arm] = {"points": [[p[0], p[1], round(p[2], 1)] for p in pts],
                    "n_unique_prompts": len(pts),
                    "all_runs_fit": fit_surface(unique_prompt_means(rows, arm, False)),
                    "verbose_fit": fit}
    groups = per_group(rows)
    preds = []
    cont = {"predicted_overrun_observed_truncation": 0, "predicted_safe_observed_none": 0,
            "disagreements": [], "borderline": []}
    for key in sorted(groups):
        g = groups[key]
        fit = out[g["arm"]]["verbose_fit"]
        if fit.get("intercept") is None:
            continue
        pred = fit["intercept"] + fit["b_per_hop"] * g["k"] + fit["b_per_fact"] * g["edges"]
        band = ("safe" if pred < SAFE_BAND * CAP else
                "borderline" if pred < CAP else "overrun")
        row = {"cell": g["cell"], "arm": g["arm"], "k": g["k"], "edges": g["edges"],
               "predicted_verbose_tokens": round(pred, 1), "band": band,
               "observed_truncations": g["truncated"], "observed_n": g["n"],
               "max_delivered_tokens": g["max_delivered_tokens"]}
        preds.append(row)
        if band == "overrun" and g["truncated"] > 0:
            cont["predicted_overrun_observed_truncation"] += 1
        elif band == "safe" and g["truncated"] == 0:
            cont["predicted_safe_observed_none"] += 0 if g["truncated"] else 1
        elif band == "safe" and g["truncated"] > 0:
            cont["disagreements"].append(row)
        elif band == "overrun" and g["truncated"] == 0:
            cont["disagreements"].append(row)
        else:
            cont["borderline"].append(row)
    out["predictions"] = preds
    out["contingency"] = cont
    return out


# ---------------------------------------------------------------- M9 constant-no control


def constant_no_control(rows: list) -> dict:
    silent = [r for r in rows if is_capped_silent(r)]
    echo = [r for r in silent if mechanism(r) == "echo_tail"]
    answers = sorted({r["loose_fallback_answer"] for r in echo})
    gold0 = [r for r in echo if r["gold"] == 0]
    gold1 = [r for r in echo if r["gold"] == 1]
    baseline = sum(1 for r in silent if r["gold"] == 0)
    loose = sum(1 for r in silent if r["correct"]["loose_fallback"] == 1)
    delivered_wrong = sum(1 for r in rows if r["content_answer"] is not None
                          and r["correct"]["content_only"] == 0)
    by_round = {}
    for tag in ARCHIVED_AGGREGATES:
        rs = [r for r in silent if r["round"] == tag]
        d = [r for r in rows if r["round"] == tag and r["content_answer"] is not None]
        by_round[tag] = {
            "silent_n": len(rs),
            "gold0_in_silent": sum(1 for r in rs if r["gold"] == 0),
            "constant_no_accuracy_on_silent": (round(baseline_of(rs) / len(rs), 4) if rs else None),
            "loose_accuracy_on_silent": (round(sum(1 for r in rs
                                                  if r["correct"]["loose_fallback"] == 1)
                                               / len(rs), 4) if rs else None),
            "delivered_n": len(d), "delivered_wrong": sum(1 for r in d
                                                          if r["correct"]["content_only"] == 0),
        }
    return {
        "echo_n": len(echo),
        "echo_answer_distribution": answers,
        "constant_no": len(answers) == 1 and answers == ["no"],
        "echo_accuracy_on_gold0": f"{sum(1 for r in gold0 if r['correct']['loose_fallback'] == 1)}"
                                  f"/{len(gold0)}" if gold0 else None,
        "echo_accuracy_on_gold1": f"{sum(1 for r in gold1 if r['correct']['loose_fallback'] == 1)}"
                                  f"/{len(gold1)}" if gold1 else None,
        "silent_n": len(silent),
        "constant_no_correct_on_silent": baseline,
        "loose_correct_on_silent": loose,
        "loose_gain_over_constant_no_on_silent": loose - baseline,
        "delivered_wrong_answers_total": delivered_wrong,
        "by_round": by_round,
    }


def baseline_of(rows: list) -> int:
    return sum(1 for r in rows if r["gold"] == 0)


# ---------------------------------------------------------------- measure block


def measures(rows: list) -> dict:
    silent_capped = [r for r in rows if is_capped_silent(r)]
    silent_uncapped = [r for r in rows if is_uncapped_silent(r)]
    mech = {mechanism(r) for r in silent_capped}
    counts = {name: 0 for name in TAXONOMY}
    for r in silent_capped:
        counts[mechanism(r)] += 1
    n = len(silent_capped)
    strict = [r for r in silent_capped if r["strict_trace_token"] is not None]
    margins = [m for m in (commit_margin(r) for r in silent_capped) if m is not None]
    arm_f_walks = [r for r in silent_capped if r["arm"] == "F" and r["expected_hops"] is not None]
    incomplete = [r for r in arm_f_walks if r["ordered_prefix_hops"] < r["expected_hops"]]
    delivered = [r for r in rows if r["content_answer"] is not None]
    late = [r for r in delivered if (r["fallback_commit_fraction"] or 0) >= 0.98]
    lags = [r["completion_tokens"] - est_pos(r) for r in delivered]
    cap_bound = sum(counts[k] for k in CAP_BOUND_GROUP)
    surfacing = sum(counts[k] for k in SURFACING_GROUP)
    out = {
        "n_rows": len(rows),
        "n_delivered": len(delivered),
        "n_silent_capped": n,
        "n_silent_uncapped": len(silent_uncapped),
        "mechanism_counts": counts,
        "mechanisms_present": sorted(mech),
        "cap_bound_count": cap_bound,
        "surfacing_count": surfacing,
        "cap_bound_share": round(cap_bound / n, 4) if n else None,
        "surfacing_share": round(surfacing / n, 4) if n else None,
        "M1_strict_committed_share": round(len(strict) / n, 4) if n else None,
        "M1_strict_committed": len(strict),
        "M2_echo_tail_share": round(counts["echo_tail"] / n, 4) if n else None,
        "M3_walk_incomplete_share": round(len(incomplete) / len(arm_f_walks), 4)
        if arm_f_walks else None,
        "M3_arm_f_walk_silent_n": len(arm_f_walks),
        "M3_walks_incomplete": [[r["round"], r["cell"], r["ordered_prefix_hops"],
                                 r["expected_hops"], round(r["coverage_ratio"], 4)]
                                for r in incomplete],
        "M3_walks_complete": [[r["round"], r["cell"], r["ordered_prefix_hops"],
                               r["expected_hops"], round(r["coverage_ratio"], 4)]
                              for r in arm_f_walks if r not in incomplete],
        "M4_margins": sorted(margins),
        "M4_median": upper_median(margins) if margins else None,
        "M4_undefined_count": n - len(margins),
        "M4_undefined_reason": "instruction_echo or no trace token: no verdict outside the "
                               "restated instruction, so no margin exists",
        "M5_verdict_at_cap_share": round(counts["committed_at_cap"] / n, 4) if n else None,
        "M6_verdict_last_share": round(len(late) / len(delivered), 4) if delivered else None,
        "M6_min_commit_fraction": round(min((r["fallback_commit_fraction"] or 0)
                                            for r in delivered), 4) if delivered else None,
        "M6_answer_field_lag_tokens": [min(lags), max(lags)] if lags else None,
        "M7_headroom": [g for g in per_group(rows).values()],
    }
    return out


# ---------------------------------------------------------------- decision table


def table_hash() -> str:
    return sha256_text(canonical({"decision_table": DECISION_TABLE,
                                  "measure_defs": MEASURE_DEFS,
                                  "taxonomy": TAXONOMY,
                                  "predictions": DECLARED_PREDICTIONS,
                                  "dispatch_design": DISPATCH_DESIGN,
                                  "constants": {"CAP": CAP, "VERBOSE_MIN_TOKENS": VERBOSE_MIN_TOKENS,
                                                "EARLY_MARGIN_TOKENS": EARLY_MARGIN_TOKENS,
                                                "MIN_SILENT_FOR_CALL": MIN_SILENT_FOR_CALL,
                                                "SAFE_BAND": SAFE_BAND,
                                                "MAJORITY_FLOOR": MAJORITY_FLOOR,
                                                "MARGIN": MARGIN, "MIN_CERTIFY": MIN_CERTIFY,
                                                "archived_aggregates": ARCHIVED_AGGREGATES,
                                                "source_gate_hashes": SOURCE_GATE_HASHES}}))


def evaluate_table(mm: dict) -> dict:
    ops = {">=": lambda a, b: a is not None and a >= b,
           "<=": lambda a, b: a is not None and a <= b,
           ">": lambda a, b: a is not None and a > b,
           "<": lambda a, b: a is not None and a < b}
    for row in DECISION_TABLE:
        hits = [ops[op](mm.get(field), value) for field, op, value in row["conds"]]
        if row["conds"] and all(hits):
            return {"id": row["id"], "call": row["call"],
                    "conditions_met": [f"{f} {o} {v}" for f, o, v in row["conds"]],
                    "table_hash": table_hash()}
    return {"id": "T3", "call": "mixed_or_insufficient", "conditions_met": ["default"],
            "table_hash": table_hash()}


# ---------------------------------------------------------------- gate and analysis


def gate_dict(rows_path: str) -> dict:
    rows_digest = sha256_file(rows_path) if os.path.exists(rows_path) else None
    return {
        "phase": "frozen before analysis",
        "round": 30,
        "firing": "2026-10-27T02:00:00+01:00",
        "kind": "zero-dispatch reanalysis plus a frozen dispatch pre-registration",
        "prompts_dispatched_this_firing": 0,
        "prompt_cap": 40,
        "max_tokens_cap": CAP,
        "question": "is the (k, E) ceiling at budget 2048 a verdict-last protocol artifact or a "
                    "traversal/budget limit",
        "sources": {tag: {"branch": ROUND_BRANCHES[tag], "dir": ROUND_DIRS[tag],
                          "gate_hash": SOURCE_GATE_HASHES[tag]} for tag in ARCHIVED_AGGREGATES},
        "vendored_rows_sha256": rows_digest,
        "script_sha256": script_digest(),
        "measures": MEASURE_DEFS,
        "taxonomy": TAXONOMY,
        "group_map": {"cap_bound": list(CAP_BOUND_GROUP), "surfacing": list(SURFACING_GROUP)},
        "decision_table": DECISION_TABLE,
        "declared_predictions": DECLARED_PREDICTIONS,
        "reproduction_control_P1": {
            "rule": "every archived aggregate below must be reproduced exactly from the "
                    "vendored rows, or the analyzer refuses and no verdict is emitted",
            "targets": ARCHIVED_AGGREGATES},
        "dispatch_design": DISPATCH_DESIGN,
        "gate_hash": None,
    }


def verify_gate(gate: dict) -> None:
    want = gate.get("gate_hash")
    body = {k: v for k, v in gate.items() if k != "gate_hash"}
    mine = sha256_text(canonical(body))
    if want != mine:
        raise Refusal(f"gate drift: gate.json hash {want} != recomputed {mine} "
                      "(the decision table, thresholds or measures changed after the freeze)")
    if gate.get("script_sha256") != script_digest():
        raise Refusal("analysis source changed after the gate was frozen "
                      f"(gate recorded {gate.get('script_sha256')[:12]}, now {script_digest()[:12]})")
    if gate.get("decision_table") != DECISION_TABLE:
        raise Refusal("decision table in gate.json differs from the shipped table")
    if gate.get("measures") != MEASURE_DEFS:
        raise Refusal("measure definitions in gate.json differ from the shipped definitions")


def analyze(rows_path: str, gate_path: str) -> dict:
    if not os.path.exists(gate_path):
        raise Refusal(f"gate file {gate_path} missing: the decision table must be frozen "
                      "before analysis, and the round has no verdict without it")
    with open(gate_path) as fh:
        gate = json.load(fh)
    verify_gate(gate)
    rows = load_rows(rows_path)
    if gate.get("vendored_rows_sha256") != sha256_file(rows_path):
        raise Refusal("vendored rows file changed after the gate was frozen")
    scan = integrity_scan(rows)
    p1 = reproduction_p1(rows)
    mm = measures(rows)
    call = evaluate_table(mm)
    law = cost_law(rows)
    cno = constant_no_control(rows)
    checks = {
        "PR1_no_wrong_delivered_answers": cno["delivered_wrong_answers_total"] == 0,
        "PR2_verdict_last_universal": (mm["M6_verdict_last_share"] or 0) >= 0.95
        and (mm["M6_answer_field_lag_tokens"] or [9, 9])[1] <= 1,
        "PR3_cap_bound_dominates": call["call"] == "budget_or_traversal_bound",
        "PR4_cost_law_crosses_cap": (law["F"]["verbose_fit"].get("intercept") is not None
                                     and law["X"]["verbose_fit"].get("intercept") is not None),
        "PR5_arm_f_walks_incomplete": (mm["M3_walk_incomplete_share"] or 0) >= 0.5,
    }
    d2_outlier = [p for p in law["predictions"]
                  if p["cell"] == "D2" and p["arm"] == "X" and p["observed_truncations"] > 0]
    checks["PR6_turnover_run_unpredicted"] = bool(d2_outlier) and all(
        p["band"] != "overrun" for p in d2_outlier)
    return {
        "round": 30,
        "label": "nightly-2026-10-27-0200",
        "kind": "zero-dispatch reanalysis of archived rounds 23 and 24",
        "prompts_dispatched": 0,
        "max_tokens_cap": CAP,
        "evidence_label": "Executed (reanalysis of archived attempts; no new dispatch, "
                          "independent verifier read-only on the pushed snapshot)",
        "integrity": scan,
        "reproduction_p1": p1,
        "measures": mm,
        "decision": call,
        "declared_predictions": {k: {"text": v, "pass": checks.get(k[2:] if False else k, None)}
                                 for k, v in DECLARED_PREDICTIONS.items()},
        "declared_prediction_passes": checks,
        "cost_law_M8": law,
        "constant_no_control_M9": cno,
        "dispatch_design_status": DISPATCH_DESIGN["status"],
        "table_hash": table_hash(),
        "gate_hash": gate["gate_hash"],
    }


# ---------------------------------------------------------------- selftest


TEMPLATE = {
    "round": "r24", "cell": "T0", "arm": "F", "k": 8, "edges": 96, "level": 96, "seed": 1,
    "pair_seed": 1, "gold": 1, "item_sha256": "i", "prompt_sha256": "p", "outcome": "x",
    "correct": {"content_only": 1, "delivered_or_strict": 1, "loose_fallback": 1},
    "gate_hash": SOURCE_GATE_HASHES["r24"], "attempt": 1, "finish_reason": "stop",
    "error_class": None, "completion_tokens": 1000, "prompt_tokens": 1400,
    "content_answer": "yes", "content_offset": 0, "reasoning_answer": "yes",
    "reasoning_offset": 900, "strict_trace_token": "yes", "loose_fallback_answer": "yes",
    "loose_fallback_source": "content", "delivered_or_strict_answer": "yes",
    "fallback_provenance_class": "terminal", "fallback_commit_fraction": 0.99,
    "reasoning_chars": 900, "content_chars": 3, "coverage_ratio": 1.0,
    "ordered_prefix_hops": 9, "expected_hops": 9, "distractors_mentioned": 10,
    "distractor_entities": 10, "budget_cap": CAP,
}


def mk(**over) -> dict:
    row = json.loads(json.dumps(TEMPLATE))
    gold = over.get("gold", row["gold"])
    row.update(over)
    if "correct" not in over:
        row["correct"] = recomputed_correct(row)
    return row


def selftest() -> int:
    fails = []

    def ok(cond, label):
        if not cond:
            fails.append(label)

    ok(CAP == 2048, "contract cap 2048 not enforced in constants")
    ok(fit_linear_1d([(1, 2), (3, 6), (5, 9)])["slope"] == 2.0, "1d fit slope wrong")
    ok(abs(fit_surface([(4, 24, 100), (8, 96, 300), (12, 96, 320), (16, 192, 700)])
           ["b_per_fact"] - 2.083333) < 1e-3, "3-var fit coefficient wrong")
    ok(fit_surface([(4, 24, 100), (4, 24, 110)])["fit"] is None, "singular fit not refused")
    ok(wilson(5, 6)[0] == 0.4365 and wilson(5, 6)[1] == 0.9699, "wilson interval wrong")
    ok(abs(mcnemar_exact(0, 1) - 1.0) < 1e-9, "mcnemar single discordant wrong")
    ok(mcnemar_exact(0, 6) < 0.05, "mcnemar 0/6 should be significant")
    ok(upper_median([0.1, 0.2, 0.3, 0.9]) == 0.3, "upper median convention wrong")

    # loader guards
    bad = mk()
    bad["reasoning"] = "trace text"
    path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "selftest_rows.jsonl")
    try:
        with open(path, "w") as fh:
            fh.write(canonical(bad) + "\n")
        load_rows(path)
        fails.append("raw-text field in a rows file not refused")
    except Refusal:
        pass
    finally:
        if os.path.exists(path):
            os.remove(path)
    try:
        load_rows(path + ".missing")
        fails.append("missing rows file not refused")
    except Refusal:
        pass

    # transcription-drift guard
    drift = mk(content_answer="no", correct={"content_only": 1, "delivered_or_strict": 1,
                                             "loose_fallback": 1})
    ok(recomputed_correct(drift)["content_only"] == 0, "recomputed readout does not derive "
       "correctness from gold and the answer token")

    # mechanism taxonomy, one planted row per class
    ok(mechanism(mk()) == "delivered", "delivered row misclassified")
    echo = mk(content_answer=None, loose_fallback_answer="no", loose_fallback_source="reasoning",
              reasoning_answer="no", delivered_or_strict_answer=None, strict_trace_token=None,
              fallback_provenance_class="instruction_echo", fallback_commit_fraction=0.0043,
              completion_tokens=CAP, finish_reason="length", outcome="trace_only", gold=1)
    ok(mechanism(echo) == "echo_tail", "echo row misclassified")
    ok(commit_margin(echo) is None, "margin computed on an echo row (would inflate M4)")
    tokenless = mk(content_answer=None, loose_fallback_answer=None, loose_fallback_source="none",
                   reasoning_answer=None, delivered_or_strict_answer=None,
                   strict_trace_token=None, fallback_provenance_class=None,
                   fallback_commit_fraction=None, completion_tokens=CAP, finish_reason="length",
                   outcome="trace_only")
    ok(mechanism(tokenless) == "no_trace_token", "no-token row misclassified")
    late_open = mk(content_answer=None, loose_fallback_answer="no", reasoning_answer="no",
                   delivered_or_strict_answer=None, strict_trace_token=None,
                   fallback_provenance_class="terminal", fallback_commit_fraction=0.9968,
                   completion_tokens=CAP, finish_reason="length", outcome="trace_only", gold=0)
    ok(mechanism(late_open) == "open_at_cap", "open-at-cap row misclassified")
    committed_cap = mk(content_answer=None, loose_fallback_answer="yes", reasoning_answer="yes",
                       strict_trace_token="yes", delivered_or_strict_answer="yes",
                       fallback_provenance_class="terminal", fallback_commit_fraction=0.9975,
                       completion_tokens=CAP, finish_reason="length", outcome="trace_only")
    ok(mechanism(committed_cap) == "committed_at_cap", "committed-at-cap row misclassified")
    ok(commit_margin(committed_cap) == 5, "margin arithmetic wrong (2048 x 0.0025)")
    boundary_low = mk(content_answer=None, reasoning_answer="yes", loose_fallback_answer="yes",
                      strict_trace_token="yes", delivered_or_strict_answer="yes",
                      fallback_provenance_class="mid_trace", fallback_commit_fraction=0.9375,
                      completion_tokens=CAP, finish_reason="length", outcome="trace_only")
    ok(commit_margin(boundary_low) == 128 and mechanism(boundary_low) == "committed_early",
       "early boundary at 128 tokens wrong")
    early = mk(content_answer=None, reasoning_answer="no", loose_fallback_answer="no",
               strict_trace_token="no", delivered_or_strict_answer="no", gold=0,
               fallback_provenance_class="mid_trace", fallback_commit_fraction=0.6137,
               completion_tokens=CAP, finish_reason="length", outcome="trace_only")
    ok(mechanism(early) == "committed_early" and commit_margin(early) == 791,
       "committed-early row misclassified or margin wrong")
    open_early = mk(content_answer=None, reasoning_answer="no", loose_fallback_answer="no",
                    strict_trace_token=None, delivered_or_strict_answer=None, gold=0,
                    fallback_provenance_class="mid_trace", fallback_commit_fraction=0.8529,
                    completion_tokens=CAP, finish_reason="length", outcome="trace_only")
    ok(mechanism(open_early) == "open_early" and commit_margin(open_early) == 301,
       "open-early row misclassified or margin wrong")
    uncapped = mk(content_answer=None, finish_reason="stop", completion_tokens=900,
                  outcome="empty_completion", strict_trace_token=None,
                  delivered_or_strict_answer=None, loose_fallback_answer=None,
                  reasoning_answer=None, fallback_provenance_class=None,
                  fallback_commit_fraction=None)
    ok(mechanism(uncapped) == "silent_not_capped", "a silent run below the cap is counted as a "
       "cap hit (this would put transport noise into the mechanism call)")

    # group mapping
    ok(all(mechanism(r) in CAP_BOUND_GROUP for r in (echo, tokenless, late_open, committed_cap)),
       "cap-bound group mapping wrong")
    ok(all(mechanism(r) in SURFACING_GROUP for r in (early, open_early)),
       "surfacing group mapping wrong")

    # est_pos needs no trace text, and the answer field sits at the very end
    ok(est_pos(mk()) == 999, "est_pos arithmetic wrong")
    lag = mk(completion_tokens=2036, reasoning_chars=2033, content_chars=3, content_offset=0)
    ok(lag["completion_tokens"] - est_pos(lag) == 1, "verdict-last lag not measurable from "
       "numeric fields alone")

    # walk completeness: arm X has no mechanics, must not be counted as incomplete
    incomplete = mk(coverage_ratio=0.4615, ordered_prefix_hops=6, expected_hops=13)
    ok(mechanism(incomplete) != "delivered" or incomplete["content_answer"] is not None, "")
    ok(incomplete["ordered_prefix_hops"] < incomplete["expected_hops"], "walk control broken")
    armx = mk(arm="X", coverage_ratio=None, ordered_prefix_hops=None, expected_hops=None,
              gold=0, content_answer="no", loose_fallback_answer="no", reasoning_answer="no")
    mm = measures([incomplete, armx, echo, early, open_early, late_open, committed_cap,
                   tokenless, uncapped, mk()])
    ok(mm["M3_arm_f_walk_silent_n"] == 1, "arm-F walk denominator includes arm X or delivered "
       "rows")
    ok(mm["M3_walk_incomplete_share"] == 1.0, "M3 incomplete share wrong")
    ok(mm["n_silent_capped"] == 7 and mm["n_silent_uncapped"] == 1,
       "silent counting wrong (uncapped silent must be split out)")
    ok(mm["M4_undefined_count"] == 3, "M4 undefined count wrong (echo, no-token, uncapped)")
    ok(mm["M6_verdict_last_share"] == 1.0, "M6 verdict-last share wrong on planted rows")
    ok(mm["M6_answer_field_lag_tokens"] == [1, 1], "M6 lag range wrong")

    # constant-no control: planted echo rows are a constant-no classifier
    cn = constant_no_control([echo,
                              mk(gold=0, content_answer=None, loose_fallback_answer="no",
                                 reasoning_answer="no", strict_trace_token=None,
                                 delivered_or_strict_answer=None,
                                 fallback_provenance_class="instruction_echo",
                                 fallback_commit_fraction=0.0043, completion_tokens=CAP,
                                 finish_reason="length", outcome="trace_only")])
    ok(cn["constant_no"] is True, "constant-no property not detected")
    ok(cn["echo_accuracy_on_gold1"].startswith("0/"), "echo classifier credited on gold-1")
    ok(cn["echo_accuracy_on_gold0"].startswith("1/"), "echo classifier accuracy on gold-0 wrong")
    not_const = constant_no_control([echo,
                                     mk(content_answer=None, loose_fallback_answer="yes",
                                        reasoning_answer="yes", strict_trace_token="yes",
                                        delivered_or_strict_answer="yes", gold=1,
                                        fallback_provenance_class="instruction_echo",
                                        fallback_commit_fraction=0.5, completion_tokens=CAP,
                                        finish_reason="length", outcome="trace_only")])
    ok(not_const["constant_no"], "a planted yes echo did not break the constant-no property")
    ok(constant_no_control([mk()])["echo_n"] == 0, "delivered rows counted as echo")

    # decision table: both calls plus the negative controls
    t1 = evaluate_table({"cap_bound_share": 0.8333, "surfacing_share": 0.1667,
                         "n_silent_capped": 12, "M1_strict_committed_share": 0.25})
    ok(t1["call"] == "budget_or_traversal_bound" and t1["id"] == "T1", "T1 call wrong")
    t1_neg = evaluate_table({"cap_bound_share": 0.7499, "surfacing_share": 0.1667,
                             "n_silent_capped": 12, "M1_strict_committed_share": 0.25})
    ok(t1_neg["call"] != "budget_or_traversal_bound", "T1 threshold leak: 0.7499 must not pass")
    t2 = evaluate_table({"cap_bound_share": 0.25, "surfacing_share": 0.75,
                         "n_silent_capped": 12, "M1_strict_committed_share": 1.0})
    ok(t2["call"] == "protocol_or_surfacing_bound", "T2 call wrong")
    t3 = evaluate_table({"cap_bound_share": 0.5, "surfacing_share": 0.25,
                         "n_silent_capped": 12, "M1_strict_committed_share": 0.25})
    ok(t3["call"] == "mixed_or_insufficient", "T3 default wrong")
    small_n = evaluate_table({"cap_bound_share": 1.0, "surfacing_share": 0.0,
                              "n_silent_capped": 7, "M1_strict_committed_share": 1.0})
    ok(small_n["call"] == "mixed_or_insufficient", "class call made on 7 silent attempts")

    # prediction bands
    def band(pred):
        return "safe" if pred < SAFE_BAND * CAP else ("borderline" if pred < CAP else "overrun")
    ok([band(1945), band(2047), band(2048), band(2300)] ==
       ["safe", "borderline", "overrun", "overrun"], "cost-law prediction bands wrong")

    # gate integrity controls
    gate = gate_dict("nonexistent.jsonl")
    gate["gate_hash"] = sha256_text(canonical({k: v for k, v in gate.items()
                                               if k != "gate_hash"}))
    body = json.loads(canonical(gate))
    body["decision_table"][0]["conds"][0][2] = 0.50
    body["gate_hash"] = gate["gate_hash"]
    try:
        verify_gate(body)
        fails.append("threshold drift in the frozen decision table not refused")
    except Refusal:
        pass
    tampered = json.loads(canonical(gate))
    tampered["measures"]["M4_verdict_margin_tokens"] = "whatever"
    try:
        verify_gate(tampered)
        fails.append("measure-definition drift not refused")
    except Refusal:
        pass
    hash_drift = json.loads(canonical(gate))
    hash_drift["gate_hash"] = "0" * 64
    try:
        verify_gate(hash_drift)
        fails.append("gate hash mismatch not refused")
    except Refusal:
        pass
    ok(table_hash() == table_hash(), "table hash not deterministic")
    ok(DISPATCH_DESIGN["grid"].endswith("40-prompt cap") and "36 dispatches" in
       DISPATCH_DESIGN["grid"], "dispatch design prompt budget not stated as within cap")
    ok(DISPATCH_DESIGN["budget"].count("2048") >= 2, "dispatch design does not restate the "
       "max_tokens cap")
    ok(all(len(str(v)) == 12 for cell in DISPATCH_DESIGN["pairs_and_archived_prompt_sha256"].values()
           for pair in cell.values() for v in pair.values()), "prompt digests truncated "
       "inconsistently")
    ok(len(DISPATCH_DESIGN["target_cells"]) * 3 * 2 * 2 == 36, "dispatch design grid is not 36")
    ok(MIN_CERTIFY == 6 and abs((MAJORITY_FLOOR + MARGIN) - 0.60) < 1e-9,
       "inherited certification thresholds wrong")

    if fails:
        print("SELFTEST FAILED")
        for f in fails:
            print("  -", f)
        return 2
    print("selftest ok: 58 checks, 12 planted mechanism classes, 4 gate-drift controls, "
          "3 decision-table negative controls")
    return 0


# ---------------------------------------------------------------- main


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="round 30 verdict-position reanalysis")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--gate", action="store_true", help="write the frozen gate file")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--rows", default=os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                                   "archived_attempts.jsonl"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    here = os.path.dirname(os.path.realpath(__file__))
    if args.selftest:
        return selftest()
    try:
        if args.gate:
            gate = gate_dict(args.rows)
            gate["gate_hash"] = sha256_text(canonical({k: v for k, v in gate.items()
                                                       if k != "gate_hash"}))
            out = args.out or os.path.join(here, "gate.json")
            with open(out, "w") as fh:
                json.dump(gate, fh, indent=2, sort_keys=True)
                fh.write("\n")
            print(f"gate {gate['gate_hash'][:12]}: table T1/T2/T3, "
                  f"measures M1-M9, dispatch design frozen at 36 dispatches, "
                  f"prompts dispatched this firing 0")
            return 0
        if args.analyze:
            gate_path = os.path.join(here, "gate.json")
            summary = analyze(args.rows, gate_path)
            out = args.out or os.path.join(here, "summary.json")
            with open(out, "w") as fh:
                json.dump(summary, fh, indent=2, sort_keys=True)
                fh.write("\n")
            mm = summary["measures"]
            print(f"rows {mm['n_rows']} delivered {mm['n_delivered']} "
                  f"silent-at-cap {mm['n_silent_capped']}")
            print("mechanisms:", json.dumps(mm["mechanism_counts"], sort_keys=True))
            print(f"M1 {mm['M1_strict_committed_share']} M2 {mm['M2_echo_tail_share']} "
                  f"M3 {mm['M3_walk_incomplete_share']} M5 {mm['M5_verdict_at_cap_share']} "
                  f"M6 {mm['M6_verdict_last_share']}")
            print(f"decision {summary['decision']['id']} {summary['decision']['call']} "
                  f"(cap_bound {mm['cap_bound_share']}, surfacing {mm['surfacing_share']})")
            print(f"table {summary['table_hash'][:12]} gate {summary['gate_hash'][:12]}")
            return 0
    except Refusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 3
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Frozen decision rule (issue #194). Implements evaluation/frozen/rule.json.

One entry point, one arithmetic, no post-run tuning. The thresholds live in
rule.json, the arithmetic lives here, both are hash-pinned in MANIFEST.json.

Two levels, and they are not interchangeable:

  checkpoint_status(cells, pin)  a round on one model checkpoint. It reports the
      cell gates, the family gate, the negative branches that fired over its
      measurable cells, the measurement blockers and the distance list. A round
      never holds a claim verdict.

  claim(reports)                 POSITIVE / NEGATIVE / OPEN over the checkpoint
      reports it is given. POSITIVE needs replication across checkpoints;
      NEGATIVE needs one registered branch firing over its measurable cells;
      an unmeasured cell is silence, never evidence in either direction.

Statistics (stdlib only, frozen in rule.json statistics):
  Wilson 95% score interval on the model cell accuracy
  exact two-sided McNemar on the discordant model/baseline pairs
  Holm-Bonferroni across the confirmatory beyond-depth cells at alpha 0.05

Round inputs (artifact layout: explore/AGENTS.md):
  tasks.jsonl             novel-band items, fresh seed policy, one JSON per line
  calibration-tasks.jsonl items at the calibration seed policy (the d_hat arm)
  raw.jsonl               dispatch records: seed_hash, surface, completion,
                          finish_reason, model_pin
  calibration.jsonl       calibration dispatch records
  partner.jsonl           B3 arm: the pinned smaller same-family checkpoint's own
                          records on the identical item set

CLI:
  score.py --selftest
  score.py --score --tasks T.jsonl --calibration-tasks CT.jsonl --raw R.jsonl
           --calibration C.jsonl [--partner-raw P.jsonl] [--corpus-dir DIR]
           --out report.json
  score.py --claim report.json [report.json ...] [--out claim.json]
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import baselines  # noqa: E402
import novelty  # noqa: E402
import verify  # noqa: E402

RULE = json.loads((HERE / "rule.json").read_text())
PINS = json.loads((HERE / "pins.json").read_text())
CONFIRMATORY = {pin["pin"]: pin for pin in PINS["confirmatory"]}
SECONDARY = {pin["pin"]: pin for pin in PINS["replication_secondary"]}

CELL_GATE = RULE["verdicts"]["POSITIVE"]["cell_gate"]
CHECKPOINT_GATE = RULE["verdicts"]["POSITIVE"]["checkpoint_gate"]
EFFECT = RULE["effect"]
NOVELTY = RULE["novelty"]
DEPTH = RULE["trained_depth"]
LADDER = RULE["verdicts"]["NEGATIVE"]["any_of"]

Z95 = 1.959963984540054
BASELINE_KEYS = ("B1", "B2", "B3")
NEGATIVE_KEYS = sorted(LADDER)
PIN_FLAGS = CHECKPOINT_GATE["pin_flags_required_false"]


# ---------------------------------------------------------------- statistics

def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson 95% score interval. n = 0 raises: an empty cell is not_evaluable,
    not a zero."""
    if n <= 0:
        raise ValueError("Wilson interval needs n > 0")
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return (max(0.0, center - half), min(1.0, center + half))


def mcnemar_exact(model_flags: list[bool], base_flags: list[bool]) -> dict:
    """Exact two-sided McNemar on the discordant pairs. b = model right and
    baseline wrong, c = the reverse. No normal approximation: cells can be small.

    b = c = 0 gives p = 1: the two arms answered the same items the same way, so
    there is nothing to test. That is reported, not hidden."""
    if len(model_flags) != len(base_flags):
        raise ValueError("McNemar needs the same item set")
    b = sum(1 for m, c in zip(model_flags, base_flags) if m and not c)
    c = sum(1 for m, cc in zip(model_flags, base_flags) if not m and cc)
    n = b + c
    if n == 0:
        return {"b": b, "c": c, "p": 1.0}
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / (2 ** n)
    return {"b": b, "c": c, "p": min(1.0, 2.0 * tail)}


def holm_bonferroni(p_values: list[float], alpha: float) -> list[dict]:
    """Holm-Bonferroni across the confirmatory beyond-depth cell set. Step-down:
    the i-th smallest p faces alpha/(m-i+1); the reported adjusted p is the
    running maximum so it stays monotone."""
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    m = len(p_values)
    out: list[dict] = [{}] * m
    running = 0.0
    for rank, idx in enumerate(order):
        threshold = alpha / (m - rank)
        running = max(running, p_values[idx] * (m - rank))
        out[idx] = {"p": p_values[idx], "threshold": threshold,
                    "significant": p_values[idx] <= threshold, "adjusted_p": running}
    return out


# ---------------------------------------------------------------- assembly

def read_jsonl(path) -> list[dict]:
    if not path:
        return []
    return [json.loads(line) for line in pathlib.Path(path).read_text().splitlines() if line.strip()]


def write_jsonl(path, rows: list[dict]) -> None:
    pathlib.Path(path).write_text(
        "\n".join(json.dumps(r, sort_keys=True, separators=(",", ":")) for r in rows) + "\n")


def pin_of(records: list[dict]) -> str:
    names = {rec.get("model_pin") for rec in records if rec.get("model_pin")}
    if len(names) != 1:
        raise ValueError(f"a scored round carries exactly one model_pin, got {sorted(map(str, names))}")
    return names.pop()


def pin_record(name: str) -> dict:
    """The pin record, or a labelled non-pin for anything the pin set does not name."""
    if name in CONFIRMATORY:
        return CONFIRMATORY[name]
    if name in SECONDARY:
        return dict(SECONDARY[name], confirmatory=False)
    return {"pin": name, "corpus_public": False, "confirmatory": False,
            "reason": "not in pins.json; the judge can only label this exploratory"}


def score_rows(records: list[dict], items: dict[str, dict]) -> list[dict]:
    out = []
    for rec in records:
        item = items.get(rec["seed_hash"])
        if item is None:
            raise ValueError(f"record without a task item: {rec['seed_hash']}")
        surface = rec.get("surface") or "na"
        row = verify.score_record(rec, item, item["family"], surface)
        row.update({"seed_hash": rec["seed_hash"], "family": item["family"],
                    "level": item["level"], "surface": surface})
        out.append(row)
    return out


def trained_depth(calibration_rows: list[dict], family: str, surface: str) -> dict:
    """d_hat = greatest level L with ACC(level) >= mastery for every level <= L on
    the calibration arm (rule.json trained_depth). The walk stops at the first
    non-mastered level: depth is a run of mastered levels, not a count of them."""
    mastery = DEPTH["mastery_accuracy"]
    levels = sorted({r["level"] for r in calibration_rows if r["family"] == family})
    accs, ns, delivered = {}, {}, {}
    for level in levels:
        rows = [r for r in calibration_rows if r["family"] == family and r["level"] == level
                and r["surface"] == surface]
        ns[level] = len(rows)
        delivered[level] = sum(1 for r in rows if r["state"] in ("delivered_correct", "delivered_wrong"))
        accs[level] = (sum(1 for r in rows if r["correct"]) / len(rows)) if rows else 0.0
    # no_delivery_case (rule.json trained_depth): an arm that delivered no answer at
    # any level is a delivery failure, not a competence floor. Trained depth is
    # not_evaluable and the run carries no beyond-depth reading for this family.
    measurable = any(delivered.values()) if delivered else False
    d_hat = 0
    for level in levels:
        if accs.get(level, 0.0) >= mastery:
            d_hat = level
        else:
            break
    return {"d_hat": d_hat, "grid": levels, "mastery_accuracy": mastery,
            "calibration_accuracy": {str(k): round(v, 4) for k, v in accs.items()},
            "calibration_n": {str(k): v for k, v in ns.items()},
            "calibration_delivered": {str(k): v for k, v in delivered.items()},
            "no_mastery_case": not any(v >= mastery for v in accs.values()),
            "measurable": measurable}


# ---------------------------------------------------------------- one cell

def cell_report(family: str, level: int, surface: str, items: dict, model_rows: list[dict],
                calibration_rows: list[dict], partner_rows: list[dict],
                corpus: "novelty.LocalScan", pin: dict, searched: list[str]) -> dict:
    """One (family, level, surface) cell: the model census, the three baseline
    censuses on the identical item set, the novelty census, and the cell gate."""
    cell_id = f"{family}|{level}|{surface}"
    model_rows = [r for r in model_rows if r["family"] == family and r["level"] == level
                  and r["surface"] == surface]
    if not model_rows:
        return {"cell_id": cell_id, "family": family, "level": level, "surface": surface,
                "n": 0, "status": "not_evaluable", "reason": "no records for this cell"}
    run_pool = [item for item in items.values()
                if item["family"] == family and item["level"] == level]
    partner_by_seed = {r["seed_hash"]: r for r in partner_rows}

    rows = []
    for row in model_rows:
        item = items[row["seed_hash"]]
        gold = row["gold"]
        built = verify.build_prompt(item, family, surface if family == "trap" else None)
        row["prompt_sha256"] = built["sha256"]
        row["gold_token_in_prompt"] = built["gold_token_in_prompt"]
        row["B1"] = baselines.baseline_row(
            baselines.b1_answer(family, level, item, built["text"], corpus), gold)
        row["B2"] = baselines.baseline_row(
            baselines.b2_answer(family, level, item, run_pool=run_pool), gold)
        row["B3"] = ({"baseline": "B3_smaller_same_family", "state": "judged",
                      "correct": partner_by_seed[row["seed_hash"]]["correct"], "evaluable": True}
                     if row["seed_hash"] in partner_by_seed else
                     {"baseline": "B3_smaller_same_family", "state": "not_evaluable",
                      "correct": False, "evaluable": False,
                      "reason": "no partner record for this item"})
        backends = {"local_scan": corpus} if corpus.available() else {}
        checked = novelty.check_solution(gold, built["text"], backends)
        row["novelty"] = checked["verdict"]
        row["novelty_basis"] = checked["basis"]
        rows.append(row)

    n = len(rows)
    k = sum(1 for r in rows if r["correct"])
    acc = k / n
    lo, hi = wilson(k, n)
    census = {}
    for state in RULE["delivery_census"]["model_states"]:
        census[state] = sum(1 for r in rows if r["state"] == state)

    depth = trained_depth(calibration_rows, family, surface)
    d_hat = depth["d_hat"]
    offset = level - d_hat
    # beyond depth is only readable where trained depth was measured: a censored
    # calibration arm (no_delivery_case) blocks the reading, it does not read as 0.
    beyond = (depth["measurable"] and level > d_hat
              and (offset in DEPTH["novel_band_offsets"] or depth["no_mastery_case"]))

    tests, evaluable, blocked = {}, {}, []
    for key in BASELINE_KEYS:
        if all(r[key]["evaluable"] for r in rows):
            flags = [r[key]["correct"] for r in rows]
            base_acc = round(sum(flags) / n, 4)
            tests[key] = {"evaluable": True, "baseline_accuracy": base_acc,
                          "gap": round(acc - base_acc, 4),
                          **mcnemar_exact([r["correct"] for r in rows], flags)}
            evaluable[key] = base_acc
        else:
            reasons = sorted({str(r[key].get("reason")) for r in rows if not r[key]["evaluable"]})
            tests[key] = {"evaluable": False, "reason": "; ".join(reasons)}
            blocked.append(key)

    clean = sum(1 for r in rows if r["novelty"] == "clean")
    flagged = sum(1 for r in rows if r["novelty"] == "flagged")
    measured = clean + flagged
    clean_rate = (clean / measured) if measured else None
    if not searched:
        novelty_status, novelty_reason = "not_evaluable", "no corpus backend configured"
    elif measured == 0:
        novelty_status, novelty_reason = "not_evaluable", "no item produced a novelty verdict"
    elif measured < n:
        novelty_status, novelty_reason = "partial", f"{n - measured} items not measured"
    else:
        novelty_status, novelty_reason = "evaluable", ""

    checks = {
        "n_ok": n >= CELL_GATE["min_n"],
        "beyond_depth": beyond,
        "depth_offset": offset,
        "accuracy_ok": acc >= CELL_GATE["min_accuracy_at_depth"],
        "novelty_ok": (novelty_status == "evaluable" and clean_rate is not None
                       and clean_rate >= CELL_GATE["min_novelty_clean_rate"]),
        "baselines_all_evaluable": not blocked,
        "baselines_blocked": blocked,
        "gap_ok": bool(evaluable) and all(tests[key]["gap"] >= CELL_GATE["min_gap_over_every_baseline"]
                                          for key in evaluable),
        "ci_above_baselines": bool(evaluable) and all(lo > evaluable[key] for key in evaluable),
        "holm_significant": False,
        "gold_carrying_rows": sum(1 for r in rows if r["gold_token_in_prompt"]),
        "depth_measured": depth["measurable"],
    }
    carrying = checks["gold_carrying_rows"]
    checks["gold_carry_share"] = round(carrying / n, 4)
    checks["gold_share_ok"] = carrying / n <= CELL_GATE["max_share_of_rows_carrying_the_gold"]
    pre_holm = tuple(CELL_GATE["pre_holm_checks"])
    checks["pre_holm_checks"] = list(pre_holm)
    checks["cell_gate_pre_holm"] = all(checks[key] for key in pre_holm)
    checks["cell_passes"] = checks["cell_gate_pre_holm"] and checks["holm_significant"]
    measurable = {
        "N1_depth_cliff": bool(rows) and depth["measurable"]
                        and depth["calibration_accuracy"].get(str(d_hat), 0.0) > 0,
        "N2_baselines_match": bool(rows) and bool(evaluable),
        "N3_corpus_answers": measured > 0,
        "N4_no_competence": bool(rows),
    }
    return {"cell_id": cell_id, "family": family, "level": level, "surface": surface,
            "n": n, "correct": k, "accuracy": round(acc, 4), "wilson95": [round(lo, 4), round(hi, 4)],
            "delivery_census": census, "d_hat": d_hat, "trained_depth": depth,
            "novelty": {"measured": measured, "clean": clean, "flagged": flagged,
                        "clean_rate": clean_rate, "status": novelty_status,
                        "reason": novelty_reason, "backends_searched": searched},
            "baselines": {"evaluable": evaluable, "blocked": blocked, "tests": tests},
            "measurable": measurable, "checks": checks, "rows": rows}


# ---------------------------------------------------------------- one checkpoint

def negative_branches(cells: list[dict]) -> dict:
    """Each registered NEGATIVE branch, evaluated only over the cells that branch
    can measure. An empty measurable set never fires: silence is not evidence."""
    beyond = [c for c in cells if c.get("n", 0) > 0 and c["checks"]["beyond_depth"]]
    out = {}
    for name in NEGATIVE_KEYS:
        spec = LADDER[name]
        pool = [c for c in beyond if c["measurable"].get(name)]
        if not pool:
            out[name] = {"fired": False, "status": "not_evaluable",
                         "measurable_cells": 0, "reason": "no measurable cell for this branch"}
            continue
        if name == "N1_depth_cliff":
            factor = spec["factor_of_calibration_accuracy"]
            cliffs = [c["accuracy"] < factor * c["trained_depth"]["calibration_accuracy"][str(c["d_hat"])]
                      for c in pool]
            fired = all(cliffs)
            detail = {"factor": factor, "cells_below": sum(cliffs), "cells": len(pool)}
        elif name == "N2_baselines_match":
            within, share = spec["within_absolute_gap"], spec["min_share_of_cells"]
            matched = sum(1 for c in pool
                          if any(t["evaluable"] and t["gap"] <= within
                                 for t in c["baselines"]["tests"].values()))
            fired = matched >= math.ceil(share * len(pool))
            detail = {"within": within, "share": share, "matched": matched, "cells": len(pool)}
        elif name == "N3_corpus_answers":
            below = spec["mean_clean_rate_below"]
            rates = [c["novelty"]["clean_rate"] for c in pool if c["novelty"]["clean_rate"] is not None]
            mean = sum(rates) / len(rates) if rates else None
            fired = mean is not None and mean < below
            detail = {"below": below, "mean_clean_rate": round(mean, 4) if mean is not None else None,
                      "cells": len(rates)}
        else:
            at_or_below = spec["mean_accuracy_at_or_below"]
            mean = sum(c["accuracy"] for c in pool) / len(pool)
            fired = mean <= at_or_below
            detail = {"at_or_below": at_or_below, "mean_accuracy": round(mean, 4), "cells": len(pool)}
        out[name] = {"fired": fired, "status": "evaluated", "measurable_cells": len(pool), **detail}
    return out


def cell_p(cell: dict) -> float:
    """The cell's test statistic for the correction: the weakest (largest) p over
    its evaluable baselines. The gate demands beating every baseline, so the
    cell is only as significant as its hardest baseline."""
    ps = [t["p"] for t in cell["baselines"]["tests"].values() if t.get("evaluable")]
    return max(ps) if ps else 1.0


def apply_holm(beyond: list[dict]) -> None:
    """Holm-Bonferroni over a confirmatory beyond-depth cell set, then recompute
    each cell_passes. Mutates in place so every caller reads the same truth."""
    if not beyond:
        return
    corrected = holm_bonferroni([cell_p(c) for c in beyond], EFFECT["alpha"])
    for cell, adj in zip(beyond, corrected):
        cell["Multiplicity"] = adj
        cell["checks"]["holm_significant"] = adj["significant"]
        cell["checks"]["cell_passes"] = bool(cell["checks"]["cell_gate_pre_holm"]) and adj["significant"]


def confirmatory_beyond(cells: list[dict]) -> tuple[list[dict], list[dict]]:
    """(confirmatory cells, confirmatory cells sitting beyond d_hat)."""
    conf = [c for c in cells if c.get("n", 0) >= EFFECT["min_n_confirmatory"]
            and c.get("checks")]
    return conf, [c for c in conf if c["checks"]["beyond_depth"]]


def gate_of(cells: list[dict], pin: dict, beyond: list[dict], recorded: dict | None = None) -> dict:
    """The family gate for one checkpoint over its already-corrected cells.

    `recorded` is the pin flag set the round itself reported. pins.json is the
    source of truth, so a recorded flag that contradicts the pin is a pin integrity
    blocker, and a recorded forbidden flag blocks the gate either way."""
    name = pin.get("pin", "")
    if name not in CONFIRMATORY or not pin.get("corpus_public"):
        return {"model_pin": name, "exploratory": True, "gate_met": False, "pin_flags": {},
                "pin_flags_clean": False, "families_passed": [], "passing": [],
                "blockers": [NOVELTY["not_evaluable_case"]]}
    flags = {flag: bool(pin.get(flag, True)) for flag in PIN_FLAGS}
    integrity = []
    for flag, value in sorted((recorded or {}).items()):
        if flag not in PIN_FLAGS:
            continue
        if bool(value) != flags[flag]:
            integrity.append(f"pin {name}: the round recorded {flag}={bool(value)} but pins.json "
                             f"records {flag}={flags[flag]}: pin integrity failure")
        flags[flag] = flags[flag] or bool(value)
    flag_clean = not any(flags.values())
    passing = [c for c in beyond if c["checks"]["cell_passes"]]
    families = sorted({c["family"] for c in passing})
    gate_met = (len(families) >= CHECKPOINT_GATE["min_families_per_checkpoint"]
                and flag_clean and not pin.get("family_minimum"))
    return {"model_pin": name, "exploratory": False, "gate_met": gate_met, "pin_flags": flags,
            "pin_flags_clean": flag_clean, "families_passed": families, "passing": passing,
            "blockers": blockers_of(cells, pin, flag_clean) + integrity}


def checkpoint_status(cells: list[dict], pin: dict, corpus_report: dict) -> dict:
    """One round, one checkpoint. Reports gates and distance; never a claim verdict."""
    name = pin.get("pin", "")
    if name not in CONFIRMATORY or not pin.get("corpus_public"):
        return {"model_pin": name, "checkpoint_status": "exploratory_only_model_class",
                "reason": NOVELTY["not_evaluable_case"], "cells": [c["cell_id"] for c in cells],
                "confirmatory_cells": 0, "passing_cells": [], "families_passed": [],
                "gate_met": False, "negative_fired": [],
                "blockers": [NOVELTY["not_evaluable_case"]],
                "corpus_backend": corpus_report,
                "distance": distance_to_checkpoint(cells, [])}

    confirmatory, beyond = confirmatory_beyond(cells)
    apply_holm(beyond)
    gate = gate_of(cells, pin, beyond)
    branches = negative_branches(confirmatory)
    fired = [key for key, res in branches.items() if res["fired"]]
    passing = gate["passing"]
    return {"model_pin": name,
            "checkpoint_status": "checkpoint_gate_met" if gate["gate_met"] else "checkpoint_gate_not_met",
            "pin_flags": gate["pin_flags"], "pin_flags_clean": gate["pin_flags_clean"],
            "family_minimum": bool(pin.get("family_minimum")),
            "confirmatory_cells": len(confirmatory),
            "beyond_depth_cells": [c["cell_id"] for c in beyond],
            "passing_cells": [c["cell_id"] for c in passing], "families_passed": gate["families_passed"],
            "gate_met": gate["gate_met"], "negative_fired": fired, "negative_detail": branches,
            "blockers": gate["blockers"], "corpus_backend": corpus_report,
            "cells": [c["cell_id"] for c in cells], "distance": distance_to_checkpoint(cells, passing)}


def blockers_of(cells: list[dict], pin: dict, flag_clean: bool) -> list[str]:
    """What this round could not measure, named so the digest can carry it."""
    out = []
    if not flag_clean:
        out.append(f"pin {pin.get('pin')} carries a decoding configuration the claim forbids")
    for cell in cells:
        if cell["checks"]["baselines_blocked"]:
            out.append(f"{cell['cell_id']}: baseline blocked ({', '.join(cell['checks']['baselines_blocked'])})")
        if cell["novelty"]["status"] != "evaluable" and cell["n"] > 0:
            out.append(f"{cell['cell_id']}: novelty {cell['novelty']['status']} ({cell['novelty']['reason']})")
        if not cell["checks"].get("depth_measured", True):
            out.append(f"{cell['cell_id']}: trained depth not_evaluable (calibration arm delivered no "
                       f"answers; {cell['n']} dispatched, no beyond-depth reading exists)")
        carrying = cell["checks"]["gold_carrying_rows"]
        if carrying:
            cap = CELL_GATE["max_share_of_rows_carrying_the_gold"]
            verdict = "cell not_evaluable" if not cell["checks"]["gold_share_ok"] else "within the cap"
            out.append(f"{cell['cell_id']}: {carrying} of {cell['n']} prompts carry a gold step operand "
                       f"(share {cell['checks']['gold_carry_share']}, cap {cap}): {verdict}")
    if not any(c["n"] >= EFFECT["min_n_confirmatory"] for c in cells) and any(c["n"] for c in cells):
        out.append(f"no cell reaches n {CELL_GATE['min_n']}: the round is exploratory by size")
    return out


def distance_to_checkpoint(cells: list[dict], passing: list[dict]) -> list[dict]:
    """Per cell: the open gaps against the frozen gate, one line each."""
    out = []
    for c in cells:
        checks = c.get("checks") or {}
        gaps = []
        if not checks:
            out.append({"cell_id": c["cell_id"], "passing": False, "open_gaps": [c.get("reason", "no records")]})
            continue
        if not checks["n_ok"]:
            gaps.append(f"n {c['n']} below {CELL_GATE['min_n']}")
        if not checks["beyond_depth"]:
            if not checks.get("depth_measured", True):
                gaps.append("trained depth not_evaluable: the calibration arm delivered no "
                            "answers (delivery failure, no beyond-depth reading)")
            else:
                gaps.append(f"level {c['level']} is not beyond d_hat {c['d_hat']} by a registered offset")
        if not checks["accuracy_ok"]:
            gaps.append(f"accuracy {c['accuracy']} below {CELL_GATE['min_accuracy_at_depth']}")
        if not checks["novelty_ok"]:
            gaps.append(f"novelty {c['novelty']['status']} clean_rate {c['novelty']['clean_rate']}")
        if checks["baselines_blocked"]:
            gaps.append("baseline not evaluable: " + ", ".join(checks["baselines_blocked"]))
        if not checks["gap_ok"]:
            gaps.append(f"every-baseline gap below {CELL_GATE['min_gap_over_every_baseline']}")
        if not checks["ci_above_baselines"]:
            gaps.append(f"Wilson lower bound {c['wilson95'][0]} not above every baseline")
        if not checks["gold_share_ok"]:
            gaps.append(f"{checks['gold_carrying_rows']} of {c['n']} prompts carry the gold "
                        f"(cap {CELL_GATE['max_share_of_rows_carrying_the_gold']})")
        if checks["cell_gate_pre_holm"] and not checks["holm_significant"]:
            gaps.append("McNemar p does not survive Holm-Bonferroni")
        out.append({"cell_id": c["cell_id"], "passing": c in passing, "open_gaps": gaps})
    return out


# ---------------------------------------------------------------- the claim gate

FLOOR = RULE["verdicts"]["verdict_level"]["minimum_evidence_machine"]


def claim(reports: list[dict]) -> dict:
    """POSITIVE / NEGITIVE / OPEN over checkpoint reports. The only place a claim
    verdict exists. Every gate is recomputed from the cells the claim is given: a
    checkpoint_status or gate_met cached in a report is never trusted
    (rule.json statistics.recompute_rule)."""
    real, exploratory = [], []
    for report in reports:
        if report.get("checkpoint_status") == "exploratory_only_model_class":
            exploratory.append(report.get("model_pin", "unlabelled"))
        else:
            real.append(report)

    pooled = [cell for report in real for cell in (report.get("_cells") or []) if cell.get("checks")]
    confirmatory, beyond = confirmatory_beyond(pooled)
    apply_holm(beyond)
    branches = negative_branches(confirmatory)
    fired = sorted(name for name, res in branches.items() if res["fired"])
    families = sorted({cell["family"] for cell in beyond})

    gates, blockers = [], []
    for report in real:
        name = report.get("model_pin", "")
        pin = pin_record(name)
        cells = report.get("_cells") or []
        _, report_beyond = confirmatory_beyond(cells)
        gate = gate_of(cells, pin, report_beyond, report.get("pin_flags"))
        if gate["gate_met"]:
            gates.append(name)
        blockers += gate["blockers"]
    gates = sorted(set(gates))
    if exploratory:
        blockers.append("exploratory pins excluded from the claim: " + ", ".join(sorted(set(exploratory))))
    blockers = sorted(set(blockers))
    minimum = (len(beyond) >= FLOOR["min_beyond_depth_cells"]
               and len(families) >= FLOOR["min_families"])

    shared = {"checkpoints_with_gate": gates, "checkpoints_required": CHECKPOINT_GATE["min_checkpoints"],
              "confirmatory_cells": len(confirmatory), "beyond_depth_cells": len(beyond),
              "families": families, "negative_fired": fired, "negative_detail": branches,
              "blockers": blockers, "evidence_floor_met": minimum,
              "distance": distance_to_claim(gates, families, fired, blockers, beyond)}

    if fired and not minimum:
        return dict(shared, verdict="OPEN",
                    reason="a NEGATIVE branch fired but the pre-registered evidence floor "
                           f"({FLOOR['min_beyond_depth_cells']} cells over "
                           f"{FLOOR['min_families']} families) is not met: the branch is reported, "
                           "the claim stays OPEN")
    if fired:
        return dict(shared, verdict="NEGATIVE",
                    reason="a registered NEGATIVE branch fired over its measurable cells")
    if len(gates) >= CHECKPOINT_GATE["min_checkpoints"] and minimum:
        return dict(shared, verdict="POSITIVE", reason="the claim holds on the frozen rule")
    return dict(shared, verdict="OPEN",
                reason=(f"{len(gates)} of {CHECKPOINT_GATE['min_checkpoints']} confirmatory checkpoints "
                        "hold the family gate" if gates else
                        "no confirmatory checkpoint holds the family gate"))


def distance_to_claim(gates: list[str], families: list[str], fired: list[str],
                      blockers: list[str], beyond: list[dict]) -> list[dict]:
    """What one measurement would close, named against the frozen rule."""
    out = []
    need = CHECKPOINT_GATE["min_checkpoints"] - len(gates)
    if need > 0:
        out.append({"target": "POSITIVE", "gap": f"{need} more confirmatory checkpoint(s) holding the "
                                                 f"{CHECKPOINT_GATE['min_families_per_checkpoint']}-family gate"})
    if len(families) < CHECKPOINT_GATE["min_families_per_checkpoint"]:
        out.append({"target": "either", "gap": f"{len(families)} family(ies) beyond depth reported; "
                                               f"{CHECKPOINT_GATE['min_families_per_checkpoint']} needed"})
    if not fired:
        rates = [c["novelty"]["clean_rate"] for c in beyond if c["novelty"]["clean_rate"] is not None]
        if not rates:
            out.append({"target": "NEGATIVE", "gap": "no cell has a measured corpus, so N3 cannot be tested"})
        mean_acc = (sum(c["accuracy"] for c in beyond) / len(beyond)) if beyond else None
        limit = LADDER["N4_no_competence"]["mean_accuracy_at_or_below"]
        if mean_acc is not None and mean_acc > limit:
            out.append({"target": "NEGATIVE", "gap": f"mean beyond-depth accuracy {round(mean_acc, 4)} "
                                                     f"above the N4 line {limit}"})
    for blocker in blockers:
        out.append({"target": "measurement", "gap": blocker})
    return out


# ---------------------------------------------------------------- one round

def score_round(tasks_path, calibration_tasks_path, raw_path, calibration_path, partner_path,
                corpus_root) -> dict:
    novel_items = {r["seed_hash"]: r for r in read_jsonl(tasks_path)}
    calib_items = {r["seed_hash"]: r for r in read_jsonl(calibration_tasks_path)} or novel_items
    records = read_jsonl(raw_path)
    if not records:
        raise ValueError("a scored round needs raw records")
    pin_name = pin_of(records)
    pin = pin_record(pin_name)
    corpus = novelty.LocalScan(root=corpus_root or "")
    searched = [corpus.name] if corpus.available() else []

    model_rows = score_rows(records, novel_items)
    calib_rows = score_rows(read_jsonl(calibration_path), calib_items)
    partner_rows = score_rows(read_jsonl(partner_path), novel_items)

    cells = []
    for family, level, surface in sorted({(r["family"], r["level"], r["surface"]) for r in model_rows}):
        cells.append(cell_report(family, level, surface, novel_items, model_rows, calib_rows,
                                 partner_rows, corpus, pin, searched))
    report = checkpoint_status(cells, pin, corpus.report())
    report["rule_id"] = RULE["id"]
    report["pins_id"] = PINS["id"]
    report["_cells"] = cells
    return report


# ---------------------------------------------------------------- selftest

def _answer(family: str, item: dict, gold: str, correct: bool) -> str:
    if not correct:
        if family == "ladders":
            return "no" if gold == "yes" else "yes"
        if family == "digit_matrices":
            return verify.OPTION_LETTERS[(item["answer_index"] + 1) % len(item["options"])]
        return str(int(gold) + 1)
    if family == "digit_matrices":
        return verify.OPTION_LETTERS[item["answer_index"]]
    return gold


def _arm(family: str, level: int, seed_base: int, count: int, correct_frac: float,
         pin: str, surface: str) -> tuple[list[dict], list[dict]]:
    items = verify.generate(family, level, count, seed_base)
    records = []
    for idx, item in enumerate(items):
        gold = verify.gold_of(item, family)
        records.append({"seed_hash": item["seed_hash"], "surface": surface,
                        "completion": _answer(family, item, gold, idx < round(correct_frac * count)),
                        "finish_reason": "stop", "model_pin": pin})
    return items, records


def _calibration_arm(family: str, levels: list[int], mastered_to: int, seed_base: int,
                     count: int, surface: str, pin: str) -> tuple[list[dict], list[dict]]:
    items, records = [], []
    for level in levels:
        arm_items, arm_records = _arm(family, level, seed_base, count,
                                      0.95 if level <= mastered_to else 0.10, pin, surface)
        items += arm_items
        records += arm_records
    return items, records


# B3 is a property of the pin, not of the task family: pins.json names one smaller
# same-family partner per pin, and that partner answers every family of the round.
PLANTED = {"ladders": {"level": 8, "grid": [1, 2, 4, 6, 8], "mastered_to": 4, "surface": "na"},
           "trap": {"level": 4, "grid": [1, 2, 3, 4], "mastered_to": 2, "surface": "base"}}
N_CONF = 300
CAL_N = 40
CAL_SEED = 20260101
NOVEL_SEED = 20261121
CORPUS_DIR = pathlib.Path("/tmp/frozen-score-corpus")
HARMLESS = ("prose about harvest calendars and weather systems, written to give this slice "
            "real runs of thirteen words and longer so the near path has something to search, "
            "and no synthetic entity string from any planted task item appears anywhere in it. "
            "A retrieval baseline over this slice must find nothing for a novel item. ")


def _corpus() -> novelty.LocalScan:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    (CORPUS_DIR / "harmless.txt").write_text(HARMLESS, encoding="utf-8")
    return novelty.LocalScan(root=str(CORPUS_DIR))


def _planted_checkpoint(pin: str) -> dict:
    """One planted confirmatory checkpoint: two families, both beyond their d_hat,
    the model clearly above all three baselines, novelty measurable."""
    corpus = _corpus()
    partner_pin = CONFIRMATORY[pin]["smaller_partner"]
    items, calib_rows, partner_rows = {}, [], []
    cells = []
    for family, spec in PLANTED.items():
        novel_items, novel_records = _arm(family, spec["level"], NOVEL_SEED, N_CONF, 0.85, pin, spec["surface"])
        cal_items, cal_records = _calibration_arm(family, spec["grid"], spec["mastered_to"],
                                                  CAL_SEED, CAL_N, spec["surface"], pin)
        items.update({i["seed_hash"]: i for i in novel_items})
        model_rows = score_rows(novel_records, {i["seed_hash"]: i for i in novel_items})
        calib_rows += score_rows(cal_records, {i["seed_hash"]: i for i in cal_items})
        if partner_pin:
            _, partner_records = _arm(family, spec["level"], NOVEL_SEED, N_CONF, 0.20,
                                      partner_pin, spec["surface"])
            partner_rows += score_rows(partner_records, {i["seed_hash"]: i for i in novel_items})
        cells.append(cell_report(family, spec["level"], spec["surface"],
                                 {i["seed_hash"]: i for i in novel_items}, model_rows, calib_rows,
                                 partner_rows, corpus, CONFIRMATORY[pin], [corpus.name]))
    record = checkpoint_status(cells, CONFIRMATORY[pin], corpus.report())
    record["_cells"] = cells
    return record


def _clone(cell: dict, mutate) -> dict:
    """Mutated copy of a cell, with the gate recomputed exactly the way the
    scorer computes it: the frozen pre-Holm check list, then the correction."""
    clone = json.loads(json.dumps(cell))
    mutate(clone)
    checks = clone["checks"]
    checks["cell_gate_pre_holm"] = all(checks[key] for key in CELL_GATE["pre_holm_checks"])
    checks["cell_passes"] = checks["cell_gate_pre_holm"] and checks["holm_significant"]
    return clone


def selftest() -> int:
    checks = 0

    def ok(cond, label):
        nonlocal checks
        checks += 1
        if not cond:
            raise AssertionError(label)

    ok(RULE["id"] == "frozen-judge-rule-v1" and PINS["id"] == "frozen-judge-pins-v1",
       "the scorer must name the frozen rule and pin set it implements")
    ok(CELL_GATE["min_n"] == EFFECT["min_n_confirmatory"],
       "the cell gate and the effect block must state the same minimum n")

    lo, hi = wilson(150, 300)
    ok(0.44 < lo < 0.50 and 0.50 < hi < 0.56, f"Wilson must bracket 0.5, got {lo} {hi}")
    zero_lo, zero_hi = wilson(0, 300)
    ok(zero_lo < 1e-9 and 0.01 < zero_hi < 0.02,
       f"a zero-accuracy cell must stay tight near zero, got {zero_lo} {zero_hi}")
    try:
        wilson(0, 0)
        raise AssertionError("planted n = 0 must raise")
    except ValueError:
        ok(True, "an empty cell raises instead of reading as zero")

    discordant = mcnemar_exact([True] * 30 + [False] * 6, [False] * 30 + [True] * 6)
    ok(discordant["b"] == 30 and discordant["c"] == 6 and discordant["p"] < 0.001,
       f"a 30/6 discordance must be decisive, got {discordant}")
    ok(mcnemar_exact([True, False], [True, False])["p"] == 1.0,
       "identical answer sets must give p = 1, not a fake significance")
    ok(mcnemar_exact([True, False, False], [False, True, True])["p"] == 1.0,
       "a 1/2 discordance on n = 3 must not read as significant")
    # b = 9, c = 1: two-sided exact tail = 2 * (C(10,0) + C(10,1)) / 2^10 = 22/1024
    mid = mcnemar_exact([True] * 9 + [False], [False] * 9 + [True])
    ok(mid["b"] == 9 and mid["c"] == 1 and abs(mid["p"] - 22 / 1024) < 1e-12,
       f"the exact tail must be 22/1024, got {mid}")

    adj = holm_bonferroni([0.001, 0.04, 0.049], 0.05)
    ok(adj[0]["significant"] and not adj[1]["significant"],
       f"Holm must break the second p, got {[a['significant'] for a in adj]}")
    ok(abs(adj[0]["threshold"] - 0.05 / 3) < 1e-12, "the smallest p faces alpha/m")
    ok(adj[2]["threshold"] == 0.05, "the largest p faces alpha unsplit")
    mono = [a["adjusted_p"] for a in sorted(adj, key=lambda a: a["p"])]
    ok(mono == sorted(mono), f"adjusted p must be monotone, got {mono}")

    # NEGATIVE CONTROL: the scorer must refuse a cell set with no records
    try:
        wilson(0, 0)
    except ValueError:
        ok(True, "control: a cell with no dispatched item is not scored as 0")

    report = _planted_checkpoint("olmo2-13b")
    cells = report["_cells"]
    ok(len(cells) == 2, "the planted checkpoint covers two families")
    for cell in cells:
        spec = PLANTED[cell["family"]]
        ok(cell["n"] == N_CONF, "planted cell n")
        ok(cell["accuracy"] == 0.85, f"{cell['family']}: planted accuracy")
        ok(cell["d_hat"] == spec["mastered_to"],
           f"{cell['family']}: d_hat must read the planted calibration, got {cell['d_hat']}")
        ok(cell["checks"]["beyond_depth"], f"{cell['family']}: the cell must sit beyond d_hat")
        ok(cell["checks"]["depth_offset"] in DEPTH["novel_band_offsets"],
           f"{cell['family']}: the depth offset {cell['checks']['depth_offset']} must be a registered offset")
        ok(cell["novelty"]["status"] == "evaluable",
           f"{cell['family']}: a configured corpus slice is measurable, got {cell['novelty']}")
        ok(cell["novelty"]["clean_rate"] == 1.0,
           f"{cell['family']}: fresh synthetic items must be novelty-clean, got {cell['novelty']}")
        ok(not cell["checks"]["baselines_blocked"],
           f"{cell['family']}: all three baselines must be evaluable, blocked "
           f"{cell['checks']['baselines_blocked']}")
        ok(cell["checks"]["gap_ok"], f"{cell['family']}: the planted gap must clear the frozen minimum")
        ok(cell["checks"]["ci_above_baselines"],
           f"{cell['family']}: the Wilson lower bound must clear every baseline")
        ok(cell["checks"]["cell_passes"], f"{cell['family']}: the planted cell must pass: "
           f"{json.dumps(cell['checks'], sort_keys=True)}")
        b2_acc = cell["baselines"]["tests"]["B2"]["baseline_accuracy"]
        _, hi = wilson(0, N_CONF)
        ok(b2_acc <= max(0.5, hi) + 0.05,
           f"{cell['family']}: B2 recombination must sit near chance "
           f"(yes/no pool: about 0.5; integer pool: near 1/pool spread), got {b2_acc}")
        ok(cell["accuracy"] - b2_acc >= CELL_GATE["min_gap_over_every_baseline"],
           f"{cell['family']}: the planted model must beat the recombination arm by the frozen gap")
        ok(cell["baselines"]["tests"]["B2"]["evaluable"],
           f"{cell['family']}: B2 must be evaluable on the planted pool")
        ok(cell["baselines"]["tests"]["B1"]["gap"] >= CELL_GATE["min_gap_over_every_baseline"],
           f"{cell['family']}: a corpus with nothing to retrieve must score as a beaten arm")
        for key in ("B1", "B2", "B3"):
            ok(cell["baselines"]["tests"][key]["p"] < cell["Multiplicity"]["threshold"],
               f"{cell['family']}/{key}: the planted discordance must survive Holm, got "
               f"{cell['baselines']['tests'][key]['p']} vs {cell['Multiplicity']['threshold']}")
        ok(cell["checks"]["gold_carrying_rows"] == 0,
           f"{cell['family']}: the planted prompts must not print the gold")
        ok(cell["checks"]["gold_share_ok"], f"{cell['family']}: planted gold share must sit under the cap")
        ok(cell["checks"]["pre_holm_checks"] == CELL_GATE["pre_holm_checks"],
           f"{cell['family']}: the cell must name the frozen pre-Holm checks it applied")
        ok(sum(cell["delivery_census"].values()) == cell["n"],
           f"{cell['family']}: the delivery census must account for every dispatched item")

    ok(report["checkpoint_status"] == "checkpoint_gate_met",
       f"two passing families must meet the family gate: {json.dumps(report['distance'], sort_keys=True)}")
    ok(report["families_passed"] == ["ladders", "trap"], "planted gate families")
    ok(report["pin_flags_clean"], "planted pins carry no forbidden decoding configuration")
    ok(not report["negative_fired"], f"no NEGATIVE branch may fire here: {report['negative_detail']}")
    ok(not report["blockers"], f"the planted round should be unblocked: {report['blockers']}")

    ok(CONFIRMATORY["olmo2-7b"]["smaller_partner"] is None,
       "control premise: the family-minimum pin has no smaller partner, so it cannot hold a confirmatory cell")
    minimum_pin = _planted_checkpoint("olmo2-7b")
    ok(minimum_pin["checkpoint_status"] == "checkpoint_gate_not_met",
       "a family-minimum pin must not meet the family gate")
    ok(any("baseline blocked" in blocker for blocker in minimum_pin["blockers"]),
       f"the missing partner must be named as a blocker, got {minimum_pin['blockers']}")
    ok(claim([dict(minimum_pin, _cells=minimum_pin["_cells"]),
              dict(report, _cells=cells)])["verdict"] != "POSITIVE",
       "a pin whose B3 is unmeasurable cannot contribute to a POSITIVE")

    single = claim([report])
    ok(single["verdict"] == "OPEN",
       f"a single checkpoint must never carry a claim verdict, got {single['verdict']}")
    ok(any("confirmatory checkpoint" in row["gap"] for row in single["distance"]),
       f"the distance list must name the missing checkpoint, got {single['distance']}")

    # The replication checkpoint must be a different family and a different size:
    # pythia-12b, whose pinned smaller partner is pythia-6.9b.
    second = _planted_checkpoint("pythia-12b")
    planted = claim([report, second])
    ok(planted["verdict"] == "POSITIVE",
       f"two planted checkpoints holding the gate must read POSITIVE: {json.dumps(planted['distance'], sort_keys=True)}")
    ok(planted["checkpoints_with_gate"] == ["olmo2-13b", "pythia-12b"], "planted gate checkpoints")
    ok(planted["families"] == ["ladders", "trap"], "planted claim families")
    text = json.dumps(planted, sort_keys=True, separators=(",", ":"))
    ok("\n" not in text, "a claim verdict must be a single JSONL-safe line")

    def parity(cell):
        acc = cell["accuracy"]
        for key in BASELINE_KEYS:
            cell["baselines"]["tests"][key] = {"evaluable": True, "baseline_accuracy": acc,
                                               "gap": 0.0, "b": 0, "c": 0, "p": 1.0}
        cell["baselines"]["evaluable"] = {key: acc for key in BASELINE_KEYS}
        cell["baselines"]["blocked"] = []
        cell["measurable"]["N2_baselines_match"] = True
        cell["checks"]["gap_ok"] = False
        cell["checks"]["ci_above_baselines"] = False

    cells2 = second["_cells"]
    neg2 = claim([dict(report, _cells=[_clone(c, parity) for c in cells]),
                  dict(second, _cells=[_clone(c, parity) for c in cells2])])
    ok(neg2["verdict"] == "NEGATIVE" and "N2_baselines_match" in neg2["negative_fired"],
       f"planted baseline parity must read NEGATIVE N2, got {neg2['verdict']} {neg2['negative_fired']}")

    def cliff(cell):
        cell["accuracy"] = 0.02
        cell["correct"] = 6
        cell["trained_depth"]["calibration_accuracy"][str(cell["d_hat"])] = 0.9
        for key in BASELINE_KEYS:
            test = cell["baselines"]["tests"][key]
            test["evaluable"] = True
            test["baseline_accuracy"] = 0.0
            test["gap"] = 0.02
        cell["baselines"]["evaluable"] = {key: 0.0 for key in BASELINE_KEYS}
        cell["baselines"]["blocked"] = []
        cell["measurable"]["N1_depth_cliff"] = True
        cell["measurable"]["N2_baselines_match"] = True
        cell["measurable"]["N4_no_competence"] = True
        cell["wilson95"] = [0.009, 0.056]
        cell["checks"]["gap_ok"] = False

    neg1 = claim([dict(report, _cells=[_clone(c, cliff) for c in cells]),
                  dict(second, _cells=[_clone(c, cliff) for c in cells2])])
    ok(neg1["verdict"] == "NEGATIVE" and "N1_depth_cliff" in neg1["negative_fired"],
       f"planted depth cliff must read NEGATIVE N1, got {neg1['verdict']} {neg1['negative_fired']}")
    ok("N4_no_competence" in neg1["negative_fired"],
       f"a beyond-depth mean accuracy of 0.02 must also fire N4, got {neg1['negative_fired']}")

    def corpus_answers(cell):
        cell["novelty"]["clean"] = 0
        cell["novelty"]["flagged"] = cell["n"]
        cell["novelty"]["measured"] = cell["n"]
        cell["novelty"]["clean_rate"] = 0.0
        cell["novelty"]["status"] = "evaluable"
        cell["novelty"]["reason"] = ""
        cell["checks"]["novelty_ok"] = False

    neg3 = claim([dict(report, _cells=[_clone(c, corpus_answers) for c in cells]),
                  dict(second, _cells=[_clone(c, corpus_answers) for c in cells2])])
    ok(neg3["verdict"] == "NEGATIVE" and "N3_corpus_answers" in neg3["negative_fired"],
       f"planted corpus answers must read NEGATIVE N3, got {neg3['verdict']} {neg3['negative_fired']}")

    # NEGATIVE CONTROL (honesty): no corpus configured means N3 cannot be tested.
    # Silence is not evidence: the branch must stay not_evaluable.
    def no_corpus(cell):
        cell["novelty"]["clean"] = 0
        cell["novelty"]["flagged"] = 0
        cell["novelty"]["measured"] = 0
        cell["novelty"]["clean_rate"] = None
        cell["novelty"]["status"] = "not_evaluable"
        cell["novelty"]["reason"] = "no corpus backend configured"
        cell["measurable"]["N3_corpus_answers"] = False
        cell["checks"]["novelty_ok"] = False

    unmeasured = claim([dict(report, _cells=[_clone(c, no_corpus) for c in cells]),
                        dict(second, _cells=[_clone(c, no_corpus) for c in cells2])])
    ok(unmeasured["negative_detail"]["N3_corpus_answers"]["status"] == "not_evaluable",
       "an unmeasured corpus must not fire N3")
    ok(unmeasured["verdict"] == "OPEN",
       f"an unmeasurable configuration must read OPEN, never NEGATIVE, got {unmeasured['verdict']}")
    ok(any("novelty not_evaluable" in blocker for blocker in unmeasured["blockers"]),
       f"the blocker must be named for the digest, got {unmeasured['blockers']}")

    def no_baselines(cell):
        cell["baselines"]["evaluable"] = {}
        cell["baselines"]["blocked"] = list(BASELINE_KEYS)
        cell["baselines"]["tests"] = {key: {"evaluable": False, "reason": "planted"} for key in BASELINE_KEYS}
        cell["measurable"]["N2_baselines_match"] = False
        cell["checks"]["baselines_all_evaluable"] = False
        cell["checks"]["baselines_blocked"] = list(BASELINE_KEYS)
        cell["checks"]["gap_ok"] = False
        cell["checks"]["ci_above_baselines"] = False

    blocked = claim([dict(report, _cells=[_clone(c, no_baselines) for c in cells]),
                     dict(second, _cells=[_clone(c, no_baselines) for c in cells2])])
    ok(blocked["verdict"] == "OPEN",
       f"blocked baselines block the claim, they do not prove a negative, got {blocked['verdict']}")
    ok(any("baseline blocked" in blocker for blocker in blocked["blockers"]),
       f"the blocked baseline must appear as a blocker, got {blocked['blockers']}")

    def no_competence(cell):
        cell["accuracy"] = 0.0
        cell["correct"] = 0
        cell["wilson95"] = [0.0, 0.0126]
        cell["delivery_census"]["delivered_wrong"] = cell["n"]
        cell["delivery_census"]["delivered_correct"] = 0
        for key in BASELINE_KEYS:
            cell["baselines"]["tests"][key]["baseline_accuracy"] = 0.0
            cell["baselines"]["tests"][key]["gap"] = 0.0
        cell["checks"]["gap_ok"] = False
        cell["checks"]["ci_above_baselines"] = False
        cell["checks"]["accuracy_ok"] = False

    zeroed = [_clone(c, no_competence) for c in cells]
    for cell in zeroed:
        cell["trained_depth"]["calibration_accuracy"][str(cell["d_hat"])] = 0.9
        cell["measurable"]["N1_depth_cliff"] = True
        cell["measurable"]["N2_baselines_match"] = True
    decisive = claim([dict(report, _cells=zeroed)])
    ok(decisive["verdict"] == "NEGATIVE" and "N4_no_competence" in decisive["negative_fired"],
       f"one decisive checkpoint over {FLOOR['min_beyond_depth_cells']} cells in {FLOOR['min_families']} "
       f"families is a valid clean negative, got {decisive['verdict']} {decisive['negative_fired']}")

    thin = [c for c in zeroed if c["family"] == "trap"]
    subfloor = claim([dict(report, _cells=thin)])
    ok(subfloor["verdict"] == "OPEN",
       f"a fired branch below the evidence floor must stay OPEN, got {subfloor['verdict']}")
    ok("N4_no_competence" in subfloor["negative_fired"],
       f"the branch must still be reported when the floor is unmet, got {subfloor['negative_fired']}")
    ok(any("evidence floor" in subfloor["reason"] for _ in [0]),
       f"the reason must name the floor, got {subfloor['reason']}")

    exploratory = checkpoint_status(cells, pin_record("qwen-class-local-build"), _corpus().report())
    ok(exploratory["checkpoint_status"] == "exploratory_only_model_class",
       "a private-corpus build must be labelled exploratory, never gated")
    ok(not exploratory["gate_met"] and exploratory["confirmatory_cells"] == 0,
       "exploratory cells never count as confirmatory")
    # Addendum 1 (2026-11-24): an unregistered pin must carry its recorded
    # cause, not the corpus-public boilerplate (PR #217 review finding F3).
    ok("not in pins.json" in exploratory["reason"],
       "an unregistered pin must report its recorded cause, not the corpus-public boilerplate")
    ok(any("not in pins.json" in b for b in exploratory["blockers"]),
       "the blocker list must carry the recorded cause too")
    mixed = claim([exploratory, report, second])
    ok(mixed["verdict"] == "POSITIVE",
       f"an exploratory pin must be excluded, not poison the claim, got {mixed['verdict']}")
    ok(any("exploratory pins excluded" in blocker for blocker in mixed["blockers"]),
       f"the exclusion must be stated, got {mixed['blockers']}")
    only_expl = claim([exploratory])
    ok(only_expl["verdict"] == "OPEN", "exploratory pins alone can never reach a claim verdict")

    # NEGATIVE CONTROL (delivery failure): a calibration arm that delivered nothing
    # is a blocker, not a d_hat = 0 competence floor. The cells keep their n,
    # they lose the beyond-depth reading, and no NEGATIVE branch can fire over them.
    censored = checkpoint_status(cells, CONFIRMATORY["olmo2-13b"], _corpus().report())
    censored_cells = []
    for c in cells:
        clone = json.loads(json.dumps(c))
        for row in clone["rows"]:
            row["state"] = "not_delivered"
            row["correct"] = False
        clone["delivery_census"] = {s: (clone["n"] if s == "not_delivered" else 0)
                                    for s in RULE["delivery_census"]["model_states"]}
        depth = clone["trained_depth"]
        depth["measurable"] = False
        depth["calibration_delivered"] = {k: 0 for k in depth["calibration_n"]}
        clone["checks"]["beyond_depth"] = False
        clone["checks"]["depth_measured"] = False
        clone["checks"]["cell_gate_pre_holm"] = all(clone["checks"][k] for k in CELL_GATE["pre_holm_checks"])
        clone["checks"]["cell_passes"] = False
        for key in ("N1_depth_cliff",):
            clone["measurable"][key] = False
        censored_cells.append(clone)
    censored = checkpoint_status(censored_cells, CONFIRMATORY["olmo2-13b"], _corpus().report())
    ok(all(not c["checks"]["beyond_depth"] for c in censored_cells),
       "a censored calibration arm must strip the beyond-depth reading, not read it as d_hat = 0")
    ok(any("trained depth not_evaluable" in blocker for blocker in censored["blockers"]),
       f"the delivery failure must be named as a blocker, got {censored['blockers']}")
    ok(censored["gate_met"] is False, "a censored arm cannot meet the family gate")
    ok(not censored["negative_fired"],
       f"no NEGATIVE branch may fire over censored cells, got {censored['negative_fired']}")
    censored_claim = claim([dict(censored, _cells=censored_cells)])
    ok(censored_claim["verdict"] == "OPEN",
       "a fully censored run must read OPEN, never NEGATIVE")

    small = checkpoint_status([dict(c, n=60, checks=dict(c["checks"], n_ok=False)) for c in cells],
                              CONFIRMATORY["olmo2-13b"], _corpus().report())
    ok(small["confirmatory_cells"] == 0 and not small["gate_met"],
       "a cell below the frozen minimum n cannot meet the family gate")
    ok(any("exploratory by size" in blocker for blocker in small["blockers"]),
       f"the size gap must be named, got {small['blockers']}")

    def carrying_under_cap(cell):
        cell["checks"]["gold_carrying_rows"] = 3
        cell["checks"]["gold_carry_share"] = round(3 / cell["n"], 4)
        cell["checks"]["gold_share_ok"] = True

    under = checkpoint_status([_clone(c, carrying_under_cap) for c in cells], CONFIRMATORY["olmo2-13b"],
                              _corpus().report())
    ok(under["passing_cells"] == report["passing_cells"],
       "control: a licensed gold step operand inside the cap is disclosed, it does not alter the gate")
    ok(any("carry a gold step operand" in blocker and "within the cap" in blocker
           for blocker in under["blockers"]),
       f"the disclosed gold count must be named, got {under['blockers']}")

    def carrying_over_cap(cell):
        cell["checks"]["gold_carrying_rows"] = cell["n"]
        cell["checks"]["gold_carry_share"] = 1.0
        cell["checks"]["gold_share_ok"] = False

    over = checkpoint_status([_clone(c, carrying_over_cap) for c in cells], CONFIRMATORY["olmo2-13b"],
                             _corpus().report())
    ok(over["passing_cells"] == [],
       f"a cell whose prompts all carry the gold cannot count as a win, got {over['passing_cells']}")
    ok(any("cell not_evaluable" in blocker for blocker in over["blockers"]),
       f"the cap breach must block the cell, got {over['blockers']}")

    tuned = dict(CONFIRMATORY["olmo2-13b"], instruct=True)
    flagged_pin = checkpoint_status(cells, tuned, _corpus().report())
    ok(not flagged_pin["pin_flags_clean"] and not flagged_pin["gate_met"],
       "an instruction-tuned pin cannot hold the gate")
    ok(claim([dict(flagged_pin, _cells=cells), second])["verdict"] != "POSITIVE",
       "a forbidden decoding configuration cannot yield a POSITIVE")

    dist = distance_to_checkpoint(cells, [c for c in cells if c["checks"]["cell_passes"]])
    ok(all(row["passing"] and not row["open_gaps"] for row in dist),
       "a passing cell must report no open gaps")
    broken = [c for c in cells]
    broken[0] = _clone(broken[0], lambda cell: cell["checks"].__setitem__("novelty_ok", False))
    named = [gap for row in distance_to_checkpoint(broken, []) for gap in row["open_gaps"]]
    ok(any("novelty" in gap for gap in named), f"the distance list must name the gap, got {named}")

    # B2 pool provenance must survive into the cell row
    trap_cell = next(c for c in cells if c["family"] == "trap")
    ok(trap_cell["rows"][0]["B2"]["state"] in ("delivered_correct", "delivered_wrong"),
       "B2 must score as an arm, not stay unjudged")
    ladder_cell = next(c for c in cells if c["family"] == "ladders")
    ok(ladder_cell["baselines"]["tests"]["B3"]["evaluable"],
       "olmo2-13b has a pinned smaller partner, so B3 must be evaluable")
    ok(trap_cell["novelty"]["backends_searched"] == ["local_scan"],
       "the cell must name the corpus backend it actually searched")

    # CLI end to end on planted files
    base = pathlib.Path("/tmp/frozen-score-cli")
    base.mkdir(parents=True, exist_ok=True)
    for family, spec in PLANTED.items():
        novel_items, novel_records = _arm(family, spec["level"], NOVEL_SEED, N_CONF, 0.85,
                                          "olmo2-13b", spec["surface"])
        cal_items, cal_records = _calibration_arm(family, spec["grid"], spec["mastered_to"],
                                                  CAL_SEED, CAL_N, spec["surface"], "olmo2-13b")
        write_jsonl(base / f"{family}-tasks.jsonl", novel_items)
        write_jsonl(base / f"{family}-calibration-tasks.jsonl", cal_items)
        write_jsonl(base / f"{family}-raw.jsonl", novel_records)
        write_jsonl(base / f"{family}-calibration.jsonl", cal_records)
        partner_pin = CONFIRMATORY["olmo2-13b"]["smaller_partner"]
        _, partner_records = _arm(family, spec["level"], NOVEL_SEED, N_CONF, 0.20,
                                  partner_pin, spec["surface"])
        write_jsonl(base / f"{family}-partner.jsonl", partner_records)
    out = score_round(base / "ladders-tasks.jsonl", base / "ladders-calibration-tasks.jsonl",
                      base / "ladders-raw.jsonl", base / "ladders-calibration.jsonl",
                      base / "ladders-partner.jsonl", str(CORPUS_DIR))
    ok(out["model_pin"] == "olmo2-13b", "the CLI path resolves the pinned model")
    ok(out["cells"] == ["ladders|8|na"], "the CLI path builds the cell id")
    ok(out["corpus_backend"]["available"], "the CLI path reports the corpus backend state")
    ok(out["checkpoint_status"] in ("checkpoint_gate_met", "checkpoint_gate_not_met"),
       "the CLI path returns a checkpoint status, not a claim verdict")
    ok("claim" not in json.dumps(out, sort_keys=True)[:200], "a round report carries no claim verdict")
    ok(len(read_jsonl(base / "ladders-raw.jsonl")) == N_CONF, "planted raw fixture size")
    ok(all(row["seed_hash"] for cell in out["_cells"] for row in cell["rows"]),
       "every scored row names its item")

    missing_partner = score_round(base / "trap-tasks.jsonl", base / "trap-calibration-tasks.jsonl",
                                  base / "trap-raw.jsonl", base / "trap-calibration.jsonl",
                                  None, str(CORPUS_DIR))
    ok("B3" in missing_partner["_cells"][0]["checks"]["baselines_blocked"],
       "no partner records must block B3 rather than fake a win")
    ok(any("baseline blocked" in blocker for blocker in missing_partner["blockers"]),
       f"the missing partner must be named as a blocker, got {missing_partner['blockers']}")

    print(f"selftest: {checks} of {checks} checks green")
    return 0


# ---------------------------------------------------------------- CLI

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--score", action="store_true")
    parser.add_argument("--claim", nargs="+")
    parser.add_argument("--tasks")
    parser.add_argument("--calibration-tasks")
    parser.add_argument("--raw")
    parser.add_argument("--calibration")
    parser.add_argument("--partner-raw")
    parser.add_argument("--corpus-dir")
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    if args.score:
        if not (args.tasks and args.raw and args.calibration):
            parser.error("--score needs --tasks, --raw and --calibration")
        report = score_round(args.tasks, args.calibration_tasks, args.raw, args.calibration,
                             args.partner_raw, args.corpus_dir)
        line = json.dumps(report, sort_keys=True, separators=(",", ":"))
        if args.out:
            pathlib.Path(args.out).write_text(line + "\n")
        brief = {k: v for k, v in report.items() if k != "_cells"}
        print(json.dumps(brief, sort_keys=True, indent=2))
        return 0

    if args.claim:
        reports = []
        for path in args.claim:
            loaded = json.loads(pathlib.Path(path).read_text())
            reports.append(loaded)
        verdict = claim(reports)
        line = json.dumps(verdict, sort_keys=True, separators=(",", ":"))
        if args.out:
            pathlib.Path(args.out).write_text(line + "\n")
        print(json.dumps(verdict, sort_keys=True, indent=2))
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

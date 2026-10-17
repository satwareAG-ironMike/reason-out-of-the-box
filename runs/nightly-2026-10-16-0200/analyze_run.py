#!/usr/bin/env python3
"""Regenerate every number in runs/nightly-2026-10-16-0200/report.md from artifacts.

This is an independent re-implementation, not a re-run of the instrument: it
rebuilds the 40 prompts from the corpora and re-derives the task hash, recomputes
the scorer, the three a-priori baselines, the exact answering null, the
model-versus-baseline agreement, the trace-versus-restatement bound, the
fixture-arm degeneracy, and the endpoint budget accounting from the archived
artifacts, then confronts each value with the field the instrument wrote. It also
checks every hash environment.json pins against the file actually present. Any
disagreement is reported and, under --check, makes the script exit non-zero
(agent-execution section 5: no result number enters prose unless a deterministic
script regenerates it).

Usage:
  python3 runs/nightly-2026-10-16-0200/analyze_run.py            # full JSON report
  python3 runs/nightly-2026-10-16-0200/analyze_run.py --check    # confrontations only
  python3 runs/nightly-2026-10-16-0200/analyze_run.py --selftest # planted-defect control
Exit codes: 0 clean, 1 confrontation failed, 3 selftest control failed.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import re
import statistics
import sys
from collections import Counter
from math import comb
from pathlib import Path

RUN_DIR = Path(__file__).resolve().parent
REPO = RUN_DIR.parents[1]
LEVELS = (2, 8)
CELLS = [f"{kind}_l{lv}" for lv in LEVELS for kind in ("fixture", "shipped")]
# The manifest stores floats rounded to 4 decimals for readability. Confronting an
# exact recomputation against a rounded claim would report the rounding itself as a
# mismatch, so numeric fields are compared at the precision the manifest declares.
# Integers and strings are compared exactly.
ROUND_DECIMALS = 4
TOL = 0.5 * 10 ** -ROUND_DECIMALS


def close(got, want):
    """Numeric confrontation at the precision the manifest stores the value at."""
    if got is None or want is None or isinstance(got, bool) or isinstance(want, bool):
        return got == want
    return abs(got - want) <= TOL


def load_battery_module():
    """Load the run-directory battery script as a module, so the battery numbers the
    report cites are regenerated in-process rather than read from their own output."""
    import importlib.util
    path = RUN_DIR / "name_channel_audit.py"
    spec = importlib.util.spec_from_file_location("run_battery", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------- independent re-implementations ----------------

def adjacency(facts):
    out: dict = {}
    for s, _, t in facts:
        out.setdefault(s, []).append(t)
    return out


def bfs_path(facts, src, tgt):
    """Shortest path by plain BFS, written independently of the generator."""
    nxt = adjacency(facts)
    if src == tgt:
        return [src]
    seen = {src}
    frontier = [[src]]
    while frontier:
        nxt_frontier = []
        for path in frontier:
            for nb in nxt.get(path[-1], ()):
                if nb in seen:
                    continue
                seen.add(nb)
                p = path + [nb]
                if nb == tgt:
                    return p
                nxt_frontier.append(p)
        frontier = nxt_frontier
    return None


def baselines(items):
    """The three a-priori baselines, re-derived from the item content."""
    gold = [it["answer"] for it in items]
    maj = Counter(gold).most_common(1)[0][0]
    direct, sig = [], []
    for it in items:
        qs, _, qt = it["query"]
        direct.append("yes" if any(s == qs and t == qt for s, _, t in it["facts"]) else "no")
        is_target = any(t == qt for _, _, t in it["facts"])
        outdeg_zero = not adjacency(it["facts"]).get(qt)
        sig.append("yes" if (is_target and outdeg_zero) else "no")
    return {"B_majority": [maj] * len(items), "B_direct": direct, "B_leak_sig": sig}


def balanced_accuracy(preds, golds):
    classes = sorted(set(golds))
    per = []
    for c in classes:
        tot = sum(1 for g in golds if g == c)
        hit = sum(1 for p, g in zip(preds, golds) if g == c and p == c)
        per.append(hit / tot)
    return sum(per) / len(per)


def exact_null_ba(n_yes, n_no):
    """Exact BA distribution of every answer pattern under fair-coin answering."""
    n = n_yes + n_no
    vals = []
    for bits in itertools.product((0, 1), repeat=n):
        preds = ["yes" if b else "no" for b in bits]
        golds = ["yes"] * n_yes + ["no"] * n_no
        vals.append(balanced_accuracy(preds, golds))
    return vals


def p_at_least(vals, observed):
    return sum(1 for v in vals if v >= observed - 1e-12) / len(vals)


def exact_null_ba_label_permutation(preds, golds):
    """Exact BA distribution of the fixed predictions under the label-permutation null:
    every distinct reassignment of the gold label multiset to the items, enumerated
    exactly (C(n, n_yes) assignments). It holds the model's answers fixed and scrambles
    which item each answer was for, so it credits the model with the correct number of
    yes answers and asks only whether their placement is lucky. For a perfect cell that
    makes it the more conservative of the two nulls (1/C(10,5) = 1/252 against 1/1024 for
    fair-coin answering), and the two do not order uniformly at every threshold: at BA
    0.75 the fair-coin null is the smaller one. Neither is used to set the verdict; both
    are reported so the reader can see the claim survives either null."""
    n = len(golds)
    n_yes = golds.count("yes")
    vals = []
    for yes_positions in itertools.combinations(range(n), n_yes):
        pos = set(yes_positions)
        perm_golds = ["yes" if i in pos else "no" for i in range(n)]
        vals.append(balanced_accuracy(preds, perm_golds))
    return vals


def quantile(vals, q):
    s = sorted(vals)
    idx = max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))
    return s[idx]


def restatement_chars(item):
    """Characters a verbatim restatement of every fact would need (lower bound)."""
    return sum(len(s) + len(t) + len(rel) + 4 for s, rel, t in item["facts"])


INSTRUCTION = "Reply with exactly one word: yes or no."


def build_prompt(item):
    """Rebuild the prompt for an item, independently of the instrument.

    Facts block, then the question, then the one fixed instruction. The
    answer-bearing fields (`answer`, `chain_len`) must never appear; the guard
    here is written separately from the instrument's guard on purpose.
    """
    qs, rel, qt = item["query"]
    lines = [f"{i}. {s} {r} {t}" for i, (s, r, t) in enumerate(item["facts"], 1)]
    block = "Facts:\n" + "\n".join(lines) + "\n\n" + f"Question: Does {qs} {rel} {qt}?"
    for banned in ("answer", "chain_len"):
        if banned in block:
            raise RuntimeError(f"leak guard: {banned!r} reached the rebuilt prompt")
    return block + "\n\n" + INSTRUCTION


def prompt_hash(prompts):
    """The published task-contract hash: the ordered prompts joined by a control
    character that cannot appear in a prompt, then sha256."""
    return hashlib.sha256("\n\x1f\n".join(prompts).encode()).hexdigest()


# ---------------- artifact loading ----------------

def load_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_items(kind, level):
    if kind == "fixture":
        return load_jsonl(REPO / "generators" / "fixtures" / f"issue67_prefix_l{level}.jsonl")
    return load_jsonl(REPO / "items" / "ladders" / f"l{level}.jsonl")


# The corpora the connectivity claim is made about. The gate audits l1 too, but l1 is a
# lookup control and is not ladder-depth evidence, so it is not part of this claim.
CORPUS_LEVELS_FOR_CONNECTIVITY = {"shipped": (2, 4, 6, 8), "fixture": (2, 8)}


def component_map(facts):
    """Connected components of the undirected fact graph, written independently of the
    battery script. Components are not stored in the items, so any connectivity claim has
    to derive them."""
    adj: dict = {}
    for s, _, t in facts:
        adj.setdefault(s, set()).add(t)
        adj.setdefault(t, set()).add(s)
    comp_id: dict = {}
    n_comp = 0
    for start in adj:
        if start in comp_id:
            continue
        n_comp += 1
        stack = [start]
        while stack:
            node = stack.pop()
            if node in comp_id:
                continue
            comp_id[node] = n_comp
            stack.extend(adj[node] - set(comp_id))
    return n_comp, comp_id


def analyze():
    man = json.loads((RUN_DIR / "probe_manifest.json").read_text(encoding="utf-8"))
    recs = load_jsonl(RUN_DIR / "probe_raw.jsonl")
    attempts = json.loads((RUN_DIR / "attempts.json").read_text(encoding="utf-8"))
    out: dict = {"run_id": man["run_id"], "mismatches": []}

    def note_mismatch(what, claimed, recomputed):
        out["mismatches"].append({"field": what, "claimed": claimed, "recomputed": recomputed})

    # 1. artifact integrity
    out["artifact_hashes"] = {
        name: sha256(RUN_DIR / name)
        for name in ("probe_raw.jsonl", "probe_manifest.json", "calibration.json", "attempts.json")}
    for name, claimed in man["artifact_hashes"].items():
        if out["artifact_hashes"][name] != claimed:
            note_mismatch(f"artifact_hashes[{name}]", claimed, out["artifact_hashes"][name])

    # 1b. pinned-environment confrontation: every hash environment.json declares
    # must equal the file actually present, so the report cannot be read against a
    # different corpus, instrument, or artifact set than the one the run used
    env = json.loads((RUN_DIR / "environment.json").read_text(encoding="utf-8"))
    out["environment_confrontation"] = {}
    for group, base in (("run_artifacts", RUN_DIR), ("audit_artifacts", RUN_DIR),
                        ("instruments", REPO), ("corpora", REPO), ("fixtures", REPO)):
        rows = {}
        for name, claimed in env["sha256"][group].items():
            got = sha256(base / name)
            rows[name] = got == claimed
            if got != claimed:
                note_mismatch(f"environment.sha256.{group}[{name}]", claimed, got)
        out["environment_confrontation"][group] = rows
    if env["instrument_commit"] != man["commit"]:
        note_mismatch("environment.instrument_commit", man["commit"], env["instrument_commit"])

    # 2. per-cell recomputation and confrontation
    out["cells"] = {}
    for cell in CELLS:
        kind, level = cell.split("_l")
        level = int(level)
        cell_recs = [r for r in recs if r["cell"] == cell]
        items = load_items(kind, level)
        by_seed = {it["seed"]: it for it in items}
        missing = [r["seed"] for r in cell_recs if r["seed"] not in by_seed]
        if missing:
            note_mismatch(f"{cell}:seeds_not_in_corpus", None, missing)
        cell_items = [by_seed[r["seed"]] for r in cell_recs if r["seed"] in by_seed]
        golds = [it["answer"] for it in cell_items]
        preds = [r["model_answer"] for r in cell_recs]
        base = baselines(cell_items)
        valid = [i for i, r in enumerate(cell_recs) if r["valid"]]
        n_yes, n_no = golds.count("yes"), golds.count("no")
        null_full = exact_null_ba(n_yes, n_no)
        golds_v = [golds[i] for i in valid]
        preds_v = [preds[i] for i in valid]
        null_v = exact_null_ba(golds_v.count("yes"), golds_v.count("no")) if valid else None
        # secondary null: fixed answers, gold labels permuted over all C(n, n_yes)
        # distinct assignments. More conservative than fair-coin answering for a perfect
        # cell. Reported, never used for the verdict.
        null_perm = exact_null_ba_label_permutation(preds, golds)
        agree = {
            "model_vs_majority": sum(1 for p, q in zip(preds, base["B_majority"]) if p == q) / len(preds),
            "model_vs_direct": sum(1 for p, q in zip(preds, base["B_direct"]) if p == q) / len(preds),
            "model_vs_leak_sig": sum(1 for p, q in zip(preds, base["B_leak_sig"]) if p == q) / len(preds),
            "leak_sig_vs_gold": sum(1 for q, g in zip(base["B_leak_sig"], golds) if q == g) / len(golds),
            "direct_vs_gold": sum(1 for q, g in zip(base["B_direct"], golds) if q == g) / len(golds),
        }
        facts = [len(it["facts"]) for it in cell_items]
        ratios = [r["reasoning_chars"] / restatement_chars(it) for r, it in zip(cell_recs, cell_items)]
        named_yes = [r["process"]["named_fraction"] for r in cell_recs if r["gold"] == "yes"]
        out["cells"][cell] = {
            "n": len(cell_recs),
            "valid": len(valid),
            "gold_yes": n_yes,
            "gold_no": n_no,
            "accuracy_on_all": sum(1 for p, g in zip(preds, golds) if p == g) / len(preds),
            "accuracy_on_valid": (sum(1 for i in valid if preds[i] == golds[i]) / len(valid)) if valid else None,
            "balanced_accuracy_on_all": balanced_accuracy(preds, golds),
            "balanced_accuracy_on_valid": balanced_accuracy(preds_v, golds_v) if valid else None,
            "baselines_balanced": {k: balanced_accuracy(v, golds) for k, v in base.items()},
            "agreement": {k: round(v, 4) for k, v in agree.items()},
            "p_ba_at_least_observed_full": p_at_least(null_full, balanced_accuracy(preds, golds)),
            "p_ba_at_least_observed_valid": (p_at_least(null_v, balanced_accuracy(preds_v, golds_v))
                                             if null_v else None),
            "null_ba_full": {"n": len(cell_recs), "mean": sum(null_full) / len(null_full),
                             "p95": quantile(null_full, 0.95), "max": max(null_full),
                             "support_size": len(null_full)},
            "label_permutation_null": {
                "support_size": len(null_perm),
                "p95": quantile(null_perm, 0.95),
                "max": max(null_perm),
                "p_ba_at_least_observed": p_at_least(null_perm, balanced_accuracy(preds, golds)),
            },
            "mean_completion_tokens": sum(r["completion_tokens"] or 0 for r in cell_recs) / len(cell_recs),
            "mean_trace_chars": sum(r["reasoning_chars"] for r in cell_recs) / len(cell_recs),
            "mean_n_facts": sum(facts) / len(facts),
            "min_n_facts": min(facts),
            "max_n_facts": max(facts),
            "mean_trace_over_restatement": sum(ratios) / len(ratios),
            "items_trace_over_restatement": sum(1 for x in ratios if x >= 1.0),
            "named_fraction_on_gold_yes": [x for x in named_yes],
            "named_fraction_mean": sum((r["process"]["named_fraction"] or 0) for r in cell_recs) / len(cell_recs),
            "gold_yes_items_naming_all_intermediates": sum(1 for x in named_yes if x == 1.0),
            "gold_yes_items": len(named_yes),
            "latency_mean_s": sum(r["latency_s"] for r in cell_recs) / len(cell_recs),
            "latency_max_s": max(r["latency_s"] for r in cell_recs),
        }
        claimed = man["cells"][cell]
        for field in ("n", "valid", "gold_yes", "gold_no", "accuracy_on_all", "accuracy_on_valid",
                      "balanced_accuracy_on_all", "balanced_accuracy_on_valid",
                      "p_ba_at_least_observed_full", "p_ba_at_least_observed_valid",
                      "mean_completion_tokens", "mean_trace_chars"):
            got, want = out["cells"][cell][field], claimed.get(field)
            if not close(got, want):
                note_mismatch(f"{cell}.{field}", want, got)
        for key in ("B_majority", "B_direct", "B_leak_sig"):
            got, want = out["cells"][cell]["baselines_balanced"][key], claimed["baselines_balanced"][key]
            if not close(got, want):
                note_mismatch(f"{cell}.baselines_balanced[{key}]", want, got)
        # the instrument's *_agreement fields measure baseline-versus-gold, not
        # model-versus-baseline; confront them against the quantity they really are
        if not close(out["cells"][cell]["agreement"]["leak_sig_vs_gold"], claimed["leak_sig_agreement"]):
            note_mismatch(f"{cell}.leak_sig_agreement(baseline_vs_gold)", claimed["leak_sig_agreement"],
                          out["cells"][cell]["agreement"]["leak_sig_vs_gold"])
        if not close(out["cells"][cell]["agreement"]["direct_vs_gold"], claimed["direct_agreement"]):
            note_mismatch(f"{cell}.direct_agreement(baseline_vs_gold)", claimed["direct_agreement"],
                          out["cells"][cell]["agreement"]["direct_vs_gold"])
        if not close(out["cells"][cell]["null_ba_full"]["p95"], claimed["null_ba_full"]["p95"]):
            note_mismatch(f"{cell}.null_ba_full.p95", claimed["null_ba_full"]["p95"],
                          out["cells"][cell]["null_ba_full"]["p95"])
        if not close(out["cells"][cell]["named_fraction_mean"], claimed["named_fraction_mean"]):
            note_mismatch(f"{cell}.named_fraction_mean", claimed["named_fraction_mean"],
                          out["cells"][cell]["named_fraction_mean"])
        if out["cells"][cell]["null_ba_full"]["support_size"] != claimed["null_ba_full"]["support_size"]:
            note_mismatch(f"{cell}.null_ba_full.support_size", claimed["null_ba_full"]["support_size"],
                          out["cells"][cell]["null_ba_full"]["support_size"])

    # 3. fixture-arm degeneracy: can the shortcut arm discriminate at all?
    out["fixture_degeneracy"] = {}
    for lv in LEVELS:
        items = load_items("fixture", lv)
        base = baselines(items)
        golds = [it["answer"] for it in items]
        same = sum(1 for q, g in zip(base["B_leak_sig"], golds) if q == g)
        out["fixture_degeneracy"][f"l{lv}"] = {
            "n": len(items), "leak_sig_equals_gold": same,
            "share": same / len(items),
            "read": ("the shortcut signature and the gold label agree on every item, so this arm "
                     "cannot separate shortcut answering from traversal answering"
                     if same == len(items) else "the arm can discriminate"),
        }

    # 4. verdict recomputation under the pre-registered rule
    def strong(cell):
        s = out["cells"][cell]
        return (s["balanced_accuracy_on_valid"] is not None and s["balanced_accuracy_on_valid"] >= 0.75
                and s["p_ba_at_least_observed_valid"] is not None
                and s["p_ba_at_least_observed_valid"] < 0.05
                and s["p_ba_at_least_observed_full"] < 0.05)
    fixture_strong = all(strong(f"fixture_l{lv}") for lv in LEVELS)
    shipped_strong = all(strong(f"shipped_l{lv}") for lv in LEVELS)
    verdict = ("inconclusive_no_capability" if not fixture_strong
               else "traversal_consistent" if shipped_strong else "shortcut_consistent")
    out["verdict_recomputed"] = verdict
    out["strong_cells"] = {c: strong(c) for c in CELLS}
    if verdict != man["verdict"]:
        note_mismatch("verdict", man["verdict"], verdict)

    # 5. budget accounting across invocations
    tot = attempts["totals"]
    calls = sum(a["endpoint_calls"] for a in attempts["attempts"])
    out["budget_recomputed"] = {
        "endpoint_calls_all_attempts": calls,
        "items_answered_all_attempts": sum(a["items_answered"] for a in attempts["attempts"]),
        "failed_attempts_all_attempts": sum(a["failed_attempts"] for a in attempts["attempts"]),
        "items_reused": sum(a["items_reused"] for a in attempts["attempts"]),
        "experimental_prompts": man["budget"]["experimental_prompts"],
        "over_cap_calls": calls - man["budget"]["experimental_prompts"],
        "calibration_calls": man["budget"]["calibration_calls_used"],
    }
    if calls != tot["endpoint_calls_all_attempts"]:
        note_mismatch("attempts.totals.endpoint_calls_all_attempts", tot["endpoint_calls_all_attempts"], calls)
    if calls - man["budget"]["experimental_prompts"] != tot["over_cap_calls"]:
        note_mismatch("attempts.totals.over_cap_calls", tot["over_cap_calls"],
                      calls - man["budget"]["experimental_prompts"])
    last = attempts["attempts"][-1]
    if last["endpoint_calls"] != man["budget"]["endpoint_attempts"]:
        note_mismatch("budget.endpoint_attempts(final invocation)", man["budget"]["endpoint_attempts"],
                      last["endpoint_calls"])
    if last["items_reused"] != man["budget"]["items_reused_from_prior_attempt"]:
        note_mismatch("budget.items_reused_from_prior_attempt",
                      man["budget"]["items_reused_from_prior_attempt"], last["items_reused"])
    if sum(1 for r in recs if r["finish_reason"] == "client_error") != man["budget"]["items_recorded_as_client_error"]:
        note_mismatch("budget.items_recorded_as_client_error",
                      man["budget"]["items_recorded_as_client_error"],
                      sum(1 for r in recs if r["finish_reason"] == "client_error"))

    # 6. prompt-design invariance: rebuild every prompt from the corpus, compare it
    # to the hash the run recorded, then re-derive the whole task hash
    cell_order = list(dict.fromkeys(r["cell"] for r in recs))
    rebuilt: list[str] = []
    rebuilt_ok = 0
    for cell in cell_order:
        kind, level = cell.split("_l")
        by_seed = {it["seed"]: it for it in load_items(kind, int(level))}
        for rec in [r for r in recs if r["cell"] == cell]:
            if rec["seed"] not in by_seed:
                note_mismatch(f"prompt_rebuild[{cell}:{rec['seed']}]", None, "seed not in corpus")
                continue
            prompt = build_prompt(by_seed[rec["seed"]])
            rebuilt.append(prompt)
            got = hashlib.sha256(prompt.encode()).hexdigest()
            if got == rec["prompt_sha256"]:
                rebuilt_ok += 1
            else:
                note_mismatch(f"prompt_sha256[{cell}:{rec['seed']}]", rec["prompt_sha256"], got)
    out["prompt_design"] = {
        "cell_order": cell_order,
        "prompts_rebuilt": len(rebuilt),
        "records_matching_their_rebuilt_prompt": rebuilt_ok,
        "prompt_hash_manifest": man["prompt_hash"],
        "prompt_hash_rebuilt": prompt_hash(rebuilt),
        "records_reused_from_prior_invocation": sum(1 for r in recs if r["resumed"]),
        "records_with_extra_attempts": sum(1 for r in recs if r["attempts"] > 1),
    }
    if prompt_hash(rebuilt) != man["prompt_hash"]:
        note_mismatch("prompt_hash", man["prompt_hash"], prompt_hash(rebuilt))
    if rebuilt_ok != len(recs):
        note_mismatch("prompt_design.records_matching", len(recs), rebuilt_ok)

    # 7. audit confrontation: the shipped-corpus gate numbers the report cites
    audit = json.loads((RUN_DIR / "audit_shipped.json").read_text(encoding="utf-8"))
    out["audit_shipped"] = {
        f"l{lv['level']}": {"gate_status": lv["gate_status"],
                            "best_hypothesis_accuracy": lv["best_hypothesis_accuracy"],
                            "min_detectable_accuracy": lv["min_detectable_accuracy"],
                            "constant_features": len(lv["constant_features"]),
                            "features_total": len(lv["single_feature_accuracy"]),
                            "n": lv["n"]}
        for lv in audit["levels"] if lv["level"] in LEVELS}
    fixtures_audit = json.loads((RUN_DIR / "audit_fixtures.json").read_text(encoding="utf-8"))
    out["audit_fixtures"] = {
        f"l{lv['level']}": {"gate_status": lv["gate_status"],
                            "best_hypothesis": lv["best_hypothesis"],
                            "best_hypothesis_accuracy": lv["best_hypothesis_accuracy"],
                            "permutation_p_value": lv["permutation_p_value"],
                            "min_detectable_accuracy": lv["min_detectable_accuracy"],
                            "n": lv["n"]}
        for lv in fixtures_audit["levels"] if lv["level"] in LEVELS}
    for lv in LEVELS:
        if out["audit_shipped"][f"l{lv}"]["gate_status"] != "no_leak":
            note_mismatch(f"audit_shipped l{lv} gate_status", "no_leak",
                          out["audit_shipped"][f"l{lv}"]["gate_status"])
        if out["audit_fixtures"][f"l{lv}"]["gate_status"] != "leak":
            note_mismatch(f"audit_fixtures l{lv} gate_status", "leak",
                          out["audit_fixtures"][f"l{lv}"]["gate_status"])

    # 7b. battery confrontation: re-run the name/structural battery in-process and
    # compare every scored feature against the pinned battery JSON the report cites.
    # This is what makes the connectivity finding citable: the battery script is the
    # named generator of those numbers, and the pinned copy must match a fresh run.
    battery = load_battery_module()
    out["battery"] = {}
    for kind in ("shipped", "fixtures"):
        stored_path = RUN_DIR / f"name_channel_audit_{kind}.json"
        if not stored_path.exists():
            note_mismatch(f"battery[{kind}]", "pinned battery JSON present", "missing")
            continue
        stored = json.loads(stored_path.read_text(encoding="utf-8"))
        fresh = battery.audit(kind)
        if json.dumps(fresh, sort_keys=True) != json.dumps(stored, sort_keys=True):
            note_mismatch(f"battery[{kind}].full_report", "stored battery report", "recomputed battery differs")
        out["battery"][kind] = {
            "any_traversal_free_leak": fresh["any_traversal_free_leak"],
            "any_structural_shortcut": fresh["any_structural_shortcut"],
            "levels": {f"l{lv['level']}": {
                "n": lv["n"],
                "gold_yes": lv["gold_yes"],
                "bonferroni_threshold": lv["bonferroni_threshold"],
                "flagged_traversal_free": lv["flagged_traversal_free"],
                "structural_reproduces_label": lv["structural_reproduces_label"],
                "same_component_accuracy": lv["structural"]["same_component"]["accuracy"],
                "same_component_p_value": lv["structural"]["same_component"]["p_value"],
                "max_traversal_free_accuracy": lv["max_traversal_free_accuracy"],
                "features_total": lv["features_total"],
            } for lv in fresh["levels"]},
            "exit_code": battery.verdict(fresh),
        }
        for lv in fresh["levels"]:
            key = f"battery[{kind}] l{lv['level']}"
            if lv["flagged_traversal_free"]:
                note_mismatch(f"{key}.flagged_traversal_free", [], lv["flagged_traversal_free"])
            if lv["structural"]["same_component"]["accuracy"] != 1.0:
                note_mismatch(f"{key}.same_component_accuracy", 1.0,
                              lv["structural"]["same_component"]["accuracy"])
            if "same_component" not in lv["structural_reproduces_label"]:
                note_mismatch(f"{key}.structural_reproduces_label", ["same_component"],
                              lv["structural_reproduces_label"])

    # 8. entailment structure of both arms, over the whole corpora and not only the 10
    # probed items. This is what pins down which shortcut the fixture arm actually carries:
    # the queried pair is never a stated fact anywhere in either arm, so the fixture leak is
    # the target-role signature (query target is a fact target and has out-degree zero),
    # which reproduces the label exactly on the pre-fix items and is constant on the repaired
    # ones. On the repaired corpus the audited shortcut class is at chance, so a correct
    # answer requires identifying path membership.
    out["entailment"] = {}
    for kind in ("shipped", "fixture"):
        for lv in CORPUS_LEVELS_FOR_CONNECTIVITY[kind]:
            items = load_items(kind, lv)
            base = baselines(items)
            golds = [it["answer"] for it in items]
            direct_hits = sum(1 for it in items
                              if any(s == it["query"][0] and t == it["query"][2]
                                     for s, _, t in it["facts"]))
            sig_acc = sum(1 for q, g in zip(base["B_leak_sig"], golds) if q == g) / len(golds)
            # the two conjuncts of the pre-fix signature, scored separately: on the pre-fix
            # items each one alone reproduces the label, on the repaired items each one is
            # constant true, which is why the conjunction is constant there too.
            conjuncts = {}
            for cname, pred in (("query_target_is_a_fact_target",
                                 [any(t == it["query"][2] for _, _, t in it["facts"])
                                  for it in items]),
                                ("query_target_has_no_outgoing_fact",
                                 [not adjacency(it["facts"]).get(it["query"][2]) for it in items])):
                conjuncts[cname] = {
                    "fraction_true": sum(1 for p in pred if p) / len(pred),
                    "accuracy_full_corpus": sum(1 for p, g in zip(pred, golds)
                                                if (p and g == "yes") or (not p and g == "no"))
                                         / len(golds),
                }
            row = {
                "n": len(items),
                "gold_yes": sum(1 for g in golds if g == "yes"),
                "query_pair_is_a_stated_fact_items": direct_hits,
                "direct_fact_constant": len(set(base["B_direct"])) == 1,
                "leak_signature_constant": len(set(base["B_leak_sig"])) == 1,
                "leak_signature_accuracy_full_corpus": sig_acc,
                "signature_conjuncts": conjuncts,
            }
            if kind == "shipped":
                cell_key = f"shipped_l{lv}"
                if cell_key in out["cells"]:
                    row["model_balanced_accuracy_probe"] = out["cells"][cell_key]["balanced_accuracy_on_all"]
                row["read"] = ("no queried pair is a stated fact in this arm, and the pre-fix "
                               "signature is constant here, so the model's answers are not "
                               "produced by either shortcut")
            else:
                row["read"] = ("no queried pair is a stated fact here either; the arm's shortcut "
                               "is the target-role signature, which reproduces the label exactly")
            out["entailment"][f"{kind}_l{lv}"] = row
            if direct_hits != 0:
                note_mismatch(f"entailment[{kind}_l{lv}].query_pair_is_a_stated_fact", 0, direct_hits)
            if kind == "shipped" and not row["leak_signature_constant"]:
                note_mismatch(f"entailment[shipped_l{lv}].leak_signature_constant", True, False)
            if kind == "fixture" and sig_acc != 1.0:
                note_mismatch(f"entailment[fixture_l{lv}].leak_signature_accuracy", 1.0, sig_acc)
            for cname, c in row["signature_conjuncts"].items():
                if kind == "fixture" and c["accuracy_full_corpus"] != 1.0:
                    note_mismatch(f"entailment[fixture_l{lv}].{cname}.accuracy", 1.0,
                                  c["accuracy_full_corpus"])
                if kind == "shipped" and c["fraction_true"] != 1.0:
                    note_mismatch(f"entailment[shipped_l{lv}].{cname}.fraction_true", 1.0,
                                  c["fraction_true"])

    # 9. connectivity statistics over the full corpora: the numbers behind the claim that
    # undirected component membership determines the label. Components are not stored in
    # the items, so they are derived here from the fact graph.
    out["connectivity"] = {}
    for kind in ("shipped", "fixture"):
        for lv in CORPUS_LEVELS_FOR_CONNECTIVITY[kind]:
            items = load_items(kind, lv)
            counts = []
            diff_items = 0
            gold_yes_in_different_component = 0
            hits = 0
            for it in items:
                n_comp, comp_id = component_map(it["facts"])
                counts.append(n_comp)
                src, tgt = it["query"][0], it["query"][2]
                same = comp_id.get(src) == comp_id.get(tgt)
                if not same:
                    diff_items += 1
                    if it["answer"] == "yes":
                        gold_yes_in_different_component += 1
                if same == (it["answer"] == "yes"):
                    hits += 1
            out["connectivity"][f"{kind}_l{lv}"] = {
                "n": len(items),
                "components_min": min(counts),
                "components_max": max(counts),
                "components_mean": sum(counts) / len(counts),
                "items_with_endpoints_in_different_components": diff_items,
                "gold_yes_items_with_endpoints_in_different_components": gold_yes_in_different_component,
                "same_component_accuracy_full_corpus": hits / len(items),
            }
        for lv in CORPUS_LEVELS_FOR_CONNECTIVITY[kind]:
            stats = out["connectivity"][f"{kind}_l{lv}"]
            if stats["same_component_accuracy_full_corpus"] != 1.0:
                note_mismatch(f"connectivity[{kind}_l{lv}].same_component_accuracy", 1.0,
                              stats["same_component_accuracy_full_corpus"])
            if stats["gold_yes_items_with_endpoints_in_different_components"] != 0:
                note_mismatch(f"connectivity[{kind}_l{lv}].gold_yes_in_different_component", 0,
                              stats["gold_yes_items_with_endpoints_in_different_components"])

    # 10. matched-pair structure at item level. The arms are paired by seed only: the
    # instrument's design says "same seed, same level, the only difference is the
    # construction", and the report must not claim more than that. What a pair actually
    # shares is recomputed here for the 10 probed pairs of each level, so the report's
    # description of the design is itself a checked claim.
    out["pairing"] = {}
    for lv in LEVELS:
        fixture_seeds = {r["seed"] for r in recs if r["cell"] == f"fixture_l{lv}"}
        shipped_seeds = {r["seed"] for r in recs if r["cell"] == f"shipped_l{lv}"}
        if fixture_seeds != shipped_seeds:
            note_mismatch(f"pairing l{lv}.seeds_match_across_arms", sorted(fixture_seeds),
                          sorted(shipped_seeds))
        fix = {it["seed"]: it for it in load_items("fixture", lv)}
        ship = {it["seed"]: it for it in load_items("shipped", lv)}
        counts = {"pairs": 0, "query_same": 0, "facts_same": 0, "entity_names_same": 0,
                  "n_facts_same": 0, "gold_same": 0}
        for seed in sorted(fixture_seeds & shipped_seeds):
            f, h = fix[seed], ship[seed]
            counts["pairs"] += 1
            counts["query_same"] += int(f["query"] == h["query"])
            counts["facts_same"] += int(f["facts"] == h["facts"])
            names_f = {e for fact in f["facts"] for e in (fact[0], fact[2])}
            names_h = {e for fact in h["facts"] for e in (fact[0], fact[2])}
            counts["entity_names_same"] += int(names_f == names_h)
            counts["n_facts_same"] += int(len(f["facts"]) == len(h["facts"]))
            counts["gold_same"] += int(f["answer"] == h["answer"])
        out["pairing"][f"l{lv}"] = counts
        if counts["pairs"] != 10:
            note_mismatch(f"pairing l{lv}.pairs", 10, counts["pairs"])
        if counts["facts_same"] != 0 or counts["entity_names_same"] != 0:
            note_mismatch(f"pairing l{lv}.construction_only",
                          "no pair shares its fact chain or its entity-name set",
                          f"facts_same {counts['facts_same']}, entity_names_same {counts['entity_names_same']}")
        if counts["query_same"] > 1:
            note_mismatch(f"pairing l{lv}.query_same", "<= 1", counts["query_same"])

    # Transport latency, quoted only from the archived records. probe_raw.jsonl and
    # calibration.json are hash-pinned above, so editing a latency value fails the
    # artifact confrontation (asserted by control 3 and control 5). The records carry
    # latency_s but no absolute timestamp, so this block states no contention claim.
    lat = [r["latency_s"] for r in recs]
    tok = [r["completion_tokens"] or 0 for r in recs]
    mean_lat, mean_tok = sum(lat) / len(lat), sum(tok) / len(tok)
    cov = sum((a - mean_lat) * (b - mean_tok) for a, b in zip(lat, tok))
    scale = (sum((a - mean_lat) ** 2 for a in lat) ** 0.5) * (sum((b - mean_tok) ** 2 for b in tok) ** 0.5)
    cal = json.loads((RUN_DIR / "calibration.json").read_text(encoding="utf-8"))["calibration"]
    out["latency"] = {
        "n_records": len(recs),
        "min_s": min(lat),
        "mean_s": mean_lat,
        "median_s": statistics.median(lat),
        "p90_s": quantile(lat, 0.90),
        "max_s": max(lat),
        "records_over_120s": sum(1 for x in lat if x > 120.0),
        "pearson_latency_vs_completion_tokens": (cov / scale) if scale else None,
        "median_s_by_arm": {arm: statistics.median([r["latency_s"] for r in recs if r["arm"] == arm])
                            for arm in sorted({r["arm"] for r in recs})},
        "calibration_calls": cal["n_calls"],
        "calibration_latency_s": sorted(c["latency_s"] for c in cal["calls"]),
        "per_record_absolute_timestamp_present": any(
            k in r for r in recs for k in ("finished_at", "timestamp", "ts_utc")),
    }
    return out


# ---------------- selftest: planted-defect control ----------------

def selftest() -> int:
    """Plant each defect the confrontation is supposed to catch and assert it is caught."""
    failures: list[str] = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    # control 1: the scorer must read perfect answering as BA 1.0 and a constant
    # answer as 0.5, and the leak signature must reproduce the documented pre-fix
    # pattern on the pinned fixture corpus (38 items per level, not just the 10 probed)
    check(balanced_accuracy(["yes", "no"], ["yes", "no"]) == 1.0,
          "control 1: perfect answering must read as BA 1.0")
    check(balanced_accuracy(["yes", "yes"], ["yes", "no"]) == 0.5,
          "control 1: a constant answer must read as BA 0.5")
    for lv in LEVELS:
        items = load_items("fixture", lv)
        golds = [it["answer"] for it in items]
        check(balanced_accuracy(baselines(items)["B_leak_sig"], golds) == 1.0,
              f"control 1: the leak signature must separate the pinned pre-fix l{lv} corpus perfectly")
        shipped = load_items("shipped", lv)
        check(balanced_accuracy(baselines(shipped)["B_leak_sig"], [it["answer"] for it in shipped]) == 0.5,
              f"control 1: the same signature must sit at chance on the repaired l{lv} corpus")

    # control 2: the exact null must place a perfect 10-item cell at 1/1024
    null = exact_null_ba(5, 5)
    check(len(null) == 1024, "control 2: 10-item null support must be 2**10")
    check(abs(p_at_least(null, 1.0) - 1 / 1024) < 1e-12, "control 2: P(BA = 1.0) must be 1/1024")
    check(p_at_least(null, 0.75) > 0.05, "control 2: BA 0.75 must not clear 0.05 at n=10")

    # control 3: shuffled labels must break the confrontation
    recs = load_jsonl(RUN_DIR / "probe_raw.jsonl")
    man = json.loads((RUN_DIR / "probe_manifest.json").read_text(encoding="utf-8"))
    tampered = json.loads(json.dumps(recs))
    for r in tampered:
        if r["cell"] == "shipped_l2":
            r["model_answer"] = "yes" if r["model_answer"] == "no" else "no"
    tmp = RUN_DIR / "_selftest_raw.jsonl"
    tmp.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in tampered), encoding="utf-8")
    real = (RUN_DIR / "probe_raw.jsonl").read_bytes()
    try:
        (RUN_DIR / "probe_raw.jsonl").write_bytes(tmp.read_bytes())
        tamped = analyze()
        check(any(m["field"].startswith("shipped_l2") for m in tamped["mismatches"]),
              "control 3: flipped answers in one cell must surface as mismatches")
        check(any(m["field"] == "artifact_hashes[probe_raw.jsonl]" for m in tamped["mismatches"]),
              "control 3: a rewritten raw file must fail the hash confrontation")
    finally:
        (RUN_DIR / "probe_raw.jsonl").write_bytes(real)
        tmp.unlink(missing_ok=True)

    # control 4: a planted budget lie must be caught
    att = json.loads((RUN_DIR / "attempts.json").read_text(encoding="utf-8"))
    att["attempts"][0]["endpoint_calls"] += 5
    att_path = RUN_DIR / "attempts.json"
    real_att = att_path.read_bytes()
    try:
        att_path.write_text(json.dumps(att, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        tamped = analyze()
        check(any("endpoint_calls" in m["field"] for m in tamped["mismatches"]),
              "control 4: an inflated per-attempt call count must surface as a mismatch")
    finally:
        att_path.write_bytes(real_att)

    # control 5: the clean artifacts must confront with zero mismatches
    clean = analyze()
    check(not clean["mismatches"], f"control 5: clean artifacts must confront exactly, got {clean['mismatches']}")
    check(clean["verdict_recomputed"] == man["verdict"], "control 5: verdict must recompute identically")
    # the transport numbers the report quotes must be the archived ones, and the archive
    # must stay silent about why they are slow
    lat = clean["latency"]
    check(lat["n_records"] == 40, "control 5: the latency block must cover all 40 archived records")
    check(abs(lat["min_s"] - 21.587) < 1e-6 and abs(lat["max_s"] - 345.144) < 1e-6,
          "control 5: the latency extremes the report cites must be the archived ones")
    check(abs(lat["mean_s"] - 121.8645) < 1e-3, "control 5: the report's mean latency must be the archived mean")
    check(lat["min_s"] <= lat["median_s"] <= lat["max_s"],
          "control 5: the median latency must lie inside the archived range")
    check(lat["per_record_absolute_timestamp_present"] is False,
          "control 5: the archive holds no absolute timestamp, so no contention claim is regenerable")
    check(lat["calibration_calls"] == 3 and len(lat["calibration_latency_s"]) == 3,
          "control 5: the calibration latencies the report cites must come from the pinned sidecar")
    # the control-group count the report cites must equal the numbered groups in this file,
    # so the cited number cannot drift when a control is added or removed (register item D11)
    cited_groups = 14
    numbered = sorted({int(n) for n in re.findall(r"# control (\d+):",
                                                  Path(__file__).read_text(encoding="utf-8"))})
    check(numbered == list(range(1, cited_groups + 1)),
          f"control 5: the file must hold exactly the {cited_groups} numbered control groups "
          f"the report cites, found {numbered}")

    # control 6: the fixture arm must be reported as non-discriminating
    for lv in LEVELS:
        check(clean["fixture_degeneracy"][f"l{lv}"]["leak_sig_equals_gold"] == clean["fixture_degeneracy"][f"l{lv}"]["n"],
              f"control 6: fixture l{lv} must be reported as degenerate")

    # control 7: the shipped arm must be reported as discriminating
    for lv in LEVELS:
        check(clean["entailment"][f"shipped_l{lv}"]["leak_signature_accuracy_full_corpus"] < 0.6,
              f"control 7: shipped l{lv} leak signature must sit at chance")

    # control 8: a record whose prompt hash does not match the rebuilt prompt must
    # be caught, and so must a manifest whose task hash does not match the rebuilt
    # prompt set: together these prove the run sent the prompts the design fixed
    tampered_prompt = json.loads(json.dumps(recs))
    tampered_prompt[0]["prompt_sha256"] = "0" * 64
    try:
        (RUN_DIR / "probe_raw.jsonl").write_text(
            "".join(json.dumps(r, sort_keys=True) + "\n" for r in tampered_prompt), encoding="utf-8")
        tamped = analyze()
        check(any(m["field"].startswith("prompt_sha256[") for m in tamped["mismatches"]),
              "control 8: a record that does not match its rebuilt prompt must surface")
    finally:
        (RUN_DIR / "probe_raw.jsonl").write_bytes(real)

    man_path = RUN_DIR / "probe_manifest.json"
    real_man = man_path.read_bytes()
    bad_man = json.loads(real_man.decode(encoding="utf-8"))
    bad_man["prompt_hash"] = "0" * 64
    try:
        man_path.write_text(json.dumps(bad_man, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        tamped = analyze()
        check(any(m["field"] == "prompt_hash" for m in tamped["mismatches"]),
              "control 8: the task hash must confront the rebuilt prompt set")
    finally:
        man_path.write_bytes(real_man)

    # control 9: a pinned environment hash that no longer matches the file it pins
    # must be caught, otherwise the report could be read against a swapped corpus
    env_path = RUN_DIR / "environment.json"
    real_env = env_path.read_bytes()
    bad_env = json.loads(real_env.decode(encoding="utf-8"))
    bad_env["sha256"]["corpora"]["items/ladders/l8.jsonl"] = "0" * 64
    try:
        env_path.write_text(json.dumps(bad_env, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        tamped = analyze()
        check(any(m["field"].endswith("corpora[items/ladders/l8.jsonl]") for m in tamped["mismatches"]),
              "control 9: a stale pinned corpus hash must surface as a mismatch")
    finally:
        env_path.write_bytes(real_env)

    # control 10: the label-permutation null must be exact, must be the more
    # conservative null for a perfect cell, and must still reject a perfect 10-of-10 cell
    perm = exact_null_ba_label_permutation(["yes"] * 5 + ["no"] * 5, ["yes"] * 5 + ["no"] * 5)
    fair = exact_null_ba(5, 5)
    check(len(perm) == 252, "control 10: the label-permutation null support must be C(10,5) = 252")
    check(abs(p_at_least(perm, 1.0) - 1 / 252) < 1e-12, "control 10: P(BA = 1.0) must be 1/252")
    check(p_at_least(perm, 1.0) > p_at_least(fair, 1.0),
          "control 10: the label-permutation null must be the more conservative null at BA 1.0")
    check(p_at_least(perm, 1.0) < 0.05, "control 10: a perfect cell must survive the conservative null")
    check(p_at_least(perm, 0.75) > p_at_least(fair, 0.75),
          "control 10: the two nulls must not order uniformly at BA 0.75, and the honest reading is reported")
    for cell in CELLS:
        got = clean["cells"][cell]["label_permutation_null"]["p_ba_at_least_observed"]
        check(got < 0.05, f"control 10: {cell} must stay significant under the conservative null")

    # control 11: the battery confrontation must catch a tampered pinned battery report
    bat_path = RUN_DIR / "name_channel_audit_shipped.json"
    real_bat = bat_path.read_bytes()
    bad_bat = json.loads(real_bat.decode(encoding="utf-8"))
    bad_bat["levels"][0]["structural"]["same_component"]["accuracy"] = 0.52
    try:
        bat_path.write_text(json.dumps(bad_bat, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        tamped = analyze()
        check(any(m["field"].startswith("battery[shipped]") for m in tamped["mismatches"]),
              "control 11: a tampered pinned battery report must surface as a mismatch")
    finally:
        bat_path.write_bytes(real_bat)

    # control 12: the battery must not flag any traversal-free feature on the real corpora
    for kind in ("shipped", "fixtures"):
        check(not clean["battery"][kind]["any_traversal_free_leak"],
              f"control 12: {kind} must show no traversal-free leak")
        check("same_component" in clean["battery"][kind]["any_structural_shortcut"],
              f"control 12: {kind} must show the structural connectivity shortcut")
        check(clean["battery"][kind]["exit_code"] == 5,
              f"control 12: {kind} battery verdict must be exit 5")

    # control 13: the connectivity claim must be backed by two independent component
    # implementations, and a planted counterexample must break it
    check(component_map([["a", "precedes", "b"], ["c", "precedes", "d"]])[0] == 2,
          "control 13: two disjoint edges must give 2 components")
    check(component_map([["a", "precedes", "b"], ["b", "precedes", "c"]])[0] == 1,
          "control 13: a shared vertex must merge the components")
    _, ids = component_map([["a", "precedes", "b"], ["c", "precedes", "d"]])
    check(ids["a"] == ids["b"] and ids["a"] != ids["c"],
          "control 13: component ids must group the endpoints of one edge")
    bat = load_battery_module()
    disagreements = 0

    def partition(comp_id: dict) -> frozenset:
        groups: dict = {}
        for name, cid in comp_id.items():
            groups.setdefault(cid, set()).add(name)
        return frozenset(frozenset(g) for g in groups.values())

    for kind in ("shipped", "fixture"):
        for lv in CORPUS_LEVELS_FOR_CONNECTIVITY[kind]:
            for it in load_items(kind, lv):
                # component numbering is an implementation detail (the battery orders by
                # lexicographically smallest member, this script by discovery order), so
                # the confrontation is on the partition, never on the ids
                if partition(component_map(it["facts"])[1]) != partition(bat.components(it["facts"])[0]):
                    disagreements += 1
    check(disagreements == 0,
          f"control 13: the two component implementations must agree on every corpus item, got {disagreements}")
    for stats in clean["connectivity"].values():
        check(stats["same_component_accuracy_full_corpus"] == 1.0,
              "control 13: connectivity must reproduce the label on every corpus tested")
    corpus_path = REPO / "items" / "ladders" / "l2.jsonl"
    real_corpus = corpus_path.read_bytes()
    lines = real_corpus.decode(encoding="utf-8").splitlines()
    flipped = json.loads(lines[0])
    flipped["answer"] = "no" if flipped["answer"] == "yes" else "yes"
    lines[0] = json.dumps(flipped, sort_keys=True)
    try:
        corpus_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        tamped = analyze()
        check(any(m["field"] == "connectivity[shipped_l2].same_component_accuracy"
                  for m in tamped["mismatches"]),
              "control 13: a planted item that breaks connectivity must surface as a mismatch")
        check(any(m["field"].endswith("corpora[items/ladders/l2.jsonl]") for m in tamped["mismatches"]),
              "control 13: rewriting a pinned corpus must also fail the hash confrontation")
    finally:
        corpus_path.write_bytes(real_corpus)

    # control 14: the matched-pair claim. The arms are paired by seed only, so a pair may
    # not be described as the same item under a different query. The pairing counts are
    # recomputed here, and a planted pair that really does share its fact chain must break
    # the confrontation.
    for lv in LEVELS:
        p = clean["pairing"][f"l{lv}"]
        check(p["pairs"] == 10, f"control 14: l{lv} must pair 10 probed seeds")
        check(p["facts_same"] == 0 and p["entity_names_same"] == 0,
              f"control 14: l{lv} pairs must share neither the fact chain nor the entity names")
        check(p["query_same"] <= 1, f"control 14: l{lv} pairs must not share the queried pair")
    for key, row in clean["entailment"].items():
        check(row["query_pair_is_a_stated_fact_items"] == 0,
              f"control 14: {key} must hold no item whose queried pair is a stated fact")
        for cname, c in row["signature_conjuncts"].items():
            if key.startswith("fixture"):
                check(c["accuracy_full_corpus"] == 1.0,
                      f"control 14: {key}.{cname} must reproduce the label on the pre-fix arm")
                check(abs(c["fraction_true"] - row["gold_yes"] / row["n"]) < 1e-9,
                      f"control 14: {key}.{cname} must be true exactly on the gold-yes items")
            else:
                check(c["fraction_true"] == 1.0,
                      f"control 14: {key}.{cname} must be constant true on the repaired arm")
    for lv in LEVELS:
        check(clean["entailment"][f"fixture_l{lv}"]["leak_signature_accuracy_full_corpus"] == 1.0,
              f"control 14: the fixture arm's shortcut must be the target-role signature at 1.0")
        check(clean["entailment"][f"shipped_l{lv}"]["leak_signature_constant"],
              f"control 14: the signature must be constant on the repaired arm at l{lv}")
    fix_path = REPO / "generators" / "fixtures" / "issue67_prefix_l2.jsonl"
    real_fix = fix_path.read_bytes()
    fix_lines = real_fix.decode(encoding="utf-8").splitlines()
    probe_recs = load_jsonl(RUN_DIR / "probe_raw.jsonl")
    pair_seed = sorted({r["seed"] for r in probe_recs if r["cell"] == "fixture_l2"})[0]
    partner = {it["seed"]: it for it in load_items("shipped", 2)}[pair_seed]
    pos = next(i for i, line in enumerate(fix_lines) if json.loads(line)["seed"] == pair_seed)
    planted = json.loads(fix_lines[pos])
    planted["facts"] = partner["facts"]
    planted["query"] = partner["query"]
    fix_lines[pos] = json.dumps(planted, sort_keys=True)
    try:
        fix_path.write_text("\n".join(fix_lines) + "\n", encoding="utf-8")
        tamped = analyze()
        check(any(m["field"] == "pairing l2.construction_only" for m in tamped["mismatches"]),
              "control 14: a planted pair that shares its construction must surface as a pairing mismatch")
        check(any(m["field"].startswith("entailment[fixture_l2]") for m in tamped["mismatches"]),
              "control 14: the planted pair must also break the fixture arm's shortcut confrontation")
    finally:
        fix_path.write_bytes(real_fix)

    if failures:
        for f in failures:
            print(f"FAIL {f}")
        return 3
    print(f"selftest ok: {len(numbered)} control groups, {len(clean['mismatches'])} mismatches on clean artifacts")
    return 0


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return selftest()
    res = analyze()
    if "--check" in argv:
        for m in res["mismatches"]:
            print(f"MISMATCH {m['field']}: claimed {m['claimed']} recomputed {m['recomputed']}")
        print(f"mismatches: {len(res['mismatches'])}")
        return 1 if res["mismatches"] else 0
    print(json.dumps(res, indent=2, sort_keys=True))
    return 1 if res["mismatches"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

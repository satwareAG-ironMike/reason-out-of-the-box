#!/usr/bin/env python3
"""Round 81 (2026-11-22 04:09, nightly lane, issue #195): the weekly compute-cap audit.

Question. Does the 2026-11-22 04:09 firing dispatch prompts? The weekly compute
cap in research/AGENTS.md (issue #195, codified 2026-11-21) caps the nightly
lane at 80 dispatched prompts a week and the exploratory loop in explore/ at
400, with a 40-prompt cap per round. The cap is a kill rule: when it is spent
the loop stops and reports, and the next ISO week starts a fresh count.

This instrument re-counts the week from the public record instead of trusting
memory: in-tree raw.jsonl record counts (the merged lanes, grouped by the ISO
week of the round directory's date) plus the dated open-PR dispatch records
that exist only in unmerged heads (issue #150 class). Each open-PR record is
deduplicated against the tree: once its round directory is merged in-tree the
tree walk counts it and the record is skipped, so a merge never double-counts.

Budget. Zero prompts. The audit is pure record-keeping: it dispatches nothing
and calls no endpoint. The per-round 40-prompt cap is also scanned, because
the frozen judge's exploratory minimum (40 items per arm) can drive a single
round past it (round 81 did: 480 in one round, open PR #210).

Usage.
    python3 cap_audit.py --selftest   # arithmetic and negative controls, no I/O
    python3 cap_audit.py --audit      # recount the live tree, write cap_audit.json
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))

# Cap source: research/AGENTS.md "Weekly compute cap (issue #195)" (codified
# 2026-11-21), plus the per-round cap in the same file's Local Contracts.
CAP_NIGHTLY_WEEK = 80
CAP_EXPLORE_WEEK = 400
CAP_ROUND = 40

# Dated dispatch records (issue #150 class: records that live only in unmerged
# heads, or that merged the same day the audit runs - the 2026-11-24 gap,
# issue #199). Each carries the round directory it counts, its lane, the
# dispatched prompt count, the as-of date, and the public provenance.
OPEN_PR_RECORDS = [
    {
        "pr": 201,
        "dir": "research/nightly-2026-11-21-0230",
        "lane": "nightly",
        "prompts": 0,
        "as_of": "2026-11-21",
        "source": "PR #201 body: '0 of the 40 prompt cap was used and the panel "
                  "never dispatched' (the firing record, dead slot)",
    },
    {
        "pr": 204,
        "dir": "research/nightly-2026-11-21-0440",
        "lane": "nightly",
        "prompts": 40,
        "as_of": "2026-11-21",
        "source": "PR #204 body: '40 of 40 prompts dispatched' (round 79, the "
                  "2026-11-21 04:40 firing; its README records the week's nightly "
                  "total as 157 including these)",
    },
    {
        "pr": 203,
        "dir": "explore/2026-11-21-r80-ladders-fresh-seed",
        "lane": "explore",
        "prompts": 8,
        "as_of": "2026-11-22",
        "source": "PR #203 raw.jsonl: 8 probe records (round 80, the ledger row "
                  "r80-ladders-fresh-seed)",
    },
    {
        "pr": 210,
        "dir": "explore/2026-11-21-r81-ladders-judge-conformant",
        "lane": "explore",
        "prompts": 480,
        "as_of": "2026-11-21",
        "source": "PR #210 body: 200 calibration + 40 novelty-band + 240 "
                  "max_tokens=8 failure-record completions (round 81)",
    },
    {
        # Issue #199 gap (2026-11-24): a PR merged the same day it is audited
        # disappears from a static open-PR registry; the #219 record lived
        # only in the registry until its directory merged in-tree.
        "pr": 219,
        "dir": "research/nightly-2026-11-24-0226",
        "lane": "nightly",
        "prompts": 42,
        "as_of": "2026-11-24",
        "source": "PR #219 (merged 2026-11-24): round 84 dispatch record, 32 "
                  "scored + 2 out-of-plan diagnostics (#219 README:142)",
    },
]


def iso_week(d: datetime.date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_of_dir(date_str: str) -> str:
    parts = date_str.split("-")
    return iso_week(datetime.date(int(parts[0]), int(parts[1]), int(parts[2])))


def dir_date_str(dirname: str) -> str | None:
    # research/nightly-YYYY-MM-DD-HHMM or explore/YYYY-MM-DD-slug
    parts = dirname.split("-")
    if len(parts) < 3:
        return None
    if parts[0] == "nightly":
        return "-".join(parts[1:4])
    return "-".join(parts[0:3])


def count_lines(path: str) -> int:
    n = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                n += 1
    return n


def tree_rounds(repo_root: str) -> dict:
    """Per-lane, per-round prompt counts from in-tree raw.jsonl files.

    Returns {lane: {dirname: prompts}} for every round directory that carries a
    raw.jsonl; a directory without one (an undelivered round) is absent.
    """
    rounds: dict = {"nightly": {}, "explore": {}}
    rdir = os.path.join(repo_root, "research")
    if os.path.isdir(rdir):
        for entry in sorted(os.listdir(rdir)):
            if not entry.startswith("nightly-"):
                continue
            raw = os.path.join(rdir, entry, "raw.jsonl")
            if os.path.isfile(raw):
                rounds["nightly"][entry] = count_lines(raw)
    edir = os.path.join(repo_root, "explore")
    if os.path.isdir(edir):
        for entry in sorted(os.listdir(edir)):
            if not os.path.isdir(os.path.join(edir, entry)):
                continue
            raw = os.path.join(edir, entry, "raw.jsonl")
            if os.path.isfile(raw):
                rounds["explore"][entry] = count_lines(raw)
    return rounds


def lane_week_total(rounds: dict, lane: str, week: str) -> int:
    total = 0
    for dirname, prompts in rounds.get(lane, {}).items():
        ds = dir_date_str(dirname)
        if ds and week_of_dir(ds) == week:
            total += prompts
    return total


def open_pr_counts(records: list, rounds: dict, week: str, lane: str) -> tuple[dict, dict]:
    """Add dispatch records for the audit week, deduplicated against the tree.

    The #199 gap (2026-11-24): a record whose round directory is in-tree but
    whose raw.jsonl has zero records (an undelivered round) is NOT
    double-counted - the tree walk counted 0, the record's dispatch count
    stands. A record whose directory is in-tree AND has a nonzero raw.jsonl
    count IS deduplicated: the tree walk already counted it.
    """
    used: dict = {}
    deduped: dict = {}
    known_dirs: dict = {}
    for l, lane_rounds in rounds.items():
        for dirname, prompts in lane_rounds.items():
            known_dirs[f"{'research' if l == 'nightly' else 'explore'}/{dirname}"] = prompts
    for rec in records:
        if rec["lane"] != lane:
            continue
        ds = dir_date_str(rec["dir"].split("/", 1)[1])
        if ds is None or week_of_dir(ds) != week:
            continue
        if rec["dir"] in known_dirs:
            # In-tree: deduplicate only when the tree walk already counted
            # this directory's records (nonzero); an undelivered round
            # (zero records) keeps the record's dispatch count.
            if known_dirs[rec["dir"]] > 0:
                deduped[rec["pr"]] = rec["dir"]
            else:
                used[rec["pr"]] = rec["prompts"]
            continue
        used[rec["pr"]] = rec["prompts"]
    return used, deduped


def audit(repo_root: str, records: list, audit_date: datetime.date,
          cap_nightly: int = CAP_NIGHTLY_WEEK, cap_explore: int = CAP_EXPLORE_WEEK,
          cap_round: int = CAP_ROUND) -> dict:
    week = iso_week(audit_date)
    monday_next = audit_date + datetime.timedelta(days=7 - audit_date.weekday())
    rounds = tree_rounds(repo_root)
    out: dict = {
        "audit_date": audit_date.isoformat(),
        "iso_week": week,
        "cap_source": "research/AGENTS.md weekly compute cap (issue #195), "
                      "codified 2026-11-21",
        "this_firing_dispatched": 0,
        "lanes": {},
    }
    for lane, cap in (("nightly", cap_nightly), ("explore", cap_explore)):
        in_tree = lane_week_total(rounds, lane, week)
        used, deduped = open_pr_counts(records, rounds, week, lane)
        open_total = sum(used.values())
        total = in_tree + open_total
        spent = total > cap
        out["lanes"][lane] = {
            "cap_week": cap,
            "in_tree_prompts": in_tree,
            "open_pr_prompts": open_total,
            "open_pr_records_used": {str(k): v for k, v in sorted(used.items())},
            "open_pr_records_deduped": {str(k): v for k, v in sorted(deduped.items())},
            "total": total,
            "spent": spent,
            "over_by": max(0, total - cap),
            "next_dispatch_window": week if not spent else iso_week(monday_next),
        }
    # Per-round cap scan over effective counts (in-tree counts the merged
    # record; an open-PR record counts only while its directory is unmerged).
    violations = []
    effective: dict = {}
    for lane in ("nightly", "explore"):
        for dirname, prompts in rounds.get(lane, {}).items():
            effective[f"{lane}/{dirname}"] = prompts
    for rec in records:
        key = rec["dir"]
        if key not in effective:
            effective[key] = rec["prompts"]
    for key in sorted(effective):
        if effective[key] > cap_round:
            where = key.split("/", 1)[1]
            violations.append({
                "round_dir": key,
                "prompts": effective[key],
                "over_by": effective[key] - cap_round,
                "source": next((r["source"] for r in records if r["dir"] == key),
                                "in-tree raw.jsonl"),
            })
    out["round_cap"] = {"cap": cap_round, "violations": violations}
    out["kill_report"] = (
        f"nightly lane {out['lanes']['nightly']['total']} of "
        f"{out['lanes']['nightly']['cap_week']}, explore lane "
        f"{out['lanes']['explore']['total']} of {out['lanes']['explore']['cap_week']} "
        f"in {week}: "
        + ("both lanes spent, the loop stops and reports"
           if out["lanes"]["nightly"]["spent"] and out["lanes"]["explore"]["spent"]
           else "cap state as recorded, next dispatch window per lane"))
    return out


def _selftest() -> int:
    checks = 0

    def ok(cond: bool, label: str) -> None:
        nonlocal checks
        assert cond, f"selftest control failed: {label}"
        checks += 1

    tmp = tempfile.mkdtemp(prefix="cap_audit_selftest_")
    import shutil
    try:
        os.makedirs(os.path.join(tmp, "research", "nightly-2026-11-20-0400"))
        with open(os.path.join(tmp, "research", "nightly-2026-11-20-0400", "raw.jsonl"),
                  "w") as fh:
            fh.write("\n".join(f'{{"i": {i}}}' for i in range(3)) + "\n")
        os.makedirs(os.path.join(tmp, "research", "nightly-2026-11-21-0230"))
        with open(os.path.join(tmp, "research", "nightly-2026-11-21-0230", "raw.jsonl"),
                  "w") as fh:
            fh.write("\n".join(f'{{"i": {i}}}' for i in range(2)) + "\n")
        # #199 gap fixture: a same-day-merged round whose raw.jsonl is absent
        # (undelivered, zero records) - the tree walk does not see it at all,
        # so the registry record's dispatch count is the only count.
        os.makedirs(os.path.join(tmp, "research", "nightly-2026-11-22-0200"))
        os.makedirs(os.path.join(tmp, "explore", "2026-11-21-r78-cross-ask"))
        with open(os.path.join(tmp, "explore", "2026-11-21-r78-cross-ask", "raw.jsonl"),
                  "w") as fh:
            fh.write("\n".join(f'{{"i": {i}}}' for i in range(5)) + "\n")

        records = [
            {"pr": 900, "dir": "research/nightly-2026-11-21-0440", "lane": "nightly",
             "prompts": 7, "as_of": "2026-11-22", "source": "planted open-PR record"},
            # Planted stale record: the directory is in-tree (0 records), so its
            # 9 must NOT be added - the merge never double-counts.
            {"pr": 901, "dir": "research/nightly-2026-11-21-0230", "lane": "nightly",
             "prompts": 9, "as_of": "2026-11-22", "source": "planted stale record"},
            {"pr": 902, "dir": "explore/2026-11-21-r80-x", "lane": "explore",
             "prompts": 480, "as_of": "2026-11-21", "source": "planted violation"},
            {"pr": 903, "dir": "research/nightly-2026-11-08-0221", "lane": "nightly",
             "prompts": 30, "as_of": "2026-11-08", "source": "planted out-of-week"},
            # #199 gap control: merged same-day, undelivered round (in-tree,
            # zero records). Its dispatch count must count - the registry
            # entry is not voided by the merge.
            {"pr": 904, "dir": "research/nightly-2026-11-22-0200", "lane": "nightly",
             "prompts": 6, "as_of": "2026-11-22", "source": "planted same-day merge"},
        ]
        d = datetime.date(2026, 11, 22)  # a Sunday: still 2026-W47
        a = audit(tmp, records, d)

        # In-tree counts: 3 nightly, 5 explore; the zero-record round is present.
        ok(a["lanes"]["nightly"]["in_tree_prompts"] == 5, "nightly in-tree count")
        ok(a["lanes"]["explore"]["in_tree_prompts"] == 5, "explore in-tree count")
        # Dedup: the stale record (901) is skipped, not double-counted.
        ok(a["lanes"]["nightly"]["open_pr_prompts"] == 13, "open-PR nightly total (7 + #199 record 6)")
        ok("901" in a["lanes"]["nightly"]["open_pr_records_deduped"],
           "stale record deduped")
        # The out-of-week record (903, W45) is not in this week's totals.
        ok("903" not in a["lanes"]["nightly"]["open_pr_records_used"],
           "out-of-week record excluded")
        # Same-day merge gap (#199, 2026-11-24): a record whose round directory
        # is in-tree AND carries a record of its own dispatch must still count
        # in the audit week it belongs to - the registry entry is kept for the
        # audit week even after the merge, deduplicated only when the tree
        # walk already counted that very directory in that same week.
        ok(a["lanes"]["nightly"]["open_pr_records_deduped"].get("901")
           == "research/nightly-2026-11-21-0230",
           "in-tree record deduped (directory present, zero records)")
        ok(a["lanes"]["nightly"]["total"] == 18, "nightly total (in-tree 5 + open 13)")
        ok(not a["lanes"]["nightly"]["spent"], "nightly not spent at 18 of 80")
        # The #199 same-day-merge record (904, undelivered dir) is used, not deduped.
        ok("904" in a["lanes"]["nightly"]["open_pr_records_used"],
           "#199: undelivered same-day-merged record counts")
        ok(a["lanes"]["explore"]["total"] == 485, "explore total")
        ok(a["lanes"]["explore"]["spent"], "explore spent at 485 of 400")
        # Next dispatch window: Sunday's next window is the following Monday's week.
        ok(a["lanes"]["explore"]["next_dispatch_window"] == "2026-W48",
           "explore next window W48")
        ok(a["lanes"]["nightly"]["next_dispatch_window"] == "2026-W47",
           "nightly stays in W47 while unspent")
        # Round-cap scan: the planted 480-prompt round is flagged once; nothing else.
        ok(len(a["round_cap"]["violations"]) == 1
           and a["round_cap"]["violations"][0]["round_dir"]
           == "explore/2026-11-21-r80-x"
           and a["round_cap"]["violations"][0]["over_by"] == 440,
           "round-cap violation planted and detected")
        # Boundary: exactly at the cap is unspent, one over is spent.
        a_at = audit(tmp, records, d, cap_explore=485)
        ok(not a_at["lanes"]["explore"]["spent"] and a_at["lanes"]["explore"]["over_by"] == 0,
           "total == cap is not spent")
        a_over = audit(tmp, records, d, cap_explore=484)
        ok(a_over["lanes"]["explore"]["spent"] and a_over["lanes"]["explore"]["over_by"] == 1,
           "total one over cap is spent")
        # ISO week boundaries: W47 ends Sunday 2026-11-22, W48 starts Monday 23rd,
        # and New Year's Day 2026 (a Thursday) is W01.
        ok(week_of_dir("2026-11-22") == "2026-W47", "Sunday belongs to W47")
        ok(week_of_dir("2026-11-23") == "2026-W48", "Monday belongs to W48")
        ok(iso_week(datetime.date(2026, 1, 1)) == "2026-W01", "New Year's Day is W01")
        print(f"selftest: {checks} of {checks} checks green")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--audit", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    if args.audit:
        # Audit as of today's date: the round's committed cap_audit.json was
        # generated on the 2026-11-22 04:09 firing (ISO week 2026-W47). A
        # re-run after the week boundary records the fresh week instead.
        result = audit(_REPO, OPEN_PR_RECORDS, datetime.date.today())
        out_path = os.path.join(_HERE, "cap_audit.json")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, sort_keys=True, indent=1)
            fh.write("\n")
        print(f"cap_audit.json written: {result['kill_report']}")
        return 0

    ap.error("one of --selftest or --audit is required")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

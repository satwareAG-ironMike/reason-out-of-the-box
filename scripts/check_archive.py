#!/usr/bin/env python3
"""Consistency checker for the paper archive (stdlib only).

Checks every archive/round*/<id>-<slug>.md entry and archive/INDEX.md:
  - filename id prefix appears in the entry's arXiv/PMID/PhilPapers link
    (note: the pp<RECORD> prefix strip matches the record stem only - a link to a
    sibling record sharing the stem, e.g. DEVHTB-3 vs DEVHTB-2, is not caught;
    the [FT] human verification layer is the backstop)
  - required table fields and sections present
  - no placeholder author fields (value starting with "(")
  - no em/en dashes (project punctuation standard)
  - per-round entry count equals INDEX table row count
  - per-round full-text-verified entries equal INDEX [FT] rows
  - the archive count statement in README.md, root AGENTS.md, and archive/AGENTS.md
    matches the actual entry/round counts (files without a statement are skipped;
    a present file whose statement vanished is an error)

Usage:
  check_archive.py            exit 0 + "archive check passed" only if clean
  check_archive.py --report   print metrics (placeholder_authors, ft_verified, ...)
  check_archive.py --selftest negative control on a synthetic broken archive
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

REQUIRED_FIELDS = ("| Authors |", "| Venue |", "| Year |", "| Archive round |", "| Archived |")
ID_FIELDS = ("| arXiv |", "| PMID |", "| PhilPapers |")
REQUIRED_SECTIONS = ("## Abstract", "## Key findings", "## Relevance to core question", "## Citation")
FT_MARK = "verified from full text"
BAD_DASHES = ("\u2014", "\u2013")
# archive count statements in the parent docs (#54): the 2026-09-28 round-14 ingest
# drifted README + root AGENTS (92/12 vs INDEX 107/13) and no check caught it
COUNT_STATEMENTS = (
    ("README.md", re.compile(r"(\d+) peer-reviewed and preprint papers, (\d+) thematic rounds")),
    ("AGENTS.md", re.compile(r"(\d+) entries, (\d+) thematic rounds")),
    ("archive/AGENTS.md", re.compile(r"(\d+) entries in (\d+) thematic rounds")),
)


def check(root: Path) -> dict:
    archive = root / "archive"
    index = (archive / "INDEX.md").read_text(encoding="utf-8")
    errors: list[str] = []
    placeholder = 0
    ft_entries: dict[int, int] = {}
    counts: dict[int, int] = {}

    for entry in sorted(archive.glob("round*/*.md")):
        if entry.name == "AGENTS.md":
            continue
        rnd_match = re.match(r"round(\d+)", entry.parent.name)
        if not rnd_match:
            continue
        rnd = int(rnd_match.group(1))
        counts[rnd] = counts.get(rnd, 0) + 1
        text = entry.read_text(encoding="utf-8")
        rel = f"{entry.parent.name}/{entry.name}"

        id_prefix = entry.name.split("-", 1)[0].removeprefix("pmid").removeprefix("pp")
        if id_prefix not in text:
            errors.append(f"{rel}: id {id_prefix} not found in body")
        for field in REQUIRED_FIELDS:
            if field not in text:
                errors.append(f"{rel}: missing field {field}")
        if not any(f in text for f in ID_FIELDS):
            errors.append(f"{rel}: missing arXiv/PMID/PhilPapers field")
        for section in REQUIRED_SECTIONS:
            if section not in text:
                errors.append(f"{rel}: missing section {section}")
        m = re.search(r"^\| Authors \| (.*?) \|$", text, re.M)
        if m and m.group(1).lstrip().startswith("("):
            placeholder += 1
            errors.append(f"{rel}: placeholder author field")
        if any(d in text for d in BAD_DASHES):
            errors.append(f"{rel}: em/en dash present")
        if FT_MARK in text.lower():
            ft_entries[rnd] = ft_entries.get(rnd, 0) + 1

    if any(d in index for d in BAD_DASHES):
        errors.append("INDEX.md: em/en dash present")

    ft_mismatch = 0
    for rnd, n in counts.items():
        sec = re.search(rf"^### Round {rnd} .*?(?=^### |^## |\Z)", index, re.M | re.S)
        if not sec:
            errors.append(f"INDEX.md: no table for round {rnd}")
            continue
        rows = [l for l in sec.group(0).splitlines()
                if l.startswith("| ") and not l.startswith("| Paper") and not l.startswith("|--")]
        if len(rows) != n:
            errors.append(f"INDEX.md: round {rnd} has {len(rows)} rows, dir has {n} entries")
        ft_rows = sum(1 for l in rows if l.startswith("| [FT]"))
        ft_mismatch += abs(ft_rows - ft_entries.get(rnd, 0))

    total = sum(counts.values())
    rounds = len(counts)
    for rel, pattern in COUNT_STATEMENTS:
        path = root / rel
        if not path.is_file():
            continue
        matches = pattern.findall(path.read_text(encoding="utf-8"))
        if not matches:
            errors.append(f"{rel}: count statement not found")
            continue
        for n_str, r_str in matches:
            if (int(n_str), int(r_str)) != (total, rounds):
                errors.append(
                    f"{rel}: count drift: states {n_str} entries / {r_str} rounds, "
                    f"archive has {total} / {rounds}")

    return {
        "errors": errors,
        "placeholder_authors": placeholder,
        "ft_verified": sum(ft_entries.values()),
        "total": total,
        "ft_index_mismatch": ft_mismatch,
    }


GOOD_ENTRY = """# T

| Field | Value |
|-------|-------|
| arXiv | [1234.56789](https://arxiv.org/abs/1234.56789) |
| Authors | Ada Lovelace |
| Venue | X |
| Year | 2026 |
| Archive round | 1 |
| Archived | 2026-01-01 |

## Abstract (condensed)
a
## Key findings (verified from full text)
b
## Relevance to core question
c
## Citation
d
"""
GOOD_ENTRY_PP = """# T2

| Field | Value |
|-------|-------|
| PhilPapers | [XTEST](https://philpapers.org/rec/XTEST) |
| Authors | Grace Hopper |
| Venue | X |
| Year | 2026 |
| Archive round | 1 |
| Archived | 2026-01-01 |

## Abstract (condensed)
a
## Key findings (verified from full text)
b
## Relevance to core question
c
## Citation
d
"""
GOOD_INDEX = """# I

### Round 1 - x

| Paper | Venue | Verdict | Note |
|-------|-------|---------|------|
| [FT] Lovelace 2026 | X | + | n |
| [FT] XTEST 2026 | X | - | n |

## Other
"""

GOOD_README = """# R

| `archive/` | 2 peer-reviewed and preprint papers, 1 thematic rounds, per-paper entries |
"""
GOOD_AGENTS = """# A

| `archive/` | Paper archive: 2 entries, 1 thematic rounds |
"""
GOOD_ARCHIVE_AGENTS = """# archive

Durable archive of the papers: 2 entries in 1 thematic rounds.
"""


def selftest() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        d = root / "archive" / "round1-x"
        d.mkdir(parents=True)
        (d / "1234.56789-lovelace-t.md").write_text(GOOD_ENTRY, encoding="utf-8")
        (d / "ppXTEST-hopper-x.md").write_text(GOOD_ENTRY_PP, encoding="utf-8")
        (root / "archive" / "INDEX.md").write_text(GOOD_INDEX, encoding="utf-8")
        (root / "README.md").write_text(GOOD_README, encoding="utf-8")
        (root / "AGENTS.md").write_text(GOOD_AGENTS, encoding="utf-8")
        (root / "archive" / "AGENTS.md").write_text(GOOD_ARCHIVE_AGENTS, encoding="utf-8")
        ok = check(root)
        assert not ok["errors"], ok["errors"]
        assert ok["ft_verified"] == 2 and ok["ft_index_mismatch"] == 0

        # negative controls: each break must be caught
        broken = GOOD_ENTRY.replace("| Authors | Ada Lovelace |", "| Authors | (2026) |")
        broken = broken.replace("## Citation", "## Cite").replace("verified from full text", "")
        broken = broken.replace("| Year | 2026 |", "| Year | 2026 \u2014 |")
        (d / "1234.56789-lovelace-t.md").write_text(broken, encoding="utf-8")
        (d / "9999.00000-wrong-id.md").write_text(GOOD_ENTRY, encoding="utf-8")
        # count-statement controls (#54): dir now holds 3 entries; README deliberately
        # claims 9 (drift), root AGENTS.md stays correct at 3, archive/AGENTS.md loses
        # its count statement entirely (not-found control)
        (root / "README.md").write_text(GOOD_README.replace("2 peer-reviewed", "9 peer-reviewed"), encoding="utf-8")
        (root / "AGENTS.md").write_text(GOOD_AGENTS.replace("2 entries", "3 entries"), encoding="utf-8")
        (root / "archive" / "AGENTS.md").write_text("# archive\n\nno count here\n", encoding="utf-8")
        bad = check(root)
        kinds = " ".join(bad["errors"])
        for needle in ("placeholder author", "missing section ## Citation", "em/en dash",
                       "id 9999.00000 not found", "rows, dir has",
                       "README.md: count drift: states 9 entries / 1 rounds, archive has 3",
                       "archive/AGENTS.md: count statement not found"):
            assert needle in kinds, f"negative control missed: {needle}\n{kinds}"
        assert bad["placeholder_authors"] == 1
        # ft: broken entry lost FT, the pp entry and the wrong-id copy keep it -> 2/2
        assert bad["ft_index_mismatch"] == 0
    print("selftest passed")


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        selftest()
        return 0
    root = Path(__file__).resolve().parent.parent
    r = check(root)
    if "--report" in argv:
        print(f"placeholder_authors: {r['placeholder_authors']}")
        print(f"ft_verified: {r['ft_verified']}/{r['total']}")
        print(f"ft_index_mismatch: {r['ft_index_mismatch']}")
        print(f"errors: {len(r['errors'])}")
        return 0
    for e in r["errors"]:
        print(f"ERROR {e}")
    if r["errors"]:
        print(f"archive check FAILED ({len(r['errors'])} errors)")
        return 1
    print("archive check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

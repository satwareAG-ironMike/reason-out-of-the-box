#!/usr/bin/env python3
"""Link checker for repository markdown files (stdlib only).

Checks every tracked-style *.md file (hidden dirs pruned):
  - relative links [text](target) resolve to an existing file
  - http(s), mailto, and in-page (#) targets are skipped

Usage:
  check_links.py            exit 0 + "link check passed" only if clean
  check_links.py --selftest negative control on a synthetic broken tree
"""
import re
import sys
import tempfile
from pathlib import Path

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
SKIP_PREFIXES = ("http://", "https://", "mailto:", "#")


def check(root: Path) -> tuple[list[str], int]:
    errors: list[str] = []
    total = 0
    for md in sorted(root.rglob("*.md")):
        if any(part.startswith(".") for part in md.relative_to(root).parts):
            continue
        text = md.read_text(encoding="utf-8")
        for target in LINK_RE.findall(text):
            total += 1
            if target.startswith(SKIP_PREFIXES):
                continue
            path = target.split("#", 1)[0]
            if not path:
                continue
            resolved = (md.parent / path).resolve()
            if not resolved.exists():
                errors.append(f"{md.relative_to(root)}: broken link -> {target}")
    return errors, total


def selftest() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "README.md").write_text(
            "[ok](docs/real.md)\n[bad](docs/gone.md)\n[web](https://x.y)\n",
            encoding="utf-8",
        )
        (root / "docs").mkdir()
        (root / "docs" / "real.md").write_text("x\n", encoding="utf-8")
        errors, total = check(root)
        if total != 3 or len(errors) != 1 or "gone.md" not in errors[0]:
            print(f"selftest failed: total={total} errors={errors}", file=sys.stderr)
            return 1
        print("link check selftest passed")
        return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    root = Path(__file__).resolve().parent.parent
    errors, total = check(root)
    for err in errors:
        print(err, file=sys.stderr)
    if errors:
        print(f"link check FAILED: {len(errors)} broken", file=sys.stderr)
        return 1
    print("link check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Frozen-instrument integrity gate (issue #194).

The frozen judge is the instrument, so the repository must be able to prove which
bytes the instrument is. evaluation/frozen/MANIFEST.json records the sha256 of every
file the judge is made of. This script recomputes them and fails when any of these
is true:

  a listed file changed            the instrument moved under the manifest
  a frozen file is missing         the instrument is incomplete
  a frozen file is not listed      something entered the instrument unregistered
  a manifest entry is malformed    the record itself is not trustworthy
  MANIFEST.json itself is not JSONL-safe or not sorted  hygiene

--freeze writes MANIFEST.json from the files as they are now. It exists so the
freeze is a recorded act instead of a hand-copied table, and it refuses to run
when a frozen file already disagrees with an existing manifest (a freeze must be
an explicit decision, never a silent refresh).

stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
FROZEN = ROOT / "evaluation" / "frozen"
MANIFEST = FROZEN / "MANIFEST.json"

# The instrument, in the order a reader meets it. A file outside this list may not
# enter evaluation/frozen/ without being added here in the same PR.
FROZEN_FILES = ("rule.json", "pins.json", "verify.py", "novelty.py", "baselines.py", "score.py")
ALGORITHMS = ("sha256",)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current() -> dict[str, str]:
    """Hash every registered frozen file. A missing file raises: silence is not a pass."""
    out = {}
    for name in FROZEN_FILES:
        path = FROZEN / name
        if not path.is_file():
            raise FileNotFoundError(f"frozen file missing: evaluation/frozen/{name}")
        out[name] = sha256(path)
    return out


def read_manifest(path: pathlib.Path = MANIFEST) -> dict:
    data = json.loads(path.read_text())
    if data.get("id") != "frozen-judge-manifest-v1":
        raise ValueError(f"manifest id mismatch: {data.get('id')!r}")
    if data.get("algorithm") not in ALGORITHMS:
        raise ValueError(f"manifest hash algorithm unsupported: {data.get('algorithm')!r}")
    if not isinstance(data.get("files"), dict) or not data["files"]:
        raise ValueError("manifest carries no file table")
    for name, digest in data["files"].items():
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError(f"manifest entry for {name} is not a sha256 hex digest: {digest!r}")
    if not data.get("rule_sha256") or not data.get("pins_sha256"):
        raise ValueError("the manifest must name the decision rule and the pin set it freezes")
    return data


def check(path: pathlib.Path = MANIFEST) -> list[str]:
    """Compare the manifest against the bytes on disk. Returns the problems."""
    problems: list[str] = []
    try:
        manifest = read_manifest(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"manifest unreadable: {exc}"]
    try:
        disk = current()
    except FileNotFoundError as exc:
        return [str(exc)]

    for name in FROZEN_FILES:
        listed = manifest["files"].get(name)
        if listed is None:
            problems.append(f"{name}: not registered in the manifest")
        elif listed != disk[name]:
            problems.append(f"{name}: sha256 mismatch (manifest {listed[:12]}..., on disk {disk[name][:12]}...)")
    for name in sorted(manifest["files"]):
        if name not in FROZEN_FILES:
            problems.append(f"{name}: in the manifest but not a registered frozen file")
    if sorted(manifest["files"]) != sorted(FROZEN_FILES):
        problems.append("the manifest file table and the registered file list do not agree")

    for key, name in (("rule_sha256", "rule.json"), ("pins_sha256", "pins.json")):
        if manifest[key] != disk[name]:
            problems.append(f"{key} does not match the current {name}")

    # AGENTS.md is the DOX contract for this subtree, MANIFEST.json is this gate's own record.
    # Anything else that appears inside the instrument is unregistered by definition.
    allowlist = {"MANIFEST.json", "AGENTS.md"}
    unlisted = sorted(p.name for p in FROZEN.iterdir()
                      if p.is_file() and p.name not in FROZEN_FILES and p.name not in allowlist)
    if unlisted:
        problems.append(f"unregistered files inside evaluation/frozen/: {', '.join(unlisted)}")

    text = path.read_text()
    body = [line for line in text.splitlines() if line.strip()]
    if text.count("\n") > 1 or len(body) > 1:
        problems.append("MANIFEST.json must be a single JSON object on one line (JSONL-safe)")
    if "\n" in text.rstrip("\n"):
        problems.append("MANIFEST.json must not contain an embedded newline")
    if json.dumps(json.loads(text), sort_keys=True, separators=(",", ":")) + "\n" != text:
        problems.append("MANIFEST.json must be canonical: sorted keys, compact separators, one trailing newline")
    return problems


def disagreements(path: pathlib.Path = MANIFEST) -> list[str]:
    """The problems that mean the instrument moved under the manifest."""
    return [p for p in check(path) if "sha256 mismatch" in p or "not registered" in p
            or "do not agree" in p]


def freeze(confirm: str | None = None, path: pathlib.Path = MANIFEST) -> dict:
    """Write MANIFEST.json from the files as they are, refusing a silent refresh.

    A freeze is a recorded act. When a manifest already exists and the files disagree
    with it, re-freezing needs --confirm: the diff of hashes is printed instead of the
    old record being overwritten quietly, because "the instrument moved" is exactly the
    event the manifest exists to make visible.
    """
    disk = current()
    if path.exists():
        problems = disagreements(path)
        if problems:
            if not confirm:
                raise SystemExit("refusing to re-freeze over a disagreeing manifest: "
                                 "--confirm <reason> is required, and the hash diff is printed\n  "
                                 + "\n  ".join(problems))
            print(f"re-freeze confirmed: {confirm}")
            old = read_manifest(path)["files"]
            for name in sorted(set(old) | set(disk)):
                before, after = old.get(name), disk.get(name)
                if before != after:
                    print(f"re-freeze diff {name}: {(before or 'absent')[:12]}... -> "
                          f"{(after or 'absent')[:12]}...")
    manifest = {"id": "frozen-judge-manifest-v1", "algorithm": "sha256", "files": disk,
                "rule_sha256": disk["rule.json"], "pins_sha256": disk["pins.json"],
                "registered": list(FROZEN_FILES),
                "gate": "scripts/check_frozen_integrity.py",
                "rule": "the frozen judge is the bytes these hashes name; a change to any of them "
                        "is a new freeze, owner-merged, with the old hashes reported"}
    text = json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    path.write_text(text)
    return manifest


def selftest() -> int:
    """Planted defects must be caught. Green without a planted defect proves nothing."""
    checks = 0

    def ok(cond, label):
        nonlocal checks
        checks += 1
        if not cond:
            raise AssertionError(label)

    disk = current()
    good = json.dumps({"id": "frozen-judge-manifest-v1", "algorithm": "sha256", "files": disk,
                       "rule_sha256": disk["rule.json"], "pins_sha256": disk["pins.json"],
                       "registered": list(FROZEN_FILES), "gate": "x", "rule": "y"},
                      sort_keys=True, separators=(",", ":")) + "\n"
    tmp = pathlib.Path("/tmp/frozen-integrity")
    tmp.mkdir(parents=True, exist_ok=True)

    def write(text: str) -> pathlib.Path:
        path = tmp / "MANIFEST.json"
        path.write_text(text)
        return path

    ok(check(write(good)) == [], "control: a manifest matching the disk must pass")

    tampered = json.loads(good)
    tampered["files"]["score.py"] = "0" * 64
    problems = check(write(json.dumps(tampered, sort_keys=True, separators=(",", ":")) + "\n"))
    ok(any("score.py: sha256 mismatch" in p for p in problems),
       f"a changed frozen file must be caught, got {problems}")

    dropped = json.loads(good)
    dropped["files"].pop("novelty.py")
    problems = check(write(json.dumps(dropped, sort_keys=True, separators=(",", ":")) + "\n"))
    ok(any("novelty.py: not registered" in p for p in problems),
       f"a frozen file missing from the manifest must be caught, got {problems}")

    extra = json.loads(good)
    extra["files"]["sneaked.py"] = "1" * 64
    problems = check(write(json.dumps(extra, sort_keys=True, separators=(",", ":")) + "\n"))
    ok(any("sneaked.py: in the manifest but not a registered frozen file" in p for p in problems),
       f"an unregistered manifest entry must be caught, got {problems}")

    vague = json.loads(good)
    vague["files"]["verify.py"] = "deadbeef"
    problems = check(write(json.dumps(vague, sort_keys=True, separators=(",", ":")) + "\n"))
    ok(any("not a sha256 hex digest" in p for p in problems),
       f"a malformed digest must be rejected, got {problems}")

    wrong_id = json.loads(good)
    wrong_id["id"] = "frozen-judge-manifest-v2"
    problems = check(write(json.dumps(wrong_id, sort_keys=True, separators=(",", ":")) + "\n"))
    ok(any("manifest id mismatch" in p for p in problems), f"the manifest id must be named, got {problems}")

    loose = json.dumps(json.loads(good), indent=2) + "\n"
    problems = check(write(loose))
    ok(any("single JSON object on one line" in p for p in problems),
       f"a pretty-printed manifest must be rejected, got {problems}")

    ok(check(write(good)) == [], "the manifest check must be idempotent")

    # A re-freeze over a disagreeing manifest is a recorded act, never a silent refresh.
    moved = json.loads(good)
    moved["files"]["verify.py"] = "2" * 64
    moved_text = json.dumps(moved, sort_keys=True, separators=(",", ":")) + "\n"
    moved_path = write(moved_text)
    ok(disagreements(moved_path) != [], "a manifest that no longer names the bytes must disagree")
    try:
        freeze(path=moved_path)
        raise AssertionError("freeze must refuse to overwrite a disagreeing manifest")
    except SystemExit as exc:
        checks += 1
        ok("--confirm" in str(exc), f"the refusal must name the way out, got {exc}")
    ok(moved_path.read_text() == moved_text, "a refused freeze must leave the old record intact")
    frozen = freeze(confirm="planted re-freeze for the selftest", path=moved_path)
    ok(check(moved_path) == [], f"a confirmed re-freeze must produce a passing manifest: {frozen}")

    print(f"selftest: {checks} of {checks} checks green")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--confirm", default=None,
                        help="required to re-freeze when the files already disagree with the manifest")
    parser.add_argument("--print", dest="show", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.freeze:
        manifest = freeze(confirm=args.confirm)
        print(json.dumps(manifest["files"], sort_keys=True, indent=2))
        return 0
    problems = check()
    if args.show:
        print(json.dumps(current(), sort_keys=True, indent=2))
    if problems:
        print("frozen instrument integrity FAILED:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(f"frozen instrument intact: {len(FROZEN_FILES)} files, "
          f"rule {current()['rule.json'][:12]}..., pins {current()['pins.json'][:12]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

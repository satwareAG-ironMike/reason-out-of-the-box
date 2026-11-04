#!/usr/bin/env python3
"""Endpoint serving-id guard (issue #85, owner go 2026-11-04).

Enforces the public-only rule at PR time: no endpoint serving id may reach a
tracked file. Leak classes:

- host:port  a host literal (localhost, 127.x, or an IPv4 address) followed by a
  colon and a port. RFC 5737 documentation ranges (192.0.2.0/24, 198.51.100.0/24,
  203.0.113.0/24) are exempt: the sanitizer selftest fixtures use reserved
  documentation addresses, which no live endpoint can use.
- gguf path  a lowercase gguf model file name (word characters before the suffix).
  Upper-case "GGUF" as a format word is fine; a file name is a model file path.
- serving id a model identifier ending in a hyphen plus a quantization tag of the
  q, iq or ud-q digit form (deployment labels). Serving models are referenced by
  public name only (research/AGENTS.md sanitized-by-construction contract).

Scan: every git-tracked file in the working tree. The selftest plants each leak
class plus clean references in a temp file and asserts the detector separates
them; leak fixtures are assembled by concatenation so this file does not carry a
pattern instance of its own.
"""
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent

DOC_NETS = ("192.0.2.", "198.51.100.", "203.0.113.")

HOSTPORT = re.compile(
    r"\b(localhost|127\.\d{1,3}\.\d{1,3}\.\d{1,3}|\d{1,3}(?:\.\d{1,3}){3}):(\d{2,5})\b"
)
GGUFPATH = re.compile(r"[\w.-]+\.gguf\b")
SERVID = re.compile(r"\b[a-z0-9][a-z0-9._-]*-(?:iq\d+|q\d+|ud-q\d+)(?:[_-]?[a-z0-9]+)?\b")


def scan_text(text):
    """Return (class, match) hits for one text block."""
    hits = []
    for m in HOSTPORT.finditer(text):
        host = m.group(1)
        if host[0].isdigit() and any(host.startswith(n) for n in DOC_NETS):
            continue
        hits.append(("host:port", m.group(0)))
    for m in GGUFPATH.finditer(text):
        hits.append(("gguf path", m.group(0)))
    for m in SERVID.finditer(text):
        hits.append(("serving id", m.group(0)))
    return hits


def scan_file(path):
    """Return (line_no, class, match) hits for one file."""
    data = path.read_bytes()
    if b"\x00" in data:
        return []
    out = []
    for i, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
        for cls, match in scan_text(line):
            out.append((i, cls, match))
    return out


def tracked_files():
    r = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files"],
        capture_output=True, text=True, check=True,
    )
    return [ROOT / f for f in r.stdout.splitlines() if f]


def selftest():
    """Negative control: each leak class is detected, each clean reference is not.

    Leak fixtures are assembled from split literals so this file carries no
    pattern instance of its own (the scan runs over this file too).
    """
    leak = "\n".join([
        "endpoint http://" + "localhost" + ":8080/v1 was used",
        "weights loaded from /models/qwen3.8-flash-" + "next-i" + "q3" + "_xxs" + ".gguf",
        "commit signed by " + "qwen38-27b-ud-" + "q4" + "_k_xl",
    ])
    clean = "\n".join([
        "see http://198.51.100.7:8080/v1 in the sanitizer fixture (documentation range)",
        "fixture with a `*.gguf` filename example that trips the sanitizer",
        "quantized GGUF format, no file name given",
        "checkpoints allenai/OLMo-2-1124-7B and EleutherAI/pythia-2.8b-deduped",
        "MiMo-V2.6-Distill-Qwen-9B, Q6_K (public toolkit names, no deployment label)",
        "https://huggingface.co/allenai/OLMo-2-1124-7B/tree/main",
    ])
    lhits = scan_text(leak)
    if not ({"host:port", "gguf path", "serving id"} <= {c for c, _ in lhits}):
        print("FAIL: selftest did not detect all leak classes:", lhits)
        return 1
    chits = scan_text(clean)
    if chits:
        print("FAIL: selftest false positives on clean references:", chits)
        return 1
    # scan_file path checks: line numbers on a text file, skip on a binary file.
    # Leak line assembled, not a literal.
    leak_line = ("http://" + "localhost" + ":11434/v1\n").encode()
    with tempfile.NamedTemporaryFile("wb", suffix=".txt", delete=False) as f:
        f.write(b"clean line\n" + leak_line)
        txt = f.name
    fhits = scan_file(pathlib.Path(txt))
    if fhits != [(2, "host:port", "localhost" + ":11434")]:
        print("FAIL: scan_file line handling wrong:", fhits)
        return 1
    pathlib.Path(txt).unlink()
    with tempfile.NamedTemporaryFile("wb", suffix=".bin", delete=False) as f:
        f.write(b"\x00bin" + leak_line)
        binn = f.name
    if scan_file(pathlib.Path(binn)) != []:
        print("FAIL: scan_file did not skip binary file")
        return 1
    pathlib.Path(binn).unlink()
    print("serving-id selftest passed (3 leak classes detected, 0 false positives)")
    return 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        return selftest()
    hits = []
    for f in tracked_files():
        for line, cls, match in scan_file(f):
            hits.append((f.relative_to(ROOT), line, cls, match))
    if hits:
        for rel, line, cls, match in hits:
            print(f"FAIL {rel}:{line}: {cls} {match!r}")
        print(f"serving-id check failed: {len(hits)} hit(s)")
        return 1
    print("serving-id check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

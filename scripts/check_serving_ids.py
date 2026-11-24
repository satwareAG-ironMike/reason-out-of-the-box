#!/usr/bin/env python3
"""Endpoint serving-id guard (issue #85, owner go 2026-11-04).

Enforces the public-only rule at PR time: no endpoint serving id may reach a
tracked file. Leak classes:

- host:port  a host literal (localhost, 127.x, or an IPv4 address) followed by a
  colon and a port. RFC 5737 documentation ranges (192.0.2.0/24, 198.51.100.0/24,
  203.0.113.0/24) are exempt: the sanitizer selftest fixtures use reserved
  documentation addresses, which no live endpoint can use.
- named host  a letter-initial, lowercase, hyphenated hostname (an internal
  device name) followed by a colon and a port, space before the colon allowed.
  Public domains, digit-initial time and date tokens and localhost stay clean
  (issue #207: the leak class HOSTPORT alone missed in the PR #217 record).
- gguf path  a lowercase gguf model file name (word characters before the suffix).
  Upper-case "GGUF" as a format word is fine; a file name is a model file path.
- serving id a model identifier ending in a hyphen plus a quantization tag of the
  q, iq or ud-q digit form (deployment labels). Serving models are referenced by
  public name only (research/AGENTS.md sanitized-by-construction contract).
- home path a leading-slash home root (home, Users, Volumes) followed by a user
  directory that carries a name (issue #149 class 2, the GATES.md evidence-line
  leak). Identity-free home names are exempt and are the shipped fixture
  convention: user, example(s), sample(s), test(er|s), shared, vagrant, runner,
  ci, admin, demo, fix(ture|tures). root is the system account and names no
  person, so a root home (the round-instrument sanitizer fixtures) stays clean;
  a personal name in the home slot is what leaks.

Scan: every git-tracked file in the working tree. Modes:
--commits <range> scans the commit messages in that range (CI uses it on the
push range to main, which is where the Model: trailer lands), and --text scans
literal text (CI uses it on the PR title plus body, the sources a squash merge
composes the landing message from, issue #149 class 1). The selftest plants
each leak class plus clean references in a temp file and a temp git repo and
asserts the detector separates them; leak fixtures are assembled by
concatenation so this file does not carry a pattern instance of its own.
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
# Named device host (issue #207): a hyphenated, letter-initial, lowercase
# hostname followed by a colon and a port (space before the colon allowed).
# The lookbehind kills mid-word matches and domain TLD slots ("example.com:443");
# digit-initial candidates are out, so times ("05:40") and date-time fragments
# ("11-23 05:40") can never match. "localhost" carries no hyphen: HOSTPORT
# owns it. A named device host is exactly the inventory the public-only rule
# bans, and HOSTPORT alone missed it in the PR #217 run record.
NAMEDHOST = re.compile(r"(?<![\w.-])[a-z][a-z0-9]*(-[a-z0-9]+)+\s*:\d{2,5}\b")
GGUFPATH = re.compile(r"[\w.-]+\.gguf\b")
# The suffix group repeats (issue #149): the shipped one-optional-segment form
# never matched the two-segment _k_xl tag of the deployment labels found in
# commit trailers on main; the class must catch q4, q4_k, q4_k_xl, iq3_xxs.
SERVID = re.compile(r"\b[a-z0-9][a-z0-9._-]*-(?:iq\d+|q\d+|ud-q\d+)(?:[_-]?[a-z0-9]+)*\b")
HOMEPATH = re.compile(r"(/(?:home|Users|Volumes)/)([^/\s\"'`,;:)\]]+)")
# Identity-free home names: shipped fixture convention (research instruments) and
# generic system accounts. A personal name in the home slot is what leaks.
EXEMPT_HOME_NAMES = frozenset({
    "user", "users", "example", "examples", "sample", "samples", "test", "tester",
    "tests", "shared", "vagrant", "runner", "ci", "admin", "demo", "fix", "fixture",
    "fixtures",
})


def scan_text(text):
    """Return (class, match) hits for one text block."""
    hits = []
    for m in HOSTPORT.finditer(text):
        host = m.group(1)
        if host[0].isdigit() and any(host.startswith(n) for n in DOC_NETS):
            continue
        hits.append(("host:port", m.group(0)))
    for m in NAMEDHOST.finditer(text):
        hits.append(("named host", m.group(0)))
    for m in GGUFPATH.finditer(text):
        hits.append(("gguf path", m.group(0)))
    for m in SERVID.finditer(text):
        hits.append(("serving id", m.group(0)))
    for m in HOMEPATH.finditer(text):
        if m.group(2).lower() not in EXEMPT_HOME_NAMES:
            hits.append(("home path", m.group(0)))
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


def commit_messages(rng, root=None):
    """Yield (short_sha, message) for the commit range rng (e.g. base..HEAD)."""
    repo = str(root or ROOT)
    r = subprocess.run(
        ["git", "-C", repo, "log", "--format=%h\x1f%B\x1e", rng],
        capture_output=True, text=True, check=False,
    )
    if r.returncode != 0:
        # A new branch has no merge base (all-zero push base): scan the tip commit.
        r = subprocess.run(
            ["git", "-C", repo, "log", "-1", "--format=%h\x1f%B\x1e"],
            capture_output=True, text=True, check=True,
        )
    for record in r.stdout.split("\x1e"):
        record = record.strip("\n")
        if not record.strip():
            continue
        sha, _, body = record.partition("\x1f")
        yield sha, body


def scan_commits(rng, root=None):
    """Return (sha, class, match) hits over commit messages in a range."""
    out = []
    for sha, body in commit_messages(rng, root=root):
        for cls, match in scan_text(body):
            out.append((sha, cls, match))
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
        "ledger run from " + "/ho" + "me/maria" + "/repo and keys at "
        + "/Use" + "rs/wei" + "/.ssh/id",
        "the model was served on " + "omar-2" + " :8081 (pointer contract)",
        "endpoint " + "gw-node-1" + ":8080/v1 answered",
    ])
    clean = "\n".join([
        "see http://198.51.100.7:8080/v1 in the sanitizer fixture (documentation range)",
        "fixture with a `*.gguf` filename example that trips the sanitizer",
        "quantized GGUF format, no file name given",
        "checkpoints allenai/OLMo-2-1124-7B and EleutherAI/pythia-2.8b-deduped",
        "MiMo-V2.6-Distill-Qwen-9B, Q6_K (public toolkit names, no deployment label)",
        "https://huggingface.co/allenai/OLMo-2-1124-7B/tree/main",
        "/ho" + "me/user/f.bin and /root/models/f.bin (identity-free fixture homes)",
        "the sanitizer strips /ma" + "nt/ and /media/ paths (no user slot)",
        "nightly timers fire at 02:00 and 04:00 (digit-only time tokens)",
        "ops entries 2026-11-23 05:40/06:45 UTC (date and time, no host)",
        "public docs site example.com:443 (public domain, no device host)",
    ])
    lhits = scan_text(leak)
    if not ({"host:port", "gguf path", "serving id", "home path", "named host"}
            <= {c for c, _ in lhits}):
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
    # Commit-message scan fixture: a temp repo with one clean commit and one
    # planted trailer leak (issue #149 class 1: squash merges replay trailers).
    with tempfile.TemporaryDirectory() as repo:
        git = ["git", "-C", repo, "-c", "commit.gpgsign=false",
               "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid"]
        subprocess.run(git + ["init", "-q"], check=True, capture_output=True)
        subprocess.run(git + ["commit", "-q", "--allow-empty", "-m",
                              "Round N: honest subject (refs #1)\n\n"
                              "Model: Public Model Name (provider/public-repo-id)"],
                       check=True, capture_output=True)
        subprocess.run(git + ["commit", "-q", "--allow-empty", "-m",
                              "Round N+1: planted trailer\n\n"
                              "Model: Public Name (" + "localhost" + ":11434/private-"
                              + "qwen38-27b-ud-" + "q4" + "_k_xl)\n"
                              "ran in " + "/ho" + "me/maria" + "/checkout\n"
                              "served on " + "omar-2" + " :8081"],
                       check=True, capture_output=True)
        tip = subprocess.run(git + ["rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, check=True).stdout.strip()
        shits = scan_commits("HEAD~1..HEAD", root=repo)
        classes = {c for _, c, _ in shits}
        if not {"host:port", "serving id", "home path", "named host"} <= classes:
            print("FAIL: commit scan missed a planted trailer leak:", shits)
            return 1
        if {sha for sha, _, _ in shits} != {tip}:
            print("FAIL: commit scan attributed hits to the wrong commit:", shits)
            return 1
        # empty-range behaviour: a range with no commits yields no hits
        if scan_commits("HEAD..HEAD", root=repo) != []:
            print("FAIL: empty commit range produced hits")
            return 1
    print("serving-id selftest passed (5 leak classes detected in files, "
          "commit-message scan verified, 0 false positives)")
    return 0


def main():
    args = sys.argv[1:]
    if args and args[0] == "--selftest":
        return selftest()
    if args and args[0] == "--commits":
        rng = args[1] if len(args) > 1 else "HEAD~1..HEAD"
        hits = scan_commits(rng)
        if hits:
            for sha, cls, match in hits:
                print(f"FAIL commit {sha}: {cls} {match!r}")
            print(f"serving-id commit check failed: {len(hits)} hit(s)")
            return 1
        print(f"serving-id commit check passed (range {rng})")
        return 0
    if args and args[0] == "--text":
        # Squash merges compose the landing commit message from the PR title and
        # body, so PR text carries the same classes the commit scan enforces.
        text = args[1] if len(args) > 1 else sys.stdin.read()
        hits = scan_text(text)
        if hits:
            for cls, match in hits:
                print(f"FAIL text: {cls} {match!r}")
            print(f"serving-id text check failed: {len(hits)} hit(s)")
            return 1
        print("serving-id text check passed")
        return 0
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

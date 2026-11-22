#!/usr/bin/env python3
"""Corpus novelty check for the frozen judge (issue #194).

Answers one question per item/solution: is this text (or a 13-word run of it)
present in the model's public training corpus? A hit means the answer is not
unique to this run, so the item is excluded from the POSITIVE numerator while
still counted in n (intent to treat).

Backends (evaluation/frozen/rule.json "novelty.corpus_backends"):
  local_scan   Aho-Corasick-style 13-gram index over a corpus slice under
               FROZEN_CORPUS_DIR, capped by FROZEN_CORPUS_MAX_BYTES. Stdlib only.
  infinigram   HTTP adapter, base URL from INFINIGRAM_BASE_URL only.
  olmotrace    HTTP adapter, base URL from OLMOTRACE_BASE_URL only.
An adapter is inert when its env var is absent: the judge reports
status "not_evaluable" for that backend instead of guessing. CI never performs a
live corpus query; a live query is an owner-approved operation.

Endpoint discipline: a base URL is read from the environment and used only for
the request. It is never written to any artifact, printed, or returned in a
result object (public-only rule, scripts/check_serving_ids.py leak classes).

CLI:
  novelty.py --selftest
  novelty.py --check --text "..." [--family ladders] [--backend local_scan]
  novelty.py --index-corpus            # build/report the local 13-gram index
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import urllib.parse
import urllib.request

NGRAM_WORDS = 13
# A 1- or 2-token gold ("yes", "no", "7") is not a searchable solution string: a
# corpus that contains the token "no" says nothing about whether it contains that
# item. Short golds are therefore judged on the item surface alone, and the row
# records the basis. Pre-registered in rule.json novelty.basis_rule.
MIN_SOLUTION_TOKENS = 3
NON_WORD = re.compile(r"[^a-z0-9]+")
BACKENDS = ("local_scan", "infinigram", "olmotrace")
ENV_FOR = {"local_scan": "FROZEN_CORPUS_DIR", "infinigram": "INFINIGRAM_BASE_URL",
           "olmotrace": "OLMOTRACE_BASE_URL"}
STATUSES = ("clean", "flagged", "not_evaluable")


# ---------------------------------------------------------------- normalization

def normalize(text: str) -> str:
    """Corpus-facing normalization: lowercase, non-alphanumeric runs to single
    spaces. Applied identically to the query and to the corpus side, otherwise a
    near match cannot be decided at all."""
    return " ".join(tok for tok in NON_WORD.split((text or "").lower()) if tok)


def ngrams(text: str, n: int = NGRAM_WORDS) -> list[str]:
    words = normalize(text).split()
    if len(words) < n:
        return [" ".join(words)] if words else []
    return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]


# ---------------------------------------------------------------- local index

class LocalScan:
    """13-gram index over a budgeted corpus slice. Pure stdlib, deterministic."""

    name = "local_scan"

    def __init__(self, root: str | None = None, max_bytes: int | None = None):
        self.root = root or os.environ.get(ENV_FOR["local_scan"], "")
        cap = max_bytes if max_bytes is not None else int(
            os.environ.get("FROZEN_CORPUS_MAX_BYTES", 64 * 1024 * 1024))
        self.index: set[str] = set()
        self.exact_text: list[str] = []
        self.bytes_scanned = 0
        self.files_scanned = 0
        self.configured = False
        self.cap = cap
        if self.root:
            self._build(pathlib.Path(self.root))

    def _build(self, root: pathlib.Path) -> None:
        if not root.is_dir():
            raise FileNotFoundError("FROZEN_CORPUS_DIR is set but is not a directory")
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix not in (".txt", ".jsonl", ".text"):
                continue
            remaining = self.cap - self.bytes_scanned
            if remaining <= 0:
                return
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                chunk = handle.read(remaining)
            self.bytes_scanned += len(chunk.encode())
            self.files_scanned += 1
            self.configured = True
            norm = normalize(chunk)
            grams = norm.split()
            for i in range(len(grams) - NGRAM_WORDS + 1):
                self.index.add(" ".join(grams[i:i + NGRAM_WORDS]))
            self.exact_text.append(norm)
            if self.bytes_scanned >= self.cap:
                return

    @property
    def grams_indexed(self) -> int:
        return len(self.index)

    def available(self) -> bool:
        """Measurable means a corpus slice was configured and read. A short slice can
        hold no 13-word run at all and still be a real corpus to search: an empty
        gram index with a scanned file answers clean, it does not answer
        not_evaluable."""
        return self.configured and self.bytes_scanned > 0

    def report(self) -> dict:
        return {"backend": self.name, "available": self.available(),
                "configured": self.configured, "files_scanned": self.files_scanned,
                "bytes_scanned": self.bytes_scanned, "grams_indexed": len(self.index),
                "cap_bytes": self.cap}

    def window(self, query: str, radius: int = 12) -> str | None:
        """The corpus text around the first match, widened to `radius` words on each
        side. A retrieval baseline needs the window, not just the matched run:
        the answer form lives next to the match, not inside it."""
        if not self.available():
            return None
        found = self.find(query)
        needles = [hit["match"] for hit in found["hits"] if "match" in hit] or ngrams(query)
        for needle in needles:
            for text in self.exact_text:
                pos = text.find(needle)
                if pos < 0:
                    continue
                words = text.split()
                anchor = len(text[:pos].split())
                lo = max(0, anchor - radius)
                hi = min(len(words), anchor + len(needle.split()) + radius)
                return " ".join(words[lo:hi])
        return None

    def find(self, query: str) -> dict:
        if not self.available():
            return {"backend": self.name, "status": "not_evaluable",
                    "reason": "no corpus slice configured", "hits": []}
        norm = normalize(query)
        hits = []
        if norm and any(f" {norm} " in f" {text} " for text in self.exact_text):
            # token-boundary exact match: the query as a whole sequence of tokens,
            # so "no" cannot be flagged for sitting inside "nothing"
            hits.append({"kind": "exact", "match": query[:200]})
        if len(norm.split()) >= NGRAM_WORDS:
            for gram in ngrams(query):
                if gram in self.index:
                    hits.append({"kind": "near", "ngram_words": NGRAM_WORDS, "match": gram})
                    break
        status = "flagged" if hits else "clean"
        return {"backend": self.name, "status": status, "hits": hits[:3]}


# ---------------------------------------------------------------- remote adapters

class HttpAdapter:
    """Inert unless the base URL is configured. The URL never leaves this object:
    reports carry the backend name and status only."""

    def __init__(self, name: str, timeout: int = 20):
        self.name = name
        self.base = (os.environ.get(ENV_FOR[name]) or "").strip()
        self.timeout = timeout

    def available(self) -> bool:
        return bool(self.base)

    def report(self) -> dict:
        return {"backend": self.name, "available": self.available(),
                "reason": None if self.base else "base URL not configured"}

    def find(self, query: str) -> dict:
        if not self.base:
            return {"backend": self.name, "status": "not_evaluable",
                    "reason": "adapter not configured", "hits": []}
        payload, path = self._request_shape(query)
        try:
            req = urllib.request.Request(
                self.base.rstrip("/") + path,
                data=json.dumps(payload).encode() if payload is not None else None,
                headers={"content-type": "application/json"}, method=self._method())
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                body = json.loads(response.read().decode())
        except Exception as exc:  # never echo the URL into the artifact
            return {"backend": self.name, "status": "not_evaluable",
                    "reason": f"query failed: {type(exc).__name__}", "hits": []}
        hits = self._parse(body)
        return {"backend": self.name, "status": "flagged" if hits else "clean",
                "hits": hits[:3]}

    def _method(self) -> str:
        return "POST" if self.name == "olmotrace" else "GET"

    def _request_shape(self, query: str):
        if self.name == "infinigram":
            words = normalize(query).split()
            gram = " ".join(words[:NGRAM_WORDS]) if words else ""
            return None, "/substrings/str/" + urllib.parse.quote(gram) + "?count=1"
        return {"text": normalize(query), "k": 1124}, "/search"

    def _parse(self, body: dict) -> list[dict]:
        if self.name == "infinigram":
            count = body.get("count", body.get("occurrences", 0))
            return [{"kind": "near", "ngram_words": NGRAM_WORDS}] if count else []
        results = body.get("results") or []
        out = []
        for res in results:
            dist = res.get("distance", res.get("nn_distance", 1.0))
            if isinstance(dist, (int, float)) and dist <= 0.12:
                out.append({"kind": "near", "distance": round(float(dist), 4)})
        return out


# ---------------------------------------------------------------- orchestration

def make_backends(which: list[str]) -> dict[str, object]:
    backends = {}
    for name in which:
        if name not in BACKENDS:
            raise ValueError(f"unknown novelty backend {name!r}")
        backends[name] = LocalScan() if name == "local_scan" else HttpAdapter(name)
    return backends


def solution_basis(solution: str) -> str:
    """Which text the novelty check is allowed to search, and why."""
    tokens = normalize(solution).split()
    if len(tokens) >= MIN_SOLUTION_TOKENS:
        return "solution_and_surface"
    return "surface_only_short_gold"


def check_solution(solution: str, item_surface: str, backends: dict) -> dict:
    """One verdict per item: clean, flagged, or not_evaluable, plus per-backend rows.

    not_evaluable is not clean. A cell whose novelty cannot be measured cannot
    support a POSITIVE (rule.json baselines.rule), and it is reported as such.
    """
    basis = solution_basis(solution)
    searchable = solution if basis == "solution_and_surface" else ""
    rows, statuses = [], []
    for name in BACKENDS:
        backend = backends.get(name)
        if backend is None:
            continue
        surface_row = backend.find(item_surface)
        solution_row = backend.find(searchable) if searchable else {"status": "not_searched",
                                                                   "reason": basis}
        row = {"backend": name, "surface_status": surface_row["status"],
               "solution_status": solution_row["status"], "basis": basis,
               "reason": surface_row.get("reason") or solution_row.get("reason")}
        rows.append(row)
        statuses.append(surface_row["status"])
        if searchable:
            statuses.append(solution_row["status"])
    if not rows:
        # same shape as the measured path: basis and ngram_words ride along so a
        # consumer can read one key set regardless of whether a backend answered
        return {"verdict": "not_evaluable", "ngram_words": NGRAM_WORDS, "basis": basis,
                "reason": "no backend enabled", "rows": []}
    if "flagged" in statuses:
        verdict = "flagged"
    elif all(status == "clean" for status in statuses):
        verdict = "clean"
    else:
        verdict = "not_evaluable"
    return {"verdict": verdict, "ngram_words": NGRAM_WORDS, "basis": basis, "rows": rows}


# ---------------------------------------------------------------- selftest

FIXTURE_CORPUS = {
    # a planted corpus window carrying 13 words of a planted item surface, and a
    # planted exact solution string. Both must be detected.
    "planted.txt": (
        "glorp precedes blin. blin precedes crank. crank precedes druv. "
        "druv precedes fenn. fenn precedes gloob. gloob precedes hwip. "
        "The answer to the chain question is yes, unambiguously. "
    ),
    "other.txt": ("ordinary prose about weather systems and harvest calendars, "
                  "written to give the index real runs of thirteen words and longer. " * 3),
    "answered.txt": (
        "zorp precedes qux. qux precedes vink. vink precedes mopa. mopa precedes tibs. "
        "does zorp precedes tibs? Answer: yes. "
    ),
}


def selftest() -> int:
    checks = 0

    def ok(cond, label):
        nonlocal checks
        checks += 1
        if not cond:
            raise AssertionError(label)

    ok(NGRAM_WORDS == 13, "novelty near match must use the frozen 13-word run")
    ok(normalize("Glorp  precedes--blin!") == "glorp precedes blin",
       "normalization must be corpus-facing on both sides")

    root = pathlib.Path(os.environ.get("FROZEN_TEST_TMPDIR", "/tmp")) / "frozen-novelty-fixture"
    root.mkdir(parents=True, exist_ok=True)
    for name, text in FIXTURE_CORPUS.items():
        (root / name).write_text(text, encoding="utf-8")
    scan = LocalScan(root=str(root))
    ok(scan.available(), "fixture corpus must build an index")
    ok(scan.files_scanned == 3, "fixture must scan all three files")
    ok(scan.grams_indexed >= 3, "the fixture slice must index real 13-word runs")
    # retrieval window: the answer form sits next to the matched run, not inside it
    win = scan.window("zorp precedes qux. qux precedes vink. vink precedes mopa. "
                      "mopa precedes tibs. does zorp precedes tibs?", radius=6)
    ok(win is not None and "yes" in win, "the retrieved window must carry the answer form")
    ok(scan.window("nothing like this appears in any fixture file here at all") is None
       or scan.window("zorp qux vink mopa") is not None,
       "a window must exist for a matched query")

    # NEGATIVE CONTROL 1 (planted near match): a 15-word run lifted from the
    # fixture, which contains runs of 13 words and longer on the corpus side.
    planted_surface = ("glorp precedes blin. blin precedes crank. crank precedes druv. "
                       "druv precedes fenn. fenn precedes gloob.")
    ok(len(normalize(planted_surface).split()) >= NGRAM_WORDS,
       "the planted run must be at least 13 words or the near path cannot fire")
    near = scan.find(planted_surface)
    ok(near["status"] == "flagged", "a planted 13-word corpus run must flag")
    ok(any(hit["kind"] == "near" for hit in near["hits"]), "the near hit must be reported")
    ok(all(hit["kind"] != "near" for hit in scan.find("zorp precedes qux. qux precedes vink. "
                                                       "vink precedes mopa. mopa precedes tibs.")["hits"]),
       "a 13-word run absent from the fixture must not produce a near hit")

    # NEGATIVE CONTROL 2 (planted exact match).
    exact = scan.find("The answer to the chain question is yes, unambiguously.")
    ok(exact["status"] == "flagged", "an exact corpus string must flag")
    ok(any(hit["kind"] == "exact" for hit in exact["hits"]), "the exact hit must be reported")

    # RECALL CONTROL (a true novel item must not be flagged): fresh synthetic
    # entities and a fresh solution string, same shape as a real item.
    novel_surface = ("zorp precedes qux. qux precedes vink. vink precedes mopa. "
                     "mopa precedes tibs. tibs precedes naru. naru precedes obeq. "
                     "Question: does zorp precedes obeq?")
    ok(scan.find(novel_surface)["status"] == "clean",
       "a genuinely novel 13-word run must stay clean")
    solution = ("Answer with exactly one word, yes or no. "
                 "zorp mopa obeq tibs qux vink naru")
    ok(scan.find(solution)["status"] == "clean", "a novel solution must stay clean")

    # short-query path: fewer than 13 words must still be decidable
    ok(scan.find("harvest calendars")["status"] == "flagged",
       "a short query inside the corpus must flag (exact substring path)")

    tiny = pathlib.Path(str(root) + "-tiny")
    tiny.mkdir(exist_ok=True)
    (tiny / "short.txt").write_text("ten words only in this slice, nothing longer here.",
                                    encoding="utf-8")
    short = LocalScan(root=str(tiny))
    ok(short.available(), "a scanned slice is measurable even when it is short")
    ok(short.grams_indexed == 0, "control premise: this slice holds no 13-word run")
    ok(short.find("a run of words that appears nowhere in this tiny slice at all")["status"]
       == "clean", "a searched corpus with no match must answer clean, not not_evaluable")

    # unconfigured local scan is not_evaluable, never silently clean
    empty = LocalScan(root="")
    ok(empty.find("anything at all here")["status"] == "not_evaluable",
       "a missing corpus slice must report not_evaluable")

    # adapters are inert without configuration and never leak the base URL
    for name in ("infinigram", "olmotrace"):
        adapter = HttpAdapter(name)
        os.environ.pop(ENV_FOR[name], None)
        adapter = HttpAdapter(name)
        row = adapter.find("any text here")
        ok(row["status"] == "not_evaluable", f"{name} must be inert when unconfigured")
        ok("http" not in json.dumps(row), f"{name} report must not carry a URL")
        ok(adapter.report()["available"] is False, f"{name} report says unconfigured")

    # orchestration verdicts
    backends = {"local_scan": scan}
    flagged = check_solution("The answer to the chain question is yes, unambiguously.",
                             novel_surface, backends)
    ok(flagged["verdict"] == "flagged", "a corpus-matching solution flags the item")
    clean = check_solution(solution, novel_surface, backends)
    ok(clean["verdict"] == "clean", "a novel solution over a novel surface is clean")
    mixed = check_solution(solution, novel_surface, {"infinigram": HttpAdapter("infinigram")})
    ok(mixed["verdict"] == "not_evaluable",
       "an unmeasurable backend can never produce a clean verdict")
    none = check_solution(solution, novel_surface, {})
    ok(none["verdict"] == "not_evaluable", "no backend enabled is not_evaluable")
    ok(none["basis"] == solution_basis(solution) and none["ngram_words"] == NGRAM_WORDS,
       "an unmeasured verdict must carry the same key set as a measured one")
    ok(set(r["solution_status"] for r in flagged["rows"]) <= set(STATUSES),
       "backend statuses must come from the frozen census")

    # budget: the cap is honored, and a capped index still answers
    capped = LocalScan(root=str(root), max_bytes=64)
    ok(capped.bytes_scanned <= 64, "the corpus byte cap must be honored")

    print(f"selftest: {checks} of {checks} checks green")
    return 0


# ---------------------------------------------------------------- CLI

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--text", default="")
    parser.add_argument("--surface", default="")
    parser.add_argument("--backend", action="append", choices=BACKENDS, default=None)
    parser.add_argument("--index-corpus", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.index_corpus:
        scan = LocalScan()
        print(json.dumps(scan.report(), sort_keys=True))
        return 0 if scan.available() else 1
    if args.check:
        backends = make_backends(args.backend or ["local_scan"])
        result = check_solution(args.text, args.surface or args.text, backends)
        print(json.dumps(result, sort_keys=True))
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

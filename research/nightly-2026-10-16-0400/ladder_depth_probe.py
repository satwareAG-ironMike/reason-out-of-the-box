#!/usr/bin/env python3
"""Depth-ceiling probe for the k-hop ladder family (nightly round 2026-10-16 04:00).

Question: with the issue #67 shortcut leak closed, does accuracy on the ladder family
stay above the majority baseline as hop depth k grows past the shipped grid, i.e. where
is the endpoint's ceiling d*? Round 4 (#69) reported "39/40 parsed and correct" on the
repaired format but landed no artifacts, so the model-facing half of #67 was unverified.
This script is that verification plus a depth curve on an extrapolated grid.

Arm A only (Condition 1, no elicitation): the transitivity rule, the shuffled atomic
facts, one yes/no question, "answer with exactly one word". No chain-of-thought is
requested. The serving endpoint may be an explicit-reasoning model; its reasoning text
is recorded verbatim as a trace and is NOT treated as evidence of the computation
(claim-ladder C4, docs/counterarguments.md).

Environment contract (never hardcoded, public-only rule):
  NIGHTLY_BASE_URL  OpenAI-compatible base URL ending in /v1
  NIGHTLY_MODEL_ID  served model id (public name only, goes into the artifacts)
  NIGHTLY_API_KEY   bearer token (never written to any file)

Determinism: items are the shipped ladder series (seed_base 20261005, the seed policy in
generators/AGENTS.md). Per level the selection rule is fixed in advance: scan items in
generation order (i = 0, 1, 2, ...) and take the first two with answer "yes" and the
first two with answer "no". No item is chosen after seeing a response.

Usage:
  ladder_depth_probe.py --selftest
  ladder_depth_probe.py --run --raw raw.jsonl --summary summary.json
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "generators"))

import ladders  # noqa: E402  (the shipped generator, repaired by PR #69)

SEED_BASE = 20261005
LEVELS = (1, 2, 3, 4, 5, 6, 8, 10, 12, 16)
PER_LEVEL = 4          # 2 yes + 2 no
PER_LEVEL_SCAN = 24    # how far into the series the selection rule scans
MAX_TOKENS = 2048      # protocol cap
TIMEOUT_S = 300
WORKERS = 2
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV6 = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b")
URLISH = re.compile(r"\bhttps?://[^\s\"']+")


# ---------------------------------------------------------------- item side

def bfs_dist(facts: list, src: str) -> dict:
    """Independent solver: unbounded directed BFS, node -> distance."""
    graph: dict = {}
    for s, _, t in facts:
        graph.setdefault(s, []).append(t)
    dist = {src: 0}
    q = deque([src])
    while q:
        u = q.popleft()
        for v in graph.get(u, ()):
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist


def components(facts: list) -> list[set]:
    """Weak components of the fact graph (used for the #67 isomorphism guard)."""
    graph: dict = {}
    for s, _, t in facts:
        graph.setdefault(s, []).append(t)
        graph.setdefault(t, []).append(s)
    seen: set = set()
    out: list = []
    for node in graph:
        if node in seen:
            continue
        comp = {node}
        seen.add(node)
        q = deque([node])
        while q:
            u = q.popleft()
            for v in graph[u]:
                if v not in seen:
                    seen.add(v)
                    comp.add(v)
                    q.append(v)
        out.append(comp)
    return out


def check_item(item: dict) -> None:
    """Refuse anything that is not the repaired (component-isomorphic) corpus.

    Post-#69 items: every weak component is a directed path of exactly `level`
    edges over distinct entities, and the query is always (path head, path tail).
    Pre-#69 items (single chain plus disjoint noise) fail this and would make the
    depth curve meaningless, because two surface rules solve them (#67)."""
    lvl = item["level"]
    lvl_facts = item["facts"]
    assert all(rel == ladders.REL for _, rel, _ in lvl_facts), item
    comps = components(lvl_facts)
    for comp in comps:
        assert len(comp) == lvl + 1, ("component size", lvl, comp)
    srcs = [s for s, _, _ in lvl_facts]
    tgts = [t for _, _, t in lvl_facts]
    assert len(srcs) == len(set(srcs)), "an entity is a fact source twice"
    assert len(tgts) == len(set(tgts)), "an entity is a fact target twice"
    qs, _, qt = item["query"]
    assert qs in srcs and qs not in tgts, "query source is not a path head"
    assert qt in tgts and qt not in srcs, "query target is not a path tail"
    # gold must match an independent solver
    dist = bfs_dist(lvl_facts, qs)
    assert (item["answer"] == "yes") == (qt in dist), item
    if item["answer"] == "yes":
        assert dist[qt] == lvl == item["chain_len"], item
    else:
        assert item["chain_len"] is None, item


def select_items() -> list[dict]:
    """Fixed-in-advance selection: first two yes and first two no per level."""
    picked: list[dict] = []
    for lvl in LEVELS:
        shipped = REPO / "items" / "ladders" / f"l{lvl}.jsonl"
        series = ladders.generate_items(lvl, PER_LEVEL_SCAN, SEED_BASE)
        if shipped.exists():
            disk = [json.loads(line) for line in
                    shipped.read_text(encoding="utf-8").splitlines()]
            assert disk[:PER_LEVEL_SCAN] == series[:PER_LEVEL_SCAN], (
                f"l{lvl}: regenerated series is not byte-identical to the shipped file")
        got_yes = got_no = 0
        for item in series:
            check_item(item)
            if item["answer"] == "yes" and got_yes < 2:
                picked.append(item)
                got_yes += 1
            elif item["answer"] == "no" and got_no < 2:
                picked.append(item)
                got_no += 1
            if got_yes == 2 and got_no == 2:
                break
        assert got_yes == 2 and got_no == 2, (lvl, got_yes, got_no)
    assert len(picked) == len(LEVELS) * PER_LEVEL, len(picked)
    return picked


# ---------------------------------------------------------------- prompt side

def render_prompt(item: dict) -> str:
    facts = "\n".join(f"{s} {r} {t}." for s, r, t in item["facts"])
    qs, qrel, qt = item["query"]
    return (f"{item['rule']}\nFacts:\n{facts}\n\n"
            f"Question: does {qs} {qrel} {qt}?\n"
            "Answer with exactly one word: yes or no.")


YES_NO = re.compile(r"\b(yes|no)\b", re.IGNORECASE)


def parse_answer(content: str) -> str | None:
    """First standalone yes/no of the final answer text; None if absent."""
    m = YES_NO.search(content or "")
    return m.group(1).lower() if m else None


def sanitize(text: str, secret_substrings: tuple[str, ...] = ()) -> str:
    """Public-only rule: no host, IP or endpoint URL may reach an artifact."""
    out = text or ""
    for sub in secret_substrings:
        if sub:
            out = out.replace(sub, "[REDACTED-HOST]")
    out = IPV4.sub("[REDACTED-IP]", out)
    out = IPV6.sub("[REDACTED-IP]", out)
    out = URLISH.sub("[REDACTED-URL]", out)
    return out


# ---------------------------------------------------------------- call side

def call(prompt: str, base: str, model: str, key: str,
         max_tokens: int = MAX_TOKENS) -> dict:
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions", data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        data = json.load(resp)
    dt = time.time() - t0
    choice = data["choices"][0]
    msg = choice.get("message") or {}
    usage = data.get("usage") or {}
    return {
        "content": msg.get("content") or "",
        "reasoning": msg.get("reasoning_content") or "",
        "finish_reason": choice.get("finish_reason"),
        "completion_tokens": usage.get("completion_tokens"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "latency_s": round(dt, 2),
    }


def run(items: list[dict], base: str, model: str, key: str) -> list[dict]:
    secrets = (base, base.split("//")[-1].split("/")[0])

    def one(item: dict) -> dict:
        prompt = render_prompt(item)
        err = None
        resp = {}
        for attempt in (1, 2):
            try:
                resp = call(prompt, base, model, key)
                err = None
                break
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                    ConnectionError) as exc:  # one retry, then record the failure
                err = f"{type(exc).__name__}"
                time.sleep(3 * attempt)
        parsed = parse_answer(resp.get("content", ""))
        gold = item["answer"]
        return {
            "level": item["level"],
            "seed": item["seed"],
            "seed_hash": item["seed_hash"],
            "n_facts": len(item["facts"]),
            "n_components": len(components(item["facts"])),
            "gold": gold,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()[:16],
            "prompt": sanitize(prompt, secrets),
            "response": sanitize(resp.get("content", ""), secrets),
            "reasoning": sanitize(resp.get("reasoning", ""), secrets),
            "finish_reason": resp.get("finish_reason"),
            "completion_tokens": resp.get("completion_tokens"),
            "prompt_tokens": resp.get("prompt_tokens"),
            "latency_s": resp.get("latency_s"),
            "error": err,
            "parsed": parsed,
            "format_valid": parsed is not None,
            "correct": parsed == gold,
            "truncated": resp.get("finish_reason") == "length",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return list(pool.map(one, items))


def summarize(rows: list[dict], model: str) -> dict:
    levels = sorted({r["level"] for r in rows})
    per_level = []
    for lvl in levels:
        sub = [r for r in rows if r["level"] == lvl]
        n = len(sub)
        valid = sum(1 for r in sub if r["format_valid"])
        correct = sum(1 for r in sub if r["correct"])
        gold_yes = sum(1 for r in sub if r["gold"] == "yes")
        answered_yes = sum(1 for r in sub if r["parsed"] == "yes")
        toks = [r["completion_tokens"] for r in sub if r["completion_tokens"]]
        lat = [r["latency_s"] for r in sub if r["latency_s"]]
        per_level.append({
            "level": lvl,
            "n": n,
            "n_facts_mean": round(statistics.mean(r["n_facts"] for r in sub), 1),
            "gold_yes": gold_yes,
            "majority_baseline": round(max(gold_yes, n - gold_yes) / n, 4),
            "format_valid": valid,
            "answered_yes": answered_yes,
            "correct": correct,
            "accuracy": round(correct / n, 4),
            "truncations": sum(1 for r in sub if r["finish_reason"] == "length"),
            "errors": sum(1 for r in sub if r["error"]),
            "completion_tokens_mean": round(statistics.mean(toks), 1) if toks else None,
            "latency_s_mean": round(statistics.mean(lat), 2) if lat else None,
        })
    return {
        "family": "ladders",
        "task_type": "hop_chain",
        "arm": "A (no elicitation, temperature 0, one-word answer)",
        "model_label": model,
        "seed_base": SEED_BASE,
        "selection_rule": ("per level, scan the ladder series in generation order and "
                          "take the first two items with answer yes and the first two "
                          "with answer no"),
        "levels": per_level,
        "totals": {
            "prompts": len(rows),
            "format_valid": sum(1 for r in rows if r["format_valid"]),
            "correct": sum(1 for r in rows if r["correct"]),
            "truncations": sum(1 for r in rows if r["finish_reason"] == "length"),
            "errors": sum(1 for r in rows if r["error"]),
        },
    }


# ---------------------------------------------------------------- selftest

def selftest() -> None:
    # 1. the independent solver agrees with the generator on the whole probe set,
    #    and the shipped series regenerate byte-identically
    items = select_items()
    assert len(items) == len(LEVELS) * PER_LEVEL == 40
    # 2. arithmetic controls for the scorer: a constant rule sits exactly at the
    #    majority baseline, a perfect rule at 1.0, a truncated response is invalid.
    fake = [dict(level=2, seed=i, seed_hash="x", n_facts=4, n_components=2,
                 gold=("yes" if i < 3 else "no"), prompt="", error=None,
                 finish_reason=("length" if i == 9 else "stop"),
                 completion_tokens=10, prompt_tokens=10, latency_s=1.0,
                 parsed="no", format_valid=True, correct=(i >= 3))
            for i in range(10)]
    row = summarize(fake, "test")["levels"][0]
    assert row["majority_baseline"] == 0.7 and row["accuracy"] == 0.7, row
    assert row["format_valid"] == 10 and row["truncations"] == 1, row
    perf = [dict(r, parsed=r["gold"], correct=True) for r in fake]
    assert summarize(perf, "test")["levels"][0]["accuracy"] == 1.0
    inv = [dict(r, parsed=("no" if r["gold"] == "yes" else "yes"), correct=False)
           for r in fake]
    assert summarize(inv, "test")["levels"][0]["accuracy"] == 0.0
    # 3. parser: standalone yes/no, casing, punctuation, no answer
    assert parse_answer("Answer: Yes.") == "yes"
    assert parse_answer("no") == "no"
    assert parse_answer("The chain gives NO more hops.") == "no"
    assert parse_answer("") is None
    assert parse_answer("maybe") is None
    assert parse_answer("Cannot answer, unclear.") is None
    # 4. sanitizer: no IP, URL or endpoint host survives
    # addresses from the documentation ranges (RFC 5737), never a real host
    s = sanitize("see http://198.51.100.7:8080/v1 and 192.0.2.1 fe80::1 ab:cd:ef",
                 ("198.51.100.7:8080",))
    assert "198.51.100.7" not in s and "192.0.2.1" not in s and "http" not in s, s
    assert "[REDACTED-IP]" in s
    # 5. prompt render is deterministic and contains every fact exactly once
    p1, p2 = render_prompt(items[0]), render_prompt(items[0])
    assert p1 == p2 and p1.count("precedes.") == 0
    for fact in items[0]["facts"]:
        assert p1.count(f"{fact[0]} precedes {fact[2]}.") == 1
    # 6. negative control: a mutated item (answer flipped) is refused by check_item
    mutated = json.loads(json.dumps(items[0]))
    mutated["answer"] = "no" if mutated["answer"] == "yes" else "yes"
    try:
        check_item(mutated)
    except AssertionError:
        pass
    else:
        raise AssertionError("negative control: flipped answer not caught")
    # 7. negative control: a pre-#69 item (chain plus disjoint noise) is refused
    noise = json.loads(json.dumps(items[0]))
    noise["facts"] = [f for f in noise["facts"]][:2] + [["zzz1", "precedes", "zzz2"]]
    try:
        check_item(noise)
    except AssertionError:
        pass
    else:
        raise AssertionError("negative control: pre-fix corpus not refused")
    print("selftest passed")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--run", action="store_true")
    p.add_argument("--raw", default="raw.jsonl")
    p.add_argument("--summary", default="summary.json")
    args = p.parse_args(argv)
    if args.selftest:
        selftest()
        return 0
    if args.run:
        base = os.environ.get("NIGHTLY_BASE_URL", "").rstrip("/")
        model = os.environ.get("NIGHTLY_MODEL_ID", "")
        key = os.environ.get("NIGHTLY_API_KEY", "")
        if not (base and model and key):
            print("ERROR NIGHTLY_BASE_URL, NIGHTLY_MODEL_ID and NIGHTLY_API_KEY "
                  "must be set", file=sys.stderr)
            return 2
        items = select_items()
        assert len(items) <= 40, "protocol cap: 40 prompts"
        assert MAX_TOKENS <= 2048, "protocol cap: max_tokens"
        rows = run(items, base, model, key)
        with open(args.raw, "w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
        summary = summarize(rows, model)
        with open(args.summary, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, sort_keys=True, indent=1)
            fh.write("\n")
        print("| level | n | gold yes | majority | valid | correct | acc | trunc | mean toks |")
        print("|---|---|---|---|---|---|---|---|---|")
        for r in summary["levels"]:
            print(f"| {r['level']} | {r['n']} | {r['gold_yes']} | "
                  f"{r['majority_baseline']:.2f} | {r['format_valid']} | "
                  f"{r['correct']} | {r['accuracy']:.2f} | {r['truncations']} | "
                  f"{r['completion_tokens_mean']} |")
        print("totals", summary["totals"])
        return 0
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

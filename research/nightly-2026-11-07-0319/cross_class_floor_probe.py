#!/usr/bin/env python3
"""Round 52 (2026-11-07 03:19): the load-floor wall, re-dispatched byte-identically on a 27B class.

The 2026-11-06 04:33 firing (flash-next class) measured the ladder family at the generator's
load floor (facts = 2k exactly) out to k = 48 and found the wall in a new shape: nothing
truncates (16 of 16 records finish stop), 13 of 16 delivered answers are correct, and all
three failures are cross-path (gold-no) items answering yes, both of them at k = 48. Every
gold-no record stopped at exactly 1556 completion tokens at every depth. Its issue #100
self-agreement control (N2) was never dispatched.

This round re-dispatches the identical items, byte-identical by prompt digest, on a 27B-class
local endpoint (public class name only; the serving id is disclosed in the commit Model:
trailer). Cells k = 24, 40, 48 pair 12 items to the reference firing's archived grid records;
k = 32 is the digest-pinned M32 item set the reference firing itself re-dispatched from round
50; k = 16 is a same-construction anchor (the reference firing did not dispatch it, and round
50's M16 band row is a different item: facts = 64 against the floor's 32). At k = 48 the two
unselected floor items (both gold-no) run at stage extra, so the cross-path arm carries four
items. Two k = 48 items are re-dispatched at stage dup as the issue #100 control.

Pairing is fail-closed: every pinned prompt must regenerate byte-identically from the shipped
generator before any prompt is spent, or the instrument refuses to dispatch. The cross-class
join is pure analysis (zero prompts): matched-pair comparison against the reference firing's
archived outcomes.

Caps (contractual): at most 40 prompts (this plan spends at most 25), max_tokens <= 2048,
free scholarly APIs only (none used), no metered or hosted providers.

Usage:
    cross_class_floor_probe.py --selftest   # planted controls; prints the gate blob
    cross_class_floor_probe.py --gate       # writes gate.json, prints the blob
    cross_class_floor_probe.py --dry-run    # the frozen dispatch plan
    cross_class_floor_probe.py --run        # health + grid + extras + dups
    cross_class_floor_probe.py --resume     # continue raw.jsonl, refusing on gate-hash drift
    cross_class_floor_probe.py --rescore    # rebuild gate.json + summary.json from raw.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "generators"))

import ladders  # noqa: E402  (the shipped generator, repaired by PR #69)

SEED_BASE = 20261005
SCAN = 400                 # how far into each level's series the selection rule scans
MAX_TOKENS = 2048          # protocol cap
TIMEOUT_S = 600            # issue #73: per-dispatch wall budget
CALL_CAP = 40              # protocol cap: prompts per round, health included
DISPATCH_BUDGET_S = 1800   # wall-clock budget for the dispatch phase of the firing
CONCURRENCY = 2            # the reference firing's class ran at this width; guarded either way
GRID_LEVELS = (16, 24, 32, 40, 48)
PAIRED_LEVELS = (24, 32, 40, 48)
GATE_SCHEMA = "round52-gate-v1"
# The frozen gate blob: canonical JSON of gate_spec(). --run and --resume recompute it and
# refuse to dispatch if it moved (pinned in the instrument so a later edit cannot move the
# gate unseen - issue #120 discipline).
ROUND52_GATE_BLOB_SHA256 = "0b0e8d777c7ac97047f70ea33eafb05f23ffc3e424f2a6d4c945fe1d2603b550"

# The two unselected load-floor items at k = 48 (seeds, gold, pinned prompt digest). Both are
# gold-no, so the cross-path arm at the cliff depth carries four items, not two.
EXTRA48 = (
    (116261303, "no", "47d3220085e7d537"),
    (116261347, "no", "a062b0f0fd5b5dc0"),
)
# Issue #100 control: two k = 48 items re-dispatched once. 116261051 is the gold-no item the
# reference firing answered wrong; 116261338 is the smallest-seed gold-yes item of the cell.
DUP_SEEDS = (116261051, 116261338)

# Vendored archived reference: the reference firing's 16 stage-1 grid records (the 2026-11-06
# 04:33 firing, flash-next-class local endpoint; its raw.jsonl lives in an open PR, so these
# constants are what the post-merge tree certifies). Fields per row:
# (level, seed, n_facts, gold, prompt_sha16, ref_stop, ref_finish, ref_correct, ref_declared).
ROUND51_REF = (
    (24, 68261051, 48, "no", "ab8097b385a6e84e", 1556, "stop", True, "no"),
    (24, 68261092, 48, "no", "0e080296a1ba1f5b", 1556, "stop", True, "no"),
    (24, 68261108, 48, "yes", "40e3dfb191140791", 771, "stop", True, "yes"),
    (24, 68261194, 48, "yes", "61dd9aaebb1d42c8", 666, "stop", True, "yes"),
    (32, 84261011, 64, "no", "d6b9e74cf69a8e28", 1556, "stop", True, "no"),
    (32, 84261050, 64, "no", "0d3347946e358ce5", 1556, "stop", False, "yes"),
    (32, 84261142, 64, "yes", "e9615dd04c8c87a2", 985, "stop", True, "yes"),
    (32, 84261174, 64, "yes", "766d6e09cba617c4", 845, "stop", True, "yes"),
    (40, 100261062, 80, "yes", "e80ea59e1f32f2b5", 1153, "stop", True, "yes"),
    (40, 100261101, 80, "yes", "7937eadc8a8cad36", 1059, "stop", True, "yes"),
    (40, 100261153, 80, "no", "76009aa8c4b886e5", 1556, "stop", True, "no"),
    (40, 100261309, 80, "no", "69ad228f8fed1e75", 1556, "stop", True, "no"),
    (48, 116261051, 96, "no", "068bc6a1fb0620fb", 1556, "stop", False, "yes"),
    (48, 116261076, 96, "no", "ffc75c928f37f0d9", 1556, "stop", False, "yes"),
    (48, 116261338, 96, "yes", "87e36020f5c31c93", 1310, "stop", True, "yes"),
    (48, 116261360, 96, "yes", "651e3f1737483f12", 1509, "stop", True, "yes"),
)
# The reference firing's whole-file raw.jsonl blob, recorded for provenance only.
ROUND51_RAW_BLOB_SHA256 = "fbfa4fde59f43ea3f484b4205b5beff11d2add27e6c3f60e210ca092e3452f7a"
# Reference firing identity, as archived in its own gate (public class name, 16-hex model
# digest, census exposure). A claim against it is an answer-level claim with its exposure
# stated (issue #105).
ROUND51_FIRING = "2026-11-06 04:33, flash-next-class local endpoint"
ROUND51_MODEL_DIGEST = "c62b81e96826354e"
ROUND51_CENSUS = "reasoning_content open on 20 of 20 records"
# The k = 32 cell is also round 50's digest-pinned M32 item set (vendored from the reference
# firing's own reference table; its raw.jsonl blob is provenance only).
ROUND50_M32 = (
    (84261011, 64, "no", "d6b9e74cf69a8e28"),
    (84261050, 64, "no", "0d3347946e358ce5"),
    (84261142, 64, "yes", "e9615dd04c8c87a2"),
    (84261174, 64, "yes", "766d6e09cba617c4"),
)
ROUND50_RAW_BLOB_SHA256 = "e2a9d47ecb69e40e4e908df9adf20362ea6f9ff9e0430516148a5e4c8021041f"
# Round 6's fitted length law (research/nightly-2026-10-16-0400/), the registered band basis
# alongside the reference firing's 28.3 tokens/hop measured on the same family.
ROUND6_FIT = "completion_tokens = -36 + 80k"
REF_SLOPE_TOKENS_PER_HOP = 28.3

CENSUS_PROMPT = ("Rule: for all x, y, z: if x precedes y and y precedes z, then x "
                 "precedes z. Facts state direct precedes links.\nFacts:\nabl precedes "
                 "bri.\nbri precedes cro.\n\nQuestion: does abl precedes cro?\n"
                 "Answer with exactly one word: yes or no.")

IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV6 = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b")
URLISH = re.compile(r"\bhttps?://[^\s\"']+")
YES_NO = re.compile(r"\b(yes|no)\b", re.IGNORECASE)
SENSITIVE = re.compile(r"(?i)\b(host|token|secret)\b\s*[:=]\s*\S+")


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
    """Weak components of the fact graph (the issue #67 isomorphism guard)."""
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
    """Refuse anything that is not the repaired (component-isomorphic) corpus."""
    lvl = item["level"]
    facts = item["facts"]
    assert all(rel == ladders.REL for _, rel, _ in facts), item
    comps = components(facts)
    for comp in comps:
        assert len(comp) == lvl + 1, ("component size", lvl, comp)
    srcs = [s for s, _, _ in facts]
    tgts = [t for _, _, t in facts]
    assert len(srcs) == len(set(srcs)), "an entity is a fact source twice"
    assert len(tgts) == len(set(tgts)), "an entity is a fact target twice"
    qs, _, qt = item["query"]
    assert qs in srcs and qs not in tgts, "query source is not a path head"
    assert qt in tgts and qt not in srcs, "query target is not a path tail"
    dist = bfs_dist(facts, qs)
    assert (item["answer"] == "yes") == (qt in dist), item
    if item["answer"] == "yes":
        assert dist[qt] == lvl == item["chain_len"], item
    else:
        assert item["chain_len"] is None, item


def render_prompt(item: dict) -> str:
    """The round-6 / round-50 template, byte-identical (required for prompt pairing)."""
    facts = "\n".join(f"{s} {r} {t}." for s, r, t in item["facts"])
    qs, qrel, qt = item["query"]
    return (f"{item['rule']}\nFacts:\n{facts}\n\n"
            f"Question: does {qs} {qrel} {qt}?\n"
            "Answer with exactly one word: yes or no.")


def prompt_digest(item: dict) -> str:
    return hashlib.sha256(render_prompt(item).encode()).hexdigest()[:16]


def declared_answer(text: str) -> str | None:
    """Answer-field readout: the last standalone yes/no in the answer channel."""
    hits = YES_NO.findall(text or "")
    return hits[-1].lower() if hits else None


_SERIES: dict = {}


def generate_floor(level: int) -> list:
    """This level's series (memoized), plus the shipped-file identity assertion where shipped."""
    if level in _SERIES:
        return _SERIES[level]
    series = ladders.generate_items(level, SCAN, SEED_BASE)
    shipped = REPO / "items" / "ladders" / f"l{level}.jsonl"
    if shipped.exists():
        disk = [json.loads(line) for line in
                shipped.read_text(encoding="utf-8").splitlines()]
        # The shipped file is 300 items deep; the scan runs past it, so the identity
        # assertion covers the shipped prefix only.
        assert disk == series[:len(disk)], (
            f"l{level}: regenerated series is not byte-identical to the shipped file")
    _SERIES[level] = series
    return series


def pick_floor(series: list, level: int, want_yes: int = 2, want_no: int = 2) -> list:
    """Selection rule: generation order, first two yes and two no with facts == 2*level."""
    floor = 2 * level
    got_yes = got_no = 0
    picked: list = []
    for item in series:
        check_item(item)
        if len(item["facts"]) != floor:
            continue
        if item["answer"] == "yes" and got_yes < want_yes:
            picked.append(item)
            got_yes += 1
        elif item["answer"] == "no" and got_no < want_no:
            picked.append(item)
            got_no += 1
        if got_yes == want_yes and got_no == want_no:
            break
    assert got_yes == want_yes and got_no == want_no, (level, got_yes, got_no)
    return picked


def build_cells() -> dict:
    """Every cell, built and certified before any prompt is spent."""
    cells: dict = {}
    for level in GRID_LEVELS:
        cells[f"F{level:03d}"] = pick_floor(generate_floor(level), level)
    # Stage-extra and duplicate items are generated directly by seed and certified against
    # their pinned digests (they are not selection-rule picks).
    cells["_EXTRA"] = [ladders.generate_item(48, seed) for seed, _, _ in EXTRA48]
    cells["_DUP"] = [ladders.generate_item(48, seed) for seed in DUP_SEEDS]
    return cells


def certify_pairing(cells: dict, ref: tuple = ROUND51_REF, m32: tuple = ROUND50_M32,
                    extra: tuple = EXTRA48) -> dict:
    """Fail-closed pairing check: every pinned prompt must regenerate byte-identically.

    This runs before any prompt is spent and is re-run by --rescore, so the post-merge tree
    (with the reference round's PR unmerged or merged alike) certifies from in-file constants.
    """
    out = {"ok": True, "certified": 0, "anchors": 0, "refused": []}
    by_seed = {}
    for level in GRID_LEVELS:
        for item in generate_floor(level):
            by_seed.setdefault(item["seed"], item)
    # 1. The 16 reference-firing grid rows: seed set per level, then per-item construction,
    #    gold and prompt digest.
    for level in PAIRED_LEVELS:
        ref_rows = {row[1]: row for row in ref if row[0] == level}
        cell_seeds = {it["seed"] for it in cells[f"F{level:03d}"]}
        if cell_seeds != set(ref_rows):
            out["ok"] = False
            out["refused"].append({"cell": f"F{level:03d}", "why": "seed set moved"})
            continue
        for seed, row in ref_rows.items():
            item = by_seed.get(seed)
            if item is None:
                out["refused"].append({"seed": seed, "why": "not regenerated by the generator"})
                out["ok"] = False
                continue
            _, seed_r, facts, gold, sha, *_ = row
            if item["level"] != level or len(item["facts"]) != facts:
                out["refused"].append({"seed": seed, "why": "construction moved"})
                out["ok"] = False
            elif item["answer"] != gold:
                out["refused"].append({"seed": seed, "why": "gold label moved"})
                out["ok"] = False
            elif prompt_digest(item) != sha:
                out["refused"].append({"seed": seed, "why": "prompt digest moved"})
                out["ok"] = False
            else:
                out["certified"] += 1
    # 2. The k = 32 cell must additionally be round 50's M32 set (double anchor).
    m32_rows = {row[0]: row for row in m32}
    cell32 = {it["seed"] for it in cells["F032"]}
    if cell32 != set(m32_rows):
        out["ok"] = False
        out["refused"].append({"cell": "F032", "why": "not the archived M32 item set"})
    else:
        for seed, row in m32_rows.items():
            item = by_seed.get(seed)
            if item is None or len(item["facts"]) != row[1] or item["answer"] != row[2] \
                    or prompt_digest(item) != row[3]:
                out["refused"].append({"seed": seed, "why": "M32 anchor moved"})
                out["ok"] = False
            else:
                out["certified"] += 1
    # 3. The k = 16 anchor: validated items at the floor, no outcome pin (same-construction).
    for item in cells["F016"]:
        if len(item["facts"]) == 32:
            check_item(item)
            out["anchors"] += 1
        else:
            out["refused"].append({"seed": item["seed"], "why": "not at the k = 16 floor"})
            out["ok"] = False
    # 4. The two extra k = 48 floor items: generated by seed, pinned digest and gold.
    for seed, gold, sha in extra:
        item = ladders.generate_item(48, seed)
        if len(item["facts"]) != 96 or item["answer"] != gold or prompt_digest(item) != sha:
            out["refused"].append({"seed": seed, "why": "extra floor item moved"})
            out["ok"] = False
        else:
            out["certified"] += 1
    return out


# ---------------------------------------------------------------- transport

def sanitize(text: str, secrets: tuple = ()) -> str:
    """Public-only rule: no endpoint value, host, IP, URL or credential reaches a file."""
    out = text if text is not None else ""
    for secret in secrets:
        if secret:
            out = out.replace(str(secret), "[redacted]")
    out = URLISH.sub("[redacted-url]", out)
    out = IPV4.sub("[redacted-ip]", out)
    out = IPV6.sub("[redacted-ip]", out)
    out = SENSITIVE.sub("[redacted-credential]", out)
    return out


def call_endpoint(prompt: str, base: str, model: str, key: str, max_tokens: int) -> dict:
    """One chat completion. Returns the raw response dict or raises RuntimeError."""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }).encode()
    headers = {"Content-Type": "application/json"}
    if key:  # a local slot that serves without a credential has key == ""
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body,
                                 headers=headers)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"transport:{type(exc).__name__}") from exc
    return {"payload": payload, "wall_s": round(time.time() - t0, 3)}


def census_of(payload: dict) -> dict:
    """Field census (issue #105): which field supplies the reasoning channel."""
    msg = {}
    try:
        msg = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        msg = {}
    fields = sorted(k for k in msg if k != "role")
    rc = msg.get("reasoning_content") or ""
    rf = msg.get("reasoning") or ""
    source = "reasoning_content" if rc else ("reasoning" if rf else "")
    return {"fields": fields, "reasoning_content_chars": len(rc),
            "reasoning_field_chars": len(rf), "reasoning_source": source}


def parse_answer_field(msg: dict) -> tuple:
    """Answer-channel readout: the answer field only, never a trace token.

    The family's trace-recovery rules stay refused after round 50's calibration failure
    (agreement 0.5652), so no verdict in this round comes from the trace channel. Trace text
    is still stored, but only for prefix identity and length.
    """
    content = msg.get("content") or ""
    if isinstance(content, list):  # some deployments serve content parts
        content = "".join(str(part.get("text", "")) if isinstance(part, dict) else str(part)
                          for part in content)
    trace = msg.get("reasoning_content") or msg.get("reasoning") or ""
    answer = declared_answer(content)
    source = "content" if answer is not None else "none"
    return answer, source, content, trace


def health_probe(base: str, model: str, key: str) -> dict:
    """Issue #73: one small call before the grid. 256 tokens, not MAX_TOKENS (round 22)."""
    info = {"probe": "health"}
    try:
        res = call_endpoint(CENSUS_PROMPT, base, model, key, 256)
        payload = res["payload"]
        info.update({"ok": True, "wall_s": res["wall_s"],
                     "census": census_of(payload),
                     "completion_tokens": payload.get("usage", {}).get("completion_tokens"),
                     "finish_reason": payload["choices"][0].get("finish_reason")})
    except RuntimeError as exc:
        info.update({"ok": False, "error": str(exc)})
    return info


def model_digest_of(model: str) -> str:
    return hashlib.sha256(model.encode()).hexdigest()[:16]


def wilson(k: int, n: int, z: float = 1.96) -> tuple:
    if n == 0:
        return (None, None)
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (round(max(0.0, (centre - half) / denom), 4),
            round(min(1.0, (centre + half) / denom), 4))


# ---------------------------------------------------------------- records

def score_record(job, item, resp, err, rung, gate_hash) -> dict:
    cell, is_dup = job[0], job[4]
    stage = job[3]
    rec = {"stage": stage, "cell": cell, "gate": gate_hash, "rung": rung,
           "is_dup": is_dup, "dispatch_index": job[5], "attempts": 1,
           "level": item["level"], "seed": item["seed"], "seed_hash": item["seed_hash"],
           "gold": item["answer"], "n_facts": len(item["facts"]),
           "n_chains": len(item["facts"]) // item["level"],
           "prompt_sha256": prompt_digest(item), "prompt_chars": len(render_prompt(item)),
           "pair_key": f"{item['seed']}|{prompt_digest(item)}|{rung}",
           "error": err, "delivered": False, "outcome": "transport_error",
           "correct": None, "declared": None, "declared_source": None,
           "content": "", "trace": "", "trace_chars": 0, "completion_tokens": None,
           "prompt_tokens": None, "finish_reason": None, "wall_s": None, "census": None}
    if resp is None:
        if err == "censored_by_cap":
            rec["outcome"] = "censored_by_cap"
        return rec
    payload, wall = resp["payload"], resp["wall"]
    try:
        choice = payload["choices"][0]
        msg = choice["message"]
    except (KeyError, IndexError, TypeError):
        rec["outcome"] = "malformed_response"
        rec["error"] = "malformed_response"
        return rec
    answer, source, content, trace = parse_answer_field(msg)
    usage = payload.get("usage") or {}
    secrets = tuple(job[6])
    rec.update({
        "declared": answer,
        "declared_source": source,
        "content": sanitize(content, secrets),
        "trace": sanitize(trace, secrets),
        "trace_chars": len(trace),
        "completion_tokens": usage.get("completion_tokens"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "finish_reason": choice.get("finish_reason"),
        "wall_s": wall,
        "census": census_of(payload),
    })
    gold = item["answer"]
    if answer is not None:
        rec["delivered"] = True
        rec["correct"] = (answer == gold)
        rec["outcome"] = "delivered_correct" if rec["correct"] else "delivered_wrong"
    elif (usage.get("completion_tokens") or 0) >= rung:
        rec["outcome"] = "undelivered_truncated"
    else:
        rec["outcome"] = "undelivered_other"
    return rec


def join_key(rec: dict) -> str:
    """Join key on the item (seed and prompt digest), never on the cell label: the defect
    that cost the reference firing its self-agreement row lives in the label, not the item."""
    return f"{rec['seed']}|{rec['prompt_sha256']}"


# ---------------------------------------------------------------- gate

def gate_spec() -> dict:
    """The frozen registration: rows, bands and the tier rule, all decided pre-dispatch."""
    return {
        "schema": GATE_SCHEMA,
        "question": ("On the load-floor ladder family (facts = 2k), does a 27B-class local "
                     "endpoint reproduce the reference firing's wall (the k = 48 cross-path "
                     "answer flip, and the negative arm pinned at 1556 completion tokens), and "
                     "are identical-prompt re-dispatches byte-identical on this class (the "
                     "issue #100 self-agreement control the reference firing owed)?"),
        "serves": ["#71", "#100", "#105", "#126", "#129", "#65"],
        "cells": {
            "levels": list(GRID_LEVELS),
            "rule": ("first two gold-yes and first two gold-no in generation order with facts "
                     "== 2*level exactly; 4 items per cell; constant baseline 0.50 per cell"),
            "pairing": ("k = 24, 40, 48 items are byte-identical (prompt digests pinned) to "
                        "the reference firing's archived grid records; k = 32 is round 50's "
                        "digest-pinned M32 item set, which the reference firing re-dispatched; "
                        "k = 16 is a same-construction anchor (the reference firing did not "
                        "dispatch it, and round 50's M16 band row is a different item: facts "
                        "= 64 against the floor's 32)"),
            "extras": ("the two unselected floor items at k = 48 (both gold-no) run at stage "
                       "extra, so the cross-path arm at the cliff depth carries four items"),
            "duplicates": ("two k = 48 items re-dispatched once at stage dup: the gold-no item "
                           "the reference firing answered wrong, and the smallest-seed "
                           "gold-yes item (the issue #100 control)"),
            "stage1_calls": len(GRID_LEVELS) * 4, "extra_calls": len(EXTRA48),
            "dup_calls": len(DUP_SEEDS),
            "dispatch_order": ("levels descending (k = 48 first), then extras, then dups: the "
                               "wall question lives in the deep cells, so a wall-clock cutoff "
                               "costs the shallow anchors (k = 16, 24) and not the wall"),
        },
        "rows": [
            {"id": "P1", "kind": "prediction", "arm": "k = 48 gold-no (2 paired + 2 extra)",
             "statement": ("the k = 48 cross-path arm does not reproduce the reference "
                           "firing's flip: at least 3 of the 4 delivered k = 48 gold-no "
                           "answers are correct"),
             "band": "correct >= 3 of 4 (an undelivered item counts as not-correct)"},
            {"id": "P2", "kind": "prediction", "arm": "gold-no natural stops, k in {24,32,40,48}",
             "statement": ("the negative arm's natural stop varies with depth on this class: "
                           "at least 3 distinct completion-token values across the delivered "
                           "gold-no records of the four paired levels"),
             "band": "distinct values >= 3 (row refused when delivered < 5)"},
            {"id": "P3", "kind": "prediction", "arm": "gold-yes natural stops, k = 16..48",
             "statement": ("the positive arm's natural stop grows with depth at 15 to 50 "
                           "tokens per hop, against round 6's 80 and the reference firing's "
                           "28.3 on this family"),
             "band": [15.0, 50.0]},
            {"id": "P4", "kind": "readout", "arm": "label-split cost",
             "statement": ("mean natural stop of gold-no over gold-yes per cell, over "
                           "delivered uncensored records only; reportable when at least 3 of "
                           "the 5 cells carry both arms"),
             "band": "reported or refused"},
            {"id": "P5", "kind": "readout", "arm": "cross-class join (zero prompts)",
             "statement": ("join the 16 paired items on (level, seed) to the reference "
                           "firing's archived outcomes; exact McNemar on matched "
                           "correct/incorrect pairs; per-arm completion-token deltas; both "
                           "sides' trace exposure stated (reference: "
                           + ROUND51_CENSUS + ", 16-hex model digest "
                           + ROUND51_MODEL_DIGEST + "; this firing: this round's census and "
                           "digest)"),
             "band": "reported"},
            {"id": "N1", "kind": "census", "arm": "issue #105 exposure",
             "statement": "the reasoning-supplying field is open on at least 90% of records",
             "band": "share >= 0.90"},
            {"id": "N2", "kind": "control", "arm": "issue #100 self-agreement",
             "statement": ("both in-firing duplicate re-dispatches are byte-identical to "
                           "their grid original (content and trace) and token-identical"),
             "band": "byte_identical >= 2 of 2"},
            {"id": "N3", "kind": "control", "arm": "pairing certification",
             "statement": ("all 18 pinned prompts (16 reference-firing rows, 4 of which are "
                           "also round 50's M32 anchors, plus 2 extra floor items) regenerate "
                           "byte-identically from the shipped generator before any prompt is "
                           "spent; the gate refuses to dispatch if any pin moves"),
             "band": "certified == 22 of 22 (16 + 4 + 2), anchors == 4 of 4 at k = 16"},
        ],
        "tier_rule": [
            "N3 uncertified -> refused_no_dispatch (fatal before any prompt is spent)",
            "P1 fail -> cross_path_cliff_class_invariant (delivered wrong cross-path answers "
            "at k = 48 on both classes: the accuracy boundary d* <= 48 on the cross-path arm "
            "is class-shared, not a flash artifact)",
            "P1 pass -> cross_path_cliff_flash_specific (the k = 48 flip does not reproduce: "
            "the wall at the floor is a capability artifact of the small class)",
            "otherwise -> ambiguous",
        ],
        "flags": [
            "P2 fail (delivered >= 5, distinct < 3) -> negative_arm_pin_reproduced (a "
            "depth-invariant negative-arm length on this class; the pinned value is reported)",
            "any gold-no record truncated at 2048 -> wall_is_label_split (against issue #126's "
            "zero-truncation claim; reported beside the tier)",
            "N2 pass -> self_agreement_holds_at_temperature_0 (the issue #100 control owed by "
            "the reference firing holds on this class)",
        ],
        "readout_policy": ("answer field only; the trace-recovery rules stay refused after "
                           "round 50's calibration failure (agreement 0.5652), so no claim in "
                           "this round rests on a trace-derived verdict. Trace text is stored "
                           "for prefix identity and length only. The cross-class comparison is "
                           "an answer-level claim with both sides' trace exposure stated "
                           "(issue #105)."),
        "budget": {"call_cap": CALL_CAP, "max_tokens": MAX_TOKENS, "temperature": 0.0,
                   "dispatch_budget_s": DISPATCH_BUDGET_S, "planned_calls": 25,
                   "concurrency": CONCURRENCY},
        "reference": {"round51_raw_blob_sha256": ROUND51_RAW_BLOB_SHA256,
                      "round51_rows": len(ROUND51_REF),
                      "round51_firing": ROUND51_FIRING,
                      "round51_model_digest": ROUND51_MODEL_DIGEST,
                      "round51_census": ROUND51_CENSUS,
                      "round50_m32_rows": len(ROUND50_M32),
                      "round50_raw_blob_sha256": ROUND50_RAW_BLOB_SHA256,
                      "round6_fit": ROUND6_FIT},
    }


def gate_blob_sha256() -> str:
    return hashlib.sha256(json.dumps(gate_spec(), sort_keys=True).encode()).hexdigest()


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p for discordant pair counts b, c (X ~ Binom(b+c, 0.5))."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1))
    return min(1.0, 2.0 * tail / (2 ** n))


def evaluate_gate(records: list, health: dict) -> dict:  # noqa: C901
    grid = [r for r in records if r["stage"] == "grid"]
    extras = [r for r in records if r["stage"] == "extra"]
    dups = [r for r in records if r["stage"] == "dup"]
    res: dict = {}

    # N3: pairing certification (pure recomputation, fail-closed).
    cert = certify_pairing(build_cells())
    res["N3"] = {"kind": "control", "ok": cert["ok"], "certified": cert["certified"],
                 "certified_target": 22, "anchors": cert["anchors"], "anchors_target": 4,
                 "refused": cert["refused"],
                 "pass": cert["ok"] and cert["certified"] == 22 and cert["anchors"] == 4}

    # P1: the k = 48 cross-path arm (2 paired + 2 extra, all gold-no).
    no48 = [r for r in grid if r["level"] == 48 and r["gold"] == "no"] + extras
    correct48 = sum(1 for r in no48 if r.get("correct") is True)
    res["P1"] = {"kind": "prediction", "n": len(no48), "delivered":
                 sum(1 for r in no48 if r.get("delivered")), "correct": correct48,
                 "pass": correct48 >= 3}

    # P2: distinct gold-no stops over the four paired levels.
    no_recs = [r for r in grid if r["gold"] == "no" and r["level"] in PAIRED_LEVELS
               and r.get("delivered") and r.get("completion_tokens") is not None]
    stops = [r["completion_tokens"] for r in no_recs]
    distinct = len(set(stops))
    if len(stops) < 5:
        res["P2"] = {"kind": "prediction", "n_delivered": len(stops), "refused": True,
                     "distinct_values": distinct, "pass": None,
                     "why": "delivered < 5, row refused"}
    else:
        res["P2"] = {"kind": "prediction", "n_delivered": len(stops), "refused": False,
                     "distinct_values": distinct, "stops": sorted(stops),
                     "pass": distinct >= 3}

    # P3: positive-arm slope over the five levels.
    per_level: dict = {}
    for level in GRID_LEVELS:
        yes = [r["completion_tokens"] for r in grid
               if r["level"] == level and r["gold"] == "yes" and r.get("delivered")
               and r.get("completion_tokens") is not None]
        per_level[level] = (round(sum(yes) / len(yes), 3) if yes else None)
    if any(v is None for v in per_level.values()):
        res["P3"] = {"kind": "prediction", "refused": True, "pass": None,
                     "mean_stop_by_level": per_level,
                     "why": "a level carries no delivered gold-yes record"}
    else:
        xs = list(GRID_LEVELS)
        ys = [per_level[l] for l in xs]
        mx = sum(xs) / len(xs)
        my = sum(ys) / len(ys)
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / \
            sum((x - mx) ** 2 for x in xs)
        res["P3"] = {"kind": "prediction", "refused": False,
                     "mean_stop_by_level": per_level,
                     "slope_tokens_per_hop": round(slope, 2),
                     "pass": 15.0 <= slope <= 50.0}

    # P4: label-split cost ratio per cell, delivered uncensored records only.
    per_cell = []
    for level in GRID_LEVELS:
        yes = [r["completion_tokens"] for r in grid
               if r["level"] == level and r["gold"] == "yes" and r.get("delivered")
               and r.get("finish_reason") != "length"]
        no = [r["completion_tokens"] for r in grid
              if r["level"] == level and r["gold"] == "no" and r.get("delivered")
              and r.get("finish_reason") != "length"]
        censored_no = sum(1 for r in grid
                          if r["level"] == level and r["gold"] == "no"
                          and r.get("finish_reason") == "length")
        if yes and no:
            per_cell.append({"level": level, "mean_yes_stop": sum(yes) / len(yes),
                             "mean_no_stop": sum(no) / len(no),
                             "ratio": (sum(no) / len(no)) / (sum(yes) / len(yes)),
                             "censored_no": censored_no})
    reportable = len(per_cell) >= 3
    res["P4"] = {"kind": "readout", "per_cell": per_cell, "reportable": reportable,
                 "pass": None}

    # P5: cross-class join (pure analysis over the 16 paired items).
    ref = {(row[0], row[1]): row for row in ROUND51_REF}
    this = {(r["level"], r["seed"]): r for r in grid if r["level"] in PAIRED_LEVELS}
    joined = 0
    detail = []
    b = c = 0
    excluded = []
    arm_stops = {"yes": [], "no": []}
    arm_ref_stops = {"yes": [], "no": []}
    for key, row in sorted(ref.items()):
        level, seed, facts, gold, sha, r_stop, r_finish, r_correct, r_declared = row
        r = this.get(key)
        if r is None:
            excluded.append({"level": level, "seed": seed, "why": "not dispatched"})
            continue
        digest_ok = r["prompt_sha256"] == sha
        joined += 1
        detail.append({"level": level, "seed": seed, "digest_ok": digest_ok,
                       "ref_stop": r_stop, "ref_finish": r_finish,
                       "ref_correct": r_correct, "ref_declared": r_declared,
                       "this_stop": r.get("completion_tokens"),
                       "this_finish": r.get("finish_reason"),
                       "this_correct": r.get("correct"),
                       "this_declared": r.get("declared")})
        if r.get("delivered") and r.get("completion_tokens") is not None:
            arm_stops[gold].append(r["completion_tokens"])
            arm_ref_stops[gold].append(r_stop)
        if not (r.get("delivered") and r_correct is not None):
            excluded.append({"level": level, "seed": seed,
                             "why": "this firing did not deliver an answer"})
            continue
        if r_correct and r.get("correct") is False:
            b += 1
        elif r_correct is False and r.get("correct") is True:
            c += 1
    def _delta(arm):
        if not arm_stops[arm] or not arm_ref_stops[arm]:
            return None
        return round(sum(arm_stops[arm]) / len(arm_stops[arm])
                     - sum(arm_ref_stops[arm]) / len(arm_ref_stops[arm]), 1)
    res["P5"] = {"kind": "readout", "joined": joined, "n_ref": len(ref), "detail": detail,
                 "excluded": excluded, "mcnemar": {"b": b, "c": c,
                                                   "p": mcnemar_exact(b, c)},
                 "per_arm_delta_this_minus_ref": {"yes": _delta("yes"), "no": _delta("no")},
                 "pass": None}

    # N1: census exposure.
    n = len(records)
    exposed = sum(1 for r in records
                  if (r.get("census") or {}).get("reasoning_source"))
    res["N1"] = {"kind": "census", "n": n, "exposed": exposed,
                 "share": round(exposed / n, 4) if n else None,
                 "pass": bool(n) and exposed / n >= 0.90}

    # N2: in-firing self-agreement, keyed on the item.
    by_key: dict = {}
    for r in records:
        if r["stage"] == "grid":
            by_key.setdefault(join_key(r), []).append(r)
    dup_rows = []
    for r in dups:
        originals = by_key.get(join_key(r)) or []
        if not originals:
            dup_rows.append({"pair": join_key(r), "joined": False})
            continue
        orig = originals[0]
        same_bytes = (orig["content"], orig["trace"]) == (r["content"], r["trace"])
        same_tokens = (orig["completion_tokens"] == r["completion_tokens"]
                       and orig.get("prompt_tokens") == r.get("prompt_tokens"))
        dup_rows.append({"pair": join_key(r), "joined": True, "byte_identical": same_bytes,
                         "token_identical": same_tokens,
                         "same_answer": orig["declared"] == r["declared"],
                         "tokens": [orig["completion_tokens"], r["completion_tokens"]]})
    bi = sum(1 for d in dup_rows if d.get("byte_identical"))
    res["N2"] = {"kind": "control", "n": len(dup_rows), "byte_identical": bi,
                 "rows": dup_rows,
                 "pass": len(dup_rows) == 2 and bi == 2}

    # Tier and flags.
    if not res["N3"]["pass"]:
        tier = "refused_no_dispatch"
    elif res["P1"]["pass"]:
        tier = "cross_path_cliff_flash_specific"
    elif res["P1"]["n"] == 4 and not res["P1"]["pass"]:
        tier = "cross_path_cliff_class_invariant"
    else:
        tier = "ambiguous"
    flags = []
    if res["P2"].get("pass") is False:
        flags.append("negative_arm_pin_reproduced")
    if any(r.get("finish_reason") == "length" for r in records if r.get("gold") == "no"):
        flags.append("wall_is_label_split")
    if res["N2"]["pass"]:
        flags.append("self_agreement_holds_at_temperature_0")
    return {"rows": res, "tier": tier, "flags": flags,
            "schema": GATE_SCHEMA, "certification": cert}


# ---------------------------------------------------------------- summary

def grid_table(records: list) -> list:
    out = []
    for level in GRID_LEVELS:
        cell = f"F{level:03d}"
        for arm in ("yes", "no", "all"):
            rows = [r for r in records if r["stage"] == "grid" and r["cell"] == cell
                    and (arm == "all" or r["gold"] == arm)]
            if not rows:
                continue
            delivered = [r for r in rows if r.get("delivered")]
            stops = [r["completion_tokens"] for r in delivered
                     if r.get("completion_tokens") is not None]
            out.append({
                "cell": cell, "arm": arm, "level": level,
                "n": len(rows), "delivered": len(delivered),
                "correct": sum(1 for r in delivered if r.get("correct") is True),
                "mean_stop_tokens": round(sum(stops) / len(stops), 3) if stops else None,
                "max_stop_tokens": max(stops) if stops else None,
                "mean_trace_chars": (round(sum(r.get("trace_chars") or 0 for r in rows)
                                           / len(rows), 1) if rows else None),
                "accuracy_over_delivered": (round(len([r for r in delivered
                                                       if r.get("correct") is True])
                                                  / len(delivered), 4) if delivered else None),
            })
    return out


def summarize(records: list, gate: dict, digest: str, health: dict | None = None) -> dict:
    delivered = [r for r in records if r.get("delivered")]
    correct = [r for r in delivered if r.get("correct") is True]
    wrong = [r for r in delivered if r.get("correct") is False]
    truncated = [r for r in records if not r.get("delivered")
                 and r.get("finish_reason") == "length"]
    other_undelivered = [r for r in records if not r.get("delivered")
                         and r.get("finish_reason") != "length"
                         and r.get("outcome") not in ("transport_error",
                                                      "malformed_response",
                                                      "censored_by_cap")]
    no_recs = [r for r in records if r["stage"] == "grid" and r["gold"] == "no"
               and r["level"] in PAIRED_LEVELS and r.get("delivered")
               and r.get("completion_tokens") is not None]
    stops = [r["completion_tokens"] for r in no_recs]
    counts = Counter(stops)
    pinned, pinned_n = (counts.most_common(1)[0] if counts else (None, 0))
    per_level = {}
    for level in PAIRED_LEVELS:
        s = [r["completion_tokens"] for r in no_recs if r["level"] == level]
        per_level[level] = round(sum(s) / len(s), 3) if s else None
    rows = gate["rows"]
    return {
        "answer_level_ledger": {
            "delivered": len(delivered), "delivered_correct": len(correct),
            "delivered_wrong": len(wrong), "undelivered_truncated": len(truncated),
            "undelivered_other": len(other_undelivered),
            "accuracy_over_delivered": wilson(len(correct), len(delivered)),
            "accuracy_over_n": wilson(len(correct), len(records)),
        },
        "dispatches": len(records),
        "transport_errors": sum(1 for r in records if r.get("error")),
        "retries": sum(1 for r in records if (r.get("attempts") or 1) > 1),
        "prompt_tokens": sum(r.get("prompt_tokens") or 0 for r in records),
        "completion_tokens": sum(r.get("completion_tokens") or 0 for r in records),
        "wall_s": round(sum(r.get("wall_s") or 0 for r in records), 1),
        "model_digest": digest,
        "health": health,
        "gate": {"tier": gate["tier"], "flags": gate["flags"],
                 "schema": gate["schema"]},
        "grid_table": grid_table(records),
        "pin": {"n_delivered_no": len(stops), "stops": sorted(stops),
                "distinct_values": len(set(stops)),
                "pinned_value": pinned, "pinned_count": pinned_n,
                "mean_stop_by_level": per_level},
        "slope": {"mean_stop_by_level": rows["P3"].get("mean_stop_by_level"),
                  "slope_tokens_per_hop": rows["P3"].get("slope_tokens_per_hop")},
        "ratios": {"per_cell": rows["P4"]["per_cell"], "reportable": rows["P4"]["reportable"]},
        "cross_class": rows["P5"],
        "duplicates": rows["N2"]["rows"],
        "certification": gate["certification"],
        "reference_firing": {"firing": ROUND51_FIRING,
                             "model_digest": ROUND51_MODEL_DIGEST,
                             "census": ROUND51_CENSUS,
                             "raw_blob_sha256": ROUND51_RAW_BLOB_SHA256},
    }


# ---------------------------------------------------------------- selftest

def _mkrec(stage, level, seed, gold, declared, correct, stop, finish="stop",
           trace="t", content="c", cell=None, attempts=1, error=None) -> dict:
    rec = {"stage": stage, "cell": cell or (f"F{level:03d}" if stage == "grid" else "X048"),
           "gate": "test", "rung": MAX_TOKENS, "is_dup": stage == "dup",
           "dispatch_index": 0, "attempts": attempts, "level": level, "seed": seed,
           "seed_hash": "0" * 16, "gold": gold, "n_facts": 2 * level,
           "n_chains": 2, "prompt_sha256": "f" * 16, "prompt_chars": 100,
           "pair_key": f"{seed}|{'f' * 16}|{MAX_TOKENS}", "error": error,
           "delivered": declared is not None, "outcome": "test",
           "correct": correct, "declared": declared,
           "declared_source": "content" if declared is not None else None,
           "content": content, "trace": trace, "trace_chars": len(trace),
           "completion_tokens": stop, "prompt_tokens": 500,
           "finish_reason": finish, "wall_s": 1.0,
           "census": {"fields": ["content", "reasoning_content"],
                      "reasoning_content_chars": 10, "reasoning_field_chars": 0,
                      "reasoning_source": "reasoning_content"}}
    return rec


def selftest() -> None:
    passed = 0

    def check(cond, msg):
        nonlocal passed
        if not cond:
            raise SystemExit(f"selftest FAIL: {msg}")
        passed += 1

    # 1. Prompt template pins, regenerated from the shipped generator.
    item_m32 = ladders.generate_item(32, 84261011)
    check(prompt_digest(item_m32) == "d6b9e74cf69a8e28", "M32 pin digest moved")
    slipped = dict(item_m32)
    slipped["rule"] = item_m32["rule"] + " "
    check(prompt_digest(slipped) != prompt_digest(item_m32),
          "planted template slip not detected")
    item48 = ladders.generate_item(48, 116261051)
    check(prompt_digest(item48) == "068bc6a1fb0620fb", "reference k48 pin digest moved")

    # 2. check_item guards (issue #67 battery) over a shipped-corpus item.
    series8 = generate_floor(8)
    it = series8[0]
    check_item(it)
    check(True, "shipped-corpus item validates")
    flipped = dict(it)
    if it["answer"] == "yes":
        flipped["answer"] = "no"
        flipped["chain_len"] = None
    else:
        flipped["answer"] = "yes"
        flipped["chain_len"] = it["level"]
    try:
        check_item(flipped)
        check(False, "planted gold flip accepted")
    except AssertionError:
        check(True, "planted gold flip refused")
    badlen = dict(it)
    badlen["chain_len"] = (it["level"] + 1) if it["answer"] == "yes" else 1
    if badlen["answer"] == "no":
        badlen["answer"] = "yes"
        badlen["query"] = [it["facts"][0][0], ladders.REL, it["facts"][-1][2]]
    try:
        check_item(badlen)
        check(False, "planted chain_len slip accepted")
    except AssertionError:
        check(True, "planted chain_len slip refused")
    non_iso = {"level": 2,
               "facts": [["a", "precedes", "b"], ["b", "precedes", "c"],
                         ["d", "precedes", "e"]],
               "query": ["a", "precedes", "c"], "answer": "yes", "chain_len": 2}
    try:
        check_item(non_iso)
        check(False, "non-isomorphic components accepted")
    except AssertionError:
        check(True, "non-isomorphic components refused")

    # 3. Selection rule: independent re-scan, plus the band-tolerance variant that selects
    #    a different item set (the reference round's selection guard).
    series24 = generate_floor(24)
    got_y = got_n = 0
    manual = []
    for x in series24:
        if len(x["facts"]) != 48:
            continue
        if x["answer"] == "yes" and got_y < 2:
            manual.append(x)
            got_y += 1
        elif x["answer"] == "no" and got_n < 2:
            manual.append(x)
            got_n += 1
        if got_y == 2 and got_n == 2:
            break
    check([x["seed"] for x in manual] == [x["seed"] for x in pick_floor(series24, 24)],
          "pick_floor disagrees with the independent scan")
    tol = []
    gy = gn = 0
    for x in series24:
        if not (48 <= len(x["facts"]) <= 72):
            continue
        if x["answer"] == "yes" and gy < 2:
            tol.append(x)
            gy += 1
        elif x["answer"] == "no" and gn < 2:
            tol.append(x)
            gn += 1
        if gy == 2 and gn == 2:
            break
    check([x["seed"] for x in tol] != [x["seed"] for x in manual],
          "band-tolerance variant selects the same set (guard vacuous)")

    # 4. Series determinism and the shipped-file identity (level 8 ships a file).
    check(generate_floor(8) is series8, "series memoization broken")
    shipped = REPO / "items" / "ladders" / "l8.jsonl"
    if shipped.exists():
        disk = [json.loads(l) for l in shipped.read_text().splitlines()]
        check(series8[:len(disk)] == disk, "regenerated l8 differs from the shipped file")

    # 5. Pairing certification: the real pins pass.
    cells = build_cells()
    cert = certify_pairing(cells)
    check(cert["ok"] and cert["certified"] == 22 and cert["anchors"] == 4
          and not cert["refused"], f"real certification failed: {cert}")

    # 6. Pairing certification: planted drifts are all refused.
    ref_bad_sha = tuple(
        (row if row[1] != 68261051
         else (row[0], row[1], row[2], row[3], "0" * 16, row[5], row[6], row[7], row[8]))
        for row in ROUND51_REF)
    c = certify_pairing(cells, ref=ref_bad_sha)
    check(not c["ok"] and any("prompt digest moved" in r["why"] for r in c["refused"]),
          "planted ref digest slip not refused")
    ref_bad_gold = tuple(
        (row if row[1] != 68261092
         else (row[0], row[1], row[2], "yes", row[4], row[5], row[6], row[7], row[8]))
        for row in ROUND51_REF)
    c = certify_pairing(cells, ref=ref_bad_gold)
    check(not c["ok"] and any("gold label moved" in r["why"] for r in c["refused"]),
          "planted ref gold flip not refused")
    ref_missing = tuple(row for row in ROUND51_REF if row[1] != 68261108)
    c = certify_pairing(cells, ref=ref_missing)
    check(not c["ok"] and any("seed set moved" in r["why"] for r in c["refused"]),
          "planted seed-set drift not refused")
    extra_bad = ((116261303, "no", "1" * 16), (116261347, "no", "a062b0f0fd5b5dc0"))
    c = certify_pairing(cells, extra=extra_bad)
    check(not c["ok"] and any("extra floor item moved" in r["why"] for r in c["refused"]),
          "planted extra-item slip not refused")
    m32_bad = tuple(
        (row if row[0] != 84261050 else (row[0], row[1], row[2], "2" * 16))
        for row in ROUND50_M32)
    c = certify_pairing(cells, m32=m32_bad)
    check(not c["ok"] and any("M32 anchor moved" in r["why"] for r in c["refused"]),
          "planted M32 anchor slip not refused")

    # 7. Gate blob: canonical and pinned.
    check(gate_blob_sha256() == gate_blob_sha256(), "gate blob not deterministic")
    if ROUND52_GATE_BLOB_SHA256:
        check(gate_blob_sha256() == ROUND52_GATE_BLOB_SHA256, "gate blob moved off its pin")

    # 8. Exact McNemar against hand-computed values.
    check(mcnemar_exact(0, 0) == 1.0, "mcnemar (0,0)")
    check(mcnemar_exact(1, 0) == 1.0, "mcnemar (1,0)")
    check(mcnemar_exact(4, 1) == 0.375, "mcnemar (4,1)")
    check(mcnemar_exact(2, 2) == 1.0, "mcnemar (2,2)")
    check(abs(mcnemar_exact(5, 2) - 0.453125) < 1e-12, "mcnemar (5,2)")

    # 9. Wilson interval pins.
    check(wilson(0, 0) == (None, None), "wilson (0,0)")
    check(wilson(13, 16) == (0.5699, 0.9341), "wilson (13,16)")
    check(wilson(1, 1) == (0.2065, 1.0), "wilson (1,1)")

    # 10. Answer readout.
    check(declared_answer("No.") == "no", "declared No.")
    check(declared_answer("") is None, "declared empty")
    check(declared_answer("yes then no") == "no", "declared last-wins")
    check(declared_answer("maybe") is None, "declared absent")

    # 11. Answer-channel parse: list content, trace-only, channel preference.
    msg = {"content": [{"text": "no "}, {"text": "again"}]}
    a, s, content, _ = parse_answer_field(msg)
    check(a == "no" and s == "content" and content == "no again", "list content parse")
    msg = {"content": "", "reasoning_content": "think", "reasoning": "think2"}
    a, s, _, trace = parse_answer_field(msg)
    check(a is None and s == "none" and trace == "think", "trace-only record")
    msg = {"content": "yes", "reasoning_content": "", "reasoning": "only"}
    a, _, _, trace = parse_answer_field(msg)
    check(a == "yes" and trace == "only", "reasoning fallback when content channel empty")

    # 12. Census merge rule (issue #105).
    p = {"choices": [{"message": {"role": "a", "content": "x",
                                  "reasoning_content": "rc", "reasoning": "rf"}}]}
    c = census_of(p)
    check(c["reasoning_source"] == "reasoning_content"
          and c["fields"] == ["content", "reasoning", "reasoning_content"],
          "census merge rule (both open)")
    p = {"choices": [{"message": {"role": "a", "content": "x", "reasoning": "rf"}}]}
    check(census_of(p)["reasoning_source"] == "reasoning", "census (reasoning only)")
    p = {"choices": [{"message": {"role": "a", "content": "x"}}]}
    check(census_of(p)["reasoning_source"] == "", "census (closed)")
    p = {"choices": []}
    check(census_of(p)["reasoning_source"] == "", "census (malformed payload)")

    # 13. Sanitizer over fixtures assembled from fragments (repo-facing text stays clean).
    ip_doc = "192." + "0.2." + "100"
    host_doc = "example." + "host" + ".invalid"
    url = "htt" + "p://" + ip_doc + ":8082/v1"
    out = sanitize("see " + url + " and " + ip_doc + " end", secrets=("sekret",))
    check("redacted" in out and ip_doc not in out
          and "sekret" not in sanitize("sekret here", secrets=("sekret",)),
          "sanitizer URL/IP/secret")
    out = sanitize("host=" + "abc123" + " token: t_999", secrets=())
    check("abc123" not in out and "t_999" not in out, "sanitizer credential pattern")
    out = sanitize("fe80:1234:abcd:5678:" + "1234:abcd:5678:9abc", secrets=())
    check("9abc" not in out, "sanitizer IPv6")
    out = sanitize("see " + url, secrets=(url,))
    check(url not in out, "sanitizer explicit secret value")
    check(len(ip_doc) == 11 and ip_doc.count(".") == 3
          and host_doc.endswith(".invalid"), "fixture assembly stays literal-free")

    # 14. Record scoring paths.
    good = {"choices": [{"message": {"role": "a", "content": "no",
                                     "reasoning_content": "trace"},
                         "finish_reason": "stop"}],
            "usage": {"completion_tokens": 100, "prompt_tokens": 50}}
    job = ("F024", False, 0, "grid", False, 0, ())
    item24 = ladders.generate_item(24, 68261051)
    rec = score_record(job, item24, {"payload": good, "wall": 1.0}, None, MAX_TOKENS, "g")
    check(rec["delivered"] and rec["correct"] is True and rec["declared"] == "no"
          and rec["declared_source"] == "content", "score delivered-correct")
    rec = score_record(job, item24, {"payload": {"choices": []}, "wall": 1.0},
                       None, MAX_TOKENS, "g")
    check(rec["outcome"] == "malformed_response", "score malformed payload")
    rec = score_record(job, item24, None, "transport:HTTPError", MAX_TOKENS, "g")
    check(rec["outcome"] == "transport_error" and rec["error"] == "transport:HTTPError",
          "score transport error")
    rec = score_record(job, item24, None, "censored_by_cap", 0, "g")
    check(rec["outcome"] == "censored_by_cap", "score censored record")
    trunc = {"choices": [{"message": {"role": "a", "content": "",
                                      "reasoning_content": "still"},
                          "finish_reason": "length"}],
             "usage": {"completion_tokens": MAX_TOKENS, "prompt_tokens": 50}}
    rec = score_record(job, item24, {"payload": trunc, "wall": 9.0}, None, MAX_TOKENS, "g")
    check(rec["outcome"] == "undelivered_truncated" and not rec["delivered"],
          "score truncated record")

    # 15. Duplicate join keyed on the item, not the cell label.
    grid_orig = _mkrec("grid", 48, 116261051, "no", "no", True, 1556,
                       trace="TRACE", content="no")
    dup_ok = _mkrec("dup", 48, 116261051, "no", "no", True, 1556,
                    trace="TRACE", content="no", cell="DUP-OTHER")
    dup_diff = _mkrec("dup", 48, 116261051, "no", "yes", False, 1400,
                      trace="other", content="yes", cell="DUP-OTHER")
    dup_lost = _mkrec("dup", 48, 99999999, "no", "no", True, 1556, cell="DUP-OTHER")
    rows = evaluate_gate([grid_orig, dup_ok, dup_diff, dup_lost], {})["rows"]["N2"]["rows"]
    pair_key = f"116261051|{'f' * 16}"
    joined = [r for r in rows if r["pair"] == pair_key]
    check(len(rows) == 3 and len(joined) == 2, "dup join (label-defect control)")
    check(joined[0]["byte_identical"] is True and joined[0]["token_identical"] is True
          and joined[0]["same_answer"] is True, "dup byte/token identity (identical)")
    check(joined[1]["byte_identical"] is False and joined[1]["token_identical"] is False,
          "dup byte/token identity (slipped)")
    check(any(r["joined"] is False for r in rows), "dup without original not joined")

    # 16. Join key arithmetic.
    a = _mkrec("grid", 48, 116261051, "no", "no", True, 1556, cell="F048")
    b = _mkrec("grid", 48, 116261051, "no", "no", True, 1556, cell="DUP-OTHER")
    check(join_key(a) == join_key(b), "join key ignores the cell label")

    # 17. P1 boundary (k = 48 gold-no, 2 grid + 2 extra): 3 correct passes, 2 fails.
    recs3 = ([_mkrec("grid", 48, 1, "no", "no", True, 1556),
              _mkrec("grid", 48, 2, "no", "no", True, 1556)] +
             [_mkrec("extra", 48, 3, "no", "no", True, 1556),
              _mkrec("extra", 48, 4, "no", "yes", False, 1556)])
    g = evaluate_gate(recs3, {})
    check(g["rows"]["P1"]["pass"] is True and g["rows"]["P1"]["n"] == 4
          and g["tier"] == "cross_path_cliff_flash_specific", "P1 pass tier")
    recs2 = ([_mkrec("grid", 48, 1, "no", "no", True, 1556),
              _mkrec("grid", 48, 2, "no", "no", True, 1556)] +
             [_mkrec("extra", 48, 3, "no", "yes", False, 1556),
              _mkrec("extra", 48, 4, "no", None, None, None, finish="length")])
    g = evaluate_gate(recs2, {})
    check(g["rows"]["P1"]["pass"] is False
          and g["tier"] == "cross_path_cliff_class_invariant",
          "P1 fail tier (undelivered counts as not-correct)")

    # 18. P2: the pin and the refusal.
    recs_pin = [_mkrec("grid", lv, i, "no", "no", True, 1556)
                for lv in (24, 24, 32, 32, 40, 40, 48, 48)
                for i in (1, 2)]
    g = evaluate_gate(recs_pin, {})
    check(g["rows"]["P2"]["pass"] is False
          and g["rows"]["P2"]["distinct_values"] == 1
          and "negative_arm_pin_reproduced" in g["flags"], "P2 pin reproduced flag")
    recs_var = list(recs_pin[:5]) + [
        _mkrec("grid", 48, 1, "no", "no", True, 1400),
        _mkrec("grid", 48, 2, "no", "no", True, 1700),
        _mkrec("grid", 32, 9, "no", "no", True, 1600)]
    g = evaluate_gate(recs_var, {})
    check(g["rows"]["P2"]["pass"] is True, "P2 variable stops pass")
    g = evaluate_gate(recs_pin[:4], {})
    check(g["rows"]["P2"]["refused"] is True, "P2 refused under-powered")

    # 19. P3 slope boundaries.
    def yes_recs(levels_means):
        out = []
        for lv, mean in levels_means.items():
            out.append(_mkrec("grid", lv, lv * 100, "yes", "yes", True, mean))
        return out
    g = evaluate_gate(yes_recs({16: 520, 24: 718, 32: 915, 40: 1106, 48: 1409}), {})
    check(g["rows"]["P3"]["pass"] is True
          and abs(g["rows"]["P3"]["slope_tokens_per_hop"] - 27.075) < 0.01,
          "P3 in-band slope")
    g = evaluate_gate(yes_recs({16: 400, 24: 850, 32: 1300, 40: 1750, 48: 2200}), {})
    check(g["rows"]["P3"]["pass"] is False
          and abs(g["rows"]["P3"]["slope_tokens_per_hop"] - 56.25) < 0.01,
          "P3 out-of-band slope")
    g = evaluate_gate(yes_recs({16: 520, 24: 718, 32: 915, 40: 1106}), {})
    check(g["rows"]["P3"]["refused"] is True, "P3 refused on missing level")

    # 20. P4 ratios with censored exclusion and reportability.
    recs_p4 = ([_mkrec("grid", lv, 1, "yes", "yes", True, 100)
                for lv in (16, 24, 32, 40, 48)] +
               [_mkrec("grid", lv, 2, "no", "no", True, 200)
                for lv in (16, 24, 32, 40, 48)] +
               [_mkrec("grid", 48, 3, "no", None, None, 2048, finish="length")])
    g = evaluate_gate(recs_p4, {})
    p4 = g["rows"]["P4"]
    check(p4["reportable"] is True
          and all(abs(c["ratio"] - 2.0) < 1e-9 for c in p4["per_cell"])
          and p4["per_cell"][-1]["censored_no"] == 1, "P4 ratio and censor count")
    g = evaluate_gate(recs_p4[:2], {})
    check(g["rows"]["P4"]["reportable"] is False, "P4 under-powered refusal")

    # 21. P5 join: matched-pair counts and exclusions, on real reference seeds.
    r1 = _mkrec("grid", 24, 68261108, "yes", "yes", True, 700)
    r1["prompt_sha256"] = "40e3dfb191140791"
    r2 = _mkrec("grid", 32, 84261050, "no", "no", True, 1556)
    r2["prompt_sha256"] = "0d3347946e358ce5"
    r3 = _mkrec("grid", 32, 84261142, "yes", None, None, None, finish="length")
    r3["prompt_sha256"] = "e9615dd04c8c87a2"
    g = evaluate_gate([r1, r2, r3], {})
    p5 = g["rows"]["P5"]
    check(p5["joined"] == 3 and p5["mcnemar"]["b"] == 0 and p5["mcnemar"]["c"] == 1
          and p5["mcnemar"]["p"] == 1.0, "P5 join and mcnemar (c=1)")
    check(p5["per_arm_delta_this_minus_ref"]["yes"] == -71.0, "P5 per-arm delta")
    check(any(e["seed"] == 84261142 and "did not deliver" in e["why"]
              for e in p5["excluded"]), "P5 undelivered exclusion")

    # 22. N1 census share boundary.
    recs_n1 = [_mkrec("grid", 24, i, "no", "no", True, 100) for i in range(9)]
    recs_n1.append(_mkrec("grid", 24, 99, "no", "no", True, 100))
    recs_n1[-1]["census"] = {"fields": ["content"], "reasoning_content_chars": 0,
                             "reasoning_field_chars": 0, "reasoning_source": ""}
    g = evaluate_gate(recs_n1, {})
    check(g["rows"]["N1"]["pass"] is True and g["rows"]["N1"]["share"] == 0.9,
          "N1 at the 0.90 boundary")
    recs_n1b = recs_n1[:8] + [_mkrec("grid", 24, i, "no", "no", True, 100)
                              for i in range(8, 10)]
    for r in recs_n1b[-2:]:
        r["census"] = dict(recs_n1[-1]["census"])
    g = evaluate_gate(recs_n1b, {})
    check(g["rows"]["N1"]["pass"] is False, "N1 below the boundary")

    # 23. Budget arithmetic and invariants.
    check(1 + len(GRID_LEVELS) * 4 + len(EXTRA48) + len(DUP_SEEDS) == 25 <= CALL_CAP,
          "planned calls exceed the cap")
    check(MAX_TOKENS == 2048 and TIMEOUT_S > 0 and CALL_CAP == 40, "cap invariants")
    check(len(gate_spec()["rows"]) == 8, "gate row count")
    check(gate_spec()["budget"]["planned_calls"] == 25, "gate budget planned calls")

    # 24. Model digest rule.
    check(model_digest_of("x") == hashlib.sha256(b"x").hexdigest()[:16],
          "model digest rule")

    print(f"selftest: {passed} checks passed")
    print(f"gate blob: {gate_blob_sha256()}")


# ---------------------------------------------------------------- dispatch

def read_raw(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def stage_jobs(cells: dict) -> list:
    """The frozen dispatch plan: levels descending, then extras, then dups."""
    jobs = []
    idx = 0
    for level in reversed(GRID_LEVELS):
        for item in cells[f"F{level:03d}"]:
            jobs.append((f"F{level:03d}", item, MAX_TOKENS, "grid", False, idx))
            idx += 1
    for item in cells["_EXTRA"]:
        jobs.append(("X048", item, MAX_TOKENS, "extra", False, idx))
        idx += 1
    for item in cells["_DUP"]:
        jobs.append(("DUP-F048", item, MAX_TOKENS, "dup", True, idx))
        idx += 1
    return jobs


def main(argv: list) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--gate", action="store_true", help="write gate.json and print the blob")
    p.add_argument("--dry-run", action="store_true", help="print the frozen dispatch plan")
    p.add_argument("--run", action="store_true")
    p.add_argument("--resume", action="store_true",
                   help="continue an existing raw.jsonl, refusing on gate-hash drift")
    p.add_argument("--rescore", action="store_true",
                   help="rebuild gate.json/summary.json from raw.jsonl with no endpoint call")
    p.add_argument("--raw", default="raw.jsonl")
    p.add_argument("--summary", default="summary.json")
    p.add_argument("--health", default="health.json")
    a = p.parse_args(argv)

    if a.selftest:
        selftest()
        return 0

    cells = build_cells()
    cert = certify_pairing(cells)
    if not cert["ok"]:
        print(f"REFUSED: pairing does not certify: {cert['refused']}", file=sys.stderr)
        return 2
    blob = gate_blob_sha256()
    if not ROUND52_GATE_BLOB_SHA256:
        print("REFUSED: the gate blob pin is empty; freeze it before dispatch",
              file=sys.stderr)
        return 2
    if blob != ROUND52_GATE_BLOB_SHA256:
        print(f"REFUSED: gate blob {blob} does not match the pin "
              f"{ROUND52_GATE_BLOB_SHA256}", file=sys.stderr)
        return 2

    here = Path(__file__).resolve().parent
    raw_path = here / a.raw
    summary_path = here / a.summary
    health_path = here / a.health

    if a.gate:
        (here / "gate.json").write_text(json.dumps(gate_spec(), indent=2, sort_keys=True) + "\n",
                                        encoding="utf-8")
        print(f"gate.json written, blob {blob}")
        return 0

    if a.rescore:
        records = read_raw(raw_path)
        if not records:
            print("REFUSED: raw.jsonl is empty", file=sys.stderr)
            return 2
        stray = [r for r in records if r.get("gate") != blob]
        if stray:
            print(f"REFUSED: {len(stray)} records carry a different gate hash",
                  file=sys.stderr)
            return 2
        health = json.loads(health_path.read_text(encoding="utf-8")) if health_path.exists() else {}
        digest = records[0].get("model_digest", "")
        gate = evaluate_gate(records, health)
        summary = summarize(records, gate, digest, health)
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                                encoding="utf-8")
        (here / "gate.json").write_text(json.dumps(gate_spec(), indent=2, sort_keys=True) + "\n",
                                        encoding="utf-8")
        print(f"rescored {len(records)} records from raw.jsonl, tier {gate['tier']}")
        return 0

    if a.dry_run:
        jobs = stage_jobs(cells)
        print(f"plan: 1 health + {len(jobs)} dispatches = {1 + len(jobs)} of {CALL_CAP}")
        for cell, item, rung, stage, _is_dup, _idx in jobs:
            print(f"  {cell} [{stage}] seed={item['seed']} gold={item['answer']} "
                  f"facts={len(item['facts'])} rung={rung} chars={len(render_prompt(item))}")
        print(f"certified pins: {cert['certified']} of 22, anchors {cert['anchors']} of 4")
        return 0

    return run_dispatch(a, cells, blob, raw_path, summary_path, health_path)


def run_dispatch(a, cells, blob, raw_path, summary_path, health_path) -> int:  # noqa: C901
    here = Path(__file__).resolve().parent
    base = os.environ.get("NIGHTLY_BASE_URL")
    model = os.environ.get("NIGHTLY_MODEL_ID")
    key = os.environ.get("NIGHTLY_API_KEY") or ""
    if not (base and model):
        print("REFUSED: NIGHTLY_BASE_URL and NIGHTLY_MODEL_ID are required "
              "(NIGHTLY_API_KEY may be empty when the slot serves without a credential)",
              file=sys.stderr)
        return 2
    secrets = (base, model, key, base.split("//")[-1] if "//" in base else "")
    digest = model_digest_of(model)

    records = read_raw(raw_path)
    if a.run and records:
        print("REFUSED: raw.jsonl already exists; use --resume", file=sys.stderr)
        return 2
    if a.resume:
        stray = [r for r in records if r.get("gate") != blob]
        if stray:
            print(f"REFUSED: {len(stray)} existing records carry a different gate hash",
                  file=sys.stderr)
            return 2
    done = {(join_key(r), r["stage"]) for r in records}
    lock = threading.Lock()
    sink = raw_path.open("a", encoding="utf-8")

    def emit(rec: dict) -> None:
        rec["model_digest"] = digest
        with lock:
            sink.write(json.dumps(rec, sort_keys=True) + "\n")
            sink.flush()
            os.fsync(sink.fileno())
        records.append(rec)

    t_start = time.time()
    calls = len(records)

    health = json.loads(health_path.read_text(encoding="utf-8")) if (
        health_path.exists() and a.resume) else None
    if health is None:
        health = health_probe(base, model, key)
        calls += 1
        health_path.write_text(json.dumps({"model_digest": digest, **health}, indent=2,
                                          sort_keys=True) + "\n", encoding="utf-8")
        print(f"health ok={health.get('ok')} wall={health.get('wall_s')} "
              f"tokens={health.get('completion_tokens')} census={health.get('census')}",
              flush=True)
        if not health.get("ok"):
            print("ABORT: health probe failed, no grid dispatched", file=sys.stderr)
            sink.close()
            return 3

    def dispatch(job):
        nonlocal calls
        if calls >= CALL_CAP:
            raise RuntimeError("call cap reached")
        if time.time() - t_start > DISPATCH_BUDGET_S:
            raise RuntimeError("dispatch budget exhausted")
        cell, item, rung, stage, is_dup, idx = job[:6]
        pair = (join_key({"seed": item["seed"], "prompt_sha256": prompt_digest(item)}),
                stage)
        if pair in done:
            return None
        prompt = render_prompt(item)
        attempts = 0
        resp = err = None
        while attempts < 2:
            attempts += 1
            try:
                res = call_endpoint(prompt, base, model, key, rung)
                resp = {"payload": res["payload"], "wall": res["wall_s"]}
                break
            except RuntimeError as exc:
                err = str(exc)
                print(f"  retry {cell} seed={item['seed']} rung={rung}: {err}", flush=True)
        job_full = (cell, item, rung, stage, is_dup, idx, secrets)
        rec = score_record(job_full, item, resp, err, rung, blob)
        rec["attempts"] = attempts
        with lock:
            calls += 1
        emit(rec)
        print(f"  {rec['stage']} {cell} seed={item['seed']} gold={item['answer']} "
              f"-> {rec['outcome']} stop={rec['completion_tokens']} "
              f"finish={rec['finish_reason']} wall={rec['wall_s']} "
              f"(calls={calls})", flush=True)
        return rec

    jobs = stage_jobs(cells)
    cutoff = None
    phase1: list = []
    try:
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            futures = []
            for j in jobs:
                if (join_key({"seed": j[1]["seed"],
                              "prompt_sha256": prompt_digest(j[1])}), j[3]) in done:
                    continue
                futures.append(pool.submit(dispatch, j))
            for f in futures:
                rec = f.result()
                if rec is not None and len(phase1) < 2:
                    phase1.append(rec)
    except RuntimeError as exc:
        cutoff = str(exc)
        print(f"CUTOFF: {exc}; the surviving records are the record", flush=True)
    finally:
        sink.close()

    gate = evaluate_gate(records, health)
    summary = summarize(records, gate, digest, health)
    if cutoff:
        summary["cutoff"] = cutoff
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    (here / "gate.json").write_text(json.dumps(gate_spec(), indent=2, sort_keys=True) + "\n",
                                    encoding="utf-8")

    s = summary
    print("dispatches", s["dispatches"], "transport_errors", s["transport_errors"],
          "retries", s["retries"])
    print("prompt_tokens", s["prompt_tokens"], "completion_tokens",
          s["completion_tokens"], "wall_s", s["wall_s"])
    if phase1:
        p1_tokens = sum(r.get("completion_tokens") or 0 for r in phase1)
        p1_wall = sum(r.get("wall_s") or 0 for r in phase1)
        print("phase1 aggregate:", p1_tokens, "tokens in", p1_wall,
              "s =", round(p1_tokens / p1_wall, 1) if p1_wall else 0, "tok/s "
              f"(concurrency {CONCURRENCY})")
    print("ledger", json.dumps(s["answer_level_ledger"], sort_keys=True))
    print("tier", gate["tier"], "flags", gate["flags"])
    for rid in ("P1", "P2", "P3", "P4", "P5", "N1", "N2", "N3"):
        r = gate["rows"][rid]
        keep = {k: v for k, v in r.items() if k in
                ("pass", "n", "correct", "delivered", "distinct_values", "n_delivered",
                 "refused", "slope_tokens_per_hop", "joined", "mcnemar", "reportable",
                 "byte_identical", "exposed", "certified", "anchors", "ok",
                 "per_arm_delta_this_minus_ref", "certified_target", "anchors_target")}
        print(rid, json.dumps(keep, sort_keys=True)[:400])
    print("PIN", json.dumps(s["pin"], sort_keys=True)[:400])
    print("CUTOFF", cutoff)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

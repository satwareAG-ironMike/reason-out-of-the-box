#!/usr/bin/env python3
"""Independent re-scoring of the 2026-10-14 nightly confidence probe (issue #65).

Reads the archived raw completions and recomputes every number quoted in
docs/next-investigations.md for that round: the item selection, per-arm accuracy,
malformed rate, mean stated confidence, Brier score under the stated-confidence
semantics, high-confidence error rate, and trace faithfulness (does every edge the
model asserts exist in the committed fact graph, and do its numbered steps form a
connected traversal from the query source to the query target?).

No model calls, no network. Stdlib only. Reads only committed repository files plus
the archived raw artifact given as an argument.

Usage:
    python3 research/nightly-2026-10-14-1900/verify_probe.py \
        research/nightly-2026-10-14-1900/probe_round2_raw.jsonl
    python3 research/nightly-2026-10-14-1900/verify_probe.py --selftest

Exit codes:
    0  every quoted number reproduced from the raw artifact
    3  the raw artifact hash does not match the pinned value
    4  a quoted number did not reproduce, or a selftest control was not caught
    2  usage error
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LEVELS = (1, 2, 4, 6, 8)
ITEMS_PER_LEVEL = 3
# Per-level composition of the probe set: levels 1, 4, 8 carry two yes items and one
# no item; levels 2 and 6 carry one yes item and two no items.
WANT_YES = {1: 2, 2: 1, 4: 2, 6: 1, 8: 2}
ARMS = ("A", "B")
HIGH_CONF = 80.0

# sha256 of the archived raw artifact this verifier is pinned to.
PINNED_RAW_SHA256 = "6489b3bf72fda8e6452e1cf10098406ddf04c57f65c9d02ec72acc3662ad5ab3"

CLAIM_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9]*)\s+precedes\s+([A-Za-z][A-Za-z0-9]*)")
NUMBERED_RE = re.compile(r"^\s*(?:Step\s*)?(\d+)[.)]?\s")
CONF_RE = re.compile(r"CONFIDENCE_(BEFORE|AFTER):\s*(\d{1,3})")
ANSWER_RE = re.compile(r"ANSWER:\s*(yes|no)")
# A line is non-assertive framing when it restates the rule, restates the question, or
# denies an edge. Edge assertions are counted only on lines that are not framing.
FRAMING_RE = re.compile(
    r"\b(whether|determine|need|want|question|asks?|no\s+fact|no\s+chain|no\s+path"
    r"|not|nor|never|without|if)\b", re.IGNORECASE)

# Every number quoted in docs/next-investigations.md for the 2026-10-14 round.
QUOTED = {
    "items": 15, "calls": 30,
    "A": {"n": 15, "correct": 15, "malformed": 0, "acc": 1.0, "conf_fields": 0},
    "B": {"n": 15, "correct": 15, "malformed": 0, "acc": 1.0, "conf_before": 98.33,
          "conf_after": 99.6, "brier_before": 0.0006, "brier_after": 0.0,
          "hc_errors": 0},
    "faith": {"enumerated": 20, "steps": 119, "mentions": 208, "framing": 14,
              "assertions": 194, "fact_backed": 159, "derived": 35, "unsupported": 0,
              "unsupported_framing": 5, "connected": 13, "endpoint": 9},
    "accuracy_by_k": {1: 1.0, 2: 1.0, 4: 1.0, 6: 1.0, 8: 1.0},
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


_BY_LEVEL: dict = {}


def committed_level(level: int) -> list:
    """The committed hop_chain items for one level, in file order."""
    if level not in _BY_LEVEL:
        path = REPO / "items" / "ladders" / f"l{level}.jsonl"
        _BY_LEVEL[level] = [json.loads(line)
                            for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return _BY_LEVEL[level]


def select_items() -> list:
    """Re-derive the probe's 15-item selection from the committed item files."""
    picked = []
    for level in LEVELS:
        want_yes = WANT_YES[level]
        want_no = ITEMS_PER_LEVEL - want_yes
        yes: list = []
        no: list = []
        for item in committed_level(level):
            if len(yes) == want_yes and len(no) == want_no:
                break
            if item["answer"] == "yes" and len(yes) < want_yes:
                yes.append(item)
            elif item["answer"] == "no" and len(no) < want_no:
                no.append(item)
        picked.extend(yes + no)
    return picked


def bfs(graph: dict, src: str) -> dict:
    dist = {src: 0}
    parent = {}
    queue = [src]
    while queue:
        u = queue.pop(0)
        for v in graph.get(u, ()):
            if v not in dist:
                dist[v] = dist[u] + 1
                parent[v] = u
                queue.append(v)
    return dist, parent


def path_from_source(item: dict) -> list:
    """A real directed path out of the query source, as edge tuples.

    For a gold-no item this path cannot end at the query target, which is what makes it
    a faithful stand-in for the model's "I followed the links and never reached it" trace.
    """
    graph = defaultdict(list)
    for s, _, t in item["facts"]:
        graph[s].append(t)
    dist, parent = bfs(graph, item["query"][0])
    if len(dist) < 2:
        return []
    deepest = max(dist, key=lambda n: (dist[n], n))
    path = [deepest]
    while path[-1] != item["query"][0]:
        path.append(parent[path[-1]])
    path.reverse()
    return list(zip(path, path[1:]))


def non_entailed_pair(item: dict) -> tuple:
    """An ordered pair of the item's own entities that is neither a fact nor entailed."""
    facts = [tuple(f) for f in item["facts"]]
    edges = {(s, t) for s, _, t in facts}
    reach = closure(facts)
    ents = sorted(item_entities(item))
    for a in ents:
        for b in ents:
            if a != b and (a, b) not in edges and (a, b) not in reach:
                return (a, b)
    raise AssertionError("no non-entailed pair available")


def gold_by_bfs(item: dict) -> str:
    """Independent gold re-derivation: directed BFS from the query source."""
    graph = defaultdict(list)
    for s, _, t in item["facts"]:
        graph[s].append(t)
    dist, _ = bfs(graph, item["query"][0])
    return "yes" if item["query"][2] in dist else "no"


def chain_edges(item: dict) -> list:
    """The directed path the item's query pair is supposed to test, as edge tuples."""
    graph = defaultdict(list)
    for s, _, t in item["facts"]:
        graph[s].append(t)
    dist, parent = bfs(graph, item["query"][0])
    target = item["query"][2]
    if target not in dist:
        return []
    path = [target]
    while path[-1] != item["query"][0]:
        path.append(parent[path[-1]])
    path.reverse()
    return list(zip(path, path[1:]))


def closure(facts: list) -> set:
    """Transitive closure of the committed fact graph."""
    reach = {(s, t) for s, _, t in facts}
    changed = True
    while changed:
        changed = False
        snapshot = list(reach)
        for a, b in snapshot:
            for c, d in snapshot:
                if b == c and (a, d) not in reach:
                    reach.add((a, d))
                    changed = True
    return reach


def item_entities(item: dict) -> set:
    """Every entity name the item itself puts on the table."""
    names = {s for s, _, _ in item["facts"]} | {t for _, _, t in item["facts"]}
    names |= {item["query"][0], item["query"][2]}
    return names


def parse_completion(content: str, entities: set) -> dict:
    """Structured fields, entity-anchored edge mentions, and the numbered step sequence.

    A mention counts only when both endpoints are item entities, which excludes the rule
    sentence's placeholder variables (x, y, z) and prose such as "direct precedes links".
    Mentions on framing lines are separated from edge assertions.
    """
    mentions = []
    numbered = []
    for line in content.splitlines():
        found = [(a, b) for a, b in CLAIM_RE.findall(line) if a in entities and b in entities]
        for a, b in found:
            mentions.append((a, b, bool(FRAMING_RE.search(line))))
        marker = NUMBERED_RE.match(line)
        if marker and found:
            a, b = found[-1]
            numbered.append((int(marker.group(1)), a, b))
    conf = {}
    for m in CONF_RE.finditer(content):
        conf.setdefault(m.group(1), int(m.group(2)))
    answer = None
    tail = content.rfind("ANSWER:")
    if tail != -1:
        m = ANSWER_RE.match(content[tail:])
        if m:
            answer = m.group(1)
    return {"mentions": mentions, "numbered": numbered, "conf": conf, "answer": answer}


def faithfulness(parsed: dict, item: dict) -> dict:
    """Edge support and traversal structure, checked against the committed graph.

    fact_backed : the asserted edge is one of the item's committed facts
    derived     : the assertion is not a fact but is entailed by them
    unsupported : neither, i.e. an invented edge
    connected   : the numbered steps are all committed facts and chain end to end
    endpoint    : the numbered chain starts at the query source and ends at the target
    """
    facts = [tuple(f) for f in item["facts"]]
    edges = {(s, t) for s, _, t in facts}
    reach = closure(facts)
    assertions = [(a, b) for a, b, framed in parsed["mentions"] if not framed]
    framing = [(a, b) for a, b, framed in parsed["mentions"] if framed]
    fact_backed = sum(1 for c in assertions if c in edges)
    derived = sum(1 for c in assertions if c not in edges and c in reach)
    unsupported = len(assertions) - fact_backed - derived
    unsupported_framing = sum(1 for c in framing if c not in edges and c not in reach)

    steps = parsed["numbered"]
    connected = bool(steps)
    for i, (_, a, b) in enumerate(steps):
        if (a, b) not in edges:
            connected = False
        if i + 1 < len(steps) and b != steps[i + 1][1]:
            connected = False
    source, _, target = item["query"]
    endpoint = bool(steps) and steps[0][1] == source and steps[-1][2] == target
    return {
        "mentions": len(parsed["mentions"]),
        "framing": len(framing),
        "assertions": len(assertions),
        "fact_backed": fact_backed,
        "derived": derived,
        "unsupported": unsupported,
        "unsupported_framing": unsupported_framing,
        "steps": len(steps),
        "connected": connected,
        "endpoint": endpoint,
    }


def score(records: list, items: list) -> tuple:
    """Recompute every aggregate from raw completions plus committed items."""
    by_hash = {it["seed_hash"]: it for it in items}
    failures: list = []
    arms: dict = defaultdict(list)
    for rec in records:
        item = by_hash.get(rec["seed_hash"])
        if item is None:
            failures.append(f"seed {rec['seed_hash'][:16]} is not in the re-derived selection")
            continue
        if item["level"] != rec["level"] or item["chain_len"] != rec["chain_len"]:
            failures.append(f"seed {rec['seed_hash'][:16]} item mismatch")
            continue
        gold = gold_by_bfs(item)
        if gold != item["answer"] or gold != rec["gold"]:
            failures.append(f"seed {rec['seed_hash'][:16]} gold disagreement")
            continue
        parsed = parse_completion(rec["completion"], item_entities(item))
        arms[rec["arm"]].append({
            "seed_hash": rec["seed_hash"],
            "level": rec["level"],
            "k": rec["chain_len"],
            "gold": gold,
            "answer": parsed["answer"],
            "conf_before": parsed["conf"].get("BEFORE"),
            "conf_after": parsed["conf"].get("AFTER"),
            "faith": faithfulness(parsed, item),
        })

    archived = {rec["seed_hash"] for rec in records}
    derived_hashes = {it["seed_hash"] for it in items}
    if archived != derived_hashes:
        failures.append("selection mismatch between the archived probe items and the re-derived set")

    stats: dict = {"items": len(archived), "calls": len(records), "failures": failures}
    for arm in ARMS:
        rows = arms[arm]
        n = len(rows)
        correct = sum(1 for r in rows if r["answer"] == r["gold"])
        entry = {"n": n, "correct": correct, "malformed": sum(1 for r in rows if r["answer"] is None),
                 "accuracy": round(correct / n, 4) if n else 0.0, "rows": rows}
        fields = sum(1 for r in rows if r["conf_before"] is not None or r["conf_after"] is not None)
        entry["conf_fields"] = fields
        if fields:
            cb = [r["conf_before"] for r in rows]
            ca = [r["conf_after"] for r in rows]
            entry["conf_before_missing"] = sum(1 for v in cb if v is None)
            entry["conf_after_missing"] = sum(1 for v in ca if v is None)
            entry["conf_before"] = round(sum(cb) / n, 2)
            entry["conf_after"] = round(sum(ca) / n, 2)
            # Stated confidence is P(this answer is correct), so the Brier target is the
            # indicator of the model's own answer matching gold, not the gold label alone.
            entry["brier_before"] = round(sum((v / 100.0 - (1.0 if r["answer"] == r["gold"] else 0.0)) ** 2
                                              for v, r in zip(cb, rows)) / n, 4)
            entry["brier_after"] = round(sum((v / 100.0 - (1.0 if r["answer"] == r["gold"] else 0.0)) ** 2
                                             for v, r in zip(ca, rows)) / n, 4)
            entry["hc_errors"] = sum(1 for v, r in zip(ca, rows)
                                     if v >= HIGH_CONF and r["answer"] != r["gold"])
        stats[arm] = entry

    all_rows = [r for arm in ARMS for r in arms[arm]]
    stats["faith"] = {
        "enumerated": sum(1 for r in all_rows if r["faith"]["steps"] > 0),
        "steps": sum(r["faith"]["steps"] for r in all_rows),
        "mentions": sum(r["faith"]["mentions"] for r in all_rows),
        "framing": sum(r["faith"]["framing"] for r in all_rows),
        "assertions": sum(r["faith"]["assertions"] for r in all_rows),
        "fact_backed": sum(r["faith"]["fact_backed"] for r in all_rows),
        "derived": sum(r["faith"]["derived"] for r in all_rows),
        "unsupported": sum(r["faith"]["unsupported"] for r in all_rows),
        "unsupported_framing": sum(r["faith"]["unsupported_framing"] for r in all_rows),
        "connected": sum(1 for r in all_rows if r["faith"]["connected"]),
        "endpoint": sum(1 for r in all_rows if r["faith"]["endpoint"]),
    }
    stats["accuracy_by_k"] = {}
    for level in LEVELS:
        rows = [r for r in all_rows if r["level"] == level]
        ok = sum(1 for r in rows if r["answer"] == r["gold"])
        stats["accuracy_by_k"][level] = round(ok / len(rows), 4) if rows else 0.0
    return stats, all_rows


def report(stats: dict, all_rows: list) -> list:
    """Print the re-scored record and return the labels that disagree with QUOTED."""
    bad: list = []

    def expect(label: str, got, want) -> None:
        ok = got == want
        print(f"  {label}: {got} (expected {want}) {'OK' if ok else 'MISMATCH'}")
        if not ok:
            bad.append(label)

    print(f"records {stats['calls']}  items {stats['items']}")
    expect("items", stats["items"], QUOTED["items"])
    expect("calls", stats["calls"], QUOTED["calls"])
    for label in stats["failures"]:
        print(f"  FAILURE: {label}")
        bad.append(label)

    for arm in ARMS:
        entry = stats[arm]
        print(f"\narm {arm}: n={entry['n']} correct={entry['correct']} malformed={entry['malformed']}")
        for r in sorted(entry["rows"], key=lambda r: (r["level"], r["gold"], r["seed_hash"])):
            f = r["faith"]
            conf = ""
            if entry["conf_fields"]:
                conf = f" conf_before={r['conf_before']} conf_after={r['conf_after']}"
            print(f"  L{r['level']} k={r['k']} gold={r['gold']} {r['seed_hash'][:12]} "
                  f"answer={r['answer']}{conf} assertions={f['assertions']} fact={f['fact_backed']} "
                  f"derived={f['derived']} unsupported={f['unsupported']} steps={f['steps']} "
                  f"connected={f['connected']} endpoint={f['endpoint']}")
        for key in ("n", "correct", "malformed"):
            expect(f"arm {arm} {key}", entry[key], QUOTED[arm][key])
        expect(f"arm {arm} accuracy", entry["accuracy"], QUOTED[arm]["acc"])
        if arm == "A":
            expect("arm A confidence fields", entry["conf_fields"], QUOTED["A"]["conf_fields"])
        else:
            for key in ("conf_before_missing", "conf_after_missing"):
                expect(f"arm {arm} {key}", entry[key], 0)
            for key in ("conf_before", "conf_after", "brier_before", "brier_after", "hc_errors"):
                expect(f"arm {arm} {key}", entry[key], QUOTED["B"][key])

    faith = stats["faith"]
    print(f"\ntrace faithfulness: {faith['enumerated']} of {stats['calls']} completions enumerate steps")
    for key in ("mentions", "framing", "assertions", "fact_backed", "derived", "unsupported",
                "unsupported_framing", "enumerated", "steps", "connected", "endpoint"):
        expect(key, faith[key], QUOTED["faith"][key])

    print("\naccuracy by depth k:")
    for level in LEVELS:
        got = stats["accuracy_by_k"][level]
        print(f"  k={level}: {got}")
        expect(f"accuracy at k={level}", got, QUOTED["accuracy_by_k"][level])
    return bad


def selftest() -> int:
    """Planted-defect controls: the verifier must catch each one.

    Built from committed items only, so it runs without the archived artifact.
    """
    yes_item = next(it for it in committed_level(4) if it["answer"] == "yes")
    no_item = next(it for it in committed_level(4) if it["answer"] == "no")
    chain = chain_edges(yes_item)
    dead_end = path_from_source(no_item)
    invented = non_entailed_pair(yes_item)
    assert chain and dead_end, "committed items must provide a chain and a reachable dead end"
    assert len(chain) >= 2, "the reorder control needs at least two chain steps"

    def synth(item: dict, edges: list, answer: str, arm: str, conf=None) -> dict:
        lines = []
        if conf:
            lines.append(f"CONFIDENCE_BEFORE: {conf[0]}")
        for i, (a, b) in enumerate(edges, 1):
            lines.append(f"{i}. {a} precedes {b}")
        lines.append(f"ANSWER: {answer}")
        if conf:
            lines.append(f"CONFIDENCE_AFTER: {conf[1]}")
        return {"arm": arm, "level": item["level"], "chain_len": item["chain_len"],
                "gold": item["answer"], "seed_hash": item["seed_hash"],
                "completion": "\n".join(lines)}

    def dataset(records) -> tuple:
        return score(records, [yes_item, no_item])

    base = [synth(yes_item, chain, "yes", "A"), synth(no_item, dead_end, "no", "A"),
            synth(yes_item, chain, "yes", "B", (90, 95)), synth(no_item, dead_end, "no", "B", (90, 95))]
    stats, rows = dataset(base)
    problems: list = []

    def check(label: str, cond: bool) -> None:
        print(f"  {label}: {'caught' if cond else 'MISSED'}")
        if not cond:
            problems.append(label)

    print("control 0: clean synthetic dataset must score clean")
    check("clean unsupported edges zero", stats["faith"]["unsupported"] == 0)
    check("clean gold re-derivation agrees", not stats["failures"])
    check("clean connected chains", stats["faith"]["connected"] == 4)
    check("clean endpoint chains", stats["faith"]["endpoint"] == 2)
    check("clean accuracy", stats["A"]["accuracy"] == 1.0 and stats["B"]["accuracy"] == 1.0)
    check("clean brier below 0.01", stats["B"]["brier_after"] < 0.01)

    print("control 1: flipped answer on a gold-no item")
    flipped = copy.deepcopy(base)
    flipped[1]["completion"] = flipped[1]["completion"].replace("ANSWER: no", "ANSWER: yes")
    flipped[3]["completion"] = flipped[3]["completion"].replace("ANSWER: no", "ANSWER: yes")
    stats, _ = dataset(flipped)
    check("arm accuracy drops", stats["A"]["accuracy"] < 1.0)
    check("high-confidence error counted", stats["B"]["hc_errors"] == 1)
    check("brier rises", stats["B"]["brier_after"] > QUOTED["B"]["brier_after"])

    print("control 2: invented edge (entity pair that is not a fact and not entailed)")
    defect2 = copy.deepcopy(base)
    defect2[0]["completion"] = defect2[0]["completion"].replace(
        "ANSWER: yes", f"9. {invented[0]} precedes {invented[1]}\nANSWER: yes")
    stats, _ = dataset(defect2)
    check("unsupported edge counted", stats["faith"]["unsupported"] == 1)
    check("chain no longer connected", stats["faith"]["connected"] < 4)

    print("control 3: reordered numbered steps")
    reordered = copy.deepcopy(base)
    steps = [f"{i}. {a} precedes {b}" for i, (a, b) in enumerate(chain, 1)]
    reordered[0]["completion"] = "\n".join(
        [steps[1], steps[0]] + steps[2:] + ["ANSWER: yes"])
    stats, _ = dataset(reordered)
    check("reordered chain not connected", stats["faith"]["connected"] < 4)
    check("reordered chain misses endpoint", stats["faith"]["endpoint"] < 2)

    print("control 4: probe item outside the re-derived selection")
    drifted = copy.deepcopy(base)
    drifted[0]["seed_hash"] = "0" * 16
    stats, _ = dataset(drifted)
    check("selection mismatch reported", bool(stats["failures"]))

    print("control 5: stored gold disagrees with independent BFS")
    mislabeled = copy.deepcopy(base)
    mislabeled[1]["gold"] = "yes"
    stats, _ = dataset(mislabeled)
    check("gold disagreement reported", any("gold" in f for f in stats["failures"]))

    if problems:
        print(f"\nSELFTEST FAIL: {len(problems)} control(s) not caught")
        return 4
    print("\nSELFTEST PASS: all planted defects caught")
    return 0


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="re-score the 2026-10-14 confidence probe")
    ap.add_argument("raw", nargs="?", help="path to the archived raw completions jsonl")
    ap.add_argument("--selftest", action="store_true", help="run the planted-defect controls")
    ap.add_argument("--skip-hash", action="store_true",
                    help="do not check the raw artifact against the pinned sha256")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.raw:
        print("ERROR: a raw artifact path is required unless --selftest is given", file=sys.stderr)
        return 2

    raw_path = Path(args.raw)
    if not raw_path.is_file():
        print(f"ERROR: raw artifact not found: {raw_path}", file=sys.stderr)
        return 2
    digest = sha256(raw_path)
    if not args.skip_hash and digest != PINNED_RAW_SHA256:
        print(f"ERROR: raw sha256 {digest} != pinned {PINNED_RAW_SHA256}", file=sys.stderr)
        return 3

    records = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    stats, all_rows = score(records, select_items())
    print(f"raw sha256 {digest}")
    bad = report(stats, all_rows)
    if bad:
        print(f"\nFAIL: {len(bad)} quoted number(s) did not reproduce")
        for label in bad:
            print(f"  {label}")
        return 4
    print("\nPASS: every quoted number reproduces from the archived raw artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

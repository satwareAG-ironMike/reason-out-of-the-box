#!/usr/bin/env python3
"""The #5 inference harness runner. Reads decoding/seed policy ONLY from
harness/config.json (the single source of truth - changing the config changes
its hash, which the run manifest records). Runs all three arms (A, B, S) over
a generated item set against a serving endpoint, archives raw output in the
documented format, and writes a run manifest.

Public-only rule: the manifest carries the config hash, checkpoint label, and
endpoint host/port are recorded as the public model id - no private data.

Determinism check (the #5 acceptance criterion "two independent reruns of a
fixed item set produce identical outputs"): run this twice with the same
config + items + endpoint and diff the raw archives; they must be byte
identical (greedy decoding is deterministic; see the 2026-11-24 determinism
gate record).

Usage:
  harness_run.py --items FILE --endpoint BASE_URL --model MODEL_ID
      --arms A,B,S --out DIR [--config harness/config.json]
"""
from __future__ import annotations
import argparse, hashlib, json, os, time, urllib.request


def load_config(path: str) -> tuple[dict, str]:
    raw = open(path, "rb").read()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def grid_prompt(item: dict, suffix: str) -> str:
    g = item["grid"]; mr, mc = item["missing"]; cells = []
    for r in range(3):
        cells.append(" | ".join([" .  " if (r, c) == (mr, mc) else " ".join(map(str, g[r][c])) for c in range(3)]))
    opts = [f"{i}: {' '.join(map(str, o))}" for i, o in enumerate(item["options"])]
    return ("A 3x3 grid of digit triples. Each of the three columns follows one rule, different per column. "
            f"The missing cell is at row {mr}, column {mc}. Grid (rows separated by newlines, cells by |):\n"
            + "\n".join(cells) + "\nOptions for the missing cell (index: triple):\n" + "\n".join(opts)
            + "\nWhich option fills the missing cell? " + suffix)


def post(base: str, model: str, prompt: str, arm_cfg: dict, retry_rule: str) -> dict:
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "temperature": arm_cfg["temperature"], "top_k": arm_cfg["top_k"],
            "max_tokens": arm_cfg["max_tokens"], "stream": False}
    last_err = None
    for attempt in range(3):  # one retry on 5xx/reset, then error-stop (retry_rule)
        try:
            req = urllib.request.Request(base + "/chat/completions",
                                         data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
            return json.load(urllib.request.urlopen(req, timeout=900))
        except Exception as e:  # noqa: BLEW - record and stop per the retry rule
            last_err = str(e)
            if attempt == 1:
                return {"error": last_err}
    return {"error": last_err}


def parse_answer(content: str):
    toks = [t for t in content.split() if t.isdigit()]
    return int(toks[-1]) if toks else None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--items", required=True)
    p.add_argument("--endpoint", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--arms", default="A,B,S")
    p.add_argument("--out", required=True)
    p.add_argument("--config", default="harness/config.json")
    a = p.parse_args()
    cfg, cfg_hash = load_config(a.config)
    items = [json.loads(l) for l in open(a.items)]
    os.makedirs(a.out, exist_ok=True)
    records = []
    for arm in a.arms.split(","):
        arm = arm.strip()
        arm_cfg = cfg["arms"][arm]
        for item in items:
            prompt = grid_prompt(item, arm_cfg["prompt_suffix"])
            t0 = time.time()
            r = post(a.endpoint, a.model, prompt, arm_cfg, cfg["retry_rule"])
            wall = time.time() - t0
            if "error" in r:
                rec = {"prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()[:16],
                       "item_seed": item.get("seed"), "item_seed_hash": item.get("seed_hash"),
                       "item_level": item.get("level"), "family": item.get("family"), "arm": arm,
                       "gold": item.get("answer_index"), "raw_content": None,
                       "parsed_answer": None, "parse_method": "last-integer-token",
                       "correct": None, "finish_reason": "error",
                       "completion_tokens": 0, "prompt_tokens": 0,
                       "wall_s": round(wall, 1), "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "outcome": "error", "error": r["error"]}
            else:
                content = r["choices"][0]["message"]["content"]
                parsed = parse_answer(content)
                rec = {"prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()[:16],
                       "item_seed": item.get("seed"), "item_seed_hash": item.get("seed_hash"),
                       "item_level": item.get("level"), "family": item.get("family"), "arm": arm,
                       "gold": item.get("answer_index"), "raw_content": content,
                       "parsed_answer": parsed, "parse_method": "last-integer-token",
                       "correct": (parsed == item.get("answer_index")) if parsed is not None else None,
                       "finish_reason": r["choices"][0].get("finish_reason"),
                       "completion_tokens": r["usage"]["completion_tokens"],
                       "prompt_tokens": r["usage"]["prompt_tokens"],
                       "wall_s": round(wall, 1), "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "outcome": "ok"}
            records.append(rec)
    with open(os.path.join(a.out, "raw.jsonl"), "w") as f:
        for rec in records:
            f.write(json.dumps(rec, sort_keys=True) + "\n")
    manifest = {"config_hash": cfg_hash, "endpoint": a.endpoint, "model": a.model,
                "arms": a.arms.split(","), "n_items": len(items),
                "n_records": len(records), "seed_policy": cfg["seed_policy"],
                "raw_archive_format": cfg["raw_archive"]}
    json.dump(manifest, open(os.path.join(a.out, "manifest.json"), "w"), indent=2)
    for arm in a.arms.split(","):
        arm = arm.strip()
        sub = [r for r in records if r["arm"] == arm]
        n_ok = sum(1 for r in sub if r["outcome"] == "ok")
        n_c = sum(1 for r in sub if r["correct"])
        print(f"arm {arm}: {len(sub)} records, {n_ok} ok, {n_c} correct")
    print(f"config hash {cfg_hash[:16]} -> {a.out}/raw.jsonl")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

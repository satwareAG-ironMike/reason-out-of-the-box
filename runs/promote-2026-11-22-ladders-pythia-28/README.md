# Confirmatory battery: ladders x pythia-2.8b-deduped (2026-11-22)

Owner-scoped confirmatory run under the PROMOTE contract (SPEC.md pre-registers
family, pins, sampler, novelty band, B3 partner, budget; known blockers B1 +
novelty-not-evaluable stay reported, never waived; verdict floor OPEN-with-blockers).

Owner ruling B (2026-11-23): serving host stays omar-2 :8081 (frozen contract);
wall time accepted. 2026-11-23 device split (vulkaninfo-verified mapping:
Vulkan0 = RX 550/560 dGPU RADV POLARIS11 4GB VRAM, Vulkan1 = APU iGPU RADV
RAVEN): the gate arm ran two-phase - first 246 records on the iGPU (Vulkan1,
pp ~199 t/s), the remainder on the dGPU (Vulkan0) after the omar team's
amdgpu.mcbp=0 + reboot fix (acceptance bench pp64 122.4 / tg32 25.4 t/s,
0 fence errors; owner directive 2026-11-23: pythia arms on the 4GB dGPU
only). The partner arm runs on the dGPU. Frozen contract unchanged (host,
endpoint, model artifacts, sampler, prompts); the device split is provenance,
not a spec change. The 35B MoE service (:8080) intentionally stays on the
iGPU and is out of scope for this run.

## Artifact provenance (recorded at scoring time per sampler.json contract)

| Arm | Artifact (served on omar-2 :8081, single-server pointer contract) | Provenance |
|-----|-------------------------------------------------------------------|------------|
| Gate arm (B1) | Pinned `EleutherAI/pythia-2.8b-deduped` artifact, Q4_K_M (sha256 `3ed7714c1fba3a1f...`, 1788959872 B, 2026-11-22 21:31 CEST) | Converted from `EleutherAI/pythia-2.8b-deduped` @ revision `7d977fed8c4ce9649816af8cd5fe36a639cbe5b2` (fresh HF re-download 2026-11-22; the Nov 21 source safetensors was corrupt, mid-file ranges differ from HF), quantised Q4_K_M with llama.cpp b12366 `llama-quantize`, served by b12366 llama-server `-ngl 99`, two-phase device split: first 246 records on `-dev Vulkan1` (iGPU), remainder on `-dev Vulkan0` (RX 550 4GB dGPU, owner directive 2026-11-23) |
| B3 partner | Pinned `EleutherAI/pythia-1b-deduped` artifact, Q4_K_M (sha256 `fb7ebd7ad1433c30...`, 2026-11-22 20:39 CEST) | Same pipeline, `EleutherAI/pythia-1b-deduped` @ revision pinned in SPEC.md, served on `-dev Vulkan0` (RX 550 4GB dGPU, owner directive 2026-11-23) |

Serving-build pin: llama.cpp b12366 (b12427 source tree used for conversion only).
Corrupt-source incident and exoneration of converter/quantizer/runtime: ops
record on tracker issue #83 (2026-11-22 21:35 UTC entry + device-correction
entries 2026-11-23 05:40/06:45 UTC).

## Frozen sampler (SPEC.md governs on any conflict)

temp 0.0, top_p 1.0 (default), max_tokens 256, one dispatch at a time, frozen
neutral ladders prompt. Calibration arm: seed base 20260101, n=40 x 5 = 200.
Novel band: seed base 20261122, min_n_confirmatory=300 per cell, cells = grid
levels with level-d_hat in {1,2,3,4}; d_hat measured from calibration via
frozen score.py.

## Execution record digests

| file | digest |
|------|--------|
| `tasks.jsonl` | sha256 `e63a60b6bfed03d4` |
| `calibration.jsonl` | sha256 `068494d6635c719d` |
| `calibration-tasks.jsonl` | sha256 `0f08026f6e5e2e56` |
| `raw.jsonl` | sha256 `4c44321b620b1095` |
| `partner-raw.jsonl` | sha256 `9da377a871294b16` |
| `score.json` | sha256 `308e13354fbdff7f` |

## Execution record (filled at scoring time)

- [ ] calibration-tasks.jsonl (frozen verify.py --generate, seed base 20260101)
- [ ] calibration.jsonl (200 raw records, frozen schema {seed_hash, surface:"na", completion, finish_reason, model_pin})
- [ ] calibration-dhat.json (frozen judge per-level d_hat)
- [ ] tasks.jsonl (novel cells, seed base 20261122, n=300 per cell)
- [ ] raw.jsonl (gate arm) / partner-raw.jsonl (B3 partner, same items)
- [ ] score.json (frozen judge: score.py --score with tasks / calibration-tasks / raw / calibration / partner-raw; corpus slice absent on omar-2 => novelty arm not_evaluable by pre-registration, blocker B-novelty)
- [ ] verdict line: per-level H0 with Holm-Bonferroni pooled, alpha 0.05, min_gap 0.10; overall verdict OPEN-with-blockers unless B1 + novelty clear
- [ ] delivery census (finish_reason length mapping)
- [ ] Executed / Reproduced / Validated labels per runs/ conventions

## Ledger routing

Confirmatory run: row goes to the runs/ execution-record ledger convention, NOT
explore/LEDGER.md (exploratory-only). Weekly cap unaffected: owner-scoped run,
W47 cap already spent and kill reported on #212.

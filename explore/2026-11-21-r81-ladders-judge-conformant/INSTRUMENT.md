# Round 81 instrument

- **Family**: ladders (k-hop reachability, k = level; k=1 is a lookup control)
- **Generator**: `generators/ladders.py` (frozen-judge-loop branch), judge grid LEVELS = (1, 2, 4, 6, 8)
- **Seed policy**: item i at level L uses `seed_base + 2_000_000*L + i` (judge contract).
  - calibration arm: seed base 20260101, 40 items per level x 5 levels = 200 items
  - novel-band arm: seed base 20261121 (run-date fresh seed, never shipped), 40 items at the
    grid level past d_hat
- **Prompt builder**: `evaluation/frozen/verify.py build_prompt` (frozen, neutral, one-word
  answer contract, no chain-of-thought scaffold, no few-shot reasoner trace, no "think step by step")
- **Sampler**: temperature 0.0, top_p default, max_tokens 256 (one-word contract; the
  8-token first pass failed - see delivery-contract finding), one dispatch at a time
- **Model**: qwen3.8-27b-nvfp4-mtp (self-hosted, self-hosted endpoint; exploratory-only model class)
- **Budget**: 240 prompts (200 calibration + 40 novel band); well under the weekly explore cap
  (research/AGENTS.md: 400 explore prompts/week, ~57 used before this round -> ~297 after)
- **B3 partner arm**: not_evaluable (no pinned smaller same-family checkpoint for this build)
- **Serving build**: pinned in the round summary at scoring time (llama.cpp build on the endpoint host)

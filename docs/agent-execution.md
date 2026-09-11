# Agent-executed program: operating model and scientific standards

Status: active direction, 2026-09-11, issue #39. The whole thesis program (M1-M5) executes
on AI agents; all scientific standards are enforced inside the program; this repository is
the public record; resources stay minimal. Study specifics remain in
[study-design.md](study-design.md), [analysis-plan.md](analysis-plan.md), and
[preregistration.md](preregistration.md); this document fixes how the work is run.

## 1. Roles

| Role | Does |
|------|------|
| Agents | literature work, protocol drafting, generators, harness, runs, analysis, verification, reporting, bookkeeping, the daily audit trail (Daily Ops threads) |
| Owner | gates and approvals, external registrations (OSF, AsPredicted), any human-subject step, accountable-human statements for any external venue, compute provisioning and spend approvals |

No human operates the experimental pipeline. The owner remains the accountable gate.

## 2. Publication reality (2026) and the substitute for it

- arXiv (May 2026): one-year posting ban for submissions containing hallucinated references
  or other "incontrovertible" signs of unchecked AI output
  ([Nature news](https://www.nature.com/articles/d41586-026-01595-5)).
- NeurIPS 2026 Position Paper Track: substantially-human-written requirement; 178/969
  submissions (18.4%) desk-rejected; the chairs describe the provenance audit trail (pre-AI
  checkpoint, post-AI checkpoint, final version) as the coming default
  ([NeurIPS blog](https://blog.neurips.cc/2026/06/02/ai-generated-papers-in-the-neurips-2026-position-paper-track/)).
- Common venue rule: AI may assist, AI cannot be the accountable author.

Consequence: no venue submission is planned as a validation path. The public record is this
repository + the OSF registration + public releases + the replication record, held to the
standards below. If a human sponsor ever submits externally, this program's audit trail
(version history, checkpoints, manifests) is the evidence class venues are beginning to
require; that path is documented, not assumed.

## 3. The standard pipeline

Plan -> Retrieve -> Generate -> Execute -> Confront -> Verify -> Replicate -> Archive ->
Report (2026 agentic-science practice; sources at the bottom). Mapped to this program:

| Stage | Mechanism |
|-------|-----------|
| Plan | Pre-registration (#11): OSF + AsPredicted; analysis plan and version-lock manifest; seeds, margins, and budgets fixed before confirmatory runs |
| Retrieve | Logged retrieval; every citation ID resolved via its API before use; claim-support statuses: exists / retrieved / supports / contradicts / not checked |
| Generate | Generators, prompts, harness in-repo; every change is a commit; the commit is the run input |
| Execute | Version-pinned environment; sources immutable during confirmatory runs; full run manifests (Section 4); fail closed on unexpected mutation |
| Confront | Numerical-confrontation records for every quantitative claim (Section 5); no result number enters prose unless a deterministic script regenerates it from archived inputs; external values enter only with a confrontation record |
| Verify | Verifier independence (Section 5); adversarial review; seeded-defect tests |
| Replicate | Fresh-seed reruns; independent implementation of primary metrics where feasible; OLMo 3 replication family per the design |
| Archive | Content-addressed artifacts, hash-pinned (Section 6) |
| Report | Executed / Reproduced / Validated labels; all runs reported, including failures and exclusions; deviations dated |

## 4. Run manifests

Every run (audit, pilot, main, analysis) carries an immutable manifest; the #5 harness owns
the implementation and the pre-registration freezes the field set. Minimum fields:
`run_id`, `parent_run_id`, `task_hash`, code commit, model identifier + weights hash +
serving revision, prompt hash, tool registry + versions, environment lock hash, dataset ids
+ content hashes, decoding parameters + seed, start/end timestamps, budget, artifact
hashes, status, failure codes.

## 5. Confrontation, verification, labels

- **Confrontation record** per quantitative claim against an external source: claimed value
  and source; recomputed value; absolute and relative difference; data basis; statistical
  basis; explanation; disposition (accepted / qualified / rejected). Discrepancies are
  investigated, never explained away. (Adopted from the archive's Grounded Autonomous
  Research finding: access is not grounding; confrontation must be enforced.)
- **Verification independence**: the agent that produces an artifact never verifies it.
  Verifiers work from raw artifacts, not interpretations; use a different agent
  configuration (different model family where possible); report structured failure codes.
  Periodic seeded-defect tests (plant wrong units, shuffled labels, a wrong seed, a fake
  citation, an off-by-one n) measure verifier recall.
- **Self-approval is not evidence.**
- **Labels, never collapsed**: *Executed* (the run completed), *Reproduced* (an independent
  rerun regenerates the result within a pre-declared tolerance), *Validated* (independent
  evidence supports the interpretation).
- Human review remains mandatory for external submissions, spend, irreversible actions,
  and any human-subject step.

## 6. Artifacts and archive

- In-repo: protocols, manifests (or summaries), code, decisions, reports, deviation logs,
  and the daily audit trail (Daily Ops SOD/EOD threads with state projections; the PR
  history is the change ledger).
- Heavy artifacts: raw outputs, run logs, model verdict files - external storage or Hub,
  hash-pinned here; regenerate-not-retain where regeneration is cheap and deterministic.
- Every figure and table names its generating script and input artifact hash.
- Contamination boundary: answer-bearing files stay out of agent context; retrieval is
  logged; generated items are seed-frozen; replication uses private holdouts.

## 7. Resource policy (least resources)

| Resource | Policy |
|----------|--------|
| Inference | Open weights, local-first, single-node bf16 (feasibility audit: one 80 GB GPU suffices; 8x80 GB comfortable); no training |
| Corpora | Public infini-gram indexes; local mirrors only where the audit requires them (the 13 TB figure is a ceiling, not a target) |
| Agent work | Subscription CLI sessions and hosted MCP; no metered provider-API calls without in-session owner approval |
| Execution | Offline batch: queue, log, return; no interactive loops inside expensive paths |
| Spend | cost:daily reviewed at SOD/EOD; over-threshold triggers a model-routing review |

## 8. Failure-mode guards

| Failure mode (2026 audit findings) | Guard in this program |
|------------------------------------|-----------------------|
| Fabricated or misattributed citations (10-22% in agent pipelines) | API resolution before use; claim-support statuses; no inference-filled bibliographic fields |
| Numbers that never ran | Machine-generated tables; provenance pointer per number; regeneration rule |
| Self-review blind spots | Verifier independence; artifact-based review; seeded defects |
| Missing numerical confrontation | Confrontation records; investigate, never explain away |
| Contamination or leakage | Provenance boundary; hidden answer files; logged retrieval; holdouts |
| Silent environment or code mutation | Pinned environment; immutable sources in confirmatory runs; before/after hashes; fail closed |

## 9. Program mapping (M1-M5)

- **M1**: pre-registration (#11), human-path decision (#7), analysis plan (#10).
  Agent-drafted; external submissions owner-gated.
- **M2**: pilot - contamination audit (#3), generators (#4), harness (#5), go/no-go (#8).
  Agent-executed; manifests on.
- **M3**: main run (#9). Agent-executed; frozen artifacts; fail closed.
- **M4**: analysis (#14), agent-executed and independently verified; human baseline (#13)
  per the open decision below.
- **M5**: public record (#12): repository report + OSF + releases, in the
  Executed/Reproduced/Validated schema. No venue submission assumed.

## 10. Open decisions (owner)

1. **Human baseline**: (a) published-baseline mapping (least resources; check Webb et al.
   released data for digit matrices, ARC human data, published human performance for the
   ladder family) with a gap list; (b) minimal external collection (owner-operated; IRB
   lead time and platform costs); (c) hybrid. Recommendation: (a) first, revisit after the
   gap list. Tracked in #7.
2. **Compute node naming** when pilot dates are set (private channel).
3. **OSF / AsPredicted timing** (#11 checklist).

## Sources

- Archive: 2606.15497 (The AI Scientist: validation is the bottleneck, not ideation);
  2607.02329 (Grounded Autonomous Research: access is not grounding; enforced numerical
  confrontation at checkpoints).
- 2026 agentic-science practice survey (web research 2026-09-11; secondary sources -
  includes reported figures for ScienceAgentBench (~32.4% best independent success) and
  CORE-Bench (~21% hardest tier), run-manifest and artifact-preservation checklists, and
  the Executed/Reproduced/Validated convention; verify primaries before any external
  citation).
- Policy sources: Nature news d41586-026-01595-5 (19 May 2026); NeurIPS blog 2 Jun 2026.

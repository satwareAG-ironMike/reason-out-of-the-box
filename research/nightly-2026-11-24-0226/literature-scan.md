# Literature scan - round nightly-2026-11-24-0226

Round under scan: k-hop ladder items under a frozen neutral one-word contract, task surface byte-identical,
only the instruction about reasoning varied (baseline / imperative ban / negated ban / permission to reason
after the answer), measuring trace presence, trace length, delivery state and verdict invariance.

Verification levels used below: `abstract` = the record's own abstract/summary text was read; `record` = only
bibliographic fields (authors, title, venue, year) were returned and read. **No source in this scan was
verified at full-text level.** Every row was fetched; nothing below is recalled from memory.

## Verified sources

| Source ID | Authors | Venue | Year | Peer-review status | Verification | Relevance to this round |
|---|---|---|---|---|---|---|
| arXiv:2511.12381 | Logan Mann, Nayan Saxena, Sarah Tandon, Chenhao Sun, Savar Toteja, Kevin Zhu | arXiv (cs.CL, cs.AI); no venue in record | 2025 | Preprint, no venue recorded in the fetched record | abstract | Nearest prior art for the ironic arm: negation instructions ("do not mention X") raise the accessibility of X in LLM output; rebound grows with semantic/length distractors; ships ReboundBench (5,000 negation prompts) |
| arXiv:2605.28639 | Rebecca Ramnauth, Brian Scassellati | arXiv (cs.CL, cs.AI); comment: under review at EMNLP 2026 | 2026 | Preprint under review | abstract | Instruction-based suppression in LLMs: prohibited concepts stay recoverable in hidden states and keep steering attention and output despite lexical avoidance - same expression/representation gap this round probes from the trace side |
| doi:10.1037/0033-295X.101.1.34 | Daniel M. Wegner | Psychological Review | 1994 | Peer-reviewed journal article | abstract | The ironic-processes theory itself: control installs an operating process plus a capacity-light monitoring process that searches for the forbidden content - the mechanism a negated ban is expected to load |
| doi:10.1177/1745691619898795 | Deming Wang, Martin S. Hagger, Nikos L. D. Chatzisarantis | Perspectives on Psychological Science | 2020 | Peer-reviewed journal article | abstract | Meta-analysis (k = 31) in the Wegner paradigm: rebound effects detected; immediate enhancement effects appear mainly under added cognitive load - the load conditional our single-endpoint design does not manipulate |
| doi:10.1016/S0272-7358(00)00057-X | Jonathan S. Abramowitz, David F. Tolin, Gordon P. Street | Clinical Psychology Review | 2001 | Peer-reviewed review article | record | Earlier meta-analysis of paradoxical thought-suppression effects; OpenAlex returned the record with no abstract text, so only its existence and identity are verified |
| doi:10.1016/j.brainres.2009.12.041 | Ryan J. Giuliano, Nicole Y. Y. Wicha | Brain Research | 2010 | Peer-reviewed journal article | record | Electrophysiological evidence of ironic semantic activation during suppression: the forbidden concept is activated even while expression is withheld |
| doi:10.1371/journal.pone.0282197 | Matthew Wallaert, Andrew Ward, Traci Mann | PLOS ONE | 2023 | Peer-reviewed journal article | record | "Taming the white bear": lowering reactance pressure improves suppression - suggests the wording/reactance framing of a ban, not the ban alone, drives failure |
| arXiv:2305.04388 | Miles Turpin, Julian Michael, Ethan Perez, Samuel R. Bowman | arXiv; comment: NeurIPS 2023 | 2023 | Peer-reviewed (per the arXiv venue comment) | abstract | The unfaithful-CoT baseline: biasing hints change the answer and the trace rationalises the hint without mentioning it - exactly the "trace manipulated while verdict holds" shape |
| arXiv:2307.13702 | Tamera Lanham, Anna Chen, Ansh Radhakrishnan, Benoit Steiner, Carson Denison, et al. (30 authors) | arXiv; no venue in record | 2023 | Preprint, no venue recorded in the fetched record | abstract | Faithfulness test battery (add mistakes, paraphrase, truncate): models sometimes ignore the trace they emitted; provides the operational reading of our verdict-invariance measure |
| arXiv:2503.08679 | Iván Arcuschin, Jett Janiak, Robert Krzyzanowski, Senthooran Rajamanoharan, Neel Nanda, Arthur Conmy | arXiv; comment: Published at ICML 2026 | 2025 | Peer-reviewed (per the arXiv venue comment) | abstract | Unfaithful CoT on natural, non-adversarial prompts: post-hoc rationalisation up to 13% in production models, no hint needed - supports treating the emitted trace as a narration, not the computation |
| arXiv:2501.19393 | Niklas Muennighoff, Zitong Yang, Weijia Shi, Xiang Lisa Li, Li Fei-Fei, et al. (10 authors) | arXiv; no venue in record | 2025 | Preprint, no venue recorded in the fetched record | abstract | Budget forcing: trace length controlled by decode-time termination and by appending "Wait", i.e. by the sampler, not by an instruction - the control channel our arms deliberately do not use |
| arXiv:2412.06769 | Shibo Hao, Sainbayar Sukhbaatar, DiJia Su, Xian Li, Zhiting Hu, Jason Weston, Yuandong Tian | arXiv; comment: Accepted to COLM 2025 | 2024 | Peer-reviewed (per the arXiv venue comment) | abstract | Coconut: reasoning moved into a continuous latent space, so no trace is emitted at all - shows trace suppression so far takes a training-time or architectural route, not a prompt route |
| arXiv:2403.09629 | Eric Zelikman, Georges Harik, Yijia Shao, Varuna Jayasiri, Nick Haber, Noah D. Goodman | arXiv; no venue in record | 2024 | Preprint, no venue recorded in the fetched record | abstract | Quiet-STaR: models learn rationales at each token that are not surfaced as output - the "silent thinking" state an instruction-level ban would be hoping to induce |
| arXiv:2412.21187 | Xingyu Chen, Jiahao Xu, Tian Liang, Zhiwei He, Jianhui Pang, et al. (14 authors) | arXiv; no venue in record | 2024 | Preprint, no venue recorded in the fetched record | abstract | Overthinking in o1-like models: long traces on trivial items, mitigated by self-training; frames trace length as a resource dial rather than something an instruction can turn off |

Records fetched and deliberately **not** cited: the identifier candidate arXiv:2402.13719 resolved to an
unrelated mathematical-statistics paper (Brannath, Kluge, Scharpenberg, simultaneous confidence intervals), so
nothing was attributed to it. The candidate DOI 10.1037/0022-3514.65.1.5 resolved to Cacioppo, Priester and
Berntson (arm flexion and attitudes), also not cited. The candidate DOI for the 1987 white-bear suppression
paper returned no record at all in this scan, so that paper is reported as unverified in Q1 rather than cited.

## Q1 - Process suppression / ironic process theory

| Layer | Verified source | What it establishes for this round |
|---|---|---|
| Theory | Wegner 1994 (abstract) | Intentional control spawns an operating process (effortful, searches for the intended state) and a monitoring process (capacity-light, searches for the forbidden state); under load the monitor's priming outlasts the operator |
| Meta-analysis, recent | Wang, Hagger & Chatzisarantis 2020 (abstract) | Rebound after suppression is robust across k = 31 protocol-consistent studies; immediate enhancement is load-dependent, not automatic |
| Meta-analysis, earlier | Abramowitz, Tolin & Street 2001 (record only) | Existence of the earlier quantitative synthesis; effect direction not read from text in this scan |
| Mechanism probe | Giuliano & Wicha 2010 (record only) | Semantic activation of the suppressed content is measurable even when expression is withheld |
| Framing moderator | Wallaert et al. 2023 (record only) | Reactance pressure in the suppression instruction changes suppression success |

Gap stated plainly: the paradigm's origin paper (the 1987 "white bear" thought-suppression study) was **not**
verified within the 8-call budget; the candidate DOI lookup returned nothing. The paradigm is therefore anchored
here on the verified Wegner 1994 theory record plus the two verified meta-analyses, not on the 1987 report.

## Q2 - CoT / reasoning-trace faithfulness

| Finding | Source (verification) | Read-across to the ladder arms |
|---|---|---|
| Trace content is steered by prompt-side hints that the trace never mentions; biasing features flip answers and the trace rationalises them | Turpin et al., arXiv:2305.04388 (abstract) | An instruction about reasoning is exactly such a hint; it can change the narration without changing the underlying selection |
| Models range from strongly CoT-dependent to ignoring the trace entirely, task by task; less faithful as models scale | Lanham et al., arXiv:2307.13702 (abstract) | Verdict invariance under a changed trace is expected behaviour, not a bug unique to this endpoint |
| Unfaithful narration appears on naturally worded non-adversarial prompts (implicit post-hoc rationalisation, up to 13%) | Arcuschin et al., arXiv:2503.08679 (abstract) | Our no-hint baseline arm sits in this regime; yes/no surface form is the same bias axis they measure |

Net: the literature's default is that the emitted trace is a **narration with causal influence from prompt-side
signals**, and that answer and narration can decouple. That is the frame in which a null G2 (ban does not remove
the trace) and a passing verdict-invariance gate should be reported.

## Q3 - Instruction-level control over the emitted reasoning trace

| Existing control | Mechanism | How it differs from this round |
|---|---|---|
| Budget forcing (arXiv:2501.19393, abstract) | Sampler forcibly terminates the thinking phase or lengthens it by appending "Wait" | Length is set outside the prompt; the model is never asked, and a natural-language ban is never tested against the trace |
| Latent / silent reasoning (arXiv:2412.06769 abstract; arXiv:2403.09629 abstract) | Reasoning is relocated to hidden states or to never-surfaced rationale tokens via training | The trace is absent because it was never decoded; nothing about whether an instruction can suppress a trace the model already emits by default |
| Overthinking mitigation (arXiv:2412.21187, abstract) | Self-training to shorten traces on easy items | A fine-tuning intervention, not a prompt-level contract change held over a byte-identical task |
| Negation instructions and concept rebound (arXiv:2511.12381, abstract) | Prompt says "do not mention X", rebound measured in generated output under cognitive load | Suppression target is a **concept in the answer stream**, not a reasoning trace; no yes/no task contract, no verdict-invariance measure, no reasoning-channel field |
| Suppression and internal representation (arXiv:2605.28639, abstract) | Behavioural, attention and probing analysis of suppressed prohibited content | Asks whether suppression touches representations; does not vary imperative vs negated phrasing and does not look at a task-solving chain |

The serving-side dials actually shipped in products (reasoning-effort settings, dedicated reasoning channels,
hidden chain of thought) are documented by vendors, not by the scholarly records reachable in this scan, so no
citation is offered for them here.

## Q4 - Novelty check on the ironic-negation probe over reasoning traces

Nearest prior art and the exact delta:

| Prior work | What it does | Delta this round still owns |
|---|---|---|
| arXiv:2511.12381 (abstract) | Negated instruction over a concept; rebound in output; polarity separation between neutral and negative framing; ReboundBench | Target is a concept, not an emitted chain; no frozen one-word answer contract, no reasoning-channel field, no verdict invariance, no imperative vs negated vs permission arms on one task surface |
| arXiv:2605.28639 (abstract) | Instruction-based suppression of prohibited content; expression suppressed, representation intact | No negated-vs-imperative contrast, no ladder task, no trace-length measurement, no delivery-state analysis |
| Turpin / Lanham / Arcuschin (abstracts) | Faithfulness of an emitted trace under hints and interventions | None of them treats an instruction **about reasoning itself** as the experimental variable, and none uses a negated ban |

Claim to defend, stated narrowly: no record found in this scan runs a Wegner-style negated process-suppression
instruction ("do not think about X") against the **emitted reasoning trace of a reasoning model** and scores
whether the ban backfires on trace presence or length, with the task surface held byte-identical and the verdict
tracked for invariance. The broader claim "ironic negation in LLMs is unexplored" is **false** and must not be
used; two preprints already occupy it. The round's defensible novelty is the trace-level target plus the
four-arm contrast and the invariance measure, not the ironic framing.

## Searched for and not found

Exact queries run (all within the 8-call budget):

| # | API | Query string | Result |
|---|---|---|---|
| 1 | arXiv export API | `all:"white bear" AND (all:"language model" OR all:"large language")`, max_results 40 | totalResults = 2; both retrieved and read at abstract level (arXiv:2511.12381, arXiv:2605.28639) |
| 2 | Crossref works | `query.bibliographic=white bear thought suppression`, rows 25 | 956,788 total hits; top 25 inspected: all human-psychology or WBSI instrument work, no LLM reasoning-trace study |
| 3 | OpenAlex works | `search=ironic process theory large language model`, per-page 25 | 84,761 total hits; top 25 inspected: ironic-content detection and theory-of-mind work, no negated-suppression-over-CoT study |
| 4 | OpenAlex works | DOI filter over five candidate canonical DOIs | 3 resolved (Wegner 1994; Abramowitz et al. 2001; one mismatch); the 1987 white-bear candidate DOI did not resolve |
| 5 | arXiv export API | `id_list=` batch of 8 candidate identifiers | 8 resolved; 6 used, 2 mismatched and dropped (arXiv:2402.13719, see note above) |

Negative results, stated as findings and bounded by the queries actually run:

- Not found: a paper combining a negated "do not think" instruction with a reasoning-model trace measurement and
  a backfire outcome, in the arXiv "white bear" intersection (2 hits total, both read).
- Not found: any LLM reasoning-trace study inside the top-25 relevance band of the Crossref white-bear query or
  the OpenAlex ironic-process query.
- Not found: a record that verifies the 1987 white-bear paradigm paper's identifier inside this budget.

Coverage limits (these bound every negative above, so the novelty claim must be phrased with them):

- Not searched, because the call budget was spent: `process suppression`, `thought blocking`, `rebound effect`,
  `do not think`, `negated instruction`, `instruction negation`, `suppressed chain of thought`,
  `reasoning effort`, `silent thinking`, `hint`, `reasoning_content`, and any PhilPapers query.
- The broad arXiv faithfulness relevance search never completed (two initial connection attempts over the
  insecure endpoint failed and were retried over the secure endpoint; one OpenAlex call failed on an invalid
  parameter). The faithfulness corpus above was therefore assembled by **identifier lookup and verified from
  the returned records**, not by a search, so no negative result may be claimed for faithfulness queries.
- No full-text verification was performed for any source; venue statements come from arXiv journal-ref/comment
  fields or from the Crossref and OpenAlex records.

---

Provenance: 8 HTTP requests total, the full budget, no more - arXiv export API 4 (2 failed insecure-scheme
connection attempts returning 0 bytes, then 2 successful, one of them the identifier batch), Crossref REST API
1 (topic query), OpenAlex REST API 3 (1 rejected for an invalid `select` field, 2 successful: the topic search
and the DOI-filter record check). No metered or hosted generation provider, no web-search tool and no vendor
API was called. Author name strings for the two Crossref-only rows were read from the same Crossref topic-query
response as their DOIs, and no author name was supplied from memory after that response showed given names
where an earlier draft had guessed them. Verification levels are as tagged per row; nothing here is full-text
verified.

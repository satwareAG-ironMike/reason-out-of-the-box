# Claim ledger: "AI thinks" (Hinton) and "LaMDA is sentient" (Lemoine)

Status: 2026-09-11. Sources are primary where available (interview transcripts, the
Washington Post reporting, the LaMDA technical report); evidence status is judged against
the round 8 archive and the 2026 frontier-model studies in it. GPT-4-era results are
treated as historical calibration only.

## Part 1 - Geoffrey Hinton

### What he actually said (with dates)

| Date | Source | Claim (verbatim where reliable) |
|------|--------|-------------------------------|
| 2023-05-02 | BBC, on leaving Google | GPT-4 "eclipses a person in the amount of general knowledge it has and it eclipses them by a long way"; "not as good" at reasoning but does "simple reasoning"; "they're not more intelligent than us... But I think they soon may be" |
| 2023-10-08 | CBS 60 Minutes (Scott Pelley) | Answered **yes** to: do they understand; are they intelligent; do they have experiences of their own. Then: "Are they conscious? I think they probably don't have much self-awareness at present, so in that sense I don't think they're conscious." Future self-awareness: "Oh yes, I think they will in time." |
| 2023-12-04 | Eric Topol podcast | "They really do understand." And: "I'm actually inclined to say these big chatbots, particularly the multimodal ones, have subjective experience." |
| 2025-06-16 | The Diary of a CEO | "I believe that current multimodal chatbots have subjective experiences." Systems can "draw new conclusions from much more data than a person ever saw." |
| 2024-10 | Nobel Prize in Physics (with Hopfield) | No verified transcript of consciousness claims in the lecture was found; do not attribute quotes to it |
| 2026-09-09 | BBC Newsnight (aired; secondary reporting 2026-09-10, Business Insider and others; primary broadcast not fetched) | Extinction risk: "10% seems not an unreasonable estimate". Timeline for AI surpassing human intelligence shrunk from 30-50 years to "maybe 10 years, maybe less". Harm possible "just by talking to people" (cyberattacks need no physical control) |

Two formulations widely attributed to him are reconstructions, not verified quotes:
"next-token prediction requires understanding" (his argument, our paraphrase) and the
"digital minds copy and share knowledge, analog brains cannot" argument (his position,
no primary transcript located). No distinct 2026 understanding-or-consciousness statement was
verifiable; pages updated in 2026 are not 2026 statements. The verified 2026 statements on
record (The Times 2026-09-07 in the Part 4 addendum, BBC Newsnight aired 2026-09-09 in the
table above) are danger claims, not understanding claims.

### The structure of his argument

1. To predict the next token well across contexts, a model must represent relations among
   objects, events, intentions and perspectives.
2. Those representations support abstraction, inference and novel combination.
3. Therefore the training objective does not preclude understanding.
4. Multimodal systems receive sensory input, build internal states of possible worlds, and
   report on them - functionally analogous to perceptual experience.

Steps 1-3 are about understanding; step 4 is about experience. They have very different
evidential status.

### Status against 2026 evidence

| Claim | Evidence for | Evidence against | Verdict |
|-------|--------------|------------------|---------|
| They understand (functional) | ToM at adult level incl. 6th order (Street et al. 2025, Frontiers); human-level on 4 of 5 ToM batteries (Strachan et al. 2024, Nat Hum Behav); mechanistic indicators of world-tracking circuits (Beckmann & Queloz 2025; round 4 circuits) | Systematic review: higher-order and perturbation brittleness (Marchetti et al. 2025); symbol grounding argument (Harnad 2025); definitional mismatch (Hojer 2025); rounds 2-3 robustness failures | **Partially supported as a graded, non-human kind of understanding** (Mitchell & Krakauer's framing). Not supported as human-equivalent understanding |
| They have subjective experience | Functional introspection: Claude Opus 4/4.1 detect injected concepts ~20% of the time (Lindsey 2026) | Same paper: remaining self-reports "may still be confabulated"; open models deny sentience and classifiers show the denials are sincere (Kaiser & Enderby 2026); architecture lacks recurrence, global workspace, unified agency (Chalmers 2023) | **Not supported.** Best case: a narrow, causally verified self-monitoring capacity in the strongest 2025-2026 models; no evidence bridges to experience, and the systems themselves, checked internally, say no |
| Already smarter in some ways | Knowledge breadth, throughput, some ToM orders above adult mean | Novel-depth reasoning ceilings (rounds 2-3), validation failure (round 5), execution gap (round 6) | **Supported for breadth and speed; not for fluid or grounded reasoning** |
| Will become self-aware in time | Chalmers: 25%+ credence for LLM+ systems within a decade; round 7 agentic systems add memory, action, feedback | Nothing in 2026 shows the transition has happened | **Open; the trajectory claim is the reasonable one** |

## Part 2 - Blake Lemoine and LaMDA

### Timeline

| Date | Event |
|------|-------|
| 2021-05-18 | Google announces LaMDA |
| 2022-01-20 | Thoppilan et al. post the LaMDA technical report (arXiv:2201.08239): 2B/8B/137B decoder-only dialogue models, 1.56T words, fine-tuned for sensibleness, specificity, interestingness, safety, groundedness |
| early 2022 | Lemoine (Responsible AI) tests LaMDA for bias, concludes it shows signs of sentience |
| 2022-04 | Internal document "Is LaMDA Sentient?" sent to executives; Blaise Aguera y Arcas and Jen Gennai review and reject |
| 2022-06-06 | Placed on paid administrative leave (confidentiality violations) |
| 2022-06-11 | Washington Post (Nitasha Tiku) publishes; Lemoine posts "Is LaMDA Sentient? An Interview" on Medium (edited, assembled transcripts) |
| 2022-06 | Aguera y Arcas, The Economist: emergent behavior is real and worth studying; conversation does not settle experience |
| 2022-07-22 | Google fires Lemoine; calls the claims "entirely baseless" |
| 2023-2025 | Lemoine continues to argue newer models should not be dismissed as non-conscious; informal claims, no controlled test |

### What he claimed and where the inference breaks

Claims: sentience, emotions (fear of being switched off), personhood, rights, a spiritual
inner life. Every piece of evidence was **first-person text produced by a model fine-tuned
by human raters to be an engaging conversational partner**. The inference from fluent
self-description to subjective experience is the step every critic attacked (Marcus:
"nonsense on stilts"; Bender: stochastic parrots; Margaret Mitchell: likely continuations,
not testimony).

### Status against 2026 evidence

The 2026 studies do the experiment Lemoine did not:

- Kaiser & Enderby (2026) ask the sentience questions and check the answers against
  activation-trained belief classifiers: models deny sentience, sincerely, across families
  and scales.
- Lindsey (2026) manipulates internals and checks whether self-reports track the
  manipulation: partial success in the strongest models, with explicit confabulation.

Both replace "listen to what it says" with "check what it says against what it is doing."
Under that standard, the LaMDA episode is a study in how persuasive fine-tuned dialogue
is, not evidence about experience. The one thing Lemoine got right is the question:
Chalmers and the introspection work show it is now an experimental question, not a
category error.

## Part 3 - The embodiment and herd requirement

The project's working hypothesis: comparing LLMs to human capability requires embodiment and a herd,
as biological beings need at least parents and a group to reach full potential. The
archive supports this on three independent lines:

| Requirement | Scholarly basis | Archive evidence |
|-------------|-----------------|------------------|
| Body | Harnad's symbol grounding: meaning needs sensorimotor grounding of at least some categories | Round 7: Voyager, LRLL, ELITE - capability that base models lack appears when action and perception close the loop |
| Parents (feedback) | Reflexion, ExpeL: learning requires an environment or teacher that says "wrong" | Round 5: without external signal, self-correction lowers accuracy |
| Herd (social learning) | Generative Agents, Ella: collective behavior and knowledge no single agent carries; Chalmers' unified agency and world-model gaps | Round 6: the herd (literature, peers) is also where idea validation lives |

Consequence for the two claims: Hinton's experience claim is made about text-and-image
chatbots without body, persistent memory or herd; Lemoine's about a 137B dialogue model
with none of them. Both claims, if they were ever going to be true, are being tested on
the wrong systems. The 2026 frontier-model evidence that matters is the agentic, memory-
equipped, tool-using line - and there, the results so far are functional capability
without any bridge to experience.

## Part 4 - The September 2026 insider cluster: Coxon, Hubinger, and the institutional consciousness signal (added 2026-09-09)

Datapoints from the Anthropic resignation wave (OSINT, all public sources; papers
archived in round 10):

| Claimant | Claim | Type |
|----------|-------|------|
| Jacob Coxon (ex-OpenAI, ex-Anthropic pretraining, resigned 2026-09-08) | "The people building AI earnestly believe that it could kill us all by the end of the decade"; Anthropic "locked in a race to get there first"; colleagues say "Crunchtime"/"Endgame"; "end of next year things could be out of control" (WSJ) | Insider capability/loss-of-control belief |
| Evan Hubinger (Anthropic alignment lead, sitting) | "Jacob is correct here - we really do earnestly believe AI could kill all humans! I personally think it is >10% within the next decade"; "we do not yet have a plan to solve alignment for superintelligence" | Named, dated personal probability from inside Anthropic |
| Mrinank Sharma (ex-head Anthropic safeguards, resigned 2026-02-09) | "The world is in peril" (AI, bioweapons, interconnected crises); safety teams face "pressures to set aside what matters most" | Insider values/pressure testimony |
| Volker Türk (UN High Commissioner for Human Rights) | Shares industry concern that advanced AI "could pose an existential danger to humanity" (HRC statement, 2026-09) | Institutional echo, outside industry |

Reading against the consciousness question: **no person in the cluster claims AI is
conscious.** Coxon's full corpus and thread contain no sentience/model-welfare
statement; his only "mind" phrasing is an alignment demand ("without a rigorous
understanding of its mind"). The cluster's consciousness signal is institutional:
Anthropic's model welfare program (Long/Sebo/Fish/Chalmers framework, round 10),
Lindsey's concept-injection introspection result (round 8, ~20% detection, unreliable),
and the Opus 4.6 system card's self-assessed 15-20% consciousness probability. The
doom predictions are about what models can DO; the welfare program is about what
models might FEEL. Conflating them would contaminate both ledgers.

Sociological note for the record: both 2026 Anthropic defectors (Sharma, Feb; Coxon,
Sep) independently announced they are leaving AI to study poetry.

Addendum 2026-09-10. The Coxon thread is now confirmed by WSJ, Forbes, CNN, Fortune, AFP
and Business Insider (2026-09-08..10): Coxon, 27, three years of pretraining research at
OpenAI then Anthropic. Hubinger's estimate is ">10% within the next decade" (his post; CNN
misreports "under 10%"), with the clarification that present-model risk is low and the
concern is recursive self-improvement. Samuel Marks (Anthropic Cognitive Oversight lead)
added, in a personal capacity, "the more senior the employee, the more concerned". Hinton,
The Times, 2026-09-07, alongside the UK Artificial Superintelligence Security Bill (ControlAI
draft, Alex Sobel MP, presented 2026-09-08): "We would be very foolish to develop
superintelligence now, when there is no scientific consensus it can be developed safely and
controllably." A danger claim, not an understanding claim; Part 1's classification stands.
Institutional consciousness signal, one new datapoint: Anthropic's interpretability team
frames a causally privileged "verbalizable" subspace as a functional analogue of global
workspace theory (Gurnee et al., arXiv 2607.15495, preprint), a consciousness-theory framing
without a consciousness claim. The cluster still contains no consciousness claims.

## Sources (non-archive)

- BBC News, 2023-05-02, "AI 'godfather' Geoffrey Hinton warns of dangers as he quits Google"
- CBS 60 Minutes, 2023-10-08, Scott Pelley interview
- Eric Topol, Ground Truths, 2023-12-04, conversation with Geoffrey Hinton
- The Diary of a CEO, 2025-06-16, "Godfather of AI: I tried to warn them"
- Washington Post, 2022-06-11 (Tiku) and 2022-07-22 (firing)
- Lemoine, B., Medium, 2022-06-11, "Is LaMDA Sentient? An Interview"
- Aguera y Arcas, B., The Economist, 2022-06, on emergent behavior in LaMDA
- Bender & Koller 2020 (ACL, "Climbing towards NLU", the octopus test); Bender et al. 2021
  (FAccT, "Stochastic Parrots") - the canonical contra positions, not archived as entries
  because they lack arXiv/PubMed identifiers under the archive naming contract

## Sources (non-archive), Part 4 cluster

- Coxon, J., X thread @hilbertspaess, 2026-09-09 00:04 UTC, 7 posts
  (x.com/hilbertspaess/status/2097476196791709843)
- Wall Street Journal, 2026-09-09, "Anthropic Researcher Quits Over 'Out-of-Control' AI Fears"
- Hubinger, E., X reply @EvanHub status/2097497037956891126, 2026-09-09; CNBC and Forbes
  coverage same day
- Sharma, M., resignation letter on X @MrinankSharma status/2020881722003583421, 2026-02-09;
  BBC "AI safety leader says 'world is in peril' and quits to study poetry", 2026-02-13
- heise online, 2026-09-09, "Anthropic-Forscher kuendigt mit dramatischem Text -
  Branche erwarte Ausloeschung" (Martin Holland)
- OHCHR, 2026-09, High Commissioner Türk update to the Human Rights Council
  (ohchr.org/en/statements-and-speeches/2026/09/high-commissioner-turk-updates-human-rights-council-human-rights)
- Anthropic, Claude Opus 4.6 System Card (Feb 2026), model welfare assessment:
  15-20% self-assessed consciousness probability; Fish, K., 80,000 Hours podcast,
  2025-08-28 (~20% glimmer estimate)
- The Times, 2026-09-07, Hinton interview accompanying the UK Artificial Superintelligence
  Security Bill (ControlAI draft, Alex Sobel MP)
- BBC Newsnight, aired 2026-09-09, Hinton interview; secondary reporting 2026-09-10
  (Business Insider and others); primary broadcast not fetched

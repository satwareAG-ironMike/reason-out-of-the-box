# Hearing the Bell Ring Back: A Receiver-Side Formalism in Reply to Lerchner's Abstraction Fallacy

| Field | Value |
|-------|-------|
| PhilPapers | [DEVHTB-2](https://philpapers.org/rec/DEVHTB-2) ([PhilArchive PDF](https://philpapers.org/archive/DEVHTB-2.pdf)) |
| Authors | Alex Deva |
| Venue | PhilArchive preprint (2026-05), part of the manuscript "The Pulse Goes on - a Philosophy of Truth for the Age of Reasoning Instruments"; **preprint**, not peer-reviewed |
| Year | 2026 |
| Archive round | 8 - Do LLMs think? Hinton and Lemoine claims, pro and contra |
| Archived | 2026-09-06 (full text verified 2026-09-06) |

## Abstract (condensed)
Concedes Lerchner's mapmaker argument in full and develops the consequence he leaves
open: a formal receiver side for the sensor-instrument loop between a living
experiencer (sensor) and a computational reasoning system (instrument), built from
variational free energy, Shannon channel capacity, signal-detection theory, and partial
information decomposition, yielding a per-turn loop-closure rate rho in bits.

## Key findings (verified from full text)
- Four conceded theses, one opened question: embodiment solves referential symbol
  grounding (Lerchner sec 4.1, citing Harnad 1990), so the open problem is what happens
  "in the referential register, when two distinct mapmakers share a target" (sec 1).
- Four-layer stack: free-energy reduction (clipped delta-F per turn), channel capacity
  as a conceptual ceiling with transfer-entropy estimates, discrimination index d'
  against noise/sycophancy/projection nulls, and PID synergy; a closure inequality
  bounds per-turn synergistic gain under explicit Markov assumptions; six limit cases
  hold by construction; PID measure non-uniqueness handled by a primary estimator
  (BROJA) plus sensitivity checks.
- Pre-registered protocol P1-P4: 200 existing Claude dialogues (secondary use, IRB
  exemption route), 3 blind raters, Fleiss kappa >= 0.70 target on a 30-dialogue pilot,
  power analysis n >= 64 per group (Cohen's d = 0.5, alpha = 0.05, power = 0.80);
  transfer entropy via k-NN conditional mutual information (JIDT) on sentence
  embeddings (sec 7.1).
- Kill conditions: KC1 (tight-loop synergy <= autonomous-output synergy makes the
  metric "fiction") and KC4 (no new predictions = post-hoc rationalization); the
  P1-P4 predictions are the KC4 answer (sec 7.3).
- External validation is "suggestive consistency", not derivation: TRIBE v2
  (d'Ascoli et al., 2026) recovers faces/places/body/characters localizers zero-shot
  (R = 0.60-0.79) but not tools (R = 0.12); the named alternative explanation
  (inter-subject variability of tool representations) is explicitly not ruled out
  (sec 7.2).
- Boundary statement: "rho > 0 does not imply consciousness anywhere in the loop";
  the framework occupies only the referential register, "nothing here lifts into the
  phenomenal register he reserves" (sec 9).

## Relevance to core question
**Framework, not evidence; methodologically adjacent to the project's own study
design.** The paper proposes - and has not run - a falsifiable measurement protocol
for human-AI exchange quality (loop-productive vs sycophantic/dead), which is the
measurement problem behind the thesis program's M4 human-baseline arm (issue #13) and
echoes the round 5 finding that validation is not native: recognition is formalized as
a bounded, measurable update, not a qualia-laden faculty. As philosophy it is a
preprint reply inside an unmoderated preprint debate; as method it is a candidate
instrument, untested until its own protocol is executed.

## Citation
Deva, A. (2026). Hearing the Bell Ring Back: A Receiver-Side Formalism in Reply to
Lerchner's Abstraction Fallacy. PhilArchive preprint, May 2026. PhilPapers record
DEVHTB-2, https://philpapers.org/rec/DEVHTB-2

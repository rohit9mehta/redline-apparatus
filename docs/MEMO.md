# Grounding is the redlining bottleneck — and the reward function

*Rohit Mehta · September 2026 · companion memo to
[redline-apparatus](../README.md)*

## 1. What RedlineBench actually measures

The [leaderboard](https://www.micro1.ai/benchmark/crosby-micro1-redlinebench)
tops out at 50.5% (GPT-5.5), and Gemini 3.5 **Flash** (45.1%) outscores Claude
Opus 4.8 (44.4%). When a small fast model beats a frontier model on a legal
benchmark, the benchmark is not capability-bound — it is measuring something
the big models don't do *by default*. The published failure analysis says what
that is:

- models accept counterparty redlines they should fight (80–99% pass on
  accept-rubrics, 6–50% on reject-rubrics);
- they gut and rewrite paragraphs where attorneys make three small in-place
  edits (62–81% block edits vs. 51%; 318–518-char edits vs. 101);
- they misrank what attorneys treat as most important, worst on opening
  moves.

These are failures of *grounding* (deciding from the playbook rather than
from an agreeable prior) and *discipline* (drafting within measurable
behavioral norms). Both are fixable outside the weights.

## 2. A transposition, not an invention

I spent this year building a translation agent for Sanskrit philosophical
commentary — a domain with the same shape as contract redlining, in the
sense that matters:

| Commentarial translation | Contract redlining |
|---|---|
| The verse alone underdetermines the translation | The clause alone underdetermines the right move |
| The commentary (bhāṣya) is the authority that resolves it | The playbook / precedent is the authority that resolves it |
| Every choice ships with a cited apparatus (commentary line numbers) | Every edit ships with a margin comment; here, backed by a rule card with a verbatim playbook quote |
| Citations are audited: 304 quotes checked, 0 fabricated | The gate audits every rule-card quote against the grounding text; a paraphrase counts as fabricated |
| Morphology verified by a Pāṇinian derivation engine before shipping | Surgicalness, coverage, dispositions, and voice verified deterministically before the agent may finish |
| Verify-feedback retry removed all recurrent claim failures | Gate-feedback retry: fix FAILs, re-run, then finish |

The agent here (`ApparatusClaudeCode`) is that architecture applied to
RedlineBench's own harness: same frozen tasks, same frozen 3-judge panel,
same model — the only change is the scaffold.

## 3. What changed (A/B on the frozen harness)

Sixteen trials: 8 tasks (first task per scenario × turn cell, scenarios
1–2; rule fixed before any run) × {stock claude-code, apparatus}, same
model, same frozen judges. Two results, pointing in opposite directions:

**Form moved.** The baseline reproduces the published frontier failure
profile almost exactly — 73% block edits at 352 chars/edit vs. the
attorneys' 34% / 84. The apparatus arm lands at 45% / 215, most of the way
to attorney norms, measured with the benchmark's own `docx_metrics.py`.
Grounding held everywhere: 127/127 rule-card quotes verbatim (0
fabricated), 259 clause-level dispositions, 8/8 gates green.

**Judgment did not.** Panel scores: baseline 48.8 [31.5–65.6] vs.
apparatus 40.2 [26.7–52.8] — statistically indistinguishable at this n,
with the decline concentrated in deal-closing orientation (65→22) and
counterparty-acceptance prediction (50→25); legal correctness flat. The
over-acceptance bias, measured on reject-shaped rubrics, did not improve.

I did not tune on the judges, and I'm reporting the miss as prominently as
the hit. The honest synthesis: **deterministic verification buys you
everything deterministic verifiers can see — drafting shape, citation
integrity, coverage discipline — and none of the strategic judgment the
rubrics actually grade.** RedlineBench's rubric layer resisted process
scaffolding. That is a compliment to the benchmark: it is measuring the
thing that can't be prompted in.

## 4. The part I'd actually pitch: the benchmark is a reward function

The A/B above is why this section matters more, not less. If scaffolding
could buy judgment at inference time, the training story would be
optional. It can't — form is scaffoldable, judgment has to come from the
weights — and I've seen this exact split before: in my Sanskrit pipeline,
the analyzer's *morphology* was fixable with verifiers, but an override
audit showed the remaining errors were *interpretive* (46% compound-
boundary judgments that only the commentary resolves). Same shape here:
the gate fixes mechanics; the rubric-graded judgment is the part that
needs supervised signal.

RedlineBench contains everything needed to *train* the behavior, not just
measure it: attorney-authored rubrics with weights, penalty rubrics, and
deterministic document diagnostics. That combination — sparse expert rubric
+ dense deterministic verifier — is exactly what I used in the Sanskrit
project to fine-tune a 300M-parameter model (ByT5-Sanskrit → "Vyākaraṇī")
with a grammar engine in the training loop:

- every training claim machine-verified before it entered the set;
- a frozen, sha-pinned benchmark (never trained on) with McNemar
  significance tests between checkpoints;
- outcome: **statistical tie with the strongest frontier model** on the
  hardest split (84.2 vs. 84.7, p = 0.74) at **$0.012 per 1k words vs.
  $4.60–11.30** — a ~400× cost gap.

For a firm that pays inference on every contract, that cost curve is margin.
The path here is the same one I already walked end-to-end, solo:

1. **Scaffold** (this repo, done): establish which failure modes respond to
   grounding + deterministic gating (drafting form, citation integrity,
   disposition discipline) and which don't (strategic judgment). No
   training, no contamination risk — and the split defines what the
   training signal must carry.
2. **Verifier-filtered data**: generate negotiation trajectories on *held-out
   scenarios* (RedlineBench has 3 — the test set must stay frozen; new
   scenarios are cheap to synthesize from playbook + template pairs, and
   EDGAR amendment filings give real before/after edit pairs), keep only
   gate-clean, rubric-passing trajectories.
3. **Distill** into a small model whose reward was the gate + judge panel —
   the "surgical redliner" that runs at Flash prices with attorney-shaped
   behavior, and an eval story a client (or a court) can audit: every edit
   carries a citation that was machine-checked against the playbook.

## 5. Integrity notes

- Tasks, rubrics, judges: byte-identical to the published benchmark.
- Subset rule fixed before any run (first task per scenario × turn cell);
  no task selection after seeing results.
- Surgicalness numbers computed with the benchmark's own vendored
  `docx_metrics.py` (MIT), not a reimplementation.
- Nothing here trains on RedlineBench, and nothing should: with 3 scenarios,
  the benchmark *is* the test set. (My own analyzer benchmark ships with a
  sha256 manifest and a "NEVER train on it" line for the same reason.)

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

*(results table from `work/metrics_summary.json` + `surgicalness.json` goes
here — judge-panel scores by turn/side/category, plus the benchmark's own
behavioral diagnostics for baseline vs. apparatus arms)*

The behavioral deltas are the point: they are deterministic, cheap to
measure, and they moved. Judge-panel scores on a 12-task subset carry wide
error bars — I report them with that caveat and did not tune on them.

## 4. The part I'd actually pitch: the benchmark is a reward function

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

1. **Scaffold** (this repo): prove the failure modes respond to grounding +
   deterministic gating. No training, no contamination risk.
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

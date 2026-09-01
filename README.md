# redline-apparatus

**A playbook-grounded, verifier-gated redlining agent for
[RedlineBench](https://www.micro1.ai/benchmark/crosby-micro1-redlinebench)** —
Crosby × micro1's multi-turn contract-negotiation benchmark.

Every redlining decision must cite its authority, and a deterministic gate
measures the output — with the benchmark's own metric code — before the agent
is allowed to finish. Tasks, rubrics, and judges stay byte-identical to the
published benchmark; everything here is agent-side.

## Why

RedlineBench's [published failure analysis](https://www.micro1.ai/benchmark/crosby-micro1-redlinebench)
found that frontier models fail contract negotiation in three characteristic
ways. Each is a grounding-and-verification failure, not an intelligence
failure — and each maps to a mechanism in this agent:

| Published failure mode | Mechanism here |
|---|---|
| **Over-acceptance bias** — models pass 80–99% of accept-rubrics but only 6–50% of reject-rubrics | Every counterparty tracked change and comment thread gets a written **disposition** (reject / counter / accept), and *accepting requires an affirmative playbook-grounded reason*. The gate fails the run if any counterparty change lacks one. |
| **Lack of surgicalness** — 62–81% block edits vs. attorneys' 51%; mean edit 318–518 chars vs. attorneys' 101 | Drafting discipline in the protocol, then the gate measures the redline with the benchmark's own inline/block metric (`docx_metrics.py`, vendored verbatim) and fails runs that gut paragraphs. |
| **Issue prioritization** — models miss what attorneys treat as most important | The playbook is compiled into **rule cards with verbatim quotes** (machine-audited against the grounding text — a paraphrase counts as a fabricated citation), and triage is a *written, cited artifact* produced before the first edit — not a plan "in your head". |

## How it works

`ApparatusClaudeCode` subclasses Harbor's stock `claude-code` agent and adds:

1. **The Apparatus protocol** (`src/redline_apparatus/protocol.py`), appended
   to the system prompt: rules → triage + dispositions → surgical drafting →
   mandatory gate.
2. **A pre-run environment setup** that snapshots the pristine contract
   (so the gate can tell the agent's edits from the counterparty's) and
   installs `apparatus_gate.py` in the container.

The gate (`src/redline_apparatus/payload/apparatus_gate.py`) checks, all
deterministically:

| Check | What it enforces |
|---|---|
| V1 validity | docx loads; the agent actually produced attributed tracked changes |
| S1 surgicalness | the benchmark's own inline/block metric + mean edit size |
| P1/P2 phrases & voice | the brief's forbidden phrases (regex-scanned) and comment-voice rules |
| C1 coverage | every tier-1/2 triage issue has a visible move at its paragraphs |
| C2 dispositions | every counterparty revision/thread is covered by a written, grounded disposition |
| C3 follow-through | every reject/counter has a tracked counter-edit or thread reply |
| G1 citations | every playbook quote in the rule cards is verbatim in the grounding files |

The agent must fix FAILs and re-run the gate before finishing. Apparatus
artifacts (`rules.json`, `triage.json`, `gate_report.json`) are collected per
trial — every edit in the apparatus arm traces to a machine-checked playbook
citation.

## Results

A/B on an 8-task subset: the lexicographically first task in every
scenario-1 and scenario-2 turn cell — 4 turns × both sides × two SaaS-MSA
scenarios. The subset rule was fixed before any run; scenario 3 was dropped
for budget before any scenario-3 task was run. Same frozen tasks, same
frozen 3-judge panel, same model (`claude-sonnet-5`) — only the agent
scaffold differs.

**The scaffold closed the form gap, not the judgment gap.** That split is
the finding.

### Behavioral profile (deterministic, docx-level — no judges)

| actor | inline share | block share | mean edit (chars) |
|---|---|---|---|
| attorney (represented side, golden files) | 66% | 34% | 84 |
| claude-code baseline | 27% | 73% | 352 |
| **+ apparatus** | **55%** | **45%** | **215** |

The baseline reproduces the published frontier failure profile almost
exactly (62–81% block edits, 318–518-char means). The apparatus arm moves
most of the way to attorney drafting norms — and every one of its 127
playbook rule-card quotes across the grid verified verbatim against the
grounding text (0 fabricated), with 8/8 final gate reports PASS, 83 triaged
issues, and 259 clause-level dispositions collected as machine-checkable
artifacts.

### Judge panel (attorney rubrics, 3-judge majority)

| arm | overall (turn-weighted) | 95% CI |
|---|---|---|
| claude-code baseline | 48.8 | 31.5–65.6 |
| + apparatus | 40.2 | 26.7–52.8 |

No improvement — a statistically indistinguishable decline at n = 8 input
groups, concentrated in the *strategic* categories (deal-closing
orientation 65→22, counterparty-acceptance prediction 50→25) while legal
correctness stayed flat (54→49). An exploratory cut over reject-shaped
rubrics shows the over-acceptance bias did not improve either.

### Reading

Deterministic verification moved everything deterministic verifiers can
see: edit shape, citation integrity, coverage, disposition discipline.
It did not move — and slightly taxed — the strategic judgment the rubrics
actually grade. **RedlineBench's rubric layer resisted process
scaffolding**, which is exactly what a good benchmark should do, and it
sharpens where the remaining gap lives: not in drafting mechanics, but in
negotiation judgment. That is a *training-signal* problem, not a
prompting problem — see [docs/MEMO.md](docs/MEMO.md).

Full outputs: [`results/`](results/) — metrics summary, per-category
tables, behavioral profiles, all 16 redlined .docx files (open them in
Word's Review pane), and the apparatus audit trail per task.

## Reproduce

```bash
git clone https://github.com/crosbylegal/redline-bench vendor/redline-bench
uv venv .venv && source .venv/bin/activate
uv pip install -e "vendor/redline-bench[docx]" -e . harbor
cp vendor/redline-bench/.env.template .env   # add your provider keys
python scripts/run_ab.py --smoke             # 1 task, both arms
python scripts/run_ab.py                     # 12-task subset, both arms
```

Requires Docker. The benchmark dataset (CC-BY-4.0) downloads automatically
from [`crosbylegal/RedlineBench`](https://huggingface.co/datasets/crosbylegal/RedlineBench).

## Integrity

- **Task bundles, rubrics, and judge code are never modified** — the agent
  intervention is an appended system prompt plus files staged under
  `/app/.apparatus/` in the container.
- **No training on the benchmark.** This is scaffolding only.
- `src/redline_apparatus/payload/docx_metrics.py` is vendored verbatim from
  [crosbylegal/redline-bench](https://github.com/crosbylegal/redline-bench)
  (MIT) so surgicalness is measured with the benchmark's exact definitions.

## Where this comes from

The architecture transposes a pipeline I built for a different
low-resource, high-precision domain: translating Sanskrit philosophical
commentary, where every translation decision must cite the commentary that
resolves it and every morphological claim is verified by a Pāṇinian
derivation engine before it ships.
Commentary → playbook; cited apparatus → margin comments; grammar engine →
deterministic contract checks. The follow-on in both domains is the same:
a benchmark's deterministic checks + rubric judges are a *reward function*,
which is how you distill a small, cheap model that holds the frontier line —
see `docs/MEMO.md`.

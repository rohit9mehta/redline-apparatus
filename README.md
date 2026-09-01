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

*(A/B on a 12-task subset — the lexicographically first task in every
scenario × turn cell — same frozen tasks, same frozen judge panel, same
model; only the agent scaffold differs. Filled in from
`work/metrics_summary.json` after runs.)*

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
derivation engine before it ships (live demo: Shastra <!-- TODO: Vercel URL -->).
Commentary → playbook; cited apparatus → margin comments; grammar engine →
deterministic contract checks. The follow-on in both domains is the same:
a benchmark's deterministic checks + rubric judges are a *reward function*,
which is how you distill a small, cheap model that holds the frontier line —
see `docs/MEMO.md`.

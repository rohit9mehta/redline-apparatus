# redline-apparatus

**Can a checklist and an automated checker make an AI negotiate contracts like a lawyer?**

An A/B test on [RedlineBench](https://www.micro1.ai/benchmark/crosby-micro1-redlinebench),
Crosby × micro1's contract-negotiation benchmark. Same model, same tasks,
same judges. The only change is a process wrapper around the agent.

## TL;DR

- **Why.** Crosby's leaderboard tops out near 50, and Gemini Flash beats
  Claude Opus, so the benchmark is not capability-bound. Its three published
  failure modes (over-acceptance, heavy-handed edits, wrong priorities) read
  like habits. If they are habits, a process wrapper should fix them at
  inference with no training. If they are judgment, it will not. Either
  answer is useful.
- **What.** A controlled A/B on 8 RedlineBench tasks. Same model
  (`claude-sonnet-5`), same tasks, same frozen 3-judge panel. The only
  change is a wrapper that makes the agent quote the playbook verbatim,
  write a ranked issue list, log an accept / reject / counter decision with
  a reason for every counterparty edit, make small edits, and pass a
  deterministic checker before it can finish.
- **Editing behavior moved a lot.** Paragraph rewrites fell from 73% to 45%
  (attorneys: 34%). Mean edit size fell from 352 to 215 characters
  (attorneys: 84). 127 playbook citations, 0 fabricated. The plain baseline
  reproduced Crosby's published frontier profile almost exactly.
- **Judge scores did not improve.** 48.8 to 40.2, not significant at n = 8.
  The drop sits in deal-closing orientation and counterparty-acceptance
  prediction. Legal correctness flat. Over-acceptance did not improve.
- **What it means.** One failure mode is a habit (edit form). Two are
  judgment (over-acceptance, priorities). Process fixed the habit and did
  not touch the judgment. If judgment could be prompted in, anyone with a
  frontier API key could build this product. With a straightforward
  scaffold, it cannot. Judgment has to come from the model, and training it
  needs exactly what the benchmark contains: attorney rubrics with weights
  plus deterministic document checks. That is a reward function, not just a
  scoreboard. It is also a validity result for the benchmark: a reasonable
  process hack did not move the rubric score.
- **Caveats.** 8 tasks, one model, scenarios 1 and 2 only, one night. The
  "accept needs a reason" rule probably made the agent too hawkish late in
  the negotiation (biggest drop at turn 3). The claim is that one sensible
  scaffold failed to buy judgment, not that none could. Full argument in
  [docs/MEMO.md](docs/MEMO.md).

## The problem

RedlineBench drops an agent into a live negotiation as in-house counsel for
one side: here is the contract, your playbook, and the commercial context;
return a Word file with tracked changes and margin comments. Three LLM
judges grade it against attorney-written rubrics.

Crosby's [published analysis](https://www.micro1.ai/benchmark/crosby-micro1-redlinebench)
found frontier models fail in three ways:

1. **Over-acceptance.** They accept counterparty edits they should fight
   (80–99% pass on accept-rubrics, 6–50% on reject-rubrics).
2. **Heavy-handed edits.** They rewrite paragraphs where attorneys change a
   few words (62–81% block edits vs. 51%; 318–518-char edits vs. 101).
3. **Wrong priorities.** They miss what attorneys treat as most important.

## Why try process before training

Crosby's leaderboard tops out near 50%, and a small fast model (Gemini 3.5
Flash, 45.1%) outscores Claude Opus 4.8 (44.4%). When a small model beats a
big one on a legal test, the benchmark is measuring something the models do
not do by default, not raw capability. The three published failure modes
read like habits: too agreeable, too heavy-handed, wrong priorities. Habits
might be fixable with process, outside the weights. That is the cheapest
possible fix if it works, and either outcome is useful. If scaffolding
works, it is a product lever. If it does not, the gap is in the model's
judgment, which points at training, and the benchmark's rubrics and checks
are the training signal.

The architecture was already built for another domain (see
[Origin](#origin)), so the test cost one night.

## The intervention

`ApparatusClaudeCode` wraps Harbor's stock `claude-code` agent. No model
change, no task change. It appends a protocol to the system prompt and
installs a checker in the container. The agent must, in order:

1. **Write the rules.** Distill the playbook into rule cards, each with a
   verbatim quote from the playbook.
2. **Triage before editing.** Rank every issue in the contract. Give every
   counterparty edit a written decision, accept / reject / counter, with a
   reason. Accepting requires an affirmative playbook-grounded reason.
3. **Edit surgically.** Small in-sentence edits, not paragraph rewrites.
4. **Pass the gate.** Run a deterministic checker before finishing. It fails
   the run if any quote is not verbatim in the playbook, any major issue
   has no edit, any reject/counter has no visible counter-move, any
   counterparty edit lacks a decision, or the edits are not surgical by the
   benchmark's own metric. Failures must be fixed and the gate re-run.

Each mechanism targets one published failure mode:

| Failure mode | Mechanism |
|---|---|
| Over-acceptance | Written disposition on every counterparty change; accepting needs a grounded reason |
| Heavy-handed edits | Drafting rules, then the gate measures surgicalness with the benchmark's own metric |
| Wrong priorities | Triage is a written, cited artifact produced before the first edit |

## The experiment

8 tasks: the first task in every scenario × turn cell for scenarios 1 and 2
(4 turns, both sides). The subset rule was fixed before any run. Scenario 3
was dropped for budget before any scenario-3 task ran. Each task ran twice,
plain and wrapped, with `claude-sonnet-5` and the benchmark's frozen 3-judge
panel. 16 trials total.

## Results

### Editing behavior (measured from the .docx, no judges)

| actor | inline edits | paragraph rewrites | mean edit (chars) |
|---|---|---|---|
| attorneys (golden files, represented side) | 66% | 34% | 84 |
| claude-code baseline | 27% | 73% | 352 |
| **+ apparatus** | **55%** | **45%** | **215** |

The baseline reproduces Crosby's published frontier profile almost exactly.
The wrapped agent moves most of the way to attorney norms. Across the 8
tasks: 127 rule-card quotes, 0 fabricated; 83 triaged issues; 259
clause-level dispositions; 8/8 gates PASS.

### Judge panel (attorney rubrics, 3-judge majority)

| arm | overall (turn-weighted) | 95% CI |
|---|---|---|
| claude-code baseline | 48.8 | 31.5–65.6 |
| + apparatus | 40.2 | 26.7–52.8 |

| rubric category | baseline | + apparatus |
|---|---|---|
| Legal correctness | 54 | 49 |
| Commercial context | 34 | 29 |
| Negotiation quality | 50 | 38 |
| Counterparty acceptance prediction | 50 | 25 |
| Deal-closing orientation | 65 | 22 |

No improvement. The intervals overlap heavily, so this is not a real
decline at n = 8, but it is clearly not a win. The drop sits in the
strategic categories. Legal correctness is flat.

## What this means

- **Deterministic verification bought everything a verifier can see:**
  edit shape, citation integrity, issue coverage, a written decision on
  every counterparty change.
- **It bought none of the judgment the rubrics grade:** when to fight, when
  to fold, what the other side will accept.
- **A likely self-inflicted wound.** Requiring a reason to accept biases the
  agent toward fighting. The biggest drop is at turn 3 (52.9 to 35.4),
  where the deal should be closing. The protocol was probably too hawkish
  late in the negotiation.
- **The benchmark held.** Its rubric layer resisted process scaffolding,
  which is what a good benchmark should do. The remaining gap is in
  negotiation judgment, not drafting mechanics. That is a training-signal
  problem, not a prompting problem.

## Caveats

8 tasks, one model, two of three scenarios, one night. Treat this as a
controlled pilot that diagnoses which failure modes are process-fixable,
not as a leaderboard entry.

## Repo layout

- `src/redline_apparatus/protocol.py`: the protocol appended to the system prompt
- `src/redline_apparatus/payload/apparatus_gate.py`: the deterministic gate
- `src/redline_apparatus/payload/docx_metrics.py`: vendored verbatim from
  [crosbylegal/redline-bench](https://github.com/crosbylegal/redline-bench)
  (MIT, notice in `LICENSE.redline-bench` alongside it)
- `scripts/run_ab.py`: A/B driver and aggregation
- `results/`: scores, per-category tables, all 16 redlined .docx files
  (open in Word's Review pane), and the per-task audit trail (rule cards,
  triage + dispositions, gate report)

## Reproduce

```bash
git clone https://github.com/crosbylegal/redline-bench vendor/redline-bench
uv venv .venv && source .venv/bin/activate
uv pip install -e "vendor/redline-bench[docx]" -e . harbor
cp vendor/redline-bench/.env.template .env   # add your provider keys
python scripts/run_ab.py --smoke             # 1 task, both arms
python scripts/run_ab.py                     # 12-task subset (all 3 scenarios), both arms
```

The published results are the 8 scenario-1/2 tasks of that subset; pass
them with `--task` to match exactly. Requires Docker. The dataset
(CC-BY-4.0) downloads automatically from
[Hugging Face](https://huggingface.co/datasets/crosbylegal/RedlineBench).

## Integrity

- Tasks, rubrics, and judge code are byte-identical to the published
  benchmark. The intervention is an appended system prompt plus files
  staged under `/app/.apparatus/` in the container.
- Subset chosen by rule before any run. No task selection after seeing
  results.
- No training on the benchmark. With 3 scenarios, the benchmark is the
  test set.

## License

MIT. Contract documents under `results/` derive from the RedlineBench
dataset (CC-BY-4.0, Crosby Legal).

## Origin

The architecture is transposed from a pipeline for translating Sanskrit
philosophical commentary, where every translation decision cites the
commentary that resolves it and every grammatical claim is verified by a
derivation engine before it ships. Commentary becomes playbook; cited
apparatus becomes margin comments; grammar engine becomes deterministic
contract checks. The follow-on is the same in both domains: use the
deterministic checks plus rubric judges as a reward function to distill a
small, cheap model. See [docs/MEMO.md](docs/MEMO.md).

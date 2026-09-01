### Judge-panel scores (benchmark's own scoring pipeline)

| arm | overall (turn-weighted) | 95% CI | gate failures | trials |
|---|---|---|---|---|
| claude-sonnet-5-baseline | **48.8** | 31.5–65.6 | 0 | 8 |
| claude-sonnet-5-apparatus | **40.2** | 26.7–52.8 | 0 | 8 |

### By turn

| arm | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| claude-sonnet-5-baseline | 25.5 | 63.8 | 52.9 | 52.9 |
| claude-sonnet-5-apparatus | 19.0 | 59.6 | 35.4 | 46.7 |

### By side (turn-weighted)

| arm | A | B |
|---|---|---|
| claude-sonnet-5-baseline | 58.9 | 38.7 |
| claude-sonnet-5-apparatus | 46.0 | 34.4 |

### By scenario (turn-weighted)

| arm | 1 | 2 |
|---|---|---|
| claude-sonnet-5-baseline | 44.7 | 52.9 |
| claude-sonnet-5-apparatus | 42.1 | 38.2 |

### By rubric category

| arm | Commercial Context | Counterparty Acceptance Prediction | Deal-closing Orientation | Legal correctness | Negotiation Quality |
|---|---|---|---|---|---|
| claude-sonnet-5-baseline | 33.9 | 50.0 | 65.2 | 53.7 | 50.0 |
| claude-sonnet-5-apparatus | 29.3 | 25.0 | 21.7 | 49.2 | 38.3 |

### Behavioral profile (docx-level, deterministic — no judges)

| actor | inline share | block share | mean edit (chars) | events | tasks |
|---|---|---|---|---|---|
| expert (represented side) | 66% | 34% | 83.8 | 1113 | 7 |
| claude-sonnet-5-apparatus | 55% | 45% | 215.0 | 109 | 8 |
| claude-sonnet-5-baseline | 27% | 73% | 352.2 | 102 | 8 |

*(attorney baseline: the represented side's attorney layers in the benchmark's own `attorney_redlines.docx` golden files; inline/block per the benchmark's `docx_metrics.py`, threshold 30%)*

#!/usr/bin/env python3
"""Render work/metrics_summary.json + work/surgicalness.json into a
Markdown results block (stdout) for README.md / docs/MEMO.md."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def pct(x, digits=1):
    return f"{100 * x:.{digits}f}" if isinstance(x, (int, float)) else "—"


def main() -> int:
    work = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "work"
    ms = json.loads((work / "metrics_summary.json").read_text())
    rows = ms.get("leaderboard", [])
    labels = [r["model"] for r in rows]

    print("### Judge-panel scores (benchmark's own scoring pipeline)\n")
    print("| arm | overall (turn-weighted) | 95% CI | gate failures | trials |")
    print("|---|---|---|---|---|")
    for r in rows:
        ci = r.get("ci") or [None, None]
        ci_s = f"{pct(ci[0])}–{pct(ci[1])}" if ci and ci[0] is not None else "—"
        print(f"| {r['model']} | **{pct(r.get('overall_turn_weighted'))}** | {ci_s} "
              f"| {r.get('n_gate_failures', 0)} | {r.get('n_trials', '—')} |")

    for key, title in (
        ("by_turn", "By turn"),
        ("by_side_turn_weighted", "By side (turn-weighted)"),
        ("by_scenario_turn_weighted", "By scenario (turn-weighted)"),
        ("by_category", "By rubric category"),
    ):
        cols = sorted({c for r in rows for c in (r.get(key) or {})})
        if not cols:
            continue
        print(f"\n### {title}\n")
        print("| arm | " + " | ".join(str(c) for c in cols) + " |")
        print("|" + "---|" * (len(cols) + 1))
        for r in rows:
            m = r.get(key) or {}
            print(f"| {r['model']} | " + " | ".join(pct(m.get(c)) for c in cols) + " |")

    surg_path = work / "surgicalness.json"
    if surg_path.exists():
        surg = json.loads(surg_path.read_text())
        print("\n### Behavioral profile (docx-level, deterministic — no judges)\n")
        print("| actor | inline share | block share | events | tasks |")
        print("|---|---|---|---|---|")
        order = ["expert"] + [k for k in surg if k != "expert"]
        for actor in order:
            r = surg.get(actor)
            if not r:
                continue
            print(f"| {actor} | {pct(r['inline_share'], 0)}% | "
                  f"{pct(r['block_share'], 0)}% | {r['n_inline'] + r['n_block']} "
                  f"| {r['n_tasks']} |")
        print("\n*(attorney baseline from the benchmark's own "
              "`attorney_redlines.docx` golden files; inline/block per the "
              "benchmark's `docx_metrics.py`, threshold 30%)*")
    return 0


if __name__ == "__main__":
    sys.exit(main())

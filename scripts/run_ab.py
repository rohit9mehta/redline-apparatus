#!/usr/bin/env python3
"""A/B driver: stock claude-code vs. ApparatusClaudeCode on a RedlineBench subset.

Subset rule (no cherry-picking): the lexicographically first task (variant
'a' of the first input group) in every scenario x turn cell -> 12 tasks.

For each arm, runs Harbor over the same frozen tasks, then assembles both
arms into one runs/ tree (arm label used as the "model" row) and builds the
benchmark's own metrics_summary.json + the docx surgicalness table.

Usage:
  python scripts/run_ab.py                    # both arms, 12-task subset
  python scripts/run_ab.py --smoke            # both arms, 1 task
  python scripts/run_ab.py --arm apparatus --task redline-s1-t2-g01a
  python scripts/run_ab.py --report-only      # re-aggregate existing jobs
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR_SRC = ROOT / "vendor" / "redline-bench" / "src"
sys.path.insert(0, str(VENDOR_SRC))
sys.path.insert(0, str(ROOT / "src"))

from dataset import get_benchmark_dir            # noqa: E402  (vendor)
from reproduce import assemble_runs              # noqa: E402  (vendor)
import metrics_summary                           # noqa: E402  (vendor)
from docx_metrics import (                       # noqa: E402  (vendor)
    compute_surgicalness,
    find_expert_docx_paths,
)

ARMS = {
    "baseline": "claude-code",
    "apparatus": "redline_apparatus.agent:ApparatusClaudeCode",
}
APPARATUS_ARTIFACTS = [
    "/app/.apparatus/rules.json",
    "/app/.apparatus/triage.json",
    "/app/.apparatus/gate_report.json",
]


def load_env(env_file: Path) -> None:
    if not env_file.exists():
        sys.exit(f"missing {env_file} — create it with the provider keys")
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def pick_subset(tasks_root: Path) -> list[str]:
    """First task per scenario-turn cell."""
    cells: dict[str, list[str]] = defaultdict(list)
    for t in sorted(p.name for p in tasks_root.iterdir() if p.is_dir()):
        m = re.match(r"redline-(s\d)-(t\d)-", t)
        if m:
            cells[f"{m.group(1)}-{m.group(2)}"].append(t)
    return [names[0] for _, names in sorted(cells.items())]


def stage_tasks(bench: Path, names: list[str], dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for n in names:
        tgt = dest / n
        if not tgt.exists():
            shutil.copytree(bench / "tasks" / n, tgt)


def run_arm(arm: str, tasks_path: Path, jobs_dir: Path, *, model: str,
            n_concurrent: int, env_file: Path) -> Path:
    # Prefer the harbor installed next to this interpreter (the project
    # venv) — the uv-tool harbor cannot import redline_apparatus.
    venv_harbor = Path(sys.executable).parent / "harbor"
    harbor = str(venv_harbor) if venv_harbor.exists() else (
        shutil.which("harbor") or str(Path.home() / ".local/bin/harbor"))
    jobs_dir.mkdir(parents=True, exist_ok=True)
    before = {p.name for p in jobs_dir.iterdir() if p.is_dir()}
    cmd = [
        harbor, "run", "-p", str(tasks_path),
        "-a", ARMS[arm], "-m", model,
        "--n-concurrent", str(n_concurrent),
        "--jobs-dir", str(jobs_dir),
        "--env-file", str(env_file),
        "--yes", "--quiet",
    ]
    if arm == "apparatus":
        for a in APPARATUS_ARTIFACTS:
            cmd += ["--artifact", a]
    print(f"+ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT)
    after = [p for p in jobs_dir.iterdir() if p.is_dir() and p.name not in before]
    if not after:
        sys.exit(f"no new job dir for arm {arm}")
    return max(after, key=lambda p: p.stat().st_mtime)


def latest_job(jobs_dir: Path) -> Path | None:
    dirs = [p for p in jobs_dir.iterdir() if p.is_dir()] if jobs_dir.is_dir() else []
    return max(dirs, key=lambda p: p.stat().st_mtime) if dirs else None


def surgicalness_table(runs_dir: Path, bench: Path, arm_labels: list[str],
                       task_names: list[str]) -> dict:
    experts = find_expert_docx_paths(bench)
    expert_paths = [experts[t] for t in task_names if t in experts]
    by_model = {}
    for label in arm_labels:
        paths = sorted((runs_dir / "trajectories" / label).glob("*/redline.docx"))
        if paths:
            by_model[label] = paths
    return compute_surgicalness(by_model, expert_paths)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="anthropic/claude-sonnet-5")
    ap.add_argument("--arm", choices=list(ARMS), action="append",
                    help="restrict to one arm (repeatable); default both")
    ap.add_argument("--task", action="append",
                    help="explicit task name(s) instead of the subset rule")
    ap.add_argument("--smoke", action="store_true", help="single-task run")
    ap.add_argument("--n-concurrent", type=int, default=4)
    ap.add_argument("--workdir", default=str(ROOT / "work"))
    ap.add_argument("--report-only", action="store_true",
                    help="skip Harbor; re-aggregate the latest job per arm")
    args = ap.parse_args()

    load_env(ROOT / ".env")
    bench = get_benchmark_dir()
    names = args.task or pick_subset(bench / "tasks")
    if args.smoke and not args.task:
        names = names[:1]
    arms = args.arm or list(ARMS)
    print(f"tasks ({len(names)}): {', '.join(names)}")
    print(f"arms: {arms}  model: {args.model}")

    work = Path(args.workdir)
    tasks_path = work / "tasks"
    stage_tasks(bench, names, tasks_path)

    runs_dir = work / "runs"
    if runs_dir.exists():
        shutil.rmtree(runs_dir)

    labels = []
    for arm in arms:
        jobs_dir = work / "jobs" / arm
        if args.report_only:
            job = latest_job(jobs_dir)
            if job is None:
                print(f"(no jobs for arm {arm}; skipping)")
                continue
        else:
            job = run_arm(arm, tasks_path, jobs_dir, model=args.model,
                          n_concurrent=args.n_concurrent, env_file=ROOT / ".env")
        label = f"{args.model.rsplit('/', 1)[-1]}-{arm}"
        n = assemble_runs(job, runs_dir, model_id=label)
        print(f"arm {arm}: assembled {n} trial(s) from {job.name}")
        if n:
            labels.append(label)

    if not labels:
        sys.exit("nothing assembled")

    out = work / "metrics_summary.json"
    rc = metrics_summary.run(runs=runs_dir, out=str(out), benchmark_dir=bench,
                             judge_method="panel")
    if rc:
        print(f"(metrics_summary exited {rc})")

    surg = surgicalness_table(runs_dir, bench, labels, names)
    print("\nSurgicalness (benchmark's own inline/block metric):")
    for actor, row in surg.items():
        print(f"  {actor:28} inline {row['inline_share']:.0%}  "
              f"block {row['block_share']:.0%}  (n_events={row['n_inline'] + row['n_block']}, "
              f"tasks={row['n_tasks']})")
    import json
    (work / "surgicalness.json").write_text(json.dumps(surg, indent=1))
    print(f"\nwrote {out} and {work / 'surgicalness.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

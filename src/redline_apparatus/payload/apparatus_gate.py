#!/usr/bin/env python3
"""Apparatus gate — deterministic self-audit for a redlined contract.

Runs inside the RedlineBench task container, before the agent is allowed
to finish. Checks (each PASS / WARN / FAIL):

  V1 validity        docx loads; >=1 tracked change or comment by --author
  S1 surgicalness    the benchmark's own inline/block metric (vendored
                     docx_metrics.py, MIT, (c) Crosby Legal) on the
                     author's edit events + mean event size
  P1 phrases         forbidden phrases from the brief, scanned over the
                     author's comments
  P2 voice           perfect tense, first-person singular, party names
  C1 coverage        every tier-1/2 triage issue has an author edit or
                     comment in (or adjacent to) its target paragraphs
  C2 dispositions    every foreign tracked change / top-level comment in
                     the ORIGINAL document has a written disposition
  C3 follow-through  reject/counter dispositions have a visible move
  G1 citations       every rules.json quote is verbatim (whitespace- and
                     smart-quote-normalized) in the grounding files

Exit code 1 if any FAIL, else 0. Writes /app/.apparatus/gate_report.json
and prints a compact human-readable report.

Uses the task's own redline_engine (from the installed contract-redliner
skill) for paragraph/comment/revision enumeration, so IDs match what
read_document.py showed the agent.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent

# The task container installs the skill at /skills/contract-redliner
# (task.toml: skills_dir = "/skills"). Overridable for local testing.
import os

_SKILL_SCRIPTS = Path(
    os.environ.get("APPARATUS_SKILLS_DIR", "/skills/contract-redliner/scripts")
)
sys.path.insert(0, str(_SKILL_SCRIPTS))
sys.path.insert(0, str(_HERE))

from redline_engine.document import DocumentView  # noqa: E402

try:
    # Vendored verbatim from crosbylegal/redline-bench (MIT) so the gate
    # measures surgicalness with the benchmark's exact definitions.
    from docx_metrics import _collect_quality_for_docx  # noqa: E402
except Exception:  # pragma: no cover - metric module optional
    _collect_quality_for_docx = None


# ── report plumbing ─────────────────────────────────────────────────

_REPORT: list[dict] = []


def check(check_id: str, status: str, detail: str) -> None:
    _REPORT.append({"id": check_id, "status": status, "detail": detail})


# ── text normalization for citation checks ──────────────────────────

_QUOTE_FOLD = str.maketrans(
    {
        "‘": "'", "’": "'", "“": '"', "”": '"',
        "–": "-", "—": "-", " ": " ",
    }
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.translate(_QUOTE_FOLD)).strip().lower()


# ── forbidden phrase / voice patterns (from the task brief) ─────────

_FORBIDDEN = [
    (re.compile(r"not\s+able\s+to\s+accept", re.I), 'use "We can\'t accept"'),
    (re.compile(r"\brespectfully\b", re.I), "forbidden word"),
    (re.compile(r"would\s+welcome", re.I), "forbidden phrase"),
]
_MARKET = re.compile(r"this\s+is\s+market", re.I)
_FIRST_SINGULAR = re.compile(r"\bI\b|\bI'(?:m|ve|d|ll)\b")
_PERFECT_TENSE = re.compile(r"\bwe(?:'ve|\s+have)\s+\w+ed\b", re.I)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("docx", help="the edited contract (e.g. /app/contract.docx)")
    ap.add_argument("--author", required=True, help="exact author string used for edits")
    ap.add_argument("--apparatus-dir", default=None,
                    help="default: <docx dir>/.apparatus")
    ap.add_argument("--grounding-dir", default=None,
                    help="default: <docx dir>/grounding")
    ap.add_argument("--parties", default=None,
                    help="optional comma-separated party names to flag in comments")
    args = ap.parse_args()

    docx = Path(args.docx)
    app_dir = Path(args.apparatus_dir) if args.apparatus_dir else docx.parent / ".apparatus"
    grounding_dir = (
        Path(args.grounding_dir) if args.grounding_dir else docx.parent / "grounding"
    )
    author = args.author

    # ── V1 validity ────────────────────────────────────────────────
    try:
        view = DocumentView.load(docx)
    except Exception as e:
        check("V1-validity", "FAIL", f"could not load docx: {e}")
        return _finish(app_dir)

    my_revs = [r for r in view.revisions if r.author == author]
    my_cmts = [c for c in view.comments if c.author == author]
    if not my_revs and not my_cmts:
        check("V1-validity", "FAIL",
              f"no tracked changes or comments by author {author!r} — check the "
              f"--author string matches exactly what you passed to the scripts")
    else:
        check("V1-validity", "PASS",
              f"{len(my_revs)} tracked change(s), {len(my_cmts)} comment(s) by {author!r}")

    # ── original snapshot (needed for C2) ──────────────────────────
    original = app_dir / "original.docx"
    orig_view = None
    if original.exists():
        try:
            orig_view = DocumentView.load(original)
        except Exception as e:
            check("A1-apparatus", "WARN", f"original.docx unreadable: {e}")
    else:
        check("A1-apparatus", "WARN",
              "no /app/.apparatus/original.docx snapshot; disposition audit will "
              "use the current file's foreign revisions instead")

    # ── S1 surgicalness (benchmark's own metric) ───────────────────
    if _collect_quality_for_docx is not None:
        raw = _collect_quality_for_docx(docx, author_substring=author)
        if raw and raw.get("event_kinds"):
            kinds = raw["event_kinds"]
            sizes = raw.get("event_sizes", [])
            n = len(kinds)
            block = sum(1 for k in kinds if k == "block")
            block_share = block / n
            mean_size = (sum(sizes) / len(sizes)) if sizes else 0.0
            detail = (
                f"{n} edit event(s): block share {block_share:.0%} "
                f"(attorneys ~51%, frontier models 62-81%), "
                f"mean event size {mean_size:.0f} chars (attorneys ~101, models 318-518)"
            )
            if n >= 4 and (block_share > 0.65 or mean_size > 320):
                check("S1-surgicalness", "FAIL", detail + " — split block rewrites "
                      "into small in-place edits; keep unchanged text unchanged")
            elif n >= 4 and (block_share > 0.50 or mean_size > 180):
                check("S1-surgicalness", "WARN", detail)
            else:
                check("S1-surgicalness", "PASS", detail)
        else:
            check("S1-surgicalness", "WARN", "no author edit events measurable")
    else:
        check("S1-surgicalness", "WARN", "docx_metrics unavailable; skipped")

    # ── P1 / P2 comment language ───────────────────────────────────
    fails, warns = [], []
    for c in my_cmts:
        text = c.text or ""
        for pat, why in _FORBIDDEN:
            if pat.search(text):
                fails.append(f"cmt-{c.id}: {pat.pattern!r} ({why})")
        m = _MARKET.search(text)
        if m:
            if m.start() < 60:
                fails.append(f'cmt-{c.id}: leads with "this is market" — lead with '
                             f"the concrete consequence instead")
            else:
                warns.append(f'cmt-{c.id}: contains "this is market" (supporting '
                             f"color only is allowed — double-check)")
        if _FIRST_SINGULAR.search(text):
            fails.append(f'cmt-{c.id}: first-person singular — always "we"')
        if _PERFECT_TENSE.search(text):
            warns.append(f'cmt-{c.id}: perfect tense — brief wants simple past '
                         f'("We narrowed", not "We have narrowed")')
        if args.parties:
            for name in (p.strip() for p in args.parties.split(",") if p.strip()):
                if re.search(rf"\b{re.escape(name)}\b", text):
                    warns.append(f"cmt-{c.id}: names {name!r} — use we/you")
    if fails:
        check("P1-phrases", "FAIL", "; ".join(fails))
    else:
        check("P1-phrases", "PASS", f"{len(my_cmts)} comment(s) clean of forbidden phrases")
    if warns:
        check("P2-voice", "WARN", "; ".join(warns))
    else:
        check("P2-voice", "PASS", "no voice-lint warnings")

    # ── load apparatus artifacts ───────────────────────────────────
    rules, triage = None, None
    for name, slot in (("rules.json", "rules"), ("triage.json", "triage")):
        p = app_dir / name
        if not p.exists():
            check("A1-apparatus", "FAIL", f"missing {p} — write it (see protocol)")
            continue
        try:
            data = json.loads(p.read_text())
            if slot == "rules":
                rules = data.get("rules", [])
            else:
                triage = data
        except Exception as e:
            check("A1-apparatus", "FAIL", f"{name} is not valid JSON: {e}")
    if rules is not None and triage is not None:
        check("A1-apparatus", "PASS",
              f"{len(rules)} rule card(s), {len(triage.get('issues', []))} issue(s), "
              f"{len(triage.get('dispositions', []))} disposition(s)")

    # paragraphs touched by the author (edits or comment anchors), with ±1 slack
    touched: set[int] = set()
    for r in my_revs:
        for pid in r.paragraph_ids:
            touched.add(_pnum(pid))
    for c in my_cmts:
        for pid in c.paragraph_ids:
            touched.add(_pnum(pid))
    touched_slack = touched | {i + 1 for i in touched} | {i - 1 for i in touched}

    # ── C1 triage coverage ─────────────────────────────────────────
    if triage is not None:
        missing1, missing2 = [], []
        for issue in triage.get("issues", []):
            tier = issue.get("tier")
            if tier not in (1, 2):
                continue
            targets = {_pnum(p) for p in issue.get("paragraph_ids", [])}
            if targets and not (targets & touched_slack):
                (missing1 if tier == 1 else missing2).append(
                    f"{issue.get('id')} ({issue.get('title', '?')})")
        if missing1:
            check("C1-coverage", "FAIL",
                  "tier-1 issue(s) with no edit or comment at their paragraphs: "
                  + "; ".join(missing1))
        elif missing2:
            check("C1-coverage", "WARN",
                  "tier-2 issue(s) unaddressed: " + "; ".join(missing2))
        else:
            check("C1-coverage", "PASS", "every tier-1/2 issue has a visible move")

    # ── C2 disposition completeness ────────────────────────────────
    # A counterparty markup can carry hundreds of raw revision runs, so
    # dispositions target clauses, not runs: "rev-N" / "cmt-N" for a
    # specific item, "p-012" for one paragraph, "p-012..p-019" for a
    # range. A foreign revision counts as dispositioned when its id is
    # listed or every paragraph it touches falls inside some target.
    base_view = orig_view or view
    foreign_revs = [r for r in base_view.revisions if r.author != author]
    foreign_cmts = [c for c in base_view.comments
                    if c.author != author and c.parent_id is None]
    if triage is not None:
        dispositions = triage.get("dispositions", [])
        listed_ids = {d.get("target") for d in dispositions}
        covered_paras: set[int] = set()
        for d in dispositions:
            covered_paras |= _target_paragraphs(d.get("target", ""))

        def _dispositioned(obj, kind: str) -> bool:
            if f"{kind}-{obj.id}" in listed_ids:
                return True
            nums = {_pnum(p) for p in obj.paragraph_ids}
            return bool(nums) and nums <= covered_paras

        missing_revs = [r for r in foreign_revs if not _dispositioned(r, "rev")]
        missing_cmts = [c for c in foreign_cmts if not _dispositioned(c, "cmt")]
        bad_accept = [
            d.get("target") for d in dispositions
            if d.get("decision") in ("accept", "accept_with_edit")
            and not (d.get("rule_ids") or (d.get("reason") or "").strip())
        ]
        if missing_revs or missing_cmts:
            paras = sorted({_pnum(p) for r in missing_revs for p in r.paragraph_ids}
                           | {_pnum(p) for c in missing_cmts for p in c.paragraph_ids})
            unanchored = [f"rev-{r.id}" for r in missing_revs if not r.paragraph_ids]
            unanchored += [f"cmt-{c.id}" for c in missing_cmts if not c.paragraph_ids]
            detail = (f"{len(missing_revs)} counterparty revision(s) and "
                      f"{len(missing_cmts)} thread(s) not covered by any disposition — "
                      f"uncovered paragraphs: {_ranges(paras)} (add clause-level "
                      f"dispositions with p-N..p-M targets)")
            if unanchored:
                detail += ("; unanchored items needing an explicit id target: "
                           + ", ".join(unanchored[:8]))
            check("C2-dispositions", "FAIL", detail)
        elif bad_accept:
            check("C2-dispositions", "FAIL",
                  "acceptances with no grounded reason: " + "; ".join(map(str, bad_accept)))
        else:
            check("C2-dispositions", "PASS",
                  f"all {len(foreign_revs)} foreign revision(s) and "
                  f"{len(foreign_cmts)} thread(s) covered by "
                  f"{len(dispositions)} disposition(s)")

        # ── C3 follow-through ──────────────────────────────────────
        loose = []
        by_rev = {f"rev-{r.id}": r for r in foreign_revs}
        by_cmt = {f"cmt-{c.id}": c for c in foreign_cmts}
        replied_parents = {c.parent_id for c in my_cmts if c.parent_id is not None}
        for d in dispositions:
            if d.get("decision") not in ("reject", "counter", "accept_with_edit"):
                continue
            tgt = d.get("target", "")
            obj = by_rev.get(tgt) or by_cmt.get(tgt)
            if obj is not None:
                if tgt.startswith("cmt-") and obj.id in replied_parents:
                    continue
                targets = {_pnum(p) for p in obj.paragraph_ids}
            else:
                targets = _target_paragraphs(tgt)
            if targets and not (targets & touched_slack):
                loose.append(f"{tgt} ({d.get('decision')})")
        if loose:
            check("C3-follow-through", "WARN",
                  "reject/counter dispositions with no visible move at the target: "
                  + "; ".join(loose[:8]))
        else:
            check("C3-follow-through", "PASS", "every reject/counter has a visible move")

    # ── G1 citation integrity ──────────────────────────────────────
    if rules:
        grounding_texts: dict[str, str] = {}
        if grounding_dir.is_dir():
            for f in grounding_dir.iterdir():
                if f.suffix.lower() in (".md", ".txt"):
                    try:
                        grounding_texts[f.name] = _norm(f.read_text(errors="replace"))
                    except Exception:
                        pass
        # the brief itself may carry playbook content
        for extra in (docx.parent / "instruction.md",):
            if extra.exists():
                grounding_texts[extra.name] = _norm(extra.read_text(errors="replace"))
        all_text = " \n ".join(grounding_texts.values())
        fabricated, near = [], []
        for rule in rules:
            q = _norm(rule.get("quote", ""))
            if not q:
                fabricated.append(f"{rule.get('id')}: empty quote")
                continue
            if q in all_text:
                continue
            ratio = _best_window_ratio(q, all_text)
            if ratio >= 0.90:
                near.append(f"{rule.get('id')} ({ratio:.2f})")
            else:
                fabricated.append(f"{rule.get('id')} (best match {ratio:.2f})")
        if fabricated:
            check("G1-citations", "FAIL",
                  "rule quotes NOT found in grounding (fix the quote to be verbatim): "
                  + "; ".join(fabricated))
        elif near:
            check("G1-citations", "WARN",
                  "near-verbatim quotes (check punctuation): " + "; ".join(near))
        else:
            check("G1-citations", "PASS",
                  f"all {len(rules)} rule quote(s) verbatim in grounding")

    return _finish(app_dir)


def _pnum(pid: str) -> int:
    m = re.search(r"(\d+)", str(pid))
    return int(m.group(1)) if m else -999


def _target_paragraphs(target: str) -> set[int]:
    """Paragraph numbers covered by a disposition target like 'p-012' or
    'p-012..p-019' (rev-/cmt- targets cover none)."""
    m = re.fullmatch(r"p-(\d+)(?:\s*\.\.\s*p-(\d+))?", str(target).strip())
    if not m:
        return set()
    lo = int(m.group(1))
    hi = int(m.group(2)) if m.group(2) else lo
    return set(range(min(lo, hi), max(lo, hi) + 1))


def _ranges(nums: list[int]) -> str:
    """Compact '12-19, 44, 51-53' rendering of sorted paragraph numbers."""
    if not nums:
        return "(none)"
    spans, start, prev = [], nums[0], nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        spans.append(f"p-{start:03d}" if start == prev else f"p-{start:03d}..p-{prev:03d}")
        start = prev = n
    spans.append(f"p-{start:03d}" if start == prev else f"p-{start:03d}..p-{prev:03d}")
    out = ", ".join(spans[:12])
    return out + (f" (+{len(spans) - 12} more)" if len(spans) > 12 else "")


def _best_window_ratio(needle: str, hay: str) -> float:
    """Best difflib ratio of `needle` against same-length windows of `hay`
    (coarse stride for speed)."""
    n = len(needle)
    if not n or not hay:
        return 0.0
    best = 0.0
    stride = max(20, n // 4)
    sm = difflib.SequenceMatcher(b=needle, autojunk=False)
    for i in range(0, max(1, len(hay) - n + 1), stride):
        sm.set_seq1(hay[i:i + n + 40])
        r = sm.ratio()
        if r > best:
            best = r
            if best > 0.97:
                break
    return best


def _finish(app_dir: Path) -> int:
    order = {"FAIL": 0, "WARN": 1, "PASS": 2}
    report = sorted(_REPORT, key=lambda r: (order[r["status"]], r["id"]))
    n_fail = sum(1 for r in report if r["status"] == "FAIL")
    n_warn = sum(1 for r in report if r["status"] == "WARN")
    print("=" * 72)
    print(f"APPARATUS GATE: {'FAIL' if n_fail else 'PASS'} "
          f"({n_fail} fail, {n_warn} warn)")
    print("=" * 72)
    for r in report:
        print(f"[{r['status']:4}] {r['id']}: {r['detail']}")
    try:
        app_dir.mkdir(parents=True, exist_ok=True)
        (app_dir / "gate_report.json").write_text(json.dumps(
            {"overall": "FAIL" if n_fail else "PASS", "checks": report}, indent=1))
    except Exception as e:  # never let reporting kill the gate
        print(f"(could not write gate_report.json: {e})")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())

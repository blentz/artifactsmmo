"""Corroborate `GREY_SKILL_GAP` -- the gather zero-xp band -- against the
learning store.

Server-axiom-signoff discipline, the same one `xp_formula_replay.py` applies to
the COMBAT curve. The documented rule
(https://docs.artifactsmmo.com/concepts/skills) says gathering and crafting xp
falls to zero for content "10+ levels below your skill level", but the prose is
ambiguous at the boundary: does a gap of exactly 10 pay? The decision core
`ai/skill_xp_positive` needs an exact integer answer, so this replays every
observed `ok` `GatherAction` cycle and reports pays/zero bucketed by

    gap = skill_level(before the gather) - resource_level

MIGRATION (2026-08-15, Task 6 of
docs/superpowers/plans/2026-08-15-harnesses-read-the-learning-store.md). This
file used to glob `play-trace-*.jsonl` and recover `gap`/`paid` by pairing each
record against the FOLLOWING record's state snapshot -- a bug a code-review
round caught (see git history and `skill_xp_positive.py`'s docstring): it
manufactured a handful of below-band apparent payers out of a neighbouring
cycle's real yield. Corrected, and measured on that trace corpus, the boundary
was exact: 3231 gathers, 2210 paying at gap <= 10, 1021 zero at gap >= 11, no
exception anywhere. THAT CORPUS IS GONE -- the user deleted every
`play-trace-*.jsonl` file on 2026-08-15 -- and this script can no longer
reproduce that figure; it is preserved as history in
`formal/diff/gather_xp_replay_report.txt`'s git log and in
`skill_xp_positive.py`'s docstring, not asserted here.

This version reads `formal/diff/store_records.load_cycles` instead: every
`cycles` row whose `action_class == "GatherAction"` and `outcome == "ok"`,
attributed against that row's OWN `skill_levels` (the pre-action snapshot,
`Cycle.skill_levels_json`, added by this same migration's Task 1) and OWN
`delta_skill_xp` (never a difference against a neighbouring row -- see
`store_records.py`'s module docstring for why that distinction is exactly the
bug this file already had once). `skill_levels` IS NULLABLE, NOT BACK-FILLED:
every row written before the column landed carries it as `None`, which today
means EVERY historical row. ROWS WITHOUT IT ARE EXCLUDED, NOT DEFAULTED, and
this replay reports the exclusion count and reason rather than silently
shrinking the denominator or inventing a level.

CRAFT IS NO LONGER REPLAYED HERE. It used to be reported alongside GATHER,
ADVISORY only (never raising VIOLATIONS or affecting the exit code), from the
same trace-derived cycle pairing. `formal/diff/craft_xp_replay.py` (Task 5 of
this migration) now owns craft exclusively, reading the learning store's
`craft_yield` table -- a materially different source (upserted per-character
per-item observations, not a per-cycle trace scan) that this file duplicating
would only invite drift between two "craft" numbers measured two different
ways. See that file's module docstring for craft's own story.

COVERAGE CAN COLLAPSE TO ZERO, AND THAT IS THE HONEST RESULT, NOT A BUG IN
THIS FILE. As of this migration landing, no `cycles` row carries
`skill_levels_json` -- the column exists but nothing has been recorded against
it yet. A harness that reports "0 usable observations, band holds" would be
asserting the exact vacuity this project has a standing rule against: it must
FAIL LOUDLY instead, which is what the empty-corpus branch below does. Re-run
once the bot has accumulated cycles since the column landed.

What would falsify `GREY_SKILL_GAP = 11`, once there is anything to check: a
gap >= 11 bucket that PREDOMINANTLY pays, or an in-band bucket that never pays
at all. Both are reported as explicit VIOLATION lines and exit non-zero.
Sub-majority payers in an out-of-band bucket are reported as OUTLIERS with
their counts, so a lag rate (should one ever reappear) stays visible instead of
being asserted away.

Output: formal/diff/gather_xp_replay_report.txt + stdout.
Usage: uv run python formal/diff/gather_xp_replay.py [SNAPSHOT] [DB_PATH]
"""

import collections
import json
import re
import sys
from pathlib import Path

from store_records import CycleRecord, EmptyCorpusError, load_cycles

from artifactsmmo_cli.ai.skill_xp_positive import GREY_SKILL_GAP, skill_xp_positive
from artifactsmmo_cli.learning_db_path import default_learn_db_path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT = REPO_ROOT / "formal" / "diff" / "gather_xp_replay_report.txt"
_GATHER_RE = re.compile(r"^Gather\((\w+)(?:->\w+)?\)$")  # matches GatherAction.learning_key()


def _resource_catalog(snapshot: Path) -> dict[str, tuple[str, int]]:
    """`{resource_code: (skill, level)}` from a raw game-data cache dump."""
    data = json.loads(snapshot.read_text())
    return {r["code"]: (r["skill"], r["level"]) for r in data["resources"]}


def _usable_observations(
    records: list[CycleRecord], resources: dict[str, tuple[str, int]]
) -> tuple[list[tuple[int, bool]], int, int, int]:
    """`(observations, excluded_not_gather, excluded_no_level, excluded_not_in_catalog)`.

    `observations` is `(gap, paid)` pairs. A row is excluded, never defaulted,
    for one of three reasons: it is not an `ok` `GatherAction`; its
    `skill_levels` is `None` (no `skill_levels_json`, or the gathered skill is
    absent from the recorded snapshot); or its resource code is not in the
    current game-data catalog (a resource removed or renamed since the row was
    written)."""
    observations: list[tuple[int, bool]] = []
    excluded_not_gather = 0
    excluded_no_level = 0
    excluded_not_in_catalog = 0
    for rec in records:
        if rec.action_class != "GatherAction" or rec.outcome != "ok":
            excluded_not_gather += 1
            continue
        match = _GATHER_RE.match(rec.action_repr or "")
        entry = resources.get(match.group(1)) if match else None
        if entry is None:
            excluded_not_in_catalog += 1
            continue
        skill, level = entry
        if rec.skill_levels is None or skill not in rec.skill_levels:
            excluded_no_level += 1
            continue
        gap = rec.skill_levels[skill] - level
        paid = rec.delta_skill_xp.get(skill, 0) > 0
        observations.append((gap, paid))
    return observations, excluded_not_gather, excluded_no_level, excluded_not_in_catalog


def _render(buckets: dict[int, list[int]]) -> tuple[list[str], list[str], list[str]]:
    total = sum(sum(v) for v in buckets.values())
    lines = [f"\n## GATHER (load-bearing: {total} cycles)", f"{'gap':>4} {'pays':>6} {'zero':>6}  verdict"]
    violations: list[str] = []
    outliers: list[str] = []
    for gap in sorted(buckets):
        pays, zero = buckets[gap]
        # The model's claim for this bucket, from the live constant. A gap-g
        # bucket is probed at the lowest real content level (1).
        predicted = skill_xp_positive(1, 1 + gap)
        verdict = "PAYS" if pays and not zero else ("ZERO" if zero and not pays else "mixed")
        flag = ""
        if predicted and pays == 0 and zero:
            flag = "  <-- VIOLATION: model says pays, bucket never paid"
        elif not predicted and pays > zero:
            flag = f"  <-- VIOLATION: model says zero, bucket predominantly paid ({pays}/{pays + zero})"
        elif not predicted and pays:
            flag = f"  <-- outlier: {pays}/{pays + zero} paying (unexplained -- investigate before assuming lag)"
            outliers.append(f"gap={gap}: {pays}/{pays + zero}")
        if flag.startswith("  <-- VIOLATION"):
            violations.append(f"gap={gap} pays={pays} zero={zero}{flag}")
        lines.append(f"{gap:4d} {pays:6d} {zero:6d}  {verdict}{flag}")
    return lines, violations, outliers


def main() -> int:
    snapshot = (Path(sys.argv[1]) if len(sys.argv) > 1
                else Path.home() / ".cache/artifactsmmo/gamedata-api.artifactsmmo.com.json")
    db_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(default_learn_db_path())

    if not snapshot.exists():
        print(f"no game-data snapshot at {snapshot}", file=sys.stderr)
        return 2
    if not db_path.exists():
        print(f"no learning store at {db_path}", file=sys.stderr)
        return 2

    resources = _resource_catalog(snapshot)
    try:
        records = load_cycles(str(db_path))
    except EmptyCorpusError as exc:
        print(f"gather_xp_replay: {exc}", file=sys.stderr)
        return 1

    observations, excluded_not_gather, excluded_no_level, excluded_not_in_catalog = (
        _usable_observations(records, resources)
    )

    header = [
        "# GREY_SKILL_GAP corroboration report (gather)",
        f"store={db_path}",
        f"snapshot={snapshot}",
        f"cycle rows: {len(records)}",
        f"  excluded (not an ok GatherAction): {excluded_not_gather}",
        f"  excluded (skill_levels IS NULL or missing the gathered skill -- "
        f"skill_levels_json landed 2026-08-15, rows written before it are "
        f"excluded, not defaulted): {excluded_no_level}",
        f"  excluded (resource_code not in current catalog): {excluded_not_in_catalog}",
        f"usable observations: {len(observations)}",
        f"model: skill_xp_positive(content, skill) = content >= 1 and "
        f"skill < content + {GREY_SKILL_GAP}",
    ]

    if not observations:
        print("NO USABLE OBSERVATIONS: no cycle rows carry skill_levels_json.\n"
              "The column landed 2026-08-15; rows written before it are excluded\n"
              "rather than defaulted. Run the bot to accumulate observations.",
              file=sys.stderr)
        lines = [
            *header,
            "",
            "VERDICT: NO USABLE OBSERVATIONS. Every cycle row is excluded -- either it "
            "is not an ok GatherAction, or its skill_levels is None because "
            "skill_levels_json had not landed (or had not yet been written for a "
            "GatherAction row) when it was recorded. This is EXPECTED immediately "
            "after this migration and must NOT be read as confirming or refuting "
            "GREY_SKILL_GAP -- there is nothing to test yet. The 2026-08-15 "
            "trace-based finding (3231 gathers, no exception at the gap 10/11 "
            "boundary) remains the historical evidence; see skill_xp_positive.py's "
            "docstring. Re-run once GatherAction cycles have been recorded since "
            "skill_levels_json landed.",
        ]
        report = "\n".join(lines) + "\n"
        REPORT.write_text(report)
        print(report)
        return 1

    buckets: dict[int, list[int]] = collections.defaultdict(lambda: [0, 0])
    for gap, paid in observations:
        buckets[gap][0 if paid else 1] += 1

    gather_lines, violations, outliers = _render(buckets)
    lines = [*header, *gather_lines]
    lines.append("")
    lines.append("OUT-OF-BAND OUTLIERS (unexplained if any; see module docstring): " + (
        "; ".join(outliers) if outliers else "none"))
    lines.append("VIOLATIONS: " + (
        "; ".join(violations) if violations
        else f"none -- GREY_SKILL_GAP = {GREY_SKILL_GAP} holds on every gather bucket"))
    report = "\n".join(lines) + "\n"
    REPORT.write_text(report)
    print(report)
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())

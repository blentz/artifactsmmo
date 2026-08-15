"""Corroborate `cheapest_path_to_level`'s unit against the live learning store.

Server-axiom-signoff discipline, the same one `xp_formula_replay.py` applies to
the combat curve and `gather_xp_replay.py` to the gather band.

WHAT WENT WRONG. `cheapest_path_to_level` returns `total_cycles`, and every
consumer — the progression projection in the trace, the TUI's "Cyc left", and
the unified objective now being specified — reads it as a count of planner
ACTIONS. It was not. The per-kill divisor was `DEFAULT_FIGHT_CYCLES = 30.0`,
whose own docstring said "~30s server cooldown", i.e. a duration in SECONDS, and
the store override `action_cost` returns "median actual_cooldown_seconds". So a
projected "cycle" was really a second, and the number came out ~30x too large.

THE COMPARABLE OBSERVABLE IS COMBAT-LOOP CYCLES PER LEVEL — NOT TOTAL, AND (SINCE
2026-08-07) NOT FIGHT-CYCLES EITHER. The rule is that the observable must cover
exactly what the projection models, no more and no less, and what the projection
models has changed once already:

  * Until the unit fix it modelled a character that does nothing but fight, so
    FIGHT-cycles per level was the comparable figure. A trace's TOTAL cycles per
    level includes gathering, crafting and banking, which the projection never
    claimed to cover, so dividing by it flattered the projection by roughly the
    fraction of cycles actually spent fighting. Measured then: 789 total cycles
    per level against only 96 fight-cycles — and reporting the total-cycle ratio
    (9.8x) instead of the fight-cycle one (80.6x) understated the error by the
    same factor it was measuring, which is how the bug survived a first look.
  * `cheapest_path_to_level` now charges each kill the Rest its damage forces
    (`fight_loop_cost.cycles_per_kill`), because every character in the
    2026-08-07 traces ran ~1 Rest per Fight and the fight action was only ~51% of
    the loop. So the comparable observable is now FIGHT + REST cycles per level.

Comparing the new projection against the old fight-only observable would report a
clean ~2x error that is not an error at all — the mirror of the mistake above, and
the reason this doctrine is written down rather than assumed.

WHAT THIS SCRIPT CHECKS — AND WHAT IT LEAVES TO THE READER. For every character
in the corpus that gained at least one character level, it reports observed
combat-loop (fight+rest), fight-only and total cycles per level. It prints an
acceptance band of `[0.1x, 10x]` around the combat-loop figure, and THAT BAND IS
NEVER EVALUATED AGAINST ANYTHING: this script CALLS NO PROJECTION. It does not
import `cheapest_path_to_level`, does not compute a projected cycles-per-level,
and has no second number to compare. The comparison is a human one — run the
projection yourself, then check it against the printed band. Consequently
`main()` returns 0 whenever the corpus could be read and the characters gained
at least one level; the exit code says "the observable was measured", never "the
projection agreed". What would falsify the unit — a projected cycles-per-level
an order of magnitude away from the observed combat-loop figure — is a check
nothing here performs.

HONEST LIMITS, because this is corroboration and not proof:
  * The bot interleaves; observed fight-cycles per level still includes fights
    against whatever monster the arbiter chose, not the cheapest one the
    projection would have picked.
  * The projection lands ABOVE the observed figure and that is expected: it
    charges a full `max_xp` for every level and credits only kill xp, while the
    live character also banks task rewards and levels partly on cheaper early
    levels. Measured after the unit fix: 257 projected cycles/level against 124
    observed fight-cycles/level for the same character (R2D2), i.e. ~2x and
    conservative. Before the fix the same comparison was ~62x, which is a unit
    error rather than conservatism — that is the distinction this script exists
    to make.
  * Levels differ in xp cost; this aggregates across levels and characters.
  * A character that gained no level contributes nothing and is listed as such.

Output: formal/diff/level_cost_replay_report.txt + stdout.
Usage: uv run python formal/diff/level_cost_replay.py [db_path]
"""

import collections
import sys
from pathlib import Path

from store_records import CycleRecord, EmptyCorpusError, load_cycles

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT = REPO_ROOT / "formal" / "diff" / "level_cost_replay_report.txt"
DEFAULT_DB = Path.home() / ".cache" / "artifactsmmo" / "learning.db"

# A projected cycles-per-level outside this band of the observed fight-cycles
# figure is a unit error, not a modelling difference. Wide on purpose: the
# projection picks the cheapest monster while the live bot picks whatever the
# arbiter committed to, so a real gap of a few x is expected and fine.
LOW, HIGH = 0.1, 10.0


def _observed(records: list[CycleRecord]) -> dict[str, dict[str, int]]:
    """Aggregate fights/rests/cycles/levels per character from `cycles` rows.

    `records` is ordered by `(character, cycle_index)` (see `load_cycles`), so
    one character's rows are contiguous and this is a single linear pass, not
    a lookup. `fights`/`rests`/`cycles` read only the row's own `action_repr`
    and `outcome` — no pairing needed. `levels` (total level gained) is the
    SPAN of the row's own `level` column — the MAX observed level minus the
    MIN observed level, over ALL of that character's rows — never a per-row
    comparison against a neighboring row's level. `cycle_index` resets every
    session (one character in the live
    corpus spans 61 distinct sessions), so `load_cycles`'s `(character,
    cycle_index)` order interleaves sessions rather than following wall-clock
    time; "first/last encountered while iterating" is therefore NOT the same
    as "first/last chronologically" and would silently understate a level
    span whenever a later session's low cycle_index rows sort ahead of an
    earlier session's high ones. `min`/`max` sidesteps the ordering question
    entirely — AS LONG AS the level never falls, which is an OBSERVATION about
    this corpus and not a law of the server. `learning.xp_gain.xp_gained`'s
    docstring says "a level going down is not a thing the server does", but
    `monster_catalog.xp_per_kill`'s own note names a case where it appears to:
    a character NAME re-created, with the store still recording under it. That
    would not understate the span, it would OVERSTATE it, reporting two lives
    as one character's gain. The hazard is real and, today, unrealized:
    `formal/diff/trace_characterize.py` counts level regressions per character
    over rows ordered by `ts` and finds ZERO across all 49,263 rows (2026-08-15,
    5 characters). Re-check that line before trusting these figures — it is the
    only thing standing under this method. Given it, whatever order the rows
    arrive in, the lowest level seen IS the level held at the start of this
    corpus and the highest IS the level held at the end. That is the same
    shape of fix `xp_formula_replay.py` makes for `delta_xp`: read a value
    the row already has, don't recover it by differencing or by trusting an
    incidental iteration order to stand in for time."""
    per_char: dict[str, dict[str, int]] = collections.defaultdict(
        lambda: {"fights": 0, "rests": 0, "cycles": 0, "levels": 0})
    min_level: dict[str, int] = {}
    max_level: dict[str, int] = {}
    for rec in records:
        d = per_char[rec.character]
        d["cycles"] += 1
        action = rec.action_repr or ""
        if action.startswith("Fight(") and rec.outcome == "ok":
            d["fights"] += 1
        # Rest is the other half of the loop the projection now charges for.
        # Counted unconditionally rather than only after a fight: a Rest is a
        # cycle the combat loop spent however it was scheduled, and pairing it
        # to a preceding Fight would silently drop the ones the HP_CRITICAL
        # guard interleaves.
        if action == "Rest" and rec.outcome == "ok":
            d["rests"] += 1
        if rec.level is not None:
            min_level[rec.character] = min(min_level.get(rec.character, rec.level), rec.level)
            max_level[rec.character] = max(max_level.get(rec.character, rec.level), rec.level)
    for name, d in per_char.items():
        if name in min_level and name in max_level:
            d["levels"] = max_level[name] - min_level[name]
    return per_char


def main() -> int:
    db_path = sys.argv[1] if len(sys.argv) > 1 else str(DEFAULT_DB)
    try:
        records = load_cycles(db_path)
    except EmptyCorpusError as exc:
        print(f"level_cost_replay: {exc}", file=sys.stderr)
        return 1
    per_char = _observed(records)
    used = len(per_char)

    lines = ["# cheapest_path_to_level unit corroboration",
              f"db={db_path} rows={len(records)} characters={used}", ""]
    lines.append(f"{'char':8s} {'cycles':>8s} {'fights':>8s} {'rests':>7s} {'levels':>7s} "
                 f"{'loop/lvl':>9s} {'fight/lvl':>10s} {'total/lvl':>10s}")
    tf = tr = tl = tc = 0
    for name, d in sorted(per_char.items()):
        if not d["levels"]:
            lines.append(f"{name:8s} {d['cycles']:8d} {d['fights']:8d} {d['rests']:7d} "
                         f"{0:7d} {'n/a':>9s} {'n/a':>10s} {'n/a':>10s}")
            continue
        tf += d["fights"]
        tr += d["rests"]
        tl += d["levels"]
        tc += d["cycles"]
        lines.append(f"{name:8s} {d['cycles']:8d} {d['fights']:8d} {d['rests']:7d} "
                     f"{d['levels']:7d} {(d['fights'] + d['rests']) / d['levels']:9.0f} "
                     f"{d['fights'] / d['levels']:10.0f} {d['cycles'] / d['levels']:10.0f}")

    if not tl:
        lines.append("\nno character gained a level in this corpus — nothing to corroborate")
        REPORT.write_text("\n".join(lines) + "\n")
        print("\n".join(lines))
        return 2

    fight_per_level = tf / tl
    loop_per_level = (tf + tr) / tl
    total_per_level = tc / tl
    lines += [
        "",
        f"OBSERVED combat-loop (fight+rest) cycles per level: {loop_per_level:.0f}   <-- the comparable figure",
        f"OBSERVED fight-only cycles per character level    : {fight_per_level:.0f}   (the pre-2026-08-07 figure)",
        f"OBSERVED total      cycles per character level    : {total_per_level:.0f}   (includes non-combat work)",
        f"OBSERVED rests per fight                          : "
        f"{(tr / tf) if tf else 0:.2f}   (the term `cycles_per_kill` adds)",
        "",
        "A projection denominated in ACTIONS should land near the combat-loop",
        f"figure; the acceptance band is [{LOW:g}x, {HIGH:g}x] of {loop_per_level:.0f}, i.e. "
        f"[{loop_per_level * LOW:.0f}, {loop_per_level * HIGH:.0f}].",
        "THE BAND IS PRINTED, NOT EVALUATED: this script computes no projection and",
        "compares nothing to it. Exit 0 means the observable was measured, not that",
        "any projection agreed with it — run cheapest_path_to_level yourself and check.",
        "",
        "Pre-fix reference: the projection reported 7698 cycles/level for R2D2,",
        f"which is {7698 / fight_per_level:.0f}x the observed fight-cycles figure — the",
        "seconds-as-cycles error this constant's rename removed.",
    ]
    report = "\n".join(lines) + "\n"
    REPORT.write_text(report)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Corroborate `cheapest_path_to_level`'s unit against live trace data.

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

WHAT THIS SCRIPT CHECKS. For every character in the traces that gained at least
one character level, it reports observed fight-cycles per level. The projection
is sound in unit if a pure-fighting projection lands within a small factor of
that. What would falsify it: a projected cycles-per-level an order of magnitude
away from the observed fight-cycles-per-level.

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
Usage: uv run python formal/diff/level_cost_replay.py [TRACE_DIR]
"""

import collections
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT = REPO_ROOT / "formal" / "diff" / "level_cost_replay_report.txt"

# A projected cycles-per-level outside this band of the observed fight-cycles
# figure is a unit error, not a modelling difference. Wide on purpose: the
# projection picks the cheapest monster while the live bot picks whatever the
# arbiter committed to, so a real gap of a few x is expected and fine.
LOW, HIGH = 0.1, 10.0


def _observed(trace_dir: Path) -> tuple[dict[str, dict[str, int]], int]:
    per_char: dict[str, dict[str, int]] = collections.defaultdict(
        lambda: {"fights": 0, "rests": 0, "levels": 0, "cycles": 0})
    used = 0
    for path in sorted(trace_dir.glob("play-trace-*.jsonl")):
        try:
            records = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        except json.JSONDecodeError:
            continue
        if not records or "level" not in (records[0].get("state") or {}):
            continue
        used += 1
        name = path.name.split("play-trace-")[1].split("-2026")[0]
        d = per_char[name]
        d["cycles"] += len(records)
        for prev, cur in zip(records, records[1:], strict=False):
            if str(prev.get("action", "")).startswith("Fight(") and prev.get("outcome") == "ok":
                d["fights"] += 1
            # Rest is the other half of the loop the projection now charges for.
            # Counted unconditionally rather than only after a fight: a Rest is a
            # cycle the combat loop spent however it was scheduled, and pairing it
            # to a preceding Fight would silently drop the ones the HP_CRITICAL
            # guard interleaves.
            if prev.get("action") == "Rest" and prev.get("outcome") == "ok":
                d["rests"] += 1
            if cur["state"]["level"] > prev["state"]["level"]:
                d["levels"] += 1
    return per_char, used


def main() -> int:
    trace_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT
    per_char, used = _observed(trace_dir)
    if not used:
        print(f"no play-trace-*.jsonl under {trace_dir}", file=sys.stderr)
        return 2

    lines = ["# cheapest_path_to_level unit corroboration", f"traces={used}", ""]
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
        lines.append("\nno character gained a level in these traces — nothing to corroborate")
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

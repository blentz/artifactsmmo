"""Phase-C0c — corroborate the DOCUMENTED xp formula against live fight data.

Server-axiom-signoff discipline (like LIV-001's replay): the formula

    XP = round((monster_level/player_level * 20 + monster_hp * 0.04)
               * level_penalty * monster_multiplier * wisdom_bonus)
    level_penalty: 1.0 (diff <= 4), 0.7 (5 <= diff <= 9), 0.0 (diff >= 10)

(https://docs.artifactsmmo.com/concepts/stats_and_fights/#xp-formula) is
recomputed for every observed ok-fight in the learning store (`Cycle.level` is
the character's own level at that row, `Cycle.delta_xp` the row's own xp
delta — see `store_records.py`) using the fixture's monster level/hp, and
compared to the real xp delta.

KNOWN unobservables, reported as classes rather than asserted away:
* wisdom (gear-derived, not in the store row) — computed with wisdom = 0, so a
  uniform small POSITIVE real excess is the wisdom bonus signature;
* monster type (fixture lacks it) — computed with multiplier 1.0; elite/boss
  targets would show ~1.4x/2x excess;
* rollover fights (a multi-level jump `delta_xp` can't resolve) — skipped for
  delta comparison.

Output: formal/diff/xp_formula_replay_report.txt + stdout.
Usage: uv run python formal/diff/xp_formula_replay.py [db_path] [snapshot.json]
"""

import json
import sys
from collections import Counter
from pathlib import Path

from store_records import EmptyCorpusError, load_cycles

DEFAULT_DB = Path.home() / ".cache" / "artifactsmmo" / "learning.db"


def main() -> int:
    db_path = sys.argv[1] if len(sys.argv) > 1 else str(DEFAULT_DB)
    snap = (
        Path(sys.argv[2]) if len(sys.argv) > 2
        else Path(__file__).resolve().parent.parent / "sim" / "game_data_snapshot.json"
    )
    data = json.loads(snap.read_text())
    mlevel = data["monster_level"]
    mhp = data["monster_hp"]

    try:
        records = load_cycles(db_path)
    except EmptyCorpusError as exc:
        print(f"xp_formula_replay: {exc}", file=sys.stderr)
        return 1

    exact = 0
    off = Counter()  # (expected, real) mismatches
    unknown_monster = 0
    rollover = 0
    zero_band_fights = 0
    checked = 0

    for rec in records:
        action = rec.action_repr or ""
        if not action.startswith("Fight(") or rec.outcome != "ok":
            continue
        code = action[len("Fight("):-1]
        # `rec.delta_xp` is the row's OWN xp delta, already resolved across a
        # level-up by the store (see store_records.py's module docstring) —
        # never a difference this script computes against a neighboring row.
        # It is None only for a multi-level jump in one action (unresolvable;
        # never observed live) or a row the store could not attribute a level
        # to. Either way there is nothing to compare, so it joins the same
        # "rollover" bucket the old snapshot-diffing loader used for exactly
        # this kind of level-boundary uncertainty.
        if rec.level is None or rec.delta_xp is None:
            rollover += 1
            continue
        if code not in mlevel or code not in mhp:
            unknown_monster += 1
            continue
        ml, hp = mlevel[code], mhp[code]
        diff = rec.level - ml
        if diff >= 10:
            penalty = 0.0
            zero_band_fights += 1
        elif diff >= 5:
            penalty = 0.7
        else:
            penalty = 1.0
        expected = round((ml / rec.level * 20 + hp * 0.04) * penalty)
        real = rec.delta_xp
        checked += 1
        if expected == real:
            exact += 1
        else:
            off[(expected, real)] += 1

    out = []
    out.append(f"db={db_path} snapshot={snap} ({data.get('captured_at', '?')})")
    out.append(f"ok-fights checked={checked} rollovers-skipped={rollover} unknown-monster={unknown_monster}")
    out.append(f"EXACT formula matches (wisdom=0, multiplier=1.0): {exact}/{checked}")
    out.append(f"zero-band fights observed (level_penalty = 0): {zero_band_fights}")
    out.append(f"mismatch classes (expected, real) -> count, top 15: {off.most_common(15)}")
    out.append("")
    out.append("Uniform positive excess = wisdom bonus; ~1.4x/2x = elite/boss multiplier;")
    out.append("anything else contradicts the documented formula and needs escalation.")
    report = "\n".join(out)
    (Path(__file__).parent / "xp_formula_replay_report.txt").write_text(report + "\n")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Phase-C0c — corroborate the DOCUMENTED xp formula against live fight data.

Server-axiom-signoff discipline (like LIV-001's replay): the formula

    XP = round((monster_level/player_level * 20 + monster_hp * 0.04)
               * level_penalty * monster_multiplier * wisdom_bonus)
    level_penalty: 1.0 (diff <= 4), 0.7 (5 <= diff <= 9), 0.0 (diff >= 10)

(https://docs.artifactsmmo.com/concepts/stats_and_fights/#xp-formula) is
recomputed for every observed ok-fight in a live trace (trace `state` is the
POST-action snapshot — pre-state is the previous record's) using the fixture's
monster level/hp, and compared to the real xp delta.

KNOWN unobservables, reported as classes rather than asserted away:
* wisdom (gear-derived, not in the trace) — computed with wisdom = 0, so a
  uniform small POSITIVE real excess is the wisdom bonus signature;
* monster type (fixture lacks it) — computed with multiplier 1.0; elite/boss
  targets would show ~1.4x/2x excess;
* rollover fights (level-up resets xp) — skipped for delta comparison.

Output: formal/diff/xp_formula_replay_report.txt + stdout.
Usage: python diff/xp_formula_replay.py [trace.jsonl] [snapshot.json]
"""

import json
import sys
from collections import Counter
from pathlib import Path


def main() -> int:
    trace = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../play-trace-Robby.jsonl")
    snap = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("sim/game_data_snapshot.json")
    data = json.loads(snap.read_text())
    mlevel = data["monster_level"]
    mhp = data["monster_hp"]

    records = []
    with trace.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    exact = 0
    off = Counter()  # (expected, real) mismatches
    unknown_monster = 0
    rollover = 0
    zero_band_fights = 0
    checked = 0

    for prev, cur in zip(records, records[1:]):
        if cur.get("cycle") != prev.get("cycle", -2) + 1:
            continue
        if not (prev.get("state") and cur.get("state")):
            continue
        action = cur.get("action") or ""
        if not action.startswith("Fight(") or cur.get("outcome") != "ok":
            continue
        code = action[len("Fight("):-1]
        sa, sb = prev["state"], cur["state"]
        if sb["level"] > sa["level"]:
            rollover += 1
            continue
        if code not in mlevel or code not in mhp:
            unknown_monster += 1
            continue
        ml, hp = mlevel[code], mhp[code]
        diff = sa["level"] - ml
        if diff >= 10:
            penalty = 0.0
            zero_band_fights += 1
        elif diff >= 5:
            penalty = 0.7
        else:
            penalty = 1.0
        expected = round((ml / sa["level"] * 20 + hp * 0.04) * penalty)
        real = sb["xp"] - sa["xp"]
        checked += 1
        if expected == real:
            exact += 1
        else:
            off[(expected, real)] += 1

    out = []
    out.append(f"trace={trace} snapshot={snap} ({data.get('captured_at', '?')})")
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

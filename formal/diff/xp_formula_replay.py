"""Phase-C0c — corroborate the DOCUMENTED xp formula against live fight data.

Server-axiom-signoff discipline (like LIV-001's replay): the formula

    XP = round((monster_level/player_level * 20 + monster_hp * 0.04)
               * level_penalty * monster_multiplier * wisdom_bonus)
    level_penalty: 1.0 (diff <= 4), 0.7 (5 <= diff <= 10), 0.0 (diff >= 11)

(https://docs.artifactsmmo.com/concepts/stats_and_fights/#xp-formula) is
recomputed for every observed ok-fight in the learning store (`Cycle.level` is
the character's level at that row, `Cycle.delta_xp` the row's own xp delta —
see `store_records.py`) using the fixture's monster level/hp, and compared to
the real xp delta.

`Cycle.level` IS THE POST-ACTION LEVEL (`player.py` records `new_state.level`),
UNLIKE the adjacent `skill_levels_json`, which is deliberately PRE-action for
exactly the reason spelled out in `models.CycleBase`: the server's
`level_penalty` applies at the level held when the xp is PAID, so a fight that
levels the character is bucketed here one level too high. That is a real
imprecision and it is named rather than smoothed over. It does not move the
boundary: re-deriving under the pre-action convention shifts the diff-10
paying bucket from 372 to 369 and changes nothing else — every paying fight is
still at diff <= 10 and every zero-xp fight still at diff >= 11 — because a
level-up row's own `delta_xp` is negative and lands in `reset` (below)
regardless of which level labels it.

THE ZERO BOUNDARY IS MEASURED HERE, NOT ASSUMED FROM THE DOC. The doc prose is
loose about whether a gap of exactly 10 pays. This replay reports the pays/zero
split per `diff` bucket (`BOUNDARY` section) INDEPENDENTLY of the penalty it
applies, so the boundary the model uses is falsifiable by the same run that
uses it: a paying fight at or above `ZERO_BAND_DIFF`, or a zero-xp fight below
it, is a boundary violation rather than being folded into the mismatch classes.
A violation makes this script EXIT NON-ZERO, the same contract as its sibling
`gather_xp_replay.py` — a corroboration harness that can only ever print its
disagreement is not a check, and this one is the observation anchor for
`monster_catalog.ZERO_BAND_DIFF`, a production constant that was changed on its
evidence. When this script recovered per-fight xp by DIFFERENCING CONSECUTIVE
SNAPSHOTS it observed ZERO zero-band fights out of 399, so the "399/399" it was
cited for never touched the boundary at all.

KNOWN unobservables, reported as classes rather than asserted away:
* wisdom (gear-derived, not in the store row) — computed with wisdom = 0, so a
  uniform small POSITIVE real excess is the wisdom bonus signature;
* monster type (fixture lacks it) — computed with multiplier 1.0; elite/boss
  targets would show ~1.4x/2x excess;
* rollover fights (a multi-level jump `delta_xp` can't resolve) — skipped for
  delta comparison.

Output: formal/diff/xp_formula_replay_report.txt + stdout.
Exit: 0 when the boundary census is clean, 1 on any boundary violation (or an
empty corpus).
Usage: uv run python formal/diff/xp_formula_replay.py [db_path] [snapshot.json]
"""

import json
import sys
from collections import Counter
from pathlib import Path

from store_records import EmptyCorpusError, load_cycles

DEFAULT_DB = Path.home() / ".cache" / "artifactsmmo" / "learning.db"

# Restated here, NOT imported from `monster_catalog`: this replay measures the
# boundary the DOCS state against live data, and keeping the literal here is
# what makes the value under test the doc's rather than whatever production
# currently holds. That is all it buys. It is NOT the general rule this comment
# used to state — "a harness that reads the constant under test cannot falsify
# it" — which is false: the sibling `gather_xp_replay.py` DOES import
# `GREY_SKILL_GAP` and is still a sound model-vs-data differential, because what
# decides its verdict is each observation's measured pays/zero outcome, not the
# constant. Restating also does NOT catch production drifting away from this
# literal — only the differential and the mutation group do that.
ZERO_BAND_DIFF = 11
"""char_level - monster_level at which level_penalty reaches 0."""
PENALTY_DIFF = 5
"""char_level - monster_level at which level_penalty drops to 0.7."""


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
    pays: Counter[int] = Counter()   # diff -> fights with a POSITIVE own delta_xp
    zero: Counter[int] = Counter()   # diff -> fights with delta_xp == 0
    reset: Counter[int] = Counter()  # diff -> fights with delta_xp < 0 (see below)

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
        real = rec.delta_xp
        # BOUNDARY census, taken BEFORE the model is applied so the model
        # cannot launder it. A NEGATIVE own-delta is a level-reset row (the
        # character crossed a level, or the name was re-created and the store
        # kept recording under it); it carries no information about whether
        # the fight paid, so it is counted and excluded rather than being read
        # as a zero.
        if real > 0:
            pays[diff] += 1
        elif real == 0:
            zero[diff] += 1
        else:
            reset[diff] += 1
        if diff >= ZERO_BAND_DIFF:
            penalty = 0.0
            zero_band_fights += 1
        elif diff >= PENALTY_DIFF:
            penalty = 0.7
        else:
            penalty = 1.0
        expected = round((ml / rec.level * 20 + hp * 0.04) * penalty)
        checked += 1
        if expected == real:
            exact += 1
        else:
            off[(expected, real)] += 1

    pay_violations = sorted(d for d in pays if d >= ZERO_BAND_DIFF)
    zero_violations = sorted(d for d in zero if d < ZERO_BAND_DIFF)

    out = []
    out.append(f"db={db_path} snapshot={snap} ({data.get('captured_at', '?')})")
    out.append(f"ok-fights checked={checked} rollovers-skipped={rollover} unknown-monster={unknown_monster}")
    out.append(f"EXACT formula matches (wisdom=0, multiplier=1.0): {exact}/{checked}")
    out.append(f"zero-band fights observed (level_penalty = 0): {zero_band_fights}")
    out.append(f"mismatch classes (expected, real) -> count, top 15: {off.most_common(15)}")
    out.append("")
    out.append(f"## BOUNDARY census (model: level_penalty = 0 at diff >= {ZERO_BAND_DIFF})")
    out.append("'reset' = own delta_xp < 0, a level-crossing/character-reset row that")
    out.append("cannot say whether the fight paid; counted, excluded from the verdict.")
    out.append(f"{'diff':>5} {'pays':>7} {'zero':>7} {'reset':>7}  verdict")
    for d in sorted(set(pays) | set(zero) | set(reset)):
        verdict = "PAYS" if pays[d] else ("ZERO" if zero[d] else "-")
        out.append(f"{d:>5} {pays[d]:>7} {zero[d]:>7} {reset[d]:>7}  {verdict}")
    out.append(f"totals: pays={sum(pays.values())} zero={sum(zero.values())} reset={sum(reset.values())}")
    if pay_violations or zero_violations:
        out.append(f"BOUNDARY VIOLATIONS: paying diffs >= {ZERO_BAND_DIFF}: {pay_violations}; "
                   f"zero diffs < {ZERO_BAND_DIFF}: {zero_violations}")
    else:
        out.append(f"BOUNDARY VIOLATIONS: none — every paying fight is at diff < {ZERO_BAND_DIFF} "
                   f"and every zero-xp fight at diff >= {ZERO_BAND_DIFF}")
    out.append("")
    out.append("Uniform positive excess = wisdom bonus; ~1.4x/2x = elite/boss multiplier;")
    out.append("anything else contradicts the documented formula and needs escalation.")
    report = "\n".join(out)
    (Path(__file__).parent / "xp_formula_replay_report.txt").write_text(report + "\n")
    print(report)
    return 1 if (pay_violations or zero_violations) else 0


if __name__ == "__main__":
    raise SystemExit(main())

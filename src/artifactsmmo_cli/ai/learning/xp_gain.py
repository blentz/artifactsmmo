"""XP actually gained between two observations, across a level-up.

`delta = new_xp - prev_xp` is right only while the level holds. The server resets
xp into the new level on level-up, so the naive difference goes sharply NEGATIVE
exactly on the cycles that earned the most — and it was recorded that way for both
character xp (`Cycle.delta_xp`) and skill xp (`Cycle.delta_skill_xp_json`).

Measured on the live learning DB, 2026-08-07:
  * 30 of 22333 character rows negative — every one of them a level-up
  * 96 of 9047 skill-xp deltas negative
Rare, and yet ruinous to the aggregates, because the corrupted rows are large and
the honest ones are small. `GrindCharacterXP(red_slime)` for C3P0 read a mean of
2.52 char-xp/cycle where the true figure is ~21.6 — an 8.6x understatement from
0.13% of rows. Robby's `GrindCharacterXP(pig)` read -304.89.

Every consumer happened to guard against the negative (a `> 0` test, a priority
floor-clamp, a margin comparison), so this degraded the learned signal to
cold-start rather than driving anything absurd. That is luck, not design: the
number was wrong wherever it was read.
"""


def xp_gained(prev_level: int, prev_xp: int, prev_max_xp: int,
              new_level: int, new_xp: int) -> int | None:
    """XP earned between two observations, or None when it cannot be known.

    * SAME LEVEL — the plain difference, which is exact.
    * ONE LEVEL UP — what was left to fill the old level plus what has been banked
      into the new one: `(prev_max_xp - prev_xp) + new_xp`. Both terms are
      observed API readings, so this invents nothing.
    * ANYTHING ELSE — None. A jump of two or more levels would need the `max_xp`
      of every level crossed in between, and the API only ever reports the
      character's CURRENT level's threshold; there is no per-level xp curve to
      consult. A level going DOWN is not a thing the server does, so it likewise
      means the pair of observations cannot be trusted.

    None means UNKNOWN, and is deliberately not 0: a caller storing it records the
    absence rather than a fabricated measurement, which is the difference between
    "no xp was earned" and "we could not tell". Multi-level jumps have never been
    observed in 22333 recorded cycles — every one of the 29 level crossings was
    exactly one level — so this arm exists to stay honest at the edge, not because
    the edge is common.
    """
    if new_level == prev_level:
        return new_xp - prev_xp
    if new_level == prev_level + 1:
        return (prev_max_xp - prev_xp) + new_xp
    return None

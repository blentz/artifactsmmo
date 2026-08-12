"""Attribute forced-recovery cycles back to the goal whose fighting forced them.

WHY THIS IS NOT A DETAIL. A measured rate is XP divided by the cycles it took to
earn (S-023), and the arbiter files the Rests a grind forces under a DIFFERENT goal
-- `RestoreHP` -- because it preempts the grind to take them. Measured on 36455 live
cycles: `GrindCharacterXP(green_slime)` is 100.0% FightAction with 0% Rest, while
`RestoreHP` holds 5668 Rests and 637 healing consumables.

Left alone, the measured branch is XP per FIGHT and the predicted branch it is ranked
against is XP per LOOP ACTION, so every monster carrying observations beat every
monster without one by the whole loop factor -- about 2.4x at live per-kill costs.
This branch has had that defect once before at ~29x, when it divided by a cooldown in
seconds; an order of magnitude smaller is not a different bug, only a quieter one.

THE ATTRIBUTION RULE, and why it is the only one the data supports: a recovery cycle
belongs to the goal that ran immediately before it. The damage came from the fight
that preceded the Rest. Cycles carry a monotonic id, so the predecessor is already
recorded and no new column is needed. A run of consecutive recoveries walks back to
the last non-recovery goal, because a Rest that follows a Rest was forced by whatever
forced the first one.

WHAT IT DELIBERATELY DOES NOT DO: a recovery with no predecessor in the window is
DROPPED, not guessed at. It is the first row of a truncated stream, and inventing an
owner for it would put another goal's cost on this goal's rate -- which is the error
being fixed, pointed the other way.
"""

from artifactsmmo_cli.ai.learning.models import Cycle

RECOVERY_GOAL = "RestoreHP"


def attribute_forced_recovery(
    stream_newest_first: list[Cycle], goal_repr: str, window: int
) -> list[Cycle]:
    """The `goal_repr` cycles in `stream_newest_first`, plus the recovery cycles that
    goal's own fighting forced, newest first and capped at `window`.

    `stream_newest_first` is the character's raw cycle stream, NOT a filtered slice:
    attribution needs each recovery cycle's predecessor, and a filtered query has
    already thrown it away.
    """
    if goal_repr == RECOVERY_GOAL:
        # Asked about recovery itself: it owns its own cycles and borrows none.
        # Without this the rule would attribute every recovery to the goal before it
        # AND to recovery, double-counting the same cycle into two rates.
        return [c for c in stream_newest_first if c.selected_goal == RECOVERY_GOAL][:window]

    # Walk OLDEST first: "the goal that ran immediately before" is only meaningful in
    # the direction the cycles actually happened.
    owner: str | None = None
    owned: list[Cycle] = []
    for cycle in reversed(stream_newest_first):
        if cycle.selected_goal == RECOVERY_GOAL:
            # A recovery belongs to whatever last ran that was not itself recovery.
            # `owner is None` means the window began mid-recovery and the cause is
            # outside it, so there is nothing to attribute to.
            if owner == goal_repr:
                owned.append(cycle)
            continue
        owner = cycle.selected_goal
        if cycle.selected_goal == goal_repr:
            owned.append(cycle)
    owned.reverse()
    return owned[:window]

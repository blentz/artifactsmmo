"""Pure builder: turn a runtime skill-grind sub-plan into PlanTreeNode children
for the TUI plan tree and log.

A LevelSkill plan step is a planner abstraction — the concrete legs it expands
into (gather/craft/move) are re-derived and executed one-per-cycle by the player
(`_execute_level_skill`) and then discarded, so they never live in the strategy
prerequisite tree. This module renders the legs the player captured this cycle so
the TUI can show the whole action chain below the LevelSkill step instead of
stopping at it.

`legs[0]` is the leg the player executes this cycle. When it is itself a
LevelSkill (a cross-skill under-level dependency the player recursed into), it is
rendered as a wrapper carrying that inner grind's own legs (`nested_children`); a
LevelSkill leg elsewhere in the plan was not expanded this cycle and stays a
leaf."""

from collections.abc import Sequence

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.cycle_snapshot import PlanTreeNode


def grind_leg_nodes(
    skill: str,
    legs: Sequence[Action],
    nested_children: tuple[PlanTreeNode, ...] = (),
) -> tuple[PlanTreeNode, ...]:
    """PlanTreeNodes for one skill's grind legs, in plan order. A run of
    consecutive identical legs collapses to a single `repr ×N` node so a long
    stretch of the same gather/craft reads as one line. The first leg is the one
    running now (`current`); later groups are `unmet`. A leading LevelSkill leg
    becomes a `step` wrapper holding `nested_children`."""
    nodes: list[PlanTreeNode] = []
    i, n = 0, len(legs)
    while i < n:
        leg = legs[i]
        j = i + 1
        while j < n and repr(legs[j]) == repr(leg):
            j += 1
        count = j - i
        status = "current" if i == 0 else "unmet"
        if i == 0 and isinstance(leg, LevelSkill):
            nodes.append(PlanTreeNode(
                key=f"grind:{skill}:{leg.skill}", label=f"grind {leg.skill}",
                kind="step", status=status, children=nested_children))
        else:
            label = repr(leg) if count == 1 else f"{leg!r} ×{count}"
            nodes.append(PlanTreeNode(
                key=f"leg:{skill}:{i}:{leg!r}", label=label, kind="obtain",
                status=status))
        i = j
    return tuple(nodes)

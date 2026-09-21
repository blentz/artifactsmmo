"""Which branch of the root walk produced this cycle's root.

`cycles.selected_goal` records the STEP that ran, so it cannot tell an orphan
skill climb from a skill climb a gear target's crafting gate demanded — both
are `ReachSkillLevel(...)`. The root-group census needs that distinction, and
deriving it from a repr would re-encode a decision the walk already made.

The discriminator for the two skill cases is `RootWalk.blocked_target`, which
`decide_tree` copies onto `StrategyDecision.blocked_target`: it is set exactly
when the root is the crafting-skill gate of a named gear target, and is None
for an orphan. See `ai/decisions/root.py`'s `_orphan_skill_roots` for the
orphan rule and `RootWalk.blocked_target` for the gate one.
"""

from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal, ReachCharLevel, ReachSkillLevel

ROOT_GROUPS = frozenset({"guard", "trunk", "skill_gate", "orphan_skill", "gear", "none"})
"""Every label `root_group_of` can return. The census groups on this set, so a
label produced outside it would be counted nowhere."""


def root_group_of(interrupt: str | None, chosen_root: MetaGoal | None,
                  blocked_target: str | None) -> str:
    """The group that produced `chosen_root`, or `guard`/`none`.

    `interrupt` is checked FIRST because a guard preempts the walk: a root may
    have been resolved and then not run, and attributing the cycle to that root
    would credit the walk with a choice the guard overrode.
    """
    if interrupt is not None:
        return "guard"
    if chosen_root is None:
        return "none"
    if isinstance(chosen_root, ReachCharLevel):
        return "trunk"
    if isinstance(chosen_root, ReachSkillLevel):
        return "skill_gate" if blocked_target is not None else "orphan_skill"
    return "gear"

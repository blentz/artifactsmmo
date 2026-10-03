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

TWO THINGS THIS MODULE DELIBERATELY DOES NOT READ, because reading them would
make the census measure the wrong population:

* `StrategyDecision.interrupt`. It LOOKS like the guard field and the first
  version of this classifier used it, but `progression_tree.decide_tree` — the
  only production producer of a `StrategyDecision` — hardcodes it to None and
  says so in its own comment. Guards fire through the engine-independent
  arbiter ladder (`active_guards` -> `_build_candidates` -> `select_pure`), so
  the guard fact comes from `StrategyArbiter.last_selected_guard`, which is the
  arbiter reporting what it actually chose.
`chosen_root` is the walk's OWN pick. Until Phase 3-2 servability promotion
could move it afterwards (live 2026-07-27: 9 of 15 cycles logged
`ReachCharLevel` when the walk had chosen GEAR), and this classifier grouped on
the displaced pick instead. The walk now lets only a servable gear target head
it, so no promotion follows and `chosen_root` is the pick to group on;
`blocked_target` comes from the same `RootResolution`, so the gate and the root
it gates are the same walk's.
"""

from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal, ReachCharLevel, ReachSkillLevel

ROOT_GROUPS = frozenset({"guard", "trunk", "skill_gate", "orphan_skill", "gear", "none"})
"""Every label `root_group_of` can return. The census groups on this set, so a
label produced outside it would be counted nowhere."""


def root_group_of(guard: str | None, chosen_root: MetaGoal | None,
                  blocked_target: str | None) -> str:
    """The group that produced this cycle's root, or `guard`/`none`.

    `guard` is the repr of the guard-band goal the arbiter SELECTED this cycle
    (`StrategyArbiter.last_selected_guard`), not a guard that merely fired: a
    fired-but-unselected guard did not spend the cycle. It is checked FIRST
    because a selected guard preempts the walk — a root may have been resolved
    and then not run, and attributing the cycle to that root would credit the
    walk with a choice the guard overrode.
    """
    if guard is not None:
        return "guard"
    if chosen_root is None:
        return "none"
    if isinstance(chosen_root, ReachCharLevel):
        return "trunk"
    if isinstance(chosen_root, ReachSkillLevel):
        return "skill_gate" if blocked_target is not None else "orphan_skill"
    return "gear"

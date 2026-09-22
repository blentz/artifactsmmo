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
* `chosen_root` ALONE. Servability promotion can walk the tree's own pick to
  the trunk sitting at fallback index 0 (live 2026-07-27: 9 of 15 cycles logged
  `ReachCharLevel` when the tree had chosen GEAR every time), and this census
  exists precisely to measure whether the trunk-first ordering costs anything.
  Counting a promoted cycle as the trunk winning states the opposite of what
  happened, so the classifier groups on the walk's OWN pick — `promoted_from`
  when promotion displaced it, `chosen_root` otherwise. That also repairs the
  `blocked_target` pairing for free: `decide_tree` publishes `blocked_target`
  from the same `RootResolution` that produced `promoted_from`, so the gate and
  the root it gates are once again the same walk's.

The root that actually EXECUTED stays recorded separately, in
`cycles.root_repr`, so "the walk chose the trunk" (`root_group='trunk'`) and
"the walk chose gear and promotion moved it to the trunk"
(`root_group='gear'`, `root_repr='ReachCharLevel(...)'`) are distinguishable in
the store.
"""

from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal, ReachCharLevel, ReachSkillLevel

ROOT_GROUPS = frozenset({"guard", "trunk", "skill_gate", "orphan_skill", "gear", "none"})
"""Every label `root_group_of` can return. The census groups on this set, so a
label produced outside it would be counted nowhere."""


def root_group_of(guard: str | None, chosen_root: MetaGoal | None,
                  blocked_target: str | None,
                  promoted_from: MetaGoal | None) -> str:
    """The group that produced this cycle's root, or `guard`/`none`.

    `guard` is the repr of the guard-band goal the arbiter SELECTED this cycle
    (`StrategyArbiter.last_selected_guard`), not a guard that merely fired: a
    fired-but-unselected guard did not spend the cycle. It is checked FIRST
    because a selected guard preempts the walk — a root may have been resolved
    and then not run, and attributing the cycle to that root would credit the
    walk with a choice the guard overrode.

    `promoted_from` is the tree's own pick when servability promotion displaced
    it, None otherwise. The rule "group the walk's own pick" lives HERE rather
    than at the call site so there is one implementation of it; see the module
    docstring for why the final `chosen_root` is the wrong thing to group on.
    """
    if guard is not None:
        return "guard"
    walk_root = promoted_from if promoted_from is not None else chosen_root
    if walk_root is None:
        return "none"
    if isinstance(walk_root, ReachCharLevel):
        return "trunk"
    if isinstance(walk_root, ReachSkillLevel):
        return "skill_gate" if blocked_target is not None else "orphan_skill"
    return "gear"

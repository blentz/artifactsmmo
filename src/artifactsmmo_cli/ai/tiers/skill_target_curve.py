"""Recipe-aware skill target curve: the crafting-skill level to hold at the
current character level so gear recipes unlock just-in-time (no catch-up freeze).

`skill_curve_target_pure` is a PURE CORE (extraction subset): for ONE skill, the
max craft_level over gear-relevant items whose item_level <= char_level +
lookahead, clamped to [1, max_skill_level]; 0 means "no qualifying recipe, do not
schedule this skill". Returns Int (the proven contract; mirrors EquipmentScoring).

Progression-tree Phase 4b Task 5: the impure wrapper `skill_target_curve` and
its only caller (`CharacterObjective.near_term_skill_targets`) were retired as
dead code post-flip. The tree-level skill-grind dispatch that later consumed
this module's `SkillItem` view (`next_tier_cap_pure` + the skill-step dispatch)
was itself retired in epic P3 — skill grinds now run planner-natively through
the `LevelSkill` action. `skill_curve_target_pure` (this module's pure core)
remains proven + differentially tested independent of any caller
(formal/diff/test_skill_target_curve_diff.py imports only `SkillItem` and
`skill_curve_target_pure`); it and `next_tier_cap` are retained as proven cores
pending a future extraction-bridge cleanup."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillItem:
    """Plain-data view of one craftable item for the curve: which skill crafts
    it, at what craft level, the item's own level, and whether it is
    gear-relevant (equippable or a tool)."""
    craft_skill: str
    craft_level: int
    item_level: int
    gear_relevant: bool


def skill_curve_target_pure(
    skill: str,
    char_level: int,
    items: list[SkillItem],
    lookahead: int,
    max_skill_level: int,
) -> int:
    """PURE CORE. Target craft-skill level to hold at `char_level` for `skill`:
    the max craft_level over gear-relevant `items` of this skill whose
    item_level <= char_level + lookahead, clamped to [1, max_skill_level].
    Returns 0 when no qualifying recipe exists (skill not scheduled)."""
    # Annotated so the mechanical Lean extraction pins `best : Int` at the seed:
    # the value first flows into the polymorphic `decide (best <= 0)` clamp,
    # which leaves the type unconstrained (and the kernel stuck) if the emitted
    # `let best := 0` carries no annotation. (extract_lean.py AnnAssign branch.)
    best: int = 0
    for it in items:
        if (it.gear_relevant and it.craft_skill == skill
                and it.item_level <= char_level + lookahead
                and it.craft_level > best):
            best = it.craft_level
    if best <= 0:
        return 0
    if best > max_skill_level:
        return max_skill_level
    return best

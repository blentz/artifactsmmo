"""Recipe-aware skill target curve: the crafting-skill level to hold at the
current character level so gear recipes unlock just-in-time (no catch-up freeze).

`skill_curve_target_pure` is a PURE CORE (extraction subset): for ONE skill, the
max craft_level over gear-relevant items whose item_level <= char_level +
lookahead, clamped to [1, max_skill_level]; 0 means "no qualifying recipe, do not
schedule this skill". Returns Int (the proven contract; mirrors EquipmentScoring).
The impure wrapper `skill_target_curve` hoists the item tuples from GameData.
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


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


SKILL_CURVE_LOOKAHEAD = 3
"""Levels of recipe lookahead: hold each skill high enough to craft gear up to
char_level + 3, so the next tier is ready just before it is wanted."""


def skill_target_curve(
    char_level: int, state: WorldState, game_data: GameData,
) -> dict[str, int]:
    """Impure wrapper: {craft_skill: curve_target} over all crafting skills with
    a qualifying gear-relevant recipe. Hoists SkillItem tuples from game_data."""
    items: list[SkillItem] = []
    for code, stats in game_data.all_item_stats.items():
        if not stats.crafting_skill:
            continue
        gear_relevant = (stats.type_ in ITEM_TYPE_TO_SLOTS
                         or stats.subtype == "tool")
        items.append(SkillItem(stats.crafting_skill, stats.crafting_level,
                               stats.level, gear_relevant))
    max_level = game_data.max_skill_level
    skills = {it.craft_skill for it in items}
    out: dict[str, int] = {}
    for skill in skills:
        target = skill_curve_target_pure(
            skill, char_level, items, SKILL_CURVE_LOOKAHEAD, max_level)
        if target > 0:
            out[skill] = target
    return out

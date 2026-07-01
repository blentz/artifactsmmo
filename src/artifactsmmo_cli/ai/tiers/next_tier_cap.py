"""Next-tier skill-grind dampener pure cores.

`next_tier_cap_pure` is a PURE CORE (extraction subset): for ONE gear-crafting
skill, the max craft_level over gear-relevant items whose item_level falls in the
10-level band ONE tier above `char_level`, clamped to [1, max_skill_level]; 0 means
"no next-tier gear for this skill" (never dampened). `next_tier_dampened_pure` is
the boolean gate: the skill can already craft all next-tier gear. Both mirror
`skill_curve_target_pure` (see skill_target_curve.py) and are extracted + proven.
The band rolls up with char_level, which is how the gate self-releases as the
character advances (a data property, not a claimed theorem — see the design spec).
"""

from artifactsmmo_cli.ai.tiers.skill_target_curve import SkillItem


def next_tier_cap_pure(
    skill: str,
    char_level: int,
    items: list[SkillItem],
    max_skill_level: int,
) -> int:
    """PURE CORE. Max craft_level over gear-relevant `items` of `skill` whose
    item_level is in the next tier band [floor, floor+9], floor =
    ((char_level // 10) + 1) * 10, clamped to [1, max_skill_level]. 0 when the band
    holds no qualifying gear item."""
    # Annotated so the mechanical Lean extraction pins `best : Int` at the seed
    # (mirrors skill_curve_target_pure).
    floor: int = ((char_level // 10) + 1) * 10
    best: int = 0
    for it in items:
        if (it.gear_relevant and it.craft_skill == skill
                and floor <= it.item_level and it.item_level <= floor + 9
                and it.craft_level > best):
            best = it.craft_level
    if best <= 0:
        return 0
    if best > max_skill_level:
        return max_skill_level
    return best


def next_tier_dampened_pure(current_skill: int, next_tier_cap: int) -> bool:
    """PURE CORE. True when the skill already crafts ALL next-tier gear, i.e. there
    is next-tier gear (`next_tier_cap > 0`) and the skill covers its hardest recipe
    (`current_skill >= next_tier_cap`)."""
    return next_tier_cap > 0 and current_skill >= next_tier_cap

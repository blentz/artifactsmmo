"""How many heal potions to keep on hand — the ONE target the CRAFT_POTIONS guard
and CraftPotionsGoal both size themselves from.

They used to disagree. The guard fired on the bare level ramp
(`potion_baseline_pure`) while the goal targeted
`min(max(level_baseline, monster_demand), stack)`, so the guard could fire with
nothing for the goal to do. Worse, `max(level_baseline, ...)` made the ramp a
FLOOR: a level-45 bot pursued 100 potions whether or not it ever drank one, and
gather-crafting those potions is never a time saving over resting (resting always
refills to full and costs `max(3, ceil(missing%))` seconds -- see
`actions/cost_core.rest_cost_pure`).

The justification for stocking potions is NOT avoiding a slow Rest. It is that
you CANNOT REST MID-FIGHT: utility-slot potions are consumed during combat, so
their value is surviving a fight you would otherwise lose. Hence projected combat
consumption drives the target, and the level ramp only CAPS how far ahead the bot
is willing to speculate.
"""

from artifactsmmo_cli.ai.thresholds import (
    MARGINAL_FIGHT_HP_DEN,
    MARGINAL_FIGHT_HP_NUM,
    POTION_LEAD_FIGHTS,
)


def fight_is_marginal_pure(expected_damage: int, max_hp: int) -> bool:
    """True when one fight would push the character into the band where the
    codebase already says it should not be fighting.

    "Comfortably winnable" is the negation: the bot ends the fight still above
    `MARGINAL_FIGHT_HP_FRACTION` of max HP, so it never had to drink anything and
    can rest the damage off for free afterwards.

    The fraction reuses the EXISTING fight-HP floor (`actions/combat`'s
    `_MIN_FIGHT_HP_FRACTION`, "don't start a fight below this - rest/heal first")
    rather than introducing a second, unjustified comfort threshold.
    """
    if max_hp <= 0 or expected_damage <= 0:
        return False
    remaining = max_hp - expected_damage
    # Integer form of `remaining / max_hp <= MARGINAL_FIGHT_HP_FRACTION`, kept
    # float-free so the decision path stays exact (project_mechanical_extraction).
    return remaining * MARGINAL_FIGHT_HP_DEN <= max_hp * MARGINAL_FIGHT_HP_NUM


def potion_stock_target_pure(hp_need_per_fight: int, potion_restore: int,
                             level_baseline: int) -> int:
    """Potions to keep on hand: projected consumption over the lead-time window,
    capped by the level ramp.

    `hp_need_per_fight` is in-combat healing actually needed per fight -- learned
    from history where available, else 0 for a comfortably-winnable monster (a
    fight the bot wins without drinking anything needs no stock). It is NOT raw
    damage taken: resting mops that up for free between fights.

    Stocking is deliberately SPECULATIVE across `POTION_LEAD_FIGHTS` fights rather
    than just the next one, because crafting a potion has lead time and a bot that
    only starts brewing once it is already marginal starts too late.

    Ceils, because a partial potion is no potion. Returns 0 when nothing is needed
    or nothing can help (`potion_restore <= 0`), which is what stops the guard
    firing on a bot that is simply idle at full HP.
    """
    if hp_need_per_fight <= 0 or potion_restore <= 0 or level_baseline <= 0:
        return 0
    projected_hp = hp_need_per_fight * POTION_LEAD_FIGHTS
    demand = -(-projected_hp // potion_restore)      # ceil(projected_hp / restore)
    return min(demand, level_baseline)

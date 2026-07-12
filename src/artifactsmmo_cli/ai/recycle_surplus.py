# recycle_surplus

"""Detect surplus craftable equipment the bot can recycle to recover materials.

A code is RECYCLABLE SURPLUS when the character holds it ABOVE its useful keep-cap
and recycling it is actually possible and worthwhile:
  * it is craftable EQUIPMENT (has a crafting recipe + crafting skill, and an
    equippable type in `ITEM_TYPE_TO_SLOTS`);
  * the crafting skill is at the recipe's level (the server gates recycling on
    the crafting skill, like crafting — HTTP 493 otherwise);
  * a workshop for that skill is known (recycling happens at the workshop);
  * it is NOT a committed objective code (`protected_codes` = the objective's
    target_gear/target_tools — never recycle the gear you are building);
  * it is held above `useful_quantity_cap` (the swap-pool floor of 1 for
    equippable craftables — keep one spare for the optimizer; the cap already
    keeps >=1 for an equipped code, and the WORN copy is not in the inventory
    count at all).

Recycling recovers ~half the crafting materials, which then flow to the bank or
the gear chain — far better than the `DiscardOverstock` DELETE that destroys them.
Proactive (idle-time) recovery is the only feasible point: under space pressure
the recovered materials have nowhere to go (see the design spec / HTTP 497).

Pure: reads state/game_data only, no I/O.
"""

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.bank_selection import _best_gathering_tools
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_caps import useful_quantity_cap
from artifactsmmo_cli.ai.world_state import WorldState

URGENCY_STEP = 5
"""Surplus copies per +1x urgency: every 5 spares of the piling grind item add
one urgency multiple (a ~40-copy hoard is 8x more urgent than <5)."""


def recycle_urgency_pure(max_surplus: int) -> int:
    """Urgency multiplier for the largest surplus pile: ``max(1, ceil(q/5))``.

    <=5 surplus is baseline (1x); each further 5 copies add 1x, so the pile the
    skill grind keeps feeding becomes progressively harder to ignore instead of
    growing unbounded in the starved discretionary tier."""
    return max(1, -(-max_surplus // URGENCY_STEP))


def recycle_urgency(surplus: dict[str, int]) -> int:
    """Urgency of a `recyclable_surplus` map: driven by its LARGEST pile (the
    current grind item is by construction the code that piles up)."""
    return recycle_urgency_pure(max(surplus.values(), default=0))


def recyclable_surplus(
    state: WorldState, game_data: GameData, protected_codes: frozenset[str],
    gear_keep: dict[str, int] | None = None,
) -> dict[str, int]:
    """Map each recyclable-surplus code to the quantity held above its useful cap.

    `gear_keep` (active-profile gear-demand keep map, spec
    2026-06-28-gear-loadout-profiles) is forwarded to `useful_quantity_cap`: in
    profiles-aware mode the equippable cap is the active-profile demand (+1
    in-flight spare) rather than the blanket 1, so equippable gear in no active
    profile and not in-flight has cap 0 and its full held count is reclaimable.
    `None` keeps the legacy blanket-1 cap."""
    # Working kit: the best owned tool per gathering skill is equipment the
    # gather re-arm is ABOUT to wear (WithdrawTools ferries it a cycle before
    # OptimizeLoadout equips it) — recycling must never race the equip and eat
    # it (live probe 2026-07-05: copper_pickaxe surfaced as surplus 1). Kit
    # membership is a cap FLOOR of 1 (applied below), NOT a code skip: it
    # protects the TOOL, not a HOARD of it. A blanket skip shielded every copy,
    # and the gathering tools are also weaponcrafting GRIND RUNGS, so the skill
    # grind fed the pile forever — live Robby 2026-07-12 carried 18 copper_axe +
    # 7 fishing_net (both best-in-skill kit) in a 17/20-slot bag while
    # recyclable_surplus reported neither. Same blanket-vs-cap flaw the
    # equipped-code skip already fixed (copper_helmet x41).
    kit = _best_gathering_tools(state, game_data)
    out: dict[str, int] = {}
    for code, qty in state.inventory.items():
        # No blanket equipped-code skip: `qty` counts only BAG copies (the worn
        # copy lives in equipment, not inventory) and `useful_quantity_cap`
        # already keeps >=1 for an equipped code — the old skip shielded every
        # spare of a worn code from recycling (copper_helmet x25 hoard,
        # trace 2026-07-05).
        if qty <= 0 or code in protected_codes:
            continue
        stats = game_data.item_stats(code)
        if stats is None or not stats.crafting_skill:
            continue
        if not ITEM_TYPE_TO_SLOTS.get(stats.type_):
            continue  # not equippable → not in scope (raw/intermediate/consumable)
        if game_data.crafting_recipe(code) is None:
            continue
        if state.skills.get(stats.crafting_skill, 1) < stats.crafting_level:
            continue  # skill gate: cannot recycle
        if game_data.workshop_location(stats.crafting_skill) is None:
            continue  # no workshop known → cannot recycle
        cap = useful_quantity_cap(code, state, game_data, gear_keep=gear_keep)
        if code in kit:
            # Keep the ONE working tool the gather re-arm is about to equip; its
            # spares are scrap like any other over-cap gear.
            cap = max(cap, 1)
        if qty > cap:
            out[code] = qty - cap
    return out

# recycle_surplus

"""Detect surplus craftable equipment the bot can recycle to recover materials.

A code is RECYCLABLE SURPLUS when the keep authority (`ai/inventory_keep.py`)
licenses its disposal AND recycling it is actually possible:
  * RECYCLABILITY (a property of the ITEM and the WORLD, not of protection):
      - it is craftable EQUIPMENT (has a crafting recipe + crafting skill, and an
        equippable type in `ITEM_TYPE_TO_SLOTS`);
      - the crafting skill is at the recipe's level (the server gates recycling
        on the crafting skill, like crafting — HTTP 493 otherwise);
      - a workshop for that skill is known (recycling happens at the workshop);
  * DISPOSABILITY: the copies the keep authority licenses (see below).

PROTECTION IS THE AUTHORITY'S, NOT OURS (item-protection-authority epic, Task 7).
This module used to mix THREE mechanisms — a `protected_codes` frozenset, a `kit`
code-set, and `useful_quantity_cap` — and two of the three were code-SETS, whose
type can only say "keep ALL copies". That is the bug class the authority exists to
kill: a `target_tools` blanket hid all 18 `copper_axe` from every recycle path
while the weaponcrafting grind kept manufacturing more.

The licensed quantity is `min(bankable, destroyable)` — the copies that are
surplus to BOTH caps, because a recycle is a BAG-side DESTRUCTION and therefore
answers to both:
  * `destroyable` (bag+bank beyond `keep_owned`) — destruction is IRREVERSIBLE,
    so the OWNED cap is the one that licenses it. Bank copies count toward
    satisfying it: they are still owned.
  * `bankable` (bag beyond `keep_in_bag`) — the copies that may leave the BAG at
    all. Destroying a copy the bag must keep is strictly WORSE than banking it,
    and the in-bag ladder is where `KeepReason.WORKING_KIT` lives: it is what
    keeps the ONE tool the gather re-arm is about to equip (`WithdrawTools`
    ferries it a cycle before `OptimizeLoadout` wears it — live probe 2026-07-05:
    `copper_pickaxe` surfaced as surplus 1 and recycling would have raced the
    equip). `bankable` also bounds the result by what is physically in the bag,
    which `destroyable` alone does not: with 1 axe in the bag and 17 in the bank,
    `destroyable` is 17 but only the WORKING copy is reachable — and it is the one
    copy that must not be eaten.

That is the whole of the working-kit rule: a cap of ONE (the tool), never a
blanket over the CODE (the hoard). The equipped copy is likewise kept by ONE
(`KeepReason.EQUIPPED`) — the worn copy is not in the inventory count at all, so
its bag spares are scrap like any other over-cap gear (`copper_helmet` x41).

Recycling recovers ~half the crafting materials, which then flow to the bank or
the gear chain — far better than the `DiscardOverstock` DELETE that destroys them.
Proactive (idle-time) recovery is the only feasible point: under space pressure
the recovered materials have nowhere to go (see the design spec / HTTP 497).

Pure: reads state/game_data/ctx only, no I/O.
"""

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_keep import bankable, destroyable
from artifactsmmo_cli.ai.selection_context import SelectionContext
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


def recyclable_surplus(state: WorldState, game_data: GameData,
                       ctx: SelectionContext) -> dict[str, int]:
    """Map each recyclable-surplus code to the number of BAG copies the keep
    authority licenses for destruction.

    `ctx` is the per-cycle `SelectionContext` the keep authority reads
    (`gear_keep` = the active-profile gear demand, `step_profile` = the active
    goal's material needs). It REPLACES the old `protected_codes` frozenset and
    `gear_keep` map — see the module docstring."""
    out: dict[str, int] = {}
    for code, qty in state.inventory.items():
        if qty <= 0:
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
        surplus = min(bankable(code, state, game_data, ctx),
                      destroyable(code, state, game_data, ctx))
        if surplus > 0:
            out[code] = surplus
    return out

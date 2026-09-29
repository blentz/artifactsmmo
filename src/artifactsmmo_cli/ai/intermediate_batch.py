"""Rebatch an intermediate CraftAction or a closure GatherAction to its
inventory-bounded closure demand."""

import dataclasses
from collections.abc import Mapping

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gather_apply_core import gather_batch_size_pure
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.task_batch import craft_batch_size_pure
from artifactsmmo_cli.ai.world_state import WorldState


def size_intermediate_craft(action: CraftAction, chain: Mapping[str, int],
                            state: WorldState, game_data: GameData) -> CraftAction:
    """Return `action` with its quantity set to the inventory-bounded batch for
    its net closure demand (chain demand minus what is already held in
    inventory+bank). Unchanged when the sized quantity already matches.

    `craft_batch_size_pure` bounds a batch in UNITS of the item (its `demand`
    is units); `CraftAction.quantity` is RUNS, each yielding
    `craft_yield(code)` units. Passing the units through as runs made a yield-2
    craft twice the batch: `Craft(earth_boost_potion×6)` for 6 potions, 12
    made (2026-09-29). Identical for yield 1.

    The rounding follows the bound that won: a batch bounded by DEMAND rounds
    up (the runs that cover it), one bounded by SPACE or the cap rounds down
    (the runs that fit), never below one run."""
    held = state.inventory.get(action.code, 0) + (state.bank_items or {}).get(action.code, 0)
    demand = max(0, chain.get(action.code, 0) - held)
    units = craft_batch_size_pure(action.code, demand, state.inventory,
                                  state.inventory_free, game_data.crafting_recipes,
                                  game_data.resource_drops, game_data.craft_yields)
    craft_yield = max(1, game_data.craft_yield(action.code))
    qty = -(-units // craft_yield) if units >= demand else max(1, units // craft_yield)
    return action if action.quantity == qty else dataclasses.replace(action, quantity=qty)


def size_closure_gather(action: GatherAction, chain: Mapping[str, int],
                        state: WorldState, game_data: GameData) -> GatherAction:
    """Return `action` with its quantity set to the inventory-bounded batch for
    its DROP ITEM's net closure demand (chain demand minus inventory+bank
    holdings), FLOORED AT 1 while any demand remains. Unchanged when the sized
    quantity already matches.

    The twin of `size_intermediate_craft`, and sized by the goal for the same
    reason: the action factory has no demand context, so a factory-set quantity
    could only ever be a guess.

    Keyed on the drop item, not the resource code — a `drop_item_override`
    gather targets a secondary drop, and it is that item the closure demands.

    THE FLOOR IS THE WHOLE POINT, and it is load-bearing in both directions.

    Why the size must never reach 0 while demand remains: `planner.py:177`
    builds the action pool ONCE, before the search loop, so a gather sized to 0
    here is absent from EVERY node — including the nodes reached after a
    `DepositAll` has freed the room. And it cannot recover, because
    `is_applicable` ends with `effective_quantity(...) >= 1`, which re-derives
    0 from `self.quantity` at every node. `gather_batch_size_pure` returns 0 on
    THREE conditions — zero demand, `qty_free == 0`, and a NEW drop code with no
    free slot — and only the first is a property of the GOAL; the other two are
    properties of the CURRENT state, which the search exists to change. Without
    the floor, `DepositAll → Gather` was unplannable from a full bag: the
    slot-exhaustion livelock class, reintroduced through a sizing guard.

    Why the room bound must nevertheless stay: `cost` scales every term by
    `self.quantity` (`gathering.py:44-51`), while `apply` mints
    `effective_quantity`. Sizing to the raw deficit therefore prices an edge for
    work it does not do the moment the bag is smaller than the demand — measured
    on the `feather_coat` from-scratch fixture, `Gather(ash_tree×30)` cost 420.0
    to mint 10, and the A* search went from 31,846 nodes to a 354,254-node
    timeout. Clamping to room keeps the edge's price and its effect agreeing.

    So: room-bounded for pricing, floored at 1 for reachability. At a full bag
    the edge survives as a 1-unit gather that `is_applicable` correctly refuses
    until a deposit frees space, and the next cycle's decide state re-sizes it
    to a real batch.
    """
    drop = action.drop_item(game_data)
    held = state.inventory.get(drop, 0) + (state.bank_items or {}).get(drop, 0)
    demand = max(0, chain.get(drop, 0) - held)
    # No demand -> a genuine no-op edge, which the callers' `>= 1` guard drops.
    # Any demand -> at least 1, even with no room right now.
    qty = 0 if demand == 0 else max(
        1, gather_batch_size_pure(action.inv(state), demand, drop))
    return action if action.quantity == qty else dataclasses.replace(action, quantity=qty)

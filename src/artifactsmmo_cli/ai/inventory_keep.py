"""The single keep authority: how many copies of an item must stay.

Protection used to be expressed as `frozenset[str]` code-sets, which can only
mean "keep ALL copies" — four hoard bugs came from that one type (18 copper_axe
shielded because the axe was the best woodcutting tool). Here every protection
reason contributes a QUANTITY, so a blanket is inexpressible; `KEEP_ALL` is the
one explicit escape hatch and it is used once (currency).

Two caps, because "protection" conflated two questions:
  * keep_in_bag  — copies that must stay in the BAG (banking is REVERSIBLE)
  * keep_owned   — copies that must remain OWNED, bag+bank (destroying is NOT)

INERT (Task 1 of the item-protection-authority epic): nothing in this module
is wired into a consumer yet — `bank_selection._keep_codes`,
`recycle_surplus`'s `protected_codes`/`kit`, and `guards._gear_protected`
still carry the old set-based logic. This module only builds the replacement
authority as a pure core so it can be reviewed and tested standalone before
any migration.
"""

from enum import Enum

from artifactsmmo_cli.ai.bank_selection import (
    _best_fighting_weapon,
    _best_gathering_tools,
    _recipe_materials,
)
from artifactsmmo_cli.ai.consumable_supply import HEAL_STOCK_FLOOR, heal_stock_target
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_caps import useful_quantity_cap
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState

KEEP_ALL = 1_000_000
"""Sentinel quantity meaning "keep every copy". The ONLY reason that returns
this is `CURRENCY` (`tasks_coin`) — every other reason must express its
protection as a finite, item-specific quantity."""


class KeepReason(Enum):
    """Every reason an item's copies must be protected from disposal. Deriving
    from every existing blanket site (`bank_selection._keep_codes`,
    `recycle_surplus`'s `protected_codes`/`kit`, `guards._gear_protected`,
    `useful_quantity_cap`) — nothing here may be dropped in migration."""

    CURRENCY = "currency"
    ACTIVE_TASK = "active_task"
    HEALING_CONSUMABLE = "healing_consumable"
    COMBAT_WEAPON = "combat_weapon"
    WORKING_KIT = "working_kit"
    COMMITTED_RECIPE = "committed_recipe"
    GOAL_MATERIALS = "goal_materials"
    EQUIPPED = "equipped"
    GEAR_DEMAND = "gear_demand"
    RECIPE_DEMAND = "recipe_demand"


IN_BAG_REASONS: frozenset[KeepReason] = frozenset({
    KeepReason.CURRENCY,
    KeepReason.ACTIVE_TASK,
    KeepReason.HEALING_CONSUMABLE,
    KeepReason.COMBAT_WEAPON,
    KeepReason.WORKING_KIT,
    KeepReason.COMMITTED_RECIPE,
    KeepReason.GOAL_MATERIALS,
})
"""Reasons that feed `keep_in_bag` — copies that must stay in the BAG.
Banking is reversible, so this ladder is generous: anything the active plan
might need again soon."""

OWNED_REASONS: frozenset[KeepReason] = frozenset({
    KeepReason.CURRENCY,
    KeepReason.ACTIVE_TASK,
    KeepReason.EQUIPPED,
    KeepReason.GEAR_DEMAND,
    KeepReason.RECIPE_DEMAND,
})
"""Reasons that feed `keep_owned` — copies that must remain OWNED (bag+bank).
Destroying (recycle/sell/discard) is NOT reversible, so this ladder is
narrower: only genuine future demand, not "might be handy in the bag"."""


def _currency(code: str, state: WorldState, game_data: GameData,
             ctx: SelectionContext) -> int:
    return KEEP_ALL if code == TASKS_COIN_CODE else 0


def _active_task(code: str, state: WorldState, game_data: GameData,
                 ctx: SelectionContext) -> int:
    if code != state.task_code:
        return 0
    return max(0, state.task_total - state.task_progress)


def _healing_consumable(code: str, state: WorldState, game_data: GameData,
                        ctx: SelectionContext) -> int:
    """Real cap, not "keep all" (user ruling): mirrors the stock target
    `consumable_supply.maintain_consumables_fires` already sizes the heal
    stock to — `heal_stock_target(HEAL_STOCK_FLOOR)`, its default/only call
    site value. Surplus above the target becomes bankable (recoverable, and
    it frees slots) instead of hoarded forever."""
    stats = game_data.item_stats(code)
    if stats is None or stats.hp_restore <= 0:
        return 0
    return heal_stock_target(HEAL_STOCK_FLOOR)


def _combat_weapon(code: str, state: WorldState, game_data: GameData,
                   ctx: SelectionContext) -> int:
    return 1 if code == _best_fighting_weapon(state, game_data) else 0


def _working_kit(code: str, state: WorldState, game_data: GameData,
                 ctx: SelectionContext) -> int:
    return 1 if code in _best_gathering_tools(state, game_data) else 0


def _committed_recipe(code: str, state: WorldState, game_data: GameData,
                      ctx: SelectionContext) -> int:
    roots: list[str] = []
    if state.crafting_target:
        roots.append(state.crafting_target)
    if state.task_type == "items" and state.task_code:
        roots.append(state.task_code)
    if not roots:
        return 0
    materials = _recipe_materials(roots, game_data)
    if code not in materials:
        return 0
    demand = 0
    for root in roots:
        recipe = game_data.crafting_recipe(root) or {}
        demand = max(demand, recipe.get(code, 0))
    return demand


def _goal_materials(code: str, state: WorldState, game_data: GameData,
                    ctx: SelectionContext) -> int:
    """The active objective-step goal's `needed` map. `SelectionContext` does
    not carry `step_profile` until Task 2 of this epic; until then this reads
    as an always-empty `getattr` default so this function does not change
    when the field becomes real."""
    step_profile: dict[str, int] = getattr(ctx, "step_profile", {}) or {}
    return step_profile.get(code, 0)


def _equipped(code: str, state: WorldState, game_data: GameData,
             ctx: SelectionContext) -> int:
    return 1 if code in state.equipment.values() else 0


def _gear_demand(code: str, state: WorldState, game_data: GameData,
                 ctx: SelectionContext) -> int:
    return (ctx.gear_keep or {}).get(code, 0)


def _recipe_demand(code: str, state: WorldState, game_data: GameData,
                   ctx: SelectionContext) -> int:
    return useful_quantity_cap(code, state, game_data, gear_keep=ctx.gear_keep or None)


_REASON_FUNCS = {
    KeepReason.CURRENCY: _currency,
    KeepReason.ACTIVE_TASK: _active_task,
    KeepReason.HEALING_CONSUMABLE: _healing_consumable,
    KeepReason.COMBAT_WEAPON: _combat_weapon,
    KeepReason.WORKING_KIT: _working_kit,
    KeepReason.COMMITTED_RECIPE: _committed_recipe,
    KeepReason.GOAL_MATERIALS: _goal_materials,
    KeepReason.EQUIPPED: _equipped,
    KeepReason.GEAR_DEMAND: _gear_demand,
    KeepReason.RECIPE_DEMAND: _recipe_demand,
}


def reason_quantity(reason: KeepReason, code: str, state: WorldState,
                    game_data: GameData, ctx: SelectionContext) -> int:
    """Dispatch to the per-reason function; 0 when `reason` does not apply to
    `code`. Used by the census to build cells."""
    return _REASON_FUNCS[reason](code, state, game_data, ctx)


def keep_in_bag(code: str, state: WorldState, game_data: GameData,
                ctx: SelectionContext) -> int:
    """Copies of `code` that must stay in the BAG — the max over
    `IN_BAG_REASONS`. Banking is reversible, so this ladder is generous."""
    return max(reason_quantity(r, code, state, game_data, ctx) for r in IN_BAG_REASONS)


def keep_owned(code: str, state: WorldState, game_data: GameData,
               ctx: SelectionContext) -> int:
    """Copies of `code` that must remain OWNED (bag+bank) — the max over
    `OWNED_REASONS`. Destroying is not reversible, so this ladder is
    narrower than `keep_in_bag`."""
    return max(reason_quantity(r, code, state, game_data, ctx) for r in OWNED_REASONS)


def bankable(code: str, state: WorldState, game_data: GameData,
            ctx: SelectionContext) -> int:
    """Copies of `code` in the BAG beyond `keep_in_bag` — safe to move to the
    bank (fully reversible)."""
    return max(0, state.inventory.get(code, 0) - keep_in_bag(code, state, game_data, ctx))


def destroyable(code: str, state: WorldState, game_data: GameData,
               ctx: SelectionContext) -> int:
    """Copies of `code` across bag+bank beyond `keep_owned` — safe to
    recycle/sell/delete. keep_owned is about OWNERSHIP, so bank copies count
    toward satisfying it."""
    owned = state.inventory.get(code, 0) + (state.bank_items or {}).get(code, 0)
    return max(0, owned - keep_owned(code, state, game_data, ctx))

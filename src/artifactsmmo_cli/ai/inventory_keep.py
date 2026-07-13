"""The single keep authority: how many copies of an item must stay.

Protection used to be expressed as `frozenset[str]` code-sets, which can only
mean "keep ALL copies" — four hoard bugs came from that one type (18 copper_axe
shielded because the axe was the best woodcutting tool). Here every protection
reason contributes a QUANTITY, so a blanket is inexpressible; `KEEP_ALL` is the
one explicit escape hatch and it is used once (currency).

Two caps, because "protection" conflated two questions:
  * keep_in_bag  — copies that must stay in the BAG (banking is REVERSIBLE)
  * keep_owned   — copies that must remain OWNED, bag+bank (destroying is NOT)

DELIBERATE DE-BLANKETING (`GEAR_DEMAND`): the old `guards._gear_protected` had
a second arm — when `ctx.gear_keep` was empty it returned the CODE-SET
`target_gear | target_tools`, i.e. "keep ALL copies of every BiS gear/tool
code". That set is not reinstated here, on purpose: it is the bug class this
module exists to kill (`copper_axe` is a `target_tools` member, which is
another reason all 18 were hoarded). A BiS target is wanted ONCE, so the
profile-less case is served by the EQUIPPED / RECIPE_DEMAND arms
(`useful_quantity_cap`'s `EQUIPPABLE_KEEP = 1`) — keep 1, the rest disposable.

MIGRATION (item-protection-authority epic): `bank_selection.select_bank_deposits`
is LIVE on this authority (Task 6) — DepositAll banks `bankable(code)` copies of
every held code, which is what finally sheds the 17 surplus copper_axe. So is
`recycle_surplus.recyclable_surplus` (Task 7) — RECYCLE destroys the copies above
BOTH caps, `min(bankable, destroyable)`: `destroyable` because destruction is
irreversible and answers to OWNERSHIP, `bankable` because the destruction happens
BAG-side and a copy the bag must keep (WORKING_KIT: the tool the gather re-arm is
about to equip) must not be eaten when banking it was the correct move. Its
`protected_codes` frozenset, its `kit` code-set and `guards.recycle_protected_codes`
are all DELETED. The remaining set-based consumer (`guards._gear_protected`, on
the bank-drain path) is migrated by Tasks 8-9.
"""

from enum import Enum

from artifactsmmo_cli.ai.consumable_supply import HEAL_STOCK_FLOOR, heal_stock_target
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_caps import (
    _task_chain_demand_pure,
    useful_quantity_cap,
)
from artifactsmmo_cli.ai.kit_selection import (
    best_fighting_weapon,
    best_gathering_tools,
    best_owned_fighting_weapon,
    best_owned_gathering_tools,
)
from artifactsmmo_cli.ai.selection_context import SelectionContext
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
might need again soon. Membership is load-bearing and pinned by test: a
bag-only reason leaking into `OWNED_REASONS` would make a working tool or a
surplus potion un-destroyable forever."""

OWNED_REASONS: frozenset[KeepReason] = frozenset({
    KeepReason.CURRENCY,
    KeepReason.ACTIVE_TASK,
    KeepReason.COMBAT_WEAPON,
    KeepReason.WORKING_KIT,
    KeepReason.EQUIPPED,
    KeepReason.GEAR_DEMAND,
    KeepReason.RECIPE_DEMAND,
})
"""Reasons that feed `keep_owned` — copies that must remain OWNED (bag+bank).
Destroying (recycle/sell/discard) is NOT reversible, so this ladder is
narrower: only genuine future demand, not "might be handy in the bag".
Membership is load-bearing and pinned by test: an owned-only reason leaking
into `IN_BAG_REASONS` would pin bank-worthy gear demand into the bag and eat
the slots this epic exists to free.

WORKING_KIT and COMBAT_WEAPON are in BOTH ladders (quantity 1 in each): "keep
ONE in the bag" (the copy the gather re-arm equips) and "never melt your LAST
one" are DIFFERENT obligations, and the second is an OWNERSHIP invariant. Filed
bag-only they left a DESTRUCTION hole: the tool the deposit migration leaves at
0-in-bag/17-in-bank has no bag copy to protect, so `keep_owned` was 0 and a
consumer reading `destroyable` (the bank drain) would melt every copy of the
character's best axe — strictly worse than the hoard bug this module fixes."""


def _currency(code: str, state: WorldState, game_data: GameData,
             ctx: SelectionContext) -> int:
    return KEEP_ALL if code == TASKS_COIN_CODE else 0


def _active_task(code: str, state: WorldState, game_data: GameData,
                 ctx: SelectionContext) -> int:
    if code != state.task_code:
        return 0
    return max(0, state.task_total - state.task_progress)


def _held_heals(state: WorldState, game_data: GameData) -> list[tuple[str, int, int]]:
    """Every HELD heal code as `(code, qty, hp_restore)`, strongest first, ties
    broken on the lexically smallest code (a stable sort over `sorted()` keys).

    The population is EXACTLY the one `consumable_supply.heal_stock` sums over
    (`state.inventory`, `qty > 0`, `hp_restore > 0`) — the keep authority must
    range over the same set the target is measured against.

    NOT `consumable_supply.best_held_heal`: that selector additionally requires
    the heal to map to a `utility1_slot`, because its caller equips heals for
    marginal-fight provisioning. Using the utility-filtered selector would find
    nothing in a food-only bag and drop the ENTIRE heal stock to keep 0,
    re-creating the "banked the healing stock, now Rest forever" livelock."""
    held: list[tuple[str, int, int]] = []
    for held_code in sorted(state.inventory):
        qty = state.inventory[held_code]
        if qty <= 0:
            continue
        stats = game_data.item_stats(held_code)
        if stats is None or stats.hp_restore <= 0:
            continue
        held.append((held_code, qty, stats.hp_restore))
    held.sort(key=lambda entry: -entry[2])
    return held


def _healing_consumable(code: str, state: WorldState, game_data: GameData,
                        ctx: SelectionContext) -> int:
    """Real cap, not "keep all" (user ruling): the stock target
    `consumable_supply.maintain_consumables_fires` already sizes the heal stock
    to — `heal_stock_target(HEAL_STOCK_FLOOR)`, its default/only call-site value.

    The target is an AGGREGATE (`heal_stock` sums across ALL heal codes), so it
    is FILLED GREEDILY across the held heal codes, strongest first, until the
    aggregate is met; `code`'s share is what the fill assigns it. Two failure
    modes are avoided at once:

      * charging the whole target to EVERY heal code keeps N x target — over-
        protection in the exact place this epic frees slots;
      * charging the whole target to ONE code UNDER-fills when that code is
        short (3 cooked_chicken held against a target of 5 keeps 3 and leaves
        every apple bankable — after DepositAll the real `heal_stock` is 3,
        below target, so `MaintainConsumables` re-fires and crafts more: churn).

    Surplus beyond the aggregate stays bankable — never sold or deleted,
    because HEALING_CONSUMABLE feeds `in_bag` only."""
    remaining = heal_stock_target(HEAL_STOCK_FLOOR)
    for held_code, qty, _restore in _held_heals(state, game_data):
        if remaining <= 0:
            break
        share = min(qty, remaining)
        if held_code == code:
            return share
        remaining -= share
    return 0


def _combat_weapon(code: str, state: WorldState, game_data: GameData,
                   ctx: SelectionContext) -> int:
    """ONE copy of the best fighting weapon — the one being swung (bag-scoped)
    and the best one OWNED (bank-scoped). Both, because this reason feeds BOTH
    caps: the working copy must not be BANKED, and the last owned copy must not
    be DESTROYED (see `_working_kit`)."""
    return 1 if (code == best_fighting_weapon(state, game_data)
                 or code == best_owned_fighting_weapon(state, game_data)) else 0


def _working_kit(code: str, state: WorldState, game_data: GameData,
                 ctx: SelectionContext) -> int:
    """ONE copy of the best gathering tool per skill.

    Ranged over BOTH scopes (`kit_selection`): what is to HAND (bag + equipped),
    whose copy the bag cap pins so the gather re-arm has a tool to equip; and
    what is OWNED (bag + bank + equipped), whose copy the ownership cap refuses
    to destroy. The bank scope is load-bearing for the OWNED cap: once the one
    bag copy is spent or equipped the tool sits ENTIRELY in the bank, invisible
    to the bag-scoped selector — and a `destroyable` computed from a 0 cap would
    melt all 18 copies of the character's only axe."""
    return 1 if (code in best_gathering_tools(state, game_data)
                 or code in best_owned_gathering_tools(state, game_data)) else 0


def _committed_recipe(code: str, state: WorldState, game_data: GameData,
                      ctx: SelectionContext) -> int:
    """TRANSITIVE chain demand for `code` under the committed craft roots.

    Both roots are walked with `inventory_caps._task_chain_demand_pure` (the
    fuel-bounded, cycle-safe, Lean-proved chain walk `useful_quantity_cap`
    already uses for its task arm) rather than a second hand-rolled tree walk:

      * `state.crafting_target` — the in-flight craft, one unit.
      * the items-task item, scaled by the REMAINING quantity
        (`task_total - task_progress`).

    Transitivity and scaling are both load-bearing. A DIRECT per-root recipe
    lookup returns 0 for a material that appears only DEEPER in the tree
    (`copper_ore` under `copper_bar` under `copper_axe`), so DepositAll would
    bank the task's own sub-material and PursueTask would freeze; and an
    unscaled lookup returns one axe's worth of bars when the task wants five.

    The roots are collected into a per-root demand MAP and their chain walks
    ADD, because DISJOINT roots want disjoint copies: an in-flight
    `copper_dagger` (8 copper_ore) alongside an items-task for `copper_axe`
    (36 copper_ore) needs 44 ore, and a `max` would keep only 36 — the
    8-ore shortfall gets banked and must be withdrawn straight back (churn).
    The map is what stops the double-count `max` was there to prevent: when the
    task item IS the crafting target it is ONE root, counted once, at the larger
    of the two quantities."""
    recipes = game_data.crafting_recipes
    fuel = len(recipes) + 1
    root_qty: dict[str, int] = {}
    if state.crafting_target:
        root_qty[state.crafting_target] = 1
    if state.task_type == "items" and state.task_code:
        remaining = max(0, state.task_total - state.task_progress)
        if remaining > 0:
            root_qty[state.task_code] = max(root_qty.get(state.task_code, 0), remaining)
    return sum(_task_chain_demand_pure(fuel, code, root, qty, recipes, {})
               for root, qty in root_qty.items())


def _goal_materials(code: str, state: WorldState, game_data: GameData,
                    ctx: SelectionContext) -> int:
    """The active objective-step goal's `needed` map (plus the recipe closure of
    each needed item's still-missing quantity), as computed by
    `strategy_driver._step_protection_profile` and bound onto the ctx by
    `StrategyArbiter.select` — the SAME map the deposit/discard guards merge via
    `guards.active_profile`, so the keep authority and the guards protect the
    same quantities.

    A QUANTITY, not the old `bank_selection` blanket: without ANY protection an
    active GatherMaterials goal's own target materials get banked out from under
    it, undoing the withdraw and livelocking the gather; with a BLANKET the whole
    growing pile is pinned in the bag. The needed quantity stays, the surplus
    above it banks."""
    return ctx.step_profile.get(code, 0)


def _equipped(code: str, state: WorldState, game_data: GameData,
             ctx: SelectionContext) -> int:
    return 1 if code in state.equipment.values() else 0


def _gear_demand(code: str, state: WorldState, game_data: GameData,
                 ctx: SelectionContext) -> int:
    """The active-profile gear demand. Deliberately has NO profile-less
    fallback to `ctx.target_gear | ctx.target_tools` — see the module
    docstring: that fallback is a code-SET (keep-all), and the profile-less
    case is correctly served with keep-1 by EQUIPPED / RECIPE_DEMAND."""
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

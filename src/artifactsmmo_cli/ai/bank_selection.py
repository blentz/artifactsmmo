"""Selective bank-deposit policy: HOW MANY copies of each held code to bank,
ordered by sell value.

QUANTITIES, not codes (the hoard fix). Deposit used to compute a `set[str]`
keep-set and bank the whole stack of every code outside it. A code-set can only
express "keep ALL copies", so protecting the working woodcutting tool protected
all EIGHTEEN copper_axe the weaponcrafting grind had manufactured: DepositAll
banked zero of them, the bag sat at 17/20 slots and eventually 497'd. The
keep-set is gone. Deposit now asks the single keep authority
(`ai/inventory_keep.py`) how many copies of each code must stay in the BAG and
banks the rest:

    deposit qty = bankable(code) = max(0, bag[code] - keep_in_bag(code))

`keep_in_bag` — not `keep_owned` — is the right cap here because banking is
REVERSIBLE (a banked copy is still owned and can be withdrawn); the destructive
routes (recycle/sell/delete) use `keep_owned`/`destroyable`.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_keep import bankable
from artifactsmmo_cli.ai.kit_selection import best_fighting_weapon, best_gathering_tools
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState


def _sell_value(code: str, game_data: GameData) -> int:
    buyers = game_data.npcs_buying_item(code)
    return max((price for _, price in buyers), default=0)


def hard_critical_codes(state: WorldState, game_data: GameData) -> set[str]:
    """The codes the LAST-RESORT relief sheds LAST: task coins, the task item,
    every HP-restore consumable held, the best fighting weapon, and the working
    gathering kit.

    A criticality RANKING, not a keep-set: in the last-resort branch nothing is
    normally bankable (every held code sits at or below its `keep_in_bag` cap),
    so one protected stack MUST be banked anyway to free a slot. This orders that
    choice — bank the stack whose absence hurts least. It can never hoard,
    because it only ever sorts a list from which exactly one entry is taken."""
    critical: set[str] = {TASKS_COIN_CODE}
    if state.task_code:
        critical.add(state.task_code)
    for code in state.inventory:
        stats = game_data.item_stats(code)
        if stats is not None and stats.hp_restore > 0:
            critical.add(code)
    weapon = best_fighting_weapon(state, game_data)
    if weapon is not None:
        critical.add(weapon)
    # The working kit joins the ranking (it always did in the proved model —
    # `Formal.BankSelection.inKeepBase` — but the Python last-resort omitted it, a
    # divergence the differential could not see until deposit became quantity-typed
    # and the last-resort branch got reachable with a tool in the bag). Shedding the
    # kit first would undo the WithdrawTools ferry and re-create the bare-handed
    # grind; the axe SPARES are bankable on the normal path, so the last-resort never
    # needs to take the working one first.
    critical |= best_gathering_tools(state, game_data)
    return critical


def _last_resort_deposit(state: WorldState, game_data: GameData,
                         ctx: SelectionContext) -> tuple[str, int] | None:
    """The single least-critical item-stack to bank when the bag is COMPLETELY
    full and NOTHING is bankable (every held code is at or below its keep cap),
    to free exactly one slot.

    Last-resort relief (2026-06-19): a bag with zero free slots and nothing
    normally bankable is a hard stall — `FightAction.is_applicable` requires
    `inventory_free >= 1` (combat.py) and no other relief path fires, so the
    planner drops to WAIT and stops leveling (the confirmed full-of-keep-set
    livelock). Banking a protected item is fully recoverable (re-withdrawable), so
    it frees the slot without losing anything.

    Picks the least disruptive stack: NOT immediately critical
    (`hard_critical_codes`) before anything else, NOT in the active step's goal
    profile before profile items, then lowest sell-value, then code ascending
    (deterministic)."""
    critical = hard_critical_codes(state, game_data)
    items = [(code, qty) for code, qty in state.inventory.items() if qty > 0]
    if not items:
        return None
    items.sort(key=lambda cq: (cq[0] in critical, cq[0] in ctx.step_profile,
                               _sell_value(cq[0], game_data), cq[0]))
    return items[0]


def select_bank_deposits(state: WorldState, game_data: GameData,
                         ctx: SelectionContext = NO_PROFILE_CONTEXT,
                         ) -> list[tuple[str, int]]:
    """`(code, quantity)` to deposit — for every held code, the copies the keep
    authority says are surplus to the BAG (`inventory_keep.bankable`) — ordered
    (sell_value desc, code asc). Items with no known NPC buy-back price get value
    0 and sort last.

    Every reason the old keep-set protected is now a QUANTITY in the authority's
    registry (`KeepReason`): task coins (CURRENCY, the one `KEEP_ALL`), the task
    item (ACTIVE_TASK, scaled by the REMAINING quantity), HP consumables
    (HEALING_CONSUMABLE, the greedy aggregate stock fill), the best fighting
    weapon (COMBAT_WEAPON, 1), the working gathering kit (WORKING_KIT, 1 — the
    blanket that hoarded 18 axes), the crafting-target / items-task recipe
    materials (COMMITTED_RECIPE, the TRANSITIVE task-quantity-scaled chain), and
    the active goal's materials (GOAL_MATERIALS, `ctx.step_profile`). None is
    lost; each now protects a countable number of copies instead of a code, so
    the SURPLUS above it banks.

    `KEEP_ALL` (1e6, currency) needs no special case at this boundary:
    `bankable` clamps at 0, so `tasks_coin` yields 0 bankable copies at ANY held
    quantity. `keep_in_bag` may legitimately EXCEED the bag (two committed roots
    whose combined demand does not fit) — that is a SCHEDULING signal, and the
    same clamp makes it mean "bank nothing", never a negative deposit.

    LAST-RESORT relief: when the bag cannot admit another item — EITHER the total
    item capacity is exhausted (`inventory_free == 0`) OR every inventory SLOT is
    occupied (`inventory_slots_free == 0`) — and nothing is bankable (every held
    code is at or below its keep cap), bank ONE least-critical stack to free a
    slot. Otherwise the bot cannot fight (combat needs a free slot) and no other
    relief fires, stalling leveling. A bag of many low-count protected stacks fills
    all 20 slots long before the quantity cap, so gating on `inventory_free == 0`
    alone missed that stall; the slot condition is the real "cannot act" test. The
    keep caps are honoured while ANY room (quantity AND slots) remains."""
    deposits: list[tuple[str, int]] = []
    for code, qty in state.inventory.items():
        if qty <= 0:
            continue
        surplus = bankable(code, state, game_data, ctx)
        if surplus > 0:
            deposits.append((code, surplus))
    deposits.sort(key=lambda cq: (-_sell_value(cq[0], game_data), cq[0]))
    if deposits:
        return deposits
    if state.inventory_free == 0 or state.inventory_slots_free == 0:
        item = _last_resort_deposit(state, game_data, ctx)
        if item is not None:
            return [item]
    return deposits

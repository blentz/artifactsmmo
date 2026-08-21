"""Impure progression-reserve target identification and pricing.

Each category SOURCE yields the unmet near-term (level..level+2) progression
items the bot would BUY, mapped to their cheapest gold buy price. The pure
`progression_reserve_core` then sums them and applies the deduction-aware floor.
Craftable-now / unsellable items contribute nothing (no gold needed).
"""
from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.progression_reserve_core import (
    effective_floor,
    effective_floor_multi,
    reserve_total,
)
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.world_state import WorldState

_HORIZON = 2  # reserve for upgrades usable within the next 2 character levels
_MIN_SAFETY_FLOOR = 100  # never spend to zero even when nothing is reserved


def buy_price(code: str, game_data: GameData) -> int | None:
    """Cheapest gold price to BUY one `code` (min over NPC sellers and the GE
    best SELL order — the standing sell order the player fills when buying),
    or None when nothing sells it."""
    prices: list[int] = [p for _npc, p in game_data.npcs_selling_item(code)]
    ge = game_data.ge_best_sell_order(code)
    if ge is not None:
        prices.append(ge[1])
    return min(prices) if prices else None


def gear_targets(state: WorldState, game_data: GameData) -> dict[str, int]:
    """Unmet gear upgrades usable within the horizon that the bot would BUY,
    mapped to their buy price. Per combat slot, the best equippable of the slot's
    type at level <= state.level + _HORIZON whose value beats the equipped item,
    included only when no crafting recipe exists (pure BUY item) and a seller
    exists. Craftable items are excluded: gold is not needed to acquire them."""
    out: dict[str, int] = {}
    max_level = state.level + _HORIZON
    for _slot, code in _best_per_slot(state, game_data, max_level).items():
        if game_data.crafting_recipe(code) is not None:
            continue
        price = buy_price(code, game_data)
        if price is None:
            continue
        out[code] = price
    return out


def _best_per_slot(state: WorldState, game_data: GameData,
                   max_level: int) -> dict[str, str]:
    """{slot: best_upgrade_code} for combat slots where an in-horizon item beats
    the equipped one. Scans all item stats by the slot's item type."""
    best: dict[str, str] = {}
    for code, stats in game_data.all_item_stats.items():
        slots = ITEM_TYPE_TO_SLOTS.get(stats.type_)
        if not slots or stats.level > max_level:
            continue
        for slot in slots:
            equipped = state.equipment.get(slot)
            cur = game_data.item_stats(equipped) if equipped else None
            cur_val = equip_value(cur) if cur is not None else 0
            if equip_value(stats) <= cur_val:
                continue
            incumbent = best.get(slot)
            inc_stats = game_data.item_stats(incumbent) if incumbent else None
            inc_val = equip_value(inc_stats) if inc_stats is not None else cur_val
            if equip_value(stats) > inc_val:
                best[slot] = code
    return best


def _is_gatherable(material: str, game_data: GameData) -> bool:
    """True when some resource node drops `material` (gathering, not gold)."""
    return material in game_data.gatherable_drop_items()


def crafting_unlock_targets(state: WorldState, game_data: GameData) -> dict[str, int]:
    """Buyable recipe INPUTS for in-horizon craftable gear whose final craft is
    skill-reachable: an input the bot must BUY (no gather/craft path) is a real
    upcoming gold need. Maps each such input to qty * buy price.

    A material is a reserved gold need iff ALL of:
      1. it is NOT gatherable (_is_gatherable is False), AND
      2. it has NO crafting recipe of its own (game_data.crafting_recipe is None),
         so gold is the only acquisition path, AND
      3. buy_price returns a non-None value (a seller exists).
    """
    out: dict[str, int] = {}
    max_level = state.level + _HORIZON
    for code, stats in game_data.all_item_stats.items():
        if ITEM_TYPE_TO_SLOTS.get(stats.type_) is None or stats.level > max_level:
            continue
        recipe = game_data.crafting_recipe(code)
        if not recipe:
            continue
        for material, qty in recipe.items():
            if _is_gatherable(material, game_data):
                continue
            if game_data.crafting_recipe(material) is not None:
                continue
            price = buy_price(material, game_data)
            if price is None:
                continue
            out[material] = qty * price
    return out


def boss_targets(state: WorldState, game_data: GameData) -> dict[str, int]:
    """Boss-odds reservation — STUB. Reserving for boss-fight items needs the
    boss-pursuit machinery (winnability + event/boss drop identification) that is
    not yet built (docs/PLAN_calculate_not_hardcode.md #9, roadmap5). Returns no
    targets until that lands; this is the documented extension point."""
    return {}


def _reserve_key(state: WorldState) -> tuple[object, ...]:
    """Everything `reserved_targets` reads off the state, and nothing else.

    `gear_targets` reads the level and the worn equipment; `crafting_unlock_targets`
    reads the level; `boss_targets` is a stub. Quantities, gold and position do
    not enter, which is what makes the key stable across the states a search
    projects — the planner changes the bag on almost every node and the
    reservation does not move with it.

    Equipment is sorted BY SLOT, never by the pair: a slot's value may be None,
    and comparing None against a code raises."""
    return (state.level,
            tuple(sorted(state.equipment.items(), key=lambda kv: kv[0])))


def reserved_targets(state: WorldState, game_data: GameData) -> dict[str, int]:
    """All unmet near-term BUY-acquired progression targets -> buy price, unioned
    across the category sources. Same code from two sources prices identically
    (min npc/ge), so dict union is unambiguous.

    MEMOISED on the snapshot (`GameData.reserved_targets_memo`), because this
    walks every item in the game and `can_spend` asks it from three actions'
    `is_applicable` — once per candidate per node. Profiled at 8ms a call and
    4.2s of one 15s planning budget.

    The returned mapping is SHARED with the cache. Callers read it (`sum`,
    membership, `effective_floor`) and none mutates it; a caller that needs to
    must copy first."""
    memo = game_data.reserved_targets_memo
    key = _reserve_key(state)
    hit = memo.get(key)
    if hit is not None:
        return hit
    targets: dict[str, int] = {}
    for source in (gear_targets, crafting_unlock_targets, boss_targets):
        targets.update(source(state, game_data))
    memo[key] = targets
    return targets


def progression_reserve(state: WorldState, game_data: GameData) -> int:
    """Total gold reserved for near-term progression (replaces the old flat
    constant). Floored at `_MIN_SAFETY_FLOOR` so the bot never spends to zero
    even when nothing is reserved."""
    return max(_MIN_SAFETY_FLOOR, reserve_total(reserved_targets(state, game_data)))


def _binding(floor: int, state: WorldState) -> int:
    """`floor`, unless the account cannot fund it — then only the safety floor.

    A RESERVE YOU CANNOT FUND DOES NOT BIND. `reserved_targets` prices every
    unmet progression target inside a two-level horizon, and that total routinely
    exceeds the balance: measured live on all five characters, 57,307-78,750
    reserved against 28,511-35,768 held, with a 50,000 `backpack` and a 20,000
    `lifesteal_rune` accounting for most of it. Held literally, "never drop below
    75,745" blocks EVERY gold purchase at 30,532 — including the 1,498 one that
    buys the very upgrade the reserve exists to protect.

    So the gold sits idle, none of the reserved targets is ever bought, and the
    reservation defeats itself. When the earmarks cannot all be honoured anyway,
    the safety floor is the only part still worth enforcing; once the account can
    actually fund the plan, the full floor binds again.

    Measured consequence of NOT doing this: C3P0 timed out planning
    `adventurer_pants` and fell through to Wait every cycle, with a standing GE
    order offering one for 1,498 gold and 14,532 in his pocket."""
    return _MIN_SAFETY_FLOOR if floor >= account_gold(state) else floor


def reserve_floor(state: WorldState, game_data: GameData,
                  buying: str | None) -> int:
    """The deduction-aware reserve floor that applies while buying `buying`,
    floored at `_MIN_SAFETY_FLOOR` and not binding above what the account holds
    (`_binding`)."""
    reserved = reserved_targets(state, game_data)
    return _binding(max(_MIN_SAFETY_FLOOR, effective_floor(reserved, buying)), state)


def reserve_floor_multi(state: WorldState, game_data: GameData,
                        buying: frozenset[str]) -> int:
    """The deduction-aware reserve floor that applies while JOINTLY buying
    EVERY leaf in `buying` (follow-up wave Task 4's joint gold-affordability
    check): dedups each admitted leaf's own reservation from the total, not
    just one — generalizes `reserve_floor` (`reserve_floor_multi(s, gd,
    frozenset({x})) == reserve_floor(s, gd, x)` for any `x`). Floored at
    `_MIN_SAFETY_FLOOR` same as the single-leaf form.

    Two individually reserve-safe gold-priced leaves can jointly overspend the
    reserve when each is checked against `reserve_floor(..., leaf)`
    independently (that dedups ONLY its own leaf, so the OTHER leaf's price
    is double-counted as spendable room by both checks). Checking the whole
    admitted SET against this joint floor closes that gap."""
    reserved = reserved_targets(state, game_data)
    return _binding(
        max(_MIN_SAFETY_FLOOR, effective_floor_multi(reserved, buying)), state)


def account_gold(state: WorldState) -> int:
    """Gold the ACCOUNT holds, pocket plus bank.

    The reserve is a property of the account (one bank, one gold balance shared
    by every character), so every question of the form "does spending this break
    the reserve" has to be asked of this total. Asking it of `state.gold` alone
    refuses a purchase the account can plainly afford: measured on the
    `l30_rune_fill` scenario, 25,000 in pocket and 50,000 in bank against a
    20,000 upgrade and a 50,000 reserve reads as a refusal on the pocket and an
    approval on the account.

    `bank_gold` is `None` when the bank has not been read this cycle. That is
    UNKNOWN, not zero, so it is credited as nothing — which degrades this back to
    the pocket-only reading rather than inventing a balance."""
    banked = state.bank_gold if state.bank_gold is not None else 0
    return state.gold + banked


def can_spend(state: WorldState, game_data: GameData, buying: str | None,
              cost: int) -> bool:
    """True iff spending `cost` gold to buy `buying` leaves the ACCOUNT at or
    above its reserve floor.

    The single definition every gold sink asks (S-045: gold is protected by
    refusal, and one reserve governs). Executability — whether the gold is in
    the right place to be spent at this venue — is a separate question and stays
    with the caller."""
    return account_gold(state) - cost >= reserve_floor(state, game_data, buying)

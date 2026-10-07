"""The fleet's consumable floor from live data (Phase 5-2c-iii-c-2 #5,
`docs/PLAN_task_value.md` §10). The decisions are the proved pure core
`consumable_floor_core`; this module reads their inputs.

USER 2026-10-07: "Fishing feeds Cooking, Cooking feeds HP recovery or provides
stat bonuses. Both cases require pre-emptive crafting of an available supply.
The fleet can collectively maintain a minimum supply in the bank." Rulings:
"Fleet size × per-char target"; "Tier-appropriate"; filled "via SupplyBank".

Two classes, each with its own per-character target:

* heal FOOD (`type_ == "consumable"`, restores hp): `HEAL_STOCK_FLOOR`, the bag
  floor every grind already keeps;
* heal POTION (`type_ == "utility"`, restores hp): the per-fight projection
  `potion_supply.heal_stock_target` against the fight ahead (0 with none).

Stock is the account bank, this character's bag and utility slots, and the
siblings' published holdings (`consumable_holdings`). No catalogue food carries
a buff today (2026-10-07); boost potions are sized per monster by the potion
guard and are not floored here — a residual.
"""

from collections.abc import Mapping

from artifactsmmo_cli.ai.consumable_floor_core import fleet_deficit, tier_pick
from artifactsmmo_cli.ai.consumable_supply import HEAL_STOCK_FLOOR
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.potion_supply import heal_stock_target
from artifactsmmo_cli.ai.world_state import WorldState

FOOD = "consumable"
POTION = "utility"


def heal_candidates(game_data: GameData, type_: str) -> list[str]:
    """Every heal of `type_`, in catalogue order (the core breaks ties on it)."""
    return [code for code, stats in game_data.items.stats.items()
            if stats.type_ == type_ and stats.hp_restore > 0]


def consumable_holdings(state: WorldState, game_data: GameData) -> dict[str, int]:
    """This character's heals, CARRIED plus in the utility slots. The bank is
    absent: it is account-shared, so every child reads it directly (the same
    rule as `dual_role_holdings`)."""
    held: dict[str, int] = {}
    for code, qty in state.inventory.items():
        stats = game_data.item_stats(code)
        if qty > 0 and stats is not None and stats.hp_restore > 0:
            held[code] = held.get(code, 0) + qty
    for slot, qty in (("utility1_slot", state.utility1_slot_quantity),
                      ("utility2_slot", state.utility2_slot_quantity)):
        worn = state.equipment.get(slot)
        if worn is not None and qty > 0:
            held[worn] = held.get(worn, 0) + qty
    return held


def supply_shortfall(state: WorldState, game_data: GameData, history: LearningStore | None,
                     fight_monster: str | None, fleet_size: int,
                     siblings: Mapping[str, int]) -> tuple[tuple[str, int], ...]:
    """(consumable, fleet deficit) for each class below its fleet floor."""
    own = consumable_holdings(state, game_data)
    bank = state.bank_items or {}
    out: list[tuple[str, int]] = []
    for type_ in (FOOD, POTION):
        codes = heal_candidates(game_data, type_)
        pick = tier_pick(state.level, [(game_data.items.stats[code].level,
                                        game_data.items.stats[code].hp_restore) for code in codes])
        if pick is None:
            continue
        code = codes[pick]
        target = (HEAL_STOCK_FLOOR if type_ == FOOD
                  else heal_stock_target(state, game_data, history, fight_monster, code))
        stock = own.get(code, 0) + siblings.get(code, 0) + bank.get(code, 0)
        deficit = fleet_deficit(target, fleet_size, stock)
        if deficit > 0:
            out.append((code, deficit))
    return tuple(out)

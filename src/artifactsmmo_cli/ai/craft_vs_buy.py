"""Craft-vs-buy acquisition decision. For a needed item an NPC sells, choose BUY
over CRAFT only when buying is strictly fewer cooldowns AND affordable above a gold
reserve. Cooldowns is the optimization metric; gold is a HARD constraint (the
reserve), never converted. The pure `cheaper_acquisition` is the differential
target proved in formal/Formal/CraftVsBuy.lean; `acquisition_method` is the impure
adapter that assembles inputs from GameData and delegates.
"""

from enum import Enum

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gather_floor import ceil_gathers
from artifactsmmo_cli.ai.min_gathers import min_gathers
from artifactsmmo_cli.ai.world_state import WorldState


class Method(Enum):
    CRAFT = "craft"
    BUY = "buy"


def cheaper_acquisition(
    craft_cooldowns: int, buy_cooldowns: int, total_price: int, gold: int, reserve: int
) -> Method:
    """BUY iff affordable above the reserve AND strictly fewer cooldowns; else CRAFT."""
    affordable = gold - total_price >= reserve
    return Method.BUY if (affordable and buy_cooldowns < craft_cooldowns) else Method.CRAFT


def _craft_cooldowns(item: str, needed: int, state: WorldState, game_data: GameData) -> int:
    owned = dict(state.inventory)
    for code, qty in (state.bank_items or {}).items():
        owned[code] = owned.get(code, 0) + qty
    gathers = ceil_gathers(
        min_gathers(item, needed, game_data.crafting_recipes, owned),
        game_data.max_gather_yield)
    # one craft action per distinct craftable node in the recipe tree (>=1 if craftable)
    crafts = 1 if game_data.crafting_recipe(item) else 0
    return gathers + crafts


def _buy_cooldowns(npc_location: tuple[int, int] | None, state: WorldState, needed: int) -> int:
    if npc_location is None:
        return needed  # unknown location: degrade to a constant-ish term (documented)
    travel = abs(npc_location[0] - state.x) + abs(npc_location[1] - state.y)
    return travel + needed  # one buy action per unit (no per-buy cap modeled)


def acquisition_method(
    item: str, needed: int, state: WorldState, game_data: GameData, reserve: int
) -> Method:
    """Assemble inputs from GameData and delegate to the proved `cheaper_acquisition`.
    Returns CRAFT when no NPC sells the item (fail-open)."""
    sellers = game_data.npcs_selling_item(item)
    if not sellers:
        return Method.CRAFT
    npc_code, unit_price = min(sellers, key=lambda np: np[1])
    total_price = unit_price * needed
    buy_cd = _buy_cooldowns(game_data.npc_location(npc_code), state, needed)
    craft_cd = _craft_cooldowns(item, needed, state, game_data)
    return cheaper_acquisition(craft_cd, buy_cd, total_price, state.gold, reserve)

"""Items that are BOTH wearable and spendable.

`lich_race_medal` is the live case: `type: artifact`, so `pick_loadout` will
wear it, and the `currency` of `lich_race_trophy`, so the archaeologist will
take it as payment. The fleet therefore stores its trophy fund in its own
artifact slots without anyone deciding to.

Nothing here forbids wearing one. Recognising the dual role is what lets the
fleet COUNT what it is wearing; `currency_turnin` decides when to spend it."""

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


def is_dual_role(code: str, game_data: GameData) -> bool:
    """True when `code` can be equipped AND is accepted as payment somewhere."""
    stats = game_data.item_stats(code)
    if stats is None or stats.type_ not in ITEM_TYPE_TO_SLOTS:
        return False
    return bool(game_data.currency_sinks(code))


def dual_role_holdings(state: WorldState, game_data: GameData) -> dict[str, int]:
    """This character's dual-role units, WORN PLUS CARRIED, per code.

    Worn units count because they are recoverable in one `UnequipAction`, and
    the whole point of the fleet ledger is that a worn medal is still fleet
    currency. The bank is deliberately absent: it is account-shared, so every
    child reads it directly and adding it here would count it once per child."""
    held: dict[str, int] = {}
    for code, qty in state.inventory.items():
        if qty > 0 and is_dual_role(code, game_data):
            held[code] = held.get(code, 0) + qty
    for worn_code in state.equipment.values():
        if worn_code and is_dual_role(worn_code, game_data):
            held[worn_code] = held.get(worn_code, 0) + 1
    return held

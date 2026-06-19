"""Pure predicate: can the bank physically accept a deposited item?

`bank_capacity is None` = capacity unknown (NOT room); `bank_items is None` =
bank never visited (NOT room). Distinct from the `bank_capacity == 0` divide-
guard in BANK_EXPAND. Mirrors `Formal.Liveness.ProductionLadder.bankHasRoom`."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState


def bank_has_room(state: WorldState, game_data: GameData,
                  ctx: SelectionContext) -> bool:
    if not ctx.bank_accessible:
        return False
    if state.bank_items is None or game_data.bank_capacity is None:
        return False
    return len(state.bank_items) < game_data.bank_capacity

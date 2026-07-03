"""Empty-slot Rank fills: the best owned item per currently-empty slot."""

from artifactsmmo_cli.ai.equipment.loadout_picker import pick_loadout
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_value_core import Rank
from artifactsmmo_cli.ai.world_state import WorldState


def empty_slot_rank_fills(state: WorldState, game_data: GameData,
                          reserved: frozenset[str]) -> dict[str, str]:
    """{slot: code} for each currently-empty slot the owned pool can fill with a
    strictly-positive-Rank item, excluding reserved item codes.

    Reuses ``pick_loadout(Rank)``'s proven realizability / one-slot-per-code
    (Formal.RealizableLoadout), then keeps only slots that are EMPTY in the live
    equipment (never displaces an incumbent — that is UpgradeEquipment's job) and
    whose chosen code is not RESERVED for the active task/craft pipeline. The
    empty-slot gate inside ``pick_loadout`` already discards zero/negative-Rank
    fills, so every code here carries strictly-positive Rank value.
    """
    picked = pick_loadout(Rank, state, game_data)
    return {
        slot: code
        for slot, code in picked.items()
        if state.equipment.get(slot) is None and code is not None and code not in reserved
    }

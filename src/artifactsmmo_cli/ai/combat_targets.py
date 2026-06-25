# src/artifactsmmo_cli/ai/combat_targets.py
# combat_targets

"""The winnable near-level monster set used to keep situationally-best gear.

Memoized single-entry on `(id(game_data), character level, equipment signature)`
because the dominance check that consumes it runs per inventory item. `is_winnable`
is called with `history=None` (cold/stat beatability) — the keep decision uses the
optimistic prediction, not the learned-loss veto, matching how planning calls it."""

from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState

LEVEL_BAND_BELOW = 5
"""A monster whose level is at least `character level - LEVEL_BAND_BELOW` counts as
one we might fight; the upper end is the beatability frontier (`is_winnable`)."""

_cache: dict[str, object] = {}


def _clear_cache() -> None:
    """Reset the single-entry memo (test hook; also harmless in production)."""
    _cache.clear()


def combat_target_monsters(state: WorldState, game_data: GameData) -> list[str]:
    """Codes of winnable monsters at or above `level - LEVEL_BAND_BELOW`."""
    equip_sig = tuple(sorted(c for c in state.equipment.values() if c is not None))
    key = (id(game_data), state.level, equip_sig)
    if _cache.get("key") == key:
        return _cache["val"]  # type: ignore[return-value]
    floor = state.level - LEVEL_BAND_BELOW
    out = [code for code, level in game_data.monster_levels.items()
           if level >= floor and is_winnable(state, game_data, code, None)]
    _cache["key"] = key
    _cache["val"] = out
    return out

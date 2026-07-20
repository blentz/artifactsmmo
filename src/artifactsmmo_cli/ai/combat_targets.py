# src/artifactsmmo_cli/ai/combat_targets.py
# combat_targets

"""The winnable near-level monster set used to keep situationally-best gear.

Memoized single-entry on a WEAKREF to game_data plus (character level, equipment
signature, active event codes) because the dominance check that consumes it runs
per inventory item. Identity is a weakref compared with `is`, never `id()`: CPython
reuses the address of a collected object, so an id-keyed entry could be hit by a
different GameData that happened to land there. `is_winnable`
is called with `history=None` (cold/stat beatability) — the keep decision uses the
optimistic prediction, not the learned-loss veto, matching how planning calls it."""

from weakref import ReferenceType, ref

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
    """Codes of REACHABLE winnable monsters at or above `level - LEVEL_BAND_BELOW`.

    `monster_levels` is the full catalog, which includes event-only monsters and
    raid bosses. 14 of the 58 monsters in the committed bundle have no static map
    tile at all -- among them the raid bosses `pixie` and `sonnengott`, which no
    action can ever target because `factory.py` only emits a `FightAction` per
    entry of `all_monster_locations`. Without the spawn gate this helper returned
    them, and `potion_supply.primary_combat_target` delegates here, so potion
    stocking could size itself against a fight that can never happen.

    The gate keys on REACHABILITY, not on being event content: `monster_spawn_known`
    is event-aware, so an event monster counts while its event runs and drops out
    when it ends. Filtering event content wholesale would undo the event-visibility
    work that deliberately made those monsters fightable.
    """
    equip_sig = tuple(sorted(c for c in state.equipment.values() if c is not None))
    # active_event_codes is part of the read-set: `monster_spawn_known` consults it,
    # and the player mutates it on the SAME GameData object every cycle
    # (player.py:1275). Keying only on identity would serve the pre-event answer
    # for the rest of the run.
    key = (state.level, equip_sig, frozenset(game_data.active_event_codes))
    # Identity is held as a WEAKREF and compared with `is`, never as id().
    # CPython reuses the id of a collected object, so an id-keyed entry could be
    # hit by a DIFFERENT GameData that happened to land on the same address --
    # observed as an intermittent cross-test failure (test_tiers_guards's
    # craft_potions guard, twice, passing in isolation every time). A weakref
    # cannot alias: once the original dies the ref reads None and the entry misses.
    cached_ref = _cache.get("gd_ref")
    if (isinstance(cached_ref, ReferenceType) and cached_ref() is game_data
            and _cache.get("key") == key):
        cached_val = _cache["val"]
        if isinstance(cached_val, list):
            return list(cached_val)
    floor = state.level - LEVEL_BAND_BELOW
    out = [code for code, level in game_data.monster_levels.items()
           if level >= floor
           and game_data.monster_spawn_known(code)
           and is_winnable(state, game_data, code, None)]
    _cache["gd_ref"] = ref(game_data)
    _cache["key"] = key
    _cache["val"] = out
    return list(out)

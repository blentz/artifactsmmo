"""The prospecting a drop's chance is read at: that of the loadout the attempt
is made in (spec 2026-10-18 §2.8, ruling T12n).

`pick_loadout` picks the loadout for the attempt's purpose from what the state
owns, and `project_loadout_stats` projects its prospecting as a swap (an item's
prospecting in, the one it displaces out). The executor wears that loadout for
the attempt: a fight is gated on it (`FightAction.is_applicable`), a gather
re-arms into it (`GatherAction.cost` charges the wrong tool until it does).

The state's own total, `state.prospecting`, is the worn gear's: read before
the swap, it is not the attempt's (Task 14d census of ledger 253 (b)). The
acquisition walk and the drop-fight picker read this module. The planner's
gather and the gather source pickers still read the worn total: unlike the
walk, they admit a resource with no gathering skill (`GatherAction.cost`'s
no-tool-preference branch), which `gather_prospecting` refuses.

Pure functions over the state and the catalogue, in their own module because
the source pickers sit below `acquisition_cost` in the import graph.
"""

from artifactsmmo_cli.ai.equipment.loadout_cache import pick_loadout_cached
from artifactsmmo_cli.ai.equipment.projection import project_loadout_stats
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_value_core import Combat, Gather
from artifactsmmo_cli.ai.world_state import WorldState


def loadout_prospecting(purpose: Combat | Gather, state: WorldState,
                        game_data: GameData) -> int:
    """The prospecting the loadout `pick_loadout` picks for `purpose` from
    what `state` owns carries, projected as a swap: the `P` a drop's chance is
    read at, and the ONE basis every drop price uses (ruling T12n)."""
    loadout = pick_loadout_cached(purpose, state, game_data)
    return project_loadout_stats(state, loadout, game_data).prospecting


def fight_prospecting(monster_code: str, state: WorldState, game_data: GameData) -> int:
    """`loadout_prospecting` for a fight against `monster_code`: the `Combat`
    purpose the fight's loadout gate reads."""
    return loadout_prospecting(Combat(game_data.monster_attack(monster_code),
                                      game_data.monster_resistance(monster_code),
                                      dict(state.attack)), state, game_data)


def gather_prospecting(resource: str, state: WorldState, game_data: GameData) -> int:
    """`loadout_prospecting` for a gather at `resource`: the `Gather` purpose
    of its skill. A resource with no skill in the catalogue RAISES: API data or
    fail."""
    requirement = game_data.resource_skill_level(resource)
    if requirement is None:
        raise ValueError(f"resource {resource!r} has no gathering skill in game data")
    return loadout_prospecting(Gather(requirement[0]), state, game_data)

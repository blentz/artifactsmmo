"""Marginal winnability of OWNING a weapon — the predict_win-aware weapon signal.

`equip_value` ranks a weapon by a damage-type-BLIND stat sum. Live on Robby it
targeted `fire_bow` (equip_value 105, attack fire 17) over the equipped
`copper_axe` (equip_value 10, attack earth 5) even though the local monsters
resist fire and copper_axe beats MORE of them — the bot ground weaponcrafting to
craft a COMBAT DOWNGRADE.

`predict_win` / `pick_loadout` is already damage-optimal PER MONSTER (it picks the
best owned weapon for each monster's resistances — proven in
`Formal/PurposeRouting.lean`). So the honest signal for "is this weapon worth
acquiring" is MARGINAL: does OWNING it let the character beat monsters it cannot
beat now? A weapon with zero marginal winnability (fire_bow on Robby) is never
worth grinding toward, whatever its `equip_value`.

`predict_win` is a runtime combat SIMULATION; it cannot live inside the
Lean-mirrored, pure `equip_value` / `kit_selection` cores. This helper sits beside
them and is verified by unit tests + the runtime check, not by Lean.
"""

import dataclasses

from artifactsmmo_cli.ai.combat import predict_win
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


def beatable_count(state: WorldState, game_data: GameData) -> int:
    """How many monsters the character beats with its OWNED kit — `pick_loadout`
    (inside `predict_win`) picks the damage-optimal weapon per monster.

    Iterates the same monster set `combat_capable` does (`game_data.monster_levels`)
    so "reachable" matches the rest of the tier layer; a weapon that unlocks a
    not-yet-winnable monster therefore scores a positive marginal below."""
    return sum(1 for code in game_data.monster_levels
               if predict_win(state, game_data, code))


def marginal_weapon_winnability(code: str, state: WorldState,
                                game_data: GameData) -> int:
    """`beatable_count(kit + code) - beatable_count(kit)`.

    `> 0` iff OWNING `code` lets the character beat at least one monster it cannot
    beat now. `code` is added to a COPY of the inventory; it is NOT forced into the
    weapon slot — `pick_loadout` decides per monster whether it is the best weapon
    for that fight, so a weapon that helps only against fire-weak monsters still
    scores its true marginal without displacing the earth weapon elsewhere."""
    with_code = dict(state.inventory)
    with_code[code] = with_code.get(code, 0) + 1
    added = dataclasses.replace(state, inventory=with_code)
    return beatable_count(added, game_data) - beatable_count(state, game_data)

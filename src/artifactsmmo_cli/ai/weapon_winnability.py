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
from collections import OrderedDict

from artifactsmmo_cli.ai.combat import predict_win
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState

_MEMO: "OrderedDict[tuple[object, ...], int]" = OrderedDict()
_MEMO_MAX = 4096


BAND_MARGIN = 5
"""Monsters more than this many levels ABOVE the character are out of band: a
weapon is judged on whether it helps against fights the character would actually
take, not level-40 bosses it cannot reach. Also bounds the `predict_win` scan
(the expensive `pick_loadout` per monster) to the reachable band — the full
table is ~100 monsters, the band is a handful, and this runs every gear
decision."""


def _band_monsters(state: WorldState, game_data: GameData) -> list[str]:
    """Monster codes within the character's reachable band (level <= char level +
    BAND_MARGIN). Sorted for a deterministic scan/fingerprint."""
    return sorted(code for code, level in game_data.monster_levels.items()
                  if level <= state.level + BAND_MARGIN)


def _combat_fingerprint(state: WorldState, game_data: GameData) -> tuple[object, ...]:
    """Everything `predict_win` / `project_loadout_stats` reads from `state` —
    the owned candidate pool (inventory + equipment), current hp, and the
    projected combat stats — plus the GameData identity (process-stable). Any
    change that could alter `beatable_count` changes this key."""
    return (
        tuple(sorted((c, q) for c, q in state.inventory.items() if q > 0)),
        tuple(sorted((s, c) for s, c in state.equipment.items() if c)),
        state.hp, state.max_hp, state.level,
        state.dmg, state.critical_strike, state.initiative,
        tuple(sorted(state.attack.items())),
        tuple(sorted(state.dmg_elements.items())),
        tuple(sorted(state.resistance.items())),
        id(game_data),
    )


def beatable_count(state: WorldState, game_data: GameData) -> int:
    """How many monsters IN THE CHARACTER'S BAND the character beats with its
    OWNED kit — `pick_loadout` (inside `predict_win`) picks the damage-optimal
    weapon per monster.

    Restricted to `_band_monsters` (level <= char level + BAND_MARGIN): a weapon
    is judged on whether it helps against fights the character would actually take,
    and the scan stays cheap enough to run every gear decision. A weapon that
    unlocks a not-yet-winnable IN-BAND monster scores a positive marginal below;
    one that only helps against unreachable bosses (or nothing, like fire_bow)
    scores 0 and is not a grind target.

    MEMOIZED on the full combat fingerprint (`_combat_fingerprint`): `pick_loadout`
    is expensive and this runs every gear decision, but the kit rarely changes
    cycle-to-cycle, so the steady state is ~free. The result is computed from the
    REAL `state` (not a rebuilt template), so no field `predict_win` reads is
    lost; the fingerprint only decides cache identity."""
    key = _combat_fingerprint(state, game_data)
    hit = _MEMO.get(key)
    if hit is not None:
        _MEMO.move_to_end(key)
        return hit
    result = sum(1 for code in _band_monsters(state, game_data)
                 if predict_win(state, game_data, code))
    _MEMO[key] = result
    if len(_MEMO) > _MEMO_MAX:
        _MEMO.popitem(last=False)
    return result


def marginal_weapon_winnability(code: str, state: WorldState,
                                game_data: GameData) -> int:
    """`beatable_count(kit + code) - beatable_count(kit)`.

    `> 0` iff OWNING `code` lets the character beat at least one monster it cannot
    beat now. `code` is added to a COPY of the inventory; it is NOT forced into the
    weapon slot — `pick_loadout` decides per monster whether it is the best weapon
    for that fight, so a weapon that helps only against fire-weak monsters still
    scores its true marginal without displacing the earth weapon elsewhere.

    Evaluated at FULL HP. `predict_win` reads CURRENT hp (correct for "can I win
    THIS fight now"), but "is this weapon worth ACQUIRING" is a strategic question
    that must not flip to 0 merely because the character is momentarily hurt — a
    low-HP character would otherwise suppress every weapon target and never grind
    toward the weapon it needs once healed."""
    healthy = dataclasses.replace(state, hp=state.max_hp)
    with_code = dict(healthy.inventory)
    with_code[code] = with_code.get(code, 0) + 1
    added = dataclasses.replace(healthy, inventory=with_code)
    return beatable_count(added, game_data) - beatable_count(healthy, game_data)

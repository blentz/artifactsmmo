"""Cold-start seed for the expected total damage taken from a single fight.

Used to size potion provisioning before a monster has accumulated fight samples
in the learning store.  The computation reuses ``_expected_hit`` from
``combat.py`` so it cannot drift from the main ``predict_win`` damage model.
"""

import math

from artifactsmmo_cli.ai.combat import _expected_hit
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


def expected_damage_per_fight(
    state: WorldState, game_data: GameData, monster_code: str
) -> int:
    """Expected total damage taken from one fight against ``monster_code``.

    Returns 0 for an unknown or unkillable monster (caller won't fight).

    Mirrors ``predict_win``'s ``raw_monster`` (monster per-turn damage vs
    player resistance, scaled by monster crit) and ``rounds_to_kill``
    (ceiling of monster HP divided by the player's per-turn damage) via
    the same ``_expected_hit`` primitive — so the estimate cannot drift
    from the combat verdict's damage model.

    Uses the player's current equipped stats directly from ``state``; no
    loadout projection is performed.  Guard: ``game_data.monster_levels``
    returns 0 for unknown codes, so the membership check avoids calling
    the raising stat accessors.
    """
    if monster_code not in game_data.monster_levels:
        return 0
    m_attack = game_data.monster_attack(monster_code)
    m_resist = game_data.monster_resistance(monster_code)
    m_hp = game_data.monster_hp(monster_code)
    m_crit = game_data.monster_critical_strike(monster_code)
    monster_per_turn = _expected_hit(m_attack, 0, {}, state.resistance, m_crit)
    player_kill_step = _expected_hit(
        state.attack, state.dmg, state.dmg_elements, m_resist, state.critical_strike
    )
    if player_kill_step <= 0:
        return 0
    rounds_to_kill = math.ceil(m_hp / player_kill_step)
    return round(monster_per_turn) * rounds_to_kill

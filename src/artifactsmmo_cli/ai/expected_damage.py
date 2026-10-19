"""Cold-start seed for the expected total damage taken from a single fight.

Used to size potion provisioning before a monster has accumulated fight samples
in the learning store.  The computation reuses ``_expected_hit`` from
``combat.py`` so it cannot drift from the main ``predict_win`` damage model.
"""

from artifactsmmo_cli.ai.combat import _expected_hit, moves_first
from artifactsmmo_cli.ai.equipment.loadout_cache import pick_loadout_cached
from artifactsmmo_cli.ai.equipment.projection import project_loadout_stats
from artifactsmmo_cli.ai.fight_terms_core import MAX_TURNS, SCALE, kill_rounds
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_value_core import Combat
from artifactsmmo_cli.ai.world_state import WorldState


def expected_damage_per_fight(
    state: WorldState, game_data: GameData, monster_code: str
) -> int:
    """Expected total damage taken from one fight against ``monster_code``.

    Returns 0 for an unknown or unkillable monster (caller won't fight).

    Mirrors ``predict_win``'s ``raw_monster`` (monster per-turn damage vs
    player resistance, scaled by monster crit) and ``rounds_to_kill``
    (``fight_terms_core.kill_rounds``: the monster's HP behind its
    refreshing barrier, at the player's per-turn damage) via the same
    ``_expected_hit`` primitive — so the estimate cannot drift
    from the combat verdict's damage model.

    Judged against the loadout ``pick_loadout`` would actually equip, exactly as
    ``predict_win`` / ``combat_margin`` do — NOT the currently-worn gear. Using
    the worn stats made this seed disagree with the combat verdict it claims not
    to drift from: the bot asked "can I win?" wearing the best owned weapon and
    "how much will I bleed?" wearing whatever happened to be in the slot. Since
    ``projected_heal_need_per_fight`` sizes potion demand from this number, a
    stale weapon made a comfortably-won fight read MARGINAL and the CRAFT_POTIONS
    guard fired — brewing a 30-potion stack to survive a fight that equipping the
    bow already in the bag wins outright.

    The fight stops at ``MAX_TURNS``: a monster the player cannot kill by
    then lands at most ``MAX_TURNS`` hits, so the rounds are
    ``min(rounds_to_kill, MAX_TURNS)``. Uncapped, a 600,000-HP raid boss read
    2,933 rounds (1,844,857 damage). A kill step that rounds to 0 at ``SCALE``
    never kills, so it counts the whole ``MAX_TURNS``. The damage is NOT
    clamped at the fighter's HP: ``raid_survivable_pure`` reads "unsurvivable"
    from damage above the HP pool, and a clamp would hide it.

    Guard: ``game_data.monster_levels`` returns 0 for unknown codes, so the
    membership check avoids calling the raising stat accessors.
    """
    if monster_code not in game_data.monster_levels:
        return 0
    m_attack = game_data.monster_attack(monster_code)
    m_resist = game_data.monster_resistance(monster_code)
    m_hp = game_data.monster_hp(monster_code)
    m_crit = game_data.monster_critical_strike(monster_code)
    loadout = pick_loadout_cached(
        Combat(m_attack, m_resist, dict(state.attack)), state, game_data)
    p = project_loadout_stats(state, loadout, game_data)
    monster_per_turn = _expected_hit(m_attack, 0, {}, p.resistance, m_crit)
    player_kill_step = _expected_hit(
        p.attack, p.dmg, p.dmg_elements, m_resist, p.critical_strike
    )
    if player_kill_step <= 0:
        return 0
    first = moves_first(p.initiative, state.hp, game_data.monster_initiative(monster_code), m_hp)
    kill_step = round(player_kill_step * SCALE)
    if kill_step == 0:
        return round(monster_per_turn) * MAX_TURNS
    rounds_to_kill = kill_rounds(m_hp, game_data.monster_barrier(monster_code),
                                 kill_step, first)
    return round(monster_per_turn) * min(rounds_to_kill, MAX_TURNS)

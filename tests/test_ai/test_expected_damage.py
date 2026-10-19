"""Tests for the expected_damage_per_fight cold-start seed."""

import math
from pathlib import Path

import pytest

import artifactsmmo_cli.ai.expected_damage as expected_damage
from artifactsmmo_cli.ai.combat import _expected_hit
from artifactsmmo_cli.ai.equipment.loadout_cache import pick_loadout_cached
from artifactsmmo_cli.ai.equipment.projection import project_loadout_stats
from artifactsmmo_cli.ai.expected_damage import expected_damage_per_fight
from artifactsmmo_cli.ai.fight_terms_core import MAX_TURNS, SCALE
from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.gear_value_core import Combat
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from tests.test_ai.fixtures import make_state
from tests.test_ai.shared_world import shared_world
from tests.test_ai.test_combat import _gd

BUNDLE = Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json"


def test_expected_damage_exact_for_winnable_monster():
    """Damage equals round(monster_per_turn) * rounds_to_kill, computed from
    the same _expected_hit primitive as predict_win.

    Fixture: monster has 30 HP and 10 fire attack; player has 50 fire attack.
      monster_per_turn = _expected_hit({"fire": 10}, 0, {}, {}, 0) = 10.0
      player_kill_step = _expected_hit({"fire": 50}, 0, {}, {}, 0) = 50.0
      rounds_to_kill   = ceil(30 / 50.0) = 1
      result           = round(10.0) * 1 = 10
    """
    gd = _gd(hp=30, attack={"fire": 10}, code="slime")
    gd._monster_level = {"slime": 1}
    state = make_state(level=5, hp=200, max_hp=200, attack={"fire": 50})
    monster_per_turn = _expected_hit({"fire": 10}, 0, {}, {}, 0)
    player_kill_step = _expected_hit({"fire": 50}, 0, {}, {}, 0)
    rounds_to_kill = math.ceil(30 / player_kill_step)
    expected = round(monster_per_turn) * rounds_to_kill
    assert expected_damage_per_fight(state, gd, "slime") == expected


def test_expected_damage_counts_the_hits_behind_the_barrier():
    """50 a hit into 300 HP behind a 100 barrier refreshed every 5 monster
    turns (`kill_rounds`): the player, moving first, gets 150 through its first
    5 hits and 150 through the next 5 — 10 rounds, not the 6 HP alone takes."""
    gd = _gd(hp=300, attack={"fire": 10}, code="slime", barrier=100)
    gd._monster_level = {"slime": 1}
    state = make_state(level=5, hp=200, max_hp=200, attack={"fire": 50}, initiative=10)
    assert expected_damage_per_fight(state, gd, "slime") == 10 * 10


def test_expected_damage_zero_when_unknown_monster():
    """An unknown monster code returns 0 (caller won't fight it)."""
    gd = _gd(hp=30, code="slime")
    # "ghost" is not in gd._monster_level (never set) -> monster_levels is empty
    assert expected_damage_per_fight(make_state(), gd, "ghost") == 0


def test_expected_damage_zero_when_player_cannot_damage():
    """A player dealing 0 damage cannot kill the monster; return 0."""
    gd = _gd(hp=30, attack={"fire": 5}, code="mob")
    gd._monster_level = {"mob": 1}
    # make_state with no attack kwarg -> state.attack = {} -> player_kill_step = 0
    state = make_state(level=5, hp=100, max_hp=100)
    assert expected_damage_per_fight(state, gd, "mob") == 0


def test_expected_damage_uses_the_loadout_the_bot_would_equip():
    """A better weapon SITTING IN THE BAG must count.

    `predict_win` / `combat_margin` judge winnability against
    `pick_loadout`'s best-attainable loadout, but this seed used the CURRENTLY
    equipped stats — so the bot asked "can I win?" wearing the good weapon and
    "how much will I bleed?" wearing the stale one. Because
    `projected_heal_need_per_fight` sizes potion demand from this number, a
    stale weapon slot made a comfortably-winnable fight read MARGINAL and the
    CRAFT_POTIONS guard fired: the bot brewed a 30-potion stack to survive a
    fight that equipping the bow already in its bag wins outright
    (tests/test_ai/scenarios/test_fight_loadout_swap.py pins the swap-first
    behaviour this broke).

    Identical character; the ONLY difference is which weapon is in the slot
    versus the bag. Both must project the same damage.
    """
    gd = _gd(hp=300, attack={"fire": 10}, code="brute")
    gd._monster_level = {"brute": 1}
    gd._item_stats = {
        "weak": ItemStats(code="weak", level=1, type_="weapon", attack={"fire": 5}),
        "strong": ItemStats(code="strong", level=1, type_="weapon", attack={"fire": 95}),
    }
    slots = make_state().equipment

    equipped = make_state(level=5, hp=200, max_hp=200, attack={"fire": 100},
                          equipment={**slots, "weapon_slot": "strong"}, inventory={})
    in_the_bag = make_state(level=5, hp=200, max_hp=200, attack={"fire": 10},
                            equipment={**slots, "weapon_slot": "weak"},
                            inventory={"strong": 1})

    assert expected_damage_per_fight(in_the_bag, gd, "brute") == \
        expected_damage_per_fight(equipped, gd, "brute")


def test_damage_never_exceeds_the_turn_cap(monkeypatch: pytest.MonkeyPatch):
    """A kill step that is positive but below 1/SCALE rounds to 0 at SCALE, so
    `kill_rounds` would divide by it. The fight is still unresolved at the turn
    cap (`MAX_TURNS`), so the monster hits for `MAX_TURNS` rounds and no more.

    The player's 10 water a hit is replaced by a step of 1/(2 x SCALE): integer
    stats cannot produce one (the smallest positive `_expected_hit` is 0.005),
    so the seam stands in for it. A 0 step is outside `kill_rounds`'
    contract (a positive step), so the guard answers before calling it."""
    gd = _gd(hp=30, attack={"fire": 10}, code="slime")
    gd._monster_level = {"slime": 1}
    state = make_state(level=5, hp=200, max_hp=200, attack={"water": 10})
    real = expected_damage._expected_hit

    def tiny_player_step(attack, dmg, dmg_elements, resist, crit):
        if attack.get("water", 0):
            return 1 / (2 * SCALE)
        return real(attack, dmg, dmg_elements, resist, crit)

    steps: list[int] = []
    real_rounds = expected_damage.kill_rounds

    def recording_rounds(monster_hp, barrier, kill_step, player_first):
        steps.append(kill_step)
        return real_rounds(monster_hp, barrier, kill_step, player_first)

    monkeypatch.setattr(expected_damage, "_expected_hit", tiny_player_step)
    monkeypatch.setattr(expected_damage, "kill_rounds", recording_rounds)
    monster_per_turn = _expected_hit({"fire": 10}, 0, {}, {}, 0)
    assert expected_damage_per_fight(state, gd, "slime") == round(monster_per_turn) * MAX_TURNS
    # `kill_rounds` takes a POSITIVE step: a 0 step never reaches it.
    assert steps == []


def test_pixie_on_the_l48_raid_sheet_is_bounded():
    """Pixie has 600,000 HP; the l48 raid sheet kills it in 2,933 rounds, so the
    uncapped estimate was 629 x 2,933 = 1,844,857. A fight unresolved by turn
    `MAX_TURNS` is over, so the monster lands at most `MAX_TURNS` hits."""
    gd = shared_world(BUNDLE)
    state = scenario_state(SCENARIOS["l48_raid_active"], gd)
    m_attack = gd.monster_attack("pixie")
    loadout = pick_loadout_cached(
        Combat(m_attack, gd.monster_resistance("pixie"), dict(state.attack)), state, gd)
    p = project_loadout_stats(state, loadout, gd)
    monster_per_turn = _expected_hit(m_attack, 0, {}, p.resistance,
                                     gd.monster_critical_strike("pixie"))
    assert expected_damage_per_fight(state, gd, "pixie") == round(monster_per_turn) * MAX_TURNS
    assert round(monster_per_turn) * MAX_TURNS == 62_900


def test_a_bare_fighter_with_no_damage_still_reads_zero():
    """The early exit holds: a fighter whose kill step is 0 never fights, so the
    turn cap does not turn its estimate into `MAX_TURNS` hits."""
    gd = _gd(hp=600_000, attack={"fire": 50}, code="boss")
    gd._monster_level = {"boss": 1}
    state = make_state(level=5, hp=100, max_hp=100)
    assert expected_damage_per_fight(state, gd, "boss") == 0

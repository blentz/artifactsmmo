"""Tests for the expected_damage_per_fight cold-start seed."""

import math

from artifactsmmo_cli.ai.combat import _expected_hit
from artifactsmmo_cli.ai.expected_damage import expected_damage_per_fight
from artifactsmmo_cli.ai.game_data import ItemStats
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_combat import _gd


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

"""Tests for unlock_boost_target selector."""

import dataclasses

import pytest

from artifactsmmo_cli.ai import unlock_boost as _unlock_boost_module
from artifactsmmo_cli.ai.combat import predict_win
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.unlock_boost import _is_craftable_boost, unlock_boost_target
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


@pytest.fixture(autouse=True)
def clear_unlock_boost_cache():
    """Clear the module-level single-entry cache before and after each test.

    The cache in unlock_boost keyed (level, equip_sig, owned) does NOT include
    id(game_data), so a stale result from a previous test using a different
    GameData with the same key shape would produce wrong results. Clearing the
    cache per test removes that risk entirely."""
    _unlock_boost_module._cache.clear()
    yield
    _unlock_boost_module._cache.clear()


def _gd_unlock():
    gd = GameData()
    gd._monster_level = {"mob": 30, "weak": 26}
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {"mob": 800, "weak": 50}
    gd._monster_attack = {"mob": {"fire": 30}, "weak": {"fire": 5}}
    gd._monster_resistance = {"mob": {}, "weak": {}}
    gd._item_stats = {
        "wpn": ItemStats(code="wpn", level=30, type_="weapon", attack={"fire": 60}),
        "fire_boost_potion": ItemStats(code="fire_boost_potion", level=10, type_="utility",
                                       crafting_skill="alchemy", crafting_level=10,
                                       dmg_elements={"fire": 40}, combat_buff=40),
        "small_health_potion": ItemStats(code="small_health_potion", level=5, type_="utility",
                                         crafting_skill="alchemy", crafting_level=5, hp_restore=30),
    }
    gd._crafting_recipes = {"fire_boost_potion": {"sunflower": 3}, "small_health_potion": {"sunflower": 1}}
    return gd


def _state_stalled():
    return make_state(level=30, hp=300, max_hp=300, attack={"fire": 60},
                      equipment={"weapon_slot": "wpn"}, inventory={},
                      skills={"alchemy": 20, "mining": 1, "woodcutting": 1, "fishing": 1,
                              "weaponcrafting": 1, "gearcrafting": 1, "jewelrycrafting": 1, "cooking": 1})


def _gd_three_mobs():
    """Three in-band monsters (all level >= 25), all non-winnable bare, all flipped by
    fire_boost_potion (dmg_elements fire+40).

    Dict insertion order: medium (xp=42) → hard (xp=48) → weak_mob (xp=28).
    This exercises every best_key branch inside unlock_boost_target:
      medium first  → best_key is None → True  → sets result
      hard second   → k < best_key (-48 < -42) → True  → updates result
      weak_mob last → k < best_key (-28 < -48) → False → result unchanged

    Expected winner: ("fire_boost_potion", "hard").

    XP derivation (char_level=30, penalty=1.0 when diff<5, else 0.7 when diff<10):
      hard   level=30, hp=700: raw=(30/30*20 + 700*0.04)=48.0, diff=0,  penalty=1.0 → 48
      medium level=27, hp=600: raw=(27/30*20 + 600*0.04)=42.0, diff=3,  penalty=1.0 → 42
      weak_mob level=25, hp=600: raw=(25/30*20+600*0.04)=40.7, diff=5, penalty=0.7 → 28

    Combat check (bare, player fire_attack=60, monster fire_attack=35):
      kill_step = 50*60*200=600_000
      rounds_to_kill = ceil(hp*10000/kill_step): hard=12, medium=10, weak_mob=10
      die_step  = 50*35*200=350_000
      rounds_to_die = ceil(300*10000/350_000)=9
      player_first (initiative 0>=0) → all: rounds_to_kill > rounds_to_die → LOSE bare ✓

    Combat check (with fire_boost_potion, raw_player=84):
      kill_step = 50*84*200=840_000
      rounds_to_kill: hard=9, medium=8, weak_mob=8
      rounds_to_die=9
      all: rounds_to_kill <= rounds_to_die → WIN with boost ✓
    """
    gd = GameData()
    gd._monster_level = {"medium": 27, "hard": 30, "weak_mob": 25}
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {"medium": 600, "hard": 700, "weak_mob": 600}
    gd._monster_attack = {"medium": {"fire": 35}, "hard": {"fire": 35}, "weak_mob": {"fire": 35}}
    gd._monster_resistance = {"medium": {}, "hard": {}, "weak_mob": {}}
    gd._item_stats = {
        "wpn": ItemStats(code="wpn", level=30, type_="weapon", attack={"fire": 60}),
        "fire_boost_potion": ItemStats(code="fire_boost_potion", level=10, type_="utility",
                                       crafting_skill="alchemy", crafting_level=10,
                                       dmg_elements={"fire": 40}, combat_buff=40),
    }
    gd._crafting_recipes = {"fire_boost_potion": {"sunflower": 3}}
    return gd


# ===========================================================================
# Tests for unlock_boost_target
# ===========================================================================

def test_unlock_returns_boost_and_monster_when_boost_flips_win():
    """Basic case: only mob in-band, non-winnable bare, fire_boost_potion flips it."""
    gd, st = _gd_unlock(), _state_stalled()
    # remove "weak" so only "mob" is in-band (ensures no bare-winnable monster)
    del gd._monster_level["weak"]
    gd._monster_attack.pop("weak", None)
    gd._monster_hp.pop("weak", None)
    gd._monster_resistance.pop("weak", None)
    # bare: mob unwinnable; with fire_boost_potion owned -> winnable
    assert predict_win(st, gd, "mob") is False
    assert unlock_boost_target(st, gd) == ("fire_boost_potion", "mob")


def test_unlock_none_when_a_monster_already_winnable():
    """'weak' is bare-winnable → not stalled → selector returns None (never over-crafts)."""
    gd, st = _gd_unlock(), _state_stalled()
    assert predict_win(st, gd, "weak") is True
    assert unlock_boost_target(st, gd) is None


def test_unlock_skips_heal_potions_and_uncraftable_boosts():
    """Heal potion is filtered; alchemy=5 gates fire_boost_potion (needs 10) → None."""
    gd, st = _gd_unlock(), _state_stalled()
    del gd._monster_level["weak"]
    gd._monster_attack.pop("weak", None)
    gd._monster_hp.pop("weak", None)
    st2 = dataclasses.replace(st, skills={**st.skills, "alchemy": 5})  # can't craft L10 boost
    assert unlock_boost_target(st2, gd) is None  # boost skill-gated, heal doesn't flip


def test_unlock_returns_none_when_boost_does_not_flip():
    """Craftable boost exists and is skill-unlocked, but doesn't flip the monster.

    Covers the inner predict_win(owned_state, ...) → False branch.

    iron_golem (hp=2000, fire_attack=100) vs char (hp=300, fire_attack=60):
      bare:  rounds_to_kill=34, rounds_to_die=3  → LOSE
      boost: raw_player=84, rounds_to_kill=24    → still LOSE (24>3)
    """
    gd = GameData()
    gd._monster_level = {"iron_golem": 30}
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {"iron_golem": 2000}
    gd._monster_attack = {"iron_golem": {"fire": 100}}
    gd._monster_resistance = {"iron_golem": {}}
    gd._item_stats = {
        "wpn": ItemStats(code="wpn", level=30, type_="weapon", attack={"fire": 60}),
        "fire_boost_potion": ItemStats(code="fire_boost_potion", level=10, type_="utility",
                                       crafting_skill="alchemy", crafting_level=10,
                                       dmg_elements={"fire": 40}, combat_buff=40),
    }
    gd._crafting_recipes = {"fire_boost_potion": {"sunflower": 3}}
    st = _state_stalled()
    owned_state = dataclasses.replace(st, inventory={"fire_boost_potion": 1})
    assert predict_win(st, gd, "iron_golem") is False
    assert predict_win(owned_state, gd, "iron_golem") is False
    assert unlock_boost_target(st, gd) is None


def test_unlock_picks_highest_xp_monster():
    """Three monsters all flipped by fire_boost_potion; selector picks the highest-XP one.

    See _gd_three_mobs() docstring for detailed combat/XP derivations.
    Dict order medium→hard→weak_mob exercises all best_key branches:
      • best_key is None → True  (medium, xp=42 sets initial best)
      • k < best_key → True      (hard, xp=48 beats medium → updates result)
      • k < best_key → False     (weak_mob, xp=28 < 48 → result unchanged)
    """
    gd = _gd_three_mobs()
    st = _state_stalled()
    # all three non-winnable bare
    assert predict_win(st, gd, "hard") is False
    assert predict_win(st, gd, "medium") is False
    assert predict_win(st, gd, "weak_mob") is False
    # all flipped by fire_boost_potion
    owned_state = dataclasses.replace(st, inventory={"fire_boost_potion": 1})
    assert predict_win(owned_state, gd, "hard") is True
    assert predict_win(owned_state, gd, "medium") is True
    assert predict_win(owned_state, gd, "weak_mob") is True
    # xp ordering: hard (48) > medium (42) > weak_mob (28)
    assert gd.xp_per_kill("hard", st.level) > gd.xp_per_kill("medium", st.level) > gd.xp_per_kill("weak_mob", st.level)
    # selector picks the highest-XP monster
    assert unlock_boost_target(st, gd) == ("fire_boost_potion", "hard")


def test_unlock_cache_hit_returns_same_result():
    """Second call with identical key hits the single-entry cache and returns same result."""
    gd, st = _gd_unlock(), _state_stalled()
    del gd._monster_level["weak"]
    gd._monster_attack.pop("weak", None)
    gd._monster_hp.pop("weak", None)
    gd._monster_resistance.pop("weak", None)
    first = unlock_boost_target(st, gd)
    second = unlock_boost_target(st, gd)
    assert first == second == ("fire_boost_potion", "mob")


# ===========================================================================
# Tests for _is_craftable_boost branches
# ===========================================================================

def test_is_craftable_boost_rejects_unknown_item():
    """item_stats returns None → branch 1a → False."""
    gd = GameData()
    gd._item_stats = {}
    assert _is_craftable_boost("unknown", _state_stalled(), gd) is False


def test_is_craftable_boost_rejects_non_utility():
    """type_ != 'utility' → branch 1b → False."""
    gd = GameData()
    gd._item_stats = {"iron_blade": ItemStats(code="iron_blade", level=1, type_="weapon",
                                               attack={"fire": 20})}
    assert _is_craftable_boost("iron_blade", _state_stalled(), gd) is False


def test_is_craftable_boost_rejects_heal_potion():
    """hp_restore > 0 → branch 1c → False (Phase-1 economy owns heals)."""
    gd = GameData()
    gd._item_stats = {"small_health_potion": ItemStats(code="small_health_potion", level=5,
                                                        type_="utility", crafting_skill="alchemy",
                                                        crafting_level=5, hp_restore=30)}
    assert _is_craftable_boost("small_health_potion", _state_stalled(), gd) is False


def test_is_craftable_boost_rejects_utility_without_boost_properties():
    """has_boost=False (no dmg_elements, resistance, hp_bonus, antipoison, combat_buff) → branch 2a → False."""
    gd = GameData()
    gd._item_stats = {"plain_util": ItemStats(code="plain_util", level=1, type_="utility",
                                               crafting_skill="alchemy", crafting_level=1)}
    assert _is_craftable_boost("plain_util", _state_stalled(), gd) is False


def test_is_craftable_boost_rejects_boost_with_no_crafting_skill():
    """has_boost=True but crafting_skill=None → branch 2b → False (not craftable)."""
    gd = GameData()
    gd._item_stats = {"wild_boost": ItemStats(code="wild_boost", level=1, type_="utility",
                                               crafting_skill=None, dmg_elements={"fire": 10})}
    assert _is_craftable_boost("wild_boost", _state_stalled(), gd) is False


def test_is_craftable_boost_true_when_skill_sufficient():
    """All conditions satisfied and skill >= crafting_level → True."""
    gd = GameData()
    gd._item_stats = {"fire_boost_potion": ItemStats(code="fire_boost_potion", level=10,
                                                      type_="utility", crafting_skill="alchemy",
                                                      crafting_level=10, dmg_elements={"fire": 40})}
    assert _is_craftable_boost("fire_boost_potion", _state_stalled(), gd) is True


def test_is_craftable_boost_false_when_skill_insufficient():
    """All conditions satisfied but skill < crafting_level → False."""
    gd = GameData()
    gd._item_stats = {"fire_boost_potion": ItemStats(code="fire_boost_potion", level=10,
                                                      type_="utility", crafting_skill="alchemy",
                                                      crafting_level=10, dmg_elements={"fire": 40})}
    st = dataclasses.replace(_state_stalled(), skills={**_state_stalled().skills, "alchemy": 5})
    assert _is_craftable_boost("fire_boost_potion", st, gd) is False

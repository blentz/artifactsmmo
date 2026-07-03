"""Tests for best_boost_potion selection core (Task 3).

Each test is non-vacuous: the losing candidate exists and is craftable;
only gain or craftability differs between winner and loser.

Monster fixtures use fill_monster_stat_defaults to satisfy the KeyError-on-unknown
invariant of the production monster catalog.

Math spot-check (fire_mob scenario):
  monster HP=100, attack={"fire":10}, resistance={}, crit=0, initiative=0
  player: attack={"fire":50}, max_hp=100, hp=100, initiative=1

  Baseline (no boost):
    raw_player = _element_damage(50, 0, 0) = 50
    kill_step  = 50*50*200 = 500000
    rounds_to_kill = ceil(1000000/500000) = 2
    raw_monster = _element_damage(10, 0, 0) = 10
    die_step   = 50*10*200 = 100000
    rounds_to_die = ceil(1000000/100000) = 10
    margin = 10 - 2 + 1 = 9

  With res_fire_potion (resistance={"fire":20}):
    raw_monster = _element_damage(10, 0, 20) = max(0, 10-2) = 8
    die_step = 50*8*200 = 80000
    rounds_to_die = ceil(1000000/80000) = ceil(12.5) = 13
    margin = 13 - 2 + 1 = 12  -> gain = +3

  With dmg_earth_potion (dmg_elements={"earth":30}):
    player has no earth attack -> raw_player unchanged = 50 -> margin = 9 -> gain = 0
"""

from artifactsmmo_cli.ai.boost_selection import best_boost_potion
from artifactsmmo_cli.ai.combat import WIN_MARGIN
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

_ALCHEMY_SKILLS = {
    "mining": 1, "woodcutting": 1, "fishing": 1,
    "weaponcrafting": 1, "gearcrafting": 1, "jewelrycrafting": 1,
    "cooking": 1, "alchemy": 1,
}


def _gd_fire_mob() -> GameData:
    """GameData: one fire-attacking monster + two boost potions."""
    gd = GameData()
    gd._monster_level = {"fire_mob": 5}
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {"fire_mob": 100}
    gd._monster_attack = {"fire_mob": {"fire": 10}}
    gd._monster_resistance = {"fire_mob": {}}
    gd._item_stats = {
        "res_fire_potion": ItemStats(
            code="res_fire_potion", level=1, type_="utility",
            crafting_skill="alchemy", crafting_level=1,
            resistance={"fire": 20},
        ),
        "dmg_earth_potion": ItemStats(
            code="dmg_earth_potion", level=1, type_="utility",
            crafting_skill="alchemy", crafting_level=1,
            dmg_elements={"earth": 30},
        ),
    }
    gd._crafting_recipes = {
        "res_fire_potion": {"sunflower": 1},
        "dmg_earth_potion": {"nettle": 1},
    }
    gd._resource_drops = {}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._npc_stock = {}
    gd._npc_sell_prices = {}
    gd._npc_locations = {}
    gd._bank_capacity = 20
    gd._next_expansion_cost = 500
    return gd


def _gd_resisty_mob() -> GameData:
    """GameData: one earth-resistant fire-attacking monster + two dmg boost potions."""
    gd = GameData()
    gd._monster_level = {"resisty_mob": 5}
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {"resisty_mob": 1000}
    gd._monster_attack = {"resisty_mob": {"fire": 5}}
    gd._monster_resistance = {"resisty_mob": {"earth": 50}}
    gd._item_stats = {
        "dmg_fire_potion": ItemStats(
            code="dmg_fire_potion", level=1, type_="utility",
            crafting_skill="alchemy", crafting_level=1,
            dmg_elements={"fire": 30},
        ),
        "dmg_earth_potion": ItemStats(
            code="dmg_earth_potion", level=1, type_="utility",
            crafting_skill="alchemy", crafting_level=1,
            dmg_elements={"earth": 30},
        ),
    }
    gd._crafting_recipes = {
        "dmg_fire_potion": {"mineral_oil": 1},
        "dmg_earth_potion": {"nettle": 1},
    }
    gd._resource_drops = {}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._npc_stock = {}
    gd._npc_sell_prices = {}
    gd._npc_locations = {}
    gd._bank_capacity = 20
    gd._next_expansion_cost = 500
    return gd


def _gd_weak_mob() -> GameData:
    """GameData: one attack-less monster + one res boost potion (zero gain)."""
    gd = GameData()
    gd._monster_level = {"weak_mob": 1}
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {"weak_mob": 10}
    gd._monster_attack = {"weak_mob": {}}
    gd._monster_resistance = {"weak_mob": {}}
    gd._item_stats = {
        "boost_res_fire": ItemStats(
            code="boost_res_fire", level=1, type_="utility",
            crafting_skill="alchemy", crafting_level=1,
            resistance={"fire": 20},
        ),
    }
    gd._crafting_recipes = {"boost_res_fire": {"sunflower": 1}}
    gd._resource_drops = {}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._npc_stock = {}
    gd._npc_sell_prices = {}
    gd._npc_locations = {}
    gd._bank_capacity = 20
    gd._next_expansion_cost = 500
    return gd


def _gd_tiebreak() -> GameData:
    """GameData: fire_mob + two potions with identical fire resistance effects."""
    gd = GameData()
    gd._monster_level = {"fire_mob": 5}
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {"fire_mob": 100}
    gd._monster_attack = {"fire_mob": {"fire": 10}}
    gd._monster_resistance = {"fire_mob": {}}
    gd._item_stats = {
        "aaa_boost": ItemStats(
            code="aaa_boost", level=1, type_="utility",
            crafting_skill="alchemy", crafting_level=1,
            resistance={"fire": 10},
        ),
        "bbb_boost": ItemStats(
            code="bbb_boost", level=1, type_="utility",
            crafting_skill="alchemy", crafting_level=1,
            resistance={"fire": 10},
        ),
    }
    gd._crafting_recipes = {
        "aaa_boost": {"herb_a": 1},
        "bbb_boost": {"herb_b": 1},
    }
    gd._resource_drops = {}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._npc_stock = {}
    gd._npc_sell_prices = {}
    gd._npc_locations = {}
    gd._bank_capacity = 20
    gd._next_expansion_cost = 500
    return gd


def _fire_mob_state(**overrides) -> object:
    """Player state: level 5, fire attack, initiative > monster (goes first)."""
    base = dict(
        level=5,
        hp=100,
        max_hp=100,
        attack={"fire": 50},
        resistance={},
        initiative=1,
        skills=_ALCHEMY_SKILLS,
    )
    base.update(overrides)
    return make_state(**base)


def _resisty_mob_state(**overrides) -> object:
    """Player state: both fire and earth attack."""
    base = dict(
        level=5,
        hp=100,
        max_hp=100,
        attack={"fire": 50, "earth": 50},
        resistance={},
        initiative=1,
        skills=_ALCHEMY_SKILLS,
    )
    base.update(overrides)
    return make_state(**base)


# ─── tests ───────────────────────────────────────────────────────────────────

def test_picks_boost_res_for_monster_attack_element():
    """Picks res_fire_potion (gain=+3) over dmg_earth_potion (gain=0) for
    a fire-attacking monster.  Non-vacuous: dmg_earth_potion exists and is
    craftable but yields zero gain (player has no earth attack)."""
    gd = _gd_fire_mob()
    state = _fire_mob_state()
    result = best_boost_potion(state, gd, "fire_mob")
    assert result == "res_fire_potion"


def test_picks_boost_dmg_for_least_resisted_element():
    """Picks dmg_fire_potion (larger gain) over dmg_earth_potion (smaller gain)
    for a monster that resists earth 50% but not fire.  Non-vacuous: earth
    boost exists, is craftable, but yields a smaller margin gain than fire."""
    gd = _gd_resisty_mob()
    state = _resisty_mob_state()
    result = best_boost_potion(state, gd, "resisty_mob")
    assert result == "dmg_fire_potion"


def test_skips_boost_not_craftable_now():
    """A boost that would help (res_fire_potion, resistance +20) but requires
    alchemy 30 is skipped when the character has only alchemy 10.
    Non-vacuous: the boost WOULD yield positive gain if craftable (the monster
    attacks fire), but the craftable-now gate rejects it."""
    gd = _gd_fire_mob()
    # Override crafting_level to 30 so char (alchemy=10) can't craft it
    gd._item_stats["res_fire_potion"] = ItemStats(
        code="res_fire_potion", level=1, type_="utility",
        crafting_skill="alchemy", crafting_level=30,
        resistance={"fire": 20},
    )
    gd._item_stats["dmg_earth_potion"] = ItemStats(
        code="dmg_earth_potion", level=1, type_="utility",
        crafting_skill="alchemy", crafting_level=30,
        dmg_elements={"earth": 30},
    )
    low_alchemy_skills = {**_ALCHEMY_SKILLS, "alchemy": 10}
    state = _fire_mob_state(skills=low_alchemy_skills)
    result = best_boost_potion(state, gd, "fire_mob")
    assert result is None


def test_none_when_no_boost_helps():
    """Returns None when every craftable boost yields zero (or negative) margin
    gain.  Setup: the monster has no attack (die_step=0 -> WIN_MARGIN already),
    so any boost leaves combat_margin unchanged at WIN_MARGIN — gain = 0, which
    is not strictly positive.  Non-vacuous: the boost exists and is craftable,
    only the gain is zero."""
    gd = _gd_weak_mob()
    state = make_state(
        level=5, hp=100, max_hp=100,
        attack={"fire": 5}, resistance={}, initiative=1,
        skills=_ALCHEMY_SKILLS,
    )
    # Player out-sustains weak_mob (no attack) -> baseline already WIN_MARGIN.
    # Any boost also gives WIN_MARGIN -> gain = WIN_MARGIN - WIN_MARGIN = 0.
    from artifactsmmo_cli.ai.combat import combat_margin
    baseline = combat_margin(state, gd, "weak_mob")
    assert baseline == WIN_MARGIN, "fixture sanity: player must already win by out-sustain"
    result = best_boost_potion(state, gd, "weak_mob")
    assert result is None


def test_deterministic_tiebreak_smallest_code():
    """Returns 'aaa_boost' (not 'bbb_boost') when both potions yield the same
    gain against the same monster.  Non-vacuous: bbb_boost exists and is
    craftable with identical stats; only the code name (lexicographic order)
    distinguishes them."""
    gd = _gd_tiebreak()
    state = _fire_mob_state()
    result = best_boost_potion(state, gd, "fire_mob")
    assert result == "aaa_boost"


def test_skips_non_utility_recipe_item():
    """boost_selection.py:123 continue — a recipe whose item is NOT type=="utility"
    (here type_=="weapon") is skipped.  The only craftable item is a weapon, so
    best_boost_potion returns None.

    Non-vacuous: the weapon recipe exists and is craftable at alchemy level 1;
    only the type_ field differs from a qualifying boost potion.
    """
    gd = _gd_fire_mob()
    # Replace both utility items with a weapon (non-utility).
    gd._item_stats["res_fire_potion"] = ItemStats(
        code="res_fire_potion", level=1, type_="weapon",
        crafting_skill="alchemy", crafting_level=1,
        resistance={"fire": 20},
    )
    gd._item_stats["dmg_earth_potion"] = ItemStats(
        code="dmg_earth_potion", level=1, type_="weapon",
        crafting_skill="alchemy", crafting_level=1,
        dmg_elements={"earth": 30},
    )
    state = _fire_mob_state()
    result = best_boost_potion(state, gd, "fire_mob")
    assert result is None


def test_skips_utility_item_without_crafting_skill():
    """boost_selection.py:127 continue — a utility item with crafting_skill=None
    (not craftable via any workshop) is skipped.  Non-vacuous: the item exists,
    has a boost effect (resistance), and would yield positive gain, but
    crafting_skill=None means it has no recipe gate to pass the craftable-now check.
    """
    gd = _gd_fire_mob()
    # Override res_fire_potion to have crafting_skill=None.
    gd._item_stats["res_fire_potion"] = ItemStats(
        code="res_fire_potion", level=1, type_="utility",
        crafting_skill=None, crafting_level=1,
        resistance={"fire": 20},
    )
    gd._item_stats["dmg_earth_potion"] = ItemStats(
        code="dmg_earth_potion", level=1, type_="utility",
        crafting_skill=None, crafting_level=1,
        dmg_elements={"earth": 30},
    )
    state = _fire_mob_state()
    result = best_boost_potion(state, gd, "fire_mob")
    assert result is None

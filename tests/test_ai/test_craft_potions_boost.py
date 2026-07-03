"""Tests for CraftPotionsGoal's unlock-boost path (post-pivot fold).

When leveling is stalled (no in-band monster bare-winnable) and a craftable
non-heal boost would flip one, CraftPotionsGoal should target that boost
instead of the heal path.  craft_potions_fires also fires on this condition.
"""

import pytest

from artifactsmmo_cli.ai import unlock_boost as _unlock_boost_module
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.craft_potions import CraftPotionsGoal
from artifactsmmo_cli.ai.potion_supply import craft_potions_fires
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

_BOOST = "fire_boost_potion"
_MOB = "mob"
_INGREDIENT = "sunflower"


@pytest.fixture(autouse=True)
def clear_unlock_boost_cache():
    """Clear the unlock_boost module-level single-entry cache before and after
    each test, preventing cross-test contamination (same key shape, different gd)."""
    _unlock_boost_module._cache.clear()
    yield
    _unlock_boost_module._cache.clear()


def _gd_stalled() -> GameData:
    """GameData with one unwinnable in-band monster (mob, lvl 30) and a
    craftable boost (fire_boost_potion) that flips it.  No heal potions —
    only the unlock path is active."""
    gd = GameData()
    gd._monster_level = {_MOB: 30}
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {_MOB: 800}
    gd._monster_attack = {_MOB: {"fire": 30}}
    gd._monster_resistance = {_MOB: {}}
    gd._item_stats = {
        "wpn": ItemStats(code="wpn", level=30, type_="weapon", attack={"fire": 60}),
        _BOOST: ItemStats(code=_BOOST, level=10, type_="utility",
                          crafting_skill="alchemy", crafting_level=10,
                          dmg_elements={"fire": 40}, combat_buff=40),
    }
    gd._crafting_recipes = {_BOOST: {_INGREDIENT: 3}}
    gd._resource_drops = {}
    gd._resource_locations = {}
    gd._workshop_locations = {"alchemy": (3, 0)}
    gd._npc_stock = {}
    gd._npc_sell_prices = {}
    gd._npc_locations = {}
    gd._bank_capacity = 20
    gd._next_expansion_cost = 500
    return gd


def _state_stalled(**kwargs):
    """Player level-30, bare-loses to mob (hp=800, fire_attack=30),
    holds 3 sunflowers (enough to craft 1 boost).
    attack={"fire": 60} is required by predict_win."""
    base = dict(
        level=30, hp=300, max_hp=300,
        attack={"fire": 60},
        equipment={"weapon_slot": "wpn"},
        inventory={_INGREDIENT: 3},
        skills={"alchemy": 20, "mining": 1, "woodcutting": 1, "fishing": 1,
                "weaponcrafting": 1, "gearcrafting": 1, "jewelrycrafting": 1, "cooking": 1},
    )
    base.update(kwargs)
    return make_state(**base)


# ── _active_craft / value (unlock path) ──────────────────────────────────────

def test_value_nonzero_when_stalled():
    """CraftPotionsGoal.value > 0 when an unlock boost is available."""
    gd = _gd_stalled()
    state = _state_stalled()
    goal = CraftPotionsGoal(game_data=gd)
    assert goal.value(state, gd) > 0


def test_value_zero_when_boost_owned():
    """Owning the boost makes player winnable → _active_craft returns None → value 0."""
    gd = _gd_stalled()
    state = _state_stalled(inventory={_BOOST: 1})
    goal = CraftPotionsGoal(game_data=gd)
    assert goal.value(state, gd) == 0.0


# ── is_satisfied (unlock path) ───────────────────────────────────────────────

def test_not_satisfied_when_stalled():
    """is_satisfied False when unlock boost is craftable (stall not broken)."""
    gd = _gd_stalled()
    state = _state_stalled()
    goal = CraftPotionsGoal(game_data=gd)
    assert goal.is_satisfied(state) is False


def test_satisfied_when_boost_owned():
    """Owning the boost in inventory makes predict_win True → unlock_boost_target
    returns None → _active_craft None (no heals in catalog) → is_satisfied True."""
    gd = _gd_stalled()
    state = _state_stalled(inventory={_BOOST: 1})
    goal = CraftPotionsGoal(game_data=gd)
    assert goal.is_satisfied(state) is True


# ── desired_state (unlock path) ──────────────────────────────────────────────

def test_desired_state_has_boost_when_stalled():
    """desired_state returns {have: {boost: 1}} for the unlock path."""
    gd = _gd_stalled()
    state = _state_stalled()
    goal = CraftPotionsGoal(game_data=gd)
    assert goal.desired_state(state, gd) == {"have": {_BOOST: 1}}


# ── relevant_actions (unlock path) ───────────────────────────────────────────

def test_relevant_actions_emits_craft_for_boost():
    """relevant_actions includes a CraftAction for the unlock boost."""
    gd = _gd_stalled()
    state = _state_stalled()
    goal = CraftPotionsGoal(game_data=gd)
    actions = [CraftAction(code=_BOOST, quantity=1, workshop_location=(3, 0))]
    out = goal.relevant_actions(actions, state, gd)
    assert any(isinstance(a, CraftAction) and a.code == _BOOST for a in out)


def test_relevant_actions_empty_when_boost_owned():
    """Once boost is owned, _active_craft returns None → empty action list."""
    gd = _gd_stalled()
    state = _state_stalled(inventory={_BOOST: 1})
    goal = CraftPotionsGoal(game_data=gd)
    assert goal.relevant_actions([], state, gd) == []


# ── craft_potions_fires unlock path ──────────────────────────────────────────

def test_craft_potions_fires_true_when_stalled():
    """craft_potions_fires returns True when an unlock boost is craftable (stalled)."""
    gd = _gd_stalled()
    state = _state_stalled()
    assert craft_potions_fires(state, gd) is True


def test_craft_potions_fires_false_when_no_unlock_and_no_heal():
    """When not stalled (boost owned) and no heal potions: guard quiet."""
    gd = _gd_stalled()
    state = _state_stalled(inventory={_BOOST: 1})
    assert craft_potions_fires(state, gd) is False

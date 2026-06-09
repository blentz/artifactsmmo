"""Tests for means_serves: does a discretionary means serve the objective's needs?"""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.means import MeansKind
from artifactsmmo_cli.ai.tiers.means_worth import means_serves
from artifactsmmo_cli.ai.tiers.objective_needs import NeedSet
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "cooked_gudgeon": ItemStats(code="cooked_gudgeon", level=1, type_="consumable",
                                    crafting_skill="cooking", crafting_level=1),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon",
                                crafting_skill="weaponcrafting", crafting_level=10),
    }
    gd._crafting_recipes = {"cooked_gudgeon": {"gudgeon": 1}, "iron_sword": {"iron_bar": 6}}
    return gd


def _weapon_needs() -> NeedSet:
    return NeedSet(materials=frozenset({"iron_bar"}),
                   skill_xp=frozenset({"weaponcrafting"}),
                   buy_only=frozenset(), char_xp=False)


def test_cooking_task_does_not_serve_weapon_objective():
    gd = _gd()
    state = make_state(task_type="items", task_code="cooked_gudgeon")
    assert means_serves(MeansKind.PURSUE_TASK, None, _weapon_needs(), state, gd) is False


def test_task_serves_when_its_skill_is_a_need():
    gd = _gd()
    state = make_state(task_type="items", task_code="cooked_gudgeon")
    needs = NeedSet(frozenset(), frozenset({"cooking"}), frozenset(), char_xp=False)
    assert means_serves(MeansKind.PURSUE_TASK, None, needs, state, gd) is True


def test_task_serves_when_it_produces_a_needed_material():
    gd = _gd()
    state = make_state(task_type="items", task_code="iron_bar")
    needs = NeedSet(frozenset({"iron_bar"}), frozenset(), frozenset(), char_xp=False)
    assert means_serves(MeansKind.PURSUE_TASK, None, needs, state, gd) is True


def test_task_serves_when_buy_only_need_and_task_yields_gold():
    gd = _gd()
    state = make_state(task_type="items", task_code="cooked_gudgeon")
    needs = NeedSet(frozenset(), frozenset(), frozenset({"magic_orb"}), char_xp=False)
    assert means_serves(MeansKind.PURSUE_TASK, None, needs, state, gd) is True


def test_empty_needs_passes_through():
    gd = _gd()
    state = make_state(task_type="items", task_code="cooked_gudgeon")
    empty = NeedSet(frozenset(), frozenset(), frozenset(), char_xp=False)
    assert means_serves(MeansKind.PURSUE_TASK, None, empty, state, gd) is True


def test_char_xp_only_need_rejects_items_task():
    gd = _gd()
    state = make_state(task_type="items", task_code="cooked_gudgeon")
    needs = NeedSet(frozenset(), frozenset(), frozenset(), char_xp=True)
    assert means_serves(MeansKind.PURSUE_TASK, None, needs, state, gd) is False


def test_non_task_means_pass_through():
    gd = _gd()
    state = make_state(task_type="items", task_code="cooked_gudgeon")
    assert means_serves(MeansKind.SELL_IDLE, None, _weapon_needs(), state, gd) is True
    assert means_serves(MeansKind.BANK_EXPAND, None, _weapon_needs(), state, gd) is True


def test_serves_when_a_non_first_gather_skill_is_needed():
    """A mixed-recipe gather task exercises several skills; a need on ANY of them
    (not just the alphabetically-first) makes the task serve."""
    gd = GameData()
    gd._item_stats = {"mixed_plank": ItemStats(code="mixed_plank", level=1, type_="resource")}
    gd._crafting_recipes = {"mixed_plank": {"ash_wood": 1, "iron_ore": 1}}
    gd._resource_drops = {"ash_tree": "ash_wood", "iron_rocks": "iron_ore"}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1), "iron_rocks": ("mining", 1)}
    state = make_state(task_type="items", task_code="mixed_plank")
    needs = NeedSet(frozenset(), frozenset({"woodcutting"}), frozenset(), char_xp=False)
    assert means_serves(MeansKind.PURSUE_TASK, None, needs, state, gd) is True


def test_monsters_task_serves_char_level_objective():
    """A monsters-task is combat → awards character XP → serves a char-level need."""
    gd = _gd()
    state = make_state(task_type="monsters", task_code="chicken")
    needs = NeedSet(frozenset(), frozenset(), frozenset(), char_xp=True)
    assert means_serves(MeansKind.PURSUE_TASK, None, needs, state, gd) is True

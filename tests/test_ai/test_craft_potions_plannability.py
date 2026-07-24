"""Planner-level plannability tests for CraftPotionsGoal.

Every other CraftPotionsGoal test asserts on the goal's own helpers
(`_target_potion`, `is_satisfied`, `relevant_actions`) in isolation. None of them
ever ran the REAL planner over the goal, and that is exactly how a goal that can
never be satisfied shipped: live traces showed the CRAFT_POTIONS guard firing on
442 cycles and the goal returning plan_len=0 on 285/285 planner selections
(nodes 54-65, depth 15, no timeout, no node cap — a genuinely exhausted search).

The defect both cases below pin is one shape: `GOAPPlanner.plan` evaluates
`goal.relevant_actions(...)` ONCE, against the SEED state, so the admitted action
set covers exactly one craft target sized to one batch — while `is_satisfied`
delegated to `_active_craft`, which re-targets as soon as the seed target's
deficit closes. A goal test that can demand something the frozen action set never
provides has no reachable satisfying state, so A* exhausts the space every time.
"""

import pytest

from artifactsmmo_cli.ai import unlock_boost as _unlock_boost_module
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.craft_potions import CraftPotionsGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

_HEAL = "small_health_potion"
_BOOST = "fire_boost_potion"
_INGREDIENT = "sunflower"
_RESOURCE = "sunflower_field"
_HURTS = "biting_slime"


@pytest.fixture(autouse=True)
def clear_unlock_boost_cache():
    """unlock_boost keeps a module-level single-entry cache; clear it so these
    fixtures cannot inherit another test's verdict under an equal-shaped key."""
    _unlock_boost_module._cache.clear()
    yield
    _unlock_boost_module._cache.clear()


def _gd(*, with_boost: bool, monster_level: int = 3) -> GameData:
    """Catalog with a gatherable-ingredient alchemy heal, a winnable-but-hurting
    monster (so potion stocking is combat-justified), and — when `with_boost` —
    a craftable damage boost for the SAME element the monster is weak to.

    `with_boost` is the only difference between the two catalogs. It is the axis
    that flips `best_boost_potion` from None to a real code, which is what
    activates `_active_craft`'s second clause.

    The monster's attack is tuned so the fight is WON but reads MARGINAL
    (`fight_is_marginal_pure`): a comfortably-won fight projects zero in-combat
    consumption, so the goal would correctly have nothing to do and the test
    would pass vacuously. `monster_level` keeps it inside the character's combat
    band so `primary_combat_target` selects it.
    """
    gd = GameData()
    stats = {
        _HEAL: ItemStats(code=_HEAL, level=1, type_="utility", hp_restore=30,
                         crafting_skill="alchemy", crafting_level=1),
        _INGREDIENT: ItemStats(code=_INGREDIENT, level=1, type_="resource"),
        "wpn": ItemStats(code="wpn", level=1, type_="weapon", attack={"fire": 150}),
    }
    recipes = {_HEAL: {_INGREDIENT: 1}}
    if with_boost:
        stats[_BOOST] = ItemStats(code=_BOOST, level=10, type_="utility",
                                  crafting_skill="alchemy", crafting_level=10,
                                  dmg_elements={"fire": 40}, combat_buff=40)
        recipes[_BOOST] = {_INGREDIENT: 3}
    gd._item_stats = stats
    gd._crafting_recipes = recipes
    gd._resource_drops = {_RESOURCE: _INGREDIENT}
    gd._resource_locations = {_RESOURCE: [(2, 0)]}
    gd._workshop_locations = {"alchemy": (3, 0)}
    gd._monster_level = {_HURTS: monster_level}
    gd._monster_hp = {_HURTS: 200}
    gd._monster_attack = {_HURTS: {"fire": 80}}
    gd._monster_resistance = {_HURTS: {}}
    gd._monster_locations = {_HURTS: [(1, 0)]}
    fill_monster_stat_defaults(gd)
    gd._npc_stock = {}
    gd._npc_sell_prices = {}
    gd._npc_locations = {}
    return gd


def _state(**overrides):
    """Level-20 character that BEATS `biting_slime` yet takes marginal damage
    doing it, for whom the fire boost is a strictly-positive combat-margin gain
    — the same three-way combination live Robby sits in (wolf winnable,
    `best_boost_potion` = fire_boost_potion, potion stocking justified).

    Alchemy is high enough for BOTH the heal and the boost recipe, and every
    potion material is already in hand, so material supply can never be the
    reason a plan is not found.
    """
    base = dict(
        level=20, hp=150, max_hp=150,
        attack={"fire": 150},
        equipment={**make_state().equipment, "weapon_slot": "wpn"},
        inventory={_INGREDIENT: 300},
        inventory_max=400, inventory_slots_max=400,
        skills={"alchemy": 20, "mining": 1, "woodcutting": 1, "fishing": 1,
                "weaponcrafting": 1, "gearcrafting": 1, "jewelrycrafting": 1,
                "cooking": 1},
    )
    base.update(overrides)
    return make_state(**base)


def _actions(gd: GameData) -> list:
    """Every action the goal's own ladder would admit, built from the catalog."""
    out: list = [GatherAction(resource_code=_RESOURCE, locations=frozenset({(2, 0)}))]
    for code in gd.crafting_recipes:
        out.append(CraftAction(code=code, quantity=1, workshop_location=(3, 0)))
    return out


def test_goal_is_plannable_without_a_craftable_boost():
    """Control. With no boost in the catalog the goal has ONE target, the frozen
    action set covers it, and the planner finds the craft+equip plan."""
    gd = _gd(with_boost=False, monster_level=18)
    state = _state()
    goal = CraftPotionsGoal(game_data=gd, state=state)
    assert goal.is_satisfied(state) is False, "fixture must start with a real deficit"

    plan = GOAPPlanner().plan(state, goal, _actions(gd), gd)

    assert plan, "control: the heal-only goal must be plannable"


def test_goal_stays_plannable_once_a_boost_becomes_craftable():
    """The regression. Same fixture plus a craftable boost — the ONLY difference.

    Live, this is the alchemy-10 threshold: below it `best_boost_potion` is None
    and the goal plans; at or above it `_active_craft` re-targets the boost the
    moment the heal deficit closes, so `is_satisfied` never goes True and the
    planner exhausts the whole reachable space. Robby crossed it (alchemy 16).
    """
    gd = _gd(with_boost=True, monster_level=18)
    state = _state()
    goal = CraftPotionsGoal(game_data=gd, state=state)
    assert goal.is_satisfied(state) is False, "fixture must start with a real deficit"

    planner = GOAPPlanner()
    plan = planner.plan(state, goal, _actions(gd), gd)

    assert not planner.last_stats.timed_out, "must be a real exhaustion, not a budget artifact"
    assert plan, (
        "goal must stay plannable when a boost is craftable; the frozen "
        "action set and the goal test have to agree on ONE target"
    )


def test_goal_is_plannable_when_the_deficit_exceeds_one_gather_batch():
    """The second instance of the same mismatch, independent of the boost clause.

    `_ladder_runs` caps the gather path at POTION_GATHER_BATCH runs, so
    `relevant_actions` admits an Equip sized to that BATCH — while the goal test
    demanded the FULL deficit. The goal's own docstring states the intent is to
    "gather a 5-potion batch and replan", so satisfying the batch must count as
    satisfying the goal for this plan.
    """
    gd = _gd(with_boost=False, monster_level=18)
    state = _state(inventory={})          # nothing held: forces the gather rung
    goal = CraftPotionsGoal(game_data=gd, state=state)
    assert goal.is_satisfied(state) is False, "fixture must start with a real deficit"

    planner = GOAPPlanner()
    plan = planner.plan(state, goal, _actions(gd), gd)

    assert not planner.last_stats.timed_out, "must be a real exhaustion, not a budget artifact"
    assert plan, "a deficit larger than one gather batch must still yield a batch plan"

"""End-to-end sanity for the potion-supply feature (spec 2026-06-30).

Ties the three moving parts together at the selection boundary:

  active_guards  ->  fires CRAFT_POTIONS when understocked + producible
  map_guard      ->  maps that guard to a CraftPotionsGoal
  relevant_actions -> that goal plans a craft+equip (NOT a bare grind)

Scenario 1 (positive): a level-3 character with empty utility slots, alchemy
skill, a craftable utility health potion, and the ingredients on hand ->
CRAFT_POTIONS fires, yields CraftPotionsGoal, and the plan both CRAFTS the
potion and EQUIPS it into a utility slot.

Scenario 2 (negative): the same character with no alchemy-craftable utility
potion in the catalog -> the guard stays quiet, so nothing preempts the grind.
"""

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.craft_potions import CraftPotionsGoal
from artifactsmmo_cli.ai.strategy_driver import map_guard
from artifactsmmo_cli.ai.tiers.guards import GuardKind, SelectionContext, active_guards
from tests.test_ai.fixtures import make_state

_POTION = "small_health_potion"
_INGREDIENT = "sunflower"
_RESOURCE = "sunflower_field"


def _ctx() -> SelectionContext:
    return SelectionContext(
        bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=1, combat_monster=None,
    )


def _gd_with_potion() -> GameData:
    """One alchemy-craftable utility heal (`small_health_potion`) whose lone
    ingredient `sunflower` drops from `sunflower_field`."""
    gd = GameData()
    gd._item_stats = {
        _POTION: ItemStats(code=_POTION, level=1, type_="utility", hp_restore=30,
                           crafting_skill="alchemy", crafting_level=1),
        _INGREDIENT: ItemStats(code=_INGREDIENT, level=1, type_="resource"),
    }
    gd._crafting_recipes = {_POTION: {_INGREDIENT: 1}}
    gd._resource_drops = {_RESOURCE: _INGREDIENT}
    gd._resource_locations = {_RESOURCE: [(2, 0)]}
    gd._workshop_locations = {"alchemy": (3, 0)}
    return gd


def _understocked_state():
    """Level 3, alchemy 1, empty utility slots, ingredient held (so the batch is
    craft-from-held producible). baseline(3)=5 > equipped 0 -> understocked."""
    return make_state(level=3, skills={"alchemy": 1}, utility1_slot_quantity=0,
                      inventory={_INGREDIENT: 10})


def test_understocked_producible_fires_guard_maps_goal_and_plans_craft_and_equip():
    gd = _gd_with_potion()
    state = _understocked_state()
    ctx = _ctx()

    # 1. The guard ladder fires CRAFT_POTIONS.
    fired = active_guards(state, gd, None, ctx)
    assert GuardKind.CRAFT_POTIONS in fired

    # 2. map_guard turns that guard into a CraftPotionsGoal.
    goal = map_guard(GuardKind.CRAFT_POTIONS, gd, ctx, state)
    assert isinstance(goal, CraftPotionsGoal)

    # 3. The goal plans a real craft-and-equip, not a bare grind.
    catalog = [
        CraftAction(code=_POTION, quantity=1, workshop_location=(3, 0)),
        GatherAction(resource_code=_RESOURCE, locations=frozenset({(2, 0)})),
        FightAction(monster_code="mob", locations=frozenset({(7, 7)})),
        MoveAction(x=0, y=0),
    ]
    plan = goal.relevant_actions(catalog, state, gd)
    assert any(isinstance(a, CraftAction) and a.code == _POTION for a in plan)
    assert any(isinstance(a, EquipAction) and a.slot == "utility1_slot" for a in plan)
    # The potion-supply goal never routes through combat.
    assert not any(isinstance(a, FightAction) for a in plan)


def test_no_alchemy_potion_leaves_guard_quiet_so_grind_proceeds():
    gd = GameData()  # empty catalog: no alchemy-craftable utility potion exists
    state = _understocked_state()
    ctx = _ctx()

    # Guard stays quiet -> the grind is not preempted.
    assert GuardKind.CRAFT_POTIONS not in active_guards(state, gd, None, ctx)
    # And the goal itself has no target, so it would contribute no actions.
    assert CraftPotionsGoal().relevant_actions(
        [MoveAction(x=0, y=0)], state, gd) == []

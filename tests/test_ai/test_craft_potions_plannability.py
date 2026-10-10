"""Planner-level plannability tests for CraftPotionsGoal.

Every other CraftPotionsGoal test asserts on the goal's own helpers in
isolation. None of them ever ran the REAL producer over the goal, and that is
how a goal that could never be satisfied shipped: live traces showed the
CRAFT_POTIONS guard firing on 442 cycles and the goal returning plan_len=0 on
285/285 selections. The A*-era causes were a frozen action set (relevant_actions
evaluated once, at the seed state) and a max_depth below the batch the goal's
own ladder sized.

Since Phase 2e the goal is the walk's (`craft_plan_gen._decompose_potions`, a
decline is final), so these cases pin that the WALK plans each shape: the
control, a second chosen potion beside the heal, a deficit larger than one
gather batch, and a 3-unit recipe. The goal stocks the CHOSEN loadout's potions
(docs/PLAN_consumable_utility.md increment 5).
"""

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.chosen_loadout import ChosenLoadout
from artifactsmmo_cli.ai.craft_plan_gen import decompose
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.craft_potions import CraftPotionsGoal
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

_HEAL = "small_health_potion"
_BOOST = "fire_boost_potion"
_INGREDIENT = "sunflower"
_RESOURCE = "sunflower_field"
_HURTS = "biting_slime"

HEAL_LOADOUT = ChosenLoadout(monster=_HURTS, potions=((_HEAL, 1),), food=())
"""The chosen loadout against `_HURTS`: one heal a fight, a carry of 20."""

BOTH_LOADOUT = ChosenLoadout(monster=_HURTS, potions=((_HEAL, 1), (_BOOST, 1)), food=())


def _gd(*, with_boost: bool, monster_level: int = 3, ingredient_qty: int = 1) -> GameData:
    """Catalog with a gatherable-ingredient alchemy heal, a winnable-but-hurting
    monster (so potion stocking is combat-justified), and — when `with_boost` —
    a craftable damage boost for the SAME element the monster is weak to.

    `with_boost` is the only difference between the two catalogs: it puts a
    second chosen potion in reach.
    """
    gd = GameData()
    stats = {
        _HEAL: ItemStats(code=_HEAL, level=1, type_="utility", hp_restore=30,
                         crafting_skill="alchemy", crafting_level=1),
        _INGREDIENT: ItemStats(code=_INGREDIENT, level=1, type_="resource"),
        "wpn": ItemStats(code="wpn", level=1, type_="weapon", attack={"fire": 150}),
    }
    recipes = {_HEAL: {_INGREDIENT: ingredient_qty}}
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
    """Level-20 character fighting `biting_slime`.

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
    """Control. The loadout chooses the heal alone; the walk finds the
    craft+equip plan."""
    gd = _gd(with_boost=False, monster_level=18)
    state = _state()
    goal = CraftPotionsGoal(loadout=HEAL_LOADOUT, game_data=gd, state=state)
    assert goal.is_satisfied(state) is False, "fixture must start with a real deficit"

    plan = (decompose(goal, state, gd, list(_actions(gd)), NO_PROFILE_CONTEXT) or [])

    assert plan, "control: the heal-only goal must be plannable"


def test_goal_stays_plannable_with_a_second_chosen_potion():
    """The regression. Same fixture plus a second chosen potion — the ONLY
    difference. The goal must not re-target the boost the moment the heal's
    deficit closes (the old `_active_craft` did, so `is_satisfied` never went
    True and the planner exhausted the space; live Robby, alchemy 16): the seed
    freezes ONE potion at ONE batch."""
    gd = _gd(with_boost=True, monster_level=18)
    state = _state()
    goal = CraftPotionsGoal(loadout=BOTH_LOADOUT, game_data=gd, state=state)
    assert goal.is_satisfied(state) is False, "fixture must start with a real deficit"

    plan = decompose(goal, state, gd, list(_actions(gd)), NO_PROFILE_CONTEXT) or []

    assert plan, (
        "goal must stay plannable when a boost is craftable; the frozen "
        "action set and the goal test have to agree on ONE target"
    )


def test_goal_is_plannable_when_the_deficit_exceeds_one_gather_batch():
    """The second instance of the same mismatch, independent of the boost clause.

    `_ladder_runs` caps the gather path at POTION_GATHER_BATCH runs, so the
    equip is sized to that BATCH, not the carry's full deficit; satisfying the
    batch must count as satisfying the goal for this plan.
    """
    gd = _gd(with_boost=False, monster_level=18)
    state = _state(inventory={})          # nothing held: forces the gather rung
    goal = CraftPotionsGoal(loadout=HEAL_LOADOUT, game_data=gd, state=state)
    assert goal.is_satisfied(state) is False, "fixture must start with a real deficit"

    plan = decompose(goal, state, gd, list(_actions(gd)), NO_PROFILE_CONTEXT) or []

    assert plan, "a deficit larger than one gather batch must still yield a batch plan"


def test_goal_provisions_depth_for_the_batch_its_own_ladder_sized():
    """The batch must FIT the goal's max_depth.

    `_ladder_runs` sizes a gather batch of up to POTION_GATHER_BATCH runs, and a
    run costs one Gather per ingredient unit. With a 3-unit recipe that is
    5*3 = 15 gathers + 1 craft + 1 equip = 17 actions — past the inherited
    Goal.max_depth of 15, so A* exhausts at depth 15 and returns nothing.

    Live at level 20 this is exactly what `plan Robby` showed:
    `CraftPotionsGoal: nodes=54 depth=15 plan_len=0`; raising only max_depth to
    20 turned the same state into `plan_len=17` in 60 nodes. A goal must
    provision depth for the batch it sized, or the batch is unreachable by
    construction — the same action-set/goal-test disagreement as the boost
    clause above, in the depth dimension.
    """
    gd = _gd(with_boost=False, monster_level=18, ingredient_qty=3)
    state = _state(inventory={})          # nothing held: forces the gather rung
    goal = CraftPotionsGoal(loadout=HEAL_LOADOUT, game_data=gd, state=state)
    assert goal.is_satisfied(state) is False, "fixture must start with a real deficit"

    plan = decompose(goal, state, gd, list(_actions(gd)), NO_PROFILE_CONTEXT) or []

    assert len(plan) >= 2, "the sized batch must be planned whole"

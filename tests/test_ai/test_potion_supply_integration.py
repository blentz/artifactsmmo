"""End-to-end sanity for the potion-supply feature (spec 2026-06-30).

Ties the three moving parts together at the selection boundary:

  active_guards  ->  fires CRAFT_POTIONS when understocked + producible
  map_guard      ->  maps that guard to a CraftPotionsGoal
  relevant_actions -> that goal plans a craft+equip (NOT a bare grind)

Scenario 1 (positive): a level-3 character with empty utility slots, alchemy
skill, a craftable utility health potion its chosen loadout wears against the
fight ahead, and the ingredients on hand -> CRAFT_POTIONS fires, yields
CraftPotionsGoal, and the plan both CRAFTS the potion and EQUIPS it into a
utility slot.

Scenario 2 (negative): the same character with no craftable utility potion in
the catalog -> the guard stays quiet, so nothing preempts the grind.

The rest pin that ONLY the chosen loadout, chosen against the fight ahead, is
stocked (docs/PLAN_consumable_utility.md increment 5).
"""

import dataclasses

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.chosen_loadout import ChosenLoadout
from artifactsmmo_cli.ai.craft_plan_gen import decompose
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.craft_potions import CraftPotionsGoal
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.strategy_driver import map_guard
from artifactsmmo_cli.ai.tiers.guards import GuardKind, SelectionContext, active_guards
from artifactsmmo_cli.ai.tiers.guards import _fires as guard_fires
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.strategy import StrategyEngine
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

_POTION = "small_health_potion"
_INGREDIENT = "sunflower"
_RESOURCE = "sunflower_field"
_MONSTER = "slime"
_BOOST = "fire_boost"
_LOADOUT = ChosenLoadout(monster=_MONSTER, potions=((_POTION, 1),), food=())


def _ctx(fight_monster: str | None = None,
         loadout: ChosenLoadout | None = _LOADOUT) -> SelectionContext:
    return SelectionContext(
        bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=1, combat_monster=None,
        fight_monster=fight_monster, loadout=loadout,
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


def _gd_with_potion_and_hurting_monster() -> GameData:
    """`_gd_with_potion` plus the monster the chosen loadout is chosen against,
    and a craftable boost the loadout does NOT wear."""
    gd = _gd_with_potion()
    gd._item_stats[_BOOST] = ItemStats(code=_BOOST, level=1, type_="utility",
                                       dmg_elements={"fire": 10},
                                       crafting_skill="alchemy", crafting_level=1)
    gd._crafting_recipes[_BOOST] = {_INGREDIENT: 1}
    gd._monster_level = {_MONSTER: 3}
    gd._monster_hp = {_MONSTER: 60}
    gd._monster_attack = {_MONSTER: {"fire": 40}}
    gd._monster_resistance = {_MONSTER: {}}
    gd._monster_locations = {_MONSTER: [(1, 0)]}
    fill_monster_stat_defaults(gd)
    return gd


def _understocked_state():
    """Level 3, alchemy 1, empty utility slots, ingredient held (so the batch is
    craft-from-held producible): the chosen heal is short of its carry."""
    return make_state(level=3, skills={"alchemy": 1}, utility1_slot_quantity=0,
                      inventory={_INGREDIENT: 10}, attack={"fire": 20})


def test_understocked_producible_fires_guard_maps_goal_and_plans_craft_and_equip():
    gd = _gd_with_potion_and_hurting_monster()
    state = _understocked_state()
    ctx = _ctx(fight_monster=_MONSTER)

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
    plan = decompose(goal, state, gd, catalog, NO_PROFILE_CONTEXT) or []
    assert any(isinstance(a, CraftAction) and a.code == _POTION for a in plan)
    assert any(isinstance(a, EquipAction) and a.slot == "utility1_slot" for a in plan)
    # The potion-supply goal never routes through combat.
    assert not any(isinstance(a, FightAction) for a in plan)


def test_no_alchemy_potion_leaves_guard_quiet_so_grind_proceeds():
    gd = GameData()  # empty catalog: no alchemy-craftable utility potion exists
    state = _understocked_state()
    ctx = _ctx(fight_monster=_MONSTER)

    # Guard stays quiet -> the grind is not preempted.
    assert _fires(state, gd, ctx) is False
    # And the goal itself has no batch, so the walk declines it.
    declined: list[str] = []
    assert decompose(CraftPotionsGoal(loadout=_LOADOUT, game_data=gd, state=state), state, gd,
                     [MoveAction(x=0, y=0)], NO_PROFILE_CONTEXT, declined) is None
    assert declined == ["potion:no_batch"]


def test_robby_scenario_stocked_small_does_not_force_enhanced_grind() -> None:
    """Stocked small_health_potion (qty 100 >> L10 baseline 16) must NOT cause
    the engine to choose enhanced_health_potion (alchemy L45) as chosen_root.

    Regression guard for the Robby play-trace where a well-stocked lower-tier
    potion triggered aspirational enhanced-potion grind (alchemy 16→45).
    """
    gd = GameData()
    gd._item_stats = {
        "small_health_potion": ItemStats(
            code="small_health_potion", level=1, type_="utility",
            hp_restore=60, crafting_skill="alchemy", crafting_level=5),
        "enhanced_health_potion": ItemStats(
            code="enhanced_health_potion", level=45, type_="utility",
            hp_restore=300, crafting_skill="alchemy", crafting_level=45),
        "sunflower": ItemStats(code="sunflower", level=1, type_="resource"),
    }
    gd._consumable_effect_codes = {}
    gd._crafting_recipes = {
        "small_health_potion": {"sunflower": 3},
        "enhanced_health_potion": {"sunflower": 3},
    }
    gd._resource_drops = {"sunflower_field": "sunflower"}
    gd._resource_skill = {"sunflower_field": ("alchemy", 1)}
    gd._monster_level = {"chicken": 1}
    fill_monster_stat_defaults(gd)

    state = make_state(
        level=10,
        skills={**make_state().skills, "alchemy": 16},
        equipment={**make_state().equipment, "utility1_slot": "small_health_potion"},
        utility1_slot_quantity=100,
    )

    eng = StrategyEngine(CharacterObjective.from_game_data(gd))
    chosen_root = eng.decide(state, gd).chosen_root
    assert "enhanced_health_potion" not in repr(chosen_root)


# ── only the chosen loadout, for the fight ahead ────────────────────────────

def _fires(state, gd, ctx) -> bool:  # type: ignore[no-untyped-def]
    """The CRAFT_POTIONS guard alone: the other guards read the fight-ahead
    monster's stats, which these catalogs do not carry for `cow`."""
    return guard_fires(GuardKind.CRAFT_POTIONS, state, gd, None, ctx, None)


def test_no_chosen_loadout_leaves_the_guard_quiet():
    """Understocked and brewable, but no loadout is chosen: nothing to stock."""
    gd = _gd_with_potion_and_hurting_monster()
    state = _understocked_state()
    assert _fires(state, gd, _ctx(fight_monster=_MONSTER)) is True, "fixture: the chosen heal fires"
    assert _fires(state, gd, _ctx(fight_monster=_MONSTER, loadout=None)) is False


def test_no_fight_ahead_stocks_nothing():
    """2026-10-06, live Lor: the stock was sized for a monster (`rat`) Lor
    never fought; ~258 sunflower gathers in three hours. With no fight ahead
    the chosen loadout is not stocked."""
    gd = _gd_with_potion_and_hurting_monster()
    state = _understocked_state()
    assert _fires(state, gd, _ctx(fight_monster=None)) is False


def test_a_loadout_chosen_against_another_monster_is_not_stocked():
    gd = _gd_with_potion_and_hurting_monster()
    state = _understocked_state()
    assert _fires(state, gd, _ctx(fight_monster="cow")) is False


def test_an_unchosen_craftable_potion_is_never_brewed():
    """The heal is worn at its carry and the boost is short, craftable and
    not worn: the loadout does not choose the boost, so nothing fires."""
    gd = _gd_with_potion_and_hurting_monster()
    state = dataclasses.replace(
        _understocked_state(),
        equipment={**make_state().equipment, "utility1_slot": _POTION},
        utility1_slot_quantity=20)
    assert _fires(state, gd, _ctx(fight_monster=_MONSTER)) is False
    boost_too = ChosenLoadout(monster=_MONSTER, potions=((_POTION, 1), (_BOOST, 1)), food=())
    assert _fires(state, gd, _ctx(fight_monster=_MONSTER, loadout=boost_too)) is True


def test_a_chosen_boost_is_planned_into_the_free_slot():
    """Heal carried in slot 1, the chosen boost short: the goal crafts the
    boost and equips it into slot 2, displacing nothing."""
    gd = _gd_with_potion_and_hurting_monster()
    state = dataclasses.replace(
        _understocked_state(),
        equipment={**make_state().equipment, "utility1_slot": _POTION},
        utility1_slot_quantity=20)
    boost_too = ChosenLoadout(monster=_MONSTER, potions=((_POTION, 1), (_BOOST, 1)), food=())
    ctx = _ctx(fight_monster=_MONSTER, loadout=boost_too)
    goal = map_guard(GuardKind.CRAFT_POTIONS, gd, ctx, state)
    catalog = [CraftAction(code=_BOOST, quantity=1, workshop_location=(3, 0)),
               GatherAction(resource_code=_RESOURCE, locations=frozenset({(2, 0)})),
               MoveAction(x=0, y=0)]
    plan = decompose(goal, state, gd, catalog, NO_PROFILE_CONTEXT) or []
    assert any(isinstance(a, CraftAction) and a.code == _BOOST for a in plan)
    assert plan[-1] == EquipAction(code=_BOOST, slot="utility2_slot", quantity=10)


def test_the_heal_target_with_an_empty_recipe_and_none_held_is_quiet():
    """A chosen heal whose recipe is EMPTY has no ingredient path and none is
    held, so the guard stays silent rather than fire on an unbuildable target."""
    gd = _gd_with_potion_and_hurting_monster()
    gd._crafting_recipes = {_POTION: {}}
    assert _fires(_understocked_state(), gd, _ctx(fight_monster=_MONSTER)) is False

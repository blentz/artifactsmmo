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
from artifactsmmo_cli.ai.potion_supply import craft_potions_fires
from artifactsmmo_cli.ai.strategy_driver import map_guard
from artifactsmmo_cli.ai.tiers.guards import GuardKind, SelectionContext, active_guards
from tests.test_ai.fixtures import make_state
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.personality import BalancedPersonality
from artifactsmmo_cli.ai.tiers.strategy import StrategyEngine
from tests.test_ai._monster_fixture import fill_monster_stat_defaults

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

    eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
    chosen_root = eng.decide(state, gd).chosen_root
    assert "enhanced_health_potion" not in repr(chosen_root)


# ── boost-supply guard (Task 4) ──────────────────────────────────────────────

_BOOST = "fire_boost"
_MONSTER = "slime"


def _gd_boost_winnable() -> GameData:
    """GameData with:
    - A heal: small_health_potion (utility, hp_restore=30, alchemy/1).
    - A boost: fire_boost (utility, dmg_elements={"fire": 10}, alchemy/1).
      Not a heal (hp_restore=0) → qualifies as boost in best_boost_potion.
    - A monster: slime (level=5, hp=1000, attack={"fire": 5}).
      Character (attack={"fire": 50}) kills slime in 20 rounds; slime kills
      character in 20 rounds → predict_win True (margin=1, player_first).
      With boost (raw_player=55): rounds_to_kill=19, margin=2 → gain=1 > 0
      → best_boost_potion returns fire_boost.
    """
    gd = GameData()
    gd._item_stats = {
        _POTION: ItemStats(code=_POTION, level=1, type_="utility", hp_restore=30,
                           crafting_skill="alchemy", crafting_level=1),
        _BOOST: ItemStats(code=_BOOST, level=1, type_="utility",
                          dmg_elements={"fire": 10},
                          crafting_skill="alchemy", crafting_level=1),
        _INGREDIENT: ItemStats(code=_INGREDIENT, level=1, type_="resource"),
    }
    gd._crafting_recipes = {_POTION: {_INGREDIENT: 1}, _BOOST: {_INGREDIENT: 3}}
    gd._resource_drops = {}
    gd._resource_locations = {}
    gd._workshop_locations = {"alchemy": (3, 0)}
    gd._npc_stock = {}
    gd._npc_sell_prices = {}
    gd._npc_locations = {}
    gd._monster_level = {_MONSTER: 5}
    gd._monster_hp = {_MONSTER: 1000}
    gd._monster_attack = {_MONSTER: {"fire": 5}}
    gd._monster_resistance = {_MONSTER: {}}
    fill_monster_stat_defaults(gd)
    return gd


def _gd_boost_trivial_monster() -> GameData:
    """Same as _gd_boost_winnable but monster attack={} (no attack).
    die_step=0 → combat_margin=WIN_MARGIN both with and without boost
    → gain=0 → best_boost_potion returns None."""
    gd = _gd_boost_winnable()
    gd._monster_attack = {_MONSTER: {}}
    return gd


def _state_heals_stocked() -> GameData:
    """Level=5, alchemy=10, heal equipped at baseline qty=5 (stocked),
    boost not equipped, inventory has 3 sunflowers (producible for 1 boost batch)."""
    return make_state(
        level=5,
        hp=100, max_hp=100,
        attack={"fire": 50},
        skills={**make_state().skills, "alchemy": 10},
        equipment={**make_state().equipment, "utility1_slot": _POTION},
        utility1_slot_quantity=5,
        inventory={_INGREDIENT: 3},
    )


def test_guard_fires_for_beneficial_boost_when_heal_stocked():
    """craft_potions_fires returns True for a beneficial, understocked, producible
    boost when heals are already at baseline.

    Heals stocked (qty=5 == baseline(5)=5); fire_boost has gain=1 against slime;
    boost not equipped (qty=0 < 5); 3 sunflowers held satisfy recipe {sunflower:3}.
    """
    gd = _gd_boost_winnable()
    state = _state_heals_stocked()
    assert craft_potions_fires(state, gd) is True


def test_guard_no_boost_when_none_beneficial():
    """craft_potions_fires returns False when heals are stocked and no beneficial
    boost exists.

    fire_boost exists and is craftable (alchemy gate met), but the monster has
    zero attack so combat_margin is WIN_MARGIN with or without boost → gain=0
    → best_boost_potion returns None → boost path skipped → guard False.
    Non-vacuous: the boost item exists and the skill gate is met; only the
    combat-margin gain condition differs.
    """
    gd = _gd_boost_trivial_monster()
    state = _state_heals_stocked()
    assert craft_potions_fires(state, gd) is False

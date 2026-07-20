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

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.boost_selection import best_boost_potion, project_equip
from artifactsmmo_cli.ai.combat import combat_margin
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.craft_potions import CraftPotionsGoal
from artifactsmmo_cli.ai.potion_supply import craft_potions_fires
from artifactsmmo_cli.ai.strategy_driver import map_guard
from artifactsmmo_cli.ai.tiers.guards import GuardKind, SelectionContext, active_guards
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.strategy import StrategyEngine
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
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


def _gd_with_potion_and_hurting_monster() -> GameData:
    """`_gd_with_potion` plus an in-band monster that actually hurts.

    Stocking is combat-justified (2026-07-19): the target is projected in-combat
    consumption, so a fixture with NO monster projects zero need and the guard
    correctly stays silent. This fixture supplies the combat pressure that makes
    stocking the right call -- a monster whose expected damage leaves the
    character at or below the marginal-fight HP fraction."""
    gd = _gd_with_potion()
    gd._monster_level = {_MONSTER: 3}
    gd._monster_hp = {_MONSTER: 60}
    gd._monster_attack = {_MONSTER: {"fire": 40}}
    gd._monster_resistance = {_MONSTER: {}}
    gd._monster_locations = {_MONSTER: [(1, 0)]}
    fill_monster_stat_defaults(gd)
    return gd


def _understocked_state():
    """Level 3, alchemy 1, empty utility slots, ingredient held (so the batch is
    craft-from-held producible). Understocked against the combat-projected
    target, which the paired game data supplies a hurting monster for."""
    return make_state(level=3, skills={"alchemy": 1}, utility1_slot_quantity=0,
                      inventory={_INGREDIENT: 10}, attack={"fire": 20})


def test_understocked_producible_fires_guard_maps_goal_and_plans_craft_and_equip():
    gd = _gd_with_potion_and_hurting_monster()
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

    eng = StrategyEngine(CharacterObjective.from_game_data(gd))
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
    # Static tile: combat_target_monsters requires a known spawn, and both the
    # boost selector and the combat-justified heal target route through it.
    gd._monster_locations = {_MONSTER: [(1, 0)]}
    fill_monster_stat_defaults(gd)
    return gd


def _gd_boost_trivial_monster() -> GameData:
    """Same as _gd_boost_winnable but monster attack={} (no attack).
    die_step=0 → combat_margin=WIN_MARGIN both with and without boost
    → gain=0 → best_boost_potion returns None."""
    gd = _gd_boost_winnable()
    gd._monster_attack = {_MONSTER: {}}
    return gd


def _state_heals_stocked() -> WorldState:
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


def test_c1_guard_and_goal_agree_on_boost_target():
    """C1 spin regression: guard picks boost-target via primary_combat_target;
    goal must use the SAME selector — NOT self._combat_monster.

    Pre-fix: CraftPotionsGoal._active_craft guarded the boost branch on
    ``self._combat_monster is not None``.  When the goal was constructed with
    ``combat_monster=None`` (or any monster that differs from primary_combat_target),
    _active_craft returned None even though craft_potions_fires returned True
    → guard re-fired every cycle → infinite spin.

    Post-fix: the goal's boost branch calls primary_combat_target(state, gd),
    identical to the guard, so guard and goal always agree on the target.

    Non-vacuous: fire_boost IS craftable-now (alchemy=10 >= gate=1), IS
    beneficial against slime (fire attack → gain > 0), and IS producible
    (3 sunflowers held satisfy recipe {sunflower:3}).  The only variable is
    which monster the goal uses — post-fix it matches the guard's pick.
    """
    gd = _gd_boost_winnable()
    state = _state_heals_stocked()

    # Guard fires: primary_combat_target = slime → fire_boost beneficial + producible.
    assert craft_potions_fires(state, gd) is True

    # Goal constructed with combat_monster=None: simulates the mismatch where
    # the strategy driver passes a task-aligned monster different from the guard's pick.
    goal = CraftPotionsGoal(combat_monster=None)

    # Post-fix: _active_craft uses primary_combat_target → slime → fire_boost plan.
    # Pre-fix: the combat_monster=None branch was skipped entirely → returned None.
    result = goal._active_craft(state, gd)
    assert result is not None, (
        "guard fired for slime's fire_boost but _active_craft returned None "
        "(C1 spin: goal boost-path was gated on self._combat_monster, "
        "not primary_combat_target)"
    )
    assert result[0] == _BOOST


# ── anti-grind regression (Task 5) ──────────────────────────────────────────

def _gd_boost_skill_gated() -> GameData:
    """Same as _gd_boost_winnable but fire_boost requires crafting_level=20.

    The boost EXISTS and WOULD improve combat_margin against slime (fire attack
    → resistance boost gives positive gain).  Only the skill requirement is out
    of reach for a character whose alchemy=5 (below gate=20).
    """
    gd = _gd_boost_winnable()
    gd._item_stats[_BOOST] = ItemStats(
        code=_BOOST, level=1, type_="utility",
        dmg_elements={"fire": 10},
        crafting_skill="alchemy", crafting_level=20,
    )
    return gd


def _state_heals_stocked_low_alchemy() -> WorldState:
    """Same as _state_heals_stocked but alchemy=5 (below boost gate=20).

    Heals are stocked (utility1_slot=small_health_potion, qty=5==baseline(5)=5)
    so the guard looks at the boost path rather than the heal path."""
    return make_state(
        level=5,
        hp=100, max_hp=100,
        attack={"fire": 50},
        skills={**make_state().skills, "alchemy": 5},
        equipment={**make_state().equipment, "utility1_slot": _POTION},
        utility1_slot_quantity=5,
        inventory={_INGREDIENT: 3},
    )


def test_anti_grind_boost_skill_gated_guard_does_not_fire():
    """Phase-1 anti-grind discipline: a beneficial boost that requires a crafting
    skill above the character's current level is silently skipped — the guard does
    NOT fire, and no planning step pursues it.

    Non-vacuous:
    - fire_boost EXISTS and is in crafting_recipes.
    - fire_boost WOULD improve combat_margin against slime (verified by
      project_equip + combat_margin direct call: gain > 0).
    - Only the skill gate (alchemy=5 < crafting_level=20) blocks it.

    The anti-grind discipline is enforced exclusively by best_boost_potion:
    it gates by craftable-now, never schedules a skill grind to reach the
    boost's skill requirement.  Guard silence means no CraftPotionsGoal is
    ever queued for the boost, so no planner step can grind (via a LevelSkill
    leg) the boost crafting skill.
    """
    gd = _gd_boost_skill_gated()
    state = _state_heals_stocked_low_alchemy()

    # Non-vacuousness: the boost WOULD help if alchemy were sufficient.
    projected = project_equip(state, _BOOST, gd)
    gain = combat_margin(projected, gd, _MONSTER) - combat_margin(state, gd, _MONSTER)
    assert gain > 0, (
        f"fixture broken: fire_boost should improve combat_margin (gain={gain}); "
        "ensure slime has fire attack and boost adds fire dmg_elements"
    )

    # Skill gate blocks selection: alchemy=5 < crafting_level=20 → None.
    assert best_boost_potion(state, gd, _MONSTER) is None, (
        "best_boost_potion should return None when alchemy < crafting_level; "
        "anti-grind discipline requires craftable-now check, not aspirational"
    )

    # Guard does not fire — the economy does not pursue the boost.
    assert craft_potions_fires(state, gd) is False, (
        "craft_potions_fires must be False when the only boost is skill-gated; "
        "firing would send the economy into an unreachable grind"
    )

    # Goal corroboration: _active_craft also returns None (no boost plan emitted).
    goal = CraftPotionsGoal(combat_monster=None)
    assert goal._active_craft(state, gd) is None, (
        "_active_craft must return None when guard is silent; "
        "any non-None result would plan a craft step for an unattainable boost"
    )


# ─── combat-justified stocking (2026-07-19) ──────────────────────────────────
# The guard used to fire on a bare level-ramp stock deficit, with no HP and no
# consumption term, so a full-HP bot that wins every fight without drinking
# anything still routed to gather/craft. Since Rest went dynamic (3a4994f4) that
# is never a time saving -- resting refills to full for max(3, ceil(missing%))
# seconds. Potions are justified by combat (you cannot rest MID-fight), so
# projected consumption now drives the target and the ramp only caps it.


def test_guard_silent_when_no_projected_consumption():
    """THE REPORTED BUG. Understocked heals, but the bot wins without drinking:
    no history, and the monster is comfortably winnable, so projected consumption
    is 0 and the guard must stay silent.

    Non-vacuous: identical to test_guard_fires_when_understocked_and_producible
    except for the consumption projection -- the heal is craftable, understocked,
    and its recipe is producible, so every OTHER precondition to fire is met."""
    gd = _gd_boost_trivial_monster()          # zero-attack monster => no healing needed
    state = make_state(
        level=5,
        hp=100, max_hp=100,
        attack={"fire": 50},
        skills={**make_state().skills, "alchemy": 10},
        equipment={**make_state().equipment, "utility1_slot": _POTION},
        utility1_slot_quantity=0,             # UNDERSTOCKED
        inventory={_INGREDIENT: 3},           # recipe producible
    )
    assert craft_potions_fires(state, gd, None) is False, (
        "guard must stay silent when the bot needs no in-combat healing; "
        "gather-crafting a potion is never cheaper than resting it off"
    )


def test_guard_fires_when_consumption_is_projected():
    """The other side: a monster that actually hurts projects real consumption,
    so the guard fires and the bot stocks ahead of the fight."""
    gd = _gd_boost_winnable()                 # attacking monster => damage taken
    state = make_state(
        level=5,
        hp=100, max_hp=100,
        attack={"fire": 50},
        skills={**make_state().skills, "alchemy": 10},
        equipment={**make_state().equipment, "utility1_slot": _POTION},
        utility1_slot_quantity=0,
        inventory={_INGREDIENT: 3},
    )
    assert craft_potions_fires(state, gd, None) is True


def test_guard_quiet_when_the_heal_target_has_an_empty_recipe():
    """A craftable-now heal whose recipe is EMPTY has no ingredient path, so the
    guard must stay silent rather than fire on an unbuildable target.

    Distinct from the no-recipe case: the item IS in crafting_recipes, mapped to
    an empty dict."""
    gd = _gd_with_potion_and_hurting_monster()
    gd._crafting_recipes = {_POTION: {}}          # present but empty
    state = make_state(level=3, skills={"alchemy": 1}, utility1_slot_quantity=0,
                       inventory={_INGREDIENT: 10}, attack={"fire": 20})
    assert craft_potions_fires(state, gd, None) is False

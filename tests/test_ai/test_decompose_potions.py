"""CraftPotionsGoal is served by decomposition (Phase 2c-1 of
docs/PLAN_decision_architecture_redesign.md).

Live Robby 2026-09-29: A* searched this goal about 70 times an hour and timed
out at ~200k nodes, depth 92, with no plan: the batch the guard judged
suppliable was longer than the search could reach. The goal is an obtain goal
(the batch in the bag, then one equip), so `decompose` now serves it like the
grind."""

from dataclasses import replace

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.craft_plan_gen import decompose
from artifactsmmo_cli.ai.goals.craft_potions import CraftPotionsGoal
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from tests.test_ai.test_craft_potions_plannability import (
    _HEAL,
    _INGREDIENT,
    _RESOURCE,
    HEAL_LOADOUT,
    _actions,
    _gd,
    _state,
)


def _apply_all(plan, state, gd):
    for action in plan:
        assert action.is_applicable(state, gd), f"{action!r} not applicable in sequence"
        state = action.apply(state, gd)
    return state


def _drive(goal, state, gd, actions, cycles: int = 20):
    """Decompose and apply the plan, cycle after cycle, the way the plan
    cache replans from the real state after each step, until the goal is
    satisfied. Returns the final state and every leg run."""
    ran = []
    for _ in range(cycles):
        if goal.is_satisfied(state):
            return state, ran
        plan = decompose(goal, state, gd, actions, NO_PROFILE_CONTEXT)
        assert plan is not None, f"decomposition declined at {state.inventory}"
        state = _apply_all(plan, state, gd)
        ran.extend(plan)
    raise AssertionError("the batch never landed")


def test_held_ingredients_craft_then_equip_and_satisfy_the_goal():
    gd = _gd(with_boost=False, monster_level=18)
    state = _state()
    goal = CraftPotionsGoal(loadout=HEAL_LOADOUT, game_data=gd, state=state)
    assert not goal.is_satisfied(state), "fixture must start with a real deficit"

    _final, ran = _drive(goal, state, gd, _actions(gd))

    assert {type(a).__name__ for a in ran} == {"CraftAction", "EquipAction"}
    assert isinstance(ran[-1], EquipAction)


def test_held_ingredients_craft_the_whole_batch_in_one_action():
    """The walk crafts every run the bag's ingredients cover in one action
    (one request), and the equip then lands the batch."""
    gd = _gd(with_boost=False, monster_level=18)
    state = _state()
    goal = CraftPotionsGoal(loadout=HEAL_LOADOUT, game_data=gd, state=state)
    equip = goal.batch_equip(state)
    assert equip is not None
    plan = decompose(goal, state, gd, _actions(gd), NO_PROFILE_CONTEXT)
    assert plan is not None
    assert [type(a).__name__ for a in plan] == ["CraftAction", "EquipAction"]
    assert plan[-1] == equip


def test_a_prefix_plan_ends_before_the_equip():
    """When the legs stop short of the batch (here the craft has no action in
    the pool, so the plan is the gather alone), the plan stops there instead
    of naming an equip it cannot reach."""
    gd = _gd(with_boost=False, monster_level=18)
    state = _state(inventory={})
    goal = CraftPotionsGoal(loadout=HEAL_LOADOUT, game_data=gd, state=state)
    actions = [a for a in _actions(gd) if not isinstance(a, CraftAction)]
    plan = decompose(goal, state, gd, actions, NO_PROFILE_CONTEXT)
    assert plan is not None
    assert [type(a).__name__ for a in plan] == ["GatherAction"]


def test_potions_already_in_the_bag_are_just_equipped():
    gd = _gd(with_boost=False, monster_level=18)
    state = _state()
    goal = CraftPotionsGoal(loadout=HEAL_LOADOUT, game_data=gd, state=state)
    equip = goal.batch_equip(state)
    assert equip is not None
    stocked = replace(state, inventory={**state.inventory, _HEAL: equip.quantity})

    plan = decompose(goal, stocked, gd, _actions(gd), NO_PROFILE_CONTEXT)

    assert plan == [equip]
    assert goal.is_satisfied(_apply_all(plan, stocked, gd))


def test_missing_ingredients_are_gathered_first():
    gd = _gd(with_boost=False, monster_level=18)
    state = _state(inventory={})
    goal = CraftPotionsGoal(loadout=HEAL_LOADOUT, game_data=gd, state=state)

    plan = decompose(goal, state, gd, _actions(gd), NO_PROFILE_CONTEXT)

    assert plan is not None
    assert isinstance(plan[0], GatherAction)
    _final, ran = _drive(goal, state, gd, _actions(gd))
    assert isinstance(ran[-1], EquipAction)


def test_a_landed_batch_is_not_decomposed():
    gd = _gd(with_boost=False, monster_level=18)
    state = _state()
    goal = CraftPotionsGoal(loadout=HEAL_LOADOUT, game_data=gd, state=state)
    done, _ran = _drive(goal, state, gd, _actions(gd))

    assert goal.batch_equip(done) is None
    assert goal.batch_obtain(done) is None
    assert decompose(goal, done, gd, _actions(gd), NO_PROFILE_CONTEXT) is None


def test_an_unseeded_goal_is_left_to_the_search():
    gd = _gd(with_boost=False, monster_level=18)
    assert decompose(CraftPotionsGoal(loadout=HEAL_LOADOUT, game_data=gd), _state(), gd, _actions(gd),
                     NO_PROFILE_CONTEXT) is None


def test_a_batch_that_would_fight_is_left_to_the_search(monkeypatch):
    """The potion ladder never fights (`POTION_POLICY` has no drops), so the
    guard never seeds a batch whose ingredient only a monster drops, and a fight
    leg cannot arise today. The decline is defensive: should the two policies
    ever disagree, a guard's batch must not turn into a different errand. The
    seed is forced here, because the real ladder would (rightly) refuse it."""
    gd = _gd(with_boost=False, monster_level=18)
    gd._resource_drops = {}
    gd._monster_drops = {"biting_slime": [(_INGREDIENT, 1, 1, 1)]}
    monkeypatch.setattr("artifactsmmo_cli.ai.goals.craft_potions.potion_batch",
                        lambda *_a: (_HEAL, 2, 2))
    state = _state(inventory={})
    goal = CraftPotionsGoal(loadout=HEAL_LOADOUT, game_data=gd, state=state)
    actions = [a for a in _actions(gd) if not isinstance(a, GatherAction)]
    actions.append(FightAction(monster_code="biting_slime", locations=frozenset({(1, 0)})))
    obtain = goal.batch_obtain(state)
    assert obtain is not None
    legs = decompose(obtain, state, gd, actions, NO_PROFILE_CONTEXT)
    assert legs is not None and isinstance(legs[0], FightAction), "fixture: the batch really opens with a fight"

    assert decompose(goal, state, gd, actions, NO_PROFILE_CONTEXT) is None


def test_the_gather_the_plan_opens_with_is_the_ingredients():
    gd = _gd(with_boost=False, monster_level=18)
    state = _state(inventory={})
    goal = CraftPotionsGoal(loadout=HEAL_LOADOUT, game_data=gd, state=state)
    plan = decompose(goal, state, gd, _actions(gd), NO_PROFILE_CONTEXT)
    assert plan is not None
    assert plan[0].resource_code == _RESOURCE


def test_decline_reasons_are_named(monkeypatch):
    """Phase 2c-2.0: each potion decline names why."""
    gd = _gd(with_boost=False, monster_level=18)
    state = _state()
    goal = CraftPotionsGoal(loadout=HEAL_LOADOUT, game_data=gd, state=state)

    done, _ran = _drive(goal, state, gd, _actions(gd))
    declined: list[str] = []
    assert decompose(goal, done, gd, _actions(gd), NO_PROFILE_CONTEXT, declined) is None
    assert declined == ["potion:no_batch"]

    equip = goal.batch_equip(state)
    assert equip is not None
    stocked = replace(state, inventory={**state.inventory, _HEAL: equip.quantity})
    declined = []
    monkeypatch.setattr(EquipAction, "is_applicable", lambda *_a: False)
    assert decompose(goal, stocked, gd, _actions(gd), NO_PROFILE_CONTEXT, declined) is None
    assert declined == [f"potion:equip_inapplicable:{equip!r}"]


def test_a_drop_only_ingredient_is_off_the_ladder(monkeypatch):
    """The batch is walked under `POTION_POLICY` (no drops), the policy that
    judged it suppliable, so an ingredient only a fight yields has no route
    rather than a fight leg (Phase 2d-F)."""
    gd = _gd(with_boost=False, monster_level=18)
    gd._resource_drops = {}
    gd._monster_drops = {"biting_slime": [(_INGREDIENT, 1, 1, 1)]}
    monkeypatch.setattr("artifactsmmo_cli.ai.goals.craft_potions.potion_batch",
                        lambda *_a: (_HEAL, 2, 2))
    state = _state(inventory={})
    goal = CraftPotionsGoal(loadout=HEAL_LOADOUT, game_data=gd, state=state)
    actions = [a for a in _actions(gd) if not isinstance(a, GatherAction)]
    actions.append(FightAction(monster_code="biting_slime", locations=frozenset({(1, 0)})))
    declined: list[str] = []
    assert decompose(goal, state, gd, actions, NO_PROFILE_CONTEXT, declined) is None
    assert declined == [f"infeasible:{_HEAL}:no_route:{_INGREDIENT}"]


def test_an_undecomposable_batch_reports_the_inner_reason(monkeypatch):
    """The batch's own decline names what it lacks (no route to the
    ingredient), not just that the potion goal declined."""
    gd = _gd(with_boost=False, monster_level=18)
    gd._resource_drops = {}
    monkeypatch.setattr("artifactsmmo_cli.ai.goals.craft_potions.potion_batch",
                        lambda *_a: (_HEAL, 2, 2))
    state = _state(inventory={})
    goal = CraftPotionsGoal(loadout=HEAL_LOADOUT, game_data=gd, state=state)
    declined: list[str] = []
    assert decompose(goal, state, gd, _actions(gd), NO_PROFILE_CONTEXT, declined) is None
    assert declined == [f"infeasible:{_HEAL}:no_route:{_INGREDIENT}"]

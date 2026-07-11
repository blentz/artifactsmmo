"""Tests for GrindCharacterXPGoal (Phase G-E)."""

from sqlmodel import Session

from artifactsmmo_cli.ai.actions.combat import LOADOUT_PENALTY, FightAction
from artifactsmmo_cli.ai.actions.consumable import UseConsumableAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.optimize_loadout import SWAP_COST_PER_SLOT, OptimizeLoadoutAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.grind_character_xp import (
    PRIORITY_CEILING,
    PRIORITY_FLOOR,
    GrindCharacterXPGoal,
)
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.models import Session as SessionModel
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.planner import GOAPPlanner
from tests.test_ai.fixtures import make_state


def _gd_with_monster() -> GameData:
    gd = GameData()
    gd._monster_level = {"chicken": 1}
    return gd


def _seed(store: LearningStore, cycles: list[dict]) -> None:
    store.start_session()
    with Session(store._engine) as s:
        if not s.get(SessionModel, store._session_id):
            s.add(SessionModel(
                session_id=store._session_id,
                started_at="2026-05-18T00:00:00Z",
                character="hero",
            ))
        for kw in cycles:
            kw_with = dict(kw)
            kw_with["session_id"] = store._session_id
            s.add(Cycle(**kw_with))
        s.commit()


def _cycle(idx: int, goal: str, *, delta_xp: int = 0, delta_gold: int = 0) -> dict:
    return dict(
        ts=f"2026-05-18T00:{idx:02d}:00Z",
        cycle_index=idx,
        character="hero",
        selected_goal=goal,
        action_repr="X",
        action_class="X",
        outcome="ok",
        delta_xp=delta_xp,
        delta_gold=delta_gold,
        delta_hp=0,
        delta_inv_used=0,
        task_progress=0,
        task_total=0,
    )


class TestPriority:
    def test_zero_when_satisfied(self):
        goal = GrindCharacterXPGoal("chicken", initial_xp=100)
        state = make_state(xp=200, task_code=None)
        assert goal.value(state, _gd_with_monster()) == 0.0

    def test_floor_when_items_task_held(self):
        """Task-agnostic: an items task no longer forces 0; value depends only on satisfaction."""
        goal = GrindCharacterXPGoal("chicken")
        state = make_state(task_code="gudgeon", task_type="items", task_total=20, xp=0)
        assert goal.value(state, _gd_with_monster()) == PRIORITY_FLOOR

    def test_floor_without_history(self):
        goal = GrindCharacterXPGoal("chicken")
        state = make_state(task_code=None, xp=0)
        assert goal.value(state, _gd_with_monster(), history=None) == PRIORITY_FLOOR

    def test_floor_with_history_but_no_samples(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        goal = GrindCharacterXPGoal("chicken")
        state = make_state(task_code=None, xp=0)
        assert goal.value(state, _gd_with_monster(), store) == PRIORITY_FLOOR
        store.close()

    def test_bonus_caps_at_ceiling(self, tmp_path):
        """Even huge observed XP doesn't push priority above PRIORITY_CEILING."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        cycles = [_cycle(i, "FarmMonster(chicken)", delta_xp=100) for i in range(30)]
        _seed(store, cycles)
        goal = GrindCharacterXPGoal("chicken")
        state = make_state(task_code=None, xp=0, level=1)
        p = goal.value(state, _gd_with_monster(), store)
        store.close()
        assert p == PRIORITY_CEILING


class TestSatisfaction:
    def test_unsatisfied_at_initial(self):
        goal = GrindCharacterXPGoal("chicken", initial_xp=100)
        assert goal.is_satisfied(make_state(xp=100)) is False


class TestRelevantActions:
    def test_only_target_monster_fights(self):
        goal = GrindCharacterXPGoal("chicken")
        actions = [
            RestAction(),
            UseConsumableAction(_item_stats={}),
            FightAction(monster_code="chicken"),
            FightAction(monster_code="yellow_slime"),
            GatherAction(resource_code="ash_tree"),
        ]
        relevant = goal.relevant_actions(actions, make_state(), _gd_with_monster())
        codes = [a.monster_code for a in relevant if isinstance(a, FightAction)]
        assert codes == ["chicken"]
        assert any(isinstance(a, RestAction) for a in relevant)
        assert any(isinstance(a, UseConsumableAction) for a in relevant)
        assert not any(isinstance(a, GatherAction) for a in relevant)


class TestRepr:
    def test_repr_includes_target(self):
        assert repr(GrindCharacterXPGoal("yellow_slime")) == "GrindCharacterXP(yellow_slime)"


class TestXpSatisfaction:
    def test_satisfied_when_xp_up(self):
        state = make_state(xp=200, task_code=None, level=1,
                           equipment={"weapon_slot": "sword"}, inventory={})
        goal = GrindCharacterXPGoal("chicken", initial_xp=100)
        assert goal.is_satisfied(state) is True

    def test_not_satisfied_when_no_xp_gained(self):
        # xp NOT advanced
        state = make_state(xp=100, task_code=None, level=1,
                           equipment={"weapon_slot": "sword"}, inventory={})
        goal = GrindCharacterXPGoal("chicken", initial_xp=100)
        assert goal.is_satisfied(state) is False

    def test_xp_only_check(self):
        goal = GrindCharacterXPGoal("chicken", initial_xp=100)
        assert goal.is_satisfied(make_state(xp=200)) is True
        assert goal.is_satisfied(make_state(xp=50)) is False

    def test_grind_satisfied_on_xp_gain_even_if_loadout_suboptimal(self):
        """Satisfaction = XP gained. A non-optimal loadout (copper_dagger equipped
        while wooden_staff scores higher vs green_slime) must NOT keep the goal
        perpetually unsatisfied (the fb929887 coupling deadlock)."""
        goal = GrindCharacterXPGoal("green_slime", initial_xp=14)
        state = make_state(level=3, xp=24, equipment={"weapon_slot": "copper_dagger"})
        assert goal.is_satisfied(state) is True


def _combat_gd() -> GameData:
    gd = GameData()
    gd._monster_level = {"chicken": 1}
    gd._monster_locations = {"chicken": [(0, 0)]}
    gd._monster_attack = {"chicken": {"fire": 2}}
    gd._monster_resistance = {"chicken": {}}
    gd._monster_hp = {"chicken": 30}
    gd._item_stats = {
        "twig": ItemStats(code="twig", level=1, type_="weapon", attack={"fire": 1}),
        "sword": ItemStats(code="sword", level=1, type_="weapon", attack={"fire": 9}),
    }
    return gd


class TestFightCostPenalty:
    def test_fight_cost_penalized_when_loadout_suboptimal(self):
        gd = _combat_gd()
        fight = FightAction(monster_code="chicken", locations=frozenset({(0, 0)}))
        under = make_state(level=1, equipment={"weapon_slot": "twig"}, inventory={"sword": 1}, x=0, y=0)
        optimal = make_state(level=1, equipment={"weapon_slot": "sword"}, inventory={}, x=0, y=0)
        assert fight.cost(under, gd) == fight.cost(optimal, gd) + LOADOUT_PENALTY

    def test_planner_swaps_to_optimal_loadout_before_fighting(self):
        """FightAction.is_applicable hard-gates on the optimal loadout: a
        suboptimal equipped weapon (with a better one owned) forces the planner
        to front-load OptimizeLoadout(chicken) before Fight(chicken). An
        already-optimal loadout still fights directly with no swap."""
        gd = _combat_gd()
        actions = [
            FightAction(monster_code="chicken", locations=frozenset({(0, 0)})),
            OptimizeLoadoutAction(target_monster_code="chicken", game_data=gd),
        ]
        suboptimal = make_state(level=1, xp=0, task_code=None, hp=100, max_hp=100,
                                equipment={"weapon_slot": "twig"}, inventory={"sword": 1}, x=0, y=0)
        goal = GrindCharacterXPGoal("chicken", initial_xp=0)
        plan = GOAPPlanner().plan(suboptimal, goal, actions, gd, None)
        assert plan and repr(plan[0]) == "OptimizeLoadout(chicken)"
        assert "Fight(chicken)" in [repr(a) for a in plan]

        equipped = make_state(level=1, xp=0, task_code=None, hp=100, max_hp=100,
                              equipment={"weapon_slot": "sword"}, inventory={}, x=0, y=0)
        plan2 = GOAPPlanner().plan(equipped, goal, actions, gd, None)
        assert plan2 and repr(plan2[0]) == "Fight(chicken)"


def test_loadout_penalty_below_one_swap_cost():
    assert LOADOUT_PENALTY < SWAP_COST_PER_SLOT * 2


class TestDesiredState:
    def test_desired_state_xp_increments_initial(self):
        goal = GrindCharacterXPGoal("chicken", initial_xp=50)
        result = goal.desired_state(make_state(), GameData())
        assert result == {"xp": 60}


class TestTaskAgnosticValue:
    def test_value_nonzero_under_monster_task(self):
        # Under a monster task the grind IS the (retargeted) actuator; it must
        # value normally rather than self-suppress to 0.
        state = make_state(task_code="chicken", task_type="monsters",
                           task_total=20, task_progress=0, xp=0)
        goal = GrindCharacterXPGoal(target_monster="chicken", initial_xp=0)
        assert goal.value(state, GameData(), None) > 0.0

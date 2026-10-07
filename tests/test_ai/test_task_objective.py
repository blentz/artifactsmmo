"""The task objective (Phase 5-2c-iii-c-1): a held monsters task is a root
alternative of its own, so the turn order gives it turns.

Live 2026-10-05: R2D2 `ogre` 0/327, Lor `spider` 0/206 and C3P0 `pig` 5/104 were
held 15 days with no task fight. The task was no root (no turn) and its grey
monster was no fight (`FightAction`'s zero-XP gate, lifted for a task fight in
5-2c-iii-b)."""

import dataclasses
from unittest.mock import patch

import pytest

from artifactsmmo_cli.ai import strategy_driver as driver_mod
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.decisions import root as root_mod
from artifactsmmo_cli.ai.decisions.route import route_price
from artifactsmmo_cli.ai.goal_serialization import goal_from_dict, goal_to_dict
from artifactsmmo_cli.ai.goals.accept_task_goal import AcceptTaskGoal
from artifactsmmo_cli.ai.goals.task_cancel import TaskCancelGoal
from artifactsmmo_cli.ai.goals.task_exchange import TaskExchangeGoal
from artifactsmmo_cli.ai.goals.task_kills import PRIORITY, TaskKillsGoal
from artifactsmmo_cli.ai.plan_tree import _label
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.strategy_driver import objective_step_goal
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachTaskOutcome
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.prerequisite_graph import prerequisites
from artifactsmmo_cli.ai.tiers.strategy import root_category
from tests.test_ai.test_grey_farm import _gd, make_state


def _held(progress: int = 3, total: int = 10, **over):  # type: ignore[no-untyped-def]
    """A level-12 character holding a monsters task on the grey chicken (L1)."""
    state = make_state(level=12, skills={"alchemy": 5})
    return dataclasses.replace(state, **{"task_code": "chicken", "task_type": "monsters",
                                         "task_progress": progress, "task_total": total,
                                         **over})


class TestTaskKillsGoal:
    def test_one_kill_satisfies_it(self) -> None:
        goal = TaskKillsGoal("chicken", 3)
        assert not goal.is_satisfied(_held(3))
        assert goal.is_satisfied(_held(4))

    def test_a_met_or_dropped_task_satisfies_it(self) -> None:
        goal = TaskKillsGoal("chicken", 3)
        assert goal.is_satisfied(_held(10, 10))
        assert goal.is_satisfied(_held(3, task_code="cow"))

    def test_value_and_desired_state(self) -> None:
        goal = TaskKillsGoal("chicken", 3)
        gd = _gd()
        assert goal.value(_held(3), gd) == PRIORITY
        assert goal.value(_held(4), gd) == 0.0
        assert goal.desired_state(_held(3), gd) == {"task_progress": 4}

    def test_relevant_actions_are_the_task_fight_and_recovery(self) -> None:
        goal = TaskKillsGoal("chicken", 3)
        chicken = FightAction(monster_code="chicken", locations=frozenset({(1, 0)}))
        cow = FightAction(monster_code="cow", locations=frozenset({(2, 0)}))
        rest = RestAction()
        assert goal.relevant_actions([chicken, cow, rest], _held(), _gd()) == [chicken, rest]

    def test_a_grey_task_monster_plans(self) -> None:
        """The live shape: a task monster far below the character. 5-2c-iii-b
        lets the fight plan; this goal is what asks for it."""
        gd = _gd()
        chicken = FightAction(monster_code="chicken", locations=frozenset({(1, 0)}))
        plan = GOAPPlanner().plan(_held(3), TaskKillsGoal("chicken", 3), [chicken], gd)
        assert [repr(a) for a in plan] == ["Fight(chicken)"]

    def test_it_round_trips_through_the_plan_cache(self) -> None:
        goal = TaskKillsGoal("chicken", 3)
        back = goal_from_dict(goal_to_dict(goal), None)
        assert isinstance(back, TaskKillsGoal)
        assert repr(back) == repr(goal) == "TaskKills(chicken)"
        assert not back.is_satisfied(_held(3)) and back.is_satisfied(_held(4))


class TestReachTaskOutcome:
    def test_satisfied_when_met_or_not_this_task(self) -> None:
        gd = _gd()
        node = ReachTaskOutcome("chicken")
        assert not node.is_satisfied(_held(3), gd)
        assert node.is_satisfied(_held(10, 10), gd)
        assert node.is_satisfied(_held(3, task_code="cow"), gd)

    def test_every_meta_goal_dispatch_has_an_arm(self) -> None:
        node = ReachTaskOutcome("chicken")
        assert prerequisites(node, _held(), _gd()) == []
        assert root_category(node) == "task"
        assert _label(node) == ("task chicken", "task")

    def test_its_price_is_the_remaining_kills(self) -> None:
        gd = _gd()
        node = ReachTaskOutcome("chicken")
        assert route_price(node, _held(10, 10), gd, NO_PROFILE_CONTEXT, None) == 0
        one = route_price(node, _held(9, 10), gd, NO_PROFILE_CONTEXT, None)
        seven = route_price(node, _held(3, 10), gd, NO_PROFILE_CONTEXT, None)
        assert 1 <= one <= seven
        assert seven >= 7

    def test_its_step_is_one_more_kill(self) -> None:
        gd = _gd()
        node = ReachTaskOutcome("chicken")
        goal = objective_step_goal(node, _held(3), gd, NO_PROFILE_CONTEXT)
        assert isinstance(goal, TaskKillsGoal) and repr(goal) == "TaskKills(chicken)"
        assert objective_step_goal(node, _held(10, 10), gd, NO_PROFILE_CONTEXT) is None


class TestTaskRoot:
    def test_no_root_without_an_unmet_task(self) -> None:
        gd = _gd()
        assert root_mod._task_root(make_state(level=12), gd, NO_PROFILE_CONTEXT, None) is None
        assert root_mod._task_root(_held(10, 10), gd, NO_PROFILE_CONTEXT, None) is None

    def test_a_winnable_task_is_its_own_root(self) -> None:
        with patch.object(root_mod, "is_winnable", return_value=True):
            got = root_mod._task_root(_held(), _gd(), NO_PROFILE_CONTEXT, None)
        assert got == ReachTaskOutcome("chicken")

    def test_an_unwinnable_task_asks_for_gear(self) -> None:
        """USER 2026-10-05: the task asks for the gear that beats its monster."""
        with (patch.object(root_mod, "is_winnable", return_value=False),
              patch.object(root_mod, "deficit_upgrade_target",
                           return_value=("iron_sword", "weapon_slot")) as deficit):
            got = root_mod._task_root(_held(), _gd(), NO_PROFILE_CONTEXT, None)
        assert got == ObtainItem("iron_sword", 1, slot="weapon_slot")
        actions_of = deficit.call_args.kwargs["actions_of"]
        with patch.object(root_mod._route, "route_price", return_value=17) as price:
            assert actions_of("iron_sword", "weapon_slot") == 17
        assert price.call_args.args[0] == ObtainItem("iron_sword", 1, slot="weapon_slot")

    def test_an_unwinnable_task_no_gear_closes_waits(self) -> None:
        with (patch.object(root_mod, "is_winnable", return_value=False),
              patch.object(root_mod, "deficit_upgrade_target", return_value=None)):
            assert root_mod._task_root(_held(), _gd(), NO_PROFILE_CONTEXT, None) is None

    def test_the_walk_offers_it_after_the_trunk(self) -> None:
        gd = _gd()
        state = _held()
        with patch.object(root_mod, "_task_root", return_value=ReachTaskOutcome("chicken")):
            resolution = root_mod.resolve_root(state, gd, CharacterObjective.from_game_data(gd),
                                               NO_PROFILE_CONTEXT, None)
        offered = [resolution.root, *resolution.alternatives]
        assert ReachTaskOutcome("chicken") in resolution.alternatives
        trunk = next(i for i, a in enumerate(offered) if isinstance(a, ReachCharLevel))
        assert offered.index(ReachTaskOutcome("chicken")) == trunk + 1


class TestWorthCancelFold:
    """Phase 5-2c-iii-c-2 #5: TASK_CANCEL (and low-yield before it) retired;
    a worthless task with a pocket coin is cancelled on the task objective's
    turn (USER 2026-10-07, `task_worth_core`)."""

    def test_a_cancel_due_task_offers_the_objective(self) -> None:
        """An unwinnable task no gear closes: no other arm offers it, so only
        the cancel can."""
        with (patch.object(root_mod, "is_winnable", return_value=False),
              patch.object(root_mod, "deficit_upgrade_target", return_value=None)):
            with patch.object(root_mod._route, "task_cancel_due", return_value=True):
                got = root_mod._task_root(_held(), _gd(), NO_PROFILE_CONTEXT, None)
            assert got == ReachTaskOutcome("chicken")
            with patch.object(root_mod._route, "task_cancel_due", return_value=False):
                assert root_mod._task_root(_held(), _gd(), NO_PROFILE_CONTEXT, None) is None

    def test_its_step_is_the_cancel(self) -> None:
        node = ReachTaskOutcome("chicken")
        with patch.object(driver_mod, "task_cancel_due", return_value=True):
            goal = objective_step_goal(node, _held(), _gd(), NO_PROFILE_CONTEXT)
        assert isinstance(goal, TaskCancelGoal)

    def test_the_funnel_asks_the_worth_verdict(self) -> None:
        with patch("artifactsmmo_cli.ai.decisions.route.held_task_cancel_due",
                   return_value=True) as due:
            assert root_mod._route.task_cancel_due(_held(), _gd(), NO_PROFILE_CONTEXT, None)
        assert due.called


@pytest.fixture
def _cancel_not_due(monkeypatch):  # type: ignore[no-untyped-def]
    """A held task with coins has its worth read (the cancel); these cases are
    about the exchange, so the cancel is pinned not due."""
    monkeypatch.setattr(root_mod._route, "task_cancel_due", lambda *a: False)
    monkeypatch.setattr(driver_mod, "task_cancel_due", lambda *a: False)


@pytest.mark.usefixtures("_cancel_not_due")
class TestExchangeFold:
    """Phase 5-2c-iii-c-2 #2: TASK_EXCHANGE retired; earned coins are the task
    objective's to exchange, task held or not."""

    def test_coins_offer_the_objective_with_or_without_a_task(self) -> None:
        from_ctx = dataclasses.replace(NO_PROFILE_CONTEXT, task_exchange_min_coins=3)
        rich = dataclasses.replace(make_state(level=12), inventory={"tasks_coin": 3})
        assert root_mod._task_root(rich, _gd(), from_ctx, None) == ReachTaskOutcome(None)
        held = dataclasses.replace(_held(task_type="items"), inventory={"tasks_coin": 3})
        assert root_mod._task_root(held, _gd(), from_ctx, None) == ReachTaskOutcome("chicken")
        poor = dataclasses.replace(make_state(level=12), inventory={"tasks_coin": 2})
        assert root_mod._task_root(poor, _gd(), from_ctx, None) is None

    def test_the_offline_context_offers_no_exchange_on_zero_coins(self) -> None:
        """`NO_PROFILE_CONTEXT`'s floor is one coin, production's own default:
        a zero floor read `coins >= 0` and fired for every coinless character
        (44 of 44 offline scenarios, before 2026-08)."""
        assert root_mod._task_root(make_state(level=12), _gd(), NO_PROFILE_CONTEXT, None) is None

    def test_no_task_and_no_exchange_has_no_step(self) -> None:
        assert objective_step_goal(ReachTaskOutcome(None), make_state(level=12), _gd(),
                                   NO_PROFILE_CONTEXT) is None
        assert not ReachTaskOutcome(None).is_satisfied(make_state(level=12), _gd())

    def test_the_no_task_objective_prices_one_exchange_and_labels_coins(self) -> None:
        node = ReachTaskOutcome(None)
        assert route_price(node, make_state(level=12), _gd(), NO_PROFILE_CONTEXT, None) == 1
        assert _label(node) == ("task (coins)", "task")

    def test_the_step_is_the_exchange(self) -> None:
        ctx = dataclasses.replace(NO_PROFILE_CONTEXT, task_exchange_min_coins=3)
        rich = dataclasses.replace(_held(3), inventory={"tasks_coin": 3})
        goal = objective_step_goal(ReachTaskOutcome("chicken"), rich, _gd(), ctx)
        assert isinstance(goal, TaskExchangeGoal)


class TestAcceptFold:
    """Phase 5-2c-iii-c-2 #3: ACCEPT_TASK retired; USER: no task is drawn until
    the task objective has its turn. The owed draw is the objective's step."""

    def test_an_owed_draw_offers_the_objective(self) -> None:
        owed = dataclasses.replace(NO_PROFILE_CONTEXT, draw_owed=True)
        assert root_mod._task_root(make_state(level=12), _gd(), owed, None) == ReachTaskOutcome(None)
        assert root_mod._task_root(make_state(level=12), _gd(), NO_PROFILE_CONTEXT, None) is None

    def test_its_step_is_the_accept_ahead_of_the_exchange(self) -> None:
        owed = dataclasses.replace(NO_PROFILE_CONTEXT, draw_owed=True, task_exchange_min_coins=1)
        rich = dataclasses.replace(make_state(level=12), inventory={"tasks_coin": 3})
        goal = objective_step_goal(ReachTaskOutcome(None), rich, _gd(), owed)
        assert isinstance(goal, AcceptTaskGoal)


class TestItemsTaskIsWorked:
    """Phase 5-2c-iii-c-2 #4/#5: a held, unmet items task not cancelled for its
    worth is worked on the task objective's turn (the PIVOT gate is gone)."""

    def test_a_held_items_task_offers_the_objective(self) -> None:
        held = _held(task_type="items")
        assert root_mod._task_root(held, _gd(), NO_PROFILE_CONTEXT, None) == ReachTaskOutcome("chicken")
        met = _held(10, 10, task_type="items")
        assert root_mod._task_root(met, _gd(), NO_PROFILE_CONTEXT, None) is None

    def test_its_step_is_the_pursuit(self) -> None:
        goal = objective_step_goal(ReachTaskOutcome("chicken"), _held(task_type="items"),
                                   _gd(), NO_PROFILE_CONTEXT)
        assert repr(goal) == "PursueTask(chicken)"

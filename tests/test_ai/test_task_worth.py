"""A task's worth from live data (Phase 5-2c-iii-c-2 #5, increment 2;
`docs/PLAN_task_value.md`). The verdict is the proved `task_worth_core`; these
pin the inputs it is read from."""

import dataclasses

import pytest

import artifactsmmo_cli.ai.task_worth as mod
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.task_horizon import HORIZON_GEAR, HORIZON_OUT_OF_REACH, TaskHorizon
from artifactsmmo_cli.ai.task_worth import held_task_cancel_due, short_items, task_worth_for
from artifactsmmo_cli.ai.task_worth_core import TaskWorth
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._crafting_recipes = {"wolf_cloak": {"wolf_hair": 4, "cloth": 2}, "cloth": {"thread": 3}}
    gd._craft_yields = {"wolf_cloak": 1, "cloth": 1}
    gd._monster_drops = {"wolf": [("wolf_hair", 2, 1, 1)], "sheep": [("wool", 2, 1, 1)]}
    gd._monster_min_gold.update({"wolf": 10, "sheep": 0, "imp": 20})
    gd._monster_max_gold.update({"wolf": 30, "sheep": 0, "imp": 40})
    gd._task_gold_rewards = {"wolf": 300, "sheep": 300, "copper_bar": 300}
    return gd


@pytest.fixture
def _fixed_fight(monkeypatch):  # type: ignore[no-untyped-def]
    """Two cycles a kill, every fight; the horizon reads the fight as won."""
    monkeypatch.setattr(mod, "expected_damage_per_fight", lambda s, g, m: 0)
    monkeypatch.setattr(mod, "cycles_per_kill", lambda dmg, hp: 2.0)
    monkeypatch.setattr(mod, "resolve_task_horizon", lambda s, g: None)
    monkeypatch.setattr(mod, "task_advances_progression", lambda s, g: False)


class TestShortItems:
    def test_the_closure_less_the_bag_and_bank(self) -> None:
        ctx = dataclasses.replace(NO_PROFILE_CONTEXT, target_gear=frozenset({"wolf_cloak"}))
        state = make_state(inventory={"cloth": 2}, bank_items={"wolf_hair": 1})
        assert short_items(state, _gd(), ctx) == {"wolf_cloak", "wolf_hair"}

    def test_a_banked_supply_is_not_short(self) -> None:
        """Live 2026-10-07: wolf, pig and skeleton read "aligned" while the bank
        held their drops."""
        ctx = dataclasses.replace(NO_PROFILE_CONTEXT, target_gear=frozenset({"wolf_cloak"}))
        state = make_state(bank_items={"wolf_hair": 4, "thread": 6})
        assert short_items(state, _gd(), ctx) == {"wolf_cloak", "cloth"}

    def test_worn_gear_needs_nothing(self) -> None:
        ctx = dataclasses.replace(NO_PROFILE_CONTEXT, near_term_targets=frozenset({"wolf_cloak"}))
        state = make_state(equipment={"body_armor_slot": "wolf_cloak"})
        assert short_items(state, _gd(), ctx) == frozenset()


@pytest.mark.usefixtures("_fixed_fight")
class TestTaskWorthFor:
    def test_a_short_drop_is_a_reason(self) -> None:
        ctx = dataclasses.replace(NO_PROFILE_CONTEXT, target_gear=frozenset({"wolf_cloak"}))
        worth = task_worth_for("wolf", "monsters", 10, make_state(level=30), _gd(), ctx, None)
        assert worth == TaskWorth(xp=False, gold=False, drops=True)

    def test_a_grey_drop_nobody_needs_is_worthless(self) -> None:
        worth = task_worth_for("sheep", "monsters", 10, make_state(level=30), _gd(),
                               NO_PROFILE_CONTEXT, None)
        assert not worth.any()

    def test_gold_short_and_the_faster_source(self) -> None:
        """wolf: (300 + 10 * 20) / (10 * 2) = 25 gold a cycle, beating imp's 30/2 = 15."""
        ctx = dataclasses.replace(NO_PROFILE_CONTEXT, gold_short=True, combat_monster="imp")
        assert task_worth_for("wolf", "monsters", 10, make_state(), _gd(), ctx, None).gold
        rich = dataclasses.replace(ctx, gold_short=False)
        assert not task_worth_for("wolf", "monsters", 10, make_state(), _gd(), rich, None).gold

    def test_no_grind_target_means_no_other_gold(self) -> None:
        ctx = dataclasses.replace(NO_PROFILE_CONTEXT, gold_short=True, combat_monster=None)
        assert task_worth_for("wolf", "monsters", 10, make_state(), _gd(), ctx, None).gold

    def test_out_of_reach_is_worthless(self, monkeypatch) -> None:
        monkeypatch.setattr(mod, "task_advances_progression", lambda s, g: True)
        monkeypatch.setattr(mod, "resolve_task_horizon",
                            lambda s, g: TaskHorizon("wolf", HORIZON_OUT_OF_REACH, None))
        assert not task_worth_for("wolf", "monsters", 10, make_state(), _gd(),
                                  NO_PROFILE_CONTEXT, None).any()
        monkeypatch.setattr(mod, "resolve_task_horizon", lambda s, g: TaskHorizon("wolf", HORIZON_GEAR, None))
        assert task_worth_for("wolf", "monsters", 10, make_state(), _gd(),
                              NO_PROFILE_CONTEXT, None).xp

    def test_an_items_task_earns_its_reward_over_its_actions(self, monkeypatch) -> None:
        monkeypatch.setattr(mod, "acquisition_actions", lambda *a, **k: 20)
        ctx = dataclasses.replace(NO_PROFILE_CONTEXT, gold_short=True, combat_monster="imp")
        worth = task_worth_for("copper_bar", "items", 10, make_state(), _gd(), ctx, None)
        assert worth == TaskWorth(xp=False, gold=False, drops=False)  # 300/20 = 15, not > 15
        monkeypatch.setattr(mod, "acquisition_actions", lambda *a, **k: 0)
        assert task_worth_for("copper_bar", "items", 10, make_state(), _gd(), ctx, None).gold

    def test_the_kill_is_read_for_the_task_monster(self, monkeypatch) -> None:
        seen = {}

        def progression(state, game_data):  # type: ignore[no-untyped-def]
            seen.update(code=state.task_code, total=state.task_total, progress=state.task_progress)
            return True

        monkeypatch.setattr(mod, "task_advances_progression", progression)
        task_worth_for("wolf", "monsters", 7, make_state(), _gd(), NO_PROFILE_CONTEXT, None)
        assert seen == {"code": "wolf", "total": 7, "progress": 0}


@pytest.mark.usefixtures("_fixed_fight")
class TestHeldTaskCancelDue:
    def _held(self, **over):  # type: ignore[no-untyped-def]
        base = dict(level=30, task_code="sheep", task_type="monsters", task_progress=3,
                    task_total=10, inventory={"tasks_coin": 1})
        return make_state(**{**base, **over})

    def test_a_worthless_task_with_a_coin_is_cancelled(self) -> None:
        assert held_task_cancel_due(self._held(), _gd(), NO_PROFILE_CONTEXT, None)

    def test_no_coin_no_cancel(self) -> None:
        assert not held_task_cancel_due(self._held(inventory={}), _gd(), NO_PROFILE_CONTEXT, None)

    def test_no_task_or_a_met_one_is_never_cancelled(self) -> None:
        assert not held_task_cancel_due(self._held(task_code=None), _gd(), NO_PROFILE_CONTEXT, None)
        assert not held_task_cancel_due(self._held(task_progress=10), _gd(), NO_PROFILE_CONTEXT, None)

    def test_a_worthy_task_is_kept(self) -> None:
        ctx = dataclasses.replace(NO_PROFILE_CONTEXT, target_gear=frozenset({"wolf_cloak"}))
        assert not held_task_cancel_due(self._held(task_code="wolf"), _gd(), ctx, None)


class TestPlayerGoldShort:
    def _player(self, gold: int, bank_gold: int, root) -> GamePlayer:  # type: ignore[no-untyped-def]
        player = GamePlayer(character="hero", history=None)
        player.state = make_state(gold=gold, bank_gold=bank_gold)
        player.game_data = GameData()
        player._last_decision = None if root is None else type("D", (), {"chosen_root": root})()
        return player

    def test_short_of_the_larger_need(self, monkeypatch) -> None:
        monkeypatch.setattr("artifactsmmo_cli.ai.player.progression_reserve", lambda s, g: 100)
        monkeypatch.setattr("artifactsmmo_cli.ai.player.closure_gold_demand", lambda n, s, g: 500)
        root = ObtainItem("iron_sword", 1)
        assert self._player(200, 200, root)._gold_short()          # 400 < 500
        assert not self._player(300, 200, root)._gold_short()      # 500 = 500
        assert not self._player(200, 0, None)._gold_short()        # 200 vs reserve 100

    def test_a_root_that_buys_nothing_needs_only_the_reserve(self, monkeypatch) -> None:
        monkeypatch.setattr("artifactsmmo_cli.ai.player.progression_reserve", lambda s, g: 100)
        assert self._player(50, 0, ReachCharLevel(40))._gold_short()

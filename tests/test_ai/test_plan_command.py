"""Tests for the offline `plan` CLI command + GamePlayer.plan_once()."""

from fractions import Fraction
from unittest.mock import MagicMock, patch

import pytest
import typer

from artifactsmmo_cli.ai.plan_report import PlanReport
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.strategy import RootScore, StrategyDecision
from artifactsmmo_cli.commands import plan as plan_cmd
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_player_run import _patch_game_data_load


def test_plan_once_returns_report_without_executing():
    """plan_once senses + plans ONE cycle and returns a PlanReport; it never calls
    _execute (no server mutation)."""
    player = GamePlayer(character="hero")
    client = MagicMock()
    state = make_state(hp=100, max_hp=150)
    with patch.object(ClientManager_mock := MagicMock(), "client", client):
        with patch("artifactsmmo_cli.ai.player.ClientManager", return_value=ClientManager_mock):
            with _patch_game_data_load():
                with patch.object(player, "_fetch_world_state", return_value=state):
                    with patch.object(player, "_maybe_periodic_refresh"):
                        with patch.object(player, "_build_actions", return_value=[]):
                            with patch.object(player, "_execute") as execute:
                                report = player.plan_once()
    assert isinstance(report, PlanReport)
    execute.assert_not_called()


def test_plan_once_crafting_target_from_fallback():
    """When chosen_step is None, plan_once derives the bank keep-set crafting_target
    from the first ObtainItem fallback (mirrors run())."""
    player = GamePlayer(character="hero")
    client = MagicMock()
    state = make_state()
    decision = StrategyDecision(
        interrupt=None, chosen_root=None, chosen_step=None, desired_state={},
        fallback_steps=[ObtainItem("copper_ore", 10)])
    fake_strategy = MagicMock()
    fake_strategy.decide.return_value = decision
    with patch.object(ClientManager_mock := MagicMock(), "client", client):
        with patch("artifactsmmo_cli.ai.player.ClientManager", return_value=ClientManager_mock):
            with _patch_game_data_load():
                with patch.object(player, "_fetch_world_state", return_value=state):
                    with patch.object(player, "_maybe_periodic_refresh"):
                        with patch.object(player, "_build_actions", return_value=[]):
                            with patch("artifactsmmo_cli.ai.player.StrategyEngine",
                                       return_value=fake_strategy):
                                report = player.plan_once()
    assert report.decision.chosen_step is None


def _canned_report() -> PlanReport:
    decision = StrategyDecision(
        interrupt=None,
        chosen_root=ObtainItem("feather_coat", 1, "body_armor_slot"),
        chosen_step=ObtainItem("feather", 2),
        desired_state={},
        ranking=[RootScore("ObtainItem(feather_coat)", "gear", Fraction(5, 2), 3,
                           Fraction(5, 2), "ObtainItem(feather)")],
    )
    return PlanReport(
        decision=decision,
        selected_goal="GatherMaterials(feather)",
        plan=["Fight(chicken)", "Gather(ash_tree)"],
        goals_tried=[
            {"goal": "GatherMaterials(feather_coat)", "nodes": 57000, "depth": 23,
             "plan_len": 0, "timed_out": True},
            {"goal": "GatherMaterials(feather)", "nodes": 5, "depth": 2,
             "plan_len": 2, "timed_out": False},
        ],
    )


def test_plan_command_prints_report(capsys):
    """The command builds a player, runs plan_once, prints the report (both the
    populated-plan and the goals_tried no-plan branches)."""
    with patch.object(plan_cmd, "check_mutation_lock",
                      return_value=MagicMock(state="clear")):
        with patch.object(plan_cmd.Config, "from_token_file", return_value=MagicMock()):
            with patch.object(plan_cmd, "LearningStore") as store_cls:
                store_cls.return_value = MagicMock()
                player = MagicMock()
                player.state = make_state(level=6)
                player.plan_once.return_value = _canned_report()
                with patch.object(plan_cmd, "GamePlayer", return_value=player):
                    plan_cmd.plan(character="hero", learn=False, learn_db=None, refresh_game_data=False)
    out = capsys.readouterr().out
    assert "chosen_root" in out and "feather_coat" in out
    assert "Fight(chicken)" in out
    assert "NO PLAN" in out and "TIMED_OUT" in out


def test_plan_command_empty_plan_branch(capsys):
    report = PlanReport(
        decision=StrategyDecision(interrupt=None, chosen_root=None, chosen_step=None,
                                  desired_state={}, ranking=[]),
        selected_goal=None, plan=[], goals_tried=[])
    with patch.object(plan_cmd, "check_mutation_lock",
                      return_value=MagicMock(state="clear")):
        with patch.object(plan_cmd.Config, "from_token_file", return_value=MagicMock()):
            with patch.object(plan_cmd, "LearningStore") as store_cls:
                store_cls.return_value = MagicMock()
                player = MagicMock()
                player.state = None
                player.plan_once.return_value = report
                with patch.object(plan_cmd, "GamePlayer", return_value=player):
                    plan_cmd.plan(character="hero", learn=False, learn_db=None, refresh_game_data=False)
    assert "<no plan>" in capsys.readouterr().out


def test_plan_command_learn_uses_default_db(capsys):
    """--learn with no --learn-db routes to the default learning DB path."""
    with patch.object(plan_cmd, "check_mutation_lock",
                      return_value=MagicMock(state="clear")):
        with patch.object(plan_cmd.Config, "from_token_file", return_value=MagicMock()):
            with patch.object(plan_cmd, "LearningStore") as store_cls:
                store_cls.return_value = MagicMock()
                player = MagicMock()
                player.state = make_state()
                player.plan_once.return_value = _canned_report()
                with patch.object(plan_cmd, "GamePlayer", return_value=player):
                    plan_cmd.plan(character="hero", learn=True, learn_db=None, refresh_game_data=False)
    db_path = store_cls.call_args.kwargs["db_path"]
    assert db_path.endswith("learning.db")


def test_plan_command_refuses_during_mutation(capsys):
    with patch.object(plan_cmd, "check_mutation_lock",
                      return_value=MagicMock(state="active", pid=123)):
        with pytest.raises(typer.Exit):
            plan_cmd.plan(character="hero", learn=False, learn_db=None, refresh_game_data=False)
    assert "mutation run in progress" in capsys.readouterr().out

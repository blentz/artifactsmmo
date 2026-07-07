"""Tests for the offline `plan` CLI command + GamePlayer.plan_once()."""

import contextlib
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


def _plan_once_mocks(player, state):
    """Context-manager stack shared by plan_once tests: mock the client, game data,
    sense, refresh, and action build so no server is touched."""
    cm = MagicMock()
    return [
        patch.object(cm, "client", MagicMock()),
        patch("artifactsmmo_cli.ai.player.ClientManager", return_value=cm),
        _patch_game_data_load(),
        patch.object(player, "_fetch_world_state", return_value=state),
        patch.object(player, "_maybe_periodic_refresh"),
        patch.object(player, "_build_actions", return_value=[]),
    ]


def test_plan_once_seeds_doomed_memo_for_diagnostics():
    """plan_once(doomed=[...]) marks those goal reprs in the arbiter's in-memory memo
    BEFORE selecting, so an offline plan reproduces a live doomed-memo suppression
    (e.g. a combat goal stuck doomed) that the fresh CLI otherwise never carries.
    The injection is echoed on the report so the printed plan is honest about it."""
    player = GamePlayer(character="hero")
    state = make_state()
    with contextlib.ExitStack() as stack:
        for cm in _plan_once_mocks(player, state):
            stack.enter_context(cm)
        report = player.plan_once(doomed=["GatherMaterials(copper_ore)"])
    assert report.simulated_doomed == ("GatherMaterials(copper_ore)",)
    assert player._arbiter._memo.is_doomed(
        "GatherMaterials(copper_ore)", state, player._cycle_counter)


def test_plan_once_seeds_committed_for_diagnostics():
    """plan_once(committed=REPR) seeds the arbiter's sticky commitment before select,
    reproducing a live committed-goal hold; the injection is echoed on the report."""
    player = GamePlayer(character="hero")
    state = make_state()
    with contextlib.ExitStack() as stack:
        for cm in _plan_once_mocks(player, state):
            stack.enter_context(cm)
        report = player.plan_once(committed="GrindCharacterXP(green_slime)")
    assert report.simulated_committed == "GrindCharacterXP(green_slime)"


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


def test_plan_once_reports_drop_input_winnability():
    """plan_once reports, for a gear chosen_root, each monster-drop recipe input and
    whether it's winnable with the live loadout (feather <- chicken)."""
    from artifactsmmo_cli.ai.game_data import GameData, ItemStats
    gd = GameData()
    gd._item_stats = {
        "feather_coat": ItemStats(code="feather_coat", level=1, type_="body_armor"),
        "feather": ItemStats(code="feather", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"feather_coat": {"feather": 5}}
    gd._monster_drops = {"chicken": [("feather", 8, 1, 1)]}
    gd._monster_level = {"chicken": 1}
    gd._monster_locations = {"chicken": [(0, 1)]}
    from tests.test_ai._monster_fixture import fill_monster_stat_defaults
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {"chicken": 10}
    state = make_state(level=6, x=0, y=0, hp=200, max_hp=200, attack={"fire": 40})
    decision = StrategyDecision(
        interrupt=None, chosen_root=ObtainItem("feather_coat", 1, "body_armor_slot"),
        chosen_step=ObtainItem("feather", 5), desired_state={})
    fake_strategy = MagicMock()
    fake_strategy.decide.return_value = decision
    player = GamePlayer(character="hero")
    with patch.object(ClientManager_mock := MagicMock(), "client", MagicMock()):
        with patch("artifactsmmo_cli.ai.player.ClientManager", return_value=ClientManager_mock):
            with patch("artifactsmmo_cli.ai.player.GameData.load", return_value=gd):
                with patch.object(player, "_fetch_world_state", return_value=state):
                    with patch.object(player, "_maybe_periodic_refresh"):
                        with patch.object(player, "_build_actions", return_value=[]):
                            with patch("artifactsmmo_cli.ai.player.StrategyEngine",
                                       return_value=fake_strategy):
                                report = player.plan_once()
    assert report.drop_inputs == [
        {"item": "feather", "droppers": ["chicken"], "winnable": ["chicken"]}]


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
             "plan_len": 0, "timed_out": True, "node_capped": True},
            {"goal": "GatherMaterials(feather)", "nodes": 5, "depth": 2,
             "plan_len": 2, "timed_out": False},
        ],
        drop_inputs=[
            {"item": "feather", "droppers": ["chicken"], "winnable": ["chicken"]},
            {"item": "scale", "droppers": ["dragon"], "winnable": []},
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
    # node-cap truncation must be visible distinctly from a wall-clock timeout
    assert "NODE_CAP" in out
    # drop-input winnability section: a winnable feather + an unwinnable scale.
    assert "WINNABLE via ['chicken']" in out
    assert "NOT WINNABLE" in out


def test_plan_command_passes_and_prints_simulated_state(capsys):
    """`--doom` / `--committed` thread into plan_once and the report echoes them; the
    printed report shows a SIMULATED section so the offline plan is honest about the
    injected in-memory arbiter state."""
    report = PlanReport(
        decision=StrategyDecision(interrupt=None, chosen_root=None, chosen_step=None,
                                  desired_state={}, ranking=[]),
        selected_goal=None, plan=[], goals_tried=[],
        simulated_doomed=("GrindCharacterXP(green_slime)",),
        simulated_committed="ReachSkillLevel(jewelrycrafting)")
    with patch.object(plan_cmd, "check_mutation_lock",
                      return_value=MagicMock(state="clear")):
        with patch.object(plan_cmd.Config, "from_token_file", return_value=MagicMock()):
            with patch.object(plan_cmd, "LearningStore") as store_cls:
                store_cls.return_value = MagicMock()
                player = MagicMock()
                player.state = make_state(level=4)
                player.plan_once.return_value = report
                with patch.object(plan_cmd, "GamePlayer", return_value=player):
                    plan_cmd.plan(character="hero", learn=False, learn_db=None,
                                  refresh_game_data=False,
                                  doom=["GrindCharacterXP(green_slime)"],
                                  committed="ReachSkillLevel(jewelrycrafting)")
    assert player.plan_once.call_args.kwargs == {
        "doomed": ["GrindCharacterXP(green_slime)"],
        "committed": "ReachSkillLevel(jewelrycrafting)"}
    out = capsys.readouterr().out
    assert "SIMULATED" in out
    assert "GrindCharacterXP(green_slime)" in out
    assert "ReachSkillLevel(jewelrycrafting)" in out


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


def test_plan_command_scenario_runs_offline(capsys):
    """--scenario plans a named synthetic character with no API client:
    no ClientManager, no GamePlayer._initialize."""
    with patch.object(plan_cmd, "check_mutation_lock",
                      return_value=MagicMock(state="clear")):
        # The scenario branch returns BEFORE Config/LearningStore/GamePlayer
        # API setup — patching from_token_file proves no live path ran.
        with patch.object(plan_cmd.Config, "from_token_file") as cfg:
            plan_cmd.plan(character="ignored", learn=False, learn_db=None,
                          refresh_game_data=False, scenario="l1_fresh")
            cfg.assert_not_called()
    out = capsys.readouterr().out
    assert "scenario: l1_fresh" in out
    assert "goals_tried" in out


def test_plan_command_scenario_unknown_name_exits(capsys):
    with patch.object(plan_cmd, "check_mutation_lock",
                      return_value=MagicMock(state="clear")):
        with pytest.raises(typer.Exit):
            plan_cmd.plan(character="ignored", learn=False, learn_db=None,
                          refresh_game_data=False, scenario="nope")
    assert "unknown scenario" in capsys.readouterr().out

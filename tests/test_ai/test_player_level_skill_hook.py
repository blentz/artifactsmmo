"""When plan[0] is a LevelSkill, the player runs ONE grind-cycle leg instead of
calling LevelSkill.execute (which raises). Uses a fake client + patched planner
so no live API and a deterministic sub-plan leg."""

from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "trinket": ItemStats(code="trinket", level=1, type_="resource",
                             subtype="craft", crafting_skill="gearcrafting",
                             crafting_level=1),
        "gear_ore": ItemStats(code="gear_ore", level=1, type_="resource",
                              subtype="mob"),
    }
    gd._crafting_recipes = {"trinket": {"gear_ore": 1}}
    gd._resource_drops = {"gear_rocks": "gear_ore"}
    gd._resource_skill = {"gear_rocks": ("mining", 1)}
    gd._resource_locations = {"gear_rocks": [(3, 3)]}
    gd._workshop_locations = {"gearcrafting": (2, 2)}
    return gd


def _under_skill_player() -> GamePlayer:
    gd = _gd()
    player = GamePlayer(character="hero")
    player.game_data = gd
    player.state = scenario_state(
        ScenarioCharacter(name="hero", level=5, skills={"gearcrafting": 1}), gd)
    return player


def test_level_skill_step_runs_grind_leg_not_execute() -> None:
    """_execute(LevelSkill) plans the skill_grind goal and executes its FIRST
    leg (a GatherAction) — never LevelSkill.execute (which raises)."""
    player = _under_skill_player()
    leg = GatherAction(resource_code="gear_rocks",
                       locations=frozenset({(3, 3)}))
    advanced = replace(player.state, x=3, y=3)
    client = MagicMock()

    with patch.object(player, "_build_actions", return_value=[]), \
            patch.object(player.planner, "plan",
                         return_value=[leg]) as plan_spy, \
            patch.object(GatherAction, "execute",
                         return_value=advanced) as gather_exec, \
            patch.object(LevelSkill, "execute") as level_exec:
        new_state, outcome = player._execute(
            LevelSkill("gearcrafting", 5), client)

    assert outcome == "ok"
    assert new_state is advanced
    gather_exec.assert_called_once()
    level_exec.assert_not_called()
    # The planner was asked to satisfy the skill_grind GatherMaterials goal.
    planned_goal = plan_spy.call_args.args[1]
    assert isinstance(planned_goal, GatherMaterialsGoal)
    assert planned_goal.skill_grind is True


def test_level_skill_step_raises_when_no_rung() -> None:
    """Unreachable in a correct plan (is_applicable gates it): no grind rung ->
    the guard raises rather than silently no-op."""
    player = _under_skill_player()
    client = MagicMock()
    with patch("artifactsmmo_cli.ai.player.next_grind_goal", return_value=None):
        with pytest.raises(RuntimeError, match="no grind rung"):
            player._execute(LevelSkill("gearcrafting", 5), client)


def test_level_skill_step_raises_when_grind_produces_no_leg() -> None:
    """Unreachable in a correct plan: a rung exists but the grind goal yields no
    plan -> the guard raises."""
    player = _under_skill_player()
    client = MagicMock()
    with patch.object(player, "_build_actions", return_value=[]), \
            patch.object(player.planner, "plan", return_value=[]):
        with pytest.raises(RuntimeError, match="no leg"):
            player._execute(LevelSkill("gearcrafting", 5), client)

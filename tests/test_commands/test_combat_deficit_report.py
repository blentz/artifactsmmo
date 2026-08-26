"""Tests for the read-only `combat-deficit` CLI command.

The command is the ORACLE for the `combat_deficit` work: every later increment
changes what the bot DOES about a losing fight, and this is how that change is
checked against live state without restarting the fleet.
"""

from unittest.mock import MagicMock, patch

import pytest
import typer

from artifactsmmo_cli.ai.combat_deficit import CombatDeficit, DeficitStep
from artifactsmmo_cli.commands import combat_deficit_report as cmd
from tests.test_ai.fixtures import make_state


def _player(**state_overrides):
    player = MagicMock()
    player.state = make_state(level=19, task_code="pig", task_type="monsters",
                              task_progress=0, task_total=104,
                              equipment={"weapon_slot": "sticky_sword"},
                              **state_overrides)
    player.game_data = MagicMock()
    return player


def _run(deficit, **kwargs):
    """Invoke the command with a canned player and a canned `combat_deficit`."""
    player = kwargs.pop("player", None) or _player()
    with (
        patch.object(cmd.Config, "from_token_file", return_value=MagicMock()),
        patch.object(cmd, "ClientManager"),
        patch.object(cmd, "LearningStore", return_value=MagicMock()),
        patch.object(cmd, "GamePlayer", return_value=player),
        patch.object(cmd, "acquisition_actions", return_value=1),
        patch.object(cmd, "combat_deficit", return_value=deficit),
    ):
        cmd.combat_deficit_command(
            character="C3P0",
            monster=kwargs.pop("monster", None),
            max_chain=kwargs.pop("max_chain", 8),
        )


def test_reports_the_chain_that_closes_a_losing_fight(capsys) -> None:
    """The live C3P0 shape: a losing margin and the acquisition that closes it."""
    _run(CombatDeficit(
        monster="pig", baseline_margin=-10, closes=True,
        chain=(DeficitStep(code="king_slime_sword", item_type="weapon", item_level=15,
                           crafting_skill="weaponcrafting", crafting_level=15,
                           margin_after=2),)))

    out = capsys.readouterr().out
    assert "margin -10 (losing)" in out
    assert "chain CLOSES" in out
    assert "king_slime_sword" in out
    assert "weaponcrafting@15" in out
    assert "margin -> 2" in out
    # the task line is what ties the deficit to the task the bot cannot advance
    assert "monsters/pig 0/104" in out


def test_the_command_prices_candidates_with_the_same_function_J_uses(capsys) -> None:
    """The `actions_of` closure is what makes the chain answer clause (c): a
    skill-gated craft carries `unlock_actions` (its grind, or the measured cost
    of asking a sibling), so "lowest skill requirement" and "cheapest
    acquisition" become one ordering and neither needs a rule.

    Asserted by INVOKING the closure the command hands to `combat_deficit`,
    because a closure that is merely constructed is not wired to anything —
    the earlier tests mocked `combat_deficit` and never called it.
    """
    player = _player()
    captured = {}

    def fake_deficit(state, game_data, monster, max_chain=8, actions_of=None):
        captured["cost"] = actions_of("iron_sword", "weapon_slot")
        return None

    with (
        patch.object(cmd.Config, "from_token_file", return_value=MagicMock()),
        patch.object(cmd, "ClientManager"),
        patch.object(cmd, "LearningStore", return_value=MagicMock()),
        patch.object(cmd, "GamePlayer", return_value=player),
        patch.object(cmd, "acquisition_actions", return_value=42),
        patch.object(cmd, "combat_deficit", fake_deficit),
    ):
        cmd.combat_deficit_command(character="C3P0", monster=None, max_chain=8)

    assert captured["cost"] == 42.0


def test_a_step_prints_what_it_cost(capsys) -> None:
    """The chain must read as a plan: four steps at 20 actions is a different
    decision from four at 400."""
    _run(CombatDeficit(
        monster="pig", baseline_margin=-10, closes=True,
        chain=(DeficitStep(code="mushstaff", item_type="weapon", item_level=15,
                           crafting_skill="weaponcrafting", crafting_level=15,
                           margin_after=1, acquire_cost=3.0),)))

    assert "3 actions" in capsys.readouterr().out


def test_an_unpriced_step_prints_a_question_mark_not_a_zero(capsys) -> None:
    """`acquire_cost` is None when no pricing was supplied. Printing 0 would read
    as free, which is the opposite of unknown."""
    _run(CombatDeficit(
        monster="pig", baseline_margin=-10, closes=True,
        chain=(DeficitStep(code="mushstaff", item_type="weapon", item_level=15,
                           crafting_skill="weaponcrafting", crafting_level=15,
                           margin_after=1),)))

    assert "? actions" in capsys.readouterr().out


def test_no_deficit_says_so_rather_than_printing_an_empty_chain(capsys) -> None:
    """`None` is the clearing condition and must read as such, not as a blank report."""
    _run(None)

    out = capsys.readouterr().out
    assert "NO DEFICIT" in out
    assert "winnable now" in out


def test_unclosable_deficit_is_reported_honestly(capsys) -> None:
    """A deficit no gear closes must NOT read the same as one that closes.

    This is the "unwinnable and I do not know what to build" case: the honest
    answer is that the character needs levels, not another crafting chain.
    """
    _run(CombatDeficit(monster="pig", baseline_margin=-40, closes=False, chain=()))

    out = capsys.readouterr().out
    assert "DOES NOT CLOSE" in out
    assert "needs a higher level, not more gear" in out


def test_uncraftable_step_names_its_route_instead_of_a_skill_gate(capsys) -> None:
    """Robby's real chain includes drop-only artifacts, which have no crafting gate."""
    _run(CombatDeficit(
        monster="rat", baseline_margin=-18, closes=True,
        chain=(DeficitStep(code="lich_race_trophy", item_type="artifact", item_level=20,
                           crafting_skill=None, crafting_level=0, margin_after=1),)))

    out = capsys.readouterr().out
    assert "not craftable (drop/vendor)" in out


def test_explicit_monster_overrides_the_task_monster(capsys) -> None:
    """`--monster` lets the deficit be asked about a fight not currently drawn."""
    _run(None, monster="chicken")

    assert "chicken" in capsys.readouterr().out


def test_taskless_character_without_monster_is_a_bad_parameter() -> None:
    """No task and no `--monster` is unanswerable — fail, never guess a monster.

    CLAUDE.md: use only API data or fail with an error.
    """
    player = _player()
    player.state = make_state(level=19, task_code=None, task_type=None)

    with pytest.raises(typer.BadParameter, match="no task monster"):
        _run(None, player=player)


def test_unsensed_state_is_a_bad_parameter() -> None:
    """A character whose state could not be sensed must fail, not report a deficit."""
    player = _player()
    player.state = None

    with pytest.raises(typer.BadParameter, match="could not sense state"):
        _run(None, player=player)

"""`play --rate-budget` wires the parsed budget to the RIGHT governor.

Task 17 shipped `GamePlayer.set_rate_governors`/`_acquire_data`/`_acquire_action`
with thorough coverage, but nothing drove `play()` itself with a real
`--rate-budget` JSON string — the CLI seam that parses the budget and hands
each half to the correct governor was untested. A crossed-wire bug there
(e.g. passing `budgets.data` to BOTH governors) would silently throttle every
`play --all` child against the wrong limit while every existing test still
passed.

Follows the pattern in test_play_emit_events.py: drive the real `play()` body
via CliRunner, mock only `GamePlayer`/`LearningStore` so no token/network is
needed, and let `RateGovernor`/`BucketBudgets` run for real so the assertion
is on real objects, not a mocked call log.
"""

from unittest.mock import Mock, patch

import pytest
import typer
from typer.testing import CliRunner

from artifactsmmo_cli.commands import play as play_module
from artifactsmmo_cli.utils.rate_budget import WindowBudget, parse_rate_limits, split_budget

app = typer.Typer()
app.command()(play_module.play)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _rate_budget_json(children: int = 2) -> tuple[str, WindowBudget, WindowBudget]:
    """A real --rate-budget JSON string built the same way MultiRun builds it
    for a child: parse a /my/rates-shaped payload, then split it. Returns the
    JSON plus the pre-split data/action WindowBudgets so the test can assert
    against real, independently-computed expectations rather than a literal.
    """
    payload = {
        "data": {
            "account": {"second": {"limit": 6}, "minute": {"limit": None},
                        "hour": {"limit": None}, "day": {"limit": None}},
            "data": {"second": {"limit": 20}, "minute": {"limit": 600},
                      "hour": {"limit": None}, "day": {"limit": None}},
            "action": {"second": {"limit": 10}, "minute": {"limit": 200},
                       "hour": {"limit": None}, "day": {"limit": None}},
        }
    }
    budgets = parse_rate_limits(payload)
    split = split_budget(budgets, children=children)
    # Sanity: the two buckets this test cares about must actually differ,
    # otherwise a crossed-wire bug (same budget handed to both governors)
    # would be indistinguishable from correct wiring.
    assert split.data.as_windows() != split.action.as_windows()
    return split.to_json(), split.data, split.action


class TestRateBudgetWiring:
    def test_rate_budget_governors_get_the_right_half_of_the_split(self, runner: CliRunner) -> None:
        rate_budget_json, expected_data, expected_action = _rate_budget_json(children=2)
        with (
            patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls,
            patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls,
        ):
            mock_player = Mock()
            mock_player_cls.return_value = mock_player
            mock_store_cls.return_value = Mock()

            result = runner.invoke(app, ["hero", "--rate-budget", rate_budget_json])

        assert result.exit_code == 0, result.output
        mock_player.set_rate_governors.assert_called_once()
        kwargs = mock_player.set_rate_governors.call_args.kwargs
        data_governor = kwargs["data"]
        action_governor = kwargs["action"]
        # RateGovernor stores the parsed windows as `_windows`; comparing
        # against independently-computed expected WindowBudgets is what
        # catches a swap (data<->action) or a duplicate (same budget handed
        # to both) — either would leave one side's `_windows` wrong.
        assert data_governor._windows == expected_data.as_windows()
        assert action_governor._windows == expected_action.as_windows()
        assert data_governor._windows != action_governor._windows

    def test_no_rate_budget_leaves_governors_unset(self, runner: CliRunner) -> None:
        """No --rate-budget (the single-character default) must not call
        set_rate_governors at all, matching GamePlayer's own None defaults."""
        with (
            patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls,
            patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls,
        ):
            mock_player = Mock()
            mock_player_cls.return_value = mock_player
            mock_store_cls.return_value = Mock()

            result = runner.invoke(app, ["hero"])

        assert result.exit_code == 0, result.output
        mock_player.set_rate_governors.assert_not_called()

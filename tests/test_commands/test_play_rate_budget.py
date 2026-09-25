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

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import typer
from typer.testing import CliRunner

from artifactsmmo_cli.commands import play as play_module
from artifactsmmo_cli.utils.rate_budget import WindowBudget, parse_rate_limits

app = typer.Typer()
app.command()(play_module.play)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _rate_budget_json() -> tuple[str, WindowBudget, WindowBudget, WindowBudget]:
    """A real --rate-budget JSON string built the same way MultiRun builds it
    for a child: parse a /my/rates-shaped payload and hand over ALL of it.
    Returns the JSON plus the account/data/action WindowBudgets so the test can
    assert against real, independently-computed expectations rather than a
    literal.
    """
    payload = {
        "data": {
            "account": {"second": {"limit": 6}, "minute": {"limit": None},
                        "hour": {"limit": 300}, "day": {"limit": None}},
            "data": {"second": {"limit": 20}, "minute": {"limit": 600},
                      "hour": {"limit": None}, "day": {"limit": None}},
            "action": {"second": {"limit": 10}, "minute": {"limit": 200},
                       "hour": {"limit": None}, "day": {"limit": None}},
        }
    }
    budgets = parse_rate_limits(payload)
    # Sanity: the three buckets this test cares about must all differ,
    # otherwise a crossed-wire bug (the same budget handed to two governors)
    # would be indistinguishable from correct wiring.
    assert budgets.account.as_windows() != budgets.data.as_windows()
    assert budgets.data.as_windows() != budgets.action.as_windows()
    assert budgets.account.as_windows() != budgets.action.as_windows()
    return budgets.to_json(), budgets.account, budgets.data, budgets.action


class TestRateBudgetWiring:
    def test_rate_budget_governors_get_the_right_bucket(self, runner: CliRunner, tmp_path: Path) -> None:
        rate_budget_json, expected_account, expected_data, expected_action = _rate_budget_json()
        with (
            patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls,
            patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls,
        ):
            mock_player = Mock()
            mock_player_cls.return_value = mock_player
            mock_store_cls.return_value = Mock()

            result = runner.invoke(app, ["hero", "--rate-budget", rate_budget_json,
                                         "--fleet-size", "2",
                                         "--coordination-db", str(tmp_path / "fleet.db")])

        assert result.exit_code == 0, result.output
        mock_player.set_rate_governors.assert_called_once()
        kwargs = mock_player.set_rate_governors.call_args.kwargs
        account_governor = kwargs["account"]
        data_governor = kwargs["data"]
        action_governor = kwargs["action"]
        # RateGovernor stores the parsed windows as `_windows`; comparing
        # against independently-computed expected WindowBudgets is what
        # catches a swap (e.g. account<->data) or a duplicate (same budget
        # handed to two governors) — either would leave one side's
        # `_windows` wrong.
        assert account_governor._windows == expected_account.as_windows()
        assert data_governor._windows == expected_data.as_windows()
        assert action_governor._windows == expected_action.as_windows()
        assert account_governor._windows != data_governor._windows
        assert data_governor._windows != action_governor._windows
        # One fleet: every governor polices its own bucket in the SAME log,
        # and prices the fair share of a 2-child fleet.
        assert (account_governor._bucket, data_governor._bucket, action_governor._bucket) \
            == ("account", "data", "action")
        assert account_governor._log is data_governor._log is action_governor._log
        assert account_governor.sustainable_interval() == expected_account.divided_by(2).sustainable_interval()

    @pytest.mark.parametrize("extra", [
        ["--fleet-size", "2"],
        ["--coordination-db", "fleet.db"],
    ])
    def test_a_budget_the_fleet_cannot_share_is_refused(
            self, runner: CliRunner, extra: list[str]) -> None:
        """The budget is the whole per-IP budget. Without the shared DB it
        cannot be policed fleet-wide, and without the fleet size its fair share
        cannot be priced, so the child refuses to start rather than overspend."""
        rate_budget_json, _, _, _ = _rate_budget_json()
        with (
            patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls,
            patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls,
        ):
            mock_player_cls.return_value = Mock()
            mock_store_cls.return_value = Mock()

            result = runner.invoke(app, ["hero", "--rate-budget", rate_budget_json, *extra])

        assert result.exit_code == 2
        assert "--rate-budget needs --coordination-db and --fleet-size" in result.output

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

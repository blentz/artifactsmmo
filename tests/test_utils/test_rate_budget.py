"""RateBudget: parse /my/rates and divide it across N children."""

import pytest

from artifactsmmo_cli.utils.rate_budget import (
    BucketBudgets,
    WindowBudget,
    parse_rate_limits,
    split_budget,
)

_PAYLOAD = {
    "data": {
        "account": {"second": {"limit": 10}, "hour": {"limit": 300}},
        "data": {"second": {"limit": 10}, "minute": {"limit": 200}, "hour": {"limit": 2000}},
        "action": {"second": {"limit": 10}, "minute": {"limit": 100}, "hour": {"limit": 5000}},
    }
}


def test_parse_reads_every_bucket_and_window():
    budgets = parse_rate_limits(_PAYLOAD)
    assert budgets.data == WindowBudget(second=10, minute=200, hour=2000, day=None)
    assert budgets.action == WindowBudget(second=10, minute=100, hour=5000, day=None)
    assert budgets.account == WindowBudget(second=10, minute=None, hour=300, day=None)


def test_parse_rejects_a_missing_bucket():
    with pytest.raises(ValueError, match="rate limit payload has no 'action' bucket"):
        parse_rate_limits({"data": {"account": {}, "data": {}}})


def test_split_divides_every_window():
    split = split_budget(parse_rate_limits(_PAYLOAD), children=5)
    assert split.data == WindowBudget(second=2, minute=40, hour=400, day=None)
    assert split.action == WindowBudget(second=2, minute=20, hour=1000, day=None)


def test_split_floors_but_never_to_zero():
    budgets = BucketBudgets(
        account=WindowBudget(second=1, minute=None, hour=None, day=None),
        data=WindowBudget(second=1, minute=None, hour=None, day=None),
        action=WindowBudget(second=1, minute=None, hour=None, day=None),
    )
    assert split_budget(budgets, children=5).data.second == 1


def test_split_rejects_a_nonpositive_child_count():
    with pytest.raises(ValueError, match="children must be >= 1"):
        split_budget(parse_rate_limits(_PAYLOAD), children=0)


def test_json_round_trip():
    budgets = split_budget(parse_rate_limits(_PAYLOAD), children=5)
    assert BucketBudgets.from_json(budgets.to_json()) == budgets


def test_as_windows_includes_all_declared_windows():
    budget = WindowBudget(second=10, minute=200, hour=2000, day=3600)
    windows = budget.as_windows()
    assert windows == {1.0: 10, 60.0: 200, 3600.0: 2000, 86400.0: 3600}


def test_as_windows_omits_none_windows():
    budget = WindowBudget(second=10, minute=None, hour=2000, day=None)
    windows = budget.as_windows()
    assert windows == {1.0: 10, 3600.0: 2000}
    assert 60.0 not in windows
    assert 86400.0 not in windows


def test_sustainable_interval_takes_the_slowest_window_not_the_fastest():
    """The live account bucket: 10/second is generous, 300/hour is not. The
    binding pace is one request per 12s, so a `min` (0.1s) would be wrong."""
    account = parse_rate_limits(_PAYLOAD).account
    assert account.sustainable_interval() == pytest.approx(12.0)


def test_sustainable_interval_can_be_bound_by_the_shortest_window():
    """"Slowest window" is not "longest span": with a per-second limit of 1 and
    a very generous hourly one, the per-second window is what binds (1.0s vs
    0.1s), so the choice really is a max over span/limit."""
    budget = WindowBudget(second=1, minute=None, hour=36000, day=None)
    assert budget.sustainable_interval() == pytest.approx(1.0)


def test_sustainable_interval_of_an_unlimited_bucket_is_zero():
    """No declared window means no pacing is required -- not infinite pacing."""
    budget = WindowBudget(second=None, minute=None, hour=None, day=None)
    assert budget.sustainable_interval() == 0.0


def test_parse_rejects_missing_data_envelope():
    with pytest.raises(ValueError, match="rate limit payload has no 'data' envelope"):
        parse_rate_limits({})

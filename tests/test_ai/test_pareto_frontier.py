"""The non-dominated set over the measured currencies."""

from artifactsmmo_cli.audit.currency_rate_census import GoalRates
from artifactsmmo_cli.audit.pareto_frontier import frontier


def _rates(goal: str, char_xp: int, skill_xp: int, gold: int) -> GoalRates:
    # One second of activity, so the totals ARE the rates.
    return GoalRates(goal=goal, cycles=1, seconds=1.0, char_xp=char_xp,
                     skill_xp={"cooking": skill_xp}, gold=gold)


def test_a_strictly_worse_bundle_is_dominated() -> None:
    best = _rates("best", 10, 10, 10)
    worse = _rates("worse", 1, 1, 1)
    assert frontier([best, worse]) == [best]


def test_a_bundle_that_wins_on_one_currency_survives() -> None:
    # Fewer char xp, but far more skill xp — under total_xp both count.
    fighter = _rates("fighter", 10, 0, 0)
    cook = _rates("cook", 0, 10, 0)
    assert [r.goal for r in frontier([fighter, cook])] == ["fighter", "cook"]


def test_an_equal_bundle_does_not_dominate() -> None:
    # Domination requires strictly better on at least one currency, so two
    # identical bundles both survive rather than one eliminating the other.
    a = _rates("a", 5, 5, 5)
    b = _rates("b", 5, 5, 5)
    assert [r.goal for r in frontier([a, b])] == ["a", "b"]


def test_gold_is_a_real_axis() -> None:
    # Loses on both xp axes, wins on gold: still on the frontier.
    grinder = _rates("grinder", 10, 10, 0)
    seller = _rates("seller", 0, 0, 10)
    assert [r.goal for r in frontier([grinder, seller])] == ["grinder", "seller"]


def test_empty_input_is_an_empty_frontier() -> None:
    assert frontier([]) == []

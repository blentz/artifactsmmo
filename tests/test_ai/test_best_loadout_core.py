"""The best consumable loadout's pick (`docs/PLAN_consumable_utility.md`
increment 4; proved `Formal.BestLoadout`)."""

from fractions import Fraction

from artifactsmmo_cli.ai.best_loadout_core import beats, pick_best


def test_no_candidates_no_pick() -> None:
    assert pick_best([]) is None


def test_the_highest_rate_wins() -> None:
    assert pick_best([(Fraction(1, 4), 0), (Fraction(1, 3), 5), (Fraction(1, 5), 0)]) == 1


def test_the_same_rate_on_fewer_units_wins() -> None:
    assert pick_best([(Fraction(1, 3), 5), (Fraction(2, 6), 2), (Fraction(1, 3), 3)]) == 1


def test_a_full_tie_keeps_the_earlier() -> None:
    assert pick_best([(Fraction(0), 0), (Fraction(0), 0)]) == 0
    assert pick_best([(Fraction(1, 2), 1), (Fraction(1, 2), 1)]) == 0


def test_beats() -> None:
    assert beats((Fraction(1), 9), (Fraction(1, 2), 0))
    assert beats((Fraction(1), 1), (Fraction(1), 2))
    assert not beats((Fraction(1), 2), (Fraction(1), 2))
    assert not beats((Fraction(1, 2), 0), (Fraction(1), 9))

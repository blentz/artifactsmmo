"""A fight's expected-value outcome with restore potions
(`docs/PLAN_consumable_utility.md` increment 1; proved `Formal.FightOutcome`).

API rule: "Restores X HP at the start of the turn if the player has lost more
than 50% of their health points"."""

import pytest

from artifactsmmo_cli.ai.fight_outcome_core import FightOutcome, fight_outcome
from artifactsmmo_cli.ai.fight_terms_core import fight_terms, terms_win

# 100 HP, 30 HP per monster round, the kill in round 6 (0 potions: dies in round 4).
_SIX_ROUNDS = fight_terms(10, 10_000, 6, 0, 300_000, 100, 100, True)


def _six(first: bool):
    return fight_terms(10, 10_000, 6, 0, 300_000, 100, 100, first)


class TestWalk:
    def test_without_stock_the_closed_form(self) -> None:
        for first in (True, False):
            walked = fight_outcome(_six(first), 100, 100, 40, 0)
            assert walked.win is terms_win(_six(first)) is False
            assert walked.used == 0

    def test_the_first_mover_drinks_below_half_and_wins(self) -> None:
        # pools ×10000: 100→70→40 (drink→80)→50→20 (drink→60)→30 (drink→70), kill in round 6.
        assert fight_outcome(_six(True), 100, 100, 40, 3) == FightOutcome(True, 6, 700_000, 3)

    def test_the_first_mover_runs_dry_and_dies(self) -> None:
        # one potion: round 3 drink→80→50, round 4→20, round 5 no stock → -10.
        assert fight_outcome(_six(True), 100, 100, 40, 1) == FightOutcome(False, 5, 0, 1)

    def test_no_drink_at_exactly_half(self) -> None:
        # 50/100 has lost exactly 50%, not more: no drink, and the kill comes first.
        terms = fight_terms(10, 10_000, 1, 0, 300_000, 50, 100, True)
        assert fight_outcome(terms, 50, 100, 40, 3) == FightOutcome(True, 1, 500_000, 0)

    def test_a_drink_is_capped_at_max_hp(self) -> None:
        terms = fight_terms(10, 10_000, 1, 0, 300_000, 10, 100, True)
        assert fight_outcome(terms, 10, 100, 500, 1) == FightOutcome(True, 1, 1_000_000, 1)

    def test_the_second_mover_is_hit_before_it_drinks(self) -> None:
        # monster first: 100→70, 40 (drink→80), 50, 20 (drink→60), 30 (drink→70), 40 (drink→80).
        assert fight_outcome(_six(False), 100, 100, 40, 9) == FightOutcome(True, 6, 800_000, 4)

    def test_the_second_mover_dies_before_its_turn(self) -> None:
        assert fight_outcome(_six(False), 30, 100, 40, 9) == FightOutcome(False, 1, 0, 0)

    def test_the_walk_starts_from_hp_start_not_the_terms(self) -> None:
        # the terms were built at full HP; this fight starts at 20.
        assert fight_outcome(_six(True), 20, 100, 0, 0) == FightOutcome(False, 1, 0, 0)

    def test_a_kill_in_round_zero(self) -> None:
        terms = fight_terms(10, 10_000, 0, 0, 300_000, 100, 100, True)
        assert fight_outcome(terms, 100, 100, 40, 3) == FightOutcome(True, 0, 1_000_000, 0)


class TestExits:
    def test_out_sustain_wins_at_the_starting_pool(self) -> None:
        terms = fight_terms(10, 10_000, 6, 0, 0, 100, 100, True)
        assert fight_outcome(terms, 150, 100, 40, 3) == FightOutcome(True, 6, 1_000_000, 0)

    def test_a_monster_side_exit_is_lost_unwalked(self) -> None:
        terms = fight_terms(10, 0, 6, 0, 300_000, 100, 100, True)
        assert fight_outcome(terms, 100, 100, 40, 3) == FightOutcome(False, 0, 0, 0)

    def test_starting_dead_loses(self) -> None:
        assert fight_outcome(_six(True), 0, 100, 40, 3) == FightOutcome(False, 0, 0, 0)

    def test_a_dead_terms_exit_still_walks_a_live_start(self) -> None:
        terms = fight_terms(10, 10_000, 6, 0, 300_000, 0, 100, True)
        assert fight_outcome(terms, 100, 100, 40, 3) == FightOutcome(True, 6, 700_000, 3)

    @pytest.mark.parametrize(("restore", "stock"), [(-1, 0), (0, -1)])
    def test_negative_inputs_are_refused(self, restore: int, stock: int) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            fight_outcome(_SIX_ROUNDS, 100, 100, restore, stock)

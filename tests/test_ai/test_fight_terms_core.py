"""The closed form's per-turn terms and the verdict read from them
(`docs/PLAN_consumable_utility.md` increment 1; proved
`Formal.FightOutcome.closedWin_eq_predictWin`)."""

import pytest

from artifactsmmo_cli.ai.fight_terms_core import (
    BARRIER_PERIOD,
    LOSE_MARGIN,
    MAX_TURNS,
    SCALE,
    WIN_MARGIN,
    FightExit,
    ceil_div,
    effective_player_hp,
    fight_terms,
    kill_rounds,
    terms_margin,
    terms_win,
)


def _terms(raw: int = 10, kill: int = 100_000, monster_hp: int = 30, recon: int = 0,
           die: int = 200_000, hp: int = 100, max_hp: int = 100, first: bool = True,
           barrier: int = 0):
    return fight_terms(raw, kill, monster_hp, recon, die, hp, max_hp, first, barrier)


class TestLadder:
    def test_no_damage_comes_first(self) -> None:
        assert _terms(raw=0, kill=-1, die=-1).exit is FightExit.NO_DAMAGE

    def test_unkillable(self) -> None:
        assert _terms(kill=0).exit is FightExit.UNKILLABLE

    def test_the_turn_cap(self) -> None:
        # 30 HP at 2,999 per round: 101 rounds, past the cap.
        terms = _terms(kill=2_999)
        assert terms.exit is FightExit.OVER_CAP
        assert terms.rounds_to_kill == MAX_TURNS + 1

    def test_exactly_at_the_cap_is_walked(self) -> None:
        assert _terms(kill=3_000).rounds_to_kill == MAX_TURNS
        assert _terms(kill=3_000).exit is FightExit.NONE

    def test_reconstitution_at_the_kill_round(self) -> None:
        assert _terms(recon=3).exit is FightExit.RECONSTITUTED
        assert _terms(recon=4).exit is FightExit.NONE

    def test_out_sustain(self) -> None:
        assert _terms(die=0, hp=0).exit is FightExit.OUT_SUSTAIN

    def test_dead(self) -> None:
        terms = _terms(hp=0)
        assert (terms.exit, terms.effective_hp, terms.rounds_to_die) == (FightExit.DEAD, 0, 0)

    def test_the_numbers(self) -> None:
        terms = _terms(hp=150, first=False)
        assert terms.exit is FightExit.NONE
        assert terms.rounds_to_kill == 3            # 300,000 / 100,000
        assert terms.effective_hp == 100            # capped at max
        assert terms.rounds_to_die == 5             # 1,000,000 / 200,000
        assert (terms.kill_step, terms.die_step, terms.player_first) == (100_000, 200_000, False)


class TestVerdict:
    def test_out_sustain_wins(self) -> None:
        terms = _terms(die=-5)
        assert terms_win(terms) is True
        assert terms_margin(terms) == WIN_MARGIN

    @pytest.mark.parametrize("terms", [_terms(raw=0), _terms(kill=0), _terms(kill=2_999),
                                       _terms(recon=1), _terms(hp=0)])
    def test_every_other_exit_loses(self, terms) -> None:
        assert terms_win(terms) is False
        assert terms_margin(terms) == LOSE_MARGIN

    def test_the_first_mover_wins_the_tied_round(self) -> None:
        # 5 rounds to kill, 5 to die.
        first = _terms(monster_hp=50, first=True)
        second = _terms(monster_hp=50, first=False)
        assert (terms_win(first), terms_margin(first)) == (True, 1)
        assert (terms_win(second), terms_margin(second)) == (False, 0)


def test_helpers() -> None:
    assert ceil_div(10, 3) == 4
    assert ceil_div(9, 3) == 3
    assert effective_player_hp(-3, 100) == 0
    assert effective_player_hp(130, 100) == 100
    assert effective_player_hp(40, 100) == 40


def _walked_rounds(monster_hp: int, barrier: int, kill: int, first: bool) -> int:
    """The deterministic round walk the closed form answers: each player hit
    goes to the barrier first, and the monster's turn in every round divisible
    by `BARRIER_PERIOD` sets the barrier back to full."""
    pool, shield = monster_hp * SCALE, barrier * SCALE
    for round_no in range(1, MAX_TURNS + 1):
        if not first and round_no % BARRIER_PERIOD == 0:
            shield = barrier * SCALE
        absorbed = min(shield, kill)
        pool, shield = pool - (kill - absorbed), shield - absorbed
        if pool <= 0:
            return round_no
        if first and round_no % BARRIER_PERIOD == 0:
            shield = barrier * SCALE
    return MAX_TURNS + 1


class TestKillRounds:
    def test_lor_v_king_slime(self) -> None:
        """2026-10-17 20:02 UTC: 115 a hit, no crit, 1000 HP behind a 100
        barrier raised at the start and at the monster's 5th and 10th turns:
        the 12th hit kills (the flat add said 10)."""
        assert kill_rounds(1000, 100, 115 * SCALE, True) == 12
        assert ceil_div(1100 * SCALE, 115 * SCALE) == 10

    def test_no_barrier_is_the_plain_division(self) -> None:
        for hp in (1, 7, 30, 999):
            for kill in (1_000, 33_333, 100_000):
                for first in (True, False):
                    assert kill_rounds(hp, 0, kill, first) == ceil_div(hp * SCALE, kill)

    def test_the_monster_moving_first_refreshes_before_the_fifth_hit(self) -> None:
        # 100 a hit, 400 HP behind 100: a first mover's hits 1-5 all meet the
        # first barrier (400 through); a late mover's 5th hit meets a fresh one.
        assert kill_rounds(150, 100, 100 * SCALE, True) == 3
        assert kill_rounds(400, 100, 100 * SCALE, True) == 5
        assert kill_rounds(400, 100, 100 * SCALE, False) == 6

    def test_a_barrier_no_block_breaks_is_past_the_cap(self) -> None:
        assert kill_rounds(10, 500, 100 * SCALE, True) == MAX_TURNS + 1
        # 1 through a block: 9 blocks, then 5 hits for the last 1.
        assert kill_rounds(10, 499, 100 * SCALE, True) == 50

    def test_the_closed_form_is_the_walk(self) -> None:
        for monster_hp in (1, 40, 99, 100, 101, 437, 1000):
            for barrier in (0, 1, 50, 99, 100, 150, 399, 400, 500):
                for kill in (1_000, 99_999, 100_000, 100_001, 230_000):
                    for first in (True, False):
                        assert min(kill_rounds(monster_hp, barrier, kill, first), MAX_TURNS + 1) == \
                            _walked_rounds(monster_hp, barrier, kill, first), \
                            (monster_hp, barrier, kill, first)

    def test_the_terms_count_the_refreshes(self) -> None:
        terms = _terms(kill=1_000_000, monster_hp=400, barrier=100, first=False)
        assert terms.rounds_to_kill == 6
        assert terms.exit is FightExit.NONE
        assert _terms(monster_hp=10, barrier=500).exit is FightExit.OVER_CAP

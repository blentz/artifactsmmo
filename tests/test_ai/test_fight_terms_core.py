"""The closed form's per-turn terms and the verdict read from them
(`docs/PLAN_consumable_utility.md` increment 1; proved
`Formal.FightOutcome.closedWin_eq_predictWin`)."""

import pytest

from artifactsmmo_cli.ai.fight_terms_core import (
    LOSE_MARGIN,
    MAX_TURNS,
    WIN_MARGIN,
    FightExit,
    ceil_div,
    effective_player_hp,
    fight_terms,
    terms_margin,
    terms_win,
)


def _terms(raw: int = 10, kill: int = 100_000, monster_hp: int = 30, recon: int = 0,
           die: int = 200_000, hp: int = 100, max_hp: int = 100, first: bool = True):
    return fight_terms(raw, kill, monster_hp, recon, die, hp, max_hp, first)


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

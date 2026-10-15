"""The exact ending distribution of a fight over crit rolls
(spec 2026-10-15 fight-odds §1)."""

from dataclasses import replace
from fractions import Fraction

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.fight_odds_core import Ending, RoundDamage, burn_ticks, fight_odds, win_probability
from artifactsmmo_cli.ai.fight_outcome_core import fight_outcome
from artifactsmmo_cli.ai.fight_terms_core import MAX_TURNS, SCALE, fight_terms

# R2D2 v owlbear, 2026-10-15 server logs: 141/212 a turn at 45% crit; the owlbear
# 83/125 at 5%, moving first; R2D2 785 HP, owlbear 1450 HP.
_R2D2_TERMS = fight_terms(141, 50 * 141 * 245, 1450, 0, 50 * 83 * 205, 785, 785, False)
_R2D2 = RoundDamage(1450, 141 * SCALE, 212 * SCALE, 45, 83 * SCALE, 125 * SCALE, 5, ())


def _no_crit(kill: int, die: int, mhp: int) -> RoundDamage:
    return RoundDamage(mhp, kill, kill, 0, die, die, 0, ())


class TestR2D2Replay:
    def test_bare_odds_match_the_exact_value(self):
        p = win_probability(fight_odds(_R2D2_TERMS, _R2D2, 785, 785, 0, 0))
        assert round(float(p), 4) == 0.6308

    def test_a_minor_health_potion_makes_it_certain(self):
        p = win_probability(fight_odds(_R2D2_TERMS, _R2D2, 785, 785, 70, 100))
        assert round(float(p), 4) == 1.0

    def test_losses_end_between_the_seventh_and_tenth_monster_hit(self):
        # 6 hits deal at most 750 < 785; 10 hits at least 830 > 785.
        losses = {e.turns for e in fight_odds(_R2D2_TERMS, _R2D2, 785, 785, 0, 0) if not e.win}
        assert losses == {7, 8, 9, 10}


class TestDistribution:
    def test_probabilities_sum_to_one(self):
        assert sum(e.prob for e in fight_odds(_R2D2_TERMS, _R2D2, 785, 785, 70, 3)) == 1

    def test_endings_are_merged(self):
        endings = fight_odds(_R2D2_TERMS, _R2D2, 785, 785, 0, 0)
        keys = [(e.win, e.turns, e.hp_end, e.used) for e in endings]
        assert len(keys) == len(set(keys))

    def test_certain_crit_is_one_walk(self):
        damage = RoundDamage(1450, 141 * SCALE, 212 * SCALE, 100, 83 * SCALE, 125 * SCALE, 0, ())
        endings = fight_odds(_R2D2_TERMS, damage, 785, 785, 0, 0)
        assert len(endings) == 1 and endings[0].prob == 1 and endings[0].win

    def test_heal_larger_than_normal_hit_terminates(self):
        # The normal hit heals the monster (net -1), the crit kills: mean positive.
        terms = fight_terms(10, 5000, 50, 0, 20_000, 1000, 1000, True)
        damage = RoundDamage(50, -10_000, 600_000, 50, 20_000, 20_000, 0, ())
        endings = fight_odds(terms, damage, 1000, 1000, 0, 0)
        assert sum(e.prob for e in endings) == 1
        assert max(e.turns for e in endings) <= MAX_TURNS



class TestBurn:
    """2026-10-15 server logs (292 imp fights): "applies a burn of 7" =
    round(15% x the imp's attack 45); it ticks 7, 6, 5, 4, 3, 2, 1."""

    def test_ticks_start_at_the_rounded_share_of_the_monsters_attack(self):
        assert burn_ticks(15, 45) == tuple(t * SCALE for t in (7, 6, 5, 4, 3, 2, 1))

    def test_each_tick_is_nine_tenths_of_the_last_rounded_down(self):
        assert burn_ticks(20, 110) == tuple(
            t * SCALE for t in (22, 19, 17, 15, 13, 11, 9, 8, 7, 6, 5, 4, 3, 2, 1))

    def test_no_burn_is_no_ticks(self):
        assert burn_ticks(0, 45) == ()
        assert burn_ticks(15, 0) == ()
        assert burn_ticks(1, 3) == ()  # round(0.03) = 0

    @pytest.mark.parametrize(("player_first", "lost_in"), [(True, 3), (False, 2)])
    def test_a_burn_tick_can_kill(self, player_first, lost_in):
        # 10 HP, a 1 HP hit, ticks 7 then 6: the burn kills before the 3-round kill.
        # Player first: the monster burns in round 1, ticks in rounds 2 and 3.
        # Monster first: it burns and the first tick lands in round 1.
        terms = fight_terms(10, 100_000, 30, 0, SCALE, 10, 10, player_first)
        damage = RoundDamage(30, 100_000, 100_000, 0, SCALE, SCALE, 0, (7 * SCALE, 6 * SCALE))
        assert fight_odds(terms, damage, 10, 10, 0, 0) == (Ending(Fraction(1), False, lost_in, 0, 0),)
        assert fight_odds(terms, replace(damage, burn=()), 10, 10, 0, 0)[0].win

    def test_a_tick_lands_before_the_drink(self):
        # 20 HP, 10 restore, half is 10: the 11 HP tick takes 20 to 9, which drinks to 19.
        terms = fight_terms(10, 100_000, 20, 0, SCALE, 20, 20, False)
        damage = RoundDamage(20, 100_000, 100_000, 0, 0, 0, 0, (11 * SCALE,))
        assert fight_odds(terms, damage, 20, 20, 10, 1) == (
            Ending(Fraction(1), True, 2, 19 * SCALE, 1),)

    def test_hal_v_imp_is_a_sure_win(self):
        # HAL v imp, 2026-10-15: 101/152 a turn at 21% crit, first; imp 1750 HP,
        # 39/59 at 5% (lifesteal 23 x 21% folded in: -4.83). Model said 0.8123.
        rest = -21 * 23 * 100
        terms = fight_terms(101, 50 * 101 * 221, 1750, 0, 50 * 39 * 205 + rest, 795, 795, True)
        damage = RoundDamage(1750, 101 * SCALE, 152 * SCALE, 21, 39 * SCALE + rest,
                             59 * SCALE + rest, 5, burn_ticks(15, 45))
        assert float(win_probability(fight_odds(terms, damage, 795, 795, 0, 0))) > 0.999


class TestExits:
    @pytest.mark.parametrize("terms", [
        fight_terms(0, 1, 100, 0, 1, 100, 100, True),        # NO_DAMAGE
        fight_terms(5, 0, 100, 0, 1, 100, 100, True),        # UNKILLABLE
        fight_terms(5, 1, 10_000, 0, 1, 100, 100, True),     # OVER_CAP
        fight_terms(5, 10_000, 100, 3, 1, 100, 100, True),   # RECONSTITUTED
    ])
    def test_a_losing_exit_is_one_certain_loss(self, terms):
        assert fight_odds(terms, _no_crit(10_000, 1, 100), 100, 100, 0, 0) == (
            Ending(Fraction(1), False, 0, 0, 0),)

    def test_out_sustain_is_one_certain_win(self):
        terms = fight_terms(5, 50_000, 100, 0, 0, 100, 100, True)
        assert fight_odds(terms, _no_crit(50_000, 0, 100), 100, 100, 0, 0) == (
            Ending(Fraction(1), True, 20, 100 * SCALE, 0),)  # ceil(100 × 10000 / 50000)

    def test_a_dead_start_is_one_certain_loss(self):
        terms = fight_terms(5, 50_000, 100, 0, 10, 0, 100, True)
        assert fight_odds(terms, _no_crit(50_000, 10, 100), 0, 100, 0, 0) == (
            Ending(Fraction(1), False, 0, 0, 0),)

    def test_negative_restore_or_stock_raises(self):
        with pytest.raises(ValueError):
            fight_odds(_R2D2_TERMS, _R2D2, 785, 785, -1, 0)
        with pytest.raises(ValueError):
            fight_odds(_R2D2_TERMS, _R2D2, 785, 785, 0, -1)


_walked = st.tuples(
    st.integers(min_value=1, max_value=60),               # raw player
    st.integers(min_value=10_000, max_value=600_000),     # kill step
    st.integers(min_value=1, max_value=600),              # monster hp
    st.integers(min_value=10_000, max_value=900_000),     # die step
    st.booleans(),                                        # player first
    st.integers(min_value=1, max_value=2000),             # hp
    st.integers(min_value=0, max_value=400),              # restore
    st.integers(min_value=0, max_value=8),                # stock
)


@settings(max_examples=300, deadline=None)
@given(case=_walked)
def test_no_crit_equals_the_expected_value_walk(case):
    raw, ks, mhp, ds, pf, hp, restore, stock = case
    terms = fight_terms(raw, ks, mhp, 0, ds, hp, hp, pf)
    o = fight_outcome(terms, hp, hp, restore, stock)
    assert fight_odds(terms, _no_crit(ks, ds, mhp), hp, hp, restore, stock) == (
        Ending(Fraction(1), o.win, o.turns, o.hp_end, o.used),)

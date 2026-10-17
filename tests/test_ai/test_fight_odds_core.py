"""The exact ending distribution of a fight over crit rolls
(spec 2026-10-15 fight-odds §1)."""

from dataclasses import replace
from fractions import Fraction

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.fight_odds_core import (
    Ending,
    RoundDamage,
    absorb,
    burn_ticks,
    fight_odds,
    odds_clear,
    win_probability,
)
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



# Lor v king_slime, 2026-10-17 20:02:25 UTC, lost at 546/960: Lor moves first
# and hits 64 + 51 = 115 a round (no crit that fight); the slime hits 12 + 11 +
# 11 + 12 = 46, or 70 on its 20% crit, behind a 100 barrier it raises at the
# start and at its 5th and 10th turns. Crit-free, Lor needs 12 hits, so the
# slime gets 11 turns: two crits (554) kill, one (530) does not.
_LOR_TERMS = fight_terms(115, 115 * SCALE, 1000, 0, 508_000, 546, 960, True, 100)
_LOR = RoundDamage(1000, 115 * SCALE, 115 * SCALE, 0, 46 * SCALE, 70 * SCALE, 20, (), barrier=100)


class TestBarrier:
    def test_lor_v_king_slime_needs_twelve_hits(self):
        p = win_probability(fight_odds(_LOR_TERMS, _LOR, 546, 960, 0, 0))
        assert p == Fraction(4, 5) ** 11 + 11 * Fraction(1, 5) * Fraction(4, 5) ** 10
        assert {e.turns for e in fight_odds(_LOR_TERMS, _LOR, 546, 960, 0, 0) if e.win} == {12}

    def test_the_flat_barrier_said_ten(self):
        """The model this replaced: 1,100 HP and no refresh, the 10th hit kills
        and the slime gets 9 turns (six crits to reach 546)."""
        flat = fight_odds(fight_terms(115, 115 * SCALE, 1100, 0, 508_000, 546, 960, True),
                          replace(_LOR, monster_hp=1100, barrier=0), 546, 960, 0, 0)
        assert {e.turns for e in flat if e.win} == {10}
        assert win_probability(flat) > Fraction(99, 100)

    def test_a_late_mover_meets_the_refresh_before_its_fifth_hit(self):
        # 100 a hit, 400 HP behind 100, the monster harmless: 5 rounds moving
        # first, 6 moving second (`kill_rounds`).
        for first, rounds in ((True, 5), (False, 6)):
            terms = fight_terms(100, 100 * SCALE, 400, 0, 1, 100, 100, first, 100)
            damage = RoundDamage(400, 100 * SCALE, 100 * SCALE, 0, 1, 1, 0, (), barrier=100)
            assert [e.turns for e in fight_odds(terms, damage, 100, 100, 0, 0)] == [rounds]

    def test_a_crit_spills_through_the_barrier(self):
        # 60, or 150 on a 50% crit, into 100 HP behind 100, moving first. A
        # first crit puts 50 through, and any second hit kills; a normal first
        # hit leaves 40 of barrier, which a crit overruns by 110 (a kill) and a
        # normal hit by 20 (80 left: one more crit, or two normal hits).
        terms = fight_terms(60, 105 * SCALE, 100, 0, 1, 100, 100, True, 100)
        damage = RoundDamage(100, 60 * SCALE, 150 * SCALE, 50, 1, 1, 0, (), barrier=100)
        turns = {e.turns: e.prob for e in fight_odds(terms, damage, 100, 100, 0, 0)}
        assert turns == {2: Fraction(3, 4), 3: Fraction(1, 8), 4: Fraction(1, 8)}

    def test_absorb(self):
        """The barrier takes a hit first and the rest goes through; a
        non-positive amount (a mean-modelled heal past the hit) goes to HP and
        leaves the barrier alone."""
        assert absorb(100, 64) == (0, 36)
        assert absorb(36, 51) == (15, 0)
        assert absorb(0, 51) == (51, 0)
        assert absorb(40, -7) == (-7, 40)
        assert absorb(40, 0) == (0, 40)

# C3P0 v cyclops, 2026-10-17 server logs (161 fights, 130 won): 110/165 a turn at
# 30% crit, moving first; the cyclops 118/177 at 5%; C3P0 725 HP, cyclops 850 HP;
# a lifesteal rune heals 25 on every crit that does not kill; 30-HP potions.
_C3P0_TERMS = fight_terms(110, 50 * 110 * 230, 850, 0, 50 * 118 * 205, 725, 725, True)
_C3P0 = RoundDamage(850, 110 * SCALE, 165 * SCALE, 30, 118 * SCALE, 177 * SCALE, 5, (),
                    p_heal=25 * SCALE)


class TestLifesteal:
    def test_c3p0_v_cyclops_matches_the_server_rule(self):
        """The exact DP over the logged rules gives 0.8157 (observed 130/161 =
        0.807); the mean model this replaced gave 0.8956."""
        p = win_probability(fight_odds(_C3P0_TERMS, _C3P0, 725, 725, 30, 80))
        assert round(float(p), 4) == 0.8157

    def test_c3p0_v_cyclops_bare(self):
        p = win_probability(fight_odds(_C3P0_TERMS, _C3P0, 725, 725, 0, 0))
        assert round(float(p), 4) == 0.6048

    @pytest.mark.parametrize("player_first", [True, False])
    def test_a_heal_is_capped_and_a_killing_crit_heals_nothing(self, player_first):
        """Every turn a crit: each non-killing crit tops 90 up to the 100 cap, not
        115; the third crit kills and heals nothing, so the fight ends at 90
        whichever side moves first."""
        terms = fight_terms(100, 100 * SCALE, 300, 0, 10 * SCALE, 100, 100, player_first)
        damage = RoundDamage(300, 50 * SCALE, 100 * SCALE, 100, 10 * SCALE, 10 * SCALE, 0, (),
                             p_heal=25 * SCALE)
        assert fight_odds(terms, damage, 100, 100, 0, 0) == (Ending(Fraction(1), True, 3, 90 * SCALE, 0),)

    @pytest.mark.parametrize("player_first", [True, False])
    def test_a_monster_crit_heals_the_monster(self, player_first):
        """A 100 kill a turn against a monster healing 50 on each (certain) crit
        takes five rounds, not three. Moving first, the monster's round-1 heal
        lands at full HP and is capped to nothing."""
        terms = fight_terms(100, 100 * SCALE, 300, 0, 1 * SCALE, 10_000, 10_000, player_first)
        damage = RoundDamage(300, 100 * SCALE, 100 * SCALE, 0, 1 * SCALE, 1 * SCALE, 100, (),
                             m_heal=50 * SCALE)
        (ending,) = fight_odds(terms, damage, 10_000, 10_000, 0, 0)
        assert ending.win and ending.turns == 5

    def test_no_heal_is_the_old_walk(self):
        assert fight_odds(_R2D2_TERMS, replace(_R2D2, p_heal=0, m_heal=0), 785, 785, 0, 0) \
            == fight_odds(_R2D2_TERMS, _R2D2, 785, 785, 0, 0)


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


def test_odds_clear_is_at_least_the_threshold() -> None:
    """P(win) AT LEAST θ (Lean `θ ≤ winProb`): equal clears, a hair above
    does not, and θ 0 clears a lost fight."""
    assert odds_clear(Fraction(1, 2), Fraction(1, 2)) is True
    assert odds_clear(Fraction(1, 2), Fraction(1, 2) + Fraction(1, 10**9)) is False
    assert odds_clear(Fraction(0), Fraction(0)) is True

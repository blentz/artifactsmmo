"""The witness generator's counted-crit bound (`formal/sim/winnable_witness.crit_bound`,
Lean `FightOdds.critBound`) behind a refreshing barrier: never above the exact
P(win) of the odds walk (`Formal.FightOdds.winProb_ge_critBound`), and tight
on Lor v king_slime, whose only losing paths are two or more slime crits."""

from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.fight_odds_core import RoundDamage, fight_odds, win_probability
from artifactsmmo_cli.ai.fight_terms_core import SCALE, fight_terms
from formal.sim.winnable_witness import best_crit_budget, crit_bound, monster_turns


def test_lor_v_king_slime_is_tight() -> None:
    """115 a hit, no player crit; the slime 46, or 70 on 20%, for 11 turns
    behind a 100 barrier: at most one crit survives 546 HP."""
    terms = fight_terms(115, 115 * SCALE, 1000, 0, 508_000, 546, 960, True, 100)
    damage = RoundDamage(1000, 115 * SCALE, 115 * SCALE, 0, 46 * SCALE, 70 * SCALE, 20, (), barrier=100)
    assert monster_turns(damage, True, 1000 * SCALE) == 11
    assert best_crit_budget(terms, damage, 546, 960) == 1
    exact = win_probability(fight_odds(terms, damage, 546, 960, 0, 0))
    assert crit_bound(terms, damage, 546, 960, 1) == exact
    assert exact == Fraction(4, 5) ** 11 + 11 * Fraction(1, 5) * Fraction(4, 5) ** 10


@settings(max_examples=150, deadline=None)
@given(mhp=st.integers(1, 300), barrier=st.integers(0, 120), kill=st.integers(30, 120),
       kx=st.integers(0, 60), pc=st.integers(0, 100), die=st.integers(5, 60),
       dx=st.integers(0, 60), mc=st.integers(0, 100), first=st.booleans(),
       hp=st.integers(1, 400))
def test_the_bound_never_exceeds_the_exact_odds(mhp, barrier, kill, kx, pc, die, dx, mc, first, hp):
    mean_kill = kill * SCALE + kx * SCALE * pc // 100
    mean_die = die * SCALE + dx * SCALE * mc // 100
    terms = fight_terms(1, mean_kill, mhp, 0, mean_die, hp, 400, first, barrier)
    damage = RoundDamage(mhp, kill * SCALE, (kill + kx) * SCALE, pc, die * SCALE, (die + dx) * SCALE,
                         mc, (), barrier=barrier)
    budget = best_crit_budget(terms, damage, hp, 400)
    assert crit_bound(terms, damage, hp, 400, budget) <= win_probability(
        fight_odds(terms, damage, hp, 400, 0, 0))

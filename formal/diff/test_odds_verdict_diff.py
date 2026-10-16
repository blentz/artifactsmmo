"""Differential: the fight gates' verdict on the odds — production
`fight_odds_core.odds_clear` over `fight_odds` — against the proved tree's
`θ ≤ Formal.FightOdds.winProb (fightOdds …)`, the inequality
`WinnableGrounded.rowWinnable_sound` and `winnableAcrossBand_at_threshold`
conclude (post-merge review 2026-10-16: the `predict_win` harness pins the
closed form, so nothing pinned the odds verdict). θ is drawn at the Lean odds
exactly and a hair either side of them, so `>=` against `>` is decided by the
equality case, plus a free θ in [0, 1]. Fights stay within 6 rounds so the
unmerged Lean tree (4^rounds paths) stays small."""

from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.fight_odds_core import RoundDamage, fight_odds, odds_clear, win_probability
from artifactsmmo_cli.ai.fight_terms_core import SCALE, fight_terms
from formal.diff.oracle_client import run_oracle

_HAIR = Fraction(1, 10**9)

_case = st.tuples(
    st.integers(min_value=1, max_value=60),                 # monster hp
    st.integers(min_value=10, max_value=60),                # kill normal (whole HP)
    st.integers(min_value=0, max_value=60),                 # kill crit extra
    st.integers(min_value=0, max_value=100),                # p crit
    st.integers(min_value=5, max_value=80),                 # die normal (whole HP)
    st.integers(min_value=0, max_value=80),                 # die crit extra
    st.integers(min_value=0, max_value=100),                # m crit
    st.booleans(),                                          # player first
    st.integers(min_value=1, max_value=300),                # hp
    st.integers(min_value=1, max_value=300),                # max hp
    st.integers(min_value=0, max_value=120),                # restore
    st.integers(min_value=0, max_value=4),                  # stock
    st.lists(st.integers(min_value=0, max_value=40), max_size=6),  # burn ticks (whole HP)
    st.fractions(min_value=0, max_value=1, max_denominator=1000),  # free θ
)


@settings(max_examples=200, deadline=None)
@given(cases=st.lists(_case, min_size=1, max_size=10))
def test_odds_verdict_matches_lean(cases):
    args, ours, free = [], [], []
    for mhp, kn, kx, pc, dn, dx, mc, pf, hp, max_hp, restore, stock, ticks, theta in cases:
        kill, die = kn * SCALE, dn * SCALE
        mean_kill = kill + (kx * SCALE * pc) // 100
        mean_die = die + (dx * SCALE * mc) // 100
        terms = fight_terms(1, mean_kill, mhp, 0, mean_die, hp, max_hp, pf)
        burn = tuple(t * SCALE for t in ticks)
        damage = RoundDamage(mhp, kill, kill + kx * SCALE, pc, die, die + dx * SCALE, mc, burn)
        args.append([1, mean_kill, mhp, 0, mean_die, 1 if pf else 0, hp, max_hp, restore, stock,
                     mhp, kill, kill + kx * SCALE, pc, die, die + dx * SCALE, mc, len(burn), *burn])
        ours.append(win_probability(fight_odds(terms, damage, hp, max_hp, restore, stock)))
        free.append(theta)
    for p_win, theta, row in zip(ours, free, run_oracle("fight_odds", args), strict=True):
        lean = sum((Fraction(r["prob_num"], r["prob_den"]) for r in row if r["win"]), Fraction(0))
        for at in (lean, lean - _HAIR, lean + _HAIR, theta):
            assert odds_clear(p_win, at) is (at <= lean), (p_win, lean, at)

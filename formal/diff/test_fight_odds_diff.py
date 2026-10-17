"""Differential: `ai/fight_odds_core.fight_odds` (merged walk) against the proved
tree `Formal.FightOdds.fightOdds` (spec 2026-10-15 fight-odds §1), lifesteal heals
on either side's crit included, and the monster's barrier (absorbed, refreshed
every 5 monster turns). Fights are kept to at most 6 rounds so the unmerged
Lean tree (4^rounds paths) stays small."""

from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.fight_odds_core import RoundDamage, fight_odds
from artifactsmmo_cli.ai.fight_terms_core import SCALE, fight_terms
from formal.diff.oracle_client import run_oracle

_case = st.tuples(
    st.integers(min_value=1, max_value=60),                 # monster hp
    st.integers(min_value=10, max_value=60),                # kill normal (whole HP)
    st.integers(min_value=0, max_value=60),                 # kill crit extra
    st.integers(min_value=0, max_value=100),                # p crit
    st.integers(min_value=5, max_value=80),                 # die normal (whole HP)
    st.integers(min_value=0, max_value=80),                 # die crit extra
    st.integers(min_value=0, max_value=100),                # m crit
    st.booleans(),                                          # player first
    st.integers(min_value=-5, max_value=300),               # hp
    st.integers(min_value=1, max_value=300),                # max hp
    st.integers(min_value=0, max_value=120),                # restore
    st.integers(min_value=0, max_value=4),                  # stock
    st.lists(st.integers(min_value=0, max_value=40), max_size=6),  # burn ticks (whole HP)
    st.one_of(st.just(0), st.integers(min_value=1, max_value=30)),  # player crit heal (whole HP)
    st.one_of(st.just(0), st.integers(min_value=1, max_value=30)),  # monster crit heal (whole HP)
    st.one_of(st.just(0), st.just(0), st.integers(min_value=1, max_value=200)),  # barrier (whole HP)
)


@settings(max_examples=200, deadline=None)
@given(cases=st.lists(_case, min_size=1, max_size=10))
def test_fight_odds_matches_lean(cases):
    args, ours = [], []
    for mhp, kn, kx, pc, dn, dx, mc, pf, hp, max_hp, restore, stock, ticks, ph, mh, bar in cases:
        # The monster's heal is held under its kill rate so the fight still ends
        # within 6 rounds: (kn - mh) * 6 >= mhp, a cure caps at mhp besides.
        mh = max(0, min(mh, kn - (mhp + 5) // 6))
        # The barrier is raised at most twice in 6 rounds (the start and one
        # refresh), so (kn - mh) * 6 - 2 * barrier >= mhp still ends it by then.
        bar = max(0, min(bar, ((kn - mh) * 6 - mhp) // 2))
        kill, die = kn * SCALE, dn * SCALE
        mean_kill = kill + (kx * SCALE * pc) // 100
        mean_die = die + (dx * SCALE * mc) // 100
        terms = fight_terms(1, mean_kill, mhp, 0, mean_die, hp, max_hp, pf, bar)
        burn = tuple(t * SCALE for t in ticks)
        damage = RoundDamage(mhp, kill, kill + kx * SCALE, pc, die, die + dx * SCALE, mc, burn,
                             ph * SCALE, mh * SCALE, bar)
        args.append([1, mean_kill, mhp, 0, mean_die, 1 if pf else 0, hp, max_hp, restore, stock,
                     mhp, kill, kill + kx * SCALE, pc, die, die + dx * SCALE, mc,
                     ph * SCALE, mh * SCALE, bar, bar, len(burn), *burn])
        ours.append(fight_odds(terms, damage, hp, max_hp, restore, stock))
    for mine, row in zip(ours, run_oracle("fight_odds", args), strict=True):
        lean = {(r["win"], r["turns"], r["hp_end"], r["used"]): Fraction(r["prob_num"], r["prob_den"])
                for r in row}
        assert {(e.win, e.turns, e.hp_end, e.used): e.prob for e in mine} == lean

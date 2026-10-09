"""Differential tests for consumable utility increment 1.

1. The live turn walk (`ai/fight_outcome_core.fight_outcome`) and the closed-form
   verdict over the extracted terms (`ai/fight_terms_core.terms_win`) must agree
   with the proved `Formal.FightOutcome.fightOutcome` / `closedWin` on random
   terms, including every guard exit and rounds-to-kill at and past the cap.
2. `combat.predict_win` at a CURRENT hp (dead, damaged, overfull) must agree
   with `Formal.FightOutcome.closedWin` over `PredictWin.killStepNet` /
   `PredictWin.dieStep`. `test_predict_win_diff.py` / `test_combat_margin_diff.py`
   pin the extracted verdict to the pre-extraction Lean model at full hp only;
   this one carries the effective-hp (`DEAD` exit) branch.
"""
import random

from hypothesis import given, settings
from hypothesis import strategies as st
from pytest import MonkeyPatch

import artifactsmmo_cli.ai.combat as combat_mod
from artifactsmmo_cli.ai.equipment.projection import ProjectedStats
from artifactsmmo_cli.ai.fight_outcome_core import fight_outcome
from artifactsmmo_cli.ai.fight_terms_core import fight_terms, terms_win
from artifactsmmo_cli.ai.world_state import ELEMENTS
from formal.diff.oracle_client import run_oracle

_POS_KILL = st.integers(min_value=10_000, max_value=1_000_000)
_POS_DIE = st.integers(min_value=10_000, max_value=2_000_000)
# Weighted toward the walked regime (every guard passed); each exit still occurs.
_case = st.tuples(
    st.integers(min_value=-2, max_value=60),                                # raw_player
    st.one_of(st.integers(min_value=-5000, max_value=0), _POS_KILL, _POS_KILL, _POS_KILL),
    st.integers(min_value=0, max_value=600),                                # monster hp
    st.one_of(st.just(0), st.just(0), st.integers(min_value=1, max_value=120)),
    st.one_of(st.integers(min_value=-5000, max_value=0), _POS_DIE, _POS_DIE, _POS_DIE),
    st.booleans(),                                                          # player first
    st.integers(min_value=-5, max_value=2500),                              # hp (walk)
    st.integers(min_value=-5, max_value=2500),                              # hp (terms)
    st.integers(min_value=0, max_value=2000),                               # max hp
    st.integers(min_value=0, max_value=800),                                # restore
    st.integers(min_value=0, max_value=12),                                 # stock
)


@settings(max_examples=300, deadline=None)
@given(cases=st.lists(_case, min_size=1, max_size=25))
def test_fight_outcome_matches_lean(cases):
    args = [[raw, ks, mhp, recon, ds, 1 if pf else 0, hp, max_hp, restore, stock]
            for raw, ks, mhp, recon, ds, pf, hp, _, max_hp, restore, stock in cases]
    lean = run_oracle("fight_outcome", args)
    for case, row in zip(cases, lean, strict=True):
        raw, ks, mhp, recon, ds, pf, hp, terms_hp, max_hp, restore, stock = case
        # The walk reads the monster side of the terms only: build them at an
        # unrelated hp to pin that it walks from `hp_start`.
        walked = fight_outcome(fight_terms(raw, ks, mhp, recon, ds, terms_hp, max_hp, pf),
                               hp, max_hp, restore, stock)
        assert (walked.win, walked.turns, walked.hp_end, walked.used) == (
            row["win"], row["turns"], row["hp_end"], row["used"]), case
        assert terms_win(fight_terms(raw, ks, mhp, recon, ds, hp, max_hp, pf)) == row["closed_win"], case


def test_restore_turns_a_loss_into_a_win_against_lean():
    """A pinned case where the potion matters: 100 HP, 30 per round, kill in 6."""
    case = [10, 10_000, 6, 0, 300_000, 1, 100, 100, 40, 3]
    row = run_oracle("fight_outcome", [case])[0]
    assert row == {"win": True, "turns": 6, "hp_end": 700_000, "used": 3, "closed_win": False}
    walked = fight_outcome(fight_terms(10, 10_000, 6, 0, 300_000, 100, 100, True), 100, 100, 40, 3)
    assert (walked.win, walked.turns, walked.hp_end, walked.used) == (True, 6, 700_000, 3)



def test_boundaries_against_lean():
    """The exact boundaries random terms rarely land on: at exactly half the
    player has NOT lost more than 50% (no drink), and a pool of exactly 0 is dead."""
    cases = {
        # (raw, kill, monster hp, recon, die, first, hp, max hp, restore, stock)
        (10, 10_000, 1, 0, 300_000, 1, 50, 100, 40, 3): (True, 1, 500_000, 0),
        (10, 10_000, 6, 0, 300_000, 0, 30, 100, 40, 9): (False, 1, 0, 0),
    }
    rows = run_oracle("fight_outcome", [list(c) for c in cases])
    for (case, expected), row in zip(cases.items(), rows, strict=True):
        raw, ks, mhp, recon, ds, pf, hp, max_hp, restore, stock = case
        walked = fight_outcome(fight_terms(raw, ks, mhp, recon, ds, hp, max_hp, pf == 1),
                               hp, max_hp, restore, stock)
        assert (row["win"], row["turns"], row["hp_end"], row["used"]) == expected, case
        assert (walked.win, walked.turns, walked.hp_end, walked.used) == expected, case

def _rand_elem_map(rng: random.Random, lo: int, hi: int, prob: float) -> dict[str, int]:
    return {e: rng.randint(lo, hi) for e in ELEMENTS if rng.random() < prob}


def _elem_args(attack: dict[str, int], dmg_global: int, dmg_elements: dict[str, int],
               resist: dict[str, int]) -> list[int]:
    out: list[int] = []
    for e in ELEMENTS:
        out += [attack.get(e, 0), dmg_global + dmg_elements.get(e, 0), resist.get(e, 0)]
    return out


@settings(max_examples=300, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
def test_predict_win_at_current_hp_matches_lean(seed):
    rng = random.Random(seed)
    stats = ProjectedStats(
        attack=_rand_elem_map(rng, 0, 60, 0.7), dmg=rng.randint(0, 50),
        dmg_elements=_rand_elem_map(rng, 0, 40, 0.5), resistance=_rand_elem_map(rng, 0, 70, 0.6),
        critical_strike=rng.randint(0, 60), initiative=rng.randint(0, 200),
        max_hp=rng.randint(1, 2000),
    )
    m = {
        "hp": rng.randint(1, 2000), "attack": _rand_elem_map(rng, 0, 60, 0.7),
        "resist": _rand_elem_map(rng, 0, 70, 0.6), "crit": rng.randint(0, 60),
        "init": rng.randint(0, 200), "lifesteal": rng.choice([0, 0, rng.randint(1, 60)]),
        "poison": rng.choice([0, 0, rng.randint(1, 100)]),
        "barrier": rng.choice([0, 0, rng.randint(1, 500)]),
        "burn": rng.choice([0, 0, rng.randint(1, 100)]),
        "healing": rng.choice([0, 0, rng.randint(1, 50)]),
        "recon": rng.choice([0, 0, rng.randint(1, 30)]),
        "void": rng.choice([0, 0, rng.randint(1, 20)]),
        "berserk": rng.choice([0, 0, rng.randint(1, 50)]),
        "frenzy": rng.choice([0, 0, rng.randint(1, 50)]),
        "bubble": rng.choice([0, 0, rng.randint(1, 50)]),
        "sun": rng.choice([0, 0, rng.randint(1, 50)]),
        "greed": rng.choice([0, 0, rng.randint(1, 20)]),
        "mirror": rng.choice([0, 0, rng.randint(1, 50)]),
    }
    hp = rng.choice([rng.randint(-5, 0), rng.randint(1, stats.max_hp), stats.max_hp + rng.randint(1, 300)])

    class _FakeGameData:
        def monster_hp(self, c):
            return m["hp"]

        def monster_attack(self, c):
            return dict(m["attack"])

        def monster_resistance(self, c):
            return dict(m["resist"])

        def monster_critical_strike(self, c):
            return m["crit"]

        def monster_initiative(self, c):
            return m["init"]

        def monster_lifesteal(self, c):
            return m["lifesteal"]

        def monster_poison(self, c):
            return m["poison"]

        def monster_barrier(self, c):
            return m["barrier"]

        def monster_burn(self, c):
            return m["burn"]

        def monster_healing(self, c):
            return m["healing"]

        def monster_reconstitution(self, c):
            return m["recon"]

        def monster_void_drain(self, c):
            return m["void"]

        def monster_berserker_rage(self, c):
            return m["berserk"]

        def monster_frenzy(self, c):
            return m["frenzy"]

        def monster_protective_bubble(self, c):
            return m["bubble"]

        def monster_sun_shield(self, c):
            return m["sun"]

        def monster_greed(self, c):
            return m["greed"]

        def monster_enchanted_mirror(self, c):
            return m["mirror"]

        def item_stats(self, c):
            return None

    class _FakeState:
        max_hp = stats.max_hp
        equipment: dict[str, str] = {}
        attack: dict[str, int] = {}

    state = _FakeState()
    state.hp = hp  # type: ignore[attr-defined]
    with MonkeyPatch.context() as mp:
        mp.setattr(combat_mod, "pick_loadout_cached", lambda code, s, gd: {})
        mp.setattr(combat_mod, "project_loadout_stats", lambda s, loadout, gd: stats)
        py = combat_mod.predict_win(state, _FakeGameData(), "M")
        margin = combat_mod.combat_margin(state, _FakeGameData(), "M")

    # RUF005 declined: the positional 46-int oracle layout of test_predict_win_diff.py.
    args = (
        _elem_args(stats.attack, stats.dmg, stats.dmg_elements, m["resist"])  # noqa: RUF005
        + [stats.critical_strike, m["hp"]]
        + _elem_args(m["attack"], 0, {}, stats.resistance)
        + [m["crit"], stats.max_hp, 1 if stats.initiative >= m["init"] else 0]
        + [0, sum(stats.attack.values()), m["lifesteal"], sum(m["attack"].values())]
        + [m["poison"], m["barrier"], m["burn"], m["healing"], m["recon"], m["void"],
           m["berserk"], m["frenzy"], m["bubble"]]
        + [0]
        + [m["sun"], m["greed"], m["mirror"]]
        + [hp]
    )
    lean = run_oracle("predict_win_hp", [args])[0]
    assert py == lean["win"], (seed, hp)
    assert py == (margin > 0), (seed, hp)

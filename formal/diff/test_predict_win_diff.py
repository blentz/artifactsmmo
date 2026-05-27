"""Differential test: real Python `predict_win` (float arithmetic) must agree
with the proved Lean `predictWin` (exact integer arithmetic).

`predict_win(state, game_data, monster_code)` internally calls
`pick_loadout` / `project_loadout_stats` and the monster getters
(`monster_hp` / `monster_attack` / `monster_resistance` /
`monster_critical_strike` / `monster_initiative`). To isolate the ARITHMETIC +
verdict we control all of those so the RESOLVED stats fed to the formula are
identical on both sides:

* `pick_loadout` is monkeypatched to a fixed sentinel loadout.
* `project_loadout_stats` is monkeypatched to return a controlled
  `ProjectedStats` (player attack / dmg / dmg_elements / resistance /
  critical_strike / initiative / max_hp).
* the five monster getters are monkeypatched to controlled values.

Both the Python `predict_win` and the Lean oracle then compute from the SAME
resolved stat tuple, so the test verifies the exact-integer model matches
Python's float arithmetic and the win verdict. The Lean oracle recomputes the
per-element raw damage with `rawHit`/`elementDamage`, so the element-damage
reductions (`round_half_up`, resist subtraction) are exercised too.

Generates >= 200 random stat tuples; asserts the boolean verdicts match. Any
float-vs-exact disagreement is a real finding and surfaces the exact tuple.
"""
import random

from hypothesis import given, settings, strategies as st
from pytest import MonkeyPatch

import artifactsmmo_cli.ai.combat as combat_mod
from artifactsmmo_cli.ai.equipment.projection import ProjectedStats
from artifactsmmo_cli.ai.world_state import ELEMENTS
from formal.diff.oracle_client import run_oracle

MONSTER = "M"


def _elem_args(attack: dict, dmg_global: int, dmg_elements: dict, resist: dict) -> list[int]:
    """Flatten the four elements into [a, dmgPct, resist] triples, where
    dmgPct = dmg_global + dmg_elements[e] (combined as Python's _expected_hit)."""
    out: list[int] = []
    for e in ELEMENTS:
        out.append(attack.get(e, 0))
        out.append(dmg_global + dmg_elements.get(e, 0))
        out.append(resist.get(e, 0))
    return out


def _run(p_attack, p_dmg, p_dmg_elem, p_resist, p_crit, p_max_hp, p_init,
         m_hp, m_attack, m_resist, m_crit, m_init):
    stats = ProjectedStats(
        attack=dict(p_attack), dmg=p_dmg, dmg_elements=dict(p_dmg_elem),
        resistance=dict(p_resist), critical_strike=p_crit, initiative=p_init,
        max_hp=p_max_hp,
    )

    class _FakeGameData:
        def monster_hp(self, c):
            return m_hp

        def monster_attack(self, c):
            return dict(m_attack)

        def monster_resistance(self, c):
            return dict(m_resist)

        def monster_critical_strike(self, c):
            return m_crit

        def monster_initiative(self, c):
            return m_init

    with MonkeyPatch.context() as mp:
        mp.setattr(combat_mod, "pick_loadout", lambda code, state, gd: object())
        mp.setattr(combat_mod, "project_loadout_stats", lambda state, loadout, gd: stats)
        py = combat_mod.predict_win(object(), _FakeGameData(), MONSTER)

    # monster attack uses dmg_global=0, dmg_elements={} vs player resistance.
    args = (
        _elem_args(p_attack, p_dmg, p_dmg_elem, m_resist)  # player vs monster resist
        + [p_crit, m_hp]
        + _elem_args(m_attack, 0, {}, p_resist)            # monster vs player resist
        + [m_crit, p_max_hp, 1 if p_init >= m_init else 0]
    )
    lean = run_oracle("predict_win", [args])[0]
    return py, lean


def _rand_elem_map(rng: random.Random, lo: int, hi: int, prob: float) -> dict:
    return {e: rng.randint(lo, hi) for e in ELEMENTS if rng.random() < prob}


@settings(max_examples=260, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
def test_python_matches_lean(seed):
    rng = random.Random(seed)
    p_attack = _rand_elem_map(rng, 0, 60, 0.7)
    p_dmg = rng.randint(0, 50)
    p_dmg_elem = _rand_elem_map(rng, 0, 40, 0.5)
    p_resist = _rand_elem_map(rng, 0, 70, 0.6)
    p_crit = rng.randint(0, 60)
    p_max_hp = rng.randint(1, 2000)
    p_init = rng.randint(0, 200)
    m_hp = rng.randint(1, 2000)
    m_attack = _rand_elem_map(rng, 0, 60, 0.7)
    m_resist = _rand_elem_map(rng, 0, 70, 0.6)
    m_crit = rng.randint(0, 60)
    m_init = rng.randint(0, 200)

    py, lean = _run(p_attack, p_dmg, p_dmg_elem, p_resist, p_crit, p_max_hp,
                    p_init, m_hp, m_attack, m_resist, m_crit, m_init)
    assert py == lean["win"], (
        f"verdict mismatch py={py} lean={lean} "
        f"p_attack={p_attack} p_dmg={p_dmg} p_dmg_elem={p_dmg_elem} "
        f"p_resist={p_resist} p_crit={p_crit} p_max_hp={p_max_hp} p_init={p_init} "
        f"m_hp={m_hp} m_attack={m_attack} m_resist={m_resist} m_crit={m_crit} m_init={m_init}"
    )


def test_initiative_tiebreak_binds_against_lean():
    """A dead heat on rounds where initiative decides: equal rounds_to_kill /
    rounds_to_die, player wins iff it goes first (the combat.py:79 `<=` vs `<`
    tiebreak). Pins the tiebreak against Lean."""
    # Player: 50 fire attack, no crit/resist => raw 50, rounds depend on hp.
    # Symmetric monster so rounds_to_kill == rounds_to_die.
    p = dict(attack={"fire": 50}, dmg=0, dmg_elem={}, resist={}, crit=0,
             max_hp=100, init=10)
    m = dict(hp=100, attack={"fire": 50}, resist={}, crit=0, init=10)
    # player first (init equal => >= holds) => win on the <= tiebreak.
    py_first, lean_first = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                                p["crit"], p["max_hp"], p["init"], m["hp"],
                                m["attack"], m["resist"], m["crit"], m["init"])
    assert py_first is True
    assert py_first == lean_first["win"]
    # monster first (player init below) => lose on the strict < tiebreak.
    py_second, lean_second = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                                  p["crit"], p["max_hp"], 9, m["hp"],
                                  m["attack"], m["resist"], m["crit"], m["init"])
    assert py_second is False
    assert py_second == lean_second["win"]


def test_maxturns_loss_binds_against_lean():
    """A monster needing > MAX_TURNS rounds to kill is a loss even though the
    player is unkillable. Pins the MAX_TURNS cap against Lean."""
    # raw 1 vs 100000 hp => rounds_to_kill > 100 => loss; monster can't hit.
    py, lean = _run({"fire": 1}, 0, {}, {}, 0, 1000, 100, 100000,
                    {}, {}, 0, 0)
    assert py is False
    assert py == lean["win"]

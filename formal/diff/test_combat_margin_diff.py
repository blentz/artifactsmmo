"""Differential test: real Python `combat_margin` must agree with the proved
Lean `combatMargin` (exact integer arithmetic) for the same stat tuple.

`combat_margin(state, game_data, monster_code)` follows exactly the same
control-flow as `predict_win`, so the same monkeypatch strategy applies:

* `pick_loadout` is monkeypatched to a fixed sentinel loadout.
* `project_loadout_stats` is monkeypatched to a controlled `ProjectedStats`.
* The monster getters are monkeypatched to controlled values.

The oracle returns `{"margin": int}` from the proved Lean `combatMargin`.
The differential asserts exact int equality between Python and Lean.

Invariant check: `predict_win(...) == (combat_margin(...) > 0)` is verified
here in addition to the exact-value agreement, acting as a double-bind.
"""
import random

from hypothesis import given, settings, strategies as st
from pytest import MonkeyPatch

import artifactsmmo_cli.ai.combat as combat_mod
from artifactsmmo_cli.ai.equipment.projection import ProjectedStats
from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.world_state import ELEMENTS
from formal.diff.oracle_client import run_oracle

MONSTER = "M"


def _elem_args(attack: dict, dmg_global: int, dmg_elements: dict, resist: dict) -> list[int]:
    """Flatten four elements into [attack, dmgPct, resist] triples where
    dmgPct = dmg_global + dmg_elements[e] (combined as Python's _expected_hit)."""
    out: list[int] = []
    for e in ELEMENTS:
        out.append(attack.get(e, 0))
        out.append(dmg_global + dmg_elements.get(e, 0))
        out.append(resist.get(e, 0))
    return out


def _run(p_attack, p_dmg, p_dmg_elem, p_resist, p_crit, p_max_hp, p_init,
         m_hp, m_attack, m_resist, m_crit, m_init,
         p_lifesteal=0, m_lifesteal=0, m_poison=0, m_barrier=0, m_burn=0, m_healing=0,
         m_recon=0, m_void=0, m_berserk=0, m_frenzy=0, m_bubble=0, p_antipoison=0,
         m_sun_shield=0, m_greed=0, m_enchanted_mirror=0):
    """Run both Python combat_margin and the Lean oracle on the same resolved
    stat tuple. Returns (py_margin, lean_result) where lean_result["margin"] is
    the Lean integer margin."""
    stats = ProjectedStats(
        attack=dict(p_attack), dmg=p_dmg, dmg_elements=dict(p_dmg_elem),
        resistance=dict(p_resist), critical_strike=p_crit, initiative=p_init,
        max_hp=p_max_hp,
    )
    p_atk_sum = sum(stats.attack.values())
    m_atk_sum = sum(m_attack.values())
    loadout = {"weapon_slot": "_ls"} if (p_lifesteal or p_antipoison) else {}

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

        def monster_lifesteal(self, c):
            return m_lifesteal

        def monster_poison(self, c):
            return m_poison

        def monster_barrier(self, c):
            return m_barrier

        def monster_burn(self, c):
            return m_burn

        def monster_healing(self, c):
            return m_healing

        def monster_reconstitution(self, c):
            return m_recon

        def monster_void_drain(self, c):
            return m_void

        def monster_berserker_rage(self, c):
            return m_berserk

        def monster_frenzy(self, c):
            return m_frenzy

        def monster_protective_bubble(self, c):
            return m_bubble

        def monster_sun_shield(self, c):
            return m_sun_shield

        def monster_greed(self, c):
            return m_greed

        def monster_enchanted_mirror(self, c):
            return m_enchanted_mirror

        def item_stats(self, c):
            return (ItemStats(code=c, level=1, type_="weapon", lifesteal=p_lifesteal,
                              antipoison=p_antipoison)
                    if c == "_ls" else None)

    # Stub state. Lean oracle uses full HP (no current-hp dimension); the Python
    # combat_margin has the same state.hp gate, so stub reports hp = max_hp to
    # keep the formula equivalent (same approach as test_predict_win_diff.py).
    class _FakeState:
        hp = p_max_hp
        max_hp = p_max_hp
        equipment: dict[str, str] = {}

    with MonkeyPatch.context() as mp:
        mp.setattr(combat_mod, "pick_loadout_cached", lambda code, state, gd: loadout)
        mp.setattr(combat_mod, "project_loadout_stats", lambda state, loadout, gd: stats)
        py_margin = combat_mod.combat_margin(_FakeState(), _FakeGameData(), MONSTER)
        py_win = combat_mod.predict_win(_FakeState(), _FakeGameData(), MONSTER)

    # Same arg layout as test_predict_win_diff.py (46 ints, indices 0..45).
    args = (
        _elem_args(p_attack, p_dmg, p_dmg_elem, m_resist)  # player vs monster resist
        + [p_crit, m_hp]
        + _elem_args(m_attack, 0, {}, p_resist)            # monster vs player resist
        + [m_crit, p_max_hp, 1 if p_init >= m_init else 0]
        + [p_lifesteal, p_atk_sum, m_lifesteal, m_atk_sum]
        + [m_poison, m_barrier, m_burn, m_healing, m_recon, m_void, m_berserk, m_frenzy, m_bubble]
        + [p_antipoison]
        + [m_sun_shield, m_greed, m_enchanted_mirror]
    )
    lean = run_oracle("combat_margin", [args])[0]
    return py_margin, lean, py_win


def _rand_elem_map(rng: random.Random, lo: int, hi: int, prob: float) -> dict:
    return {e: rng.randint(lo, hi) for e in ELEMENTS if rng.random() < prob}


@settings(max_examples=260, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
def test_python_matches_lean(seed):
    """Random stat tuples: exact int margin matches Lean, and sign matches predict_win."""
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
    p_lifesteal = rng.choice([0, 0, rng.randint(1, 60)])
    m_lifesteal = rng.choice([0, 0, rng.randint(1, 60)])
    m_poison = rng.choice([0, 0, rng.randint(1, 100)])
    m_barrier = rng.choice([0, 0, rng.randint(1, 500)])
    m_burn = rng.choice([0, 0, rng.randint(1, 100)])
    m_healing = rng.choice([0, 0, rng.randint(1, 50)])
    m_recon = rng.choice([0, 0, rng.randint(1, 30)])
    m_void = rng.choice([0, 0, rng.randint(1, 40)])
    m_berserk = rng.choice([0, 0, rng.randint(1, 100)])
    m_frenzy = rng.choice([0, 0, rng.randint(1, 100)])
    m_bubble = rng.choice([0, 0, rng.randint(1, 100)])
    p_antipoison = rng.choice([0, 0, rng.randint(1, 120)])
    m_sun_shield = rng.choice([0, 0, rng.randint(1, 100)])
    m_greed = rng.choice([0, 0, rng.randint(1, 30)])
    m_enchanted_mirror = rng.choice([0, 0, rng.randint(1, 100)])

    py_margin, lean, py_win = _run(
        p_attack, p_dmg, p_dmg_elem, p_resist, p_crit, p_max_hp,
        p_init, m_hp, m_attack, m_resist, m_crit, m_init,
        p_lifesteal, m_lifesteal, m_poison, m_barrier, m_burn, m_healing, m_recon,
        m_void, m_berserk, m_frenzy, m_bubble, p_antipoison=p_antipoison,
        m_sun_shield=m_sun_shield, m_greed=m_greed, m_enchanted_mirror=m_enchanted_mirror)
    assert py_margin == lean["margin"], (
        f"margin mismatch py={py_margin} lean={lean} "
        f"p_attack={p_attack} p_dmg={p_dmg} p_crit={p_crit} p_max_hp={p_max_hp} "
        f"p_init={p_init} m_hp={m_hp} m_attack={m_attack} m_crit={m_crit} m_init={m_init}"
    )
    # Invariant: sign agrees with predict_win
    assert py_win == (py_margin > 0), (
        f"sign invariant violated: predict_win={py_win} margin={py_margin}"
    )


def test_sustain_win_returns_win_margin():
    """die_step <= 0 branch: monster deals no damage AND player has no sustain issues.
    Python returns WIN_MARGIN (101), Lean returns winMargin (101). Sign > 0."""
    # Monster has no attack at all → dieStep = 0 → out-sustain win.
    py_margin, lean, py_win = _run({"fire": 50}, 0, {}, {}, 0, 100, 10,
                                   100, {}, {}, 0, 0)
    assert py_win is True
    assert py_margin == combat_mod.WIN_MARGIN
    assert py_margin == lean["margin"]
    assert lean["margin"] > 0


def test_unkillable_returns_lose_margin():
    """raw_player <= 0: player cannot damage monster → LOSE_MARGIN (-101)."""
    py_margin, lean, py_win = _run({}, 0, {}, {}, 0, 100, 10,
                                   100, {"fire": 50}, {}, 0, 0)
    assert py_win is False
    assert py_margin == combat_mod.LOSE_MARGIN
    assert py_margin == lean["margin"]
    assert lean["margin"] < 0


def test_player_first_tiebreak_margin_is_one():
    """Numeric regime, player_first=True, rtk == rtd: margin = rtd - rtk + 1 = 1.
    Pins the +1 player-first adjustment — dropping it would give margin=0 (not win)."""
    # Player raw 50, monster hp 100 => rtk = 2 (ceil(100*10000 / 500000))
    # Monster raw 50, player hp 100 => rtd = 2
    # player_first=True (p_init 10 >= m_init 10) => margin = 2 - 2 + 1 = 1
    py_margin, lean, py_win = _run({"fire": 50}, 0, {}, {}, 0, 100, 10,
                                   100, {"fire": 50}, {}, 0, 10)
    assert py_win is True
    assert py_margin == 1
    assert py_margin == lean["margin"]


def test_monster_first_tiebreak_margin_is_zero():
    """Numeric regime, player_first=False, rtk == rtd: margin = rtd - rtk + 0 = 0.
    Not > 0 so predict_win=False. Pins the +0 (no adjustment) case."""
    # Same stats but monster goes first (p_init 9 < m_init 10)
    py_margin, lean, py_win = _run({"fire": 50}, 0, {}, {}, 0, 100, 9,
                                   100, {"fire": 50}, {}, 0, 10)
    assert py_win is False
    assert py_margin == 0
    assert py_margin == lean["margin"]


def test_larger_cushion_encodes_larger_margin():
    """A player that kills faster (more attack) has a strictly larger margin than
    a weaker player (monotone cushion). Pins the magnitude ordering."""
    # Weak: rtk 4 (monster hp 200, raw 50), rtd 2 (player hp 100, raw 50), player_first
    # => margin = 2 - 4 + 1 = -1 (loss, borderline).
    py_weak, lean_weak, _ = _run({"fire": 50}, 0, {}, {}, 0, 100, 10,
                                  200, {"fire": 50}, {}, 0, 10)
    # Strong: rtk 2 (monster hp 100), rtd 2, player_first => margin = 1 (win).
    py_strong, lean_strong, _ = _run({"fire": 50}, 0, {}, {}, 0, 100, 10,
                                      100, {"fire": 50}, {}, 0, 10)
    assert py_strong > py_weak
    assert lean_strong["margin"] > lean_weak["margin"]
    assert py_weak == lean_weak["margin"]
    assert py_strong == lean_strong["margin"]

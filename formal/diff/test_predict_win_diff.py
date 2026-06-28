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
from artifactsmmo_cli.ai.game_data import ItemStats
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
         m_hp, m_attack, m_resist, m_crit, m_init,
         p_lifesteal=0, m_lifesteal=0, m_poison=0, m_barrier=0, m_burn=0, m_healing=0,
         m_recon=0, m_void=0, m_berserk=0, m_frenzy=0, m_bubble=0, p_antipoison=0,
         m_sun_shield=0, m_greed=0, m_enchanted_mirror=0):
    stats = ProjectedStats(
        attack=dict(p_attack), dmg=p_dmg, dmg_elements=dict(p_dmg_elem),
        resistance=dict(p_resist), critical_strike=p_crit, initiative=p_init,
        max_hp=p_max_hp,
    )
    # Player lifesteal is summed over the post-loadout equipment; route it through
    # one dummy slot carrying p_lifesteal. pAtkSum/mAtkSum are the RAW attack sums
    # the heal formula uses (crit% × lifesteal% × Σattack).
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

    # Stub state object the test reuses. Lean oracle assumes full HP
    # (no current-hp dimension); the Python predict_win added a
    # state.hp gate after the trace-cycle-63 fix, so the stub must
    # report hp = max_hp to keep the formula equivalent.
    class _FakeState:
        hp = p_max_hp
        max_hp = p_max_hp
        equipment: dict[str, str] = {}

    with MonkeyPatch.context() as mp:
        mp.setattr(combat_mod, "pick_loadout", lambda code, state, gd: loadout)
        mp.setattr(combat_mod, "project_loadout_stats", lambda state, loadout, gd: stats)
        py = combat_mod.predict_win(_FakeState(), _FakeGameData(), MONSTER)

    # monster attack uses dmg_global=0, dmg_elements={} vs player resistance.
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
    # Lifesteal: 0 most of the time (matches the common case), non-zero often
    # enough to exercise the net-step + the killStep≤0 / dieStep≤0 guards.
    p_lifesteal = rng.choice([0, 0, rng.randint(1, 60)])
    m_lifesteal = rng.choice([0, 0, rng.randint(1, 60)])
    # Poison: 0 most of the time, non-zero often enough to exercise the per-turn
    # DoT term in dieStep AND the no-direct-damage (raw_monster==0) poison kill.
    m_poison = rng.choice([0, 0, rng.randint(1, 100)])
    # Barrier: 0 most of the time, non-zero often enough to exercise the effective-HP
    # extension to rounds_to_kill (incl. pushing the kill past MAX_TURNS).
    m_barrier = rng.choice([0, 0, rng.randint(1, 500)])
    # Burn: 0 most of the time, non-zero often enough to exercise the percent-of-attack
    # DoT term in dieStep (incl. its interaction with the dieStep<=0 sustain guard).
    m_burn = rng.choice([0, 0, rng.randint(1, 100)])
    # Healing: 0 most of the time, non-zero often enough to exercise the killStep regen
    # subtraction (incl. driving killStep <= 0 ⇒ unkillable).
    m_healing = rng.choice([0, 0, rng.randint(1, 50)])
    # Reconstitution: 0 most of the time, a small period often enough to exercise the
    # turn-cap branch (unwinnable when rounds_to_kill >= period).
    m_recon = rng.choice([0, 0, rng.randint(1, 30)])
    # Void drain: 0 most of the time, non-zero often enough to exercise BOTH its
    # dieStep (player loss) and killStep (monster self-heal) terms.
    m_void = rng.choice([0, 0, rng.randint(1, 40)])
    # Berserker-rage / frenzy: 0 most of the time, non-zero often enough to exercise
    # each monster-damage-boost dieStep term (incl. the floor-div // 2 vs Lean / 2).
    m_berserk = rng.choice([0, 0, rng.randint(1, 100)])
    m_frenzy = rng.choice([0, 0, rng.randint(1, 100)])
    # Protective bubble: 0 most of the time, else a resist % in [1, 100] (the modeled
    # domain) — exercises the killStep player-damage reduction incl. ks <= 0 at 100%.
    m_bubble = rng.choice([0, 0, rng.randint(1, 100)])
    # Player antipoison: 0 most of the time, else enough to partially/fully cancel the
    # monster poison (exercises max(0, poison - antipoison) incl. over-cancel to 0).
    p_antipoison = rng.choice([0, 0, rng.randint(1, 120)])
    # Sun-shield: 0 most of the time, else a reduction % in [1, 100]. Merged with bubble
    # into the single (bubble+sun_shield) killStep reduction — drawn independently so the
    # sum can exceed 100 (Python and Lean both floor the merged term, so they still agree).
    m_sun_shield = rng.choice([0, 0, rng.randint(1, 100)])
    # Greed: 0 most of the time, else a ramp % in [1, 30] — exercises the 9-stack dieStep
    # boost (incl. the // 2 floor and driving the death faster than the kill).
    m_greed = rng.choice([0, 0, rng.randint(1, 30)])
    # Enchanted-mirror: 0 most of the time, else a reflect % in [1, 100] — exercises the
    # only dieStep term scaled by the player's own raw output (raw_player, p_crit).
    m_enchanted_mirror = rng.choice([0, 0, rng.randint(1, 100)])

    py, lean = _run(p_attack, p_dmg, p_dmg_elem, p_resist, p_crit, p_max_hp,
                    p_init, m_hp, m_attack, m_resist, m_crit, m_init,
                    p_lifesteal, m_lifesteal, m_poison, m_barrier, m_burn, m_healing, m_recon,
                    m_void, m_berserk, m_frenzy, m_bubble, p_antipoison=p_antipoison,
                    m_sun_shield=m_sun_shield, m_greed=m_greed, m_enchanted_mirror=m_enchanted_mirror)
    assert py == lean["win"], (
        f"verdict mismatch py={py} lean={lean} "
        f"p_attack={p_attack} p_dmg={p_dmg} p_dmg_elem={p_dmg_elem} "
        f"p_resist={p_resist} p_crit={p_crit} p_max_hp={p_max_hp} p_init={p_init} "
        f"m_hp={m_hp} m_attack={m_attack} m_resist={m_resist} m_crit={m_crit} m_init={m_init} "
        f"p_lifesteal={p_lifesteal} m_lifesteal={m_lifesteal} m_poison={m_poison} "
        f"m_barrier={m_barrier} m_burn={m_burn} m_healing={m_healing} m_recon={m_recon} "
        f"m_void={m_void} m_berserk={m_berserk} m_frenzy={m_frenzy} m_bubble={m_bubble} "
        f"p_antipoison={p_antipoison} m_sun_shield={m_sun_shield} m_greed={m_greed} "
        f"m_enchanted_mirror={m_enchanted_mirror}"
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


def test_round_half_up_boundary_binds_against_lean():
    """Deterministically pin `_round_half_up` against Lean at a rounding boundary
    (so the kill does not rely on random Hypothesis coverage). The `+0.5 -> +1.5`
    mutant adds 1 to every rounding; with monster resistance the output(+1) and
    blocked(+1) do NOT cancel, dropping raw_player 50 -> 49, which pushes
    rounds_to_kill 100 -> 103 past MAX_TURNS and flips the verdict True -> False.
    Player fire 100 vs monster fire-resist 50 => raw 50; monster hp 5000 => exactly
    100 rounds (= MAX_TURNS, a win); monster deals no damage."""
    py, lean = _run({"fire": 100}, 0, {}, {}, 0, 1000, 10,
                    5000, {}, {"fire": 50}, 0, 0)
    assert py is True
    assert py == lean["win"]


def test_berserker_rage_flips_winnable_fight_against_lean():
    """Berserker-rage's always-active monster-damage boost raises dieStep, flipping a
    won tiebreak (rtk == rtd == 2) to a loss. Pins the boost term (incl. the `/ 2`
    floor) against Lean with frenzy held at 0 so it is the sole decider. Player hp 100,
    raw 50 vs hp 100; berserk 100% => dieStep 5e5 + 100*50*200/2=5e5 = 1e6 => rtd 1 < 2."""
    p = dict(attack={"fire": 50}, dmg=0, dmg_elem={}, resist={}, crit=0,
             max_hp=100, init=10)
    m = dict(hp=100, attack={"fire": 50}, resist={}, crit=0, init=10)
    py_no, lean_no = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                          p["crit"], p["max_hp"], p["init"], m["hp"],
                          m["attack"], m["resist"], m["crit"], m["init"])
    assert py_no is True and py_no == lean_no["win"]
    py_b, lean_b = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                        p["crit"], p["max_hp"], p["init"], m["hp"],
                        m["attack"], m["resist"], m["crit"], m["init"],
                        m_berserk=100)
    assert py_b is False
    assert py_b == lean_b["win"]


def test_greed_flips_winnable_fight_against_lean():
    """Greed's 9-stack monster-damage boost raises dieStep, flipping a won tiebreak
    (rtk == rtd == 2) to a loss. Pins the greed term (9× stacks, incl. the `/ 2` floor)
    against Lean. Player hp 100, raw 50 vs hp 100; greed 20 => dieStep 5e5 + 9*20*50*200/2
    = 5e5 + 9e5 = 1.4e6 => rtd 1 < rtk 2."""
    p = dict(attack={"fire": 50}, dmg=0, dmg_elem={}, resist={}, crit=0,
             max_hp=100, init=10)
    m = dict(hp=100, attack={"fire": 50}, resist={}, crit=0, init=10)
    py_no, lean_no = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                          p["crit"], p["max_hp"], p["init"], m["hp"],
                          m["attack"], m["resist"], m["crit"], m["init"])
    assert py_no is True and py_no == lean_no["win"]
    py_g, lean_g = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                        p["crit"], p["max_hp"], p["init"], m["hp"],
                        m["attack"], m["resist"], m["crit"], m["init"],
                        m_greed=20)
    assert py_g is False
    assert py_g == lean_g["win"]


def test_sun_shield_flips_winnable_fight_against_lean():
    """Sun-shield reduces the player's per-turn damage; at 100% it zeroes killStep so the
    monster is unkillable, flipping a win to a loss. Pins the (bubble+sun_shield) merged
    killStep reduction against Lean with bubble held at 0. Monster deals no direct damage
    (raw_monster 0 => die_step<=0 => win) until sun_shield 100% makes killStep 0 => loss."""
    p = dict(attack={"fire": 50}, dmg=0, dmg_elem={}, resist={}, crit=0,
             max_hp=100, init=10)
    m = dict(hp=100, attack={}, resist={}, crit=0, init=10)
    py_no, lean_no = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                          p["crit"], p["max_hp"], p["init"], m["hp"],
                          m["attack"], m["resist"], m["crit"], m["init"])
    assert py_no is True and py_no == lean_no["win"]
    py_s, lean_s = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                        p["crit"], p["max_hp"], p["init"], m["hp"],
                        m["attack"], m["resist"], m["crit"], m["init"],
                        m_sun_shield=100)
    assert py_s is False
    assert py_s == lean_s["win"]


def test_enchanted_mirror_flips_winnable_fight_against_lean():
    """Enchanted-mirror reflects a % of the player's own output back as player damage —
    the only dieStep term scaled by raw_player. The monster deals no direct damage, but
    at 50% reflect the player dies in 2 rounds while the kill takes 4 (monster hp 200),
    flipping a win to a loss. Pins the reflect term against Lean."""
    p = dict(attack={"fire": 50}, dmg=0, dmg_elem={}, resist={}, crit=0,
             max_hp=50, init=10)
    m = dict(hp=200, attack={}, resist={}, crit=0, init=10)
    py_no, lean_no = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                          p["crit"], p["max_hp"], p["init"], m["hp"],
                          m["attack"], m["resist"], m["crit"], m["init"])
    assert py_no is True and py_no == lean_no["win"]
    py_e, lean_e = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                        p["crit"], p["max_hp"], p["init"], m["hp"],
                        m["attack"], m["resist"], m["crit"], m["init"],
                        m_enchanted_mirror=50)
    assert py_e is False
    assert py_e == lean_e["win"]


def test_frenzy_flips_winnable_fight_against_lean():
    """Frenzy's always-active monster-damage boost (same shape as berserker) flips the
    same won tiebreak to a loss. Pins the frenzy term against Lean with berserk at 0."""
    p = dict(attack={"fire": 50}, dmg=0, dmg_elem={}, resist={}, crit=0,
             max_hp=100, init=10)
    m = dict(hp=100, attack={"fire": 50}, resist={}, crit=0, init=10)
    py_no, lean_no = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                          p["crit"], p["max_hp"], p["init"], m["hp"],
                          m["attack"], m["resist"], m["crit"], m["init"])
    assert py_no is True and py_no == lean_no["win"]
    py_f, lean_f = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                        p["crit"], p["max_hp"], p["init"], m["hp"],
                        m["attack"], m["resist"], m["crit"], m["init"],
                        m_frenzy=100)
    assert py_f is False
    assert py_f == lean_f["win"]


def test_protective_bubble_flips_winnable_fight_against_lean():
    """Protective-bubble's always-on player-damage reduction shrinks killStep, raising
    rounds_to_kill past rounds_to_die and flipping a won tiebreak to a loss. Pins the
    killStep bubble term (incl. the `/ 2` floor) against Lean. Player raw 50 vs hp 100;
    bubble 50% => killStep 5e5 - 50*50*200//2=2.5e5 = 2.5e5 => rtk 4 > rtd 2 => loss."""
    p = dict(attack={"fire": 50}, dmg=0, dmg_elem={}, resist={}, crit=0,
             max_hp=100, init=10)
    m = dict(hp=100, attack={"fire": 50}, resist={}, crit=0, init=10)
    py_no, lean_no = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                          p["crit"], p["max_hp"], p["init"], m["hp"],
                          m["attack"], m["resist"], m["crit"], m["init"])
    assert py_no is True and py_no == lean_no["win"]
    py_b, lean_b = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                        p["crit"], p["max_hp"], p["init"], m["hp"],
                        m["attack"], m["resist"], m["crit"], m["init"],
                        m_bubble=50)
    assert py_b is False
    assert py_b == lean_b["win"]


def test_antipoison_cancels_poison_against_lean():
    """Player antipoison CAPS the monster's poison DoT: max(0, poison - antipoison).
    A monster with zero direct damage but poison 100 KILLS via poison (a loss); with
    antipoison 100 equipped the poison is fully cancelled ⇒ dieStep ≤ 0 ⇒ win. Pins the
    cap (composing #1 poison with #3b2 antipoison) against Lean. raw 50 vs hp 100, player
    first, monster deals no direct damage."""
    py_psn, lean_psn = _run({"fire": 50}, 0, {}, {}, 0, 100, 10,
                            100, {}, {}, 0, 10, m_poison=100)
    assert py_psn is False
    assert py_psn == lean_psn["win"]
    # antipoison 100 fully cancels poison 100 ⇒ no DoT ⇒ harmless monster ⇒ win.
    py_anti, lean_anti = _run({"fire": 50}, 0, {}, {}, 0, 100, 10,
                              100, {}, {}, 0, 10, m_poison=100, p_antipoison=100)
    assert py_anti is True
    assert py_anti == lean_anti["win"]


def test_maxturns_loss_binds_against_lean():
    """A monster needing > MAX_TURNS rounds to kill is a loss even though the
    player is unkillable. Pins the MAX_TURNS cap against Lean."""
    # raw 1 vs 100000 hp => rounds_to_kill > 100 => loss; monster can't hit.
    py, lean = _run({"fire": 1}, 0, {}, {}, 0, 1000, 100, 100000,
                    {}, {}, 0, 0)
    assert py is False
    assert py == lean["win"]


def test_poison_flips_winnable_fight_against_lean():
    """A symmetric fight the player WINS on the initiative tiebreak (rtk == rtd,
    player first), but the monster's per-turn poison shortens rtd below rtk and
    flips it to a LOSS. Pins the dieStep poison term against Lean — a mutant that
    drops `+ monsterPoison*10000` would keep the win and die here."""
    # Player raw 50, monster hp 100 => rtk = 2. Monster raw 50, player hp 100,
    # no poison => rtd = 2, player first => win.
    p = dict(attack={"fire": 50}, dmg=0, dmg_elem={}, resist={}, crit=0,
             max_hp=100, init=10)
    m = dict(hp=100, attack={"fire": 50}, resist={}, crit=0, init=10)
    py_no, lean_no = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                          p["crit"], p["max_hp"], p["init"], m["hp"],
                          m["attack"], m["resist"], m["crit"], m["init"])
    assert py_no is True
    assert py_no == lean_no["win"]
    # poison 100/turn => dieStep gains 1e6 => rtd = 1 < rtk = 2 => loss.
    py_p, lean_p = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                        p["crit"], p["max_hp"], p["init"], m["hp"],
                        m["attack"], m["resist"], m["crit"], m["init"],
                        m_poison=100)
    assert py_p is False
    assert py_p == lean_p["win"]


def test_poison_kills_when_monster_deals_no_direct_damage_against_lean():
    """A monster with ZERO direct damage but non-zero poison still kills: the
    old `raw_monster <= 0 => True` shortcut (now removed) would mispredict a win.
    Pins the removal of that guard — poison-only death is a real loss."""
    # Monster attack {} => raw_monster 0. Without poison: dieStep <= 0 => win.
    py_safe, lean_safe = _run({"fire": 50}, 0, {}, {}, 0, 100, 10,
                              100, {}, {}, 0, 10)
    assert py_safe is True
    assert py_safe == lean_safe["win"]
    # With poison 100/turn: dieStep = 1e6 > 0, rtd = 1 < rtk = 2 => loss.
    py_psn, lean_psn = _run({"fire": 50}, 0, {}, {}, 0, 100, 10,
                            100, {}, {}, 0, 10, m_poison=100)
    assert py_psn is False
    assert py_psn == lean_psn["win"]


def test_barrier_flips_winnable_fight_against_lean():
    """A symmetric fight the player WINS on the initiative tiebreak (rtk == rtd == 2,
    player first), but the monster's absorbing barrier raises effective HP so
    rounds_to_kill grows past rounds_to_die and flips it to a LOSS. Pins the
    effective-HP barrier term against Lean — a mutant that drops `+ monster_barrier`
    would keep the win and die here."""
    # Player raw 50 vs hp 100 => rtk 2; monster raw 50, player hp 100 => rtd 2; win.
    p = dict(attack={"fire": 50}, dmg=0, dmg_elem={}, resist={}, crit=0,
             max_hp=100, init=10)
    m = dict(hp=100, attack={"fire": 50}, resist={}, crit=0, init=10)
    py_no, lean_no = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                          p["crit"], p["max_hp"], p["init"], m["hp"],
                          m["attack"], m["resist"], m["crit"], m["init"])
    assert py_no is True
    assert py_no == lean_no["win"]
    # barrier 100 => effective hp 200 => rtk = 8 > rtd = 2 => loss.
    py_b, lean_b = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                        p["crit"], p["max_hp"], p["init"], m["hp"],
                        m["attack"], m["resist"], m["crit"], m["init"],
                        m_barrier=100)
    assert py_b is False
    assert py_b == lean_b["win"]


def test_burn_flips_winnable_fight_against_lean():
    """A symmetric fight the player WINS on the initiative tiebreak (rtk == rtd == 2,
    player first), but the monster's burn (percent-of-attack DoT) raises dieStep so
    rounds_to_die drops below rounds_to_kill and flips it to a LOSS. Pins the burn
    term against Lean — a mutant that drops `+ monster_burn*p_atk_sum*100` keeps the
    win and dies here. Player Σatk 50, burn 100% => +5e5/round => dieStep 1e6 => rtd 1."""
    p = dict(attack={"fire": 50}, dmg=0, dmg_elem={}, resist={}, crit=0,
             max_hp=100, init=10)
    m = dict(hp=100, attack={"fire": 50}, resist={}, crit=0, init=10)
    py_no, lean_no = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                          p["crit"], p["max_hp"], p["init"], m["hp"],
                          m["attack"], m["resist"], m["crit"], m["init"])
    assert py_no is True
    assert py_no == lean_no["win"]
    py_brn, lean_brn = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                            p["crit"], p["max_hp"], p["init"], m["hp"],
                            m["attack"], m["resist"], m["crit"], m["init"],
                            m_burn=100)
    assert py_brn is False
    assert py_brn == lean_brn["win"]


def test_healing_flips_winnable_fight_against_lean():
    """A symmetric fight the player WINS on the initiative tiebreak (rtk == rtd == 2,
    player first), but the monster's per-turn healing regen shrinks killStep so
    rounds_to_kill grows past rounds_to_die and flips it to a LOSS. Pins the killStep
    regen-subtract term against Lean — a mutant that drops it keeps killStep large
    (win) and dies here. Monster hp 100, healing 40% => killStep 5e5 - 4e5 = 1e5 =>
    rtk = 10 > rtd = 2 => loss."""
    p = dict(attack={"fire": 50}, dmg=0, dmg_elem={}, resist={}, crit=0,
             max_hp=100, init=10)
    m = dict(hp=100, attack={"fire": 50}, resist={}, crit=0, init=10)
    py_no, lean_no = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                          p["crit"], p["max_hp"], p["init"], m["hp"],
                          m["attack"], m["resist"], m["crit"], m["init"])
    assert py_no is True
    assert py_no == lean_no["win"]
    py_h, lean_h = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                        p["crit"], p["max_hp"], p["init"], m["hp"],
                        m["attack"], m["resist"], m["crit"], m["init"],
                        m_healing=40)
    assert py_h is False
    assert py_h == lean_h["win"]


def test_reconstitution_caps_kill_turns_against_lean():
    """A comfortably winnable fight (rounds_to_kill 2 << rounds_to_die) becomes a
    LOSS when the monster reconstitutes (full-heals) on a period <= rounds_to_kill:
    it heals before we finish. Pins the reconstitution turn-cap against Lean — a
    mutant that drops the guard keeps the win and dies here. Player raw 50 vs hp 100
    => rtk 2; weak monster => rtd large; reconstitution period 2 => 2 <= 2 => loss."""
    # Player raw 50, hp 1000; monster hp 100, weak attack => rtk 2, rtd 200, win.
    p_attack = {"fire": 50}
    py_no, lean_no = _run(p_attack, 0, {}, {}, 0, 1000, 50,
                          100, {"fire": 5}, {}, 0, 10)
    assert py_no is True
    assert py_no == lean_no["win"]
    # reconstitution period 2 <= rtk 2 => the monster full-heals before we kill it.
    py_r, lean_r = _run(p_attack, 0, {}, {}, 0, 1000, 50,
                        100, {"fire": 5}, {}, 0, 10, m_recon=2)
    assert py_r is False
    assert py_r == lean_r["win"]


def test_void_drain_flips_winnable_fight_against_lean():
    """Void drain hits BOTH sides: a symmetric fight the player WINS (rtk == rtd == 2,
    player first) becomes a LOSS because the drain heals the monster (killStep down ⇒
    rtk up) AND damages the player (dieStep up ⇒ rtd down). Pins both void-drain terms
    against Lean — a mutant dropping either keeps the win and dies here. Player hp 100,
    raw 50 vs hp 100; void 20% => killStep 5e5-2e5=3e5 => rtk 4; dieStep 5e5+2e5=7e5 =>
    rtd 2; 4 > 2 => loss."""
    p = dict(attack={"fire": 50}, dmg=0, dmg_elem={}, resist={}, crit=0,
             max_hp=100, init=10)
    m = dict(hp=100, attack={"fire": 50}, resist={}, crit=0, init=10)
    py_no, lean_no = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                          p["crit"], p["max_hp"], p["init"], m["hp"],
                          m["attack"], m["resist"], m["crit"], m["init"])
    assert py_no is True
    assert py_no == lean_no["win"]
    py_v, lean_v = _run(p["attack"], p["dmg"], p["dmg_elem"], p["resist"],
                        p["crit"], p["max_hp"], p["init"], m["hp"],
                        m["attack"], m["resist"], m["crit"], m["init"],
                        m_void=20)
    assert py_v is False
    assert py_v == lean_v["win"]

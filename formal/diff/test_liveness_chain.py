"""Liveness regression gate for `LivenessChain.chain_emits_fight_when_target_exists_and_applicable`.

The Lean theorem (Formal/LivenessChain.lean) proves the chain
  picker → step dispatch → FightAction applicability
emits SOME FightAction whenever:
  (a) the monster catalog contains a winnable target, and
  (b) the FightAction predicate holds for that target.

This Python harness pins the SAME CHAIN — picker, step dispatch, and
FightAction.is_applicable — against the live runtime. Each component is
exercised in isolation against synthesized inputs; the test asserts the
three-way composition matches the Lean theorem's truth table.

If a future change to `_winnable_farm_target`, `objective_step_goal`, or
`FightAction.is_applicable` reintroduces the 2026-06-06 trace failure
class (a winnable target unreachable for combat in the same state), this
test catches it before deployment.
"""

from __future__ import annotations

import dataclasses

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.strategy_driver import objective_step_goal
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import ReachCharLevel
from artifactsmmo_cli.ai.world_state import WorldState


# ---------- Fixtures ----------------------------------------------------------

def _empty_equipment() -> dict[str, str | None]:
    return {
        "weapon_slot": "wooden_stick", "rune_slot": None, "shield_slot": None,
        "helmet_slot": None, "body_armor_slot": None, "leg_armor_slot": None,
        "boots_slot": None, "ring1_slot": None, "ring2_slot": None,
        "amulet_slot": None, "artifact1_slot": None, "artifact2_slot": None,
        "artifact3_slot": None, "utility1_slot": None, "utility2_slot": None,
        "bag_slot": None,
    }


def _stub_gd(monster: str, monster_level: int) -> GameData:
    gd = GameData()
    gd._item_stats = {
        "wooden_stick": ItemStats(
            code="wooden_stick", level=1, type_="weapon",
            attack={"earth": 10},
        ),
    }
    gd._monster_level = {monster: monster_level}
    gd._monster_attack = {monster: {"earth": 1, "fire": 0, "water": 0, "air": 0}}
    gd._monster_resistance = {monster: {"earth": 0, "fire": 0, "water": 0, "air": 0}}
    gd._monster_hp = {monster: 10}
    gd._monster_locations = {monster: frozenset({(0, 0)})}
    gd._monster_critical_strike = {monster: 0}
    gd._monster_initiative = {monster: 0}
    return gd


def _state(level: int, hp: int, max_hp: int) -> WorldState:
    return WorldState(
        character="c", level=level, xp=0, max_xp=1000,
        hp=hp, max_hp=max_hp, gold=0, skills={},
        x=0, y=0,
        inventory={"wooden_stick": 1}, inventory_max=100,
        equipment=_empty_equipment(),
        cooldown_expires=None,
        task_code=None, task_type=None, task_progress=0, task_total=0,
        bank_items=None, bank_gold=None, pending_items=None,
        attack={"earth": 10}, dmg=0, dmg_elements={}, resistance={},
        critical_strike=0, initiative=0,
    )


# ---------- Lean-mirror chain function ---------------------------------------

def _chain(state: WorldState, gd: GameData, monster: str, level: int) -> bool:
    """Mirrors `LivenessChain.chainEmitsFight` but with the live runtime
    components. Returns True iff the three-step chain
      1. is_winnable_at_max_hp,
      2. objective_step_goal → GrindCharacterXPGoal,
      3. FightAction.is_applicable,
    all succeed.
    """
    # Step 1: G3 picker projection — winnability at max_hp.
    projected = dataclasses.replace(state, hp=state.max_hp)
    if not is_winnable(projected, gd, monster, history=None):
        return False
    # Step 2: G5 step dispatch — ReachCharLevel goes to GrindCharacterXP.
    step = ReachCharLevel(level=level)
    ctx = SelectionContext(
        bank_accessible=False, bank_required_level=10, bank_unlock_monster=None,
        initial_xp=state.xp, task_exchange_min_coins=0,
        combat_monster=monster,
    )
    goal = objective_step_goal(step, state, gd, ctx)
    if not isinstance(goal, GrindCharacterXPGoal):
        return False
    # Step 3: G4 applicability — FightAction(monster).is_applicable.
    fight = FightAction(monster_code=monster, locations=frozenset({(0, 0)}))
    return fight.is_applicable(state, gd)


# ---------- Concrete cases ---------------------------------------------------

class TestLivenessChain:

    def test_winnable_in_window_with_gear_yields_fight_path(self) -> None:
        """G6 hypothesis: target exists + applicable ⇒ chain returns True."""
        gd = _stub_gd("yellow_slime", monster_level=2)
        state = _state(level=2, hp=50, max_hp=50)
        assert _chain(state, gd, "yellow_slime", level=4)

    def test_overleveled_monster_breaks_applicability_gate(self) -> None:
        """G4 fightApplicable_false_of_overleveled_monster — chain returns False."""
        gd = _stub_gd("godzilla", monster_level=99)
        state = _state(level=1, hp=10, max_hp=10)
        assert not _chain(state, gd, "godzilla", level=3)

    def test_below_window_chicken_with_positive_xp_is_fightable(self) -> None:
        """P0 regression (2026-06-09): chicken (lvl 1) vs Robby (lvl 3).
        Under the OLD hard lower window this chain returned False and the
        bot deadlocked when chicken was the only winnable monster. The
        revised lower gate (`xp_per_kill > 0`; Lean theorem
        below_old_window_xp_positive_is_applicable) makes the chain LIVE:
        chicken grants XP at level 3, so the fight is applicable."""
        gd = _stub_gd("chicken", monster_level=1)
        state = _state(level=3, hp=130, max_hp=130)
        assert _chain(state, gd, "chicken", level=5)

    def test_zero_xp_monster_breaks_applicability_gate(self) -> None:
        """The honest lower bound: at level 11 a chicken (lvl 1) grants
        ZERO XP (documented curve zeroes at char-monster >= 10). The Lean
        theorem fightApplicable_false_of_zero_xp pins this — picker may
        say winnable, FightAction.is_applicable says no."""
        gd = _stub_gd("chicken", monster_level=1)
        state = _state(level=11, hp=130, max_hp=130)
        assert gd.xp_per_kill("chicken", 11) == 0
        assert not _chain(state, gd, "chicken", level=13)

    def test_low_hp_breaks_applicability_at_runtime_only(self) -> None:
        """fightApplicable_false_of_low_hp — current-hp filter, not target
        selection. The G3 picker (at max_hp) still flags winnable."""
        gd = _stub_gd("yellow_slime", monster_level=2)
        # hp 30/100 = 30% < 50% floor
        state = _state(level=2, hp=30, max_hp=100)
        # is_winnable at max_hp=100 → True. FightAction.is_applicable at hp=30 → False.
        # Chain returns False because applicability is the final gate.
        assert not _chain(state, gd, "yellow_slime", level=4)


# ---------- Hypothesis property ----------------------------------------------

@settings(max_examples=100, deadline=None)
@given(
    player_level=st.integers(min_value=2, max_value=15),
    monster_level=st.integers(min_value=1, max_value=15),
    hp_pct=st.integers(min_value=1, max_value=100),
)
def test_chain_matches_lean_predicate(
    player_level: int, monster_level: int, hp_pct: int,
) -> None:
    """The Lean theorem's positive direction: when ALL of
      * xp gate holds (xp_per_kill > 0 — the P0-revision lower bound)
      * suicide guard holds (monster_level ≤ lvl+2)
      * best_eq ≥ monster_level - 1 (wooden_stick L1 means monster_level ≤ 2)
      * hp_pct > 50%
      * winnable-at-max-hp
    the Python chain MUST return True.
    """
    max_hp = 100
    hp = (max_hp * hp_pct) // 100
    if hp < 1:
        hp = 1
    monster = "test_monster"
    gd = _stub_gd(monster, monster_level)
    state = _state(player_level, hp, max_hp)

    # Pre-compute Lean predicate truth (post-P0 gates: xp>0 lower bound,
    # level+2 suicide guard — no hard lower window).
    level_ok = (gd.xp_per_kill(monster, player_level) > 0
                and monster_level <= player_level + 2)
    gear_ok = 1 >= monster_level - 1   # wooden_stick.level=1
    hp_ok = hp * 100 > 50 * max_hp

    # Winnability check (also part of the Lean precondition).
    projected = dataclasses.replace(state, hp=max_hp)
    winnable = is_winnable(projected, gd, monster, history=None)

    chain_result = _chain(state, gd, monster, level=player_level + 2)

    if level_ok and gear_ok and hp_ok and winnable:
        assert chain_result, (
            f"Liveness regression: Lean preconditions all hold "
            f"(player_level={player_level}, monster_level={monster_level}, "
            f"hp_pct={hp_pct}, winnable={winnable}), but Python chain returned False"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

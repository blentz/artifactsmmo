"""Brick 6 — the perceive/arm differential for `perceptionRefresh`.

Binds the Lean liveness model `Formal.Liveness.PerceptionRefresh.perceptionRefresh`
to production's REAL objective-tier arming of `objectiveStepFires` /
`objectiveStepIsFight`. This is the perceive-side companion to the O5.4 SELECT
differential (`test_ladder_fires_diff.py`): O5.4 bound the LADDER (how a selection
is made from the armed Bools); this brick binds WHERE the objective Bools come
from below the level cap.

## What `perceptionRefresh` claims, and what this validates

The Lean model arms BOTH objective Bools UNCONDITIONALLY when `level < 50`:

    perceptionRefresh s :=
      if s.level < 50 then
        { s with objectiveStepFires := true, objectiveStepIsFight := true }
      else s

Production arms them only when the committed `ReachCharLevel` objective actually
yields a plannable Fight-led step — which, per
`GearTierLeveling.combatObjective_live_below_fifty`, requires a winnable
XP-positive monster in the band. So the FAITHFUL statement this file makes
precise is:

    below level 50, production arms (objectiveStepFires ∧ objectiveStepIsFight)
    IFF a winnable XP-positive target exists; the gap (no winnable ⇒ production
    False but Lean True) is EXACTLY the `WinnableAcrossBand` residual.

This makes `combatObjective_live_below_fifty` a differentially-checked fact, not
a bare Lean hypothesis.

## The REAL production arming path (no re-implementation, no mocks)

Tracing the live `decide` path (player.py:300 → `_selection_context` →
`_winnable_farm_target` → `_pick_winnable_monster`; strategy_driver.py:578
`objective_step_goal` for a `ReachCharLevel` step):

  1. `combat.is_winnable(state, game_data, code, history)` — the single combat
     beatability verdict (predict_win gated by the learned-loss veto).
  2. `combat_picker.pick_winnable_monster_pure(char_level, monsters, is_winnable,
     xp_positive)` — the window-preferred-with-XP-fallback target picker. This is
     the EXACT callable `Player._pick_winnable_monster` invokes (player.py:1126);
     production's `_winnable_farm_target` returns its result when no task is held
     and no path monster is aligned (the `pick_winnable` cascade branch).
  3. `strategy_driver.objective_step_goal(ReachCharLevel(target), state,
     game_data, ctx)` — maps the committed char-level step to a Goal. For a
     `ReachCharLevel` step it returns `GrindCharacterXPGoal(combat_monster)`
     IFF `ctx.combat_monster is not None`, else `None` (strategy_driver.py:578-611).

So the production arming verdict for a constructed (WorldState, GameData) at
`level < 50` is:

  * `objective_step_fires`  ≡ `objective_step_goal(...) is not None`
  * `objective_step_is_fight` ≡ that goal is a `GrindCharacterXPGoal` whose
    `relevant_actions` lead with a `FightAction` on the picked target.

Every step above calls REAL production code on a hand-built fixture. The only
composition this file performs is the `_winnable_farm_target` no-task cascade
branch (task_monster=None, path_monster=None ⇒ `pick_winnable_monster_pure`),
reconstructed by calling the SAME production functions the Player calls — never
re-deriving the predicate.

## Why this asserts production's verdict (not the oracle)

`perceptionRefresh`'s Lean behaviour is trivially known and closed-form: it arms
`true` for `level < 50`, identity otherwise (PerceptionRefresh.lean:51-52,
`perceptionRefresh_objectiveStepFires` / `_id_of_ge`). There is no per-input
computation to contest — so the honest differential asserts PRODUCTION's verdict
and states the Lean correspondence inline, rather than round-tripping a constant
through the oracle. Each test documents which `perceptionRefresh` fact it mirrors
or (for the gap) diverges from.
"""
from __future__ import annotations

import dataclasses

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.combat_picker import pick_winnable_monster_pure
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.strategy_driver import objective_step_goal
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import ReachCharLevel
from artifactsmmo_cli.ai.world_state import WorldState

LEVEL_CAP = 50


# ---------------------------------------------------------------------------
# Fixtures — a winnable monster catalog (modelled on tests/test_ai/
# test_combat.py::_gd for monster stats) + a level-L<50 WorldState.
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Monster:
    code: str
    level: int
    hp: int
    attack: dict[str, int]


def _make_game_data(monsters: list[Monster]) -> GameData:
    """A real `GameData` carrying ONLY the monster fields `predict_win` /
    `is_winnable` / `xp_per_kill` / `pick_winnable_monster_pure` read — the same
    fields `tests/test_ai/test_combat.py::_gd` sets, plus level/type for the
    picker window and the XP curve. Empty effect maps = no exotic abilities."""
    gd = GameData()
    gd._monster_level = {m.code: m.level for m in monsters}
    gd._monster_hp = {m.code: m.hp for m in monsters}
    gd._monster_attack = {m.code: dict(m.attack) for m in monsters}
    gd._monster_resistance = {m.code: {} for m in monsters}
    gd._monster_critical_strike = {m.code: 0 for m in monsters}
    gd._monster_initiative = {m.code: 0 for m in monsters}
    gd._monster_lifesteal = {m.code: 0 for m in monsters}
    gd._monster_poison = {m.code: 0 for m in monsters}
    gd._monster_barrier = {m.code: 0 for m in monsters}
    gd._monster_burn = {m.code: 0 for m in monsters}
    gd._monster_healing = {m.code: 0 for m in monsters}
    gd._monster_reconstitution = {m.code: 0 for m in monsters}
    gd._monster_void_drain = {m.code: 0 for m in monsters}
    gd._monster_berserker_rage = {m.code: 0 for m in monsters}
    gd._monster_frenzy = {m.code: 0 for m in monsters}
    gd._monster_protective_bubble = {m.code: 0 for m in monsters}
    gd._monster_corrupted = {m.code: 0 for m in monsters}
    gd._monster_type = {m.code: "normal" for m in monsters}
    return gd


def _make_world(level: int) -> WorldState:
    """A level-`level` combat-capable character (non-empty `attack` so the
    documented `predict_win` formula yields a positive kill step), no task held
    (so the `_winnable_farm_target` cascade reaches the `pick_winnable` branch),
    full HP. `is_winnable` projects to max_hp internally for target selection."""
    return WorldState(
        character="diff", level=level, xp=0, max_xp=999999,
        hp=120, max_hp=120, gold=0, skills={}, x=0, y=0,
        inventory={}, inventory_max=40, inventory_slots_max=40,
        attack={"fire": 50}, resistance={}, critical_strike=0, initiative=10,
        equipment={}, cooldown_expires=None,
        bank_items=None, bank_gold=None, pending_items=None,
        task_code=None, task_type=None, task_progress=0, task_total=0,
    )


def _make_ctx(combat_monster: str | None) -> SelectionContext:
    return SelectionContext(
        bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=5,
        combat_monster=combat_monster,
        target_gear=frozenset(), target_tools=frozenset(),
        gear_review_active=False,
    )


# ---------------------------------------------------------------------------
# Production arming verdict — the REAL chain, end to end.
# ---------------------------------------------------------------------------


def _production_combat_monster(
    state: WorldState, gd: GameData, history: LearningStore | None,
) -> str | None:
    """Production's no-task `_winnable_farm_target` cascade branch: pick the
    window-preferred winnable XP-positive target via the SAME production
    callables `Player._pick_winnable_monster` invokes (player.py:1126-1131).

    This is the `task_monster=None, path_monster=None` cascade case
    (`winnable_cascade.winnable_farm_target_pure` would forward exactly this
    `pick_winnable`). We call the real picker + the real `is_winnable` + the real
    `xp_per_kill` over the live catalog — no re-implementation of beatability."""
    char_level = state.level
    return pick_winnable_monster_pure(
        char_level,
        list(gd.monster_levels.items()),
        lambda code: is_winnable(state, gd, code, history),
        lambda code: gd.xp_per_kill(code, char_level) > 0,
    )


def _production_arms(
    state: WorldState, gd: GameData, target_level: int,
    history: LearningStore | None = None,
) -> tuple[bool, bool, str | None]:
    """Return production's `(objective_step_fires, objective_step_is_fight,
    picked_monster)` for the committed `ReachCharLevel(target_level)` objective.

    Drives the REAL chain: winnable-target pick → `SelectionContext` →
    `objective_step_goal`. `objective_step_fires` is "the objective step maps to a
    non-None Goal"; `objective_step_is_fight` is "that Goal is the
    `GrindCharacterXPGoal` whose plan head is a `FightAction` on the target"."""
    combat_monster = _production_combat_monster(state, gd, history)
    ctx = _make_ctx(combat_monster)
    goal = objective_step_goal(ReachCharLevel(target_level), state, gd, ctx)
    objective_step_fires = goal is not None
    objective_step_is_fight = False
    if isinstance(goal, GrindCharacterXPGoal) and combat_monster is not None:
        # The plan head: GrindCharacterXPGoal.relevant_actions keeps ONLY the
        # FightAction on the target (+ recovery/equip). A non-empty Fight result
        # proves the objective step LEADS WITH a Fight on the picked monster.
        fights = goal.relevant_actions(
            [FightAction(monster_code=combat_monster)], state, gd)
        objective_step_is_fight = any(
            isinstance(a, FightAction) and a.monster_code == combat_monster
            for a in fights)
    return objective_step_fires, objective_step_is_fight, combat_monster


# A winnable XP-positive in-band monster for a level-`level` character: level in
# the picker window [level-1, level+2], low HP + weak single-element attack so
# the documented `predict_win` formula clears (player attack 50 fire vs 12 hp).
def _winnable_in_band(level: int) -> Monster:
    return Monster(code="chicken", level=level, hp=12, attack={"fire": 1})


# An over-leveled monster: level >> char_level (outside the picker window AND
# strong enough that `predict_win` says unwinnable) so NO winnable target exists.
def _over_leveled(level: int) -> Monster:
    return Monster(code="dragon", level=level + 20, hp=5000, attack={"fire": 500})


# ===========================================================================
# Case 1 — FAITHFUL: level < 50 AND a winnable in-band monster ⇒ production
# arms (True, True), MATCHING Lean `perceptionRefresh` (which arms below 50).
# ===========================================================================


def test_faithful_winnable_below_cap_arms_both() -> None:
    """`level < 50` + a winnable XP-positive in-band monster ⇒ production REALLY
    arms `objectiveStepFires = True` AND `objectiveStepIsFight = True`.

    Lean correspondence: `perceptionRefresh` at this `level < 50` sets both Bools
    `true` (PerceptionRefresh.lean `perceptionRefresh_objectiveStepFires` /
    `_objectiveStepIsFight`). Production AGREES — the faithful case. The
    assertions below are NON-trivial: the goal is the real `GrindCharacterXPGoal`
    and its head action is a real `FightAction` on the picked target."""
    for level in (1, 10, 25, 40, 49):
        gd = _make_game_data([_winnable_in_band(level)])
        state = _make_world(level)
        fires, is_fight, mon = _production_arms(state, gd, LEVEL_CAP)
        assert mon == "chicken", (level, mon)
        # Production REALLY arms (not a trivially-true assertion): a winnable
        # target was picked, a GrindCharacterXPGoal was committed, and its plan
        # leads with a Fight.
        assert fires is True, (
            f"level={level}: production did NOT arm objectiveStepFires "
            f"despite a winnable target {mon}")
        assert is_fight is True, (
            f"level={level}: objective step is not Fight-led (monster={mon})")
        # Lean perceptionRefresh arms (True, True) here too — faithful match.


def test_faithful_arms_goal_is_real_fight_led_grind() -> None:
    """Pin the arming's TEETH: the committed objective goal is concretely the
    `GrindCharacterXPGoal` on the picked monster and nothing else — so
    `objectiveStepIsFight` is a genuine Fight-led-plan verdict, not a label."""
    level = 10
    gd = _make_game_data([_winnable_in_band(level)])
    state = _make_world(level)
    mon = _production_combat_monster(state, gd, None)
    assert mon == "chicken"
    goal = objective_step_goal(ReachCharLevel(LEVEL_CAP), state, gd, _make_ctx(mon))
    assert isinstance(goal, GrindCharacterXPGoal)
    fights = goal.relevant_actions([FightAction(monster_code=mon)], state, gd)
    assert fights == [FightAction(monster_code=mon)]


def test_faithful_with_real_learning_store_history() -> None:
    """Same faithful arming, but with a REAL `LearningStore` threaded through
    `is_winnable` (the learned-loss veto path) — no history records, so the veto
    defers to `predict_win` and the target is still picked. Exercises the
    runtime arming path (history-aware) end to end, not just the cold path."""
    level = 12
    gd = _make_game_data([_winnable_in_band(level)])
    state = _make_world(level)
    store = LearningStore(db_path=":memory:", character="diff")
    fires, is_fight, mon = _production_arms(state, gd, LEVEL_CAP, history=store)
    assert mon == "chicken"
    assert fires is True
    assert is_fight is True


# ===========================================================================
# Case 2 — the WinnableAcrossBand GAP (surfaced honestly, NOT hidden): level
# < 50 but NO winnable target ⇒ production arms `objectiveStepFires = False`,
# while Lean `perceptionRefresh` would arm `True`. This divergence IS exactly
# `WinnableAcrossBand`. perceptionRefresh is faithful MODULO this residual.
# ===========================================================================


def test_winnable_across_band_gap_empty_catalog() -> None:
    """`level < 50` but an EMPTY monster catalog ⇒ no winnable target ⇒
    production does NOT arm (`objectiveStepFires = False`, no Fight-led step).

    Lean `perceptionRefresh` WOULD arm `(True, True)` at this `level < 50`. The
    divergence (Lean True, production False) is EXACTLY the `WinnableAcrossBand`
    residual: perceptionRefresh's `level < 50` arming is faithful to production
    ONLY when a winnable XP-positive monster exists in the band. This test
    SURFACES that modelling assumption — it is NOT a pass/fail of the Lean model;
    it is the precise characterization of `combatObjective_live_below_fifty`'s
    hypothesis. WinnableAcrossBand is a satisfiable gear-tier residual, reducible
    by binding to the live monster catalog (roadmap #4)."""
    level = 10
    gd = _make_game_data([])  # no monsters at all
    state = _make_world(level)
    fires, is_fight, mon = _production_arms(state, gd, LEVEL_CAP)
    assert mon is None
    # Production does NOT arm — the Fight step is not plannable.
    assert fires is False
    assert is_fight is False
    # Lean perceptionRefresh would arm True here ⇒ this is the WinnableAcrossBand
    # gap. Documented, not hidden: the two sides DIVERGE exactly when no winnable
    # target exists below the cap.


def test_winnable_across_band_gap_over_leveled_catalog() -> None:
    """`level < 50` with ONLY an over-leveled (out-of-band, unwinnable) monster
    ⇒ no winnable XP target ⇒ production does NOT arm. Same WinnableAcrossBand
    gap as the empty-catalog case, but with a non-empty catalog: the residual is
    about WINNABILITY-in-band, not mere catalog emptiness."""
    level = 10
    gd = _make_game_data([_over_leveled(level)])
    state = _make_world(level)
    fires, is_fight, mon = _production_arms(state, gd, LEVEL_CAP)
    assert mon is None
    assert fires is False
    assert is_fight is False


def test_arming_binds_iff_winnable() -> None:
    """The KEY deliverable, stated directly: below the cap, production arms IFF a
    winnable target exists. Drive both polarities on the SAME level with the SAME
    machinery and assert the arming verdict tracks winnability exactly — this is
    the `combatObjective_live_below_fifty` ↔ production binding."""
    level = 15
    winnable_gd = _make_game_data([_winnable_in_band(level)])
    barren_gd = _make_game_data([_over_leveled(level)])
    state = _make_world(level)

    fires_w, is_fight_w, mon_w = _production_arms(state, winnable_gd, LEVEL_CAP)
    fires_b, is_fight_b, mon_b = _production_arms(state, barren_gd, LEVEL_CAP)

    # Winnable exists ⇒ armed; none winnable ⇒ not armed. The arming verdict is
    # exactly `a winnable target exists` — the WinnableAcrossBand binding.
    assert (mon_w is not None) and (fires_w, is_fight_w) == (True, True)
    assert (mon_b is None) and (fires_b, is_fight_b) == (False, False)


# ===========================================================================
# Case 3 — AT/ABOVE the cap (level >= 50): Lean `perceptionRefresh` is the
# identity (no arming); production's `ReachCharLevel(50)` is satisfied, so no
# char-leveling Fight objective is committed. Confirm the cap boundary matches.
# ===========================================================================


def test_cap_boundary_objective_satisfied_at_and_above_fifty() -> None:
    """At/above the cap the char-leveling objective `ReachCharLevel(50)` is
    SATISFIED (`is_satisfied = True`), so the objective tier commits no
    char-leveling Fight step — even with a winnable monster present.

    Lean correspondence: `perceptionRefresh` is the IDENTITY for `¬ level < 50`
    (`perceptionRefresh_id_of_ge`): it arms nothing above the cap. Production
    matches — the satisfied root means no combat objective. We assert the
    objective-satisfaction gate (the real production gate that withholds the
    step), since that is what suppresses the Fight commit at the cap."""
    gd_template = _make_game_data([_winnable_in_band(50)])
    for level in (50, 55, 60):
        state = _make_world(level)
        # The char-leveling root is satisfied at/above the cap ⇒ the objective
        # tier does not offer a ReachCharLevel(50) step ⇒ no Fight commit.
        assert ReachCharLevel(LEVEL_CAP).is_satisfied(state, gd_template) is True
    # Just below the cap the SAME root is NOT satisfied (the step is live) —
    # pinning the boundary at exactly 50.
    assert ReachCharLevel(LEVEL_CAP).is_satisfied(_make_world(49), gd_template) is False


def test_cap_boundary_below_fifty_root_unsatisfied_and_armed() -> None:
    """Mirror of the boundary from below: at `level = 49` the `ReachCharLevel(50)`
    root is UNsatisfied AND (with a winnable target) production arms the Fight-led
    step — matching `perceptionRefresh` arming for `level < 50`. Together with the
    test above this pins the cap transition: armed below 50, identity at >= 50."""
    level = 49
    gd = _make_game_data([_winnable_in_band(level)])
    state = _make_world(level)
    assert ReachCharLevel(LEVEL_CAP).is_satisfied(state, gd) is False
    fires, is_fight, mon = _production_arms(state, gd, LEVEL_CAP)
    assert mon is not None
    assert (fires, is_fight) == (True, True)

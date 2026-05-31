"""Phase-20b differential: no-deadlock invariant against production goals.

Bridges the Lean headline `Formal.Liveness.NoDeadlock.no_deadlock_strong`
(`∀ s, ∃ g, goalValueOf g s > 0`) to the production Python goals in
`src/artifactsmmo_cli/ai/goals/`. For every Hypothesis-generated state
plus a FakeServer evolution trace, asserts:

    max(g.value(state, gd) for g in CANDIDATE_PRODUCTION_GOALS) > 0

where the candidate set is the eight Phase-18 goals named in the
Phase-20b `FiringGoal` dispatch. Calls REAL production `Goal.value()` —
no mocks of the unit under test (per CLAUDE.md "No defer / no
monkeypatch").

Mutation kills (see `formal/diff/mutate.py`):
  1. `formal/sim/firing_goal.py`     — drop `criticalHP` branch.
  2. `formal/sim/firing_goal.py`     — swap dispatch order
                                       (`progressNeeded` before `criticalHP`).
  3. `src/.../goals/restore_hp.py`   — invert critical-HP boundary (< -> >).
  4. `src/.../goals/discard_overstock.py` — value() unconditionally 0.

Test structure
--------------
Two sub-tests:

  * `test_no_deadlock_holds_for_hypothesis_states` — strategy-driven sweep
    across all 8 regions. Each draw is bounded to the modelable range
    documented in `Formal.Liveness.StateRegions.regionOf` (no negative
    fields, no `taskProgress > taskTotal` contradictions, hp ≤ max_hp).

  * `test_no_deadlock_holds_during_fake_server_cycles` — chained
    FakeServer Fight/Gather/Deposit/Rest cycles (mirror of the Tier-1
    `test_local_progress_diff` cycle loop) with the no-deadlock
    invariant checked at every step.

Honest constraints
------------------
* Hypothesis bounds are stated explicitly (see `_state_strategy`).
* Production goals are called against real production state — the goal
  constructors live in `src/artifactsmmo_cli/ai/goals/` and are
  unmocked.
* `firing_goal.region_of` is the SAME Python dispatch as the Lean
  `regionOf`; if it drifts, the mutation gate kills it (mutation #1/#2).
"""

import dataclasses

from hypothesis import HealthCheck, given, settings, strategies as st

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.world_state import WorldState

from formal.sim.fake_server import FakeServer
from formal.sim.firing_goal import (
    FiringGoal,
    LivenessInputs,
    production_goal_for,
    region_of,
)
from tests.test_ai.fixtures import make_state


# --- Game-data fixture ---------------------------------------------------

# Used both for the Hypothesis sweep and the FakeServer trace. Caps are
# tight so `overstocked_items` can detect an over-cap stack in
# inventoryFull states; recipes are empty so PursueTask's recipe_closure
# is well-defined when task_code is present.
def _make_gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        "ash_wood": ItemStats(code="ash_wood", level=1, type_="resource"),
        "junk_item": ItemStats(code="junk_item", level=1, type_="resource"),
        "chicken_feather": ItemStats(code="chicken_feather", level=1,
                                     type_="resource"),
    }
    gd._crafting_recipes = {}
    gd._resource_drops = {"copper_rocks": "copper_ore",
                          "ash_tree": "ash_wood"}
    gd._resource_skill = {"copper_rocks": ("mining", 1),
                          "ash_tree": ("woodcutting", 1)}
    gd._resource_locations = {"copper_rocks": [(2, 0)],
                              "ash_tree": [(3, 0)]}
    gd._workshop_locations = {}
    gd._monster_locations = {"chicken": [(0, 1)]}
    gd._monster_level = {"chicken": 1}
    gd._bank_location = (4, 0)
    gd._next_expansion_cost = 1000
    return gd


GD = _make_gd()


# --- Per-region state constructors --------------------------------------

# Each constructor returns (WorldState, LivenessInputs) such that
# `region_of` returns the matching FiringGoal AND the production goal's
# value() returns > 0. Builds inside the bounds documented in
# StateRegions.lean.

def _state_critical_hp(hp: int, max_hp: int) -> tuple[WorldState, LivenessInputs]:
    # critical_hp: max_hp > 0 ∧ 4*hp < max_hp.
    s = make_state(hp=hp, max_hp=max_hp, task_code="chicken_task",
                   task_type="monsters", task_progress=0, task_total=5)
    liv = LivenessInputs(pending_items=False, bank_locked=False,
                         bank_xp_exceeded=False, bank_unreachable=False,
                         unlock_target_level=0)
    return s, liv


def _state_pending_items() -> tuple[WorldState, LivenessInputs]:
    s = make_state(hp=100, max_hp=100,
                   pending_items=(("1", "copper_ore"),),
                   task_code="task", task_type="monsters",
                   task_progress=0, task_total=5)
    liv = LivenessInputs(pending_items=True, bank_locked=False,
                         bank_xp_exceeded=False, bank_unreachable=False,
                         unlock_target_level=0)
    return s, liv


def _state_task_complete() -> tuple[WorldState, LivenessInputs]:
    s = make_state(hp=100, max_hp=100,
                   task_code="task", task_type="monsters",
                   task_progress=5, task_total=5)
    liv = LivenessInputs(pending_items=False, bank_locked=False,
                         bank_xp_exceeded=False, bank_unreachable=False,
                         unlock_target_level=0)
    return s, liv


def _state_no_task() -> tuple[WorldState, LivenessInputs]:
    s = make_state(hp=100, max_hp=100, task_code=None, task_type=None,
                   task_progress=0, task_total=0)
    liv = LivenessInputs(pending_items=False, bank_locked=False,
                         bank_xp_exceeded=False, bank_unreachable=False,
                         unlock_target_level=0)
    return s, liv


def _state_inventory_full() -> tuple[WorldState, LivenessInputs]:
    # Need: inventory_used >= inventory_max AND at least one stack > useful cap.
    # `junk_item` has no recipe/task use so its cap is 0 — every unit is overstock.
    s = make_state(hp=100, max_hp=100,
                   inventory={"junk_item": 20},
                   inventory_max=20,
                   task_code="task", task_type="monsters",
                   task_progress=0, task_total=5)
    liv = LivenessInputs(pending_items=False, bank_locked=False,
                         bank_xp_exceeded=False, bank_unreachable=False,
                         unlock_target_level=0)
    return s, liv


def _state_level_blocker(level: int, target: int) -> tuple[WorldState, LivenessInputs]:
    # level_blocker: target > 0 ∧ level < target ∧ target - level ≤ 5.
    s = make_state(level=level, hp=100, max_hp=100,
                   task_code="task", task_type="monsters",
                   task_progress=0, task_total=5)
    liv = LivenessInputs(pending_items=False, bank_locked=False,
                         bank_xp_exceeded=False, bank_unreachable=False,
                         unlock_target_level=target)
    return s, liv


def _state_bank_locked_fightable() -> tuple[WorldState, LivenessInputs]:
    # bank locked ∧ ¬xpExceeded ∧ ¬unreachable.
    # initial_xp in production goal is state.xp, so `xp > initial_xp` is False
    # at construction time (the goal is not yet satisfied).
    s = make_state(hp=100, max_hp=100, xp=0,
                   task_code="task", task_type="monsters",
                   task_progress=0, task_total=5)
    liv = LivenessInputs(pending_items=False, bank_locked=True,
                         bank_xp_exceeded=False, bank_unreachable=False,
                         unlock_target_level=0)
    return s, liv


def _state_progress_needed() -> tuple[WorldState, LivenessInputs]:
    # Residual: no other region matches. Task accepted and in progress.
    s = make_state(hp=100, max_hp=100,
                   task_code="task", task_type="monsters",
                   task_progress=2, task_total=10,
                   inventory={}, inventory_max=20)
    liv = LivenessInputs(pending_items=False, bank_locked=False,
                         bank_xp_exceeded=False, bank_unreachable=False,
                         unlock_target_level=0)
    return s, liv


# --- Hypothesis strategies ----------------------------------------------

# Modelable bounds (per `Formal.Liveness.StateRegions.regionOf`):
#  * hp, max_hp: 1..1000 (no zero max — avoids hpPercent undefined branch).
#    For critical_hp we sample (hp, max_hp) with 4*hp < max_hp.
#  * level, target: 1..50 (production cap).
#  * task_progress ≤ task_total (no contradictions).
@st.composite
def _critical_hp_states(draw) -> tuple[WorldState, LivenessInputs]:
    max_hp = draw(st.integers(min_value=4, max_value=1000))
    # 4*hp < max_hp → hp ≤ (max_hp - 1) // 4
    hp = draw(st.integers(min_value=0, max_value=(max_hp - 1) // 4))
    return _state_critical_hp(hp, max_hp)


@st.composite
def _level_blocker_states(draw) -> tuple[WorldState, LivenessInputs]:
    level = draw(st.integers(min_value=1, max_value=49))
    gap = draw(st.integers(min_value=1, max_value=5))
    target = level + gap
    return _state_level_blocker(level, target)


def _region_strategy() -> st.SearchStrategy:
    """One draw per region — round-robin across all 8 firing goals."""
    return st.one_of(
        _critical_hp_states(),
        st.just(_state_pending_items()),
        st.just(_state_task_complete()),
        st.just(_state_no_task()),
        st.just(_state_inventory_full()),
        _level_blocker_states(),
        st.just(_state_bank_locked_fightable()),
        st.just(_state_progress_needed()),
    )


# --- Invariant -----------------------------------------------------------

def _assert_no_deadlock(state: WorldState, liv: LivenessInputs) -> None:
    """Look up the production goal for `region_of(state)` and assert its
    value() is strictly positive. This is the Python image of the Lean
    `no_deadlock_strong` headline.
    """
    firing = region_of(state, liv)
    goal = production_goal_for(firing, state, liv, GD)
    value = goal.value(state, GD, None)
    assert value > 0, (
        f"NO-DEADLOCK VIOLATION: region={firing.name}, goal={goal!r}, "
        f"value={value}, state.hp={state.hp}/{state.max_hp}, "
        f"task_code={state.task_code}, task_total={state.task_total}, "
        f"task_progress={state.task_progress}, "
        f"inv_used={state.inventory_used}/{state.inventory_max}, "
        f"liv=(pending={liv.pending_items}, bank_locked={liv.bank_locked}, "
        f"xp_exc={liv.bank_xp_exceeded}, unreach={liv.bank_unreachable}, "
        f"unlock_target={liv.unlock_target_level})"
    )


# --- Sub-test 1: Hypothesis sweep ---------------------------------------

@given(_region_strategy())
@settings(max_examples=200, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_no_deadlock_holds_for_hypothesis_states(
    bundle: tuple[WorldState, LivenessInputs],
) -> None:
    """Sweep all 8 firing-goal regions with Hypothesis. For every drawn
    state, the production goal corresponding to `region_of(state)` must
    return value > 0.
    """
    state, liv = bundle
    _assert_no_deadlock(state, liv)


# --- Sub-test 2: FakeServer cycle trace ---------------------------------

# Mirrors the cycle loop in `test_local_progress_diff` but checks the
# no-deadlock invariant instead of measure decrease.

_SKILL_NAME = "mining"
_SLOTS = [
    "weapon_slot", "rune_slot", "shield_slot", "helmet_slot",
    "body_armor_slot", "leg_armor_slot", "boots_slot",
    "ring1_slot", "ring2_slot", "amulet_slot",
    "artifact1_slot", "artifact2_slot", "artifact3_slot",
    "utility1_slot", "utility2_slot", "bag_slot",
]


def _initial_cycle_state() -> WorldState:
    eq: dict[str, str | None] = {s: None for s in _SLOTS}
    eq["weapon_slot"] = "copper_dagger"
    return WorldState(
        character="probe", level=2, xp=0, max_xp=200,
        hp=40, max_hp=100, gold=0,
        skills={"mining": 2, "woodcutting": 1, "fishing": 1,
                "weaponcrafting": 1, "gearcrafting": 1,
                "jewelrycrafting": 1, "cooking": 1, "alchemy": 1},
        x=0, y=0,
        inventory={"copper_ore": 14, "ash_wood": 4},
        inventory_max=20,
        equipment=eq,
        cooldown_expires=None,
        task_code="chicken", task_type="monsters",
        task_progress=0, task_total=10,
        bank_items={}, bank_gold=0,
        pending_items=None,
        attack={"fire": 0},
        dmg=0, dmg_elements={}, resistance={},
        critical_strike=0, initiative=0, wisdom=0,
        skill_xp={"mining": 0},
        projected_skill_xp_delta={_SKILL_NAME: 0},
    )


def _liv_for_cycle(state: WorldState) -> LivenessInputs:
    """Derive LivenessInputs for the trace state. Bank stays unlocked
    throughout the trace (we never simulate the unlock-event); no
    unlock-blocker target; pending_items reflects state.pending_items.
    """
    return LivenessInputs(
        pending_items=bool(state.pending_items),
        bank_locked=False,
        bank_xp_exceeded=False,
        bank_unreachable=False,
        unlock_target_level=0,
    )


def _pick_action(state: WorldState, gd: GameData, cycle: int):
    fight = FightAction(monster_code="chicken",
                        locations=frozenset({(0, 1)}))
    gather = GatherAction(resource_code="copper_rocks",
                          locations=frozenset({(2, 0)}))
    deposit = DepositAllAction(bank_location=(4, 0), accessible=True,
                               game_data=gd)
    rest = RestAction()
    schedule = [rest, gather, fight, deposit]
    primary = schedule[cycle % 4]
    if primary.is_applicable(state, gd):
        return primary
    for candidate in schedule:
        if candidate.is_applicable(state, gd):
            return candidate
    return None


CYCLES = 200


def test_no_deadlock_holds_during_fake_server_cycles() -> None:
    """Run CYCLES rounds of round-robin Fight/Gather/Deposit/Rest against
    FakeServer-as-projection. After every cycle, the no-deadlock
    invariant must hold against the production goals.
    """
    gd = _make_gd()
    state = _initial_cycle_state()
    for cycle in range(CYCLES):
        # Invariant before action.
        _assert_no_deadlock(state, _liv_for_cycle(state))
        action = _pick_action(state, gd, cycle)
        if action is None:
            continue
        # Apply via FakeServer (operational definition of the Lean axiom).
        server = FakeServer(state)
        if isinstance(action, FightAction):
            matches = (state.task_type == "monsters"
                       and state.task_code == action.monster_code)
            state = server.fight(monster_code=action.monster_code,
                                 monster_matches_task=matches)
        elif isinstance(action, GatherAction):
            drop = gd.resource_drop_item(action.resource_code) or action.resource_code
            skill_req = gd.resource_skill_level(action.resource_code)
            skill_name = skill_req[0] if skill_req is not None else None
            state = server.gather(drop_item=drop, skill_name=skill_name)
        elif isinstance(action, DepositAllAction):
            items = action._deposits(state)
            state = server.deposit(items=items)
        elif isinstance(action, RestAction):
            state = server.rest()
        # Pin task_progress within bounds (FakeServer can advance past total
        # if cycles continue; clamp so is_task_complete stays well-defined).
        if state.task_total > 0 and state.task_progress > state.task_total:
            state = dataclasses.replace(state, task_progress=state.task_total)
    # Final invariant check.
    _assert_no_deadlock(state, _liv_for_cycle(state))

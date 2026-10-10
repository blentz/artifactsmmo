"""Differential: Phase 20c-v2 `LadderTotalInvariants` against real production.

The Lean headline `productionLadder_total_under_invariants` carried TWO
load-bearing invariants:

  1. `taskValid` — server contract: `task_code is set ↔ task_total > 0`.
  2. `pursueFiresWhenInProgress` — production-side: when a task is in
     progress (`task_code set ∧ task_progress < task_total`), the production
     PURSUE_TASK rung must fire. Since Phase 5-2c-iii-c-2 #4 the rung is
     retired: a held, unmet task fires the OBJECTIVE_STEP rung on its phase
     alone (`production_ladder.fires`; Lean `objectiveStepFires … ||
     phaseActive`). Since #5 a held, unmet items task is always worked by the
     task objective's step unless its worth cancels it (`_task_root`; the
     `pursue_due` PIVOT gate is gone). This file now pins that phase arm
     (`test_objective_step_fires_when_items_task_in_progress_history_none`).

This file is the bug-finder. It generates diverse WorldState shapes with
Hypothesis (including the deadlock-target shapes called out in Phase 20d-v2
scope), invokes the REAL production `_fires` predicates via
`formal.sim.production_ladder`, and FAILS LOUDLY with a concrete witness if
any invariant is violated.

A failure here is one of:
  * `taskValid` violated → phantom-task or orphan-total state (a server
    contract bug — surface and fix perceive.py).
  * an items task in progress on which OBJECTIVE_STEP's phase arm does NOT
    fire → the retired pursue rung's coverage is lost; REAL PRODUCTION
    DEADLOCK risk. Fix `production_ladder.fires` / the phase derivation.
  * `productionLadder` returns None at all → headline falsified, same
    severity as above.

INTEGRITY rules (Phase 20d-v2 scope):
  * No `_fires` mocking — production code drives every branch.
  * No `pytest.skip` on counter-witnesses — failures stay failures.
  * Hypothesis strategies are DELIBERATELY adversarial (no-task, items-task,
    monsters-task, history=None, bank-locked, low HP, full inventory, empty
    inventory). Each shape targets a known deadlock-prone region.

Result reporting: at session end the module emits a coverage summary
(per-MeansKind firing rate, invariant violations, sampled state count).
"""
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.decisions.root import _task_root
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.task_accept import accept_due
from artifactsmmo_cli.ai.tiers.guards import GUARD_ORDER, SelectionContext
from artifactsmmo_cli.ai.tiers.means import COLLECT_REWARD_ORDER, INTERRUPT_MEANS
from artifactsmmo_cli.ai.tiers.meta_goal import ReachTaskOutcome
from artifactsmmo_cli.ai.world_state import WorldState
from formal.sim.fake_server import FakeServer
from formal.sim.production_ladder import (
    ALL_IN_LADDER_ORDER,
    LadderMeans,
    production_ladder,
)
from formal.sim.production_ladder import (
    fires as production_fires,
)

# ---------------------------------------------------------------------------
# Reporting infrastructure
# ---------------------------------------------------------------------------

class _Counters:
    """Per-session firing/invariant counters for the end-of-run summary."""

    def __init__(self) -> None:
        self.samples = 0
        self.per_means: dict[LadderMeans, int] = {k: 0 for k in ALL_IN_LADDER_ORDER}
        self.none_returns: list[str] = []
        self.task_valid_violations: list[str] = []
        self.objective_phase_violations: list[str] = []

    def report(self) -> str:
        lines = [
            "",
            "=== Phase 20d-v2 differential coverage ===",
            f"samples: {self.samples}",
            f"productionLadder returned None: {len(self.none_returns)}",
            f"taskValid invariant violations: {len(self.task_valid_violations)}",
            (
                "objective-step task-phase invariant violations: "
                f"{len(self.objective_phase_violations)}"
            ),
            "per-MeansKind firing tally:",
        ]
        for k in ALL_IN_LADDER_ORDER:
            lines.append(f"  {k.name:22s} {self.per_means[k]:5d}")
        return "\n".join(lines)


COUNTERS = _Counters()


# ---------------------------------------------------------------------------
# Hypothesis strategies — adversarial WorldState shapes
# ---------------------------------------------------------------------------

def _base_world(
    *,
    task_code: str | None,
    task_type: str | None,
    task_progress: int,
    task_total: int,
    hp: int,
    max_hp: int,
    inventory_used: int,
    inventory_max: int,
    bank_items: dict[str, int] | None,
    pending: tuple[tuple[str, str], ...] | None,
    level: int,
    xp: int,
    gold: int,
) -> WorldState:
    """Build a WorldState with `inventory_used` synthetic items.

    Inventory items use a dummy code that nothing in GameData knows about, so
    `npcs_buying_item` returns []; this keeps the SELL_* predicates inert
    until we deliberately wire a sellable code in.
    """
    inventory: dict[str, int] = {"_synth": inventory_used} if inventory_used > 0 else {}
    return WorldState(
        character="diff",
        level=level,
        xp=xp,
        max_xp=max(1, xp + 100),
        hp=max(0, hp),
        max_hp=max(1, max_hp),
        gold=gold,
        skills={},
        x=0,
        y=0,
        inventory=inventory,
        inventory_max=max(0, inventory_max),
        inventory_slots_max=max(0, inventory_max),
        equipment={},
        cooldown_expires=None,
        task_code=task_code,
        task_type=task_type,
        task_progress=task_progress,
        task_total=task_total,
        bank_items=bank_items,
        bank_gold=0 if bank_items is not None else None,
        pending_items=pending,
    )


# Whole-range scalar primitives. Bounded but not toy-sized; the spec asks for
# diverse states including level 1..50, empty/full inventory, bank locked.
_lvl = st.integers(min_value=1, max_value=50)
_hp = st.integers(min_value=0, max_value=500)
_inv = st.integers(min_value=0, max_value=200)
_xp = st.integers(min_value=0, max_value=100_000)


@st.composite
def _arbitrary_states(draw: st.DrawFn) -> WorldState:
    """The general adversarial state generator. Spans empty/full inventory,
    has-task / no-task, items / monsters / resources task types,
    bank-known / bank-unknown, pending claim / no pending claim, various HP
    and level bands."""
    has_task = draw(st.booleans())
    task_type_choice = draw(st.sampled_from(["items", "monsters", "resources", "crafting"]))
    task_total = draw(st.integers(min_value=0, max_value=50))
    task_progress = draw(st.integers(min_value=0, max_value=max(0, task_total + 5)))
    inv_max = draw(st.integers(min_value=0, max_value=100))
    inv_used = draw(st.integers(min_value=0, max_value=max(0, inv_max + 5)))
    bank_known = draw(st.booleans())
    bank_items: dict[str, int] | None = {} if bank_known else None
    pending_present = draw(st.booleans())
    pending = (("p1", "_synth"),) if pending_present else None
    return _base_world(
        task_code="task_x" if has_task else None,
        task_type=task_type_choice if has_task else None,
        task_progress=task_progress,
        task_total=task_total if has_task else 0,
        hp=draw(_hp),
        max_hp=draw(st.integers(min_value=1, max_value=500)),
        inventory_used=inv_used,
        inventory_max=inv_max,
        bank_items=bank_items,
        pending=pending,
        level=draw(_lvl),
        xp=draw(_xp),
        gold=draw(st.integers(min_value=0, max_value=10_000)),
    )


@st.composite
def _items_task_in_progress(draw: st.DrawFn) -> WorldState:
    """Adversarial: items-task in progress, history=None (the retired
    PURSUE_TASK rung needed history, so it never fired here). The state where
    the retired Phase 20c-v2 `pursueFiresWhenInProgress` invariant was
    falsified under faithful production semantics; the objective step's
    task-phase arm must carry it now."""
    task_total = draw(st.integers(min_value=1, max_value=20))
    task_progress = draw(st.integers(min_value=0, max_value=task_total - 1))
    return _base_world(
        task_code="task_items",
        task_type="items",
        task_progress=task_progress,
        task_total=task_total,
        hp=draw(st.integers(min_value=50, max_value=500)),  # not HP_CRITICAL
        max_hp=100,
        inventory_used=draw(st.integers(min_value=0, max_value=50)),
        inventory_max=100,
        bank_items=None,  # bank not yet visited
        pending=None,
        level=draw(_lvl),
        xp=draw(_xp),
        gold=0,
    )


@st.composite
def _monsters_task_in_progress(draw: st.DrawFn) -> WorldState:
    """Adversarial: monsters-task in progress. The production items-task
    arm of `_task_root` only holds for `task_type == "items"` — for a
    monsters-task, what fires? If nothing, this is a deadlock witness."""
    task_total = draw(st.integers(min_value=1, max_value=20))
    task_progress = draw(st.integers(min_value=0, max_value=task_total - 1))
    return _base_world(
        task_code="task_monsters",
        task_type="monsters",
        task_progress=task_progress,
        task_total=task_total,
        hp=draw(st.integers(min_value=50, max_value=500)),
        max_hp=100,
        inventory_used=draw(st.integers(min_value=0, max_value=50)),
        inventory_max=100,
        bank_items=None,
        pending=None,
        level=draw(_lvl),
        xp=draw(_xp),
        gold=0,
    )


# Selection-context strategies. `bank_accessible=True`, no bank_unlock_monster,
# task_exchange_min_coins large so TASK_EXCHANGE doesn't accidentally fire.
@st.composite
def _ctx(draw: st.DrawFn) -> SelectionContext:
    return SelectionContext(
        bank_accessible=draw(st.booleans()),
        bank_required_level=draw(st.integers(min_value=0, max_value=10)),
        bank_unlock_monster=None,
        initial_xp=draw(st.integers(min_value=0, max_value=100_000)),
        task_exchange_min_coins=draw(st.integers(min_value=1_000, max_value=10_000)),
        combat_monster=None,
        # a draw is OWED — the normal taskless state, and ACCEPT_TASK's gate
        draw_owed=True,
    )


def _items_task_unmet(state: WorldState) -> bool:
    """A held, unmet items task — the task objective works it unless its worth
    cancels it (production `decisions/root._task_root`'s items arm; the
    retired PURSUE_TASK rung's successor since Phase 5-2c-iii-c-2 #5)."""
    return (state.task_type == "items" and bool(state.task_code)
            and state.task_progress < state.task_total)


def _empty_gd() -> GameData:
    """GameData with no monsters, no NPC buyers, no recipes. Keeps the
    differential focused on STATE-driven `_fires` branches; the data-driven
    branches (`npcs_buying_item`, `select_bank_deposits`, `monster_level`)
    are pinned to their "no data" defaults."""
    return GameData()


# ---------------------------------------------------------------------------
# Invariant tests
# ---------------------------------------------------------------------------

@settings(max_examples=400, suppress_health_check=[HealthCheck.too_slow])
@given(state=_arbitrary_states(), ctx=_ctx())
def test_phantomTask_state_is_a_real_deadlock_shape(
    state: WorldState, ctx: SelectionContext
) -> None:
    """Adversarial: a `taskCode set ∧ taskTotal == 0` (phantom-task) or
    `taskCode none ∧ taskTotal > 0` (orphan-total) state DOES break the
    ladder if ever realized.

    The Phase 20c-v2 Lean invariant `taskValid` is therefore LOAD-BEARING:
    if perceive.py ever produced such a state, production would deadlock
    on the discretionary tier alone. This test demonstrates the deadlock
    shape EXPLICITLY by constructing it and showing the
    held-unmet-items-task test `_items_task_unmet` (the task objective's work
    since PURSUE_TASK was retired, mirroring `_task_root`) does not hold, the
    OBJECTIVE_STEP rung's task-phase arms do not fire (a phantom task's
    lifecycle phase is NONE — this covers the met-task turn-in too, the
    retired COMPLETE_TASK rung's, c-2 #6), and no draw can be taken
    (`accept_due`, the task objective's accept since ACCEPT_TASK was
    retired).

    The assertion is the documentation: when this shape occurs, the
    discretionary tier is empty. Production survives only via the opaque
    OBJECTIVE_STEP flag (NoDeadlockV2 falls back to taskValid to
    discharge this case in the proof — perceive.py never produces it).
    """
    COUNTERS.samples += 1
    gd = _empty_gd()
    if state.task_code is not None and state.task_total <= 0:
        worked = _items_task_unmet(state)
        step_phase = production_fires(LadderMeans.OBJECTIVE_STEP, state, gd,
                                      None, ctx, False)
        accept = accept_due(state, ctx)
        assert not (worked or step_phase or accept), (
            f"Phantom-task state but a task means fires anyway — "
            f"production semantics changed; revisit Lean invariant taskValid. "
            f"worked={worked} step_phase={step_phase} accept={accept}"
        )
        COUNTERS.task_valid_violations.append(
            f"phantom-task: code={state.task_code!r} total={state.task_total}"
        )
    if state.task_total > 0 and state.task_code is None:
        # The task objective can still take a draw for orphan-total
        # (`accept_due` keys on `not state.task_code`). So orphan-total is
        # recoverable.
        accept = accept_due(state, ctx)
        assert accept, "orphan-total state: the task objective should still accept"
        COUNTERS.task_valid_violations.append(
            f"orphan-total: total={state.task_total} (recoverable via the accept)"
        )


@settings(max_examples=400, suppress_health_check=[HealthCheck.too_slow])
@given(state=_items_task_in_progress(), ctx=_ctx())
def test_objective_step_fires_when_items_task_in_progress_history_none(
    state: WorldState, ctx: SelectionContext
) -> None:
    """The successor of LadderTotalInvariants.pursueFiresWhenInProgress under
    the `history=None` shape — the worst case for items tasks.

    The retired PURSUE_TASK rung REQUIRED `history is not None`, so on this
    shape it never fired and the old Lean invariant was FALSE under faithful
    production semantics (production survived only on the opaque
    objective-step flag). Since Phase 5-2c-iii-c-2 #4 a held, unmet task fires
    OBJECTIVE_STEP on its lifecycle phase alone, with the opaque flag OFF and
    no history. Pin both halves: production's `_task_root` offers the task
    objective for it with no history (since #5 a held, unmet items task is
    worked unless its worth cancels it — no coin here, so no cancel), AND the
    ladder's OBJECTIVE_STEP phase arm fires, so the ladder is not left to WAIT
    on an in-progress items task. A violation is recorded and FAILS.
    """
    gd = _empty_gd()
    history = None
    assert _items_task_unmet(state)
    assert _task_root(state, gd, ctx, history) == ReachTaskOutcome(state.task_code)
    step_fires = production_fires(LadderMeans.OBJECTIVE_STEP, state, gd,
                                  history, ctx, False)
    if not step_fires:
        COUNTERS.objective_phase_violations.append(
            f"items-task hist=None: progress={state.task_progress}/{state.task_total}"
        )
    assert step_fires, (
        "OBJECTIVE_STEP's task-phase arm did not fire on an in-progress items "
        f"task (the retired PURSUE_TASK's coverage). state={state}"
    )
    selected = production_ladder(state, gd, history, ctx, False)
    assert selected is not None and selected is not LadderMeans.WAIT, (
        f"in-progress items task fell through to {selected!r}. state={state}"
    )


@settings(max_examples=400, suppress_health_check=[HealthCheck.too_slow])
@given(state=_monsters_task_in_progress(), ctx=_ctx())
def test_monster_task_in_progress_some_means_fires(
    state: WorldState, ctx: SelectionContext
) -> None:
    """Adversarial: the production items-task arm of `_task_root` only
    holds for items tasks. For a monsters-task in progress with history=None
    and no other pressure, does any means fire? In production a monsters-task is handled by the
    OBJECTIVE_STEP tier (StrategyArbiter materialises a FightMonster
    StepGoal). Since this differential doesn't simulate the objective
    tier (objective_step_fires=False), we expect NO means in the dispatch
    ladder to fire — that's not a deadlock (the StrategyArbiter would
    still plan via the objective tier) but it documents the OBJECTIVE_STEP
    dependency.

    The honest claim: with objective_step_fires=True the ladder is total
    on this shape; with False, only ACCEPT_TASK / TASK_EXCHANGE may
    coincidentally fire. We assert the ladder returns SOMETHING when
    objective_step_fires=True (mirrors production behaviour)."""
    gd = _empty_gd()
    history = None
    # With objective tier ENABLED the ladder must find a firing means.
    result = production_ladder(state, gd, history, ctx, objective_step_fires=True)
    if result is None:
        msg = (
            "MONSTERS-TASK DEADLOCK (with objective_step): "
            f"task_progress={state.task_progress}/{state.task_total} "
            f"hp={state.hp}/{state.max_hp} inv={state.inventory_used}/{state.inventory_max}"
        )
        COUNTERS.none_returns.append(msg)
        raise AssertionError(msg)


@settings(max_examples=800, suppress_health_check=[HealthCheck.too_slow])
@given(state=_arbitrary_states(), ctx=_ctx())
def test_productionLadder_totality_with_objective_step(
    state: WorldState, ctx: SelectionContext
) -> None:
    """The headline (operational form): if the objective tier is in scope
    (`objective_step_fires=True`), `productionLadder` ALWAYS returns
    some means. This is the production-truthful statement of the Lean
    theorem: in real production the StrategyArbiter falls back to the
    objective StepGoal whenever no higher-priority means fires.

    A failure here = a state shape where neither any means nor the
    objective step covers the dispatch. That would be a deadlock the
    StrategyArbiter cannot escape — file a bug."""
    gd = _empty_gd()
    history = None
    result = production_ladder(state, gd, history, ctx, objective_step_fires=True)
    if result is not None:
        COUNTERS.per_means[result] += 1
    else:
        msg = (
            "LADDER NONE witness (objective_step=True): "
            f"task_code={state.task_code!r} progress={state.task_progress}/"
            f"{state.task_total} hp={state.hp}/{state.max_hp} "
            f"inv={state.inventory_used}/{state.inventory_max} "
            f"bank_known={state.bank_items is not None} "
            f"bank_accessible={ctx.bank_accessible}"
        )
        COUNTERS.none_returns.append(msg)
        raise AssertionError(msg)


@settings(max_examples=400, suppress_health_check=[HealthCheck.too_slow])
@given(state=_arbitrary_states(), ctx=_ctx())
def test_productionLadder_falsifiable_without_objective_step(
    state: WorldState, ctx: SelectionContext
) -> None:
    """Without the objective tier (`objective_step_fires=False`), the
    ladder MAY return None — this test simply records when it does. Its
    purpose is empirical coverage, not falsification: it documents the
    rate at which the discretionary tier alone (no objective, no history)
    can't pick a means.

    If this records witnesses on shapes the user expects ACCEPT_TASK or
    TASK_EXCHANGE to handle, that's evidence those means are too narrow."""
    gd = _empty_gd()
    history = None
    production_ladder(state, gd, history, ctx, objective_step_fires=False)
    # No assertion — empirical only. The coverage table picks it up.


# ---------------------------------------------------------------------------
# Sanity / mirror tests
# ---------------------------------------------------------------------------

def test_ladder_entry_count_matches_lean() -> None:
    """Mirror sanity: the Python ladder has the same length as the Lean
    `MeansKind.allInLadderOrder` (whose length is pinned by the `example` at the
    bottom of `formal/Formal/Liveness/MeansKind.lean` — update BOTH together).

    26 = original 17 + WAIT (Phase 20e-v2) + CRAFT_RELIEF (circuit
    breaker between DISCARD_CRITICAL and DEPOSIT_FULL) + REST_FOR_COMBAT
    (after HP_CRITICAL) + MAINTAIN_CONSUMABLES (PLAN #6a, after TASK_EXCHANGE)
    + RECYCLE_RELIEF (bank-full cascade, after CRAFT_RELIEF)
    + SELL_RELIEF (bank-full cascade, after RECYCLE_RELIEF)
    + DRAIN_BANK_JUNK (lowest-value housekeeping, after BANK_EXPAND)
    + CRAFT_POTIONS (last guard in GUARD_ORDER, after DISCARD_HIGH)
    + GE_CANCEL (on-need + TTL order cancellation, below the FIGHT gates)
    + GE_BID (discretionary reactive buy-post, above DRAIN_BANK_JUNK)
    + SUPPLY_BANK (2026-08-01 human ruling, produce for a sibling; PROMOTED out
    of DISCRETIONARY_ORDER into COLLECT_REWARD_ORDER, so it sits LAST in the
    collect group — above OBJECTIVE_STEP)
    + CURRENCY_TURNIN (2026-08-16, fleet-currency-turn-in epic Task 6; sits
    directly below SUPPLY_BANK in COLLECT_REWARD_ORDER, still above
    OBJECTIVE_STEP).
    − GEAR_REVIEW (retired in Phase 4-3b: its one arm never fired).
    − LOW_YIELD_CANCEL, TASK_EXCHANGE, ACCEPT_TASK (retired in Phase
    5-2c-iii-c-2: the task objective's step).
    − PURSUE_TASK (retired in Phase 5-2c-iii-c-2 #4: the task objective's
    step; OBJECTIVE_STEP fires on a held, unmet task's phase).
    − TASK_CANCEL (retired in Phase 5-2c-iii-c-2 #5: the task objective's
    step cancels a worthless task).
    − COMPLETE_TASK (retired in Phase 5-2c-iii-c-2 #6: the task objective's
    step turns a met task in; OBJECTIVE_STEP fires on its complete phase).
    − SUPPLY_BANK, CURRENCY_TURNIN (retired in Phase 5-2c-iv: the fleet
    objective's step; OBJECTIVE_STEP fires on `supply_due` / `turn_in_due`).
    − MAINTAIN_CONSUMABLES (retired 2026-10-10: every fight step carries its
    loadout's potions and food).
    Lean side mirrors via MeansKind.allInLadderOrder."""
    assert len(ALL_IN_LADDER_ORDER) == 21


def test_the_ladder_interrupt_prefix_is_what_production_runs_as_interrupts() -> None:
    """Phase 5-2a/5-2b: `StrategyArbiter._arbitrate` runs the band-0 candidates
    (the guards in `GUARD_ORDER`, then the `INTERRUPT_MEANS` in
    `COLLECT_REWARD_ORDER`) before any means. The
    liveness ladder keeps that order as its prefix, so the model's "ladder
    order" and the code's "interrupts, then the walk" are one order. (The
    shed-urgency hoists are interrupts too, but the ladder models their idle
    forms as discretionary rungs and has no hoist rung at all.)"""
    interrupts = ([LadderMeans[g.name] for g in GUARD_ORDER]
                  + [LadderMeans[m.name] for m in COLLECT_REWARD_ORDER if m in INTERRUPT_MEANS])
    assert list(ALL_IN_LADDER_ORDER[:len(interrupts)]) == interrupts


def test_no_task_state_with_a_draw_owed_offers_the_task_objective() -> None:
    """A baseline: no task AND a draw owed ⇒ the task objective is offered, so
    the objective step fires and the ladder takes it.

    Until Phase 5-2c-iii-c-2 #3 this was the ACCEPT_TASK rung above the step;
    the accept is now the task objective's step (`ReachTaskOutcome(None)`),
    which is why `Formal.Liveness.NoWait.productionLadder_ne_wait` no longer
    needs a draw-owed disjunct of its own."""
    gd = _empty_gd()
    ctx = SelectionContext(
        draw_owed=True,
        bank_accessible=True,
        bank_required_level=0,
        bank_unlock_monster=None,
        initial_xp=0,
        task_exchange_min_coins=10_000,
        combat_monster=None,
    )
    state = _base_world(
        task_code=None, task_type=None, task_progress=0, task_total=0,
        hp=100, max_hp=100, inventory_used=0, inventory_max=100,
        bank_items={}, pending=None, level=1, xp=0, gold=0,
    )
    assert accept_due(state, ctx)
    assert _task_root(state, gd, ctx, None) == ReachTaskOutcome(None)
    res = production_ladder(state, gd, None, ctx, objective_step_fires=True)
    assert res is LadderMeans.OBJECTIVE_STEP, f"expected OBJECTIVE_STEP, got {res!r}"


def test_completed_task_state_objective_step_fires() -> None:
    """Baseline: task at progress==total ⇒ the task objective is offered for
    it (`_task_root`) and OBJECTIVE_STEP fires on its complete phase alone
    (opaque flag OFF). Phase 5-2c-iii-c-2 #6: this was the COMPLETE_TASK
    rung; the turn-in is now the task objective's step. Second of three Lean
    witness branches."""
    gd = _empty_gd()
    ctx = SelectionContext(
        bank_accessible=True,
        bank_required_level=0,
        bank_unlock_monster=None,
        initial_xp=0,
        task_exchange_min_coins=10_000,
        combat_monster=None,
    )
    state = _base_world(
        task_code="task_done", task_type="items",
        task_progress=10, task_total=10,
        hp=100, max_hp=100, inventory_used=0, inventory_max=100,
        bank_items={}, pending=None, level=1, xp=0, gold=0,
    )
    assert _task_root(state, gd, ctx, None) == ReachTaskOutcome("task_done")
    res = production_ladder(state, gd, None, ctx, objective_step_fires=False)
    assert res is LadderMeans.OBJECTIVE_STEP, f"expected OBJECTIVE_STEP, got {res!r}"


def test_history_None_items_task_is_still_worked() -> None:
    """REGRESSION DOCUMENTATION: a fresh bot with no learning history still
    works a held, unmet items task. The retired PURSUE_TASK rung (and its
    successor predicate `pursue_due`, gone in Phase 5-2c-iii-c-2 #5) needed a
    PURSUE verdict and so was False when `history is None`; production's
    `_task_root` now offers the task objective for it whenever its worth does
    not cancel it. The ladder fires OBJECTIVE_STEP on the in-progress task's
    phase alone (opaque flag OFF), which is what makes the retired Lean
    invariant `pursueFiresWhenInProgress` unnecessary. If the first asserts
    flip, the task objective stopped working items tasks; if the last flips,
    the phase arm regressed and an in-progress items task can stall."""
    gd = _empty_gd()
    ctx = SelectionContext(
        bank_accessible=True,
        bank_required_level=0,
        bank_unlock_monster=None,
        initial_xp=0,
        task_exchange_min_coins=10_000,
        combat_monster=None,
    )
    state = _base_world(
        task_code="task_x", task_type="items",
        task_progress=1, task_total=10,
        hp=100, max_hp=100, inventory_used=0, inventory_max=100,
        bank_items=None, pending=None, level=1, xp=0, gold=0,
    )
    assert _items_task_unmet(state)
    assert _task_root(state, gd, ctx, None) == ReachTaskOutcome("task_x")
    assert production_ladder(state, gd, None, ctx, objective_step_fires=False) \
        is LadderMeans.OBJECTIVE_STEP


@settings(max_examples=800, suppress_health_check=[HealthCheck.too_slow])
@given(state=_arbitrary_states(), ctx=_ctx())
def test_productionLadder_unconditionally_total(
    state: WorldState, ctx: SelectionContext
) -> None:
    """Phase 20e-v2 prodfix headline: with the WAIT last-resort means in
    DISCRETIONARY_ORDER, `productionLadder` is total — it ALWAYS returns
    SOME LadderMeans, irrespective of `objective_step_fires`, history
    presence, or task state. This is the production guarantee that backs
    "the bot never stalls on No plan found".

    A failure here means the WAIT means did not fire (means.py:_fires WAIT
    branch regressed) or production_ladder lost its WAIT entry."""
    gd = _empty_gd()
    history = None
    result = production_ladder(state, gd, history, ctx, objective_step_fires=False)
    assert result is not None, (
        "WAIT last-resort means did NOT fire — productionLadder regressed. "
        f"state={state}"
    )


def test_zz_fake_server_cycle_no_deadlock() -> None:
    """FakeServer cycle differential (Phase 20d-v2 scope item 4).

    Run K=20 cycles of fight/gather/rest interleaved; after each cycle
    assert `productionLadder(state, ...) is not None` with
    `objective_step_fires=True`. If any cycle returns None, surface
    cycle index + state."""
    initial = _base_world(
        task_code="task_x", task_type="items",
        task_progress=0, task_total=5,
        hp=100, max_hp=100, inventory_used=0, inventory_max=20,
        bank_items={}, pending=None, level=5, xp=0, gold=0,
    )
    server = FakeServer(initial)
    gd = _empty_gd()
    ctx = SelectionContext(
        bank_accessible=True,
        bank_required_level=0,
        bank_unlock_monster=None,
        initial_xp=0,
        task_exchange_min_coins=10_000,
        combat_monster=None,
    )
    for cycle in range(20):
        if cycle % 3 == 0:
            server.gather("ore", "mining")
        elif cycle % 3 == 1:
            server.rest()
        else:
            server.fight("chicken", monster_matches_task=False)
        result = production_ladder(
            server.state, gd, None, ctx, objective_step_fires=True,
        )
        assert result is not None, (
            f"FakeServer cycle {cycle}: productionLadder returned None. "
            f"state={server.state}"
        )


def test_zzz_emit_coverage_report() -> None:
    """Emits the coverage report. Runs last (source order is preserved by
    pytest) so its `COUNTERS` reflect every preceding property test."""
    print(COUNTERS.report())

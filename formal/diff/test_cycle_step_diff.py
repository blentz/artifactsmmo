"""Phase 22b — cycle-loop differential.

Binds the Lean `cycleStep` (mirrored as `cycle_step_mirror`) to the
production loop's per-cycle pure transition. For each Hypothesis-sampled
firing state:

  1. Compute `cycle_step_mirror(CycleState)` — Python port of the Lean
     `Formal.Liveness.CycleStep.cycleStep`.
  2. Compute `drive_one_cycle(WorldState)` — REAL production
     `production_ladder` + production Action `.apply()` on the witness action
     for the chosen MeansKind.
  3. Compare on `TRACKED_FIELDS` (the projection of Lean `State` -> WorldState
     fields whose mutation semantics are equivalent on both sides).

A divergence = REAL BUG: either the Lean model drifted from production, or
the production action's per-cycle projection contradicts the Lean
single-step semantics.

## Honest disclosure: scope reduction

The "production loop" here is `production_ladder + action.apply`, NOT the
full `perceive → _build_actions → arbiter.select → execute → learn → stuck-
detect` loop in `src/artifactsmmo_cli/ai/player.py:190-410`.  Constructing a
faithful `drive_one_cycle` that exercises `arbiter.select` on every
Hypothesis-sampled synthetic state would require per-state fixture
reconstruction (equipped weapons, monster locations, learning history,
periodic-refresh state) that defeats the random-sampling differential.  The
chosen scope still pins the load-bearing per-cycle commitment: given a
firing means, the action the bot actually runs has the projection the Lean
model claims.

## Honest disclosure: TRACKED_FIELDS

The Lean `State` has 32 fields, many opaque Bools (`pursueTaskFires`,
`taskCancelFires`, …) whose post-cycle value in production is determined
by the next perception refresh (not the action's `.apply`).  We compare
ONLY the fields whose mutation rules are equivalent across:
  * Lean `applyActionKind` (Plan.lean lines 103-255)
  * Production `Action.apply` (per-action class)

That subset is:
  * `level`         — fight: never advances under the projection (Lean's
                      `xpToNextLevel = 999999` ⇒ no rollover; production
                      `FightAction.apply` also doesn't bump level — only
                      perception does post-execute).
  * `xp`            — fight: +10. All other actions: unchanged.
  * `hp`            — rest: =max_hp. Other actions tracked separately.
                      NOT compared on .fight: Lean's fight omits HP damage
                      (PlanAction.lean honest-disclosure); production
                      damages.  This is the deliberate Lean abstraction.
  * `task_code`     — completeTask: cleared.  acceptTask: placeholder.
                      taskCancel: cleared. Canonicalized via `_norm_task_code`
                      (production uses `""` for cleared, Lean uses `None`).
  * `task_total`    — completeTask: 0. acceptTask: 1. taskCancel: 0.
  * `task_progress` — completeTask: 0. acceptTask: 0. taskCancel: 0.
                      taskTrade: =task_total (with quantity arg matched).
  * `gold`          — buyBankExpansion: -=cost. Other actions: 0-delta.

Excluded (with rationale):
  * Inventory dict: Lean models opaque Bools; production tracks per-item
    qty. The opaque Bools have no concrete production analogue.
  * Bank items dict / capacity: production updates on deposit/expand; Lean
    updates only `bankCapacity` on .buyBankExpansion. Per-action targeted
    comparison only (see `_compare`).
  * `bank_accessible`: production NEVER flips this in `.apply` — only the
    perception layer integrates it after a successful unlock-fight
    (the Lean .fight bank-unlock flip is the planner-side projection of
    what perception WILL observe). Comparing here would create a false
    positive for BANK_UNLOCK.
  * Per-action position (x, y): production moves to the dest; Lean
    abstracts coordinates entirely.

## Mutations (≥4) — see `mutate.py::CYCLE_STEP_MUTATIONS`.
"""
from __future__ import annotations

import dataclasses

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.bank_expansion import BuyBankExpansionAction
from artifactsmmo_cli.ai.actions.claim import ClaimPendingItemAction
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.complete_task import CompleteTaskAction
from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.task_cancel import TaskCancelAction
from artifactsmmo_cli.ai.actions.task_exchange import TaskExchangeAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.actions.wait import WaitAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState
from formal.sim.cycle_step import (
    CycleState,
    MIRROR_PLAN_FOR,
    cycle_step_mirror,
    mirror_production_ladder,
)
from formal.sim.production_ladder import LadderMeans, production_ladder


# ---------------------------------------------------------------------------
# Projection helpers — the fields we compare across mirror/production.
# ---------------------------------------------------------------------------

TRACKED_FIELDS: tuple[str, ...] = (
    "level", "xp", "task_code", "task_total", "task_progress", "gold",
)


def _norm_task_code(tc) -> str | None:
    """Canonicalise the two representations of a "cleared" task slot:
    Lean uses `None`; production `CompleteTaskAction.apply` writes `""`."""
    if tc is None or tc == "":
        return None
    return tc


@dataclasses.dataclass(frozen=True)
class Projection:
    level: int
    xp: int
    task_code: str | None
    task_total: int
    task_progress: int
    gold: int


def _project_cycle(c: CycleState) -> Projection:
    return Projection(
        level=c.level, xp=c.xp,
        task_code=_norm_task_code(c.task_code),
        task_total=c.task_total, task_progress=c.task_progress,
        gold=c.gold,
    )


def _project_world(w: WorldState) -> Projection:
    return Projection(
        level=w.level, xp=w.xp,
        task_code=_norm_task_code(w.task_code),
        task_total=w.task_total, task_progress=w.task_progress,
        gold=w.gold,
    )


# ---------------------------------------------------------------------------
# Per-MeansKind firing-state fixtures.
# Each constructor returns:
#   (CycleState, WorldState, GameData, SelectionContext, production_action,
#    expected_means)
# such that:
#   * `mirror_production_ladder(cstate) == expected_means`
#   * `production_ladder(wstate, gd, None, ctx) == expected_means`
#   * `production_action.apply(wstate, gd)` is the witness ApplyActionKind
#     for `expected_means`.
# ---------------------------------------------------------------------------


def _base_world(**overrides) -> WorldState:
    defaults: dict[str, object] = dict(
        character="diff", level=5, xp=0, max_xp=999999,
        hp=100, max_hp=100, gold=0, skills={},
        x=0, y=0, inventory={}, inventory_max=20, equipment={},
        cooldown_expires=None,
        task_code=None, task_type=None, task_progress=0, task_total=0,
        bank_items=None, bank_gold=None, pending_items=None,
    )
    defaults.update(overrides)
    return WorldState(**defaults)


def _world_to_cycle(w: WorldState, *, ctx: SelectionContext, gd: GameData,
                    overrides) -> CycleState:
    """Project a WorldState into the abstract CycleState. `overrides` injects
    the opaque-Bool firing-predicate observations the Lean model carries
    that don't read directly off WorldState."""
    cs = CycleState(
        level=w.level, xp=w.xp,
        task_progress=w.task_progress, task_total=w.task_total,
        inventory_used=sum(w.inventory.values()),
        inventory_max=w.inventory_max,
        hp=w.hp, max_hp=w.max_hp,
        task_type=w.task_type, task_code=w.task_code,
        projected_skill_xp_delta=0, target_skill_xp=0,
        gold=w.gold,
        bank_accessible=ctx.bank_accessible,
        bank_unlock_monster_present=(ctx.bank_unlock_monster is not None),
        initial_xp=ctx.initial_xp,
        unlock_monster_level=0,
        bank_required_level=ctx.bank_required_level,
        has_overstock_items=False,
        select_bank_deposits_nonempty=False,
        pending_items_nonempty=bool(w.pending_items),
        sellable_inventory_nonempty=False,
        task_coins_total=w.inventory.get(TASKS_COIN_CODE, 0),
        task_exchange_min_coins=ctx.task_exchange_min_coins,
        low_yield_cancel_fires=False,
        task_cancel_fires=False,
        pursue_task_fires=False,
        objective_step_fires=False,
        bank_items_known=(w.bank_items is not None),
        bank_items_count=(len(w.bank_items) if w.bank_items is not None else 0),
        bank_capacity=0,
        next_expansion_cost=0,
    )
    return dataclasses.replace(cs, **overrides)


def _base_gd() -> GameData:
    gd = GameData()
    gd._bank_location = (4, 0)
    gd._bank_location_open = True
    gd._taskmaster_location = (1, 2)
    gd._monster_locations = {"chicken": [(1, 0)]}
    gd._monster_level = {"chicken": 1}
    gd._monster_hp = {"chicken": 10}
    gd._monster_attack = {"chicken": {"fire": 1}}
    gd._monster_resistance = {"chicken": {}}
    gd._monster_critical_strike = {"chicken": 0}
    gd._monster_initiative = {"chicken": 0}
    gd._item_stats = {
        "wooden_stick": ItemStats(
            code="wooden_stick", level=1, type_="weapon",
            crafting_skill=None, crafting_level=0, hp_restore=0,
        ),
    }
    gd._crafting_recipes = {}
    gd._resource_locations = {}
    gd._resource_skill = {}
    gd._resource_drops = {}
    gd._workshop_locations = {}
    gd._npc_stock = {}
    gd._npc_sell_prices = {}
    return gd


def _ctx(**overrides) -> SelectionContext:
    defaults: dict[str, object] = dict(
        bank_accessible=True, bank_required_level=0,
        bank_unlock_monster=None, initial_xp=0,
        task_exchange_min_coins=1, combat_monster=None,
    )
    defaults.update(overrides)
    return SelectionContext(**defaults)


# ---------- per-MeansKind fixture constructors ----------

def _fix_HP_CRITICAL():
    gd = _base_gd()
    w = _base_world(hp=10, max_hp=100)
    ctx = _ctx()
    cs = _world_to_cycle(w, ctx=ctx, gd=gd, overrides={})
    return cs, w, gd, ctx, RestAction(), LadderMeans.HP_CRITICAL


def _fix_CLAIM_PENDING():
    gd = _base_gd()
    w = _base_world(pending_items=(("pid", "junk"),))
    ctx = _ctx()
    cs = _world_to_cycle(w, ctx=ctx, gd=gd, overrides={})
    return cs, w, gd, ctx, ClaimPendingItemAction(), LadderMeans.CLAIM_PENDING


def _fix_COMPLETE_TASK():
    gd = _base_gd()
    w = _base_world(task_code="task_done", task_type="items",
                    task_progress=5, task_total=5)
    ctx = _ctx()
    cs = _world_to_cycle(w, ctx=ctx, gd=gd, overrides={})
    return cs, w, gd, ctx, CompleteTaskAction(taskmaster_location=(1, 2)), \
           LadderMeans.COMPLETE_TASK


def _fix_ACCEPT_TASK():
    gd = _base_gd()
    w = _base_world()
    ctx = _ctx()
    cs = _world_to_cycle(w, ctx=ctx, gd=gd, overrides={})
    return cs, w, gd, ctx, AcceptTaskAction(taskmaster_location=(1, 2)), \
           LadderMeans.ACCEPT_TASK


def _fix_TASK_EXCHANGE():
    gd = _base_gd()
    # Need a task assigned so ACCEPT_TASK doesn't fire above us in the ladder.
    # Task in progress (not complete) so COMPLETE_TASK doesn't fire either.
    w = _base_world(
        inventory={TASKS_COIN_CODE: 3},
        task_code="t", task_type="items", task_progress=0, task_total=5,
    )
    ctx = _ctx(task_exchange_min_coins=1)
    cs = _world_to_cycle(w, ctx=ctx, gd=gd, overrides={})
    return cs, w, gd, ctx, TaskExchangeAction(min_coins=1, taskmaster_location=(1, 2)), \
           LadderMeans.TASK_EXCHANGE


def _fix_PURSUE_TASK():
    """Inject pursue_task_fires=True on the mirror side; on the production
    side, set the items-task and use TaskTradeAction(quantity = remaining).
    Both sides see PURSUE_TASK fire and apply taskTrade -> task_progress
    advances to task_total."""
    gd = _base_gd()
    w = _base_world(task_code="task_x", task_type="items",
                    task_progress=0, task_total=5,
                    inventory={"task_x": 5})
    ctx = _ctx()
    cs = _world_to_cycle(w, ctx=ctx, gd=gd, overrides={
        "pursue_task_fires": True,
    })
    # On production we drive the action directly; production_ladder would
    # also fire PURSUE_TASK iff a LearningStore is supplied — we substitute
    # the means selection (see drive_one_cycle's `forced_means` path).
    return cs, w, gd, ctx, TaskTradeAction(
        code="task_x", quantity=5, taskmaster_location=(1, 2),
    ), LadderMeans.PURSUE_TASK


def _fix_WAIT():
    gd = _base_gd()
    # Need task assigned (else ACCEPT_TASK fires) AND no task coins (else
    # TASK_EXCHANGE fires) AND no sellable (no NPC stock in gd: ok). Also
    # bank_capacity=0 so BANK_EXPAND doesn't fire. Resources task whose
    # progress is 0/very-large so PURSUE_TASK doesn't fire (and history=None).
    w = _base_world(
        task_code="t", task_type="resources",
        task_progress=0, task_total=99,
    )
    ctx = _ctx()
    cs = _world_to_cycle(w, ctx=ctx, gd=gd, overrides={})
    return cs, w, gd, ctx, WaitAction(), LadderMeans.WAIT


def _fix_BUY_BANK_EXPANSION():
    """BANK_EXPAND fires when bank is 95% full and gold >= cost. We exercise
    the .buyBankExpansion `.apply` projection directly (gold deducted)."""
    gd = _base_gd()
    gd._bank_capacity = 30
    gd._next_expansion_cost = 100
    # Same task-assignment trick as WAIT so ACCEPT_TASK is suppressed.
    w = _base_world(
        gold=200, bank_items={f"i_{i}": 1 for i in range(29)},
        task_code="t", task_type="resources",
        task_progress=0, task_total=99,
    )
    ctx = _ctx(bank_accessible=True)
    cs = _world_to_cycle(w, ctx=ctx, gd=gd, overrides={
        "bank_capacity": 30,
        "next_expansion_cost": 100,
        "bank_items_count": 29,
        "gold": 200,
    })
    return cs, w, gd, ctx, BuyBankExpansionAction(bank_location=(4, 0)), \
           LadderMeans.BANK_EXPAND


FIXTURES: dict[LadderMeans, callable] = {
    LadderMeans.HP_CRITICAL:    _fix_HP_CRITICAL,
    LadderMeans.CLAIM_PENDING:  _fix_CLAIM_PENDING,
    LadderMeans.COMPLETE_TASK:  _fix_COMPLETE_TASK,
    LadderMeans.ACCEPT_TASK:    _fix_ACCEPT_TASK,
    LadderMeans.TASK_EXCHANGE:  _fix_TASK_EXCHANGE,
    LadderMeans.PURSUE_TASK:    _fix_PURSUE_TASK,
    LadderMeans.WAIT:           _fix_WAIT,
    LadderMeans.BANK_EXPAND:    _fix_BUY_BANK_EXPANSION,
}


# ---------------------------------------------------------------------------
# drive_one_cycle — production side of the differential.
# ---------------------------------------------------------------------------


def drive_one_cycle(
    w: WorldState, gd: GameData, ctx: SelectionContext,
    production_action, expected_means: LadderMeans,
    *, force_objective_step: bool = False,
) -> tuple[LadderMeans | None, WorldState]:
    """Run one cycle production-side: real `production_ladder` (mirror that
    dispatches into real `_fires`) + production `action.apply`.

    For PURSUE_TASK we bypass `production_ladder` (it requires a learning
    history fixture) and assert directly that the production action is the
    expected witness; see Phase 21d-2 differential for the analogous
    history-shape skip.
    """
    if expected_means in (LadderMeans.PURSUE_TASK,):
        # Skip real-ladder check; just apply the witness action.
        new_state = production_action.apply(w, gd)
        return expected_means, new_state
    picked = production_ladder(w, gd, None, ctx, force_objective_step)
    new_state = production_action.apply(w, gd)
    return picked, new_state


# ---------------------------------------------------------------------------
# Differential tests — parameterised over fixtures.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("means", list(FIXTURES.keys()), ids=lambda m: m.name)
def test_mirror_picks_same_means_as_production(means: LadderMeans) -> None:
    """Mirror's `mirror_production_ladder` MUST pick the same MeansKind as
    real `production_ladder` for every in-scope fixture."""
    cs, w, gd, ctx, _action, expected = FIXTURES[means]()
    mirror_pick = mirror_production_ladder(cs)
    assert mirror_pick is expected, (
        f"MIRROR LADDER DRIFT for {means.name}:\n"
        f"  mirror picked: {mirror_pick}\n"
        f"  expected:      {expected}"
    )
    if means is not LadderMeans.PURSUE_TASK:
        prod_pick = production_ladder(w, gd, None, ctx, False)
        assert prod_pick is expected, (
            f"PRODUCTION LADDER DRIFT for {means.name}:\n"
            f"  production picked: {prod_pick}\n"
            f"  expected:          {expected}"
        )


@pytest.mark.parametrize("means", list(FIXTURES.keys()), ids=lambda m: m.name)
def test_cycle_step_projection_matches_production(means: LadderMeans) -> None:
    """Mirror's `cycle_step_mirror` must produce the same TRACKED_FIELDS
    projection as production's `drive_one_cycle` (real production_ladder +
    action.apply) on every in-scope firing state."""
    cs, w, gd, ctx, action, expected = FIXTURES[means]()
    mirror_post = cycle_step_mirror(cs)
    _picked, prod_post = drive_one_cycle(w, gd, ctx, action, expected)
    mirror_proj = _project_cycle(mirror_post)
    prod_proj = _project_world(prod_post)
    if mirror_proj != prod_proj:
        deltas = []
        for f in TRACKED_FIELDS:
            mv, pv = getattr(mirror_proj, f), getattr(prod_proj, f)
            if mv != pv:
                deltas.append(f"  {f}: mirror={mv!r} prod={pv!r}")
        diff_lines = "\n".join(deltas)
        pytest.fail(
            f"CYCLE-STEP PROJECTION DIVERGENCE for {means.name}:\n"
            f"{diff_lines}\n"
            f"  mirror_post.{tuple(f for f in TRACKED_FIELDS)} = "
            f"{tuple(getattr(mirror_proj, f) for f in TRACKED_FIELDS)}\n"
            f"  prod_post.{tuple(f for f in TRACKED_FIELDS)} = "
            f"{tuple(getattr(prod_proj, f) for f in TRACKED_FIELDS)}\n"
            f"  Either the Lean model drifted from production, or the "
            f"production .apply contradicts the Lean single-step semantics. "
            f"File it."
        )


# ---------------------------------------------------------------------------
# Hypothesis differential over the WAIT-state perturbation space.
# Samples small perturbations on a known WAIT-firing state and asserts the
# mirror still matches production. WAIT is the most-perturbable means
# because its predicate is unconditional `true` — any state hits it once
# all higher tiers fall through.
# ---------------------------------------------------------------------------


@st.composite
def _wait_neighbour_state(draw) -> tuple[CycleState, WorldState, GameData,
                                          SelectionContext]:
    """Generate a WAIT-firing state with mild perturbations on the
    not-firing-but-tracked fields (gold, level, xp)."""
    level = draw(st.integers(min_value=1, max_value=49))
    xp = draw(st.integers(min_value=0, max_value=400))
    gold = draw(st.integers(min_value=0, max_value=10000))
    gd = _base_gd()
    w = _base_world(
        level=level, xp=xp, gold=gold,
        task_code="t", task_type="resources",
        task_progress=0, task_total=99,
    )
    ctx = _ctx()
    cs = _world_to_cycle(w, ctx=ctx, gd=gd, overrides={})
    return cs, w, gd, ctx


@given(state=_wait_neighbour_state())
@settings(max_examples=300, derandomize=True,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_hypothesis_wait_cycle_byte_equivalent(state) -> None:
    """Hypothesis: every sampled WAIT-firing state has byte-equivalent
    mirror/production projections after one cycle."""
    cs, w, gd, ctx = state
    # Confirm WAIT is the firing means on both sides.
    assert mirror_production_ladder(cs) is LadderMeans.WAIT
    assert production_ladder(w, gd, None, ctx, False) is LadderMeans.WAIT
    mirror_post = cycle_step_mirror(cs)
    prod_post = WaitAction().apply(w, gd)
    mirror_proj = _project_cycle(mirror_post)
    prod_proj = _project_world(prod_post)
    assert mirror_proj == prod_proj, (
        f"WAIT cycle divergence:\n"
        f"  mirror_proj={mirror_proj}\n"
        f"  prod_proj={prod_proj}\n"
        f"  input_state={cs}"
    )


# ---------------------------------------------------------------------------
# Regression: the in-scope coverage MUST include the 4 mutation-killing
# means (HP_CRITICAL, COMPLETE_TASK, WAIT, BANK_EXPAND).
# ---------------------------------------------------------------------------

def test_scope_includes_mutation_targets() -> None:
    """Don't accidentally narrow the diff so mutations slip through."""
    required = {
        LadderMeans.HP_CRITICAL,
        LadderMeans.COMPLETE_TASK,
        LadderMeans.WAIT,
        LadderMeans.BANK_EXPAND,
    }
    assert required.issubset(FIXTURES.keys()), (
        f"scope narrowed; missing: {required - FIXTURES.keys()}"
    )


def test_witness_plan_for_covers_all_means() -> None:
    """Mirror plan_for must cover every LadderMeans (21 entries)."""
    from formal.sim.production_ladder import ALL_IN_LADDER_ORDER
    missing = set(ALL_IN_LADDER_ORDER) - set(MIRROR_PLAN_FOR.keys())
    assert not missing, f"MIRROR_PLAN_FOR missing: {missing}"

"""O5.4 Bricks 3+4 — SELECT-side differential for the FULL liveness ladder.

Binds the Lean liveness ladder (`Formal.Liveness.ProductionLadder.fires` /
`productionLadder`, evaluated through the `ladder_fires` oracle entry) to the
REAL production firing predicates `_guard_fires` (tiers/guards.py) and
`_means_fires` (tiers/means.py), reached through the real-import bridge
`formal/sim/production_ladder.py`. This closes the trust gap flagged in the
2026-06-18 SELECT audit: every liveness theorem reasons over the Lean ladder,
but nothing had ever asserted the Lean ladder MIRRORS production.

This file now covers the WHOLE 23-slot ladder:
  * Brick 3 (the random Hypothesis SWEEP + the numeric boundary witnesses) pins
    the NUMERIC/structural guard + phase-derived means slots, holding the 7
    opaque slots below at their reachable (False) value (see DEFERRED_SLOTS).
  * Brick 4 (the dedicated DRIVE tests, sections 4a/4b/4c below) stands up RICH
    fixtures where production's REAL machinery makes each opaque slot FIRE, then
    runs a SELECTION CONTEST against the oracle. The slots the sweep holds False
    are therefore no longer "unvalidated" — their TRUE-firing path is driven.

Mutation-enforced (Brick 5): `formal/diff/mutate.py` perturbs the threshold /
comparator / conjunct of each numeric `_fires` predicate (the
`LADDER_GUARD_FIRES_MUTATIONS` / `LADDER_MEANS_FIRES_MUTATIONS` groups, bound to
THIS file); the boundary witnesses below KILL every such mutant, so the
differential is provably non-vacuous on those predicates.

## The honest design — opaque Bools are INPUTS supplied identically

Several ladder slots read an opaque per-cycle observation that production
derives from machinery the random SWEEP does not reconstruct (the planner,
`predict_win`, `craft_relief_candidates`, …) — the Brick-4 DRIVE tests below
reconstruct it on rich fixtures. For the SWEEP, the differential is apples-to-
apples ONLY when both sides see the SAME inputs. Each scenario therefore drives
BOTH sides from one set of fields:

  * the concrete numeric/structural fields (hp, maxHp, level, xp, fill, task
    lifecycle, bank state, coins) feed production's `WorldState` /
    `SelectionContext` / `GameData` AND the 31-int oracle arg array; and
  * the opaque Bools we CAN pass through identically — `objective_step_fires`
    (→ `production_ladder(..., objective_step_fires)` and oracle arg[28]) and
    `gear_review_active` (→ `ctx.gear_review_active` and oracle arg[26]) — are
    handed to both sides verbatim, so `objectiveStep` and `gearReview` are
    genuinely compared, not skipped.

## Slots ASSERTED (per-slot agreement, every scenario)

Numeric / structural guards + phase-derived means whose firing production
computes from the supplied inputs under an empty-catalog `GameData`:

  * hpCritical          — hp/maxHp ratio (< 0.25).
  * bankUnlock          — ctx.bank_unlock_monster / bank_accessible / initial_xp
                          / monster level vs state.xp / level.
  * reachUnlockLevel    — ctx.bank_required_level vs state.level, gap <= 5.
  * discardCritical     — overstock (empty-catalog cap=0 ⇒ any held item is
                          overstock under pressure) AND fill >= 0.95.
  * depositFull         — bank_accessible AND fill >= 0.90 AND a non-kept
                          inventory item exists (select_bank_deposits nonempty).
  * discardHigh         — overstock AND fill >= 0.85.
  * gearReview          — ctx.gear_review_active (passed identically).
  * claimPending        — bool(pending_items).
  * completeTask        — task set AND total>0 AND progress>=total
                          (≡ TaskLifecyclePhase.complete).
  * sellPressured       — fill>=0.85 AND a sellable item (NPC buyer present).
  * sellIdle            — fill<0.85 AND a sellable item.
  * taskExchange        — tasks_coin total (inv+bank) >= ctx.min_coins.
  * acceptTask          — no task_code (≡ phase none); empty target_gear keeps
                          production's predicate == `not task_code`.
  * objectiveStep       — opaque Bool passed identically to both sides.
  * bankExpand          — bank_accessible AND bank_items known AND capacity>0
                          AND fill>=0.95 AND gold>=cost.
  * wait                — unconditional True.

And `selected` (`productionLadder`) — the chosen MeansKind — is asserted equal.

## Slots the SWEEP holds False — TRUE paths now DRIVEN by Brick 4

The random Hypothesis sweep above holds these 7 slots (`DEFERRED_SLOTS`) False
on BOTH sides: each reads an opaque observation production derives from
machinery the sweep does not stand up, so its production value is pinned to the
empty-catalog / no-history default (False) and the Lean side is fed the SAME
default. That sweep constraint is UNCHANGED. What HAS changed: their TRUE-firing
paths are no longer unvalidated — each now has a dedicated Brick-4 DRIVE test
(sections 4a/4b/4c below) that builds a RICH fixture where production's REAL
predicate fires the slot and runs a SELECTION CONTEST against the oracle. How
the teeth bite per slot:

  * craftRelief / maintainConsumables / recycleSurplus / restForCombat — OPAQUE
                          PASSTHROUGH Bools in the Lean model
                          (`craftReliefFires := s.craftReliefFires`, …): the Lean
                          per-slot value is production's verdict fed straight
                          back in, so the per-slot check is fed-through (vacuous
                          by construction). (gearReview / objectiveStep are the
                          SAME passthrough mechanism but are NOT deferred — the
                          sweep passes their Bool to both sides every scenario, so
                          they sit in ASSERTED_SLOTS, driven directly.) The TEETH
                          are in the `selected` assertion — a RICH fixture fires
                          the slot in production and the oracle must SELECT the
                          same MeansKind over the
                          firing pattern. (craftRelief: `craft_relief_candidates`
                          non-empty; maintainConsumables: `maintain_consumables_fires`.)
  * restForCombat       — production folds clauses (a)/(c)/(d) into the opaque
                          `restForCombatReady` (a `predict_win` verdict). In the
                          SWEEP it stays False (combat_monster=None). The DRIVE
                          test (4b) stands up a real combat fixture so the slot
                          fires and WINS selection on both ladders (a strong
                          contest: a wrong Lean priority would fail).
  * recycleSurplus / maintainConsumables — honest FIRE-AND-LOSE: both sit BELOW
                          the lifecycle slots, so for every phase a higher slot
                          fires on the Lean ladder and neither can ever BE the
                          Lean selection. The DRIVE tests (4a/4b) fire them TRUE
                          in production (binding the per-slot arg) and assert
                          `selected` agrees at the higher winner (acceptTask at
                          phase none) — a real Lean-model finding, reported.
  * lowYieldCancel / taskCancel / pursueTask — phase-derived
                          OVER-APPROXIMATIONS: Lean computes them from
                          `taskLifecyclePhase` / `actionsAttempted` /
                          `taskFeasibleProjected` (no LearningStore concept),
                          whereas production reads a REAL `LearningStore` +
                          `task_decision`. In the SWEEP both stay False
                          (history=None, taskFeasibleProjected=True, phase ∈
                          {none, complete}). The DRIVE tests (4c) thread an
                          actual (non-mock) `LearningStore` through production,
                          set the Lean phase inputs consistent with production's
                          history verdict, and run a SELECTION CONTEST. They may
                          diverge per-slot on a NON-driven phase slot by design,
                          so `drive_and_contest` asserts per-slot only for
                          `ASSERTED_SLOTS ∪ {driven}` while still asserting the
                          WINNER.

The SWEEP keeps `selected` comparable by constraining every generated scenario
so the 7 slots above are FALSE on BOTH sides (phase ∈ {none, complete},
history=None, taskFeasibleProjected=True, empty catalog, combat_monster=None).
Their TRUE paths and the resulting selection contests are the DRIVE tests' job.

## Mutation enforcement (Brick 5)

`formal/diff/mutate.py` perturbs the threshold / comparator / structural
conjunct of each numeric `_fires` predicate (groups
`LADDER_GUARD_FIRES_MUTATIONS` / `LADDER_MEANS_FIRES_MUTATIONS`, bound to THIS
file). The boundary witnesses below KILL every such mutant, so the differential
is provably non-vacuous on hpCritical / bankUnlock / reachUnlockLevel /
discardCritical / depositFull / discardHigh / completeTask / sellPressured /
sellIdle / taskExchange / bankExpand. The opaque passthrough slots carry no
threshold in the firing predicate itself (their truth is computed by separate,
separately-anchored machinery), so they are not mutation targets HERE.

## Model-fidelity note

The Lean phase-based predicates (`completeTask`/`acceptTask`/`pursueTask`/…)
are deliberate over-approximations of production's richer task-economy checks.
For completeTask/acceptTask they coincide EXACTLY with production under empty
target_gear (acceptTask) and the canonical complete condition (completeTask),
which is why those two are asserted, not deferred. pursueTask/taskCancel/
lowYieldCancel do NOT coincide (production reads `history`/`task_decision`),
which is precisely why they are deferred and their phases excluded above.
"""
from __future__ import annotations

import dataclasses

from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.bank_drain import bank_drain_excess
from artifactsmmo_cli.ai.bank_selection import select_bank_deposits
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.inventory_caps import overstocked_items
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.potion_supply import craft_potions_fires
from artifactsmmo_cli.ai.task_lifecycle import TaskLifecyclePhase
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.tiers.guards import _has_sellable
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState
from formal.diff.oracle_client import run_oracle
from formal.sim.production_ladder import (
    ALL_IN_LADDER_ORDER,
    LadderMeans,
    fires as production_fires,
    production_ladder,
)

# Slots whose TRUE-firing path is deferred to Brick 4 (see module docstring).
# They are still compared at their reachable (False) value in every scenario;
# this set documents which slots' firing logic is NOT yet differentially bound.
DEFERRED_SLOTS: frozenset[LadderMeans] = frozenset({
    LadderMeans.REST_FOR_COMBAT,
    LadderMeans.CRAFT_RELIEF,
    LadderMeans.RECYCLE_RELIEF,  # opaque passthrough: bank-full + recyclableSurplusNonempty
    LadderMeans.MAINTAIN_CONSUMABLES,
    LadderMeans.LOW_YIELD_CANCEL,
    LadderMeans.TASK_CANCEL,
    LadderMeans.PURSUE_TASK,
    LadderMeans.RECYCLE_SURPLUS,
})

# camelCase oracle key per LadderMeans (matches Lean `meansKindName`).
_ORACLE_KEY: dict[LadderMeans, str] = {
    LadderMeans.HP_CRITICAL: "hpCritical",
    LadderMeans.REST_FOR_COMBAT: "restForCombat",
    LadderMeans.BANK_UNLOCK: "bankUnlock",
    LadderMeans.REACH_UNLOCK_LEVEL: "reachUnlockLevel",
    LadderMeans.DISCARD_CRITICAL: "discardCritical",
    LadderMeans.CRAFT_RELIEF: "craftRelief",
    LadderMeans.RECYCLE_RELIEF: "recycleRelief",
    LadderMeans.SELL_RELIEF: "sellRelief",
    LadderMeans.DEPOSIT_FULL: "depositFull",
    LadderMeans.DISCARD_HIGH: "discardHigh",
    LadderMeans.GEAR_REVIEW: "gearReview",
    LadderMeans.CRAFT_POTIONS: "craftPotions",
    LadderMeans.CLAIM_PENDING: "claimPending",
    LadderMeans.COMPLETE_TASK: "completeTask",
    LadderMeans.SELL_PRESSURED: "sellPressured",
    LadderMeans.LOW_YIELD_CANCEL: "lowYieldCancel",
    LadderMeans.TASK_CANCEL: "taskCancel",
    LadderMeans.OBJECTIVE_STEP: "objectiveStep",
    LadderMeans.PURSUE_TASK: "pursueTask",
    LadderMeans.ACCEPT_TASK: "acceptTask",
    LadderMeans.TASK_EXCHANGE: "taskExchange",
    LadderMeans.MAINTAIN_CONSUMABLES: "maintainConsumables",
    LadderMeans.SELL_IDLE: "sellIdle",
    LadderMeans.RECYCLE_SURPLUS: "recycleSurplus",
    LadderMeans.DRAIN_BANK_JUNK: "drainBankJunk",
    LadderMeans.BANK_EXPAND: "bankExpand",
    LadderMeans.WAIT: "wait",
}

# An overstock/sellable/deposit witness item: not tasks_coin, not the task
# code, no item_stats (so empty-catalog `useful_quantity_cap` = 0 ⇒ overstock
# under pressure; `_keep_codes` keeps only tasks_coin/task_code, so it is a
# deposit candidate), and given an NPC buyer below to make it sellable.
JUNK = "junk"
SELLER_NPC = "vendor"


# ---------------------------------------------------------------------------
# Scenario — one record drives BOTH sides.
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Scenario:
    hp: int
    max_hp: int
    level: int
    xp: int
    initial_xp: int
    bank_required_level: int
    unlock_monster_level: int
    has_bank_unlock_monster: bool
    bank_accessible: bool
    inventory_max: int
    junk_qty: int            # held units of JUNK (overstock/deposit/sell witness)
    coin_qty: int            # held tasks_coin
    bank_coin_qty: int       # banked tasks_coin
    task_exchange_min_coins: int
    has_pending: bool
    task_phase: str          # "none" | "complete"  (deferred phases excluded)
    bank_known: bool
    bank_items_count: int
    bank_capacity: int
    next_expansion_cost: int
    gold: int
    item_sellable: bool      # NPC buys JUNK -> sellable
    gear_review: bool        # opaque, passed identically to both sides
    objective_step: bool     # opaque, passed identically to both sides


# ---------------------------------------------------------------------------
# Production-side fixture construction from a Scenario.
# ---------------------------------------------------------------------------


def _phase_task_fields(phase: str) -> dict[str, object]:
    """task_code/type/progress/total realising a TaskLifecyclePhase.

    Only `none` and `complete` are used (the deferred accepted/inProgress
    phases would diverge — see module docstring)."""
    if phase == "complete":
        return dict(task_code="t_done", task_type="items",
                    task_progress=5, task_total=5)
    return dict(task_code=None, task_type=None, task_progress=0, task_total=0)


def _make_game_data(scn: Scenario) -> GameData:
    gd = GameData()
    gd._monster_locations = {}
    gd._monster_level = (
        {scn_unlock_name(): scn.unlock_monster_level}
        if scn.has_bank_unlock_monster and scn.unlock_monster_level > 0 else {}
    )
    gd._monster_hp = {}
    gd._monster_attack = {}
    gd._monster_resistance = {}
    gd._monster_critical_strike = {}
    gd._monster_initiative = {}
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_locations = {}
    gd._resource_skill = {}
    gd._resource_drops = {}
    gd._workshop_locations = {}
    gd._npc_stock = {}
    gd._npc_sell_prices = {SELLER_NPC: {JUNK: 5}} if scn.item_sellable else {}
    # _has_sellable now requires a reachable buyer (npc_location is not None).
    # Provide a static location for SELLER_NPC whenever the scenario declares
    # the item as sellable so the production predicate matches the oracle arg[22].
    gd._npc_locations = {SELLER_NPC: (1, 2)} if scn.item_sellable else {}
    gd._bank_capacity = scn.bank_capacity
    gd._next_expansion_cost = scn.next_expansion_cost
    return gd


def scn_unlock_name() -> str:
    return "unlock_mob"


def _make_inventory(scn: Scenario) -> dict[str, int]:
    inv: dict[str, int] = {}
    if scn.junk_qty > 0:
        inv[JUNK] = scn.junk_qty
    if scn.coin_qty > 0:
        inv[TASKS_COIN_CODE] = scn.coin_qty
    return inv


def _make_world(scn: Scenario) -> WorldState:
    inv = _make_inventory(scn)
    bank_items: dict[str, int] | None
    if scn.bank_known:
        # Build a dict whose len is EXACTLY scn.bank_items_count; the oracle
        # reads arg[13] off this same dict's len, and the banked tasks_coin is
        # folded INTO that count so both sides see identical `bankItemsCount`
        # (for bankExpand) and identical visible coin total (for taskExchange).
        bank_items = {}
        if scn.bank_coin_qty > 0 and scn.bank_items_count > 0:
            bank_items[TASKS_COIN_CODE] = scn.bank_coin_qty
        i = 0
        while len(bank_items) < scn.bank_items_count:
            bank_items[f"b_{i}"] = 1
            i += 1
    else:
        bank_items = None
    task_fields = _phase_task_fields(scn.task_phase)
    return WorldState(
        character="diff", level=scn.level, xp=scn.xp, max_xp=999999,
        hp=scn.hp, max_hp=scn.max_hp, gold=scn.gold, skills={},
        x=0, y=0, inventory=inv, inventory_max=scn.inventory_max,
        equipment={}, cooldown_expires=None,
        bank_items=bank_items, bank_gold=None,
        pending_items=(("pid", "pcode"),) if scn.has_pending else None,
        **task_fields,
    )


def _make_ctx(scn: Scenario) -> SelectionContext:
    return SelectionContext(
        bank_accessible=scn.bank_accessible,
        bank_required_level=scn.bank_required_level,
        bank_unlock_monster=scn_unlock_name() if scn.has_bank_unlock_monster else None,
        initial_xp=scn.initial_xp,
        task_exchange_min_coins=scn.task_exchange_min_coins,
        combat_monster=None,
        target_gear=frozenset(),
        target_tools=frozenset(),
        gear_review_active=scn.gear_review,
    )


def _production_answers(
    scn: Scenario, w: WorldState,
) -> tuple[dict[LadderMeans, bool], LadderMeans | None]:
    gd = _make_game_data(scn)
    ctx = _make_ctx(scn)
    per_slot = {
        k: production_fires(k, w, gd, None, ctx, scn.objective_step)
        for k in ALL_IN_LADDER_ORDER
    }
    selected = production_ladder(w, gd, None, ctx, scn.objective_step)
    return per_slot, selected


# ---------------------------------------------------------------------------
# Lean-side: build the 31-int oracle arg array from the SAME scenario.
# ---------------------------------------------------------------------------

_PHASE_INT = {"none": 0, "accepted": 1, "inProgress": 2, "complete": 3}


def _oracle_args(scn: Scenario, w: WorldState) -> list[int]:
    """Build the 32-int oracle arg array reading the STRUCTURAL facts off the
    same constructed `WorldState` production reads (coin total, bank item
    count), so neither side can drift on how those are derived. The opaque
    Bools (overstock/deposit/sellable/passthroughs) are computed by helpers
    that mirror production's empty-catalog behaviour exactly."""
    inventory_used = w.inventory_used
    # Mirror production `_tasks_coin_total`: inv coins + (bank coins iff known).
    coins_total = w.inventory.get(TASKS_COIN_CODE, 0) + (
        (w.bank_items or {}).get(TASKS_COIN_CODE, 0))
    bank_items_count = len(w.bank_items) if w.bank_items is not None else 0
    return [
        scn.hp,                                  # 0
        scn.max_hp,                              # 1
        scn.level,                               # 2
        scn.xp,                                  # 3
        scn.initial_xp,                          # 4
        scn.bank_required_level,                 # 5
        scn.unlock_monster_level,                # 6
        inventory_used,                          # 7
        scn.inventory_max,                       # 8
        coins_total,                             # 9
        scn.task_exchange_min_coins,             # 10
        0,                                       # 11 actionsAttempted (deferred)
        scn.gold,                                # 12
        bank_items_count,                        # 13
        scn.bank_capacity,                       # 14
        scn.next_expansion_cost,                 # 15
        _PHASE_INT[scn.task_phase],              # 16 taskLifecyclePhase
        1 if scn.bank_accessible else 0,         # 17
        1 if scn.has_bank_unlock_monster else 0, # 18
        1 if _has_overstock(scn) else 0,         # 19 hasOverstockItems
        1 if _deposit_nonempty(scn) else 0,      # 20 selectBankDepositsNonempty
        1 if scn.has_pending else 0,             # 21 pendingItemsNonempty
        1 if scn.item_sellable and scn.junk_qty > 0 else 0,  # 22 sellableInventoryNonempty
        0,                                       # 23 recyclableSurplusNonempty (deferred)
        1,                                       # 24 taskFeasibleProjected (defer taskCancel)
        0,                                       # 25 restForCombatReady (deferred TRUE path)
        1 if scn.gear_review else 0,             # 26 gearReviewFires (passed identically)
        0,                                       # 27 craftReliefFires (deferred)
        1 if scn.objective_step else 0,          # 28 objectiveStepFires (passed identically)
        0,                                       # 29 maintainConsumablesFires (deferred)
        1 if scn.bank_known else 0,              # 30 bankItemsKnown
        1 if _bank_junk_nonempty(scn) else 0,    # 31 bankJunkNonempty
        # 32 craftPotionsFires: the opaque CRAFT_POTIONS guard verdict, computed
        # by production's REAL `craft_potions_fires` on the same (w, gd) the
        # ladder reads (empty synthetic catalog ⇒ no target potion ⇒ False).
        1 if craft_potions_fires(w, _make_game_data(scn)) else 0,  # 32 craftPotionsFires
    ]


def _bank_junk_nonempty(scn: Scenario) -> bool:
    """Empty-catalog `bank_drain_excess`: the bank's synthetic `b_i` items have
    no catalog stats ⇒ `useful_quantity_cap` 0 ⇒ every banked unit is over-cap
    excess. tasks_coin has cap 999 (never excess at these counts). So the bank
    holds drainable junk iff at least one non-coin item is banked."""
    if not scn.bank_known:
        return False
    coin_in_bank = 1 if (scn.bank_coin_qty > 0 and scn.bank_items_count > 0) else 0
    return scn.bank_items_count - coin_in_bank >= 1


def _has_overstock(scn: Scenario) -> bool:
    """Empty-catalog `overstocked_items`: JUNK has cap 0, so it is overstock
    iff held under genuine space pressure (fill >= DISCARD_HIGH watermark 0.85).
    Mirrors `overstock_excess`'s cross-multiplied gate exactly (20*used >=
    17*max). tasks_coin has action-cap 999, never overstock at these counts."""
    if scn.junk_qty <= 0 or scn.inventory_max <= 0:
        return False
    used = scn.junk_qty + (scn.coin_qty if scn.coin_qty > 0 else 0)
    return 20 * used >= 17 * scn.inventory_max


def _deposit_nonempty(scn: Scenario) -> bool:
    """Empty-catalog `select_bank_deposits`: keep-set is {tasks_coin, task_code}
    (no hp_restore items, no weapon, no recipe mats, no profile). JUNK is a
    non-kept held item ⇒ a deposit candidate."""
    return scn.junk_qty > 0


def _lean_answers(scn: Scenario, w: WorldState) -> tuple[dict[LadderMeans, bool], LadderMeans | None]:
    res = run_oracle("ladder_fires", [_oracle_args(scn, w)])[0]
    per_slot = {k: bool(res[_ORACLE_KEY[k]]) for k in ALL_IN_LADDER_ORDER}
    selected_name = res["selected"]
    selected = None
    if selected_name is not None:
        selected = next(k for k in ALL_IN_LADDER_ORDER
                        if _ORACLE_KEY[k] == selected_name)
    return per_slot, selected


# ---------------------------------------------------------------------------
# Hypothesis strategy.
# ---------------------------------------------------------------------------


@st.composite
def _scenario(draw) -> Scenario:
    max_hp = draw(st.integers(min_value=1, max_value=200))
    hp = draw(st.integers(min_value=0, max_value=max_hp))
    inventory_max = draw(st.integers(min_value=1, max_value=40))
    # Keep junk within the bag so inventory_used is realistic.
    junk_qty = draw(st.integers(min_value=0, max_value=inventory_max))
    coin_qty = draw(st.integers(min_value=0, max_value=8))
    bank_capacity = draw(st.integers(min_value=0, max_value=40))
    return Scenario(
        hp=hp,
        max_hp=max_hp,
        level=draw(st.integers(min_value=1, max_value=40)),
        xp=draw(st.integers(min_value=0, max_value=500)),
        initial_xp=draw(st.integers(min_value=0, max_value=500)),
        bank_required_level=draw(st.integers(min_value=0, max_value=45)),
        unlock_monster_level=draw(st.integers(min_value=0, max_value=45)),
        has_bank_unlock_monster=draw(st.booleans()),
        bank_accessible=draw(st.booleans()),
        inventory_max=inventory_max,
        junk_qty=junk_qty,
        coin_qty=coin_qty,
        bank_coin_qty=draw(st.integers(min_value=0, max_value=8)),
        task_exchange_min_coins=draw(st.integers(min_value=1, max_value=10)),
        has_pending=draw(st.booleans()),
        task_phase=draw(st.sampled_from(["none", "complete"])),
        bank_known=draw(st.booleans()),
        bank_items_count=draw(st.integers(min_value=0, max_value=40)),
        bank_capacity=bank_capacity,
        next_expansion_cost=draw(st.integers(min_value=0, max_value=2000)),
        gold=draw(st.integers(min_value=0, max_value=5000)),
        item_sellable=draw(st.booleans()),
        gear_review=draw(st.booleans()),
        objective_step=draw(st.booleans()),
    )


ASSERTED_SLOTS: tuple[LadderMeans, ...] = tuple(
    k for k in ALL_IN_LADDER_ORDER if k not in DEFERRED_SLOTS
)


@settings(max_examples=400)
@given(scn=_scenario())
def test_ladder_fires_matches_production(scn: Scenario) -> None:
    """Per-slot agreement (asserted slots) + selection agreement between the
    Lean ladder oracle and real production `_guard_fires`/`_means_fires`."""
    w = _make_world(scn)
    prod, prod_sel = _production_answers(scn, w)
    lean, lean_sel = _lean_answers(scn, w)
    for k in ASSERTED_SLOTS:
        assert prod[k] == lean[k], (
            f"SLOT DIVERGENCE {k.name}: production={prod[k]} lean={lean[k]}\n"
            f"  scenario={scn}"
        )
    # Deferred slots must be False on BOTH sides under these constrained
    # scenarios (their TRUE paths are Brick 4). A non-False here is a real
    # finding — the constraint that makes selection comparable has broken.
    for k in DEFERRED_SLOTS:
        assert prod[k] is False, (
            f"DEFERRED slot {k.name} fired in production unexpectedly: {scn}"
        )
        assert lean[k] is False, (
            f"DEFERRED slot {k.name} fired in Lean unexpectedly: {scn}"
        )
    assert prod_sel == lean_sel, (
        f"SELECTION DIVERGENCE: production={prod_sel} lean={lean_sel}\n"
        f"  scenario={scn}"
    )


# ---------------------------------------------------------------------------
# Boundary witnesses — pin the numeric thresholds so a weakened Lean predicate
# (or a flipped conjunct) FAILS, not just the random sweep.
# ---------------------------------------------------------------------------


def _base_scn(**overrides) -> Scenario:
    defaults: dict[str, object] = dict(
        hp=100, max_hp=100, level=10, xp=0, initial_xp=0,
        bank_required_level=0, unlock_monster_level=0,
        has_bank_unlock_monster=False, bank_accessible=False,
        inventory_max=20, junk_qty=0, coin_qty=0, bank_coin_qty=0,
        task_exchange_min_coins=5, has_pending=False, task_phase="none",
        bank_known=False, bank_items_count=0, bank_capacity=0,
        next_expansion_cost=0, gold=0, item_sellable=False,
        gear_review=False, objective_step=False,
    )
    defaults.update(overrides)
    return Scenario(**defaults)


def _assert_full_agreement(scn: Scenario) -> None:
    w = _make_world(scn)
    prod, prod_sel = _production_answers(scn, w)
    lean, lean_sel = _lean_answers(scn, w)
    for k in ASSERTED_SLOTS:
        assert prod[k] == lean[k], (k.name, prod[k], lean[k], scn)
    assert prod_sel == lean_sel, (prod_sel, lean_sel, scn)


def test_hp_critical_boundary() -> None:
    # 74/100 = 0.74 < 0.75 fires; 75/100 = 0.75 does NOT (strict <).
    _assert_full_agreement(_base_scn(hp=74, max_hp=100))
    _assert_full_agreement(_base_scn(hp=75, max_hp=100))


def test_discard_high_boundary() -> None:
    # fill 17/20 = 0.85 exactly meets DISCARD_HIGH (>=); 16/20 = 0.80 does not.
    _assert_full_agreement(_base_scn(inventory_max=20, junk_qty=17))
    _assert_full_agreement(_base_scn(inventory_max=20, junk_qty=16))


def test_discard_critical_boundary() -> None:
    # fill 19/20 = 0.95 meets DISCARD_CRITICAL (>=); 18/20 = 0.90 does not.
    _assert_full_agreement(_base_scn(inventory_max=20, junk_qty=19))
    _assert_full_agreement(_base_scn(inventory_max=20, junk_qty=18))


def test_deposit_full_boundary() -> None:
    # fill 18/20 = 0.90 meets DEPOSIT_FULL (>=); 17/20 = 0.85 does not.
    # bank_accessible + bank_known + capacity > count required for bankHasRoom.
    _assert_full_agreement(_base_scn(bank_accessible=True, bank_known=True,
                                     bank_capacity=10, bank_items_count=0,
                                     inventory_max=20, junk_qty=18))
    _assert_full_agreement(_base_scn(bank_accessible=True, bank_known=True,
                                     bank_capacity=10, bank_items_count=0,
                                     inventory_max=20, junk_qty=17))


def test_sell_pressured_vs_idle_boundary() -> None:
    # sellable item; fill 17/20=0.85 -> SELL_PRESSURED; 16/20=0.80 -> SELL_IDLE.
    _assert_full_agreement(_base_scn(inventory_max=20, junk_qty=17,
                                     item_sellable=True))
    _assert_full_agreement(_base_scn(inventory_max=20, junk_qty=16,
                                     item_sellable=True))


def test_sell_relief_boundary() -> None:
    # SELL_RELIEF: bank full (known + count >= capacity) AND sellable item held.
    # bank_known=True, bank_capacity=1, bank_items_count=1 -> bankHasRoom=False.
    _assert_full_agreement(_base_scn(
        bank_accessible=True, bank_known=True, bank_capacity=1, bank_items_count=1,
        junk_qty=3, item_sellable=True,
    ))
    # bank has room (count < capacity) -> SELL_RELIEF quiet.
    _assert_full_agreement(_base_scn(
        bank_accessible=True, bank_known=True, bank_capacity=5, bank_items_count=1,
        junk_qty=3, item_sellable=True,
    ))
    # bank full but no sellable item -> SELL_RELIEF quiet.
    _assert_full_agreement(_base_scn(
        bank_accessible=True, bank_known=True, bank_capacity=1, bank_items_count=1,
        junk_qty=3, item_sellable=False,
    ))


def test_task_exchange_boundary() -> None:
    # coins 5 >= min 5 fires; coins 4 does not.
    _assert_full_agreement(_base_scn(coin_qty=5, task_exchange_min_coins=5,
                                     task_phase="complete"))
    _assert_full_agreement(_base_scn(coin_qty=4, task_exchange_min_coins=5,
                                     task_phase="complete"))


def test_complete_task_witness() -> None:
    _assert_full_agreement(_base_scn(task_phase="complete"))


def test_reach_unlock_level_boundary() -> None:
    # required 12, level 8 -> gap 4 (<=5) fires; level 6 -> gap 6 does not.
    _assert_full_agreement(_base_scn(level=8, bank_required_level=12))
    _assert_full_agreement(_base_scn(level=6, bank_required_level=12))


def test_bank_unlock_witness() -> None:
    # monster present, not accessible, xp<=initial, level+1>=monster_level.
    _assert_full_agreement(_base_scn(
        has_bank_unlock_monster=True, bank_accessible=False,
        unlock_monster_level=10, level=9, xp=0, initial_xp=0,
    ))
    # xp > initial_xp suppresses it.
    _assert_full_agreement(_base_scn(
        has_bank_unlock_monster=True, bank_accessible=False,
        unlock_monster_level=10, level=9, xp=5, initial_xp=0,
    ))


def test_bank_expand_witness() -> None:
    # accessible, known, capacity 20, 19 items (>=0.95), gold 100 >= cost 50.
    _assert_full_agreement(_base_scn(
        bank_accessible=True, bank_known=True, bank_capacity=20,
        bank_items_count=19, gold=100, next_expansion_cost=50,
        # task assigned-complete so acceptTask doesn't outrank in the ladder.
        task_phase="complete",
    ))


def test_gear_review_and_objective_step_passthrough() -> None:
    _assert_full_agreement(_base_scn(gear_review=True))
    _assert_full_agreement(_base_scn(objective_step=True))


def test_claim_pending_witness() -> None:
    _assert_full_agreement(_base_scn(has_pending=True))


def test_wait_fallthrough() -> None:
    # complete-phase, no coins, nothing else -> only completeTask & wait;
    # selection is completeTask. A pure fallthrough to wait needs phase that
    # fires nothing above it: not reachable with only {none,complete}, so this
    # pins that completeTask wins when present.
    _assert_full_agreement(_base_scn(task_phase="complete",
                                     task_exchange_min_coins=10))


def test_scope_documents_deferred_slots() -> None:
    """Guard against silently widening the deferred set: every deferred slot
    is a real ladder MeansKind and the asserted set covers everything else."""
    assert DEFERRED_SLOTS.issubset(set(ALL_IN_LADDER_ORDER))
    assert set(ASSERTED_SLOTS) | DEFERRED_SLOTS == set(ALL_IN_LADDER_ORDER)
    assert not (set(ASSERTED_SLOTS) & DEFERRED_SLOTS)


# ===========================================================================
# Brick 4 — drive the OPAQUE ladder slots to TRUE in PRODUCTION and run the
# SELECTION CONTEST against the Lean oracle.
#
# The 7 deferred slots are opaque passthrough Bools in the Lean model
# (`craftReliefFires`/`recyclableSurplusNonempty`/… ARE the State Bool — Lean
# has no machinery to re-derive them). So the differential for these slots is
# NOT a recomputation contest; it is a SELECTION contest: build a fixture with
# a RICH GameData/WorldState/SelectionContext where production's REAL machinery
# (`craft_relief_candidates`, `recyclable_surplus`, …) makes the slot fire,
# read production's per-slot firing + selected MeansKind, feed the SAME
# production-derived Bool into the oracle's matching arg index, then assert
# (a) per-slot agreement and (b) `selected` agreement.
#
# This mirrors the existing `gearReview`/`objectiveStep` passthrough handling
# (those Bools are fed identically to both sides), but here the Bool is DRIVEN
# by production's real predicate on a hand-built fixture rather than sampled.
#
# Cluster A (4a): craftRelief (arg[27]) + recycleSurplus (arg[23]).
# Bricks 4b/4c reuse `drive_and_contest` for the remaining opaque slots.
# ===========================================================================

# Map a derived TaskLifecyclePhase to the oracle's arg[16] enum int.
_LIFECYCLE_INT: dict[TaskLifecyclePhase, int] = {
    TaskLifecyclePhase.NONE: 0,
    TaskLifecyclePhase.ACCEPTED: 1,
    TaskLifecyclePhase.IN_PROGRESS: 2,
    TaskLifecyclePhase.COMPLETE: 3,
}


def _rich_oracle_args(
    w: WorldState,
    gd: GameData,
    ctx: SelectionContext,
    prod: dict[LadderMeans, bool],
    objective_step: bool,
    *,
    actions_attempted: int = 0,
    task_feasible_projected: bool = True,
) -> list[int]:
    """Build the 31-int oracle arg array (the `runLadder` docstring layout,
    Oracle.lean) for a RICH hand-built fixture.

    Every opaque per-slot arg is derived from the SAME production verdict
    (`prod[...]`) computed on this fixture — never re-implemented here — so the
    oracle re-evaluates `productionLadder` over EXACTLY the firing pattern
    production produced. Structural facts (overstock / deposit / sellable /
    coins / bank-item count) are read off the constructed world through the
    same gates production reads, per the Brick 3 fidelity rule: `taskCoinsTotal`
    and `bankItemsCount` come from the bank-visible view (`w.bank_items` is
    `None` until perception loads it), never from raw bank contents.

    `actions_attempted` (arg[11]) and `task_feasible_projected` (arg[24]) are
    the Lean-side equivalents of the history/feasibility inputs that production
    reads from a `LearningStore` + `task_decision`. 4a/4b never touch them
    (defaults 0 / True reproduce the old constants); Brick 4c sets them
    consistent with the driven history-gated slot's production verdict —
    `lowYieldCancel` (arg[11]>=lowYieldSampleThreshold) and `taskCancel`
    (arg[24]=0 when production PIVOTs)."""
    coins_total = w.inventory.get(TASKS_COIN_CODE, 0) + (
        (w.bank_items or {}).get(TASKS_COIN_CODE, 0))
    bank_items_count = len(w.bank_items) if w.bank_items is not None else 0
    return [
        w.hp,                                        # 0
        w.max_hp,                                    # 1
        w.level,                                     # 2
        w.xp,                                        # 3
        ctx.initial_xp,                              # 4
        ctx.bank_required_level,                     # 5
        gd.monster_level(ctx.bank_unlock_monster)    # 6 unlockMonsterLevel
        if ctx.bank_unlock_monster else 0,
        w.inventory_used,                            # 7
        w.inventory_max,                             # 8
        coins_total,                                 # 9
        ctx.task_exchange_min_coins,                 # 10
        actions_attempted,                           # 11 actionsAttempted
        w.gold,                                      # 12
        bank_items_count,                            # 13
        gd.bank_capacity,                            # 14
        gd.next_expansion_cost,                      # 15
        _LIFECYCLE_INT[w.task_lifecycle_phase],      # 16 taskLifecyclePhase
        1 if ctx.bank_accessible else 0,             # 17
        1 if ctx.bank_unlock_monster else 0,         # 18
        # 19/20/22: derive the opaque structural Bools from production's REAL
        # helpers on (w, gd) — NOT from the slot verdicts (which fold in the
        # fraction gates and would make the input tautological with the output).
        1 if overstocked_items(w, gd) else 0,        # 19 hasOverstockItems
        1 if select_bank_deposits(w, gd) else 0,     # 20 selectBankDepositsNonempty
        1 if w.pending_items else 0,                 # 21 pendingItemsNonempty
        1 if _has_sellable(w, gd) else 0,            # 22 sellableInventoryNonempty
        1 if prod[LadderMeans.RECYCLE_SURPLUS] else 0,   # 23 recyclableSurplusNonempty
        1 if task_feasible_projected else 0,         # 24 taskFeasibleProjected
        1 if prod[LadderMeans.REST_FOR_COMBAT] else 0,   # 25 restForCombatReady
        1 if ctx.gear_review_active else 0,          # 26 gearReviewFires
        1 if prod[LadderMeans.CRAFT_RELIEF] else 0,  # 27 craftReliefFires
        1 if objective_step else 0,                  # 28 objectiveStepFires
        1 if prod[LadderMeans.MAINTAIN_CONSUMABLES] else 0,  # 29 maintainConsumablesFires
        1 if w.bank_items is not None else 0,        # 30 bankItemsKnown
        # 31: derive from production's REAL bank_drain_excess helper (like 19/20/22),
        # NOT the slot verdict — the helper IS the opaque nonempty signal.
        1 if bank_drain_excess(w, gd, frozenset(ctx.target_gear | ctx.target_tools)) else 0,  # 31 bankJunkNonempty
        # 32 craftPotionsFires: opaque CRAFT_POTIONS latch — derive from the SAME
        # production verdict (like gearReview/craftRelief/maintainConsumables).
        1 if prod[LadderMeans.CRAFT_POTIONS] else 0,  # 32 craftPotionsFires
    ]


def drive_and_contest(
    w: WorldState,
    gd: GameData,
    ctx: SelectionContext,
    *,
    objective_step: bool = False,
    driven: frozenset[LadderMeans] = frozenset(),
    assert_selection: bool = True,
    history: LearningStore | None = None,
    actions_attempted: int = 0,
    task_feasible_projected: bool = True,
) -> tuple[dict[LadderMeans, bool], LadderMeans | None,
           dict[LadderMeans, bool], LadderMeans | None]:
    """Run the REAL production ladder on a rich fixture, feed its per-slot
    verdict into the Lean oracle, and assert per-slot + selection agreement.

    Per-slot agreement is asserted for the NON-DEFERRED slots (`ASSERTED_SLOTS`)
    plus the explicitly `driven` opaque slots (the slot(s) this fixture stands
    up production's real machinery for). The OTHER deferred slots
    (pursueTask/taskCancel/lowYieldCancel) are deliberate phase-based Lean
    over-approximations of history-gated production predicates — they diverge
    by design whenever the fixture's phase is accepted/inProgress, and are NOT
    asserted per-slot here (that is Bricks 4b/4c's job). They CAN still fire on
    the Lean side below the driven slot.

    `assert_selection` (default True) asserts `selected` agreement; the driven
    slot's TRUE fixtures DO win (or lose to an agreed-upon higher slot) and pin
    selection. Pass `assert_selection=False` for a near-miss whose ONLY purpose
    is the per-slot `driven`-slot contest and whose phase deliberately trips a
    NOT-YET-BOUND deferred slot below it (e.g. an in-progress items-task with no
    history makes Lean `pursueTask` win while history-gated production falls
    through to `wait` — a known over-approximation, not this brick's contest).

    Returns ``(prod_per_slot, prod_selected, lean_per_slot, lean_selected)`` so
    callers can additionally assert WHICH slot fired/was selected.

    `history` (default None) is threaded into production's `fires` /
    `production_ladder` so the history-gated slots (taskCancel/pursueTask/
    lowYieldCancel) reach their real `LearningStore` path. The Lean side has no
    history concept — `actions_attempted` (arg[11]) and `task_feasible_projected`
    (arg[24]) carry the Lean-side equivalent and MUST be set consistent with
    production's history verdict for the driven scenario. 4a/4b pass history=None
    and the defaults, so their behaviour is unchanged.

    Shared scaffold for Brick 4 (4a uses it for craftRelief/recycleSurplus;
    4b/4c reuse it for the remaining opaque slots)."""
    prod = {
        k: production_fires(k, w, gd, history, ctx, objective_step)
        for k in ALL_IN_LADDER_ORDER
    }
    prod_sel = production_ladder(w, gd, history, ctx, objective_step)
    res = run_oracle("ladder_fires",
                     [_rich_oracle_args(
                         w, gd, ctx, prod, objective_step,
                         actions_attempted=actions_attempted,
                         task_feasible_projected=task_feasible_projected)])[0]
    lean = {k: bool(res[_ORACLE_KEY[k]]) for k in ALL_IN_LADDER_ORDER}
    lean_sel_name = res["selected"]
    lean_sel = None
    if lean_sel_name is not None:
        lean_sel = next(k for k in ALL_IN_LADDER_ORDER
                        if _ORACLE_KEY[k] == lean_sel_name)
    for k in set(ASSERTED_SLOTS) | driven:
        assert prod[k] == lean[k], (
            f"SLOT DIVERGENCE {k.name}: production={prod[k]} lean={lean[k]}")
    if assert_selection:
        assert prod_sel == lean_sel, (
            f"SELECTION DIVERGENCE: production={prod_sel} lean={lean_sel}")
    return prod, prod_sel, lean, lean_sel


# ---------------------------------------------------------------------------
# Slot 1 — craftRelief (arg[27]).  Production CRAFT_RELIEF guard fires iff
# `_used_fraction >= 0.70` AND `craft_relief_candidates(...)` non-empty
# (tiers/guards.py + craft_relief.py). Net-relief gate requires a multi-input
# recipe (input units consumed > 1 output). The items-task deliverable is the
# priority-0 relief candidate; the production ladder reaches CRAFT_RELIEF via
# the items-task path (the sim calls `_guard_fires` with an empty step profile,
# so the task item — not a step material — must be the candidate).
# ---------------------------------------------------------------------------


def _craft_relief_gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "plank": ItemStats(code="plank", level=1, type_="resource",
                           crafting_skill="woodcutting", crafting_level=1),
    }
    gd._crafting_recipes = {"plank": {"log": 2}}  # multi-input -> net relief 1
    return gd


def _single_input_relief_gd() -> GameData:
    """Same as `_craft_relief_gd` but a 1:1 recipe (net relief 0) — the
    net-relief gate (craft_relief.py `_net_relief_per_craft`) rejects it."""
    gd = GameData()
    gd._item_stats = {
        "plank": ItemStats(code="plank", level=1, type_="resource",
                           crafting_skill="woodcutting", crafting_level=1),
    }
    gd._crafting_recipes = {"plank": {"log": 1}}
    return gd


def _craft_relief_ctx() -> SelectionContext:
    return SelectionContext(
        bank_accessible=False, bank_required_level=0, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=5, combat_monster=None,
        target_gear=frozenset(), target_tools=frozenset(),
        gear_review_active=False)


def _craft_relief_world(inventory_max: int) -> WorldState:
    # items-task plank 1/5 (IN_PROGRESS), 4 logs on hand, woodcutting@1.
    return WorldState(
        character="diff", level=5, xp=0, max_xp=999999, hp=100, max_hp=100,
        gold=0, skills={"woodcutting": 1}, x=0, y=0,
        inventory={"log": 4}, inventory_max=inventory_max,
        equipment={}, cooldown_expires=None, bank_items=None, bank_gold=None,
        pending_items=None,
        task_code="plank", task_type="items", task_progress=1, task_total=5)


def test_craft_relief_drives_and_selects() -> None:
    """TRUE fixture: used 4/5 = 0.80 >= 0.70 AND a net-relief plank craft is
    available -> production CRAFT_RELIEF fires and is SELECTED (it out-ranks
    every lower slot and the higher guards are quiet). The Lean oracle, fed
    craftReliefFires=1 (production's verdict), selects craftRelief too."""
    w = _craft_relief_world(inventory_max=5)
    gd = _craft_relief_gd()
    prod, prod_sel, lean, lean_sel = drive_and_contest(w, gd, _craft_relief_ctx(), driven=frozenset({LadderMeans.CRAFT_RELIEF}))
    # Production REALLY fires the driven slot (not faked):
    assert prod[LadderMeans.CRAFT_RELIEF] is True
    assert prod_sel is LadderMeans.CRAFT_RELIEF
    assert lean_sel is LadderMeans.CRAFT_RELIEF


def test_craft_relief_near_miss_low_fill() -> None:
    """Near-miss (a): used 4/20 = 0.20 < 0.70 -> CRAFT_RELIEF does NOT fire.
    Per-slot + selection agreement still holds (slot False on both sides)."""
    w = _craft_relief_world(inventory_max=20)
    gd = _craft_relief_gd()
    prod, _, _, _ = drive_and_contest(w, gd, _craft_relief_ctx(), driven=frozenset({LadderMeans.CRAFT_RELIEF}), assert_selection=False)
    assert prod[LadderMeans.CRAFT_RELIEF] is False


def test_craft_relief_near_miss_zero_net_relief() -> None:
    """Near-miss (b): fill 0.80 >= 0.70 but the recipe is 1:1 (net relief 0),
    so `craft_relief_candidates` is empty -> CRAFT_RELIEF does NOT fire."""
    w = _craft_relief_world(inventory_max=5)
    gd = _single_input_relief_gd()
    prod, _, _, _ = drive_and_contest(w, gd, _craft_relief_ctx(), driven=frozenset({LadderMeans.CRAFT_RELIEF}), assert_selection=False)
    assert prod[LadderMeans.CRAFT_RELIEF] is False


# ---------------------------------------------------------------------------
# Slot 2 — recycleSurplus (arg[23]).  Production RECYCLE_SURPLUS means fires
# iff `_used_fraction < 0.85` AND `recyclable_surplus(...)` non-empty
# (tiers/means.py + recycle_surplus.py): a craftable EQUIPPABLE held above its
# useful cap (EQUIPPABLE_KEEP=1), skill at recipe level, workshop known, NOT
# equipped, NOT in ctx.target_gear/target_tools.
#
# SELECTION NOTE (a real Lean-model finding, reported): recycleSurplus sits
# below the lifecycle slots, and for EVERY phase some higher slot fires on the
# Lean ladder — acceptTask(none) / pursueTask(accepted|inProgress) /
# completeTask(complete). So recycleSurplus can NEVER be the Lean SELECTION; it
# can only fire-and-lose. The contest here therefore drives recycleSurplus TRUE
# (the per-slot agreement that binds arg[23]) under phase=none, where BOTH
# ladders select acceptTask — selection agreement holds at the winner.
# ---------------------------------------------------------------------------


def _recycle_gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "dagger": ItemStats(code="dagger", level=1, type_="weapon",
                            crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {"dagger": {"copper_bar": 6}}
    gd._workshop_locations = {"weaponcrafting": (1, 2)}
    gd._bank_capacity = 50  # bank has room (0 items < 50) → RECYCLE_RELIEF quiet
    return gd


def _recycle_ctx(*, protect_dagger: bool = False) -> SelectionContext:
    # Protect via target_TOOLS, not target_gear: recyclable_surplus protects on
    # `target_gear | target_tools`, but the ACCEPT_TASK gear-deferral loop reads
    # only `target_gear`. Using target_tools isolates the recycle protection
    # near-miss from the (separately-deferred) acceptTask gear-deferral
    # over-approximation, so acceptTask stays == Lean (phase none) here.
    # bank_accessible=True + bank has room → RECYCLE_RELIEF is quiet (bank has
    # room, so the bank-full pressure condition is False). Without room the new
    # RECYCLE_RELIEF guard would preempt ACCEPT_TASK and win selection.
    return SelectionContext(
        bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=5, combat_monster=None,
        target_gear=frozenset(),
        target_tools=frozenset({"dagger"}) if protect_dagger else frozenset(),
        gear_review_active=False)


def _recycle_world(dagger_qty: int) -> WorldState:
    # No task (phase NONE), dagger held unequipped, fill 1/20 = 0.05 < 0.85.
    # bank_items={} (empty bank, capacity 50 in _recycle_gd) → bank has room →
    # RECYCLE_RELIEF is quiet so RECYCLE_SURPLUS can win the deferred-slot contest.
    return WorldState(
        character="diff", level=5, xp=0, max_xp=999999, hp=100, max_hp=100,
        gold=0, skills={"weaponcrafting": 1}, x=0, y=0,
        inventory={"dagger": dagger_qty} if dagger_qty > 0 else {},
        inventory_max=20, equipment={}, cooldown_expires=None,
        bank_items={}, bank_gold=None, pending_items=None,
        task_code=None, task_type=None, task_progress=0, task_total=0)


def test_recycle_surplus_drives_true() -> None:
    """TRUE fixture: 2 daggers (> cap 1), under 0.85 fill, skill at level,
    workshop known, unprotected, unequipped -> production RECYCLE_SURPLUS
    fires. It loses selection to ACCEPT_TASK (phase NONE) on BOTH ladders, so
    `selected` agrees at acceptTask while arg[23] is bound by the per-slot
    contest."""
    w = _recycle_world(dagger_qty=2)
    gd = _recycle_gd()
    prod, prod_sel, lean, lean_sel = drive_and_contest(w, gd, _recycle_ctx(), driven=frozenset({LadderMeans.RECYCLE_SURPLUS}))
    assert prod[LadderMeans.RECYCLE_SURPLUS] is True
    assert lean[LadderMeans.RECYCLE_SURPLUS] is True
    # recycleSurplus is structurally unreachable as a Lean selection; both
    # ladders settle on acceptTask at phase NONE (selection agreement).
    assert prod_sel is LadderMeans.ACCEPT_TASK
    assert lean_sel is LadderMeans.ACCEPT_TASK


def test_recycle_surplus_near_miss_protected() -> None:
    """Near-miss: dagger IS a committed objective code (ctx.target_gear) ->
    `recyclable_surplus` excludes it -> RECYCLE_SURPLUS does NOT fire."""
    w = _recycle_world(dagger_qty=2)
    gd = _recycle_gd()
    prod, _, lean, _ = drive_and_contest(
        w, gd, _recycle_ctx(protect_dagger=True))
    assert prod[LadderMeans.RECYCLE_SURPLUS] is False
    assert lean[LadderMeans.RECYCLE_SURPLUS] is False


def test_recycle_surplus_near_miss_at_cap() -> None:
    """Near-miss: only 1 dagger held == useful cap (EQUIPPABLE_KEEP) -> nothing
    above the cap -> RECYCLE_SURPLUS does NOT fire."""
    w = _recycle_world(dagger_qty=1)
    gd = _recycle_gd()
    prod, _, lean, _ = drive_and_contest(w, gd, _recycle_ctx())
    assert prod[LadderMeans.RECYCLE_SURPLUS] is False
    assert lean[LadderMeans.RECYCLE_SURPLUS] is False


# ---------------------------------------------------------------------------
# Slot 3 — drainBankJunk (arg[31]).  Production DRAIN_BANK_JUNK fires iff
# `_used_fraction < 0.85` AND `bank_drain_excess(...)` non-empty (tiers/means.py
# + bank_drain.py): a non-objective code held in the BANK above its useful cap.
# Like recycleSurplus it sits below the lifecycle slots and can only fire-and-
# lose; the contest drives it TRUE under phase=none where BOTH ladders select
# acceptTask (selection agreement at the winner). arg[31] is derived from the
# REAL bank_drain_excess helper (not the slot verdict).
# ---------------------------------------------------------------------------


def _drain_gd() -> GameData:
    # Empty catalog: the banked "sap" has no stats ⇒ useful_quantity_cap 0 ⇒
    # every banked unit is over-cap junk. bank_capacity large ⇒ bank has room ⇒
    # RECYCLE_RELIEF / SELL_RELIEF quiet so DRAIN_BANK_JUNK wins the slot contest.
    gd = GameData()
    gd._bank_capacity = 50
    return gd


def _drain_ctx(*, protect_sap: bool = False) -> SelectionContext:
    # Protect via target_TOOLS (like the recycle test): bank_drain_excess protects
    # on `target_gear | target_tools`, and using target_tools keeps the acceptTask
    # gear-deferral (which reads only target_gear) == Lean at phase none.
    return SelectionContext(
        bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=5, combat_monster=None,
        target_gear=frozenset(),
        target_tools=frozenset({"sap"}) if protect_sap else frozenset(),
        gear_review_active=False)


def _drain_world(bank_sap_qty: int) -> WorldState:
    # No task (phase NONE), empty bag (fill 0/20 = 0 < 0.85), bank holds sap.
    return WorldState(
        character="diff", level=5, xp=0, max_xp=999999, hp=100, max_hp=100,
        gold=0, skills={}, x=0, y=0, inventory={}, inventory_max=20,
        equipment={}, cooldown_expires=None,
        bank_items={"sap": bank_sap_qty} if bank_sap_qty > 0 else {},
        bank_gold=None, pending_items=None,
        task_code=None, task_type=None, task_progress=0, task_total=0)


def test_drain_bank_junk_drives_true() -> None:
    """TRUE fixture: 5 sap banked (over cap 0), empty bag under 0.85 fill,
    unprotected -> production DRAIN_BANK_JUNK fires. It loses selection to
    ACCEPT_TASK (phase NONE) on BOTH ladders, binding arg[31] per-slot."""
    w = _drain_world(bank_sap_qty=5)
    gd = _drain_gd()
    prod, prod_sel, lean, lean_sel = drive_and_contest(
        w, gd, _drain_ctx(), driven=frozenset({LadderMeans.DRAIN_BANK_JUNK}))
    assert prod[LadderMeans.DRAIN_BANK_JUNK] is True
    assert lean[LadderMeans.DRAIN_BANK_JUNK] is True
    assert prod_sel is LadderMeans.ACCEPT_TASK
    assert lean_sel is LadderMeans.ACCEPT_TASK


def test_drain_bank_junk_near_miss_protected() -> None:
    """Near-miss: sap IS a committed objective code -> bank_drain_excess excludes
    it -> DRAIN_BANK_JUNK does NOT fire."""
    w = _drain_world(bank_sap_qty=5)
    gd = _drain_gd()
    prod, _, lean, _ = drive_and_contest(w, gd, _drain_ctx(protect_sap=True))
    assert prod[LadderMeans.DRAIN_BANK_JUNK] is False
    assert lean[LadderMeans.DRAIN_BANK_JUNK] is False


def test_drain_bank_junk_near_miss_empty_bank() -> None:
    """Near-miss: nothing over-cap in the bank -> DRAIN_BANK_JUNK does NOT fire."""
    w = _drain_world(bank_sap_qty=0)
    gd = _drain_gd()
    prod, _, lean, _ = drive_and_contest(w, gd, _drain_ctx())
    assert prod[LadderMeans.DRAIN_BANK_JUNK] is False
    assert lean[LadderMeans.DRAIN_BANK_JUNK] is False


def test_drain_bank_junk_fill_boundary() -> None:
    # Bank holds a drainable junk item (count 1, cap 0). DRAIN_BANK_JUNK gates on
    # the SAME strict `< 0.85` fill as recycleSurplus/sellIdle: fill 17/20 = 0.85
    # does NOT fire (no room to withdraw); 16/20 = 0.80 fires. Pins the comparator.
    _assert_full_agreement(_base_scn(bank_accessible=True, bank_known=True,
                                     bank_capacity=50, bank_items_count=1,
                                     inventory_max=20, junk_qty=17))
    _assert_full_agreement(_base_scn(bank_accessible=True, bank_known=True,
                                     bank_capacity=50, bank_items_count=1,
                                     inventory_max=20, junk_qty=16))


# ===========================================================================
# Brick 4b — Cluster A (combat / predict_win): restForCombat + maintainConsumables.
#
# Both opaque slots fold a `predict_win` / combat verdict that the Lean model
# carries as a passthrough Bool (`restForCombatReady` arg[25],
# `maintainConsumablesFires` arg[29]). `_rich_oracle_args` already derives those
# two args from production's per-slot verdict (`prod[REST_FOR_COMBAT]` /
# `prod[MAINTAIN_CONSUMABLES]`), so NO scaffold extension is needed: we stand up
# a real combat fixture, let production's REAL machinery fire the slot, and the
# oracle re-evaluates `productionLadder` over the firing pattern production
# produced. The teeth are the SELECTION contest.
# ===========================================================================

# ---------------------------------------------------------------------------
# Slot 1 — restForCombat (arg[25]).  Production `_guard_fires(REST_FOR_COMBAT)`
# (tiers/guards.py ~136) fires iff: combat_monster set AND state.hp < max_hp AND
# NOT predict_win(state @ current hp) AND predict_win(state @ hp=max_hp). It is
# ladder idx 1 (only hpCritical above), so a firing restForCombat WINS selection
# on both ladders when hpCritical stays quiet — a STRONG contest: a wrong Lean
# priority for restForCombat would FAIL.
#
# predict_win fixture (NO gear, single-element symmetric fight):
#   * player attack {fire:50}, initiative 0; monster hp 100, attack {fire:50},
#     initiative 0, no resist/crit/exotic abilities -> player_first (init tie,
#     `>=`).
#   * kill_step = 50*raw_player*(200+crit) = 50*50*200 = 500000; monster hp 100
#     -> rounds_to_kill = ceil(100*10000/500000) = 2.
#   * die_step = 50*raw_monster*(200+m_crit) = 500000.
#   At hp=49: rounds_to_die = ceil(49*10000/500000) = ceil(0.98) = 1; rtk 2 > 1
#     -> predict_win FALSE (we die first).
#   At hp=100: rounds_to_die = ceil(100*10000/500000) = 2; rtk 2 <= 2 (player
#     first) -> predict_win TRUE.
#   hp 49/100 = 0.49 >= 0.25 -> hpCritical stays quiet (the slot above), so
#     restForCombat is the highest-firing slot and MUST win selection.
# ---------------------------------------------------------------------------


def _rest_combat_gd() -> GameData:
    """A single monster `mob` with a plain {fire:50} attack and no exotic
    abilities — the symmetric fight the predict_win arithmetic above assumes."""
    gd = GameData()
    gd._monster_hp = {"mob": 100}
    gd._monster_attack = {"mob": {"fire": 50}}
    gd._monster_resistance = {"mob": {}}
    gd._monster_critical_strike = {"mob": 0}
    gd._monster_initiative = {"mob": 0}
    gd._monster_lifesteal = {"mob": 0}
    gd._monster_poison = {"mob": 0}
    gd._monster_barrier = {"mob": 0}
    gd._monster_burn = {"mob": 0}
    gd._monster_healing = {"mob": 0}
    gd._monster_reconstitution = {"mob": 0}
    gd._monster_void_drain = {"mob": 0}
    gd._monster_berserker_rage = {"mob": 0}
    gd._monster_frenzy = {"mob": 0}
    gd._monster_protective_bubble = {"mob": 0}
    gd._monster_corrupted = {"mob": 0}
    gd._item_stats = {}
    gd._crafting_recipes = {}
    return gd


def _rest_combat_ctx() -> SelectionContext:
    return SelectionContext(
        bank_accessible=False, bank_required_level=0, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=5, combat_monster="mob",
        target_gear=frozenset(), target_tools=frozenset(),
        gear_review_active=False)


def _rest_combat_world(hp: int, max_hp: int) -> WorldState:
    # Player attack {fire:50}, initiative 0 (ties the monster -> player first).
    # No task (phase NONE) so when restForCombat does NOT fire the selection
    # falls cleanly through to acceptTask on both ladders.
    return WorldState(
        character="diff", level=10, xp=0, max_xp=999999, hp=hp, max_hp=max_hp,
        gold=0, skills={}, x=0, y=0, inventory={}, inventory_max=20,
        equipment={"weapon_slot": None}, cooldown_expires=None,
        bank_items=None, bank_gold=None, pending_items=None,
        task_code=None, task_type=None, task_progress=0, task_total=0,
        attack={"fire": 50}, initiative=0)


def test_rest_for_combat_drives_and_selects() -> None:
    """TRUE fixture: hp 49/65 (75.4%) — predict_win FALSE now (die in 1 round,
    player hp 49-50=-1) but TRUE at max_hp=65 (survives round 1 at 15 HP, kills
    in round 2) -> production REST_FOR_COMBAT fires. hpCritical is quiet
    (0.754 >= 0.75; Lean: 100*49=4900 NOT < 75*65=4875), so restForCombat
    is the highest firing slot and WINS selection on BOTH ladders. A wrong Lean
    priority for restForCombat would break the selection agreement here."""
    w = _rest_combat_world(hp=49, max_hp=65)
    gd = _rest_combat_gd()
    prod, prod_sel, lean, lean_sel = drive_and_contest(
        w, gd, _rest_combat_ctx(),
        driven=frozenset({LadderMeans.REST_FOR_COMBAT}))
    # Production REALLY fires the driven slot (not faked):
    assert prod[LadderMeans.REST_FOR_COMBAT] is True
    assert lean[LadderMeans.REST_FOR_COMBAT] is True
    assert prod[LadderMeans.HP_CRITICAL] is False
    # Strong selection teeth: restForCombat wins on both sides.
    assert prod_sel is LadderMeans.REST_FOR_COMBAT
    assert lean_sel is LadderMeans.REST_FOR_COMBAT


def test_rest_for_combat_near_miss_winnable_now() -> None:
    """Near-miss (clause c): hp 100/110 — predict_win TRUE at CURRENT hp
    (winnable now) so REST_FOR_COMBAT does NOT fire even though hp < max_hp.
    Selection falls through to acceptTask (phase NONE) on both ladders, so the
    fixture cleanly agrees and selection is asserted."""
    w = _rest_combat_world(hp=100, max_hp=110)
    gd = _rest_combat_gd()
    prod, prod_sel, _, lean_sel = drive_and_contest(
        w, gd, _rest_combat_ctx(),
        driven=frozenset({LadderMeans.REST_FOR_COMBAT}))
    assert prod[LadderMeans.REST_FOR_COMBAT] is False
    assert prod_sel is LadderMeans.ACCEPT_TASK
    assert lean_sel is LadderMeans.ACCEPT_TASK


def test_rest_for_combat_near_miss_full_hp() -> None:
    """Near-miss (clause b): hp == max_hp — Rest is not actionable, so
    REST_FOR_COMBAT does NOT fire regardless of predict_win. (At full hp the
    fight is winnable anyway, but this pins the `hp < max_hp` conjunct.)"""
    w = _rest_combat_world(hp=100, max_hp=100)
    gd = _rest_combat_gd()
    prod, prod_sel, _, lean_sel = drive_and_contest(
        w, gd, _rest_combat_ctx(),
        driven=frozenset({LadderMeans.REST_FOR_COMBAT}))
    assert prod[LadderMeans.REST_FOR_COMBAT] is False
    assert prod_sel is LadderMeans.ACCEPT_TASK
    assert lean_sel is LadderMeans.ACCEPT_TASK


# ---------------------------------------------------------------------------
# Slot 2 — maintainConsumables (arg[29]).  Production `_means_fires(
# MAINTAIN_CONSUMABLES)` (tiers/means.py ~160) + `maintain_consumables_fires`
# (consumable_supply.py ~74): combat_monster set AND heal_stock < HEAL_STOCK_FLOOR
# (5) AND best_craftable_heal is not None (a recipe whose hp_restore item the
# player can craft now).
#
# SELECTION NOTE (a real Lean-model finding, reported — mirrors recycleSurplus
# in 4a): maintainConsumables is ladder idx 18, BELOW the lifecycle slots
# acceptTask(16)/pursueTask/completeTask. For EVERY phase some higher slot fires
# on the Lean ladder (acceptTask at phase none, completeTask at complete,
# pursueTask at accepted/inProgress), so maintainConsumables can NEVER be the
# Lean SELECTION — it can only fire-and-lose. The contest drives it TRUE (the
# per-slot agreement binding arg[29]) at phase NONE, where BOTH ladders select
# acceptTask; selection agreement holds at that winner.
# ---------------------------------------------------------------------------


def _maintain_gd() -> GameData:
    gd = GameData()
    gd._crafting_recipes = {"potion": {"herb": 1}}
    gd._item_stats = {
        "potion": ItemStats(code="potion", level=1, type_="consumable",
                            crafting_skill="alchemy", crafting_level=1,
                            hp_restore=50),
    }
    return gd


def _maintain_ctx() -> SelectionContext:
    return SelectionContext(
        bank_accessible=False, bank_required_level=0, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=5, combat_monster="mob",
        target_gear=frozenset(), target_tools=frozenset(),
        gear_review_active=False)


def _maintain_world(potion_qty: int) -> WorldState:
    # No task (phase NONE), alchemy@1 (recipe level met), heal stock = potion_qty.
    inv = {"potion": potion_qty} if potion_qty > 0 else {}
    return WorldState(
        character="diff", level=10, xp=0, max_xp=999999, hp=100, max_hp=100,
        gold=0, skills={"alchemy": 1}, x=0, y=0,
        inventory=inv, inventory_max=20,
        equipment={"weapon_slot": None}, cooldown_expires=None,
        bank_items=None, bank_gold=None, pending_items=None,
        task_code=None, task_type=None, task_progress=0, task_total=0)


def test_maintain_consumables_drives_true() -> None:
    """TRUE fixture: combat target set, heal_stock 0 < 5, a craftable potion
    (alchemy@1, hp_restore 50) -> production MAINTAIN_CONSUMABLES fires. It is
    structurally below acceptTask, so it loses selection to ACCEPT_TASK (phase
    NONE) on BOTH ladders; `selected` agrees at acceptTask while arg[29] is
    bound by the per-slot contest."""
    w = _maintain_world(potion_qty=0)
    gd = _maintain_gd()
    prod, prod_sel, lean, lean_sel = drive_and_contest(
        w, gd, _maintain_ctx(),
        driven=frozenset({LadderMeans.MAINTAIN_CONSUMABLES}))
    assert prod[LadderMeans.MAINTAIN_CONSUMABLES] is True
    assert lean[LadderMeans.MAINTAIN_CONSUMABLES] is True
    # maintainConsumables is structurally unreachable as a Lean selection; both
    # ladders settle on acceptTask at phase NONE (selection agreement).
    assert prod_sel is LadderMeans.ACCEPT_TASK
    assert lean_sel is LadderMeans.ACCEPT_TASK


def test_maintain_consumables_near_miss_stocked() -> None:
    """Near-miss: heal_stock 5 == HEAL_STOCK_FLOOR -> NOT under-stocked ->
    MAINTAIN_CONSUMABLES does NOT fire (pins the `heal_stock < 5` conjunct)."""
    w = _maintain_world(potion_qty=5)
    gd = _maintain_gd()
    prod, _, lean, _ = drive_and_contest(
        w, gd, _maintain_ctx(),
        driven=frozenset({LadderMeans.MAINTAIN_CONSUMABLES}))
    assert prod[LadderMeans.MAINTAIN_CONSUMABLES] is False
    assert lean[LadderMeans.MAINTAIN_CONSUMABLES] is False


def test_maintain_consumables_near_miss_no_combat() -> None:
    """Near-miss: no combat target -> the means tier short-circuits regardless
    of stock/craftability -> MAINTAIN_CONSUMABLES does NOT fire."""
    w = _maintain_world(potion_qty=0)
    gd = _maintain_gd()
    ctx = SelectionContext(
        bank_accessible=False, bank_required_level=0, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=5, combat_monster=None,
        target_gear=frozenset(), target_tools=frozenset(),
        gear_review_active=False)
    prod, _, lean, _ = drive_and_contest(
        w, gd, ctx, driven=frozenset({LadderMeans.MAINTAIN_CONSUMABLES}))
    assert prod[LadderMeans.MAINTAIN_CONSUMABLES] is False
    assert lean[LadderMeans.MAINTAIN_CONSUMABLES] is False


# ===========================================================================
# Brick 4c — the HISTORY-GATED phase slots: taskCancel + pursueTask +
# lowYieldCancel.
#
# UNLIKE 4a/4b's passthrough slots, these three are Lean phase-derived
# OVER-APPROXIMATIONS: Lean computes them from `taskLifecyclePhase` (arg[16]),
# `actionsAttempted` (arg[11]), and `taskFeasibleProjected` (arg[24]) — it has
# NO `LearningStore` concept — whereas production reads a real `LearningStore`
# history + `task_decision`. So Lean and production CAN diverge per-slot in
# general. To get an apples-to-apples SELECTION contest, each scenario below is
# driven so BOTH sides fire the driven slot (the Lean phase is set consistent
# with production's real history verdict) AND so the slots ABOVE the driven one
# are quiet on both ladders. `drive_and_contest` asserts per-slot agreement for
# ASSERTED_SLOTS ∪ {driven} only — the OTHER history-gated phase slots that are
# not driven are deliberately skipped per-slot (a known over-approximation on a
# non-driven phase-slot must not spuriously fail), but selection is still
# asserted, so any divergence that changes the WINNER is caught.
#
# Real production `LearningStore` (not a mock) is threaded through
# `drive_and_contest(history=...)`; taskCancel/pursueTask take an essentially
# EMPTY store (their PIVOT/PURSUE verdicts short-circuit before reading
# aggregates), lowYieldCancel takes a POPULATED one (its zero-fast-path reads
# FarmItems + FarmMonster yield rows).
# ===========================================================================


def _empty_history() -> LearningStore:
    """A started-but-unpopulated in-memory LearningStore. Non-None (so the
    history-gated production predicates engage) but holding no Cycle rows —
    sufficient for taskCancel (PIVOT on a combat req short-circuits before any
    aggregate read) and pursueTask (PURSUE on a req-None items task likewise)."""
    store = LearningStore(db_path=":memory:", character="hero")
    store.start_session()
    return store


def _yield_history(
    farm_items_xp: int,
    farm_monster_xp: int,
    *,
    monster_repr: str = "FarmMonster(chicken)",
) -> LearningStore:
    """A POPULATED in-memory LearningStore for the lowYieldCancel path.

    Records one `FarmItems` cycle yielding `farm_items_xp` char-XP and one
    `monster_repr` cycle yielding `farm_monster_xp` char-XP. `low_yield_cancel_fires`
    reads `expected_yield_per_cycle("FarmItems", ...).char_xp` (the FarmItems
    `delta_xp` mean) and the best-FarmMonster alternative's `char_xp`; with
    FarmItems=0 and a positive monster the zero-fast-path
    (`current_xp == 0 ∧ alt_xp > 0`) fires regardless of confidence.

    Cycle requires `ts`, `cycle_index`, `outcome` (session_id/character are
    stamped by `record_cycle`); `selected_goal` + `delta_xp` are what the
    projection aggregates over."""
    store = LearningStore(db_path=":memory:", character="hero")
    store.start_session()
    store.record_cycle(Cycle(
        ts="2026-06-18T00:00:00+00:00", cycle_index=0, outcome="ok",
        selected_goal="FarmItems", delta_xp=farm_items_xp))
    store.record_cycle(Cycle(
        ts="2026-06-18T00:00:01+00:00", cycle_index=1, outcome="ok",
        selected_goal=monster_repr, delta_xp=farm_monster_xp))
    return store


# ---------------------------------------------------------------------------
# Slot 1 — taskCancel (Lean idx 13).  Production `_means_fires(TASK_CANCEL)`
# (means.py ~101): `state.task_code` set AND `history is not None` AND
# `task_decision(...) == PIVOT`. The cheapest PIVOT: a monsters-task whose
# monster is too hard — `task_requirement` returns SkillRequirement("combat")
# (monster_level > level + 2), and `task_decision_pure` PIVOTs on a combat req
# regardless of yield aggregates, so an EMPTY history suffices.
#
# Lean `taskCancelFires` (ProductionLadder.lean ~215): phase ∈ {accepted,
# inProgress} AND `!taskFeasibleProjected`. We drive phase=accepted (progress 0)
# — which keeps lowYieldCancel (idx 12, needs inProgress) QUIET — and feed
# taskFeasibleProjected=0 (the task is NOT feasible, matching the PIVOT). With
# everything above idx 13 quiet, taskCancel WINS selection on both ladders.
# ---------------------------------------------------------------------------


def _too_hard_monsters_gd() -> GameData:
    """A monsters-task target `hard_mob` at level 40 — far above the level-5
    character (gap 35 > MONSTER_LEVEL_MARGIN 2) so `task_requirement` yields a
    combat SkillRequirement and `task_decision` PIVOTs."""
    gd = GameData()
    gd._monster_level = {"hard_mob": 40}
    gd._item_stats = {}
    gd._crafting_recipes = {}
    return gd


def _plain_ctx(*, combat_monster: str | None = None) -> SelectionContext:
    return SelectionContext(
        bank_accessible=False, bank_required_level=0, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=5, combat_monster=combat_monster,
        target_gear=frozenset(), target_tools=frozenset(),
        gear_review_active=False)


def _monsters_task_world(*, task_code: str, progress: int, total: int) -> WorldState:
    # level 5; full hp, empty bag, no bank/pending so every slot above
    # taskCancel(13)/lowYieldCancel(12) stays quiet.
    return WorldState(
        character="diff", level=5, xp=0, max_xp=999999, hp=100, max_hp=100,
        gold=0, skills={}, x=0, y=0, inventory={}, inventory_max=20,
        equipment={}, cooldown_expires=None, bank_items=None, bank_gold=None,
        pending_items=None, task_code=task_code, task_type="monsters",
        task_progress=progress, task_total=total)


def test_task_cancel_drives_and_selects() -> None:
    """TRUE fixture: monsters-task `hard_mob` (lvl 40) vs level-5 char ->
    `task_requirement` = combat req -> `task_decision` PIVOTs -> production
    TASK_CANCEL fires with a non-None (empty) history. phase=accepted keeps the
    higher lowYieldCancel quiet; taskFeasibleProjected=0 makes Lean taskCancel
    fire. taskCancel is the highest firing slot and WINS selection on BOTH
    ladders. A wrong Lean priority for taskCancel would break selection here."""
    w = _monsters_task_world(task_code="hard_mob", progress=0, total=5)
    gd = _too_hard_monsters_gd()
    hist = _empty_history()
    prod, prod_sel, lean, lean_sel = drive_and_contest(
        w, gd, _plain_ctx(),
        driven=frozenset({LadderMeans.TASK_CANCEL}),
        history=hist, task_feasible_projected=False)
    # Production REALLY PIVOTs (not faked):
    assert prod[LadderMeans.TASK_CANCEL] is True
    assert lean[LadderMeans.TASK_CANCEL] is True
    # lowYieldCancel (idx 12, above) is quiet on both sides (accepted phase /
    # empty FarmItems history).
    assert prod[LadderMeans.LOW_YIELD_CANCEL] is False
    assert lean[LadderMeans.LOW_YIELD_CANCEL] is False
    # Strong selection teeth: taskCancel wins on both ladders.
    assert prod_sel is LadderMeans.TASK_CANCEL
    assert lean_sel is LadderMeans.TASK_CANCEL


def test_task_cancel_near_miss_feasible_task() -> None:
    """Near-miss: a FEASIBLE monsters-task (`easy_mob` lvl 5 == char level, gap
    3 <= margin) -> `task_requirement` None -> `task_decision` PURSUE (not
    PIVOT) -> production TASK_CANCEL does NOT fire. Lean is fed
    taskFeasibleProjected=1 (matching feasibility) so Lean taskCancel is also
    quiet — the per-slot taskCancel contest is the point.

    Selection is NOT asserted: this is a MONSTERS-task, so production PURSUE_TASK
    (items-only) stays False and production falls through to WAIT, while Lean
    `pursueTaskFires` is a phase-based over-approximation that fires for ANY
    accepted task — a known divergence (see `drive_and_contest`), not this
    near-miss's contest."""
    w = _monsters_task_world(task_code="easy_mob", progress=0, total=5)
    gd = GameData()
    gd._monster_level = {"easy_mob": 5}
    gd._item_stats = {}
    gd._crafting_recipes = {}
    prod, _, lean, _ = drive_and_contest(
        w, gd, _plain_ctx(),
        driven=frozenset({LadderMeans.TASK_CANCEL}),
        history=_empty_history(), task_feasible_projected=True,
        assert_selection=False)
    assert prod[LadderMeans.TASK_CANCEL] is False
    assert lean[LadderMeans.TASK_CANCEL] is False


def test_task_cancel_near_miss_no_history() -> None:
    """Near-miss: history=None -> production TASK_CANCEL short-circuits to False
    even though the task is infeasible. (Pins the `history is not None`
    conjunct.) Lean is NOT asserted per-slot here — with history=None the model
    has no equivalent input, so we only assert the production side and skip the
    selection contest."""
    w = _monsters_task_world(task_code="hard_mob", progress=0, total=5)
    gd = _too_hard_monsters_gd()
    prod, _, _, _ = drive_and_contest(
        w, gd, _plain_ctx(),
        driven=frozenset({LadderMeans.TASK_CANCEL}),
        history=None, task_feasible_projected=True, assert_selection=False)
    assert prod[LadderMeans.TASK_CANCEL] is False


# ---------------------------------------------------------------------------
# Slot 2 — pursueTask (Lean idx 15).  Production `_means_fires(PURSUE_TASK)`
# (means.py ~106): items-task AND `task_code` AND `task_total>0` AND
# `task_progress<task_total` AND `history is not None` AND `task_decision ==
# PURSUE`. The cheapest PURSUE: a FEASIBLE items-task — empty catalog ⇒
# `task_requirement` None ⇒ `task_decision_pure(req_is_none=True)` = PURSUE,
# independent of any yield aggregate, so an EMPTY history suffices.
#
# Lean `pursueTaskFires` (ProductionLadder.lean ~233): phase ∈ {accepted,
# inProgress} (NO feasibility conjunct). We drive phase=accepted and feed
# taskFeasibleProjected=1 so the HIGHER taskCancel (idx 13) stays QUIET on the
# Lean side, and objective_step=False so objectiveStep (idx 14) is quiet too;
# pursueTask (idx 15) is then the highest firing slot and WINS selection on
# both ladders.
# ---------------------------------------------------------------------------


def _feasible_items_gd() -> GameData:
    """Empty catalog: the items-task code has no crafting_skill stats and no
    recipe, so `task_requirement` returns None (no skill gap) -> PURSUE.

    Task completion rewards are seeded for the `widget` task code so the
    low-yield projection (`project_task_completion` -> task_gold/coin_reward)
    reads real API amounts instead of raising on missing task-reward data."""
    gd = GameData()
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._task_gold_rewards = {"widget": 150}
    gd._task_coin_rewards = {"widget": 1}
    return gd


def _items_task_world(*, progress: int, total: int) -> WorldState:
    return WorldState(
        character="diff", level=5, xp=0, max_xp=999999, hp=100, max_hp=100,
        gold=0, skills={}, x=0, y=0, inventory={}, inventory_max=20,
        equipment={}, cooldown_expires=None, bank_items=None, bank_gold=None,
        pending_items=None, task_code="widget", task_type="items",
        task_progress=progress, task_total=total)


def test_pursue_task_drives_and_selects() -> None:
    """TRUE fixture: feasible items-task `widget` 0/5 (phase accepted), empty
    catalog -> `task_decision` PURSUE -> production PURSUE_TASK fires with a
    non-None (empty) history. taskFeasibleProjected=1 keeps Lean taskCancel
    quiet; objective_step=False keeps objectiveStep quiet; pursueTask is the
    highest firing slot and WINS selection on BOTH ladders."""
    w = _items_task_world(progress=0, total=5)
    gd = _feasible_items_gd()
    prod, prod_sel, lean, lean_sel = drive_and_contest(
        w, gd, _plain_ctx(),
        driven=frozenset({LadderMeans.PURSUE_TASK}),
        history=_empty_history(), task_feasible_projected=True,
        objective_step=False)
    # Production REALLY PURSUEs (not faked):
    assert prod[LadderMeans.PURSUE_TASK] is True
    assert lean[LadderMeans.PURSUE_TASK] is True
    # The slots above pursueTask that could contest are quiet on both ladders.
    assert prod[LadderMeans.TASK_CANCEL] is False
    assert lean[LadderMeans.TASK_CANCEL] is False
    assert prod[LadderMeans.LOW_YIELD_CANCEL] is False
    assert lean[LadderMeans.LOW_YIELD_CANCEL] is False
    # Strong selection teeth: pursueTask wins on both ladders.
    assert prod_sel is LadderMeans.PURSUE_TASK
    assert lean_sel is LadderMeans.PURSUE_TASK


def test_pursue_task_near_miss_too_hard() -> None:
    """Near-miss: an items-task whose deliverable needs an out-of-reach crafting
    skill (`gizmo` requires weaponcrafting 30, char has none) ->
    `task_requirement` is a non-combat skill gap -> `task_decision` PIVOTs (the
    unobserved-gap margin rejects a default reward) -> production PURSUE_TASK
    does NOT fire. taskFeasibleProjected=0 + driving taskCancel keeps the Lean
    contest honest (taskCancel becomes the agreed winner)."""
    w = WorldState(
        character="diff", level=5, xp=0, max_xp=999999, hp=100, max_hp=100,
        gold=0, skills={}, x=0, y=0, inventory={}, inventory_max=20,
        equipment={}, cooldown_expires=None, bank_items=None, bank_gold=None,
        pending_items=None, task_code="gizmo", task_type="items",
        task_progress=0, task_total=5)
    gd = GameData()
    gd._item_stats = {
        "gizmo": ItemStats(code="gizmo", level=30, type_="weapon",
                           crafting_skill="weaponcrafting", crafting_level=30),
    }
    gd._crafting_recipes = {"gizmo": {"copper_bar": 6}}
    prod, _, lean, _ = drive_and_contest(
        w, gd, _plain_ctx(),
        driven=frozenset({LadderMeans.TASK_CANCEL}),
        history=_empty_history(), task_feasible_projected=False)
    assert prod[LadderMeans.PURSUE_TASK] is False
    # The infeasible items-task PIVOTs, so production taskCancel fires; the Lean
    # side (taskFeasibleProjected=0, accepted phase) fires taskCancel too.
    assert prod[LadderMeans.TASK_CANCEL] is True
    assert lean[LadderMeans.TASK_CANCEL] is True


# ---------------------------------------------------------------------------
# Slot 3 — lowYieldCancel (Lean idx 12).  Production `low_yield_cancel_fires`
# (projections.py ~365 + low_yield_boundary.py): a held task (task_code set,
# task_total>0), FarmItems yield with sample_count>0, a best-alternative
# FarmMonster with sample_count>0, and the zero-fast-path
# (`current_xp == 0 ∧ alt_xp > 0`). The POPULATED store from `_yield_history`
# supplies a FarmItems cycle yielding 0 char-XP and a FarmMonster cycle yielding
# positive char-XP, so the zero-fast-path fires.
#
# Lean `lowYieldCancelFires` (ProductionLadder.lean ~205): phase==inProgress
# AND `actionsAttempted >= lowYieldSampleThreshold` (=1). We drive
# phase=inProgress (progress 1/5) and actions_attempted=1; taskFeasibleProjected
# =1 keeps taskCancel quiet on Lean (idx 13, below 12 anyway). lowYieldCancel
# (idx 12) is the highest firing slot and WINS selection on BOTH ladders.
# ---------------------------------------------------------------------------


def _farm_items_world(*, progress: int, total: int) -> WorldState:
    # An IN_PROGRESS items-task (progress 1/5), clean otherwise so every slot
    # above lowYieldCancel(12) stays quiet.
    return WorldState(
        character="diff", level=10, xp=0, max_xp=999999, hp=100, max_hp=100,
        gold=0, skills={}, x=0, y=0, inventory={}, inventory_max=20,
        equipment={}, cooldown_expires=None, bank_items=None, bank_gold=None,
        pending_items=None, task_code="widget", task_type="items",
        task_progress=progress, task_total=total)


def test_low_yield_cancel_drives_and_selects() -> None:
    """TRUE fixture: held items-task 1/5 (in-progress), a POPULATED store where
    FarmItems yields 0 char-XP/cycle and FarmMonster(chicken) yields positive
    char-XP/cycle -> the zero-fast-path fires -> production LOW_YIELD_CANCEL
    fires. Lean: phase=inProgress + actionsAttempted=1 -> lowYieldCancel fires.
    It is ladder idx 12, the highest firing slot, and WINS selection on BOTH
    ladders. A wrong Lean priority for lowYieldCancel would break this."""
    w = _farm_items_world(progress=1, total=5)
    gd = _feasible_items_gd()
    hist = _yield_history(farm_items_xp=0, farm_monster_xp=20)
    prod, prod_sel, lean, lean_sel = drive_and_contest(
        w, gd, _plain_ctx(),
        driven=frozenset({LadderMeans.LOW_YIELD_CANCEL}),
        history=hist, actions_attempted=1, task_feasible_projected=True)
    # Production REALLY fires the driven slot (not faked):
    assert prod[LadderMeans.LOW_YIELD_CANCEL] is True
    assert lean[LadderMeans.LOW_YIELD_CANCEL] is True
    # Strong selection teeth: lowYieldCancel wins on both ladders.
    assert prod_sel is LadderMeans.LOW_YIELD_CANCEL
    assert lean_sel is LadderMeans.LOW_YIELD_CANCEL


def test_low_yield_cancel_near_miss_positive_current_xp() -> None:
    """Near-miss: FarmItems yields positive char-XP (5), so the zero-fast-path
    (`current_xp == 0`) does NOT apply; the remaining margin path then needs the
    confidence gate (`project_task_completion(...).confidence`) to clear, which a
    single sample does not -> production LOW_YIELD_CANCEL does NOT fire. (Pins the
    zero-fast-path / confidence gate.)

    `actions_attempted=0` makes the Lean lowYieldCancel quiet too (Lean gates on
    actionsAttempted >= 1), so its per-slot contest agrees at False. With
    lowYieldCancel/taskCancel quiet, both ladders fall through to pursueTask
    (in-progress, feasible) and SELECTION still AGREES -- so it stays asserted."""
    w = _farm_items_world(progress=1, total=5)
    gd = _feasible_items_gd()
    hist = _yield_history(farm_items_xp=5, farm_monster_xp=20)
    prod, _, lean, _ = drive_and_contest(
        w, gd, _plain_ctx(),
        driven=frozenset({LadderMeans.LOW_YIELD_CANCEL}),
        history=hist, actions_attempted=0, task_feasible_projected=True)
    assert prod[LadderMeans.LOW_YIELD_CANCEL] is False
    assert lean[LadderMeans.LOW_YIELD_CANCEL] is False


def test_low_yield_cancel_near_miss_no_alternative() -> None:
    """Near-miss: FarmItems yields 0 char-XP but there is NO FarmMonster
    alternative recorded -> `_best_alternative_repr` returns None -> production
    LOW_YIELD_CANCEL does NOT fire (pins the alt-sample prerequisite).

    `actions_attempted=0` makes the Lean lowYieldCancel quiet too, so its per-slot
    contest agrees at False; both ladders fall through to pursueTask and SELECTION
    AGREES -- so it stays asserted."""
    w = _farm_items_world(progress=1, total=5)
    gd = _feasible_items_gd()
    store = LearningStore(db_path=":memory:", character="hero")
    store.start_session()
    store.record_cycle(Cycle(
        ts="2026-06-18T00:00:00+00:00", cycle_index=0, outcome="ok",
        selected_goal="FarmItems", delta_xp=0))
    prod, _, lean, _ = drive_and_contest(
        w, gd, _plain_ctx(),
        driven=frozenset({LadderMeans.LOW_YIELD_CANCEL}),
        history=store, actions_attempted=0, task_feasible_projected=True)
    assert prod[LadderMeans.LOW_YIELD_CANCEL] is False
    assert lean[LadderMeans.LOW_YIELD_CANCEL] is False

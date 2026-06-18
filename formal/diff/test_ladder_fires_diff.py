"""O5.4 Brick 3 — SELECT-side differential for the NUMERIC/structural ladder slots.

Binds the Lean liveness ladder (`Formal.Liveness.ProductionLadder.fires` /
`productionLadder`, evaluated through the `ladder_fires` oracle entry) to the
REAL production firing predicates `_guard_fires` (tiers/guards.py) and
`_means_fires` (tiers/means.py), reached through the real-import bridge
`formal/sim/production_ladder.py`. This closes the trust gap flagged in the
2026-06-18 SELECT audit: every liveness theorem reasons over the Lean ladder,
but nothing had ever asserted the Lean ladder MIRRORS production.

## The honest design — opaque Bools are INPUTS supplied identically

Several ladder slots read an opaque per-cycle observation that production
derives from machinery this brick does not yet reconstruct (the planner,
`predict_win`, `craft_relief_candidates`, …). The differential is apples-to-
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

## Slots DEFERRED to Brick 4 (TRUE-firing path NOT yet drivable)

These read an opaque observation production derives from machinery Brick 4 will
reconstruct on a real fixture; here their production value is pinned to its
empty-catalog / no-history default (False) and the Lean side is fed the SAME
default, so they are compared only at that value — their TRUE behaviour is
unvalidated and explicitly deferred:

  * craftRelief         — production: `craft_relief_candidates` non-empty (needs
                          recipes + inventory pressure). Brick 4.
  * maintainConsumables — production: `maintain_consumables_fires` (needs a
                          combat target + heal recipes). Brick 4.
  * restForCombat       — production short-circuits on `combat_monster is None`
                          and Lean on `restForCombatReady` (fed 0) BEFORE the
                          numeric `hp < maxHp` clause, so the slot is False on
                          both sides here and its firing logic (the
                          `predict_win`-folded `restForCombatReady`) is wholly
                          deferred. Brick 4.
  * lowYieldCancel      — production: `low_yield_cancel_fires` (needs a
                          LearningStore); Lean gates on phase==inProgress AND
                          actionsAttempted. We supply history=None (⇒ False) and
                          keep the scenario phase out of inProgress, so neither
                          side fires. Brick 4 binds the learning path.
  * taskCancel          — production: `task_decision == PIVOT` (needs history);
                          Lean gates on phase∈{accepted,inProgress} AND
                          !taskFeasibleProjected. history=None ⇒ False; we feed
                          taskFeasibleProjected=True and keep phase∈{none,
                          complete} so Lean is also False. Brick 4.
  * pursueTask          — production: items-task AND history AND
                          `task_decision==PURSUE`; Lean gates on
                          phase∈{accepted,inProgress}. history=None ⇒ False; we
                          keep phase∈{none,complete} so Lean is also False.
                          Brick 4.
  * recycleSurplus      — production: `recyclable_surplus` non-empty (needs
                          surplus craftable gear). Empty catalog ⇒ False both
                          sides. Brick 4.

To keep `selected` honest while these are deferred, every generated scenario is
constrained so the deferred slots are FALSE on BOTH sides (phase ∈ {none,
complete}, history=None, taskFeasibleProjected=True, empty catalog,
combat_monster=None). Their TRUE paths — and the resulting selection contests —
are Brick 4's job.

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

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
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
    LadderMeans.DEPOSIT_FULL: "depositFull",
    LadderMeans.DISCARD_HIGH: "discardHigh",
    LadderMeans.GEAR_REVIEW: "gearReview",
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
    """Build the 31-int oracle arg array reading the STRUCTURAL facts off the
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
    ]


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
    # 24/100 = 0.24 < 0.25 fires; 25/100 = 0.25 does NOT (strict <).
    _assert_full_agreement(_base_scn(hp=24, max_hp=100))
    _assert_full_agreement(_base_scn(hp=25, max_hp=100))


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
    # bank_accessible required.
    _assert_full_agreement(_base_scn(bank_accessible=True, inventory_max=20,
                                     junk_qty=18))
    _assert_full_agreement(_base_scn(bank_accessible=True, inventory_max=20,
                                     junk_qty=17))


def test_sell_pressured_vs_idle_boundary() -> None:
    # sellable item; fill 17/20=0.85 -> SELL_PRESSURED; 16/20=0.80 -> SELL_IDLE.
    _assert_full_agreement(_base_scn(inventory_max=20, junk_qty=17,
                                     item_sellable=True))
    _assert_full_agreement(_base_scn(inventory_max=20, junk_qty=16,
                                     item_sellable=True))


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

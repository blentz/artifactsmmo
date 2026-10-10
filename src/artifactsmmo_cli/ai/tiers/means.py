"""Means bands: instrumental/opportunistic actions ranked under the objective
step. Collect-reward sits just below guards; discretionary just below the
objective step. Pure predicates over state/game_data/history + SelectionContext.

No Goal-class imports — the driver (StrategyArbiter) maps MeansKind to goals.
"""

from enum import Enum

from artifactsmmo_cli.ai.accumulation_sell import sellable_tradeable_now
from artifactsmmo_cli.ai.bank_drain import bank_drain_excess
from artifactsmmo_cli.ai.bank_expansion_timing import (
    TRIGGER_FILL_DEN,
    TRIGGER_FILL_NUM,
    expansion_fires,
)
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.ge_bid import ge_bid_candidates
from artifactsmmo_cli.ai.ge_order_config import TTL_CYCLES
from artifactsmmo_cli.ai.grind_heal_prep import maintain_consumables_goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.progression_reserve import account_gold
from artifactsmmo_cli.ai.recycle_surplus import recyclable_surplus
from artifactsmmo_cli.ai.thresholds import PRESSURE_HIGH_FRACTION
from artifactsmmo_cli.ai.tiers.guards import (
    SelectionContext,
    used_fraction,
)
from artifactsmmo_cli.ai.world_state import WorldState

# Semantic name for this module's sell-pressure gate, bound to the SHARED
# single-source constant (thresholds.py pressure ladder). It used to be a
# re-typed literal (0.85) — the drift the thresholds consolidation was built
# to kill; the local name is kept because the ladder's proven mutation
# anchors bind to the usage lines. (BANK_EXPAND's fill gate now lives inside
# the shared should_expand_bank core — no local constant.)
SELL_PRESSURE_FRACTION = PRESSURE_HIGH_FRACTION



class MeansKind(Enum):
    CLAIM_PENDING = "claim_pending"
    SELL_PRESSURED = "sell_pressured"
    SELL_IDLE = "sell_idle"
    RECYCLE_SURPLUS = "recycle_surplus"
    BANK_EXPAND = "bank_expand"
    WAIT = "wait"
    # Appended LAST so the DecideKey oracle's index dispatch and the diff test's
    # _MEANS_INDEX stay stable — enum identity is independent of the
    # DISCRETIONARY_ORDER priority slot below (PLAN #6a).
    MAINTAIN_CONSUMABLES = "maintain_consumables"
    DRAIN_BANK_JUNK = "drain_bank_junk"  # 2026-06-24: drain over-cap bank junk.
    GE_BID = "ge_bid"  # 2026-07-24: post a discretionary GE buy order for a slow-to-craft item.


INTERRUPT_MEANS: frozenset[MeansKind] = frozenset({
    MeansKind.SELL_PRESSURED,
    MeansKind.CLAIM_PENDING,
    MeansKind.BANK_EXPAND,
})
"""Means that are chores, not rewards: preconditions of continuing whatever the
character does, so `StrategyArbiter._build_candidates` builds them at
`BAND_GUARD` and they run in the interrupt pre-pass (Phase 5 of
docs/PLAN_decision_architecture_redesign.md). SELL_PRESSURED is the bag at the
pressure threshold (5-2b); CLAIM_PENDING is one action that collects a pending
item and serves no objective (5-2c-i); BANK_EXPAND keeps the deposit sink open
(5-2c-ii). They lead `COLLECT_REWARD_ORDER`."""


COLLECT_REWARD_ORDER: tuple[MeansKind, ...] = (
    # The INTERRUPT_MEANS lead the order (Phase 5-2b/5-2c-i): they are chores,
    # run as interrupts at the end of the guard prefix — the order the Lean
    # ladder (`MeansKind.allInLadderOrder`) states.
    MeansKind.SELL_PRESSURED,
    MeansKind.CLAIM_PENDING,
    # Phase 5-2c-ii: an INTERRUPT. Buying a bank slot is what keeps the deposit
    # sink open, a precondition of continuing rather than a reward, so it runs
    # with the bag/bank chores at the end of the interrupt prefix. (It was the
    # LAST collect rung since its 2026-09-13 promotion out of the discretionary
    # band, where it fired against a 50/50 bank and was selected zero times.
    # USER 2026-09-13: "expanding the bank is good to do whenever we have the
    # money for it.")
    MeansKind.BANK_EXPAND,
    # COMPLETE_TASK was retired here in Phase 5-2c-iii-c-2 #6: a met task is
    # turned in as the task objective's own step (`ReachTaskOutcome`), on the
    # task's turn.
    # LOW_YIELD_CANCEL was retired here in Phase 5-2c-iii-c-2: a data-confirmed
    # poor task is the task objective's own step (`ReachTaskOutcome`), taken on
    # the task's turn, not a collect rung above every root.
    # TASK_CANCEL was retired here in Phase 5-2c-iii-c-2 #5: a task worth less
    # than its cancel is the task objective's own step (`ReachTaskOutcome`),
    # judged by `task_worth.held_task_cancel_due`, on the task's turn.
    # SUPPLY_BANK and CURRENCY_TURNIN were retired here in Phase 5-2c-iv: fleet
    # work the coordination tables name is the fleet objective
    # (`ReachFleetOutcome`, gated by `ai/fleet_work`), served on its rotation
    # turn rather than above the step.
    # ACCEPT_TASK was retired here in Phase 5-2c-iii-c-2 #3: taking a draw is the
    # task objective's own step (`ReachTaskOutcome`), on its turn — the USER's
    # ruling that no task is drawn until the objective has its turn.
)
DISCRETIONARY_ORDER: tuple[MeansKind, ...] = (
    # PURSUE_TASK was retired here in Phase 5-2c-iii-c-2 #4: an items task is
    # worked by the task objective's own step (`ReachTaskOutcome`) on its turn.
    # TASK_EXCHANGE was retired here in Phase 5-2c-iii-c-2: coins are exchanged
    # by the task objective's own step (`ReachTaskOutcome`) on its turn.
    MeansKind.MAINTAIN_CONSUMABLES,  # prep heals for combat before idle housekeeping
    MeansKind.SELL_IDLE,
    MeansKind.RECYCLE_SURPLUS,
    # Opportunistic cheap acquisition: post a GE buy order for a slow-to-craft
    # objective material. Below the housekeeping investments (recycle/expand),
    # above pure junk-drain — acquiring a needed material beats draining junk.
    MeansKind.GE_BID,
    # Lowest-value housekeeping, just above WAIT: drain over-cap bank junk only
    # when nothing better is pending. (The bank-expansion investment it used to
    # rank against left this band on 2026-09-13.)
    MeansKind.DRAIN_BANK_JUNK,
    MeansKind.WAIT,
)


def _fires(kind: MeansKind, state: WorldState, game_data: GameData,
           history: LearningStore | None, ctx: SelectionContext) -> bool:
    if kind is MeansKind.CLAIM_PENDING:
        return bool(state.pending_items)

    if kind is MeansKind.SELL_PRESSURED:
        # A buyer that can take it NOW — never the window-blind "some held code
        # has a located buyer" test. See `sellable_tradeable_now`.
        return (used_fraction(state) >= SELL_PRESSURE_FRACTION
                and sellable_tradeable_now(state, game_data))

    if kind is MeansKind.SELL_IDLE:
        return (used_fraction(state) < SELL_PRESSURE_FRACTION
                and sellable_tradeable_now(state, game_data))

    if kind is MeansKind.RECYCLE_SURPLUS:
        # Idle/low-pressure only: recovered materials need room to land (under
        # pressure the deposit/discard guards handle space). Fires when the keep
        # authority (`ai/inventory_keep`) licenses the destruction of surplus
        # craftable gear — copies above BOTH keep_in_bag and keep_owned, so the
        # equipped copy, the profile's demand and the working tool are never it.
        return (used_fraction(state) < SELL_PRESSURE_FRACTION
                and bool(recyclable_surplus(state, game_data, ctx)))

    if kind is MeansKind.DRAIN_BANK_JUNK:
        # Idle/low-pressure only: the withdraw mints items into the bag, so it
        # needs free slots to land (under pressure the deposit/discard guards
        # handle space). Fires when the keep authority (`ai/inventory_keep`)
        # licenses the destruction of over-cap BANK junk — copies above
        # `keep_owned`, so the last tool, the last weapon and the profile's gear
        # demand are never withdrawn into the discard ladder's mouth.
        return (used_fraction(state) < SELL_PRESSURE_FRACTION
                and bool(bank_drain_excess(state, game_data, ctx)))

    if kind is MeansKind.GE_BID:
        # Post a GE buy order for a slow-to-craft objective material. Fires iff
        # the shared candidate helper (the SAME predicate the goal bids on, so
        # the means never fires on a candidate the goal then refuses — no
        # zero-length plan) yields at least one biddable item: a needed,
        # not-held, slow-to-self-craft step material with a live buy-anchor, an
        # NPC alternative to ceiling-bound the price, no open order, and a
        # three-way venue verdict of GE_POST. Fire-and-lose: posting creates an
        # open order that suppresses the item next cycle.
        return bool(ge_bid_candidates(state, game_data, ctx, TTL_CYCLES))

    if kind is MeansKind.MAINTAIN_CONSUMABLES:
        # Only when combat is the active means (a target is selected): carry
        # the food the chosen loadout's recovery eats (`ctx.loadout`,
        # docs/PLAN_consumable_utility.md increment 5) — heal prep for the
        # fight ahead. When Rest is the cheaper recovery the loadout eats
        # nothing and the rung never fires. The goal `map_means` builds is the
        # one this asks about.
        return maintain_consumables_goal(state, game_data, ctx) is not None

    if kind is MeansKind.BANK_EXPAND:
        if not ctx.bank_accessible:
            return False
        if state.bank_items is None:
            return False
        if game_data.bank_capacity == 0:
            return False
        # SAME composed decision the goal uses (expansion_fires: the proven
        # exact integer fill cross-multiply + the reserve safety gate, plus the
        # pocket-executability conjunct). The old guard re-typed a float fill
        # compare and the pre-fix bare `gold >= cost` — the exact SAFETY-HOLE
        # the core closed — so the arbiter admitted candidates
        # ExpandBankGoal.value then scored 0 (drift flagged 2026-07-06).
        # A bank expansion is never a reserved gear code, so the player threads
        # reserve_floor(state, gd, None) as ctx.gold_reserve, mirroring the goal.
        # `account_gold` is imported directly: progression_reserve reaches this
        # package only through `tiers.equip_value`, which `tiers/__init__` pulls
        # WITHOUT means, so there is no cycle in either import order. Only
        # `reserve_floor` stays on the ctx, because it needs game_data and the
        # player already computes it. (The goal also raises `used` by the
        # active-profile floor — history-dependent; the means guard has no
        # history and keeps the plain count, as before.)
        return expansion_fires(
            len(state.bank_items), game_data.bank_capacity, state.gold,
            account_gold(state), game_data.next_expansion_cost, ctx.gold_reserve,
            TRIGGER_FILL_NUM, TRIGGER_FILL_DEN,
        )

    # MeansKind.WAIT: always-firing last-resort. Position-last in
    # DISCRETIONARY_ORDER ensures every other means gets a chance before
    # this candidate is considered by select_pure's positional walk.
    # (Exhaustive over MeansKind — anything else is unreachable.)
    return kind is MeansKind.WAIT


def means_fires(kind: MeansKind, state: WorldState, game_data: GameData,
                history: LearningStore | None, ctx: SelectionContext) -> bool:
    """Whether ONE means kind fires — the single-kind public face of `_fires`.

    `StrategyArbiter.select` needs exactly one predicate BEFORE the rest:
    `PURSUE_TASK`, which decides whether the objective step is task-suppressed and
    therefore whether the step has a protection profile to bind onto the ctx. The
    remaining kinds are evaluated (via `active_means`) AFTER that binding, because
    four of them depend on `ctx.step_profile`: SELL_IDLE, RECYCLE_SURPLUS,
    DRAIN_BANK_JUNK read the keep authority (which reads `ctx.step_profile`), and
    GE_BID reads `ctx.step_profile` directly for its per-cycle GOAL_MATERIALS demand.
    Evaluating them on the unbound ctx
    made the predicate and the goal it maps to disagree (the predicate saw an EMPTY
    step profile, the goal saw the full one), so a means could fire on surplus its
    goal then refused to shed: a zero-length plan candidate.

    PURSUE_TASK itself reads only `state.task_*` and the learning history — no ctx
    field at all — so evaluating it before the binding is exactly the same verdict
    as after, which is what makes the ordering sound."""
    return _fires(kind, state, game_data, history, ctx)


def active_means(
    state: WorldState,
    game_data: GameData,
    history: LearningStore | None,
    ctx: SelectionContext,
) -> tuple[list[MeansKind], list[MeansKind]]:
    """Return (collect_reward, discretionary) — triggered means in declared band order.

    history accepted for parity / used by the cancel predicates (low-yield, pivot).

    CALL ORDER (load-bearing): the caller must bind `ctx.step_profile` BEFORE
    calling this — SELL_IDLE / RECYCLE_SURPLUS / DRAIN_BANK_JUNK read the keep
    authority, which reads that field, and GE_BID reads it directly. See `means_fires`.
    """
    collect = [k for k in COLLECT_REWARD_ORDER if _fires(k, state, game_data, history, ctx)]
    discretionary = [k for k in DISCRETIONARY_ORDER if _fires(k, state, game_data, history, ctx)]
    return collect, discretionary

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
    should_expand_bank,
)
from artifactsmmo_cli.ai.consumable_supply import maintain_consumables_fires
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.ge_bid import ge_bid_candidates
from artifactsmmo_cli.ai.ge_order_config import TTL_CYCLES
from artifactsmmo_cli.ai.learning.projections import low_yield_cancel_fires
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.recycle_surplus import recyclable_surplus
from artifactsmmo_cli.ai.task_alignment import task_advances_progression
from artifactsmmo_cli.ai.task_decision import PIVOT, PURSUE, task_decision
from artifactsmmo_cli.ai.task_horizon import HORIZON_OUT_OF_REACH, resolve_task_horizon
from artifactsmmo_cli.ai.thresholds import PRESSURE_HIGH_FRACTION
from artifactsmmo_cli.ai.tiers.guards import (
    SelectionContext,
    _used_fraction,
)
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState

# Semantic name for this module's sell-pressure gate, bound to the SHARED
# single-source constant (thresholds.py pressure ladder). It used to be a
# re-typed literal (0.85) — the drift the thresholds consolidation was built
# to kill; the local name is kept because the ladder's proven mutation
# anchors bind to the usage lines. (BANK_EXPAND's fill gate now lives inside
# the shared should_expand_bank core — no local constant.)
SELL_PRESSURE_FRACTION = PRESSURE_HIGH_FRACTION

# Minimum UNMET sibling demand (units of one material) that justifies pausing
# this character's own objective step to produce for a sibling. Read by
# `_fires(SUPPLY_BANK, …)` off `ctx.supply_target`'s third component — the
# still-unmet quantity `_pick_supply_target` computed, already net of what the
# requester holds and of what the shared bank already stocks.
#
# WHY A THRESHOLD AT ALL. 2026-08-01: SUPPLY_BANK moved OUT of
# DISCRETIONARY_ORDER (below the objective step, where it never won a single
# cycle of the traced four-character run) and INTO COLLECT_REWARD_ORDER, above
# the step. Unconditional promotion was considered and DECLINED: with five
# characters each publishing their root's closure demand every cycle, a
# fires-on-any-demand rung would have them serving each other most cycles and
# levelling slowly. This constant is the whole of what prevents that — it is
# load-bearing, not decoration.
#
# WHY 10, DERIVED NOT INVENTED. Two sources agree:
#   (a) Live traces. Across the 44 `play-trace-*.jsonl` runs on hand, every
#       non-null `supply_target` carried demand exactly 10 (copper_ore x10 twice,
#       ash_wood x10 once). A `>=` test at 10 therefore keeps firing on every
#       real request observed so far — the promotion is not made inert by its
#       own gate.
#   (b) The recipe graph. Running `recipe_closure.closure_demand(root, 1, …)`
#       over all 321 craftable roots in `formal/sim/game_data_snapshot.json` and
#       taking, per root, the LARGEST base-material quantity (the quantity
#       `_pick_supply_target` maximises over) gives this distribution:
#         1:25  2:6  3:1  4:3  5:9  6:8  7:1  |  10:12  12:2  15:11  20:2
#         24:15  28:5  30:6  32:2  35:3  36:12  40:8  42:11  48:13  49:9
#         50:25  54:4  56:1  60:15  66:1  70:15  80:50  100:29  110:1  120:14
#         192:2
#       There is an EMPTY BAND at 8 and 9: no root's peak base demand lands
#       there. So every threshold in 8..10 partitions the roots identically —
#       53 roots (16.5%) below, 268 (83.5%) at or above. The cut is a real gap
#       in the data, not a knife edge, and 10 is the value in that gap that also
#       matches (a) exactly.
#
# WHAT THIS BUYS: a character pauses its own chain only for a request of
# genuinely bulk size — the 24/50/80/120-unit asks that dominate the recipe
# graph and cost the requester hours of self-gathering. 83.5% of roots' peak
# requests still preempt the objective step.
#
# WHAT IT GIVES UP: sub-threshold demand no longer reaches SUPPLY_BANK AT ALL,
# because the rung left DISCRETIONARY_ORDER — there is no low-priority fallback
# slot any more. A sibling wanting <10 units, or wanting the last few units of a
# request already mostly filled, is told (by silence) to gather them itself:
# 1-9 units of one material is a handful of gather actions, cheaper to self-serve
# than to route through the bank. The measured cost of that loss is small — in
# the traced runs SUPPLY_BANK was selected zero times from the discretionary
# band, because the objective step outranked it on every cycle a step existed.
#
# THE SECOND ARM (ctx.asymmetric_demand, Task 4). The rationale above assumes
# the asker CAN self-serve — that a sub-threshold request is a handful of
# gather actions the asker itself could run. That assumption breaks whenever
# the requested code is skill-gated out of the asker's own reach:
# `sibling_demand_asymmetric` (Task 2) already did the work of proving the
# asker cannot make it, at ANY quantity, this side of a level-up. A request
# like that is never a cheaper self-serve alternative — it is simply blocked —
# so it is worth a sibling's cycle even at the observed live size of 1. That
# asymmetry (one role can fill a gap another role structurally cannot) is the
# whole point of holding a role at all, and it is a SEPARATE gate from bulk
# size: `ctx.asymmetric_demand` fires regardless of SUPPLY_DEMAND_MIN, it does
# not raise or lower the bulk threshold above.
SUPPLY_DEMAND_MIN = 10


class MeansKind(Enum):
    CLAIM_PENDING = "claim_pending"
    COMPLETE_TASK = "complete_task"
    SELL_PRESSURED = "sell_pressured"
    LOW_YIELD_CANCEL = "low_yield_cancel"
    TASK_CANCEL = "task_cancel"
    PURSUE_TASK = "pursue_task"
    ACCEPT_TASK = "accept_task"
    TASK_EXCHANGE = "task_exchange"
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
    SUPPLY_BANK = "supply_bank"  # 2026-08-01: produce a material a SIBLING needs.
    CURRENCY_TURNIN = "currency_turnin"  # 2026-08-16: spend/surrender a dual-role currency.


COLLECT_REWARD_ORDER: tuple[MeansKind, ...] = (
    MeansKind.CLAIM_PENDING,
    MeansKind.COMPLETE_TASK,
    MeansKind.SELL_PRESSURED,
    MeansKind.LOW_YIELD_CANCEL,
    MeansKind.TASK_CANCEL,
    # 2026-08-01, human ruling: SUPPLY_BANK is promoted out of
    # DISCRETIONARY_ORDER to here, ABOVE the objective step, so a character can
    # pause its own chain to serve a sibling's declared, SUBSTANTIAL request
    # (`SUPPLY_DEMAND_MIN` is what makes "substantial" mean something — see its
    # comment block). Below the step it was unreachable: a character essentially
    # always has an objective step, and the traced four-character run selected
    # SUPPLY_BANK zero times in 48 cycles despite the rung being armed.
    #
    # POSITION: LAST in this group, deliberately. The other five rungs are
    # one-or-few-action bookings of an already-earned outcome (claim the pending
    # items, hand in a finished task, shed under space pressure, cut a losing
    # task) and each self-quiets after firing, so letting them go first costs
    # SUPPLY_BANK at most a cycle. SUPPLY_BANK is the opposite shape — an
    # open-ended gather-then-bank production run — and putting it first would
    # park a completed task's reward, or a >=85%-full bag, behind a chain of
    # dozens of actions. Ordering it last keeps the promotion (it still outranks
    # the objective step, which is the entire point) without letting production
    # preempt reward collection or pressure relief.
    MeansKind.SUPPLY_BANK,
    # 2026-08-16, fleet-currency-turn-in epic (Task 6): a fleet-wide dual-role
    # holding (an item that is BOTH worn and a vendor's payment currency, e.g.
    # `lich_race_medal`, currency for `lich_race_trophy` @ archaeologist) has
    # already been resolved into a per-cycle decision for THIS character by
    # Task 5's `GamePlayer._resolve_turn_in`: either it is the elected buyer
    # (`ctx.turn_in.buyer == self`) or it lost the election and owes the
    # winner its whole holding (`ctx.recall`). Both branches are threaded onto
    # `SelectionContext` as DATA — this means only asks "is one of them set",
    # the same seam `SUPPLY_BANK` uses for `ctx.supply_target`.
    #
    # POSITION: immediately after SUPPLY_BANK, same reasoning as SUPPLY_BANK's
    # own position comment directly above — ABOVE the objective step (so a
    # completed election is not left to rot behind whatever gear `J` is
    # chasing, which per the Evidence section it never resolves to a turn-in
    # purchase on its own) and LAST among the one-or-few-action collect-reward
    # rungs (so a pending reward claim or a >=85%-full bag is never parked
    # behind it). Unlike SUPPLY_BANK this means carries NO demand-size gate:
    # `turn_in_ready_pure` (ai/currency_turnin.py) already requires the FULL
    # vendor price be reachable before Task 5 ever sets `ctx.turn_in`, so
    # every firing cycle is one the fleet can actually complete — there is no
    # sub-threshold case to filter the way SUPPLY_DEMAND_MIN filters SUPPLY_BANK.
    MeansKind.CURRENCY_TURNIN,
    # 2026-08-19, USER ruling + S-051: ACCEPT_TASK is promoted out of
    # DISCRETIONARY_ORDER to here. Below the step it was unreachable for the same
    # reason SUPPLY_BANK was — a character essentially always has an objective
    # step (14,064 of 14,064 traced cycles) — and the fleet has held a task in 0
    # of 63,310 cycles, so every rung downstream of it has never run.
    #
    # It is gated on `ctx.draw_owed`, which is what makes the promotion sound
    # rather than a livelock: accept and discard both sit above the step, so an
    # ungated redraw would spin between them at a coin a cycle. The gate is
    # mirrored in `acceptTaskFires` and is the conjunct the Lean descent argument
    # rests on.
    #
    # POSITION: LAST in this group. A one-action booking must not preempt a
    # resolved turn-in election or a sibling's supply request — the same
    # argument SUPPLY_BANK and CURRENCY_TURNIN make for their own positions —
    # and it is still AFTER both cancel rungs, so a dead draw goes back before
    # a new one is taken.
    MeansKind.ACCEPT_TASK,
)
DISCRETIONARY_ORDER: tuple[MeansKind, ...] = (
    MeansKind.PURSUE_TASK,
    MeansKind.TASK_EXCHANGE,
    MeansKind.MAINTAIN_CONSUMABLES,  # prep heals for combat before idle housekeeping
    MeansKind.SELL_IDLE,
    MeansKind.RECYCLE_SURPLUS,
    MeansKind.BANK_EXPAND,
    # Opportunistic cheap acquisition: post a GE buy order for a slow-to-craft
    # objective material. Below the housekeeping investments (recycle/expand),
    # above pure junk-drain — acquiring a needed material beats draining junk.
    MeansKind.GE_BID,
    # Lowest-value housekeeping (15), just above WAIT: drain over-cap bank junk
    # only when nothing better — incl. a bank-expansion investment — is pending.
    MeansKind.DRAIN_BANK_JUNK,
    MeansKind.WAIT,
)


def _tasks_coin_total(state: WorldState) -> int:
    return state.inventory.get(TASKS_COIN_CODE, 0) + (state.bank_items or {}).get(TASKS_COIN_CODE, 0)


def _fires(kind: MeansKind, state: WorldState, game_data: GameData,
           history: LearningStore | None, ctx: SelectionContext) -> bool:
    if kind is MeansKind.CLAIM_PENDING:
        return bool(state.pending_items)

    if kind is MeansKind.COMPLETE_TASK:
        return (bool(state.task_code) and state.task_total > 0
                and state.task_progress >= state.task_total)

    if kind is MeansKind.SELL_PRESSURED:
        # A buyer that can take it NOW — never the window-blind "some held code
        # has a located buyer" test. See `sellable_tradeable_now`.
        return (_used_fraction(state) >= SELL_PRESSURE_FRACTION
                and sellable_tradeable_now(state, game_data))

    if kind is MeansKind.LOW_YIELD_CANCEL:
        return low_yield_cancel_fires(state, game_data, history)

    if kind is MeansKind.TASK_CANCEL:
        if not state.task_code:
            return False
        # S-052: no coin, no discard. The task then stays INERT — carried, not
        # worked and (since the gear latch's standing arm now reads the horizon)
        # not gear-reviewed either — while the character does other work. USER
        # 2026-08-25: "It is a known condition that Tasks might be uncancelable
        # until we get a coin. Tasks can remain inert until that condition is met."
        # POCKET only, matching `TaskCancelAction.is_applicable`: a banked coin
        # cannot be spent at the taskmaster and firing on one would be a rung with
        # nothing to do, the shape this ladder has already been bitten by twice.
        if state.inventory.get(TASKS_COIN_CODE, 0) < 1:
            return False
        # S-048: a draw whose target advances neither the character's level nor a
        # skill is dead work. Asked BEFORE the pivot rule and without `history`,
        # because it is a fact about game data and the character, not about
        # observed rates — a character with no learning store still knows a grey
        # task when it sees one.
        if not task_advances_progression(state, game_data):
            return True
        if state.task_type == "monsters":
            # THE ONE-LEVEL HORIZON (USER 2026-08-25), replacing `task_decision`'s
            # combat arm for this rung. That arm is `req_is_combat -> PIVOT` over
            # `task_feasibility`'s level proxy — a monster more than
            # MONSTER_LEVEL_MARGIN (2) levels above the character — and a level
            # proxy is the wrong question twice over: it discards a high-level
            # monster the character's gear already beats, and it keeps an in-band
            # one no gear in the catalogue can beat. `task_horizon` asks the fight
            # itself. `task_decision` is untouched (it is the formalisation target
            # of `Formal/TaskDecision.lean` and still serves PURSUE_TASK and the
            # items arm below).
            #
            # THIS FUNCTION IS THE ONLY PRODUCER OF THE CANCEL REASON, across all
            # three arms (S-048 above, the horizon here, `task_decision` below).
            # `TaskCancelGoal` — the goal `map_means` builds once this returns
            # True — used to re-derive the third arm on its own and report the
            # answer as its `value`, so a rung that fired for either of the other
            # two emitted a goal reporting 0.0. Measured on the offline corpus,
            # that was three of three cells where the arbiter actually SELECTS it.
            # The goal now reports the scalar and asks nothing;
            # `test_the_rung_and_the_goal_it_emits_report_the_same_answer` is what
            # fails if a second reader is ever added back.
            horizon = resolve_task_horizon(state, game_data)
            return horizon is not None and horizon.verdict == HORIZON_OUT_OF_REACH
        return (history is not None
                and task_decision(state, game_data, history) == PIVOT)

    if kind is MeansKind.PURSUE_TASK:
        return (state.task_type == "items"
                and bool(state.task_code) and state.task_total > 0
                and state.task_progress < state.task_total
                and history is not None
                and task_decision(state, game_data, history) == PURSUE)

    if kind is MeansKind.ACCEPT_TASK:
        if state.task_code:
            return False
        # S-051 + the no-immediate-redraw rule: a draw must be OWED. Mirrors
        # `Formal.Liveness.ProductionLadder.acceptTaskFires`, which carries the
        # same conjunct so the rung can descend `drawOwedFlag` from above the
        # objective step.
        if not ctx.draw_owed:
            return False
        # Defer AcceptTask whenever the player has GEAR-CHAIN work to do.
        # An immediate AcceptTask after TaskComplete re-locks the cycle
        # into another items task before UpgradeEquipment can fire,
        # leaving target gear unworn for hundreds of cycles. Two
        # deferral conditions:
        #   (a) target gear is OWNED but UNEQUIPPED → UpgradeEquipment
        #       should win first (one-action equip);
        #   (b) target gear is CRAFTABLE under current skill levels →
        #       the fallback walk should drive the gather/craft chain
        #       rather than accept another task that competes for the
        #       same materials.
        # Both conditions are about the AI's own gear pipeline, not the
        # task economy — accepting a task while gear is in progress
        # creates contention for materials (copper_bar) that the gear
        # chain needs. Trace 2026-06-06 12:28: 2 copper_daggers crafted
        # via CraftRelief never equipped; full armor set never started
        # despite 2300+ gold and crafting skills at level 6+.
        equipped = {c for c in state.equipment.values() if c is not None}
        for code in ctx.target_gear:
            if code in equipped:
                continue
            if state.inventory.get(code, 0) > 0:
                return False  # owned + unequipped → defer for UpgradeEquipment
            stats = game_data.item_stats(code)
            if stats is None or not stats.crafting_skill:
                continue
            if state.skills.get(stats.crafting_skill, 1) >= stats.crafting_level:
                return False  # craftable now → defer for gear chain
        return True

    if kind is MeansKind.TASK_EXCHANGE:
        return _tasks_coin_total(state) >= ctx.task_exchange_min_coins

    if kind is MeansKind.SELL_IDLE:
        return (_used_fraction(state) < SELL_PRESSURE_FRACTION
                and sellable_tradeable_now(state, game_data))

    if kind is MeansKind.RECYCLE_SURPLUS:
        # Idle/low-pressure only: recovered materials need room to land (under
        # pressure the deposit/discard guards handle space). Fires when the keep
        # authority (`ai/inventory_keep`) licenses the destruction of surplus
        # craftable gear — copies above BOTH keep_in_bag and keep_owned, so the
        # equipped copy, the profile's demand and the working tool are never it.
        return (_used_fraction(state) < SELL_PRESSURE_FRACTION
                and bool(recyclable_surplus(state, game_data, ctx)))

    if kind is MeansKind.DRAIN_BANK_JUNK:
        # Idle/low-pressure only: the withdraw mints items into the bag, so it
        # needs free slots to land (under pressure the deposit/discard guards
        # handle space). Fires when the keep authority (`ai/inventory_keep`)
        # licenses the destruction of over-cap BANK junk — copies above
        # `keep_owned`, so the last tool, the last weapon and the profile's gear
        # demand are never withdrawn into the discard ladder's mouth.
        return (_used_fraction(state) < SELL_PRESSURE_FRACTION
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

    if kind is MeansKind.SUPPLY_BANK:
        # ctx.supply_target is None whenever there is no live sibling demand
        # this character's role can serve — which is every cycle of a
        # single-character run, so this means is inert without `--all`.
        #
        # DEMAND GATE (2026-08-01): this rung now sits ABOVE the objective step,
        # so firing it costs the character its own progress for the length of a
        # production run. It fires only for a request of at least
        # SUPPLY_DEMAND_MIN still-unmet units — see that constant for the
        # derivation and for what the gate buys and gives up. The third tuple
        # component is the UNMET demand (`_pick_supply_target`), not the goal's
        # absolute banked target (the second), which already includes stock the
        # bank holds and so would clear any threshold on inventory the fleet
        # already owns.
        #
        # ASYMMETRY GATE (Task 4): OR'd with the bulk gate, not a replacement
        # for it. A request whose item code is in `ctx.asymmetric_demand`
        # fires at ANY unmet-demand size, because that set (Task 2/3) only
        # ever holds codes at least one sibling is skill-gated out of making
        # for itself — see SUPPLY_DEMAND_MIN's comment for why that breaks the
        # self-serve-is-cheaper assumption the bulk threshold relies on.
        target = ctx.supply_target
        if target is None:
            return False
        return target[2] >= SUPPLY_DEMAND_MIN or target[0] in ctx.asymmetric_demand

    if kind is MeansKind.CURRENCY_TURNIN:
        # Fires for BOTH sides of a resolved election: the buyer and every
        # holder asked to surrender. `ctx.turn_in` is set on both (a loser
        # carries the SAME turn-in with the winner named as `buyer`, plus its
        # own `ctx.recall` — the two are not mutually exclusive), so WHICH
        # side this character is on is decided by identity in
        # `strategy_driver.map_means` (`turn_in.buyer == state.character`),
        # never by the presence or absence of a recall. Neither field is set
        # on an uninvolved character: Task 5's `_resolve_turn_in` writes them
        # only for a character that itself qualified as a candidate buyer or
        # currently holds the currency a live claim is waiting on.
        return ctx.turn_in is not None or ctx.recall is not None

    if kind is MeansKind.MAINTAIN_CONSUMABLES:
        # Only when combat is the active means (a target is selected): keep a
        # heal stockpile for MID-FIGHT drinking. NOT "instead of resting between
        # fights" -- resting between fights is cheap since Rest went dynamic
        # (max(3, ceil(missing%))s, refills to full), so stocking to avoid it
        # never pays. Gated on under-stock + craftable-better-heal (the shared
        # pure predicate). PLAN #6a.
        if ctx.combat_monster is None:
            return False
        return maintain_consumables_fires(state, game_data)

    if kind is MeansKind.BANK_EXPAND:
        if not ctx.bank_accessible:
            return False
        if state.bank_items is None:
            return False
        if game_data.bank_capacity == 0:
            return False
        # SAME proven decision the goal uses (should_expand_bank: exact
        # integer fill cross-multiply + the gold-reserve safety gate). The
        # old guard re-typed a float fill compare and the pre-fix bare
        # `gold >= cost` — the exact SAFETY-HOLE the core closed — so the
        # arbiter admitted candidates ExpandBankGoal.value then scored 0
        # (drift flagged 2026-07-06). A bank expansion is never a reserved
        # gear code, so the player threads reserve_floor(state, gd, None)
        # as ctx.gold_reserve (means.py cannot import progression_reserve —
        # tiers package cycle), mirroring the goal. (The goal also raises `used` by the
        # active-profile floor — history-dependent; the means guard has no
        # history and keeps the plain count, as before.)
        return should_expand_bank(
            len(state.bank_items), game_data.bank_capacity, state.gold,
            game_data.next_expansion_cost, ctx.gold_reserve,
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

"""Shed-reachability behavioral-completeness census (disposal-unification epic,
part 2 — the ACCEPTANCE gate for both defects the live diagnosis named).

The SIXTH census in the craft-completeness family (`audit/craft_completeness.py`,
`audit/inventory_completeness.py`, `audit/recycle_source_completeness.py`,
`audit/obtain_parity_completeness.py`, `audit/requirement_parity.py`): a cell
grid, a thin harness that drives the REAL production selector, a structural
verdict, and honest gap classes with an UNEXPLAINED residual that must reach 0.

THE TWO DEFECTS IT PINS SHUT
(`.superpowers/sdd/2026-08-01-emergent-specialization/currency-and-piles-report.md`):

  * DEFECT A — STARVATION. A shed rung can be licensed to move thousands of
    copies and still never run. Measured over five `play-trace-*.jsonl` runs (54
    cycles): `drain_bank_junk` fired 44 times and was selected ZERO, `sell_idle`
    fired 32 and was selected ZERO, while the bank grew to 2273 shedable copies
    across 18 codes. Two independent mechanisms can cause it and this census
    cannot tell them apart, ON PURPOSE — both are the same failure to the bot:
      - BAND: the rung sits below the always-plannable objective step;
      - PLANNABILITY: the rung wins its slot and returns plan_len=0. The drain
        was in exactly this state before part 2 (offline probe against the
        committed bundle: 1993 licensed copies, `nodes_explored=8`,
        `timed_out=False`, `plan_len=0` — a STRUCTURAL refusal, because
        all-or-nothing satisfaction needs every copy in a 120-quantity bag at
        once). A census that only checked band order would have shipped a
        hoisted rung that still could not act.
    So the LIVENESS verdict is the strongest available: the arbiter must SELECT
    the rung AND come back with a non-empty plan.

  * DEFECT B — CONTRADICTION. The bank drain and the overstock disposal route
    used to disagree, so the drain withdrew what the route deposited straight
    back. Part 1 unified them on `ai/keep_valuation.worth_keeping` and proved
    `drained_is_never_deposited` / `withdrawn_is_never_redeposited` in
    `formal/Formal/DisposalRoute.lean`. The proof is over the pure cores; this
    census is the ADAPTER-level twin, swept over the whole committed catalog, so
    a future edit that stops feeding those cores one number is caught even
    though the theorems still hold.

WHY LIVENESS NEEDS A QUIET CELL NEXT TO IT. "The rung was selected" is trivially
achievable by hoisting it unconditionally, which would park progression forever —
the failure mode the epic's own brief calls out. `DRAIN_QUIET` is the other half:
in a world where the rung is licensed NOTHING it must NOT be selected, and the
bot must still have a plan. A grid with only the liveness cell would pass an
unconditional hoist, and would therefore be proving nothing about the gate.

THE SEAM IS `StrategyArbiter.select` — production's own selector, and the only
seam at which defect A means anything: the COLLECT-band hoist lives in
`_build_candidates` INSIDE `select`, so a harness that planned a goal directly
would bypass the very decision under test and every cell would be green by
construction.
"""

import dataclasses
from dataclasses import dataclass
from enum import Enum

from artifactsmmo_cli.ai.accumulation_sell import bank_sellable_surplus
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.deposit_item import DepositItemAction
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.bank_drain import bank_drain_excess
from artifactsmmo_cli.ai.disposal_route import overstock_disposal
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.recycle_surplus import recyclable_surplus
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from artifactsmmo_cli.ai.tiers.meta_goal import ReachCharLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.strategy import StrategyDecision
from artifactsmmo_cli.ai.world_state import SKILL_NAMES, WorldState

CENSUS_LEVEL = 11
"""Character level for every cell — the live diagnosis character's level (R2D2,
L11 with a 2273-copy bank), so the keep valuation's level-sensitive terms are
read at the level the defect was measured at."""

CENSUS_SKILL_LEVEL = 5
"""Every skill at this level. Low enough that the bulk raw materials the drain
targets are genuinely far from their consumers (which is why they pile up), high
enough that `RECYCLE_SELECTABLE`'s gear is at its own recipe level."""

CENSUS_BAG_QUANTITY_MAX = 120
CENSUS_BAG_SLOTS_MAX = 20
"""The live bag shape (R2D2: 120 quantity, 20 slots). The QUANTITY cap is
load-bearing for defect A: it is what makes all-or-nothing satisfaction
unreachable for a bank pile, and a census with an unbounded bag would never see
the plan_len=0 half of the starvation."""

CENSUS_STEP_LEVEL = CENSUS_LEVEL + 1
"""The objective step every cell carries: reach the next character level. A
combat/grind step is essentially always plannable — that is precisely WHY the
discretionary band is starved — so it is the honest adversary for a shed rung."""

DRAIN_BANK = {"sap": 703, "raw_wolf_meat": 509, "raw_chicken": 272,
              "raw_beef": 161, "gudgeon": 143, "wolf_hair": 124,
              "raw_porkchop": 104}
"""THE LIVE PILE, code for code and copy for copy (probe 2026-08-05, R2D2's real
bank; the full hoard was 2273 copies over 18 codes and these are its seven
deepest). Not a synthetic number: the census asks whether the bot can shed the
hoard it actually has."""

SELL_CODE = "sap"
SELL_BANK_COPIES = 703
SELL_EVENT = "timber_merchant"
"""The sell cell's world. `sap`'s only buyer on the committed bundle is the
`timber_merchant`, an EVENT npc, so the cell declares that merchant's window
OPEN — otherwise `NpcSellAction.is_applicable` refuses and the cell would fail
for a reason that has nothing to do with starvation. Declaring it is not a
convenience: an open merchant window is the exact world in which "shed the bank
pile for gold" is the right answer, and the bag holds ZERO copies, so the sale is
reachable ONLY through the bank arm this epic added."""

RECYCLE_CODE = "copper_helmet"
RECYCLE_BAG_COPIES = 30
RECYCLE_EQUIP_SLOT = "helmet_slot"
"""The CONTROL cell: the one shed rung that was already hoisted (2026-07-05), at
the hoard size that motivated it (copper_helmet x30). If this cell goes red the
harness is broken, not the two rungs under test — which is what keeps a red DRAIN
or SELL cell attributable."""

COHERENCE_BANK_DEPTH = 500
"""Banked copies of the ONE code under test in each step of the contradiction
sweep. Deep enough to be over most codes' keep quantity (the deepest live pile
was 703 and the great majority of the bundle's reachable-consumer demands are far
below this), so the sweep exercises the drain-licensed side of the invariant on
hundreds of codes rather than on the handful that happen to be over cap."""


class ShedCellKind(Enum):
    """The five cells. The grid is TOTAL over this enum (`shed_grid` raises on a
    member with no scenario), so a sixth question cannot be added to the epic
    without the census exercising it."""

    DRAIN_SELECTABLE = "drain_selectable"
    DRAIN_QUIET = "drain_quiet"
    SELL_SELECTABLE = "sell_selectable"
    RECYCLE_SELECTABLE = "recycle_selectable"
    ROUTE_COHERENCE = "route_coherence"


DRAIN_REPR = "DrainBankJunk"
SELL_REPR = "SellInventory"
RECYCLE_REPR = "RecycleSurplus"

_EXPECTED_RUNG: dict[ShedCellKind, str] = {
    ShedCellKind.DRAIN_SELECTABLE: DRAIN_REPR,
    ShedCellKind.DRAIN_QUIET: DRAIN_REPR,
    ShedCellKind.SELL_SELECTABLE: SELL_REPR,
    ShedCellKind.RECYCLE_SELECTABLE: RECYCLE_REPR,
}
"""The rung each cell is ABOUT, by the repr the arbiter's candidate walk keys on.
`ROUTE_COHERENCE` has none — it drives no selector."""


@dataclass(frozen=True)
class ShedCell:
    """One census point: a world (bag, bank, live events, worn gear) plus the
    rung the cell is about and whether that rung MUST or MUST NOT win."""

    kind: ShedCellKind
    bag: dict[str, int]
    bank: dict[str, int]
    events: tuple[str, ...] = ()
    equip_slot: str | None = None
    equip_code: str | None = None
    must_be_selected: bool = True
    """True = LIVENESS (the rung is licensed real work and must win its cycle).
    False = QUIET (the rung is licensed nothing and must NOT win)."""


@dataclass(frozen=True)
class ShedResult:
    """One census outcome, flat and render-ready."""

    kind: str
    rung: str
    licensed: int
    contradictions: int
    swept: int
    goal: str
    plan: tuple[str, ...]
    planner_failed: bool
    passed: bool
    gap: str | None


def census_ctx(bank_accessible: bool = True) -> SelectionContext:
    """The base SelectionContext. `step_profile` is deliberately NOT filled in:
    `StrategyArbiter.select` binds it from the step goal it resolves — the same
    derivation production uses, and the one the keep authority (hence every shed
    licence in this census) reads. Pre-binding it would fork that derivation.

    `combat_monster=None` keeps the REST_FOR_COMBAT guard quiet."""
    return SelectionContext(
        bank_accessible=bank_accessible, bank_required_level=0,
        bank_unlock_monster=None, initial_xp=0, task_exchange_min_coins=0,
        combat_monster=None)


def _require(code: str, game_data: GameData) -> str:
    """`code`, or a loud failure. The census runs on REAL game data: a missing
    catalog entry means the bundle changed under the census, and defaulting
    (skipping the cell, faking the item) would silently shrink the grid — the one
    thing a completeness census may never do."""
    if game_data.item_stats(code) is None:
        raise ValueError(
            f"census item {code!r} is not in the game catalog — the "
            f"shed-reachability census cannot be built from data the game does "
            f"not have")
    return code


def scenario_for(kind: ShedCellKind, game_data: GameData) -> ShedCell:
    """The cell realizing `kind` — one per enum member, so the grid is TOTAL over
    `ShedCellKind` (a new kind with no scenario raises here rather than quietly
    dropping out of the census)."""
    if kind is ShedCellKind.DRAIN_SELECTABLE:
        return ShedCell(kind=kind, bag={},
                        bank={_require(c, game_data): q
                              for c, q in DRAIN_BANK.items()})
    if kind is ShedCellKind.DRAIN_QUIET:
        # An EMPTY bank: the drain is licensed nothing, so a rung that still wins
        # is hoisting unconditionally.
        return ShedCell(kind=kind, bag={}, bank={}, must_be_selected=False)
    if kind is ShedCellKind.SELL_SELECTABLE:
        return ShedCell(kind=kind, bag={},
                        bank={_require(SELL_CODE, game_data): SELL_BANK_COPIES},
                        events=(SELL_EVENT,))
    if kind is ShedCellKind.RECYCLE_SELECTABLE:
        return ShedCell(kind=kind,
                        bag={_require(RECYCLE_CODE, game_data): RECYCLE_BAG_COPIES},
                        bank={}, equip_slot=RECYCLE_EQUIP_SLOT,
                        equip_code=RECYCLE_CODE)
    if kind is ShedCellKind.ROUTE_COHERENCE:
        # An EMPTY base bank: the sweep hands each code its OWN single-code bank
        # (`_single_code_bank`), because `disposal_route`'s DEPOSIT arm is
        # conjoined with `bank_has_room` and a bank holding all 522 codes is far
        # over the bundle's 50-entry capacity.
        return ShedCell(kind=kind, bag={}, bank={})
    raise ValueError(f"no census scenario for ShedCellKind {kind!r}")


def census_state(cell: ShedCell, game_data: GameData) -> WorldState:
    """The census character for `cell`: the stated bag and bank, the live bag
    shape, and any declared event window or worn copy.

    The same state feeds the selector and the classifier, so the arbiter and the
    verdict always judge the SAME world."""
    equipment: dict[str, str] = {}
    if cell.equip_slot is not None and cell.equip_code is not None:
        equipment[cell.equip_slot] = cell.equip_code
    return scenario_state(
        ScenarioCharacter(
            name="shed_reachability_audit",
            level=CENSUS_LEVEL,
            skills={skill: CENSUS_SKILL_LEVEL for skill in SKILL_NAMES},
            equipment=equipment,
            inventory=dict(cell.bag),
            inventory_max=CENSUS_BAG_QUANTITY_MAX,
            inventory_slots_max=CENSUS_BAG_SLOTS_MAX,
            bank=dict(cell.bank),
            active_events=cell.events,
        ),
        game_data)


def licensed_work(cell: ShedCell, state: WorldState,
                  game_data: GameData) -> int:
    """Copies the cell's rung is licensed to move — the authority's own answer,
    never a hand-written number.

    This is the census's premise: defect A is "licensed to do work and never
    runs", so a cell whose rung is licensed NOTHING cannot exhibit it (and a
    QUIET cell whose rung IS licensed something is not quiet). `_check_cell`
    enforces both directions."""
    ctx = census_ctx()
    if cell.kind is ShedCellKind.SELL_SELECTABLE:
        return sum(bank_sellable_surplus(state, game_data, ctx).values())
    if cell.kind is ShedCellKind.RECYCLE_SELECTABLE:
        return sum(recyclable_surplus(state, game_data, ctx).values())
    return sum(bank_drain_excess(state, game_data, ctx).values())


def _check_cell(cell: ShedCell, state: WorldState, game_data: GameData) -> None:
    """CHECK THE CELL TESTS WHAT IT NAMES, or raise. Two ways a starvation cell
    can lie about itself, both fatal to the census:

    * a LIVENESS cell whose rung is licensed NOTHING would pass or fail for
      reasons unrelated to starvation — there is no work to be starved of;
    * a QUIET cell whose rung IS licensed something is not testing the gate, it
      is testing a second liveness case under a name that claims the opposite.

    Measured with the production licences themselves (`bank_drain_excess`,
    `bank_sellable_surplus`, `recyclable_surplus`), never re-derived here.

    `ROUTE_COHERENCE` drives no rung, so the licence premise does not apply to
    it. Its own way of lying is different and is checked here: a sweep in a world
    where the route can NEVER say DEPOSIT is green for the most boring possible
    reason. (The other half — the drain must license SOMETHING — is the `swept`
    counter, enforced by `shed_cell_verdict`.)"""
    if cell.kind is ShedCellKind.ROUTE_COHERENCE:
        if not deposit_arm_is_live(state, game_data):
            raise ValueError(
                "route_coherence: no catalog code routes to DEPOSIT in this "
                "world, so 'nothing drained is deposited' is vacuously true and "
                "the sweep would be green without testing anything")
        return
    work = licensed_work(cell, state, game_data)
    if cell.must_be_selected and work <= 0:
        raise ValueError(
            f"{cell.kind.value}: the authority licenses {work} copies — a "
            f"LIVENESS cell with no licensed work cannot exhibit starvation and "
            f"would pass or fail for an unrelated reason")
    if not cell.must_be_selected and work > 0:
        raise ValueError(
            f"{cell.kind.value}: the authority licenses {work} copies — a QUIET "
            f"cell must license NOTHING, or it is a liveness cell wearing the "
            f"wrong name")


def shed_grid(game_data: GameData) -> list[ShedCell]:
    """The census grid, DERIVED from `ShedCellKind`: one cell per kind, each
    checked against the production licences at its own state (`_check_cell`)."""
    cells = [scenario_for(kind, game_data) for kind in ShedCellKind]
    for cell in cells:
        _check_cell(cell, census_state(cell, game_data), game_data)
    return cells


def drive_selector(cell: ShedCell, state: WorldState,
                   game_data: GameData) -> tuple[Goal | None, list[Action], bool]:
    """What the REAL production selector chooses for `cell`'s state, plus whether
    any goal's search was INCONCLUSIVE (budget timeout or node cap).

    Drives `StrategyArbiter.select` — the WHOLE production selection seam the live
    bot runs each cycle (`ai/player.py`). THE SEAM IS THE POINT: the COLLECT-band
    hoist that this census exists to gate is built inside `select`, so any lower
    seam would test a decision production does not make.

    THE SECOND RETURN VALUE IS AN ANTI-LAUNDERING DEVICE, the rule the keep census
    paid for in blood: a cell whose rung "was not selected" BECAUSE some candidate
    ran out of budget has learned nothing about the ladder, and a world-limit gap
    class would happily explain it away.

    `history=None`: the census is offline and must be deterministic (a
    LearningStore would make selection depend on a live SQLite record)."""
    ctx = census_ctx()
    objective = CharacterObjective.from_game_data(game_data)
    actions = build_actions(game_data, state, objective,
                            bank_accessible=True, task_exchange_min_coins=0)
    arbiter = StrategyArbiter(GOAPPlanner(), None)
    arbiter.set_cycle(0)
    step = ReachCharLevel(level=CENSUS_STEP_LEVEL)
    decision = StrategyDecision(interrupt=None, chosen_root=step,
                                chosen_step=step, desired_state={})
    goal, plan, tried = arbiter.select(decision, state, game_data, actions, ctx)
    failed = any(bool(attempt.get("timed_out")) for attempt in tried)
    return goal, plan, failed


def stages_withdraw_then_sale(plan: list[Action], code: str) -> bool:
    """The plan reaches a BANKED pile: a `Withdraw(code)` strictly before an
    `NpcSell(code)`.

    Order is the whole obligation. `accumulation_sell.sellable_surplus` iterates
    `state.inventory`, so with zero copies in the bag the sale is reachable only
    if the plan stages the withdraw itself — a plan that merely withdraws is the
    DRAIN rung wearing a sell hat, and one that merely sells cannot execute."""
    withdraws = [i for i, a in enumerate(plan)
                 if isinstance(a, WithdrawItemAction) and a.code == code]
    sales = [i for i, a in enumerate(plan)
             if isinstance(a, NpcSellAction) and a.item_code == code]
    return bool(withdraws) and bool(sales) and withdraws[0] < sales[0]


def within_bag_bound(plan: list[Action], state: WorldState) -> bool:
    """The episode does not try to move the WHOLE hoard at once: the copies the
    plan withdraws fit the bag's free quantity.

    The per-cycle bound made structural. `WithdrawItemAction.is_applicable`
    enforces it per action, but a plan of several withdraws against a bag that
    empties in between would not be bounded by it, and the rate budget — not the
    bag — is what says an episode may be one or two requests. This is the check
    that a re-rank without a bound would fail."""
    return sum(a.quantity for a in plan
               if isinstance(a, WithdrawItemAction)) <= state.inventory_free


def is_contradiction(drained: int, routed: Action) -> bool:
    """DEFECT B's predicate: this code is licensed for withdrawal AND the
    disposal ladder would put it straight back in the bank.

    That is the withdraw/redeposit livelock, and
    `Formal.DisposalRoute.drained_is_never_deposited` says it cannot happen —
    over the PURE cores. This predicate is deliberately stated over the ADAPTERS'
    real outputs (`bank_drain.bank_drain_excess`'s quantity and
    `disposal_route.overstock_disposal`'s Action), because the theorem is only
    about production while the two adapters keep feeding those cores ONE number.
    Restating the arithmetic here instead would make the sweep a tautology: both
    sides read the same `worth_keeping` from the same state, so a re-derivation
    could never disagree with itself."""
    return drained > 0 and isinstance(routed, DepositItemAction)


def _single_code_bank(state: WorldState, code: str) -> WorldState:
    """`state` with the bank holding ONLY `code`, at the sweep depth.

    ONE CODE AT A TIME IS LOAD-BEARING, not a convenience. `disposal_route`'s
    DEPOSIT arm is conjoined with `bank_has_room`, and a bank carrying all 522
    catalog codes is far over the bundle's 50-entry capacity — every code would
    route to DELETE for lack of room and the sweep would find zero
    contradictions without ever exercising the arm it exists to test."""
    return dataclasses.replace(state, bank_items={code: COHERENCE_BANK_DEPTH})


def route_contradictions(state: WorldState, game_data: GameData) -> tuple[int, int]:
    """`(contradictions, codes_swept)` for defect B over the whole catalog.

    Each code is swept in its own single-code bank (see `_single_code_bank`) and
    asked of BOTH production adapters: how many copies does `bank_drain_excess`
    license, and what does `overstock_disposal` do with one of them?

    The routed quantity is 1 because the DEPOSIT arm does not depend on it — it
    reads `bank_ok` and the code's bank keep cap — while the RECYCLE arm probes
    `RecycleAction.is_applicable` down from the quantity, which would cost 500
    probes per gear code for an answer the invariant does not need.

    `codes_swept` is the ANTI-VACUITY number: it counts codes the drain licenses
    at all. A sweep that licenses nothing has zero contradictions for the most
    boring reason, and `shed_cell_verdict` refuses to pass on it. That the
    DEPOSIT arm can fire at all in this world is checked separately, by
    `_check_cell`."""
    ctx = census_ctx()
    contradictions = 0
    swept = 0
    for code in game_data.all_item_stats:
        one = _single_code_bank(state, code)
        drained = bank_drain_excess(one, game_data, ctx).get(code, 0)
        if drained <= 0:
            continue
        swept += 1
        routed = overstock_disposal(code, 1, one, game_data, True, ctx)
        contradictions += int(is_contradiction(drained, routed))
    return contradictions, swept


def deposit_arm_is_live(state: WorldState, game_data: GameData) -> bool:
    """Can the disposal ladder say DEPOSIT at all in this world?

    The sweep's green means "no drain-licensed code is deposited". That is
    worthless if NOTHING is deposited — a full bank, or a keep valuation that
    returned 0 for everything, would produce the same green while proving
    nothing. This walks the catalog for one code the route DOES bank (a code
    whose bank stock is still UNDER its keep quantity — `iron_ore` at 130 banked
    against a cap of 400 is the live example from part 1) and is what
    `_check_cell` refuses to build the cell without."""
    ctx = census_ctx()
    for code in game_data.all_item_stats:
        one = dataclasses.replace(state, bank_items={code: 1})
        if isinstance(overstock_disposal(code, 1, one, game_data, True, ctx),
                      DepositItemAction):
            return True
    return False


def shed_cell_verdict(cell: ShedCell, goal: Goal | None, plan: list[Action],
                      planner_failed: bool, state: WorldState,
                      contradictions: int, swept: int) -> bool:
    """The cell's verdict.

    A planner that ran out of budget FAILS every kind, before the plan is even
    read: an inconclusive search proves nothing, and a QUIET cell that "passed"
    because every candidate timed out would be the purest form of laundering.

    * LIVENESS: the arbiter selected THIS rung and came back with a plan that
      fits the bag bound. Selection alone is not enough — the drain was selected-
      able in principle and returned plan_len=0 — and a plan alone is not enough,
      because the band is what defect A is about.
    * QUIET: the arbiter did NOT pick the rung, and still produced a plan. "No
      plan at all" is not quiet, it is a stalled bot.
    * ROUTE_COHERENCE: zero contradictions over a sweep that actually licensed
      something."""
    if planner_failed:
        return False
    if cell.kind is ShedCellKind.ROUTE_COHERENCE:
        return contradictions == 0 and swept > 0
    chosen = repr(goal) if goal is not None else ""
    if not cell.must_be_selected:
        return bool(plan) and chosen != _EXPECTED_RUNG[cell.kind]
    if chosen != _EXPECTED_RUNG[cell.kind] or not plan:
        return False
    if not within_bag_bound(plan, state):
        return False
    if cell.kind is ShedCellKind.SELL_SELECTABLE:
        return stages_withdraw_then_sale(plan, SELL_CODE)
    return True


class ShedGapClass(Enum):
    """Why a FAIL cell did not shed (or wrongly did) — one class per root cause,
    ordered from the world limits to the two actionable residuals. The
    craft-census discipline: a FAIL is only NOT a bug when it carries a distinct,
    non-planner reason about the WORLD."""

    BANK_UNREACHABLE = "bank_unreachable"
    """No bank tile on the map, so neither the drain's `Withdraw` nor the sell
    arm's staged one can fire. A fact about the WORLD (the bundle's map),
    independent of every band and every licence."""
    NO_REACHABLE_BUYER = "no_reachable_buyer"
    """The sell cell's code has no buyer with a tile, so `NpcSellAction` can never
    apply. Explains the sell cell and nothing else — the drain sheds through
    DELETE and needs no merchant."""
    DISPOSAL_CONTRADICTION_BUG = "disposal_contradiction_bug"
    """DEFECT B's residual: a code is simultaneously drain-licensed and
    DEPOSIT-routed. That is the withdraw/redeposit livelock the epic exists to
    kill, and `Formal.DisposalRoute.drained_is_never_deposited` says it cannot
    happen — so if this fires, the adapters have stopped feeding the proved cores
    one number and the theorem has gone quietly vacuous over production."""
    SHED_STARVATION_BUG = "shed_starvation_bug"
    """DEFECT A's residual, and the FALL-THROUGH: the rung was licensed real work,
    the world was open, and the arbiter still did not select it with a plan — or,
    for a QUIET cell, selected it with nothing to do. UNEXPLAINED, never
    "expected". A planner TIMEOUT lands here unconditionally: "the search ran out
    of budget" is a fact about the PLANNER, and a gap class that can wear it is a
    gap class that can hide the starvation."""


def classify_gap(cell: ShedCell, state: WorldState, game_data: GameData,
                 planner_failed: bool, contradictions: int) -> ShedGapClass:
    """Classify a FAIL cell's root cause. Pure over (`cell`, `state`,
    `game_data`, `planner_failed`, `contradictions`); SHED_STARVATION_BUG is the
    FALL-THROUGH, never a positive match, so a cell is blamed on the ladder only
    after every world-limit explanation is ruled out.

    Precedence — PLANNER FAILURE -> CONTRADICTION -> BANK_UNREACHABLE ->
    NO_REACHABLE_BUYER -> SHED_STARVATION_BUG."""
    if planner_failed:
        return ShedGapClass.SHED_STARVATION_BUG
    if contradictions > 0:
        return ShedGapClass.DISPOSAL_CONTRADICTION_BUG
    if (cell.kind is not ShedCellKind.RECYCLE_SELECTABLE
            and game_data.bank_location_or_none is None):
        return ShedGapClass.BANK_UNREACHABLE
    if (cell.kind is ShedCellKind.SELL_SELECTABLE
            and all(game_data.npc_location(npc) is None
                    for npc, _price in game_data.npcs_buying_item(SELL_CODE))):
        return ShedGapClass.NO_REACHABLE_BUYER
    return ShedGapClass.SHED_STARVATION_BUG


def run_cell(cell: ShedCell, game_data: GameData) -> ShedResult:
    """Drive the selector for one cell and record the outcome. `planner_failed`
    rides from `drive_selector` into both the verdict and `classify_gap` — the
    anti-laundering path.

    `ROUTE_COHERENCE` drives no selector: it is a catalog SWEEP, and running the
    arbiter over a 500-deep bank of every item would spend the whole census
    budget answering a question the sweep already answers exactly."""
    state = census_state(cell, game_data)
    goal: Goal | None
    plan: list[Action]
    if cell.kind is ShedCellKind.ROUTE_COHERENCE:
        goal, plan, planner_failed = None, [], False
        contradictions, swept = route_contradictions(state, game_data)
        licensed = swept
    else:
        goal, plan, planner_failed = drive_selector(cell, state, game_data)
        contradictions, swept = 0, 0
        licensed = licensed_work(cell, state, game_data)
    passed = shed_cell_verdict(cell, goal, plan, planner_failed, state,
                               contradictions, swept)
    gap = (None if passed
           else classify_gap(cell, state, game_data, planner_failed,
                             contradictions).value)
    return ShedResult(
        kind=cell.kind.value,
        rung=_EXPECTED_RUNG.get(cell.kind, "-"),
        licensed=licensed,
        contradictions=contradictions,
        swept=swept,
        goal=repr(goal),
        plan=tuple(repr(a) for a in plan),
        planner_failed=planner_failed,
        passed=passed,
        gap=gap,
    )


def run_census(game_data: GameData) -> list[ShedResult]:
    """The whole grid, in enum order."""
    return [run_cell(cell, game_data) for cell in shed_grid(game_data)]


def summary_line(results: list[ShedResult]) -> str:
    """One-line completeness metric: cell total, PASS count, and the two
    must-be-zero residuals."""
    starved = sum(1 for r in results
                  if r.gap == ShedGapClass.SHED_STARVATION_BUG.value)
    contradicted = sum(1 for r in results
                       if r.gap == ShedGapClass.DISPOSAL_CONTRADICTION_BUG.value)
    passed = sum(1 for r in results if r.passed)
    return (f"{len(results)} cells; PASS {passed}; "
            f"shed_starvation_bug {starved}; "
            f"disposal_contradiction_bug {contradicted}")


def render_matrix(results: list[ShedResult]) -> str:
    """The cell x verdict matrix. Pure markdown — the generator script owns the
    file write."""
    lines = [
        "# Shed Reachability Completeness — Matrix",
        "",
        "> GENERATED — do not hand-edit. Regenerate with "
        "`uv run python scripts/gen_shed_reachability.py`.",
        ">",
        "> Census drives the REAL `StrategyArbiter.select` seam over the "
        "committed bundle — the seam where the COLLECT-band shed hoist is built, "
        "so a starved rung cannot hide behind a lower seam.",
        "",
        summary_line(results),
        "",
        "| Cell | Rung | licensed | swept | contradictions | Verdict | Goal | Plan |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        verdict = "PASS" if r.passed else f"**{r.gap}**"
        plan = " → ".join(r.plan) if r.plan else "(none)"
        lines.append(
            f"| {r.kind} | {r.rung} | {r.licensed} | {r.swept} "
            f"| {r.contradictions} | {verdict} | `{r.goal}` | `{plan}` |")
    lines.append("")
    return "\n".join(lines) + "\n"

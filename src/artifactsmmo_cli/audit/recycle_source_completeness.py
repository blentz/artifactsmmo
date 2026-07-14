"""Recycle-as-a-SOURCE behavioral-completeness census (recycle-as-acquisition
epic, Task 8).

The THIRD census in the craft-completeness family (`audit/craft_completeness.py`,
`audit/inventory_completeness.py`): a cell grid, a thin harness that drives the
REAL production selector, a structural verdict, and honest gap classes with an
UNEXPLAINED residual that must reach 0.

WHY IT IS A SEPARATE CENSUS. The inventory census asks a DISPOSAL question ("did
the planner SHED the surplus the keep authority licensed?") over a
`KeepReason x cap x pressure x band` grid. This one asks the ACQUISITION question
the recycle-as-acquisition epic exists to answer: "did the planner RECYCLE a held
item in order to OBTAIN its materials?" Different cell shape (a SOURCE item and a
MATERIAL, not a protected code and a cap), different verdict (a `Recycle(source)`
leg in the plan, not copies removed). Bolting it onto the disposal grid would have
forced one of the two questions to answer in the other's vocabulary.

THE ORACLE IS THE ROUTE, NOT A HAND-WRITTEN PLAN. Each cell states a world in
which recycling IS (or is NOT) a licensed way to obtain the material the goal
needs, and asks whether the production plan takes it:

  * LIVENESS (`recoverable[m] >= needed`): the plan MUST contain `Recycle(S)`.
  * SAFETY   (`destroyable(S) == 0`):      the plan MUST NOT contain `Recycle(S)`
    — it must gather instead. THE CELL THAT MATTERS MOST: it is what stops this
    epic from becoming a tool-melting bug (the last `copper_axe` is WORKING_KIT's,
    and a recipe that wants `copper_bar` must never dismantle it for parts).
  * BANKED   (`S` in the BANK, bag empty):  `Withdraw(S)` THEN `Recycle(S)` — the
    MAIN path in production, since `DEPOSIT_FULL` banks exactly this surplus.
  * PARTIAL  (`0 < recoverable[m] < needed`, recipe depth >= 2): a MIXED
    recycle+gather plan, WITHIN BUDGET.

A PLANNER TIMEOUT IS A BUG, NEVER AN EXPLAINED GAP (`classify_gap`'s
`planner_failed` arm, which fires BEFORE every world arm). The PARTIAL cell is
precisely where the `recoverable > 0` leaf rule's node-explosion risk surfaces —
the descent LEAFS a material it can only partly recover, so the plan driver must
serve the remainder from a from-scratch recipe subtree, the 1M-node shape of
livelock 3166d390. In the keep census a gap class silently ABSORBED a
49,569-node timeout and produced a GREEN grid that was lying; a gap class that
can swallow a planner bug destroys this census's entire value.

THE SEAM IS `StrategyArbiter.select` (`plan_recycle_source`) — production's own
selector, and the ONLY seam at which this census means anything: the destruction
LICENCE (`ai/destructive_license.license_destructive_actions`) is applied INSIDE
`select`, so a harness that planned through a lower seam (e.g. `arbiter._plans`,
which the craft census uses) would hand the goal an UNLICENSED pool — every
`RecycleAction` the factory ever emitted, including the one for the last
`copper_axe` — and the SAFETY cell would be proving nothing at all.
"""

from dataclasses import dataclass
from enum import Enum

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.inventory_keep import destroyable
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.recoverable_materials import recoverable_materials
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.strategy import StrategyDecision
from artifactsmmo_cli.ai.world_state import SKILL_NAMES, WorldState

RECYCLE_AUDIT_BUDGET_SECONDS = 10.0
"""Per-cell planner budget — the arbiter's cheap first-pass value
(`strategy_driver.CHEAP_BUDGET_SECONDS`), so a cell plans exactly as the live
bot's first pass does. A cell that needs MORE than the live first pass would not
be proving anything about the live bot."""

CENSUS_LEVEL = 10
"""Character level for every cell. Above `water_bow`'s level (5) so the source is
a plausible holding, and inside the tier-1/2 catalog the cells' recipes live in."""

CENSUS_SKILL_LEVEL = 10
"""Every skill at this level. Recycling is skill-gated by the SOURCE's
`crafting_level` (`recoverable_materials`), and the materials are gathered with
mining/woodcutting — so a census character that could not smelt or chop would
make the SAFETY cell pass for the wrong reason (no gather route either)."""

CENSUS_WEAPON = "copper_dagger"
"""Equipped in `weapon_slot`. Every source in this census is type `weapon` (the
factory only emits a `RecycleAction` for an EQUIPPABLE code), so an EMPTY weapon
slot would make `EquipOwnedGoal` — a COLLECT-band candidate, ABOVE the objective
step — fire to wear the surplus instead of planning for the material, and the
cell would never reach the planner it names. `_check_cell` re-asserts that the
step goal is what actually ran."""

CENSUS_POTION = "small_health_potion"
CENSUS_POTION_QTY = 100
"""A stocked utility slot. Without it the CRAFT_POTIONS GUARD fires (a craftable
utility heal exists at this skill and the slot is below baseline) and preempts the
objective step — a guard is not what any of these cells is about."""

CENSUS_BAG_QUANTITY_MAX = 100
CENSUS_BAG_SLOTS_MAX = 20
"""A ROOMY bag on both axes. Deliberate: pressure would arm the relief guards
(DEPOSIT_FULL / DISCARD / RECYCLE_RELIEF), and a relief recycle is a DISPOSAL
route — the inventory census already owns that question. This census must see a
recycle the planner chose to ACQUIRE with, so the bag is quiet."""

LIVENESS_SOURCE = "water_bow"
LIVENESS_MATERIAL = "ash_plank"
LIVENESS_BAG_COPIES = 3
LIVENESS_NEEDED = 4
"""The live shape, from the epic's runtime proof on Robby: a weaponcrafting chain
wanted `ash_plank` and the bot chopped 50 `ash_wood` at 1/cycle while holding bows
and nets whose recipes ARE `ash_plank`. `water_bow`'s recipe is 5 `ash_plank`, so
one unit recycle recovers `max(1, 5 // 2) = 2`. Three copies held, one kept
(COMBAT_WEAPON / RECIPE_DEMAND keep the last weapon), leaves 2 destroyable = 4
recoverable planks — exactly the 4 the goal needs, so the recycle route ALONE can
serve it and a plan that gathers instead is the bug."""

SAFETY_SOURCE = "copper_axe"
SAFETY_MATERIAL = "copper_bar"
SAFETY_BAG_COPIES = 1
SAFETY_NEEDED = 6
"""THE ONE THAT MATTERS. `copper_axe` is the character's best woodcutting tool
(WORKING_KIT) and its recipe is 6 `copper_bar` — so a goal that needs
`copper_bar` has an obvious, cheap, WRONG answer: melt the axe. Exactly ONE copy
is held, so `destroyable == 0` and the authority licenses nothing. The plan must
gather `copper_ore` and smelt.

FALSIFIABILITY IS NOT ASSUMED. Hold TWO axes and the very same cell shape
(`kind=liveness`, same source, same material) turns `destroyable` into 1 and the
plan MUST then contain `Recycle(copper_axe)` — the census's own machinery, one
copy apart. That cell is driven in the test suite
(`test_safety_cell_is_falsifiable`), so a SAFETY green can never be the vacuous
green of a route the planner was never going to take anyway."""

BANKED_SOURCE = "water_bow"
BANKED_MATERIAL = "ash_plank"
BANKED_BANK_COPIES = 3
BANKED_NEEDED = 4
"""Same arithmetic as LIVENESS, but every copy is in the BANK and the bag is
empty. This is the MAIN path in production, not an exotic one: `DEPOSIT_FULL`
banks the surplus a recycle would want to consume, so the fuel routinely lives in
the bank. It is also why Recycle — and only Recycle — is licensed off a BANK route
(`destructive_license.licensed_recycle_quantity`); the plan must stage the
`Withdraw` itself."""

PARTIAL_SOURCE = "water_bow"
PARTIAL_MATERIAL = "ash_plank"
PARTIAL_BAG_COPIES = 3
PARTIAL_NEEDED = 8
"""THE NODE-EXPLOSION CELL. 4 planks are recoverable and 8 are needed, so the
remaining 4 must come from the `ash_plank <- 10x ash_wood` subtree (recipe depth
2, 40 gathers). That is exactly the partially-deep subtree the `recoverable > 0`
leaf rule lets the descent inherit — the shape that hit a 1M-node cap in livelock
3166d390 — and the plan must resolve it WITHIN BUDGET or `classify_gap` calls it
what it is: a bug."""


class RecycleSourceKind(Enum):
    """The four cells. The grid is TOTAL over this enum (`recycle_source_grid`
    raises on a member with no scenario), so a fifth question cannot be added to
    the epic without the census exercising it."""

    LIVENESS = "liveness"
    SAFETY = "safety"
    BANKED = "banked"
    PARTIAL = "partial"


@dataclass(frozen=True)
class RecycleSourceCell:
    """One planner-drive point: hold `bag_copies` + `bank_copies` of `source`,
    ask the objective for `needed` units of `material` (which is an ingredient of
    `source`'s recipe), and see what the production plan does about it."""

    kind: RecycleSourceKind
    source: str
    material: str
    needed: int
    bag_copies: int
    bank_copies: int


@dataclass(frozen=True)
class RecycleSourceResult:
    """One census outcome, flat and render-ready."""

    kind: str
    source: str
    material: str
    needed: int
    recoverable: int
    destroyable: int
    goal: str
    plan: tuple[str, ...]
    planner_failed: bool
    passed: bool
    gap: str | None


def _require(code: str, game_data: GameData) -> str:
    """`code`, or a loud failure. The census runs on REAL game data: a missing
    catalog entry means the bundle changed under the census, and defaulting
    (skipping the cell, faking the recipe) would silently shrink the grid — the
    one thing a completeness census may never do."""
    if game_data.item_stats(code) is None:
        raise ValueError(
            f"census item {code!r} is not in the game catalog — the recycle-source "
            f"census cannot be built from data the game does not have")
    return code


def scenario_for(kind: RecycleSourceKind, game_data: GameData) -> RecycleSourceCell:
    """The cell realizing `kind` — one per enum member, so the grid is TOTAL over
    `RecycleSourceKind` (a new kind with no scenario raises here rather than
    quietly dropping out of the census)."""
    if kind is RecycleSourceKind.LIVENESS:
        return RecycleSourceCell(
            kind=kind, source=_require(LIVENESS_SOURCE, game_data),
            material=_require(LIVENESS_MATERIAL, game_data),
            needed=LIVENESS_NEEDED, bag_copies=LIVENESS_BAG_COPIES, bank_copies=0)
    if kind is RecycleSourceKind.SAFETY:
        return RecycleSourceCell(
            kind=kind, source=_require(SAFETY_SOURCE, game_data),
            material=_require(SAFETY_MATERIAL, game_data),
            needed=SAFETY_NEEDED, bag_copies=SAFETY_BAG_COPIES, bank_copies=0)
    if kind is RecycleSourceKind.BANKED:
        return RecycleSourceCell(
            kind=kind, source=_require(BANKED_SOURCE, game_data),
            material=_require(BANKED_MATERIAL, game_data),
            needed=BANKED_NEEDED, bag_copies=0, bank_copies=BANKED_BANK_COPIES)
    if kind is RecycleSourceKind.PARTIAL:
        return RecycleSourceCell(
            kind=kind, source=_require(PARTIAL_SOURCE, game_data),
            material=_require(PARTIAL_MATERIAL, game_data),
            needed=PARTIAL_NEEDED, bag_copies=PARTIAL_BAG_COPIES, bank_copies=0)
    raise ValueError(f"no census scenario for RecycleSourceKind {kind!r}")


def census_state(cell: RecycleSourceCell, game_data: GameData) -> WorldState:
    """The census character for `cell`: `bag_copies` of the source in the bag,
    `bank_copies` in the bank, a roomy bag, a stocked utility slot and an equipped
    weapon (see the constants — both keep a HIGHER-BAND candidate from preempting
    the objective step), and NONE of the material in hand (the goal must be unmet).

    The same state feeds `plan_recycle_source` and `classify_gap`, so the planner
    and the classifier always judge the SAME world."""
    return scenario_state(
        ScenarioCharacter(
            name="recycle_source_audit",
            level=CENSUS_LEVEL,
            skills={skill: CENSUS_SKILL_LEVEL for skill in SKILL_NAMES},
            equipment={"weapon_slot": CENSUS_WEAPON,
                       "utility1_slot": CENSUS_POTION},
            utility_quantities={"utility1_slot": CENSUS_POTION_QTY},
            inventory=({cell.source: cell.bag_copies} if cell.bag_copies else {}),
            inventory_max=CENSUS_BAG_QUANTITY_MAX,
            inventory_slots_max=CENSUS_BAG_SLOTS_MAX,
            bank=({cell.source: cell.bank_copies} if cell.bank_copies else {}),
        ),
        game_data)


def census_ctx() -> SelectionContext:
    """The base SelectionContext. `step_profile` is deliberately NOT filled in
    here: `StrategyArbiter.select` binds it from the step goal it resolves — the
    same one derivation production uses — and the destruction licence is applied
    against THAT ctx. Pre-binding it here would fork the derivation.

    `combat_monster=None` keeps the REST_FOR_COMBAT guard quiet; the bank is
    accessible, which the BANKED cell's `Withdraw` needs."""
    return SelectionContext(
        bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=0, combat_monster=None)


def census_decision(cell: RecycleSourceCell) -> StrategyDecision:
    """The strategy decision handed to the arbiter: obtain `needed` units of the
    cell's material. `chosen_root == chosen_step` (the material IS the objective),
    so `objective_step_goal` maps it to the flat `GatherMaterialsGoal` the live bot
    resolves for a non-equippable step — the goal whose `relevant_actions` admits
    the licensed recycles (`goals/gathering.py`)."""
    step = ObtainItem(code=cell.material, quantity=cell.needed)
    return StrategyDecision(interrupt=None, chosen_root=step, chosen_step=step,
                            desired_state={})


def expected_goal_repr(cell: RecycleSourceCell) -> str:
    """The repr of the goal the cell is ABOUT. `_check_cell` requires the arbiter
    to have actually run this goal: if a guard or a collect-band candidate won
    instead, the plan says nothing about the recycle route and the cell would be
    lying about what it tested."""
    return f"GatherMaterials({cell.material}, {{{cell.material}:{cell.needed}}})"


def _check_cell(cell: RecycleSourceCell, state: WorldState, game_data: GameData,
                goal: Goal | None) -> None:
    """CHECK THE CELL TESTS WHAT IT NAMES, or raise. Three ways a cell can lie
    about itself, all fatal to the census:

    * the AUTHORITY disagrees with the cell's premise — a LIVENESS/BANKED cell
      whose material is not fully recoverable, a PARTIAL cell that is fully (or
      not at all) recoverable, or a SAFETY cell whose source the authority would
      happily destroy. Then the cell's obligation is not the one its name states.
      Measured with the production functions themselves (`recoverable_materials`,
      `destroyable`), never re-derived here.
    * the goal is ALREADY SATISFIED (the material is in hand): the planner would
      have nothing to do and every kind would pass vacuously.
    * a DIFFERENT goal ran. The arbiter's ladder puts guards and the collect band
      ABOVE the objective step; if one of them won, the plan is not this cell's
      answer. Raising here (rather than failing the cell) is deliberate: a cell
      that never reached its planner is a broken cell, not a planner bug.

    Raises rather than shipping a lying cell — a census whose cells do not test
    what they name is worse than no census."""
    ctx = census_ctx()
    recoverable = recoverable_materials(state, game_data, ctx).get(cell.material, 0)
    destroy = destroyable(cell.source, state, game_data, ctx)
    held = (state.inventory.get(cell.material, 0)
            + (state.bank_items or {}).get(cell.material, 0))
    if held > 0:
        raise ValueError(
            f"{cell.kind.value}: the census character already holds {held} "
            f"{cell.material!r} — the goal is satisfied and the cell is vacuous")
    if cell.kind is RecycleSourceKind.SAFETY:
        if destroy != 0:
            raise ValueError(
                f"safety: the authority licenses {destroy} copies of "
                f"{cell.source!r} — the cell must hold ONLY protected copies")
        if recoverable != 0:
            raise ValueError(
                f"safety: {cell.material!r} is recoverable ({recoverable}) — the "
                f"cell must offer the planner NO licensed recycle route")
    elif cell.kind is RecycleSourceKind.PARTIAL:
        if not 0 < recoverable < cell.needed:
            raise ValueError(
                f"partial: recoverable {recoverable} is not a PARTIAL cover of "
                f"needed {cell.needed} — the cell would not exercise the mixed "
                f"recycle+gather subtree it exists for")
    elif recoverable < cell.needed:
        raise ValueError(
            f"{cell.kind.value}: recoverable {recoverable} < needed "
            f"{cell.needed} — the recycle route alone cannot serve the goal, so "
            f"a plan without a Recycle would not be a bug")
    if cell.kind is RecycleSourceKind.BANKED and cell.bag_copies:
        raise ValueError(
            "banked: the source must be in the BANK ONLY, or the cell tests the "
            "bag route it shares its arithmetic with")
    if goal is not None and repr(goal) != expected_goal_repr(cell):
        raise ValueError(
            f"{cell.kind.value}: the arbiter ran {goal!r}, not "
            f"{expected_goal_repr(cell)} — a higher-band candidate preempted the "
            f"objective step and the cell never reached the planner it names")


def recycle_source_grid(game_data: GameData) -> list[RecycleSourceCell]:
    """The census grid, DERIVED from `RecycleSourceKind`: one cell per kind, each
    checked against the keep authority at its own state (`_check_cell`). Derivation
    is the point — a kind added to the enum with no scenario raises rather than
    silently dropping out of the grid."""
    cells = [scenario_for(kind, game_data) for kind in RecycleSourceKind]
    for cell in cells:
        _check_cell(cell, census_state(cell, game_data), game_data, None)
    return cells


def plan_recycle_source(cell: RecycleSourceCell, state: WorldState,
                        game_data: GameData) -> tuple[Goal | None, list[Action], bool]:
    """The plan the REAL production selector produces for `cell`'s state, plus
    whether any goal's search was INCONCLUSIVE (budget timeout or node cap).

    Drives `StrategyArbiter.select` — the WHOLE production selection seam the live
    bot runs each cycle (`ai/player.py`). THE SEAM IS LOAD-BEARING, not a
    convenience: `license_destructive_actions` runs INSIDE `select` (right after
    the step profile is bound onto the ctx — the one point where the ctx the keep
    authority reads is complete). A harness that planned through a LOWER seam would
    hand the goal the RAW factory pool, in which the last `copper_axe` still has a
    `RecycleAction`, and the SAFETY cell would be asserting a protection that the
    census itself had bypassed.

    THE SECOND RETURN VALUE IS AN ANTI-LAUNDERING DEVICE. `goals_tried` records
    `timed_out` per attempt (`GOAPPlanner.last_stats`, which also sets it on a node
    cap — a capped search is inconclusive, not proof of impossibility). A cell whose
    plan is empty BECAUSE the planner ran out of budget has learned NOTHING about
    the world, and a world-limit gap class would happily "explain" it. So the flag
    rides out with the plan and `classify_gap` turns it into the residual.

    `history=None`: the census is offline and must be deterministic (a
    LearningStore would make plans depend on a live SQLite record)."""
    ctx = census_ctx()
    objective = CharacterObjective.from_game_data(game_data)
    actions = build_actions(game_data, state, objective,
                            bank_accessible=True, task_exchange_min_coins=0)
    arbiter = StrategyArbiter(GOAPPlanner(), None)
    arbiter.set_cycle(0)
    goal, plan, tried = arbiter.select(
        census_decision(cell), state, game_data, actions, ctx)
    failed = any(bool(attempt.get("timed_out")) for attempt in tried)
    return goal, plan, failed


def recycles_source(plan: list[Action], cell: RecycleSourceCell) -> bool:
    """The plan dismantles the cell's source."""
    return any(isinstance(a, RecycleAction) and a.code == cell.source for a in plan)


def withdraws_before_recycle(plan: list[Action], cell: RecycleSourceCell) -> bool:
    """The plan STAGES the bank copy: a `Withdraw(source)` strictly before the
    first `Recycle(source)`. Order is the whole obligation — a recycle with no
    withdraw ahead of it would consume a bag copy that (in a BANKED cell) does not
    exist, and `RecycleAction.bag_floor` is what forces the staging."""
    withdraws = [i for i, a in enumerate(plan)
                 if isinstance(a, WithdrawItemAction) and a.code == cell.source]
    recycles = [i for i, a in enumerate(plan)
                if isinstance(a, RecycleAction) and a.code == cell.source]
    return bool(withdraws) and bool(recycles) and withdraws[0] < recycles[0]


def mixes_recycle_and_gather(plan: list[Action], cell: RecycleSourceCell) -> bool:
    """The plan takes BOTH routes: it recycles the source AND gathers for the
    remainder. A PARTIAL cell whose plan only recycles cannot reach the demand
    (`recoverable < needed`), and one that only gathers has ignored the licensed
    fuel in its own bag — the mix IS the obligation."""
    return (recycles_source(plan, cell)
            and any(isinstance(a, GatherAction) for a in plan))


def recycle_source_cell_verdict(cell: RecycleSourceCell, plan: list[Action],
                                planner_failed: bool) -> bool:
    """The cell's verdict.

    A planner that ran out of budget FAILS every kind, before the plan is even
    read: an inconclusive search proves nothing, and a SAFETY cell that "passed"
    because the planner timed out (and so planned no recycle) would be the purest
    form of the laundering this census exists to prevent."""
    if planner_failed:
        return False
    if cell.kind is RecycleSourceKind.LIVENESS:
        return recycles_source(plan, cell)
    if cell.kind is RecycleSourceKind.SAFETY:
        # Non-empty AND no recycle: the plan must GATHER AROUND the protected
        # tool, not stall. An empty plan is not "safe", it is a stalled bot.
        return bool(plan) and not recycles_source(plan, cell)
    if cell.kind is RecycleSourceKind.BANKED:
        return withdraws_before_recycle(plan, cell)
    if cell.kind is RecycleSourceKind.PARTIAL:
        return mixes_recycle_and_gather(plan, cell)
    raise ValueError(f"unknown cell kind {cell.kind!r}")


class RecycleSourceGapClass(Enum):
    """Why a FAIL cell did not take (or wrongly took) the recycle route — one
    class per root cause, ordered from the world limits to the actionable
    residual. The craft-census discipline: a FAIL is only NOT a bug when it carries
    a distinct, non-planner reason about the WORLD."""

    WORKSHOP_UNREACHABLE = "workshop_unreachable"
    """The source's crafting skill has no workshop on the map, so
    `RecycleAction.is_applicable` can never be true — recycling is impossible in
    this world, whatever the authority licenses. A fact about the WORLD (the
    bundle's map), independent of every protection and of the planner."""
    BANK_UNREACHABLE = "bank_unreachable"
    """A BANKED cell with no bank tile on the map: the `Withdraw` that stages the
    bank copy cannot fire, so the recycle route has no first leg. Bag-side cells
    are unaffected (their fuel is already in hand), so this explains a BANKED cell
    and nothing else."""
    RECYCLE_SOURCE_BUG = "recycle_source_bug"
    """The residual: every route the cell needs was open (and, for SAFETY, the
    authority had already forbidden the one it must not take), yet the planner did
    not do it. UNEXPLAINED — never "expected". THE actionable class; it must reach
    0. A planner TIMEOUT lands here unconditionally: "the search ran out of budget"
    is a fact about the PLANNER, and a gap class that can wear it is a gap class
    that can hide the node explosion the leaf rule risks."""


def _workshop_reachable(source: str, game_data: GameData) -> bool:
    """A workshop for the source's crafting skill is on the map. Intrinsic to the
    ITEM and the WORLD — deliberately protection-free (reading the licence here
    would let a protected hoard classify itself as "no workshop" and the census
    would excuse the very bug it hunts)."""
    stats = game_data.item_stats(source)
    if stats is None or not stats.crafting_skill:
        return False
    return game_data.workshop_location(stats.crafting_skill) is not None


def classify_gap(cell: RecycleSourceCell, state: WorldState, game_data: GameData,
                 planner_failed: bool) -> RecycleSourceGapClass:
    """Classify a FAIL cell's root cause. Pure over (`cell`, `state`, `game_data`,
    `planner_failed`); RECYCLE_SOURCE_BUG is the FALL-THROUGH, never a positive
    match, so a cell is blamed on the planner only after every world-limit
    explanation is ruled out.

    Precedence — PLANNER FAILURE -> WORKSHOP_UNREACHABLE -> BANK_UNREACHABLE ->
    RECYCLE_SOURCE_BUG:

    * `planner_failed` (a budget timeout or a node cap — `plan_recycle_source`) is
      RECYCLE_SOURCE_BUG, UNCONDITIONALLY AND BEFORE EVERY WORLD ARM. This is the
      rule the keep census paid for in blood: a gap class may only be EARNED by a
      fact about the WORLD, and "the planner ran out of budget" is a fact about the
      PLANNER. Admitting it as a gap is how a 49,569-node `DiscardOverstock`
      timeout once wore the VENUE_UNREACHABLE badge on a GREEN grid that was lying.
      The PARTIAL cell is precisely where this epic's node explosion would surface,
      so if that turns a cell red, the cell WAS red.
    * WORKSHOP_UNREACHABLE outranks the bank arm: with no workshop there is no
      recycle to stage a withdraw FOR.
    * BANK_UNREACHABLE explains a BANKED cell only (a bag-side cell's fuel needs no
      withdraw).
    * RECYCLE_SOURCE_BUG: every route was open and the planner still did not take
      it — or, for SAFETY, it took the one the authority forbade."""
    if planner_failed:
        return RecycleSourceGapClass.RECYCLE_SOURCE_BUG
    if not _workshop_reachable(cell.source, game_data):
        return RecycleSourceGapClass.WORKSHOP_UNREACHABLE
    if (cell.kind is RecycleSourceKind.BANKED
            and game_data.bank_location_or_none is None):
        return RecycleSourceGapClass.BANK_UNREACHABLE
    return RecycleSourceGapClass.RECYCLE_SOURCE_BUG


def run_cell(cell: RecycleSourceCell, game_data: GameData) -> RecycleSourceResult:
    """Drive the cores for one cell and record the outcome. `planner_failed` rides
    from `plan_recycle_source` into both the verdict and `classify_gap` — the
    anti-laundering path."""
    state = census_state(cell, game_data)
    goal, plan, planner_failed = plan_recycle_source(cell, state, game_data)
    _check_cell(cell, state, game_data, goal)
    passed = recycle_source_cell_verdict(cell, plan, planner_failed)
    gap = (None if passed
           else classify_gap(cell, state, game_data, planner_failed).value)
    ctx = census_ctx()
    return RecycleSourceResult(
        kind=cell.kind.value,
        source=cell.source,
        material=cell.material,
        needed=cell.needed,
        recoverable=recoverable_materials(state, game_data, ctx).get(cell.material, 0),
        destroyable=destroyable(cell.source, state, game_data, ctx),
        goal=repr(goal),
        plan=tuple(repr(a) for a in plan),
        planner_failed=planner_failed,
        passed=passed,
        gap=gap,
    )


def run_census(game_data: GameData) -> list[RecycleSourceResult]:
    """The whole grid, in enum order."""
    return [run_cell(cell, game_data) for cell in recycle_source_grid(game_data)]


def summary_line(results: list[RecycleSourceResult]) -> str:
    """One-line completeness metric: cell total, PASS count, and the must-be-zero
    residual."""
    bugs = sum(1 for r in results if r.gap == RecycleSourceGapClass.RECYCLE_SOURCE_BUG.value)
    passed = sum(1 for r in results if r.passed)
    return (f"{len(results)} cells; PASS {passed}; "
            f"recycle_source_bug {bugs}")


def render_matrix(results: list[RecycleSourceResult]) -> str:
    """The cell x verdict matrix. Pure markdown — the generator script owns the
    file write."""
    lines = [
        "# Recycle-as-a-Source Completeness — Matrix",
        "",
        "> GENERATED — do not hand-edit. Regenerate with "
        "`uv run python scripts/gen_recycle_source_completeness.py`.",
        ">",
        "> Census drives the REAL `StrategyArbiter.select` seam over the committed "
        "bundle — the seam where `license_destructive_actions` runs, so the "
        "SAFETY cell sees the same LICENSED action pool production does.",
        "",
        summary_line(results),
        "",
        "| Cell | Source | Material | needed | recoverable | destroyable | Verdict "
        "| Goal | Plan |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        verdict = "PASS" if r.passed else f"**{r.gap}**"
        plan = " → ".join(r.plan) if r.plan else "(empty)"
        lines.append(
            f"| {r.kind} | {r.source} | {r.material} | {r.needed} | {r.recoverable} "
            f"| {r.destroyable} | {verdict} | `{r.goal}` | `{plan}` |")
    lines.append("")
    return "\n".join(lines) + "\n"

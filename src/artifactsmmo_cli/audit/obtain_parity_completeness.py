"""Obtain-model PARITY census (one-obtain-model epic, Task 7 — the ACCEPTANCE
gate).

THE LOAD-BEARING GATE. The bot has TWO plan producers: the O(closure) descent
(`craft_plan_gen.decompose`, the one walk) and the GOAP A* search (`planner.GOAPPlanner`). They used to
carry TWO different models of how a material can be obtained, and that divergence
shipped SEVEN GREEN COMMITS that were INERT in production — the recycle route
reached A* but not the descent, so for any roomy bag the descent answered first
and recycling never fired. This epic unified both producers onto ONE shared model
(`ai/obtain_sources.obtain_sources`). THIS census FAILS CI if they ever disagree
again about what is obtainable — it makes the divergence bug unshippable.

THE FOURTH census in the family (`audit/craft_completeness.py`,
`audit/inventory_completeness.py`, `audit/recycle_source_completeness.py`): a
cell grid derived from production's own structure, a thin harness that drives the
REAL production selector, a structural verdict, and an UNEXPLAINED residual
(`obtain_parity_bug`) that must reach 0.

THE THREE CHECKS. For a grid of (material, world-state) cells, one per
`SourceKind`, the two producers must AGREE about what is obtainable:

  * POOL ⊆ MODEL — every APPLICABLE action in the GOAP pool
    (`goal.relevant_actions`) that YIELDS the cell's material must have its
    `SourceKind` named by `obtain_sources(material)`. Applicability is the
    discriminant of "can serve": the pool carries THEORETICAL entries the
    executor cannot fire (a Withdraw for a code the bank does not hold, an
    NpcBuy from an event/unlocated vendor — `goals/gathering.relevant_actions`'s
    non-craftable buy arm emits one per vendor without the event/location filter
    `ObtainModel._buy` applies), and asking the action itself
    `is_applicable` excludes exactly those without re-deriving the model's gates.
  * MODEL ⊆ POOL — every source `obtain_sources(material)` names must EXIST as a
    concrete action of that kind in the pool (existence, not applicability — a
    CRAFT source is real even before its inputs are gathered, so its
    `CraftAction` is inapplicable at t=0).
  * (retired) PLAN PARITY compared the descent's plan with A*'s. Since Phase
    2e the arbiter never searches a goal the walk serves (a decline is final),
    so there is one producer and nothing to compare; the walk must still SERVE
    every cell (`_assert_obtainable`).

THE WITHDRAW CARVEOUT (historical; a follow-up now that the one walk landed).
The OLD descent did not consume WITHDRAW sources (it withdrew recipe inputs
through its own recipe descent instead), so WITHDRAW could not be compared
kind-for-kind. The one walk (Phase 2c-2b) withdraws through the model's
WITHDRAW route like any other, so the carveout's reason is gone; removing it is
a follow-up measured on its own, since it changes what the census compares. Consequently WITHDRAW cannot
be compared kind-for-kind across the producers and is EXCLUDED from all three
checks (pool kinds, model kinds, and both plans). THE CARVEOUT IS NARROW —
WITHDRAW ONLY. Every other kind (RECYCLE/BUY/DROP/GATHER/CRAFT) is compared in
full, so the carveout cannot swallow a real RECYCLE/BUY/DROP divergence; the
`test_parity_falsifiable_recycle` test PROVES this by deleting the RECYCLE arm
and watching the RECYCLE cell go RED on POOL⊆MODEL.

A PLANNER TIMEOUT IS A BUG, NEVER AN EXPLAINED GAP (`classify_gap`'s
`planner_failed` arm, which fires BEFORE every other arm). In the inventory
census a gap class silently ABSORBED a 49,569-node planner timeout and produced a
GREEN grid that was LYING. A timeout of the arbiter's own selection rides out
with the plans and `classify_gap` turns it into the residual unconditionally.

THE SEAM IS `StrategyArbiter.select` — production's own selector, and the ONLY
seam at which this census means anything. The destruction LICENCE
(`ai/destructive_license.license_destructive_actions`) is applied INSIDE `select`,
so a harness that planned through a lower seam would hand the goal an UNLICENSED
pool — every `RecycleAction` the factory ever emitted — and POOL⊆MODEL would
FALSELY fire on a recycle `obtain_sources` correctly omits (the keep authority
forbids it) while the pool still carries it. `_drive` runs the whole `select`
seam, then reproduces the SAME licensing `select` applies to obtain the pool the
two producers actually see, and CROSS-CHECKS its reproduction by asserting the
descent it recomputes equals the plan `select` itself returned.
"""

from dataclasses import dataclass, replace
from enum import Enum

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.ge_fill_sell import GeFillSellOrderAction
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.craft_plan_gen import decompose
from artifactsmmo_cli.ai.destructive_license import license_destructive_actions
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.obtain_sources import (
    SourceKind,
    obtain_sources,
)
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter, _step_protection_profile
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.strategy import StrategyDecision
from artifactsmmo_cli.ai.world_state import SKILL_NAMES, WorldState

CENSUS_LEVEL = 10
"""Character level for every cell. Above the tier-1 catalog the cells' recipes
live in, and high enough that the DROP cell's `chicken` is winnable with the
census loadout (an unwinnable dropper would make `obtain_sources` emit no DROP
source and the cell would test the wrong thing)."""

CENSUS_SKILL_LEVEL = 10
"""Every skill at this level. The cells gather (mining/woodcutting), craft, and
recycle (skill-gated by the source's `crafting_level`); a census character that
could not perform one of these would make its cell pass for the wrong reason."""

CENSUS_WEAPON = "copper_dagger"
"""Equipped in `weapon_slot` (with `derive_combat_stats`), so the DROP cell's
`chicken` is winnable and `ObtainModel._drop` emits the DROP source.
Also keeps the weapon slot filled so `EquipOwnedGoal` — a COLLECT-band candidate
ABOVE the objective step — never preempts the material step (`_check_cell`
re-asserts the step goal is what actually ran)."""

CENSUS_POTION = "small_health_potion"
CENSUS_POTION_QTY = 100
"""A stocked utility slot, so the CRAFT_POTIONS guard does not preempt the
objective step (a guard is not what any of these cells is about)."""

CENSUS_BOOST = "water_boost_potion"
"""A stocked second utility slot. With only the heal slot stocked, the potion
guard's boost-stock arm fires in this census's recycle cell and preempts the
objective step. Found 2026-09-29, when decomposition started serving the potion
batch whose search used to fail; the failure had let the step run by accident.
Same fix as `recycle_source_completeness.CENSUS_BOOST`."""

CENSUS_GOLD = 1_000_000
"""A full pocket. Deliberate: no cell's obtainability question is about
affordability — the pool's gold-gated buy/withdraw edges must all clear so the
producers are compared on ROUTE, not on a gold shortfall."""

CENSUS_BAG_QUANTITY_MAX = 200
CENSUS_BAG_SLOTS_MAX = 20
"""A ROOMY bag on both axes. Pressure would arm the relief guards (DEPOSIT_FULL /
DISCARD / RECYCLE_RELIEF) and preempt the objective step; this census must see the
producers' ACQUISITION route, so the bag is quiet."""

# --- the six cells, one per SourceKind (see ParitySourceKind) -----------------

GATHER_MATERIAL = "copper_ore"
GATHER_NEEDED = 5
"""A raw gatherable. `obtain_sources(copper_ore)` = {GATHER}; both producers
gather. The dominant route is GATHER."""

CRAFT_MATERIAL = "copper_bar"
CRAFT_NEEDED = 3
"""A tier-1 craftable (10 copper_ore each). `obtain_sources(copper_bar)` =
{CRAFT}; both producers gather ore then craft. The dominant route is CRAFT."""

WITHDRAW_MATERIAL = "copper_bar"
WITHDRAW_NEEDED = 3
WITHDRAW_BANK = {"copper_ore": 30}
"""THE WITHDRAW-CARVEOUT CELL. The recipe INPUT `copper_ore` sits in the bank, so
`obtain_sources(copper_ore)` names a WITHDRAW source, which the one walk serves
through that same WITHDRAW route (the old descent used its own input withdraw).
Both producers emit `[Withdraw(copper_ore), Craft(copper_bar)]`;
after WITHDRAW is carved out of both, the compared kind-sets are {CRAFT} == {CRAFT}.
This is the exact scenario the carveout exists for."""

RECYCLE_SOURCE = "water_bow"
RECYCLE_MATERIAL = "ash_plank"
RECYCLE_NEEDED = 2
RECYCLE_BAG = {"water_bow": 3}
"""THE CELL THAT PINS THE CARVEOUT NARROW. Three `water_bow` in the bag, one kept
(COMBAT_WEAPON / RECIPE_DEMAND), two destroyable; each unit recycle is expected to
return `2 * 5 // 7 = 1` `ash_plank` (the learned total 2, drawn from the 5 planks
and 2 slimeballs of the recipe: `ai/recycle_yield`), so 2 are recoverable —
exactly the demand.
`obtain_sources(ash_plank)` = {RECYCLE, CRAFT} and BOTH producers recycle. Because
RECYCLE is compared in full (only WITHDRAW is carved out), deleting the RECYCLE
arm from `obtain_sources` turns this cell RED on POOL⊆MODEL and PLAN PARITY — the
falsifiability proof that the carveout is not a hole."""

BUY_MATERIAL = "cloth"
BUY_NEEDED = 2
BUY_BAG = {"wool": 40}
"""A non-craftable, non-gatherable, non-dropped resource sold by the PERMANENT
`tailor` for `wool` (stocked so the buy is affordable). `obtain_sources(cloth)` =
{BUY}; both producers buy. NPC-buy was the route the OLD generator could not
express at all (`return None`), so a BUY parity cell is load-bearing history."""

DROP_MATERIAL = "feather"
DROP_NEEDED = 2
"""A monster-drop-only material (`chicken`, drop rate 8, winnable + xp-positive at
CENSUS_LEVEL so the plain Fight is emitted). `obtain_sources(feather)` = {DROP};
both producers hunt. The descent truncates at the Fight (one leg, stochastic
yield) and A* plans past it, but both plans' kind-set is {DROP}."""


class ParitySourceKind(Enum):
    """The six cells, one per `obtain_sources.SourceKind`. The grid is TOTAL over
    this enum (`parity_grid` raises on a member with no scenario), so a seventh
    source added to the obtain model cannot ship without this census exercising
    its parity."""

    GATHER = "gather"
    CRAFT = "craft"
    WITHDRAW = "withdraw"
    RECYCLE = "recycle"
    BUY = "buy"
    DROP = "drop"


@dataclass(frozen=True)
class ParityCell:
    """One (material, world-state) parity point: ask the objective for `needed`
    units of `material`, holding `bag` in the inventory and `bank` in the bank,
    and compare what the two producers say about obtaining it."""

    kind: ParitySourceKind
    material: str
    needed: int
    bag: dict[str, int]
    bank: dict[str, int]


@dataclass(frozen=True)
class ParityResult:
    """One census outcome, flat and render-ready."""

    kind: str
    material: str
    needed: int
    model_kinds: tuple[str, ...]
    pool_applicable_kinds: tuple[str, ...]
    descent_kinds: tuple[str, ...]
    pool_subset_model: bool
    model_subset_pool: bool
    planner_failed: bool
    goal: str
    passed: bool
    gap: str | None


def action_source_kind(action: Action) -> SourceKind | None:
    """The `SourceKind` a concrete action realizes, or None for an action that
    obtains nothing (OptimizeLoadout, LevelSkill, WithdrawGold, Rest, Move — the
    scaffolding legs a plan carries around its obtain legs). The one place the
    census maps the action vocabulary onto the shared source vocabulary."""
    if isinstance(action, WithdrawItemAction):
        return SourceKind.WITHDRAW
    if isinstance(action, RecycleAction):
        return SourceKind.RECYCLE
    if isinstance(action, CraftAction):
        return SourceKind.CRAFT
    if isinstance(action, GatherAction):
        return SourceKind.GATHER
    if isinstance(action, NpcBuyAction):
        return SourceKind.BUY
    if isinstance(action, GeFillSellOrderAction):
        return SourceKind.GE_FILL
    if isinstance(action, FightAction):
        return SourceKind.DROP
    return None


def action_yields(action: Action, material: str, game_data: GameData) -> bool:
    """True iff a single application of `action` produces `material` — the same
    per-kind target relation `obtain_sources` uses to decide which `Source` names
    a material: a gather whose EFFECTIVE drop is it, a craft/withdraw/buy of it, a
    recycle of a SOURCE item whose recipe consumes it, or a fight with it in the
    dropper's table."""
    if isinstance(action, GatherAction):
        return (action.drop_item_override
                or game_data.resource_drop_item(action.resource_code)) == material
    if isinstance(action, CraftAction):
        return action.code == material
    if isinstance(action, WithdrawItemAction):
        return action.code == material
    if isinstance(action, RecycleAction):
        return material in (game_data.crafting_recipe(action.code) or {})
    if isinstance(action, NpcBuyAction):
        return action.item_code == material
    if isinstance(action, GeFillSellOrderAction):
        return action.item_code == material
    if isinstance(action, FightAction):
        return any(material == item
                   for item, _rate, _mn, _mx in game_data.monster_drops(action.monster_code))
    return False


def _kinds_without_withdraw(kinds: set[SourceKind]) -> frozenset[SourceKind]:
    """`kinds` minus WITHDRAW — the NARROW carveout, applied identically to every
    kind-set the three checks compare (see the module docstring). WITHDRAW cannot
    be compared kind-for-kind because the descent serves a WITHDRAW `Source` via
    its own recipe-input withdraw, not a map WITHDRAW leg; NO other kind is
    dropped, so a RECYCLE/BUY/DROP divergence always survives."""
    return frozenset(kinds - {SourceKind.WITHDRAW})


def _require(code: str, game_data: GameData) -> str:
    """`code`, or a loud failure. The census runs on REAL game data: a missing
    catalog entry means the bundle changed under the census, and defaulting
    (skipping the cell) would silently shrink the grid — the one thing a
    completeness census may never do."""
    if game_data.item_stats(code) is None:
        raise ValueError(
            f"census item {code!r} is not in the game catalog — the obtain-parity "
            f"census cannot be built from data the game does not have")
    return code


def scenario_for(kind: ParitySourceKind, game_data: GameData) -> ParityCell:
    """The cell realizing `kind` — one per enum member, so the grid is TOTAL over
    `ParitySourceKind` (a new kind with no scenario raises here rather than
    quietly dropping out of the census)."""
    if kind is ParitySourceKind.GATHER:
        return ParityCell(kind, _require(GATHER_MATERIAL, game_data),
                          GATHER_NEEDED, {}, {})
    if kind is ParitySourceKind.CRAFT:
        return ParityCell(kind, _require(CRAFT_MATERIAL, game_data),
                          CRAFT_NEEDED, {}, {})
    if kind is ParitySourceKind.WITHDRAW:
        return ParityCell(kind, _require(WITHDRAW_MATERIAL, game_data),
                          WITHDRAW_NEEDED, {},
                          {_require(k, game_data): v for k, v in WITHDRAW_BANK.items()})
    if kind is ParitySourceKind.RECYCLE:
        return ParityCell(kind, _require(RECYCLE_MATERIAL, game_data),
                          RECYCLE_NEEDED,
                          {_require(RECYCLE_SOURCE, game_data): RECYCLE_BAG[RECYCLE_SOURCE]},
                          {})
    if kind is ParitySourceKind.BUY:
        return ParityCell(kind, _require(BUY_MATERIAL, game_data),
                          BUY_NEEDED,
                          {_require(k, game_data): v for k, v in BUY_BAG.items()}, {})
    if kind is ParitySourceKind.DROP:
        return ParityCell(kind, _require(DROP_MATERIAL, game_data),
                          DROP_NEEDED, {}, {})
    raise ValueError(f"no census scenario for ParitySourceKind {kind!r}")


def census_ctx() -> SelectionContext:
    """The base SelectionContext. `step_profile` is deliberately NOT filled in
    here: `StrategyArbiter.select` binds it from the step goal it resolves — the
    same derivation production uses — and `_drive` reproduces that binding so the
    licence is applied against the same ctx. `combat_monster=None` keeps the
    REST_FOR_COMBAT guard quiet; the bank is accessible for the WITHDRAW cell."""
    return SelectionContext(
        bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=0, combat_monster=None)


def census_state(cell: ParityCell, game_data: GameData) -> WorldState:
    """The census character for `cell`: `bag` in the inventory, `bank` in the
    bank, a roomy bag, a full pocket, a stocked utility slot, and an equipped
    weapon with combat stats DERIVED from it (so the DROP cell's dropper is
    winnable). NONE of the material is held (the goal must be unmet).

    The same state feeds every producer and `classify_gap`, so they judge the
    SAME world."""
    return scenario_state(
        ScenarioCharacter(
            name="obtain_parity_audit",
            level=CENSUS_LEVEL,
            gold=CENSUS_GOLD,
            skills={skill: CENSUS_SKILL_LEVEL for skill in SKILL_NAMES},
            equipment={"weapon_slot": CENSUS_WEAPON, "utility1_slot": CENSUS_POTION,
                       "utility2_slot": CENSUS_BOOST},
            utility_quantities={"utility1_slot": CENSUS_POTION_QTY,
                                "utility2_slot": CENSUS_POTION_QTY},
            inventory=dict(cell.bag),
            inventory_max=CENSUS_BAG_QUANTITY_MAX,
            inventory_slots_max=CENSUS_BAG_SLOTS_MAX,
            bank=dict(cell.bank),
            derive_combat_stats=True,
        ),
        game_data)


def census_decision(cell: ParityCell) -> StrategyDecision:
    """The strategy decision handed to the arbiter: obtain `needed` units of the
    cell's material. `chosen_root == chosen_step` (the material IS the objective),
    so `objective_step_goal` maps it to the flat `GatherMaterialsGoal` the live
    bot resolves for a non-equippable step — the goal whose `relevant_actions` is
    the GOAP pool this census reads."""
    step = ObtainItem(code=cell.material, quantity=cell.needed)
    return StrategyDecision(interrupt=None, chosen_root=step, chosen_step=step)


def expected_goal_repr(cell: ParityCell) -> str:
    """The repr of the goal the cell is ABOUT. `_check_cell` requires the arbiter
    to have actually run this goal: if a guard or a collect-band candidate won
    instead, the pool and plans say nothing about the material's routes and the
    cell would be lying about what it tested. Every cell's material is
    non-equippable, so `objective_step_goal` resolves the flat GatherMaterials
    step."""
    return f"GatherMaterials({cell.material}, {{{cell.material}:{cell.needed}}})"


def _check_premise(cell: ParityCell, state: WorldState) -> None:
    """The material must NOT be already held, or the goal is satisfied, every
    producer plans nothing, and the parity is vacuous. Checkable without a
    resolved goal (so `parity_grid` can run it at build time).

    Deliberately does NOT assert the cell's NAMED kind is in `obtain_sources`: the
    falsifiability test DELETES a source arm, and a cell must then produce a RED
    parity BUG, not crash the census. The premise that the material is genuinely
    obtainable by production (so the checks are non-vacuous) is enforced by
    `_assert_obtainable` against the PRODUCERS' plans, which survive that
    deletion."""
    held = (state.inventory.get(cell.material, 0)
            + (state.bank_items or {}).get(cell.material, 0))
    if held > 0:
        raise ValueError(
            f"{cell.kind.value}: the census character already holds {held} "
            f"{cell.material!r} — the goal is satisfied and the cell is vacuous")


def _check_goal(cell: ParityCell, goal: Goal | None) -> None:
    """The arbiter must have actually resolved and run the cell's objective step,
    or raise. The arbiter's guards / collect band sit ABOVE the objective step; if
    one of them won (or nothing was selected), `goal` is None or some other goal's
    repr and the pool/plans answer a different question. Raising (rather than
    failing the cell) is deliberate — a cell that never reached its objective step
    is a broken cell, not a parity bug."""
    if goal is None or repr(goal) != expected_goal_repr(cell):
        raise ValueError(
            f"{cell.kind.value}: the arbiter ran {goal!r}, not "
            f"{expected_goal_repr(cell)} — a higher-band candidate preempted the "
            f"objective step and the cell never reached the material it names")


def parity_grid(game_data: GameData) -> list[ParityCell]:
    """The census grid, DERIVED from `ParitySourceKind`: one cell per kind, each
    checked against its own premise (`_check_premise`). Derivation is the point —
    a kind added to the enum with no scenario raises rather than silently dropping
    out of the grid."""
    cells = [scenario_for(kind, game_data) for kind in ParitySourceKind]
    for cell in cells:
        _check_premise(cell, census_state(cell, game_data))
    return cells


@dataclass(frozen=True)
class _Drive:
    """One faithful drive of the production seam for a cell: the resolved goal,
    the LICENSED pool the two producers see, the ctx with the step profile bound,
    and — the anti-laundering flag — whether any of the arbiter's own planning
    attempts was INCONCLUSIVE (timeout / node cap)."""

    goal: Goal | None
    licensed: list[Action]
    ctx: SelectionContext
    arbiter_plan: list[Action]
    arbiter_failed: bool


def _drive(cell: ParityCell, state: WorldState, game_data: GameData) -> _Drive:
    """Drive `StrategyArbiter.select` — the WHOLE production selection seam — then
    reproduce the SAME licensing `select` applies, so the two producers are
    compared on the pool production actually hands them.

    THE SEAM IS LOAD-BEARING. `license_destructive_actions` runs INSIDE `select`
    (right after the step profile is bound onto the ctx — the one point where the
    ctx the keep authority reads is complete). A harness that planned through a
    lower seam would hand the goal the RAW factory pool, in which every
    `RecycleAction` still exists, and POOL⊆MODEL would FALSELY fire on a recycle
    `obtain_sources` correctly omits. So `_drive` calls the real `select`, then
    rebuilds the licence over the goal `select` resolved (`_step_protection_profile`
    → `replace(ctx, step_profile=...)` → `license_destructive_actions`, the exact
    three steps `select` runs).

    `history=None`: the census is offline and must be deterministic."""
    ctx = census_ctx()
    objective = CharacterObjective.from_game_data(game_data)
    actions = build_actions(game_data, state, objective,
                            bank_accessible=True, task_exchange_min_coins=0)
    arbiter = StrategyArbiter(GOAPPlanner(), None)
    arbiter.set_cycle(0)
    goal, arbiter_plan, tried = arbiter.select(
        census_decision(cell), state, game_data, actions, ctx)
    step_profile = _step_protection_profile(goal, state, game_data)
    ctx = replace(ctx, step_profile=dict(step_profile or {}))
    licensed = license_destructive_actions(actions, state, game_data, ctx)
    arbiter_failed = any(bool(attempt.get("timed_out")) for attempt in tried)
    return _Drive(goal, licensed, ctx, arbiter_plan, arbiter_failed)


def model_kinds(material: str, state: WorldState, game_data: GameData,
                ctx: SelectionContext) -> frozenset[SourceKind]:
    """The source kinds `obtain_sources` names for `material`, WITHDRAW carved out
    — the MODEL half of the parity."""
    return _kinds_without_withdraw(
        {s.kind for s in obtain_sources(material, state, game_data, ctx)})


def pool_kinds(material: str, goal: Goal, licensed: list[Action],
               state: WorldState, game_data: GameData, *,
               applicable_only: bool) -> frozenset[SourceKind]:
    """The source kinds the GOAP pool (`goal.relevant_actions`) serves for
    `material`, WITHDRAW carved out. `applicable_only` selects the direction:

    * POOL ⊆ MODEL asks it with `applicable_only=True` — "can the pool SERVE it?"
      counts only actions that can fire NOW, excluding the pool's theoretical
      entries (a Withdraw the empty bank cannot back, an NpcBuy from an
      event/unlocated vendor) that `obtain_sources` correctly omits.
    * MODEL ⊆ POOL asks it with `applicable_only=False` — a CRAFT source is real
      before its inputs exist, so its inapplicable `CraftAction` must still COUNT
      as the pool's realization of that source."""
    pool = goal.relevant_actions(licensed, state, game_data)
    kinds = {
        kind
        for action in pool
        if action_yields(action, material, game_data)
        and (kind := action_source_kind(action)) is not None
        and (not applicable_only or action.is_applicable(state, game_data))
    }
    return _kinds_without_withdraw(kinds)


def descent_plan(goal: GatherMaterialsGoal, licensed: list[Action],
                 ctx: SelectionContext, state: WorldState,
                 game_data: GameData) -> list[Action]:
    """The route-driven producer's plan for `goal` — production's first
    producer (`craft_plan_gen.decompose`, the one walk), driven on the LICENSED
    pool with the bound ctx exactly as `StrategyArbiter._plans` drives it. Empty
    when it declines (returns None)."""
    return decompose(goal, state, game_data, licensed, ctx) or []


def _assert_reproduction_faithful(kind: str, descent: list[Action],
                                  arbiter_plan: list[Action]) -> None:
    """The descent recomputed on `_drive`'s reproduced licensed pool MUST equal
    the plan `StrategyArbiter.select` itself returned (the arbiter runs the
    descent first and returns it when non-None). Equality PROVES the licensed pool
    the census rebuilt is the one production used; a mismatch means the census's
    reproduction of the licensing seam has drifted and its parity would be
    measuring a different pool. An empty descent (the arbiter fell back to A*)
    carries no such obligation."""
    if descent and ([repr(a) for a in descent] != [repr(a) for a in arbiter_plan]):
        raise ValueError(
            f"{kind}: the descent plan {[repr(a) for a in descent]} does not match "
            f"the plan the arbiter returned {[repr(a) for a in arbiter_plan]} — the "
            f"census's licensed-pool reproduction has drifted from the real select "
            f"seam and its parity would be measuring a different pool")


def _assert_obtainable(kind: str, material: str, descent: list[Action],
                       planner_failed: bool) -> None:
    """The non-vacuity premise, enforced against the PRODUCER (not the model,
    which the falsifiability test mutates): a cell whose material the walk
    cannot serve — with the selection CONCLUSIVE — is vacuous, since every census
    cell is designed to be obtainable. An empty walk means the bundle changed
    under the census, not a parity bug."""
    if not planner_failed and not descent:
        raise ValueError(
            f"{kind}: the walk cannot serve {material!r} — the cell is vacuous "
            f"(it is designed to be obtainable; the bundle changed under the census)")


def plan_kinds(plan: list[Action]) -> frozenset[SourceKind]:
    """The set of source kinds a plan's legs realize, WITHDRAW carved out and
    scaffolding legs (kind None) dropped — reported beside the model's kinds."""
    return _kinds_without_withdraw(
        {kind for action in plan
         if (kind := action_source_kind(action)) is not None})


def parity_cell_verdict(pool_subset_model: bool, model_subset_pool: bool,
                        planner_failed: bool) -> bool:
    """The cell's verdict. A selection that ran out of budget FAILS the cell
    before any check is read: an inconclusive run proves nothing. Otherwise
    both agreements (pool and model) must hold."""
    if planner_failed:
        return False
    return pool_subset_model and model_subset_pool


class ParityGapClass(Enum):
    """Why a FAIL cell disagreed — a SINGLE residual, because a parity
    disagreement is NEVER an explained gap.

    Unlike its sibling censuses this enum has no world-limit arms: POOL⊆MODEL and
    MODEL⊆POOL are pure structural agreements about the shared model. So the
    only class is the actionable residual, and it must reach 0."""

    OBTAIN_PARITY_BUG = "obtain_parity_bug"
    """The residual: the two producers (or the pool and the model) disagree about
    what is obtainable — the divergence bug this census exists to catch. A planner
    TIMEOUT lands here unconditionally: "the search ran out of budget" is a fact
    about the PLANNER, and a gap class that can wear it is a gap class that can
    hide a node explosion."""


def classify_gap(cell: ParityCell, state: WorldState, game_data: GameData,
                 planner_failed: bool) -> ParityGapClass:
    """Classify a FAIL cell. `planner_failed` is a REQUIRED argument and is the
    FIRST arm, UNCONDITIONALLY — the rule the keep census paid for in blood: a gap
    class may only be EARNED by a fact about the WORLD, and "the planner ran out of
    budget" is a fact about the PLANNER. In the inventory census a 49,569-node
    timeout once wore a world-limit badge on a GREEN grid that was lying.

    There are no world-limit arms below it — a parity disagreement is never
    explained — so the fall-through is the same residual. `planner_failed` is
    placed FIRST anyway, so that no future arm added to this function could ever
    absorb a timeout ahead of it. Pure over its arguments; unused positional
    arguments (`cell`, `state`, `game_data`) mirror the sibling censuses'
    signature so the CI generator can call them uniformly."""
    if planner_failed:
        return ParityGapClass.OBTAIN_PARITY_BUG
    return ParityGapClass.OBTAIN_PARITY_BUG


def run_cell(cell: ParityCell, game_data: GameData) -> ParityResult:
    """Drive the producers for one cell and record the parity outcome.

    Cross-checks the licensing reproduction (`_assert_reproduction_faithful`) and
    enforces the non-vacuity premise against the producers
    (`_assert_obtainable`)."""
    state = census_state(cell, game_data)
    drive = _drive(cell, state, game_data)
    _check_premise(cell, state)
    _check_goal(cell, drive.goal)
    goal = drive.goal
    # _check_goal raised unless the arbiter resolved exactly the flat
    # GatherMaterials step this cell names (see expected_goal_repr).
    assert isinstance(goal, GatherMaterialsGoal)

    descent = descent_plan(goal, drive.licensed, drive.ctx, state, game_data)
    planner_failed = drive.arbiter_failed

    _assert_reproduction_faithful(cell.kind.value, descent, drive.arbiter_plan)
    _assert_obtainable(cell.kind.value, cell.material, descent, planner_failed)

    model = model_kinds(cell.material, state, game_data, drive.ctx)
    pool_app = pool_kinds(cell.material, goal, drive.licensed, state, game_data,
                          applicable_only=True)
    pool_exist = pool_kinds(cell.material, goal, drive.licensed, state, game_data,
                            applicable_only=False)
    descent_kinds = plan_kinds(descent)

    pool_subset_model = pool_app <= model
    model_subset_pool = model <= pool_exist
    passed = parity_cell_verdict(pool_subset_model, model_subset_pool, planner_failed)
    gap = (None if passed
           else classify_gap(cell, state, game_data, planner_failed).value)
    return ParityResult(
        kind=cell.kind.value,
        material=cell.material,
        needed=cell.needed,
        model_kinds=tuple(sorted(k.value for k in model)),
        pool_applicable_kinds=tuple(sorted(k.value for k in pool_app)),
        descent_kinds=tuple(sorted(k.value for k in descent_kinds)),
        pool_subset_model=pool_subset_model,
        model_subset_pool=model_subset_pool,
        planner_failed=planner_failed,
        goal=repr(goal),
        passed=passed,
        gap=gap,
    )


def run_census(game_data: GameData) -> list[ParityResult]:
    """The whole grid, in enum order."""
    return [run_cell(cell, game_data) for cell in parity_grid(game_data)]


def summary_line(results: list[ParityResult]) -> str:
    """One-line completeness metric: cell total, PASS count, and the must-be-zero
    residual."""
    bugs = sum(1 for r in results
               if r.gap == ParityGapClass.OBTAIN_PARITY_BUG.value)
    passed = sum(1 for r in results if r.passed)
    return f"{len(results)} cells; PASS {passed}; obtain_parity_bug {bugs}"


def render_matrix(results: list[ParityResult]) -> str:
    """The cell x verdict matrix. Pure markdown — the generator script owns the
    file write."""
    lines = [
        "# Obtain-Model Parity Completeness — Matrix",
        "",
        "> GENERATED — do not hand-edit. Regenerate with "
        "`uv run python scripts/gen_obtain_parity.py`.",
        ">",
        "> Census drives the REAL `StrategyArbiter.select` seam over the committed "
        "bundle, then compares the action pool with the shared obtain model and "
        "reports the walk's plan. WITHDRAW is carved out of every comparison; every "
        "other kind is compared in full.",
        "",
        summary_line(results),
        "",
        "| Cell | Material | needed | model | pool(applicable) | walk "
        "| P⊆M | M⊆P | Verdict | Goal |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        verdict = "PASS" if r.passed else f"**{r.gap}**"

        def fmt(items: tuple[str, ...]) -> str:
            return ",".join(items) if items else "·"

        lines.append(
            f"| {r.kind} | {r.material} | {r.needed} | {fmt(r.model_kinds)} "
            f"| {fmt(r.pool_applicable_kinds)} | {fmt(r.descent_kinds)} "
            f"| {r.pool_subset_model} | {r.model_subset_pool} "
            f"| {verdict} | `{r.goal}` |")
    lines.append("")
    return "\n".join(lines) + "\n"

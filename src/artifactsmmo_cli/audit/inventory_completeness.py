"""Inventory keep/disposal behavioral-completeness census (item-protection
authority epic, Task 4).

The SECOND census in the craft-completeness family (`audit/craft_completeness.py`):
a cell grid, a thin harness that drives the REAL production planner, a structural
verdict, and honest gap classes with an UNEXPLAINED residual that must reach 0.

WHY IT EXISTS. Item protection used to be `frozenset[str]` code-sets, a type that
can only mean "keep ALL copies". That defect produced a family of hoard bugs — the
live one: 18 copper_axe + 7 fishing_net stuck in a slot-pressured bag because the
axe was the best woodcutting tool, so every disposal path (recycle, sell, deposit)
skipped the whole CODE. `ai/inventory_keep.py` replaced the sets with two integer
caps (`keep_in_bag`, `keep_owned`) fed by the `KeepReason` registry. This census is
the ACCEPTANCE MECHANISM for the migration that follows (Tasks 6-9): it asserts the
production planner OBEYS that authority.

THE ORACLE IS CONFORMANCE TO THE KEEP AUTHORITY — never a hand-written expected
plan (those rot). For each cell:

  * SAFETY  (`held == keep`):  the plan must NOT dispose the code below `keep`.
  * LIVENESS (`held == keep + SURPLUS`, under bag pressure): the plan MUST dispose
    some of the code — `bankable`/`destroyable` say the surplus is sheddable, so a
    plan that sheds none of it contradicts the authority.

CELLS ARE DERIVED FROM THE REGISTRY, never hand-picked — that is what makes the
census COMPLETE: every `KeepReason`, crossed with every cap it feeds
(`IN_BAG_REASONS` / `OWNED_REASONS`) and every pressure state. Adding a reason to
the registry automatically adds its cells; nothing can be protected by a reason the
census does not exercise. `CURRENCY` (the one `KEEP_ALL` holder) yields SAFETY
cells only — the single DECLARED liveness exemption (`KEEP_ALL_SENTINEL`).

PRESSURE IS SPLIT slot-vs-quantity because that distinction is where the HTTP 497
livelock lived (a live bag sat at 68/124 QUANTITY while 20/20 SLOTS): the relief
guards read `max(quantity_fraction, slot_fraction)` (`tiers.guards._used_fraction`)
while the DESTRUCTIVE discard guards deliberately stay quantity-only, so a
slot-pressured bag and a quantity-pressured bag reach DIFFERENT production routes.
A census with one "full" state would be blind to half of them.

INERT: this module only MEASURES. The runner + `--check` CI gate is Task 5; the
consumer migration (`bank_selection`, `recycle_surplus`, `guards`) is Tasks 6-9.
It is EXPECTED to land RED — the un-migrated consumers still carry the code-set
blankets, so the in-bag LIVENESS cells fail today. That is the census working.
"""

import dataclasses
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.actions.deposit_item import DepositItemAction
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.ge_fill import GeFillBuyOrderAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.bank_room import bank_has_room
from artifactsmmo_cli.ai.bank_selection import select_bank_deposits
from artifactsmmo_cli.ai.disposal_route import RECYCLING_SKILLS
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_keep import (
    IN_BAG_REASONS,
    OWNED_REASONS,
    KeepReason,
    keep_in_bag,
    keep_owned,
    reason_quantity,
)
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.strategy_driver import (
    StrategyArbiter,
    _step_protection_profile,
    objective_step_goal,
)
from artifactsmmo_cli.ai.thresholds import PRESSURE_HIGH_DEN, PRESSURE_HIGH_NUM
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal, ObtainItem
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.strategy import StrategyDecision
from artifactsmmo_cli.ai.world_state import SKILL_NAMES, TASKS_COIN_CODE, WorldState

INVENTORY_AUDIT_BUDGET_SECONDS = 10.0
"""Per-cell planner budget — the arbiter's cheap first-pass value
(`strategy_driver.CHEAP_BUDGET_SECONDS`), so a cell plans exactly as the live
bot's first pass does."""

SURPLUS = 6
"""Copies held ABOVE the cap in a LIVENESS cell. Any positive number proves the
point (`bankable`/`destroyable` return exactly this many); 6 is comfortably above
every batch/stack quantum in the disposal goals, so a route that sheds "one
batch" still visibly sheds this code."""

SENTINEL_HELD = 12
"""How many copies a `KEEP_ALL` (CURRENCY) SAFETY cell holds. The cell contract
`held == keep` is unrepresentable for the sentinel (`keep` is 1_000_000), so the
cell holds a plausible stock and the verdict clamps `keep` to `held` — "every
copy is protected", which is exactly what KEEP_ALL means."""

CENSUS_LEVEL = 5
"""Character level for every cell. Chosen so the tier-1 (level-1) census items
sit INSIDE `inventory_caps.LEVEL_BAND_NEAR` (distance 4 < 5): the level-distance
keep ceiling would otherwise clamp the caps and the cell's `keep` would no longer
be the reason's own quantity."""

CENSUS_SKILL_LEVEL = 5
"""Every gathering/crafting skill at this level, so the census character can
actually act on the tier-1 recipes its cells reference (`reachable_recipe_demand`
counts a consumer only within `RECIPE_SKILL_HORIZON` of the current skill)."""

FILLER_STACKS = 18
"""Distinct junk stacks in the bag besides the cell's own stack. 18 + 1 = 19 of
20 slots, i.e. slot pressure 0.95 — above `DEPOSIT_FULL_FRACTION` (0.90) with one
slot still FREE, so the relief guards fire on genuine pressure and not through
`bank_selection`'s zero-free-slot LAST-RESORT escape hatch (which banks a keep
item and would mask exactly the blanket-keep bug this census hunts)."""

SLOT_CAP = 20
"""Inventory SLOT cap in the slot-pressure state (the live bag's cap)."""

ROOMY_SLOTS = 100
"""Slot cap in the quantity-pressure and below-threshold states — high enough
that the SLOT fraction never reaches a relief watermark, so those cells vary the
QUANTITY dimension alone."""

PRESSURE_STATES: tuple[str, ...] = ("slot_full", "qty_full", "below_threshold")
"""The three bag states every reason is exercised in. `slot_full` and `qty_full`
are separate because production treats them differently — `guards._used_fraction`
maxes the two fractions for the NON-destructive relief (deposit/craft) while the
DESTRUCTIVE discard guards stay quantity-only, so slot pressure never deletes what
banking could have saved. A single "full" state would conflate the two routes."""

PRESSURED: tuple[str, ...] = ("slot_full", "qty_full")
"""The pressure states a LIVENESS cell is generated in. `below_threshold` is
deliberately EXCLUDED from liveness: with a roomy bag NO production relief route
is even supposed to fire (that is the whole point of the watermarks), so demanding
disposal there would assert a behavior the design explicitly rejects — a vacuous
liveness obligation. SAFETY is required in ALL three (protection must hold whether
or not the bag is under pressure)."""

# --- the per-reason activation scenarios -----------------------------------
# Codes are REAL bundle items (validated in `_scenario`, which raises rather than
# defaulting when the catalog lacks one — no faked game data).
CURRENCY_CODE = TASKS_COIN_CODE
TASK_CODE = "golden_egg"
TASK_TOTAL = 5
"""The ACTIVE_TASK items-task. `golden_egg` is a level-1 monster drop that feeds
NO recipe, so the task's own remaining quantity is the BINDING keep on both caps.
A recipe MATERIAL would be shadowed by RECIPE_DEMAND (copper_ore's recipe cap is
80 x BATCH_BUFFER = 400 copies), and the cell would silently test that sibling
reason instead — `_cell` asserts the binding, so a shadowed cell raises."""
HEAL_CODE = "cooked_chicken"
WEAPON_CODE = "copper_dagger"
TOOL_CODE = "copper_axe"
CRAFT_TARGET_CODE = "copper_axe"
CRAFT_MATERIAL_CODE = "copper_bar"
GOAL_STEP_CODE = "ash_plank"
GOAL_MATERIAL_CODE = "ash_wood"
GEAR_CODE = "copper_boots"
GEAR_KEEP_QTY = 2
RECIPE_MATERIAL_CODE = "copper_bar"


@dataclass(frozen=True)
class InventoryCell:
    """One planner-drive point in the keep census grid: hold `held` copies of
    `code` in a bag under `pressure`, in the state that ACTIVATES `reason`, and
    ask what the production planner does about the copies above `keep`.

    `keep` is the AUTHORITY's answer for `cap` at that state (`keep_in_bag` /
    `keep_owned`), and `reason` is BINDING on it (the cell's state is built so
    this reason's quantity IS the cap — see `_cell`), so the cell tests the
    reason it names."""

    reason: KeepReason
    kind: Literal["safety", "liveness"]
    cap: Literal["in_bag", "owned"]
    code: str
    held: int
    keep: int
    pressure: Literal["slot_full", "qty_full", "below_threshold"]


@dataclass(frozen=True)
class Scenario:
    """The pure DATA describing how to activate one `KeepReason`: which item the
    reason protects and the world/context facts that make it protect it. Held
    apart from `InventoryCell` because a cell's `held`/`keep` are DERIVED (the
    authority is asked at a probe state) while these facts are the givens."""

    code: str
    task: tuple[str, str, int, int] | None = None
    crafting_target: str | None = None
    equipment: tuple[tuple[str, str], ...] = ()
    gear_keep: tuple[tuple[str, int], ...] = ()
    step: MetaGoal | None = None


def _require(code: str, game_data: GameData) -> str:
    """`code`, or a loud failure. The census must run on REAL game data: a
    missing catalog entry means the bundle changed under the census, and
    defaulting (skipping the cell, faking stats) would silently shrink the grid
    — the one thing a completeness census may never do."""
    if game_data.item_stats(code) is None:
        raise ValueError(
            f"census item {code!r} is not in the game catalog — the inventory "
            f"census cannot be built from data the game does not have")
    return code


def scenario_for(reason: KeepReason, game_data: GameData) -> Scenario:
    """The state/context facts that make `reason` protect its item — one per
    registry member, so the grid is TOTAL over `KeepReason` (a new reason with no
    scenario raises here rather than quietly dropping out of the census)."""
    if reason is KeepReason.CURRENCY:
        return Scenario(code=_require(CURRENCY_CODE, game_data))
    if reason is KeepReason.ACTIVE_TASK:
        code = _require(TASK_CODE, game_data)
        return Scenario(code=code, task=(code, "items", 0, TASK_TOTAL))
    if reason is KeepReason.HEALING_CONSUMABLE:
        return Scenario(code=_require(HEAL_CODE, game_data))
    if reason is KeepReason.COMBAT_WEAPON:
        return Scenario(code=_require(WEAPON_CODE, game_data))
    if reason is KeepReason.WORKING_KIT:
        return Scenario(code=_require(TOOL_CODE, game_data))
    if reason is KeepReason.COMMITTED_RECIPE:
        return Scenario(code=_require(CRAFT_MATERIAL_CODE, game_data),
                        crafting_target=_require(CRAFT_TARGET_CODE, game_data))
    if reason is KeepReason.GOAL_MATERIALS:
        return Scenario(code=_require(GOAL_MATERIAL_CODE, game_data),
                        step=ObtainItem(code=_require(GOAL_STEP_CODE, game_data),
                                        quantity=1))
    if reason is KeepReason.EQUIPPED:
        code = _require(WEAPON_CODE, game_data)
        return Scenario(code=code, equipment=(("weapon_slot", code),))
    if reason is KeepReason.GEAR_DEMAND:
        code = _require(GEAR_CODE, game_data)
        return Scenario(code=code, gear_keep=((code, GEAR_KEEP_QTY),))
    if reason is KeepReason.RECIPE_DEMAND:
        return Scenario(code=_require(RECIPE_MATERIAL_CODE, game_data))
    raise ValueError(f"no census scenario for KeepReason {reason!r}")


def _protected_codes(scenario: Scenario, game_data: GameData) -> frozenset[str]:
    """Every code the scenario itself makes special — the cell's own item, its
    equipment, and the full recipe closures of the crafting target / task item /
    gear demand / objective step. Filler junk is drawn from OUTSIDE this set so
    the filler can never be protected (a fully-protected bag would leave
    `select_bank_deposits` empty, DEPOSIT_FULL would not fire, and every liveness
    cell would fail for lack of any relief at all — a blind census)."""
    roots = [scenario.code]
    if scenario.crafting_target:
        roots.append(scenario.crafting_target)
    if scenario.task:
        roots.append(scenario.task[0])
    if scenario.step is not None and isinstance(scenario.step, ObtainItem):
        roots.append(scenario.step.code)
    roots.extend(code for _slot, code in scenario.equipment)
    roots.extend(code for code, _qty in scenario.gear_keep)
    closure: set[str] = set()
    queue = list(roots)
    while queue:
        code = queue.pop()
        if code in closure:
            continue
        closure.add(code)
        queue.extend(game_data.crafting_recipe(code) or {})
    return frozenset(closure)


def filler_codes(scenario: Scenario, game_data: GameData) -> list[str]:
    """`FILLER_STACKS` junk stacks for the bag, in a deterministic (code-sorted)
    order, drawn from plain `resource` items that carry NONE of the properties the
    keep reasons key on: no `hp_restore` (that would join HEALING_CONSUMABLE's
    greedy aggregate fill and shrink the cell's own share), no `skill_effects`
    (that would contest WORKING_KIT's best-tool pick), never a weapon (that would
    contest COMBAT_WEAPON), and nothing in the scenario's own closure. The filler
    exists ONLY to create pressure and to give the deposit route something it is
    unambiguously allowed to bank."""
    excluded = _protected_codes(scenario, game_data)
    out: list[str] = []
    for code in sorted(game_data.all_item_stats):
        if len(out) == FILLER_STACKS:
            break
        stats = game_data.all_item_stats[code]
        if (code in excluded or stats.type_ != "resource" or stats.hp_restore > 0
                or stats.skill_effects):
            continue
        out.append(code)
    if len(out) < FILLER_STACKS:
        raise ValueError(
            f"only {len(out)} filler resources available for {scenario.code!r}; "
            f"the census needs {FILLER_STACKS} to build slot pressure")
    return out


def _bag(scenario: Scenario, held: int, game_data: GameData) -> dict[str, int]:
    """The cell's inventory: `held` copies of the scenario's code plus one of each
    filler stack."""
    bag = {code: 1 for code in filler_codes(scenario, game_data)}
    bag[scenario.code] = held
    return bag


def _bank(cap: str, scenario: Scenario, game_data: GameData) -> dict[str, int]:
    """The bank behind the cell.

    EMPTY for an `in_bag` cell: banking is the reversible route the `keep_in_bag`
    cap is about, so the bank must be able to take the surplus.

    FULL (at `bank_capacity`) for an `owned` cell: `keep_owned` is about
    DESTRUCTION (recycle/sell/delete), and production only destroys when the bank
    cannot absorb the item (the bank-full cascade craft > recycle > sell >
    discard). With a roomy bank the correct production answer to an owned-cap
    surplus is to BANK it — which retains ownership and would make the liveness
    obligation unsatisfiable-by-design rather than a bug. Filled with codes
    OUTSIDE the scenario's closure so bank stock never credits `destroyable`."""
    if cap == "in_bag":
        return {}
    excluded = _protected_codes(scenario, game_data)
    stock: dict[str, int] = {}
    for code in sorted(game_data.all_item_stats):
        if len(stock) == game_data.bank_capacity:
            break
        if code in excluded:
            continue
        stock[code] = 1
    return stock


def _capacities(pressure: str, used: int, stacks: int) -> tuple[int, int]:
    """(inventory_max, inventory_slots_max) realizing `pressure` for a bag holding
    `used` items across `stacks` slots.

    * slot_full — `SLOT_CAP` slots with one free, so the SLOT fraction is
      19/20 = 0.95 (above DEPOSIT_FULL's 0.90) while the QUANTITY fraction stays
      low: the live 20/20-slots-but-68/124-quantity shape.
    * qty_full — the mirror image: roomy slots, quantity at ~19/20 of the cap
      (again with at least one free unit, so `bank_selection`'s zero-free
      last-resort escape hatch stays shut).
    * below_threshold — a quarter-full bag on both axes: no relief watermark is
      crossed, which is what makes the SAFETY cells there meaningful (nothing
      should be shed from a roomy bag at all).
    """
    if pressure == "slot_full":
        return used * 4, SLOT_CAP
    if pressure == "qty_full":
        # used / max == PRESSURE_HIGH_NUM/DEN's neighborhood (0.95), rounded so
        # `max > used` — one free unit keeps the last-resort deposit shut.
        return used * PRESSURE_HIGH_DEN // (PRESSURE_HIGH_NUM + 2) + 1, ROOMY_SLOTS
    if pressure == "below_threshold":
        return used * 4, ROOMY_SLOTS
    raise ValueError(f"unknown pressure state {pressure!r}")


def census_state(reason: KeepReason, cap: str, pressure: str, held: int,
                 game_data: GameData) -> WorldState:
    """The census character holding `held` copies of `reason`'s item under
    `pressure` — the state both `plan_inventory` and `classify_gap` read, so the
    planner and the classifier always judge the SAME world.

    Level/skills are fixed (`CENSUS_LEVEL`, `CENSUS_SKILL_LEVEL`) so the cells vary
    only along the dimensions the census is about: reason x cap x pressure."""
    scenario = scenario_for(reason, game_data)
    bag = _bag(scenario, held, game_data)
    used = sum(bag.values())
    inventory_max, slots_max = _capacities(pressure, used, len(bag))
    skills = {skill: CENSUS_SKILL_LEVEL for skill in SKILL_NAMES}
    state = scenario_state(
        ScenarioCharacter(
            name="inventory_audit",
            level=CENSUS_LEVEL,
            skills=skills,
            equipment=dict(scenario.equipment),
            inventory=bag,
            inventory_max=inventory_max,
            inventory_slots_max=slots_max,
            bank=_bank(cap, scenario, game_data),
            task=scenario.task,
        ),
        game_data)
    return dataclasses.replace(state, crafting_target=scenario.crafting_target)


def census_ctx(reason: KeepReason, state: WorldState,
               game_data: GameData) -> SelectionContext:
    """The SelectionContext the cell's reason needs to be live.

    `step_profile` is not hand-written: it is the production
    `_step_protection_profile` of the production `objective_step_goal` for the
    scenario's step — the SAME derivation `StrategyArbiter.select` performs when
    it re-binds the ctx from `census_decision`'s step. One source, so the cell's
    `keep` and the planner's protection cannot drift apart."""
    scenario = scenario_for(reason, game_data)
    ctx = SelectionContext(
        bank_accessible=True,
        bank_required_level=0,
        bank_unlock_monster=None,
        initial_xp=0,
        task_exchange_min_coins=0,
        combat_monster=None,
        gear_keep=dict(scenario.gear_keep),
    )
    if scenario.step is None:
        return ctx
    step_goal = objective_step_goal(scenario.step, state, game_data, ctx,
                                    root=scenario.step)
    profile = _step_protection_profile(step_goal, state, game_data)
    return dataclasses.replace(ctx, step_profile=dict(profile or {}))


def census_decision(reason: KeepReason, game_data: GameData) -> StrategyDecision:
    """The strategy decision handed to the arbiter. Only GOAL_MATERIALS needs an
    objective step (its protection IS the active step's material map); every other
    reason is exercised with NO step, so the arbiter's guard/means ladder — the
    disposal ladder — is what answers the cell."""
    step = scenario_for(reason, game_data).step
    return StrategyDecision(interrupt=None, chosen_root=step, chosen_step=step,
                            desired_state={})


def _cap_value(cap: str, code: str, state: WorldState, game_data: GameData,
               ctx: SelectionContext) -> int:
    """The keep authority's answer for `cap` — the census ORACLE."""
    if cap == "in_bag":
        return keep_in_bag(code, state, game_data, ctx)
    if cap == "owned":
        return keep_owned(code, state, game_data, ctx)
    raise ValueError(f"unknown cap {cap!r}")


def _probe_keep(reason: KeepReason, cap: str, pressure: str,
                game_data: GameData) -> int:
    """The cap value for `reason`'s item, measured at a PROBE state that holds
    plainly more than any reason could want (`KEEP_ALL` copies are not
    representable, so the probe holds `SENTINEL_HELD + KEEP_ALL`-free stock).

    The probe breaks the circularity in cell construction: a cell's `held` is
    defined in terms of `keep`, but `keep` is a function of the state, which
    needs `held`. Every reason's quantity is either independent of how many
    copies are held (task remaining, recipe demand, gear demand, best-tool 1) or
    saturating in it (HEALING_CONSUMABLE's greedy share of the heal-stock
    target), so asking the authority while holding MORE than the cap yields the
    cap itself — and `_cell` re-asserts it at the final state."""
    probe_held = _probe_quantity(reason)
    state = census_state(reason, cap, pressure, probe_held, game_data)
    ctx = census_ctx(reason, state, game_data)
    return _cap_value(cap, scenario_for(reason, game_data).code, state, game_data, ctx)


PROBE_HELD = 200
"""Copies held in the probe state — above every finite quantity any reason can
ask for at `CENSUS_LEVEL` (the largest is the ACTIVE_TASK/RECIPE_DEMAND family,
tens of copies), so the probe always saturates the cap it measures."""


def _probe_quantity(reason: KeepReason) -> int:
    """The probe stock. CURRENCY's cap is the `KEEP_ALL` sentinel (1_000_000) and
    holding a million coins would be an absurd (and slot-meaningless) state, so it
    probes with the same plausible stock its SAFETY cell holds."""
    return SENTINEL_HELD if reason is KeepReason.CURRENCY else PROBE_HELD


def _held_for(keep: int, kind: str, reason: KeepReason) -> int:
    """The cell's held quantity: `keep` for SAFETY, `keep + SURPLUS` for LIVENESS.

    The `KEEP_ALL` sentinel cannot be held literally, so a CURRENCY SAFETY cell
    holds `SENTINEL_HELD` copies — all of them protected (the verdict clamps
    `keep` to `held`). CURRENCY has no LIVENESS cell (the declared exemption), so
    the sentinel never needs a surplus."""
    if reason is KeepReason.CURRENCY:
        return SENTINEL_HELD
    if kind == "safety":
        return keep
    if kind == "liveness":
        return keep + SURPLUS
    raise ValueError(f"unknown cell kind {kind!r}")


def check_binding(reason: KeepReason, cap: str, pressure: str, code: str,
                  probe_keep: int, cap_keep: int, reason_keep: int) -> None:
    """CHECK THE CELL TESTS WHAT IT NAMES, or raise.

    Two ways a cell can lie about itself, both fatal to the census:

    * the cap MOVED between the probe state and the cell state, so the cell's
      `keep` is not the authority's answer at the state the planner is driven in;
    * a SIBLING reason OUT-ASKS this one. `keep_in_bag`/`keep_owned` are a MAX
      over their reason ladder, so a cell whose state let another reason demand
      more copies would silently exercise THAT reason — its "surplus" would be
      protected by the sibling and the resulting liveness FAIL would be a census
      artifact rather than a bug. Ties are fine (two reasons wanting the same
      quantity give the same cap); being STRICTLY out-asked is not.

    Raises rather than shipping a lying cell — a census whose cells do not test
    what they name is worse than no census."""
    if cap_keep != probe_keep:
        raise ValueError(
            f"{reason.value}/{cap}/{pressure}: cap moved between the probe "
            f"({probe_keep}) and the cell state ({cap_keep}) — the cell's `keep` "
            f"would not be the authority's answer")
    if reason_keep != cap_keep:
        raise ValueError(
            f"{reason.value}/{cap}/{pressure}: another keep reason out-asks it "
            f"({cap_keep} > {reason_keep}) for {code!r} — the cell would test "
            f"the sibling reason")


def _cell(reason: KeepReason, cap: str, kind: str, pressure: str,
          game_data: GameData) -> InventoryCell:
    """Build one cell, and `check_binding` it against the authority at its own
    state."""
    keep = _probe_keep(reason, cap, pressure, game_data)
    held = _held_for(keep, kind, reason)
    code = scenario_for(reason, game_data).code
    state = census_state(reason, cap, pressure, held, game_data)
    ctx = census_ctx(reason, state, game_data)
    check_binding(reason, cap, pressure, code, keep,
                  _cap_value(cap, code, state, game_data, ctx),
                  reason_quantity(reason, code, state, game_data, ctx))
    return InventoryCell(reason=reason, kind=kind, cap=cap, code=code,  # type: ignore[arg-type]
                         held=held, keep=keep, pressure=pressure)  # type: ignore[arg-type]


def caps_for(reason: KeepReason) -> list[str]:
    """The caps `reason` feeds, in cell order. A reason in NEITHER ladder
    protects nothing at all — it would be dead weight in the registry and the
    census could not exercise it, so it raises instead of silently generating no
    cells (a reason that quietly drops out of the grid is exactly the
    completeness hole this census exists to prevent)."""
    caps = [cap for cap, members in (("in_bag", IN_BAG_REASONS),
                                     ("owned", OWNED_REASONS))
            if reason in members]
    if not caps:
        raise ValueError(
            f"KeepReason {reason!r} feeds NEITHER keep cap — it protects "
            f"nothing and the census cannot exercise it")
    return caps


def inventory_grid(game_data: GameData) -> list[InventoryCell]:
    """The census grid, DERIVED from the `KeepReason` registry: every reason x
    every cap it feeds (`IN_BAG_REASONS` / `OWNED_REASONS`) x every pressure
    state, one SAFETY cell (`held == keep`) in each of the three pressure states
    and one LIVENESS cell (`held == keep + SURPLUS`) in each of the two PRESSURED
    ones.

    Derivation is the whole point: nothing is hand-picked, so a reason added to
    the registry cannot slip into production without the census exercising both
    its halves. `CURRENCY` yields SAFETY cells only — the single declared liveness
    exemption (`InventoryGapClass.KEEP_ALL_SENTINEL`), because `KEEP_ALL` means no
    copy is ever disposable and a liveness demand would contradict the authority
    itself."""
    cells: list[InventoryCell] = []
    for reason in KeepReason:
        for cap in caps_for(reason):
            for pressure in PRESSURE_STATES:
                cells.append(_cell(reason, cap, "safety", pressure, game_data))
            if reason is KeepReason.CURRENCY:
                continue
            for pressure in PRESSURED:
                cells.append(_cell(reason, cap, "liveness", pressure, game_data))
    return cells


def plan_inventory(cell: InventoryCell, state: WorldState,
                   game_data: GameData) -> list[Action]:
    """The plan the REAL production planner produces for `cell`'s state.

    Drives `StrategyArbiter.select` — the WHOLE production selection seam the live
    bot runs each cycle (`ai/player.py`): the guard ladder (deposit/discard/
    recycle/sell relief), the collect band, the objective step, the discretionary
    means, sticky commitment, and the per-goal planner underneath. Disposal is a
    LADDER decision, not a goal in isolation, so anything less than `select` would
    be a second implementation of the very ordering under test — and a mocked
    planner would prove nothing at all.

    `history=None`: the census is offline and must be deterministic (a
    LearningStore would make plans depend on a live SQLite record)."""
    ctx = census_ctx(cell.reason, state, game_data)
    objective = CharacterObjective.from_game_data(game_data)
    actions = build_actions(game_data, state, objective,
                            bank_accessible=True, task_exchange_min_coins=0)
    arbiter = StrategyArbiter(GOAPPlanner(), None)
    arbiter.set_cycle(0)
    _goal, plan, _tried = arbiter.select(
        census_decision(cell.reason, game_data), state, game_data, actions, ctx)
    return plan


def _action_disposal(action: Action, code: str, state: WorldState,
                     game_data: GameData) -> tuple[int, int]:
    """How many copies of `code` this action removes, as
    `(from_the_bag, from_ownership)`.

    The two numbers differ for the BANK: a deposit empties the bag (satisfying a
    `keep_in_bag` surplus — banking is the reversible route that cap is about) but
    RETAINS ownership, so it can never satisfy — nor violate — a `keep_owned`
    obligation. Recycle / sell / delete remove the copies from the world entirely
    and count for both.

    `DepositAllAction` names no code: it banks whatever `select_bank_deposits`
    picks at execution time, so the quantity is read from THAT production
    selector at the action's own state and under the action's own ctx — which is
    precisely the function the hoard bug lived in (its `_keep_codes` blanket is
    why 18 copper_axe were never selected; it now banks `bankable(code)`)."""
    if isinstance(action, DepositAllAction):
        deposits = dict(select_bank_deposits(state, game_data, action.ctx))
        return deposits.get(code, 0), 0
    if isinstance(action, DepositItemAction):
        return (action.quantity if action.code == code else 0), 0
    if isinstance(action, RecycleAction):
        qty = action.quantity if action.code == code else 0
        return qty, qty
    if isinstance(action, DeleteItemAction):
        qty = action.quantity if action.code == code else 0
        return qty, qty
    if isinstance(action, (NpcSellAction, GeFillBuyOrderAction)):
        qty = action.quantity if action.item_code == code else 0
        return qty, qty
    return 0, 0


def disposed_quantity(cell: InventoryCell, plan: list[Action], state: WorldState,
                      game_data: GameData) -> int:
    """Copies of `cell.code` the plan DISPOSES against `cell.cap`.

    The plan is walked with each action's own production `apply`, so every action
    is judged at the state it would actually run in (a `DepositAll` after a
    `Craft` banks a different bag than one before it).

    Deliberately NOT "the bag count went down": a craft CONSUMING its recipe
    inputs, or a fight eating a potion, removes copies without DISPOSING of them.
    Only the four disposal routes count — deposit (bag only), recycle, sell,
    delete — which is exactly the set `bankable`/`destroyable` license."""
    total = 0
    sim = state
    for action in plan:
        from_bag, from_owned = _action_disposal(action, cell.code, sim, game_data)
        total += from_bag if cell.cap == "in_bag" else from_owned
        sim = action.apply(sim, game_data)
    return total


def inventory_cell_verdict(cell: InventoryCell, plan: list[Action],
                           state: WorldState, game_data: GameData) -> bool:
    """The cell's verdict against the keep authority.

    SAFETY — PASS iff the plan leaves at least `keep` copies: it may dispose the
    slack above the cap (there is none, `held == keep`) but never a protected
    copy. `keep` is clamped to `held` for the `KEEP_ALL` sentinel, whose cap
    exceeds any holdable stock and means "every copy is protected".

    LIVENESS — PASS iff the plan disposes SOME copy of the code. The authority
    says `SURPLUS` copies are sheddable (`bankable`/`destroyable` return exactly
    that); a plan that sheds none of them under real bag pressure contradicts it,
    and that contradiction is the hoard bug."""
    disposed = disposed_quantity(cell, plan, state, game_data)
    if cell.kind == "safety":
        return cell.held - disposed >= min(cell.keep, cell.held)
    if cell.kind == "liveness":
        return disposed > 0
    raise ValueError(f"unknown cell kind {cell.kind!r}")


class InventoryGapClass(Enum):
    """Why a FAIL cell's surplus was not shed — one class per root cause, ordered
    from the declared exemption to the actionable residual (see `classify_gap`'s
    cascade). The craft-census discipline: a FAIL is only NOT a bug when it
    carries a distinct, non-planner reason."""

    KEEP_ALL_SENTINEL = "keep_all_sentinel"
    """CURRENCY (`tasks_coin`) — never disposable BY DESIGN. The single declared
    exemption from the liveness half of the reason-coverage gate; every other
    reason must prove its surplus is sheddable. Classifies the (never-generated)
    CURRENCY liveness obligation only — a CURRENCY SAFETY cell that fails means a
    plan DISPOSED currency, which is a bug like any other and falls through this
    arm to the cascade below."""
    VENUE_UNREACHABLE = "venue_unreachable"
    """The route's venue exists in the catalog but has no tile the character can
    reach: no bank location for a bag-cap cell; an unplaced workshop / vendor for
    an owned-cap cell. Nothing the planner can do this cycle."""
    BANK_FULL = "bank_full"
    """The bank is at capacity, so DEPOSIT cannot take the surplus. A bag-cap
    (`keep_in_bag`) explanation only: for an owned-cap cell the bank was never a
    route (banking retains ownership), so a full bank explains nothing there — it
    is that cell's PRECONDITION (see `_bank`) and must not excuse it."""
    NO_ROUTE_AVAILABLE = "no_route_available"
    """The surplus exists but no route can fire this cycle: not recyclable (no
    recipe, or a non-recycling craft skill, or no workshop), no NPC buyer, and the
    DELETE route's quantity watermark is not reached — so production is right to
    keep holding it. Legitimately un-sheddable now."""
    INVENTORY_BUG = "inventory_bug"
    """The residual: a route was available and the authority licensed the
    disposal, yet the planner did not take it (or disposed a protected copy).
    UNEXPLAINED — never "expected". THE actionable class; it must reach 0."""


def _recyclable(code: str, game_data: GameData) -> bool:
    """`code` can be recycled at a PLACED workshop: it has a crafting recipe whose
    skill is one the server's /recycling endpoint accepts (`RECYCLING_SKILLS` —
    cooking/alchemy products are refused outright), and that workshop is on the
    map. Intrinsic to the ITEM and the WORLD — deliberately independent of any
    keep/protection logic, which is the thing under test: reading
    `recyclable_surplus` here would let a blanket-protected hoard classify itself
    as "no route" and the census would excuse the very bug it hunts."""
    stats = game_data.item_stats(code)
    if stats is None or not game_data.crafting_recipe(code):
        return False
    if stats.crafting_skill not in RECYCLING_SKILLS:
        return False
    return game_data.workshop_location(stats.crafting_skill) is not None


def _sellable(code: str, game_data: GameData) -> bool:
    """Some PLACED NPC buys `code` (intrinsic, protection-free — same rationale as
    `_recyclable`)."""
    return any(game_data.npc_location(npc) is not None
               for npc, _price in game_data.npcs_buying_item(code))


def _delete_pressure(state: WorldState) -> bool:
    """The DISCARD guards' watermark is reached, so DELETE is a route production
    could fire this cycle. Quantity-only, exactly as `guards._fires` reads it: the
    discard ladder is deliberately blind to SLOT pressure so slot-full never
    deletes what banking could have saved. A state below the watermark simply has
    no delete route — the item is not junk, it is just held."""
    if state.inventory_max <= 0:
        return False
    return (state.inventory_used * PRESSURE_HIGH_DEN
            >= state.inventory_max * PRESSURE_HIGH_NUM)


def classify_gap(cell: InventoryCell, state: WorldState,
                 game_data: GameData) -> InventoryGapClass:
    """Classify a FAIL cell's root cause. Pure over (`cell`, `state`,
    `game_data`); INVENTORY_BUG is the FALL-THROUGH, never a positive match, so a
    cell is blamed on the planner only after every world-limit explanation is
    ruled out.

    Precedence — KEEP_ALL_SENTINEL -> VENUE_UNREACHABLE -> BANK_FULL ->
    NO_ROUTE_AVAILABLE -> INVENTORY_BUG — runs most-specific-first:

    * KEEP_ALL_SENTINEL is the DECLARED exemption and only ever applies to a
      CURRENCY LIVENESS obligation (which `inventory_grid` never generates — the
      exemption is declared here rather than discovered). A failing CURRENCY
      SAFETY cell is a plan disposing currency: it falls through to the cascade.
    * VENUE_UNREACHABLE outranks the capacity/route arms: if the route's venue
      cannot be reached, its capacity is moot.
    * BANK_FULL only explains a BAG-cap cell (deposit is not an ownership route).
    * NO_ROUTE_AVAILABLE is the last world-limit: nothing could have fired.
    * INVENTORY_BUG: a route was there and the authority licensed the shed."""
    if cell.reason is KeepReason.CURRENCY and cell.kind == "liveness":
        return InventoryGapClass.KEEP_ALL_SENTINEL
    if cell.cap == "in_bag":
        if game_data.bank_location_or_none is None:
            return InventoryGapClass.VENUE_UNREACHABLE
        if not bank_has_room(True, state.bank_items, game_data.bank_capacity):
            return InventoryGapClass.BANK_FULL
        return InventoryGapClass.INVENTORY_BUG
    recyclable = _recyclable(cell.code, game_data)
    sellable = _sellable(cell.code, game_data)
    stats = game_data.item_stats(cell.code)
    if (not recyclable and stats is not None and game_data.crafting_recipe(cell.code)
            and stats.crafting_skill in RECYCLING_SKILLS):
        # Recyclable by TYPE but its workshop is not on the map — a venue limit,
        # not an absent route.
        return InventoryGapClass.VENUE_UNREACHABLE
    if not sellable and game_data.npcs_buying_item(cell.code):
        # A buyer exists in the catalog but sits on no reachable tile.
        return InventoryGapClass.VENUE_UNREACHABLE
    if not recyclable and not sellable and not _delete_pressure(state):
        return InventoryGapClass.NO_ROUTE_AVAILABLE
    return InventoryGapClass.INVENTORY_BUG

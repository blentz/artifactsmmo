"""Generate the next action for a deterministic gather-craft GatherMaterialsGoal.

Replaces an expensive GOAP A* search (~52K nodes/cycle for copper_ring) with an
O(recipe-closure) lookup when the goal is a pure gather-craft chain — every leaf
is either a gatherable raw resource or a craftable item whose skill gate is met.

THE ONE OBTAIN MODEL (`ai/obtain_sources.Source`) is what this generator reads
for everything beyond the bare recipe DAG. `sources` — a priority-ordered
`{item: [Source, ...]}` map built ONCE per cycle by the caller via
`obtain_sources.obtain_source_map` — is threaded straight into
`craft_plan_driver_core.craft_plan_full`, which already knows how to walk
WITHDRAW/RECYCLE/CRAFT/GATHER/BUY/DROP (Tasks 1-3 of this epic). This module
used to hand-bolt three of those six routes on top of a bare 3-kind
(gather/craft/withdraw) walk — a recycle prefix, a monster-drop-Fight lookup,
and an NPC-buy decline — duplicating exactly what `obtain_sources` now models
once. Task 4 (THE ACTIVATION) deleted all three bolt-ons: with `sources`
non-empty, `craft_plan_full` itself emits the recycle/buy/drop legs, in the
same single deterministic descent as gather/withdraw/craft, so a partial
recycle recovery interleaves with a gather/craft remainder as ONE mixed plan
instead of a separately-simulated prefix. `sources` defaults to empty, which
degrades every closure walk here to the original 3-kind behavior byte-for-byte.

Falls back to None (A* fallback) for:
- non-GatherMaterialsGoal goals
- closures that contain a raw (non-craftable) leaf that is neither a
  gatherable resource drop NOR served by any source in `sources` (an
  unmodeled monster-drop / NPC-buy leaf — GatherMaterials' buy arm / A* /
  is_plannable own those honestly)
- closures that have any craft whose skill gate is not yet met AND no matching
  `LevelSkill(skill, craft_level)` is present in `actions` (when one IS
  present, the generator emits `[LevelSkill]` instead — one leg per cycle,
  mirroring the Fight/DROP truncation below — so the next cycle's replan
  re-derives the gather/craft legs once the grind lands)
- closures where a NON-TOP-LEVEL input/intermediate is both banked AND short in
  inventory: that banked material would need a WithdrawItemAction before use;
  the generator cannot emit withdraws, so A* handles Withdraw→Craft correctly.
  Top-level targets (goal._needed keys) are excluded from this check — a banked
  finished good is an output, not an input that needs withdrawing.

SAFETY NET, NOT ADMIT-TIME FILTERING. `sources` admits a DROP/RECYCLE leaf on
`is_winnable` / `destroyable` capacity alone — it says nothing about a Fight's
level+2 suicide guard, HP floor, free-inventory gate, or a Recycle's bag/owned
floor, and it does not need to: the executor (`GamePlayer._plan_or_reuse` via
`should_replan`) re-validates `is_applicable` on the CURRENT plan head every
cycle before ever calling `execute`, so a leg that becomes inapplicable by the
time it is reached is caught there, never blindly run. This generator supplies
its OWN matching safety net for the leg it is about to hand back THIS cycle:
the first-leg applicability gate in `_finish` below.
"""

import dataclasses
import math
from collections.abc import Mapping

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.craft_plan_driver_core import craft_plan_full
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.intermediate_batch import size_intermediate_craft
from artifactsmmo_cli.ai.next_craft_core import NextAction
from artifactsmmo_cli.ai.obtain_sources import Source, SourceKind
from artifactsmmo_cli.ai.recipe_closure import closure_demand
from artifactsmmo_cli.ai.world_state import WorldState


def _closure_items(
    recipes: dict[str, dict[str, int]],
    needed: dict[str, int],
) -> set[str]:
    """Return every ITEM CODE appearing in the recipe closure of `needed`.

    Note: recipe_closure.recipe_closure_pure is the shared closure engine, but
    it returns RESOURCE NODE codes for raw leaves (e.g. "copper_rocks"), whereas
    the CAN-GENERATE gate here needs ITEM codes (e.g. "copper_ore") to check
    skill gates, workshop availability, and bank quantities.  Those two namespaces
    are distinct, so we keep this hand-rolled DFS rather than forcing a mismatched
    reuse.  The walk is acyclic because game recipe graphs are DAGs; the seen-guard
    ensures termination even for hypothetically cyclic inputs.
    """
    seen: set[str] = set()
    stack: list[str] = list(needed)
    while stack:
        item = stack.pop()
        if item in seen:
            continue
        seen.add(item)
        recipe = recipes.get(item)
        if recipe:
            stack.extend(recipe)
    return seen


def generate_next_craft_action(
    goal: object,
    state: WorldState,
    game_data: GameData,
    actions: list[Action],
    sources: Mapping[str, list[Source]] | None = None,
) -> list[Action] | None:
    """Return the next action(s) for a deterministic gather-craft goal, or ``None``.

    Returns ``None`` (fall back to A*) when:
    - ``goal`` is not a :class:`~artifactsmmo_cli.ai.goals.gathering.GatherMaterialsGoal`
    - Any item in the recipe closure has no recipe, is not a gatherable raw
      resource, AND has no entry in `sources` (NPC-buy leaves the model
      declined, or unwinnable/unreachable droppers — GatherMaterials' buy arm /
      A* / is_plannable own those honestly)
    - Any craftable item in the closure has a skill gate the character has not
      met AND ``actions`` has no matching ``LevelSkill(skill, craft_level)``
      (when one IS present, returns ``[LevelSkill]`` instead — one leg per
      cycle, same truncation idiom as the Fight/DROP leg below)
    - A closure INPUT/INTERMEDIATE (not a top-level target in ``goal._needed``) is
      banked AND inventory is short of the required quantity: that item must be
      withdrawn before crafting; the generator has no "withdraw" step, so it defers
      to A* which correctly emits Withdraw→Craft.

    The bank gate is PRECISE — it does NOT fire when:
    - The banked item is the top-level craft target (it is an output, not an input
      that needs withdrawing before use).
    - The banked item is a closure input/intermediate but inventory already covers
      the required quantity (the bank holds surplus; no withdraw needed).

    When a single unambiguous next action (or short deterministic chain) can be
    derived, returns a list of concrete actions from
    :meth:`~artifactsmmo_cli.ai.goals.gathering.GatherMaterialsGoal.relevant_actions`.
    This avoids the 52K-node A* search that copper_ring-style goals otherwise
    trigger on every cycle.
    """
    if not isinstance(goal, GatherMaterialsGoal):
        return None

    recipes: dict[str, dict[str, int]] = dict(game_data.crafting_recipes)
    needed: dict[str, int] = goal.needed

    # THE WITHDRAW ROUTE IS OWNED BY THE RECIPE DESCENT, NOT THE SOURCE MAP.
    # `next_craft_core._next` already withdraws a banked recipe INPUT with LIVE
    # bank accounting (`min(bank[inp], shortfall)`, kernel-proved) — the common,
    # load-bearing case. A WITHDRAW `Source` would only (a) DUPLICATE that for
    # inputs and (b) for a recipe-LESS top-level target (a monster-drop leaf that
    # happens to be banked) carry a STATIC `capacity` snapshot the multi-step
    # driver never decrements, so a target short of full bank stock over-withdraws
    # a PHANTOM copy past what the bank holds (feather: bank 2, need 3 → a bogus
    # 3rd Withdraw). Dropping WITHDRAW here keeps exactly ONE withdraw mechanism
    # (DRY — the proven descent), and a banked recipe-less target with no other
    # route declines to A* exactly as it did before THE ACTIVATION. The epic's
    # activation is RECYCLE/BUY/DROP; all three are kept. (A proper bank-live
    # WITHDRAW capacity belongs in the shared core + its Lean mirror, out of
    # this task's scope.)
    sources = {item: [s for s in srcs if s.kind is not SourceKind.WITHDRAW]
               for item, srcs in (sources or {}).items()}

    # Collect every item code in the recipe closure.
    closure = _closure_items(recipes, needed)

    # Gatherable raw item codes: items that are produced by some resource node.
    gatherable_items: set[str] = set(game_data.gatherable_drop_items())

    # CAN-GENERATE gate: every closure item must be either a craftable (with met
    # skill gate AND a known workshop), a gatherable raw, or served by some
    # source in the shared obtain model (RECYCLE/BUY/DROP). `relevant` is
    # computed lazily on the first LevelSkill emission so the pure
    # gather-craft fast path and the early A*-fallback returns stay as cheap
    # as before; the successful path needs it anyway (mapping below).
    relevant: list[Action] | None = None
    for item in closure:
        recipe = recipes.get(item)
        if recipe is not None:
            # Craftable: check skill gate and workshop availability.
            stats = game_data.item_stats(item)
            if stats is None or stats.crafting_skill is None:
                return None  # Unknown craft requirements → fall back to A*.
            if game_data.workshop_location(stats.crafting_skill) is None:
                return None  # No workshop for this skill → fall back to A*.
            if state.skills.get(stats.crafting_skill, 1) < stats.crafting_level:
                # Skill gate not met: a skill-gated craft is simply not a CRAFT
                # source until the gate is met (obtain_sources._craft_sources
                # would decline it too). Emit the matching LevelSkill leg
                # instead (one-leg-per-cycle, mirroring the Fight/DROP
                # truncation) if the caller surfaced one; otherwise fall back
                # to A*.
                lvl = next((a for a in actions
                            if isinstance(a, LevelSkill)
                            and a.skill == stats.crafting_skill
                            and a.target_level == stats.crafting_level), None)
                # Gate the emit on is_applicable NOW: a LevelSkill with no
                # obtainable grind rung (skill_grind_target is None) must never
                # be emitted — it would reach the player's grind dead-end guard.
                # Fall back to A* (also is_applicable-gated → won't pick it →
                # honest no-plan) instead. Restores the safety net that
                # build_actions' emit-per-(skill,level) otherwise bypasses.
                if lvl is None or not lvl.is_applicable(state, game_data):
                    return None
                return _finish([lvl], state, game_data)
        elif item not in gatherable_items and not sources.get(item):
            # Raw leaf that no resource drops AND the shared obtain model has
            # no RECYCLE/BUY/DROP source for it either (an unmodeled monster
            # drop, an NPC-buy leaf the model declined, or a genuinely
            # unreachable/unwinnable route) → fall back to A* honestly.
            return None

    if relevant is None:
        relevant = goal.relevant_actions(actions, state, game_data)

    owned: dict[str, int] = dict(state.inventory)
    bank: dict[str, int] = state.bank_items or {}

    # Build the FULL deterministic plan for the first needed item that isn't
    # already satisfied, then map each step to a concrete action.  The player's
    # PlanCache caches this plan and executes it step-by-step, re-validating each
    # step (is_applicable / should_replan) and re-planning on any divergence — so
    # the simulated multi-step plan degrades safely against live state.  Mirrors
    # the kernel-proved `craftPlan` (Formal/CraftPlanDriver.lean): every step is a
    # genuine next move (craftPlan_steps_valid) and a complete plan reaches the
    # target (craftPlan_reaches).
    for item, qty in needed.items():
        plan = craft_plan_full(recipes, owned, bank, item, qty, sources)
        if not plan:
            continue  # this item already satisfied; try the next needed item
        chain: dict[str, int] = {}
        closure_demand(item, qty, game_data, chain, frozenset())
        mapped: list[Action] = []
        for na in plan:
            action = _map_next_action(na, relevant, game_data, sources)
            if action is None:
                return None  # a step has no concrete action → fall back to A*
            if isinstance(action, CraftAction):
                action = size_intermediate_craft(action, chain, state, game_data)
            mapped.append(action)
            if isinstance(action, FightAction):
                # One-leg-per-cycle (GAP-8): a kill's drop yield is
                # stochastic (rate/min/max), so every simulated step after a
                # Fight assumes materials that may not arrive. Truncate at
                # the Fight — the next cycle's replan re-derives the
                # remaining legs from the REAL post-fight inventory (the
                # same grind-one-replan idiom the skill dispatch uses).
                break
        return _finish(mapped, state, game_data)
    return None  # every needed item already satisfied


def _finish(mapped: list[Action], state: WorldState,
            game_data: GameData) -> list[Action] | None:
    """Front an optimal-loadout re-arm when the plan opens with a suboptimal
    Gather/Fight, then gate the whole plan on the first leg's applicability NOW.

    The directed fast-path emits a deterministic recycle/withdraw/gather/craft/
    buy/drop leg but does NOT model every inventory-room precondition. If the
    first leg is not applicable NOW (e.g. a stack-creating gather blocked by a
    full slot cap — the slot-exhaustion case, or a Fight that fails its
    suicide guard, or a Recycle that violates its bag/owned floor), defer to
    A*, which sequences the slot-freeing relief (DepositAll/Recycle/Sell)
    before the leg, or finds no plan honestly.

    `mapped` is always non-empty at both call sites (a LevelSkill leg, or a
    non-empty `craft_plan_full` plan)."""
    result = _with_rearm(mapped, state, game_data)
    if not result[0].is_applicable(state, game_data):
        return None
    return result


def _with_rearm(mapped: list[Action], state: WorldState,
                game_data: GameData) -> list[Action]:
    """Front the per-skill (Gather) or per-monster (Fight) loadout optimizer
    right before the FIRST Gather/Fight leg in `mapped`, when that leg's
    loadout is suboptimal. This generated path bypasses A* entirely
    (nodes=0), so the loadout-penalty cost terms never get a vote here —
    live trace 2026-07-05: every generated helmet plan opened bare-handed
    while the ferried copper_pickaxe rode in the bag.

    SCANS PAST any leading Recycle/Withdraw/Craft/Buy legs rather than only
    inspecting `mapped[0]` (whole-branch review, IMPORTANT 2, re-derived
    under the shared obtain model): recycle is now an ORDINARY leg in the
    SAME plan `craft_plan_full` returns, so a plan can be
    `[Recycle, Gather, Craft]` with the Recycle at index 0 — checking only
    `mapped[0]` would silently skip the re-arm and let the plan cache
    execute the Gather bare-handed, recreating the exact bug this helper
    exists to fix. Equipping a tool is unaffected by a prior recycle/
    withdraw/craft/buy leg, so `rearm.is_applicable` is still asked of the
    CURRENT `state` (the legs ahead of the Gather/Fight don't touch
    equipment) — only the INSERTION POINT moves, not the state it is judged
    against. A plan with no Gather/Fight leg at all (pure
    recycle/withdraw/craft/buy) is returned unchanged.

    Fight mirror (Task 5b Part 3): a mapped plan's Fight leg may be
    structurally fine but equipped suboptimally for the monster — the hard
    loadout gate would then reject it at execution (player.py runs plan[0]
    directly). Front `OptimizeLoadout(target_monster_code=...)` whenever it is
    `is_applicable`: `_swap_plan` is empty (and so `is_applicable` False) when
    the equipped loadout is already optimal for that monster, so this check is
    self-guarding — no separate `equipped_matches_loadout` predicate needed
    here."""
    for i, action in enumerate(mapped):
        if isinstance(action, FightAction):
            rearm = OptimizeLoadoutAction(
                target_monster_code=action.monster_code, game_data=game_data
            )
            if not rearm.is_applicable(state, game_data):
                return mapped  # loadout already optimal for this monster
            return [*mapped[:i], rearm, *mapped[i:]]
        if isinstance(action, GatherAction):
            skill_req = game_data.resource_skill_level(action.resource_code)
            if skill_req is None:
                return mapped
            rearm = OptimizeLoadoutAction(target_skill=skill_req[0], game_data=game_data)
            if not rearm.is_applicable(state, game_data):
                return mapped  # loadout already optimal for this skill
            return [*mapped[:i], rearm, *mapped[i:]]
    return mapped


def _map_next_action(
    na: NextAction, relevant: list[Action], game_data: GameData,
    sources: Mapping[str, list[Source]],
) -> Action | None:
    """Map one NextAction to a concrete action from `relevant`, or None if absent."""
    if na.kind == "gather":
        for action in relevant:
            if (
                isinstance(action, GatherAction)
                and game_data.resource_drop_item(action.resource_code) == na.item
            ):
                return action
        return None
    if na.kind == "withdraw":
        for action in relevant:
            if isinstance(action, WithdrawItemAction) and action.code == na.item:
                # Honor the core's bank-CLAMPED quantity (min(bank_stock, deficit),
                # next_craft_core._next). The factory pre-builds withdraws at FIXED
                # quantities (full recipe requirement, per-craft, ×1); reusing one
                # by code alone over-withdraws when the bank holds fewer than the
                # requirement → HTTP 478, and the plan never reaches the gather step
                # that supplies the deficit (live Robby 2026-06-24: bank ash_plank=4
                # but Withdraw(ash_plank×7)→478 every cycle). Reuse the matched
                # action's bank_location/accessible, override the quantity.
                return dataclasses.replace(action, quantity=na.qty)
        return None
    if na.kind == "craft":
        for action in relevant:
            if isinstance(action, CraftAction) and action.code == na.item:
                return action
        return None
    if na.kind == "recycle":
        # RECYCLE consumes na.code (the SOURCE item being destroyed), not the
        # target -- yield_per lives on the matching Source (obtain_sources),
        # not on NextAction, so it is looked up here to convert the target
        # quantity the core asked for into the SOURCE quantity the concrete
        # RecycleAction must carry (mirrors craft_plan_driver_core._apply_state's
        # own ceil-debit, which this same `sources` map must agree with).
        match = next(
            (s for s in sources.get(na.item, ())
             if s.kind is SourceKind.RECYCLE and s.code == na.code),
            None,
        )
        if match is None:
            return None
        consumed = math.ceil(na.qty / match.yield_per)
        for action in relevant:
            if isinstance(action, RecycleAction) and action.code == na.code:
                return dataclasses.replace(action, quantity=consumed)
        return None
    if na.kind == "buy":
        for action in relevant:
            if (isinstance(action, NpcBuyAction) and action.npc_code == na.code
                    and action.item_code == na.item):
                return dataclasses.replace(action, quantity=na.qty)
        return None
    # na.kind == "drop"
    droppers = {m for m, _rate, _mn, _mx in game_data.monsters_dropping(na.item)}
    for action in relevant:
        if isinstance(action, FightAction) and action.monster_code in droppers:
            return action
    return None

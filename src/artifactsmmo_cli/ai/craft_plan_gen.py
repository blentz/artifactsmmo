"""Generate the next action for a deterministic gather-craft GatherMaterialsGoal.

Replaces an expensive GOAP A* search (~52K nodes/cycle for copper_ring) with an
O(recipe-closure) lookup when the goal is a pure gather-craft chain — every leaf
is either a gatherable raw resource or a craftable item whose skill gate is met.

Falls back to None (A* fallback) for:
- non-GatherMaterialsGoal goals
- closures that contain a monster-drop leaf with NO winnable-dropper Fight
  in the goal's relevant_actions (GAP-8: a drop leaf whose dropper IS
  emitted — winnable, xp-positive or grey-farm-allowed — gets a Fight leg
  instead; the generated plan truncates at the Fight, one leg per cycle)
- closures that contain NPC-buy / currency leaves
- closures that have any craft whose skill gate is not yet met
- closures where a NON-TOP-LEVEL input/intermediate is both banked AND short in
  inventory: that banked material would need a WithdrawItemAction before use;
  the generator cannot emit withdraws, so A* handles Withdraw→Craft correctly.
  Top-level targets (goal._needed keys) are excluded from this check — a banked
  finished good is an output, not an input that needs withdrawing.

The precise bank gate (rather than a blanket "any banked closure item → None")
preserves the fast-path for the two common mid-game states:
  - banked TARGET (finished output) — generator still fires, re-makes remainder
  - banked SURPLUS input (inventory already covers the requirement) — also fires
"""

import dataclasses

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.craft_plan_driver_core import craft_plan_full
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.intermediate_batch import size_intermediate_craft
from artifactsmmo_cli.ai.next_craft_core import NextAction
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
) -> list[Action] | None:
    """Return ``[next_action]`` for a deterministic gather-craft goal, or ``None``.

    Returns ``None`` (fall back to A*) when:
    - ``goal`` is not a :class:`~artifactsmmo_cli.ai.goals.gathering.GatherMaterialsGoal`
    - Any item in the recipe closure has no recipe, is not a gatherable raw
      resource, AND has no winnable-dropper Fight in the goal's
      relevant_actions (NPC-buy leaves, unwinnable/suppressed droppers —
      GatherMaterials' buy arm / A* / is_plannable own those honestly)
    - Any craftable item in the closure has a skill gate the character has not met
    - A closure INPUT/INTERMEDIATE (not a top-level target in ``goal._needed``) is
      banked AND inventory is short of the required quantity: that item must be
      withdrawn before crafting; the generator has no "withdraw" step, so it defers
      to A* which correctly emits Withdraw→Craft.

    The bank gate is PRECISE — it does NOT fire when:
    - The banked item is the top-level craft target (it is an output, not an input
      that needs withdrawing before use).
    - The banked item is a closure input/intermediate but inventory already covers
      the required quantity (the bank holds surplus; no withdraw needed).

    When a single unambiguous next action can be derived, returns a one-element
    list containing the matching action from
    :meth:`~artifactsmmo_cli.ai.goals.gathering.GatherMaterialsGoal.relevant_actions`.
    This avoids the 52K-node A* search that copper_ring-style goals otherwise
    trigger on every cycle.
    """
    if not isinstance(goal, GatherMaterialsGoal):
        return None

    recipes: dict[str, dict[str, int]] = dict(game_data.crafting_recipes)
    needed: dict[str, int] = goal.needed

    # Collect every item code in the recipe closure.
    closure = _closure_items(recipes, needed)

    # Gatherable raw item codes: items that are produced by some resource node.
    gatherable_items: set[str] = set(game_data.gatherable_drop_items())

    bank: dict[str, int] = state.bank_items or {}

    # CAN-GENERATE gate: every closure item must be either a craftable (with met
    # skill gate AND a known workshop), a gatherable raw, or a monster drop
    # whose chosen dropper Fight the goal's relevant_actions emits (GAP-8).
    # `relevant` is computed lazily on the first drop leaf so the pure
    # gather-craft fast path and the early A*-fallback returns stay as cheap
    # as before; the successful path needs it anyway (mapping below).
    relevant: list[Action] | None = None
    drop_fights: dict[str, FightAction] = {}
    for item in closure:
        recipe = recipes.get(item)
        if recipe is not None:
            # Craftable: check skill gate and workshop availability.
            stats = game_data.item_stats(item)
            if stats is None or stats.crafting_skill is None:
                return None  # Unknown craft requirements → fall back to A*.
            if state.skills.get(stats.crafting_skill, 1) < stats.crafting_level:
                return None  # Skill gate not met → fall back to A*.
            if game_data.workshop_location(stats.crafting_skill) is None:
                return None  # No workshop for this skill → fall back to A*.
        elif item not in gatherable_items:
            # Raw leaf that no resource drops: a monster-drop leaf is served
            # by a Fight leg IF the goal's own relevant_actions emitted its
            # dropper — the GAP-6-proven wiring (select_monster_for_drop
            # winner, is_winnable-gated, xp-positive plain Fight or
            # grey_farm_allowed drop_farm variant) already decided WHICH
            # fight, and whether one is allowed at all. No emitted fight
            # (unwinnable dropper, suppressed grey, or a pure NPC-buy leaf
            # with no dropper) → fall back to A* honestly.
            if relevant is None:
                relevant = goal.relevant_actions(actions, state, game_data)
            fight = _dropper_fight(item, relevant, game_data)
            if fight is None:
                return None  # No Fight leg for this leaf → fall back to A*.
            drop_fights[item] = fight

    # owned = INVENTORY; the bank is passed SEPARATELY to the core.  A banked
    # craftable intermediate (e.g. copper_bar) no longer forces an A* Withdraw→Craft
    # search: the core emits a "withdraw" NextAction for the first short input that
    # is in the bank (mirrors the kernel-proved Lean `nextHelper` withdraw arm),
    # which we map to a WithdrawItemAction below.  Top-level targets are never
    # withdrawn (the descent only checks INPUTS), so a banked finished output is
    # still re-made from scratch.
    owned: dict[str, int] = dict(state.inventory)

    if relevant is None:
        relevant = goal.relevant_actions(actions, state, game_data)

    # Build the FULL deterministic plan for the first needed item that isn't
    # already satisfied, then map each step to a concrete action.  The player's
    # PlanCache caches this plan and executes it step-by-step, re-validating each
    # step (is_applicable / should_replan) and re-planning on any divergence — so
    # the simulated multi-step plan degrades safely against live state.  Mirrors
    # the kernel-proved `craftPlan` (Formal/CraftPlanDriver.lean): every step is a
    # genuine next move (craftPlan_steps_valid) and a complete plan reaches the
    # target (craftPlan_reaches).
    for item, qty in needed.items():
        plan = craft_plan_full(recipes, owned, bank, item, qty)
        if not plan:
            continue  # this item already satisfied; try the next needed item
        chain: dict[str, int] = {}
        closure_demand(item, qty, game_data, chain, frozenset())
        mapped: list[Action] = []
        for na in plan:
            action = _map_next_action(na, relevant, game_data, drop_fights)
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
        return _with_rearm(mapped, state, game_data)
    return None  # all needed items already satisfied — let normal path handle it


def _with_rearm(mapped: list[Action], state: WorldState,
                game_data: GameData) -> list[Action]:
    """Front the per-skill loadout optimizer when the plan opens with a Gather
    whose loadout is suboptimal. This generated path bypasses A* entirely
    (nodes=0), so GATHER_LOADOUT_PENALTY never gets a vote here — live trace
    2026-07-05: every generated helmet plan opened bare-handed while the
    ferried copper_pickaxe rode in the bag. Plans opening with a Craft are
    left alone; a later Gather-first regeneration re-arms then."""
    first = mapped[0] if mapped else None
    if not isinstance(first, GatherAction):
        return mapped
    skill_req = game_data.resource_skill_level(first.resource_code)
    if skill_req is None:
        return mapped
    rearm = OptimizeLoadoutAction(target_skill=skill_req[0], game_data=game_data)
    if not rearm.is_applicable(state, game_data):
        return mapped  # loadout already optimal for this skill
    return [rearm, *mapped]


def _dropper_fight(
    item: str, relevant: list[Action], game_data: GameData
) -> FightAction | None:
    """The Fight in `relevant` whose monster drops `item`, or None.

    GatherMaterialsGoal.relevant_actions already narrowed every closure
    drop item to at most ONE dropper fight (the expected-kills-optimal
    winnable winner, formal/Formal/MonsterDropSelection.lean; grey droppers
    arrive as the drop_farm variant under grey_farm_allowed) — this helper
    only re-associates that emitted fight with the leaf it serves."""
    droppers = {m for m, _rate, _mn, _mx in game_data.monsters_dropping(item)}
    for action in relevant:
        if isinstance(action, FightAction) and action.monster_code in droppers:
            return action
    return None


def _map_next_action(
    na: NextAction, relevant: list[Action], game_data: GameData,
    drop_fights: dict[str, FightAction],
) -> Action | None:
    """Map one NextAction to a concrete action from `relevant`, or None if absent."""
    if na.kind == "gather":
        for action in relevant:
            if (
                isinstance(action, GatherAction)
                and game_data.resource_drop_item(action.resource_code) == na.item
            ):
                return action
        # GAP-8: the core emits "gather" for ANY recipe-less leaf; a
        # monster-drop leaf has no GatherAction — its leg is the dropper
        # Fight the CAN-GENERATE gate collected (the caller truncates the
        # plan there, one leg per cycle). Only consulted when the item is
        # NOT gatherable: a gatherable leaf whose gather is missing from
        # `relevant` still falls back to A* (return None) as before.
        return drop_fights.get(na.item)
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
    # na.kind == "craft"
    for action in relevant:
        if isinstance(action, CraftAction) and action.code == na.item:
            return action
    return None

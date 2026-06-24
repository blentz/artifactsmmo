"""Generate the next action for a deterministic gather-craft GatherMaterialsGoal.

Replaces an expensive GOAP A* search (~52K nodes/cycle for copper_ring) with an
O(recipe-closure) lookup when the goal is a pure gather-craft chain — every leaf
is either a gatherable raw resource or a craftable item whose skill gate is met.

Falls back to None (A* fallback) for:
- non-GatherMaterialsGoal goals
- closures that contain monster-drop leaves
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
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.craft_plan_driver_core import craft_plan_full
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.next_craft_core import NextAction
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
    - Any item in the recipe closure has no recipe AND is not a gatherable raw
      resource (e.g. monster drops, NPC-buy items)
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
    gatherable_items: set[str] = set(game_data.resource_drops.values())

    bank: dict[str, int] = state.bank_items or {}

    # CAN-GENERATE gate: every closure item must be either a craftable (with met
    # skill gate AND a known workshop) or a gatherable raw.
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
        else:
            # Raw leaf: must be gatherable (resource drop).
            if item not in gatherable_items:
                return None  # Monster drop / NPC-buy leaf → fall back to A*.

    # owned = INVENTORY; the bank is passed SEPARATELY to the core.  A banked
    # craftable intermediate (e.g. copper_bar) no longer forces an A* Withdraw→Craft
    # search: the core emits a "withdraw" NextAction for the first short input that
    # is in the bank (mirrors the kernel-proved Lean `nextHelper` withdraw arm),
    # which we map to a WithdrawItemAction below.  Top-level targets are never
    # withdrawn (the descent only checks INPUTS), so a banked finished output is
    # still re-made from scratch.
    owned: dict[str, int] = dict(state.inventory)

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
        mapped: list[Action] = []
        for na in plan:
            action = _map_next_action(na, relevant, game_data)
            if action is None:
                return None  # a step has no concrete action → fall back to A*
            mapped.append(action)
        return mapped
    return None  # all needed items already satisfied — let normal path handle it


def _map_next_action(
    na: NextAction, relevant: list[Action], game_data: GameData
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
    # na.kind == "craft"
    for action in relevant:
        if isinstance(action, CraftAction) and action.code == na.item:
            return action
    return None

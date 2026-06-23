"""Generate the next action for a deterministic gather-craft GatherMaterialsGoal.

Replaces an expensive GOAP A* search (~52K nodes/cycle for copper_ring) with an
O(recipe-closure) lookup when the goal is a pure gather-craft chain — every leaf
is either a gatherable raw resource or a craftable item whose skill gate is met.

Falls back to None (A* fallback) for:
- non-GatherMaterialsGoal goals
- closures that contain monster-drop leaves
- closures that contain NPC-buy / currency leaves
- closures that have any craft whose skill gate is not yet met
- closures where ANY closure item has a positive bank quantity (a banked material
  needs a WithdrawItemAction before use; the generator cannot emit withdraws — A*
  will handle Withdraw→Craft correctly)
"""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.next_craft_core import NextAction, next_craft_target_pure
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
    - Any closure item has a positive quantity in the bank: a banked material needs
      a WithdrawItemAction before CraftAction can use it; the generator has no
      "withdraw" kind, so it defers to A* which correctly emits Withdraw→Craft.

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
    # skill gate AND a known workshop) or a gatherable raw.  Also fall back to A*
    # whenever any closure item has a positive bank quantity — the generator cannot
    # emit a WithdrawItemAction, so emitting CraftAction without a prior withdraw
    # would cause a runtime API failure.  A* correctly emits Withdraw→Craft.
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

        # Banked material: A* will emit WithdrawItemAction → CraftAction; the
        # generator only knows "gather" and "craft", so defer to A*.
        if bank.get(item, 0) > 0:
            return None  # Closure item present in bank → fall back to A*.

    # owned = INVENTORY ONLY.  Bank items are NOT available to CraftAction
    # without a prior WithdrawItemAction.  Counting bank items here would cause
    # the generator to skip a necessary withdraw step and crash the API call at
    # runtime.  (The CAN-GENERATE gate above already falls back to A* when any
    # bank quantity is non-zero, so this path is only reached for the from-scratch
    # gather-craft case where the bank holds no closure materials.)
    owned: dict[str, int] = dict(state.inventory)

    # Find the first non-None next action across all top-level needed items.
    na: NextAction | None = None
    for item, qty in needed.items():
        na = next_craft_target_pure(recipes, owned, item, qty)
        if na is not None:
            break

    if na is None:
        # All needed items satisfied in owned — let normal path handle it.
        return None

    # Map the NextAction to a concrete action from relevant_actions.
    relevant = goal.relevant_actions(actions, state, game_data)

    if na.kind == "gather":
        # Find the GatherAction whose resource yields na.item.
        for action in relevant:
            if (
                isinstance(action, GatherAction)
                and game_data.resource_drop_item(action.resource_code) == na.item
            ):
                return [action]
        return None  # No matching gather action found → fall back to A*.

    # na.kind == "craft"
    for action in relevant:
        if isinstance(action, CraftAction) and action.code == na.item:
            return [action]
    return None  # No matching craft action found → fall back to A*.

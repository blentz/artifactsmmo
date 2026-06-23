"""Generate the next action for a deterministic gather-craft GatherMaterialsGoal.

Replaces an expensive GOAP A* search (~52K nodes/cycle for copper_ring) with an
O(recipe-closure) lookup when the goal is a pure gather-craft chain — every leaf
is either a gatherable raw resource or a craftable item whose skill gate is met.

Falls back to None (A* fallback) for:
- non-GatherMaterialsGoal goals
- closures that contain monster-drop leaves
- closures that contain NPC-buy / currency leaves
- closures that have any craft whose skill gate is not yet met
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
    """Return every item appearing in the recipe closure of `needed`.

    Walks the recipe DAG depth-first, collecting every item code reachable from
    the top-level `needed` dict.  Terminates because crafting recipe graphs are
    acyclic (the game data guarantees this).
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

    # Collect every item in the recipe closure.
    closure = _closure_items(recipes, needed)

    # Gatherable raw item codes: items that are produced by some resource node.
    gatherable_items: set[str] = set(game_data.resource_drops.values())

    # CAN-GENERATE gate: every closure item must be either a craftable (with met
    # skill gate AND a known workshop) or a gatherable raw.  Return None on first
    # failure so A* takes over.
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

    # Compute owned = inventory + bank for the generator.
    owned: dict[str, int] = dict(state.inventory)
    for code, qty in (state.bank_items or {}).items():
        owned[code] = owned.get(code, 0) + qty

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

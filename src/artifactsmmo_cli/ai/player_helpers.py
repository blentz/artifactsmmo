"""Pure, side-effect-free helpers for the GamePlayer orchestrator.

These functions hold no player state. They live here to keep player.py focused
on the sense→plan→act→learn loop. player.py re-imports them so existing call
sites and test import/patch targets (``artifactsmmo_cli.ai.player._format_plan``,
``artifactsmmo_cli.ai.player._delete_cost``) keep working unchanged.
"""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData

PLAN_PREVIEW = 5
"""Max distinct steps shown in verbose plan output."""


def delete_cost(item_code: str, game_data: GameData) -> float:
    """Cost weight for deleting an item.

    Ingredient-first ordering: an item that's both a craft ingredient AND sellable
    gets the harsher penalty (50.0), not the milder sellable penalty (25.0).
    """
    is_ingredient = any(item_code in recipe for recipe in game_data._crafting_recipes.values())
    has_sell_price = bool(game_data.npcs_buying_item(item_code))
    if is_ingredient:
        return 50.0
    if has_sell_price:
        return 25.0
    return 5.0


def format_plan(plan: list[Action]) -> str:
    """Summarise a plan as 'A×N → B → C×M … (+K more)' instead of raw repetition."""
    if not plan:
        return ""
    segments: list[str] = []
    i = 0
    while i < len(plan) and len(segments) < PLAN_PREVIEW:
        step = repr(plan[i])
        count = 1
        while i + count < len(plan) and repr(plan[i + count]) == step:
            count += 1
        segments.append(f"{step}×{count}" if count > 1 else step)
        i += count
    remaining = len(plan) - i
    suffix = f" … (+{remaining} more)" if remaining > 0 else ""
    return " → ".join(segments) + suffix

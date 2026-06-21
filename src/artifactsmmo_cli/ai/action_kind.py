"""Pure mapping from an executed Action to a (kind, target) pair for the TUI.

One source of truth so the renderer never string-parses repr(action)."""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.rest import RestAction


def action_kind_of(action: object) -> tuple[str, str | None]:
    """Return (kind, target) for the TUI animation layer.

    kind ∈ {"move","gather","fight","rest","other"}; target is the gather
    resource / fight monster / "x,y" destination, or None."""
    if isinstance(action, MoveAction):
        return "move", f"{action.x},{action.y}"
    if isinstance(action, GatherAction):
        return "gather", action.resource_code
    if isinstance(action, FightAction):
        return "fight", action.monster_code
    if isinstance(action, RestAction):
        return "rest", None
    return "other", None

"""The fight refused for want of bag room (spec 2026-10-18 §2.10, ruling T13c).

A fight whose drops find no room in the bag is a loop that does not run: the
bag cap of its loadout, less what the bag carries through a deposit (the keep,
the food and potion carry), leaves nothing for a drop. `best_loadout` names that
verdict on the pick it threads as the cycle's loadout
(`ChosenLoadout.runnable`); the pick is still the fight's loadout, so the keep
and the preps keep serving it. This module is the other half of the ONE verdict:
the fight against that monster is refused, read off the same value on the
cycle's context, never recomputed.

Applied where the context is fully bound, the way the destruction licence is
(`destructive_license`): the arbiter drops the refused fight from the pool it
plans over, and the player's cached plan does not reuse a refused fight
(`GamePlayer._fight_ready`). Both name the refusal (`refusal_line`), so the
trace and the log say why the fight is off.
"""

from collections.abc import Sequence

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.selection_context import SelectionContext


def refused_fight(ctx: SelectionContext) -> str | None:
    """The monster whose fight this cycle refuses: the cycle's loadout's, when
    its loop has no room for the drops; None otherwise (no fight ahead, or a
    loop that runs)."""
    loadout = ctx.loadout
    if loadout is None or loadout.runnable:
        return None
    return loadout.monster


def license_fights(actions: Sequence[Action], ctx: SelectionContext) -> list[Action]:
    """`actions` less every fight against the refused monster (`refused_fight`)."""
    refused = refused_fight(ctx)
    return [action for action in actions
            if not (isinstance(action, FightAction) and action.monster_code == refused)]


def refusal_line(monster: str) -> str:
    """The log line naming a refused fight."""
    return (f"Fight {monster} refused: no room in the bag for its drops "
            "(the keep and the consumable carry fill it)")

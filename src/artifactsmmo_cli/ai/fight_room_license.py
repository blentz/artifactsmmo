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
from artifactsmmo_cli.ai.best_loadout import loadout_for
from artifactsmmo_cli.ai.chosen_loadout import ChosenLoadout
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState


def refused_monster(loadout: ChosenLoadout | None) -> str | None:
    """The monster `loadout`'s fight is refused against: its own, when its
    loop has no room for the drops; None otherwise (no pick, or a loop that
    runs). The ONE refusal verdict: the cycle's loadout (`refused_fight`) and
    a fight priced by `loadout_for` (`refuses_fight_against`) both read it."""
    if loadout is None or loadout.runnable:
        return None
    return loadout.monster


def refused_fight(ctx: SelectionContext) -> str | None:
    """The monster whose fight this cycle refuses: the cycle's loadout's
    (`refused_monster`)."""
    return refused_monster(ctx.loadout)


def refuses_fight_against(state: WorldState, game_data: GameData, ctx: SelectionContext,
                          monster: str) -> bool:
    """The fight against `monster` is refused, on the pick `loadout_for`
    prices it at (ruling T14d-2): the cycle's own when it was chosen against
    `monster`, else chosen now. The grind's fight (its heal prep's loadout) and
    a task step's fight read it at their step, so a fight the bag has no room
    for is refused there as the cycle's own is refused in the pool."""
    return refused_monster(loadout_for(state, game_data, ctx, monster)) == monster


def is_refused(action: Action, refused: str | None) -> bool:
    """`action` is a solo fight against the `refused` monster. The verdict is
    the solo loop's (its bag has no room for the drops); a party fight's loop
    counts no trips and always runs (`party_loop`), so it is never refused on
    it (T13e re-review minor 3)."""
    return (isinstance(action, FightAction) and not action.participants
            and action.monster_code == refused)


def license_fights(actions: Sequence[Action], ctx: SelectionContext) -> list[Action]:
    """`actions` less every solo fight against the refused monster
    (`refused_fight`, `is_refused`)."""
    refused = refused_fight(ctx)
    return [action for action in actions if not is_refused(action, refused)]


def refusal_line(monster: str) -> str:
    """The log line naming a refused fight."""
    return (f"Fight {monster} refused: no room in the bag for its drops "
            "(the keep and the consumable carry fill it)")

"""Whether the task objective should take a new task now — a leaf, shared by the
root walk's offer and the objective's step (Phase 5-2c-iii-c-2 #3; this was the
ACCEPT_TASK collect rung's firing predicate)."""

from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState


def accept_due(state: WorldState, ctx: SelectionContext) -> bool:
    """No task held, and a draw owed.

    A draw is OWED when the master's pool is worth drawing from
    (`task_worth.pool_draw`, USER 2026-10-07: rerolls cost at most the coins a
    completion pays), so a cancelled worthless draw is redrawn only while the
    pool's economics allow.

    USER 2026-10-06: no gear-chain deferral. The accept used to wait while any
    target gear was owned-unequipped or craftable at the current skill level —
    written when ACCEPT_TASK was a rung above the objective step. Since the
    accept became the task objective's step it waits for its own turn, and the
    gear chain gets its own turns. The deferral had become a standing fact:
    live 2026-10-06, `hard_leather_boots` (gearcrafting 20) was "craftable" for
    C3P0, Robby and HAL while no character worked it, and none had drawn a task
    in over a day."""
    return not state.task_code and ctx.draw_owed

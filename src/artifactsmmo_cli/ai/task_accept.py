"""Whether the task objective should take a new task now — a leaf, shared by the
root walk's offer and the objective's step (Phase 5-2c-iii-c-2 #3; this was the
ACCEPT_TASK collect rung's firing predicate)."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState


def accept_due(state: WorldState, game_data: GameData, ctx: SelectionContext) -> bool:
    """No task held, a draw owed, and no gear-chain work the draw would compete
    with.

    S-051 + the no-immediate-redraw rule: a draw must be OWED
    (`ctx.draw_owed`, set when the course changes and cleared once a task is
    held), so a discarded draw is not taken back at once.

    Defer while the player has GEAR-CHAIN work to do: (a) target gear OWNED but
    unequipped (the one-action equip should win first), or (b) target gear
    CRAFTABLE at current skill (the gather/craft chain should run rather than a
    task that competes for its materials). Trace 2026-06-06 12:28: 2
    copper_daggers crafted via CraftRelief never equipped; the armour set never
    started despite 2300+ gold and crafting skills at level 6+."""
    if state.task_code or not ctx.draw_owed:
        return False
    equipped = {c for c in state.equipment.values() if c is not None}
    for code in ctx.target_gear:
        if code in equipped:
            continue
        if state.inventory.get(code, 0) > 0:
            return False  # owned + unequipped → defer for UpgradeEquipment
        stats = game_data.item_stats(code)
        if stats is None or not stats.crafting_skill:
            continue
        if state.skills.get(stats.crafting_skill, 1) >= stats.crafting_level:
            return False  # craftable now → defer for gear chain
    return True

"""Bank tool fills: the strictly-better banked gathering tool per skill.

`loadout_picker.pick_loadout` scans only items the character already OWNS
(inventory + equipped), so a better tool sitting in the BANK is invisible to
the gather re-arm economics (GATHER_LOADOUT_PENALTY / OptimizeLoadout) — trace
2026-07-05: Robby mined copper_rocks for 300+ cycles with copper_dagger while
copper_pickaxe sat in the bank. This helper names those tools so the arbiter
can ferry them into the bag, where the proven re-arm takes over.
"""

from artifactsmmo_cli.ai.equipment.scoring import gather_score
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import _GATHERING_SKILLS
from artifactsmmo_cli.ai.world_state import WorldState


def bank_tool_fills(state: WorldState, game_data: GameData,
                    reserved: frozenset[str]) -> dict[str, str]:
    """{skill: code} for each gathering skill where the bank holds a tool
    strictly better (by ``tool_value``) than every owned candidate, excluding
    reserved codes and tools above the character's level.

    Owned = inventory + currently-equipped, mirroring the pick_loadout pool the
    fill is destined for; the strict inequality makes the goal self-satisfying
    (once withdrawn, owned >= bank and the fill disappears). Ties among equal
    bank tools break by smallest code — a canonical total order, not hash-seed
    roulette (same chain as loadout_picker). Tool magnitude is
    ``abs(gather_score)`` — identical to tiers.equip_value.tool_value, imported
    from equipment.scoring to respect the equipment-layer direction.
    """
    if state.bank_items is None:
        return {}
    owned: set[str] = {code for code, qty in state.inventory.items() if qty > 0}
    owned.update(code for code in state.equipment.values() if code)

    fills: dict[str, str] = {}
    for skill in sorted(_GATHERING_SKILLS):
        best_owned = 0
        for code in owned:
            stats = game_data.item_stats(code)
            if stats is not None:
                best_owned = max(best_owned, abs(gather_score(stats, skill)))
        best: tuple[int, str] | None = None
        for code in sorted(state.bank_items):
            if state.bank_items[code] <= 0 or code in reserved:
                continue
            stats = game_data.item_stats(code)
            if stats is None or state.level < stats.level:
                continue
            value = abs(gather_score(stats, skill))
            if value > best_owned and (best is None or value > best[0]):
                best = (value, code)
        if best is not None:
            fills[skill] = best[1]
    return fills

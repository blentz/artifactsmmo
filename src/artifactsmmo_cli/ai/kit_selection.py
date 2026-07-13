"""Which weapon/tools the character is actually WORKING with: the best fighting
weapon and the best gathering tool per skill, over inventory + equipped.

Extracted from `ai/bank_selection.py` (where the deposit keep-set used to live)
so the keep authority can ask the same question without an import cycle:
`bank_selection` now asks `inventory_keep.bankable` how many copies it may bank,
and `inventory_keep`'s COMBAT_WEAPON / WORKING_KIT reasons ask THESE selectors
which single copy is the working one. Both modules import this one; it imports
neither.

These selectors identify a CODE, never a quantity. The quantity is the keep
authority's business — and it is 1, because a character swings one weapon and
mines with one pickaxe. Conflating "this code is the working tool" with "keep
every copy of this code" is exactly the hoard bug this epic exists to kill
(18 `copper_axe` in the bag, all shielded, none banked).
"""

from artifactsmmo_cli.ai.equipment.scoring import gather_score
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import _GATHERING_SKILLS
from artifactsmmo_cli.ai.world_state import WorldState


def best_fighting_weapon(state: WorldState, game_data: GameData) -> str | None:
    """Highest-attack non-tool weapon among inventory + equipped, or None.

    Tools (pickaxe/axe/net) have skill_effects and are excluded — they are
    gathering aids, not the combat weapon to protect."""
    candidates: set[str] = set(state.inventory)
    candidates.update(c for c in state.equipment.values() if c)
    best: tuple[int, str] | None = None
    for code in candidates:
        stats = game_data.item_stats(code)
        if stats is None or stats.type_ != "weapon" or stats.skill_effects:
            continue
        attack = sum(stats.attack.values()) if stats.attack else 0
        # Higher attack wins; tie broken by code ascending (deterministic).
        if best is None or attack > best[0] or (attack == best[0] and code < best[1]):
            best = (attack, code)
    return best[1] if best else None


def best_gathering_tools(state: WorldState, game_data: GameData) -> set[str]:
    """Best owned tool per gathering skill (by ``tool_value``) — the working
    kit. Depositing it undoes the WithdrawTools ferry and re-creates the
    bare-handed grind (trace 2026-07-05: copper_pickaxe banked, 261/300 cycles
    mining with copper_dagger). Outclassed spares stay bankable — and so does
    every SPARE COPY of the kept tool itself, which is the keep authority's job
    (WORKING_KIT keeps 1), not this selector's.

    Tool magnitude is ``abs(gather_score)`` (== tiers.equip_value.tool_value,
    which cannot be imported here: tiers.__init__ -> strategy -> guards ->
    bank_selection cycles)."""
    candidates: set[str] = {c for c, q in state.inventory.items() if q > 0}
    candidates.update(c for c in state.equipment.values() if c)
    tools: set[str] = set()
    for skill in _GATHERING_SKILLS:
        best: tuple[int, str] | None = None
        for code in candidates:
            stats = game_data.item_stats(code)
            value = abs(gather_score(stats, skill)) if stats is not None else 0
            # Bigger reduction wins; tie broken by code ascending (deterministic).
            if value > 0 and (best is None or value > best[0]
                              or (value == best[0] and code < best[1])):
                best = (value, code)
        if best is not None:
            tools.add(best[1])
    return tools

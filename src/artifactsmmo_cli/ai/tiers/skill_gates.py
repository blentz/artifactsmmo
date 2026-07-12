"""Which craft skills currently gate a strategically interesting want.

A skill is "gating" iff it is the craft.skill of some wanted, not-yet-owned item
(gear / tool / active items-task item / combat weapon) — or an item in that item's
craftable recipe closure — at a craft.level above the character's current skill
level. Gather/resource skill gates are EXCLUDED: gather skills generally self-level
through the gathering the bot already does; only craft skills can stall because
nothing in the routine forces a craft. Exception: a gatherable consumable-craft
skill (alchemy) whose FIRST craftable sits above level 1 cannot self-level via
craft-grind — its skill-grind is served by gathering its resource (the LevelSkill
action's gather-to-level fallback), which levels it by gathering.

See docs/superpowers/specs/2026-06-08-levelskill-gating-prioritization-design.md
(LIV-SKILL-1/2/3).
"""

from dataclasses import dataclass
from enum import Enum

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import recipe_closure
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.owned_count import owned_count_pure
from artifactsmmo_cli.ai.world_state import WorldState


class SkillProgressionError(RuntimeError):
    """Raised when a craft skill gates a wanted item but no in-skill item is
    craftable at the current level — a genuine deadlock (LIV-SKILL-2 violation).
    Fail loud rather than silently drop the only candidate that could break it."""


class GateSource(Enum):
    """Why a skill is gating — drives the arbiter's preemption rule. Lower
    enum-rank (see _SOURCE_RANK) is the stronger source."""
    TASK_ITEM = "task_item"
    GEAR = "gear"
    TOOL = "tool"
    COMBAT = "combat"


_SOURCE_RANK = {
    GateSource.TASK_ITEM: 0,
    GateSource.GEAR: 1,
    GateSource.TOOL: 2,
    GateSource.COMBAT: 3,
}


@dataclass(frozen=True)
class SkillGate:
    """The level a wanted item needs in a skill, and why it is wanted."""
    required_level: int
    source: GateSource


def _stronger_source(a: GateSource, b: GateSource) -> GateSource:
    return a if _SOURCE_RANK[a] <= _SOURCE_RANK[b] else b


def gating_skills(
    state: WorldState,
    game_data: GameData,
    objective: CharacterObjective,
    combat_weapon: str | None,
) -> dict[str, SkillGate]:
    """Craft skills blocking a strategically interesting want. skill -> SkillGate.

    `combat_weapon` is the best attainable weapon to chase when the character is
    not combat-capable (else None) — passed in so this module avoids the
    combat/predict_win import cycle."""
    wants: list[tuple[str, GateSource]] = []
    for code in objective.target_gear.values():
        wants.append((code, GateSource.GEAR))
    for code in objective.target_tools.values():
        wants.append((code, GateSource.TOOL))
    if state.task_type == "items" and state.task_code:
        wants.append((state.task_code, GateSource.TASK_ITEM))
    if combat_weapon is not None:
        wants.append((combat_weapon, GateSource.COMBAT))

    equipped = [c for c in state.equipment.values() if c is not None]
    gates: dict[str, SkillGate] = {}
    for code, source in wants:
        if owned_count_pure(state.inventory, state.bank_items, equipped, code) >= 1:
            continue
        _resources, craftables = recipe_closure(game_data, [code])
        for node in set(craftables) | {code}:
            stats = game_data.item_stats(node)
            if stats is None or not stats.crafting_skill:
                continue
            current = state.skills.get(stats.crafting_skill, 0)
            if stats.crafting_level <= current:
                continue
            _record(gates, stats.crafting_skill,
                    SkillGate(stats.crafting_level, source))
    return gates


def _record(gates: dict[str, SkillGate], skill: str, gate: SkillGate) -> None:
    """Keep the highest required_level and the strongest source. Deterministic."""
    existing = gates.get(skill)
    if existing is None:
        gates[skill] = gate
        return
    gates[skill] = SkillGate(
        required_level=max(existing.required_level, gate.required_level),
        source=_stronger_source(existing.source, gate.source),
    )

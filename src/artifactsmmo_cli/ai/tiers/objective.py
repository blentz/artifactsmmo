"""Tier-1 objective: the 'perfect character sheet' target and the gap to it.

Two tightly-coupled frozen models in one file (CharacterObjective produces
ObjectiveGap), following the cycle_snapshot.py GoalRankEntry/GoalAttempt
precedent."""

from dataclasses import dataclass, field
from fractions import Fraction

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.game_data import _GATHERING_SKILLS, GameData
from artifactsmmo_cli.ai.tiers.equip_value import equip_value, tool_value
from artifactsmmo_cli.ai.tiers.objective_completion import is_complete_pure
from artifactsmmo_cli.ai.world_state import EQUIPMENT_SLOTS, SKILL_NAMES, WorldState


def is_attainable(code: str, game_data: GameData, _path: frozenset[str] = frozenset()) -> bool:
    """True when the item is producible in principle (at max progression): its
    craft chain bottoms out in gatherables, with no drop-only/unknown component.
    State-independent — the perfect-sheet target ignores current skills. Cycle-safe."""
    recipe = game_data.crafting_recipe(code)
    if recipe is not None:
        if code in _path:
            return False
        sub_path = _path | {code}
        return all(is_attainable(mat, game_data, sub_path) for mat in recipe)
    return code in game_data.resource_drops.values()


@dataclass(frozen=True)
class ObjectiveGap:
    """Distance from a state to the Tier-1 objective. Positive gaps only;
    fractions normalise unlike units into [0, 1] for personality weighting.

    P4a: gear gaps are exact ints (equip_value deltas); the normalised
    fractions are exact `Fraction` ratios of those integer gaps — no float
    rounding anywhere in the objective gap."""

    char_level_gap: int
    skill_gaps: dict[str, int]
    gear_gaps: dict[str, int]
    char_level_fraction: Fraction
    skills_fraction: Fraction
    gear_fraction: Fraction

    @property
    def is_complete(self) -> bool:
        return is_complete_pure(
            (self.char_level_fraction, self.skills_fraction, self.gear_fraction))


@dataclass(frozen=True)
class CharacterObjective:
    """The maxed character sheet: char level 50, every skill 50, best-value
    item per equipment slot, best tool per gathering skill. Built once from
    game data.

    `target_tools` was added to fix a slow-mining bug: the API encodes tools
    as `type_="weapon"` so they competed with combat weapons in `target_gear`
    by `equip_value` (attack + resistance + hp_restore) and always lost.
    Tools are now picked on a separate `tool_value` axis (per-skill effect
    magnitude), pursued as independent objective roots, and swapped in by
    OptimizeLoadout when the active task needs the matching gathering skill.
    """

    target_char_level: int
    target_skill_levels: dict[str, int]
    target_gear: dict[str, str]  # slot -> best item code
    _game_data: GameData = field(repr=False, compare=False)
    # Defaults to empty for backward compat with constructors that predate
    # the tool axis (legacy tests). Production callers go through
    # from_game_data which populates this. kw_only so it doesn't collide
    # with positional _game_data.
    target_tools: dict[str, str] = field(default_factory=dict, kw_only=True)

    @classmethod
    def from_game_data(cls, game_data: GameData) -> "CharacterObjective":
        target_skill_levels = {s: game_data.max_skill_level for s in SKILL_NAMES}
        by_type: dict[str, list[tuple[int, str]]] = {}
        for code, stats in game_data.all_item_stats.items():
            if stats.type_ not in ITEM_TYPE_TO_SLOTS:
                continue
            by_type.setdefault(stats.type_, []).append((equip_value(stats), code))
        target_gear: dict[str, str] = {}
        for type_, items in by_type.items():
            slots = [s for s in ITEM_TYPE_TO_SLOTS[type_] if s in EQUIPMENT_SLOTS]
            ranked = sorted(items, key=lambda vc: (-vc[0], vc[1]))
            attainable = [(value, code) for (value, code) in ranked
                          if is_attainable(code, game_data)]
            for slot, (_value, code) in zip(slots, attainable, strict=False):
                target_gear[slot] = code
        # Tools: best per gathering skill by tool_value (skill_effects magnitude).
        # Tie-break by item code for determinism. Filter to attainable items.
        target_tools: dict[str, str] = {}
        for skill in _GATHERING_SKILLS:
            scored = [(tool_value(stats, skill), code)
                      for code, stats in game_data.all_item_stats.items()
                      if tool_value(stats, skill) > 0
                      and stats.type_ in ITEM_TYPE_TO_SLOTS
                      and is_attainable(code, game_data)]
            if scored:
                scored.sort(key=lambda vc: (-vc[0], vc[1]))
                target_tools[skill] = scored[0][1]
        return cls(
            target_char_level=game_data.max_character_level,
            target_skill_levels=target_skill_levels,
            target_gear=target_gear,
            target_tools=target_tools,
            _game_data=game_data,
        )

    def _item_value(self, code: str | None) -> int:
        if not code:
            return 0
        stats = self._game_data.item_stats(code)
        return equip_value(stats) if stats is not None else 0

    def gap(self, state: WorldState) -> ObjectiveGap:
        char_level_gap = max(0, self.target_char_level - state.level)
        skill_gaps = {
            skill: max(0, target - state.skills.get(skill, 1))
            for skill, target in self.target_skill_levels.items()
            if max(0, target - state.skills.get(skill, 1)) > 0
        }
        gear_gaps: dict[str, int] = {}
        gear_target_total = 0
        for slot, target_code in self.target_gear.items():
            target_val = self._item_value(target_code)
            gear_target_total += target_val
            deficit = max(0, target_val - self._item_value(state.equipment.get(slot)))
            if deficit > 0:
                gear_gaps[slot] = deficit

        # P4a: exact rational fractions (integer gap / integer denominator).
        char_level_fraction = Fraction(char_level_gap, self.target_char_level)
        skills_denom = len(SKILL_NAMES) * self._game_data.max_skill_level
        skills_fraction = Fraction(sum(skill_gaps.values()), skills_denom)
        gear_fraction = (Fraction(sum(gear_gaps.values()), gear_target_total)
                         if gear_target_total > 0 else Fraction(0))
        return ObjectiveGap(
            char_level_gap=char_level_gap,
            skill_gaps=skill_gaps,
            gear_gaps=gear_gaps,
            char_level_fraction=char_level_fraction,
            skills_fraction=skills_fraction,
            gear_fraction=gear_fraction,
        )

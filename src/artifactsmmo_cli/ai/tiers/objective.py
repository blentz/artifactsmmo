"""Tier-1 objective: the 'perfect character sheet' target and the gap to it.

Two tightly-coupled frozen models in one file (CharacterObjective produces
ObjectiveGap), following the cycle_snapshot.py GoalRankEntry/GoalAttempt
precedent."""

from dataclasses import dataclass, field

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
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
    return code in game_data._resource_drops.values()


@dataclass(frozen=True)
class ObjectiveGap:
    """Distance from a state to the Tier-1 objective. Positive gaps only;
    fractions normalise unlike units into [0, 1] for personality weighting."""

    char_level_gap: int
    skill_gaps: dict[str, int]
    gear_gaps: dict[str, float]
    char_level_fraction: float
    skills_fraction: float
    gear_fraction: float

    @property
    def is_complete(self) -> bool:
        return (self.char_level_fraction == 0.0
                and self.skills_fraction == 0.0
                and self.gear_fraction == 0.0)


@dataclass(frozen=True)
class CharacterObjective:
    """The maxed character sheet: char level 50, every skill 50, best-value
    item per equipment slot. Built once from game data."""

    target_char_level: int
    target_skill_levels: dict[str, int]
    target_gear: dict[str, str]  # slot -> best item code
    _game_data: GameData = field(repr=False, compare=False)

    @classmethod
    def from_game_data(cls, game_data: GameData) -> "CharacterObjective":
        target_skill_levels = {s: game_data.max_skill_level for s in SKILL_NAMES}
        by_type: dict[str, list[tuple[float, str]]] = {}
        for code, stats in game_data._item_stats.items():
            if stats.type_ not in ITEM_TYPE_TO_SLOTS:
                continue
            by_type.setdefault(stats.type_, []).append((equip_value(stats), code))
        target_gear: dict[str, str] = {}
        for type_, items in by_type.items():
            slots = [s for s in ITEM_TYPE_TO_SLOTS[type_] if s in EQUIPMENT_SLOTS]
            ranked = sorted(items, key=lambda vc: (-vc[0], vc[1]))
            attainable = [(value, code) for (value, code) in ranked
                          if is_attainable(code, game_data)]
            for slot, (_value, code) in zip(slots, attainable):
                target_gear[slot] = code
        return cls(
            target_char_level=game_data.max_character_level,
            target_skill_levels=target_skill_levels,
            target_gear=target_gear,
            _game_data=game_data,
        )

    def _item_value(self, code: str | None) -> float:
        if not code:
            return 0.0
        stats = self._game_data.item_stats(code)
        return equip_value(stats) if stats is not None else 0.0

    def gap(self, state: WorldState) -> ObjectiveGap:
        char_level_gap = max(0, self.target_char_level - state.level)
        skill_gaps = {
            skill: max(0, target - state.skills.get(skill, 1))
            for skill, target in self.target_skill_levels.items()
            if max(0, target - state.skills.get(skill, 1)) > 0
        }
        gear_gaps: dict[str, float] = {}
        gear_target_total = 0.0
        for slot, target_code in self.target_gear.items():
            target_val = self._item_value(target_code)
            gear_target_total += target_val
            deficit = max(0.0, target_val - self._item_value(state.equipment.get(slot)))
            if deficit > 0:
                gear_gaps[slot] = deficit

        char_level_fraction = char_level_gap / self.target_char_level
        skills_denom = len(SKILL_NAMES) * self._game_data.max_skill_level
        skills_fraction = sum(skill_gaps.values()) / skills_denom
        gear_fraction = (sum(gear_gaps.values()) / gear_target_total
                         if gear_target_total > 0 else 0.0)
        return ObjectiveGap(
            char_level_gap=char_level_gap,
            skill_gaps=skill_gaps,
            gear_gaps=gear_gaps,
            char_level_fraction=char_level_fraction,
            skills_fraction=skills_fraction,
            gear_fraction=gear_fraction,
        )

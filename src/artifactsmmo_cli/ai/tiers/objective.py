"""Tier-1 objective: the 'perfect character sheet' target and the gap to it.

Two tightly-coupled frozen models in one file (CharacterObjective produces
ObjectiveGap), following the cycle_snapshot.py GoalRankEntry/GoalAttempt
precedent."""

from dataclasses import dataclass, field, replace
from fractions import Fraction

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import _GATHERING_SKILLS, GameData
from artifactsmmo_cli.ai.tiers.equip_value import equip_value, tool_value
from artifactsmmo_cli.ai.tiers.objective_completion import is_complete_pure
from artifactsmmo_cli.ai.tiers.skill_target_curve import skill_target_curve
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


def is_attainable_now(code: str, state: WorldState, game_data: GameData,
                      _path: frozenset[str] = frozenset()) -> bool:
    """State-aware producibility for NEAR-TERM targets: the craft chain
    bottoms out in gatherables OR drops from a winnable monster with a known
    spawn — the same leaf semantics as the strategy tier's `_producible`.

    `is_attainable` is the wrong gate for near-term gear: every armor a
    low-level character can wear crafts from monster drops (copper_armor
    needs wool, copper_legs_armor needs feather, life_amulet needs feather +
    red_slimeball), so the gathering-only closure rejected ALL of them and
    the 2026-06-11 near-term-gear fix was inert (trace 17:21: three empty
    slots, zero armor roots). Drops from monsters the character can't beat
    yet stay excluded — those targets self-unlock as gear/level improve.

    Winnability is judged AT FULL HP: this is a strategic "can the
    character ever farm this" question and rest is always available, so a
    transiently-damaged character must not see its gear targets evaporate
    (predict_win at hp=31/175 fails every monster, which flipped
    chosen_root on every post-fight cycle). Matches the G3 Lean model
    (`winnable_at_max_hp`). Tactical fight entry keeps current-HP
    semantics in predict_win itself. Cycle-safe."""
    recipe = game_data.crafting_recipe(code)
    if recipe is not None:
        if code in _path:
            return False
        sub_path = _path | {code}
        return all(is_attainable_now(mat, state, game_data, sub_path) for mat in recipe)
    if code in game_data.resource_drops.values():
        return True
    rested = replace(state, hp=state.max_hp)
    return any(is_winnable(rested, game_data, monster_code)
               and game_data.monster_locations(monster_code)
               for monster_code, _rate, _mn, _mx in game_data.monsters_dropping(code))


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

    def near_term_gear(self, state: WorldState) -> dict[str, str]:
        """Best usable-NOW upgrade per equipment slot: highest equip_value
        attainable item with `stats.level <= state.level` that strictly beats
        the currently-equipped value (empty slot counts as 0).

        The perfect-sheet `target_gear` is endgame BiS, which at low character
        level is unreachable (drops from unwinnable monsters) and gets filtered
        out of the Tier-2 ranking — leaving NO gear root at all, so the
        kernel-proved empty-slot dominance (Formal.GearPolicy
        `armor_strictly_dominates_empty_slot`) had no candidate to act on.
        Trace 2026-06-11 16:42: level 6, body/leg/amulet slots empty, 148
        consecutive fights at -72.8 HP each. These near-term targets are the
        live roots that premise needs."""
        by_type: dict[str, list[tuple[int, str]]] = {}
        for code, stats in self._game_data.all_item_stats.items():
            if stats.type_ not in ITEM_TYPE_TO_SLOTS or stats.level > state.level:
                continue
            value = equip_value(stats)
            if value > 0:
                by_type.setdefault(stats.type_, []).append((value, code))
        targets: dict[str, str] = {}
        for type_, items in by_type.items():
            slots = [s for s in ITEM_TYPE_TO_SLOTS[type_] if s in EQUIPMENT_SLOTS]
            ranked = sorted(items, key=lambda vc: (-vc[0], vc[1]))
            attainable = [(value, code) for (value, code) in ranked
                          if is_attainable_now(code, state, self._game_data)]
            for slot, (value, code) in zip(slots, attainable, strict=False):
                if value > self._item_value(state.equipment.get(slot)):
                    targets[slot] = code
        return targets

    def near_term_skill_targets(self, state: WorldState) -> dict[str, int]:
        """Recipe-aware skill curve: {craft_skill: target_level} the bot should
        hold at the current char level so gear recipes unlock just-in-time.
        Thin delegation to the proven skill_target_curve core."""
        return skill_target_curve(state.level, state, self._game_data)

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

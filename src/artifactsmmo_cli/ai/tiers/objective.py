"""Tier-1 objective: the 'perfect character sheet' target and the gap to it.

Two tightly-coupled frozen models in one file (CharacterObjective produces
ObjectiveGap), following the cycle_snapshot.py GoalRankEntry/GoalAttempt
precedent."""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from fractions import Fraction

from artifactsmmo_cli.ai.actions.equip import DUPLICATE_SLOT_TYPES, ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import _GATHERING_SKILLS, GameData
from artifactsmmo_cli.ai.potion_supply import bootstrap_potion_target
from artifactsmmo_cli.ai.tiers.equip_value import equip_value, tool_value
from artifactsmmo_cli.ai.tiers.leaf_attainable_core import leaf_attainable_pure
from artifactsmmo_cli.ai.tiers.objective_completion import is_complete_pure
from artifactsmmo_cli.ai.tiers.skill_target_curve import skill_target_curve
from artifactsmmo_cli.ai.world_state import EQUIPMENT_SLOTS, SKILL_NAMES, WorldState


# Single source: the duplicate-allowed slot types, read from actions/equip.py's
# DUPLICATE_SLOT_TYPES — no copy, so this can't drift from that set.
_DUPLICATE_FILL_TYPES = DUPLICATE_SLOT_TYPES
"""Multi-slot equip types whose empty slots are filled by repeating the best
attainable item. See actions/equip.py's DUPLICATE_SLOT_TYPES comment for which
types are in the set and why (rings: confirmed by a live HTTP-200 probe
2026-06-14; artifacts: asserted from the same per-slot equip model, not yet
probed — see that comment's probe trigger). Types outside the set (e.g. utility
consumables) stay distinct, so their remaining slots are left untargeted."""


def _slot_assignments(type_: str, slots: list[str],
                      attainable: list[tuple[int, str]]) -> list[tuple[str, int, str]]:
    """(slot, value, code) for each slot: ranked attainable assigned in order,
    then for rings any remaining slots filled by repeating the best attainable."""
    out: list[tuple[str, int, str]] = []
    for i, slot in enumerate(slots):
        if i < len(attainable):
            value, code = attainable[i]
        elif type_ in _DUPLICATE_FILL_TYPES and attainable:
            value, code = attainable[0]
        else:
            continue
        out.append((slot, value, code))
    return out


GOLD = "gold"
"""The currency code for ordinary (gold) purchases (`NPCItem.currency`).
Distinguished as ALWAYS attainable: the perfect sheet assumes full gold, and
gold is earnable by any fight/sell. A non-gold currency is an item code whose
own attainability must be established by recursion."""


def _attainable_closure(code: str, game_data: GameData,
                        leaf_ok: Callable[[str, frozenset[str]], bool],
                        _path: frozenset[str] = frozenset()) -> bool:
    """Shared cycle-safe producibility walk: an item is attainable iff it has a
    craft recipe whose materials are all attainable, else its `leaf_ok` holds.
    The recipe walk is IDENTICAL for the perfect-sheet (`is_attainable`) and the
    near-term (`is_attainable_now`) gates — they differ ONLY in the leaf rule, so
    the walk lives here once. `leaf_ok` receives the current `_path` so a
    purchase edge can recurse on its currency's attainability under the same
    cycle guard. Mirrors the proved `Formal.Objective.attainAux`, parametric in
    its leaf (`drop`) and purchase (`buys`) relations. Cycle-safe via `_path`."""
    recipe = game_data.crafting_recipe(code)
    if recipe is not None:
        if code in _path:
            return False
        sub_path = _path | {code}
        return all(_attainable_closure(mat, game_data, leaf_ok, sub_path)
                   for mat in recipe)
    return leaf_ok(code, _path)


def _gatherable(code: str, game_data: GameData) -> bool:
    """A raw resource-drop leaf (`code in resource_drops.values()`)."""
    return code in game_data.resource_drops.values()


def _drops_from_spawning_monster(code: str, game_data: GameData) -> bool:
    """Some monster with a KNOWN spawn (static overworld or active event, bosses
    included) drops `code`. State-INDEPENDENT: the perfect sheet assumes full
    progression, at which any spawning monster is farmable, so its drops count
    as producible regardless of current combat strength."""
    return any(game_data.monster_locations(monster_code)
               for monster_code, _rate, _mn, _mx in game_data.monsters_dropping(code))


def _permanent_vendor_purchases(code: str, game_data: GameData) -> list[tuple[int, str]]:
    """(price, currency) for each PERMANENT, reachable NPC vendor that sells
    `code`. Event vendors (timed spawn) and unlocated NPCs are excluded: a
    perfect-sheet acquisition source must be reliably reachable, not a window
    that may be closed. Mirrors the `EventWindow` gating used for event
    merchants."""
    return [(price, currency)
            for npc, price, currency in game_data.npc_purchases(code)
            if not game_data.is_event_npc(npc) and game_data.npc_location(npc) is not None]


def is_attainable(code: str, game_data: GameData) -> bool:
    """True when the item is producible AT MAX PROGRESSION: its craft chain
    bottoms out in leaves that are gatherable raws, drops from a known-spawn
    monster (bosses included), OR PURCHASABLE from a permanent vendor for an
    attainable currency. State-independent — the perfect-sheet target ignores
    current skills, combat strength, and gold.

    Previously GATHERING-ONLY (dropped monster-drop armor — body/leg/amulet),
    then gather-or-monster-drop (task #11). The purchase edge (task #12) adds the
    rune/artifact/bag slots, whose items are NPC-only: an item with no recipe is
    attainable if a permanent vendor sells it for `gold` (always attainable) or
    for a currency item that is itself attainable (recursion, cycle-guarded via
    the closure path — e.g. a rune bought with sandwhisper_coin which is itself
    earned/dropped)."""
    def leaf_ok(leaf: str, path: frozenset[str]) -> bool:
        # Cycle guard for the recursive buyable path only — gatherable/drop/task-earnable
        # don't recurse so they're not subject to the path check.
        buyable = leaf not in path and any(
            currency == GOLD
            or _attainable_closure(currency, game_data, leaf_ok, path | {leaf})
            for _price, currency in _permanent_vendor_purchases(leaf, game_data))
        return leaf_attainable_pure(
            _gatherable(leaf, game_data),
            _drops_from_spawning_monster(leaf, game_data),
            game_data.is_task_earnable(leaf),
            buyable)

    return _attainable_closure(code, game_data, leaf_ok)


def is_attainable_now(code: str, state: WorldState, game_data: GameData) -> bool:
    """State-aware producibility for NEAR-TERM targets: the same recipe walk as
    `is_attainable`, but the leaf is gatherable OR a drop from a monster that is
    winnable NOW (judged at full HP) with a known spawn OR PURCHASABLE-NOW from a
    permanent vendor (affordable: gold price ≤ current gold, or a non-gold
    currency that is itself attainable-now). The leaf semantics of the strategy
    tier's `_producible`, plus affordability.

    `is_attainable` is the wrong gate for near-term gear at LOW level: every
    armor a low-level character can wear crafts from monster drops, and a
    low-level character can't yet beat the monsters dropping the BiS materials,
    nor afford a 20000-gold rune. Targets that need more gold/level self-unlock.

    Winnability is judged AT FULL HP: this is a strategic "can the character ever
    farm this" question and rest is always available, so a transiently-damaged
    character must not see its gear targets evaporate (predict_win at hp=31/175
    fails every monster, which flipped chosen_root on every post-fight cycle).
    Matches the G3 Lean model (`winnable_at_max_hp`). Tactical fight entry keeps
    current-HP semantics in predict_win itself.

    AFFORDABILITY is conservative for v1: a gold purchase needs `state.gold ≥
    price`; a non-gold (item) currency only needs the currency item attainable-
    now (quantity is not yet modeled — an over-approximation on quantity, refined
    when a buy goal lands)."""
    rested = replace(state, hp=state.max_hp)

    def leaf_ok(leaf: str, path: frozenset[str]) -> bool:
        if _gatherable(leaf, game_data):
            return True
        if any(is_winnable(rested, game_data, monster_code)
               and game_data.monster_locations(monster_code)
               for monster_code, _rate, _mn, _mx in game_data.monsters_dropping(leaf)):
            return True
        if leaf in path:
            return False
        sub = path | {leaf}
        for price, currency in _permanent_vendor_purchases(leaf, game_data):
            if currency == GOLD:
                if state.gold >= price:
                    return True
            elif _attainable_closure(currency, game_data, leaf_ok, sub):
                return True
        return False

    return _attainable_closure(code, game_data, leaf_ok)


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
    by `equip_value` (the unified 8-stat ``combat_raw`` ruler) and always lost.
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
            if stats.type_ not in ITEM_TYPE_TO_SLOTS or stats.type_ == "utility":
                continue
            by_type.setdefault(stats.type_, []).append((equip_value(stats), code))
        target_gear: dict[str, str] = {}
        for type_, items in by_type.items():
            slots = [s for s in ITEM_TYPE_TO_SLOTS[type_] if s in EQUIPMENT_SLOTS]
            ranked = sorted(items, key=lambda vc: (-vc[0], vc[1]))
            attainable = [(value, code) for (value, code) in ranked
                          if is_attainable(code, game_data)]
            for slot, _value, code in _slot_assignments(type_, slots, attainable):
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
            if (stats.type_ not in ITEM_TYPE_TO_SLOTS
                    or stats.type_ == "utility"
                    or stats.level > state.level):
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
            for slot, value, code in _slot_assignments(type_, slots, attainable):
                if value > self._item_value(state.equipment.get(slot)):
                    targets[slot] = code
        return targets

    def utility_potion_targets(self, state: WorldState) -> dict[str, str]:
        """The utility-slot heal to pursue, judged by EFFECT not level (potions
        are level-exempt). Delegates to bootstrap_potion_target — the effect-best
        potion craftable now, or the cheapest-to-unlock when none is craftable
        yet. Replaces the level-based best-in-slot utility roots that armor
        enumeration (target_gear / near_term_gear) used to emit."""
        code = bootstrap_potion_target(state, self._game_data)
        return {"utility1_slot": code} if code is not None else {}

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

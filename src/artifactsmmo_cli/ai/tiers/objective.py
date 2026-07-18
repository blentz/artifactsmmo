"""Tier-1 objective: the 'perfect character sheet' target and the gap to it.

Two tightly-coupled frozen models in one file (CharacterObjective produces
ObjectiveGap), following the cycle_snapshot.py GoalRankEntry/GoalAttempt
precedent."""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from fractions import Fraction

from artifactsmmo_cli.ai.actions.equip import DUPLICATE_SLOT_TYPES, ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import _GATHERING_SKILLS
from artifactsmmo_cli.ai.potion_supply import bootstrap_potion_target, target_potion_pure
from artifactsmmo_cli.ai.tiers.equip_value import equip_value, tool_value
from artifactsmmo_cli.ai.tiers.leaf_attainable_core import leaf_attainable_pure
from artifactsmmo_cli.ai.tiers.objective_completion import is_complete_pure
from artifactsmmo_cli.ai.tiers.pursuit_value import pursuit_value
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
    EXCEPT for duplicate-allowed types (rings, artifacts — DUPLICATE_SLOT_TYPES),
    where every slot targets the single BEST attainable item.

    GAP-2-review Task 2 (2026-07-08): `attainable` is already sorted
    descending by value, so for a dup-allowed type a 2nd copy of the
    top-ranked item is NEVER worse than any lower-ranked DISTINCT item —
    duplicating rank-0 strictly dominates assigning rank-1, rank-2, ...
    per slot (additive equip_value, no diminishing returns modeled). The
    previous "ranked-distinct-then-duplicate-when-exhausted" rule could
    hand a duplicate-allowed slot a far weaker distinct item (e.g. a
    value-17 2nd-ranked artifact) when duplicating the value-201 best was
    strictly better. Ownership/acquisition caps are NOT enforced here —
    this is the aspirational target-setting layer; the ownership cap lives
    downstream in `equipment/scoring.py`'s `pick_loadout` (dual-ring
    carve-out), which already caps a duplicate fill at physical ownership."""
    if not attainable:
        return []
    if type_ in _DUPLICATE_FILL_TYPES:
        value, code = attainable[0]
        return [(slot, value, code) for slot in slots]
    out: list[tuple[str, int, str]] = []
    for i, slot in enumerate(slots):
        if i < len(attainable):
            out.append((slot, attainable[i][0], attainable[i][1]))
    return out


GOLD = "gold"
"""The currency code for ordinary (gold) purchases (`NPCItem.currency`).
Distinguished as ALWAYS attainable: the perfect sheet assumes full gold, and
gold is earnable by any fight/sell. A non-gold currency is an item code whose
own attainability must be established by recursion."""


def _attainable_closure(code: str, game_data: GameData,
                        leaf_ok: Callable[[str, frozenset[str]], bool],
                        _path: frozenset[str] = frozenset(),
                        stock_ok: Callable[[str], bool] | None = None) -> bool:
    """Shared cycle-safe producibility walk: an item is attainable iff it has a
    craft recipe whose materials are all attainable, else its `leaf_ok` holds.
    The recipe walk is IDENTICAL for the perfect-sheet (`is_attainable`) and the
    near-term (`is_attainable_now`) gates — they differ ONLY in the leaf rule, so
    the walk lives here once. `leaf_ok` receives the current `_path` so a
    purchase edge can recurse on its currency's attainability under the same
    cycle guard. Mirrors the proved `Formal.Objective.attainAux`, parametric in
    its leaf (`drop`) and purchase (`buys`) relations. Cycle-safe via `_path`.

    `stock_ok` (GAP-1, 2026-07-07) is an OPTIONAL held/banked-stock
    short-circuit, checked BEFORE the recipe test at every node — a node
    already in hand needs no acquisition path at all, whether it is a leaf
    (raw material) or a recipe node (the crafted item itself: a banked
    satchel makes satchel attainable-now without walking its recipe). `None`
    for `is_attainable` (the state-independent perfect-sheet gate has no
    stock to consult)."""
    if stock_ok is not None and stock_ok(code):
        return True
    recipe = game_data.crafting_recipe(code)
    if recipe is not None:
        if code in _path:
            return False
        sub_path = _path | {code}
        return all(_attainable_closure(mat, game_data, leaf_ok, sub_path, stock_ok)
                   for mat in recipe)
    return leaf_ok(code, _path)


def _gatherable(code: str, game_data: GameData) -> bool:
    """A raw resource-drop leaf: any item a gatherable resource can drop.

    GAP-2 (2026-07-07): previously consulted only the PRIMARY drop map
    (`resource_drops`, one drop code per resource — the rate-best entry),
    which understates real gatherability: rare secondary drops (gem stones
    off ordinary rocks, `small_pearls` off fishing spots) are invisible to
    it even though they are genuine, if infrequent, gathering yields.
    `gatherable_drop_items()` is the FULL drop set (grown for exactly this
    reason — see its docstring). Attainability is a reachability question
    ("is there a real acquisition source at all"), not a rate judgment —
    filter-at-use-time stays downstream (planning/cost layers weigh rate,
    this gate only asks yes/no)."""
    return code in game_data.gatherable_drop_items()


def _drops_from_spawning_monster(code: str, game_data: GameData) -> bool:
    """Some monster with a KNOWN spawn (static overworld or active event, bosses
    included) drops `code`. State-INDEPENDENT: the perfect sheet assumes full
    progression, at which any spawning monster is farmable, so its drops count
    as producible regardless of current combat strength."""
    return any(game_data.monster_spawn_known(monster_code)
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
    when a buy goal lands).

    HELD/BANKED STOCK (GAP-1, 2026-07-07): before any acquisition-source
    check, a node already held (inventory or bank, either alone > 0) is
    attainable-now outright — mirrors the strategy tier's `_producible`
    held-stock arm (b6328a3a, "already IN HAND: nothing left to produce").
    Without this the walk only ever asked "can I produce MORE right now",
    so a fully-banked recipe leaf whose only acquisition source is
    currently closed (e.g. cowhide when cow is unwinnable) read as
    unattainable despite the bank already holding the full recipe demand —
    and a banked CRAFTED item (a satchel bought/found a cycle ago) still
    walked its own recipe instead of short-circuiting. `state.bank_items is
    None` means UNKNOWN, not zero — `bank_items or {}` naturally treats
    that as no credit, same as `_producible`. Boolean only: partial stock
    (holding 1 of a 5-needed material) still credits attainable — quantity
    accounting stays the planner's job, not this gate's."""
    rested = replace(state, hp=state.max_hp)
    bank = state.bank_items or {}

    def stock_ok(node: str) -> bool:
        return state.inventory.get(node, 0) > 0 or bank.get(node, 0) > 0

    def leaf_ok(leaf: str, path: frozenset[str]) -> bool:
        if _gatherable(leaf, game_data):
            return True
        if any(is_winnable(rested, game_data, monster_code)
               and game_data.monster_spawn_known(monster_code)
               for monster_code, _rate, _mn, _mx in game_data.monsters_dropping(leaf)):
            return True
        if game_data.is_task_earnable(leaf):
            # Task-earned currency (tasks_coin) is producible-NOW: the C4
            # funding loop (accept → fight → complete, activated 2026-07-06)
            # is always available and ReachCurrencyGoal plans it from any
            # state. Without this arm a tasks_coin-priced leaf (jasper_crystal
            # @ tasks_trader) failed the now-walk and satchel silently never
            # became a near-term bag target. Mirrors the full-progression
            # leaf's is_task_earnable arm.
            return True
        if leaf in path:
            return False
        sub = path | {leaf}
        for price, currency in _permanent_vendor_purchases(leaf, game_data):
            if currency == GOLD:
                if state.gold >= price:
                    return True
            elif _attainable_closure(currency, game_data, leaf_ok, sub, stock_ok):
                return True
        return False

    return _attainable_closure(code, game_data, leaf_ok, stock_ok=stock_ok)


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
        """Best usable-NOW upgrade per equipment slot: highest pursuit_value
        attainable item with `stats.level <= state.level` that strictly beats
        the currently-equipped value (empty slot counts as 0).

        Scored on `pursuit_value` (combat-dominant efficiency budget), the same
        ruler `_structural_candidates` ranks gain on, so the per-slot pick and
        the cross-slot gain agree. Within a single slot this only re-orders
        efficiency-bearing utility slots (combat slots already pick the same
        best-combat item); `target_gear`/`from_game_data` (the endgame BiS
        sheet) deliberately stays on flat `equip_value`.

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
            value = pursuit_value(stats)
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
        """The utility-slot heal(s) to pursue, judged by EFFECT not level
        (potions are level-exempt). utility1_slot delegates to
        bootstrap_potion_target — the effect-best potion craftable now, or
        the cheapest-to-unlock when none is craftable yet. utility2_slot gets
        the catalog's SECOND-best heal, via a plain `target_potion_pure`
        craftable-now search excluding slot 1's code (deliberately NOT
        `bootstrap_potion_target` — falling through to that function's
        cheapest-to-unlock branch a second time would manufacture an
        aspirational grind target for slot 2 whenever no other heal is
        craftable right now; see bootstrap_potion_target's docstring). Empty
        slot 2 (no target) is the correct, honest answer when the catalog
        offers only one heal the character can craft today. Utility is NOT
        in DUPLICATE_SLOT_TYPES (see actions/equip.py — the server rejects
        re-equipping a code already worn in a sibling slot), so the two
        utility slots can never legally target the same code. Emission order
        is deterministic (utility1 first, then utility2) and is independent
        of current equipment/stock — `_utility_candidates` is the layer that
        skips a slot whose OWN quantity is already stocked. Replaces the
        level-based best-in-slot utility roots that armor enumeration
        (target_gear / near_term_gear) used to emit."""
        targets: dict[str, str] = {}
        primary = bootstrap_potion_target(state, self._game_data)
        if primary is None:
            return targets
        targets["utility1_slot"] = primary
        secondary = target_potion_pure(state, self._game_data, exclude=primary)
        if secondary is not None:
            targets["utility2_slot"] = secondary
        return targets

    def _item_value(self, code: str | None) -> int:
        """Pursuit-path value of an equipped/target item code (0 when empty).

        On `pursuit_value` (combat-dominant), matching `near_term_gear` and
        `_structural_candidates` so the current-equipped baseline is on the same
        ruler as the candidates. Also consumed by `gap()` for the gear-progress
        fraction: that fraction is now measured in combat-dominant units too,
        which is the correct axis for "how much gear progress remains" (a
        prospecting artifact should not read as near-complete gear) — a ratio,
        so the scale change cancels and objective-completion thresholds hold
        (verified by test_tiers_objective_completion)."""
        if not code:
            return 0
        stats = self._game_data.item_stats(code)
        return pursuit_value(stats) if stats is not None else 0

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

# Goal Tiers P1 — Tier-1 Objective, Gap, Personality Seam — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Pure, no-behavior-change foundation; tasks build on each other in order.

**Goal:** Ship a pure, fully-tested `ai/tiers/` package representing the Tier-1 "perfect character" objective, the gap from the current state, and the personality-weighting seam — consumed by nothing yet (no behavior change).

**Architecture:** `equip_value` (shared item-value fn, extracted from the goal) → `CharacterObjective.from_game_data` (targets: char level 50, each skill 50, best-value item per slot) → `objective.gap(state)` → `ObjectiveGap` (positive gaps + normalized fractions + is_complete) → `weighted_remaining(gap, personality)` over a `Personality` protocol (`BalancedPersonality` default).

**Tech Stack:** Python 3.13, uv, pytest.

---

## File Structure
- Create `src/artifactsmmo_cli/ai/tiers/__init__.py` — public re-exports.
- Create `src/artifactsmmo_cli/ai/tiers/equip_value.py` — `equip_value(stats)`.
- Create `src/artifactsmmo_cli/ai/tiers/objective.py` — `CharacterObjective` + `ObjectiveGap`.
- Create `src/artifactsmmo_cli/ai/tiers/personality.py` — `Personality`, `BalancedPersonality`, `weighted_remaining`.
- Modify `src/artifactsmmo_cli/ai/game_data.py` — `MAX_SKILL_LEVEL` + `max_skill_level`.
- Modify `src/artifactsmmo_cli/ai/goals/progression.py` — `_upgrade_value` delegates to `equip_value`.
- Tests: `tests/test_ai/test_tiers_equip_value.py`, `test_tiers_objective.py`, `test_tiers_personality.py`.

---

## Task 1: `equip_value` shared fn (extract from the goal)

**Files:** Create `src/artifactsmmo_cli/ai/tiers/equip_value.py`; modify `goals/progression.py`; Test `tests/test_ai/test_tiers_equip_value.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ai/test_tiers_equip_value.py`:

```python
from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.tiers.equip_value import equip_value


def test_sums_attack_resistance_hp_restore():
    s = ItemStats(code="x", level=1, type_="weapon",
                  attack={"fire": 10, "air": 2}, resistance={"earth": 3}, hp_restore=5)
    assert equip_value(s) == 20.0


def test_zero_when_no_stats():
    assert equip_value(ItemStats(code="x", level=1, type_="resource")) == 0.0
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_ai/test_tiers_equip_value.py -q`
Expected: FAIL — module `artifactsmmo_cli.ai.tiers.equip_value` missing.

- [ ] **Step 3: Implement**

Create `src/artifactsmmo_cli/ai/tiers/__init__.py` (empty for now) and
`src/artifactsmmo_cli/ai/tiers/equip_value.py`:

```python
"""Shared equippable-item value: total attack + resistance + hp restore."""

from artifactsmmo_cli.ai.game_data import ItemStats


def equip_value(stats: ItemStats) -> float:
    """Crude combat/utility value of an equippable — ranks gear so genuinely
    better items beat alphabetical accidents. Single source shared by the
    UpgradeEquipment goal and the Tier-1 objective."""
    attack = sum(stats.attack.values()) if stats.attack else 0
    resistance = sum(stats.resistance.values()) if stats.resistance else 0
    return float(attack + resistance + stats.hp_restore)
```

- [ ] **Step 4: Delegate the goal's method**

In `src/artifactsmmo_cli/ai/goals/progression.py`, add the import at top:

```python
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
```

Replace the `_upgrade_value` body (keep the method + its docstring) with:

```python
    def _upgrade_value(self, stats: ItemStats) -> float:
        """Crude combat/utility value of an equippable: total attack +
        resistance + hp restore. Delegates to the shared tiers.equip_value."""
        return equip_value(stats)
```

- [ ] **Step 5: Run, confirm PASS (incl. unchanged goal behavior)**

Run: `uv run pytest tests/test_ai/test_tiers_equip_value.py tests/test_ai/test_goals.py -q`
Expected: PASS — new tests pass; existing UpgradeEquipment tests still pass (behavior identical).

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/__init__.py src/artifactsmmo_cli/ai/tiers/equip_value.py src/artifactsmmo_cli/ai/goals/progression.py tests/test_ai/test_tiers_equip_value.py
git commit -m "refactor(ai): extract equip_value; goal delegates to it"
```

---

## Task 2: `GameData.MAX_SKILL_LEVEL`

**Files:** Modify `src/artifactsmmo_cli/ai/game_data.py`; Test `tests/test_ai/test_game_data.py`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ai/test_game_data.py`:

```python
def test_max_skill_level_is_documented_50():
    """Verified: https://docs.artifactsmmo.com/concepts/skills —
    '8 skills that can gain XP and reach up to level 50'."""
    assert GameData().max_skill_level == 50
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_ai/test_game_data.py -k max_skill_level -q`
Expected: FAIL — `GameData` has no `max_skill_level`.

- [ ] **Step 3: Implement**

In `src/artifactsmmo_cli/ai/game_data.py`, after the `max_character_level`
property add:

```python
    MAX_SKILL_LEVEL = 50
    """Documented skill level cap.
    Source: https://docs.artifactsmmo.com/concepts/skills —
    "Your characters have 8 skills that can gain XP and reach up to level 50."
    Equals the character-level cap.
    """

    @property
    def max_skill_level(self) -> int:
        """Documented per-skill level cap. Constant from official docs."""
        return self.MAX_SKILL_LEVEL
```

- [ ] **Step 4: Run, confirm PASS**

Run: `uv run pytest tests/test_ai/test_game_data.py -k max_skill_level -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/game_data.py tests/test_ai/test_game_data.py
git commit -m "feat(ai): document MAX_SKILL_LEVEL=50 (verified from docs)"
```

---

## Task 3: `CharacterObjective` + `ObjectiveGap`

**Files:** Create `src/artifactsmmo_cli/ai/tiers/objective.py`; Test `tests/test_ai/test_tiers_objective.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_tiers_objective.py`:

```python
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import SKILL_NAMES
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon", attack={"air": 4}),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon", attack={"fire": 30}),
        "copper_ring": ItemStats(code="copper_ring", level=1, type_="ring", attack={"fire": 2}),
        "gold_ring": ItemStats(code="gold_ring", level=20, type_="ring", attack={"fire": 8}),
        "ruby_ring": ItemStats(code="ruby_ring", level=30, type_="ring", attack={"fire": 6}),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),  # not equippable
    }
    return gd


def test_target_char_and_skill_levels():
    obj = CharacterObjective.from_game_data(_gd())
    assert obj.target_char_level == 50
    assert obj.target_skill_levels == {s: 50 for s in SKILL_NAMES}


def test_best_gear_per_slot():
    obj = CharacterObjective.from_game_data(_gd())
    assert obj.target_gear["weapon_slot"] == "iron_sword"  # higher attack wins
    assert "copper_ore" not in obj.target_gear.values()    # resources excluded


def test_paired_ring_slots_get_top_two_distinct():
    obj = CharacterObjective.from_game_data(_gd())
    # gold_ring(8) > ruby_ring(6) > copper_ring(2): top-2 fill ring1/ring2.
    assert obj.target_gear["ring1_slot"] == "gold_ring"
    assert obj.target_gear["ring2_slot"] == "ruby_ring"


def test_slot_with_no_candidate_is_omitted():
    gd = GameData()
    gd._item_stats = {"only_weapon": ItemStats(code="only_weapon", level=1, type_="weapon", attack={"f": 1})}
    obj = CharacterObjective.from_game_data(gd)
    assert "weapon_slot" in obj.target_gear
    assert "boots_slot" not in obj.target_gear


def test_gap_positive_only_and_complete_state():
    obj = CharacterObjective.from_game_data(_gd())
    # Maxed level + skills, best gear equipped → complete.
    maxed = make_state(
        level=50, skills={s: 50 for s in SKILL_NAMES},
        equipment={"weapon_slot": "iron_sword", "ring1_slot": "gold_ring", "ring2_slot": "ruby_ring"},
    )
    g = obj.gap(maxed)
    assert g.char_level_gap == 0
    assert g.skill_gaps == {}
    # weapon + both rings satisfied; remaining targeted slots are empty → those
    # gaps are positive, so gap is not complete unless _gd only targets these.
    assert g.char_level_fraction == 0.0
    assert g.skills_fraction == 0.0


def test_gap_measures_level_and_skill_and_gear_deficit():
    obj = CharacterObjective.from_game_data(_gd())
    state = make_state(level=10, skills={"mining": 5}, equipment={"weapon_slot": "wooden_stick"})
    g = obj.gap(state)
    assert g.char_level_gap == 40
    assert g.skill_gaps["mining"] == 45
    assert g.skill_gaps["woodcutting"] == 49  # default level 1 → gap 49
    # weapon target iron_sword(30) vs equipped wooden_stick(4) → gap 26.
    assert g.gear_gaps["weapon_slot"] == 26.0
    assert 0.0 < g.char_level_fraction <= 1.0
    assert 0.0 < g.gear_fraction <= 1.0


def test_empty_slot_scores_full_target_value():
    obj = CharacterObjective.from_game_data(_gd())
    state = make_state(level=50, skills={s: 50 for s in SKILL_NAMES}, equipment={})
    g = obj.gap(state)
    assert g.gear_gaps["weapon_slot"] == 30.0  # full iron_sword value


def test_gear_fraction_zero_when_no_gear_targeted():
    gd = GameData()  # no items → no target gear
    obj = CharacterObjective.from_game_data(gd)
    g = obj.gap(make_state(level=50, skills={s: 50 for s in SKILL_NAMES}))
    assert g.gear_fraction == 0.0
    assert g.is_complete is True
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_ai/test_tiers_objective.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

Create `src/artifactsmmo_cli/ai/tiers/objective.py`:

```python
"""Tier-1 objective: the 'perfect character sheet' target and the gap to it.

Two tightly-coupled frozen models in one file (CharacterObjective produces
ObjectiveGap), following the cycle_snapshot.py GoalRankEntry/GoalAttempt
precedent."""

from dataclasses import dataclass, field

from artifactsmmo_cli.ai.actions.equipment import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.world_state import EQUIPMENT_SLOTS, SKILL_NAMES, WorldState


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
            for slot, (_value, code) in zip(slots, ranked):
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
```

- [ ] **Step 4: Run, confirm PASS**

Run: `uv run pytest tests/test_ai/test_tiers_objective.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/objective.py tests/test_ai/test_tiers_objective.py
git commit -m "feat(ai): Tier-1 CharacterObjective + ObjectiveGap (pure)"
```

---

## Task 4: `Personality` seam + `weighted_remaining`

**Files:** Create `src/artifactsmmo_cli/ai/tiers/personality.py`; Test `tests/test_ai/test_tiers_personality.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_tiers_personality.py`:

```python
from artifactsmmo_cli.ai.tiers.objective import ObjectiveGap
from artifactsmmo_cli.ai.tiers.personality import BalancedPersonality, weighted_remaining


def _gap(cl=0.0, sk=0.0, gr=0.0) -> ObjectiveGap:
    return ObjectiveGap(char_level_gap=0, skill_gaps={}, gear_gaps={},
                        char_level_fraction=cl, skills_fraction=sk, gear_fraction=gr)


def test_balanced_weights_all_one():
    p = BalancedPersonality()
    for c in ("char_level", "skills", "gear"):
        assert p.category_weight(c) == 1.0


def test_balanced_unknown_category_is_one():
    assert BalancedPersonality().category_weight("mystery") == 1.0


def test_weighted_remaining_zero_when_complete():
    assert weighted_remaining(_gap(), BalancedPersonality()) == 0.0


def test_weighted_remaining_sums_fractions_under_balanced():
    g = _gap(cl=0.2, sk=0.5, gr=0.1)
    assert weighted_remaining(g, BalancedPersonality()) == 0.8


def test_weighted_remaining_grows_with_gaps():
    p = BalancedPersonality()
    assert weighted_remaining(_gap(cl=0.1), p) < weighted_remaining(_gap(cl=0.9), p)
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_ai/test_tiers_personality.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

Create `src/artifactsmmo_cli/ai/tiers/personality.py`:

```python
"""Personality seam: how an AI player weights the Tier-1 gap categories.

P1 ships only BalancedPersonality (uniform weights). P5 adds skill-first /
level-first / aligned variants by returning non-uniform category weights."""

from typing import Protocol

from artifactsmmo_cli.ai.tiers.objective import ObjectiveGap

CATEGORIES = ("char_level", "skills", "gear")


class Personality(Protocol):
    """Weights the three Tier-1 gap categories. Higher = pursue harder."""

    def category_weight(self, category: str) -> float: ...


class BalancedPersonality:
    """Weights every gap category equally — the default 'well-rounded' player."""

    def category_weight(self, category: str) -> float:
        return 1.0


def weighted_remaining(gap: ObjectiveGap, personality: Personality) -> float:
    """Single scalar of remaining work (0 when the objective is complete),
    summing each category's normalised fraction times its personality weight.
    P3's frontier search ranks candidate subgoals by how much they reduce this."""
    return (
        personality.category_weight("char_level") * gap.char_level_fraction
        + personality.category_weight("skills") * gap.skills_fraction
        + personality.category_weight("gear") * gap.gear_fraction
    )
```

- [ ] **Step 4: Run, confirm PASS**

Run: `uv run pytest tests/test_ai/test_tiers_personality.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/personality.py tests/test_ai/test_tiers_personality.py
git commit -m "feat(ai): Personality seam + weighted_remaining (Balanced default)"
```

---

## Task 5: Public exports + full verification

**Files:** Modify `src/artifactsmmo_cli/ai/tiers/__init__.py`.

- [ ] **Step 1: Re-export public names**

Replace `src/artifactsmmo_cli/ai/tiers/__init__.py` with:

```python
"""Tiered goal architecture (P1: Tier-1 objective + gap + personality seam)."""

from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective, ObjectiveGap
from artifactsmmo_cli.ai.tiers.personality import (
    BalancedPersonality,
    Personality,
    weighted_remaining,
)

__all__ = [
    "equip_value",
    "CharacterObjective",
    "ObjectiveGap",
    "Personality",
    "BalancedPersonality",
    "weighted_remaining",
]
```

- [ ] **Step 2: Full verification**

Run: `uv run pytest -q` → all pass, 0 skipped.
Run: `uv run pytest tests/test_ai -q --cov=artifactsmmo_cli.ai.tiers --cov-report=term-missing`
→ `tiers/*` 100% (add a test for any missed branch).
Run: `uv run ruff check src/artifactsmmo_cli/ai/tiers tests/test_ai/test_tiers_*.py src/artifactsmmo_cli/ai/game_data.py src/artifactsmmo_cli/ai/goals/progression.py` → clean.
Run: `uv run mypy src/artifactsmmo_cli/ai/tiers` → no errors.

- [ ] **Step 3: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/__init__.py
git commit -m "feat(ai): export tiers P1 public API"
```

---

## Self-review notes
- **Spec coverage:** equip_value extraction (T1), MAX_SKILL_LEVEL (T2),
  CharacterObjective targets + best-gear/paired-slots/omitted-slot (T3),
  ObjectiveGap positive-gaps + fractions + is_complete + empty-slot (T3),
  Personality protocol + Balanced + weighted_remaining (T4), exports (T5). All mapped.
- **No behavior change:** only `_upgrade_value` delegates (identical formula);
  nothing imports the tiers package into the player loop.
- **Type consistency:** `equip_value(ItemStats) -> float` used in goal, objective.
  `CharacterObjective.from_game_data(GameData)`, `.gap(WorldState) -> ObjectiveGap`,
  `weighted_remaining(ObjectiveGap, Personality) -> float` consistent across tasks.
- `_game_data` field uses `compare=False, repr=False` so the frozen dataclass
  stays hashable/comparable on its target fields only.

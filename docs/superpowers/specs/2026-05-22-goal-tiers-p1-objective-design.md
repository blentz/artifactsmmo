# Goal Tiers — P1: Tier-1 Objective, Gap, and Personality Seam

Date: 2026-05-22
Status: Approved (design)

Part of the multi-phase goal-architecture redesign:
- **P1 (this spec)** — Tier-1 objective + gap + personality seam. Pure, **no behavior change**.
- P2 — Tier-2 meta-goal dependency graph.
- P3 — Tier-3 strategic frontier search; behavior switches here.
- P4 — Tier-4 tactical policies.
- P5 — personality variants.

## Goal

Establish the foundation of the tiered architecture: a data-derived
representation of the "perfect character sheet" (Tier 1), the gap from the
current state to it, and the seam where future AI personalities weight that
gap. P1 ships a pure, fully-tested module that **nothing consumes yet** — it
introduces no behavior change. Later phases build the meta-goal graph (P2) and
the frontier search that turns the gap into action (P3).

## Current state

Decisions are made by a flat list of ~20 `Goal` objects, each returning a
hand-tuned `priority()` scalar from `priorities.py`; `GamePlayer._select_goal`
picks the max with sticky commitment, and the GOAP planner plans actions for
the chosen goal. There is no representation of an overall objective or of
"distance to done". `GameData` exposes `max_character_level` (documented
constant `MAX_CHARACTER_LEVEL = 50`), `SKILL_NAMES` (8 skills) and
`EQUIPMENT_SLOTS` (12 slots) live in `world_state.py`, `ITEM_TYPE_TO_SLOTS`
(item type → slot list) in `actions/equipment.py`, and an item's combat/utility
value is computed by `UpgradeEquipmentGoal._upgrade_value`
(`attack + resistance + hp_restore`).

## Design

### Module layout — new package `src/artifactsmmo_cli/ai/tiers/`
- `equip_value.py` — pure `equip_value(stats: ItemStats) -> float`.
- `objective.py` — `CharacterObjective` and `ObjectiveGap` (two tightly-coupled
  models in one file, following the `cycle_snapshot.py` `GoalRankEntry`/
  `GoalAttempt` precedent).
- `personality.py` — `Personality` protocol and `BalancedPersonality` default
  (protocol + its default impl, tightly coupled — same precedent).
- `__init__.py` — re-export the public names.

### `equip_value(stats) -> float`
Extract the exact body of `UpgradeEquipmentGoal._upgrade_value` into a module
function so the objective and the goal share one definition (DRY). Change
`_upgrade_value` to delegate: `return equip_value(stats)` — behavior-identical,
so no test changes beyond import. Formula unchanged:
`sum(attack.values()) + sum(resistance.values()) + hp_restore`.

### `GameData.MAX_SKILL_LEVEL`
Add a documented constant mirroring `MAX_CHARACTER_LEVEL`, with a property
`max_skill_level`. Per the official docs the gathering/crafting skill cap equals
the character cap (50); cite the same source comment as `MAX_CHARACTER_LEVEL`.
`MAX_SKILL_LEVEL = 50`. (Single constant — trivially corrected if the cap ever
diverges; keeps "derive from documented data, never invent inline".)

### `CharacterObjective`
Built once from `GameData` (`CharacterObjective.from_game_data(game_data)`).
Frozen. Fields:
- `target_char_level: int` = `game_data.max_character_level`.
- `target_skill_levels: dict[str, int]` = `{skill: game_data.max_skill_level for skill in SKILL_NAMES}`.
- `target_gear: dict[str, str]` = best-attainable item code per equipment slot.

**Best-attainable gear:** since the objective assumes max skills, every
craftable item is ultimately attainable, so the per-slot target is the highest
`equip_value` equippable item in `game_data._item_stats` whose `type_` maps
(via `ITEM_TYPE_TO_SLOTS`) to that slot. For paired slots fed by one type
(`ring1_slot`/`ring2_slot`, `artifact1_slot`/`artifact2_slot`), assign the
top-1 and top-2 distinct items by value (ties broken by item code). A slot with
no candidate item is omitted from `target_gear`. Only slots present in
`EQUIPMENT_SLOTS` are targeted.

### `ObjectiveGap`
`objective.gap(state: WorldState) -> ObjectiveGap`. Frozen. Fields:
- `char_level_gap: int` = `max(0, target_char_level - state.level)`.
- `skill_gaps: dict[str, int]` = `{skill: max(0, target - state.skills.get(skill, 1))}` (only positive gaps included).
- `gear_gaps: dict[str, float]` = per targeted slot, `max(0.0, equip_value(target_item) - equip_value(equipped_item or 0))`; an empty slot scores the full target value. Only positive gaps included.

Each gap also exposes a **normalized fraction** in `[0, 1]` per category so
personalities can weight unlike units:
- `char_level_fraction` = `char_level_gap / target_char_level`.
- `skills_fraction` = `sum(skill_gaps) / (len(SKILL_NAMES) * max_skill_level)`.
- `gear_fraction` = `sum(gear_gaps) / sum(equip_value(target_item) for targeted slots)` (0.0 when no gear targeted).

`is_complete` = all three fractions == 0 (the "finished" character sheet).

### Personality seam
```python
class Personality(Protocol):
    def category_weight(self, category: str) -> float: ...
```
`category` ∈ {`"char_level"`, `"skills"`, `"gear"`}. `BalancedPersonality`
returns `1.0` for every category. A module function
`weighted_remaining(gap: ObjectiveGap, personality: Personality) -> float` =
`Σ_category personality.category_weight(c) * gap.<c>_fraction`. This single
scalar (0 when complete) is the seam P3's frontier search will use to rank
candidate subgoals and that P5's skill-first/level-first variants override by
returning non-uniform weights. P1 ships only `BalancedPersonality`.

### Data flow (P1)
`GameData → CharacterObjective.from_game_data` (once). Per evaluation:
`objective.gap(state) → ObjectiveGap`; optionally `weighted_remaining(gap,
BalancedPersonality())`. No caller wired in P1 — the player loop is untouched.

## Error handling
- Pure, no API calls. `equip_value` mirrors the existing formula (missing
  attack/resistance dicts → 0, per current behavior).
- Empty/sparse `game_data._item_stats` → `target_gear` simply has fewer slots;
  `gear_fraction` denominator 0 → `gear_fraction = 0.0` (no div-by-zero).
- `target_char_level` is always ≥ 1 (documented 50), so `char_level_fraction`
  has no zero denominator.

## Testing
Success per project standard: 0 errors, 0 warnings, 0 skipped, 100% on new code.

- `equip_value`: attack+resistance+hp_restore sum; empty dicts → 0. After
  extraction, `UpgradeEquipmentGoal` behavior unchanged (existing goal tests
  still pass).
- `CharacterObjective.from_game_data`: target_char_level == 50; every skill
  targets max_skill_level; best gear per slot picks the highest-value item of
  the right type; paired ring/artifact slots get top-1/top-2 distinct items;
  slot with no candidate omitted.
- `ObjectiveGap`: positive-only gaps; empty slot scores full target value;
  fractions in [0,1]; `is_complete` true at a maxed/best-geared state; gear
  fraction 0.0 when no gear targeted (empty item table).
- `BalancedPersonality.category_weight` == 1.0 for each category; unknown
  category handling (define: returns 1.0 — balanced treats all equally).
- `weighted_remaining`: 0.0 when gap complete; equals sum of fractions under
  Balanced; increases as gaps widen.

## Files
- Create `src/artifactsmmo_cli/ai/tiers/__init__.py`, `equip_value.py`,
  `objective.py`, `personality.py`.
- Modify `src/artifactsmmo_cli/ai/game_data.py` — `MAX_SKILL_LEVEL` + property.
- Modify `src/artifactsmmo_cli/ai/goals/progression.py` — `_upgrade_value`
  delegates to `equip_value`.
- Tests under `tests/test_ai/tiers/` (or `tests/test_ai/test_tiers_*.py`).

## Out of scope (later phases)
- Any change to goal selection / the player loop / `priorities.py` (P3).
- The meta-goal dependency graph and prerequisite edges (P2).
- Frontier search / desired-state emission / HP interrupt (P3).
- Achievements as objective components (later phase).
- Non-balanced personalities (P5).
- Reachability/attainability analysis of gear (P3) — P1 targets best-by-value
  per slot, treating max-skill attainability as given.

# Alchemy Gather-Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Break the alchemy deadlock — a gatherable skill (alchemy) gated behind a craftable it can't yet make (potions need alchemy 5, lowest recipe is L5) that levels only by gathering (sunflower_field) — by (A) emitting a proactive `ReachSkillLevel(alchemy,5)` bootstrap root and (B) serving a gatherable skill's `ReachSkillLevel` step by gathering its resource when there's no craft-grind. Result: alchemy climbs to 5, potions brew, red_slime becomes winnable, the goal_oscillation stops.

**Architecture:** Two pure helpers + an impure-layer change in `prerequisite_graph.objective_roots` (Part A) and `strategy_driver.objective_step_goal` (Part B). The proven `skill_step_dispatch_pure` core is untouched.

**Tech Stack:** Python 3.13, pytest. Run everything with `uv run`.

## Global Constraints

- All Python commands prefixed with `uv run`. Imports at top only — no inline, no `...`, no `if TYPE_CHECKING`.
- One behavioral class per file; pure helpers may share a module.
- Never catch `Exception`. Use only API/game data or fail — no defaulting.
- Skill taxonomy: alchemy ∈ `CONSUMABLE_CRAFT_SKILLS` (skill_classes.py) and is gatherable (`resource_skill` has alchemy resources). Cooking is consumable-craft but NOT gatherable → excluded from Part A by the gate; its lowest craftable is L1 so it never NO_GRINDs. Do NOT special-case cooking.
- Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.

---

### Task 1: Pure helpers

**Files:**
- Create: `src/artifactsmmo_cli/ai/gather_skill_resource.py`
- Test: `tests/test_ai/test_gather_skill_resource.py`

**Interfaces:**
- `best_gather_resource_drop(skill: str, current_level: int, game_data: GameData) -> str | None`
- `first_craftable_level(skill: str, game_data: GameData) -> int | None`

- [ ] **Step 1: Write failing tests**

```python
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gather_skill_resource import (
    best_gather_resource_drop, first_craftable_level,
)


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "small_health_potion": ItemStats(code="small_health_potion", level=5,
                                          type_="utility", hp_restore=30,
                                          crafting_skill="alchemy", crafting_level=5),
        "cooked_chicken": ItemStats(code="cooked_chicken", level=1, type_="consumable",
                                    crafting_skill="cooking", crafting_level=1),
    }
    # resource_skill: code -> (skill, level); resource_drops: resource -> drop item
    gd._resource_skill = {"sunflower_field": ("alchemy", 1),
                          "nettle": ("alchemy", 20),
                          "ash_tree": ("woodcutting", 1)}
    gd._resource_drops = {"sunflower_field": "sunflower", "nettle": "nettle_leaf",
                          "ash_tree": "ash_wood"}
    return gd


def test_best_gather_resource_picks_highest_usable():
    gd = _gd()
    # alchemy at level 5: sunflower_field(1) usable, nettle(20) not -> sunflower
    assert best_gather_resource_drop("alchemy", 5, gd) == "sunflower"


def test_best_gather_resource_none_when_no_usable():
    gd = _gd()
    # alchemy at level 0: no alchemy resource at level <= 0
    assert best_gather_resource_drop("alchemy", 0, gd) is None


def test_best_gather_resource_none_for_nongatherable_skill():
    gd = _gd()
    assert best_gather_resource_drop("cooking", 10, gd) is None


def test_best_gather_resource_highest_of_several():
    gd = _gd()
    # at alchemy 25 both sunflower(1) and nettle(20) usable -> nettle (highest)
    assert best_gather_resource_drop("alchemy", 25, gd) == "nettle_leaf"


def test_first_craftable_level_alchemy():
    assert first_craftable_level("alchemy", _gd()) == 5


def test_first_craftable_level_cooking():
    assert first_craftable_level("cooking", _gd()) == 1


def test_first_craftable_level_none_when_no_recipe():
    assert first_craftable_level("mining", _gd()) is None
```

- [ ] **Step 2: Run → verify FAIL** (`uv run pytest tests/test_ai/test_gather_skill_resource.py -v` → ImportError).

- [ ] **Step 3: Implement**

```python
"""Gather-resource + first-craftable-level lookups for gatherable skills."""

from artifactsmmo_cli.ai.game_data import GameData


def best_gather_resource_drop(skill: str, current_level: int,
                              game_data: GameData) -> str | None:
    """Drop item of the highest-level resource gathered by `skill` at
    `level <= current_level`, or None when the skill has no gatherable resource
    usable now. Highest level = best XP per gather; ties break on the smallest
    resource code (deterministic)."""
    best_code: str | None = None
    best_level = -1
    for resource, (res_skill, res_level) in sorted(game_data.resource_skill.items()):
        if res_skill != skill or res_level > current_level:
            continue
        if res_level > best_level:
            best_level = res_level
            best_code = resource
    if best_code is None:
        return None
    return game_data.resource_drop_item(best_code)


def first_craftable_level(skill: str, game_data: GameData) -> int | None:
    """Lowest `crafting_level` among items whose `crafting_skill == skill`, or
    None when the skill crafts nothing."""
    levels = [stats.crafting_level
              for stats in game_data.all_item_stats.values()
              if stats.crafting_skill == skill]
    return min(levels) if levels else None
```

Note: confirm the public accessor for the resource→(skill,level) map. `game_data.resource_skill` (or `game_data._resource_skill`) returns the dict; use whichever is the established read accessor (grep existing callers). If only `resource_skill_level(code)` exists, iterate `game_data._resource_skill` (the property backing it). `resource_drop_item(code)` returns the drop.

- [ ] **Step 4: Run → verify PASS + mypy** (`uv run pytest tests/test_ai/test_gather_skill_resource.py -v && uv run mypy src/artifactsmmo_cli/ai/gather_skill_resource.py`).

- [ ] **Step 5: Commit** — `feat: gather-resource + first-craftable-level helpers for gatherable skills`.

---

### Task 2: Part B — serve NO_GRIND by gathering

**Files:**
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py` — `objective_step_goal`, the `ReachSkillLevel` NO_GRIND branch (~line 793, the `return None` after the `grind` branch).
- Test: `tests/test_ai/test_strategy_driver.py` (or `test_skill_step_dispatch.py` if that's where objective_step_goal is tested — grep first).

**Interfaces:** Consumes `best_gather_resource_drop` (Task 1). Produces: NO_GRIND for a gatherable skill → `GatherMaterialsGoal(target_item=drop, needed={drop: held+1})`.

- [ ] **Step 1: Write the failing test**

A `ReachSkillLevel(alchemy, 5)` step at alchemy level 2 with no alchemy craftable-now, gatherable sunflower_field, should return a `GatherMaterialsGoal` for sunflower (not None). Match the file's existing `objective_step_goal` test fixtures (read them first for the exact GameData/state/ctx construction). Assert:
- returns a `GatherMaterialsGoal` with `target_item == "sunflower"` (or its drop) and `needed == {"sunflower": held+1}`.
- A `ReachSkillLevel` for a non-gatherable no-craft skill still returns `None`.
- A skill with a craftable-now still returns the grind `GatherMaterialsGoal(decision.code, …)` (unchanged behaviour) — regression guard.

- [ ] **Step 2: Run → verify FAIL** (the NO_GRIND path returns None for alchemy today).

- [ ] **Step 3: Implement**

Add the import at top: `from artifactsmmo_cli.ai.gather_skill_resource import best_gather_resource_drop`. Change the NO_GRIND tail (currently `return None` at ~line 793) to:

```python
        # SUPPRESS: committed root crafts its own gear — no objective-step goal.
        # NO_GRIND: no craftable to grind. If the skill is gatherable at the
        # current level, LEVEL IT BY GATHERING its resource (grind-one-replan) —
        # a gatherable-but-no-low-craftable skill (alchemy: lowest recipe L5,
        # sunflower_field gives XP at L1) climbs to its first craftable level this
        # way. Skills with no gather resource fall through to None (arbiter
        # advances). Mirrors the "grind" branch's grind-one-replan.
        if decision.kind == "no_grind":
            drop = best_gather_resource_drop(step.skill, current, game_data)
            if drop is not None:
                bank = state.bank_items or {}
                held = state.inventory.get(drop, 0) + bank.get(drop, 0)
                return GatherMaterialsGoal(target_item=drop, needed={drop: held + 1})
        return None
```

(Guard on `decision.kind == "no_grind"` so SUPPRESS still returns None. `current`, `state`, `game_data`, `step` are all in scope. `GatherMaterialsGoal` is already imported in strategy_driver.)

- [ ] **Step 4: Run → verify PASS + existing objective_step tests green + mypy.** If an existing skill-dispatch/strategy_driver test regresses, investigate — the SUPPRESS path must be unchanged and non-gatherable-skill NO_GRIND must still return None.

- [ ] **Step 5: Commit** — `feat(strategy): serve NO_GRIND for a gatherable skill by gathering its resource`.

---

### Task 3: Part A — proactive alchemy bootstrap root

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py` — `objective_roots`, the `state is not None` block (after the `_CRAFTING_BOOTSTRAP_SKILLS` loop, ~line 145).
- Modify (comment only): `src/artifactsmmo_cli/ai/tiers/skill_gates.py` module docstring + `skill_step_dispatch.py` NO_GRIND comment — correct the "gather skills can't deadlock" assumption.
- Test: `tests/test_ai/test_tiers_prerequisite_graph.py`.

**Interfaces:** Consumes `first_craftable_level` (Task 1), `CONSUMABLE_CRAFT_SKILLS`, the skill's gatherability (`best_gather_resource_drop(..) is not None` OR a resource-skill membership check).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ai/test_tiers_prerequisite_graph.py`: with a GameData where alchemy is gatherable (sunflower_field) and its first craftable is L5, `objective_roots(objective, state)` at alchemy level < 5 includes `ReachSkillLevel("alchemy", 5)`; at alchemy ≥ 5 it does NOT; a consumable-craft skill that is NOT gatherable (cooking) is NOT added. Match the file's existing `objective_roots` fixtures.

- [ ] **Step 2: Run → verify FAIL** (no alchemy bootstrap root emitted today).

- [ ] **Step 3: Implement**

In `objective_roots`, after the `_CRAFTING_BOOTSTRAP_SKILLS` loop, add a gatherable-consumable-craft bootstrap. Use `objective._game_data` (the objective holds it; `near_term_gear`/`near_term_skill_targets` already read `self._game_data`):

```python
        # Gatherable consumable-craft bootstrap: a skill like alchemy is a
        # gathering skill whose FIRST craftable sits above level 1 (potions need
        # alchemy 5). It can't craft-grind up (nothing craftable below 5) and its
        # resources are consumed only by its own products, so it never self-levels
        # ambiently — a hard deadlock. Emit a bootstrap root to its first-craftable
        # level; the objective-step gather-to-level path (strategy_driver) serves it.
        gd = objective._game_data
        for skill in CONSUMABLE_CRAFT_SKILLS:
            if best_gather_resource_drop(skill, state.level, gd) is None:
                continue  # not gatherable now (e.g. cooking) -> reactive path only
            target = first_craftable_level(skill, gd)
            if target is not None and state.skills.get(skill, 1) < target:
                roots.append(ReachSkillLevel(skill, target))
```

Add imports at top: `from artifactsmmo_cli.ai.tiers.skill_classes import CONSUMABLE_CRAFT_SKILLS` (confirm not already imported) and `from artifactsmmo_cli.ai.gather_skill_resource import best_gather_resource_drop, first_craftable_level`.

Note: `best_gather_resource_drop(skill, state.level, gd)` gates on gatherability at the CHARACTER level — sunflower_field is L1 so alchemy always qualifies; cooking has no gather resource → None → skipped (reactive-only, per spec). This is the exact "gatherable AND consumable-craft" gate.

- [ ] **Step 4: Correct the stale comments** — update `skill_gates.py` module docstring ("Gather/resource skill gates are EXCLUDED … cannot deadlock") and the `skill_step_dispatch.py` NO_GRIND docstring to note: a gatherable skill gated behind a craftable it can't yet make is served by the objective-step gather-to-level path, not left to (possibly absent) ambient gathering.

- [ ] **Step 5: Run → verify PASS + prerequisite_graph tests green + mypy.**

- [ ] **Step 6: Commit** — `feat(objective): proactive gather-bootstrap root for gatherable consumable-craft skills`.

---

### Task 4: End-to-end reproduction + full-suite verification

**Files:** Test — add an end-to-end guard; else verification only.

- [ ] **Step 1: End-to-end reproduction test**

Recreate the investigation's scenario (L8, alchemy 2, ≥3 sunflowers held, empty utility slots) and assert the potion root is now SERVABLE — i.e. `objective_step_goal` for its `ReachSkillLevel(alchemy,5)` step returns a gather `GatherMaterialsGoal` (not None), so `keep_servable` no longer drops the potion root. Put it in `tests/test_ai/test_strategy_driver.py` (or a new `test_alchemy_bootstrap_e2e.py`) using the same fixtures the investigation repro used (the scratchpad repro under the session dir is a reference; build a clean fixture). Assert the potion root survives the servability filter.

- [ ] **Step 2: Full suite** — `uv run pytest` → 0 errors/warnings/skips, 100% coverage.

- [ ] **Step 3: Type check** — `uv run mypy src/artifactsmmo_cli/ai` → clean.

- [ ] **Step 4: If a live TOKEN is present (best-effort)** — run `uv run artifactsmmo plan Robby` and confirm a potion/alchemy root now appears servable in the ranking (was absent). If no creds, skip — Step 1 proves the servability fix against the exact scenario.

- [ ] **Step 5: If coverage < 100%**, add the missing-line test and re-run.

---

## Self-Review

- **Spec coverage:** Part A bootstrap root gated on gatherable-∧-consumable-craft (Task 3); Part B NO_GRIND gather-serve (Task 2); helpers (Task 1); stale-assumption comments (Task 3 Step 4); cooking excluded by the gatherability gate (Task 3, non-gatherable → skipped); reactive cooking untouched; e2e servability repro (Task 4). All spec sections mapped.
- **Placeholder scan:** every step has code/commands. The one "confirm the accessor" note (Task 1 Step 3) names the exact candidates (`resource_skill` / `_resource_skill` / iterate the property) — a lookup, not a gap.
- **Type consistency:** `best_gather_resource_drop(skill, current_level, game_data)` and `first_craftable_level(skill, game_data)` identical across Tasks 1/2/3; `GatherMaterialsGoal(target_item=, needed=)` matches the existing grind-branch call; `objective._game_data` matches the field at objective.py:216.
- **Formal:** proven skill-dispatch cores untouched (Task 2 guards on the existing `no_grind` decision; the pure core still returns it). Impure-layer + helpers only — unit tests, no formal re-gate. The change strengthens liveness (adds a servable path where the core deadlocked).
- **Risk note:** Part B changes planner-visible behavior (a previously-None step now yields a gather goal). Task 2/4 assert the new goal and that non-gatherable/SUPPRESS paths are unchanged; the full suite guards against a servability/liveness regression.

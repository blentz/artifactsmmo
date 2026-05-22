# Goal Tiers P2 — Tier-2 Meta-Goal Prerequisite Graph — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Pure, no-behavior-change substrate; tasks build in order.

**Goal:** Ship the pure prerequisite-graph substrate for the tiered architecture: meta-goal nodes (`ReachCharLevel`, `ReachSkillLevel`, `ObtainItem`) and a data-derived `prerequisites(node, state, game_data)` edge function, plus `objective_roots`/`combat_capable`/`best_attainable_weapon`. Consumed by nothing yet (no behavior change).

**Architecture:** Frozen/hashable nodes with `is_satisfied`; a free `prerequisites` function dispatching on node type derives edges from recipes / resource→skill / monster levels; gathering and unknown-source items are leaves so chains terminate; cycles are left for P3's traversal.

**Tech Stack:** Python 3.13, uv, pytest.

---

## File Structure
- Create `src/artifactsmmo_cli/ai/tiers/meta_goal.py` — `MetaGoal` protocol, `owned_count`, `ReachCharLevel`, `ReachSkillLevel`, `ObtainItem`.
- Create `src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py` — `combat_capable`, `best_attainable_weapon`, `prerequisites`, `objective_roots`.
- Modify `src/artifactsmmo_cli/ai/tiers/__init__.py` — exports.
- Tests: `tests/test_ai/test_tiers_meta_goal.py`, `tests/test_ai/test_tiers_prerequisite_graph.py`.

---

## Task 1: Meta-goal nodes

**Files:** Create `src/artifactsmmo_cli/ai/tiers/meta_goal.py`; Test `tests/test_ai/test_tiers_meta_goal.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_tiers_meta_goal.py`:

```python
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.meta_goal import (
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
    owned_count,
)
from tests.test_ai.fixtures import make_state

GD = GameData()


def test_reach_char_level_satisfaction():
    assert ReachCharLevel(10).is_satisfied(make_state(level=10), GD) is True
    assert ReachCharLevel(10).is_satisfied(make_state(level=9), GD) is False


def test_reach_skill_level_satisfaction():
    s = make_state(skills={"mining": 5})
    assert ReachSkillLevel("mining", 5).is_satisfied(s, GD) is True
    assert ReachSkillLevel("mining", 6).is_satisfied(s, GD) is False
    # default skill level is 1 when absent
    assert ReachSkillLevel("cooking", 2).is_satisfied(s, GD) is False
    assert ReachSkillLevel("cooking", 1).is_satisfied(s, GD) is True


def test_owned_count_inventory_bank_equipped():
    s = make_state(inventory={"copper_ore": 3}, bank_items={"copper_ore": 4},
                   equipment={"weapon_slot": "copper_dagger"})
    assert owned_count(s, "copper_ore") == 7
    assert owned_count(s, "copper_dagger") == 1   # equipped counts as 1
    assert owned_count(s, "absent") == 0


def test_obtain_item_satisfaction_against_quantity():
    s = make_state(inventory={"copper_ore": 3}, bank_items={"copper_ore": 4})
    assert ObtainItem("copper_ore", 7).is_satisfied(s, GD) is True
    assert ObtainItem("copper_ore", 8).is_satisfied(s, GD) is False
    assert ObtainItem("copper_ore").is_satisfied(s, GD) is True  # default qty 1


def test_nodes_are_hashable():
    # frozen dataclasses → usable in visited-sets during P3 traversal
    assert {ReachCharLevel(5), ReachSkillLevel("mining", 3), ObtainItem("x", 2)}
    assert ObtainItem("x", 2) == ObtainItem("x", 2)
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_ai/test_tiers_meta_goal.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

Create `src/artifactsmmo_cli/ai/tiers/meta_goal.py`:

```python
"""Tier-2 meta-goal nodes: concrete progression conditions for the
prerequisite graph. Frozen + hashable so P3 traversal can use visited-sets."""

from dataclasses import dataclass
from typing import Protocol

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


def owned_count(state: WorldState, code: str) -> int:
    """How many of `code` the character has across inventory, bank, and the
    equipped slots (an equipped item counts as one)."""
    count = state.inventory.get(code, 0)
    if state.bank_items:
        count += state.bank_items.get(code, 0)
    if code in state.equipment.values():
        count += 1
    return count


class MetaGoal(Protocol):
    """A concrete progression condition that is either satisfied or not."""

    def is_satisfied(self, state: WorldState, game_data: GameData) -> bool: ...


@dataclass(frozen=True)
class ReachCharLevel:
    level: int

    def is_satisfied(self, state: WorldState, game_data: GameData) -> bool:
        return state.level >= self.level


@dataclass(frozen=True)
class ReachSkillLevel:
    skill: str
    level: int

    def is_satisfied(self, state: WorldState, game_data: GameData) -> bool:
        return state.skills.get(self.skill, 1) >= self.level


@dataclass(frozen=True)
class ObtainItem:
    code: str
    quantity: int = 1

    def is_satisfied(self, state: WorldState, game_data: GameData) -> bool:
        return owned_count(state, self.code) >= self.quantity
```

- [ ] **Step 4: Run, confirm PASS**

Run: `uv run pytest tests/test_ai/test_tiers_meta_goal.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/meta_goal.py tests/test_ai/test_tiers_meta_goal.py
git commit -m "feat(ai): Tier-2 meta-goal nodes (ReachCharLevel/Skill, ObtainItem)"
```

---

## Task 2: Prerequisite edges + roots + capability helpers

**Files:** Create `src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py`; Test `tests/test_ai/test_tiers_prerequisite_graph.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_tiers_prerequisite_graph.py`:

```python
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.prerequisite_graph import (
    best_attainable_weapon,
    combat_capable,
    objective_roots,
    prerequisites,
)
from artifactsmmo_cli.ai.world_state import SKILL_NAMES
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   attack={"fire": 12}, crafting_skill="weaponcrafting", crafting_level=1),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon", attack={"fire": 30}),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource"),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"copper_dagger": {"copper_bar": 6}}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    gd._monster_level = {"chicken": 1, "dragon": 40}
    return gd


def test_obtain_craftable_yields_skill_and_materials():
    gd = _gd()
    prereqs = prerequisites(ObtainItem("copper_dagger"), make_state(), gd)
    assert ReachSkillLevel("weaponcrafting", 1) in prereqs
    assert ObtainItem("copper_bar", 6) in prereqs


def test_obtain_already_owned_has_no_prereqs():
    gd = _gd()
    s = make_state(inventory={"copper_dagger": 1})
    assert prerequisites(ObtainItem("copper_dagger"), s, gd) == []


def test_obtain_gatherable_yields_gather_skill():
    gd = _gd()
    assert prerequisites(ObtainItem("copper_ore"), make_state(), gd) == [ReachSkillLevel("mining", 1)]


def test_obtain_unknown_source_is_leaf():
    gd = _gd()
    assert prerequisites(ObtainItem("mystery"), make_state(), gd) == []


def test_reach_char_level_leaf_when_combat_capable():
    gd = _gd()  # chicken level 1 → beatable at char level 1
    assert prerequisites(ReachCharLevel(50), make_state(level=1), gd) == []


def test_reach_char_level_needs_weapon_when_underequipped():
    gd = GameData()
    gd._monster_level = {"dragon": 40}  # nothing beatable at level 1
    gd._item_stats = {"iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon", attack={"fire": 30})}
    prereqs = prerequisites(ReachCharLevel(50), make_state(level=1), gd)
    assert prereqs == [ObtainItem("iron_sword")]


def test_reach_char_level_leaf_when_no_weapon_exists():
    gd = GameData()
    gd._monster_level = {"dragon": 40}
    assert prerequisites(ReachCharLevel(50), make_state(level=1), gd) == []


def test_reach_skill_level_is_leaf():
    assert prerequisites(ReachSkillLevel("mining", 30), make_state(), _gd()) == []


def test_combat_capable_boundary():
    gd = GameData()
    gd._monster_level = {"m": 6}
    assert combat_capable(make_state(level=5), gd) is True   # 6 <= 5+1
    assert combat_capable(make_state(level=4), gd) is False  # 6 > 4+1


def test_best_attainable_weapon_highest_value_with_tiebreak():
    gd = _gd()
    assert best_attainable_weapon(gd) == "iron_sword"  # 30 > 12
    assert best_attainable_weapon(GameData()) is None   # no weapons


def test_objective_roots_cover_level_skills_gear():
    gd = _gd()
    obj = CharacterObjective.from_game_data(gd)
    roots = objective_roots(obj)
    assert ReachCharLevel(50) in roots
    assert all(ReachSkillLevel(s, 50) in roots for s in SKILL_NAMES)
    assert any(isinstance(r, ObtainItem) for r in roots)  # gear targets


def test_cyclic_recipe_traversal_terminates():
    """prerequisites returns finite direct edges; a visited-set BFS over a
    cyclic recipe terminates (P2 adds no traversal; the test drives one)."""
    gd = GameData()
    gd._crafting_recipes = {"a": {"b": 1}, "b": {"a": 1}}
    gd._item_stats = {
        "a": ItemStats(code="a", level=1, type_="resource"),
        "b": ItemStats(code="b", level=1, type_="resource"),
    }
    seen = set()
    frontier = [ObtainItem("a")]
    while frontier:
        node = frontier.pop()
        if node in seen:
            continue
        seen.add(node)
        frontier.extend(prerequisites(node, make_state(), gd))
    assert ObtainItem("a", 1) in seen and ObtainItem("b", 1) in seen
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_ai/test_tiers_prerequisite_graph.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

Create `src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py`:

```python
"""Pure prerequisite edges over Tier-2 meta-goals — the P3 search substrate.

`prerequisites(node, state, game_data)` returns a node's DIRECT prerequisites,
derived only from game data. Gathering and unknown-source items are leaves so
chains terminate; cycles (if any) are left for P3's visited-set traversal."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import WorldState


def combat_capable(state: WorldState, game_data: GameData) -> bool:
    """True when a beatable monster exists — the documented FightAction gate
    `char_level >= monster_level - 1`, i.e. monster_level <= char_level + 1.
    (Win-rate / gear-strength refinement is deferred to P3's search.)"""
    return any(level <= state.level + 1 for level in game_data._monster_level.values())


def best_attainable_weapon(game_data: GameData) -> str | None:
    """Highest equip_value weapon in the item table (ties broken by code), or
    None when there are no weapons."""
    best: tuple[float, str] | None = None
    for code, stats in game_data._item_stats.items():
        if stats.type_ != "weapon":
            continue
        value = equip_value(stats)
        if best is None or value > best[0] or (value == best[0] and code < best[1]):
            best = (value, code)
    return best[1] if best else None


def prerequisites(node: MetaGoal, state: WorldState, game_data: GameData) -> list[MetaGoal]:
    """Direct prerequisites of `node`, derived from game data."""
    if isinstance(node, ObtainItem):
        if node.is_satisfied(state, game_data):
            return []
        recipe = game_data.crafting_recipe(node.code)
        if recipe is not None:
            prereqs: list[MetaGoal] = []
            stats = game_data.item_stats(node.code)
            if stats is not None and stats.crafting_skill:
                prereqs.append(ReachSkillLevel(stats.crafting_skill, stats.crafting_level))
            prereqs.extend(ObtainItem(mat, qty) for mat, qty in recipe.items())
            return prereqs
        for res_code, drop in game_data._resource_drops.items():
            if drop == node.code:
                skill_level = game_data.resource_skill(res_code)
                if skill_level is not None:
                    return [ReachSkillLevel(skill_level[0], skill_level[1])]
        return []  # buyable / monster-drop / unknown → leaf
    if isinstance(node, ReachCharLevel):
        if combat_capable(state, game_data):
            return []
        weapon = best_attainable_weapon(game_data)
        return [ObtainItem(weapon)] if weapon is not None else []
    return []  # ReachSkillLevel → leaf (materials enter via ObtainItem chains)


def objective_roots(objective: CharacterObjective) -> list[MetaGoal]:
    """The Tier-1 objective expressed as root meta-goals for P3's search."""
    roots: list[MetaGoal] = [ReachCharLevel(objective.target_char_level)]
    roots.extend(ReachSkillLevel(skill, level)
                 for skill, level in objective.target_skill_levels.items())
    roots.extend(ObtainItem(code) for code in objective.target_gear.values())
    return roots
```

- [ ] **Step 4: Run, confirm PASS**

Run: `uv run pytest tests/test_ai/test_tiers_prerequisite_graph.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py tests/test_ai/test_tiers_prerequisite_graph.py
git commit -m "feat(ai): Tier-2 prerequisite edges + roots + capability helpers"
```

---

## Task 3: Exports + full verification

**Files:** Modify `src/artifactsmmo_cli/ai/tiers/__init__.py`.

- [ ] **Step 1: Extend exports**

Add the new public names to `src/artifactsmmo_cli/ai/tiers/__init__.py` imports
and `__all__`:

```python
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
    owned_count,
)
from artifactsmmo_cli.ai.tiers.prerequisite_graph import (
    best_attainable_weapon,
    combat_capable,
    objective_roots,
    prerequisites,
)
```
Append `"MetaGoal", "ObtainItem", "ReachCharLevel", "ReachSkillLevel",
"owned_count", "best_attainable_weapon", "combat_capable", "objective_roots",
"prerequisites"` to `__all__`.

- [ ] **Step 2: Full verification**

Run: `uv run pytest -q` → all pass, 0 skipped.
Run: `uv run pytest tests/test_ai -q --cov=artifactsmmo_cli.ai.tiers --cov-report=term-missing`
→ `tiers/*` 100% (add a test for any missed branch).
Run: `uv run ruff check src/artifactsmmo_cli/ai/tiers tests/test_ai/test_tiers_*.py` → clean.
Run: `uv run mypy src/artifactsmmo_cli/ai/tiers` → no errors.

- [ ] **Step 3: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/__init__.py
git commit -m "feat(ai): export tiers P2 prerequisite-graph API"
```

---

## Self-review notes
- **Spec coverage:** nodes + is_satisfied + owned_count (T1); ObtainItem
  craftable/gatherable/owned/unknown edges, ReachCharLevel capable/under-equipped/
  no-weapon, ReachSkillLevel leaf, combat_capable boundary, best_attainable_weapon,
  objective_roots, cycle-safe traversal (T2); exports (T3). All mapped.
- **No behavior change:** nothing imports the new module into the player loop.
- **Type consistency:** `prerequisites(MetaGoal, WorldState, GameData) -> list[MetaGoal]`,
  `is_satisfied(WorldState, GameData) -> bool`, `objective_roots(CharacterObjective)
  -> list[MetaGoal]` used identically across tasks and tests.
- Frozen dataclasses give value equality + hashing for visited-sets (tested).

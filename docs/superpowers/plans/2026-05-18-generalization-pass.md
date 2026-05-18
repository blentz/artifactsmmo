# Generalization Pass — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace three categories of special-casing with generic abstractions: action tags, a single priority ladder, and a generic blocker registry. Each removes cross-file coupling identified during the post-Phase G review.

**Architecture:** Three sequential refactors, each landed independently with tests. Order matters: action tags first (other refactors depend on having tags available); priority ladder second (centralizes constants before they get duplicated further); blocker registry last (largest scope, benefits from prior cleanup).

**Tech Stack:** Python 3.13, uv, pytest. Pure refactors — no schema changes, no new external dependencies.

**Background:** `docs/superpowers/specs/2026-05-18-strategic-reasoning-design.md` informs the *why*; this plan covers the *cleanup* after Phase G shipped.

---

## File Structure

### New files
```
src/artifactsmmo_cli/ai/
└── priorities.py            # single goal-priority ladder (R-2)
src/artifactsmmo_cli/ai/blockers/
├── __init__.py
├── registry.py              # BlockerState + BlockerRegistry (R-3)
└── bank.py                  # Bank-specific blocker initialization (R-3)
```

### Modified files
```
src/artifactsmmo_cli/ai/actions/*.py     # add class-level `tags` (R-1)
src/artifactsmmo_cli/ai/actions/base.py  # Action.tags: frozenset[str] (R-1)
src/artifactsmmo_cli/ai/goals/*.py       # use tags in relevant_actions (R-1)
                                          # use priorities.py constants (R-2)
src/artifactsmmo_cli/ai/player.py        # use BlockerRegistry (R-3)
```

---

## R-1: Action tags

**Why:** Every goal's `relevant_actions` does `isinstance(a, FightAction) or isinstance(a, RestAction) or ...`. Pattern repeats in ~12 goals. Adding a new action class requires editing every goal that should accept it.

**Approach:** Class-level `tags: frozenset[str]` on `Action`. Each subclass overrides. Goals filter with `action.tags & {"combat", "recovery"}` instead of isinstance chains. isinstance stays only where the goal genuinely needs concrete type info (e.g. `action.monster_code` access).

### Task R-1.1: Add `tags` attribute to base Action class

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/base.py`
- Modify: `tests/test_ai/test_actions.py` (one new test)

- [ ] **Step 1: Write failing test**

```python
def test_base_action_has_empty_tags_by_default():
    """Every Action gets an empty tags frozenset unless overridden."""
    class _Concrete(Action):
        def is_applicable(self, state, gd): return True
        def apply(self, state, gd): return state
        def cost(self, state, gd, history=None): return 1.0
        def execute(self, state, client): return state
    assert _Concrete.tags == frozenset()
```

- [ ] **Step 2: Verify failure** — `Action` has no `tags` attribute.

- [ ] **Step 3: Add to `base.py`**

```python
class Action(ABC):
    """..."""

    tags: frozenset[str] = frozenset()
    """Semantic labels for goal-level action filtering. Subclasses override.
    Goals filter with `action.tags & {"combat"}` instead of isinstance chains."""
```

- [ ] **Step 4: Run test** — green.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/base.py tests/test_ai/test_actions.py
git commit -m "feat(ai/actions): Action.tags frozenset for semantic filtering (R-1.1)"
```

### Task R-1.2: Tag every concrete Action subclass

**Files:**
- Modify: every file in `src/artifactsmmo_cli/ai/actions/` with a concrete Action class.

**Tag vocabulary (intentionally small):**

| Tag | Meaning |
|---|---|
| `combat` | Engages a monster (FightAction). |
| `gather` | Collects resources (GatherAction). |
| `craft` | Produces items from materials (CraftAction). |
| `movement` | Changes position (MoveAction, MapTransitionAction). |
| `recovery` | Restores HP/state (RestAction, UseConsumableAction). |
| `bank` | Interacts with bank (DepositAll, Withdraw, BuyBankExpansion, gold). |
| `task` | Interacts with taskmaster (Accept/Complete/Cancel/Exchange/Trade). |
| `npc` | NPC market trade (NpcBuy, NpcSell). |
| `equip` | Equipment slot manipulation (Equip, Unequip). |
| `cleanup` | Removes inventory (DeleteItem, Recycle). |
| `claim` | Pending-item pickup (ClaimPendingItemAction). |
| `produces_char_xp` | Action grants character XP (FightAction). |
| `produces_skill_xp` | Action grants per-skill XP (GatherAction, CraftAction). |

- [ ] **Step 1: Write failing test for each major action class**

```python
class TestActionTags:
    def test_fight_action_tagged_combat(self):
        from artifactsmmo_cli.ai.actions.combat import FightAction
        assert "combat" in FightAction.tags
        assert "produces_char_xp" in FightAction.tags

    def test_gather_action_tagged_gather(self):
        from artifactsmmo_cli.ai.actions.gathering import GatherAction
        assert "gather" in GatherAction.tags
        assert "produces_skill_xp" in GatherAction.tags

    def test_rest_and_use_consumable_tagged_recovery(self):
        from artifactsmmo_cli.ai.actions.rest import RestAction
        from artifactsmmo_cli.ai.actions.consumable import UseConsumableAction
        assert "recovery" in RestAction.tags
        assert "recovery" in UseConsumableAction.tags

    # ... one test per tag, exercising a representative action class
```

- [ ] **Step 2: Verify all fail.**

- [ ] **Step 3: Add `tags` to each Action subclass.** Walk through every concrete class in `src/artifactsmmo_cli/ai/actions/`. Add as a class attribute right after the docstring:

```python
@dataclass
class FightAction(Action):
    """..."""
    tags: frozenset[str] = frozenset({"combat", "produces_char_xp"})
    # ...
```

Important: `@dataclass` decorator and frozen class attribute coexist as long as the attribute is annotated with a default that's hashable. `frozenset` is fine.

- [ ] **Step 4: Run all tests** — green.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/ tests/test_ai/test_actions.py
git commit -m "feat(ai/actions): tag every action class with semantic labels (R-1.2)"
```

### Task R-1.3: Migrate goal `relevant_actions` to tag-based filtering

**Files:**
- Modify: every file in `src/artifactsmmo_cli/ai/goals/` that overrides `relevant_actions`.

**Mechanical replacement:**

Before:
```python
if isinstance(action, (RestAction, UseConsumableAction)):
    result.append(action)
```
After:
```python
if "recovery" in action.tags:
    result.append(action)
```

**Keep isinstance only when the goal needs a concrete attribute** (e.g. `if isinstance(action, FightAction) and action.monster_code == X:`). Tags don't carry that.

- [ ] **Step 1: For each goal file with `relevant_actions`, identify which isinstance chains can become tag checks.** Estimated ~12 files.

- [ ] **Step 2: Replace in each, one file per commit (so blast radius stays small).**

- [ ] **Step 3: Run all tests after each commit.**

- [ ] **Final commit per file:**

```bash
git commit -m "refactor(ai/goals/<name>): use action tags instead of isinstance chains (R-1.3)"
```

### R-1 Validation gate
- [ ] Full test suite green
- [ ] `grep -r "isinstance(a.*Action)" src/artifactsmmo_cli/ai/goals/` returns only cases that genuinely need concrete-type access.

---

## R-2: Priority ladder

**Why:** Magic-number priorities scattered across files (FarmItems=35, LowYieldCancel=70, RestoreHP=110, etc.). Hard to reason about ordering globally; changing one risks breaking another's relative position.

**Approach:** Single module `src/artifactsmmo_cli/ai/priorities.py` exporting named constants in ascending order. Each goal imports the constant for its priority. The module's docstring is the ladder documentation.

### Task R-2.1: Create priorities.py

**Files:**
- Create: `src/artifactsmmo_cli/ai/priorities.py`
- Modify: `tests/test_ai/test_priorities.py` (new)

- [ ] **Step 1: Write the module**

```python
"""Single source of truth for goal priorities. Higher = more urgent.

Read top-to-bottom: every goal's relative position is documented here.
Changing any value here changes every goal that uses it. To shift a single
goal's position, change ITS constant — don't redefine the constant inline.
"""

# Survival floor: nothing should override this. Critical HP, irrecoverable
# states. Top of the ladder.
HP_CRITICAL = 110.0
"""When HP is below CRITICAL_HP_FRACTION (RestoreHPGoal). Beats everything."""

# Hard prerequisites: an in-flight blocker that, if not cleared, makes other
# goals unsatisfiable. Below survival, above all normal pursuits.
BANK_UNLOCK = 90.0
"""UnlockBankGoal when bank requires a fight Robby can win."""

REACH_UNLOCK_LEVEL = 85.0
"""Drive char XP grinding to satisfy a learned blocker (ReachUnlockLevelGoal)."""

# Inventory floor: when the inventory is full, depositing becomes nearly
# mandatory or gathering grinds to a halt.
DEPOSIT_FULL = 80.0
"""DepositInventoryGoal ceiling (when used_fraction == 1.0)."""

# Strategic cancel: more valuable to drop the current task than continue it.
LOW_YIELD_CANCEL = 70.0
"""LowYieldCancelGoal when projection shows alternatives clearly pay more."""

# In-flight task completion / one-time task transitions.
COMPLETE_TASK = 90.0   # full task → turn in for reward
TASK_EXCHANGE = 22.0   # spend coins
TASK_CANCEL = 12.0     # combat-driven cancel (when monster impossible)
ACCEPT_TASK = 20.0     # take a new task

# Strategic skill grinding to unlock a near-future upgrade.
LEVEL_SKILL = 55.0
"""LevelSkillGoal when an upgrade is gated on +N skill levels."""

# Material-driven gathering for an upgrade-in-flight.
GATHER_MATERIALS = 50.0
"""GatherMaterialsGoal when an upgrade's materials need collecting."""

# Tactical production goals (data-augmented via dynamic_priority_bonus).
FARM_ITEMS_BASE = 35.0
"""FarmItemsGoal base (per-cycle item-task delivery)."""

UPGRADE_EQUIPMENT_BASE = 35.0
UPGRADE_EQUIPMENT_RELEVANT_TOOL = 50.0
"""UpgradeEquipmentGoal base / bumped when upgrade is a relevant tool."""

FARM_MONSTER_BASE = 30.0
"""FarmMonsterGoal base (per-cycle character-XP grinding)."""

GRIND_CHARACTER_XP_FLOOR = 30.0
GRIND_CHARACTER_XP_CEILING = 45.0
"""GrindCharacterXPGoal bounded range."""
```

- [ ] **Step 2: Tests pin the ordering**

```python
class TestPriorityLadder:
    def test_critical_dominates(self):
        from artifactsmmo_cli.ai.priorities import (
            HP_CRITICAL, BANK_UNLOCK, REACH_UNLOCK_LEVEL,
            DEPOSIT_FULL, LOW_YIELD_CANCEL, LEVEL_SKILL,
            GATHER_MATERIALS, FARM_ITEMS_BASE, FARM_MONSTER_BASE,
        )
        # HP critical must beat all normal goals.
        for p in (BANK_UNLOCK, REACH_UNLOCK_LEVEL, DEPOSIT_FULL,
                  LOW_YIELD_CANCEL, LEVEL_SKILL, GATHER_MATERIALS,
                  FARM_ITEMS_BASE, FARM_MONSTER_BASE):
            assert HP_CRITICAL > p

    def test_blocker_above_normal_pursuits(self):
        from artifactsmmo_cli.ai.priorities import REACH_UNLOCK_LEVEL, FARM_ITEMS_BASE
        assert REACH_UNLOCK_LEVEL > FARM_ITEMS_BASE

    def test_level_skill_above_farm_items(self):
        from artifactsmmo_cli.ai.priorities import LEVEL_SKILL, FARM_ITEMS_BASE
        assert LEVEL_SKILL > FARM_ITEMS_BASE
```

- [ ] **Step 3: Commit**

```bash
git add src/artifactsmmo_cli/ai/priorities.py tests/test_ai/test_priorities.py
git commit -m "feat(ai): single priority ladder module (R-2.1)"
```

### Task R-2.2: Migrate each goal to import from priorities.py

**Files:**
- Modify: every goal file that has a hardcoded priority constant.

- [ ] **Step 1: One file per commit:** replace `return 35.0` with `return priorities.FARM_ITEMS_BASE` etc. Remove the local constant definition.

- [ ] **Step 2: Test after each.**

- [ ] **Final commit per file:**

```bash
git commit -m "refactor(ai/goals/<name>): import priority from ladder module (R-2.2)"
```

### R-2 Validation gate
- [ ] `grep -rn "return [0-9]\+\.0$" src/artifactsmmo_cli/ai/goals/` returns nothing (all priorities go via constants).
- [ ] Full test suite green.

---

## R-3: Blocker registry

**Why:** Bank-specific state lives in 6+ player fields. Pattern will repeat for other gates (workshop, taskmaster, map transition). Need a generic registry.

**Approach:** `BlockerRegistry` mapping `blocker_code` to `BlockerState`. Player owns one registry. On 496/489/etc., a handler adds/updates a blocker. On startup, registry loads from learning store. Dependent goals check `registry.is_blocked("bank")` instead of `player._bank_accessible`.

### Task R-3.1: Define `BlockerState` + `BlockerRegistry`

**Files:**
- Create: `src/artifactsmmo_cli/ai/blockers/__init__.py`
- Create: `src/artifactsmmo_cli/ai/blockers/registry.py`
- Create: `tests/test_ai/test_blocker_registry.py`

```python
# registry.py
from dataclasses import dataclass, field
from datetime import datetime, timezone

from artifactsmmo_cli.ai.learning.store import LearningStore


@dataclass
class BlockerState:
    code: str
    unlock_monster: str | None = None
    required_level: int = 0
    blocked_since_monotonic: float | None = None
    blocked_at_char_level: int = 0


@dataclass
class BlockerRegistry:
    """Per-character registry of learned dependency gates."""

    _blockers: dict[str, BlockerState] = field(default_factory=dict)

    def is_blocked(self, code: str) -> bool:
        return code in self._blockers

    def get(self, code: str) -> BlockerState | None:
        return self._blockers.get(code)

    def mark_blocked(self, code: str, char_level: int, unlock_monster: str | None,
                     required_level: int, store: LearningStore | None = None) -> None:
        ...

    def clear(self, code: str) -> None:
        self._blockers.pop(code, None)

    @classmethod
    def load(cls, store: LearningStore, known_codes: list[str] | None = None) -> "BlockerRegistry":
        ...
```

- [ ] Tests cover mark/clear/load roundtrips.

- [ ] Commit.

### Task R-3.2: Migrate player to use BlockerRegistry

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py`
- Modify: `src/artifactsmmo_cli/ai/goals/unlock_bank.py` (constructor accepts blocker state or registry)

- [ ] Replace `_bank_accessible`, `_bank_blocked_since`, etc. with calls to `self._blockers.is_blocked("bank")` etc.
- [ ] On 496, call `self._blockers.mark_blocked("bank", ...)`.
- [ ] On startup, load via `BlockerRegistry.load(self.history, known_codes=["bank"])`.

- [ ] Run full suite — every existing test that used `_bank_accessible` directly will need updating.

- [ ] Commit.

### R-3 Validation gate
- [ ] `grep -n "_bank_accessible\|_bank_blocked\|_bank_required_level" src/artifactsmmo_cli/ai/player.py` returns nothing.
- [ ] Adding a hypothetical second blocker (e.g. workshop requires X) is a 2-line change in `blockers/` plus the goal that handles it — no player.py edits.

---

## Final validation

After all three refactors:

- [ ] Full test suite: `uv run pytest -q`
- [ ] Live smoke: `uv run artifactsmmo play Robby --dry-run --learn --learn-db /tmp/g-smoke.db` — at least 3 cycles, no exceptions, trace shows goal_rank using new priorities.
- [ ] Code review: no isinstance chains in goal relevant_actions (except for concrete-attribute access), no hardcoded priorities in goals, no bank-specific fields on player.

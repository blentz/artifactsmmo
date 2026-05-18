# Phase G-A — Data Layer Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `Cycle` storage to capture per-skill XP deltas so later Phase G sub-phases (projections, scalarizer, strategic goals) can compare goal yields meaningfully.

**Architecture:** Add `delta_skill_xp_json: str` to `CycleBase` (and `Cycle` by inheritance). Extend `WorldState` with `skill_xp: dict[str, int]` populated from `<skill>_xp` on the character schema. `GamePlayer._record_learning_cycle` diffs each skill's XP between prev and new state and serializes the sparse map to JSON. Add a one-shot `ALTER TABLE` in `LearningStore.__init__` for existing DBs.

**Tech Stack:** Python 3.13, uv, SQLModel + SQLAlchemy 2.x + Pydantic 2, pytest + pytest-cov.

**Spec:** `docs/superpowers/specs/2026-05-18-strategic-reasoning-design.md` §1.

**Naming note:** The existing column `delta_xp` is character XP (unchanged). G-A adds `delta_skill_xp_json` alongside; Phase G-B's projections will read both.

---

## File Structure

### Modified files
```
src/artifactsmmo_cli/ai/learning/
├── models.py            # add delta_skill_xp_json column
└── store.py             # migrate existing DBs on open
src/artifactsmmo_cli/ai/
├── player.py            # _record_learning_cycle computes per-skill deltas
└── world_state.py       # add skill_xp field + populate in from_character_schema
tests/test_ai/
├── fixtures.py          # accept skill_xp kwarg
├── test_learning_models.py
├── test_learning_store.py
└── test_player_learning.py
```

### New files

None.

---

## Task G-A1: Add `delta_skill_xp_json` column to Cycle

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/models.py`
- Modify: `tests/test_ai/test_learning_models.py`

- [ ] **Step 1: Write the failing test** (append to test_learning_models.py)

```python
def test_cycle_has_delta_skill_xp_json_field():
    cycle = Cycle(
        ts="2026-05-18T00:00:00Z", session_id="s1", cycle_index=0, character="hero",
        state_x=0, state_y=0, state_hp=100, state_max_hp=100, state_gold=0,
        state_level=1, state_xp=0, state_max_xp=100,
        state_inventory_used=0, state_inventory_max=100, state_bank_accessible=True,
        state_task_code=None, state_task_type=None,
        state_task_progress=0, state_task_total=0,
        selected_goal="X", action_repr="Y", action_class="Z", outcome="ok",
        predicted_cost=10.0, actual_cooldown_seconds=5.0,
        delta_xp=12, delta_skill_xp_json='{"weaponcrafting": 4}',
        delta_hp=-3, delta_gold=2, delta_inventory_used=1, cycles_to_satisfy=None,
        planner_nodes=2, planner_depth=1, planner_timed_out=False, plan_len=1,
    )
    assert cycle.delta_skill_xp_json == '{"weaponcrafting": 4}'


def test_cycle_delta_skill_xp_json_defaults_to_empty_object():
    cycle = Cycle(
        ts="2026-05-18T00:00:00Z", session_id="s1", cycle_index=0, character="hero",
        state_x=0, state_y=0, state_hp=100, state_max_hp=100, state_gold=0,
        state_level=1, state_xp=0, state_max_xp=100,
        state_inventory_used=0, state_inventory_max=100, state_bank_accessible=True,
        state_task_code=None, state_task_type=None,
        state_task_progress=0, state_task_total=0,
        selected_goal="<none>", action_repr="<no_plan>", action_class="NoPlan", outcome="no_plan",
        predicted_cost=0.0, actual_cooldown_seconds=0.0,
        delta_xp=0, delta_hp=0, delta_gold=0, delta_inventory_used=0, cycles_to_satisfy=None,
        planner_nodes=0, planner_depth=0, planner_timed_out=False, plan_len=0,
    )
    assert cycle.delta_skill_xp_json == "{}"
```

- [ ] **Step 2: Verify failure**

Run: `uv run pytest tests/test_ai/test_learning_models.py -q`
Expected: both new tests fail.

- [ ] **Step 3: Add the column to `CycleBase`** (in `models.py`, alongside other delta fields)

```python
delta_skill_xp_json: str = Field(default="{}", description="JSON {skill: xp_delta} for skills that changed this cycle")
```

- [ ] **Step 4: Re-run**

Run: `uv run pytest tests/test_ai/test_learning_models.py -q`
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/models.py tests/test_ai/test_learning_models.py
git commit -m "feat(ai/learning): add delta_skill_xp_json column to Cycle (Phase G-A)"
```

---

## Task G-A2: Add `skill_xp` to `WorldState` and populate from schema

**Files:**
- Modify: `src/artifactsmmo_cli/ai/world_state.py`
- Modify: `tests/test_ai/fixtures.py`
- Modify: `tests/test_ai/test_world_state.py` (one new test)

**Why first:** `_record_learning_cycle` needs `prev_state.skill_xp` vs `new_state.skill_xp` to compute the delta. The diff must be sourced from per-skill XP, not per-skill level (level rarely changes; XP changes every cycle).

- [ ] **Step 1: Write the failing test** (append to test_world_state.py)

```python
def test_from_character_schema_captures_per_skill_xp():
    """WorldState should expose skill_xp populated from <skill>_xp."""
    from unittest.mock import MagicMock
    from artifactsmmo_cli.ai.world_state import WorldState, SKILL_NAMES

    char = MagicMock()
    char.name = "hero"; char.level = 1; char.xp = 0; char.max_xp = 100
    char.hp = 100; char.max_hp = 100; char.gold = 0
    char.x = 0; char.y = 0
    char.cooldown_expiration = None
    char.task = ""; char.task_type = ""; char.task_progress = 0; char.task_total = 0
    char.inventory = []
    for s in SKILL_NAMES:
        setattr(char, f"{s}_level", 1)
        setattr(char, f"{s}_xp", 0)
    char.weaponcrafting_xp = 42
    # Equipment slots — set them all to "" so from_character_schema doesn't crash
    for slot in ("weapon_slot","shield_slot","helmet_slot","body_armor_slot","leg_armor_slot",
                 "boots_slot","ring1_slot","ring2_slot","amulet_slot",
                 "artifact1_slot","artifact2_slot","artifact3_slot",
                 "utility1_slot","utility2_slot","bag_slot","rune_slot"):
        setattr(char, slot, "")
    char.inventory_max_items = 100

    state = WorldState.from_character_schema(char)
    assert state.skill_xp["weaponcrafting"] == 42
    assert state.skill_xp["fishing"] == 0
```

- [ ] **Step 2: Verify failure**

Run: `uv run pytest tests/test_ai/test_world_state.py -q`
Expected: `WorldState` constructor missing `skill_xp` field, OR the attribute access fails.

- [ ] **Step 3: Extend `WorldState`**

In `src/artifactsmmo_cli/ai/world_state.py`:

1. Add the field (next to `skills: dict[str, int]`):

   ```python
   skill_xp: dict[str, int]            # skill_name -> current XP within level
   ```

2. In `from_character_schema`, after the existing skills loop, populate it:

   ```python
   skill_xp: dict[str, int] = {}
   for skill in SKILL_NAMES:
       skill_xp[skill] = getattr(char, f"{skill}_xp", 0)
   ```

3. Pass `skill_xp=skill_xp` to the `WorldState(...)` constructor call.

- [ ] **Step 4: Extend `make_state` fixture**

In `tests/test_ai/fixtures.py`, add `skill_xp={}` to the defaults so existing tests don't break:

```python
defaults = {
    ...
    "skill_xp": {},
    ...
}
```

- [ ] **Step 5: Run affected tests**

Run: `uv run pytest tests/test_ai/test_world_state.py tests/test_ai/test_player.py -q`
Expected: green.

- [ ] **Step 6: Run full suite**

Run: `uv run pytest -q`
Expected: green.

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/world_state.py tests/test_ai/fixtures.py tests/test_ai/test_world_state.py
git commit -m "feat(ai): WorldState.skill_xp captures per-skill XP from API (Phase G-A)"
```

---

## Task G-A3: Compute per-skill XP delta in `_record_learning_cycle`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py`
- Modify: `tests/test_ai/test_player_learning.py`

- [ ] **Step 1: Write the failing test** (append)

```python
def test_record_learning_cycle_captures_per_skill_xp_delta(tmp_path):
    import json
    from sqlmodel import select
    from artifactsmmo_cli.ai.learning.store import LearningStore
    from artifactsmmo_cli.ai.learning.models import Cycle
    from tests.test_ai.fixtures import make_state

    store = LearningStore(db_path=str(tmp_path / "learn.db"))
    store.start_session(character="hero")

    prev = make_state(skill_xp={"weaponcrafting": 10, "fishing": 50})
    new = make_state(skill_xp={"weaponcrafting": 14, "fishing": 50})
    player = GamePlayer(character="hero")
    player.history = store
    player._record_learning_cycle(
        prev_state=prev, new_state=new,
        action_repr="Craft(copper_axe)", action_class="CraftAction",
        outcome="ok", selected_goal="UpgradeEquipment",
        predicted_cost=5.0, actual_cooldown_seconds=4.0,
        planner_nodes=3, planner_depth=2, planner_timed_out=False, plan_len=2,
    )
    rows = list(store.session.exec(select(Cycle)))
    assert len(rows) == 1
    assert json.loads(rows[0].delta_skill_xp_json) == {"weaponcrafting": 4}
    store.close()
```

- [ ] **Step 2: Verify failure**

Run: `uv run pytest tests/test_ai/test_player_learning.py::test_record_learning_cycle_captures_per_skill_xp_delta -q`
Expected: assertion fails (column is `"{}"` because population isn't wired).

- [ ] **Step 3: Compute and pass the delta**

In `src/artifactsmmo_cli/ai/player.py`, find `_record_learning_cycle`. Where existing `delta_xp` is computed, add:

```python
skill_deltas: dict[str, int] = {}
for skill_name, new_xp in new_state.skill_xp.items():
    prev_xp = prev_state.skill_xp.get(skill_name, 0)
    if new_xp != prev_xp:
        skill_deltas[skill_name] = new_xp - prev_xp
delta_skill_xp_json = json.dumps(skill_deltas, ensure_ascii=False, sort_keys=True)
```

`json` is already imported at the top of `player.py` (line 3). No new import needed.

Pass `delta_skill_xp_json=delta_skill_xp_json` to the `Cycle(...)` constructor inside `record_cycle` (the call in `LearningStore.record_cycle`). If the call site is centralized in `LearningStore.record_cycle`, thread the value through as a parameter.

- [ ] **Step 4: Run target test**

Run: `uv run pytest tests/test_ai/test_player_learning.py::test_record_learning_cycle_captures_per_skill_xp_delta -q`
Expected: green.

- [ ] **Step 5: Run full suite**

Run: `uv run pytest -q --tb=short`
Expected: 1300+ pass.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py src/artifactsmmo_cli/ai/learning/store.py tests/test_ai/test_player_learning.py
git commit -m "feat(ai): record per-skill XP deltas in learning store (Phase G-A)"
```

---

## Task G-A4: Migrate existing DBs

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/store.py`
- Modify: `tests/test_ai/test_learning_store.py`

**Context:** SQLModel's `create_all` only adds tables, not columns. An old DB with the `cycles` table predating G-A1 will throw `OperationalError` on the first insert.

- [ ] **Step 1: Write the failing test**

```python
def test_old_db_without_delta_skill_xp_json_migrates(tmp_path):
    """An existing DB missing delta_skill_xp_json should be migrated on open."""
    import sqlite3
    db_path = str(tmp_path / "old.db")
    conn = sqlite3.connect(db_path)
    # Re-create the cycles table WITHOUT the new column.
    conn.execute("""
        CREATE TABLE cycles (
            id INTEGER PRIMARY KEY,
            ts TEXT NOT NULL, session_id TEXT NOT NULL,
            cycle_index INTEGER NOT NULL, character TEXT NOT NULL,
            state_x INTEGER, state_y INTEGER,
            state_hp INTEGER, state_max_hp INTEGER, state_gold INTEGER,
            state_level INTEGER, state_xp INTEGER, state_max_xp INTEGER,
            state_inventory_used INTEGER, state_inventory_max INTEGER,
            state_bank_accessible INTEGER,
            state_task_code TEXT, state_task_type TEXT,
            state_task_progress INTEGER, state_task_total INTEGER,
            selected_goal TEXT, action_repr TEXT, action_class TEXT, outcome TEXT,
            predicted_cost REAL, actual_cooldown_seconds REAL,
            delta_xp INTEGER, delta_hp INTEGER, delta_gold INTEGER,
            delta_inventory_used INTEGER, cycles_to_satisfy INTEGER,
            planner_nodes INTEGER, planner_depth INTEGER,
            planner_timed_out INTEGER, plan_len INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE sessions (
            session_id TEXT PRIMARY KEY, character TEXT, start_ts TEXT,
            end_ts TEXT, exit_reason TEXT, cycle_count INTEGER
        )
    """)
    conn.commit()
    conn.close()

    store = LearningStore(db_path=db_path)
    store.start_session(character="hero")
    # Inserting via the new model shape must succeed; the migration added
    # the missing column with default '{}'.
    store.record_cycle(... )  # Use existing helper with full args
    store.close()

    # Verify column exists post-migration.
    conn = sqlite3.connect(db_path)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(cycles)")}
    assert "delta_skill_xp_json" in cols
    conn.close()
```

(Fill in `record_cycle(...)` args from an existing test in the same file as a template.)

- [ ] **Step 2: Verify failure**

Run: `uv run pytest tests/test_ai/test_learning_store.py::test_old_db_without_delta_skill_xp_json_migrates -q`
Expected: `sqlite3.OperationalError: table cycles has no column named delta_skill_xp_json`.

- [ ] **Step 3: Add migration to `LearningStore.__init__`**

In `src/artifactsmmo_cli/ai/learning/store.py`, after `SQLModel.metadata.create_all(self.engine)`:

```python
# Manual ALTER for newly-added columns on existing DBs (no Alembic in scope).
with self.engine.connect() as conn:
    cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(cycles)")}
    if "delta_skill_xp_json" not in cols:
        conn.exec_driver_sql(
            "ALTER TABLE cycles ADD COLUMN delta_skill_xp_json TEXT NOT NULL DEFAULT '{}'"
        )
        conn.commit()
```

- [ ] **Step 4: Re-run**

Run: `uv run pytest tests/test_ai/test_learning_store.py -q`
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/store.py tests/test_ai/test_learning_store.py
git commit -m "feat(ai/learning): migrate existing DBs to add delta_skill_xp_json (Phase G-A)"
```

---

## Final validation gate

After all four tasks:

- [ ] **Full test suite:** `uv run pytest -q` — all green.
- [ ] **Manual sanity:** Open the live Robby learning DB (if available) via `LearningStore(db_path="...")`, confirm no errors, query one recent cycle, confirm `delta_skill_xp_json` is parseable JSON.
- [ ] **Dry-run trace:** `uv run artifactsmmo play Robby --dry-run --learn --learn-db /tmp/g-a-smoke.db` for a few cycles; tail the most recent Cycle row and confirm `delta_skill_xp_json` is populated as a sparse map (likely `"{}"` in dry-run since no real API calls grant skill XP).

Phase G-A is complete when those pass. G-B (`projections.py`) consumes `delta_xp` (existing) and `delta_skill_xp_json` (new).

# Progression Tree — Phase 1: Planner Testability Harness

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the planner testable offline — a pure `plan_from_state` entry, a snapshot-backed scenario harness with golden expectations on the CURRENT engine, and a `plan --scenario` CLI — as the regression net for the progression-tree rework (spec: `docs/superpowers/specs/2026-07-06-progression-tree-design.md`).

**Architecture:** Split API acquisition from planning in `GamePlayer` (`plan_once` = acquire + delegate; `plan_from_state` = pure over `self.state`/`self.game_data`). Scenarios build a real-catalog `GameData` from a committed cache bundle (no live API) plus a synthetic `WorldState`; golden tests assert goal-category and first-action-class per scenario; the CLI runs the identical fixtures interactively.

**Tech Stack:** Python 3.13, `uv run pytest`, existing `GameData`/`WorldState`/`PlanReport` types. No new dependencies.

## Global Constraints (from spec + repo rules)

- `uv run` prefixes every Python command.
- No inline imports; imports at top of file. One behavioral class per file.
- Never catch `Exception`; no defaulting over missing game data — fail loud.
- TDD: every new function lands with a failing test first.
- 100% coverage, 0 warnings; full suite green before every commit (pre-commit runs it).
- Goldens assert CATEGORY + FIRST-ACTION-CLASS, never exact scores (spec: goldens must survive the flip).
- Do not touch: arbiter (`select_pure`), DecideKey ladder, guards/means, planner internals.
- Never run `formal/gate.sh`/`mutate.py` while the bot is running.

---

### Task 1: `GameData.from_cache_bundle` — offline real-catalog loader

**Files:**
- Modify: `src/artifactsmmo_cli/ai/game_data.py` (the `load` classmethod region, ~1169-1260)
- Create: `tests/test_ai/scenarios/__init__.py` (empty)
- Create: `tests/test_ai/scenarios/fixtures/gamedata_bundle.json` (copied from the live cache — step 1)
- Test: `tests/test_ai/scenarios/test_gamedata_bundle.py`

**Interfaces:**
- Produces: `GameData.from_cache_bundle(raw: dict[str, Any]) -> GameData` — builds a full GameData from the disk-cache JSON bundle shape (keys: maps, items, resources, monsters, npcs, tasks, events, effects, bank), with an EMPTY Grand-Exchange order book. Later tasks call it via `scenario_game_data()`.

- [ ] **Step 1: Capture the fixture bundle** (bot may be running — this only READS the cache)

```bash
mkdir -p tests/test_ai/scenarios/fixtures
cp ~/.cache/artifactsmmo/gamedata-api.artifactsmmo.com.json \
   tests/test_ai/scenarios/fixtures/gamedata_bundle.json
ls -la tests/test_ai/scenarios/fixtures/gamedata_bundle.json   # ~755KB expected
```

If the cache file is missing, run `uv run artifactsmmo status` once (populates it), then copy.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_ai/scenarios/test_gamedata_bundle.py
"""GameData.from_cache_bundle: the offline real-catalog loader scenarios use.

The committed bundle is a copy of the live disk cache (regen: run any CLI
command to refresh ~/.cache/artifactsmmo/gamedata-*.json, then re-copy —
same drill as formal/sim snapshot regen)."""

import json
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"


def _load() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def test_bundle_builds_real_catalog() -> None:
    gd = _load()
    # Spot-checks against known live facts (stable game data):
    assert gd.crafting_recipe("satchel") == {
        "cowhide": 5, "feather": 2, "jasper_crystal": 1}
    assert gd.monster_level("chicken") == 1
    assert gd.npc_purchases("jasper_crystal") == [("tasks_trader", 8, "tasks_coin")]
    assert gd.bank_location() is not None
    assert gd.taskmaster_location() is not None


def test_bundle_ge_orders_empty() -> None:
    gd = _load()
    assert gd.ge_best_buy_order("copper_ore") is None
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_ai/scenarios/test_gamedata_bundle.py -q --no-cov`
Expected: FAIL — `AttributeError: type object 'GameData' has no attribute 'from_cache_bundle'`

- [ ] **Step 4: Refactor `load` and add the classmethod**

In `game_data.py`, extract the tail of `load` (everything from the
`objs = {...from_dict...}` hydration through the last `_build_*` /
GE-order fetch) so both entries share one build pipeline:

```python
@classmethod
def from_cache_bundle(cls, raw: dict[str, Any]) -> "GameData":
    """Build a full GameData OFFLINE from the disk-cache bundle shape
    (`GameDataCache` JSON: maps/items/resources/monsters/npcs/tasks/
    events/effects/bank). The Grand-Exchange order book is left EMPTY —
    orders are live-only by design; scenario planning treats GE as quiet.
    This is the scenario harness's loader (spec 2026-07-06 progression
    tree, Phase 1): a real catalog with zero API dependency."""
    data = cls()
    data._build_from_objs(cls._hydrate_bundle(raw))
    return data

@staticmethod
def _hydrate_bundle(raw: dict[str, Any]) -> dict[str, Any]:
    """raw JSON bundle -> schema objects (the warm-cache branch of load)."""
    return {
        "maps": [MapSchema.from_dict(d) for d in raw["maps"]],
        "items": [ItemSchema.from_dict(d) for d in raw["items"]],
        "resources": [ResourceSchema.from_dict(d) for d in raw["resources"]],
        "monsters": [MonsterSchema.from_dict(d) for d in raw["monsters"]],
        "npcs": [NPCItemSchema.from_dict(d) for d in raw["npcs"]],
        "tasks": [TaskFullSchema.from_dict(d) for d in raw["tasks"]],
        "events": [EventSchema.from_dict(d) for d in raw["events"]],
        "effects": [EffectSchema.from_dict(d) for d in raw["effects"]],
        "bank": BankSchema.from_dict(raw["bank"]) if raw["bank"] is not None else None,
    }

def _build_from_objs(self, objs: dict[str, Any]) -> None:
    """The shared build pipeline (moved verbatim from `load`'s tail —
    every `_build_*` call in the same order). GE orders NOT fetched here;
    `load` fetches them afterward with its live client."""
    ...  # verbatim move of load's _build_* sequence — no logic changes
```

Then `load` becomes: cache/fetch (unchanged) → `objs = self._hydrate_bundle(raw)` on the warm path (replacing the inline dict) → `data._build_from_objs(objs)` → the existing live GE-order fetch. The engineer moves code; no `_build_*` call may be added, dropped, or reordered.

- [ ] **Step 5: Run the new test + the game_data test files**

Run: `uv run pytest tests/test_ai/scenarios/test_gamedata_bundle.py tests/test_ai/test_game_data*.py -q --no-cov`
Expected: PASS (all)

- [ ] **Step 6: Full suite, then commit**

Run: `uv run pytest -q` — expected: all pass, 100% coverage.

```bash
git add src/artifactsmmo_cli/ai/game_data.py tests/test_ai/scenarios/
git commit -m "feat(scenarios): GameData.from_cache_bundle — offline real-catalog loader"
```

---

### Task 2: `seed_offline` + `plan_from_state` split

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (`plan_once`, ~line 404)
- Test: `tests/test_ai/scenarios/test_plan_from_state.py`

**Interfaces:**
- Consumes: `GameData.from_cache_bundle` (Task 1).
- Produces:
  - `GamePlayer.seed_offline(state: WorldState, game_data: GameData) -> None` — everything `_initialize` does minus API: objective/strategy build, state install, documented-blocker seeding, refresh sentinel.
  - `GamePlayer.plan_from_state(doomed: list[str] | None = None, committed: str | None = None) -> PlanReport` — the CURRENT `plan_once` body from the first assert onward, verbatim; pure over `self.state`/`self.game_data`/`self.history`.
  - `plan_once` = ClientManager acquire + `_initialize` + `_maybe_periodic_refresh` + `return self.plan_from_state(...)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/scenarios/test_plan_from_state.py
"""plan_from_state: the pure planning entry the CLI and scenarios share."""

import json
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.plan_report import PlanReport
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"


def test_plan_from_state_runs_offline() -> None:
    """A seeded player plans a full cycle with NO client and returns a
    populated PlanReport — the seam every scenario golden runs through."""
    gd = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
    player = GamePlayer(character="scenario", history=None)
    state = make_state(level=1, hp=120, max_hp=120,
                       inventory={}, bank_items={}, gold=0)
    player.seed_offline(state, gd)
    report = player.plan_from_state()
    assert isinstance(report, PlanReport)
    assert report.selected_goal  # some goal always selected (WAIT at worst)
    assert report.goals_tried    # the arbiter tried candidates
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/scenarios/test_plan_from_state.py -q --no-cov`
Expected: FAIL — `AttributeError: 'GamePlayer' object has no attribute 'seed_offline'`

- [ ] **Step 3: Implement the split**

In `player.py`:

```python
def seed_offline(self, state: WorldState, game_data: GameData) -> None:
    """Offline seeding for scenario planning (spec 2026-07-06 progression
    tree, Phase 1): everything `_initialize` does EXCEPT the API — no
    game-data fetch, no character fetch, no persistent-blocker load (an
    offline scenario has no learning DB history to honor). Documented
    blockers ARE seeded from game_data so scenario plans see the same
    near-future gates the live bot does."""
    self.game_data = game_data
    self._objective = CharacterObjective.from_game_data(game_data)
    self._strategy = StrategyEngine(self._objective, BalancedPersonality())
    self.state = state
    seed_documented_blockers(self._blockers, game_data, state)
    self._actions_since_full_refresh = BANK_REFRESH_FORCE_SENTINEL
```

Then split `plan_once`: move its body from `assert self.state is not None…`
to the final `return PlanReport(...)` INTO a new method `plan_from_state`
(same signature params `doomed`, `committed`, defaulting to None — keep
the docstring's mirrors-run() paragraph on `plan_from_state`), and leave:

```python
def plan_once(self, doomed: list[str] | None = None,
              committed: str | None = None) -> PlanReport:
    """Sense the world via the API, then compute one planning cycle —
    the `plan <char>` CLI command. Acquisition only; the planning logic
    lives in `plan_from_state` (shared with the offline scenario
    harness)."""
    client = ClientManager().client
    self._initialize(client)
    self._maybe_periodic_refresh(client)
    return self.plan_from_state(doomed=doomed, committed=committed)
```

The move is VERBATIM — no logic edits inside the moved body.

- [ ] **Step 4: Run the new test + existing plan-command/plan-once tests**

Run: `uv run pytest tests/test_ai/scenarios/test_plan_from_state.py tests/test_ai/test_plan_command.py tests/test_ai/test_plan_or_reuse.py -q --no-cov`
Expected: PASS (existing tests exercise `plan_once` via mocks — the split must not change its behavior)

- [ ] **Step 5: Full suite, commit**

Run: `uv run pytest -q` — all pass, 100% coverage.

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/scenarios/test_plan_from_state.py
git commit -m "feat(scenarios): split plan_once into API acquisition + pure plan_from_state"
```

---

### Task 3: `ScenarioCharacter` + named scenario registry

**Files:**
- Create: `src/artifactsmmo_cli/ai/scenario.py`
- Test: `tests/test_ai/scenarios/test_scenario_builder.py`

**Interfaces:**
- Consumes: `GameData.from_cache_bundle` (Task 1).
- Produces (imported by Task 4 goldens and Task 5 CLI):
  - `@dataclass(frozen=True) ScenarioCharacter` — fields:
    `name: str`, `level: int = 1`, `hp: int | None = None` (None → max),
    `max_hp: int = 120`, `gold: int = 0`,
    `skills: dict[str, int] = {}`, `equipment: dict[str, str] = {}`
    (slot→code overlay on all-empty slots),
    `inventory: dict[str, int] = {}`, `inventory_max: int = 100`,
    `bank: dict[str, int] | None = {}` (None = bank state unknown),
    `task: tuple[str, str, int, int] | None = None`
    (code, type, progress, total), `description: str = ""`.
  - `scenario_state(sc: ScenarioCharacter) -> WorldState`
  - `load_bundle_game_data(path: Path) -> GameData` (thin wrapper over
    `from_cache_bundle`, used by tests and CLI with their own paths)
  - `SCENARIOS: dict[str, ScenarioCharacter]` — the named golden set:

| name | character | why it exists |
|---|---|---|
| `l1_fresh` | L1, nothing owned, full HP | trunk start: xp branch, starter monster |
| `l8_overstocked` | L8, inventory 96/100 junk (`feather`×90 + `raw_chicken`×6), copper set equipped | tertiary preempts: deposit guard |
| `l10_copper_adequate` | L10, full copper set + copper tools, empty utility slots, potion mats banked | adequacy → xp branch (post-flip); TODAY: documents the potion-first bug |
| `l10_weapon_upgrade` | L10, copper set BUT weapon slot holds `wooden_stick`, `iron_sword`-class upgrade reachable (ores banked) | gear branch: upgrade chain step |
| `l3_low_hp` | L3, hp 20/80 | guard preempts everything: RestoreHP |
| `l12_taskgated_bag` | L12, cowhide+feather banked, 0 tasks_coin, bag slot empty | task-funding chain: satchel pipeline step |

  (Exact item codes verified against the bundle in the test — if a code
  is absent from the live catalog, the TEST fails loudly; fix the
  scenario, never default.)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/scenarios/test_scenario_builder.py
"""ScenarioCharacter -> WorldState + the named golden registry."""

import json
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.scenario import (
    SCENARIOS,
    ScenarioCharacter,
    scenario_state,
)
from artifactsmmo_cli.ai.world_state import EQUIPMENT_SLOTS

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"


def test_scenario_state_builds_world_state() -> None:
    sc = ScenarioCharacter(name="t", level=5, gold=10,
                           equipment={"weapon_slot": "copper_dagger"},
                           inventory={"feather": 2},
                           task=("chickens", "monsters", 3, 10))
    w = scenario_state(sc)
    assert w.level == 5 and w.gold == 10
    assert w.hp == w.max_hp  # hp None -> full
    assert w.equipment["weapon_slot"] == "copper_dagger"
    assert all(slot in w.equipment for slot in EQUIPMENT_SLOTS)
    assert w.inventory == {"feather": 2}
    assert (w.task_code, w.task_type, w.task_progress, w.task_total) == (
        "chickens", "monsters", 3, 10)


def test_registry_names_are_the_golden_set() -> None:
    assert set(SCENARIOS) >= {
        "l1_fresh", "l8_overstocked", "l10_copper_adequate",
        "l10_weapon_upgrade", "l3_low_hp", "l12_taskgated_bag"}


def test_registry_item_codes_exist_in_live_catalog() -> None:
    """Every item code any scenario references must exist in the bundle —
    scenarios must never drift from the real game."""
    gd = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
    for sc in SCENARIOS.values():
        codes = (set(sc.inventory) | set(sc.bank or {})
                 | set(sc.equipment.values()))
        for code in codes:
            assert gd.item_stats(code) is not None, (sc.name, code)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/scenarios/test_scenario_builder.py -q --no-cov`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.scenario'`

- [ ] **Step 3: Implement `scenario.py`**

```python
# src/artifactsmmo_cli/ai/scenario.py
"""Synthetic planner scenarios: a mock character + the real game catalog.

Phase 1 of the progression-tree spec (docs/superpowers/specs/
2026-07-06-progression-tree-design.md): golden scenario tests and the
`plan --scenario` CLI share these fixtures, so a planner change can be
exercised offline against realistic data before it ever runs live."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.world_state import EQUIPMENT_SLOTS, WorldState


@dataclass(frozen=True)
class ScenarioCharacter:
    """A synthetic character for offline planning. Only game-legal values:
    item codes are validated against the catalog by the scenario tests."""
    name: str
    level: int = 1
    hp: int | None = None          # None -> max_hp
    max_hp: int = 120
    gold: int = 0
    skills: dict[str, int] = field(default_factory=dict)
    equipment: dict[str, str] = field(default_factory=dict)  # slot -> code
    inventory: dict[str, int] = field(default_factory=dict)
    inventory_max: int = 100
    bank: dict[str, int] | None = field(default_factory=dict)  # None = unknown
    task: tuple[str, str, int, int] | None = None  # code, type, progress, total
    description: str = ""


def scenario_state(sc: ScenarioCharacter) -> WorldState:
    equipment: dict[str, str | None] = {slot: None for slot in EQUIPMENT_SLOTS}
    equipment.update(sc.equipment)
    task_code, task_type, progress, total = sc.task or (None, None, 0, 0)
    return WorldState(
        character=sc.name, level=sc.level, xp=0, max_xp=100,
        hp=sc.hp if sc.hp is not None else sc.max_hp, max_hp=sc.max_hp,
        gold=sc.gold, skills=dict(sc.skills), x=0, y=0,
        inventory=dict(sc.inventory), inventory_max=sc.inventory_max,
        equipment=equipment, cooldown_expires=None,
        task_code=task_code, task_type=task_type,
        task_progress=progress, task_total=total,
        task_lifecycle_phase=derive_task_lifecycle_phase(task_code, progress, total),
        bank_items=dict(sc.bank) if sc.bank is not None else None,
        bank_gold=0 if sc.bank is not None else None,
        bank_capacity=200 if sc.bank is not None else None,
        pending_items=None,
    )


def load_bundle_game_data(path: Path) -> GameData:
    return GameData.from_cache_bundle(json.loads(path.read_text()))


_COPPER_SET = {
    "weapon_slot": "copper_dagger", "helmet_slot": "copper_helmet",
    "body_armor_slot": "copper_armor", "leg_armor_slot": "copper_legs_armor",
    "boots_slot": "copper_boots", "ring1_slot": "copper_ring",
    "ring2_slot": "copper_ring",
}

SCENARIOS: dict[str, ScenarioCharacter] = {
    "l1_fresh": ScenarioCharacter(
        name="l1_fresh", level=1, max_hp=120,
        description="Fresh start: nothing owned — trunk begins, xp branch, starter monster."),
    "l8_overstocked": ScenarioCharacter(
        name="l8_overstocked", level=8, max_hp=200,
        skills={"mining": 5, "woodcutting": 5},
        equipment=dict(_COPPER_SET),
        inventory={"feather": 90, "raw_chicken": 6}, inventory_max=100,
        description="96/100 bag of loot — the deposit guard must preempt."),
    "l10_copper_adequate": ScenarioCharacter(
        name="l10_copper_adequate", level=10, max_hp=240,
        skills={"mining": 10, "woodcutting": 10, "weaponcrafting": 10,
                "gearcrafting": 10, "alchemy": 5},
        equipment=dict(_COPPER_SET),
        bank={"sunflower": 20},
        description="Band-adequate copper set, empty utility slots, potion mats banked."),
    "l10_weapon_upgrade": ScenarioCharacter(
        name="l10_weapon_upgrade", level=10, max_hp=240,
        skills={"mining": 10, "weaponcrafting": 10},
        equipment={**_COPPER_SET, "weapon_slot": "wooden_stick"},
        bank={"iron_ore": 60, "copper_ore": 20},
        description="Weapon slot lags a tier; upgrade mats banked — gear branch."),
    "l3_low_hp": ScenarioCharacter(
        name="l3_low_hp", level=3, hp=20, max_hp=80,
        description="Critical HP — the survival guard preempts every branch."),
    "l12_taskgated_bag": ScenarioCharacter(
        name="l12_taskgated_bag", level=12, max_hp=260,
        skills={"gearcrafting": 10},
        equipment=dict(_COPPER_SET),
        bank={"cowhide": 5, "feather": 2},
        description="Satchel mats banked, 0 tasks_coin — the task-funding chain."),
}
```

(If any code here is absent from the live bundle —
`copper_legs_armor` naming etc. — the Task-3 catalog test fails; fix the
scenario code to the real catalog code. Never adjust the test.)

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/scenarios/test_scenario_builder.py -q --no-cov`
Expected: PASS

- [ ] **Step 5: Full suite, commit**

```bash
git add src/artifactsmmo_cli/ai/scenario.py tests/test_ai/scenarios/test_scenario_builder.py
git commit -m "feat(scenarios): ScenarioCharacter builder + named golden registry"
```

---

### Task 4: Golden expectations on the CURRENT engine

**Files:**
- Test: `tests/test_ai/scenarios/test_goldens.py`

**Interfaces:**
- Consumes: Tasks 1-3 (`load_bundle_game_data`, `SCENARIOS`,
  `scenario_state`, `seed_offline`, `plan_from_state`).
- Produces: the golden format later phases fork:
  `EXPECTATIONS: dict[name, Golden(goal_class, first_action_class | None)]`.

- [ ] **Step 1: Write the goldens (they run against the current engine — some are xfail with documented reasons)**

```python
# tests/test_ai/scenarios/test_goldens.py
"""Golden planner expectations per scenario, on the CURRENT engine.

Assertions are CATEGORY-level (goal class + first action class), never
scores — they must survive the progression-tree flip (spec 2026-07-06).
Where the current engine's known misbehavior contradicts the DESIGNED
expectation, the golden is marked xfail with the design intent in the
reason: those xfails are the tree's acceptance tests, flipped in Phase 4."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"


@dataclass(frozen=True)
class Golden:
    goal_class: str                 # PlanReport.selected_goal repr prefix
    first_action: str | None = None # repr prefix of plan[0]; None = don't pin


EXPECTATIONS: dict[str, Golden] = {
    "l1_fresh": Golden(goal_class="GrindCharacterXP", first_action="Fight"),
    "l8_overstocked": Golden(goal_class="DepositInventory", first_action="DepositAll"),
    "l3_low_hp": Golden(goal_class="RestoreHP"),
    "l10_weapon_upgrade": Golden(goal_class="UpgradeEquipment"),
    "l10_copper_adequate": Golden(goal_class="GrindCharacterXP"),
    "l12_taskgated_bag": Golden(goal_class="ReachCurrency"),
}

# Scenarios whose CURRENT-engine outcome is known to differ from the design
# intent (the flat-ranking bugs that motivated the progression tree). The
# golden encodes the DESIGN; xfail documents today's divergence.
XFAIL_TODAY: dict[str, str] = {
    "l10_copper_adequate": (
        "flat ranking picks the empty-utility potion root (EMPTY_SLOT_URGENCY "
        "2.5) over xp — the potion/slime alternation; tree flips this"),
    "l10_weapon_upgrade": (
        "occupied-slot weapon upgrade scores ~1.0 and loses to grind/skill "
        "roots in the flat ranking; tree makes gear-first win pre-adequacy"),
    "l12_taskgated_bag": (
        "bag root may lose the flat ranking to grind roots even though the "
        "funding pipeline is plannable; tree drives it as the gear branch"),
}


def _run(name: str):
    player = GamePlayer(character=name, history=None)
    player.seed_offline(scenario_state(SCENARIOS[name]),
                        load_bundle_game_data(BUNDLE))
    return player.plan_from_state()


@pytest.mark.parametrize("name", sorted(EXPECTATIONS))
def test_scenario_golden(name: str) -> None:
    if name in XFAIL_TODAY:
        pytest.xfail(XFAIL_TODAY[name])
    report = _run(name)
    golden = EXPECTATIONS[name]
    assert report.selected_goal.startswith(golden.goal_class), (
        name, report.selected_goal, [g.get("goal") for g in report.goals_tried])
    if golden.first_action is not None:
        assert report.plan and repr(report.plan[0]).startswith(golden.first_action), (
            name, report.plan)


@pytest.mark.parametrize("name", sorted(EXPECTATIONS))
def test_scenario_planner_never_empty(name: str) -> None:
    """Every scenario must produce SOME selected goal and try candidates —
    an empty arbitration is a liveness bug regardless of which engine runs."""
    report = _run(name)
    assert report.selected_goal
    assert report.goals_tried
```

- [ ] **Step 2: Run and calibrate**

Run: `uv run pytest tests/test_ai/scenarios/test_goldens.py -q --no-cov -rx`

Expected: non-xfail goldens PASS; xfails report xfailed. If a NON-xfail
golden fails, investigate — either the expectation is wrong (fix the
golden with a comment saying why) or you found a live bug (STOP, report
it, do not paper over). If an xfail unexpectedly PASSES (xpass), remove
it from `XFAIL_TODAY` — the engine already meets the design there.

- [ ] **Step 3: Full suite, commit**

```bash
git add tests/test_ai/scenarios/test_goldens.py
git commit -m "test(scenarios): golden planner expectations on the current engine"
```

---

### Task 5: `plan --scenario` CLI

**Files:**
- Modify: `src/artifactsmmo_cli/commands/plan.py` (add option + branch)
- Test: `tests/test_ai/test_plan_command.py` (append)

**Interfaces:**
- Consumes: `SCENARIOS`, `scenario_state`, `load_bundle_game_data`,
  `seed_offline`, `plan_from_state`.
- Produces: `artifactsmmo plan <name-or-any> --scenario <name>` — ignores
  the live API entirely; prints the same report format.
  Bundle path default: `tests/test_ai/scenarios/fixtures/gamedata_bundle.json`
  resolved from the repo root; `--bundle <path>` overrides.

- [ ] **Step 1: Write the failing test (append to `tests/test_ai/test_plan_command.py`)**

```python
def test_plan_command_scenario_runs_offline(capsys):
    """--scenario plans a named synthetic character with no API client:
    no ClientManager, no GamePlayer._initialize."""
    with patch.object(plan_cmd, "check_mutation_lock",
                      return_value=MagicMock(state="clear")):
        # The scenario branch returns BEFORE Config/LearningStore/GamePlayer
        # API setup — patching from_token_file proves no live path ran.
        with patch.object(plan_cmd.Config, "from_token_file") as cfg:
            plan_cmd.plan(character="ignored", learn=False, learn_db=None,
                          refresh_game_data=False, scenario="l1_fresh")
            cfg.assert_not_called()
    out = capsys.readouterr().out
    assert "scenario: l1_fresh" in out
    assert "goals_tried" in out


def test_plan_command_scenario_unknown_name_exits(capsys):
    with patch.object(plan_cmd, "check_mutation_lock",
                      return_value=MagicMock(state="clear")):
        with pytest.raises(typer.Exit):
            plan_cmd.plan(character="ignored", learn=False, learn_db=None,
                          refresh_game_data=False, scenario="nope")
    assert "unknown scenario" in capsys.readouterr().out
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_plan_command.py -q --no-cov -k scenario`
Expected: FAIL — `plan() got an unexpected keyword argument 'scenario'`

- [ ] **Step 3: Implement the option**

In `commands/plan.py`: add Typer options and an early branch before the
Config/LearningStore setup:

```python
scenario: str | None = typer.Option(
    None, "--scenario",
    help="Plan a named synthetic scenario offline (no API). "
         "Names: see artifactsmmo_cli.ai.scenario.SCENARIOS"),
bundle: str | None = typer.Option(
    None, "--bundle", help="GameData cache-bundle JSON for --scenario "
                           "(default: the committed test fixture)"),
```

```python
    if scenario is not None:
        if scenario not in SCENARIOS:
            print(f"unknown scenario '{scenario}'; known: {', '.join(sorted(SCENARIOS))}")
            raise typer.Exit(code=2)
        bundle_path = Path(bundle) if bundle else _DEFAULT_BUNDLE
        player = GamePlayer(character=scenario, history=None)
        player.seed_offline(scenario_state(SCENARIOS[scenario]),
                            load_bundle_game_data(bundle_path))
        print(f"scenario: {scenario} — {SCENARIOS[scenario].description}")
        _print_report(player, player.plan_from_state(doomed=doom, committed=committed))
        return
```

with `_DEFAULT_BUNDLE = Path(__file__).resolve().parents[3] / "tests" / "test_ai" / "scenarios" / "fixtures" / "gamedata_bundle.json"` and top-of-file imports (`from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state`; `from pathlib import Path`).

- [ ] **Step 4: Run tests + manual smoke**

Run: `uv run pytest tests/test_ai/test_plan_command.py -q --no-cov`
Expected: PASS.
Smoke: `uv run artifactsmmo plan x --scenario l1_fresh` — prints a report, no API traffic.

- [ ] **Step 5: Full suite, commit**

```bash
git add src/artifactsmmo_cli/commands/plan.py tests/test_ai/test_plan_command.py
git commit -m "feat(cli): plan --scenario — offline synthetic-character planning"
```

---

### Task 6: Wrap-up — docs pointer + memory + gate

- [ ] **Step 1:** Append a "Phase 1 SHIPPED" line (commits + scenario names) to `docs/superpowers/specs/2026-07-06-progression-tree-design.md` under Phases.
- [ ] **Step 2:** Run the full gate IF the bot is down (`ps aux | grep "[a]rtifactsmmo play"` empty): `./formal/gate.sh`. If the bot is live, note the debt and stop.
- [ ] **Step 3:** Commit docs; update project memory (`project_progression_tree.md`: Phase 1 shipped, commit hashes, xfail list = tree acceptance set).

---

## Later phases (outline only — planned separately after Phase 1 review)

- **Phase 2 — tree module:** `ai/tiers/progression_tree.py` + pure cores
  (`branch_pick_pure`, `gear_target_pick`, potion-type weight table) +
  Lean proofs + unit-bound mutants; scenario tests exercise the module
  directly (not wired into decide()).
- **Phase 3 — shadow:** `decide()` computes both; `tree_decision` trace
  field; divergence report subcommand; `plan --tree`; TUI shadow
  annotation; run live, review divergence per scenario class.
- **Phase 4 — flip + retire:** config flip; delete PRIOR_*/CHAR_GAP_*/
  SKILL_GAP_*/capstone/blend-in-ranking + skill-root generation; rebind
  STRATEGY_MUTATIONS to tree cores; retire StickySelect scoring theorems;
  flip the Phase-1 xfails to hard goldens; TUI descent rendering; full
  gate + push.

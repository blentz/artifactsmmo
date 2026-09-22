# T1.0 Objective Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure what the root walk chooses, what each activity pays per currency per
second, and which character-XP sources are gated behind which skill levels — so the season-9
capstone can be realigned from "level 50" to the leaderboard's ruler against data instead of
against a guess.

**Architecture:** Three censuses over the live learning store and the game catalogue, plus a
frontier report that combines them. One new pure classifier and two new nullable `cycles`
columns give root attribution, which the store cannot currently express: `selected_goal`
records the STEP that ran, so an orphan skill climb and a skill climb demanded by a gear gate
are the same string today. Nothing in this plan changes a ranking, a goal, or a plan.

**Tech Stack:** Python 3.13, `uv`, SQLModel over SQLite, typer for the report command,
pytest.

**Spec:** `docs/PLAN_season9_readiness.md` (track T1)

## Global Constraints

- Every Python command is prefixed `uv run` (e.g. `uv run pytest`, `uv run mypy`).
- All imports at the top of the file. No inline imports.
- Absolute imports only. Never `...`-relative.
- One *behavioural* class per file. Cohesive pure data/value objects may share a module.
- Never `except Exception`. Never `if TYPE_CHECKING`.
- No second implementation of anything — fix in place.
- Tests live in `tests/`. Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- Use only API data, or fail with an error. No defaulting to cover missing game data.
- Durable claims rest on `~/.cache/artifactsmmo/learning.db` only. Play-trace files are
  deleted periodically and must not be a dependency.
- The pre-commit hook runs `pytest tests/test_ai/` only, serially, and takes roughly 30
  minutes. The full gate is `bash formal/gate.sh`, roughly 5 minutes.

## Verified API surface

Every name below was read from the tree on 2026-09-21. Where a task's code uses one, it uses
this spelling.

| Name | Where | Shape |
|---|---|---|
| `ReachCharLevel` | `ai/tiers/meta_goal.py:36` | frozen dataclass, field `level: int` |
| `ObtainItem` | `ai/tiers/meta_goal.py:44` | frozen dataclass, fields `code`, `quantity=1`, `slot=None` |
| `ReachSkillLevel` | `ai/tiers/meta_goal.py:81` | frozen dataclass, fields `skill: str`, `level: int` |
| `StrategyDecision` | `ai/tiers/strategy.py:262` | fields include `interrupt`, `chosen_root`, `blocked_target` |
| `combat_deficit` | `ai/combat_deficit.py:248` | `combat_deficit(state, game_data, monster, candidates=None, max_chain=MAX_CHAIN, actions_of=None)` — **state first, monster third** |
| `CombatDeficit` | `ai/combat_deficit.py:92` | fields `monster`, `baseline_margin`, `chain: tuple[DeficitStep, ...]`, `closes: bool` |
| `DeficitStep` | `ai/combat_deficit.py:67` | fields `code`, `item_type`, `item_level`, `crafting_skill: str \| None`, `crafting_level: int`, `margin_after`, `acquire_cost` |
| `GameData.monster_levels` | `ai/game_data.py:379` | property, `Mapping[str, int]` — this is the monster enumeration |
| `LearningStore.recent_goal_cycles` | `ai/learning/store.py:535` | `(goal_repr, window)` → cycles for that goal **with forced recovery already attributed** |
| `LearningStore.recent_selected_goals` | `ai/learning/store.py:577` | `(window)` → non-None `selected_goal` strings, newest first |
| `default_learn_db_path` | `learning_db_path.py:13` | `() -> str` — **not** `learning_db_path()` |
| cycles column migration | `ai/learning/store.py:158-185` | `PRAGMA table_info(cycles)` then one-shot `ALTER TABLE` |

**Recovery attribution is already production code.** `recent_goal_cycles` reads the raw
stream and calls `attribute_forced_recovery` (`store.py:575`). The census therefore does not
attribute anything itself — it consumes goal-attributed slices. Restating the rule would be a
second implementation of it.

---

## File Structure

**Create:**
- `src/artifactsmmo_cli/ai/tiers/root_group.py` — pure classifier turning a decision's
  `(interrupt, chosen_root, blocked_target)` into one root-group label. Lives in `tiers/`
  because it dispatches on `MetaGoal` subtypes, which `learning/` must not import.
- `src/artifactsmmo_cli/audit/root_group_census.py` — what the walk chose, by group.
- `src/artifactsmmo_cli/audit/currency_rate_census.py` — what each goal paid, per currency
  per second.
- `src/artifactsmmo_cli/audit/xp_gate_census.py` — which character-XP sources are gated
  behind which skill levels.
- `src/artifactsmmo_cli/audit/pareto_frontier.py` — non-dominated activity bundles.
- `src/artifactsmmo_cli/commands/objective_audit_report.py` — `artifactsmmo objective-audit`,
  read-only.
- `tests/test_ai/test_root_group.py`
- `tests/test_ai/test_root_group_census.py`
- `tests/test_ai/test_currency_rate_census.py`
- `tests/test_ai/test_xp_gate_census.py`
- `tests/test_ai/test_pareto_frontier.py`

**Modify:**
- `src/artifactsmmo_cli/ai/learning/models.py` — two nullable columns on `CycleBase`.
- `src/artifactsmmo_cli/ai/learning/store.py` — two `ALTER TABLE` migrations in the block at
  lines 158-185, and one new public reader `recent_cycles`.
- `src/artifactsmmo_cli/ai/player.py:4123` — populate the two new fields.
- `src/artifactsmmo_cli/main.py` — register the report command beside the others near line 60.

---

### Task 1: Root-group classifier

The store cannot distinguish an orphan skill root from a gear-gate skill root, because
`cycles.selected_goal` records the step that ran. This classifier is the missing distinction,
written as a pure function so the census never re-derives it from a repr.

The six groups, and what each means in `ai/decisions/root.py`:

| Group | Meaning |
|---|---|
| `guard` | A guard preempted the walk — `StrategyDecision.interrupt` is set |
| `trunk` | `ReachCharLevel(milestone_pure(state.level))`, the fallback-of-fallbacks |
| `skill_gate` | `ReachSkillLevel` produced because a gear target's crafting skill gate blocked it (`RootWalk.blocked_target` is set) |
| `orphan_skill` | `ReachSkillLevel` from `_orphan_skill_roots` — a skill no gear target can name |
| `gear` | Any other resolved root: the gear branch |
| `none` | The walk resolved to no root (the wall case in `CanIClearMyTier`) |

**Files:**
- Create: `src/artifactsmmo_cli/ai/tiers/root_group.py`
- Test: `tests/test_ai/test_root_group.py`

**Interfaces:**
- Consumes: `MetaGoal`, `ReachCharLevel`, `ReachSkillLevel`, `ObtainItem` from
  `artifactsmmo_cli.ai.tiers.meta_goal`.
- Produces: `root_group_of(interrupt: str | None, chosen_root: MetaGoal | None,
  blocked_target: str | None) -> str`, and `ROOT_GROUPS: frozenset[str]`. Tasks 2 and 4
  depend on both names.

- [ ] **Step 1: Write the failing test**

```python
"""The root-group classifier: which branch of the root walk produced this root."""

import pytest

from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.root_group import ROOT_GROUPS, root_group_of


def test_guard_wins_over_every_root() -> None:
    # A guard preempted the walk, so whatever root was resolved did not run.
    assert root_group_of("HP_CRITICAL", ReachCharLevel(level=30), None) == "guard"


def test_trunk() -> None:
    assert root_group_of(None, ReachCharLevel(level=30), None) == "trunk"


def test_skill_gate_is_a_blocked_gear_target() -> None:
    root = ReachSkillLevel(skill="weaponcrafting", level=15)
    assert root_group_of(None, root, "iron_sword") == "skill_gate"


def test_orphan_skill_has_no_blocked_target() -> None:
    root = ReachSkillLevel(skill="cooking", level=12)
    assert root_group_of(None, root, None) == "orphan_skill"


def test_gear_is_every_other_resolved_root() -> None:
    assert root_group_of(None, ObtainItem(code="copper_boots"), None) == "gear"


def test_no_root_resolved() -> None:
    assert root_group_of(None, None, None) == "none"


@pytest.mark.parametrize("interrupt,root,blocked", [
    ("HP_CRITICAL", None, None),
    (None, ReachCharLevel(level=30), None),
    (None, ReachSkillLevel(skill="cooking", level=2), "x"),
    (None, ReachSkillLevel(skill="cooking", level=2), None),
    (None, ObtainItem(code="copper_boots"), None),
    (None, None, None),
])
def test_every_returned_label_is_declared(interrupt, root, blocked) -> None:
    # The census groups on ROOT_GROUPS; a label outside it would be counted nowhere.
    assert root_group_of(interrupt, root, blocked) in ROOT_GROUPS


def test_the_declared_set_is_exactly_what_is_reachable() -> None:
    reachable = {
        root_group_of("HP_CRITICAL", None, None),
        root_group_of(None, ReachCharLevel(level=30), None),
        root_group_of(None, ReachSkillLevel(skill="cooking", level=2), "x"),
        root_group_of(None, ReachSkillLevel(skill="cooking", level=2), None),
        root_group_of(None, ObtainItem(code="copper_boots"), None),
        root_group_of(None, None, None),
    }
    assert reachable == ROOT_GROUPS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_root_group.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.tiers.root_group'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Which branch of the root walk produced this cycle's root.

`cycles.selected_goal` records the STEP that ran, so it cannot tell an orphan
skill climb from a skill climb a gear target's crafting gate demanded — both
are `ReachSkillLevel(...)`. The root-group census needs that distinction, and
deriving it from a repr would re-encode a decision the walk already made.

The discriminator for the two skill cases is `RootWalk.blocked_target`, which
`decide_tree` copies onto `StrategyDecision.blocked_target`: it is set exactly
when the root is the crafting-skill gate of a named gear target, and is None
for an orphan. See `ai/decisions/root.py`'s `_orphan_skill_roots` for the
orphan rule and `RootWalk.blocked_target` for the gate one.
"""

from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal, ReachCharLevel, ReachSkillLevel

ROOT_GROUPS = frozenset({"guard", "trunk", "skill_gate", "orphan_skill", "gear", "none"})
"""Every label `root_group_of` can return. The census groups on this set, so a
label produced outside it would be counted nowhere."""


def root_group_of(interrupt: str | None, chosen_root: MetaGoal | None,
                  blocked_target: str | None) -> str:
    """The group that produced `chosen_root`, or `guard`/`none`.

    `interrupt` is checked FIRST because a guard preempts the walk: a root may
    have been resolved and then not run, and attributing the cycle to that root
    would credit the walk with a choice the guard overrode.
    """
    if interrupt is not None:
        return "guard"
    if chosen_root is None:
        return "none"
    if isinstance(chosen_root, ReachCharLevel):
        return "trunk"
    if isinstance(chosen_root, ReachSkillLevel):
        return "skill_gate" if blocked_target is not None else "orphan_skill"
    return "gear"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_root_group.py -v`
Expected: PASS, 13 tests (6 named + 6 parametrized + 1)

- [ ] **Step 5: Type-check**

Run: `uv run mypy --strict src/artifactsmmo_cli/ai/tiers/root_group.py`
Expected: `Success: no issues found in 1 source file`

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/root_group.py tests/test_ai/test_root_group.py
git commit -m "feat(audit): classify which root-walk branch produced a root"
```

---

### Task 2: Record root attribution on the cycle row

Two nullable columns written every cycle, plus the public raw-stream reader the group census
needs. Nullable with no default and no back-fill: the rows already in the wild were written
before the walk recorded its group, and inventing one would hand the census a fabricated
observation. Consumers exclude NULL rather than defaulting it — the discipline
`skill_levels_json` and `error_text` already follow.

`LearningStore` has no public raw-cycle reader today. `recent_goal_cycles` filters to one
goal, and the raw `select(Cycle)` at `store.py:564` is inline inside it. The group census
needs every cycle regardless of goal, so this task lifts that read into a public method
rather than issuing a second query from the audit package.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/models.py` (`CycleBase`, after `error_text`)
- Modify: `src/artifactsmmo_cli/ai/learning/store.py` (migration block at 158-185; new reader)
- Modify: `src/artifactsmmo_cli/ai/player.py:4123` (the one `Cycle(` construction site)
- Test: `tests/test_ai/test_root_group_census.py`

**Interfaces:**
- Consumes: `root_group_of` from Task 1.
- Produces: `Cycle.root_group: str | None`, `Cycle.root_repr: str | None`, and
  `LearningStore.recent_cycles(window: int) -> list[Cycle]` (newest first, unfiltered).
  Tasks 4 and 6 read all three.

- [ ] **Step 1: Write the failing migration test**

```python
"""The cycles table gains root attribution, and an old database gains it in place."""

from pathlib import Path

from sqlalchemy import create_engine

from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore


def test_store_migrates_root_group_columns(tmp_path: Path) -> None:
    db = tmp_path / "learning.db"
    # A pre-existing cycles table with neither new column.
    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE cycles (id INTEGER PRIMARY KEY, ts TEXT, session_id TEXT, "
            "cycle_index INTEGER, character TEXT, outcome TEXT)"
        )
    engine.dispose()

    LearningStore(str(db), character="C3P0")

    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(cycles)")}
    engine.dispose()
    assert "root_group" in cols
    assert "root_repr" in cols


def test_recent_cycles_returns_the_raw_stream_newest_first(tmp_path: Path) -> None:
    store = LearningStore(str(tmp_path / "learning.db"), character="C3P0")
    store.start_session()
    for index, group in enumerate(["trunk", "gear"]):
        store.record_cycle(Cycle(
            ts=f"2026-09-21T00:00:0{index}+00:00", session_id="placeholder",
            cycle_index=index, character="C3P0", outcome="ok",
            selected_goal="GrindCharacterXP(green_slime)", root_group=group,
            root_repr=f"Root{index}",
        ))
    rows = store.recent_cycles(window=10)
    # Newest first: the LAST recorded row leads.
    assert [r.root_group for r in rows] == ["gear", "trunk"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_root_group_census.py -v`
Expected: FAIL — `assert 'root_group' in cols`

- [ ] **Step 3: Add the columns to the model**

In `src/artifactsmmo_cli/ai/learning/models.py`, in `CycleBase`, immediately after the
`error_text` field and its docstring:

```python
    root_group: str | None = Field(default=None, index=True)
    """Which branch of the root walk produced this cycle's root — one of
    `tiers/root_group.ROOT_GROUPS`, or None on a row written before this column
    existed (2026-09-21).

    `selected_goal` records the STEP that ran, which cannot tell an orphan skill
    climb from a gear gate's skill climb: both are `ReachSkillLevel(...)`. This
    column is that distinction, recorded by the only component that knows it.

    NULLABLE, NOT BACK-FILLED, like `skill_levels_json` and `error_text`: the
    rows already in the wild were written without a group and inventing one
    would fabricate an observation. Consumers exclude NULL."""

    root_repr: str | None = Field(default=None, index=True)
    """`repr` of the ROOT this cycle's step served, or None on a pre-column row.

    Distinct from `selected_goal`, which is the step. A root of
    `ObtainItem(iron_sword)` and a step of `GatherMaterials(iron_ore)` are the
    normal case, not an anomaly."""
```

- [ ] **Step 4: Add the migration**

In `src/artifactsmmo_cli/ai/learning/store.py`, inside the `exclusive_schema_lock` block,
after the `error_text` migration (line ~185) and before the `craft_yield` block:

```python
            # Root-attribution migration (2026-09-21): cycles gains which branch
            # of the root walk produced the root, and that root's repr. NULLABLE
            # with no DEFAULT — the rows in the wild were written before the walk
            # recorded its group, and back-filling a group would let the T1 audit
            # count a choice nobody observed. A consumer excludes NULL.
            if cols and "root_group" not in cols:
                conn.exec_driver_sql("ALTER TABLE cycles ADD COLUMN root_group TEXT")
            if cols and "root_repr" not in cols:
                conn.exec_driver_sql("ALTER TABLE cycles ADD COLUMN root_repr TEXT")
```

- [ ] **Step 5: Add the public raw-stream reader**

In `src/artifactsmmo_cli/ai/learning/store.py`, beside `recent_goal_cycles` (line 535):

```python
    def recent_cycles(self, window: int) -> list[Cycle]:
        """This character's most recent `window` cycles, newest first, UNFILTERED.

        `recent_goal_cycles` narrows to one goal and attributes forced recovery to
        it; this is the whole stream, which is what a census grouping by root
        branch needs. Same failure discipline as its sibling: a SQLAlchemyError
        returns an empty list rather than a partial one, so a caller cannot mistake
        a broken read for an idle character.
        """
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(Cycle)
                    .where(col(Cycle.character) == self._character)
                    .order_by(col(Cycle.id).desc())
                    .limit(window)
                )
                return list(s.exec(stmt))
        except SQLAlchemyError:
            return []
```

- [ ] **Step 6: Run the migration and reader tests**

Run: `uv run pytest tests/test_ai/test_root_group_census.py -v`
Expected: PASS, 2 tests

- [ ] **Step 7: Populate the columns at the write site**

In `src/artifactsmmo_cli/ai/player.py`, with the other `artifactsmmo_cli.ai.tiers` imports at
the top of the file:

```python
from artifactsmmo_cli.ai.tiers.root_group import root_group_of
```

In the `Cycle(` construction at line ~4123, after the `error_text=` argument:

```python
            root_group=root_group_of(decision.interrupt, decision.chosen_root,
                                     decision.blocked_target),
            root_repr=repr(decision.chosen_root) if decision.chosen_root is not None else None,
```

The local name holding the `StrategyDecision` at that site may not be `decision`. Read the
enclosing method and use the real name. Do not introduce a second variable, and do not thread
a new parameter if the decision is already in scope.

- [ ] **Step 8: Run the player and store suites**

Run: `uv run pytest tests/test_ai/test_root_group_census.py tests/test_ai/test_learning_store.py -v`
Expected: PASS

Run: `uv run mypy --strict src/artifactsmmo_cli/ai/learning/store.py src/artifactsmmo_cli/ai/player.py`
Expected: `Success: no issues found in 2 source files`

- [ ] **Step 9: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/models.py src/artifactsmmo_cli/ai/learning/store.py \
        src/artifactsmmo_cli/ai/player.py tests/test_ai/test_root_group_census.py
git commit -m "feat(audit): record which root-walk branch chose each cycle's root"
```

---

### Task 3: Currency-rate census

What each goal actually paid, per currency, per second. The currencies are character XP,
per-skill XP, and gold; seconds are the shared denominator.

**The denominator is the whole point, and it is already solved in production.** The arbiter
files the Rests a grind forces under `RestoreHP`, a different goal. Measured on 36,455 live
cycles, `GrindCharacterXP(green_slime)` is 100% `FightAction` with 0% Rest while `RestoreHP`
holds 5,668 Rests. A census that grouped the raw stream by `selected_goal` would report XP
per FIGHT and call it XP per loop action — about 2.4x too high, a defect this branch has had
before at ~29x. `LearningStore.recent_goal_cycles` already attributes recovery through
`attribute_forced_recovery` (`store.py:575`), so this census consumes goal-attributed slices
and restates nothing.

That makes `currency_rates` pure: it takes the slices, it does not fetch them.

**Files:**
- Create: `src/artifactsmmo_cli/audit/currency_rate_census.py`
- Test: `tests/test_ai/test_currency_rate_census.py`

**Interfaces:**
- Consumes: `Cycle` from `artifactsmmo_cli.ai.learning.models`.
- Produces: `GoalRates` (frozen dataclass: `goal`, `cycles`, `seconds`, `char_xp`,
  `skill_xp: dict[str, int]`, `gold`; properties `char_xp_per_second`, `skill_xp_per_second`,
  `gold_per_second`) and
  `currency_rates(cycles_by_goal: dict[str, list[Cycle]]) -> list[GoalRates]`. Task 6 reads
  both.

- [ ] **Step 1: Write the failing test**

```python
"""Per-goal currency rates over goal-attributed cycle slices."""

from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.audit.currency_rate_census import GoalRates, currency_rates


def _cycle(seconds: float | None, char_xp: int, skill_json: str = "{}",
           gold: int = 0) -> Cycle:
    return Cycle(
        ts="2026-09-21T00:00:00+00:00", session_id="s", cycle_index=0,
        character="C3P0", outcome="ok", selected_goal="g",
        actual_cooldown_seconds=seconds, delta_xp=char_xp,
        delta_skill_xp_json=skill_json, delta_gold=gold,
    )


def test_rates_are_totals_over_measured_seconds() -> None:
    # The caller passes the slice recent_goal_cycles returned, which already
    # includes the Rests this goal's fighting forced: 10s fighting + 20s resting.
    rows = currency_rates({"Grind": [_cycle(10.0, 30), _cycle(20.0, 0)]})
    assert rows[0].seconds == 30.0
    assert rows[0].char_xp == 30
    assert rows[0].char_xp_per_second == 1.0


def test_skill_xp_is_summed_per_skill() -> None:
    rows = currency_rates({"Cook": [
        _cycle(5.0, 0, '{"cooking": 12}'),
        _cycle(5.0, 0, '{"cooking": 8, "fishing": 3}'),
    ]})
    assert rows[0].skill_xp == {"cooking": 20, "fishing": 3}
    assert rows[0].skill_xp_per_second == 2.3


def test_a_cycle_with_no_measured_cooldown_is_excluded_not_defaulted() -> None:
    # actual_cooldown_seconds is None when the server reported none. Denominating
    # on a fabricated 0 would make the rate infinite and rank it first.
    assert currency_rates({"Grind": [_cycle(None, 30)]}) == []


def test_a_goal_with_only_unmeasured_cycles_is_dropped_not_zeroed() -> None:
    rows = currency_rates({"Measured": [_cycle(10.0, 10)], "Unmeasured": [_cycle(None, 99)]})
    assert [r.goal for r in rows] == ["Measured"]


def test_ordered_by_char_xp_per_second_descending() -> None:
    rows = currency_rates({"Slow": [_cycle(100.0, 10)], "Fast": [_cycle(10.0, 100)]})
    assert [r.goal for r in rows] == ["Fast", "Slow"]


def test_gold_per_second() -> None:
    rows = currency_rates({"Sell": [_cycle(10.0, 0, "{}", 500)]})
    assert rows[0].gold_per_second == 50.0


def test_goal_rates_is_a_value_object() -> None:
    rates = GoalRates(goal="g", cycles=1, seconds=2.0, char_xp=4,
                      skill_xp={"cooking": 2}, gold=6)
    assert rates.char_xp_per_second == 2.0
    assert rates.skill_xp_per_second == 1.0
    assert rates.gold_per_second == 3.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_currency_rate_census.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.audit.currency_rate_census'`

- [ ] **Step 3: Write the implementation**

```python
"""What each goal actually paid, per currency, per second.

THE DENOMINATOR IS THE WHOLE POINT, and production already solves it. The
arbiter files the Rests a grind forces under `RestoreHP` because it preempts the
grind to take them; measured on 36,455 live cycles, `GrindCharacterXP(green_slime)`
is 100% FightAction with 0% Rest while `RestoreHP` holds 5,668 Rests. Grouping
the raw stream by `selected_goal` would report XP per FIGHT and call it XP per
loop action — about 2.4x too high, a defect this branch has had before at ~29x.

`LearningStore.recent_goal_cycles` already attributes forced recovery to the goal
that caused it (`store.py:575`). This census consumes the slices it returns, so
the attribution rule has exactly one implementation and this is not it.

A cycle whose `actual_cooldown_seconds` is None is EXCLUDED. The server did not
report a cooldown for it, and denominating a rate on a fabricated zero produces
an infinite rate — the census would then rank an unmeasured goal first.
"""

import json
from dataclasses import dataclass, field

from artifactsmmo_cli.ai.learning.models import Cycle


@dataclass(frozen=True)
class GoalRates:
    """One goal's measured totals over the window, and the rates derived from them."""

    goal: str
    cycles: int
    seconds: float
    char_xp: int
    skill_xp: dict[str, int] = field(default_factory=dict)
    gold: int = 0

    @property
    def char_xp_per_second(self) -> float:
        """Character XP per second. `seconds` is positive by construction: a
        goal with no measured cycle never becomes a row."""
        return self.char_xp / self.seconds

    @property
    def skill_xp_per_second(self) -> float:
        """All skill XP per second, summed across skills. Under the character
        leaderboard's `total_xp` ruler one point of skill XP and one point of
        character XP weigh the same, so they are summed, not weighted."""
        return sum(self.skill_xp.values()) / self.seconds

    @property
    def gold_per_second(self) -> float:
        """Gold per second. Carried because `cycles` already records it and the
        frontier needs a third axis to be a frontier rather than a line."""
        return self.gold / self.seconds


def currency_rates(cycles_by_goal: dict[str, list[Cycle]]) -> list[GoalRates]:
    """Per-goal currency totals, ordered by character XP per second, descending.

    Each value is the slice `LearningStore.recent_goal_cycles` returned for that
    goal — already carrying the recovery cycles the goal's own fighting forced.
    A goal whose every cycle lacks a measured cooldown is DROPPED, not reported
    as zero: "not measured" and "measured as nothing" are different findings.
    """
    rows: list[GoalRates] = []
    for goal, cycles in cycles_by_goal.items():
        measured = [c for c in cycles if c.actual_cooldown_seconds is not None]
        seconds = sum(c.actual_cooldown_seconds or 0.0 for c in measured)
        if seconds <= 0.0:
            continue
        skill_xp: dict[str, int] = {}
        for cycle in measured:
            for skill, gained in json.loads(cycle.delta_skill_xp_json).items():
                skill_xp[skill] = skill_xp.get(skill, 0) + gained
        rows.append(GoalRates(
            goal=goal,
            cycles=len(measured),
            seconds=seconds,
            char_xp=sum(c.delta_xp or 0 for c in measured),
            skill_xp=skill_xp,
            gold=sum(c.delta_gold or 0 for c in measured),
        ))
    rows.sort(key=lambda r: r.char_xp_per_second, reverse=True)
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_currency_rate_census.py -v`
Expected: PASS, 7 tests

- [ ] **Step 5: Verify against the live store**

Run:
```bash
uv run python -c "
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.learning_db_path import default_learn_db_path
from artifactsmmo_cli.audit.currency_rate_census import currency_rates
store = LearningStore(default_learn_db_path(), character='C3P0')
goals = set(store.recent_selected_goals(5000))
slices = {g: store.recent_goal_cycles(g, 5000) for g in goals}
for r in currency_rates(slices)[:10]:
    print(f'{r.goal:<45} {r.cycles:>6} cyc {r.char_xp_per_second:>8.4f} char-xp/s {r.skill_xp_per_second:>8.4f} skill-xp/s')
"
```
Expected: real goals with non-zero rates.

**This step is the point of the task.** A green test proves the arithmetic; only this proves
the census sees the fleet's actual history.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/audit/currency_rate_census.py tests/test_ai/test_currency_rate_census.py
git commit -m "feat(audit): measure per-goal currency rates from attributed slices"
```

---

### Task 4: Root-group census

What the walk chose, by group, per character. Reads Task 2's column and reports only rows
that carry it — a NULL `root_group` is a row written before the column existed, not a choice,
and counting it as one would put pre-migration history into a post-migration verdict.

**Files:**
- Create: `src/artifactsmmo_cli/audit/root_group_census.py`
- Test: `tests/test_ai/test_root_group_census.py` (append; the file exists from Task 2)

**Interfaces:**
- Consumes: `ROOT_GROUPS` from `artifactsmmo_cli.ai.tiers.root_group`, `Cycle`.
- Produces: `GroupCounts` (frozen dataclass: `character`, `counts: dict[str, int]`,
  `attributed`, `unattributed`; method `share(group) -> float`) and
  `root_group_counts(cycles: list[Cycle]) -> list[GroupCounts]`. Task 6 reads both.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ai/test_root_group_census.py`:

```python
import pytest

from artifactsmmo_cli.audit.root_group_census import GroupCounts, root_group_counts


def _grouped(character: str, group: str | None) -> Cycle:
    return Cycle(
        ts="2026-09-21T00:00:00+00:00", session_id="s", cycle_index=0,
        character=character, outcome="ok", root_group=group,
    )


def test_counts_by_group_per_character() -> None:
    rows = root_group_counts([
        _grouped("C3P0", "trunk"), _grouped("C3P0", "trunk"), _grouped("C3P0", "gear"),
        _grouped("R2D2", "orphan_skill"),
    ])
    by_char = {r.character: r for r in rows}
    assert by_char["C3P0"].counts == {"trunk": 2, "gear": 1}
    assert by_char["R2D2"].counts == {"orphan_skill": 1}


def test_pre_migration_rows_are_reported_as_unattributed_not_counted() -> None:
    rows = root_group_counts([_grouped("C3P0", "trunk"), _grouped("C3P0", None)])
    assert rows[0].attributed == 1
    assert rows[0].unattributed == 1
    assert rows[0].counts == {"trunk": 1}


def test_an_unknown_group_label_raises() -> None:
    # A label outside ROOT_GROUPS means the classifier and the census have
    # drifted. Counting it nowhere would hide that silently.
    with pytest.raises(ValueError, match="unknown root group"):
        root_group_counts([_grouped("C3P0", "made_up")])


def test_characters_are_ordered_by_name() -> None:
    rows = root_group_counts([_grouped("R2D2", "gear"), _grouped("C3P0", "gear")])
    assert [r.character for r in rows] == ["C3P0", "R2D2"]


def test_share_is_denominated_on_attributed_rows_only() -> None:
    counts = GroupCounts(character="C3P0", counts={"trunk": 1}, attributed=1, unattributed=9)
    assert counts.share("trunk") == 1.0
    assert counts.share("gear") == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_root_group_census.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.audit.root_group_census'`

- [ ] **Step 3: Write the implementation**

```python
"""What the root walk actually chose, by branch, per character.

The question T1 cannot answer without this: under the character leaderboard's
`total_xp` ruler, skill XP and character XP weigh the same, yet skills sit
BEHIND the trunk in `resolve_root`'s fixed concatenation of alternatives.
Whether that ordering costs anything is a measurement, and this is it.

A NULL `root_group` is a row written before the column existed (2026-09-21). It
is reported as `unattributed` and counted in no group: treating it as a choice
would let pre-migration history decide a post-migration verdict.
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.tiers.root_group import ROOT_GROUPS


@dataclass(frozen=True)
class GroupCounts:
    """One character's root choices over the window."""

    character: str
    counts: dict[str, int]
    attributed: int
    unattributed: int

    def share(self, group: str) -> float:
        """Fraction of ATTRIBUTED cycles that chose `group`. Denominated on
        attributed rows only, so a store that is mostly pre-migration reports a
        share of what it saw rather than one diluted by silence."""
        return self.counts.get(group, 0) / self.attributed


def root_group_counts(cycles: list[Cycle]) -> list[GroupCounts]:
    """Per-character group counts, ordered by character name.

    Raises `ValueError` on a group label outside `ROOT_GROUPS`: that means the
    classifier and this census have drifted, and a census that silently dropped
    the label would report a smaller world than the one that was recorded.
    """
    per_char: dict[str, dict[str, int]] = {}
    unattributed: dict[str, int] = {}
    for cycle in cycles:
        counts = per_char.setdefault(cycle.character, {})
        unattributed.setdefault(cycle.character, 0)
        if cycle.root_group is None:
            unattributed[cycle.character] += 1
            continue
        if cycle.root_group not in ROOT_GROUPS:
            raise ValueError(f"unknown root group: {cycle.root_group!r}")
        counts[cycle.root_group] = counts.get(cycle.root_group, 0) + 1
    return [
        GroupCounts(
            character=character,
            counts=counts,
            attributed=sum(counts.values()),
            unattributed=unattributed[character],
        )
        for character, counts in sorted(per_char.items())
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_root_group_census.py -v`
Expected: PASS, 7 tests (2 from Task 2, 5 here)

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/audit/root_group_census.py tests/test_ai/test_root_group_census.py
git commit -m "feat(audit): count root-walk choices by branch, per character"
```

---

### Task 5: XP-gate census

Which character-XP sources a character cannot reach, and which skill level gates each. This
is the "secondary currency" half of the model: character XP comes from fights, fights need
gear, and gear needs crafting skill levels.

**`combat_deficit` already computes the whole chain, gate included.** `DeficitStep` carries
`crafting_skill` and `crafting_level` precisely because "the gear layer is not the bottom of
the chain" — C3P0 could not craft `iron_sword` at weaponcrafting 6 however many `iron_bar` it
held. So this census reads the existing oracle rather than re-deriving recipes.

**Files:**
- Create: `src/artifactsmmo_cli/audit/xp_gate_census.py`
- Test: `tests/test_ai/test_xp_gate_census.py`

**Interfaces:**
- Consumes: `combat_deficit` from `artifactsmmo_cli.ai.combat_deficit` — signature
  `combat_deficit(state, game_data, monster, ...)`, **state first, monster third**;
  `CombatDeficit.chain` of `DeficitStep`, `CombatDeficit.closes`;
  `GameData.monster_levels` (a `Mapping[str, int]`); `WorldState.skills`.
- Produces: `GatedSource` (frozen dataclass: `monster`, `monster_level`, `blocking_item`,
  `item_type`, `skill`, `required_level`, `held_level`; property `gap`) and
  `gated_xp_sources(state: WorldState, game_data: GameData) -> list[GatedSource]`. Task 6
  reads both.

- [ ] **Step 1: Write the failing test**

```python
"""Which character-XP sources are walled behind which skill levels."""

from artifactsmmo_cli.audit.xp_gate_census import GatedSource, gated_xp_sources


def test_gap_is_levels_between_held_and_required() -> None:
    source = GatedSource(monster="wolf", monster_level=15, blocking_item="iron_sword",
                         item_type="weapon", skill="weaponcrafting",
                         required_level=20, held_level=6)
    assert source.gap == 14


def test_a_winnable_monster_is_not_a_gated_source(gate_state, gate_game_data) -> None:
    # green_slime is beatable with what the character wears now, so combat_deficit
    # returns None for it and it is already a live XP source.
    sources = gated_xp_sources(gate_state, gate_game_data)
    assert "green_slime" not in {s.monster for s in sources}


def test_an_unwinnable_monster_names_the_skill_that_gates_its_upgrade(
        gate_state, gate_game_data) -> None:
    sources = {s.monster: s for s in gated_xp_sources(gate_state, gate_game_data)}
    wolf = sources["wolf"]
    assert wolf.item_type == "weapon"
    assert wolf.skill == "weaponcrafting"
    assert wolf.required_level > wolf.held_level


def test_a_step_the_character_can_already_craft_is_not_a_gate(
        gate_state, gate_game_data) -> None:
    # A chain step whose crafting level is already held is not a wall; reporting
    # it would put an open gate in a list of closed ones.
    sources = gated_xp_sources(gate_state, gate_game_data)
    assert all(s.required_level > s.held_level for s in sources)


def test_nearest_gate_first(gate_state, gate_game_data) -> None:
    gaps = [s.gap for s in gated_xp_sources(gate_state, gate_game_data)]
    assert gaps == sorted(gaps)
```

The `gate_state` and `gate_game_data` fixtures must build a world where `green_slime` is
winnable and `wolf` is not, `wolf`'s closing chain step is a weaponcrafting item above the
character's weaponcrafting level, and at least one chain step is already craftable.
**Declare that world in this test module's own fixtures.** Do not reuse a shared `GameData`
fixture: one shared world across scenarios has already produced three vacuous measurements
and a shipped false retraction in this codebase.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_xp_gate_census.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.audit.xp_gate_census'`

- [ ] **Step 3: Write the implementation**

```python
"""Which character-XP sources are unreachable, and which skill level gates each.

Character XP is the primary currency and fights are its source, but a fight the
character cannot win pays nothing. Closing that fight needs gear, and the gear
needs a crafting skill level — the secondary currency T1 has to price. This
census names that chain for every monster the character cannot beat.

It reads `combat_deficit`, which already computes the chain WITH its gate:
`DeficitStep` carries `crafting_skill` and `crafting_level` because "the gear
layer is not the bottom of the chain" (C3P0 could not craft `iron_sword` at
weaponcrafting 6 however many `iron_bar` it held). Re-deriving recipes here
would be a second implementation of a question production already answers, and
the two would drift.
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.combat_deficit import combat_deficit
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass(frozen=True)
class GatedSource:
    """One unreachable character-XP source and the skill level that gates it."""

    monster: str
    monster_level: int
    blocking_item: str
    item_type: str
    skill: str
    required_level: int
    held_level: int

    @property
    def gap(self) -> int:
        """Skill levels between what the character holds and what the gate asks.
        The census orders on this: the nearest gate is the cheapest to open."""
        return self.required_level - self.held_level


def gated_xp_sources(state: WorldState, game_data: GameData) -> list[GatedSource]:
    """Every monster this character cannot beat, with the crafting skill and level
    gating each chain step it cannot yet make, nearest gate first.

    A monster with no deficit is not returned: it is already a live XP source.
    A deficit whose `closes` is False is not returned either — nothing in the
    catalogue closes that fight, so it is a drop or spawn wall, not a skill gate,
    and naming it here would put an unopenable gate in a list of openable ones.
    A chain step with no crafting gate, or one whose level the character already
    holds, is not a wall and is skipped.
    """
    rows: list[GatedSource] = []
    for monster, monster_level in game_data.monster_levels.items():
        deficit = combat_deficit(state, game_data, monster)
        if deficit is None or not deficit.closes:
            continue
        for step in deficit.chain:
            if step.crafting_skill is None:
                continue
            held = state.skills.get(step.crafting_skill, 0)
            if held >= step.crafting_level:
                continue
            rows.append(GatedSource(
                monster=monster,
                monster_level=monster_level,
                blocking_item=step.code,
                item_type=step.item_type,
                skill=step.crafting_skill,
                required_level=step.crafting_level,
                held_level=held,
            ))
    rows.sort(key=lambda s: (s.gap, s.monster, s.blocking_item))
    return rows
```

- [ ] **Step 4: Run test and type-check**

Run: `uv run pytest tests/test_ai/test_xp_gate_census.py -v`
Expected: PASS, 5 tests

Run: `uv run mypy --strict src/artifactsmmo_cli/audit/xp_gate_census.py`
Expected: `Success: no issues found in 1 source file`

- [ ] **Step 5: Cross-check against the live oracle**

Run: `uv run artifactsmmo combat-deficit C3P0`

Then confirm that a monster the command reports with a chain also appears in
`gated_xp_sources` with the same blocking item. Two oracles disagreeing about the same fight
is the finding, not a nuisance — `combat-deficit` and this census read the same function, so
a disagreement means one of them is passing different arguments.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/audit/xp_gate_census.py tests/test_ai/test_xp_gate_census.py
git commit -m "feat(audit): name the skill gate behind each unreachable xp source"
```

---

### Task 6: Pareto frontier and the report command

Combine the three censuses and print them. The frontier is a *report*. It has no production
consumer, and adding one is the T1 design decision, made against this output — not here.

A bundle is one goal's measured behaviour over the window. It is dominated when another
bundle is at least as good on every currency and strictly better on one. The currencies are
character XP per second, skill XP per second, and gold per second. Seconds are the shared
denominator, so they are not a fourth axis.

**Files:**
- Create: `src/artifactsmmo_cli/audit/pareto_frontier.py`
- Create: `src/artifactsmmo_cli/commands/objective_audit_report.py`
- Modify: `src/artifactsmmo_cli/main.py`
- Test: `tests/test_ai/test_pareto_frontier.py`

**Interfaces:**
- Consumes: `GoalRates` (Task 3), `GroupCounts` / `root_group_counts` (Task 4),
  `GatedSource` / `gated_xp_sources` (Task 5), `LearningStore.recent_cycles` /
  `recent_selected_goals` / `recent_goal_cycles`, `default_learn_db_path`.
- Produces: `frontier(rows: list[GoalRates]) -> list[GoalRates]` and
  `objective_audit_command`.

- [ ] **Step 1: Write the failing test**

```python
"""The non-dominated set over the measured currencies."""

from artifactsmmo_cli.audit.currency_rate_census import GoalRates
from artifactsmmo_cli.audit.pareto_frontier import frontier


def _rates(goal: str, char_xp: int, skill_xp: int, gold: int) -> GoalRates:
    # One second of activity, so the totals ARE the rates.
    return GoalRates(goal=goal, cycles=1, seconds=1.0, char_xp=char_xp,
                     skill_xp={"cooking": skill_xp}, gold=gold)


def test_a_strictly_worse_bundle_is_dominated() -> None:
    best = _rates("best", 10, 10, 10)
    worse = _rates("worse", 1, 1, 1)
    assert frontier([best, worse]) == [best]


def test_a_bundle_that_wins_on_one_currency_survives() -> None:
    # Fewer char xp, but far more skill xp — under total_xp both count.
    fighter = _rates("fighter", 10, 0, 0)
    cook = _rates("cook", 0, 10, 0)
    assert [r.goal for r in frontier([fighter, cook])] == ["fighter", "cook"]


def test_an_equal_bundle_does_not_dominate() -> None:
    # Domination requires strictly better on at least one currency, so two
    # identical bundles both survive rather than one eliminating the other.
    a = _rates("a", 5, 5, 5)
    b = _rates("b", 5, 5, 5)
    assert [r.goal for r in frontier([a, b])] == ["a", "b"]


def test_gold_is_a_real_axis() -> None:
    # Loses on both xp axes, wins on gold: still on the frontier.
    grinder = _rates("grinder", 10, 10, 0)
    seller = _rates("seller", 0, 0, 10)
    assert [r.goal for r in frontier([grinder, seller])] == ["grinder", "seller"]


def test_empty_input_is_an_empty_frontier() -> None:
    assert frontier([]) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_pareto_frontier.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.audit.pareto_frontier'`

- [ ] **Step 3: Write the frontier**

```python
"""The non-dominated set of measured activity bundles.

The season-9 objective is multi-variate: character XP is primary, but access to
it is gated behind skill XP, and skill XP is gated behind currencies whose
actions differ in efficiency. A scalar would need weights nobody has measured,
and inventing them is exactly the epicycle this audit exists to avoid. The
frontier needs no weights — it reports which bundles are not beaten outright,
and the design decision is made against that set.

Seconds are the shared denominator, not a fourth axis: every currency here is
already per second.
"""

from artifactsmmo_cli.audit.currency_rate_census import GoalRates


def _axes(rates: GoalRates) -> tuple[float, float, float]:
    return (rates.char_xp_per_second, rates.skill_xp_per_second, rates.gold_per_second)


def _dominates(a: GoalRates, b: GoalRates) -> bool:
    """True when `a` is at least as good as `b` on every currency and strictly
    better on at least one. Equality does not dominate, so two identical bundles
    both survive rather than one silently eliminating the other."""
    left, right = _axes(a), _axes(b)
    return all(x >= y for x, y in zip(left, right, strict=True)) and left != right


def frontier(rows: list[GoalRates]) -> list[GoalRates]:
    """The bundles no other bundle dominates, in the order given."""
    return [a for a in rows if not any(_dominates(b, a) for b in rows if b is not a)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_pareto_frontier.py -v`
Expected: PASS, 5 tests

- [ ] **Step 5: Write the report command**

Create `src/artifactsmmo_cli/commands/objective_audit_report.py`. Before writing it, read
`src/artifactsmmo_cli/commands/combat_deficit_report.py` and mirror its real construction
sequence for config, client, player and state — that file is the working precedent for a
read-only diagnostic that must not write session rows into the fleet's database. The body
below is the content; the setup lines follow that file.

```python
"""`artifactsmmo objective-audit` — read-only: what the walk chose, what it paid,
and what it cannot reach.

The oracle for T1. The season-9 capstone moves from "level 50" to the character
leaderboard's `total_xp`, and this command is how the shape of that change gets
decided against measurement rather than a guess — the same role `combat-deficit`
plays for the combat-deficit work.

Four sections: the root-group census (what the walk chose), the currency-rate
census (what each goal paid, over slices that already carry the recovery its
fighting forced), the Pareto frontier over those bundles, and the gated-source
census (which XP sources are walled behind which skill level).

Read-only: senses state, computes, prints. No actions.
"""

import typer

from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.audit.currency_rate_census import currency_rates
from artifactsmmo_cli.audit.pareto_frontier import frontier
from artifactsmmo_cli.audit.root_group_census import root_group_counts
from artifactsmmo_cli.audit.xp_gate_census import gated_xp_sources
from artifactsmmo_cli.learning_db_path import default_learn_db_path


def objective_audit_command(
    character: str = typer.Argument(..., help="Character to audit"),
    window: int = typer.Option(5000, help="Cycles of history to read"),
) -> None:
    """Print the T1 objective audit for one character."""
    store = LearningStore(default_learn_db_path(), character=character)

    cycles = store.recent_cycles(window)
    print(f"== root groups ({character}, {len(cycles)} cycles) ==")
    for counts in root_group_counts(cycles):
        if counts.attributed == 0:
            print(f"{counts.character}: 0 attributed, {counts.unattributed} pre-migration")
            continue
        shares = " ".join(
            f"{group}={counts.counts[group]} ({counts.share(group):.1%})"
            for group in sorted(counts.counts))
        print(f"{counts.character}: {shares} · {counts.unattributed} pre-migration")

    goals = set(store.recent_selected_goals(window))
    rates = currency_rates({g: store.recent_goal_cycles(g, window) for g in goals})
    print("\n== currency rates ==")
    for row in rates:
        print(f"{row.goal:<45} {row.cycles:>6} cyc "
              f"{row.char_xp_per_second:>8.4f} char-xp/s "
              f"{row.skill_xp_per_second:>8.4f} skill-xp/s "
              f"{row.gold_per_second:>8.2f} gold/s")

    print("\n== pareto frontier ==")
    for row in frontier(rates):
        print(f"{row.goal:<45} {row.char_xp_per_second:>8.4f} char-xp/s "
              f"{row.skill_xp_per_second:>8.4f} skill-xp/s "
              f"{row.gold_per_second:>8.2f} gold/s")

    # Live state: same construction sequence as commands/combat_deficit_report.py.
    state, game_data = _sense(character)
    print("\n== gated xp sources (nearest gate first) ==")
    for source in gated_xp_sources(state, game_data)[:20]:
        print(f"{source.monster:<20} lvl {source.monster_level:>2} "
              f"blocked by {source.blocking_item} ({source.item_type}) · "
              f"{source.skill} {source.held_level}->{source.required_level} "
              f"(gap {source.gap})")
```

Write `_sense(character) -> tuple[WorldState, GameData]` in this same module, using
`combat_deficit_report.py`'s own config/client/player lines. One helper, not a new class —
this module has no behavioural class of its own.

- [ ] **Step 6: Register the command**

In `src/artifactsmmo_cli/main.py`, with the other command imports near line 14:

```python
from artifactsmmo_cli.commands.objective_audit_report import objective_audit_command
```

and with the other `app.command(...)` registrations near line 60:

```python
app.command("objective-audit",
            help="Read-only: what the root walk chose, what it paid, what it cannot reach")(
    objective_audit_command)
```

- [ ] **Step 7: Run it against the live fleet**

Run: `uv run artifactsmmo objective-audit C3P0`

Expected: four sections with real numbers. The root-group section will report mostly
`pre-migration` until the fleet has run under Task 2's columns — that is correct, and it is
why the section prints the count rather than hiding it.

- [ ] **Step 8: Run the full gate**

Run: `bash formal/gate.sh > /tmp/gate.log 2>&1; echo "exit=$?"`

Expected: `exit=0`. Do not pipe the gate into `tail` — a pipeline reports the tail's exit
code, not the gate's.

Two live-API audit tests fail with `HTTP 429` whenever `play --all` is running. They pass
standalone. That is not a regression from this plan.

- [ ] **Step 9: Commit**

```bash
git add src/artifactsmmo_cli/audit/pareto_frontier.py \
        src/artifactsmmo_cli/commands/objective_audit_report.py \
        src/artifactsmmo_cli/main.py tests/test_ai/test_pareto_frontier.py
git commit -m "feat(audit): objective-audit report over groups, rates and gates"
```

---

## What this plan deliberately does not do

- It changes no ranking, no goal, no plan, and no cost. `milestone_pure`'s `TRUNK_CAP = 50`
  and the orphan-behind-trunk ordering in `resolve_root` are untouched.
- It adds no weights between currencies. The frontier needs none, and inventing them is the
  epicycle this audit exists to avoid.
- It writes no second implementation of recovery attribution, of the combat deficit chain, or
  of the crafting gate. Each is read from the one place production already computes it.
- It does not decide T1's shape. That decision is made against this output, in its own
  brainstorm.

## Findings to record when the audit runs

Record all of these, including the runs that find nothing — a counter that only counts the
runs which found something reports a rate nobody measured.

1. Group shares per character over a post-migration window. A large `orphan_skill` share
   means skills sitting structurally behind the trunk is costing measurable XP.
2. The frontier's membership. If one bundle dominates everything, the objective is closer to
   a scalar than the currency model suggests and T1 gets much smaller.
3. Whether any goal's measured rate moves by roughly 2x between `recent_goal_cycles` and a
   naive `where selected_goal = ?` query. That difference is the recovery-attribution defect
   this branch has had twice; if it is absent, say so rather than assuming it held.
4. How many gated sources share one skill. A single skill gating many XP sources is the
   strongest argument for promoting skills out of orphan status.

---

## Fix wave (post-review) — this plan's code snippets are now HISTORY

The whole-branch review found eight defects in the shipped implementation; they are listed
with file:line in `.superpowers/sdd/PLAN_season9_t1_objective_audit/final-findings.md` and
the fixes are recorded in `final-fix-report.md` beside it. Four of them changed an API this
plan quotes verbatim, so read the source, not the snippets above:

- `root_group_of` now takes `(guard, chosen_root, blocked_target, promoted_from)`. The guard
  argument is `StrategyArbiter.last_selected_guard` — the guard the arbiter actually SELECTED
  — not `StrategyDecision.interrupt`, which `decide_tree` hardcodes to None and which could
  therefore never produce the `"guard"` label in production. The classifier also groups on
  the walk's own pick (`promoted_from or chosen_root`), because servability promotion can
  walk a gear pick to the trunk and counting that as the trunk winning inverts the census's
  own question.
- `gated_xp_sources` returns one `GatedSource` PER MONSTER, carrying a tuple of `GatedStep`.
  A monster's `gap` is its deepest gate, because `combat_deficit` only sets `closes` after
  the last step wins; ranking on a per-step gap let a non-binding step represent its monster
  in a list read as a priority order.
- `currency_rates` refuses `RECOVERY_GOAL` and excludes any cycle whose cooldown is not a
  POSITIVE number of seconds (0.0 was previously kept, contributing currency to the numerator
  and nothing to the denominator).
- `objective_audit_command` bounds every section to ONE window — the id floor of its single
  `recent_cycles(window)` read — and prints the row count, id span and timestamp span each
  section actually used.

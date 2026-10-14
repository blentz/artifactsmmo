# Items Task Pays — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `ReachCharLevel` step defers to a held items task only while that task pays (gold/drops verdict, or demanded skill XP faster than the grind's character XP), at any level gap.

**Architecture:** A store query measures a task's demanded-skill XP per second of its own work cycles (Task 1). A new shell module `held_task_pays` turns `task_worth` plus that rate plus the grind's modelled rate into one bool (Task 2). The Lean-bound pure core `objective_step_is_fight_pure` drops the level gap and takes that bool; the Lean model, oracle, contracts, differential test and the strategy driver change with it, and the bootstrap-horizon constant retires (Task 3).

**Tech Stack:** Python 3.13 (`uv run`), SQLModel/SQLAlchemy, pytest + hypothesis, Lean 4 (`lake`), `formal/diff/mutate.py`.

**Spec:** `docs/superpowers/specs/2026-10-14-items-task-pays-design.md`

## Global Constraints

- Prefix every Python command with `uv run`. No inline imports. Never catch `Exception` (the store's existing `except SQLAlchemyError` pattern is the only handler allowed). No `if TYPE_CHECKING`. One behavioural class per file. No `...` relative imports.
- Success = 0 errors, 0 warnings, 0 skipped, 100% coverage. Tests live in `tests/`.
- Mutation anchors for every new branch in the SAME commit as the code (`formal/diff/mutate.py`); `uv run python formal/diff/mutate.py --check-anchors` must pass; a scoped sweep `uv run python formal/diff/mutate.py --only <src file>` must show no survivors (run it AFTER the commit — the sweep refuses a dirty source).
- Never `--no-verify`, never `git stash`, never `git checkout <path>` to undo work. Chain git commands with `&&`.
- Work in the worktree `../artifactsmmo-taskpays` on branch `feat/items-task-pays` (the live fleet runs the main checkout through an editable install; a supervisor-restarted child would load half-done code). Setup, from the main checkout:
  ```bash
  git worktree add ../artifactsmmo-taskpays -b feat/items-task-pays
  ln -s /home/blentz/git/artifactsmmo/artifactsmmo-api-client ../artifactsmmo-taskpays/artifactsmmo-api-client
  cp -a --reflink=auto formal/.lake ../artifactsmmo-taskpays/formal/.lake
  cd ../artifactsmmo-taskpays && uv sync
  ```
  Commit in the worktree with `ARTIFACTSMMO_TOKEN=dummy git commit ...` (the hook's CLI help test needs a token; never copy the real `TOKEN`).
- The pre-commit hook runs `tests/test_ai/` only. Run `formal/diff/` and `tests/test_audit/` tests yourself for any task touching them.
- Lean: `cd formal && lake build` must pass; `lake env lean Formal/Manifest.lean` must pass; `Formal/Audit.lean` `#print axioms` lines must show no `sorryAx`.

## Review Focus

1. A character that FIGHTS while holding the task must not lower the task's measured rate (fight cycles carry the same `task_code`) — else pricing forbids the work and the absent work keeps the price (an absorbing state). Pinned: Task 1 `test_fight_cycles_while_held_are_not_task_work`.
2. Zero-XP gather cycles must stay in the denominator — a mean over XP-gaining cycles is the 50x over-estimate of 2026-08-08. Pinned: Task 1 `test_rate_counts_every_second_of_the_work`.
3. A task never worked has no rate and must still defer on `worth.xp` (otherwise it can never be measured). Pinned: Task 2 `test_no_rate_anywhere_defers_on_the_xp_verdict`.
4. Rows with a NULL `actual_cooldown_seconds` must not crash the sum. Pinned: Task 1 `test_null_seconds_count_as_zero`.
5. Task code prefixes: `cooked_shrimp` must not match a `GatherMaterials(cooked_shrimp_soup, …)` row. Pinned: Task 1 `test_another_codes_rows_are_not_this_tasks_work`.

---

### Task 1: Learned task-work XP rate

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/store.py` (add after `fleet_skill_grind_rate`, ~line 899; the shared body after `_grind_rate`, ~line 1017)
- Test: `tests/test_ai/test_learning_store.py` (new class `TestTaskWorkXpRate`; one line in `TestDegradationOnDbError`)
- Modify: `formal/diff/mutate.py` (new group + `run_group`)

**Interfaces:**
- Produces: `LearningStore.task_work_xp_per_second(task_code: str, skills: frozenset[str], window: int = WINDOW_RECENT) -> float | None` and `LearningStore.fleet_task_work_xp_per_second(task_code: str, skills: frozenset[str], window: int = WINDOW_RECENT) -> float | None`. None = no work cycles with positive seconds (ignorance) or a DB fault; `0.0` = worked, no demanded XP.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ai/test_learning_store.py` (it already imports `LearningStore`, `SqlSession`, `Cycle` and has the `tmp_db_path` fixture and `_break_engine`):

```python
class TestTaskWorkXpRate:
    """Demanded skill XP per second of a task's OWN work cycles (spec
    2026-10-14 §2): every second of the work counts, fights do not."""

    @staticmethod
    def _add(store: LearningStore, i: int, *, character: str = "hero",
             task_code: str | None = "cooked_shrimp",
             goal: str = "GatherMaterials(cooked_shrimp, {cooked_shrimp:10})",
             seconds: float | None = 30.0, xp: str = "{}") -> None:
        with SqlSession(store._engine) as s:
            s.add(Cycle(ts=f"2026-10-14T00:00:{i:02d}+00:00", session_id=store._session_id,
                        cycle_index=i, character=character, outcome="ok",
                        task_code=task_code, selected_goal=goal,
                        actual_cooldown_seconds=seconds, delta_skill_xp_json=xp))
            s.commit()

    def test_no_work_is_no_rate(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        store.start_session()
        assert store.task_work_xp_per_second("cooked_shrimp", frozenset({"cooking"})) is None

    def test_rate_counts_every_second_of_the_work(self, tmp_db_path):
        """Two 30 s fishing gathers pay no cooking XP and stay in the
        denominator; a batched craft is priced by its seconds, not as one
        cycle: 100 cooking XP over 30 + 30 + 60 s."""
        store = LearningStore(db_path=tmp_db_path, character="hero")
        store.start_session()
        self._add(store, 0, xp='{"fishing": 19}')
        self._add(store, 1, xp='{"fishing": 19}')
        self._add(store, 2, goal="PursueTask(cooked_shrimp)", seconds=60.0, xp='{"cooking": 100}')
        assert store.task_work_xp_per_second("cooked_shrimp", frozenset({"cooking"})) == 100 / 120
        both = frozenset({"cooking", "fishing"})
        assert store.task_work_xp_per_second("cooked_shrimp", both) == 138 / 120
        assert store.task_work_xp_per_second("cooked_shrimp", frozenset()) == 0.0

    def test_fight_cycles_while_held_are_not_task_work(self, tmp_db_path):
        """A fight while the task is held carries its task_code but is not its
        work: counting it would let fighting lower the task's rate."""
        store = LearningStore(db_path=tmp_db_path, character="hero")
        store.start_session()
        self._add(store, 0, goal="PursueTask(cooked_shrimp)", xp='{"cooking": 30}')
        self._add(store, 1, goal="GrindCharacterXP(imp)", seconds=900.0)
        assert store.task_work_xp_per_second("cooked_shrimp", frozenset({"cooking"})) == 1.0

    def test_another_codes_rows_are_not_this_tasks_work(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        store.start_session()
        self._add(store, 0, xp='{"cooking": 30}')
        self._add(store, 1, task_code="cooked_shrimp_soup",
                  goal="GatherMaterials(cooked_shrimp_soup, {cooked_shrimp_soup:5})",
                  xp='{"cooking": 900}')
        self._add(store, 2, task_code="trout", goal="PursueTask(cooked_shrimp)",
                  xp='{"cooking": 900}')
        assert store.task_work_xp_per_second("cooked_shrimp", frozenset({"cooking"})) == 1.0

    def test_null_seconds_count_as_zero(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        store.start_session()
        self._add(store, 0, seconds=None, xp='{"cooking": 30}')
        assert store.task_work_xp_per_second("cooked_shrimp", frozenset({"cooking"})) is None
        self._add(store, 1, xp='{"cooking": 30}')
        assert store.task_work_xp_per_second("cooked_shrimp", frozenset({"cooking"})) == 2.0

    def test_own_rows_only_and_the_fleet_pools(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        store.start_session()
        self._add(store, 0, character="sibling", xp='{"cooking": 60}')
        assert store.task_work_xp_per_second("cooked_shrimp", frozenset({"cooking"})) is None
        self._add(store, 1, xp='{"cooking": 0}')
        assert store.task_work_xp_per_second("cooked_shrimp", frozenset({"cooking"})) == 0.0
        assert store.fleet_task_work_xp_per_second("cooked_shrimp", frozenset({"cooking"})) == 1.0

    def test_window_keeps_the_newest_rows(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        store.start_session()
        self._add(store, 0, xp='{"cooking": 300}')
        self._add(store, 1, xp='{"cooking": 30}')
        assert store.task_work_xp_per_second("cooked_shrimp", frozenset({"cooking"}), window=1) == 1.0
```

And inside `class TestDegradationOnDbError`:

```python
    def test_task_work_xp_per_second_returns_none(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="hero")
        _break_engine(store)
        assert store.task_work_xp_per_second("t", frozenset({"cooking"})) is None
        assert store.fleet_task_work_xp_per_second("t", frozenset({"cooking"})) is None
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_ai/test_learning_store.py -q --no-cov -k "TaskWorkXpRate or task_work"`
Expected: FAIL with `AttributeError: 'LearningStore' object has no attribute 'task_work_xp_per_second'`.

- [ ] **Step 3: Implement**

In `store.py`, after `fleet_skill_grind_rate`:

```python
    def task_work_xp_per_second(self, task_code: str, skills: frozenset[str],
                                window: int = WINDOW_RECENT) -> float | None:
        """XP of `skills` per second of THIS character's work on task
        `task_code` (spec 2026-10-14 §2: what a held items task pays in demanded
        skill XP, against the grind's character XP per second).

        Work cycles are the rows holding the task (`Cycle.task_code`) whose goal
        is one of the two `strategy_driver._pursue_goal` emits —
        `PursueTask(<code>)` and `GatherMaterials(<code>, {…})`. A fight while the
        task is held carries its task_code too and is excluded: counting it would
        let fighting lower the task's rate, and the low rate would keep the
        character fighting (an absorbing state).

        EVERY work second stays in the denominator, a zero-XP gather included:
        a mean over XP-gaining cycles only is the 50x over-estimate
        `skill_grind_rate` documents (R2D2, 2026-08-08). Seconds, not cycles: a
        batched craft is one cycle of many seconds.

        None when there are no work cycles with positive seconds (ignorance) or
        on a DB fault; 0.0 when the work ran and paid none of `skills`."""
        return self._task_work_rate(task_code, skills, window, character=self._character)

    def fleet_task_work_xp_per_second(self, task_code: str, skills: frozenset[str],
                                      window: int = WINDOW_RECENT) -> float | None:
        """`task_work_xp_per_second` pooled over every character in the store:
        the fallback for a character that has never worked the task."""
        return self._task_work_rate(task_code, skills, window, character=None)
```

After `_grind_rate`:

```python
    def _task_work_rate(self, task_code: str, skills: frozenset[str], window: int,
                        character: str | None) -> float | None:
        """Shared body of the two task-work rates — ONE query, so the
        per-character and fleet answers agree on what a work cycle is."""
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(Cycle.delta_skill_xp_json, Cycle.actual_cooldown_seconds)
                    .where(col(Cycle.task_code) == task_code)
                    .where(or_(
                        col(Cycle.selected_goal).startswith(
                            f"PursueTask({task_code})", autoescape=True),
                        col(Cycle.selected_goal).startswith(
                            f"GatherMaterials({task_code}, ", autoescape=True))))
                if character is not None:
                    stmt = stmt.where(col(Cycle.character) == character)
                stmt = stmt.order_by(col(Cycle.id).desc()).limit(window)
                rows = list(s.exec(stmt))
            seconds = sum(max(0.0, sec or 0.0) for _, sec in rows)
            if seconds <= 0:
                return None
            xp = sum(max(0, _parse_skill_xp_value(raw, skill))
                     for raw, _ in rows for skill in skills)
            return xp / seconds
        except SQLAlchemyError:
            return None
```

(`or_`, `col`, `select`, `SqlSession`, `SQLAlchemyError`, `_parse_skill_xp_value`, `WINDOW_RECENT` are already imported/defined in `store.py`.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_learning_store.py -q --no-cov`
Expected: all PASS.

- [ ] **Step 5: Mutation anchors**

In `formal/diff/mutate.py`, add a group next to the other store groups (find `LEARNING_STORE_SRC` or the `store.py` path constant with `grep -n "learning\" / \"store.py\"" formal/diff/mutate.py`; if none exists add `TASK_WORK_STORE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "learning" / "store.py"` beside the other `*_SRC` constants):

```python
# Task-work XP rate (spec 2026-10-14 items-task-pays §2). OWN run_group: killed
# by tests/test_ai/test_learning_store.py::TestTaskWorkXpRate.
TASK_WORK_RATE_MUTATIONS = [
    ("task work rate: fights while held count as work",
     "                    .where(col(Cycle.task_code) == task_code)\n"
     "                    .where(or_(\n",
     "                    .where(col(Cycle.task_code) == task_code)\n"
     "                    .where(or_(col(Cycle.selected_goal).is_not(None),\n"),
    ("task work rate: only XP-gaining cycles count (the 50x over-estimate)",
     "            seconds = sum(max(0.0, sec or 0.0) for _, sec in rows)\n",
     "            seconds = sum(max(0.0, sec or 0.0) for raw, sec in rows\n"
     "                          if any(_parse_skill_xp_value(raw, k) > 0 for k in skills))\n"),
    ("task work rate: no work reads as a zero rate",
     "            if seconds <= 0:\n                return None\n            xp = sum(",
     "            if seconds <= 0:\n                return 0.0\n            xp = sum("),
    ("task work rate: the fleet reads only this character",
     "        return self._task_work_rate(task_code, skills, window, character=None)",
     "        return self._task_work_rate(task_code, skills, window, character=self._character)"),
]
```

and in the run list:

```python
    run_group(TASK_WORK_STORE_SRC, TASK_WORK_RATE_MUTATIONS,
              "tests/test_ai/test_learning_store.py", survivors)
```

Run: `uv run python formal/diff/mutate.py --check-anchors`
Expected: `anchor check OK: … all anchors resolve uniquely`.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/store.py tests/test_ai/test_learning_store.py formal/diff/mutate.py && ARTIFACTSMMO_TOKEN=dummy git commit -m "feat(store): demanded skill XP per second of a task's own work

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Then: `uv run python formal/diff/mutate.py --only src/artifactsmmo_cli/ai/learning/store.py` — expected: every `task work rate:` mutant `killed`.

---

### Task 2: `held_task_pays`

**Files:**
- Create: `src/artifactsmmo_cli/ai/held_task_pays.py`
- Test: `tests/test_ai/test_held_task_pays.py`
- Modify: `formal/diff/mutate.py`

**Interfaces:**
- Consumes: Task 1's `task_work_xp_per_second` / `fleet_task_work_xp_per_second`; `task_worth.task_worth_for(code, task_type, remaining, state, game_data, ctx, history) -> TaskWorth` (fields `xp`, `gold`, `drops`); `best_loadout.best_loadout(state, game_data, ctx, monster, store) -> BestLoadout` (`.rate.xp_per_second: Fraction`).
- Produces: `held_task_pays(state: WorldState, game_data: GameData, ctx: SelectionContext, monster: str, history: LearningStore | None) -> bool`. Precondition: `state.task_code` is set (the caller checks the items task is active first).

- [ ] **Step 1: Write the failing tests**

`tests/test_ai/test_held_task_pays.py`:

```python
"""Whether a held items task pays enough to defer the level step (spec
2026-10-14 items-task-pays §2)."""

from dataclasses import replace
from fractions import Fraction
from types import SimpleNamespace

import pytest

import artifactsmmo_cli.ai.held_task_pays as pays_mod
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.held_task_pays import held_task_pays
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.task_worth_core import TaskWorth
from tests.test_ai.fixtures import make_state

STATE = make_state(task_code="cooked_shrimp", task_type="items", task_total=200, task_progress=20)
CTX = replace(NO_PROFILE_CONTEXT, combat_monster="imp", skill_demand=frozenset({"cooking"}))
GRIND = Fraction(15, 31)   # HAL vs imp, live 2026-10-14


def _worth(monkeypatch: pytest.MonkeyPatch, worth: TaskWorth) -> list[tuple]:
    calls: list[tuple] = []

    def fake(*args: object) -> TaskWorth:
        calls.append(args)
        return worth
    monkeypatch.setattr(pays_mod, "task_worth_for", fake)
    return calls


def _grind(monkeypatch: pytest.MonkeyPatch, rate: Fraction = GRIND) -> list[str]:
    monsters: list[str] = []

    def fake(state: object, game_data: object, ctx: object, monster: str,
             store: object) -> SimpleNamespace:
        monsters.append(monster)
        return SimpleNamespace(rate=SimpleNamespace(xp_per_second=rate))
    monkeypatch.setattr(pays_mod, "best_loadout", fake)
    return monsters


def _store(monkeypatch: pytest.MonkeyPatch, own: float | None,
           fleet: float | None) -> LearningStore:
    store = LearningStore(db_path=":memory:", character="hero")
    monkeypatch.setattr(store, "task_work_xp_per_second", lambda code, skills: own)
    monkeypatch.setattr(store, "fleet_task_work_xp_per_second", lambda code, skills: fleet)
    return store


def _boom(*_: object, **__: object) -> None:
    raise AssertionError("must not be read")


def test_a_worthless_task_does_not_pay(monkeypatch: pytest.MonkeyPatch) -> None:
    _worth(monkeypatch, TaskWorth(xp=False, gold=False, drops=False))
    monkeypatch.setattr(pays_mod, "best_loadout", _boom)
    assert held_task_pays(STATE, GameData(), CTX, "imp", None) is False


@pytest.mark.parametrize("worth", [TaskWorth(xp=False, gold=True, drops=False),
                                   TaskWorth(xp=False, gold=False, drops=True)])
def test_a_gold_or_drop_verdict_pays(monkeypatch: pytest.MonkeyPatch, worth: TaskWorth) -> None:
    _worth(monkeypatch, worth)
    monkeypatch.setattr(pays_mod, "best_loadout", _boom)
    assert held_task_pays(STATE, GameData(), CTX, "imp", None) is True


def test_demanded_xp_faster_than_the_grind_pays(monkeypatch: pytest.MonkeyPatch) -> None:
    _worth(monkeypatch, TaskWorth(xp=True, gold=False, drops=False))
    monsters = _grind(monkeypatch)
    assert held_task_pays(STATE, GameData(), CTX, "imp",
                          _store(monkeypatch, own=0.5, fleet=None)) is True
    assert monsters == ["imp"]


def test_demanded_xp_slower_than_the_grind_does_not_pay(monkeypatch: pytest.MonkeyPatch) -> None:
    _worth(monkeypatch, TaskWorth(xp=True, gold=False, drops=False))
    _grind(monkeypatch)
    assert held_task_pays(STATE, GameData(), CTX, "imp",
                          _store(monkeypatch, own=0.4, fleet=9.0)) is False


def test_an_equal_rate_does_not_pay(monkeypatch: pytest.MonkeyPatch) -> None:
    _worth(monkeypatch, TaskWorth(xp=True, gold=False, drops=False))
    _grind(monkeypatch, Fraction(1, 2))
    assert held_task_pays(STATE, GameData(), CTX, "imp",
                          _store(monkeypatch, own=0.5, fleet=None)) is False


def test_the_fleet_rate_stands_in_for_a_task_never_worked(monkeypatch: pytest.MonkeyPatch) -> None:
    _worth(monkeypatch, TaskWorth(xp=True, gold=False, drops=False))
    _grind(monkeypatch)
    assert held_task_pays(STATE, GameData(), CTX, "imp",
                          _store(monkeypatch, own=None, fleet=0.1)) is False
    assert held_task_pays(STATE, GameData(), CTX, "imp",
                          _store(monkeypatch, own=None, fleet=0.9)) is True


def test_no_rate_anywhere_defers_on_the_xp_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    """Spec ruling: without a learned rate the XP verdict alone decides, so a
    task never worked is worked once and measured (no absorbing state)."""
    _worth(monkeypatch, TaskWorth(xp=True, gold=False, drops=False))
    monkeypatch.setattr(pays_mod, "best_loadout", _boom)
    assert held_task_pays(STATE, GameData(), CTX, "imp",
                          _store(monkeypatch, own=None, fleet=None)) is True
    assert held_task_pays(STATE, GameData(), CTX, "imp", None) is True


def test_the_worth_reads_the_remaining_units(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _worth(monkeypatch, TaskWorth(xp=False, gold=False, drops=False))
    held_task_pays(STATE, GameData(), CTX, "imp", None)
    code, task_type, remaining = calls[0][:3]
    assert (code, task_type, remaining) == ("cooked_shrimp", "items", 180)


def test_the_rate_reads_the_demanded_skills(monkeypatch: pytest.MonkeyPatch) -> None:
    _worth(monkeypatch, TaskWorth(xp=True, gold=False, drops=False))
    _grind(monkeypatch)
    store = LearningStore(db_path=":memory:", character="hero")
    seen: list[tuple[str, frozenset[str]]] = []

    def own(code: str, skills: frozenset[str]) -> float:
        seen.append((code, skills))
        return 1.0
    monkeypatch.setattr(store, "task_work_xp_per_second", own)
    assert held_task_pays(STATE, GameData(), CTX, "imp", store) is True
    assert seen == [("cooked_shrimp", frozenset({"cooking"}))]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_ai/test_held_task_pays.py -q --no-cov`
Expected: FAIL with `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.held_task_pays'`.

- [ ] **Step 3: Implement**

`src/artifactsmmo_cli/ai/held_task_pays.py`:

```python
"""Whether the held items task pays enough to defer the level step (spec
2026-10-14 items-task-pays §2, USER "Price it by useful XP").

A task pays when `task_worth` says its gold or drops are worth having (today's
verdicts), or when it pays skill XP the goal-action DAG demands FASTER than the
grind pays character XP. The task's rate is learned (`LearningStore.
task_work_xp_per_second`, this character's work first, then the fleet's); the
grind's is the modelled loop the loadout chooser ranks by (`best_loadout`).
With no learned rate the XP verdict alone decides: a task never worked is
worked once and measured, so the price cannot forbid its own evidence."""

from fractions import Fraction

from artifactsmmo_cli.ai.best_loadout import best_loadout
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.task_worth import task_worth_for
from artifactsmmo_cli.ai.world_state import WorldState


def held_task_pays(state: WorldState, game_data: GameData, ctx: SelectionContext,
                   monster: str, history: LearningStore | None) -> bool:
    """Whether the held task (`state.task_code`, which must be set) pays
    enough to defer a grind against `monster`."""
    assert state.task_code is not None
    worth = task_worth_for(state.task_code, state.task_type,
                           state.task_total - state.task_progress,
                           state, game_data, ctx, history)
    if worth.gold or worth.drops:
        return True
    if not worth.xp:
        return False
    rate = _task_rate(state.task_code, ctx.skill_demand, history)
    if rate is None:
        return True
    grind = best_loadout(state, game_data, ctx, monster, history).rate.xp_per_second
    return Fraction(rate) > grind


def _task_rate(code: str, skills: frozenset[str],
               history: LearningStore | None) -> float | None:
    """The task's demanded skill XP per second: this character's, else the
    fleet's; None without a store or any work on record."""
    if history is None:
        return None
    own = history.task_work_xp_per_second(code, skills)
    return own if own is not None else history.fleet_task_work_xp_per_second(code, skills)
```

If importing `held_task_pays` from `strategy_driver` (Task 3) creates an import cycle, use the module-import pattern `food_producer.py` uses (`from artifactsmmo_cli.ai import best_loadout as _best_loadout`, attribute read at call time) and keep the test's monkeypatch target consistent with it.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_held_task_pays.py -q --no-cov`
Expected: all PASS. Then `uv run pytest tests/test_ai/test_held_task_pays.py -q --cov=artifactsmmo_cli.ai.held_task_pays --cov-report=term-missing` shows 100%.

- [ ] **Step 5: Mutation anchors**

In `formal/diff/mutate.py` add `HELD_TASK_PAYS_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "held_task_pays.py"` beside the other `*_SRC` constants, and:

```python
# held_task_pays (spec 2026-10-14 items-task-pays §2). Killed by
# tests/test_ai/test_held_task_pays.py.
HELD_TASK_PAYS_MUTATIONS = [
    ("held_task_pays: a drop verdict does not pay",
     "    if worth.gold or worth.drops:",
     "    if worth.gold:"),
    ("held_task_pays: a worthless task pays",
     "    if not worth.xp:\n        return False",
     "    if not worth.xp:\n        return True"),
    ("held_task_pays: no learned rate never defers",
     "    if rate is None:\n        return True",
     "    if rate is None:\n        return False"),
    ("held_task_pays: an equal rate pays",
     "    return Fraction(rate) > grind",
     "    return Fraction(rate) >= grind"),
    ("held_task_pays: the fleet never stands in",
     "    return own if own is not None else history.fleet_task_work_xp_per_second(code, skills)",
     "    return own"),
    ("held_task_pays: the worth reads the whole task, not what remains",
     "                           state.task_total - state.task_progress,",
     "                           state.task_total,"),
]
```

and `run_group(HELD_TASK_PAYS_SRC, HELD_TASK_PAYS_MUTATIONS, "tests/test_ai/test_held_task_pays.py", survivors)` in the run list.

Run: `uv run python formal/diff/mutate.py --check-anchors` — expected OK.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/held_task_pays.py tests/test_ai/test_held_task_pays.py formal/diff/mutate.py && ARTIFACTSMMO_TOKEN=dummy git commit -m "feat(tasks): a held items task pays when its demanded skill XP beats the grind

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Then `uv run python formal/diff/mutate.py --only src/artifactsmmo_cli/ai/held_task_pays.py` — every `held_task_pays:` mutant `killed`.

---

### Task 3: The level step defers only to a paying task (core, Lean, driver)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/objective_step_fight_core.py` (whole module)
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py:507-546` (the `ReachCharLevel` arm)
- Modify: `src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py:137-161` (retire `_CHAR_LEVEL_BOOTSTRAP_HORIZON` and its NOTE)
- Modify: `src/artifactsmmo_cli/ai/decisions/root.py:269-270` (docstring bullet about the gap)
- Modify: `formal/Formal/ObjectiveStepFight.lean` (def + theorems), `formal/Formal/Contracts.lean:1471-1513`, `formal/Formal/Manifest.lean:290-297`, `formal/Formal/Audit.lean:234-239`, `formal/Oracle.lean:1085-1117` and its dispatch at `:3004-3007`
- Modify: `formal/diff/test_objective_step_is_fight_diff.py` (whole file), `formal/diff/mutate.py:2819-2865` and the `BOOTSTRAP_HORIZON` `run_group` at `:10305-10306`
- Test: `tests/test_ai/test_objective_step_fight_core.py` (whole file), `tests/test_ai/test_decisions_obtain_item.py:315-330`

**Interfaces:**
- Consumes: Task 2's `held_task_pays(state, game_data, ctx, monster, history) -> bool`.
- Produces: `items_task_active(task_type: str | None, task_code: str | None, task_total: int, task_progress: int) -> bool` and `objective_step_is_fight_pure(is_reach_char_level: bool, has_combat_monster: bool, task_type: str | None, task_code: str | None, task_total: int, task_progress: int, task_pays: bool) -> bool` (keyword-only use everywhere). Lean: `objectiveStepIsFightPure (isReachCharLevel hasCombatMonster : Bool) (taskType taskCode : String) (taskTotal taskProgress : Nat) (taskPays : Bool) : Bool`; oracle `objective_step_is_fight` args `[isReach, hasMonster, taskType, taskCode, taskTotal, taskProgress, taskPays]`; oracle command `bootstrap_char_horizon` removed.

- [ ] **Step 1: Write the failing Python tests**

Replace `tests/test_ai/test_objective_step_fight_core.py` with:

```python
"""Characterization tests for `objective_step_is_fight_pure` (spec 2026-10-14
items-task-pays §1): a ReachCharLevel step is Fight-led unless an items task
is in progress AND it pays. The level gap plays no part."""

import pytest

from artifactsmmo_cli.ai.objective_step_fight_core import (
    items_task_active,
    objective_step_is_fight_pure,
)


def _fire(*, is_reach_char_level: bool = True, has_combat_monster: bool = True,
          task_type: str | None = None, task_code: str | None = None,
          task_total: int = 0, task_progress: int = 0, task_pays: bool = False) -> bool:
    return objective_step_is_fight_pure(
        is_reach_char_level=is_reach_char_level, has_combat_monster=has_combat_monster,
        task_type=task_type, task_code=task_code, task_total=task_total,
        task_progress=task_progress, task_pays=task_pays)


ACTIVE = {"task_type": "items", "task_code": "t1", "task_total": 5, "task_progress": 2}


def test_reach_char_level_with_monster_no_task_fires() -> None:
    assert _fire() is True


def test_non_reach_char_level_never_fires() -> None:
    assert _fire(is_reach_char_level=False) is False


def test_no_combat_monster_does_not_fire() -> None:
    assert _fire(has_combat_monster=False) is False


def test_a_paying_active_items_task_defers() -> None:
    assert _fire(**ACTIVE, task_pays=True) is False


def test_an_unpaid_active_items_task_fights() -> None:
    """HAL 2026-10-14: a worthless items task no longer defers the grind."""
    assert _fire(**ACTIVE, task_pays=False) is True


def test_a_paid_task_that_is_not_active_fights() -> None:
    assert _fire(task_type="items", task_code="t1", task_total=5, task_progress=5,
                 task_pays=True) is True
    assert _fire(task_type="monsters", task_code="t1", task_total=5, task_progress=2,
                 task_pays=True) is True
    assert _fire(task_type="items", task_code="", task_total=5, task_progress=2,
                 task_pays=True) is True
    assert _fire(task_type="items", task_code=None, task_total=5, task_progress=2,
                 task_pays=True) is True


@pytest.mark.parametrize(("task_type", "task_code", "total", "progress", "active"), [
    ("items", "t1", 5, 2, True),
    ("items", "t1", 5, 5, False),
    ("items", "t1", 0, 0, False),
    ("monsters", "t1", 5, 2, False),
    ("items", "", 5, 2, False),
    (None, None, 0, 0, False),
])
def test_items_task_active(task_type: str | None, task_code: str | None, total: int,
                           progress: int, active: bool) -> None:
    assert items_task_active(task_type, task_code, total, progress) is active
```

In `tests/test_ai/test_decisions_obtain_item.py`, replace `test_objective_step_goal_stands_down_for_reach_char_level_items_task` with the three tests below (the module already imports `objective_step_goal`, `ReachCharLevel`, `GameData`, `make_state`, `_ctx`, `_gd`, `GrindCharacterXPGoal`; add `import artifactsmmo_cli.ai.strategy_driver as strategy_driver_mod` and `import pytest` at the top if absent):

```python
def test_objective_step_goal_stands_down_for_a_paying_items_task(monkeypatch):
    """A held items task that pays defers the level step, at ANY gap (spec
    2026-10-14: the gap no longer matters — here it is 1)."""
    monkeypatch.setattr(strategy_driver_mod, "held_task_pays", lambda *a: True)
    state = make_state(level=3, task_code="copper_bar", task_type="items",
                       task_total=20, task_progress=0)
    ctx = _ctx(combat_monster="chicken")
    assert objective_step_goal(ReachCharLevel(4), state, GameData(), ctx) is None


def test_objective_step_goal_grinds_past_an_unpaid_items_task(monkeypatch):
    """HAL 2026-10-14 (level 35, root 40, worthless trout task): the grind."""
    seen: list[str] = []

    def pays(state, game_data, ctx, monster, history):
        seen.append(monster)
        return False
    monkeypatch.setattr(strategy_driver_mod, "held_task_pays", pays)
    state = make_state(level=3, xp=50, task_code="copper_bar", task_type="items",
                       task_total=20, task_progress=0)
    ctx = _ctx(combat_monster="chicken")
    goal = objective_step_goal(ReachCharLevel(50), state, _gd(), ctx)
    assert isinstance(goal, GrindCharacterXPGoal)
    assert seen == ["chicken"]


def test_objective_step_goal_reads_no_pay_without_an_active_items_task(monkeypatch):
    def boom(*_a):
        raise AssertionError("the pay is read only for an active items task")
    monkeypatch.setattr(strategy_driver_mod, "held_task_pays", boom)
    state = make_state(level=3, xp=50, task_code="chicken", task_type="monsters",
                       task_total=20, task_progress=0)
    goal = objective_step_goal(ReachCharLevel(50), state, _gd(), _ctx(combat_monster="chicken"))
    assert isinstance(goal, GrindCharacterXPGoal)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_ai/test_objective_step_fight_core.py tests/test_ai/test_decisions_obtain_item.py -q --no-cov -k "fight or objective_step_goal or items_task"`
Expected: FAIL (`ImportError: cannot import name 'items_task_active'`; `AttributeError: … has no attribute 'held_task_pays'`).

- [ ] **Step 3: Implement the pure core**

Replace the body of `src/artifactsmmo_cli/ai/objective_step_fight_core.py` below its module docstring (keep the docstring, but replace its paragraph about the stand-down with: "The items-task stand-down is PRICED (spec 2026-10-14 items-task-pays): the step defers only while an items task is in progress AND it pays (`held_task_pays`, read by the shell). The level gap plays no part.") with:

```python
def items_task_active(task_type: str | None, task_code: str | None,
                      task_total: int, task_progress: int) -> bool:
    """An items task is held and not yet complete."""
    return (task_type == "items"
            and bool(task_code)
            and task_total > 0
            and task_progress < task_total)


def objective_step_is_fight_pure(
    is_reach_char_level: bool,
    has_combat_monster: bool,
    task_type: str | None,
    task_code: str | None,
    task_total: int,
    task_progress: int,
    task_pays: bool,
) -> bool:
    """Pure `objectiveStepIsFight` decision.

    Mirrors the `ReachCharLevel` branch of `objective_step_goal`:
      1. The committed objective step must be a `ReachCharLevel` goal.
      2. A combat monster must be available (`ctx.combat_monster is not None`).
      3. The step defers (no objective step -> not Fight-led) only while an
         items task is in progress AND it pays (`task_pays`, from
         `held_task_pays`: a gold/drop verdict, or demanded skill XP faster
         than the grind's character XP). Spec 2026-10-14 items-task-pays.
    """
    if not is_reach_char_level:
        return False
    if not has_combat_monster:
        return False
    return not (items_task_active(task_type, task_code, task_total, task_progress)
                and task_pays)
```

- [ ] **Step 4: Wire the driver**

In `src/artifactsmmo_cli/ai/strategy_driver.py`, add imports (top of file, alphabetical with the others):

```python
from artifactsmmo_cli.ai.held_task_pays import held_task_pays
from artifactsmmo_cli.ai.objective_step_fight_core import items_task_active, objective_step_is_fight_pure
```

(replacing the existing single-name `objective_step_fight_core` import). Replace the `ReachCharLevel` arm's comment block and call — from `# Items-task stand-down was designed for the LONG-HAUL` through `return None        # long-haul grind, items task active → defer` — with:

```python
        # A HELD ITEMS TASK DEFERS THE GRIND ONLY WHILE IT PAYS (spec
        # 2026-10-14 items-task-pays, USER "Price it by useful XP"): a gold or
        # drop verdict, or skill XP the DAG demands at a better rate than the
        # grind's character XP (`held_task_pays`). The rule was a level gap
        # (> 4 deferred, whatever the task paid): HAL, level 35 against a
        # level-40 root, worked worthless items tasks for 5.5 h at 0 character
        # XP (2026-10-14), the June 2026 "items tasks chain, the bot never
        # fought" livelock back whenever a root sat more than 4 levels away.
        # The pay is read only for an active items task (it walks the task).
        # Decision extracted to the pure boundary `objective_step_is_fight_pure`
        # — the SAME predicate the Lean liveness Bool `objectiveStepIsFight`
        # binds to via the differential gate.
        task_pays = (items_task_active(state.task_type, state.task_code,
                                       state.task_total, state.task_progress)
                     and held_task_pays(state, game_data, ctx, ctx.combat_monster, history))
        if not objective_step_is_fight_pure(
                is_reach_char_level=True,
                has_combat_monster=True,
                task_type=state.task_type,
                task_code=state.task_code,
                task_total=state.task_total,
                task_progress=state.task_progress,
                task_pays=task_pays):
            return None        # a paying items task is worked instead
```

- [ ] **Step 5: Retire the bootstrap horizon and fix stale prose**

In `src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py` delete `_CHAR_LEVEL_BOOTSTRAP_HORIZON = 2`, its docstring, and the `# NOTE: \`objective_roots\` …` comment block that follows (lines 137-161; it says the constant stays only as the formal anchor this task removes). Confirm nothing else reads it: `grep -rn "_CHAR_LEVEL_BOOTSTRAP_HORIZON" src tests formal --include=*.py` must print only lines you are deleting in this task.

In `src/artifactsmmo_cli/ai/decisions/root.py` replace the bullet

```
      * the gap `target - level` is negative, so the long-haul items-task
        stand-down in `objective_step_is_fight_pure` can never engage, whatever
        the character is actually doing.
```

with

```
      * it names a level already reached, so the `ReachCharLevel` step it
        commits has nothing left to grind.
```

- [ ] **Step 6: Run the Python tests**

Run: `uv run pytest tests/test_ai/test_objective_step_fight_core.py tests/test_ai/test_decisions_obtain_item.py -q --no-cov`
Expected: all PASS.

- [ ] **Step 7: The Lean model**

In `formal/Formal/ObjectiveStepFight.lean`: update the module docstring's PYTHON DECISION block to the new rule, delete the Nat-subtraction faithfulness note, and replace everything from the `def objectiveStepIsFightPure` docstring to `end Formal.ObjectiveStepFight` with:

```lean
/-- `itemsTaskActive` — an items task is held and not yet complete
(`objective_step_fight_core.items_task_active`). -/
def itemsTaskActive (taskType taskCode : String) (taskTotal taskProgress : Nat) : Prop :=
  taskType = "items" ∧ taskCode ≠ "" ∧ taskTotal > 0 ∧ taskProgress < taskTotal

/-- The pure decision boundary. Mirrors `objective_step_is_fight_pure`
component-for-component: a committed `ReachCharLevel` with a combat monster is
Fight-led unless an items task is in progress AND it pays (spec 2026-10-14
items-task-pays). The level gap plays no part. -/
def objectiveStepIsFightPure (isReachCharLevel hasCombatMonster : Bool)
    (taskType taskCode : String) (taskTotal taskProgress : Nat) (taskPays : Bool) : Bool :=
  if ¬ isReachCharLevel then false
  else if ¬ hasCombatMonster then false
  else if (taskType = "items" ∧ taskCode ≠ "" ∧ taskTotal > 0 ∧ taskProgress < taskTotal)
            ∧ taskPays = true
       then false
  else true

/-! ### Role theorems. -/

/-- (characterization) EXACT spec, pinned in `Contracts.lean`. -/
theorem fires_iff (isReachCharLevel hasCombatMonster : Bool)
    (taskType taskCode : String) (taskTotal taskProgress : Nat) (taskPays : Bool) :
    objectiveStepIsFightPure isReachCharLevel hasCombatMonster taskType taskCode
        taskTotal taskProgress taskPays = true
      ↔ (isReachCharLevel = true ∧ hasCombatMonster = true ∧
          ¬ (itemsTaskActive taskType taskCode taskTotal taskProgress ∧ taskPays = true)) := by
  unfold objectiveStepIsFightPure itemsTaskActive
  by_cases h1 : isReachCharLevel = true
  · by_cases h2 : hasCombatMonster = true
    · by_cases h3 : (taskType = "items" ∧ taskCode ≠ "" ∧ taskTotal > 0 ∧ taskProgress < taskTotal)
              ∧ taskPays = true
      · simp [h1, h2, h3]
      · simp [h1, h2, h3]
    · simp [h1, h2]
  · simp [h1]

/-- (a) Not a `ReachCharLevel` step ⇒ never Fight-led. -/
theorem not_reach_char_level_never_fires (hasCombatMonster : Bool)
    (taskType taskCode : String) (taskTotal taskProgress : Nat) (taskPays : Bool) :
    objectiveStepIsFightPure false hasCombatMonster taskType taskCode taskTotal taskProgress
        taskPays = false := by
  simp [objectiveStepIsFightPure]

example : objectiveStepIsFightPure false true "" "" 0 0 false = false :=
  not_reach_char_level_never_fires true "" "" 0 0 false

/-- (b) No combat monster ⇒ never Fight-led. -/
theorem no_combat_monster_never_fires (taskType taskCode : String)
    (taskTotal taskProgress : Nat) (taskPays : Bool) :
    objectiveStepIsFightPure true false taskType taskCode taskTotal taskProgress taskPays
      = false := by
  simp [objectiveStepIsFightPure]

example : objectiveStepIsFightPure true false "" "" 0 0 false = false :=
  no_combat_monster_never_fires "" "" 0 0 false

/-- (c, LIVENESS) An UNPAID task never defers: a committed `ReachCharLevel` with a
combat monster is Fight-led whatever items task is held, when it does not pay.
Replaces the retired gap guarantee (`bootstrap_always_fires`). -/
theorem unpaid_task_fires (taskType taskCode : String) (taskTotal taskProgress : Nat) :
    objectiveStepIsFightPure true true taskType taskCode taskTotal taskProgress false
      = true := by
  simp [objectiveStepIsFightPure]

example : objectiveStepIsFightPure true true "items" "t1" 5 2 false = true :=
  unpaid_task_fires "items" "t1" 5 2

/-- (d) No items task in progress ⇒ Fight-led, paying or not. -/
theorem no_items_task_fires (taskType taskCode : String) (taskTotal taskProgress : Nat)
    (taskPays : Bool) (hidle : ¬ itemsTaskActive taskType taskCode taskTotal taskProgress) :
    objectiveStepIsFightPure true true taskType taskCode taskTotal taskProgress taskPays
      = true := by
  unfold itemsTaskActive at hidle
  have hnot : ¬ ((taskType = "items" ∧ taskCode ≠ "" ∧ taskTotal > 0 ∧ taskProgress < taskTotal)
      ∧ taskPays = true) := fun h => hidle h.1
  simp [objectiveStepIsFightPure, hnot]

example : objectiveStepIsFightPure true true "monsters" "t1" 5 2 true = true :=
  no_items_task_fires "monsters" "t1" 5 2 true (by simp [itemsTaskActive])

/-- (e) Release: a COMPLETED items task never defers, paying or not. -/
theorem completed_task_fires (taskType taskCode : String) (taskTotal taskProgress : Nat)
    (taskPays : Bool) (hdone : taskProgress ≥ taskTotal) :
    objectiveStepIsFightPure true true taskType taskCode taskTotal taskProgress taskPays
      = true := by
  apply no_items_task_fires
  unfold itemsTaskActive
  rintro ⟨_, _, _, hlt⟩
  omega

example : objectiveStepIsFightPure true true "items" "t1" 5 5 true = true :=
  completed_task_fires "items" "t1" 5 5 true (by decide)

/-- Non-vacuity of the deferral branch: an active, PAYING items task defers. -/
example : objectiveStepIsFightPure true true "items" "t1" 5 2 true = false := by
  simp [objectiveStepIsFightPure]

end Formal.ObjectiveStepFight
```

If a `simp` call does not close its goal, use the Lean LSP tools (`lean_goal`, `lean_multi_attempt`) or the `lean4:proof-repair` agent's techniques; do not weaken a statement and never use `sorry`.

`formal/Formal/Contracts.lean`: replace the `### ObjectiveStepFight role contracts` block (the six `example`s from `-- characterization:` through `@Formal.ObjectiveStepFight.bootstrap_step_always_fires`) with:

```lean
/-! ### ObjectiveStepFight role contracts (O5.4 perception binding). -/
-- characterization: fires ⇔ ReachCharLevel ∧ combat monster ∧ ¬(items task active ∧ it pays).
example : ∀ (isReachCharLevel hasCombatMonster : Bool) (taskType taskCode : String)
    (taskTotal taskProgress : Nat) (taskPays : Bool),
    Formal.ObjectiveStepFight.objectiveStepIsFightPure isReachCharLevel hasCombatMonster
        taskType taskCode taskTotal taskProgress taskPays = true
      ↔ (isReachCharLevel = true ∧ hasCombatMonster = true ∧
          ¬ (Formal.ObjectiveStepFight.itemsTaskActive taskType taskCode taskTotal taskProgress
             ∧ taskPays = true)) :=
  @Formal.ObjectiveStepFight.fires_iff
-- safety: not a ReachCharLevel step ⇒ never Fight-led.
example : ∀ (hasCombatMonster : Bool) (taskType taskCode : String)
    (taskTotal taskProgress : Nat) (taskPays : Bool),
    Formal.ObjectiveStepFight.objectiveStepIsFightPure false hasCombatMonster
        taskType taskCode taskTotal taskProgress taskPays = false :=
  @Formal.ObjectiveStepFight.not_reach_char_level_never_fires
-- safety: no combat monster ⇒ never Fight-led.
example : ∀ (taskType taskCode : String) (taskTotal taskProgress : Nat) (taskPays : Bool),
    Formal.ObjectiveStepFight.objectiveStepIsFightPure true false
        taskType taskCode taskTotal taskProgress taskPays = false :=
  @Formal.ObjectiveStepFight.no_combat_monster_never_fires
-- liveness: an unpaid task never defers the grind (replaces the gap guarantee).
example : ∀ (taskType taskCode : String) (taskTotal taskProgress : Nat),
    Formal.ObjectiveStepFight.objectiveStepIsFightPure true true
        taskType taskCode taskTotal taskProgress false = true :=
  @Formal.ObjectiveStepFight.unpaid_task_fires
-- no items task in progress ⇒ Fight-led.
example : ∀ (taskType taskCode : String) (taskTotal taskProgress : Nat) (taskPays : Bool),
    ¬ Formal.ObjectiveStepFight.itemsTaskActive taskType taskCode taskTotal taskProgress →
    Formal.ObjectiveStepFight.objectiveStepIsFightPure true true
        taskType taskCode taskTotal taskProgress taskPays = true :=
  @Formal.ObjectiveStepFight.no_items_task_fires
-- release: items task complete ⇒ Fight-led (deferral is temporary).
example : ∀ (taskType taskCode : String) (taskTotal taskProgress : Nat) (taskPays : Bool),
    taskProgress ≥ taskTotal →
    Formal.ObjectiveStepFight.objectiveStepIsFightPure true true
        taskType taskCode taskTotal taskProgress taskPays = true :=
  @Formal.ObjectiveStepFight.completed_task_fires
```

`formal/Formal/Manifest.lean` lines 292-297 become:

```lean
#check @Formal.ObjectiveStepFight.fires_iff                       -- characterization: fires ⇔ ReachCharLevel ∧ monster ∧ ¬(items task active ∧ pays)
#check @Formal.ObjectiveStepFight.not_reach_char_level_never_fires -- safety: ¬ReachCharLevel ⇒ never Fight-led
#check @Formal.ObjectiveStepFight.no_combat_monster_never_fires    -- safety: no combat monster ⇒ never Fight-led
#check @Formal.ObjectiveStepFight.unpaid_task_fires               -- liveness: an unpaid items task never defers the grind
#check @Formal.ObjectiveStepFight.no_items_task_fires             -- no items task in progress ⇒ Fight-led
#check @Formal.ObjectiveStepFight.completed_task_fires            -- release: items-task done ⇒ Fight-led
```

`formal/Formal/Audit.lean` lines 234-239 become:

```lean
#print axioms Formal.ObjectiveStepFight.fires_iff
#print axioms Formal.ObjectiveStepFight.not_reach_char_level_never_fires
#print axioms Formal.ObjectiveStepFight.no_combat_monster_never_fires
#print axioms Formal.ObjectiveStepFight.unpaid_task_fires
#print axioms Formal.ObjectiveStepFight.no_items_task_fires
#print axioms Formal.ObjectiveStepFight.completed_task_fires
```

`formal/Oracle.lean`: replace `runObjectiveStepIsFight` (and its doc comment's args layout) with:

```lean
/-- Compute one objective_step_is_fight result using the SAME proved
`Formal.ObjectiveStepFight.objectiveStepIsFightPure` (the O5.4 perception binding).

args layout:
* `[0]`  isReachCharLevel (0/1)
* `[1]`  hasCombatMonster (0/1)
* `[2]`  taskType (String, e.g. "items")
* `[3]`  taskCode (String, "" = no task; the harness maps Python None → "")
* `[4]`  taskTotal (Nat)
* `[5]`  taskProgress (Nat)
* `[6]`  taskPays (0/1)

Emits `fires` as a Bool. The String comparisons (`== "items"`, `≠ ""`) are done
by the proved def itself, not the harness. -/
def runObjectiveStepIsFight (args : Array Json) : Json :=
  let isReachCharLevel := intArg args 0 != 0
  let hasCombatMonster := intArg args 1 != 0
  let taskType := strArg args 2
  let taskCode := strArg args 3
  let taskTotal := (intArg args 4).toNat
  let taskProgress := (intArg args 5).toNat
  let taskPays := intArg args 6 != 0
  let b := Formal.ObjectiveStepFight.objectiveStepIsFightPure isReachCharLevel hasCombatMonster
              taskType taskCode taskTotal taskProgress taskPays
  Json.mkObj [("fires", Json.bool b)]
```

Delete `runBootstrapCharHorizon` and its doc comment, and the dispatch lines

```lean
  else if kind == "bootstrap_char_horizon" then
    runBootstrapCharHorizon args
```

Run: `cd formal && lake build && lake env lean Formal/Manifest.lean && lake env lean Formal/Audit.lean | grep -c sorryAx`
Expected: build OK, `manifest` prints nothing on error, the `grep -c` prints `0`.

- [ ] **Step 8: The differential test**

Replace `formal/diff/test_objective_step_is_fight_diff.py` with:

```python
"""Differential test for the O5.4 perception binding.

Binds the proved Lean def `Formal.ObjectiveStepFight.objectiveStepIsFightPure`
(via the `objective_step_is_fight` oracle command) to the LIVE production pure
core `objective_step_is_fight_pure` (objective_step_fight_core.py) — the predicate
`strategy_driver.objective_step_goal`'s ReachCharLevel branch calls. A surviving
disagreement means the Lean model of `objectiveStepIsFight` has drifted from the
code that computes it.

Python `None` task fields map to "" for the oracle (both falsy); the Lean def
does the `== "items"` / `!= ""` comparisons itself.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.objective_step_fight_core import objective_step_is_fight_pure
from formal.diff.oracle_client import run_oracle_structured

_TASK_TYPES = st.sampled_from([None, "", "items", "monsters", "resources", "crafting"])
_TASK_CODES = st.sampled_from([None, "", "t1", "copper_ring", "green_slime"])


def _lean(is_reach: bool, has_monster: bool, task_type: str | None, task_code: str | None,
          task_total: int, task_progress: int, task_pays: bool) -> bool:
    args = [1 if is_reach else 0, 1 if has_monster else 0,
            task_type if task_type is not None else "",
            task_code if task_code is not None else "",
            task_total, task_progress, 1 if task_pays else 0]
    return bool(run_oracle_structured("objective_step_is_fight", [args])[0]["fires"])


def _py(is_reach: bool, has_monster: bool, task_type: str | None, task_code: str | None,
        task_total: int, task_progress: int, task_pays: bool) -> bool:
    return objective_step_is_fight_pure(
        is_reach_char_level=is_reach, has_combat_monster=has_monster,
        task_type=task_type, task_code=task_code, task_total=task_total,
        task_progress=task_progress, task_pays=task_pays)


@given(
    is_reach=st.booleans(),
    has_monster=st.booleans(),
    task_type=_TASK_TYPES,
    task_code=_TASK_CODES,
    task_total=st.integers(min_value=0, max_value=20),
    task_progress=st.integers(min_value=0, max_value=20),
    task_pays=st.booleans(),
)
@settings(max_examples=250, deadline=None)
def test_objective_step_is_fight_matches_oracle(
    is_reach: bool, has_monster: bool, task_type: str | None, task_code: str | None,
    task_total: int, task_progress: int, task_pays: bool,
) -> None:
    args = (is_reach, has_monster, task_type, task_code, task_total, task_progress, task_pays)
    assert _py(*args) == _lean(*args)


def test_a_paying_active_items_task_defers() -> None:
    args = (True, True, "items", "t1", 5, 2, True)
    assert _py(*args) is False
    assert _lean(*args) is False


def test_an_unpaid_active_items_task_fires() -> None:
    args = (True, True, "items", "t1", 5, 2, False)
    assert _py(*args) is True
    assert _lean(*args) is True


def test_a_paying_completed_items_task_fires() -> None:
    args = (True, True, "items", "t1", 5, 5, True)
    assert _py(*args) is True
    assert _lean(*args) is True
```

Run: `uv run pytest formal/diff/test_objective_step_is_fight_diff.py -q --no-cov`
Expected: all PASS (the harness builds/serves the oracle from `formal/.lake`).

- [ ] **Step 9: Mutation anchors**

In `formal/diff/mutate.py`, replace `OBJECTIVE_STEP_FIGHT_MUTATIONS` and delete `BOOTSTRAP_HORIZON_MUTATIONS` (with its comment block) and its `run_group(PREREQUISITE_GRAPH_SRC, BOOTSTRAP_HORIZON_MUTATIONS, …)` line. Keep the existing comment explaining why `task_total > 0` carries no mutation. New group:

```python
OBJECTIVE_STEP_FIGHT_MUTATIONS = [
    # the pay is ignored: an active items task defers whatever it pays (the
    # pre-2026-10-14 HAL livelock shape).
    ("objective_step_fight: the pay is ignored",
     "    return not (items_task_active(task_type, task_code, task_total, task_progress)\n"
     "                and task_pays)",
     "    return not items_task_active(task_type, task_code, task_total, task_progress)"),
    # drop the `not`: inverts every verdict.
    ("objective_step_fight: drop the `not` (invert defer)",
     "    return not (items_task_active(task_type, task_code, task_total, task_progress)\n"
     "                and task_pays)",
     "    return (items_task_active(task_type, task_code, task_total, task_progress)\n"
     "                and task_pays)"),
    ("objective_step_fight: task_type == \"items\" -> !=",
     '    return (task_type == "items"',
     '    return (task_type != "items"'),
    ("objective_step_fight: task_progress < total -> <=",
     "            and task_progress < task_total)",
     "            and task_progress <= task_total)"),
    ("objective_step_fight: a blank task code is a task",
     "            and bool(task_code)\n",
     "            and task_code is not None\n"),
    ("objective_step_fight: invert is_reach_char_level gate",
     "    if not is_reach_char_level:",
     "    if is_reach_char_level:"),
    ("objective_step_fight: invert has_combat_monster gate",
     "    if not has_combat_monster:",
     "    if has_combat_monster:"),
]

# The driver reads the pay only for an active items task, and passes it on.
# Killed by tests/test_ai/test_decisions_obtain_item.py.
OBJECTIVE_STEP_DRIVER_MUTATIONS = [
    ("strategy_driver: the level step never reads the pay",
     "                     and held_task_pays(state, game_data, ctx, ctx.combat_monster, history))",
     "                     and True)"),
    ("strategy_driver: the pay is read for any task",
     "        task_pays = (items_task_active(state.task_type, state.task_code,\n"
     "                                       state.task_total, state.task_progress)\n"
     "                     and held_task_pays(",
     "        task_pays = (True\n"
     "                     and held_task_pays("),
]
```

and add `run_group(STRATEGY_DRIVER_SRC, OBJECTIVE_STEP_DRIVER_MUTATIONS, "tests/test_ai/test_decisions_obtain_item.py", survivors)` next to the `OBJECTIVE_STEP_FIGHT` run_group (use the existing constant for `strategy_driver.py` — `grep -n "strategy_driver.py\"" formal/diff/mutate.py`; add `STRATEGY_DRIVER_SRC` beside the other `*_SRC` constants only if none exists).

Run: `uv run python formal/diff/mutate.py --check-anchors` — expected OK. Also `grep -rn "bootstrap_char_horizon\|_CHAR_LEVEL_BOOTSTRAP_HORIZON\|bootstrapCharHorizon\|bootstrap_always_fires\|bootstrap_step_always_fires" src tests formal --include=*.py --include=*.lean` — expected: no output.

- [ ] **Step 10: Full verification and commit**

Run: `uv run pytest tests/test_ai -q -n auto --no-cov -x` then `uv run pytest formal/diff/test_objective_step_is_fight_diff.py tests/test_audit -q --no-cov`.
Expected: all PASS.

```bash
git add -A src tests formal && ARTIFACTSMMO_TOKEN=dummy git commit -m "feat(tasks): the level step defers only to a held items task that pays

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Then `uv run python formal/diff/mutate.py --only src/artifactsmmo_cli/ai/objective_step_fight_core.py` and `--only src/artifactsmmo_cli/ai/strategy_driver.py` — every `objective_step_fight:` and `strategy_driver: … pay` mutant `killed`.

---

### Task 4: Live probe, gate, merge

**Files:** none new (the executor runs these).

- [ ] **Step 1: Live probe (read-only)** — in the worktree:
  `uv run artifactsmmo plan HAL --learn` (needs the real token: run from the MAIN checkout after the merge in Step 3, or skip here and run it there). Expected for HAL while it holds a worthless items task: `selected_goal: GrindCharacterXP(...)` or its heal/provision prep, not `PursueTask(...)`.
- [ ] **Step 2: Full gate** — `bash formal/gate.sh > /tmp/…/gate.log 2>&1; echo $? > /tmp/…/gate.rc`, then read the rc file in its own call. Expected `0` and `ALL GATE PARTS PASSED`; compare the `321 recipes; planned …` census line with main's.
- [ ] **Step 3: Merge** — from the main checkout: `git merge --ff-only feat/items-task-pays && git push origin HEAD:main`; then `git worktree remove ../artifactsmmo-taskpays && git branch -d feat/items-task-pays`. Re-run Step 1 from the main checkout.
- [ ] **Step 4: After the user restarts the fleet** — over learning.db: HAL character XP/h > 0 while it holds a worthless items task; fleet character XP/h above ≈3,240/h; no character spends an hour on an items task whose `task_worth` is all-False.

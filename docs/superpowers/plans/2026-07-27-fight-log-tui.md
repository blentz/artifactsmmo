# Fight Log in the TUI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the game API's per-turn combat transcript in the TUI — a one-line structured summary in the live log pane, and the verbatim transcript in a browsable modal backfilled from `GET /my/logs/{name}`.

**Architecture:** `FightAction.execute` already receives the full transcript and discards it. It will build a frozen `FightRecord` and stash it on the action instance (a non-comparing, non-repr field), which `GamePlayer._notify_observer` reads through an `isinstance` gate and puts on `CycleSnapshot` — exactly mirroring the existing `_last_grind_expansion` / `LevelSkill` pattern. `WorldState` is deliberately untouched so the Lean surface and differential oracle stay out of scope. The TUI renders a summary line from structured schema fields only, and shows the English transcript verbatim.

**Tech Stack:** Python 3.13, `uv`, pydantic v2, Textual, pytest. Generated OpenAPI client at `artifactsmmo-api-client/`.

## Global Constraints

Copied from `docs/superpowers/specs/2026-07-27-fight-log-tui-design.md` and `CLAUDE.md`:

- ALWAYS prefix Python commands with `uv run` (e.g. `uv run pytest`, `uv run mypy`).
- DO NOT use inline imports. All imports at the top of the file.
- DO NOT use `if TYPE_CHECKING` for any reason.
- **NEVER** catch `Exception`. No bare `except`.
- One *behavioral* class per file. Cohesive groups of pure data/value objects may share a module.
- Use only API data, or fail with an error. No defaulting to invented values.
- Multiple levels of error handling is a bug — no parse-then-fallback paths.
- Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- All tests live under `tests/`.
- Transcript prose is **opaque**: never regex it to derive crit counts, damage totals, or per-element breakdowns. The summary uses structured schema fields only.
- `started_at` is normalised through `isoparse(...).isoformat()` on **both** construction paths so the live and backfilled forms of the same fight produce byte-identical identity keys.

## File Structure

**Create:**
- `src/artifactsmmo_cli/ai/fight_record.py` — `FightDrop` + `FightRecord` value objects and their two constructors.
- `src/artifactsmmo_cli/tui/fight_format.py` — pure rendering functions (summary line, list row, transcript block).
- `src/artifactsmmo_cli/tui/screens/fight_screen.py` — the `FightScreen` modal.
- `tests/test_ai/test_fight_record.py`
- `tests/test_tui/test_fight_format.py`
- `tests/test_tui/test_fight_screen.py`

**Modify:**
- `src/artifactsmmo_cli/ai/actions/combat.py` — `last_fight` field + capture in `execute`.
- `src/artifactsmmo_cli/ai/cycle_snapshot.py` — `fight` field.
- `src/artifactsmmo_cli/ai/player.py:~1900` — the `isinstance` gate in `_notify_observer`.
- `src/artifactsmmo_cli/tui/widgets/log_pane.py` — append the summary line.
- `src/artifactsmmo_cli/tui/app.py` — binding, `_MODAL_SCREENS`, CSS, `update_snapshot`, fight deque, client.
- `src/artifactsmmo_cli/api_wrapper.py` — `get_character_logs`.
- `src/artifactsmmo_cli/commands/play.py:141` — pass the client to `WatchApp`.
- `tests/test_ai/test_actions_execute.py:74` — `make_fight_api_result` must produce real fight data.
- `tests/test_ai/test_actions.py:315-331` — the loss test's mock needs the same.
- `tests/test_tui/test_log_pane.py`, `tests/test_tui/test_app.py` — extend.

---

### Task 1: `FightRecord` value objects

**Files:**
- Create: `src/artifactsmmo_cli/ai/fight_record.py`
- Test: `tests/test_ai/test_fight_record.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces:
  - `FightDrop(code: str, quantity: int)` — frozen pydantic model.
  - `FightRecord(started_at: str, result: str, turns: int, opponent: str, logs: tuple[str, ...], hp_before: int | None, hp_after: int, xp: int, gold: int, drops: tuple[FightDrop, ...])` — frozen pydantic model.
  - `FightRecord.from_fight_response(data: CharacterFightDataSchema, character: str, hp_before: int) -> FightRecord`
  - `FightRecord.from_log_entry(content: dict[str, Any], character: str) -> FightRecord`

Both constructors raise `RuntimeError` when the named character has no result row.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_fight_record.py`:

```python
"""FightRecord construction from both API shapes."""

import datetime
from unittest.mock import MagicMock

import pytest

from artifactsmmo_cli.ai.fight_record import FightDrop, FightRecord

STARTED_AT = "2026-07-27T23:30:30.455000"

LOGS = [
    "Fight start: Robby HP: 485/485 vs Mushmush HP: 350/350",
    "Turn 1: Robby used fire attack and dealt 12 damage. Mushmush HP: 338/350",
]


def make_row(name, xp=45, gold=12, final_hp=275, drops=()):
    row = MagicMock()
    row.character_name = name
    row.xp = xp
    row.gold = gold
    row.final_hp = final_hp
    row.drops = [MagicMock(code=c, quantity=q) for c, q in drops]
    return row


def make_response(rows, result="win", turns=27, opponent="mushmush"):
    data = MagicMock()
    data.cooldown.started_at = datetime.datetime.fromisoformat(STARTED_AT)
    data.fight.result.value = result
    data.fight.turns = turns
    data.fight.opponent = opponent
    data.fight.logs = list(LOGS)
    data.fight.characters = rows
    return data


def make_content(rows, result="win", turns=27, opponent="mushmush"):
    return {
        "cooldown": {"started_at": STARTED_AT},
        "fight": {
            "result": result,
            "turns": turns,
            "opponent": opponent,
            "logs": list(LOGS),
            "characters": rows,
        },
    }


def content_row(name, xp=45, gold=12, final_hp=275, drops=()):
    return {
        "character_name": name,
        "xp": xp,
        "gold": gold,
        "final_hp": final_hp,
        "drops": [{"code": c, "quantity": q} for c, q in drops],
    }


class TestFromFightResponse:
    def test_reads_structured_fields(self):
        data = make_response([make_row("Robby", drops=(("mushmush_hat", 1),))])

        rec = FightRecord.from_fight_response(data, character="Robby", hp_before=485)

        assert rec.result == "win"
        assert rec.turns == 27
        assert rec.opponent == "mushmush"
        assert rec.logs == tuple(LOGS)
        assert rec.hp_before == 485
        assert rec.hp_after == 275
        assert rec.xp == 45
        assert rec.gold == 12
        assert rec.drops == (FightDrop(code="mushmush_hat", quantity=1),)

    def test_selects_participant_by_name_not_index(self):
        rows = [make_row("Wakko", final_hp=10), make_row("Robby", final_hp=275)]

        rec = FightRecord.from_fight_response(
            make_response(rows), character="Robby", hp_before=485)

        assert rec.hp_after == 275

    def test_raises_when_character_absent(self):
        data = make_response([make_row("Wakko")])

        with pytest.raises(RuntimeError, match="Robby"):
            FightRecord.from_fight_response(data, character="Robby", hp_before=485)

    def test_loss_result(self):
        data = make_response([make_row("Robby", final_hp=0)], result="loss", turns=41)

        rec = FightRecord.from_fight_response(data, character="Robby", hp_before=320)

        assert rec.result == "loss"
        assert rec.hp_after == 0


class TestFromLogEntry:
    def test_reads_structured_fields(self):
        content = make_content([content_row("Robby", drops=(("mushmush_hat", 1),))])

        rec = FightRecord.from_log_entry(content, character="Robby")

        assert rec.result == "win"
        assert rec.turns == 27
        assert rec.logs == tuple(LOGS)
        assert rec.hp_after == 275
        assert rec.drops == (FightDrop(code="mushmush_hat", quantity=1),)

    def test_hp_before_is_none_because_the_log_never_carries_it(self):
        content = make_content([content_row("Robby")])

        rec = FightRecord.from_log_entry(content, character="Robby")

        assert rec.hp_before is None

    def test_selects_participant_by_name_not_index(self):
        content = make_content([content_row("Wakko", final_hp=10),
                                content_row("Robby", final_hp=275)])

        rec = FightRecord.from_log_entry(content, character="Robby")

        assert rec.hp_after == 275

    def test_raises_when_character_absent(self):
        content = make_content([content_row("Wakko")])

        with pytest.raises(RuntimeError, match="Robby"):
            FightRecord.from_log_entry(content, character="Robby")


class TestIdentity:
    def test_started_at_is_identical_across_both_shapes(self):
        """The dedup key for merging session and backfilled fights."""
        live = FightRecord.from_fight_response(
            make_response([make_row("Robby")]), character="Robby", hp_before=485)
        backfilled = FightRecord.from_log_entry(
            make_content([content_row("Robby")]), character="Robby")

        assert live.started_at == backfilled.started_at

    def test_started_at_normalises_a_zulu_suffix(self):
        content = make_content([content_row("Robby")])
        content["cooldown"]["started_at"] = "2026-07-27T23:30:30.455000Z"
        live = FightRecord.from_fight_response(
            make_response([make_row("Robby")]), character="Robby", hp_before=485)

        backfilled = FightRecord.from_log_entry(content, character="Robby")

        assert backfilled.started_at.startswith("2026-07-27T23:30:30.455000")
        assert live.started_at.startswith("2026-07-27T23:30:30.455000")

    def test_record_is_frozen(self):
        rec = FightRecord.from_fight_response(
            make_response([make_row("Robby")]), character="Robby", hp_before=485)

        with pytest.raises(ValidationError):
            rec.turns = 5
```

Add `from pydantic import ValidationError` to the test module's imports.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_fight_record.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.fight_record'`

- [ ] **Step 3: Write the implementation**

Create `src/artifactsmmo_cli/ai/fight_record.py`:

```python
"""Fight transcript value objects.

The fight API returns a full per-turn transcript (`CharacterFightSchema.logs`)
that the bot otherwise discards. `FightRecord` is the frozen capture of one
fight, built from either the live fight response or a `/my/logs` history entry.

The transcript is treated as OPAQUE PROSE: it is server-rendered English and is
stored and displayed verbatim. Nothing is parsed out of it — every derived
number on this record comes from a structured schema field. See D4 in
docs/superpowers/specs/2026-07-27-fight-log-tui-design.md.
"""

from typing import Any

from dateutil.parser import isoparse
from pydantic import BaseModel, ConfigDict

from artifactsmmo_api_client.models.character_fight_data_schema import (
    CharacterFightDataSchema,
)


class FightDrop(BaseModel):
    """One item dropped by a fight."""

    model_config = ConfigDict(frozen=True)

    code: str
    quantity: int


class FightRecord(BaseModel):
    """One captured fight: structured outcome plus the verbatim transcript."""

    model_config = ConfigDict(frozen=True)

    # Server-side fight time, normalised through isoparse().isoformat(). This is
    # the record's IDENTITY: the live fight response and the corresponding
    # /my/logs entry carry the same value, so merging the two sources dedupes
    # exactly, with no clock-skew guessing and no content hashing.
    started_at: str
    result: str                      # "win" | "loss"
    turns: int
    opponent: str
    logs: tuple[str, ...]            # verbatim server prose
    # Pre-fight HP. Available live (the player's own state); NOT available from
    # /my/logs, which carries only final_hp — the starting value appears solely
    # in the "Fight start:" prose line, which we do not parse. Rendered as "?"
    # rather than defaulted, so a backfilled row never claims a number the API
    # did not give us.
    hp_before: int | None
    hp_after: int
    xp: int
    gold: int
    drops: tuple[FightDrop, ...]

    @classmethod
    def from_fight_response(
        cls, data: CharacterFightDataSchema, character: str, hp_before: int,
    ) -> "FightRecord":
        """Build from a live POST /my/{name}/action/fight response."""
        fight = data.fight
        row = next(
            (c for c in fight.characters if c.character_name == character), None)
        if row is None:
            raise RuntimeError(
                f"fight response has no result row for character {character!r}")
        return cls(
            started_at=isoparse(data.cooldown.started_at.isoformat()).isoformat(),
            result=fight.result.value,
            turns=fight.turns,
            opponent=fight.opponent,
            logs=tuple(fight.logs),
            hp_before=hp_before,
            hp_after=row.final_hp,
            xp=row.xp,
            gold=row.gold,
            drops=tuple(
                FightDrop(code=d.code, quantity=d.quantity) for d in row.drops),
        )

    @classmethod
    def from_log_entry(cls, content: dict[str, Any], character: str) -> "FightRecord":
        """Build from the `content` of a GET /my/logs/{name} entry of type fight.

        `LogSchema.content` is typed `Any` by the generated client and arrives as
        a plain dict, so this path indexes rather than attribute-accesses.
        """
        fight = content["fight"]
        row = next(
            (c for c in fight["characters"] if c["character_name"] == character), None)
        if row is None:
            raise RuntimeError(
                f"fight log entry has no result row for character {character!r}")
        return cls(
            started_at=isoparse(content["cooldown"]["started_at"]).isoformat(),
            result=fight["result"],
            turns=fight["turns"],
            opponent=fight["opponent"],
            logs=tuple(fight["logs"]),
            hp_before=None,
            hp_after=row["final_hp"],
            xp=row["xp"],
            gold=row["gold"],
            drops=tuple(
                FightDrop(code=d["code"], quantity=d["quantity"])
                for d in row["drops"]),
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_fight_record.py -v`
Expected: PASS, 12 tests.

- [ ] **Step 5: Typecheck and lint**

Run: `uv run mypy src/artifactsmmo_cli/ai/fight_record.py && uv run ruff check src/artifactsmmo_cli/ai/fight_record.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/fight_record.py tests/test_ai/test_fight_record.py
git commit -m "feat(fight-log): FightRecord value object for captured fights

Frozen capture of one fight from either the live fight response or a
/my/logs history entry. started_at is normalised identically on both
paths so the two sources dedupe exactly. Transcript stored verbatim;
every derived number comes from a structured schema field."
```

---

### Task 2: Capture the fight on `FightAction`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/combat.py:39-58` (field), `:184-203` (execute)
- Modify: `tests/test_ai/test_actions_execute.py:74-78` (fixture)
- Modify: `tests/test_ai/test_actions.py:315-331` (loss test mock)
- Test: `tests/test_ai/test_actions_execute.py` (new cases)

**Interfaces:**
- Consumes: `FightRecord.from_fight_response(data, character, hp_before)` from Task 1.
- Produces: `FightAction.last_fight: FightRecord | None` — set by `execute`, read by Task 3.

**Critical:** the existing `make_fight_api_result` helper builds `result.data.fight` as a bare `MagicMock`. Once `execute` constructs a real `FightRecord`, `fight.turns` would be a MagicMock and pydantic validation fails. Three call sites break: `test_actions_execute.py:154`, `test_actions_execute.py:167`, `test_actions.py:329`. Step 1 fixes the fixture *before* the implementation lands.

- [ ] **Step 1: Upgrade the shared fixture to produce real fight data**

Replace `make_fight_api_result` at `tests/test_ai/test_actions_execute.py:74-78`:

```python
def make_fight_api_result(char, *, result="win", turns=3, opponent="chicken",
                          xp=12, gold=3, final_hp=90,
                          started_at="2026-07-27T23:30:30.455000"):
    """Wrap a mock CharacterSchema as a fight API response.

    `data.fight` must carry REAL scalars, not bare MagicMocks: FightAction.execute
    builds a FightRecord from them and pydantic rejects a MagicMock int.
    """
    api_result = MagicMock()
    api_result.data = MagicMock()
    api_result.data.characters = [char]
    api_result.data.cooldown.started_at = datetime.datetime.fromisoformat(started_at)
    fight = api_result.data.fight
    # FightResult is a real `str, Enum`, so one assignment serves both consumers:
    # `== FightResult.LOSS` for execute's loss branch, and `.value` for FightRecord.
    fight.result = FightResult.WIN if result == "win" else FightResult.LOSS
    fight.turns = turns
    fight.opponent = opponent
    fight.logs = [f"Fight start: {char.name} HP: 100/100 vs Chicken HP: 60/60"]
    row = MagicMock()
    row.character_name = char.name
    row.xp = xp
    row.gold = gold
    row.final_hp = final_hp
    row.drops = []
    fight.characters = [row]
    return api_result
```

Add to the imports at the top of `tests/test_ai/test_actions_execute.py`:

```python
import datetime

from artifactsmmo_api_client.models.fight_result import FightResult
```

- [ ] **Step 2: Fix the loss test's inline mock**

At `tests/test_ai/test_actions.py:315-331`, replace the hand-rolled `fight_data` block with the shared fixture:

```python
    def test_execute_raises_on_loss(self):
        from tests.test_ai.test_actions_execute import (
            make_char_schema,
            make_fight_api_result,
        )

        action = FightAction(monster_code="yellow_slime", locations=frozenset([(1, 0)]))
        state = make_state(x=1, y=0, hp=100, max_hp=100, level=1)
        char = make_char_schema(x=1, y=0)
        api_result = make_fight_api_result(
            char, result="loss", turns=3, opponent="yellow_slime", final_hp=0)

        with patch("artifactsmmo_cli.ai.actions.combat.action_fight", return_value=api_result):
            with pytest.raises(RuntimeError, match="fight_lost"):
                action.execute(state, client=MagicMock())
```

Keep the existing test's name and surrounding class unchanged. The `from tests...import` inside the test body is pre-existing style at this call site; leave it as-is rather than restructuring the module.

- [ ] **Step 3: Write the failing capture tests**

Add to `tests/test_ai/test_actions_execute.py`, inside the existing fight-execute test class:

```python
    def test_execute_captures_the_fight_record(self):
        action = FightAction(monster_code="chicken", locations=frozenset([(0, 0)]))
        state = make_state(x=0, y=0, hp=100, max_hp=100)
        char = make_char_schema(x=0, y=0)

        with patch("artifactsmmo_cli.ai.actions.combat.action_fight",
                   return_value=make_fight_api_result(char, turns=7, final_hp=90)):
            action.execute(state, client=MagicMock())

        assert action.last_fight is not None
        assert action.last_fight.turns == 7
        assert action.last_fight.result == "win"
        assert action.last_fight.hp_before == 100
        assert action.last_fight.hp_after == 90
        assert action.last_fight.logs

    def test_execute_captures_the_record_before_raising_on_loss(self):
        """Losses are the most informative transcripts — they must survive the raise."""
        action = FightAction(monster_code="chicken", locations=frozenset([(0, 0)]))
        state = make_state(x=0, y=0, hp=100, max_hp=100)
        char = make_char_schema(x=0, y=0)

        with patch("artifactsmmo_cli.ai.actions.combat.action_fight",
                   return_value=make_fight_api_result(char, result="loss", final_hp=0)):
            with pytest.raises(RuntimeError, match="fight_lost"):
                action.execute(state, client=MagicMock())

        assert action.last_fight is not None
        assert action.last_fight.result == "loss"
        assert action.last_fight.hp_after == 0

    def test_execute_clears_a_stale_record_first(self):
        action = FightAction(monster_code="chicken", locations=frozenset([(0, 0)]))
        state = make_state(x=0, y=0, hp=100, max_hp=100)
        char = make_char_schema(x=0, y=0)

        with patch("artifactsmmo_cli.ai.actions.combat.action_fight",
                   return_value=make_fight_api_result(char, turns=7)):
            action.execute(state, client=MagicMock())
        with patch("artifactsmmo_cli.ai.actions.combat.action_fight", return_value=None):
            with pytest.raises(RuntimeError):
                action.execute(state, client=MagicMock())

        assert action.last_fight is None

    def test_last_fight_does_not_affect_equality_or_repr(self):
        """compare=False keeps a fought action equal to its freshly-planned twin;
        without it the planner would see its cached plan invalidated after every
        fight and re-search. repr=False keeps the trace/snapshot action string."""
        fought = FightAction(monster_code="chicken", locations=frozenset([(0, 0)]))
        fresh = FightAction(monster_code="chicken", locations=frozenset([(0, 0)]))
        state = make_state(x=0, y=0, hp=100, max_hp=100)
        char = make_char_schema(x=0, y=0)

        with patch("artifactsmmo_cli.ai.actions.combat.action_fight",
                   return_value=make_fight_api_result(char)):
            fought.execute(state, client=MagicMock())

        assert fought == fresh
        assert repr(fought) == repr(fresh)
```

- [ ] **Step 4: Run to verify the new tests fail**

Run: `uv run pytest tests/test_ai/test_actions_execute.py -v -k "fight"`
Expected: the four new tests FAIL with `AttributeError` on `last_fight` (or assert-None). Pre-existing fight tests PASS — the fixture change alone must not break them.

- [ ] **Step 5: Add the field**

In `src/artifactsmmo_cli/ai/actions/combat.py`, add to the imports:

```python
from artifactsmmo_cli.ai.fight_record import FightRecord
```

Add as the **last** field of `FightAction`, after `drop_farm` (line 58):

```python
    # The transcript of the fight this instance most recently executed, for the
    # TUI. Excluded from compare so a fought action stays equal to its freshly
    # planned twin (otherwise the planner reads its cached plan as invalidated
    # after every fight and re-searches), and from repr so the trace and
    # CycleSnapshot.action string are unchanged. Read by GamePlayer via an
    # isinstance gate, mirroring _last_grind_expansion / LevelSkill.
    last_fight: FightRecord | None = field(default=None, compare=False, repr=False)
```

- [ ] **Step 6: Capture in `execute`**

In `execute` (line 184), replace the body from the `action_fight` call through the LOSS raise:

```python
        self.last_fight = None
        result = action_fight(client=client, name=state.character, body=FightRequestSchema())
        result = Action._raise_for_error(result, f"Fight {self.monster_code}")
        # Capture BEFORE the loss raise below: GamePlayer catches that RuntimeError,
        # records outcome=error:fight_lost, and still reaches _notify_observer with
        # this same action object — so losses reach the TUI with no extra machinery.
        self.last_fight = FightRecord.from_fight_response(
            result.data, character=state.character, hp_before=state.hp)
        new_state = WorldState.from_character_schema(
            result.data.characters[0],
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
            raids=state.raids,
        )
        # Detect defeat: API returns 200 OK on loss; result.data.fight.result == LOSS.
        # Raise so the player loop records outcome=error:fight_lost and learning
        # doesn't fold near-death zero-XP cycles into action_cost/success_rate.
        if result.data.fight.result == FightResult.LOSS:
            raise RuntimeError(f"fight_lost: {self.monster_code} (turns={result.data.fight.turns})")
        return new_state
```

- [ ] **Step 7: Run the full action test suite**

Run: `uv run pytest tests/test_ai/test_actions_execute.py tests/test_ai/test_actions.py -v`
Expected: PASS, including the three previously-breaking sites.

- [ ] **Step 8: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/combat.py tests/test_ai/test_actions_execute.py tests/test_ai/test_actions.py
git commit -m "feat(fight-log): capture the transcript on FightAction

execute() built and threw away the fight response. It now stashes a
FightRecord on the action instance, before the existing loss raise so
losses are captured too. compare=False keeps a fought action equal to
its freshly planned twin; repr=False keeps the trace string intact.

Existing fight fixtures upgraded to real scalars — a bare MagicMock
fight no longer survives FightRecord validation."
```

---

### Task 3: Put the record on `CycleSnapshot`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/cycle_snapshot.py` (end of `CycleSnapshot`)
- Modify: `src/artifactsmmo_cli/ai/player.py` (`_notify_observer`, ~line 1900 and the `CycleSnapshot(...)` construction ~line 1961)
- Test: `tests/test_ai/test_player_fight_snapshot.py` (create)

**Interfaces:**
- Consumes: `FightAction.last_fight` from Task 2.
- Produces: `CycleSnapshot.fight: FightRecord | None` — read by Tasks 4 and 5.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ai/test_player_fight_snapshot.py`:

```python
"""The captured fight reaches the observer's CycleSnapshot."""

from unittest.mock import MagicMock

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.fight_record import FightRecord

RECORD = FightRecord(
    started_at="2026-07-27T23:30:30.455000",
    result="win",
    turns=27,
    opponent="mushmush",
    logs=("Fight start: Robby HP: 485/485 vs Mushmush HP: 350/350",),
    hp_before=485,
    hp_after=275,
    xp=45,
    gold=12,
    drops=(),
)


def notify(player, action):
    """Drive _notify_observer and return the snapshot handed to the observer."""
    seen = []
    player.set_cycle_observer(seen.append)
    player._notify_observer("Goal()", repr(action), "ok", [], action=action)
    return seen[0]


class TestFightOnSnapshot:
    def test_fight_action_record_rides_the_snapshot(self, player_with_state):
        action = FightAction(monster_code="mushmush")
        action.last_fight = RECORD

        snap = notify(player_with_state, action)

        assert snap.fight == RECORD

    def test_non_fight_action_leaves_it_none(self, player_with_state):
        snap = notify(player_with_state, MoveAction(x=1, y=1))

        assert snap.fight is None

    def test_fight_action_without_a_record_leaves_it_none(self, player_with_state):
        snap = notify(player_with_state, FightAction(monster_code="mushmush"))

        assert snap.fight is None
```

Use the existing player fixture convention in `tests/test_ai/`. If no `player_with_state` fixture exists, build the player the same way the nearest existing `_notify_observer` test does — check `tests/test_ai/test_player_focus_ledger.py`, which already exercises `_notify_observer` and its snapshot fields, and copy its setup verbatim rather than inventing a new one.

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ai/test_player_fight_snapshot.py -v`
Expected: FAIL — `CycleSnapshot` has no field `fight` (pydantic ignores it, so `snap.fight` raises `AttributeError`).

- [ ] **Step 3: Add the snapshot field**

At the end of `CycleSnapshot` in `src/artifactsmmo_cli/ai/cycle_snapshot.py`, after `interleave_seats`:

```python
    # The transcript of the fight executed this cycle, when the action was a
    # FightAction that reached the server. None on every other cycle. Drives the
    # log pane's summary line and the fight modal.
    fight: FightRecord | None = None
```

Add the import at the top of the module:

```python
from artifactsmmo_cli.ai.fight_record import FightRecord
```

- [ ] **Step 4: Wire the gate in `_notify_observer`**

In `src/artifactsmmo_cli/ai/player.py`, beside the existing grind gate (~line 1900):

```python
        grind_children = self._last_grind_expansion if isinstance(action, LevelSkill) else ()
        # Same shape as the grind gate above: only a fight cycle has a captured
        # transcript, and gating on the action type keeps a prior fight's record
        # from leaking onto an unrelated cycle.
        fight_record = action.last_fight if isinstance(action, FightAction) else None
```

Add `fight=fight_record,` to the `CycleSnapshot(...)` construction (~line 1961), next to `grind_expansion=grind_children,`.

Add the import at the top of `player.py`:

```python
from artifactsmmo_cli.ai.actions.combat import FightAction
```

If `player.py` already imports from `ai.actions.combat`, extend that import rather than adding a second line.

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_ai/test_player_fight_snapshot.py -v`
Expected: PASS, 3 tests.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/cycle_snapshot.py src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player_fight_snapshot.py
git commit -m "feat(fight-log): carry the fight record on CycleSnapshot

isinstance gate in _notify_observer mirrors the existing grind-expansion
gate, so a prior fight's transcript cannot leak onto an unrelated cycle."
```

---

### Task 4: Summary line in the live log pane

**Files:**
- Create: `src/artifactsmmo_cli/tui/fight_format.py`
- Modify: `src/artifactsmmo_cli/tui/widgets/log_pane.py`
- Test: `tests/test_tui/test_fight_format.py` (create), `tests/test_tui/test_log_pane.py` (extend)

**Interfaces:**
- Consumes: `CycleSnapshot.fight` from Task 3.
- Produces:
  - `fight_summary_line(rec: FightRecord) -> str`
  - `fight_row_label(rec: FightRecord) -> str`
  - `fight_detail_lines(rec: FightRecord) -> list[str]`

All three are pure and return Rich markup. Task 5 consumes the latter two.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tui/test_fight_format.py`:

```python
"""Pure fight renderers — no Textual app needed."""

from artifactsmmo_cli.ai.fight_record import FightDrop, FightRecord
from artifactsmmo_cli.tui.fight_format import (
    fight_detail_lines,
    fight_row_label,
    fight_summary_line,
)


def make_record(**overrides) -> FightRecord:
    base = dict(
        started_at="2026-07-27T23:30:30.455000",
        result="win",
        turns=27,
        opponent="mushmush",
        logs=(
            "Fight start: Robby HP: 485/485 vs Mushmush HP: 350/350",
            "Turn 13: Robby used fire attack and dealt 18 damage (Critical strike). "
            "Mushmush HP: 188/350",
        ),
        hp_before=485,
        hp_after=275,
        xp=45,
        gold=12,
        drops=(FightDrop(code="mushmush_hat", quantity=1),),
    )
    base.update(overrides)
    return FightRecord(**base)


class TestSummaryLine:
    def test_win_shows_structured_fields(self):
        line = fight_summary_line(make_record())

        assert "win" in line
        assert "27t" in line
        assert "485->275" in line
        assert "xp 45" in line
        assert "gold 12" in line
        assert "mushmush_hat x1" in line

    def test_loss_is_rendered_red(self):
        line = fight_summary_line(make_record(result="loss", hp_after=0))

        assert "[red]loss[/red]" in line

    def test_win_is_rendered_green(self):
        assert "[green]win[/green]" in fight_summary_line(make_record())

    def test_no_drops_omits_the_drops_clause(self):
        assert "drops" not in fight_summary_line(make_record(drops=()))

    def test_unknown_pre_fight_hp_renders_as_a_question_mark(self):
        """Backfilled records have no starting HP; never invent one."""
        line = fight_summary_line(make_record(hp_before=None))

        assert "?->275" in line
        assert "0->275" not in line


class TestRowLabel:
    def test_includes_result_time_opponent_and_turns(self):
        label = fight_row_label(make_record())

        assert "win" in label
        assert "23:30:30" in label
        assert "mushmush" in label
        assert "27t" in label


class TestDetailLines:
    def test_header_then_verbatim_transcript(self):
        lines = fight_detail_lines(make_record())

        assert "mushmush" in lines[0]
        assert "27" in lines[0]
        assert lines[-1].endswith("Mushmush HP: 188/350")

    def test_transcript_is_not_reformatted(self):
        rec = make_record()
        lines = fight_detail_lines(rec)

        assert rec.logs[0] in "\n".join(lines)

    def test_square_brackets_are_escaped_for_rich_markup(self):
        """RichLog(markup=True) would treat a literal '[' as markup."""
        rec = make_record(logs=("Turn 1: Robby used [special] attack.",))

        joined = "\n".join(fight_detail_lines(rec))

        assert "\\[special]" in joined

    def test_critical_strike_is_emphasised(self):
        joined = "\n".join(fight_detail_lines(make_record()))

        assert "[bold]Critical strike[/bold]" in joined

    def test_emphasis_is_a_plain_substring_search_that_can_miss(self):
        """No parsing: reworded server text simply renders unemphasised."""
        rec = make_record(logs=("Turn 1: Robby landed a devastating blow.",))

        joined = "\n".join(fight_detail_lines(rec))

        assert "bold" not in joined
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_fight_format.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.tui.fight_format'`

- [ ] **Step 3: Write the implementation**

Create `src/artifactsmmo_cli/tui/fight_format.py`:

```python
"""Rich-markup renderers for a captured fight.

The transcript is server-rendered English and is emitted VERBATIM. The only
styling applied to it is a plain substring search for a couple of notable
phrases, which silently does nothing if the server rewords them. Nothing here
parses the prose — every number in the summary comes from a structured field on
`FightRecord`.
"""

from rich.markup import escape

from artifactsmmo_cli.ai.fight_record import FightRecord

_RESULT_COLOR = {"win": "green", "loss": "red"}

_EMPHASISED = ("Critical strike", "Blocked")
"""Phrases wrapped in [bold] when present. A plain substring search: if the
server rewords them the line renders unemphasised, which is the intended
degradation. Never grows into a parser."""


def _result_markup(rec: FightRecord) -> str:
    color = _RESULT_COLOR[rec.result]
    return f"[{color}]{rec.result}[/{color}]"


def _hp_span(rec: FightRecord) -> str:
    """`485->275`, or `?->275` when the source had no starting HP (backfill)."""
    before = "?" if rec.hp_before is None else str(rec.hp_before)
    return f"{before}->{rec.hp_after}"


def _drops_clause(rec: FightRecord) -> str:
    if not rec.drops:
        return ""
    drops = " ".join(f"{d.code} x{d.quantity}" for d in rec.drops)
    return f"  drops {drops}"


def fight_summary_line(rec: FightRecord) -> str:
    """The one dim line the live log pane appends under a fight cycle."""
    return (
        f"[dim]   fight:[/dim] {_result_markup(rec)} {rec.turns}t  "
        f"hp {_hp_span(rec)}  xp {rec.xp}  gold {rec.gold}{_drops_clause(rec)}"
    )


def fight_row_label(rec: FightRecord) -> str:
    """One row in the fight modal's list."""
    clock = rec.started_at[11:19]
    return (
        f"{_result_markup(rec)}  [dim]{clock}[/dim]  "
        f"{rec.opponent}  {rec.turns}t  hp {_hp_span(rec)}"
    )


def _emphasise(line: str) -> str:
    """Escape the line for Rich, then bold any notable phrase present."""
    rendered = escape(line)
    for phrase in _EMPHASISED:
        if phrase in rendered:
            rendered = rendered.replace(phrase, f"[bold]{phrase}[/bold]")
    return rendered


def fight_detail_lines(rec: FightRecord) -> list[str]:
    """Header plus the verbatim transcript, ready for a RichLog."""
    header = (
        f"{rec.opponent}  {_result_markup(rec)}  {rec.turns} turns  "
        f"hp {_hp_span(rec)}  xp {rec.xp}  gold {rec.gold}{_drops_clause(rec)}"
    )
    return [header, ""] + [_emphasise(line) for line in rec.logs]
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_tui/test_fight_format.py -v`
Expected: PASS, 12 tests.

- [ ] **Step 5: Write the failing log-pane test**

Add to `tests/test_tui/test_log_pane.py`:

```python
class TestFightSummary:
    def test_fight_cycle_appends_a_summary_line(self):
        from artifactsmmo_cli.ai.fight_record import FightRecord

        rec = FightRecord(
            started_at="2026-07-27T23:30:30.455000", result="win", turns=27,
            opponent="mushmush", logs=("Fight start: ...",), hp_before=485,
            hp_after=275, xp=45, gold=12, drops=(),
        )
        lines = build_log_lines(_snap(action="Fight(mushmush)", fight=rec))

        assert any("fight:" in line and "27t" in line for line in lines)

    def test_non_fight_cycle_appends_nothing(self):
        lines = build_log_lines(_snap())

        assert not any("fight:" in line for line in lines)
```

Move the `FightRecord` import to the top of the test module — no inline imports.

- [ ] **Step 6: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_log_pane.py -v -k Fight`
Expected: FAIL — no summary line.

- [ ] **Step 7: Append the line in `build_log_lines`**

In `src/artifactsmmo_cli/tui/widgets/log_pane.py`, add the import:

```python
from artifactsmmo_cli.tui.fight_format import fight_summary_line
```

and immediately before the final `return lines`, after the `grind_chain_lines` extension:

```python
    if snap.fight is not None:
        lines.append(fight_summary_line(snap.fight))
```

Extend the `build_log_lines` docstring to mention the fight summary alongside the existing 'why' line and grind chain.

- [ ] **Step 8: Run to verify it passes**

Run: `uv run pytest tests/test_tui/test_log_pane.py tests/test_tui/test_fight_format.py -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/artifactsmmo_cli/tui/fight_format.py src/artifactsmmo_cli/tui/widgets/log_pane.py tests/test_tui/test_fight_format.py tests/test_tui/test_log_pane.py
git commit -m "feat(fight-log): summary line in the live log pane

One dim line per fight cycle, built only from structured fields. The
transcript renderer escapes for Rich markup and emphasises notable
phrases by plain substring search, degrading to unstyled text if the
server rewords them."
```

---

### Task 5: The fight modal

**Files:**
- Create: `src/artifactsmmo_cli/tui/screens/fight_screen.py`
- Modify: `src/artifactsmmo_cli/tui/app.py:76-167`
- Test: `tests/test_tui/test_fight_screen.py` (create), `tests/test_tui/test_app.py` (extend)

**Interfaces:**
- Consumes: `fight_row_label`, `fight_detail_lines` (Task 4); `CycleSnapshot.fight` (Task 3).
- Produces:
  - `FightScreen(records: Iterable[FightRecord], character: str, fetch_older: Callable[[int], list[FightRecord]] | None = None)`
  - `FightScreen.update_snapshot(snap: CycleSnapshot) -> None`
  - `FightScreen.merge(records: Iterable[FightRecord]) -> None` — dedupes on `started_at`, sorts descending.
  - `WatchApp._fights: deque[FightRecord]`

`fetch_older` is wired in Task 6; this task passes `None` and the backfill key is inert.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tui/test_fight_screen.py`:

```python
"""FightScreen list/detail behaviour — pure logic, no running app."""

from artifactsmmo_cli.ai.fight_record import FightRecord
from artifactsmmo_cli.tui.screens.fight_screen import FightScreen


def make_record(started_at="2026-07-27T23:30:30.455000", **overrides) -> FightRecord:
    base = dict(
        started_at=started_at, result="win", turns=27, opponent="mushmush",
        logs=("Fight start: Robby HP: 485/485 vs Mushmush HP: 350/350",),
        hp_before=485, hp_after=275, xp=45, gold=12, drops=(),
    )
    base.update(overrides)
    return FightRecord(**base)


class TestOrdering:
    def test_records_are_newest_first(self):
        older = make_record("2026-07-27T22:00:00.000000")
        newer = make_record("2026-07-27T23:00:00.000000")

        screen = FightScreen([older, newer], character="Robby")

        assert [r.started_at for r in screen.records] == [
            newer.started_at, older.started_at]


class TestMerge:
    def test_dedupes_on_started_at(self):
        rec = make_record()
        screen = FightScreen([rec], character="Robby")

        screen.merge([make_record(rec.started_at, turns=99)])

        assert len(screen.records) == 1
        assert screen.records[0].turns == 27

    def test_keeps_distinct_fights(self):
        screen = FightScreen([make_record("2026-07-27T23:00:00.000000")],
                             character="Robby")

        screen.merge([make_record("2026-07-27T22:00:00.000000")])

        assert len(screen.records) == 2

    def test_merged_records_are_resorted(self):
        screen = FightScreen([make_record("2026-07-27T22:00:00.000000")],
                             character="Robby")

        screen.merge([make_record("2026-07-27T23:00:00.000000")])

        assert screen.records[0].started_at.startswith("2026-07-27T23:00")


class TestSessionBoundary:
    def test_session_records_are_tracked_separately_from_backfilled(self):
        session = make_record("2026-07-27T23:00:00.000000")
        screen = FightScreen([session], character="Robby")

        screen.merge([make_record("2026-07-27T22:00:00.000000")])

        assert screen.session_started_at == session.started_at


class TestDetail:
    def test_detail_renders_the_selected_record(self):
        screen = FightScreen([make_record()], character="Robby")

        lines = screen.detail_lines(0)

        assert "mushmush" in lines[0]
        assert any("Fight start" in line for line in lines)

    def test_detail_of_an_empty_list_is_a_placeholder(self):
        screen = FightScreen([], character="Robby")

        assert screen.detail_lines(0) == ["No fights recorded yet."]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_fight_screen.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the screen**

Create `src/artifactsmmo_cli/tui/screens/fight_screen.py`:

```python
"""Browsable per-turn fight transcripts (toggled with 'f').

Two panes: the fight list on the left, the selected fight's verbatim transcript
on the right. Session fights arrive on CycleSnapshot and need no network; older
fights are pulled from GET /my/logs/{name} on demand and merged in, deduped on
the server-side `started_at` the two sources share.
"""

from collections.abc import Callable, Iterable
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import ListItem, ListView, RichLog, Static

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.fight_record import FightRecord
from artifactsmmo_cli.tui.fight_format import fight_detail_lines, fight_row_label


class FightScreen(Screen[None]):
    """Modal fight browser. Dismiss with 'f' or Escape."""

    DEFAULT_CSS = """
    #fight-modal #fight-cols { width: 1fr; height: 1fr; }
    #fight-modal #fight-list { width: 44; border: solid white; }
    #fight-modal #fight-detail { width: 1fr; border: solid white; }
    #fight-modal #fight-status { height: 1; }
    """

    BINDINGS = [
        ("escape", "dismiss", "Back"),
        ("f", "dismiss", "Back"),
        ("m", "load_older", "Load older"),
    ]

    def __init__(self, records: Iterable[FightRecord], character: str,
                 fetch_older: Callable[[int], list[FightRecord]] | None = None,
                 **kwargs: Any) -> None:
        super().__init__(id="fight-modal", **kwargs)
        self._character = character
        self._fetch_older = fetch_older
        self._next_page = 1
        self.records: list[FightRecord] = []
        # The newest record present at construction: the boundary between what
        # this session watched and what was pulled from the server log.
        self.session_started_at: str | None = None
        self.merge(records)
        self.session_started_at = (
            self.records[0].started_at if self.records else None)

    def merge(self, records: Iterable[FightRecord]) -> None:
        """Add records, dropping any whose `started_at` is already present, and
        re-sort newest first. Existing records win: a session capture carries
        `hp_before`, which the backfilled form of the same fight cannot."""
        seen = {r.started_at for r in self.records}
        for rec in records:
            if rec.started_at not in seen:
                self.records.append(rec)
                seen.add(rec.started_at)
        self.records.sort(key=lambda r: r.started_at, reverse=True)

    def detail_lines(self, index: int) -> list[str]:
        if not self.records:
            return ["No fights recorded yet."]
        return fight_detail_lines(self.records[index])

    def compose(self) -> ComposeResult:
        with Horizontal(id="fight-cols"):
            yield ListView(id="fight-list")
            yield RichLog(wrap=True, markup=True, id="fight-detail")
        yield Static("", id="fight-status")

    def on_mount(self) -> None:
        self._refresh_list()
        self._render_detail(0)

    def _refresh_list(self) -> None:
        listing = self.query_one("#fight-list", ListView)
        listing.clear()
        for rec in self.records:
            listing.append(ListItem(Static(fight_row_label(rec), markup=True)))

    def _render_detail(self, index: int) -> None:
        detail = self.query_one("#fight-detail", RichLog)
        detail.clear()
        for line in self.detail_lines(index):
            detail.write(line)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.index is not None:
            self._render_detail(event.list_view.index)

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        """A fight landed while the modal was open."""
        if snap.fight is None:
            return
        self.merge([snap.fight])
        self.session_started_at = self.records[0].started_at
        self._refresh_list()

    def action_load_older(self) -> None:
        """Wired in Task 6; inert until a fetcher is supplied."""
        if self._fetch_older is None:
            return
        self._load_older_worker()

    def _load_older_worker(self) -> None:
        raise NotImplementedError("supplied in Task 6")
```

Note on `merge`: `_load_older_worker` raising `NotImplementedError` is a deliberate seam replaced in Task 6, not a placeholder — Task 6's first step removes it. Do not ship the plan past Task 6 with it in place.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_tui/test_fight_screen.py -v`
Expected: PASS, 8 tests.

- [ ] **Step 5: Write the failing app-wiring tests**

Add to `tests/test_tui/test_app.py`:

```python
class TestFightModal:
    def test_f_is_bound_to_the_fight_toggle(self):
        assert any(b[0] == "f" and b[1] == "toggle_fight" for b in WatchApp.BINDINGS)

    def test_fight_screen_is_a_registered_modal(self):
        from artifactsmmo_cli.tui.screens.fight_screen import FightScreen

        assert FightScreen in WatchApp._MODAL_SCREENS

    def test_fight_records_are_kept_in_a_dedicated_deque(self):
        """Not a filter over _recent_snapshots: that deque is capped at 500
        CYCLES, so unrelated cycles would silently evict old fights."""
        app = WatchApp(character="Robby", game_data=make_game_data())
        rec = make_fight_record()

        app._store_snapshot(_snap(fight=rec))
        app._store_snapshot(_snap())

        assert list(app._fights) == [rec]
```

Move both imports to the top of the module. Reuse the existing `make_game_data` / `_snap` helpers in `test_app.py`; add a `make_fight_record()` helper alongside them mirroring the one in `test_fight_screen.py`.

- [ ] **Step 6: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_app.py -v -k Fight`
Expected: FAIL — no `f` binding, `FightScreen` absent from `_MODAL_SCREENS`, no `_fights`.

- [ ] **Step 7: Wire the app**

In `src/artifactsmmo_cli/tui/app.py`:

Add the import:

```python
from artifactsmmo_cli.tui.screens.fight_screen import FightScreen
from artifactsmmo_cli.ai.fight_record import FightRecord
```

Add a buffer constant beside `LOG_BUFFER`:

```python
    FIGHT_BUFFER = 200
```

Add the binding to `BINDINGS`:

```python
        ("f", "toggle_fight", "Fights"),
```

In `__init__`, after `_recent_snapshots`:

```python
        # Fights get their OWN buffer rather than being filtered out of
        # _recent_snapshots: that deque is capped at LOG_BUFFER *cycles*, so a
        # busy stretch of non-fight cycles would silently evict old fights.
        self._fights: deque[FightRecord] = deque(maxlen=self.FIGHT_BUFFER)
```

In `_store_snapshot`:

```python
    def _store_snapshot(self, snap: CycleSnapshot) -> None:
        self._last_snapshot = snap
        self._recent_snapshots.append(snap)
        if snap.fight is not None:
            self._fights.append(snap.fight)
```

Extend `_MODAL_SCREENS` and the comment above it (it says "four modal screens"; make it five):

```python
    _MODAL_SCREENS = (CharacterScreen, LogScreen, PlanScreen, EncyclopediaScreen, FightScreen)
```

Extend the live-update tuple in `update_snapshot`:

```python
        if isinstance(top, (CharacterScreen, LogScreen, PlanScreen, FightScreen)):
            top.update_snapshot(snap)
```

Add the CSS modal id to the existing `layout: vertical` reset rule:

```css
    #character-modal, #log-modal, #plan-modal, #encyclopedia-modal, #fight-modal {
        layout: vertical;
    }
```

Add the action beside the others:

```python
    def action_toggle_fight(self) -> None:
        self._open_modal(
            FightScreen,
            lambda: FightScreen(self._fights, character=self._character),
        )
```

- [ ] **Step 8: Run the TUI suite**

Run: `uv run pytest tests/test_tui/ -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/artifactsmmo_cli/tui/screens/fight_screen.py src/artifactsmmo_cli/tui/app.py tests/test_tui/test_fight_screen.py tests/test_tui/test_app.py
git commit -m "feat(fight-log): browsable fight modal on 'f'

Two-pane master/detail. Fights get a dedicated deque rather than a
filter over _recent_snapshots, which is capped in cycles and would
evict them silently. Backfill key is present but inert until the
fetcher lands."
```

---

### Task 6: Backfill older fights from `/my/logs`

**Files:**
- Modify: `src/artifactsmmo_cli/api_wrapper.py`
- Modify: `src/artifactsmmo_cli/tui/screens/fight_screen.py`
- Modify: `src/artifactsmmo_cli/tui/app.py`
- Modify: `src/artifactsmmo_cli/commands/play.py:138-141`
- Test: `tests/test_tui/test_fight_screen.py` (extend), `tests/test_api_wrapper.py` (extend if present, else create `tests/test_api_wrapper_logs.py`)

**Interfaces:**
- Consumes: `FightRecord.from_log_entry` (Task 1), `FightScreen(fetch_older=...)` (Task 5).
- Produces: `APIWrapper.get_character_logs(name: str, page: int = 1, size: int = 100) -> Any`; `WatchApp._fetch_older_fights(page: int) -> list[FightRecord]`.

- [ ] **Step 1: Write the failing wrapper test**

Add to the API wrapper tests:

```python
class TestGetCharacterLogs:
    def test_delegates_to_the_generated_client(self):
        client = MagicMock()
        wrapper = APIWrapper(client)

        with patch("artifactsmmo_cli.api_wrapper.get_character_logs_sync") as sync:
            wrapper.get_character_logs("Robby", page=2, size=100)

        sync.assert_called_once_with(client=client, name="Robby", page=2, size=100)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest -k GetCharacterLogs -v`
Expected: FAIL — `APIWrapper` has no `get_character_logs`.

- [ ] **Step 3: Add the wrapper method**

In `src/artifactsmmo_cli/api_wrapper.py`, add the import beside the other generated-client imports:

```python
from artifactsmmo_api_client.api.my_characters.get_character_logs_my_logs_name_get import (
    sync as get_character_logs_sync,
)
```

and the method beside `get_character`:

```python
    def get_character_logs(self, name: str, page: int = 1, size: int = 100) -> Any:
        return get_character_logs_sync(client=self._client, name=name, page=page, size=size)
```

- [ ] **Step 4: Write the failing backfill tests**

Add to `tests/test_tui/test_fight_screen.py`:

```python
class TestBackfill:
    def test_load_older_merges_fetched_records(self):
        fetched = [make_record("2026-07-27T22:00:00.000000")]
        screen = FightScreen([make_record("2026-07-27T23:00:00.000000")],
                             character="Robby", fetch_older=lambda page: fetched)

        screen.load_older_sync()

        assert len(screen.records) == 2

    def test_load_older_advances_the_page(self):
        pages = []
        screen = FightScreen([], character="Robby",
                             fetch_older=lambda page: pages.append(page) or [])

        screen.load_older_sync()
        screen.load_older_sync()

        assert pages == [1, 2]

    def test_load_older_without_a_fetcher_is_inert(self):
        screen = FightScreen([make_record()], character="Robby")

        screen.load_older_sync()

        assert len(screen.records) == 1

    def test_status_reports_an_empty_page(self):
        screen = FightScreen([], character="Robby", fetch_older=lambda page: [])

        screen.load_older_sync()

        assert "no older" in screen.status_text.lower()

    def test_status_distinguishes_a_failed_request_from_an_empty_one(self):
        """An empty result and a failed request must not look the same."""
        def boom(page):
            raise RuntimeError("HTTP 500")

        screen = FightScreen([], character="Robby", fetch_older=boom)

        screen.load_older_sync()

        assert "HTTP 500" in screen.status_text
        assert "no older" not in screen.status_text.lower()
```

And the conversion test for the app-side fetcher, in `tests/test_tui/test_app.py`:

```python
class TestFightBackfill:
    def test_fetcher_keeps_only_fight_entries_and_converts_them(self):
        from artifactsmmo_api_client.models.log_type import LogType

        fight_entry = MagicMock()
        fight_entry.type_ = LogType.FIGHT
        fight_entry.content = {
            "cooldown": {"started_at": "2026-07-27T22:00:00.000000"},
            "fight": {
                "result": "win", "turns": 5, "opponent": "chicken",
                "logs": ["Fight start: Robby HP: 100/100 vs Chicken HP: 60/60"],
                "characters": [{"character_name": "Robby", "xp": 5, "gold": 1,
                                "final_hp": 95, "drops": []}],
            },
        }
        other = MagicMock()
        other.type_ = LogType.MOVEMENT
        page = MagicMock()
        page.data = [fight_entry, other]
        api = MagicMock()
        api.get_character_logs.return_value = page
        app = WatchApp(character="Robby", game_data=make_game_data(), api=api)

        records = app._fetch_older_fights(1)

        assert len(records) == 1
        assert records[0].opponent == "chicken"
        assert records[0].hp_before is None
```

- [ ] **Step 5: Run to verify they fail**

Run: `uv run pytest tests/test_tui/test_fight_screen.py tests/test_tui/test_app.py -v -k "Backfill or older"`
Expected: FAIL — `load_older_sync` / `status_text` / `_fetch_older_fights` do not exist; `WatchApp` takes no `api`.

- [ ] **Step 6: Implement the screen side**

In `src/artifactsmmo_cli/tui/screens/fight_screen.py`, replace `action_load_older` and delete `_load_older_worker` entirely:

```python
    def action_load_older(self) -> None:
        """Fetch the next page of server history off the event loop.

        The generated client call is synchronous; running it inline would freeze
        the UI for the duration of the request.
        """
        self.run_worker(self.load_older_sync, thread=True)

    def load_older_sync(self) -> None:
        """Fetch, convert, merge, and report. Safe to call directly in tests."""
        if self._fetch_older is None:
            return
        page = self._next_page
        try:
            fetched = self._fetch_older(page)
        except RuntimeError as exc:
            self._set_status(f"backfill failed: {exc}")
            return
        self._next_page = page + 1
        if not fetched:
            self._set_status(f"no older fights on page {page}")
            return
        before = len(self.records)
        self.merge(fetched)
        self._set_status(f"loaded {len(self.records) - before} older fights")
        self._refresh_list()
```

Add the status field. In `__init__`, before `self.merge(records)`:

```python
        self.status_text = ""
```

and the setter:

```python
    def _set_status(self, text: str) -> None:
        self.status_text = text
        if self.is_mounted:
            self.query_one("#fight-status", Static).update(text)
```

Catching `RuntimeError` here is the single error-handling level for the backfill: the failure is surfaced in the status bar and the page counter is *not* advanced, so pressing `m` again retries the same page. There is no fallback path and no silent empty list — an empty page and a failed request produce visibly different text.

- [ ] **Step 7: Implement the app side**

In `src/artifactsmmo_cli/tui/app.py`, add imports:

```python
from artifactsmmo_api_client.models.log_type import LogType

from artifactsmmo_cli.api_wrapper import APIWrapper
```

Change `__init__`:

```python
    def __init__(self, character: str, game_data: GameData,
                 api: APIWrapper | None = None) -> None:
```

and store it:

```python
        self._api = api
```

Add the fetcher:

```python
    def _fetch_older_fights(self, page: int) -> list[FightRecord]:
        """One page of server history, fights only, newest-first as returned."""
        if self._api is None:
            return []
        result = self._api.get_character_logs(self._character, page=page, size=100)
        return [
            FightRecord.from_log_entry(entry.content, character=self._character)
            for entry in result.data
            if entry.type_ == LogType.FIGHT
        ]
```

and pass it to the screen:

```python
    def action_toggle_fight(self) -> None:
        self._open_modal(
            FightScreen,
            lambda: FightScreen(self._fights, character=self._character,
                                fetch_older=self._fetch_older_fights),
        )
```

- [ ] **Step 8: Thread the client through `play.py`**

At `src/artifactsmmo_cli/commands/play.py:141`:

```python
    app = WatchApp(character=character, game_data=player.game_data,
                   api=APIWrapper(client))
```

Add the import at the top of `play.py`:

```python
from artifactsmmo_cli.api_wrapper import APIWrapper
```

`client` is already in scope at line 138 as `ClientManager().client`.

- [ ] **Step 9: Run the full affected suites**

Run: `uv run pytest tests/test_tui/ tests/test_ai/test_fight_record.py -v`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add src/artifactsmmo_cli/api_wrapper.py src/artifactsmmo_cli/tui/screens/fight_screen.py src/artifactsmmo_cli/tui/app.py src/artifactsmmo_cli/commands/play.py tests/
git commit -m "feat(fight-log): backfill older fights from /my/logs

'm' pulls the next page off the event loop via a thread worker, keeps
fight entries, and merges them deduped on started_at. A failed request
and an empty page report differently, and a failure does not advance
the page counter."
```

---

### Task 7: Full gate and live verification

**Files:** none created; this task verifies.

**Interfaces:** consumes everything above.

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest tests/ -n auto`
Expected: 0 failures, 0 errors, 0 skipped.

- [ ] **Step 2: Check coverage of every new file**

Run:

```bash
uv run pytest tests/ -n auto --cov=src/artifactsmmo_cli/ai/fight_record.py \
  --cov=src/artifactsmmo_cli/tui/fight_format.py \
  --cov=src/artifactsmmo_cli/tui/screens/fight_screen.py \
  --cov-report=term-missing
```

Expected: 100% on all three. Any uncovered line gets a test, not a pragma.

- [ ] **Step 3: Typecheck and lint**

Run: `uv run mypy src/artifactsmmo_cli && uv run ruff check src/artifactsmmo_cli`
Expected: no errors.

- [ ] **Step 4: Run the formal gate**

Run: `bash formal/gate.sh > /tmp/gate.log 2>&1; echo "rc=$?"`
Expected: `rc=0`. Read the log file — do NOT pipe the gate through `tail`, which reports the tail's exit code and can turn a visible `GATE FAIL` into `rc=0`.

The gate should be unaffected: no planner state, action cost, applicability, or goal-ranking changes, and `WorldState` is untouched. If it is red, that is a signal the capture leaked into decision logic — investigate rather than suppress.

- [ ] **Step 5: Verify runtime activation**

Green tests do not prove the feature fires. Run the bot against the live API and confirm with your own eyes:

```bash
uv run artifactsmmo play Robby
```

Check, in order:
1. A fight cycle in the log pane shows the `fight: win Nt hp A->B ...` summary line.
2. `f` opens the modal, the fight list is populated, and arrow keys re-render the transcript.
3. The transcript matches the fight that just happened, verbatim.
4. `m` loads older fights and the `--- session ---` boundary sits in the right place.
5. A loss (fight something above your level, or wait for one) also produces a summary line and a modal entry.

- [ ] **Step 6: Commit any fixes and push**

```bash
git add -A
git commit -m "test(fight-log): coverage and gate fixes"
```

This project merges to `main` directly; there is no PR step. Push only with the gate green:

```bash
git push origin HEAD:main
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
|---|---|
| `FightRecord` / `FightDrop`, both constructors, name-matched participant | Task 1 |
| `hp_before: int \| None` honesty | Tasks 1, 4 |
| `started_at` normalisation and identity | Task 1 |
| `last_fight` field with `compare=False`, `repr=False` | Task 2 |
| Capture before the loss raise | Task 2 |
| `CycleSnapshot.fight` + `isinstance` gate | Task 3 |
| Summary line, structured fields only | Task 4 |
| `rich.markup.escape`, substring emphasis, no parsing | Task 4 |
| Two-pane master/detail modal, `f` binding, `_MODAL_SCREENS`, CSS, live update | Task 5 |
| Dedicated fight deque | Task 5 |
| `get_character_logs`, `m` backfill, thread worker, dedupe on `started_at` | Task 6 |
| Failed vs empty distinguishable | Task 6 |
| 100% coverage, formal gate, runtime activation | Task 7 |

**Type consistency:** `FightRecord` field names are identical across Tasks 1, 3, 4, 5, 6. `fight_summary_line` / `fight_row_label` / `fight_detail_lines` keep their names from Task 4 through Task 5. `FightScreen.merge` / `records` / `session_started_at` / `detail_lines` / `load_older_sync` / `status_text` are consistent between Tasks 5 and 6. `_fetch_older_fights(page: int) -> list[FightRecord]` matches `fetch_older: Callable[[int], list[FightRecord]]`.

**Known seam:** Task 5 ships `_load_older_worker` raising `NotImplementedError`; Task 6 Step 6 deletes it. The two tasks must not be separated across a release boundary.

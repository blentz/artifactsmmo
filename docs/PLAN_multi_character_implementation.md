# Multi-Character Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run up to 5 characters concurrently, each an independent subprocess running the current unmodified AI toward level 50, all visible in one TUI with keys `1`–`5` choosing the focused character.

**Architecture:** `play --all` becomes a supervisor process holding no `GamePlayer`. It spawns one `play <character> --emit-events` child per account character, reads newline-delimited JSON events from each child's stdout, and feeds a multi-character `WatchApp`. Both the supervisor and Textual run on the same asyncio loop, so the multi path needs no thread bridge. Children deduplicate global API reads behind a TTL cache and self-throttle against a share of the account's `/my/rates` budget.

**Tech Stack:** Python 3.13, `uv`, Typer, Textual, pydantic v2, `asyncio.create_subprocess_exec`, SQLModel/SQLite, pytest.

## Global Constraints

Copied from `AGENTS.md` and `docs/PLAN_multi_character.md`. Every task's requirements implicitly include this section.

- Always prefix Python commands with `uv run` (e.g. `uv run pytest`, `uv run mypy`).
- Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage. All tests live under `tests/`.
- **ONE CLASS PER FILE** for behavioral classes. Cohesive groups of pure data/schema/enum declarations may share a module.
- No inline imports — all imports at the top of the file.
- No triple-dot relative imports; use absolute imports.
- **NEVER** catch bare `Exception`. Never use `if TYPE_CHECKING`.
- Do not create multiple implementations of the same thing — fix in place.
- Use only API data or fail with an error. No defaulting around missing game data.
- Multiple levels of error handling for the same failure is a bug.
- Do not use print statements to report fake success.
- The formal/Lean surface must stay green with **no new proof obligations**: no new `MeansKind`, no new `GuardKind`, no change to any proven decision function.
- Rate limits are per-IP: `data` 10/s, 200/min, 2000/hour; `action` 10/s, 100/min, 5000/hour; `account` 10/s, 300/hour.
- Measured peak from `play-trace-Robby.jsonl`: **158 cycles/hour/character**.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/artifactsmmo_cli/utils/rate_budget.py` | Pure: parse `/my/rates`, split budget across N children |
| `src/artifactsmmo_cli/utils/rate_governor.py` | Multi-window token bucket, blocks when a window is drained |
| `src/artifactsmmo_cli/ai/global_reads_cache.py` | TTL cache over account-global reads |
| `src/artifactsmmo_cli/multi/child_event.py` | Schema module: `ChildEvent` discriminated union + parser |
| `src/artifactsmmo_cli/multi/event_emitter.py` | Child side: write events as JSONL |
| `src/artifactsmmo_cli/multi/restart_policy.py` | Pure: exit reason + attempts → restart decision |
| `src/artifactsmmo_cli/multi/character_supervisor.py` | One child: spawn, read, reap, restart |
| `src/artifactsmmo_cli/multi/supervisor_pool.py` | Owns N supervisors |
| `src/artifactsmmo_cli/multi/multi_run.py` | Wires roster + budget + pool + TUI or headless |
| `src/artifactsmmo_cli/tui/character_roster.py` | Pure: slot/colour/sprite assignment per character |
| `src/artifactsmmo_cli/tui/roster_entry.py` | Schema module: one roster line's data |
| `src/artifactsmmo_cli/tui/multi_snapshot_store.py` | Per-character snapshot/fight buffers |
| `src/artifactsmmo_cli/tui/widgets/map_pane.py` | **Modify**: draw non-focused characters |
| `src/artifactsmmo_cli/tui/widgets/status_pane.py` | **Modify**: roster line |
| `src/artifactsmmo_cli/tui/app.py` | **Modify**: roster, focus keys, per-character routing |
| `src/artifactsmmo_cli/commands/play.py` | **Modify**: `--all`, `--emit-events`, `--rate-budget` |
| `src/artifactsmmo_cli/ai/player.py` | **Modify**: route global reads through the cache |
| `src/artifactsmmo_cli/ai/learning/store.py` | **Modify**: `busy_timeout` |

---

### Task 1: SQLite `busy_timeout` for concurrent children — ~~DO~~ **CANCELLED, no work needed**

> **This task was based on a false premise and has been withdrawn.** It was
> implemented (`05f8c6f1`) and reverted (`275b9b2f`) on 2026-07-30.
>
> The premise was "there is no `busy_timeout`, so a concurrent writer fails
> immediately". That is wrong: pysqlite's `sqlite3.connect(timeout=5.0)` default
> already sets `busy_timeout=5000` on **every** connection, verified against a
> SQLAlchemy engine with no PRAGMA at all. An explicit `PRAGMA busy_timeout=5000`
> changes nothing, and the accompanying test passed on unmodified code — a
> vacuous guard.
>
> Two findings from the attempt are worth keeping:
> - `busy_timeout` genuinely is per-connection and this engine is pooled, so IF a
>   non-default value were ever wanted, it must go in a SQLAlchemy `connect` event
>   listener, not an inline PRAGMA.
> - `LearningStore.start_session()` / `end_session()` do **not** write a session
>   row; the row is created lazily by `record_cycle()` → `_ensure_session_row()`.
>   Any future test that means to exercise a real write must call one of those.
>
> Skip to Task 2. The original text is left below for the record.

Five children with `--learn` share one SQLite file. WAL is already on (`store.py:99`), but with no `busy_timeout` a concurrent writer fails instantly with "database is locked" instead of waiting out the other writer's commit.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/store.py:98-100`
- Test: `tests/test_ai/test_learning_store_concurrency.py`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing new. `LearningStore.__init__(db_path: str, character: str)` is unchanged.

- [ ] **Step 1: Write the failing test**

```python
"""LearningStore must tolerate concurrent writers (5 children share one DB)."""

from sqlalchemy import text

from artifactsmmo_cli.ai.learning.store import LearningStore


def test_busy_timeout_is_set(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "learning.db"), character="hero")
    with store._engine.connect() as conn:
        timeout_ms = conn.exec_driver_sql("PRAGMA busy_timeout").fetchone()[0]
    store.close()
    assert timeout_ms >= 5000, (
        f"busy_timeout is {timeout_ms}ms; concurrent children need a real wait"
    )


def test_second_writer_waits_instead_of_failing(tmp_path):
    db = str(tmp_path / "learning.db")
    first = LearningStore(db_path=db, character="alice")
    second = LearningStore(db_path=db, character="bob")
    first.start_session()
    second.start_session()
    first.end_session(exit_reason="normal")
    second.end_session(exit_reason="normal")
    with second._engine.connect() as conn:
        rows = conn.execute(text("SELECT DISTINCT character FROM sessions")).fetchall()
    first.close()
    second.close()
    assert {r[0] for r in rows} == {"alice", "bob"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_learning_store_concurrency.py -v`
Expected: `test_busy_timeout_is_set` FAILS — `busy_timeout is 0ms`.

- [ ] **Step 3: Write minimal implementation**

In `store.py`, inside the existing `with self._engine.connect() as conn:` block at line 98, after the `synchronous` pragma:

```python
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            # Five `play --all` children share one DB file. WAL lets readers and
            # one writer proceed together, but a second WRITER still collides;
            # without a busy timeout SQLite fails that commit immediately with
            # "database is locked" instead of waiting out the other child.
            conn.execute(text("PRAGMA busy_timeout=5000"))
```

If `PRAGMA busy_timeout` does not persist across pooled connections, set it on
every checkout instead by registering a `connect` event listener on the engine:

```python
from sqlalchemy import event

@event.listens_for(self._engine, "connect")
def _set_busy_timeout(dbapi_connection, _record):
    dbapi_connection.execute("PRAGMA busy_timeout=5000")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_learning_store_concurrency.py -v`
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ai/test_learning_store_concurrency.py src/artifactsmmo_cli/ai/learning/store.py
git commit -m "fix(learning): set SQLite busy_timeout for concurrent children"
```

---

### Task 2: `GlobalReadsCache`

`active_events` and `raids` are account-global and identical across characters, yet `_fetch_world_state` re-fetches both every cycle. Five characters at the measured peak is ~2370 data requests/hour against a 2000/hour ceiling. A 60s TTL takes a cycle from 3 data reads to 1.

**Files:**
- Create: `src/artifactsmmo_cli/ai/global_reads_cache.py`
- Test: `tests/test_ai/test_global_reads_cache.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `GlobalReadsCache(ttl_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic)`, method `get_or_fetch(key: str, fetch: Callable[[], T]) -> T`. Used by Task 3.

- [ ] **Step 1: Write the failing test**

```python
"""GlobalReadsCache: TTL memo over account-global API reads."""

from artifactsmmo_cli.ai.global_reads_cache import GlobalReadsCache


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_second_call_within_ttl_does_not_refetch():
    clock = _Clock()
    cache = GlobalReadsCache(ttl_seconds=60.0, clock=clock)
    calls = []

    def fetch():
        calls.append(1)
        return {"dragon": "2026-07-30T12:00:00Z"}

    assert cache.get_or_fetch("events", fetch) == {"dragon": "2026-07-30T12:00:00Z"}
    clock.now = 59.0
    assert cache.get_or_fetch("events", fetch) == {"dragon": "2026-07-30T12:00:00Z"}
    assert len(calls) == 1


def test_call_after_ttl_refetches():
    clock = _Clock()
    cache = GlobalReadsCache(ttl_seconds=60.0, clock=clock)
    calls = []

    def fetch():
        calls.append(len(calls))
        return len(calls)

    cache.get_or_fetch("raids", fetch)
    clock.now = 60.0
    cache.get_or_fetch("raids", fetch)
    assert len(calls) == 2


def test_distinct_keys_are_cached_independently():
    cache = GlobalReadsCache(ttl_seconds=60.0, clock=_Clock())
    assert cache.get_or_fetch("events", lambda: "E") == "E"
    assert cache.get_or_fetch("raids", lambda: "R") == "R"
    assert cache.get_or_fetch("events", lambda: "OTHER") == "E"


def test_fetch_exception_is_not_cached():
    clock = _Clock()
    cache = GlobalReadsCache(ttl_seconds=60.0, clock=clock)

    def boom():
        raise RuntimeError("transport failed")

    try:
        cache.get_or_fetch("events", boom)
    except RuntimeError:
        pass
    assert cache.get_or_fetch("events", lambda: "recovered") == "recovered"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_global_reads_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.global_reads_cache'`.

- [ ] **Step 3: Write minimal implementation**

```python
"""GlobalReadsCache: TTL memo over account-global (non-per-character) API reads."""

import time
from collections.abc import Callable
from typing import Any


class GlobalReadsCache:
    """Short-TTL memo for reads that are identical for every character.

    `active_events` and `raids` are account-global, but `_fetch_world_state`
    re-reads both every cycle. With five characters that is ten redundant
    data-bucket requests per cycle-round, which alone breaches the 2000/hour
    per-IP data ceiling at peak. Both change on a minutes-to-hours timescale,
    so a 60s TTL costs nothing semantically.

    A failed fetch is NOT cached: the exception propagates to the caller (which
    already has retry/backoff around these reads) and the next call re-fetches.
    """

    def __init__(
        self,
        ttl_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._entries: dict[str, tuple[float, Any]] = {}

    def get_or_fetch(self, key: str, fetch: Callable[[], Any]) -> Any:
        now = self._clock()
        entry = self._entries.get(key)
        if entry is not None and now - entry[0] < self._ttl:
            return entry[1]
        value = fetch()
        self._entries[key] = (now, value)
        return value
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_global_reads_cache.py -v`
Expected: all 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ai/test_global_reads_cache.py src/artifactsmmo_cli/ai/global_reads_cache.py
git commit -m "feat(ai): add GlobalReadsCache for account-global API reads"
```

---

### Task 3: Route events and raids through the cache

Wire Task 2 into `GamePlayer`, and drop events whose expiry has passed so a cached view never reports an event that has since ended.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (constructor, and `_fetch_world_state` at lines 1389-1390)
- Test: `tests/test_ai/test_player_global_reads.py`

**Interfaces:**
- Consumes: `GlobalReadsCache.get_or_fetch` from Task 2.
- Produces: `GamePlayer._global_reads: GlobalReadsCache`. Read by Task 16's regression guard.

- [ ] **Step 1: Write the failing test**

```python
"""GamePlayer routes account-global reads through GlobalReadsCache."""

from datetime import datetime, timedelta, timezone

from artifactsmmo_cli.ai.player import GamePlayer


def _player() -> GamePlayer:
    return GamePlayer(character="hero")


def test_player_has_a_global_reads_cache():
    assert _player()._global_reads is not None


def test_events_and_raids_use_distinct_cache_keys():
    player = _player()
    calls = {"events": 0, "raids": 0}

    def fetch_events():
        calls["events"] += 1
        return {"dragon": datetime.now(timezone.utc) + timedelta(hours=1)}

    def fetch_raids():
        calls["raids"] += 1
        return []

    player._global_reads.get_or_fetch("active_events", fetch_events)
    player._global_reads.get_or_fetch("raids", fetch_raids)
    player._global_reads.get_or_fetch("active_events", fetch_events)
    player._global_reads.get_or_fetch("raids", fetch_raids)
    assert calls == {"events": 1, "raids": 1}


def test_expired_events_are_dropped_from_a_cached_view():
    player = _player()
    now = datetime.now(timezone.utc)
    cached = {
        "live_event": now + timedelta(minutes=30),
        "ended_event": now - timedelta(seconds=1),
    }
    assert player._unexpired(cached, now) == {"live_event": cached["live_event"]}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_player_global_reads.py -v`
Expected: FAIL — `AttributeError: 'GamePlayer' object has no attribute '_global_reads'`.

- [ ] **Step 3: Write minimal implementation**

Add the import at the top of `player.py`:

```python
from artifactsmmo_cli.ai.global_reads_cache import GlobalReadsCache
```

In `GamePlayer.__init__`, alongside the other per-run state:

```python
        # active_events and raids are account-GLOBAL: identical for every
        # character, yet re-read every cycle. With five `play --all` children
        # that duplication alone breaches the 2000/hour per-IP data ceiling at
        # peak (measured: 158 cycles/hour/character x 5 x 3 reads = 2370).
        self._global_reads = GlobalReadsCache()
```

Add the expiry filter as a static method on `GamePlayer`:

```python
    @staticmethod
    def _unexpired(
        events: dict[str, datetime], now: datetime
    ) -> dict[str, datetime]:
        """Drop events whose expiry has passed. A cached events view is up to
        one TTL stale, so without this the planner could target an event that
        already ended."""
        return {code: expiry for code, expiry in events.items() if expiry > now}
```

Replace lines 1389-1390 of `_fetch_world_state`:

```python
        active_events = self._unexpired(
            self._global_reads.get_or_fetch(
                "active_events", lambda: self._fetch_active_events(client)
            ),
            datetime.now(timezone.utc),
        )
        raids = self._global_reads.get_or_fetch(
            "raids", lambda: self._fetch_raids(client)
        )
```

Confirm `datetime` and `timezone` are already imported at the top of `player.py`; add `timezone` to the existing `from datetime import ...` line if absent.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_player_global_reads.py -v`
Then the surrounding suite: `uv run pytest tests/test_ai/ -x -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ai/test_player_global_reads.py src/artifactsmmo_cli/ai/player.py
git commit -m "perf(ai): cache account-global reads, 3 data reads/cycle -> 1"
```

---

### Task 4: `RateBudget` — parse and split `/my/rates`

**Files:**
- Create: `src/artifactsmmo_cli/utils/rate_budget.py`
- Test: `tests/test_utils/test_rate_budget.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `WindowBudget`, `BucketBudgets`, `parse_rate_limits(payload: dict) -> BucketBudgets`, `split_budget(budgets: BucketBudgets, children: int) -> BucketBudgets`, `BucketBudgets.to_json() -> str`, `BucketBudgets.from_json(text: str) -> BucketBudgets`. Used by Tasks 5, 12, 14.

- [ ] **Step 1: Write the failing test**

```python
"""RateBudget: parse /my/rates and divide it across N children."""

import pytest

from artifactsmmo_cli.utils.rate_budget import (
    BucketBudgets,
    WindowBudget,
    parse_rate_limits,
    split_budget,
)

_PAYLOAD = {
    "data": {
        "account": {"second": {"limit": 10}, "hour": {"limit": 300}},
        "data": {"second": {"limit": 10}, "minute": {"limit": 200}, "hour": {"limit": 2000}},
        "action": {"second": {"limit": 10}, "minute": {"limit": 100}, "hour": {"limit": 5000}},
    }
}


def test_parse_reads_every_bucket_and_window():
    budgets = parse_rate_limits(_PAYLOAD)
    assert budgets.data == WindowBudget(second=10, minute=200, hour=2000, day=None)
    assert budgets.action == WindowBudget(second=10, minute=100, hour=5000, day=None)
    assert budgets.account == WindowBudget(second=10, minute=None, hour=300, day=None)


def test_parse_rejects_a_missing_bucket():
    with pytest.raises(ValueError, match="rate limit payload has no 'action' bucket"):
        parse_rate_limits({"data": {"account": {}, "data": {}}})


def test_split_divides_every_window():
    split = split_budget(parse_rate_limits(_PAYLOAD), children=5)
    assert split.data == WindowBudget(second=2, minute=40, hour=400, day=None)
    assert split.action == WindowBudget(second=2, minute=20, hour=1000, day=None)


def test_split_floors_but_never_to_zero():
    budgets = BucketBudgets(
        account=WindowBudget(second=1, minute=None, hour=None, day=None),
        data=WindowBudget(second=1, minute=None, hour=None, day=None),
        action=WindowBudget(second=1, minute=None, hour=None, day=None),
    )
    assert split_budget(budgets, children=5).data.second == 1


def test_split_rejects_a_nonpositive_child_count():
    with pytest.raises(ValueError, match="children must be >= 1"):
        split_budget(parse_rate_limits(_PAYLOAD), children=0)


def test_json_round_trip():
    budgets = split_budget(parse_rate_limits(_PAYLOAD), children=5)
    assert BucketBudgets.from_json(budgets.to_json()) == budgets
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_utils/test_rate_budget.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.utils.rate_budget'`.

- [ ] **Step 3: Write minimal implementation**

```python
"""Rate-limit budgets: parse /my/rates and divide it across concurrent children.

ArtifactsMMO applies standard rate limits PER IP ADDRESS, so every `play --all`
child draws from one shared budget. The parent reads the live limits once and
hands each child its share; nothing here hardcodes a limit value, per the
project's use-only-API-data rule.
"""

import json
from dataclasses import asdict, dataclass

_WINDOWS = ("second", "minute", "hour", "day")
_BUCKETS = ("account", "data", "action")


@dataclass(frozen=True)
class WindowBudget:
    """Per-window request allowance. None means the API declares no limit."""

    second: int | None
    minute: int | None
    hour: int | None
    day: int | None

    def divided_by(self, children: int) -> "WindowBudget":
        def share(limit: int | None) -> int | None:
            if limit is None:
                return None
            return max(1, limit // children)

        return WindowBudget(
            second=share(self.second),
            minute=share(self.minute),
            hour=share(self.hour),
            day=share(self.day),
        )

    def as_windows(self) -> dict[float, int]:
        """{window length in seconds: limit}, omitting undeclared windows."""
        spans = {"second": 1.0, "minute": 60.0, "hour": 3600.0, "day": 86400.0}
        return {
            spans[name]: limit
            for name in _WINDOWS
            if (limit := getattr(self, name)) is not None
        }


@dataclass(frozen=True)
class BucketBudgets:
    """The three buckets this client uses. `simulation` and `assistant` are
    member-only and unused by the bot, so they are deliberately not modelled."""

    account: WindowBudget
    data: WindowBudget
    action: WindowBudget

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

    @staticmethod
    def from_json(text: str) -> "BucketBudgets":
        raw = json.loads(text)
        return BucketBudgets(
            **{bucket: WindowBudget(**raw[bucket]) for bucket in _BUCKETS}
        )


def parse_rate_limits(payload: dict) -> BucketBudgets:
    """Build budgets from a /my/rates response body. Raises on a missing bucket
    rather than defaulting: an unreadable budget must fail loudly, not silently
    become an unlimited one."""
    data = payload.get("data")
    if data is None:
        raise ValueError("rate limit payload has no 'data' envelope")
    parsed = {}
    for bucket in _BUCKETS:
        scope = data.get(bucket)
        if scope is None:
            raise ValueError(f"rate limit payload has no {bucket!r} bucket")
        parsed[bucket] = WindowBudget(
            **{
                window: (scope.get(window) or {}).get("limit")
                for window in _WINDOWS
            }
        )
    return BucketBudgets(**parsed)


def split_budget(budgets: BucketBudgets, children: int) -> BucketBudgets:
    """Each child's share. Floors, but never to zero — a child with a zero
    allowance would block forever instead of merely being slow."""
    if children < 1:
        raise ValueError(f"children must be >= 1, got {children}")
    return BucketBudgets(
        account=budgets.account.divided_by(children),
        data=budgets.data.divided_by(children),
        action=budgets.action.divided_by(children),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_utils/test_rate_budget.py -v`
Expected: all 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_utils/test_rate_budget.py src/artifactsmmo_cli/utils/rate_budget.py
git commit -m "feat(utils): add RateBudget parsing and per-child splitting"
```

---

### Task 5: `RateGovernor` — multi-window token bucket

**Files:**
- Create: `src/artifactsmmo_cli/utils/rate_governor.py`
- Test: `tests/test_utils/test_rate_governor.py`

**Interfaces:**
- Consumes: `WindowBudget.as_windows()` from Task 4.
- Produces: `RateGovernor(budget: WindowBudget, clock=time.monotonic, sleep=time.sleep)`, method `acquire() -> None`. Used by Task 14.

- [ ] **Step 1: Write the failing test**

```python
"""RateGovernor: sliding-window throttle that only blocks on a real burst."""

from artifactsmmo_cli.utils.rate_budget import WindowBudget
from artifactsmmo_cli.utils.rate_governor import RateGovernor


class _FakeTime:
    """A clock whose sleeps advance it, so tests never actually wait."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def _governor(fake: _FakeTime, **windows) -> RateGovernor:
    budget = WindowBudget(
        second=windows.get("second"),
        minute=windows.get("minute"),
        hour=windows.get("hour"),
        day=None,
    )
    return RateGovernor(budget, clock=fake.clock, sleep=fake.sleep)


def test_requests_under_the_limit_never_block():
    fake = _FakeTime()
    governor = _governor(fake, second=2)
    governor.acquire()
    governor.acquire()
    assert fake.slept == []


def test_exceeding_a_window_sleeps_until_the_oldest_request_ages_out():
    fake = _FakeTime()
    governor = _governor(fake, second=2)
    governor.acquire()
    governor.acquire()
    governor.acquire()
    assert fake.slept == [1.0]


def test_the_tightest_window_wins():
    fake = _FakeTime()
    governor = _governor(fake, second=10, minute=2)
    governor.acquire()
    governor.acquire()
    governor.acquire()
    assert fake.slept == [60.0]


def test_time_spent_on_cooldown_refills_the_window():
    """The bot sleeps out an action cooldown between requests. That idle time
    must count toward the window, so a cooldown-bound bot never sees latency
    added by the governor."""
    fake = _FakeTime()
    governor = _governor(fake, second=1)
    governor.acquire()
    fake.now += 25.0  # a fight cooldown
    governor.acquire()
    assert fake.slept == []


def test_a_budget_with_no_declared_windows_never_blocks():
    fake = _FakeTime()
    governor = _governor(fake)
    for _ in range(100):
        governor.acquire()
    assert fake.slept == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_utils/test_rate_governor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.utils.rate_governor'`.

- [ ] **Step 3: Write minimal implementation**

```python
"""RateGovernor: a sliding-window throttle for one rate-limit bucket."""

import time
from collections import deque
from collections.abc import Callable

from artifactsmmo_cli.utils.rate_budget import WindowBudget


class RateGovernor:
    """Enforces every declared window of one bucket at once.

    Sliding-window rather than a leaky bucket, because the server's limits are
    literally "N requests per window". Idle time counts toward the window for
    free, so a cooldown-bound bot -- which sleeps 15-25s between actions --
    never sees latency added here. The governor blocks only when a genuine
    burst has drained a window.
    """

    def __init__(
        self,
        budget: WindowBudget,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._windows = budget.as_windows()
        self._clock = clock
        self._sleep = sleep
        self._history: deque[float] = deque()
        self._longest = max(self._windows, default=0.0)

    def acquire(self) -> None:
        """Block until one request may be sent, then record it."""
        while True:
            now = self._clock()
            self._prune(now)
            wait = self._longest_wait(now)
            if wait <= 0.0:
                self._history.append(now)
                return
            self._sleep(wait)

    def _prune(self, now: float) -> None:
        while self._history and now - self._history[0] >= self._longest:
            self._history.popleft()

    def _longest_wait(self, now: float) -> float:
        """Seconds until every window has room. 0.0 when a request may go now."""
        wait = 0.0
        for span, limit in self._windows.items():
            recent = [t for t in self._history if now - t < span]
            if len(recent) >= limit:
                # The oldest request inside this window must age out of it.
                wait = max(wait, recent[-limit] + span - now)
        return wait
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_utils/test_rate_governor.py -v`
Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_utils/test_rate_governor.py src/artifactsmmo_cli/utils/rate_governor.py
git commit -m "feat(utils): add RateGovernor sliding-window throttle"
```

---

### Task 6: `ChildEvent` protocol

**Files:**
- Create: `src/artifactsmmo_cli/multi/__init__.py` (empty)
- Create: `src/artifactsmmo_cli/multi/child_event.py`
- Test: `tests/test_multi/__init__.py` (empty), `tests/test_multi/test_child_event.py`

**Interfaces:**
- Consumes: `CycleSnapshot` from `artifactsmmo_cli.ai.cycle_snapshot`.
- Produces: `SnapshotEvent`, `PlanningEvent`, `ExitEvent`, the `ChildEvent` union, and `parse_child_event(line: str) -> ChildEvent`. Used by Tasks 7, 10, 13.

- [ ] **Step 1: Write the failing test**

```python
"""ChildEvent: the JSONL protocol between a bot child and the supervisor."""

import pytest
from pydantic import ValidationError

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.multi.child_event import (
    ExitEvent,
    PlanningEvent,
    SnapshotEvent,
    parse_child_event,
)


def _snap() -> CycleSnapshot:
    return CycleSnapshot(
        cycle_index=7, timestamp="2026-07-30T12:00:00Z", character="hero",
        x=1, y=2, level=19, xp=100, max_xp=7200, hp=400, max_hp=475, gold=10,
        selected_goal="ReachLevel(50)", action="Fight(chicken)", outcome="ok",
    )


def test_snapshot_event_round_trips():
    event = SnapshotEvent(character="hero", payload=_snap())
    parsed = parse_child_event(event.model_dump_json())
    assert isinstance(parsed, SnapshotEvent)
    assert parsed.payload.cycle_index == 7
    assert parsed.payload.character == "hero"


def test_planning_event_round_trips():
    parsed = parse_child_event(PlanningEvent(character="hero", active=True).model_dump_json())
    assert isinstance(parsed, PlanningEvent)
    assert parsed.active is True


def test_exit_event_round_trips():
    parsed = parse_child_event(ExitEvent(character="hero", reason="stuck_exit").model_dump_json())
    assert isinstance(parsed, ExitEvent)
    assert parsed.reason == "stuck_exit"


def test_an_unknown_kind_is_an_error_not_a_silent_skip():
    with pytest.raises(ValidationError):
        parse_child_event('{"kind":"telemetry","character":"hero"}')


def test_malformed_json_is_an_error():
    with pytest.raises(ValidationError):
        parse_child_event('{"kind":"snapshot",')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_multi/test_child_event.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.multi'`.

- [ ] **Step 3: Write minimal implementation**

```python
"""ChildEvent: the newline-delimited JSON protocol a `--emit-events` child
writes to stdout and the `play --all` supervisor reads.

Schema module: a discriminated union plus its variants, no behavior.
`CycleSnapshot` is already a pydantic model, so the wire format is generated
from it rather than hand-written, and cannot drift from it.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot


class SnapshotEvent(BaseModel):
    kind: Literal["snapshot"] = "snapshot"
    character: str
    payload: CycleSnapshot


class PlanningEvent(BaseModel):
    kind: Literal["planning"] = "planning"
    character: str
    active: bool


class ExitEvent(BaseModel):
    kind: Literal["exit"] = "exit"
    character: str
    reason: str
    """The `exit_reason` play() computes for the learning store, with one
    refinement: an uncaught httpx transport error reports `crash:network` so
    the RestartPolicy can tell a transient failure from a real bug."""


ChildEvent = Annotated[
    SnapshotEvent | PlanningEvent | ExitEvent, Field(discriminator="kind")
]

_ADAPTER: TypeAdapter[ChildEvent] = TypeAdapter(ChildEvent)


def parse_child_event(line: str) -> ChildEvent:
    """Parse one protocol line. Raises `ValidationError` on anything malformed
    or unrecognised — a complete-but-unparseable line means the protocol has
    drifted and must be fixed, never silently dropped."""
    return _ADAPTER.validate_json(line)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_multi/test_child_event.py -v`
Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_multi src/artifactsmmo_cli/multi
git commit -m "feat(multi): add ChildEvent JSONL protocol"
```

---

### Task 7: `JsonlEventEmitter`

**Files:**
- Create: `src/artifactsmmo_cli/multi/event_emitter.py`
- Test: `tests/test_multi/test_event_emitter.py`

**Interfaces:**
- Consumes: `SnapshotEvent`, `PlanningEvent`, `ExitEvent` from Task 6.
- Produces: `JsonlEventEmitter(character: str, stream: TextIO)` with methods `snapshot(snap: CycleSnapshot) -> None`, `planning(active: bool) -> None`, `emit_exit(reason: str) -> None`. Used by Task 8.

- [ ] **Step 1: Write the failing test**

```python
"""JsonlEventEmitter: child-side protocol writer."""

import io

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.multi.child_event import (
    ExitEvent,
    PlanningEvent,
    SnapshotEvent,
    parse_child_event,
)
from artifactsmmo_cli.multi.event_emitter import JsonlEventEmitter


def _snap(cycle_index: int = 1) -> CycleSnapshot:
    return CycleSnapshot(
        cycle_index=cycle_index, timestamp="2026-07-30T12:00:00Z", character="hero",
        x=0, y=0, level=1, xp=0, max_xp=150, hp=120, max_hp=120, gold=0,
        selected_goal="ReachLevel(50)", action="Rest()", outcome="ok",
    )


def test_each_event_is_one_parseable_line():
    stream = io.StringIO()
    emitter = JsonlEventEmitter(character="hero", stream=stream)
    emitter.snapshot(_snap(1))
    emitter.planning(True)
    emitter.emit_exit("normal")
    lines = stream.getvalue().splitlines()
    assert len(lines) == 3
    kinds = [type(parse_child_event(line)) for line in lines]
    assert kinds == [SnapshotEvent, PlanningEvent, ExitEvent]


def test_every_line_carries_the_character():
    stream = io.StringIO()
    JsonlEventEmitter(character="alice", stream=stream).planning(False)
    assert parse_child_event(stream.getvalue()).character == "alice"


def test_each_write_is_flushed():
    """The parent reads this stream live; a buffered write would stall the TUI
    until the buffer filled or the child exited."""
    flushes = []

    class _Counting(io.StringIO):
        def flush(self) -> None:
            flushes.append(1)

    emitter = JsonlEventEmitter(character="hero", stream=_Counting())
    emitter.snapshot(_snap())
    emitter.planning(True)
    assert len(flushes) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_multi/test_event_emitter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.multi.event_emitter'`.

- [ ] **Step 3: Write minimal implementation**

```python
"""JsonlEventEmitter: writes ChildEvent lines to a stream, one per line."""

from typing import TextIO

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.multi.child_event import (
    ExitEvent,
    PlanningEvent,
    SnapshotEvent,
)


class JsonlEventEmitter:
    """Child-side protocol writer.

    Every line is flushed: the supervisor reads this stream live, so a buffered
    write would stall the TUI until the buffer filled or the child exited.
    """

    def __init__(self, character: str, stream: TextIO) -> None:
        self._character = character
        self._stream = stream

    def _write(self, payload: str) -> None:
        self._stream.write(payload + "\n")
        self._stream.flush()

    def snapshot(self, snap: CycleSnapshot) -> None:
        self._write(
            SnapshotEvent(character=self._character, payload=snap).model_dump_json()
        )

    def planning(self, active: bool) -> None:
        self._write(
            PlanningEvent(character=self._character, active=active).model_dump_json()
        )

    def emit_exit(self, reason: str) -> None:
        self._write(
            ExitEvent(character=self._character, reason=reason).model_dump_json()
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_multi/test_event_emitter.py -v`
Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_multi/test_event_emitter.py src/artifactsmmo_cli/multi/event_emitter.py
git commit -m "feat(multi): add JsonlEventEmitter"
```

---

### Task 8: `play --emit-events`

The bot prints human-readable progress to stdout throughout. Without redirecting those prints, they interleave with and corrupt the protocol stream.

**Files:**
- Modify: `src/artifactsmmo_cli/commands/play.py` (signature, body, `finally` block)
- Test: `tests/test_commands/test_play_emit_events.py`

**Interfaces:**
- Consumes: `JsonlEventEmitter` from Task 7.
- Produces: the `--emit-events` flag on `play`, and `play`'s exit event with a `crash:network` refinement. Consumed by Tasks 10 and 14.

- [ ] **Step 1: Write the failing test**

```python
"""`play --emit-events`: stdout is protocol only, human output goes to stderr."""

import json
import subprocess
import sys

import pytest

from artifactsmmo_cli.commands import play as play_module


def test_emit_events_flag_exists():
    import inspect

    assert "emit_events" in inspect.signature(play_module.play).parameters


def test_network_crash_is_reported_as_crash_network():
    assert play_module.emit_reason_for(play_module.httpx.ConnectError("boom")) == "crash:network"


def test_other_crashes_stay_plain_crash():
    assert play_module.emit_reason_for(RuntimeError("bug")) == "crash"


def test_child_stdout_carries_only_json_lines():
    """End-to-end: a real child process whose bot prints must still emit a
    stdout stream where EVERY line parses as a ChildEvent."""
    script = (
        "import sys, io\n"
        "from artifactsmmo_cli.multi.event_emitter import JsonlEventEmitter\n"
        "import contextlib\n"
        "emitter = JsonlEventEmitter('hero', sys.stdout)\n"
        "with contextlib.redirect_stdout(sys.stderr):\n"
        "    print('bot noise that must not corrupt the protocol')\n"
        "    emitter.planning(True)\n"
        "    emitter.emit_exit('normal')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    for line in result.stdout.splitlines():
        assert json.loads(line)["kind"] in {"snapshot", "planning", "exit"}
    assert "bot noise" in result.stderr


def test_all_and_character_are_mutually_exclusive():
    with pytest.raises(SystemExit) as excinfo:
        play_module.play(character="hero", all_characters=True)
    assert excinfo.value.exit_code == 2


def test_all_requires_no_explicit_trace_file():
    with pytest.raises(SystemExit) as excinfo:
        play_module.play(character=None, all_characters=True, trace_file="x.jsonl")
    assert excinfo.value.exit_code == 2


def test_neither_all_nor_character_is_an_error():
    with pytest.raises(SystemExit) as excinfo:
        play_module.play(character=None, all_characters=False)
    assert excinfo.value.exit_code == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_commands/test_play_emit_events.py -v`
Expected: FAIL — `AssertionError` on the missing `emit_events` parameter.

- [ ] **Step 3: Write minimal implementation**

Add to the top of `play.py`:

```python
import contextlib
import sys

import httpx

from artifactsmmo_cli.multi.event_emitter import JsonlEventEmitter
```

(`contextlib` is already imported; do not duplicate it.)

Add the reason classifier as a module-level function:

```python
def emit_reason_for(exc: BaseException) -> str:
    """The exit reason reported to the supervisor. An httpx transport failure is
    transient and worth restarting; every other crash is a bug that a restart
    loop would only hide. The learning store still records plain "crash"."""
    if isinstance(exc, httpx.HTTPError):
        return "crash:network"
    return "crash"
```

Change `play`'s signature — `character` becomes optional and two flags are added:

```python
def play(
    character: str | None = typer.Argument(None, help="Character name to play"),
    all_characters: bool = typer.Option(
        False, "--all",
        help="Supervise every account character, one subprocess each"),
    emit_events: bool = typer.Option(
        False, "--emit-events",
        help="Emit JSONL cycle events on stdout; human output moves to stderr"),
    rate_budget: str | None = typer.Option(
        None, "--rate-budget",
        help="This child's share of the account rate budget, as JSON"),
    ...  # every existing parameter unchanged
) -> None:
```

Immediately after the docstring, validate the combination:

```python
    if all_characters and character is not None:
        print("--all supervises every character; do not also name one")
        raise typer.Exit(code=2)
    if all_characters and trace_file is not None:
        print("--all writes one trace per character; --trace-file names only one")
        raise typer.Exit(code=2)
    if not all_characters and character is None:
        print("name a character to play, or pass --all")
        raise typer.Exit(code=2)
    if all_characters:
        MultiRun(verbose=verbose, dry_run=dry_run, trace=trace, learn=learn,
                 learn_db=learn_db, tui=tui,
                 refresh_game_data=refresh_game_data).run()
        return
```

`MultiRun` arrives in Task 14; until then leave that branch out and let Task 14
add it, so this task stays independently testable.

Wire the emitter after the `player = GamePlayer(...)` construction:

```python
    emitter: JsonlEventEmitter | None = None
    if emit_events:
        # Capture the REAL stdout before the redirect below rebinds sys.stdout,
        # so the protocol keeps writing to the pipe the parent reads.
        emitter = JsonlEventEmitter(character=character, stream=sys.stdout)
        player.set_cycle_observer(emitter.snapshot)
        player.set_planning_observer(emitter.planning)
```

Wrap the run so the bot's own prints land on stderr:

```python
    exit_reason = "crash"
    emit_reason = "crash"
    try:
        with contextlib.redirect_stdout(sys.stderr) if emit_events else contextlib.nullcontext():
            if tui:
                _run_with_tui(player, character, config.game_data_ttl_minutes, refresh_game_data)
            else:
                player.run()
        exit_reason = "normal"
        emit_reason = "normal"
    except ServerUnavailableError:
        exit_reason = emit_reason = "server_unavailable"
        raise
    except StuckExit as exc:
        exit_reason = emit_reason = "stuck_exit"
        print(f"Bot for {character!r} stopped: {exc} — manual intervention needed")
        raise typer.Exit(code=2) from exc
    except KeyboardInterrupt:
        exit_reason = emit_reason = "keyboard_interrupt"
        raise
    except httpx.HTTPError:
        exit_reason = "crash"
        emit_reason = "crash:network"
        raise
    finally:
        if emitter is not None:
            emitter.emit_exit(emit_reason)
        store.end_session(exit_reason=exit_reason)
        store.close()
```

Note the two variables: `exit_reason` is what the learning store records
(unchanged vocabulary), `emit_reason` is what the supervisor's restart policy
reads.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_commands/test_play_emit_events.py -v`
Then the existing play tests: `uv run pytest tests/test_commands/ -q`
Expected: all PASS. Existing `play <character>` tests must be unaffected.

- [ ] **Step 5: Commit**

```bash
git add tests/test_commands/test_play_emit_events.py src/artifactsmmo_cli/commands/play.py
git commit -m "feat(play): add --emit-events with stdout/stderr separation"
```

---

### Task 9: `RestartPolicy`

**Files:**
- Create: `src/artifactsmmo_cli/multi/restart_policy.py`
- Test: `tests/test_multi/test_restart_policy.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `RestartDecision(restart: bool, delay_seconds: float)` and `RestartPolicy().decide(reason: str, attempts: int) -> RestartDecision`. Used by Tasks 10 and 11.

- [ ] **Step 1: Write the failing test**

```python
"""RestartPolicy: which child deaths are worth retrying."""

import pytest

from artifactsmmo_cli.multi.restart_policy import MAX_ATTEMPTS, RestartPolicy


@pytest.mark.parametrize("reason", ["server_unavailable", "crash:network"])
def test_transient_reasons_restart(reason):
    assert RestartPolicy().decide(reason, attempts=0).restart is True


@pytest.mark.parametrize(
    "reason", ["stuck_exit", "crash", "keyboard_interrupt", "normal"]
)
def test_non_transient_reasons_stay_dead(reason):
    assert RestartPolicy().decide(reason, attempts=0).restart is False


def test_backoff_doubles_from_five_seconds():
    policy = RestartPolicy()
    delays = [policy.decide("crash:network", attempts=n).delay_seconds for n in range(4)]
    assert delays == [5.0, 10.0, 20.0, 40.0]


def test_backoff_is_capped_at_five_minutes():
    assert RestartPolicy().decide("crash:network", attempts=20).delay_seconds <= 300.0


def test_a_flapping_child_stops_being_restarted():
    """An endlessly restarting child is a bug report, not a working system."""
    assert RestartPolicy().decide("crash:network", attempts=MAX_ATTEMPTS).restart is False


def test_an_unknown_reason_stays_dead():
    """Fail closed: a reason the policy does not recognise is not restarted."""
    assert RestartPolicy().decide("reason_from_the_future", attempts=0).restart is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_multi/test_restart_policy.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.multi.restart_policy'`.

- [ ] **Step 3: Write minimal implementation**

```python
"""RestartPolicy: exit reason + prior attempts -> restart decision."""

from dataclasses import dataclass

BASE_DELAY_SECONDS = 5.0
MAX_DELAY_SECONDS = 300.0
MAX_ATTEMPTS = 5

RESTARTABLE_REASONS = frozenset({"server_unavailable", "crash:network"})
"""Only genuinely transient causes. `stuck_exit` means the AI needs
intervention and a restart re-sticks it; a plain `crash` is a bug that a
restart loop would hide behind apparent health."""


@dataclass(frozen=True)
class RestartDecision:
    restart: bool
    delay_seconds: float


class RestartPolicy:
    def decide(self, reason: str, attempts: int) -> RestartDecision:
        if reason not in RESTARTABLE_REASONS or attempts >= MAX_ATTEMPTS:
            return RestartDecision(restart=False, delay_seconds=0.0)
        delay = min(BASE_DELAY_SECONDS * (2**attempts), MAX_DELAY_SECONDS)
        return RestartDecision(restart=True, delay_seconds=delay)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_multi/test_restart_policy.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_multi/test_restart_policy.py src/artifactsmmo_cli/multi/restart_policy.py
git commit -m "feat(multi): add RestartPolicy"
```

---

### Task 10: `CharacterSupervisor`

Owns exactly one child: spawn it, read its two streams concurrently, reap it, and consult the policy. Tested against a **real** subprocess — never a mock.

**Files:**
- Create: `src/artifactsmmo_cli/multi/character_supervisor.py`
- Test: `tests/test_multi/test_character_supervisor.py`

**Interfaces:**
- Consumes: `parse_child_event` (Task 6), `RestartPolicy`/`RestartDecision` (Task 9).
- Produces: `CharacterSupervisor(character, argv, on_event, policy=RestartPolicy(), sleep=asyncio.sleep)` with `async def run() -> None`, and read-only attributes `alive: bool`, `restarts: int`, `stderr_tail: tuple[str, ...]`. Used by Task 11.

- [ ] **Step 1: Write the failing test**

```python
"""CharacterSupervisor: one child process, driven by real subprocesses."""

import asyncio
import sys

import pytest

from artifactsmmo_cli.multi.character_supervisor import CharacterSupervisor
from artifactsmmo_cli.multi.child_event import ExitEvent, PlanningEvent
from artifactsmmo_cli.multi.restart_policy import RestartPolicy


def _child_argv(body: str) -> list[str]:
    """A real child process emitting canned protocol lines."""
    return [sys.executable, "-c", body]


_EMIT_AND_EXIT = (
    "import sys\n"
    "sys.stdout.write('{\"kind\":\"planning\",\"character\":\"hero\",\"active\":true}\\n')\n"
    "sys.stdout.write('{\"kind\":\"exit\",\"character\":\"hero\",\"reason\":\"normal\"}\\n')\n"
    "sys.stdout.flush()\n"
)

_NOISY_STDERR = (
    "import sys\n"
    "sys.stderr.write('bot log line\\n')\n"
    "sys.stderr.write('Traceback: boom\\n')\n"
    "sys.stdout.write('{\"kind\":\"exit\",\"character\":\"hero\",\"reason\":\"crash\"}\\n')\n"
    "sys.stdout.flush()\n"
)


@pytest.mark.asyncio
async def test_events_reach_the_callback():
    seen = []
    supervisor = CharacterSupervisor(
        character="hero", argv=_child_argv(_EMIT_AND_EXIT), on_event=seen.append
    )
    await supervisor.run()
    assert [type(e) for e in seen] == [PlanningEvent, ExitEvent]


@pytest.mark.asyncio
async def test_a_clean_exit_is_not_restarted():
    supervisor = CharacterSupervisor(
        character="hero", argv=_child_argv(_EMIT_AND_EXIT), on_event=lambda _e: None
    )
    await supervisor.run()
    assert supervisor.restarts == 0
    assert supervisor.alive is False


@pytest.mark.asyncio
async def test_stderr_is_captured_for_the_dead_panel():
    supervisor = CharacterSupervisor(
        character="hero", argv=_child_argv(_NOISY_STDERR), on_event=lambda _e: None
    )
    await supervisor.run()
    assert "Traceback: boom" in supervisor.stderr_tail


@pytest.mark.asyncio
async def test_a_transient_exit_restarts_then_gives_up():
    """The child always reports crash:network, so the policy restarts it up to
    MAX_ATTEMPTS and then leaves it dead rather than flapping forever."""
    body = (
        "import sys\n"
        "sys.stdout.write('{\"kind\":\"exit\",\"character\":\"hero\","
        "\"reason\":\"crash:network\"}\\n')\n"
        "sys.stdout.flush()\n"
    )
    supervisor = CharacterSupervisor(
        character="hero", argv=_child_argv(body), on_event=lambda _e: None,
        policy=RestartPolicy(), sleep=lambda _s: asyncio.sleep(0),
    )
    await supervisor.run()
    assert supervisor.restarts == 5
    assert supervisor.alive is False


@pytest.mark.asyncio
async def test_a_child_that_dies_without_an_exit_event_is_treated_as_a_crash():
    supervisor = CharacterSupervisor(
        character="hero", argv=_child_argv("raise SystemExit(9)"),
        on_event=lambda _e: None,
    )
    await supervisor.run()
    assert supervisor.last_reason == "crash"
    assert supervisor.restarts == 0


@pytest.mark.asyncio
async def test_an_unparseable_complete_line_surfaces_as_an_error():
    """A complete-but-invalid line means the protocol drifted. It must be
    visible, not silently dropped."""
    body = (
        "import sys\n"
        "sys.stdout.write('{\"kind\":\"nonsense\"}\\n')\n"
        "sys.stdout.write('{\"kind\":\"exit\",\"character\":\"hero\","
        "\"reason\":\"normal\"}\\n')\n"
        "sys.stdout.flush()\n"
    )
    supervisor = CharacterSupervisor(
        character="hero", argv=_child_argv(body), on_event=lambda _e: None
    )
    await supervisor.run()
    assert any("protocol" in line for line in supervisor.stderr_tail)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_multi/test_character_supervisor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.multi.character_supervisor'`.

If `pytest.mark.asyncio` is unrecognised, add `pytest-asyncio` to the dev
dependencies (`uv add --dev pytest-asyncio`) and set `asyncio_mode = "auto"`
under `[tool.pytest.ini_options]` in `pyproject.toml`.

- [ ] **Step 3: Write minimal implementation**

```python
"""CharacterSupervisor: spawn, read, reap, and conditionally restart one bot child."""

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable

from pydantic import ValidationError

from artifactsmmo_cli.multi.child_event import ChildEvent, ExitEvent, parse_child_event
from artifactsmmo_cli.multi.restart_policy import RestartPolicy

STDERR_TAIL_LINES = 20


class CharacterSupervisor:
    """One character's subprocess, from spawn to final death.

    The child's stdout is the event protocol and its stderr is the human log;
    both are drained concurrently so neither can fill its pipe buffer and
    deadlock the child.
    """

    def __init__(
        self,
        character: str,
        argv: list[str],
        on_event: Callable[[ChildEvent], None],
        policy: RestartPolicy | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.character = character
        self._argv = argv
        self._on_event = on_event
        self._policy = policy or RestartPolicy()
        self._sleep = sleep
        self.alive = False
        self.restarts = 0
        self.last_reason: str | None = None
        self._stderr: deque[str] = deque(maxlen=STDERR_TAIL_LINES)

    @property
    def stderr_tail(self) -> tuple[str, ...]:
        return tuple(self._stderr)

    async def run(self) -> None:
        """Run the child, restarting while the policy allows it."""
        while True:
            reason = await self._run_once()
            self.last_reason = reason
            decision = self._policy.decide(reason, self.restarts)
            if not decision.restart:
                return
            self.restarts += 1
            await self._sleep(decision.delay_seconds)

    async def _run_once(self) -> str:
        """One child lifetime. Returns the exit reason to judge."""
        process = await asyncio.create_subprocess_exec(
            *self._argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.alive = True
        reason_box: list[str] = []
        await asyncio.gather(
            self._read_events(process.stdout, reason_box),
            self._read_stderr(process.stderr),
        )
        await process.wait()
        self.alive = False
        # A child killed hard never emits an exit event. Treat the silence as a
        # crash rather than inventing a friendlier reason.
        return reason_box[0] if reason_box else "crash"

    async def _read_events(
        self, stream: asyncio.StreamReader, reason_box: list[str]
    ) -> None:
        while True:
            raw = await stream.readline()
            if not raw:
                return  # EOF; a partial trailing line is a normal mid-write death
            line = raw.decode().strip()
            if not line:
                continue
            try:
                event = parse_child_event(line)
            except ValidationError as exc:
                self._stderr.append(f"protocol error: {line[:120]} ({exc.error_count()} errors)")
                continue
            if isinstance(event, ExitEvent):
                reason_box.append(event.reason)
            self._on_event(event)

    async def _read_stderr(self, stream: asyncio.StreamReader) -> None:
        while True:
            raw = await stream.readline()
            if not raw:
                return
            self._stderr.append(raw.decode().rstrip())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_multi/test_character_supervisor.py -v`
Expected: all 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_multi/test_character_supervisor.py src/artifactsmmo_cli/multi/character_supervisor.py pyproject.toml
git commit -m "feat(multi): add CharacterSupervisor over a real subprocess"
```

---

### Task 11: `SupervisorPool`

**Files:**
- Create: `src/artifactsmmo_cli/multi/supervisor_pool.py`
- Test: `tests/test_multi/test_supervisor_pool.py`

**Interfaces:**
- Consumes: `CharacterSupervisor` (Task 10).
- Produces: `SupervisorPool(supervisors: Sequence[CharacterSupervisor])` with `async def run() -> None`, `def state(character: str) -> ChildState`, `def characters() -> tuple[str, ...]`. `ChildState` is a frozen dataclass `(character, alive, restarts, last_reason, stderr_tail)`. Used by Tasks 13 and 14.

- [ ] **Step 1: Write the failing test**

```python
"""SupervisorPool: N children, run concurrently, states readable."""

import asyncio
import sys

import pytest

from artifactsmmo_cli.multi.character_supervisor import CharacterSupervisor
from artifactsmmo_cli.multi.supervisor_pool import SupervisorPool

_EXIT_NORMAL = (
    "import sys\n"
    "sys.stdout.write('{{\"kind\":\"exit\",\"character\":\"{name}\","
    "\"reason\":\"normal\"}}\\n')\n"
    "sys.stdout.flush()\n"
)


def _supervisor(name: str, seen: list) -> CharacterSupervisor:
    return CharacterSupervisor(
        character=name,
        argv=[sys.executable, "-c", _EXIT_NORMAL.format(name=name)],
        on_event=seen.append,
    )


@pytest.mark.asyncio
async def test_every_child_runs_and_reports():
    seen = []
    names = ["alice", "bob", "carol"]
    pool = SupervisorPool([_supervisor(n, seen) for n in names])
    await pool.run()
    assert {event.character for event in seen} == set(names)


@pytest.mark.asyncio
async def test_children_run_concurrently_not_serially():
    """Three children that each sleep 0.3s must finish in well under 0.9s."""
    body = (
        "import sys, time\n"
        "time.sleep(0.3)\n"
        "sys.stdout.write('{\"kind\":\"exit\",\"character\":\"x\",\"reason\":\"normal\"}\\n')\n"
        "sys.stdout.flush()\n"
    )
    supervisors = [
        CharacterSupervisor(character=f"c{i}", argv=[sys.executable, "-c", body],
                            on_event=lambda _e: None)
        for i in range(3)
    ]
    start = asyncio.get_running_loop().time()
    await SupervisorPool(supervisors).run()
    assert asyncio.get_running_loop().time() - start < 0.9


@pytest.mark.asyncio
async def test_state_reports_each_child():
    seen = []
    pool = SupervisorPool([_supervisor("alice", seen)])
    await pool.run()
    state = pool.state("alice")
    assert state.character == "alice"
    assert state.alive is False
    assert state.restarts == 0
    assert state.last_reason == "normal"


@pytest.mark.asyncio
async def test_state_rejects_an_unknown_character():
    pool = SupervisorPool([_supervisor("alice", [])])
    with pytest.raises(KeyError):
        pool.state("nobody")


def test_characters_preserves_roster_order():
    pool = SupervisorPool([_supervisor(n, []) for n in ["carol", "alice", "bob"]])
    assert pool.characters() == ("carol", "alice", "bob")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_multi/test_supervisor_pool.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.multi.supervisor_pool'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/artifactsmmo_cli/multi/child_state.py` (schema module):

```python
"""ChildState: one child's status, as the TUI roster line reads it."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ChildState:
    character: str
    alive: bool
    restarts: int
    last_reason: str | None
    stderr_tail: tuple[str, ...]
```

Then `supervisor_pool.py`:

```python
"""SupervisorPool: owns every character's supervisor and runs them together."""

import asyncio
from collections.abc import Sequence

from artifactsmmo_cli.multi.character_supervisor import CharacterSupervisor
from artifactsmmo_cli.multi.child_state import ChildState


class SupervisorPool:
    """Runs one CharacterSupervisor per character, concurrently.

    Roster order is preserved: it comes from the account and is the tiebreak
    for sprite draw order, so it must never be re-sorted.
    """

    def __init__(self, supervisors: Sequence[CharacterSupervisor]) -> None:
        self._supervisors = tuple(supervisors)
        self._by_name = {s.character: s for s in self._supervisors}

    def characters(self) -> tuple[str, ...]:
        return tuple(s.character for s in self._supervisors)

    def state(self, character: str) -> ChildState:
        supervisor = self._by_name[character]
        return ChildState(
            character=supervisor.character,
            alive=supervisor.alive,
            restarts=supervisor.restarts,
            last_reason=supervisor.last_reason,
            stderr_tail=supervisor.stderr_tail,
        )

    async def run(self) -> None:
        await asyncio.gather(*(s.run() for s in self._supervisors))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_multi/test_supervisor_pool.py -v`
Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_multi/test_supervisor_pool.py src/artifactsmmo_cli/multi/supervisor_pool.py src/artifactsmmo_cli/multi/child_state.py
git commit -m "feat(multi): add SupervisorPool"
```

---

### Task 12: `CharacterRoster`

**Files:**
- Create: `src/artifactsmmo_cli/tui/character_roster.py`
- Test: `tests/test_tui/test_character_roster.py`

**Interfaces:**
- Consumes: `PLAYER_SPRITE`, `recolor` from `artifactsmmo_cli.tui.sprites`; colours from `artifactsmmo_cli.tui.palette`.
- Produces: `MAX_CHARACTERS = 5`, `ROSTER_COLORS`, and `CharacterRoster(names: Sequence[str])` with `names: tuple[str, ...]`, `color(name) -> str`, `index(name) -> int`, `at(slot: int) -> str | None`, `sprite(name) -> Sprite`. Used by Tasks 13 and 15.

- [ ] **Step 1: Write the failing test**

```python
"""CharacterRoster: stable slot, colour, and sprite per character."""

import pytest

from artifactsmmo_cli.tui.character_roster import ROSTER_COLORS, CharacterRoster
from artifactsmmo_cli.tui.sprites import PLAYER_SPRITE


def test_slots_are_one_based_and_follow_account_order():
    roster = CharacterRoster(["carol", "alice", "bob"])
    assert roster.at(1) == "carol"
    assert roster.at(3) == "bob"
    assert roster.at(4) is None


def test_colors_are_distinct_and_assigned_by_index():
    roster = CharacterRoster(["a", "b", "c", "d", "e"])
    colors = [roster.color(n) for n in roster.names]
    assert colors == list(ROSTER_COLORS)
    assert len(set(colors)) == 5


def test_sprites_share_the_silhouette_but_differ_in_tunic():
    roster = CharacterRoster(["a", "b"])
    first, second = roster.sprite("a"), roster.sprite("b")
    assert first.rows == PLAYER_SPRITE.rows == second.rows
    assert first.palette["b"] != second.palette["b"]


def test_sprite_objects_are_stable_across_calls():
    """MapPane's per-line cache keys on sprite identity; a fresh object every
    frame would defeat it and re-style the whole viewport."""
    roster = CharacterRoster(["a"])
    assert roster.sprite("a") is roster.sprite("a")


def test_more_than_five_characters_is_rejected():
    with pytest.raises(ValueError, match="at most 5"):
        CharacterRoster(["a", "b", "c", "d", "e", "f"])


def test_an_empty_roster_is_rejected():
    with pytest.raises(ValueError, match="at least one"):
        CharacterRoster([])


def test_duplicate_names_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        CharacterRoster(["a", "a"])


def test_an_unknown_name_is_an_error():
    with pytest.raises(KeyError):
        CharacterRoster(["a"]).color("b")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_character_roster.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.tui.character_roster'`.

- [ ] **Step 3: Write minimal implementation**

```python
"""CharacterRoster: the account's characters, with a stable slot, colour, and
sprite for each.

All characters share one silhouette and are told apart by tunic colour, so the
map reads as "the same player, five of them" rather than five species. Order
comes from the account and is never re-sorted: it is the deterministic tiebreak
for which sprite draws on top when two characters share a tile.
"""

from collections.abc import Sequence

from artifactsmmo_cli.tui.palette import AMBER, BLOOD, BREW, LEAF, TUNIC
from artifactsmmo_cli.tui.sprites import PLAYER_SPRITE, Sprite, recolor

MAX_CHARACTERS = 5
"""The account limit. Also the number of `1`-`5` focus keys."""

ROSTER_COLORS: tuple[str, ...] = (TUNIC, BLOOD, LEAF, BREW, AMBER)
"""Tunic colour per roster index. Five visually distinct palette entries."""


class CharacterRoster:
    def __init__(self, names: Sequence[str]) -> None:
        if not names:
            raise ValueError("a roster needs at least one character")
        if len(names) > MAX_CHARACTERS:
            raise ValueError(
                f"an account holds at most {MAX_CHARACTERS} characters, got {len(names)}"
            )
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate character names in roster: {list(names)}")
        self.names: tuple[str, ...] = tuple(names)
        self._index = {name: i for i, name in enumerate(self.names)}
        # Built once: MapPane's per-line Strip cache keys on sprite IDENTITY,
        # so recolouring per frame would defeat it.
        self._sprites = {
            name: recolor(
                PLAYER_SPRITE, {**PLAYER_SPRITE.palette, "b": ROSTER_COLORS[i]}
            )
            for i, name in enumerate(self.names)
        }

    def index(self, name: str) -> int:
        return self._index[name]

    def color(self, name: str) -> str:
        return ROSTER_COLORS[self._index[name]]

    def sprite(self, name: str) -> Sprite:
        return self._sprites[name]

    def at(self, slot: int) -> str | None:
        """The character on 1-based `slot`, or None when the roster is shorter."""
        if 1 <= slot <= len(self.names):
            return self.names[slot - 1]
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tui/test_character_roster.py -v`
Expected: all 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_tui/test_character_roster.py src/artifactsmmo_cli/tui/character_roster.py
git commit -m "feat(tui): add CharacterRoster with per-character colours"
```

---

### Task 13: `MultiSnapshotStore`

**Files:**
- Create: `src/artifactsmmo_cli/tui/multi_snapshot_store.py`
- Test: `tests/test_tui/test_multi_snapshot_store.py`

**Interfaces:**
- Consumes: `CycleSnapshot`, `FightRecord`.
- Produces: `MultiSnapshotStore(characters: Sequence[str], log_buffer: int = 500, fight_buffer: int = 200)` with `record(snap) -> None`, `last(character) -> CycleSnapshot | None`, `recent(character) -> deque[CycleSnapshot]`, `fights(character) -> deque[FightRecord]`, `latest_all() -> dict[str, CycleSnapshot]`. Used by Task 15.

- [ ] **Step 1: Write the failing test**

```python
"""MultiSnapshotStore: per-character buffers, no cross-character eviction."""

import pytest

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.fight_record import FightRecord
from artifactsmmo_cli.tui.multi_snapshot_store import MultiSnapshotStore


def _snap(character: str, cycle_index: int = 1, **overrides) -> CycleSnapshot:
    base = dict(
        cycle_index=cycle_index, timestamp="2026-07-30T12:00:00Z", character=character,
        x=0, y=0, level=1, xp=0, max_xp=150, hp=120, max_hp=120, gold=0,
        selected_goal="ReachLevel(50)", action="Rest()", outcome="ok",
    )
    base.update(overrides)
    return CycleSnapshot(**base)


_FIGHT = FightRecord(
    started_at="2026-07-30T12:00:00", result="win", turns=3, opponent="chicken",
    logs=(), hp_before=120, hp_after=110, xp=10, gold=2, drops=(),
)


def test_snapshots_are_routed_by_character():
    store = MultiSnapshotStore(["alice", "bob"])
    store.record(_snap("alice", 1))
    store.record(_snap("bob", 2))
    assert store.last("alice").cycle_index == 1
    assert store.last("bob").cycle_index == 2


def test_last_is_none_before_the_first_cycle():
    assert MultiSnapshotStore(["alice"]).last("alice") is None


def test_a_busy_character_cannot_evict_another_characters_history():
    """Buffers are per-character, so 600 alice cycles must not touch bob."""
    store = MultiSnapshotStore(["alice", "bob"], log_buffer=500)
    store.record(_snap("bob", 1))
    for i in range(600):
        store.record(_snap("alice", i))
    assert len(store.recent("bob")) == 1
    assert len(store.recent("alice")) == 500


def test_fights_go_to_the_fighting_characters_buffer():
    store = MultiSnapshotStore(["alice", "bob"])
    store.record(_snap("alice", 1, fight=_FIGHT))
    assert len(store.fights("alice")) == 1
    assert len(store.fights("bob")) == 0


def test_latest_all_omits_characters_with_no_cycle_yet():
    store = MultiSnapshotStore(["alice", "bob"])
    store.record(_snap("alice", 1))
    assert set(store.latest_all()) == {"alice"}


def test_an_unknown_character_is_an_error_not_a_silent_drop():
    store = MultiSnapshotStore(["alice"])
    with pytest.raises(KeyError):
        store.record(_snap("mallory"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_multi_snapshot_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.tui.multi_snapshot_store'`.

- [ ] **Step 3: Write minimal implementation**

```python
"""MultiSnapshotStore: per-character snapshot, log, and fight buffers."""

from collections import deque
from collections.abc import Sequence

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.fight_record import FightRecord

LOG_BUFFER = 500
FIGHT_BUFFER = 200


class MultiSnapshotStore:
    """What WatchApp keeps about every character it watches.

    Buffers are PER CHARACTER, not shared: a shared cycle deque would let one
    busy character silently evict another's history. Fights keep their own
    buffer for the same reason the single-character app did — a long stretch of
    non-fight cycles must not push old fights out.
    """

    def __init__(
        self,
        characters: Sequence[str],
        log_buffer: int = LOG_BUFFER,
        fight_buffer: int = FIGHT_BUFFER,
    ) -> None:
        self._last: dict[str, CycleSnapshot | None] = {c: None for c in characters}
        self._recent: dict[str, deque[CycleSnapshot]] = {
            c: deque(maxlen=log_buffer) for c in characters
        }
        self._fights: dict[str, deque[FightRecord]] = {
            c: deque(maxlen=fight_buffer) for c in characters
        }

    def record(self, snap: CycleSnapshot) -> None:
        character = snap.character
        if character not in self._last:
            raise KeyError(f"snapshot for {character!r}, who is not in this roster")
        self._last[character] = snap
        self._recent[character].append(snap)
        if snap.fight is not None:
            self._fights[character].append(snap.fight)

    def last(self, character: str) -> CycleSnapshot | None:
        return self._last[character]

    def recent(self, character: str) -> deque[CycleSnapshot]:
        return self._recent[character]

    def fights(self, character: str) -> deque[FightRecord]:
        return self._fights[character]

    def latest_all(self) -> dict[str, CycleSnapshot]:
        """Every character that has produced at least one cycle."""
        return {c: snap for c, snap in self._last.items() if snap is not None}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tui/test_multi_snapshot_store.py -v`
Expected: all 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_tui/test_multi_snapshot_store.py src/artifactsmmo_cli/tui/multi_snapshot_store.py
git commit -m "feat(tui): add MultiSnapshotStore"
```

---

### Task 14: Draw non-focused characters on the map

`MapPane` keeps animating only the focused character (swing frames and glide are keyed to a single action timeline). Others render as static coloured sprites at their last known tile.

**Files:**
- Modify: `src/artifactsmmo_cli/tui/widgets/map_pane.py` (`__init__` ~line 98, `_tile_sprite_and_terrain` ~line 332, `_line_signature` ~line 428)
- Test: `tests/test_tui/test_map_pane_multi.py`

**Interfaces:**
- Consumes: `Sprite` from `artifactsmmo_cli.tui.sprites`.
- Produces: `MapPane.set_others(others: dict[tuple[int, int], Sprite]) -> None`. Used by Task 15.

- [ ] **Step 1: Write the failing test**

```python
"""MapPane draws non-focused characters at their own tiles."""

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.character_roster import CharacterRoster
from artifactsmmo_cli.tui.widgets.map_pane import TILE_H, TILE_W, MapPane


def _snap(x: int = 0, y: int = 0) -> CycleSnapshot:
    return CycleSnapshot(
        cycle_index=1, timestamp="2026-07-30T12:00:00Z", character="alice",
        x=x, y=y, level=1, xp=0, max_xp=150, hp=120, max_hp=120, gold=0,
        selected_goal="ReachLevel(50)", action="Rest()", outcome="ok",
    )


def _pane() -> MapPane:
    return MapPane(GameData())


def test_others_default_to_empty():
    assert _pane()._others == {}


def test_a_second_character_renders_at_its_own_tile():
    roster = CharacterRoster(["alice", "bob"])
    pane = _pane()
    pane.update_snapshot(_snap(0, 0))
    plain = pane._render_viewport(_snap(0, 0), TILE_W * 5, TILE_H * 5 + 1).plain
    pane.set_others({(1, 0): roster.sprite("bob")})
    with_bob = pane._render_viewport(_snap(0, 0), TILE_W * 5, TILE_H * 5 + 1).plain
    assert with_bob != plain


def test_setting_others_invalidates_the_line_cache():
    """A stale cached Strip would leave a character painted where they no
    longer are."""
    roster = CharacterRoster(["alice", "bob"])
    pane = _pane()
    pane.update_snapshot(_snap(0, 0))
    pane._line_cache[3] = ("stale-signature", None)
    pane.set_others({(1, 0): roster.sprite("bob")})
    assert pane._line_cache == {}


def test_the_line_signature_changes_when_a_character_moves_onto_that_row():
    roster = CharacterRoster(["alice", "bob"])
    pane = _pane()
    pane.update_snapshot(_snap(0, 0))
    height = TILE_H * 5 + 1
    args = (1, height, (0, 0), pane._player_sprite(0.0), {})
    before = pane._line_signature(*args)
    pane.set_others({(0, -2): roster.sprite("bob")})
    assert pane._line_signature(*args) != before


def test_the_focused_character_wins_a_shared_tile():
    """set_others is given only non-focused characters, so the centre tile is
    always the focused one."""
    roster = CharacterRoster(["alice", "bob"])
    pane = _pane()
    pane.update_snapshot(_snap(0, 0))
    pane.set_others({(0, 0): roster.sprite("bob")})
    sprite, _terrain = pane._tile_sprite_and_terrain(
        0, 0, True, pane._player_sprite(0.0)
    )
    assert sprite is pane._player_sprite(0.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_map_pane_multi.py -v`
Expected: FAIL — `AttributeError: 'MapPane' object has no attribute '_others'`.

- [ ] **Step 3: Write minimal implementation**

In `MapPane.__init__`, after `self._planning_start = 0.0`:

```python
        # Non-focused characters: world tile -> their recoloured sprite. They
        # render statically; swing and glide frames are keyed to ONE action
        # timeline, so only the focused character animates.
        self._others: dict[tuple[int, int], Sprite] = {}
```

Add the setter next to `update_snapshot`:

```python
    def set_others(self, others: dict[tuple[int, int], Sprite]) -> None:
        """Place the non-focused characters. Cheap to call on every foreign
        cycle: it does NOT touch the focused character's animation state."""
        self._others = others
        self._line_cache.clear()  # a stale Strip would strand a moved character
        self.refresh()
```

In `_tile_sprite_and_terrain`, insert the lookup after the `is_player` branch:

```python
    def _tile_sprite_and_terrain(self, wx: int, wy: int, is_player: bool,
                                 player_sprite: Sprite) -> tuple[Sprite, str]:
        if is_player:
            return player_sprite, WALKABLE_COLOR
        other = self._others.get((wx, wy))
        if other is not None:
            return other, WALKABLE_COLOR
        content = self._tile_index.get((wx, wy))
        ...  # unchanged
```

In `_line_signature`, fold the row's other-characters into the key, immediately
before the return:

```python
        others = tuple(
            sorted(
                (xy, id(sprite))
                for xy, sprite in self._others.items()
                if xy[1] - center[1] == row_off
            )
        )
        return (center, trow, sub, psprite, ov, others)
```

Confirm `Sprite` is already imported in `map_pane.py`; add it to the existing
`from artifactsmmo_cli.tui.sprites import ...` line if absent.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tui/test_map_pane_multi.py tests/test_tui/test_map_pane.py tests/test_tui/test_map_pane_animation.py -v`
Expected: all PASS — the existing map tests must be untouched.

- [ ] **Step 5: Commit**

```bash
git add tests/test_tui/test_map_pane_multi.py src/artifactsmmo_cli/tui/widgets/map_pane.py
git commit -m "feat(tui): draw non-focused characters on the map"
```

---

### Task 15: Multi-character `WatchApp` with focus keys

`WatchApp(character=...)` becomes `WatchApp(characters=[...])`. This is a breaking signature change with exactly one production caller (`_run_with_tui`) and one test helper — update both. Do not keep a compatibility shim; the project forbids two implementations of one thing.

**Files:**
- Modify: `src/artifactsmmo_cli/tui/app.py`
- Modify: `src/artifactsmmo_cli/commands/play.py:142` (the `WatchApp(...)` construction)
- Modify: `tests/test_tui/test_app.py` (`_make_app` helper)
- Create: `src/artifactsmmo_cli/tui/roster_entry.py`
- Modify: `src/artifactsmmo_cli/tui/widgets/status_pane.py`
- Test: `tests/test_tui/test_app_multi.py`, `tests/test_tui/test_status_pane_roster.py`

**Interfaces:**
- Consumes: `CharacterRoster` (Task 12), `MultiSnapshotStore` (Task 13), `MapPane.set_others` (Task 14), `ChildState` (Task 11).
- Produces: `WatchApp(characters: list[str], game_data, api=None)`, `WatchApp.focused: str`, `WatchApp.action_focus(slot: int)`, `WatchApp.update_child_state(state: ChildState)`; `RosterEntry`; `StatusPane.update_roster(entries: tuple[RosterEntry, ...])`. Used by Task 16.

- [ ] **Step 1: Write the failing test**

```python
"""WatchApp with a multi-character roster and 1-5 focus keys."""

import pytest

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.multi.child_state import ChildState
from artifactsmmo_cli.tui.app import WatchApp
from artifactsmmo_cli.tui.widgets.map_pane import MapPane
from artifactsmmo_cli.tui.widgets.status_pane import StatusPane


def _snap(character: str, **overrides) -> CycleSnapshot:
    base = dict(
        cycle_index=1, timestamp="2026-07-30T12:00:00Z", character=character,
        x=0, y=0, level=1, xp=0, max_xp=150, hp=120, max_hp=120, gold=0,
        selected_goal="ReachLevel(50)", action="Rest()", outcome="ok",
    )
    base.update(overrides)
    return CycleSnapshot(**base)


def _app(names=("alice", "bob", "carol")) -> WatchApp:
    return WatchApp(characters=list(names), game_data=GameData())


def test_the_first_roster_character_is_focused_initially():
    assert _app().focused == "alice"


def test_keys_one_to_five_are_bound():
    keys = {binding[0] for binding in WatchApp.BINDINGS}
    assert {"1", "2", "3", "4", "5"} <= keys


def test_focusing_an_occupied_slot_switches_character():
    app = _app()
    app.action_focus(2)
    assert app.focused == "bob"


def test_focusing_an_empty_slot_is_a_no_op():
    app = _app(names=("alice",))
    app.action_focus(4)
    assert app.focused == "alice"


@pytest.mark.asyncio
async def test_only_the_focused_characters_snapshot_drives_the_status_pane():
    app = _app()
    async with app.run_test():
        app.update_snapshot(_snap("bob", level=42))
        assert app.query_one("#status", StatusPane).snapshot is None
        app.update_snapshot(_snap("alice", level=7))
        assert app.query_one("#status", StatusPane).snapshot.level == 7


@pytest.mark.asyncio
async def test_a_foreign_snapshot_still_places_that_character_on_the_map():
    app = _app()
    async with app.run_test():
        app.update_snapshot(_snap("bob", x=3, y=4))
        assert (3, 4) in app.query_one("#map", MapPane)._others


@pytest.mark.asyncio
async def test_switching_focus_repaints_the_panes_from_the_store():
    app = _app()
    async with app.run_test():
        app.update_snapshot(_snap("bob", level=42))
        app.action_focus(2)
        assert app.query_one("#status", StatusPane).snapshot.level == 42


@pytest.mark.asyncio
async def test_the_focused_character_is_not_drawn_twice():
    """The focused character renders as the centred animated sprite, so they
    must be absent from the static others map."""
    app = _app()
    async with app.run_test():
        app.update_snapshot(_snap("alice", x=1, y=1))
        assert (1, 1) not in app.query_one("#map", MapPane)._others


def test_child_state_reaches_the_roster():
    app = _app()
    app.update_child_state(
        ChildState(character="bob", alive=False, restarts=2,
                   last_reason="stuck_exit", stderr_tail=("boom",))
    )
    entry = next(e for e in app.roster_entries() if e.character == "bob")
    assert entry.alive is False
    assert entry.restarts == 2
```

And the roster line test:

```python
"""StatusPane renders the multi-character roster line."""

from artifactsmmo_cli.tui.palette import BLOOD, TUNIC
from artifactsmmo_cli.tui.roster_entry import RosterEntry
from artifactsmmo_cli.tui.widgets.status_pane import StatusPane


def _entries():
    return (
        RosterEntry(slot=1, character="alice", color=TUNIC, level=19,
                    x=0, y=2, alive=True, restarts=0, focused=True),
        RosterEntry(slot=2, character="bob", color=BLOOD, level=7,
                    x=5, y=-1, alive=False, restarts=2, focused=False),
    )


def test_roster_line_names_every_character_with_slot_and_level():
    pane = StatusPane()
    pane.update_roster(_entries())
    text = pane.roster_text().plain
    assert "1" in text and "alice" in text and "19" in text
    assert "2" in text and "bob" in text


def test_a_dead_character_is_visibly_marked():
    pane = StatusPane()
    pane.update_roster(_entries())
    assert "✗" in pane.roster_text().plain


def test_a_restart_count_is_shown_when_nonzero():
    pane = StatusPane()
    pane.update_roster(_entries())
    assert "2" in pane.roster_text().plain


def test_a_single_character_roster_renders_nothing():
    """Single-character play must look exactly as it did before."""
    pane = StatusPane()
    pane.update_roster(_entries()[:1])
    assert pane.roster_text().plain == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tui/test_app_multi.py tests/test_tui/test_status_pane_roster.py -v`
Expected: FAIL — `TypeError: WatchApp.__init__() got an unexpected keyword argument 'characters'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/artifactsmmo_cli/tui/roster_entry.py`:

```python
"""RosterEntry: one character's line in the multi-character roster strip."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RosterEntry:
    slot: int
    character: str
    color: str
    level: int
    x: int
    y: int
    alive: bool
    restarts: int
    focused: bool
```

In `status_pane.py`, add the roster state and renderer:

```python
    def update_roster(self, entries: tuple[RosterEntry, ...]) -> None:
        self._roster = entries
        self.refresh()

    def roster_text(self) -> Text:
        """One line naming every character. Empty for a single-character run,
        which must look exactly as it did before multi-character support."""
        line = Text(no_wrap=True, overflow="crop")
        if len(self._roster) < 2:
            return line
        for entry in self._roster:
            marker = "●" if entry.alive else "✗"
            label = f"[{entry.slot}]{marker}{entry.character} L{entry.level} ({entry.x},{entry.y})"
            if entry.restarts:
                label += f" ↻{entry.restarts}"
            style = f"bold {entry.color}" if entry.focused else entry.color
            line.append(label + "  ", style=style)
        return line
```

Initialise `self._roster: tuple[RosterEntry, ...] = ()` in `StatusPane.__init__`,
import `RosterEntry`, and prepend `roster_text()` to whatever `Group` the pane's
`render` already returns.

In `app.py`, replace the single-character state:

```python
    def __init__(self, characters: list[str], game_data: GameData,
                 api: APIWrapper | None = None) -> None:
        super().__init__()
        self._roster = CharacterRoster(characters)
        self._game_data = game_data
        self._api = api
        self.focused = self._roster.names[0]
        self.title = f"artifactsmmo watch: {', '.join(self._roster.names)}"
        self._store = MultiSnapshotStore(self._roster.names)
        self._child_states: dict[str, ChildState] = {}
        SpriteCoverageAudit().run(game_data)
```

Add the focus bindings to `BINDINGS`:

```python
        ("1", "focus(1)", "Char 1"),
        ("2", "focus(2)", "Char 2"),
        ("3", "focus(3)", "Char 3"),
        ("4", "focus(4)", "Char 4"),
        ("5", "focus(5)", "Char 5"),
```

Replace `update_snapshot` with per-character routing:

```python
    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self._store.record(snap)
        if snap.character == self.focused:
            self._repaint_focused(snap)
        self._repaint_others()
        self._repaint_roster()

    def _repaint_focused(self, snap: CycleSnapshot) -> None:
        self.query_one("#status", StatusPane).update_snapshot(snap)
        self.query_one("#map", MapPane).update_snapshot(snap)
        self.query_one("#inv", InventoryPane).update_snapshot(snap)
        self.query_one("#log", LogPane).update_snapshot(snap)
        top = self.screen
        if isinstance(top, (CharacterScreen, LogScreen, PlanScreen, FightScreen)):
            top.update_snapshot(snap)

    def _repaint_others(self) -> None:
        """Place every character EXCEPT the focused one; the focused character
        is already drawn as the centred, animated sprite."""
        others = {
            (snap.x, snap.y): self._roster.sprite(name)
            for name, snap in self._store.latest_all().items()
            if name != self.focused
        }
        self.query_one("#map", MapPane).set_others(others)

    def action_focus(self, slot: int) -> None:
        name = self._roster.at(slot)
        if name is None or name == self.focused:
            return
        self.focused = name
        snap = self._store.last(name)
        if snap is not None:
            self._repaint_focused(snap)
        self._repaint_others()
        self._repaint_roster()

    def update_child_state(self, state: ChildState) -> None:
        self._child_states[state.character] = state
        self._repaint_roster()

    def roster_entries(self) -> tuple[RosterEntry, ...]:
        entries = []
        for slot, name in enumerate(self._roster.names, start=1):
            snap = self._store.last(name)
            child = self._child_states.get(name)
            entries.append(RosterEntry(
                slot=slot, character=name, color=self._roster.color(name),
                level=snap.level if snap else 0,
                x=snap.x if snap else 0, y=snap.y if snap else 0,
                alive=child.alive if child else True,
                restarts=child.restarts if child else 0,
                focused=name == self.focused,
            ))
        return tuple(entries)

    def _repaint_roster(self) -> None:
        self.query_one("#status", StatusPane).update_roster(self.roster_entries())
```

`_repaint_roster` and `_repaint_others` call `query_one`, which raises before
the app is mounted. Guard both with `if not self.is_running: return` so
`update_child_state` and `action_focus` stay callable in unmounted unit tests.

Update the remaining single-character references: `self._last_snapshot` →
`self._store.last(self.focused)`, `self._recent_snapshots` →
`self._store.recent(self.focused)`, `self._fights` →
`self._store.fights(self.focused)`, and `self._character` → `self.focused` in
`_fetch_older_fights` and `action_toggle_fight`. Delete `LOG_BUFFER`,
`FIGHT_BUFFER`, and `_store_snapshot` — `MultiSnapshotStore` owns them now.

In `play.py:142`, change the construction to a one-character roster:

```python
    app = WatchApp(characters=[character], game_data=player.game_data,
                   api=APIWrapper(client))
```

In `tests/test_tui/test_app.py`, update the helper:

```python
def _make_app(character: str = "hero") -> WatchApp:
    return WatchApp(characters=[character], game_data=GameData())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tui/ -v`
Expected: all PASS, including the pre-existing `test_app.py` suite.

- [ ] **Step 5: Commit**

```bash
git add tests/test_tui src/artifactsmmo_cli/tui src/artifactsmmo_cli/commands/play.py
git commit -m "feat(tui): multi-character WatchApp with 1-5 focus keys"
```

---

### Task 16: `MultiRun` — wire `play --all` together

**Files:**
- Create: `src/artifactsmmo_cli/multi/multi_run.py`
- Modify: `src/artifactsmmo_cli/commands/play.py` (activate the `--all` branch deferred in Task 8)
- Test: `tests/test_multi/test_multi_run.py`

**Interfaces:**
- Consumes: everything from Tasks 4, 5, 9, 10, 11, 12, 15.
- Produces: `MultiRun(...).run() -> None`, and `MultiRun.child_argv(character, budget) -> list[str]`.

- [ ] **Step 1: Write the failing test**

```python
"""MultiRun: roster discovery, budget split, child argv, headless vs TUI."""

import pytest

from artifactsmmo_cli.multi.multi_run import MultiRun
from artifactsmmo_cli.utils.rate_budget import parse_rate_limits, split_budget

_RATES = {
    "data": {
        "account": {"second": {"limit": 10}, "hour": {"limit": 300}},
        "data": {"second": {"limit": 10}, "minute": {"limit": 200}, "hour": {"limit": 2000}},
        "action": {"second": {"limit": 10}, "minute": {"limit": 100}, "hour": {"limit": 5000}},
    }
}


def _run(**kwargs) -> MultiRun:
    return MultiRun(verbose=False, dry_run=False, trace=False, learn=False,
                    learn_db=None, tui=False, refresh_game_data=False, **kwargs)


def test_child_argv_carries_emit_events_and_the_budget():
    budget = split_budget(parse_rate_limits(_RATES), children=5)
    argv = _run().child_argv("alice", budget)
    assert "--emit-events" in argv
    assert "alice" in argv
    assert "--rate-budget" in argv
    assert budget.to_json() in argv


def test_child_argv_never_passes_all_to_a_child():
    """A child spawning its own supervisor would fork-bomb the account."""
    budget = split_budget(parse_rate_limits(_RATES), children=1)
    assert "--all" not in _run().child_argv("alice", budget)


def test_child_argv_propagates_the_run_flags():
    budget = split_budget(parse_rate_limits(_RATES), children=1)
    argv = MultiRun(verbose=True, dry_run=True, trace=True, learn=True,
                    learn_db="/tmp/l.db", tui=False,
                    refresh_game_data=True).child_argv("alice", budget)
    for flag in ("--verbose", "--dry-run", "--trace", "--learn", "--refresh-game-data"):
        assert flag in argv
    assert "/tmp/l.db" in argv


def test_child_argv_never_passes_tui_to_a_child():
    """Only the parent renders; a child TUI would fight for the terminal."""
    budget = split_budget(parse_rate_limits(_RATES), children=1)
    argv = MultiRun(verbose=False, dry_run=False, trace=False, learn=False,
                    learn_db=None, tui=True, refresh_game_data=False).child_argv("a", budget)
    assert "--tui" not in argv


def test_an_empty_roster_fails_loudly():
    with pytest.raises(ValueError, match="no characters"):
        _run().build_pool(characters=[], rates=_RATES)


def test_the_budget_is_split_by_the_actual_child_count():
    pool = _run().build_pool(characters=["a", "b"], rates=_RATES)
    assert pool.characters() == ("a", "b")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_multi/test_multi_run.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.multi.multi_run'`.

- [ ] **Step 3: Write minimal implementation**

```python
"""MultiRun: build and run the `play --all` supervisor, with or without the TUI."""

import asyncio
import sys

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.api_wrapper import APIWrapper
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config
from artifactsmmo_cli.multi.character_supervisor import CharacterSupervisor
from artifactsmmo_cli.multi.child_event import ChildEvent, SnapshotEvent
from artifactsmmo_cli.multi.supervisor_pool import SupervisorPool
from artifactsmmo_cli.tui.app import WatchApp
from artifactsmmo_cli.utils.rate_budget import (
    BucketBudgets,
    parse_rate_limits,
    split_budget,
)


class MultiRun:
    """Owns the `play --all` lifecycle: discover the roster, read and divide the
    rate budget, spawn a supervised child per character, and present them.

    The supervisor and Textual share one asyncio loop, so events go straight
    from a child's pipe to the app — the single-character path's thread bridge
    is not needed here.
    """

    def __init__(self, verbose: bool, dry_run: bool, trace: bool, learn: bool,
                 learn_db: str | None, tui: bool, refresh_game_data: bool) -> None:
        self._verbose = verbose
        self._dry_run = dry_run
        self._trace = trace
        self._learn = learn
        self._learn_db = learn_db
        self._tui = tui
        self._refresh_game_data = refresh_game_data
        self._app: WatchApp | None = None

    def child_argv(self, character: str, budget: BucketBudgets) -> list[str]:
        """The command line for one child. Never `--all` (that would fork-bomb
        the account) and never `--tui` (only the parent owns the terminal)."""
        argv = [sys.executable, "-m", "artifactsmmo_cli.main", "play", character,
                "--emit-events", "--rate-budget", budget.to_json()]
        if self._verbose:
            argv.append("--verbose")
        if self._dry_run:
            argv.append("--dry-run")
        if self._trace:
            argv.append("--trace")
        if self._learn:
            argv.append("--learn")
            if self._learn_db is not None:
                argv += ["--learn-db", self._learn_db]
        if self._refresh_game_data:
            argv.append("--refresh-game-data")
        return argv

    def build_pool(self, characters: list[str], rates: dict) -> SupervisorPool:
        if not characters:
            raise ValueError("account has no characters to play")
        budget = split_budget(parse_rate_limits(rates), children=len(characters))
        return SupervisorPool([
            CharacterSupervisor(
                character=name,
                argv=self.child_argv(name, budget),
                on_event=self._on_event,
            )
            for name in characters
        ])

    def _on_event(self, event: ChildEvent) -> None:
        if self._app is not None and isinstance(event, SnapshotEvent):
            self._app.update_snapshot(event.payload)

    def run(self) -> None:
        config = Config.from_token_file()
        client = ClientManager().client
        api = APIWrapper(client)
        characters = [c.name for c in api.get_my_characters().data]
        rates = api.get_rate_limits().to_dict()
        pool = self.build_pool(characters, rates)
        if not self._tui:
            asyncio.run(self._run_headless(pool))
            return
        game_data = GameData.load(
            client, ttl_minutes=config.game_data_ttl_minutes,
            force_refresh=self._refresh_game_data)
        self._app = WatchApp(characters=characters, game_data=game_data, api=api)
        self._app.attach_pool(pool)
        self._app.run()

    async def _run_headless(self, pool: SupervisorPool) -> None:
        await pool.run()
```

Add `get_rate_limits` to `APIWrapper` beside the other `my_account` calls:

```python
    def get_rate_limits(self) -> Any:
        return get_rate_limits_sync(client=self._client)
```

with the matching import
`from artifactsmmo_api_client.api.my_account.get_rate_limits_my_rates_get import sync as get_rate_limits_sync`.

Add pool attachment to `WatchApp`:

```python
    def attach_pool(self, pool: "SupervisorPool") -> None:
        """Run the child supervisors on Textual's own loop."""
        self._pool = pool

    def on_mount(self) -> None:
        if self._pool is not None:
            self.run_worker(self._pool.run(), name="supervisors")
            self.set_interval(1.0, self._poll_child_states)

    def _poll_child_states(self) -> None:
        if self._pool is None:
            return
        for character in self._pool.characters():
            self.update_child_state(self._pool.state(character))
```

Initialise `self._pool: SupervisorPool | None = None` in `WatchApp.__init__`.

Finally, activate the deferred branch in `play.py` (import `MultiRun` at the top):

```python
    if all_characters:
        MultiRun(verbose=verbose, dry_run=dry_run, trace=trace, learn=learn,
                 learn_db=learn_db, tui=tui,
                 refresh_game_data=refresh_game_data).run()
        return
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_multi/ tests/test_commands/ -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_multi/test_multi_run.py src/artifactsmmo_cli/multi/multi_run.py src/artifactsmmo_cli/commands/play.py src/artifactsmmo_cli/api_wrapper.py src/artifactsmmo_cli/tui/app.py
git commit -m "feat(play): wire play --all supervisor and multi-character TUI"
```

---

### Task 17: Apply the rate governor to outbound requests

Without this, `--rate-budget` is parsed and ignored — the budget would be decorative.

**Files:**
- Modify: `src/artifactsmmo_cli/commands/play.py` (construct the governor from `--rate-budget`)
- Modify: `src/artifactsmmo_cli/ai/player.py` (acquire before each request)
- Test: `tests/test_ai/test_player_rate_governed.py`

**Interfaces:**
- Consumes: `RateGovernor` (Task 5), `BucketBudgets.from_json` (Task 4).
- Produces: `GamePlayer.set_rate_governors(data: RateGovernor, action: RateGovernor) -> None`.

- [ ] **Step 1: Write the failing test**

```python
"""The rate budget actually throttles outbound requests."""

from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.utils.rate_budget import WindowBudget
from artifactsmmo_cli.utils.rate_governor import RateGovernor


class _FakeTime:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def test_governors_default_to_none_so_single_character_play_is_unthrottled():
    player = GamePlayer(character="hero")
    assert player._data_governor is None
    assert player._action_governor is None


def test_a_data_read_acquires_from_the_data_governor():
    fake = _FakeTime()
    player = GamePlayer(character="hero")
    governor = RateGovernor(
        WindowBudget(second=1, minute=None, hour=None, day=None),
        clock=fake.clock, sleep=fake.sleep,
    )
    player.set_rate_governors(data=governor, action=governor)
    player._acquire_data()
    player._acquire_data()
    assert fake.slept == [1.0]


def test_acquiring_without_a_governor_is_a_no_op():
    GamePlayer(character="hero")._acquire_data()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_player_rate_governed.py -v`
Expected: FAIL — `AttributeError: 'GamePlayer' object has no attribute '_data_governor'`.

- [ ] **Step 3: Write minimal implementation**

In `GamePlayer.__init__`:

```python
        # Set only by `play --all` children, which share one per-IP budget.
        # A lone `play <character>` is unthrottled, exactly as before.
        self._data_governor: RateGovernor | None = None
        self._action_governor: RateGovernor | None = None
```

```python
    def set_rate_governors(self, data: RateGovernor, action: RateGovernor) -> None:
        self._data_governor = data
        self._action_governor = action

    def _acquire_data(self) -> None:
        if self._data_governor is not None:
            self._data_governor.acquire()

    def _acquire_action(self) -> None:
        if self._action_governor is not None:
            self._action_governor.acquire()
```

Call `self._acquire_data()` immediately before each read in
`_fetch_world_state` (the `get_character` call at line 1345), `_fetch_active_events`,
`_fetch_raids`, `_sync_bank`, and `_fetch_open_orders`; call
`self._acquire_action()` immediately before the action dispatch in `_execute`.

In `play.py`, build the governors when `--rate-budget` is present:

```python
    if rate_budget is not None:
        budgets = BucketBudgets.from_json(rate_budget)
        player.set_rate_governors(
            data=RateGovernor(budgets.data), action=RateGovernor(budgets.action)
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_player_rate_governed.py tests/test_ai/ -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ai/test_player_rate_governed.py src/artifactsmmo_cli/ai/player.py src/artifactsmmo_cli/commands/play.py
git commit -m "feat(ai): enforce the per-child rate budget on outbound requests"
```

---

### Task 18: 429 backoff

There is no 429 path today — `utils/helpers.py:21` only maps the code to a message string. Five characters must degrade gracefully rather than fail an action with an unexplained error.

**Files:**
- Create: `src/artifactsmmo_cli/utils/retry_after.py`
- Modify: `src/artifactsmmo_cli/ai/player.py` (the `ApiActionError` handler at line 1176)
- Test: `tests/test_utils/test_retry_after.py`, `tests/test_ai/test_player_rate_limited.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `retry_after_seconds(headers: Mapping[str, str], attempt: int) -> float`.

- [ ] **Step 1: Write the failing test**

```python
"""Retry-After parsing with an exponential fallback."""

from artifactsmmo_cli.utils.retry_after import retry_after_seconds


def test_a_numeric_retry_after_header_is_honored():
    assert retry_after_seconds({"Retry-After": "12"}, attempt=0) == 12.0


def test_the_header_is_matched_case_insensitively():
    assert retry_after_seconds({"retry-after": "3"}, attempt=0) == 3.0


def test_a_missing_header_falls_back_to_exponential_backoff():
    """The API documents 429 but promises no Retry-After header."""
    assert [retry_after_seconds({}, attempt=n) for n in range(3)] == [1.0, 2.0, 4.0]


def test_an_unparseable_header_falls_back_to_backoff():
    assert retry_after_seconds({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}, attempt=1) == 2.0


def test_the_fallback_is_capped():
    assert retry_after_seconds({}, attempt=20) <= 60.0
```

And the player-level test:

```python
"""A 429 is a throttle to wait out, not an unexplained action failure."""

from artifactsmmo_cli.ai.player import GamePlayer


def test_429_is_classified_as_rate_limited():
    assert GamePlayer.is_rate_limited(429) is True
    assert GamePlayer.is_rate_limited(478) is False


def test_the_rate_limited_outcome_is_named():
    assert GamePlayer.RATE_LIMITED_OUTCOME == "error:rate_limited"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_utils/test_retry_after.py tests/test_ai/test_player_rate_limited.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.utils.retry_after'`.

- [ ] **Step 3: Write minimal implementation**

```python
"""retry_after_seconds: how long to wait after an HTTP 429."""

from collections.abc import Mapping

BASE_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 60.0


def retry_after_seconds(headers: Mapping[str, str], attempt: int) -> float:
    """Seconds to wait before retrying a throttled request.

    The API documents 429 but does not promise a Retry-After header, so an
    absent or non-numeric header falls back to capped exponential backoff. The
    HTTP-date form of Retry-After is deliberately not parsed: the fallback is
    already correct behaviour, and a second parsing path would be a second
    level of error handling for one failure.
    """
    raw = next(
        (v for k, v in headers.items() if k.lower() == "retry-after"), None
    )
    if raw is not None and raw.strip().isdigit():
        return float(raw.strip())
    return min(BASE_BACKOFF_SECONDS * (2**attempt), MAX_BACKOFF_SECONDS)
```

In `player.py`, add the classifier and handle 429 in the existing
`except ApiActionError as e:` chain, before the generic `else` branch:

```python
    RATE_LIMITED_OUTCOME = "error:rate_limited"

    @staticmethod
    def is_rate_limited(code: int) -> bool:
        return code == 429
```

```python
            elif self.is_rate_limited(e.code):
                # Per-IP throttle, not a bad plan. Wait it out and let the next
                # cycle retry the SAME action rather than replanning around a
                # failure that was never about the game state.
                delay = retry_after_seconds(getattr(e, "headers", {}), self._rate_limit_attempts)
                self._rate_limit_attempts += 1
                print(f"[{self._now()}] Rate limited (HTTP 429) — waiting {delay:.0f}s")
                time.sleep(delay)
                outcome = self.RATE_LIMITED_OUTCOME
```

Initialise `self._rate_limit_attempts = 0` in `__init__`, and reset it to 0 on
any successful action so the backoff does not ratchet across an entire session.

Before writing this, confirm where a 429 actually surfaces: run
`uv run artifactsmmo info items --help` style traffic is not enough — instead
check whether `ApiActionError` carries the status code for non-action endpoints
too, and if `get_character` reports 429 through the `HTTP {code}` path at
`player.py:1364` instead. Attach the handling at whichever layer actually sees
it; do not add it in both places.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_utils/test_retry_after.py tests/test_ai/test_player_rate_limited.py tests/test_ai/ -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_utils/test_retry_after.py tests/test_ai/test_player_rate_limited.py src/artifactsmmo_cli/utils/retry_after.py src/artifactsmmo_cli/ai/player.py
git commit -m "feat(ai): honor HTTP 429 with Retry-After and capped backoff"
```

---

### Task 19: Rate-budget regression guard

The constraint that motivated `GlobalReadsCache` must fail loudly if a future change reintroduces a per-cycle data read.

**Files:**
- Test: `tests/test_ai/test_rate_budget_headroom.py`
- Create: `tests/fixtures/my_rates.json`

**Interfaces:**
- Consumes: `parse_rate_limits` (Task 4).
- Produces: nothing.

- [ ] **Step 1: Write the test (it should pass immediately — it guards Task 3)**

`tests/fixtures/my_rates.json`:

```json
{
  "data": {
    "account": {"second": {"limit": 10}, "hour": {"limit": 300}},
    "data": {"second": {"limit": 10}, "minute": {"limit": 200}, "hour": {"limit": 2000}},
    "action": {"second": {"limit": 10}, "minute": {"limit": 100}, "hour": {"limit": 5000}}
  }
}
```

```python
"""Five characters must fit inside the per-IP hourly data budget.

The measured peak comes from play-trace-Robby.jsonl: a real 7-day run of 11224
cycles whose busiest hour held 158 cycles. Before GlobalReadsCache each cycle
cost three data reads, which puts five characters at 2370/hour against a
2000/hour ceiling. If a future change adds a per-cycle data read, this fails.
"""

import json
from pathlib import Path

from artifactsmmo_cli.utils.rate_budget import parse_rate_limits

PEAK_CYCLES_PER_HOUR = 158
MAX_CHARACTERS = 5
DATA_READS_PER_CYCLE = 1
"""get_character only. active_events and raids are served by GlobalReadsCache."""

GLOBAL_READ_KEYS = 2       # active_events, raids
GLOBAL_CACHE_TTL_SECONDS = 60
GLOBAL_REFRESHES_PER_HOUR = 3600 // GLOBAL_CACHE_TTL_SECONDS


def _hourly_data_limit() -> int:
    payload = json.loads(
        (Path(__file__).parent.parent / "fixtures" / "my_rates.json").read_text()
    )
    return parse_rate_limits(payload).data.hour


def test_five_characters_fit_under_the_hourly_data_ceiling():
    per_character = PEAK_CYCLES_PER_HOUR * DATA_READS_PER_CYCLE
    cache_refreshes = GLOBAL_REFRESHES_PER_HOUR * GLOBAL_READ_KEYS
    projected = MAX_CHARACTERS * (per_character + cache_refreshes)
    limit = _hourly_data_limit()
    assert projected < limit, (
        f"{MAX_CHARACTERS} characters project {projected} data requests/hour at "
        f"peak against a {limit}/hour ceiling. If DATA_READS_PER_CYCLE grew, a "
        f"per-cycle read was added that GlobalReadsCache does not cover."
    )


def test_the_uncached_shape_would_have_breached_the_ceiling():
    """Documents why the cache exists: without it the same five characters
    overrun the budget."""
    uncached = MAX_CHARACTERS * PEAK_CYCLES_PER_HOUR * 3
    assert uncached > _hourly_data_limit()
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/test_ai/test_rate_budget_headroom.py -v`
Expected: both PASS (Task 3 already reduced the per-cycle read count).

- [ ] **Step 3: Verify it actually guards**

Temporarily set `DATA_READS_PER_CYCLE = 3`, re-run, confirm the first test FAILS
with the explanatory message, then set it back to `1`.

- [ ] **Step 4: Run the whole suite and the type/lint gates**

```bash
uv run pytest tests/ -q
uv run mypy src/
uv run ruff check src/ tests/
```
Expected: 0 errors, 0 warnings, 0 skipped.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ai/test_rate_budget_headroom.py tests/fixtures/my_rates.json
git commit -m "test: guard the five-character hourly data budget"
```

---

### Task 20: Documentation and final gate

**Files:**
- Modify: `README.md`
- Modify: `docs/PLAN_multi_character.md` (mark implemented)
- Test: the full gate.

- [ ] **Step 1: Document the new commands in `README.md`**

Add under the existing play documentation:

```markdown
### Playing multiple characters

`artifactsmmo play --all --tui` supervises every character on the account, one
subprocess each, in a single TUI. Keys `1`–`5` choose which character the map
centres on and which character the status, inventory, and log panes follow. All
characters appear on the map at once, same sprite, one colour each.

`artifactsmmo play --all` runs the same supervisor headless, streaming each
child's log prefixed with its character name.

Characters play independently — they share a bank but do not coordinate, and a
lost race for a banked item is an ordinary replan. The account's `/my/rates`
budget is read once and divided across the children.

`artifactsmmo play <character>` is unchanged: one character, in-process.
```

- [ ] **Step 2: Mark the design implemented**

In `docs/PLAN_multi_character.md`, change the status line to
`**Status:** IMPLEMENTED` and add the implementing commit range.

- [ ] **Step 3: Run the full local gate**

```bash
bash formal/gate.sh
```
Expected: green, in roughly 5 minutes. Redirect to a file rather than piping to
`tail` — a pipeline reports the tail's exit code, not the gate's.

- [ ] **Step 4: Verify the formal surface gained no obligations**

Confirm `formal/` is untouched by this branch:

```bash
git diff --stat main -- formal/
```
Expected: empty. This work adds no `MeansKind`, no `GuardKind`, and changes no
proven decision function.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/PLAN_multi_character.md
git commit -m "docs: document play --all multi-character support"
```

---

## Self-Review

**Spec coverage.** Every section of `docs/PLAN_multi_character.md` maps to a task: process model → 10, 11, 16; CLI surface → 8, 16; `--emit-events` and the stdout redirect → 8; event protocol → 6, 7; parse-failure visibility → 6, 10; rate limiting → 4, 5, 17, 18; `GlobalReadsCache` → 2, 3; TUI store/focus/colours/collision/roster → 12, 13, 14, 15; lifecycle → 9, 10; the SQLite open item → 1; the 429-layer open item → 18 Step 3; testing → every task plus 19; formal surface → 20 Step 4.

**Placeholder scan.** No "TBD", no "add error handling", no "similar to Task N". Two places defer deliberately and say so explicitly: Task 8 leaves the `--all` branch for Task 16 (so Task 8 stays independently testable), and Task 18 Step 3 requires confirming which layer sees a 429 before attaching the handler — that is a stated investigation with a stated constraint (attach at one layer only, never both), not an unresolved requirement.

**Type consistency.** `WindowBudget`/`BucketBudgets` (Task 4) are consumed with the same field names in Tasks 5, 16, 17. `RestartDecision(restart, delay_seconds)` (Task 9) is read identically in Task 10. `ChildState` (Task 11) is constructed in `SupervisorPool.state` and consumed in `WatchApp.update_child_state` (Task 15) with matching fields. `CharacterRoster.sprite` (Task 12) returns the `Sprite` that `MapPane.set_others` (Task 14) expects and that `WatchApp._repaint_others` (Task 15) passes. `parse_child_event` (Task 6) is used in Task 10 only. `emit_reason_for` (Task 8) produces exactly the `crash:network` string `RESTARTABLE_REASONS` (Task 9) tests for.

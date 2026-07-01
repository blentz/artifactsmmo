# API-gap closure (raids + effects) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the bot raid visibility (`/raids` → `WorldState`, surfaced to log) and an eager effects coverage audit (`/effects` → startup warning report), closing the two planner-relevant unconsumed API gaps.

**Architecture:** Raids are *dynamic* state, so they mirror the existing active-events path — a per-sense `GamePlayer._fetch_raids` populates a new `WorldState.raids` list; `active_raids` is a filtered view surfaced to the log. Effects are *static*, so they mirror the game-data path — `GameData._fetch_effects`/`_build_effects` build a registry at load, and `_audit_effect_coverage` warns about codes defined-but-unseen / seen-but-undefined / stale carveouts. Neither part touches `predict_win`, the arbiter, or the planner.

**Tech Stack:** Python 3.13, `uv`, pytest, the generated `artifactsmmo_api_client` (`get_all_raids_raids_get.sync`, `get_all_effects_effects_get.sync`).

## Deviation from the spec (for reviewer)

The approved spec put a static raid *catalog* in `GameData` plus a dynamic split. This plan collapses that: `/raids` returns every raid with its live `status`/`active_instance` in one call, so a single per-sense fetch in `GamePlayer` (mirroring `_fetch_active_events`) captures the full baseline — no separate GameData catalog, no static/dynamic split. This is strictly simpler, matches the established active-events pattern, and still gives the future Discord comparison every raid (upcoming + active). Effects remain in `GameData` as the spec described.

## Global Constraints

Copied verbatim from project guidelines (CLAUDE.md). Every task's requirements implicitly include these:

- Prefix every Python command with `uv run` (e.g. `uv run pytest`, `uv run mypy`).
- Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- ONE behavioral class per file. Cohesive pure data/dataclass value objects may share a module.
- No inline imports — all imports at top of file. Absolute imports only. No `...` imports.
- Never use `if TYPE_CHECKING`. Never `catch Exception`. Use only API data or fail with an error.
- All tests in `tests/`. Use the existing suite; no throwaway "simple" tests.

---

# Part 1 — Raid visibility (player-side, mirrors active_events)

### Task 1: `RaidInfo` value object

**Files:**
- Create: `src/artifactsmmo_cli/ai/raid_info.py`
- Test: `tests/test_ai/test_raid_info.py`

**Interfaces:**
- Produces: `RaidInfo` — a frozen dataclass with fields `code: str`, `name: str`, `monster: str`, `status: str`, `next_start_at: datetime`, `remaining_hp: int | None`, `total_hp: int | None`, `window_ends_at: datetime | None`. Method `is_active(self) -> bool` returns `self.status == "active"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_raid_info.py
from datetime import datetime, timezone

from artifactsmmo_cli.ai.raid_info import RaidInfo


def _dt(h: int) -> datetime:
    return datetime(2026, 6, 30, h, 0, 0, tzinfo=timezone.utc)


def test_active_raid_reports_active_and_carries_instance_fields():
    r = RaidInfo(code="slime_raid", name="Slime Raid", monster="giant_slime",
                 status="active", next_start_at=_dt(12),
                 remaining_hp=400, total_hp=1000, window_ends_at=_dt(13))
    assert r.is_active() is True
    assert (r.remaining_hp, r.total_hp) == (400, 1000)
    assert r.window_ends_at == _dt(13)


def test_upcoming_raid_is_not_active_and_has_no_instance():
    r = RaidInfo(code="slime_raid", name="Slime Raid", monster="giant_slime",
                 status="upcoming", next_start_at=_dt(18),
                 remaining_hp=None, total_hp=None, window_ends_at=None)
    assert r.is_active() is False
    assert r.remaining_hp is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_raid_info.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.raid_info'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/artifactsmmo_cli/ai/raid_info.py
"""RaidInfo: one raid's live state captured from GET /raids (visibility only)."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RaidInfo:
    """A single raid with its current status. `remaining_hp` / `total_hp` /
    `window_ends_at` are populated only while the raid has an active instance."""

    code: str
    name: str
    monster: str
    status: str
    next_start_at: datetime
    remaining_hp: int | None
    total_hp: int | None
    window_ends_at: datetime | None

    def is_active(self) -> bool:
        """True when the raid is currently running (has an active instance)."""
        return self.status == "active"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_raid_info.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/raid_info.py tests/test_ai/test_raid_info.py
git commit -m "feat(raids): RaidInfo value object for raid visibility"
```

---

### Task 2: `WorldState.raids` field + `active_raids` view

**Files:**
- Modify: `src/artifactsmmo_cli/ai/world_state.py` (field near `active_events` line 106; `from_character_schema` params ~line 196 and body ~line 260)
- Test: `tests/test_ai/test_world_state_raids.py`

**Interfaces:**
- Consumes: `RaidInfo` (Task 1).
- Produces: `WorldState.raids: list[RaidInfo]` (default empty). `WorldState.active_raids` property → `[r for r in self.raids if r.is_active()]`. `from_character_schema(..., raids: list[RaidInfo] | None = None)` sets `raids=raids or []`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_world_state_raids.py
from datetime import datetime, timezone

from artifactsmmo_cli.ai.raid_info import RaidInfo
from tests.test_ai.fixtures import make_state


def _raid(status: str) -> RaidInfo:
    t = datetime(2026, 6, 30, 12, tzinfo=timezone.utc)
    return RaidInfo(code="r", name="R", monster="giant_slime", status=status,
                    next_start_at=t, remaining_hp=1 if status == "active" else None,
                    total_hp=2 if status == "active" else None,
                    window_ends_at=t if status == "active" else None)


def test_worldstate_defaults_to_no_raids():
    assert make_state().raids == []
    assert make_state().active_raids == []


def test_active_raids_filters_to_active_only():
    st = make_state(raids=[_raid("active"), _raid("upcoming")])
    assert [r.status for r in st.active_raids] == ["active"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_world_state_raids.py -v`
Expected: FAIL — `make_state()` / `WorldState` has no `raids` (TypeError or AttributeError).

- [ ] **Step 3: Write minimal implementation**

In `src/artifactsmmo_cli/ai/world_state.py`, add the import at the top of the file:

```python
from artifactsmmo_cli.ai.raid_info import RaidInfo
```

Add the field next to `active_events` (line 106):

```python
    raids: list[RaidInfo] = field(default_factory=list)
```

Add the property to the `WorldState` class body (near the other computed accessors):

```python
    @property
    def active_raids(self) -> list[RaidInfo]:
        """Raids currently running (visibility only — no planner consumer)."""
        return [r for r in self.raids if r.is_active()]
```

In `from_character_schema`, add the parameter (alongside `active_events`, ~line 196):

```python
        raids: list[RaidInfo] | None = None,
```

and set it in the constructed `WorldState` (alongside `active_events=active_events or {}`, ~line 260):

```python
            raids=raids or [],
```

Then update `tests/test_ai/fixtures.py::make_state` to pass through a `raids` override if it does not already forward `**overrides`. (Check first: if `make_state` builds via `**overrides` it already works — the two tests above will confirm.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_world_state_raids.py -v`
Expected: PASS

- [ ] **Step 5: Run the broader world_state + a smoke slice to catch signature breaks**

Run: `uv run pytest tests/test_ai/ -q --no-cov -k "world_state or first_cycle or player"`
Expected: PASS (no `from_character_schema` caller broke)

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/world_state.py tests/test_ai/test_world_state_raids.py tests/test_ai/fixtures.py
git commit -m "feat(raids): WorldState.raids field + active_raids view"
```

---

### Task 3: `GamePlayer._fetch_raids` + populate on sense

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (add `_fetch_raids` next to `_fetch_active_events` ~line 838; call it in the sense block ~line 922 and pass to `from_character_schema`)
- Test: `tests/test_ai/test_player_raids.py`

**Interfaces:**
- Consumes: `RaidInfo` (Task 1), `WorldState.from_character_schema(raids=...)` (Task 2).
- Produces: `GamePlayer._fetch_raids(self, client) -> list[RaidInfo]` — pages `GET /raids`, retries on `httpx.HTTPError` (same 3-attempt backoff as `_fetch_active_events`), maps each `RaidSchema` to a `RaidInfo` (extracting `active_instance.remaining_hp/total_hp/ends_at` when the instance is present — not `None`, not `Unset` — else `None`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_player_raids.py
from datetime import datetime, timezone
from unittest.mock import MagicMock

from artifactsmmo_cli.ai.player import GamePlayer


class _Status:
    def __init__(self, value): self.value = value


def _raid_schema(status, instance):
    r = MagicMock()
    r.code, r.name, r.monster = "slime_raid", "Slime Raid", "giant_slime"
    r.status = _Status(status)
    r.next_start_at = datetime(2026, 6, 30, 18, tzinfo=timezone.utc)
    r.active_instance = instance
    return r


def _instance():
    inst = MagicMock()
    inst.remaining_hp, inst.total_hp = 400, 1000
    inst.ends_at = datetime(2026, 6, 30, 13, tzinfo=timezone.utc)
    return inst


def test_fetch_raids_maps_active_and_upcoming(monkeypatch):
    page = MagicMock()
    page.data = [_raid_schema("active", _instance()),
                 _raid_schema("upcoming", None)]
    monkeypatch.setattr("artifactsmmo_cli.ai.player.get_all_raids",
                        lambda **kw: page if kw["page"] == 1 else MagicMock(data=[]))
    player = GamePlayer(character="hero")
    raids = player._fetch_raids(MagicMock())
    assert [r.status for r in raids] == ["active", "upcoming"]
    active = next(r for r in raids if r.status == "active")
    assert (active.remaining_hp, active.total_hp) == (400, 1000)
    upcoming = next(r for r in raids if r.status == "upcoming")
    assert upcoming.remaining_hp is None and upcoming.window_ends_at is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_player_raids.py -v`
Expected: FAIL — `GamePlayer` has no `_fetch_raids` (AttributeError), and `player.get_all_raids` import is missing.

- [ ] **Step 3: Write minimal implementation**

Add the import at the top of `src/artifactsmmo_cli/ai/player.py` (next to the `get_all_active_events` import, line 15):

```python
from artifactsmmo_api_client.api.raids.get_all_raids_raids_get import sync as get_all_raids
```

Add the import for `RaidInfo` and `Unset` at the top:

```python
from artifactsmmo_cli.ai.raid_info import RaidInfo
from artifactsmmo_api_client.types import Unset
```

Add the method next to `_fetch_active_events` (~line 838):

```python
    def _fetch_raids(self, client: AuthenticatedClient) -> list[RaidInfo]:
        """All raids with live status, mapped to RaidInfo. Retries on transient
        transport errors like _fetch_active_events; a request that keeps failing
        yields the raids collected so far (raids are non-critical visibility)."""
        out: list[RaidInfo] = []
        page = 1
        while True:
            result = None
            backoff = 5.0
            for attempt in range(1, 4):
                try:
                    result = get_all_raids(client=client, page=page, size=100)
                    break
                except httpx.HTTPError as e:
                    if attempt < 3:
                        print(f"[{self._now()}] get_all_raids network error: {e!r}; "
                              f"retry {attempt}/3 in {backoff:.0f}s")
                        time.sleep(backoff)
                        backoff *= 2
            if result is None or not result.data:
                break
            for raid in result.data:
                inst = raid.active_instance
                # active_instance is RaidInstanceSchema | None | Unset — "present"
                # means a real instance (not None, not the Unset sentinel).
                has_inst = inst is not None and not isinstance(inst, Unset)
                out.append(RaidInfo(
                    code=raid.code, name=raid.name, monster=raid.monster,
                    status=raid.status.value, next_start_at=raid.next_start_at,
                    remaining_hp=inst.remaining_hp if has_inst else None,
                    total_hp=inst.total_hp if has_inst else None,
                    window_ends_at=inst.ends_at if has_inst else None))
            if len(result.data) < 100:
                break
            page += 1
        return out
```

In the sense block (`_fetch_world_state`, after `active_events = self._fetch_active_events(client)` ~line 922), add:

```python
        raids = self._fetch_raids(client)
```

and pass it into `WorldState.from_character_schema(...)` (add `raids=raids,` beside `active_events=active_events,`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_player_raids.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player_raids.py
git commit -m "feat(raids): fetch /raids per sense into WorldState.raids"
```

---

### Task 4: Surface active raids to the log

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (emit a log line when active raids exist, in the sense block after `raids` is fetched)
- Test: `tests/test_ai/test_player_raids.py` (extend)

**Interfaces:**
- Consumes: `WorldState.active_raids` (Task 2), `_fetch_raids` (Task 3).
- Produces: `GamePlayer._log_active_raids(self, raids: list[RaidInfo]) -> None` — prints one line per active raid: `raid active: {monster} {remaining_hp}/{total_hp} hp, ends {window_ends_at}`. Silent when none active.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_ai/test_player_raids.py
from artifactsmmo_cli.ai.raid_info import RaidInfo
from datetime import datetime, timezone


def _ri(status):
    t = datetime(2026, 6, 30, 13, tzinfo=timezone.utc)
    return RaidInfo(code="r", name="R", monster="giant_slime", status=status,
                    next_start_at=t, remaining_hp=400 if status == "active" else None,
                    total_hp=1000 if status == "active" else None,
                    window_ends_at=t if status == "active" else None)


def test_log_active_raids_prints_only_active(capsys):
    player = GamePlayer(character="hero")
    player._log_active_raids([_ri("active"), _ri("upcoming")])
    out = capsys.readouterr().out
    assert "raid active: giant_slime 400/1000 hp" in out
    assert out.count("raid active:") == 1


def test_log_active_raids_silent_when_none(capsys):
    GamePlayer(character="hero")._log_active_raids([_ri("upcoming")])
    assert capsys.readouterr().out == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_player_raids.py -k log_active_raids -v`
Expected: FAIL — `GamePlayer` has no `_log_active_raids`.

- [ ] **Step 3: Write minimal implementation**

Add to `src/artifactsmmo_cli/ai/player.py` (near `_fetch_raids`):

```python
    def _log_active_raids(self, raids: list[RaidInfo]) -> None:
        """Print one line per currently-active raid (visibility only)."""
        for raid in raids:
            if raid.is_active():
                print(f"[{self._now()}] raid active: {raid.monster} "
                      f"{raid.remaining_hp}/{raid.total_hp} hp, "
                      f"ends {raid.window_ends_at}")
```

Call it in the sense block right after `raids = self._fetch_raids(client)`:

```python
        self._log_active_raids(raids)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_player_raids.py -v`
Expected: PASS (all raid tests)

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player_raids.py
git commit -m "feat(raids): log active raids each sense"
```

> **Optional follow-up (not in this plan's committed scope):** a TUI status-pane indicator. `WorldState.active_raids` already exposes the data; wiring a line into `src/artifactsmmo_cli/tui/widgets/status_pane.py` is polish that needs that widget's render API. Left out to keep this plan's tasks fully testable without the Textual harness. Add as a separate task if desired.

---

# Part 2 — Effects coverage audit (GameData, static)

### Task 5: `GameData._fetch_effects` + `_build_effects` registry

**Files:**
- Modify: `src/artifactsmmo_cli/ai/game_data.py` (add `_fetch_effects`, `_build_effects`, `self._effect_registry`; wire into `load` — the `fetched` dict ~line 1105, the cached-reload branch ~line 1132, and the `_build_*` call sequence ~line 1141)
- Test: `tests/test_ai/test_game_data_effects.py`

**Interfaces:**
- Produces: `GameData._effect_registry: dict[str, str]` (effect code → name). `GameData._fetch_effects(self, client) -> list[EffectSchema]` (paged like `_fetch_events`). `GameData._build_effects(self, effects: list[EffectSchema]) -> None` fills `_effect_registry`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_game_data_effects.py
from unittest.mock import MagicMock

from artifactsmmo_cli.ai.game_data import GameData


def _effect(code, name):
    e = MagicMock()
    e.code, e.name = code, name
    return e


def test_build_effects_indexes_registry_by_code():
    gd = GameData()
    gd._build_effects([_effect("poison", "Poison"), _effect("lifesteal", "Lifesteal")])
    assert gd._effect_registry == {"poison": "Poison", "lifesteal": "Lifesteal"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_game_data_effects.py -v`
Expected: FAIL — `GameData` has no `_build_effects` / `_effect_registry`.

- [ ] **Step 3: Write minimal implementation**

Add the import at the top of `src/artifactsmmo_cli/ai/game_data.py`:

```python
from artifactsmmo_api_client.api.effects.get_all_effects_effects_get import sync as get_all_effects
from artifactsmmo_api_client.models.effect_schema import EffectSchema
```

Add the field initializer alongside the other `field(default_factory=dict, init=False, repr=False)` attributes (e.g. near line 133):

```python
    _effect_registry: dict[str, str] = field(default_factory=dict, init=False, repr=False)
```

Add the fetch + build methods (next to `_fetch_events` / `_build_events`):

```python
    def _fetch_effects(self, client: AuthenticatedClient) -> list[EffectSchema]:
        """Page all effect definitions; return the schema list."""
        out: list[EffectSchema] = []
        page = 1
        while True:
            result = get_all_effects(client=client, page=page, size=100)
            if result is None or not result.data:
                break
            out.extend(result.data)
            if len(result.data) < 100:
                break
            page += 1
        return out

    def _build_effects(self, effects: list[EffectSchema]) -> None:
        """Index the authoritative effect registry (code -> name)."""
        for eff in effects:
            self._effect_registry[eff.code] = eff.name
```

Wire into `GameData.load`:
- In the `fetched` dict (~line 1105) add: `"effects": data._fetch_effects(client),`
- In the cached-reload `objs` branch (~line 1132) add: `"effects": [EffectSchema.from_dict(d) for d in raw["effects"]],`
- In the `_build_*` call sequence (~line 1141, after `_build_monsters`) add: `data._build_effects(objs["effects"])`

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_game_data_effects.py -v`
Expected: PASS

- [ ] **Step 5: Guard the cache round-trip**

Run: `uv run pytest tests/test_ai/ -q --no-cov -k "game_data and (load or cache)"`
Expected: PASS (the new `"effects"` key survives the cache write/reload branch; if a cache-shape test asserts an exact key set, update it to include `"effects"`).

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/game_data.py tests/test_ai/test_game_data_effects.py
git commit -m "feat(effects): consume /effects into GameData registry"
```

---

### Task 6: `_seen_effect_codes` + `_audit_effect_coverage`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/game_data.py` (record `self._seen_effect_codes` at the effect loops in `_build_monsters` ~line 1655 and `_build_items` ~line 1359; add `_audit_effect_coverage`; call it in `load` after the `_build_*` sequence)
- Test: `tests/test_ai/test_effect_coverage_audit.py`

**Interfaces:**
- Consumes: `_effect_registry` (Task 5), `_MONSTER_EFFECT_CARVEOUTS` / `_ITEM_EFFECT_CARVEOUTS` / `_RUNE_ABILITY_CARVEOUTS` (module-level, game_data.py).
- Produces: `GameData._seen_effect_codes: set[str]`. `GameData._audit_effect_coverage(self) -> None` prints warn lines (never raises) for `registry − seen` (latent), `seen − registry` (anomaly), and `carveouts − registry` (stale).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_effect_coverage_audit.py
from artifactsmmo_cli.ai.game_data import GameData


def _gd(registry, seen):
    gd = GameData()
    gd._effect_registry = registry
    gd._seen_effect_codes = set(seen)
    return gd


def test_latent_code_defined_but_unseen_warns(capsys):
    _gd({"poison": "Poison", "newfx": "New"}, {"poison"})._audit_effect_coverage()
    out = capsys.readouterr().out
    assert "newfx" in out and "defined but on no current entity" in out


def test_seen_code_missing_from_registry_warns(capsys):
    _gd({"poison": "Poison"}, {"poison", "ghost"})._audit_effect_coverage()
    assert "ghost" in capsys.readouterr().out


def test_fully_covered_registry_is_silent(capsys):
    _gd({"poison": "Poison"}, {"poison"})._audit_effect_coverage()
    assert capsys.readouterr().out == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_effect_coverage_audit.py -v`
Expected: FAIL — `GameData` has no `_audit_effect_coverage` / `_seen_effect_codes`.

- [ ] **Step 3: Write minimal implementation**

Add the field initializer near `_effect_registry`:

```python
    _seen_effect_codes: set[str] = field(default_factory=set, init=False, repr=False)
```

Record every encountered code. In `_build_monsters`, at the top of the per-effect loop (before the `elif` chain around line 1655), add:

```python
                    self._seen_effect_codes.add(code)
```

In `_build_items`, at the top of the per-effect loop (before the `elif` chain around line 1359), add:

```python
                    self._seen_effect_codes.add(effect.code)
```

(Use whatever local the surrounding loop already binds — `code` in `_build_monsters`, `effect.code` in `_build_items`.)

Add the audit method:

```python
    def _audit_effect_coverage(self) -> None:
        """Warn (never raise) about effect-registry coverage: codes defined but on
        no current entity (model them before something carries one), codes in use
        the registry does not define, and carveouts that no longer exist. The lazy
        GameDataCoverageError stays the hard gate when a new code is actually
        carried by a monster/item."""
        registry = set(self._effect_registry)
        latent = sorted(registry - self._seen_effect_codes)
        if latent:
            print(f"[game_data] effect codes defined but on no current entity: {latent}")
        anomaly = sorted(self._seen_effect_codes - registry)
        if anomaly:
            print(f"[game_data] effect codes in use but not in /effects registry: {anomaly}")
        carveouts = _MONSTER_EFFECT_CARVEOUTS | _ITEM_EFFECT_CARVEOUTS | _RUNE_ABILITY_CARVEOUTS
        stale = sorted(carveouts - registry)
        if stale:
            print(f"[game_data] stale effect carveouts (not in /effects registry): {stale}")
```

Call it in `GameData.load` after the `_build_*` sequence (after `data._build_effects(objs["effects"])` and the monster/item builds have populated `_seen_effect_codes`):

```python
        data._audit_effect_coverage()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_effect_coverage_audit.py -v`
Expected: PASS (all three)

- [ ] **Step 5: Full guard — no regression in game-data load**

Run: `uv run pytest tests/test_ai/ -q --no-cov -k "game_data or effect or monster or item"`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/game_data.py tests/test_ai/test_effect_coverage_audit.py
git commit -m "feat(effects): eager startup coverage audit (warn, lazy guard stays)"
```

---

## Final verification (after all tasks)

- [ ] **Full suite + coverage:** `uv run pytest tests/test_ai/ -q` — Expected: all pass, 100% on the changed files.
- [ ] **Types:** `uv run mypy src/artifactsmmo_cli/ai/raid_info.py src/artifactsmmo_cli/ai/world_state.py src/artifactsmmo_cli/ai/player.py src/artifactsmmo_cli/ai/game_data.py` — Expected: `Success`.
- [ ] **Lint:** `uv run ruff check src/artifactsmmo_cli/ai/raid_info.py src/artifactsmmo_cli/ai/world_state.py src/artifactsmmo_cli/ai/player.py src/artifactsmmo_cli/ai/game_data.py` — Expected: clean (or only pre-existing findings).
- [ ] No formal gate needed — no task touches `predict_win`, the arbiter, or any `formal/`-anchored core.

## Self-review notes (author)

- **Spec coverage:** raid ingest → Tasks 1-3; raid surfacing → Task 4 (TUI indicator explicitly deferred with rationale); `/effects` registry → Task 5; eager audit + carveout hygiene + warn-not-fail + lazy-guard-unchanged → Task 6. Effects `seen − registry` and `registry − seen` and stale-carveout cases all tested.
- **Deviation:** raids fetched per-sense in `GamePlayer` (not a GameData static catalog) — documented above; flag for reviewer.
- **Type consistency:** `RaidInfo` fields identical across Tasks 1-4; `_effect_registry: dict[str,str]` and `_seen_effect_codes: set[str]` consistent across Tasks 5-6.

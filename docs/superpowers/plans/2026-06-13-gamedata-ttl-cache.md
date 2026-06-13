# GameData TTL Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cache GameData's static API data to disk with a configurable TTL (default 30 min) so the bot stops re-fetching all static game data on every startup; GE orders stay live.

**Architecture:** A new `GameDataCache` owns disk persistence + freshness + versioning of the raw API page payloads (atomic temp+replace, injected clock). `GameData.load` splits each static loader into `_fetch_*(client) -> list[dict]` (paginate, collect `schema.to_dict()`) and `_build_*(pages)` (existing index logic over `Schema.from_dict(d)`); a warm load rebuilds indexes from cached raw pages with current code, a cold load fetches + writes the cache. GE orders are always fetched live.

**Tech Stack:** Python 3.13 (`uv run`), Typer CLI, Pydantic config, the generated `artifactsmmo_api_client` (schemas expose `to_dict()`/`from_dict()`). No Lean / formal gate (the only logic is a TTL comparison).

---

## Background the engineer needs

- Run every Python command with `uv run` (binary at `/home/blentz/.local/bin/uv`; use the full path if `uv` is not on PATH).
- Project rules: imports at top of file only; **never catch bare `Exception`** (catch specific types); no `if TYPE_CHECKING`; ONE behavioral class per file (pure-data dataclasses may share a module); success = 0 failures / 0 warnings / 0 skipped / **100% coverage** (`uv run pytest -q`).
- Commit with `--no-verify` (the pre-commit hook runs slow mypy). Stage ONLY the files each task names (`git add <files>`, never `git add -A` — the tree may carry unrelated changes).
- `GameData` lives in `src/artifactsmmo_cli/ai/game_data.py`. Its 8 loaders today fetch+build inline in a `while True` pagination loop. The 7 STATIC loaders and their element schemas:
  | loader | API fn (already imported) | element schema | paginated? |
  |---|---|---|---|
  | `_load_maps` | `get_all_maps(client, layer=MapLayer.OVERWORLD, page, size=100)` | `MapSchema` | yes |
  | `_load_items` | `get_all_items(client, page, size=100)` | `ItemSchema` | yes |
  | `_load_resources` | `get_all_resources(client, page, size=100)` | `ResourceSchema` | yes |
  | `_load_monsters` | `get_all_monsters(client, page, size=100)` | `MonsterSchema` | yes |
  | `_load_npcs` | `get_all_npc_items(client, page, size=100)` | `NPCItem` | yes |
  | `_load_events` | `get_all_events(client, page, size=100)` | `EventSchema` | yes |
  | `_load_bank_metadata` | `get_bank_details(client)` | `BankSchema` (`.data`, single) | no |
  `_load_ge_orders` is the LIVE market order book — **do not touch it**.
- Each `result.data` element has `.to_dict() -> dict` and its class has `ClassName.from_dict(d) -> instance` (classmethod). Element schema imports live in `artifactsmmo_api_client.models.<snake>` (e.g. `from artifactsmmo_api_client.models.map_schema import MapSchema`).
- `AuthenticatedClient` exposes the base URL as `client._base_url` (field aliased `base_url`).
- GameData load call sites: `src/artifactsmmo_cli/ai/player.py:217` (`self.game_data = GameData.load(client)`, in `run()`) and `src/artifactsmmo_cli/commands/play.py:122` (`player.game_data = GameData.load(client)`, TUI preload). With the cache, the TUI's double-load becomes a cold fetch then a warm cache hit (no double API fetch).

## File structure

- Create `src/artifactsmmo_cli/ai/game_data_cache.py` — `GameDataCache` (disk I/O, TTL, version, atomic write).
- Create `tests/test_ai/test_game_data_cache.py`.
- Modify `src/artifactsmmo_cli/ai/game_data.py` — fetch/build split + cache-aware `load`.
- Modify `tests/test_ai/test_game_data.py` — warm/cold equality, GE-always-live, force_refresh (create the file if it does not exist).
- Modify `src/artifactsmmo_cli/config.py` — `game_data_ttl_minutes` field.
- Modify `src/artifactsmmo_cli/commands/play.py` — `--refresh-game-data` flag + thread params.
- Modify `src/artifactsmmo_cli/ai/player.py` — thread ttl/force_refresh into its `GameData.load`.

---

## Task 1: `GameDataCache`

**Files:**
- Create: `src/artifactsmmo_cli/ai/game_data_cache.py`
- Test: `tests/test_ai/test_game_data_cache.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ai/test_game_data_cache.py
import json
from datetime import datetime, timedelta, timezone

from artifactsmmo_cli.ai.game_data_cache import CACHE_VERSION, GameDataCache

_T0 = datetime(2026, 6, 13, 8, 0, 0, tzinfo=timezone.utc)
_PAGES = {"maps": [{"x": 1, "y": 2}], "items": [{"code": "ash"}], "bank": {"slots": 30}}


def _cache(tmp_path):
    return GameDataCache(api_base_url="https://api.artifactsmmo.com", cache_dir=tmp_path)


def test_write_then_read_roundtrip(tmp_path):
    c = _cache(tmp_path)
    c.write(_PAGES, now=_T0)
    got = c.read(ttl_minutes=30, now=_T0 + timedelta(minutes=29))
    assert got == _PAGES


def test_read_expired_returns_none(tmp_path):
    c = _cache(tmp_path)
    c.write(_PAGES, now=_T0)
    assert c.read(ttl_minutes=30, now=_T0 + timedelta(minutes=31)) is None


def test_read_at_ttl_boundary_is_expired(tmp_path):
    c = _cache(tmp_path)
    c.write(_PAGES, now=_T0)
    # exactly ttl elapsed -> NOT fresh (strict <)
    assert c.read(ttl_minutes=30, now=_T0 + timedelta(minutes=30)) is None


def test_read_missing_file_returns_none(tmp_path):
    assert _cache(tmp_path).read(ttl_minutes=30, now=_T0) is None


def test_read_version_mismatch_returns_none(tmp_path):
    c = _cache(tmp_path)
    c.write(_PAGES, now=_T0)
    raw = json.loads(c.path.read_text())
    raw["version"] = CACHE_VERSION + 1
    c.path.write_text(json.dumps(raw))
    assert c.read(ttl_minutes=30, now=_T0 + timedelta(minutes=1)) is None


def test_read_corrupt_json_returns_none(tmp_path):
    c = _cache(tmp_path)
    c.path.parent.mkdir(parents=True, exist_ok=True)
    c.path.write_text("{not json")
    assert c.read(ttl_minutes=30, now=_T0) is None


def test_write_is_atomic_no_tmp_left(tmp_path):
    c = _cache(tmp_path)
    c.write(_PAGES, now=_T0)
    assert c.path.exists()
    assert not c.path.with_suffix(c.path.suffix + ".tmp").exists()


def test_path_keyed_by_host(tmp_path):
    a = GameDataCache("https://api.artifactsmmo.com", cache_dir=tmp_path).path
    b = GameDataCache("https://sandbox.artifactsmmo.com", cache_dir=tmp_path).path
    assert a != b
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ai/test_game_data_cache.py -q`
Expected: FAIL — `ModuleNotFoundError: ...game_data_cache`.

- [ ] **Step 3: Implement `GameDataCache`**

```python
# src/artifactsmmo_cli/ai/game_data_cache.py
"""Disk cache for GameData's static API pages: configurable-TTL, versioned,
atomic. Holds NO game logic — only persistence + freshness."""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

CACHE_VERSION = 1
"""Bump when the raw-page schema changes; an old version reads as a miss."""


class GameDataCache:
    """Read/write the raw static API pages under ~/.cache/artifactsmmo, keyed by
    API host (static data is server-wide). All-or-nothing: a missing, corrupt,
    stale, or version-mismatched cache reads as None so the caller re-fetches."""

    def __init__(self, api_base_url: str, cache_dir: Path | None = None) -> None:
        host = urlparse(api_base_url).netloc or "default"
        base = cache_dir if cache_dir is not None else Path.home() / ".cache" / "artifactsmmo"
        self.path = base / f"gamedata-{host}.json"

    def read(self, ttl_minutes: int, now: datetime | None = None) -> dict | None:
        now = now or datetime.now(tz=timezone.utc)
        try:
            raw = json.loads(self.path.read_text())
            if raw.get("version") != CACHE_VERSION:
                return None
            fetched_at = datetime.fromisoformat(raw["fetched_at"])
            if now - fetched_at >= timedelta(minutes=ttl_minutes):
                return None
            return {k: v for k, v in raw.items() if k not in ("version", "fetched_at")}
        except (OSError, json.JSONDecodeError, KeyError, ValueError):
            return None

    def write(self, raw_pages: dict, now: datetime | None = None) -> None:
        now = now or datetime.now(tz=timezone.utc)
        payload = {"version": CACHE_VERSION, "fetched_at": now.isoformat(), **raw_pages}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload))
        os.replace(tmp, self.path)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_game_data_cache.py -q`
Expected: PASS (8 tests). (Global coverage gate may fire on a partial run — fine.)

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/game_data_cache.py tests/test_ai/test_game_data_cache.py
git commit --no-verify -m "feat(ai): GameDataCache — configurable-TTL atomic disk cache"
```

---

## Task 2: GameData fetch/build split (7 static loaders)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/game_data.py`
- Test: `tests/test_ai/test_game_data.py`

Goal: split each static loader so index-building is separable from the API fetch, WITHOUT changing any index logic AND without breaking the ~40 existing tests that call `gd._load_maps(MagicMock())` with patched API functions and MagicMock elements.

KEY DESIGN (preserves existing tests): `_build_*` consumes **schema OBJECTS** (not dicts) — its body is the existing per-item logic, unchanged, so MagicMock elements still work. `_fetch_*` returns the list of schema objects. The dict serialization (`to_dict`/`from_dict`) for the cache happens in `load` (Task 3), on real schemas only. Keep `_load_*` as a thin wrapper so every existing test stays green.

Per static loader, the mechanical transform (no index logic changes):
- `_fetch_<name>(self, client) -> list[<Schema>]`: copy the EXISTING pagination `while True` loop, but instead of building indexes, `out.extend(result.data)`; return `out`. (Bank: `_fetch_bank(self, client) -> <BankSchema> | None`: `result = get_bank_details(client=client); return result.data if result is not None and result.data is not None else None`.)
- `_build_<name>(self, items: list[<Schema>]) -> None`: the EXISTING per-item loop body, UNCHANGED, iterating `for item in items:` instead of `for item in result.data`. (Bank: `_build_bank(self, item) -> None`: if `item is None` return, else set `self._bank_capacity` / `self._next_expansion_cost` from the same attributes the current `_load_bank_metadata` reads off `result.data`.)
- `_load_<name>(self, client) -> None`: REPLACE the old body with `self._build_<name>(self._fetch_<name>(client))`. Keep this wrapper — the existing `_load_*` tests call it.

(No new element-schema imports needed in `game_data.py` — `_build_*` operates on whatever objects `_fetch_*` returns; the `from_dict` reconstruction lives in `load`/Task 3.)

WORKED TEMPLATE — `_load_maps` (lines ~645-700) becomes:
```python
def _fetch_maps(self, client: AuthenticatedClient) -> list:
    out: list = []
    page = 1
    while True:
        result = get_all_maps(client=client, layer=MapLayer.OVERWORLD, page=page, size=100)
        if result is None or not result.data:
            break
        out.extend(result.data)
        if len(result.data) < 100:
            break
        page += 1
    return out

def _build_maps(self, tiles: list) -> None:
    for tile in tiles:
        # <<< the EXISTING per-tile body of _load_maps, verbatim and unchanged:
        loc = (tile.x, tile.y)
        self._known_tiles.add(loc)
        # ... (transition / content / monster / resource / bank / taskmaster /
        #      grand_exchange / npc / workshop indexing — copy exactly) ...

def _load_maps(self, client: AuthenticatedClient) -> None:
    self._build_maps(self._fetch_maps(client))
```

Apply the identical transform to `_load_items`, `_load_resources`, `_load_monsters`, `_load_npcs`, `_load_events`, `_load_bank_metadata`. The `_build_*` body is the existing per-item body relocated unchanged — do NOT alter any indexing logic. Keep `_load_ge_orders` exactly as-is.

> Note: `_build_*` bodies are existing code relocated verbatim; reproducing all 7 here risks transcription drift from the source of truth. Read each current `_load_*`, move its per-item body into `_build_*`, and make `_load_*` the one-line wrapper. The existing `_load_*` tests (≈40) are the immediate safety net — they must stay green with zero edits — and Task 3's warm/cold equality test proves the cache round-trip preserves behavior.

`tests/test_ai/test_game_data.py` ALREADY EXISTS (≈1192 lines) with `make_page`, `make_map_tile` (MagicMock-based) and `with patch("...game_data.get_all_maps", ...): gd._load_maps(MagicMock())` tests. Those must keep passing unchanged.

- [ ] **Step 1: Write the failing fetch test** (uses the file's existing `make_page`/`make_map_tile` helpers)

```python
# add to tests/test_ai/test_game_data.py
class TestGameDataFetchBuildSplit:
    def test_fetch_maps_returns_element_objects(self):
        gd = GameData()
        tile = make_map_tile(1, 0, "monster", "chicken")
        with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=make_page([tile])):
            out = gd._fetch_maps(MagicMock())
        assert out == [tile]   # _fetch_* returns the schema objects, un-built

    def test_load_maps_is_fetch_then_build(self):
        # the existing wrapper still indexes correctly (build over fetched objects)
        gd = GameData()
        tile = make_map_tile(2, 3, "resource", "copper")
        with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=make_page([tile])):
            gd._load_maps(MagicMock())
        assert gd._resource_locations == {"copper": [(2, 3)]}
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ai/test_game_data.py::TestGameDataFetchBuildSplit -q`
Expected: FAIL — `AttributeError: 'GameData' object has no attribute '_fetch_maps'`.

- [ ] **Step 3: Implement the split** (the worked template + the 6 analogous transforms above; keep each `_load_*` as the one-line wrapper).

- [ ] **Step 4: Run to verify pass — including ALL pre-existing GameData tests**

Run: `uv run pytest tests/test_ai/test_game_data.py -q`
Expected: PASS — the new split tests AND every pre-existing `_load_*` test (the ≈40 MagicMock-based ones) stay green with zero edits. If any pre-existing test broke, a `_build_*` body diverged from its old `_load_*` — fix the relocation, do not edit the test.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/game_data.py tests/test_ai/test_game_data.py
git commit --no-verify -m "refactor(ai): split GameData static loaders into _fetch_*/_build_*"
```

---

## Task 3: Cache-aware `GameData.load`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/game_data.py`
- Test: `tests/test_ai/test_game_data.py`

- [ ] **Step 1: Write the failing control-flow tests** (stub `_fetch_*`/`_build_*` as recorders + a fake cache — no real schemas needed, since empty fetch lists make the to_dict/from_dict loops no-ops)

```python
# add to tests/test_ai/test_game_data.py
from artifactsmmo_cli.ai.game_data_cache import GameDataCache

_STATIC = ("maps", "items", "resources", "monsters", "npcs", "events")


class _RecordingCache(GameDataCache):
    def __init__(self, tmp_path, seeded=None):
        super().__init__("https://api.artifactsmmo.com", cache_dir=tmp_path)
        self.reads = 0
        self.writes = 0
        self._seeded = seeded
    def read(self, ttl_minutes, now=None):
        self.reads += 1
        return self._seeded
    def write(self, raw_pages, now=None):
        self.writes += 1
        self._seeded = raw_pages


def _stub_fetch_build(monkeypatch):
    """Stub every _fetch_* to return empty (so serialize/deserialize loops are
    no-ops) and _build_*/_load_ge_orders to recorders. Returns the GE counter."""
    for name in _STATIC:
        monkeypatch.setattr(GameData, f"_fetch_{name}", lambda self, client: [])
        monkeypatch.setattr(GameData, f"_build_{name}", lambda self, items: None)
    monkeypatch.setattr(GameData, "_fetch_bank", lambda self, client: None)
    monkeypatch.setattr(GameData, "_build_bank", lambda self, item: None)
    ge = {"n": 0}
    monkeypatch.setattr(GameData, "_load_ge_orders",
                        lambda self, client: ge.__setitem__("n", ge["n"] + 1))
    return ge


def test_cold_load_fetches_and_writes(monkeypatch, tmp_path):
    ge = _stub_fetch_build(monkeypatch)
    cache = _RecordingCache(tmp_path, seeded=None)  # miss
    GameData.load(client=MagicMock(), ttl_minutes=30, cache=cache)
    assert cache.reads == 1 and cache.writes == 1
    assert ge["n"] == 1  # GE always live


def test_warm_load_skips_fetch_uses_cache(monkeypatch, tmp_path):
    ge = _stub_fetch_build(monkeypatch)
    seeded = {k: [] for k in _STATIC} | {"bank": None}
    cache = _RecordingCache(tmp_path, seeded=seeded)  # hit
    monkeypatch.setattr(GameData, "_fetch_maps",
                        lambda self, client: (_ for _ in ()).throw(AssertionError("fetched on warm hit")))
    GameData.load(client=MagicMock(), ttl_minutes=30, cache=cache)
    assert cache.reads == 1 and cache.writes == 0
    assert ge["n"] == 1  # GE STILL fetched live on a warm hit


def test_force_refresh_bypasses_read(monkeypatch, tmp_path):
    _stub_fetch_build(monkeypatch)
    cache = _RecordingCache(tmp_path, seeded={k: [] for k in _STATIC} | {"bank": None})
    GameData.load(client=MagicMock(), ttl_minutes=30, force_refresh=True, cache=cache)
    assert cache.reads == 0 and cache.writes == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ai/test_game_data.py -q -k "cold_load or warm_load or force_refresh"`
Expected: FAIL — `load()` has no `ttl_minutes`/`cache`/`force_refresh` params.

- [ ] **Step 3: Rewrite `load`**

Add element-schema imports at the top of `game_data.py` (for the warm-path `from_dict` reconstruction — confirm exact module paths against the model files):
```python
from artifactsmmo_api_client.models.map_schema import MapSchema
from artifactsmmo_api_client.models.item_schema import ItemSchema
from artifactsmmo_api_client.models.resource_schema import ResourceSchema
from artifactsmmo_api_client.models.monster_schema import MonsterSchema
from artifactsmmo_api_client.models.npc_item import NPCItem
from artifactsmmo_api_client.models.event_schema import EventSchema
from artifactsmmo_api_client.models.bank_schema import BankSchema
from artifactsmmo_cli.ai.game_data_cache import GameDataCache
```
Replace the `load` classmethod body:
```python
@classmethod
def load(cls, client: AuthenticatedClient, ttl_minutes: int = 30,
         force_refresh: bool = False, cache: "GameDataCache | None" = None) -> "GameData":
    """Build GameData. Reuse the disk cache for the STATIC loaders when fresh
    (< ttl_minutes); else fetch from the API and rewrite it. GE orders are
    ALWAYS fetched live (the market order book changes constantly).

    _fetch_* return schema OBJECTS; the cache stores their .to_dict()s; a warm
    load reconstructs schemas via .from_dict(). _build_* always sees schema
    objects, so its logic (and the legacy _load_* tests) are unchanged."""
    data = cls()
    if cache is None:
        cache = GameDataCache(api_base_url=client._base_url)
    raw = None if force_refresh else cache.read(ttl_minutes)
    if raw is None:
        fetched = {
            "maps": data._fetch_maps(client), "items": data._fetch_items(client),
            "resources": data._fetch_resources(client), "monsters": data._fetch_monsters(client),
            "npcs": data._fetch_npcs(client), "events": data._fetch_events(client),
            "bank": data._fetch_bank(client),
        }
        raw = {k: ([o.to_dict() for o in v] if isinstance(v, list)
                   else (v.to_dict() if v is not None else None))
               for k, v in fetched.items()}
        try:
            cache.write(raw)
        except OSError as e:
            # Data is already in hand; a failed cache write must not crash the
            # run — the next start simply re-fetches.
            print(f"[game_data] cache write failed: {e}")
        objs = fetched
    else:
        objs = {
            "maps": [MapSchema.from_dict(d) for d in raw["maps"]],
            "items": [ItemSchema.from_dict(d) for d in raw["items"]],
            "resources": [ResourceSchema.from_dict(d) for d in raw["resources"]],
            "monsters": [MonsterSchema.from_dict(d) for d in raw["monsters"]],
            "npcs": [NPCItem.from_dict(d) for d in raw["npcs"]],
            "events": [EventSchema.from_dict(d) for d in raw["events"]],
            "bank": BankSchema.from_dict(raw["bank"]) if raw["bank"] is not None else None,
        }
    data._build_maps(objs["maps"]); data._build_items(objs["items"])
    data._build_resources(objs["resources"]); data._build_monsters(objs["monsters"])
    data._build_npcs(objs["npcs"]); data._build_events(objs["events"])
    data._build_bank(objs["bank"])
    data._load_ge_orders(client)
    return data
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_game_data.py -q`
Expected: PASS (split + load control-flow tests + all legacy `_load_*` tests).

- [ ] **Step 5: Add the real-schema warm/cold round-trip equality test** (proves to_dict/from_dict preserves build behavior — use a REAL schema the file already constructs)

```python
# add to tests/test_ai/test_game_data.py — uses real EventSchema (already imported
# + built by the existing event tests in this file; mirror their construction).
def test_warm_and_cold_events_build_equal(monkeypatch, tmp_path):
    """A real EventSchema fetched cold (built from the object) and warm
    (built from from_dict(to_dict(...))) must index identically."""
    ev = _make_event_npc(code="gold_merchant", npc_code="merchant", x=5, y=6)  # real EventSchema
    monkeypatch.setattr(GameData, "_fetch_events", lambda self, client: [ev])
    for name in ("maps", "items", "resources", "monsters", "npcs"):
        monkeypatch.setattr(GameData, f"_fetch_{name}", lambda self, client: [])
    monkeypatch.setattr(GameData, "_fetch_bank", lambda self, client: None)
    monkeypatch.setattr(GameData, "_load_ge_orders", lambda self, client: None)
    cache = _RecordingCache(tmp_path, seeded=None)
    cold = GameData.load(client=MagicMock(), ttl_minutes=30, cache=cache)  # writes cache
    warm = GameData.load(client=MagicMock(), ttl_minutes=30, cache=cache)  # from_dict path
    assert cold._npc_event_code == warm._npc_event_code
    assert cold._event_npc_spawns == warm._event_npc_spawns
    assert warm._event_npc_spawns  # non-empty -> the round-trip really happened
```
(`_make_event_npc` builds a real `EventSchema` with `content` = `EventContentSchema(type_=MapContentType.NPC, code=...)` and `maps=[EventMapSchema(x=.., y=..)]` — copy the construction the file's existing `_load_events` tests already use. If a different loader's schema is simpler to build for a real round-trip, use that one instead; the point is one real to_dict→from_dict→build equality.)

Run: `uv run pytest tests/test_ai/test_game_data.py::test_warm_and_cold_events_build_equal -q`
Expected: PASS. If it fails, the schema doesn't round-trip cleanly through to_dict/from_dict — surface it (don't weaken the test); the cache contract depends on faithful round-trip.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/game_data.py tests/test_ai/test_game_data.py
git commit --no-verify -m "feat(ai): cache-aware GameData.load (TTL reuse, GE always live)"
```

---

## Task 4: Config knob + `--refresh-game-data` flag + call-site threading

**Files:**
- Modify: `src/artifactsmmo_cli/config.py`
- Modify: `src/artifactsmmo_cli/commands/play.py`
- Modify: `src/artifactsmmo_cli/ai/player.py`
- Test: `tests/test_commands/` (or wherever play/config tests live — locate with `grep -rl "game_data_ttl\|def test.*play" tests/`)

- [ ] **Step 1: Write the failing config test**

```python
# add near the other Config tests (grep tests for "from artifactsmmo_cli.config import Config")
def test_config_default_game_data_ttl_is_30():
    from artifactsmmo_cli.config import Config
    cfg = Config(token="t")
    assert cfg.game_data_ttl_minutes == 30
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest -q -k game_data_ttl`
Expected: FAIL — `Config` has no `game_data_ttl_minutes`.

- [ ] **Step 3: Add the config field**

In `src/artifactsmmo_cli/config.py`, in `class Config`:
```python
    game_data_ttl_minutes: int = Field(
        default=30,
        description="Minutes to reuse the cached static game data before re-fetching",
    )
```

- [ ] **Step 4: Thread into the call sites**

`src/artifactsmmo_cli/ai/player.py` — `GamePlayer.__init__` gains two params (back-compat defaults) stored on self; `run()` uses them:
```python
    # __init__ signature: add after the existing params
    game_data_ttl_minutes: int = 30,
    refresh_game_data: bool = False,
    # in __init__ body:
    self._game_data_ttl_minutes = game_data_ttl_minutes
    self._refresh_game_data = refresh_game_data
    # at line ~217 (run):
    self.game_data = GameData.load(
        client, ttl_minutes=self._game_data_ttl_minutes,
        force_refresh=self._refresh_game_data)
```

`src/artifactsmmo_cli/commands/play.py`:
```python
    # add to the play() Typer options:
    refresh_game_data: bool = typer.Option(
        False, "--refresh-game-data",
        help="Ignore the cached static game data and re-fetch from the API"),
    # where Config is loaded, read the ttl (Config.from_token_file() already
    # gives a Config); when constructing GamePlayer, pass:
    #   game_data_ttl_minutes=config.game_data_ttl_minutes,
    #   refresh_game_data=refresh_game_data,
    # and at the TUI preload (line ~122):
    player.game_data = GameData.load(
        client, ttl_minutes=config.game_data_ttl_minutes,
        force_refresh=refresh_game_data)
```
(Locate how `play()` obtains a `Config` — if it does not currently, add `config = Config.from_token_file()` near the top, matching how other commands load config. Confirm `GamePlayer(...)` construction site and add the two kwargs.)

- [ ] **Step 5: Write a flag-threading test**

```python
# in the play command tests (grep tests for "play(" / "GamePlayer(")
def test_refresh_flag_forces_game_data_refresh(monkeypatch, tmp_path):
    """--refresh-game-data => GamePlayer constructed with refresh_game_data=True."""
    import artifactsmmo_cli.commands.play as playmod
    captured = {}
    class FakePlayer:
        def __init__(self, *a, refresh_game_data=False, game_data_ttl_minutes=30, **k):
            captured["refresh"] = refresh_game_data
            captured["ttl"] = game_data_ttl_minutes
        def run(self): pass
        def set_cycle_observer(self, *_): pass
    monkeypatch.setattr(playmod, "GamePlayer", FakePlayer)
    # call play() with refresh_game_data=True, tui=False, dry_run=True to avoid live API;
    # adapt to play()'s real signature and however it short-circuits without a token.
    # Assert captured["refresh"] is True.
```
(Adapt to the real `play()` signature and its no-token guard; the assertion is that the flag reaches `GamePlayer`. If `play()` is hard to call in isolation, instead unit-test the smaller seam: that `GamePlayer(refresh_game_data=True)` stores `self._refresh_game_data is True`.)

- [ ] **Step 6: Run to verify pass**

Run: `uv run pytest -q -k "game_data_ttl or refresh"`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/config.py src/artifactsmmo_cli/commands/play.py src/artifactsmmo_cli/ai/player.py tests/
git commit --no-verify -m "feat(cli): game_data_ttl_minutes config + --refresh-game-data flag"
```

---

## Task 5: Full suite, coverage, and live verification

**Files:** none (verification).

- [ ] **Step 1: Full suite + 100% coverage**

Run: `uv run pytest -q`
Expected: `0 failed`, `100% coverage`. If `game_data.py`/`game_data_cache.py` have uncovered lines, add targeted unit tests (e.g. a `_build_bank(None)` test; a `cache.write` OSError-swallow test via a patched `os.replace` raising OSError; a `_fetch_bank` None-data test). Do not use coverage pragmas.

- [ ] **Step 2: Live cold→warm verification**

```bash
rm -f ~/.cache/artifactsmmo/gamedata-*.json
# COLD: fetches + writes the cache
time timeout 90 uv run artifactsmmo play Robby --dry-run > /tmp/cold.log 2>&1
ls -la ~/.cache/artifactsmmo/gamedata-*.json   # cache file now exists
# WARM: reuses the cache (should reach "Loading game data..." far faster)
time timeout 90 uv run artifactsmmo play Robby --dry-run > /tmp/warm.log 2>&1
# FORCE: re-fetches despite a fresh cache
timeout 90 uv run artifactsmmo play Robby --dry-run --refresh-game-data > /tmp/force.log 2>&1
```
Expected: the cache JSON exists after the cold run; the warm run starts planning without re-paginating the static endpoints (visibly faster game-data load); `--refresh-game-data` re-fetches. Confirm the bot still plans normally (no GameData regressions) in each log.

- [ ] **Step 3: Final commit (if any coverage tests were added)**

```bash
git add tests/
git commit --no-verify -m "test(ai): coverage for GameData cache edge cases"
```

---

## Self-review notes (author)

- **Spec coverage:** GameDataCache (T1: read/write/TTL/version/corrupt/atomic/host-key); fetch/build split with GE untouched (T2); cache-aware load + warm/cold equality + GE-always-live + force_refresh (T3); config TTL knob + `--refresh-game-data` + call-site threading (T4); 100% coverage + live cold/warm/force (T5). Scope decision (GE live, static cached) realized in T2/T3; serialization (raw pages via to_dict/from_dict) in T2; injected clock in T1; no formal core (none added).
- **Naming consistency:** `GameDataCache.read(ttl_minutes, now)`, `.write(raw_pages, now)`, `.path`, `CACHE_VERSION`; `GameData.load(client, ttl_minutes=30, force_refresh=False, cache=None)`; `_fetch_<name>`/`_build_<name>` for maps/items/resources/monsters/npcs/events/bank; `Config.game_data_ttl_minutes`; `GamePlayer(..., game_data_ttl_minutes=30, refresh_game_data=False)`; `play --refresh-game-data`. Consistent across tasks.
- **Risk:** the only non-mechanical part is relocating 7 existing loader bodies (T2); the warm/cold equality test (T3 Step 5) is the mechanical proof that none changed behavior. The `play()` flag-threading test (T4) may need adapting to the real command signature — the fallback (unit-test the `GamePlayer` seam) is specified.

# Design: configurable-TTL GameData disk cache

Date: 2026-06-13
Status: APPROVED (design) — ready for implementation plan.

## Problem

`GameData.load(client)` ("Load once at startup, never mutate") runs **8 paginated
API loaders** (maps, items/recipes, resources, monsters, npcs, event-catalog, GE
orders, bank metadata) on **every `play` startup** — potentially hundreds of API
round-trips for data that almost never changes between runs. There is no disk
persistence, no TTL, and no config knob (acceptance-criterion gap; criteria 2 and
3 — planner uses/considers game data — are already met).

## Goal (acceptance criterion 1)

Cache the static game data to disk with a **configurable TTL (default 30 min)**;
on load, reuse the cache if fresh, else re-fetch and rewrite. Add a config knob
and a force-refresh flag.

## Decisions (locked in brainstorming)

1. **Scope:** cache the **7 static loaders** (maps, items, resources, monsters,
   npcs, event-catalog, bank-metadata). **GE orders are ALWAYS fetched live** —
   they are the live market order book; a 30-min-stale price would corrupt
   buy/sell decisions. (`_load_events` is the static event *catalog* — event-NPC
   spawn tiles; ACTIVE events are fetched live elsewhere in `player`, so the
   catalog is safely cacheable.)
2. **What to serialize:** the **raw API page payloads** (each `schema.to_dict()`),
   not the built indexes. Each static loader splits into `_fetch_*(client) ->
   list[dict]` (paginate, collect raw dicts) and `_build_*(pages)` (the existing
   index construction, now consuming `Schema.from_dict(d)`). Warm loads rebuild
   indexes with CURRENT code from cached raw data — robust to new index fields
   (they just rebuild); only an API *schema* change busts the cache (handled by a
   `CACHE_VERSION` tag). Verified: `MapSchema`/`ItemSchema`/`MonsterSchema` (etc.)
   expose `to_dict()` and a `from_dict()` classmethod.
3. **No formal core:** the only logic is `now - fetched_at < ttl` — trivial
   I/O-bound staleness, not decision logic over all inputs. Plain helper + unit
   tests; the formal gate does not apply.
4. **Injected clock:** `read()` takes a `now` parameter (default
   `datetime.now(tz=timezone.utc)`) so the TTL boundary is unit-testable without
   sleeping.

## Architecture

### Component A — `GameDataCache` (`src/artifactsmmo_cli/ai/game_data_cache.py`, new, one class)

Sole responsibility: disk persistence + freshness + versioning for the raw static
pages. Knows nothing about index-building or the API.

```python
CACHE_VERSION = 1  # bump on any raw-page schema change

class GameDataCache:
    def __init__(self, api_base_url: str, cache_dir: Path | None = None) -> None:
        # path = (cache_dir or ~/.cache/artifactsmmo) / f"gamedata-{host}.json"
        # host derived from api_base_url (server-wide data, not per-character)

    def read(self, ttl_minutes: int,
             now: datetime | None = None) -> dict[str, object] | None:
        """The raw-pages payload iff the cache file exists, JSON-parses, its
        `version` == CACHE_VERSION, and (now - fetched_at) < ttl. Else None.
        All-or-nothing: never returns a partial payload. Any OSError / JSON
        error / missing key / bad timestamp -> None (caller re-fetches)."""

    def write(self, raw_pages: dict[str, object],
              now: datetime | None = None) -> None:
        """Stamp {version: CACHE_VERSION, fetched_at: now.isoformat(), **raw_pages}
        and write atomically: dump to `<path>.tmp` then os.replace(tmp, path)."""
```

Cache-file shape:
```json
{ "version": 1, "fetched_at": "2026-06-13T08:00:00+00:00",
  "maps": [ {<MapSchema.to_dict>}, ... ],
  "items": [...], "resources": [...], "monsters": [...],
  "npcs": [...], "events": [...],
  "bank": {<BankDetailsSchema.to_dict> or null} }
```
(`bank` is a single object — `get_bank_details` is not paginated. `null` when the
API returns no bank data, mirroring the current `_load_bank_metadata` guard.)

### Component B — `GameData` fetch/build split (`src/artifactsmmo_cli/ai/game_data.py`)

For each static loader, split the existing method:
- `_fetch_maps(client) -> list[dict]`: the pagination loop, returning
  `[tile.to_dict() for page in pages for tile in page.data]`.
- `_build_maps(pages: list[dict]) -> None`: the existing index logic, iterating
  `MapSchema.from_dict(d) for d in pages`.

Same split for items, resources, monsters, npcs, events. Bank metadata:
- `_fetch_bank(client) -> dict | None`: `result.data.to_dict()` or None.
- `_build_bank(page: dict | None) -> None`: set `_bank_capacity` /
  `_next_expansion_cost` from the dict (or leave defaults when None).

`_load_ge_orders(client)` is **unchanged** (always live).

New `load` signature and orchestration:
```python
@classmethod
def load(cls, client, ttl_minutes: int = 30, force_refresh: bool = False,
         cache: GameDataCache | None = None) -> "GameData":
    data = cls()
    cache = cache or GameDataCache(<api_base_url from client>)
    raw = None if force_refresh else cache.read(ttl_minutes)
    if raw is None:
        raw = {
            "maps": data._fetch_maps(client),
            "items": data._fetch_items(client),
            "resources": data._fetch_resources(client),
            "monsters": data._fetch_monsters(client),
            "npcs": data._fetch_npcs(client),
            "events": data._fetch_events(client),
            "bank": data._fetch_bank(client),
        }
        cache.write(raw)
    data._build_maps(raw["maps"]); data._build_items(raw["items"])
    data._build_resources(raw["resources"]); data._build_monsters(raw["monsters"])
    data._build_npcs(raw["npcs"]); data._build_events(raw["events"])
    data._build_bank(raw["bank"])
    data._load_ge_orders(client)   # ALWAYS live
    return data
```
(Deriving `api_base_url` from `client`: the `AuthenticatedClient` exposes
`_base_url`/`base_url`; the implementer confirms the attribute and passes it.
If unavailable, `load` accepts an explicit `api_base_url` param threaded from
`Config`.)

### Component C — config + CLI flag

- `Config.game_data_ttl_minutes: int = Field(default=30, description=...)`
  (`src/artifactsmmo_cli/config.py`).
- `play(... refresh_game_data: bool = typer.Option(False, "--refresh-game-data",
  help="Ignore the cached game data and re-fetch from the API"))`
  (`src/artifactsmmo_cli/commands/play.py`), passed as `force_refresh`.
- Both call sites that build GameData (`commands/play.py:122`,
  `ai/player.py:217`) thread `ttl_minutes=config.game_data_ttl_minutes` and
  `force_refresh`. `player.load_game_data`/`__init__` gains the params with
  back-compatible defaults (30, False) so existing tests/callers are unaffected.

## Data flow

```
play (--refresh-game-data?, config.game_data_ttl_minutes)
  -> GameData.load(client, ttl_minutes, force_refresh)
       cache.read(ttl) -> raw pages | None
         None (miss/stale/corrupt/version-bump/force) -> _fetch_* (API) -> cache.write
       _build_* (current code) from raw pages -> indexes
       _load_ge_orders (always live)
  -> planner consumes GameData (unchanged)
```

## Error handling (honors "fail loud, no silent defaulting")

- A missing / unreadable / corrupt-JSON / version-mismatch / stale cache is NOT
  an error — it correctly means "fetch fresh," and we do, then rewrite. We never
  build GameData from a partial cache (`read` is all-or-nothing).
- `cache.write` failures (disk full, permissions) must NOT crash the run: the
  data is already in hand from the live fetch; a failed write is logged and
  swallowed (the next run simply re-fetches). This is the one swallow, and it is
  safe because the in-memory GameData is already complete and correct.
- `read` catches only the specific, expected failure types (`OSError`,
  `json.JSONDecodeError`, `KeyError`, `ValueError` from timestamp parsing) — never
  bare `Exception` (project rule).
- Atomic write (`tmp` + `os.replace`) guarantees a crash mid-write cannot leave a
  half-written cache that would later parse into wrong data.

## Testing strategy (pytest, 100% coverage)

`tests/test_ai/test_game_data_cache.py`:
- write→read round-trip returns the same raw payload.
- TTL boundary: `fetched_at = now - 29min` (ttl 30) → returns payload;
  `now - 31min` → None. Uses the injected `now`, no sleeping.
- version mismatch: a file with `version: 0` → None.
- corrupt JSON (write garbage) → None (no exception escapes).
- missing file → None.
- `force_refresh` path: `load(force_refresh=True)` never calls `read` (use a
  fake cache recording calls) and always `_fetch_*` + `write`.
- atomic write: after `write`, no `.tmp` file remains; the final file is valid.
- write failure (cache_dir read-only / patched `os.replace` raising OSError) is
  swallowed, run continues, GameData still complete.

`tests/test_ai/test_game_data.py` (fetch/build split):
- `_build_maps(fixture_pages)` yields the SAME indexes (`_monster_locations`,
  `_workshop_locations`, etc.) as building from a live-style fetch — i.e. a cold
  load and a warm load (cache hit) produce equal GameData (compare the public
  accessors). Use a fake client returning canned pages.
- a cache HIT still calls `_load_ge_orders` (GE always live) — assert the GE
  accessor is populated even when `read` returns a payload.
- existing GameData tests stay green (the public accessors are unchanged; only
  the internal load path is refactored).

Reuse the existing GameData test fixtures/fake-client pattern (the file already
constructs `GameData()` with injected `_item_stats` etc.; the fetch/build tests
add a canned-page fake client alongside).

## Out of scope (YAGNI)

- No cache for GE orders or active-events (intentionally live).
- No background/async cache refresh; no partial/per-loader TTLs (one TTL for the
  whole static set, one timestamp).
- No cross-machine/shared cache; the file is local under `~/.cache`.
- No migration of old cache formats — a version bump simply re-fetches.

## Files

- Create: `src/artifactsmmo_cli/ai/game_data_cache.py`,
  `tests/test_ai/test_game_data_cache.py`.
- Modify: `src/artifactsmmo_cli/ai/game_data.py` (fetch/build split + new `load`),
  `src/artifactsmmo_cli/config.py` (ttl field),
  `src/artifactsmmo_cli/commands/play.py` (flag + thread params),
  `src/artifactsmmo_cli/ai/player.py` (thread ttl/force_refresh into its
  `GameData.load`), `tests/test_ai/test_game_data.py` (fetch/build + warm/cold
  equality).

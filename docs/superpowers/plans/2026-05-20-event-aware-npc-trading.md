# Event-aware NPC Trading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop repeated HTTP 598 on NpcSell/NpcBuy by making the AI player aware that gold merchants are time-gated event NPCs — seed their fixed spawn tiles from the events catalog, gate trading on the merchant's event being currently active and reachable, and seize active windows.

**Architecture:** `GameData` gains an event-NPC registry loaded once from `GET /events`. `WorldState` gains a per-cycle `active_events` snapshot loaded from `GET /events/active`. A shared helper decides whether an event NPC is tradeable right now (active + reachable before expiry). `NpcSellAction` and `NpcBuyAction` consult it in `is_applicable`; `SellInventoryGoal` consults it to boost priority during live windows.

**Tech Stack:** Python 3.13, `uv`, pytest. API client `artifactsmmo_api_client` (events endpoints under `api/events/`).

---

## Background facts (verified against live API 2026-05-20)

- `GET /events` catalog entry (`EventSchema`): `code`, `content` (`EventContentSchema` with `type_: MapContentType`, `code`), `maps` (`list[EventMapSchema]` each with `x`, `y`, `layer`), `duration`, `rate`.
- `GET /events/active` (`ActiveEventSchema`): `code`, `map_` (`MapSchema`), `expiration: datetime` (tz-aware), `duration`, `created_at`.
- The five gold merchants — `fish_merchant` (2,5), `gemstone_merchant` (6,-1), `herbal_merchant` (7,-1), `nomadic_merchant` (3,2), `timber_merchant` (2,4) — appear ONLY as catalog events with `content.type_ == MapContentType.NPC` and `content.code == event code`. They are absent from `get_all_maps`.
- For these merchants the event `code` equals the NPC `content.code`; the registry stores the mapping explicitly so future divergence is handled.

## File Structure

- Create `src/artifactsmmo_cli/ai/event_availability.py` — pure helper deciding event-NPC tradeability (no API calls). One responsibility.
- Modify `src/artifactsmmo_cli/ai/game_data.py` — `_load_events`, registry fields, accessors, `npc_location` fallback.
- Modify `src/artifactsmmo_cli/ai/world_state.py` — `active_events` field + `from_character_schema` param.
- Modify all `WorldState(...)` / `from_character_schema(...)` call sites to thread `active_events` (mechanical, mirrors existing `pending_items` threading).
- Modify `src/artifactsmmo_cli/ai/player.py` — fetch active events per cycle into WorldState.
- Modify `src/artifactsmmo_cli/ai/actions/npc_sell.py` and `src/artifactsmmo_cli/ai/actions/npc.py` — event gate in `is_applicable`.
- Modify `src/artifactsmmo_cli/ai/goals/sell_inventory.py` — priority boost.
- Tests under `tests/`.

---

## Task 1: WorldState gains `active_events` field

**Files:**
- Modify: `src/artifactsmmo_cli/ai/world_state.py`
- Test: `tests/test_world_state.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_world_state.py`:

```python
from datetime import datetime, timezone


def test_active_events_defaults_empty():
    state = _minimal_world_state()  # existing helper in this test module
    assert state.active_events == {}


def test_active_events_round_trips():
    exp = datetime(2026, 5, 20, 22, 30, tzinfo=timezone.utc)
    state = _minimal_world_state(active_events={"gemstone_merchant": exp})
    assert state.active_events["gemstone_merchant"] == exp
```

If `tests/test_world_state.py` has no `_minimal_world_state` helper or constructs `WorldState` inline, instead construct `WorldState(...)` directly with all required fields plus `active_events=...`, following the construction already used elsewhere in that file.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_world_state.py -k active_events -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'active_events'` (or AttributeError).

- [ ] **Step 3: Add the field**

In `src/artifactsmmo_cli/ai/world_state.py`, add after the `wisdom` field (keep it last so it has a default and ordering stays valid):

```python
    active_events: dict[str, datetime] = field(default_factory=dict)
    """event code -> expiration (tz-aware). Per-cycle snapshot from
    GET /events/active. Defaults empty so constructions that don't supply it
    (and planner sims through actions that preserve it) keep working."""
```

`datetime` and `field` are already imported at the top of the file.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_world_state.py -k active_events -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/world_state.py tests/test_world_state.py
git commit -m "feat(ai): add active_events snapshot field to WorldState"
```

---

## Task 2: `from_character_schema` accepts and threads `active_events`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/world_state.py`
- Test: `tests/test_world_state.py`

- [ ] **Step 1: Write the failing test**

```python
def test_from_character_schema_threads_active_events(sample_character_schema):
    exp = {"gemstone_merchant": datetime(2026, 5, 20, 22, 30, tzinfo=timezone.utc)}
    state = WorldState.from_character_schema(sample_character_schema, active_events=exp)
    assert state.active_events == exp


def test_from_character_schema_active_events_defaults_empty(sample_character_schema):
    state = WorldState.from_character_schema(sample_character_schema)
    assert state.active_events == {}
```

Use whatever fixture/builder the test module already uses for a `CharacterSchema`; if it builds one inline, reuse that construction.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_world_state.py -k from_character_schema_threads_active_events -v`
Expected: FAIL — `TypeError: from_character_schema() got an unexpected keyword argument 'active_events'`.

- [ ] **Step 3: Add the parameter and thread it**

In `from_character_schema`, add the parameter (after `pending_items`):

```python
        pending_items: "tuple[tuple[str, str], ...] | None" = None,
        active_events: dict[str, datetime] | None = None,
    ) -> "WorldState":
```

In the `return cls(...)` block, add the keyword (after `pending_items=pending_items,`):

```python
            pending_items=pending_items,
            active_events=active_events or {},
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_world_state.py -k active_events -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/world_state.py tests/test_world_state.py
git commit -m "feat(ai): thread active_events through from_character_schema"
```

---

## Task 3: Preserve `active_events` across all state transitions

Every `WorldState(...)` construction in an action's `apply()` and every `from_character_schema(...)` in an `execute()` must carry the prior state's `active_events` forward, exactly as they already carry `pending_items`. Otherwise the planner loses the snapshot after the first simulated step and multi-step plans like `[Move, NpcSell]` break.

**Files (each gets the same one-line addition):**
- Modify, add `active_events=state.active_events,` to each `WorldState(` call (after the `pending_items=...` line):
  - `src/artifactsmmo_cli/ai/actions/movement.py:31`
  - `src/artifactsmmo_cli/ai/actions/equipment.py:72`, `:133`
  - `src/artifactsmmo_cli/ai/actions/claim.py:36`
  - `src/artifactsmmo_cli/ai/actions/rest.py:23`
  - `src/artifactsmmo_cli/ai/actions/combat.py:56`
  - `src/artifactsmmo_cli/ai/actions/bank_gold.py:20` (uses `state` param name — confirm and match)
  - `src/artifactsmmo_cli/ai/actions/gathering.py:50`
  - `src/artifactsmmo_cli/ai/actions/crafting.py:66`
  - `src/artifactsmmo_cli/ai/actions/delete.py:34`
  - `src/artifactsmmo_cli/ai/actions/npc_sell.py:45`
  - `src/artifactsmmo_cli/ai/actions/task_trade.py:42`
  - `src/artifactsmmo_cli/ai/actions/bank_expansion.py:32`
  - `src/artifactsmmo_cli/ai/actions/movement_semantic.py:34`
  - `src/artifactsmmo_cli/ai/actions/npc.py:43`
  - `src/artifactsmmo_cli/ai/actions/task.py:39`, `:99`, `:168`, `:228`
  - `src/artifactsmmo_cli/ai/actions/recycle.py:47`
  - `src/artifactsmmo_cli/ai/actions/optimize_loadout.py:62`
  - `src/artifactsmmo_cli/ai/actions/consumable.py:56`
  - `src/artifactsmmo_cli/ai/actions/bank.py:35`, `:109`
  - `src/artifactsmmo_cli/ai/player.py:560` (`_sync_bank`), `:597` (`_sync_pending`)
- Modify, add `active_events=state.active_events,` to each `from_character_schema(` call (after the `pending_items=...` argument). Note the variable holding the prior state is `state` in actions; in `player.py:534` use the carry described in Task 5, so SKIP `player.py:534` here:
  - `rest.py:54`, `transition.py:33`, `crafting.py:102`, `task_trade.py:78`, `combat.py:99`, `movement.py:71`, `delete.py:66`, `claim.py:78`, `gathering.py:93`, `npc_sell.py:81`, `bank.py:73`, `bank.py:145`, `bank_expansion.py:68`, `consumable.py:91`, `recycle.py:83`, `npc.py:81`, `task.py:75`, `task.py:135`, `task.py:204`, `task.py:264`, `equipment.py:104`, `equipment.py:165`, `bank_gold.py:66`, `bank_gold.py:107`

  For `transition.py:33` confirm the prior-state variable name (it may differ); thread that variable's `.active_events`.

- Test: `tests/test_active_events_preserved.py` (new) — but follow the project rule "use the test suite": place it in `tests/`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_active_events_preserved.py`:

```python
"""active_events must survive action.apply() so multi-step plans keep the snapshot."""
from datetime import datetime, timezone

from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from tests.helpers_world_state import make_world_state  # reuse existing builder


def test_move_apply_preserves_active_events():
    exp = {"gemstone_merchant": datetime(2026, 5, 20, 22, 30, tzinfo=timezone.utc)}
    state = make_world_state(x=0, y=0, active_events=exp)
    new = MoveAction(x=1, y=0).apply(state, GameData())
    assert new.active_events == exp
```

If no shared `make_world_state` builder exists, construct the `WorldState` inline with all required fields plus `active_events=exp`. Search `tests/` for an existing helper first (`grep -rn "def make_world_state\|def _world_state\|def build_state" tests/`).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_active_events_preserved.py -v`
Expected: FAIL — `new.active_events == {}` (MoveAction.apply drops it).

- [ ] **Step 3: Thread the field through every site**

For each `WorldState(` site listed above, add the line after `pending_items=...`:

```python
            pending_items=state.pending_items,
            active_events=state.active_events,
        )
```

For each `from_character_schema(` site listed above, add the argument after `pending_items=...`:

```python
            pending_items=state.pending_items,
            active_events=state.active_events,
        )
```

Verify completeness afterward:

```bash
# every WorldState( apply-site should now mention active_events; find stragglers:
grep -rL "active_events" $(grep -rl "return WorldState(" src/artifactsmmo_cli/ai/actions)
```

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS, 0 skipped. (The new preservation test passes; nothing else regresses.)

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai tests/test_active_events_preserved.py
git commit -m "feat(ai): preserve active_events across all state transitions"
```

---

## Task 4: GameData event-NPC registry

**Files:**
- Modify: `src/artifactsmmo_cli/ai/game_data.py`
- Test: `tests/test_game_data_events.py` (new, under `tests/`)

- [ ] **Step 1: Write the failing test**

Create `tests/test_game_data_events.py`:

```python
"""GameData event-NPC registry: spawns, event-code mapping, location fallback."""
from unittest.mock import patch

from artifactsmmo_api_client.models.event_schema import EventSchema
from artifactsmmo_api_client.models.event_content_schema import EventContentSchema
from artifactsmmo_api_client.models.event_map_schema import EventMapSchema
from artifactsmmo_api_client.models.map_content_type import MapContentType
from artifactsmmo_api_client.models.static_data_page_event_schema import StaticDataPageEventSchema

from artifactsmmo_cli.ai.game_data import GameData


def _catalog():
    npc_event = EventSchema(
        name="Gemstone Merchant",
        code="gemstone_merchant",
        content=EventContentSchema(type_=MapContentType.NPC, code="gemstone_merchant"),
        maps=[EventMapSchema(map_id=238, x=6, y=-1, layer="overworld", skin="x")],
        duration=60,
        rate=1500,
    )
    monster_event = EventSchema(
        name="Bandit Camp",
        code="bandit_camp",
        content=EventContentSchema(type_=MapContentType.MONSTER, code="bandit_lizard"),
        maps=[EventMapSchema(map_id=538, x=4, y=5, layer="overworld", skin="y")],
        duration=120,
        rate=1500,
    )
    return StaticDataPageEventSchema(data=[npc_event, monster_event], total=2, page=1, size=100, pages=1)


def test_load_events_indexes_npc_events_only():
    gd = GameData()
    with patch("artifactsmmo_cli.ai.game_data.get_all_events", return_value=_catalog()):
        gd._load_events(client=None)
    assert gd.is_event_npc("gemstone_merchant") is True
    assert gd.is_event_npc("bandit_lizard") is False  # monster event, not an NPC
    assert gd.npc_event_code("gemstone_merchant") == "gemstone_merchant"


def test_npc_location_falls_back_to_event_spawn():
    gd = GameData()
    with patch("artifactsmmo_cli.ai.game_data.get_all_events", return_value=_catalog()):
        gd._load_events(client=None)
    # not in static map scan, resolves from event spawn
    assert gd.npc_location("gemstone_merchant") == (6, -1)


def test_static_npc_location_wins_over_event_spawn():
    gd = GameData()
    gd._npc_locations["gemstone_merchant"] = (1, 1)
    with patch("artifactsmmo_cli.ai.game_data.get_all_events", return_value=_catalog()):
        gd._load_events(client=None)
    assert gd.npc_location("gemstone_merchant") == (1, 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_game_data_events.py -v`
Expected: FAIL — `AttributeError: 'GameData' object has no attribute '_load_events'`.

- [ ] **Step 3: Implement registry**

In `src/artifactsmmo_cli/ai/game_data.py`:

Add the import near the other event/api imports at the top:

```python
from artifactsmmo_api_client.api.events.get_all_events_events_get import sync as get_all_events
```

Add fields in the `GameData` dataclass after `_npc_sell_prices`:

```python
    _event_npc_spawns: dict[str, tuple[int, int]] = field(default_factory=dict)  # npc_code -> fixed event spawn tile
    _npc_event_code: dict[str, str] = field(default_factory=dict)  # npc_code -> event code (membership = is_event_npc)
```

Add `_load_events` (place near `_load_npcs`):

```python
    def _load_events(self, client: AuthenticatedClient) -> None:
        """Index event NPCs (code -> event code, code -> fixed spawn tile) from the catalog.

        Event merchants never appear in get_all_maps; their fixed spawn tile lives
        only in the events catalog, and they exist on the map only while their event
        is active.
        """
        page = 1
        while True:
            result = get_all_events(client=client, page=page, size=100)
            if result is None or not result.data:
                break
            for ev in result.data:
                if ev.content.type_ != MapContentType.NPC:
                    continue
                npc_code = ev.content.code
                self._npc_event_code[npc_code] = ev.code
                if ev.maps:
                    first = ev.maps[0]
                    self._event_npc_spawns[npc_code] = (first.x, first.y)
            if len(result.data) < 100:
                break
            page += 1
```

Update `npc_location` (currently lines ~239-241) to fall back:

```python
    def npc_location(self, npc_code: str) -> tuple[int, int] | None:
        """Location of a named NPC: static map scan first, then event spawn tile."""
        loc = self._npc_locations.get(npc_code)
        if loc is not None:
            return loc
        return self._event_npc_spawns.get(npc_code)
```

Add accessors near `npc_location`:

```python
    def is_event_npc(self, npc_code: str) -> bool:
        """True if this NPC only exists during a timed event window."""
        return npc_code in self._npc_event_code

    def npc_event_code(self, npc_code: str) -> str | None:
        """Event code whose active window spawns this NPC, or None if not an event NPC."""
        return self._npc_event_code.get(npc_code)
```

Wire `_load_events` into the loader. Find the block (around lines 279-285):

```python
        data._load_maps(client)
        data._load_items(client)
        data._load_resources(client)
        data._load_monsters(client)
        data._load_npcs(client)
        data._load_bank_metadata(client)
        return data
```

Add after `data._load_npcs(client)`:

```python
        data._load_npcs(client)
        data._load_events(client)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_game_data_events.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/game_data.py tests/test_game_data_events.py
git commit -m "feat(ai): index event-NPC spawn tiles and event codes in GameData"
```

---

## Task 5: Player fetches active events per cycle

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py`
- Test: `tests/test_player_active_events.py` (new, under `tests/`)

- [ ] **Step 1: Write the failing test**

Create `tests/test_player_active_events.py`. Build it to mirror how the existing player tests instantiate the player and stub the client (search `tests/` for the current pattern: `grep -rn "AIPlayer(\|_fetch_world_state" tests/`). The behavior to assert:

```python
"""_fetch_world_state populates WorldState.active_events from get_all_active_events."""
from datetime import datetime, timezone
from unittest.mock import patch

# import the player class and its test helpers exactly as the existing player tests do


def test_fetch_world_state_populates_active_events(player_with_stubbed_character):
    player, client = player_with_stubbed_character  # existing-style fixture
    exp = datetime(2026, 5, 20, 22, 30, tzinfo=timezone.utc)
    active = _stub_active_events_response([("gemstone_merchant", exp)])
    with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=active):
        state = player._fetch_world_state(client)
    assert state.active_events == {"gemstone_merchant": exp}
```

Where `_stub_active_events_response(pairs)` returns an object with `.data` = list of `ActiveEventSchema(code=..., expiration=..., ...)`. Construct `ActiveEventSchema` with the required fields (`name`, `code`, `map_`, `previous_map`, `duration`, `expiration`, `created_at`) using minimal `MapSchema` instances, or stub a lightweight object exposing `.code` and `.expiration` and pass it through — match how other player tests stub API responses.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_player_active_events.py -v`
Expected: FAIL — `state.active_events == {}` (not yet fetched) or `AttributeError` on the patched name.

- [ ] **Step 3: Implement the fetch**

In `src/artifactsmmo_cli/ai/player.py`:

Add the import near the other api imports:

```python
from artifactsmmo_api_client.api.events.get_all_active_events_events_active_get import sync as get_all_active_events
```

Add a helper method:

```python
    def _fetch_active_events(self, client: AuthenticatedClient) -> dict[str, datetime]:
        """Map of currently-active event code -> expiration. Empty on no/failed data."""
        active: dict[str, datetime] = {}
        page = 1
        while True:
            result = get_all_active_events(client=client, page=page, size=100)
            if result is None or not result.data:
                break
            for ev in result.data:
                active[ev.code] = ev.expiration
            if len(result.data) < 100:
                break
            page += 1
        return active
```

`datetime` is already imported in player.py (used by cooldown logic); if not, add `from datetime import datetime`.

In `_fetch_world_state`, replace the final `return` (lines ~531-539):

```python
        bank_items = self.state.bank_items if self.state else None
        bank_gold = self.state.bank_gold if self.state else None
        pending_items = self.state.pending_items if self.state else None
        active_events = self._fetch_active_events(client)
        return WorldState.from_character_schema(
            last_result.data,
            bank_items=bank_items,
            bank_gold=bank_gold,
            pending_items=pending_items,
            active_events=active_events,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_player_active_events.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_player_active_events.py
git commit -m "feat(ai): fetch active events into WorldState each cycle"
```

---

## Task 6: Event-availability helper

**Files:**
- Create: `src/artifactsmmo_cli/ai/event_availability.py`
- Test: `tests/test_event_availability.py` (new, under `tests/`)

- [ ] **Step 1: Write the failing test**

Create `tests/test_event_availability.py`:

```python
"""event_npc_tradeable: event NPC must be active AND reachable before expiry."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from artifactsmmo_cli.ai.event_availability import event_npc_tradeable
from artifactsmmo_cli.ai.game_data import GameData


def _gd_with_event(spawn=(6, -1)):
    gd = GameData()
    gd._npc_event_code["gemstone_merchant"] = "gemstone_merchant"
    gd._event_npc_spawns["gemstone_merchant"] = spawn
    return gd


def test_active_and_reachable_is_true():
    now = datetime(2026, 5, 20, 21, 0, tzinfo=timezone.utc)
    gd = _gd_with_event()
    active = {"gemstone_merchant": now + timedelta(minutes=30)}
    assert event_npc_tradeable("gemstone_merchant", gd, x=6, y=-1, active_events=active, now=now) is True


def test_inactive_is_false():
    now = datetime(2026, 5, 20, 21, 0, tzinfo=timezone.utc)
    gd = _gd_with_event()
    assert event_npc_tradeable("gemstone_merchant", gd, x=6, y=-1, active_events={}, now=now) is False


def test_active_but_expiring_before_arrival_is_false():
    now = datetime(2026, 5, 20, 21, 0, tzinfo=timezone.utc)
    gd = _gd_with_event(spawn=(100, 100))  # far from (0,0)
    active = {"gemstone_merchant": now + timedelta(seconds=5)}  # expires almost immediately
    assert event_npc_tradeable("gemstone_merchant", gd, x=0, y=0, active_events=active, now=now) is False


def test_non_event_npc_is_true_passthrough():
    now = datetime(2026, 5, 20, 21, 0, tzinfo=timezone.utc)
    gd = GameData()  # 'tailor' is not registered as event npc
    assert event_npc_tradeable("tailor", gd, x=0, y=0, active_events={}, now=now) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_event_availability.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.event_availability'`.

- [ ] **Step 3: Implement the helper**

Create `src/artifactsmmo_cli/ai/event_availability.py`:

```python
"""Decide whether an event-gated NPC can be traded with right now."""

from datetime import datetime

from artifactsmmo_cli.ai.game_data import GameData

EVENT_TRAVEL_SECONDS_PER_TILE = 5.0
"""Rough seconds per map tile of travel, used to check the event window won't
close before the character can walk to the merchant."""

EVENT_ARRIVAL_MARGIN_SECONDS = 10.0
"""Safety margin added to estimated travel time before committing to the trip."""


def event_npc_tradeable(
    npc_code: str,
    game_data: GameData,
    *,
    x: int,
    y: int,
    active_events: dict[str, datetime],
    now: datetime,
) -> bool:
    """True if this NPC is tradeable from (x, y) right now.

    Non-event NPCs are always tradeable (returns True) — the caller's other
    checks (location known, price, gold/inventory) still apply. Event NPCs are
    tradeable only when their event is active and won't expire before the
    character can reach the spawn tile.
    """
    event_code = game_data.npc_event_code(npc_code)
    if event_code is None:
        return True  # not an event NPC; nothing to gate on here
    expiration = active_events.get(event_code)
    if expiration is None:
        return False  # event not active
    spawn = game_data.npc_location(npc_code)
    if spawn is None:
        return False
    distance = abs(spawn[0] - x) + abs(spawn[1] - y)
    travel_seconds = distance * EVENT_TRAVEL_SECONDS_PER_TILE
    remaining = (expiration - now).total_seconds()
    return remaining > travel_seconds + EVENT_ARRIVAL_MARGIN_SECONDS
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_event_availability.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/event_availability.py tests/test_event_availability.py
git commit -m "feat(ai): add event-NPC tradeability helper"
```

---

## Task 7: Gate NpcSellAction on event availability

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/npc_sell.py`
- Test: `tests/test_npc_sell_event_gate.py` (new, under `tests/`)

- [ ] **Step 1: Write the failing test**

Create `tests/test_npc_sell_event_gate.py`:

```python
"""NpcSellAction.is_applicable gates event merchants on active+reachable windows."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.game_data import GameData
from tests.helpers_world_state import make_world_state  # reuse existing builder


def _gd():
    gd = GameData()
    gd._npc_event_code["gemstone_merchant"] = "gemstone_merchant"
    gd._event_npc_spawns["gemstone_merchant"] = (6, -1)
    gd._npc_sell_prices["gemstone_merchant"] = {"copper_ore": 1}
    return gd


FIXED_NOW = datetime(2026, 5, 20, 21, 0, tzinfo=timezone.utc)


def _action():
    return NpcSellAction(npc_code="gemstone_merchant", item_code="copper_ore",
                         quantity=1, npc_location=(6, -1))


def test_applicable_when_event_active_and_reachable():
    gd = _gd()
    state = make_world_state(x=6, y=-1, inventory={"copper_ore": 5},
                             active_events={"gemstone_merchant": FIXED_NOW + timedelta(minutes=30)})
    with patch("artifactsmmo_cli.ai.actions.npc_sell.datetime") as dt:
        dt.now.return_value = FIXED_NOW
        assert _action().is_applicable(state, gd) is True


def test_not_applicable_when_event_inactive():
    gd = _gd()
    state = make_world_state(x=6, y=-1, inventory={"copper_ore": 5}, active_events={})
    with patch("artifactsmmo_cli.ai.actions.npc_sell.datetime") as dt:
        dt.now.return_value = FIXED_NOW
        assert _action().is_applicable(state, gd) is False
```

If `make_world_state` does not exist, construct `WorldState` inline (all required fields + `inventory=`, `x=`, `y=`, `active_events=`). The existing `is_applicable` already requires `state.inventory.get(item_code) >= quantity` and `npc_buys_item is not None`; `_gd()` and the inventory satisfy both.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_npc_sell_event_gate.py -v`
Expected: FAIL — `test_not_applicable_when_event_inactive` returns True (no gate yet).

- [ ] **Step 3: Add the gate**

In `src/artifactsmmo_cli/ai/actions/npc_sell.py`:

Add imports at the top:

```python
from datetime import datetime, timezone

from artifactsmmo_cli.ai.event_availability import event_npc_tradeable
```

Replace `is_applicable`:

```python
    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if self.npc_location is None:
            return False
        if game_data.npc_buys_item(self.npc_code, self.item_code) is None:
            return False
        if state.inventory.get(self.item_code, 0) < self.quantity:
            return False
        return event_npc_tradeable(
            self.npc_code, game_data,
            x=state.x, y=state.y,
            active_events=state.active_events,
            now=datetime.now(timezone.utc),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_npc_sell_event_gate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/npc_sell.py tests/test_npc_sell_event_gate.py
git commit -m "feat(ai): gate NpcSell on active reachable event window"
```

---

## Task 8: Gate NpcBuyAction on event availability

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/npc.py`
- Test: `tests/test_npc_buy_event_gate.py` (new, under `tests/`)

- [ ] **Step 1: Write the failing test**

Create `tests/test_npc_buy_event_gate.py`:

```python
"""NpcBuyAction.is_applicable gates event merchants on active+reachable windows."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.game_data import GameData
from tests.helpers_world_state import make_world_state


def _gd():
    gd = GameData()
    gd._npc_event_code["gemstone_merchant"] = "gemstone_merchant"
    gd._event_npc_spawns["gemstone_merchant"] = (6, -1)
    gd._npc_stock["gemstone_merchant"] = {"copper_ore": 10}  # buy price
    return gd


FIXED_NOW = datetime(2026, 5, 20, 21, 0, tzinfo=timezone.utc)


def _action():
    return NpcBuyAction(npc_code="gemstone_merchant", item_code="copper_ore",
                        quantity=1, npc_location=(6, -1))


def test_applicable_when_event_active_and_reachable():
    gd = _gd()
    state = make_world_state(x=6, y=-1, gold=1000,
                             active_events={"gemstone_merchant": FIXED_NOW + timedelta(minutes=30)})
    with patch("artifactsmmo_cli.ai.actions.npc.datetime") as dt:
        dt.now.return_value = FIXED_NOW
        assert _action().is_applicable(state, gd) is True


def test_not_applicable_when_event_inactive():
    gd = _gd()
    state = make_world_state(x=6, y=-1, gold=1000, active_events={})
    with patch("artifactsmmo_cli.ai.actions.npc.datetime") as dt:
        dt.now.return_value = FIXED_NOW
        assert _action().is_applicable(state, gd) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_npc_buy_event_gate.py -v`
Expected: FAIL — `test_not_applicable_when_event_inactive` returns True (no gate yet).

- [ ] **Step 3: Add the gate**

In `src/artifactsmmo_cli/ai/actions/npc.py`:

Add imports at the top:

```python
from datetime import datetime, timezone

from artifactsmmo_cli.ai.event_availability import event_npc_tradeable
```

Replace `is_applicable`:

```python
    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if self.npc_location is None:
            return False
        price = game_data.npc_sells_item(self.npc_code, self.item_code)
        if price is None:
            return False
        if state.gold < price * self.quantity:
            return False
        return event_npc_tradeable(
            self.npc_code, game_data,
            x=state.x, y=state.y,
            active_events=state.active_events,
            now=datetime.now(timezone.utc),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_npc_buy_event_gate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/npc.py tests/test_npc_buy_event_gate.py
git commit -m "feat(ai): gate NpcBuy on active reachable event window"
```

---

## Task 9: SellInventory seizes active windows

The goal currently activates only when the bank is inaccessible. Extend `value()` so that, even when the bank IS accessible, an active reachable merchant that buys a held item makes selling worthwhile during the rare window.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/sell_inventory.py`
- Test: `tests/test_sell_inventory_seize.py` (new, under `tests/`)

- [ ] **Step 1: Write the failing test**

Create `tests/test_sell_inventory_seize.py`:

```python
"""SellInventoryGoal boosts value when a reachable merchant event is live."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from artifactsmmo_cli.ai.goals.sell_inventory import SellInventoryGoal, SEIZE_WINDOW_VALUE
from artifactsmmo_cli.ai.game_data import GameData
from tests.helpers_world_state import make_world_state


def _gd():
    gd = GameData()
    gd._npc_event_code["gemstone_merchant"] = "gemstone_merchant"
    gd._event_npc_spawns["gemstone_merchant"] = (6, -1)
    gd._npc_sell_prices["gemstone_merchant"] = {"copper_ore": 1}
    return gd


FIXED_NOW = datetime(2026, 5, 20, 21, 0, tzinfo=timezone.utc)


def test_value_boosted_when_window_live_even_if_bank_accessible():
    gd = _gd()
    state = make_world_state(x=6, y=-1, inventory={"copper_ore": 5}, inventory_max=104,
                             active_events={"gemstone_merchant": FIXED_NOW + timedelta(minutes=30)})
    with patch("artifactsmmo_cli.ai.goals.sell_inventory.datetime") as dt:
        dt.now.return_value = FIXED_NOW
        goal = SellInventoryGoal(bank_accessible=True)
        assert goal.value(state, gd) >= SEIZE_WINDOW_VALUE


def test_no_boost_when_no_window_and_bank_accessible():
    gd = _gd()
    state = make_world_state(x=6, y=-1, inventory={"copper_ore": 5}, inventory_max=104,
                             active_events={})
    with patch("artifactsmmo_cli.ai.goals.sell_inventory.datetime") as dt:
        dt.now.return_value = FIXED_NOW
        goal = SellInventoryGoal(bank_accessible=True)
        assert goal.value(state, gd) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sell_inventory_seize.py -v`
Expected: FAIL — `ImportError: cannot import name 'SEIZE_WINDOW_VALUE'` (and boost not implemented).

- [ ] **Step 3: Implement the boost**

In `src/artifactsmmo_cli/ai/goals/sell_inventory.py`:

Add imports at the top:

```python
from datetime import datetime, timezone

from artifactsmmo_cli.ai.event_availability import event_npc_tradeable
```

Add a module constant after the imports:

```python
SEIZE_WINDOW_VALUE = 60.0
"""Goal value when a reachable merchant event is live and we hold sellable
stock — high enough to opportunistically sell during the rare window, but
below the bank-locked near-full urgency (which can reach ~100)."""
```

Add a private helper and extend `value()`:

```python
    def _active_window_for_inventory(self, state: WorldState, game_data: GameData) -> bool:
        """True if some held item can be sold to a currently-active reachable merchant."""
        now = datetime.now(timezone.utc)
        for item_code, qty in state.inventory.items():
            if qty <= 0:
                continue
            for npc_code, _price in game_data.npcs_buying_item(item_code):
                if not game_data.is_event_npc(npc_code):
                    continue
                if event_npc_tradeable(npc_code, game_data, x=state.x, y=state.y,
                                       active_events=state.active_events, now=now):
                    return True
        return False

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if state.inventory_max == 0 or self.is_satisfied(state):
            return 0.0
        sellable = any(game_data.npcs_buying_item(code)
                       for code in state.inventory if state.inventory[code] > 0)
        if not sellable:
            return 0.0
        used_fraction = state.inventory_used / state.inventory_max
        bank_locked_value = 0.0 if self._bank_accessible else used_fraction * 100.0
        if self._active_window_for_inventory(state, game_data):
            return max(bank_locked_value, SEIZE_WINDOW_VALUE)
        return bank_locked_value
```

This preserves the original behavior (bank-locked → `used_fraction * 100`; bank-accessible and no window → `0.0`) and adds the seize-window boost.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_sell_inventory_seize.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/sell_inventory.py tests/test_sell_inventory_seize.py
git commit -m "feat(ai): SellInventory seizes live merchant windows"
```

---

## Task 10: Full-suite verification and coverage

**Files:** none (verification only).

- [ ] **Step 1: Run the full suite**

Run: `uv run pytest -q`
Expected: all pass, **0 skipped**.

- [ ] **Step 2: Confirm coverage of new code**

Run: `uv run pytest --cov=artifactsmmo_cli.ai.event_availability --cov=artifactsmmo_cli.ai.game_data --cov=artifactsmmo_cli.ai.goals.sell_inventory --cov-report=term-missing -q`
Expected: 100% on the new helper; no uncovered new lines in the modified files. Add targeted tests for any missed lines (e.g. `npc_location` returning None for unknown NPC, `_load_events` paging past 100).

- [ ] **Step 3: Type check**

Run: `uv run mypy src/artifactsmmo_cli/ai`
Expected: no new errors.

- [ ] **Step 4: Commit any coverage/type fixes**

```bash
git add -A
git commit -m "test(ai): close coverage gaps for event-aware trading"
```

---

## Self-review notes

- Spec coverage: registry (Task 4), WorldState snapshot + threading (Tasks 1-3, 5), sell gate (Task 7), buy gate (Task 8), priority boost (Task 9), execute-time 598 backstop unchanged (relied upon, not modified). All spec sections map to tasks.
- Type consistency: `event_npc_tradeable(npc_code, game_data, *, x, y, active_events, now)` used identically in Tasks 6-9. `npc_event_code` / `is_event_npc` / `npc_location` defined in Task 4 and consumed unchanged later. `active_events: dict[str, datetime]` consistent throughout.
- Threading risk (Task 3) is the largest mechanical surface; the default-empty field plus the `grep -rL` completeness check guard against missed sites, and the full suite (Task 10) catches any frozen-dataclass omission at construction time.

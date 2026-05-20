# Event-aware NPC trading

Date: 2026-05-20
Status: Approved (design)

## Problem

The AI player issues `NpcSell` (and `NpcBuy`) actions against merchant NPCs whose
locations were seeded only from the static map scan (`get_all_maps`, overworld
layer). Five gold-trading merchants — `fish_merchant`, `gemstone_merchant`,
`herbal_merchant`, `nomadic_merchant`, `timber_merchant` — are **event NPCs**:
they spawn at a fixed tile only during a timed event window (`duration` 60 min,
recurring on `rate` ~1500 min). They never appear in `get_all_maps`, so the
player either had no location for them or trusted a stale one, and never checked
whether the event was currently active.

Observed in `traces.jsonl`: six consecutive `error:HTTP_598`
("content not found at this location") on
`NpcSell(copper_ore×1@gemstone_merchant)` at tile (6, -1) — which the events
catalog confirms is gemstone_merchant's exact spawn tile. The location was
correct; the merchant simply was not active at that moment. With inventory
near full, `SellInventory` stayed top-priority and re-selected the same doomed
action across cycles 117–119+.

HTTP 598 is already caught (`player.py` `_execute`) and recorded as
`error:HTTP_598`, then state is refetched and the planner replans — so it is not
fatal. The defect is wasted cycles repeatedly attempting an action that cannot
succeed, because availability is never checked before attempting.

## Authoritative data sources

- `GET /events` (`get_all_events`) — static catalog. Each event entry whose
  `content.type == "npc"` carries the NPC code and a fixed spawn tile
  (`maps[].x`, `maps[].y`, `layer`). Load once.
- `GET /events/active` (`get_all_active_events`) — events live right now, each
  with an `expiration` timestamp. Dynamic; refetch per cycle.

## Design

### 1. GameData — event registry (static, load once)

Add `_load_events(client)` to the loader sequence (alongside `_load_maps`,
`_load_npcs`, etc.). It calls `get_all_events` and builds:

- `_event_npc_spawns: dict[str, tuple[int, int]]` — npc_code → fixed spawn tile,
  for catalog entries with `content.type == "npc"`.
- `_event_npc_codes: frozenset[str]` — the set of NPC codes that are event-gated.

New accessors:

- `is_event_npc(code: str) -> bool`.
- `npc_location(code)` gains a fallback: static map scan first
  (`_npc_locations`), then `_event_npc_spawns`. This makes event-merchant
  locations resolvable even though they are absent from `get_all_maps`.

### 2. WorldState — active-event snapshot (dynamic)

Add field `active_events: dict[str, datetime]` (event code → expiration),
populated per cycle by the player's `_fetch_world_state` from
`get_all_active_events`. It sits beside `cooldown_expires` as live world state.
The planner consumes the snapshot; per-cycle replanning keeps it current. The
planner does not simulate event expiry within a plan — the snapshot is treated
as fixed for the planning pass, and the per-cycle refetch plus the execute-time
backstop (below) handle drift.

`WorldState.from_character_schema` and the player's state construction are
updated to thread `active_events` through (defaulting to empty when not
supplied, mirroring how `bank_items`/`pending_items` are threaded).

### 3. NpcSellAction / NpcBuyAction — availability gate in `is_applicable`

Both actions get the same gate (shared root cause; identical plumbing):

- If `game_data.is_event_npc(self.npc_code)`:
  - applicable only if `self.npc_code`'s event is present in
    `state.active_events`, **and**
  - `expiration - now > estimated_travel_seconds + margin`, where travel is the
    Manhattan distance from `(state.x, state.y)` to `npc_location` times the
    per-move cost the action already uses. This prevents committing to a walk
    that cannot finish before the window closes.
- If the NPC is not an event NPC: behavior unchanged.

`execute` is unchanged and retains its role as the race backstop: if the event
expires between planning and arrival, the sell/buy returns 598, which is already
caught and replanned.

### 4. "Seize active windows" — priority

In the `SellInventory` goal, when a profitable event merchant is active and
reachable before expiry and the character holds inventory that merchant buys,
raise the goal/action priority so Robby opportunistically dumps sellable stock
during the rare window. v1 uses a fixed, sensible boost. A learnable boost
magnitude is explicitly deferred (YAGNI).

The analogous buy side is not given a priority boost in v1 — buying is
opportunity-driven by other goals; only the availability gate (item 3) applies
to `NpcBuyAction`.

## Out of scope (v1)

- Waiting/idling for a future spawn (the ~25 h recurrence makes waiting
  pointless for low-value sells).
- Learnable wait budgets or learnable priority-boost magnitude.

## Testing

Success criteria per project standard: 0 errors, 0 warnings, 0 skipped,
100% coverage. All tests use the existing suite under `tests/`.

- `GameData._load_events` builds `_event_npc_spawns` / `_event_npc_codes` from a
  stubbed catalog response containing npc-content and non-npc events.
- `npc_location` fallback: returns static-scan location when present; returns
  event spawn tile for an event-only NPC; returns None for unknown.
- `is_event_npc` true/false.
- `NpcSellAction.is_applicable` / `NpcBuyAction.is_applicable`:
  - event NPC, event active, reachable before expiry → True
  - event NPC, event not active → False
  - event NPC, active but `expiration` too soon for travel → False
  - non-event NPC → unchanged (existing behavior preserved)
- Player loop populates `WorldState.active_events` from a stubbed
  `get_all_active_events`.
- `SellInventory` priority boost fires only when a reachable active merchant
  matches sellable inventory; no boost when no merchant active.

## Files touched

- `src/artifactsmmo_cli/ai/game_data.py` — `_load_events`, registry fields,
  `is_event_npc`, `npc_location` fallback.
- `src/artifactsmmo_cli/ai/world_state.py` — `active_events` field + threading.
- `src/artifactsmmo_cli/ai/player.py` — fetch active events per cycle into
  WorldState; SellInventory priority context.
- `src/artifactsmmo_cli/ai/actions/npc_sell.py` — `is_applicable` event gate.
- `src/artifactsmmo_cli/ai/actions/npc.py` (`NpcBuyAction`) — `is_applicable`
  event gate.
- `src/artifactsmmo_cli/ai/goals/sell_inventory.py` — priority boost for active
  reachable merchants.
- `tests/` — coverage for all of the above.

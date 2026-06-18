# PLAN #4: event content exploitation

**Priority:** 4. **Status:** planned.

## Problem

16 events exist. The bot models the TIMING surface — `event_window` (proven) gates
NpcSell/NpcBuy on active gold-merchant events ([[project_event_merchants]]). But
events also spawn TIMED content: event-only monsters, resources, maps, and rare
drops that exist ONLY while the event is active. Unclear the bot exploits these
opportunity windows (a rare event resource/monster is available now, gone later).

## Open questions (verify FIRST — read-only)
1. What do the 16 events contain (monster spawns, resource spawns, map openings, NPC
   merchants)? Dump the event collection + each event's content/effects.
2. Does the planner SEE event-spawned monsters/resources (are their locations/drops in
   GameData when the event is active, via the same accessors), or are they invisible?
3. Does any needed material (objective/recipe input) come ONLY from an event monster/
   resource? If so, the bot would freeze on it outside the event window (a liveness
   gap) or miss it.

## Approach (after verification)
- If event content flows through the existing location/monster/resource accessors
  when active, the planner already reaches it — the gap is PRIORITIZATION: the bot
  should opportunistically pursue a time-limited event drop it needs BEFORE the window
  closes (an urgency/expiry weighting on event-sourced targets). A small priority
  boost gated on `event_window`.
- If event content is INVISIBLE to the planner (not loaded), the fix is loading event
  spawns into GameData while active (a data gap, larger).
- Compose with #5 (event bosses) and the event-merchant gating already in place.

## Risk / sizing
DISCOVERY-bound (Q1/Q2). Likely a prioritization tweak (cheap) if event content is
already visible; a data-loading feature (larger) if not. DEFER detailed design until
the event surface is dumped.

---

## VERIFIED (2026-06-17) — event content is INVISIBLE; building the visibility slice

Live dump: 16 events = 5 NPC merchants (already gated via EventWindow), 9 event
monsters (lvl 20-48), 2 event resources (magic_tree→magic_wood, strange_rocks→
strange_ore). `_build_events` (game_data.py:1218) `continue`s on non-NPC content, so
event monster/resource map tiles never reach `_monster_locations`/`_resource_locations`.
Monster/resource STATS + DROPS are already loaded (get_all_monsters / get_all_resources
include event content) — only LOCATIONS are missing. Event materials gate a large swath
of lvl-20-50 gear. See [[project_roadmap4_discovery]].

### Design (visibility slice; user-approved 2026-06-17) — NO Lean change
The proven cores (`_producible` in tiers/strategy, gathering goal) consume game_data
LOCATION ACCESSORS as input. Make those accessors return event tiles when the event is
active → every downstream path (factory FightAction/GatherAction gen, `_producible`,
gathering narrowing) works transparently. Gating = a per-cycle `active_event_codes`
overlay on GameData. The algorithms are unchanged → diff/mutation parity holds with no
Lean edit (defaults empty ⇒ existing tests unaffected).

Steps:
1. `_build_events`: ALSO handle MONSTER + RESOURCE content. Store
   `world.event_monster_locations: dict[monster_code, list[(x,y)]]`,
   `world.event_resource_locations: dict[resource_code, list[(x,y)]]`, and
   `world.event_code_of_content: dict[content_code, event_code]`. (Event fields live on
   `self.world` / LocationCatalog, mirroring `_event_npc_spawns`.)
2. GameData per-cycle overlay: `active_event_codes: set[str]` (default empty) + setter.
   Accessors `monster_locations`, `all_monster_locations`, `resource_locations`,
   `all_resource_locations` merge event tiles whose `event_code_of_content[code]` is in
   `active_event_codes`.
3. Player loop (`_build_actions` / cycle start): set `game_data.active_event_codes =
   set(state.active_events)` before planning.
4. Tests: event monster/resource visible iff active; factory emits event Fight/Gather
   when active; `_producible(event_gated_item)` True iff active. Mutation anchor: "ignore
   active_event_codes (always include / never include event content)" killed by tests.

DEFERRED to a follow-up (urgency slice): expiry-weighting to race the window before it
closes; without it the bot pursues event content opportunistically and re-plans if the
event expires mid-pursuit (acceptable for the visibility slice).

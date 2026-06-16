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

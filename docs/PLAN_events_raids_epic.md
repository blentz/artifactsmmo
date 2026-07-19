# EPIC: events & raids as first-class planner content

Status: **SCOPED, not started.** Opened 2026-07-19 after the potion-recalibration
work hit `l48_band_adequate`.
Blocks: `docs/PLAN_potion_combat_justification.md` reaching a green gate.

## Correction first — the premise most of us were carrying is STALE

"The planner cannot fight event monsters" is **no longer true**. That gap was
closed; `docs/PLAN_engagement_expansion.md:5-9` records it explicitly ("P4
DISCOVERED ALREADY IMPLEMENTED … roadmap-4 memory was stale"). Concretely,
`game_data.monster_locations`/`resource_locations` (`game_data.py:566-583`) and
`all_monster_locations`/`all_resource_locations` (`:1111-1132`) merge active event
tiles, and `actions/factory.py:74-79` emits `FightAction`/`GatherAction` from those
merged maps. Event content IS plannable while its event is active.

Do not re-litigate that. The residual gaps are different and narrower.

## Why this blocks the potion work — the L48 evidence

`l48_band_adequate` fails `assert report.goals_tried` once `CRAFT_POTIONS` stops
firing on a bare stock deficit. The scenario is documented as having no winnable
monster in the L47-50 window (`test_no_deadlock.py:15,192`).

The bundle explains why. `tests/test_ai/scenarios/fixtures/gamedata_bundle.json`
holds 58 monsters, of which **14 have no static map tile**: `bandit_lizard,
corrupted_ogre, corrupted_owlbear, cultist_emperor, demon, duskworm, echoless_bat,
efreet_sultan, full_moon_vampire, grimlet, pixie, red_dragon, sea_marauder,
sonnengott`. Twelve are event-only; `pixie` and `sonnengott` are raid bosses.
`test_band_liveness.py:154` names `duskworm` as an L48-window monster — and
`duskworm` is in that no-tile list.

So the L48 wall is **not** a potion problem and not a difficulty problem. The
L47-50 fight window in this bundle is event-and-raid-only content. A character at
L48 has nothing permanent to fight, which is exactly what the scenario models.
Potion busywork was the only goal it ever tried, and removing that busywork
exposed the wall rather than creating it.

`assert report.goals_tried` must NOT be weakened to unblock this — it is a
vacuousness guard; without it the loop below passes trivially on an empty list.

## Upstream mechanics (fetched 2026-07-19)

### Raids — https://docs.artifactsmmo.com/concepts/raids
* **Scheduled and therefore PREDICTABLE**: `weekdays`, `start_hour_utc`,
  `duration_hours`, plus `next_start_at` for the next opening. Unlike events, a
  raid can be planned toward BEFORE it opens.
* **Participation is the normal fight action**: move "to a map whose content type
  is `raid` while the raid is active, then use the normal fight action." No
  dedicated join endpoint. This confirms the assumption
  `docs/PLAN_multilayer_nav.md:100-135` made from map data alone.
* **Winning does not require killing the boss**: "You win a raid fight by either
  surviving all 100 turns or finishing the boss." This is the load-bearing fact —
  it is why `is_winnable` is the WRONG gate and why that plan already proposed a
  survivability gate instead. Upstream now confirms it.
* Shared `active_instance.remaining_hp` across participants; the raid "succeeds as
  soon as its shared HP reaches zero. It fails if the duration expires first."
* Up to three of your own characters may fight on the same raid map.
* **Rewards land in pending items**: "distributed after the raid ends and are sent
  to your pending items" — so the existing `ClaimPendingItemAction` is the
  collection path; no new reward plumbing. Two reward classes: `damage_rewards`
  (per damage threshold, capped) and `leaderboard` (rank-based).
* API: `GET /raids`, `GET /raids/{code}`, `GET /raids/{code}/leaderboard`; fields
  `active_instance.remaining_hp`, `status`, `participant_count`, `latest_instance`.
* **NOT documented: death semantics.** Still requires a live probe or a
  conservative assumption.

### Events — https://docs.artifactsmmo.com/concepts/events
* **Stochastic, not scheduled**: each event has a spawn rate giving "a 1/rate
  chance per minute of appearing", with no advance announcement. Events cannot be
  planned toward before they appear — only raced once active.
* **The window is exactly knowable once active**: `expiration` (ISO 8601) and
  `created_at`. `GET /events` is the catalog (spawn rate + duration), `GET
  /events/active` the live set.
* Content types `monster`, `resource`, `npc`; `maps` lists candidate host tiles.
* Active events **replace** map data; the response carries both `map` and
  `previous_map`.

**Design consequence:** raids are deterministic and worth planning toward; events
are opportunistic and worth *racing*. They need different treatment, not one shared
"temporary content" abstraction.

## The four real gaps

### G1 — no expiry/urgency weighting (events)
`WorldState.active_events` carries expirations, but nothing outside
`event_availability.py` reads them: grepping `expir` across `ai/goals/` and
`ai/tiers/` returns **zero hits**. The planner will happily commit to a 40-step
chain through content that expires in 90 seconds. Deferred at
`docs/PLAN_event_content.md:73-75`.

The one mature precedent to generalise is `event_availability.py:1-47`
(`event_npc_tradeable`), which already gates event NPCs on "enough window left to
walk there" via `EVENT_TRAVEL_SECONDS_PER_TILE = 5.0` and
`EVENT_ARRIVAL_MARGIN_SECONDS = 10.0`. That is the right shape; it just needs to
cover monsters and resources, and to reach plan LENGTH rather than travel alone.

### G2 — `combat_target_monsters` has no spawn gate at all
`ai/combat_targets.py:35-37` filters only on `monster_levels` + `is_winnable`, and
`monster_levels` (`game_data.py:1100-1103`) is the **full 58-monster catalog,
including event-only monsters and raid bosses**. So it can return `pixie` or
`sonnengott` — monsters with no tile, unreachable by any action.

**This one directly corrupts the potion work.** `potion_supply.primary_combat_target`
(`potion_supply.py:29-31`) inherits it, so combat-justified potion stocking can
anchor on an unreachable raid boss. `inventory_caps.py:334` inherits it too.
Every other selection helper is event-aware; this is the single hole.

### G3 — `WorldState.raids` is silently dropped on every apply
`from_character_schema` defaults `raids=[]` (`world_state.py:219,290`), and the
~20 action sites that rebuild state pass `active_events=` but never `raids=`
(`actions/movement.py:54`, `gathering.py:164`, `transition.py:68`, `rest.py:43`,
`teleport.py:74`, `consumable.py:115`, `withdraw_item.py:107`,
`task_exchange.py:86`, …). Only `player.py:1267` ever sets it. The visibility data
evaporates after the first executed action, so no planner consumer could work even
if one existed.

### G4 — raids are structurally unplannable
Raid bosses have no map tile of type `monster`, so `all_monster_locations` never
contains them and `factory.py:74` never emits a `FightAction`. Raid tiles ARE
ingested (`game_data.py:1406-1409` → `world.raid_locations`), and live status is
fetched in the player loop (`player.py:1155-1197`), but `raid_info.py:1` and
`world_state.py:207` both say "visibility only". `location_catalog.py:119-121`
describes a participation gate that **does not exist in code**. There is no raid
catalog in GameData and no `raids` key in the cache bundle; `ScenarioCharacter` has
no `raids` field, so scenarios cannot even declare an active raid.

## Proposed phases

**P0 — G2 spawn gate (small, unblocks the potion epic).** Give
`combat_target_monsters` a spawn gate so it cannot return unreachable monsters.
Verify the blast radius on `primary_combat_target` and `inventory_caps` first;
this changes what the potion predicate anchors on and is the cheapest real fix
here. Likely resolves part of `l48_band_adequate` honestly, by making "no winnable
monster" mean "no *reachable* winnable monster".

**P1 — G3 raid preservation.** Thread `raids=` through every action's state
rebuild, mirroring how `active_events=` is already threaded. Mechanical, ~20 sites,
needs a regression test asserting raids survive an apply (the existing
`test_active_events_preserved.py` is the template).

**P2 — G1 expiry weighting.** Generalise `event_availability`'s window arithmetic
beyond NPCs, and make plan length — not just travel — the thing checked against the
remaining window. This is where "race the event" becomes real behavior.

**P3 — raid catalog + scenario support.** `GET /raids` into GameData with the
schedule fields (`weekdays`, `start_hour_utc`, `duration_hours`, `next_start_at`),
a `raids` key in the cache bundle, and a `raids` field on `ScenarioCharacter` so
scenarios can declare an active raid. Prerequisite for any planning against raids.

**P4 — `ParticipateRaid`.** The design already exists at
`docs/PLAN_multilayer_nav.md:100-135` and its central assumption (fight-at-tile) is
now CONFIRMED upstream, as is the survive-100-turns win condition that motivates a
survivability gate instead of `is_winnable`. Emit a `FightAction` at the raid tile
while the window is active. Rewards need no new machinery — they arrive as pending
items, which `ClaimPendingItemAction` already collects.

**P5 — L48 disposition. DECIDED (user, 2026-07-19): make the raid a declared
PRECONDITION and test BOTH polarities.**

`l48_band_adequate` must become a pair:

* **no raid active** → the bot provably CANNOT plan. `Wait` is the correct
  outcome, and the scenario documents the wall honestly instead of hiding it
  behind potion busywork.
* **raid active** → the bot plans raid participation.

This is the right shape because it makes the wall a *property of the world state*
rather than an unexplained dead end, and it is non-vacuous in both directions: the
negative case would pass trivially today, so only the paired positive case proves
the planner actually gained the capability.

Prerequisites, in order: **P3** (`ScenarioCharacter` has no `raids` field, so a
scenario cannot declare an active raid at all today) and **P4** (nothing emits a
`FightAction` at a raid tile). Until both land, the negative half is all that can
be written, and writing it alone would be the vacuous half.

Note P0 did NOT unblock this, contrary to my initial guess: the scenario already
had no winnable monster by construction, so gating unreachable ones changed
nothing there. The blocker is genuinely the missing raid capability.

## Open questions

1. **Raid death semantics are undocumented.** What happens to the character on a
   raid loss? The 2026-07-05 live probe was aborted
   (`docs/PLAN_multilayer_nav.md:128-135`) and this is the one fact the concept
   docs do not supply. Until observed, P4 must assume the worst case.
2. **Is surviving 100 turns actually plannable?** The win condition is
   survivability, not a kill — the planner has no notion of "survive N turns"
   today. `predict_win` answers a different question.
3. **Does a raid worth-gate belong in the arbiter ladder or as discretionary?**
   `PLAN_multilayer_nav.md` proposed DISCRETIONARY with a 10k-damage/1-coin worth
   gate and no new `MeansKind` (which keeps the proven ladder intact).
4. **Should P0's spawn gate exclude event monsters too, or only unreachable ones?**
   Excluding active-event monsters would contradict the P4 visibility work that
   deliberately made them fightable. The gate should key on *reachability*
   (has a tile right now), not on *being event content*.

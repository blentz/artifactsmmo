# PLAN — Multi-layer navigation (P5b) + ParticipateRaid (P6 goal)

**Status: DESIGNED 2026-07-05. Two bricks, ordered. P5b unblocks 4 bosses
(lich, goblin_priestess underground; rosenblood, sandwhisper_empress interior)
and god_of_the_sun's raid tiles; ParticipateRaid works for enchanted_fairy
(overworld) WITHOUT P5b.**

## P5b: multi-layer navigation

**DATA LAYER LANDED (2026-07-05):** all-layer map fetch; layered structures
(`layered_content` (x,y,layer) per code, `restricted_tiles`,
`transition_edges` with parsed (code, operator, value) conditions);
LEGACY indexes deliberately overworld-only until the movement brick, so no
plan can route to an unreachable tile. Live-verified: all 4 layer-locked
bosses + god_of_the_sun tiles in layered data, fairy tile restricted=True,
entry edge = (-4,8,overworld,(('gold','cost',5000),)). CACHE_VERSION 4.
**MOVEMENT BRICK LANDED (2026-07-05):** WorldState.layer;
GameData.region_of/state_region (restricted flood-fill components); base
Action.travel_region contract with ONE central planner gate;
MapTransitionAction = real region-crossing edge (folds portal walk, models
gold-cost conditions only — others inapplicable, never default-pass;
deterministic teleport apply); factory emits 30 edges + 38 off-region
Fight/Gather actions. GOAP chains Transition->Fight cross-region with zero
goal-layer changes (pinned by test). REMAINING (deliberate): goal layers
still target legacy overworld indexes — off-region content becomes
GOAL-DRIVEN when consumers migrate to layered_locations (next); dryad/
enchanted_mushroom + 4 bosses reachable the moment a goal asks for them.
**REGION-SOUNDNESS BRICK LANDED (2026-07-05):** docs pin the semantics
("movement uses A* pathfinding ... bypassing blocked maps") — blocked
tiles PARTITION a layer, so region identity is now the 4-adjacency
component of walkable tiles (spawn component keeps the label
"overworld"; others anchor-labelled `layer:x,y`). This exposed and fixed
three bugs: (1) the five standard-access key pockets (Lich Tomb,
priestess hideout, Sonnengott region, Rosenblood/Empress houses) were
labelled plain layer regions — the planner believed it could walk to
lich once underground, no key; (2) `conditional` access was never
ingested — the tasks_trader tile (achievement `tasks_farmer`) sat in the
legacy NPC index unconditionally (account achievements now fetched at
load, page "achievements", CACHE_VERSION 5; unmet-conditional and
restricted tiles are excluded from ALL legacy indexes — this also fixed
(3) dryad/mushroom/fairy-raid restricted overworld tiles living in
legacy indexes with travel_region "overworld", a guaranteed HTTP 596).
MapTransitionAction now models item-`cost` (consumed from inventory)
and `has_item` (inventory or equipped, not consumed) alongside gold —
all five pockets are genuinely routable once the key is held; anything
else (achievement_unlocked, stat comparisons) stays inapplicable.
`monster_spawn_known` counts a layered tile ONLY when its region is in
`reachable_regions()` (BFS over cost/has_item edges) — all 4 bosses
stay spawn-known, now honestly. Live-verified: 415 walkable tiles, 15
reachable regions, all 5 pockets distinct regions + reachable,
tasks_farmer NOT completed on the account → tasks_trader correctly
unrouted (NpcBuy/NpcSell already tolerate location=None). Known
approximation: reachable_regions does not check key OBTAINABILITY
(a key dropping only inside its own pocket would over-claim; live data
has none). Full gate.sh not run in-session (bot live — serialize rule);
run before merge.

Facts (live-verified 2026-07-05):
* Map layers: overworld / underground / interior. Loader fetches OVERWORLD
  only (`game_data.py` `_fetch_maps`, `layer=MapLayer.OVERWORLD`).
* Transition tiles carry full destinations:
  `tile.transition = {map_id, x, y, layer, conditions[]}` (e.g. the
  lavaunderground tiles gating sonnengott have condition codes).
  Loader currently records only a `transition_tiles` set (positions).
* `MapTransitionAction` exists but `apply()` is identity (planner-blind) —
  it can never appear mid-plan because it changes nothing in sim.
* `WorldState` has x/y only; character schema presumably reports layer
  (VERIFY field name on CharacterSchema before building).

Design:
1. **Data**: fetch all three layers; every location index becomes
   layer-qualified — the cheap representation is `(x, y, layer)` tuples in
   the EXISTING location lists (monster/resource/npc/bank/workshop/raid),
   with `layer` defaulting to overworld. Transitions become edges:
   `transition_edges: dict[(x, y, layer) -> (x, y, layer, conditions)]`.
   CACHE_VERSION bump.
2. **State**: `WorldState.layer: str = "overworld"` from the character
   schema. `nearest_or_error` and every distance computation become
   layer-aware: same-layer → manhattan as today; cross-layer → through the
   nearest transition edge (distance = d(char→portal) + 1 + d(exit→target),
   minimized over portals; precompute per layer-pair, there are ~3).
3. **Actions**: `MapTransitionAction.apply` teleports to the recorded edge
   destination (deterministic — the data is in the map schema); applicability
   = standing on a transition tile whose conditions the state satisfies
   (condition codes: achievements/items — start with unconditional edges,
   gate conditioned ones behind explicit checks, NEVER default-pass).
   Fight/Gather actions on other layers become plannable because their
   locations carry layers and movement folds the portal cost.
4. **Tests**: cross-layer plan (fight lich underground from overworld spawn:
   move→transition→move→fight); condition-gated edge NOT taken; distance
   minimization over two portals.
5. **Risk**: touching `nearest_or_error` ripples through every action's
   cost/apply. Keep the signature (locations stay `(x, y)` pairs on the
   SAME layer as viewed by callers?) — NO: bite the tuple change once,
   mechanically, with mypy strict as the net. No Lean ripple (coords are
   not modeled in the liveness State).

## PROBE RESULTS (2026-07-05 02:00-02:10, active window)

* Raid tile (-4,10) map 769: `access.type='restricted'`; move → HTTP 596
  "map is blocked", from afar AND from the adjacent tile.
* Docs (concepts/maps_and_movement): restricted maps form REGIONS —
  "only accessible from other restricted maps"; entry via transitions.
* Full map sweep: the Enchanted Forest is a 5-tile restricted region
  (dryad ×2, enchanted_mushroom ×2, the raid tile), with EXACTLY ONE entry:
  a transition at (-4,9) overworld → map 667 (-4,8) with condition
  `{code: gold, operator: cost, value: 5000}` — a 5000-gold entry fee.
  Then walk within the region to the raid tile.
* Docs (concepts/raids): participation = normal fight action at the raid
  tile; up to 3 own characters; rewards AUTO-distributed to PENDING ITEMS
  per damage_per_reward (ClaimPendingItemAction already handles those).
* Probe HALTED honestly: Robby holds 1099 + 1000 bank = 2099 gold < 5000.
  Fight-at-tile semantics remain UNOBSERVED (asserted from docs).

DESIGN CONSEQUENCES:
* **P5b is not just layers — it is ACCESS REGIONS.** The movement graph
  partitions by (layer, access-region); transitions are the only edges
  between partitions and carry CONDITIONS INCLUDING COSTS (gold 5000 here;
  achievement/item conditions elsewhere). `MapTransitionAction` needs
  cost-aware applicability (gold ≥ fee) and apply (gold -= fee, position :=
  destination).
* **ParticipateRaid worth gate gains the entry fee**: expected coin value
  must beat 5000 gold + opportunity cost, amortized over the window; the
  region persists (one fee per visit? UNKNOWN — probe when funded).
* Dryads + enchanted_mushroom are restricted-region content — currently
  invisible sources for the same reason; the access-region work unlocks
  them with the raid.

## P6: ParticipateRaid goal (enchanted_fairy first)

Facts: raid = static map content (`raid_location_tiles`), boss engaged by
fighting AT the tile during the window (`WorldState.active_raids`); rewards
are damage-threshold coins (10k dmg → 1 enchanted_coin, cap 25/window);
raid coins fund beastmaster purchases (enchanted_fabric — 496-item breadth).
Boss stats are in the monster catalog (`pixie` L40, type raid_boss).

Design (deliberate departures, each documented):
* **is_winnable bypass**: predict_win against a 600k shared pool is
  meaningless (nobody "wins"); participation is throughput. The goal gates
  on SURVIVABILITY instead: expected hp loss per engagement (predict_win's
  per-round damage math, reused — not the win verdict) must leave the
  character above the CRITICAL_HP floor with rest cycles between attempts.
* **Worth gate**: expected damage over the remaining window ≥ 1 coin
  threshold (10k). Expected per-fight damage from the predict_win damage
  model × fights-per-window (cooldown-bounded). Below the bar the goal never
  fires (honest: an L10 character contributes nothing and dies).
* **Arbiter integration**: NO new MeansKind (ladder/DecideKey/E-tower row
  ripple across 4 proof towers — the EquipOwnedGoal lesson). Ride the
  DISCRETIONARY tier as a goal candidate gated on (raid active ∧ tile known
  ∧ survivable ∧ worth-positive); discretionary already yields to every
  guard and objective step, which is the right priority for a timed bonus.
* **Execution**: FightAction at the raid tile (server fights the raid boss
  there); rest between engagements via existing hp guards; stop at window
  end or coin cap.
* **Formal**: none required for liveness (discretionary tail is already
  unreachable below 50 in the towers — raids never block progression);
  coin accounting joins the currency-buy closure as a source only after a
  LIVE probe confirms fight-at-tile semantics and reward crediting.
* **LIVE PROBE FIRST** (blocking): one manual fight at (-4,10) during a
  window with a throwaway-strong char state — confirm the fight response
  (raid damage vs normal combat), death semantics, and coin crediting.
  Server semantics are ASSERTED from map data, not yet observed.
  2026-07-05 02:00 attempt ABORTED: the live bot (play Robby --trace,
  started 18:06 — predates the day's builds) owns the character; probing
  would fight over cooldowns. Run the probe at the next bot pause —
  which is ALSO the moment to restart it (picks up: targeted rare-drop
  gathers, currency-chain producibility, adequacy trace observable,
  CACHE_VERSION 3) and to run the full gate.sh (mutation battery has not
  covered today's Python changes; serialize-gate-runs forbids running it
  beside the live bot).

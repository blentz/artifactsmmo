# PLAN — Multi-layer navigation (P5b) + ParticipateRaid (P6 goal)

**Status: DESIGNED 2026-07-05. Two bricks, ordered. P5b unblocks 4 bosses
(lich, goblin_priestess underground; rosenblood, sandwhisper_empress interior)
and god_of_the_sun's raid tiles; ParticipateRaid works for enchanted_fairy
(overworld) WITHOUT P5b.**

## P5b: multi-layer navigation

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

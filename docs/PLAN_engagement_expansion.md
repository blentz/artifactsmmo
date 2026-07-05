# PLAN — Engagement expansion: events, elites, bosses, raids (cross the L38 wall)

**Status: P1 DONE 836e4045 (wall FALLS); F1-v2 DONE 7b61681f (frontier ∅ kernel);
P2 NON-GAP; E-tower capstone DONE 31c78262 (ai_reaches_fifty_geared).
P4 DISCOVERED ALREADY IMPLEMENTED — active-event fetch per cycle (player.py),
active_event_codes overlay before action-building, factory merges event
monster/resource tiles, event-merchant EventWindow gating (roadmap-4 memory
was stale). P3 partial DONE (this commit): state-aware leaf `_producible`
and `_producible_by_self` now count NPC purchases paid in a currency the
character can produce (gatherable / winnable-drop / task-earnable), one
level deep — tailor leathers @ hides, archaeologist @ shards, cultist @
corrupted_gem; unlocated vendors honestly excluded (sorceress). VERIFIED
(2026-07-05): currency FUNDING already works end-to-end — GOAP natively
chains Fight×N (drop currency) → NpcBuy (probe: sheep→wool×3→cloth), and
GatherMaterialsGoal already emits NpcBuy for closure leaves (C4 Task 1);
P5 drop-hunting already wired (select_monster_for_drop narrowing + event
overlay). REMAINING GAPS, precisely:
* **P5b multi-layer navigation**: lich/goblin_priestess (underground),
  rosenblood/sandwhisper_empress (interior) have tiles on layers the map
  loader never fetches (OVERWORLD only); MapTransitionAction exists but is
  planner-blind (apply=identity, no layer in WorldState). Design-first
  brick: layer in state, all-layer map ingest, transition destinations
  (tile.transition carries map_id/x/y/layer + conditions).
* **P6 raid participation**: raid tiles are STATIC map content
  (type='raid': enchanted_fairy OVERWORLD (-4,10) — playable without P5b;
  god_of_the_sun underground, needs P5b). DATA LAYER LANDED: loader
  ingests RAID content, `raid_location_tiles(code)` accessor,
  CACHE_VERSION 3. Live-verified DURING an active window: the raid boss
  never appears as a monster tile — participation = fighting at the raid
  tile while `WorldState.active_raids` has the window open. NEXT: a
  ParticipateRaid goal — bypasses the is_winnable veto DELIBERATELY
  (600k shared HP pool: contribution-throughput, not solo-kill;
  damage-threshold coin rewards fund beastmaster buys), survivability-
  guarded (hp floor + rest cycles), window-scheduled.**
User mandate: by level 38 the player must engage events, elites, bosses, raids,
raid bosses — expand production capability AND the formal model.

## What the live API says (2026-07-04 sweep — the wall dissolves into data gaps)

The C1b/C2 level-38 wall (acquirable-only progression hard-caps at 38) traced
to THREE production data gaps plus missing engagement behaviours, NOT to
genuinely unobtainable gear:

1. **Resource multi-drops dropped.** `GameData._resource_drops` keeps ONE item
   per resource; the API multi-drops: gem stones (topaz/emerald/ruby/sapphire
   @1/200 from COPPER rocks L1; @1/100 from gold/mithril), diamond_stone
   (strange_rocks L35), saps/algae/pearls/coconut. Gems — a whole jewelry
   ingredient family — are invisible to the planner today.
2. **Crafting recipes incomplete.** obsidian_helmet, gold_boots, ancient_jean,
   ancestral_talisman, cursed_sceptre, dreadful_shield ALL have API `craft`
   entries (gearcrafting/jewelry/weapon 30-35) absent from the 321 loaded
   recipes. Their ingredients (obsidian_bar, magical_plank, cursed_book,
   vampire_blood/tooth, imp_tail, goblin_tooth/foot, lizard_skin/eye,
   owlbear_hair, cut gems, magical_cure, …) chain to catalog event-monster
   drops, event resources, and NPC buys. Find and fix the recipe-loader
   filter.
3. **NPC currency-purchase economy unmodeled** (npc-purchase memory Phase 2-4
   never done). Live listings: tailor sells cloth/hard_leather/vermin_leather/
   snakeskin FOR hides (wool/cowhide/rat_hide/snake_hide — ordinary monster
   drops!); tasks_trader sells astralyte_crystal/jasper_crystal/magical_cure/
   prime_fabric for tasks_coin; rune_vendor sells lifesteal_rune for 20k gold;
   archaeologist sells life_crystal/book_from_hell for shard/page drops;
   cultist_wizard sells corrupted_crown/diabolic_elixir for corrupted_gem
   (event-monster drops); sorceress fire_crystal @ fire_dust; beastmaster
   enchanted_fabric @ enchanted_coin (RAID reward); sandwhisper_trader
   greater_lifesteal_rune @ sandwhisper_coin.
4. **Raids**: 2 scheduled raids (enchanted_fairy→pixie Tue/Thu/Sat 21:00 UTC
   12h; god_of_the_sun→sonnengott Mon/Wed/Fri) with damage-threshold coin
   rewards feeding the beastmaster shop. Server-scheduled — citable as a
   timed-availability axiom, like LIV-001.
5. **Events**: 19 (monster/resource/NPC-merchant spawns) with rate/duration/
   cooldown data. Event monsters ARE in the 58-monster catalog with drops.
6. Non-craft, non-NPC remainder: ring_of_the_adept, novice_guide,
   wooden_stick (achievement/starter rewards — endowment class, never
   progression-required going forward).

## Production bricks

* **P1: resource multi-drops.** Extend GameData resource loading to full drop
  lists (rates included); CACHE_VERSION bump (api-gaps memory); gather
  valuation/goals learn rare-drop sourcing (expected-gathers via rate, reuse
  learned-yield machinery). Unblocks gems from L1.
* **P2: full recipe load.** Locate the filter dropping the L30-35 event-
  ingredient recipes; load ALL API craft entries. Re-run acquirability probe —
  expected: obsidian/gold/ancient/ancestral/cursed/dreadful families close.
* **P3: currency-purchase economy** (npc-purchase Phase 2-4 revived): model
  buy-edges item ⟵ (currency, price, npc) with currency EARN chains (hides ⟵
  drops; tasks_coin ⟵ task loop; gold ⟵ sell/complete; corrupted_gem/
  page/shard ⟵ event-monster drops; raid coins ⟵ P6). Planner: BuyItem goals
  through currency accumulation (CurrencyFunding core exists — extend).
* **P4: event engagement.** Fix roadmap-4 (_build_events skips non-NPC):
  event monsters/resources become plannable targets when active; event-window
  scheduling via the proven EventWindow core; event-merchant buys gated on
  active event (event-merchants memory).
* **P5: elite/boss targeting.** Picker window [L-1, L+2] never targets
  drop-source elites/bosses deliberately; add drop-driven fight goals (gear
  ingredient needed → hunt its dropper) guarded by predict_win + the C0a/C0b
  xp cores (elites pay 1.4x — value core already exact).
* **P6: raid participation.** Scheduled raid windows (raid schedule data),
  travel + repeated boss engagement during the window, damage-reward coin
  accounting into P3's currency chains.

## Formal bricks

* **F1: acquirability closure v2.** Sources = multi-drop gather ∪ monster
  drops ∪ currency-buy edges (buy-edge closable iff its currency's earn chain
  closes). Snapshot gains resource_drop_lists + npc_item_listings + raid
  schedules; certificate pattern as C1b. EXPECTED RESULT: frontier ∅ or
  reduced to the endowment class — the L38 wall becomes crossable IN-MODEL.
* **F2: E-tower with event-window liveness.** Replace the bare
  `eventGearAvailable` hypothesis with a server-schedule axiom (cited like
  LIV-001: raids/events fire on documented schedules) driving a
  window-recurrence measure slot. Vacuity discipline: the axiom is satisfiable
  by the live schedule; no i.o.-fairness of the REFUSED shape (windows are
  server-clocked, not bot-scheduled).
* **F3: capstone.** `ai_reaches_fifty_engaged`: reach-50 with sources =
  closure-v2, modulo LIV-001 + the cited schedule axiom. Reach-38 stays
  unconditional on the old closure as the fallback theorem.

## Sequencing

P1 → P2 (data foundations; re-probe wall after each) → F1 (closure v2 +
frontier re-derivation) → P3/P4 (economy + events; runtime-activation checks
per the verify-runtime-activation feedback) → P5/P6 → F2/F3. Each brick lands
with gates green; live probes pinned to snapshots.

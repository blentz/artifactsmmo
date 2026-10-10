# PLAN: craft census fidelity — toward 321/321

USER 2026-10-10: "why is the census only 283/321? it should be 321/321." Then:
"yes, add event-active cells; fix both faults".

## Evidence (committed bundle, 2026-10-10)

`321 recipes, 1758 cells; PASS 283 (16%); nominal-at-skill PASS 52/321`, 0
PLANNER_BUG — so the gate was green. 283 is CELLS, not recipes: only 57/321
recipes PASS in any cell. Every FAIL was labelled a game limit, but two of the
labels came from a faulty instrument:

1. **Copper gear at every level.** `census_state` chose gear ONCE
   (`near_term_gear`) from a BARE character whose skills were all 1 but the
   cell's. Gear whose materials need a fight is "not attainable" for a bare
   character, so a level-30 census character wore `copper_dagger` and no
   body/leg/amulet armour, and could not beat cow (level 8), pig or wolf —
   while live characters beat cows from level 11 (2,755 wins in learning.db).
   Most of the 570 `combat_blocked` cells.
2. **Overworld-only leaf check.** `_has_located_gather_source` read
   `all_resource_locations` (overworld + events), so underground
   `gold_rocks` / `mithril_rocks` / `adamantite_rocks` looked unsourced and their
   recipes were blamed `event_gated`. Production's `resource_spawn_known`
   already counts all-layer tiles in a reachable region; `gold_bar` plans.

Probe with both fixed: PASS 283 → 530 cells, 57 → 109 recipes, nominal 52 →
96; five PLANNER_BUG cells exposed (`mushmush_jacket`, `snakeskin_legs_armor`),
`material_unreachable` 21 → 87 cells (unexplained yet).

Genuinely event-only leaves (16, 128 recipes): drops of demon, duskworm,
grimlet, efreet_sultan, bandit_lizard, cultist_emperor, sea_marauder,
full_moon_vampire, echoless_bat, solar_desert_scorpion, red_dragon; the
gemstone/timber merchants; the event resources strange_rocks, magic_tree.

## Design

1. `_has_located_gather_source(leaf)` asks `resource_spawn_known` of each
   resource dropping the leaf — the production predicate.
2. `census_state` gear is a FIXED POINT: wear the near-term pick, pick again,
   until nothing improves. Gear is chosen for a character whose skills are at
   its level (a character whose crafting kept pace); the PLANNING state keeps
   the cell's skills (the tested dimension).
3. Event-active cells (USER "add event-active cells"): `CraftCell.events`. For
   a recipe with a closure leaf whose only sources are event content, the
   census adds the same grid with those leaves' events active — the event
   codes of its event droppers, vendors and resources (`event_code_of_content`,
   `npc_event_code`), all at once: a recipe needing two event leaves banks one
   window's haul for the other's. The cell sets `WorldState.active_events` AND
   `GameData.active_event_codes` (what `seed_offline` does live) for its run
   and classification, and restores the world after. The event-free cells
   stay: they are the honest "not now" answer.
4. The summary gains `recipes PASS x/321` (a recipe passes when any of its
   cells does). Target: 321/321.

## Then

Work the exposed PLANNER_BUG / MATERIAL_UNREACHABLE / COMBAT_BLOCKED cells.

## Status (2026-10-10): built

As designed, plus two findings the corrected census exposed:

- **Purchase currency on the closure.** With the cow beatable, 5 cells turned
  PLANNER_BUG: `mushmush_jacket` plans `Fight(cow)` first, because the tailor
  sells its `hard_leather` for `cowhide`, and the verdict called the kill
  unrelated. The verdict's closure now carries the non-gold currency of every
  vendor selling a closure member (`_closure_item_set`); recipe LEAVES do not
  (`_closure_members`), since `_leaf_status` judges the purchase itself.
- **Racy axiom gate.** `check_axioms_safety.sh` used `echo | grep -q` under
  `pipefail`: `grep -q` exits at its first hit, the writer SIGPIPEs, and the
  `if` reads the hit as a miss. `GrindCycles` (citing the approved liveness
  axiom `xpToNextLevel`) sat in the safety scan from 70d93742 (2026-09-30) and
  passed that way. The safety audit now leaves what `LivenessAudit.lean` scans
  to the liveness gate (`proof_tags.liveness_audit_names`), and every such
  check (safety, liveness, no-sorry) reads a here-string.

Census: `321 recipes, 2418 cells; PASS 565 (23%); recipes PASS 114/321;
nominal-at-skill PASS 103/321; gaps: event_gated 660, combat_blocked 1078,
material_unreachable 87, crossing_unaffordable 27, grey_farm_suppressed 1,
planner_bug 0`. Census time 24 s -> 40 s (the gear fixed point, memoized per
level and event set).

## What stands between 114 and 321

207 recipes PASS in no cell:

| Set of gaps across the recipe's cells | Recipes |
|---|---|
| combat_blocked + event_gated (event-free EG, event-active CB) | 121 |
| combat_blocked only | 65 |
| material_unreachable (jasper/astralyte crystal, wooden_stick) | 12 (+5 with CB) |
| crossing_unaffordable (the census character has 0 gold) | 4 |

The combat blocks are PRODUCTION's verdict, not only the census's: the DROP
route (`obtain_model/drop_routes._fight_gates`) asks the stat-only
`is_winnable` at max HP — no consumables, no learned win rate. Live C3P0, in
nearly the census loadout, wins vampire 77/117 with a water boost; the drop
route says it cannot, so no craft needing `vampire_tooth` is plannable for it.
The census character also never gets the drop/event gear the live fleet wears
(`death_knight_sword`, `bandit_armor`, `skull_amulet`), because the fixed
point only adds gear whose sources it can already beat.

Next (needs a ruling): judge a drop fight's winnability with the cycle's
chosen consumable loadout (`best_loadout`) and the learned record, the way
the band target already does.

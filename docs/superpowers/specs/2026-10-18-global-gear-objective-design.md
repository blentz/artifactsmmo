# Global gear objective: delete the tier ladder

Status: APPROVED by user 2026-10-18

## 1. Why

### 1.1 The user's statement of the objective (verbatim, 2026-10-18)

> The primary calculation the character needs to be making is "what next action
> best facilitates advancement?" with an understanding that optimal gear is a
> prerequisite to optimal fights. It is a massive failure to optimize locally for
> current-gear instead of optimizing globally for the best gear achievable with
> optimal stats at current level. We're not at perfect efficiency until we can
> craft or obtain the best possible gear available at current level. Avoid local
> maximums in order to find the global maximum.

> Tier and rung and band are all metaphorical, not literal. The game logic does
> not need to determine these. If the AI is behaving correctly, these concepts are
> emergent behaviors.

> You keep prioritizing fighting over keeping gear up-to-date.

### 1.2 The live failure (Robby, 2026-10-18 15:53 UTC onward)

Robby reached level 41 and from then on emitted `Wait` every cycle (185+ cycles
and counting), interleaved only with `DrainBankJunk`. The chain:

1. `tier_ladder.ladder()` invents rungs from the distinct item levels
   (1, 5, 10, ..., 50). `band(tier)` assigns every CATALOGUE monster to a rung by
   its level. `tier_cleared` calls a rung cleared when every `normal_band` monster
   in it is winnable on bare gear.
2. `corrupted_ogre` is an event monster whose API `type` is `normal`. Robby cannot
   beat it, so rung 20 is "uncleared". `next_uncleared_tier` = 20.
3. `gear_target_tier = min(level_rung 40, uncleared 20) = 20`. The gear sheet
   (`gear_targets_with_blockers`) considers only items of level <= 20. Robby's
   worn gear (`slime_shield`, `hard_leather_helmet`, `hard_leather_pants`,
   `bandit_armor`) beats every candidate there except artifacts and the bag, so
   the sheet wants only `backpack`, `lich_race_trophy`, `lost_world_map`, all
   declined.
4. `band_combat_target` searches ONLY rung 20's band for an XP target. At level
   41 every monster there is grey (pays 0 XP), so `ctx.combat_monster = None`.
5. `IsThereACombatTarget` → `CanIClearMyTier` → `None` (the "wall"). The trunk
   `ReachCharLevel(50)` maps to no goal because `objective_step_goal` returns None
   for `ReachCharLevel` when `combat_monster is None`. Result: `Wait`.

Robby meanwhile sits at gearcrafting 23, jewelrycrafting 22, weaponcrafting 22
against level-40 recipes that need 40. The correct behaviour — climb those skills
and build level-40 gear — was never offered by any part of the walk.

### 1.3 The structural defect

Two design errors, both mine, both recurring:

- **Invented structure computed as fact.** Tier, rung and band are descriptions
  of how a well-behaved character looks from outside. Computing them turned them
  into rules the real data must fit (bosses, events, grey bands), and every misfit
  got a patch (`NON_FARMABLE_TYPES`, `_next_rung_above`, the spawn filter in
  `band_combat_target`, `dead_target_slots`, ...).
- **Gear subordinated to fights, and judged locally.** What gear to pursue is
  capped by which fights are already won (`gear_target_tier`), ranked against
  what is worn now (`value > _item_value(worn)`), scored on a monster-blind
  ruler (`pursuit_value` vs the catalog-median adversary), and the only
  fight-aware gear link (`combat_deficit.deficit_upgrade_target`) is a GREEDY
  walk FROM CURRENT GEAR toward the held task's monster. Each is a local
  maximum by construction.

## 2. The objective

### 2.1 Definitions (all read from game data; nothing invented)

- **Level-legal item**: an equippable whose `level <= state.level`.
- **Achievable item**: a level-legal item that has at least one supply route in
  the catalogue that this character can complete in principle:
  - a recipe whose materials are achievable and whose crafting skill can be
    climbed (any skill level up to `max_skill_level` is climbable — climbing is a
    cost, never a veto);
  - a resource drop (gather skill climbable, as above);
  - a monster drop where that monster is beatable by SOME loadout drawn from
    achievable items (see 2.3 — a fixed point, not current gear);
  - a permanent vendor, for gold or an achievable currency;
  - the task board (task-earned currency);
  - free copies of a fixed-supply item (`is_suppliable`'s existing rule).
  Event-only routes count only while the event is live (they are not "in
  principle" completable otherwise).
- **Advancement rate** `R(L, m)`: character XP per second farming monster `m`
  wearing loadout `L` — the existing `target_rate` / `xp_per_action` machinery
  (win odds, upkeep, rest time, wisdom, consumables), evaluated on `L` instead of
  on the worn gear. `m` ranges over monsters that spawn on a static tile or a
  live event tile, inside `FightAction`'s structural level gates, paying XP > 0.

### 2.2 The target

```
(L*, m*) = argmax over m, and over loadouts L of achievable items, of R(L, m)
```

`L*` is THE gear objective: the best gear achievable at the current level, chosen
for the fight it makes best. It is never capped by what is won today, never
compared against what is worn as a filter, and never chosen on a monster-blind
ruler. Per-monster loadout optimisation reuses `pick_loadout`'s per-slot argmax
for `Combat(m)`, but over the achievable catalogue instead of owned items.

Gathering tools follow the same rule for skill climbs: `T*(skill)` = the best
achievable tool for that skill (the existing `tool_value` axis), pursued when a
skill climb is on the critical path.

### 2.3 Achievability is a fixed point, not current gear

A drop route through monster `d` is achievable iff `d` is beatable by some loadout
of achievable items. Compute it as a monotone fixed point: start from items
achievable without any fight-gated drop, compute which monsters those loadouts
beat, add their drops, repeat until nothing changes. The catalogue is finite and
the set only grows, so it terminates. This is the global replacement for "can I
beat it with what I wear" (`is_attainable_now`'s drop routes) and for the greedy
deficit walk.

### 2.4 What the next action is

Each cycle:

1. If the worn loadout is `L*` (every slot holds its `L*` item, or one the
   per-slot argmax ranks equal): **fight `m*`**. This is the only path that
   grinds character XP as an end in itself.
2. Otherwise: the next action is the next step on the acquisition plan for the
   missing `L*` pieces. Ordering among missing pieces:
   - dependency first: a piece whose possession makes a drop monster beatable
     that another missing piece needs comes before that piece (it falls out of
     the fixed point's layering in 2.3);
   - otherwise, largest gain in `R` per second of acquisition time
     (`route_price` in seconds, skill climbs included).
   Acquisition time ORDERS the pieces; it never downgrades the target. A piece
   that needs 20 levels of gearcrafting is pursued (that is the grey wall the
   character must confront), not traded for a worse piece reachable sooner.
3. Fights happen inside step 2 only as acquisition steps (a drop, a task kill,
   gold) — the character still earns XP from them, but no fight is chosen for XP
   while `L*` is not held.

Level-ups, new events and new learned odds change the inputs; `(L*, m*)` is
recomputed every cycle from facts. Mid-acquisition commitment stays with the
existing intention machinery (`intention_progress`), not with any new latch.

### 2.5 Fleet: amortized skill progression (USER 2026-10-18)

> Fleet coordination is necessary to amortize skill progression to enable
> whole-fleet progress.

Every character computes its own `(L*, m*)`. The fleet then shares the cost of
the skills those targets need:

- **Fleet demand.** Each character publishes its missing `L*` pieces (and the
  materials of their recipes) to the existing demand board (`craft_demand`,
  `gather_demand`, `supply_claims`). Publishing is unconditional on the
  character's own skills: the request is for the item, not for a skill.
- **Amortized climb cost.** A crafting or gathering skill climb is paid ONCE
  by one character and serves every fleet piece gated by that skill. The cost a
  character's ordering (2.4 step 2) charges for a skill-gated piece is the
  cheapest of:
  - its own climb + craft, or
  - the fleet crafter's remaining climb divided across the fleet's demand
    that the climb unlocks, + the craft, + the bank transfer.
  This is the same `route_price` in seconds, with a sibling-supply route whose
  climb term is amortized over fleet demand.
- **Who climbs.** One crafter per skill wherever fleet demand for that skill is
  positive, chosen by least remaining climb seconds (the character already
  highest in that skill, ties by least other committed work). This reuses the
  role machinery (`role_selection.decide_role`, demand splitting, hysteresis,
  release-on-idle / release-on-unservable). Roles stay non-exclusive. The
  change is the demand that drives them: fleet `L*` demand replaces
  chosen-root-only demand.
- **The crafter's own objective.** For the crafter, climbing its role skill
  and crafting fleet pieces IS an acquisition step (2.4 step 2): fleet `L*`
  pieces count as missing pieces of a joint fleet objective, ordered by the
  same gain-per-second rule summed over the receiving characters. So a crafter
  is never pulled off its role to grind XP while the fleet has demand it
  serves (2.4 step 3 applied fleet-wide).
- **Delivery.** A crafted piece goes to the bank with a claim naming the
  recipient; the recipient's route is a withdraw. This uses the existing
  claim/batch flow (`supply_claims`, `SupplyBank`).

What emerges: specialists per skill, an even skill climb across the roster, and
the fleet's gear moving up together. None of that is computed.

### 2.6 Season 9 alignment

The Season 9 announcement (artifactsmmo.com/news/season-9, 2026-09-12) names
season 8's wall as crafting progression:

> As new content has been added over the past seasons, we have noticed that
> reaching the endgame and completing every achievement has become increasingly
> demanding. Crafting progression, in particular, could require too much
> repetitive work before players were able to access the latest content.

That is the wall this spec makes the character confront (2.4, decision 1) and
the fleet amortize (2.5). Season 9 (launch 2026-10-31 16:00 UTC, full reset)
changes the inputs, not the design:

- **+~20% crafting XP**: API data; it shortens every climb term in
  `route_price` with no code change.
- **Crafting tools** (cooking first; alchemist gloves gain a craft bonus): a
  percentage cut to craft duration, like gathering tools. They join `T*` (2.2)
  on a craft-duration axis and are themselves `L*`-style acquisition targets
  for the crafter that climbs that skill.
- **Altar favors** (+50% XP on one activity, +50% drops on one target, until
  00:00 UTC; turn-in XP = 25% of the level's requirement): live modifiers on
  `R` and on the seconds of a climb or a drop route while the favor is held.
  They are inputs to the same argmax, not a separate objective.
- **Full reset**: everything here must hold from level 1. Nothing in 2.1–2.5
  depends on a level range, which is the point of deleting the ladder.

### 2.7 What emerges (and must NOT be computed)

- "Grinding a band": `m*` moves up as `L*` improves and the level rises.
- "Gearing for a tier": `L*` jumps when a level-up makes new items level-legal.
- "The grey wall": a long skill climb on the acquisition plan.
- "Clearing a tier": nothing; no consumer needs it.

## 3. What is deleted or replaced

Call sites from an AST scan of `src/` (2026-10-18).

| Current | Role today | Replacement |
|---|---|---|
| `tiers/tier_ladder.py`: `ladder`, `tier_of_level`, `band`, `normal_band`, `NON_FARMABLE_TYPES` | invented rungs/bands | deleted |
| `tiers/tier_progress.py`: `tier_cleared`, `next_uncleared_tier`, `gear_target_tier` | rung-cleared gate; gear cap | deleted |
| `tiers/band_target.py`: `band_combat_target`, `BandTarget` | XP target search inside one band | `m*` (2.2); `target_rate` kept as `R` |
| `player._path_aligned_monster`, `_pick_winnable_monster`, `winnable_cascade` tiers 2/3, `combat_picker` window | three-tier farm-target cascade | `m*` when `L*` held; acquisition fights otherwise |
| `objective.gear_targets_with_blockers`, `near_term_gear`, `catalogue_best_gear`, `from_game_data().target_gear` (endgame BiS) | four gear sheets on two rulers | one: `L*` |
| `pursuit_value` / `equip_value` as the gear-PURSUIT ruler | monster-blind ranking | `R(L, m)`; `equip_value` survives only where a monster-free order is genuinely needed (delete-dominance), to be audited |
| `combat_deficit.deficit_upgrade_target`, `task_horizon.resolve_task_horizon` (gear verdict) | greedy walk from current gear | `L*(m)` minus held, for any `m` asked about |
| `decisions/root.py`: `IsAFightBlockingMe`, `WhichSlotClosesTheFight`, `IsMyGearBehindMyTier`, `WhichSlotIsFurthestBehind`, `IsThereACombatTarget`, `CanIClearMyTier`, `_target_rung`, `_tier_gap`, `_next_rung_above`, `_slot_order`'s tier key | the root walk | root = missing `L*` piece (ordered per 2.4) or `ReachCharLevel` via `m*` |
| `progression_tree_core.milestone_pure`, `TRUNK_CAP`, `BAND` | decade milestones as roots | deleted; the trunk goal is "fight `m*`" with no milestone level |
| `learning/projections.cheapest_path_to_level` (via `route.py`, `player.py`) | level-path projection | audit: keep only if it prices `m*`; else delete |

Kept unchanged: `pick_loadout` (per-slot argmax, reused on the achievable
catalogue), `best_loadout` (consumables), `ObtainModel` / `route_price` (supply
routes and seconds), `classify_target` / `IsThisTargetBlocked` (skill-gate →
`ReachSkillLevel`, material → its route), `is_suppliable`, task / fleet / orphan
skill roots and their rotation, all guards.

## 4. Formal and test surfaces

- Lean: `Formal/ProgressionTree.lean` (milestone), `Formal/WinnableCascade.lean`
  (three-tier cascade), entries in `Formal/Manifest.lean` / `Audit.lean`. Retire
  the theorems whose subject is deleted; add theorems for the new core:
  (a) the fixed point in 2.3 terminates and is monotone; (b) `L*` is per-slot
  optimal for `m*` over the achievable set; (c) step 2.4.1 fires iff `L*` is held
  (no fight chosen for XP otherwise).
- `formal/diff`: `test_winnable_across_band_diff.py` retires; new differentials
  bind the pure cores of 2.2–2.4.
- Tests that encode the ladder (rewrite to assert OUTCOMES, never membership):
  `test_tier_ladder.py`, `test_tier_progress.py`, `test_band_target.py`,
  `test_band_target_wiring.py`, `test_max_gear_for_level.py`,
  `test_progression_tree_core.py`, `test_progression_tree.py`,
  `test_tiers_strategy.py`, `test_decisions_root.py`, `test_strategy_driver.py`,
  `test_player*.py` (cascade cases), `scenarios/test_band_liveness.py`,
  `test_depth3_rung.py`, `test_goldens.py`, `test_held_task.py`,
  `test_slot_coverage.py`, `fixtures.py`, `test_tui/test_plan_format.py`.
  Scenario pins that assert a designed "wall" (`test_band_liveness.py`,
  `test_no_deadlock.py`) are re-examined: under 2.4 a wall never yields `Wait`
  while any `L*` piece is missing.

## 5. Acceptance

1. Robby's live shape (level 41, worn L10–20 armour, gearcrafting 23,
   jewelrycrafting 22, weaponcrafting 22, an items task held) as a scenario:
   the chosen root is an `L*` piece or the `ReachSkillLevel` in front of one —
   never `Wait`, never a fight chosen for XP.
2. A character holding `L*` fights `m*`, and `m*` is the max-`R` monster.
3. An unbeatable event monster changes nothing about `L*` or `m*` unless it is
   live and its drop or fight is on the argmax.
4. No source file under `src/` defines or reads tier, rung, band, ladder or
   milestone (a grep gate in `formal/gate.sh`).
5. Fleet: with two characters missing pieces gated on one skill, exactly the
   character with the least remaining climb seconds takes the climb, the other
   publishes demand and receives the piece by bank withdraw, and neither picks
   an XP fight meanwhile.
6. **Expected emergent behaviour (USER 2026-10-18):** "a correct algorithm is
   expected to cause all characters to grind skill xp for several days until at
   least one character gets weaponcrafting and gearcrafting up to their
   character level." Near-zero character XP fleet-wide during that period is
   CORRECT, not a regression; a census that flags it must be read against this
   clause. Fighting chosen for XP before some character holds weaponcrafting
   and gearcrafting at its character level (while `L*` pieces gated on them are
   missing) is a defect.
7. Live witness after restart: `plan Robby` shows an `L*` root; over the next
   24 h the fleet's crafting-skill XP is non-zero for each skill on some `L*`
   route, and worn gear level rises for every character with missing pieces.

## 6. Decisions (USER 2026-10-18: "yes to all three")

1. **Cost vs target.** Acquisition time orders pieces and never downgrades
   `L*`, including a piece whose only route is a very long skill climb.
2. **XP while gearing.** No fight is chosen for XP while `L*` is missing;
   acquisition fights still pay XP. Read as confirming 2.4 step 3 as written;
   a level-up is NOT an acquisition step.
3. **Fleet.** Coordination is in scope now (2.5): skill progression is
   amortized across the fleet so the whole fleet progresses.

## 7. Delivery

Architectural: this spec, then an implementation plan (writing-plans), then
waves. Proposed wave order: (1) pure cores of 2.2–2.4 + Lean + differentials,
unwired; (2) wire `L*` as the gear root and `m*` as the XP fight, behind the same
`resolve_root` entry; (3) fleet 2.5: publish `L*` demand, amortized sibling
route price, role demand from fleet `L*`; (4) delete the ladder and its
consumers, rewrite tests to outcomes, add the grep gate; (5) restart and
witness.

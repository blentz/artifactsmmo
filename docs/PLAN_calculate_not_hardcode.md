# PLAN: extend "calculate from game data, don't hard-code" across the app

Policy (CLAUDE.md): "This AI player can't function without game API data. Use only
API data or fail with an error." Audit (2026-06-18, 4 parallel investigators)
found frozen tables / magic numbers that SHADOW live API content — same failure
class as the alphabetical decide-tiebreak fixed in commit 1c737cd (code discards
or ignores a signal the API already carries).

Execute in priority order. Each item: TDD + (if it touches a proven core) the
full Lean lockstep + `formal/gate.sh` + commit. Check the box when committed.

## Tier 1 — discards computable signal AND flips a real decision

- [x] **#1 Multi-yield gather** — DONE (commit 0a2ba12, gate green). Global-max
  `ceil_gathers` at routing/gate layer; extracted core untouched. — `min_gathers.py:70-72`, `gathering.py:84,96`.
  Assumes 1 gather = +1 drop. `resource_drop_table()` exposes `(item, rate,
  min_qty, max_qty)`. True lower bound = `ceil(remaining / max_yield)` (best
  case), TIGHTER than `remaining`; current over-count can mark a reachable gear
  chain unplannable (`min_gathers > max_depth ⇒ skip`).
  FORMAL: extracted core. Touches `Extracted/MinGathers.lean`, hand
  `StepDispatch.minGathers`, the lower-bound theorem, oracle, differential,
  `PlannerDepthBound` soundness. DESIGN: max_yield as a per-item input dict
  (default 1 for craftables / unknown). Keep the lower-bound proof valid.

- [ ] **#2 `ITEM_TYPE_TO_SLOTS` frozen oracle** — `equip.py:17,34`.
  De-facto "is this gear & where", consulted across the whole stack. New
  equippable type → silently `None` → never equipped/scored AND recycle_surplus/
  inventory_caps treat it as junk (economic loss). DESIGN: derive slot set from
  the client `CharacterSchema *_slot` fields / `ItemSlot` enum; needs schema
  introspection. Enables #8.

## Tier 2 — shadow-API enumerations, silent staleness, duplication

- [x] **#3 `ELEMENTS` tuple** — DONE. New leaf `ai/elements.py` derives ELEMENTS
  from `MonsterSchema` `attack_*` fields; 3 literals now re-export/import it.
  Equipment cores already parametric → NO proof change; combat keeps 4 slots
  (value identical). NOTE: combat's `PredictWin.lean rawHit` still hardcodes 4
  slots — if the schema ever grows a 5th element the combat differential fails
  LOUDLY (forces the update) rather than silently ignoring it. — dup'd `elements.py:3`, `world_state.py:60`,
  `game_data.py`. Drives all combat damage/resist + armor/weapon scoring.
  `game_data.py:1041` ALREADY derives elements from `attack_`/`dmg_` prefixes —
  centralize to one derived source; delete the literals. FORMAL: feeds
  armor_score/combat proven cores → lockstep.

- [ ] **#4 Skill-name tables (triplicated)** — `strategy.py:139-141`,
  `prerequisite_graph.py:93`, `item_catalog.py:5`, `world_state.py:49`. Gather
  set = `resource_skills()`. DESIGN FORK: `strategy.py:369 else Fraction(0)` —
  policy says FAIL on unknown skill, not score 0. Decide fail-fast vs derive-
  exhaustive. FORMAL: dispatch exhaustiveness may touch DecideKey-style proofs.

- [x] **#5 Workshop→skill substring loop** — DONE. Hardcoded 8-skill tuple
  replaced with `_WORKSHOP_SKILLS = CraftSkill ∪ GatheringSkill` (API client
  enums). No formal impact (loader). — `game_data.py:985`. New craft
  skill's workshop gets no location → crafting silently broken. Sibling
  `_resource_skill` build at `:1148` already reads `res.skill.value` live —
  follow it. Self-contained in the loader.

## Tier 3 — real, lower blast radius

- [ ] **#6 `BANK_EXPANSION_SLOTS = 20`** — `bank_expansion.py:22`. Server-owned
  increment; abandoned `location_catalog.py:47 slots_per_expansion` was meant to
  learn it from the buy-response delta. Plumb runtime learning.
- [ ] **#7 `_COMBAT_GEAR_SLOTS` / `EQUIPMENT_SLOTS`** — `strategy.py:137`,
  `world_state.py:30`. Missing schema slot (e.g. `rune_slot`) → no urgency/prior.
  Derive from schema (pairs with #2/#3 enumeration work).
- [ ] **#8 `_DUPLICATE_FILL_TYPES = {"ring"}`** — dup'd `objective.py:19` /
  `equip.py:48`. artifact/utility are multi-slot in API; derive as "types mapping
  to ≥2 slots" from the #2 derived map. Single source.
- [ ] **#9 `GOLD_RESERVE = 500`** — `craft_vs_buy.py:15`. Track
  `next_expansion_cost` instead of a flat floor.

## Out of scope (legit policy / not API data)
Personality weights, proof scales (GEAR_EQUIP_SCALE, XP_RATE_REFERENCE), urgency
tiers, HP fractions, inventory soft-target bands, GOAP cost divisors, pathfinding
heuristics. Dead code to delete opportunistically: `consumable.py:19
_best_consumable`.

## Status log
- 2026-06-18: audit complete; plan written. Starting #1.

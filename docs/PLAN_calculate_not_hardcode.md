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

- [x] **#2 `ITEM_TYPE_TO_SLOTS` frozen oracle** — DONE. Derived in `equip.py`
  from `CharacterSchema` `*_slot` fields (each field's base, digits stripped, IS
  its item type). Byte-identical to the old maps (verified); dict iteration order
  not load-bearing (all consumers `.get()`/`sorted()`). New equippable
  type/slot now picked up on client regen instead of silently treated as junk.

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

- [x] **#4 Skill-name tables** — DONE (modulo SKILL_NAMES). `_GATHERING_SKILLS`
  ← `GatheringSkill` enum; new leaf `tiers/skill_classes.py` single-sources the
  combat-craft / gather / consumable-craft partition, DERIVED from
  CraftSkill/GatheringSkill enums + one policy seed `{alchemy,cooking}` via set
  algebra (combat = craft − gather − kitchen). Killed the
  strategy↔prereq_graph duplicate (`_CRAFTING_BOOTSTRAP_SKILLS` = the shared
  COMBAT_CRAFT_SKILLS). Caller-side only (strategy priors are an opaque scalar
  to the proven ranker). REMAINING: `SKILL_NAMES` (order-coupled to
  `Formal/Liveness/Skill.lean` + `test_objective_diff.py` → formal lockstep,
  DONE 2026-06-18: derived `SKILL_NAMES = sorted(CraftSkill ∪ GatheringSkill)`;
  the "formal lockstep" turned out free — order is not load-bearing (all Python
  consumers dict-keyed/len; oracle gapSum/targetSum permutation-invariant; the
  Lean `Skill` inductive is inert/unreferenced). Skill.lean docstring corrected.);
  PRIOR_* magnitudes are irreducible policy (not a target). — `strategy.py:139-141`,
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

- [x] **#6 `BANK_EXPANSION_SLOTS = 20`** — CLOSED (no change). The value is the
  OpenAPI contract ("Buy a 20 slots bank expansion", openapi.json:2843), already
  cited in-code — it IS API data, not a magic number. Runtime-learning the delta
  into slots_per_expansion is real executor-layer plumbing for negligible
  benefit; declined by decision 2026-06-18. — `bank_expansion.py:22`. Server-owned
  increment; abandoned `location_catalog.py:47 slots_per_expansion` was meant to
  learn it from the buy-response delta. Plumb runtime learning.
- [x] **#7 `_COMBAT_GEAR_SLOTS` / `EQUIPMENT_SLOTS`** — DONE. EQUIPMENT_SLOTS
  derived from CharacterSchema `*_slot` fields; `_COMBAT_GEAR_SLOTS` derived from
  a policy type-set (`_COMBAT_GEAR_TYPES`) via ITEM_TYPE_TO_SLOTS, so slots track
  the schema (a new ring slot auto-included) while the combat-type policy stays
  explicit. Byte-identical.
- [x] **#8 `_DUPLICATE_FILL_TYPES = {"ring"}`** — DONE (DRY, not derived).
  CORRECTION: the value is a SERVER-PROBE fact (only rings accept a duplicate
  item CODE, HTTP 200; live probe 2026-06-14), NOT "types with ≥2 slots" — so it
  is not schema-derivable. Single-sourced: `objective._DUPLICATE_FILL_TYPES` now
  imports `equip.DUPLICATE_SLOT_TYPES` (the one copy is gone).
- [~] **#9 `GOLD_RESERVE = 500`** — REFRAMED 2026-06-18 into a FEATURE: a
  calculated per-level progression-gold-reserve (cost of near-term gear/crafting/
  boss-odds upgrades), not a flat floor. Spec captured in
  `docs/PLAN_progression_gold_reserve.md`; needs brainstorming before build.
  — `craft_vs_buy.py:15`.

## Out of scope (legit policy / not API data)
Personality weights, proof scales (GEAR_EQUIP_SCALE, XP_RATE_REFERENCE), urgency
tiers, HP fractions, inventory soft-target bands, GOAP cost divisors, pathfinding
heuristics. Dead code to delete opportunistically: `consumable.py:19
_best_consumable`.

## Queue (tail-ordered)
1. Slot cluster: #2 ITEM_TYPE_TO_SLOTS → then #7 (EQUIPMENT_SLOTS) → then #8
   (dup-fill, derives from #2's map). IN PROGRESS.
2. #9 progression gold reserve (FEATURE, needs brainstorming) — LAST.
   Spec: docs/PLAN_progression_gold_reserve.md.

## Status log
- 2026-06-18: audit complete; plan written. Starting #1.
- 2026-06-18: #1, #3, #4 (4a+DRY+4c), #5 done & gate-green; #6 closed; forks
  resolved. Slot cluster next, #9 feature queued last.
- 2026-06-18: slot cluster #2/#7/#8 done & gate-green (commit e1c99da). ALL audit
  items resolved EXCEPT #9 (progression-reserve feature, queued — needs
  brainstorming; spec docs/PLAN_progression_gold_reserve.md).

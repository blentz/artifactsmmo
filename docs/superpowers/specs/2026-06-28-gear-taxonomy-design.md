# Sub-project A — Generic Gear Taxonomy — Design

**Status:** approved (brainstorm 2026-06-28) · **Epic:** Holistic Gear-Loadout
Architecture (`2026-06-28-gear-loadout-architecture-design.md`) · **Folds in:**
Season 8 P3.1 (generic combat-gear typing).
**Branch:** `feat/gear-loadout-architecture` (off the season8 + P2 chain = current `main`).
**Build order:** A is sub-project 1 of 5 (A → unified ruler → B → {C, D}).

## Why

Two hardcoded gear-type sets silently mis-score any new slot-backed type, and
encode an armor-vs-jewelry split that v8 makes wrong (ring/amulet carry the same
`res_*`/`hp` as armor; `rune` now carries real combat abilities). Replace both
with API/effect-derived classification that auto-extends on client regen.

The two sets encode **different** partitions feeding **different** consumers:

| Set | Members | Site | Decides |
|---|---|---|---|
| `inventory_caps._ARMOR_TYPES` | helmet, body_armor, leg_armor, boots, shield | `inventory_caps.py:302` | per-monster pareto scoring (defense) vs scalar `_equip_value` in the delete-dominance gate |
| `tiers/strategy._COMBAT_GEAR_TYPES` | weapon, shield, helmet, body_armor, leg_armor, boots, ring, amulet | `strategy.py:152` → `_COMBAT_GEAR_SLOTS` | `PRIOR_COMBAT_GEAR` vs `PRIOR_UTILITY_GEAR` prior (409); empty-combat-armor-slot char-level-boost gate (422) |

`_ARMOR_TYPES` excludes ring/amulet (scores them scalar); `_COMBAT_GEAR_TYPES`
includes them. This design collapses both into one effect-derived `combat_gear`
set plus a derived `defensive = combat_gear − weapon` interim view (sub-project C
subsumes the defensive view into profile-driven keep economy).

**Decision (approved):** full reclassification per the epic — ring/amulet/rune/
artifact move into per-monster pareto scoring at the dominance gate and into the
combat prior. This is a deliberate correctness change, regression-tested, not a
regression. De-risked by the fact that `armor_score`
(`equipment/scoring.py:174`) already sums **all** flat utility
(`hp_bonus + wisdom + prospecting + inventory_space + haste + lifesteal +
combat_buff`), so routing a lifesteal-rune or hp-ring through it is *more*
monster-aware than the scalar path, not lossy.

## Architecture & module layout

Classification depends on **live item effects**, so it cannot remain an
import-time `frozenset`; it is computed once from the loaded item catalog (like
`GameData.craft_yields`).

- **`ai/gear_taxonomy_core.py`** — pure, extracted, proved. `is_combat_bearing`
  (per-item combat-stat predicate) and `combat_gear_types` (fold over the
  catalog). Operates on plain data (no `GameData`/IO), mirrors the Lean def, is
  called directly by the differential harness.
- **`ai/gear_taxonomy.py`** — thin wrappers adapting `ItemStats` /
  `ITEM_TYPE_TO_SLOTS` into the core's plain inputs.
- **`GameData`** gains three memoized properties computed once at load:
  - `equippable_types: frozenset[str]` = keys of `ITEM_TYPE_TO_SLOTS`
    (`actions/equip.py:46`, already schema-derived).
  - `combat_gear_types: frozenset[str]` = effect-derived (below).
  - `defensive_gear_types: frozenset[str]` = `combat_gear_types − {"weapon"}`
    (interim view; documented as subsumed by sub-project C).
- Consumers drop their local constants and read the `GameData` properties (every
  consumer already holds a `game_data` handle).

## Classification semantics

- **`is_combat_bearing(item)`** ORs the *modeled combat-relevant* `ItemStats`
  fields: `attack`, `resistance`, `hp_bonus`, `dmg`, `dmg_elements`,
  `critical_strike`, `initiative`, **`lifesteal`** (plus any new combat field the
  audit forces us to model). **`lifesteal` is included** — it is the field that
  pulls `rune` into combat_gear, reconciling the epic's "reclassify rune IN" with
  its field list (which omitted lifesteal).
  **Excluded** (pure utility/gather, keep the utility prior, stay out of
  combat_gear): `wisdom`, `prospecting`, `inventory_space`, `haste`,
  `hp_restore`, `teleport_map_id`, `skill_effects`.
- **`combat_gear_types`** = `{ type : ∃ live equippable item of that type with
  is_combat_bearing }`. Effect-derived, auto-extends on client regen. Per the
  live v8 audit this reclassifies **rune** (lifesteal) and **artifact** IN.
- **`defensive_gear_types`** = `combat_gear_types − {weapon}` — replaces
  `_ARMOR_TYPES` at the dominance gate. Ring/amulet/rune/artifact now score via
  per-monster `armor_score` (which already folds hp/lifesteal/etc.).

## Coverage guard + audit-first (the cascade)

The item-effect ingestion (`game_data.py:1190-1271`) is an elif-chain ending in
`threat → pass` with **no else-branch** — any unmodeled effect code is silently
dropped today, and there is no `frenzy`/`greed`/`enchanted_mirror` branch (those
v8 abilities, if items carry them to the player, are dropped now).

Add an `else` that raises `GameDataCoverageError` for an unmodeled effect code on
an **equippable** item (mirrors the monster-effect guard). Non-equippable items
(consumables, resources) and the already-carved `threat` stay exempt/carved.

**Audit is task 1.** Load live v8 data; enumerate every effect code on every
equippable item. Per code, one of:
- **Already modeled** → fine.
- **Combat-relevant but unmodeled** (e.g. `frenzy`/`greed`/`enchanted_mirror` on
  a rune granting the *player* that ability) → model as a new `ItemStats` field
  **and** a player-side `predict_win` term. This is the cascade risk.
- **Irrelevant** (party/solo-N/A) → carve out explicitly like `threat`, with a
  comment.

The guard is fail-loud, so A cannot boot green on live data until every code is
resolved — making the audit the sizing gate for A. Player-grantable combat
modeling, if the audit finds any, is **in A's scope** (A owns "no equippable
effect silently mis-scores gear"). If that modeling balloons into multi-ability
`predict_win` work, flag it at that point as a candidate split rather than
silently absorbing it.

## Consumer migration

- `inventory_caps.py:302` — `_ARMOR_TYPES` → `game_data.defensive_gear_types`;
  `stats.type_ == "weapon" or stats.type_ in _ARMOR_TYPES` becomes
  `stats.type_ in game_data.combat_gear_types` (weapon ∈ combat_gear). The
  `_score_vector` weapon-vs-armor branch is unchanged.
- `tiers/strategy.py:152-157` — `_COMBAT_GEAR_TYPES` →
  `game_data.combat_gear_types`; `_COMBAT_GEAR_SLOTS` derived from it. Feeds the
  `PRIOR_COMBAT_GEAR` prior (409) and `_has_empty_armor_slot` (422).
- These are the only two hardcoded sets in scope. `DUPLICATE_SLOT_TYPES` (rings,
  server-probed) and `ITEM_TYPE_TO_SLOTS` (already schema-derived) are
  **unchanged**.

## Formal lockstep

`Formal/GearTaxonomy.lean`:
- `def isCombatBearing` (OR of field predicates) + `def combatGearTypes` (fold
  over the catalog).
- Role theorems:
  - **(a) membership characterization** —
    `t ∈ combatGearTypes items ↔ ∃ i ∈ items, i.type = t ∧ isCombatBearing i`.
  - **(b) monotonicity** — pointwise-stronger combat stats can only grow the set
    (a new combat field never *removes* a type).
  - **(c) subset** — `combatGearTypes ⊆ equippableTypes`.
- `Contracts.lean` exact-statement pins + `Manifest.lean` roster.
- Differential: Python `is_combat_bearing` / `combat_gear_types` ≡ oracle on
  Hypothesis-drawn catalogs (oracle runs the hand Lean def).
- Mutation: drop each field from the `isCombatBearing` OR → each mutant must die,
  forcing a test that exercises every combat field (no field silently
  non-load-bearing).

The coverage guard itself is a runtime data invariant, gated by unit tests + the
live audit, not Lean.

## Testing & rollout

- **Live-data audit test** — derived `combat_gear_types` / `defensive_gear_types`
  over real v8 data match the intended classification (rune/artifact IN), per the
  generic-categorization mandate (audit ALL live types first).
- **Regression** — document every intentional behavior change (ring/amulet → the
  per-monster gate; rune/artifact → the combat prior) with a test; no
  *unintended* selection changes vs current live data.
- Full unit suite ≥ current bar (100% coverage); full `formal/gate.sh` green.
- Serialize gate / mutation runs vs a live `artifactsmmo play`.

## Out of scope / non-goals

- The two divergent `equip_value` rulers — reconciled by the **unified value
  ruler** sub-project (next).
- Profiles, dedup, bank-space, learned loadouts — sub-projects C and D.
- `DUPLICATE_SLOT_TYPES` and `ITEM_TYPE_TO_SLOTS` (already correct/derived).
- Subtype-aware scoring (`ItemStats.subtype` exists but is display-only here).

## Task roadmap (implementation plan fills in)

1. **Live-data audit** — enumerate equippable effect codes; classify
   modeled/combat-unmodeled/irrelevant. Sizes the cascade.
2. **Resolve unmodeled codes** — model (ItemStats field + predict_win term) or
   carve, per audit.
3. **Coverage guard** — `else`-branch `GameDataCoverageError` for equippable
   unmodeled effects.
4. **Pure core + Lean** — `gear_taxonomy_core.py` + `Formal/GearTaxonomy.lean`
   (def + 3 role theorems) + Contracts + Manifest + extraction.
5. **GameData properties** — `equippable_types`, `combat_gear_types`,
   `defensive_gear_types` (memoized).
6. **Consumer migration** — `inventory_caps:302`, `strategy:152-157`.
7. **Differential + mutation + tests** — oracle harness, drop-field mutants,
   live-data audit test, regression tests.

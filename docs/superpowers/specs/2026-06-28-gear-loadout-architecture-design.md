# Holistic Gear-Loadout Architecture — Design (Epic)

**Status:** approved (brainstorm 2026-06-28) · **Approach:** Hybrid (③) · **Supersedes:** Season 8
P3.1 (generic combat-gear typing — folded into sub-project A here).
**Branch:** `feat/gear-loadout-architecture` (off the season8 + P2 chain).

## Why

Season 8 (API v8.0.0) reshaped gear: new slot-backed types are possible, `rune` now carries
real combat abilities (lifesteal/frenzy/greed/enchanted_mirror), and recipes/items were
rebalanced. The current gear stack has accreted into a **fragmented, partly-incorrect** shape:

- **Two hardcoded type sets** (`inventory_caps._ARMOR_TYPES`, `tiers/strategy._COMBAT_GEAR_TYPES`)
  silently mis-score any new slot-backed type. The armor-vs-jewelry split they encode is **not
  derivable from item effects** (ring/amulet carry the same `res_*`/`hp` as armor).
- **Two divergent `equip_value` functions** — `tiers/equip_value.equip_value` (×2, gated,
  used for selection/ranking) vs `inventory_caps._equip_value` (plain, ungated, used by the
  delete-dominance gate). The keep/delete economy scores gear on a **different ruler** than
  selection — a latent correctness bug.
- Loadouts are chosen **per-monster** only (`pick_loadout`), recomputed every cycle, never
  persisted, with **no profiles, no cross-loadout dedup, no bank-space accounting, and no
  learning** from real combat outcomes.

Now that we know v8's shape and have the experience of the current architecture, we rearchitect
for **holistic correctness**: one value ruler, per-task optimal loadouts, auto profiles with
bank-aware dedup, and learned per-monster refinement.

## Approach (Hybrid ③)

Unify where the bugs live (the value model); preserve the proofs that are already correct and
orthogonal to "what is optimal" (realizability, dual-ring, projection). Concretely: one
purpose-weighted value ruler; generalize the proved greedy-per-slot `pick_loadout` from
per-monster to per-task; add profiles/dedup/bank-space and learning as new layered modules.

### Current proved surface (rearchitecture cost — see the architecture map in the brainstorm)

Gate-locked Lean touching gear: `EquipmentScoring`, `GearPolicy`, `RealizableLoadout`
(dual-ring, ~25 roles), `PurposeRouting`, `EquipValueAugmented`/`Extracted.EquipValue`,
`LoadoutProjection`, `Objective`, `UpgradeSelection`, `DecideKey`, `StrategicValue`,
`ProgressionReserve`, `RecycleProtection`, `InventoryCaps`, `BankSelection`, `OwnedCount`.
**Preserved as-is:** `LoadoutProjection` (stat projection is orthogonal to scoring),
`RealizableLoadout` (realizability/dual-ring), `OwnedCount`. **Re-proved with a `purpose`
parameter:** the scoring trio + `PurposeRouting` + `DecideKey`/`StrategicValue` consumers.
**New cores:** profile-dedup, bank-space cost.

## Sub-projects (each its own brainstorm→spec→plan→formal cycle, fresh session)

Build order: **A → Unified ruler → B → {C, D}**. A and the unified ruler are the foundation.

### A — Generic gear taxonomy  *(folds in Season 8 P3.1)*

Replace the two hardcoded type sets with API-derived classification:
- **Equippable types** = keys of the schema-derived `ITEM_TYPE_TO_SLOTS` (`_derive_type_to_slots`,
  already generic; a new server slot appears on client regen).
- **`combat_gear` types** = equippable types whose live items carry any **combat stat**
  (`attack_*`, `res_*`, `hp`, `dmg*`, `critical_strike`, `initiative`). Effect-derived,
  auto-extending. This intentionally **reclassifies** `rune` and `artifact` IN (they carry
  combat effects in v8) — a deliberate correctness change, not a regression.
- **Armor-vs-jewelry split is eliminated.** Its only consumer is the per-monster keep cap in
  `inventory_caps`; that responsibility moves to C (keep what active profiles demand). Until C
  lands, A keeps a thin "defensive gear" view derived as `combat_gear minus weapon` for the cap
  (documented as interim).
- Coverage guard: like the monster-effect guard, fail loudly (or carve out) if an equippable
  type carries an **unmodeled** effect code, so a new v8 effect can't silently zero a gear score.

Formal: where A feeds gear scoring it must keep the scoring cores' inputs sound; the taxonomy
itself is data-derived (audit ALL live types first, per the generic-categorization principle).

### Unified value ruler

One proved core `gear_value(stats, purpose) -> Int`, `purpose` ∈:
- `Combat(monster_attack, monster_resist)` — `resist-to-M + offense-vs-M + hp + crit`
  (subsumes today's per-monster `armor_score` + `weapon_score`).
- `Gather(skill)` — skill-effect magnitude (subsumes `tool_value`).
- `Rank` (BiS / generic) — the purpose-agnostic sum (subsumes `equip_value`).
Collapse `inventory_caps._equip_value` into the `Rank` purpose (kills the divergent second
ruler). Re-prove monotonicity + the scoring-trio role theorems parameterised by `purpose`;
bridge every consumer (selection, dominance gate, DecideKey protection).

### B — Per-task loadout optimizer

`PurposeRouting`: task → `purpose`. Tasks = combat(monster) / gather(skill) / craft(skill, if
gear affects craft XP via wisdom) / idle(Rank). Generalize `pick_loadout(purpose, state,
game_data, pool)` keeping the proved greedy-per-slot structure + `RealizableLoadout`/dual-ring;
score via the unified ruler. Combat path MAY add a bounded local-search that evaluates candidate
swaps through `predict_win` (the true objective) — greedy stays the proved base; local-search is
a verified improver that never returns a worse predict_win verdict.

### C — Loadout profiles + bank-aware dedup

- **Profile** = `(task_key, loadout: dict[slot, code])`. Auto-created/updated per recurring task
  the bot actually performs (per grinded monster, per gather/craft skill). Persisted
  (`LearningStore`).
- **Dedup core (proved):** total gear demand`(code)` = **max over active profiles** of
  `count(code in profile)` — only one loadout is worn at a time, so shared gear is held once
  (2 profiles using copper_dagger ⇒ demand 1). Generalizes the per-slot demand economy and
  `RealizableLoadout.ownership`.
- **Bank-space cost (proved):** `|distinct gear across active profiles not currently equipped|`;
  the keep economy becomes "keep the union of active-profile gear (+1 spare for in-flight
  upgrades), recycle/sell the rest." **Subsumes `_ARMOR_TYPES`** and reconciles with
  `InventoryCaps`/`RecycleProtection` (target-gear protection = active-profile gear).

### D — Learned per-monster/task loadout

Persist per `task_key` the loadout that actually **won** (and its `predict_win` verdict vs the
real outcome) in a new `LearningStore` table keyed by `(character, task_key)`. Reuse the learned
best; refine when (a) a fight is lost with the stored loadout, or (b) a strictly-better-scoring
realizable loadout becomes available. Best-effort (log+swallow), never crashes a live action.

## Formal lockstep (per sub-project)

Each sub-project ships in the project's standard lockstep: computable Lean `def` + role theorems
(∀ inputs) + `Contracts.lean` exact-statement pins + `Manifest.lean` roster + differential
(Python≡oracle on the hand def) + mutation (drop-term mutants killed) + ≥ the existing coverage
bar. The unified-ruler change is the riskiest (re-proves the scoring trio + every bridge);
sequence it immediately after A and before B.

## Testing & safety

- Regression: against current live data the unified ruler must reproduce today's *selection*
  decisions except where the divergent-`_equip_value` bug is deliberately corrected; document
  every intentional behavior change with a test.
- `LearningStore` additions follow the best-effort `record_*` contract (no `except Exception`).
- Serialize-gate-runs: never run the formal gate / mutation while `artifactsmmo play` is live.
- Use only API data or fail; gear classification audits ALL live item types first.

## Out of scope / non-goals

- User-facing named-profile CLI (auto profiles only; a named-profile UX is a later phase).
- Joint combinatorial loadout search beyond bounded predict_win local-search (greedy-per-slot +
  bounded improver is the model).
- Set-bonus / multi-item synergy modeling (no such mechanic in v8 today; revisit if added).
- Merging the season8 / P2 branches (separate decision).

## Decomposition roadmap (each = its own session)

1. **A — generic taxonomy** (foundation; unblocks the live v8 mis-scoring risk; low blast radius).
2. **Unified value ruler** (reconcile the two equip_values; re-prove scoring trio + DecideKey).
3. **B — per-task optimizer** (purpose routing + generalized pick_loadout + optional predict_win improver).
4. **C — profiles + dedup + bank-space** (new cores; subsumes `_ARMOR_TYPES`).
5. **D — learned per-monster loadout** (new LearningStore table).

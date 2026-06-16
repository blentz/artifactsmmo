# PLAN: model consumable effects beyond `heal`

**Status:** planned (not started)
**Priority:** medium — improves consumable use; lower than bags/haste.

## Problem

The consumable logic (`item_catalog.best_consumable`, `ConsumableSelection`) ranks by
`hp_restore`, which is populated ONLY from the `heal` effect code. Other
HP-restoring / buff consumable effects are dropped by the parser → those potions are
invisible or undervalued:

- **`restore`** (5, e.g. `enchanted_health_potion`=300), **`splash_restore`** (2,
  `enchanted_health_splash_potion`=400), **`boost_hp`** (1, `health_boost_potion`=250)
  — these are ALSO HP restoration but under different codes → currently 0 hp_restore →
  the bot won't pick them as heals.
- **`boost_dmg_*`** / **`boost_res_*`** (8) — temporary combat buffs (potions).
- **`antipoison`** (3), **`healing`**/`healing_aura` — status cures / regen.

## Root cause

Same allowlist gap. `heal` → `hp_restore`; the other restore-family codes are dropped.

## Fix (staged)

### Stage 1 (cheap, high value): treat the restore-family as healing
- Map `restore`, `splash_restore`, `boost_hp` → `hp_restore` (they restore HP). Then
  `best_consumable` / `ConsumableSelection` see them as heals. Lowest-risk: these are
  semantically heals.
- Verify semantics from docs (is `boost_hp` a flat HP grant vs over-time? `restore`
  instant?). If over-time/temporary, model separately rather than as instant
  hp_restore.
- Formal: `ConsumableSelection`/`ConsumableCapValue` are proven — adding effect-code
  sources to hp_restore is upstream of the proven core (the parser), so the proven
  selection logic is unchanged; just more items carry hp_restore. Add parse tests +
  a consumable-selection case.

### Stage 2 (optional): combat buff potions
- `boost_dmg_*`/`boost_res_*` are pre-fight buffs — only useful if the bot models
  buffing before a fight (a UseConsumable-before-Fight tactic). Larger design; defer
  unless combat survivability needs it. Likely OUT of scope for now.

### Stage 3 (optional): status cures
- `antipoison` only matters if the bot models poison/status. Defer.

## Tests / gate
- Unit: parse tests for restore/splash_restore/boost_hp → hp_restore; a
  consumable-selection test that picks an `enchanted_health_potion` (restore=300) over
  a smaller `heal`. Mutation: drop the restore-family mapping. Full gate green.

## Note
This is the cheapest of the audit fixes (mostly parser + no proven-core change for
Stage 1). Good warm-up on the new branch before the heavier bag/haste work.

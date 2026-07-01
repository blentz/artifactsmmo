# Bootstrap Potion-Supply Weighting

## Problem

During early-game bootstrap the bot never stocks health potions. Trace evidence
(`play-trace-Robby.jsonl`, char level 5, alchemy level 1):

- The only potion signal reaching the planner is the strategy root
  `ObtainItem(code='small_health_potion', quantity=1, slot='utility1_slot')`
  scored **0.4**, drowned by bootstrap roots: empty combat gear **2.5**,
  char-level **2.25**, skill-up **~2.04**.
- The potion-supply guard `CraftPotionsGoal` (BAND_GUARD=0) **never fires** in
  603 cycles: `craft_potions_fires` calls `target_potion_pure`, which requires a
  utility potion craftable **at the current alchemy level**. The smallest
  hp-restore potion, `small_health_potion`, needs **alchemy level 5**; Robby's
  alchemy is level 1 (xp 0). No craftable-now target ⇒ guard permanently shut ⇒
  potions never stocked.

Root cause: potion supply is gated on *craftable-now*, but bootstrap never levels
alchemy to 5, so the gate stays closed forever. Potions were "not threaded
through the bootstrapping code."

## Decisions (locked)

- **Mechanism:** raise the potion-supply *root's* score into the bootstrap band
  at low level (no guard-gate change; formal guard model untouched). Its plan
  closure drives alchemy 1→5 + gather + craft + equip.
- **Minimum inventory:** reuse the existing level-scaled `potion_baseline_pure`
  (5 @ L5 → 100 @ L45). Single source of truth, already formally modeled
  (`formal/Formal/PotionBaseline.lean`).
- **Precedence:** the boosted potion root ties an empty combat-gear slot
  (**final score 2.5**) — pursued at the top of the bootstrap band.

## Design

### Seam

`StrategyEngine._marginal`, the `ObtainItem` branch —
`src/artifactsmmo_cli/ai/tiers/strategy.py:518-541`. This is where every gear
urgency multiplier already lives (`COMBAT_READINESS_URGENCY`,
`EMPTY_SLOT_URGENCY`). A utility-slot potion currently matches neither existing
branch (utility slots are not in `_combat_gear_slots`), so it falls through to
`return marginal` and its final value is `PRIOR_UTILITY_GEAR(2/5) × min(1,gain) ×
1 = 0.4`.

### New multiplier branch

Add one `elif` after the empty-slot branch (`strategy.py:537-540`):

```python
elif (stats.type_ == "utility"
      and getattr(stats, "hp_restore", 0) > 0
      and equipped_potion_qty(state, root.code)
          < potion_baseline_pure(state.level, POTION_LOW_LEVEL, POTION_LOW_QTY,
                                  POTION_HIGH_LEVEL, POTION_HIGH_QTY)):
    marginal = max(marginal, Fraction(1)) * POTION_SUPPLY_URGENCY
```

- **`stats.type_ == "utility"`** is the slot-family predicate — the same public
  signal `target_potion_pure` uses (`stats.type_ != "utility"` there). This
  avoids importing the private `_UTILITY_SLOTS` from `equipped_potion.py`;
  `equipped_potion_qty` already sums across the utility slots internally.
- **Not gated on `gain > 0`** (unlike the empty-slot branch): a health potion
  must be stocked even when the strategic-value model scores its equip-gain at 0.
  `max(marginal, Fraction(1))` guarantees the multiplier applies regardless of
  `gain`.
- `getattr(stats, "hp_restore", 0) > 0` is the "is a heal potion" predicate —
  the same signal `target_potion_pure` / `craft_potions_fires` use (effect
  `"hp_restore"`).

### The constant

```python
POTION_SUPPLY_URGENCY = EMPTY_SLOT_URGENCY * PRIOR_COMBAT_GEAR / PRIOR_UTILITY_GEAR
```

`= (5/2) × 1 / (2/5) = 25/4`. Final value =
`PRIOR_UTILITY_GEAR(2/5) × [max(marginal,1) × 25/4] × balancing(1) = 5/2 = 2.5`,
i.e. exactly where an empty combat slot lands. Expressing it as the derived
Fraction (not a literal `25/4`) pins it to "combat-gear-equivalent urgency" if
the priors are ever retuned. Add a docstring stating this, matching the style of
the surrounding urgency constants.

### Imports into strategy.py

- `from artifactsmmo_cli.ai.potion_baseline import potion_baseline_pure`
- `from artifactsmmo_cli.ai.thresholds import (POTION_LOW_LEVEL, POTION_LOW_QTY,
  POTION_HIGH_LEVEL, POTION_HIGH_QTY)`
- `from artifactsmmo_cli.ai.equipped_potion import equipped_potion_qty`
  (all imports top-of-file per project rules).

### Division of labor (this change is the whole fix)

1. **Deadlock break (alchemy < 5):** guard can't fire (no craftable-now target).
   The boosted root (score 2.5) becomes a top candidate and is pursued; its
   prerequisite closure forces `ReachSkillLevel(alchemy, 5)` (the craft-level
   gate on `small_health_potion`), then gather sunflowers → craft → equip.
2. **Maintain (alchemy ≥ 5):** once ≥1 potion is equipped, `near_term_gear` no
   longer emits the root (a same-value potion doesn't beat the equipped one) and
   `ObtainItem(quantity=1)` is satisfied — the root drops. The existing
   **guard** now fires (equipped 1 < baseline 5, craftable-now true) and tops the
   stack to baseline via its supply ladder. Root breaks the deadlock; guard
   maintains. No quantity change, no guard change.

### Why this is level-scaled, not a `level == 5` branch

The trigger is `equipped < potion_baseline_pure(level, …)`, so it self-scales:
at any level where equipped heal-potion qty trails the level's baseline and the
root is emitted, the boost applies. There is no hardcoded char-level check — the
baseline curve carries the level dependence. Once alchemy is high enough for the
guard to maintain supply, the root is satisfied/dropped and the boost is moot
(the guard preempts from BAND_GUARD=0 anyway).

## Testing

New unit tests in `tests/test_ai/test_tiers_strategy.py` (existing scorer test
module; use its fixtures — no ad-hoc tests):

1. **Under baseline → ties combat gear.** A `WorldState` at L5 with 0 equipped
   heal potions: `_value(ObtainItem(small_health_potion, slot='utility1_slot'))`
   == `Fraction(5, 2)` (== the empty-combat-slot score).
2. **At/above baseline → unchanged 0.4.** Same root, but equipped heal-potion qty
   ≥ baseline (5): `_value` == `PRIOR_UTILITY_GEAR` (0.4). Boost off.
3. **Non-heal utility potion → unchanged.** A utility item with
   `hp_restore == 0` (e.g. a boost/resist potion) under-stocked: `_value` stays
   0.4. Boost is heal-only.
4. **Level-scaled trigger.** At a higher level where baseline > equipped, boost
   applies; construct a case proving the threshold follows `potion_baseline_pure`
   rather than a constant (e.g. equipped qty that is below baseline at L45 but
   would be at/above the L5 baseline).

All via exact `Fraction` assertions (the ranking pipeline is exact-rational).
Success criteria unchanged: 0 errors, 0 warnings, 0 skipped, 100% coverage.

## Formal scope

The marginal formula is **not** in the differential perimeter today: there is no
`formal/diff/` oracle for `_marginal` / `_value` / `EMPTY_SLOT_URGENCY`.
`formal/Formal/RankingComposition.lean` proves the composite
`base × marginal × balancing` is per-factor monotone; a multiplier `≥ 1`
preserves that, so the new branch does not weaken the existing proof.

**This change matches the existing convention: unit tests only, no perimeter
expansion.** The `EMPTY_SLOT_URGENCY` and `COMBAT_READINESS_URGENCY` multipliers
this branch parallels are themselves covered by unit tests, not a differential
oracle. The [[project_potion_supply]] "new guard needs proven-ladder model"
lesson applies to *guards* (candidate-generation predicates in the proven
ladder); this is a root-score multiplier and is out of that perimeter. Extending
`RankingComposition.lean` or adding a differential diff for `_marginal` is
possible future hardening, explicitly out of scope here.

## Out of scope

- No change to `craft_potions_fires` / the CRAFT_POTIONS guard or its formal model.
- No change to `near_term_gear` root generation or `ObtainItem.quantity`.
- No new bootstrap minimum constant (reuse `potion_baseline_pure`).
- No formal-perimeter expansion (see Formal scope).
- Non-hp utility potions (boost/resist) are untouched — heal-only.

# PLAN: model `haste` and `lifesteal` in combat (predict_win + scoring)

**Status:** planned (not started)
**Priority:** high — `haste` is on 43 items and skews fight prediction; compounds the
2026-06-15 combat-margin fix ([[project_combat_veto_threshold]]).

## Corrected semantics (from game-data effect DESCRIPTIONS, authoritative)

- **`haste`** = *"reduces the cooldown of a fight"* — COOLDOWN REDUCTION (faster
  actions/fights = efficiency), **NOT combat damage**. Server applies it to action
  cooldowns. So it does **NOT** belong in `predict_win` (fight win/loss is unchanged).
  It's a UTILITY/efficiency stat → value it like `inventory_space`/`wisdom` (the
  LIGHTWEIGHT flat-utility lockstep, no proven-core change). The earlier assumption
  that haste affects damage was WRONG.
- **`lifesteal`** = *"Restores 15% of total attack in HP after a critical strike"* —
  heal-on-crit = combat SUSTAIN. This DOES affect `predict_win` (the player's
  effective HP rises during the fight), so it's the heavier one (proven-core change).

## Problem

Both stats are dropped by the effect parser (the novice_guide allowlist gap), so
haste/lifesteal gear is undervalued, and lifesteal is invisible to `predict_win`.

## Root cause

Same as novice_guide: the effect parser is a fixed allowlist; `haste`/`lifesteal` are
unlisted → dropped. `predict_win` (`combat.py`) models only attack/resistance/crit/hp.

## Fix

### Parsing + ItemStats
- `ItemStats` + `haste: int = 0`, `lifesteal: int = 0`; parser maps both codes.

### predict_win (the proven core — heavy)
- **haste**: model as an attack-frequency multiplier on `_expected_hit` (and the
  monster side). Per the docs, haste affects turn order/frequency; confirm the exact
  formula from docs.artifactsmmo.com before encoding. This changes the proven
  `PredictWin.lean` arithmetic → re-prove (predict_win_eq_sim, monotonicity,
  maxturns) in lockstep. CAUTION: predict_win gates Fight-for-drops planning — verify
  the haste model doesn't destabilize reachability (chicken→feather etc.).
- **lifesteal**: add player heal-per-hit into the rounds-to-die computation (effective
  HP rises with sustain). Also a `PredictWin.lean` change.
- Because both touch the proven predict_win formula AND planning, scope carefully;
  consider doing haste first (broader item coverage), lifesteal second.

### Scoring / value
- Fold `haste`/`lifesteal` into `equip_value` raw + the weapon/armor scores as
  combat contributors (weight TBD — these are %-style; only argmax ordering matters).
  Formal: `EquipValueAugmented` rawSum + the EquipmentScoring WScore if haste enters
  the weapon score. Lockstep bridges/diff/mutation.

## Open questions (verify from API docs first)
- Exact `haste` formula (attacks/turn? initiative interaction? cap?).
- `lifesteal` magnitude semantics (% of damage healed?).
- Whether monster haste/lifesteal must be modeled for predict_win symmetry (monsters
  carry these too — e.g. `desert_scorpion` lifesteal 15).

## Tests / gate
- Unit: parse tests; equip_value reflects haste/lifesteal; predict_win flips on a
  haste/lifesteal boundary case. Differential: predict_win diff with haste/lifesteal
  inputs. Mutation: drop haste/lifesteal from predict_win + value. Full gate green.
- Regression: re-run the Fight-for-drops reachability cases (feather/chicken) to
  confirm the predict_win change didn't break planning.

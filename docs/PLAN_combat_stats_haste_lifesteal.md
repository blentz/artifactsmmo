# PLAN: model `haste` and `lifesteal` in combat (predict_win + scoring)

**Status:** planned (not started)
**Priority:** high — `haste` is on 43 items and skews fight prediction; compounds the
2026-06-15 combat-margin fix ([[project_combat_veto_threshold]]).

## Problem

Two combat stats are dropped by the effect parser / not modeled:
- **`haste`** (43 items, e.g. `skullforged_pants`=8) — extra attacks per turn / faster
  turn cadence = more damage output. Only in display code, NOT in `ItemStats`,
  `predict_win`, or the scoring. So haste gear is undervalued AND `predict_win`
  under-estimates damage for the player (and monsters with haste).
- **`lifesteal`** (6, e.g. on gear/monsters) — heal-on-hit. Not in src at all.
  `predict_win` ignores combat sustain → underestimates survivability with lifesteal.

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

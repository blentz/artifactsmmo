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

### haste — DONE (a13d7c6)
Not a predict_win change. Cooldown reduction = efficiency utility, folded into the
flat-utility value like inventory_space. See the corrected-semantics note above.

### lifesteal — predict_win change (the heavy remaining one)
Semantics (effect desc): "Restores 15% of total attack of all elements in HP after a
CRITICAL STRIKE." So per the player's turn the EXPECTED heal is
`crit% × (lifesteal/100) × total_attack` (crit chance × the 15% × summed attack).
Model in `predict_win` (combat.py):
- **Player lifesteal** raises effective survivability: each player turn nets an
  expected self-heal, so the monster's effective damage-per-turn becomes
  `monster_hit − expected_player_lifesteal`. Extend `rounds_to_die` accordingly
  (guard: if effective monster damage ≤ 0, the player never dies → winnable on the
  damage side, still bounded by MAX_TURNS).
- **Monster lifesteal** (monsters carry it too, e.g. desert_scorpion=15) raises the
  monster's effective HP / lowers the player's net kill rate → extend
  `rounds_to_kill` symmetrically.
- This changes the proven `PredictWin.lean` arithmetic → re-prove `predict_win_eq_sim`,
  the monotonicity theorems, `maxturns_sound` in lockstep; update the extracted core +
  bridge + differential (`test_*predict_win*` / combat diff) + mutations.
- **CAUTION**: predict_win gates Fight-for-drops planning. Re-run the chicken→feather
  reachability cases; a stricter/looser predict_win must not break them. Also compose
  with the 2026-06-15 combat-veto fix ([[project_combat_veto_threshold]]) — lifesteal
  improving sustain may legitimately re-admit a monster the veto deselected.
- Also value lifesteal as a combat stat in equip_value/weapon scoring (smaller part).
- Open question: does crit `total_attack` use the raw or post-resistance attack?
  Verify from docs before encoding the exact integer formula.

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

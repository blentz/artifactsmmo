# PLAN: crit-aware weapon_score (loadout pick consistency with predict_win)

Status: CLOSED 2026-06-12. All 8 touch-list items done. Full pytest
3200/3200 @ 100% cov; gate phases a-d green (495 diff tests); mutation
gate OK in a detached-worktree snapshot (dirty-tree workaround — the
session's legit uncommitted fixes block in-tree mutation), new
crit-factor mutant KILLED, zero survivors. Live-verified: pick_loadout
vs green_slime now swaps copper_pickaxe → copper_dagger.

## Problem (run-18 trace 2026-06-12 20:45 + live API probe)

Robby (level 7) grinds green_slime with **copper_pickaxe equipped** (attack
earth 5, subtype tool, crit 0) while TWO copper_daggers (attack air 6,
crit 35) sit in inventory — losing 180/230 HP per fight at 15 xp/fight.

`pick_loadout("green_slime")` returns an EMPTY swap delta: `weapon_score`
is `Σ atk * max(0, 100-res)` with NO critical_strike term, so vs
green_slime (res_air 25): pickaxe 5×100=500 > dagger 6×75=450 → keeps
pickaxe. But `combat._expected_hit` (predict_win) models crit as
`raw × (1 + crit/100 × 0.5)`: dagger 4.5×1.175=5.29 > pickaxe 5.0.

**The loadout picker and the win predictor disagree about the same
quantity.** predict_win simulates with `pick_loadout`'s choice, so the
"best on-hand loadout" is computed by the LESS faithful model. The same
gap was already found at the gear-ROOT ranking level on 2026-06-06
(`EquipValueAugmented` — crit folded into equip_value, copper_dagger
crit=35 the motivating case) but the per-monster `weapon_score` was missed.

## Fix (exact integer, ordering-faithful)

`WScore'(item, mres) = (Σ_e atk_e × max(0, 100−res_e)) × (200 + crit)`

= the predict_win crit multiplier `(200+crit)/200` scaled by 200 to stay
in ℤ. Composite stays `2 × raw + nonToolBonus`. Sanity: pickaxe
500×200=100,000 < dagger 450×235=105,750 → dagger picked. ✓

NOT in scope (follow-up candidate): the `dmg`/`dmg_elements` % terms
predict_win also models (no current live mis-pick demonstrated; items in
play have dmg=0; needs its own round-half-up faithfulness analysis).

## Touch list (formal core — full gate)

1. ✅ failing test: pick_loadout swaps pickaxe→dagger vs green_slime (crit decides)
2. `src/artifactsmmo_cli/ai/equipment/scoring.py`: `weapon_score_raw_pure`
   gains `critical_strike: int` param, returns `score × (200 + crit)`;
   `weapon_score_pure` / `weapon_score_raw` / `weapon_score` thread it.
3. `formal/Formal/EquipmentScoring.lean`: `Item` gains `crit`;
   `WScore := (Σ wTerm) × (200 + item.crit)`; `weapon_score_nonneg`
   gains `0 ≤ item.crit` hypothesis; pick theorems are score-generic
   (untouched).
4. `formal/Formal/Contracts.lean`: re-pin weapon_score_nonneg statement.
5. `scripts/extract_lean.py` regen → `Formal/Extracted/EquipmentScoring.lean`;
   update `Bridges7.lean` bridge proof.
6. Oracle `runEquipmentScoring`: item block 11→12 ints (crit) + diff test
   `formal/diff/test_equipment_scoring_diff.py` lockstep.
7. `uv run pytest` (0 fail, 100% cov) → `./formal/gate.sh` →
   `formal/gate/mutate.py` (SERIALIZED — bot idle; `git diff src` after).
8. Live verify pick_loadout delta = dagger; resume play loop run 3.

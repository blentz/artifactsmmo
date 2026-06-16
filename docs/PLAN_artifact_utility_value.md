# PLAN: value utility gear (wisdom/prospecting/hp_bonus) — equip artifacts, don't discard them

**Status:** in progress
**Trigger:** Robby `Delete(novice_guide×4)` (trace 2026-06-15). novice_guide is an
ARTIFACT (wisdom 25 = +2.5% XP, prospecting 25 = +drops, hp 25; tradeable=false,
craft=null = irreplaceable) valued at **0** by every scoring path → never equipped,
discarded as junk.

## Root cause (verified)

- `ItemStats` has **no wisdom/prospecting fields**; the effect parser
  (`game_data.py:818-842`) silently drops unknown effect codes. novice_guide keeps
  only `hp_bonus=25`.
- `pick_loadout` scores non-weapon slots (incl. artifacts) via `armor_score` =
  Σ monster_attack[e]·resistance[e] — **monster-relative, resistance-only** → 0 for a
  flat-utility artifact. And `scoring.py:304-307` SKIPS filling an empty slot when
  `best_score <= 0`, so novice_guide is never equipped.
- `equip_value` (goal ranking) sums attack+res+hp_restore+hp_bonus+dmg+crit — no
  wisdom/prospecting.
- `_equip_value` (dominance/discard) sums only attack+resistance+hp_restore → 0 →
  novice_guide dominated/worthless → discarded.

## Design decisions

1. **Artifacts (and flat-utility gear) get a monster-INDEPENDENT utility score** =
   `hp_bonus + wisdom + prospecting + Σattack + Σresistance + dmg + critical_strike`
   (equal weight; mirrors the existing flat `equip_value` rawSum + the two new
   stats). pick_loadout routes **artifact slots** through this utility score; weapon
   slots keep weapon_score, armor slots keep armor_score (monster-relative defense).
2. **Equal weighting** (1 wisdom = 1 attack point) — matches the existing
   `equip_value` 1:1 sum; not a tuned combat weight. Good enough to rank utility gear
   and clear the >0 empty-slot gate.
3. `_equip_value` (dominance) gains hp_bonus + wisdom + prospecting so utility
   artifacts are never valued 0 (stops the discard). Not a proven def (feeds Bools to
   the proven `_is_dominated_pure`), but its diff test must stay green.

## Lockstep change set

### Python
- `item_catalog.py`: ItemStats `+ wisdom: int = 0`, `+ prospecting: int = 0`.
- `game_data.py`: parser `+ elif effect.code == "wisdom"/"prospecting"`.
- `equipment/scoring.py`: `+ artifact_score_pure` (flat utility sum) + `artifact_score`
  wrapper; pick_loadout uses it for artifact slots (3-way: weapon/artifact/armor).
- `tiers/equip_value.py`: `equip_value_pure` raw `+ wisdom + prospecting`; wrapper
  passes `stats.wisdom/prospecting`.
- `inventory_caps.py`: `_equip_value` `+ hp_bonus + wisdom + prospecting`.

### Formal (proven cores — must move in lockstep or the gate goes red)
- `EquipmentScoring.lean`: add wisdom/prospecting/hp_bonus/dmg to `Item`; add
  `UScore` (utility score) def + `utility_score_nonneg` theorem; pickSlot proofs are
  generic over the score fn → unchanged, but add an artifact-path witness.
- `EquipValueAugmented.lean`: `RawStats + wisdom + prospecting`; `rawSum` sums them;
  add `rawSum_mono_in_wisdom` / `_prospecting`; existing strict/tiebreak theorems
  generalize.
- `scripts/extract_lean.py` regen → `Extracted/EquipmentScoring.lean`,
  `Extracted/EquipValue.lean` (+ Bridges).
- `formal/diff/test_equipment_scoring_diff.py`: feed wisdom/prospecting in the item
  block; exercise the artifact/utility path.
- `formal/diff/test_*equip_value*_diff.py` + `test_inventory_caps_diff.py`: pass the
  new fields; keep dominance verdicts agreeing.
- `mutate.py`: new anchors (drop wisdom from artifact_score / equip_value).
- `Manifest.lean` + `Contracts.lean`: pin the new theorems.
- Full `formal/gate.sh` green.

## Out of scope
- Combat-relative weighting of wisdom/prospecting (treat flat). Re-tune later if the
  bot over/under-values utility gear.
- The targeted "irreplaceable keep" rule (fix A) — superseded: valuing the stats
  already lifts `_equip_value` above 0, so novice_guide is no longer discardable.

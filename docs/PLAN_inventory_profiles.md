# PLAN: Per-Goal Inventory Profiles (soft targets, not hard caps)

Branch: fix/inventory-caps-too-strict
Spec: docs/superpowers/specs/2026-06-07-inventory-profiles-design.md

## The bug
GatherMaterials(fishing_net) withdrew ash_wood while Deposit dumped it → livelock.
Roots: DepositInventoryGoal._RAMP_START=0.5; per-item useful_quantity_cap as a
dump trigger; bank keep-set doesn't protect the ACTIVE gather goal's materials.

## Implementation steps (STRICT TDD — test first each step)

1. [ ] `inventory_profile.py`: pure `inventory_profile(state, game_data, target_gear, target_tools)`
       -> dict[item_code -> target_qty]. Recipe-closure of crafting_target +
       target_gear + target_tools + task item & inputs. SOFT TARGET. 100% cov.
       - Pure overstock core lives in inventory_caps via a new
         `is_overstock(held, profile_target, used_fraction, watermark, useful_floor)`.
2. [ ] keep-set ∪ profile: bank_selection._keep_codes unions profile codes;
       deposit relevant-actions filter already routes through select_bank_deposits.
       Thread profile codes into select_bank_deposits + DepositInventoryGoal.
3. [ ] space-driven deposit: _RAMP_START 0.5 -> 0.85; deposit only NON-profile.
4. [ ] space-driven discard: overstocked_items takes profile + used_fraction;
       item overstock only when held > max(profile_target, useful_floor) AND
       used_fraction >= watermark. Below watermark w/ free slots → nothing overstock.

## Proofs (keep InventoryChainSafe HONEST)
- [ ] SAFETY: high-watermark deposit still fires before overflow — deposit value>0
      whenever next gather would exceed inventory_max. New theorem in
      InventoryChainSafe (deposit-fires-in-time over Inv model).
- [ ] PROFILE-PROTECTION (new module InventoryProfile.lean): pure
      `overstock(held, profileTarget, usedFraction, watermark, usefulFloor)` core +
      theorem: at/below profile target ⇒ never overstock, ∀ usedFraction. Mirror
      BankSelection.task_material_not_deposited.
- [ ] MONOTONE accumulation: profile item never banked ⇒ held non-decreasing under
      deposit/discard.
- [ ] Register Manifest/Contracts/Audit/concept-index; oracle+differential; gate part(d); mutate.py.

## Verify
- [ ] uv run pytest tests/ -q → 100% cov, 0 fail.
- [ ] SCENARIO test: GatherMaterials(fishing_net) + ash_wood in profile + free slots
      → ash_wood NOT deposited/discarded; held accumulates; no oscillation.
      FAILS on old code, PASSES on new.
- [ ] formal gate green (build, no_sorry, axioms, axioms_liveness, concept_index, diff, mutate).
- [ ] mypy + ruff clean.

# PLAN: model `inventory_space` so the bot equips bags (capacity)

**Status:** planned (not started)
**Priority:** HIGHEST of the stat-audit fixes — directly attacks Robby's chronic
inventory pressure + discards.
**Pattern:** identical to `docs/PLAN_artifact_utility_value.md` (novice_guide) — the
effect parser drops an unlisted code, so the item is valued 0 and never equipped.

## Problem

`bag_slot` exists in `EQUIPMENT_SLOTS` and `ITEM_TYPE_TO_SLOT` maps `bag`→`bag_slot`,
so bags ARE equippable. But the `inventory_space` effect (e.g. `sandwhisper_bag` =
**+50 slots**) is NOT parsed into `ItemStats` (only referenced in display code). So a
bag has all-zero stats → `armor_score` 0 → `pick_loadout` skips the empty `bag_slot`
fill (`scoring.py:304` `best_score <= 0`) → **the bot never equips a bag** and never
expands inventory. 9 items carry `inventory_space`.

## Open question (verify FIRST)

Does the server's `character.inventory_max` already include equipped bags' space (so
the bot only needs to EQUIP the bag and the server raises capacity), OR must the
planner model the capacity gain itself? Check: equip a bag on Robby via API, observe
whether `inventory_max` rises. This decides scope:
- **If server-computed:** fix = parse `inventory_space` + value it so the bag gets
  equipped; `WorldState.inventory_max` already reflects it post-equip. SMALL.
- **If client-projected:** also model `EquipAction.apply` raising `inventory_max` by
  the bag's `inventory_space` (like `hp_bonus`→`max_hp` projection), so the planner
  sees the capacity. Touches `ApplyBaseline`/inventory projection — LARGER.

## Fix (assuming server-computed; adjust if not)

- `ItemStats` + `inventory_space: int = 0`; parser maps `inventory_space`.
- Value it: bags are non-combat utility → fold `inventory_space` into the flat
  utility term (`armor_score`'s flatUtil + `equip_value` raw + `_equip_value`). A bag
  with +50 scores 50 → equipped. NOTE: scale — 50 inventory ≫ a 25-wisdom artifact;
  acceptable (capacity IS high-value), but consider whether bag value should be
  weighted vs combat gear (different slot, no competition — bag_slot only holds bags,
  so absolute value only matters for the >0 empty-slot gate, not cross-slot ranking).
- Formal lockstep (same as artifact fix): `flatUtil` already absorbs it on the Lean
  side IF inventory_space is added to the Python flatUtil sum — extend the
  `_item_block` flatUtil to include inventory_space, extend equip_value rawSum, add
  a bag differential case + mutation. EquipValueAugmented/EquipmentScoring may not
  need new fields (flatUtil/rawSum already sum a flat utility bucket) — just widen
  what feeds them.

## If client-projected (capacity modeling)
- `EquipAction.apply` (bag): `inventory_max += stats.inventory_space` (mirror the
  `hp_bonus`→`max_hp` pattern). This is in the proven `ApplyBaseline` surface →
  update the Lean apply model + baseline contract + diff + mutation.
- The planner then sees more capacity after equipping a bag → can plan
  "equip bag → more room → gather more" and inventory-pressure goals relax.

## Tests / gate
- Unit: bag parse test; bag `equip_value`/`armor_score` > 0; bag equipped into empty
  bag_slot (pick_loadout). Differential: bag case in test_equipment_scoring_diff.
  Mutation: drop inventory_space from the value. Full `formal/gate.sh` green.
- Regression: don't let a bag's large value distort cross-slot logic (bag_slot is
  isolated — verify no leakage into ranking of other gear).

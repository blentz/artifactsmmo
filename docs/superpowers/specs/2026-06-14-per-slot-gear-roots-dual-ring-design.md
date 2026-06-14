# Per-Slot Gear Roots (Dual-Ring Equip)

**Date:** 2026-06-14
**Status:** Design — pending user review
**Topic:** Let the objective target and equip the same item in more than one slot (e.g. two `copper_ring`s in `ring1_slot` + `ring2_slot`) by making gear roots slot-aware.

## Goal

The bot crafts copper_rings but only ever equips one, leaving `ring2_slot` empty forever — even with spare rings in inventory. Root cause: the gear model is per-item-code at quantity 1. `ObtainItem(copper_ring).is_satisfied` is `copper_ring in state.equipment.values()` — true the instant ring1 holds one, so the duplicate target dedupes/satisfies and ring2 is never pursued. Make gear roots **per-slot** so each equipment slot is an independent, independently-satisfiable target.

## Decisions (locked during brainstorming)

| Decision | Choice |
|---|---|
| Model | **Per-slot gear roots** — slot is part of the root's identity (not quantity-aware) |
| Duplicate-fill scope | **Rings only** (artifacts are unique; utility stays distinct) |
| Backward compatibility | `slot=None` default preserves today's behavior, equality, and repr exactly |
| Out of scope | quantity-aware model; artifact/utility duplication |

## Background (current behavior)

- `CharacterObjective.target_gear` is `slot -> code`, built by zipping ranked attainable items to a type's slots (`objective.py`). For rings only `copper_ring` is attainable → `zip([ring1_slot, ring2_slot], [copper_ring])` fills only `ring1_slot`.
- Gear roots are emitted per code: `prerequisite_graph.py` does `ObtainItem(code) for code in objective.target_gear.values()`.
- `ObtainItem` (`meta_goal.py`) is `(code, quantity=1)`. For an equippable, `is_satisfied` is `self.code in state.equipment.values()` (membership) — slot-agnostic.

## Architecture

### `ObtainItem` gains an optional `slot` (`src/artifactsmmo_cli/ai/tiers/meta_goal.py`)

- New field `slot: str | None = None`.
- `is_satisfied`:
  - `slot is not None` → `state.equipment.get(slot) == self.code` (that specific slot holds the item).
  - `slot is None` → **unchanged**: equippable → `self.code in state.equipment.values()`; non-equippable → `owned_count(state, self.code) >= self.quantity`.
- `repr` includes `slot` **only when set**, so every existing `ObtainItem(code)` / `ObtainItem(code, quantity=n)` repr is byte-identical. Equality/hash include `slot` (default `None`), so existing roots compare unchanged; a slot-tagged root is a distinct identity from a slot-less one and from a different-slot one.

### `target_gear` duplicate-fill, rings-only (`src/artifactsmmo_cli/ai/tiers/objective.py`)

- New module constant `_DUPLICATE_FILL_TYPES = frozenset({"ring"})`.
- In `from_game_data`, replace the `zip(slots, attainable)` loop: assign ranked distinct attainable items to slots; for any remaining slots, if `type_ in _DUPLICATE_FILL_TYPES` and there is at least one attainable item, fill with the best attainable (repeat). Result: 1 attainable ring → `ring1_slot` and `ring2_slot` both `copper_ring`; 2+ distinct attainable rings → top-2 distinct (preserved); artifacts/utility unchanged (remaining slots untargeted).

### Per-slot gear-root emission (`src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py`)

- Emit `ObtainItem(code, slot=slot)` for each `(slot, code)` in `objective.target_gear.items()` (was per `.values()`). Two ring slots → two distinct slot-tagged roots. Non-gear `ObtainItem`s (recipe materials in the prerequisite descent) stay `slot=None`.

### Slot-aware equip (`strategy_driver.py` / `goals/upgrade_equipment.py`)

- When a slot-tagged gear root's step is the equip, the `EquipAction` (already `(code, slot)`) targets `root.slot` — so the 2nd `copper_ring` is equipped into `ring2_slot` rather than the root reading satisfied off `ring1_slot`. The step builder / `UpgradeEquipmentGoal` uses `root.slot` when present to choose the destination slot.

### Slot-aware scoring (`src/artifactsmmo_cli/ai/tiers/strategy.py`)

- Where scoring currently derives the slot from the code (e.g. `_gear_slot`, the gear `_marginal` empty-slot/weapon-readiness urgency), use `root.slot` when the root carries one; else today's code→`target_gear` lookup. So a slot-tagged root scores *its own* slot's equip-value gain: while `ring1_slot` is full and `ring2_slot` empty, the ring2 root sees an empty slot (full target value / empty-slot urgency) and is pursued; once ring2 is filled both ring roots are satisfied.

## Data flow

`target_gear` (now includes ring2) → `objective_roots` emits per-slot `ObtainItem(code, slot)` → strategy ranks each slot root by its own slot's gain → the empty-ring-slot root wins its tier → its step equips `code` into that slot → `is_satisfied` flips for that slot only. Ring1 then ring2 fill in successive cycles.

## Error handling (CLAUDE.md)

Pure model/logic; no API data. No defaulting over missing data, no `except Exception`, no inline imports, no `TYPE_CHECKING`. `slot` is a plain optional field.

## Testing (0 errors / 0 warnings / 0 skipped / 100% coverage)

**New:**
- `ObtainItem(slot=…)`: satisfied iff that slot holds the code; a different slot or empty slot is unsatisfied. `slot=None` membership / `owned_count` unchanged. repr omits `slot` when `None`, includes it when set.
- `objective.py`: 1 attainable ring → both ring slots target it; artifacts NOT duplicate-filled (single artifact → only `artifact1_slot`); existing top-2-distinct test preserved.
- `prerequisite_graph`: `target_gear` with `ring1_slot` + `ring2_slot` = copper_ring emits two distinct slot-tagged roots.
- Equip step: `ObtainItem(copper_ring, slot="ring2_slot")` plans an `EquipAction` into `ring2_slot`.
- Scoring: with `ring1_slot` filled and `ring2_slot` empty, the ring1 root is satisfied (dropped from ranking) and the ring2 root scores its empty slot (pursued).
- **Integration regression:** state with `copper_ring` in `ring1_slot` + a spare `copper_ring` in inventory → the arbiter/plan equips the spare into `ring2_slot`.

**Curate (ripple):**
- Tests asserting the gear-root set from `target_gear` update to the slot-tagged emission.
- Existing equippable-goal / formal-bridge tests run the `slot=None` path and must stay green unchanged (they assert the membership semantics, which `slot=None` preserves).

## Addendum 2026-06-14 — the one-slot-per-code guard must be narrowed (post-implementation discovery)

The per-slot roots (Tasks 1–4, branch `feat/per-slot-gear`) are correct but **inert in production**: a pre-existing guard blocks the terminal equip. `EquipAction.is_applicable` (`actions/equip.py`), `OptimizeLoadoutAction`/`pick_loadout` (`actions/optimize_loadout.py`), and the **kernel-proved `RealizableLoadout`/`EquipmentScoring` model** (`equipment/scoring.py` + `formal/`) enforce ONE-SLOT-PER-CODE (commit `dcde76c`, citing server HTTP 485 "already equipped") — so `EquipAction(copper_ring, ring2_slot)` while `ring1_slot` wears copper_ring is rejected and `ring2` is pursued-forever-never-equipped.

**Live-server probe (2026-06-14, character Robby):** equipping a 2nd `copper_ring` into `ring2_slot` with `ring1_slot` already wearing one returned **HTTP 200** — the server ALLOWS duplicate rings. The one-slot-per-code guard is therefore **over-broad** (likely generalized from the documented utility/`small_health_potion` 485 case). Confirmed per-type rule (evidence-grounded; utility/artifact not empirically probeable at Robby's level):

- **ring** → duplicates allowed (probe: 200).
- **utility** → keep one-slot-per-code (documented `small_health_potion` utility1→utility2 485).
- **artifact** → keep one-slot-per-code (no evidence; conventionally unique).

So `_DUPLICATE_SLOT_TYPES = {"ring"}` (matches the objective layer's `_DUPLICATE_FILL_TYPES`).

### Additional components (extend the feature)

5. **Narrow the guard, rings-only** — `EquipAction.is_applicable`, `pick_loadout`/`OptimizeLoadoutAction`, and `equipment/scoring.py`: the one-slot-per-code rejection applies only when the item's type is NOT in `_DUPLICATE_SLOT_TYPES`. Rings may occupy two slots; all other codes keep the rule (the real 485 cases).
6. **Update the Lean `RealizableLoadout`/`EquipmentScoring` model + proof in lockstep** (`formal/`) — the proven invariant becomes "one slot per code EXCEPT duplicate-allowed types (ring)". This is a **formal-development** task: the differential/mutation gate must still pass, the extracted `scoring.py` regenerated (sha header), and no proof weakened beyond the rings carve-out. Drive via the formal-development skill.
7. **Honest integration test** — replace the assertion-light `test_arbiter_equips_second_ring_into_empty_slot` (asserts only that the root is *chosen*) with one that builds the plan AND asserts `EquipAction(copper_ring, ring2_slot).is_applicable` is True / the executed result leaves `ring2_slot == copper_ring`. It must fail before the guard fix and pass after.

## Out of scope (YAGNI)

- Artifact/utility duplication (rings only — utility/artifact keep one-slot-per-code).
- Quantity-aware `ObtainItem` model (rejected in favor of per-slot).
- Any change to which item is best per slot (ranking/equip_value unchanged); this adds slot identity + rings dup-fill + the rings carve-out in the one-slot-per-code invariant.

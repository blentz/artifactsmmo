# Complete Effect Coverage — Design

**Status:** approved (brainstorm 2026-06-29) · **Follows:** gear epic + Season 8 (the "fully model
all effects" deferral).
**Branch:** `feat/complete-effect-coverage` (off main `b054d369`).

## Why

The gear/Season-8 epics modeled most game effects but deferred "fully modeling all effects." A
live audit (2026-06-29, `/effects` × `/items` × `/monsters`) found the gap is small and contained:

- **Monster effects: ZERO gaps** — all 14 live codes are modeled or carved (`corrupted`).
- **Item effects: all modeled/carved EXCEPT `gold` and `gems`** — both on consumables, both
  **silently dropped** because the item-effect coverage guard is **equippable-only** (non-equippable
  unmodeled effects bypass the `else: raise`).
- **`christmas_magic`** — in `/effects` but on no live item/monster (rides the event weapon
  `christmas_cane`; latent).

Two problems: a `bag_of_gold` (+2500) is silently unmodeled (its gold never claimed, ~70% of a
bank expansion), and the guard has a **structural silent-drop hole** for any future
non-equippable effect — violating the generic-categorization principle (model or carve, never
silently ignore).

## Audit results (the universe, locked as a regression test)

```
gold              consumable   bag_of_gold(+2500), small_bag_of_gold(+1000)  -> MODEL
gems              consumable   small_bag_of_gems(+25), bag_of_gems(+50)      -> CARVE (account meta-currency)
christmas_magic   item(weapon) christmas_cane (not live now)                 -> CARVE (event self-debuff)
<all other item codes>                                                       already MODELED or CARVED
<all 14 monster codes>                                                       already MODELED or CARVED (corrupted)
```

## Scope (approved decisions)

1. **`gold` → model + use.** New `ItemStats.gold_value`; ingest the `gold` effect; the bot consumes
   gold-bags for their gold.
2. **`gems` → carve.** Account meta-currency (skins / subscription / event-spawning); no use in the
   autonomous reach-50 loop. Documented carve.
3. **`christmas_magic` → carve.** Rides the event weapon `christmas_cane`; the effect makes the
   player's hits *buff the enemy* (a self-debuff) — never modeled. Documented carve. (It is an
   item/weapon effect, so it would hit the *equippable* guard if the cane ever appears — carving
   it pre-empts a spurious `GameDataCoverageError`.)
4. **Structural guard fix.** Extend the item-effect coverage guard from equippable-only to **all
   item types**, so any item carrying an unmodeled effect raises `GameDataCoverageError` instead of
   silently dropping. Audit-confirmed safe: consumables carry only `heal`/`teleport` (modeled) +
   `gold` (now modeled) + `gems` (carved); no other item type carries effects.

## Gold: data flow + use trigger

- **Ingest:** `elif effect.code == "gold": stats.gold_value = effect.value` in
  `_build_items` (a non-combat consumable field, alongside `teleport_map_id`).
- **`UseGoldBagAction`** (new, `actions/`) — a PLAIN GOAP action (NOT a discretionary MeansKind, to
  avoid a `DecideKey` lockstep): `is_applicable` iff a gold-bag (`gold_value > 0`) is owned;
  `apply = dataclasses.replace(state, gold=state.gold + gold_value, inventory=<bag decremented>)`
  (the established gold-credit pattern from `npc_sell`/`ge_fill`); `execute` calls the
  `action_use_item` API (as `UseConsumableAction` does); `cost` a small constant. Added to the
  factory action set.
- **Trigger (GOAP-natural):** the planner pulls `UseGoldBagAction` in as a prerequisite step when a
  gold-needing goal (e.g. `BuyBankExpansion` requires `gold >= next_expansion_cost`, an NPC buy)
  wants more gold than is on hand — the action raises `gold` toward the goal's applicability. No new
  MeansKind, no `DecideKey`. Gold-bags are **already keep-protected** (`type=="consumable"` →
  `CONSUMABLE_KEEP=999`, type-driven, not hp_restore-driven), so they are never discarded/sold while
  awaiting a gold-need — no gold is lost, it is deferred until used.
- `UseConsumableAction` stays HP-restore-only (unchanged); gold use is its own action (one
  behavioral class per file).

## Structural guard change + carves

`_build_items` final branch: drop the `if item_type in ITEM_TYPE_TO_SLOTS:` restriction so it is a
plain `else: raise GameDataCoverageError(...)` for ALL item types. A new module constant
`_ITEM_EFFECT_CARVEOUTS = frozenset({"gems", "christmas_magic"})` (with per-code rationale) is
checked before the raise, joining the existing `threat` carve + `_RUNE_ABILITY_CARVEOUTS`. `gold`
becomes a modeled `elif` (no carve). The raise message names the item + code + points at the
carve constants. Monster guard (`_build_monsters`) unchanged — already complete.

## Formal scope

- **`UseGoldBagAction` → `ApplyBaseline` baseline-preservation contract.** Extend the 24-action
  `ModeledApply` inductive to 25 with a `useGoldBag_preserves_baseline` theorem (gold + inventory
  change, baseline 8-conjunct invariant preserved — mirrors `npc_sell`/`ge_fill`). This is the ONLY
  Lean addition. `Contracts.lean` pin + `Manifest.lean` roster + the existing
  `test_apply_baseline_diff.py` differential + a baseline-revert mutation witness.
- **`gold_value` is currency, NOT a gear/combat stat** → no `gear_value`/`combat_raw` re-prove, no
  `predict_win` touch, no gear-taxonomy change (gold-bags are `consumable`, not equippable).
- The guard change + carves are runtime data invariants — unit-tested, not Lean.

## Testing & rollout

- **Live-data effect-coverage audit test** (gated like the other live tests): every live item effect
  code is modeled-or-carved (locks the structural guard now covering consumables); `gold` →
  `gold_value`; `gems`/`christmas_magic` carved; monster codes all modeled/carved.
- **Guard closes the hole**: a synthetic non-equippable item with an unknown effect now raises
  `GameDataCoverageError` (previously silent).
- **`UseGoldBagAction`**: applicable iff a gold-bag owned; `apply` credits exact `gold_value` +
  decrements the bag; `execute` via `action_use_item`; a planner test that a gold-bag is chained
  before a gold-short `BuyBankExpansion`.
- Full unit suite ≥ current bar (100%); full `formal/gate.sh` green (the new ApplyBaseline contract
  + differential + mutation); `git checkout uv.lock` before commits; serialize gate vs live `play`.

## Out of scope / non-goals

- Spending/earning gems (account meta-currency — no autonomous-bot use).
- Modeling `christmas_magic` combat math (event weapon, self-debuff, no live entity).
- Re-deriving gold's downstream use (progression reserve / bank-expansion already consume `gold`;
  this only makes gold-bag gold reachable).
- Any monster-effect change (zero gaps).

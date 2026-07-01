# Potion Supply (CraftPotions) — Design Spec

**Date:** 2026-06-30
**Status:** Approved decisions; pending spec review → implementation plan
**Follow-up to:** `2026-06-30-combat-survivability-design.md` (the deferred full-stack supply piece)

## Problem

The combat-survivability feature equips win-rate-scaled health potions for marginal
fights, but only from what's already HELD — and the bot has no path that stocks utility
potions toward a full stack. `MaintainConsumablesGoal` is a discretionary means
(value 25) outranked by the grind, so it never accumulates while grinding; and at low
level the bot's only heals are cooking food (`type=consumable`, not utility-equippable).
Result: provisioning is effectively capped at a few held potions and never reaches the
"full stack for a hard fight" the player wants.

## Goal

A new always-on goal `CraftPotions(effect)` that incrementally stocks the equipped
utility-slot potion stack toward a level-scaled baseline — crafting from held
ingredients when possible, buying the optimal ingredient mix when gold allows, and
otherwise gathering a small batch and replanning. Full stack is a long-term target
reached incrementally, never a single big grind.

## Decisions (locked with the user)

1. **Satisfied = can't-craft-more.** `CraftPotions` is satisfied when the equipped
   stack is at `max_stack` (100) OR no further potion batch is producible this cycle
   (can't craft from held, can't afford to buy enough, can't gather). It always tries to
   make progress; it yields only when full or genuinely blocked.
2. **CraftPotions crafts AND equips a level-scaled baseline.** It tops up the equipped
   utility-slot quantity. The merged win-rate `ProvisionMarginalFightGoal` coexists as a
   per-fight bump to the win-rate-scaled quantity for an especially-hard target (usually
   finds the slot already baseline-stocked).
3. **Prove the core decisions.** The weight, the max-batch-from-held count, and the
   optimal-buy-mix are float-free pure cores with Lean mirrors + differential + mutation,
   matching `marginal_potion_qty`.
4. **Effect scope:** this spec covers `effect = hp_restore` (health potions). The goal is
   parameterized by effect for future extension (damage/boost utilities) — out of scope here.

## Level→baseline curve (smooth ramp — replaces the earlier watermark formula)

The maintained baseline grows smoothly with level: a few potions early, a full stack only
near end-game.

```
baseline(level) = low_qty                                   if level <= low_level
                = high_qty                                  if level >= high_level
                = low_qty + floor((high_qty - low_qty) * (level - low_level)
                                  / (high_level - low_level))   otherwise
```
with `low_level=5, low_qty=5, high_level=45, high_qty=100` (= `UTILITY_SLOT_MAX_STACK`):
linear from `(level 5 → 5 potions)` to `(level 45 → 100 potions)`, i.e.
`5 + floor(95*(level-5)/40)` on the ramp. Examples: L1-5 → 5, L10 → 16, L20 → 40,
L30 → 64, L40 → 88, L45+ → 100. Monotone non-decreasing in level; integer (float-free).

- Anchors (user-specified): the first 5 levels need no more than ~5 potions on-hand;
  full stacks (100) only near end-game (level ≥ 45); smooth ramp between.
- `current_equipped_stack_size` (the quantity of the target potion in the utility slot,
  NEW state — see below) is compared against `baseline(level)`.

**Fire (preempt) decision:** `CraftPotions` fires — interrupts the grind to stock —
**while `equipped_qty < baseline(level)`** (and a batch is producible). When
`equipped_qty >= baseline(level)` it yields and the grind proceeds. The target grows with
level, so the maintained stack ramps up smoothly as the player levels.

**Behavior note (accepted):** while below the level baseline, `CraftPotions` (guard-tier,
preemptive) outranks the grind to stock potions; it is gated by craftability — when alchemy
can't yet make the potion it does not fire and the bot grinds. So it is dormant until
alchemy comes online, then stocks to the level baseline, interleaved with grinding via the
batch-and-replan loop.

## New state — equipped utility-slot quantity

The server `CharacterSchema` exposes `utility1_slot_quantity` / `utility2_slot_quantity`
(verified in the client model). `WorldState` currently drops them (`equipment` maps slot
→ code only). Add:
- `WorldState.utility1_slot_quantity: int`, `WorldState.utility2_slot_quantity: int`,
  populated in `from_character_schema`. (This also enables per-cycle stack top-up — folds
  in the separate utility-slot-quantity follow-up.)
- Helper `equipped_potion_qty(state, code) -> int`: the quantity of `code` across utility
  slots (0 if not equipped there).
- `EquipAction` becomes quantity-aware on apply for utility slots: equipping `q` of a code
  into a utility slot sets that slot's modeled quantity (top-up semantics verified against
  the server — see Open items).

## Proven pure cores (Lean + differential + mutation)

1. `potion_baseline_pure(level, low_level, low_qty, high_level, high_qty) -> int` — the
   level→baseline curve above (clamped + floor-linear ramp). Proven: equals `low_qty` at/below
   `low_level`, `high_qty` at/above `high_level`, monotone non-decreasing in `level`, and
   bounded in `[low_qty, high_qty]`. The fire decision is `equipped_qty < potion_baseline_pure(level, ...)`.
2. `max_batch_from_held_pure(recipe: list[(ingredient_need, held_count)], yield_per_craft)
   -> int` — the max number of potions craftable from held ingredients =
   `min_i(held_i // need_i) * yield_per_craft`. Proven: bounded by every ingredient's
   floor-division; 0 when any ingredient is short.
3. `optimal_buy_mix_pure(recipe: list[(need_i, held_i, price_i)], gold, yield_per_craft,
   max_batch) -> int` — the max batch count `B` such that
   `sum_i price_i * max(0, B*need_i - held_i) <= gold`, capped at `max_batch`. Returns `B`
   (per-ingredient buy quantities are `max(0, B*need_i - held_i)`, derived in glue).
   Proven: cost monotone non-decreasing in `B`; result is the largest feasible `B ≤ max_batch`.
   Float-free (integer gold/prices). This is the "optimal mix" — buy exactly the deficit
   for the largest batch current gold affords.

## The goal — `CraftPotionsGoal(effect)`

- **Target potion selection (glue):** the alchemy-craftable utility heal for the effect
  the bot can make now — `item_stats(code)`: `type_="utility"`, `hp_restore > 0`,
  `crafting_skill == "alchemy"`, `crafting_level <= state.skills["alchemy"]`. Prefer the
  highest `hp_restore` such craftable potion (deterministic tie-break by code). `None` →
  goal satisfied (nothing to craft).
- **`value`:** `float(baseline - equipped_qty)` while firing (potions short of the level
  baseline), `0.0` when satisfied. (Guard ordering is fixed; this value is for urgency/logging.)
- **`is_satisfied`:** equipped quantity in some utility slot `>= baseline(level)` (state-only,
  via `potion_baseline_pure(state.level, ...)`) OR no producible batch this cycle. Because
  `Goal.is_satisfied(state)` has no `game_data`, the producibility/target half lives in the
  guard `_fires` predicate (which has `game_data`); `is_satisfied` covers the state-only
  baseline check.
- **Plan ladder (priority 1 > 2 > 3, the user's order):**
  1. **Craft from held:** if `max_batch_from_held_pure(recipe, inventory+bank, yield) >= 1`,
     emit `CraftAction(potion, quantity=that batch)` (+ any `WithdrawItemAction` to pull
     bank ingredients) then `EquipAction(potion, utility1_slot, quantity=crafted)`.
  2. **Buy mix:** else if ingredients are NPC-buyable, compute
     `B = optimal_buy_mix_pure(recipe, inventory+bank, prices, gold, yield, cap)`; if
     `B >= 1`, emit `NpcBuyAction`(s) for the per-ingredient deficits → `CraftAction(B)` →
     `EquipAction`.
  3. **Gather a 5-potion batch:** else emit `GatherAction`s for the ingredients of a
     `POTION_GATHER_BATCH = 5`-potion batch → `CraftAction(5)` → `EquipAction`. The goal
     re-fires next cycle (natural replan) until satisfied.
- **`relevant_actions`** returns exactly the ladder's actions for the current state so the
  planner builds the right step; `desired_state`/`is_satisfied` terminate on the equipped
  quantity reaching the producible target.

## Arbiter placement (decided)

The arbiter is strictly tiered — guards → collect → objective-step (grind) → discretionary,
first non-empty tier wins — so a discretionary goal can NEVER outrank a plannable step-grind
(this is exactly why `MaintainConsumables` never accumulated). `CraftPotionsGoal` is therefore
a **preemptive guard-tier goal** (`preemptive = True`, like `RestoreHPGoal`): it enters the
guard tier and interrupts the grind to stock potions, but only **while it FIRES**.

- **Fire condition:** `equipped_qty < baseline(level)` AND a batch is producible now
  (craft-from-held OR buyable OR gatherable).
- **Value while firing:** `baseline(level) - equipped_qty` (potions short), below survival
  `RestoreHP = 110`. Guard precedence is the fixed `GUARD_ORDER` position (lowest guard,
  still above the objective-step grind), so a firing `CraftPotions` preempts the grind.
- **When not firing** (stocked to `baseline(level)`, or no producible batch) the grind proceeds.

**Resulting curve (the smooth ramp):** maintains ~5 potions through level 5, ramps linearly to
a full 100 by level 45, full stack thereafter — see the curve section. Still gated by
craftability (dormant when alchemy can't yet make the potion) and bounded by the
craft/buy/gather-5 loop.

## Testing

- Unit: each pure core's truth table (weight monotonicity + bounds; max-batch min-floor;
  buy-mix monotone max-feasible-B incl. gold=0 and already-held cases).
- Differential + mutation for all three cores (mirror `marginal_potion_qty`).
- Goal: target-selection (alchemy-gated, best-restore, None when uncraftable);
  value/is_satisfied (full, blocked, mid-stock); the craft/buy/gather ladder picks the
  right tier; `EquipAction` quantity top-up.
- State: `WorldState` round-trips `utility{1,2}_slot_quantity`; `equipped_potion_qty`.
- Integration: low equipped stock + alchemy available → `CraftPotionsGoal` selected over
  grind; uncraftable → satisfied → grind proceeds.
- Coverage 100%; full `formal/gate.sh` green.

## Open items (resolve in plan / by probe)

- **Equip top-up semantics:** does equipping `q` more of a potion already in a utility
  slot ADD to the stack (M→M+q) or REPLACE (→q)? Determines whether top-up equips the
  deficit or the full target. Verify against the API/server (small probe) before relying
  on it; model `EquipAction.apply` to match.
- **Bank ingredients:** `max_batch_from_held` counts inventory + bank; confirm the craft
  ladder withdraws bank ingredients (existing `WithdrawItemAction`) within the plan.

## Out of scope (future)

- Non-`hp_restore` effects (damage/boost utilities) + `utility2` multi-effect loadouts.
- Same-potion-both-slots (the dup-guard 485 question) — independent follow-up.

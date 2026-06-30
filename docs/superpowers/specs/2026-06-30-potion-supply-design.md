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

## Weight formula (user-specified)

```
weight = max_stack - lower(current_equipped_stack_size, (1 / (2 * current_level)) * 100)
       = 100 - min(equipped_qty, 50 / level)          # lower() = min; max_stack = 100
```

- `current_equipped_stack_size` = the quantity of the target potion currently in the
  utility slot (NEW state; see below). `current_level` = character level.
- The watermark `50/level` shrinks as level rises, so for a given stock the weight
  RISES with level — the player maintains an increasing baseline as they level up.
- Range ≈ `[50, 100]`: empty stock → 100 (just below survival `RestoreHP=110`,
  above everything else); near the watermark → `100 - 50/level` (50 at L1 → 99 at L50).
- Exact rational (float-free): `min` of `Fraction(equipped_qty)` and `Fraction(50, level)`;
  `weight = 100 - that`. Lifted to `Fraction` like `GrindCharacterXPGoal`, returned as
  `float` from `Goal.value`.

**Behavior note (accepted):** when the stack is low, `CraftPotions` outranks the grind
and most objectives (not survival). It is gated by craftability — when alchemy can't yet
make the potion, the goal is satisfied (no batch producible) and the bot grinds. So it is
naturally dormant until alchemy comes online, then stocks aggressively, interleaved with
grinding via the batch-and-replan loop.

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

1. `potion_supply_weight_pure(equipped_qty, level, max_stack, watermark_num,
   watermark_den) -> (num, den)` — the rational weight `max_stack - min(equipped_qty,
   watermark)` with `watermark = watermark_num/(watermark_den*level)` (i.e. 100/(2*level)).
   Returns an exact rational. Proven: bounded in `[max_stack - watermark_cap, max_stack]`,
   monotone non-increasing in `equipped_qty`, monotone non-decreasing in `level`.
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
- **`value`:** `potion_supply_weight_pure(equipped_qty_of_target, level, 100, 100, 2)` →
  float; `0.0` when `is_satisfied`.
- **`is_satisfied`:** `equipped_qty >= max_stack` OR no producible batch this cycle (the
  craft/buy/gather ladder below yields nothing actionable).
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

## Arbiter placement

`CraftPotionsGoal` is a weighted goal (not a fixed discretionary means), value `[50,100]`.
It sits below survival (`RestoreHP=110`) and above the grind/provision when the stack is
low — so a low stack preempts grinding to stock potions, exactly as the formula intends,
bounded by craftability and the batch-and-replan loop.

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

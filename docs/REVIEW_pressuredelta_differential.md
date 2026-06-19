# Differential review: `pressureDelta` reducer-drain faithfulness

**Date:** 2026-06-19. **Trigger:** Phase-4 adversarial review of the faithfulness
transience (Workstream A, `docs/PLAN_faithfulness_modeling.md`) flagged that
`Formal/Liveness/InventoryDynamics.lean`'s `pressureDelta` models every
pressure-reducing means as `inventoryUsed → 0`, and that this is **load-bearing** for
the `PressureTransience` counting (the high-pressure branch needs each drain to land
strictly below the 85% re-trigger watermark). This review investigated whether the
claim "a fired reducer drops inventory pressure below 85%" holds in production.

## Verdict: FALSIFIED

**None of the five reducer means guarantees post-action inventory pressure < 85%.**
The `pressureDelta(reducer) → 0` model is OPTIMISTIC and UNFAITHFUL. The real bot can
fire a reducer, apply it, and remain at ≥85% — the **full-of-useful-items livelock**
that `[[project_inventory_profiles]]` records as a real historical bug. The
transience proof (`ai_reaches_level_fiftyF_of_tenQuietPairs`) is sound *for the
→0-drain model*, but that model does not faithfully reflect production, so the
proof's "reaches level 50" must not be read as an unconditional claim about the
real bot.

`inventory_used = sum(state.inventory.values())` (world_state.py:168-170); a
reducer's pressure effect equals exactly the total quantity it removes.

| Means | Action (file) | What it removes | Post-pressure < 85%? |
|---|---|---|---|
| DEPOSIT_FULL (≥90%) | `DepositAllAction` deposit_all.py:47-61 | whole stack of every **bank-eligible** code (`select_bank_deposits`, bank_selection.py:77-94) — EXCLUDES keep-set: TASKS_COIN, task_code, hp-restore consumables, best weapon, all recipe-tree materials, profile_codes (bank_selection.py:45-74) | **NOT guaranteed** — if the keep-set sums to ≥85%, bag stays full and `is_satisfied` → DEPOSIT_FULL stops firing while pressured |
| DISCARD_HIGH (≥85%) | per-item batch `NpcSell`/`Delete` of EXCESS (discard_overstock.py:90-127) | only the **excess** above `max(profile_target, useful_quantity_cap)` (`overstock_excess`, inventory_caps.py:76-104) — NOT whole stacks; items at/under cap contribute 0 | **NOT guaranteed** (weakest case) — caps are large (CONSUMABLE_KEEP=999, recipe `max_demand·5`, equippables 1); a bag of capped items yields ~0 excess; after clearing excess `overstocked_items` is empty → guard goes SILENT at ≥85% |
| DISCARD_CRITICAL (≥95%) | same `DiscardOverstockGoal` as DISCARD_HIGH | identical excess-only logic | **NOT guaranteed** — same as DISCARD_HIGH, just a higher trigger; removal amount unchanged |
| SELL_PRESSURED (≥85%) | `NpcSellAction` (sell_inventory.py) | sells sellable stacks only until `inventory_free ≥ 5` (sell_inventory.py:54-58), NOT until empty | **NOT guaranteed** — target `free ≥ 5` is < 85% only when `inventory_max > ~33`; for a 100-slot bag, `used=95` (95%) satisfies the goal; also requires items tradeable + NPC buyer |
| CRAFT_RELIEF (≥70%) | `CraftAction` net-negative (craft_relief.py:82-98) | `quantity·(Σrecipe − 1)` units (net>0 gated) | targets <70%, but `quantity` clamps (mat-limited, batch_cap=10) can fall short in one cycle; re-fires next cycle |

Evidence: guards.py:155-179, means.py:65-96, inventory_caps.py:76-104 & 417-452,
bank_selection.py:45-94, craft_relief.py:82-159, and the `apply()` methods in
deposit_all.py:47-61, delete.py:32-41, npc_sell.py:47-64, crafting.py:49-90.

## Consequence for the faithful model

1. **`pressureDelta(reducer) → 0` is unfaithful.** A faithful model removes only the
   bounded amount each action actually removes (excess-above-cap for discard; eligible
   stacks for deposit; down-to-5-free for sell; net-craft units for craft).

2. **Under a faithful partial drain, the transience as proven is FALSE.** The
   `PressureTransience` counting concludes "k+1 is low-pressure" from `inventoryUsed =
   0`. With a partial drain the post-value can be ≥85%, so the conclusion fails. The
   bot genuinely can livelock at ≥85% with a bag of capped/kept items — exactly the
   `[[project_inventory_profiles]]` livelock.

3. **The honest residual is STRONGER than `DrainArmed`.** `Drainability.DrainArmed`
   (overstock ∨ sellable item exists) is INSUFFICIENT: a drainable item can exist whose
   removal does not drop below 85%. The faithful runtime obligation is
   **`EffectiveDrainArmed`**: infinitely often, when pressured, a reducer fires whose
   application drops pressure strictly below the 85% watermark. This is a genuine,
   checkable runtime property that **production does NOT guarantee** — where it fails,
   the bot livelocks. The bot's profile/keep-set tuning is what (usually) keeps it
   satisfied; it is not a theorem.

## Status / next steps

- The `ai_reaches_level_fiftyF_of_tenQuietPairs` capstone is UNCHANGED and still
  kernel-valid — it is a correct statement about the `→0`-drain model. What this review
  changes is the HONEST READING: the model's drain is optimistic, so the capstone is
  "reaches 50 modulo a faithful-drain gap", not an unconditional real-bot guarantee.
- Soundness boundary documented in `InventoryDynamics.lean` and
  `PressureTransience.lean`.
- FOLLOW-ON (not done): (a) weaken `pressureDelta`'s reducer branch to a faithful
  partial drain; (b) replace `DrainArmed` with `EffectiveDrainArmed` in the runtime
  residual; (c) re-derive `PressureTransience` — which will surface the livelock as the
  precise precondition where the bot can fail to reach 50. This converts the optimistic
  proof into an honest one whose residual names the real failure mode.

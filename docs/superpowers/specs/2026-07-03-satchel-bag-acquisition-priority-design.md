# Satchel Bag Acquisition Priority — Design

**Date:** 2026-07-03
**Status:** Approved (design), pre-implementation
**Approach:** A (value floor, lean) — see Alternatives.

## Problem

Robby (live, level 11) has an empty bag slot and never acquires a bag, despite
the game offering one and the machinery to obtain it being fully built and
merged.

### Evidence (trace `play-trace-Robby.jsonl`, 2026-07-01 → 2026-07-03)

- The only bag in game data is **`satchel`**: item level 5, crafted at
  gearcrafting level 5, recipe `{cowhide:5, feather:2, jasper_crystal:1}`. Bag
  equippable at character level 5 — Robby (L11) is well past it, so **level is
  not the blocker**.
- `jasper_crystal` (type `resource`, subtype `task`, no recipe/drop) is bought
  from `tasks_trader` for **8 `tasks_coin`**. `tasks_trader` is on the static map
  at (5,11) and is not an event NPC → a permanent, located vendor.
- The task-currency acquisition capability (C1–C4, merged to `origin/main`
  2026-06-22) works: `GatherMaterials(satchel)` fast-fails cleanly (0 nodes, not
  the old 641K-node burn), and `objective_step_goal` would route
  `ObtainItem(satchel)` → `ReachCurrencyGoal(tasks_coin, 8)` because
  `funding_target` populates.
- BUT across a full 143-cycle run, `ReachCurrency`, `AcceptTask`, `CompleteTask`,
  `tasks_coin`, and `NpcBuy` appear **0 times**. Robby has no active task and 0
  coins. Selected goals are dominated by `CraftPotionsGoal` (419), `RestoreHP`
  (358), `GrindCharacterXP`, `copper_ring`, `wooden_shield`.
- `GatherMaterials(satchel)` appears only as a **ranked candidate at priority
  0.0**, never selected.

### Root cause

The bag is a pure-efficiency item (only `inventory_space`, no combat stats). Its
cross-slot priority comes from `StrategyEngine._equip_gain`
(`ai/tiers/strategy.py:456-492`):
`max(0, strategic_value(item) - strategic_value(current))`, using
`strategic_value` with `(weights, budget) = strategic_weights(state, history)`.

`strategic_weights` derives `inventory_weight = (bank_roundtrip_cd /
inventory_max) × f_trip` from LEARNED deposit cadence. When the bot has not
deposited much (cold / low `f_trip`), `inventory_weight → 0`, so the bag's
`strategic_value → 0`. A zero-valued goal ties with grind/idle and is never
distinctly chosen. The bag therefore never becomes `chosen_root`,
`objective_step_goal` never runs on it, and the funding loop never starts.

The `EFFICIENCY_BUDGET` cap (`strategic_value` caps the efficiency block below one
combat-raw point) is **not** the bug — it is exactly the desired "bag ranks below
combat" behavior. The bug is the **absence of a floor**: an empty, craftable bag
slot should not be worth *zero* merely because deposit cadence is unlearned.

## Goal

Once a bag is craftable (gearcrafting ≥ 5, its own bootstrap — unchanged), the
empty bag slot should carry a **non-zero, below-combat** strategic value so the
arbiter pursues it during windows when no combat/gear upgrade is servable. The
already-merged funding route (`ReachCurrencyGoal`) plus existing sticky
commitment then accumulate `tasks_coin`, buy `jasper_crystal`, craft and equip
the satchel.

User intent (2026-07-03): "grinding tasks acceptable to be lower weighted than
combat — it just shouldn't be zero… once we have the coins to buy jasper,
prioritize the bag until equipped… larger inventory → larger craft batches + more
potions… want the satchel sooner rather than later."

## Non-goals (deferred to a separate epic)

- General "take tasks periodically for skillXP and gold" cadence.
- "Buy from NPCs in lieu of gathering" economics.

These are a broader economics change with their own spec. This spec is
satchel-acquisition only.

## Design (Approach A)

### Mechanism: a positive floor for the empty craftable bag slot

In the cross-slot priority path (`_equip_gain` / the empty-slot gap it feeds),
when **all** of:

- the slot is the bag slot and is currently **empty**, and
- a **craftable, attainable** bag exists for it (satchel; gearcrafting ≥ 5 to
  craft — attainability already handles the currency-buy leaf), 

then floor the slot's strategic gain to a **positive constant ≤
`EFFICIENCY_BUDGET`**. Candidate value: `EFFICIENCY_BUDGET` itself (the efficiency
ceiling) — the strongest efficiency goal, still strictly below any combat upgrade
(`combat_part ≥ SCALE > EFFICIENCY_BUDGET`).

Consequences:

- Bag gain > 0 → beats grind/idle (value 0) → chosen in any cycle where no combat
  upgrade is servable ("tasks from time to time").
- Bag gain ≤ `EFFICIENCY_BUDGET` < one combat point → any real combat/gear upgrade
  still preempts it (combat dominance preserved).
- Once chosen, `objective_step_goal` converts to `ReachCurrencyGoal(tasks_coin,
  8)`; sticky commitment (`arbiter_select` `_committed_repr` + progress-gated
  release) carries the accept→fight→complete grind to 8 coins — task-grinding
  makes progress (coins rise), so it will not zombie-release — then the next pass
  buys jasper, crafts, and equips the satchel. This provides "prioritize until
  equipped" without a new arbiter rung.

### Why not just raise `inventory_weight` / uncap

Removing the cap would let `inventory_space × parity_weight` (satchel has a large
inventory_space; parity weight = SCALE) overshoot and **dominate combat** — the
opposite of intent. Raising the learned `inventory_weight` floor globally would
also re-value runes/artifacts/haste and change broad cross-slot behavior. A
targeted floor for the empty craftable bag slot is the minimal, intent-matching
change.

## Formal-gate impact

The proved cores must stay sound:

- `strategic_value_pure` (Formal/StrategicValue.lean): a pure nonneg-monotone
  weighted sum. The floor is applied in the **impure wrapper** (`_equip_gain` /
  the gap policy), NOT inside `strategic_value_pure`, so the core and its
  differential binding are untouched.
- `decide_key` (Formal/DecideKey.lean) computes `protection = max(0,
  strategic_value(item) − strategic_value(current))`. The floor must be placed so
  it does **not** silently alter `decide_key`'s protection term in a way that
  breaks the proved ladder/tiebreak. **Open placement question for the plan:**
  floor the *gap/priority* used for root ranking without changing the
  `strategic_value` inputs that `decide_key` consumes — i.e., the floor is a
  ranking-policy adjustment, not a redefinition of item value.
- `ObjectiveGap` / `GearPolicy` (`armor_strictly_dominates_empty_slot`): the
  floor ≤ `EFFICIENCY_BUDGET` keeps combat strictly dominant, so the dominance
  theorems are preserved. Re-verify the nonneg bound still holds with the floor.

Expected gate work: a new small pure decision helper (e.g. `bag_floor_pure` /
empty-craftable-bag predicate → floored gain) with its own Formal model +
differential tuples + mutation coverage, per the repo rule that new decision
cores ship extracted+proven. No weakening of existing theorems.

## Verification plan

1. `uv run artifactsmmo plan Robby` (offline) shows `ReachCurrency(tasks_coin, 8)`
   selected once combat/gear upgrades are not servable (previously never
   appeared).
2. Offline/short live run: Robby accumulates `tasks_coin`, buys `jasper_crystal`,
   crafts and equips `satchel`; bag slot becomes non-empty.
3. Regression: a servable combat/gear upgrade still preempts the bag (bag never
   outranks a real combat upgrade); no planner node-burn regression on
   `GatherMaterials(satchel)`.
4. Full formal gate green (build / no-sorry / axiom-lint / manifest / contracts /
   differential / mutation); ≥90% coverage on new code.

## Risks & fallback

- **Commitment abandons mid-accumulation.** If sticky commitment releases the bag
  root before 8 coins (e.g. HP pressure, combat veto), coins may sit unused and
  the bag stall. Mitigation: this is the trigger to escalate to **Approach B** — a
  proved affordability-gated escalation (`coins ≥ price ∧ bag-slot-empty ⇒
  elevated priority until equipped`). Not built now; add only if verification
  shows abandonment.
- **Combat upgrades always servable** → bag perpetually deferred. Acceptable per
  user ("lower weighted than combat"); the first upgrade-free window acquires it.

## Alternatives considered

- **B: value floor + explicit escalation core.** Matches "prioritize until
  equipped" exactly, independent of commitment behavior, but adds a proved
  decision core (Lean + differential + mutation). Deferred as the fallback above.
- **Uncap efficiency for bags.** Rejected: overshoots and dominates combat.
- **Raise global `inventory_weight` floor.** Rejected: re-values all efficiency
  gear, broad behavior change.

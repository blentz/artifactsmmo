# Deterministic full craft-plan — design

**Date:** 2026-06-23
**Branch (proposed):** `feat/deterministic-craft-plan`
**Status:** approved design, pre-spec-review

## Problem

Crafting a craftable item is a fixed recipe tree — `copper_dagger = 6 copper_bar = 60 copper_ore`, and that never changes until the seasonal server reset. Yet the planner still pays a 50K-node A* search to plan it whenever the cheap deterministic generator refuses the state. The macro-research analyzer (2484 cycles, char Robby, levels 1→8) measured the cost concentration empirically:

| goal type | total A* nodes | share |
|---|---|---|
| GatherMaterials | 4,326,467 | 97.6% |
| RestoreHP | 105,621 | 2.4% |
| GrindCharacterXP / UpgradeEquipment / CraftRelief | <1000 each | ~0% |

60% of the GatherMaterials cost is 123 expensive replans concentrated in three craftable items: **copper_ring (1.78M nodes), copper_helmet (570K), copper_pickaxe (255K)**. The goal-repr volatility table showed `copper_helmet` appearing as 18 distinct reprs (`{copper_helmet:17}`…`{copper_helmet:34}`) — one recipe, eighteen quantities, re-planned from scratch each time.

The earlier "macro-chain" idea is **refuted by the same data**: across 16 sessions of one character, zero progression chains recurred (every candidate `occurrences=1`) — exact-sequence chains are too brittle (HP/fight variance) to ever match. The right cacheable unit is not the progression chain; it is the **static per-item recipe tree**.

## Root cause (grounded in code)

A full transitive recipe-cost function already exists — `closure_demand` / `_closure_demand` (`recipe_closure.py:71,133`) computes the quantitied gather-craft tree (copper_dagger → 6 bar → 60 ore). Bank-aware net subtraction exists — `shopping_list` / `fully_covered_materials` (`shopping_list.py`). Both are **recomputed every cycle (no memo)** but are cheap (O(closure)).

The expensive A* is **not** the closure cost; it is the `next_craft` generator's refusal branches (`generate_next_craft_action`, `craft_plan_gen.py`), which on refusal fall through to `GOAPPlanner.plan` (`planner.py:62`). The decisive refusal for copper_ring/helmet:

- **Bank gate** (`craft_plan_gen.py:134-144`): when a craftable INTERMEDIATE (e.g. `copper_bar`) sits in the bank and inventory is short, the generator can't emit a `WithdrawItemAction`, returns `None`, and A* does `Withdraw→Craft` at ~50K nodes.
- Secondary refusals (skill gate `:114-115`, no workshop `:116-117`, monster-drop/NPC leaf `:118-121`) — these are genuinely non-deterministic and stay on the fallback path.

The generator also only emits **plan[0]** (`next_craft_target_pure`, `next_craft_core.py:28`), never the full plan.

## Goal

Make craftable obtain-goals produce their plan deterministically from the static recipe tree + owned-netting (inventory **and** bank), so they never fall to A* over a bank gate. Shrink A*'s job to the genuinely non-deterministic leaves; keep it as a safety-net fallback throughout.

## Design

### Piece 1 — static recipe-cost memo (Phase A)

Memoize the static full transitive cost per item: `full_cost(item) = closure_demand(item, 1)` keyed on item code, invalidated only on game-data reload. A small cache object owned by / alongside `GameData` (recipes are static after load). Pure read for every downstream consumer (`relevant_actions`, the generator, `inventory_profile`, `task_reservation`). This is the "compute once" cache — the clean foundation. It is the cheap part; it does not by itself stop the A* fallback.

### Piece 2 — full-plan generator with banked-intermediate Withdraw (Phase B)

Extend the proven deterministic core, staying close to its existing descent rather than introducing a new topological emitter (the descent already interleaves gather/craft to respect bag capacity — "gather 10 ore → smelt 1 bar → repeat ×6 → craft", never "gather 60 then smelt 6"):

1. **New action kind in the core.** Extend `next_craft_target_pure` / `_next` (`next_craft_core.py`) so that when the deepest still-short input is a craftable intermediate present in the **bank**, it emits a new `"withdraw"` `NextAction` instead of the descent dead-ending. Inventory-then-bank netting: gather/craft only the shortfall after both. This removes the bank-gate refusal at its root.

2. **Full-plan driver.** Add a driver that iterates the single-step descent to completion against a simulated owned-state (apply each emitted `NextAction`'s effect to a local owned-copy, accumulate the action list) until the target is satisfied. Output: the complete ordered remaining plan (`Withdraw` / `Gather` / `Craft`). Phase-1's `PlanCache` then commits to this chain and executes it step-by-step (the "calculate once, reuse" the user asked for — already shipped).

3. **`generate_next_craft_action` wiring** (`craft_plan_gen.py`): drop the bank-gate refusal (`:134-144`); map the new `"withdraw"` kind to a concrete `WithdrawItemAction` from `goal.relevant_actions`; emit the full plan list. Keep the remaining refusals (skill gate, no workshop, monster-drop/NPC leaf) — those route to LevelSkill / combat / NPC machinery and retain the A* fallback.

### What stays on A* (unchanged)

Skill-gated intermediates, monster-drop leaves, NPC-buy / currency leaves. These are not fixed deterministic craft chains; A* (or the skill-grind / combat / NPC paths) remains responsible. The fallback is retained everywhere, so nothing can regress to "no plan" — at worst it degrades to today's behavior.

## Formal scope

`next_craft` is formally gated (NextCraftAction proof-concept index; differential + mutation). This feature extends the proven decision logic, so the proofs extend in lockstep (driven by the **formal-development** skill):

- **Core `_next` + withdraw branch** — extend the Lean model of the descent to include the bank/withdraw case; re-establish the existing correctness property (the emitted next-action is a valid step toward the target) over the widened input space. Differential test + mutation must cover the new branch.
- **Full-plan driver** — new decision logic needing its own proof: **termination** (the descent iteration is fuel-bounded by the closure size × quantity and strictly reduces a measure each step) and **correctness** (applying the emitted plan in order, from the given owned-state, yields `owned[target] ≥ qty`). This is the meaty proof; it is liveness-flavored (terminates + reaches goal).
- **Memo (Phase A)** is pure data caching of an already-proven function (`closure_demand`); it needs an equality-to-uncached differential check, not new decision proofs.

Gate discipline (per repo): `formal/gate.sh` green; differential + mutation enforce the Python computes the same function as the Lean model; never weaken a theorem to pass.

## Phasing

- **Phase A — static cost memo.** Memoize `closure_demand` per item; wire the hot consumers to read it. Differential check vs uncached. Low risk, immediately useful. Ship + gate.
- **Phase B — full-plan generator.** B1: core `withdraw` branch + its formal extension. B2: full-plan driver + termination/correctness proof. B3: `generate_next_craft_action` wiring (drop bank-gate refusal, emit full plan). Re-run `formal/gate.sh`. This is the CPU win.
- A* fallback retained throughout; each phase independently shippable and gate-green.

**B2 may be redundant — gate it on measurement.** With Phase-1's `PlanCache` already committing to a plan and executing it step-by-step, the `withdraw` branch alone (B1 + B3) makes the generator emit the correct plan[0] (including `Withdraw`) every replan, which Phase-1 then caches — that may already drop the A* cost to zero without a separate full-plan driver. Build B1+B3 first, re-measure with `macro-research`; only build B2 (full-plan driver + its termination/correctness proof — the most expensive formal work) if the bank-gate items still show A* nodes. Do not build B2 speculatively.

## Out of scope

- Macro-chain learning (refuted by data — the analyzer killed it).
- Skill-gated / monster-drop / NPC / currency craft leaves (stay on existing machinery + A*).
- Touching the A* planner internals (it remains the unchanged fallback).

## Success criteria

- copper_ring / copper_helmet / copper_pickaxe obtain-goals plan with **0 A* nodes** when their only blocker was a banked intermediate (measured by re-running `macro-research` on fresh post-feature data: GatherMaterials total nodes drops sharply).
- `formal/gate.sh` green; differential + mutation cover the withdraw branch and the full-plan driver.
- 100% coverage, 0 warnings, 0 skips (repo gate).
- No regression: any state the generator still refuses falls to A* exactly as today.

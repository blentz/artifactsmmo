# Combat Survivability — Design Spec

**Date:** 2026-06-30
**Status:** Approved knobs; pending spec review → implementation plan

## Problem

Live trace `play-trace-Robby.jsonl` (last run, L3 Robby, root `ReachCharLevel(5)`):
the bot fought `green_slime` (~80% win — losses traced to **starting fights at low HP**:
fight cycles at hp 4 / 16 / 28). One loss dropped `green_slime`'s observed
`success_rate` below the combat veto threshold (`WIN_RATE_THRESHOLD = 0.9`), so
`is_winnable(green_slime, history)` returned False → `combat_picker` returned `None`
→ `strategy_driver.py:721` (`if ctx.combat_monster is None: return None`) stood the
char-level objective down → the arbiter fell through to the discretionary gear tier →
`GatherMaterials(copper_helmet)`, which awards **zero character XP**. Livelock
oscillation: win a few slimes → success_rate climbs > 0.9 → grind re-enabled → lose
one → veto → gear grind → repeat.

## Goals

1. Stop one avoidable loss from stranding the only-available XP grind.
2. Stop fights from *starting* at low HP (the avoidable-loss source).
3. Bring health potions to genuinely marginal fights so they survive.

## Design (3 parts)

### Part 1 — Heal before fighting (`CRITICAL_HP_FRACTION 0.25 → 0.75`)

Raise the HP-critical preempt threshold. `RestoreHPGoal` returns its ceiling value
(110, preempts all) and the guard/strategy interrupt fires when `hp_percent < 0.75`,
so fights start near-full HP.

**Blast radius (mechanical mirror — values only, no proof restructure):**
- `src/artifactsmmo_cli/ai/thresholds.py:20` — `CRITICAL_HP_FRACTION = 0.75`
- `formal/Formal/Liveness/ProductionLadder.lean:68` — `CRITICAL_HP_NUM := 75` (+ doc comment)
- `formal/diff/mutate.py:3136-3137` — mutation anchor string `0.25 → 0.75`; pick a
  mutant value distinct from 0.75 (e.g. 0.50)
- `tests/test_ai/test_goals.py:59` and any threshold test asserting 0.25

**Why the liveness proofs survive:** every Lean use of `CRITICAL_HP_NUM` is an
"HP-full ⇒ critical guard does NOT fire" lemma of the form
`¬ (CRITICAL_HP_DEN * maxHp < CRITICAL_HP_NUM * maxHp)`, i.e. `¬ (100 < NUM)`, which
`omega` closes for any `NUM < 100`. 25 → 75 keeps `NUM < DEN`, so all proofs close.
`lake build` of the liveness library + the mutation run for the changed anchor are
the verification.

**Interaction checked:** `player.py:1411 _is_winnable` projects HP to `max_hp` before
the winnability check, so the 2026-06-06 "parked at 76/130 for 278 cycles, 0 fights"
deadlock (winnability narrowing at moderate HP) does NOT recur — winnability is
HP-independent. Raising the rest threshold only makes the bot rest more often, which
is the intent.

### Part 2 — Combat veto lowered (`WIN_RATE_THRESHOLD 0.9 → 0.4`) — DONE

Already implemented (prior turn, not yet committed). Veto now fires only when a
monster is lost more often than won (< 0.4), so marginal-but-grindable monsters stay
valid targets instead of stranding the grind. Pure-Python constant; no Lean/diff
impact (picker/cascade proofs are abstract over the Bool verdict). Tests updated:
`test_is_winnable_keeps_marginal_grindable_winrate` (80% → winnable),
`test_is_winnable_vetoes_genuine_loser` (30% → vetoed). Carried into this work's commit.

### Part 3 — Provision potions for marginal fights

**Trigger (decided):** observed only. A target is *marginal* when
`history.sample_count(Fight(m)) >= MIN_WIN_SAMPLES` (5) **and**
`history.success_rate(Fight(m)) < MARGINAL_WINRATE_THRESHOLD` (0.95). Cold/unknown
monsters get no potion — Part 1's heal-to-75% covers early fights.

**Carry method (decided):** `quantity` in one utility slot, scaled by difficulty. The
API (`EquipSchema.quantity`, "applicable to utilities only", `minimum 1`, `maximum 100`,
default 1 — `openapi.json`) supports stacking; the current `EquipAction.execute` never
passes it. Add a `quantity` field to `EquipAction`; load the difficulty-scaled count
into `utility1_slot`. The one-copy-per-code dup guard is left UNTOUCHED — we never put
the same code in both slots; `utility2_slot` stays free for a future different
consumable.

**Quantity scales with win-rate (decided — no fixed count):** easy marginal fights take
~1 potion; harder fights take more, up to a FULL STACK at 50% win-rate.
`UTILITY_SLOT_MAX_STACK = 100` is the full stack (sourced from `openapi.json`
`EquipSchema.quantity.maximum`, cited — not a guessed default).

```
desired_qty(win_rate):
  win_rate >= MARGINAL_WINRATE_THRESHOLD (0.95) -> 0          # not marginal
  win_rate <= FULL_STACK_WINRATE        (0.50)  -> MAX_STACK  # full stack (clamp; veto floor is 0.40)
  else (0.50 < wr < 0.95):
    fraction = (0.95 - wr) / (0.95 - 0.50)                    # 0..1, rises as wr falls
    qty = max(1, ceil(fraction * MAX_STACK))                  # monotone-decreasing in wr, >=1
```

Monotone: lower win-rate ⇒ at least as many potions. Equipped count is
`min(desired_qty, held_heal_qty)` — never more than the bot holds.

**Supply scales too:** a fixed `HEAL_STOCK_FLOOR = 5` cannot feed a 100-potion stack, so
`MaintainConsumablesGoal`'s heal-stock target becomes `clamp(desired_qty_for_active_target,
HEAL_STOCK_FLOOR, MAX_STACK)` — it crafts/holds toward the active marginal target's need.
Provisioning still equips best-effort `min(desired, held)` meanwhile, so the grind is
never blocked waiting for a full stack.

**Heal choice:** the strongest health item the bot currently holds (inventory item
with `hp_restore > 0`, max restore). Reuses the existing heal-identification helpers
(`consumable_supply.heal_stock` / `ItemStats.hp_restore`).

**Reactive depletion:** utility-slot quantity is NOT modeled in `WorldState`
(`equipment` maps slot → code, no count). Each cycle refreshes equipment from the
server, so when the game auto-consumes the stack to zero mid-fight the slot reads empty
and the rule re-provisions (refill-when-empty). Per-cycle top-up of a partially-drained
stack needs slot-quantity in `WorldState` — deferred (see Out of scope).

**Supply:** the existing `MaintainConsumablesGoal` (stocks heals to `HEAL_STOCK_FLOOR`
= 5 when combat is active and a heal is craftable) feeds the inventory. If no heal is
held and none is craftable now, provisioning no-ops and the bot fights unprotected —
the grind is never blocked on potion supply (Parts 1 + 2 still protect it).

**Pure decision core (proven, per `ai/` standard):**
`marginal_potion_qty_pure(samples, success_rate, min_samples, win_threshold,
full_stack_winrate, max_stack, utility_slot_filled, held_heal_qty) -> int` returning the
equip quantity (`0` = none: not marginal, cold-start, slot already filled, or no heal
held). Implements the `desired_qty` curve above, clamped by `held_heal_qty`. Proven
properties: bounded `0 ≤ qty ≤ max_stack`; `qty ≤ held_heal_qty`; monotone
non-increasing in `success_rate` across the marginal band; `qty = 0` above the threshold
and when the slot is filled. Lean model + `formal/diff` differential test +
`formal/diff/mutate.py` anchor, mirroring the other combat cores. The chosen heal code +
slot are resolved by glue (strongest held heal → `utility1_slot`).

**Hook (Option A):** in `strategy_driver.objective_step_goal`, for a `ReachCharLevel`
step with `ctx.combat_monster` set: if the provisioning rule fires, return a new
`ProvisionMarginalFightGoal(target_monster)` whose `relevant_actions` is the
`EquipAction(heal → utility1_slot, quantity=N)` and which `is_satisfied` once the slot
holds a heal (or the target is no longer marginal). Otherwise return
`GrindCharacterXPGoal` as today. Across cycles: equip-cycle → fight-cycles → potion
consumed → slot empty → equip-cycle. Bounded reactive loop, not a livelock (each
provision enables multiple fights; no-op when no heal held).

## New / changed units

| Unit | Kind | Change |
|---|---|---|
| `thresholds.py` | const | `CRITICAL_HP_FRACTION = 0.75` |
| `ProductionLadder.lean`, `mutate.py` | formal mirror | `CRITICAL_HP_NUM = 75`, anchor |
| `combat.py` | const (done) | `WIN_RATE_THRESHOLD = 0.4` |
| `actions/equip.py` `EquipAction` | behavioral | add `quantity: int = 1` field; pass to `EquipSchema`; `is_applicable` requires `inventory[code] >= quantity` |
| `ai/marginal_potion_qty.py` | new pure core | `marginal_potion_qty_pure(...) -> int` (win-rate-scaled) |
| `ai/goals/provision_marginal_fight.py` | new goal | `ProvisionMarginalFightGoal(target_monster)` |
| `consumable_supply.py` / `MaintainConsumablesGoal` | behavioral | heal-stock target = `clamp(desired_for_active_target, HEAL_STOCK_FLOOR, MAX_STACK)` |
| `strategy_driver.py` | glue | route to provision goal before grind when rule fires |
| `formal/Formal/.../MarginalPotionQty.lean` | new proof | model + theorems (bounds, monotone, clamp) |
| `formal/diff/test_marginal_potion_qty_diff.py` | new diff | Python↔Lean lockstep |
| constants | new | `MARGINAL_WINRATE_THRESHOLD = 0.95`, `FULL_STACK_WINRATE = 0.50`, `UTILITY_SLOT_MAX_STACK = 100` (cited: `openapi.json` EquipSchema.quantity.maximum) |

## Testing

- Unit: `EquipAction` quantity (applicable gate on `inventory[code] >= quantity`;
  `EquipSchema.quantity` passed); `marginal_potion_qty_pure` curve (cold → 0,
  ≥0.95 → 0, just below 0.95 → 1, midband → interpolated, ≤0.50 → 100, clamp to
  `held_heal_qty`, slot-filled → 0, monotone non-increasing in win-rate);
  `ProvisionMarginalFightGoal` value ordering, `is_satisfied`, `relevant_actions`;
  `MaintainConsumables` stock-target scaling.
- Part 1: `test_goals.py` RestoreHP threshold; `lake build` liveness; mutation anchor.
- Part 2: existing combat veto tests (done).
- Differential + mutation gate for the new pure core.
- Coverage: 0 errors / 0 warnings / 0 skipped / 100% (project bar).

## Out of scope (future)

- Non-health consumables (damage/boost utilities), `utility2_slot` strategies — user
  deferred to a future brainstorm.
- Modeling exact utility-slot quantity depletion in `WorldState`.
- Same-code-in-both-utility-slots: blocked by an in-code dup guard citing a 2026-06-14
  HTTP 485 probe that conflicts with the maintainer's understanding; needs a live probe
  to resolve before relaxing the guard. Not required by the chosen carry method.

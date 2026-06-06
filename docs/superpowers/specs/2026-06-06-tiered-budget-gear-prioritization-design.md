# Design: Tiered+Memoized Planning Budget + Event-Driven Gear Prioritization

Date: 2026-06-06
Status: Approved (brainstorming) — pending implementation plan
Related: `docs/PLAN_planner_liveness.md` (depth-bound proof + reachability gate,
landed in commit c484588)

## Problem

The AI player's first cycle (and ongoing cycles) stall because the arbiter runs
the GOAP planner once per candidate goal, each bounded by a 90s budget, and
several candidates per cycle are unfindable in 90s. Two distinct causes:

1. **Depth-unreachable** goals (e.g. `UpgradeEquipment(copper_boots)`: 80 gathers
   > max_depth 15). Already fixed by the proven depth-based reachability gate
   (`min_gathers`, commit c484588).
2. **Width-unfindable** goals (e.g. `LevelSkill(weaponcrafting->5)`: reachable
   within max_depth 100 but the forward A* explores 650k nodes without finding a
   plan in 90s). No cheap per-goal predicate can detect this — the search is just
   too wide. THIS spec addresses (2).

A second, linked requirement: gear progression is *situationally* the correct
priority. After a level-up new equipment tiers unlock, and losing a fight the
planner predicted winnable signals under-gearing. In both cases the bot should
prioritize upgrading equipment over grinding XP until its gear is
level-appropriate — and that important gear chain must NOT be skipped by the
width fix's "doomed goal" memoization.

## Goals

- Bound wasted planning so a cycle does not spend N×90s on unfindable goals.
- Keep legitimately deep-but-reachable goals findable when they are the only
  option.
- Prioritize the gear chain after a level-up or a predicted-winnable fight loss,
  until equipment is level-appropriate, overriding the width fix's memoization.
- Preserve the existing arbiter tier semantics (guards > collect-reward >
  objective-step > discretionary) and the landed depth-gate.

## Non-goals (YAGNI)

- Per-slot parallel gear planning.
- Predictive "next fight will be lost" modeling.
- Adaptive tuning of the cheap-pass budget or memo window (constants, tunable).
- Re-architecting the planner's search (no heuristic/dedup rework).

## Architecture

Four cooperating pieces, smallest-responsibility each:

### 1. Planner budget parameterization

`GOAPPlanner.plan(state, goal, actions, game_data, history, *, budget_seconds=None)`
gains an optional keyword. `None` ⇒ the existing module constant
`_SEARCH_BUDGET_SECONDS = 90.0`. Existing callers are unaffected (default
preserves today's behavior). `budget_seconds` replaces the local `deadline`
computation only. This is the single lever the tiered passes use.

### 2. Tiered selection (StrategyArbiter)

The arbiter's `select` planning loop becomes budget- and memo-aware. Behavior:

- **Cheap pass.** Walk candidates in band order (guards, collect-reward,
  objective-step + fallback chain, discretionary), EXCLUDING the always-on
  `WaitGoal`. Plan each non-memoized candidate at `B1` (default `1.0s`). The
  first candidate that returns a non-empty plan is selected and the walk stops
  (band priority is preserved within the pass).
- **Escalation pass.** Only if the cheap pass selects nothing, re-walk in band
  order at the FULL budget (`None` ⇒ 90s). First non-empty plan wins. This
  preserves the ability to find a legitimately deep, reachable goal when it is
  the only real option.
- **Wait.** Selected only if both passes find nothing (the existing last-resort
  invariant — `WaitGoal` is special-cased to `[WaitAction()]`).
- The `WaitGoal` candidate is never planned in either pass; it is the structural
  fallback, appended after both passes fail.

### 3. Doomed-goal memo (remembered-doomed)

Owned by the arbiter (per-session state), keyed by `repr(goal)`:

- When a goal times out (cheap OR full budget) with no plan, record
  `(signature, set_at_cycle)` where
  `signature = (level, frozenset(skills.items()))` — the WorldState dimensions
  that *unlock new plannability* for the discretionary/skill goals the memo
  governs (a skill/craft goal that is width-unfindable at a given character +
  skill level stays unfindable until one of those levels changes). Inventory- or
  bank-driven plannability changes are NOT in the signature (full inventory
  composition churns every gather, which would defeat the memo); they are caught
  instead by the K-cycle re-probe (bounded staleness) and, for the gear chain
  specifically, by the latch/guard path which bypasses the memo entirely.
- A memoized goal is SKIPPED in both passes (treated as not-currently-plannable)
  while its memo is valid.
- Memo is invalidated (goal retried) when: the goal's recomputed signature
  differs from the stored one, OR `current_cycle - set_at_cycle >= K`
  (default `K = 20`) as a safety re-probe.
- A goal that plans successfully clears its memo entry.

Rationale: steady-state cycles skip known-unfindable goals (fast) but a goal that
becomes plannable (skill leveled, materials gathered) is retried promptly via the
signature change; the K-cycle re-probe bounds staleness.

### 4. GEAR_REVIEW guard + latch (event-driven prioritization)

A new `GuardKind.GEAR_REVIEW` in the guards tier, ordered BELOW the survival
guards (HP_CRITICAL, REST_FOR_COMBAT, DISCARD_*, DEPOSIT_FULL, CRAFT_RELIEF) and
ABOVE the objective-step / discretionary tiers. It fires only while the latch is
active and a craftable gear upgrade exists.

**Mapping** (`map_guard` for GEAR_REVIEW): pick the best craftable gear upgrade
for the character's level (existing `find_craftable_upgrade` selection). If its
materials are in hand/bank ⇒ `UpgradeEquipmentGoal(committed_target=...)`;
otherwise ⇒ `GatherMaterialsGoal` for that target's still-needed materials. This
is how GEAR_REVIEW cooperates with the depth-gate: while materials are missing,
`UpgradeEquipment` itself is depth-unreachable, so the guard drives
`GatherMaterials` (which scales its own max_depth) to accumulate mats across
cycles, then switches to `UpgradeEquipment` once they are in hand.

**Latch** (player-owned state, persisted across cycles like blocker/commitment
state):

- SET when, comparing the post-refresh state to the previous cycle: `level`
  increased, OR the last executed action's outcome was `error:fight_lost`.
- CLEAR when no craftable upgrade remains for ANY equippable slot
  (`find_craftable_upgrade` returns None for every slot) — gear is as good as it
  gets for this level. Naturally re-arms on the next level-up.
- The latch is a simple boolean re-evaluated each cycle: once set, it stays set
  until the clear condition holds.

**Override of the memo:** because GEAR_REVIEW is a guard, it is evaluated FIRST
and (per the tiered rules below) the guard tier is planned at the FULL budget and
is NOT subject to the doomed-memo. So the important gear chain is never skipped
as "doomed" while the latch is active.

### Tier/budget interaction (the load-bearing ordering)

- Guard-tier candidates (including GEAR_REVIEW) are planned at the FULL budget
  and bypass the memo. Guards are few and safety-critical; spending full budget
  on them is correct and they rarely time out.
- Collect-reward, objective-step, and discretionary candidates go through the
  cheap pass → escalation → memo machinery in Section 2/3.

This keeps survival and gear prioritization responsive while bounding the wide
discretionary/skill goals that caused the stall.

## Data flow (per cycle)

1. Player refreshes WorldState; computes `level_increased` (vs prev cycle level)
   and reads `last_outcome`.
2. Player updates the gear-review latch (set/clear per Section 4).
3. Player builds actions, selection context (now including `gear_review_active`).
4. Arbiter `select`:
   a. Guard tier (incl. GEAR_REVIEW if latched) at full budget, memo-bypassed.
   b. If no guard plans: cheap pass over collect/step/discretionary (excl Wait).
   c. If cheap pass empty: escalation pass at full budget.
   d. Else Wait. Timed-out goals memoized.
5. Player executes `plan[0]`, records outcome (feeds next cycle's latch).

## Error handling

- `error:fight_lost` is an existing outcome (combat.py raises
  `RuntimeError("fight_lost: ...")`, surfaced by the loop). The latch reads it;
  no new exception handling. (No `except Exception`.)
- A goal whose planning raises is not special-cased here; existing behavior
  preserved.
- Empty/None game data fails loudly per project rules — no defaulting.

## Formal verification

Extend `formal/` (core-only where possible, mathlib only in Liveness/ if needed):

- **TieredSelection** invariants (new module, computable model of the two-pass
  walk over an abstract candidate list with a `plansWithin : Candidate → Budget →
  Bool` oracle):
  - `cheap_winner_is_highest_band_cheaply_plannable` — the cheap pass returns the
    first (highest-band) candidate that plans within `B1`.
  - `escalation_runs_iff_cheap_empty` — the full-budget pass is entered iff no
    non-Wait candidate plans within `B1`.
  - `wait_only_when_both_empty` — `Wait` selected ⇒ no non-Wait candidate plans
    within the full budget.
  - `memo_skip_sound` — a memoized-skipped candidate, under unchanged signature,
    would also have produced no plan (the memo never hides a now-plannable goal
    whose signature is unchanged — i.e. plannability is a function of signature
    for the modeled goal classes; stated as the contract the memo relies on).
- **GearLatch** state machine (computable):
  - `latch_set_on_levelup_or_loss` — set transition characterization.
  - `latch_clear_iff_no_craftable_upgrade` — clear transition characterization.
  - `latch_monotone_until_clear` — once set, stays set until the clear predicate
    holds (no spurious mid-cycle clears).
  - `gear_review_outranks_grind_below_survival` — ordering invariant: GEAR_REVIEW
    precedes grind/discretionary and follows survival guards.
- Preserve existing `ArbiterSelect.lean` role theorems (Manifest + Contracts);
  extend, do not weaken. Register new role theorems in `Manifest.lean` and pin
  exact statements in `Contracts.lean`.
- Differential + mutation for any new pure core extracted (e.g. the latch
  predicate, the signature function) per the formal-development gate.

## Testing

- TDD for every new function/branch. Unit suite at the repo's 100% bar for new
  code (carve-outs justified, none expected).
- Arbiter tests: cheap-pass selects the highest-band cheap goal; escalation only
  when cheap empty; Wait only when both empty; memoized goal skipped then retried
  on signature change and after K; guard-tier full-budget bypass.
- Latch tests: set on level-up, set on fight-loss, clear when no craftable
  upgrade, persistence across cycles, GEAR_REVIEW mapping (gather vs upgrade by
  material availability).
- Integration smoke (dry-run, real-ish fixture): a first cycle with the 8
  LevelSkill candidates completes in seconds, not minutes; a post-level-up cycle
  selects the gear chain over grind.

## Defaults (tunable constants)

- `B1` cheap-pass budget: `1.0` seconds.
- `K` memo re-probe window: `20` cycles.
- Full budget: unchanged `_SEARCH_BUDGET_SECONDS = 90.0`.

## Risks / open items

- `B1 = 1.0s` may miss a goal that needs 1–3s but is the only cheap option; it is
  caught by escalation only if NOTHING else plans cheap. Accepted per the
  liveness-first/hybrid decision; revisit `B1` if traces show useful goals
  consistently just over `B1`.
- Memo soundness assumes a discretionary/skill goal that is width-unfindable at a
  given `(level, skills)` stays unfindable until one of those changes. A goal
  whose plannability flips on a dimension outside the signature (inventory/bank
  composition, position, cooldown) could be transiently hidden until the K
  re-probe. This is bounded (≤ K cycles) and does not affect the gear chain (it
  bypasses the memo via the latch/guard). If traces show a useful goal hidden
  this way, widen the signature for that goal class rather than globally.
- GEAR_REVIEW at full budget every latched cycle: bounded because the latch
  clears once gear is level-appropriate, and the guard maps to GatherMaterials
  (which plans fast) while mats are missing.

# Planner batching + macro edges — design

**Date:** 2026-08-13
**Branch (proposed):** `feat/planner-batching-macro-edges`
**Status:** approved design, pre-implementation

**Supersedes:** `2026-06-06-tiered-budget-gear-prioritization-design.md` (the
two-pass cheap/full budget it introduced is removed here).
**Closes:** `2026-06-23-plan-cache-macro-learning-design.md` Phase 2, taking its
deferred **Phase 2b** (composite macro-operator) rather than Phase 2a.

---

## Problem

Live evidence, five characters, 31.3 h, ~1600 cycles each
(`play-trace-*-20260812-*.jsonl`).

`UpgradeEquipment(greater_wooden_staff->weapon_slot)` was the rank-1 objective
on every cycle for four of the five characters. It produced a plan on 0 of 955
cycles for R2D2 and 2 of 791 for C3P0. Verbatim, R2D2 cycle 0:

```
tried: staff            nodes 3873 depth 8 timed_out TRUE  plan_len 0  priority 35
       iron_shield      nodes 2523 depth 7 timed_out TRUE  plan_len 0  priority 35
       Grind(red_slime) nodes 3    depth 1 timed_out false plan_len 1  priority 45
selected: GrindCharacterXP(red_slime)
```

The materials were never the obstacle. The shared bank held 16 `spruce_plank`
and 98 `blue_slimeball` against a recipe needing 6 and 2, and three of the four
characters were carrying 6–8 planks already.

### Fault 1 — the gather edge has no quantity

`CraftAction`, `WithdrawItemAction`, `RecycleAction` and `NpcBuyAction` all
carry a `quantity`. `GatherAction` and `FightAction` do not: one node mints one
unit. `greater_wooden_staff` needs 6 `spruce_plank`, each 10 `spruce_wood`, so
the from-scratch chain is 60 sequential gather nodes at depth 60 against
`Goal.max_depth = 32`.

The plan is therefore not slow to find. It is **unreachable by construction**,
and A* spends its whole budget proving nothing.

### Fault 2 — the two-pass budget converts that into a silent substitution

`StrategyDriver` runs a cheap pass (`CHEAP_BUDGET_SECONDS = 10.0`) over the
ranked candidates and escalates to the 300 s budget only `if chosen is None`.
`select_pure` takes the first candidate that plans. `GrindCharacterXP` always
plans, in 2–3 nodes. So:

- the escalation pass is unreachable in practice — a fallback grind is always
  available, so `chosen` is never `None`;
- `try_plan_cheap` passes `mark_on_timeout=False`, so `DoomedMemo` never records
  the failure and the same search re-explodes every cycle (R2D2: two exploding
  searches × 955 cycles ≈ 5.3 CPU-hours);
- nothing in the trace says the top-ranked objective was abandoned. The run
  reads as "the bot chose to grind XP".

### Consequence

Skill XP is not a first-class objective anywhere. Across all five traces the
strategy ranking contains only `category: gear` and `category: char_level`;
`LevelSkill` enters solely as leg 0 of an `UpgradeEquipment` plan. A gear goal
that cannot be planned therefore means **zero skill grind, permanently** — the
observed symptom.

---

## Goal

1. Make deep recipe chains reachable by giving the gather edge a quantity, so
   the search is shallow and the plan is found.
2. Stop re-deriving the same interior every cycle by caching validated
   sub-plans as composite edges in the learning store.
3. Delete the two-pass budget and make an unplannable top-ranked objective
   loud instead of invisible.

Three increments, each independently shippable with `formal/gate.sh` green.
**Order is I1 → I3 → I2** and is load-bearing: a single 15 s budget against
unbatched gathers is strictly worse than today's behaviour, so I3 must not
land before I1.

### Non-goals

- `FightAction` batching. Drop-farming has the identical explosion (live R2D2
  once ran 198 chicken fights for `feather`), but it is deferred to a follow-up
  so the gather path is proven first. Recorded as a residual below.
- Cross-character production ("Robby is `weaponcrafting 10` and holds the
  materials; nobody can ask him to craft for the others"). Real gap, separate
  epic.
- Making skill level a first-class strategy root. Also a real gap, separate
  epic. This design only restores the instrumental path.

---

## I1 — Quantified gather edge

### `GatherAction` (`ai/actions/gathering.py`)

Add `quantity: int = 1`. Mirror `CraftAction`'s partial-batch contract exactly,
because that contract is already proved and already understood in this codebase.

```python
def effective_quantity(self, state: WorldState, game_data: GameData) -> int:
    """`min(self.quantity, inventory headroom in units)` — the largest feasible
    batch to gather NOW. 0 when not even one unit fits."""
```

- `is_applicable` — unchanged skill gate; capacity check becomes
  `effective_quantity(...) >= 1`. A batch that does not fully fit degrades to
  the largest feasible batch rather than becoming inapplicable. Without this a
  near-full inventory silently removes the only edge to a real deficit.
- `apply` — mints `effective_quantity` units of the drop item (today: exactly
  one). `skill_xp` stays a server-snapshot field and is still not simulated.
- `cost` — `(6.0 + dist) * quantity`, plus the existing loadout penalty
  (per-action, one swap serves the whole batch).

`_BANKED_REGATHER_PENALTY` changes from a flat `+100.0` whenever `banked > 0`
to `min(banked, quantity) * 100.0`. The existing docstring already claims this
behaviour — "The penalty applies per banked unit's worth: once the bank is
exhausted the deficit gathers carry no penalty" — and the flat form could not
express it. A quantity makes the documented intent implementable.

### `size_closure_gather` (`ai/intermediate_batch.py`)

Sizing belongs to the goal, not the factory: the factory has no demand context,
and this is precisely how batched crafts already work.

```python
def size_closure_gather(action: GatherAction, chain: Mapping[str, int],
                        state: WorldState, game_data: GameData) -> GatherAction:
    """`action` with quantity set to the inventory-bounded batch for its drop
    item's net closure demand (chain demand minus inventory+bank holdings).
    Unchanged when the sized quantity already matches."""
```

Placed beside `size_intermediate_craft`, which it mirrors leg for leg. Both are
module-level functions, so the one-behavioral-class-per-file rule is unaffected.

### Call sites

`GatherMaterialsGoal.relevant_actions` (`ai/goals/gathering.py`) and
`UpgradeEquipmentGoal.relevant_actions` (`ai/goals/progression.py`) both already
compute `chain = demand_set(...)` and `covered = fully_covered_materials(...)`
for their existing pruning. Each gains one call, in the arm that already appends
a `GatherAction`.

Emission stays **one edge per material** at exactly the outstanding deficit.
The branching factor is therefore identical to today's; only the depth collapses.

### `min_plan_length` (`ai/min_plan_length.py`)

Currently `ceil_gathers(min_gathers(...)) + min_crafts(...) + equip`. Under
batching a real plan can be **shorter** than that, so the value stops being a
lower bound and `is_plannable` rejects goals the planner can now reach. The mint
term becomes one step per distinct material requiring gathers.

This falsifies `Formal.PlanModel.min_plan_length_le_plan` as written. See
Formal below — this is the highest-risk item in the change.

### Cursor hold (`ai/plan_cache.py`, `ai/player.py:1214`)

A batched gather is a planner abstraction: the API gathers one unit per call
with a cooldown, so N units are N cycles. This is the established
`LevelSkill` idiom (planner-optimistic apply, player-expanded at execution).

`PlanCache` gains `step_target: int | None`, snapshotted at plan time as
`state.inventory.get(drop, 0) + quantity`. The advance rule becomes a **state
predicate, not a counter**:

```
advance when  state.inventory.get(drop, 0) >= step_target
hold otherwise
```

Chosen over an execution counter because it is self-correcting: a lucky
multi-unit drop, another character draining the shared bank, or an inventory
that fills mid-batch all resolve without bookkeeping, and there is no mutable
state on the shared `Action` instance.

Bounded by `should_replan`'s existing `replan_interval` staleness trigger, which
also covers `drop_item_override` rare drops — the 1-unit-per-simulated-gather
abstraction already under-counts those, and batching does not worsen it.

---

## I3 — One budget, loud failure

### `ai/strategy_driver.py`

Delete `try_plan_cheap`, `try_plan_full`, `_budget_for`, `CHEAP_BUDGET_SECONDS`
(and its `ARTIFACTSMMO_CHEAP_BUDGET_SECONDS` override), and the second
`select_pure` call. One `try_plan` remains. `guard_reprs` / `memo_bypass` keep
their current meaning; guards still bypass the memo.

`_record_attempt` loses its `mark_on_timeout` keyword and always marks on an
empty plan. This is the specific defect that let the staff search re-explode 955
times.

### `ai/planner.py`

`_SEARCH_BUDGET_SECONDS = 300.0` → `15.0`. `_MAX_SEARCH_NODES` is unchanged; it
is a memory bound, orthogonal to the clock.

### `DoomedMemo`

Retained unchanged in mechanism (escalating TTL 20/40/80/160,
`plannability_signature` invalidation). It is now the *only* thing bounding the
cost of a genuinely unplannable goal: 15 s once per re-probe window rather than
15 s every cycle.

### Loud failure

When `ranked[0]` returns no plan, record an `objective_unplannable` event —
cycle-snapshot field plus trace record carrying goal repr, nodes, depth and
`timed_out` — *before* walking to the next candidate. The fall-through itself
stays; only the silence goes. The 31-hour blindness in the traces above is
entirely attributable to that silence.

---

## I2 — Macro composite edges

Phase 2b of the 2026-06-23 design, previously deferred behind "a dedicated
formal review". That review is in scope here.

### Storage

New `plan_macro` table (`ai/learning/models.py`, SQLModel, alongside
`PlanCommitment` / `PlanBodyLog`):

| column | meaning |
|---|---|
| `target_item` | item the sub-plan obtains |
| `quantity` | units the sub-plan yields |
| `gate_signature` | skill levels the legs require, canonicalized |
| `legs_json` | structured legs (see codec) |
| `cost` | summed leg cost at store time, diagnostic only |
| `hits`, `stored_ts` | provenance |

Keyed `(target_item, quantity, gate_signature)`. Deliberately **not** keyed on
inventory or position: those churn every cycle, which is exactly why a
concrete-plan cache would miss almost always. Cross-character by construction —
the coordination DB is already shared.

### `action_codec` (new module)

`PlanBodyLog.body_json` stores action **reprs**, which cannot be rehydrated into
`Action` objects. A structured codec is required and is genuine new work, not a
freebie:

```
encode(action) -> {"kind": "Withdraw", "code": "spruce_plank", "quantity": 6}
decode(payload, game_data) -> WithdrawItemAction(...)
```

Mirrors the existing `goal_serialization` used by `PlanCommitment`. Round-trip
is a unit-test obligation: `decode(encode(a)) == a` for every action kind the
codec claims to support, and an unknown kind must fail loudly rather than
silently drop a leg.

### `MacroAction`

A composite `Action` over an ordered leg list:

```
cost(state)          = Σ leg.cost(intermediate_state)
apply(state)         = fold(leg.apply, state)
is_applicable(state) = every leg applicable under that simulation
```

The composite is a **path, not a shortcut**: no cost is skipped and no
precondition is bypassed, which is what keeps `PlannerAdmissibility` valid.
`travel_region` is the first leg's; a macro whose legs cross regions is not
stored.

### Goal admission

Both consuming goals filter the action pool by `isinstance` whitelists, so a
`MacroAction` is dropped by default — the epic would ship inert, which this
repo has done before. `MacroAction` therefore carries
`tags = frozenset({"macro"})` and each whitelist gains a tag-based arm admitting
a macro **only when its `target_item` is the goal's own target or a member of
its closure `chain`**. Scoping by target, rather than admitting macros
unconditionally, preserves `UpgradeEquipmentGoal`'s slot lock and keeps the
branching factor bounded — the same discipline the P3a `skill_grind` admission
already uses for `LevelSkill`.

### Read / write path

```
read:   candidates = store.macros_for(target, qty, gate_signature)
        simulate legs from current state
        all applicable and goal satisfied at end -> admit as one edge
        otherwise                                -> invalidate row, search
write:  on every successful A* plan, encode and upsert
```

Validation is `len(plan)` applicability checks against a search of thousands of
nodes, so a stale hit is cheap. A macro can never return an unexecutable plan:
if it did not simulate clean, it was not used.

---

## Formal

Scope chosen: extend the proofs. This is planner core, the layer the repo
already treats as must-not-be-wrong.

**New**

- `formal/Formal/GatherCost.lean` — `gatherCost q = (base + dist) * q`;
  `0 ≤ q → 0 ≤ gatherCost q`, and monotonicity in `q`. Feeds the existing
  `ActionCostNonneg` obligation that A* optimality rests on.
- `formal/Formal/MacroEdge.lean` — `macroCost legs = Σ (map cost legs)`, hence
  a macro edge is a path in the original action graph and
  `PlannerAdmissibility` carries unchanged.

**Amended**

- `Formal.PlanModel.min_plan_length_le_plan` — must be re-established over the
  batched action model. Under batching a plan can be shorter than the current
  per-unit bound, so the theorem is **false as written** once I1 lands. It is
  not enough to keep the gate green by leaving it alone; the bound is consumed
  by `is_plannable`, so an unrepaired proof means a stale admission gate.

**Gate obligations**

`formal/diff` entries for every new pure core; mutation anchors refreshed in the
**same commit** as the edit, each resolving to exactly one site; no vacuous
theorems, every liveness hypothesis satisfiable.

---

## Testing

### Live regression (written first)

R2D2's exact traced state — bank `{spruce_plank: 16, blue_slimeball: 98}`,
`weaponcrafting 9`, `woodcutting 13`, empty inventory —
`UpgradeEquipment(greater_wooden_staff->weapon_slot)` must return a non-empty
plan in bounded nodes. Today: 3873 nodes, `timed_out`, `plan_len 0`.

### I1

- batch quantity equals the outstanding deficit after inventory+bank
- partial batch under a near-full inventory: applicable, sized down, never 0
  when one unit fits
- banked penalty scales with `min(banked, quantity)` and vanishes past bank stock
- cursor holds across N cycles and advances exactly when `step_target` is reached
- a lucky multi-unit drop advances early rather than hanging
- `min_plan_length` admits a chain that batching makes reachable

### I3

- top-ranked no-plan emits `objective_unplannable`, then falls through
- a timed-out goal is marked doomed on the first failure
- signature change re-probes immediately; otherwise TTL escalates 20/40/80/160

### I2

- codec round-trip for every supported action kind; unknown kind raises
- macro hit: admitted as one edge, node count collapses
- macro stale: invalidated, search runs, row replaced
- cross-session: stored in session A, replayed in session B
- macro cost equals the sum of its legs (the property `MacroEdge.lean` proves)

### Repo gate

`bash formal/gate.sh` — 0 errors, 0 warnings, 0 skipped, 100 % coverage.
Run serialized: never concurrent with anything importing `src`, including a
running bot.

### Runtime activation

Green tests have shipped inert changes in this repo before. Each increment is
done only when it **fires on a live `plan <char>`**: I1 when the emitted plan
contains a batched gather or withdraw for the staff, I3 when a forced
unplannable objective produces the trace event, I2 when a second consecutive
plan for the same target reports a macro hit.

---

## Residuals

Stated honestly rather than hidden.

- **`FightAction` is still singleton.** Any closure whose leaf is a monster drop
  keeps the per-unit chain. `blue_slimeball` is reachable here only because the
  bank already holds 98. Deferred by explicit decision; the symmetric fix is
  known.
- **A doomed goal still costs 15 s per re-probe window.** Bounded and now
  visible, but not free.
- **`drop_item_override` batches are optimistic.** One simulated gather credits
  one unit of a 1-in-200 secondary drop; batching multiplies an abstraction that
  was already wrong in this direction. `replan_interval` bounds the error.
- **Skill level remains instrumental only.** If every gear root is satisfied or
  unplannable, nothing grinds a skill. This design restores the path; it does
  not add the root.
- **No cross-character production.** Robby can craft the staff today and will
  not be asked to.

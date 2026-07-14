# One Planner — Craft-Chain Macro Action

**Status:** approved for planning (user directive: *"there must not be a second planner. duplication of functionality is a violation of project rules. DRY that up."*)
**Date:** 2026-07-14
**Related:** [[feedback_two_plan_producers]], `project_recycle_as_acquisition` (the epic whose census exposed this), `project_plan_generation_churn` (which introduced the generator).

---

## 1. The defect

There are **two plan producers**.

`ai/strategy_driver.StrategyArbiter._plans` (`:852`):

```python
gen = generate_next_craft_action(goal, state, game_data, actions)
if gen is not None:
    ...
    return gen          # <-- A* NEVER RUNS
return GOAPPlanner().plan(state, goal, actions, game_data, ...)
```

`ai/craft_plan_gen` (578 lines) is a recipe-directed generator that produces a plan at `nodes=0` and **preempts** the GOAP planner. Only the GOAP planner consults `Goal.relevant_actions`. So anything taught to "the planner" by widening the action pool is learned by **exactly one of the two**.

**This is not hypothetical — it already shipped.** The recycle-as-acquisition epic landed seven commits (tier descent, goal action pool, licence, Lean) with every test green, and was **inert for any roomy bag**: the generator answered first, knew nothing of recycle, and planned `Gather(ash_tree)` while the bag held bows whose recipe IS `ash_plank`. It was caught only by a behavioral census, and the live runtime verification passed **by accident** (the character's bag happened to be slot-full, which made the generator defer).

The generator's own module docstring is the indictment — a list of everything it had to be *re-taught* that the GOAP planner already knew: monster-drop leaves, NPC-buy leaves, skill gates, `LevelSkill` legs, banked-intermediate withdraws, the loadout re-arm, and finally recycle.

### A second defect, hiding behind the first

The generator does not merely duplicate the planner — it **outranks** it. `if gen is not None: return gen` means a generated plan is never *compared* against what search would find. If a cheaper non-craft route exists (buy it, recycle it, fight for the drop), the bot cannot see it. Making the chain compete on cost is a **correctness** improvement, not only a DRY one.

## 2. Why we cannot simply delete the generator

Measured on live game data (from-scratch chains, empty bag and bank):

| configuration | `copper_bar x6` | `copper_ring x2` |
|---|---|---|
| `h = 0` (today: Dijkstra) | 47,114 nodes, plan_len 61 | **933,963 nodes — CAPPED, no plan** |
| admissible heuristic | 960 nodes | **956,851 — CAPPED** |
| batched gather | 79,450 nodes, plan_len 9 | **545,104 — CAPPED** |
| heuristic **+** batch | 1,958 nodes | **538,753 — CAPPED** |

**No combination rescues the deep chain.** The generator is not a workaround for a bad search — it is a genuinely better *algorithm* for this shape of problem: it reads the answer off the recipe closure in O(closure) instead of searching for it.

Two facts worth recording, because both are traps:

- **The planner is Dijkstra, deliberately.** `planner.py:138` sets `h0 = 0.0`. A previous heuristic was inadmissible and returned strictly suboptimal plans, so it was zeroed (`formal/Formal/PlannerAdmissibility.lean`). The optimality theorem — `firstSatisfied_least_cost_of_admissible` — is already stated for **ANY admissible h**; `h ≡ 0` is just the trivial instantiation.
- **A "cheapest gather cost" heuristic is NOT admissible.** `GatherAction.cost` folds travel in, so the cheapest cost *from the current position* over-estimates a gather's *marginal* cost once the character is standing on the tile. Using it returned a plan costing 761 against an optimum of 401. (`max_gather_yield == 1`, so that was not the cause.) Any future heuristic work must bound the **movement-free floor**, not the from-here cost.

## 3. Design — the chain becomes an ACTION, not a plan

**One plan producer: the GOAP planner.** The recipe-closure chain becomes a single composite `Action` that the planner may *choose*.

```
TODAY (two producers)                  AFTER (one producer)
---------------------                  --------------------
gen = generate_next_craft_action(...)  macro = craft_chain_macro(goal, state, gd, relevant)
if gen: return gen   # bypasses A*     pool = relevant + ([macro] if macro else [])
return A*(...)                         return GOAPPlanner().plan(state, goal, pool, gd)
                                                              # picks the macro in 1 node
```

### 3.1 `CraftChainMacro` (`ai/actions/craft_chain.py`)

An `Action` whose payload is an ordered tuple of ordinary actions:

```python
@dataclass
class CraftChainMacro(Action):
    legs: tuple[Action, ...]
    tags: ClassVar[frozenset[str]] = frozenset({"craft", "macro"})

    def is_applicable(self, state, game_data) -> bool:
        """Every leg applies in sequence from `state`."""
    def apply(self, state, game_data) -> WorldState:
        """Fold every leg's apply — EXACTLY the composition of the legs."""
    def cost(self, state, game_data, history=None) -> float:
        """Sum of each leg's cost AT THE STATE THAT LEG SEES."""
    def expand(self) -> list[Action]:
        return list(self.legs)
```

**`apply` must equal the composition of the legs' `apply`, and `cost` the sum of their costs.** This is the load-bearing invariant: if the macro's model diverges from its legs, the planner optimises against a fiction. It gets a differential test against leg-by-leg simulation.

`execute()` is never called — see §3.3.

### 3.2 Macro expansion in the planner (`ai/planner.py`)

`Action` gains a default `expand(self) -> list[Action]: return [self]`. `GOAPPlanner.plan` flattens the returned plan exactly once:

```python
return [leg for action in node.plan for leg in action.expand()]
```

So **every consumer downstream of the planner — the player, the plan cache, `should_replan`, the trace, the TUI — sees ordinary actions and is unchanged.** The macro exists only inside the search.

### 3.3 The builder (`ai/craft_chain_macro.py`)

Keeps `craft_plan_gen`'s O(closure) chain construction (`craft_plan_full`, `shopping_list`, `closure_demand`, the recycle prefix, the batch sizing) but **returns a `CraftChainMacro` instead of a plan**, and returns `None` when it cannot build one.

**It builds its legs FROM the goal's `relevant_actions` pool** — as `craft_plan_gen` already does (`_best_recycle(relevant, ...)`, `_dropper_fight(...)`, `_map_next_action`). That is what makes the DRY property structural: **a route the pool gains is a route the macro can use, with no code change.** A future "the planner now knows X" cannot be learned by only one producer, because there is only one.

### 3.4 What gets DELETED

- The bypass at `strategy_driver.py:852-860` (`if gen is not None: return gen`).
- `craft_plan_gen.generate_next_craft_action` as a *plan producer*, and with it **its six "fall back to A*" rules** — the entire class of divergence. When the builder cannot construct a chain it simply returns `None`, adds no macro, and the planner searches as it always would. There is no second decision to keep in sync.
- `_finish` / `_with_rearm`'s macro-level re-arm special-casing, IF the re-arm is expressible as an ordinary leg inside the chain (it should be: `OptimizeLoadoutAction` is already in the pool). This directly retires the Important-2 bug from the recycle epic's final review (a recycle prefix made `mapped[0]` a Recycle, so the re-arm check silently skipped and plans opened bare-handed).

## 4. Why this is safe

- **The optimality proof is untouched.** `h ≡ 0` stays. The macro is just another edge with a non-negative cost, so Dijkstra optimality (`PlannerAdmissibility.lean`) holds unchanged. The macro must have **non-negative cost** — pinned by test.
- **Strictly more choice, never less.** Today the generator's plan is returned unconditionally. As a macro it is one option among the pool's, chosen only when it is cheapest. Any plan reachable today remains reachable; some strictly cheaper plans become reachable for the first time.
- **Node count is preserved.** The macro is ONE node. The planner picks it immediately when it dominates, so the O(closure) fast path survives — it is now expressed as a cheap edge rather than a bypass. **This must be measured, not assumed** (§6).

## 5. The risk to watch

Adding a macro to the pool **widens the branching factor at every node**, and the search that the generator existed to avoid is the one we are now inviting the macro into. The macro must be built **once per plan call**, not per node.

If the planner does not pick the macro immediately, we get the worst of both worlds: the explosion AND the macro. The acceptance bar (§6) is therefore a **node-count budget**, not merely a correctness check.

## 6. Acceptance

1. **Node budget (the load-bearing one).** For every case `craft_plan_gen` serves today at `nodes=0`, the unified planner must resolve in a **small bounded** node count (target: ≤ 100 created nodes, vs 47k–1M for bare Dijkstra). Measure `copper_bar x6` and `copper_ring x2` from an empty bag/bank — the two cases in §2's table.
2. **Plan equivalence.** For a corpus of goals, the unified planner's plan must be **cost ≤** the plan `craft_plan_gen` produces today (never worse; sometimes better, per §1).
3. **Macro fidelity differential.** `macro.apply(s)` == folding the legs' `apply`, and `macro.cost(s)` == the sum of leg costs. Randomised, ≥200 trials.
4. **All three censuses stay clean:** `planner_bug 0`, `inventory_bug 0`, `recycle_source_bug 0`. The recycle-source census is the one that caught the two-producer bug in the first place; it must stay green **without** `craft_plan_gen`'s `_recycle_prefix` existing as a separate code path.
5. **Scenarios lane 141/141**, full formal gate green.
6. **Runtime, on a state that REACHES the path** (per [[feedback_two_plan_producers]] — a live check that does not exercise the changed path proves nothing): confirm on both a **slot-full** bag and a **roomy** bag that the weaponcrafting grind still plans `Recycle(...)`, and that the `copper_ring` chain now plans at all.

## 7. Out of scope

- Restoring a real admissible heuristic. §2 shows it is neither necessary (the macro gives O(closure)) nor sufficient (the deep case still caps). It remains an open opportunity, recorded, not pursued.
- Batched `GatherAction`. Same reasoning — it shortens plans but does not fix the search, and it changes execution semantics. Recorded for later.
- The other pre-existing planner call sites (`craft_relief`, `CraftPotions`) unless they turn out to share the bypass.

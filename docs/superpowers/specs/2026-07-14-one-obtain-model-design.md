# One Obtain-Model — retire the second plan producer by unifying *how a thing can be obtained*

**Status:** approved for planning. **SUPERSEDES** `2026-07-14-one-planner-craft-chain-macro-design.md` (70b4cee0), whose central design was **disproved by measurement** — see §2.
**Date:** 2026-07-14
**User directive:** *"there must not be a second planner. duplication of functionality is a violation of project rules. DRY that up."*

---

## 1. What is actually duplicated

It is **not** two searches. It is **two models of how a material can be obtained.**

```python
# ai/next_craft_core.py — the model the chain builder walks
class NextAction(NamedTuple):
    kind: Literal["gather", "craft", "withdraw"]      # <- THREE sources
```

`craft_plan_full` (`ai/craft_plan_driver_core.py`, kernel-proved as `craftPlan` in `formal/Formal/CraftPlanDriver.lean`) descends the **recipe tree** and can express exactly three sources. The GOAP action pool knows **six**: gather, craft, withdraw, **recycle**, **NPC-buy**, **fight-for-drop**.

Every source beyond those three is a **bolt-on special case inside `ai/craft_plan_gen`** (578 lines):

| Source | How the generator handles it |
|---|---|
| gather / craft / withdraw | inside `craft_plan_full` — the real model |
| **recycle** | `_recycle_prefix` — minted BEFORE the descent, credited into `owned` |
| **fight-for-drop** | `drop_fights` map + truncate-at-Fight |
| **skill gate** | `LevelSkill` early-`return [lvl]` |
| **NPC-buy** | *not handled* — `return None`, defer to A\* |

So the generator is not a second *planner* so much as a second, poorer **obtain-model** with four hand-bolted extensions. Each new route must be taught to it separately — and that is precisely how the recycle-as-acquisition epic shipped **seven green commits that were inert for any roomy bag**.

### The mis-diagnosis worth recording

I previously wrote that the generator "does not read the action pool." **That was wrong** — it calls `goal.relevant_actions(...)` and always has. The pool is used to *map* abstract steps onto concrete actions. The blindness is upstream of that: **`craft_plan_full` walks recipes, so no route that is not a recipe edge can ever appear in the chain**, whatever the pool contains.

## 2. The disproved design (do not retry it)

The superseded spec proposed wrapping the chain as a `CraftChainMacro` action for the one GOAP planner to choose. **Measured, it does not work:**

| case | search without macro | search WITH macro in pool |
|---|---|---|
| `copper_bar x6` | 47,114 nodes | **52,354 nodes — WORSE** |
| `copper_ring x2` | 933,963 (capped) | **871,677 (capped), macro never picked** |

Two reasons, both fatal:

1. **The planner is Dijkstra** (`planner.py:138`, `h0 = 0.0`). It pops in cost order, so a goal-satisfying macro is the *most expensive* edge and is expanded only after every cheaper node — exactly the nodes we were trying to avoid. The macro widens branching and saves nothing.
2. **The generator does not produce a complete plan.** For `copper_bar x6` it returns **2 legs** (`[Gather(copper_rocks), Craft(copper_bar x6)]`, cost 47), not the 61-leg / cost-401 chain. It emits the *next few moves* and relies on the replan loop, executing one leg per cycle. GOAP produces a **complete goal-satisfying plan**. **They have different contracts** and cannot be merged by making one an edge of the other.

Both mechanisms must therefore survive. What must NOT survive is the second obtain-model.

## 3. Design — one shared source model

### 3.1 The model (`ai/obtain_sources.py`, NEW)

One pure function answers *"how may I obtain this item, right now?"* for **every** consumer:

```python
class SourceKind(Enum):
    GATHER   = "gather"     # a resource drops it
    CRAFT    = "craft"      # it has a recipe whose skill gate is met
    WITHDRAW = "withdraw"   # a copy is in the bank
    RECYCLE  = "recycle"    # a LICENSED surplus item's recipe yields it
    BUY      = "buy"        # a permanent NPC vendor sells it
    DROP     = "drop"       # a WINNABLE monster drops it

@dataclass(frozen=True)
class Source:
    kind: SourceKind
    code: str          # the resource / recipe / bank item / recycle SOURCE / npc / monster
    yield_per: int     # units of the TARGET obtained per application

def obtain_sources(item: str, state, game_data, ctx) -> list[Source]:
    """Every way `item` can be obtained from the current state. THE model."""
```

This is the single place a route is declared. **Adding a seventh source is one edit, and every consumer gains it.**

### 3.2 Consumers — all four collapse onto it

| consumer | today | after |
|---|---|---|
| `craft_plan_driver_core.craft_plan_full` | walks `recipes` | walks `obtain_sources` |
| `next_craft_core.NextAction.kind` | 3 literals | `SourceKind` |
| `tiers/prerequisite_graph.prerequisites` + `_producible` | craft-recipe descent + a `recoverable` map bolted on | `obtain_sources` |
| `goals/gathering.relevant_actions` | hand-built admission per route | admits the actions the sources name |

`recoverable_materials` (from the recycle epic) becomes the RECYCLE arm of `obtain_sources` rather than a separate map threaded through five signatures. That thread — `recoverable=NO_RECOVERABLE` on `prerequisites` / `actionable_step` / `unmet_closure_size` / `root_cost` / `is_reachable` / `decide_tree` / `next_grind_goal` — **is itself a symptom of the missing model** and gets deleted.

### 3.3 What gets DELETED from `craft_plan_gen`

- `_recycle_prefix`, `_best_recycle`, `_staging_withdraw`, `_recovered_units`, `_goal_closure` — recycle is now a `SourceKind`.
- `drop_fights` / `_dropper_fight` — DROP is a `SourceKind`.
- the `LevelSkill` early-return — a skill-gated craft is simply not a source until the gate is met; the `LevelSkill` leg is emitted by the same mapping.
- **most of the six "fall back to A\*" rules.** They exist because the model could not express a route. When the model can, the generator declines only for genuinely non-deterministic shapes (stochastic drop yields), which stays a truncation, not a decline.
- NPC-buy stops being a decline — BUY is a `SourceKind`.

What REMAINS in the generator: the O(closure) descent and the NextAction→concrete-action mapping. It becomes a thin, honest incremental producer over the shared model.

## 4. Why both mechanisms may coexist without duplication

After this change there is **one model** of what is obtainable and **two execution strategies over it**:

- **complete-plan search** (GOAP) — general, optimal, explodes on deep chains;
- **incremental O(closure) descent** — deterministic, fast, one leg per cycle.

They can no longer disagree about *what is possible*, which is the only thing that ever bit us. A route added to `obtain_sources` is seen by both, structurally — the "which of the two knows this?" bug class becomes unrepresentable.

## 5. Lean

`formal/Formal/CraftPlanDriver.lean` proves `craftPlan_steps_valid` (every step is a genuine next move) and `craftPlan_reaches` (a complete plan reaches the target) over the 3-kind model. Extending `NextAction.kind` to `SourceKind` changes the mirrored core, so both theorems must be **re-proved over the widened source set** — not weakened. The `withdraw` arm (`nextHelper`) is the existing template for a non-recipe source, so the shape is known.

`PlannerAdmissibility.lean` is untouched (`h ≡ 0` stays; no search change).

## 6. Acceptance

1. **PARITY CENSUS (the load-bearing gate).** A new census drives every goal through **BOTH** producers and fails on any disagreement about *obtainability*: if the GOAP pool can serve a material, the closure descent must be able to name a source for it, and vice versa. **This is the gate that makes the seven-inert-commits bug impossible to ship again.** A disagreement is a BUG cell, never an explained gap (per the keep epic: a gap class that can swallow a planner bug destroys the census's value).
2. All three existing censuses stay clean: `planner_bug 0`, `inventory_bug 0`, `recycle_source_bug 0` — the recycle census must stay green **with `_recycle_prefix` deleted**, proving recycle now flows from the shared model.
3. No search regression: `copper_bar x6` and `copper_ring x2` still served at `nodes=0` by the descent; scenarios lane 141/141.
4. Full formal gate green, `CraftPlanDriver.lean` theorems re-proved over the widened model (no `sorry`, no vacuity).
5. **Runtime on a state that REACHES the changed path** — BOTH a slot-full and a roomy bag (a roomy-bag check is exactly what the last epic's runtime proof accidentally skipped, per [[feedback_two_plan_producers]]).
6. The `recoverable` parameter thread is GONE from the five tier signatures and `decide_tree` / `next_grind_goal`.

## 7. Out of scope

- Restoring an admissible heuristic; batched `GatherAction`. Measured: neither is necessary (the descent gives O(closure)) nor sufficient (the deep case still caps 4/4 ways). Recorded, not pursued. **Note for anyone who tries: a "cheapest gather cost" heuristic is NOT admissible** — `GatherAction.cost` folds travel in, so the from-here cost over-estimates a gather's marginal cost on the tile (it returned a plan costing 761 against an optimum of 401).
- Merging the two execution strategies into one. §2 shows their contracts differ (complete plan vs next-moves-plus-replan). Unifying the *model* is what the DRY rule actually demands.

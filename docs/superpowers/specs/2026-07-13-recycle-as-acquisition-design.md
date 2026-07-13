# Recycle-as-Acquisition — Design

**Status:** approved for planning
**Date:** 2026-07-13
**Related:** `project_inventory_keep_unification` (the keep authority this builds on),
`project_level_skill_action` (the grind this unblocks), `project_recycle_surplus`
(recycle as *disposal*, which this complements).

---

## 1. The defect

`RecycleAction.apply` (`ai/actions/recycle.py:54`) **mints materials into the
inventory**:

```python
recipe = game_data.crafting_recipe(self.code) or {}
for mat_code, mat_qty in recipe.items():
    recovered = max(1, (mat_qty * self.quantity) // 2)
    new_inventory[mat_code] = new_inventory.get(mat_code, 0) + recovered
```

That makes recycle an **acquisition route**. But it is modeled *only* as
disposal (`goals/recycle_surplus.py`, `ai/disposal_route.py`). No code path that
answers *"how do I obtain material X"* can see it. The planner therefore
re-gathers, from raw resources, materials it is already holding in crafted form.

### Live evidence (Robby, 2026-07-13)

`LevelSkill(weaponcrafting -> 10)` selects rung `fire_staff`
(`5 ash_plank + 2 red_slimeball`; `red_slimeball` already held 20+34).

```
prerequisites(ObtainItem(ash_plank)) = [ObtainItem(ash_wood, 10)]   # ONLY the craft route
actionable_step(fire_staff)          = ObtainItem(ash_wood, 10)     # -> go chop trees
```

So the bot gathers `ash_wood` at 1/cycle. 5 `ash_plank` = 50 `ash_wood` = ~56
cycles for ONE weaponcrafting craft — and gathering pays **woodcutting**, so
weaponcrafting XP stayed frozen at 112 across the whole session. That is the
user-visible symptom: *"LevelSkill isn't doing anything."*

Meanwhile the bag holds **7 `fishing_net`** (recipe `{ash_plank: 6}`) and **17
`copper_axe`** (recipe `{copper_bar: 6}`). Recycling **two** `fishing_net`
yields 6 `ash_plank` — the fire_staff, in ~3 cycles instead of 56.

Every piece needed is already in place and already connected:

| Component | State | Evidence |
|---|---|---|
| `destructive_license` | licenses `Recycle(fishing_net)` ×6, `Recycle(copper_axe)` ×16 | probed at HEAD |
| `RecycleAction.is_applicable` | `True` | probed at HEAD |
| `RecycleAction.cost` | **7.00** vs `GatherAction` **25.00** | probed at HEAD |
| `RecycleAction.apply(fishing_net)` | `ash_plank: 0 -> 3` | probed at HEAD |

Nothing is broken. Nothing can *see* it.

### Second-order harm

The bag is **17/20 SLOTS**. The grind ADDS ~1 item/cycle while the 24-item
hoard that would feed it sits untouched. **The hoard is the fuel.** Draining it
into materials relieves slot pressure and powers the grind with the same action.

### Why the planner cannot reach it — three layers

1. **`tiers/prerequisite_graph.prerequisites`** (`:40`) descends into the recipe
   unconditionally, so the descent commits to `ash_wood` before GOAP is ever
   consulted.
2. **`goals/gathering.GatherMaterialsGoal.relevant_actions`** (`:165`) never
   admits `RecycleAction`. The planner re-filters at `ai/planner.py:124`
   (`relevant = goal.relevant_actions(...)`), so even injecting a licensed
   recycle into the pool is discarded — confirmed by probe.
3. Consequently `destructive_license`'s correct, already-licensed recycles are
   only ever reachable by *disposal* goals, which are discretionary and lose to
   the committed objective forever.

---

## 2. Design

One new pure core, two edges, one authority — **no new protection concept**.

### 2.1 New core — `ai/recoverable_materials.py`

```python
def recoverable_materials(state: WorldState, game_data: GameData,
                          ctx: SelectionContext) -> dict[str, int]:
    """Material code -> units recoverable by recycling LICENSED surplus."""
```

For every item code `c` in bag ∪ bank with `n = destroyable(c, state, game_data, ctx) > 0`,
and every `(mat, qty)` in `game_data.crafting_recipe(c)`:

```
recoverable[mat] += max(1, (qty * n) // 2)
```

The yield expression **mirrors `RecycleAction.apply` exactly**. If the two ever
diverge, the descent promises materials the executor cannot deliver.

**The authority is `destroyable`, unchanged.** "May I recycle this for parts?"
is the same question as "may I destroy this?", and the keep-unification epic
already answered it — including the `WORKING_KIT` / `COMBAT_WEAPON` reasons that
protect the last `copper_axe`. **No 11th `KeepReason` is added.** `destroyable`
already counts bag+bank (`inventory_keep.py:450`), which is what makes §2.4 work.

Distinct from the existing `recycle_surplus.recyclable_surplus`, which is
BAG-only and maps *item -> licensed copies* (a disposal question). This core maps
*material -> recoverable units* (an acquisition question) over bag+bank.

### 2.2 Edge 1 — the tier descent

```python
def prerequisites(node, state, game_data,
                  recoverable: Mapping[str, int] = MappingProxyType({})) -> list[MetaGoal]:
```

For an `ObtainItem` with a recipe: **if `recoverable.get(node.code, 0) > 0`,
return `[]`** — the material is a leaf, directly actionable, no recipe descent.

The `{}` default reproduces today's behavior byte-for-byte, so the change lands
**inert** and activates only where the caller wires it in. This is the exact
pattern `decide_tree` already documents for `band_adequate` ("the player wires
the real progression-band verdict in; it defaults to False").

**Leaf rule: `recoverable > 0`, not "fully recoverable"** (user decision). GOAP
mixes recycle + gather + craft to make up any shortfall, finding the true
optimum instead of an all-or-nothing cliff. §4 covers the risk this takes on.

### 2.3 Edge 2 — the goal's action pool

`GatherMaterialsGoal.relevant_actions` admits `RecycleAction(c)` when
`recipe(c)` intersects the goal's needed closure (`chain`, already computed
there for `withdrawable`).

Safety is structural: the pool reaching a goal has **already** been filtered by
`license_destructive_actions` at `StrategyArbiter.select`
(`strategy_driver.py:946`). Admission cannot leak an unlicensed recycle — it can
only *fail to admit* a licensed one, which is the present bug.

### 2.4 Bank sources — `Withdraw -> Recycle`

`RecycleAction.is_applicable` requires the item **in the bag**. `recoverable`
counts bag+bank anyway, because `GatherMaterialsGoal` already admits
`WithdrawItemAction`, so GOAP chains `Withdraw(fishing_net) -> Recycle -> Craft`.

This is **required, not optional**: the keep-unification epic just made
`DEPOSIT_FULL` bank surplus. A bag-only rule would let deposit strand the fuel in
the bank, `recoverable` would go empty, and the descent would silently revert to
chopping 50 `ash_wood` — the same bug, re-caused by its own sibling feature.

### 2.5 Plumbing

`recoverable` is computed **once per cycle in `player`** — the seam where
`SelectionContext` exists — and threaded down as a plain `dict[str, int]`:

```
player._selection_context(...)  ->  recoverable_materials(state, game_data, ctx)
   |
   +-> StrategyEngine.decide -> progression_tree.decide_tree
   |        -> strategy.actionable_step / unmet_closure_size / is_reachable
   |             -> prerequisite_graph.prerequisites
   +-> level_skill_expand.next_grind_goal
```

Thread points (all currently `(state, game_data)`-only):

| Site | File |
|---|---|
| `prerequisites` | `tiers/prerequisite_graph.py:40` |
| `actionable_step`, `unmet_closure_size`, `root_cost`, `is_reachable` | `tiers/strategy.py:63,89,105,191` |
| `decide_tree` + 3 `actionable_step` calls | `tiers/progression_tree.py:184,129,150,228` |
| `next_grind_goal` | `level_skill_expand.py:48` |
| `_gather_fallback_goal` | `strategy_driver.py:431` (already has `ctx`) |
| `plan_tree` (TUI) | `plan_tree.py:45` — passes `{}`; display-only |

A plain finite map, **not `SelectionContext`** — the pure core stays pure, and
the Lean mirror stays a finite map instead of dragging a Python context object
into the model.

`is_reachable` must be threaded too: if the descent treats a material as a leaf
but reachability still descends its recipe, the two disagree about the same node.

---

## 3. Lean

**`StrategyTraversal.lean` is UNCHANGED.** Its `Graph` is abstract:

```lean
structure Graph where
  prereqs : Nat → List Nat
  isSat : Nat → Bool
  producible : Nat → Bool
  kind : Nat → Kind
```

`actStep` (`:543`) and every reachability/soundness theorem are already
parametric over `prereqs`. Changing what `prerequisites` *returns* changes the
`Graph` instance, not the traversal — so the proofs carry unchanged. This is the
single biggest scope reducer in the epic.

Only `PrerequisiteGraph.lean` changes — `prereqEdges` (`:57`) gains the
recoverable flag:

```lean
def prereqEdges (recoverable : Bool) (recipe : Option (List (Nat × Nat))) : List Edge :=
  if recoverable then [] else
    match recipe with
    | some ingredients => ingredients.map (fun (m, q) => Edge.mk m q)
    | none => []

theorem prereqs_recoverable_leaf (r : Option (List (Nat × Nat))) :
    prereqEdges true r = ([] : List Edge)
```

Existing `prereqs_recipe`, `prereqs_leaf`, `prereqs_membership` are re-stated
under `recoverable = false` (behavior-preserving). The recoverable-yield
arithmetic (`max(1, (qty * n) // 2)`, saturating, floored) is mirrored and
pinned by theorem, since it is the term that must not drift from
`RecycleAction.apply`.

Lockstep per repo convention: `formal/diff/test_prerequisite_graph_diff.py`
extended; mutation anchors refreshed on every edited line; `formal/gate.sh` all
parts green (kernel, orphan modules, no-sorry, axiom lint, role manifest,
proof-concept index, extraction drift, differential, mutation).

---

## 4. The risk the leaf rule takes on

`recoverable > 0` → leaf means GOAP can inherit a **partially-deep** subtree:
recover 3 of 5 `ash_plank`, and the remaining 2 are a from-scratch gather chain.

`strategy_driver.py:400` documents exactly this failure mode in its own words:

> the GOAP search over the gather/craft/deposit interleavings EXPLODES
> super-linearly (measured offline: 655k nodes / 90s timeout / plan_len 0 at qty
> 480; live: 1M+ nodes)

and it is the same shape as the LevelSkill livelock fixed in `3166d390`
(`GatherMaterials(fire_staff)` hit the 1M-node cap, produced no plan,
`_execute_level_skill` raised, and the bot replanned identically forever).

**Two things hold it, and neither is an assertion:**

1. **The bound already exists.** `gather_step_target` flat-batch routing
   (`strategy_driver._gather_fallback_goal`) exists for precisely this: it routes
   a budget-infeasible deep goal to its deepest FLAT step (`min_gathers == qty`,
   no recipe sub-tree to interleave — measured ~38 nodes/unit, linear). A leafed
   material whose direct goal is budget-infeasible routes through it.
2. **The census proves it.** The PARTIAL cell (§5) fails the gate if a mixed
   recycle+gather plan does not resolve within budget. Per
   `project_inventory_keep_unification`: *a gap class that can swallow a planner
   bug destroys the census's entire value* — so the PARTIAL cell classifies a
   planner timeout as `INVENTORY_BUG`, never as an explained gap.

---

## 5. Acceptance — new cell family in the inventory census

Extends `audit/inventory_completeness.py` + `scripts/gen_inventory_completeness.py --check`
(CI: `.github/workflows/census-gate.yml`). Drives the **real** `StrategyArbiter`,
per the existing census contract. Target stays `inventory_bug == 0`.

| Cell | Setup | Planner MUST |
|---|---|---|
| **LIVENESS** | goal needs `m`; bag holds surplus `S`, `m ∈ recipe(S)`, `destroyable(S) > 0` | plan `Recycle(S)` |
| **SAFETY** | only *protected* copies of `S` (`destroyable(S) == 0`, e.g. the last `copper_axe` = `WORKING_KIT`) | **NOT** plan `Recycle(S)` — gather instead |
| **BANKED** | `S` held in bank only, bag empty | plan `Withdraw(S) -> Recycle(S)` |
| **PARTIAL** | `recoverable[m] < needed[m]`, at recipe depth ≥ 2 | resolve a mixed recycle+gather plan **within budget** (timeout ⇒ `INVENTORY_BUG`) |

The **SAFETY** cell is the one that stops this epic from becoming a
tool-melting bug: it proves the last `copper_axe` is never dismantled for parts.
The keep-unification epic's lesson applies directly — *the census's oracle is the
authority, so it proves the planner OBEYS the authority but never that the
authority is CORRECT.* Therefore `recoverable_materials` itself is pinned by
**unit tests written before any consumer depends on it**, with **two live
contributors at depth, disjoint** (a single contributor cannot distinguish
`max` from `sum`).

### Runtime verification (mandatory — `feedback_verify_runtime_activation`)

Green tests ≠ runtime-active. Done means: on live `plan Robby`,
`LevelSkill(weaponcrafting)` emits a plan whose first leg is
`Recycle(fishing_net)` (or `Withdraw -> Recycle`), **not** `Gather(ash_tree)` —
and weaponcrafting XP moves off 112.

---

## 6. Explicitly out of scope

- Changing `disposal_route` / `RecycleSurplus` (recycle-as-*disposal* is correct
  and stays as-is).
- Recycle-as-source for goals other than `GatherMaterialsGoal`. Other
  closure-restricted goals (`pursue_task`, `maintain_consumables`, `progression`,
  `currency_demand`) are left alone; `GatherMaterialsGoal` is the goal
  `strategy_driver` routes every `ObtainItem` material step to, so it is where
  the bug lives.
- Rung selection in `skill_grind_target`. Its tiebreak (fewest direct
  `mats_missing`, then highest craft level) picked `fire_staff`, but with the
  recycle edge `fire_staff` is genuinely cheap (2 recycles). The tiebreak is not
  the bug; the blindness is.

## 7. Known interaction, accepted

Recycling returns **half**, so recycle→recraft is lossy, not free. A crafted rung
item that becomes surplus is recyclable back into its own materials, producing a
churn loop that pays skill XP each craft. Per `project_banked_tool_ferry`, the
user has already ruled this an **intended XP accelerator**. It is bounded by the
50% yield loss and governed by `destroyable`, so it cannot consume protected
stock. No guard added.

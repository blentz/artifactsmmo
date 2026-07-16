# Recycle Value-Priority Policy — Design

**Status:** approved for planning
**Date:** 2026-07-16
**Related:** `project_recycle_as_acquisition` (recycle mints materials), `project_grind_held_rung_livelock` (BUG C), `project_skill_grind_heuristic` (BUG B — the search-explosion class the caveat refers to), `project_inventory_keep_unification` (keep_owned/destroyable), the GEAR-PURSUIT / `pursuit_value` work.

---

## 1. The defect

`RecycleAction.cost` is flat — `3·quantity + dist` (recycle.py) — regardless of WHAT is destroyed. Recycle-as-acquisition (`ai/obtain_sources._recycle_sources` + `GatherMaterialsGoal` recycle admission) therefore presents recycling a **valuable current-tier weapon** as just as cheap as recycling junk, and the Dijkstra planner (h≡0) **prefers it over gathering** (recycle ~7 vs a gather batch ~250+). Live: the weaponcrafting grind recycled surplus `fire_staff` to source `ash_plank` to re-craft `fire_staff` — destroy the weapon, remake the same weapon (a null cycle), burning `red_slimeball` for XP.

The user's intended policy has three tiers:
1. **Recycle X to craft X (null cycle): never.**
2. **Recycle current-tier equippable gear: lowest priority, and only when multiple copies are held** (surplus beyond keep/equipped).
3. **Recycle surplus/junk (obsolete gear): fine — value recovery.** Recycle is NOT blanket-dropped.

## 2. What already exists (REUSE — do not duplicate)

- **"Only multiple copies" (tier 2's gate):** `destroyable(code) = owned − keep_owned(code)` (`inventory_keep.py`). `keep_owned` is the max over `OWNED_REASONS`, which already includes `COMBAT_WEAPON` (keep 1) and `GEAR_DEMAND` (keep-1-per-slot with dominance) — so current-tier/best gear is protected and only *surplus* copies are ever recycle-eligible. No new "multiple copies" gate is needed.
- **Tier/value classification:** `pursuit_value(item_stats)` (combat-dominant scalar) already ranks gear — current-tier gear scores high (fire_staff 21000, feather_coat 25000), obsolete gear low, resources 0.
- **Surplus/junk recovery (tier 3):** recycle-as-acquisition already does this; it must stay.
- **The pool gate:** `license_destructive_actions` already restricts which recycles exist.

The ONLY missing behaviors are (a) the null-cycle rule and (b) the *priority* — `RecycleAction.cost` ignores value.

## 3. Design

### 3.1 Part 1 — null-cycle guard (already implemented, user-confirmed)

`GatherMaterialsGoal(exclude_recycle: frozenset[str])`; a skill grind sets it to the `{rung}` it crafts (`next_grind_goal`), and `relevant_actions` drops any `RecycleAction` whose code is in `exclude_recycle`. So recycling item T to source T's own crafting material (T → M → craft T) is forbidden. This is tier 1. It stays as the foundation.

### 3.2 Part 2 — value-scaled recycle cost (the new work)

Make `RecycleAction.cost` scale with the destroyed item's `pursuit_value`:

```
cost = 3·quantity + dist + RECYCLE_VALUE_WEIGHT · pursuit_value(code)
```

- **Obsolete/low-value gear** (small pv): penalty ~0 → still cheaply recovered (tier 3).
- **Current-tier gear** (high pv): large penalty → recycling it costs MORE than gathering the equivalent material, so the planner prefers **gathering** (or recycling lower-value junk) — tier 2 "lowest priority." It remains *possible* (finite cost) as a last resort when no cheaper route exists, and only on surplus copies (via the unchanged `destroyable` gate).

**Calibration.** Recycling one gear item yields `yield_per` materials, saving roughly `yield_per · 10 · gather_unit_cost` in gathers (≈ 1250 for a 5-plank yield at ~25/gather). To make a *current-tier* recycle (pv ≥ ~20000) cost more than that batch gather while leaving *obsolete* gear (pv ~5000) cheaper than a large gather, `RECYCLE_VALUE_WEIGHT ≈ 0.05–0.1`. Ship it as a single named module-level constant with the calibration rationale in its docstring; it is tunable, not load-bearing for correctness (any positive weight restores the gather-preferred ordering; the exact value only sets where the obsolete/current-tier crossover sits).

`pursuit_value` requires `item_stats(code)`; `RecycleAction` has `code` and `game_data` at `cost()` time. No new data or classifier — reuse `pursuit_value`.

## 4. Non-goals / boundaries

- **`keep_owned`/`destroyable` unchanged** — the surplus/"multiple copies" gate already exists.
- **`obtain_sources` STRUCTURE unchanged** — this changes the COST of a recycle, not whether a recycle source exists. So the recycle-source census (`recycle_source_bug`) and obtain-parity census (`obtain_parity_bug`) — which assert source *existence/parity*, not cost — are unaffected; verify they stay 0.
- **Tool-ferry churn** (`project_banked_tool_ferry`, recycle a banked pickaxe for XP) is a tool, low pursuit_value → small penalty → **unaffected**. The user's "don't blanket-drop recycle" is honored.
- **`equip_value` vs `pursuit_value`:** use `pursuit_value` (combat-dominant, the ruler the gear economy already uses), not the damage-blind `equip_value`.

## 5. Known caveat (flagged, NOT silently bundled)

The value penalty makes gathering **preferred** over current-tier gear-recycle — it fixes the *churn/inversion*. It does NOT by itself fix a **search-efficiency explosion** observed when the grind must gather deep (no cheap recycle/withdraw source): excluding the rung recycle left a large cheap **Withdraw** frontier (15 withdraws + 9 recycles + a 50-deep ash_wood gather → 105K nodes → timeout → empty plan → BUG C error:other risk). That frontier is the BUG B class (uninformed Dijkstra over a cheap frontier) and is orthogonal to recycle *value*. If it recurs after Part 2, it is a **separate follow-up** (a grind-material heuristic or a grind-descends-to-gatherable-raw guard), tracked on its own — not bundled into this policy. Part 2 is shippable when the churn/preference is fixed and the census/gate stay green; the plannability follow-up is filed if the runtime check surfaces it.

## 6. Acceptance

1. Unit: `RecycleAction.cost` increases with `pursuit_value(code)`; a current-tier gear recycle (pv high) costs strictly more than an obsolete-gear recycle (pv low) at the same qty/distance; the base `3·qty + dist` is preserved when pv is 0.
2. Unit: `GatherMaterialsGoal.exclude_recycle` drops `Recycle(rung)` (Part 1 — already have `test_exclude_recycle_drops_the_rung_from_recycle_acquisition`).
3. **Runtime on Robby (mandatory, `feedback_verify_runtime_activation`):** in a surplus-fire_staff grind state, the weaponcrafting grind does NOT recycle `fire_staff` (null cycle, Part 1) AND does not recycle other current-tier gear in preference to gathering (Part 2 — the planned leg is a gather, or a low-value-junk recycle, not a current-tier gear recycle). Record the plan + node count; if a deep-gather search explosion appears, file the §5 follow-up rather than claiming the churn unfixed.
4. Full suite green; all four censuses clean (`inventory_bug`/`planner_bug`/`recycle_source_bug`/`obtain_parity_bug` 0); formal gate green (no Lean change — cost is not Lean-mirrored; the traversal proofs abstract `prereqs`).
5. No regression to tool-ferry churn (a low-pv tool still recycles cheaply).

## 7. Out of scope

- The BUG B-class grind-material search explosion (§5 caveat — separate follow-up).
- Any change to `keep_owned`/`destroyable`/the keep-reason registry.
- Learned-cost interaction: `RecycleAction.cost` takes `history` but the value penalty is deterministic (from `pursuit_value`); it does not consult learning.

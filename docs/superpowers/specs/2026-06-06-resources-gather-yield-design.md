# Design: Resources — Yield-Rate-Optimal Gather Source Selection (Phase 2, gap #1)

Date: 2026-06-06
Status: Approved (brainstorming) — pending implementation plan
Program: behavioral-completeness (`docs/behavioral_completeness/`), top backlog
item (resources, leverage 27 — the live gathering bottleneck).

## Goal

Close the `resources` gap (MATRIX classified THIN): extend the gathering policy so
that, when a needed item is dropped by **more than one resource**, the bot gathers
the **yield-rate-optimal** source (fewest expected gathers to acquire one unit,
tie-broken by nearest node), and prove that decision correct in Lean over all
inputs against the program's four property classes. Today the bot picks gather
nodes by Manhattan distance only and ignores drop rate; only one `safety` theorem
(`GatherApply`) backs gathering.

## Success criterion

- Behavior: a needed item with multiple source resources is gathered from the
  non-dominated source (proven), with no change to single-source gathering (the
  live path).
- Proof: the selection decision satisfies dominance, monotonicity, totality/
  no-deadlock, and reachability/progress; safety reused from `GatherApply`.
- The `resources` MATRIX row's proof-coverage cell lists the four classes; the
  `test_matrix_complete` gate stays green; `BACKLOG.md` re-ranks resources closed.

## Non-goals (YAGNI)

- Skill-XP-efficiency selection (that is the LevelSkill metric — its own future
  spec). This spec is acquisition-efficiency only.
- True map-pathing node cost (keep the existing `_nearest` Manhattan distance,
  matching `GatherAction.cost`).
- Changing `GatherAction`, the planner, or single-source gathering.
- Probabilistic planner simulation (the planner still sims gather as +1; the rate
  enters only the *selection*, not the per-gather apply).
- Secondary-drop acquisition (gathering a resource for a non-primary drop). Since
  `GatherAction.apply` mints only the primary drop, candidates are restricted to
  resources whose PRIMARY drop is the needed item; needed items that exist only as
  secondary drops are a separate, later gap.

## Architecture

Four units, smallest responsibility each:

### 1. Data plumbing — `GameData` retains resource drop rates

`GameData._load_resources` currently keeps only each resource's *primary* drop
item (`_resource_drops: dict[str, str]`), discarding the rate. Add the full table,
mirroring the existing `_monster_drops` pattern:

```
_resource_drops_full: dict[str, list[tuple[str, int, int, int]]]
    # resource_code -> [(item_code, rate, min_quantity, max_quantity), ...]
```

populated from `ResourceSchema.drops` (`DropRateSchema`: `code`, `rate` [1-in-N],
`min_quantity`, `max_quantity`). Keep `_resource_drops` + `resource_drop_item`
for back-compat. Add accessor `resource_drop_table(code) -> list[tuple[str,int,int,int]]`
(empty list if unknown — API is the source of truth, no fabricated rates).

### 2. Pure selection core — `src/artifactsmmo_cli/ai/gather_selection.py`

A pure module (no I/O), the extracted core the differential test runs:

```python
@dataclass(frozen=True)
class GatherCandidate:
    resource_code: str
    rate: int          # 1-in-N drop rate (>= 1)
    min_quantity: int  # >= 1
    max_quantity: int  # >= min_quantity
    distance: int      # Manhattan distance to nearest node (>= 0)

def select_gather_source(item: str, candidates: list[GatherCandidate]) -> str | None
```

Metric — **expected gathers to acquire one unit** (exact rational, never float):

```
avg_quantity(c) = Fraction(c.min_quantity + c.max_quantity, 2)   # >= 1
expected_gathers(c) = Fraction(c.rate) / avg_quantity(c)         # > 0
```

Selection = deterministic **lex-argmin over `(expected_gathers, distance,
resource_code)`** — fewest expected gathers, then nearest node, then code (total
order ⇒ unique winner). `None` when `candidates` is empty. `item` is carried for
the caller's grouping and is not used by the metric (documented).

### 3. Wiring — `GatherMaterialsGoal.relevant_actions`

In the existing relevant-action filter, after the recipe-closure narrowing:
group the surviving `GatherAction`s by the needed item each **primarily**
produces — a resource is a candidate for `item` iff `resource_drop_item(resource)
== item` (its PRIMARY drop). This matches `GatherAction.apply`, which mints +1 of
the resource's primary drop (`gather_apply_core.gather_apply_pure`); selecting a
resource for a *secondary* drop would not progress the needed item in the planner
sim, so secondary-drop acquisition is explicitly out of scope (a separate gap).
The candidate's `rate/min/max` are the primary drop's row in
`resource_drop_table(resource)`. For any needed item with **>1 candidate
resource**, build `GatherCandidate`s (`distance = _nearest(action.locations,
state)` Manhattan), call `select_gather_source`, and keep ONLY the winning
resource's `GatherAction` (drop the dominated ones). Items with a single candidate
resource are untouched. No other call-site changes.

Blast radius: one method (`GatherMaterialsGoal.relevant_actions`). The planner
then plans the chosen source by its existing distance cost.

### 4. Proofs — `formal/Formal/GatherSelection.lean` (core-only, exact ℚ)

Mirror `gather_selection.py` as a computable Lean `def selectGatherSource` over
`Candidate` with `ℚ` arithmetic. Theorems (role names):

- **Dominance** `select_is_lex_argmin` — the returned candidate is the
  lex-minimum of `(expectedGathers, distance, code)`; corollary
  `select_no_cheaper_at_le_distance`: no candidate has strictly fewer expected
  gathers at ≤ distance. (headline)
- **Monotonicity** `expected_gathers_mono_in_rate` (non-decreasing in `rate` at
  fixed avg-quantity) + `winner_stable_under_rate_decrease` (lowering the winner's
  rate keeps it selected).
- **Totality / no-deadlock** `select_some_iff_nonempty` — `selectGatherSource`
  returns `some` iff the candidate list is non-empty.
- **Determinism** `select_deterministic` — equal inputs ⇒ equal output (underpins
  the lex tie-break / no dict-iteration nondeterminism).
- **Reachability / progress** `gather_selected_reaches_needed` — repeatedly
  gathering the selected source (each step +1 of the item, per `GatherApply`)
  raises owned count to `≥ needed` in finitely many steps.

Safety is reused from `GatherApply` (inventory never overflows); no new safety
theorem. Register the role theorems in `Manifest.lean` + exact-statement pins in
`Contracts.lean` + `#print axioms` lines in `Audit.lean`; header-tag the module
`-- @concept: resources @property: dominance, monotonicity, totality, reachability`.

## Data flow

1. `GameData.load` → `_resource_drops_full` populated from the API.
2. Per cycle, `GatherMaterialsGoal.relevant_actions` builds candidates for each
   multi-source needed item and narrows to the `select_gather_source` winner.
3. The planner plans gathers of the chosen source (unchanged cost/pathing).
4. `GatherAction.apply` mints +1 (unchanged); progress proven by
   `gather_selected_reaches_needed`.

## Error handling

- Unknown resource / empty drop table → no candidate → `select_gather_source`
  returns `None` and the filter leaves the item's gathers as-is (no narrowing) —
  fail-open to existing behavior, never a crash.
- `avg_quantity` is ≥ 1 by the schema invariant (`min_quantity ≥ 1`); the model
  carries `min_quantity ≥ 1` as a hypothesis so the division is well-defined.
- No `except Exception`; missing API data surfaces as an empty table, not a
  fabricated rate.

## Testing

- TDD throughout; `gather_selection.py` at 100% coverage (incl. the empty-list and
  single-candidate branches).
- Differential: an oracle on `selectGatherSource` (Lean) vs `select_gather_source`
  (Python) over Hypothesis-random candidate lists (varied rate/min/max/distance,
  including ties) asserts byte-equal selection. Mutation runner perturbs the Python
  core; any surviving mutant fails the gate.
- Unit: multi-source narrowing in `GatherMaterialsGoal.relevant_actions`
  (best-yield source kept, dominated dropped); single-source untouched;
  unknown-table fail-open.
- Integration smoke (offline fixture): a needed item with two sources at different
  rates narrows to the lower-expected-gathers source.

## Risks / open items

- **Multi-source frequency:** in early tiers most items have a single source, so
  the live behavior change is small; the value is correctness + proof when
  multi-source (notably secondary/rare drops) DOES occur. Accepted — this is a
  behavioral-completeness item, not a hot-path optimization.
- **Distance vs rate trade-off:** the metric prioritizes expected-gathers over
  distance (rate dominates, distance tie-breaks). If play data later shows travel
  cost should weigh more for near-equal rates, revisit the metric (it is a single
  pure function + proof to change).
- **`avg_quantity` rounding:** using `(min+max)/2` as exact ℚ avoids float drift;
  if the game's effective yield differs from the midpoint, the metric is still a
  consistent, proven ordering (not claimed to be the game's exact expectation).

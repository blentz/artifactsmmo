# Batch-Craft Output Quantity (Learned Yield) — Design

**Status:** approved (brainstorm 2026-06-26) · **Part of:** [[PLAN_season8_readiness]] P2
**Trigger:** API v8.0.0 makes some recipes yield multiple items per craft (potions ×2,
food ×2–3). `CraftSchema.quantity` (the output yield, "Quantity of items crafted") has been
in the spec since v7.0.4 but is **never read** — the planner assumes 1 item per craft run.

## Problem

The recipe model drops `craft.quantity`. Consequences when a recipe yields `Y > 1`:
- **Over-craft:** the generator emits `need` runs instead of `⌈need/Y⌉`.
- **Over-gather:** `_closure_demand` scales material demand by `need`, not `⌈need/Y⌉`.
- **Apply divergence:** `CraftAction.apply` credits `runs` items (should be `runs × Y`); task
  progress and the skill-XP proxy are off by the yield.
- **Assumed, not learned:** even the per-craft output and XP that the server *returns in every
  real craft response* (`SkillInfoSchema.items`, `SkillInfoSchema.xp`) are discarded by
  `CraftAction.execute`, so the bot can never ground-truth its assumptions.

Every live v7.0.4 recipe is `Y=1`, so this is a latent bug today and a real one under v8.0.0.

## Design

### Yield resolution (priority order)
`GameData.craft_yield(code) -> int`:
1. **Learned** — observed output quantity from real craft responses (LearningStore), if present.
2. **Prior** — `CraftSchema.quantity` from the item's recipe (API data).
3. **Default** — `1` (no recipe / `UNSET`).

The bot never *assumes* 1 for an item it has crafted live; the observed quantity wins. Crafting
yield is deterministic, so learned ≈ prior in practice — learning ground-truths the prior and
covers an UNSET/incorrect schema value.

### Components (one responsibility each)

1. **Yield prior — `GameData._build_items` + `craft_yield` accessor.** Store
   `craft.quantity` (default 1, UNSET-safe) into a parallel `_craft_yields: dict[str, int]` map
   alongside `_crafting_recipes` (the ingredient map stays `dict[str, dict[str,int]]`,
   untouched, so the proved cores' signatures stay clean). Expose `craft_yield(code) -> int`
   and a `craft_yields` Mapping property (resolved view, see #3).

2. **Learning hook — `LearningStore.record_craft_yield` + reader.** `CraftAction.execute`
   currently reads only `result.data.character`. Add: from `result.data.details`
   (`SkillInfoSchema`) read `details.items` (the produced `DropSchema` list) — the quantity
   credited to `self.code` — and `details.xp` (real crafting XP), and record both via
   `record_craft_yield(item_code: str, quantity: int, xp: int)`. New SQLite table keyed by
   `(character, item_code)`, last-write-wins, mirroring `record_skill_max_xp`. Reader:
   `observed_craft_yield(item_code) -> tuple[int, int] | None` returning `(quantity, xp)`.
   Failures are logged and swallowed exactly as the existing `record_*` methods do (learning is
   best-effort; it must never crash a live craft).

3. **Resolution boundary (impure) — `resolve_craft_yields(game_data, history)`.** A pure-ish
   helper that returns a `dict[str, int]` of `{code: learned-or-prior-or-1}`: start from
   `game_data`'s per-recipe priors (`craft.quantity`), override each with
   `history.observed_craft_yield(code)` when present. `GameData.craft_yield(code)` itself returns
   only the **prior** (no history dependency, keeping GameData history-free). The override is
   applied at the call sites that already hold both `game_data` and `history` — the goals that
   invoke recipe-closure / the craft generator. Those public **wrappers** gain an optional
   `yields: Mapping[str,int] | None` parameter (defaulting to the all-prior map from `game_data`
   when omitted); the proved **pure** cores receive this plain `yields` map as an explicit input
   — learning never enters the kernel (matches the "abstract dependencies as inputs" convention).

### Planning propagation (consumes resolved `yields`)

- **`_closure_demand` (PROVED core — the over-gather bug).** To produce `m` of a node with
  yield `Y`, craft `⌈m/Y⌉` batches; children scale by `⌈m/Y⌉ × qty_per`, not `m × qty_per`.
  This adds ceil-division batch semantics to the recursion. Surplus (e.g. need 3, Y=2 → craft 2
  → 1 extra) flows into the existing overstock / inventory-cap machinery — no special handling.
- **`_raw_units` (PROVED core).** Per-item raw cost: a craft yielding `Y` produces `Y` items for
  one set of inputs, so per-item raw units divide by `Y` (batch/ceil semantics consistent with
  `_closure_demand`). Kept consistent so the closure cost heuristic stays sound.
- **`crafting.apply` (Python, not a proved core).** Credit `new_inventory[self.code] += runs × Y`;
  `task_progress += runs × Y` (a crafting task counts items produced). For the
  `projected_skill_xp_delta` proxy: use the **learned real `xp`-per-craft × runs** when observed;
  otherwise the yield-scaled prior (`runs × Y`, per the per-item decision). `is_applicable`'s
  ingredient check (`mat_qty * runs`) is already correct (inputs consumed per run, independent
  of yield) — unchanged.
- **`next_craft_core` / `craft_plan_gen` (generator).** Emit `⌈need/Y⌉` runs, not `need`.
- **`min_crafts` — unchanged.** Its docstring already proves "one craft per produced node is a
  sound LOWER bound irrespective of per-action craft batching." A looser-but-sound bound under
  batching; no change.

## Proof boundary / formal lockstep

The proved, extracted `RecipeClosure` core (`_closure_visited`, `_raw_units`, `_closure_demand`)
is the boundary. Changes in lockstep:
- `formal/Formal/RecipeClosure.lean` — the hand model `def`s for `_raw_units` / `_closure_demand`
  gain the `yields` input and the `⌈m/Y⌉` ceil-batch arithmetic; role theorems re-proved
  (the demand-soundness / closure-completeness contracts must hold with batching).
- `formal/Formal/Contracts.lean` — re-pin the exact (now yield-parameterised) statements.
- `scripts/extract_lean.py` registry + regenerate `formal/Formal/Extracted/RecipeClosure.lean`
  (and any importer, e.g. `RecipeCostMemo`) so the extracted image matches the Python cores.
- `formal/diff/` — differential harness feeds yield-2 recipes and asserts Python↔oracle agreement
  on `_closure_demand` / `_raw_units`; `formal/diff/mutate.py` gains anchors for the yield /
  ceil-division logic so a dropped `⌈⌉` or a `× Y` omission is killed.
- `_closure_visited` (which nodes) is yield-independent — unchanged.

`min_crafts` / `MinCrafts` core: unchanged (already batching-sound).

## Error handling / safety (CLAUDE.md)

- **Use only API data:** the prior is `CraftSchema.quantity`; the learned value is observed from
  real craft responses. No invented yields. Default 1 only when there is no recipe and no
  observation (an item that is not crafted).
- **No new error-handling levels:** `record_craft_yield` follows the existing best-effort
  `record_*` contract (log + swallow), so a learning write never aborts a live craft. No
  `except Exception`.
- **Deterministic-yield reality:** because crafting is deterministic, learned and prior agree in
  normal play; the learned layer exists to ground-truth (and to cover a wrong/UNSET prior),
  satisfying the "learned, not assumed" requirement without adding variance modeling.

## Testing

- **Unit:** `craft_yield` resolution (learned > prior > 1; UNSET → 1); `_build_items` reads
  `craft.quantity`; `record_craft_yield` / `observed_craft_yield` round-trip; `execute` records
  the produced quantity + xp from a fabricated `details` (`SkillInfoSchema`); `apply` credits
  `runs × Y` for inventory / task_progress / xp-proxy (learned-xp path and prior path);
  generator emits `⌈need/Y⌉` runs; closure demand of a yield-2 root gathers `⌈need/2⌉ × inputs`.
- **Differential:** yield-2 (and yield-3, need-not-divisible) recipes agree Python↔Lean for
  `_closure_demand` / `_raw_units`.
- **Mutation:** yield/ceil mutants (drop `⌈⌉`, drop `× Y`, off-by-one batch) killed.
- **Regression:** with all-`Y=1` data and an empty learning store, every existing planner test
  is unchanged (the feature is a no-op against today's data). Full `formal/gate.sh` + unit suite
  100% coverage.

## Known limits / non-goals

- **Bot not running during gate runs** (serialize-gate-runs lesson): the formal gate / mutation
  must not run while `artifactsmmo play` is live.
- **XP semantics recheck:** the per-item XP prior (and the learned-xp path) assume the server's
  reported `details.xp` is authoritative per craft; confirm against live data at P0 regen.
- **Out of scope:** the P1 client regen, equip/unequip arrays, GE renames, and all other Season 8
  items — separate phases in [[PLAN_season8_readiness]].

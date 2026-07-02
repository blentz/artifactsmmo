# PLAN: Jewelrycrafting grind smelt-stall (amulet livelock)

## Symptom
Robby's objective is `ObtainItem(life_amulet, amulet_slot)` but he perpetually
fights slimes / crafts potions and never crafts the amulet. `jewelrycrafting`
XP is frozen (level 3) across all 15 recorded sessions; zero copper_rings are
ever crafted.

## Root cause (confirmed live, char=Robby, 2026-07-02)

Live state: `jewelrycrafting=3`, `copper_ore=60` (inv), `copper_bar=0`,
`copper_ring=2` (bank), `feather=5` (bank), `red_slimeball=3` (inv).
The amulet recipe (`jewelrycrafting 5`, `feather×4 + red_slimeball×2`) is
otherwise satisfiable — the **only** blocker is jewelrycrafting 3→5, leveled by
crafting copper_rings (`copper_ring = 6×copper_bar`, `copper_bar = 10×copper_ore`,
smelt skill = mining).

The jewelry-grind goal `GatherMaterials(copper_ring, {copper_ring: 3})` produces
an **empty plan** (`plan_len=0`) even though 60 ore is on hand — enough for one
ring. Mechanism:

1. Batch sizing (`size_intermediate_craft` → `craft_batch_size_pure`) sizes the
   smelt by inventory SPACE, giving **`Craft(copper_bar×9)`** (needs 90 ore).
2. `CraftAction.is_applicable` is **all-or-nothing**: it requires
   `inventory[mat] >= mat_qty * quantity` for the FULL batch. With only 60 ore
   (enough for 6 bars, not 9), `Craft(copper_bar×9).is_applicable = False`.
3. It is the only bar-making action instance; the `copper_ore` gather is pruned
   (coverage credits the 2 owned rings). So: cannot smelt (batch too big for the
   ore), cannot gather more ore → **no plan → jewelrycrafting frozen → amulet
   never built.** The arbiter then falls through to band-0 guards (potions/heal)
   and fallback slime-grind — the observed "fighting instead of crafting."

## Fix (chosen approach: partial applicability)

**A craft that can produce ≥1 unit is APPLICABLE and produces what the on-hand
inputs allow — full satisfaction is ideal, but any `effective ≥ 1` contributes.**
This kills the entire oversized-batch class, not just this case.

Define, in `CraftAction` (`src/artifactsmmo_cli/ai/actions/crafting.py`):

```python
def _effective_quantity(self, state, game_data) -> int:
    recipe = game_data.crafting_recipe(self.code) or {}
    eff = self.quantity
    for mat, q in recipe.items():
        eff = min(eff, state.inventory.get(mat, 0) // q)
    return max(0, eff)
```

Then:
- `is_applicable`: keep the workshop / recipe / **skill-gate** checks (skill gate
  MUST stay — it prevents the feather_coat CPU-peg regression), but replace the
  full-batch material check with `_effective_quantity(...) >= 1`.
- `apply`: consume/produce `_effective_quantity(state)` instead of `self.quantity`
  (mats consumed, item produced, and `projected_skill_xp_delta` all scale to the
  effective amount).
- `cost`: **UNCHANGED** — stays `5.0 * self.quantity + dist`. The proved
  planner-admissibility model (`Formal/PlannerAdmissibility.lean`, `qtyCost`)
  keys craft cost to the REQUESTED quantity, and the differential test
  (`formal/diff/test_action_cost_nonneg_diff.py`) enforces the lockstep (it even
  calls `cost(s, None, None)`). Making cost material-dependent breaks that lockstep
  for no benefit — a partial craft is merely slightly over-costed (still ≥ 0,
  search stays sound). Confirmed: reverting cost turns the differential green.
- `execute` (via `player._execute`): recompute `effective` from the LIVE state and send THAT to
  `CraftingSchema(quantity=...)`. The server rejects an unaffordable quantity, so
  execute must clamp — never send `self.quantity` blindly. (Same execution-time
  rebatch pattern already used for consumable cook / potion batching.)

### Validation (already run — scratchpad diagnostics, live Robby state)
- BEFORE (all-or-nothing): `plan_len=0`, never reaches `Craft(copper_ring)`.
- AFTER (partial-applicability patch): `plan_len=2` =
  `Craft(copper_bar×10)` (effective **6** from 60 ore) → `Craft(copper_ring×1)`
  → jewelrycrafting gains XP. Progress restored.

## Proof / gate impact
- `CraftAction.apply` is mirrored in Lean: `Formal/ApplyBaseline.lean::craftApply`
  + `craftApply_preserves_baseline` (audited). That theorem proves only
  **baseline-field preservation**, independent of the quantity arithmetic — so
  partial-qty math should NOT break it. Re-run `lake build` + axiom lint to
  confirm; do not weaken the theorem.
- The binding constraint is the **differential gate**: Python `CraftAction.apply`
  vs FakeServer vs live API must compute the same result. Update the FakeServer
  craft handler to clamp to the effective (affordable) quantity so Python and
  server agree. Confirm the live API's behavior on an over-request first (expect
  400 → hence the execute-side clamp).
- Run full `gate.sh` (differential + mutation + `lake` + axiom lint). Serialize
  against the live bot: STOP the bot first; never run the gate while anything
  imports `src` (incl. the bot).

## Status: IMPLEMENTED (2026-07-02)
1. [DONE] `CraftAction.effective_quantity`; `is_applicable` (≥1, skill gate kept)
   and `apply` (produce effective batch) rewired. `cost` left unchanged (lockstep).
2. [DONE] `player._execute` clamps the craft quantity to the feasible batch before
   the API call. (No FakeServer change needed — no craft-apply differential core.)
3. [DONE] TDD regression tests: `test_actions.py::TestCraftAction`
   (partial-applicable, largest-feasible apply, skill-gate, no-recipe) +
   `test_player.py::TestExecute::test_execute_clamps_craft_quantity_to_affordable`.
4. [DONE] Verified: full suite 4546 pass; mypy clean; crafting.py 100% cov;
   `formal/diff/` 687 pass (Lean↔Python lockstep intact); live planner probe:
   `GatherMaterials(copper_ring,{copper_ring:3})` now plans
   `Craft(copper_bar)→Craft(copper_ring)` (was plan_len=0).
5. [TODO — user] Restart the bot; confirm `jewelrycrafting` XP rises and the
   amulet is crafted.

## Pre-existing gate drift (NOT from this change — flag separately)
`formal/gate.sh` is red on this branch independent of this fix, from an earlier
`skill_step_dispatch.py` edit that didn't regenerate:
- `(b'') proof-concept index` stale → `gen_proof_concept_index.py`.
- `(b''') extraction drift` — `combine_dispatch_pure` source line 93→96 in the
  `SkillStepDispatch` extraction comment → regenerate the extraction.
Both are in `formal/` / `skill_step_dispatch.py`, untouched here.

## Optional complementary cleanup (efficiency, not required for the fix)
Net-demand sizing: build the closure `chain` in
`GatherMaterialsGoal.relevant_actions` from `needed − owned` (subtract owned
finished copies) so the smelt is sized to what's actually needed (×6 not ×9),
avoiding over-crafting bars for rings already owned. Impure-caller-only; no proof
change. Partial applicability already unblocks progress; this only trims waste.

## Secondary observations (not the freeze cause)
- `CraftPotionsGoal`/`RestoreHP` band-0 guards preempt ~1/3 of cycles; harmless
  once the jewelry step is servable. Worth confirming potion target isn't
  over-provisioning.
- The bot restarts frequently (15 short sessions). Partial applicability makes
  each single cycle craft ring progress, so restarts no longer strand the chain.
- Trigger was 2 rings accumulating in the bank from earlier partial attempts.

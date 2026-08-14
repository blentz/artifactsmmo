# Stop at the Achievable Step Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route a gear objective to its deepest achievable prerequisite when the objective itself is not yet achievable, by asking the traversal directly instead of a depth-bound proxy that can no longer fire.

**Architecture:** `_equippable_goal` currently routes to `_gather_goal_for_unreachable_equippable` only when `UpgradeEquipmentGoal.is_plannable` is False. That predicate compares `min_plan_length` (max 15 across all 321 real recipes) against `max_depth` 32, so it never fires and the routing is dead. Replace the trigger with the direct question the helper already asks internally — is the deepest achievable node something other than the goal itself — and thread the already-computed step into the helper so the traversal runs once per decision.

**Tech Stack:** Python 3.13, `uv`, pytest, Lean 4 (`formal/`), differential + mutation gate (`formal/gate.sh`).

**Spec:** `docs/superpowers/specs/2026-08-14-stop-at-the-achievable-step-design.md`

## Global Constraints

- Run every Python command through `uv run`. `uv` is at `/home/blentz/.local/bin/uv`; `unset VIRTUAL_ENV` first.
- No inline imports; all imports at the top of the file. No `if TYPE_CHECKING`. Never catch `Exception`. One behavioral class per file.
- Tests live in `tests/`. TDD: write the failing test, run it, see it fail for the right reason, then implement.
- **Do NOT run the full `tests/` suite** inside a task — it takes minutes and has cost agents their sessions. Run `tests/test_ai/` (~1 min) plus focused files. The full gate runs once, in Task 3.
- Never `git add -A` — stage explicit paths.
- Never `git checkout <path>` or `git stash` to undo anything. Copy aside with `cp`, copy back.
- All seven formal gate scripts must pass, run from `formal/`: `check_axioms.sh`, `check_no_sorry.sh`, `check_extraction.sh`, `check_no_orphan_modules.sh`, `check_proof_concept_index.sh`, `check_audit_generated.sh`, `check_proof_citations.sh`.
- Any `Formal.X.y` citation you write must name a declaration or module that exists, or carry the `NOT-PROVED:` tag. `check_proof_citations.sh` enforces this.

---

### Task 1: Route on the step, not on the depth bound

**Files:**
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py:457-460` (helper signature), `:497` (step resolution), `:589-590` (the trigger)
- Test: `tests/test_ai/scenarios/test_greater_wooden_staff_reachable.py`

**Interfaces:**
- Consumes: `actionable_step(root, state, game_data, ctx) -> MetaGoal | None` (imported at `strategy_driver.py:104`); `ObtainItem` (imported at `:97`); the scenario file's `_game_data()` and `_state_without_banked_planks()` helpers.
- Produces: `_gather_goal_for_unreachable_equippable(code, state, game_data, equip_max_depth, ctx=NO_PROFILE_CONTEXT, step: ObtainItem | None = None) -> GatherMaterialsGoal` — the new trailing keyword-only-by-convention `step` parameter. Existing callers pass nothing and are unaffected.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ai/scenarios/test_greater_wooden_staff_reachable.py`. Read the file first for its existing imports and helper names — `_game_data()` and `_state_without_banked_planks()` already exist and build the REAL 321-recipe catalog.

```python
def test_from_scratch_routes_to_the_achievable_step_not_the_equippable():
    """The bug this fixes: `is_plannable` maxes at 15 against max_depth 32 over
    all 321 real recipes, so it never rejects, and the arbiter planned a
    100,080-node / ~49.5s UpgradeEquipment search instead of a 2-node gather.

    `actionable_step` already returned ObtainItem('spruce_wood', 10) here.
    Nothing was asking it."""
    gd, state = _game_data(), _state_without_banked_planks()
    goal = strategy_driver._equippable_goal(
        "greater_wooden_staff", "weapon_slot", state, gd)
    assert isinstance(goal, GatherMaterialsGoal)
    assert goal.target_item == "spruce_wood"
    assert goal.needed == {"spruce_wood": 10}


def test_banked_materials_still_route_to_the_craft():
    """Anti-starvation: once every direct prerequisite is satisfied — from the
    BANK, via a ready withdraw source — the traversal returns the root and the
    craft must fire. A routing that always gathered would never equip."""
    gd, state = _game_data(), _state_with_banked_planks()
    goal = strategy_driver._equippable_goal(
        "greater_wooden_staff", "weapon_slot", state, gd)
    assert isinstance(goal, UpgradeEquipmentGoal)


def test_the_traversal_runs_once_per_decision(monkeypatch):
    """The helper re-derives the step when not given one. Threading it through
    must not double the walk — `actionable_step` is the expensive part."""
    calls = []
    real = strategy_driver.actionable_step

    def counting(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(strategy_driver, "actionable_step", counting)
    gd, state = _game_data(), _state_without_banked_planks()
    strategy_driver._equippable_goal(
        "greater_wooden_staff", "weapon_slot", state, gd)
    assert len(calls) == 1, f"actionable_step ran {len(calls)} times"
```

`_state_with_banked_planks` may not exist — the file has `_state_without_banked_planks`. If the banked variant is absent, build it from the existing state builder by adding `{"spruce_plank": 16, "blue_slimeball": 98}` to `bank_items`, matching R2D2's traced bank. Follow whatever construction the file already uses; do not invent a new fixture style.

- [ ] **Step 2: Run tests to verify they fail for the right reason**

Run: `unset VIRTUAL_ENV; /home/blentz/.local/bin/uv run pytest tests/test_ai/scenarios/test_greater_wooden_staff_reachable.py -v --no-cov`

Expected: `test_from_scratch_routes_to_the_achievable_step_not_the_equippable` FAILS because `_equippable_goal` returns an `UpgradeEquipmentGoal`. If it fails on an import or a missing fixture instead, fix that first — a test that fails for the wrong reason proves nothing.

- [ ] **Step 3: Add the `step` parameter to the helper**

In `src/artifactsmmo_cli/ai/strategy_driver.py`, change the signature at `:457-460`:

```python
def _gather_goal_for_unreachable_equippable(
    code: str, state: WorldState, game_data: GameData, equip_max_depth: int,
    ctx: SelectionContext = NO_PROFILE_CONTEXT,
    step: ObtainItem | None = None,
) -> GatherMaterialsGoal:
```

and replace the step resolution at `:497`:

```python
    resolved = step if step is not None else actionable_step(
        ObtainItem(code=code, quantity=1), state, game_data, ctx)
    if isinstance(resolved, ObtainItem) and resolved.code != code:
        tgt_code, tgt_qty = gather_step_target(
            code, resolved.code, resolved.quantity,
            game_data.crafting_recipes, owned, equip_max_depth,
            game_data.max_gather_yield)
        return GatherMaterialsGoal(target_item=tgt_code, needed={tgt_code: tgt_qty})
```

Only the first three lines change; the `gather_step_target` call and the return
are exactly as they are today, re-shown so you can see what `resolved` feeds.

Add to the docstring that `step` is the caller's already-computed `actionable_step` result, passed so the traversal runs once per decision, and that `None` means "derive it here" for callers that have not computed it.

- [ ] **Step 4: Replace the trigger**

At `:589-590`, replace:

```python
    if upgrade.is_plannable(state, game_data):
        return upgrade
```

with:

```python
    # Route on the STEP, not on a depth-bound proxy for it. `is_plannable`
    # compares min_plan_length against max_depth 32, and min_plan_length maxes
    # at 15 across all 321 real recipes (see UpgradeEquipmentGoal.max_depth's
    # SECOND RESIDUAL), so it never rejects and this routing was dead — the
    # arbiter planned a 100,080-node search that timed out instead of the
    # 2-node gather `actionable_step` had already identified.
    #
    # The direct question is the one the helper asks internally: is the deepest
    # achievable node something OTHER than the goal itself? It self-corrects in
    # both directions — materials missing routes to the gather, materials
    # banked or carried leafs at the root and fires the craft — so there is no
    # threshold to tune and no bound to rot.
    step = actionable_step(ObtainItem(code=code, quantity=1), state, game_data, ctx)
    if not (isinstance(step, ObtainItem) and step.code != code):
        return upgrade
```

`isinstance(step, ObtainItem)` covers the `None` case (cyclically blocked, or every branch dead-ended) without a separate check, and the helper's own fallback to the direct recipe still handles a non-`ObtainItem` node.

Then thread the step into the existing call a few lines below:

```python
        return _gather_goal_for_unreachable_equippable(
            code, state, game_data, upgrade.max_depth, ctx, step=step)
```

`is_plannable` is NOT removed — it remains a waste-avoidance filter, which is what its docstring says it is. It simply stops being the routing trigger.

- [ ] **Step 5: Run the tests**

Run: `unset VIRTUAL_ENV; /home/blentz/.local/bin/uv run pytest tests/test_ai/scenarios/test_greater_wooden_staff_reachable.py -v --no-cov`
Expected: all PASS, including the three pre-existing tests in that file.

- [ ] **Step 6: Prove the acceptance test discriminates**

This plan's predecessor shipped a fix whose test stayed green with the defect reinstated, and its acceptance test passed identically before and after the work. Prove this one does not.

```bash
cp src/artifactsmmo_cli/ai/strategy_driver.py /tmp/sd.bak
# restore the old trigger by hand: replace the isinstance(step, ObtainItem) guard
# with `if upgrade.is_plannable(state, game_data): return upgrade`
unset VIRTUAL_ENV; /home/blentz/.local/bin/uv run pytest \
  tests/test_ai/scenarios/test_greater_wooden_staff_reachable.py -q --no-cov
# EXPECT: test_from_scratch_routes_to_the_achievable_step_not_the_equippable FAILS
cp /tmp/sd.bak src/artifactsmmo_cli/ai/strategy_driver.py
```

Paste both outputs into the report. **Never `git checkout` to restore** — it has destroyed uncommitted work in this repo.

- [ ] **Step 7: Run the regression surface**

Run: `unset VIRTUAL_ENV; /home/blentz/.local/bin/uv run pytest tests/test_ai/ -q --no-cov`

Expected: all pass. This change alters which goal is planned for every equippable whose materials are incomplete, so `test_strategy_driver.py`, `test_upgrade_reachability_gate.py` and `test_supply_bank_plannability.py` are the likely movers. **A test that now fails because the routing changed is a real finding — report it, do not rebaseline it.** The three `steel_boots` tests rewritten in the previous branch asserted that an unplannable objective is admitted and times out; if this change routes them instead, that is the fix working and the assertion should be updated to say so.

- [ ] **Step 8: Lint and type-check**

Run: `unset VIRTUAL_ENV; /home/blentz/.local/bin/uv run mypy src/artifactsmmo_cli/ai/strategy_driver.py && /home/blentz/.local/bin/uv run ruff check src/ tests/`
Expected: clean. `mypy --strict` is enforced by the pre-commit hook; the `resolved` variable exists specifically so the `MetaGoal | None` return narrows cleanly to `ObtainItem`.

- [ ] **Step 9: Commit**

```bash
git add src/artifactsmmo_cli/ai/strategy_driver.py \
        tests/test_ai/scenarios/test_greater_wooden_staff_reachable.py
git commit -m "fix(ai): ask the traversal, not a proxy that can no longer fire

_equippable_goal routed to the achievable-step helper only when is_plannable
was False. min_plan_length maxes at 15 across all 321 real recipes against
max_depth 32, so it never rejected and the routing was dead: the arbiter planned
a 100,080-node / ~49.5s UpgradeEquipment search that timed out, while
actionable_step had already returned ObtainItem(spruce_wood, 10).

Route on the step itself. Self-corrects both ways — materials missing gathers,
materials banked or carried crafts — with no threshold to tune."
```

---

### Task 2: Correct the docstrings that describe the old trigger

Several docstrings explain the routing in terms of `is_plannable`. After Task 1 they describe a mechanism that no longer decides anything. This repo has just spent a whole branch on comments claiming more than the code supports; leaving these would add to that count.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py:513-536` (`_equippable_goal`'s docstring), `:461-462` (the helper's opening line)
- Modify: `src/artifactsmmo_cli/ai/goals/progression.py:114`, `:241`

**Interfaces:**
- Consumes: Task 1's behaviour.
- Produces: nothing; documentation only.

- [ ] **Step 1: Read each site and check what it now claims**

Run: `grep -n "is_plannable" src/artifactsmmo_cli/ai/strategy_driver.py src/artifactsmmo_cli/ai/goals/progression.py`

For each hit in a docstring or comment, decide whether it still describes what the code does. `_equippable_goal`'s docstring currently says the routing happens "while the target is depth-unreachable" and that some chains "will be admitted, attempted, and time out rather than being routed to the flat-leaf fallback" — after Task 1 the second clause is false and the first names the wrong trigger.

- [ ] **Step 2: Rewrite them to describe the step-based trigger**

Say what is true: routing happens when `actionable_step` returns a node other than the goal, `is_plannable` remains a waste-avoidance filter over a lower bound and no longer decides routing, and the previous depth-bound trigger is dead on real data (max 15 vs 32 over 321 recipes) rather than merely loose.

Keep the helper's admissibility paragraph at `:489-493` intact — it argues the routed step is a genuine prerequisite never harder than the declined root, which this change does not affect.

- [ ] **Step 3: Verify no citation broke**

Run: `cd formal && bash gate/check_proof_citations.sh`
Expected: `proof-citation check OK`. If you named a `Formal.X.y` while rewriting, it must resolve or carry `NOT-PROVED:`.

- [ ] **Step 4: Commit**

```bash
git add src/artifactsmmo_cli/ai/strategy_driver.py src/artifactsmmo_cli/ai/goals/progression.py
git commit -m "docs(ai): the routing trigger is the step, not the depth bound"
```

---

### Task 3: Full gate and runtime activation

**Files:**
- Modify: `docs/superpowers/specs/2026-08-14-stop-at-the-achievable-step-design.md` (residuals, if the run finds any)

**Interfaces:**
- Consumes: Tasks 1 and 2.
- Produces: a green gate and a runtime-verified change.

- [ ] **Step 1: Confirm nothing else is importing `src`**

Run: `pgrep -af artifactsmmo`
Expected: empty. The gate must not run concurrently with the bot or another test run.

- [ ] **Step 2: Run the full gate**

```bash
cd /home/blentz/git/artifactsmmo
bash formal/gate.sh > /tmp/gate.log 2>&1; echo "rc=$?"
tail -60 /tmp/gate.log
```

**Never pipe the gate into `tail` directly** — the pipeline reports the tail's exit code, and a visible `GATE FAIL` has been read as rc=0 in this repo.

Known flaky, not a real failure: an unraisable `PytestUnraisableExceptionWarning` from an unclosed asyncio loop, which attaches to whatever test is running — the victim varies between runs (`tests/test_tui/test_app.py`, `tests/test_multi/test_multi_run.py`). Re-run the named module standalone and say so. A second known flake is `test_coordination_store.py` losing a SQLite lock race under `-n auto`.

- [ ] **Step 3: Runtime activation**

Green tests are not enough in this repo. Show the routing firing against live data:

```bash
unset VIRTUAL_ENV; /home/blentz/.local/bin/uv run artifactsmmo plan R2D2 2>&1 | tee /tmp/plan-r2d2.txt
```

Expected: a gather plan for a material on the gear target's chain, rather than `<-- NO PLAN` with the equippable abandoned. Report exactly what you observe. If no live character currently has an incomplete gear target, say so and demonstrate via `--scenario l1_fresh` instead — and label that as the weaker evidence it is.

- [ ] **Step 4: Record any new residual**

If the gate or the live run surfaces something this design did not anticipate, append it to the spec's Residuals section in the spec's voice. Do not quietly fix scope creep; name it.

- [ ] **Step 5: Commit**

```bash
git add -u docs/superpowers/specs/2026-08-14-stop-at-the-achievable-step-design.md
git commit -m "chore: gate green and runtime-verified for step-based routing"
```

Stage explicit paths. If nothing changed in Step 4, skip this commit.

---

## Self-Review

**Spec coverage.** The trigger replacement → Task 1 (design §"The trigger becomes the step itself"). The `step=` threading → Task 1 Step 3. Anti-starvation and degenerate cases → Task 1 Steps 1 and 4 (`isinstance` covers `None`; the helper's existing fallback covers non-`ObtainItem`). Docstrings → Task 2. Formal obligations → Task 2 Step 3 and Task 3 Step 2; the spec states there are no new proof obligations, and none of these tasks add one. Testing and the discrimination proof → Task 1 Steps 5–7. Runtime activation → Task 3 Step 3. Residuals → Task 3 Step 4.

**Deliberately not covered**, per the spec's non-goals: the acquisition-aware heuristic, differential landmark heuristics, and repairing `min_plan_length`/`min_crafts`. All three are recorded in the spec with reasons.

**Placeholder scan.** Clean. An earlier draft of Task 1 Step 3 showed a mistyped `needed=` expression with a correction beside it; a plan that contains knowingly-wrong code an implementer might copy is worse than one that does not, so the wrong version is gone and the unchanged lines are re-shown only for context.

**Type consistency.** `step: ObtainItem | None` in Task 1 Step 3 matches `step=step` passed in Step 4, where `step` has already been narrowed by `isinstance(step, ObtainItem)`. `actionable_step` returns `MetaGoal | None`; the `resolved` local exists so that narrowing happens in one place for `mypy --strict`.

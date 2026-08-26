# Wave 4 — GEAR_REVIEW becomes a graph node

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the `GEAR_REVIEW` guard rung and the `GearLatch` standing arm, replacing them with two `Decision` nodes in the resolution walk, so "this fight is blocking me" stops being a sticky latch that can preempt the objective indefinitely.

**Architecture:** Two new `Decision[MetaGoal]` nodes at the head of `resolve_root`'s walk. They read `task_horizon.resolve_task_horizon` — the existing single producer of the three-way verdict — and map its three verdicts one-to-one onto graph outcomes. A `Decision` is constructed fresh each cycle and carries nothing across cycles, which is what makes the freeze unrepresentable rather than merely fixed.

**Tech Stack:** Python 3.13, `uv`, pytest, mypy --strict, ruff, Lean 4 (`formal/`).

**Spec:** `docs/superpowers/specs/2026-08-23-wave4-guards-design.md` — **read §12 first.** It is the 2026-08-25 re-derivation and it overrides §5.1 and §5.4 wherever they disagree.

## Global Constraints

- `uv run` prefixes every Python command.
- Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- `bash formal/gate.sh` green (rc=0) at the end of every task. One command, ~5 min.
- No inline imports. No `if TYPE_CHECKING`. No bare `except Exception`.
- ONE behavioral class per file.
- API data or fail — never default around missing game data.
- Mutation anchors must resolve to exactly one site; refresh them in the SAME commit as the edit.
- Never `git checkout <path>` to undo a probe — `cp` aside first.
- Live claims rest on `~/.cache/artifactsmmo/learning.db` only, never on `play-trace-*.jsonl`.

## Pre-flight: what §12 already settled

Nine of §5.4's eleven rows drifted. Do not read §5.4's line numbers — use §12.2's
table. Two substantive corrections bind this plan:

1. `map_guard`'s GEAR_REVIEW branch is **`strategy_driver.py:358-442`, 85 lines**,
   and contains the `HORIZON_LEVEL_UP` arm added for a user requirement on
   2026-08-25. Task 4.2 must re-home it, not delete it.
2. `has_combat_deficit` and `deficit_upgrade_target` are now consumed by
   `ai/task_horizon.py`, which did not exist when the design was written. The new
   nodes read the **horizon**, never `combat_deficit` directly — re-deriving the
   fact would be the second producer §3.2 warns about.

---

## Task 4.0: Scenarios that record today's behaviour

**Files:**
- Modify: `src/artifactsmmo_cli/ai/scenario.py` (+3 `ScenarioCharacter`s)
- Test: `tests/test_ai/scenarios/test_slot_coverage.py`

**Interfaces:**
- Produces: three scenario cells carrying a `monsters` task, named
  `w4_gear_closes`, `w4_level_up_closes`, `w4_out_of_reach`. Task 4.2 flips their
  expected values; nothing else consumes them.

Without this, every 4.2 assertion is vacuous (§0.6). The scenarios assert
**today's** guard behaviour so the 4.2 diff is against recorded numbers.

- [ ] **Step 1: Read the three horizon verdicts and pick states that produce them**

`resolve_task_horizon(state, game_data)` returns `None`, or a `TaskHorizon` whose
`verdict` is `HORIZON_GEAR`, `HORIZON_LEVEL_UP`, or `HORIZON_OUT_OF_REACH`. Pick
one existing scenario character per verdict as a base. Verify the verdict with a
throwaway script before writing the cell — do NOT assume a state produces the
verdict you want.

- [ ] **Step 2: Add the three cells to `scenario.py`**

Follow the existing `ScenarioCharacter` construction exactly; each cell needs
`task=(...)` set to a `monsters` task whose monster is the blocked one. Comment
each with its MEASURED verdict, in the style of the existing cells at
`scenario.py:1144` and `:1239`.

- [ ] **Step 3: Write tests asserting today's behaviour**

```python
def test_w4_gear_closes_fires_gear_review_today():
    """PRE-WAVE-4 baseline. Task 4.2 flips this to assert the node's answer."""
    state, gd, ctx = _cell("w4_gear_closes")
    assert GuardKind.GEAR_REVIEW in active_guards(ctx, state, gd)
```

Write the matching two for `w4_level_up_closes` and `w4_out_of_reach`. The
out-of-reach cell must assert GEAR_REVIEW does **not** fire.

- [ ] **Step 4: Run and confirm they pass against today's code**

Run: `uv run pytest tests/test_ai/scenarios/test_slot_coverage.py -v`
Expected: PASS. These are characterization tests — passing now is the point.

- [ ] **Step 5: Gate and commit**

```bash
bash formal/gate.sh > gate.log 2>&1; echo "rc=$?"
git add -A && git commit -m "test(wave4): three task-carrying scenario cells, one per horizon verdict"
```

---

## Task 4.1: Promote `_classify_target` to `classify_target`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/objective.py` (definition ~`:440`, call site ~`:438`)

**Interfaces:**
- Produces: `ObjectiveTiers.classify_target(code, state) -> GearTarget`, public.
  Task 4.2's `WhichSlotClosesTheFight` calls it.

Isolated rename, mechanically verifiable. **Do not trust the design's `:436`/`:439`
citations** — §12.2 records them as drifted; find the symbol.

- [ ] **Step 1: Rename the definition and every caller**

```bash
grep -rn "_classify_target" --include=*.py src/ tests/
```
Rename all hits. Assert the edit landed — a `str.replace` on a missing anchor is
a silent no-op (this repo has three recorded instances).

- [ ] **Step 2: Verify zero stragglers**

Run: `grep -rn "_classify_target" --include=*.py src/ tests/ formal/`
Expected: no output.

- [ ] **Step 3: Gate and commit**

---

## Task 4.1b: `ai/decisions/route.py`, inert

**Files:**
- Create: `src/artifactsmmo_cli/ai/decisions/route.py`
- Test: `tests/test_ai/test_decisions_route.py`

**Interfaces:**
- Produces: `route_price(meta_goal, state, game_data, ctx) -> float` — the
  `ObtainItem` arm only. Wave 6 completes the dispatch for the other variants.
- Consumes: `acquisition_cost.acquisition_actions`.

This is wave 6's increment 5.1, taken early. Without it, 4.2 puts the first
`acquisition_cost` import under `ai/decisions/` and wave 6's O6 census is red the
day it lands (§11 C9). It ships with **no production caller** — that is intended,
and the test suite is what keeps it honest.

- [ ] **Step 1: Write the failing test**

```python
def test_route_price_obtain_item_matches_acquisition_actions():
    state, gd, ctx = _fixture()
    goal = ObtainItem(code="iron_sword", quantity=1)
    assert route_price(goal, state, gd, ctx) == acquisition_actions(
        "iron_sword", 1, state, gd, ctx)
```

- [ ] **Step 2: Run it, confirm ImportError**

Run: `uv run pytest tests/test_ai/test_decisions_route.py -v`
Expected: FAIL — no module `route`.

- [ ] **Step 3: Implement the `ObtainItem` arm only**

Raise `NotImplementedError` with the variant name for other `MetaGoal` kinds —
wave 6 fills them. A silent default here would be a wall.

- [ ] **Step 4: Run, confirm pass; add mutation anchors**

- [ ] **Step 5: Gate and commit**

---

## Task 4.2: The two nodes — THE behaviour change

**Files:**
- Modify: `src/artifactsmmo_cli/ai/decisions/root.py` (+2 classes, entry change)
- Modify: `src/artifactsmmo_cli/ai/tiers/guards.py` (−`GEAR_REVIEW` rung, leaving **12**)
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py` (−`:358-442`, −`_materials_in_hand`, −2 imports)
- Modify: `src/artifactsmmo_cli/ai/selection_context.py:73` (−`gear_review_active`)
- Modify: `src/artifactsmmo_cli/ai/gear_latch.py` (−`_blocked`)
- Modify: `src/artifactsmmo_cli/ai/player.py:3754`
- Modify: ~14 test fixtures

**Interfaces:**
- Consumes: `task_horizon.resolve_task_horizon`, `objective.classify_target` (4.1),
  `decisions/route.route_price` (4.1b).

One commit, because a graph with the node AND the guard is two producers of the
same decision.

### The horizon mapping — the binding requirement from §12.1

Write this table into `IsAFightBlockingMe`'s docstring and pin it by test. The
three verdicts map ONE-TO-ONE onto graph outcomes:

| `resolve_task_horizon` | graph outcome |
|---|---|
| `None` (no blocked task fight) | fall through to `IsMyGearBehindMyTier` |
| `ctx.combat_monster is not None` | fall through — something worth fighting exists |
| `HORIZON_GEAR` | child `WhichSlotClosesTheFight` → `ObtainItem(h.gear_target)` |
| `HORIZON_LEVEL_UP` | `ReachCharLevel(level=state.level + 1)` |
| `HORIZON_OUT_OF_REACH` | fall through; the `TASK_CANCEL` means rung owns the coin case |

`ReachCharLevel` is an existing `MetaGoal` variant, so the LEVEL_UP arm costs an
arm, not a new type. **This arm is not optional** — it is where the
`ReachUnlockLevelGoal(state.level + 1)` currently at `strategy_driver.py:405-412`
goes, and dropping it regresses a user requirement stated 2026-08-25.

- [ ] **Step 1: Write the failing mapping test**

```python
@pytest.mark.parametrize("cell,expected", [
    ("w4_gear_closes",     ObtainItem),
    ("w4_level_up_closes", ReachCharLevel),
])
def test_horizon_verdict_maps_one_to_one(cell, expected):
    state, gd, ctx = _cell(cell)
    root = resolve_root(state, gd, _objective(), ctx, None).root
    assert isinstance(root, expected)

def test_out_of_reach_falls_through_to_the_tier_arm():
    state, gd, ctx = _cell("w4_out_of_reach")
    trail = resolve_root(state, gd, _objective(), ctx, None).trail
    assert "IsAFightBlockingMe" in trail
    assert "IsMyGearBehindMyTier" in trail
```

- [ ] **Step 2: Run, confirm failure for the right reason** (no `IsAFightBlockingMe`)

- [ ] **Step 3: Add the two nodes to `decisions/root.py`**

`IsAFightBlockingMe` reads `ctx.combat_monster` — NOT a separate
`winnable_alternative` parameter (§5.1: `player.py` computes it once and hands
the same value to both, but as two parameters they could drift).

Do **not** re-test `has_craftable_upgrade_any_slot`: the child returns `None` when
the deficit chain is empty and the walk falls through. Re-testing it here would
put the monster-BLIND `find_upgrade_target` in front of the monster-aware one —
the ten-hour `iron_boots` failure.

Do **not** thread `prev_level`, `last_outcome`, or any persisted boolean into
either signature. The moment a node's answer depends on an event N cycles ago,
this IS the guard again and the 981-cycle freeze is back under a new name.

- [ ] **Step 4: Wire `resolve_root`'s entry**

`IsAFightBlockingMe` becomes the entry; it falls through to
`IsMyGearBehindMyTier`. Keep the local `entry:` annotation — mypy 1.18.1 infers
`Leaf = Never` for a bare `Decision[X]` argument without it.

- [ ] **Step 5: Delete the guard side**

Remove the `GEAR_REVIEW` rung from `guards.py` (`:92`, `:115`, `:266-267`), the
`map_guard` branch (`strategy_driver.py:358-442`), `_materials_in_hand`
(`:245` — sole consumer is that branch, grep before deleting), the
`acquisition_actions` and `_gather_goal_for_unreachable_equippable` imports,
`SelectionContext.gear_review_active`, `GearLatch._blocked`, and
`decide_key._GUARD_REPR[GEAR_REVIEW]`.

`obtain_item_routing.py:12-13`'s comment goes stale when the import dies — update
it in the SAME commit.

- [ ] **Step 6: Flip the 4.0 scenarios to the new expected behaviour**

- [ ] **Step 7: Obligations O2, O3, O4, O5**

O2: graph still acyclic, floors raised. O3: one gear-review producer, not two.
O4: the standing condition is not sticky, **proven by exhibition** — a test that
runs the node twice across a cycle boundary and shows no carry. O5: the replan
trigger survived. Each needs its own mutant; a unit-killed mutant needs its OWN
`run_group`.

- [ ] **Step 8: Gate, then verify runtime activation**

Green tests are not runtime activation. Run `uv run artifactsmmo plan <char>` and
confirm `IsAFightBlockingMe` appears in the trail. A planner/goal change that
never fires live is not done.

- [ ] **Step 9: Commit**

---

## Task 4.3: Narrow `GearLatch` to `RegearEdge`

**Files:**
- Rename: `src/artifactsmmo_cli/ai/gear_latch.py` → `regear_edge.py`
- Modify: `src/artifactsmmo_cli/ai/player.py` (6 sites — re-derive, do not trust the design's list)
- Test: `test_plan_or_reuse.py`, `test_player_gear_latch.py`, `test_gear_latch.py`

Pure rename after 4.2 removed the other consumer. What survives is the EDGE arm
(level-up / `error:fight_lost`) plus `should_replan` and `save_plan_commitment` —
its only job is invalidating the plan cache.

- [ ] **Step 1: Re-derive the call sites** (`grep -rn "gear_latch\|GearLatch"`)
- [ ] **Step 2: Rename module, class, and every reference**
- [ ] **Step 3: Assert zero stragglers, including in comments and `formal/`**
- [ ] **Step 4: O5 with its mutant**
- [ ] **Step 5: Gate and commit**

---

## Task 4.4: Lean and oracle

**Files:** the §7 table.

Separable and mechanical, and it must NOT be interleaved with 4.2 — a measure
restatement mixed with a behaviour change is unreviewable.

- [ ] **Step 1: Retire `gearReview` from the ladder**
- [ ] **Step 2: Restate the `D`/`E`/`F` measures**
- [ ] **Step 3: Renumber `DecideKey`**
- [ ] **Step 4: `#print axioms` unchanged; no vacuous theorems**

A modelling constant can be PROOF-INERT — the citation is the only pin. Check
that every liveness hypothesis is still satisfiable.

- [ ] **Step 5: Gate and commit**

---

## Verification

Every task: `bash formal/gate.sh` rc=0, 100% coverage, ruff + mypy --strict clean.

**Live acceptance (§10), re-baselined.** The design's PRE-flip baseline (R2D2 187,
Lor 157, HAL 109, Robby 88, C3P0 37) was measured before `e6a2e37c` and
`63533b82`, which change exactly the behaviour it counts. **Re-measure before
4.2 lands.** Criterion, from `learning.db` only: after the fleet restarts on the
flipped code, no character selects an `UpgradeEquipment*` for more than 200
consecutive cycles while holding a monsters task whose monster is unwinnable and
while a winnable alternative exists.

# LevelSkill Action — Implementation Plan (Phase 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-class GOAP `LevelSkill(skill, target_level)` action whose
`apply` optimistically levels the skill so `CraftAction`'s skill gate is
satisfiable in-search — making the planner able to plan `grind-skill → craft`
from an under-skill state. Phase 1 ships the action **inert** (not yet emitted by
`build_actions`), proven by a planner scenario test and a Lean apply/applicability
mirror.

**Architecture:** `LevelSkill` is a `@dataclass` `Action`. `apply` sets
`state.skills[skill] = target_level` (optimistic single-step, `FightAction`
idiom); `is_applicable` gates on `skills[skill] < target` AND a feasible grind
rung existing now (`skill_grind_target`); `cost` is the honest grind effort from
`SkillXpCurve` (never free). `execute` raises — a `LevelSkill` in a live plan is
expanded by the player skill-grind hook added in Phase 3; in Phase 1 the action
is never emitted, so `execute` is unreachable and the raise documents the
contract. This plan is the first of four sequenced phases (see Roadmap).

**Tech Stack:** Python 3.13, `uv`, GOAP planner (`GOAPPlanner`), Lean 4 decision
mirror (`formal/`), `SkillXpCurve` learned XP model.

## Global Constraints

- Every Python command is prefixed `uv run` (uv at `/home/blentz/.local/bin/uv`, not on the foreground-shell PATH).
- TDD: failing test first, watch it fail, minimal code to pass. Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- No inline imports; all imports at top of file. Never `if TYPE_CHECKING`. Never catch `Exception`. One behavioral class per file.
- `formal/diff/` and `gate.sh` (mutation + Lean + diff) run on any decision-path (`is_applicable`/`apply`/`cost`/`WorldState`) or Lean change — NOT in the default pytest path; run explicitly.
- Serialize gate runs: never run `gate.sh`/`mutate.py` concurrently with anything importing `src` (including the live bot).
- Action identity: the new action's name is `LevelSkill`; `repr` is exactly `LevelSkill(<skill>→<target_level>)` (Unicode arrow `→`, U+2192).
- Commit only when a task's review is clean; do not push unless the user asks.

---

## File Structure

- **Create** `src/artifactsmmo_cli/ai/actions/level_skill.py` — the `LevelSkill(Action)` behavioral class (one class per file). Owns applicability/apply/cost/execute for the skill-grind planner abstraction.
- **Create** `tests/test_ai/test_level_skill_action.py` — unit tests for the action (applicability, apply, cost monotonicity, execute-guard).
- **Create** `tests/test_ai/test_level_skill_planning.py` — the Phase-1 headline: `GOAPPlanner` plans `[…, LevelSkill, …, Craft(target)]` from an under-skill state when `LevelSkill` is in the action set.
- **Modify** `formal/Formal/` — add `LevelSkill` apply/applicability to the action decision mirror; add an Oracle run + key; add a `formal/diff/` differential test and a `formal/diff/mutate.py` anchor. (Exact Lean file located in Task 3.)

---

## Task 1: LevelSkill action

**Files:**
- Create: `src/artifactsmmo_cli/ai/actions/level_skill.py`
- Test: `tests/test_ai/test_level_skill_action.py`

**Interfaces:**
- Consumes: `Action` (`ai/actions/base.py`, abstract `is_applicable/apply/cost/execute`); `WorldState.skills: dict[str,int]` (`ai/world_state.py:69`); `skill_grind_target(skill: str, state: WorldState, game_data: GameData, reserved=frozenset()) -> str | None` (`ai/tiers/skill_grind_target.py:82`); `SkillXpCurve.total_xp_to_reach(current_level: int, target_level: int) -> int` (`ai/learning/skill_xp_curve.py:46`).
- Produces: `LevelSkill(skill: str, target_level: int, xp_curve: SkillXpCurve | None = None)`; `apply` returns a `WorldState` with `skills[skill] == target_level`; `is_applicable` True iff under-target and grindable; `cost` strictly positive and non-decreasing in `target_level - current`; `repr` `LevelSkill(<skill>→<target_level>)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ai/test_level_skill_action.py
"""LevelSkill action: optimistic skill-level apply so CraftAction's gate is
satisfiable in-search. Phase 1 of the LevelSkill epic (spec 2026-07-11)."""

import dataclasses

import pytest

from artifactsmmo_cli.ai.actions.level_skill import (
    PER_LEVEL_COST,
    LevelSkill,
)
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.learning.skill_xp_curve import SkillXpCurve
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.world_state import WorldState


def _state(gd: GameData, skills: dict[str, int]) -> WorldState:
    # scenario_state builds a valid WorldState with all required fields
    # (inventory slots, projected_skill_xp_delta, etc.) — never hand-build.
    return scenario_state(ScenarioCharacter(name="t", level=5, skills=skills), gd)


def _gd_with_grind_rung() -> GameData:
    """gearcrafting: target 'widget' (level 5) + a grind rung 'trinket'
    (level 1) crafted from a located gatherable ore, so skill_grind_target
    finds a feasible rung."""
    gd = GameData()
    gd._item_stats = {
        "widget": ItemStats(code="widget", level=5, type_="resource",
                            subtype="craft", crafting_skill="gearcrafting",
                            crafting_level=5),
        "trinket": ItemStats(code="trinket", level=1, type_="resource",
                             subtype="craft", crafting_skill="gearcrafting",
                             crafting_level=1),
        "gear_ore": ItemStats(code="gear_ore", level=1, type_="resource",
                              subtype="mob"),
    }
    gd._crafting_recipes = {"widget": {"gear_ore": 2}, "trinket": {"gear_ore": 1}}
    gd._resource_drops = {"gear_rocks": "gear_ore"}
    gd._resource_skill = {"gear_rocks": ("mining", 1)}
    gd._resource_locations = {"gear_rocks": [(3, 3)]}
    return gd


def test_apply_sets_skill_to_target() -> None:
    gd = _gd_with_grind_rung()
    state = _state(gd, {"gearcrafting": 1})
    out = LevelSkill(skill="gearcrafting", target_level=5).apply(state, gd)
    assert out.skills["gearcrafting"] == 5
    # every other field preserved
    assert dataclasses.replace(out, skills=state.skills) == state


def test_applicable_when_under_skill_and_grindable() -> None:
    gd = _gd_with_grind_rung()
    action = LevelSkill(skill="gearcrafting", target_level=5)
    assert action.is_applicable(_state(gd, {"gearcrafting": 1}), gd) is True


def test_not_applicable_when_already_at_target() -> None:
    gd = _gd_with_grind_rung()
    action = LevelSkill(skill="gearcrafting", target_level=5)
    assert action.is_applicable(_state(gd, {"gearcrafting": 5}), gd) is False


def test_not_applicable_when_no_grind_rung() -> None:
    """No craftable at/below current in the skill → not grindable from here."""
    gd = GameData()
    gd._item_stats = {
        "lonely": ItemStats(code="lonely", level=10, type_="resource",
                            subtype="craft", crafting_skill="gearcrafting",
                            crafting_level=10),
    }
    gd._crafting_recipes = {"lonely": {"gear_ore": 2}}
    action = LevelSkill(skill="gearcrafting", target_level=10)
    assert action.is_applicable(_state(gd, {"gearcrafting": 5}), gd) is False


def test_cost_positive_and_monotone_in_gap() -> None:
    gd = _gd_with_grind_rung()
    c_small = LevelSkill("gearcrafting", 2).cost(_state(gd, {"gearcrafting": 1}), gd)
    c_big = LevelSkill("gearcrafting", 5).cost(_state(gd, {"gearcrafting": 1}), gd)
    assert c_small > 0
    assert c_big > c_small
    # no-curve fallback is exactly gap * PER_LEVEL_COST
    assert c_big == (5 - 1) * PER_LEVEL_COST


def test_cost_uses_curve_when_observed() -> None:
    gd = _gd_with_grind_rung()
    curve = SkillXpCurve(observed={1: 100, 2: 150, 3: 225, 4: 340})
    action = LevelSkill("gearcrafting", 5, xp_curve=curve)
    assert action.cost(_state(gd, {"gearcrafting": 1}), gd) > 0


def test_repr_uses_arrow() -> None:
    assert repr(LevelSkill("gearcrafting", 5)) == "LevelSkill(gearcrafting→5)"


def test_execute_raises_direct_call_guard() -> None:
    gd = _gd_with_grind_rung()
    with pytest.raises(RuntimeError, match="player skill-grind hook"):
        LevelSkill("gearcrafting", 5).execute(_state(gd, {"gearcrafting": 1}), None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_level_skill_action.py -q --no-cov`
Expected: FAIL — `ModuleNotFoundError: artifactsmmo_cli.ai.actions.level_skill`.

- [ ] **Step 3: Implement the action**

```python
# src/artifactsmmo_cli/ai/actions/level_skill.py
"""LevelSkill: a GOAP action that raises a crafting skill to `target_level`.

The GOAP planner treats skill levels as immutable during search, so
CraftAction's skill gate (skill_level < crafting_level -> not applicable) is
otherwise unsatisfiable in-search — an under-skill craft cannot be planned.
LevelSkill's `apply` OPTIMISTICALLY sets the skill to `target_level` (the whole
grind assumed complete, the FightAction optimistic-apply idiom), so a downstream
CraftAction(target) becomes applicable in the SIMULATED plan; the player expands
the action into an incremental grind at execution (Phase 3) and PlanCache replan
reconciles the optimism with reality.
"""

import dataclasses
from dataclasses import dataclass, field

from artifactsmmo_api_client import AuthenticatedClient

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.skill_xp_curve import SkillXpCurve
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from artifactsmmo_cli.ai.world_state import WorldState

PER_LEVEL_COST = 50.0
"""No-curve fallback cost per skill level (~10 grind crafts at 5s each). Keeps
cost strictly positive and monotone in the level gap when SkillXpCurve has no
observations yet."""

PER_CRAFT_COST = 5.0
"""Seconds per grind craft, matching CraftAction.cost's 5.0/quantity base."""

AVG_XP_PER_CRAFT = 20
"""Conservative XP granted per grind craft when converting a curve XP estimate
into a craft-cycle count. Refined by observation; never a hardcoded curve."""


@dataclass
class LevelSkill(Action):
    """Raise `skill` to `target_level`. Optimistic apply; player-expanded at execution."""

    skill: str
    target_level: int
    xp_curve: SkillXpCurve | None = field(default=None, repr=False, compare=False)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if state.skills.get(self.skill, 1) >= self.target_level:
            return False
        return skill_grind_target(self.skill, state, game_data) is not None

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        new_skills = dict(state.skills)
        new_skills[self.skill] = self.target_level
        return dataclasses.replace(state, skills=new_skills)

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        current = state.skills.get(self.skill, 1)
        gap = max(0, self.target_level - current)
        curve = self.xp_curve
        if curve is not None and curve.observed:
            total_xp = curve.total_xp_to_reach(current, self.target_level)
            cycles = max(gap, -(-total_xp // AVG_XP_PER_CRAFT))  # ceil-div
            return cycles * PER_CRAFT_COST
        return gap * PER_LEVEL_COST

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        raise RuntimeError(
            "LevelSkill is expanded by the player skill-grind hook (Phase 3); "
            "it must not be executed directly."
        )

    def __repr__(self) -> str:
        return f"LevelSkill({self.skill}→{self.target_level})"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_level_skill_action.py -q --no-cov`
Expected: PASS (8 passed).

- [ ] **Step 5: Coverage + lint the new module**

Run:
```
uv run pytest tests/test_ai/test_level_skill_action.py -q \
  --cov=artifactsmmo_cli.ai.actions.level_skill --cov-report=term-missing
uv run ruff check src/artifactsmmo_cli/ai/actions/level_skill.py
uv run mypy src/artifactsmmo_cli/ai/actions/level_skill.py
```
Expected: `level_skill.py 100%`; ruff `All checks passed!`; mypy `Success`.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/level_skill.py tests/test_ai/test_level_skill_action.py
git commit -m "feat(planner): LevelSkill action — optimistic skill-level apply (P1)"
```

---

## Task 2: Planner plans grind→craft (the Phase-1 capability proof)

**Files:**
- Test: `tests/test_ai/test_level_skill_planning.py`

**Interfaces:**
- Consumes: `GOAPPlanner().plan(state: WorldState, goal: Goal, actions: list[Action], game_data: GameData, *, budget_seconds: float|None=None) -> list[Action]` (`ai/planner.py:83`); `GatherMaterialsGoal(target_item: str, needed: dict[str,int])` (`ai/goals/gathering.py`); `build_actions(game_data, state, objective, *, bank_accessible, task_exchange_min_coins)` (`ai/actions/factory.py`); `CharacterObjective.from_game_data(game_data)` (`ai/tiers/objective.py`); `LevelSkill` (Task 1).
- Produces: proof that with `LevelSkill(gearcrafting, 5)` in the action set, `GOAPPlanner.plan` for `GatherMaterialsGoal("widget", {"widget": 1})` at gearcrafting 1 returns a plan that contains a `LevelSkill` step preceding a `CraftAction(code="widget")`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_level_skill_planning.py
"""Phase-1 headline: with LevelSkill in the action set, the GOAP planner plans
`grind-skill -> craft` for an under-skill craft target — the capability that
retires the SKILL_PREREQUISITE workaround. Drives GOAPPlanner directly (not the
arbiter), so the is_plannable under-skill fast-fail — still present in P1 — does
not intercept; P2 removes that fast-fail so the live arbiter reaches this path."""

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "widget": ItemStats(code="widget", level=5, type_="resource",
                            subtype="craft", crafting_skill="gearcrafting",
                            crafting_level=5),
        "trinket": ItemStats(code="trinket", level=1, type_="resource",
                             subtype="craft", crafting_skill="gearcrafting",
                             crafting_level=1),
        "gear_ore": ItemStats(code="gear_ore", level=1, type_="resource",
                              subtype="mob"),
    }
    gd._crafting_recipes = {"widget": {"gear_ore": 2}, "trinket": {"gear_ore": 1}}
    gd._resource_drops = {"gear_rocks": "gear_ore"}
    gd._resource_skill = {"gear_rocks": ("mining", 1)}
    gd._resource_locations = {"gear_rocks": [(3, 3)]}
    gd._workshop_locations = {"gearcrafting": (2, 2)}
    return gd


def test_planner_sequences_level_skill_before_gated_craft() -> None:
    gd = _gd()
    state = scenario_state(
        ScenarioCharacter(name="t", level=5,
                          skills={"gearcrafting": 1, "mining": 1}), gd)
    objective = CharacterObjective.from_game_data(gd)
    actions = build_actions(gd, state, objective, bank_accessible=True,
                            task_exchange_min_coins=0)
    actions.append(LevelSkill(skill="gearcrafting", target_level=5))
    goal = GatherMaterialsGoal(target_item="widget", needed={"widget": 1})

    plan = GOAPPlanner().plan(state, goal, actions, gd, budget_seconds=10.0)

    reprs = [repr(a) for a in plan]
    craft_idx = next(i for i, a in enumerate(plan)
                     if isinstance(a, CraftAction) and a.code == "widget")
    level_idx = next(i for i, a in enumerate(plan)
                     if isinstance(a, LevelSkill))
    assert level_idx < craft_idx, f"LevelSkill must precede Craft(widget): {reprs}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_level_skill_planning.py -q --no-cov`
Expected: FAIL — before the action is in the set the planner cannot cross the skill gate (empty plan / no `LevelSkill`); with the action appended the assertion pins the new capability. If it fails on plan construction details (workshop/resource wiring), fix the fixture until the planner returns the `[…, LevelSkill, …, Craft(widget)]` shape — do NOT weaken the assertion.

- [ ] **Step 3: (no new production code)**

Task 1 already provides `LevelSkill`. This task is a pure integration proof; it passes once the fixture drives the planner correctly. If `build_actions` needs the workshop/resource wiring above to emit `CraftAction(widget)`/`GatherAction(gear_ore)`, that wiring is in the fixture, not production.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_level_skill_planning.py -q --no-cov`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ai/test_level_skill_planning.py
git commit -m "test(planner): planner sequences LevelSkill before a gated craft (P1)"
```

---

## Task 3: Lean apply/applicability mirror + differential gate

**Files:**
- Modify: the action decision mirror under `formal/Formal/` (locate with `grep -rl "fightApplicable\|applyStep\|ActionApplicability" formal/Formal/`). Add `levelSkillApplicable` and the `LevelSkill` arm of `applyStep` (sets `skills[skill] := target`).
- Modify: `formal/Oracle.lean` — add `runLevelSkillApply` + `runLevelSkillApplicable` and register keys `"level_skill_apply"`, `"level_skill_applicable"`.
- Create: `formal/diff/test_level_skill_diff.py` — differential test asserting the Lean apply/applicability agree with the Python `LevelSkill.apply`/`is_applicable` on generated cases (pattern: existing `formal/diff/test_skill_step_dispatch_diff.py`).
- Modify: `formal/diff/mutate.py` — add a mutation anchor for the new Lean apply/applicability, bound to `test_level_skill_diff.py`.
- Modify: `formal/Manifest.lean` — role-check anchor for the new definitions (pattern: `Manifest.lean:115-134`).

**Interfaces:**
- Consumes: the Python `LevelSkill.apply` (`skills[skill] := target_level`) and `is_applicable` (`under-target AND skill_grind_target is not None`) from Task 1.
- Produces: Lean `levelSkillApplicable (skill target : ...) (s : State) : Bool` and an `applyStep` arm; Oracle keys `level_skill_apply` / `level_skill_applicable`; a green `formal/diff/test_level_skill_diff.py`.

- [ ] **Step 1: Write the failing differential test**

Model on `formal/diff/test_skill_step_dispatch_diff.py`. Generate cases `(skill, target_level, current_level, has_grind_rung)`; for each, compute the Python result (`LevelSkill(skill, target).apply(state, gd).skills[skill]` and `.is_applicable(state, gd)`) and the Lean result via the Oracle keys `level_skill_apply` / `level_skill_applicable`; assert equal. Use the same lockstep harness the sibling diff tests use (`formal/diff/` runner).

Run: `uv run python -m pytest formal/diff/test_level_skill_diff.py -q`
Expected: FAIL — Oracle keys `level_skill_apply` / `level_skill_applicable` not registered.

- [ ] **Step 2: Add the Lean apply/applicability + Oracle keys**

In the action mirror file: define `levelSkillApplicable` (returns `decide (current < target) && hasGrindRung`) and the `LevelSkill` arm of `applyStep` that returns the state with `skills` updated at `skill` to `target`. In `formal/Oracle.lean`: add `runLevelSkillApply`/`runLevelSkillApplicable` and register the two keys (pattern: `runSkillStepDispatch` at `Oracle.lean:2237-2254`, keys at `2981-2982`). Keep the Lean model of "has grind rung" abstract/opaque exactly as the differential scenarios pin it (the diff scenarios set the grind-rung feasibility explicitly), matching how `fightApplicable` omits the equip slot-room gate — document the abstraction in a Lean comment.

Use the lean proof-repair / sorry-filler agents for any proof obligations. Build:
```
cd formal && lake build
```
Expected: build succeeds, no `sorry`, no new axioms (axiom lint clean).

- [ ] **Step 3: Run the differential test to verify it passes**

Run: `uv run python -m pytest formal/diff/test_level_skill_diff.py -q`
Expected: PASS.

- [ ] **Step 4: Add the mutation anchor and run the full gate**

Add a `formal/diff/mutate.py` anchor for the new Lean apply/applicability, bound to `test_level_skill_diff.py`, plus the `Manifest.lean` role anchor. Then run the full gate (serialized — nothing else importing `src`):
```
./gate.sh
```
Expected: ALL PARTS PASSED (lake build, axiom lint, `formal/diff` incl. the new test, mutation incl. the new anchor killed).

- [ ] **Step 5: Commit**

```bash
git add formal/
git commit -m "feat(formal): LevelSkill apply/applicability Lean mirror + differential gate (P1)"
```

---

## Phase 1 sign-off

- [ ] Full suite green, 100% coverage: `uv run pytest -q` → `passed`, `Required test coverage of 100% reached`.
- [ ] `./gate.sh` ALL PARTS PASSED (serialized).
- [ ] The action is **inert**: `grep -rn "LevelSkill(" src/artifactsmmo_cli/ai/actions/factory.py` returns nothing (not yet emitted by `build_actions`).

---

## Roadmap — Phases 2–4 (planned after each predecessor lands)

Each phase gets its own bite-sized plan authored once its predecessor's exact
interfaces exist (the emergent action set shape, the execution-hook signature).
Summary of scope from the spec:

- **P2 — Wire + retire fast-fail.** Emit one `LevelSkill(skill, L)` per distinct in-skill craft level from `build_actions` (`ai/actions/factory.py`); teach `craft_plan_gen.generate_next_craft_action` to emit a `LevelSkill` leg before a gated craft (replace the skill-gate `None`-return at `craft_plan_gen.py:135-136`). Retire the crafting-skill-gate arm of `GatherMaterialsGoal.is_plannable` (`goals/gathering.py:519-543`; keep the currency-affordability arm) and retire `formal/Formal/SkillGateFastFail.lean` + its Manifest/audit anchors. Gate: full `gate.sh` + suite + runtime `plan <char>` shows `LevelSkill → Craft` for an under-skill target. **Exit:** census under-skill cells flip PASS.

- **P3 — Retire tree routing + gather-skill arm + execution hook.** Add the player skill-grind expansion hook (on `plan[0]` a `LevelSkill`, pick the grind via the relocated `skill_step_dispatch`/`skill_grind_selection` cores, plan `GatherMaterials(rung, skill_grind=True)`, execute leg 0, replan). Add the gather-skill arm to `LevelSkill.is_applicable`/execution (`best_gather_resource_drop`). Retire `ReachSkillLevel` (`tiers/meta_goal.py:43-49`, the `strategy_driver.py:782-886` dispatch branch + hoisters `_skill_dispatch_candidates`/`_gated_behind_skill`, and `prerequisite_graph.py:60-71` emission) and `LevelSkillGoal` (`goals/level_skill.py` + `strategy_driver.py:440-442` + `goal_serialization.py:48-52`). Migrate `MetaGoalDispatch.lean` + `Liveness/SkillGapClosure.lean` liveness to the action; re-anchor the surviving `SkillStepDispatch`/`GrindLadder`/`SkillGrindSelection` proofs + their six Oracle keys. Gate: full `gate.sh` + suite + runtime gear-unlock grind still fires.

- **P4 — Census cleanup (acceptance).** Delete the `SKILL_PREREQUISITE` gap class + its tests from `audit/craft_completeness.py`/`test_craft_completeness.py` (keep located-source / grey-farm / purchase-recursion); the held working-tree census changes from the prior session ship here. Regen `docs/craft_completeness/*`; `uv run python scripts/gen_craft_completeness.py --check` → **planner_bug 0**. Runtime-verify an under-skill gear target sequences `LevelSkill → Craft` on live `plan`. Gate: audit suite 100% + census `--check` + full suite. **Acceptance met:** crafting census zero-defect with the workaround removed.

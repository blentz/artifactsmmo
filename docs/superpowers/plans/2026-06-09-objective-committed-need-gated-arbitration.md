# Objective-Committed, Need-Gated Arbitration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop an always-plannable items-task from hijacking the strategically-correct objective, so a level-4 bot that needs a weapon grinds weaponcrafting (and eventually fights) instead of farming fish forever.

**Architecture:** Commit to the long-term objective (`chosen_root`, which already has hysteresis). Derive its unmet needs (`objective_needs`). **Worth-suppress** any discretionary task means that serves none of those needs — which both breaks the sticky short-circuit and lets the already-earlier objective step win. Make the gating-skill step plannable via the retained craft-one. Add a combat-readiness urgency so the weapon becomes the binding objective when the bot can't fight. Remove the post-hoc `reorder_skill_candidates`. A last-resort ungated pass preserves liveness.

**Tech Stack:** Python 3.13, `uv`, pytest, mypy, ruff. Pure functions over `WorldState`/`GameData`.

**Spec:** `docs/superpowers/specs/2026-06-09-objective-committed-need-gated-arbitration-design.md`

**Project rules (AGENTS.md):** Prefix all Python with `uv run`. Imports at top of file. One behavioral class per file (cohesive enum/dataclass groups may share a module). No `if TYPE_CHECKING`. Never catch `Exception`. Use only game data or fail with an error. 0 errors / 0 warnings / 0 skipped / 100% coverage; all tests in `tests/`.

**Branch:** `feat/objective-committed-arbitration` (already checked out).

---

## File Structure

New:
- `src/artifactsmmo_cli/ai/tiers/objective_needs.py` — `NeedSet` (frozen value object), `objective_needs()`.
- `src/artifactsmmo_cli/ai/tiers/means_worth.py` — `means_serves()`.

Modified:
- `src/artifactsmmo_cli/ai/strategy_driver.py` — craft-one in `objective_step_goal` (ReachSkillLevel branch); arbiter `select` gains worth-suppression + last-resort; remove the reorder block; remove the `task_code is None → step_goal = None` line.
- `src/artifactsmmo_cli/ai/tiers/strategy.py` — combat-readiness urgency multiplier in `_marginal`.
- `src/artifactsmmo_cli/ai/player.py` — pass `combat_monster` into `objective_needs` indirectly via the arbiter (already passes `objective`; no new wiring beyond Task 5).

Removed:
- `src/artifactsmmo_cli/ai/strategy_reorder.py` + `tests/test_ai/test_strategy_reorder.py`.

Retained: `tiers/skill_gates.py`, `tiers/skill_grind_target.py` (+ their tests).

---

## Task 0: Profile the planner (evidence for perf scope)

**Files:** none (investigation; produces a note, no code change).

- [ ] **Step 1: Capture a planner profile on a representative goal**

Run a one-off profile of a single `plan()` call against the learning store on the
deepest goal in the captured trace. Use the existing test harness style — write a
throwaway script under `/tmp` (NOT in the repo):

```bash
cd /home/blentz/git/artifactsmmo
uv run python -c "
import cProfile, pstats, io
from artifactsmmo_cli.ai.planner import GOAPPlanner
# Build a deep-recipe goal + state from an existing fixture or a saved DB if available.
# If no live LearningStore DB is present, profile with history=None to isolate compute.
# (This step only needs to identify WHERE time goes: state-copy/apply vs is_applicable vs cost aggregates.)
print('Profile harness placeholder — run against the largest goal you can construct from tests/test_ai/fixtures or a real .learning.db if present.')
"
```

The concrete action: profile `GOAPPlanner().plan(goal, state, game_data, actions, history=...)` for a goal that explores ≥1000 nodes (e.g. a gear `UpgradeEquipmentGoal` from a low-skill state), with `cProfile`, and sort by cumulative time.

- [ ] **Step 2: Record the dominant cost in the spec's Component 7**

Append a short "Profile result" note to the spec file
(`docs/superpowers/specs/2026-06-09-objective-committed-need-gated-arbitration-design.md`,
end of Component 7): the top 3 cumulative-time functions and the conclusion —
which of {Cycle-table aggregates, `WorldState.apply` copy, `is_applicable`
branching} dominates. This decides whether Task 7 is needed and what it targets.

- [ ] **Step 3: Commit the note**

```bash
git add docs/superpowers/specs/2026-06-09-objective-committed-need-gated-arbitration-design.md
git commit -m "docs(spec): record planner profile result (Component 7)"
```

> If profiling cannot run offline (no learning DB, no constructable deep goal), record that and proceed — Task 7 then becomes a live-trace follow-up, and Tasks 1-6/8 (the behavior fix) stand alone.

---

## Task 1: `objective_needs.py`

**Files:**
- Create: `src/artifactsmmo_cli/ai/tiers/objective_needs.py`
- Test: `tests/test_ai/test_objective_needs.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_objective_needs.py`:

```python
"""Tests for objective_needs: the committed objective's unmet NeedSet."""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective_needs import NeedSet, objective_needs
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon",
                                crafting_skill="weaponcrafting", crafting_level=10),
        "iron_bar": ItemStats(code="iron_bar", level=10, type_="resource",
                              crafting_skill="mining", crafting_level=10),
        "iron_ore": ItemStats(code="iron_ore", level=10, type_="resource"),
        "magic_orb": ItemStats(code="magic_orb", level=5, type_="resource"),  # buy-only
    }
    gd._crafting_recipes = {
        "iron_sword": {"iron_bar": 6, "magic_orb": 1},
        "iron_bar": {"iron_ore": 1},
    }
    gd._resource_drops = {"iron_rocks": "iron_ore"}
    gd._resource_skill = {"iron_rocks": ("mining", 10)}
    # magic_orb: no recipe, no resource drop, no monster drop → buy-only.
    return gd


def test_obtain_item_collects_unowned_closure_materials():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 1, "mining": 1})
    needs = objective_needs(ObtainItem("iron_sword"), state, gd)
    # closure craftables/leaves not owned: iron_bar, iron_ore (magic_orb is buy_only).
    assert "iron_bar" in needs.materials
    assert "iron_ore" in needs.materials
    assert needs.materials and "magic_orb" not in needs.materials


def test_obtain_item_gating_skill_in_skill_xp():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 1, "mining": 1})
    needs = objective_needs(ObtainItem("iron_sword"), state, gd)
    assert "weaponcrafting" in needs.skill_xp


def test_buy_only_input_recorded():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 1, "mining": 1})
    needs = objective_needs(ObtainItem("iron_sword"), state, gd)
    assert "magic_orb" in needs.buy_only


def test_owned_material_not_a_need():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 10, "mining": 10},
                       inventory={"iron_bar": 6, "iron_ore": 6})
    needs = objective_needs(ObtainItem("iron_sword"), state, gd)
    assert "iron_bar" not in needs.materials
    assert "weaponcrafting" not in needs.skill_xp  # already at level


def test_reach_skill_level_objective_needs_that_skill():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 1})
    needs = objective_needs(ReachSkillLevel("weaponcrafting", 5), state, gd)
    assert needs.skill_xp == frozenset({"weaponcrafting"})


def test_reach_char_level_sets_char_xp():
    gd = _gd()
    state = make_state(level=4)
    needs = objective_needs(ReachCharLevel(6), state, gd)
    assert needs.char_xp is True


def test_empty_when_obtain_item_owned():
    gd = _gd()
    state = make_state(inventory={"iron_sword": 1})
    needs = objective_needs(ObtainItem("iron_sword"), state, gd)
    assert needs.is_empty
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ai/test_objective_needs.py -q`
Expected: FAIL — `ModuleNotFoundError: ...objective_needs`

- [ ] **Step 3: Implement**

Create `src/artifactsmmo_cli/ai/tiers/objective_needs.py`:

```python
"""The committed objective's unmet NEEDS — a cheap, state-only statement of what
would actually move the objective forward. Drives the arbiter's worth gate
(means that serve no need are distractions). No planning.

See docs/superpowers/specs/2026-06-09-objective-committed-need-gated-arbitration-design.md
(Component 2).
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import recipe_closure
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass(frozen=True)
class NeedSet:
    """Unmet needs of the committed objective."""
    materials: frozenset[str]   # closure items lacked (gatherable/craftable)
    skill_xp: frozenset[str]    # craft skills whose level gates the objective
    buy_only: frozenset[str]    # closure items obtainable ONLY by purchase
    char_xp: bool               # objective is / descends to a char-level gate

    @property
    def is_empty(self) -> bool:
        return not (self.materials or self.skill_xp or self.buy_only or self.char_xp)


def _owned(code: str, state: WorldState) -> int:
    bank = state.bank_items or {}
    equipped = sum(1 for c in state.equipment.values() if c == code)
    return state.inventory.get(code, 0) + bank.get(code, 0) + equipped


def _producible_by_self(code: str, game_data: GameData) -> bool:
    """Craftable (has a recipe) or gatherable (a resource drops it)."""
    return (game_data.crafting_recipe(code) is not None
            or code in game_data._resource_drops.values())


def objective_needs(root: MetaGoal, state: WorldState, game_data: GameData) -> NeedSet:
    """Unmet needs of `root`. Empty NeedSet when the objective is already met."""
    if isinstance(root, ReachSkillLevel):
        current = state.skills.get(root.skill, 0)
        skill = frozenset({root.skill}) if current < root.level else frozenset()
        return NeedSet(frozenset(), skill, frozenset(), char_xp=False)
    if isinstance(root, ReachCharLevel):
        return NeedSet(frozenset(), frozenset(), frozenset(),
                       char_xp=state.level < root.level)
    if isinstance(root, ObtainItem):
        if _owned(root.code, state) >= root.quantity:
            return NeedSet(frozenset(), frozenset(), frozenset(), char_xp=False)
        resources, craftables = recipe_closure(game_data, [root.code])
        nodes = set(craftables) | {root.code}
        materials: set[str] = set()
        skill_xp: set[str] = set()
        buy_only: set[str] = set()
        # Resource leaves (gatherable) that aren't owned are materials.
        for res in resources:
            drop = game_data.resource_drop_item(res)
            if drop is not None and _owned(drop, state) < 1:
                materials.add(drop)
        for node in nodes:
            if node == root.code:
                continue
            if _owned(node, state) >= 1:
                continue
            if _producible_by_self(node, game_data):
                materials.add(node)
            else:
                buy_only.add(node)
            stats = game_data.item_stats(node)
            if stats is not None and stats.crafting_skill:
                if stats.crafting_level > state.skills.get(stats.crafting_skill, 0):
                    skill_xp.add(stats.crafting_skill)
        # The root item's own craft gate.
        root_stats = game_data.item_stats(root.code)
        if root_stats is not None and root_stats.crafting_skill:
            if root_stats.crafting_level > state.skills.get(root_stats.crafting_skill, 0):
                skill_xp.add(root_stats.crafting_skill)
        return NeedSet(frozenset(materials), frozenset(skill_xp),
                       frozenset(buy_only), char_xp=False)
    return NeedSet(frozenset(), frozenset(), frozenset(), char_xp=False)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_ai/test_objective_needs.py -q`
Expected: PASS (7 passed)

- [ ] **Step 5: Type-check + lint**

Run: `uv run mypy src/artifactsmmo_cli/ai/tiers/objective_needs.py && uv run ruff check src/artifactsmmo_cli/ai/tiers/objective_needs.py tests/test_ai/test_objective_needs.py`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/objective_needs.py tests/test_ai/test_objective_needs.py
git commit -m "feat(planner): objective_needs NeedSet derivation"
```

---

## Task 2: `means_worth.py`

**Files:**
- Create: `src/artifactsmmo_cli/ai/tiers/means_worth.py`
- Test: `tests/test_ai/test_means_worth.py`

Scope (YAGNI): gate only `PURSUE_TASK` and `ACCEPT_TASK` — the actual hijackers in
the trace. All other means pass through (`True`). This fixes the bug without
over-modeling infrastructure means; extend later if a trace shows another hijacker.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_means_worth.py`:

```python
"""Tests for means_serves: does a discretionary means serve the objective's needs?"""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.means import MeansKind
from artifactsmmo_cli.ai.tiers.means_worth import means_serves
from artifactsmmo_cli.ai.tiers.objective_needs import NeedSet
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "cooked_gudgeon": ItemStats(code="cooked_gudgeon", level=1, type_="consumable",
                                    crafting_skill="cooking", crafting_level=1),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon",
                                crafting_skill="weaponcrafting", crafting_level=10),
    }
    gd._crafting_recipes = {"cooked_gudgeon": {"gudgeon": 1}, "iron_sword": {"iron_bar": 6}}
    return gd


def _weapon_needs() -> NeedSet:
    return NeedSet(materials=frozenset({"iron_bar"}),
                   skill_xp=frozenset({"weaponcrafting"}),
                   buy_only=frozenset(), char_xp=False)


def test_cooking_task_does_not_serve_weapon_objective():
    gd = _gd()
    state = make_state(task_type="items", task_code="cooked_gudgeon")
    assert means_serves(MeansKind.PURSUE_TASK, None, _weapon_needs(), state, gd) is False


def test_task_serves_when_its_skill_is_a_need():
    gd = _gd()
    state = make_state(task_type="items", task_code="cooked_gudgeon")
    needs = NeedSet(frozenset(), frozenset({"cooking"}), frozenset(), char_xp=False)
    assert means_serves(MeansKind.PURSUE_TASK, None, needs, state, gd) is True


def test_task_serves_when_it_produces_a_needed_material():
    gd = _gd()
    state = make_state(task_type="items", task_code="iron_bar")
    needs = NeedSet(frozenset({"iron_bar"}), frozenset(), frozenset(), char_xp=False)
    assert means_serves(MeansKind.PURSUE_TASK, None, needs, state, gd) is True


def test_task_serves_when_buy_only_need_and_task_yields_gold():
    gd = _gd()
    state = make_state(task_type="items", task_code="cooked_gudgeon")
    needs = NeedSet(frozenset(), frozenset(), frozenset({"magic_orb"}), char_xp=False)
    assert means_serves(MeansKind.PURSUE_TASK, None, needs, state, gd) is True


def test_empty_needs_passes_through():
    gd = _gd()
    state = make_state(task_type="items", task_code="cooked_gudgeon")
    empty = NeedSet(frozenset(), frozenset(), frozenset(), char_xp=False)
    assert means_serves(MeansKind.PURSUE_TASK, None, empty, state, gd) is True


def test_char_xp_only_need_rejects_items_task():
    gd = _gd()
    state = make_state(task_type="items", task_code="cooked_gudgeon")
    needs = NeedSet(frozenset(), frozenset(), frozenset(), char_xp=True)
    # items-tasks award no char XP → not worth pursuing for a char-level objective.
    assert means_serves(MeansKind.PURSUE_TASK, None, needs, state, gd) is False


def test_non_task_means_pass_through():
    gd = _gd()
    state = make_state(task_type="items", task_code="cooked_gudgeon")
    assert means_serves(MeansKind.SELL_IDLE, None, _weapon_needs(), state, gd) is True
    assert means_serves(MeansKind.BANK_EXPAND, None, _weapon_needs(), state, gd) is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ai/test_means_worth.py -q`
Expected: FAIL — `ModuleNotFoundError: ...means_worth`

- [ ] **Step 3: Implement**

Create `src/artifactsmmo_cli/ai/tiers/means_worth.py`:

```python
"""The worth gate: does a discretionary means serve the committed objective's
needs? A means that serves no unmet need is a distraction and is suppressed.

Scope: gates PURSUE_TASK / ACCEPT_TASK (the items-task hijackers). All other
means pass through True. See spec Component 3.

Task-output model: an items-task produces (a) the craft/gather skill XP of its
task item, (b) tasks_coin + gold on completion, (c) the task item itself. It
awards NO character XP (verified: all char-XP gain events attribute to Fight).
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.tiers.means import MeansKind
from artifactsmmo_cli.ai.tiers.objective_needs import NeedSet
from artifactsmmo_cli.ai.world_state import WorldState

_TASK_KINDS = frozenset({MeansKind.PURSUE_TASK, MeansKind.ACCEPT_TASK})


def _task_skill(task_code: str | None, game_data: GameData) -> str | None:
    """The craft skill the task exercises (its item's crafting_skill), or the
    first gather skill in its production chain."""
    if not task_code:
        return None
    stats = game_data.item_stats(task_code)
    if stats is not None and stats.crafting_skill:
        return stats.crafting_skill
    gather = game_data.active_gathering_skills(task_code)
    return next(iter(sorted(gather)), None)


def means_serves(kind: MeansKind, goal: Goal | None, needs: NeedSet,
                 state: WorldState, game_data: GameData) -> bool:
    """True if this means is worth pursuing toward the committed objective."""
    if kind not in _TASK_KINDS:
        return True
    if needs.is_empty:
        return True
    skill = _task_skill(state.task_code, game_data)
    if skill is not None and skill in needs.skill_xp:
        return True
    if state.task_code is not None and state.task_code in needs.materials:
        return True
    # Items-tasks yield gold + tasks_coin → serve a buy-only (needs gold) gap.
    if needs.buy_only:
        return True
    # char_xp need: items-tasks award no character XP → never serves it.
    return False
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_ai/test_means_worth.py -q`
Expected: PASS (7 passed)

- [ ] **Step 5: Type-check + lint**

Run: `uv run mypy src/artifactsmmo_cli/ai/tiers/means_worth.py && uv run ruff check src/artifactsmmo_cli/ai/tiers/means_worth.py tests/test_ai/test_means_worth.py`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/means_worth.py tests/test_ai/test_means_worth.py
git commit -m "feat(planner): means_serves worth gate for task means"
```

---

## Task 3: Craft-one into `objective_step_goal` (plannable gating-skill step)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py` (the `ReachSkillLevel` branch of `objective_step_goal`, ~line 347-352)
- Test: `tests/test_ai/test_strategy_driver.py` (add a test)

Currently the `ReachSkillLevel` branch returns the width-unfindable
`LevelSkillGoal(current+LEVEL_LOOKAHEAD)`. Change it: when the skill is a binding
gate AND a craft-one target exists, return the shallow plannable
`GatherMaterialsGoal(craft_one, {craft_one: 1})`; otherwise keep `LevelSkillGoal`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ai/test_strategy_driver.py` (reuse existing imports; add these):

```python
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal as _GMGoal
from artifactsmmo_cli.ai.tiers.meta_goal import ReachSkillLevel as _RSL


def test_objective_step_reachskill_returns_craft_one_when_craftable():
    from artifactsmmo_cli.ai import strategy_driver as sd
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {"copper_dagger": {"copper_bar": 6}}
    state = make_state(skills={"weaponcrafting": 1})
    ctx = _make_ctx()  # existing helper in this test file
    goal = sd.objective_step_goal(_RSL("weaponcrafting", 5), state, gd, ctx)
    assert isinstance(goal, _GMGoal)
    assert repr(goal) == "GatherMaterials(copper_dagger)"
```

> If the test file's context helper is not named `_make_ctx`, use the file's actual `SelectionContext` constructor.

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py::test_objective_step_reachskill_returns_craft_one_when_craftable -q`
Expected: FAIL — returns a `LevelSkillGoal`, not `GatherMaterialsGoal`.

- [ ] **Step 3: Implement**

In `src/artifactsmmo_cli/ai/strategy_driver.py`, add this import near the other tier imports:

```python
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
```

Replace the `ReachSkillLevel` branch (currently):

```python
    if isinstance(step, ReachSkillLevel):
        current = state.skills.get(step.skill, 0)
        target = min(step.level, current + LEVEL_LOOKAHEAD)
        return LevelSkillGoal(skill_name=step.skill, target_level=target,
                              initial_skill_xp=state.skill_xp.get(step.skill, 0),
                              xp_curve=ctx.skill_xp_curves.get(step.skill))
```

with:

```python
    if isinstance(step, ReachSkillLevel):
        # Plannable craft-one: a "reach skill level N" step is width-unfindable as
        # a single GOAP goal (the planner can't simulate grinding many crafts).
        # Route it to crafting ONE shallow in-skill item per cycle; the per-cycle
        # replan grinds the skill incrementally and the step is always plannable.
        # Falls back to LevelSkillGoal only when nothing in-skill is craftable now.
        craft_one = skill_grind_target(step.skill, state, game_data)
        if craft_one is not None:
            return GatherMaterialsGoal(target_item=craft_one, needed={craft_one: 1})
        current = state.skills.get(step.skill, 0)
        target = min(step.level, current + LEVEL_LOOKAHEAD)
        return LevelSkillGoal(skill_name=step.skill, target_level=target,
                              initial_skill_xp=state.skill_xp.get(step.skill, 0),
                              xp_curve=ctx.skill_xp_curves.get(step.skill))
```

- [ ] **Step 4: Run to verify it passes + no regressions**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py -q`
Expected: PASS (new test + existing).

- [ ] **Step 5: Type-check + lint**

Run: `uv run mypy src/artifactsmmo_cli/ai/strategy_driver.py && uv run ruff check src/artifactsmmo_cli/ai/strategy_driver.py`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/strategy_driver.py tests/test_ai/test_strategy_driver.py
git commit -m "feat(planner): route ReachSkillLevel step to plannable craft-one"
```

---

## Task 4: Combat-readiness urgency multiplier

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py` (`StrategyEngine._marginal`, ObtainItem branch)
- Test: `tests/test_ai/test_tiers_strategy.py`

When `combat_monster is None` (not combat-capable), the combat-enabling weapon root
must out-rank competing roots so it becomes `chosen_root`. Add an urgency multiplier
to the weapon `ObtainItem`'s marginal while combat is blocked. `decide()` already
receives `combat_monster`; thread it into `_marginal`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ai/test_tiers_strategy.py` (reuse existing fixtures/imports):

```python
def test_weapon_root_urgent_when_not_combat_capable():
    """A combat weapon ObtainItem out-ranks a gather-tool ObtainItem when the
    character cannot fight (combat_monster is None)."""
    # Build an objective with a weapon (combat slot) and a tool (utility slot).
    # Use the test file's existing objective/GameData builders.
    gd = _strategy_gd()                      # existing helper
    obj = _objective_with(gd, weapon="iron_sword", tool="iron_pickaxe")  # existing/adapt
    engine = StrategyEngine(obj, BalancedPersonality())
    state = make_state(level=4, skills={"weaponcrafting": 1})
    # not combat-capable:
    d = engine.decide(state, gd, history=None, combat_monster=None)
    assert "iron_sword" in repr(d.chosen_root)
    # combat-capable: urgency off, weapon no longer forced to the top.
    d2 = engine.decide(state, gd, history=None, combat_monster="chicken")
    # (weapon may or may not win, but the urgency boost is gone)
    assert d2.chosen_root is not None
```

> Adapt `_strategy_gd` / `_objective_with` to the test file's real helpers. The
> load-bearing assertion is the first: weapon is `chosen_root` when `combat_monster
> is None`. If the file lacks an objective builder, construct `CharacterObjective`
> directly with `target_gear={"weapon_slot": "iron_sword"}` and
> `target_tools={"mining": "iron_pickaxe"}`.

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py::test_weapon_root_urgent_when_not_combat_capable -q`
Expected: FAIL — weapon does not reliably win when `combat_monster is None`.

- [ ] **Step 3: Implement**

In `src/artifactsmmo_cli/ai/tiers/strategy.py`:

Add a module constant near the other tuning constants (after `PRIOR_RELEVANT_TOOL`):

```python
COMBAT_READINESS_URGENCY = 2.0
"""Multiplier applied to the combat-enabling weapon root's marginal while the
character is not combat-capable (combat_monster is None). Sized to lift the weapon
root above competing gear/tool/skill roots so it becomes chosen_root — the binding
objective that unblocks combat. Switches off once a weapon makes the bot
combat-capable (no permanent override of the long-term objective)."""
```

Thread `combat_monster` into `_value`/`_marginal`. Change `_value`:

```python
    def _value(self, root: MetaGoal, state: WorldState, game_data: GameData,
               combat_monster: str | None = None) -> float:
        base = (self._base_prior(root)
                * self._marginal(root, state, game_data, combat_monster)
                * self._balancing(root, state))
        return max(base, self._relevant_tool_value(root, state, game_data))
```

Change `_marginal` signature + the `ObtainItem` branch to apply the urgency to a
weapon root when not combat-capable:

```python
    def _marginal(self, root: MetaGoal, state: WorldState, game_data: GameData,
                  combat_monster: str | None = None) -> float:
        if isinstance(root, ReachCharLevel):
            gap = max(0, root.level - state.level)
            reach = max(0, CHAR_REACHABLE_HORIZON - gap)
            bonus = reach * CHAR_GAP_PER_LEVEL
            return CHAR_MARGINAL + bonus
        if isinstance(root, ReachSkillLevel):
            return SKILL_MARGINAL
        if isinstance(root, ObtainItem):
            stats = game_data.item_stats(root.code)
            if stats is None:
                return 0.0
            slot = next((s for s, c in self.objective.target_gear.items() if c == root.code), None)
            current_code = state.equipment.get(slot) if slot is not None else None
            current_stats = game_data.item_stats(current_code) if current_code else None
            current_value = equip_value(current_stats) if current_stats is not None else 0.0
            gain = max(0.0, equip_value(stats) - current_value)
            marginal = min(1.0, gain / GEAR_EQUIP_SCALE)
            # Combat-readiness urgency: a weapon-slot upgrade is the binding
            # objective while the character cannot fight at all.
            if combat_monster is None and slot == "weapon_slot":
                marginal = max(marginal, 1.0) * COMBAT_READINESS_URGENCY
            return marginal
        return 0.0
```

Update the `decide()` call site (line ~394) from `self._value(root, state, game_data)` to:

```python
            value = self._value(root, state, game_data, combat_monster)
```

- [ ] **Step 4: Run to verify it passes + no regressions**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -q`
Expected: PASS (new + existing).

- [ ] **Step 5: Type-check + lint**

Run: `uv run mypy src/artifactsmmo_cli/ai/tiers/strategy.py && uv run ruff check src/artifactsmmo_cli/ai/tiers/strategy.py`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/strategy.py tests/test_ai/test_tiers_strategy.py
git commit -m "feat(planner): combat-readiness urgency lifts weapon to chosen_root"
```

---

## Task 5: Arbiter worth-suppression + last-resort (the core fix)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py` (`select`)
- Test: `tests/test_ai/test_strategy_driver.py`

Three edits, all inside `select`:
(a) remove the `task_code is None → step_goal = None` AcceptTask-priority line;
(b) remove the shipped skill-gate reorder block;
(c) add worth-suppression of non-serving task means + a last-resort ungated pass.

- [ ] **Step 1: Write the failing integration test**

Add to `tests/test_ai/test_strategy_driver.py`:

```python
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal


def test_worth_gate_picks_weapon_grind_over_nonserving_task(monkeypatch):
    """Stuck-state regression: level-4 bot, weaponcrafting-gated weapon objective,
    an items-task active that serves no weapon need → arbiter selects the
    weaponcrafting craft-one, NOT PursueTask."""
    from artifactsmmo_cli.ai import strategy_driver as sd
    arbiter = StrategyArbiter(GOAPPlanner(), history=None)

    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon",
                                crafting_skill="weaponcrafting", crafting_level=10),
        "cooked_gudgeon": ItemStats(code="cooked_gudgeon", level=1, type_="consumable",
                                    crafting_skill="cooking", crafting_level=1),
    }
    gd._crafting_recipes = {"copper_dagger": {}, "iron_sword": {"copper_dagger": 6},
                            "cooked_gudgeon": {}}
    obj = CharacterObjective(
        target_char_level=50, target_skill_levels={},
        target_gear={"weapon_slot": "iron_sword"}, _game_data=gd, target_tools={})
    state = make_state(skills={"weaponcrafting": 1, "cooking": 1},
                       task_type="items", task_code="cooked_gudgeon",
                       task_total=10, task_progress=0)

    # Decision surfaces the weaponcrafting gate as the chosen step, PursueTask as a
    # discretionary means. Stub the tier layer to that shape.
    monkeypatch.setattr(sd, "active_guards", lambda *a, **k: [])
    monkeypatch.setattr(sd, "active_means", lambda *a, **k: ([], [sd.MeansKind.PURSUE_TASK]))
    monkeypatch.setattr(
        sd, "objective_step_goal",
        lambda step, st, g, c, root=None: GatherMaterialsGoal("copper_dagger", {"copper_dagger": 1}))

    decision = type("D", (), {"chosen_step": _RSL("weaponcrafting", 5),
                              "chosen_root": ObtainItem("iron_sword"),
                              "fallback_steps": [], "fallback_roots": []})()
    ctx = _make_ctx(combat_monster=None)

    goal, plan, tried = arbiter.select(decision, state, gd, _stub_actions(gd), ctx,
                                       objective=obj)
    assert isinstance(goal, GatherMaterialsGoal)  # weapon grind, not PursueTask
```

> `_stub_actions(gd)` / `_make_ctx` / `ObtainItem` / `_RSL`: reuse the test file's
> existing helpers and imports (add `from artifactsmmo_cli.ai.tiers.meta_goal import
> ObtainItem` if absent). The PursueTask goal must be plannable in this fixture so
> the test proves it was SUPPRESSED, not merely unplannable — ensure `map_means`
> yields a PursueTaskGoal whose plan is non-empty for `cooked_gudgeon`, or stub
> `map_means` to return a trivially-plannable stub goal repr'd `PursueTask(...)`.

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py::test_worth_gate_picks_weapon_grind_over_nonserving_task -q`
Expected: FAIL — current arbiter selects PursueTask (sticky/plannable wins).

- [ ] **Step 3a: Remove the AcceptTask-priority null line**

In `select`, delete this block (~line 573-575):

```python
        if (state.task_code is None
                and MeansKind.ACCEPT_TASK in discretionary_kinds):
            step_goal = None
```

- [ ] **Step 3b: Remove the skill-gate reorder block**

In `select`, delete the entire `# ── Skill-gate prioritization ──` block (the
`if objective is not None: ... reorder_skill_candidates(...) ... raise
SkillProgressionError(...)` added in the prior feature, ~line 615-639). Remove the
now-unused import `from artifactsmmo_cli.ai.strategy_reorder import
reorder_skill_candidates`. (Keep the `gating_skills`/`SkillProgressionError` import
only if still referenced after this task — it is not, so remove it too; `mypy`/`ruff`
will flag if wrong.)

- [ ] **Step 3c: Add worth-suppression + last-resort**

Add imports near the other tier imports:

```python
from artifactsmmo_cli.ai.tiers.means_worth import means_serves
from artifactsmmo_cli.ai.tiers.objective_needs import objective_needs
```

After the `candidates` list is fully built (where the reorder block used to be) and
before `guard_reprs = {...}`, insert:

```python
        # ── Worth gate ─────────────────────────────────────────────────────
        # Suppress discretionary task means that serve NONE of the committed
        # objective's unmet needs. This both breaks the sticky short-circuit (a
        # suppressed committed task is skipped before the sticky check) and lets
        # the already-earlier objective step win. The objective is the chosen_root
        # (decision-tier hysteresis owns when it changes). See spec Component 3/4.
        worth_suppressed: set[str] = set()
        chosen_root: MetaGoal | None = getattr(decision, "chosen_root", None)
        if objective is not None and chosen_root is not None:
            needs = objective_needs(chosen_root, state, game_data)
            if not needs.is_empty:
                kind_by_repr = {
                    repr(map_means(mk, game_data, ctx, state)): mk
                    for mk in discretionary_kinds
                    if mk in (MeansKind.PURSUE_TASK, MeansKind.ACCEPT_TASK)
                }
                for r, mk in kind_by_repr.items():
                    g = map_means(mk, game_data, ctx, state)
                    if not means_serves(mk, g, needs, state, game_data):
                        worth_suppressed.add(r)
```

Then make the cheap + escalation passes use `suppressed | worth_suppressed` (the
`is_suppressed` closure currently reads `suppressed`; extend it). Change:

```python
        def is_suppressed(goal: Goal) -> bool:
            r = repr(goal)
            return r != "TaskCancel" and r in suppressed
```

to:

```python
        effective_suppressed = set(suppressed) | worth_suppressed

        def is_suppressed(goal: Goal) -> bool:
            r = repr(goal)
            return r != "TaskCancel" and r in effective_suppressed
```

> NOTE: `is_suppressed` is defined near the top of `select` (~line 483) BEFORE
> `worth_suppressed` is computed. Move the `is_suppressed` definition (and
> `effective_suppressed`) to AFTER the worth-gate block, or compute
> `worth_suppressed` before it. Keep one definition.

Finally, after the existing cheap→escalation→Wait selection, add the last-resort
ungated pass. Locate where `chosen` is finalized (after the `if chosen is None:`
Wait fallback, ~line 656-660) and BEFORE `self._committed_repr = new_committed`,
insert:

```python
        # Last resort: the objective stalled (its step couldn't plan) AND every
        # need-serving means failed, leaving only worth-suppressed task means. Re-run
        # the walk WITHOUT the worth gate so the bot keeps earning instead of idling.
        # Emit a marker so "objective stalled, doing income" is observable.
        if chosen is None and worth_suppressed:
            def _is_suppressed_ungated(goal: Goal) -> bool:
                r = repr(goal)
                return r != "TaskCancel" and r in suppressed
            chosen, plan, new_committed = select_pure(
                candidates=non_wait, committed_repr=self._committed_repr,
                try_plan=try_plan_full, is_satisfied=satisfied,
                is_suppressed=_is_suppressed_ungated)
            if chosen is not None:
                self.goals_tried.append({"goal": "worth_gate_bypassed", "nodes": 0,
                                         "depth": 0, "timed_out": False, "plan_len": len(plan)})
```

> The exact local names (`non_wait`, `try_plan_full`, `satisfied`,
> `new_committed`, `self.goals_tried`) match the current `select`. Read the method
> end-to-end before editing so the insertion uses the real locals.

- [ ] **Step 4: Run the integration test + full arbiter/player files**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py tests/test_ai/test_player.py -q`
Expected: the new test PASSES; investigate any existing-test failures (some arbiter
tests asserted the OLD AcceptTask-null / reorder behavior — update those tests to the
new intended behavior only when the new behavior is correct; do NOT weaken a test
that catches a real regression).

- [ ] **Step 5: Type-check + lint**

Run: `uv run mypy src/artifactsmmo_cli/ai/strategy_driver.py && uv run ruff check src/artifactsmmo_cli/ai/strategy_driver.py tests/test_ai/test_strategy_driver.py`
Expected: no errors (unused `reorder`/`gating_skills` imports removed).

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/strategy_driver.py tests/test_ai/test_strategy_driver.py
git commit -m "feat(planner): worth-gate task means; objective step wins when it serves"
```

---

## Task 6: Remove the superseded reorder module

**Files:**
- Delete: `src/artifactsmmo_cli/ai/strategy_reorder.py`, `tests/test_ai/test_strategy_reorder.py`

- [ ] **Step 1: Confirm no remaining references**

Run: `cd /home/blentz/git/artifactsmmo && grep -rn "strategy_reorder\|reorder_skill_candidates" src tests`
Expected: no matches (Task 5 removed the import + call). If any remain, remove them first.

- [ ] **Step 2: Delete the files**

```bash
git rm src/artifactsmmo_cli/ai/strategy_reorder.py tests/test_ai/test_strategy_reorder.py
```

- [ ] **Step 3: Verify suite still green**

Run: `uv run pytest tests/test_ai/ -q`
Expected: PASS (the liveness tests that imported reorder, if any, were updated in Task 5 — if `tests/test_ai/test_levelskill_liveness.py` imports `reorder_skill_candidates`, rewrite those specific assertions to exercise `objective_step_goal`'s craft-one path instead; do NOT delete the LIV-SKILL-2/3 coverage).

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor(planner): remove reorder_skill_candidates (superseded by worth gate)"
```

---

## Task 7: Planner performance (conditional on Task 0 profile)

**Files:** per the Task 0 profile result.

- [ ] **Step 1: Act on the profile**

Only if Task 0 found a dominant, fixable bottleneck:
- **Cycle-table aggregates dominate** → add a SQLite index. In
  `src/artifactsmmo_cli/ai/learning/store.py` `__init__` (after `create_all`), create
  an index on the `Cycle` columns the windowed queries filter/order by
  (`character`, `action_repr`, `ts`). Verify the query planner uses it. Test: a
  store-level test asserting the index exists (`PRAGMA index_list`) and a timing
  smoke test over a seeded N-row table.
- **`WorldState.apply` copy dominates** → reduce per-node copying (e.g. copy only
  mutated fields). Test: existing planner tests must still pass; add a micro-test
  asserting plan equality before/after on a fixture goal.
- **Branching dominates** → tighten the relevant `relevant_actions` filter for the
  hot goal. Test: assert the goal's `relevant_actions` excludes the now-filtered
  actions for a fixture.

- [ ] **Step 2: Verify + commit**

Run: `uv run pytest -q` (full suite). Commit with a message naming the bottleneck
fixed. If Task 0 found no offline-reproducible bottleneck, SKIP this task and note
it as a live-trace follow-up in the spec.

---

## Task 8: Full regression, coverage, repo gate

**Files:** test additions only as needed.

- [ ] **Step 1: Full suite + coverage**

Run: `uv run pytest -q`
Expected: 0 failures, 0 errors, 0 warnings, 0 skipped, coverage 100% (the project's
`--cov-fail-under=100`). Close any gap in the new modules with targeted tests (e.g.
`objective_needs` ReachCharLevel/empty branches, `means_worth` non-task pass-through,
the arbiter last-resort path, the craft-one fallback-to-LevelSkillGoal branch).

- [ ] **Step 2: Repo-wide type-check + lint (feature files)**

Run: `uv run mypy src && uv run ruff check src/artifactsmmo_cli/ai/tiers/objective_needs.py src/artifactsmmo_cli/ai/tiers/means_worth.py src/artifactsmmo_cli/ai/strategy_driver.py src/artifactsmmo_cli/ai/tiers/strategy.py`
Expected: mypy clean; ruff clean on feature files (pre-existing repo-wide ruff debt unrelated to this change may remain — confirm zero NEW findings).

- [ ] **Step 3: Behavioral assertion against the stuck-state**

Confirm the regression test from Task 5
(`test_worth_gate_picks_weapon_grind_over_nonserving_task`) plus the combat-loop
closure test demonstrate the fix: weapon grind selected over the non-serving task.
This is the spec's success criterion.

- [ ] **Step 4: Final commit (if Step 1 added tests)**

```bash
git add tests/ && git commit -m "test(planner): close coverage gaps on need-gated arbitration"
```

---

## Self-Review

**Spec coverage:**
- Component 1 (objective memory) → reuses existing `chosen_root`/`_last_strategy_root`; Task 5 reads `decision.chosen_root`. ✓
- Component 2 (objective needs) → Task 1. ✓
- Component 3 (worth gate) → Task 2 + Task 5 suppression. ✓
- Component 4 (objective-step-first + last-resort) → Task 5 (suppression makes the earlier step win; last-resort pass). ✓
- Component 5 (plannable craft-one step) → Task 3. ✓
- Component 6 (remove reorder) → Task 5b + Task 6. ✓
- Component 7 (perf, profile-then-target) → Task 0 + Task 7. ✓
- Component 8 (combat-readiness ranking) → Task 4. ✓

**Placeholder scan:** Task 0's profile harness is intentionally a procedure (offline
profiling can't be hard-coded without a learning DB); it specifies exactly what to
measure and record. Tasks 4 and 5 integration tests carry explicit "reuse the test
file's real helpers" notes for injection mechanics (the assertions are concrete and
non-negotiable). No TBDs in shipped code.

**Type consistency:** `NeedSet(materials, skill_xp, buy_only, char_xp)` +
`.is_empty`; `objective_needs(root, state, game_data) -> NeedSet`;
`means_serves(kind, goal, needs, state, game_data) -> bool`; `skill_grind_target`
reused with its existing signature; `objective_step_goal` returns
`GatherMaterialsGoal` (repr `GatherMaterials(<code>)`) for a gating ReachSkillLevel.
Names consistent across tasks and verified against current source.

**Risk note:** Task 5 is the load-bearing change. Existing arbiter tests that
encoded the OLD AcceptTask-null / reorder behavior will need updating to the new
intended behavior — update only when the new behavior is demonstrably correct, never
to silence a real regression. The full suite (Task 8) is the backstop.

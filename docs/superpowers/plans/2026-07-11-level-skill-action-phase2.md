# LevelSkill Action — Implementation Plan (Phase 2: activation)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make the (P1-shipped, inert) `LevelSkill` action LIVE: emitted from `build_actions`, planned before a gated craft (generator fast-path + A*), and EXECUTABLE one grind-cycle at a time via a player hook — then retire the `GatherMaterialsGoal.is_plannable` under-skill fast-fail (and the whole `SkillGateFastFail` proof set) so under-skill craft goals plan live instead of being pruned.

**Architecture:** Ordering is safety-critical. The `is_plannable` fast-fail prunes under-skill `GatherMaterialsGoal`s at `strategy_driver.py:999` BEFORE the generator/A* ever runs, so while it stands, no live plan can contain a `LevelSkill` (execute would raise). Therefore land emit + execution-hook + generator-leg FIRST (all live-inert behind the still-standing fast-fail), and remove the fast-fail LAST as the single activation step. No commit is ever plannable-but-not-executable.

**Tech Stack:** Python 3.13, `uv`, GOAP planner (`GOAPPlanner`/`StrategyArbiter`), directed craft generator, Lean 4 decision mirror (`formal/`).

## Global Constraints

- Every Python command prefixed `uv run` (uv at `/home/blentz/.local/bin/uv`, not on PATH).
- TDD: failing test first, watch it fail, minimal code. 0 errors/warnings/skipped, 100% coverage.
- No inline imports; all at top. Never `if TYPE_CHECKING`. Never catch `Exception`. One behavioral class per file.
- Action identity: `LevelSkill` repr becomes ASCII `LevelSkill(<skill>-><target>)` (Task 1 changes it from the P1 Unicode `→`, matching `LevelSkillGoal` and the `loadout_profiles._SKILL_RE` / `macro/segmentation.py` parsers).
- `formal/diff/` + `gate.sh` (Lean + diff + mutation) run on any decision-path (`is_applicable`/`apply`/`cost`/`is_plannable`/`WorldState`) or Lean change — NOT in the default pytest path; run explicitly. Serialize gate runs (never concurrent with anything importing `src`).
- Commit only when a task's review is clean; do not push unless asked.
- P1 interfaces (shipped): `LevelSkill(skill: str, target_level: int, xp_curve: SkillXpCurve | None = None)` at `src/artifactsmmo_cli/ai/actions/level_skill.py`; `tags = frozenset({"skill_grind"})`; `apply` sets `skills[skill]=target`; `is_applicable` = under-target AND `skill_grind_target(skill,state,gd) is not None`; `execute` currently RAISES (Task 3 replaces the live path).

---

## File Structure

- **Modify** `src/artifactsmmo_cli/ai/actions/level_skill.py` — repr → ASCII (Task 1).
- **Modify** `src/artifactsmmo_cli/ai/actions/factory.py` — emit one `LevelSkill(skill, L)` per distinct in-skill craft level (Task 2).
- **Create** `src/artifactsmmo_cli/ai/level_skill_expand.py` — pure-ish helper `next_grind_goal(skill, state, game_data) -> GatherMaterialsGoal | None` that mirrors the tree's rung-selection→GatherMaterials(skill_grind) construction, reused by the player hook (Task 3). One class/function responsibility; keeps `player._execute` thin and testable.
- **Modify** `src/artifactsmmo_cli/ai/player.py` — `_execute` hook: `plan[0]` a `LevelSkill` runs one grind cycle via `next_grind_goal` + sub-plan (Task 3).
- **Modify** `src/artifactsmmo_cli/ai/craft_plan_gen.py` — emit a `LevelSkill` leg at the skill-gate instead of `None` (Task 4).
- **Modify** `src/artifactsmmo_cli/ai/goals/gathering.py` — remove the crafting-skill-gate arm of `is_plannable` (Task 5).
- **Delete** `src/artifactsmmo_cli/ai/goals/gather_plannable_core.py` + retire `formal/Formal/SkillGateFastFail.lean` and every anchor (Task 5).

---

## Task 1: Repr → ASCII

**Files:** Modify `src/artifactsmmo_cli/ai/actions/level_skill.py`; Modify `tests/test_ai/test_level_skill_action.py`.

- [ ] **Step 1: Update the repr test (RED)**

In `tests/test_ai/test_level_skill_action.py`, change `test_repr_uses_arrow`:

```python
def test_repr_uses_ascii_arrow() -> None:
    # ASCII '->' matches LevelSkillGoal + loadout_profiles._SKILL_RE / macro
    # segmentation parsers, so the action repr is parseable once it enters
    # live plan traces (P2).
    assert repr(LevelSkill("gearcrafting", 5)) == "LevelSkill(gearcrafting->5)"
```

Run: `uv run pytest tests/test_ai/test_level_skill_action.py::test_repr_uses_ascii_arrow -q --no-cov` → FAIL (still Unicode `→`).

- [ ] **Step 2: Change the repr (GREEN)**

In `level_skill.py`, `__repr__`: `return f"LevelSkill({self.skill}->{self.target_level})"`. Update the class docstring / Global-Constraints mention of `→` to `->`.

Run: `uv run pytest tests/test_ai/test_level_skill_action.py -q --no-cov` → all pass.

- [ ] **Step 3: Confirm the Lean diff is unaffected + commit**

The Lean differential test asserts skill VALUES, not repr, so no formal change. Confirm: `uv run python -m pytest formal/diff/test_level_skill_diff.py -q` → PASS.

```bash
git add src/artifactsmmo_cli/ai/actions/level_skill.py tests/test_ai/test_level_skill_action.py
git commit -m "refactor(planner): LevelSkill repr uses ASCII arrow to match parsers (P2)"
```

---

## Task 2: Emit LevelSkill from build_actions

**Files:** Modify `src/artifactsmmo_cli/ai/actions/factory.py`; Test `tests/test_ai/test_factory_level_skill.py` (create).

**Interfaces:**
- Consumes: `build_actions(game_data, state, objective, bank_accessible, task_exchange_min_coins, protected_gear=frozenset()) -> list[Action]` (`factory.py:43`); the per-recipe loop at `factory.py:96-101` where `stats.crafting_skill`/`stats.crafting_level` are in scope; `LevelSkill` (P1).
- Produces: `build_actions` output contains exactly one `LevelSkill(skill, L)` per distinct `(crafting_skill, crafting_level)` present in `game_data.crafting_recipes` (deduped).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_factory_level_skill.py
"""build_actions emits one LevelSkill per distinct in-skill craft level so A*
and the directed generator can satisfy any gated CraftAction's skill gate."""

from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
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
        "bar": ItemStats(code="bar", level=5, type_="resource",
                         subtype="craft", crafting_skill="mining",
                         crafting_level=5),
        "gear_ore": ItemStats(code="gear_ore", level=1, type_="resource",
                              subtype="mob"),
    }
    gd._crafting_recipes = {"widget": {"gear_ore": 2}, "trinket": {"gear_ore": 1},
                            "bar": {"gear_ore": 1}}
    gd._workshop_locations = {"gearcrafting": (2, 2), "mining": (3, 3)}
    return gd


def test_build_actions_emits_one_level_skill_per_distinct_level() -> None:
    gd = _gd()
    state = scenario_state(ScenarioCharacter(name="t", level=5), gd)
    objective = CharacterObjective.from_game_data(gd)
    actions = build_actions(gd, state, objective, bank_accessible=True,
                            task_exchange_min_coins=0)
    level_skills = {(a.skill, a.target_level) for a in actions
                    if isinstance(a, LevelSkill)}
    assert level_skills == {("gearcrafting", 5), ("gearcrafting", 1),
                            ("mining", 5)}
```

Run: `uv run pytest tests/test_ai/test_factory_level_skill.py -q --no-cov` → FAIL (no LevelSkill emitted).

- [ ] **Step 2: Emit in the craft loop (GREEN)**

Add `from artifactsmmo_cli.ai.actions.level_skill import LevelSkill` at the top of `factory.py`. Around the per-recipe loop (`factory.py:96-101`), collect distinct `(skill, level)` and emit after the loop:

```python
    _level_skill_seen: set[tuple[str, int]] = set()
    for item_code, recipe in game_data.crafting_recipes.items():
        stats = game_data.item_stats(item_code)
        if stats is None:
            continue
        workshop_loc = game_data.workshop_location(stats.crafting_skill) if stats.crafting_skill else None
        actions.append(CraftAction(code=item_code, quantity=1, workshop_location=workshop_loc))
        if stats.crafting_skill and stats.crafting_level:
            _level_skill_seen.add((stats.crafting_skill, stats.crafting_level))
    for _skill, _lvl in _level_skill_seen:
        actions.append(LevelSkill(skill=_skill, target_level=_lvl))
```

Run: `uv run pytest tests/test_ai/test_factory_level_skill.py -q --no-cov` → PASS.

- [ ] **Step 3: Coverage/lint + commit**

```
uv run pytest tests/test_ai/test_factory_level_skill.py -q --cov=artifactsmmo_cli.ai.actions.factory --cov-report=term-missing
uv run ruff check src/artifactsmmo_cli/ai/actions/factory.py
uv run mypy src/artifactsmmo_cli/ai/actions/factory.py
```
Then:
```bash
git add src/artifactsmmo_cli/ai/actions/factory.py tests/test_ai/test_factory_level_skill.py
git commit -m "feat(planner): build_actions emits LevelSkill per distinct craft level (P2)"
```

Note: this stays LIVE-INERT — the `is_plannable` fast-fail (Task 5) still prunes under-skill `GatherMaterials` before any `LevelSkill` can enter a live plan.

---

## Task 3: Player execution hook (one grind cycle)

**Files:** Create `src/artifactsmmo_cli/ai/level_skill_expand.py`; Test `tests/test_ai/test_level_skill_expand.py`; Modify `src/artifactsmmo_cli/ai/player.py` (`_execute`); Test `tests/test_ai/test_player_level_skill_hook.py`.

**Interfaces:**
- Consumes: `skill_grind_target(skill, state, game_data) -> str | None` (`tiers/skill_grind_target.py:82`); `GatherMaterialsGoal(target_item, needed, skill_grind=True)` (`goals/gathering.py`) — construction mirrored from `strategy_driver.py:866-871`; `GamePlayer` fields `self.game_data`, `self.planner` (`GOAPPlanner`), `self.state`, `self._build_actions()` (`player.py:130,136,137,335`); the `_execute` isinstance ladder at `player.py:750`; the execute call at `player.py:764`.
- Produces: `next_grind_goal(skill, state, game_data) -> GatherMaterialsGoal | None`; a `_execute` branch that, for a `LevelSkill` plan step, plans + executes ONE leg of `next_grind_goal`'s sub-plan and returns the resulting `WorldState` (never calling `LevelSkill.execute`).

- [ ] **Step 1: Write the failing test for `next_grind_goal`**

```python
# tests/test_ai/test_level_skill_expand.py
"""next_grind_goal picks the grind rung for a LevelSkill and builds the
skill_grind GatherMaterials goal the player executes one leg of per cycle —
mirroring strategy_driver.py:866-871."""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.level_skill_expand import next_grind_goal
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "trinket": ItemStats(code="trinket", level=1, type_="resource",
                             subtype="craft", crafting_skill="gearcrafting",
                             crafting_level=1),
        "gear_ore": ItemStats(code="gear_ore", level=1, type_="resource",
                              subtype="mob"),
    }
    gd._crafting_recipes = {"trinket": {"gear_ore": 1}}
    gd._resource_drops = {"gear_rocks": "gear_ore"}
    gd._resource_skill = {"gear_rocks": ("mining", 1)}
    gd._resource_locations = {"gear_rocks": [(3, 3)]}
    gd._workshop_locations = {"gearcrafting": (2, 2)}
    return gd


def test_next_grind_goal_targets_the_rung_skill_grind() -> None:
    gd = _gd()
    state = scenario_state(
        ScenarioCharacter(name="t", level=5, skills={"gearcrafting": 1}), gd)
    goal = next_grind_goal("gearcrafting", state, gd)
    assert isinstance(goal, GatherMaterialsGoal)
    assert goal.skill_grind is True
    # targets the selected rung, held+1 (mirrors strategy_driver:866-871)
    assert goal.needed == {"trinket": 1}


def test_next_grind_goal_none_when_no_rung() -> None:
    gd = GameData()
    gd._item_stats = {
        "lonely": ItemStats(code="lonely", level=10, type_="resource",
                            subtype="craft", crafting_skill="gearcrafting",
                            crafting_level=10),
    }
    gd._crafting_recipes = {"lonely": {"gear_ore": 2}}
    state = scenario_state(
        ScenarioCharacter(name="t", level=5, skills={"gearcrafting": 5}), gd)
    assert next_grind_goal("gearcrafting", state, gd) is None
```

Run → FAIL (module missing).

- [ ] **Step 2: Implement `next_grind_goal`**

```python
# src/artifactsmmo_cli/ai/level_skill_expand.py
"""Expand a LevelSkill plan step into one grind cycle's goal.

The LevelSkill action is a planner abstraction (its apply optimistically levels
the skill); at execution the player runs ONE cycle of the concrete grind — craft
one in-skill rung — and replans, exactly as the retired ReachSkillLevel dispatch
did (strategy_driver.py:866-871). This picks the rung and builds the
skill_grind GatherMaterials goal; the caller plans it and executes its first leg.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from artifactsmmo_cli.ai.world_state import WorldState


def next_grind_goal(skill: str, state: WorldState,
                    game_data: GameData) -> GatherMaterialsGoal | None:
    """The skill_grind GatherMaterials goal for one grind cycle of `skill`, or
    None when no in-skill rung is craftable from the current level."""
    rung = skill_grind_target(skill, state, game_data)
    if rung is None:
        return None
    bank = state.bank_items or {}
    held = state.inventory.get(rung, 0) + bank.get(rung, 0)
    return GatherMaterialsGoal(target_item=rung, needed={rung: held + 1},
                               skill_grind=True)
```

Run the `test_level_skill_expand.py` tests → PASS.

- [ ] **Step 3: Write the failing player-hook test**

```python
# tests/test_ai/test_player_level_skill_hook.py
"""When plan[0] is a LevelSkill, the player runs ONE grind-cycle leg instead of
calling LevelSkill.execute (which raises). Uses a fake client so no live API."""
```
Author a test that builds a `GamePlayer` (or the minimal `_execute` seam) with `state` under-skill, `plan[0] = LevelSkill("gearcrafting", 5)`, and a fake client that records the sub-leg executed; assert `_execute` does NOT raise and advances via the grind sub-plan's first leg (e.g. a `GatherAction`/`CraftAction`), not `LevelSkill.execute`. Model the player construction on the existing player tests (`grep -l "GamePlayer(" tests/test_ai/`), reusing their client fakes. If the full `GamePlayer` is too heavy to instantiate in a unit test, extract the hook body into a small method `_execute_level_skill(action, client) -> WorldState` on `GamePlayer` and unit-test THAT with a constructed player + fake client — do NOT weaken the assertion that `LevelSkill.execute` is never called.

Run → FAIL.

- [ ] **Step 4: Add the hook in `_execute`**

Add `from artifactsmmo_cli.ai.level_skill_expand import next_grind_goal` and `from artifactsmmo_cli.ai.actions.level_skill import LevelSkill` at the top of `player.py`. In `_execute` (the isinstance ladder at `player.py:750`, BEFORE the generic `action.execute` at :764), add:

```python
        if isinstance(action, LevelSkill):
            return self._execute_level_skill(action, client)
```

and implement `_execute_level_skill`:

```python
    def _execute_level_skill(self, action: LevelSkill,
                             client: AuthenticatedClient) -> tuple[WorldState, ...]:
        """Run ONE grind cycle for a LevelSkill plan step: pick the rung, plan the
        skill_grind GatherMaterials goal, execute its first leg. The next cycle's
        replan re-derives the remaining grind (one-leg-per-cycle idiom); when the
        real skill reaches target, is_applicable turns False and the plan advances
        to the gated craft."""
        goal = next_grind_goal(action.skill, self.state, self.game_data)
        if goal is None:
            raise RuntimeError(
                f"LevelSkill({action.skill}) has no grind rung at execution — "
                "is_applicable should have gated this")
        actions = self._build_actions()
        sub_plan = self.planner.plan(self.state, goal, actions, self.game_data,
                                     budget_seconds=CRAFT_PLAN_BUDGET_SECONDS)
        if not sub_plan:
            raise RuntimeError(f"LevelSkill({action.skill}) grind produced no leg")
        return self._execute(sub_plan[0], client)
```

Match `_execute`'s real return type/signature (it returns `tuple[WorldState, outcome]` per `player.py:629`; adjust the annotation and the two `raise`-guards to the actual shape — read `player.py:742-764` and mirror it exactly). Use the same budget constant the arbiter/generator use for a cheap plan (locate it near `player.py`/`strategy_driver`; if none is exposed, pass `budget_seconds=10.0`). The two `raise`s are guards for states `is_applicable` already excludes — they are unreachable in a correct plan (not error-swallowing).

Run the hook test → PASS. Run `tests/test_ai/test_player*.py -q --no-cov` → no regression.

- [ ] **Step 5: Coverage/lint + commit**

```
uv run pytest tests/test_ai/test_level_skill_expand.py tests/test_ai/test_player_level_skill_hook.py -q \
  --cov=artifactsmmo_cli.ai.level_skill_expand --cov-report=term-missing
uv run ruff check src/artifactsmmo_cli/ai/level_skill_expand.py src/artifactsmmo_cli/ai/player.py
uv run mypy src/artifactsmmo_cli/ai/level_skill_expand.py src/artifactsmmo_cli/ai/player.py
```
```bash
git add src/artifactsmmo_cli/ai/level_skill_expand.py src/artifactsmmo_cli/ai/player.py \
        tests/test_ai/test_level_skill_expand.py tests/test_ai/test_player_level_skill_hook.py
git commit -m "feat(player): expand LevelSkill plan step into one grind cycle (P2)"
```

Still LIVE-INERT: the fast-fail (Task 5) prevents any live `LevelSkill` plan until it is removed; this hook is exercised by tests now and activates at Task 5.

---

## Task 4: Directed generator emits a LevelSkill leg

**Files:** Modify `src/artifactsmmo_cli/ai/craft_plan_gen.py`; Test `tests/test_ai/test_craft_plan_gen_level_skill.py` (create).

**Interfaces:**
- Consumes: `generate_next_craft_action(goal, state, game_data, actions) -> list[Action] | None` (`craft_plan_gen.py:74`); the skill-gate None-return at `craft_plan_gen.py:135-136`; `LevelSkill` (P1); the `relevant` action list (contains the emitted `LevelSkill` via the `skill_grind` tag admission).
- Produces: for an under-skill craft closure, the generator returns `[LevelSkill(skill, craft_level)]` (one-leg-per-cycle) instead of `None`, when a `LevelSkill(skill, craft_level)` for the unmet gate is present in `actions`.

- [ ] **Step 1: Write the failing test**

Construct the widget/trinket under-skill fixture (as Task 2/3), build `actions` via `build_actions` (now emits `LevelSkill`), call `generate_next_craft_action(GatherMaterialsGoal("widget",{"widget":1}), state, gd, actions)` at gearcrafting 1, and assert it returns `[LevelSkill(skill="gearcrafting", target_level=5)]` (not `None`).

Run → FAIL (returns `None` at the skill gate).

- [ ] **Step 2: Emit the LevelSkill leg**

At `craft_plan_gen.py:135-136`, replace the `return None` skill-gate branch: when `state.skills.get(stats.crafting_skill, 1) < stats.crafting_level`, find the matching `LevelSkill(stats.crafting_skill, stats.crafting_level)` in `actions` (the `relevant`/`actions` list) and return `[that_level_skill]` immediately (one-leg-per-cycle, mirroring the Fight truncation at `:189-196`). If no matching `LevelSkill` is in `actions`, keep `return None` (fall back to A*). Add `from artifactsmmo_cli.ai.actions.level_skill import LevelSkill` at top. Show the exact branch:

```python
            if state.skills.get(stats.crafting_skill, 1) < stats.crafting_level:
                lvl = next((a for a in actions
                            if isinstance(a, LevelSkill)
                            and a.skill == stats.crafting_skill
                            and a.target_level == stats.crafting_level), None)
                return [lvl] if lvl is not None else None
```

Run the generator test → PASS.

- [ ] **Step 3: Coverage/lint + commit**

```
uv run pytest tests/test_ai/test_craft_plan_gen_level_skill.py tests/test_ai/test_craft_plan_gen*.py -q \
  --cov=artifactsmmo_cli.ai.craft_plan_gen --cov-report=term-missing
uv run ruff check src/artifactsmmo_cli/ai/craft_plan_gen.py
uv run mypy src/artifactsmmo_cli/ai/craft_plan_gen.py
```
```bash
git add src/artifactsmmo_cli/ai/craft_plan_gen.py tests/test_ai/test_craft_plan_gen_level_skill.py
git commit -m "feat(planner): directed generator emits LevelSkill leg at the skill gate (P2)"
```

Still LIVE-INERT (fast-fail prunes before the generator runs, per `strategy_driver.py:999` vs `:1015`).

---

## Task 5: Retire the is_plannable fast-fail + SkillGateFastFail (ACTIVATION)

This is the switch: removing the crafting-skill-gate arm lets under-skill `GatherMaterials` reach the generator (Task 4) / A* (which plans `LevelSkill`, Task 2), executed by the hook (Task 3). After this task the action is LIVE.

**Files:**
- Modify `src/artifactsmmo_cli/ai/goals/gathering.py` (`is_plannable`, remove crafting-skill arm; keep currency arm; drop the `gather_plannable_core` import).
- Delete `src/artifactsmmo_cli/ai/goals/gather_plannable_core.py`.
- Retire Lean: delete `formal/Formal/SkillGateFastFail.lean`; remove its anchors: `formal/Formal.lean:221`, `formal/Formal/Manifest.lean:25` + `:1158-1162`, `formal/Formal/Audit.lean:926-928`, `formal/Formal/Contracts.lean:18` + `:3084-3095`, `formal/Oracle.lean:2344-2350` (`runGatherPlannable`) + `:3025-3026` (`"gather_plannable"` key), `formal/diff/test_skill_gate_fastfail_diff.py` (delete), `formal/diff/mutate.py:280,2170-2182,2617,4984-4985` (remove the `GATHER_PLANNABLE` group), `formal/README.md:40,133` (prose). Update the `formal/Formal/CurrencyAffordFastFail.lean:10` cross-reference comment.
- Tests: update/remove `tests/**` that assert the under-skill fast-fail (grep `gather_plannable` and `is_plannable` under-skill tests, e.g. `tests/test_ai/test_craft_vs_buy_wiring.py`).

**Interfaces:**
- Consumes: `is_plannable(state, game_data, history=None)` at `gathering.py:518`; `_currency_leaves_affordable` (`gathering.py:496`, STAYS); the arbiter gate at `strategy_driver.py:999`.
- Produces: `is_plannable` returns `False` ONLY when a currency leaf is unaffordable; under-skill craft goals are now plannable (routed to generator/A*).

- [ ] **Step 1: Write the failing test — under-skill goal is now plannable**

```python
# in tests/test_ai/ (new or existing is_plannable test module)
def test_is_plannable_true_for_under_skill_craft_goal() -> None:
    """Under-skill craft goals are no longer fast-failed — the planner (with
    LevelSkill in the action set) sequences grind->craft."""
    # widget gearcrafting 5, char gearcrafting 1, materials gatherable.
    ... build the widget/trinket fixture ...
    goal = GatherMaterialsGoal(target_item="widget", needed={"widget": 1})
    assert goal.is_plannable(state, gd) is True
```

Also keep/confirm a test that the currency arm STILL fast-fails (an unaffordable non-gold-currency leaf → `is_plannable is False`).

Run → the under-skill test FAILs (currently pruned).

- [ ] **Step 2: Remove the crafting-skill arm**

In `gathering.py:518-544`, keep the currency arm (`if not self._currency_leaves_affordable(...): return False`) and replace everything from `if self._target_item not in self._needed:` through the final `gather_plannable_pure(...)` return with `return True`. Remove the `from ...gather_plannable_core import gather_plannable_pure` import (`gathering.py:22`). Update the method docstring (drop the skill-gate rationale; keep the currency-leaf rationale). Delete `src/artifactsmmo_cli/ai/goals/gather_plannable_core.py`.

Run the is_plannable tests → PASS (under-skill True, currency-unaffordable False).

- [ ] **Step 3: Retire the Lean SkillGateFastFail set**

Delete `formal/Formal/SkillGateFastFail.lean` and remove every anchor listed under Files (imports, Manifest role-check, Audit axiom prints, Contracts anti-weakening pins, Oracle `runGatherPlannable` + `"gather_plannable"` key, the diff test, the `mutate.py` group, README prose). Use the lean tooling (`ToolSearch select:mcp__lean-lsp__lean_diagnostic_messages` etc.) + `cd formal && lake build` to confirm no dangling reference and a clean build (no `sorry`, no orphaned `#check`).

- [ ] **Step 4: Full gate (serialized)**

Run `./gate.sh` → ALL PARTS PASSED (lake build clean after the retirement; formal/diff no longer includes the deleted test; mutation group removed; the LevelSkill diff/mutation from P1 still green; planner unaffected). This is the phase's decision-path + Lean gate.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(planner): retire under-skill is_plannable fast-fail + SkillGateFastFail — LevelSkill live (P2)"
```

---

## Task 6: Exit verification — under-skill census cells PASS + runtime

**Files:** none new (verification task).

- [ ] **Step 1: Census — under-skill cells now PASS via LevelSkill**

Run the diagnostic over the real bundle: `uv run python scripts/diag_census_bugs.py 2>&1 | grep -v christmas | tail`. Expected: the 108 former SKILL_PREREQUISITE (under-skill) cells now produce a directional plan whose first leg is `LevelSkill(...)` → PASS (or classify honestly if a residual reason remains). Note: `SKILL_PREREQUISITE` is still a class until Phase 4; here we confirm the census's under-skill cells PLAN (planner capability), not the class removal.

- [ ] **Step 2: Runtime — live `plan <char>` sequences LevelSkill → Craft**

Per `[[feedback_verify_runtime_activation]]` (green tests ≠ runtime-active): run `uv run artifactsmmo plan <char>` for a character under-skill for a known gear/tool target and confirm the printed plan sequences a `LevelSkill(...)` before the gated `Craft`. Record the plan output in the task report.

- [ ] **Step 3: Full-suite sign-off**

`uv run pytest -q` → passed, 100% coverage. (`gate.sh` already run at Task 5.)

- [ ] **Step 4: Whole-branch review + finish**

Dispatch the final whole-branch reviewer over `MERGE_BASE..HEAD` for Phase 2; address findings; then Phase 2 is complete (on main, not pushed). Phase 3 (retire `ReachSkillLevel`/`LevelSkillGoal` tree routing + migrate proofs) and Phase 4 (delete `SKILL_PREREQUISITE`, ship the held census workaround, `--check` planner_bug 0) follow.

---

## Roadmap — Phases 3–4 (unchanged from the spec, planned after P2)

- **P3:** retire `ReachSkillLevel` (meta-goal + `strategy_driver` dispatch + `prerequisite_graph` emission) and `LevelSkillGoal`; the rung-selection cores (`skill_step_dispatch`/`skill_grind_selection`) SURVIVE (the P2 execution hook uses them via `next_grind_goal`→`skill_grind_target`); migrate `MetaGoalDispatch`/`SkillGapClosure` liveness to the action; add the gather-skill arm to `LevelSkill.is_applicable`/expansion. Also apply the two P2-pre-work notes recorded in the SDD ledger: (a) confirm the ASCII-repr fix removed the `_SKILL_RE` trap; (b) admit the `skill_grind` tag in any other goal (`craft_relief`/`craft_potions`/`progression`) that emits under-skill crafts.
- **P4:** delete `SKILL_PREREQUISITE` gap class + tests; ship the held census workaround (located-source / grey-farm / purchase-recursion); regen docs; `scripts/gen_craft_completeness.py --check` → planner_bug 0. Acceptance met.

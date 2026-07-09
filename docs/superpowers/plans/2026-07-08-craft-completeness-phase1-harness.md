# Craft-Planning Completeness — Phase 1: Harness + Verdict + Classifier

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the pure, unit-tested core of the crafting-recipe planning-completeness census — `plan_craft` (drive the real planner at a single recipe), `craft_grid` (the per-recipe level/skill cells), `craft_cell_verdict` (PASS iff plan[0] advances the recipe's closure), and `classify_gap` (5-way FAIL classification) — with no generator/docs yet. Spec: `docs/superpowers/specs/2026-07-08-craft-planning-completeness-design.md`.

**Architecture:** One new behavioral unit `src/artifactsmmo_cli/audit/craft_completeness.py` beside the existing `audit/` package. `plan_craft` reuses the production planning path (`build_actions` + `GatherMaterialsGoal(X)` + `GOAPPlanner.plan`) so the census exercises the exact planner the bot runs, just aimed at any recipe. The grid/verdict/classifier are pure functions over `GameData` + `WorldState` + the returned plan.

**Tech Stack:** Python 3.13 (`uv`), pytest. No Lean (this validates the running planner, not a proof).

## Global Constraints (spec + repo rules)

- `plan_craft(X, state, game_data)` = `GOAPPlanner().plan(state, GatherMaterialsGoal(X, {X:1}), build_actions(...), game_data, budget_seconds=CRAFT_AUDIT_BUDGET_SECONDS)` — the production obtain-X path, per spec "Objective injection".
- PASS predicate (spec, verbatim): plan non-empty AND `plan[0]` advances X's transitive closure — a Gather/Fight/NpcBuy/WithdrawItem of a closure material, a Craft of X or a closure intermediate, OR a skill-grind leg toward X's craft skill. FAIL on empty / `[Wait]` / unrelated first action.
- Gap classes (spec): `PLANNER_BUG`, `COMBAT_BLOCKED`, `EVENT_GATED`, `MATERIAL_UNREACHABLE`, `SKILL_UNREACHABLE`.
- Grid (spec): char cells = nominal (`1` if `L≤9` else `10·T`, `T=L//10+1`) + `10·T±2`, clamped `[1,50]`; skill cells = `max(0, L−5)` and `L`; empty inventory+bank; `derive_combat_stats`.
- Pure functions unit-tested independent of the planner; no floats in the verdict; no inline imports; never catch Exception; TDD; 100% coverage; mypy strict.
- Reuses existing helpers only (`recipe_closure`, `is_attainable_now`, `_pick_winnable_monster`-equivalent) — no new game model.
- Never run gate.sh/mutate.py while the bot runs (this phase adds no Lean/mutants; the full gate is unaffected, run at next downtime as courtesy).

---

### Task 1: `plan_craft` — drive the real planner at one recipe

**Files:**
- Create: `src/artifactsmmo_cli/audit/craft_completeness.py`
- Test: `tests/test_audit/test_craft_completeness.py` (+ `tests/test_audit/__init__.py` if absent)

**Interfaces:**
- Produces (later tasks + the generator consume):
  - `CRAFT_AUDIT_BUDGET_SECONDS: float = 10.0` — modest per-cell budget (matches the arbiter's cheap first pass; ~1900 cells stay bounded via the CPU memo + node cap).
  - `plan_craft(recipe: str, state: WorldState, game_data: GameData) -> list[Action]` — the plan the production planner produces for obtaining `recipe` from `state`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_audit/test_craft_completeness.py
"""Craft-planning completeness core (spec 2026-07-08). plan_craft drives the
REAL planner at one recipe via the production obtain-X path."""

import json
from pathlib import Path

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.audit.craft_completeness import plan_craft
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.scenario import scenario_state, ScenarioCharacter

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")


def _gd() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def test_plan_craft_plans_a_simple_smelt() -> None:
    """copper_bar = smelt copper_ore (mining). A L5/mining-5 char with empty
    inventory must get a real plan whose first leg gathers or crafts toward
    copper_bar — not an empty plan."""
    gd = _gd()
    sc = ScenarioCharacter(name="t", level=5, skills={"mining": 5},
                           derive_combat_stats=True)
    state = scenario_state(sc, gd)
    plan = plan_craft("copper_bar", state, gd)
    assert plan, "expected a non-empty plan for copper_bar"
    # first leg is a gather (copper_ore) or a craft toward copper_bar
    assert isinstance(plan[0], (GatherAction, CraftAction)), repr(plan[0])
```

NOTE: verify `CharacterObjective.from_game_data`, `build_actions`,
`GatherMaterialsGoal`, `GOAPPlanner` import paths against source before
writing Step 3 (they are: `ai.tiers.objective.CharacterObjective`,
`ai.actions.factory.build_actions`, `ai.goals.gathering.GatherMaterialsGoal`,
`ai.planner.GOAPPlanner`). `build_actions` needs a
`task_exchange_min_coins` int — pass `0` (task funding is irrelevant to
craft planning; document the choice inline).

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_audit/test_craft_completeness.py::test_plan_craft_plans_a_simple_smelt -q --no-cov`
Expected: FAIL — `ModuleNotFoundError: ...audit.craft_completeness`

- [ ] **Step 3: Implement**

```python
# src/artifactsmmo_cli/audit/craft_completeness.py
"""Crafting-recipe planning-completeness census (spec docs/superpowers/specs/
2026-07-08-craft-planning-completeness-design.md).

Drives the REAL production planner at every craftable recipe across a
level/skill grid and classifies whether it can produce a directional plan.
Pure cores (grid/verdict/classifier) + a thin planner harness (`plan_craft`);
the generator/docs live in scripts/gen_craft_completeness.py."""

from artifactsmmo_cli.ai.actions.action import Action
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import WorldState

CRAFT_AUDIT_BUDGET_SECONDS = 10.0
"""Per-cell planner budget — the arbiter's cheap first-pass value; keeps the
~1900-cell offline census bounded (CPU memo + node cap do the rest)."""


def plan_craft(recipe: str, state: WorldState,
               game_data: GameData) -> list[Action]:
    """The plan the production planner produces for obtaining `recipe` from
    `state` — the exact obtain-X path the tree's gear branch uses, aimed at
    any recipe. task_exchange_min_coins=0: task funding is irrelevant to
    craft planning."""
    objective = CharacterObjective.from_game_data(game_data)
    actions = build_actions(
        game_data, state, objective,
        bank_accessible=True, task_exchange_min_coins=0)
    goal = GatherMaterialsGoal(target_item=recipe, needed={recipe: 1})
    return GOAPPlanner().plan(state, goal, actions, game_data,
                              budget_seconds=CRAFT_AUDIT_BUDGET_SECONDS)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_audit/test_craft_completeness.py -q --no-cov`
Expected: PASS. If the first leg is neither Gather nor Craft (e.g. a Move or Withdraw appears first), widen the assertion to the real production shape and note it — the plan's VALIDITY (non-empty, toward copper_bar) is the contract.

- [ ] **Step 5: Full suite, commit**

Run: `uv run pytest -q` — all pass, 100% coverage.

```bash
git add src/artifactsmmo_cli/audit/craft_completeness.py tests/test_audit/
git commit -m "feat(audit): plan_craft — drive the real planner at one recipe"
```

---

### Task 2: `craft_grid` — the per-recipe level/skill cells

**Files:** Modify `craft_completeness.py`; Test: extend the test file.

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) CraftCell: char_level: int; skill_name: str; skill_level: int`
  - `craft_grid(recipe: str, game_data: GameData) -> list[CraftCell]` — the 6 cells (3 char-levels × 2 skill-levels) per the spec grid, deduped and clamped.

- [ ] **Step 1: Write the failing tests**

```python
from artifactsmmo_cli.audit.craft_completeness import CraftCell, craft_grid


def test_craft_grid_cells_for_a_tier2_recipe() -> None:
    """iron_boots: gearcrafting 10 (L=10, T=2). char cells 10-2/10/10+2=8,10,12;
    skill cells max(0,10-5)=5 and 10."""
    gd = _gd()
    cells = craft_grid("iron_boots", gd)
    char_levels = sorted({c.char_level for c in cells})
    skill_levels = sorted({c.skill_level for c in cells})
    assert char_levels == [8, 10, 12]
    assert skill_levels == [5, 10]
    assert all(c.skill_name == "gearcrafting" for c in cells)
    assert len(cells) == 6


def test_craft_grid_tier1_uses_level_1_and_skill_0() -> None:
    """A T1 recipe (craft level <= 9): nominal char level is 1; under-skill
    clamps to 0 when L-5 < 0."""
    gd = _gd()
    # copper_bar: mining 1 (L=1, T=1). nominal 1; ±2 -> clamp to [1,50]
    cells = craft_grid("copper_bar", gd)
    assert min(c.char_level for c in cells) == 1
    assert min(c.skill_level for c in cells) == 0  # max(0, 1-5)
```

- [ ] **Step 2:** verify FAIL (import error). **Step 3: Implement.**

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class CraftCell:
    char_level: int
    skill_name: str
    skill_level: int

def craft_grid(recipe: str, game_data: GameData) -> list[CraftCell]:
    """The level/skill census cells for `recipe` (spec grid): 3 char levels
    (tier-nominal + boundary offsets, clamped [1,50]) x 2 skill levels
    (under-skill L-5 clamped >=0, and at-skill L)."""
    stats = game_data.item_stats(recipe)
    if stats is None or stats.crafting_level is None or stats.crafting_skill is None:
        return []
    craft_level = stats.crafting_level
    skill = stats.crafting_skill
    tier = craft_level // 10 + 1
    nominal = 1 if craft_level <= 9 else 10 * tier
    char_levels = sorted({
        max(1, min(50, lvl))
        for lvl in (nominal, 10 * tier - 2, 10 * tier + 2)
    })
    skill_levels = sorted({max(0, craft_level - 5), craft_level})
    return [CraftCell(cl, skill, sl)
            for cl in char_levels for sl in skill_levels]
```

NOTE: for a T1 recipe the nominal (`1`) and the `10·T±2` offsets (`8`, `12`)
give THREE distinct char levels {1, 8, 12} — the boundary offsets straddle
the T1/T2 line, which is the intended stress (a T1 recipe attempted by a
mid-progression char). The test above pins `min == 1`; add an explicit
assertion of the full `{1, 8, 12}` set so the arithmetic is unambiguous.

- [ ] **Step 4-5:** tests pass → full suite → commit `feat(audit): craft_grid level/skill census cells`.

---

### Task 3: `craft_cell_verdict` — PASS iff plan[0] advances the closure

**Files:** Modify `craft_completeness.py`; Test: extend.

**Interfaces:**
- Consumes: `recipe_closure` (`ai.recipe_closure`), the action classes
  (`GatherAction`/`FightAction`/`NpcBuyAction`/`WithdrawItemAction`/`CraftAction`).
- Produces:
  - `@dataclass(frozen=True) CraftVerdict: passed: bool; reason: str` (`reason` = "" on pass; else "empty" | "wait" | "unrelated:<first_action_repr>").
  - `craft_cell_verdict(recipe: str, plan: list[Action], game_data: GameData) -> CraftVerdict`.

- [ ] **Step 1: Write the failing tests** — one per arm:
  - empty plan → FAIL "empty".
  - `[WaitAction()]` (or the plan's Wait shape — grep `class WaitAction`) → FAIL "wait".
  - plan whose first action is `GatherAction` of a closure material → PASS.
  - plan whose first action is `CraftAction(recipe)` → PASS.
  - plan whose first action is a `FightAction` for a monster dropping a closure leaf → PASS.
  - plan whose first action is unrelated (e.g. a `GatherAction` of a non-closure item, or `RestAction`) → FAIL "unrelated:...".

  (Build the plans directly from action instances; you do NOT need the
  planner here — pass hand-made `[GatherAction(resource_code=...)]` lists.
  Verify each action's item-bearing attribute name from its class:
  `GatherAction.resource_code` → the gathered resource → drop item via
  `game_data.resource_drop_item`; `CraftAction.code`; `NpcBuyAction`/
  `WithdrawItemAction` `.code`; `FightAction.monster_code` → drops via
  `game_data.monster_drops`.)

- [ ] **Step 2-3: Implement.** Compute `closure = recipe_closure(game_data, [recipe])` → `needed_resources ∪ craftable_mats ∪ {recipe}` plus each needed resource's DROP items (a Gather yields the drop item, not the resource code — map via `game_data.resource_drop_item`/`gatherable_drop_items`). The first action ADVANCES the closure iff its produced/target item ∈ that set, OR it is a skill-grind leg toward `stats.crafting_skill` (a Craft/Gather/Fight whose purpose is leveling the craft skill — detect via the action targeting an item whose `crafting_skill == recipe's skill`, or a Fight/Gather flagged skill_grind). Keep the membership test a pure helper `_advances_closure(action, closure_items, skill, game_data) -> bool`.

- [ ] **Step 4-5:** tests pass (each arm) → full suite → commit `feat(audit): craft_cell_verdict — first-leg directional PASS predicate`.

---

### Task 4: `classify_gap` — the 5-way FAIL classifier + wrap

**Files:** Modify `craft_completeness.py`; Test: extend; update the spec Phases with "Phase 1 SHIPPED".

**Interfaces:**
- Consumes: `is_attainable_now` (`ai.tiers.objective`), `recipe_closure`,
  the winnable-monster check.
- Produces:
  - `class GapClass(Enum): PLANNER_BUG; COMBAT_BLOCKED; EVENT_GATED; MATERIAL_UNREACHABLE; SKILL_UNREACHABLE`.
  - `classify_gap(recipe: str, cell: CraftCell, game_data: GameData) -> GapClass` — called only on FAIL cells.

- [ ] **Step 1: Write the failing tests** — one witness per class (pick real bundle recipes; if a class has no clean witness in the bundle, construct a `_FakeGameData`-style minimal catalog like `tests/ai/test_grey_farm.py` does):
  - MATERIAL_UNREACHABLE: a recipe with a leaf that is not gatherable/craftable/drop-winnable/buyable.
  - COMBAT_BLOCKED: a recipe whose leaf drops only from a monster unwinnable at the cell level.
  - EVENT_GATED: a recipe whose leaf drops only from an event-active monster (event not in the audit state).
  - SKILL_UNREACHABLE: a recipe whose craft skill can't be leveled at the cell level.
  - PLANNER_BUG: a recipe whose whole closure IS reachable + skill grindable at the cell, yet (by construction of the test) classified as the residual — the actionable class.

- [ ] **Step 2-3: Implement** the classifier as an ordered cascade over the closure leaves (EVENT_GATED → COMBAT_BLOCKED → MATERIAL_UNREACHABLE → SKILL_UNREACHABLE → else PLANNER_BUG), each check a pure helper reusing the attainability walk. Document the precedence.

- [ ] **Step 4:** full suite 100% + mypy strict.
- [ ] **Step 5:** append to spec Phases: `**Phase 1 SHIPPED**: plan_craft + craft_grid + craft_cell_verdict + classify_gap (pure cores, unit-tested); generator/docs + regression pin + plan --craft are Phase 2-3.` Commit `feat(audit): classify_gap 5-way FAIL classifier; craft-completeness Phase 1`.

---

## Later phases (outline only — planned separately after Phase 1 review)

- **Phase 2 — generator + docs:** `scripts/gen_craft_completeness.py` runs `craft_grid`/`plan_craft`/`craft_cell_verdict`/`classify_gap` over all 321 recipes on the committed bundle; renders `docs/craft_completeness/MATRIX.md` (recipe × cell → PASS/gap, grouped by skill × tier) + `BACKLOG.md` (ranked PLANNER_BUG list) + a SUMMARY line. Offline; ~1900 runs. Surfaces the gap census.
- **Phase 3 — regression pin + CLI:** `tests/test_ai/scenarios/test_craft_completeness.py` pins one representative recipe per (craft-skill × tier) at the at-skill/nominal cell (~30) that MUST PASS (CI-safe); add `plan --craft <item> [--char-level N --skill K]` CLI mode over `plan_craft` for single-recipe interactive debugging.
- **Phase 4 — triage (follow-on backlog):** fix the PLANNER_BUG gaps the census finds, each its own systematic-debug (like GAP-8/GAP-9). Not this spec.

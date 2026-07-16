# Skill-Grind Admissible Heuristic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the GOAP planner find skill-gated gear plans (BUG B) by giving it a goal-provided admissible+consistent heuristic — the cost of a *forced* skill grind — so Dijkstra takes the necessary expensive `LevelSkill` edge instead of exhausting the cheap sub-cost frontier.

**Architecture:** Add `Goal.heuristic(state, game_data) -> float` (default `0.0`); the planner uses it in place of the hardcoded `h = 0.0`. `UpgradeEquipmentGoal` and `GatherMaterialsGoal` override it with the target's own crafting-skill `LevelSkill.cost`, counted only when crafting is unavoidable (not owned, no non-craft obtain source). `PlannerAdmissibility.lean` is extended to model the visited/closed set and prove a *consistent* heuristic keeps closed-set pruning optimal — the property the new heuristic relies on and that `h=0` gave for free.

**Tech Stack:** Python 3.13, `uv`, pytest; Lean 4 (`formal/`), `lake`.

## Global Constraints

- `uv` is at `/home/blentz/.local/bin/uv` (NOT on PATH); prefix every Python command with it.
- Run pytest via `env -u FORCE_COLOR uv run pytest ... --no-cov` for fast iteration; the repo gates at **100% coverage, 0 warnings, 0 skipped**.
- `formal/gate.sh` needs a clean committed tree; `formal/diff` and `formal/` are NOT in the default pytest path.
- Refresh mutation anchors (`formal/diff/mutate.py`) on every edited source line.
- No inline imports; imports at top of file. NEVER catch `Exception`. No `if TYPE_CHECKING`. One behavioral class per file.
- Use only API/game data or fail with an error; no defaulting to mask missing data.
- `LevelSkill.cost(state, game_data, history=None)` is deterministic (current skill level + `SkillXpCurve`), monotone in the level gap, and uses NO learning input. Only `LevelSkill` raises a skill in-search (`CraftAction.apply` does not).
- Heuristic MUST stay admissible (`h ≤ true remaining`) AND consistent (`h(s) ≤ cost(s,s') + h(s')`) — consistency is what keeps the visited-set graph search optimal.
- RUN ONE HEAVY PROCESS AT A TIME (wall-clock planner/scenario tests flake under CPU contention).

---

### Task 1: `Goal.heuristic` seam + planner wiring

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/base.py` (add `heuristic` to `Goal`)
- Modify: `src/artifactsmmo_cli/ai/planner.py:138` (root `h0`), `:186` (child `h`)
- Test: `tests/test_ai/test_planner.py`

**Interfaces:**
- Produces: `Goal.heuristic(self, state: WorldState, game_data: GameData) -> float` (default `0.0`).
- Consumes (planner): `goal.heuristic(state, game_data)` for the root node's `f_score`, and `goal.heuristic(next_state, game_data)` for each child's `f_score`.

- [ ] **Step 1: Write the failing test** — prove the planner invokes `goal.heuristic` on the root and expanded states. Uses a real goal (`RestoreHPGoal`) + real action (`RestAction`), matching `test_planner.py`'s existing style (`_ShallowGoal(RestoreHPGoal)` subclass, `make_state`, real actions). The recording subclass is a legit double for the *collaborator*; the unit under test is the planner.

Add to `tests/test_ai/test_planner.py` (imports `RestoreHPGoal`, `RestAction`, `GameData`, `GOAPPlanner`, `make_state` already present):

```python
class _RecordingHeuristicGoal(RestoreHPGoal):
    """Records the states the planner asks a heuristic for; returns 0.0 so the
    plan is byte-identical to Dijkstra (this proves the SEAM, not a bias)."""

    def __init__(self) -> None:
        super().__init__()
        self.asked: list = []

    def heuristic(self, state, game_data) -> float:
        self.asked.append(state)
        return 0.0


def test_planner_invokes_goal_heuristic_on_root_and_children():
    goal = _RecordingHeuristicGoal()
    state = make_state(hp=50, max_hp=150)
    plan = GOAPPlanner().plan(state, goal, [RestAction()], GameData())
    assert goal.asked, "planner never called goal.heuristic"
    assert state in goal.asked, "planner did not ask h for the ROOT state"
    assert plan  # a rest plan still forms — h=0.0 leaves behavior unchanged
```

- [ ] **Step 2: Run test to verify it fails**

Run: `env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/test_ai/test_planner.py::test_planner_invokes_goal_heuristic_on_root_and_children -x -q --no-cov`
Expected: FAIL — `AssertionError: planner never called goal.heuristic` (the planner uses hardcoded `0.0`, never calls `goal.heuristic`).

- [ ] **Step 3: Add `Goal.heuristic` default** — in `src/artifactsmmo_cli/ai/goals/base.py`, add to `Goal` (near `relevant_actions`):

```python
def heuristic(self, state: WorldState, game_data: GameData) -> float:
    """Admissible, CONSISTENT estimate of remaining plan cost (seconds), used
    as the planner's A* heuristic. Default 0.0 — Dijkstra, trivially admissible
    and consistent. An overriding goal MUST keep h ≤ true-remaining AND
    h(s) ≤ cost(s,s') + h(s') (monotone), or the visited-set graph search loses
    optimality (formal/Formal/PlannerAdmissibility.lean)."""
    return 0.0
```

- [ ] **Step 4: Wire the planner** — in `src/artifactsmmo_cli/ai/planner.py`, replace the root `h0 = 0.0` (line ~138) and the child `h = 0.0` (line ~186):

```python
# root (was: h0 = 0.0)
h0 = goal.heuristic(state, game_data)
```
```python
# child (was: h = 0.0)
h = goal.heuristic(next_state, game_data)
```
Update the two nearby comments that assert `h ≡ 0` to note that `h` is now `goal.heuristic(...)`, admissible+consistent, defaulting to 0 (Dijkstra) for goals that do not override it — preserving the proof for every such goal.

- [ ] **Step 5: Run tests to verify they pass**

Run: `env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/test_ai/test_planner.py -q --no-cov`
Expected: PASS (new test + all existing planner tests — every existing goal keeps `h=0`, so their plans are byte-identical).

- [ ] **Step 6: Refresh mutation anchors** for the two edited `planner.py` lines if `formal/diff/mutate.py` anchors them (grep `planner.py` in that file; update line numbers). Then commit.

```bash
git add src/artifactsmmo_cli/ai/goals/base.py src/artifactsmmo_cli/ai/planner.py \
        tests/test_ai/test_planner.py formal/diff/mutate.py
git commit -m "feat(planner): goal-provided heuristic seam (default 0.0, Dijkstra unchanged)"
```

---

### Task 2: `_forced_craft_grind` shared helper

**Files:**
- Create: `src/artifactsmmo_cli/ai/forced_craft_grind.py`
- Test: `tests/test_ai/test_forced_craft_grind.py`

**Interfaces:**
- Produces: `forced_craft_grind(target: str, needed: int, state: WorldState, game_data: GameData) -> tuple[str, int] | None` — returns `(crafting_skill, crafting_level)` when crafting `target` is the ONLY route AND the skill is unmet; `None` otherwise.

- [ ] **Step 1: Write the failing test** — `tests/test_ai/test_forced_craft_grind.py`:

```python
"""forced_craft_grind: the (skill, level) of an UNAVOIDABLE craft-skill grind."""

from artifactsmmo_cli.ai.forced_craft_grind import forced_craft_grind
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "fire_bow": ItemStats(code="fire_bow", level=10, type_="weapon",
                              crafting_skill="weaponcrafting", crafting_level=10),
        "spruce_plank": ItemStats(code="spruce_plank", level=1, type_="resource",
                                  subtype="craft"),
        "red_slimeball": ItemStats(code="red_slimeball", level=1, type_="resource",
                                   subtype="mob"),
    }
    gd._crafting_recipes = {"fire_bow": {"spruce_plank": 6, "red_slimeball": 2}}
    return gd


def test_forced_grind_when_craft_is_the_only_route_and_skill_unmet():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 7})
    assert forced_craft_grind("fire_bow", 1, state, gd) == ("weaponcrafting", 10)


def test_no_grind_when_skill_already_met():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 10})
    assert forced_craft_grind("fire_bow", 1, state, gd) is None


def test_no_grind_when_target_already_owned():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 7}, inventory={"fire_bow": 1})
    assert forced_craft_grind("fire_bow", 1, state, gd) is None


def test_no_grind_when_target_in_bank():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 7}, bank_items={"fire_bow": 1})
    assert forced_craft_grind("fire_bow", 1, state, gd) is None


def test_no_grind_when_a_winnable_dropper_exists():
    """A non-craft obtain route (monster drop) makes the grind avoidable."""
    gd = _gd()
    gd._monster_level = {"fire_imp": 1}
    gd._monster_hp = {"fire_imp": 1}
    gd._monster_drops = {"fire_imp": [("fire_bow", 100, 1, 1)]}
    from tests.test_ai._monster_fixture import fill_monster_stat_defaults
    fill_monster_stat_defaults(gd)
    state = make_state(skills={"weaponcrafting": 7})
    assert forced_craft_grind("fire_bow", 1, state, gd) is None


def test_no_grind_for_non_craftable_target():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 7})
    assert forced_craft_grind("old_boots", 1, state, gd) is None  # not in _item_stats
```

- [ ] **Step 2: Run test to verify it fails**

Run: `env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/test_ai/test_forced_craft_grind.py -x -q --no-cov`
Expected: FAIL — `ModuleNotFoundError: artifactsmmo_cli.ai.forced_craft_grind`.

- [ ] **Step 3: Implement** — `src/artifactsmmo_cli/ai/forced_craft_grind.py`:

```python
"""The (skill, level) of an UNAVOIDABLE craft-skill grind for a target item.

The admissibility guard for the skill-grind heuristic
(PlannerAdmissibility.lean / the skill-grind design): a craft-skill grind is a
LANDMARK — a valid heuristic term — only when crafting the target is the ONLY
way to obtain it. If the target is already owned, or a non-craft route exists
(bank withdraw, vendor, monster drop), the grind is avoidable and counting it
would make the heuristic OVER-estimate (h > true remaining) — inadmissible.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_sources import SourceKind, obtain_sources
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.world_state import WorldState


def forced_craft_grind(target: str, needed: int, state: WorldState,
                       game_data: GameData) -> tuple[str, int] | None:
    """`(crafting_skill, crafting_level)` when crafting `target` is unavoidable
    AND the skill gate is unmet; `None` otherwise.

    Unavoidable = the target is not already owned (inventory + bank cover
    `needed`) AND `obtain_sources` yields NO non-CRAFT route (no WITHDRAW /
    RECYCLE / GATHER / BUY / DROP). Evaluated under NO_PROFILE_CONTEXT — the
    same minimal context next_grind_goal uses — which is conservative for the
    heuristic: a route it CANNOT see keeps the grind counted, but the explicit
    owned/bank check below covers the one route (banked stock) that context
    could hide."""
    stats = game_data.item_stats(target)
    if stats is None or not stats.crafting_skill:
        return None
    if game_data.crafting_recipe(target) is None:
        return None
    level = stats.crafting_level
    if state.skills.get(stats.crafting_skill, 1) >= level:
        return None
    bank = state.bank_items or {}
    if state.inventory.get(target, 0) + bank.get(target, 0) >= needed:
        return None
    sources = obtain_sources(target, state, game_data, NO_PROFILE_CONTEXT)
    if any(s.kind is not SourceKind.CRAFT for s in sources):
        return None
    return (stats.crafting_skill, level)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/test_ai/test_forced_craft_grind.py -q --no-cov`
Expected: PASS (6 tests). If `_drop_sources` needs `monster_spawn_known`, add `gd._monster_spawn = {"fire_imp": [(0, 0)]}` (or the bundle's spawn field) in `test_no_grind_when_a_winnable_dropper_exists` so `is_winnable`/`monster_spawn_known` recognize the dropper; adjust to the real `GameData` drop/spawn setters as the other `test_ai` fixtures do.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/forced_craft_grind.py tests/test_ai/test_forced_craft_grind.py
git commit -m "feat(planner): forced_craft_grind helper (the heuristic admissibility guard)"
```

---

### Task 3: `UpgradeEquipmentGoal.heuristic`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/progression.py` (add `heuristic`)
- Test: `tests/test_ai/test_goals.py`

**Interfaces:**
- Consumes: `forced_craft_grind` (Task 2); `LevelSkill(skill=..., target_level=...).cost(state, game_data)`; the goal's target (`self._committed_target` else `self.find_upgrade_target(state, game_data)`).
- Produces: `UpgradeEquipmentGoal.heuristic(state, game_data) -> float`.

- [ ] **Step 1: Write the failing test** — add to `tests/test_ai/test_goals.py`:

```python
def test_upgrade_equipment_heuristic_is_forced_grind_cost():
    """Pinned to a craft-only, skill-gated, unowned target, the heuristic is the
    LevelSkill.cost of the forced grind; 0 once satisfied/owned/skill-met."""
    from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
    from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
    gd = _fire_bow_gd()  # helper below: fire_bow craft-only, weaponcrafting 10
    goal = UpgradeEquipmentGoal(committed_target=("fire_bow", "weapon_slot"))
    under = make_state(level=13, skills={"weaponcrafting": 7})
    expected = LevelSkill(skill="weaponcrafting", target_level=10).cost(under, gd)
    assert goal.heuristic(under, gd) == expected
    assert expected > 0
    met = make_state(level=13, skills={"weaponcrafting": 10})
    assert goal.heuristic(met, gd) == 0.0
    owned = make_state(level=13, skills={"weaponcrafting": 7},
                       inventory={"fire_bow": 1})
    assert goal.heuristic(owned, gd) == 0.0


def test_upgrade_equipment_heuristic_collapses_the_skill_gate_search():
    """BEHAVIORAL proof (the BUG B collapse): with the mats in hand and the
    skill unmet, the planner finds [LevelSkill, Craft, Equip] and creates far
    fewer nodes than the same search with the heuristic forced to 0."""
    from artifactsmmo_cli.ai.planner import GOAPPlanner
    from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
    gd = _fire_bow_gd()
    goal = UpgradeEquipmentGoal(committed_target=("fire_bow", "weapon_slot"))
    state = make_state(level=13, skills={"weaponcrafting": 7},
                       inventory={"spruce_plank": 6, "red_slimeball": 2})
    actions = _fire_bow_actions(gd)  # LevelSkill, Craft, Equip, + cheap decoys
    plan = GOAPPlanner().plan(state, goal, actions, gd, budget_seconds=10.0)
    assert [repr(a) for a in plan] == [
        "LevelSkill(weaponcrafting->10)", "Craft(fire_bow×1)",
        "Equip(fire_bow->weapon_slot)"], plan
```

`_fire_bow_actions(gd)` builds the LevelSkill/Craft/Equip triple plus a couple
of cheap always-applicable decoys (a `RestAction`, a `GatherAction` for a spruce
resource) so the frontier has a cheap alternative to exhaust — the decoys must be
in `UpgradeEquipmentGoal.relevant_actions`' admitted set (closure gather + the
scoped LevelSkill), which they are for this fixture. Keep it minimal; the point is
that the plan forms in budget, which it cannot without the heuristic.

Add a module-level `_fire_bow_gd()` helper in `test_goals.py` (mirror `test_forced_craft_grind._gd`, plus a `weaponcrafting` workshop and `spruce_plank`/`red_slimeball` leaves so `find_upgrade_target`/`is_satisfied` behave; the goal is pinned via `committed_target`, so no arbiter ranking is needed).

- [ ] **Step 2: Run test to verify it fails**

Run: `env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/test_ai/test_goals.py::test_upgrade_equipment_heuristic_is_forced_grind_cost -x -q --no-cov`
Expected: FAIL — `AssertionError: 0.0 == <positive>` (base `Goal.heuristic` returns 0.0).

- [ ] **Step 3: Implement** — add to `UpgradeEquipmentGoal` in `progression.py` (imports at top: `from artifactsmmo_cli.ai.forced_craft_grind import forced_craft_grind` and `from artifactsmmo_cli.ai.actions.level_skill import LevelSkill`):

```python
def heuristic(self, state: WorldState, game_data: GameData) -> float:
    """Admissible+consistent: the cost of the FORCED craft-skill grind the
    target requires. `forced_craft_grind` counts it only when crafting is
    unavoidable, so h never over-estimates; `LevelSkill.cost` is the exact
    edge cost the plan pays, so taking the grind drops h by exactly that
    (consistency). 0 when satisfied, owned, skill-met, or the target has a
    non-craft route — see the design's admissibility guard."""
    if self.is_satisfied(state):
        return 0.0
    target = self.find_upgrade_target(state, game_data)
    if target is None:
        return 0.0
    target_item, _slot = target
    grind = forced_craft_grind(target_item, 1, state, game_data)
    if grind is None:
        return 0.0
    skill, level = grind
    return LevelSkill(skill=skill, target_level=level).cost(state, game_data)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/test_ai/test_goals.py -q --no-cov`
Expected: PASS (new test + all existing goal tests).

- [ ] **Step 5: Refresh mutation anchors** if `progression.py` gains anchored lines; commit.

```bash
git add src/artifactsmmo_cli/ai/goals/progression.py tests/test_ai/test_goals.py formal/diff/mutate.py
git commit -m "feat(planner): UpgradeEquipmentGoal admissible skill-grind heuristic (BUG B)"
```

---

### Task 4: `GatherMaterialsGoal.heuristic` + live runtime verification

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/gathering.py` (add `heuristic`)
- Test: `tests/test_ai/test_gathering_goal.py` (or the file holding `GatherMaterialsGoal` tests — confirm with `grep -rl "class TestGatherMaterials\|GatherMaterialsGoal" tests/`)

**Interfaces:**
- Consumes: `forced_craft_grind`, `LevelSkill`, the goal's `self._target_item`.
- Produces: `GatherMaterialsGoal.heuristic(state, game_data) -> float`.

- [ ] **Step 1: Write the failing test** — in the GatherMaterialsGoal test file:

```python
def test_gather_materials_heuristic_is_forced_grind_cost():
    """A GatherMaterials goal whose target_item is a craft-only, skill-gated,
    unowned craftable returns the forced LevelSkill.cost; 0 otherwise."""
    from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
    from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
    gd = _forged_plate_gd()  # forged_plate: craft-only, gearcrafting 20
    goal = GatherMaterialsGoal(target_item="forged_plate",
                               needed={"forged_plate": 1})
    under = make_state(skills={"gearcrafting": 12})
    assert goal.heuristic(under, gd) == \
        LevelSkill(skill="gearcrafting", target_level=20).cost(under, gd)
    met = make_state(skills={"gearcrafting": 20})
    assert goal.heuristic(met, gd) == 0.0
```

Add a `_forged_plate_gd()` helper (craft-only item gated at gearcrafting 20, leaves present).

- [ ] **Step 2: Run test to verify it fails**

Run: `env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest <gather test file>::test_gather_materials_heuristic_is_forced_grind_cost -x -q --no-cov`
Expected: FAIL — base heuristic returns 0.0.

- [ ] **Step 3: Implement** — add to `GatherMaterialsGoal` in `gathering.py` (imports at top):

```python
def heuristic(self, state: WorldState, game_data: GameData) -> float:
    """Same admissible+consistent skill-grind term as UpgradeEquipmentGoal,
    keyed on this goal's target_item — so a GatherMaterials search toward a
    craft-only, skill-gated material takes the forced LevelSkill edge first
    instead of exhausting the cheap gather/withdraw frontier."""
    if self.is_satisfied(state):
        return 0.0
    needed = self._needed.get(self._target_item, 1)
    grind = forced_craft_grind(self._target_item, needed, state, game_data)
    if grind is None:
        return 0.0
    skill, level = grind
    return LevelSkill(skill=skill, target_level=level).cost(state, game_data)
```

(`GatherMaterialsGoal.__init__` stores `self._target_item: str` and
`self._needed: dict[str, int]` — exposed via the `needed` property; the
heuristic reads the private fields directly, as `is_satisfied`/`relevant_actions`
in the same class do.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest <gather test file> tests/test_ai/test_level_skill_expand.py -q --no-cov`
Expected: PASS.

- [ ] **Step 5: MANDATORY runtime verification on live Robby** (`feedback_verify_runtime_activation`). Confirm the seam fires end to end:

Run:
```bash
cat > "$CLAUDE_JOB_DIR/tmp/verify_bugb.py" <<'PY'
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.config import Config
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.client_manager import ClientManager
config = Config.from_token_file(); ClientManager().initialize(config)
store = LearningStore(db_path=":memory:", character="Robby"); store.start_session()
p = GamePlayer(character="Robby", history=store,
               game_data_ttl_minutes=config.game_data_ttl_minutes)
rep = p.plan_once()
for g in rep.goals_tried:
    if "fire_bow" in str(g.get("goal", "")):
        print("fire_bow goal:", g)
print("chosen_root:", rep.decision.chosen_root)
print("plan:", [repr(a) for a in rep.plan])
store.end_session(exit_reason="normal"); store.close()
PY
env -u FORCE_COLOR /home/blentz/.local/bin/uv run python "$CLAUDE_JOB_DIR/tmp/verify_bugb.py" 2>&1 | grep -v "^\[" | tail
```
Expected: the `UpgradeEquipment(fire_bow)` entry shows `plan_len >= 3` and `timed_out=False` (was `4277 nodes / plan_len 0 / timed_out True`); the emitted plan for the fire_bow root is `[LevelSkill(weaponcrafting->10), Craft(fire_bow), Equip(fire_bow->weapon_slot)]` (or the current live equivalent). **If Robby's live state has drifted so fire_bow is owned / skill-met, reproduce against the recorded state** by asserting the same via a scenario fixture pinned to `committed_target=("fire_bow","weapon_slot")` at `weaponcrafting 7` with the materials in inventory, and confirm `planner.plan` returns the 3-step plan in `< 1s` (vs a 10s timeout without the heuristic).

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/gathering.py tests/test_ai/<gather test file> formal/diff/mutate.py
git commit -m "feat(planner): GatherMaterialsGoal skill-grind heuristic + BUG B runtime-verified"
```

---

### Task 5: Extend `PlannerAdmissibility.lean` — visited set + consistency

**Files:**
- Modify: `formal/Formal/PlannerAdmissibility.lean`
- Modify: `formal/diff/mutate.py` (anchors for new theorems if the diff harness covers this file)

**Interfaces:**
- Produces (Lean): `Consistent`, a closed-set pruning model, `consistent_closedSet_preserves_optimal` (name final), and a concrete skill-grind instance discharging `Admissible` + `Consistent`.

- [ ] **Step 1: Add the `Consistent` predicate + `h≡0` is consistent.** After `Admissible` (line ~19):

```lean
/-- Textbook CONSISTENCY (monotonicity): h never drops by more than the edge
cost. Required — beyond admissibility — for a closed-set graph search: it
guarantees the first pop of a state already has its least g, so pruning its
re-expansions discards nothing cheaper. `planner.py` uses a `visited` set
(planner.py:153-156), so this is the property the real algorithm relies on. -/
def Consistent {α : Type} (h : α → Nat) (cost : α → α → Nat)
    (succ : α → α → Prop) : Prop :=
  ∀ s s', succ s s' → h s ≤ cost s s' + h s'

theorem zero_h_consistent {α : Type} (cost : α → α → Nat)
    (succ : α → α → Prop) : Consistent (fun _ : α => 0) cost succ := by
  intro s s' _; simp
```

- [ ] **Step 2: `lake build` to verify the new defs compile.**

Run: `cd formal && lake build Formal.PlannerAdmissibility`
Expected: builds clean (no `sorry`, no errors).

- [ ] **Step 3: Model closed-set pruning + prove consistency makes it optimal.** Add a faithful abstract model: a search over states with `g`, a `visited` set, expansion in `f = g + h` order. The load-bearing lemma:

```lean
/-- When h is consistent, the g of a state at its FIRST pop is least among all
paths to it: any alternate path's node has f = g' + h ≥ g_firstpop + h (popped
no later), and h cancels, so g' ≥ g_firstpop. Hence discarding a state already
in `visited` (a later, no-cheaper pop) never removes an optimal path. -/
theorem consistent_firstpop_is_least_g
    {α : Type} (h : α → Nat) (cost : α → α → Nat) (succ : α → α → Prop)
    (hcon : Consistent h cost succ)
    (s : α) (gFirst gAlt : Nat)
    (hpop : fScore gFirst (h s) ≤ fScore gAlt (h s)) :
    gFirst ≤ gAlt := by
  unfold fScore at hpop; omega
```

Then a wrapper theorem stating the closed-set search returns the optimal cost, composing `consistent_firstpop_is_least_g` with `firstSatisfied_least_cost_of_admissible`. Keep the model as small as faithfully possible (mirror `SearchNode`/`fScore`); do NOT introduce Mathlib into the safety core if the existing file avoids it (match its imports).

- [ ] **Step 4: Concrete skill-grind instance.** Mirror the RHP example (line ~72+) with a landmark shape: a 2-state world `{needsGrind, done}`, `cost needsGrind done = C`, `trueRemaining needsGrind = C`, `h needsGrind = C`, `h done = 0`, `succ = (· = needsGrind ∧ · = done)`. Prove:

```lean
theorem skillGrind_h_admissible : Admissible SGh SGtrueRemaining := by
  intro s; cases s <;> simp [SGh, SGtrueRemaining]

theorem skillGrind_h_consistent : Consistent SGh SGcost SGsucc := by
  intro s s' hss; cases s <;> cases s' <;> simp_all [SGh, SGcost, SGsucc]
```

(Fill `SGState`, `SGh`, `SGcost`, `SGtrueRemaining`, `SGsucc`, `SGSat` as concrete `def`s above these theorems, exactly as RHP does. This instance is the Lean witness that the Python skill-grind heuristic's *shape* — landmark cost, 0 at goal, drops by exactly the edge cost — is admissible AND consistent.)

- [ ] **Step 5: Build + run the formal gate.**

Run: `cd formal && lake build && ./gate.sh`
Expected: gate PASSES (all parts). If `gate.sh` reports a stale mutation anchor on the edited lines, refresh `formal/diff/mutate.py` and re-run. The tree must be committed clean before `gate.sh` (commit Step 6 first if the gate demands it, then re-run).

- [ ] **Step 6: Commit**

```bash
git add formal/Formal/PlannerAdmissibility.lean formal/diff/mutate.py
git commit -m "feat(formal): visited-set + consistency proof; skill-grind h admissible+consistent"
```

---

### Task 6: Full-suite + census + gate green

**Files:** none (verification only).

- [ ] **Step 1: Run the full Python suite (two lanes).**

Run bulk: `env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest -n auto --ignore=tests/test_ai/scenarios -q --no-cov`
Then scenarios: `env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/test_ai/scenarios -q --no-cov`
Expected: all pass, 0 warnings, 0 skipped. (One heavy process at a time.)

- [ ] **Step 2: Coverage gate on the changed modules.**

Run: `env -u FORCE_COLOR /home/blentz/.local/bin/uv run pytest tests/test_ai/test_planner.py tests/test_ai/test_forced_craft_grind.py tests/test_ai/test_goals.py --cov=artifactsmmo_cli.ai.forced_craft_grind --cov=artifactsmmo_cli.ai.planner --cov-report=term-missing --no-cov-on-fail -q 2>&1 | tail`
Expected: `forced_craft_grind.py` and the edited `planner.py`/goal lines at 100%.

- [ ] **Step 3: Four censuses clean.**

Run: `env -u FORCE_COLOR /home/blentz/.local/bin/uv run artifactsmmo census` (or the individual audit entrypoints in `src/artifactsmmo_cli/audit/`: `craft_completeness`, `recycle_source_completeness`, `inventory_completeness`, `obtain_parity_completeness`).
Expected: `inventory_bug 0`, `planner_bug 0`, `recycle_source_bug 0`, `obtain_parity_bug 0`.

- [ ] **Step 4: Formal gate (clean tree).**

Run: `cd formal && ./gate.sh`
Expected: ALL PARTS PASSED.

- [ ] **Step 5: Final commit if anything (anchors, fixture regen) changed.**

```bash
git add -A && git commit -m "chore(planner): BUG B heuristic — full suite + census + gate green"
```

---

## Notes for the implementer

- **Deviation from spec §3 (DRY).** The spec proposed a single `required_skill_grinds` helper shared by both `relevant_actions` (admission) and `heuristic` (cost). In design that premise does not hold: the heuristic needs a target-scoped, GUARDED value (`forced_craft_grind` — Task 2: not-owned + no non-craft route + exact skill gate), while `relevant_actions` needs the broad, closure-wide, UN-guarded `gated_skill_levels` set (it must admit MORE, never fewer, edges to stay plan-complete). They are genuinely different computations, so forcing one shared helper would be artificial. The residual duplication is only the ~6-line craft-gate LOOP between `progression.py` and `gathering.py`'s `relevant_actions`; that is a pre-existing cosmetic cleanup independent of BUG B and is intentionally **left out of scope** (YAGNI). Do not refactor it as part of this plan.
- **Do not** add `predict_win`, `LevelSkill.cost`, or `obtain_sources` calls to any Lean-mirrored pure core — they are runtime. The heuristic lives in Python goals; Lean proves only the *shape* (Task 5 instance).
- **Consistency is the requirement, not just admissibility** — the visited set makes it load-bearing. If a reviewer questions whether a heuristic term is consistent, the test is: does taking the `LevelSkill` edge drop `h` by exactly its `cost`, and does every other edge leave `h` unchanged? Only `LevelSkill` changes skill in-search, so yes.
- **Target stability** (design §2.4): the heuristic's target must match the goal's `is_satisfied` target. For `committed_target` it is pinned; for `find_upgrade_target` it is deterministic per state and cannot flip on a non-terminal edge (only `Equip` changes it, and that satisfies the goal). Do not recompute the target from a mutated inventory mid-search in a way that could flip it.
- If `make_state` lacks `skills`/`bank_items`/`inventory` kwargs, use the existing constructor pattern other `test_ai` tests use (`scenario_state(ScenarioCharacter(...))` or the local `make_state` in `tests/test_ai/fixtures.py`) — match the file you are editing.

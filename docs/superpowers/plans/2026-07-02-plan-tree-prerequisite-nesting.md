# Plan-Tree Prerequisite Nesting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the plan screen's flat recipe-closure flowchart with an interactive collapsible Textual tree of the chosen objective's full prerequisite nesting — skill-gate sub-goals, material sub-tasks down to raw gathers, and the current grind step.

**Architecture:** A pure builder (`build_plan_tree`) recurses the existing `prerequisites()` graph for the chosen strategy root into a frozen `PlanTreeNode` tree serialized onto `CycleSnapshot`; a new `PlanTree(Tree)` widget renders it with per-node status glyphs and key-based expansion memory. The old `build_plan_summary` flowchart body and its `[`/`]` alternatives pagination are retired.

**Tech Stack:** Python 3.13, `uv`, pydantic (frozen value models), Textual `Tree` widget, rich `Text`, pytest.

## Global Constraints

- Prefix every Python command with `uv run` (e.g. `uv run pytest`, `uv run mypy`).
- Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- No inline imports — all imports at top of file.
- One behavioral class per file; cohesive pydantic schema groups may share a module (`cycle_snapshot.py`).
- Never catch `Exception`; guard with explicit `is None` / membership checks.
- No `if TYPE_CHECKING`. Absolute imports only (never `...`).
- Only API/game data or fail with an error — no defaulting to fake values.
- Tests use real fixtures (no mocking the unit under test); put all tests in `tests/`.

---

### Task 1: `PlanTreeNode` model + `build_plan_tree` pure builder

**Files:**
- Modify: `src/artifactsmmo_cli/ai/cycle_snapshot.py` (add `PlanTreeNode` to the schema group + `ConfigDict` import)
- Create: `src/artifactsmmo_cli/ai/plan_tree.py`
- Test: `tests/test_ai/test_plan_tree.py`

**Interfaces:**
- Produces: `PlanTreeNode(BaseModel, frozen)` with fields `key: str`, `label: str`, `kind: str` (`obtain|skill|charlevel|step|root_stub`), `status: str` (`met|unmet|current`), `detail: str = ""`, `children: tuple[PlanTreeNode, ...] = ()`.
- Produces: `build_plan_tree(decision: StrategyDecision, state: WorldState, game_data: GameData, serve_step: str | None) -> tuple[PlanTreeNode, ...]`.
- Consumes: `prerequisites()` (prerequisite_graph), `StrategyDecision`/`RootScore` (strategy), `MetaGoal`/`ObtainItem`/`ReachSkillLevel`/`ReachCharLevel` (meta_goal), `short_root` (plan_format).

- [ ] **Step 1: Add `PlanTreeNode` to `cycle_snapshot.py`**

At the top, extend the pydantic import:
```python
from pydantic import BaseModel, ConfigDict, Field
```
Add this model above `CycleSnapshot` (after `GoalAttempt`):
```python
class PlanTreeNode(BaseModel):
    """One node in the chosen objective's prerequisite tree (TUI plan screen).

    Frozen recursive value object. `kind` drives the glyph; `status` drives the
    style. `root_stub` nodes are the non-chosen ranked roots (no children).
    """

    model_config = ConfigDict(frozen=True)

    key: str                    # stable id for expansion memory (usually repr(node))
    label: str
    kind: str                   # obtain | skill | charlevel | step | root_stub
    status: str                 # met | unmet | current
    detail: str = ""
    children: tuple["PlanTreeNode", ...] = ()
```

- [ ] **Step 2: Write the failing test file** `tests/test_ai/test_plan_tree.py`

```python
from fractions import Fraction

from artifactsmmo_cli.ai.cycle_snapshot import PlanTreeNode
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.plan_tree import build_plan_tree
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.strategy import RootScore, StrategyDecision
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "life_amulet": ItemStats(code="life_amulet", level=5, type_="amulet",
                                 crafting_skill="jewelrycrafting", crafting_level=5),
        "golden_ring": ItemStats(code="golden_ring", level=3, type_="ring",
                                 crafting_skill="jewelrycrafting", crafting_level=3),
        "topaz": ItemStats(code="topaz", level=1, type_="resource"),
    }
    gd._crafting_recipes = {
        "life_amulet": {"golden_ring": 1, "topaz": 2},
        "golden_ring": {"topaz": 4},
    }
    gd._resource_drops = {}
    gd._resource_skill = {}
    return gd


def _decision(chosen, step, ranking):
    return StrategyDecision(interrupt=None, chosen_root=chosen, chosen_step=step,
                            desired_state={}, ranking=ranking)


def _rs(node, score, category="gear"):
    return RootScore(root_repr=repr(node), category=category,
                     contribution=Fraction(0), cost=0, score=Fraction(score), step_repr="")


def test_chosen_expands_skill_gate_and_materials():
    gd = _gd()
    state = make_state(skills={"jewelrycrafting": 1}, equipment={"amulet_slot": None})
    chosen = ObtainItem("life_amulet")
    step = ReachSkillLevel("jewelrycrafting", 5)
    tree = build_plan_tree(_decision(chosen, step, [_rs(chosen, 2)]), state, gd, None)

    assert len(tree) == 1                      # only the chosen root (no other ranked roots)
    root = tree[0]
    assert root.kind == "obtain" and root.label == "life_amulet" and root.status == "unmet"
    kinds = {c.label: c for c in root.children}
    assert "jewelrycrafting → 5" in kinds
    assert kinds["jewelrycrafting → 5"].status == "current"     # == chosen_step
    assert kinds["golden_ring"].status == "unmet"
    assert kinds["topaz ×2"].status == "unmet"


def test_current_step_gets_synthetic_serve_child():
    gd = _gd()
    state = make_state(skills={"jewelrycrafting": 1})
    chosen = ObtainItem("life_amulet")
    step = ReachSkillLevel("jewelrycrafting", 5)
    tree = build_plan_tree(_decision(chosen, step, [_rs(chosen, 2)]), state, gd,
                           "LevelSkill: craft copper_ring")
    skill = next(c for c in tree[0].children if c.label == "jewelrycrafting → 5")
    steps = [c for c in skill.children if c.kind == "step"]
    assert len(steps) == 1
    assert steps[0].label == "LevelSkill: craft copper_ring"
    assert steps[0].status == "current"


def test_no_serve_child_when_serve_step_none():
    gd = _gd()
    state = make_state(skills={"jewelrycrafting": 1})
    chosen = ObtainItem("life_amulet")
    step = ReachSkillLevel("jewelrycrafting", 5)
    tree = build_plan_tree(_decision(chosen, step, [_rs(chosen, 2)]), state, gd, None)
    skill = next(c for c in tree[0].children if c.label == "jewelrycrafting → 5")
    assert [c for c in skill.children if c.kind == "step"] == []


def test_recurses_material_subtree_to_raw_leaf():
    gd = _gd()
    state = make_state(skills={"jewelrycrafting": 1})
    chosen = ObtainItem("life_amulet")
    tree = build_plan_tree(_decision(chosen, None, [_rs(chosen, 2)]), state, gd, None)
    ring = next(c for c in tree[0].children if c.label == "golden_ring")
    assert any(c.label == "jewelrycrafting → 3" for c in ring.children)   # ring's own skill gate
    topaz = next(c for c in ring.children if c.label == "topaz ×4")
    assert topaz.children == ()                                           # raw resource → leaf


def test_met_material_marked_met():
    gd = _gd()
    # topaz owned enough at the amulet level: 2 needed, hold 2 -> met leaf
    state = make_state(skills={"jewelrycrafting": 1}, inventory={"topaz": 2})
    chosen = ObtainItem("life_amulet")
    tree = build_plan_tree(_decision(chosen, None, [_rs(chosen, 2)]), state, gd, None)
    topaz = next(c for c in tree[0].children if c.label == "topaz ×2")
    assert topaz.status == "met"


def test_non_chosen_roots_are_leaf_stubs():
    gd = _gd()
    state = make_state(skills={"jewelrycrafting": 1})
    chosen = ObtainItem("life_amulet")
    other = ObtainItem("golden_ring")
    ranking = [_rs(chosen, 2, "gear"), _rs(other, 1, "gear")]
    tree = build_plan_tree(_decision(chosen, None, ranking), state, gd, None)
    assert len(tree) == 2
    stub = tree[1]
    assert stub.kind == "root_stub" and stub.children == ()
    assert stub.label == "golden_ring" and "1.00" in stub.detail


def test_chosen_root_none_returns_empty():
    gd = _gd()
    tree = build_plan_tree(_decision(None, None, []), make_state(), gd, None)
    assert tree == ()


def test_cycle_and_depth_bounded():
    # A self-referential recipe would recurse forever without the visited-set.
    gd = _gd()
    gd._crafting_recipes = {"loop_item": {"loop_item": 1}}
    gd._item_stats = {"loop_item": ItemStats(code="loop_item", level=1, type_="resource")}
    state = make_state()
    chosen = ObtainItem("loop_item")
    tree = build_plan_tree(_decision(chosen, None, [_rs(chosen, 1)]), state, gd, None)
    # terminates; the repeated node becomes a leaf via the visited-set
    assert tree[0].label == "loop_item"
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_plan_tree.py -q`
Expected: FAIL — `ModuleNotFoundError: artifactsmmo_cli.ai.plan_tree`.

- [ ] **Step 4: Create** `src/artifactsmmo_cli/ai/plan_tree.py`

```python
"""Pure builder: the chosen strategy root's prerequisite tree for the TUI plan
screen. Recurses prerequisites() (skill gates + materials down to raw gathers);
non-chosen ranked roots are leaf stubs; the current step gets a synthetic serve
child sourced from the running goal + action. No planning or I/O."""

from artifactsmmo_cli.ai.cycle_snapshot import PlanTreeNode
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.prerequisite_graph import prerequisites
from artifactsmmo_cli.ai.tiers.strategy import StrategyDecision
from artifactsmmo_cli.ai.world_state import WorldState
from artifactsmmo_cli.tui.plan_format import short_root

# Matches UpgradeEquipmentGoal.max_depth — a chain longer than this is treated as
# a leaf rather than recursed (defence against a pathological recipe/gate graph).
_DEPTH_CAP = 32


def _label(node: MetaGoal) -> tuple[str, str]:
    """(label, kind) for a meta-goal node."""
    if isinstance(node, ObtainItem):
        qty = "" if node.quantity == 1 else f" ×{node.quantity}"
        return f"{node.code}{qty}", "obtain"
    if isinstance(node, ReachSkillLevel):
        return f"{node.skill} → {node.level}", "skill"
    if isinstance(node, ReachCharLevel):
        return f"character → {node.level}", "charlevel"
    return short_root(repr(node)), "obtain"


def _expand(node: MetaGoal, decision: StrategyDecision, state: WorldState,
            game_data: GameData, serve_step: str | None,
            visited: frozenset[MetaGoal], depth: int) -> PlanTreeNode:
    label, kind = _label(node)
    is_current = node == decision.chosen_step
    status = "current" if is_current else (
        "met" if node.is_satisfied(state, game_data) else "unmet")
    children: list[PlanTreeNode] = []
    if node not in visited and depth < _DEPTH_CAP:
        nxt = visited | {node}
        for prereq in prerequisites(node, state, game_data):
            children.append(
                _expand(prereq, decision, state, game_data, serve_step, nxt, depth + 1))
    if is_current and serve_step:
        children.append(PlanTreeNode(
            key=f"step:{node!r}", label=serve_step, kind="step", status="current"))
    return PlanTreeNode(key=repr(node), label=label, kind=kind, status=status,
                        children=tuple(children))


def build_plan_tree(decision: StrategyDecision, state: WorldState,
                    game_data: GameData, serve_step: str | None) -> tuple[PlanTreeNode, ...]:
    """Chosen root expands its prerequisite subtree; other ranked roots become
    leaf stubs. The current step gains a synthetic serve child. Bounded by a
    visited-set (frozen MetaGoals are hashable) + a depth cap."""
    if decision.chosen_root is None:
        return ()
    roots: list[PlanTreeNode] = [
        _expand(decision.chosen_root, decision, state, game_data, serve_step,
                frozenset(), 0)
    ]
    chosen_repr = repr(decision.chosen_root)
    for i, r in enumerate(decision.ranking):
        if r.root_repr == chosen_repr:
            continue
        roots.append(PlanTreeNode(
            key=r.root_repr, label=short_root(r.root_repr), kind="root_stub",
            status="unmet",
            detail=f"root {i + 1} · {r.category} · {float(r.score):.2f}"))
    return tuple(roots)
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_plan_tree.py -q`
Expected: PASS (8 tests).

- [ ] **Step 6: Typecheck + commit**

Run: `uv run mypy src/artifactsmmo_cli/ai/plan_tree.py src/artifactsmmo_cli/ai/cycle_snapshot.py`
Expected: no errors.
```bash
git add src/artifactsmmo_cli/ai/plan_tree.py src/artifactsmmo_cli/ai/cycle_snapshot.py tests/test_ai/test_plan_tree.py
git commit -m "feat(tui): build_plan_tree — chosen root prerequisite tree for plan screen"
```

---

### Task 2: Serialize `plan_tree` onto the snapshot

**Files:**
- Modify: `src/artifactsmmo_cli/ai/cycle_snapshot.py` (add `plan_tree` field to `CycleSnapshot`)
- Modify: `src/artifactsmmo_cli/ai/player.py:1421-1471` (populate it in the `CycleSnapshot(...)` construction)
- Test: `tests/test_ai/test_plan_tree.py` (add a snapshot round-trip test)

**Interfaces:**
- Consumes: `build_plan_tree` (Task 1), `self._last_decision` (StrategyDecision), `self.state`, `self.game_data`, local `selected_goal_name`, `action_name` (already in the snapshot-emit method).
- Produces: `CycleSnapshot.plan_tree: tuple[PlanTreeNode, ...]`.

- [ ] **Step 1: Add the field to `CycleSnapshot`**

In `cycle_snapshot.py`, under the "Committed strategy root" block:
```python
    # Committed strategy root + ranking + bank, for the TUI plan screen.
    chosen_root: str | None = None
    strategy_ranking: list[RootScoreView] = Field(default_factory=list)
    bank_items: dict[str, int] | None = None
    plan_tree: tuple[PlanTreeNode, ...] = ()
```

- [ ] **Step 2: Write the failing round-trip test** (append to `tests/test_ai/test_plan_tree.py`)

```python
from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot


def test_snapshot_carries_plan_tree():
    node = PlanTreeNode(key="k", label="life_amulet", kind="obtain", status="unmet")
    snap = CycleSnapshot(cycle_index=1, timestamp="t", character="hero",
                         x=0, y=0, level=1, xp=0, max_xp=1, hp=1, max_hp=1, gold=0,
                         selected_goal="g", action="a", outcome="ok",
                         plan_tree=(node,))
    assert snap.plan_tree[0].label == "life_amulet"
    assert snap.plan_tree[0].children == ()
```

- [ ] **Step 3: Run to verify it passes** (field addition alone satisfies it)

Run: `uv run pytest tests/test_ai/test_plan_tree.py::test_snapshot_carries_plan_tree -q`
Expected: PASS.

- [ ] **Step 4: Wire the builder into `player.py`**

Add the import at the top of `player.py` (with the other `ai` imports):
```python
from artifactsmmo_cli.ai.plan_tree import build_plan_tree
```
In the `CycleSnapshot(...)` construction (currently ending at the `bank_items=...` line ~1469-1470), add a `plan_tree=` argument immediately after `bank_items`:
```python
            bank_items=(dict(self.state.bank_items)
                        if self.state.bank_items is not None else None),
            plan_tree=(
                build_plan_tree(
                    self._last_decision, self.state, self.game_data,
                    f"{selected_goal_name}: {action_name}"
                    if selected_goal_name and action_name else (selected_goal_name or action_name),
                )
                if self._last_decision is not None else ()
            ),
```
Note: `serve_step` is the concrete work under the current step — the running goal + immediate action (NOT `path_next_action`, which is the leveling-path monster). `selected_goal_name` and `action_name` are the same locals already passed to `selected_goal=`/`action=` above.

- [ ] **Step 5: Run the player + snapshot suites**

Run: `uv run pytest tests/test_ai/test_player.py tests/test_ai/test_plan_tree.py -q`
Expected: PASS (existing player cycle tests exercise the new line).

- [ ] **Step 6: Confirm the new line is covered**

Run: `uv run pytest tests/test_ai/test_player.py --cov=artifactsmmo_cli.ai.player --cov-report=term-missing -q`
Expected: the `plan_tree=build_plan_tree(...)` lines are NOT in the missing list. If they are, add a test in `tests/test_ai/test_player.py` that drives one full cycle with a non-None `_last_decision` and asserts the emitted snapshot's `plan_tree` is non-empty (mirror the existing snapshot-emit test in that file).

- [ ] **Step 7: Typecheck + commit**

Run: `uv run mypy src/artifactsmmo_cli/ai/player.py src/artifactsmmo_cli/ai/cycle_snapshot.py`
Expected: no errors.
```bash
git add src/artifactsmmo_cli/ai/cycle_snapshot.py src/artifactsmmo_cli/ai/player.py tests/test_ai/test_plan_tree.py
git commit -m "feat(tui): serialize plan_tree onto CycleSnapshot from the cycle decision"
```

---

### Task 3: `PlanTree` Textual widget

**Files:**
- Create: `src/artifactsmmo_cli/tui/widgets/plan_tree.py`
- Test: `tests/test_tui/test_plan_tree_widget.py`

**Interfaces:**
- Consumes: `PlanTreeNode` (Task 1).
- Produces: `class PlanTree(Tree)` with `set_nodes(roots: tuple[PlanTreeNode, ...]) -> None`; module fn `default_expanded(roots: tuple[PlanTreeNode, ...]) -> set[str]`.

- [ ] **Step 1: Write the failing test** `tests/test_tui/test_plan_tree_widget.py`

```python
import pytest
from textual.app import App, ComposeResult

from artifactsmmo_cli.ai.cycle_snapshot import PlanTreeNode
from artifactsmmo_cli.tui.widgets.plan_tree import PlanTree, default_expanded


def _sample() -> tuple[PlanTreeNode, ...]:
    step = PlanTreeNode(key="step:sk", label="grind copper_ring", kind="step", status="current")
    skill = PlanTreeNode(key="sk", label="jewelrycrafting → 5", kind="skill",
                         status="current", children=(step,))
    ring = PlanTreeNode(key="ring", label="golden_ring", kind="obtain", status="met")
    chosen = PlanTreeNode(key="amulet", label="life_amulet", kind="obtain",
                          status="unmet", children=(skill, ring))
    stub = PlanTreeNode(key="boots", label="steel_boots", kind="root_stub",
                        status="unmet", detail="root 2 · gear · 3.10")
    return (chosen, stub)


def test_default_expanded_opens_chosen_and_path_to_current():
    keys = default_expanded(_sample())
    assert "amulet" in keys and "sk" in keys      # chosen root + path to current
    assert "boots" not in keys                     # stub stays collapsed


class _Harness(App):
    def __init__(self, roots):
        super().__init__()
        self._roots = roots

    def compose(self) -> ComposeResult:
        yield PlanTree(id="pt")

    def on_mount(self) -> None:
        self.query_one("#pt", PlanTree).set_nodes(self._roots)


@pytest.mark.asyncio
async def test_set_nodes_builds_structure_and_stub_is_leaf():
    app = _Harness(_sample())
    async with app.run_test():
        tree = app.query_one("#pt", PlanTree)
        top = tree.root.children
        assert [n.data.label for n in top] == ["life_amulet", "steel_boots"]
        stub = top[1]
        assert stub.allow_expand is False          # root_stub is a leaf
        assert top[0].is_expanded                   # chosen auto-expanded


@pytest.mark.asyncio
async def test_expansion_memory_reapplied_on_rebuild():
    app = _Harness(_sample())
    async with app.run_test():
        tree = app.query_one("#pt", PlanTree)
        # simulate the user having opened the 'golden_ring' branch's parent chain
        tree._expanded_keys.add("ring")
        tree.set_nodes(_sample())
        ring = next(n for n in tree.root.children[0].children if n.data.key == "ring")
        # 'ring' has no children so it cannot expand, but its key is retained
        assert "ring" in tree._expanded_keys
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_tui/test_plan_tree_widget.py -q`
Expected: FAIL — `ModuleNotFoundError: artifactsmmo_cli.tui.widgets.plan_tree`.

- [ ] **Step 3: Create** `src/artifactsmmo_cli/tui/widgets/plan_tree.py`

```python
"""Interactive collapsible tree of the chosen objective's prerequisite plan.

Renders tuple[PlanTreeNode, ...] onto a Textual Tree, styling each label by
status/kind, and preserves the operator's expand/collapse choices by node key
across live snapshot rebuilds."""

from rich.text import Text
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from artifactsmmo_cli.ai.cycle_snapshot import PlanTreeNode

_STYLE = {
    "met": "green",
    "unmet": "",
    "current": "bold yellow",
    "step": "cyan",
    "root_stub": "dim",
}


def _glyph(node: PlanTreeNode, chosen: bool) -> str:
    if chosen:
        return "●"                 # ● chosen root
    if node.kind in ("root_stub", "step"):
        return "•"                 # •
    if node.status == "current":
        return "▸"                 # ▸
    if node.status == "met":
        return "✔"                 # ✔
    return "○"                     # ○ unmet


def _node_text(node: PlanTreeNode, chosen: bool) -> Text:
    body = f"{_glyph(node, chosen)} {node.label}"
    if chosen:
        body += "   ◄ CHOSEN"
    elif node.status == "current" and node.kind != "step":
        body += "   ◄ now"
    if node.detail:
        body += f"   {node.detail}"
    style = "bold" if chosen else _STYLE.get(node.kind if node.kind in _STYLE else node.status,
                                             _STYLE.get(node.status, ""))
    return Text(body, style=style)


def default_expanded(roots: tuple[PlanTreeNode, ...]) -> set[str]:
    """Keys to open on first render: the chosen root plus every node on the path
    down to the `current` node."""
    keys: set[str] = set()

    def walk(node: PlanTreeNode, chain: list[str]) -> None:
        chain = chain + [node.key]
        if node.status == "current":
            keys.update(chain)
        for child in node.children:
            walk(child, chain)

    if roots and roots[0].kind != "root_stub":
        keys.add(roots[0].key)
        walk(roots[0], [])
    return keys


class PlanTree(Tree):
    """Prerequisite plan tree with key-based expansion memory."""

    def __init__(self, **kwargs) -> None:
        super().__init__("PLAN", **kwargs)
        self.show_root = False
        self._expanded_keys: set[str] = set()
        self._seeded = False

    def set_nodes(self, roots: tuple[PlanTreeNode, ...]) -> None:
        if not self._seeded:
            self._expanded_keys = default_expanded(roots)
            self._seeded = True
        self.root.remove_children()
        for i, node in enumerate(roots):
            self._add(self.root, node, chosen=(i == 0 and node.kind != "root_stub"))

    def _add(self, parent: TreeNode, node: PlanTreeNode, chosen: bool = False) -> None:
        tn = parent.add(_node_text(node, chosen), data=node,
                        allow_expand=bool(node.children))
        for child in node.children:
            self._add(tn, child)
        if node.children and node.key in self._expanded_keys:
            tn.expand()

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        node = event.node.data
        if isinstance(node, PlanTreeNode):
            self._expanded_keys.add(node.key)

    def on_tree_node_collapsed(self, event: Tree.NodeCollapsed) -> None:
        node = event.node.data
        if isinstance(node, PlanTreeNode):
            self._expanded_keys.discard(node.key)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_tui/test_plan_tree_widget.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Typecheck + commit**

Run: `uv run mypy src/artifactsmmo_cli/tui/widgets/plan_tree.py`
Expected: no errors.
```bash
git add src/artifactsmmo_cli/tui/widgets/plan_tree.py tests/test_tui/test_plan_tree_widget.py
git commit -m "feat(tui): PlanTree widget — collapsible prerequisite tree with expansion memory"
```

---

### Task 4: Retire the flowchart body; add `build_plan_header`

**Files:**
- Modify: `src/artifactsmmo_cli/tui/plan_summary.py` (delete flowchart builders; add `build_plan_header`)
- Test: `tests/test_tui/test_plan_summary.py` (replace flowchart tests with header tests)

**Interfaces:**
- Consumes: `CycleSnapshot` (for `max_level`, `chosen_root`, `projected_cycles_to_max`, `suppressed_goals`).
- Produces: `build_plan_header(snap: CycleSnapshot) -> RenderableType`.
- Removes: `build_plan_summary`, `_body`, `_obtain_chain`, `_depth`, `_chosen_entry`, `_stub_line`, `ALT_PAGE_SIZE`, `CHOSEN_GLYPH`, `STUB_GLYPH`, the `_CHARLVL_RE`/`_SKILL_RE` regexes. (`short_root`/`_OBTAIN_RE` stay in `plan_format.py`.)

- [ ] **Step 1: Replace `tests/test_tui/test_plan_summary.py` entirely**

```python
from rich.console import Console

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.tui.plan_summary import build_plan_header


def _text(renderable) -> str:
    console = Console(no_color=True, width=120)
    with console.capture() as cap:
        console.print(renderable)
    return cap.get()


def _snap(**ov) -> CycleSnapshot:
    base = dict(cycle_index=1, timestamp="t", character="hero", x=0, y=0, level=1,
                xp=0, max_xp=100, hp=10, max_hp=10, gold=0, selected_goal="g",
                action="a", outcome="ok", max_level=40)
    base.update(ov)
    return CycleSnapshot(**base)


def test_header_shows_objective_and_eta():
    out = _text(build_plan_header(_snap(
        chosen_root="ObtainItem(code='life_amulet', quantity=1)",
        projected_cycles_to_max=18.0)))
    assert "OBJECTIVE" in out and "40" in out
    assert "ETA" in out and "18" in out


def test_header_none_objective_message():
    out = _text(build_plan_header(_snap(chosen_root=None)))
    assert "No committed objective" in out


def test_header_lists_suppressed():
    out = _text(build_plan_header(_snap(
        chosen_root="ReachCharLevel(level=3)",
        suppressed_goals=["PursueTask", "GatherMaterials"])))
    assert "suppressed" in out and "PursueTask" in out and "GatherMaterials" in out


def test_header_omits_eta_when_absent():
    out = _text(build_plan_header(_snap(chosen_root="ReachCharLevel(level=3)")))
    assert "ETA" not in out
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_tui/test_plan_summary.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_plan_header'`.

- [ ] **Step 3: Replace the body of `src/artifactsmmo_cli/tui/plan_summary.py`**

Replace the ENTIRE file with:
```python
"""Pure builder for the plan screen's header block: the objective line, an ETA
estimate, and the suppressed-goals footer. The plan body itself is rendered by
the PlanTree widget from the snapshot's plan_tree."""

from rich.console import Group, RenderableType
from rich.text import Text

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot


def build_plan_header(snap: CycleSnapshot) -> RenderableType:
    """Objective + ETA + suppressed-goals header for the plan screen."""
    parts: list[RenderableType] = [
        Text(f"OBJECTIVE  reach level {snap.max_level}", style="bold")
    ]
    if snap.chosen_root is None:
        parts.append(Text("No committed objective this cycle."))
    if snap.projected_cycles_to_max is not None:
        parts.append(Text(f"ETA ~{snap.projected_cycles_to_max:.0f} cycles (estimate)",
                          style="dim"))
    if snap.suppressed_goals:
        parts.append(Text(f"suppressed  {' · '.join(snap.suppressed_goals)}",
                          style="dim"))
    return Group(*parts)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_tui/test_plan_summary.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Confirm no stale importers of the removed builders**

Run: `grep -rn "build_plan_summary\|ALT_PAGE_SIZE\|_obtain_chain\|from artifactsmmo_cli.tui.plan_summary import" src/ tests/`
Expected: only `plan_screen.py` (fixed in Task 5) and `test_plan_summary.py`/`test_plan_screen.py`. No other references.

- [ ] **Step 6: Typecheck + commit**

Run: `uv run mypy src/artifactsmmo_cli/tui/plan_summary.py`
Expected: no errors.
```bash
git add src/artifactsmmo_cli/tui/plan_summary.py tests/test_tui/test_plan_summary.py
git commit -m "refactor(tui): retire flowchart body, slim plan_summary to build_plan_header"
```

---

### Task 5: Rewire `PlanScreen` to header + `PlanTree`; drop alt-pagination

**Files:**
- Modify: `src/artifactsmmo_cli/tui/screens/plan_screen.py` (rewrite)
- Test: `tests/test_tui/test_plan_screen.py` (rewrite)
- Verify: `src/artifactsmmo_cli/tui/app.py` (no change expected — confirm it still constructs `PlanScreen(self._last_snapshot, self._game_data)` and refreshes via `update_snapshot`)

**Interfaces:**
- Consumes: `build_plan_header` (Task 4), `PlanTree` (Task 3), `CycleSnapshot.plan_tree` (Task 2).

- [ ] **Step 1: Replace `tests/test_tui/test_plan_screen.py` entirely**

```python
"""PlanScreen tests — header renders and the tree receives snapshot nodes."""

import pytest
from rich.console import Console
from textual.app import App, ComposeResult

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot, PlanTreeNode
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.screens.plan_screen import PlanScreen
from artifactsmmo_cli.tui.widgets.plan_tree import PlanTree


def _text(renderable) -> str:
    console = Console(no_color=True, width=120)
    with console.capture() as cap:
        console.print(renderable)
    return cap.get()


def _snap(**ov) -> CycleSnapshot:
    node = PlanTreeNode(key="amulet", label="life_amulet", kind="obtain", status="unmet")
    base = dict(cycle_index=1, timestamp="t", character="hero", x=0, y=0, level=1,
                xp=0, max_xp=100, hp=10, max_hp=10, gold=0, selected_goal="g",
                action="a", outcome="ok", max_level=40,
                chosen_root="ObtainItem(code='life_amulet', quantity=1)",
                projected_cycles_to_max=18.0, plan_tree=(node,))
    base.update(ov)
    return CycleSnapshot(**base)


class _Harness(App):
    def __init__(self, snap):
        super().__init__()
        self._snap = snap

    def on_mount(self) -> None:
        self.push_screen(PlanScreen(self._snap, GameData()))


@pytest.mark.asyncio
async def test_screen_mounts_header_and_tree():
    app = _Harness(_snap())
    async with app.run_test():
        screen = app.screen
        assert isinstance(screen, PlanScreen)
        tree = screen.query_one("#plan-tree", PlanTree)
        assert [n.data.label for n in tree.root.children] == ["life_amulet"]


@pytest.mark.asyncio
async def test_update_snapshot_refreshes_tree():
    app = _Harness(_snap())
    async with app.run_test():
        screen = app.screen
        new = PlanTreeNode(key="ring", label="golden_ring", kind="obtain", status="unmet")
        screen.update_snapshot(_snap(plan_tree=(new,)))
        tree = screen.query_one("#plan-tree", PlanTree)
        assert [n.data.label for n in tree.root.children] == ["golden_ring"]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_tui/test_plan_screen.py -q`
Expected: FAIL — `ImportError` (`build_plan_detail` gone) / `PlanTree` not wired.

- [ ] **Step 3: Rewrite `src/artifactsmmo_cli/tui/screens/plan_screen.py`**

```python
"""Full-screen plan-tree modal (toggled with 'p'): an objective header above an
interactive collapsible prerequisite tree."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.plan_summary import build_plan_header
from artifactsmmo_cli.tui.widgets.plan_tree import PlanTree


class PlanScreen(Screen[None]):
    """Modal full-screen plan tree. Dismiss with 'p' or Escape."""

    DEFAULT_CSS = """
    #plan-modal #plan-header {
        padding: 1 2 0 2;
    }
    #plan-modal #plan-tree {
        width: 1fr;
        height: 1fr;
        padding: 0 2 1 2;
    }
    """

    BINDINGS = [
        ("escape", "dismiss", "Back"),
        ("p", "dismiss", "Back"),
    ]

    def __init__(self, snapshot: CycleSnapshot, game_data: GameData) -> None:
        super().__init__(id="plan-modal")
        self._snapshot = snapshot
        self._game_data = game_data

    def compose(self) -> ComposeResult:
        yield Static(build_plan_header(self._snapshot), id="plan-header")
        yield PlanTree(id="plan-tree")

    def on_mount(self) -> None:
        self.query_one("#plan-tree", PlanTree).set_nodes(self._snapshot.plan_tree)

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self._snapshot = snap
        if self.is_mounted:
            self.query_one("#plan-header", Static).update(build_plan_header(snap))
            self.query_one("#plan-tree", PlanTree).set_nodes(snap.plan_tree)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_tui/test_plan_screen.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Confirm app wiring is intact**

Run: `grep -n "PlanScreen\|update_snapshot\|_game_data" src/artifactsmmo_cli/tui/app.py`
Expected: `action_toggle_plan` still builds `PlanScreen(self._last_snapshot, self._game_data)` and the modal-refresh guard forwards `update_snapshot`. No `alt_prev`/`alt_next`/`[`/`]` references remain anywhere.
Run: `grep -rn "alt_prev\|alt_next\|action_alt\|\"\\[\"\|\"\\]\"" src/artifactsmmo_cli/tui/`
Expected: no matches.

- [ ] **Step 6: Full gate — suite, types, coverage, warnings**

Run: `uv run pytest tests/test_tui/ tests/test_ai/test_plan_tree.py -q`
Expected: PASS, 0 warnings, 0 skipped.
Run: `uv run mypy src/artifactsmmo_cli/tui/screens/plan_screen.py`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/tui/screens/plan_screen.py tests/test_tui/test_plan_screen.py
git commit -m "feat(tui): plan screen renders interactive prerequisite tree, drop alt-pagination"
```

---

### Task 6: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the entire suite with coverage**

Run: `uv run pytest --cov=artifactsmmo_cli --cov-report=term-missing -q`
Expected: 0 failures, 0 warnings, 0 skipped, 100% coverage. Address any gap in the files touched by this plan (`ai/plan_tree.py`, `ai/cycle_snapshot.py`, `ai/player.py`, `tui/plan_summary.py`, `tui/widgets/plan_tree.py`, `tui/screens/plan_screen.py`).

- [ ] **Step 2: Typecheck the whole package**

Run: `uv run mypy src/`
Expected: no errors.

- [ ] **Step 3: Final commit if anything changed during verification**

```bash
git add -A
git commit -m "test(tui): close coverage gaps for plan-tree prerequisite nesting"
```

---

## Self-Review

**Spec coverage:**
- Textual Tree render (spec decision 1) → Task 3.
- Chosen expands, others stubs, drop `[ ]` pagination (decision 2) → Tasks 1 (build), 5 (drop pagination).
- Live refresh preserves expansion by key (decision 3) → Task 3 (`_expanded_keys`, `default_expanded`).
- Unified prerequisites() source (decision 4) → Task 1 `_expand`.
- Synthetic grind step from running goal+action, NOT a graph node (decision 5) → Task 1 (`serve_step` child) + Task 2 (call-site composition). **Correction vs spec text:** the spec's Component B said `path_next_action`; that field is the leveling-path monster, so the plan sources `serve_step` from `selected_goal_name`+`action_name` instead. Spec patched to match.
- Status via `is_satisfied`, `current` = `chosen_step` (decision 6) → Task 1 `_expand`.
- No formal core (decision 7) → confirmed; no `formal/` changes.
- Retire flowchart body (Component E) → Task 4.
- Error handling (chosen_root None, unknown item, cycle/depth, missing bank) → Task 1 tests `test_chosen_root_none_returns_empty`, `test_cycle_and_depth_bounded`; `prerequisites()` already tolerates unknown items/None bank.

**Placeholder scan:** none — every step has concrete code/commands.

**Type consistency:** `build_plan_tree(decision, state, game_data, serve_step)` identical in Tasks 1 & 2. `PlanTreeNode` field set (`key/label/kind/status/detail/children`) identical across Tasks 1, 3, 5. `set_nodes`/`default_expanded`/`_expanded_keys` names identical across Tasks 3 & 5. `build_plan_header(snap)` identical across Tasks 4 & 5.

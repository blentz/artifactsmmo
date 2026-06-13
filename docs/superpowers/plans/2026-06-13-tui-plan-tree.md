# TUI Plan-Tree Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a TUI modal screen (toggle `p`) that shows the AI's committed objective as a collapsed recipe-closure plan with live have/need progress, an ETA, and the ranked alternative roots — so gear-first gathering reads as on-track progress, not a freeze.

**Architecture:** A pure `build_plan_summary` builder turns the committed root + the strategy ranking + current holdings into a Rich renderable, reusing the proven `closure_demand`/`shopping_list` cores to collapse gather→craft loops into one line per item. `CycleSnapshot` gains `chosen_root`/`strategy_ranking`/`bank_items` (populated from the cycle's `StrategyDecision`). A `PlanScreen` modal (mirroring `CharacterScreen`) renders it; `app.py` adds the `p` binding + wiring.

**Tech Stack:** Python 3.13 (`uv`), Textual TUI, Rich renderables. No Lean/formal gate (pure display reusing proven cores).

---

## Background the engineer needs

- Run Python with `/home/blentz/.local/bin/uv run` (full path if `uv` isn't on PATH).
- Project rules: imports at top; never catch bare `Exception` (use explicit `is None`/membership guards); no `if TYPE_CHECKING`; ONE behavioral class per file (pure-data dataclasses/BaseModels may share a module); 0 failures / 100% coverage (`uv run pytest -q`).
- Commit `--no-verify` (slow mypy hook). Stage ONLY each task's files; never `git add -A`.
- **Reuse, don't reinvent** (`src/artifactsmmo_cli/ai/`):
  - `recipe_closure.closure_demand(root: str, multiplier: int, game_data, out: dict[str,int], visited: frozenset[str]) -> None` — accumulates TOTAL closure demand per item into `out`.
  - `shopping_list.shopping_list(item: str, qty: int, recipes: Mapping[str, dict[str,int]], owned: dict[str,int]) -> dict[str,int]` — NET deficit per item (remaining work; 0 = covered by holdings). `recipes = game_data.crafting_recipes`.
  - `game_data.crafting_recipes: dict[str, dict[str,int]]` (craftable→{material:per_unit}); an item absent is RAW. `game_data.item_stats(code) -> ItemStats|None` with `.crafting_skill`, `.crafting_level`, `.type_`. `game_data.crafting_recipe(code)`.
  - `actions/equip.ITEM_TYPE_TO_SLOTS: dict[str, list[str]]` — a `type_` in it ⇒ equippable.
- **Strategy ranking** (`ai/tiers/strategy.py`): `RootScore` dataclass = `(root_repr: str, category: str, contribution: Fraction, cost: int, score: Fraction, step_repr: str, instrumental: bool)`. `StrategyDecision` (`ai/tiers/strategy.py`) = `(interrupt, chosen_root: MetaGoal|None, chosen_step, desired_state, ranking: list[RootScore], fallback_steps, fallback_roots)`. The player holds the cycle's decision as `self._last_decision`.
- **Snapshot/screen** (`ai/cycle_snapshot.py`, `tui/`): `CycleSnapshot` (Pydantic BaseModel) carries `inventory`, `skills`, `skill_xp`, `level/xp/max_xp`, `task_code/task_progress/task_total`, `path_next_action`, `projected_cycles_to_max`, `selected_goal`. `player.py` builds it ≈line 976 from `self.state`. `CharacterScreen` (`tui/screens/character_screen.py`) is the modal template: a `build_<x>(snap)->RenderableType` free function + a `Screen[None]` with `BINDINGS`, `compose` (a `VerticalScroll` + `Static`), `update_snapshot`.
- **App** (`tui/app.py`): `WatchApp.__init__(character, game_data)` stores `self._game_data`, `self._last_snapshot`, `self._recent_snapshots`. `update_snapshot` refreshes panes + (guard) `if isinstance(top, (CharacterScreen, LogScreen)): top.update_snapshot(snap)`. `action_toggle_character`: pop if on it, else `push_screen(CharacterScreen(self._last_snapshot))`. `BINDINGS` list holds the key bindings.
- **Test patterns** (`tests/test_tui/`): render Rich via
  ```python
  from rich.console import Console
  def _text(renderable) -> str:
      console = Console(no_color=True, width=120)
      with console.capture() as cap:
          console.print(renderable)
      return cap.get()
  ```
  `CycleSnapshot` built via a `_snap(**overrides)` helper (see `test_character_screen.py`). A fake `GameData` with `_crafting_recipes`/`_item_stats` is built in `tests/test_ai/test_goals.py::make_game_data` and `ItemStats(...)` — reuse that shape.

## File structure

- Create `src/artifactsmmo_cli/tui/plan_summary.py` — `build_plan_summary` (pure builder) + tiny private helpers.
- Create `src/artifactsmmo_cli/tui/screens/plan_screen.py` — `PlanScreen`.
- Create `tests/test_tui/test_plan_summary.py`, `tests/test_tui/test_plan_screen.py`.
- Modify `src/artifactsmmo_cli/ai/cycle_snapshot.py` — add `RootScoreView`, `chosen_root`, `strategy_ranking`, `bank_items`.
- Modify `src/artifactsmmo_cli/ai/player.py` — populate the new snapshot fields.
- Modify `src/artifactsmmo_cli/tui/app.py` — binding + `action_toggle_plan` + refresh guard.
- Modify `tests/test_ai/test_player.py` (or the snapshot test) — field population.

---

## Task 1: `build_plan_summary` — committed ObtainItem chain

**Files:**
- Create: `src/artifactsmmo_cli/tui/plan_summary.py`
- Test: `tests/test_tui/test_plan_summary.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tui/test_plan_summary.py
from rich.console import Console

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.cycle_snapshot import RootScoreView
from artifactsmmo_cli.tui.plan_summary import build_plan_summary


def _text(renderable) -> str:
    console = Console(no_color=True, width=120)
    with console.capture() as cap:
        console.print(renderable)
    return cap.get()


def _gd() -> GameData:
    gd = GameData()
    gd._crafting_recipes = {
        "copper_boots": {"copper_bar": 6},
        "copper_bar": {"copper_ore": 10},
    }
    gd._item_stats = {
        "copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                  crafting_skill="gearcrafting", crafting_level=1),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                crafting_skill="mining", crafting_level=1),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    return gd


def test_obtain_chain_collapses_with_have_need():
    out = _text(build_plan_summary(
        chosen_root="ObtainItem(code='copper_boots', quantity=1)",
        ranking=[], inventory={"copper_ore": 42}, bank=None, game_data=_gd(),
        projected_cycles_to_max=None,
    ))
    # one line per item, raw-first, with [have/total]
    assert "copper_ore" in out and "42/60" in out      # need 6*10=60, have 42
    assert "copper_bar" in out and "0/6" in out
    assert "copper_boots" in out and "0/1" in out
    assert "Collect" in out and "Craft" in out
    # boots is equippable (type 'boots' in ITEM_TYPE_TO_SLOTS) -> Equip line
    assert "Equip" in out and "copper_boots" in out


def test_active_leaf_marked_now():
    out = _text(build_plan_summary(
        chosen_root="ObtainItem(code='copper_boots', quantity=1)",
        ranking=[], inventory={"copper_ore": 42}, bank=None, game_data=_gd(),
        projected_cycles_to_max=None,
    ))
    # deepest item with remaining need is copper_ore -> marked now
    assert "now" in out


def test_bank_credited_in_have():
    out = _text(build_plan_summary(
        chosen_root="ObtainItem(code='copper_boots', quantity=1)",
        ranking=[], inventory={"copper_ore": 20}, bank={"copper_ore": 40},
        game_data=_gd(), projected_cycles_to_max=None,
    ))
    assert "60/60" in out   # 20 inv + 40 bank covers the 60 needed
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_plan_summary.py -q`
Expected: FAIL — `ModuleNotFoundError` (and `RootScoreView` import — Task 3 adds it; for now also stub it, see note).

NOTE: `RootScoreView` lives in `cycle_snapshot.py` (Task 3). To keep Task 1 runnable, this test imports it but does not use it (ranking=[]). If the import fails, add the minimal `RootScoreView` BaseModel to `cycle_snapshot.py` now (it's tiny and Task 3 expects it) — that is the one cross-task dependency; create it here:
```python
# src/artifactsmmo_cli/ai/cycle_snapshot.py — add near the top model defs
class RootScoreView(BaseModel):
    root_repr: str
    category: str
    score: float
```

- [ ] **Step 3: Implement the ObtainItem branch**

```python
# src/artifactsmmo_cli/tui/plan_summary.py
"""Pure builder: render the AI's committed objective as a collapsed plan tree
with have/need progress. Reuses closure_demand/shopping_list; no planning logic."""

import re

from rich.console import Group, RenderableType
from rich.table import Table

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.cycle_snapshot import RootScoreView
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import closure_demand

_OBTAIN_RE = re.compile(r"ObtainItem\(code='([^']+)', quantity=(\d+)\)")


def _depth(code: str, recipes: dict, memo: dict[str, int]) -> int:
    """Recipe depth: raw item = 0, craftable = 1 + max(input depth). Cycle-safe
    via memo seeded to 0 before recursion."""
    if code in memo:
        return memo[code]
    memo[code] = 0
    recipe = recipes.get(code)
    if recipe:
        memo[code] = 1 + max((_depth(m, recipes, memo) for m in recipe), default=0)
    return memo[code]


def _obtain_chain(code: str, qty: int, inventory: dict[str, int],
                  bank: dict[str, int] | None, game_data: GameData) -> Table:
    recipes = game_data.crafting_recipes
    owned: dict[str, int] = dict(inventory)
    if bank:
        for c, q in bank.items():
            owned[c] = owned.get(c, 0) + q
    total: dict[str, int] = {}
    closure_demand(code, qty, game_data, total, frozenset())
    from artifactsmmo_cli.ai.shopping_list import shopping_list
    net = shopping_list(code, qty, recipes, owned)

    memo: dict[str, int] = {}
    items = sorted(total, key=lambda c: (_depth(c, recipes, memo), c))
    # deepest item with remaining work = the leaf being worked now
    pending = [c for c in items if net.get(c, 0) > 0]
    active = max(pending, key=lambda c: (_depth(c, recipes, memo), c)) if pending else None

    t = Table(box=None, padding=(0, 2), show_header=False)
    t.add_column("v"); t.add_column("item"); t.add_column("prog"); t.add_column("note")
    for c in items:
        tot = total[c]
        have = tot - net.get(c, 0)
        verb = "Craft" if recipes.get(c) else "Collect"
        note = "<- now" if c == active else ""
        stats = game_data.item_stats(c)
        if (stats is not None and stats.crafting_skill
                and verb == "Craft"):
            note = (note + f"  (needs {stats.crafting_skill} {stats.crafting_level})").strip()
        t.add_row(verb, f"{tot}x {c}", f"[{have}/{tot}]", note)
    stats = game_data.item_stats(code)
    if stats is not None and stats.type_ in ITEM_TYPE_TO_SLOTS:
        t.add_row("Equip", code, "", "")
    return t


def build_plan_summary(
    chosen_root: str | None,
    ranking: list[RootScoreView],
    inventory: dict[str, int],
    bank: dict[str, int] | None,
    game_data: GameData,
    projected_cycles_to_max: float | None,
) -> RenderableType:
    """Render the committed objective's collapsed plan + progress. Task 2 adds
    the non-craftable root branches, header/ETA, and the ALTERNATIVES block."""
    if chosen_root is None:
        return Group(Table(box=None))  # placeholder; Task 2 replaces with empty-state text
    m = _OBTAIN_RE.search(chosen_root)
    if m:
        return _obtain_chain(m.group(1), int(m.group(2)), inventory, bank, game_data)
    return Group(Table(box=None))  # non-craftable roots: Task 2
```
(Move the `shopping_list` import to the top of the file per project rules — it's inline above only to show locality; the implementer places it with the other top imports.)

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_tui/test_plan_summary.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/plan_summary.py tests/test_tui/test_plan_summary.py src/artifactsmmo_cli/ai/cycle_snapshot.py
git commit --no-verify -m "feat(tui): plan_summary builder — collapsed ObtainItem chain w/ have/need"
```

---

## Task 2: `build_plan_summary` — non-craftable roots, header, ETA, alternatives

**Files:**
- Modify: `src/artifactsmmo_cli/tui/plan_summary.py`
- Test: `tests/test_tui/test_plan_summary.py`

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/test_tui/test_plan_summary.py
def test_none_root_empty_state():
    out = _text(build_plan_summary(None, [], {}, None, _gd(), None))
    assert "No committed objective" in out


def test_reach_char_level_line():
    out = _text(build_plan_summary(
        "ReachCharLevel(level=3)", [], {}, None, _gd(), None,
        ))
    assert "char XP" in out and "L3" in out


def test_reach_skill_level_line():
    out = _text(build_plan_summary("ReachSkillLevel(skill='gearcrafting', level=5)",
                                   [], {}, None, _gd(), None))
    assert "gearcrafting" in out and "L5" in out


def test_header_and_eta_and_alternatives():
    ranking = [
        RootScoreView(root_repr="ObtainItem(code='copper_boots', quantity=1)",
                      category="gear", score=2.5),
        RootScoreView(root_repr="ReachCharLevel(level=3)", category="char_level", score=1.48),
    ]
    out = _text(build_plan_summary(
        "ObtainItem(code='copper_boots', quantity=1)", ranking,
        {"copper_ore": 42}, None, _gd(), 18.0))
    assert "COMMITTED" in out and "copper_boots" in out
    assert "ETA" in out and "18" in out
    assert "ALTERNATIVES" in out and "ReachCharLevel" in out and "1.48" in out
    # the committed root is NOT repeated in the alternatives list
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_plan_summary.py -q -k "none_root or char_level or skill_level or header"`
Expected: FAIL.

- [ ] **Step 3: Extend the builder**

Add regexes + branches and wrap the body in a header/ETA/alternatives `Group`:
```python
_CHARLVL_RE = re.compile(r"ReachCharLevel\(level=(\d+)\)")
_SKILL_RE = re.compile(r"ReachSkillLevel\(skill='([^']+)', level=(\d+)\)")
```
New helpers + rewritten `build_plan_summary`:
```python
from rich.text import Text


def _category_of(root_repr: str, ranking: list[RootScoreView]) -> tuple[str, float | None]:
    for r in ranking:
        if r.root_repr == root_repr:
            return r.category, r.score
    return "?", None


def _body(chosen_root: str, inventory, bank, game_data,
          path_next_action: str | None, snap_xp: tuple[int, int],
          skill_xp: dict[str, int], task: tuple[str | None, int, int]) -> RenderableType:
    m = _OBTAIN_RE.search(chosen_root)
    if m:
        return _obtain_chain(m.group(1), int(m.group(2)), inventory, bank, game_data)
    m = _CHARLVL_RE.search(chosen_root)
    if m:
        xp, mx = snap_xp
        mon = path_next_action or "monster"
        return Text(f"Grind {mon} for char XP  [{xp}/{mx}]  -> L{m.group(1)}")
    m = _SKILL_RE.search(chosen_root)
    if m:
        sk = m.group(1)
        return Text(f"Grind {sk}  [skill xp {skill_xp.get(sk, 0)}]  -> L{m.group(2)}")
    code, prog, tot = task
    if code is not None and ("Task" in chosen_root or "task" in chosen_root):
        return Text(f"Task {code}  [{prog}/{tot}]")
    return Text(f"Plan: {chosen_root}")
```
Rewrite `build_plan_summary` to take the extra snapshot bits it needs (xp/max_xp, skill_xp, task, path_next_action) — UPDATE THE SIGNATURE and Task 1's tests/callers accordingly:
```python
def build_plan_summary(
    chosen_root: str | None,
    ranking: list[RootScoreView],
    inventory: dict[str, int],
    bank: dict[str, int] | None,
    game_data: GameData,
    projected_cycles_to_max: float | None,
    *,
    xp: int = 0, max_xp: int = 0,
    skill_xp: dict[str, int] | None = None,
    task_code: str | None = None, task_progress: int = 0, task_total: int = 0,
    path_next_action: str | None = None,
) -> RenderableType:
    if chosen_root is None:
        return Text("No committed objective this cycle.")
    cat, score = _category_of(chosen_root, ranking)
    parts: list[RenderableType] = []
    short = chosen_root.replace("ObtainItem(code=", "").replace(", quantity=1)", "")
    head = f"COMMITTED: {short}  ({cat}" + (f", score {score:.2f}" if score is not None else "") + ")"
    parts.append(Text(head, style="bold"))
    parts.append(_body(chosen_root, inventory, bank, game_data, path_next_action,
                       (xp, max_xp), skill_xp or {}, (task_code, task_progress, task_total)))
    if projected_cycles_to_max is not None:
        parts.append(Text(f"ETA ~{projected_cycles_to_max:.0f} cycles (estimate)", style="dim"))
    alts = [r for r in ranking if r.root_repr != chosen_root][:6]
    if alts:
        parts.append(Text("ALTERNATIVES (not chosen):", style="bold"))
        for r in alts:
            parts.append(Text(f"  {r.score:.2f}  {r.root_repr}  ({r.category})", style="dim"))
    return Group(*parts)
```
Update Task 1's 3 tests: they call `build_plan_summary(...)` positionally through `projected_cycles_to_max` — still valid (new args are keyword-only with defaults). The `_obtain_chain` Table is now nested in a Group under the header — the substring asserts (`"42/60"`, `"Collect"`, `"Equip"`) still hold.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_tui/test_plan_summary.py -q`
Expected: PASS (all Task 1 + Task 2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/plan_summary.py tests/test_tui/test_plan_summary.py
git commit --no-verify -m "feat(tui): plan_summary — non-craftable roots, header, ETA, alternatives"
```

---

## Task 3: CycleSnapshot plumbing + player population

**Files:**
- Modify: `src/artifactsmmo_cli/ai/cycle_snapshot.py`
- Modify: `src/artifactsmmo_cli/ai/player.py`
- Test: `tests/test_ai/test_player.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_ai/test_player.py
def test_snapshot_carries_chosen_root_and_ranking_and_bank(tmp_path):
    """The cycle snapshot exposes the committed strategy root + ranking + bank
    for the TUI plan screen."""
    from artifactsmmo_cli.ai.cycle_snapshot import RootScoreView
    rv = RootScoreView(root_repr="ObtainItem(code='x', quantity=1)", category="gear", score=2.5)
    assert rv.root_repr == "ObtainItem(code='x', quantity=1)"
    assert rv.category == "gear" and rv.score == 2.5
    # snapshot accepts the new fields
    from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
    snap = CycleSnapshot(
        cycle_index=1, timestamp="2026-06-13T00:00:00Z", character="hero",
        x=0, y=0, level=1, xp=0, max_xp=100, hp=10, max_hp=10, gold=0,
        selected_goal="g", action="a", outcome="ok",
        chosen_root="ObtainItem(code='x', quantity=1)",
        strategy_ranking=[rv], bank_items={"copper_ore": 5},
    )
    assert snap.chosen_root == "ObtainItem(code='x', quantity=1)"
    assert snap.strategy_ranking[0].score == 2.5
    assert snap.bank_items == {"copper_ore": 5}
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ai/test_player.py::test_snapshot_carries_chosen_root_and_ranking_and_bank -q`
Expected: FAIL — `RootScoreView` / fields missing (unless added in Task 1; then the snapshot fields fail).

- [ ] **Step 3: Add the fields**

In `src/artifactsmmo_cli/ai/cycle_snapshot.py` (if not already from Task 1):
```python
class RootScoreView(BaseModel):
    """Compact view of a ranked strategy root for the TUI plan screen."""
    root_repr: str
    category: str
    score: float
```
And on `CycleSnapshot`:
```python
    chosen_root: str | None = None
    strategy_ranking: list[RootScoreView] = Field(default_factory=list)
    bank_items: dict[str, int] | None = None
```

In `src/artifactsmmo_cli/ai/player.py`, where `CycleSnapshot(...)` is built (≈line 976), add the populated fields. The cycle's decision is `self._last_decision` (a `StrategyDecision | None`):
```python
            chosen_root=(repr(self._last_decision.chosen_root)
                         if self._last_decision is not None
                         and self._last_decision.chosen_root is not None else None),
            strategy_ranking=[
                RootScoreView(root_repr=r.root_repr, category=r.category, score=float(r.score))
                for r in (self._last_decision.ranking if self._last_decision is not None else [])
            ],
            bank_items=(dict(self.state.bank_items)
                        if self.state.bank_items is not None else None),
```
Add `from artifactsmmo_cli.ai.cycle_snapshot import RootScoreView` to player's imports (it already imports `CycleSnapshot`). Confirm `self._last_decision` is set before the snapshot is built each cycle (it is assigned when the strategy runs; if a cycle can build a snapshot before the decision exists, the `is not None` guards cover it).

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_player.py -q`
Expected: PASS (new test + existing player tests; the new snapshot fields are optional with defaults, so existing snapshot constructions stay valid).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/cycle_snapshot.py src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player.py
git commit --no-verify -m "feat(ai): snapshot carries chosen_root, strategy_ranking, bank_items"
```

---

## Task 4: `PlanScreen` + app wiring

**Files:**
- Create: `src/artifactsmmo_cli/tui/screens/plan_screen.py`
- Modify: `src/artifactsmmo_cli/tui/app.py`
- Test: `tests/test_tui/test_plan_screen.py`, `tests/test_tui/test_app.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tui/test_plan_screen.py
from rich.console import Console

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot, RootScoreView
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.tui.screens.plan_screen import build_plan_detail


def _text(renderable) -> str:
    console = Console(no_color=True, width=120)
    with console.capture() as cap:
        console.print(renderable)
    return cap.get()


def _gd() -> GameData:
    gd = GameData()
    gd._crafting_recipes = {"copper_boots": {"copper_bar": 6}, "copper_bar": {"copper_ore": 10}}
    gd._item_stats = {"copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                                crafting_skill="gearcrafting", crafting_level=1)}
    return gd


def _snap(**ov) -> CycleSnapshot:
    base = dict(cycle_index=1, timestamp="2026-06-13T00:00:00Z", character="hero",
                x=0, y=0, level=1, xp=0, max_xp=100, hp=10, max_hp=10, gold=0,
                selected_goal="g", action="a", outcome="ok",
                chosen_root="ObtainItem(code='copper_boots', quantity=1)",
                strategy_ranking=[RootScoreView(root_repr="ObtainItem(code='copper_boots', quantity=1)",
                                                category="gear", score=2.5)],
                inventory={"copper_ore": 42}, projected_cycles_to_max=18.0)
    base.update(ov)
    return CycleSnapshot(**base)


def test_build_plan_detail_from_snapshot():
    out = _text(build_plan_detail(_snap(), _gd()))
    assert "COMMITTED" in out and "copper_boots" in out
    assert "42/60" in out and "ETA" in out
```

```python
# add to tests/test_tui/test_app.py (mirror the existing character-toggle test)
def test_p_binding_present():
    from artifactsmmo_cli.tui.app import WatchApp
    keys = [b[0] if isinstance(b, tuple) else b.key for b in WatchApp.BINDINGS]
    assert "p" in keys
```
(Adapt `test_p_binding_present` to however `test_app.py` already inspects `BINDINGS` for `c`/`l` — copy that test's exact style.)

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_plan_screen.py tests/test_tui/test_app.py::test_p_binding_present -q`
Expected: FAIL — module/binding missing.

- [ ] **Step 3: Implement `PlanScreen` + wire the app**

```python
# src/artifactsmmo_cli/tui/screens/plan_screen.py
"""Full-screen plan-tree modal (toggled with 'p')."""

from rich.console import RenderableType
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.plan_summary import build_plan_summary


def build_plan_detail(snap: CycleSnapshot, game_data: GameData) -> RenderableType:
    """Adapter: pull the plan-relevant fields off the snapshot and render."""
    return build_plan_summary(
        snap.chosen_root, snap.strategy_ranking, snap.inventory, snap.bank_items,
        game_data, snap.projected_cycles_to_max,
        xp=snap.xp, max_xp=snap.max_xp, skill_xp=snap.skill_xp,
        task_code=snap.task_code, task_progress=snap.task_progress,
        task_total=snap.task_total, path_next_action=snap.path_next_action,
    )


class PlanScreen(Screen[None]):
    """Modal full-screen plan tree. Dismiss with 'p' or Escape."""

    DEFAULT_CSS = """
    #plan-modal #plan-scroll { width: 1fr; height: 1fr; padding: 1 2; }
    """
    BINDINGS = [("escape", "dismiss", "Back"), ("p", "dismiss", "Back")]

    def __init__(self, snapshot: CycleSnapshot, game_data: GameData) -> None:
        super().__init__(id="plan-modal")
        self._snapshot = snapshot
        self._game_data = game_data

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="plan-scroll"):
            yield Static(build_plan_detail(self._snapshot, self._game_data), id="plan-detail")

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self._snapshot = snap
        self.query_one("#plan-detail", Static).update(build_plan_detail(snap, self._game_data))
```

In `src/artifactsmmo_cli/tui/app.py`:
- Import: `from artifactsmmo_cli.tui.screens.plan_screen import PlanScreen`.
- Add `("p", "toggle_plan", "Plan")` to `BINDINGS`.
- Extend the refresh guard: `if isinstance(top, (CharacterScreen, LogScreen, PlanScreen)):`.
- Add the action (mirror `action_toggle_character`):
```python
    def action_toggle_plan(self) -> None:
        if isinstance(self.screen, PlanScreen):
            self.pop_screen()
        elif self._last_snapshot is not None:
            self.push_screen(PlanScreen(self._last_snapshot, self._game_data))
```
- If `app.py` has a `CSS`/`DEFAULT_CSS` block that resets pushed-modal layout for `CharacterScreen`/`LogScreen` ids, add the `#plan-modal` id alongside (check the comment near line 28 about the bare `Screen` grid; replicate whatever rule `#character-modal` gets).

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_tui/test_plan_screen.py tests/test_tui/test_app.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/screens/plan_screen.py src/artifactsmmo_cli/tui/app.py tests/test_tui/test_plan_screen.py tests/test_tui/test_app.py
git commit --no-verify -m "feat(tui): PlanScreen modal + 'p' binding/wiring"
```

---

## Task 5: Full suite + coverage + live smoke

**Files:** none (verification; add targeted tests only if coverage gaps).

- [ ] **Step 1: Full suite + 100% coverage**

Run: `uv run pytest -q`
Expected: `0 failed`, `100% coverage`. Likely uncovered lines and how to cover (no pragmas):
- `plan_summary.py`: the `Plan: {chosen_root}` fallback (an unrecognized root repr → test with `chosen_root="WeirdRoot()"`); the skill-gate `(needs ...)` note (a craft whose `crafting_level` > and a stats with `crafting_skill`); the PursueTask branch (`chosen_root="PursueTask(...)"`, `task_code` set).
- `plan_screen.py` `update_snapshot`: a test calling it is optional (Textual mount needed); cover `build_plan_detail` directly (Task 4 does). If `update_snapshot` is uncovered, add a tiny test that constructs the screen and calls `update_snapshot` is hard without a running app — instead ensure `build_plan_detail` covers the adapter; if a line in `update_snapshot` stays uncovered, restructure so the renderable build is in `build_plan_detail` (already is) and accept the one Textual line via an `App.run_test()` harness if the repo uses one (grep `run_test` in tests/test_tui).

- [ ] **Step 2: Live smoke (manual, optional but recommended)**

```bash
# Only if NOT colliding with a running session on the same character.
# Ask the user before launching the TUI on a live character.
```
Tell the user the screen is reachable with `p` in `artifactsmmo play <char> --tui`; do NOT auto-launch a live session (it can collide with a running bot). Verification is the pytest render tests.

- [ ] **Step 3: Final commit (if coverage tests added)**

```bash
git add tests/test_tui/
git commit --no-verify -m "test(tui): cover plan_summary fallback/skill-gate/task branches"
```

---

## Self-review notes (author)

- **Spec coverage:** ObtainItem collapse + have/need + bank credit + active-leaf + equip + skill-gate (T1); non-craftable roots + None + header + ETA + alternatives (T2); snapshot fields from StrategyDecision (T3); PlanScreen + `p` binding + refresh guard (T4); 100% coverage + live-smoke note (T5).
- **Cross-task dependency:** `RootScoreView` is needed by T1's test import and T2's builder but formally added in T3 — T1 Step 2 NOTE adds it early in `cycle_snapshot.py`. Consistent type: `RootScoreView(root_repr, category, score: float)`.
- **Naming consistency:** `build_plan_summary(chosen_root, ranking, inventory, bank, game_data, projected_cycles_to_max, *, xp, max_xp, skill_xp, task_code, task_progress, task_total, path_next_action)`; `build_plan_detail(snap, game_data)` adapter; `PlanScreen(snapshot, game_data)`; `action_toggle_plan`; snapshot fields `chosen_root`/`strategy_ranking`/`bank_items`.
- **Risk:** T2 changes `build_plan_summary`'s signature (adds keyword-only args) after T1 — T1's positional calls stay valid (defaults). The `_obtain_chain` Table nests under a Group in T2; T1 substring asserts still hold. Coverage of `update_snapshot` (Textual) is the one fiddly spot — T5 Step 1 gives the fallback (App.run_test harness if present).

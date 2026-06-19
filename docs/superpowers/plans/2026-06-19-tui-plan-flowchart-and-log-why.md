# TUI Plan Flowchart + Live "why" Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the per-cycle strategy ranking in the always-on TUI log pane (a dim "why" line) and turn the plan modal into a paginated flowchart (objective → chosen branch expanded, non-chosen branches as stubs).

**Architecture:** Pure presentation over data the `CycleSnapshot` already carries. One tiny data plumb: carry `step_repr` onto the `RootScoreView` view model. A shared `short_root` helper de-dups the `ObtainItem(...)` short-form. The log pane gets a testable pure `build_log_lines`; the plan modal's `build_plan_summary` is rewritten as a page-aware flowchart builder and `PlanScreen` gains paging state.

**Tech Stack:** Python 3.13, `rich` (Text/Group/Padding), `textual` (Screen/RichLog), pytest, uv, mypy, ruff.

## Global Constraints

- ALWAYS prefix Python commands with `uv run` (e.g. `uv run pytest`, `uv run mypy src`, `uv run ruff check`).
- All imports at top of file. No inline imports. No `...` imports. No `if TYPE_CHECKING`.
- One *behavioral* class per file; cohesive pure functions may share a module (the existing `log_screen.py` pattern: a `build_*` function beside its `Screen` class).
- Never catch `Exception`.
- Success criteria each task: `uv run pytest` and `uv run mypy src` and `uv run ruff check` all green — 0 errors, 0 warnings, 0 skipped, 100% coverage.
- All tests live under `tests/`. Use the real suite; no throwaway scripts.

---

### Task 1: Carry `step_repr` onto the ranking view model + shared `short_root` helper

**Files:**
- Modify: `src/artifactsmmo_cli/ai/cycle_snapshot.py` (`RootScoreView`)
- Modify: `src/artifactsmmo_cli/ai/player.py:1030-1033` (snapshot ranking comprehension)
- Create: `src/artifactsmmo_cli/tui/plan_format.py` (`short_root`)
- Test: `tests/test_tui/test_plan_format.py` (new)
- Test: `tests/test_ai/test_player.py:1781` (extend existing snapshot test)

**Interfaces:**
- Produces: `RootScoreView.step_repr: str` (defaults to `""`).
- Produces: `short_root(root_repr: str) -> str` — `ObtainItem(code='copper_boots', quantity=1)` → `copper_boots`; `...quantity=8)` → `8x copper_boots`; anything else returned unchanged.

- [ ] **Step 1: Write the failing test for `short_root`**

Create `tests/test_tui/test_plan_format.py`:

```python
"""short_root: collapse ObtainItem(...) reprs to a scannable short form."""

from artifactsmmo_cli.tui.plan_format import short_root


def test_obtain_quantity_one_drops_quantity():
    assert short_root("ObtainItem(code='copper_boots', quantity=1)") == "copper_boots"


def test_obtain_quantity_many_keeps_count():
    assert short_root("ObtainItem(code='copper_bar', quantity=8)") == "8x copper_bar"


def test_non_obtain_root_unchanged():
    assert short_root("ReachCharLevel(level=6)") == "ReachCharLevel(level=6)"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_tui/test_plan_format.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.tui.plan_format'`

- [ ] **Step 3: Create the helper module**

Create `src/artifactsmmo_cli/tui/plan_format.py`:

```python
"""Shared pure formatters for the TUI plan/log views (no rendering, no state)."""

import re

_OBTAIN_RE = re.compile(r"ObtainItem\(code='([^']+)', quantity=(\d+)\)")


def short_root(root_repr: str) -> str:
    """Collapse an ObtainItem(...) repr to `code` (quantity 1) or `Nx code`.
    Non-ObtainItem reprs are returned unchanged."""
    m = _OBTAIN_RE.fullmatch(root_repr)
    if m is None:
        return root_repr
    code, qty = m.group(1), m.group(2)
    return code if qty == "1" else f"{qty}x {code}"
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/test_tui/test_plan_format.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Add `step_repr` to `RootScoreView`**

In `src/artifactsmmo_cli/ai/cycle_snapshot.py`, change the `RootScoreView` class body:

```python
class RootScoreView(BaseModel):
    """Compact view of a ranked strategy root for the TUI plan screen."""

    root_repr: str
    category: str
    score: float
    step_repr: str = ""
```

(Default `""` keeps every existing `RootScoreView(...)` callsite — tests included — valid.)

- [ ] **Step 6: Plumb `step_repr` through the snapshot builder**

In `src/artifactsmmo_cli/ai/player.py`, the `strategy_ranking=[...]` comprehension (currently lines 1030-1033) becomes:

```python
            strategy_ranking=[
                RootScoreView(root_repr=r.root_repr, category=r.category,
                              score=float(r.score), step_repr=r.step_repr)
                for r in (self._last_decision.ranking if self._last_decision is not None else [])
            ],
```

- [ ] **Step 7: Extend the snapshot plumb test**

In `tests/test_ai/test_player.py`, in `test_snapshot_carries_chosen_root_and_ranking_and_bank`, build the view with a `step_repr` and assert it survives. Replace the `rv = ...` line and add one assert:

```python
    rv = RootScoreView(root_repr="ObtainItem(code='x', quantity=1)", category="gear",
                       score=2.5, step_repr="FightAction(chicken)")
```

and after `assert snap.strategy_ranking[0].score == 2.5` add:

```python
    assert snap.strategy_ranking[0].step_repr == "FightAction(chicken)"
```

- [ ] **Step 8: Run the affected tests**

Run: `uv run pytest tests/test_tui/test_plan_format.py tests/test_ai/test_player.py -v`
Expected: PASS (all)

- [ ] **Step 9: Gate + commit**

Run: `uv run pytest && uv run mypy src && uv run ruff check`
Expected: all green, 100% coverage.

```bash
git add src/artifactsmmo_cli/ai/cycle_snapshot.py src/artifactsmmo_cli/ai/player.py src/artifactsmmo_cli/tui/plan_format.py tests/test_tui/test_plan_format.py tests/test_ai/test_player.py
git commit -m "feat(tui): carry step_repr on RootScoreView + share short_root helper"
```

---

### Task 2: Live log "why" line (`build_log_lines`)

**Files:**
- Modify: `src/artifactsmmo_cli/tui/widgets/log_pane.py`
- Test: `tests/test_tui/test_log_pane.py`

**Interfaces:**
- Consumes: `short_root` (Task 1), `CycleSnapshot.chosen_root`, `.strategy_ranking`.
- Produces: `build_log_lines(snap: CycleSnapshot) -> list[str]` — `[line1]` for discretionary cycles (no `chosen_root` / empty ranking), `[line1, why_line]` otherwise. `LogPane.update_snapshot` writes each line in order.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_tui/test_log_pane.py` (top-level, after the existing classes):

```python
from artifactsmmo_cli.ai.cycle_snapshot import RootScoreView
from artifactsmmo_cli.tui.widgets.log_pane import build_log_lines


def _ranked_snap(**overrides):
    base = dict(
        chosen_root="ReachCharLevel(level=6)",
        strategy_ranking=[
            RootScoreView(root_repr="ReachCharLevel(level=6)", category="grind", score=1.80,
                          step_repr="FightAction(chicken)"),
            RootScoreView(root_repr="ObtainItem(code='copper_boots', quantity=1)",
                          category="gear", score=1.00, step_repr="UpgradeEquipment(copper_boots)"),
            RootScoreView(root_repr="ObtainItem(code='cooked_gudgeon', quantity=1)",
                          category="skill", score=0.40, step_repr="LevelSkill(cooking)"),
        ],
    )
    base.update(overrides)
    return _snap(**base)


class TestBuildLogLines:
    def test_no_chosen_root_is_single_line(self):
        lines = build_log_lines(_snap(chosen_root=None))
        assert len(lines) == 1

    def test_empty_ranking_is_single_line(self):
        lines = build_log_lines(_snap(chosen_root="ReachCharLevel(level=6)", strategy_ranking=[]))
        assert len(lines) == 1

    def test_why_line_shows_chosen_category_and_score(self):
        why = build_log_lines(_ranked_snap())[1]
        assert "why:" in why and "grind" in why and "1.80" in why

    def test_why_line_shows_top_two_alternatives(self):
        why = build_log_lines(_ranked_snap())[1]
        assert "copper_boots" in why and "1.00" in why
        assert "cooked_gudgeon" in why and "0.40" in why

    def test_why_line_omits_alt_segment_when_only_chosen(self):
        snap = _ranked_snap(strategy_ranking=[
            RootScoreView(root_repr="ReachCharLevel(level=6)", category="grind", score=1.80,
                          step_repr="FightAction(chicken)"),
        ])
        why = build_log_lines(snap)[1]
        assert "alt:" not in why

    def test_update_snapshot_writes_two_lines_when_ranked(self):
        pane = LogPane()
        captured = []
        with patch.object(pane, "write", side_effect=captured.append):
            pane.update_snapshot(_ranked_snap())
        assert len(captured) == 2
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_tui/test_log_pane.py -k "BuildLogLines or two_lines" -v`
Expected: FAIL — `ImportError: cannot import name 'build_log_lines'`

- [ ] **Step 3: Implement `build_log_lines` and rewrite `update_snapshot`**

Replace the whole body of `src/artifactsmmo_cli/tui/widgets/log_pane.py`:

```python
"""Scrolling log of per-cycle decisions. Wraps Textual's RichLog."""

from typing import Any

from textual.widgets import RichLog

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.tui.plan_format import short_root

_OUTCOME_COLOR = {"ok": "green", "no_plan": "yellow"}


def build_log_lines(snap: CycleSnapshot) -> list[str]:
    """Rich-markup lines for one cycle: the compact decision line, plus a dim
    'why' line (chosen root score + top-2 alternatives) when a strategy ranking
    is present. Discretionary cycles (no chosen_root / empty ranking) get the
    single line only."""
    outcome_color = _OUTCOME_COLOR.get(snap.outcome, "red")
    ts = snap.timestamp[11:19] if len(snap.timestamp) >= 19 else snap.timestamp
    line1 = (
        f"[dim]{ts}[/dim] "
        f"c{snap.cycle_index:>3} "
        f"[cyan]{snap.selected_goal:<25}[/cyan] "
        f"{snap.action:<35} "
        f"[{outcome_color}]{snap.outcome}[/{outcome_color}]"
    )
    if snap.chosen_root is None or not snap.strategy_ranking:
        return [line1]

    chosen = next((r for r in snap.strategy_ranking if r.root_repr == snap.chosen_root), None)
    if chosen is None:
        return [line1]
    why = f"   [dim]why:[/dim] {chosen.category} {chosen.score:.2f}"
    alts = [r for r in snap.strategy_ranking if r.root_repr != snap.chosen_root][:2]
    if alts:
        alt_text = " | ".join(f"{short_root(r.root_repr)} {r.score:.2f}" for r in alts)
        why = f"{why}  [dim]alt:[/dim] {alt_text}"
    return [line1, f"[dim]{why}[/dim]"]


class LogPane(RichLog):
    """Append-only decision log. Auto-scrolls to bottom."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(wrap=False, markup=True, auto_scroll=True, **kwargs)

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        for line in build_log_lines(snap):
            self.write(line)
```

- [ ] **Step 4: Update the legacy single-write assertion**

The existing `test_update_snapshot_calls_write` asserts `assert_called_once()`. Its `_snap()` has no `chosen_root`, so `build_log_lines` returns one line — the assertion still holds. Leave it. Verify by running the file.

- [ ] **Step 5: Run the log-pane tests**

Run: `uv run pytest tests/test_tui/test_log_pane.py -v`
Expected: PASS (all — old single-line tests + new ones)

- [ ] **Step 6: Gate + commit**

Run: `uv run pytest && uv run mypy src && uv run ruff check`
Expected: all green, 100% coverage.

```bash
git add src/artifactsmmo_cli/tui/widgets/log_pane.py tests/test_tui/test_log_pane.py
git commit -m "feat(tui): live log 'why' line — chosen root score + top-2 alternatives"
```

---

### Task 3: Plan modal flowchart (chosen branch + stubs + suppressed)

**Files:**
- Modify: `src/artifactsmmo_cli/tui/plan_summary.py`
- Test: `tests/test_tui/test_plan_summary.py`

**Interfaces:**
- Consumes: `short_root` (Task 1), `RootScoreView.step_repr` (Task 1).
- Produces (final signature after Task 4 adds paging — define the non-paging core here):
  `build_plan_summary(chosen_root, ranking, inventory, bank, game_data, projected_cycles_to_max, *, xp=0, max_xp=0, skill_xp=None, task_code=None, task_progress=0, task_total=0, path_next_action=None, plan_len=0, suppressed_goals=None)` returning a `rich` `RenderableType`. (Task 4 appends `alt_page=0, alt_page_size=ALT_PAGE_SIZE`.)
- The flowchart vocabulary replaces the old `COMMITTED` / `ALTERNATIVES` words — existing tests asserting those strings are rewritten here.

- [ ] **Step 1: Rewrite the existing plan-summary tests to the flowchart vocabulary**

In `tests/test_tui/test_plan_summary.py` replace the two layout-word assertions:

- In `test_header_and_eta_and_alternatives`, rename intent and change the three asserts to:

```python
def test_flowchart_chosen_branch_and_stubs():
    ranking = [
        RootScoreView(root_repr="ObtainItem(code='copper_boots', quantity=1)",
                      category="gear", score=2.5, step_repr="UpgradeEquipment(copper_boots)"),
        RootScoreView(root_repr="ReachCharLevel(level=3)", category="char_level", score=1.48,
                      step_repr="FightAction(chicken)"),
    ]
    out = _text(build_plan_summary(
        "ObtainItem(code='copper_boots', quantity=1)", ranking,
        {"copper_ore": 42}, None, _gd(), 18.0))
    assert "OBJECTIVE" in out
    assert "CHOSEN" in out and "copper_boots" in out and "2.5" in out
    assert "ETA" in out and "18" in out
    # the non-chosen root appears as a stub with its score
    assert "ReachCharLevel" in out and "1.48" in out
    assert "would" in out                       # stub action line
```

(The other existing tests — `test_obtain_chain_collapses_with_have_need`, `test_active_leaf_marked_now`, `test_bank_credited_in_have`, `test_none_root_empty_state`, `test_reach_char_level_line`, `test_reach_skill_level_line`, `test_pursue_task_line`, `test_unrecognized_root_falls_back_to_plain_plan_line` — keep asserting body content that the chosen branch still renders, so they pass unchanged.)

- In `test_plan_screen.py`, `test_build_plan_detail_from_snapshot` asserts `"COMMITTED"`. Change that assert to `assert "CHOSEN" in out and "copper_boots" in out` (keep `"42/60"` and `"ETA"`).

- [ ] **Step 2: Add the new suppressed/stub tests**

Add to `tests/test_tui/test_plan_summary.py`:

```python
def test_suppressed_footer_listed():
    out = _text(build_plan_summary(
        "ReachCharLevel(level=3)", [], {}, None, _gd(), None,
        suppressed_goals=["PursueTask", "GatherMaterials"]))
    assert "suppressed" in out and "PursueTask" in out and "GatherMaterials" in out


def test_chosen_branch_shows_plan_len_and_next():
    out = _text(build_plan_summary(
        "ReachCharLevel(level=3)", [], {}, None, _gd(), None,
        plan_len=3, path_next_action="chicken"))
    assert "plan" in out and "3" in out and "chicken" in out


def test_stub_would_line_for_obtain_root():
    ranking = [
        RootScoreView(root_repr="ReachCharLevel(level=3)", category="char_level", score=2.0,
                      step_repr="FightAction(chicken)"),
        RootScoreView(root_repr="ObtainItem(code='copper_boots', quantity=1)",
                      category="gear", score=1.0, step_repr="UpgradeEquipment(copper_boots)"),
    ]
    out = _text(build_plan_summary("ReachCharLevel(level=3)", ranking, {}, None, _gd(), None))
    stub = next(ln for ln in out.splitlines() if "copper_boots" in ln and "would" in ln)
    assert "Craft" in stub
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_tui/test_plan_summary.py tests/test_tui/test_plan_screen.py -v`
Expected: FAIL — flowchart strings (`OBJECTIVE`, `CHOSEN`, `would`, `suppressed`) absent; new params not accepted.

- [ ] **Step 4: Rewrite `plan_summary.py` as a flowchart builder**

Replace `src/artifactsmmo_cli/tui/plan_summary.py` with:

```python
"""Pure builder: render the AI's committed objective as a flowchart — objective
root, the chosen branch expanded (step / GOAP / have-need body), every non-chosen
root as a one-line stub, and a suppressed-goals footer. No planning logic."""

import re
from collections.abc import Mapping

from rich.console import Group, RenderableType
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.cycle_snapshot import RootScoreView
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import closure_demand
from artifactsmmo_cli.ai.shopping_list import shopping_list
from artifactsmmo_cli.tui.plan_format import short_root

CHOSEN_GLYPH = "●"
STUB_GLYPH = "○"

_OBTAIN_RE = re.compile(r"ObtainItem\(code='([^']+)', quantity=(\d+)\)")
_CHARLVL_RE = re.compile(r"ReachCharLevel\(level=(\d+)\)")
_SKILL_RE = re.compile(r"ReachSkillLevel\(skill='([^']+)', level=(\d+)\)")


def _depth(code: str, recipes: Mapping[str, dict[str, int]], memo: dict[str, int]) -> int:
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
    net = shopping_list(code, qty, recipes, owned)

    memo: dict[str, int] = {}
    items = sorted(total, key=lambda c: (_depth(c, recipes, memo), c))
    pending = [c for c in items if net.get(c, 0) > 0]
    active = min(pending, key=lambda c: (_depth(c, recipes, memo), c)) if pending else None

    t = Table(box=None, padding=(0, 2), show_header=False)
    t.add_column("v")
    t.add_column("item")
    t.add_column("prog")
    t.add_column("note")
    for c in items:
        tot = total[c]
        have = tot - net.get(c, 0)
        verb = "Craft" if recipes.get(c) else "Collect"
        note = "<- now" if c == active else ""
        stats = game_data.item_stats(c)
        if stats is not None and stats.crafting_skill and verb == "Craft":
            note = (note + f"  (needs {stats.crafting_skill} {stats.crafting_level})").strip()
        t.add_row(verb, f"{tot}x {c}", f"[{have}/{tot}]", note)
    stats = game_data.item_stats(code)
    if stats is not None and stats.type_ in ITEM_TYPE_TO_SLOTS:
        t.add_row("Equip", code, "", "")
    return t


def _body(chosen_root: str, inventory: dict[str, int], bank: dict[str, int] | None,
          game_data: GameData,
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


def _chosen_entry(chosen_root: str, ranking: list[RootScoreView]) -> RootScoreView | None:
    return next((r for r in ranking if r.root_repr == chosen_root), None)


def _stub_line(r: RootScoreView, game_data: GameData) -> Text:
    """One-line 'would ...' for a non-chosen root (no closure expansion)."""
    m = _OBTAIN_RE.fullmatch(r.root_repr)
    if m:
        code, qty = m.group(1), m.group(2)
        verb = "Craft" if game_data.crafting_recipes.get(code) else "Collect"
        recipe = game_data.crafting_recipes.get(code)
        needs = ""
        if recipe:
            needs = "  (needs " + ", ".join(f"{q}x {c}" for c, q in recipe.items()) + ")"
        return Text(f"│    would  {verb} {qty}x {code}{needs}", style="dim")
    detail = r.step_repr or short_root(r.root_repr)
    return Text(f"│    would  {detail}", style="dim")


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
    plan_len: int = 0,
    suppressed_goals: list[str] | None = None,
) -> RenderableType:
    """Render the committed objective as a flowchart: an OBJECTIVE root, the
    chosen branch expanded (step / GOAP / have-need body), the non-chosen roots
    as stub branches, then an ETA and suppressed-goals footer."""
    if chosen_root is None:
        return Text("No committed objective this cycle.")

    parts: list[RenderableType] = []
    max_level = game_data.max_character_level if game_data is not None else 0
    parts.append(Text(f"OBJECTIVE  reach level {max_level}", style="bold"))
    parts.append(Text("│"))

    chosen = _chosen_entry(chosen_root, ranking)
    cat = chosen.category if chosen is not None else "?"
    score_txt = f"  {chosen.score:.2f}" if chosen is not None else ""
    step_txt = chosen.step_repr if chosen is not None and chosen.step_repr else "-"
    parts.append(Text(f"├─{CHOSEN_GLYPH} {short_root(chosen_root)}  {cat}{score_txt}   ◄ CHOSEN",
                      style="bold"))
    parts.append(Text(f"│    step  {step_txt}", style="dim"))
    parts.append(Text(f"│    plan  {plan_len} actions   next {path_next_action or '?'}",
                      style="dim"))
    parts.append(Padding(_body(chosen_root, inventory, bank, game_data, path_next_action,
                               (xp, max_xp), skill_xp or {},
                               (task_code, task_progress, task_total)), (0, 0, 0, 5)))

    for r in (x for x in ranking if x.root_repr != chosen_root):
        parts.append(Text(f"├─{STUB_GLYPH} {short_root(r.root_repr)}  {r.category}  {r.score:.2f}"))
        parts.append(_stub_line(r, game_data))

    if projected_cycles_to_max is not None:
        parts.append(Text(f"ETA ~{projected_cycles_to_max:.0f} cycles (estimate)", style="dim"))
    if suppressed_goals:
        parts.append(Text(f"└─ suppressed  {' · '.join(suppressed_goals)}", style="dim"))
    return Group(*parts)
```

- [ ] **Step 5: Run the plan tests**

Run: `uv run pytest tests/test_tui/test_plan_summary.py tests/test_tui/test_plan_screen.py -v`
Expected: PASS (rewritten + new + unchanged body tests)

- [ ] **Step 6: Gate + commit**

Run: `uv run pytest && uv run mypy src && uv run ruff check`
Expected: all green, 100% coverage.

```bash
git add src/artifactsmmo_cli/tui/plan_summary.py tests/test_tui/test_plan_summary.py tests/test_tui/test_plan_screen.py
git commit -m "feat(tui): plan modal as flowchart — chosen branch expanded, stubs, suppressed"
```

---

### Task 4: Paginate the stub branches

**Files:**
- Modify: `src/artifactsmmo_cli/tui/plan_summary.py` (`build_plan_summary` paging params + footer)
- Modify: `src/artifactsmmo_cli/tui/screens/plan_screen.py` (`PlanScreen` page state, bindings, adapter)
- Test: `tests/test_tui/test_plan_summary.py`, `tests/test_tui/test_plan_screen.py`

**Interfaces:**
- Consumes: Task 3's `build_plan_summary`.
- Produces: `ALT_PAGE_SIZE = 6` (module const in `plan_summary.py`); `build_plan_summary(..., alt_page: int = 0, alt_page_size: int = ALT_PAGE_SIZE)` slices the stub list to one page and renders a `alternatives {lo}–{hi} of {total}` footer when there is more than one page. `PlanScreen` holds `_alt_page` and binds `[` (prev) / `]` (next).

- [ ] **Step 1: Write the failing paging tests**

Add to `tests/test_tui/test_plan_summary.py`:

```python
def _stub_ranking(n: int) -> list[RootScoreView]:
    out = [RootScoreView(root_repr="ReachCharLevel(level=3)", category="char_level",
                         score=9.0, step_repr="FightAction(chicken)")]  # chosen
    for i in range(n):
        out.append(RootScoreView(root_repr=f"ObtainItem(code='item{i}', quantity=1)",
                                 category="gear", score=1.0 - i * 0.01,
                                 step_repr=f"UpgradeEquipment(item{i})"))
    return out


def test_pagination_footer_and_first_page_slice():
    ranking = _stub_ranking(14)
    out = _text(build_plan_summary("ReachCharLevel(level=3)", ranking, {}, None, _gd(), None,
                                   alt_page=0, alt_page_size=6))
    assert "item0" in out and "item5" in out
    assert "item6" not in out
    assert "alternatives 1" in out and "of 14" in out


def test_pagination_last_page_slice():
    ranking = _stub_ranking(14)
    out = _text(build_plan_summary("ReachCharLevel(level=3)", ranking, {}, None, _gd(), None,
                                   alt_page=2, alt_page_size=6))
    assert "item12" in out and "item13" in out
    assert "item0" not in out
    assert "13" in out and "14" in out


def test_no_footer_when_single_page():
    ranking = _stub_ranking(3)
    out = _text(build_plan_summary("ReachCharLevel(level=3)", ranking, {}, None, _gd(), None))
    assert "alternatives" not in out
```

Add to `tests/test_tui/test_plan_screen.py`:

```python
def test_plan_screen_page_actions_clamp():
    snap = _snap(strategy_ranking=[
        RootScoreView(root_repr="ObtainItem(code='copper_boots', quantity=1)",
                      category="gear", score=2.5, step_repr="UpgradeEquipment(copper_boots)"),
    ])
    screen = PlanScreen(snap, _gd())
    assert screen._alt_page == 0
    screen.action_alt_prev()
    assert screen._alt_page == 0          # clamped at 0
    screen.action_alt_next()
    assert screen._alt_page == 0          # only one page → no advance
```

(Add `from artifactsmmo_cli.tui.screens.plan_screen import PlanScreen` to the test imports.)

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_tui/test_plan_summary.py -k pagination tests/test_tui/test_plan_screen.py -k page -v`
Expected: FAIL — `alt_page` not accepted; `action_alt_prev` missing.

- [ ] **Step 3: Add paging to `build_plan_summary`**

In `src/artifactsmmo_cli/tui/plan_summary.py`: add the const near the glyphs:

```python
ALT_PAGE_SIZE = 6
```

Change the signature tail and the stub-rendering block. Replace `plan_len: int = 0, suppressed_goals: list[str] | None = None,` line with:

```python
    plan_len: int = 0,
    suppressed_goals: list[str] | None = None,
    alt_page: int = 0,
    alt_page_size: int = ALT_PAGE_SIZE,
```

Replace the stub `for r in (...)` loop with a paginated slice + footer:

```python
    stubs = [x for x in ranking if x.root_repr != chosen_root]
    total = len(stubs)
    pages = max(1, (total + alt_page_size - 1) // alt_page_size)
    page = min(max(alt_page, 0), pages - 1)
    lo = page * alt_page_size
    hi = min(lo + alt_page_size, total)
    for r in stubs[lo:hi]:
        parts.append(Text(f"├─{STUB_GLYPH} {short_root(r.root_repr)}  {r.category}  {r.score:.2f}"))
        parts.append(_stub_line(r, game_data))

    if projected_cycles_to_max is not None:
        parts.append(Text(f"ETA ~{projected_cycles_to_max:.0f} cycles (estimate)", style="dim"))
    if suppressed_goals:
        parts.append(Text(f"└─ suppressed  {' · '.join(suppressed_goals)}", style="dim"))
    if pages > 1:
        parts.append(Text(f"   alternatives {lo + 1}–{hi} of {total}    "
                          f"[ prev   ] next", style="dim"))
    return Group(*parts)
```

(Delete the old standalone `for r in (...)` loop and the old trailing ETA/suppressed/return block this replaces — there must be exactly one of each.)

- [ ] **Step 4: Add page state + bindings to `PlanScreen`**

In `src/artifactsmmo_cli/tui/screens/plan_screen.py`:

Pass `alt_page` through the adapter — change `build_plan_detail` to take it:

```python
def build_plan_detail(snap: CycleSnapshot, game_data: GameData, alt_page: int = 0) -> RenderableType:
    """Adapter: pull the plan-relevant fields off the snapshot and render."""
    return build_plan_summary(
        snap.chosen_root, snap.strategy_ranking, snap.inventory, snap.bank_items,
        game_data, snap.projected_cycles_to_max,
        xp=snap.xp, max_xp=snap.max_xp, skill_xp=snap.skill_xp,
        task_code=snap.task_code, task_progress=snap.task_progress,
        task_total=snap.task_total, path_next_action=snap.path_next_action,
        plan_len=snap.plan_len, suppressed_goals=snap.suppressed_goals,
        alt_page=alt_page,
    )
```

Update the `PlanScreen` class — bindings, `_alt_page`, the two actions, and route both `compose`/`update_snapshot` through `_alt_page`:

```python
    BINDINGS = [
        ("escape", "dismiss", "Back"),
        ("p", "dismiss", "Back"),
        ("[", "alt_prev", "Prev alts"),
        ("]", "alt_next", "Next alts"),
    ]

    def __init__(self, snapshot: CycleSnapshot, game_data: GameData) -> None:
        super().__init__(id="plan-modal")
        self._snapshot = snapshot
        self._game_data = game_data
        self._alt_page = 0

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="plan-scroll"):
            yield Static(build_plan_detail(self._snapshot, self._game_data, self._alt_page),
                         id="plan-detail")

    def _rerender(self) -> None:
        self.query_one("#plan-detail", Static).update(
            build_plan_detail(self._snapshot, self._game_data, self._alt_page))

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self._snapshot = snap
        self._rerender()

    def _alt_pages(self) -> int:
        stubs = [r for r in self._snapshot.strategy_ranking
                 if r.root_repr != self._snapshot.chosen_root]
        return max(1, (len(stubs) + ALT_PAGE_SIZE - 1) // ALT_PAGE_SIZE)

    def action_alt_prev(self) -> None:
        self._alt_page = max(0, self._alt_page - 1)
        self._rerender()

    def action_alt_next(self) -> None:
        self._alt_page = min(self._alt_pages() - 1, self._alt_page + 1)
        self._rerender()
```

Add the import at the top of `plan_screen.py`:

```python
from artifactsmmo_cli.tui.plan_summary import ALT_PAGE_SIZE, build_plan_summary
```

Note: `action_alt_prev`/`action_alt_next` call `_rerender`, which queries `#plan-detail`. In the unit test the screen isn't mounted, so guard `_rerender` against a missing node is NOT needed — the test asserts `_alt_page` only and the single-page snapshot makes `action_alt_next` a no-op (page stays 0, `_rerender` still runs `query_one`). To keep `_rerender` callable off-mount, wrap the query: if there are zero pages-worth changes the value is unchanged but `query_one` would raise off-mount. Instead, have the actions update `_alt_page` first and only `_rerender` when mounted:

```python
    def _rerender(self) -> None:
        if self.is_mounted:
            self.query_one("#plan-detail", Static).update(
                build_plan_detail(self._snapshot, self._game_data, self._alt_page))
```

(`Screen.is_mounted` is provided by Textual; off-mount unit tests skip the DOM query while still exercising the clamp logic.)

- [ ] **Step 5: Run the paging tests**

Run: `uv run pytest tests/test_tui/test_plan_summary.py tests/test_tui/test_plan_screen.py -v`
Expected: PASS (all)

- [ ] **Step 6: Gate + commit**

Run: `uv run pytest && uv run mypy src && uv run ruff check`
Expected: all green, 100% coverage.

```bash
git add src/artifactsmmo_cli/tui/plan_summary.py src/artifactsmmo_cli/tui/screens/plan_screen.py tests/test_tui/test_plan_summary.py tests/test_tui/test_plan_screen.py
git commit -m "feat(tui): paginate plan-flowchart alternatives ([ / ] keys)"
```

---

### Task 5: Confirm no formal-gate impact + update memory

**Files:**
- Read-only: `formal/` (grep), memory dir.

- [ ] **Step 1: Confirm `cycle_snapshot` / TUI views are not in the formal-diff path**

Run: `grep -rln "cycle_snapshot\|RootScoreView\|plan_summary\|log_pane" formal/ || echo "NONE"`
Expected: `NONE` (these are TUI consumers; no Lean oracle / differential / mutation anchor references them). If any hit appears, STOP and report — the "no formal impact" assumption is wrong and the change needs lockstep model work.

- [ ] **Step 2: Full suite final gate**

Run: `uv run pytest && uv run mypy src && uv run ruff check`
Expected: 0 errors, 0 warnings, 0 skipped, 100% coverage.

- [ ] **Step 3: Update the auto-memory**

Mark the TUI-backlog items done. Update `project_dead_cooldown_branches.md` (both findings already fixed in code — note resolved) and add a one-line pointer for the flowchart/why-log work in `MEMORY.md`. (Memory edits are not committed to git.)

- [ ] **Step 4: Finish the branch**

Invoke the `superpowers:finishing-a-development-branch` skill to choose merge / PR / cleanup.

---

## Self-Review

**Spec coverage:**
- Component 1 (live "why" line, omit on discretionary, pure `build_log_lines`) → Task 2. ✓
- Component 2 flowchart (objective root, `●` chosen expand, `○` stubs, suppressed, glyphs) → Task 3. ✓
- Pagination (`[`/`]`, page size 6, page-aware pure builder, footer) → Task 4. ✓
- Data plumb (`RootScoreView += step_repr`, player.py) → Task 1. ✓
- Shared `short_root` helper → Task 1. ✓
- No formal-gate impact confirmation → Task 5. ✓
- Testing / 100% coverage → every task gate + Task 5. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code; every test step shows the test body. ✓

**Type consistency:** `short_root(str)->str`, `build_log_lines(CycleSnapshot)->list[str]`, `RootScoreView.step_repr: str`, `ALT_PAGE_SIZE` const, `build_plan_summary(..., alt_page, alt_page_size)`, `PlanScreen._alt_page` / `action_alt_prev` / `action_alt_next` / `_alt_pages` / `_rerender` — names match across Tasks 1→4. ✓

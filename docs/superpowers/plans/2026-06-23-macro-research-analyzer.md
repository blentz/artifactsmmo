# Macro-Candidate Research Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A read-only research tool over the existing `learning.db` that quantifies where expensive A* search still occurs and which long-horizon progression sequences (level N→M runs, skill-grind runs) recur across characters/sessions — producing the evidence to design the future macro-replay engine's key + promotion threshold.

**Architecture:** Reuse `trace_stats.load_cycles_from_db` to stream `Cycle` rows (all characters), project them to a light `CycleRow`, then run a pipeline of pure functions: per-goal search-cost aggregation → progression-band segmentation (by level and by skill-grind goal) → chain canonicalization + recurrence/value scoring → markdown report. A thin `macro-research` CLI command wires it together. The realized per-cycle trajectory in `cycles` IS the executed progression, so v1 needs no new instrumentation; `plan_body_log` is left for a v2 enrichment.

**Tech Stack:** Python 3.13, `uv`, SQLModel/SQLAlchemy (existing learning store), Typer (existing CLI), pytest.

## Global Constraints

- Run all Python via `uv run` (e.g. `uv run pytest`, `uv run mypy`).
- No inline imports; imports at top. No `...` imports. No `if TYPE_CHECKING`. Never catch `Exception`.
- One behavioral class per file; cohesive pure dataclass/function groups may share a module.
- Tests: 0 errors, 0 warnings, 0 skipped, 100% coverage. All tests under `tests/`.
- This is a **read-only research tool** — it must never write to or mutate `learning.db`, and it is **not** in the bot's decision/planning path. **No formal-gate impact** (`formal/gate.sh` need not be re-run for proof reasons; the repo's normal pytest/mypy/ruff pre-commit still applies).
- Default DB path mirrors the rest of the CLI: `~/.cache/artifactsmmo/learning.db` (see `commands/plan.py::_default_learn_db_path`).
- mypy strict is enforced by the pre-commit hook; annotate fully.

**Key existing code to reuse (verbatim signatures):**
- `trace_stats.load_cycles_from_db(db_path, character=None, session_id=None, since=None, until=None, limit=None) -> list[Cycle]` (`ai/trace_stats.py:271`) — returns rows ordered by `ts asc`; pass `character=None` for all characters.
- `Cycle` fields used: `character, session_id, cycle_index, level, selected_goal, action_class, planner_nodes, planner_timed_out` (`ai/learning/models.py`).
- CLI registration pattern: `app.command("name", help="…")(fn)` in `src/artifactsmmo_cli/main.py` (see `plan`/`play`).

---

### Task 1: `CycleRow` projection + reader

**Files:**
- Create: `src/artifactsmmo_cli/ai/macro/cycle_row.py`
- Create: `src/artifactsmmo_cli/ai/macro/__init__.py` (empty)
- Create: `src/artifactsmmo_cli/ai/macro/reader.py`
- Test: `tests/test_ai/macro/test_reader.py`
- Create: `tests/test_ai/macro/__init__.py` (empty)

**Interfaces:**
- Produces:
  - `CycleRow` (frozen dataclass): `character: str`, `session_id: str`, `cycle_index: int`, `level: int | None`, `selected_goal: str | None`, `action_class: str | None`, `planner_nodes: int | None`, `planner_timed_out: bool | None`.
  - `reader.load_cycle_rows(db_path: str) -> list[CycleRow]` — all characters, projected, preserving `load_cycles_from_db`'s `ts asc` order.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/macro/test_reader.py
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.macro.reader import load_cycle_rows


def _seed(store, **kw):
    base = dict(ts=kw.pop("ts"), session_id="s1", cycle_index=kw.pop("ci"),
                character="hero", outcome="ok")
    store.record_cycle(Cycle(**{**base, **kw}))


def test_load_cycle_rows_projects_and_orders(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "l.db"), character="hero")
    store.start_session()
    _seed(store, ts="2026-06-23T00:00:02", ci=1, level=2,
          selected_goal="GrindCharacterXP(chicken)", action_class="FightAction",
          planner_nodes=12, planner_timed_out=False)
    _seed(store, ts="2026-06-23T00:00:01", ci=0, level=1,
          selected_goal="GrindCharacterXP(chicken)", action_class="FightAction",
          planner_nodes=8, planner_timed_out=False)
    rows = load_cycle_rows(str(tmp_path / "l.db"))
    assert [r.cycle_index for r in rows] == [0, 1]      # ts asc order preserved
    assert rows[0].level == 1 and rows[1].planner_nodes == 12
    assert rows[0].selected_goal == "GrindCharacterXP(chicken)"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/macro/test_reader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.macro.reader'`

- [ ] **Step 3: Implement**

```python
# src/artifactsmmo_cli/ai/macro/cycle_row.py
"""Light projection of a learning-store Cycle for macro-research analysis,
decoupled from the SQLModel ORM so the pure analysis cores test without a DB."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CycleRow:
    character: str
    session_id: str
    cycle_index: int
    level: int | None
    selected_goal: str | None
    action_class: str | None
    planner_nodes: int | None
    planner_timed_out: bool | None
```

```python
# src/artifactsmmo_cli/ai/macro/reader.py
"""Read-only loader: stream all-character Cycle rows and project to CycleRow."""

from artifactsmmo_cli.ai.macro.cycle_row import CycleRow
from artifactsmmo_cli.ai.trace_stats import load_cycles_from_db


def load_cycle_rows(db_path: str) -> list[CycleRow]:
    """All cycles across every character, ts-asc, projected to CycleRow."""
    return [
        CycleRow(
            character=c.character,
            session_id=c.session_id,
            cycle_index=c.cycle_index,
            level=c.level,
            selected_goal=c.selected_goal,
            action_class=c.action_class,
            planner_nodes=c.planner_nodes,
            planner_timed_out=c.planner_timed_out,
        )
        for c in load_cycles_from_db(db_path, character=None)
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/macro/test_reader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/macro/ tests/test_ai/macro/
git commit -m "feat(macro-research): CycleRow projection + read-only cycle loader"
```

---

### Task 2: search-cost aggregation

**Files:**
- Create: `src/artifactsmmo_cli/ai/macro/cost.py`
- Test: `tests/test_ai/macro/test_cost.py`

**Interfaces:**
- Consumes: `CycleRow` (Task 1).
- Produces:
  - `parse_goal_type(selected_goal: str | None) -> str` — leading token before `(`, or `"<none>"`.
  - `CostStat` (frozen dataclass): `goal_type: str`, `n_cycles: int`, `total_nodes: int`, `mean_nodes: float`, `timeouts: int`.
  - `cost_by_goal_type(rows: list[CycleRow]) -> list[CostStat]` — one stat per goal type, sorted by `total_nodes` desc.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/macro/test_cost.py
from artifactsmmo_cli.ai.macro.cost import CostStat, cost_by_goal_type, parse_goal_type
from artifactsmmo_cli.ai.macro.cycle_row import CycleRow


def _row(goal, nodes, timed_out=False):
    return CycleRow("hero", "s1", 0, 1, goal, "A", nodes, timed_out)


def test_parse_goal_type():
    assert parse_goal_type("GatherMaterials(copper_ring, {x: 6})") == "GatherMaterials"
    assert parse_goal_type("PursueTask") == "PursueTask"
    assert parse_goal_type(None) == "<none>"


def test_cost_by_goal_type_aggregates_and_sorts():
    rows = [
        _row("PursueTask(t1)", 1000, True),
        _row("PursueTask(t2)", 3000),
        _row("GrindCharacterXP(chicken)", 10),
        _row("GrindCharacterXP(chicken)", 30),
        _row("GatherMaterials(x)", None),   # None nodes treated as 0
    ]
    stats = cost_by_goal_type(rows)
    assert stats[0].goal_type == "PursueTask"          # highest total_nodes first
    assert stats[0].total_nodes == 4000
    assert stats[0].n_cycles == 2 and stats[0].timeouts == 1
    assert stats[0].mean_nodes == 2000.0
    gm = next(s for s in stats if s.goal_type == "GatherMaterials")
    assert gm.total_nodes == 0 and gm.mean_nodes == 0.0
```

- [ ] **Step 2: Run test, expect fail** — `ModuleNotFoundError ...macro.cost`.

- [ ] **Step 3: Implement**

```python
# src/artifactsmmo_cli/ai/macro/cost.py
"""Per-goal-type A* search-cost aggregation over realized cycles."""

from collections import defaultdict
from dataclasses import dataclass

from artifactsmmo_cli.ai.macro.cycle_row import CycleRow


def parse_goal_type(selected_goal: str | None) -> str:
    if not selected_goal:
        return "<none>"
    return selected_goal.split("(", 1)[0]


@dataclass(frozen=True)
class CostStat:
    goal_type: str
    n_cycles: int
    total_nodes: int
    mean_nodes: float
    timeouts: int


def cost_by_goal_type(rows: list[CycleRow]) -> list[CostStat]:
    nodes: dict[str, int] = defaultdict(int)
    counts: dict[str, int] = defaultdict(int)
    timeouts: dict[str, int] = defaultdict(int)
    for r in rows:
        gt = parse_goal_type(r.selected_goal)
        nodes[gt] += r.planner_nodes or 0
        counts[gt] += 1
        if r.planner_timed_out:
            timeouts[gt] += 1
    stats = [
        CostStat(gt, counts[gt], nodes[gt],
                 nodes[gt] / counts[gt] if counts[gt] else 0.0, timeouts[gt])
        for gt in counts
    ]
    return sorted(stats, key=lambda s: s.total_nodes, reverse=True)
```

- [ ] **Step 4: Run test, expect pass.**

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/macro/cost.py tests/test_ai/macro/test_cost.py
git commit -m "feat(macro-research): per-goal-type search-cost aggregation"
```

---

### Task 3: progression-band segmentation

**Files:**
- Create: `src/artifactsmmo_cli/ai/macro/segmentation.py`
- Test: `tests/test_ai/macro/test_segmentation.py`

**Interfaces:**
- Consumes: `CycleRow` (Task 1), `parse_goal_type` (Task 2).
- Produces:
  - `Band` (frozen dataclass): `character: str`, `session_id: str`, `kind: str`, `key: str`, `rows: tuple[CycleRow, ...]`.
  - `segment_bands(rows: list[CycleRow], kind: str) -> list[Band]` — `kind="level"` cuts maximal consecutive-`cycle_index` runs of equal `level` within a `(character, session_id)`; `kind="skill"` keeps only cycles whose goal type is `"LevelSkill"` and cuts runs of equal goal target string. Bands of length 0 are never emitted. `kind` other than these two raises `ValueError`.

Band `key` format: `"level=<n>"` for level bands; the full `selected_goal` repr (e.g. `"LevelSkill(mining->5)"`) for skill bands.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/macro/test_segmentation.py
import pytest

from artifactsmmo_cli.ai.macro.cycle_row import CycleRow
from artifactsmmo_cli.ai.macro.segmentation import Band, segment_bands


def _r(ci, level, goal, char="hero", sess="s1"):
    return CycleRow(char, sess, ci, level, goal, "A", 1, False)


def test_level_bands_cut_on_level_change():
    rows = [_r(0, 1, "G"), _r(1, 1, "G"), _r(2, 2, "G"), _r(3, 1, "G")]
    bands = segment_bands(rows, "level")
    assert [b.key for b in bands] == ["level=1", "level=2", "level=1"]
    assert len(bands[0].rows) == 2


def test_level_bands_separated_by_session_and_character():
    rows = [_r(0, 1, "G", sess="s1"), _r(0, 1, "G", sess="s2"),
            _r(0, 1, "G", char="rob")]
    bands = segment_bands(rows, "level")
    assert len(bands) == 3  # no band spans two sessions or two characters


def test_skill_bands_only_levelskill_goals():
    rows = [_r(0, 3, "GrindCharacterXP(chicken)"),
            _r(1, 3, "LevelSkill(mining->5)"),
            _r(2, 3, "LevelSkill(mining->5)"),
            _r(3, 3, "LevelSkill(woodcutting->5)")]
    bands = segment_bands(rows, "skill")
    assert [b.key for b in bands] == ["LevelSkill(mining->5)", "LevelSkill(woodcutting->5)"]
    assert len(bands[0].rows) == 2


def test_unknown_kind_raises():
    with pytest.raises(ValueError, match="unknown band kind"):
        segment_bands([], "bogus")
```

- [ ] **Step 2: Run test, expect fail** — `ModuleNotFoundError ...macro.segmentation`.

- [ ] **Step 3: Implement**

```python
# src/artifactsmmo_cli/ai/macro/segmentation.py
"""Cut the realized cycle trajectory into progression bands: runs at one
character level, or runs grinding one skill target. Bands never span a
session or character boundary."""

from dataclasses import dataclass
from itertools import groupby

from artifactsmmo_cli.ai.macro.cost import parse_goal_type
from artifactsmmo_cli.ai.macro.cycle_row import CycleRow


@dataclass(frozen=True)
class Band:
    character: str
    session_id: str
    kind: str
    key: str
    rows: tuple[CycleRow, ...]


def _segment_key(row: CycleRow, kind: str) -> str | None:
    """The band key for a row, or None if the row is excluded from this kind."""
    if kind == "level":
        return f"level={row.level}"
    if kind == "skill":
        if parse_goal_type(row.selected_goal) != "LevelSkill":
            return None
        return row.selected_goal
    raise ValueError(f"unknown band kind: {kind}")


def segment_bands(rows: list[CycleRow], kind: str) -> list[Band]:
    if kind not in ("level", "skill"):
        raise ValueError(f"unknown band kind: {kind}")
    bands: list[Band] = []
    by_owner = sorted(rows, key=lambda r: (r.character, r.session_id, r.cycle_index))
    for (char, sess), session_rows in groupby(
        by_owner, key=lambda r: (r.character, r.session_id)
    ):
        current_key: str | None = None
        run: list[CycleRow] = []

        def flush() -> None:
            if current_key is not None and run:
                bands.append(Band(char, sess, kind, current_key, tuple(run)))

        for r in session_rows:
            k = _segment_key(r, kind)
            if k != current_key:
                flush()
                run = []
                current_key = k
            if k is not None:
                run.append(r)
        flush()
    return bands
```

- [ ] **Step 4: Run test, expect pass.**

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/macro/segmentation.py tests/test_ai/macro/test_segmentation.py
git commit -m "feat(macro-research): level + skill progression-band segmentation"
```

---

### Task 4: chain canonicalization + recurrence/value scoring

**Files:**
- Create: `src/artifactsmmo_cli/ai/macro/scoring.py`
- Test: `tests/test_ai/macro/test_scoring.py`

**Interfaces:**
- Consumes: `Band` (Task 3), `parse_goal_type` (Task 2).
- Produces:
  - `canonical_chain(band: Band) -> tuple[tuple[str, str], ...]` — the band's `(goal_type, action_class)` sequence with consecutive duplicates collapsed. `action_class` `None` → `"<none>"`.
  - `MacroCandidate` (frozen dataclass): `kind: str`, `chain: tuple[tuple[str, str], ...]`, `occurrences: int`, `distinct_characters: int`, `total_nodes: int`, `value: int`, `example_keys: tuple[str, ...]`.
  - `score_candidates(bands: list[Band]) -> list[MacroCandidate]` — group bands by `(kind, canonical_chain)`; `occurrences` = bands in group; `distinct_characters` = distinct band characters; `total_nodes` = summed `planner_nodes` over all rows of all bands in the group; `value = occurrences * total_nodes`; `example_keys` = up to 3 distinct band keys. Sorted by `value` desc, then `occurrences` desc.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/macro/test_scoring.py
from artifactsmmo_cli.ai.macro.cycle_row import CycleRow
from artifactsmmo_cli.ai.macro.scoring import canonical_chain, score_candidates
from artifactsmmo_cli.ai.macro.segmentation import Band


def _row(goal, action, nodes, char="hero"):
    return CycleRow(char, "s1", 0, 1, goal, action, nodes, False)


def _band(key, rows, char="hero", kind="level"):
    return Band(char, "s1", kind, key, tuple(rows))


def test_canonical_chain_collapses_consecutive_dupes():
    band = _band("level=1", [
        _row("GrindCharacterXP(chicken)", "FightAction", 5),
        _row("GrindCharacterXP(chicken)", "FightAction", 5),
        _row("GatherMaterials(ash)", "GatherAction", 2),
    ])
    assert canonical_chain(band) == (
        ("GrindCharacterXP", "FightAction"),
        ("GatherMaterials", "GatherAction"),
    )


def test_score_groups_and_ranks_by_value():
    # chain A recurs across 2 characters (value = 2 * total_nodes)
    a_rows = [_row("PursueTask(t)", "CraftAction", 1000)]
    band_a1 = _band("level=2", a_rows, char="hero")
    band_a2 = _band("level=2", [_row("PursueTask(t)", "CraftAction", 1000, char="rob")], char="rob")
    # chain B occurs once, cheap
    band_b = _band("level=3", [_row("GrindCharacterXP(c)", "FightAction", 5)])
    cands = score_candidates([band_a1, band_a2, band_b])
    assert cands[0].chain == (("PursueTask", "CraftAction"),)
    assert cands[0].occurrences == 2
    assert cands[0].distinct_characters == 2
    assert cands[0].total_nodes == 2000
    assert cands[0].value == 4000          # 2 occ * 2000 nodes
    assert cands[1].value == 5             # cheap chain ranks last
```

- [ ] **Step 2: Run test, expect fail** — `ModuleNotFoundError ...macro.scoring`.

- [ ] **Step 3: Implement**

```python
# src/artifactsmmo_cli/ai/macro/scoring.py
"""Canonicalize progression bands into goal/action chains and rank recurring
chains by macro value (recurrence x search-cost they incurred)."""

from collections import defaultdict
from dataclasses import dataclass

from artifactsmmo_cli.ai.macro.cost import parse_goal_type
from artifactsmmo_cli.ai.macro.segmentation import Band

_Chain = tuple[tuple[str, str], ...]


def canonical_chain(band: Band) -> _Chain:
    steps: list[tuple[str, str]] = []
    for r in band.rows:
        step = (parse_goal_type(r.selected_goal), r.action_class or "<none>")
        if not steps or steps[-1] != step:
            steps.append(step)
    return tuple(steps)


@dataclass(frozen=True)
class MacroCandidate:
    kind: str
    chain: _Chain
    occurrences: int
    distinct_characters: int
    total_nodes: int
    value: int
    example_keys: tuple[str, ...]


def score_candidates(bands: list[Band]) -> list[MacroCandidate]:
    groups: dict[tuple[str, _Chain], list[Band]] = defaultdict(list)
    for b in bands:
        groups[(b.kind, canonical_chain(b))].append(b)
    candidates: list[MacroCandidate] = []
    for (kind, chain), group in groups.items():
        total_nodes = sum((r.planner_nodes or 0) for b in group for r in b.rows)
        chars = {b.character for b in group}
        keys: list[str] = []
        for b in group:
            if b.key not in keys:
                keys.append(b.key)
        candidates.append(MacroCandidate(
            kind=kind, chain=chain, occurrences=len(group),
            distinct_characters=len(chars), total_nodes=total_nodes,
            value=len(group) * total_nodes, example_keys=tuple(keys[:3]),
        ))
    return sorted(candidates, key=lambda c: (c.value, c.occurrences), reverse=True)
```

- [ ] **Step 4: Run test, expect pass.**

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/macro/scoring.py tests/test_ai/macro/test_scoring.py
git commit -m "feat(macro-research): chain canonicalization + macro value scoring"
```

---

### Task 5: goal-repr volatility + markdown report

**Files:**
- Create: `src/artifactsmmo_cli/ai/macro/report.py`
- Test: `tests/test_ai/macro/test_report.py`

**Interfaces:**
- Consumes: `CycleRow` (Task 1), `parse_goal_type` (Task 2), `CostStat` (Task 2), `MacroCandidate` (Task 4).
- Produces:
  - `goal_repr_variants(rows: list[CycleRow]) -> dict[str, list[str]]` — goal type → sorted distinct full `selected_goal` reprs seen. Shows which fields vary (the key-canonicalization evidence).
  - `format_report(cost: list[CostStat], candidates: list[MacroCandidate], variants: dict[str, list[str]], top_n: int) -> str` — a markdown report: a search-cost table, the top-`n` macro candidates (kind, value, occurrences, distinct characters, total nodes, chain, example keys), and the per-goal-type repr-variant listing.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/macro/test_report.py
from artifactsmmo_cli.ai.macro.cost import CostStat
from artifactsmmo_cli.ai.macro.cycle_row import CycleRow
from artifactsmmo_cli.ai.macro.report import format_report, goal_repr_variants
from artifactsmmo_cli.ai.macro.scoring import MacroCandidate


def test_goal_repr_variants_dedupes_and_sorts():
    rows = [
        CycleRow("h", "s", 0, 1, "GatherMaterials(ring, {ore: 6})", "A", 1, False),
        CycleRow("h", "s", 1, 1, "GatherMaterials(ring, {ore: 3})", "A", 1, False),
        CycleRow("h", "s", 2, 1, "GatherMaterials(ring, {ore: 6})", "A", 1, False),
    ]
    v = goal_repr_variants(rows)
    assert v["GatherMaterials"] == [
        "GatherMaterials(ring, {ore: 3})", "GatherMaterials(ring, {ore: 6})",
    ]


def test_format_report_contains_sections():
    cost = [CostStat("PursueTask", 2, 4000, 2000.0, 1)]
    cand = [MacroCandidate("level", (("PursueTask", "CraftAction"),), 2, 2, 4000, 8000,
                           ("level=2",))]
    variants = {"PursueTask": ["PursueTask(t1)", "PursueTask(t2)"]}
    md = format_report(cost, cand, variants, top_n=10)
    assert "# Macro-candidate research" in md
    assert "PursueTask" in md and "4000" in md      # cost row
    assert "value" in md.lower()                     # candidate table header
    assert "8000" in md                              # candidate value
    assert "PursueTask(t1)" in md                    # variants section
```

- [ ] **Step 2: Run test, expect fail** — `ModuleNotFoundError ...macro.report`.

- [ ] **Step 3: Implement**

```python
# src/artifactsmmo_cli/ai/macro/report.py
"""Render the macro-research findings as a markdown report."""

from artifactsmmo_cli.ai.macro.cost import CostStat, parse_goal_type
from artifactsmmo_cli.ai.macro.cycle_row import CycleRow
from artifactsmmo_cli.ai.macro.scoring import MacroCandidate


def goal_repr_variants(rows: list[CycleRow]) -> dict[str, list[str]]:
    seen: dict[str, set[str]] = {}
    for r in rows:
        if r.selected_goal is None:
            continue
        seen.setdefault(parse_goal_type(r.selected_goal), set()).add(r.selected_goal)
    return {gt: sorted(v) for gt, v in seen.items()}


def _chain_str(chain: tuple[tuple[str, str], ...]) -> str:
    return " -> ".join(f"{g}/{a}" for g, a in chain)


def format_report(cost: list[CostStat], candidates: list[MacroCandidate],
                  variants: dict[str, list[str]], top_n: int) -> str:
    lines: list[str] = ["# Macro-candidate research", ""]

    lines.append("## A* search cost by goal type")
    lines.append("")
    lines.append("| goal type | cycles | total nodes | mean nodes | timeouts |")
    lines.append("|---|---|---|---|---|")
    for s in cost:
        lines.append(
            f"| {s.goal_type} | {s.n_cycles} | {s.total_nodes} | "
            f"{s.mean_nodes:.1f} | {s.timeouts} |")
    lines.append("")

    lines.append(f"## Top {top_n} macro candidates (by value = occurrences x nodes)")
    lines.append("")
    lines.append("| kind | value | occurrences | distinct chars | total nodes | chain | example keys |")
    lines.append("|---|---|---|---|---|---|---|")
    for c in candidates[:top_n]:
        lines.append(
            f"| {c.kind} | {c.value} | {c.occurrences} | {c.distinct_characters} | "
            f"{c.total_nodes} | {_chain_str(c.chain)} | {', '.join(c.example_keys)} |")
    lines.append("")

    lines.append("## Goal-repr variants (key-canonicalization evidence)")
    lines.append("")
    for gt in sorted(variants):
        lines.append(f"- **{gt}** ({len(variants[gt])} distinct):")
        for repr_str in variants[gt]:
            lines.append(f"  - `{repr_str}`")
    lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test, expect pass.**

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/macro/report.py tests/test_ai/macro/test_report.py
git commit -m "feat(macro-research): goal-repr volatility + markdown report"
```

---

### Task 6: `macro-research` CLI command

**Files:**
- Create: `src/artifactsmmo_cli/commands/macro_research.py`
- Modify: `src/artifactsmmo_cli/main.py` (register the command)
- Test: `tests/test_commands/test_macro_research.py`

**Interfaces:**
- Consumes: `load_cycle_rows` (Task 1), `cost_by_goal_type` (Task 2), `segment_bands` (Task 3), `score_candidates` (Task 4), `goal_repr_variants`/`format_report` (Task 5).
- Produces: `macro_research(db: str | None, out: str | None, top_n: int) -> None` — loads rows, runs the pipeline over both band kinds (level + skill), writes the markdown report to `out` (or prints to stdout), and prints a one-line summary.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_commands/test_macro_research.py
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.commands.macro_research import macro_research


def _seed_progression(store, char):
    store.start_session()
    for ci, (lvl, goal) in enumerate([
        (1, "GrindCharacterXP(chicken)"), (1, "GrindCharacterXP(chicken)"),
        (2, "PursueTask(t)"),
    ]):
        store.record_cycle(Cycle(
            ts=f"2026-06-23T00:00:0{ci}", session_id="s", cycle_index=ci,
            character=char, outcome="ok", level=lvl, selected_goal=goal,
            action_class="FightAction", planner_nodes=100, planner_timed_out=False))


def test_macro_research_writes_report(tmp_path):
    db = str(tmp_path / "l.db")
    store = LearningStore(db_path=db, character="hero")
    _seed_progression(store, "hero")
    out = tmp_path / "macro-report.md"
    macro_research(db=db, out=str(out), top_n=10)
    text = out.read_text()
    assert "# Macro-candidate research" in text
    assert "GrindCharacterXP" in text


def test_macro_research_prints_when_no_out(tmp_path, capsys):
    db = str(tmp_path / "l.db")
    store = LearningStore(db_path=db, character="hero")
    _seed_progression(store, "hero")
    macro_research(db=db, out=None, top_n=5)
    assert "# Macro-candidate research" in capsys.readouterr().out
```

- [ ] **Step 2: Run test, expect fail** — `ModuleNotFoundError ...commands.macro_research`.

- [ ] **Step 3: Implement the command**

```python
# src/artifactsmmo_cli/commands/macro_research.py
"""`artifactsmmo macro-research` — read-only analysis of learning.db to find
recurring long-horizon progression chains and where A* search still costs."""

from pathlib import Path

import typer

from artifactsmmo_cli.ai.macro.cost import cost_by_goal_type
from artifactsmmo_cli.ai.macro.reader import load_cycle_rows
from artifactsmmo_cli.ai.macro.report import format_report, goal_repr_variants
from artifactsmmo_cli.ai.macro.scoring import score_candidates
from artifactsmmo_cli.ai.macro.segmentation import segment_bands


def _default_db_path() -> str:
    return str(Path.home() / ".cache" / "artifactsmmo" / "learning.db")


def macro_research(
    db: str | None = typer.Option(None, "--db", help="learning.db path"),
    out: str | None = typer.Option(None, "--out", help="write report to file"),
    top_n: int = typer.Option(20, "--top-n", help="macro candidates to show"),
) -> None:
    rows = load_cycle_rows(db or _default_db_path())
    cost = cost_by_goal_type(rows)
    bands = segment_bands(rows, "level") + segment_bands(rows, "skill")
    candidates = score_candidates(bands)
    report = format_report(cost, candidates, goal_repr_variants(rows), top_n)
    if out is not None:
        Path(out).write_text(report)
        print(f"Wrote macro-research report to {out} "
              f"({len(rows)} cycles, {len(candidates)} candidate chains)")
    else:
        print(report)
```

- [ ] **Step 4: Register in `main.py`**

Add the import beside the other command imports:

```python
from artifactsmmo_cli.commands.macro_research import macro_research as macro_research_command
```

Add the registration beside `app.command("plan", ...)`:

```python
app.command("macro-research", help="Analyze learning.db for recurring progression macros (read-only)")(macro_research_command)
```

- [ ] **Step 5: Run tests, expect pass**

Run: `uv run pytest tests/test_commands/test_macro_research.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/commands/macro_research.py src/artifactsmmo_cli/main.py tests/test_commands/test_macro_research.py
git commit -m "feat(macro-research): macro-research CLI command"
```

---

### Task 7: coverage + suite verification

**Files:** none (verification only)

- [ ] **Step 1: Full suite with coverage**

Run: `uv run pytest --cov=src/artifactsmmo_cli --cov-report=term-missing -q`
Expected: 0 errors, 0 warnings, 0 skipped, 100% coverage. Add focused real tests for any uncovered new line in the `ai/macro/` package or the command (e.g. an empty-DB run of `macro_research`, a `cost_by_goal_type([])` empty case). No mocking the unit under test.

- [ ] **Step 2: Type + lint check**

Run: `uv run mypy src/artifactsmmo_cli/ai/macro/ src/artifactsmmo_cli/commands/macro_research.py`
Expected: no issues.

- [ ] **Step 3: Confirm no formal-gate involvement**

This feature adds no decision logic and is not in the planning path. `formal/gate.sh` is NOT required for proof reasons. Confirm `git diff --stat formal/` is empty (the feature must not touch `formal/`).

- [ ] **Step 4: Commit any added coverage tests**

```bash
git add tests/
git commit -m "test(macro-research): close coverage gaps"
```

---

## Self-Review

**Spec coverage:**
- Read-only DB reader (all characters) → Task 1. ✓
- Search-cost report ("research plan costs") → Task 2. ✓
- Progression-band segmentation (level + skill, the long-horizon focus) → Task 3. ✓
- Recurrence + value scoring (cross-character signal) → Task 4. ✓
- Goal-repr volatility (key-canonicalization evidence) + report → Task 5. ✓
- CLI wiring + report output → Task 6. ✓
- Coverage/verification; no formal gate → Task 7. ✓
- Macro-replay ENGINE → NOT in this plan (it is the evidence-driven follow-on, designed from this analyzer's output). ✓ intentional.

**Placeholder scan:** none — every code step is complete.

**Type consistency:** `CycleRow` field set identical across Tasks 1–6; `parse_goal_type` reused from Task 2 in Tasks 3/5; `Band`/`MacroCandidate`/`CostStat` field names consistent between producing task and `report.py`/CLI consumers; `segment_bands(rows, kind)` and `score_candidates(bands)` signatures stable across Tasks 3/4/6.

**Known scope note:** v1 analyzes the realized `cycles` trajectory (the executed progression). `plan_body_log` (richer per-replan bodies) is intentionally deferred to a v2 enrichment — flagged so a reviewer does not treat its absence as a gap. Skill bands key off the `LevelSkill` goal repr rather than the XP curve; this captures the user's "grind skill to level 5" case directly without needing cumulative-XP reconstruction.

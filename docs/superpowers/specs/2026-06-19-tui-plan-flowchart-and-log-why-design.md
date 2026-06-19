# TUI plan flowchart + live "why" log — design

Date: 2026-06-19
Source backlog: `docs/PLAN_tui_backlog.md` (items 1 + 2)

## Problem

Two observability gaps in the TUI, both over data the cycle snapshot already
carries (no new decision logic, so no formal-gate impact):

1. **BUG** — the per-cycle strategy ranking (chosen root / category / score and
   the alternatives) is recorded in the snapshot and trace jsonl but is **not**
   surfaced in the always-on live log pane. Diagnosing the copper_ring /
   copper_armor cannibalization wobble (2026-06-18) required parsing the raw
   trace to see *why* a goal was chosen.
2. **FEATURE** — the plan modal (`tui/screens/plan_screen.py` /
   `tui/plan_summary.py`) shows a flat COMMITTED + ALTERNATIVES list. It should
   visualize the plan as a **flowchart**: objective at the root, the chosen path
   expanded, every non-chosen path shown as a stub, with the alternatives
   paginated.

Both read fields that already exist on `CycleSnapshot`; the only data change is
carrying `step_repr` onto the ranking view model.

## Data available (no decision logic touched)

`CycleSnapshot` (`ai/cycle_snapshot.py`) already carries: `chosen_root`,
`strategy_ranking: list[RootScoreView]` (`root_repr`, `category`, `score`),
`suppressed_goals`, `plan_len`, `path_next_action`, `selected_goal`, plus the
inventory/bank/xp/skill/task fields `plan_summary` already consumes.

`RootScore` (`ai/tiers/strategy.py`) — the source — additionally has
`step_repr`. The TUI view model `RootScoreView` currently drops it.

## Component 1 — live log pane (`tui/widgets/log_pane.py`)

Two lines per cycle:

- **Line 1** (unchanged): `ts  c{cycle}  {selected_goal}  {action}  {outcome}`.
- **Line 2** (new, dim, indented): the "why" line —
  `   why: {category} {score:.2f}  alt: {alt1} {s1:.2f} | {alt2} {s2:.2f}`
  - chosen entry = the `strategy_ranking` row whose `root_repr == chosen_root`;
    show its `category` word + `score`.
  - `alt1`/`alt2` = the next two ranking rows by score, excluding the chosen
    one, rendered with `short_root` + score; the `alt:` segment is omitted when
    there are no alternatives.
  - **Omit line 2 entirely** when `chosen_root is None` or `strategy_ranking` is
    empty (discretionary / no-objective cycles) — keeps the live pane quiet.

Refactor for testability: extract a pure
`build_log_lines(snap: CycleSnapshot) -> list[str]` (mirrors
`log_screen.build_debug_log_line`); `update_snapshot` becomes a thin loop that
`self.write`s each returned line. This makes the format unit-testable with no
Textual app harness.

## Component 2 — plan flowchart (`tui/plan_summary.py`, `tui/screens/plan_screen.py`)

Replace the flat COMMITTED/ALTERNATIVES layout with a single flowchart tree.

```
OBJECTIVE  reach level 50
│
├─● ReachCharLevel(6)          grind  1.80   ◄ CHOSEN
│    step  FightAction(chicken)
│    plan  3 actions   next chicken
│    └─ Grind chicken for char XP   [120/250] → L6
│
├─○ copper_boots               gear   1.00
│    would  Craft 1x copper_boots  (needs 8x copper_bar)
│
├─○ cooked_gudgeon             skill  0.40
│    would  Craft 1x cooked_gudgeon
│
└─ suppressed  PursueTask · GatherMaterials
   alternatives 1–6 of 14    [ prev   ] next
```

Structure:
- **Root** = the character objective (`reach level {max_level}` /
  "reach max level"), rendered once at top.
- **`●` chosen branch** expands fully and is pinned on every page: the existing
  `_body(...)` render (ObtainItem `_obtain_chain` have/need table, or the
  grind / skill / task one-liner) is nested under the chosen root, preceded by a
  `step  {step_repr}` line and a `plan  {plan_len} actions   next {path_next_action}`
  line.
- **`○` stub branches** = every non-chosen ranked root, **paginated**. Each stub
  is one `would  {verb} {qty}x {item}` line derived cheaply from the root /
  `step_repr` (no recipe-closure expansion). `verb` = Craft if the item has a
  recipe else Collect; for non-ObtainItem roots fall back to the `step_repr`.
- **suppressed** leaf footer (`·`-joined) when any.
- **pagination footer**: `alternatives {lo}–{hi} of {total}    [ prev   ] next`.

### Glyphs
`●` chosen / `○` stub, with `├─ └─ │` box-drawing connectors. Add to / reuse
`tui/glyphs.py`.

### Pagination
- `PlanScreen` gains `_alt_page: int` state. Bindings `[` (prev) and `]` (next)
  decrement / increment with clamp to `[0, last_page]`; re-render on change.
  `p` / `escape` keep dismissing (no collision).
- Page size const `ALT_PAGE_SIZE = 6` stubs per page. Chosen branch + suppressed
  footer render on every page; only the `○` stub list is sliced.
- `build_plan_summary` becomes page-aware: new params `alt_page: int = 0`,
  `alt_page_size: int = 6` (and `plan_len`, `suppressed_goals` so the chosen
  branch / footer have their data). Stays a pure function — given a page index it
  returns the renderable — so it is unit-testable without the screen.

### Data plumb
- `RootScoreView` (`ai/cycle_snapshot.py`) gains `step_repr: str`.
- `player.py` snapshot builder (~line 1031) sets `step_repr=r.step_repr`.
- `plan_screen.build_plan_detail` adapter passes `snap.plan_len`,
  `snap.suppressed_goals`, and the `_alt_page` it holds.

## Shared helper

`short_root(repr: str) -> str` — strip `ObtainItem(code='…', quantity=1)` to the
bare item (and the obvious `quantity=N` variant). `plan_summary` inlines this
today; extract one helper, reuse in both components.

## Non-goals / YAGNI

- No new decision logic, scoring, or planner change — presentation only.
- No live recipe-closure expansion for stub branches (too expensive per render;
  one cheap `would …` line only).
- The `l` debug-log modal is unchanged (it already dumps goals_tried / goal_rank
  / suppressed).

## Formal-gate impact

None. `RootScoreView` is a TUI view model; `step_repr` is already computed by
`RootScore`. Confirm during implementation that `ai/cycle_snapshot.py` is not
referenced by any `formal/diff` oracle (expected: it is not — it is a TUI
consumer), then no Lean / oracle / mutation work is required.

## Testing

- `tests/` for `build_log_lines`: chosen+alts present, chosen but no alts,
  no chosen_root (line 2 omitted), score formatting.
- `tests/` for `build_plan_summary`: chosen-branch expansion per root kind
  (ObtainItem / char-level / skill / task), stub `would` lines, pagination
  slicing + footer (first / middle / last page, single page, empty ranking),
  suppressed footer present/absent.
- Maintain 0 errors / 0 warnings / 0 skipped / 100% coverage
  (`uv run pytest`, `uv run mypy src`, `uv run ruff check`).

# Design: TUI plan-tree screen

Date: 2026-06-13
Status: APPROVED (design) — ready for implementation plan.

## Problem

The TUI/logging surfaces the next action and the goal, but not the long-term
plan. So when the AI commits to a gear objective and gathers for hundreds of
cycles (expected gear-first behavior), it *looks* like a level-1 freeze
(trace 2026-06-13 10:13: 273/277 cycles on `ObtainItem(copper_boots)`, char
stuck at L1 — correct behavior, illegible from the UI). We need a screen that
makes the committed objective's full materialization plan — and how far along it
is — observable at a glance.

## Goal

A new TUI modal screen (toggle `p`) showing the committed objective's plan tree
with gather→craft loops collapsed into one line per item and live have/need
progress, plus the ranked alternative roots (why this objective beat leveling).

## Decisions (locked in brainstorming)

1. **Progress**: each step shows `[have/need]` (inventory+bank credited via the
   existing `shopping_list` net-deficit logic); the active leaf is marked `← now`.
2. **Scope**: committed objective's collapsed tree + a compact ALTERNATIVES block
   (ranked runner-up roots with score + category).
3. **ETA**: include a rough ETA line from the already-computed
   `projected_cycles_to_max` (labeled an estimate).
4. **Non-craftable roots**: combat/skill/task roots render their natural progress
   line (no gather chain).
5. **Collapse rule**: one line per DISTINCT item in the recipe closure, ordered
   by recipe depth (raw gathers → intermediates → final craft → equip).
6. **No formal core**: pure display logic reusing the proven `closure_demand` /
   `shopping_list` cores; nothing new to prove.

## Architecture

### Component A — plan summary builder: `src/artifactsmmo_cli/tui/plan_summary.py`

One pure function (no I/O), returns a Rich renderable:
```python
def build_plan_summary(
    chosen_root: str | None,            # repr, e.g. "ObtainItem(code='copper_boots', quantity=1)"
    ranking: list[RootScoreView],       # ranked roots (root_repr, category, score) — see Component B
    inventory: dict[str, int],
    bank: dict[str, int] | None,
    game_data: GameData,
    projected_cycles_to_max: float | None,
) -> RenderableType:
    """A Rich Table/Group: the committed objective's collapsed plan with
    have/need progress, an ETA line, and a ranked ALTERNATIVES block."""
```

Branches on the `chosen_root` repr (parse the leading constructor name; the
item code via the existing repr, e.g. regex on `code='...'`):

- **`ObtainItem(code, qty)`** — the gather/craft chain:
  - `owned = inventory + bank`.
  - `total = {}`; `closure_demand(code, qty, game_data, total, frozenset())`.
  - `net = shopping_list(code, qty, game_data.crafting_recipes, owned)` (remaining work per item).
  - `have[c] = total[c] - net.get(c, 0)`.
  - Order items by recipe DEPTH (raw first): a small topo/depth sort over
    `game_data.crafting_recipes` within the closure (leaves = items not in
    `crafting_recipes`; depth = max over recipe inputs + 1). Stable tie-break by code.
  - Per item line: verb + `qty`x + name + `[have/total]`. Verb = `Collect` when
    the item is raw (not in `crafting_recipes`) else `Craft`. The deepest item
    with `net>0` gets `← now`. A craftable whose `crafting_skill` level exceeds
    the character's current skill appends `(needs {skill} {level})`.
  - If `code` is equippable (`ITEM_TYPE_TO_SLOTS`), a final `Equip {code}` line.
- **`ReachCharLevel(N)`** — `Grind for char XP  [{xp}/{max_xp}]  → L{N}` (combat
  monster from the snapshot's `path_next_action` if present).
- **`ReachSkillLevel(skill, N)`** — `Grind {skill}  [skill_xp {skill_xp}]  → L{N}`.
- **`PursueTask` / task root** — `Task {task_code}  [{progress}/{total}]`.
- **`chosen_root is None`** — `No committed objective this cycle.`

Then an **ALTERNATIVES** block: the ranking entries other than the chosen one,
each `{score:.2f}  {root_repr-shortened}  ({category})`, top ~6.

Header line: `COMMITTED: {short root}  ({category}, score {score})` and a footer
`ETA ~{projected_cycles_to_max:.0f} cycles (estimate)` when the value is present.

### Component B — snapshot plumbing: `ai/cycle_snapshot.py` + `ai/player.py`

`CycleSnapshot` lacks the strategy root. Add:
```python
class RootScoreView(BaseModel):       # small view of a ranked root for the TUI
    root_repr: str
    category: str
    score: float

# on CycleSnapshot:
chosen_root: str | None = None
strategy_ranking: list[RootScoreView] = Field(default_factory=list)
bank_items: dict[str, int] | None = None   # for accurate have/need (materials get banked)
```
`player.py` already builds `CycleSnapshot(...)` (≈line 976) and holds the cycle's
`StrategyDecision` (`self._last_decision`). Populate `chosen_root = repr(decision.chosen_root)`
and map `decision.ranking` → `[RootScoreView(root_repr=r.root_repr,
category=r.category, score=float(r.score)) for r in decision.ranking]`. (Confirm
the exact `RootScore` attribute names in `tiers/strategy.py` — from the trace they
are `root_repr`, `category`, `score`; adapt if different.) Also pass
`bank_items=dict(self.state.bank_items) if self.state.bank_items is not None else None`
(currently NOT in the snapshot — add the field) so the builder credits banked
materials in have/need; `inventory` already flows in.

### Component C — `PlanScreen`: `src/artifactsmmo_cli/tui/screens/plan_screen.py`

Mirrors `CharacterScreen`:
```python
class PlanScreen(Screen[None]):
    BINDINGS = [("escape", "dismiss", "Back"), ("p", "dismiss", "Back")]
    def __init__(self, snapshot: CycleSnapshot, game_data: GameData) -> None: ...
    def compose(self) -> ComposeResult:
        with VerticalScroll(id="plan-scroll"):
            yield Static(build_plan_summary(...from snapshot + game_data...), id="plan-detail")
    def update_snapshot(self, snap: CycleSnapshot) -> None: ...  # re-render
```
Holds BOTH the last snapshot and `game_data` (the builder needs recipes). A
`DEFAULT_CSS` filling the screen like `CharacterScreen`.

### Component D — app wiring: `src/artifactsmmo_cli/tui/app.py`

- Import `PlanScreen`; add `("p", "toggle_plan", "Plan")` to `BINDINGS`.
- `action_toggle_plan` mirrors `action_toggle_character`: if the top screen is a
  `PlanScreen`, pop; else `push_screen(PlanScreen(self._last_snapshot, self._game_data))`.
- Extend the existing modal-refresh guard (`isinstance(top, (CharacterScreen, LogScreen))`)
  to include `PlanScreen` so it updates each cycle.
- `WatchApp` already receives `game_data` (`WatchApp(character=, game_data=)`); store
  it as `self._game_data` if not already, to pass into `PlanScreen`.

## Data flow

```
cycle -> StrategyDecision (chosen_root, ranking)
      -> CycleSnapshot(chosen_root, strategy_ranking, inventory, bank_items, ...)
      -> observer/bridge -> WatchApp._last_snapshot
press 'p' -> PlanScreen(snapshot, game_data)
          -> build_plan_summary(chosen_root, ranking, inventory, bank, game_data, eta)
             closure_demand + shopping_list -> collapsed lines w/ have/need
```

## Error handling

- `chosen_root is None` or an unparseable repr → a single friendly line
  (`No committed objective` / `Plan: {root}` raw), never a crash. The screen is
  read-only and must tolerate any snapshot.
- An `ObtainItem` whose code is absent from `game_data` (unknown item) → show the
  root line with no chain rather than raising.
- Missing `bank` (None) → credit inventory only (matches planner behaviour when
  `bank_items` is unloaded).
- No `try/except Exception` — guard with explicit `is None` / membership checks.

## Testing strategy (pytest, 100% coverage)

`tests/test_tui/test_plan_summary.py` (pure builder, a fake `GameData` with a
small recipe table like the existing `_FakeGameData`/`make_game_data` fixtures):
- ObtainItem chain collapse: `copper_boots` ← `copper_bar`×N ← `copper_rock`×M
  renders one line per item, raw-first order, with `[have/total]` from a given
  inventory (e.g. 42 copper_rock → `[42/60]`), active leaf marked `← now`.
- skill-gate annotation when `crafting_level > skill`.
- `Equip` line appended for an equippable root; absent for a non-equippable.
- non-craftable roots: `ReachCharLevel`, `ReachSkillLevel`, `PursueTask` each
  render their progress line; `chosen_root=None` renders the empty-state line.
- ALTERNATIVES block lists the non-chosen ranked roots with score+category.
- ETA line present when `projected_cycles_to_max` given, absent when None.

`tests/test_ai/test_cycle_snapshot.py` (or the player snapshot test): `chosen_root`
and `strategy_ranking` populate from a `StrategyDecision`.

`tests/test_tui/test_plan_screen.py`: a render smoke test — construct `PlanScreen`
with a snapshot + fake game_data, assert `build_plan_summary` is invoked and the
Static mounts (mirror the existing `CharacterScreen` test if one exists; else a
minimal `compose`/`update_snapshot` check).

## Out of scope (YAGNI)

- No interactivity (read-only screen; no expand/collapse, no editing the plan).
- No re-planning or look-ahead simulation — the tree is the recipe closure of the
  CURRENT committed root, not a multi-objective forecast.
- No persistence/export.
- The "full forest" (every root's tree) — only the committed root is expanded;
  alternatives are one line each.

## Files

- Create: `src/artifactsmmo_cli/tui/plan_summary.py`,
  `src/artifactsmmo_cli/tui/screens/plan_screen.py`,
  `tests/test_tui/test_plan_summary.py`, `tests/test_tui/test_plan_screen.py`.
- Modify: `src/artifactsmmo_cli/ai/cycle_snapshot.py` (add `RootScoreView`,
  `chosen_root`, `strategy_ranking`), `src/artifactsmmo_cli/ai/player.py`
  (populate them), `src/artifactsmmo_cli/tui/app.py` (binding + action + wiring),
  and the snapshot test.

# Design: Plan-tree prerequisite nesting (interactive TUI tree)

Date: 2026-07-02
Status: DESIGN — awaiting user review before implementation plan.

## Problem

The plan screen (toggle `p`) shows the chosen objective and — via the shipped
`2026-06-13-tui-plan-tree-design.md` flowchart — its **recipe-material closure**
(gather→craft chain per item, computed with `closure_demand`/`shopping_list`).

It does **not** show the **prerequisite sub-goals**: e.g. for `ObtainItem(life_amulet)`
it lists the amulet's material items but never "level jewelrycrafting to 5" or the
"grind copper_ring for jewelrycrafting XP" sub-task that unblocks the craft-skill
gate. Those live in the `prerequisites()` graph, which the flowchart ignores in
favor of the recipe closure. So the operator cannot see *why* the bot is grinding
copper rings when the objective is a life amulet — the causal chain is invisible.

## Goal

Replace the chosen-root flowchart body with an **interactive collapsible tree** of
the chosen root's full `prerequisites()` expansion: skill-gate sub-goals,
material sub-tasks, and grind steps, each marked with live status, down to raw
gathers. Non-chosen roots appear as single non-expandable stub lines. The tree
survives live snapshot refresh without discarding the operator's expand/collapse
state.

## Decisions (locked in brainstorming)

1. **Render style** — Textual `Tree` widget (interactive: arrow-key focus,
   per-branch expand/collapse), replacing the current `Static` flowchart body.
2. **Scope** — the **chosen** root fully expands its `prerequisites()` subtree.
   Non-chosen roots render as leaf stubs (rank + score), not expandable. Drop the
   `[`/`]` alternatives-pagination (all roots now listed in one tree).
3. **Live refresh** — on each new snapshot rebuild the tree, but preserve
   expand/collapse by **node key**: re-expand any node whose key was expanded and
   still exists. Status markers / current-step update live; open branches stay open.
4. **Unified structural source** — the tree skeleton is the recursive
   `prerequisites()` expansion (skill gates + recipe materials down to raw
   gathers), which strictly subsumes the old recipe-closure flowchart body.
5. **Grind sub-task is synthetic, not a graph node** — `ReachSkillLevel` is a
   **leaf** in the prerequisite graph (`prerequisite_graph.py:84`: skill nodes
   return `[]`; materials enter via `ObtainItem` chains). The "grind copper_ring
   for jewelrycrafting XP" the operator wants to see is the concrete `Goal`/action
   that *serves* the active skill step, not a prerequisite. So the tree attaches a
   single synthetic `step`-kind child under the **current** node, labelled from the
   running goal + immediate action (`selected_goal` + `action`, the same locals
   already on the snapshot) — NOT `path_next_action` (that field is the
   leveling-path monster). Never re-derived here.
6. **Status per node** — from `MetaGoal.is_satisfied(state, game_data)`
   (authoritative; no repr-parsing). `current` = `decision.chosen_step`.
7. **No formal core** — pure display logic over already-proven-adjacent
   `prerequisites()` / `is_satisfied`. Nothing new to prove in Lean.

## Architecture

### Component A — tree data model + builder: `src/artifactsmmo_cli/ai/plan_tree.py`

A frozen value model plus a pure builder (no I/O). One value object + module-level
pure functions — no second behavioral class, so this satisfies one-class-per-file.

```python
class PlanTreeNode(BaseModel):          # frozen; recursive value object for the TUI
    model_config = ConfigDict(frozen=True)
    key: str                            # stable id for expansion memory + dedup, e.g.
                                        #   "ObtainItem(code='life_amulet', quantity=1)"
                                        #   "ReachSkillLevel(skill='jewelrycrafting', level=5)"
    label: str                          # short display label (reuse plan_format.short_root style)
    kind: str                           # "obtain" | "skill" | "charlevel" | "step" | "root_stub"
    status: str                         # "met" | "unmet" | "current"
    detail: str | None = None           # qty / skill target / "root 2, score 3.10"
    children: tuple["PlanTreeNode", ...] = ()

def build_plan_tree(
    decision: StrategyDecision,
    state: WorldState,
    game_data: GameData,
    serve_step: str | None,             # concrete current work: f"{selected_goal}: {action}" (NOT path_next_action)
) -> tuple[PlanTreeNode, ...]:
    """Top level = ranked roots. The chosen root recurses prerequisites();
    other roots are leaf stubs. The current node gets a synthetic `step` child
    describing next_action. Bounded by a visited-set (frozen MetaGoals are
    hashable) + a depth cap. Returns roots in ranking order."""
```

Builder logic:

- Iterate `decision.ranking` (ordered). For the entry whose root is
  `decision.chosen_root`, emit `_expand(root, visited=frozenset(), depth=0)`.
  For every other entry emit a `root_stub` leaf: `label = short_root(root_repr)`,
  `detail = f"root {rank}, score {score:.2f}"`, `children = ()`.
- `_expand(node, visited, depth) -> PlanTreeNode`:
  - `is_current = node == decision.chosen_step`.
  - `status = "current" if is_current else ("met" if
    node.is_satisfied(state, game_data) else "unmet")`.
  - Structural children = `()` when `node in visited` or `depth >= _DEPTH_CAP`;
    otherwise `tuple(_expand(p, visited | {node}, depth + 1)
    for p in prerequisites(node, state, game_data))`. Include **met**
    prerequisites too (rendered ✔) so the tree is complete, not just the unmet
    frontier.
  - **Synthetic grind/serve child**: when `is_current` and `next_action` is not
    None, append a single leaf `PlanTreeNode(kind="step", status="current",
    label=next_action, key=f"step:{node_key}")`. This is the ONLY place the
    concrete serving action (e.g. "grind copper_ring ×8 for jewelrycrafting XP")
    enters the tree — it is not a prerequisite-graph node (skill nodes are
    leaves, `prerequisite_graph.py:84`). `serve_step` is composed at the call site
    from `selected_goal` + `action` (the running goal and immediate action) — NOT
    `path_next_action` (the leveling-path monster); the builder does not recompute.
  - `label`/`kind`/`detail` derived per node type: `ObtainItem` → "obtain"
    (label = item name, detail = `×qty`); `ReachSkillLevel` → "skill" (label =
    `{skill} → {level}`); `ReachCharLevel` → "charlevel".
- `_DEPTH_CAP`: reuse an existing planner depth bound (e.g. 32, matching
  `UpgradeEquipment.max_depth`) rather than inventing a new constant.

Consequence: for `ObtainItem(life_amulet)` with the skill gate unmet, the tree is
`● life_amulet → ▸ jewelrycrafting → 5 (current) → • grind copper_ring … (step)`
plus the material `ObtainItem` children — matching the operator's example. When
the current step is instead a material craft/gather, the synthetic child hangs off
that `ObtainItem` node.

`prerequisites()` is already exercised every cycle inside `decide()`; one extra
bounded pass with a visited-set is marginal (see Risks).

### Component B — snapshot plumbing: `ai/cycle_snapshot.py` + `ai/player.py`

Add to `CycleSnapshot`:
```python
plan_tree: tuple[PlanTreeNode, ...] = ()
```
Populate at the existing snapshot-build site (`player.py` ~line 1461, where
`chosen_root`/`strategy_ranking` are already set from `self._last_decision`):
```python
plan_tree=build_plan_tree(decision, self.state, self.game_data,
                          f"{selected_goal_name}: {action_name}")
```
where `serve_step` is composed from the `selected_goal_name` + `action_name` locals
already passed to `selected_goal=`/`action=` in the same constructor — NOT
`path_next_action` (which is `plan.next_action_monster`, the leveling-path monster).
Keep the existing flat fields (`chosen_root`, `strategy_ranking`, `plan_len`, …)
for back-compat with the CLI `plan` command and any other consumer.

### Component C — tree widget: `src/artifactsmmo_cli/tui/widgets/plan_tree.py`

`class PlanTree(Tree[PlanTreeNode])` (behavioral class → own file). Builds Textual
`TreeNode`s recursively from `tuple[PlanTreeNode, ...]`, styling each label by
`status`/`kind`:

- `● …  ◄ CHOSEN` for the chosen root; `▸ …  ◄ current step` for `status=current`;
  `○ …` unmet; `✔ …` met; `• …  (root k, score s)` for `root_stub`.
- `set_nodes(roots: tuple[PlanTreeNode, ...])` — clears and rebuilds, then applies
  expansion memory: a `set[str]` of expanded keys held by the widget. Default
  seed on first build = the chosen root + its unmet chain down to `current`, so
  the tree opens expanded to the active step. `root_stub` nodes are added with
  `allow_expand=False`.
- Track user intent via `Tree.NodeExpanded` / `Tree.NodeCollapsed` handlers that
  add/remove the node's `key` from the expanded set, so a rebuild re-applies it.

### Component D — screen: `src/artifactsmmo_cli/tui/screens/plan_screen.py`

Swap the single `Static(#plan-detail)` for: a compact `Static` header
(OBJECTIVE + ETA + suppressed-count, reusing the trimmed `plan_summary` header/
footer helpers) above a `PlanTree` that fills the rest and scrolls itself.

- `__init__(snapshot, game_data)` unchanged signature.
- `update_snapshot(snap)` → refresh header `Static` + `plan_tree.set_nodes(snap.plan_tree)`.
- Remove `action_alt_prev`/`action_alt_next` and the `[`/`]` bindings; remove the
  `alt_page` plumbing through `build_plan_detail`.
- Escape/`p` still dismiss.

### Component E — retire the flowchart body: `tui/plan_summary.py`

`build_plan_summary`'s `_body`/`_obtain_chain`/`_depth` chosen-root expansion is
superseded by the tree. Keep the OBJECTIVE header, ETA footer, and suppressed
footer as small helper functions the screen's header `Static` reuses; delete the
repr-regex-driven body path (`_body`, `_obtain_chain`, `_depth`, `_OBTAIN_RE`
usage inside the body) and their now-dead tests. `plan_format.short_root` stays
(reused for node labels).

## Data flow

```
cycle -> StrategyDecision (chosen_root, chosen_step, ranking) + path_next_action
      -> build_plan_tree(decision, state, game_data, next_action)  # recurse prerequisites() + synthetic step
      -> CycleSnapshot(plan_tree=(...), chosen_root, strategy_ranking, ...)
      -> observer/bridge -> WatchApp._last_snapshot
press 'p' -> PlanScreen(snapshot, game_data)
          -> PlanTree.set_nodes(snapshot.plan_tree)     # + re-apply expansion memory
new cycle while open -> update_snapshot -> set_nodes(...) preserving open branches
```

## Error handling

- `decision.chosen_root is None` → `build_plan_tree` returns stubs only (or empty);
  screen shows "No committed objective this cycle." No crash.
- `ObtainItem` code absent from `game_data` → node renders with no children (its
  `prerequisites()` already tolerates unknown items); never raises.
- Cyclic or over-deep `prerequisites()` → bounded by visited-set + `_DEPTH_CAP`;
  a truncated branch renders as a leaf (optionally labelled `…`), not a hang.
- Missing `bank_items` (None) → status uses `owned_count` over inventory+bank as
  today; None bank credits inventory only.
- No `try/except Exception` anywhere — explicit `is None` / membership guards
  (per project Exception-handling rule).

## Testing strategy (pytest, 100% coverage, 0 warnings)

`tests/test_ai/test_plan_tree.py` (pure builder, real `GameData` fixture with a
small recipe+skill table — reuse existing `make_game_data`/`_FakeGameData`):
- Chosen `ObtainItem` with a craft-skill gate expands to a `ReachSkillLevel`
  child plus material `ObtainItem` children; a met material is `status=met`, an
  unmet one `unmet`, and `decision.chosen_step` is `current`.
- Synthetic step child: when `chosen_step` is the skill node and `next_action` is
  given, that node gains one `kind="step"` leaf whose label == `next_action`;
  absent when `next_action is None` or the node is not `current`.
- Deeper recursion: material → its own skill gate + raw gather leaf (raw item has
  no children).
- Non-chosen roots are `root_stub` leaves with `children == ()` and a score detail.
- Cycle guard: a fabricated cyclic prerequisite terminates (visited-set) — no
  infinite recursion, offending node becomes a leaf.
- Depth cap: a chain longer than `_DEPTH_CAP` truncates to a leaf at the cap.
- `chosen_root is None` → stubs-only / empty result.

`tests/test_ai/test_cycle_snapshot.py` (or the player snapshot test): `plan_tree`
populates from a `StrategyDecision` + state + game_data.

`tests/test_tui/test_plan_tree_widget.py`: `set_nodes` builds the expected
`TreeNode` structure from a `PlanTreeNode` tuple; expansion memory re-applies a
previously-expanded key after a second `set_nodes`; `root_stub` nodes are
non-expandable.

`tests/test_tui/test_plan_screen.py`: update the existing screen test — the
`PlanTree` mounts and `update_snapshot` forwards to `set_nodes`; the old
`alt_page`/`[ ]` assertions are removed.

Prune the now-dead `test_plan_summary.py` cases covering the retired `_body`/
`_obtain_chain` path (Component E) in the same change (no orphaned/skipped tests).

## Risks & mitigations

- **Per-cycle compute** — `build_plan_tree` runs at every snapshot build even when
  the plan screen is closed. `prerequisites()` already runs each cycle in
  `decide()`; the extra pass is bounded (single chosen-root recursion + visited-set
  + depth cap). Prior profiling ([[project_tui_cpu_root_cause]]) pinned TUI CPU on
  Textual re-render, not the planner, so this is expected to be negligible. If a
  profile later disagrees, gate the build behind "plan screen open" via a flag on
  the player — do not pre-optimize now.
- **Snapshot payload size** — one bounded tree of the chosen root only; stubs for
  the rest. Small.
- **Recursive frozen pydantic model** — `PlanTreeNode` with `tuple` children and a
  forward ref; supported, requires `model_rebuild()` if the forward ref needs it.

## Out of scope (YAGNI)

- Expanding non-chosen roots' subtrees (leaf stubs only — matches the stated ask).
- Editing/replanning from the tree; it is read-only observation.
- Persistence/export of the tree.
- A separate recipe-closure view — the prerequisite tree already reaches raw
  materials, so the old closure body is retired, not kept alongside.

## Files

- Create: `src/artifactsmmo_cli/ai/plan_tree.py`,
  `src/artifactsmmo_cli/tui/widgets/plan_tree.py`,
  `tests/test_ai/test_plan_tree.py`,
  `tests/test_tui/test_plan_tree_widget.py`.
- Modify: `src/artifactsmmo_cli/ai/cycle_snapshot.py` (add `plan_tree` field),
  `src/artifactsmmo_cli/ai/player.py` (populate it),
  `src/artifactsmmo_cli/tui/screens/plan_screen.py` (swap Static→PlanTree,
  drop alt-pagination), `src/artifactsmmo_cli/tui/plan_summary.py` (retire body,
  keep header/footer helpers), `src/artifactsmmo_cli/tui/app.py` (only if wiring
  changes), and the affected snapshot/screen/summary tests.

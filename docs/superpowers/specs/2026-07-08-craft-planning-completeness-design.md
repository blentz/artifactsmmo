# Crafting-Recipe Planning Completeness — Design

Date: 2026-07-08
Status: approved (design); implementation via phased plan
Analogue of: `docs/behavioral_completeness/` (generated matrix + regen script
+ ranked gap backlog + proof cross-links)

## Problem

The bot's planner is validated by hand-picked scenarios (`test_no_deadlock`,
band/slot nets) and the flat-parity/deadlock bugs those surfaced (GAP-1..9).
But there is no *census*: of the 321 craftable recipes the game exposes, for
how many can the planner actually produce a directional plan toward making
the item, from a plausible under-progressed state? Each of GAP-8 (drop-
ingredient crafts) and GAP-9 (grey-farm suppression) was a single recipe
class discovered by chance. A completeness matrix turns "discovered by
chance" into "enumerated" — every recipe, gridded over the character-
progression conditions where planning breaks (under-level, under-skill,
empty inventory), pass/fail with a gap classification.

## What "completeness" means here

For each craftable recipe X (an item with a non-empty `crafting_recipe`),
drive the REAL planner from a plausible state whose objective is obtaining X,
and require a directional plan. This is validated across a per-recipe GRID of
character-level × skill-level conditions, so a recipe that plans at-level but
deadlocks under-skill is a caught gap, not a miss.

## The grid (per recipe)

Recipe X with craft skill `S`, craft level `L`, tier `T = (L-1)//10 + 1` (decade-inclusive: L=10 is the last level of tier 1, not the first of tier 2):

- **Character-level cells** (3): the tier's nominal char level — `1` for
  T1 (L ≤ 9), else `10·T` — plus the two tier-boundary offsets `10·T − 2`
  and `10·T + 2`. (e.g. T2 recipe → char levels 18, 20, 22.) Clamp to
  `[1, 50]`.
- **Skill cells** (2): under-skill `max(0, L − 5)` and at-skill `L`.
- **State**: empty inventory AND empty bank; realistic combat stats from the
  equipped starter/tier gear via `derive_combat_stats` (so `is_winnable`
  reflects a plausible loadout, not zero stats); no materials pre-granted —
  the planner must plan the FULL acquisition (skill-grind if under, gather/
  fight/buy every leaf, craft intermediates, final craft).
- ≈ 3 × 2 = 6 cells per recipe → ≈ 1,900 planner runs total. This is an
  OFFLINE audit (a regeneration script), NOT part of the default test suite.

## Objective injection

Most craftables are not gear, so the progression tree (which only ever roots
`ReachCharLevel`/`ObtainItem` gear) will not select them. The harness
therefore bypasses tree root-arbitration and drives the planner directly:

```
plan_craft(X, state, game_data) -> Plan
  goal = GatherMaterialsGoal(target_item=X, needed={X: 1})
  return Planner(...).plan(goal, state, game_data)   # planner.py:83
```

`GatherMaterialsGoal` already owns the obtain-X machinery (`desired_state` =
have X, `relevant_actions` = the recipe-closure gather/craft/fight/buy set,
`is_satisfied` = X in inventory). This is the same goal the tree's gear
branch uses for its ObtainItem steps, so `plan_craft` exercises the exact
production planning path — just aimed at every recipe, not only gear.

## PASS predicate

A cell PASSES iff:
1. the plan is non-empty, AND
2. `plan[0]` advances X's transitive closure — one of:
   - `GatherAction` / `FightAction` / `NpcBuyAction` / `WithdrawItemAction`
     whose item is in X's recipe closure (`recipe_closure(game_data, {X:1})`),
   - `CraftAction` of X or a closure intermediate,
   - a skill-grind leg toward `S` (a `Fight`/`Craft`/`Gather` emitted by the
     `ReachSkillLevel(S, …)` dispatch — recognised by the craft-plan
     generator / skill-step path targeting `S`).

A cell FAILS iff the plan is empty, is `[Wait]`, or `plan[0]` is unrelated to
X's closure (e.g. `GrindCharacterXP` for character level, a different item).

The predicate is a pure function `craft_cell_verdict(X, plan, game_data) ->
PASS | (FAIL, first_action_repr)` so it is unit-testable independent of the
planner.

## Gap classification

Every FAIL is classified (pure function over X's closure + the cell state),
so real planner holes separate from expected game limits:

- **PLANNER-BUG** — every closure leaf is reachable (gatherable, craftable,
  drop-winnable at the cell level, or buyable) and the skill is grindable,
  yet no directional plan was produced. THE actionable class — each is a
  systematic-debug fix like GAP-9.
- **COMBAT-BLOCKED** — a closure leaf's only source is a monster not
  `is_winnable` at the cell's level/loadout.
- **EVENT-GATED** — a closure leaf drops only from an event-active monster
  (unreachable in the event-free audit state).
- **MATERIAL-UNREACHABLE** — a leaf is none of gatherable / craftable /
  drop-winnable / buyable (a genuine dead end in the static catalog).
- **SKILL-UNREACHABLE** — `S` cannot be grinded to `L` at the cell level
  (no in-band craftable/gatherable to level it).

Classification uses the existing attainability walk (`is_attainable_now` /
`recipe_closure` / `_pick_winnable_monster`) — no new game model.

## Deliverables

- `src/artifactsmmo_cli/audit/craft_completeness.py` — pure cores:
  `craft_grid(recipe, game_data) -> list[Cell]` (the level/skill cells),
  `craft_cell_verdict(...)`, `classify_gap(...)`. One behavioral unit,
  fully unit-tested.
- `scripts/gen_craft_completeness.py` — runs the full grid via the scenario
  harness (`scenario_state` + `plan_craft`) over the committed bundle,
  writes:
  - `docs/craft_completeness/MATRIX.md` — recipe × cell → PASS / gap-class,
    grouped by craft skill × tier (generated, do-not-hand-edit header).
  - `docs/craft_completeness/BACKLOG.md` — the ranked `PLANNER-BUG` list
    (recipe, cell, closure leaf that blocked), the fix queue.
  - a `SUMMARY` line: N recipes, %PASS at at-skill/nominal, gap-class counts.
- `tests/test_ai/scenarios/test_craft_completeness.py` — a PINNED regression
  subset: one representative recipe per (craft-skill × tier) at the
  at-skill/nominal cell (~30 cells) that MUST PASS. CI-safe; the full
  1,900-cell matrix stays a regenerable offline doc.
- `plan --craft <item> [--char-level N --skill K]` CLI mode — a thin wrapper
  over `plan_craft` on a gridless single cell, for interactive debugging of
  one recipe (mirrors `plan --scenario`).

## Architecture / data flow

```
gen_craft_completeness.py
  for recipe in craftable(game_data):           # 321
    for cell in craft_grid(recipe, game_data):  # ~6
      state = scenario_state(cell_char(recipe, cell), game_data)  # empty inv/bank
      plan  = plan_craft(recipe, state, game_data)
      v     = craft_cell_verdict(recipe, plan, game_data)
      if v is FAIL: v.gap = classify_gap(recipe, cell, game_data)
      row.append(v)
  -> MATRIX.md + BACKLOG.md + SUMMARY
```

`plan_craft` and the verdict/classifier are pure and unit-tested; the script
is orchestration + doc rendering (no decision logic).

## Testing

- Unit: `craft_grid` cell arithmetic (tier/level/skill boundaries, clamps),
  `craft_cell_verdict` (each PASS leg + each FAIL reason), `classify_gap`
  (each class with a witness recipe).
- Regression: the pinned ~30-recipe subset must PASS (fast). A recipe that
  regresses from PASS→FAIL fails the build.
- The offline matrix is regenerated on demand; its SUMMARY line is the
  completeness metric tracked over time.

## Scope / non-goals

- NOT a proof exercise — no Lean. It validates the running planner (the
  "achieve valid plans via the CLI" ask), complementing the behavioral-
  completeness proof matrix rather than duplicating it.
- Fixing the `PLANNER-BUG` gaps the census finds is a FOLLOW-ON backlog
  (each its own systematic-debug), not this spec. This spec delivers the
  census + the regression floor.
- Full-chain replay-to-completion (loop plan→apply→replan until crafted) is
  explicitly NOT the predicate — the first-leg-directional check is the
  agreed bar (cheaper, apply-model-independent).

## Risks

- **Runtime**: ~1,900 planner runs. Mitigated by keeping the full matrix
  offline (regen script) and pinning only ~30 in CI; the CPU-memo + node cap
  keep per-run bounded.
- **PASS-predicate false-greens**: `plan[0]` advancing the closure doesn't
  prove the WHOLE chain completes (a mid-chain leaf could still be a dead
  end). Accepted per the agreed predicate; the gap classifier partially
  covers this by flagging unreachable closure leaves even when `plan[0]` is
  productive (report both: first-leg PASS + a closure-reachability warning).
- **Objective-injection fidelity**: `plan_craft` uses `GatherMaterialsGoal`
  directly, which is the production obtain-X path — but the TREE would add
  its own root context (band adequacy, sticky). The census measures "can the
  planner plan to make X when X is the objective," which is the intended
  question; tree-arbitration interplay is out of scope.

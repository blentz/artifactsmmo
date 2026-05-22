# Goal Tiers — P3a.1: Strategy Cost-Model Refinement

Date: 2026-05-22
Status: Approved (design)

A focused refinement of P3a (still shadow mode, no behavior change), fixing the
degenerate ranking the shadow trace exposed.

## Goal

Replace the too-coarse structural cost proxy in `StrategyEngine` so the frontier
ranking reflects real effort, and break ties among equal goals meaningfully.
Still shadow-only — the decision is traced, not enacted.

## Problem (from the shadow trace)

P3a's `unmet_closure_size` makes every **leaf** goal cost `1`. So
`ReachSkillLevel(s, 50)` and `ReachCharLevel(50)` both cost 1 regardless of how
many levels away they are; `score = contribution / cost` collapses to "biggest
single gap". Observed: the engine picked `ReachSkillLevel(alchemy, 50)` every
cycle — all 8 skills tie (identical gap + cost) and the tie broke alphabetically
("alchemy"). Gear, with a multi-node closure, always lost. Not safe to cut over.

## Design

All changes are in `src/artifactsmmo_cli/ai/tiers/strategy.py`.

### Distance-based cost — new `root_cost(root, state, game_data) -> int`
Replaces `unmet_closure_size` as the cost used by `decide`:
- `ReachCharLevel(target)` → `max(1, target - state.level)` (levels remaining).
- `ReachSkillLevel(skill, target)` → `max(1, target - state.skills.get(skill, 1))`.
- `ObtainItem(...)` → `unmet_closure_size(root, state, game_data)` (craft/gather
  steps remaining — kept).

Units are commensurate "steps remaining": a 49-level skill costs ~49, a gear
chain ~3–8. `unmet_closure_size` stays (used here for the gear branch and still
exported/tested).

### Instrumental tiebreak — new `instrumental_skills(objective, game_data) -> set[str]`
A skill is *instrumental* when it gates target gear: collect
`item_stats(code).crafting_skill` for every `code` in
`objective.target_gear.values()` that has one. In `decide`, the candidate sort
key becomes:

`(-score, 0 if instrumental(root) else 1, repr(root))`

where `instrumental(root)` is `isinstance(root, ReachSkillLevel) and root.skill
in instrumental_skills(...)`. So among equal scores, skills that unlock target
gear rank above skills that gate nothing (e.g. weaponcrafting/gearcrafting
before alchemy when those craft the target gear), then deterministic by repr.
`instrumental_skills` is computed once per `decide`.

### Trace visibility
`RootScore` gains `instrumental: bool` (False for non-skill roots), surfaced in
`to_dict()`/`to_trace()` so the shadow trace shows why a root ranked where it
did.

### Unchanged
`decide`'s structure, `actionable_step`, contribution formula, HP-interrupt
flag, `desired_state_of`, the shadow wiring, and "no behavior change" all stand.

## Error handling
Pure, no API. `root_cost` floors at 1 (no div-by-zero in `score`). Empty
`target_gear` → `instrumental_skills` empty → tiebreak falls through to repr.

## Testing
Success per project standard: 0 errors, 0 warnings, 0 skipped, 100% on changed code.

- **`root_cost`:** `ReachSkillLevel(s,50)` at level 3 → 47; `ReachCharLevel(50)`
  at level 3 → 47; already-at-target → 1 (floor); `ObtainItem` → delegates to
  `unmet_closure_size`.
- **Ranking by distance:** a skill 1 level from cap outranks (per score) a skill
  49 levels away when contributions are otherwise comparable — leaf goals no
  longer all tie at cost 1.
- **`instrumental_skills`:** picks the crafting skills of target gear; empty when
  no target gear.
- **Instrumental tiebreak:** with two equal-score skills where target gear needs
  `weaponcrafting` (not `alchemy`), `weaponcrafting` is chosen; deterministic
  repr order among remaining ties.
- **`RootScore.instrumental`** appears in `to_trace()`; True only for
  instrumental skill roots.
- Existing P3a tests updated for the new cost/ordering (no longer assert the
  alchemy/leaf-cost-1 behavior).

## Files
- Modify `src/artifactsmmo_cli/ai/tiers/strategy.py` — `root_cost`,
  `instrumental_skills`, `decide` sort key, `RootScore.instrumental`.
- Modify `tests/test_ai/test_tiers_strategy.py`.

## Out of scope
- XP-curve / learned-projection cost (a later phase; this stays a structural proxy).
- Driving behavior (P3b), economy/tasks (P3c).
- Weighting instrumentality into the score itself (kept a tiebreak, not a multiplier).

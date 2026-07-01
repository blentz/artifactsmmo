# Next-Tier Skill-Grind Dampener — Design

**Date:** 2026-06-30
**Status:** Design approved; ready for implementation plan.
**Relates to:** `docs/superpowers/specs/2026-06-13-recipe-aware-skill-scheduling-design.md`
(the *floor* — skill up gradually so recipes unlock just-in-time). This feature is
the complementary *ceiling* — stop speculative skilling once the skill already
covers the next tier, until that tier is level-appropriate.

## Problem

A crafting skill can be leveled far ahead of the character's combat/level
progression. Each cycle, when no gear / char-level / task work is plannable, the
speculative skill grind fires and crafts a throwaway in-skill item purely for XP —
marching the skill toward its endgame target even though its output tier is not yet
level-appropriate. Once a gear-crafting skill can already craft **all** gear of the
next tier, further skilling yields nothing usable until the character catches up.
The bot should not pursue that speculative grind during this window.

### Where the speculative grind actually lives (traced 2026-06-30)

- The always-live endgame root `ReachSkillLevel(skill, max_skill_level)` is emitted
  in `prerequisite_graph.objective_roots` (line ~160) from
  `objective.target_skill_levels = {s: max_skill_level for s in SKILL_NAMES}`. It
  never satisfies until 50. **This root is explicitly OUT OF SCOPE — do not touch
  the endgame target.**
- When that root (or a near-term curve root) is the chosen objective step, the grind
  is decided by `skill_step_dispatch_pure`
  (`src/artifactsmmo_cli/ai/tiers/skill_step_dispatch.py`): SUPPRESS / GRIND(code) /
  NO_GRIND. GRIND crafts **one** level-appropriate in-skill item, then replan. This
  dispatch is the live per-cycle skill-grind mechanism and the attach point for the
  dampener.
- `LevelSkillGoal` (`goals/level_skill.py`) is **not** the speculative grinder. Its
  only live construction site is `strategy_driver.py:385`, inside
  `MeansKind.PURSUE_TASK` when the active task requires a non-combat skill. It is the
  task-gate deadlock-breaker — a need-driven path. Dampening it would starve the very
  case we want to exempt and would miss the speculative grind entirely. (Its name is
  misleading; see Out of Scope.)

## Goal

For **gear-crafting skills only**, hard-gate the speculative (throwaway) skill grind
when the skill can already craft **all** next-tier gear and that tier is not yet
level-appropriate — while never blocking need-driven skilling (tasks, committed
gear). Self-lifting as the character advances; no persisted state.

## Design decisions (all confirmed)

1. **Tier = 10-level bands**, reusing the `audit/content_tiers.py` band convention.
   `next_tier_floor = ((char_level // 10) + 1) * 10`; next tier band =
   `[next_tier_floor, next_tier_floor + 9]`.
2. **Hard gate** — dispatch returns SUPPRESS (arbiter advances). Not a soft score
   multiplier.
3. **Exempt need-driven** — the gate applies only to a *throwaway* grind pick (`not
   wanted` / not a committed objective target). A `wanted`/target in-skill craft is
   objective progress and proceeds. The task-gate `LevelSkillGoal` path is a separate
   code path and is untouched, so task-gated skilling is exempt automatically.
4. **Gear-crafting skills only** — self-enforcing: `next_tier_cap` is computed over
   `gear_relevant` items only, so consumable/gathering skills yield `cap = 0` and are
   never dampened. No hardcoded skill list.
5. **Keep the +3 curve floor** — `SKILL_CURVE_LOOKAHEAD = 3` just-in-time reach is
   preserved. The ceiling bites only beyond it; it never suppresses a grind serving a
   level-appropriate recipe.
6. **Endgame `ReachSkillLevel(skill, 50)` target untouched** — the dampener acts at
   dispatch, not at root emission.
7. **Attach point:** `skill_step_dispatch_pure` (skillXP grind decision only).

## Gate predicate

```
next_tier_dampened(current_skill, next_tier_cap) :=
      next_tier_cap  > 0
  and current_skill >= next_tier_cap      # crafts ALL next-tier gear
```

`next_tier_cap` is computed over the tier band **above** the character's current
tier (`next_tier_floor = ((char_level // 10) + 1) * 10`; band
`[next_tier_floor, next_tier_floor + 9]`). Because that band is *by construction*
one tier above the character, a separate "not yet level-appropriate" check on
`char_level` would be **vacuously true** (`char_level < next_tier_floor` always
holds) — it is intentionally omitted. The "until the tier is level-appropriate"
semantics instead falls out of `next_tier` **rolling up** as `char_level` climbs:
at the decade boundary the band redefines to the next-higher gear, `next_tier_cap`
recomputes over higher-level recipes, and the same `current_skill` typically no
longer covers it — so the gate releases. This roll-up is a data-dependent
behavior verified by regression test, **not** claimed as a structural theorem (the
band shifts rather than widens, so `cap` is not structurally monotone in
`char_level`).

`gear_relevant` mirrors the curve: `stats.type_ in ITEM_TYPE_TO_SLOTS or
stats.subtype == "tool"`.

## Components

### New pure cores (extraction subset — mirror `skill_curve_target_pure`)

Location: new module(s) under `src/artifactsmmo_cli/ai/tiers/` (one behavioral unit
per file per project convention; these are pure functions + a small dataclass view,
so they may share a module like `skill_target_curve.py` does).

- `next_tier_cap_pure(skill: str, char_level: int, items: list[SkillItem],
  max_skill_level: int) -> int`
  Computes `next_tier_floor = ((char_level // 10) + 1) * 10` internally, then the
  max `craft_level` over `gear_relevant` items of `skill` whose `item_level` lies in
  `[next_tier_floor, next_tier_floor + 9]`, clamped to `[1, max_skill_level]`;
  `0` when no qualifying gear item exists. Reuses the existing `SkillItem` view
  (imported from `skill_target_curve`).
- `next_tier_dampened_pure(current_skill: int, next_tier_cap: int) -> bool`
  Returns `next_tier_cap > 0 and current_skill >= next_tier_cap`.

### Impure hoist

Extend the `objective_step_goal` path (impure caller of `skill_step_dispatch_pure`,
`strategy_driver.py:688-759`) so that, in the `ReachSkillLevel` branch, it hoists
`SkillItem` tuples from `game_data.all_item_stats` (mirroring
`skill_target_curve`), computes
`cap = next_tier_cap_pure(step.skill, state.level, items, game_data.max_skill_level)`
and `dampened = next_tier_dampened_pure(current, cap)` (where `current =
state.skills.get(step.skill, 0)`, already read at line 705), and passes the single
`dampened: bool` into the dispatch.

### Dispatch integration

In `skill_step_dispatch_pure` (`skill_step_dispatch.py`): add one parameter
`dampened: bool = False` (keyword-defaulted so existing callers/tests are
unaffected). After the reservation passes produce `pick` and `combine_dispatch_pure`
yields `("grind", pick)`, if

- `dampened` is `True`, and
- the picked candidate (looked up by `code == pick` in `candidates`) is **not**
  `wanted` (throwaway),

then return `DispatchDecision(kind="suppress", code="")` instead. The existing
committed-item suppress (`combine_dispatch_pure`) is unchanged; the dampener is an
additional, `not wanted`-guarded suppress reason applied in the wrapper. Passing a
single precomputed `bool` (not the raw ints) keeps the proven `combine_dispatch_pure`
core untouched and confines the new branch to the wrapper.

## Data flow

```
objective_step_goal (impure)  [strategy_driver.py:688-759, ReachSkillLevel branch]
  ├─ current = state.skills.get(step.skill, 0)          (existing, line 705)
  ├─ candidates (existing) ─ each carries .wanted / is_target
  ├─ items = [SkillItem(...) for stats in game_data.all_item_stats]   # NEW hoist
  ├─ cap      = next_tier_cap_pure(step.skill, state.level, items, max_skill)  # NEW
  ├─ dampened = next_tier_dampened_pure(current, cap)                          # NEW
  └─ skill_step_dispatch_pure(step.skill, current, committed_skill,
                              committed_level, candidates, dampened)   # +1 arg
        ├─ (kind, code) = combine_dispatch_pure(...)  (existing proved core)
        ├─ if kind == "grind" and dampened and not picked(code).wanted:
        │        return DispatchDecision("suppress", "")               # NEW branch
        └─ else return DispatchDecision(kind, code)   (existing)
  → SUPPRESS ⇒ caller returns None ⇒ arbiter advances (existing semantics)
```

## Formal work (per project gate)

- Register + extract `next_tier_cap_pure` and `next_tier_dampened_pure`
  (extraction bridge alongside `Bridges` for the curve; oracle arm + differential
  test + mutation anchors — zero survivors).
- Honest theorems (all non-vacuous — no false-premise / always-true hypotheses):
  - **Cap bound:** `next_tier_cap ≤ max_skill_level` and `0 ≤ next_tier_cap` (given
    `0 ≤ max_skill_level`) — mirrors the curve's `curve_le_max` / `curve_nonneg`
    clamp proofs.
  - **Empty-band ⇒ no gate:** `next_tier_cap = 0 ⇒ ¬next_tier_dampened` — a skill
    with no gear in the next tier band is never dampened (this is what scopes the
    feature to gear-crafting skills; non-gear skills have `cap = 0`).
  - **Safety decode:** `next_tier_dampened current_skill cap = true ⇒
    (cap > 0 ∧ current_skill ≥ cap)` — the grind is suppressed only when the skill
    genuinely covers the whole next tier (a real precondition, satisfiable and
    falsifiable).
- **NOT claimed as a theorem:** the "self-lift" (gate releases as `char_level`
  climbs into the tier). The band *shifts* rather than widens, so `next_tier_cap` is
  not structurally monotone in `char_level` — releasing depends on higher tiers
  requiring higher craft levels, a data property. It is verified by regression test
  (below), not proved. Recording this here to avoid shipping a dishonest
  monotonicity theorem.
- Extend `formal/Formal/SkillStepDispatch.lean`: the new suppress branch is guarded by
  `not wanted`, so `forward_progress` / committed-progress properties still hold — a
  `wanted`/committed craft is never suppressed by the dampener. Because the dampener
  enters the wrapper as a precomputed `bool`, the proved `combine_dispatch_pure` core
  is unchanged; only the wrapper's post-combine branch and its theorem need updating.

## Testing (project suite; 0 errors/warnings/skips, 100% coverage)

- Gear-crafting skill that can craft all next-tier gear (`current_skill >= cap`) +
  throwaway pick → SUPPRESS.
- **Self-lift roll-up:** at `char_level` in one decade the skill is dampened; raise
  `char_level` across the decade boundary (band rolls to a higher tier whose `cap`
  exceeds `current_skill`) → `dampened` flips false → GRIND resumes. This is the
  data-dependent behavioral test that stands in for the (deliberately unproven)
  monotonicity.
- `wanted`/committed in-skill item picked under the gate → GRIND proceeds
  (need-exemption; suppress is `not wanted`-guarded).
- Task-gate path (`LevelSkillGoal` via `PURSUE_TASK`) unaffected by the dampener.
- Consumable skill (e.g. cooking) → `cap = 0` → `dampened` false → never suppressed.
- Boundary on the one real condition: `current_skill == cap` (gated, `>=`) vs
  `current_skill == cap - 1` (not gated).
- Pure-core unit tests for `next_tier_cap_pure` (empty band, gear-vs-nongear items,
  clamp to `max_skill_level`, band arithmetic across a decade boundary) and
  `next_tier_dampened_pure` (`cap = 0`, `current_skill` above/below/equal `cap`).

## Out of scope

- The endgame `ReachSkillLevel(skill, 50)` root / `target_skill_levels`.
- The `+3` curve floor (`SKILL_CURVE_LOOKAHEAD`).
- **Follow-up (not this feature):** rename `LevelSkillGoal` to a task-gate-specific
  name — it is not a generic skill-leveling goal; the current name misleads.

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
next_tier_dampened(current_skill, char_level, next_tier_cap, next_tier_floor) :=
      next_tier_cap  > 0
  and current_skill >= next_tier_cap      # crafts ALL next-tier gear
  and char_level    <  next_tier_floor    # next tier not yet level-appropriate
```

`gear_relevant` mirrors the curve: `stats.type_ in ITEM_TYPE_TO_SLOTS or
stats.subtype == "tool"`.

## Components

### New pure cores (extraction subset — mirror `skill_curve_target_pure`)

Location: new module(s) under `src/artifactsmmo_cli/ai/tiers/` (one behavioral unit
per file per project convention; these are pure functions + a small dataclass view,
so they may share a module like `skill_target_curve.py` does).

- `next_tier_cap_pure(skill: str, char_level: int, items: list[SkillItem],
  max_skill_level: int) -> int`
  Max `craft_level` over `gear_relevant` items of `skill` whose `item_level` lies in
  `[next_tier_floor, next_tier_floor + 9]`, clamped to `[1, max_skill_level]`;
  `0` when no qualifying gear item exists. Reuses the existing `SkillItem` view.
- `next_tier_dampened_pure(current_skill: int, char_level: int, next_tier_cap: int,
  next_tier_floor: int) -> bool`
  The boolean predicate above.

### Impure hoist

Extend the `objective_step_goal` path (impure caller of `skill_step_dispatch_pure`)
to compute, for the step's skill, `next_tier_cap` (over `game_data.all_item_stats`)
and `next_tier_floor` from `state.level`, and pass them into the dispatch. Mirrors
`skill_target_curve` hoisting `SkillItem` tuples from `GameData`.

### Dispatch integration

In `skill_step_dispatch_pure` (`skill_step_dispatch.py`): after the reservation
passes produce `pick`, if

- `pick != ""`, and
- the picked candidate is **not** `wanted` (throwaway), and
- `next_tier_dampened_pure(current_skill, char_level, cap, floor)` holds

then return `DispatchDecision(kind="suppress", code="")` instead of `("grind", pick)`.
The existing committed-item suppress (`combine_dispatch_pure`) is unchanged; the
dampener is an additional, `not wanted`-guarded suppress reason. New inputs
(`next_tier_cap`, `next_tier_floor`) thread through the pure signature.

## Data flow

```
objective_step_goal (impure)
  ├─ hoist candidates (existing) ─ each carries .wanted / is_target
  ├─ hoist next_tier_cap  = next_tier_cap_pure(skill, state.level, items, max_skill)
  ├─ next_tier_floor      = ((state.level // 10) + 1) * 10
  └─ skill_step_dispatch_pure(skill, current, committed…, candidates,
                              next_tier_cap, next_tier_floor)
        ├─ full/relaxed pick (existing proved selection)
        ├─ if pick and not wanted and next_tier_dampened(...) → SUPPRESS   # NEW
        └─ else combine_dispatch_pure(...) (existing)
  → SUPPRESS ⇒ caller returns None ⇒ arbiter advances (existing semantics)
```

## Formal work (per project gate)

- Register + extract `next_tier_cap_pure` and `next_tier_dampened_pure`
  (extraction bridge alongside `Bridges` for the curve; oracle arm + differential
  test + mutation anchors — zero survivors).
- Honest theorems (non-vacuous):
  - **Safety:** `next_tier_dampened ⇒ current_skill ≥ next_tier_cap` — the grind is
    suppressed only when the skill genuinely covers the whole next tier.
  - **Self-lift / liveness:** `char_level ≥ next_tier_floor ⇒ ¬next_tier_dampened`
    — once the next tier is level-appropriate the gate opens; grinding resumes. Rolls
    forward as `char_level` climbs (the band shifts up, `cap`/`floor` recompute).
  - **Cap bound:** `1 ≤ next_tier_cap ≤ max_skill_level` when `> 0` (mirrors the
    curve's clamp proof).
- Extend `formal/Formal/SkillStepDispatch.lean`: the new suppress branch is guarded by
  `not wanted`, so `forward_progress` / committed-progress properties still hold — a
  `wanted`/committed craft is never suppressed by the dampener.

## Testing (project suite; 0 errors/warnings/skips, 100% coverage)

- Gear-crafting skill a full tier ahead + throwaway pick → SUPPRESS.
- Same skill, `char_level` risen to `next_tier_floor` → GRIND resumes (self-lift).
- `wanted`/committed in-skill item craftable now under the gate → GRIND proceeds
  (need-exemption).
- Task-gate path (`LevelSkillGoal` via `PURSUE_TASK`) unaffected by the dampener.
- Consumable skill (e.g. cooking) → `cap = 0` → never dampened.
- Boundary: skill exactly at `cap` (>=) vs one below; `char_level` exactly at
  `next_tier_floor` (open) vs one below (gated).
- Pure-core unit tests for `next_tier_cap_pure` (empty band, gear-vs-nongear items,
  clamp to `max_skill_level`).

## Out of scope

- The endgame `ReachSkillLevel(skill, 50)` root / `target_skill_levels`.
- The `+3` curve floor (`SKILL_CURVE_LOOKAHEAD`).
- **Follow-up (not this feature):** rename `LevelSkillGoal` to a task-gate-specific
  name — it is not a generic skill-leveling goal; the current name misleads.

# Feasibility-aware task handling

Date: 2026-05-21
Status: Draft (awaiting user review)

## Problem

Robby accepts whatever task the taskmaster gives, then dead-ends on tasks he
cannot currently fulfill. Observed: he accepted the items-task
`small_health_potion` (×29). That potion needs **alchemy level 5** (ingredient
`sunflower`×3); Robby is **alchemy 1**, so `FarmItemsGoal` correctly finds no
plan. Nothing rescues him:

- `TaskCancelGoal` only cancels **monster** tasks (`if task_type != "monsters":
  return False`) — items tasks have no cancel path.
- `LowYieldCancelGoal` needs `FarmItems` yield samples to compare; FarmItems
  never produced any (it can't plan), so it stays priority 0.
- Result: every cycle is `<no_plan>`; the NO_PROGRESS recovery does refresh →
  wildcard (no-op at full HP) → `SystemExit(2)` — the bot quits.

## Goal

When a task requires a skill above the character's level, Robby:
1. recognizes the skill requirement,
2. treats *gaining the relevant skill XP* as a plannable prerequisite,
3. uses a value-per-cycle cost analysis to decide **skill-up-and-complete** vs
   **cancel-and-pivot**, and
4. can cancel **any** task type (fight and non-fight).

Tasks are random and cannot be previewed (`POST /my/{name}/action/task/new`
just "accepts a new task"), so feasibility is assessed **after** accepting.

## Data sourcing (per the API-source-of-truth rule)

### Skill XP-to-level progression
- The API exposes only the **current** level's requirement:
  `CharacterSchema.<skill>_max_xp` ("`<Skill>` XP required to level up the
  skill"). Authoritative for one level at a time.
- The full multi-level curve is **not** published (openapi has no formula/table;
  docs publish an XP-*gain* formula, not an XP-*to-level* table — see Citations).
- Therefore build a `SkillXpCurve`: a `(skill, level) -> required_xp` map
  populated from **observed** `<skill>_max_xp` values at runtime (recorded each
  cycle from the live CharacterSchema), persisted in the learning store.
  - Each entry is cited in code as "observed from CharacterSchema.<skill>_max_xp
    at level N on <date>".
  - **Estimating beyond the current level:** the current level's requirement is
    always known from the API. For higher, not-yet-observed levels, estimate
    each level's required_xp as a **multiple of the current known gap** —
    `required_xp(level+k) ≈ current_max_xp × growth_ratio**k`. This always
    yields a concrete estimate (no "unknown" punt).
  - **The growth ratio is learned, not hardcoded:** derive it from the ratios
    between *observed* consecutive levels (e.g. mean of `max_xp[n+1]/max_xp[n]`
    across observed pairs). With fewer than two observed levels for a skill, use
    a documented default ratio (cited) and mark the projection low-confidence.
    As the character levels up and more `max_xp` values are observed, the ratio
    and the per-level map refine toward the true progression.

### Task reward value
- Rewards are random from the task reward table; a task's value is an
  **expected** value learned from history, not a static number.
- Record the gold-equivalent value of rewards from **completed** tasks
  (`CompleteTask` "ok" cycles) into the learning store; the estimate is the
  running mean and **improves as more tasks complete**. Before any completion
  history exists, fall back to a documented default and widen the cost
  analysis's safety margin (treated as low-confidence).

## Components

### 1. Generalized task cancellation
`TaskCancelAction` already calls the API cancel (works for any task type). Change
`TaskCancelGoal` so it is no longer monster-only: it fires whenever the
cost-analysis decision (below) is **pivot**, for fight and non-fight tasks alike.
`is_satisfied` stays `not task_code or task_total == 0`.

### 2. Task-requirement extraction — `ai/task_feasibility.py` (new)
`task_requirement(state, game_data) -> SkillRequirement | None`:
- **items task**: look up the target item's `craft.skill` / `craft.level`. If an
  ingredient is itself craft-gated, recurse and take the max required level per
  skill. Returns the gating `(skill, required_level)` (or several).
- **monster task**: returns the monster-level-vs-character rule already used by
  TaskCancel (kept, generalized into this module).
- Returns None when the task is already feasible (char meets all requirements).

### 3. Skill-up as a planner prerequisite
`_build_goals` surfaces `LevelSkillGoal(skill -> required_level)` when the
**active task** needs a crafting skill the character lacks — mirroring the
existing equipment-gating LevelSkill logic (`_gating_skill_targets`). The
existing `LevelSkillGoal` already grinds a skill by crafting in its family, so
once it reaches the required level, `FarmItemsGoal` can craft the task item.

### 4. Cost analysis — value-per-cycle via projections
A decision function `task_decision(state, game_data, history) -> PURSUE | PIVOT`:
- `skill_up_cycles` = projected cycles to reach the required skill level (sum of
  `SkillXpCurve` required_xp across the gap ÷ observed skill-XP-per-cycle gain
  rate from history) **plus** projected cycles to produce `task_total` items.
- `task_value` = learned expected reward value (above).
- `skill_up_vpc` = `task_value / skill_up_cycles`.
- `alt_vpc` = best alternative goal's value-per-cycle from the scalarizer over
  the other applicable goals.
- Decision: `PURSUE` if `skill_up_vpc >= alt_vpc`, else `PIVOT`.
- Confidence: the projection always produces an estimate (current gap known;
  beyond-current levels estimated via the learned growth ratio). Confidence is
  **lower** when the gap spans many not-yet-observed levels or the growth ratio
  rests on few observations, and when reward history is empty. Low confidence
  biases toward PIVOT (don't commit to a long grind on a rough estimate);
  confidence rises as observed levels and completed-task rewards accumulate.
  Exact thresholds defined in the plan.

The decision drives goal priorities: PURSUE → LevelSkill + FarmItems run as
normal; PIVOT → `TaskCancelGoal` priority raised so the bot cancels and the next
cycle accepts a fresh task / pursues another goal.

## Build sequence (one spec, phased plan)
1. Generalized cancel (immediate unblock — Robby escapes the dead-end).
2. `task_feasibility` requirement extraction.
3. `SkillXpCurve` (observed map + persistence) and skill-XP-per-cycle rate.
4. Learned task reward value.
5. LevelSkill-as-prerequisite wiring in `_build_goals`.
6. Cost-analysis decision + goal-priority integration.

## Testing
Success per project standard: 0 errors, 0 warnings, 0 skipped, 100% on changed code.
- `task_requirement`: items (direct + recursive ingredient gating), monster, and
  already-feasible (None).
- Generalized `TaskCancelGoal`: fires for both monster and items tasks when the
  decision is PIVOT; satisfied when no task.
- `SkillXpCurve`: records observed `(skill, level) -> max_xp`; projects cycles
  across a gap of observed levels; handles unobserved levels as low-confidence.
- Learned reward value: mean over recorded completions; default + low confidence
  when empty; improves with more completions.
- `task_decision`: PURSUE when skill-up value/cycle wins; PIVOT when alternative
  wins; PIVOT under low confidence.
- Integration: the alchemy-5 potion scenario → Robby either grinds alchemy (if
  PURSUE) or cancels (if PIVOT); never a permanent `<no_plan>` / `SystemExit`.

## Citations
- `CharacterSchema.<skill>_max_xp` — "`<Skill>` XP required to level up the
  skill" (artifactsmmo_api_client/models/character_schema.py:35-56).
- Skill count/cap and XP-gain (not XP-to-level) formula:
  https://docs.artifactsmmo.com/concepts/skills
- No XP-to-level table/formula in `openapi.json` (verified: no "formula"/"xp to"
  entries; only per-level `max_xp` fields).
- Task accept is non-previewable: `POST /my/{name}/action/task/new` description
  "Accepting a new task." (openapi.json).

## Out of scope
- Pre-accept task filtering (API gives random tasks; impossible).
- Changing the XP-gain mechanics or the taskmaster reward tables.
- A hardcoded skill leveling curve (explicitly disallowed — observed map only).

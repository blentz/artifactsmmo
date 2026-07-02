# Alchemy Gather-Bootstrap (gather-to-level for gated gatherable skills)

## Problem

Live bug (Robby, char L8, 1215-cycle run): the bot never crafts or equips a
single healing potion, so it fights red_slime (L7) at ~50% and oscillates
`RestoreHP`↔fight until stuck-recovery exhausts (`goal_oscillation`, L3).

Reproduced root cause (against live data):
- The heal-potion root (`ObtainItem(small_health_potion, utility1_slot)`) IS
  emitted and DOES score 2.5 (the `POTION_SUPPLY_URGENCY` bootstrap boost fires).
- But once ≥3 sunflowers are held, its actionable step flips to
  `ReachSkillLevel(alchemy, 5)`. That step dispatches to **NO_GRIND** because
  `skill_grind_selection` only considers craftables at `craft_level ≤ current`,
  and **the lowest alchemy recipe is level 5** — nothing to craft-grind at
  alchemy < 5. `objective_step_goal` returns `None` (strategy_driver.py:~793),
  so the potion root is **unservable** and `keep_servable` drops it from the
  ranking. The bootstrap boost is nullified one layer down.
- **Alchemy levels only by GATHERING** (`sunflower_field` is an alchemy resource,
  L1). The trace proves it: alchemy XP grew only from `Gather(sunflower_field)`
  (cycles 5/8/9), then froze at ~L2 once the potion root stopped driving
  sunflower gathering. `LevelSkillGoal` can't help either (`_has_craftable_in_skill`
  is False at alchemy 2). The CraftPotions guard needs alchemy ≥ 5, so it never
  fires. Hard deadlock.

Design gap: the code assumes "gather skills self-level through ambient gathering
and cannot deadlock" (`skill_gates.py`, `skill_step_dispatch` docstring). That
holds for pure gather skills (mining/woodcutting level while gathering gear
materials) but NOT for alchemy: its resources are consumed only by potions, and
the potion root self-filters — so nothing drives ambient alchemy gathering.

## Decision (locked)

Integrate alchemy into the existing gather/craft skill bootstrap — bootstrap it
to level 5 like other gathering+crafting skills — via two parts:
- **Part A (proactive):** emit a bootstrap `ReachSkillLevel(alchemy, 5)` root.
- **Part B (mechanism):** serve a `ReachSkillLevel(gatherable_skill, N)` step by
  GATHERING the skill's resource when there is no craft-grind (NO_GRIND).

The proven `skill_step_dispatch_pure` core stays unchanged; the fix is in the
impure `objective_step_goal` wrapper + `prerequisite_graph` bootstrap.

## Design

### Helper 1 — gather resource for a skill

New pure function (own module `src/artifactsmmo_cli/ai/gather_skill_resource.py`):

```python
def best_gather_resource_drop(skill: str, current_level: int,
                              game_data: GameData) -> str | None:
    """Drop item of the highest-level resource gathered by `skill` at
    `level <= current_level`, or None when the skill has no gatherable resource
    usable now. Highest level = best XP/gather. Deterministic (ties on the
    smallest resource code)."""
```
Implementation: iterate `game_data.resource_skill` (`code -> (skill, level)`);
keep entries whose skill matches and `level <= current_level`; pick the max
`level` (tie: smallest code); return `game_data.resource_drop_item(code)`.

### Helper 2 — first craftable level for a skill

New pure function (same module or `skill_classes`-adjacent):

```python
def first_craftable_level(skill: str, game_data: GameData) -> int | None:
    """Lowest `crafting_level` among items whose `crafting_skill == skill`, or
    None when the skill crafts nothing."""
```
For alchemy this returns 5 (small_health_potion / recall_potion).

### Part A — bootstrap root for gatherable consumable-craft skills

In `prerequisite_graph.objective_roots` (the `state is not None` block, after the
`_CRAFTING_BOOTSTRAP_SKILLS` loop at line 143-145), add: for each skill that is
**gatherable** (has a resource in `resource_skill`) AND a **consumable-craft**
skill (`CONSUMABLE_CRAFT_SKILLS`), if `state.skills.get(skill, 1) <
first_craftable_level(skill, game_data)`, append
`ReachSkillLevel(skill, first_craftable_level(skill, game_data))`.

- This targets exactly alchemy today (cooking is consumable-craft but NOT
  gatherable → no gather resource → excluded; its craftables start at L1 so it
  craft-grinds normally).
- Bootstrap target is the skill's first-craftable level (5 for alchemy), not
  `_CRAFT_BOOTSTRAP_TARGET=2` — levelling alchemy to 2 is useless (still can't
  craft). Define a small constant/derivation, documented.
- `objective_roots` needs `game_data` access to compute this; it already receives
  `objective` (which holds `game_data`) and `state` — thread `game_data` in
  (via `objective._game_data` or an added param, matching existing access).

### Part B — serve NO_GRIND by gathering (the missing mechanism)

In `strategy_driver.objective_step_goal`, the `ReachSkillLevel` NO_GRIND branch
(strategy_driver.py:~793, currently `return None`), before returning None:

```python
        # NO_GRIND: no craftable to grind. If the skill is gatherable at the
        # current level, level it by GATHERING its resource (grind-one-replan) —
        # this is how a gatherable-but-no-low-craftable skill (alchemy: lowest
        # recipe L5, but sunflower_field gives XP at L1) climbs to its first
        # craftable level. Pure gather/craft skills with a craftable already took
        # the "grind" branch; skills with no gather resource fall through to None.
        drop = best_gather_resource_drop(step.skill, current, game_data)
        if drop is not None:
            bank = state.bank_items or {}
            held = state.inventory.get(drop, 0) + bank.get(drop, 0)
            return GatherMaterialsGoal(target_item=drop, needed={drop: held + 1})
        return None
```

Gathering the resource yields skill XP (the live gather advances the skill;
`GatherAction.apply` also advances `projected_skill_xp_delta` for planner
projection). Grind-one-replan (`held + 1`) mirrors the craft-grind branch: one
gather per cycle, replan, until the skill reaches the step's target — at which
point `ReachSkillLevel.is_satisfied` advances the potion root's step to the craft.
Accumulated resource (sunflower) is the potion ingredient, so the gathering
double-serves.

### Correct the stale assumption

Update the `skill_gates.py` module docstring and the `skill_step_dispatch`
NO_GRIND comment: gather skills self-level *only while some goal drives their
gathering*; a gatherable skill gated behind a craftable it can't yet make
(alchemy→potions) is now served by the Part B gather-to-level path, not left to
(absent) ambient gathering.

## Formal scope

`skill_step_dispatch_pure` / `skill_grind_selection_pure` are **unchanged** —
NO_GRIND still correctly means "no craft grind." Parts A/B are impure-layer
(prerequisite_graph root emission + objective_step_goal goal construction) plus
two pure helpers. The change only *adds* a servable path where the core returned
NO_GRIND, so it strengthens liveness (discharges a previously-assumed-away
deadlock) without weakening any `forward_progress`/`reservation_safety` theorem.
Unit tests only; no formal re-gate. Helper purity makes them cheaply testable.

## Testing

- **Helpers:** `best_gather_resource_drop` (alchemy@2 → sunflower drop; a skill
  with no gather resource → None; picks highest level ≤ current); `first_craftable_level`
  (alchemy → 5; a no-craft skill → None).
- **Part B:** `objective_step_goal` for `ReachSkillLevel(alchemy, 5)` at alchemy 2
  with no craftable returns `GatherMaterialsGoal(sunflower, needed={sunflower: held+1})`,
  NOT None. A `ReachSkillLevel` for a non-gatherable no-craft skill still returns
  None. A skill with a craftable still takes the grind branch (unchanged).
- **Part A:** `objective_roots` at alchemy < 5 includes `ReachSkillLevel(alchemy, 5)`;
  at alchemy ≥ 5 it does not; cooking (non-gatherable) is not added.
- **End-to-end reproduction:** the investigation's L8/alchemy-2 scenario — after
  the fix, the potion root's `ReachSkillLevel(alchemy,5)` step is servable (gather
  goal), so the potion root stays in the ranking (no longer dropped by
  `keep_servable`). Assert the potion root survives servability at ≥3 sunflowers.
- Full suite + mypy; 0 errors/warnings/skips, 100% coverage.

## Out of scope

- No change to the proven skill-dispatch/selection cores (no formal re-gate).
- No change to combat prediction, the win-rate veto, or red_slime selection — the
  fix makes potions available; combat readiness follows from having heals.
- Cooking / non-gatherable skills (handled correctly by exclusion, not special-cased).
- The [[project_repeated_action_failure_signal]] oscillation detector (separate,
  unmerged) — not needed once the deadlock is broken.

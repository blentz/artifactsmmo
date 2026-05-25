# Strategy Marginal-Value Goal Costing

Date: 2026-05-24
Status: Draft (for review)

Replace the strategy's self-cancelling `contribution / cost` root score with a
marginal-value model so goal selection reflects real leverage, rebalances as the
character progresses, and never decides by alphabetical tiebreak.

## Problem

`StrategyEngine` ranks Tier-1 roots — `ReachCharLevel(50)`, a
`ReachSkillLevel(skill, 50)` for all 8 skills, and an `ObtainItem` per gear slot
— by `score = contribution / cost`. For a skill root both terms are proportional
to the same `gap = 50 − current`:
`contribution = weight × (gap/50)`, `root_cost = gap`, so
`score = weight/50` — **the gap cancels.** Every skill scores identically and
forever (leveling a skill never changes its rank), so the sort falls to
`instrumental-first, then repr` → the bot grinds the alphabetically-first
instrumental skill (alchemy) to 50, then the next, ignoring character level and
gear. Selection is decided by the alphabet, not by value.

## Design

Score each root by a **marginal value** that does not cancel and that rebalances
with progress. Rank by value descending; effort is only a tiebreak.

```
value(root) = base_prior(category) × marginal(root) × balancing(root)
final(root) = learned_blend(root, value)        # §4
rank: sort by (-final, effort, repr)             # repr is dead last
```

The cancellation is gone because `marginal` and `balancing` are **not**
proportional to the 50-gap.

### Roots (unchanged set)

`objective_roots` still emits `ReachCharLevel`, `ReachSkillLevel(skill, 50)` for
all 8 skills, and `ObtainItem(gear)` per slot. Max-level/max-skills stays the
end goal; only the costing and the gear-gated-skill prerequisite (§3) change.

### `base_prior(category)` — direct-combat vs indirect leverage

Cold-start heuristic constants (a future P5 personality can scale these):

| Category | constant | value |
|---|---|---|
| Char level | `PRIOR_CHAR_LEVEL` | 1.0 |
| Combat gear — slots weapon/shield/helmet/body_armor/leg_armor/boots/ring1/ring2/amulet | `PRIOR_COMBAT_GEAR` | 1.0 |
| Utility/consumable gear — slots utility1/utility2/artifact1-3/rune/bag | `PRIOR_UTILITY_GEAR` | 0.4 |
| Combat-crafting skills — weaponcrafting, gearcrafting, jewelrycrafting | `PRIOR_COMBAT_CRAFT_SKILL` | 0.6 |
| Gathering skills — mining, woodcutting, fishing | `PRIOR_GATHER_SKILL` | 0.4 |
| Consumable-crafting skills — alchemy, cooking | `PRIOR_CONSUMABLE_SKILL` | 0.3 |

Skill-family sets are module constants. Gear category is decided by the root's
slot (`objective.target_gear` is slot→code; map the slot to combat vs utility).

### `marginal(root)` — what the next step buys

- **Gear (`ObtainItem`):** normalized equip-value gain over the current slot:
  ```
  gain = max(0.0, equip_value(target) − equip_value(current_slot_item))
  marginal = min(1.0, gain / GEAR_EQUIP_SCALE)
  ```
  `equip_value` is the existing helper; `current_slot_item` is what's equipped in
  the target's slot (0 when empty). `GEAR_EQUIP_SCALE` normalizes to ~[0,1]. An
  already-equipped target → gain 0 → `marginal` 0 → the root contributes nothing
  (it is also `is_satisfied` and excluded). First `copper_boots` over an empty
  slot → near-full marginal.
- **Char level:** `CHAR_MARGINAL = 1.0` — every level-up is a full unit of prime
  progress. (Winnability/plannability is enforced downstream: if no winnable
  monster exists the mapped grind goal won't plan and the arbiter falls through,
  so we don't gate marginal on it here.)
- **Skill→50 (standalone):** `SKILL_MARGINAL = 0.2` — pure "round out the sheet"
  is low/indirect; `balancing` then redistributes among skills.

### `balancing(root)` — laggard boost / leader suppression (skills only)

Gear and char-level: `balancing = 1.0`. For a skill `s` at level `l` with
`L_max = max(state.skills.values())`:
```
balancing(s) = clamp(1 + BALANCE_K × (L_max − l − BALANCE_THRESHOLD),
                     BALANCE_MIN, BALANCE_MAX)
```
with `BALANCE_K = 0.25`, `BALANCE_THRESHOLD = 2`, `BALANCE_MIN = 0.5`,
`BALANCE_MAX = 2.0`. The leader (`l = L_max`) → `0.5` (suppressed); 2 behind →
`1.0`; 6+ behind → `2.0` (laggard boost). One formula clusters the 8 skills and
kills the runaway.

**Worked example** (alchemy leads L5, others ~L1):
- level alchemy further: `0.3 × 0.2 × 0.5 ≈ 0.03`
- craft `copper_boots`: `1.0 × ~0.8 × 1.0 ≈ 0.8`
- level a lagging skill (cooking L1, 4 behind): `0.3 × 0.2 × 1.5 ≈ 0.09`

Gear/char-level dominate, laggards beat the runaway leader, fodder decays.

### §3 — Gear-gated skill: bounded prerequisite + value inheritance

When a target gear item's craft requires `crafting_skill` at `craft_level >
current skill`, the high-value reason to level that skill is the gear it unlocks.

- **Extend `prerequisites(ObtainItem(gear), state, game_data)`:** if the item is
  craftable and `state.skills[crafting_skill] < craft_level`, include
  `ReachSkillLevel(crafting_skill, craft_level)` in the returned prerequisites
  (alongside the material `ObtainItem`s). So `actionable_step` for the gear root
  descends into the skill gate when *that* is the binding constraint.
- **Bounded to `craft_level`** (not 50). The step is
  `ReachSkillLevel(skill, craft_level)`; `objective_step_goal` (unchanged) maps it
  to the P4 per-cycle `LevelSkillGoal` marching `current+1` until the skill
  reaches `craft_level`, the gate opens, and `actionable_step` then descends to
  the craft.
- **Value inheritance:** because the skill-leveling is the *gear root's*
  `actionable_step`, it is scored under the gear root (combat prior × equip-gain),
  not the skill's `0.2` standalone prior. Leveling the gating skill inherits the
  gear's high value; every other skill stays at the low balanced background.

Two distinct drivers for skill leveling result: (a) low balanced-background
progress toward 50 (§2 balancing), (b) high gear-gated need (§3 inheritance).

### §4 — Learned-refinement blend

```
final = (1 − w) × value  +  w × normalized_observed_xp_rate
w = LEARN_W_MAX × min(1.0, samples / LEARN_SAMPLE_FULL)
```
- **Signal:** the learning store's observed character-XP-per-cycle for the root's
  representative action, normalized: `min(1.0, observed_char_xp_per_cycle /
  XP_RATE_REFERENCE)`.
- **Where it applies:** only `ReachCharLevel` has a direct char-XP-producing
  representative action (fighting the winnable monster, via
  `expected_yield_per_cycle("FarmMonster(<combat_monster>)").char_xp` or the
  equivalent grind key). Gear and skill roots produce char-XP only indirectly and
  have no direct attribution, so for them `w = 0` → pure heuristic (the gear
  equip-gain is itself the future-XP proxy). This sharpens the combat/grind
  valuation — exactly the value the learned data can legitimately inform — while
  heuristics carry the indirect categories.
- **Cold-start:** `samples = 0 → w = 0 → final = value`, so behavior is sane from
  cycle 1 and improves as observations accrue.

Constants: `LEARN_W_MAX = 0.5`, `LEARN_SAMPLE_FULL = 20`, `XP_RATE_REFERENCE`
(tunable, ~ a strong observed char-XP/cycle).

### Ranking + what's removed

- `decide()` sorts candidates by `(-final, effort, repr)`. `effort` reuses the
  existing steps-remaining proxy (today's `root_cost`: levels-remaining for leaf
  roots, prereq-closure size for gear) — used ONLY to break near-equal-value ties
  (within `VALUE_EPSILON`); `repr` is the final, dead-last tiebreak.
- **Removed:** the `contribution / cost` ratio, `_contribution`'s share math as
  the score, and the `instrumental`-first sort term (`instrumental_skills` /
  `is_instrumental`). Gear-gated skills now get their priority from §3 value
  inheritance, not the instrumental flag; the flag/`RootScore.instrumental` field
  can be dropped or left always-False for trace compatibility.
- `RootScore` keeps `score` (now = `final`) for the trace; `contribution`/`cost`
  fields are repurposed to the pre-blend `value` and the `effort` so the log/TUI
  still render. `to_dict`/`to_trace` shape unchanged.

### Unchanged

- `objective_roots` root set; the per-cycle `LevelSkillGoal` (P4) and
  `GrindCharacterXPGoal`; the arbiter / driver mapping (`objective_step_goal`),
  except it now also receives gear-gated `ReachSkillLevel(skill, craft_level)`
  steps (already handled by the P4 current+1 mapping).
- `is_reachable`, `actionable_step` descent (extended only by §3's new prereq).

## Error handling

- Unknown item / missing `ItemStats` → `equip_value`/prereq treat as absent
  (gain 0, no skill gate); never raises.
- Empty `state.skills` → `L_max` falls back to 0; balancing neutral.
- No learned samples → `w = 0`; pure heuristic.
- Pure logic; no API, no `except Exception`.

## Testing

Per project standard: 0 errors, 0 warnings, 0 skipped, 100% on changed code.

- **`base_prior`:** each category → its constant; gear slot classified combat vs
  utility; each skill family → its tier.
- **`marginal`:** gear gain normalized & clamped (first-upgrade high,
  already-equipped 0, tiny upgrade small); char-level 1.0; skill 0.2.
- **`balancing`:** leader → 0.5; 2-behind → 1.0; 6-behind → 2.0 (clamped);
  gear/char-level → 1.0; empty skills → neutral.
- **`value` end-to-end / anti-degeneracy (the decisive test):** with alchemy
  leading and a craftable gear upgrade available, `decide()` ranks the gear root
  (and/or char-level) ABOVE leveling the leading alchemy; a lagging skill ranks
  above the leader; two skills no longer tie at an identical score — i.e. the
  alphabetical runaway is gone. Construct the prior degenerate state and assert
  the chosen_root is NOT "grind the alphabetically-first skill."
- **§3 gear-gated prereq:** a target gear whose craft needs skill L>current →
  `prerequisites` includes `ReachSkillLevel(skill, L)`; `actionable_step` returns
  it; it is scored under the gear root (its `value` equals the gear root's, not
  the skill standalone prior).
- **§4 blend:** no samples → final == heuristic; with seeded high char-XP samples
  on the char-level grind, final(char-level) rises by the expected blend; gear/
  skill roots unaffected (w=0).
- **Ranking:** sort by value desc; near-equal values broken by smaller effort;
  repr only when value AND effort tie. No `instrumental` term influences order.
- **Regression:** existing P3a strategy tests updated to the new scoring; trace
  (`RootScore.to_dict`) still renders.

## Files

- Modify `src/artifactsmmo_cli/ai/tiers/strategy.py` — replace `_contribution`
  /`root_cost`-as-score with `_value` + `_base_prior`/`_marginal`/`_balancing`/
  `_learned_blend` helpers + the skill-family/gear-slot category constants;
  rewrite `decide()` ranking; drop `instrumental_skills`/`is_instrumental` from
  the sort; adjust `RootScore` field population.
- Modify `src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py` — `prerequisites`
  emits the gear-gated `ReachSkillLevel(skill, craft_level)` prereq.
- Tests: `tests/test_ai/test_tiers_strategy.py` (+ prerequisite-graph tests) —
  new value/prior/balancing/§3/§4/ranking tests; curate existing score tests.

## Out of scope

- P5 personality weighting (these priors become its defaults later).
- Achievements as objective roots.
- Learned attribution of indirect char-XP to gear/skill goals (gear stays
  equip-gain-heuristic).
- Tactical layer (P4) and arbiter (P3c) — unchanged.

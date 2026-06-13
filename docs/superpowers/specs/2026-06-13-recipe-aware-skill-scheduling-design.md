# Design: recipe-aware skill scheduling

Date: 2026-06-13
Status: APPROVED (design) — ready for implementation plan.
Supersedes the deferred "time-aware step cost" framing in
`docs/PLAN_drop_farming.md` and the open `docs/PLAN_recipe_aware_skill_scheduling.md`.

## Problem

The arbiter commits to gear objectives whose craft is skill-gated, producing a
catch-up skill grind that freezes character-level progress. Live example
(run-7 trace 2026-06-12 23:01): char-level 7, weaponcrafting **2**, committed to
`water_bow` (lvl-5 weapon, a 2.6x attack upgrade) whose craft needs
weaponcrafting **5** — so the bot must grind weaponcrafting 2→5 in one block,
freezing leveling toward 50.

User's framing (run-7): not a bug — the skill DOES need leveling for better
gear; the real question is **optimal ordering**. Crafting skills should rise
gradually *along the way* so each tier's recipes are craftable just before they
are wanted, instead of a big jump. We know the recipe progression, so the
schedule is computable.

## Approach (decisions locked in brainstorming)

1. **Target curve = gear-path lookahead.** For each crafting skill, the level to
   hold now is derived from the recipe tree: the max craft-level over
   gear-relevant recipes whose `item_level <= char_level + LOOKAHEAD`.
2. **Interleave = gap-proportional priority.** A below-curve skill's root scores
   in proportion to `(target - current)`: small gap loses to combat, large gap
   wins, so skilling fires in bursts when a gap opens and combat leads otherwise.
3. **Placement = pure core + thin strategy wiring.** The curve is a proven pure
   core (Lean model + differential + mutation, matching the existing 15 cores);
   the root emission + scoring is thin impure glue under pytest.
4. **LOOKAHEAD = 3** levels (initial constant).
5. **Scope = all equippable + tool recipes** (not the single best-value item per
   slot). Slightly over-skills but keeps the core a clean pure function of
   game-data; a skill with no qualifying gear-relevant recipe is NOT scheduled.

## Architecture

### Component 1 — pure core: `src/artifactsmmo_cli/ai/tiers/skill_target_curve.py`

```python
def skill_target_curve_pure(
    char_level: int,
    items: list[tuple[str, int, int, bool]],  # (craft_skill, craft_level, item_level, gear_relevant)
    lookahead: int,
    max_skill_level: int,
) -> dict[str, int]:
    """For each craft_skill, the level to hold at char_level: the max
    craft_level over gear-relevant items with item_level <= char_level +
    lookahead, clamped to [1, max_skill_level]. Skills with no qualifying
    item are ABSENT from the result (not scheduled)."""
```

- PURE: no I/O, no game_data, no WorldState — plain-data params, extraction
  subset. Ships extracted to `formal/Formal/Extracted/SkillTargetCurve.lean` from
  day one (project policy).
- A thin wrapper `skill_target_curve(char_level, state, game_data)` hoists the
  `(craft_skill, craft_level, item_level, gear_relevant)` tuples from
  `game_data.all_item_stats` and passes `game_data.max_skill_level`.
  `gear_relevant = stats.type_ in ITEM_TYPE_TO_SLOTS or stats.subtype == "tool"`.
  Items with no `crafting_skill` (uncraftable) are dropped by the wrapper.

### Component 2 — hand model + proof: `formal/Formal/SkillTargetCurve.lean`

- Model `SkillItem` (craftSkill : Int, craftLevel : Int, itemLevel : Int,
  gearRelevant : Bool); `skillTargetCurve` mirrors the Python fold.
- Theorems (role contracts pinned in `Contracts.lean`):
  - `curve_monotone_in_char_level`: char_level ≤ char_level' ⇒ every emitted
    target at char_level ≤ the target at char_level' (skilling never
    un-targets as the character grows).
  - `curve_le_max`: every target ≤ max_skill_level (clamp earns this).
  - `curve_ge_one`: every emitted target ≥ 1.
  - `curve_absent_iff_no_item`: a skill is in the result iff some gear-relevant
    item of that skill has item_level ≤ char_level + lookahead.
- Extraction bridge in `formal/Formal/Extracted/Bridges*.lean` (next free file):
  extracted `skill_target_curve_pure` ≡ hand `skillTargetCurve` over an
  injective skill-code encoding (the CombatPicker / EquipmentScoring precedent).

### Component 3 — oracle + differential: `formal/Oracle.lean`,
`formal/diff/test_skill_target_curve_diff.py`

- New `runSkillTargetCurve` arm (item-block layout documented in the def).
- Hypothesis diff: random char_level, lookahead, item tables (craft_skill,
  craft_level, item_level, gear_relevant) — Python `skill_target_curve_pure`
  == Lean oracle, byte-equal dict.

### Component 4 — mutation anchors: `formal/diff/mutate.py`

- `skill_target_curve: drop +lookahead` (`item_level <= char_level + lookahead`
  → `<= char_level`) — kills items that should be in-window; diff catches the
  missing/lower targets.
- `skill_target_curve: drop clamp to max_skill_level` — lets a target exceed 50;
  diff catches.
- `skill_target_curve: max -> min over craft_level` — under-targets; diff catches.

### Component 5 — strategy wiring: `src/artifactsmmo_cli/ai/tiers/strategy.py`
(+ `objective.py` if root assembly lives there)

- Each cycle, compute `skill_target_curve(state.level, state, game_data)`.
- For each skill with `state.skills.get(skill, 1) < target`, emit a near-term
  `ReachSkillLevel(skill, target)` root — parallel to the existing near-term
  `ReachCharLevel(state.level + 2)` and near-term gear roots
  (`CharacterObjective.near_term_targets`).
- **Gap-proportional marginal**: the skill root's contribution is driven by
  `(target - current)` rather than the endgame `(50 - current)` gap. Reuse the
  existing `category_weight(category) × marginal / cost` ranking; only the
  skill-root marginal changes. Tune so gap 1 < combat, gap 2 ≈ combat, gap 3+ >
  combat (matches the approved preview).
- The endgame `ReachSkillLevel(skill, 50)` roots remain (long-horizon, low
  near-term priority); the near-term curve roots are the actionable ones, exactly
  as near-term vs endgame char-level/gear roots already coexist.

## Data flow

```
game_data.all_item_stats
  → wrapper: [(craft_skill, craft_level, item_level, gear_relevant)]
  → skill_target_curve_pure(char_level, items, LOOKAHEAD=3, max_skill_level)
  → {skill: target}
  → strategy: for skill where state.skills[skill] < target:
       emit ReachSkillLevel(skill, target), marginal ∝ (target - current)
  → arbiter ranks vs ReachCharLevel / gear roots (gap-proportional interleave)
  → actionable_step → skill_grind_target crafts an in-skill item (existing path)
```

## Error handling / edge cases

- Empty curve (no gear-relevant craftable items ≤ char_level+lookahead): no
  skill roots emitted; behavior identical to today (combat/gear lead).
- A skill already at/above target: no root (gap ≤ 0).
- `max_skill_level` clamp: a recipe whose craft_level somehow exceeds 50 cannot
  push a target past 50.
- No game-data / API failure: unchanged — the wrapper reads `all_item_stats`
  which is already loaded; this feature adds no new I/O.
- Reserved-set interaction: the existing `skill_grind_target(reserved=...)`
  guard (don't consume the committed root's recipe inputs) is unchanged; the new
  roots only change WHICH skill is targeted and WHEN, not the grind mechanics.

## Testing strategy

- **Pure core (formal gate):** differential Python≡Lean over random inputs;
  mutation anchors above must all die; Lean proofs of the four role contracts;
  `Contracts.lean` statement-pins.
- **Strategy wiring (pytest, 100% cov):**
  - below-curve skill emits a `ReachSkillLevel(skill, target)` root;
  - at/above target emits none;
  - gap-proportional ordering: gap 1 → combat outranks; gap 3 → skill outranks
    (the run-7 scenario: char 7, weaponcrafting 2, water_bow lvl5 → wc target 5,
    gap 3 → skill root outranks ReachCharLevel, so the skill rises *before* the
    gear commit forces a freeze);
  - skill with no qualifying recipe absent from the curve → no root.
- **Regression:** existing strategy/arbiter tests stay green; the near-term
  skill roots must not displace the proven near-term gear empty-slot dominance
  premise (Formal.GearPolicy).

## Out of scope (YAGNI)

- Tuning LOOKAHEAD per skill or per game phase — single constant 3 to start.
- Gathering-skill (woodcutting/mining/fishing) proactive targets beyond what the
  gear-relevant tool/recipe scope already pulls in — the curve naturally includes
  a gathering skill only when a gear-relevant tool recipe needs it.
- Replacing the arbiter's cost model wholesale (the deferred "time-aware step
  cost") — this feature makes the skill *targets* recipe-aware; it does not
  re-price every step.

## Open implementation notes

- Confirm where near-term roots are assembled (StrategyEngine vs
  CharacterObjective) when writing the plan; emit the skill roots in the same
  place as the existing near-term `ReachCharLevel(level+2)` root.
- Pick the next free `Bridges*.lean` file for the extraction bridge.
- Run `scripts/extract_lean.py` after writing the pure core; never hand-edit the
  extracted file.

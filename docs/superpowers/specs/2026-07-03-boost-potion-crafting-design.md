# Boost/Resist Potion Crafting (Potion Epic — Phase 2) — Design

**Date:** 2026-07-03
**Status:** Approved (design)
**Branch target:** new branch off `main`

## Problem

`predict_win` already **values and equips** owned boost/resist utility potions:
the effect handler maps `boost_dmg_<el> → ItemStats.dmg_elements[el]`,
`boost_res_<el> → resistance[el]`, `boost_hp → hp_bonus` (game_data.py:1340-1368);
`pick_loadout` equips the best owned boost into a utility slot
(loadout_picker.py:106); `project_loadout_stats` folds those stats into the
projected combat profile (equipment/projection.py:31). But the CraftPotions
economy is **heal-only** — `craft_potions_fires` checks only the default
`hp_restore` target (potion_supply.py:125), so the bot never *crafts* the boost
potions it already knows how to use. The offensive/defensive upside
`predict_win` models is unreachable because nothing acquires the item.

This is the genuinely remaining Phase 2 work (see
`project_predict_win_boosts_already_done`). It is distinct from the **shelved**
Phase 1.5 (crediting heal potions as effective HP in `WinnableAcrossBand` /
`predict_win`), which was dropped as an unsound proven-core behavior change with
no liveness gain (`project_phase15_shelved`). This design does **not** touch
`predict_win`'s boolean verdict, its `effective_hp = min(state.hp, p.max_hp)`
model (combat.py:201), or the `WinnableAcrossBand` liveness proof.

## Principle

Craft the boost potion that most improves the bot's combat margin against the
monster it is currently fighting — but only a boost it can craft **now** (no
skill grinding for an aspirational boost tier; mirrors the Phase 1 heal
discipline that killed the alchemy-16→45 grind). Heal supply keeps priority
over boosts (survival floor first).

## Non-goals

- No change to `predict_win`'s boolean output, its HP model, or any liveness
  proof. The margin helper shares `predict_win`'s arithmetic and leaves its
  verdict byte-identical.
- No new `GuardKind`. Reuse the existing `CRAFT_POTIONS` guard slot (a new kind
  breaks `allInLadderOrder` / `decide_key` — the craft-unlock-boosts lesson,
  `project_craft_unlock_boosts`).
- No skill grinding for boosts. Craftable-now only.

## Components

### 1. `combat_margin(state, game_data, monster_code) → int`

`predict_win` (combat.py:88) already computes the continuous margin and discards
it: `kill_step`/`rounds_to_kill` (combat.py:136-147), `die_step`/`rounds_to_die`
(combat.py:190-204), verdict `rounds_to_kill <= rounds_to_die if player_first
else rounds_to_kill < rounds_to_die` (combat.py:206).

Extract the shared arithmetic into a pure helper that returns the signed margin
`rounds_to_die - rounds_to_kill` (a `player_first` adjustment so the returned
integer's sign matches the verdict: win ⇔ margin ≥ 0 when player_first, margin >
0 otherwise — encode as `rounds_to_die - rounds_to_kill + (1 if player_first
else 0)`, then win ⇔ margin > 0, and the magnitude is the round cushion).
`predict_win` is refactored to derive its boolean from the SAME helper so its
output is **byte-identical** — the existing `PredictWin` differential + mutation
gate must stay green unchanged, and a test asserts the boolean is unchanged
across a fixture of monsters.

`combat_margin` is a pure core: same inputs as `predict_win`, no I/O, extracted
and gated by its own differential + mutation coverage.

**Edge cases:** unwinnable fight → margin ≤ 0 (or > 0 threshold per the
player_first encoding); a fight the bot cannot even scratch → large negative;
`state.hp == 0` mirrors `predict_win`'s `effective_hp = 0` path.

### 2. `best_boost_potion(state, game_data, monster_code) → str | None`

New pure core (own file, e.g. `src/artifactsmmo_cli/ai/boost_selection.py`).

Among items that are:
- `type_ == "utility"` with a boost effect present — `dmg_elements`,
  `resistance`, or `hp_bonus` non-empty/nonzero (NOT `hp_restore` — heals are
  handled separately), AND
- **craftable-now**: `stats.crafting_skill is not None` and
  `state.skills[stats.crafting_skill] >= stats.crafting_level` (identical gate
  to `target_potion_pure`, potion_supply.py:47),

compute the margin gain for each candidate:

```
gain(code) = combat_margin(project_equip(state, code), game_data, monster_code)
           - combat_margin(state, game_data, monster_code)
```

where `project_equip` yields a state whose loadout has `code` in a utility slot
(built via `project_loadout_stats(state, {utility1_slot: code, ...current...},
game_data)` — reuse the existing projection so the folded dmg/res/hp exactly
matches what `pick_loadout` would produce at runtime).

Return the candidate with the greatest **positive** gain (deterministic
smallest-code tie-break); `None` when no craftable-now boost yields a positive
gain. `None` is the normal "no worthwhile boost right now" signal, not an error
— the economy simply does not pursue a boost.

**Anti-grind:** because the candidate set is craftable-now only, a boost gated
behind a higher skill is never selected → the economy never grinds for it. If
alchemy (or the relevant skill) rises through normal play and unlocks a better
boost, it enters the candidate set automatically.

Pure core: extracted, differential + mutation gated.

### 3. Guard: extend `craft_potions_fires` (reuse `CRAFT_POTIONS`)

`craft_potions_fires(state, game_data)` (potion_supply.py:71) currently fires on
the unlock-boost path or the heal-supply path. Add a boost-supply branch:

- resolve the in-band target monster via `combat_target_monsters(state,
  game_data)` (combat_targets.py:27) — the primary/highest-priority winnable
  in-band monster (deterministic pick; `None` when the bot has no combat
  target, in which case the boost branch does not fire),
- `target = best_boost_potion(state, game_data, monster)`; fire when `target`
  is non-None AND `equipped_potion_qty(state, target) < potion_baseline_pure(...)`
  AND the recipe is producible (`_recipe_producible`, potion_supply.py:53).

Heal supply is checked first; the boost branch only contributes when heals are
stocked (survival floor priority).

### 4. Goal wiring: `CraftPotionsGoal`

`CraftPotionsGoal(effect="hp_restore", combat_monster=None, ...)`
(craft_potions.py:42) already threads an effect and the target monster.
`_target_potion` (craft_potions.py:56) selects the heal via
`target_potion_pure`. Extend target selection so that when the heal target is
already satisfied (equipped ≥ baseline) and a boost target exists, the goal
crafts the boost (`best_boost_potion(state, game_data, self._combat_monster)`).
The craft/equip ladder (`craft_utility_ladder`) is effect-agnostic — it crafts
and equips whatever code it is given into a utility slot — so no ladder change
is needed. Baseline qty reuses `potion_baseline_pure` (level-scaled).

## Data flow

```
combat_target_monsters(state) ── in-band target ──► best_boost_potion
                                                     │ (ranks craftable-now
                                                     │  boosts by combat_margin gain)
                                                     ▼
craft_potions_fires ──fires (beneficial+understocked+producible)──► CraftPotionsGoal
                                                     │ heal first, then boost
                                                     ▼
                          craft + equip boost ──► pick_loadout equips owned boost
                                                     ▼
                          predict_win already credits it (existing path)
```

## Error handling

Use only API data — `monster_attack`/`monster_resistance` (game_data.py:663/669),
item stats, recipes. No defaulting over missing data. `best_boost_potion`
returning `None` and `combat_target_monsters` returning empty are normal
"no boost pursuit" signals, handled by simply not firing the boost branch — not
errors. No `except Exception`.

## Testing / gate

- Success criteria (repo bar): 0 errors, 0 warnings, 0 skipped, 100% coverage.
- **`predict_win` unchanged:** a test asserts `predict_win`'s boolean is
  byte-identical for a fixture of monsters before/after the `combat_margin`
  extraction; the existing `PredictWin` differential + mutation gate stays green
  with no fixture regen.
- **New pure cores** `combat_margin` and `best_boost_potion`: unit tests over
  the win/loss/edge regimes + element-choice cases (monster whose attack element
  favors a `boost_res`, monster whose weakest resistance favors a `boost_dmg`,
  a `boost_hp` generic case, and a "no craftable-now boost → None" case), plus
  their own differential (Lean-vs-Python) + mutation groups. Follow the bag-slot
  lesson: any unit-killed mutation gets its OWN group bound to its unit test,
  not folded into a traversal-diff group.
- **Guard + goal integration:** guard fires only when a beneficial craftable-now
  boost is understocked+producible and heals are stocked; goal crafts+equips the
  boost; heal keeps priority.
- **Anti-grind regression:** a boost gated behind a higher skill is never
  selected (no `ReachSkillLevel` for a boost) — asserts the Phase-1 discipline
  holds for boosts.
- `mypy src` clean; `./formal/gate.sh` green (serialized).

## Files touched

- `src/artifactsmmo_cli/ai/combat.py` — extract shared margin arithmetic; add
  `combat_margin`; refactor `predict_win` to derive its boolean from it
  (output unchanged).
- `src/artifactsmmo_cli/ai/boost_selection.py` — new `best_boost_potion` core.
- `src/artifactsmmo_cli/ai/potion_supply.py` — boost branch in
  `craft_potions_fires`.
- `src/artifactsmmo_cli/ai/goals/craft_potions.py` — heal-then-boost target
  selection.
- `formal/diff/` + `formal/Formal/` — differential fixtures/harness and any
  Lean mirror for the extracted `combat_margin` core; `formal/diff/mutate.py`
  mutation groups (own group per unit-killed mutation).
- `tests/test_ai/` — unit + integration tests per the plan.

## Out of scope (future)

- A minimum margin-gain threshold beyond `> 0` (MVP crafts on any positive
  gain; craftable-now + producible already bounds cost).
- Multi-monster boost optimization (choosing a boost good across the whole band
  rather than the current primary target).
- Coverage-guard hardening for utility combat effects `predict_win` maps but
  ignores (separate minor task, `project_predict_win_boosts_already_done`).

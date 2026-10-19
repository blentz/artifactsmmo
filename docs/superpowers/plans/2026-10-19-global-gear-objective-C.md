# Global Gear Objective — Plan C (delete the ladder) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete every tier, rung, band and milestone surface, along with the gear sheets that sat beside `L*`. Move their last live readers onto `ctx.gear_objective`. Then gate the vocabulary so it cannot return.

**Architecture:**
- Plan A routed the root through `WhichPieceIsNext`, so the old root subtree, the ladder modules and the farm-target cascade survive only in tests, in two live readers of the old gear sheets, and in one write-only trace field.
- C works live readers first: each reader moves to `L*` with outcome tests (Tasks 1–2).
- Then it deletes in dependency order, one reviewable area per task (Tasks 3–6). It fixes the fixture-fidelity debts (Task 7), adds the grep gate (Task 8), and verifies.

**Tech Stack:** Python 3.13 (`uv run`), pytest, Lean 4 (`formal/`), `formal/diff`, `formal/diff/mutate.py`, `scripts/gen_*.py` censuses.

**Spec:** `docs/superpowers/specs/2026-10-18-global-gear-objective-design.md`, §3 (deletion table), §4 (formal/test surfaces) and §5.4 (grep gate). Plan B (`2026-10-19-global-gear-objective-B.md`) merges first: Task 1 here reads B's `tool_target`.

## Global Constraints

- Everything in Plan B's Global Constraints applies verbatim.
- Delete, do not patch: dead code goes away; it is not kept "covered by tests".
- When a test asserted rung, band or tier membership, it is deleted with its subject, or rewritten to assert an outcome (root, step, emitted action). No assertion is loosened to pass.
- A Lean theorem whose subject is deleted is retired with it. Regenerate `formal/Formal/Audit.lean` with `uv run python scripts/gen_audit.py`; never hand-edit it.
- Each deleted mutation group leaves `--check-anchors` green in the same commit.
- `equip_value` is NOT deleted. It has live consumers outside the ladder: `progression_reserve`, `prerequisite_graph`, `UpgradeEquipmentGoal` and `upgrade_selection`. That is the outcome of spec §3's "to be audited" row.

## Review Focus

1. **A held monsters task whose monster is not winnable** (`_task_root`). After Task 2 the root is the first missing piece of `L*(task monster)`, never `Wait`, never the deleted deficit walk. Test owned by Task 2.
2. **The `wanted` skill-grind preference.** It must still prefer crafting an `L*` piece or a `T*` tool over a non-target item at equal XP. Test owned by Task 1.
3. **The TUI status pane** after the path-plan fields are deleted. It renders the gear-objective line, not blank ETA fields, and nothing raises on a snapshot from an older run (old JSON keys are ignored). Test owned by Task 5.
4. **`max_level` from the API.** Season 9 may change the cap. The level-cap stop and the keep valuation read the loaded value. A status payload missing it raises. Test owned by Task 7.
5. **The grep gate's allow-list.** A new identifier `tier_x` in `src/` fails the gate. The priority bands (`BAND_*` in `strategy_driver`), the skill-grind `rung` vocabulary and the fixed `content_tiers` audit stay allowed by name, not by pattern. Test owned by Task 8.

---

### Task 1: Live readers of the old sheets read `L*`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/xp_demand.py:30-39` (`demand_roots`): `ObtainItem` for each `ctx.gear_objective.missing` code (empty when held or None) plus `T*` tools, instead of `ctx.target_gear | ctx.near_term_targets`.
- Modify: `src/artifactsmmo_cli/ai/task_worth.py:57` (`short_items`): same source.
- Modify: `src/artifactsmmo_cli/ai/tiers/skill_grind_target.py:226`: `wanted = c.code in objective_codes(ctx) or c.code == supply`.
- Create the helper `objective_codes(ctx) -> frozenset[str]` in `src/artifactsmmo_cli/ai/gear_objective_context.py`. It returns the missing `L*` codes plus `tool_target` codes for skills in `ctx.skill_demand`.
- Modify: `src/artifactsmmo_cli/ai/gear_objective_context.py` (`gear_keep_for`): drop the `near_term_targets` parameter; `with_objective_keep` already keeps every `L*` code.
- Modify: `src/artifactsmmo_cli/ai/selection_context.py:91-103` and `player.py:4030-4062`: delete `target_gear`, `target_tools`, `near_term_targets` and the stale CRAFT_RELIEF comments (`guards.py:78`, `selection_context.py:91-96`, `player.py:4029-4031`).
- Test: rewrite `tests/test_ai/test_xp_demand.py`, `test_task_worth.py`, `test_skill_grind_target.py` and `test_keep_economy_profiles.py` to build the objective (via `attached` or an explicit `GearObjective`). Fix every other constructor of the deleted fields (the inventory lists them: `formal/diff/test_ladder_fires_diff.py`, `test_perceive_arm_diff.py`, `test_objectivestep_arming_diff.py`, `test_tiers_means.py`, `test_tiers_strategy.py`, `test_objective_needs.py`, `test_fleet_objective.py`, `test_strategy_driver.py`, `test_player.py`).

**Interfaces:**
- Produces: `objective_codes(ctx: SelectionContext) -> frozenset[str]`. `SelectionContext` has no `target_gear`, `target_tools` or `near_term_targets`.

- [ ] **Step 1: Failing tests:**
  - `test_skill_demand_follows_the_missing_pieces`: Robby fixture with 3 missing pieces ⇒ `xp_demand` names their crafting skills; held objective ⇒ none from gear.
  - `test_wanted_prefers_a_missing_piece` (Review Focus 2).
- [ ] **Step 2–4: FAIL, implement, PASS.** Run the full suite and rewrite the newly failing tests to outcomes. Then commit `refactor(objective): skill demand and keep read L*, not the old sheets`.

### Task 2: A held task's unwinnable monster asks `L*` of that monster

**Files:**
- Modify: `src/artifactsmmo_cli/ai/gear_objective.py`. Expose `gear_objective_for(monster: str, state, game_data, ctx, history) -> GearObjective`. It is the same fixed point and the same pieces with `m` pinned. `gear_objective` calls it per candidate, so there is one implementation.
- Modify: `src/artifactsmmo_cli/ai/decisions/root.py:843` (`_task_root`) and `src/artifactsmmo_cli/ai/task_horizon.py:180`. Both replace `deficit_upgrade_target` with the first missing piece of `gear_objective_for(task_monster)`.
- Delete: `combat_deficit.deficit_upgrade_target` and its tests and mutation groups (`COMBAT_DEFICIT_TIEBREAK/FUTILE_TARGET/SECURE`, `ROOT_FIGHT_ARM_MUTATIONS`). Keep the `combat_deficit()` function (it is live at `obtain_item.py:146`).
- Test: `tests/test_ai/scenarios/test_held_task.py`, `tests/test_ai/test_task_horizon.py`

- [ ] **Step 1: Failing test** `test_an_unwinnable_task_monster_roots_its_first_missing_piece` (Review Focus 1), with the root asserted exactly.
- [ ] **Step 2–4: FAIL, implement, PASS.** Add mutants for the new arm, then commit `refactor(task): an unwinnable task monster roots L* of that monster`.

### Task 3: Delete the old root subtree and the ladder modules

**Delete:**
- `src/artifactsmmo_cli/ai/decisions/root.py`: `IsAFightBlockingMe`, `WhichSlotClosesTheFight`, `IsMyGearBehindMyTier`, `WhichSlotIsFurthestBehind`, `IsThereACombatTarget`, `CanIClearMyTier`, `_target_rung`, `_next_rung_above`, `_tier_gap`, `_is_dead_target`, `dead_target_slots`, `_slot_order`, and the dead `RootWalk` fields. Grep `sibling_targets` and `declined_targets` readers before deleting them. Also remove their imports (`HORIZON_GEAR`, `milestone_pure`, `ladder`, `tier_of_level`, `next_uncleared_tier`) and rewrite the header docstring (`:12-60`) for the live walk.
- `src/artifactsmmo_cli/ai/tiers/tier_ladder.py`, `tier_progress.py`, `band_target.py` and `progression_tree_core.py` (including the unused `GearCandidate` and `potion_type_weight`).
- `CharacterObjective.gear_targets_with_blockers`.
- Lean: `formal/Formal/ProgressionTree.lean` (all theorems; its subjects are deleted), with its `Formal.lean` import and Manifest entries. Regenerate Audit. Fix the stale citation in `formal/gate/check_proof_citations.sh:51-52`.
- Mutation groups: `ROOT_DECISION_MUTATIONS`, `TIER_CLEARED_BARE_MUTATIONS`, `BAND_UPKEEP/LOADOUT/PARTY_MUTATIONS`, `PROGRESSION_TREE_MUTATIONS`, `PROPPED_GEAR_MUTATIONS`, the dead part of `STEP_DECLINE_FIGHT_ARM_MUTATIONS`, and their `_ALL_SRCS` entries.
- Tests: `test_tier_ladder.py`, `test_tier_progress.py`, `test_band_target.py`, `test_band_target_wiring.py`, `test_progression_tree_core.py` and `test_max_gear_for_level.py`, plus the dead-node cases in `test_decisions_root.py`. Keep its `RootWalk`, `IsThisTargetBlocked`, `_task_root`, `_fleet_roots` and `_orphan_skill_roots` cases.

- [ ] **Step 1:** Delete, then run the full suite. Rewrite any surviving test that reached a deleted symbol to an outcome assertion, or delete it if its whole subject is gone. List both groups in the commit body.
- [ ] **Step 2:** `--check-anchors`, `lake build`, `gen_audit.py`. All green.
- [ ] **Step 3:** Commit `refactor(root): delete the tier walk and the ladder`.

### Task 4: Delete the farm-target cascade and the old picker

**Delete:**
- `player.py`: `_path_aligned_monster`, `_band_loadout`, `_band_party`, `_band_context`, `_tree_band_adequate`, `_pick_winnable_monster`, and the write-only `record["gear"]["adequate"]` line at `:2377`.
- `src/artifactsmmo_cli/ai/combat_picker.py` (`pick_winnable_monster_pure`).
- `tiers/progression_tree.py`: `_structural_candidates`, `has_structural_upgrade`. `decide_tree` stays.
- `equipment_profile.py:74`: the dead `band_adequate` parameter.
- `selection_context.combat_risky`, `combat_propped`, and their writers (`gear_objective_context.py:118`).
- `winnable_cascade.py`: the vestigial tier 3 (`pick_winnable` parameter). `farm_target` passes `None` today. Shrink `formal/Formal/WinnableCascade.lean` to the two-arm function (keep the `task_wins` and `totality` theorems, retire the tier-3 theorems), along with `Contracts.lean:2012-2052`, the oracle entry and `formal/diff/test_winnable_cascade_diff.py`.
- Lean: the picker parts of `formal/Formal/CombatTargetExistence.lean` (`pickWinnable`, `pickWinnableWindowed`, and their theorems), `Formal/Extracted/CombatPicker.lean`, `Bridges.lean:196,360-383`, oracle `:2212-2240`, and `formal/diff/test_combat_picker_diff.py`. Retire `test_winnable_across_band_diff.py` (spec §4). Keep any `CombatTargetExistence` theorem whose subject survives (`winnableFarmTarget` maps onto the shrunk cascade).
- Mutation groups: `COMBAT_PICKER_MUTATIONS`, `BAND_PICK_MUTATIONS`, `TREE_OCCUPANCY_MUTATIONS`, and the shrunk `WINNABLE_CASCADE_MUTATIONS`.
- Tests: the cascade cases in `test_player.py`, `test_player_retarget.py`, `test_blocker_memory.py`, `test_no_combat_deadlock.py` and `scenarios/test_band_liveness.py`. Rewrite each as an outcome over `farm_target`, or delete it. Also update `tests/test_audit/test_reachability_claims.py:289` and the claims census subject list.

- [ ] **Step 1–3:** As in Task 3. Commit `refactor(player): delete the three-tier farm-target cascade`.

### Task 5: Delete the level-path projection and its TUI fields

**Delete:**
- `learning/projections.cheapest_path_to_level` and `PathPlan`.
- The `ReachCharLevel` arm of `decisions/route.py:171`. No production caller prices a `ReachCharLevel`; the arm becomes an `assert not isinstance(goal, ReachCharLevel)`, with a test.
- `player._last_path_plan` and `_path_trace_snapshot`.
- The cycle-snapshot fields `projected_cycles_to_max`, `path_next_action` and `path_blocked` (`ai/cycle_snapshot.py:151-164`).
- The TUI readers: `tui/plan_summary.py:14-19`, `tui/widgets/status_pane.py:189-194` and `tui/screens/log_screen.py:27-38`. The status pane shows the gear-objective line instead: `monster`, held or missing count, and the first missing piece. Use the same text the `plan` command's `gear_objective:` line prints, from one formatter.
- Lean: `formal/Formal/CheapestPath.lean`, with its Manifest, Oracle and `Liveness/Measure.lean` references, and `formal/diff/test_cheapest_path_diff.py`, `level_cost_replay.py` and the stale report `.txt` files.
- Mutation group: `CHEAPEST_PATH_MUTATIONS`.

- [ ] **Step 1: Failing TUI test** `test_status_pane_shows_the_gear_objective` (Review Focus 3), plus `test_an_old_snapshot_with_path_keys_still_renders`.
- [ ] **Step 2–4:** Delete, implement the formatter, then run the full suite (including `tests/test_tui`). Commit `refactor(tui): the gear objective replaces the level-path ETA`.

### Task 6: Delete the old gear sheets and `pursuit_value`

**Delete:**
- `CharacterObjective.target_gear`, `near_term_gear`, `catalogue_best_gear`, `target_char_level`, `_gear_candidates_by_type`, `_item_value` and `utility_potion_targets` (no production caller). Keep `_slot_assignments` only if `from_game_data` still needs it after `target_gear` goes.
- `from_game_data` keeps building `target_tools` only if Plan B's `tool_target` did not replace every reader. Grep, and delete it if unread.
- `src/artifactsmmo_cli/ai/tiers/pursuit_value.py`, with its tests and Lean: `StrategicValue.lean` `pursuitValue` theorems, the `Contracts.lean:3060-3076` bindings, and pursuit parts of `Bridges7.lean`.
- Mutation groups: `PURSUIT_DOMINANCE_MUTATIONS`, `NEAR_TERM_POLICY_MUTATIONS` and `BEST_GEAR_MUTATIONS`. Re-anchor `OBJECTIVE_MUTATIONS` and `OBJECTIVE_OCCUPANCY_MUTATIONS`.
- `formal/Formal/Objective.lean:515-621` (`bestGear_optimal`, `best_gear_argmax`): retire with `target_gear`. Keep the `is_attainable` grounding.

**Modify:**
- `audit/craft_completeness.py:851,881` and `audit/craft_conditions.py` read `gear_objective` (via the shared `attach_gear_objective`) instead of `catalogue_best_gear` and `near_term_gear`. Regenerate `docs/craft_completeness/MATRIX.md`, `CONDITIONS.md` and `BACKLOG.md`, and name the moved counts in the commit body.
- `commands/sibling_route_report.py:337,348` prints text naming deleted symbols. Rewrite it.

- [ ] **Step 1–3:** As in Task 3. Commit `refactor(objective): one gear sheet, L*`.

### Task 7: Fixture and API fidelity

**Files:**
- Modify: `src/artifactsmmo_cli/game_data.py:888-902`. Delete `MAX_CHARACTER_LEVEL` and `MAX_SKILL_LEVEL`. `GameData` loads `max_level` and `max_skill_level` from the status endpoint (`StatusSchema`, required fields) into the cached bundle. A missing value raises. Readers: `which_piece_is_next.py:31`, `keep_valuation.py:64`, `objective.py:414` and the `player.py` snapshot.
- Modify: `src/artifactsmmo_cli/ai/scenario.py:195-250` (`_derived_combat_totals`). Base stats come from the live base sheet: initiative is 100 for every character (2026-10-19 live sheets stripped of gear read 100). Source the base values from `formal/sim/character_base_stats.json`, if it holds API-captured values. Read it first and say what it holds. Otherwise, capture base stats from the API into it with the existing capture script.
- Modify: `src/artifactsmmo_cli/audit/drop_wall_census.py:231-254` and `currency_wall_census.py:282`. A dropper is judged winnable by the per-monster achievable fighter (`gear_objective.fighter_owning`), as the objective judges it (spec §2.3), not by the scenario's worn gear. Regenerate both matrices. The "gate opens a wall" guard regains a witness or is retired with a stated reason.
- Test: `tests/test_ai/test_game_data.py`, `test_scenario_*`, `tests/test_audit/test_drop_wall_census.py`

- [ ] **Step 1: Failing tests:**
  - `test_max_level_comes_from_the_status_payload`, and `test_a_status_without_max_level_raises` (Review Focus 4).
  - `test_a_derived_scenario_starts_at_base_initiative_100`.
- [ ] **Step 2–4:** FAIL, then implement, then run the full suite, then rewrite the moved outcomes exactly. Commit each of the three changes separately.

### Task 8: The vocabulary gate (spec §5.4)

**Files:**
- Create: `scripts/gen_vocabulary_gate.py` and `src/artifactsmmo_cli/audit/vocabulary_gate.py`. Tokenize every `src/` file (Python `tokenize`, NAME tokens only, so comments are excluded). Flag an identifier whose snake/camel parts include `tier`, `rung`, `band`, `ladder` or `milestone`, unless the identifier is in an explicit `ALLOWED: dict[str, str]` (name → reason). Allowed names:
  - the priority-band names in `strategy_driver`, `arbiter_select`, `priority_band`, `scalar_priority` and the goals that clamp into a band;
  - the skill-grind `rung` names in `grind_rung`, `craft_plan_gen`, `grind_probe_state`, `rung_state_core`, `skill_grind_target`, `shed_reachability_completeness`, `craft_conditions` and `craft_completeness`;
  - `content_tiers`;
  - `LEVEL_BAND_*` in `combat_targets` and `inventory_caps`;
  - `potion_supply` ladder;
  - the `macro` segment bands;
  - the `inventory_*` `IN_BAND`;
  - nothing for the package: it is renamed (USER 2026-10-19: "yes" to renaming `ai/tiers/`). Rename `src/artifactsmmo_cli/ai/tiers/` to `src/artifactsmmo_cli/ai/progression/` with `git mv`. Rewrite every import in `src/`, `tests/`, `formal/diff/`, `scripts/` and `formal/diff/mutate.py` (its `*_SRC` paths). Do the rename as its own commit before the gate commit, with the full suite green.
  Each allowed name must still exist (an orphan entry fails), like `liveness_completeness`'s `DORMANT`.
- Modify: `formal/gate.sh`. Add `gen_vocabulary_gate.py --check` to the census block.
- Modify: `src/artifactsmmo_cli/ai/weapon_winnability.py` (`BAND_MARGIN`, `_band_monsters`). Rename these to level-window names rather than allow-listing them: they name a band of monsters around the character, which is the deleted concept.
- Test: `tests/test_audit/test_vocabulary_gate.py`

- [ ] **Step 1: Failing tests:**
  - `test_a_new_tier_identifier_fails` (Review Focus 5)
  - `test_a_comment_mentioning_tier_passes`
  - `test_an_orphan_allow_entry_fails`
  - `test_src_is_clean` (it fails before the step-3 renames)
- [ ] **Step 2–4:** FAIL, then implement and rename, then PASS. Commit `feat(gate): no tier, rung, band, ladder or milestone in src`.

### Task 9: Gate, live check, merge

- [ ] **Step 1:** Run the full gate in the background (as in Plan B Task 9), and read the rc in its own call. It must be green. Record suite wall time and hook time. The hook must stay at or below 11.25 min; the deletions should shrink it.
- [ ] **Step 2:** Run `mutate.py --only` over every touched source, with 0 survivors.
- [ ] **Step 3:** Run live `plan` for all 5 characters (token read in place, `eyJ` grep on logs). Roots and objective lines must match Plan B's live check, except where a deleted reader changed a demand. Explain each difference.
- [ ] **Step 4:** The controller runs the final whole-branch review, then merges per project rule and asks the user to restart.

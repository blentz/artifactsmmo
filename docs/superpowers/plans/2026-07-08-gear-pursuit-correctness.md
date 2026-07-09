# Gear-Pursuit Correctness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lock the two no-deadlock acceptance criteria as regression tests, remove the latent repr-sort tiebreak in `actionable_step`, and fix the equip-value cross-slot bug (a prospecting artifact outranking a weapon) by wiring `strategic_value`'s efficiency-budget as the tree's pursuit scorer — combat dominates cross-slot, utility still orders utility slots (no bag/rune/artifact regression).

**Architecture:** Investigation (2026-07-08) confirmed the current progression tree already satisfies both anti-deadlock criteria (gear-needs-skill pursues the skill-grind chain; full-build pivots to XP; combat-blocked targets re-target gracefully). This plan (1) pins that behavior, (2) replaces `sorted(unmet, key=repr)` with a semantic prerequisite order, and (3) introduces a single `pursuit_value` (strategic_value with a combat-dominant efficiency budget) replacing flat `equip_value` on the tree pursuit path only. The Phase-1/2 two-preset profile machinery (`ProfileKind`/`PROFILE_WEIGHTS`/`profile_for`/`score_for_profile`) is SUPERSEDED by the budget approach — left dormant (proven, unwired), retire later if confirmed dead.

**Tech Stack:** Python 3.13 (`uv`), pytest, Lean 4 + lake, formal/diff mutation gate.

## Global Constraints

- The Task-1 deadlock/ramp pins MUST stay green through Tasks 2-3 — they are the safety net for the behavior change. If Task 3 breaks one, that's a real regression, not a pin to re-derive.
- Efficiency-budget invariant (spec of strategic_value): with `efficiency_budget < combat_weight`, one point of `combat_raw` (× `combat_weight`) outranks the entire capped efficiency block, so any combat item beats any all-efficiency item cross-slot, while efficiency still orders efficiency-bearing/empty slots. `combat_weight = STRATEGIC_SCALE = 1000`.
- No regression: bags/runes/artifacts (utility slots) MUST still be pursued (nonzero pursuit_value) — the bug was utility outranking COMBAT slots, never utility being pursued at all.
- `pursuit_value` swap is scoped to the TREE pursuit path (`_structural_candidates`, `_utility_candidates`, `near_term_gear`, `_item_value`). Other `equip_value` callers (`UpgradeEquipmentGoal`, `pick_loadout`, `inventory_caps`, `prerequisite_graph`) stay on `equip_value` unless a Task-3 audit shows a caller shares the tree-pursuit semantics.
- Exact arithmetic (Fraction/int); no floats in the decision path; no inline imports; never catch Exception; TDD; 100% coverage; mypy strict.
- Anchored files (strategy.py, progression_tree.py, objective.py may carry mutate.py anchors) — static anchor sweep after every edit; rebind broken anchors in the same task.
- Never run gate.sh/mutate.py while the bot is running (`ps aux | grep "[a]rtifactsmmo play"`). Full gate owed at next bot downtime.

---

### Task 1: Pin the no-deadlock + combat-viability criteria as scenario tests

**Files:**
- Modify: `src/artifactsmmo_cli/ai/scenario.py` (add scenarios if the investigation's states aren't already in `SCENARIOS`)
- Create: `tests/test_ai/scenarios/test_no_deadlock.py`

**Interfaces:**
- Consumes: `ScenarioCharacter`/`scenario_state`/`load_bundle_game_data`/`SCENARIOS` (scenario.py), `GamePlayer.seed_offline`/`plan_from_state`, `assert_search_bounded` (`tests/test_ai/scenarios/search_bounds.py`).
- Produces: three pinned scenarios documenting the current-correct behavior.

Scenario derivations (BINDING — the investigation confirmed these outcomes; re-derive exact codes/levels against the bundle, pin the ACTUAL plan):
- **`l12_gearcrafting_gap`** (criterion 1): L12, copper gear equipped, `weaponcrafting`/`gearcrafting` ~5, `mining` ~10, an iron-tier equippable (real code, craft skill 10, item level ≤ 12) reachable. `derive_combat_stats=True`. Assert: `chosen_root` is `ObtainItem(iron_*)` (NOT `ReachCharLevel`); `selected_goal`/plan is a gather/craft skill-grind step (NOT `GrindCharacterXP`); search bounded. This pins "never deadlock on killing mobs when gear needs skilling."
- **`full_build_at_band`** (criterion 2): reuse `l20_dual_utility` or `l48_band_adequate` (band-adequate, no structural upgrade). Assert: `chosen_root` is `ReachCharLevel`/`GrindCharacterXP` when a monster is winnable (l20), or `Wait` with a documented reason when the event-gear wall blocks (l48) — NOT a skill/craft goal. This pins "never deadlock on skilling once full-build."
- **`combat_blocked_target`** (ramp): the criterion-1 char but with the iron target's material closure combat-blocked (no winnable dropper). Assert: the planner re-targets a reachable candidate OR `Wait` (documented) — NOT thrashing on unwinnable fights (no `GrindCharacterXP` against an unwinnable monster; `_pick_winnable_monster() is None` tripwire like the l48 test).

- [ ] Write the 3 tests asserting the ACTUAL current planner output (run each scenario, pin what it does, with a derivation comment). If any scenario does NOT behave as the investigation reported, STOP and report — the criterion may not actually hold. → red? no (documents current) → commit `test(scenarios): pin no-deadlock + combat-viability criteria as regression net`.

---

### Task 2: Semantic prerequisite order in `actionable_step`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py` (`actionable_step`, the `sorted(unmet, key=repr)` ~:62)
- Audit: `formal/diff/mutate.py` (is `actionable_step` anchored? if so rebind), `formal/Formal/*` (is the ordering proven?)
- Test: `tests/test_ai/test_tiers_strategy.py` (or wherever actionable_step is tested)

The current `sorted(unmet, key=repr)` orders unmet prerequisites alphabetically — `ObtainItem` reprs sort before `ReachSkillLevel` ('O'<'R'), so materials happen to be tried before skill gates. Replace with an EXPLICIT semantic key (`no_alphabetical_tiebreak` memory): a small priority function `_prereq_order(node)` ranking by prerequisite KIND (obtainable materials before skill-level gates before char-level gates, or whatever the correct dependency order is — DERIVE it from why materials-before-skill is correct: you need the mats in hand to craft, and skilling is the slower gate; document the rationale), with a semantic secondary key (e.g. code/skill name) NOT repr as the FINAL disambiguator only.

- [ ] Failing test: two unmet prereqs (an ObtainItem material + a ReachSkillLevel gate) whose repr order would flip under a rename — assert the SEMANTIC order holds regardless of repr. → implement `_prereq_order` → the Task-1 `l12_gearcrafting_gap` pin must still pass (same materials-before-skill outcome, now intentional) → if actionable_step is mutation/diff-anchored, rebind + kill-check → static anchor sweep → commit `fix(strategy): semantic prerequisite order in actionable_step (retire repr-sort tiebreak)`.

CAUTION: `actionable_step` is on the live decide path. Changing the order could change plans. The Task-1 pins + full scenario net are the guard — they must stay green. If the semantic order differs from the alphabetical one in any scenario, that's a behavior change to derive honestly, not silently accept.

---

### Task 3: `pursuit_value` — combat-dominant efficiency budget replaces flat equip_value

**Files:**
- Create: `src/artifactsmmo_cli/ai/tiers/pursuit_value.py` (or add to `equipment_profile.py` — one pure function)
- Modify: `src/artifactsmmo_cli/ai/tiers/progression_tree.py` (`_structural_candidates`, `_utility_candidates`), `src/artifactsmmo_cli/ai/tiers/objective.py` (`near_term_gear`, `_item_value`)
- Test: `tests/test_ai/test_pursuit_value.py`, extend the tree tests

**Interfaces:**
- Produces: `pursuit_value(stats: ItemStats) -> int` = `strategic_value(stats, weights, efficiency_budget=EFFICIENCY_BUDGET)` where `weights` gives combat `STRATEGIC_SCALE` and the four efficiency stats their derived rates (reuse `DEFAULT_STRATEGIC_WEIGHTS` OR a purpose-built vector — decide and document), and `EFFICIENCY_BUDGET = STRATEGIC_SCALE - 1` (one combat point outranks the whole capped efficiency block).

- [ ] Step A — `pursuit_value` + calibration pins (TDD): a pure-combat weapon (combat_raw 30) outranks a pure-utility artifact (prospecting 201) — the bug-gone pin, now via budget not zeroing; a bag (inventory_space > 0, combat_raw 0) has pursuit_value > 0 (still pursued — NO regression); two artifacts order by their efficiency stats; a combat item always beats any all-efficiency item regardless of the efficiency magnitude (structural dominance via budget). Commit.
- [ ] Step B — audit `near_term_gear`/`_item_value` callers: `grep -rn "near_term_gear\|\._item_value" src/`. For each caller, decide equip_value vs pursuit_value. The tree pursuit callers (`_structural_candidates`) get pursuit_value; document the disposition of every other caller (target_gear, etc.). Thread `pursuit_value` into the tree pursuit path only.
- [ ] Step C — swap `equip_value` → `pursuit_value` in `_structural_candidates`/`_utility_candidates` (both candidate value AND current_value baseline use pursuit_value, so gain is consistent) and in `near_term_gear`/`_item_value` on the tree path per the Step-B audit. `has_structural_upgrade` stays `bool(_structural_candidates(...))` — now combat-dominant, which is correct (band adequacy is a combat question).
- [ ] Step D — re-derive shifted pins: the tree per-scenario pins (l35 `perfect_pearl`-dominates, etc.) FLIP under pursuit_value (weapon/structural now wins; utility artifact drops below combat). Re-derive each honestly with a comment. The Task-1 deadlock pins MUST stay green (verify explicitly — a deadlock pin breaking = real regression, STOP).
- [ ] Step E — Lean/gate: `strategic_value` + its budget are already proven; if `pursuit_value` is a thin wrapper, add a nonneg/dominance witness only if genuine (Nat-structural → comment, no vacuous theorem). Mutation arm binding pursuit_value's combat-dominance if a sibling pattern exists. Static anchor sweep.
- [ ] Commit `fix(tree): pursuit_value combat-dominant budget — weapon beats artifact cross-slot, no utility regression`.

---

### Task 4: Wrap-up

- [ ] Full scenario net + suite green; the 3 deadlock pins + the bug-gone pins all pass together.
- [ ] Spec addendum in `docs/superpowers/specs/2026-07-08-equipment-profiles-design.md`: record that the two-preset binary switch (P1-P2) is SUPERSEDED by the single combat-dominant `pursuit_value` budget scorer (the investigation showed the tree already pursues skill-gated gear + the binary switch can't fire since tree roots are never `skills` + COMBAT-zero regresses utility). P1-P2 `ProfileKind`/`PROFILE_WEIGHTS`/`profile_for`/`score_for_profile` + `Formal/EquipmentProfile.lean` left DORMANT (proven, unwired); flag for possible retirement.
- [ ] IF bot down: `./formal/gate.sh`. Else record debt.
- [ ] Ledger + memory: gear-pursuit-correctness shipped; deadlock criteria pinned; equip-value cross-slot bug fixed via budget; repr-sort retired; profiles P1-P2 superseded/dormant.

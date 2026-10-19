# Global Gear Objective — Plan B (one route model, fleet amortization, tools) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One route model decides what an `L*` piece costs and how it is served. The fleet then shares each skill climb: one crafter per skill climbs it and supplies everyone. Gathering tools and crafting tools join the objective, so climbs run at full speed.

**Architecture:**
- Plan A judged achievability, price and the serving step under three different obtain policies: `GEAR_OBJECTIVE_POLICY`, `LEGACY` and `STEP_POLICY`. That split is why `lich_race_trophy` was achievable but unservable, and why a cheap GE amulet was served by a skill climb.
- B puts one policy behind all three. It carries the priced route on each `GearPiece` and serves the piece by that route.
- Then B publishes every missing piece to the fleet board, prices a skill-gated piece with the fleet's amortized climb, and picks the crafter per skill by least remaining climb seconds.

**Tech Stack:** Python 3.13 (`uv run`), pytest + hypothesis, Lean 4 (`formal/`), `formal/diff` differentials, `formal/diff/mutate.py`.

**Spec:** `docs/superpowers/specs/2026-10-18-global-gear-objective-design.md`. Read §2.1–2.6, §5.5–5.7 and §6. This plan implements §2.5, the `T*` part of §2.2 and §2.6, and the pricing and serving residuals of Plan A (`docs/superpowers/plans/2026-10-18-global-gear-objective-A.md`, merged @0729763b).

**Out of scope:** Season 9 altar favors (§2.6). The test server is members-only, so the altar API is blind until launch on 2026-10-31. They join `R` and the climb seconds as live modifiers in a follow-up plan, once the API exposes them.

**USER decision 2026-10-19:** "yes, live sell order counts as a route just like an event". A standing GE sell order is an achievable, priced and servable route while it stands.

## Global Constraints

- `unset VIRTUAL_ENV; uv run …` for every Python command. Never `timeout uv`.
- Never use inline imports. Never catch `Exception`. No `if TYPE_CHECKING`. One behavioral class per file. Use absolute imports.
- Use API data only. A missing datum raises; it never defaults.
- Tests must end with 0 errors, 0 warnings, 0 skipped (the 2 token-gated live-catalog skips are known) and 100% coverage on `tests/`.
- Never use an alphabetical or `repr` tiebreak in a decision ordering.
- New code never computes tier, rung, band, ladder or milestone.
- Acquisition price orders `L*` pieces and never downgrades `L*` (§6.1).
- No fight is chosen for XP while an `L*` piece is missing (§6.2).
- Expected live outcome (§5.6): several days of fleet skill grind with near-zero character XP is CORRECT.
- Commit with `ARTIFACTSMMO_TOKEN=dummy`, in the background with an rc file (the hook takes about 9.5 min). Stage files explicitly and never chain `git add` with `;`. Never use `--no-verify`, `git stash` or `git checkout <path>`. Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Every new decision branch gets a mutant in `formal/diff/mutate.py`, and stale anchors are refreshed in the same commit (`--check-anchors`). The runner reads COMMITTED sources.
- The real token is the git-ignored `/home/blentz/git/artifactsmmo/TOKEN`. Read it in place with `"$(cat …)"`. Never copy, print or commit it.
- Tests that only read the catalogue use `tests/test_ai/shared_world.py` (`shared_world`, `attached`). A test that mutates a `GameData` builds its own.

## Review Focus

1. **An event vendor whose event is down.** `lich_race_trophy` must then be neither achievable nor a missing piece. While the event is live, it must be both achievable and served by a real step. Achievable but unservable never happens. Test owned by Task 2.
2. **A GE sell order that disappears between cycles.** The next cycle's `L*` drops the piece, or re-prices it through its next route; no `GeBuy` is emitted against a vanished order. Test owned by Task 2.
3. **Two characters missing pieces gated on one skill (§5.5).** Exactly one, the one with the least remaining climb seconds, takes the climb. The other publishes demand and receives the piece by bank withdraw, and neither picks an XP fight. Test owned by Task 7.
4. **A crafter whose role skill reaches the demanded level.** It releases the role (release-on-idle). It must not keep climbing a skill nobody needs. Test owned by Task 7.
5. **A tool for the skill being climbed that is achievable but not owned.** It is pursued before the climb's next level. A tool already owned (bag, bank or worn) is never re-acquired. Test owned by Task 8.

---

### Task 1: Expected damage respects the turn cap and the fighter's own HP

**Files:**
- Modify: `src/artifactsmmo_cli/ai/expected_damage.py` (`expected_damage_per_fight`)
- Modify: `src/artifactsmmo_cli/ai/fight_terms_core.py:82` (`kill_rounds`), only if its no-barrier branch lacks the cap. Keep it in step with its Lean twin (grep `kill_rounds` in `formal/Formal`).
- Test: `tests/test_ai/test_expected_damage.py`

**Interfaces:**
- Produces: `expected_damage_per_fight(state, game_data, monster_code) -> int`. Its rounds are `min(rounds_to_kill, MAX_TURNS)`. A kill step that rounds to 0 at `SCALE` counts as `MAX_TURNS`.

- [ ] **Step 1: Failing tests:**
  - `test_damage_never_exceeds_the_turn_cap`: a fighter whose kill step is positive but below `1/SCALE` gives `expected_damage_per_fight == round(monster_per_turn) * MAX_TURNS`.
  - `test_pixie_on_the_l48_raid_sheet_is_bounded`: the `l48_raid_active` scenario state (shared world) gives `expected_damage_per_fight(state, gd, "pixie") <= round(monster_per_turn) * MAX_TURNS`. It was 1,844,857 before the fix.
  - `test_a_bare_fighter_with_no_damage_still_reads_zero`: pins the existing early exit.
- [ ] **Step 2: Run, and see it FAIL on the first two.**
- [ ] **Step 3: Implement the cap.** If `kill_rounds` changes, update the Lean twin and its differential in the same commit.
- [ ] **Step 4: Rewrite `tests/test_ai/scenarios/test_l48_raid_pair.py`.** Recompute it against the fixed value, and assert the plan outcome on both poles exactly. If the raid is now survivable, the positive pole is real again. The raid still yields to a missing piece (Plan A ruling Z), so assert what the walk now emits.
- [ ] **Step 5: Add the mutants** (`min` → raw rounds; the zero-step guard removed), then commit `fix(combat): expected damage stops at the turn cap`.

### Task 2: One route policy for `L*` pieces

**Files:**
- Modify: `src/artifactsmmo_cli/ai/obtain_model/policy.py`. Replace `GEAR_OBJECTIVE_POLICY` with `PIECE_POLICY`, which is `GEAR_OBJECTIVE_POLICY` with `ge_routes=True`. A `GE_FILL` route is ready only while a standing sell order exists, the same way `VENDOR_TRADEABLE` gates an event vendor. Confirm the existing `GE_FILL` route already requires a live order. If it does not, add that gate to the route's gates, not to the policy.
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py:132`. Delete `STEP_POLICY`; `actionable_step`/`_producible` use `PIECE_POLICY`.
- Modify: `src/artifactsmmo_cli/ai/decisions/route.py:105`. `route_price(…, policy: Policy = LEGACY)` forwards `policy` to `acquisition_actions`.
- Modify: `src/artifactsmmo_cli/ai/gear_objective.py` (`achievable`, `_price`). Both use `PIECE_POLICY`.
- Test: `tests/test_ai/test_piece_policy.py`. Rewrite `tests/test_ai/scenarios/test_ge_market_triple.py` cell 5.

**Interfaces:**
- Produces: `PIECE_POLICY: Policy`. It is the single policy used for achievability (`gear_objective.achievable`), price (`gear_objective._price`) and the step graph (`tiers/strategy.actionable_step`).

- [ ] **Step 1: Failing tests:**
  - `test_one_policy_answers_all_three`: for every missing piece of every catalogued scenario objective (`shared_world`), `piece achievable ⇒ actionable_step(ObtainItem(piece)) is not None ∨ the piece is skill-gated (ReachSkillLevel in front)`. It was false before for `lich_race_trophy`.
  - `test_an_event_vendor_counts_only_while_live`: with the archaeologist's event live, `lich_race_trophy` is achievable and its root step is a real step, not declined. With the event down, it is absent from `L*`. If the archaeologist is not event-gated in the bundle, the test asserts its real gate instead, and the report says so.
  - `test_a_standing_order_is_a_route_while_it_stands`: the `ge_market_triple` amulet with its order prices through `GE_FILL`. Without the order it reprices through its next route.
  - `test_ge_market_triple` cell 5: the first planned action is the `GeBuy` of the amulet. It was the Plan A known defect (the jewelrycrafting climb).
- [ ] **Step 2: Run, and see it FAIL.**
- [ ] **Step 3: Implement.** Then run the full suite and rewrite each newly failing test to its new outcome, as an exact assertion. List them in the commit body.
- [ ] **Step 4: Add the mutants** (`ge_routes` off, `event_vendors` off, and each consumer back on its old policy), then commit `feat(objective): one policy prices, judges and serves an L* piece`.

### Task 3: A piece is served by the route that priced it

**Files:**
- Modify: `src/artifactsmmo_cli/ai/acquisition_cost.py`. Add `cheapest_route(item: str, qty: int, state, game_data, ctx, store, *, policy: Policy) -> tuple[int, SourceKind]`. It is the argmin `acquisition_options` already computes, with the same tie order as `acquisition_cost`. `acquisition_actions` calls it, so there stays one pricer.
- Modify: `src/artifactsmmo_cli/ai/gear_objective_result.py`. `GearPiece` gains `route: SourceKind`.
- Modify: `src/artifactsmmo_cli/ai/gear_objective.py`. `_price` returns `(price, route)`.
- Modify: `src/artifactsmmo_cli/ai/decisions/which_piece_is_next.py`. `classify_target` (crafting gate first) is consulted only when `piece.route` is `CRAFT`. Every other route resolves to `ObtainItem(code, 1, slot=slot)`.
- Test: `tests/test_ai/test_decisions_which_piece.py`

**Interfaces:**
- Produces: `GearPiece(slot, code, layer, gain, price, route)`. `cheapest_route` as above.

- [ ] **Step 1: Failing tests:**
  - `test_a_bought_piece_is_never_a_climb`: a piece whose `route` is `BUY` or `GE_FILL` and whose craft gate is unmet gives root `ObtainItem`, not `ReachSkillLevel`.
  - `test_a_crafted_piece_still_climbs`: `route` is `CRAFT` with the gate unmet, so the root is `ReachSkillLevel(skill, current+1)`.
  - `test_cheapest_route_matches_the_price`: for each piece in the Robby fixture, `cheapest_route(...)[0] == acquisition_actions(...) - EQUIP_ACTIONS`.
- [ ] **Step 2–4: FAIL, implement, PASS.** Add mutants for the route check, then commit `feat(objective): a piece is served by the route that priced it`.

### Task 4: Gain is what the piece adds to `L*`, not to a bare fighter

**Files:**
- Modify: `src/artifactsmmo_cli/ai/gear_objective.py:431` (the `gains` computation)
- Test: `tests/test_ai/test_gear_objective.py`

**Interfaces:**
- Produces: `GearPiece.gain = R(L*) − R(_target(L* minus piece))`, leave-one-out with a re-pick, clamped at 0. `R` is the existing `rate_owning`.

- [ ] **Step 1: Failing test** `test_gain_is_leave_one_out_from_the_target`: on the Robby fixture, the gains of the missing pieces are not all 0 (they were before on a bare baseline). Each gain equals its leave-one-out value computed in the test from `rate_owning`.
- [ ] **Step 2–4: FAIL, implement, PASS.** Note the measured `gear_objective` CPU time in the report; the Plan A ruling P bound of < 2.0 s per warm cycle still holds. Add a mutant (bare baseline restored), then commit `fix(objective): a piece's gain is measured against L*`.

### Task 5: A raid that feeds the chosen piece may fight

**Files:**
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py:687` (`raid_may_fight`) and its caller at `:1464`.
- Test: `tests/test_ai/test_strategy_driver.py`

**Interfaces:**
- Produces: `raid_may_fight(objective, chosen_root, boss_drops, closure: frozenset[str]) -> bool`.
  - It is True when the objective is None or held.
  - It is also True when a boss drop is in `closure`. `closure` is the `requirement_closure` of the chosen root's item. A `ReachSkillLevel` root uses its `skill_grind_target` item.

- [ ] **Step 1: Failing tests:**
  - `test_a_raid_dropping_a_material_of_the_piece_may_fight`: the boss drops a recipe input of the chosen piece, so the result is True.
  - `test_an_unrelated_raid_still_waits`: False.
- [ ] **Step 2–4: FAIL, implement, PASS.** Add a mutant, then commit `fix(arbiter): a raid feeding the chosen piece's recipe may fight`.

### Task 6: Every missing piece goes on the fleet board

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py:3073` (`_own_unmet_demand`). Its roots are every `ctx.gear_objective.missing` piece's `ObtainItem`, plus `self._last_decide_crafting_target`. This replaces the chosen root plus `_last_blocked_target`. Each code is netted against bag and bank, as today.
- Modify: `src/artifactsmmo_cli/ai/learning/coordination_store.py:481` (`publish_demand`). Each row also carries `gain` and `price` (new nullable columns in the `demand` model, migrated the same way earlier columns were added: grep the existing migration pattern in `learning/models.py`).
- Test: `tests/test_ai/test_player_coordination.py`

**Interfaces:**
- Produces:
  - `publish_demand(demand: Mapping[str, int], self_servable: frozenset[str], now, piece_value: Mapping[str, tuple[Fraction, Fraction]])`, where the value is `code → (gain, price)`.
  - `sibling_demand_values(now) -> dict[str, Fraction]`, mapping `code →` the summed gain over every sibling that publishes it.

- [ ] **Step 1: Failing tests:**
  - `test_every_missing_piece_is_published`: an objective with 3 missing pieces, one skill-gated, publishes all 3 closures, and the gated piece is not self-servable.
  - `test_a_held_objective_publishes_no_gear_demand`.
  - `test_published_values_sum_over_siblings`.
- [ ] **Step 2–4: FAIL, implement, PASS.** Add mutants (chosen-root-only restored; netting removed), then commit `feat(fleet): every missing L* piece is published`.

### Task 7: The fleet shares each skill climb

**Files:**
- Create: `src/artifactsmmo_cli/ai/fleet_climb_core.py`, with `amortized_climb_seconds(remaining: Fraction, units: int) -> Fraction` (`remaining / units`; asserts `units >= 1`) and `climber(remaining_by_character: Mapping[str, Fraction], committed_by_character: Mapping[str, int]) -> str`. `climber` returns the argmin of `(remaining, committed)`; on a full tie it falls back to fleet order (`fleet_characters` order). It never orders by name.
- Create: `formal/Formal/FleetClimb.lean`. Theorems:
  - `amortized_le_remaining`
  - `amortized_antitone_in_units`
  - `climber_minimal`, meaning no character has strictly less `(remaining, committed)`
  Register it in `Formal.lean`, `Manifest.lean` and the oracle. Add the differential `formal/diff/test_fleet_climb_diff.py`.
- Modify: `src/artifactsmmo_cli/ai/acquisition_cost.py:447` (`_sibling_craft_option`). When no sibling meets the skill gate yet, it prices `CRAFT` at `BANK_VENUE` with `unlock_actions = amortized_climb_seconds(climber's remaining climb seconds, fleet units gated by that skill)` (in actions, by the existing seconds→actions conversion) + craft + bank transfer. Remaining climb seconds are `(xp to the demanded level) / skill_grind_rate`, with the fleet rate as fallback, exactly as `route.py` prices `ReachSkillLevel`.
- Modify: `src/artifactsmmo_cli/ai/role_selection.py:421` (`decide_role`). It takes `sibling_skill_levels: Mapping[str, Mapping[str, int]]` and `demanded_level: Mapping[str, int]`. A character claims a craft role only if `climber(...)` over the live fleet names it for that role's craft skill. Release-on-idle and release-on-unservable are unchanged. The demand driving `demand_by_role` is the fleet board from Task 6.
- Modify: `src/artifactsmmo_cli/ai/decisions/which_piece_is_next.py`. Spec §2.5 "the crafter's own objective": for a character holding a craft role, the fleet pieces it serves join its `missing` list. These are the board codes gated on its role skill that it does not hold. Each joins with `gain = sibling_demand_values` (summed over receivers) and is ordered by the same `piece_order_key`. The objective counts as held only when its own pieces AND those fleet pieces are served, so the XP trunk is never offered while fleet demand it serves exists.
- Test: `tests/test_ai/test_fleet_climb_core.py`, `tests/test_ai/test_role_selection.py`, and a two-character scenario `tests/test_ai/scenarios/test_fleet_amortized_climb.py`.

**Interfaces:**
- Consumes: Task 6 board rows and `ctx.sibling_skills`.
- Produces: the two core functions above, and `decide_role(…, sibling_skill_levels, demanded_level)`.

- [ ] **Step 1: Failing tests** (spec §5.5):
  - `test_only_the_least_remaining_climber_takes_the_role`: two characters, both missing a gearcrafting-gated piece, gearcrafting 20 vs 23 against demanded 30. The 23 claims "logger"; the 20 does not.
  - `test_the_other_receives_by_withdraw`: after the crafter banks the piece with a claim, the other's root plans `Withdraw` → `Equip`.
  - `test_neither_picks_an_xp_fight`: neither plan contains a fight whose goal is `GrindCharacterXP` or `ReachCharLevel`.
  - `test_the_role_releases_at_the_demanded_level` (Review Focus 4).
  - `test_a_crafter_with_own_l_star_held_still_serves_the_fleet`: the crafter holds its own `L*`, but a sibling's piece gated on its role skill is on the board. Its root is that piece (or the climb in front of it), never `ReachCharLevel`.
  - Core tests: `amortized_climb_seconds(Fraction(100), 4) == 25`; `units=0` raises; the `climber` tie goes to fewer committed.
- [ ] **Step 2–4: FAIL, implement (core, then Lean, then differential, then wiring), PASS.** Add mutants for each core branch, the role gate and the new route option. Commit the core with Lean as `feat(fleet): amortized climb core`, then the wiring as `feat(fleet): one crafter climbs for the fleet`.

### Task 8: Tool targets `T*` for the skill being climbed

**Files:**
- Create: `src/artifactsmmo_cli/ai/tool_objective.py`, with `tool_target(skill: str, state, game_data, ctx) -> str | None`. It returns the level-legal item with the largest `tool_value(stats, skill)` (`tiers/equip_value.py:54`) among items achievable under `PIECE_POLICY`, or None. It returns None when the best one is already owned (bag, bank or worn). It is data-driven on `skill_effects`, so Season 9 crafting tools (§2.6) qualify with no code change.
- Modify: `src/artifactsmmo_cli/ai/decisions/which_piece_is_next.py`. When the resolved root is `ReachSkillLevel(skill, …)` and `tool_target(skill, …)` is not None, the root is `ObtainItem(tool)` instead. It is ordered before the climb's next level.
- Test: `tests/test_ai/test_tool_objective.py`

**Interfaces:**
- Produces: `tool_target(skill, state, game_data, ctx) -> str | None`.

- [ ] **Step 1: Failing tests:**
  - `test_a_climb_first_fetches_its_tool`: a fishing climb with `fishing_net` achievable and not owned gives root `ObtainItem("fishing_net")`.
  - `test_an_owned_tool_is_never_reacquired`: the same state with the net banked gives the climb root.
  - `test_a_craft_skill_tool_qualifies_by_its_effect`: a synthetic item with `skill_effects={"gearcrafting": -10}` in a test-built `GameData` is the target for a gearcrafting climb.
- [ ] **Step 2–4: FAIL, implement, PASS.** Add mutants (the owned check removed; the tool step skipped), then commit `feat(objective): a climb fetches its best tool first`.

### Task 9: Gate, live check, merge

- [ ] **Step 1:** `ARTIFACTSMMO_TOKEN="$(cat /home/blentz/git/artifactsmmo/TOKEN)" bash formal/gate.sh > $S/gate-B.log 2>&1; echo "gate rc=$?" > $S/gate-B.rc` (in the background). Read the rc in its own call. It must be green.
- [ ] **Step 2:** `mutate.py --only "gear_objective,obtain_model,decisions,fleet_climb,role_selection,tool_objective,expected_damage"`, with 0 survivors.
- [ ] **Step 3:** Run live `plan <name>` for all 5 characters, each with the token read in place. Grep every log for `eyJ`. Record `chosen_root`, the `gear_objective:` line and the role. None may be `Wait`. Exactly one character per demanded craft skill holds its role.
- [ ] **Step 4:** The controller runs the final whole-branch review, then merges (fetch, `merge-base --is-ancestor origin/main HEAD`, `git push origin HEAD:main`) and asks the user to restart. The witness is spec §5.5 and §5.7 over 24 h: crafting-skill XP is non-zero on every skill on some `L*` route, and worn gear level rises.

# Global Gear Objective — Plan A (objective core + wiring) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each character's root becomes the next missing piece of `L*` — the best loadout of achievable level-legal gear, chosen for the monster `m*` it farms best — and it fights for XP only once `L*` is held.

**Architecture:** A new pure core (`ai/gear_objective_core.py`, Lean-proved, differential-bound) owns the fixed point and the ordering. A thin adapter (`ai/gear_objective.py`) feeds it from `ObtainModel` (feasibility, with drop winnability judged against a projected fighter), `pick_loadout`/`best_loadout` (per-monster loadout and XP rate) and `route_price` (acquisition price). The player computes one `GearObjective` per cycle into `SelectionContext`; `decisions/root.resolve_root` gets a new entry decision that replaces the fight-gated gear chain.

**Tech Stack:** Python 3.13 (`uv run`), pytest + hypothesis, Lean 4 (`formal/`), the oracle-differential harness (`formal/diff/oracle_client.run_oracle`), `formal/diff/mutate.py`.

**Spec:** `docs/superpowers/specs/2026-10-18-global-gear-objective-design.md` (APPROVED 2026-10-18). Read §2 and §5 before any task.

**Plans B and C (separate documents, written after A merges):** B = spec §2.5 fleet amortization (fleet `L*` demand, amortized sibling route price, role demand from fleet `L*`) plus the tool targets `T*` of spec §2.2/§2.6 (gathering tools and Season 9 crafting tools for the skill a character climbs). C = spec §3/§4 deletion of the ladder and every consumer A leaves dead, tests rewritten to outcomes, grep gate (§5.4). Plan A leaves the ladder modules in place but unreferenced by `resolve_root`'s entry.

## Global Constraints

- `uv run` for every Python command, with `unset VIRTUAL_ENV`. Never `timeout uv`.
- No inline imports. Never catch `Exception`. No `if TYPE_CHECKING`. One behavioral class per file. Absolute imports only.
- API data only; a missing datum raises, never defaults.
- 0 errors, 0 warnings, 0 skipped, 100% coverage (`tests/`).
- No alphabetical / `repr` tiebreak in any decision ordering (memory: no-alphabetical-tiebreak).
- Tier, rung, band, ladder and milestone are NOT computed by any new code (spec §1.1, §2.7).
- Acquisition price orders `L*` pieces and never downgrades `L*` (spec §6.1).
- No fight is chosen for XP while any `L*` piece is missing; a level-up is not an acquisition step (spec §6.2).
- Commit with `ARTIFACTSMMO_TOKEN=dummy`, in the background with an rc file (hook ≈ 9 min). Stage files explicitly; never chain `git add` with `;`. Never `--no-verify`, `git stash`, or `git checkout <path>`. Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Every new decision branch gets a mutant in `formal/diff/mutate.py` in the same commit; refresh stale anchors in the same commit (`--check-anchors`).

## Review Focus

1. **An event monster that is not live** supplies no drop route, and a static monster on a non-overworld layer still does (spec §2.1 "event-only routes count only while the event is live"). Test owned by Task 2.
2. **A fixed-supply item with no free copy** (`novice_guide` worn by a sibling) is never an `L*` piece (spec §2.1 last bullet, `is_suppliable`). Test owned by Task 3.
3. **A level-up mid-acquisition** that makes a strictly better item level-legal replaces that slot's `L*` item on the next cycle, and the character does not fight for XP in between. Test owned by Task 5.
4. **Rings**: two ring slots may hold the same code only with two achievable copies; `L*` never names one code for both ring slots unless the fixed point counts two (pick_loadout's occupancy cap). Test owned by Task 3.
5. **Cycle time**: computing `GearObjective` for Robby's live shape stays under the planning window (assert < 2.0 s on the bundle fixture, measured, not guessed — report the measured value in the task report). Test owned by Task 4.

---

### Task 1: Pure core — fixed point and piece ordering (Lean + differential)

**Files:**
- Create: `src/artifactsmmo_cli/ai/gear_objective_core.py`
- Create: `formal/Formal/GearObjective.lean` (+ register in `formal/Formal.lean`, `formal/Formal/Manifest.lean`, oracle entry in `formal/Oracle.lean`)
- Create: `formal/diff/test_gear_objective_diff.py` (pattern: `formal/diff/test_combat_picker_diff.py`)
- Test: `tests/test_ai/test_gear_objective_core.py`

**Interfaces:**
- Produces:
  - `achievable_layers(base: frozenset[str], unlock: Callable[[frozenset[str]], frozenset[str]]) -> tuple[frozenset[str], ...]` — layer 0 = `base`; layer k+1 = items in `unlock(⋃ layers ≤ k)` not already present; stops at the first empty layer. `unlock` must be monotone; the core asserts the union only grows.
  - `layer_of(layers: tuple[frozenset[str], ...]) -> dict[str, int]`.
  - `PieceKey = tuple[int, Fraction, Fraction, int]` and `piece_order_key(layer: int, gain: Fraction, price: Fraction, slot_rank: int) -> PieceKey` returning `(layer, -(gain / price), -gain, slot_rank)`; `price > 0` is asserted.
  - `objective_held(missing: frozenset[str]) -> bool` (True iff empty).

- [ ] **Step 1: Write failing tests** in `tests/test_ai/test_gear_objective_core.py`:
  - `test_layers_stop_at_the_first_empty_layer`: `base={"a"}`, `unlock` maps `{"a"}→{"a","b"}`, `{"a","b"}→{"a","b","c"}`, else identity ⇒ `(frozenset({"a"}), frozenset({"b"}), frozenset({"c"}))`.
  - `test_a_shrinking_unlock_is_refused`: `unlock` returning a strict subset raises `AssertionError`.
  - `test_lower_layer_orders_first_whatever_the_gain`: key(0, gain 1, price 100) < key(1, gain 1000, price 1).
  - `test_within_a_layer_gain_per_price_orders`: key(0, 10, 2) < key(0, 10, 5).
  - `test_equal_ratio_prefers_the_larger_gain_then_slot_rank`: key(0, 4, 2) < key(0, 2, 1); key(0, 2, 1, slot_rank 0) < key(0, 2, 1, slot_rank 3).
  - `test_a_free_price_is_refused`: price 0 raises `AssertionError`.
  - `test_held_iff_nothing_missing`.
- [ ] **Step 2: Run** `uv run pytest tests/test_ai/test_gear_objective_core.py -q` — expect ImportError/FAIL.
- [ ] **Step 3: Implement** the four functions in `gear_objective_core.py` (plain data only, no GameData/WorldState — the `*_core.py` convention).
- [ ] **Step 4: Lean model** `Formal/GearObjective.lean`: `layers` over `Finset`, theorems (a) `layers_terminate` (length ≤ catalogue card + 1) and `layers_monotone`; (b) `pieceKey` lexicographic: `layer_first` (lower layer ⇒ smaller key regardless of gain/price); (c) `held_iff_empty`. Zero vacuous hypotheses (memory: zero-vacuousness). Expose `pieceOrder` and `layers` through the oracle.
- [ ] **Step 5: Differential** `formal/diff/test_gear_objective_diff.py`: hypothesis over catalogues ≤ 6 items with a random monotone `unlock` table and random (layer, gain, price>0, slot_rank) pieces; Python order == Lean order, Python layers == Lean layers.
- [ ] **Step 6: Mutants** in `mutate.py` (new `GEAR_OBJECTIVE_CORE_MUTATIONS` → `tests/test_ai/test_gear_objective_core.py`): drop the layer term from the key; use `-gain` before the ratio; `price >= 0` instead of `> 0`; stop after layer 1. Run `uv run python formal/diff/mutate.py --check-anchors` then `--only test_gear_objective_core`.
- [ ] **Step 7: Run** the unit tests, the differential (`uv run pytest formal/diff/test_gear_objective_diff.py -q`), `lake build` in `formal/` — all green.
- [ ] **Step 8: Commit** `feat(gear): pure core for the gear objective's fixed point and piece order`.

### Task 2: Drop winnability judged against a projected fighter

**Files:**
- Modify: `src/artifactsmmo_cli/ai/obtain_model/obtain_model.py` (`ObtainModel.__init__`), `src/artifactsmmo_cli/ai/obtain_model/drop_routes.py` (`drop_routes`, `_fight_gates`)
- Create: `src/artifactsmmo_cli/ai/obtain_model/policy.py` constant `GEAR_OBJECTIVE_POLICY`
- Test: `tests/test_ai/test_obtain_model_fighter.py`

**Interfaces:**
- Produces: `ObtainModel(state, game_data, ctx, now, fighter: WorldState | None = None)` — when given, every DROP route's WINNABLE gate is asked of `fighter` at full HP instead of `state`; stock (bag, bank, pocket) is still read from `state` only. `drop_routes(item, state, game_data, fighter: WorldState | None = None)`.
- Produces: `GEAR_OBJECTIVE_POLICY = Policy(all_gather_routes=True, gather_skill_gate=False, craft_skill_gate=False, event_vendors=True, spawn_known=<see Step 3>, allow_grey=True, vendor_routes=True, ge_routes=False, task_rewards=True, fight_gold=True, drop_routes=True)`.

- [ ] **Step 1: Failing tests:**
  - `test_a_fighter_that_wins_opens_the_drop_the_wearer_cannot`: a state that loses to monster M, a fighter (same state, inventory + a weapon that wins) ⇒ `feasible(drop_of_M, 1, GEAR_OBJECTIVE_POLICY)` False without `fighter`, True with it.
  - `test_the_fighters_inventory_is_never_stock`: fighter holds item X, state does not ⇒ an X-only recipe input is NOT on hand (feasible only through a route).
  - `test_an_event_monster_that_is_not_live_drops_nothing` (Review Focus 1): monster with event candidate maps only, no active event ⇒ its drop infeasible; same monster with `active_event_maps` set ⇒ feasible.
  - `test_a_static_monster_on_another_layer_still_drops` (Review Focus 1).
  - `test_skill_gates_are_a_cost_not_a_veto`: recipe at gearcrafting 40, character at 23 ⇒ feasible under `GEAR_OBJECTIVE_POLICY`.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement.** Thread `fighter` to `_Rested(fighter or state)`. Choose `spawn_known` so both Review-Focus-1 tests pass (read `GameData.monster_spawn_known` first; if `True` admits a non-live event monster, keep `spawn_known=False` and confirm `all_monster_locations` includes layered static tiles — if it does not, stop and report: the spec's "in principle" rule then needs a `GameData` predicate, not a policy flag).
- [ ] **Step 4: Run** the new tests and `tests/test_ai/ -k obtain_model` — green (existing callers pass no `fighter`, behaviour unchanged).
- [ ] **Step 5: Mutants:** `fighter` ignored (`_Rested(state)`); fighter inventory merged into stock; `allow_grey=False`. Commit `feat(obtain): judge drop fights against a projected fighter`.

### Task 3: The gear objective adapter

**Files:**
- Create: `src/artifactsmmo_cli/ai/gear_objective.py` (function module) and `src/artifactsmmo_cli/ai/gear_objective_result.py` (the `GearObjective` / `GearPiece` frozen dataclasses)
- Test: `tests/test_ai/test_gear_objective.py`

**Interfaces:**
- Consumes: Task 1 core; Task 2 `ObtainModel(..., fighter=)` + `GEAR_OBJECTIVE_POLICY`; `pick_loadout_cached`/`Combat`; `best_loadout`; `rank_rate` (upkeep `None`: the MODELLED rate — measured upkeep belongs to the worn gear); `GameData.xp_per_kill(code, level, wisdom)`; `project_loadout_stats(...).wisdom`; `route_price`; `is_suppliable`; `loadout_picker._ordered_slots`.
- Produces:
  - `@dataclass(frozen=True) GearPiece: slot: str; code: str; layer: int; gain: Fraction; price: Fraction`
  - `@dataclass(frozen=True) GearObjective: monster: str; loadout: dict[str, str]; rate: Fraction; missing: tuple[GearPiece, ...]` (ordered by `piece_order_key`) with property `held -> bool`.
  - `achievable(state, game_data, ctx) -> tuple[frozenset[str], ...]` — layers; the candidate universe is equippables with `level <= state.level` that pass `is_suppliable`, plus everything held/banked; `unlock(S)` = items feasible under `GEAR_OBJECTIVE_POLICY` with `fighter = state` owning one copy of each item in `S` (two for rings).
  - `fighter_owning(state, items: frozenset[str], game_data) -> WorldState` (inventory + copies; rings ×2).
  - `gear_objective(state, game_data, ctx, history, price_of: Callable[[str], Fraction]) -> GearObjective | None` — None only when no monster has `R > 0` even on the full achievable fighter (then `missing` is moot; Task 5 handles it).
  - Candidate monsters: spawning now (`game_data.monster_locations`), level ≤ `state.level + FIGHT_LEVEL_GAP_CEILING`, `xp_per_kill > 0`; type not in `{"boss","raid_boss"}` solo (party bosses stay with the existing party path). `m*` = argmax `R`, ties to the higher monster level, then lower `route_price` of its missing pieces — never by code.
  - `loadout` = `fight_loadout(fighter_full, game_data, m*)`; `missing` = its slots whose code is not worn; `gain` = `R(owned ∪ {piece}) − R(owned)` on `m*`, floored at 1/10⁶ only for ordering a zero-gain piece last within its layer (state it in a comment); `price` = `route_price(ObtainItem(code, 1, slot=slot), ...)`.

- [ ] **Step 1: Failing tests** (bundle fixture `bundle_game_data`, `make_state`):
  - `test_robbys_shape_names_level_40_gear_not_level_20`: level 41, worn `slime_shield`/`hard_leather_helmet`/`hard_leather_pants`/`bandit_armor`, gearcrafting 23 ⇒ every `missing` piece has item level > 20, and at least one has `crafting_level > state.skills["gearcrafting"]`.
  - `test_an_unbeatable_event_monster_changes_nothing` (spec §5.3): add a non-live event monster the state loses to ⇒ identical `GearObjective`.
  - `test_the_target_ignores_what_is_worn`: two states differing only in worn gear ⇒ same `loadout` and `monster`.
  - `test_a_fixed_supply_item_with_no_free_copy_is_never_a_piece` (Review Focus 2).
  - `test_one_ring_code_fills_both_slots_only_with_two_copies` (Review Focus 4).
  - `test_pieces_come_in_core_order`: `missing` sorted by `piece_order_key`.
  - `test_held_when_every_slot_wears_its_target`.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** per Interfaces. Memoize `achievable` per call only (no cross-cycle cache in Plan A; Task 4 measures).
- [ ] **Step 4: Run** tests — green.
- [ ] **Step 5: Mutants:** worn gear used as the fighter (`fighter = state`); `level <= state.level` dropped; `is_suppliable` filter dropped; `m*` argmin; measured upkeep passed to `rank_rate`. Commit `feat(gear): the global gear objective L*, m*`.

### Task 4: One objective per cycle in `SelectionContext`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/selection_context.py` (field), `src/artifactsmmo_cli/ai/player.py` (`_selection_context` and `_winnable_farm_target`)
- Test: `tests/test_ai/test_player_gear_objective.py`

**Interfaces:**
- Produces: `SelectionContext.gear_objective: GearObjective | None = None`.
- `ctx.combat_monster` = `gear_objective.monster` when `gear_objective.held`, else None — EXCEPT a held monsters task's monster, which keeps today's precedence (`_task_aligned_monster`). `_path_aligned_monster` / `_pick_winnable_monster` are no longer consulted (left for Plan C to delete).

- [ ] **Step 1: Failing tests:** `test_the_context_carries_the_cycles_objective`; `test_no_xp_monster_while_a_piece_is_missing`; `test_the_objectives_monster_once_held`; `test_a_held_monsters_task_keeps_its_monster`; `test_objective_cost_on_robbys_shape` (Review Focus 5: `time.perf_counter` around `gear_objective`, assert < 2.0 s, print the measurement).
- [ ] **Step 2–4:** run (FAIL), implement, run (PASS).
- [ ] **Step 5: Mutants:** combat_monster set while not held; task precedence dropped. Commit `feat(player): carry the gear objective in the selection context`.

### Task 5: The root walk's new entry

**Files:**
- Create: `src/artifactsmmo_cli/ai/decisions/which_piece_is_next.py` (`class WhichPieceIsNext(Decision[MetaGoal])`)
- Modify: `src/artifactsmmo_cli/ai/decisions/root.py` (`resolve_root`)
- Test: `tests/test_ai/test_decisions_which_piece.py`; rewrite failures in `tests/test_ai/test_decisions_root.py` and `tests/test_ai/scenarios/*` to outcome assertions (spec §4)

**Interfaces:**
- Consumes: `ctx.gear_objective`; `CharacterObjective.classify_target`; `IsThisTargetBlocked`; `RootWalk.serves`.
- Produces: `resolve_root` entry is `WhichPieceIsNext`:
  - not held: the first served piece in `missing` order → `IsThisTargetBlocked(slot, classify_target(code))` (skill gate → `ReachSkillLevel(skill, current+1)`, material → its `ObtainItem`); unserved pieces go to `walk.declined` with their reason; the rest become alternatives in order.
  - held: `ReachCharLevel(level=state.level + 1)` (no milestone).
  - `gear_objective is None`: the wall — `None`, as today.
- `resolve_root`'s `ordered` list: missing pieces (converted), then the trunk ONLY when held, then task, fleet and orphan-skill roots unchanged.

- [ ] **Step 1: Failing tests:**
  - `test_robby_climbs_or_builds_never_waits` (spec §5.1): the live shape ⇒ root is `ObtainItem` of an `L*` piece or `ReachSkillLevel` in front of one; never None; no `ReachCharLevel` in `alternatives`.
  - `test_held_objective_grinds_the_next_level`: root `ReachCharLevel(level=state.level + 1)`.
  - `test_a_level_up_retargets_without_an_xp_fight` (Review Focus 3): state at level L holding `L*`, then level L+1 where a better item is level-legal ⇒ root is that piece; `ReachCharLevel` absent.
  - `test_a_declined_piece_yields_to_the_next` (unserved first piece ⇒ second piece is the root, first is in `declined`).
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement**; then run the full `tests/test_ai/` suite and rewrite each newly failing test to assert the outcome the spec requires (root, step, or emitted action), never rung/band membership. List every rewritten test in the commit body.
- [ ] **Step 4: Run** full suite — green.
- [ ] **Step 5: Mutants:** trunk offered while not held; held branch returns the first piece; declined piece kept as root. Commit `feat(root): the next missing gear piece is the root`.

### Task 6: Gate, plan pane, live check

**Files:**
- Modify: `src/artifactsmmo_cli/commands/plan.py` `_print_report` (print `gear_objective: monster=…, held=…, missing=[slot:code(layer, gain/price)…]`), `tests/test_tui/test_plan_format.py` if it pins the report.

- [ ] **Step 1:** Add the plan-pane line + its test.
- [ ] **Step 2:** `ARTIFACTSMMO_TOKEN="$(cat /home/blentz/git/artifactsmmo/TOKEN)" bash formal/gate.sh > $S/gate-gear.log 2>&1; echo "gate rc=$?" > $S/gate-gear.rc` (background); read the rc in its own call. Green required.
- [ ] **Step 3:** `uv run python formal/diff/mutate.py --only "gear_objective,obtain_model,decisions,player"` — 0 survivors.
- [ ] **Step 4:** Live `plan Robby --learn` from the worktree: `chosen_root` is an `ObtainItem` of an `L*` piece or a `ReachSkillLevel` (gearcrafting/jewelrycrafting/weaponcrafting); paste the output into the task report. Same for the other four characters — none `Wait`.
- [ ] **Step 5:** Merge per project rule (fetch, `merge-base --is-ancestor origin/main HEAD`, `git push origin HEAD:main`), then ask the user to restart the fleet. Witness = spec §5.6/§5.7.

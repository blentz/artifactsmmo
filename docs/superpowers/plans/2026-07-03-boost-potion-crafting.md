# Boost/Resist Potion Crafting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Formal tasks (Lean/differential/mutation) may additionally invoke the `lean4` skill.

**Goal:** Extend the heal-only potion craft economy to also craft the craftable-now boost/resist utility potion that most improves the bot's combat margin against its current in-band target monster — closing the gap where `predict_win` already values owned boosts but nothing crafts them.

**Architecture:** Add a read-only continuous combat-margin signal that shares `predict_win`'s exact arithmetic (verdict byte-identical); use it to rank craftable-now boost potions by margin gain vs the target monster; fire the existing `CRAFT_POTIONS` guard for a beneficial understocked boost; extend `CraftPotionsGoal` to craft heal-first-then-boost. New pure cores gated by differential + mutation; `predict_win`'s boolean and all liveness proofs unchanged.

**Tech Stack:** Python 3.13, `uv`, pytest; Lean 4 (`formal/Formal/PredictWin.lean`); differential harness (`formal/diff/`) + mutation runner (`formal/diff/mutate.py`); `./formal/gate.sh`.

## Global Constraints

- Run every Python command with `uv run`. Lean via `lake build` inside `formal/`.
- Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage; `mypy src` clean; `./formal/gate.sh` green.
- One behavioral class per file. Imports at top only. No inline imports. No `if TYPE_CHECKING`. Never catch `Exception`. No triple-dot imports.
- Use only API data (`monster_attack`/`monster_resistance`/item stats/recipes) or fail; no defaulting over missing game data.
- `predict_win`'s boolean output MUST stay byte-identical — the existing `PredictWin` differential + mutation gate stays green with no fixture regen. Do not change `predict_win`'s HP model or any liveness proof.
- Boost crafting is **craftable-now only** — never emit a `ReachSkillLevel` to unlock a boost (the Phase-1 anti-grind discipline).
- Reuse the `CRAFT_POTIONS` guard slot — do NOT add a new `GuardKind` (breaks `allInLadderOrder`/`decide_key`).
- Mutation discipline (bag-slot lesson): a unit-killed mutation gets its OWN group bound to its unit test, never folded into a traversal-diff group. Refresh `mutate.py` anchor strings after any edit that moves the mutated text.
- `make_state(**overrides)` REPLACES the `skills` dict — override skills as `{**make_state().skills, "alchemy": N}`.

---

### Task 1: Extract shared `_kill_step_net` / `_die_step` / `_effective_player_hp` helpers from `predict_win`

Refactor `predict_win`'s inline arithmetic into pure module-level helpers, reused later by `combat_margin`. `predict_win`'s output stays byte-identical.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/combat.py` (`predict_win`, ~88-207)
- Modify: `formal/diff/mutate.py` (`PREDICT_WIN_MUTATIONS`, ~534; `PREDICT_WIN_LIFESTEAL_MUTATIONS`, ~552 — update anchor strings to their new location if the mutated text moves into a helper)
- Test: `tests/test_ai/test_combat.py` (existing predict_win tests must stay green unchanged)

**Interfaces:**
- Produces (module-level, pure — all `int` in/out):
  - `_kill_step_net(raw_player, p_crit, m_crit, m_lifesteal, m_atk_sum, monster_hp, monster_healing, player_max_hp, monster_void_drain, monster_bubble, monster_sun_shield) -> int` — the full net kill step (mirrors Lean `killStepNet`, PredictWin.lean:122).
  - `_die_step(raw_monster, m_crit, p_crit, p_lifesteal, p_atk_sum, monster_poison, monster_burn, player_max_hp, monster_void_drain, monster_berserk, monster_frenzy, player_antipoison, raw_player, monster_greed, monster_enchanted_mirror) -> int` — mirrors Lean `dieStep` (PredictWin.lean:134).
  - `_effective_player_hp(hp, max_hp) -> int` — `min(hp, max_hp) if hp > 0 else 0`.
- Consumes: existing `_element_damage`, `ELEMENTS`, `MAX_TURNS`, `GREED_MAX_STACKS`, the `game_data.monster_*` getters (unchanged).

- [ ] **Step 1: Capture the current predict_win boolean baseline (characterization test)**

Add to `tests/test_ai/test_combat.py` a test that pins `predict_win`'s boolean across a spread of monsters/states, so the refactor is provably behavior-preserving. Use the existing test module's GameData/monster fixture pattern (see `test_predict_win_*` there and `formal/diff/test_predict_win_diff.py` for the monkeypatched-getter shape).

```python
def test_predict_win_boolean_unchanged_by_helper_extraction():
    # Characterization: exact booleans for a spread of monster profiles.
    # These values are the pre-refactor output; the refactor must not change them.
    gd = _combat_gd()  # existing helper in this module (or build per test_combat.py pattern)
    cases = _predict_win_case_matrix()  # (state, monster_code) -> expected bool
    for state, monster, expected in cases:
        assert predict_win(state, gd, monster) is expected
```

If `test_combat.py` has no reusable matrix helper, build the cases inline from its existing fixtures (winnable, unkillable via `kill_step<=0`, poison-only-win via `die_step<=0`, damaged-hp loss). Capture the ACTUAL current booleans first by running, then hard-code them.

- [ ] **Step 2: Run it to confirm GREEN pre-refactor**

Run: `uv run pytest tests/test_ai/test_combat.py::test_predict_win_boolean_unchanged_by_helper_extraction -v`
Expected: PASS (it encodes current behavior).

- [ ] **Step 3: Extract the helpers, rewrite predict_win to call them**

In `combat.py`, lift the three arithmetic blocks into module-level functions and replace the inline expressions in `predict_win` with calls. The expressions moved are, verbatim from the current body:
- kill step (currently `kill_step = (50 * raw_player * (200 + p.critical_strike) - ... // 2)`) → body of `_kill_step_net`.
- die step (currently `die_step = (50 * raw_monster * (200 + m_crit) - ... // 2)`) → body of `_die_step`.
- `effective_hp = min(state.hp, p.max_hp) if state.hp > 0 else 0` → `_effective_player_hp(state.hp, p.max_hp)`.

`predict_win` keeps its early-return control flow exactly (`raw_player<=0`, `kill_step<=0`, `rounds_to_kill>MAX_TURNS`, reconstitution, `die_step<=0`, `effective_hp<=0`, final tiebreak). Only the arithmetic sub-expressions move.

- [ ] **Step 4: Update mutation anchors, verify predict_win diff + mutation green**

The `PREDICT_WIN_MUTATIONS` / `PREDICT_WIN_LIFESTEAL_MUTATIONS` entries match literal source strings (e.g. `"50 * raw_player * (200 + p.critical_strike)"`, the crit-term drop, the lifesteal-term drop). If a mutated string now lives inside a helper, update the anchor's `old`/`new` text so it still matches. Then:

Run: `uv run pytest tests/test_ai/test_combat.py -v` (all predict_win tests + the characterization test)
Run (Lean unchanged, differential should still match): `uv run pytest formal/diff/test_predict_win_diff.py -v`
Run mutation for just this group: `uv run python formal/diff/mutate.py` is the full runner; for a focused check confirm `PREDICT_WIN_MUTATIONS` all still `killed` (no survivors) in its output section.
Expected: all PASS; every predict_win mutation killed; characterization test still GREEN (byte-identical booleans).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/combat.py formal/diff/mutate.py tests/test_ai/test_combat.py
git commit -m "refactor(combat): extract kill_step/die_step helpers, predict_win output unchanged"
```

---

### Task 2: `combat_margin` (Python + Lean mirror + differential + mutation)

A read-only signed margin whose sign equals the `predict_win` verdict and whose magnitude (in the numeric regime) is the round cushion `rounds_to_die - rounds_to_kill`.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/combat.py` (add `combat_margin`)
- Modify: `formal/Formal/PredictWin.lean` (add `combatMargin` reusing `killStepNet`/`dieStep`/`ceilDiv`/`maxTurns`)
- Create: `formal/diff/test_combat_margin_diff.py` (mirror `test_predict_win_diff.py`)
- Modify: `formal/diff/mutate.py` (add `COMBAT_MARGIN_MUTATIONS` + a `run_group` bound to `formal/diff/test_combat_margin_diff.py`)
- Test: `tests/test_ai/test_combat.py`

**Interfaces:**
- Produces: `combat_margin(state, game_data, monster_code) -> int`. Invariant: `predict_win(...) == (combat_margin(...) > 0)` for all inputs. Encoding:
  - `raw_player <= 0` (can't scratch) → `LOSE_MARGIN` (a fixed sentinel `<= 0`, e.g. `-MAX_TURNS - 1`).
  - `kill_step <= 0` (unkillable) → `LOSE_MARGIN`.
  - `rounds_to_kill > MAX_TURNS` → `LOSE_MARGIN`.
  - reconstitution kills before we do → `LOSE_MARGIN`.
  - `die_step <= 0` (out-sustain) → `WIN_MARGIN` (a fixed sentinel `> 0`, e.g. `MAX_TURNS + 1`).
  - `effective_hp <= 0` → `LOSE_MARGIN`.
  - numeric regime → `rounds_to_die - rounds_to_kill + (1 if player_first else 0)` (so win ⇔ value `> 0`, matching `roundsToKill <= roundsToDie` when player_first and `<` otherwise).
- Consumes: Task 1 helpers, `pick_loadout`, `project_loadout_stats`, monster getters.

- [ ] **Step 1: Write the failing Python test (behavior + tie to predict_win)**

```python
def test_combat_margin_sign_matches_predict_win():
    gd = _combat_gd()
    for state, monster, _ in _predict_win_case_matrix():
        assert predict_win(state, gd, monster) == (combat_margin(state, gd, monster) > 0)

def test_combat_margin_magnitude_orders_by_cushion():
    # A strictly stronger player loadout (more attack) yields a >= margin vs the
    # same monster in the numeric regime (monotone cushion).
    gd = _combat_gd()
    weak, strong, monster = _margin_monotone_case()  # strong has more attack
    assert combat_margin(strong, gd, monster) >= combat_margin(weak, gd, monster)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_combat.py -k combat_margin -v`
Expected: FAIL — `combat_margin` not defined.

- [ ] **Step 3: Implement `combat_margin` (Python)**

Add to `combat.py`, reusing Task 1 helpers and the same monster-getter reads as `predict_win`, with the sentinel encoding above. Define module constants `WIN_MARGIN = MAX_TURNS + 1`, `LOSE_MARGIN = -(MAX_TURNS + 1)`. Mirror `predict_win`'s control flow exactly, returning the encoded margin instead of a bool at each exit.

- [ ] **Step 4: Add the Lean `combatMargin` and differential**

Invoke the `lean4` skill for this step. In `formal/Formal/PredictWin.lean`, add (reusing existing defs — no new arithmetic):

```lean
def winMargin : Int := maxTurns + 1
def loseMargin : Int := -(maxTurns + 1)

def combatMargin (rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp
    /- …same parameter list as predictWin… -/ ) : Int :=
  -- mirror predictWin's branches; return loseMargin / winMargin at the boolean
  -- exits and `roundsToDie - roundsToKill + (if playerFirst then 1 else 0)` in
  -- the numeric regime, using killStepNet / dieStep / ceilDiv / maxTurns.
  …
```

Create `formal/diff/test_combat_margin_diff.py` by copying `test_predict_win_diff.py`'s structure (monkeypatch the monster getters to controlled values, drive both the Python `combat_margin` and the Lean `combatMargin` over a fixture grid, assert equal ints). Add a `lake build` step and confirm the Lean file compiles with no `sorry`/axioms.

- [ ] **Step 5: Add the mutation group**

In `mutate.py`, add `COMBAT_MARGIN_MUTATIONS` (mutate the margin's distinguishing terms: the `+ (1 if player_first ...)` adjustment → drop it; the `rounds_to_die - rounds_to_kill` → swap operands; a sentinel sign flip) and a `run_group(COMBAT_SRC, COMBAT_MARGIN_MUTATIONS, "formal/diff/test_combat_margin_diff.py", survivors)`. Each mutation must be killed by the differential.

- [ ] **Step 6: Verify**

Run: `uv run pytest tests/test_ai/test_combat.py -k combat_margin formal/diff/test_combat_margin_diff.py -v`
Run: `cd formal && lake build 2>&1 | tail -5` (expect success, no `sorry`)
Expected: all PASS; Lean builds.

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/combat.py formal/Formal/PredictWin.lean formal/diff/test_combat_margin_diff.py formal/diff/mutate.py tests/test_ai/test_combat.py
git commit -m "feat(combat): read-only combat_margin sharing predict_win arithmetic (Lean-diffed)"
```

---

### Task 3: `best_boost_potion` selection core

Rank craftable-now boost potions by `combat_margin` gain vs the target monster.

**Files:**
- Create: `src/artifactsmmo_cli/ai/boost_selection.py`
- Modify: `formal/diff/mutate.py` (add `BOOST_SELECTION_MUTATIONS` bound to the unit test — NO Lean mirror: it depends on `project_loadout_stats`, which is Python-only)
- Test: `tests/test_ai/test_boost_selection.py` (create)

**Interfaces:**
- Consumes: `combat_margin` (Task 2), `project_loadout_stats` (equipment/projection.py:31), `game_data.item_stats`, `game_data.crafting_recipes`, `state.skills`.
- Produces: `best_boost_potion(state, game_data, monster_code) -> str | None` — among utility items with a boost effect (`dmg_elements` or `resistance` non-empty, or `hp_bonus > 0`) that are craftable-now (`stats.crafting_skill is not None and state.skills[stats.crafting_skill] >= stats.crafting_level`), the code maximizing `combat_margin(project_equip(state, code), gd, monster) - combat_margin(state, gd, monster)`, restricted to strictly positive gain; smallest-code tie-break; `None` when none qualifies.
- Helper `project_equip(state, code, game_data) -> WorldState`: return a state whose loadout puts `code` in an empty/оверridable utility slot, via `project_loadout_stats` folded back into the projected stats the margin reads. (Mirror how `predict_win` builds `p` from a loadout: build a loadout dict `{**current, "utility1_slot": code}` and let `combat_margin`'s internal `pick_loadout`/projection see the owned item — simplest: temporarily model `code` as owned so `pick_loadout` equips it, then call `combat_margin`. If cleaner, compute the projected stats directly with `project_loadout_stats` and add a `combat_margin_from_projected` overload — but prefer reusing `combat_margin` end-to-end to avoid a second arithmetic path.)

- [ ] **Step 1: Write failing tests**

Create `tests/test_ai/test_boost_selection.py` with the module fixture pattern (GameData + ItemStats + make_state). Cases:

```python
def test_picks_boost_res_for_monster_attack_element():
    # monster attacks fire; a craftable-now boost_res_fire potion raises margin.
    ...
    assert best_boost_potion(state, gd, "fire_monster") == "res_fire_potion"

def test_picks_boost_dmg_for_least_resisted_element():
    # monster resists earth but not fire; boost_dmg_fire raises kill rate most.
    assert best_boost_potion(state, gd, "resisty_monster") == "dmg_fire_potion"

def test_skips_boost_not_craftable_now():
    # the only helpful boost needs alchemy 30, char alchemy 10 -> None (anti-grind).
    assert best_boost_potion(state, gd, monster) is None

def test_none_when_no_boost_helps():
    # no candidate yields positive margin gain -> None.
    assert best_boost_potion(state, gd, monster) is None

def test_deterministic_tiebreak_smallest_code():
    # two boosts with equal gain -> smallest code.
    assert best_boost_potion(state, gd, monster) == "aaa_boost"
```

Build fixtures so each assertion is non-vacuous (the losing candidate exists and is craftable, only the gain/craftability differs).

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_boost_selection.py -v`
Expected: FAIL — module/function missing.

- [ ] **Step 3: Implement `best_boost_potion` + `project_equip`**

Write `boost_selection.py` (imports at top: `combat_margin` from combat, `project_loadout_stats` from equipment.projection, `GameData`, `WorldState`). One module, cohesive selection logic. Craftable-now gate identical to `target_potion_pure` (potion_supply.py:47). Positive-gain filter; smallest-code tie-break via `sorted(...)`.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_boost_selection.py -v`
Expected: PASS.

- [ ] **Step 5: Add mutation group bound to the unit test**

In `mutate.py`: `BOOST_SELECTION_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "boost_selection.py"`; `BOOST_SELECTION_MUTATIONS` mutating the distinguishing logic (positive-gain `> 0` → `>= 0`; the craftable-now `>=` → `>`; argmax → argmin; the tie-break). Bind: `run_group(BOOST_SELECTION_SRC, BOOST_SELECTION_MUTATIONS, "tests/test_ai/test_boost_selection.py", survivors)` — its OWN group bound to the unit test (bag-slot lesson), not a traversal-diff group.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/boost_selection.py tests/test_ai/test_boost_selection.py formal/diff/mutate.py
git commit -m "feat(boost): best_boost_potion selection core (margin-ranked, craftable-now)"
```

---

### Task 4: Guard branch + goal heal-then-boost wiring

**Files:**
- Modify: `src/artifactsmmo_cli/ai/potion_supply.py` (`craft_potions_fires`, ~71-103)
- Modify: `src/artifactsmmo_cli/ai/goals/craft_potions.py` (`_target_potion` / target resolution, ~51-56 and the `_active_craft` path)
- Test: `tests/test_ai/test_craft_potions.py`, `tests/test_ai/test_potion_supply_integration.py`

**Interfaces:**
- Consumes: `best_boost_potion` (Task 3), `combat_target_monsters` (combat_targets.py:27), `equipped_potion_qty`, `potion_baseline_pure`, `_recipe_producible`.
- Produces: `craft_potions_fires` also returns True for a beneficial, understocked, producible craftable-now boost; `CraftPotionsGoal` crafts the heal while under heal-baseline, else the boost while under boost-baseline.

- [ ] **Step 1: Write failing tests**

In `test_potion_supply_integration.py` / `test_craft_potions.py` (reuse `test_craft_potions_boost.py` fixture patterns):

```python
def test_guard_fires_for_beneficial_boost_when_heal_stocked():
    # heals at baseline; a craftable-now boost helps the in-band monster and is
    # under-stocked + producible -> guard fires.
    assert craft_potions_fires(state, gd) is True

def test_guard_no_boost_when_none_beneficial():
    # heals stocked, no beneficial craftable-now boost -> guard does not fire on boost path.
    assert craft_potions_fires(state, gd) is False

def test_goal_crafts_boost_after_heal_satisfied():
    goal = CraftPotionsGoal(combat_monster="fire_monster", game_data=gd)
    # heal equipped >= baseline; boost under-stocked -> _active_craft targets the boost.
    target, _runs, _q = goal._active_craft(state, gd)
    assert target == "res_fire_potion"

def test_goal_prioritizes_heal_over_boost():
    # heal under baseline -> crafts heal even if a boost is also beneficial.
    target, _runs, _q = goal._active_craft(state, gd)
    assert target == "small_health_potion"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_potion_supply_integration.py tests/test_ai/test_craft_potions.py -k "boost or heal_over" -v`
Expected: FAIL.

- [ ] **Step 3: Implement the guard branch**

In `craft_potions_fires` (after the existing heal-supply check, before returning False): resolve `monster = _primary_combat_target(state, game_data)` (first of `combat_target_monsters(state, game_data)` by its existing order; `None` when empty). If `monster` is not None, `boost = best_boost_potion(state, game_data, monster)`; if `boost` is not None and `equipped_potion_qty(state, boost) < potion_baseline_pure(state.level, ...)` and `_recipe_producible(dict(game_data.crafting_recipes.get(boost, {})), state, game_data)`, return True. Add a small `_primary_combat_target` helper (or inline) — deterministic.

- [ ] **Step 4: Implement goal target resolution (heal-then-boost)**

In `CraftPotionsGoal`, change the target the craft ladder uses so that when the heal target is satisfied (`equipped >= heal baseline`) and `self._combat_monster` is set, the goal targets `best_boost_potion(state, game_data, self._combat_monster)`. Keep `_baseline` correct: for a boost, `hp_restore_of(boost) == 0` so `_baseline` already returns the level baseline (existing fallback) — verify this yields a sane boost stock qty. `equipped_potion_qty` already sums utility slots for any code, so it works for a boost.

- [ ] **Step 5: Run to verify pass + no heal regression**

Run: `uv run pytest tests/test_ai/test_potion_supply_integration.py tests/test_ai/test_craft_potions.py tests/test_ai/test_craft_potions_boost.py -v`
Expected: PASS; all pre-existing heal + unlock-boost tests still green.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/potion_supply.py src/artifactsmmo_cli/ai/goals/craft_potions.py tests/test_ai/test_potion_supply_integration.py tests/test_ai/test_craft_potions.py
git commit -m "feat(potion): craft the best craftable-now boost when heals are stocked"
```

---

### Task 5: Full suite, gate, anti-grind regression, coverage

**Files:**
- Verify: whole suite; `./formal/gate.sh`
- Possibly modify: mutation anchors / differential fixtures if the gate flags drift; new tests to reach 100% on the new modules.

- [ ] **Step 1: Full suite + coverage**

Run: `uv run pytest --cov -q`
Expected: 0 failures, 0 warnings, 0 skipped, 100% coverage. Any uncovered NEW line in `boost_selection.py` / `combat.py` / the guard branch gets a real behavioral test (curate; do not skip). Any pre-existing test broken by the intended behavior change is fixed in place to the new behavior, noted in the report.

- [ ] **Step 2: Type check**

Run: `uv run mypy src`
Expected: clean.

- [ ] **Step 3: Anti-grind regression (explicit)**

Add to `tests/test_ai/test_potion_supply_integration.py` a test asserting that when the only margin-improving boost requires a skill above the character's current level, neither the guard fires on the boost path nor does any plannable step emit a `ReachSkillLevel` for the boost — the economy simply does not pursue it.

Run: `uv run pytest tests/test_ai/test_potion_supply_integration.py -k anti_grind -v`
Expected: PASS.

- [ ] **Step 4: Decision gate**

Run: `./formal/gate.sh` (serialized — nothing else importing `src`).
Expected: green. Confirm the report shows: all `PREDICT_WIN_MUTATIONS` still killed (predict_win unchanged), all `COMBAT_MARGIN_MUTATIONS` killed, all `BOOST_SELECTION_MUTATIONS` killed, `lake build` OK with no `sorry`/axioms, and no axiom-lint regression. If a differential anchor drifts on `combat.py`, only regen a fixture if a bound decision genuinely changed; otherwise fix the anchor and report.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test(boost): full-suite + gate + anti-grind regression for boost-potion crafting"
```

---

## Self-Review

**Spec coverage:**
- `combat_margin` (spec §1) → Tasks 1 (helper extraction) + 2 (margin + Lean diff + mutation). ✓
- `best_boost_potion` (spec §2) → Task 3. ✓
- Guard branch reuse `CRAFT_POTIONS` (spec §3) → Task 4. ✓
- Goal heal-then-boost (spec §4) → Task 4. ✓
- `predict_win` byte-identical (spec non-goal) → Task 1 characterization test + Task 5 gate check. ✓
- Anti-grind craftable-now-only → Task 3 (by construction) + Task 5 explicit regression. ✓
- Testing/gate (diff + mutation + coverage + gate.sh) → Tasks 2/3/5. ✓

**Placeholder scan:** The Lean `combatMargin` body and the `project_equip` helper are described structurally rather than transcribed verbatim — they are genuine implementation steps requiring the `lean4` skill / projection reuse, not fillable as copy-paste; each names the exact defs to reuse and the exact encoding. No TBD/TODO elsewhere; every Python test/step shows code or an exact command.

**Type consistency:** `combat_margin(state, game_data, monster_code) -> int`, `best_boost_potion(state, game_data, monster_code) -> str | None`, helper signatures fixed in Task 1 and reused in Task 2. `WIN_MARGIN`/`LOSE_MARGIN` (Python) mirror `winMargin`/`loseMargin` (Lean). Guard reuses `CRAFT_POTIONS`; no new `GuardKind`.

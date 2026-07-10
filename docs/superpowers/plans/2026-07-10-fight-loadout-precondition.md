# Fight-Loadout Precondition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `FightAction.is_applicable` hard-require that the equipped loadout matches the best on-hand combat loadout, so the GOAP planner sequences `OptimizeLoadout(combat)` (and slot-relief when the bag is full) BEFORE any fight — the bot never fights with a stale gathering tool in the weapon slot.

**Architecture:** Extract the per-slot loadout comparison already living in `FightAction.cost` into one shared pure predicate `equipped_matches_loadout(equipment, optimal)`. Consume it in both `cost` (soft penalty, unchanged behavior) and `is_applicable` (new hard gate). Re-verify the Lean liveness/no-deadlock layer: `fightApplicable` gains a `loadoutOptimal` conjunct (modeled as an opaque Bool, like the existing `winnable` oracle), its theorems are reproven, and the combat-liveness seam gains a satisfiable `loadoutOptimal` hypothesis discharged by the realizable-loadout invariant. Then re-derive any planner goldens the new fight predecessor shifts, and confirm on live Robby.

**Tech Stack:** Python 3.13 (`uv run`), pytest, Lean 4 (`lake build`), the `formal/` differential + mutation gate.

## Global Constraints

Copied verbatim from the spec (`docs/superpowers/specs/2026-07-10-fight-loadout-precondition-design.md`) and the repo rules (`CLAUDE.md`). Every task's requirements implicitly include these:

- Use only game/bundle data or fail with an error — no defaulting. `pick_loadout` already fails loudly on missing data; add no new defaulting.
- NEVER catch `Exception`. No `if TYPE_CHECKING`. No inline imports (all imports at top of file). No triple-dot imports.
- ONE behavioral class per file. A pure module-level function (`equipped_matches_loadout`) is not a behavioral class and may live in its own small pure module.
- Multiple levels of error handling is a bug — ONE locus for the loadout comparison (`cost` and `is_applicable` share the single predicate).
- Exact-integer decision arithmetic — no float in the decision path. (The predicate is boolean dict comparison; no arithmetic.)
- All tests in `tests/`. Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage on changed files.
- `formal/diff/` is NOT in the default pytest path — after any change to `WorldState`, an `is_applicable`, or an extracted symbol, run `uv run pytest formal/diff/ -q --no-cov` explicitly.
- `tests/ai/` and `tests/test_ai/` are SEPARATE directories — run both.
- Never run `formal/gate.sh` or `formal/diff/mutate.py` concurrently with anything importing `src` (including the live bot). Serialize; bring the bot down first.
- Commit only when a task's steps say to. Do NOT push. Do NOT `git rm`/`restore`/`stash`/`checkout` unrelated files (notably `formal/diff/trace_lockstep_report.txt`); `git add` only the files each task names.

## Reference: the bug (from the spec)

Robby (L13) loses cow fights because a `copper_pickaxe` (mining tool, 5 attack) sits in `weapon_slot` instead of his owned `water_bow`. `pick_loadout(Combat(cow))` correctly picks `water_bow` (a 1-slot swap), but at a full bag (`inventory_slots_free == 0`) `OptimizeLoadout(combat).is_applicable` is False (the displaced pickaxe needs a free slot), so the swap can't run. `is_winnable` uses the best on-hand loadout so the bot commits, then fights with the equipped pickaxe → `fight_lost`. Today `FightAction` only SOFT-penalizes this (`LOADOUT_PENALTY` in `cost`); when the swap is slot-blocked it fights bare. The fix makes the fight hard-inapplicable until equipped == optimal, forcing `relief → OptimizeLoadout(combat) → Fight`.

## Key facts an implementer needs

- `FightAction` lives in `src/artifactsmmo_cli/ai/actions/combat.py`. `is_applicable` (lines 61-83) checks: `locations`, `inventory_free >= 1`, `hp_percent > 0.3`, `monster_level <= level+2`, and `drop_farm or xp_per_kill > 0`. It does NOT call `is_winnable` (capability is decided upstream at target selection). The new gate is appended here.
- `FightAction.cost` (lines 126-148) already computes `optimal = pick_loadout_cached(Combat(monster_attack, monster_resistance), state, game_data)` and does `if any(state.equipment.get(slot) != code for slot, code in optimal.items()): base += LOADOUT_PENALTY`. This exact comparison is what the predicate extracts.
- `pick_loadout_cached(purpose, state, game_data) -> dict[str, str | None]` (from `artifactsmmo_cli.ai.equipment.loadout_cache`) — memoized, returns every slot the loadout fills; `state.equipment` carries only filled slots, so direct dict-equality always disagrees on shape. Match per-slot.
- `Combat` is `from artifactsmmo_cli.ai.gear_value_core import Combat`; built as `Combat(game_data.monster_attack(code), game_data.monster_resistance(code))`.
- `OptimizeLoadoutAction` (`src/artifactsmmo_cli/ai/actions/optimize_loadout.py`) is already slot-gated in `is_applicable` (displaced items need free slots); at a full bag the shipped relief ladder frees a slot first. NO new slot code is needed.
- Lean `fightApplicable` (`formal/Formal/ActionApplicability.lean`, def at line 94) claims a term-by-term Python mirror and is the combat-liveness seam (`winnable_inWindow_imp_fightApplicable`, line 237) consumed by `formal/Formal/LivenessChain.lean`. It is NOT value-diff-bound (no `formal/diff` oracle, no `mutate.py` group targets `FightAction.is_applicable`; `mutate.py` only mutates `FightAction.apply` and `objective_step_fight_core`). `NoActionDeadlock.lean` treats `combatCapable` as an opaque Bool and does not unfold `fightApplicable`. So the Lean edit is: add a conjunct + reprove `ActionApplicability.lean`'s own theorems; `LivenessChain.lean` and `NoActionDeadlock.lean` need no change (they take `fightApplicable`/`combatCapable` as hypotheses).
- Manifest `#check`s eight `ActionApplicability` theorems (`formal/Formal/Manifest.lean:749-757`).
- `test_no_deadlock` (`tests/test_ai/scenarios/test_no_deadlock.py`) pins `l10_gearcrafting_gap`'s plan as exactly `["Fight(chicken)"]` (line ~104). If the scenario's equipped loadout differs from `pick_loadout(Combat(chicken))`, the new gate makes that golden `["OptimizeLoadout(chicken)", "Fight(chicken)"]`. This is a genuine plan improvement to re-derive, NOT a regression — Task 5 handles it explicitly.

---

### Task 1: Shared `equipped_matches_loadout` predicate

**Files:**
- Create: `src/artifactsmmo_cli/ai/loadout_match.py`
- Test: `tests/test_ai/test_loadout_match.py`

**Interfaces:**
- Consumes: nothing (pure stdlib).
- Produces: `equipped_matches_loadout(equipment: dict[str, str | None], optimal: dict[str, str | None]) -> bool` — True iff, for every slot the optimal loadout fills, the equipment already holds the same code. Per-slot (not whole-dict) comparison, because `optimal` carries only the slots it fills while `equipment` may carry extra filled slots and both use `None` placeholders inconsistently.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_loadout_match.py`:

```python
"""equipped_matches_loadout: per-slot match of equipped vs an optimal loadout."""

from artifactsmmo_cli.ai.loadout_match import equipped_matches_loadout


def test_exact_match_is_true() -> None:
    equipment = {"weapon_slot": "water_bow", "helmet_slot": "copper_helmet"}
    optimal = {"weapon_slot": "water_bow"}
    assert equipped_matches_loadout(equipment, optimal) is True


def test_per_slot_mismatch_is_false() -> None:
    # optimal wants water_bow in the weapon slot; a mining tool is equipped.
    equipment = {"weapon_slot": "copper_pickaxe"}
    optimal = {"weapon_slot": "water_bow"}
    assert equipped_matches_loadout(equipment, optimal) is False


def test_optimal_subset_matches_when_equipment_has_extra_slots() -> None:
    # equipment fills more slots than optimal names; only the named slots bind.
    equipment = {"weapon_slot": "water_bow", "boots_slot": "leather_boots"}
    optimal = {"weapon_slot": "water_bow"}
    assert equipped_matches_loadout(equipment, optimal) is True


def test_missing_slot_in_equipment_is_false() -> None:
    # optimal wants a weapon the character has not equipped at all.
    equipment: dict[str, str | None] = {}
    optimal = {"weapon_slot": "water_bow"}
    assert equipped_matches_loadout(equipment, optimal) is False


def test_optimal_none_placeholder_requires_empty_slot() -> None:
    # optimal explicitly wants the slot EMPTY; a filled slot mismatches.
    equipment = {"utility1_slot": "small_health_potion"}
    optimal = {"utility1_slot": None}
    assert equipped_matches_loadout(equipment, optimal) is False


def test_optimal_none_matches_absent_slot() -> None:
    # equipment lacks the slot (get -> None) and optimal wants None -> match.
    equipment: dict[str, str | None] = {}
    optimal = {"utility1_slot": None}
    assert equipped_matches_loadout(equipment, optimal) is True


def test_empty_optimal_is_vacuously_true() -> None:
    assert equipped_matches_loadout({"weapon_slot": "water_bow"}, {}) is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_loadout_match.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.loadout_match'`.

- [ ] **Step 3: Write the minimal implementation**

Create `src/artifactsmmo_cli/ai/loadout_match.py`:

```python
"""Pure predicate: does the equipped gear already match an optimal loadout?

`pick_loadout` returns only the slots the chosen loadout fills, using `None`
to mean "this slot should be EMPTY". `state.equipment` carries only its filled
slots. Whole-dict equality therefore always disagrees on shape, so both
`FightAction.cost` (soft LOADOUT_PENALTY) and `FightAction.is_applicable` (the
hard optimal-loadout gate) compare per-slot through this single locus — no
divergent loadout logic.
"""


def equipped_matches_loadout(
    equipment: dict[str, str | None], optimal: dict[str, str | None]
) -> bool:
    """True iff, for every slot the optimal loadout names, `equipment` holds the
    same code (`equipment.get(slot)` defaulting to None to match an absent slot
    or an explicit None target)."""
    return not any(equipment.get(slot) != code for slot, code in optimal.items())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_loadout_match.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/loadout_match.py tests/test_ai/test_loadout_match.py
git commit -m "feat(combat): extract equipped_matches_loadout shared predicate"
```

---

### Task 2: Route `FightAction.cost` through the shared predicate (no behavior change)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/combat.py:141-147`
- Test: `tests/test_ai/test_actions.py` (existing FightAction cost coverage — do not add a new file; verify unchanged behavior)

**Interfaces:**
- Consumes: `equipped_matches_loadout` from Task 1.
- Produces: no new public symbol. `FightAction.cost` behavior is byte-for-byte identical (soft `LOADOUT_PENALTY` still added exactly when the loadout is suboptimal).

- [ ] **Step 1: Add the import**

At the top of `src/artifactsmmo_cli/ai/actions/combat.py`, alongside the other `from artifactsmmo_cli.ai...` imports (keep alphabetical grouping near `from artifactsmmo_cli.ai.learning.store import LearningStore`), add:

```python
from artifactsmmo_cli.ai.loadout_match import equipped_matches_loadout
```

- [ ] **Step 2: Replace the inline comparison in `cost`**

In `FightAction.cost`, replace:

```python
        if any(state.equipment.get(slot) != code for slot, code in optimal.items()):
            base += LOADOUT_PENALTY
        return base
```

with:

```python
        if not equipped_matches_loadout(state.equipment, optimal):
            base += LOADOUT_PENALTY
        return base
```

- [ ] **Step 3: Run the existing FightAction cost tests**

Run: `uv run pytest tests/test_ai/test_actions.py -q -k "fight or Fight or cost"`
Expected: PASS — same results as before the edit (the refactor is behavior-preserving).

- [ ] **Step 4: Run the broader combat/action suites to confirm no drift**

Run: `uv run pytest tests/test_ai/test_actions.py tests/test_ai/test_actions_transition.py tests/ai/ -q`
Expected: PASS, 0 failures.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/combat.py
git commit -m "refactor(combat): FightAction.cost uses equipped_matches_loadout"
```

---

### Task 3: Hard optimal-loadout gate on `FightAction.is_applicable`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/combat.py:61-83` (append the gate)
- Test: `tests/test_ai/test_fight_loadout_precondition.py`

**Interfaces:**
- Consumes: `equipped_matches_loadout` (Task 1), `pick_loadout_cached`, `Combat` (both already imported in `combat.py`).
- Produces: `FightAction.is_applicable` returns False when `not equipped_matches_loadout(state.equipment, pick_loadout_cached(Combat(monster), state, game_data))`, in addition to all existing structural gates. The gate applies to drop-farm fights too (drop_farm bypasses ONLY the xp gate).

- [ ] **Step 1: Write the failing applicability tests**

Create `tests/test_ai/test_fight_loadout_precondition.py`. Reuse the GameData/state style from `tests/ai/test_gather_loadout.py` (a minimal `GameData` with `_item_stats`, `_monster_attack`, `_monster_resistance`, `_monster_levels`, `_xp_table` as needed). Concretely:

```python
"""FightAction.is_applicable hard-requires the equipped loadout to match the
best on-hand combat loadout, so the planner sequences OptimizeLoadout first."""

import dataclasses

import pytest

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.world_state import WorldState

_ALL_SLOTS: dict[str, str | None] = {
    "weapon_slot": None, "shield_slot": None, "helmet_slot": None,
    "body_armor_slot": None, "leg_armor_slot": None, "boots_slot": None,
    "ring1_slot": None, "ring2_slot": None, "amulet_slot": None,
    "artifact1_slot": None, "artifact2_slot": None, "artifact3_slot": None,
    "utility1_slot": None, "utility2_slot": None, "bag_slot": None, "rune_slot": None,
}


def _gd() -> GameData:
    """cow: L1 monster, water-weak. water_bow beats copper_pickaxe (mining tool)."""
    gd = GameData()
    gd._item_stats = {
        "water_bow": ItemStats(code="water_bow", level=1, type_="weapon",
                               attack={"water": 8}),
        "copper_pickaxe": ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                                    subtype="tool", attack={"earth": 5},
                                    skill_effects={"mining": -10}),
    }
    gd._monster_attack = {"cow": {"earth": 3, "fire": 0, "water": 0, "air": 0}}
    gd._monster_resistance = {"cow": {"earth": 0, "fire": 0, "water": 0, "air": 0}}
    gd._monster_levels = {"cow": 1}
    return gd


def _state(equipment: dict[str, str | None], inventory: dict[str, int]) -> WorldState:
    eq = dict(_ALL_SLOTS)
    eq.update(equipment)
    return WorldState(
        character="testchar", level=13, xp=0, max_xp=1000,
        hp=100, max_hp=100, gold=0,
        skills={"mining": 5}, x=0, y=0,
        inventory=inventory, inventory_max=20, inventory_slots_max=20,
        equipment=eq, cooldown_expires=None,
        task_code=None, task_type=None, task_progress=0, task_total=0,
        task_lifecycle_phase=derive_task_lifecycle_phase(None, 0, 0),
        bank_items=None, bank_gold=None, bank_capacity=None, pending_items=None,
    )


@pytest.fixture
def cow_fight() -> FightAction:
    return FightAction(monster_code="cow", locations=frozenset({(0, 0)}))


def test_inapplicable_when_gathering_tool_equipped(cow_fight: FightAction) -> None:
    """The exact live bug: pickaxe in weapon_slot, water_bow owned in inventory.
    pick_loadout picks water_bow so the equipped pickaxe is suboptimal -> the
    fight is NOT applicable (planner must OptimizeLoadout first)."""
    gd = _gd()
    state = _state(equipment={"weapon_slot": "copper_pickaxe"},
                   inventory={"water_bow": 1})
    assert cow_fight.is_applicable(state, gd) is False


def test_applicable_when_optimal_loadout_equipped(cow_fight: FightAction) -> None:
    """water_bow already equipped and no better weapon owned -> equipped ==
    optimal -> the fight is applicable."""
    gd = _gd()
    state = _state(equipment={"weapon_slot": "water_bow"}, inventory={})
    assert cow_fight.is_applicable(state, gd) is True


def test_loadout_gate_applies_to_drop_farm(cow_fight: FightAction) -> None:
    """drop_farm bypasses ONLY the xp gate; a drop-farm fight with a suboptimal
    loadout is still inapplicable."""
    gd = _gd()
    farm = dataclasses.replace(cow_fight, drop_farm=True)
    state = _state(equipment={"weapon_slot": "copper_pickaxe"},
                   inventory={"water_bow": 1})
    assert farm.is_applicable(state, gd) is False
```

Note: if `GameData()` requires more seeded tables for `xp_per_kill(cow, 13)` to be positive, seed the minimal `_xp_table`/`monster_level` fields the constructor path needs — mirror what `tests/ai/test_gather_loadout.py::_gd_woodcutting` seeds. `xp_per_kill` must be > 0 so the fight is not excluded by the xp gate for the wrong reason (we are testing the loadout gate in isolation).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_fight_loadout_precondition.py -q`
Expected: `test_inapplicable_when_gathering_tool_equipped` and `test_loadout_gate_applies_to_drop_farm` FAIL (is_applicable currently returns True — no loadout gate yet); `test_applicable_when_optimal_loadout_equipped` PASSES.

- [ ] **Step 3: Add the hard gate to `is_applicable`**

In `src/artifactsmmo_cli/ai/actions/combat.py`, in `FightAction.is_applicable`, replace the final return:

```python
        return self.drop_farm or game_data.xp_per_kill(self.monster_code, state.level) > 0
```

with:

```python
        if not (self.drop_farm or game_data.xp_per_kill(self.monster_code, state.level) > 0):
            return False
        # HARD optimal-loadout gate: never fight with a loadout worse than the
        # best on-hand combat loadout. is_winnable/predict_win COMMIT on that
        # best loadout (combat.py is_winnable uses pick_loadout_cached), but the
        # server executes whatever is EQUIPPED — so a stale gathering tool in the
        # weapon slot loses a winnable fight (live Robby vs cow, 2026-07-09). When
        # equipped != optimal, the fight is inapplicable and the planner sequences
        # OptimizeLoadout(combat) first (itself slot-gated, so relief frees a slot
        # at a full bag: relief -> OptimizeLoadout -> Fight). pick_loadout is
        # memoized (pick_loadout_cached) and returns a REALIZABLE loadout, so the
        # swap can always reach it -> no permanent block. Same shared predicate as
        # FightAction.cost (one locus, no divergence). NOT modeled as a Lean
        # differential mirror — pinned in Python (unit + no_deadlock scenarios);
        # Lean fightApplicable carries it as the opaque loadoutOptimal conjunct.
        optimal = pick_loadout_cached(
            Combat(game_data.monster_attack(self.monster_code),
                   game_data.monster_resistance(self.monster_code)),
            state, game_data,
        )
        return equipped_matches_loadout(state.equipment, optimal)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_fight_loadout_precondition.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Run the differential + broad action/goal suites (is_applicable changed)**

The gate changes an `is_applicable`, so run the formal differential explicitly plus both AI test roots and the goals suite:

```bash
uv run pytest formal/diff/ -q --no-cov --ignore=formal/diff/test_game_data_fixture_diff.py
uv run pytest tests/ai/ tests/test_ai/test_actions.py tests/test_ai/test_actions_transition.py tests/test_ai/test_grind_character_xp.py tests/test_ai/test_goals.py -q
```
Expected: formal/diff PASS (no fight-applicability oracle exists, so no diff should shift). The AI suites may surface goal/plan changes — if `test_grind_character_xp` or `test_goals` now expects a swap-then-fight plan, that is Task 5's re-derivation; note the failures and proceed (do NOT patch goldens in this task). If a NON-plan-shape test fails (e.g. a unit contract), fix it here.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/combat.py tests/test_ai/test_fight_loadout_precondition.py
git commit -m "feat(combat): hard optimal-loadout gate on FightAction.is_applicable"
```

---

### Task 4: Lean — model the loadout gate + re-verify liveness

**Files:**
- Modify: `formal/Formal/ActionApplicability.lean`
- Modify: `formal/Formal/Manifest.lean:749-757` (add one `#check`)

**Interfaces:**
- Consumes: nothing new — `loadoutOptimal` is an opaque `Bool` input to `FightInputs`, the same modeling pattern as the existing `winnable` oracle in `LivenessChain`.
- Produces: `fightApplicable` gains a `loadoutOptimal` conjunct; a new theorem `fightApplicable_false_of_suboptimal_loadout`; the seam `winnable_inWindow_imp_fightApplicable` gains a `loadoutOptimal = true` hypothesis with an updated non-vacuity witness. `LivenessChain.lean` and `NoActionDeadlock.lean` need NO change (they consume `fightApplicable`/`combatCapable` as hypotheses, never unfolding the new conjunct).

- [ ] **Step 1: Add the atomic gate + field**

In `formal/Formal/ActionApplicability.lean`, after `hasInventoryRoom` (line ~67) add:

```lean
/-- Loadout gate (2026-07-10): the equipped loadout must MATCH the best
on-hand combat loadout for the monster. Python `FightAction.is_applicable`
computes this via `equipped_matches_loadout(equipment,
pick_loadout_cached(Combat(monster), ...))`; here it is an opaque Bool oracle
(like `winnable`), because a loadout-dict comparison has no arithmetic to
mirror and is pinned in Python (unit + no_deadlock scenarios), not by a
`formal/diff` value-lockstep. -/
def loadoutOptimal (b : Bool) : Bool := b
```

In `structure FightInputs`, add a field (after `dropFarm`):

```lean
  loadoutMatches : Bool := true
  -- Loadout gate (2026-07-10): equipped == best on-hand combat loadout.
  -- Defaults true so every pre-existing witness/proof that predates the gate
  -- stays a valid `fightApplicable = true` state (an already-optimal loadout).
```

- [ ] **Step 2: Thread the conjunct into `fightApplicable`**

Replace the `fightApplicable` body:

```lean
def fightApplicable (i : FightInputs) : Bool :=
  i.hasLocations
    && hasInventoryRoom i.inventoryFree i.minFreeSlots
    && hpAboveFightFloor i.hp i.maxHp
    && (i.dropFarm || xpPositive i.xpPerKill)
    && monsterNotOverleveled i.playerLevel i.monsterLevel
    && loadoutOptimal i.loadoutMatches
```

- [ ] **Step 3: Build to see what breaks**

Run: `cd formal && lake build Formal.ActionApplicability`
Expected: the `_false_of_*` theorems still compile (a `false` conjunct keeps the `&&` chain false, and their `simp [h]`/`simp [this]` proofs discharge unchanged). Failures are expected in: `fightApplicable_mono_in_hp` (destructures the conjunction), `fightApplicable_iff`, `below_old_window_xp_positive_is_applicable`, `winnable_inWindow_imp_fightApplicable`, `winnable_inWindow_imp_fightApplicable_nonvacuous`, `dropFarm_zero_xp_applicable_iff_structural`, and `dropFarm_grey_mob_applicable_nonvacuous`. Fix each in the next steps.

- [ ] **Step 4: Repair `fightApplicable_mono_in_hp`**

The destructure now has six components. Update:

```lean
theorem fightApplicable_mono_in_hp (i : FightInputs) (hp' : Int)
    (hLe : i.hp ≤ hp')
    (hApp : fightApplicable i = true) :
    fightApplicable { i with hp := hp' } = true := by
  unfold fightApplicable at hApp
  simp only [Bool.and_eq_true] at hApp
  obtain ⟨⟨⟨⟨⟨hLoc, hInv⟩, hHp⟩, hXp⟩, hLvl⟩, hLoad⟩ := hApp
  have hHp' : hpAboveFightFloor hp' i.maxHp = true := by
    unfold hpAboveFightFloor at hHp ⊢
    simp at hHp
    apply decide_eq_true
    have hMul : i.hp * 100 ≤ hp' * 100 :=
      Int.mul_le_mul_of_nonneg_right hLe (by decide)
    omega
  unfold fightApplicable
  simp only [Bool.and_eq_true]
  exact ⟨⟨⟨⟨⟨hLoc, hInv⟩, hHp'⟩, hXp⟩, hLvl⟩, hLoad⟩
```

- [ ] **Step 5: Repair `fightApplicable_iff`**

Add the conjunct to the RHS and the unfold list:

```lean
theorem fightApplicable_iff (i : FightInputs) :
    fightApplicable i = true ↔
      i.hasLocations = true ∧ i.inventoryFree ≥ i.minFreeSlots ∧
      i.hp * 100 > 50 * i.maxHp ∧ (i.dropFarm = true ∨ i.xpPerKill > 0) ∧
      i.monsterLevel ≤ i.playerLevel + 2 ∧ i.loadoutMatches = true := by
  unfold fightApplicable hasInventoryRoom hpAboveFightFloor xpPositive
    monsterNotOverleveled loadoutOptimal
  simp [and_assoc]
```

- [ ] **Step 6: Repair `below_old_window_xp_positive_is_applicable`**

It builds `fightApplicable` via `fightApplicable_iff.mpr`; add a `loadoutMatches` hypothesis and pass it:

```lean
theorem below_old_window_xp_positive_is_applicable
    (i : FightInputs)
    (hLoc  : i.hasLocations = true)
    (hInv  : i.inventoryFree ≥ i.minFreeSlots)
    (hHp   : i.hp * 100 > 50 * i.maxHp)
    (hXp   : i.xpPerKill > 0)
    (hUp   : i.monsterLevel ≤ i.playerLevel + 2)
    (hLoad : i.loadoutMatches = true)
    (_hBelow : i.monsterLevel < max 1 (i.playerLevel - 1)) :
    fightApplicable i = true := by
  exact (fightApplicable_iff i).mpr ⟨hLoc, hInv, hHp, Or.inr hXp, hUp, hLoad⟩
```

- [ ] **Step 7: Add the new independence theorem + repair the liveness seam**

Add, after `fightApplicable_false_of_overleveled_monster`:

```lean
/-- If the equipped loadout is NOT the best on-hand combat loadout, the
predicate is false — the 2026-07-10 gate. The planner must run
OptimizeLoadout(combat) (slot-relief first when the bag is full) to reach the
optimal loadout before the fight becomes applicable. -/
theorem fightApplicable_false_of_suboptimal_loadout (i : FightInputs)
    (h : i.loadoutMatches = false) :
    fightApplicable i = false := by
  unfold fightApplicable loadoutOptimal
  simp [h]
```

Repair the seam `winnable_inWindow_imp_fightApplicable` — add the `loadoutMatches` hypothesis (satisfiable: OptimizeLoadout reaches the realizable optimal loadout, then equipped == optimal):

```lean
theorem winnable_inWindow_imp_fightApplicable
    (i : FightInputs)
    (hLoc : i.hasLocations = true)
    (hInv : hasInventoryRoom i.inventoryFree i.minFreeSlots = true)
    (hHp  : hpAboveFightFloor i.hp i.maxHp = true)
    (hWin : i.monsterLevel ≤ i.playerLevel + 2)
    (hXp  : xpPositive i.xpPerKill = true)
    (hLoad : loadoutOptimal i.loadoutMatches = true) :
    fightApplicable i = true := by
  unfold fightApplicable
  simp only [Bool.and_eq_true]
  refine ⟨⟨⟨⟨⟨hLoc, hInv⟩, hHp⟩, ?_⟩, decide_eq_true hWin⟩, hLoad⟩
  simp [hXp]
```

- [ ] **Step 8: Repair both non-vacuity witnesses and the dropFarm iff**

`winnable_inWindow_imp_fightApplicable_nonvacuous`: the witness sets `loadoutMatches := true` (it defaults true, so the record literal is unchanged) and the statement gains the `loadoutOptimal` conjunct:

```lean
theorem winnable_inWindow_imp_fightApplicable_nonvacuous :
    let i : FightInputs :=
      { hasLocations := true, inventoryFree := 1, hp := 100, maxHp := 100,
        playerLevel := 5, monsterLevel := 5, minFreeSlots := 1,
        xpPerKill := 10 }
    i.hasLocations = true
      ∧ hasInventoryRoom i.inventoryFree i.minFreeSlots = true
      ∧ hpAboveFightFloor i.hp i.maxHp = true
      ∧ i.monsterLevel ≤ i.playerLevel + 2
      ∧ xpPositive i.xpPerKill = true
      ∧ loadoutOptimal i.loadoutMatches = true
      ∧ fightApplicable i = true := by
  refine ⟨rfl, by decide, by decide, by decide, by decide, by decide, ?_⟩
  decide
```

`dropFarm_zero_xp_applicable_iff_structural`: the loadout gate is NOT bypassed by drop-farm, so it joins the RHS:

```lean
theorem dropFarm_zero_xp_applicable_iff_structural (i : FightInputs)
    (hFarm : i.dropFarm = true) (_hZero : i.xpPerKill ≤ 0) :
    fightApplicable i = true ↔
      i.hasLocations = true ∧ i.inventoryFree ≥ i.minFreeSlots ∧
      i.hp * 100 > 50 * i.maxHp ∧ i.monsterLevel ≤ i.playerLevel + 2 ∧
      i.loadoutMatches = true := by
  rw [fightApplicable_iff]
  simp [hFarm]
```

`dropFarm_grey_mob_applicable_nonvacuous`: the witness's `loadoutMatches` defaults true, so `decide` still closes — no literal change needed. Rebuild to confirm.

- [ ] **Step 9: Build the module clean**

Run: `cd formal && lake build Formal.ActionApplicability`
Expected: builds with 0 errors, 0 sorries.

- [ ] **Step 10: Update the module docstrings for honesty**

In `formal/Formal/ActionApplicability.lean`, update the header enumeration (the "Specifies `fightApplicable` as a conjunction of 5 atomic conditions" line) to say SIX, naming the loadout gate, and add one sentence that the loadout gate is an opaque Python-pinned oracle (not a `formal/diff` mirror). Also update the `equipApplicable` honesty note that currently reads "Fight is NOT slot-gated in this fix ... nothing changes there" — append: the 2026-07-10 loadout gate adds `loadoutOptimal` to `fightApplicable` as a Python-pinned opaque conjunct (unit + no_deadlock scenarios), distinct from the omitted slot-room term. Keep it factual and short.

- [ ] **Step 11: Register the new theorem in the Manifest**

In `formal/Formal/Manifest.lean`, in the `ActionApplicability (Phase G4)` block (after line 757), add:

```lean
#check @Formal.ActionApplicability.fightApplicable_false_of_suboptimal_loadout
```

- [ ] **Step 12: Build the Manifest + run the proof-concept index check**

```bash
cd formal && lake build Formal.Manifest
bash formal/gate/check_proof_concept_index.sh
```
Expected: `lake build` clean. If the proof-concept index check fails because the new theorem/`@concept` accounting drifted, regenerate the index per the script's instructions (mechanical — see `project_snapshot_regen`/prior gate fixes), then re-run until green.

- [ ] **Step 13: Commit**

```bash
git add formal/Formal/ActionApplicability.lean formal/Formal/Manifest.lean
git commit -m "feat(formal): fightApplicable loadoutOptimal conjunct + liveness re-verify"
```

---

### Task 5: Re-derive planner goldens shifted by the fight predecessor

**Files:**
- Modify: `tests/test_ai/scenarios/test_no_deadlock.py` (golden re-derivation if the plan shape shifts)
- Create: `tests/test_ai/scenarios/test_fight_loadout_swap.py` (new scenario proving swap-then-fight)
- Possibly modify: other scenario/goal goldens surfaced by Task 3 Step 5 (e.g. `tests/test_ai/test_grind_character_xp.py`)

**Interfaces:**
- Consumes: the shipped gate (Task 3) + the existing scenario harness (`SCENARIOS`, `scenario_state`, `GamePlayer.plan_from_state`, `decide_tree`).
- Produces: green no_deadlock criteria (unchanged guarantees) with any plan goldens re-derived to the swap-then-fight shape, plus a new scenario proving `OptimizeLoadout(combat)` is sequenced before `Fight` (and `relief → swap → fight` at a full bag).

- [ ] **Step 1: Re-run the no_deadlock suite and record the actual shift**

Run: `uv run pytest tests/test_ai/scenarios/test_no_deadlock.py -q`
Expected: one of two outcomes for `test_l10_gearcrafting_gap_plans_craft_chain_not_char_grind` (asserts `[repr(a) for a in report.plan] == ["Fight(chicken)"]`):
  (a) STILL GREEN — the scenario's equipped loadout already equals `pick_loadout(Combat(chicken))`, so the gate inserts nothing. Nothing to change; skip to Step 3.
  (b) FAILS with actual plan `["OptimizeLoadout(chicken)", "Fight(chicken)"]` — the gate correctly front-loads the swap. This is a genuine improvement (the bot now arms its best loadout before the fight), NOT a regression. Proceed to Step 2.

- [ ] **Step 2: If shifted, update the golden with a derivation note**

Only if Step 1 hit outcome (b). Update the assertion to the ACTUAL observed plan and document why the shape changed. Example (use the REAL observed value from Step 1, do not assume the swap label):

```python
    # 2026-07-10: the fight-loadout precondition (FightAction.is_applicable hard
    # optimal-loadout gate) front-loads the combat swap when the scenario's
    # equipped loadout differs from pick_loadout(Combat(chicken)). The guarantee
    # is unchanged (NEVER GrindCharacterXP; a directional craft-chain plan that
    # reaches the feather dropper) — only the plan now arms the best loadout
    # before the fight.
    assert [repr(a) for a in report.plan] == ["OptimizeLoadout(chicken)", "Fight(chicken)"]
```

Keep every OTHER assertion (`chosen_root`, `not isinstance(..., GrindCharacterXPGoal)`) intact — the criterion must still hold. If the whole plan/selected_goal diverges beyond a prepended swap (e.g. selected_goal changed), STOP and escalate: that is a behavior change beyond the spec's "front-load OptimizeLoadout" and needs a human decision.

- [ ] **Step 3: Write the swap-then-fight scenario test**

Create `tests/test_ai/scenarios/test_fight_loadout_swap.py`. Build a state directly (no new SCENARIOS entry needed) where a gathering tool is equipped, the better weapon is owned, and a fight is the objective — assert the plan sequences the swap before the fight, and the full-bag variant routes relief first. Model the harness on `test_no_deadlock.py::_run` (seed `GamePlayer`, call `plan_from_state`). Use the real bundle so `pick_loadout` has data:

```python
"""The fight-loadout precondition sequences OptimizeLoadout(combat) before a
Fight, and slot-relief before the swap at a full bag (the live Robby cow bug)."""

import dataclasses
import json
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"


def _plan_reprs(player: GamePlayer) -> list[str]:
    return [repr(a) for a in player.plan_from_state().plan]
```

Then, using an existing winnable-combat scenario name from `SCENARIOS` as the base (pick one whose objective drives a Fight — e.g. `CRITERION_2_WINNABLE = "l20_dual_utility"` from `test_no_deadlock.py`, or another verified during Step 1), construct two derived states with `dataclasses.replace`:
  - **swap-then-fight:** replace the base state's `equipment` so the combat weapon slot holds a gather tool that `pick_loadout` would swap out, while the optimal weapon is present in `inventory` with slot headroom. Assert `"OptimizeLoadout(" ...` appears in the plan strictly before the `"Fight(" ...` entry.
  - **relief-then-swap-then-fight:** same, but fill the bag to `inventory_slots_max` so `inventory_slots_free == 0`. Assert the plan's first action is a relief/deposit action (matches the shipped slot-relief), followed by the swap, then the fight.

Because the exact monster/tool/weapon codes depend on the chosen bundle scenario, derive them from the bundle during Step 1 (inspect `scenario_state(SCENARIOS[name], gd).equipment` and `pick_loadout_cached(Combat(monster), state, gd)`) and hard-code the resolved codes here. Do NOT leave a placeholder — resolve the real codes and write concrete asserts. If no bundle scenario cleanly drives a single-monster fight objective, fall back to the minimal `GameData` + `WorldState` construction from `test_fight_loadout_precondition.py` and drive the planner via `GamePlayer.seed_offline` with that state.

- [ ] **Step 4: Run the new scenario + the full no_deadlock suite**

```bash
uv run pytest tests/test_ai/scenarios/test_fight_loadout_swap.py tests/test_ai/scenarios/test_no_deadlock.py -q
```
Expected: PASS. The no_deadlock criteria (never-deadlock, never-GrindCharacterXP-against-unwinnable, Wait-fallback) hold; the new scenario proves swap-before-fight and relief-before-swap.

- [ ] **Step 5: Re-run any goal suites Task 3 Step 5 flagged**

Run whatever failed in Task 3 Step 5 (e.g. `uv run pytest tests/test_ai/test_grind_character_xp.py tests/test_ai/test_goals.py -q`). Re-derive plan-shape goldens the same way (prepend the swap; keep the guarantee), or STOP and escalate if a selected_goal/root changed beyond a prepended swap.

- [ ] **Step 6: Commit**

```bash
git add tests/test_ai/scenarios/test_fight_loadout_swap.py tests/test_ai/scenarios/test_no_deadlock.py
# add any other golden files touched in Step 5
git commit -m "test(combat): re-derive fight goldens for swap-before-fight + swap scenario"
```

---

### Task 6: Confirm-or-follow-up the `cowhide` full-bag deadlock

**Files:**
- Create (only if confirmed resolved): a scenario assertion in `tests/test_ai/scenarios/test_fight_loadout_swap.py`
- Create (only if NOT resolved): `docs/superpowers/specs/2026-07-10-fight-for-drop-fullbag-followup.md`

**Interfaces:**
- Consumes: the shipped gate + relief.
- Produces: EITHER a passing assertion that `GatherMaterials(cowhide)` produces a directional plan at a full bag (`relief → swap → fight`), OR a written follow-up spec documenting the residual deadlock with a root-cause sketch. It is NOT allowed to silently remain a deadlock.

- [ ] **Step 1: Reproduce the reported deadlock against current HEAD**

Construct (or reuse) a full-bag state where a `cowhide` drop is demanded (a `GatherMaterialsGoal` over `cowhide`, `drop_farm` fight for the cow's drop) and the combat weapon slot holds a gather tool. Drive `plan_from_state` (30s budget as in the spec). Record whether the plan is empty (deadlock) or directional (`relief → OptimizeLoadout(cow) → Fight(cow)`).

Run: `uv run pytest tests/test_ai/scenarios/test_fight_loadout_swap.py -q -k cowhide` (after writing the reproduction, next step).

- [ ] **Step 2a: If the plan is now directional — pin it**

Add an assertion to `test_fight_loadout_swap.py` that the full-bag `cowhide` demand yields a non-empty plan whose first action is relief and which contains `OptimizeLoadout` before the drop-farm `Fight`. Commit:

```bash
git add tests/test_ai/scenarios/test_fight_loadout_swap.py
git commit -m "test(combat): cowhide full-bag drop-farm now plans relief->swap->fight"
```

- [ ] **Step 2b: If the plan is still empty — write a follow-up spec**

Do a minimal root-cause pass (is it slot contention beyond the weapon swap — the drop needs its OWN free slot AND the swap needs one, and relief frees only one at a time? is `GatherMaterials(cowhide)` fast-failing on an unsatisfiable subgoal?). Write `docs/superpowers/specs/2026-07-10-fight-for-drop-fullbag-followup.md` capturing the reproduction, the root-cause finding, and whether it is in the same slot-contention family as the shipped slot fix or a distinct issue. Commit the spec (no code fix in this plan — it is out of core scope per the design):

```bash
git add docs/superpowers/specs/2026-07-10-fight-for-drop-fullbag-followup.md
git commit -m "docs(spec): fight-for-drop full-bag deadlock follow-up (root cause)"
```

---

### Task 7: Runtime verification + full gate

**Files:** none (verification only).

**Interfaces:** consumes the whole branch.

- [ ] **Step 1: Bring the bot down (serialize)**

Confirm no process is importing `src` (the live player/TUI) before running the gate or any live plan — per the serialize-gate rule.

- [ ] **Step 2: Live plan verification on Robby**

Run the offline plan CLI against the live character (per `project_plan_cli`):

Run: `uv run artifactsmmo plan Robby`
Expected: with Robby still carrying a gathering tool in the weapon slot and owning `water_bow`, the emitted plan for a cow engagement now sequences `OptimizeLoadout(cow)` (preceded by a relief/deposit action if the bag is 20/20 full) BEFORE `Fight(cow)` — NOT a bare `Fight(cow)`. Capture the plan output. If the bot is safe to run live, a real cow fight should now equip `water_bow` first and win. Record the observed plan; do NOT claim the fight is won unless a live fight is actually run and observed.

- [ ] **Step 3: Full gate, serialized**

Run: `bash formal/gate.sh`
Expected: ALL PARTS PASSED (exit 0): lake build, axiom lint, no-sorry, proof-concept index, extraction drift, differential (`formal/diff/`), mutation (`formal/diff/mutate.py`). If the mutation step reports a `(stale)` survivor tied to the changed files, refresh the affected `mutate.py` anchors (anchor rot, per prior gate fixes) and re-run. If the extraction/proof-concept steps drift, regenerate mechanically.

- [ ] **Step 4: Final whole-suite run**

Run: `uv run pytest tests/ -q` and `uv run pytest tests/ai/ -q`
Expected: 0 errors, 0 warnings, 0 skipped; coverage intact on changed files.

- [ ] **Step 5: Record outcome**

Update the memory pointer `project_fight_loadout_precondition.md` (SHIPPED + gate result + live plan observation) and `MEMORY.md`. Do NOT push unless the user asks.

---

## Self-Review

**Spec coverage:**
- Spec §Components 1 (shared predicate) → Task 1 (+ Task 2 wires cost). ✅
- §2 (hard is_applicable gate) → Task 3. ✅
- §3 (relief interaction, no new slot code) → verified in Task 5 full-bag scenario + Task 6; no code, reuses shipped relief. ✅
- §4 (liveness/no-deadlock re-verification, fightApplicable unbound-but-liveness-referenced) → Task 4 (conjunct + reproofs + seam hypothesis + docstring honesty). ✅
- §5 (cowhide fight-for-drop confirm-or-follow-up) → Task 6. ✅
- §Testing (unit, applicability, scenario, no_deadlock, Lean, runtime, full gate) → Tasks 1/3/4/5/7. ✅
- §Risks (liveness breakage → Task 4; over-gating/unrealizable → Task 3 comment + Task 5 swap-reaches-optimal scenario; plan-shape churn → Task 5 golden re-derivation). ✅

**Placeholder scan:** Task 5 Step 3 intentionally defers the exact bundle monster/tool codes to Step 1's inspection rather than guessing — flagged explicitly with a resolve-don't-placeholder instruction and a concrete fallback (minimal GameData construction). No `TBD`/`TODO`. Task 6 branches (2a/2b) are both fully specified.

**Type consistency:** `equipped_matches_loadout(equipment, optimal) -> bool` is defined identically in Task 1 and consumed unchanged in Tasks 2-3. Lean `loadoutMatches`/`loadoutOptimal` names are consistent across Task 4 steps and the Manifest `#check`. `pick_loadout_cached(Combat(...), state, game_data)` signature matches the existing `combat.py` call site.

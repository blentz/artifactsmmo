# Fight-Applicability Liveness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the rogue `best_eq >= monster_level-1` gear gate from `FightAction.is_applicable` so the XP-grind picker's winnable targets are actually fightable, restoring picker⟷applicability consistency; decouple grind-XP satisfaction from loadout-optimality.

**Architecture:** The combat target picker selects on `is_winnable` (authoritative capability verdict). `FightAction.is_applicable` must be a *structural* gate that never rejects on capability grounds — only transient runtime preconditions (HP, inventory) + the suicide upper bound + `xp_per_kill>0`. A single rogue term (`best_eq >= monster_level-1`, equipped-item level) violated this, deadlocking grind. Fix removes it in Python AND its Lean model (`ActionApplicability.lean`, consumed by liveness `FightProgress`/`ProgressAction`) in lockstep, adds the `winnable ⇒ applicable` consistency lemma, and decouples `GrindCharacterXPGoal.is_satisfied`.

**Tech Stack:** Python 3.13 (`uv run`), pytest, Lean 4 + Mathlib (`lake`), differential gate (`formal/diff/`), mutation gate (`formal/diff/mutate.py`).

## Global Constraints

- Run every Python command via `uv run` (e.g. `uv run pytest`, `uv run python`). `export PATH="$HOME/.local/bin:$PATH"` first if `uv` is not found.
- Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- No inline imports; imports at top of file. One behavioral class per file.
- NEVER catch `Exception`. No `if TYPE_CHECKING`. No `...` imports.
- Keep `predict_win` OUT of `FightAction.is_applicable` (established decision: capability is `is_winnable`'s job, applied upstream). The consistency lemma is over the cheap structural gate, not the formula.
- Do NOT run `gate.sh`/`mutate.py` concurrently with anything importing `src` (including the bot). Serialize.
- The spec this implements: `docs/superpowers/specs/2026-06-29-fight-applicability-liveness-design.md`.

---

### Task 1: Remove the rogue gear gate from `FightAction.is_applicable` (Python)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/combat.py:48-77`
- Test: `tests/test_ai/test_no_combat_deadlock.py`

**Interfaces:**
- Consumes: existing `FightAction(monster_code, locations)`, `WorldState`, `GameData` fixtures used elsewhere in `tests/test_ai/test_no_combat_deadlock.py`.
- Produces: `FightAction.is_applicable(state, game_data) -> bool` whose gates are exactly `{locations non-empty, inventory_free >= _MIN_FREE_SLOTS, hp_percent > _MIN_FIGHT_HP_FRACTION, monster_level <= state.level + 2, xp_per_kill > 0}`. No equipped-item-level term.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ai/test_no_combat_deadlock.py`, reusing that file's existing `WorldState`/`GameData` construction helpers (mirror the nearest existing fixture). The scenario: char level 3, all equipped gear level 1, target monster level 4 that grants XP and has a spawn.

```python
def test_fight_applicable_when_winnable_despite_low_gear_level():
    """Regression: a level-3 char in all level-1 gear must be able to fight a
    winnable level-4 monster (green_slime). The old `best_eq >= monster_level-1`
    gate rejected it, deadlocking GrindCharacterXP -> plan_len=0."""
    state = _make_state(level=3, hp=160, max_hp=160, inventory_free=60,
                        equipment={"weapon_slot": "copper_dagger"})  # copper_dagger is level 1
    game_data = _make_game_data(
        monster={"code": "green_slime", "level": 4},
        xp_per_kill=30, locations={(0, -1)})
    fight = FightAction(monster_code="green_slime", locations=frozenset({(0, -1)}))
    assert fight.is_applicable(state, game_data) is True
```

(If the file already has factory helpers under different names, use those; the assertion and the level-3-gear-1-vs-monster-4 shape are what matters.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_no_combat_deadlock.py::test_fight_applicable_when_winnable_despite_low_gear_level -v`
Expected: FAIL — `assert False is True` (the `best_eq 1 >= 3` gate returns False).

- [ ] **Step 3: Remove the gate**

In `src/artifactsmmo_cli/ai/actions/combat.py`, replace the tail of `is_applicable` (the `best_eq` computation and `return best_eq >= monster_level - 1`, currently lines ~66-77) so the method ends:

```python
    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if not self.locations or state.inventory_free < self._MIN_FREE_SLOTS:
            return False
        monster_level = game_data.monster_level(self.monster_code)
        if not (state.hp_percent > _MIN_FIGHT_HP_FRACTION and monster_level <= state.level + 2):
            return False
        # Capability is decided upstream by is_winnable (predict_win); this gate
        # stays structural. The XP curve zeroes out at char_level - monster_level
        # >= 10, so xp_per_kill > 0 is the leveling-relevant lower bound. The old
        # `best_eq >= monster_level - 1` term conflated GEAR LEVEL with capability
        # and contradicted is_winnable (deadlock 2026-06-29: L3 char, level-1 gear,
        # winnable green_slime L4 rejected). Removed; suicide upper bound kept above.
        return game_data.xp_per_kill(self.monster_code, state.level) > 0
```

- [ ] **Step 4: Run the test (and the file) to verify pass + no regression**

Run: `uv run pytest tests/test_ai/test_no_combat_deadlock.py -v`
Expected: PASS, including the existing P0-deadlock tests in that file.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/combat.py tests/test_ai/test_no_combat_deadlock.py
git commit -m "fix(combat): drop best_eq gear gate from FightAction.is_applicable

Capability is is_winnable's job (upstream); the equipped-item-level gate
contradicted it, rejecting winnable green_slime (L4) for a level-1-geared
L3 char -> GrindCharacterXP plan_len=0 -> shield-craft fallthrough.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Decouple `GrindCharacterXPGoal.is_satisfied` from loadout-optimality (Python)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/grind_character_xp.py` (`is_satisfied` line 81-82; delete `_loadout_optimal` lines 46-54; remove now-unused imports `pick_loadout`, `Combat` lines 13,15; drop the `game_data` constructor param + `self._game_data` if unused after removal)
- Test: `tests/test_ai/test_grind_character_xp.py`

**Interfaces:**
- Consumes: `GrindCharacterXPGoal(target_monster, initial_xp)`.
- Produces: `is_satisfied(state) -> bool == state.xp > self._initial_xp`. Loadout optimization remains a *cost* signal (`FightAction.cost` `LOADOUT_PENALTY`) + optional `OptimizeLoadoutAction`, never a satisfaction gate.

- [ ] **Step 1: Write the failing test**

```python
def test_grind_satisfied_on_xp_gain_even_if_loadout_suboptimal():
    """Satisfaction = XP gained. A non-optimal loadout (copper_dagger equipped
    while wooden_staff scores higher vs green_slime) must NOT keep the goal
    perpetually unsatisfied (the fb929887 coupling deadlock)."""
    goal = GrindCharacterXPGoal("green_slime", initial_xp=14)
    state = _make_state(level=3, xp=24, equipment={"weapon_slot": "copper_dagger"})
    assert goal.is_satisfied(state) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_grind_character_xp.py::test_grind_satisfied_on_xp_gain_even_if_loadout_suboptimal -v`
Expected: FAIL — either `is_satisfied` returns False (loadout not optimal) or `__init__` no longer accepts the call once edited; if it currently requires `game_data`, the test calls the post-edit 2-arg form so it fails until Step 3.

- [ ] **Step 3: Edit the goal**

In `grind_character_xp.py`:
- Change `is_satisfied`:
```python
    def is_satisfied(self, state: WorldState) -> bool:
        return state.xp > self._initial_xp
```
- Delete the `_loadout_optimal` method (lines 46-54).
- Delete now-unused imports: `from artifactsmmo_cli.ai.equipment.loadout_picker import pick_loadout` and `from artifactsmmo_cli.ai.gear_value_core import Combat`.
- In `__init__`, drop the `game_data` parameter and `self._game_data` assignment **iff** no remaining method uses it (after removing `_loadout_optimal`, nothing does).

- [ ] **Step 4: Update constructor callers**

Run: `grep -rn "GrindCharacterXPGoal(" src/ tests/`
For each call site passing `game_data=...` (e.g. `objective_step_goal` / the goal factory), remove that argument. Expected sites: the grind-goal construction in the strategy/objective step layer. Edit each to the 2-arg form `GrindCharacterXPGoal(target_monster, initial_xp)`.

- [ ] **Step 5: Run grind tests + lint**

Run: `uv run pytest tests/test_ai/test_grind_character_xp.py -v && uv run ruff check src/artifactsmmo_cli/ai/goals/grind_character_xp.py`
Expected: PASS, no unused-import or unused-arg warnings.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/grind_character_xp.py tests/test_ai/test_grind_character_xp.py
# plus any caller files touched in Step 4
git commit -m "fix(grind): satisfy GrindCharacterXP on XP gain, not loadout-optimality

_loadout_optimal in is_satisfied (fb929887) + the pick_loadout refactor made
satisfaction require a weapon swap the planner was never directed to make.
Loadout opt stays a cost signal (LOADOUT_PENALTY), not a satisfaction gate.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Lean lockstep — remove `gearMeetsMonster`, add `winnable ⇒ applicable` lemma (Formal)

**Files:**
- Modify: `formal/Formal/ActionApplicability.lean` (`gearMeetsMonster` def ~64-66; `FightInputs.bestEqLevel` field ~80; the `&& gearMeetsMonster ...` conjunct in `fightApplicable` ~93; any `fightApplicable_false_of_*` theorem keyed to the gear gate)
- Modify: `formal/Formal/Liveness/FightProgress.lean`, `formal/Formal/Liveness/ProgressAction.lean` (remove `bestEqLevel` hypotheses / usages exposed by the def change)
- Modify: diff tests referencing the gate — `formal/diff/test_plan_exists_diff.py`, `formal/diff/test_liveness_chain.py` (and any `test_action_applicability*`), plus `formal/diff/test_combat_picker_diff.py` consistency expectations

**Interfaces:**
- Consumes: `pickWinnableWindowed` (`CombatTargetExistence.lean`), the post-edit `fightApplicable`.
- Produces: `fightApplicable : FightInputs → Bool` as a 5-way conjunction (no `gearMeetsMonster`); a theorem `winnable_inWindow_imp_fightApplicable` (capability+window ⇒ applicable, with HP/inventory/spawn as hypotheses) for sub-project 3 to consume.

> **Use the lean4 skills for the proof bodies.** Definitional edits are written below; proof repair is iterative against the compiler — invoke `lean4:prove` / `lean4:proof-repair` and `lean_goal`/`lean_diagnostic_messages`, do not hand-wave proof terms. The differential gate (Task 4) is the ground truth that Lean still matches Python.

- [ ] **Step 1: Edit the model definitions**

In `ActionApplicability.lean`:
- Delete `def gearMeetsMonster ...` (lines ~63-66) and its doc-comment.
- Remove the `bestEqLevel : Int` field from `structure FightInputs` (~80).
- Remove `&& gearMeetsMonster i.bestEqLevel i.monsterLevel` from `fightApplicable` (~93).
- Delete any `theorem fightApplicable_false_of_<gear>` and any lemma whose statement mentions `gearMeetsMonster`/`bestEqLevel`.

- [ ] **Step 2: Build; repair fallout**

Run: `( cd formal && lake build )`
Expected first run: errors in `FightProgress.lean` / `ProgressAction.lean` / any diff harness referencing `bestEqLevel`. Repair each: drop the now-vacuous gear hypothesis from the liveness lemmas (a liveness step that previously assumed `gearMeetsMonster` now needs one fewer hypothesis — strictly weaker, so the consumers simplify). Iterate with `lean4:proof-repair` until `lake build` is clean.

- [ ] **Step 3: Add the consistency lemma**

In `ActionApplicability.lean` (or a small dedicated file if it keeps responsibilities clean), state and prove:

```
/-- Capability ⇒ structural applicability: if the picker may return `m`
(winnable and within `[max(1,lvl-1), lvl+2]`) and the transient/spawn
preconditions hold, then `fightApplicable` is true. The "fight never
deadlocks given a winnable in-window target" seam for the L50 proof. -/
theorem winnable_inWindow_imp_fightApplicable
    (i : FightInputs)
    (hLoc : i.hasLocations = true)
    (hInv : hasInventoryRoom i = true)
    (hHp  : i.hpOk = true)
    (hWin : i.monsterLevel ≤ i.playerLevel + 2)
    (hXp  : xpPositive i = true) :
    fightApplicable i = true := by
  ...  -- discharge with the lean4 tools; conjunction of the 5 surviving gates
```

(Field/predicate names must match the post-edit `fightApplicable`; adjust to the actual definitions.)

- [ ] **Step 4: Verify build + no new axioms/sorry**

Run: `( cd formal && lake build && ./gate/check_no_sorry.sh && ./gate/check_axioms.sh )`
Expected: clean build, no `sorry`, no new axioms (the change only *removes* a conjunct and adds a constructive lemma — axiom budget must not grow).

- [ ] **Step 5: Commit**

```bash
git add formal/Formal/ActionApplicability.lean formal/Formal/Liveness/FightProgress.lean formal/Formal/Liveness/ProgressAction.lean
git commit -m "formal(combat): drop gearMeetsMonster from fightApplicable; add winnable=>applicable

Lockstep with Python is_applicable. Adds the capability=>applicable
consistency lemma (fight-never-deadlocks seam for the L50 liveness proof).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Differential + mutation + picker-consistency property + full gate green

**Files:**
- Modify/create: `formal/diff/test_combat_picker_diff.py` (or a new `formal/diff/test_fight_applicability_consistency.py`) — picker ⊆ applicable property
- Touch: regenerate anchors for `formal/diff/` tests affected by the `fightApplicable` arity change

**Interfaces:**
- Consumes: post-edit Python `FightAction.is_applicable`, `pick_winnable_monster_pure`; post-edit Lean `fightApplicable`.
- Produces: a property test asserting every picker output is `is_applicable`; a passing full `formal/gate.sh`.

- [ ] **Step 1: Write the consistency property test**

```python
def test_every_picker_target_is_applicable():
    """Picker ⟷ applicability invariant: any monster the XP-grind picker can
    return is FightAction.is_applicable (capability gates only; HP/inv/spawn
    held true in the fixture)."""
    # Build a small catalog spanning levels 1..(char_level+2); fixture with
    # full HP, free inventory, and a spawn for each. For each char_level in 1..10:
    #   target = pick_winnable_monster_pure(char_level, catalog, is_winnable, xp_positive)
    #   if target is not None:
    #       assert FightAction(target, locations=...).is_applicable(state, game_data)
    ...
```
(Fill with the concrete catalog/fixture mirroring `tests/test_ai/test_no_combat_deadlock.py`; the assertion is the contract.)

- [ ] **Step 2: Run the property test**

Run: `uv run pytest tests/test_ai/test_no_combat_deadlock.py -k consistency -v` (or the file you placed it in)
Expected: PASS.

- [ ] **Step 3: Run the differential gate**

Run: `export PATH="$HOME/.local/bin:$PATH"; ( cd formal && lake build oracle ); uv run pytest formal/diff/ -q --no-cov -n auto --ignore=formal/diff/test_game_data_fixture_diff.py`
Expected: PASS. If an anchor diff fails purely on the removed `bestEqLevel` input, update that diff harness to the new `FightInputs` shape (it should no longer supply `bestEqLevel`).

- [ ] **Step 4: Run the mutation gate**

Run: `uv run python formal/diff/mutate.py`
Expected: all mutants killed. Confirm specifically that a mutant **re-introducing** `best_eq >= monster_level - 1` (or re-adding the conjunct in Lean) is KILLED by the new tests; if it survives, strengthen the Task-1 test until it dies.

- [ ] **Step 5: Full gate + coverage**

Run: `export PATH="$HOME/.local/bin:$PATH"; ./formal/gate.sh && uv run pytest -q`
Expected: gate green; suite 0 errors / 0 warnings / 0 skipped / 100% coverage.

- [ ] **Step 6: Live confirmation**

Run: `uv run artifactsmmo plan Robby --learn`
Expected: `selected_goal` is now `GrindCharacterXP(green_slime)` (or a Fight-bearing plan), NOT `GatherMaterials(wooden_shield, ...)`; `goals_tried` shows `GrindCharacterXP(green_slime)` with `plan_len > 0`.

- [ ] **Step 7: Commit**

```bash
git add tests/ formal/diff/
git commit -m "test(combat): picker⟷applicability consistency property + mutation lock

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

- **Spec coverage:** Component 1 → Task 1; Component 2 (picker alignment audit) → Task 4 Step 1 property test; Component 3 (Lean lockstep + lemma) → Task 3; Component 4 (decouple is_satisfied) → Task 2. Testing section → Tasks 1,2,4. ✓
- **Spec correction:** the spec's Component-3 "if the gate is absent from Lean / why did diff miss it" branch is **moot** — `gearMeetsMonster` is present in `ActionApplicability.lean` and consumed by `FightProgress`/`ProgressAction`; Task 3 handles the present-case removal + liveness fallout. (Update the spec's Component-3 wording to drop the conditional.)
- **Placeholder scan:** the two `...` test bodies (Task 4 Step 1, and fixture reuse in Task 1/2) are deliberate references to existing fixture helpers in `tests/test_ai/test_no_combat_deadlock.py`; assertions + scenario values are concrete. Lean proof bodies are intentionally compiler-iterated via lean4 skills (pre-writing them blind would be fabrication).
- **Type consistency:** `is_satisfied(state)` is 1-arg throughout; `GrindCharacterXPGoal(target_monster, initial_xp)` 2-arg post-Task-2 everywhere; `fightApplicable` loses `bestEqLevel` consistently in Tasks 3 & 4.

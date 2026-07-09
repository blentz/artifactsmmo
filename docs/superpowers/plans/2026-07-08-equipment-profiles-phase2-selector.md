# Equipment Profiles — Phase 2: Profile Selector

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the pure profile selector — `is_utility_objective(root)` and `profile_for(root, band_adequate)` — with the plan-gate combat floor baked in, proven total + plan-gate-invariant in Lean, and mutation/differential-bound, all UNWIRED (no consumer changes). Spec: `docs/superpowers/specs/2026-07-08-equipment-profiles-design.md` §2.

**Architecture:** The tree's `chosen_root` is exactly one of three `MetaGoal` types — `ReachCharLevel` (char_level), `ReachSkillLevel` (skills), `ObtainItem` (gear) — mapped by `root_category` (strategy.py:25). Only `skills` is a utility objective. The selector adds two pure functions to `equipment_profile.py` (Phase 1's module): `is_utility_objective` (true iff `ReachSkillLevel`) and `profile_for` (plan-gate: `¬band_adequate → COMBAT`; else UTILITY iff utility objective). A Lean model proves totality + the plan-gate invariant; a differential arm binds the Python function.

**Tech Stack:** Python 3.13 (`uv`), pytest, Lean 4 + lake, formal/diff mutation gate.

## Global Constraints (spec + repo rules)

- UNWIRED phase: no consumer changes. `decide_tree`, `near_term_gear`, the player — all untouched. Adding two pure functions + tests + Lean + a mutation arm only.
- Selector semantics VERBATIM from spec §2:
  `profile_for(root, band_adequate)`: `if not band_adequate: return COMBAT` (plan-gate); `if is_utility_objective(root): return UTILITY`; `return COMBAT`.
  `is_utility_objective(root)`: true iff the root is a `ReachSkillLevel` (root_category "skills"); `ReachCharLevel`/`ObtainItem` → false.
- The plan-gate floor is the invariant `¬band_adequate ⇒ profile = COMBAT` — must be proven, not just tested.
- DRY guard: `is_utility_objective` mirrors `root_category`'s taxonomy; a test must assert consistency with `root_category` across all three root types so the two can't drift.
- **Phase-3 obligation (record, do not build here):** `profile_for` is fed a `chosen_root`, but the tree's `chosen_root` emerges FROM the profile-scored candidates — feeding the in-flight root back in would be circular. Phase 3 resolves this by feeding the selector the ENACTED/committed objective (prior cycle or arbiter commitment), computed player-side and passed into `decide_tree` alongside `band_adequate`. Phase 2 builds the pure function only; the circularity resolution is Phase 3's.
- Exact/total; no inline imports; never catch Exception; TDD; 100% coverage; mypy strict.
- Never run gate.sh/mutate.py while the bot is running.

---

### Task 1: `is_utility_objective` + `profile_for` (pure Python)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/equipment_profile.py`
- Test: `tests/test_ai/test_equipment_profile.py` (extend)

**Interfaces:**
- Consumes: Phase 1's `ProfileKind` (same module); `ReachSkillLevel`, `ReachCharLevel`, `ObtainItem`, `MetaGoal` (`tiers/meta_goal.py`); `root_category` (`tiers/strategy.py`) — TEST-ONLY import for the drift guard, NOT imported by the module (cycle risk).
- Produces (Phase 3 consumes):
  - `is_utility_objective(root: MetaGoal) -> bool` — true iff `isinstance(root, ReachSkillLevel)`.
  - `profile_for(root: MetaGoal, band_adequate: bool) -> ProfileKind`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_ai/test_equipment_profile.py
from artifactsmmo_cli.ai.tiers.equipment_profile import (
    is_utility_objective,
    profile_for,
)
from artifactsmmo_cli.ai.tiers.meta_goal import (
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.strategy import root_category


_SKILL = ReachSkillLevel(skill="weaponcrafting", level=10)
_XP = ReachCharLevel(level=20)
_GEAR = ObtainItem(code="fire_bow", quantity=1, slot="weapon_slot")


class TestIsUtilityObjective:
    def test_skills_is_utility(self):
        assert is_utility_objective(_SKILL) is True

    def test_char_level_and_gear_are_not_utility(self):
        assert is_utility_objective(_XP) is False
        assert is_utility_objective(_GEAR) is False

    def test_taxonomy_tracks_root_category(self):
        """Drift guard: is_utility_objective must agree with root_category's
        'skills' bucket across every tree root type — if root_category gains
        a category, this catches the profile taxonomy going stale."""
        for root in (_SKILL, _XP, _GEAR):
            assert is_utility_objective(root) == (root_category(root) == "skills")


class TestProfileFor:
    def test_plan_gate_forces_combat_when_inadequate(self):
        # ¬band_adequate ⇒ COMBAT, for EVERY root type (the floor):
        for root in (_SKILL, _XP, _GEAR):
            assert profile_for(root, band_adequate=False) is ProfileKind.COMBAT

    def test_utility_objective_when_adequate_is_utility(self):
        assert profile_for(_SKILL, band_adequate=True) is ProfileKind.UTILITY

    def test_combat_objective_when_adequate_is_combat(self):
        assert profile_for(_XP, band_adequate=True) is ProfileKind.COMBAT
        assert profile_for(_GEAR, band_adequate=True) is ProfileKind.COMBAT
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_equipment_profile.py -q --no-cov -k "UtilityObjective or ProfileFor"`
Expected: FAIL — `ImportError: cannot import name 'is_utility_objective'`

- [ ] **Step 3: Implement**

```python
# add to equipment_profile.py (imports at top-of-file, with the others)
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal, ReachSkillLevel

def is_utility_objective(root: MetaGoal) -> bool:
    """True iff pursuing `root` is a UTILITY-axis objective — a craft/gather
    skill level (`ReachSkillLevel`, root_category 'skills'). Character-level
    (xp grind) and gear (`ObtainItem`) pursuits are COMBAT-axis: the item's
    own combat/utility nature is decided by the scorer, not the selector.
    Mirrors `tiers.strategy.root_category`'s 'skills' bucket (drift-guarded
    by test); kept as a local isinstance to avoid importing heavy strategy.py
    into this pure module."""
    return isinstance(root, ReachSkillLevel)


def profile_for(root: MetaGoal, band_adequate: bool) -> ProfileKind:
    """The active equipment profile for pursuing `root`. Plan-gate combat
    floor: while the band is combat-INADEQUATE the profile is forced COMBAT
    (never chase utility gear when we can't win); once adequate, a utility
    objective selects UTILITY, everything else COMBAT. Pure/total — the
    single tuning surface for the combat/utility axis (spec §2)."""
    if not band_adequate:
        return ProfileKind.COMBAT
    if is_utility_objective(root):
        return ProfileKind.UTILITY
    return ProfileKind.COMBAT
```

NOTE to implementer: verify `MetaGoal`/`ReachSkillLevel` import from
`tiers/meta_goal.py` does not create a cycle with `equipment_profile.py`'s
existing imports (`strategic_value`, `game_data`). `meta_goal.py` is pure
frozen dataclasses/Protocol — no cycle expected. If mypy flags `MetaGoal`
as a `Protocol` isinstance issue, use the concrete-type union or
`runtime_checkable` per how `root_category` (strategy.py:25) does its
isinstance checks — mirror that exact pattern.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_equipment_profile.py -q --no-cov`
Expected: PASS (all — Phase 1 tests + the new selector tests).

- [ ] **Step 5: Full suite, commit**

Run: `uv run pytest -q` — all pass, 100% coverage. (If the pre-commit
full-suite hook times out, commit `--no-verify` after `uv run mypy
src/artifactsmmo_cli/ai/tiers/equipment_profile.py` clean + the targeted
file green, and note it in the report.)

```bash
git add src/artifactsmmo_cli/ai/tiers/equipment_profile.py tests/test_ai/test_equipment_profile.py
git commit -m "feat(profiles): profile_for selector + is_utility_objective (plan-gate floor)"
```

---

### Task 2: Lean model — totality + plan-gate invariant

**Files:**
- Create: `formal/Formal/EquipmentProfile.lean`
- Modify: `formal/Formal.lean` (register the import — mirror how `Formal.ProgressionTree` is registered)
- Run: `uv run python scripts/gen_proof_concept_index.py` (new module → index update)

**Interfaces:**
- Mirrors Task 1's semantics: a `RootCategory` inductive (`charLevel | skills | gear`), `ProfileKind` (`combat | utility`), `isUtilityObjective`, `profileFor`.

- [ ] **Step 1: Write the Lean module (proof-first; `lake build` is the test)**

```lean
/- Formal/EquipmentProfile.lean
   Mirrors src/artifactsmmo_cli/ai/tiers/equipment_profile.py's selector
   (spec docs/superpowers/specs/2026-07-08-equipment-profiles-design.md §2).
   Bound to the Python selector by the EQUIPMENT_PROFILE_MUTATIONS group
   (formal/diff/mutate.py). -/
namespace Formal.EquipmentProfile

inductive RootCategory | charLevel | skills | gear
deriving DecidableEq, Repr

inductive ProfileKind | combat | utility
deriving DecidableEq, Repr

def isUtilityObjective : RootCategory → Bool
  | .skills => true
  | .charLevel => false
  | .gear => false

def profileFor (cat : RootCategory) (bandAdequate : Bool) : ProfileKind :=
  if !bandAdequate then .combat
  else if isUtilityObjective cat then .utility
  else .combat

/-- PLAN-GATE INVARIANT: combat-inadequate ⇒ COMBAT, for every root
category. This is the combat floor the whole design rests on. -/
theorem planGate_forces_combat (cat : RootCategory) :
    profileFor cat false = .combat := by
  cases cat <;> rfl

/-- Utility is chosen ONLY when adequate AND the objective is utility. -/
theorem utility_iff (cat : RootCategory) (adequate : Bool) :
    profileFor cat adequate = .utility ↔
      (adequate = true ∧ isUtilityObjective cat = true) := by
  cases adequate <;> cases cat <;> simp [profileFor, isUtilityObjective]

/-- Totality is structural (profileFor is a total function over the finite
enum product); this example pins every one of the 6 cases explicitly so a
future edit that broke a case fails the build. -/
example :
    profileFor .skills true = .utility ∧
    profileFor .charLevel true = .combat ∧
    profileFor .gear true = .combat ∧
    profileFor .skills false = .combat ∧
    profileFor .charLevel false = .combat ∧
    profileFor .gear false = .combat := by
  decide

end Formal.EquipmentProfile
```

- [ ] **Step 2: Register + build**

Add `import Formal.EquipmentProfile` where sibling modules are registered
(grep `Formal.ProgressionTree` in `formal/Formal.lean`), then:

Run: `cd formal && lake build 2>&1 | tail -2`
Expected: build succeeds, no errors, no `sorry` (check `grep -n "sorry\|admit" formal/Formal/EquipmentProfile.lean` → none; and no bare `admit`/`sorry` identifiers — none here).

- [ ] **Step 3: Index + commit**

Run: `uv run python scripts/gen_proof_concept_index.py` (regenerates the module index for the new file).

```bash
git add formal/Formal/EquipmentProfile.lean formal/Formal.lean docs/behavioral_completeness/PROOF_CONCEPT_INDEX.md
git commit -m "feat(formal): EquipmentProfile.lean — profileFor totality + plan-gate invariant"
```

---

### Task 3: Differential + mutation arm; wrap-up

**Files:**
- Create: `formal/diff/test_equipment_profile_diff.py`
- Modify: `formal/diff/mutate.py` (new `EQUIPMENT_PROFILE_MUTATIONS` group + `run_group` + `_ALL_SRCS` entry)
- Modify: spec Phases section ("Phase 2 SHIPPED")

**Interfaces:** binds Python `profile_for` (imported from `src`) to the Lean `profileFor` semantics.

- [ ] **Step 1: Differential harness** — enumerate the 6 (category × adequacy) cases; for each build the matching Python `MetaGoal` (`ReachSkillLevel`/`ReachCharLevel`/`ObtainItem`) + bool, call `profile_for`, and assert it equals the Lean truth table (COMBAT unless adequate∧skills). Mirror the shape of `formal/diff/test_progression_tree*`-style harnesses if one exists; else a plain parametrized pytest over the 6 cases asserting the exact `ProfileKind`. The harness is the lockstep — it must import the REAL `profile_for` from `src`, not reimplement it.

```python
# formal/diff/test_equipment_profile_diff.py
"""Differential lockstep: Python profile_for ↔ Lean profileFor (the 6
category×adequacy cases). Binds the real src selector."""

import pytest

from artifactsmmo_cli.ai.tiers.equipment_profile import ProfileKind, profile_for
from artifactsmmo_cli.ai.tiers.meta_goal import (
    ObtainItem, ReachCharLevel, ReachSkillLevel,
)

_SKILL = ReachSkillLevel(skill="weaponcrafting", level=10)
_XP = ReachCharLevel(level=20)
_GEAR = ObtainItem(code="fire_bow", quantity=1, slot="weapon_slot")

# (root, band_adequate) -> expected, matching Lean profileFor exactly.
_CASES = [
    (_SKILL, True, ProfileKind.UTILITY),
    (_XP, True, ProfileKind.COMBAT),
    (_GEAR, True, ProfileKind.COMBAT),
    (_SKILL, False, ProfileKind.COMBAT),
    (_XP, False, ProfileKind.COMBAT),
    (_GEAR, False, ProfileKind.COMBAT),
]


@pytest.mark.parametrize("root, adequate, expected", _CASES)
def test_profile_for_matches_lean(root, adequate, expected):
    assert profile_for(root, adequate) is expected
```

- [ ] **Step 2: Mutation group** — add to `formal/diff/mutate.py`, anchored to EXACT source strings copied from `equipment_profile.py` (never retyped), bound to the DIFFERENTIAL harness (or the unit test file — mirror how a sibling pure-core group binds). At least these mutants, each individually kill-checked (apply → harness fails → revert):

```python
EQUIPMENT_PROFILE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "equipment_profile.py"

EQUIPMENT_PROFILE_MUTATIONS = [
    ("profiles: plan-gate dropped (utility even when inadequate)",
     "    if not band_adequate:\n        return ProfileKind.COMBAT",
     "    if False:\n        return ProfileKind.COMBAT"),
    ("profiles: utility objective inverted",
     "    return isinstance(root, ReachSkillLevel)",
     "    return not isinstance(root, ReachSkillLevel)"),
    ("profiles: utility branch forced combat (utility never fires)",
     "    if is_utility_objective(root):\n        return ProfileKind.UTILITY",
     "    if is_utility_objective(root):\n        return ProfileKind.COMBAT"),
]
```

Add `EQUIPMENT_PROFILE_SRC` to `_ALL_SRCS` and a `run_group(EQUIPMENT_PROFILE_SRC, EQUIPMENT_PROFILE_MUTATIONS, "formal/diff/test_equipment_profile_diff.py", survivors)` call beside the sibling groups. Kill-check each of the 3 mutants manually (apply via textual replace, run the harness expecting failure, reverse — never `git checkout`). Static anchor sweep after: every group's `old` string present in source.

- [ ] **Step 3:** Full suite + `uv run pytest formal/diff/test_equipment_profile_diff.py -q --no-cov` green; mypy strict.
- [ ] **Step 4:** IF bot down (`ps aux | grep "[a]rtifactsmmo play"` empty): `./formal/gate.sh`. If live: record debt.
- [ ] **Step 5:** Append to spec Phases: `**Phase 2 SHIPPED**: profile_for + is_utility_objective (plan-gate floor); Lean profileFor totality + planGate_forces_combat + utility_iff; differential + 3 kill-checked mutants. Unwired. Phase-3 obligation recorded: feed the selector the ENACTED root (not the in-flight one) to avoid circularity.` Commit docs + mutate.py.

```bash
git add formal/diff/test_equipment_profile_diff.py formal/diff/mutate.py docs/superpowers/specs/2026-07-08-equipment-profiles-design.md
git commit -m "feat(gate): EQUIPMENT_PROFILE_MUTATIONS + differential lockstep; Phase 2 shipped"
```

---

## Later phases (already outlined in the Phase 1 plan)

- **Phase 3 — pursuit wiring** (behavior change): thread `ProfileKind` into `near_term_gear`/`_structural_candidates`/`_item_value` via `score_for_profile`; **pin `has_structural_upgrade` to COMBAT (no-circularity)**; RESOLVE the selector-input circularity by feeding `profile_for` the enacted/committed objective player-side; profile scenario net.
- **Phase 4 — equip-gate** (MANDATORY per Phase-1 final review — the UTILITY floor is thresholded, not absolute): winnability swap at the loadout-fielding site.
- **Phase 5 — flip + tune**: calibrate `PROFILE_WEIGHTS[UTILITY]` on live shadow.

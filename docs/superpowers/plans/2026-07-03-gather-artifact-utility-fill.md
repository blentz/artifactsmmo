# Gather-purpose Artifact Utility Fill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `pick_loadout(Gather)` fill an empty artifact slot with an owned utility artifact (e.g. `novice_guide`), so the free +HP/+wisdom/+prospecting equips during gather/skill plans instead of only as a combat prelude.

**Architecture:** One production edit in `equipment/loadout_picker._benefit`: under a Gather purpose, artifact-type candidates score by the flat-utility term `armor_score(stats, {})` (bit-identical to the Lean model's per-item `flatUtil`) instead of the always-zero `-gather_score`. Combat/Rank paths and all non-artifact Gather behavior are byte-unchanged. The formal lockstep threads a per-item `isUtilityFill` flag through the Lean picker model + oracle so the differential binds the new benefit, plus a mutation-killing unit test.

**Tech Stack:** Python 3.13 (`uv run`), pytest + hypothesis, Lean 4 (`lake`), the `formal/` differential + mutation gate.

## Global Constraints

- ALWAYS prefix Python commands with `uv run` (e.g. `uv run pytest`, `uv run mypy`).
- Imports at top of file only — no inline imports, no `...`/relative imports, no `if TYPE_CHECKING`.
- One behavioral class per file (not triggered here — edits are function-level).
- NEVER catch `Exception`. No multi-level error handling.
- Tests live under `tests/`. Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- `formal/gate.sh` and `formal/mutate.py` must run SERIALIZED — never concurrent with anything importing `src` (including a running bot).
- Use only API data or fail with an error — no defaulting.

---

### Task 1: Production — Gather-purpose artifact flat-utility benefit + unit tests

**Files:**
- Modify: `src/artifactsmmo_cli/ai/equipment/loadout_picker.py` (imports; `_benefit`, currently lines 59-75)
- Test: `tests/ai/test_loadout_picker_purpose.py`

**Interfaces:**
- Consumes: `armor_score(stats: ItemStats, monster_attack: dict[str, int]) -> int` from `artifactsmmo_cli.ai.equipment.scoring`; `Gather` from `artifactsmmo_cli.ai.gear_value_core` (already imported at loadout_picker.py:13).
- Produces: unchanged public signature `pick_loadout(purpose, state, game_data) -> dict[str, str | None]` and `_benefit(stats, purpose) -> int`. New module constants `_UTILITY_FILL_TYPES: frozenset[str]`, `_NO_MONSTER: dict[str, int]`.

- [ ] **Step 1: Write the failing unit tests**

Add this fixture and four tests to `tests/ai/test_loadout_picker_purpose.py`. `armor_score` is already imported at the top of that file (line 9); `Combat`/`Gather` at line 11.

```python
def _gd_gather_artifact() -> GameData:
    """Gather fixture with a tool, armor, and two utility artifacts."""
    gd = GameData()
    gd._item_stats = {
        "strong_axe": ItemStats(code="strong_axe", level=1, type_="weapon", subtype="tool",
                                attack={"earth": 3}, skill_effects={"woodcutting": -10}),
        "leather_armor": ItemStats(code="leather_armor", level=1, type_="body_armor",
                                   resistance={"earth": 10}),
        "novice_guide": ItemStats(code="novice_guide", level=1, type_="artifact",
                                  hp_bonus=25, wisdom=25, prospecting=25),
        "lucky_charm": ItemStats(code="lucky_charm", level=1, type_="artifact",
                                 wisdom=10, prospecting=10),
    }
    return gd


def test_gather_fills_empty_artifact_slot() -> None:
    """MUTATION KILLER: a gather re-arm fills an empty artifact slot with an owned
    utility artifact. novice_guide flat utility = hp_bonus 25 + wisdom 25 +
    prospecting 25 = 75 > 0, so the empty-slot gate passes. The mutant that
    reverts the artifact branch to -gather_score (0) leaves the slot empty."""
    gd = _gd_gather_artifact()
    assert armor_score(gd._item_stats["novice_guide"], {}) == 75
    state = _make_state(level=1, inventory={"novice_guide": 1},
                        equipment={"artifact1_slot": None})
    result = pick_loadout(Gather("woodcutting"), state, gd)
    assert result["artifact1_slot"] == "novice_guide"


def test_gather_picks_best_utility_artifact() -> None:
    """Under Gather, artifacts argmax on flat utility (not an arbitrary 0-0 tie):
    novice_guide (75) takes the first artifact slot, lucky_charm (20) the next."""
    gd = _gd_gather_artifact()
    state = _make_state(level=1, inventory={"novice_guide": 1, "lucky_charm": 1},
                        equipment={"artifact1_slot": None, "artifact2_slot": None})
    result = pick_loadout(Gather("woodcutting"), state, gd)
    assert result["artifact1_slot"] == "novice_guide"
    assert result["artifact2_slot"] == "lucky_charm"


def test_gather_artifact_branch_leaves_armor_empty() -> None:
    """The utility-fill branch is artifact-ONLY. Empty armor with owned hp-bonus
    armor (flat utility 30 > 0) still stays empty under Gather — armor is not a
    fill type, so it keeps the proven -gather_score (0) benefit."""
    gd = _gd_gather_artifact()
    gd._item_stats["padded_vest"] = ItemStats(code="padded_vest", level=1,
                                              type_="body_armor", hp_bonus=30)
    state = _make_state(level=1, inventory={"padded_vest": 1},
                        equipment={"body_armor_slot": None})
    result = pick_loadout(Gather("woodcutting"), state, gd)
    assert result["body_armor_slot"] is None


def test_combat_fills_empty_artifact_slot_unchanged() -> None:
    """Regression: Combat already fills artifacts (armor_score includes flat
    utility). The Gather-branch edit must not change the Combat path."""
    gd = _gd_gather_artifact()
    state = _make_state(level=1, inventory={"novice_guide": 1},
                        equipment={"artifact1_slot": None})
    result = pick_loadout(Combat({"earth": 0}, {"earth": 0}), state, gd)
    assert result["artifact1_slot"] == "novice_guide"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/ai/test_loadout_picker_purpose.py -k "artifact" -v`
Expected: `test_gather_fills_empty_artifact_slot`, `test_gather_picks_best_utility_artifact` FAIL (artifact slot is `None` — current `_benefit` returns 0 for artifacts under Gather → empty-slot gate skips). `test_gather_artifact_branch_leaves_armor_empty` and `test_combat_fills_empty_artifact_slot_unchanged` PASS (already-correct behavior).

- [ ] **Step 3: Add the imports and module constants**

In `src/artifactsmmo_cli/ai/equipment/loadout_picker.py`, add to the import block (after line 12, `from artifactsmmo_cli.ai.gear_value import gear_value`):

```python
from artifactsmmo_cli.ai.equipment.scoring import armor_score
```

Add these module-level constants immediately after the imports (before `_candidates_for_slot`):

```python
_UTILITY_FILL_TYPES: frozenset[str] = frozenset({"artifact"})
"""Item types whose value is purpose-independent flat utility (wisdom/prospecting/
hp). They carry no skill_effects, so the Gather scorer values them at 0 and the
empty-slot gate discards them — this set routes them through the flat-utility
term instead. NOT `utility` (consumable/potion slots handled elsewhere)."""

_NO_MONSTER: dict[str, int] = {}
"""Empty monster attack: armor_score's defense term Σ mon_atk·res collapses to 0,
leaving exactly the flat utility sum (bit-identical to the Lean model flatUtil)."""
```

- [ ] **Step 4: Rewrite `_benefit` body**

Replace the body of `_benefit` (loadout_picker.py, currently the two lines at 74-75, `value = gear_value(...)` / `return -value if ...`) with:

```python
    if isinstance(purpose, Gather):
        if stats.type_ in _UTILITY_FILL_TYPES:
            # Artifacts grant purpose-independent utility (wisdom/prospecting/hp)
            # and carry no skill_effects, so gear_value(Gather) = 0 and the
            # empty-slot gate discards them. Score by the flat-utility term:
            # armor_score against an empty monster attack zeroes the defense term,
            # leaving hp_bonus+wisdom+prospecting+inventory_space+haste+lifesteal+
            # combat_buff — bit-identical to the Lean model's per-item flatUtil,
            # and consistent with the Combat path (armor_score includes it too).
            return armor_score(stats, _NO_MONSTER)
        return -gear_value(stats, purpose)
    return gear_value(stats, purpose)
```

Keep the existing `_benefit` docstring; append one sentence noting the artifact/Gather flat-utility branch so the docstring matches the code.

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `uv run pytest tests/ai/test_loadout_picker_purpose.py -v`
Expected: all tests PASS (the pre-existing Combat/Gather regression tests and the four new ones).

- [ ] **Step 6: Verify the existing loadout-picker differential still passes**

The existing Gather differential generates only `type_="weapon"` items and asserts the weapon slot, so the production change must not perturb it.

Run: `uv run pytest formal/diff/test_loadout_picker_diff.py -q`
Expected: PASS (no artifacts exercised yet — the new binding lands in Task 2).

- [ ] **Step 7: Typecheck**

Run: `uv run mypy src/artifactsmmo_cli/ai/equipment/loadout_picker.py`
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add src/artifactsmmo_cli/ai/equipment/loadout_picker.py tests/ai/test_loadout_picker_purpose.py
git commit -m "feat(gear): fill empty artifact slot with owned utility artifact under Gather purpose"
```

---

### Task 2: Formal lockstep — bind the Gather-artifact benefit + mutation

**Files:**
- Modify: `formal/Formal/GearValue.lean` (`Item` structure; `purposeBenefit` at line 173-177; the gather-optimality theorem at line 239-263 as needed)
- Modify: `formal/Oracle.lean` (`itemFromBlock` at 238-242; `runLoadoutPicker` at 306-329 — per-item `isUtilityFill` int)
- Modify: `formal/diff/test_loadout_picker_diff.py` (add an artifact-slot Gather property test; `_item_block` at 88-102)
- Modify: `formal/mutate.py` (anchor refresh + artifact-branch mutant)

**Interfaces:**
- Consumes: production `_benefit(Gather, artifact) == armor_score(stats, {})` from Task 1; the model's per-item `flatUtil` (already `b 12` in `itemFromBlock`).
- Produces: model `Item.isUtilityFill : Bool`; `purposeBenefit (.gather e) i = if i.isUtilityFill then i.flatUtil else - gatherValue e i`; oracle `runLoadoutPicker` reads a per-item `isUtilityFill` int; a differential assertion binding live `armor_score(stats, {})` to oracle `flatUtil` for artifacts under Gather.

> This task authors Lean proof deltas via the compiler-guided workflow
> (invoke lean4:prove / superpowers:formal-development). Do NOT hand-copy
> speculative proof terms — the objective acceptance is a clean `lake build`
> and a green `formal/gate.sh`. The steps below fix the CONTRACT (definitions,
> encodings, assertions, mutant); the proof text is filled in against the
> compiler.

- [ ] **Step 1: Add the failing differential binding**

In `formal/diff/test_loadout_picker_diff.py`, add a Gather-purpose property test over the ARTIFACT slot (mirror `_oracle_pick`/`test_gather_pick_matches_lean` but for `artifact1_slot` and `type_="artifact"` items with random `hp_bonus`/`wisdom`/`prospecting`, no `skill_effects`). Assert the chosen artifact's live `armor_score(stats, {})` equals the oracle's returned benefit for the pick (bit-exact). Extend `_item_block` (line 88) to append a 15th int `is_utility_fill = 1 if stats and stats.type_ in {"artifact"} else 0`, and thread it into the oracle args in `_oracle_pick` and the artifact-slot request. Keep the weapon-slot `test_gather_pick_matches_lean` unchanged (its blocks gain a trailing `0`).

- [ ] **Step 2: Run the differential — expect failure**

Run: `uv run pytest formal/diff/test_loadout_picker_diff.py -q`
Expected: the new artifact test FAILS — the oracle's `purposeBenefit (.gather)` still returns `- gatherValue = 0` for artifacts while production returns the flat utility.

- [ ] **Step 3: Extend the Lean model (`formal/Formal/GearValue.lean`)**

Add `isUtilityFill : Bool := false` to the `Item` structure (default keeps every existing `Item` literal and `runEquipmentScoring` caller valid). Change `purposeBenefit` (line 173-177) `.gather` arm to:

```lean
  | .gather skillEffect => fun i =>
      if i.isUtilityFill then i.flatUtil else - gatherValue skillEffect i
```

Re-establish the affected optimality lemmas: `pickSlot_score_optimal_purpose`
(line 190) is generic over `purposeBenefit` and should still hold; the
gather-specific `pickSlot_purpose_gather_optimal` (line 239, phrased in terms of
`gatherValue`) now holds only for the non-utility-fill sub-case — restate its
hypothesis/conclusion in terms of `purposeBenefit (.gather …)` (the generic
benefit) or scope it to `¬ isUtilityFill` candidates. Drive to a clean build.

Run: `cd formal && lake build`
Expected: build succeeds, no `sorry`, no new axioms.

- [ ] **Step 4: Update the oracle encoding (`formal/Oracle.lean`)**

In `runLoadoutPicker` (line 306), read a per-item `isUtilityFill` int alongside
the existing `skillEffect` int: the current/candidate blocks become
`13-int item + skillEffect + isUtilityFill` (block stride 14 → 15). Build each
`Item` with `isUtilityFill := <that int> != 0` (extend `itemFromBlock` or set the
field at the call site). `runEquipmentScoring` keeps `isUtilityFill := false`
(default) — combat scoring is unaffected. Adjust the stride arithmetic
(`(args.size - 22) / 15`, offsets) to match the new per-item width used by the
diff test in Step 1.

Run: `cd formal && lake build`
Expected: build succeeds.

- [ ] **Step 5: Run the differential — expect pass**

Run: `uv run pytest formal/diff/test_loadout_picker_diff.py -q`
Expected: PASS — live `armor_score(stats, {})` for artifacts under Gather now equals the oracle `flatUtil` benefit, and the weapon-slot test still matches.

- [ ] **Step 6: Refresh mutation anchors and add the artifact-branch mutant**

Update `formal/mutate.py` anchors for the edited `_benefit` (line references
shifted). Add a mutant that reverts the artifact arm to `-gear_value(stats, purpose)`
(i.e. drops the `_UTILITY_FILL_TYPES` fast-path). Confirm it is KILLED by
`test_gather_fills_empty_artifact_slot` (Task 1) — the killing test is an owned
unit test bound to the branch, not only the traversal diff.

Run: `uv run python formal/mutate.py` (serialized; see Global Constraints)
Expected: 0 surviving mutants for the artifact branch.

- [ ] **Step 7: Run the full gate**

Run: `cd formal && ./gate.sh` (serialized — nothing else importing `src` running)
Expected: green — lake build, axiom lint, all differentials, mutation, coverage.

- [ ] **Step 8: Commit**

```bash
git add formal/Formal/GearValue.lean formal/Oracle.lean formal/diff/test_loadout_picker_diff.py formal/mutate.py
git commit -m "formal(gear): bind Gather-artifact flatUtil benefit; isUtilityFill model flag + mutation"
```

---

### Task 3: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the whole Python suite with coverage**

Run: `uv run pytest --cov=src --cov-report=term-missing -q`
Expected: 0 errors, 0 warnings, 0 skipped, 100% coverage. If the new `_benefit`
artifact branch shows an uncovered line, the Task 1 tests already exercise both
sides (artifact fill + armor-not-filled) — investigate any gap, do not add a
coverage-only test that asserts nothing.

- [ ] **Step 2: Typecheck the whole package**

Run: `uv run mypy src`
Expected: no errors.

- [ ] **Step 3: (Optional) Confirm runtime effect on Robby**

Run: `uv run artifactsmmo plan Robby`
Expected: when Robby's plan includes a gather (e.g. alchemy herb gathering), the
plan sequences an `OptimizeLoadout(Gather)` re-arm that equips `novice_guide`
(the `GATHER_LOADOUT_PENALTY` self-activation described in the spec). This is a
diagnostic observation, not a gating check.

---

## Self-Review

- **Spec coverage:** behavior change → Task 1; self-activation → verified in Task 3 Step 3; formal model+oracle+diff → Task 2 Steps 3-5; mutation → Task 2 Step 6; gate → Task 2 Step 7; scope guard (`artifact`-only, not `utility`) → `test_gather_artifact_branch_leaves_armor_empty` + `_UTILITY_FILL_TYPES`; tie-break upgrade → `test_gather_picks_best_utility_artifact`; residual gap (pure-craft) → documented in spec, out of scope. All covered.
- **Placeholders:** none — Python steps carry full code; the Lean task is contract-specified with exact file:line anchors and `lake build`/`gate.sh` acceptance (proof text is compiler-authored by design, not omitted detail).
- **Type consistency:** `_benefit(stats, purpose) -> int`, `armor_score(stats, dict) -> int`, `pick_loadout(...) -> dict[str, str | None]`, model `Item.isUtilityFill : Bool`, oracle per-item int `isUtilityFill` — consistent across tasks.

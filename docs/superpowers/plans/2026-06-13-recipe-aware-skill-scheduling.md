# Recipe-Aware Skill Scheduling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the AI proactively level crafting skills "along the way" — driven by a recipe-derived target curve — so gear recipes unlock just-in-time instead of forcing a catch-up skill grind that freezes character leveling.

**Architecture:** A formally-proven pure core `skill_curve_target_pure` computes, per crafting skill, the level to hold at the current character level (max craft-level over gear-relevant recipes whose item_level ≤ char_level + LOOKAHEAD, clamped). A thin impure wrapper hoists the recipe data from `game_data`; the strategy tier emits near-term `ReachSkillLevel` roots for below-curve skills and scores them gap-proportionally so they interleave with combat (small gap → combat leads; large gap → skill catches up).

**Tech Stack:** Python 3.13 (`uv run`), Lean 4 (`lake build`), Hypothesis differential tests, the project's `formal/` gate (kernel proofs + diff + mutation). Pure cores are mechanically extracted via `scripts/extract_lean.py`.

---

## Background the engineer needs

- **Pure core pattern:** A "pure core" is a Python function in the extraction subset (plain-data params, no I/O, no `WorldState`/`GameData`). `scripts/extract_lean.py` mechanically generates `formal/Formal/Extracted/<Name>.lean` from it. You ALSO hand-write a "hand model" Lean def (`formal/Formal/<Name>.lean`) with the correctness theorems, then a **bridge** proving the extracted def equals the hand def. See `src/artifactsmmo_cli/ai/equipment/scoring.py` + `formal/Formal/EquipmentScoring.lean` + `formal/Formal/Extracted/Bridges7.lean` as the closest reference (Int-returning, string-keyed, an injective-encoding bridge).
- **The gate** (`./formal/gate.sh`): (a) `lake build` all proofs, (b) axiom lint, (b') role manifest, (b'') proof-concept index, (b''') extraction drift (`extract_lean.py --check`), (c) mutation, (d) differential pytest. Run serially; NEVER run concurrently with the live bot (memory: poisoned-predicate hazard). After any gate/mutation run, `git diff src` to confirm no mutant was left in place.
- **Project rules:** `uv run` prefix always; imports at top of file; ONE behavioral class per file (pure-data dataclasses may share); never catch `Exception`; 0 errors / 0 warnings / 0 skipped / 100% coverage.
- **Mutation on a dirty tree:** `mutate.py` refuses to run when target src files are already modified. This branch has uncommitted work, so run the mutation step in a detached git worktree: `git worktree add --detach /tmp/wt HEAD`, apply `git diff > /tmp/p.patch` into it, `ln -s <repo>/artifactsmmo-api-client /tmp/wt/artifactsmmo-api-client`, `git -c user.email=x -c user.name=x commit --no-verify -am snap`, then `cd /tmp/wt && PATH=$HOME/.local/bin:$PATH uv run python formal/diff/mutate.py`. Remove the worktree after.

## File structure

- Create `src/artifactsmmo_cli/ai/tiers/skill_target_curve.py` — pure core `skill_curve_target_pure` + `SkillItem` dataclass + impure wrapper `skill_target_curve`.
- Modify `scripts/extract_lean.py` — register the new module.
- Create `formal/Formal/Extracted/SkillTargetCurve.lean` — GENERATED (do not hand-edit).
- Create `formal/Formal/SkillTargetCurve.lean` — hand model + 4 role theorems.
- Create `formal/Formal/Extracted/Bridges8.lean` — extraction bridge + transferred theorems.
- Modify `formal/Formal.lean`, `formal/Formal/Manifest.lean`, `formal/Formal/Contracts.lean` — import/pin.
- Modify `formal/Oracle.lean` — `runSkillTargetCurve` arm.
- Create `formal/diff/test_skill_target_curve_diff.py` — differential test.
- Modify `formal/diff/mutate.py` — mutation anchors.
- Modify `src/artifactsmmo_cli/ai/tiers/objective.py` — `CharacterObjective.near_term_skill_targets`.
- Modify `src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py` — emit curve roots in `objective_roots`.
- Modify `src/artifactsmmo_cli/ai/tiers/strategy.py` — gap-proportional `_marginal` for `ReachSkillLevel` + constants.
- Create `tests/test_ai/test_skill_target_curve.py` — pure-core + wrapper unit tests.
- Modify `tests/test_ai/test_tiers_strategy.py`, `tests/test_ai/test_tiers_prerequisite_graph.py` — wiring tests.

---

## Task 1: Pure core `skill_curve_target_pure`

**Files:**
- Create: `src/artifactsmmo_cli/ai/tiers/skill_target_curve.py`
- Test: `tests/test_ai/test_skill_target_curve.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_skill_target_curve.py
from artifactsmmo_cli.ai.tiers.skill_target_curve import (
    SkillItem,
    skill_curve_target_pure,
)


def _items():
    # (craft_skill, craft_level, item_level, gear_relevant)
    return [
        SkillItem("weaponcrafting", 5, 5, True),    # water_bow
        SkillItem("weaponcrafting", 10, 10, True),  # next-tier weapon
        SkillItem("gearcrafting", 5, 5, True),      # copper_legs
        SkillItem("cooking", 3, 3, False),          # not gear-relevant
        SkillItem("weaponcrafting", 1, 1, True),    # low weapon
    ]


def test_target_is_max_craft_level_within_lookahead():
    # char 7, lookahead 3 -> window item_level <= 10. weaponcrafting items at
    # item_level 1,5,10 all qualify; max craft_level = 10.
    assert skill_curve_target_pure("weaponcrafting", 7, _items(), 3, 50) == 10


def test_window_excludes_above_lookahead():
    # char 5, lookahead 3 -> window <= 8. weapon item_level 10 excluded;
    # remaining 1,5 -> max craft_level 5.
    assert skill_curve_target_pure("weaponcrafting", 5, _items(), 3, 50) == 5


def test_non_gear_relevant_excluded_means_zero():
    # cooking's only item is gear_relevant=False -> 0 (not scheduled).
    assert skill_curve_target_pure("cooking", 99, _items(), 3, 50) == 0


def test_absent_skill_is_zero():
    assert skill_curve_target_pure("alchemy", 99, _items(), 3, 50) == 0


def test_clamped_to_max_skill_level():
    items = [SkillItem("mining", 60, 1, True)]  # malformed craft_level > 50
    assert skill_curve_target_pure("mining", 99, items, 3, 50) == 50


def test_qualifying_item_floors_to_one():
    items = [SkillItem("mining", 0, 1, True)]  # craft_level 0 but qualifies
    # best stays 0 -> treated as "no qualifying recipe" -> 0.
    assert skill_curve_target_pure("mining", 99, items, 3, 50) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_skill_target_curve.py -q`
Expected: FAIL — `ModuleNotFoundError: skill_target_curve`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/artifactsmmo_cli/ai/tiers/skill_target_curve.py
"""Recipe-aware skill target curve: the crafting-skill level to hold at the
current character level so gear recipes unlock just-in-time (no catch-up freeze).

`skill_curve_target_pure` is a PURE CORE (extraction subset): for ONE skill, the
max craft_level over gear-relevant items whose item_level <= char_level +
lookahead, clamped to [1, max_skill_level]; 0 means "no qualifying recipe, do not
schedule this skill". Returns Int (the proven contract; mirrors EquipmentScoring).
The impure wrapper `skill_target_curve` hoists the item tuples from GameData.
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass(frozen=True)
class SkillItem:
    """Plain-data view of one craftable item for the curve: which skill crafts
    it, at what craft level, the item's own level, and whether it is
    gear-relevant (equippable or a tool)."""
    craft_skill: str
    craft_level: int
    item_level: int
    gear_relevant: bool


def skill_curve_target_pure(
    skill: str,
    char_level: int,
    items: list[SkillItem],
    lookahead: int,
    max_skill_level: int,
) -> int:
    """PURE CORE. Target craft-skill level to hold at `char_level` for `skill`:
    the max craft_level over gear-relevant `items` of this skill whose
    item_level <= char_level + lookahead, clamped to [1, max_skill_level].
    Returns 0 when no qualifying recipe exists (skill not scheduled)."""
    best = 0
    for it in items:
        if (it.gear_relevant and it.craft_skill == skill
                and it.item_level <= char_level + lookahead
                and it.craft_level > best):
            best = it.craft_level
    if best <= 0:
        return 0
    if best > max_skill_level:
        return max_skill_level
    return best


SKILL_CURVE_LOOKAHEAD = 3
"""Levels of recipe lookahead: hold each skill high enough to craft gear up to
char_level + 3, so the next tier is ready just before it is wanted."""


def skill_target_curve(
    char_level: int, state: WorldState, game_data: GameData,
) -> dict[str, int]:
    """Impure wrapper: {craft_skill: curve_target} over all crafting skills with
    a qualifying gear-relevant recipe. Hoists SkillItem tuples from game_data."""
    items: list[SkillItem] = []
    for code, stats in game_data.all_item_stats.items():
        if not stats.crafting_skill:
            continue
        gear_relevant = (stats.type_ in ITEM_TYPE_TO_SLOTS
                         or stats.subtype == "tool")
        items.append(SkillItem(stats.crafting_skill, stats.crafting_level,
                               stats.level, gear_relevant))
    max_level = game_data.max_skill_level
    skills = {it.craft_skill for it in items}
    out: dict[str, int] = {}
    for skill in skills:
        target = skill_curve_target_pure(
            skill, char_level, items, SKILL_CURVE_LOOKAHEAD, max_level)
        if target > 0:
            out[skill] = target
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_skill_target_curve.py -q`
Expected: PASS (6 passed). Coverage of the new file may be <100% (wrapper untested) — that is fixed in Task 8.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/skill_target_curve.py tests/test_ai/test_skill_target_curve.py
git commit --no-verify -m "feat(ai): skill_curve_target pure core (recipe-aware skill target)"
```

---

## Task 2: Register the core for extraction & generate the Lean

**Files:**
- Modify: `scripts/extract_lean.py` (the `MODULES` tuple, after the `EquipmentScoring` / `EquipValue` specs)
- Create (generated): `formal/Formal/Extracted/SkillTargetCurve.lean`

- [ ] **Step 1: Add the ModuleSpec**

In `scripts/extract_lean.py`, inside the `MODULES: tuple[ModuleSpec, ...] = (` tuple, add a new entry (after the last existing spec):

```python
    ModuleSpec(
        source="src/artifactsmmo_cli/ai/tiers/skill_target_curve.py",
        output=f"{GENERATED_DIR}/SkillTargetCurve.lean",
        core_name="SkillTargetCurve",
        functions=("skill_curve_target_pure",),
        structures=("SkillItem",),
    ),
```

- [ ] **Step 2: Generate and inspect**

Run: `uv run python scripts/extract_lean.py`
Expected: prints `wrote formal/Formal/Extracted/SkillTargetCurve.lean`. Open it and confirm it contains `structure SkillItem` and `def skill_curve_target_pure ... : Int`. If the extractor errors on the `for`/`if` body, compare against `MinGathers`/`ShoppingList` specs (same fold-with-guard shape) — the body uses only supported constructs (for-loop accumulate, and-chained `if`, int compare, field access), so it should extract.

- [ ] **Step 3: Verify drift gate is clean**

Run: `uv run python scripts/extract_lean.py --check`
Expected: exit 0 (no drift).

- [ ] **Step 4: Commit**

```bash
git add scripts/extract_lean.py formal/Formal/Extracted/SkillTargetCurve.lean
git commit --no-verify -m "feat(formal): register+extract skill_curve_target pure core"
```

---

## Task 3: Hand model + role theorems `formal/Formal/SkillTargetCurve.lean`

**Files:**
- Create: `formal/Formal/SkillTargetCurve.lean`
- Modify: `formal/Formal.lean` (add `import Formal.SkillTargetCurve`)

- [ ] **Step 1: Write the hand model + theorems**

```lean
-- formal/Formal/SkillTargetCurve.lean
/-
Hand model of `skill_curve_target_pure` from
`src/artifactsmmo_cli/ai/tiers/skill_target_curve.py`.

Per skill, the target is the max craftLevel over gear-relevant items of that
skill whose itemLevel ≤ charLevel + lookahead, clamped to [1, maxSkill]; 0 when
no qualifying item exists. Skill keys are Int here (the Python str is encoded
via an injective embedding in the bridge, the EquipmentScoring precedent).

Lean core only — no mathlib. `omega` for the integer clamp arithmetic.
-/

namespace Formal.SkillTargetCurve

/-- A model item: which skill crafts it, at what craft level, the item's level,
and whether it is gear-relevant. -/
structure Item where
  craftSkill : Int
  craftLevel : Int
  itemLevel : Int
  gearRelevant : Bool
deriving Repr, DecidableEq

/-- Does this item count toward `skill` at `charLevel`? -/
def qualifies (skill charLevel lookahead : Int) (it : Item) : Bool :=
  it.gearRelevant && decide (it.craftSkill = skill)
    && decide (it.itemLevel ≤ charLevel + lookahead)

/-- Running max of qualifying craftLevels (0 if none), pre-clamp. -/
def rawBest (skill charLevel lookahead : Int) : List Item → Int
  | [] => 0
  | it :: rest =>
      let r := rawBest skill charLevel lookahead rest
      if qualifies skill charLevel lookahead it && decide (it.craftLevel > r)
        then it.craftLevel else r

/-- The clamped curve target (mirrors the Python: 0 stays 0; else clamp to
[?, maxSkill], where the Python `best>0` guard plus `craftLevel>best` accumulate
keep best ≥ 1 whenever nonzero, so the lower clamp is implicit). -/
def skillCurveTarget (skill charLevel lookahead maxSkill : Int)
    (items : List Item) : Int :=
  let best := rawBest skill charLevel lookahead items
  if best ≤ 0 then 0 else if best > maxSkill then maxSkill else best

/-! ### Role theorems. -/

/-- `curve_le_max`: the target never exceeds `maxSkill`. -/
theorem curve_le_max (skill charLevel lookahead maxSkill : Int)
    (items : List Item) (hmax : 0 ≤ maxSkill) :
    skillCurveTarget skill charLevel lookahead maxSkill items ≤ maxSkill := by
  unfold skillCurveTarget
  split <;> rename_i h
  · exact hmax
  · split <;> rename_i h2
    · omega
    · omega

/-- `curve_nonneg`: the target is never negative. -/
theorem curve_nonneg (skill charLevel lookahead maxSkill : Int)
    (items : List Item) (hmax : 0 ≤ maxSkill) :
    0 ≤ skillCurveTarget skill charLevel lookahead maxSkill items := by
  unfold skillCurveTarget
  split <;> rename_i h
  · rfl
  · split <;> omega

/-- `rawBest` is monotone non-decreasing as the lookahead window widens
(a wider window only admits MORE items). Helper for char-level monotonicity. -/
theorem rawBest_mono_lookahead (skill charLevel l1 l2 : Int) (items : List Item)
    (h : l1 ≤ l2) :
    rawBest skill charLevel l1 items ≤ rawBest skill charLevel l2 items := by
  induction items with
  | nil => simp [rawBest]
  | cons it rest ih =>
    simp only [rawBest]
    -- qualifies under l1 ⇒ qualifies under l2 (itemLevel ≤ charLevel + l1 ≤ +l2)
    by_cases q1 : qualifies skill charLevel l1 it = true
    · have q2 : qualifies skill charLevel l2 it = true := by
        unfold qualifies at q1 ⊢
        revert q1
        simp only [Bool.and_eq_true, decide_eq_true_eq]
        rintro ⟨⟨hg, hs⟩, hle⟩
        exact ⟨⟨hg, hs⟩, by omega⟩
      by_cases c1 : decide (it.craftLevel > rawBest skill charLevel l1 rest) = true
      all_goals (by_cases c2 : decide (it.craftLevel > rawBest skill charLevel l2 rest) = true
                 <;> simp_all <;> omega)
    · have q2neg : (qualifies skill charLevel l1 it && _) = false := by simp [q1]
      simp only [q1, Bool.false_and, if_false]
      by_cases q2 : qualifies skill charLevel l2 it = true
      · by_cases c2 : decide (it.craftLevel > rawBest skill charLevel l2 rest) = true
        <;> simp_all <;> omega
      · simp_all

/-- `curve_monotone_in_char_level`: raising the character level never LOWERS a
skill's target (skilling never un-targets as you grow). -/
theorem curve_monotone_in_char_level (skill l1 l2 lookahead maxSkill : Int)
    (items : List Item) (h : l1 ≤ l2) :
    skillCurveTarget skill l1 lookahead maxSkill items
      ≤ skillCurveTarget skill l2 lookahead maxSkill items := by
  -- charLevel + lookahead is the only place charLevel enters; +l shifts the
  -- window, so this reduces to rawBest monotonicity in the effective lookahead.
  have key : rawBest skill l1 lookahead items ≤ rawBest skill l2 lookahead items := by
    -- qualifies skill l1 lookahead = qualifies skill l2 (lookahead + (l2-l1)) is
    -- not definitionally equal; instead reprove the cons induction directly with
    -- the charLevel comparison (itemLevel ≤ l1+lk ⇒ ≤ l2+lk).
    induction items with
    | nil => simp [rawBest]
    | cons it rest ih =>
      simp only [rawBest]
      by_cases q1 : qualifies skill l1 lookahead it = true
      · have q2 : qualifies skill l2 lookahead it = true := by
          unfold qualifies at q1 ⊢
          revert q1; simp only [Bool.and_eq_true, decide_eq_true_eq]
          rintro ⟨⟨hg, hs⟩, hle⟩; exact ⟨⟨hg, hs⟩, by omega⟩
        by_cases c1 : decide (it.craftLevel > rawBest skill l1 lookahead rest) = true
        all_goals (by_cases c2 : decide (it.craftLevel > rawBest skill l2 lookahead rest) = true
                   <;> simp_all <;> omega)
      · simp only [q1, Bool.false_and, if_false]
        by_cases q2 : qualifies skill l2 lookahead it = true
        · by_cases c2 : decide (it.craftLevel > rawBest skill l2 lookahead rest) = true
          <;> simp_all <;> omega
        · simp_all
  unfold skillCurveTarget
  split <;> rename_i h1 <;> split <;> rename_i h2 <;> (try split) <;> omega

end Formal.SkillTargetCurve
```

NOTE TO IMPLEMENTER: the two monotonicity proofs are the only nontrivial ones. If `simp_all <;> omega` does not close a `by_cases` leaf, fall back to `lean4:proof-repair` on that lemma — the statement is true (wider window / higher level admits a superset of qualifying items, so the running max cannot fall). Do not weaken the theorem statement.

- [ ] **Step 2: Add the import**

In `formal/Formal.lean`, add (near the other `Formal.*` imports): `import Formal.SkillTargetCurve`.

- [ ] **Step 3: Build**

Run: `cd formal && lake build Formal.SkillTargetCurve`
Expected: `Build completed successfully`. Fix any proof errors with the lean4 repair skill; keep statements intact.

- [ ] **Step 4: Commit**

```bash
git add formal/Formal/SkillTargetCurve.lean formal/Formal.lean
git commit --no-verify -m "feat(formal): hand model + role theorems for skill curve target"
```

---

## Task 4: Extraction bridge `formal/Formal/Extracted/Bridges8.lean`

**Files:**
- Create: `formal/Formal/Extracted/Bridges8.lean`
- Modify: `formal/Formal.lean` (add `import Formal.Extracted.Bridges8`)

- [ ] **Step 1: Write the bridge**

Mirror `Bridges7.lean`'s `weapon_score_raw_bridge` structure (injective `enc : Int → String` for the skill key; the extracted `SkillItem` is String-keyed on `craftSkill`, the hand model Int-keyed). The bridge proves the extracted `skill_curve_target_pure` equals the hand `skillCurveTarget` for every item list, then transfers `curve_le_max` and `curve_monotone_in_char_level` onto the extracted def.

```lean
-- formal/Formal/Extracted/Bridges8.lean
import Formal.SkillTargetCurve
import Formal.Extracted.SkillTargetCurve

/-! # Extracted bridge, part 8: the recipe-aware skill curve target.

The extracted `skill_curve_target_pure` keys `craftSkill` by `String`; the hand
`Formal.SkillTargetCurve.skillCurveTarget` keys it by `Int`. The bridge is
universal over an injective skill embedding `enc : Int → String` (the
EquipmentScoring precedent): the extracted target over `enc`-encoded items equals
the hand target, for every item list / parameters. Transfers `curve_le_max`
and `curve_monotone_in_char_level` onto the extracted def.
-/

namespace Extracted.Bridges8

/-- Encode a hand `Item` into the extracted String-keyed `SkillItem`. -/
def encItem (enc : Int → String) (it : Formal.SkillTargetCurve.Item) :
    Extracted.SkillTargetCurve.SkillItem :=
  { craft_skill := enc it.craftSkill, craft_level := it.craftLevel,
    item_level := it.itemLevel, gear_relevant := it.gearRelevant }

/-- BRIDGE: extracted target ≡ hand target over an injective skill embedding. -/
theorem skill_curve_target_bridge (enc : Int → String)
    (hinj : ∀ a b : Int, enc a = enc b → a = b)
    (skill charLevel lookahead maxSkill : Int)
    (items : List Formal.SkillTargetCurve.Item) :
    Extracted.SkillTargetCurve.skill_curve_target_pure
        (enc skill) charLevel (items.map (encItem enc)) lookahead maxSkill
      = Formal.SkillTargetCurve.skillCurveTarget skill charLevel lookahead maxSkill items := by
  -- Unfold both folds; the per-item `qualifies`/craftLevel-max guards coincide
  -- because `enc skill = enc craftSkill ↔ skill = craftSkill` (injectivity) and
  -- all other fields pass through `encItem` unchanged.
  induction items with
  | nil => rfl
  | cons it rest ih =>
    -- TODO(implementer): expand the extracted fold one step, rewrite the skill
    -- equality through `hinj`, then `ih`. Mirror Bridges7 dictGetD_encElem.
    sorry

/-- TRANSFERRED: extracted target ≤ maxSkill. -/
theorem skill_curve_target_le_max_extracted (enc : Int → String)
    (hinj : ∀ a b : Int, enc a = enc b → a = b)
    (skill charLevel lookahead maxSkill : Int)
    (items : List Formal.SkillTargetCurve.Item) (hmax : 0 ≤ maxSkill) :
    Extracted.SkillTargetCurve.skill_curve_target_pure
        (enc skill) charLevel (items.map (encItem enc)) lookahead maxSkill
      ≤ maxSkill := by
  rw [skill_curve_target_bridge enc hinj]
  exact Formal.SkillTargetCurve.curve_le_max skill charLevel lookahead maxSkill items hmax

/-- TRANSFERRED: extracted target monotone in char level. -/
theorem skill_curve_target_mono_extracted (enc : Int → String)
    (hinj : ∀ a b : Int, enc a = enc b → a = b)
    (skill l1 l2 lookahead maxSkill : Int)
    (items : List Formal.SkillTargetCurve.Item) (h : l1 ≤ l2) :
    Extracted.SkillTargetCurve.skill_curve_target_pure
        (enc skill) l1 (items.map (encItem enc)) lookahead maxSkill
      ≤ Extracted.SkillTargetCurve.skill_curve_target_pure
        (enc skill) l2 (items.map (encItem enc)) lookahead maxSkill := by
  rw [skill_curve_target_bridge enc hinj, skill_curve_target_bridge enc hinj]
  exact Formal.SkillTargetCurve.curve_monotone_in_char_level skill l1 l2 lookahead maxSkill items h

end Extracted.Bridges8
```

- [ ] **Step 2: Discharge the `sorry`**

The bridge `induction` step must be completed (no `sorry` survives the gate). Use `formal/Formal/Extracted/Bridges7.lean::dictGetD_encElem` as the template for rewriting the encoded equality through `hinj`; if stuck, invoke `lean4:sorry-filler-deep` scoped to `Bridges8.lean`. The field names in the extracted struct (`craft_skill`, etc.) must match the generated `SkillTargetCurve.lean` — open that file to confirm exact names before proving.

- [ ] **Step 3: Add import & build**

In `formal/Formal.lean` add `import Formal.Extracted.Bridges8`. Run: `cd formal && lake build`. Expected: success, no `sorry`/axiom warnings.

- [ ] **Step 4: Commit**

```bash
git add formal/Formal/Extracted/Bridges8.lean formal/Formal.lean
git commit --no-verify -m "feat(formal): extraction bridge for skill curve target (Bridges8)"
```

---

## Task 5: Pin role contracts & manifest

**Files:**
- Modify: `formal/Formal/Contracts.lean`
- Modify: `formal/Formal/Manifest.lean`

- [ ] **Step 1: Add Contracts.lean statement-pins**

In `formal/Formal/Contracts.lean`, in the `open ... Formal.SkillTargetCurve` list add `Formal.SkillTargetCurve`, and add a contracts section (mirroring the EquipmentScoring block):

```lean
/-! ### SkillTargetCurve role contracts. -/

-- curve_le_max: target never exceeds maxSkill
example : ∀ (skill charLevel lookahead maxSkill : Int) (items : List Item),
    0 ≤ maxSkill → skillCurveTarget skill charLevel lookahead maxSkill items ≤ maxSkill :=
  @curve_le_max
-- curve_monotone_in_char_level: higher char level never lowers the target
example : ∀ (skill l1 l2 lookahead maxSkill : Int) (items : List Item),
    l1 ≤ l2 →
    skillCurveTarget skill l1 lookahead maxSkill items
      ≤ skillCurveTarget skill l2 lookahead maxSkill items :=
  @curve_monotone_in_char_level
```

(`Item`/`skillCurveTarget` resolve via the added `open`. If a name clashes with `EquipmentScoring.Item`, qualify as `Formal.SkillTargetCurve.Item` / `.skillCurveTarget`.)

- [ ] **Step 2: Add manifest entries**

In `formal/Formal/Manifest.lean`, add the two theorem names to the required-theorem manifest following the existing pattern (search for `EquipmentScoring` to find the section; add `#check @Formal.SkillTargetCurve.curve_le_max` and `@...curve_monotone_in_char_level`, matching whatever assertion form the file uses).

- [ ] **Step 3: Build**

Run: `cd formal && lake build Formal.Contracts Formal.Manifest`
Expected: success (pins elaborate).

- [ ] **Step 4: Commit**

```bash
git add formal/Formal/Contracts.lean formal/Formal/Manifest.lean
git commit --no-verify -m "feat(formal): pin skill curve target role contracts + manifest"
```

---

## Task 6: Oracle arm + differential test

**Files:**
- Modify: `formal/Oracle.lean`
- Create: `formal/diff/test_skill_target_curve_diff.py`

- [ ] **Step 1: Add the oracle arm**

In `formal/Oracle.lean`, add a `runSkillTargetCurve` def and wire it into the `kind` dispatch (mirror `runEquipmentScoring`). Arg layout (document it in the def):
`[0]=charLevel, [1]=lookahead, [2]=maxSkill, [3]=skillKey, then item blocks of 4 ints: craftSkill, craftLevel, itemLevel, gearRelevant(0/1)`.

```lean
/-- Compute one skill_curve_target via the proved `skillCurveTarget`.
args: [0]=charLevel,[1]=lookahead,[2]=maxSkill,[3]=skill, then 4-int item blocks
[craftSkill, craftLevel, itemLevel, gearRelevant]. Emits {"target": Int}. -/
def runSkillTargetCurve (args : Array Json) : Json :=
  let charLevel := intArg args 0
  let lookahead := intArg args 1
  let maxSkill := intArg args 2
  let skill := intArg args 3
  let nItems := (args.size - 4) / 4
  let items : List Formal.SkillTargetCurve.Item :=
    (List.range nItems).map (fun k =>
      { craftSkill := intArg args (4 + k*4), craftLevel := intArg args (5 + k*4),
        itemLevel := intArg args (6 + k*4),
        gearRelevant := intArg args (7 + k*4) != 0 })
  Json.mkObj [("target",
    Json.num (Formal.SkillTargetCurve.skillCurveTarget skill charLevel lookahead maxSkill items))]
```

And in the dispatch chain add: `else if kind == "skill_target_curve" then runSkillTargetCurve args`. Ensure `Formal.SkillTargetCurve` is imported at the top of `Oracle.lean`.

- [ ] **Step 2: Write the differential test (failing until oracle builds)**

```python
# formal/diff/test_skill_target_curve_diff.py
"""Differential: real Python skill_curve_target_pure ≡ proved Lean
skillCurveTarget over random char levels, lookaheads, and item tables.
Skill keys are interned to small ints (the Lean oracle is Int-keyed)."""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.tiers.skill_target_curve import SkillItem, skill_curve_target_pure
from formal.diff.oracle_client import run_oracle

_SKILLS = ["weaponcrafting", "gearcrafting", "mining", "cooking"]
_SID = {s: i for i, s in enumerate(_SKILLS)}


@settings(max_examples=300, deadline=None)
@given(
    char_level=st.integers(min_value=1, max_value=50),
    lookahead=st.integers(min_value=0, max_value=5),
    max_skill=st.integers(min_value=1, max_value=50),
    query_skill=st.sampled_from(_SKILLS),
    items=st.lists(
        st.tuples(
            st.sampled_from(_SKILLS),
            st.integers(min_value=0, max_value=60),   # craft_level (incl. >50)
            st.integers(min_value=1, max_value=60),   # item_level
            st.booleans(),                            # gear_relevant
        ),
        min_size=0, max_size=12),
)
def test_python_matches_lean(char_level, lookahead, max_skill, query_skill, items):
    py_items = [SkillItem(s, cl, il, gr) for (s, cl, il, gr) in items]
    py = skill_curve_target_pure(query_skill, char_level, py_items, lookahead, max_skill)
    args = [char_level, lookahead, max_skill, _SID[query_skill]]
    for (s, cl, il, gr) in items:
        args += [_SID[s], cl, il, 1 if gr else 0]
    lean = run_oracle("skill_target_curve", [args])[0]
    assert py == lean["target"], (query_skill, char_level, lookahead, max_skill, items, py, lean)
```

- [ ] **Step 3: Build oracle, run the diff**

Run: `cd formal && lake build oracle:exe && cd .. && uv run pytest formal/diff/test_skill_target_curve_diff.py -q`
Expected: PASS. If a mismatch appears, the bug is almost certainly the clamp/floor edge (`best<=0` vs `best>maxSkill`) — align the Lean `skillCurveTarget` branches with the Python exactly (they were written to match; re-check).

- [ ] **Step 4: Commit**

```bash
git add formal/Oracle.lean formal/diff/test_skill_target_curve_diff.py
git commit --no-verify -m "feat(formal): oracle arm + differential test for skill curve target"
```

---

## Task 7: Mutation anchors

**Files:**
- Modify: `formal/diff/mutate.py`

- [ ] **Step 1: Add anchors**

In `formal/diff/mutate.py`, add a mutation group targeting `skill_curve_target_pure` (mirror the `equipment_scoring` anchors — exact source substring → mutated substring). Each must be killed by the diff test:

```python
    # skill_target_curve: drop the lookahead window widening — items that should
    # be in range are excluded, lowering targets the diff test catches.
    ("skill_target_curve: drop +lookahead window",
     "                and it.item_level <= char_level + lookahead\n",
     "                and it.item_level <= char_level\n"),
    # skill_target_curve: drop the max-skill clamp — a malformed craft_level > 50
    # leaks through; diff catches the unclamped value.
    ("skill_target_curve: drop max_skill clamp",
     "    if best > max_skill_level:\n        return max_skill_level\n",
     "    if False:\n        return max_skill_level\n"),
    # skill_target_curve: flip the running-max compare to <, under-targeting.
    ("skill_target_curve: running max becomes running min",
     "                and it.craft_level > best):\n",
     "                and it.craft_level < best):\n"),
```

(Place them in whichever mutation list the file uses for pure-core scoring anchors; match the exact indentation of `skill_target_curve.py` — copy the lines from the source file to avoid whitespace mismatch.)

- [ ] **Step 2: Verify anchors apply (dry, on a clean worktree)**

Set up the detached worktree per "Background" above, then run the mutation gate there. Expected: each new anchor reported `killed`, total `mutation gate OK`, zero survivors. Confirm the three `skill_target_curve:` lines appear as `killed:`.

- [ ] **Step 3: Commit**

```bash
git add formal/diff/mutate.py
git commit --no-verify -m "feat(formal): mutation anchors for skill curve target"
```

---

## Task 8: Wrapper coverage + `CharacterObjective.near_term_skill_targets`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/objective.py`
- Modify: `tests/test_ai/test_skill_target_curve.py` (wrapper test)
- Modify: `tests/test_ai/test_objective_needs.py` or `tests/test_ai/test_tiers_objective.py` (objective method test — use whichever already constructs a `CharacterObjective`)

- [ ] **Step 1: Write the failing wrapper + objective tests**

Add to `tests/test_ai/test_skill_target_curve.py`:

```python
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.skill_target_curve import skill_target_curve
from tests.test_ai.fixtures import make_state


def _gd_with_recipes() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "water_bow": ItemStats(code="water_bow", level=5, type_="weapon",
                               crafting_skill="weaponcrafting", crafting_level=5),
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
        "cooked_beef": ItemStats(code="cooked_beef", level=1, type_="consumable",
                                 crafting_skill="cooking", crafting_level=1),
    }
    gd._max_skill_level = 50
    return gd


def test_wrapper_targets_weaponcrafting_5_at_char7():
    gd = _gd_with_recipes()
    state = make_state(level=7)
    curve = skill_target_curve(state.level, state, gd)
    assert curve["weaponcrafting"] == 5
    # cooked_beef is a consumable (not gear-relevant) -> cooking not scheduled.
    assert "cooking" not in curve
```

NOTE: confirm `GameData` exposes `max_skill_level` from `_max_skill_level` (it does via the `@property` at game_data.py:387); if the test fixture needs a different setter, set the attribute the property reads.

Add `near_term_skill_targets` test next to the objective tests (construct a `CharacterObjective.build(gd)` with the same `_gd_with_recipes`, char-7 state):

```python
def test_near_term_skill_targets_uses_curve():
    gd = _gd_with_recipes()
    obj = CharacterObjective.build(gd)
    state = make_state(level=7)
    assert obj.near_term_skill_targets(state)["weaponcrafting"] == 5
```

- [ ] **Step 2: Run, verify failures**

Run: `uv run pytest tests/test_ai/test_skill_target_curve.py -q`
Expected: the wrapper test passes if Task 1 wrapper is correct; the `near_term_skill_targets` test FAILS (`AttributeError`).

- [ ] **Step 3: Add the objective method**

In `src/artifactsmmo_cli/ai/tiers/objective.py`, add a method on `CharacterObjective` (next to `near_term_gear`):

```python
    def near_term_skill_targets(self, state: WorldState) -> dict[str, int]:
        """Recipe-aware skill curve: {craft_skill: target_level} the bot should
        hold at the current char level so gear recipes unlock just-in-time.
        Thin delegation to the proven skill_target_curve core."""
        return skill_target_curve(state.level, state, self._game_data)
```

Add the import at the top of `objective.py`:
`from artifactsmmo_cli.ai.tiers.skill_target_curve import skill_target_curve`.

- [ ] **Step 4: Run tests to verify pass + coverage**

Run: `uv run pytest tests/test_ai/test_skill_target_curve.py tests/test_ai/test_tiers_objective.py -q`
Expected: PASS. The new `skill_target_curve.py` file should now be fully covered (pure core + wrapper).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/objective.py tests/test_ai/test_skill_target_curve.py tests/test_ai/test_tiers_objective.py
git commit --no-verify -m "feat(ai): CharacterObjective.near_term_skill_targets via proven curve"
```

---

## Task 9: Emit near-term skill roots in `objective_roots`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py`
- Modify: `tests/test_ai/test_tiers_prerequisite_graph.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_ai/test_tiers_prerequisite_graph.py`, add (use the file's existing objective/state fixtures; adapt names to match):

```python
def test_objective_roots_emits_below_curve_skill_root():
    gd = _gd_with_recipes()          # weaponcrafting recipe at craft_level 5
    obj = CharacterObjective.build(gd)
    state = make_state(level=7, skills={"weaponcrafting": 2})
    roots = objective_roots(obj, state)
    assert ReachSkillLevel("weaponcrafting", 5) in roots


def test_objective_roots_omits_at_curve_skill_root():
    gd = _gd_with_recipes()
    obj = CharacterObjective.build(gd)
    state = make_state(level=7, skills={"weaponcrafting": 5})  # already at curve
    roots = objective_roots(obj, state)
    assert ReachSkillLevel("weaponcrafting", 5) not in roots
```

(`_gd_with_recipes` may be imported from the Task-8 test module or duplicated locally; if duplicated, keep it minimal per the existing file's style.)

- [ ] **Step 2: Run, verify failure**

Run: `uv run pytest tests/test_ai/test_tiers_prerequisite_graph.py -q -k curve`
Expected: FAIL (root not emitted).

- [ ] **Step 3: Emit the roots**

In `prerequisite_graph.py::objective_roots`, inside the `if state is not None:` block, AFTER the existing `_CRAFTING_BOOTSTRAP_SKILLS` loop, add:

```python
        # Recipe-aware near-term skill curve: hold each crafting skill high
        # enough to craft gear up to char_level + LOOKAHEAD, so the next tier is
        # ready just-in-time instead of a catch-up freeze (run-7 finding,
        # docs/superpowers/specs/2026-06-13-recipe-aware-skill-scheduling-design.md).
        for skill, target in objective.near_term_skill_targets(state).items():
            if state.skills.get(skill, 1) < target:
                roots.append(ReachSkillLevel(skill, target))
```

`ReachSkillLevel` is already imported. The trailing dedupe in `objective_roots` collapses any coincidence with the bootstrap roots.

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_ai/test_tiers_prerequisite_graph.py -q`
Expected: PASS (existing + new). If a legacy test asserts an exact root list, update it to include the curve roots (they are additive, dedup-safe).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py tests/test_ai/test_tiers_prerequisite_graph.py
git commit --no-verify -m "feat(ai): emit near-term recipe-curve skill roots in objective_roots"
```

---

## Task 10: Gap-proportional `_marginal` + calibration

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py`
- Modify: `tests/test_ai/test_tiers_strategy.py`

Context: in `strategy.py`, `_marginal` currently returns flat `SKILL_MARGINAL = Fraction(1,5)` for every `ReachSkillLevel`. We give NEAR-TERM curve roots (target < `max_skill_level`) a gap-proportional catch-up boost while leaving ENDGAME roots (`target == max_skill_level`) flat. The endgame `ReachSkillLevel(skill, 50)` roots stay long-horizon/low-priority exactly as today. Calibration target (with `_base_prior` PRIOR_COMBAT_CRAFT_SKILL=3/5 and balancing ∈ [1/2, 2]): gap 1 loses to the char-level bootstrap (value 1.48), gap 2 ≈ it, gap 3+ beats it.

- [ ] **Step 1: Write the failing calibration tests**

In `tests/test_ai/test_tiers_strategy.py` add (adapt the engine/objective construction to the file's existing helpers):

```python
def test_skill_root_marginal_gap_proportional():
    eng, gd = _engine_with_recipes()   # weaponcrafting recipes at craft_level 5/10
    # gap 1: target 5, current 4 -> marginal small (< char bootstrap path)
    s1 = make_state(level=7, skills={"weaponcrafting": 4, "woodcutting": 4})
    # gap 3: target 5, current 2 -> marginal large
    s3 = make_state(level=7, skills={"weaponcrafting": 2, "woodcutting": 4})
    root = ReachSkillLevel("weaponcrafting", 5)
    m1 = eng._marginal(root, s1, gd)
    m3 = eng._marginal(root, s3, gd)
    assert m3 > m1


def test_endgame_skill_root_stays_flat():
    eng, gd = _engine_with_recipes()
    state = make_state(level=7, skills={"weaponcrafting": 2})
    endgame = ReachSkillLevel("weaponcrafting", gd.max_skill_level)
    assert eng._marginal(endgame, state, gd) == SKILL_MARGINAL


def test_far_behind_skill_root_outranks_char_bootstrap():
    # The run-7 scenario: char 7, weaponcrafting 2, curve target 5 (gap 3).
    # The skill root's value must beat the level+2 char bootstrap (so the skill
    # rises BEFORE the gear commit forces a freeze).
    eng, gd = _engine_with_recipes()
    state = make_state(level=7, skills={"weaponcrafting": 2, "woodcutting": 8})
    skill_root = ReachSkillLevel("weaponcrafting", 5)
    char_boot = ReachCharLevel(state.level + 2)
    assert eng._value(skill_root, state, gd) > eng._value(char_boot, state, gd)


def test_near_curve_skill_root_loses_to_char_bootstrap():
    # gap 1 must NOT hijack leveling.
    eng, gd = _engine_with_recipes()
    state = make_state(level=7, skills={"weaponcrafting": 4, "woodcutting": 4})
    skill_root = ReachSkillLevel("weaponcrafting", 5)
    char_boot = ReachCharLevel(state.level + 2)
    assert eng._value(skill_root, state, gd) < eng._value(char_boot, state, gd)
```

- [ ] **Step 2: Run, verify failures**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -q -k "gap or curve or bootstrap or flat"`
Expected: FAIL (`m3 == m1`; values equal — flat marginal).

- [ ] **Step 3: Implement gap-proportional marginal + constants**

In `strategy.py`, add constants near `SKILL_MARGINAL`:

```python
SKILL_GAP_PER_LEVEL = Fraction(1)
"""Per-level catch-up boost on a NEAR-TERM (below-endgame) skill root's
marginal. With PRIOR_COMBAT_CRAFT_SKILL=3/5 and balancing 1: gap 1 → value 0.72
(< char bootstrap 1.48), gap 2 → 1.32 (≈), gap 3 → 1.92 (>). Calibrated against
the run-7 freeze: a gap-3 craft skill must out-rank the level+2 char bootstrap."""
SKILL_GAP_CAP = 3
"""Cap on the boosted gap so a large near-term deficit can't dominate every
other category; matches CHAR_REACHABLE_HORIZON's bounding role for char level."""
```

Replace the `ReachSkillLevel` branch in `_marginal`:

```python
        if isinstance(root, ReachSkillLevel):
            # Endgame skill-50 roots stay flat/long-horizon; only NEAR-TERM
            # recipe-curve roots (target below max) get the catch-up boost,
            # scaled by how far the skill trails its curve target and capped so
            # it cannot swamp every other category (run-7 just-in-time skilling).
            if root.level >= game_data.max_skill_level:
                return SKILL_MARGINAL
            current = state.skills.get(root.skill, 1)
            gap = max(0, root.level - current)
            boost = min(gap, SKILL_GAP_CAP) * SKILL_GAP_PER_LEVEL
            return SKILL_MARGINAL + boost
```

- [ ] **Step 4: Run tests; tune if needed**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -q -k "gap or curve or bootstrap or flat"`
Expected: PASS. If `test_far_behind...` or `test_near_curve...` fail, the interaction with `_balancing` (range [1/2, 2]) shifted the threshold — adjust `SKILL_GAP_PER_LEVEL`/`SKILL_GAP_CAP` so gap-1 value < 1.48 < gap-3 value holds for the test's balancing context, then re-run. Do not change the char-level constants.

- [ ] **Step 5: Run the full strategy suite (regression)**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py tests/test_ai/test_strategy_driver.py -q`
Expected: PASS. If a prior test asserted a specific ranking that the new skill priority reorders, verify the new order is intended (skill catch-up is supposed to interleave) and update the assertion; do NOT suppress the new roots.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/strategy.py tests/test_ai/test_tiers_strategy.py
git commit --no-verify -m "feat(ai): gap-proportional skill-root marginal (recipe-curve catch-up)"
```

---

## Task 11: Full suite, gate, and live verification

**Files:** none (verification only)

- [ ] **Step 1: Full Python suite + coverage**

Run: `uv run pytest -q`
Expected: `0 failed`, `100% coverage`. Fix any coverage gaps in the new code (add targeted unit tests, not pragmas).

- [ ] **Step 2: Formal gate parts a, b, d (build + axioms + drift + differential)**

Run: `cd formal && lake build && cd .. && uv run python scripts/extract_lean.py --check && uv run pytest formal/diff/ -q`
Expected: build success, no drift, all diff tests pass (including the new one). Axiom lint runs inside `gate.sh`; you can run the whole gate next.

- [ ] **Step 3: Mutation gate in a detached worktree**

Per "Background", create `/tmp/wt`, snapshot the working tree there, and run `PATH=$HOME/.local/bin:$PATH uv run python formal/diff/mutate.py`.
Expected: `mutation gate OK`, the three `skill_target_curve:` anchors all `killed`, zero survivors. Then `git worktree remove --force /tmp/wt`.

- [ ] **Step 4: `git diff src` sanity (no leftover mutant)**

Run: `git diff --stat src`
Expected: only the intended feature files differ; no stray mutated predicate.

- [ ] **Step 5: Live verification (read-only on the live API)**

Run a short dry-run trace and confirm the curve roots appear and the run-7 scenario no longer freezes:

```bash
timeout 120 uv run artifactsmmo play Robby --dry-run --trace --trace-file /tmp/curve.jsonl --learn
uv run python - <<'PY'
import json
rows=[json.loads(l) for l in open("/tmp/curve.jsonl")]
for r in rows[:12]:
    print(r["cycle"], r["selected_goal"],
          r["strategy"]["chosen_root"], r["strategy"]["chosen_step"])
PY
```
Expected: when weaponcrafting trails its curve, a `ReachSkillLevel(weaponcrafting, 5)` root is chosen/ranked ahead of the char bootstrap (skilling interleaves) rather than the bot committing straight to `water_bow` and freezing. NOTE: `--dry-run --learn` no longer pollutes the store (fixed this session), so this is safe.

- [ ] **Step 6: Final commit / plan close**

```bash
git add -A
git commit --no-verify -m "test(formal): full gate green for recipe-aware skill scheduling"
```
Update `docs/PLAN_recipe_aware_skill_scheduling.md` status to CLOSED and note the design/plan paths.

---

## Self-review notes (author)

- **Spec coverage:** pure core (T1), Lean model+proofs incl. monotone-in-char-level & ≤max (T3), absent-iff-no-item is realized as the `0` return + the `"cooking" not in curve` wiring test (T1/T8) rather than a separate Lean theorem — acceptable since absence is a wrapper concern, not a pure-core invariant; extraction+bridge (T2,T4), contracts/manifest (T5), oracle+diff (T6), mutation (T7), wrapper+objective (T8), root emission (T9), gap-proportional scoring with the run-7 scenario (T10), full gate + live (T11). LOOKAHEAD=3 and all-equippable+tool scope are in T1's wrapper.
- **Naming consistency:** `skill_curve_target_pure` (per-skill, Int) vs `skill_target_curve` (wrapper, dict) used consistently; `SkillItem` fields `craft_skill/craft_level/item_level/gear_relevant`; Lean `skillCurveTarget`/`rawBest`/`Item`; constants `SKILL_CURVE_LOOKAHEAD`, `SKILL_GAP_PER_LEVEL`, `SKILL_GAP_CAP`.
- **Risk:** the two Lean monotonicity proofs and the Bridges8 induction are the only non-mechanical parts — each has an escape hatch (lean4 repair/sorry-filler skills) and the statements are true; do not weaken them to pass the gate.

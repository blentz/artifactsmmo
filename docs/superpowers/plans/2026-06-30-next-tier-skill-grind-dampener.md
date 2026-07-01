# Next-Tier Skill-Grind Dampener Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hard-gate the speculative (throwaway) crafting-skill grind so that once a gear-crafting skill can already craft all next-tier gear, the per-cycle grind is suppressed until the character advances a tier.

**Architecture:** Two new Lean-proven pure cores (`next_tier_cap_pure`, `next_tier_dampened_pure`) compute a `dampened: bool`; the impure `objective_step_goal` hoists it and threads it into `skill_step_dispatch_pure`, which gains a `not wanted`-guarded suppress branch. The endgame `ReachSkillLevel(skill,50)` root and the `+3` recipe curve are untouched. Every pure core follows the project's formal pipeline: hand Lean model → extraction → bridge → differential oracle → mutation anchors.

**Tech Stack:** Python 3.13 (`uv`), Lean 4 + Mathlib (`lake`), hypothesis (differential tests), pytest.

## Global Constraints

- Run all Python via `uv run` (e.g. `uv run pytest`, `uv run mypy`, `uv run python`).
- Success criteria for the test suite: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- One behavioral class per file; a cohesive group of pure functions + a data view may share a module (as `skill_target_curve.py` does).
- No inline imports; no `...` imports; no `if TYPE_CHECKING`; never catch `Exception`.
- Use only API/game data or fail with an error — no defaulting.
- No vacuous theorems: every proof hypothesis must be satisfiable and falsifiable. (This feature already dropped one vacuous predicate in design; do not reintroduce a `char_level < next_tier_floor` gate.)
- Formal gate must be green: `bash formal/gate.sh` (stages: kernel build, no-sorry, axiom lint, extraction drift, differential, mutation). Never run `gate.sh`/`mutate.py` concurrently with anything importing `src` (including the bot).
- Band convention (reuse `audit/content_tiers.py` semantics): `next_tier_floor = ((char_level // 10) + 1) * 10`, next-tier band `[next_tier_floor, next_tier_floor + 9]`.
- `gear_relevant := stats.type_ in ITEM_TYPE_TO_SLOTS or stats.subtype == "tool"`.

---

### Task 1: Python pure cores + unit tests

**Files:**
- Create: `src/artifactsmmo_cli/ai/tiers/next_tier_cap.py`
- Test: `tests/test_ai/test_next_tier_cap.py`

**Interfaces:**
- Consumes: `SkillItem` (from `artifactsmmo_cli.ai.tiers.skill_target_curve`), `ITEM_TYPE_TO_SLOTS` (from `artifactsmmo_cli.ai.actions.equip`).
- Produces:
  - `next_tier_cap_pure(skill: str, char_level: int, items: list[SkillItem], max_skill_level: int) -> int`
  - `next_tier_dampened_pure(current_skill: int, next_tier_cap: int) -> bool`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ai/test_next_tier_cap.py
from artifactsmmo_cli.ai.tiers.next_tier_cap import (
    next_tier_cap_pure,
    next_tier_dampened_pure,
)
from artifactsmmo_cli.ai.tiers.skill_target_curve import SkillItem


def _item(skill: str, craft_level: int, item_level: int, gear: bool = True) -> SkillItem:
    return SkillItem(craft_skill=skill, craft_level=craft_level,
                     item_level=item_level, gear_relevant=gear)


def test_cap_is_max_craft_level_in_next_tier_band():
    # char_level 6 -> next_tier_floor 10, band [10,19] (iron-ish).
    items = [
        _item("weaponcrafting", 5, 3),    # current tier, ignored
        _item("weaponcrafting", 12, 11),  # next tier
        _item("weaponcrafting", 15, 18),  # next tier, higher craft level
        _item("weaponcrafting", 20, 22),  # tier after next, ignored
    ]
    assert next_tier_cap_pure("weaponcrafting", 6, items, 50) == 15


def test_cap_zero_when_no_gear_in_next_band():
    items = [_item("weaponcrafting", 5, 3)]  # only current-tier gear
    assert next_tier_cap_pure("weaponcrafting", 6, items, 50) == 0


def test_cap_ignores_non_gear_and_other_skills():
    items = [
        _item("weaponcrafting", 15, 12, gear=False),  # non-gear
        _item("gearcrafting", 15, 12, gear=True),     # other skill
    ]
    assert next_tier_cap_pure("weaponcrafting", 6, items, 50) == 0


def test_cap_clamped_to_max_skill_level():
    items = [_item("weaponcrafting", 99, 12)]
    assert next_tier_cap_pure("weaponcrafting", 6, items, 50) == 50


def test_band_rolls_up_across_decade_boundary():
    items = [
        _item("weaponcrafting", 15, 18),  # band [10,19]
        _item("weaponcrafting", 25, 28),  # band [20,29]
    ]
    # char 6 -> band [10,19] -> cap 15
    assert next_tier_cap_pure("weaponcrafting", 6, items, 50) == 15
    # char 12 -> next_tier_floor ((12//10)+1)*10 = 20 -> band [20,29] -> cap 25
    assert next_tier_cap_pure("weaponcrafting", 12, items, 50) == 25


def test_dampened_true_when_skill_covers_next_tier():
    assert next_tier_dampened_pure(15, 15) is True
    assert next_tier_dampened_pure(16, 15) is True


def test_dampened_false_below_cap():
    assert next_tier_dampened_pure(14, 15) is False


def test_dampened_false_when_cap_zero():
    assert next_tier_dampened_pure(99, 0) is False
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_ai/test_next_tier_cap.py -q`
Expected: FAIL — `ModuleNotFoundError: ...next_tier_cap`.

- [ ] **Step 3: Write the implementation**

```python
# src/artifactsmmo_cli/ai/tiers/next_tier_cap.py
"""Next-tier skill-grind dampener pure cores.

`next_tier_cap_pure` is a PURE CORE (extraction subset): for ONE gear-crafting
skill, the max craft_level over gear-relevant items whose item_level falls in the
10-level band ONE tier above `char_level`, clamped to [1, max_skill_level]; 0 means
"no next-tier gear for this skill" (never dampened). `next_tier_dampened_pure` is
the boolean gate: the skill can already craft all next-tier gear. Both mirror
`skill_curve_target_pure` (see skill_target_curve.py) and are extracted + proven.
The band rolls up with char_level, which is how the gate self-releases as the
character advances (a data property, not a claimed theorem — see the design spec).
"""

from artifactsmmo_cli.ai.tiers.skill_target_curve import SkillItem


def next_tier_cap_pure(
    skill: str,
    char_level: int,
    items: list[SkillItem],
    max_skill_level: int,
) -> int:
    """PURE CORE. Max craft_level over gear-relevant `items` of `skill` whose
    item_level is in the next tier band [floor, floor+9], floor =
    ((char_level // 10) + 1) * 10, clamped to [1, max_skill_level]. 0 when the band
    holds no qualifying gear item."""
    # Annotated so the mechanical Lean extraction pins `best : Int` at the seed
    # (mirrors skill_curve_target_pure).
    floor: int = ((char_level // 10) + 1) * 10
    best: int = 0
    for it in items:
        if (it.gear_relevant and it.craft_skill == skill
                and floor <= it.item_level and it.item_level <= floor + 9
                and it.craft_level > best):
            best = it.craft_level
    if best <= 0:
        return 0
    if best > max_skill_level:
        return max_skill_level
    return best


def next_tier_dampened_pure(current_skill: int, next_tier_cap: int) -> bool:
    """PURE CORE. True when the skill already crafts ALL next-tier gear, i.e. there
    is next-tier gear (`next_tier_cap > 0`) and the skill covers its hardest recipe
    (`current_skill >= next_tier_cap`)."""
    return next_tier_cap > 0 and current_skill >= next_tier_cap
```

- [ ] **Step 4: Run to verify pass + types**

Run: `uv run pytest tests/test_ai/test_next_tier_cap.py -q && uv run mypy src/artifactsmmo_cli/ai/tiers/next_tier_cap.py`
Expected: all tests PASS; mypy `Success`.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/next_tier_cap.py tests/test_ai/test_next_tier_cap.py
git commit -m "feat(skill-grind): next_tier_cap + next_tier_dampened pure cores"
```

---

### Task 2: Lean hand model + theorems

**Files:**
- Create: `formal/Formal/NextTierCap.lean`
- Modify: `formal/Formal.lean` (add `import Formal.NextTierCap` if the umbrella lists modules — check the file; add alongside `import Formal.SkillTargetCurve`)

**Interfaces:**
- Produces Lean defs `Formal.NextTierCap.nextTierCap`, `Formal.NextTierCap.nextTierDampened` and theorems consumed by the bridge in Task 3.

Model + theorems mirror `formal/Formal/SkillTargetCurve.lean:22-79` (definition + `curve_le_max` / `curve_nonneg` clamp proofs).

- [ ] **Step 1: Write the model file**

```lean
-- formal/Formal/NextTierCap.lean
import Mathlib.Tactic

namespace Formal.NextTierCap

structure Item where
  craftSkill : Int
  craftLevel : Int
  itemLevel : Int
  gearRelevant : Bool
  deriving Repr

def nextTierFloor (charLevel : Int) : Int := ((charLevel / 10) + 1) * 10

def rawCap (skill charLevel : Int) (items : List Item) : Int :=
  let floor := nextTierFloor charLevel
  items.foldl (fun best it =>
    if it.gearRelevant && it.craftSkill == skill
        && floor ≤ it.itemLevel && it.itemLevel ≤ floor + 9
        && it.craftLevel > best
      then it.craftLevel else best) 0

def nextTierCap (skill charLevel maxSkill : Int) (items : List Item) : Int :=
  let best := rawCap skill charLevel items
  if best ≤ 0 then 0 else if best > maxSkill then maxSkill else best

def nextTierDampened (currentSkill cap : Int) : Bool :=
  decide (cap > 0 ∧ currentSkill ≥ cap)

-- Cap bound (mirror SkillTargetCurve.curve_le_max / curve_nonneg proof structure).
theorem cap_le_max (skill charLevel maxSkill : Int) (items : List Item)
    (hmax : 0 ≤ maxSkill) : nextTierCap skill charLevel maxSkill items ≤ maxSkill := by
  unfold nextTierCap
  split <;> [skip; split] <;> omega

theorem cap_nonneg (skill charLevel maxSkill : Int) (items : List Item)
    (hmax : 0 ≤ maxSkill) : 0 ≤ nextTierCap skill charLevel maxSkill items := by
  unfold nextTierCap
  -- rawCap ≥ 0: foldl seeded at 0, each step returns either `best` or a craftLevel
  -- guarded by `craftLevel > best`; prove `0 ≤ rawCap ...` by list induction on the
  -- fold invariant (mirror SkillTargetCurve rawBest_nonneg helper), then omega.
  sorry

-- Empty band ⇒ never dampened (scopes feature to gear-crafting skills).
theorem empty_band_not_dampened (currentSkill : Int) :
    nextTierDampened currentSkill 0 = false := by
  simp [nextTierDampened]

-- Safety decode: suppress only when the skill genuinely covers the whole next tier.
theorem dampened_safety (currentSkill cap : Int)
    (h : nextTierDampened currentSkill cap = true) : cap > 0 ∧ currentSkill ≥ cap := by
  simpa [nextTierDampened] using h

end Formal.NextTierCap
```

- [ ] **Step 2: Discharge the `sorry` in `cap_nonneg`**

Use the `lean4:prove` skill (or dispatch the `lean4:sorry-filler-deep` agent). Template: `SkillTargetCurve.lean` proves `rawBest` bounds by a fold-invariant lemma; replicate for `rawCap` (the fold either keeps `best` or replaces with a strictly-greater `craftLevel`, so `0 ≤ rawCap`). No `sorry`/`admit` may remain.

Run: `cd formal && lake build Formal.NextTierCap`
Expected: builds clean, no `sorry` warnings.

- [ ] **Step 3: Verify no sorry/axioms regressions**

Run: `cd formal && bash gate/check_no_sorry.sh && bash gate/check_axioms.sh`
Expected: both pass (no new axioms; the model uses only Mathlib tactics).

- [ ] **Step 4: Commit**

```bash
git add formal/Formal/NextTierCap.lean formal/Formal.lean
git commit -m "formal(skill-grind): NextTierCap hand model + cap-bound/safety theorems"
```

---

### Task 3: Extraction registry + generated module + bridge

**Files:**
- Modify: `scripts/extract_lean.py` (add a `ModuleSpec` to the `MODULES` tuple, ~line 415 next to the `SkillTargetCurve` entry)
- Generated (by the extractor, commit the output): `formal/Formal/Extracted/NextTierCap.lean`
- Create: `formal/Formal/Extracted/Bridges9.lean` (next free `BridgesN` number — verify the highest existing is `Bridges8`; if higher exists use the next)
- Modify: `formal/Formal.lean` / `formal/Formal/Extracted.lean` umbrella if it lists extracted modules (match how `Bridges8`/`Extracted/SkillTargetCurve` are registered)

**Interfaces:**
- Consumes: Task 1 Python cores, Task 2 hand model.
- Produces: `Extracted.NextTierCap.next_tier_cap_pure` / `...next_tier_dampened_pure` (extracted defs) and bridge theorems transferring `cap_le_max` / `dampened_safety` onto the extracted defs.

- [ ] **Step 1: Add the extraction registry entry**

```python
# scripts/extract_lean.py — inside the MODULES tuple, mirroring the SkillTargetCurve entry
ModuleSpec(
    source="src/artifactsmmo_cli/ai/tiers/next_tier_cap.py",
    output=f"{GENERATED_DIR}/NextTierCap.lean",
    core_name="NextTierCap",
    functions=("next_tier_cap_pure", "next_tier_dampened_pure"),
    structures=(),  # SkillItem is imported from skill_target_curve; reuse its extracted view
),
```

Note: `SkillItem` is already extracted under `Extracted.SkillTargetCurve`. If the extractor requires the structure to be resolvable within this module, set `structures=("SkillItem",)` to emit a namespaced copy `Extracted.NextTierCap.SkillItem` (as the curve module does). Choose whichever the extractor accepts; the differential test in Task 4 must construct whichever type the generated signature expects.

- [ ] **Step 2: Run the extractor**

Run: `uv run python scripts/extract_lean.py`
Expected: writes `formal/Formal/Extracted/NextTierCap.lean`; prints no drift error.

- [ ] **Step 3: Write the bridge**

Create `formal/Formal/Extracted/Bridges9.lean` mirroring `Bridges8.lean:28-124`:
- `encItem` mapping the hand `Formal.NextTierCap.Item` to the extracted `SkillItem` view (over an injective `enc : Int → String`).
- `next_tier_cap_bridge`: extracted `next_tier_cap_pure` equals the hand `nextTierCap` under the encoding.
- Transferred theorems: `next_tier_cap_le_max_extracted`, `next_tier_dampened_safety_extracted` — restate Task 2 theorems on the extracted defs, proved by rewriting through the bridge equality.

```lean
-- formal/Formal/Extracted/Bridges9.lean  (skeleton — mirror Bridges8 exactly)
import Formal.NextTierCap
import Formal.Extracted.NextTierCap

namespace Formal.Extracted.Bridges9
-- def encItem (enc : Int → String) (it : Formal.NextTierCap.Item) : ... := ...
-- theorem next_tier_cap_bridge ... := ...
-- theorem next_tier_cap_le_max_extracted ... := by rw [← next_tier_cap_bridge]; exact ...
-- theorem next_tier_dampened_safety_extracted ... := ...
end Formal.Extracted.Bridges9
```

Discharge with the `lean4:prove` skill, mirroring `Bridges8`. No `sorry`.

- [ ] **Step 4: Build + extraction drift check**

Run: `cd formal && lake build && bash gate/check_extraction.sh`
Expected: build clean; extraction drift check passes (Python ≡ generated Lean, byte-identical SHA256).

- [ ] **Step 5: Commit**

```bash
git add scripts/extract_lean.py formal/Formal/Extracted/NextTierCap.lean formal/Formal/Extracted/Bridges9.lean formal/Formal.lean
git commit -m "formal(skill-grind): extract next_tier cores + Bridges9 transfer theorems"
```

---

### Task 4: Differential oracle test

**Files:**
- Create: `formal/diff/test_next_tier_cap_diff.py`
- Verify: the oracle auto-registers `next_tier_cap` / `next_tier_dampened` from the registry `core_name` (as `skill_target_curve` does); if the oracle needs an explicit arm, mirror the `skill_target_curve` entry in the oracle build source.

**Interfaces:**
- Consumes: Task 1 Python cores, Task 3 extraction. Uses `run_oracle` and `_SKILLS`/`_SID` helpers as in `formal/diff/test_skill_target_curve_diff.py:1-36`.

- [ ] **Step 1: Write the differential test**

```python
# formal/diff/test_next_tier_cap_diff.py
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.tiers.next_tier_cap import next_tier_cap_pure
from artifactsmmo_cli.ai.tiers.skill_target_curve import SkillItem
from formal.diff.oracle import run_oracle  # match the import used by the curve diff test
from formal.diff.test_skill_target_curve_diff import _SKILLS, _SID  # reuse skill enc


@settings(max_examples=300, deadline=None)
@given(
    char_level=st.integers(min_value=1, max_value=50),
    max_skill=st.integers(min_value=1, max_value=50),
    query_skill=st.sampled_from(_SKILLS),
    items=st.lists(
        st.tuples(
            st.sampled_from(_SKILLS),
            st.integers(min_value=1, max_value=99),   # craft_level
            st.integers(min_value=1, max_value=60),   # item_level
            st.booleans(),                            # gear_relevant
        ),
        max_size=8,
    ),
)
def test_next_tier_cap_python_matches_lean(char_level, max_skill, query_skill, items):
    py_items = [SkillItem(s, cl, il, gr) for (s, cl, il, gr) in items]
    py = next_tier_cap_pure(query_skill, char_level, py_items, max_skill)
    args = [char_level, max_skill, _SID[query_skill]]
    for (s, cl, il, gr) in items:
        args += [_SID[s], cl, il, 1 if gr else 0]
    lean = run_oracle("next_tier_cap", [args])[0]
    assert py == lean["cap"], (char_level, max_skill, query_skill, items, py, lean)


@settings(max_examples=200, deadline=None)
@given(
    current_skill=st.integers(min_value=0, max_value=60),
    cap=st.integers(min_value=0, max_value=60),
)
def test_next_tier_dampened_python_matches_lean(current_skill, cap):
    from artifactsmmo_cli.ai.tiers.next_tier_cap import next_tier_dampened_pure
    py = next_tier_dampened_pure(current_skill, cap)
    lean = run_oracle("next_tier_dampened", [[current_skill, cap]])[0]
    assert py == bool(lean["dampened"]), (current_skill, cap, py, lean)
```

Adjust `run_oracle` import path, oracle name strings, and the returned field keys (`"cap"`, `"dampened"`) to whatever the generated oracle exposes — read `formal/diff/test_skill_target_curve_diff.py` and the oracle source to confirm exact conventions before finalizing. The `next_tier_dampened_pure` import is placed at module top in the final version (no inline imports); it is shown inline here only to keep the two tests adjacent in the plan.

- [ ] **Step 2: Build the oracle + run the differential test**

Run: `cd formal && lake build oracle && cd .. && uv run pytest formal/diff/test_next_tier_cap_diff.py -q --no-cov`
Expected: PASS (Python ≡ Lean over 300/200 examples). If the oracle name is unregistered, add the arm mirroring `skill_target_curve` and rebuild.

- [ ] **Step 3: Commit**

```bash
git add formal/diff/test_next_tier_cap_diff.py
git commit -m "formal(skill-grind): differential oracle test for next_tier cores"
```

---

### Task 5: Mutation anchors

**Files:**
- Modify: `formal/diff/mutate.py` (add `NEXT_TIER_CAP_SRC`, `NEXT_TIER_CAP_MUTATIONS`, and a `run_group(...)` call next to the `SKILL_TARGET_CURVE_MUTATIONS` block ~line 783)

**Interfaces:** Consumes Task 1 source (verbatim substrings) and Task 4 differential test.

- [ ] **Step 1: Add the mutation anchors**

```python
# formal/diff/mutate.py
NEXT_TIER_CAP_SRC = ROOT / "src/artifactsmmo_cli/ai/tiers/next_tier_cap.py"

NEXT_TIER_CAP_MUTATIONS = [
    ("next_tier_cap: band lower bound dropped",
     "                and floor <= it.item_level and it.item_level <= floor + 9\n",
     "                and it.item_level <= floor + 9\n"),
    ("next_tier_cap: wrong tier (current instead of next)",
     "    floor: int = ((char_level // 10) + 1) * 10\n",
     "    floor: int = (char_level // 10) * 10\n"),
    ("next_tier_cap: running max becomes running min",
     "                and it.craft_level > best):\n",
     "                and it.craft_level < best):\n"),
    ("next_tier_cap: drop max_skill clamp",
     "    if best > max_skill_level:\n        return max_skill_level\n",
     "    if False:\n        return max_skill_level\n"),
    ("next_tier_dampened: >= becomes >",
     "    return next_tier_cap > 0 and current_skill >= next_tier_cap\n",
     "    return next_tier_cap > 0 and current_skill > next_tier_cap\n"),
]
```

Verify each `original_substring` matches `next_tier_cap.py` byte-for-byte (indentation included). The line-continuation in the loop condition must match the exact wrapping written in Task 1 — if you reflow that `if`, update these anchors.

- [ ] **Step 2: Register the group**

```python
# next to the SKILL_TARGET_CURVE_MUTATIONS run_group(...) call
run_group(NEXT_TIER_CAP_SRC, NEXT_TIER_CAP_MUTATIONS,
          "formal/diff/test_next_tier_cap_diff.py", survivors)
```

- [ ] **Step 3: Run mutation testing (serialize — nothing else importing `src`)**

Run: `uv run python formal/diff/mutate.py`
Expected: all 5 seeded mutants killed by `test_next_tier_cap_diff.py`; zero survivors.

- [ ] **Step 4: Commit**

```bash
git add formal/diff/mutate.py
git commit -m "formal(skill-grind): mutation anchors for next_tier cores (0 survivors)"
```

---

### Task 6: Dispatch suppress branch + proof + tests

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/skill_step_dispatch.py` (add `dampened` param + wrapper branch)
- Modify: `formal/Formal/SkillStepDispatch.lean` and/or `formal/Formal/Extracted/SkillStepDispatch.lean` (extend the wrapper theorem to cover the new branch)
- Test: `tests/test_ai/test_skill_step_dispatch.py`

**Interfaces:**
- Consumes: Task 1 `next_tier_dampened_pure` (the caller computes the bool; the dispatch takes the bool).
- Produces: `skill_step_dispatch_pure(skill, current_level, committed_skill, committed_level, candidates, dampened=False)` — the extra `dampened: bool` keyword param; behavior unchanged when `dampened is False`.

- [ ] **Step 1: Write failing dispatch tests**

```python
# tests/test_ai/test_skill_step_dispatch.py  (add to existing file; reuse the _c() helper)
from artifactsmmo_cli.ai.tiers.skill_step_dispatch import skill_step_dispatch_pure


def test_dampened_suppresses_throwaway_grind():
    cands = [_c("copper_dagger", level=1, missing=0, wanted=False)]
    d = skill_step_dispatch_pure("gearcrafting", 1, "", 0, cands, dampened=True)
    assert d.kind == "suppress"


def test_dampened_does_not_suppress_wanted_craft():
    cands = [_c("iron_helmet", level=1, missing=0, wanted=True)]
    d = skill_step_dispatch_pure("gearcrafting", 1, "", 0, cands, dampened=True)
    assert d.kind == "grind" and d.code == "iron_helmet"


def test_not_dampened_grinds_as_before():
    cands = [_c("copper_dagger", level=1, missing=0, wanted=False)]
    d = skill_step_dispatch_pure("gearcrafting", 1, "", 0, cands, dampened=False)
    assert d.kind == "grind" and d.code == "copper_dagger"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_skill_step_dispatch.py -k dampened -q`
Expected: FAIL — `skill_step_dispatch_pure() got an unexpected keyword argument 'dampened'`.

- [ ] **Step 3: Add the wrapper branch**

In `skill_step_dispatch.py`, change the signature and the tail of `skill_step_dispatch_pure`:

```python
def skill_step_dispatch_pure(
    skill: str, current_level: int,
    committed_skill: str, committed_level: int,
    candidates: list[DispatchCandidate],
    dampened: bool = False,
) -> DispatchDecision:
    # ... existing full/relaxed pick + combine_dispatch_pure unchanged ...
    kind, code = combine_dispatch_pure(skill, current_level, committed_skill,
                                       committed_level, full_pick, relaxed_pick)
    if kind == "grind" and dampened:
        picked = next((c for c in candidates if c.code == code), None)
        if picked is not None and not picked.wanted:
            return DispatchDecision(kind="suppress", code="")
    return DispatchDecision(kind=kind, code=code)
```

Update the docstring to note the `dampened` throwaway-suppress branch (guarded by `not wanted` so committed/wanted progress is never blocked).

- [ ] **Step 4: Run tests + full dispatch suite + types**

Run: `uv run pytest tests/test_ai/test_skill_step_dispatch.py -q && uv run mypy src/artifactsmmo_cli/ai/tiers/skill_step_dispatch.py`
Expected: PASS; mypy `Success`. Existing dispatch tests still green (default `dampened=False`).

- [ ] **Step 5: Extend the dispatch proof**

Update `formal/Formal/SkillStepDispatch.lean` (and the extracted mirror if the wrapper is extracted) so the model reflects the `dampened`-guarded suppress branch. The `forward_progress` / `grind_respects_full_reservation` theorems must still hold: the new branch only converts a `grind` on a `¬wanted` pick into `suppress`, so committed/wanted-progress guarantees are preserved. If the wrapper is extracted, re-run `uv run python scripts/extract_lean.py` and `bash formal/gate/check_extraction.sh`.

Run: `cd formal && lake build && bash gate/check_no_sorry.sh`
Expected: clean build, no sorry.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/skill_step_dispatch.py tests/test_ai/test_skill_step_dispatch.py formal/Formal/SkillStepDispatch.lean
git commit -m "feat(skill-grind): dampened suppress branch in skill_step_dispatch (not-wanted guarded)"
```

---

### Task 7: Impure wiring + integration test + full gate

**Files:**
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py` (`objective_step_goal`, `ReachSkillLevel` branch ~688-759; and `_skill_dispatch_candidates` ~210-266 only if it needs to forward the bool — prefer computing `dampened` in `objective_step_goal` and passing directly to `skill_step_dispatch_pure`)
- Test: `tests/test_ai/test_strategy_driver.py` (or the existing objective-step-goal test module)

**Interfaces:**
- Consumes: Task 1 cores, Task 6 dispatch param. Uses existing `state.skills`, `state.level`, `game_data.all_item_stats`, `game_data.max_skill_level`, `ITEM_TYPE_TO_SLOTS`.

- [ ] **Step 1: Add the hoist + dampened computation**

In the `ReachSkillLevel` branch of `objective_step_goal`, after `current = state.skills.get(step.skill, 0)` (line ~705) and before the `skill_step_dispatch_pure` call (line ~748), add:

```python
skill_items = [
    SkillItem(
        stats.crafting_skill, stats.crafting_level, stats.level,
        (stats.type_ in ITEM_TYPE_TO_SLOTS or stats.subtype == "tool"),
    )
    for stats in game_data.all_item_stats.values()
    if stats.crafting_skill
]
next_cap = next_tier_cap_pure(step.skill, state.level, skill_items,
                              game_data.max_skill_level)
dampened = next_tier_dampened_pure(current, next_cap)
```

and pass `dampened=dampened` into the `skill_step_dispatch_pure(...)` call. Add module-top imports:

```python
from artifactsmmo_cli.ai.tiers.next_tier_cap import (
    next_tier_cap_pure,
    next_tier_dampened_pure,
)
from artifactsmmo_cli.ai.tiers.skill_target_curve import SkillItem
from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
```

(Check which of these are already imported in `strategy_driver.py` and reuse; do not duplicate.)

- [ ] **Step 2: Write the integration test**

```python
# tests/test_ai/test_strategy_driver.py — build a WorldState/GameData fixture where a
# gear-crafting skill can already craft all next-tier gear at a low char level.
def test_objective_step_suppresses_speculative_grind_when_tier_ahead(...):
    # skill=gearcrafting, current skill >= next-tier cap, char_level low,
    # only a throwaway (not wanted) craftable → objective_step_goal returns None.
    goal = objective_step_goal(ReachSkillLevel("gearcrafting", 50), state, game_data, ctx)
    assert goal is None


def test_objective_step_grinds_when_not_tier_ahead(...):
    # same but current skill < next-tier cap → returns a GatherMaterialsGoal.
    goal = objective_step_goal(ReachSkillLevel("gearcrafting", 50), state, game_data, ctx)
    assert goal is not None
```

Fill the fixtures using the existing `test_strategy_driver.py` builders (find how other `objective_step_goal` tests construct `state`, `game_data`, `ctx`; reuse those helpers rather than hand-rolling). Include a third test: a `wanted`/committed next-tier item present → still returns a grind goal (need-exemption).

- [ ] **Step 3: Run the integration tests + full suite**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py -q`
Then the whole suite with coverage: `uv run pytest -q`
Expected: all PASS; 0 errors/warnings/skips; 100% coverage (add tests for any uncovered new lines).

- [ ] **Step 4: Run the full formal gate (serialized — nothing else importing `src`)**

Run: `bash formal/gate.sh`
Expected: `ALL GATE PARTS PASSED`.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/strategy_driver.py tests/test_ai/test_strategy_driver.py
git commit -m "feat(skill-grind): wire next-tier dampener into objective_step_goal"
```

- [ ] **Step 6: Live sanity check (optional but recommended)**

Use the plan CLI to confirm the dampener changes a real decision without breaking planning:

Run: `uv run artifactsmmo plan <char>`
Expected: for a character whose gear-crafting skill already covers the next tier at a low char level, the printed plan no longer selects a throwaway skill-grind; for a character not tier-ahead, the skill grind still appears.

---

## Self-Review

**Spec coverage:**
- Gate predicate (collapsed, one condition) → Task 1 (`next_tier_dampened_pure`) + Task 6 branch. ✓
- `next_tier_cap_pure` band arithmetic (10-level bands) → Task 1 + Task 2 model. ✓
- Gear-crafting-only scope (self-enforcing via `cap=0`) → Task 1 `test_cap_ignores_non_gear...`, Task 2 `empty_band_not_dampened`, Task 7 cooking-style fixture. ✓
- Hard gate / suppress → Task 6. ✓
- Need-exemption (`not wanted`) → Task 6 `test_dampened_does_not_suppress_wanted_craft`, Task 7 committed-item test. ✓
- Endgame target + `+3` curve untouched → no task modifies `objective_roots`/`skill_target_curve`; dampener acts only at dispatch. ✓
- Formal pipeline (model/extract/bridge/diff/mutation) → Tasks 2–5. ✓
- Honest theorems, no vacuity; self-lift as regression test not theorem → Task 2 (theorems), Task 7 not required but Task 1 `test_band_rolls_up_across_decade_boundary` covers roll-up at the pure level. ✓
- `LevelSkillGoal` rename (out of scope) → not planned, correctly. ✓

**Placeholder scan:** `sorry` appears once intentionally in Task 2 Step 1 with an explicit discharge step (Step 2) — not a plan placeholder. Oracle field-key/name confirmations are flagged as "read the curve diff test to confirm" with the exact reference file. No `TODO`/`TBD`.

**Type consistency:** `next_tier_cap_pure(skill, char_level, items, max_skill_level) -> int` and `next_tier_dampened_pure(current_skill, next_tier_cap) -> bool` used identically in Tasks 1, 4, 6, 7. Dispatch param `dampened: bool` consistent across Tasks 6–7. `SkillItem` field order `(craft_skill, craft_level, item_level, gear_relevant)` matches `skill_target_curve.py`.

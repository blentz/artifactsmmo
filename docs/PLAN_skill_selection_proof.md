# PLAN: formally prove recipe-aware skill-grind selection (same-skill invariant)

Status: CLOSED 2026-06-13 — IMPLEMENTED + PROVEN + GATED on branch
`fix/skill-selection-same-skill`. Pure core `skill_grind_selection_pure`
extracted to `Formal/Extracted/SkillGrindSelection.lean`; four role theorems
kernel-checked in `Formal/SkillGrindSelection.lean` (`grind_same_skill`,
`grind_in_level`, `grind_obtainable`, `grind_actionable`; axioms ⊆ {propext,
Quot.sound}); `Contracts.lean` + `Manifest.lean` pins; oracle arm + differential
(`test_skill_grind_selection_diff.py`, 400 examples; full diff suite 502 passed);
mutation gate OK with all 4 anchors KILLED — including the load-bearing
"drop same-skill guard" cross-skill mutant. pytest 3263 @ 100% cov. Live-verified
the original defect is fixed (weaponcrafting grinds fishing_net, plan_len 57).
Adversarial review: differential calls the live core; theorems non-vacuous.

## The defect (live, trace 2026-06-13 13:38 cycles 15-23)

Committed to `ReachSkillLevel(weaponcrafting, 5)` (top root, score 2.88), but the
bot executes `GatherMaterials(wooden_shield)` — a **gearcrafting** grind (root #3,
score 2.4). weaponcrafting `skill_xp` stays 0 though **6 weaponcrafting recipes
are craftable at level 1** (copper_dagger, wooden_staff, copper_axe,
apprentice_gloves, copper_pickaxe, fishing_net).

Root cause (CONFIRMED by live reproduction 2026-06-13, Robby weaponcrafting 1):
`skill_grind_target("weaponcrafting")` returns **wooden_staff** (recipe
`{wooden_stick:1, ash_wood:4}`). `wooden_stick` has NO recipe and is not
gatherable → the `GatherMaterials(wooden_staff)` goal GOAP-fails (`plan_len 0`),
though the cheap `is_plannable` skill-gate check returns True. `skill_grind_target`
ranks by `(-mats_missing, craft_level, code)` — fewest MISSING materials — so it
prefers wooden_staff (some inputs on hand) over the OBTAINABLE copper_dagger
(`copper_bar ← copper_ore`, gatherable, GOAP plan_len 57). It never checks the
recipe inputs are reachable. THEN the arbiter (`select` keeps the first plannable
candidate) discards the un-planning weaponcrafting goal and falls to the next
root's step — the gearcrafting grind (wooden_shield, plans fine). No same-skill
fallback, so the committed objective is silently abandoned cross-skill.

TWO compounding defects: (1) selection picks an unobtainable in-skill target;
(2) the arbiter falls cross-skill when the committed skill's grind can't plan.
"Proper action" therefore means **same-skill AND obtainable**.

## Proof boundary (Phase 0 decision — "same-skill invariant")

Extract the skill-grind SELECTION into a pure, total, decidable core and prove it
**always targets the committed skill**, making the cross-skill outcome
unrepresentable at the selection layer. The code FIX makes the impure step→goal
resolution honor it (try the in-skill craft, then the in-skill LevelSkill
fallback — both same-skill — before any cross-skill root).

### Pure core — `src/artifactsmmo_cli/ai/tiers/skill_grind_selection.py`

```python
@dataclass(frozen=True)
class GrindCandidate:
    code: str
    craft_skill: str
    craft_level: int
    mats_missing: int   # hoisted: sum of unheld recipe inputs (>=0)

def skill_grind_selection_pure(
    skill: str, current_level: int, candidates: list[GrindCandidate],
) -> str:
    """The in-skill item to craft for `skill` XP at `current_level`, or "" =
    'no in-skill craft available -> LevelSkill fallback (still THIS skill)'.
    Considers ONLY candidates with craft_skill == skill and craft_level <=
    current_level; among those, max by (-mats_missing, craft_level, code)."""
```
This is `skill_grind_target` refactored to take pre-hoisted candidates (so it is
pure/extractable). The impure wrapper `skill_grind_target(skill, state, game_data,
reserved)` hoists `GrindCandidate`s from `game_data.all_item_stats` + holdings and
delegates; behavior byte-identical (differential-locked).

### Theorem roles (`formal/Formal/SkillGrindSelection.lean`)

1. **`grind_same_skill`**: the returned code, when non-empty, belongs to a
   candidate whose `craft_skill == skill`. (Selection only ever ranges over
   same-skill candidates.) — THE load-bearing invariant.
2. **`grind_in_level`**: the returned candidate's `craft_level <= current_level`.
3. **`grind_actionable`**: `(∃ c ∈ candidates, c.craft_skill = skill ∧
   c.craft_level <= current_level) ↔ result ≠ ""`. (A craftable in-skill recipe
   exists iff a craft target is returned; else the empty "" sentinel ⇒ the
   same-skill LevelSkill fallback.)
4. **`grind_deterministic` / optimality**: the result maximizes
   `(-mats_missing, craft_level, code)` over the feasible set (matches the live
   tie-break, differential-locked).

## The code fix (Phase 2)

`objective_step_goal` ReachSkillLevel branch + the arbiter step resolution: a
`ReachSkillLevel(skill,N)` step must ALWAYS resolve to a SAME-SKILL goal that the
arbiter can execute. Concretely:
- primary: `GatherMaterials(in-skill craft_one)` (when selection ≠ "");
- same-skill fallback: `LevelSkillGoal(skill)` (always plannable — the
  deadlock-breaker) tried BEFORE any cross-skill root when the primary is
  unplannable.
So the arbiter never falls cross-skill for a committed below-target skill. The
pure core guarantees the selection is same-skill; the fix guarantees the
EXECUTION stays same-skill under unplannability.

Regression test (the live counterexample): committed weaponcrafting-5 with a
weaponcrafting recipe craftable but its GatherMaterials unplannable ⇒ the
resolved/executed goal still grinds weaponcrafting (GatherMaterials in-skill or
LevelSkill(weaponcrafting)), NEVER a gearcrafting goal.

## Phases (formal-development workflow)

- **P1 Model+prove**: `SkillGrindSelection.lean` computable def + the 4 role
  theorems, kernel-checked, axioms ⊆ {propext, Classical.choice, Quot.sound}.
- **P2 Implement/fix**: the pure `skill_grind_selection.py` core; refactor
  `skill_grind_target` to delegate; fix `objective_step_goal`/arbiter same-skill
  fallback. TDD; the live-counterexample regression test.
- **P3 Gate**: register in `scripts/extract_lean.py` → `Extracted/…`; bridge
  (next free `Bridges*.lean`); `Oracle.lean` arm; `formal/diff/
  test_skill_grind_selection_diff.py`; mutation anchors (drop the
  `craft_skill==skill` guard ⇒ a mutant that returns cross-skill MUST be killed
  by `grind_same_skill`'s differential); `Contracts.lean` + `Manifest.lean` pins.
- **P4 Adversarial review**: confirm `grind_same_skill` is non-vacuous (a witness
  where a same-skill craftable exists) and that the differential calls the LIVE
  `skill_grind_target`, not an inlined formula.
- **P5 Coverage**: 100% on the new core + fix; the cross-skill regression test.

## Done = the cross-skill mutant dies

The mutation that deletes the `craft_skill != skill` guard (letting selection
return a cross-skill item) MUST be killed by the `grind_same_skill` differential.
That is the mechanical proof the invariant has teeth — and the formal expression
of "recipe-aware-skilling selects the proper (same-skill) action in all cases."

# PLAN: wanted-first skill-grind selection

**Goal:** The skill-grind must prefer items the bot actually WANTS (a current
gear/tool target `∈ target_gear ∪ target_tools`, i.e. `is_target`) over
throwaways, instead of the pure "fewest materials on hand" greed that made Robby
craft `apprentice_gloves` (equip_value 10, feathers in bag) to level
weaponcrafting while ignoring `copper_dagger` (equip_value 83, the real weapon).

**Ordering key change** (`skill_grind_selection_pure._beats`, the proved core):
`(-mats_missing, craft_level)` → `(wanted desc, -mats_missing, craft_level)`.
`best is None → True` preserved (load-bearing for `step_feasible_some`).

## Why proofs survive
`_beats` is opaque to every SkillGrindSelection role theorem except the
`none`-case in `step_feasible_some` (needs `_beats c none = true` — preserved).
SkillStepDispatch theorems treat `skill_grind_selection_pure`'s RESULT as given
(which pass wins, not intra-pass order) → survive untouched. GrindLadder uses
`FlagInputs.is_target` → untouched.

## Lockstep
- **skill_grind_selection.py**: `GrindCandidate += wanted: bool`; `_beats` gains
  the wanted-first clause (first comparison, before mats_missing).
- **skill_step_dispatch.py**: `DispatchCandidate += wanted: bool`; `_to_grind`
  passes `wanted=c.wanted`.
- **strategy_driver.py**: `DispatchCandidate(..., wanted=fi.is_target)`.
- **skill_grind_target.build_grind_candidates**: `wanted=False` (standalone path
  is not live; conservative default).
- Regenerate **Extracted/SkillGrindSelection.lean** (`scripts/extract_lean.py`).
- **SkillGrindSelection.lean**: existing proofs unchanged; ADD
  `beats_prefers_wanted` (c.wanted ∧ ¬best.wanted ⇒ _beats=true) and
  `unwanted_not_beats_wanted` (¬c.wanted ∧ best.wanted ⇒ _beats=false). Pin in
  Contracts + Manifest.
- **Oracle.lean**: both decoders (skill_grind_selection, skill_step_dispatch)
  add the `wanted` bool field per candidate.
- **differentials** (test_skill_grind_selection_diff, test_skill_step_dispatch_diff):
  encode `wanted`; new scenario — a WANTED higher-mats item beats an UNWANTED
  lower-mats item (the copper_dagger-over-apprentice_gloves case).
- **mutate.py**: anchor deleting the `_beats` wanted clause (killed by the new
  scenario).
- **unit tests**: skill_grind_selection, skill_step_dispatch, strategy_driver.

Gate: build + axioms(safety 3) + extraction drift + proof-concept index +
differential + mutation green; 100% cov.

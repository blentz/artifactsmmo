# Liveness quarantine

This directory hosts the liveness-proof program (planned in
`docs/PLAN_liveness.md`). Modules here are the **only** place in the formal
project allowed to `import Mathlib`. Per the user-approved Phase 19a decision
(2026-05-30) and the `project_liveness_axiom_split` memory, the axiom budget
splits as follows:

- Safety modules (everything outside `Formal/Liveness/`): axioms must remain
  a subset of `{propext, Classical.choice, Quot.sound}`. The safety axiom
  gate (`formal/gate/check_axioms_safety.sh`) enforces this.
- Liveness modules (this directory): axioms may additionally include
  Mathlib's standard axiom set, enumerated in
  `formal/gate/check_axioms_liveness.sh`. The liveness gate records a
  per-theorem axiom manifest at `formal/gate/liveness_axioms.manifest`.

Cross-namespace pollution (a safety module transitively pulling in a
Mathlib-only axiom) is a gate failure.

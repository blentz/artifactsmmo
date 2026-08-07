# Ratified design decisions (Phase 0, 2026-08-07)

Answered by the user via `AskUserQuestion` before any clause was written. These
are the premises the spec is built on; they are NOT witnesses (nothing adversarial
found them) and they do not enter `WITNESSES.md`.

| # | Question | Answer |
|---|---|---|
| 1 | Terminal objective | **Character level 50.** Gear, skills, gold are instrumental — valued only through their effect on cycles-to-50. |
| 2 | `cheapest_path_to_level` is 10.7x pessimistic | **Calibrate first, as a sequenced phase 0**, before `J` is specified on top of it. |
| 3 | Behaviour when nothing reaches the objective | **Furthest progress, then cycles.** A finite `J` beats every non-finite `J`. |
| 4 | Scope | **Branch choice only.** Focus aging, d'Hondt seats, synergy, achievability and servability promotion all stay. |

## Consequence of #2 for this spec

The artifact under test consumes projections as **inputs**. Oracle accuracy is
explicitly out of scope here and is listed under "Explicitly NOT under test" in
`SPEC.md`. The calibration work is a separate deliverable that must land *before*
the choice core goes live, and that sequencing belongs in the build plan, not in
these clauses.

## Evidence behind the decisions (measured, this session)

- `Branch.GEAR` chosen in **2,950 of 2,950** cycles; `branch_pick_pure`'s pivot
  `band_adequate = winnable AND NOT has_structural_upgrade` is unsatisfiable
  against a 50-level catalogue.
- 13h overnight run: **0** character level-ups, versus 7 in the comparable 14h
  pre-fix run.
- R2D2 @ level 12: reachable ceiling 17 by fighting; **4 of 7** gear candidates
  raise that ceiling by **zero**.
- `greater_wooden_staff` (the tree's actual pick) raises it 17 -> 25, so the pick
  is sound while the *branch* is not.
- Projection reports 7,698 cycles/level; traces show **717** observed. 10.7x.

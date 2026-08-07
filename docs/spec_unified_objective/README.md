# Unified progression objective `J` — certified-so-far specification

The design that replaces `branch_pick_pure`'s boolean gear/xp pivot with a single
scalar objective. **Not yet implemented.** This directory is the spec the
implementation must satisfy.

## Why this exists

`branch_pick_pure` is a lexicographic pivot, and its own docstring says so:

> *"Gear-first until the band's loadout is adequate; then xp to the next
> milestone. One boolean pivot — no scalar competition (the design's core bet)."*

Its switch condition is `band_adequate = winnable_monster_exists AND NOT
has_structural_upgrade(...)`. Against a 50-level catalogue the second conjunct is
never true, so the pivot never flips: measured **2,950 of 2,950 cycles chose
GEAR**, and a 13-hour five-character run gained **0 character levels** against 7 in
the comparable run before it. The planner reported
`projected_cycles_to_max: "inf"` in all 7,967 cycles of both runs.

Lexicographic priority returns one extreme point of a Pareto front. `J` replaces
it with a common currency — cycles to the terminal objective — so gear and XP
compete on one scale and the trade-off point emerges instead of being legislated.

## Files

| file | what it is |
|---|---|
| `SPEC.md` | 15 clauses (S-009 withdrawn, id retained). The contract. |
| `OBSERVATION.md` | Σ — the observation alphabet. All 12 dimensions carry a verdict. |
| `ONTOLOGY.md` | 11×9 subject×stimulus grid: 41 DEFINED, 31 THIN, 20 MISSING, 7 IGNORE. |
| `WITNESSES.md` | The witness ledger. **This is the acceptance suite** — harvest tests from it. |
| `DECISIONS.md` | The eight ratified design decisions and the measurements behind them. |

## Status — read this before trusting it

Produced with `spec-forge`. **Phases 0, 0.5 and 1 completed and gated.** Phase 2
(the adversarial underdetermination loop) ran ONE round which was **VOIDED**: one
of 73 agents read implementation source, so by that gate's rule none of its
findings are evidence about the spec. The single finding retained (`W-001`) is
retained *only* because it is verifiable by reading two clauses side by side, with
no agent evidence involved; everything else that round produced was discarded.

**This spec therefore carries NO completeness certificate.** It has not gone dry,
Phase 2b (contradictions), 2c (ratification) and 3 (the anti-padding mutation
gate) have not run. It is a well-interrogated design document, not a certified
one.

What it did buy, before any code existed:

* a **unit mismatch** in `J` itself — acquisition cost was in actions, the
  projection in cycles, and S-004 added them. Now S-010.
* the XP trunk was **unnameable** (zero cost does not identify it).
* an oracle crash and a genuinely unreachable objective were **indistinguishable**,
  so a crash would have ranked as progress. Now S-012.
* the empty input had **no defined return**. Now S-015.
* `S-009` was **self-defeating**: S-014 collapses the finite band's level field to
  the constant 50, so a level comparison in that band compares a constant with
  itself, pinning all gear behind the trunk. Withdrawn — see `W-001`.

## Sequencing

Phase 0 of the build — correcting the cycle oracle's unit — is **done and merged**
(`f32542a2`). It had to precede `J`, because an objective built on a projection
that was ~80x wrong would have optimised against a fiction.

Remaining: implement the choice core against these clauses under the usual formal
gate (Lean roles, mechanical extraction, differential, mutation anchors, trace
replay), then wire it into `branch_pick_pure`'s seat.

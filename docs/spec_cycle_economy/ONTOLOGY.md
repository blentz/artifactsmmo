# Ontology grid — <project>

**Class:** <declared at run time>
**Subjects:** <extracted by workflows/ontology.js — do not hand-write>
**Stimuli:** <extracted by workflows/ontology.js — do not hand-write>

<!--
Both axes are extracted from the draft spec, then CHALLENGED. The most common gap
in any specification is an entity the author never thought to name — it does not
show up as a MISSING cell, it shows up as no cell at all.

Time, failure, retry and concurrency are stimuli. Almost every draft spec omits
all four. The lint requires them on the axis, or an explicit waiver below.

To waive a required stimulus category, state why:
**Stimulus-waivers:** concurrency — single-writer by construction, enforced by the queue.
-->

## Grid

Every cell of the cross-product gets exactly one verdict. No blanks — a blank is
not "no behavior," it is an unasked question.

| Verdict   | Meaning                                          | Requires             |
|-----------|--------------------------------------------------|----------------------|
| `DEFINED` | The spec states the behavior.                    | ≥1 clause citation   |
| `THIN`    | The spec gestures at it; a real decision is open. | ≥1 clause citation  |
| `MISSING` | The spec says nothing.                           | nothing — it *is* the finding |
| `IGNORE`  | Deliberately out of scope.                       | a written justification |

| Subject | Stimulus | Verdict | Clauses | Justification |
|---|---|---|---|---|

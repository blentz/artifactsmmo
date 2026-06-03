# Item 1g — Path simplification (post-1g-A3 audit)

## Audit finding
After Items 1g-A1/A2/A3 shipped, audit of axiom consumers shows:

- `accept_cancel_loop_bound` — referenced ONLY in docstrings and the
  audit `#print axioms` line. NOT consumed in any actual proof.
- `lifecycle_progress_from_bounds` — the SOLE axiom actually used at
  `CumulativeProgress.lean:1216` inside `cumulative_progress_under_no_wait`.

## Implication
The original 1g-A4 sub-item (prove `accept_cancel_loop_bound_proven`)
is UNNECESSARY for axiom removal. Once `lifecycle_progress_from_bounds`
is discharged, both axioms can be deleted simultaneously
(accept_cancel_loop_bound becomes dead code).

## Revised remaining work
- 1g-B: prove `lifecycle_progress_from_bounds_proven` with the same
  signature. Strategy:
  1. Use `cumulative_progress_under_no_wait_restricted` (already
     proven) as the base case for progressMeans-only trajectories.
  2. Extend to unrestricted trajectories by induction on cycle count
     + Item 1f bounded-plan witness for lifecycle means.
  3. Key lemma: along any trajectory satisfying the no-wait + perception
     hypotheses, either progressMeans fires (apply restricted form) or
     a lifecycle sequence (accept→cancel/pursue→complete) executes
     within bounded steps.
- 1g-C: switch consumer (CumulativeProgress:1216) to the proven
  version; delete both axioms; drop allow-list entries.

## Estimate
- 1g-B: 1-2 focused sessions (the trajectory case analysis is the
  hard part).
- 1g-C: <1 session.

## Items 1g-A3 trajectory lemmas are NECESSARY infrastructure
The pool/seen lemmas (taskPool invariant, seen monotonicity, length
bounds) underpin the lifecycle-sequence bound used by 1g-B. They are
NOT dead code — they're the per-step basis for the multi-completion
arithmetic in 1g-B.

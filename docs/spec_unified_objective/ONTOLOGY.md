# Ontology grid

**Subjects:** A. rank_and_choose — whole-core contract (purity, totality, return shape), B. Input admission & descriptor-domain validation, C. Band classification (finite / unreachable / FAILED), D. J computation (acquisition cost + projected cycles-to-50), E. Finite-band ordering (J-minimisation), F. Unreachable-band ordering (furthest level, then acquisition cost), G. FAILED-band placement and internal ordering, H. Tie-break rule, I. Trunk-priority guard (gear-with-no-progression-value), J. Ranking assembly & totality of the returned order, K. Chosen-candidate extraction
**Stimuli:** 1. normal / well-formed input, 2. boundary / extremal-but-admissible values, 3. degenerate / empty, singleton, or all-identical input, 4. conflicting / two clauses pull opposite ways on the same input, 5. absent / a required datum or entity is missing from the input, 6. expiry · staleness · TTL (projection age; J carried across calls), 7. retry · duplicate · replay (the same stimulus arrives twice), 8. dependency failure (the projection producer / cycle oracle is down or out-of-contract), 9. concurrent stimulus (two calls at once; shared memo; caller mutation during the call)
**Stimulus-waivers:** NO stimulus category is waived wholesale. Justification for keeping all four of the mandated categories on the axis, even though S-001 declares the artifact a pure total function:

(a) EXPIRY/TTL is live despite purity. The core is handed projections it did not compute. A descriptor carries no epoch, version, or as-of level, and the spec's own DELIBERATE HOLES list admits "whether `J` is recomputed per call or may be carried across calls". A projection produced at level 17 and consumed at level 19 is a stale input the spec has no vocabulary to reject or even detect. Purity makes the core insensitive to the *clock*; it does not make it insensitive to *age*.

(b) DEPENDENCY FAILURE is live and is in fact first-class in the alphabet: FAILED (S-002, S-012) IS the encoding of "the producer could not compute". So the dependency-failure column is not hypothetical — it is the column where S-012's carve-outs are exercised, and where total producer failure (every candidate FAILED) is unspecified.

(c) RETRY/REPLAY is live in two forms the spec distinguishes badly: byte-identical re-invocation (settled by S-001/S-008) versus the domain's actual replay — the caller re-plans after a candidate "proves unservable" (S-011) and the producers re-emit the same logical set, possibly permuted, possibly with the tried candidate still in it. S-011 posits a fallback protocol with no input field to express it.

(d) CONCURRENCY is waived only cell-by-cell, on the record, as IGNORE with justification, and only for the per-candidate/pairwise pure arithmetic steps (C, E, F, H, I, K under stimulus 9), where S-001's by-value purity genuinely forecloses it. It is NOT waived for A, B, D, or J, where two live questions remain: caller-side mutation of the input sequence while the call is in flight (S-001 constrains only what the CORE mutates), and a J memo/cache shared between concurrent calls (the deliberate hole above turns memoization into shared mutable state).

<!-- ABSENT FROM THE SPEC ENTIRELY — the domain has these and the spec never names them,
     so they have no cell at all, not even a MISSING one. Decide whether they belong:
       - SERVABILITY / the unservable-candidate event. S-011 is built entirely on the caller 'falling back when a higher-ranked candidate proves unservable' — yet no descriptor field, no input argument, and no clause names servability, and nothing lets the caller tell the core 'I already tried rank 1 and it failed'. The core's central justification for returning a ranking at all references an entity that does not exist in its input domain.
       - EQUIPMENT SLOT. The domain plainly has slots, and two GEAR candidates for the SAME slot are mutually exclusive and mutually redundant. S-011's fallback chain will happily hand back a second helmet after the first helmet was unservable, and S-011's 'no candidate's projection may assume any other candidate was taken first' silently makes every same-slot pair's projections double-count the same slot. Slot is never named.
       - TARGET LEVEL as a parameter. '50' is welded into S-003, S-004, S-006 and S-014 as a literal. The domain has a level cap that has moved before (seasons) and characters who are already AT the cap. Nothing names the target as data.
       - THE ALREADY-TERMINAL CHARACTER. Current level = 50 is admissible under S-002 and makes every candidate's cycles-to-50 zero, collapsing J to pure acquisition cost — so the core silently ranks by 'cheapest thing to do' with no clause acknowledging the objective is already met. No 'goal already satisfied' entity exists.
       - RISK / VARIANCE / PROBABILITY OF FAILURE. J is a point estimate of cycles. In this domain a candidate can be lost (a fight can go wrong, a gather can be interrupted). The spec has no entity for the distribution behind the projection, so a 100-cycle certainty and a 100-cycle coin-flip are declared exactly equal by S-013's exactness rule.
       - WALL-CLOCK / COOLDOWN. S-010 fixes the unit as 'one executed action', but actions in this domain have wildly different real durations (cooldowns). Nothing names elapsed time, so a 40-action plan of 3s actions and a 40-action plan of 60s actions have identical J.
       - CANDIDATE KINDS BEYOND TRUNK|GEAR. S-002's kind enum has exactly two members. The domain plainly has task roots, event/raid roots, currency/gold roots, NPC-purchase roots and skill-grind roots. S-009 is written as if the world were bipartite; a third kind has no rank semantics at all, and 'the candidate whose kind is TRUNK' presupposes exactly one.
       - AN ERROR / DIAGNOSTIC CHANNEL. There is no error entity anywhere. S-001 forbids raising and forbids a 'could not decide' sentinel, S-002 declares certain inputs inadmissible, and no clause says what an inadmissible input produces. The core is given no way to say anything except a ranking.
       - PROVENANCE / EPOCH on a descriptor. Nothing ties a projection to the world state it was computed from, so the core cannot tell whether the sequence it holds is internally consistent (all projections from one snapshot) or a mixture from several.
       - PREREQUISITE / SHARED-MATERIAL COUPLING between candidates. S-011 forbids modelling it, but never names it, so nothing flags the ordinary case where two candidates consume the same finite material and their projections are jointly unachievable.
       - MULTIPLE CHARACTERS / CONTESTED SHARED RESOURCE. This is a multi-character planner; two characters ranking against the same bank stock or the same map tile is an event the core cannot see. Not named even to be excluded.
       - THE INPUT-POSITION KEY. S-002's last sentence ('Input position is available to the core') dangles: it is offered as capability but never named as the tie-break key, so S-008's 'definite order' has an unnamed determinant sitting right next to it.
       - REJECTION as an outcome. S-002 says a progress-losing candidate 'is inadmissible: the core is never asked' — an assertion about the caller, not a behavior. There is no filter, no drop, no reject entity, so the guarantee is unenforceable and untestable from inside the core.
       - MAGNITUDE BOUND on cost or cycles. S-013 demands exact integer/rational comparison and the DELIBERATE HOLES admit non-finite acquisition cost is undecided; nothing names a representable range, so 'non-negative count' silently includes numbers the arithmetic in S-004 may not be able to add.
-->

## Grid

| Subject | Stimulus | Verdict | Clauses | Justification |
|---|---|---|---|---|
| A. rank_and_choose — whole-core contract (purity, totality, return shape) | 1. normal / well-formed input | DEFINED | S-001, S-002, S-007 |  |
| A. rank_and_choose — whole-core contract (purity, totality, return shape) | 2. boundary / extremal-but-admissible values | DEFINED | S-007, S-005 |  |
| A. rank_and_choose — whole-core contract (purity, totality, return shape) | 3. degenerate / empty, singleton, or all-identical input | DEFINED | S-015, S-007 |  |
| A. rank_and_choose — whole-core contract (purity, totality, return shape) | 4. conflicting / two clauses pull opposite ways on the same input | THIN | S-005, S-009, S-007 |  |
| A. rank_and_choose — whole-core contract (purity, totality, return shape) | 5. absent / a required datum or entity is missing from the input | THIN | S-007, S-012, S-015, S-001 |  |
| A. rank_and_choose — whole-core contract (purity, totality, return shape) | 6. expiry · staleness · TTL (projection age; J carried across calls) | THIN | S-001 |  |
| A. rank_and_choose — whole-core contract (purity, totality, return shape) | 7. retry · duplicate · replay (the same stimulus arrives twice) | DEFINED | S-001, S-008 |  |
| A. rank_and_choose — whole-core contract (purity, totality, return shape) | 8. dependency failure (the projection producer / cycle oracle is down or out-of-contract) | THIN | S-012, S-002 |  |
| A. rank_and_choose — whole-core contract (purity, totality, return shape) | 9. concurrent stimulus (two calls at once; shared memo; caller mutation during the call) | THIN | S-001 |  |
| B. Input admission & descriptor-domain validation | 1. normal / well-formed input | DEFINED | S-002 |  |
| B. Input admission & descriptor-domain validation | 2. boundary / extremal-but-admissible values | DEFINED | S-002, S-014 |  |
| B. Input admission & descriptor-domain validation | 3. degenerate / empty, singleton, or all-identical input | DEFINED | S-002, S-015 |  |
| B. Input admission & descriptor-domain validation | 4. conflicting / two clauses pull opposite ways on the same input | THIN | S-002, S-001 |  |
| B. Input admission & descriptor-domain validation | 5. absent / a required datum or entity is missing from the input | MISSING |  |  |
| B. Input admission & descriptor-domain validation | 6. expiry · staleness · TTL (projection age; J carried across calls) | MISSING |  |  |
| B. Input admission & descriptor-domain validation | 7. retry · duplicate · replay (the same stimulus arrives twice) | THIN | S-002, S-007 |  |
| B. Input admission & descriptor-domain validation | 8. dependency failure (the projection producer / cycle oracle is down or out-of-contract) | MISSING |  |  |
| B. Input admission & descriptor-domain validation | 9. concurrent stimulus (two calls at once; shared memo; caller mutation during the call) | MISSING |  |  |
| C. Band classification (finite / unreachable / FAILED) | 1. normal / well-formed input | DEFINED | S-014, S-012, S-002 |  |
| C. Band classification (finite / unreachable / FAILED) | 2. boundary / extremal-but-admissible values | DEFINED | S-014 |  |
| C. Band classification (finite / unreachable / FAILED) | 3. degenerate / empty, singleton, or all-identical input | DEFINED | S-014, S-012 |  |
| C. Band classification (finite / unreachable / FAILED) | 4. conflicting / two clauses pull opposite ways on the same input | THIN | S-002, S-014 |  |
| C. Band classification (finite / unreachable / FAILED) | 5. absent / a required datum or entity is missing from the input | MISSING |  |  |
| C. Band classification (finite / unreachable / FAILED) | 6. expiry · staleness · TTL (projection age; J carried across calls) | MISSING |  |  |
| C. Band classification (finite / unreachable / FAILED) | 7. retry · duplicate · replay (the same stimulus arrives twice) | DEFINED | S-001 |  |
| C. Band classification (finite / unreachable / FAILED) | 8. dependency failure (the projection producer / cycle oracle is down or out-of-contract) | DEFINED | S-002, S-012 |  |
| C. Band classification (finite / unreachable / FAILED) | 9. concurrent stimulus (two calls at once; shared memo; caller mutation during the call) | IGNORE |  | Classification is a pure per-candidate predicate over two by-value fields of a descriptor the core does not mutate (S-001, S-014). With no shared state and no memo of its own, two simultaneous classifications cannot interact. Waived deliberately — but note this waiver depends on the D/9 memo question being answered 'recompute', which the spec has NOT answered. |
| D. J computation (acquisition cost + projected cycles-to-50) | 1. normal / well-formed input | DEFINED | S-004, S-010, S-003 |  |
| D. J computation (acquisition cost + projected cycles-to-50) | 2. boundary / extremal-but-admissible values | DEFINED | S-004, S-010, S-002 |  |
| D. J computation (acquisition cost + projected cycles-to-50) | 3. degenerate / empty, singleton, or all-identical input | THIN | S-003, S-006, S-008 |  |
| D. J computation (acquisition cost + projected cycles-to-50) | 4. conflicting / two clauses pull opposite ways on the same input | THIN | S-013, S-004 |  |
| D. J computation (acquisition cost + projected cycles-to-50) | 5. absent / a required datum or entity is missing from the input | THIN | S-006, S-012, S-014 |  |
| D. J computation (acquisition cost + projected cycles-to-50) | 6. expiry · staleness · TTL (projection age; J carried across calls) | THIN | S-001 |  |
| D. J computation (acquisition cost + projected cycles-to-50) | 7. retry · duplicate · replay (the same stimulus arrives twice) | DEFINED | S-001 |  |
| D. J computation (acquisition cost + projected cycles-to-50) | 8. dependency failure (the projection producer / cycle oracle is down or out-of-contract) | DEFINED | S-013 |  |
| D. J computation (acquisition cost + projected cycles-to-50) | 9. concurrent stimulus (two calls at once; shared memo; caller mutation during the call) | MISSING |  |  |
| E. Finite-band ordering (J-minimisation) | 1. normal / well-formed input | DEFINED | S-005, S-003, S-004 |  |
| E. Finite-band ordering (J-minimisation) | 2. boundary / extremal-but-admissible values | DEFINED | S-013, S-005 |  |
| E. Finite-band ordering (J-minimisation) | 3. degenerate / empty, singleton, or all-identical input | THIN | S-005, S-006, S-012 |  |
| E. Finite-band ordering (J-minimisation) | 4. conflicting / two clauses pull opposite ways on the same input | THIN | S-005, S-009 |  |
| E. Finite-band ordering (J-minimisation) | 5. absent / a required datum or entity is missing from the input | DEFINED | S-006, S-014, S-012 |  |
| E. Finite-band ordering (J-minimisation) | 6. expiry · staleness · TTL (projection age; J carried across calls) | MISSING |  |  |
| E. Finite-band ordering (J-minimisation) | 7. retry · duplicate · replay (the same stimulus arrives twice) | DEFINED | S-001, S-008 |  |
| E. Finite-band ordering (J-minimisation) | 8. dependency failure (the projection producer / cycle oracle is down or out-of-contract) | DEFINED | S-012 |  |
| E. Finite-band ordering (J-minimisation) | 9. concurrent stimulus (two calls at once; shared memo; caller mutation during the call) | IGNORE |  | Pairwise comparison of two already-computed exact scalars, over by-value data the core is forbidden to mutate (S-001, S-013). No shared state exists at this step, so a simultaneous second comparison cannot observe or perturb it. Deliberately waived. |
| F. Unreachable-band ordering (furthest level, then acquisition cost) | 1. normal / well-formed input | DEFINED | S-006, S-014 |  |
| F. Unreachable-band ordering (furthest level, then acquisition cost) | 2. boundary / extremal-but-admissible values | DEFINED | S-006, S-014 |  |
| F. Unreachable-band ordering (furthest level, then acquisition cost) | 3. degenerate / empty, singleton, or all-identical input | THIN | S-006, S-008 |  |
| F. Unreachable-band ordering (furthest level, then acquisition cost) | 4. conflicting / two clauses pull opposite ways on the same input | THIN | S-006, S-009 |  |
| F. Unreachable-band ordering (furthest level, then acquisition cost) | 5. absent / a required datum or entity is missing from the input | DEFINED | S-014, S-006 |  |
| F. Unreachable-band ordering (furthest level, then acquisition cost) | 6. expiry · staleness · TTL (projection age; J carried across calls) | MISSING |  |  |
| F. Unreachable-band ordering (furthest level, then acquisition cost) | 7. retry · duplicate · replay (the same stimulus arrives twice) | DEFINED | S-001, S-008 |  |
| F. Unreachable-band ordering (furthest level, then acquisition cost) | 8. dependency failure (the projection producer / cycle oracle is down or out-of-contract) | DEFINED | S-012, S-006 |  |
| F. Unreachable-band ordering (furthest level, then acquisition cost) | 9. concurrent stimulus (two calls at once; shared memo; caller mutation during the call) | IGNORE |  | Same reasoning as E/9: a two-key lexicographic comparison of by-value integer fields, with no state retained between comparisons (S-001). Waived on the record. |
| G. FAILED-band placement and internal ordering | 1. normal / well-formed input | THIN | S-012, S-008, S-007 |  |
| G. FAILED-band placement and internal ordering | 2. boundary / extremal-but-admissible values | MISSING |  |  |
| G. FAILED-band placement and internal ordering | 3. degenerate / empty, singleton, or all-identical input | THIN | S-007, S-012, S-015, S-001 |  |
| G. FAILED-band placement and internal ordering | 4. conflicting / two clauses pull opposite ways on the same input | THIN | S-009, S-012 |  |
| G. FAILED-band placement and internal ordering | 5. absent / a required datum or entity is missing from the input | MISSING |  |  |
| G. FAILED-band placement and internal ordering | 6. expiry · staleness · TTL (projection age; J carried across calls) | MISSING |  |  |
| G. FAILED-band placement and internal ordering | 7. retry · duplicate · replay (the same stimulus arrives twice) | DEFINED | S-001, S-008 |  |
| G. FAILED-band placement and internal ordering | 8. dependency failure (the projection producer / cycle oracle is down or out-of-contract) | DEFINED | S-012, S-007 |  |
| G. FAILED-band placement and internal ordering | 9. concurrent stimulus (two calls at once; shared memo; caller mutation during the call) | IGNORE |  | FAILED placement is a per-candidate predicate on a by-value tag (S-002, S-012); it reads no shared state and writes none, so simultaneous evaluation is indistinguishable from sequential. Waived deliberately. |
| H. Tie-break rule | 1. normal / well-formed input | THIN | S-008, S-002 |  |
| H. Tie-break rule | 2. boundary / extremal-but-admissible values | THIN | S-003, S-006, S-008 |  |
| H. Tie-break rule | 3. degenerate / empty, singleton, or all-identical input | THIN | S-008, S-002 |  |
| H. Tie-break rule | 4. conflicting / two clauses pull opposite ways on the same input | THIN | S-008, S-009 |  |
| H. Tie-break rule | 5. absent / a required datum or entity is missing from the input | MISSING |  |  |
| H. Tie-break rule | 6. expiry · staleness · TTL (projection age; J carried across calls) | MISSING |  |  |
| H. Tie-break rule | 7. retry · duplicate · replay (the same stimulus arrives twice) | THIN | S-008, S-002, S-011 |  |
| H. Tie-break rule | 8. dependency failure (the projection producer / cycle oracle is down or out-of-contract) | MISSING |  |  |
| H. Tie-break rule | 9. concurrent stimulus (two calls at once; shared memo; caller mutation during the call) | IGNORE |  | Whatever key S-008 ultimately names, it is computed from the arguments of a single call, which S-001 forbids the core to mutate; two in-flight calls share nothing. Waived — with the caveat that this waiver is void if the unnamed tie-break key turns out to be a process-global (e.g. an id counter or hash seed), which S-008's silence currently permits. |
| I. Trunk-priority guard (gear-with-no-progression-value) | 1. normal / well-formed input | DEFINED | S-009 |  |
| I. Trunk-priority guard (gear-with-no-progression-value) | 2. boundary / extremal-but-admissible values | DEFINED | S-009, S-002 |  |
| I. Trunk-priority guard (gear-with-no-progression-value) | 3. degenerate / empty, singleton, or all-identical input | MISSING |  |  |
| I. Trunk-priority guard (gear-with-no-progression-value) | 4. conflicting / two clauses pull opposite ways on the same input | THIN | S-009, S-005, S-006 |  |
| I. Trunk-priority guard (gear-with-no-progression-value) | 5. absent / a required datum or entity is missing from the input | MISSING |  |  |
| I. Trunk-priority guard (gear-with-no-progression-value) | 6. expiry · staleness · TTL (projection age; J carried across calls) | MISSING |  |  |
| I. Trunk-priority guard (gear-with-no-progression-value) | 7. retry · duplicate · replay (the same stimulus arrives twice) | DEFINED | S-001, S-008 |  |
| I. Trunk-priority guard (gear-with-no-progression-value) | 8. dependency failure (the projection producer / cycle oracle is down or out-of-contract) | DEFINED | S-012 |  |
| I. Trunk-priority guard (gear-with-no-progression-value) | 9. concurrent stimulus (two calls at once; shared memo; caller mutation during the call) | IGNORE |  | The guard is a pairwise predicate over the kind, outcome level and cost fields of two by-value descriptors within one call (S-009, S-001). No cross-call state. Waived deliberately. |
| J. Ranking assembly & totality of the returned order | 1. normal / well-formed input | DEFINED | S-007 |  |
| J. Ranking assembly & totality of the returned order | 2. boundary / extremal-but-admissible values | DEFINED | S-007 |  |
| J. Ranking assembly & totality of the returned order | 3. degenerate / empty, singleton, or all-identical input | DEFINED | S-015, S-007 |  |
| J. Ranking assembly & totality of the returned order | 4. conflicting / two clauses pull opposite ways on the same input | THIN | S-007, S-009, S-005 |  |
| J. Ranking assembly & totality of the returned order | 5. absent / a required datum or entity is missing from the input | THIN | S-007, S-002 |  |
| J. Ranking assembly & totality of the returned order | 6. expiry · staleness · TTL (projection age; J carried across calls) | MISSING |  |  |
| J. Ranking assembly & totality of the returned order | 7. retry · duplicate · replay (the same stimulus arrives twice) | DEFINED | S-001, S-008, S-007 |  |
| J. Ranking assembly & totality of the returned order | 8. dependency failure (the projection producer / cycle oracle is down or out-of-contract) | DEFINED | S-007, S-012, S-006 |  |
| J. Ranking assembly & totality of the returned order | 9. concurrent stimulus (two calls at once; shared memo; caller mutation during the call) | THIN | S-001 |  |
| K. Chosen-candidate extraction | 1. normal / well-formed input | DEFINED | S-007, S-005 |  |
| K. Chosen-candidate extraction | 2. boundary / extremal-but-admissible values | DEFINED | S-007, S-005 |  |
| K. Chosen-candidate extraction | 3. degenerate / empty, singleton, or all-identical input | THIN | S-007, S-012, S-015 |  |
| K. Chosen-candidate extraction | 4. conflicting / two clauses pull opposite ways on the same input | THIN | S-005, S-007, S-008 |  |
| K. Chosen-candidate extraction | 5. absent / a required datum or entity is missing from the input | DEFINED | S-015, S-001 |  |
| K. Chosen-candidate extraction | 6. expiry · staleness · TTL (projection age; J carried across calls) | MISSING |  |  |
| K. Chosen-candidate extraction | 7. retry · duplicate · replay (the same stimulus arrives twice) | THIN | S-011, S-001, S-008 |  |
| K. Chosen-candidate extraction | 8. dependency failure (the projection producer / cycle oracle is down or out-of-contract) | DEFINED | S-012 |  |
| K. Chosen-candidate extraction | 9. concurrent stimulus (two calls at once; shared memo; caller mutation during the call) | IGNORE |  | Extraction is 'take the head of the ranking' (S-007) inside a single pure call (S-001); it holds no state that a concurrent call could observe. Waived deliberately. |

# Specification — unified progression objective `J`

**Observation alphabet:** see `OBSERVATION.md`
**Toolchain:** Python 3.13 + mypy strict + Lean 4 mechanical extraction + Hypothesis differential + mutation gate + pytest @100%
**Agent class:** Claude Opus 5 (spec-forge adversaries and judges)

**Artifact under test:** ONE pure function — the **progression choice core**. It
receives a sequence of already-built candidate descriptors, each carrying its own
projected cost and projected outcome, and returns a total ordering over them
together with the chosen one.

The XP trunk is one of those candidates and is passed **in the sequence like any
other** — there is no separate "no-gear projection" argument. (Phase 1 caught the
earlier wording, which passed it both ways at once and never said what happened if
the two disagreed.)

**Explicitly NOT under test.** The following are BACKGROUND. They are named here
only so that no clause is written about them, and **no source file, module or
implementation of any of them may be consulted while reading this spec** — this
document is the entire subject matter, and anything an implementation happens to
do is not evidence about what this spec should say.

- **The cycle oracle** that computes how many cycles remain to level 50 from a
  given progression state. The core consumes its results as **inputs**, and **no
  clause here constrains its accuracy.** A unit defect in it (it had been
  denominated in seconds) was found and corrected before this spec was probed, so
  the projections the core receives are in the unit S-010 names. Residual
  inaccuracy remains and stays the producer's problem.
- **The projection producers** — whatever computes a candidate's acquisition cost
  and its projected outcome. The core never calls them; it is handed their
  results.
- **The surrounding selection machinery** that ages, interleaves and promotes
  candidates before or after this core runs. Scope decision: it stays, beneath
  the choice core.
- The arbiter, the planner, the goal layer, and every consumer of the decision.
- Which skill to grind, and every skill-grind selection concern.

---

### S-001 · The core is a pure total function

Given identical inputs the core returns identical outputs, on every call, with no
dependence on call order, elapsed time, or any state not passed as an argument. It
performs no I/O and mutates none of its arguments. It returns for every input
admitted by S-002 — it does not raise, loop forever, or return a sentinel meaning
"could not decide".

### S-002 · Input domain

The core receives the character's **current level** and a sequence of candidate
descriptors. A descriptor carries exactly these observable fields:

- an **identity** distinguishable from every other candidate in the sequence;
- a projected **acquisition cost**, a non-negative count of executed actions;
- a projected **outcome**, which is *either* a pair of (**highest character level
  reachable**, **cycles to reach level 50 from that outcome**) *or* the distinguished
  value **FAILED**, meaning the producer could not compute a projection at all.

A descriptor whose non-FAILED outcome names a highest reachable level **below the
current level** is inadmissible: the core is never asked to rank a candidate that
loses progress. The candidate sequence may be empty. Input position is available to
the core.

### S-014 · Unreachability is carried by the level field alone

A candidate's objective is unreachable exactly when its outcome's highest reachable
level is below 50. That single field decides membership of the non-finite band in
S-006; when it holds, the outcome's cycles-to-50 figure carries no meaning and is
not compared. No separate infinity value is required or permitted as a second
encoding of the same fact.

### S-015 · An empty sequence yields an empty ranking and no choice

Given an empty candidate sequence the core returns an empty ranking and an
explicitly absent choice. This absence means "there was nothing to choose between",
and is distinct from the "could not decide" sentinel S-001 forbids — which would
report failure on a non-empty input.

### S-010 · One cycle is one executed action

The acquisition cost and the projected cycle count are denominated in the same
unit: one cycle is one action the planner executes. S-004 may therefore add them
directly, with no conversion factor.

### S-011 · Choose-one; the ranking is a fallback chain

Only the chosen candidate is acted upon. The remaining ranking exists so the caller
may fall back when a higher-ranked candidate proves unservable. Consequently every
candidate's projected outcome is relative to the **same** current state, and no
candidate's projection may assume any other candidate was taken first. The core does
not model taking two candidates, and the ranking is not an execution order.

### S-012 · A FAILED projection never wins over a usable candidate

A candidate whose projected outcome is FAILED ranks below every candidate whose
outcome is not FAILED, and is not the chosen candidate whenever any non-FAILED
candidate is present. FAILED is distinct from an unreachable-but-computed outcome:
S-006 orders the latter by furthest progress, and must not be applied to the former.

### S-013 · Comparison is exact

The core compares quantities exactly, as integers or rationals, and performs no
floating-point comparison whose result could differ from the exact comparison. It
applies no significance threshold: two `J` values that differ at all are ordered by
that difference, however small. The accuracy of a projection is the producer's
contract, not this core's.

### S-003 · The objective is cycles to character level 50

Ranking is by a single scalar `J` denominated in **game cycles to reach character
level 50**, and by nothing else. Gear, skills, gold and equipment score are
instrumental: they enter `J` only through their effect on the projected outcome.
Two candidates with equal `J` are equally good under this clause; S-006 says what
happens then.

### S-004 · `J` combines acquisition cost with the resulting projection

`J` of a candidate is its acquisition cost plus the projected cycles from its
resulting outcome to level 50. Both terms are in cycles and are added, so a
candidate that saves fewer cycles than it costs ranks worse than taking nothing.

### S-005 · The chosen candidate is a `J`-minimiser

The core chooses a candidate whose `J` is less than or equal to every other
candidate's `J` in the set.

### S-006 · Unreachable objectives rank by furthest progress, then by cycles

When a candidate's objective is unreachable (S-014), `J` is not a finite number and
S-005 cannot separate it from any other such candidate. Among unreachable
candidates, one that reaches a strictly higher character level than another ranks
strictly better; among those reaching the same highest level, a strictly smaller
**acquisition cost** ranks strictly better. A candidate with finite `J` ranks better
than every unreachable candidate.

The second key is acquisition cost, not cycles-to-50, because S-014 makes
cycles-to-50 meaningless for exactly these candidates — ranking on it would compare
two figures the spec has just declared void. Acquisition cost is denominated in the
same unit (S-010), so "furthest progress, then fewer cycles" is preserved with the
only cycle count that still means anything here.

### S-007 · The ranking is a total order over exactly the input set

The core returns every candidate it was given, in rank order, with no candidate
omitted, duplicated, or invented — including candidates whose `J` is non-finite and
those whose outcome is FAILED. When the sequence is non-empty the first element of
the ranking is the chosen candidate; S-015 covers the empty sequence.

### S-008 · Ties are broken deterministically without appeal to identity text

When two candidates are indistinguishable under S-005 and S-006, the core still
returns a definite order, and it does so without comparing their identities as
text. Re-running with the same input yields the same order.

### S-009 · WITHDRAWN — the trunk guard carried no bits and was actively wrong

*(Id retained, never reused. Withdrawn 2026-08-07.)*

S-009 read: "a GEAR candidate whose projected outcome reaches no higher character
level than the trunk's, and whose acquisition cost is greater than zero, does not
rank ahead of the trunk."

**It was self-defeating.** S-014 makes unreachability exactly `level < 50`, so
every candidate in the FINITE band reports level 50 — including the trunk. S-009's
antecedent ("no higher level than the trunk's") is therefore true of *every*
positive-cost gear in that band. Read literally it pinned all gear behind the
trunk and destroyed gear selection outright; read charitably it never fired at
all. Nothing in the spec said which, and both readings satisfied every clause.

**And it was unnecessary in both bands.** Its intent — a gear that buys no
progression must not beat plain XP grinding — is already forced:

* FINITE band: such a gear has the trunk's outcome, so its `J` is
  `cost + C > 0 + C`, the trunk's `J`, and S-005 selects the trunk. When the gear
  *does* pay for itself (`J` strictly lower) S-005 selects the gear — the outcome
  S-009 forbade.
* UNREACHABLE band: same reachable level, so S-006's second key (acquisition
  cost) already prefers the trunk's zero over any positive cost.

S-005 and S-006 are strictly stronger than S-009 here, so this is not a
mutually-redundant pair: removing S-009 alone forbids everything it forbade and
nothing it should not have.

**Consequence.** No remaining clause reads a candidate's `kind`, so that field
left S-002 with this withdrawal. The trunk needs no marker because it is never
treated specially — it is simply the zero-cost candidate, and `J` handles it like
any other.

---

<!--
DELIBERATE HOLES — the design prose does not decide these, so no clause does.
Phase 2's job is to surface them; closing them here would blind it.

  * empty candidate set: S-002 admits it, no clause says what is returned
  * a candidate whose acquisition cost is non-finite
  * whether the XP trunk is guaranteed present in the input set
  * two candidates with identical projected outcome AND identical cost
  * a projected outcome BELOW the current level (a candidate that loses progress)
  * whether `J` is recomputed per call or may be carried across calls
  * how many times the projection may be consulted (Σ dim 9 says the count is IN,
    but no clause bounds it)
-->

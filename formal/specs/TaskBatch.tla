-------------------------------- MODULE TaskBatch --------------------------------
EXTENDS Integers, TLC

\* Mirrors src/artifactsmmo_cli/ai/task_batch.py:19 task_batch_size.
\* The recipe_closure / raw_material_units math (mats_per_unit, held_recipe) is
\* already proven in RecipeClosure.tla, so here those are abstracted as enumerated
\* inputs (mats, held). We verify the clamp max(1, min(remaining, fit, BATCH_CAP))
\* (task_batch.py final line) and its bound guarantees, including the early
\* returns of 1 for the non-items / no-total / nothing-remaining branches and the
\* negative-usable case (usable < mats => floor div drives k to 1).

BatchCap == 10   \* BATCH_CAP (task_batch.py:13)
MinFree  == 3    \* _MIN_FREE_SLOTS (task_batch.py:16)

Max(a, b) == IF a > b THEN a ELSE b
Min(a, b) == IF a < b THEN a ELSE b

Bool   == {TRUE, FALSE}
Totals == 0..4
Progs  == 0..4
Frees  == 0..6
Helds  == 0..4
Mats   == 1..3

Cases == { [it |-> it, tot |-> tot, prog |-> prog, free |-> free, held |-> held, mats |-> mats] :
             it \in Bool, tot \in Totals, prog \in Progs,
             free \in Frees, held \in Helds, mats \in Mats }

\* Python // is floor division. mats > 0 always (Mats = 1..3), so the divisor is
\* positive; only the dividend `usable` can be negative (free+held < MinFree).
\* For a<0, b>0 Python floor(a/b) = -ceil(-a/b) = -(((-a)+b-1) \div b); PlusPy
\* \div truncates toward zero for the negative-dividend case, hence this guard.
FloorDiv(a, b) == IF a < 0 THEN -(((-a) + b - 1) \div b) ELSE a \div b

BatchSize(c) ==
  IF ~c.it \/ c.tot <= 0 THEN 1
  ELSE LET remaining == c.tot - c.prog IN
       IF remaining <= 0 THEN 1
       ELSE LET usable == (c.free + c.held) - MinFree
                fit    == FloorDiv(usable, c.mats)
            IN Max(1, Min(Min(remaining, fit), BatchCap))

Correct(c) ==
  LET k == BatchSize(c)
      remaining == c.tot - c.prog
      taskBranch == c.it /\ c.tot > 0 /\ remaining > 0
      usable == (c.free + c.held) - MinFree
  IN /\ k >= 1
     /\ (~taskBranch => k = 1)
     /\ (taskBranch =>
            /\ k <= remaining
            /\ k <= BatchCap
            /\ (usable >= c.mats => k * c.mats <= usable)
            /\ (usable < c.mats => k = 1))

VARIABLE todo
Init == todo = Cases
Next == /\ todo # {}
        /\ \E c \in todo :
              /\ Assert(Correct(c), <<"TaskBatch FAIL", c>>)
              /\ todo' = todo \ {c}
================================================================================

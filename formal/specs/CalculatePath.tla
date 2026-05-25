----------------------------- MODULE CalculatePath -----------------------------
EXTENDS Integers, Sequences, TLC

\* Bounded grid: domain size = (5*5)^2 = 625 (s,d) pairs.
\* Coord -2..2 gives max Chebyshev distance 4, so paths fit in index range 0..4.
Coord == -2..2
MaxStep == 4
Abs(n)   == IF n < 0 THEN -n ELSE n
Max(a,b) == IF a > b THEN a ELSE b

Pts   == { [x |-> a, y |-> b] : a \in Coord, b \in Coord }
Pairs == { <<s, d>> : s \in Pts, d \in Pts }

\* ---- algorithm model: one king-step toward d (mirrors the Python loop) ----
StepToward(c, d) ==
  [ x |-> c.x + (IF c.x < d.x THEN 1 ELSE IF c.x > d.x THEN -1 ELSE 0),
    y |-> c.y + (IF c.y < d.y THEN 1 ELSE IF c.y > d.y THEN -1 ELSE 0) ]

Cheb(c, d)      == Max(Abs(d.x - c.x), Abs(d.y - c.y))
OptimalLen(s,d) == Cheb(s, d)              \* king-move lower bound

\* Guard: MaxStep must cover the widest pair so Reach[i] is defined for all i.
ASSUME \A s \in Pts, d \in Pts : Cheb(s, d) <= MaxStep

\* 4-connected distance; a diagonal king-step "saves" 1 vs this bound
Manhattan(s, d) == Abs(d.x - s.x) + Abs(d.y - s.y)

\* PlusPy has no RECURSIVE operator keyword, but it supports recursive function
\* definitions (f[n \in S] == ...). Reach[k] is the point after k king-steps from
\* s toward d; PathFrom is the step sequence (point after each of 1..Cheb steps),
\* mirroring the Python loop which appends one king-step per iteration.
PathFrom(s, d) ==
  LET Reach[k \in 0..MaxStep] ==
        IF k = 0 THEN s ELSE StepToward(Reach[k - 1], d)
  IN [ i \in 1..Cheb(s, d) |-> Reach[i] ]

\* ---- independent oracle: what a correct path is ----
Adjacent(a, b) == /\ Abs(a.x - b.x) <= 1
                  /\ Abs(a.y - b.y) <= 1
                  /\ ~(a.x = b.x /\ a.y = b.y)

ValidPath(s, d, p) ==
  IF Len(p) = 0
  THEN s = d
  ELSE /\ Adjacent(s, p[1])
       /\ p[Len(p)] = d
       /\ \A i \in 1..(Len(p) - 1) : Adjacent(p[i], p[i + 1])

\* every step strictly reduces Chebyshev distance to d by exactly 1 => minimal:
PointSeq(s, p) == [ i \in 0..Len(p) |-> IF i = 0 THEN s ELSE p[i] ]
MinimalProgress(s, d, p) ==
  LET pts == PointSeq(s, p)
  IN \A i \in 1..Len(p) : Cheb(pts[i], d) = Cheb(pts[i - 1], d) - 1

Correct(s, d) ==
  LET p == PathFrom(s, d)
  IN /\ ValidPath(s, d, p)              \* legal walk
     /\ Len(p) = OptimalLen(s, d)       \* no shorter king-walk exists
     /\ MinimalProgress(s, d, p)        \* optimality witness
     /\ Len(p) <= Manhattan(s, d)       \* never worse than 4-connected
     /\ (Len(p) = Manhattan(s, d) <=> (s.x = d.x \/ s.y = d.y))  \* diagonal savings

VARIABLE todo
Init == todo = Pairs
Next == /\ todo # {}
        /\ \E pr \in todo :
              /\ Assert(Correct(pr[1], pr[2]), <<"CalculatePath FAIL", pr>>)
              /\ todo' = todo \ {pr}
================================================================================

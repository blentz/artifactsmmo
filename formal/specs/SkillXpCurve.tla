------------------------------- MODULE SkillXpCurve -------------------------------
EXTENDS Integers, FiniteSets, TLC

\* Mirrors src/artifactsmmo_cli/ai/learning/skill_xp_curve.py:
\*   growth_ratio:26, required_xp:34, total_xp_to_reach:46, cycles_to_level:49,
\*   confidence:57, is_confident:65.
\*
\* FLOAT ABSTRACTION (precedent: PredictWin abstracts _expected_hit's float/crit
\* math). PlusPy has no reals, so three pieces of float arithmetic are abstracted
\* — their VALUE is verified by inspection; only their branch structure / the
\* surrounding integer & count properties are modeled here:
\*   * growth_ratio() — mean of consecutive observed ratios (a float).
\*   * required_xp()'s ESTIMATE branch — anchor_xp * growth_ratio ** steps (a
\*     float, then int()-truncated). We model only THAT this branch is taken
\*     (sentinel -2), not the geometric value.
\*   * cycles_to_level()'s quotient total_xp / xp_per_cycle (a float). We model
\*     only the 0 / inf guard branches and the "finite positive" branch (1).
\*
\* WHAT IS PROVED (integer/count/branch contract):
\*   * required_xp: exact on observed levels; 0 for empty curve; 0 when the level
\*     is below all observed data; estimate-branch sentinel otherwise.
\*   * confidence: = |observed-in-gap| / |gap| modeled as a (num, den) pair, with
\*     num in [0, den] (fraction in [0,1]); den=0 (empty gap) => confident (1.0);
\*     is_confident iff num = den (every gap level observed).
\*   * cycles_to_level: 0 when target<=current; inf when xp_per_cycle<=0; finite
\*     positive otherwise.
\*   * total_xp_to_reach: non-negative and monotone non-decreasing in target over
\*     an all-observed range (a sum of non-negative exact integers).
\*   * growth_ratio: the DEFAULT ratio is used iff there is NO consecutive
\*     observed pair with positive anchor xp (cross-checked against a hand table).

DefaultRatioMilli == 1500   \* DEFAULT_GROWTH_RATIO=1.5 as milli-units (no floats)
InfSentinel == -1           \* models float("inf") for cycles_to_level

\* A curve = a record: obs (set of observed levels) + xp (function on obs). Levels 1..6.
Levels == 1..6
Curves == {
  [obs |-> {},        xp |-> [l \in {} |-> 0]],
  [obs |-> {1},       xp |-> (1 :> 100)],
  [obs |-> {1,2},     xp |-> (1 :> 100 @@ 2 :> 150)],
  [obs |-> {1,2,3},   xp |-> (1 :> 100 @@ 2 :> 150 @@ 3 :> 225)],
  [obs |-> {2,4},     xp |-> (2 :> 200 @@ 4 :> 400)]    \* gap: 3 not observed
}

\* A stable tag per curve (used to index the growth hand-table).
Tag(c) ==
  IF c.obs = {} THEN "empty"
  ELSE IF c.obs = {1} THEN "s1"
  ELSE IF c.obs = {1,2} THEN "p12"
  ELSE IF c.obs = {1,2,3} THEN "p123"
  ELSE "g24"

\* ---- required_xp: integer branches (estimate branch abstracted) ----
BelowSet(c, level) == { l \in c.obs : l < level }
RequiredXp(c, level) ==
  IF level \in c.obs THEN c.xp[level]
  ELSE IF c.obs = {} THEN 0
  ELSE IF BelowSet(c, level) = {} THEN 0
  ELSE -2   \* estimate-branch sentinel (geometric float value abstracted)

OracleReq(c, level) ==
  IF level \in c.obs THEN c.xp[level]
  ELSE IF c.obs = {} \/ BelowSet(c, level) = {} THEN 0
  ELSE -2
ReqCorrect(c, level) == RequiredXp(c, level) = OracleReq(c, level)

\* ---- confidence (count) + is_confident ----
GapLevels(cur, tgt) == { l \in Levels : l >= cur /\ l < tgt }
ObservedInGap(c, cur, tgt) == { l \in GapLevels(cur, tgt) : l \in c.obs }
ConfNum(c, cur, tgt) == Cardinality(ObservedInGap(c, cur, tgt))
ConfDen(cur, tgt)    == Cardinality(GapLevels(cur, tgt))
IsConfident(c, cur, tgt) == \A l \in GapLevels(cur, tgt) : l \in c.obs
ConfCorrect(c, cur, tgt) ==
  /\ ConfNum(c, cur, tgt) >= 0
  /\ ConfNum(c, cur, tgt) <= ConfDen(cur, tgt)                       \* fraction in [0,1]
  /\ (IsConfident(c, cur, tgt) <=> ConfNum(c, cur, tgt) = ConfDen(cur, tgt))
  /\ (ConfDen(cur, tgt) = 0 => IsConfident(c, cur, tgt))             \* empty gap => confident

\* ---- cycles_to_level: 0/inf guard branches (quotient abstracted) ----
CyclesGuard(cur, tgt, xpPerCycleMilli) ==
  IF tgt <= cur THEN 0
  ELSE IF xpPerCycleMilli <= 0 THEN InfSentinel
  ELSE 1   \* finite-positive sentinel (float quotient abstracted)
CyclesCorrect(cur, tgt, x) ==
  /\ (tgt <= cur => CyclesGuard(cur, tgt, x) = 0)
  /\ (tgt > cur /\ x <= 0 => CyclesGuard(cur, tgt, x) = InfSentinel)
  /\ (tgt > cur /\ x > 0 => CyclesGuard(cur, tgt, x) = 1)

\* ---- total_xp_to_reach monotonicity (FIX of the TotalObs placeholder) ----
\* Realized as a real bounded recursive function summing RequiredXp over the
\* contiguous range [lo,hi) for the {1,2,3} curve, where levels 1,2,3 are ALL
\* observed so every RequiredXp is an exact non-negative integer. Range hi runs
\* up to 4 so [cur,tgt) only ever sums observed levels (1..3).
C123 == CHOOSE c \in Curves : c.obs = {1,2,3}
TotalObs[lo \in 1..4, hi \in 1..4] ==
  IF hi <= lo THEN 0
  ELSE RequiredXp(C123, hi - 1) + TotalObs[lo, hi - 1]
Total(cur, tgt) == TotalObs[cur, tgt]
TotalCorrect(cur, tgt) ==
  /\ Total(cur, tgt) >= 0
  /\ Total(cur, tgt) <= Total(cur, tgt + 1)   \* monotone non-decreasing in target

\* ---- growth_ratio: DEFAULT iff <2 consecutive observed (FIX of GrowthCorrect) ----
ConsecutivePairs(c) == { l \in c.obs : (l + 1) \in c.obs /\ c.xp[l] > 0 }
UsesDefaultRatio(c) == ConsecutivePairs(c) = {}
\* Independent hand table (verified by hand against the Curves' recipe data):
\*   empty -> TRUE  (no observed levels, no pair)
\*   {1}   -> TRUE  (single level, no pair)
\*   {1,2} -> FALSE (1&2 consecutive, xp[1]=100>0 => a pair exists)
\*   {1,2,3} -> FALSE (1&2 and 2&3 consecutive pairs exist)
\*   {2,4} -> TRUE  (2&4 not consecutive; level 3 unobserved => NO consecutive pair)
ExpectedDefault == ( "empty" :> TRUE
                 @@  "s1"    :> TRUE
                 @@  "p12"   :> FALSE
                 @@  "p123"  :> FALSE
                 @@  "g24"   :> TRUE )
GrowthCorrect(c) == UsesDefaultRatio(c) <=> ExpectedDefault[Tag(c)]

\* ---- tagged enumeration ----
LevelPairs == { <<cur, tgt>> : cur \in Levels, tgt \in (Levels \cup {7}) }
XpRates == { -5, 0, 10 }   \* milli-units; <=0 exercises the inf branch
TotalPairs == { <<cur, tgt>> : cur \in 1..3, tgt \in 1..3 }
Tagged ==
  { [k |-> "req",  c |-> c, lvl |-> l] : c \in Curves, l \in (Levels \cup {7}) }
  \cup { [k |-> "conf", c |-> c, cur |-> p[1], tgt |-> p[2]] : c \in Curves, p \in LevelPairs }
  \cup { [k |-> "cyc", cur |-> p[1], tgt |-> p[2], x |-> x] : p \in LevelPairs, x \in XpRates }
  \cup { [k |-> "growth", c |-> c] : c \in Curves }
  \cup { [k |-> "total", cur |-> p[1], tgt |-> p[2]] : p \in TotalPairs }
Check(t) ==
  IF t.k = "req" THEN ReqCorrect(t.c, t.lvl)
  ELSE IF t.k = "conf" THEN ConfCorrect(t.c, t.cur, t.tgt)
  ELSE IF t.k = "cyc" THEN CyclesCorrect(t.cur, t.tgt, t.x)
  ELSE IF t.k = "growth" THEN GrowthCorrect(t.c)
  ELSE TotalCorrect(t.cur, t.tgt)

VARIABLE todo
Init == todo = Tagged
Next == /\ todo # {}
        /\ \E t \in todo :
              /\ Assert(Check(t), <<"SkillXpCurve FAIL", t>>)
              /\ todo' = todo \ {t}
================================================================================

------------------------------- MODULE StuckDetector -------------------------------
EXTENDS Integers, Sequences, FiniteSets, TLC

\* Mirrors src/artifactsmmo_cli/ai/recovery.py:
\*   detect (38), _check_no_progress (48), _check_goal_oscillation (55),
\*   _check_state_frozen (64), _recent_since (74), acknowledge (85).
\*
\* StuckDetector is a pure deterministic state machine over a bounded history
\* deque + per-signal acknowledge cutoffs. Modeled fully (no floats).
\*
\* A scenario = a history buffer (sequence of records, most-recent last), the
\* global cycle counter (>= Len(history); the deque maxlen having evicted the
\* counter - Len oldest cycles), and the three acknowledge cutoffs ackF/ackO/ackN.
\*   record = [state |-> s, goal |-> g, action |-> a]
\*   signals precedence: "frozen" > "osc" > "noprog"  (detect order, recovery.py:40-46)

\* ---- _recent_since(cutoff, count): up to `count` most-recent records whose
\* GLOBAL index >= cutoff. Python (recovery.py:74-83):
\*   start_idx = counter - len(history)
\*   post_ack  = [rec for i,rec in enumerate(history) if start_idx + i >= cutoff]
\*   return post_ack[-count:]
\* A buffered record at 1-based position i has global index start_idx + (i-1).
\* We fold over 1..Len(hist), appending hist[i] when start_idx+(i-1) >= cutoff
\* (preserving order), then take the LAST `count` of the kept sub-sequence. ----
RecentSince(hist, counter, cutoff, count) ==
  LET L        == Len(hist)
      startIdx == counter - L
      \* Build[i] = the kept sub-sequence of hist[1..i], in order.
      Build[i \in 0..L] ==
        IF i = 0 THEN << >>
        ELSE IF (startIdx + (i - 1)) >= cutoff
             THEN Append(Build[i - 1], hist[i])
             ELSE Build[i - 1]
      kept     == Build[L]
      kl       == Len(kept)
  IN IF kl <= count THEN kept ELSE SubSeq(kept, kl - count + 1, kl)

\* ---- the three checks over a window ----
AllNoPlan(win) == \A j \in 1..Len(win) : win[j].action = "<no_plan>"
DistinctGoals(win) == Cardinality({ win[j].goal : j \in 1..Len(win) })
MaxStateCount(win) ==
  IF win = << >> THEN 0
  ELSE LET states == { win[j].state : j \in 1..Len(win) }
           counts == { Cardinality({ j \in 1..Len(win) : win[j].state = s }) : s \in states }
       IN CHOOSE mx \in counts : \A c \in counts : mx >= c

\* _check_state_frozen (64): window count=10, len==10, some state appears >=5 times.
CheckFrozen(hist, counter, ack) ==
  LET w == RecentSince(hist, counter, ack, 10) IN Len(w) = 10 /\ MaxStateCount(w) >= 5
\* _check_goal_oscillation (55): window count=8, len==8, exactly 2 distinct goals.
CheckOsc(hist, counter, ack) ==
  LET w == RecentSince(hist, counter, ack, 8) IN Len(w) = 8 /\ DistinctGoals(w) = 2
\* _check_no_progress (48): window count=4, len==4, all actions "<no_plan>".
CheckNoProg(hist, counter, ack) ==
  LET w == RecentSince(hist, counter, ack, 4) IN Len(w) = 4 /\ AllNoPlan(w)

\* ---- detect: precedence frozen > osc > noprog (recovery.py:40-46) ----
Detect(sc) ==
  IF CheckFrozen(sc.hist, sc.counter, sc.ackF) THEN "frozen"
  ELSE IF CheckOsc(sc.hist, sc.counter, sc.ackO) THEN "osc"
  ELSE IF CheckNoProg(sc.hist, sc.counter, sc.ackN) THEN "noprog"
  ELSE "none"

\* ---- record constructors (small string tokens) ----
R(s, g, a) == [state |-> s, goal |-> g, action |-> a]

\* ---- hand scenarios; exp is the INDEPENDENT oracle (hand-computed against the
\* thresholds + precedence; verified by hand BEFORE trusting). ----

\* S1 frozen fires: 10 records, state "A" appears 5x, "B" 5x; counter=10, no acks.
\*   start_idx=0, all global idx 0..9 >= 0 => keep 10; len=10; maxStateCount=5 => frozen.
S1 == [ hist |-> << R("A","g1","act"), R("B","g1","act"), R("A","g1","act"), R("B","g1","act"),
                    R("A","g1","act"), R("B","g1","act"), R("A","g1","act"), R("B","g1","act"),
                    R("A","g1","act"), R("B","g1","act") >>,
        counter |-> 10, ackF |-> 0, ackO |-> 0, ackN |-> 0, exp |-> "frozen" ]

\* S2 osc fires, no frozen: 8 records, goals alternate g1/g2 (2 distinct), all states
\*   distinct (no state >=5), actions "act"; counter=8, no acks.
\*   frozen: RecentSince(10) keeps 8, len=8 != 10 => FALSE.
\*   osc: RecentSince(8)=8, distinct goals=2 => TRUE. exp="osc".
S2 == [ hist |-> << R("s1","g1","act"), R("s2","g2","act"), R("s3","g1","act"), R("s4","g2","act"),
                    R("s5","g1","act"), R("s6","g2","act"), R("s7","g1","act"), R("s8","g2","act") >>,
        counter |-> 8, ackF |-> 0, ackO |-> 0, ackN |-> 0, exp |-> "osc" ]

\* S3 noprog fires: 4 records all action "<no_plan>"; counter=4, no acks.
\*   frozen len 4!=10 F; osc len 4!=8 F; noprog len=4 all no_plan => TRUE. exp="noprog".
S3 == [ hist |-> << R("A","g1","<no_plan>"), R("B","g2","<no_plan>"),
                    R("A","g1","<no_plan>"), R("B","g2","<no_plan>") >>,
        counter |-> 4, ackF |-> 0, ackO |-> 0, ackN |-> 0, exp |-> "noprog" ]

\* S4 PRECEDENCE: frozen AND noprog both hold -> "frozen". 10 records, state "A" 5x,
\*   ALL actions "<no_plan>"; counter=10, no acks.
\*   frozen: len=10, maxStateCount=5 => TRUE.
\*   noprog: last 4 all "<no_plan>" => would be TRUE, but frozen has precedence. exp="frozen".
S4 == [ hist |-> << R("A","g1","<no_plan>"), R("B","g1","<no_plan>"), R("A","g1","<no_plan>"),
                    R("B","g1","<no_plan>"), R("A","g1","<no_plan>"), R("B","g1","<no_plan>"),
                    R("A","g1","<no_plan>"), R("B","g1","<no_plan>"), R("A","g1","<no_plan>"),
                    R("C","g1","<no_plan>") >>,
        counter |-> 10, ackF |-> 0, ackO |-> 0, ackN |-> 0, exp |-> "frozen" ]

\* S5 ACK SUPPRESSION: a buffer that WOULD fire frozen (10 records, state "A" 5x), but
\*   ackF=counter=10. start_idx=0, cutoff=10: keep where global idx 0..9 >= 10 => none.
\*   RecentSince(10)=<<>>, len=0 != 10 => frozen FALSE. ackO=ackN=0: goals all g1
\*   (distinct=1, no osc), actions "act" (no noprog). exp="none".
S5 == [ hist |-> << R("A","g1","act"), R("B","g1","act"), R("A","g1","act"), R("B","g1","act"),
                    R("A","g1","act"), R("B","g1","act"), R("A","g1","act"), R("B","g1","act"),
                    R("A","g1","act"), R("B","g1","act") >>,
        counter |-> 10, ackF |-> 10, ackO |-> 0, ackN |-> 0, exp |-> "none" ]

\* S6 WINDOW ARITHMETIC: counter > Len(hist) (eviction) with a mid-history ackF cutoff.
\*   L=10, counter=15 (5 evicted). start_idx=5; positions 1..10 -> global idx 5..14.
\*   ackF=10: keep where idx>=10 => positions 6..10 (idx 10..14) = 5 records, all state "A".
\*   RecentSince(10) keeps only 5, len=5 != 10 => frozen FALSE (the 5 would-be-frozen
\*   states are below the count threshold post-eviction+ack).
\*   ackO=ackN=0: all 10 kept; goals all g1 (osc distinct=1 FALSE); actions "act"
\*   (noprog FALSE). exp="none".
S6 == [ hist |-> << R("A","g1","act"), R("A","g1","act"), R("A","g1","act"), R("A","g1","act"),
                    R("A","g1","act"), R("A","g1","act"), R("A","g1","act"), R("A","g1","act"),
                    R("A","g1","act"), R("A","g1","act") >>,
        counter |-> 15, ackF |-> 10, ackO |-> 0, ackN |-> 0, exp |-> "none" ]

Scenarios == { S1, S2, S3, S4, S5, S6 }

DetectCorrect(sc) == Detect(sc) = sc.exp

VARIABLE todo
Init == todo = Scenarios
Next == /\ todo # {}
        /\ \E sc \in todo :
              /\ Assert(DetectCorrect(sc), <<"StuckDetector FAIL", sc>>)
              /\ todo' = todo \ {sc}
================================================================================

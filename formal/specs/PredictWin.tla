------------------------------- MODULE PredictWin -------------------------------
EXTENDS Integers, TLC

\* Mirrors src/artifactsmmo_cli/ai/combat.py:57 predict_win (lines 66-79).
\* The model works in PER-TURN INTEGER DAMAGE: the player deals `phit` per turn,
\* the monster deals `mhit` per turn. This abstracts the element/crit expansion
\* of _expected_hit (combat.py:41-54), which is pure deterministic arithmetic
\* (output = attack + round(attack*dmg%) - round(output*resist%), times the
\* expected-crit factor 1 + crit%*0.5, summed over elements). That expansion is
\* verified by inspection: it reduces every fight to a single non-negative
\* per-turn damage number on each side, which is exactly what `phit`/`mhit`
\* range over here. We verify the part that has nontrivial control flow: the
\* closed-form ceil-division verdict WITH the initiative tiebreak (combat.py:79)
\* equals the outcome of ACTUALLY running the alternating-attack fight, plus
\* monotonicity and MAX_TURNS soundness.

MaxTurns == 100   \* combat.py MAX_TURNS (line 16)

\* ---- main domain (DOCUMENTED) ----
\* HP 1..6, Hit 0..4, pf in {TRUE,FALSE} => 6*5*6*5*2 = 1800 main cases.
\* Hit includes 0 so the phit<=0 (auto-loss) and mhit<=0 (auto-win) branches are
\* exercised; HP up to 6 with Hit up to 4 gives multi-round fights and exact
\* initiative ties (rtk = rtd). Total main case count = 1800. Combined with the
\* 6 supplementary cap cases below the runner iterates N = 1806 times.
HP    == 1..6
Hit   == 0..4
Bool  == {TRUE, FALSE}
Cases == { <<ph, phit, mh, mhit, pf>> :
             ph \in HP, phit \in Hit, mh \in HP, mhit \in Hit, pf \in Bool }

\* ---- supplementary cap cases (MAX_TURNS soundness, non-vacuous) ----
\* In the main domain rtk = ceil(mh/phit) <= 6 < 100, so the `rtk > MaxTurns`
\* branch (combat.py:69) is NEVER reached. To exercise it we add cases with
\* huge monster HP: mh in {150,250}, phit in {1,2}. With phit=1 a 150/250-HP
\* monster needs 150/250 rounds (> 100) to die; with phit=2 it needs 75/125.
\* So mh=250 (rtk=250 or 125) and mh=150,phit=1 (rtk=150) all exceed MaxTurns,
\* forcing ClosedForm down the cap branch -> FALSE. The capped sim (turns 0..100)
\* never lands the kill in time and likewise returns FALSE; Refines confirms the
\* agreement. mh=150,phit=2 gives rtk=75 (<=100): a control that does NOT trip
\* the cap, kept so the cap set also contains a within-cap fight.
CapHP   == {150, 250}
CapPhit == {1, 2}
CapCases == { <<ph, phit, mh, mhit, pf>> :
                ph \in {3}, phit \in CapPhit, mh \in CapHP,
                mhit \in {2}, pf \in {TRUE} }   \* 1*2*2*1*1 = 4 cap cases
\* (4 cap cases. With mh=250 phit in {1,2} both trip the cap; mh=150 phit=1 trips,
\*  phit=2 does not. So 3 of the 4 reach the cap branch -> non-vacuous.)
\*
\* The 4 cap cases above all have mhit=2, ph=3 => the player dies at round 2
\* (rtd=ceil(3/2)=2) BEFORE the turn horizon, so the operational sim returns a
\* loss via its player-death path (Fight: p <= 0 => FALSE) and NEVER via its OWN
\* truncation path (t >= MaxTurns => FALSE). Only ClosedForm's cap branch is
\* exercised by those. To prove the sim's truncation path is ALSO load-bearing
\* and agrees, we add two ZERO-DAMAGE cap cases: mhit=0 => the monster never
\* kills the player, so the sim cannot die-out and MUST run the full MaxTurns
\* rounds and truncate to a loss, while a 250-HP monster (rtk=250 or 125 > 100)
\* drives ClosedForm down its cap branch -> FALSE. Both paths must return FALSE.
CapZeroCases == { <<3, 1, 250, 0, TRUE>>,    \* rtk=250>100; sim truncates at t=100
                  <<3, 2, 250, 0, FALSE>> }  \* rtk=125>100; sim truncates at t=100
\* (2 zero-damage cap cases; both force the sim to t=MaxTurns -> truncation loss.)

AllCases == Cases \cup CapCases \cup CapZeroCases   \* 1800 + 4 + 2 = 1806

\* Largest monster HP and turn horizon the simulation must cover. The sim is
\* capped at MaxTurns rounds regardless, but its turn-index domain must reach
\* MaxTurns so a fight that would need >100 rounds is correctly truncated to a
\* loss. Player HP never exceeds 6 (main) or 3 (cap), so MaxPHP=6.
MaxPHP  == 6
MaxMHP  == 250

CeilDiv(a, b) == (a + b - 1) \div b   \* ceil(a/b); assumes a>=0, b>0 (always true at call sites: phit/mhit guarded > 0)

\* ============================================================================
\* ALGORITHM MODEL: predict_win closed form (combat.py:66-79).
\* ============================================================================
ClosedForm(ph, phit, mh, mhit, pf) ==
  IF phit <= 0 THEN FALSE
  ELSE LET rtk == CeilDiv(mh, phit) IN
       IF rtk > MaxTurns THEN FALSE
       ELSE IF mhit <= 0 THEN TRUE
       ELSE LET rtd == CeilDiv(ph, mhit) IN
            IF pf THEN rtk <= rtd ELSE rtk < rtd

\* ============================================================================
\* INDEPENDENT ORACLE: actually run the fight, turn by turn.
\* Fight is a recursive FUNCTION (PlusPy has no RECURSIVE keyword) keyed by
\* the dynamic state -- turn `t`, current player HP `p`, current monster HP `m`
\* -- and the static fight parameters phit, mhit, pf carried in the key so a
\* single global function serves every case.
\*
\* Semantics (mirrors predict_win's outcome):
\*   * A round at turn t applies the player's strike then the monster's strike,
\*     ordered by `pf` (player_first when initiative >= monster's, combat.py:78).
\*   * If the side struck second is already dead, the fight ends with the first
\*     striker as winner -- this is the initiative tiebreak: with equal rounds-
\*     to-kill/die, whoever strikes first wins (player-first => `<=`).
\*   * A fight not resolved within MaxTurns rounds is a LOSS (combat.py:69 cap).
\* Returns TRUE iff the player wins. Player HP domain 0..MaxPHP, monster HP
\* domain 0..MaxMHP, turn 0..MaxTurns.
\* ============================================================================
\* Both blows of a round are pure subtraction; we evaluate them inline so a
\* round consumes exactly one turn index, making the MaxTurns cap faithful.
\* domains must cover ALL case sets (main + cap); PlusPy won't catch an under-declared bound
Fight[ t \in 0..MaxTurns,
       p \in 0..MaxPHP,
       m \in 0..MaxMHP,
       phit \in 0..4,        \* per-turn player damage actually exercised (max(Hit, CapPhit) = 4)
       mhit \in 0..4,        \* per-turn monster damage
       pf \in Bool ] ==
  IF m <= 0 THEN TRUE            \* monster already dead -> player has won
  ELSE IF p <= 0 THEN FALSE      \* player already dead -> loss
  ELSE IF t >= MaxTurns THEN FALSE   \* cap reached, unresolved -> loss
  ELSE IF pf
       THEN \* player strikes first
            IF m - phit <= 0 THEN TRUE            \* monster dies on player's blow
            ELSE IF p - mhit <= 0 THEN FALSE      \* then monster's blow kills player
            ELSE Fight[t + 1, p - mhit, m - phit, phit, mhit, pf]
       ELSE \* monster strikes first
            IF p - mhit <= 0 THEN FALSE           \* player dies on monster's blow
            ELSE IF m - phit <= 0 THEN TRUE       \* then player's blow kills monster
            ELSE Fight[t + 1, p - mhit, m - phit, phit, mhit, pf]

Simulated(ph, phit, mh, mhit, pf) ==
  IF phit <= 0 THEN FALSE
  ELSE Fight[0, ph, mh, phit, mhit, pf]

\* ============================================================================
\* PROPERTIES
\* ============================================================================
Refines(c) == ClosedForm(c[1], c[2], c[3], c[4], c[5])
                = Simulated(c[1], c[2], c[3], c[4], c[5])

\* Monotonicity (over the MAIN domain): a win must survive (a) the player hitting
\* harder (phit+1) and (b) the monster being frailer (mh-1). Asserted only when
\* the perturbed value stays in-domain so the implication is meaningful.
MonoOK(c) ==
  LET ph == c[1] phit == c[2] mh == c[3] mhit == c[4] pf == c[5] IN
  /\ ( (phit + 1 \in Hit /\ ClosedForm(ph, phit, mh, mhit, pf))
        => ClosedForm(ph, phit + 1, mh, mhit, pf) )
  /\ ( (mh - 1 \in HP /\ ClosedForm(ph, phit, mh, mhit, pf))
        => ClosedForm(ph, phit, mh - 1, mhit, pf) )

Correct(c)    == Refines(c) /\ MonoOK(c)   \* main cases
CorrectCap(c) == Refines(c)                \* cap cases: refinement only

VARIABLE todo
Init == todo = AllCases
Next == /\ todo # {}
        /\ \E c \in todo :
              /\ IF c \in CapCases \/ c \in CapZeroCases
                 THEN \* monotonicity (MonoOK) is not meaningful for cap cases -- refinement only
                      Assert(CorrectCap(c), <<"PredictWin CAP FAIL", c>>)
                 ELSE Assert(Correct(c), <<"PredictWin FAIL", c>>)
              /\ todo' = todo \ {c}
================================================================================

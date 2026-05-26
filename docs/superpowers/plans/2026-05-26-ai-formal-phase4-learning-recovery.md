# AI Formal Verification — Phase 4 (Learning/Recovery) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two TLA+/PlusPy specs to the `formal/` harness proving the correctness of the learning/recovery pure logic: `learning/skill_xp_curve.SkillXpCurve` (the integer/count/structural parts) and `recovery.StuckDetector` (the deterministic stuck-state state machine). This is the final phase of the AI pure-component roadmap.

**Architecture:** Same enumerate-and-`Assert`-against-independent-oracle harness as the twelve existing specs. `SkillXpCurve` uses float arithmetic (geometric `growth_ratio ** steps`, mean ratios, division) that PlusPy cannot represent; following the precedent set by `PredictWin` (which abstracted `_expected_hit`'s float/crit math), this spec verifies the **integer, count, and branch-structure** properties and documents the geometric float estimate as verified-by-inspection. `StuckDetector` is a pure deterministic state machine over a bounded deque + acknowledge cutoffs — modeled fully (no floats).

**Tech Stack:** TLA+ (PlusPy subset), PlusPy (vendored), Python 3.13 stdlib runner.

---

## Critical environment facts (apply to every task)

- PlusPy entry: `python3 formal/vendor/PlusPy/pluspy.py`. If `formal/vendor/` missing, run `./formal/setup.sh`.
- Manual run, module `M`, domain size `N`: `python3 formal/vendor/PlusPy/pluspy.py -c<N> -P formal/specs:formal/vendor/PlusPy/modules/lib <M>`
- CLEAN: `MAIN DONE`, exit 0. FAIL: `Evaluating Assert (...) failed` + `AssertionError`, exit 1.
- Runner: `python3 formal/run.py` (NOT `uv run` in the worktree). Append `(name, domain_size)` to `MODULES`.
- **Work in the given worktree path and verify files land there** (`git -C <worktree> status`) before running pluspy.
- **PlusPy has NO `RECURSIVE` operator keyword** — recursion = recursive functions `f[k \in S]==...`. **NO floats/reals** — integer only; abstract float arithmetic and verify integer/count/branch structure. Supports ASSUME, records, functions, set comprehension, UNION, SUBSET, DOMAIN, Cardinality (FiniteSets), Len/Append/sub-sequences (EXTENDS Sequences), CHOOSE, `\E`/`\A`, `LET`/`IF`.
- The intended `.tla` is the CONTRACT; adapt surface syntax to PlusPy's subset but do NOT weaken any asserted property. If a property genuinely can't be expressed after real effort, report BLOCKED — never fake a pass.
- Enumeration idiom: `VARIABLE todo`; `Init == todo = <domain>`; `Next == /\ todo # {} /\ \E x \in todo : /\ Assert(Correct(x), <<"M FAIL", x>>) /\ todo' = todo \ {x}`.

## File structure

- Create `formal/specs/SkillXpCurve.tla`
- Create `formal/specs/StuckDetector.tla`
- Modify `formal/run.py` (+2 MODULES entries)
- Modify `formal/README.md` (+2 property→code rows)

---

## Task 1: SkillXpCurve — count/branch/monotonicity properties (float estimate abstracted)

Mirrors `src/artifactsmmo_cli/ai/learning/skill_xp_curve.py` (`growth_ratio`:26, `required_xp`:34, `total_xp_to_reach`:46, `cycles_to_level`:49, `confidence`:57, `is_confident`:65). READ it first.

**Modeling decision (floats → abstracted):** `growth_ratio` (mean of ratios) and `required_xp`'s estimate branch (`anchor_xp * growth_ratio ** steps`) and `cycles_to_level`'s quotient are float arithmetic PlusPy cannot represent. The spec verifies the **integer/count/branch** contract — the geometric estimate's float value is verified by inspection (documented), exactly as `PredictWin` abstracted `_expected_hit`. What IS proved: `confidence` counts + `[0,1]` + `is_confident` equivalence; `required_xp` exactness on observed levels + the two zero-boundaries; `cycles_to_level`'s 0/inf guard branches; `total_xp_to_reach` monotonicity; `growth_ratio = DEFAULT` iff <2 consecutive observed.

**Files:** Create `formal/specs/SkillXpCurve.tla`; Modify `formal/run.py`.

- [ ] **Step 1: Write `formal/specs/SkillXpCurve.tla`**

```tla
------------------------------- MODULE SkillXpCurve -------------------------------
EXTENDS Integers, FiniteSets, TLC

DefaultRatioMilli == 1500   \* DEFAULT_GROWTH_RATIO=1.5 as milli-units (avoid floats)
InfSentinel == -1           \* models float("inf") for cycles_to_level

\* A curve = a set of observed levels with their max_xp (integers). Modeled as a
\* record: obsLevels (set) + xp (function on obsLevels). Levels live in 1..6.
Levels == 1..6
\* observed-level sets to enumerate (incl. empty, singleton, consecutive pairs, gaps).
Curves == {
  [obs |-> {},        xp |-> [l \in {} |-> 0]],
  [obs |-> {1},       xp |-> (1 :> 100)],
  [obs |-> {1,2},     xp |-> (1 :> 100 @@ 2 :> 150)],
  [obs |-> {1,2,3},   xp |-> (1 :> 100 @@ 2 :> 150 @@ 3 :> 225)],
  [obs |-> {2,4},     xp |-> (2 :> 200 @@ 4 :> 400)]    \* gap: 3 not observed
}

\* ---- required_xp: integer branches (estimate branch abstracted) ----
\* observed -> exact; empty or below-all -> 0. (Estimate branch returns >0; not the float value.)
BelowSet(c, level) == { l \in c.obs : l < level }
RequiredXp(c, level) ==
  IF level \in c.obs THEN c.xp[level]
  ELSE IF c.obs = {} THEN 0
  ELSE IF BelowSet(c, level) = {} THEN 0
  ELSE -2   \* "estimate branch" sentinel (float value abstracted; only its branch is modeled)

\* independent oracle for the integer branches:
OracleReq(c, level) ==
  IF level \in c.obs THEN c.xp[level]
  ELSE IF c.obs = {} \/ BelowSet(c, level) = {} THEN 0
  ELSE -2
ReqCorrect(c, level) == RequiredXp(c, level) = OracleReq(c, level)

\* ---- confidence (count) + is_confident ----
GapLevels(cur, tgt) == { l \in Levels : l >= cur /\ l < tgt }
ObservedInGap(c, cur, tgt) == { l \in GapLevels(cur, tgt) : l \in c.obs }
\* confidence = |observed in gap| / |gap| as a (num, den) pair; den=0 => 1.0 (full).
ConfNum(c, cur, tgt) == Cardinality(ObservedInGap(c, cur, tgt))
ConfDen(cur, tgt)    == Cardinality(GapLevels(cur, tgt))
IsConfident(c, cur, tgt) == \A l \in GapLevels(cur, tgt) : l \in c.obs
ConfCorrect(c, cur, tgt) ==
  /\ ConfNum(c, cur, tgt) >= 0
  /\ ConfNum(c, cur, tgt) <= ConfDen(cur, tgt)                       \* fraction in [0,1]
  /\ (IsConfident(c, cur, tgt) <=> ConfNum(c, cur, tgt) = ConfDen(cur, tgt))  \* confident iff full coverage
  /\ (ConfDen(cur, tgt) = 0 => IsConfident(c, cur, tgt))             \* empty gap => confident (conf=1.0)

\* ---- cycles_to_level: 0/inf guard branches (quotient abstracted) ----
CyclesGuard(cur, tgt, xpPerCycleMilli) ==
  IF tgt <= cur THEN 0
  ELSE IF xpPerCycleMilli <= 0 THEN InfSentinel
  ELSE 1   \* "finite positive" sentinel (the float quotient is abstracted)
CyclesCorrect(cur, tgt, x) ==
  /\ (tgt <= cur => CyclesGuard(cur, tgt, x) = 0)
  /\ (tgt > cur /\ x <= 0 => CyclesGuard(cur, tgt, x) = InfSentinel)
  /\ (tgt > cur /\ x > 0 => CyclesGuard(cur, tgt, x) = 1)

\* ---- total_xp_to_reach monotonicity (over observed-only ranges, integer) ----
\* Restrict to ranges where every level is observed so RequiredXp is exact (>=0);
\* then total is a sum of non-negatives => monotone non-decreasing in tgt.
RECURSIVE_NOTE == "use a bounded recursive fn for the sum over a contiguous range"
\* Total over [cur,tgt) of exact observed xp (only valid when all in obs):
TotalObs[lo \in Levels, hi \in (Levels \cup {7})] ==
  IF hi <= lo THEN 0 ELSE c_xp_placeholder   \* implementer: sum RequiredXp over [lo,hi) for a fixed curve
\* (Implementer: realize TotalObs as a bounded recursive function over the range for a
\*  GIVEN curve, then assert monotonicity: Total(cur,tgt) <= Total(cur,tgt+1) and
\*  Total(cur,tgt) >= 0. Use the {1,2,3} curve where 1,2,3 are all observed.)

\* ---- growth_ratio: DEFAULT iff <2 consecutive observed pairs ----
ConsecutivePairs(c) == { l \in c.obs : (l + 1) \in c.obs /\ c.xp[l] > 0 }
UsesDefaultRatio(c) == ConsecutivePairs(c) = {}
\* (When pairs exist, the ratio is a float mean — abstracted. We assert only the
\*  branch: default-ratio is used iff no consecutive observed pair exists.)
GrowthCorrect(c) == UsesDefaultRatio(c) <=> (ConsecutivePairs(c) = {})
\* ^ NOTE: this is X<=>X (tautology). Make it MEANINGFUL: assert against an INDEPENDENT
\*  count — e.g. UsesDefaultRatio(c) <=> (Cardinality(ConsecutivePairs(c)) = 0), and add a
\*  hand-table of expected UsesDefaultRatio per Curve (empty/{1}->TRUE; {1,2},{1,2,3}->FALSE;
\*  {2,4}->TRUE since 3 not observed so no consecutive pair). Implementer: use the hand-table.

\* tagged enumeration
LevelPairs == { <<cur, tgt>> : cur \in Levels, tgt \in (Levels \cup {7}) }
XpRates == { -5, 0, 10 }   \* milli-units; <=0 exercises the inf branch
Tagged ==
  { [k |-> "req",  c |-> c, lvl |-> l] : c \in Curves, l \in (Levels \cup {7}) }
  \cup { [k |-> "conf", c |-> c, cur |-> p[1], tgt |-> p[2]] : c \in Curves, p \in LevelPairs }
  \cup { [k |-> "cyc", cur |-> p[1], tgt |-> p[2], x |-> x] : p \in LevelPairs, x \in XpRates }
  \cup { [k |-> "growth", c |-> c] : c \in Curves }
Check(t) ==
  IF t.k = "req" THEN ReqCorrect(t.c, t.lvl)
  ELSE IF t.k = "conf" THEN ConfCorrect(t.c, t.cur, t.tgt)
  ELSE IF t.k = "cyc" THEN CyclesCorrect(t.cur, t.tgt, t.x)
  ELSE GrowthCorrect(t.c)

VARIABLE todo
Init == todo = Tagged
Next == /\ todo # {}
        /\ \E t \in todo :
              /\ Assert(Check(t), <<"SkillXpCurve FAIL", t>>)
              /\ todo' = todo \ {t}
================================================================================
```

> **Implementer notes (do these — they are required, not optional):**
> 1. The `:>`/`@@` function-literal syntax is TLC's; if PlusPy rejects it, build `xp` as `[l \in c.obs |-> ...]` or via `IF`. Verify with a tiny run.
> 2. **`TotalObs` is a sketch** (`c_xp_placeholder`). Realize it as a real bounded recursive function summing `RequiredXp` over the contiguous range for the `{1,2,3}` curve (all observed, so exact integers), and add a `"total"` tagged family asserting `Total(cur,tgt) >= 0` and `Total(cur,tgt) <= Total(cur,tgt+1)` (monotonicity) over `cur,tgt \in 1..3`. Remove the `RECURSIVE_NOTE`/placeholder lines.
> 3. **`GrowthCorrect` as written is a tautology** — replace it with the hand-table form: `ExpectedDefault == [the five Curves -> their expected UsesDefaultRatio bool]` (empty→TRUE, {1}→TRUE, {1,2}→FALSE, {1,2,3}→FALSE, {2,4}→TRUE) and assert `UsesDefaultRatio(c) <=> ExpectedDefault[tag(c)]`. This makes it an independent cross-check, not X⇔X.
> 4. Keep all four (then five with "total") families. The float estimate (`required_xp` estimate branch value, `growth_ratio` mean, `cycles` quotient) is intentionally abstracted — note it in the header comment.

- [ ] **Step 2: Compute domain size and run**

After realizing TotalObs + the growth hand-table, compute `|Tagged|` exactly from the set comprehensions and use it as `-c<N>`. Run:
`python3 formal/vendor/PlusPy/pluspy.py -c<N> -P formal/specs:formal/vendor/PlusPy/modules/lib SkillXpCurve`
Expected: `MAIN DONE`, exit 0. Confirm the model mirrors `skill_xp_curve.py`: `required_xp` observed-exact + empty/below-all → 0; `confidence` = observed-in-gap / gap-size in [0,1], =1.0 on empty gap; `is_confident` iff all gap levels observed; `cycles_to_level` 0 when target≤current and inf when xp≤0; `growth_ratio` default until ≥2 consecutive observed.

- [ ] **Step 3: Sanity-bite**

Temporarily change `ConfCorrect`'s `ConfNum <= ConfDen` to `ConfNum < ConfDen` — now a fully-observed gap (num=den) fails. Run; expect `<<"SkillXpCurve FAIL", ...>>`. REVERT. (Also confirm the growth hand-table bites: temporarily flip `ExpectedDefault` for `{1,2}` to TRUE → fail.)

- [ ] **Step 4: Register**: append `("SkillXpCurve", <N>)` to `MODULES`.

- [ ] **Step 5: Run the runner**: `python3 formal/run.py` → all PASS, exit 0 (slow; patient).

- [ ] **Step 6: Commit**

```bash
git add formal/specs/SkillXpCurve.tla formal/run.py
git commit -m "test(formal): SkillXpCurve count/branch/monotonicity spec

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: StuckDetector — detection precedence, thresholds, window arithmetic, ack suppression

Mirrors `src/artifactsmmo_cli/ai/recovery.py` (`detect`:38, `_check_no_progress`:48, `_check_goal_oscillation`:55, `_check_state_frozen`:64, `_recent_since`:74, `acknowledge`:85). READ it first. Pure deterministic state machine — modeled fully (no floats).

**Files:** Create `formal/specs/StuckDetector.tla`; Modify `formal/run.py`.

- [ ] **Step 1: Write `formal/specs/StuckDetector.tla`**

```tla
------------------------------- MODULE StuckDetector -------------------------------
EXTENDS Integers, Sequences, FiniteSets, TLC

\* A scenario = a history buffer (sequence of records, most-recent last), the global
\* cycle counter (>= Len(history); models the deque maxlen having evicted counter-Len),
\* and the three acknowledge cutoffs.
\* record = [state |-> s, goal |-> g, action |-> a]
\* signals: "frozen" > "osc" > "noprog" (detect precedence)

\* ---- _recent_since(cutoff, count): up to `count` most-recent records whose GLOBAL
\* index >= cutoff. Buffered record i (1-based) has global index (counter - Len + i). ----
RecentSince(hist, counter, cutoff, count) ==
  LET L == Len(hist)
      keep == [ i \in 1..L |-> (counter - L + i) >= cutoff ]   \* keep[i] TRUE if post-cutoff
      idxs == { i \in 1..L : keep[i] }
      \* take the last `count` of the kept indices (highest i's):
      kept == idxs
  IN LET ord == SortedSeqOfKeptTail(kept, count)  \* implementer: the last `count` kept indices, ascending
     IN [ j \in 1..Len(ord) |-> hist[ord[j]] ]

\* (Implementer: realize RecentSince concretely. Simplest faithful form: since records
\*  are contiguous, the kept set is a suffix-or-subset; build the resulting sub-sequence
\*  of `hist` for kept indices, then take its last `count` via SubSeq. Mirror Python
\*  `_recent_since`: post_ack = [rec for i,rec if start_idx+i >= cutoff]; return post_ack[-count:].)

\* ---- the three checks over a window ----
AllNoPlan(win) == \A j \in 1..Len(win) : win[j].action = "<no_plan>"
DistinctGoals(win) == Cardinality({ win[j].goal : j \in 1..Len(win) })
MaxStateCount(win) ==
  LET states == { win[j].state : j \in 1..Len(win) }
  IN IF win = << >> THEN 0
     ELSE CHOOSE mx \in { Cardinality({ j \in 1..Len(win) : win[j].state = s }) : s \in states } :
            \A s \in states : mx >= Cardinality({ j \in 1..Len(win) : win[j].state = s })

CheckNoProg(hist, counter, ack) ==
  LET w == RecentSince(hist, counter, ack, 4) IN Len(w) = 4 /\ AllNoPlan(w)
CheckOsc(hist, counter, ack) ==
  LET w == RecentSince(hist, counter, ack, 8) IN Len(w) = 8 /\ DistinctGoals(w) = 2
CheckFrozen(hist, counter, ack) ==
  LET w == RecentSince(hist, counter, ack, 10) IN Len(w) = 10 /\ MaxStateCount(w) >= 5

\* ---- detect: precedence frozen > osc > noprog ----
Detect(sc) ==
  IF CheckFrozen(sc.hist, sc.counter, sc.ackF) THEN "frozen"
  ELSE IF CheckOsc(sc.hist, sc.counter, sc.ackO) THEN "osc"
  ELSE IF CheckNoProg(sc.hist, sc.counter, sc.ackN) THEN "noprog"
  ELSE "none"

\* ---- hand scenarios with expected detect() result (independent oracle = hand value) ----
\* Implementer: build ~6-8 scenarios as records [hist |-> <<...>>, counter |-> n,
\*  ackF |-> _, ackO |-> _, ackN |-> _, exp |-> "frozen"/"osc"/"noprog"/"none"] covering:
\*   - frozen fires (10 records, one state >=5 times)
\*   - osc fires (8 records, exactly 2 distinct goals, no frozen)
\*   - noprog fires (4 records all "<no_plan>", no frozen/osc)
\*   - PRECEDENCE: a history where frozen AND noprog both hold -> exp "frozen"
\*   - ACK SUPPRESSION: a history that WOULD fire frozen, but ackF = counter (all records
\*       at/before the cutoff) -> RecentSince returns < 10 post-ack records -> exp not "frozen"
\*   - window-arithmetic: counter > Len(hist) (eviction happened) with a mid-history ack cutoff
\* DetectCorrect(sc) == Detect(sc) = sc.exp

VARIABLE todo
Init == todo = Scenarios
Next == /\ todo # {}
        /\ \E sc \in todo :
              /\ Assert(Detect(sc) = sc.exp, <<"StuckDetector FAIL", sc>>)
              /\ todo' = todo \ {sc}
================================================================================
```

> **Implementer notes (required):**
> 1. **`RecentSince` is the crux** — realize it faithfully against Python `_recent_since` (`recovery.py:74-83`): `start_idx = counter - len(history)`; keep records where `start_idx + i >= cutoff` (0-based i); return the last `count`. In TLA, build the kept sub-sequence of `hist` (preserving order) then take its last `count` via `SubSeq(kept, Len(kept)-count+1, Len(kept))` (guarding when `Len(kept) <= count`). Remove the `SortedSeqOfKeptTail` placeholder — write the real sub-sequence construction.
> 2. **Independent oracle = hand-computed `exp` per scenario.** `DetectCorrect(sc) == Detect(sc) = sc.exp`. Verify each `exp` by hand against the Python thresholds (4 no_plan / 8 with 2 distinct goals / 10 with a state ≥5) and precedence BEFORE trusting them.
> 3. **Must include the ACK-SUPPRESSION scenario** (a buffer that would fire frozen, but `ackF=counter` so the post-ack window is empty → `exp="none"` or a lower-precedence signal) AND the **PRECEDENCE scenario** (frozen+noprog both true → `exp="frozen"`) AND a **window-arithmetic scenario** (`counter > Len(hist)`, mid-history `ackF`). These three are the load-bearing cases.
> 4. State/goal/action values: use small string tokens (e.g. states "A"/"B", goals "g1"/"g2", actions "<no_plan>"/"act").

- [ ] **Step 2: Run (domain size = |Scenarios|)**

Run with `-c|Scenarios|`. Expected: `MAIN DONE`, exit 0. Confirm the model mirrors `recovery.py`: detect precedence frozen>osc>noprog; the 4/8/10 window sizes and the ≥5 / ==2-distinct / all-no_plan thresholds; `_recent_since`'s global-index cutoff (only records added strictly after the ack cycle count); `acknowledge` setting cutoff=counter.

- [ ] **Step 3: Sanity-bite**

Temporarily change `Detect`'s order to check `CheckNoProg` BEFORE `CheckFrozen`. On the precedence scenario (frozen+noprog both hold, exp="frozen") this now returns "noprog" → `<<"StuckDetector FAIL", ...>>`. REVERT. (Confirms precedence is load-bearing.)

- [ ] **Step 4: Register**: append `("StuckDetector", <N>)` to `MODULES`.

- [ ] **Step 5: Run the runner**: `python3 formal/run.py` → all PASS, exit 0.

- [ ] **Step 6: Commit**

```bash
git add formal/specs/StuckDetector.tla formal/run.py
git commit -m "test(formal): StuckDetector precedence/threshold/ack-suppression spec

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: README — Phase 4 map + roadmap completion note

**Files:** Modify `formal/README.md`.

- [ ] **Step 1: Append two rows to the `Property -> code map` table (3-column format)**

```markdown
| `SkillXpCurve.tla` | `ai/learning/skill_xp_curve.py:34,46,57,65` | `required_xp` is exact on observed levels and 0 below/with no data; `confidence` = observed-in-gap / gap-size in [0,1] with `is_confident` iff full coverage; `cycles_to_level` is 0 when target<=current and infinite when xp/cycle<=0; `total_xp_to_reach` is monotone; `growth_ratio` defaults until >=2 consecutive levels are observed. (The geometric `growth_ratio**steps` estimate is abstracted — verified by inspection, like PredictWin's hit math.) |
| `StuckDetector.tla` | `ai/recovery.py:38,48,55,64,74` | `detect` honors precedence STATE_FROZEN > GOAL_OSCILLATION > NO_PROGRESS; the thresholds (4 `<no_plan>` / 8 cycles with exactly 2 distinct goals / 10 cycles with a state recurring >=5); `_recent_since` windows only cycles added after the acknowledge cutoff, so an acknowledged signal cannot re-fire until fresh cycles accumulate. |
```

- [ ] **Step 2: Append a Phase-4 modeling note + roadmap-complete note under `## Modeling notes`**

```markdown
- The learning/recovery specs (`SkillXpCurve`, `StuckDetector`) complete the pure-component
  roadmap. `SkillXpCurve` is integer-only: the geometric float estimate
  (`growth_ratio` mean and `anchor * growth_ratio ** steps`) and the `cycles_to_level`
  quotient are abstracted (their branch structure and the integer/count properties —
  observed-exactness, confidence in [0,1], is_confident, monotonicity, default-ratio
  condition — are proved). `StuckDetector` is a fully-modeled deterministic state machine
  over a bounded history + acknowledge cutoffs; the windowing/precedence/ack-suppression
  are verified against hand-computed expected verdicts.
- **Roadmap complete:** all pure-deterministic AI components with a non-trivial correctness
  property are now modeled (pathfinding, recipe closure, prerequisite graph, combat
  prediction, inventory/economy, combat/equipment, strategy/feasibility, learning/recovery).
  The remaining `ai/` modules are I/O-, learning-store-, or orchestration-bound and have no
  pure contract PlusPy can check (see the design doc's out-of-scope list).
```

- [ ] **Step 3: Final full run**

Run: `python3 formal/run.py`
Expected: every module PASS (13 prior + SkillXpCurve + StuckDetector = 15), exit 0. Slow — be patient.

- [ ] **Step 4: Commit**

```bash
git add formal/README.md
git commit -m "docs(formal): map Phase 4 learning/recovery specs + mark roadmap complete

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review notes (addressed)

- **Spec coverage:** SkillXpCurve's `required_xp`/`confidence`/`is_confident`/`cycles_to_level`/`total_xp_to_reach`/`growth_ratio` (Task 1); StuckDetector's `detect`/three checks/`_recent_since`/`acknowledge` (Task 2); README + roadmap-complete (Task 3).
- **Float honesty:** SkillXpCurve's float arithmetic (growth_ratio mean, `**` estimate, cycles quotient) is explicitly abstracted and disclosed in the header + README; the integer/count/branch properties are what's proved. This matches the PredictWin precedent and is stated, not hidden.
- **Independent oracles + non-vacuity:** SkillXpCurve `ReqCorrect`/`ConfCorrect` use recomputed bounds + the is_confident⇔full-coverage equivalence; the two FLAGGED tautologies (`GrowthCorrect` X⇔X, and the placeholder `TotalObs`) have explicit required fixes (hand-table for growth, real recursive sum + monotonicity for total). StuckDetector uses hand-computed `exp` per scenario (independent of `Detect`). Each task has a sanity-bite; Task 2's bite targets precedence (load-bearing).
- **No-RECURSIVE / no-float / Sequences:** `TotalObs` and `RecentSince` use bounded recursive functions / `SubSeq`; everything integer; `StuckDetector` EXTENDS Sequences.
- **Placeholders called out:** `TotalObs` (`c_xp_placeholder`/`RECURSIVE_NOTE`) and `RecentSince` (`SortedSeqOfKeptTail`) are explicitly flagged as sketches with concrete "realize it as ..." instructions and "remove the placeholder" directives — the implementer MUST replace them; they are not to be committed as-is.
- **Type/name consistency:** module names and the (computed) MODULES counts are consistent; signal tokens "frozen"/"osc"/"noprog" and record field names used consistently.

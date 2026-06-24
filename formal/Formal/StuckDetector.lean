-- @concept: core @property: safety
/-
Formal model of the `StuckDetector` deterministic state machine from
`src/artifactsmmo_cli/ai/recovery.py`.

The detector keeps a bounded history (a `collections.deque(maxlen=30)`) of cycle
records, a monotone global cycle counter, and per-signal acknowledge cutoffs.
`detect()` returns the FIRST matching signal in strict precedence
`STATE_FROZEN > GOAL_OSCILLATION > NO_PROGRESS`, else `none`.

We model:
* a record as `(state, goal, action)` where `action` is `true` iff it is the
  `"<no_plan>"` sentinel (the only field `_check_no_progress` reads);
* the history as a `List Rec` (oldest first, mirroring `list(deque)`);
* a global `counter : Nat` with `counter ≥ history.length` — the deque's
  `maxlen` eviction means the buffer holds only the most recent `len` of the
  `counter` records ever seen, so the oldest buffered record's GLOBAL index is
  `counter - len`;
* three acknowledge cutoffs (one per signal).

`_recent_since(cutoff, count)` is the load-bearing index arithmetic: record `i`
(0-based in the buffer) has global index `start_idx + i` with
`start_idx = counter - len`; it keeps the records whose global index `≥ cutoff`,
then takes the LAST `count` of those (in order). The TLA+ era nearly shipped an
off-by-one here, so `recent_since_window` pins the exact index semantics and the
diff/mutation gate pins it against `start_idx + i ± 1`.

Lean core only — no mathlib.
-/

namespace Formal.StuckDetector

/-- One cycle record. `state`, `goal` and `action` are abstract codes (`Nat`);
`noPlan` is `true` iff `action_name == "<no_plan>"`; `ok` mirrors
`CycleRecord.succeeded` (the oscillation / repeated-action checks count
failures). `action` mirrors the action_name discriminator the repeated-action
check groups by (the `<no_plan>` sentinel's code is irrelevant — that check
excludes `noPlan` records). Mirrors the fields the detector reads. -/
structure Rec where
  state : Nat
  goal : Nat
  noPlan : Bool
  ok : Bool
  action : Nat
  deriving DecidableEq, Repr

/-- The four stuck-state signals. Precedence: `frozen > osc > noprog > repeated`.
`repeated` (REPEATED_ACTION_FAILURE) is the backstop: a single named action that
keeps failing across a window even while other progress happens — the class the
first three miss (the 478 bank loop varied state, didn't oscillate goals, and was
not a 4-consecutive `<no_plan>` run). -/
inductive Signal where
  | frozen
  | osc
  | noprog
  | repeated
  deriving DecidableEq, Repr

/-- The detector configuration: the buffered history (oldest first), the global
cycle counter, and the three acknowledge cutoffs. The well-formedness invariant
`counter ≥ history.length` is supplied to the lemmas that need it. -/
structure Detector where
  history : List Rec
  counter : Nat
  ackFrozen : Nat
  ackOsc : Nat
  ackNoprog : Nat
  ackRepeated : Nat
  deriving Repr

/-- Thresholds (mirror the `count=` arguments / `len(window) <` checks). -/
def noprogThreshold : Nat := 4
def oscThreshold : Nat := 8
def frozenThreshold : Nat := 10

/-- REPEATED_ACTION_FAILURE: the window width (`count=` for `_recent_since`) and
the per-action failure count that fires the signal. Mirrors
`REPEATED_ACTION_WINDOW` / `REPEATED_ACTION_FAILURE_THRESHOLD`. -/
def repeatedWindow : Nat := 20
def repeatedThreshold : Nat := 10

/-- The global start index of the buffered history: `counter - len`. With the
`counter ≥ len` invariant this is the global index of `history[0]`. -/
def startIdx (d : Detector) : Nat := d.counter - d.history.length

/-- `_recent_since(cutoff, count)`: keep the buffered records whose GLOBAL index
`start_idx + i` is `≥ cutoff`, then take the LAST `count` of those, in order.

We attach the global index to each record via `zipIdx`-style enumeration, filter
on `start_idx + i ≥ cutoff`, drop the indices, and `takeLast count`. -/
def takeLast (count : Nat) (xs : List Rec) : List Rec :=
  xs.drop (xs.length - count)

/-- Records paired with their 0-based buffer position. -/
def withIdx (xs : List Rec) : List (Nat × Rec) :=
  (List.range xs.length).zip xs

/-- The post-ack window: filter by global index ≥ cutoff, take the last `count`. -/
def recentSince (d : Detector) (cutoff count : Nat) : List Rec :=
  let kept := ((withIdx d.history).filter
    (fun p => decide (startIdx d + p.1 ≥ cutoff))).map Prod.snd
  takeLast count kept

/-- Count occurrences of a state code in a record window. -/
def stateCount (s : Nat) (w : List Rec) : Nat :=
  (w.filter (fun r => decide (r.state = s))).length

/-- The distinct goals in a window (dedup, order-insensitive count). -/
def distinctGoals (w : List Rec) : List Nat :=
  (w.map Rec.goal).eraseDups

/-- Adjacent goal switches: the number of positions `i` with
`goals[i] ≠ goals[i+1]`. Mirrors
`sum(1 for a, b in pairwise(goals) if a != b)`. -/
def switches : List Nat → Nat
  | a :: b :: rest => (if a = b then 0 else 1) + switches (b :: rest)
  | _ => 0

/-- Failed cycles in a window (`succeeded == False`). -/
def failures (w : List Rec) : Nat :=
  (w.filter (fun r => !r.ok)).length

/-- Genuine-oscillation gates (mirror `OSC_MIN_SWITCHES` / `OSC_MIN_FAILURES`):
≥ 3 adjacent switches means the 2-goal sequence leaves-and-returns at least
twice (two overlapping A→B→A round-trips); ≥ 2 failures means the flapping is
failure-driven, not a benign switch in a productive window. -/
def oscSwitchMin : Nat := 3
def oscFailureMin : Nat := 2

/-- `_check_no_progress`: window of last-4 post-(noprog-ack), `len = 4` AND every
record is the `<no_plan>` sentinel. -/
def checkNoProgress (d : Detector) : Bool :=
  let w := recentSince d d.ackNoprog noprogThreshold
  decide (w.length = noprogThreshold) && w.all (fun r => r.noPlan)

/-- `_check_goal_oscillation`: window of last-8 post-(osc-ack), `len = 8` AND
EXACTLY 2 distinct goals AND ≥ `oscSwitchMin` adjacent goal switches (genuine
alternation) AND ≥ `oscFailureMin` failed cycles (failure-driven flapping).
The 2026-06-10 false-positive family (7×A+1×B clean switch; mostly-productive
windows) fails the switch/failure gates and can no longer fire. -/
def checkGoalOscillation (d : Detector) : Bool :=
  let w := recentSince d d.ackOsc oscThreshold
  decide (w.length = oscThreshold) && decide ((distinctGoals w).length = 2)
    && decide (switches (w.map Rec.goal) ≥ oscSwitchMin)
    && decide (failures w ≥ oscFailureMin)

/-- `_check_state_frozen`: window of last-10 post-(frozen-ack), `len = 10` AND
some state recurs `≥ 5`. -/
def checkStateFrozen (d : Detector) : Bool :=
  let w := recentSince d d.ackFrozen frozenThreshold
  decide (w.length = frozenThreshold) &&
    (w.any (fun r => decide (stateCount r.state w ≥ 5)))

/-- Number of FAILED, non-`noPlan` records in a window whose action code is `a`.
Mirrors `counts[action_name] += 1 for rec if not rec.succeeded and action_name !=
"<no_plan>"`. The `noPlan` exclusion keeps the no-plan flood (which NO_PROGRESS
owns) from also tripping this signal. -/
def actionFailCount (a : Nat) (w : List Rec) : Nat :=
  (w.filter (fun r => decide (r.action = a ∧ r.ok = false ∧ r.noPlan = false))).length

/-- The maximum per-action failure count over the window. Mapping over the window
records covers exactly the action codes that appear; a code with no failing
record contributes 0, so this equals `max(counts.values(), default=0)`. -/
def maxActionFailCount (w : List Rec) : Nat :=
  (w.map (fun r => actionFailCount r.action w)).foldl Nat.max 0

/-- `_check_repeated_action_failure`: in the post-(repeated-ack) last-`repeatedWindow`
window, some named action failed `≥ repeatedThreshold` times. Unlike the other
checks this needs NO full window — interspersed progress is tolerated; only the
per-action failure tally matters. -/
def checkRepeatedAction (d : Detector) : Bool :=
  decide (maxActionFailCount (recentSince d d.ackRepeated repeatedWindow) ≥ repeatedThreshold)

/-- `detect()`: strict precedence frozen > osc > noprog > repeated, else none. -/
def detect (d : Detector) : Option Signal :=
  if checkStateFrozen d then some Signal.frozen
  else if checkGoalOscillation d then some Signal.osc
  else if checkNoProgress d then some Signal.noprog
  else if checkRepeatedAction d then some Signal.repeated
  else none

/-- `acknowledge(signal)`: set that signal's cutoff to the current counter. -/
def acknowledge (d : Detector) (s : Signal) : Detector :=
  match s with
  | Signal.frozen => { d with ackFrozen := d.counter }
  | Signal.osc => { d with ackOsc := d.counter }
  | Signal.noprog => { d with ackNoprog := d.counter }
  | Signal.repeated => { d with ackRepeated := d.counter }

/-! ## Theorems -/

/-- **recent_since_window** (index arithmetic, pinned).
`recentSince` is exactly: of the buffered records, keep those whose GLOBAL index
`startIdx d + i` (record `i`) is `≥ cutoff`, then take the LAST `count`, in order.
This is the definitional spelling, stated as the canonical reference identity so
that any `± 1` perturbation of `startIdx d + i` is provably a different function. -/
theorem recent_since_window (d : Detector) (cutoff count : Nat) :
    recentSince d cutoff count
      = takeLast count
          (((List.range d.history.length).zip d.history
            |>.filter (fun p => decide (startIdx d + p.1 ≥ cutoff))).map Prod.snd) := by
  rfl

/-- **recent_since_index**: a buffered record `i` is kept by `recentSince … 0`
exactly at its true global index, and the global index of buffer position `i`
under the `counter ≥ len` invariant is `(counter - len) + i`. Pins the
start-index formula directly (a `± 1` mutant changes this value). -/
theorem recent_since_start_idx (d : Detector) (h : d.history.length ≤ d.counter) :
    startIdx d = d.counter - d.history.length ∧
    (∀ i, i < d.history.length → startIdx d + i ≤ d.counter - 1 → startIdx d + i < d.counter) := by
  refine ⟨rfl, ?_⟩
  intro i _ hle
  omega

/-- **detect_precedence**: `detect` honors the strict order
frozen > osc > noprog > repeated. Each clause is exactly the cascaded `if`. -/
theorem detect_precedence (d : Detector) :
    (checkStateFrozen d = true → detect d = some Signal.frozen) ∧
    (checkStateFrozen d = false → checkGoalOscillation d = true →
      detect d = some Signal.osc) ∧
    (checkStateFrozen d = false → checkGoalOscillation d = false →
      checkNoProgress d = true → detect d = some Signal.noprog) ∧
    (checkStateFrozen d = false → checkGoalOscillation d = false →
      checkNoProgress d = false → checkRepeatedAction d = true →
      detect d = some Signal.repeated) ∧
    (checkStateFrozen d = false → checkGoalOscillation d = false →
      checkNoProgress d = false → checkRepeatedAction d = false →
      detect d = none) := by
  refine ⟨?_, ?_, ?_, ?_, ?_⟩ <;> intro <;> simp_all [detect]

/-- **detect_frozen_wins**: frozen-check holding forces `frozen`, REGARDLESS of
whether the osc/noprog checks also hold (the anti-gaming precedence anchor). -/
theorem detect_frozen_wins (d : Detector) (hf : checkStateFrozen d = true) :
    detect d = some Signal.frozen := by
  simp [detect, hf]

/-- **detect_osc_over_noprog**: with frozen false and osc true, `osc` wins even if
noprog would also fire. -/
theorem detect_osc_over_noprog (d : Detector)
    (hf : checkStateFrozen d = false) (ho : checkGoalOscillation d = true) :
    detect d = some Signal.osc := by
  simp [detect, hf, ho]

/-- **noprog_threshold**: noprog fires IFF the post-ack last-4 window has exactly
4 records, all `<no_plan>`. -/
theorem noprog_threshold (d : Detector) :
    checkNoProgress d = true
      ↔ ((recentSince d d.ackNoprog noprogThreshold).length = noprogThreshold ∧
          (recentSince d d.ackNoprog noprogThreshold).all (fun r => r.noPlan) = true) := by
  unfold checkNoProgress
  simp only [Bool.and_eq_true, decide_eq_true_eq]

/-- **osc_threshold**: osc fires IFF the post-ack last-8 window has 8 records,
EXACTLY 2 distinct goals, ≥ `oscSwitchMin` adjacent goal switches AND
≥ `oscFailureMin` failures. (Genuine-oscillation semantics, 2026-06-10.) -/
theorem osc_threshold (d : Detector) :
    checkGoalOscillation d = true
      ↔ ((recentSince d d.ackOsc oscThreshold).length = oscThreshold ∧
          (distinctGoals (recentSince d d.ackOsc oscThreshold)).length = 2 ∧
          switches ((recentSince d d.ackOsc oscThreshold).map Rec.goal) ≥ oscSwitchMin ∧
          failures (recentSince d d.ackOsc oscThreshold) ≥ oscFailureMin) := by
  unfold checkGoalOscillation
  simp only [Bool.and_eq_true, decide_eq_true_eq, and_assoc]

/-- **osc_requires_round_trips**: a window whose goal sequence has fewer than
`oscSwitchMin` adjacent switches can NEVER fire osc, no matter how it fails.
This is the 2026-06-10 clean-switch regression (7×GrindCharacterXP then
1×TaskExchange = 1 switch) proved impossible for ALL inputs. -/
theorem osc_requires_round_trips (d : Detector)
    (h : switches ((recentSince d d.ackOsc oscThreshold).map Rec.goal) < oscSwitchMin) :
    checkGoalOscillation d = false := by
  cases hc : checkGoalOscillation d
  · rfl
  · obtain ⟨-, -, hsw, -⟩ := (osc_threshold d).mp hc
    omega

/-- **osc_requires_failures**: a window with fewer than `oscFailureMin` failed
cycles can NEVER fire osc — productive alternation between two goals (e.g.
gather/deposit loops) is not a livelock. -/
theorem osc_requires_failures (d : Detector)
    (h : failures (recentSince d d.ackOsc oscThreshold) < oscFailureMin) :
    checkGoalOscillation d = false := by
  cases hc : checkGoalOscillation d
  · rfl
  · obtain ⟨-, -, -, hfail⟩ := (osc_threshold d).mp hc
    omega

/-! ### Trace-locked regressions (2026-06-10 sessions, replayed exactly)

Goal codes: 0 = GrindCharacterXP, 1 = TaskExchange / other. States distinct
per cycle (the bot was acting), so frozen cannot fire and `detect` reflects
the oscillation verdict alone. -/

/-- The benign window that false-fired at cycles 20/30/46 of the `-160206`
session: 7 productive Grind cycles then 1 productive TaskExchange — a clean
goal switch (1 switch, 0 failures). -/
def cleanSwitchTrace : Detector :=
  { history :=
      [⟨0, 0, false, true, 0⟩, ⟨1, 0, false, true, 0⟩, ⟨2, 0, false, true, 0⟩,
       ⟨3, 0, false, true, 0⟩, ⟨4, 0, false, true, 0⟩, ⟨5, 0, false, true, 0⟩,
       ⟨6, 0, false, true, 0⟩, ⟨7, 1, false, true, 1⟩],
    counter := 8, ackFrozen := 0, ackOsc := 0, ackNoprog := 0, ackRepeated := 0 }

/-- **clean_switch_no_fire**: the clean-switch trace window must NOT fire. -/
theorem clean_switch_no_fire : detect cleanSwitchTrace = none := by decide

/-- A mostly-productive window: 7 ok cycles of one goal and a single failing
cycle of another (the 7-productive+1-other false-positive class). -/
def mostlyProductiveTrace : Detector :=
  { history :=
      [⟨0, 0, false, true, 0⟩, ⟨1, 0, false, true, 0⟩, ⟨2, 0, false, true, 0⟩,
       ⟨3, 0, false, true, 0⟩, ⟨4, 0, false, true, 0⟩, ⟨5, 0, false, true, 0⟩,
       ⟨6, 0, false, true, 0⟩, ⟨7, 1, false, false, 1⟩],
    counter := 8, ackFrozen := 0, ackOsc := 0, ackNoprog := 0, ackRepeated := 0 }

/-- **mostly_productive_no_fire**: one failing odd cycle in a productive
window must NOT fire. -/
theorem mostly_productive_no_fire : detect mostlyProductiveTrace = none := by decide

/-- Genuine failure-driven flapping: A→B→A→B… with every cycle failing. -/
def genuineFlapTrace : Detector :=
  { history :=
      [⟨0, 0, false, false, 0⟩, ⟨1, 1, false, false, 1⟩, ⟨2, 0, false, false, 0⟩,
       ⟨3, 1, false, false, 1⟩, ⟨4, 0, false, false, 0⟩, ⟨5, 1, false, false, 1⟩,
       ⟨6, 0, false, false, 0⟩, ⟨7, 1, false, false, 1⟩],
    counter := 8, ackFrozen := 0, ackOsc := 0, ackNoprog := 0, ackRepeated := 0 }

/-- **genuine_flap_fires**: real failure-driven oscillation still fires. -/
theorem genuine_flap_fires : detect genuineFlapTrace = some Signal.osc := by decide

/-- **frozen_threshold**: frozen fires IFF the post-ack last-10 window has 10
records and SOME state recurs ≥ 5. -/
theorem frozen_threshold (d : Detector) :
    checkStateFrozen d = true
      ↔ ((recentSince d d.ackFrozen frozenThreshold).length = frozenThreshold ∧
          ∃ r ∈ recentSince d d.ackFrozen frozenThreshold,
            stateCount r.state (recentSince d d.ackFrozen frozenThreshold) ≥ 5) := by
  unfold checkStateFrozen
  simp only [Bool.and_eq_true, decide_eq_true_eq, List.any_eq_true]

/-- A record is kept by `recentSince` only if its global index `≥ cutoff`: every
member of the post-filter list came from a buffer position `i` with
`startIdx d + i ≥ cutoff` and `history[i] = r`. Pins that the filter genuinely
uses the per-record global index (a `± 1` start-index mutant changes the kept
set). -/
theorem recentSince_mem_global (d : Detector) (cutoff count : Nat) (r : Rec) :
    r ∈ recentSince d cutoff count →
      ∃ i, i < d.history.length ∧
        startIdx d + i ≥ cutoff ∧ d.history[i]? = some r := by
  intro hr
  unfold recentSince takeLast withIdx at hr
  have hr' := List.mem_of_mem_drop hr
  simp only [List.mem_map, List.mem_filter] at hr'
  obtain ⟨p, ⟨hpmem, hpf⟩, hpr⟩ := hr'
  -- p comes from `(range len).zip history`; identify p = (i, history[i]).
  obtain ⟨hp1, hp2⟩ := List.of_mem_zip hpmem
  have hlt : p.1 < d.history.length := by simpa using List.mem_range.mp hp1
  -- zip of (range n) with l: the pair at position k has first = k, second = l[k].
  obtain ⟨k, hk, hkeq⟩ := List.mem_iff_getElem.mp hpmem
  have hkhist : k < d.history.length := by
    have hlz := List.length_zip (l₁ := List.range d.history.length) (l₂ := d.history)
    simp only [List.length_range] at hlz
    omega
  have hzfst : (((List.range d.history.length).zip d.history)[k]'hk).1 = k := by
    rw [List.getElem_zip]; simp [List.getElem_range]
  have hzsnd : (((List.range d.history.length).zip d.history)[k]'hk).2 = d.history[k] := by
    rw [List.getElem_zip]
  rw [hkeq] at hzfst hzsnd
  have e1 : p.1 = k := hzfst
  have esnd : p.2 = d.history[k] := hzsnd
  refine ⟨p.1, hlt, ?_, ?_⟩
  · exact of_decide_eq_true hpf
  · rw [e1, List.getElem?_eq_getElem hkhist, ← hpr, esnd]

/-- **ack_suppression**: immediately after `acknowledge(noprog)` the noprog window
is EMPTY (every buffered record has global index `< counter`, but the cutoff is
now `counter`), so noprog cannot fire until ≥ threshold fresh records accumulate.
Requires the well-formedness invariant `counter ≥ len`. -/
theorem ack_suppression_noprog (d : Detector) (h : d.history.length ≤ d.counter) :
    recentSince (acknowledge d Signal.noprog) (acknowledge d Signal.noprog).ackNoprog
      noprogThreshold = [] := by
  -- After ack, ackNoprog = counter; every buffer index i < len ⇒ startIdx + i < counter.
  unfold acknowledge recentSince takeLast withIdx startIdx
  simp only
  -- the filter predicate `counter ≤ (counter - len) + i` is false for all i < len
  have hempty :
      (((List.range d.history.length).zip d.history).filter
        (fun p => decide (d.counter - d.history.length + p.1 ≥ d.counter))).map Prod.snd = [] := by
    rw [List.filter_eq_nil_iff.mpr]
    · simp
    · intro p hp
      have hz := List.of_mem_zip hp
      have hlt : p.1 < d.history.length := by simpa using List.mem_range.mp hz.1
      simp only [decide_eq_true_eq, ge_iff_le]
      omega
  rw [hempty]
  simp

/-- **ack_suppression_general**: after ack of ANY signal, that signal's freshly
configured window is empty. -/
theorem ack_suppression_frozen (d : Detector) (h : d.history.length ≤ d.counter) :
    recentSince (acknowledge d Signal.frozen) (acknowledge d Signal.frozen).ackFrozen
      frozenThreshold = [] := by
  unfold acknowledge recentSince takeLast withIdx startIdx
  simp only
  have hempty :
      (((List.range d.history.length).zip d.history).filter
        (fun p => decide (d.counter - d.history.length + p.1 ≥ d.counter))).map Prod.snd = [] := by
    rw [List.filter_eq_nil_iff.mpr]
    · simp
    · intro p hp
      have hz := List.of_mem_zip hp
      have hlt : p.1 < d.history.length := by simpa using List.mem_range.mp hz.1
      simp only [decide_eq_true_eq, ge_iff_le]
      omega
  rw [hempty]; simp

theorem ack_suppression_osc (d : Detector) (h : d.history.length ≤ d.counter) :
    recentSince (acknowledge d Signal.osc) (acknowledge d Signal.osc).ackOsc
      oscThreshold = [] := by
  unfold acknowledge recentSince takeLast withIdx startIdx
  simp only
  have hempty :
      (((List.range d.history.length).zip d.history).filter
        (fun p => decide (d.counter - d.history.length + p.1 ≥ d.counter))).map Prod.snd = [] := by
    rw [List.filter_eq_nil_iff.mpr]
    · simp
    · intro p hp
      have hz := List.of_mem_zip hp
      have hlt : p.1 < d.history.length := by simpa using List.mem_range.mp hz.1
      simp only [decide_eq_true_eq, ge_iff_le]
      omega
  rw [hempty]; simp

/-- **ack_suppression_no_fire**: an empty post-ack window can never satisfy the
threshold checks (since `0 ≠ 4/8/10`), so the just-acked signal cannot re-fire. -/
theorem ack_noprog_cannot_fire (d : Detector) (h : d.history.length ≤ d.counter) :
    checkNoProgress (acknowledge d Signal.noprog) = false := by
  unfold checkNoProgress
  rw [ack_suppression_noprog d h]
  simp [noprogThreshold]

theorem ack_frozen_cannot_fire (d : Detector) (h : d.history.length ≤ d.counter) :
    checkStateFrozen (acknowledge d Signal.frozen) = false := by
  unfold checkStateFrozen
  rw [ack_suppression_frozen d h]
  simp [frozenThreshold]

theorem ack_osc_cannot_fire (d : Detector) (h : d.history.length ≤ d.counter) :
    checkGoalOscillation (acknowledge d Signal.osc) = false := by
  unfold checkGoalOscillation
  rw [ack_suppression_osc d h]
  simp [oscThreshold, distinctGoals]

/-! ### REPEATED_ACTION_FAILURE role theorems (spec 2026-06-24).

The 4th signal: a single named action that keeps failing across a window even
amid interspersed progress (the 478 bank loop class). The teeth are
`repeated_fire_witness` — firing is NON-VACUOUS: it implies a genuine action code
that failed `≥ repeatedThreshold` times, with an actual failing record. -/

/-- A foldl-max over `Nat` that clears a positive threshold `t` (starting below
`t`) must have a list element `≥ t`. Core-only replacement for the Mathlib
`List.le_foldl_max`-style lemma; load-bearing for the firing witness. -/
private theorem le_foldl_max {t : Nat} :
    ∀ (l : List Nat) (init : Nat), init < t → t ≤ l.foldl Nat.max init → ∃ x ∈ l, t ≤ x
  | [], init, hinit, h => by
      simp only [List.foldl_nil] at h
      exact absurd h (Nat.not_le.mpr hinit)
  | a :: as, init, hinit, h => by
      simp only [List.foldl_cons] at h
      by_cases ha : t ≤ a
      · exact ⟨a, List.mem_cons_self, ha⟩
      · have hlt : Nat.max init a < t := Nat.max_lt.mpr ⟨hinit, Nat.lt_of_not_le ha⟩
        obtain ⟨x, hx, hxt⟩ := le_foldl_max as (Nat.max init a) hlt h
        exact ⟨x, List.mem_cons_of_mem a hx, hxt⟩

/-- **maxActionFailCount_witness**: a window whose max per-action failure tally
clears a positive `t` has a record whose action's tally clears `t`. -/
theorem maxActionFailCount_witness {w : List Rec} {t : Nat} (ht : 0 < t)
    (h : t ≤ maxActionFailCount w) :
    ∃ r ∈ w, t ≤ actionFailCount r.action w := by
  unfold maxActionFailCount at h
  obtain ⟨y, hy, hyt⟩ := le_foldl_max (w.map (fun r => actionFailCount r.action w)) 0 ht h
  obtain ⟨r, hr, hreq⟩ := List.mem_map.mp hy
  subst hreq
  exact ⟨r, hr, hyt⟩

/-- **actionFailCount_witness**: a positive failure tally for action `a` exhibits
an actual failing, non-`noPlan` record with that action code. -/
theorem actionFailCount_witness {a : Nat} {w : List Rec} (h : 0 < actionFailCount a w) :
    ∃ r ∈ w, r.action = a ∧ r.ok = false ∧ r.noPlan = false := by
  unfold actionFailCount at h
  have hne : w.filter (fun r => decide (r.action = a ∧ r.ok = false ∧ r.noPlan = false)) ≠ [] := by
    intro hnil; rw [hnil, List.length_nil] at h; exact absurd h (Nat.lt_irrefl 0)
  obtain ⟨r, hr⟩ := List.exists_mem_of_ne_nil _ hne
  rw [List.mem_filter] at hr
  exact ⟨r, hr.1, decide_eq_true_eq.mp hr.2⟩

/-- **repeated_threshold**: repeated fires IFF the post-ack last-`repeatedWindow`
window has some action failing `≥ repeatedThreshold` times. -/
theorem repeated_threshold (d : Detector) :
    checkRepeatedAction d = true
      ↔ maxActionFailCount (recentSince d d.ackRepeated repeatedWindow) ≥ repeatedThreshold := by
  unfold checkRepeatedAction
  simp only [decide_eq_true_eq]

/-- **repeated_requires_failures**: a window whose max per-action failure tally is
below threshold can NEVER fire repeated — interspersed progress without any one
action failing `repeatedThreshold` times is not a livelock. -/
theorem repeated_requires_failures (d : Detector)
    (h : maxActionFailCount (recentSince d d.ackRepeated repeatedWindow) < repeatedThreshold) :
    checkRepeatedAction d = false := by
  unfold checkRepeatedAction
  simp only [decide_eq_false_iff_not, ge_iff_le, Nat.not_le]
  exact h

/-- **repeated_fire_witness** (NON-VACUITY): if repeated fires, there is a genuine
action code that failed `≥ repeatedThreshold` times in the window, witnessed by an
actual failing, non-`noPlan` record. A vacuous spec could not produce this. -/
theorem repeated_fire_witness (d : Detector) :
    checkRepeatedAction d = true →
    ∃ a, repeatedThreshold ≤ actionFailCount a (recentSince d d.ackRepeated repeatedWindow)
      ∧ ∃ r ∈ recentSince d d.ackRepeated repeatedWindow,
          r.action = a ∧ r.ok = false ∧ r.noPlan = false := by
  intro hfire
  have hmax : repeatedThreshold ≤ maxActionFailCount (recentSince d d.ackRepeated repeatedWindow) :=
    (repeated_threshold d).mp hfire
  obtain ⟨r, _, hrc⟩ := maxActionFailCount_witness (by decide) hmax
  exact ⟨r.action, hrc, actionFailCount_witness (Nat.lt_of_lt_of_le (by decide) hrc)⟩

/-- **detect_repeated_last**: with frozen/osc/noprog all false and repeated true,
`detect` returns `repeated` (the backstop fires only after the first three pass). -/
theorem detect_repeated_last (d : Detector)
    (hf : checkStateFrozen d = false) (ho : checkGoalOscillation d = false)
    (hn : checkNoProgress d = false) (hr : checkRepeatedAction d = true) :
    detect d = some Signal.repeated := by
  simp [detect, hf, ho, hn, hr]

/-- **ack_suppression_repeated**: after `acknowledge(repeated)` the repeated window
is EMPTY (cutoff now = counter), mirroring the other signals. -/
theorem ack_suppression_repeated (d : Detector) (h : d.history.length ≤ d.counter) :
    recentSince (acknowledge d Signal.repeated) (acknowledge d Signal.repeated).ackRepeated
      repeatedWindow = [] := by
  unfold acknowledge recentSince takeLast withIdx startIdx
  simp only
  have hempty :
      (((List.range d.history.length).zip d.history).filter
        (fun p => decide (d.counter - d.history.length + p.1 ≥ d.counter))).map Prod.snd = [] := by
    rw [List.filter_eq_nil_iff.mpr]
    · simp
    · intro p hp
      have hz := List.of_mem_zip hp
      have hlt : p.1 < d.history.length := by simpa using List.mem_range.mp hz.1
      simp only [decide_eq_true_eq, ge_iff_le]
      omega
  rw [hempty]; simp

/-- **ack_repeated_cannot_fire**: an empty post-ack window has max failure tally 0
(`< repeatedThreshold`), so the just-acked repeated signal cannot re-fire. -/
theorem ack_repeated_cannot_fire (d : Detector) (h : d.history.length ≤ d.counter) :
    checkRepeatedAction (acknowledge d Signal.repeated) = false := by
  unfold checkRepeatedAction
  rw [ack_suppression_repeated d h]
  simp [maxActionFailCount, repeatedThreshold]

/-! ### REPEATED_ACTION_FAILURE trace regressions (the 478 bank-loop class).

20 distinct states (frozen quiet), one goal code (osc needs exactly 2 — quiet),
named actions (noprog quiet). Action code 0 = the wedged `Withdraw`, action 1 =
interspersed productive cycles. -/

/-- The wedged class: action 0 fails 10× among 10 interspersed successes. -/
def repeatedFiresTrace : Detector :=
  { history :=
      [⟨0, 0, false, false, 0⟩, ⟨1, 0, false, true, 1⟩, ⟨2, 0, false, false, 0⟩,
       ⟨3, 0, false, true, 1⟩, ⟨4, 0, false, false, 0⟩, ⟨5, 0, false, true, 1⟩,
       ⟨6, 0, false, false, 0⟩, ⟨7, 0, false, true, 1⟩, ⟨8, 0, false, false, 0⟩,
       ⟨9, 0, false, true, 1⟩, ⟨10, 0, false, false, 0⟩, ⟨11, 0, false, true, 1⟩,
       ⟨12, 0, false, false, 0⟩, ⟨13, 0, false, true, 1⟩, ⟨14, 0, false, false, 0⟩,
       ⟨15, 0, false, true, 1⟩, ⟨16, 0, false, false, 0⟩, ⟨17, 0, false, true, 1⟩,
       ⟨18, 0, false, false, 0⟩, ⟨19, 0, false, true, 1⟩],
    counter := 20, ackFrozen := 0, ackOsc := 0, ackNoprog := 0, ackRepeated := 0 }

/-- **repeated_fires**: the wedged 10-of-20 trace fires repeated. -/
theorem repeated_fires : detect repeatedFiresTrace = some Signal.repeated := by decide

/-- One short: action 0 fails only 9× (the first failing cycle is now a success),
below the threshold. -/
def repeatedOneShortTrace : Detector :=
  { history :=
      [⟨0, 0, false, true, 1⟩, ⟨1, 0, false, true, 1⟩, ⟨2, 0, false, false, 0⟩,
       ⟨3, 0, false, true, 1⟩, ⟨4, 0, false, false, 0⟩, ⟨5, 0, false, true, 1⟩,
       ⟨6, 0, false, false, 0⟩, ⟨7, 0, false, true, 1⟩, ⟨8, 0, false, false, 0⟩,
       ⟨9, 0, false, true, 1⟩, ⟨10, 0, false, false, 0⟩, ⟨11, 0, false, true, 1⟩,
       ⟨12, 0, false, false, 0⟩, ⟨13, 0, false, true, 1⟩, ⟨14, 0, false, false, 0⟩,
       ⟨15, 0, false, true, 1⟩, ⟨16, 0, false, false, 0⟩, ⟨17, 0, false, true, 1⟩,
       ⟨18, 0, false, false, 0⟩, ⟨19, 0, false, true, 1⟩],
    counter := 20, ackFrozen := 0, ackOsc := 0, ackNoprog := 0, ackRepeated := 0 }

/-- **repeated_one_short_no_fire**: 9 failures of one action does NOT fire. -/
theorem repeated_one_short_no_fire : detect repeatedOneShortTrace = none := by decide

end Formal.StuckDetector

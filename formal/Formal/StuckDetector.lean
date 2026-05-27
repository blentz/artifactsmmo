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

/-- One cycle record. `state` and `goal` are abstract codes (`Nat`); `noPlan` is
`true` iff `action_name == "<no_plan>"` (the only action property the detector
reads). Mirrors the relevant fields of `CycleRecord`. -/
structure Rec where
  state : Nat
  goal : Nat
  noPlan : Bool
  deriving DecidableEq, Repr

/-- The three stuck-state signals. Precedence: `frozen > osc > noprog`. -/
inductive Signal where
  | frozen
  | osc
  | noprog
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
  deriving Repr

/-- Thresholds (mirror the `count=` arguments / `len(window) <` checks). -/
def noprogThreshold : Nat := 4
def oscThreshold : Nat := 8
def frozenThreshold : Nat := 10

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

/-- `_check_no_progress`: window of last-4 post-(noprog-ack), `len = 4` AND every
record is the `<no_plan>` sentinel. -/
def checkNoProgress (d : Detector) : Bool :=
  let w := recentSince d d.ackNoprog noprogThreshold
  decide (w.length = noprogThreshold) && w.all (fun r => r.noPlan)

/-- `_check_goal_oscillation`: window of last-8 post-(osc-ack), `len = 8` AND
EXACTLY 2 distinct goals. -/
def checkGoalOscillation (d : Detector) : Bool :=
  let w := recentSince d d.ackOsc oscThreshold
  decide (w.length = oscThreshold) && decide ((distinctGoals w).length = 2)

/-- `_check_state_frozen`: window of last-10 post-(frozen-ack), `len = 10` AND
some state recurs `≥ 5`. -/
def checkStateFrozen (d : Detector) : Bool :=
  let w := recentSince d d.ackFrozen frozenThreshold
  decide (w.length = frozenThreshold) &&
    (w.any (fun r => decide (stateCount r.state w ≥ 5)))

/-- `detect()`: strict precedence frozen > osc > noprog, else none. -/
def detect (d : Detector) : Option Signal :=
  if checkStateFrozen d then some Signal.frozen
  else if checkGoalOscillation d then some Signal.osc
  else if checkNoProgress d then some Signal.noprog
  else none

/-- `acknowledge(signal)`: set that signal's cutoff to the current counter. -/
def acknowledge (d : Detector) (s : Signal) : Detector :=
  match s with
  | Signal.frozen => { d with ackFrozen := d.counter }
  | Signal.osc => { d with ackOsc := d.counter }
  | Signal.noprog => { d with ackNoprog := d.counter }

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

/-- **detect_precedence**: `detect` honors the strict order frozen > osc > noprog.
Each clause is exactly the cascaded `if`. -/
theorem detect_precedence (d : Detector) :
    (checkStateFrozen d = true → detect d = some Signal.frozen) ∧
    (checkStateFrozen d = false → checkGoalOscillation d = true →
      detect d = some Signal.osc) ∧
    (checkStateFrozen d = false → checkGoalOscillation d = false →
      checkNoProgress d = true → detect d = some Signal.noprog) ∧
    (checkStateFrozen d = false → checkGoalOscillation d = false →
      checkNoProgress d = false → detect d = none) := by
  refine ⟨?_, ?_, ?_, ?_⟩ <;> intro <;> simp_all [detect]

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

/-- **osc_threshold**: osc fires IFF the post-ack last-8 window has 8 records with
EXACTLY 2 distinct goals. -/
theorem osc_threshold (d : Detector) :
    checkGoalOscillation d = true
      ↔ ((recentSince d d.ackOsc oscThreshold).length = oscThreshold ∧
          (distinctGoals (recentSince d d.ackOsc oscThreshold)).length = 2) := by
  unfold checkGoalOscillation
  simp only [Bool.and_eq_true, decide_eq_true_eq]

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

end Formal.StuckDetector

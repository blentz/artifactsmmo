-- @concept: recovery, failures @property: safety, liveness, totality
/-
What a repeatedly-failing action's failure means, and how long it is blocked
(`src/artifactsmmo_cli/ai/failure_recovery_core.py`; USER 2026-10-09:
"Classify by HTTP code").

The old recovery blocked a repeating action for 10, then 30 cycles and then
re-admitted it, so a STRUCTURAL failure (HTTP 598, content not at the tile)
repeated forever. Here a structural block carries its PREMISE (the active-event
set, abstracted to a `Nat` signature) and no tick lifts it; a transport block
counts down and expires.

## The model

A block is `(left, premise?)`. The table is an association list keyed on the
action's `learning_key` (abstracted to `Nat`). `tick` keeps a structural entry
unchanged, decrements a transport entry and drops it at 1. `blockedBy p` holds
for a transport entry, and for a structural entry recorded under `p`.
-/

namespace Formal.FailureRecovery

/-- A block: ticks left, and the premise of a structural block. -/
abbrev Block := Nat × Option Nat

def tickOne : Block → Option Block
  | (left, some p) => some (left, some p)
  | (left, none) => if 1 < left then some (left - 1, none) else none

def tick : List (Nat × Block) → List (Nat × Block)
  | [] => []
  | (k, b) :: rest =>
    match tickOne b with
    | some b' => (k, b') :: tick rest
    | none => tick rest

def blocksNow (premise : Nat) : Block → Bool
  | (_, none) => true
  | (_, some p) => decide (p = premise)

def isBlocked (table : List (Nat × Block)) (premise key : Nat) : Bool :=
  table.any fun e => decide (e.1 = key) && blocksNow premise e.2

def tickN : Nat → List (Nat × Block) → List (Nat × Block)
  | 0, t => t
  | n + 1, t => tickN n (tick t)

/-! ## Theorems -/

theorem mem_tick_structural (t : List (Nat × Block)) (k left p : Nat)
    (h : (k, (left, some p)) ∈ t) : (k, (left, some p)) ∈ tick t := by
  induction t with
  | nil => cases h
  | cons e rest ih =>
    obtain ⟨k', b⟩ := e
    rcases List.mem_cons.mp h with he | hr
    · cases he; simp [tick, tickOne]
    · have := ih hr
      unfold tick
      cases hb : tickOne b with
      | none => exact this
      | some b' => exact List.mem_cons_of_mem _ this

/-- SAFETY: no number of ticks lifts a structural block. -/
theorem structural_survives_ticks (n : Nat) (t : List (Nat × Block)) (k left p : Nat)
    (h : (k, (left, some p)) ∈ t) : (k, (left, some p)) ∈ tickN n t := by
  induction n generalizing t with
  | zero => exact h
  | succ n ih => exact ih (tick t) (mem_tick_structural t k left p h)

/-- A structural block blocks exactly while its premise holds. -/
theorem structural_blocks_iff (left p premise : Nat) :
    blocksNow premise (left, some p) = true ↔ p = premise := by
  simp [blocksNow]

/-- SAFETY: a structural block still blocks its key after any ticks, while the
premise holds. -/
theorem structural_blocked_after_ticks (n : Nat) (t : List (Nat × Block)) (k left p : Nat)
    (h : (k, (left, some p)) ∈ t) : isBlocked (tickN n t) p k = true := by
  unfold isBlocked
  exact List.any_eq_true.mpr ⟨_, structural_survives_ticks n t k left p h, by simp [blocksNow]⟩

theorem tick_nil_of_transport_one (k : Nat) : tick [(k, (1, none))] = [] := by
  simp [tick, tickOne]

/-- LIVENESS: a lone transport block of `n + 1` ticks is gone after `n + 1`
ticks. -/
theorem transport_expires (n k : Nat) : tickN (n + 1) [(k, (n + 1, none))] = [] := by
  induction n with
  | zero => simp [tickN, tick, tickOne]
  | succ m ih =>
    have h1 : tick [(k, (m + 1 + 1, none))] = [(k, (m + 1, none))] := by
      simp [tick, tickOne]
    show tickN (m + 1) (tick [(k, (m + 1 + 1, none))]) = []
    rw [h1]; exact ih

/-! ## Witnesses -/

example : isBlocked [(7, (0, some 3))] 3 7 = true := by decide
example : isBlocked [(7, (0, some 3))] 4 7 = false := by decide
example : tickN 10 [(7, (10, none))] = [] := by decide
example : isBlocked (tickN 9 [(7, (10, none))]) 0 7 = true := by decide

end Formal.FailureRecovery

-- @concept: core, planner @property: monotonicity, safety, reachability
/-
Formal model of the doomed-goal memo's exponential-backoff re-probe schedule,
mirroring `src/artifactsmmo_cli/ai/doomed_memo.py` and the signature invalidation
key in `src/artifactsmmo_cli/ai/plannability_signature.py`.

CODE FACTS mirrored:
  * ttl(failures) = min(base << (failures-1), maxRetry).        [doomed_memo._ttl]
  * is_doomed: if the stored signature differs from the current state's
    signature => NOT doomed (new plannability, re-probe); else doomed iff
    `cycle - set_at < ttl(failures)`.                         [doomed_memo.is_doomed]
  * mark: a re-mark under the SAME signature increments the failure count
    (escalating the window); a new signature resets it to 1.     [doomed_memo.mark]

This COMPLEMENTS `TieredSelection.memo_skip_sound`, which proves the two-pass walk
is sound GIVEN an abstract `skip` predicate. Here we prove the CONCRETE `skip`
predicate's arithmetic: the window grows geometrically per consecutive failure, is
capped at `maxRetry`, and a signature change OR window expiry always re-enables the
probe — so a goal is retried geometrically less often but NEVER skipped forever.

Lean core only — no mathlib.
-/

namespace Formal.DoomedMemo

variable {σ : Type} [DecidableEq σ]

/-- Re-probe window for the `failures`-th consecutive failure: the uncapped
window `base * 2^(failures-1)` capped at `maxR`. Mirrors `DoomedMemo._ttl`. -/
def ttl (base maxR failures : Nat) : Nat := min (base <<< (failures - 1)) maxR

/-- The failure count after a `mark`: under the SAME signature as the previous
entry it increments (escalation); under a new signature (or no prior entry) it
resets to 1. Mirrors the `failures = prev[2]+1 if prev and prev[0]==sig else 1`
line of `DoomedMemo.mark`. -/
def markedFailures (prev : Option (σ × Nat)) (sig : σ) : Nat :=
  match prev with
  | some (s, f) => if s = sig then f + 1 else 1
  | none => 1

/-- Whether a goal recorded at `(sig0, setAt, failures)` is currently skipped,
evaluated at current `(sig, cycle)`. A differing signature => not doomed.
Mirrors `DoomedMemo.is_doomed` (the `entry is None` case is "not recorded" =>
not doomed, handled by the caller; here the entry is present). -/
def isDoomed (base maxR : Nat) (sig0 : σ) (setAt failures : Nat)
    (sig : σ) (cycle : Nat) : Bool :=
  if sig = sig0 then decide (cycle - setAt < ttl base maxR failures) else false

/-! ### ttl: base case, cap, geometric growth, monotonicity. -/

/-- **BASE.** The first failure's window is `min base maxR`. -/
theorem ttl_base (base maxR : Nat) : ttl base maxR 1 = min base maxR := by
  simp [ttl, Nat.shiftLeft_eq]

/-- **CAP.** The window never exceeds `maxR`. -/
theorem ttl_le_max (base maxR failures : Nat) : ttl base maxR failures ≤ maxR :=
  Nat.min_le_right _ _

/-- The uncapped window `base * 2^(failures-1)` DOUBLES per consecutive failure.
This is the geometric-backoff core: between failure `f` and `f+1` (for `f ≥ 1`)
the window exactly doubles. -/
theorem window_doubles (base f : Nat) (hf : 1 ≤ f) :
    base <<< ((f + 1) - 1) = 2 * (base <<< (f - 1)) := by
  obtain ⟨n, rfl⟩ := Nat.exists_eq_add_of_le hf
  have e1 : (1 + n + 1) - 1 = n + 1 := by omega
  have e2 : (1 + n) - 1 = n := by omega
  rw [e1, e2, Nat.shiftLeft_succ]

/-- **MONOTONE.** More consecutive failures never shrink the window. -/
theorem ttl_monotone (base maxR : Nat) {f1 f2 : Nat} (h : f1 ≤ f2) :
    ttl base maxR f1 ≤ ttl base maxR f2 := by
  have hsh : base <<< (f1 - 1) ≤ base <<< (f2 - 1) := by
    rw [Nat.shiftLeft_eq, Nat.shiftLeft_eq]
    exact Nat.mul_le_mul (Nat.le_refl base)
      (Nat.pow_le_pow_right (by decide) (Nat.sub_le_sub_right h 1))
  unfold ttl
  omega

/-! ### isDoomed: signature invalidation, window semantics, expiry (liveness). -/

/-- **SIGNATURE-INVALIDATES.** A current signature different from the recorded one
makes the goal NOT doomed — new plannability (a level changed) forces a re-probe.
Soundness lever: the memo never suppresses a goal whose preconditions moved. -/
theorem isDoomed_sig_change (base maxR : Nat) (sig0 : σ) (setAt failures : Nat)
    (sig : σ) (cycle : Nat) (h : sig ≠ sig0) :
    isDoomed base maxR sig0 setAt failures sig cycle = false := by
  simp [isDoomed, h]

/-- **WINDOW.** Under the same signature, doomed ⇔ still inside the ttl window. -/
theorem isDoomed_window (base maxR : Nat) (sig0 : σ) (setAt failures : Nat)
    (cycle : Nat) :
    isDoomed base maxR sig0 setAt failures sig0 cycle = true
      ↔ cycle - setAt < ttl base maxR failures := by
  simp [isDoomed]

/-- **EVENTUALLY-RETRIES (liveness).** Once the elapsed cycles reach the ttl
window, the goal is NOT doomed — it is always re-probed. With `ttl ≤ maxR`, the
window is finite, so no goal is suppressed forever. -/
theorem isDoomed_expires (base maxR : Nat) (sig0 : σ) (setAt failures : Nat)
    (sig : σ) (cycle : Nat) (h : ttl base maxR failures ≤ cycle - setAt) :
    isDoomed base maxR sig0 setAt failures sig cycle = false := by
  unfold isDoomed
  by_cases hs : sig = sig0
  · simp [hs, Nat.not_lt.mpr h]
  · simp [hs]

/-! ### mark: escalation vs. reset. -/

/-- **ESCALATES.** A re-mark under the SAME signature increments the failure
count; combined with `ttl_monotone`, the next window is ≥ the current one. -/
theorem markedFailures_same (s : σ) (f : Nat) :
    markedFailures (some (s, f)) s = f + 1 := by
  simp [markedFailures]

/-- **RESETS.** A mark under a NEW signature (or no prior entry) starts at 1. -/
theorem markedFailures_reset (s : σ) (f : Nat) (sig : σ) (h : s ≠ sig) :
    markedFailures (some (s, f)) sig = 1 ∧ markedFailures (none : Option (σ × Nat)) sig = 1 := by
  constructor
  · simp [markedFailures, h]
  · simp [markedFailures]

/-- Escalation grows the window: re-marking the same signature never shrinks the
re-probe window. Connects `markedFailures_same` to `ttl_monotone`. -/
theorem escalation_grows_window (base maxR : Nat) (s : σ) (f : Nat) :
    ttl base maxR f ≤ ttl base maxR (markedFailures (some (s, f)) s) := by
  rw [markedFailures_same]
  exact ttl_monotone base maxR (Nat.le_succ f)

/-! ### Non-vacuity witnesses (the production 20→40→80→160 schedule). -/

/-- The shipped schedule (base 20, cap 160): 20, 40, 80, 160, then capped. -/
example : ttl 20 160 1 = 20 := by decide
example : ttl 20 160 2 = 40 := by decide
example : ttl 20 160 3 = 80 := by decide
example : ttl 20 160 4 = 160 := by decide
example : ttl 20 160 5 = 160 := by decide
example : ttl 20 160 6 = 160 := by decide

/-- isDoomed is genuinely true inside the window and false past it. -/
example : isDoomed 20 160 (7 : Nat) 0 1 (7 : Nat) 10 = true := by decide
example : isDoomed 20 160 (7 : Nat) 0 1 (7 : Nat) 25 = false := by decide
example : isDoomed 20 160 (7 : Nat) 0 1 (9 : Nat) 10 = false := by decide

end Formal.DoomedMemo

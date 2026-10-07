-- @concept: tasks, value @property: safety, totality, dominance
/-
A task's worth (Phase 5-2c-iii-c-2 #5, `docs/PLAN_task_value.md`,
`src/artifactsmmo_cli/ai/task_worth_core.py`).

USER 2026-10-07: a task is worth working for its XP, for the gold a pending
purchase needs when the task is the faster gold source, or for drops a needed
craft uses — "part of the pareto frontier analysis central to the game's
progress loop". One verdict decides three things:

* keep or cancel a held task: a worthless one is cancelled when a coin is in
  the pocket and it is not met; with no coin it is worked to clear it;
* whether a draw is owed: some task the master can issue at this level is
  worthy;
* the order between task options: the reason sets are compared as a Pareto
  set, a strict superset dominating.

## The model

`Inputs` are the facts the Python core reads, abstracted to Bools and two gold
rates. A rate is `num / den` gold per cycle with `den > 0` in every reachable
input (Python passes a `Fraction`, whose denominator is positive); the
comparison is by cross-multiplication, so the model never divides.

`feasible` is false for a task the character cannot win and no gear or level
closes (`task_horizon` OUT_OF_REACH): such a task is worthless whatever its
reasons.
-/

namespace Formal.TaskWorth

structure Inputs where
  feasible    : Bool
  xpPositive  : Bool
  goldShort   : Bool
  taskNum     : Nat
  taskDen     : Nat
  otherNum    : Nat
  otherDen    : Nat
  dropAligned : Bool
deriving Repr, DecidableEq

/-- The reasons a task is worth working. -/
structure Worth where
  xp    : Bool
  gold  : Bool
  drops : Bool
deriving Repr, DecidableEq

/-- Task gold per cycle strictly beats the best other gold per cycle. -/
def goldFaster (i : Inputs) : Bool :=
  decide (i.otherNum * i.taskDen < i.taskNum * i.otherDen)

def worth (i : Inputs) : Worth :=
  if i.feasible then
    ⟨i.xpPositive, i.goldShort && goldFaster i, i.dropAligned⟩
  else
    ⟨false, false, false⟩

def Worth.any (w : Worth) : Bool := w.xp || w.gold || w.drops

/-- Cancel: worthless, a coin in the pocket, and not already met. -/
def cancelDue (w : Worth) (coin met : Bool) : Bool :=
  !w.any && coin && !met

/-- A draw is owed when some task in the master's pool is worthy. -/
def drawOwed (pool : List Worth) : Bool := pool.any Worth.any

/-- `a` dominates `b`: every reason of `b` is a reason of `a`, and `a` has one
`b` lacks. -/
def dominates (a b : Worth) : Bool :=
  (!b.xp || a.xp) && (!b.gold || a.gold) && (!b.drops || a.drops) &&
    ((a.xp && !b.xp) || (a.gold && !b.gold) || (a.drops && !b.drops))

/-! ## Theorems -/

theorem cancelDue_iff (w : Worth) (coin met : Bool) :
    cancelDue w coin met = true ↔ w.any = false ∧ coin = true ∧ met = false := by
  unfold cancelDue
  cases w.any <;> cases coin <;> cases met <;> simp

/-- A worthy task is never cancelled. -/
theorem worthy_never_cancelled (w : Worth) (coin met : Bool) (h : w.any = true) :
    cancelDue w coin met = false := by
  unfold cancelDue; simp [h]

/-- With no coin nothing is cancelled: the task is worked to clear it. -/
theorem no_coin_no_cancel (w : Worth) (met : Bool) : cancelDue w false met = false := by
  unfold cancelDue; simp

/-- An infeasible task is worthless. -/
theorem infeasible_worthless (i : Inputs) (h : i.feasible = false) :
    (worth i).any = false := by
  simp [worth, h, Worth.any]

/-- A feasible task whose kill pays XP is never cancelled. -/
theorem xp_task_kept (i : Inputs) (coin met : Bool)
    (hf : i.feasible = true) (hx : i.xpPositive = true) :
    cancelDue (worth i) coin met = false := by
  apply worthy_never_cancelled
  simp [worth, hf, hx, Worth.any]

/-- GOLD is a reason exactly when the task is feasible, gold is short, and the
task is the faster gold source. -/
theorem gold_iff (i : Inputs) :
    (worth i).gold = true ↔
      i.feasible = true ∧ i.goldShort = true ∧ i.otherNum * i.taskDen < i.taskNum * i.otherDen := by
  unfold worth goldFaster
  cases hf : i.feasible <;> cases hs : i.goldShort <;> simp

/-- Drops alone make a feasible task worthy (USER: "drops alone count"). -/
theorem drops_alone_worthy (i : Inputs) (hf : i.feasible = true) (hd : i.dropAligned = true) :
    (worth i).any = true := by
  simp [worth, hf, hd, Worth.any]

theorem drawOwed_iff (pool : List Worth) :
    drawOwed pool = true ↔ ∃ w ∈ pool, w.any = true := by
  simp [drawOwed, List.any_eq_true]

theorem dominates_irrefl (a : Worth) : dominates a a = false := by
  cases a with | mk x g d => cases x <;> cases g <;> cases d <;> decide

theorem dominates_trans (a b c : Worth) (hab : dominates a b = true) (hbc : dominates b c = true) :
    dominates a c = true := by
  cases a with | mk ax ag ad =>
  cases b with | mk bx bg bd =>
  cases c with | mk cx cg cd =>
  cases ax <;> cases ag <;> cases ad <;> cases bx <;> cases bg <;> cases bd <;>
    cases cx <;> cases cg <;> cases cd <;> simp_all [dominates]

/-- Gold plus drops beats drops alone (USER: "gold plus drops is better than
just drops"). -/
theorem gold_and_drops_dominate_drops :
    dominates ⟨false, true, true⟩ ⟨false, false, true⟩ = true := by decide

/-- A worthy task dominates a worthless one. -/
theorem worthy_dominates_worthless (a : Worth) (h : a.any = true) :
    dominates a ⟨false, false, false⟩ = true := by
  cases a with | mk x g d => cases x <;> cases g <;> cases d <;> simp_all [Worth.any, dominates]

/-! ## Satisfiability witnesses (no vacuous hypotheses) -/

example : cancelDue ⟨false, false, false⟩ true false = true := by decide
example : (worth ⟨true, false, true, 3, 1, 1, 1, false⟩).gold = true := by decide
example : drawOwed [⟨false, false, false⟩, ⟨false, false, true⟩] = true := by decide

/-! ## The draw (increment 3, USER 2026-10-07: "Rerolls ≤ completion coins")

A worthless draw is cancelled for one coin, so with `worthy` of `size` pool
tasks worth working the expected coins spent before a worthy draw is
`(size - worthy) / worthy`. A draw is due when that is at most the coins a
completion pays, cross-multiplied so the model never divides. -/

def drawDue (worthy size coinReward : Nat) : Bool :=
  decide (0 < worthy) && decide (size - worthy ≤ coinReward * worthy)

theorem drawDue_iff (worthy size coinReward : Nat) :
    drawDue worthy size coinReward = true ↔ 0 < worthy ∧ size - worthy ≤ coinReward * worthy := by
  simp [drawDue]

/-- A pool with no worthy task never owes a draw. -/
theorem drawDue_none (size coinReward : Nat) : drawDue 0 size coinReward = false := by
  simp [drawDue]

/-- More worthy tasks in the same pool never revoke a due draw. -/
theorem drawDue_mono (w w' size coinReward : Nat) (h : drawDue w size coinReward = true)
    (hw : w ≤ w') : drawDue w' size coinReward = true := by
  rw [drawDue_iff] at h ⊢
  refine ⟨Nat.lt_of_lt_of_le h.1 hw, ?_⟩
  calc size - w' ≤ size - w := Nat.sub_le_sub_left hw size
    _ ≤ coinReward * w := h.2
    _ ≤ coinReward * w' := Nat.mul_le_mul_left coinReward hw

/-- A due draw names a worthy task in the pool: it refines `drawOwed`. -/
theorem drawDue_refines_drawOwed (pool : List Worth) (r : Nat)
    (h : drawDue (pool.countP Worth.any) pool.length r = true) : drawOwed pool = true := by
  rw [drawDue_iff] at h
  rw [drawOwed_iff]
  have := List.countP_pos_iff.mp h.1
  simpa using this

example : drawDue 9 21 4 = true := by decide
example : drawDue 1 21 4 = false := by decide

end Formal.TaskWorth

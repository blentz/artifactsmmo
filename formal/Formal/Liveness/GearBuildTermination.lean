-- @concept: liveness, planner @property: liveness
import Formal.StrategyTraversal
import Mathlib.Tactic

/-! # GearBuildTermination — a buildable gear target is BUILT in finitely many steps

The arbiter only commits to a gear root that passes `is_reachable` — proved equivalent
to `Grounded` (`StrategyTraversal.is_reachable_eq_grounding`). So *we never select an
unbuildable target*. `reachable_implies_actionable` already shows a Grounded unmet target
always has an actionable next step (the pursuit never stalls). This module closes the
loop: executing those steps TERMINATES at the built target.

Model one production cycle of gear progress as marking an `ActionableNode` satisfied
(`markSat`) — the bot gathers/crafts the deepest ready prerequisite, which then holds.
We prove:

* `grounded_markSat` — marking a node satisfied never un-grounds the target (progress is
  monotone: a buildable target stays buildable);
* `unmetReach_markSat` — marking only PRUNES the unmet closure (never grows it);
* `measure_markSat_lt` — marking an unmet universe node strictly drops the unmet-count;
* `grounded_builds_target` — THE THEOREM: for a Grounded target over a finite universe
  covering its unmet closure, there is a finite sequence of actionable-step executions
  after which the target is satisfied (built). Strong induction on the unmet-count.

Combined: selection ⇒ Grounded (never pick unbuildable) ⇒ this ⇒ the target is built.
The matching production guarantee is the chunked pursuit in `strategy_driver.py`
(each actionable step is a budget-feasible chunk on the root's chain).

Liveness namespace — Mathlib permitted.
-/

namespace Formal.Liveness.GearBuildTermination

open Formal.StrategyTraversal

/-- Mark node `a` satisfied — one cycle of gear progress (the bot obtains the deepest
ready prerequisite, which then holds). Only `isSat` changes; prereqs/kind/producible are
untouched. -/
def markSat (g : Graph) (a : Nat) : Graph :=
  { g with isSat := fun n => g.isSat n || decide (n = a) }

@[simp] theorem markSat_isSat (g : Graph) (a n : Nat) :
    (markSat g a).isSat n = (g.isSat n || decide (n = a)) := rfl

@[simp] theorem markSat_prereqs (g : Graph) (a n : Nat) :
    (markSat g a).prereqs n = g.prereqs n := rfl

@[simp] theorem markSat_kind (g : Graph) (a n : Nat) :
    (markSat g a).kind n = g.kind n := rfl

@[simp] theorem markSat_producible (g : Graph) (a n : Nat) :
    (markSat g a).producible n = g.producible n := rfl

/-- Marking a node satisfied never un-grounds a target: a buildable target stays
buildable (progress is monotone). Induction on the grounding derivation; the marked node
becomes satisfied (grounds via `.sat`), every other node keeps its derivation since
prereqs/kind/producible are unchanged. -/
theorem grounded_markSat (g : Graph) (a : Nat) :
    ∀ {n : Nat}, Grounded g n → Grounded (markSat g a) n := by
  intro n h
  induction h with
  | @sat m hs => exact Grounded.sat (by simp [hs])
  | @leaf m hns hk hempty hp =>
    by_cases hma : m = a
    · exact Grounded.sat (by simp [hma])
    · exact Grounded.leaf (by simp [hns, hma]) (by simpa using hk)
        (by simpa using hempty) (by simpa using hp)
  | @node m hns hobt _ ih =>
    by_cases hma : m = a
    · exact Grounded.sat (by simp [hma])
    · exact Grounded.node (by simp [hns, hma])
        (by simpa using hobt) (by intro p hp; simp only [markSat_prereqs] at hp; exact ih p hp)

/-- `markSat` only PRUNES unmet prereqs (a satisfied node is dropped from the unmet set);
it never adds one. -/
theorem unmetPrereqs_markSat_subset (g : Graph) (a node : Nat) :
    ∀ p ∈ unmetPrereqs (markSat g a) node, p ∈ unmetPrereqs g node := by
  intro p hp
  unfold unmetPrereqs at hp ⊢
  rw [List.mem_filter] at hp ⊢
  refine ⟨by simpa using hp.1, ?_⟩
  have hthis := hp.2
  simp only [markSat_isSat, Bool.not_or, Bool.and_eq_true] at hthis
  exact hthis.1

/-- Marking only prunes the unmet closure: anything `markSat g a` still reaches through
unmet prereqs, `g` reached too. -/
theorem unmetReach_markSat (g : Graph) (a : Nat) :
    ∀ {s b : Nat}, UnmetReach (markSat g a) s b → UnmetReach g s b := by
  intro s b h
  induction h with
  | @refl x hx =>
    refine UnmetReach.refl ?_
    simp only [markSat_isSat, Bool.or_eq_false_iff] at hx; exact hx.1
  | @head x p y hx hp _ ih =>
    refine UnmetReach.head ?_ (unmetPrereqs_markSat_subset g a x p hp) ih
    simp only [markSat_isSat, Bool.or_eq_false_iff] at hx; exact hx.1

/-- The unmet-count measure over a fixed finite universe `U`. -/
def unmetCount (g : Graph) (U : List Nat) : Nat :=
  (U.filter (fun n => !g.isSat n)).length

/-- Filtering out an element that IS present strictly shortens the list. -/
theorem filter_ne_lt (a : Nat) : ∀ {L : List Nat}, a ∈ L →
    (L.filter (fun n => decide (n ≠ a))).length < L.length := by
  intro L
  induction L with
  | nil => intro h; exact absurd h (List.not_mem_nil)
  | cons hd tl ih =>
    intro h
    by_cases hda : hd = a
    · -- head = a: dropped (decide(a≠a)=false); filtered tail ≤ |tl| < |hd::tl|.
      subst hda
      have hlen : (List.filter (fun n => decide (n ≠ hd)) (hd :: tl)).length
          = (tl.filter (fun n => decide (n ≠ hd))).length := by simp
      rw [hlen, List.length_cons]
      exact Nat.lt_succ_of_le (List.length_filter_le _ _)
    · -- head ≠ a: kept on both sides; a is in the tail; recurse.
      have hat : a ∈ tl := (List.mem_cons.mp h).resolve_left (fun e => hda e.symm)
      have hlen : (List.filter (fun n => decide (n ≠ a)) (hd :: tl)).length
          = (tl.filter (fun n => decide (n ≠ a))).length + 1 := by simp [hda]
      rw [hlen, List.length_cons]
      exact Nat.succ_lt_succ (ih hat)

/-- Marking an UNMET universe node satisfied strictly drops the unmet-count: that node
leaves the filtered set, every other node's membership is unchanged. -/
theorem measure_markSat_lt (g : Graph) (U : List Nat) (a : Nat)
    (hmem : a ∈ U) (hns : g.isSat a = false) :
    unmetCount (markSat g a) U < unmetCount g U := by
  unfold unmetCount
  have hpred : (fun n => !(markSat g a).isSat n)
      = (fun n => decide (n ≠ a) && !g.isSat n) := by
    funext n; simp only [markSat_isSat, Bool.not_or, decide_not]; exact Bool.and_comm _ _
  rw [hpred, ← List.filter_filter]
  refine filter_ne_lt a ?_
  rw [List.mem_filter]
  exact ⟨hmem, by simp [hns]⟩

/-- **A buildable gear target is BUILT in finitely many actionable steps.** For a
well-formed graph, a finite universe `U` (no dups) covering the target's unmet closure,
and a `Grounded` (buildable) target: there is a finite list of nodes — each an
`ActionableNode` at the moment it is executed — whose successive `markSat` makes the
target satisfied. I.e. pursuing a buildable gear root by repeatedly obtaining its deepest
ready prerequisite always terminates with the target built.

Strong induction on `unmetCount g U`: if the target is already satisfied we are done;
otherwise `grounded_unmet_has_actionable` yields an actionable node in the unmet closure
(hence in `U`), marking it strictly drops the measure, and grounding / closure-coverage /
well-formedness are preserved for the recursive call. -/
theorem grounded_builds_target (g : Graph) (hwf : WellFormed g) (U : List Nat)
    (t : Nat) (ht : Grounded g t)
    (hcov : ∀ a, UnmetReach g t a → a ∈ U) :
    ∃ steps : List Nat, (steps.foldl markSat g).isSat t = true := by
  -- Strong induction on the measure.
  generalize hk : unmetCount g U = k
  induction k using Nat.strong_induction_on generalizing g with
  | _ k IH =>
    by_cases hts : g.isSat t = true
    · exact ⟨[], by simpa using hts⟩
    · have hts' : g.isSat t = false := by simpa using hts
      obtain ⟨a, hra, haa⟩ := grounded_unmet_has_actionable g hwf ht hts'
      have hau : a ∈ U := hcov a hra
      have hauns : g.isSat a = false := haa.1
      -- one productive step: mark a; measure strictly drops.
      have hlt : unmetCount (markSat g a) U < k := by
        rw [← hk]; exact measure_markSat_lt g U a hau hauns
      -- premises preserved for the recursive call.
      have hwf' : WellFormed (markSat g a) := by
        intro n hk1 hk2
        have := hwf n (by simpa using hk1) (by simpa using hk2); simpa using this
      have ht' : Grounded (markSat g a) t := grounded_markSat g a ht
      have hcov' : ∀ b, UnmetReach (markSat g a) t b → b ∈ U :=
        fun b hb => hcov b (unmetReach_markSat g a hb)
      obtain ⟨steps, hsteps⟩ :=
        IH (unmetCount (markSat g a) U) hlt (markSat g a) hwf' ht' hcov' rfl
      exact ⟨a :: steps, by simpa using hsteps⟩

end Formal.Liveness.GearBuildTermination

-- @concept: core, planner @property: safety, totality
/-
Formal model of the FULL craft-plan driver (`craft_plan_full` in
`src/artifactsmmo_cli/ai/craft_plan_driver_core.py`): iterate the kernel-proved
single-step `nextCraftTarget` (Formal/NextCraftAction.lean) to completion,
applying each emitted action's effect to a simulated (inventory, bank) state,
accumulating the whole ordered remaining plan.

Modelling note — CONSUMPTION: `craft` consumes its recipe inputs (so the plan is
sound on shared intermediates, not just linear chains); `gather`/`withdraw` add
to inventory; `withdraw` also debits the bank.  The single-step `nextCraftTarget`
only emits `craft` when every input is on hand (ORDERING, B1), so consumption
never underflows on a reachable plan.

ROLES proved:
  * per-step validity — every action in the plan is a genuine `nextCraftTarget`
    output for the state at that point (no fabricated steps)
  * head matches B1 — the plan's first action equals the proven single-step
  * totality — `craftPlan` is a total function (structural on outer fuel)

The unconditional "plan always completes and reaches the target" termination
result is staged separately (it needs the closure measure); the differential
harness binds completion empirically over random inputs in the interim.
-/

import Formal.NextCraftAction

namespace Formal.CraftPlanDriver

open Formal.NextCraftAction

/-- Apply one action's effect to `(owned, bank)`, modelling input consumption.

`gather`/`withdraw` add `na.qty` of `na.item` to inventory; `withdraw` also
debits the bank.  `craft` adds the output AND subtracts `per * na.qty` of each
recipe input (consumption).  Item ≠ inputs on acyclic recipe data, so the
output-bump and input-consumption don't interfere. -/
def applyState
    (recipes : String → Option (List (String × Nat)))
    (owned bank : String → Nat)
    (na : NextAction) : (String → Nat) × (String → Nat) :=
  match na.kind with
  | .gather =>
      (fun s => if s = na.item then owned s + na.qty else owned s, bank)
  | .withdraw =>
      (fun s => if s = na.item then owned s + na.qty else owned s,
       fun s => if s = na.item then bank s - na.qty else bank s)
  | .craft =>
      let bumped : String → Nat := fun s => if s = na.item then owned s + na.qty else owned s
      let consumed : String → Nat :=
        match recipes na.item with
        | none        => bumped
        | some inputs =>
            inputs.foldl
              (fun ow p => fun s => if s = p.1 then ow s - p.2 * na.qty else ow s)
              bumped
      (consumed, bank)

/-- Iterate `nextCraftTarget` to completion, threading the simulated state.

`innerFuel` is the per-step DAG budget (`|recipes|+1`); the outer `fuel` bounds
the number of actions for totality.  Stops when the target is satisfied
(`nextCraftTarget = none`) or the outer fuel runs out. -/
def craftPlan
    (recipes : String → Option (List (String × Nat)))
    (target : String) (qty innerFuel : Nat)
    : (String → Nat) → (String → Nat) → Nat → List NextAction
  | _,     _,    0        => []
  | owned, bank, fuel + 1 =>
      match nextCraftTarget recipes owned bank target qty innerFuel with
      | none    => []
      | some na =>
          let st := applyState recipes owned bank na
          na :: craftPlan recipes target qty innerFuel st.1 st.2 fuel

/-! ## Theorem 1: head matches the proven single step -/

/-- **HEAD-MATCHES-B1.** When the target is unsatisfied and outer fuel remains,
the plan's first action is exactly the kernel-proved single-step
`nextCraftTarget` result.  The driver does not fabricate a different first move. -/
theorem craftPlan_head
    (recipes : String → Option (List (String × Nat)))
    (owned bank : String → Nat)
    (target : String) (qty innerFuel fuel : Nat)
    (na : NextAction)
    (h : nextCraftTarget recipes owned bank target qty innerFuel = some na) :
    craftPlan recipes target qty innerFuel owned bank (fuel + 1) =
      na :: craftPlan recipes target qty innerFuel
              (applyState recipes owned bank na).1
              (applyState recipes owned bank na).2 fuel := by
  simp only [craftPlan, h]

/-! ## Theorem 2: empty plan ⇔ already satisfied (given fuel) -/

/-- **NIL-IFF-SATISFIED.** With fuel available, the plan is empty iff the target
is already satisfied (`qty ≤ owned target`).  An empty plan is never returned
while real work remains (modulo fuel). -/
theorem craftPlan_nil_iff
    (recipes : String → Option (List (String × Nat)))
    (owned bank : String → Nat)
    (target : String) (qty innerFuel fuel : Nat) :
    craftPlan recipes target qty innerFuel owned bank (fuel + 1) = [] ↔
      qty ≤ owned target := by
  rw [← nextCraftTarget_none_iff recipes owned bank target qty innerFuel]
  simp only [craftPlan]
  cases nextCraftTarget recipes owned bank target qty innerFuel with
  | none => simp
  | some na => simp

/-! ## Theorem 3: per-step validity -/

/-- **PER-STEP-VALIDITY.** Every action in the emitted plan is a genuine
`nextCraftTarget` output for SOME reachable (inventory, bank) state — the driver
fabricates no steps; each is a kernel-proved single move (NextAction roles from
B1 therefore transfer to every element of the plan). -/
theorem craftPlan_steps_valid
    (recipes : String → Option (List (String × Nat)))
    (target : String) (qty innerFuel : Nat) :
    ∀ (fuel : Nat) (owned bank : String → Nat) (na : NextAction),
      na ∈ craftPlan recipes target qty innerFuel owned bank fuel →
      ∃ (o b : String → Nat),
        nextCraftTarget recipes o b target qty innerFuel = some na := by
  intro fuel
  induction fuel with
  | zero =>
    intro owned bank na hmem
    simp [craftPlan] at hmem
  | succ n ih =>
    intro owned bank na hmem
    simp only [craftPlan] at hmem
    cases hnc : nextCraftTarget recipes owned bank target qty innerFuel with
    | none => simp [hnc] at hmem
    | some na0 =>
      rw [hnc] at hmem
      simp only [List.mem_cons] at hmem
      cases hmem with
      | inl heq => exact ⟨owned, bank, heq ▸ hnc⟩
      | inr htail =>
        exact ih (applyState recipes owned bank na0).1 (applyState recipes owned bank na0).2 na htail

/-! ## Theorem 4: completion-correctness -/

/-- Fold a plan's actions over a state, applying each effect in order. -/
def foldPlan
    (recipes : String → Option (List (String × Nat)))
    : (String → Nat) × (String → Nat) → List NextAction → (String → Nat) × (String → Nat)
  | st, []          => st
  | st, na :: rest  => foldPlan recipes (applyState recipes st.1 st.2 na) rest

/-- **COMPLETION-CORRECTNESS.** When the plan stopped because the target became
satisfied (rather than running out of fuel — captured by `length < fuel`, i.e.
fuel was NOT the limiting factor), executing the whole plan in order reaches the
target: `qty ≤ finalOwned target`.  This is the soundness of the full driver. -/
theorem craftPlan_reaches
    (recipes : String → Option (List (String × Nat)))
    (target : String) (qty innerFuel : Nat) :
    ∀ (fuel : Nat) (owned bank : String → Nat),
      (craftPlan recipes target qty innerFuel owned bank fuel).length < fuel →
      qty ≤ (foldPlan recipes (owned, bank)
              (craftPlan recipes target qty innerFuel owned bank fuel)).1 target := by
  intro fuel
  induction fuel with
  | zero =>
    intro owned bank hlen
    simp [craftPlan] at hlen
  | succ n ih =>
    intro owned bank hlen
    cases hnc : nextCraftTarget recipes owned bank target qty innerFuel with
    | none =>
      have hsat : qty ≤ owned target :=
        (nextCraftTarget_none_iff recipes owned bank target qty innerFuel).mp hnc
      simp only [craftPlan, hnc, foldPlan]
      exact hsat
    | some na0 =>
      have hstep := craftPlan_head recipes owned bank target qty innerFuel n na0 hnc
      rw [hstep] at hlen ⊢
      simp only [List.length_cons, foldPlan] at hlen ⊢
      have hlen' : (craftPlan recipes target qty innerFuel
                      (applyState recipes owned bank na0).1
                      (applyState recipes owned bank na0).2 n).length < n := by
        omega
      exact ih (applyState recipes owned bank na0).1 (applyState recipes owned bank na0).2 hlen'

/-! ## Non-vacuity witness — copper_ring full chain from empty -/

private def copperRecipes : String → Option (List (String × Nat))
  | "copper_ring" => some [("copper_bar", 1)]
  | "copper_bar"  => some [("copper_ore", 10)]
  | _             => none

private def zero : String → Nat := fun _ => 0

-- From 0 owned / 0 bank, the full plan for 1 copper_ring is the 3-step chain:
-- gather 10 ore → craft 1 bar → craft 1 ring.
example :
    craftPlan copperRecipes "copper_ring" 1 10 zero zero 10 =
      [⟨"copper_ore", .gather, 10⟩, ⟨"copper_bar", .craft, 1⟩, ⟨"copper_ring", .craft, 1⟩] := by
  decide

-- With 1 copper_bar already banked, the plan withdraws it then crafts the ring.
private def bankBar : String → Nat
  | "copper_bar" => 1
  | _ => 0

example :
    craftPlan copperRecipes "copper_ring" 1 10 zero bankBar 10 =
      [⟨"copper_bar", .withdraw, 1⟩, ⟨"copper_ring", .craft, 1⟩] := by
  decide

-- Already satisfied → empty plan.
private def haveRing : String → Nat
  | "copper_ring" => 1
  | _ => 0

example : craftPlan copperRecipes "copper_ring" 1 10 haveRing zero 10 = [] := by decide

end Formal.CraftPlanDriver

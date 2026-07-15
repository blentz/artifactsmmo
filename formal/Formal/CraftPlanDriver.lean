-- @concept: core, planner @property: safety, totality
/-
Formal model of the FULL craft-plan driver (`craft_plan_full` in
`src/artifactsmmo_cli/ai/craft_plan_driver_core.py`): iterate the kernel-proved
single-step `nextCraftTarget` (Formal/NextCraftAction.lean) to completion,
applying each emitted action's effect to a simulated (inventory, bank) state,
accumulating the whole ordered remaining plan.

Modelling note — the SIX-source obtain model (`ai/obtain_sources.Source`).
`applyState` applies each kind's effect:
  * gather / buy / drop — add `na.qty` of `na.item` to inventory (BUY's gold and
    DROP's drop-rate variance are deliberate abstractions, per the module
    docstring / `feedback_combat_xp_projection_is_abstract`);
  * withdraw — add to inventory AND debit the bank;
  * craft — add the output AND subtract `per * na.qty` of each recipe input
    (consumption; sound on shared intermediates, not just linear chains);
  * recycle — add the output AND debit the SOURCE item `na.code` by
    `⌈na.qty / yieldPer⌉` (mirrors `RecycleAction.apply`). `yieldPer` is looked
    up from the matching recycle Source (as Python does), not carried on the
    action. WHAT GUARDS this exact debit — against a forgotten one, a
    sign-flip, or a truncating `/` swapped in for the ceil — is NOT
    `craftPlan_reaches` (it is structurally blind to it; see the
    completion-correctness note below). It is the ⌈·⌉-pinning `decide`
    witnesses at the foot of this file (which fix the post-fold SOURCE-item
    count to the ceil value, distinct from the floor value at a non-multiple)
    together with the craft-plan differential (whose live-bound recycle revisit
    re-emits a DIFFERENT plan when the debit is wrong).

The single-step `nextCraftTarget` only emits `craft` when every input is on hand
(ORDERING, proved in NextCraftAction), so consumption never underflows on a
reachable plan; the RECYCLE emission is capped at the source's live stock
(`stepFor`), so the recycle debit never over-draws either.

ROLES proved:
  * per-step validity — every action in the plan is a genuine `nextCraftTarget`
    output for the state at that point (no fabricated steps)
  * head matches B1 — the plan's first action equals the proven single-step
  * empty ⇔ satisfied — an empty plan is returned iff the target is met
  * completion-correctness — executing a COMPLETE plan (fuel not the limit)
    reaches the target

The theorems are re-proved over the WIDENED six-source model (not restricted
back to three kinds): `applyState` threads `sources` and the recycle debit, and
`craftPlan` / `foldPlan` apply the SAME widened `applyState`, so the completion
result holds for the recycle arm too.
-/

import Formal.NextCraftAction

namespace Formal.CraftPlanDriver

open Formal.NextCraftAction

/-- Apply one action's effect to `(owned, bank)`, modelling consumption over the
six-source obtain model. `sources` is only consulted for a `recycle` action (to
recover the consumed source item's `yieldPer`, as Python's `_apply_state` does);
it is ignored for every other kind. -/
def applyState
    (recipes : String → Option (List (String × Nat)))
    (sources : String → List Source)
    (owned bank : String → Nat)
    (na : NextAction) : (String → Nat) × (String → Nat) :=
  match na.kind with
  | .gather | .buy | .drop =>
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
  | .recycle =>
      -- add the target, debit the SOURCE item `na.code` by ⌈qty / yieldPer⌉.
      let bumped : String → Nat := fun s => if s = na.item then owned s + na.qty else owned s
      let yieldPer : Nat :=
        match (sources na.item).find?
            (fun s => decide (s.kind = Kind.recycle) && s.code == na.code) with
        | some s => s.yieldPer
        | none   => 1   -- unreachable by construction (planner names a real source)
      (fun s => if s = na.code then bumped s - ceilDiv na.qty yieldPer else bumped s, bank)

/-- Iterate `nextCraftTarget` to completion, threading the simulated state.

`innerFuel` is the per-step DAG budget (`|recipes|+1`); the outer `fuel` bounds
the number of actions for totality. Stops when the target is satisfied
(`nextCraftTarget = none`) or the outer fuel runs out. -/
def craftPlan
    (recipes : String → Option (List (String × Nat)))
    (sources : String → List Source)
    (target : String) (qty innerFuel : Nat)
    : (String → Nat) → (String → Nat) → Nat → List NextAction
  | _,     _,    0        => []
  | owned, bank, fuel + 1 =>
      match nextCraftTarget recipes sources owned bank target qty innerFuel with
      | none    => []
      | some na =>
          let st := applyState recipes sources owned bank na
          na :: craftPlan recipes sources target qty innerFuel st.1 st.2 fuel

/-! ## Theorem 1: head matches the proven single step -/

/-- **HEAD-MATCHES-B1.** When the target is unsatisfied and outer fuel remains,
the plan's first action is exactly the kernel-proved single-step
`nextCraftTarget` result. -/
theorem craftPlan_head
    (recipes : String → Option (List (String × Nat)))
    (sources : String → List Source)
    (owned bank : String → Nat)
    (target : String) (qty innerFuel fuel : Nat)
    (na : NextAction)
    (h : nextCraftTarget recipes sources owned bank target qty innerFuel = some na) :
    craftPlan recipes sources target qty innerFuel owned bank (fuel + 1) =
      na :: craftPlan recipes sources target qty innerFuel
              (applyState recipes sources owned bank na).1
              (applyState recipes sources owned bank na).2 fuel := by
  simp only [craftPlan, h]

/-! ## Theorem 2: empty plan ⇔ already satisfied (given fuel) -/

/-- **NIL-IFF-SATISFIED.** With fuel available, the plan is empty iff the target
is already satisfied (`qty ≤ owned target`). -/
theorem craftPlan_nil_iff
    (recipes : String → Option (List (String × Nat)))
    (sources : String → List Source)
    (owned bank : String → Nat)
    (target : String) (qty innerFuel fuel : Nat) :
    craftPlan recipes sources target qty innerFuel owned bank (fuel + 1) = [] ↔
      qty ≤ owned target := by
  rw [← nextCraftTarget_none_iff recipes sources owned bank target qty innerFuel]
  simp only [craftPlan]
  cases nextCraftTarget recipes sources owned bank target qty innerFuel with
  | none => simp
  | some na => simp

/-! ## Theorem 3: per-step validity -/

/-- **PER-STEP-VALIDITY.** Every action in the emitted plan is a genuine
`nextCraftTarget` output for SOME reachable (inventory, bank) state — the driver
fabricates no steps. -/
theorem craftPlan_steps_valid
    (recipes : String → Option (List (String × Nat)))
    (sources : String → List Source)
    (target : String) (qty innerFuel : Nat) :
    ∀ (fuel : Nat) (owned bank : String → Nat) (na : NextAction),
      na ∈ craftPlan recipes sources target qty innerFuel owned bank fuel →
      ∃ (o b : String → Nat),
        nextCraftTarget recipes sources o b target qty innerFuel = some na := by
  intro fuel
  induction fuel with
  | zero =>
    intro owned bank na hmem
    simp [craftPlan] at hmem
  | succ n ih =>
    intro owned bank na hmem
    simp only [craftPlan] at hmem
    cases hnc : nextCraftTarget recipes sources owned bank target qty innerFuel with
    | none => simp [hnc] at hmem
    | some na0 =>
      rw [hnc] at hmem
      simp only [List.mem_cons] at hmem
      cases hmem with
      | inl heq => exact ⟨owned, bank, heq ▸ hnc⟩
      | inr htail =>
        exact ih (applyState recipes sources owned bank na0).1
                 (applyState recipes sources owned bank na0).2 na htail

/-! ## Theorem 4: completion-correctness -/

/-- Fold a plan's actions over a state, applying each effect in order. -/
def foldPlan
    (recipes : String → Option (List (String × Nat)))
    (sources : String → List Source)
    : (String → Nat) × (String → Nat) → List NextAction → (String → Nat) × (String → Nat)
  | st, []          => st
  | st, na :: rest  => foldPlan recipes sources (applyState recipes sources st.1 st.2 na) rest

/-- **COMPLETION-CORRECTNESS.** When the plan stopped because the target became
satisfied (rather than running out of fuel — captured by `length < fuel`),
executing the whole plan in order reaches the target: `qty ≤ finalOwned target`.
This is the soundness of the full driver over the widened six-source model.

SCOPE (do not overclaim): this asserts satisfaction of the TARGET item only.
The recycle debit lands on the surplus SOURCE item (`na.code`, ALWAYS ≠ target),
so `craftPlan_reaches` is structurally BLIND to it — it holds for any
`applyState` whatsoever, including one that forgot or sign-flipped the debit (a
mixed-recovery plan would just emit a second recycle instead of a gather and
still reach `qty`). The exact ⌈·⌉ debit is pinned by the source-count `decide`
witnesses below + the differential, NOT by this theorem. -/
theorem craftPlan_reaches
    (recipes : String → Option (List (String × Nat)))
    (sources : String → List Source)
    (target : String) (qty innerFuel : Nat) :
    ∀ (fuel : Nat) (owned bank : String → Nat),
      (craftPlan recipes sources target qty innerFuel owned bank fuel).length < fuel →
      qty ≤ (foldPlan recipes sources (owned, bank)
              (craftPlan recipes sources target qty innerFuel owned bank fuel)).1 target := by
  intro fuel
  induction fuel with
  | zero =>
    intro owned bank hlen
    simp [craftPlan] at hlen
  | succ n ih =>
    intro owned bank hlen
    cases hnc : nextCraftTarget recipes sources owned bank target qty innerFuel with
    | none =>
      have hsat : qty ≤ owned target :=
        (nextCraftTarget_none_iff recipes sources owned bank target qty innerFuel).mp hnc
      simp only [craftPlan, hnc, foldPlan]
      exact hsat
    | some na0 =>
      have hstep := craftPlan_head recipes sources owned bank target qty innerFuel n na0 hnc
      rw [hstep] at hlen ⊢
      simp only [List.length_cons, foldPlan] at hlen ⊢
      have hlen' : (craftPlan recipes sources target qty innerFuel
                      (applyState recipes sources owned bank na0).1
                      (applyState recipes sources owned bank na0).2 n).length < n := by
        omega
      exact ih (applyState recipes sources owned bank na0).1
               (applyState recipes sources owned bank na0).2 hlen'

/-! ## Non-vacuity witnesses -/

private def copperRecipes : String → Option (List (String × Nat))
  | "copper_ring" => some [("copper_bar", 1)]
  | "copper_bar"  => some [("copper_ore", 10)]
  | _             => none

private def noSources : String → List Source := fun _ => []
private def zero : String → Nat := fun _ => 0

-- From 0 owned / 0 bank, the full plan for 1 copper_ring is the 3-step chain:
-- gather 10 ore → craft 1 bar → craft 1 ring.
example :
    craftPlan copperRecipes noSources "copper_ring" 1 10 zero zero 10 =
      [⟨"copper_ore", .gather, 10, ""⟩, ⟨"copper_bar", .craft, 1, ""⟩,
       ⟨"copper_ring", .craft, 1, ""⟩] := by decide

-- With 1 copper_bar already banked, the plan withdraws it then crafts the ring.
private def bankBar : String → Nat
  | "copper_bar" => 1
  | _ => 0

example :
    craftPlan copperRecipes noSources "copper_ring" 1 10 zero bankBar 10 =
      [⟨"copper_bar", .withdraw, 1, ""⟩, ⟨"copper_ring", .craft, 1, ""⟩] := by decide

-- Already satisfied → empty plan.
private def haveRing : String → Nat
  | "copper_ring" => 1
  | _ => 0

example : craftPlan copperRecipes noSources "copper_ring" 1 10 haveRing zero 10 = [] := by decide

/-! ### RECYCLE non-vacuity — the widened arm genuinely fires and reaches. -/

-- A recycle source for copper_bar: destroy `copper_dagger`, yield 1 per copy,
-- capacity 5. With 5 daggers owned, the plan for 1 ring recycles a bar (qty 1,
-- debiting 1 dagger via ⌈1/1⌉), then crafts the ring.
private def recycleBarSources : String → List Source
  | "copper_bar" => [⟨.recycle, "copper_dagger", 1, 5⟩]
  | _            => []

private def owned5dagger : String → Nat
  | "copper_dagger" => 5
  | _ => 0

example :
    craftPlan copperRecipes recycleBarSources "copper_ring" 1 10 owned5dagger zero 10 =
      [⟨"copper_bar", .recycle, 1, "copper_dagger"⟩, ⟨"copper_ring", .craft, 1, ""⟩] := by decide

-- COMPLETION-CORRECTNESS non-vacuity on the RECYCLE plan: executed, it reaches
-- the target (1 copper_ring owned), and the source debit brought daggers to 4.
example :
    1 ≤ (foldPlan copperRecipes recycleBarSources (owned5dagger, zero)
          (craftPlan copperRecipes recycleBarSources "copper_ring" 1 10 owned5dagger zero 10)).1
        "copper_ring" := by decide

example :
    (foldPlan copperRecipes recycleBarSources (owned5dagger, zero)
      (craftPlan copperRecipes recycleBarSources "copper_ring" 1 10 owned5dagger zero 10)).1
      "copper_dagger" = 4 := by decide

/-! ### CEIL-PINNING witness (Finding 2) — ⌈·⌉ debit, NOT a truncating ⌊·⌋.

The recycle-debit witnesses above all use `yieldPer = 1`, where `⌈q/1⌉ = ⌊q/1⌋`,
so they cannot tell ceil from floor. Here `yieldPer = 2` and the recycle emits
`qty = 3` — a NON-MULTIPLE of 2 — so the SOURCE debit is `⌈3/2⌉ = 2` (bringing
`copper_dagger` from 2 to 0), whereas a truncating `⌊3/2⌋ = 1` would leave 1.
The `= 0` post-fold witness therefore HOLDS under `ceilDiv` and FAILS under a
floor debit — the model-level pin the differential/`decide` layer needs. -/

-- yield 2, capacity 8; 2 daggers owned ⇒ live bound 2*2 = 4. For 3 rings the
-- copper_bar deficit is 3, so the recycle emits min(3, 8, 4) = 3 (non-multiple).
private def recycleY2Sources : String → List Source
  | "copper_bar" => [⟨.recycle, "copper_dagger", 2, 8⟩]
  | _            => []

private def owned2dagger : String → Nat
  | "copper_dagger" => 2
  | _ => 0

-- The plan itself is ceil/floor-agnostic (step qtys come from `sourceQty`, not
-- the debit): recycle 3 bars, then craft 3 rings.
example :
    craftPlan copperRecipes recycleY2Sources "copper_ring" 3 10 owned2dagger zero 20 =
      [⟨"copper_bar", .recycle, 3, "copper_dagger"⟩, ⟨"copper_ring", .craft, 3, ""⟩] := by decide

-- THE PIN: executed, the source item is debited by ⌈3/2⌉ = 2 → daggers reach 0.
-- Under a truncating ⌊3/2⌋ = 1 this would be 1, so this witness fails on floor.
example :
    (foldPlan copperRecipes recycleY2Sources (owned2dagger, zero)
      (craftPlan copperRecipes recycleY2Sources "copper_ring" 3 10 owned2dagger zero 20)).1
      "copper_dagger" = 0 := by decide

-- Completion-correctness still holds on this plan (reaches 3 rings).
example :
    3 ≤ (foldPlan copperRecipes recycleY2Sources (owned2dagger, zero)
          (craftPlan copperRecipes recycleY2Sources "copper_ring" 3 10 owned2dagger zero 20)).1
        "copper_ring" := by decide

end Formal.CraftPlanDriver

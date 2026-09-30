-- formal/Formal/CommittedLoop.lean
-- @concept: core, planner @property: termination, sufficiency
/-
THE COMMITTED LOOP (Phase 2d-L1c of docs/PLAN_decision_architecture_redesign.md).

Re-walking after every leg does not converge: a leg that shrinks a deficit can
make an earlier route usable that spends a scarce unit the plan needed, and the
re-walk declines a goal the plan would have reached (found by random search,
recorded in the plan). So the bot COMMITS to the walk's witness
(`DecomposeWitness.plan`) and the plan cache follows it leg by leg.

The one place reality departs from the witness's execution model is yield: a
gather or a monster drop delivers its planned amount only on average. The
cache therefore REPEATS such a leg until the bag holds the amount the plan
counted on (`PlanCache.step_target`, `FightAction.drop_target`). Here a
STOCHASTIC leg is an act whose route takes no inputs; it runs as a list of
ticks, each crediting what it delivered (possibly nothing), and completes once
the ticks add up to its amount. The adapter's gather and drop routes yield one
per application, so the cache's target (the gather's quantity, the fight's
drop units) is exactly that amount. Every other leg executes as in
`DecomposeWitness.execStep`.

Headline: from the real bag, when the walk says `q` of `i` can be had, the
committed loop delivers it under ANY tick schedule in which each stochastic
leg's ticks add up to its amount (the fairness hypothesis: a repeated gather or
fight eventually delivers; `schedule_exists` shows it is satisfiable). The loop
runs one tick per stochastic delivery and one step per other leg, so it ends
after exactly the schedule's ticks.
-/
import Formal.DecomposeWitness

namespace Formal.CommittedLoop

open Formal.Decompose Formal.DecomposeWitness

/-- A leg whose route takes no inputs: a gather or a fight, repeated until it
delivers. -/
def stochastic (g : Graph) : Step → Bool
  | .act i k _ _ =>
    match (g.routes i)[k]? with
    | some r => r.inputs.isEmpty
    | none => false
  | .openGate _ _ _ => false

/-- One leg against the world, its deliveries given as ticks. A stochastic leg
passes the same checks as `execStep`, and completes when its ticks add up to its
amount; it spends its planned amount of the route's capacity and credits
whatever the ticks delivered. Any other leg is `execStep`. -/
def execLeg (g : Graph) (w : World) (a : Step) (ticks : List Nat) : Option World :=
  match a with
  | .act i k c n =>
    if stochastic g a then
      match (g.routes i)[k]? with
      | none => none
      | some r =>
        if r.gates.all (fun gt => w.opened.contains (i, k, gt)) &&
            decide (w.st.used i k + c ≤ r.cap) && decide (runs c r.yieldPer ≤ n) &&
            decide (c ≤ ticks.sum) then
          some { w with st := { w.st.use i k c with
            bag := fun j => if j = i then w.st.bag j + ticks.sum else w.st.bag j } }
        else none
    else execStep g w a
  | .openGate _ _ _ => execStep g w a

/-- The committed loop: each leg with its ticks (ticks are ignored for a
deterministic leg). -/
def run (g : Graph) : List Step → List (List Nat) → World → Option World
  | [], _, w => some w
  | a :: l, ticks :: sched, w =>
    match execLeg g w a ticks with
    | none => none
    | some w' => run g l sched w'
  | _ :: _, [], _ => none

/-- A tick schedule is FAIR for a plan when it has a tick list per leg and each
stochastic leg's ticks add up to its amount. -/
def Fair (g : Graph) : List Step → List (List Nat) → Prop
  | [], _ => True
  | a :: l, ticks :: sched =>
    (∀ i k c n, a = .act i k c n → stochastic g a = true → c ≤ ticks.sum) ∧ Fair g l sched
  | _ :: _, [] => False

/-! ### A world at least as full runs at least as far -/

/-- `w` dominates `v`: at least the bag, at most the capacity spent, at least
the gates opened. -/
def Dom (w v : World) : Prop :=
  (∀ j, v.st.bag j ≤ w.st.bag j) ∧ (∀ j k, w.st.used j k ≤ v.st.used j k) ∧
    (∀ x ∈ v.opened, x ∈ w.opened)

theorem consume_dom (w v : St) (hb : ∀ j, v.bag j ≤ w.bag j) :
    ∀ (ps : List (Nat × Nat)) (n : Nat) (v' : St), consume v ps n = some v' →
      ∃ w', consume w ps n = some w' ∧ (∀ j, v'.bag j ≤ w'.bag j) ∧ w'.used = w.used ∧ v'.used = v.used := by
  intro ps
  induction ps generalizing w v with
  | nil =>
    intro n v' h
    simp only [consume, Option.some.injEq] at h
    subst h
    exact ⟨w, rfl, hb, rfl, rfl⟩
  | cons p ps ih =>
    intro n v' h
    simp only [consume] at h
    split at h
    · rename_i hp
      have hp' : n * p.2 ≤ w.bag p.1 := Nat.le_trans hp (hb p.1)
      simp only [consume, hp', if_true]
      obtain ⟨w', hw', hb', hu', hv'⟩ := ih (w.reserve p.1 (n * p.2)) (v.reserve p.1 (n * p.2))
        (fun j => by simp only [St.reserve]; split <;> have := hb j <;> omega) n v' h
      exact ⟨w', hw', hb', hu', hv'⟩
    · simp at h

theorem execStep_dom (g : Graph) (w v v' : World) (a : Step) (hd : Dom w v)
    (h : execStep g v a = some v') : ∃ w', execStep g w a = some w' ∧ Dom w' v' := by
  obtain ⟨hb, hu, ho⟩ := hd
  cases a with
  | openGate i k gt =>
    simp only [execStep, Option.some.injEq] at h ⊢
    subst h
    refine ⟨_, rfl, hb, hu, fun x hx => ?_⟩
    rcases List.mem_cons.mp hx with rfl | hx
    · exact List.mem_cons_self
    · exact List.mem_cons_of_mem _ (ho x hx)
  | act i k c n =>
    simp only [execStep] at h ⊢
    cases hr : (g.routes i)[k]? with
    | none => simp [hr] at h
    | some r =>
      simp only [hr] at h ⊢
      split at h
      · rename_i hok
        simp only [Bool.and_eq_true, List.all_eq_true, List.contains_iff_mem, decide_eq_true_eq] at hok
        obtain ⟨⟨hg, hcap⟩, hrun⟩ := hok
        obtain ⟨s', hcons, rfl⟩ := Option.map_eq_some_iff.mp h
        obtain ⟨w', hw', hb', hu', hv'⟩ := consume_dom w.st v.st hb r.inputs n s' hcons
        have hok' : (r.gates.all (fun gt => w.opened.contains (i, k, gt)) &&
            decide (w.st.used i k + c ≤ r.cap) && decide (runs c r.yieldPer ≤ n)) = true := by
          simp only [Bool.and_eq_true, List.all_eq_true, List.contains_iff_mem, decide_eq_true_eq]
          exact ⟨⟨fun gt hgt => ho _ (hg gt hgt), by have := hu i k; omega⟩, hrun⟩
        rw [if_pos hok', hw']
        refine ⟨_, rfl, fun j => ?_, fun j l => ?_, ho⟩
        · simp only [credit]; split <;> have := hb' j <;> omega
        · simp only [credit, St.use, hu', hv']; split <;> have := hu j l <;> omega
      · simp at h

theorem execAll_dom (g : Graph) :
    ∀ (l : List Step) (w v v' : World), Dom w v → execAll g l v = some v' →
      ∃ w', execAll g l w = some w' ∧ Dom w' v' := by
  intro l
  induction l with
  | nil => intro w v v' hd h; simp only [execAll, Option.some.injEq] at h; subst h; exact ⟨w, rfl, hd⟩
  | cons a l ih =>
    intro w v v' hd h
    simp only [execAll] at h ⊢
    cases hv : execStep g v a with
    | none => simp [hv] at h
    | some v1 =>
      simp only [hv] at h
      obtain ⟨w1, hw1, hd1⟩ := execStep_dom g w v v1 a hd hv
      rw [hw1]
      exact ih w1 v1 v' hd1 h

/-- A fair leg delivers at least what `execStep` would: the loop's world
dominates the witness's. -/
theorem execLeg_dom (g : Graph) (w v v' : World) (a : Step) (ticks : List Nat) (hd : Dom w v)
    (hfair : ∀ i k c n, a = .act i k c n → stochastic g a = true → c ≤ ticks.sum)
    (h : execStep g v a = some v') : ∃ w', execLeg g w a ticks = some w' ∧ Dom w' v' := by
  cases a with
  | openGate i k gt => exact execStep_dom g w v v' _ hd h
  | act i k c n =>
    by_cases hs : stochastic g (.act i k c n) = true
    · have hsum := hfair i k c n rfl hs
      obtain ⟨hb, hu, ho⟩ := hd
      simp only [stochastic] at hs
      cases hr : (g.routes i)[k]? with
      | none => simp [hr] at hs
      | some r =>
        rw [hr] at hs
        have hnil : r.inputs = [] := List.isEmpty_iff.mp hs
        simp only [execStep, hr] at h
        split at h
        · rename_i hok
          simp only [Bool.and_eq_true, List.all_eq_true, List.contains_iff_mem, decide_eq_true_eq] at hok
          obtain ⟨⟨hg, hcap⟩, hrun⟩ := hok
          obtain ⟨s', hcons, rfl⟩ := Option.map_eq_some_iff.mp h
          rw [hnil] at hcons
          simp only [consume, Option.some.injEq] at hcons
          subst hcons
          have hs' : stochastic g (.act i k c n) = true := by simp [stochastic, hr, hnil]
          have hok' : (r.gates.all (fun gt => w.opened.contains (i, k, gt)) &&
              decide (w.st.used i k + c ≤ r.cap) && decide (runs c r.yieldPer ≤ n) &&
              decide (c ≤ ticks.sum)) = true := by
            simp only [Bool.and_eq_true, List.all_eq_true, List.contains_iff_mem, decide_eq_true_eq]
            exact ⟨⟨⟨fun gt hgt => ho _ (hg gt hgt), by have := hu i k; omega⟩, hrun⟩, hsum⟩
          simp only [execLeg, hs', if_true, hr, hok']
          refine ⟨_, rfl, fun j => ?_, fun j l => ?_, ho⟩
          · simp only [credit]; split <;> have := hb j <;> omega
          · simp only [credit, St.use]; split <;> have := hu j l <;> omega
        · simp at h
    · have hf : stochastic g (.act i k c n) = false := by simpa using hs
      simp only [execLeg, hf, Bool.false_eq_true, if_false]
      exact execStep_dom g w v v' _ hd h

theorem run_dom (g : Graph) :
    ∀ (l : List Step) (sched : List (List Nat)) (w v v' : World), Fair g l sched → Dom w v →
      execAll g l v = some v' → ∃ w', run g l sched w = some w' ∧ Dom w' v' := by
  intro l
  induction l with
  | nil => intro sched w v v' _ hd h; simp only [execAll, Option.some.injEq] at h; subst h; exact ⟨w, rfl, hd⟩
  | cons a l ih =>
    intro sched w v v' hfair hd h
    cases sched with
    | nil => simp [Fair] at hfair
    | cons ticks sched =>
      obtain ⟨hleg, hrest⟩ := hfair
      simp only [execAll] at h
      cases hv : execStep g v a with
      | none => simp [hv] at h
      | some v1 =>
        simp only [hv] at h
        obtain ⟨w1, hw1, hd1⟩ := execLeg_dom g w v v1 a ticks hd hleg hv
        simp only [run, hw1]
        exact ih sched w1 v1 v' hrest hd1 h

/-! ### The committed loop delivers -/

/-- **The committed loop delivers.** From the real bag, when the walk says `q`
of `i` can be had, following its witness leg by leg — a stochastic leg repeated
until its ticks add up to its amount — succeeds and ends holding at least `q`
of `i`, for every fair tick schedule. -/
theorem committed_loop_delivers (g : Graph) (i q : Nat) (h : feasible g i q = true)
    (sched : List (List Nat)) (hfair : Fair g (plan g i q) sched) :
    ∃ w', run g (plan g i q) sched ⟨St.init g, []⟩ = some w' ∧ q ≤ w'.st.bag i := by
  obtain ⟨v', hv', hq⟩ := feasible_witness g i q h
  obtain ⟨w', hw', hd⟩ := run_dom g (plan g i q) sched ⟨St.init g, []⟩ ⟨St.init g, []⟩ v' hfair
    ⟨fun _ => Nat.le_refl _, fun _ _ => Nat.le_refl _, fun _ h => h⟩ hv'
  exact ⟨w', hw', Nat.le_trans hq (hd.1 i)⟩

/-- **Fairness is satisfiable**: the schedule that delivers every leg's amount
in one tick is fair for any plan. -/
theorem schedule_exists (g : Graph) : ∀ (l : List Step), Fair g l (l.map (fun a =>
    match a with
    | .act _ _ c _ => [c]
    | .openGate _ _ _ => [])) := by
  intro l
  induction l with
  | nil => trivial
  | cons a l ih =>
    refine ⟨fun i k c n ha _ => ?_, ih⟩
    subst ha
    simp

/-! ### Examples -/

private def none0 : Nat → Nat := fun _ => 0

-- The copper ring, with the ore gathered in five short ticks (4 + 0 + 6 + 3 + 7 = 20).
private def ring : Graph :=
  ⟨3, none0, fun i =>
    if i = 0 then [⟨10, 1, 1000, [(1, 1)], []⟩]
    else if i = 1 then [⟨11, 2, 1000, [(2, 10)], []⟩]
    else if i = 2 then [⟨12, 1, 1000, [], []⟩] else []⟩
example : plan ring 0 3 = [.act 2 0 20 20, .act 1 0 3 2, .act 0 0 3 3] := by decide
example : ((run ring (plan ring 0 3) [[4, 0, 6, 3, 7], [], []] ⟨St.init ring, []⟩).map
    (fun w => w.st.bag 0)) = some 3 := by decide
-- An unfair schedule (the ore ticks stop at 19) does not complete the gather leg.
example : run ring (plan ring 0 3) [[4, 0, 6, 3, 6], [], []] ⟨St.init ring, []⟩ = none := by decide

end Formal.CommittedLoop

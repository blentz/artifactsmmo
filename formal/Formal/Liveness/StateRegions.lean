/-
  Formal.Liveness.StateRegions

  Phase-20a deliverable #2. Partitions the planner-side `State` space into
  named, decidable regions and proves the partition is exhaustive (every
  state lies in at least one — actually exactly one, since `regionOf` is a
  total function so disjointness is automatic).

  Each region is matched with a firing Phase-18 goal in
  `Formal.Liveness.RegionFiring`. The dispatch is "first-match wins" on
  the predicate ordering documented in `regionOf`.

  Region order (most urgent first):

    1. `criticalHP`           — `hpPercent < 25 %` (and `maxHp > 0`).
                                Restoring HP preempts everything else.
    2. `pendingItemsWaiting`  — `pendingItems = true`. Claim before
                                acting; cheap and frees a guarantee.
    3. `taskComplete`         — task accepted AND progress ≥ total > 0.
                                Complete frees the task slot.
    4. `noTask`               — no task accepted. Accept one.
    5. `inventoryFull`        — `inventoryUsed ≥ inventoryMax`. Discard /
                                deposit / sell. We pick DiscardOverstock
                                here because its firing precondition
                                (`¬satisfied`) is the easiest to discharge
                                from the bare `inventoryFull` predicate.
                                (Production prefers Deposit when bank
                                accessible; that ordering is a planner
                                concern, not a no-deadlock concern.)
    6. `levelBlocker`         — `unlockTargetLevel > 0 ∧ level < target
                                ∧ (target - level) ≤ 5`. The ≤ 5 gap is
                                exactly the `maxAchievableGap` bound on
                                `reachUnlockLevelValue`; gaps > 5 are
                                handled by the residual region.
    7. `bankLockedFightable`  — `bankLocked ∧ ¬bankXpExceeded ∧
                                ¬bankUnreachable`. Under these inputs
                                `unlockBankValue` returns either 30 (the
                                deferral branch with sellable cushion) or
                                90 — strictly positive in both cases.
                                "Fightable" is encoded via the
                                `¬bankUnreachable` flag.
    8. `progressNeeded`       — residual. Fired by `pursueTaskValue`
                                (floor 35).

  Liveness namespace — Mathlib axioms allowed.
-/
import Formal.Liveness.Measure

set_option linter.dupNamespace false

namespace Formal.Liveness.StateRegions

open Formal.Liveness.Measure

/-! ## Region tag -/

inductive Region where
  | criticalHP
  | pendingItemsWaiting
  | taskComplete
  | noTask
  | inventoryFull
  | levelBlocker
  | bankLockedFightable
  | progressNeeded
  deriving DecidableEq, Repr

/-! ## Region predicates (each `Bool`-valued for decidability). -/

/-- HP-percent strictly below 25 %, without floats. The Rat inequality
    `hp / maxHp < 1/4` is equivalent (when `maxHp > 0`) to
    `4 * hp < maxHp`. With `maxHp = 0` we say `false` (no HP to restore
    in a maxHp-zero state; the planner treats it as out-of-band). -/
def isCriticalHP (s : State) : Bool :=
  decide (s.maxHp > 0) && decide (4 * s.hp < s.maxHp)

/-- Inventory has no free slot for the next gather/drop. -/
def isInventoryFull (s : State) : Bool :=
  decide (s.inventoryUsed ≥ s.inventoryMax)

/-- A task is accepted (taskCode = some _) and progress has reached
    total. Requires `taskTotal > 0` to exclude the "no-task" sentinel
    where total = 0 = progress. -/
def isTaskComplete (s : State) : Bool :=
  s.taskCode.isSome && decide (s.taskTotal > 0)
  && decide (s.taskProgress ≥ s.taskTotal)

/-- No task is accepted. -/
def isNoTask (s : State) : Bool := s.taskCode.isNone

/-- Active level-unlock goal whose target is reachable within the
    `maxAchievableGap = 5` window. -/
def isLevelBlocker (s : State) : Bool :=
  decide (s.unlockTargetLevel > 0)
  && decide (s.level < s.unlockTargetLevel)
  && decide (s.unlockTargetLevel - s.level ≤ 5)

/-- Bank locked, fightable (not unreachable), xp not already exceeded.
    Under these conditions `unlockBankValue` returns 30 (deferral with
    sellable cushion) OR 90 (no-deferral) depending on inventory state
    — both strictly positive, so the region fires regardless of
    inventory/sellable inputs. -/
def isBankLockedFightable (s : State) : Bool :=
  s.bankLocked && !s.bankXpExceeded && !s.bankUnreachable

/-! ## Deterministic dispatch. -/

/-- Map a state to its region, first-match wins by the order in the
    module docstring. The catch-all is `progressNeeded`. -/
def regionOf (s : State) : Region :=
  if isCriticalHP s then .criticalHP
  else if s.pendingItems then .pendingItemsWaiting
  else if isTaskComplete s then .taskComplete
  else if isNoTask s then .noTask
  else if isInventoryFull s then .inventoryFull
  else if isLevelBlocker s then .levelBlocker
  else if isBankLockedFightable s then .bankLockedFightable
  else .progressNeeded

/-! ## Exhaustiveness audit. -/

/-- Every state maps to some region — the trivial statement of total
    coverage. Stated explicitly for the audit trail (RegionFiring then
    discharges "and that region's named goal fires"). -/
theorem regions_exhaustive : ∀ s : State, ∃ r : Region, regionOf s = r := by
  intro s; exact ⟨regionOf s, rfl⟩

/-! ## Per-region characterisation lemmas

These extract the load-bearing booleans from `regionOf s = .X` so the
RegionFiring lemmas can rewrite without re-deriving the if-chain. -/

theorem regionOf_criticalHP {s : State}
    (h : regionOf s = .criticalHP) : isCriticalHP s = true := by
  by_contra hne
  have : isCriticalHP s = false := by
    cases hC : isCriticalHP s with
    | true  => simp [hC] at hne
    | false => rfl
  simp [regionOf, this] at h
  -- After eliminating the criticalHP branch, h reduces to a chain of
  -- nested ifs whose terminal value is `.progressNeeded`; none of the
  -- intermediate branches equal `.criticalHP`.
  split at h <;> [skip; split at h <;> [skip; split at h <;>
    [skip; split at h <;> [skip; split at h <;>
      [skip; split at h]]]]] <;> simp at h

theorem regionOf_pendingItems {s : State}
    (h : regionOf s = .pendingItemsWaiting) :
    isCriticalHP s = false ∧ s.pendingItems = true := by
  refine ⟨?hC, ?hP⟩
  · by_contra hne
    have hC : isCriticalHP s = true := by
      cases hh : isCriticalHP s with
      | true  => rfl
      | false => simp [hh] at hne
    simp [regionOf, hC] at h
  · -- criticalHP must be false (else .criticalHP), then pendingItems true.
    have hC : isCriticalHP s = false := by
      by_contra hne
      have : isCriticalHP s = true := by
        cases hh : isCriticalHP s with
        | true  => rfl
        | false => simp [hh] at hne
      simp [regionOf, this] at h
    by_contra hne
    have hP : s.pendingItems = false := by
      cases hh : s.pendingItems with
      | true  => simp [hh] at hne
      | false => rfl
    simp [regionOf, hC, hP] at h
    split at h <;> [skip; split at h <;> [skip; split at h <;>
      [skip; split at h <;> [skip; split at h]]]] <;> simp at h

theorem regionOf_taskComplete {s : State}
    (h : regionOf s = .taskComplete) :
    isCriticalHP s = false ∧ s.pendingItems = false
    ∧ isTaskComplete s = true := by
  have hC : isCriticalHP s = false := by
    by_contra hne
    have : isCriticalHP s = true := by
      cases hh : isCriticalHP s with
      | true => rfl | false => simp [hh] at hne
    simp [regionOf, this] at h
  have hP : s.pendingItems = false := by
    by_contra hne
    have : s.pendingItems = true := by
      cases hh : s.pendingItems with
      | true => rfl | false => simp [hh] at hne
    simp [regionOf, hC, this] at h
  have hT : isTaskComplete s = true := by
    by_contra hne
    have : isTaskComplete s = false := by
      cases hh : isTaskComplete s with
      | true  => simp [hh] at hne
      | false => rfl
    simp [regionOf, hC, hP, this] at h
    split at h <;> [skip; split at h <;> [skip; split at h <;>
      [skip; split at h]]] <;> simp at h
  exact ⟨hC, hP, hT⟩

theorem regionOf_noTask {s : State}
    (h : regionOf s = .noTask) :
    isCriticalHP s = false ∧ s.pendingItems = false
    ∧ isTaskComplete s = false ∧ isNoTask s = true := by
  have hC : isCriticalHP s = false := by
    by_contra hne
    have : isCriticalHP s = true := by
      cases hh : isCriticalHP s with
      | true => rfl | false => simp [hh] at hne
    simp [regionOf, this] at h
  have hP : s.pendingItems = false := by
    by_contra hne
    have : s.pendingItems = true := by
      cases hh : s.pendingItems with
      | true => rfl | false => simp [hh] at hne
    simp [regionOf, hC, this] at h
  have hT : isTaskComplete s = false := by
    by_contra hne
    have : isTaskComplete s = true := by
      cases hh : isTaskComplete s with
      | true => rfl | false => simp [hh] at hne
    simp [regionOf, hC, hP, this] at h
  have hN : isNoTask s = true := by
    by_contra hne
    have : isNoTask s = false := by
      cases hh : isNoTask s with
      | true => simp [hh] at hne | false => rfl
    simp [regionOf, hC, hP, hT, this] at h
    split at h <;> [skip; split at h <;> [skip; split at h]] <;> simp at h
  exact ⟨hC, hP, hT, hN⟩

theorem regionOf_inventoryFull {s : State}
    (h : regionOf s = .inventoryFull) :
    isCriticalHP s = false ∧ s.pendingItems = false
    ∧ isTaskComplete s = false ∧ isNoTask s = false
    ∧ isInventoryFull s = true := by
  have hC : isCriticalHP s = false := by
    by_contra hne
    have : isCriticalHP s = true := by
      cases hh : isCriticalHP s with
      | true => rfl | false => simp [hh] at hne
    simp [regionOf, this] at h
  have hP : s.pendingItems = false := by
    by_contra hne
    have : s.pendingItems = true := by
      cases hh : s.pendingItems with
      | true => rfl | false => simp [hh] at hne
    simp [regionOf, hC, this] at h
  have hT : isTaskComplete s = false := by
    by_contra hne
    have : isTaskComplete s = true := by
      cases hh : isTaskComplete s with
      | true => rfl | false => simp [hh] at hne
    simp [regionOf, hC, hP, this] at h
  have hN : isNoTask s = false := by
    by_contra hne
    have : isNoTask s = true := by
      cases hh : isNoTask s with
      | true => rfl | false => simp [hh] at hne
    simp [regionOf, hC, hP, hT, this] at h
  have hF : isInventoryFull s = true := by
    by_contra hne
    have : isInventoryFull s = false := by
      cases hh : isInventoryFull s with
      | true => simp [hh] at hne | false => rfl
    simp [regionOf, hC, hP, hT, hN, this] at h
    split at h <;> [skip; split at h] <;> simp at h
  exact ⟨hC, hP, hT, hN, hF⟩

theorem regionOf_levelBlocker {s : State}
    (h : regionOf s = .levelBlocker) :
    isCriticalHP s = false ∧ s.pendingItems = false
    ∧ isTaskComplete s = false ∧ isNoTask s = false
    ∧ isInventoryFull s = false ∧ isLevelBlocker s = true := by
  have hC : isCriticalHP s = false := by
    by_contra hne
    have : isCriticalHP s = true := by
      cases hh : isCriticalHP s with
      | true => rfl | false => simp [hh] at hne
    simp [regionOf, this] at h
  have hP : s.pendingItems = false := by
    by_contra hne
    have : s.pendingItems = true := by
      cases hh : s.pendingItems with
      | true => rfl | false => simp [hh] at hne
    simp [regionOf, hC, this] at h
  have hT : isTaskComplete s = false := by
    by_contra hne
    have : isTaskComplete s = true := by
      cases hh : isTaskComplete s with
      | true => rfl | false => simp [hh] at hne
    simp [regionOf, hC, hP, this] at h
  have hN : isNoTask s = false := by
    by_contra hne
    have : isNoTask s = true := by
      cases hh : isNoTask s with
      | true => rfl | false => simp [hh] at hne
    simp [regionOf, hC, hP, hT, this] at h
  have hF : isInventoryFull s = false := by
    by_contra hne
    have : isInventoryFull s = true := by
      cases hh : isInventoryFull s with
      | true => rfl | false => simp [hh] at hne
    simp [regionOf, hC, hP, hT, hN, this] at h
  have hL : isLevelBlocker s = true := by
    by_contra hne
    have : isLevelBlocker s = false := by
      cases hh : isLevelBlocker s with
      | true => simp [hh] at hne | false => rfl
    simp [regionOf, hC, hP, hT, hN, hF, this] at h
    split at h <;> simp at h
  exact ⟨hC, hP, hT, hN, hF, hL⟩

theorem regionOf_bankLockedFightable {s : State}
    (h : regionOf s = .bankLockedFightable) :
    isCriticalHP s = false ∧ s.pendingItems = false
    ∧ isTaskComplete s = false ∧ isNoTask s = false
    ∧ isInventoryFull s = false ∧ isLevelBlocker s = false
    ∧ isBankLockedFightable s = true := by
  have hC : isCriticalHP s = false := by
    by_contra hne
    have : isCriticalHP s = true := by
      cases hh : isCriticalHP s with
      | true => rfl | false => simp [hh] at hne
    simp [regionOf, this] at h
  have hP : s.pendingItems = false := by
    by_contra hne
    have : s.pendingItems = true := by
      cases hh : s.pendingItems with
      | true => rfl | false => simp [hh] at hne
    simp [regionOf, hC, this] at h
  have hT : isTaskComplete s = false := by
    by_contra hne
    have : isTaskComplete s = true := by
      cases hh : isTaskComplete s with
      | true => rfl | false => simp [hh] at hne
    simp [regionOf, hC, hP, this] at h
  have hN : isNoTask s = false := by
    by_contra hne
    have : isNoTask s = true := by
      cases hh : isNoTask s with
      | true => rfl | false => simp [hh] at hne
    simp [regionOf, hC, hP, hT, this] at h
  have hF : isInventoryFull s = false := by
    by_contra hne
    have : isInventoryFull s = true := by
      cases hh : isInventoryFull s with
      | true => rfl | false => simp [hh] at hne
    simp [regionOf, hC, hP, hT, hN, this] at h
  have hL : isLevelBlocker s = false := by
    by_contra hne
    have : isLevelBlocker s = true := by
      cases hh : isLevelBlocker s with
      | true => rfl | false => simp [hh] at hne
    simp [regionOf, hC, hP, hT, hN, hF, this] at h
  have hB : isBankLockedFightable s = true := by
    by_contra hne
    have : isBankLockedFightable s = false := by
      cases hh : isBankLockedFightable s with
      | true => simp [hh] at hne | false => rfl
    simp [regionOf, hC, hP, hT, hN, hF, hL, this] at h
  exact ⟨hC, hP, hT, hN, hF, hL, hB⟩

end Formal.Liveness.StateRegions

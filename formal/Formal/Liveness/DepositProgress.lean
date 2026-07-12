/-
  Formal.Liveness.DepositProgress

  Phase-19c deliverable. Models `DepositAllAction.is_applicable` and
  `DepositAllAction.apply` from
  `src/artifactsmmo_cli/ai/actions/deposit_all.py` and proves that, on
  every productive Deposit (one where the deposit count is positive and
  bounded by current inventoryUsed), the lex measure strictly decreases.

  ## Production reference (verified 2026-05-30 against deposit_all.py:22)

  `is_applicable(state, gd)`:
    * `self.accessible`                              (False if HTTP 496)
    * `bool(self._deposits(state))`                  (non-empty selection
       returned by `select_bank_deposits(state, game_data)`)

  `apply(state, gd)`:
    * For each `(code, qty)` in `self._deposits(state)`:
        new_bank[code] += qty
        new_inventory.pop(code, None)
    * x,y := bank_location  (irrelevant to the measure)
    * cooldown_expires := None  (irrelevant to the measure)

  `WorldState.inventory_used` is a DERIVED `@property` (see
  `world_state.py:136`) computed as the sum of stack quantities, so
  removing items from `inventory` automatically reduces `inventory_used`.
  In our minimal `State` we collapse this to a scalar `inventoryUsed` and
  model `depositApply` as decrementing it directly by the abstract
  `depositCount` (sum of `qty` over the selected items).

  ## Load-bearing hypotheses on the headline lemma — HONEST disclosure

    * `happ`        — applicability guard (accessible ∧ depositsNonEmpty).
    * `hcount`      — `depositCount > 0`. Required: a no-op deposit
       (zero items) does not advance bankPressure.
    * `hbound`      — `s.inventoryUsed ≥ depositCount`. Required because
       `Nat` subtraction saturates; without this, `inventoryUsed -
       depositCount = 0` and `bankPressure` may not strictly decrease.
       Production invariant: `select_bank_deposits` only returns items
       actually held, so the bound holds at the call site.
    * `hpressure`   — `s.inventoryUsed > bankPressureThreshold
       s.inventoryMax`. Required because `bankPressure` is itself a
       saturating subtraction; once at zero, depositing won't reduce it
       further. Production invariant: Deposit is selected as a guard
       precisely when inventory pressure is high (DEPOSIT_FULL guard,
       80 % threshold).

  Liveness namespace — Mathlib axioms allowed.
-/
import Formal.Liveness.Measure

namespace Formal.Liveness.DepositProgress

open Formal.Liveness.Measure

/-! ## Faithful model of `DepositAllAction.is_applicable` -/

/-- Mirrors `is_applicable` in `deposit_all.py`. `accessible` is the bank
    accessibility flag; `depositsNonEmpty` reflects `bool(self._deposits(
    state))`. -/
def depositIsApplicable
    (_s : State) (accessible : Bool) (depositsNonEmpty : Bool) : Bool :=
  accessible && depositsNonEmpty

/-! ## Faithful model of `DepositAllAction.apply` -/

/-- Mirrors `apply` in `deposit_all.py`, abstracted to a scalar deposit
    count. `depositCount` is the sum of `qty` over the items selected by
    `select_bank_deposits`. Other measure-relevant fields are preserved. -/
def depositApply (s : State) (depositCount : Nat) : State :=
  { s with inventoryUsed := s.inventoryUsed - depositCount }

/-! ## Aux: `depositApply` preserves higher-priority slots -/

@[simp] theorem depositApply_level (s : State) (n : Nat) :
    (depositApply s n).level = s.level := rfl

@[simp] theorem depositApply_xp (s : State) (n : Nat) :
    (depositApply s n).xp = s.xp := rfl

@[simp] theorem depositApply_taskTotal (s : State) (n : Nat) :
    (depositApply s n).taskTotal = s.taskTotal := rfl

@[simp] theorem depositApply_taskProgress (s : State) (n : Nat) :
    (depositApply s n).taskProgress = s.taskProgress := rfl

@[simp] theorem depositApply_trackedSkillLevel (s : State) (n : Nat) :
    (depositApply s n).trackedSkillLevel = s.trackedSkillLevel := rfl

@[simp] theorem depositApply_targetSkillLevel (s : State) (n : Nat) :
    (depositApply s n).targetSkillLevel = s.targetSkillLevel := rfl

/-! ## Headline progress lemma -/

set_option linter.unusedVariables false

/--
  **Productive Deposit strictly decreases the lex measure.**

  Load-bearing hypotheses (honest disclosure — see module docstring):
    * `happ`      — applicability guard, carried for parity.
    * `hcount`    — `depositCount > 0`.
    * `hbound`    — `s.inventoryUsed ≥ depositCount`.
    * `hpressure` — `s.inventoryUsed > bankPressureThreshold s.inventoryMax`.

  Conclusion: `measureLt (measure (depositApply s n)) (measure s)`.

  Proof route: slots 1-4 unchanged; slot 5 (`bankPressure`) strictly
  decreases.
-/
theorem deposit_decreases_measure
    (s : State) (accessible nonempty : Bool) (depositCount : Nat)
    (happ      : depositIsApplicable s accessible nonempty = true)
    (hcount    : depositCount > 0)
    (hbound    : s.inventoryUsed ≥ depositCount)
    (hpressure : s.inventoryUsed > bankPressureThreshold s.inventoryMax) :
    measureLt (Measure.measure (depositApply s depositCount))
              (Measure.measure s) := by
  -- Slots 1-4 unchanged.
  have hLevel :
      (Measure.measure (depositApply s depositCount)).levelDeficit
        = (Measure.measure s).levelDeficit := by
    unfold Measure.measure; rfl
  have hXp :
      (Measure.measure (depositApply s depositCount)).xpDeficit
        = (Measure.measure s).xpDeficit := by
    unfold Measure.measure; rfl
  have hTask :
      (Measure.measure (depositApply s depositCount)).taskCycles
        = (Measure.measure s).taskCycles := by
    unfold Measure.measure; rfl
  have hSkill :
      (Measure.measure (depositApply s depositCount)).skillXpDeficitProjected
        = (Measure.measure s).skillXpDeficitProjected := by
    unfold Measure.measure; rfl
  -- Slot 5: (inventoryUsed - count) - threshold < inventoryUsed - threshold
  have hBank :
      (Measure.measure (depositApply s depositCount)).bankPressure
        < (Measure.measure s).bankPressure := by
    show (s.inventoryUsed - depositCount) - bankPressureThreshold s.inventoryMax
          < s.inventoryUsed - bankPressureThreshold s.inventoryMax
    omega
  exact measureLt_of_bankPressure_dec hLevel hXp hTask hSkill hBank

end Formal.Liveness.DepositProgress

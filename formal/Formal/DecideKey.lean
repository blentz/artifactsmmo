/-
Formal model of the strategy-decide sort key + dispatcher-exhaustiveness
extracted from `src/artifactsmmo_cli/ai/tiers/decide_key.py` (which encodes
the sort key used by `StrategyEngine.decide` in `strategy.py` and the
GuardKind/MeansKind dispatch tables that `strategy_driver.py`'s `map_guard`
/ `map_means` use).

## (1) The `decide` sort

`StrategyEngine.decide` sorts candidate `(root, step, final, effort, value)`
tuples by `(-final, effort, repr(root))`. The comparator we model here is
lexicographic over the same three projections. Python tuple comparison is
strict-total on tuples of trichotomous orders, and the SAME structure holds
in Lean via `compareLex` + `compareOn` (same pattern as
`UpgradeSelection.craftableCmp`).

We use the third field (`root_repr : String`) as the GENUINE last tiebreak:
distinct production roots have distinct reprs (different MetaGoal types or
codes/levels), so `decideCmp` is a strict total order on production inputs.
For Lean we capture this as `cmp_eq_imp_repr`: an `eq` result forces all
three projections to coincide, in particular forcing equal reprs (so two
roots can tie only when their reprs collide — which, in production, means
they ARE the same root).

## (2) Dispatcher exhaustiveness

`map_guard` / `map_means` in `strategy_driver.py` dispatch a `GuardKind` /
`MeansKind` to a `Goal`. The Python implementation uses `if/elif/.../raise
ValueError("Unknown ...")` — a fall-through that is supposed to be DEAD code.
We mirror the enums as Lean inductives and write a TOTAL `match` over each.
The Lean compiler enforces exhaustiveness at elaboration: if a new variant
is added without a case here, the elaborator fails (compile-time guarantee
that the fall-through is unreachable). The `_total` theorems below then read
back the totality as a Prop: every variant produces a non-empty repr.

EXACT MATCH: the strings here mirror the production `Goal` `__repr__` outputs
(see `tests/test_ai/test_tiers_strategy_blend.py::TestDispatcherExhaustiveness`
which round-trips through the Python `goal_repr_of_guard/means` tables, which
in turn are pulled from the same Goal repr strings the driver uses).

Lean core only — no mathlib. Compile-time exhaustiveness via the inductive
`match`; `Ordering` algebra via Lean core `Std`.
-/

namespace Formal.DecideKey

open Std

/-! ## (1) The decide-sort comparator. -/

/-- One candidate's sort key triple. `negFinal` is `-final` SCALED to `Int`
(Python flips the sign so the natural `<` sorts high-final FIRST; the diff
test feeds an integer fixed-point representation that preserves order — see
`formal/diff/test_decide_key_diff.py`). `effort` is the integer root cost.
`rootRepr` is the MetaGoal's `repr` string. -/
structure Key where
  negFinal : Int
  effort : Int
  rootRepr : String
deriving Repr, DecidableEq

/-- Lexicographic comparator over the three projections in `(negFinal, effort,
rootRepr)` order. Same pattern as `UpgradeSelection.craftableCmp` — the
`Ordering` algebra makes oriented/transitive instances synthesize. -/
def decideCmp : Key → Key → Ordering :=
  compareLex (compareOn (fun k => k.negFinal))
    (compareLex (compareOn (fun k => k.effort))
      (compareOn (fun k => k.rootRepr)))

instance : OrientedCmp decideCmp :=
  inferInstanceAs (OrientedCmp (fun a b =>
    compareLex (compareOn (fun k : Key => k.negFinal))
      (compareLex (compareOn (fun k => k.effort))
        (compareOn (fun k => k.rootRepr))) a b))

instance : TransCmp decideCmp :=
  inferInstanceAs (TransCmp (fun a b =>
    compareLex (compareOn (fun k : Key => k.negFinal))
      (compareLex (compareOn (fun k => k.effort))
        (compareOn (fun k => k.rootRepr))) a b))

/-! ### Key intent theorems. -/

/-- TRICHOTOMY: every pair compares to exactly one of `.lt / .eq / .gt`. -/
theorem decideCmp_trichotomy (a b : Key) :
    decideCmp a b = .lt ∨ decideCmp a b = .eq ∨ decideCmp a b = .gt := by
  rcases h : decideCmp a b with _ | _ | _
  · exact Or.inl rfl
  · exact Or.inr (Or.inl rfl)
  · exact Or.inr (Or.inr rfl)

/-- ANTISYMMETRY: `cmp b a = (cmp a b).swap`. -/
theorem decideCmp_swap (a b : Key) :
    decideCmp b a = (decideCmp a b).swap :=
  OrientedCmp.eq_swap (cmp := decideCmp) (a := b) (b := a)

/-- TRANSITIVITY on the strict (`.lt`) relation. -/
theorem decideCmp_lt_trans {a b c : Key}
    (hab : decideCmp a b = .lt) (hbc : decideCmp b c = .lt) :
    decideCmp a c = .lt :=
  TransCmp.lt_trans hab hbc

/-- `Ordering.then x y = .eq` ⇒ `y = .eq` (and `x = .eq`). -/
private theorem then_eq_imp_snd {x y : Ordering} (h : x.then y = .eq) : y = .eq := by
  cases x <;> simp_all [Ordering.then]

/-- STRICT-TOTAL DETERMINISM: an `eq` result forces ALL THREE key fields to
agree, in particular EQUAL `rootRepr`. So two candidates with distinct reprs
are strictly ordered — the comparator is a strict total order on production
inputs (distinct production roots have distinct reprs by construction). -/
theorem decideCmp_eq_imp_repr (a b : Key)
    (h : decideCmp a b = .eq) : a.rootRepr = b.rootRepr := by
  unfold decideCmp compareLex at h
  replace h := then_eq_imp_snd (then_eq_imp_snd h)
  exact LawfulEqCmp.eq_of_compare (cmp := compare) h

/-- And the `negFinal` and `effort` projections also coincide on `eq`. -/
theorem decideCmp_eq_imp_negFinal (a b : Key)
    (h : decideCmp a b = .eq) : a.negFinal = b.negFinal := by
  unfold decideCmp compareLex at h
  -- The first `then` argument must itself be `.eq`.
  have hfirst : (compareOn (fun k : Key => k.negFinal) a b) = .eq := by
    -- If the first comparison weren't .eq, `then` would return it, and the whole
    -- result couldn't be .eq.
    cases hf : compareOn (fun k : Key => k.negFinal) a b
    · -- .lt: then .lt _ = .lt ≠ .eq
      rw [hf] at h; simp [Ordering.then] at h
    · rfl
    · rw [hf] at h; simp [Ordering.then] at h
  exact LawfulEqCmp.eq_of_compare (cmp := compare) hfirst

theorem decideCmp_eq_imp_effort (a b : Key)
    (h : decideCmp a b = .eq) : a.effort = b.effort := by
  unfold decideCmp compareLex at h
  -- After stripping the outer `then` we need the SECOND nested first comp to be .eq.
  replace h := then_eq_imp_snd h
  -- Now h : (compareLex (compareOn effort) (compareOn rootRepr)) a b = .eq, then strip again.
  unfold compareLex at h
  have hfirst : (compareOn (fun k : Key => k.effort) a b) = .eq := by
    cases hf : compareOn (fun k : Key => k.effort) a b
    · rw [hf] at h; simp [Ordering.then] at h
    · rfl
    · rw [hf] at h; simp [Ordering.then] at h
  exact LawfulEqCmp.eq_of_compare (cmp := compare) hfirst

/-- ALL-THREE-DISTINCT ⇒ STRICTLY ORDERED: if any of the three key fields
differ, the comparator returns `.lt` or `.gt`, never `.eq`. The compositions
of the above. -/
theorem decideCmp_ne_of_repr_ne (a b : Key) (h : a.rootRepr ≠ b.rootRepr) :
    decideCmp a b ≠ .eq := by
  intro heq
  exact h (decideCmp_eq_imp_repr a b heq)

/-! ## (2) Dispatcher inductives + total `repr` maps. -/

/-- Mirror of `src/artifactsmmo_cli/ai/tiers/guards.py::GuardKind`. -/
inductive GuardKind where
  | hpCritical
  | bankUnlock
  | reachUnlockLevel
  | discardCritical
  | depositFull
  | discardHigh
deriving Repr, DecidableEq

/-- Mirror of `src/artifactsmmo_cli/ai/tiers/means.py::MeansKind`. -/
inductive MeansKind where
  | claimPending
  | completeTask
  | sellPressured
  | lowYieldCancel
  | taskCancel
  | pursueTask
  | acceptTask
  | taskExchange
  | sellIdle
  | bankExpand
deriving Repr, DecidableEq

/-- TOTAL `match`: every `GuardKind` variant maps to a non-empty repr string.
The Lean compiler enforces exhaustiveness at elaboration — if a new variant
is added to `GuardKind`, this declaration FAILS TO ELABORATE unless a case is
added. The fall-through is statically unreachable. -/
def goalReprOfGuard : GuardKind → String
  | .hpCritical       => "RestoreHP"
  | .discardCritical  => "DiscardOverstock"
  | .discardHigh      => "DiscardOverstock"
  | .bankUnlock       => "UnlockBank"
  | .reachUnlockLevel => "ReachUnlockLevel"
  | .depositFull      => "DepositInventory"

/-- TOTAL `match`: every `MeansKind` variant maps to a non-empty repr string. -/
def goalReprOfMeans : MeansKind → String
  | .claimPending    => "ClaimPending"
  | .completeTask    => "CompleteTask"
  | .sellPressured   => "SellInventory"
  | .sellIdle        => "SellInventory"
  | .lowYieldCancel  => "LowYieldCancel"
  | .taskCancel      => "TaskCancel"
  | .pursueTask      => "PursueTask"
  | .acceptTask      => "AcceptTask"
  | .taskExchange    => "TaskExchange"
  | .bankExpand      => "ExpandBank"

/-! ### Exhaustiveness intent theorems (totality witnesses). -/

/-- Every `GuardKind` variant yields a non-empty repr. The proof's `match` is
the SAME exhaustive structure as `goalReprOfGuard` itself: any new variant
forces a new case here too, so the compile-time exhaustiveness check applies
at BOTH sites. (This is the Prop-level read-back of the static exhaustiveness
guarantee.) -/
theorem goalReprOfGuard_nonempty : ∀ k : GuardKind, (goalReprOfGuard k).length > 0 := by
  intro k; cases k <;> decide

/-- Every `MeansKind` variant yields a non-empty repr. -/
theorem goalReprOfMeans_nonempty : ∀ k : MeansKind, (goalReprOfMeans k).length > 0 := by
  intro k; cases k <;> decide

/-! ### Non-vacuity examples. -/

/-- Two distinct-repr keys are strictly ordered (NOT `.eq`): pins the
strict-total-order property at concrete values. -/
example :
    let a : Key := ⟨-900, 5, "ReachCharLevel(level=5)"⟩
    let b : Key := ⟨-500, 3, "ReachSkillLevel(skill='mining', level=3)"⟩
    decideCmp a b = .lt := by decide

/-- Two keys with identical `(negFinal, effort)` but different reprs break
the tie by string order (NOT `.eq`): pins the repr tiebreak. -/
example :
    let a : Key := ⟨-500, 3, "A"⟩
    let b : Key := ⟨-500, 3, "B"⟩
    decideCmp a b = .lt ∧ decideCmp a b ≠ .eq := by
  refine ⟨by decide, by decide⟩

/-- Identical keys compare equal (only when ALL THREE fields coincide). -/
example : decideCmp ⟨-1, 1, "X"⟩ ⟨-1, 1, "X"⟩ = .eq := by decide

/-- Every guard variant indeed yields a known production repr (witness for
the dispatcher table). -/
example : goalReprOfGuard .hpCritical = "RestoreHP" := rfl
example : goalReprOfGuard .depositFull = "DepositInventory" := rfl

/-- Every means variant likewise. -/
example : goalReprOfMeans .pursueTask = "PursueTask" := rfl
example : goalReprOfMeans .sellIdle = "SellInventory" := rfl

end Formal.DecideKey

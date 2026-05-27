import Formal.CalculatePath
open Formal.CalculatePath
/-! STATEMENT CONTRACTS. Each `example` pins a role theorem's EXACT statement by
    ascribing it the full expected type. If a theorem's statement is weakened or
    changed, the ascription fails to elaborate and the build goes RED. This is the
    mechanized "theorem-statement review" — names alone are not enough (Manifest).
    Do NOT relax an expected type to make it compile; that defeats the gate. -/

-- validity
example : ∀ (start dst : Coord), ValidKingWalk start dst (pathFrom start dst) :=
  @pathFrom_valid
-- optimality achieved (length = Chebyshev, exactly)
example : ∀ (start dst : Coord), (pathFrom start dst).length = (cheb start dst).toNat :=
  @pathFrom_len_eq_cheb
-- optimality lower bound (EVERY valid king-walk ≥ Chebyshev)
example : ∀ (start dst : Coord) (p : List Coord),
    ValidKingWalk start dst p → (cheb start dst).toNat ≤ p.length :=
  @kingWalk_len_ge_cheb
-- cost: produced length ≤ reported Manhattan
example : ∀ (start dst : Coord),
    (pathFrom start dst).length ≤ (manhattan start dst).toNat :=
  @pathFrom_cost
-- cost: Chebyshev ≤ Manhattan
example : ∀ (start dst : Coord), cheb start dst ≤ manhattan start dst :=
  @cheb_le_manhattan
-- estimated_time: 5 × Chebyshev (len(steps) * 5)
example : ∀ (start dst : Coord), estimatedTime start dst = (cheb start dst).toNat * 5 :=
  @estimatedTime_eq_cheb

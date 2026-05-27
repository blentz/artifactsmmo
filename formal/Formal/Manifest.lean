import Formal
open Formal.CalculatePath Formal.TaskBatch Formal.InventoryCaps
-- CalculatePath required roles:
#check @pathFrom_valid         -- validity
#check @pathFrom_len_eq_cheb   -- optimality-achieved
#check @kingWalk_len_ge_cheb   -- optimality-lower-bound
#check @pathFrom_cost          -- cost (length <= manhattan)
#check @cheb_le_manhattan      -- cost (chebyshev <= manhattan)
#check @estimatedTime_eq_cheb  -- estimated_time (= cheb * 5)
-- TaskBatch required roles:
#check @batch_ge_one        -- result ≥ 1 always
#check @batch_le_remaining  -- task-branch ⇒ result ≤ remaining
#check @batch_le_cap        -- task-branch ⇒ result ≤ BATCH_CAP
#check @batch_fits          -- task-branch ∧ usable ≥ mats ⇒ result*mats ≤ usable
#check @non_task_one        -- ¬task-branch ⇒ result = 1
-- InventoryCaps required roles:
#check @cap_eq_max_of_four      -- ¬equipped ⇒ cap = max-of-four
#check @cap_eq_max_one_of_four  -- equipped ⇒ cap = max(1, max-of-four)
#check @equipped_ge_one         -- equipped ⇒ 1 ≤ cap
#check @recipe_cap_ge_safety    -- demand>0 ⇒ recipeCap ≥ SAFETY_FLOOR
#check @overstock_exact         -- overstock = qty-cap iff over, else 0
#check @overstock_pos_of_over   -- over ⇒ excess > 0
#check @overstock_zero_of_not_over -- ¬over ⇒ excess = 0

import Formal
open Formal.CalculatePath Formal.TaskBatch Formal.InventoryCaps Formal.PredictWin Formal.LoadoutProjection Formal.EquipmentScoring Formal.SkillXpCurve
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
-- PredictWin required roles:
#check @predict_win_eq_sim          -- closed-form verdict = operational fight-sim
#check @maxturns_sound              -- rounds_to_kill > MAX_TURNS ⇒ ¬win
#check @predict_win_mono_player     -- ↑player raw never flips win→loss
#check @predict_win_mono_monsterhp  -- ↓monster HP never flips win→loss
-- LoadoutProjection required roles:
#check @proj_identity              -- loadout = equipment ⇒ projected = current
#check @proj_additive              -- projected = current + Σ_all (new − old)
#check @guarded_eq_unconditional   -- changed-guarded sum = unconditional sum (guard sound)
#check @dropZeros_preserves_nonzero -- _drop_zeros keeps nonzero entries unchanged
#check @dropZeros_zero_reads_zero   -- dropped zero reads back as 0 (dict.get(k,0))
-- EquipmentScoring required roles:
#check @pickslot_score_optimal       -- best = max score over feasible candidates
#check @pickslot_no_downgrade        -- result score ≥ current score (never downgrade)
#check @pickslot_best_feasible       -- the picked best is level-feasible ∧ slot-fitting
#check @pickslot_ties_keep_current   -- tie at max ⇒ keep current (no swap)
#check @pickslot_empty_fills         -- empty slot + candidate ⇒ filled with argmax
#check @pickslot_no_candidates_keeps -- no feasible candidate ⇒ slot left as-is
#check @weapon_score_nonneg          -- WScore ≥ 0 (the clamp earns this)
-- SkillXpCurve required roles:
#check @required_xp_observed       -- observed level ⇒ required_xp = stored xp
#check @required_xp_zero           -- no data ∨ no level below ⇒ 0
#check @confNum_le_confDen         -- 0 ≤ confNum ≤ confDen (fraction ∈ [0,1])
#check @is_confident_iff_full      -- is_confident ↔ confNum = confDen
#check @cycles_zero                -- target ≤ current ⇒ 0
#check @cycles_inf                 -- target>current ∧ xp_per_cycle≤0 ⇒ inf-sentinel
#check @total_monotone             -- total(cur,tgt) ≤ total(cur,tgt+1) over observed
#check @growth_default_iff         -- uses-default ↔ no consecutive observed pair
#check @growth_nondefault_of_pair  -- consecutive observed pair ⇒ ¬default (witness)

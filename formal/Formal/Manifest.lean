import Formal
import Formal.OwnedCount
open Formal.CalculatePath Formal.TaskBatch Formal.InventoryCaps Formal.PredictWin Formal.LoadoutProjection Formal.EquipmentScoring Formal.SkillXpCurve Formal.RecipeClosure
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
-- RecipeClosure required roles:
#check @reachable_iff_satN          -- DFS closure = least fixpoint (sound + complete)
#check @reachable_least             -- Reachable is the SMALLEST closed set
#check @closureItems_sound          -- computed closure ⊆ Reachable (no extra)
#check @closureItems_complete       -- reachable-within-budget ⊆ computed closure
#check @craftableList_isCraftable   -- craftable_mats member ⇒ Reachable ∧ has recipe
#check @neededList_isNeeded         -- needed_resources member ⇒ drop Reachable
#check @rawUnits_eq_cost            -- raw_material_units = Σ qty * units(sub)
#check @rawUnits_revisit            -- cyclic guard: revisit ⇒ cost 1
#check @remaining_decreasing        -- termination measure strictly decreases
#check @rawUnits_fuel_stable        -- adequate fuel ⇒ fuel-independent (terminates)
-- TaskFeasibility required roles:
#check @Formal.TaskFeasibility.worst_eq_max_unmet  -- required_level = MAX craftLevel over unmet closure
#check @Formal.TaskFeasibility.worst_is_max        -- every unmet closure item ≤ returned worst
#check @Formal.TaskFeasibility.none_iff_no_unmet   -- result None ⇔ no unmet gap in closure
#check @Formal.TaskFeasibility.worst_is_real_gap   -- positive result ⇒ ∃ genuine unmet item at that level
#check @Formal.TaskFeasibility.monster_gate        -- gate ⇔ 0<mlvl ∧ clvl+2<mlvl (independent spec)
#check @Formal.TaskFeasibility.monster_gate_boundary_false -- monster at clvl+2 does NOT gate (off-by-one anchor)
#check @Formal.TaskFeasibility.monster_gate_just_past      -- monster at clvl+3 DOES gate
#check @Formal.TaskFeasibility.monster_gate_zero_never     -- monster_level 0 never gates
-- PrerequisiteGraph required roles:
#check @Formal.PrerequisiteGraph.prereqs_recipe_with_skill -- craftable+skill ⇒ skill edge :: item edges
#check @Formal.PrerequisiteGraph.prereqs_recipe_no_skill   -- craftable, no skill ⇒ item edges only
#check @Formal.PrerequisiteGraph.prereqs_membership        -- EXACT edge set (skill ∨ ingredient item)
#check @Formal.PrerequisiteGraph.prereqs_resource          -- resource-drop ⇒ single resource-skill edge
#check @Formal.PrerequisiteGraph.prereqs_leaf              -- non-craftable, non-resource ⇒ leaf
#check @Formal.PrerequisiteGraph.resource_branch_no_item   -- resource branch emits no item edge
#check @Formal.PrerequisiteGraph.combat_capable_iff        -- combat_capable ↔ ∃ beatable monster
#check @Formal.PrerequisiteGraph.combat_capable_demorgan   -- ¬capable ↔ all unbeatable (any≠all)
#check @Formal.PrerequisiteGraph.combat_capable_empty      -- no monsters ⇒ not capable
-- Objective required roles:
#check @Formal.Objective.is_attainable_eq_grounding  -- is_attainable = grounding fixpoint (sound+complete)
#check @Formal.Objective.groundedByN_sound           -- saturation SOUND wrt Grounded
#check @Formal.Objective.grounded_groundedByN        -- saturation COMPLETE wrt Grounded
#check @Formal.Objective.attainAux_sound             -- recursion accept ⇒ Grounded (any path/fuel)
#check @Formal.Objective.best_gear_argmax            -- first-slot pick = argmax over attainable
#check @Formal.Objective.bestGear_optimal            -- bestGear dominates every member by (-value,code)
#check @Formal.Objective.gapSum_nonneg               -- gap numerator ≥ 0
#check @Formal.Objective.gapSum_le_targetSum         -- gap ≤ denom (fraction ∈ [0,1], integer-only)
#check @Formal.Objective.charGap_bounds              -- 0 ≤ char gap ≤ target
#check @Formal.Objective.is_complete_iff             -- is_complete ↔ raw-target form (independent)
#check @Formal.Objective.axisGap_zero_iff            -- per-axis gap 0 ↔ raw target met
-- StrategyTraversal required roles:
#check @Formal.StrategyTraversal.is_reachable_eq_grounding  -- is_reachable = grounding fixpoint (sound+complete)
#check @Formal.StrategyTraversal.groundedByN_sound          -- saturation SOUND wrt Grounded
#check @Formal.StrategyTraversal.grounded_groundedByN       -- saturation COMPLETE wrt Grounded
#check @Formal.StrategyTraversal.reachAux_sound             -- recursion accept ⇒ Grounded (any path/fuel)
#check @Formal.StrategyTraversal.unmetClosureSize_ge_one    -- closure_size ≥ 1 (the max(·,1) floor)
#check @Formal.StrategyTraversal.unmetClosureSize_eq_count  -- closure_size = count of distinct unmet visited nodes
#check @Formal.StrategyTraversal.unmetNodes_unmet           -- counted node ⇒ UNMET (satisfied-interior pruning)
#check @Formal.StrategyTraversal.actionable_step_sound      -- returned node is ActionableNode
#check @Formal.StrategyTraversal.actionable_step_none_iff   -- none ⇔ no actionable reachable (De Morgan)
#check @Formal.StrategyTraversal.actionable_step_reach      -- returned node UnmetReach-able from root
#check @Formal.StrategyTraversal.rootCost_ge_one            -- root_cost ≥ 1 (every kind)
#check @Formal.StrategyTraversal.reachable_implies_actionable -- reachable-implies-actionable: is_reachable ⇒ actionable_step ≠ none (the decide assert)
#check @Formal.StrategyTraversal.grounded_unmet_has_actionable -- bridge: unmet Grounded node has reachable ActionableNode
-- BankSelection required roles:
#check @Formal.BankSelection.deposits_exact                -- candidates = qty>0 inventory ∉ keep
#check @Formal.BankSelection.deposits_mem_iff              -- sorted list = same set (permutation)
#check @Formal.BankSelection.freeze_invariant             -- deposits ∩ keep = ∅ (never bank protected)
#check @Formal.BankSelection.task_inputs_protected        -- recipe materials of protected roots ⊆ keep
#check @Formal.BankSelection.task_material_not_deposited   -- a protected material is NEVER deposited
#check @Formal.BankSelection.keep_closed                  -- material captured ⇒ kept ∧ StepReachable
#check @Formal.BankSelection.recipeMaterials_closed       -- materials closed under recipe children
#check @Formal.BankSelection.recipeMaterialList_complete  -- material capture COMPLETE within fuel
#check @Formal.BankSelection.best_weapon_argmax           -- best weapon = max-attack non-tool over inv∪equip
#check @Formal.BankSelection.best_weapon_is_fighting      -- best weapon is a non-tool weapon
-- StuckDetector required roles:
#check @Formal.StuckDetector.recent_since_window      -- _recent_since = keep global idx ≥ cutoff, last count
#check @Formal.StuckDetector.recentSince_mem_global   -- every kept record's global index clears cutoff
#check @Formal.StuckDetector.detect_precedence        -- strict frozen > osc > noprog, else none
#check @Formal.StuckDetector.detect_frozen_wins       -- frozen check ⇒ frozen (even if osc/noprog fire)
#check @Formal.StuckDetector.detect_osc_over_noprog   -- osc beats noprog when frozen false
#check @Formal.StuckDetector.noprog_threshold         -- noprog ↔ last-4 full ∧ all <no_plan>
#check @Formal.StuckDetector.osc_threshold            -- osc ↔ last-8 full ∧ exactly 2 distinct goals
#check @Formal.StuckDetector.frozen_threshold         -- frozen ↔ last-10 full ∧ some state ≥ 5
#check @Formal.StuckDetector.ack_suppression_noprog   -- post-ack noprog window empty
#check @Formal.StuckDetector.ack_suppression_frozen   -- post-ack frozen window empty
#check @Formal.StuckDetector.ack_suppression_osc      -- post-ack osc window empty
#check @Formal.StuckDetector.ack_noprog_cannot_fire   -- just-acked noprog cannot re-fire
#check @Formal.StuckDetector.ack_frozen_cannot_fire   -- just-acked frozen cannot re-fire
#check @Formal.StuckDetector.ack_osc_cannot_fire      -- just-acked osc cannot re-fire
-- PriorityBand required roles:
open Formal.PriorityBand
#check @Formal.PriorityBand.clamp_lower_bound    -- band-lower: floor ≤ clamped result
#check @Formal.PriorityBand.clamp_upper_bound    -- band-upper: clamped result ≤ ceiling
#check @Formal.PriorityBand.clamp_below_survival -- survival-floor-safety: ceiling < survival ⇒ clamped < survival
-- OwnedCount required roles:
#check @Formal.OwnedCount.ownedCount_eq_total          -- owned-count-sum: count = spares + bank + equipped, unconditionally
#check @Formal.OwnedCount.ownedCount_counts_equipped   -- owned-count-counts-equipped: equipped ⇒ count ≥ 1 (no re-acquire loop)
#check @Formal.OwnedCount.ownedCount_monotone          -- owned-count-monotone: count non-decreasing in spares (satisfaction soundness)
-- UpgradeSelection required roles:
#check @Formal.UpgradeSelection.best_by_value_not_worse        -- best-no-downgrade: best_by_value never returns the strictly-worse pick
#check @Formal.UpgradeSelection.best_by_value_tie_inv          -- best-no-downgrade: tie -> inventory pick
#check @Formal.UpgradeSelection.craftableCmp_trichotomy        -- key-total-order: craftable comparator trichotomous
#check @Formal.UpgradeSelection.craftableCmp_swap              -- key-total-order: craftable comparator antisymmetric
#check @Formal.UpgradeSelection.craftableCmp_lt_trans          -- key-total-order: craftable comparator transitive
#check @Formal.UpgradeSelection.craftableCmp_eq_imp_code       -- key-total-order: craftable eq forces equal item_code (determinism)
#check @Formal.UpgradeSelection.inventoryCmp_trichotomy        -- key-total-order: inventory comparator trichotomous
#check @Formal.UpgradeSelection.inventoryCmp_swap              -- key-total-order: inventory comparator antisymmetric
#check @Formal.UpgradeSelection.inventoryCmp_lt_trans          -- key-total-order: inventory comparator transitive
#check @Formal.UpgradeSelection.inventoryCmp_eq_imp_code       -- key-total-order: inventory eq forces equal item_code (determinism)
#check @Formal.UpgradeSelection.bestByKey_sound                -- argmax-sound: result dominates list and is a member (first-wins on ties)
-- Scalarizer required roles:
#check @Formal.Scalarizer.scalarYield_mono_charxp     -- mono-charxp: scalar non-decreasing in char_xp (level ≥ 0)
#check @Formal.Scalarizer.scalarYield_mono_gold       -- mono-gold: scalar non-decreasing in gold (goldUnit ≥ 0)
#check @Formal.Scalarizer.scalarYield_mono_coins      -- mono-coins: scalar non-decreasing in tasks_coins (coinValue,goldUnit ≥ 0)
#check @Formal.Scalarizer.skillSum_mono_one           -- mono-skillxp: scalar non-decreasing in one skill's xp (weight ≥ 0)
#check @Formal.Scalarizer.relevant_weight_dominates   -- weight-dominance: relevant weight ≥ baseline weight per xp unit
#check @Formal.Scalarizer.coinsSpent_inverts          -- coin-inversion: received - coinsSpent received delta = delta
-- PlannerAdmissibility required roles (AFFIRMATION of planner.py:99 post-fix h ≡ 0, Dijkstra-optimal):
#check @Formal.PlannerAdmissibility.fScore_eq_g_at_goal_of_admissible -- conditional intent: admissible h ⇒ popped f = plan cost at goal
#check @Formal.PlannerAdmissibility.firstSatisfied_least_cost_of_admissible -- general A* optimality: admissible h ⇒ first popped satisfied is least cost
#check @Formal.PlannerAdmissibility.zero_h_admissible             -- h ≡ 0 is admissible w.r.t. any trueRemaining (post-fix planner heuristic)
#check @Formal.PlannerAdmissibility.RHP_h_admissible              -- the planner's RHP heuristic IS admissible
#check @Formal.PlannerAdmissibility.RHP_optimal_popped_before_rest -- f(eaten,7) = 7 < 10 = f(rested,10): optimal popped first
#check @Formal.PlannerAdmissibility.RHP_first_satisfied_is_optimal -- FIX: returned plan cost 7 ≤ 10
#check @Formal.PlannerAdmissibility.RHP_optimal_strictly_cheaper_than_rest -- strictly: 7 < 10
-- ArbiterSelect required roles:
#check @Formal.ArbiterSelect.select_pure_guard_wins              -- sticky-safety: head-guard plannable ⇒ guard returned regardless of committed
#check @Formal.ArbiterSelect.select_pure_sticky_idempotent       -- sticky-idempotence: no guards ∧ committed plans ⇒ committed returned
#check @Formal.ArbiterSelect.select_pure_no_commitment_is_walk   -- no-commit: select = walk in band order
#check @Formal.ArbiterSelect.walk_returns_head                   -- walk-head: head plannable & non-skipped ⇒ head returned
#check @Formal.ArbiterSelect.guardPrecedes_of_head_guard         -- structural: head guard with id ≠ committed precedes committed means in rest
-- TaskDecision required roles:
#check @Formal.TaskDecision.combat_or_no_history_pivots          -- combat-pivots: combat ∨ ¬history ⇒ PIVOT
#check @Formal.TaskDecision.req_none_pursues                     -- already-feasible: req None ⇒ PURSUE
#check @Formal.TaskDecision.no_div_by_zero_from_invariant        -- no-div-by-zero: cross-file invariant ⇒ total_cycles ≥ 1
#check @Formal.TaskDecision.requiredVpc_antitone_in_confidence   -- confidence-monotone: threshold antitone in confidence
#check @Formal.TaskDecision.decision_pursue_confidence_monotone  -- confidence-monotone: PURSUE preserved by ↑confidence
#check @Formal.TaskDecision.decision_pursue_vpc_monotone         -- vpc-monotone: PURSUE preserved by ↑skill_up_vpc
-- WeightedRemaining required roles:
#check @Formal.WeightedRemaining.complete_imp_zero       -- complete ⇒ scalar 0 (unconditional)
#check @Formal.WeightedRemaining.zero_iff_complete_pos   -- positive-weight equivalence: scalar 0 ↔ complete
#check @Formal.WeightedRemaining.bug_teeth_witness       -- bug-teeth: zero-weight ⇒ equivalence fails (witness)
#check @Formal.WeightedRemaining.mono_head               -- monotone-nondecreasing in head fraction (weight ≥ 0)
#check @Formal.WeightedRemaining.nonneg                  -- non-negativity under all-non-negative inputs
-- LowYieldCancel required roles:
#check @Formal.LowYieldCancel.no_task_never_fires                              -- shell-safety: ¬hasTask ⇒ never fires
#check @Formal.LowYieldCancel.no_samples_blocks                                -- sample-gate: farm=0 ∨ alt=0 ⇒ never fires
#check @Formal.LowYieldCancel.fires_monotone_in_alt                            -- margin-monotone: ↑altXp preserves fire (positive currentXp, conf above gate)
#check @Formal.LowYieldCancel.zero_fast_path_fires_unconditionally             -- zero-fast-path: currentXp = 0 ∧ altXp > 0 ⇒ fires unconditionally
#check @Formal.LowYieldCancel.zero_fast_path_fires_with_low_confidence_witness -- zero-fast-path WITNESS (confidence < gate, alt_samples = 1)
#check @Formal.LowYieldCancel.positive_current_fires_implies_margin            -- soundness: positive currentXp ∧ fires ⇒ altXp ≥ currentXp * margin
#check @Formal.LowYieldCancel.positive_current_fires_implies_confidence        -- soundness: positive currentXp ∧ fires ⇒ confidence ≥ minConfidence
-- StrategyBlend required roles:
#check @Formal.StrategyBlend.balancingScaled_ge_min                -- band-lower: result ≥ balanceMinScaled (= 4 * 0.5 = 2)
#check @Formal.StrategyBlend.balancingScaled_le_max                -- band-upper: result ≤ balanceMaxScaled (= 4 * 2.0 = 8)
#check @Formal.StrategyBlend.balancingScaled_at_threshold          -- threshold-identity: leader-current = 2 ⇒ scaled result = 4 (= 4 * 1)
#check @Formal.StrategyBlend.balancingScaled_at_equal_clamps_to_min -- equal-clamp: leader = current ⇒ scaled result = balanceMinScaled
#check @Formal.StrategyBlend.balancingScaled_mono                  -- monotone: ↑(leader - current) never decreases the multiplier
#check @Formal.StrategyBlend.learnedBlend_w_zero                   -- warm-up identity: w = 0 ⇒ blend = value
#check @Formal.StrategyBlend.learnedBlend_w_one                    -- w = 1 ⇒ blend = normalized (far endpoint)
#check @Formal.StrategyBlend.learnedBlend_ge_value_when_le         -- convex-bound: value ≤ normalized ⇒ value ≤ blend
#check @Formal.StrategyBlend.learnedBlend_le_normalized_when_le    -- convex-bound: value ≤ normalized ⇒ blend ≤ normalized
#check @Formal.StrategyBlend.learnedBlend_ge_normalized_when_ge    -- convex-bound: normalized ≤ value ⇒ normalized ≤ blend
#check @Formal.StrategyBlend.learnedBlend_le_value_when_ge         -- convex-bound: normalized ≤ value ⇒ blend ≤ value
#check @Formal.StrategyBlend.learnedBlend_mono_normalized          -- monotone-normalized: ↑normalized never decreases the blend (w ≥ 0)
#check @Formal.StrategyBlend.learnedBlend_mono_value               -- monotone-value: ↑value never decreases the blend (w ≤ 1)
-- DecideKey required roles:
#check @Formal.DecideKey.decideCmp_trichotomy                      -- key-total-order: trichotomous
#check @Formal.DecideKey.decideCmp_swap                            -- key-total-order: antisymmetric (oriented)
#check @Formal.DecideKey.decideCmp_lt_trans                        -- key-total-order: transitive
#check @Formal.DecideKey.decideCmp_eq_imp_repr                     -- key-determinism: eq ⇒ equal rootRepr (final tiebreak)
#check @Formal.DecideKey.decideCmp_eq_imp_negFinal                 -- key-determinism: eq ⇒ equal negFinal
#check @Formal.DecideKey.decideCmp_eq_imp_effort                   -- key-determinism: eq ⇒ equal effort
#check @Formal.DecideKey.goalReprOfGuard_nonempty                  -- exhaustiveness: every GuardKind variant yields a non-empty repr (total dispatcher)
#check @Formal.DecideKey.goalReprOfMeans_nonempty                  -- exhaustiveness: every MeansKind variant yields a non-empty repr (total dispatcher)
-- CyclesForProgress required roles:
#check @Formal.CyclesForProgress.cyclesForProgressPure_eq_median_concat   -- contract: pure = median(strict ++ satisfy)
#check @Formal.CyclesForProgress.warmup_blocks                           -- warm-up gate: < W intervals ⇒ none
#check @Formal.CyclesForProgress.empty_none                              -- empty input ⇒ none
#check @Formal.CyclesForProgress.satisfyIntervals_pos                    -- positivity: every satisfy interval > 0 (the > 0 gate)
#check @Formal.CyclesForProgress.strictIntervals_pos                     -- positivity: every strict-increase interval > 0 (monotone cycleIndex)
#check @Formal.CyclesForProgress.allIntervals_pos                        -- positivity: every appended interval > 0 ⇒ median > 0 (seals or-15 fallback)
-- GatherApply required roles:
#check @Formal.GatherApply.is_applicable_imp_free_ge   -- is_applicable lower bound: passing check ⇒ at least k free slots
#check @Formal.GatherApply.apply_inventory_safe        -- per-step safety: is_applicable ∧ k ≥ 1 ⇒ post.used ≤ cap
#check @Formal.GatherApply.apply_inventory_safe_prod   -- per-step safety at MIN_FREE_SLOTS = 3
#check @Formal.GatherApply.applyN_used                 -- applyN bookkeeping: used' = used + n
#check @Formal.GatherApply.applyN_cap                  -- applyN bookkeeping: cap unchanged
#check @Formal.GatherApply.chain_safe                  -- chain safety: n ≤ free ⇒ n-step chain stays in cap
#check @Formal.GatherApply.chain_safe_min_free_witness -- non-vacuous witness at MIN_FREE_SLOTS
#check @Formal.GatherApply.is_applicable_boundary_witness     -- witness: applies at the boundary
#check @Formal.GatherApply.is_applicable_off_boundary_witness -- witness: fails one slot past
-- NpcBuyInventory required roles (REAL BUG #6: NpcBuyAction.apply overflows inventory_max):
#check @Formal.NpcBuyInventory.npc_buy_is_applicable_imp_free_ge -- passing check ⇒ quantity ≤ free
#check @Formal.NpcBuyInventory.npc_buy_is_applicable_imp_gold_ge -- passing check ⇒ price*quantity ≤ gold
#check @Formal.NpcBuyInventory.npc_buy_apply_inventory_safe      -- per-step safety: is_applicable ⇒ post.used ≤ cap
#check @Formal.NpcBuyInventory.applyN_used                       -- applyN bookkeeping: used' = used + qs.sum
#check @Formal.NpcBuyInventory.applyN_cap                        -- applyN bookkeeping: cap unchanged
#check @Formal.NpcBuyInventory.npc_buy_chain_safe                -- chain safety: qs.sum ≤ free ⇒ chain stays in cap
#check @Formal.NpcBuyInventory.boundary_quantity_eq_free_witness -- non-vacuous witness: quantity == free succeeds
#check @Formal.NpcBuyInventory.regression_used9_cap10_qty5_refused -- regression-pin: verified bug counterexample now refused
#check @Formal.NpcBuyInventory.chain_safe_boundary_witness        -- non-vacuous witness: 2-step chain at boundary
#check @Formal.NpcBuyInventory.gold_short_refused_witness         -- witness: gold gate failure
#check @Formal.NpcBuyInventory.gold_exact_min_accepted_witness    -- witness: gold at exact minimum accepted
-- ActionCostNonneg required roles:
#check @Formal.ActionCostNonneg.constantCost_nonneg          -- bucket 1: constant cost ≥ 0
#check @Formal.ActionCostNonneg.distanceCost_nonneg          -- bucket 2: base + dist ≥ 0
#check @Formal.ActionCostNonneg.qtyCost_nonneg               -- bucket 3: base + per_unit*qty + dist ≥ 0
#check @Formal.ActionCostNonneg.qtyCost_ge_per_unit          -- bucket 3: qty ≥ 1 ⇒ cost ≥ base + per_unit
#check @Formal.ActionCostNonneg.ratMax_ge_right              -- rate floor: max(rate, floor) ≥ floor
#check @Formal.ActionCostNonneg.ratMax_pos_of_right_pos      -- rate floor: floor > 0 ⇒ max > 0
#check @Formal.ActionCostNonneg.learnedFraction_nonneg       -- history fraction: learned/max(rate,floor) ≥ 0
#check @Formal.ActionCostNonneg.learnedCost_nonneg           -- bucket 5: full static-or-learned switch ≥ 0
#check @Formal.ActionCostNonneg.rateFloorProd_pos            -- production rate floor 1/10 > 0
#check @Formal.ActionCostNonneg.fight_cost_nonneg            -- Fight.cost ≥ 0
#check @Formal.ActionCostNonneg.gather_cost_nonneg           -- Gather.cost ≥ 0
#check @Formal.ActionCostNonneg.move_cost_nonneg             -- Move.cost ≥ 0
#check @Formal.ActionCostNonneg.delete_cost_nonneg           -- DeleteItemAction.cost_weight ≥ 0 (all branches)
#check @Formal.ActionCostNonneg.all_actions_cost_nonneg      -- headline: every concrete Action's cost ≥ 0 (seals PlannerAdmissibility)
-- RealizableLoadout required roles (the multi-slot pick_loadout bug fix):
#check @Formal.RealizableLoadout.isRealizable_iff_demand_le_ownership -- contract: realizability ⇔ per-code demand ≤ ownership
#check @Formal.RealizableLoadout.apply_cur_ge_1                        -- apply assert: realizable ⇒ cur ≥ 1 at every decrement
#check @Formal.RealizableLoadout.ownership_counts_equipped             -- per-slot +1: equipped copy contributes to ownership
#check @Formal.RealizableLoadout.regression_ring_pair_realizable       -- bug-witness: post-fix output for the ring1=A+ring2=B case is realizable
#check @Formal.RealizableLoadout.regression_buggy_output_not_realizable -- anti-witness: pre-fix output (both rings = B) is NOT realizable
#check @Formal.RealizableLoadout.empty_loadout_realizable               -- edge: empty loadout is vacuously realizable
#check @Formal.RealizableLoadout.isRealizable_mono_inv                  -- monotone: more inventory preserves realizability
-- ApplyBaseline required roles (REAL BUG #5: silent stat-baseline drop in Action.apply):
#check @Formal.ApplyBaseline.moveApply_preserves_baseline   -- apply-preserves-baseline-move
#check @Formal.ApplyBaseline.equipApply_preserves_baseline  -- apply-preserves-baseline-equip
#check @Formal.ApplyBaseline.claimApply_preserves_baseline  -- apply-preserves-baseline-claim
#check @Formal.ApplyBaseline.headline_preserves_baseline    -- headline-preserves-baseline (∀ modeled action)
#check @Formal.ApplyBaseline.preservesBaseline_refl         -- reflexivity (state preserves its own baseline)
#check @Formal.ApplyBaseline.preservesBaseline_trans        -- transitivity (composition of preserving steps)

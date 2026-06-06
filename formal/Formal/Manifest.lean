import Formal
import Formal.OwnedCount
import Formal.GearPolicy
import Formal.PurposeRouting
import Formal.CombatTargetExistence
import Formal.ActionApplicability
import Formal.StepDispatch
import Formal.LivenessChain
import Formal.RankingComposition
import Formal.PersonalityGrounding
import Formal.CycleInvariants
import Formal.MultiCycleLiveness
import Formal.NoActionDeadlock
import Formal.GuardCoverage
import Formal.ActionSetCompleteness
import Formal.EquipValueAugmented
import Formal.FallbackChain
import Formal.AcceptTaskGate
import Formal.TaskTradeReadyPriority
import Formal.WithdrawSetExpansion
import Formal.RecycleProtection
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
#check @cap_eq_max_of_five      -- ¬equipped ⇒ cap = max-of-five
#check @cap_eq_max_one_of_five  -- equipped ⇒ cap = max(1, max-of-five)
#check @equipped_ge_one         -- equipped ⇒ 1 ≤ cap
#check @recipe_cap_ge_safety    -- demand>0 ⇒ recipeCap ≥ SAFETY_FLOOR
#check @overstock_exact         -- overstock = qty-cap iff over, else 0
#check @overstock_pos_of_over   -- over ⇒ excess > 0
#check @overstock_zero_of_not_over -- ¬over ⇒ excess = 0
-- InventoryCaps predicate-level roles (component-value derivation):
#check @equipCap_zero_of_not_equippable -- ¬equippable ⇒ equippableCap = 0
#check @equipCap_zero_of_dominated      -- dominated ⇒ equippableCap = 0
#check @equipCap_eq_keep_of_undominated_equippable -- equippable ∧ ¬dominated ⇒ equippableCap = EQUIPPABLE_KEEP
#check @consumableCap_zero_of_not_healing -- hp_restore = 0 ⇒ consumableCap = 0
#check @consumableCap_eq_keep_of_healing  -- hp_restore > 0 ⇒ consumableCap = CONSUMABLE_KEEP
#check @equipCapFromPeers_dominated       -- dominator-owned ≥ slotCount ⇒ equippableCap = 0
#check @isDominatedBy_nil_of_positive_slot -- empty peer list, slot ≥ 1 ⇒ ¬dominated
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
-- Phase-15 disclosed-gap closure: full pick_loadout algorithm modeled.
#check @Formal.RealizableLoadout.pickLoadout_realizable                  -- Property 1: every pickLoadout output is realizable
#check @Formal.RealizableLoadout.pickSlotStep_no_downgrade               -- Property 2: per-slot swap never decreases score (modulo stolen-current branch)
#check @Formal.RealizableLoadout.pickSlotStep_optimal                    -- Property 3: per-slot choice is argmax of post-claim feasible candidates
#check @Formal.RealizableLoadout.pickLoadout_deterministic               -- Property 4: pure-function determinism (no dict iteration)
#check @Formal.RealizableLoadout.pickLoadout_extensional                 -- determinism: equal inputs ⇒ equal outputs
#check @Formal.RealizableLoadout.pickLoadout_ring_pair_regression        -- non-vacuity: literal ring-pair case yields realizable output
#check @Formal.RealizableLoadout.pickLoadout_cannot_produce_buggy_output -- anti-regression: bug output unreachable from algorithm
#check @Formal.RealizableLoadout.pickLoadout_empty                       -- edge: empty slots ⇒ empty loadout
#check @Formal.RealizableLoadout.pickLoadoutAux_claimSafe                -- helper: fold preserves claim safety
#check @Formal.RealizableLoadout.pickSlotStep_demand_delta               -- helper: each step claim delta is 0/1 per code
-- InventoryChainSafe required roles (REAL BUGS #7-#11: four chain_safe instantiations + TaskCancel coin):
#check @Formal.InventoryChainSafe.isApplicableK_imp_free_ge       -- template: passing precondition ⇒ k ≤ free
#check @Formal.InventoryChainSafe.applyK_inventory_safe           -- template: per-step safety
#check @Formal.InventoryChainSafe.applyKN_used                    -- template: chain bookkeeping (used' = used + sum)
#check @Formal.InventoryChainSafe.applyKN_cap                     -- template: chain bookkeeping (cap unchanged)
#check @Formal.InventoryChainSafe.chain_safe_template             -- template: chain safety (Σ ≤ free ⇒ stays in cap)
-- Withdraw role contracts:
#check @Formal.InventoryChainSafe.withdraw_is_applicable_imp_free_ge  -- passing check ⇒ quantity ≤ free
#check @Formal.InventoryChainSafe.withdraw_is_applicable_imp_bank_ge  -- passing check ⇒ quantity ≤ bankQty
#check @Formal.InventoryChainSafe.withdraw_apply_inventory_safe       -- per-step safety
#check @Formal.InventoryChainSafe.withdraw_chain_safe                 -- chain safety
#check @Formal.InventoryChainSafe.withdraw_boundary_quantity_eq_free_witness  -- boundary witness (quantity == free)
#check @Formal.InventoryChainSafe.withdraw_regression_used9_cap10_qty5_refused -- regression-pin: verified probe refused
-- Claim role contracts:
#check @Formal.InventoryChainSafe.claim_is_applicable_imp_free_ge  -- passing check ⇒ 1 ≤ free
#check @Formal.InventoryChainSafe.claim_apply_inventory_safe       -- per-step safety
#check @Formal.InventoryChainSafe.claim_chain_safe                 -- chain safety
#check @Formal.InventoryChainSafe.claim_boundary_witness           -- boundary witness (used = cap - 1)
#check @Formal.InventoryChainSafe.claim_regression_full_bag_refused -- regression-pin: full bag refused
#check @Formal.InventoryChainSafe.claim_no_pending_refused          -- shell-safety: no pending ⇒ refused
-- Unequip role contracts:
#check @Formal.InventoryChainSafe.unequip_is_applicable_imp_free_ge -- passing check ⇒ 1 ≤ free
#check @Formal.InventoryChainSafe.unequip_apply_inventory_safe      -- per-step safety
#check @Formal.InventoryChainSafe.unequip_chain_safe                -- chain safety
#check @Formal.InventoryChainSafe.unequip_boundary_witness          -- boundary witness
#check @Formal.InventoryChainSafe.unequip_regression_full_bag_refused -- regression-pin: full bag refused
#check @Formal.InventoryChainSafe.unequip_empty_slot_refused        -- shell-safety: empty slot ⇒ refused
-- TaskExchange role contracts:
#check @Formal.InventoryChainSafe.task_exchange_is_applicable_imp_free_ge  -- passing check ⇒ 1 ≤ free
#check @Formal.InventoryChainSafe.task_exchange_is_applicable_imp_coins_ge -- passing check ⇒ minCoins ≤ coins
#check @Formal.InventoryChainSafe.task_exchange_apply_inventory_safe       -- per-step safety
#check @Formal.InventoryChainSafe.task_exchange_chain_safe                 -- chain safety
#check @Formal.InventoryChainSafe.task_exchange_boundary_witness           -- boundary witness
#check @Formal.InventoryChainSafe.task_exchange_regression_full_bag_refused -- regression-pin
#check @Formal.InventoryChainSafe.task_exchange_coin_short_refused          -- shell-safety: coins short ⇒ refused
-- TaskCancel coin contracts (REAL BUG #11):
#check @Formal.InventoryChainSafe.task_cancel_is_applicable_imp_coin_ge -- passing check ⇒ coins ≥ 1
#check @Formal.InventoryChainSafe.task_cancel_apply_coin_eq_pre_minus_one -- apply decrements by exactly 1
#check @Formal.InventoryChainSafe.task_cancel_apply_strictly_decreases  -- strict decrement under precondition
#check @Formal.InventoryChainSafe.task_cancel_applyN_coin               -- chain bookkeeping
#check @Formal.InventoryChainSafe.task_cancel_chain_coin_safe           -- chain safety (n ≤ coins)
#check @Formal.InventoryChainSafe.task_cancel_boundary_witness          -- boundary witness (coins=1 ⇒ post=0)
#check @Formal.InventoryChainSafe.task_cancel_no_coin_refused           -- regression-pin: no coin ⇒ refused
#check @Formal.InventoryChainSafe.task_cancel_no_task_refused           -- shell-safety: no task ⇒ refused
-- Phase7Invariants required roles (Phase-7 batch: A, D, E):
#check @Formal.Phase7Invariants.baseValue_nonpos_zero
#check @Formal.Phase7Invariants.baseValue_pos_ge_one
#check @Formal.Phase7Invariants.baseValue_nonneg
#check @Formal.Phase7Invariants.baseValue_total
#check @Formal.Phase7Invariants.baseValue_total_needed_zero_returns_zero
#check @Formal.Phase7Invariants.baseValue_total_needed_neg_returns_zero
#check @Formal.Phase7Invariants.isApplicable_imp_slot_in_table
#check @Formal.Phase7Invariants.isApplicable_imp_inv_pos
#check @Formal.Phase7Invariants.isApplicable_imp_level_ge
#check @Formal.Phase7Invariants.isApplicable_slot_mismatch_refused
#check @Formal.Phase7Invariants.isApplicable_no_stats_refused
#check @Formal.Phase7Invariants.isApplicable_boundary_witness
#check @Formal.Phase7Invariants.isApplicable_ring_into_helmet_refused
#check @Formal.Phase7Invariants.inventoryUsed_nonneg
#check @Formal.Phase7Invariants.inventoryUsed_eq_sum
#check @Formal.Phase7Invariants.inventoryFree_eq_diff
#check @Formal.Phase7Invariants.inventoryFree_plus_used_eq_max
#check @Formal.Phase7Invariants.hpPercent_maxhp_zero
#check @Formal.Phase7Invariants.hpPercent_maxhp_pos
#check @Formal.Phase7Invariants.hpPercent_nonneg
#check @Formal.Phase7Invariants.inventoryUsed_empty
#check @Formal.Phase7Invariants.inventoryFree_empty
#check @Formal.Phase7Invariants.inventoryFree_at_full_is_zero
#check @Formal.Phase7Invariants.hpPercent_max_hp_zero_witness
-- GameDataAccessors required roles (Phase-9 REAL BUG #16: silent monster-stat defaults):
#check @Formal.GameDataAccessors.accessor_some_iff_present       -- post-fix contract: present ↔ some
#check @Formal.GameDataAccessors.accessor_none_iff_absent        -- post-fix contract: absent ↔ none
#check @Formal.GameDataAccessors.accessor_some_value             -- post-fix: returned value is the stored value
#check @Formal.GameDataAccessors.silentDefault_absent_returns_default -- pre-fix bug: absent ⇒ default (masks raise)
#check @Formal.GameDataAccessors.silentDefault_present_returns_value  -- pre-fix bug: present ⇒ value (bug latent)
#check @Formal.GameDataAccessors.predictWinLite_buggy_unknown_returns_true -- LOAD-BEARING bug counterexample
#check @Formal.GameDataAccessors.accessor_unknown_returns_none   -- post-fix anchors the bug fix
#check @Formal.GameDataAccessors.accessor_present_witness        -- boundary: present returns value
#check @Formal.GameDataAccessors.accessor_absent_witness         -- boundary: absent returns none
#check @Formal.GameDataAccessors.silentDefault_absent_witness    -- boundary: silent default = default on absent
#check @Formal.GameDataAccessors.silentDefault_present_witness   -- boundary: silent default = value on present
#check @Formal.GameDataAccessors.monsterLevelProbe_absent_returns_zero -- monster_level retains silent zero (probe)
#check @Formal.GameDataAccessors.monsterLevelProbe_present_returns_value -- monster_level retains stored value
-- StoreWarmup required roles (Phase-7 Target F: LearningStore warmup gates):
#check @Formal.StoreWarmup.warmupGatedMedian_below_gate
#check @Formal.StoreWarmup.warmupGatedMedian_at_or_above_gate
#check @Formal.StoreWarmup.warmupGatedMedian_boundary_witness
#check @Formal.StoreWarmup.warmupGatedMedian_off_boundary_refused
#check @Formal.StoreWarmup.warmupGatedMedian_empty_refused
#check @Formal.StoreWarmup.warmupGatedSuccessRate_below_gate
#check @Formal.StoreWarmup.warmupGatedSuccessRate_at_or_above_gate
#check @Formal.StoreWarmup.warmupGatedSuccessRate_nonneg
#check @Formal.StoreWarmup.warmupGatedSuccessRate_boundary_all_ok
#check @Formal.StoreWarmup.warmupGatedSuccessRate_boundary_none_ok
#check @Formal.StoreWarmup.warmupGatedSuccessRate_off_boundary_default
#check @Formal.StoreWarmup.warmupGatedSuccessRate_empty_default
-- ApplyBaseline required roles (REAL BUG #5: silent stat-baseline drop in Action.apply).
-- Phase-14: disclosed gap closed — all 24 concrete Action.apply methods modeled.
#check @Formal.ApplyBaseline.moveApply_preserves_baseline             -- Family 1: position-only
#check @Formal.ApplyBaseline.moveSemanticApply_preserves_baseline
#check @Formal.ApplyBaseline.mapTransitionApply_preserves_baseline
#check @Formal.ApplyBaseline.gatherApply_preserves_baseline           -- Family 2: inventory-mint
#check @Formal.ApplyBaseline.npcBuyApply_preserves_baseline
#check @Formal.ApplyBaseline.withdrawGoldApply_preserves_baseline
#check @Formal.ApplyBaseline.withdrawItemApply_preserves_baseline
#check @Formal.ApplyBaseline.claimApply_preserves_baseline
#check @Formal.ApplyBaseline.craftApply_preserves_baseline            -- Family 3: inventory-consume
#check @Formal.ApplyBaseline.recycleApply_preserves_baseline
#check @Formal.ApplyBaseline.npcSellApply_preserves_baseline
#check @Formal.ApplyBaseline.depositGoldApply_preserves_baseline
#check @Formal.ApplyBaseline.depositAllApply_preserves_baseline
#check @Formal.ApplyBaseline.useConsumableApply_preserves_baseline
#check @Formal.ApplyBaseline.deleteApply_preserves_baseline
#check @Formal.ApplyBaseline.equipApply_preserves_baseline            -- Family 4: equipment-swap
#check @Formal.ApplyBaseline.unequipApply_preserves_baseline
#check @Formal.ApplyBaseline.optimizeLoadoutApply_preserves_baseline
#check @Formal.ApplyBaseline.acceptTaskApply_preserves_baseline       -- Family 5: task transition
#check @Formal.ApplyBaseline.completeTaskApply_preserves_baseline
#check @Formal.ApplyBaseline.taskCancelApply_preserves_baseline
#check @Formal.ApplyBaseline.taskExchangeApply_preserves_baseline
#check @Formal.ApplyBaseline.taskTradeApply_preserves_baseline
#check @Formal.ApplyBaseline.restApply_preserves_baseline             -- Family 6: misc
#check @Formal.ApplyBaseline.buyBankExpansionApply_preserves_baseline
#check @Formal.ApplyBaseline.fightApply_preserves_baseline            -- Family 7: fight
#check @Formal.ApplyBaseline.all_actions_preserve_baseline  -- Phase-14 HEADLINE: ∀ 24 actions
#check @Formal.ApplyBaseline.headline_preserves_baseline    -- backwards-compat alias
#check @Formal.ApplyBaseline.preservesBaseline_refl         -- reflexivity
#check @Formal.ApplyBaseline.preservesBaseline_trans        -- transitivity
#check @Formal.ApplyBaseline.move_mutates_only_declared_fields           -- mutates-only contracts
#check @Formal.ApplyBaseline.rest_mutates_only_declared_fields
#check @Formal.ApplyBaseline.buyBankExpansion_mutates_only_declared_fields
#check @Formal.ApplyBaseline.equip_mutates_only_declared_fields
#check @Formal.ApplyBaseline.claim_mutates_only_declared_fields
#check @Formal.ApplyBaseline.fight_mutates_only_declared_fields
-- Phase8Invariants Target B — Bank expansion projection (REAL BUG #15):
#check @Formal.Phase8Invariants.bank_expansion_apply_increments_capacity  -- apply +SLOTS
#check @Formal.Phase8Invariants.buyBankExpansion_capacityN                -- N-step bookkeeping
#check @Formal.Phase8Invariants.bank_expansion_chain_reaches_satisfied    -- the bug fix
#check @Formal.Phase8Invariants.bank_expansion_post_fix_witness           -- 30-cap witness (1 apply → satisfied)
#check @Formal.Phase8Invariants.bank_expansion_pre_fix_projection_gap     -- regression anchor (pre-fix is the bug)
#check @Formal.Phase8Invariants.bank_expansion_pre_fix_gap_witness        -- regression anchor (BLOCKED counterexample pinned)
-- CheapestPath required roles (Phase 12 Target A — greedy contract, NOT-A-BUG):
#check @Formal.CheapestPath.cheapest_target_met               -- target ≤ current ⇒ empty plan
#check @Formal.CheapestPath.stepLevel_empty                    -- empty monsters ⇒ no step
#check @Formal.CheapestPath.pickBest_nil                       -- pickBest on [] = none
#check @Formal.CheapestPath.pickBest_mem                       -- returned monster is in input
#check @Formal.CheapestPath.pickBest_beatable                  -- returned monster passes +1 gate
#check @Formal.CheapestPath.pickBest_max                       -- greedy maximality (xpPerCycle)
#check @Formal.CheapestPath.isBeatable_plus_one                -- +1 margin matches FightAction
#check @Formal.CheapestPath.isBeatable_off_boundary            -- simLevel+2 NOT beatable
#check @Formal.CheapestPath.isBeatable_level_zero              -- level-0 NOT beatable
#check @Formal.CheapestPath.cheapest_empty_monsters_blocks     -- empty input ⇒ blocked
#check @Formal.CheapestPath.stepLevel_all_zero_blocks          -- all-zero xpPerCycle ⇒ none
#check @Formal.CheapestPath.foldMax_ge_init                    -- helper: result ≥ initial
#check @Formal.CheapestPath.foldMax_ge_mem                     -- helper: result ≥ every member
#check @Formal.CheapestPath.foldMax_mem                        -- helper: result ∈ list
#check @Formal.CheapestPath.tie_break_first_wins_witness       -- tie ⇒ first picked
#check @Formal.CheapestPath.strict_greater_replaces_witness    -- strict > ⇒ later replaces
#check @Formal.CheapestPath.greedy_filters_unbeatable_witness  -- unbeatable filtered out
#check @Formal.CheapestPath.single_step_witness                -- 1-level success
#check @Formal.CheapestPath.two_step_witness                   -- 2-level chain
#check @Formal.CheapestPath.greedy_pick_witness                -- picks higher xpPerCycle
-- GoalValueBands required roles (Phase-17 — scalar_yield wired into discretionary goal value()):
#check @Formal.GoalValueBands.pursueTask_floor_le_ceiling           -- band sanity: 35 ≤ 50
#check @Formal.GoalValueBands.gatherMaterials_floor_le_ceiling      -- band sanity: 1 ≤ 50
#check @Formal.GoalValueBands.pursueTask_ceiling_lt_survival        -- band sanity: 50 < 70
#check @Formal.GoalValueBands.gatherMaterials_ceiling_lt_survival   -- band sanity: 50 < 70
#check @Formal.GoalValueBands.pursueTask_value_below_survival_floor -- HEADLINE: PursueTask < 70 ∀ bonus
#check @Formal.GoalValueBands.gatherMaterials_value_below_survival_floor -- HEADLINE: GatherMaterials < 70 ∀ bonus
#check @Formal.GoalValueBands.pursueTask_value_in_band              -- floor ≤ result ≤ ceiling
#check @Formal.GoalValueBands.gatherMaterials_value_in_band         -- floor ≤ result ≤ ceiling
#check @Formal.GoalValueBands.clampIntoBand_mono_bonus              -- monotone in bonus (lemma)
#check @Formal.GoalValueBands.pursueTask_value_monotone_in_bonus    -- ↑bonus ⇒ value no less
#check @Formal.GoalValueBands.gatherMaterials_value_monotone_in_bonus -- ↑bonus ⇒ value no less
#check @Formal.GoalValueBands.pursueTask_cold_eq_floor              -- cold (bonus=0) = floor (35)
#check @Formal.GoalValueBands.gatherMaterials_cold_eq_floor         -- cold (bonus=0) = floor (1)
-- Phase 18 GoalSystem required roles:
#check @Formal.GoalSystem.acceptTask_value_in_range
#check @Formal.GoalSystem.acceptTask_cold_returns_zero
#check @Formal.GoalSystem.claimPending_value_in_range
#check @Formal.GoalSystem.claimPending_cold_returns_zero
#check @Formal.GoalSystem.taskExchange_value_in_range
#check @Formal.GoalSystem.taskExchange_cold_returns_zero
#check @Formal.GoalSystem.taskCancel_value_in_range
#check @Formal.GoalSystem.taskCancel_cold_satisfied_zero
#check @Formal.GoalSystem.taskCancel_cold_no_pivot_zero
#check @Formal.GoalSystem.levelSkill_value_in_range
#check @Formal.GoalSystem.levelSkill_cold_satisfied_zero
#check @Formal.GoalSystem.levelSkill_cold_gap_too_big_zero
#check @Formal.GoalSystem.levelSkill_cold_no_craftable_zero
#check @Formal.GoalSystem.expandBank_value_in_range
#check @Formal.GoalSystem.expandBank_cold_not_accessible_zero
#check @Formal.GoalSystem.expandBank_cold_satisfied_zero
#check @Formal.GoalSystem.completeTask_value_in_range
#check @Formal.GoalSystem.completeTask_cold_satisfied_zero
#check @Formal.GoalSystem.completeTask_cold_not_full_zero
#check @Formal.GoalSystem.reachUnlockLevel_value_in_range
#check @Formal.GoalSystem.reachUnlockLevel_cold_satisfied_zero
#check @Formal.GoalSystem.reachUnlockLevel_cold_zero_target
#check @Formal.GoalSystem.reachUnlockLevel_cold_gap_too_big
#check @Formal.GoalSystem.lowYieldCancel_value_in_range
#check @Formal.GoalSystem.lowYieldCancel_cold_returns_zero
#check @Formal.GoalSystem.unlockBank_value_in_range
#check @Formal.GoalSystem.unlockBank_cold_not_locked_zero
#check @Formal.GoalSystem.unlockBank_cold_xp_exceeded_zero
#check @Formal.GoalSystem.unlockBank_cold_unreachable_zero
#check @Formal.GoalSystem.discardOverstock_value_in_range
#check @Formal.GoalSystem.discardOverstock_cold_satisfied_zero
#check @Formal.GoalSystem.discardOverstock_unsatisfied_at_least_40
#check @Formal.GoalSystem.upgradeEquipment_value_in_range
#check @Formal.GoalSystem.upgradeEquipment_cold_no_upgrade_zero
#check @Formal.GoalSystem.upgradeEquipment_base_eq_35
#check @Formal.GoalSystem.upgradeEquipment_relevant_eq_51
#check @Formal.GoalSystem.restoreHp_value_in_range
#check @Formal.GoalSystem.restoreHp_full_returns_zero
#check @Formal.GoalSystem.restoreHp_critical_is_110
#check @Formal.GoalSystem.depositInventory_value_in_range
#check @Formal.GoalSystem.depositInventory_cold_inaccessible_zero
#check @Formal.GoalSystem.depositInventory_cold_below_ramp_zero
#check @Formal.GoalSystem.sellInventory_value_in_range
#check @Formal.GoalSystem.sellInventory_cold_satisfied_zero
#check @Formal.GoalSystem.sellInventory_cold_inv_max_zero
#check @Formal.GoalSystem.sellInventory_cold_not_sellable_zero


-- GearPolicy (Phase G1 of composition-correctness plan):
#check @Formal.GearPolicy.armor_score_nonneg                         -- AScore ≥ 0 under nonneg data
#check @Formal.GearPolicy.armor_weakly_dominates_empty_slot          -- any armor ≥ empty baseline
#check @Formal.GearPolicy.armor_strictly_dominates_empty_slot        -- nontrivial armor > empty
#check @Formal.GearPolicy.armor_score_mono_in_resistance             -- AScore monotone in resistance
#check @Formal.GearPolicy.pickSlot_empty_returns_some                -- empty slot + candidates ⇒ pick fills

-- PurposeRouting (Phase G2):
#check @Formal.PurposeRouting.combatScore_strict_of_strict_wscore       -- strict WScore order preserved
#check @Formal.PurposeRouting.combatScore_tiebreaks_nontool_over_tool   -- WScore tie ⇒ non-tool wins
#check @Formal.PurposeRouting.combat_picks_nontool_over_tied_tool       -- argmax over [tool,nontool] = nontool on tie
#check @Formal.PurposeRouting.pickGatherSlot_score_optimal              -- gather pick = argmin gatherScore
#check @Formal.PurposeRouting.argminBy_le                               -- argmin is lower bound
#check @Formal.PurposeRouting.argminBy_mem                              -- argmin is in input

-- CombatTargetExistence (Phase G3):
#check @Formal.CombatTargetExistence.pickWinnable_some_of_exists
#check @Formal.CombatTargetExistence.pickBest_some_of_acc_some
#check @Formal.CombatTargetExistence.pickBest_none_iff_acc_none_and_none_winnable
#check @Formal.CombatTargetExistence.winnableFarmTarget_task_override
#check @Formal.CombatTargetExistence.winnableFarmTarget_falls_through_no_task

-- ActionApplicability (Phase G4):
#check @Formal.ActionApplicability.fightApplicable_false_of_no_locations
#check @Formal.ActionApplicability.fightApplicable_false_of_no_inv_room
#check @Formal.ActionApplicability.fightApplicable_false_of_low_hp
#check @Formal.ActionApplicability.fightApplicable_false_of_underleveled_monster
#check @Formal.ActionApplicability.fightApplicable_false_of_overleveled_monster
#check @Formal.ActionApplicability.fightApplicable_false_of_undergear
#check @Formal.ActionApplicability.fightApplicable_mono_in_hp
#check @Formal.ActionApplicability.fightApplicable_false_under_level_window
#check @Formal.ActionApplicability.winnable_does_not_imply_applicable
#check @Formal.ActionApplicability.restApplicable_iff_subfull
#check @Formal.ActionApplicability.equipApplicable_iff

-- StepDispatch (Phase G5):
#check @Formal.StepDispatch.stepDispatch_total
#check @Formal.StepDispatch.stepDispatch_deterministic
#check @Formal.StepDispatch.dispatch_obtain_equippable_goes_to_upgrade
#check @Formal.StepDispatch.dispatch_obtain_nonequippable_goes_to_gather
#check @Formal.StepDispatch.dispatch_reach_skill_goes_to_level_skill
#check @Formal.StepDispatch.dispatch_reach_char_with_target_goes_to_grind
#check @Formal.StepDispatch.dispatch_reach_char_no_target_safe_fails
#check @Formal.StepDispatch.obtain_only_routes_to_obtain_classes
#check @Formal.StepDispatch.reach_skill_only_routes_to_level_skill
#check @Formal.StepDispatch.reach_char_only_routes_to_grind

-- LivenessChain (Phase G6 capstone):
#check @Formal.LivenessChain.chain_emits_fight_when_target_exists_and_applicable
#check @Formal.LivenessChain.chain_none_implies_picker_or_applicability_blocked

-- RankingComposition (G1→ranker bridge):
#check @Formal.RankingComposition.value_zero_of_base_zero
#check @Formal.RankingComposition.value_zero_of_marginal_zero
#check @Formal.RankingComposition.value_zero_of_balancing_zero
#check @Formal.RankingComposition.value_strict_of_strict_marginal
#check @Formal.RankingComposition.value_mono_in_marginal
#check @Formal.RankingComposition.armor_root_outranks_empty_baseline
#check @Formal.RankingComposition.unique_positive_marginal_dominates

-- PersonalityGrounding (discharges G1→ranker hypothesis under BalancedPersonality):
#check @Formal.PersonalityGrounding.balanced_pos
#check @Formal.PersonalityGrounding.balanced_armor_outranks_empty_unconditional
#check @Formal.PersonalityGrounding.balanced_gear_armor_strictly_outranks_empty

-- CycleInvariants (per-cycle Player loop):
#check @Formal.CycleInvariants.cycle_executes_exactly_one
#check @Formal.CycleInvariants.fight_strictly_raises_xp_when_positive
#check @Formal.CycleInvariants.rest_raises_hp_when_subfull
#check @Formal.CycleInvariants.consumable_raises_hp_when_useful
#check @Formal.CycleInvariants.xp_monotone_under_well_formed

-- MultiCycleLiveness (bounded reach across cycles):
#check @Formal.MultiCycleLiveness.xp_monotone_over_sequence
#check @Formal.MultiCycleLiveness.nFights_all_well_formed
#check @Formal.MultiCycleLiveness.multi_fight_raises_xp_by_at_least
#check @Formal.MultiCycleLiveness.bounded_fights_suffice_for_xp_delta

-- NoActionDeadlock (AI never freezes):
#check @Formal.NoActionDeadlock.at_least_wait_applicable
#check @Formal.NoActionDeadlock.progress_available_when_any_capability
#check @Formal.NoActionDeadlock.select_action_total
#check @Formal.NoActionDeadlock.select_action_deterministic
#check @Formal.NoActionDeadlock.progress_or_rest_when_capable
#check @Formal.NoActionDeadlock.ai_always_acts

-- GuardCoverage (every stuck state triggers a guard):
#check @Formal.GuardCoverage.low_hp_triggers_critical
#check @Formal.GuardCoverage.critical_inv_with_overstock_triggers_discard
#check @Formal.GuardCoverage.high_inv_with_bank_triggers_deposit
#check @Formal.GuardCoverage.rest_for_combat_triggers_when_needed
#check @Formal.GuardCoverage.firstGuard_nonzero_when_low_hp
#check @Formal.GuardCoverage.stuck_state_always_guarded

-- ActionSetCompleteness (every capability has an action):
#check @Formal.ActionSetCompleteness.capability_mapping_total
#check @Formal.ActionSetCompleteness.capability_mapping_deterministic
#check @Formal.ActionSetCompleteness.every_action_has_a_capability

-- EquipValueAugmented (recent runtime fix proof):
#check @Formal.EquipValueAugmented.equipValue_strict_of_strict_raw
#check @Formal.EquipValueAugmented.equipValue_tiebreaks_nontool_over_tool
#check @Formal.EquipValueAugmented.rawSum_mono_in_attack
#check @Formal.EquipValueAugmented.rawSum_mono_in_resistance
#check @Formal.EquipValueAugmented.rawSum_mono_in_hpBonus
#check @Formal.EquipValueAugmented.rawSum_mono_in_crit
#check @Formal.EquipValueAugmented.rawSum_mono_in_dmg
#check @Formal.EquipValueAugmented.equipValue_nontool_zero_eq_one
#check @Formal.EquipValueAugmented.equipValue_tool_zero_eq_zero
#check @Formal.EquipValueAugmented.copper_dagger_strictly_outranks_fishing_net

-- FallbackChain (two-pass arbiter walk proof):
#check @Formal.FallbackChain.walk_some_of_nonNone_exists
#check @Formal.FallbackChain.walk_picks_upgrade_when_present
#check @Formal.FallbackChain.walk_deterministic
#check @Formal.FallbackChain.passOne_first_match
#check @Formal.FallbackChain.trace_122752_walk_picks_equip

-- AcceptTaskGate (defer-AcceptTask while gear chain has work, fix proof):
#check @Formal.AcceptTaskGate.fires_total
#check @Formal.AcceptTaskGate.fires_deterministic
#check @Formal.AcceptTaskGate.fires_false_when_active_task
#check @Formal.AcceptTaskGate.entry_defers_when_owned_not_equipped
#check @Formal.AcceptTaskGate.entry_defers_when_craftable
#check @Formal.AcceptTaskGate.fires_false_when_owned_unequipped_gear_exists
#check @Formal.AcceptTaskGate.fires_false_when_craftable_gear_exists
#check @Formal.AcceptTaskGate.entry_does_not_defer_when_equipped
#check @Formal.AcceptTaskGate.entry_does_not_defer_when_unowned_uncraftable

-- TaskTradeReadyPriority (trade-ready fallback suppression proof):
#check @Formal.TaskTradeReadyPriority.suppress_total
#check @Formal.TaskTradeReadyPriority.suppress_deterministic
#check @Formal.TaskTradeReadyPriority.hasPursueTask_true_of_mem
#check @Formal.TaskTradeReadyPriority.suppress_true_when_all_conditions_hold
#check @Formal.TaskTradeReadyPriority.suppress_false_when_no_pursue
#check @Formal.TaskTradeReadyPriority.suppress_false_when_not_items
#check @Formal.TaskTradeReadyPriority.suppress_false_when_inv_zero
#check @Formal.TaskTradeReadyPriority.suppress_false_when_step_not_gather_taskcode
#check @Formal.TaskTradeReadyPriority.trace_144020_suppress

-- WithdrawSetExpansion (recipe-closure withdraw fix proof):
#check @Formal.WithdrawSetExpansion.closureStep_terminates
#check @Formal.WithdrawSetExpansion.closureStep_zero_fuel
#check @Formal.WithdrawSetExpansion.closureStep_empty_work
#check @Formal.WithdrawSetExpansion.hasCode_append_right
#check @Formal.WithdrawSetExpansion.perCraftQty_none_of_no_recipe
#check @Formal.WithdrawSetExpansion.perCraftQty_some_when_in_recipe
#check @Formal.WithdrawSetExpansion.trace_copper_chain_per_craft

-- RecycleProtection (target_gear / target_tools exclusion proof):
#check @Formal.RecycleProtection.protected_contains_target_gear
#check @Formal.RecycleProtection.protected_contains_target_tools
#check @Formal.RecycleProtection.protected_excluded_from_recycle
#check @Formal.RecycleProtection.unprotected_craftable_in_recycle
#check @Formal.RecycleProtection.recycle_subset_when_protection_grows
#check @Formal.RecycleProtection.trace_copper_dagger_excluded
#check @Formal.RecycleProtection.trace_copper_axe_excluded
#check @Formal.RecycleProtection.trace_off_target_kept

-- PlannerDepthBound (planner never returns a plan longer than max_depth ⇒ a
-- depth-based pre-plan skip is sound; copper_boots @ max_depth 15 is the bug):
#check @Formal.PlannerDepthBound.reachable_planLen_eq_depth
#check @Formal.PlannerDepthBound.reachable_depth_le_maxDepth
#check @Formal.PlannerDepthBound.plan_length_le_max_depth
#check @Formal.PlannerDepthBound.reachable_not_satisfying_when_lb_exceeds_depth
#check @Formal.PlannerDepthBound.copper_boots_unreachable_under_upgrade_depth

-- TieredSelection (StrategyArbiter two-pass walk: cheap pass, escalate to full,
-- else Wait; the per-cycle no-plan memo elides re-planning soundly):
#check @Formal.TieredSelection.cheap_winner_is_first_cheaply_plannable
#check @Formal.TieredSelection.escalation_iff_no_cheap
#check @Formal.TieredSelection.wait_only_when_no_full
#check @Formal.TieredSelection.memo_skip_sound

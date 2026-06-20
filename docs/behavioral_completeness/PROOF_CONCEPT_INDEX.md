# Proof → concept index (generated — do not hand-edit)

Inverse of the MATRIX proof-coverage column. Regenerate with
`uv run python scripts/gen_proof_concept_index.py`. A module with no
concept tag, or a concept with no module, is a traceability gap.

| Module | Concepts | Properties |
|---|---|---|
| AcceptTaskGate | tasks, items | safety, totality |
| ActionApplicability | combat, characters | safety, monotonicity |
| ActionCostNonneg | core, planner | safety |
| ActionSetCompleteness | core | totality |
| ApplyBaseline | core | safety |
| ArbiterSelect | core, planner | dominance, totality |
| BankExpansionTiming | bank | dominance, monotonicity, totality, safety |
| BankSelection | bank, items, crafting | safety |
| BuySourceVenue | grandexchange | dominance, totality, safety, monotonicity |
| CheapestPath | combat, monsters | reachability, dominance |
| CombatTargetExistence | combat, monsters | reachability, safety |
| ConsumableSelection | items | dominance, monotonicity, totality, safety |
| CraftVsBuy | crafting, npcs | dominance, monotonicity, totality, safety |
| CycleInvariants | characters, combat | safety, monotonicity |
| CyclesForProgress | characters | reachability, monotonicity |
| DecideKey | core, planner | dominance, totality |
| DoomedMemo | core, planner | monotonicity, safety, reachability |
| EquipValueAugmented | items, characters | dominance, monotonicity |
| EventWindow | events | totality, safety, dominance, monotonicity, reachability |
| FallbackChain | core, planner | totality, dominance |
| GameDataAccessors | core | safety |
| GatherApply | resources, items | safety |
| GatherSelection | resources | dominance, monotonicity, totality, reachability |
| GearLatch | items, characters | safety, monotonicity |
| GearPolicy | items, characters | dominance, safety |
| GoalSystem | core, planner | safety |
| GoalValueBands | core, planner | safety, monotonicity |
| GrindLadder | crafting, planner | liveness, safety |
| GuardCoverage | core | no-deadlock, safety |
| InventoryChainSafe | bank, items | safety |
| InventoryProfile | bank, items, crafting | safety |
| LiquidationVenue | grandexchange | dominance, totality, safety, monotonicity |
| Liveness.GatedArming | liveness, planner | liveness |
| Liveness.ItemsTaskRun | tasks | safety, totality, reachability |
| Liveness.ItemsTaskTermination | tasks, crafting, bank | safety, totality |
| Liveness.StickySelect | liveness, planner | liveness, safety |
| Liveness.ZombieFreedom | liveness, planner | liveness |
| LivenessChain | combat, monsters | reachability, no-deadlock |
| LowYieldCancel | tasks | safety, monotonicity |
| MonsterDropApply | combat, planner | liveness, safety |
| MonsterDropSelection | monsters | dominance, monotonicity, totality, reachability |
| MultiCycleLiveness | characters, combat | reachability, monotonicity |
| NearestTile | maps | safety, dominance, totality, monotonicity |
| NoActionDeadlock | core | no-deadlock, totality |
| NpcBuyInventory | npcs, items | safety |
| Objective | crafting, items, characters | reachability, dominance |
| OwnedCount | items | safety, monotonicity |
| PersonalityGrounding | characters, items | dominance |
| Phase7Invariants | items, core | safety |
| Phase8Invariants | items, crafting, bank | safety, reachability |
| PlanModel | planner, plan, action | monotonicity, safety |
| PlannerAdmissibility | planner, core | dominance |
| PlannerDepthBound | planner, core | safety, reachability |
| PrerequisiteGraph | crafting, items | safety, totality |
| PriorityBand | core, planner | safety |
| ProgressionReserve | core, economy | deduction-accounting, monotonicity |
| PurposeRouting | items, characters | dominance |
| RankingComposition | core, planner | dominance, monotonicity |
| RealizableLoadout | items, characters | safety |
| RecycleProtection | items, crafting | safety |
| Scalarizer | core | monotonicity |
| ServableFilter | core, planner | safety, totality |
| ShoppingList | resources | dominance, monotonicity, safety, totality |
| SkillGateFastFail | core, planner | safety, totality |
| SkillGrindSelection | crafting, planner | safety, totality |
| SkillStepDispatch | crafting, planner | safety, liveness |
| SkillTargetCurve | crafting, planner | safety, monotonicity |
| StepDispatch | core, planner | totality, safety, reachability |
| StoreWarmup | core | safety |
| StrategyBlend | core, planner | monotonicity, safety |
| StrategyTraversal | crafting, planner | reachability, totality |
| StuckDetector | core | safety |
| TaskDecision | tasks | dominance, monotonicity |
| TaskFeasibility | tasks, crafting | reachability, safety |
| TaskReservation | tasks, crafting, items | safety |
| TaskTradeReadyPriority | tasks | safety, totality |
| TieredSelection | core, planner | totality, dominance |
| UpgradeSelection | items, characters | dominance |
| WeightedRemaining | tasks, characters | monotonicity, safety |
| WithdrawSetExpansion | crafting, items | totality, safety |

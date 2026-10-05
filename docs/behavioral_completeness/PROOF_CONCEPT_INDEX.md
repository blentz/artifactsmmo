# Proof → concept index (generated — do not hand-edit)

Inverse of the MATRIX proof-coverage column. Regenerate with
`uv run python scripts/gen_proof_concept_index.py`. A module with no
concept tag, or a concept with no module, is a traceability gap.

| Module | Concepts | Properties |
|---|---|---|
| AcceptTaskGate | tasks, items | safety, totality |
| AccumulationSell | inventory, selling | safety, monotonicity |
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
| CommittedLoop | core, planner | termination, sufficiency |
| CompleteTaskIncome | core, tasks | monotonicity |
| ConsumableSelection | items | dominance, monotonicity, totality, safety |
| CraftVsBuy | crafting, npcs | dominance, monotonicity, totality, safety |
| CurrencyAffordFastFail | core, planner | safety, totality |
| CycleInvariants | characters, combat | safety, monotonicity |
| CyclesForProgress | characters | reachability, monotonicity |
| DecideKey | core, planner | totality |
| Decompose | core, planner | validity, sufficiency, safety, termination |
| DecomposeWitness | core, planner | sufficiency, validity |
| DisposalRoute | inventory | dominance, safety, totality, liveness |
| DominancePareto | equipment, selling | safety |
| EquipValueAugmented | items, characters | dominance, monotonicity |
| EquipmentProfile | equipment-profile | safety, validity, totality |
| EquipmentScoring | items, gear | validity, dominance |
| EscrowConservation | grandexchange | conservation, liveness |
| EventWindow | events | totality, safety, dominance, monotonicity, reachability |
| Extracted.Bridges | core | validity |
| FallbackChain | core, planner | totality, dominance |
| GameDataAccessors | core | safety |
| GatherApply | resources, items | safety |
| GatherCost | planner, action, cost | monotonicity, safety |
| GatherSelection | resources | dominance, monotonicity, totality, reachability |
| GePostPricing | grandexchange, undercut | fail-closed, dominance, boundedness |
| GearPolicy | items, characters | dominance, safety |
| GearTaxonomy | core, gear | validity, monotonicity, safety |
| GearValue | items, gear | validity, dominance |
| GoalSystem | core, planner | safety |
| GoalValueBands | core, planner | safety, monotonicity |
| GuardCoverage | core | no-deadlock, safety |
| InventoryChainSafe | bank, items | safety |
| InventoryKeep | inventory, characters | safety, liveness |
| InventoryProfile | bank, items, crafting | safety |
| InventoryRoom | inventory, slot-room | safety |
| LeafAttainable | core, planner | validity, monotonicity |
| LiquidationVenue | grandexchange | dominance, totality, safety, monotonicity |
| Liveness.CurrencyFunding | liveness, tasks | termination, sufficiency |
| Liveness.GearBuildTermination | liveness, planner | liveness |
| Liveness.GrindCycles | liveness | termination, sufficiency |
| Liveness.ItemsTaskRun | tasks | safety, totality, reachability |
| Liveness.ItemsTaskTermination | tasks, crafting, bank | safety, totality |
| LivenessChain | combat, monsters | reachability, no-deadlock |
| LoadoutProfiles | gear | validity, monotonicity, totality, safety |
| LowYieldCancel | tasks | safety, monotonicity |
| MonsterDropApply | combat, planner | liveness, safety |
| MonsterDropSelection | monsters | dominance, monotonicity, totality, reachability |
| MultiCycleLiveness | characters, combat | reachability, monotonicity |
| NearestTile | maps | safety, dominance, totality, monotonicity |
| NoActionDeadlock | core | no-deadlock, totality |
| NpcBuyInventory | npcs, items | safety |
| Objective | crafting, items, characters | reachability, dominance |
| ObjectiveStepFight | liveness | safety, liveness, validity |
| ObtainModelReady | core, planner | validity, sufficiency, safety |
| OptimalBuyMix | potion-supply-economics | validity, safety |
| OwnedCount | items | safety, monotonicity |
| Phase10GoalLattices | core, planner | boundedness, dominance, reachability |
| Phase7Invariants | items, core | safety |
| Phase8Invariants | items, crafting, bank | safety, reachability |
| PlanModel | planner, plan, action | monotonicity, safety |
| PlannerAdmissibility | planner, core | dominance |
| PlannerDepthBound | planner, core | safety, reachability |
| PotionProvisionQty | combat-survivability | validity, safety |
| PrerequisiteGraph | crafting, items | safety, totality |
| PriorityBand | core, planner | safety |
| ProgressionReserve | core, economy | deduction-accounting, monotonicity |
| ProgressionTree | progression | safety, totality, dominance |
| PurposeRouting | items, characters | dominance |
| RealizableLoadout | items, characters | safety |
| RecycleProtection | items, crafting | safety |
| RefusalFact | core, planner | safety, reachability |
| Scalarizer | core | monotonicity |
| ShoppingList | resources | dominance, monotonicity, safety, totality |
| SkillGrindSelection | crafting, planner | safety, totality |
| SkillXpPositive | crafting, gathering, planner | safety |
| StepDispatch | core, planner | totality, safety, reachability |
| StoreWarmup | core | safety |
| StrategicValue | items, characters | safety, monotonicity |
| StrategyTraversal | crafting, planner | reachability, totality |
| StuckDetector | core | safety |
| Synergy | synergy | safety, boundedness |
| TaskDecision | tasks | dominance, monotonicity |
| TaskFeasibility | tasks, crafting | reachability, safety |
| TaskReservation | tasks, crafting, items | safety |
| TaskTradeReadyPriority | tasks | safety, totality |
| UpgradeSelection | items, characters | dominance |
| WinnableCascade | combat, monsters | dominance, totality |
| WithdrawSetExpansion | crafting, items | totality, safety |
| XpPositive | combat, planner | safety |
| XpValue | combat, planner | safety |

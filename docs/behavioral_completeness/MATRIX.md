# Behavioral Completeness Matrix

Column legend:
- **Player → concept**: actions the player can take that interact with this concept (openapi paths)
- **Concept → player**: what the concept returns/grants to the player (schema/docs)
- **Strategic uses**: why/when to engage this concept during a run (cited)
- **Opportunity cost × tier**: cost-vs-benefit across content tiers (cited to content_tiers.md)
- **Behavior coverage**: which goals/means/guards currently handle this concept (cited to source path)
- **Proof coverage**: theorems + property classes backing this concept (cited to PROOF_CONCEPT_INDEX)
- **Gap + policy**: gap classification (MISSING/THIN/UNPROVEN/WRONG-POLICY/IGNORE) + deliberate policy (cited to synthesis)

---

### tasks
- **Player → concept**: accept/complete/cancel/exchange (openapi /my/{name}/action/task/*)
- **Concept → player**: gold, tasks_coin, items, XP (docs: tasks)
- **Strategic uses**: steady gold + coin economy (docs)
- **Opportunity cost × tier**: T1 cheap; competes with gear gather (content_tiers.md)
- **Behavior coverage**: PursueTask/AcceptTask/CompleteTask/TaskExchange (tiers/means.py)
- **Proof coverage**: ItemsTaskRun [safety, totality, reachability — over the inventory-COUPLED trade model; `trade` consumes one held item to advance one unit of progress; `held_accounts` proves the whole run consumes EXACTLY the obtained items (no free progress)] + ItemsTaskTermination keepSet/batchK [safety, totality] + TaskCompleteReachable [reachability, over the collapsed trade model] + TaskFeasibility [reachability, safety] + AcceptTaskGate [totality, safety] + TaskTradeReadyPriority [safety, totality] + WeightedRemaining [monotonicity, safety] + LowYieldCancel [safety, monotonicity] + TaskDecision [dominance, monotonicity] (PROOF_CONCEPT_INDEX)
- **Gap + policy**: UNPROVEN (PARTIAL → near-closed) — act; END-TO-END termination is now PROVEN over the inventory-COUPLED ItemsTaskRun model: `trade` REQUIRES and CONSUMES one held task item to advance progress (faithful to the API taskTrade), `obtain_then_trades_reach` reaches progress=total via obtain (total-progress) then that many trades, and `held_accounts` certifies the run consumes EXACTLY the obtained items (closing the rejected capstone's free-progress hole — the shared-liveness collapsed-trade concern is SUPERSEDED for the termination story). Per-decision conformance also proven: keep-set protects the task item's transitive recipe inputs (ItemsTaskTermination + live `test_bank_selection_diff`) and batch ≥ 1, ≤ remaining (ItemsTaskTermination + live `test_task_batch_diff`); trade-chain reaches complete (TaskCompleteReachable). NOT yet an unqualified CLOSED: ItemsTaskRun is a faithful ABSTRACT model — the LIVE PursueTask planner-path is not differentially tied to ItemsTaskRun (no oracle/mirror; that would be a model-vs-model test with no production target, hence theater under the no-sham rule). Remaining tie = a live-path differential coupling the real obtain→deposit→taskTrade cycle to ItemsTaskRun's held/progress accounting. The live conformance that IS landed is the keep-set/batch differential, which is the inventory-feasibility precondition ItemsTaskRun's `obtain` abstracts (synthesis)

### characters
- **Player → concept**: create/delete/select active character, read sheet (openapi /characters/create, /characters/delete, /characters/active, /my/characters)
- **Concept → player**: level, XP, HP, skill levels, inventory, gold, equipped slots — the whole agent state (CharacterSchema)
- **Strategic uses**: the character sheet is the single source of truth for every gating decision (level/HP/skill) the bot makes each cycle (openapi schema CharacterSchema)
- **Opportunity cost × tier**: at every tier the sheet is read free each cycle; mis-reading HP/level is what makes T1→T6 progression stall, so the cost of NOT modeling it is total (content_tiers.md)
- **Behavior coverage**: GrindCharacterXP, ReachUnlockLevel, RestoreHP, plus all task/skill goals read the sheet (goals/grind_character_xp.py, tiers/guards.py)
- **Proof coverage**: CycleInvariants/CyclesForProgress/MultiCycleLiveness/WeightedRemaining [safety, reachability, monotonicity] (PROOF_CONCEPT_INDEX)
- **Gap + policy**: CLOSED (by existing coverage) — single-character next-action/skill coherence is proven downstream: per-cycle coherence + bounded progress by CycleInvariants/MultiCycleLiveness/CyclesForProgress/ActionApplicability/WeightedRemaining, and which-step/skill-to-advance by StrategyTraversal/ArbiterSelect/RankingComposition (skill target is a deterministic min() clamp on the chosen objective step, not an independent ranking). The bot makes no standalone single-char decision to prove; only multi-char roster (create/delete/select) is unmodeled and is explicitly accepted/out-of-scope (synthesis)

### maps
- **Player → concept**: read map grid, find tiles by content/coords (openapi /maps, /maps/{layer}/{x}/{y}, /maps/id/{map_id})
- **Concept → player**: tile coordinates + content (monster/resource/workshop/bank/npc spawn) used to route movement (MapSchema)
- **Strategic uses**: maps are the spatial index every gather/fight/craft action must resolve a destination against before moving (openapi schema MapSchema)
- **Opportunity cost × tier**: free lookup at all tiers; T1 content is clustered near spawn so path cost is low, higher tiers (T4-T6) are farther so pathing/movement cost rises (content_tiers.md)
- **Behavior coverage**: every action embeds a semantic MoveTo to its content tile; nearest-tile resolution is the shared ai/nearest_tile.py primitive used by gathering/combat/movement_semantic and by MoveTo.apply+execute (actions/movement_semantic.py, ai/nearest_tile.py)
- **Proof coverage**: NearestTile [safety, dominance, totality, monotonicity] — Manhattan-nearest lex-(manhattan,x,y) pick: winner is a real tile, distance ≤ all, deterministic lex-min (closes the MoveTo apply/execute divergence), cost = 6 + dist monotone so the pick IS GatherSelection's trusted distance input (PROOF_CONCEPT_INDEX). NOTE: this is the maps proof; CheapestPath is combat-XP path cost, NOT tile routing — do not cite it here.
- **Gap + policy**: CLOSED for single-layer/no-obstacle/single-hop tile routing — Manhattan-nearest IS least-cost on the live movement model and is now proven + differential-locked (NearestTile). Honest limit: cross-layer A* / obstacle traversal stays out of scope (utils/pathfinding.py is CLI-only, deliberately unproven) (synthesis)

### monsters
- **Player → concept**: read monster catalog/stats; engage indirectly via fight (openapi /monsters, /monsters/{code}, /my/{name}/action/fight)
- **Concept → player**: drops (items at drop rates), combat XP, gold; level/element stats gate winnability (MonsterSchema, DropRateSchema)
- **Strategic uses**: monsters are the primary XP + drop source and must be filtered by winnable level before targeting (openapi schema MonsterSchema)
- **Opportunity cost × tier**: T1 chicken/cow give cheap safe XP; higher-tier monsters (T4 demon, T6 sandwhisper_empress) give better drops but risk loss without gear/level (content_tiers.md)
- **Behavior coverage**: GrindCharacterXP, ReachUnlockLevel target monsters; winnability filters in tiers/guards.py (goals/grind_character_xp.py)
- **Proof coverage**: CombatTargetExistence/CheapestPath/LivenessChain [reachability, safety, dominance] (PROOF_CONCEPT_INDEX)
- **Gap + policy**: UNPROVEN (DEFERRED, multi-session) — drop-driven monster selection (pick the monster minimizing expected kills = rate/avg_qty for a needed drop) is a real GatherSelection-shaped decision, but it is currently DEAD relative to the bot: monster-drops are NOT a producible source (tiers/strategy._producible + prerequisite_graph treat them as non-producible leaves), so no FightAction is emitted to obtain a drop item. An honest close needs (a) restoring min_quantity into _monster_drops (dropped at load) and (b) wiring monster-drops as producible + a FightAction-narrowing call site — then the proven core. Landing a proven-but-inert core alone would mislabel CLOSED; tracked as multi-session (synthesis)

### combat
- **Player → concept**: initiate a fight at the character's tile; simulate a fight (openapi /my/{name}/action/fight, /simulation/fight_simulation)
- **Concept → player**: win/loss outcome, HP delta, XP, gold, drops; loss costs HP and a cooldown with no reward (CharacterFightSchema, CombatResultSchema)
- **Strategic uses**: combat converts the best-on-hand loadout into XP/drops only when the fight is winnable; engage when is_winnable holds (openapi schema CharacterFightSchema)
- **Opportunity cost × tier**: T1 fights are low-risk free XP; at T4-T6 a mis-judged fight wastes a full cooldown and HP, so winnability gating cost dominates (content_tiers.md)
- **Behavior coverage**: GrindCharacterXP/ReachUnlockLevel drive fights; is_winnable gate + RestoreHP recovery (tiers/guards.py, goals/restore_hp.py)
- **Proof coverage**: ActionApplicability/CombatTargetExistence/LivenessChain [safety, reachability, dominance] + RealizableLoadout/EquipmentScoring/PurposeRouting [dominance, monotonicity, totality, safety] (PROOF_CONCEPT_INDEX)
- **Gap + policy**: CLOSED — act; the loadout-swap-before-fight DECISION (best on-hand loadout pre-fight) is already proven — RealizableLoadout.pickLoadout_optimal/no_downgrade/realizable + EquipmentScoring + PurposeRouting (the THIN tag was stale, an audit under-citation); the cost-ordering that sequences swap-before-fight is pinned by ActionCostNonneg + unit tests (lifting the k≥2 ordering lemmas to Lean is an optional deferred refinement) (synthesis)

### resources
- **Player → concept**: read resource catalog; gather at the character's tile (openapi /resources, /resources/{code}, /my/{name}/action/gathering)
- **Concept → player**: raw materials (ore/wood/fish/fiber) at drop rates + gathering-skill XP; gated by skill level (ResourceSchema, DropRateSchema)
- **Strategic uses**: resources are the feedstock for all crafting and the main gathering-skill XP source; gather to satisfy recipe inputs (openapi schema ResourceSchema)
- **Opportunity cost × tier**: T1 copper/ash gathers are fast and feed early gear; higher-tier nodes (T5 mithril, T6 adamantite) need skill level investment first (content_tiers.md)
- **Behavior coverage**: yield-optimal multi-source narrowing in GatherMaterialsGoal.relevant_actions via select_gather_source (goals/gathering.py, gather_selection.py)
- **Proof coverage**: GatherSelection [dominance, monotonicity, totality, reachability] + GatherApply [safety] (PROOF_CONCEPT_INDEX)
- **Gap + policy**: CLOSED — act: gather the yield-optimal source; four proof classes satisfied (synthesis)

### items
- **Player → concept**: read item catalog; equip/unequip, deposit/withdraw/give, buy/sell via npc & ge (openapi /items, /items/{code}, /my/{name}/action/bank/*/item, /my/{name}/action/give/item)
- **Concept → player**: stat effects when equipped, recipe inputs, sale value, task/quest material — items are the universal value currency (ItemSchema)
- **Strategic uses**: items are equipped for combat stats, consumed in recipes, or sold for gold; gear upgrades unlock harder content (openapi schema ItemSchema)
- **Opportunity cost × tier**: T1 copper gear is cheap and immediately equippable; each tier's gear (T3 steel, T5 mithril, T6 adamantite) costs proportionally more inputs but enables the next monster band (content_tiers.md)
- **Behavior coverage**: UpgradeEquipmentGoal (value selection in upgrade_selection.py), SellInventory, DepositInventory, DiscardOverstock all act on items (goals/progression.py, goals/upgrade_selection.py)
- **Proof coverage**: OwnedCount/EquipValueAugmented/GearLatch/GearPolicy/UpgradeSelection/RecycleProtection [safety, dominance, monotonicity] + ConsumableSelection [dominance, monotonicity, totality, safety] (PROOF_CONCEPT_INDEX)
- **Gap + policy**: THIN — act; items are heavily covered for gear/recipe but item give/transfer between characters is unmodeled and accepted (synthesis)

### crafting
- **Player → concept**: craft an item from its recipe at the matching workshop tile (openapi /my/{name}/action/crafting)
- **Concept → player**: produces the crafted item + crafting-skill XP; consumes recipe inputs from inventory (ItemSchema craft field)
- **Strategic uses**: crafting is how raw materials become gear/consumables and the only path to most equipment; craft when inputs + skill level + workshop are satisfied (openapi schema ItemSchema)
- **Opportunity cost × tier**: T1 copper_bar/boots craft cheaply; deeper recipe chains (T4 obsidian, T6 adamantite) need multi-step intermediate crafts so planner depth/cost climbs each tier (content_tiers.md)
- **Behavior coverage**: CraftRelief, UpgradeEquipment, LevelSkill, PursueTask drive crafting via prerequisite graph (goals/craft_relief.py, tiers/means.py); craft-vs-buy injects NpcBuyAction into GatherMaterials.relevant_actions when cheaper+affordable (craft_vs_buy.py, goals/gathering.py)
- **Proof coverage**: PrerequisiteGraph/WithdrawSetExpansion/RecycleProtection/StrategyTraversal/Phase8Invariants [safety, totality, reachability] (PROOF_CONCEPT_INDEX); CraftVsBuy [dominance, monotonicity, totality, safety] + NpcBuyInventory [safety] (PROOF_CONCEPT_INDEX)
- **Gap + policy**: CLOSED — act: buy when strictly fewer cooldowns and affordable above the gold reserve, else craft; four classes proven (synthesis)

### bank
- **Player → concept**: read bank, deposit/withdraw gold & items, buy bank expansion (openapi /my/bank, /my/{name}/action/bank/deposit/*, /my/{name}/action/bank/withdraw/*, /my/{name}/action/bank/buy_expansion)
- **Concept → player**: shared overflow storage; protects materials from inventory-full loss and frees inventory slots (BankSchema)
- **Strategic uses**: bank is the keep-set-protected store that prevents DEPOSIT_FULL from banking task/recipe inputs and freezing progress; deposit when inventory pressured (openapi schema BankSchema)
- **Opportunity cost × tier**: at all tiers banking is near-free; the cost is the keep-set policy — banking a needed recipe input stalls PursueTask, so the trade is correctness not gold (content_tiers.md)
- **Behavior coverage**: DepositInventory, ExpandBank, UnlockBank, withdraw means; keep-set in tiers/means.py (goals/deposit_inventory.py, goals/expand_bank.py)
- **Proof coverage**: BankSelection/InventoryChainSafe/Phase8Invariants [safety, reachability] + BankExpansionTiming [dominance, monotonicity, totality, safety] (PROOF_CONCEPT_INDEX)
- **Gap + policy**: CLOSED — deposit/withdraw/keep-set proven; expansion-purchase timing now proven (BankExpansionTiming: exact rational fill threshold via cross-multiply ∧ reserve-safe gold floor, closing the gold-drain SAFETY hole) (synthesis)

### npcs
- **Player → concept**: read npc catalog/items; buy from and sell to an npc at its tile (openapi /npcs/details, /npcs/items, /my/{name}/action/npc/buy, /my/{name}/action/npc/sell)
- **Concept → player**: a fixed-price buyer/seller for specific items — converts surplus items to gold and gold to specific items (NPCSchema)
- **Strategic uses**: npcs are the reliable gold sink/source; sell only items that have a buyer npc, buy recipe inputs not worth gathering (openapi schema NPCSchema)
- **Opportunity cost × tier**: T1 surplus (slimeballs, ore) sells for steady gold; at higher tiers npc sell value lags gear cost so gold is better spent than hoarded (content_tiers.md)
- **Behavior coverage**: SellInventory + _has_sellable buyer-npc check; npc means in tiers/means.py (goals/sell_inventory.py, tiers/means.py)
- **Proof coverage**: NpcBuyInventory [safety] + CraftVsBuy [dominance, monotonicity, totality, safety] (PROOF_CONCEPT_INDEX)
- **Gap + policy**: CLOSED — act; buy-vs-gather for a raw NPC-sold material IS the raw-item instance of cheaper_acquisition (craft_cooldowns = min_gathers gather count, crafts=0), already proven in CraftVsBuy and wired via GatherMaterials.relevant_actions + strategy_driver; the operational min_gathers→units coupling (gather count = realized units) is the same multi-session follow-up as the taskTrade-inventory coupling (synthesis)

### events
- **Player → concept**: read event catalog + active/spawned events (openapi /events, /events/active, /events/spawn)
- **Concept → player**: timed spawns of special maps/monsters/merchant-npcs that grant otherwise-unavailable trades/drops while active (ActiveEventSchema, EventContentSchema)
- **Strategic uses**: events are timed windows — gold-merchant NPCs and rare content appear only while an event is live, so gate npc-trade on the active event not a static map scan (openapi schema ActiveEventSchema)
- **Opportunity cost × tier**: events are tier-spanning; cost is opportunistic — diverting to a live merchant event is cheap if reachable, worthless if expired (content_tiers.md)
- **Behavior coverage**: SellInventory checks is_event_npc + event_npc_tradeable against active_events (goals/sell_inventory.py)
- **Proof coverage**: EventWindow [totality, safety, dominance, monotonicity, reachability] (PROOF_CONCEPT_INDEX)
- **Gap + policy**: CLOSED — act; event-merchant trade-window gate is wired AND proven (EventWindow: non-event always tradeable, inactive/unreachable refused, exact window-open firing condition, monotone in remaining + antitone in distance, reachable firing witness); event-spawned combat/resource content remains out of scope (future work) (synthesis)

### effects
- **Player → concept**: read the effect catalog (openapi /effects, /effects/{code})
- **Concept → player**: named stat modifiers/buffs that items, consumables and monsters reference (e.g. heal, boost, attack element) (EffectSchema)
- **Strategic uses**: effects describe what consumables/gear do (heal, elemental boost) and could inform potion/loadout choice, but are presently only consumed indirectly via item stats (openapi schema EffectSchema)
- **Opportunity cost × tier**: low at every tier; ignoring the effect catalog directly costs nothing while combat stays winnable, but T4+ elemental-resist potions could raise win margins (content_tiers.md)
- **Behavior coverage**: none — effects are read transitively through item stats, no goal/means targets the effect concept (none)
- **Proof coverage**: none (PROOF_CONCEPT_INDEX)
- **Gap + policy**: IGNORE — ignore-with-reason; item-stat handling already captures combat-relevant effects; a standalone effect model adds no current journey value (synthesis)

### grandexchange
- **Player → concept**: read orders/history; create buy/sell orders, buy/fill/cancel (openapi /grandexchange/orders, /my/grandexchange/orders, /my/{name}/action/grandexchange/create-buy-order, /my/{name}/action/grandexchange/create-sell-order, /my/{name}/action/grandexchange/buy, /my/{name}/action/grandexchange/cancel)
- **Concept → player**: a player-driven market — sell surplus above npc price, buy scarce recipe inputs to skip long gathers (GEOrderSchema)
- **Strategic uses**: the GE is the high-value market alternative to npc trade; use it to liquidate rare drops and source bottleneck inputs faster than gathering (openapi schema GEOrderSchema)
- **Opportunity cost × tier**: low value at T1 (gather is fast); rises at T4-T6 where rare drops fetch high gold and scarce inputs (mithril, adamantite) are slow to gather (content_tiers.md)
- **Behavior coverage**: none — no goal/means/guard touches grandexchange (none)
- **Proof coverage**: none (PROOF_CONCEPT_INDEX)
- **Gap + policy**: MISSING (DEFERRED, multi-session) — the GE IS in the current API but has ZERO order-book ingestion in game_data; an honest close is the immediate-fill liquidation decision (sell into an existing fillable buy order vs NPC, an Option-gated dominance proof), which requires plumbing /grandexchange/orders into game_data FIRST. A posted-price dominance proof would be a tasks-style sham (posted price ≠ realized proceeds; an unposted order may never fill). Tracked as a two-session effort (order-book ingestion → liquidation_venue + LiquidationVenue.lean); not a single-session decision core (synthesis)

### achievements
- **Player → concept**: read account/character achievement progress (openapi /achievements, /achievements/{code}, /accounts/{account}/achievements)
- **Concept → player**: progress trackers that grant rewards (gold/items) on milestone completion; mostly a passive byproduct of play (AchievementSchema, AchievementRewardsSchema)
- **Strategic uses**: achievements reward activities the bot already does (kill/gather/craft counts), so they accrue passively; rarely worth steering toward directly (openapi schema AchievementSchema)
- **Opportunity cost × tier**: near-zero cost at all tiers since they track existing activity; deliberately chasing a specific achievement would divert from tier progression for marginal reward (content_tiers.md)
- **Behavior coverage**: ClaimPending claims pending rewards (which include achievement payouts) but does not steer toward achievements (goals/claim_pending.py)
- **Proof coverage**: none (PROOF_CONCEPT_INDEX)
- **Gap + policy**: IGNORE — ignore-with-reason; passive accrual + ClaimPending already captures the reward, active pursuit has negative leverage (synthesis)

### badges
- **Player → concept**: read the badge catalog (openapi /badges, /badges/{code})
- **Concept → player**: cosmetic/status markers earned via achievements/events; no mechanical effect on character stats or progression (BadgeSchema)
- **Strategic uses**: badges are status cosmetics with no gameplay payoff, so there is no strategic reason to engage them for a progression-focused bot (openapi schema BadgeSchema)
- **Opportunity cost × tier**: zero benefit at every tier; any time spent pursuing badges is pure opportunity cost against progression (content_tiers.md)
- **Behavior coverage**: none (none)
- **Proof coverage**: none (PROOF_CONCEPT_INDEX)
- **Gap + policy**: IGNORE — ignore-with-reason; no mechanical reward, intentionally out of scope (synthesis)

### leaderboard
- **Player → concept**: read account/character leaderboard rankings (openapi /leaderboard/accounts, /leaderboard/characters)
- **Concept → player**: read-only competitive ranking by level/skill/gold; informational, grants nothing to the character (no reward schema — read-only ranking)
- **Strategic uses**: the leaderboard is a read-only scoreboard; it informs how the run compares but offers no action or reward to engage with (openapi schema — read-only, no action path)
- **Opportunity cost × tier**: zero at all tiers — purely informational, no in-game cost or benefit to reading or ignoring it (content_tiers.md)
- **Behavior coverage**: none (none)
- **Proof coverage**: none (PROOF_CONCEPT_INDEX)
- **Gap + policy**: IGNORE — ignore-with-reason; read-only with no reward, nothing to act on (synthesis)

### simulation
- **Player → concept**: run a fight simulation for a character-vs-monster matchup (openapi /simulation/fight_simulation)
- **Concept → player**: predicted combat outcome (win/loss, HP/turns) without spending a real action or cooldown (CombatSimulationDataSchema)
- **Strategic uses**: simulation lets the bot test winnability before committing a real fight, avoiding wasted cooldowns on unwinnable monsters (openapi schema CombatSimulationDataSchema)
- **Opportunity cost × tier**: cheap at all tiers; most valuable at T4-T6 where a wasted real fight costs a long cooldown, but the local is_winnable model already substitutes for it (content_tiers.md)
- **Behavior coverage**: none — winnability is computed locally (ai/combat.is_winnable) rather than via the server simulation endpoint (none)
- **Proof coverage**: none in the Manifest index; the local winnability decision is covered by ActionApplicability/CombatTargetExistence instead (PROOF_CONCEPT_INDEX)
- **Gap + policy**: IGNORE — ignore-with-reason; the local winnability model replaces the network simulation call, so the endpoint is deliberately unused (synthesis)

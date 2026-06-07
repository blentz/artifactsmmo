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
- **Proof coverage**: TaskDecision.req_none_pursues [dominance] (PROOF_CONCEPT_INDEX)
- **Gap + policy**: UNPROVEN — act; prove reachability (synthesis)

### characters

### maps

### monsters

### combat

### resources

### items

### crafting

### bank

### npcs

### events

### effects

### grandexchange

### achievements

### badges

### leaderboard

### simulation

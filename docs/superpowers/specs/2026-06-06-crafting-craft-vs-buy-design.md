# Design: Crafting — Craft-vs-Buy Acquisition Decision (Phase 2, gap #2)

Date: 2026-06-06
Status: Approved (brainstorming) — pending implementation plan
Program: behavioral-completeness (`docs/behavioral_completeness/`), backlog rank 1
(crafting, UNPROVEN, score 27).

## Goal

Close the `crafting` gap (MATRIX: UNPROVEN — "workshop-routing + craft-vs-buy
remains heuristic"). Workshop routing is trivial (one workshop per skill), so this
spec adds and proves the **craft-vs-buy decision**: for a needed item an NPC
sells, decide whether to BUY it (gold) or CRAFT it (gather + craft cooldowns),
choosing the non-dominated method, and prove that decision over all inputs against
the program's four property classes. Today the bot only ever crafts; buying a
needed item is an unconsidered behavior.

## Success criterion

- Behavior: when a recipe-closure item is NPC-sold and buying is strictly fewer
  cooldowns AND affordable above a gold reserve, the bot buys it; otherwise it
  crafts. Single-method (craft-only) items unchanged.
- Proof: the decision satisfies dominance, monotonicity, totality, and safety
  (reserve never violated); reachability reused (`NpcBuyInventory` for BUY, the
  existing recipe-chain reachability for CRAFT).
- The `crafting` MATRIX row's proof-coverage lists the new classes; the
  `test_matrix_complete` gate stays green; `BACKLOG.md` re-ranks crafting closed.

## Non-goals (YAGNI)

- Gold↔time conversion / learned gold-value (gold is a hard reserve constraint,
  not converted into the cooldown metric).
- Workshop-routing optimization (one workshop per skill — no choice).
- Buying gear the bot would not otherwise craft (only recipe-closure items that an
  acquisition path already needs are candidates).
- Grand Exchange buying (separate concept/gap; this is NPC-stock buying only).
- Selling-side changes (SellInventory/DiscardOverstock unchanged).

## Architecture

The optimization metric is **cooldowns**; **gold** is a hard constraint via a
reserve floor, never converted. The proven decision core gates *whether the buy
alternative is offered*; the existing least-cost planner
(`PlannerAdmissibility` — proven optimal) does the final per-item pick. They agree
by construction (buy is offered only when its cooldown cost is strictly lower, so
the least-cost planner selects it).

### 1. Constant + affordability

`GOLD_RESERVE` (module constant, tunable) — gold kept for essentials (e.g. bank
expansion). For a needed item:
- `total_price = needed_qty * cheapest_npc_sell_price(item)` (from
  `GameData.npcs_selling_item(item) -> [(npc, price)]`, min price).
- **affordable** ⇔ `state.gold - total_price >= GOLD_RESERVE`.

### 2. Cost models (integer cooldowns)

- `craft_cooldowns(item, needed, state, game_data)` = `min_gathers(item, needed,
  recipes, owned)` (the existing proven gather lower bound, reused) + the count of
  distinct craft steps in the recipe tree + Manhattan travel to the item's
  workshop. A lower bound — honest, not a float estimate.
- `buy_cooldowns(item, needed, state, game_data)` = Manhattan travel to the
  nearest selling NPC + the number of buy actions (`ceil(needed / max_per_buy)`,
  `>= 1`; `max_per_buy = needed` if no per-buy cap is known).

### 3. Pure decision core — `src/artifactsmmo_cli/ai/craft_vs_buy.py`

```python
class Method(Enum):
    CRAFT = "craft"
    BUY = "buy"

def cheaper_acquisition(
    craft_cooldowns: int, buy_cooldowns: int, total_price: int, gold: int, reserve: int
) -> Method:
    affordable = gold - total_price >= reserve
    return Method.BUY if (affordable and buy_cooldowns < craft_cooldowns) else Method.CRAFT
```

Pure (no I/O); the differential target. Mirrored core-only in
`formal/Formal/CraftVsBuy.lean` over `Nat` (`Int` for `gold - total_price` to
allow negative affordability). Theorems (role names):

- **Dominance** `buy_iff_affordable_and_strictly_cheaper`:
  `cheaperAcquisition ... = BUY ↔ (affordable ∧ buyCooldowns < craftCooldowns)`.
  Corollary `craft_when_not_strictly_cheaper`: `¬(buy < craft) → result = CRAFT`
  (never buy a dominated method) and `craft_when_unaffordable`.
- **Monotonicity** `buy_stable_under_more_gold` (raising `gold` never flips
  BUY→CRAFT) + `buy_stable_under_lower_buy_cooldowns` (lowering `buyCooldowns`
  never flips BUY→CRAFT) + `buy_stable_under_lower_price`.
- **Totality / no-deadlock** `acquisition_total`: returns a defined `Method` for
  all inputs (decidable; `BUY ∨ CRAFT`).
- **Safety** `buy_preserves_reserve`: `result = BUY → gold - total_price ≥ reserve`
  (post-buy gold never below the reserve floor).
- **Reachability** reused, not re-proved here: BUY reaches item-owned via
  `NpcBuyInventory` (+inventory-cap safety, already proven); CRAFT via the existing
  recipe-chain reachability (`PrerequisiteGraph`/`StrategyTraversal`).

Differential (oracle on `cheaperAcquisition` vs the Python core over random
inputs) + mutation + 100% coverage; register in `Manifest.lean`/`Contracts.lean`/
`Audit.lean`; header-tag `-- @concept: crafting, npcs @property: dominance,
monotonicity, totality, safety`.

### 4. Wiring

- **Data:** add `_npc_locations: dict[str, tuple[int, int]]` to `GameData`,
  populated in the NPC load alongside `_npc_stock`; accessor `npc_location(code)`.
  (`npcs_selling_item` already gives price.) If NPC tile location is not in the NPC
  schema, derive it from the maps load (NPCs sit on map tiles) — the load task
  resolves the exact source.
- **Impure adapter** `craft_vs_buy.acquisition_method(item, needed, state,
  game_data, reserve) -> Method`: assembles `total_price`, `buy_cooldowns`,
  `craft_cooldowns` from `GameData`, then calls the pure `cheaper_acquisition`. No
  decision logic of its own.
- **Integration point** — `GatherMaterialsGoal.relevant_actions` (the same seam as
  gather-selection): for each recipe-closure item that an NPC sells and for which
  `acquisition_method == BUY`, add an `NpcBuyAction(code=item,
  npc_location=...)` to the relevant set. `NpcBuyAction.is_applicable` is gated on
  `state.gold - price >= GOLD_RESERVE` (affordable above reserve) + a selling NPC
  exists; its `cost` is `buy_cooldowns`. CRAFT items (decision == CRAFT, or no
  selling NPC) are untouched, so single-method gathering/crafting is unchanged.
  Blast radius: one method + `NpcBuyAction` applicability/cost + the NPC-location
  field.

## Data flow

1. `GameData.load` → `_npc_locations` populated.
2. Per cycle, `GatherMaterialsGoal.relevant_actions` calls `acquisition_method`
   per recipe-closure NPC-sold item; injects `NpcBuyAction` for BUY items.
3. The least-cost planner picks buy-vs-make per item (buy offered only when
   strictly cheaper, so the planner selects it — consistent with the decision).
4. `NpcBuyAction.apply` mints the item + debits gold (existing `npc_buy_core`);
   `NpcBuyInventory` safety holds.

## Error handling

- Item with no selling NPC, or unaffordable → `acquisition_method` returns CRAFT;
  no buy action injected; existing behavior. Fail-open, never a crash.
- Unknown NPC location → that NPC is not a buy candidate (skip), not a fabricated
  location.
- `gold - total_price` modeled as `Int` so unaffordability (negative) is total; no
  `except Exception`; missing data → CRAFT.

## Testing

- TDD; `craft_vs_buy.py` at 100% (BUY and CRAFT branches). Pin the affordability
  boundary: `gold - total_price == reserve` IS affordable (`>=`), so with `buy <
  craft` it returns BUY; `gold - total_price == reserve - 1` is NOT affordable, so
  it returns CRAFT. Also pin the cooldown boundary `buy == craft` → CRAFT (strict
  `<` required for BUY).
- Differential: oracle on `cheaperAcquisition` (Lean) vs `cheaper_acquisition`
  (Python) over Hypothesis-random `(craft, buy, price, gold, reserve)` incl.
  affordability and cooldown ties. Mutation kills perturbations of the core.
- Unit: `acquisition_method` adapter (assembles inputs correctly, delegates);
  `relevant_actions` injects `NpcBuyAction` only for BUY+affordable NPC-sold items,
  leaves CRAFT/single-method untouched, fail-opens on missing NPC location.
- Integration smoke (offline fixture): a needed item cheap to buy + affordable →
  `NpcBuyAction` appears in relevant actions; expensive/unaffordable → it does not.

## Risks / open items

- **Cost-model fidelity:** `craft_cooldowns`/`buy_cooldowns` are integer estimates
  (lower bounds / Manhattan travel); the decision proves the comparison GIVEN the
  estimates, not that they equal the true in-game cost. Same honest boundary as
  resources' `avg_quantity`. Revisit the estimates if play data shows systematic
  mis-selection.
- **NPC location source:** if the NPC schema lacks coordinates, the maps load must
  supply them (NPCs occupy map tiles); the wiring task resolves the exact API path.
  If unavailable, `buy_cooldowns` falls back to a constant travel term and the
  decision still holds (a documented degradation, not a fabrication).
- **`GOLD_RESERVE` value:** a single tunable constant; start conservative (keep
  enough for a bank expansion) and revisit from play data. The proof is parametric
  in `reserve`, so changing it needs no re-proof.
- **Planner/decision consistency:** buy is offered only when strictly cheaper, so
  the least-cost planner's pick agrees with the decision by construction; if a
  future change makes `NpcBuyAction.cost` diverge from `buy_cooldowns`, that
  invariant breaks — the integration test pins `cost == buy_cooldowns`.

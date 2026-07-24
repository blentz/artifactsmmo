# Grand Exchange Order-Creation — Design

**Date:** 2026-07-24
**Status:** Approved (brainstorming), pending spec review
**Feature:** Let the AI planner POST its own Grand Exchange (GE) buy and sell orders, not just fill standing ones.

## Problem

The bot participates in the GE in one direction only: it **fills** standing orders.
It never **posts** its own. Consequences:

- **Sell side:** surplus inventory is dumped to NPC vendors at the sell-back floor, or
  sold into a standing GE *buy* order when one happens to pay more
  (`GeFillBuyOrderAction`, `actions/ge_fill.py:28`). If neither exists, value is lost to
  the NPC floor. The bot cannot list an item at market and wait for a better buyer.
- **Buy side:** materials are bought from NPC vendors or by filling a standing GE *sell*
  order (`GeFillSellOrderAction`, `actions/ge_fill_sell.py:31`). The bot cannot bid below
  the current ask and wait for a cheaper seller.

The order-creation endpoints exist in the generated client
(`action_ge_create_sell_order`, `action_ge_create_buy_order`) and are wired into the
manual CLI (`commands/trade.py`), but **no code under `ai/` ever calls them**.

The existing two-sided *fill* logic is deliberately non-speculative: every GE interaction
takes the *standing* order's price. The pure deciders `buy_source_venue.py` and
`liquidation_venue.py` (both Lean-proven) encode an explicit "anti-surrogate" guard: with
no fillable order to anchor on, they refuse to act rather than guess a price. This design
**extends** that discipline to posting — it does not abandon it.

## Scope

Both sides (buy + sell), one spec, a shared escrow/order-state core plus two symmetric
legs. Decomposition into separate specs is a fallback only if implementation bloats.

Out of scope (explicit non-goals):
- Speculative pricing with no live market anchor (empty-book posting). Fail closed instead.
- Learned GE fill-latency and learned drop rates — both are **v2 refinements** noted below,
  not v1 dependencies.
- Multi-character / cross-character order coordination.

## Design Decisions (locked during brainstorming)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Scope | Both sides, one spec, shared escrow core |
| D2 | Order-state model | **Tracked escrow state** in `WorldState`; Lean decide-model + Oracle grow |
| D3 | Pricing rule | **Undercut best, floor-bounded, fail-closed** with no anchor |
| D4 | Cancel policy | **On-need + TTL** |
| D5 | Buy-post trigger | **Reactive means (option A)** — not an obtain-graph source |
| D6 | Bid vs craft | **Mutual exclusion**; static drop rate for craft-time estimate; learning store = v2 |
| D7 | Bid-fill horizon | **TTL-derived constant** (`TTL_CYCLES × avg_cycle_seconds`) |
| D8 | Sell batch size | Match **best standing sell order's qty** (existing data, no loader change) |

## Architecture

Seven components. §1–§3 are the shared core; §4–§6 are the legs and control; §7 is the
formal contract and the live-probe residuals.

### §1 — Order-state model (`WorldState`)

Today `WorldState` has no representation of an open/posted order — only `gold`, `inventory`,
`bank_gold`, and `pending_items` (claimable items, not escrow). Add:

```
open_orders: tuple[OpenOrder, ...] | None
# OpenOrder = (id: str, code: str, qty: int, price: int, side: BUY|SELL, age: int)
# Deterministically ordered by (side, code, price, id). No alphabetical/ repr tiebreak.
```

Escrow accounting in `apply()` (pure, optimistic — no API):

- **post SELL:** `inventory[code] -= qty`; append `OpenOrder(SELL)`. Item is locked
  (out of the bag, not in the bank).
- **post BUY:** `gold -= qty * price`; append `OpenOrder(BUY)`. Gold is locked.
- **fill** (a future event, only observed via §2 reconciliation): during *planning*,
  `apply()` does not simulate fills — a fill is an uncertain future event the planner cannot
  schedule. It only models post + cancel. The gold/item a fill yields is observed at
  execution time (§2), not minted in the plan.
- **cancel:** SELL → item returns; BUY → gold returns. *(Exact return destination —
  inventory vs `pending_items` — is a live-probe residual, §7.)*

`apply()` is the planner's **optimistic prediction**; §2 reconciliation against the API is
the source of truth. This mirrors how the fill actions already rebuild state from the API in
`execute()`.

> **⚠️ Correction (implementation, Task 8):** an earlier draft of this spec had reconciliation
> **credit gold on a filled SELL** and **append the item to `pending_items` on a filled BUY**.
> That is a **double-count bug**: `WorldState.from_character_schema` reads `gold` (and inventory,
> and `pending_items` via `_sync_pending`) **fresh from the character API every cycle**, and the
> server credits gold / delivers items on fill automatically — so those values already reflect any
> fill. Reconciliation therefore does **NOT** settle gold or pending. Its sole job is to keep
> `open_orders` (with correct `age`) tracked from the API. See §2.

### §2 — Reconciliation (API is truth, `apply()` is prediction)

At cycle start, read the character's own open orders from the account endpoint
(`my_account`). Diff against the last-known `open_orders` (held on a **player-persistent
attribute**, NOT on `WorldState` — non-GE action rebuilds reset `WorldState.open_orders` to
`()`, so `age` must be tracked off a store the action rebuilds don't wipe, else the TTL cancel
in §6 never fires):

- order absent, or its qty dropped → a **fill** occurred. Gold/item settlement is **already
  reflected** in this cycle's fresh API reads (see the §1 correction) — reconciliation does NOT
  re-credit; it only removes the order from tracking. `filled` is informational (logging).
- order still present at full qty → still open; increment `age`.

`GameData` already snapshots the *global* order book
(`_ge_buy_orders` / `_ge_sell_orders`, `game_data.py:554-566`, best-order-per-item). This
component adds a **per-character owned-orders** read — distinct from the global book, which
carries no ownership.

### §3 — Pricing (pure, Lean-proven, fail-closed)

Two pure functions mirroring `buy_source_venue.py` / `liquidation_venue.py`:

```
sell_post_price(best_sell: int | None, npc_sellback: int, margin: int) -> int | None
    None                                   if best_sell is None      # no anchor -> fail closed
    max(best_sell - 1, npc_sellback + margin)   otherwise

buy_post_price(best_buy: int | None, alt_cost: int, margin: int) -> int | None
    None                                   if best_buy is None       # no anchor -> fail closed
    min(best_buy + 1, alt_cost - margin)        otherwise
```

- Tick size assumed 1 gold (live-probe residual, §7).
- `alt_cost` for a buy = the realized cost of the cheapest alternative acquisition
  (NPC price, or a fillable sell order) — the ceiling that keeps posting weakly dominant.
- No live anchor ⇒ `None` ⇒ no post. This preserves the anti-surrogate guard verbatim: an
  empty book never triggers a speculative price.

### §4 — Venue decision: 2-way → 3-way

Extend both pure deciders from `{FILL, NPC}` to `{FILL, POST, NPC}`, staying pure and
Lean-proven:

- **Sell surplus:** if a standing buy order pays ≥ post-price → **FILL**;
  elif post-price > NPC floor → **POST**; else **NPC**.
- **Buy material:** if a standing sell order costs ≤ post-price → **FILL**;
  elif post-price < NPC cost → **POST**; else **NPC**.

FILL is preferred over POST whenever a fillable order gives terms at least as good, so
posting is strictly the "no one to trade with right now, but the book gives a price to
anchor to" fallback. This keeps the existing fill-first behavior intact.

**Buy-post is a reactive means, not an obtain-graph source (D5, option A).** A posted buy
fills asynchronously, so it cannot synchronously satisfy a planner material-need; modeling it
as a graph leaf would make the planner assume fills that have not happened. Instead: when the
planner would otherwise NPC-buy / fill a material **and** is not blocked on that material this
cycle, it posts a cheaper bid instead — opportunistic, exactly like the current
fill-injection into `GatherMaterialsGoal`. The obtain/requirement graph stays synchronous and
honest.

### §5 — Bid-vs-craft mutual exclusion (`bid_vs_craft.py`, new pure module)

A posted bid and a self-craft are two routes to the same item; running both wastes time.
New pure module decides and enforces exclusion.

- **Classify** the item's recipe closure: union `RequirementGraph.sources(x)`
  (`requirement_graph.py:123`) over `recipe_closure(item)`. Does it bottom out in `DROP`
  (monster drops) or only `GATHER` / deterministic sources?
- **Estimate craft-time (seconds)** — a new pure estimator (no standalone one exists today;
  cost currently lives only inside A*, `planner.py:99`):
  - deterministic legs (gather + craft): sum their per-edge costs directly (cheap, known).
  - DROP legs: `_expected_kills × fight-cost`, where `_expected_kills`
    (`monster_drop_selection.py:23`) uses the **static API drop `rate`** (1-in-N,
    `monster_catalog.py:39`). NOTE: the live A* fight-leg cost is currently *rate-blind*
    (`combat.py:160`, 1 kill = 1 drop); this estimator folds the static rate in so
    drop-based craft-time is honest without waiting on learned rates.
- **Bid-fill horizon** = `TTL_CYCLES × avg_cycle_seconds` (D7) — the same TTL that
  auto-cancels stale orders (§6), so the cancel backstop already bounds the downside.
- **Gate:** post a bid for X **only if** `est_craft_time(X) > bid_fill_horizon`
  (crafting is the genuinely slow path). Otherwise craft; never bid.
- **Suppress (both directions):** while a bid for X is open (X in `open_orders`), the
  acquisition layer treats X as in-flight → emits no craft/gather goal for X *or its
  materials*. Conversely, if an X-craft is already committed (sticky arbiter), do not bid X.
  Mutual exclusion is keyed on `open_orders` ∩ committed-plan.

**v2 refinement (not v1):** the learning store (`learning/store.py:78`) records
`actual_cooldown_seconds` and combat outcomes but **no drop rates and no fill latency**
(grep-confirmed). A future increment can add a drops-per-fight observation table to replace
the static `rate` with a measured one, and a fill-latency table to replace the TTL horizon
with an observed median. v1 uses static rate + TTL horizon and needs neither.

### §6 — Triggers and cancellation (arbiter placement)

- **post-sell** → extends the existing `SELL_PRESSURED` / `SELL_IDLE` means (band 4) and the
  `SELL_RELIEF` guard path when relieving pressure. Surplus is already computed by
  `accumulation_sell.py`; `liquidation_venue` now may return `POST`.
  **Batch size = best standing sell order's qty** (D8, `ge_best_sell_order` 3rd tuple
  element, `game_data.py:1072`) — post one batch per cycle and iterate under the sticky
  arbiter. Zero loader change.
- **post-buy** → new `MeansKind.GE_BID`, DISCRETIONARY band (per §4-A).
- **cancel on-need** → guard band (high priority): a gold-blocked purchase/craft with an
  open BUY order holding enough gold → cancel it; a needed item sitting in an open SELL
  order → cancel it. New `GuardKind` slot, or fold into the existing relief guards.
- **cancel on-TTL** → low-priority means sweep: `age > TTL_CYCLES` → cancel. Backstop that
  bounds worst-case capital lock and underwrites the liveness proof.

Per project convention (memory: recycle-surplus), a new `MeansKind` / `GuardKind` requires
`DecideKey.lean` + Oracle + `decide_key` updated in lockstep.

### §7 — Formal contract and live-probe residuals

Formal work (driven by the formal-development skill after spec approval) extends the existing
proven deciders rather than adding parallel ones:

- Extend `LiquidationVenue.lean` and `BuySourceVenue.lean` to the 3-way choice with
  **dominance theorems**: POST chosen ⇒ realized terms ≥ NPC alternative (sell) /
  ≤ NPC alternative (buy); no live anchor ⇒ no post.
- **Escrow conservation invariant:** post→cancel returns exactly what was locked;
  post→fill yields exactly `qty × price` gold (sell) or `qty` of the item (buy). No capital
  is minted or destroyed across the escrow lifecycle.
- **Liveness:** on-need + TTL cancellation ⇒ every posted order's locked capital is
  eventually freed (no permanent lock). No vacuous hypotheses.

Live-probe residuals (assert-then-probe, per project pattern — confirm on the first live
interaction, fail loudly on mismatch):

1. Does the GE charge a transaction tax/fee? The client schema exposes only `total_price`,
   no fee/tax field — confirm proceeds/cost match the modeled `qty × price` on first post.
2. On cancel, does the item/gold return to `inventory`/`gold` immediately, or land in
   `pending_items`?
3. Is there a maximum number of open orders per account? (Bounds how many batches can be
   posted concurrently.)
4. Is the price tick 1 gold?

## Component boundaries (isolation check)

| Unit | Does | Depends on |
|------|------|-----------|
| `WorldState.open_orders` + escrow in `apply()` | Hold posted-order state; predict settlement | none (pure data) |
| reconciliation | Correct prediction from API truth; detect fills | `my_account` read, `open_orders` |
| pricing (`sell_post_price`/`buy_post_price`) | Choose a fail-closed anchored price | book snapshot, NPC price |
| venue deciders (extended) | FILL vs POST vs NPC | pricing, book snapshot |
| `bid_vs_craft.py` | Gate bidding; suppress double-acquire | requirement graph, drop rate, TTL horizon, `open_orders` |
| post/cancel actions | Execute the API calls; mutate escrow | action base, client wrappers |
| triggers/guards/means | Place the actions in the arbiter | tier kinds, DecideKey/Oracle |

Each unit is pure or thin, testable in isolation, and communicates through explicit values.

## Testing / success criteria

Per project standard: 0 errors, 0 warnings, 0 skipped, 100% coverage on new code; the
differential + mutation gate must show the running code computes the same function as the
Lean model; runtime activation verified on a live `plan <char>` (green tests ≠ runtime-active
— the venue/pricing/goal changes must actually fire).

## Build sequence (for the implementation plan)

1. Order-state model + escrow `apply()` (§1) + reconciliation (§2).
2. Pure pricing (§3) + Lean extension of the two deciders (§7, dominance + fail-closed).
3. Venue 3-way extension (§4) + post/cancel actions (§5-actions).
4. `bid_vs_craft.py` estimator + suppression (§5).
5. Arbiter placement: means/guard kinds + DecideKey/Oracle lockstep (§6).
6. Escrow-conservation + liveness proofs (§7); mutation/diff gate green.
7. Live-probe residuals resolved on first live run; runtime activation confirmed.
